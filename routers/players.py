import json
import logging
from collections import Counter

import aiomysql
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from auth import require_server_key
from db import get_db
from models import (GoldChange, InventoryChange, ItemUse, PlayerSave,
                    QuestAccept, QuestKill, QuestTurnin, ShopBuy, XpChange)
from routers.inventory_utils import (MAX_SLOTOVA, dodaj_u_inventar,
                                     ukloni_iz_inventara)

# Ceo ruter je samo za game server: sve rute traze X-Server-Key.
router = APIRouter(
    prefix="/players", tags=["players"],
    dependencies=[Depends(require_server_key)],
)
log = logging.getLogger(__name__)

SLOTOVI_OPREME = {"head", "chest", "legs", "boots", "weapon", "shield"}


def _decode_player(row: dict) -> dict:
    row["inventory"] = json.loads(row.get("inventory") or "[]")
    row["equipment"] = json.loads(row.get("equipment") or "{}")
    return row


def _prazno(v) -> bool:
    # NULL i prazan string se tretiraju isto
    return v is None or str(v).strip() == ""


async def _greska(conn, poruka: str) -> dict:
    await conn.rollback()
    return {"error": poruka}


async def _zakljucaj_igraca(cur, ime: str, kolone: str):
    await cur.execute(f"SELECT {kolone} FROM players WHERE ime = %s FOR UPDATE", (ime,))
    return await cur.fetchone()


async def _je_zavrsen(cur, ime: str, quest_id: str) -> bool:
    await cur.execute(
        "SELECT 1 FROM zavrseni_questovi WHERE player_ime = %s AND quest_id = %s",
        (ime, quest_id),
    )
    return await cur.fetchone() is not None


XP_KOLONE = "level, xp, max_xp, max_hp, max_mana, napad_damage"


def _primeni_xp(row: dict, delta: int) -> dict:
    s = {k: int(row[k] or 0) for k in XP_KOLONE.split(", ")}
    s["max_xp"] = max(s["max_xp"], 1)  # max_xp 0 bi dao beskonacnu petlju
    s["xp"] += max(delta, 0)
    s["level_up"] = False
    while s["xp"] >= s["max_xp"]:
        s["xp"] -= s["max_xp"]
        s["level"] += 1
        # celobrojno, jer npr. int(100 * 1.15) == 114 zbog float greske
        s["max_xp"] = s["max_xp"] * 3 // 2
        s["max_hp"] = s["max_hp"] * 115 // 100
        s["max_mana"] = s["max_mana"] * 11 // 10
        s["napad_damage"] = s["napad_damage"] * 11 // 10
        s["level_up"] = True
    return s


async def _upisi_xp(cur, ime: str, s: dict):
    kolone = XP_KOLONE.split(", ")
    vrednosti = [s[k] for k in kolone]
    if s["level_up"]:  # level up puni hp i manu na NOVE maksimume
        kolone += ["hp", "mana"]
        vrednosti += [s["max_hp"], s["max_mana"]]
    postavi = ", ".join(f"{k} = %s" for k in kolone)
    await cur.execute(f"UPDATE players SET {postavi} WHERE ime = %s", (*vrednosti, ime))


async def _validna_oprema(cur, eq: dict) -> bool:
    ids = {v for v in eq.values() if not _prazno(v)}
    if not ids:
        return True
    await cur.execute(
        f"SELECT id, tip FROM items WHERE id IN ({', '.join(['%s'] * len(ids))})",
        tuple(ids),
    )
    tipovi = {r["id"]: r["tip"] for r in await cur.fetchall()}
    for slot, item_id in eq.items():
        if _prazno(item_id):
            continue
        if item_id not in tipovi:
            return False
        if tipovi[item_id] != ("weapon" if slot == "weapon" else "armor"):
            return False
    return True


