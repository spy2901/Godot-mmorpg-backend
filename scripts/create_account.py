"""Pravi nalog i vezuje ga za postojeceg lika istog imena (ako nije vec vezan).

Upotreba (na Pi-ju, iz ~/mmorpg-backend, sa aktivnim venv):
    python -m scripts.create_account spy
"""
import asyncio
import getpass
import re
import sys

import aiomysql
from argon2 import PasswordHasher

from db import get_db

IME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
MIN_LOZINKA = 8


async def main(username: str) -> int:
    if not IME_RE.match(username):
        print("Ime mora imati 3-16 znakova: slova, brojevi, _")
        return 1

    lozinka = getpass.getpass("Lozinka: ")
    if len(lozinka) < MIN_LOZINKA:
        print(f"Lozinka mora imati bar {MIN_LOZINKA} znakova")
        return 1
    if lozinka != getpass.getpass("Ponovi lozinku: "):
        print("Lozinke se ne poklapaju")
        return 1

    pw_hash = PasswordHasher().hash(lozinka)

    gen = get_db()
    conn = await gen.__anext__()
    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM accounts WHERE username = %s", (username,))
            if await cur.fetchone():
                print("Nalog vec postoji")
                return 1

            await cur.execute(
                "INSERT INTO accounts (username, password_hash) VALUES (%s, %s)",
                (username, pw_hash),
            )
            account_id = cur.lastrowid

            await cur.execute(
                "SELECT ime, account_id FROM players WHERE ime = %s FOR UPDATE", (username,)
            )
            lik = await cur.fetchone()
            if lik is None:
                await cur.execute(
                    "INSERT INTO players (ime, account_id) VALUES (%s, %s)",
                    (username, account_id),
                )
                print(f"Napravljen nalog #{account_id} i novi lik '{username}'")
            elif lik["account_id"] is None:
                await cur.execute(
                    "UPDATE players SET account_id = %s WHERE ime = %s",
                    (account_id, username),
                )
                print(f"Napravljen nalog #{account_id}, vezan postojeci lik '{username}'")
            else:
                await conn.rollback()
                print("Lik vec pripada drugom nalogu, nista nije upisano")
                return 1

            await conn.commit()
            return 0
    finally:
        await gen.aclose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(asyncio.run(main(sys.argv[1])))