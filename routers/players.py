import json

import aiomysql
from fastapi import APIRouter, Depends

from db import get_db
from models import PlayerSave

router = APIRouter(prefix="/players", tags=["players"])


def _decode_player(row: dict) -> dict:
    # inventory i equipment su LONGTEXT sa JSON stringom
    row["inventory"] = json.loads(row.get("inventory") or "[]")
    row["equipment"] = json.loads(row.get("equipment") or "{}")
    return row


@router.get("/{ime}")
async def get_player(ime: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM players WHERE ime = %s", (ime,))
        player = await cur.fetchone()
        if not player:
            # auto-kreiranje igraca sa default vrednostima
            d = PlayerSave()
            await cur.execute(
                "INSERT INTO players (ime, level, xp, gold, hp, max_hp, inventory, equipment) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (ime, d.level, d.xp, d.gold, d.hp, d.max_hp,
                 json.dumps(d.inventory), json.dumps(d.equipment)),
            )
            await conn.commit()
            await cur.execute("SELECT * FROM players WHERE ime = %s", (ime,))
            player = await cur.fetchone()
    return _decode_player(player)


@router.post("/{ime}/save")
async def save_player(ime: str, data: PlayerSave, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            "INSERT INTO players (ime, level, xp, gold, hp, max_hp, inventory, equipment) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE level=VALUES(level), xp=VALUES(xp), gold=VALUES(gold), "
            "hp=VALUES(hp), max_hp=VALUES(max_hp), inventory=VALUES(inventory), "
            "equipment=VALUES(equipment)",
            (ime, data.level, data.xp, data.gold, data.hp, data.max_hp,
             json.dumps(data.inventory), json.dumps(data.equipment)),
        )
        await conn.commit()
    return {"status": "ok", "ime": ime}
