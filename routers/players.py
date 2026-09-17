import json

import aiomysql
from fastapi import APIRouter, Depends

from db import get_db
from models import PlayerSave

router = APIRouter(prefix="/players", tags=["players"])


def _decode_player(row: dict) -> dict:
    row["inventory"] = json.loads(row.get("inventory") or "[]")
    row["equipment"] = json.loads(row.get("equipment") or "{}")
    return row


@router.get("/{ime}")
async def get_player(ime: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM players WHERE ime = %s", (ime,))
        player = await cur.fetchone()
        if not player:
            await cur.execute("INSERT INTO players (ime) VALUES (%s)", (ime,))
            await conn.commit()
            await cur.execute("SELECT * FROM players WHERE ime = %s", (ime,))
            player = await cur.fetchone()
    return _decode_player(player)


@router.post("/{ime}/save")
async def save_player(ime: str, data: PlayerSave, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("""
            INSERT INTO players
                (ime, level, xp, max_xp, gold, hp, max_hp, mana, max_mana, napad_damage,
                 pos_x, pos_y, pos_z, inventory, equipment, aktivni_quest_id, quest_progres)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                level = VALUES(level), xp = VALUES(xp), max_xp = VALUES(max_xp),
                gold = VALUES(gold), hp = VALUES(hp), max_hp = VALUES(max_hp),
                mana = VALUES(mana), max_mana = VALUES(max_mana),
                napad_damage = VALUES(napad_damage),
                pos_x = VALUES(pos_x), pos_y = VALUES(pos_y), pos_z = VALUES(pos_z),
                inventory = VALUES(inventory), equipment = VALUES(equipment),
                aktivni_quest_id = VALUES(aktivni_quest_id),
                quest_progres = VALUES(quest_progres)
        """, (
            ime, data.level, data.xp, data.max_xp, data.gold, data.hp, data.max_hp,
            data.mana, data.max_mana, data.napad_damage,
            data.pos_x, data.pos_y, data.pos_z,
            json.dumps(data.inventory), json.dumps(data.equipment),
            data.aktivni_quest_id, data.quest_progres
        ))
        await conn.commit()
    return {"status": "ok"}