"""Test migracije 010 (buffovi) i njenog rollback-a na posebnoj bazi mmorpg_test_010.
Struktura i podaci items i quests se kopiraju iz baze DB_NAME (podaci te baze se ne diraju), players samo struktura.
Ako DB_NAME još nije posle 009 (npr. tests/run_with_temp_db.sh staje na 007), kopija se prvo dovede do 009.
Za stvarnu šemu i redove items (utf8mb3) DB_NAME treba da bude kopija sa Pi-ja (mariadb-dump --no-data + items/quests).
Traži mariadb CLI (DELIMITER blokovi) i pravo CREATE DATABASE.
Pokretanje: DB_HOST=127.0.0.1 DB_PORT=33077 DB_USER=root DB_PASSWORD=... python3.12 test_migracija_010.py"""
import hashlib
import os
import subprocess

import pymysql

from db import DB_CONFIG

TEST_DB = "mmorpg_test_010"
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
MIGRACIJA = os.path.join(DIR, "010_buffovi.sql")
ROLLBACK = os.path.join(DIR, "010_buffovi_rollback.sql")
MIGRACIJA_009 = os.path.join(DIR, "009_sadrzaj.sql")

BUFFOVI = {  # id: (buff_tip, buff_vrednost, buff_trajanje_ms)
    "elixir_of_strength": ("napad", 20, 60000), "elixir_of_defense": ("oklop", 30, 60000),
    "elixir_of_wisdom": ("xp", 25, 300000), "elixir_of_luck": ("loot", 50, 300000),
    "speed_potion": ("brzina", 30, 20000),
}


def _conn(db=None):
    return pymysql.connect(**{**DB_CONFIG, "db": db}, autocommit=True)


def _sql(upit, args=(), db=TEST_DB):
    c = _conn(db)
    try:
        with c.cursor() as cur:
            cur.execute(upit, args)
            return cur.fetchall()
    finally:
        c.close()


def _pokreni(fajl) -> subprocess.CompletedProcess:
    env = {**os.environ, "MYSQL_PWD": DB_CONFIG["password"]}
    with open(fajl, "rb") as f:
        return subprocess.run(["mariadb", "--default-character-set=utf8mb4", "-h", DB_CONFIG["host"],
                               "-P", str(DB_CONFIG["port"]), "-u", DB_CONFIG["user"], TEST_DB],
                              stdin=f, capture_output=True, env=env)


def _snimak():
    return (_sql("SHOW CREATE TABLE items"), _sql("SELECT * FROM items ORDER BY id"), _sql("SHOW TABLES"))


def _md5(s) -> str:
    return hashlib.md5(repr(s).encode()).hexdigest()


def _napravi_bazu():
    _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)
    _sql(f"CREATE DATABASE {TEST_DB}", db=None)
    izvor = DB_CONFIG["db"]
    for t in ("items", "quests"):
        _sql(f"CREATE TABLE {t} LIKE {izvor}.{t}")
        _sql(f"INSERT INTO {t} SELECT * FROM {izvor}.{t}")
    _sql(f"CREATE TABLE players LIKE {izvor}.players")
    if not _sql("SELECT 1 FROM items WHERE id = 'cloth_trousers'"):
        r = _pokreni(MIGRACIJA_009)
        assert r.returncode == 0, r.stderr.decode()
        _sql("DROP TABLE items_pre_009, quests_pre_009")


