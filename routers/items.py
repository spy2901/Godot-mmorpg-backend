import aiomysql
from fastapi import APIRouter, Depends

from db import get_db

router = APIRouter(prefix="/items", tags=["items"])


@router.get("")
async def get_all_items(conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM items")
        items = await cur.fetchall()
    return {"items": items}


@router.get("/{item_id}")
async def get_item(item_id: str, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
        item = await cur.fetchone()
    if item:
        return item
    return {"error": "Item not found"}
