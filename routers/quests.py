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
@router.get("/completed")
async def get_completed_quests(conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT quest_id FROM zavrseni_questovi")
        rows = await cur.fetchall()
    return {"completed": [r["quest_id"] for r in rows]}


@router.get("/completed/{ime}")
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


@router.post("/{quest_id}/complete", dependencies=[Depends(require_server_key)])
async def complete_quest(quest_id: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM quests WHERE id = %s", (quest_id,))
        quest = await cur.fetchone()
        if not quest:
            return {"error": "Quest not found"}
        try:
            await cur.execute(
                "INSERT INTO zavrseni_questovi (quest_id) VALUES (%s)",
                (quest_id,)
            )
            await conn.commit()
        except Exception:
            pass  # vec zavrsen (UNIQUE constraint) - nije greska
    return {"status": "ok", "quest_id": quest_id}


@router.post("/{quest_id}/complete/{ime}", dependencies=[Depends(require_server_key)])
async def complete_quest_for_player(quest_id: str, ime: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT id FROM quests WHERE id = %s", (quest_id,))
        if not await cur.fetchone():
            return {"error": "Quest not found"}
        await cur.execute(
            "INSERT IGNORE INTO zavrseni_questovi (player_ime, quest_id) VALUES (%s, %s)",
            (ime, quest_id)
        )
        await conn.commit()
    return {"status": "ok", "quest_id": quest_id}
