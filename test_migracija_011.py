"""Test migracije 011 (efekti) i njenog rollback-a na posebnoj bazi mmorpg_test_011.
Struktura i podaci items i quests se kopiraju iz baze DB_NAME (podaci te baze se ne diraju), players samo struktura.
Ako DB_NAME još nije posle 010 (npr. tests/run_with_temp_db.sh staje na 007), kopija se prvo dovede do 010.
Za stvarnu šemu i redove items (utf8mb3) DB_NAME treba da bude kopija sa Pi-ja (mariadb-dump --no-data + items/quests).
Traži mariadb CLI (DELIMITER blokovi) i pravo CREATE DATABASE.
Pokretanje: DB_HOST=127.0.0.1 DB_PORT=33077 DB_USER=root DB_PASSWORD=... python3.12 test_migracija_011.py"""
import os

import test_migracija_010 as m010
from db import DB_CONFIG

TEST_DB = "mmorpg_test_011"
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
MIGRACIJA = os.path.join(DIR, "011_efekti.sql")
ROLLBACK = os.path.join(DIR, "011_efekti_rollback.sql")

EFEKTI = {  # id: (quest_item, cooldown_ms, hp_efekat, buff_tip, buff_vrednost, buff_trajanje_ms)
    "invisibility_potion": (0, 60000, 0, "nevidljivost", 1, 20000),
    "resurrection_potion": (0, 5000, 0, "vaskrsenje", 50, 600000),
    "antidote": (0, 5000, 20, "protivotrov", 1, 30000),
}
KOLONE = "quest_item, cooldown_ms, hp_efekat, buff_tip, buff_vrednost, buff_trajanje_ms"


def _sql(upit, args=(), db=TEST_DB):
    return m010._sql(upit, args, db)


def _pokreni(fajl):
    stara = m010.TEST_DB
    m010.TEST_DB = TEST_DB
    try:
        return m010._pokreni(fajl)
    finally:
        m010.TEST_DB = stara


def _snimak():
    return (_sql("SHOW CREATE TABLE items"), _sql("SELECT * FROM items ORDER BY id"), _sql("SHOW TABLES"))


def _napravi_bazu():
    _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)
    _sql(f"CREATE DATABASE {TEST_DB}", db=None)
    izvor = DB_CONFIG["db"]
    for t in ("items", "quests"):
        _sql(f"CREATE TABLE {t} LIKE {izvor}.{t}")
        _sql(f"INSERT INTO {t} SELECT * FROM {izvor}.{t}")
    _sql(f"CREATE TABLE players LIKE {izvor}.players")
    if not _sql("SELECT 1 FROM items WHERE id = 'cloth_trousers'"):
        assert _pokreni(m010.MIGRACIJA_009).returncode == 0
        _sql("DROP TABLE items_pre_009, quests_pre_009")
    if not _sql("SHOW COLUMNS FROM items LIKE 'buff_tip'"):
        r = _pokreni(m010.MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _sql("DROP TABLE items_pre_010")


def _proveri_posle_migracije(pre_items):
    for id, ocekivano in EFEKTI.items():
        r = _sql(f"SELECT {KOLONE} FROM items WHERE id = %s", (id,))
        assert r == (ocekivano,), (id, r)
    posle = {r[0]: r for r in _sql("SELECT * FROM items")}
    assert len(posle) == len(pre_items)
    for r in pre_items:  # ostali predmeti netaknuti
        if r[0] not in EFEKTI:
            assert posle[r[0]] == r, r[0]


def test_migracija_i_rollback():
    _napravi_bazu()
    pocetak = _snimak()
    try:
        # 1) migracija
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _proveri_posle_migracije(pocetak[1])
        assert b"invisibility_potion\tcd 1000 quest_item 1 bez buff-a\tcd 60000 quest_item 0 nevidljivost 1 20 s" in r.stdout
        posle_1 = _snimak()

        # 2) ponovljena migracija se odbija i ništa ne menja
        r = _pokreni(MIGRACIJA)
        assert r.returncode != 0 and b"011 vec primenjena" in r.stderr, r.stderr.decode()
        assert _snimak() == posle_1

        # 3) rollback: tačno početna struktura i redovi items (isti md5), bez rezervne tabele
        r = _pokreni(ROLLBACK)
        assert r.returncode == 0, r.stderr.decode()
        assert m010._md5(_snimak()) == m010._md5(pocetak)

        # 4) ponovljen rollback se odbija i ništa ne menja
        r = _pokreni(ROLLBACK)
        assert r.returncode != 0 and b"011 nije primenjena" in r.stderr, r.stderr.decode()
        assert m010._md5(_snimak()) == m010._md5(pocetak)

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
        _sql("UPDATE items SET cooldown_ms = 30000 WHERE id = 'invisibility_potion'")
        r = _pokreni(ROLLBACK)
        assert r.returncode == 0, r.stderr.decode()
        assert b"promenjen posle 011" in r.stdout
        assert _sql("SELECT cooldown_ms, buff_tip FROM items WHERE id = 'invisibility_potion'") == ((30000, "nevidljivost"),)
        assert _sql(f"SELECT {KOLONE} FROM items WHERE id = 'resurrection_potion'") == ((1, 1000, 0, None, 0, 0),)
        assert _sql(f"SELECT {KOLONE} FROM items WHERE id = 'antidote'") == ((0, 5000, 20, None, 0, 0),)
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


def test_neocekivano_stanje_prekida_bez_izmena():
    for upit in ("UPDATE items SET cooldown_ms = 2000 WHERE id = 'invisibility_potion'",
                 "UPDATE items SET quest_item = 0 WHERE id = 'resurrection_potion'",
                 "UPDATE items SET hp_efekat = 30 WHERE id = 'antidote'",
                 "UPDATE items SET buff_tip = 'napad', buff_vrednost = 5, buff_trajanje_ms = 1000 WHERE id = 'antidote'",
                 "DELETE FROM items WHERE id = 'resurrection_potion'"):
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
    # rezervna tabela ostala od pokušaja koji je pao pre izmene redova: migracija je briše i prolazi
    _napravi_bazu()
    try:
        _sql("CREATE TABLE items_pre_011 (id VARCHAR(50))")
        pre_items = _sql("SELECT * FROM items")
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _proveri_posle_migracije(pre_items)
        assert _sql("SELECT COUNT(*) FROM items_pre_011") == ((3,),)
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


if __name__ == "__main__":
    test_migracija_i_rollback()
    test_rollback_ne_vraca_izmenjeno_posle_migracije()
    test_neocekivano_stanje_prekida_bez_izmena()
    test_ostatak_neuspelog_pokusaja_ne_blokira()
    print("ok")