def _proveri_posle_migracije(pre_items):
    for id, (tip, vrednost, trajanje) in BUFFOVI.items():
        r = _sql("SELECT tip, hp_efekat, mana_efekat, cooldown_ms, quest_item, buff_tip, buff_vrednost, buff_trajanje_ms "
                 "FROM items WHERE id = %s", (id,))
        assert r == (("consumable", 0, 0, 5000, 0, tip, vrednost, trajanje),), (id, r)
    # ostali predmeti: iste vrednosti, buff kolone prazne
    kolone = len(pre_items[0])
    posle = {r[0]: r for r in _sql("SELECT * FROM items")}
    assert len(posle) == len(pre_items)
    for r in pre_items:
        if r[0] not in BUFFOVI:
            assert posle[r[0]][:kolone] == r and posle[r[0]][kolone:] == (None, 0, 0), r[0]
    # nove kolone u collation-u tabele (kao ostale tekstualne kolone items)
    tabela = _sql("SELECT TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'items'",
                  (TEST_DB,))[0][0]
    kol = _sql("SELECT COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'items' "
               "AND COLUMN_NAME = 'buff_tip'", (TEST_DB,))[0][0]
    assert kol == tabela, (kol, tabela)


def test_migracija_i_rollback():
    _napravi_bazu()
    pocetak = _snimak()
    try:
        # 1) migracija
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _proveri_posle_migracije(pocetak[1])
        posle_1 = _snimak()

        # 2) ponovljena migracija se odbija i ništa ne menja
        r = _pokreni(MIGRACIJA)
        assert r.returncode != 0 and b"010 vec primenjena" in r.stderr, r.stderr.decode()
        assert _snimak() == posle_1

        # 3) rollback: tačno početna struktura i redovi items (isti md5), bez rezervne tabele
        r = _pokreni(ROLLBACK)
        assert r.returncode == 0, r.stderr.decode()
        assert _md5(_snimak()) == _md5(pocetak)

        # 4) ponovljen rollback se odbija i ništa ne menja
        r = _pokreni(ROLLBACK)
        assert r.returncode != 0 and b"010 nije primenjena" in r.stderr, r.stderr.decode()
        assert _md5(_snimak()) == _md5(pocetak)

        # 5) migracija ponovo prolazi
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _proveri_posle_migracije(pocetak[1])
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


def test_rollback_ne_vraca_izmenjeno_posle_migracije():
    _napravi_bazu()
    try:
        assert _pokreni(MIGRACIJA).returncode == 0
        _sql("UPDATE items SET cooldown_ms = 8000 WHERE id = 'speed_potion'")
        r = _pokreni(ROLLBACK)
        assert r.returncode == 0, r.stderr.decode()
        assert b"promenjen posle 010" in r.stdout
        assert _sql("SELECT cooldown_ms FROM items WHERE id = 'speed_potion'") == ((8000,),)
        assert _sql("SELECT cooldown_ms, quest_item FROM items WHERE id = 'elixir_of_luck'") == ((1000, 1),)
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


def test_neocekivano_stanje_prekida_bez_izmena():
    for upit in ("UPDATE items SET cooldown_ms = 2000 WHERE id = 'elixir_of_strength'",
                 "UPDATE items SET quest_item = 0 WHERE id = 'elixir_of_luck'",
                 "UPDATE items SET hp_efekat = 10 WHERE id = 'speed_potion'",
                 "DELETE FROM items WHERE id = 'elixir_of_wisdom'"):
        _napravi_bazu()
        try:
            _sql(upit)
            pre = _snimak()
            r = _pokreni(MIGRACIJA)
            assert r.returncode != 0 and b"nisu u ocekivanom stanju" in r.stderr, (upit, r.stderr.decode())
            assert _snimak() == pre, upit
        finally:
            _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


def test_ostatak_neuspelog_pokusaja_ne_blokira():
    # rezervna tabela bez kolona u items (pokušaj pao pre ALTER-a): migracija je briše i prolazi
    _napravi_bazu()
    try:
        _sql("CREATE TABLE items_pre_010 (id VARCHAR(50))")
        pre_items = _sql("SELECT * FROM items")
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _proveri_posle_migracije(pre_items)
        assert _sql("SELECT COUNT(*) FROM items_pre_010") == ((5,),)
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


if __name__ == "__main__":
    test_migracija_i_rollback()
    test_rollback_ne_vraca_izmenjeno_posle_migracije()
    test_neocekivano_stanje_prekida_bez_izmena()
    test_ostatak_neuspelog_pokusaja_ne_blokira()
    print("ok")
