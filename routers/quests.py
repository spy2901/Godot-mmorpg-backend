import aiomysql
from fastapi import APIRouter, Depends

from auth import require_server_key
from db import get_db

router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("")
async def get_all_quests(conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM quests")
        quests = await cur.fetchall()
    return {"quests": quests}


# MORA biti pre /{quest_id}, inace "completed" bude uhvacen kao quest_id
@router.get("/completed/{ime}", dependencies=[Depends(require_server_key)])
async def get_completed_quests_for_player(ime: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT quest_id FROM zavrseni_questovi WHERE player_ime = %s", (ime,))
        rows = await cur.fetchall()
    return {"completed": [r["quest_id"] for r in rows]}


@router.get("/{quest_id}")
async def get_quest(quest_id: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM quests WHERE id = %s", (quest_id,))
        quest = await cur.fetchone()
    if not quest:
        return {"error": "Quest not found"}
    return quest

