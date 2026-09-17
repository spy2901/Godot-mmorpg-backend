import aiomysql

DB_CONFIG = {
    "host": "localhost",
    "port": 8889,  # MAMP koristi port 8889
    "user": "root",
    "password": "root",  # MAMP default
    "db": "mmorpg"
}


async def get_db():
    conn = await aiomysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()
