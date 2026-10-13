import hashlib
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import aiomysql
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from auth import require_server_key
from db import get_db
from models import LoginRequest, RegisterRequest, VerifyRequest

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)
ph = PasswordHasher()

IME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
MIN_LOZINKA, MAX_LOZINKA = 8, 128
TRAJANJE_SESIJE = timedelta(days=7)

# Ogranicenje pokusaja, u memoriji (vazi uz jedan uvicorn worker).
LOGIN_LIMIT, LOGIN_PROZOR = 5, 300      # 5 neuspelih / 5 min po (ime, ip)
REG_LIMIT, REG_PROZOR = 5, 3600         # 5 registracija / sat po ip
_neuspeli_login: dict = defaultdict(deque)
_registracije: dict = defaultdict(deque)
# MariaDB: 1020 = red promenjen posle snapshot-a (innodb_snapshot_isolation), 1213 = deadlock
PROLAZNE_GRESKE = (1020, 1213)
MAX_POKUSAJA = 3

# Za nepostojece naloge i dalje radimo verify, da vreme odgovora ne otkrije
# da li ime postoji.
_LAZNI_HASH = ph.hash(secrets.token_urlsafe(16))


def _greska(status: int, poruka: str) -> JSONResponse:
    return JSONResponse({"error": poruka}, status_code=status)