@router.get("/{ime}")
async def get_player(ime: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM players WHERE ime = %s", (ime,))
        player = await cur.fetchone()
        if not player:
            return JSONResponse({"error": "Player not found"}, status_code=404)
    return _decode_player(player)


# ---------- save: klijent sme samo hp, manu, poziciju i preraspored inventara ----------

def _je_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _prebroj(inv: list, eq: dict) -> Counter:
    # Stari unosi bez "slot" se broje normalno; opremljen item = 1 komad.
    c = Counter()
    for e in inv:
        c[e["id"]] += int(e.get("kolicina", 1))
    for item_id in eq.values():
        if not _prazno(item_id):
            c[item_id] += 1
    return c


def _validan_raspored(inv, eq, db_inv: list, db_eq: dict) -> bool:
    if not isinstance(inv, list) or not isinstance(eq, dict):
        return False
    slotovi = set()
    for e in inv:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            return False
        kol, slot = e.get("kolicina"), e.get("slot")
        if not _je_int(kol) or kol < 1:
            return False
        if not _je_int(slot) or not 0 <= slot < MAX_SLOTOVA or slot in slotovi:
            return False
        slotovi.add(slot)
    for k, v in eq.items():
        if k not in SLOTOVI_OPREME:
            return False
        if not (v is None or isinstance(v, str)):
            return False
    return _prebroj(inv, eq) == _prebroj(db_inv, db_eq)


@router.post("/{ime}/save")
async def save_player(ime: str, data: PlayerSave, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        kolone = "inventory, equipment, max_hp, max_mana"
        row = await _zakljucaj_igraca(cur, ime, kolone)
        if not row:
            return await _greska(conn, "Player not found")

        db_inv = json.loads(row["inventory"] or "[]")
        db_eq = json.loads(row["equipment"] or "{}")
        if (_validan_raspored(data.inventory, data.equipment, db_inv, db_eq)
                and await _validna_oprema(cur, data.equipment)):
            inventory, equipment = json.dumps(data.inventory), json.dumps(data.equipment)
        else:
            log.warning("save %r: neispravan inventory/equipment, zadrzano stanje iz baze", ime)
            inventory, equipment = row["inventory"], row["equipment"]

        hp = min(max(data.hp, 1), int(row["max_hp"]))
        mana = min(max(data.mana, 0), int(row["max_mana"]))

        await cur.execute("""
            UPDATE players SET
                hp = %s, mana = %s,
                pos_x = %s, pos_y = %s, pos_z = %s,
                inventory = %s, equipment = %s
            WHERE ime = %s
        """, (
            hp, mana,
            data.pos_x, data.pos_y, data.pos_z,
            inventory, equipment, ime,
        ))
        await conn.commit()
    return {"status": "ok"}


# ---------- izmene stanja igraca ----------

@router.post("/{ime}/inventory/change")
async def promeni_inventar(ime: str, data: InventoryChange, conn=Depends(get_db)):
    if data.delta == 0:
        return {"error": "delta ne sme biti 0"}

    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT id, stackable, max_stack, vrednost FROM items WHERE id = %s", (data.item_id,))
        item = await cur.fetchone()
        if not item:
            return {"error": "Item not found"}

        # zaključaj red igrača da dva zahteva ne upišu istovremeno
        row = await _zakljucaj_igraca(cur, ime, "inventory")
        if not row:
            return {"error": "Player not found"}

        inv = json.loads(row["inventory"] or "[]")

        if data.delta > 0:
            if not dodaj_u_inventar(inv, item, data.delta):
                return await _greska(conn, "Inventory pun")
        elif not ukloni_iz_inventara(inv, data.item_id, -data.delta):
            return await _greska(conn, "Nedovoljno itema")

        await cur.execute(
            "UPDATE players SET inventory = %s WHERE ime = %s",
            (json.dumps(inv), ime)
        )
        await conn.commit()

    return {"status": "ok", "inventory": inv}


@router.post("/{ime}/gold/change")
async def promeni_gold(ime: str, data: GoldChange, conn=Depends(get_db)):
    if data.delta == 0:
        return {"error": "delta ne sme biti 0"}

    async with conn.cursor(aiomysql.DictCursor) as cur:
        # zaključaj red da dva istovremena zahteva ne prepišu jedan drugi
        row = await _zakljucaj_igraca(cur, ime, "gold")
        if not row:
            return await _greska(conn, "Player not found")

        novo = int(row["gold"]) + data.delta
        if novo < 0:
            return await _greska(conn, "Nedovoljno golda")

        await cur.execute("UPDATE players SET gold = %s WHERE ime = %s", (novo, ime))
        await conn.commit()

    return {"status": "ok", "gold": novo}


@router.post("/{ime}/xp/change")
async def promeni_xp(ime: str, data: XpChange, conn=Depends(get_db)):
    if data.delta <= 0:
        return {"error": "delta mora biti > 0"}

    async with conn.cursor(aiomysql.DictCursor) as cur:
        row = await _zakljucaj_igraca(cur, ime, XP_KOLONE)
        if not row:
            return await _greska(conn, "Player not found")

        s = _primeni_xp(row, data.delta)
        await _upisi_xp(cur, ime, s)
        await conn.commit()

    return {"status": "ok", **s}


@router.post("/{ime}/shop/buy")
async def kupi(ime: str, data: ShopBuy, conn=Depends(get_db)):
    if not 1 <= data.kolicina <= 99:
        return {"error": "kolicina mora biti 1..99"}

    async with conn.cursor(aiomysql.DictCursor) as cur:
        row = await _zakljucaj_igraca(cur, ime, "gold, inventory")
        if not row:
            return await _greska(conn, "Player not found")

        await cur.execute(
            "SELECT id, stackable, max_stack, vrednost, quest_item FROM items WHERE id = %s",
            (data.item_id,),
        )
        item = await cur.fetchone()
        if not item:
            return await _greska(conn, "Item not found")
        if item["quest_item"] == 1 or int(item["vrednost"] or 0) <= 0:
            return await _greska(conn, "Item nije na prodaju")

        cena = int(item["vrednost"]) * data.kolicina
        gold = int(row["gold"])
        if gold < cena:
            return await _greska(conn, "Nedovoljno golda")

        inv = json.loads(row["inventory"] or "[]")
        if not dodaj_u_inventar(inv, item, data.kolicina):
            return await _greska(conn, "Inventory pun")

        novo = gold - cena
        await cur.execute(
            "UPDATE players SET gold = %s, inventory = %s WHERE ime = %s",
            (novo, json.dumps(inv), ime),
        )
        await conn.commit()

    return {"status": "ok", "gold": novo, "inventory": inv}


@router.post("/{ime}/item/use")
async def upotrebi_item(ime: str, data: ItemUse, conn=Depends(get_db)):
    # Backend ne zna trenutni hp/manu (drzi ih game server): samo trosi komad i vraca efekat.
    async with conn.cursor(aiomysql.DictCursor) as cur:
        row = await _zakljucaj_igraca(cur, ime, "inventory")
        if not row:
            return await _greska(conn, "Player not found")

        await cur.execute(
            "SELECT id, tip, hp_efekat, mana_efekat, cooldown_ms FROM items WHERE id = %s",
            (data.item_id,),
        )
        item = await cur.fetchone()
        if not item:
            return await _greska(conn, "Item not found")
        if item["tip"] != "consumable" or item["hp_efekat"] + item["mana_efekat"] <= 0:
            return await _greska(conn, "Item nije potrosni")

        # samo inventory; opremljeno se ne racuna
        inv = json.loads(row["inventory"] or "[]")
        if not ukloni_iz_inventara(inv, data.item_id, 1):
            return await _greska(conn, "Nedovoljno itema")

        await cur.execute(
            "UPDATE players SET inventory = %s WHERE ime = %s", (json.dumps(inv), ime)
        )
        await conn.commit()

    return {
        "status": "ok",
        "item_id": item["id"],
        "hp_efekat": item["hp_efekat"],
        "mana_efekat": item["mana_efekat"],
        "cooldown_ms": item["cooldown_ms"],
        "inventory": inv,
    }


@router.post("/{ime}/quest/accept")
async def prihvati_quest(ime: str, data: QuestAccept, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        row = await _zakljucaj_igraca(cur, ime, "aktivni_quest_id")
        if not row:
            return await _greska(conn, "Player not found")

        await cur.execute("SELECT * FROM quests WHERE id = %s", (data.quest_id,))
        quest = await cur.fetchone()
        if not quest:
            return await _greska(conn, "Quest not found")
        if await _je_zavrsen(cur, ime, data.quest_id):
            return await _greska(conn, "Quest vec zavrsen")
        if not _prazno(row["aktivni_quest_id"]):
            return await _greska(conn, "Vec imas aktivan quest")

        # lanac: svaki quest kome je ovaj sledeci_quest mora biti zavrsen
        await cur.execute("""
            SELECT q.id FROM quests q
            LEFT JOIN zavrseni_questovi z ON z.quest_id = q.id AND z.player_ime = %s
            WHERE q.sledeci_quest = %s AND z.quest_id IS NULL
            LIMIT 1
        """, (ime, data.quest_id))
        if await cur.fetchone():
            return await _greska(conn, "Prethodni quest nije zavrsen")

        await cur.execute(
            "UPDATE players SET aktivni_quest_id = %s, quest_progres = 0 WHERE ime = %s",
            (data.quest_id, ime),
        )
        await conn.commit()

    return {"status": "ok", "quest": quest}


@router.post("/{ime}/quest/kill")
async def quest_kill(ime: str, data: QuestKill, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        row = await _zakljucaj_igraca(cur, ime, "aktivni_quest_id, quest_progres")
        if not row:
            return await _greska(conn, "Player not found")

        progres = int(row["quest_progres"] or 0)
        quest = None
        if not _prazno(row["aktivni_quest_id"]):
            await cur.execute(
                "SELECT tip, cilj, kolicina FROM quests WHERE id = %s",
                (row["aktivni_quest_id"],),
            )
            quest = await cur.fetchone()

        if (quest and quest["tip"] == "kill" and quest["cilj"] == data.tip
                and progres < int(quest["kolicina"])):
            progres += 1
            await cur.execute(
                "UPDATE players SET quest_progres = %s WHERE ime = %s", (progres, ime)
            )
            await conn.commit()
        else:
            await conn.rollback()  # nista za upis, samo pusti zakljucavanje

    return {"status": "ok", "quest_progres": progres}


@router.post("/{ime}/quest/abandon")
async def napusti_quest(ime: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        if not await _zakljucaj_igraca(cur, ime, "ime"):
            return await _greska(conn, "Player not found")
        await cur.execute(
            "UPDATE players SET aktivni_quest_id = NULL, quest_progres = 0 WHERE ime = %s",
            (ime,),
        )
        await conn.commit()
    return {"status": "ok"}


@router.post("/{ime}/quest/turnin")
async def predaj_quest(ime: str, data: QuestTurnin, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        row = await _zakljucaj_igraca(
            cur, ime, f"gold, inventory, aktivni_quest_id, quest_progres, {XP_KOLONE}"
        )
        if not row:
            return await _greska(conn, "Player not found")
        if _prazno(row["aktivni_quest_id"]) or row["aktivni_quest_id"] != data.quest_id:
            return await _greska(conn, "Quest nije aktivan")

        await cur.execute("SELECT * FROM quests WHERE id = %s", (data.quest_id,))
        quest = await cur.fetchone()
        if not quest:
            return await _greska(conn, "Quest not found")
        if await _je_zavrsen(cur, ime, data.quest_id):
            return await _greska(conn, "Quest vec zavrsen")

        inv = json.loads(row["inventory"] or "[]")
        kolicina = int(quest["kolicina"] or 0)
        if quest["tip"] == "kill":
            if int(row["quest_progres"] or 0) < kolicina:
                return await _greska(conn, "Quest nije zavrsen")
        elif quest["tip"] == "fetch":
            if not ukloni_iz_inventara(inv, quest["cilj"], kolicina):
                return await _greska(conn, "Nedovoljno itema")
        else:
            return await _greska(conn, "Nepoznat tip questa")

        nagrada_gold = int(quest["nagrada_gold"] or 0)
        gold = int(row["gold"]) + max(nagrada_gold, 0)

        nagrada_item = None if _prazno(quest["nagrada_item"]) else quest["nagrada_item"]
        if nagrada_item:
            await cur.execute(
                "SELECT id, stackable, max_stack FROM items WHERE id = %s", (nagrada_item,)
            )
            item = await cur.fetchone()
            if not item:
                return await _greska(conn, "Nagrada item ne postoji")
            if not dodaj_u_inventar(inv, item, 1):
                return await _greska(conn, "Inventory pun")

        try:
            await cur.execute(
                "INSERT INTO zavrseni_questovi (player_ime, quest_id) VALUES (%s, %s)",
                (ime, data.quest_id),
            )
        except aiomysql.IntegrityError:
            return await _greska(conn, "Quest vec zavrsen")

        await cur.execute("""
            UPDATE players SET gold = %s, inventory = %s,
                aktivni_quest_id = NULL, quest_progres = 0
            WHERE ime = %s
        """, (gold, json.dumps(inv), ime))

        nagrada_xp = max(int(quest["nagrada_xp"] or 0), 0)
        s = _primeni_xp(row, nagrada_xp)
        await _upisi_xp(cur, ime, s)
        await conn.commit()

    sledeci = None if _prazno(quest["sledeci_quest"]) else quest["sledeci_quest"]
    return {
        "status": "ok",
        "nagrada": {
            "naziv": quest["naziv"],
            "gold": max(nagrada_gold, 0),
            "xp": int(quest["nagrada_xp"] or 0),
            "item": nagrada_item,
            "sledeci_quest": sledeci,
        },
        "quest": quest,
        "gold": gold,
        "inventory": inv,
        "stats": s,
    }