def _hash_tokena(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _sada_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _ogranicen(tabela: dict, kljuc, limit: int, prozor: int) -> bool:
    sada = time.monotonic()
    q = tabela[kljuc]
    while q and sada - q[0] > prozor:
        q.popleft()
    if not q:
        tabela.pop(kljuc, None)
        return False
    return len(q) >= limit


def _zabelezi(tabela: dict, kljuc) -> None:
    tabela[kljuc].append(time.monotonic())


def _proveri_lozinku(pw_hash: str, lozinka: str) -> bool:
    try:
        return ph.verify(pw_hash, lozinka)
    except (VerificationError, InvalidHashError):
        return False


def _validna_lozinka(lozinka: str) -> bool:
    return MIN_LOZINKA <= len(lozinka) <= MAX_LOZINKA


# ---------------------------------------------------------------- REGISTER

@router.post("/register")
async def register(data: RegisterRequest, request: Request, conn=Depends(get_db)):
    ip = _ip(request)
    if _ogranicen(_registracije, ip, REG_LIMIT, REG_PROZOR):
        return _greska(429, "Previse registracija, pokusaj kasnije")

    ime = data.username.strip()
    if not IME_RE.match(ime):
        return _greska(400, "Ime mora imati 3-16 znakova: slova, brojevi, _")
    if not _validna_lozinka(data.password):
        return _greska(400, f"Lozinka mora imati {MIN_LOZINKA}-{MAX_LOZINKA} znakova")

    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT 1 FROM accounts WHERE username = %s", (ime,))
        zauzeto = await cur.fetchone()
        if not zauzeto:
            await cur.execute("SELECT 1 FROM players WHERE ime = %s", (ime,))
            zauzeto = await cur.fetchone()
        if zauzeto:
            return _greska(409, "Ime je zauzeto")

        pw_hash = await run_in_threadpool(ph.hash, data.password)
        try:
            await cur.execute(
                "INSERT INTO accounts (username, password_hash) VALUES (%s, %s)",
                (ime, pw_hash),
            )
            account_id = cur.lastrowid
            await cur.execute(
                "INSERT INTO players (ime, account_id) VALUES (%s, %s)",
                (ime, account_id),
            )
        except aiomysql.IntegrityError:
            # dva istovremena zahteva za isto ime
            await conn.rollback()
            return _greska(409, "Ime je zauzeto")
        await conn.commit()

    _zabelezi(_registracije, ip)
    return {"status": "ok", "username": ime}


# ---------------------------------------------------------------- LOGIN

@router.post("/login")
async def login(data: LoginRequest, request: Request, conn=Depends(get_db)):
    ime = data.username.strip()
    kljuc = (ime.lower(), _ip(request))
    if _ogranicen(_neuspeli_login, kljuc, LOGIN_LIMIT, LOGIN_PROZOR):
        return _greska(429, "Previse neuspelih pokusaja, sacekaj par minuta")
    if not _validna_lozinka(data.password):
        _zabelezi(_neuspeli_login, kljuc)
        return _greska(401, "Pogresno ime ili lozinka")

    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("""
            SELECT a.id, a.username, a.password_hash, p.ime AS ime_lika
            FROM accounts a LEFT JOIN players p ON p.account_id = a.id
            WHERE a.username = %s
        """, (ime,))
        nalog = await cur.fetchone()

        pw_hash = nalog["password_hash"] if nalog else _LAZNI_HASH
        ok = await run_in_threadpool(_proveri_lozinku, pw_hash, data.password)
        if not nalog or not ok:
            _zabelezi(_neuspeli_login, kljuc)
            return _greska(401, "Pogresno ime ili lozinka")

        _neuspeli_login.pop(kljuc, None)

        if ph.check_needs_rehash(nalog["password_hash"]):
            novi = await run_in_threadpool(ph.hash, data.password)
            await cur.execute(
                "UPDATE accounts SET password_hash = %s WHERE id = %s", (novi, nalog["id"])
            )

        # Kraj transakcije odmah posle provere lozinke: sesija se upisuje u novoj, bez snapshot-a
        # uzetog pre (spore) provere, inace MariaDB baci 1020 kad se dve prijave preklope.
        await conn.commit()

        token = secrets.token_urlsafe(32)
        istice = _sada_utc() + TRAJANJE_SESIJE

        # Novi login zamenjuje staru sesiju (UNIQUE account_id, migracija 004): jedan upsert,
        # bez DELETE-a i njegovog gap lock-a. Na prolaznu gresku rollback i cela transakcija
        # ispocetka, najvise MAX_POKUSAJA puta.
        for pokusaj in range(1, MAX_POKUSAJA + 1):
            try:
                await cur.execute("""
                    INSERT INTO sessions (token_hash, account_id, expires_at) VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE token_hash = VALUES(token_hash),
                        expires_at = VALUES(expires_at), created_at = CURRENT_TIMESTAMP
                """, (_hash_tokena(token), nalog["id"], istice))
                await conn.commit()
                break
            except aiomysql.OperationalError as e:
                await conn.rollback()
                if pokusaj == MAX_POKUSAJA or e.args[0] not in PROLAZNE_GRESKE:
                    raise
                log.warning("login: sesija, greska %s, pokusaj %d/%d, ponavljam", e.args[0], pokusaj, MAX_POKUSAJA)

    # Istekle sesije svih naloga: posebna transakcija, greska ne rusi prijavu (sledeci login pokusava opet).
    try:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM sessions WHERE expires_at < UTC_TIMESTAMP()")
        await conn.commit()
    except aiomysql.Error as e:
        await conn.rollback()
        log.warning("login: ciscenje isteklih sesija preskoceno (%s)", e.args[0] if e.args else e)

    return {
        "status": "ok",
        "token": token,
        "expires_at": istice.isoformat() + "Z",
        "username": nalog["username"],
        "ime_lika": nalog["ime_lika"],
    }


# ---------------------------------------------------------------- LOGOUT

@router.post("/logout")
async def logout(authorization: str = Header(default=""), conn=Depends(get_db)):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return _greska(401, "Nedostaje token")
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM sessions WHERE token_hash = %s", (_hash_tokena(token),))
        await conn.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------- VERIFY (samo game server)

@router.post("/verify", dependencies=[Depends(require_server_key)])
async def verify(data: VerifyRequest, conn=Depends(get_db)):
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("""
            SELECT a.id AS account_id, a.username, p.ime AS ime_lika
            FROM sessions s
            JOIN accounts a ON a.id = s.account_id
            LEFT JOIN players p ON p.account_id = a.id
            WHERE s.token_hash = %s AND s.expires_at > UTC_TIMESTAMP()
        """, (_hash_tokena(data.token),))
        row = await cur.fetchone()
    if not row or not row["ime_lika"]:
        return _greska(401, "Nevazeci ili istekao token")
    return {"status": "ok", **row}