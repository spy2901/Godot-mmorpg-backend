"""Test migracije 008 (napredak lika) i njenog rollback-a na posebnoj bazi mmorpg_test_008.
Struktura tabela players i items se kopira iz baze DB_NAME (LIKE), podaci te baze se ne diraju.
Traži mariadb CLI (DELIMITER blokovi) i pravo CREATE DATABASE.
Pokretanje: DB_HOST=127.0.0.1 DB_PORT=33077 DB_USER=root DB_PASSWORD=... python3.12 test_migracija_008.py"""
import json
import os
import subprocess

import pymysql

from db import DB_CONFIG
from napredak import statistike_za_nivo

TEST_DB = "mmorpg_test_008"
MIGRACIJA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations", "008_napredak.sql")
ROLLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations", "008_napredak_rollback.sql")
KOLONE = "level, xp, max_xp, hp, max_hp, mana, max_mana, napad_damage"

# ime: (level, xp, max_xp, hp, max_hp, mana, max_mana, napad_damage, equipment) = stanje pre 008 (stara kriva)
LIKOVI = {
    "nov": (1, 40, 100, 100, 100, 100, 100, 250, {}),
    "nivo3": (3, 200, 225, 132, 132, 121, 121, 302, {}),
    "nivo3_ranjen": (3, 10, 225, 50, 132, 40, 121, 302, {}),
    "nivo3_stit": (3, 0, 225, 132, 132, 121, 121, 302, {"shield": "steel_shield"}),  # max HP 130 + 10
    "xp_iznad": (12, 5000, 8649, 400, 405, 285, 285, 713, {}),  # novi max_xp nivoa 12 je 4500
    "nivo25": (25, 50, 168151, 3000, 3292, 985, 985, 2462, {}),
    "nivo20": (20, 77, 221683, 1000, 1424, 500, 516, 1529, {"chest": "dragon_scale_armor"}),
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


def _stanje(ime):
    return _sql(f"SELECT {KOLONE} FROM players WHERE ime = %s", (ime,))[0]


def _default_napada():
    return int(_sql("SELECT COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s "
                    "AND TABLE_NAME = 'players' AND COLUMN_NAME = 'napad_damage'", (TEST_DB,))[0][0])


def _ocekivano_posle(ime):
    level, xp, _, hp, _, mana, _, _, eq = LIKOVI[ime]
    s = statistike_za_nivo(level)
    bonus = {"steel_shield": 10, "dragon_scale_armor": 50}
    hp_max = s["max_hp"] + sum(bonus.get(i, 0) for i in eq.values())
    novi_xp = 0 if s["max_xp"] == 0 else min(xp, s["max_xp"] - 1)
    return (s["level"], novi_xp, s["max_xp"], min(hp, hp_max), s["max_hp"], min(mana, s["max_mana"]), s["max_mana"],
            s["napad_damage"])


def _napravi_bazu():
    _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)
    _sql(f"CREATE DATABASE {TEST_DB}", db=None)
    izvor = DB_CONFIG["db"]
    _sql(f"CREATE TABLE items LIKE {izvor}.items")
    _sql(f"INSERT INTO items SELECT * FROM {izvor}.items WHERE id IN ('steel_shield', 'dragon_scale_armor')")
    _sql(f"CREATE TABLE players LIKE {izvor}.players")
    for ime, (level, xp, max_xp, hp, max_hp, mana, max_mana, napad, eq) in LIKOVI.items():
        _sql(f"INSERT INTO players (ime, {KOLONE}, inventory, equipment) VALUES (%s, {', '.join(['%s'] * 8)}, '[]', %s)",
             (ime, level, xp, max_xp, hp, max_hp, mana, max_mana, napad, json.dumps(eq)))


def test_migracija_i_rollback():
    _napravi_bazu()
    assert _default_napada() == 250
    try:
        # 1) migracija: statistike iz nivoa, nivo > 20 -> 20, XP iznad novog max_xp -> max_xp - 1, hp/mana do maksimuma
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        for ime in LIKOVI:
            assert _stanje(ime) == _ocekivano_posle(ime), ime
        assert _stanje("nivo25")[:3] == (20, 0, 0)
        assert _stanje("xp_iznad")[:3] == (12, 4499, 4500)
        assert _stanje("nivo3_stit")[3] == 132  # 130 + 10 (štit): HP 132 ostaje
        assert _default_napada() == 10
        posle_1 = {ime: _stanje(ime) for ime in LIKOVI}

        # 2) ponovljena migracija se odbija i ništa ne menja
        r = _pokreni(MIGRACIJA)
        assert r.returncode != 0 and b"008 vec primenjena" in r.stderr, r.stderr.decode()
        assert {ime: _stanje(ime) for ime in LIKOVI} == posle_1

        # posle migracije: "nivo3" stekne nivo 4 (novi kod), "nov" dobije XP; novi lik "posle" nastane posle 008
        s4 = statistike_za_nivo(4)
        _sql("UPDATE players SET level = 4, xp = 20, max_xp = %s, max_hp = %s, max_mana = %s, napad_damage = %s, "
             "hp = %s, mana = %s WHERE ime = 'nivo3'",
             (s4["max_xp"], s4["max_hp"], s4["max_mana"], s4["napad_damage"], s4["max_hp"], s4["max_mana"]))
        _sql("UPDATE players SET xp = 90, hp = 77 WHERE ime = 'nov'")
        _sql("INSERT INTO players (ime, inventory, equipment) VALUES ('posle', '[]', '{}')")
        posle_novi = _sql(f"SELECT {KOLONE} FROM players WHERE ime = 'posle'")[0]
        assert posle_novi == (1, 0, 100, 100, 100, 100, 100, 10)

        # 3) rollback: lik bez napretka dobija stare vrednosti; napredak (nivo, XP) ostaje
        r = _pokreni(ROLLBACK)
        assert r.returncode == 0, r.stderr.decode()
        for ime in ("nivo3_ranjen", "nivo3_stit", "xp_iznad", "nivo25", "nivo20"):
            assert _stanje(ime) == LIKOVI[ime][:8], ime
        # nivo3: nivo 4, XP i max_xp ostaju (napredak); max HP, mana i napad nazad na stare
        assert _stanje("nivo3") == (4, 20, s4["max_xp"], s4["max_hp"], 132, s4["max_mana"], 121, 302)
        # nov: XP 90 i HP 77 ostaju (promenjeni posle migracije), statistike nazad
        assert _stanje("nov") == (1, 90, 100, 77, 100, 100, 100, 250)
        assert _sql(f"SELECT {KOLONE} FROM players WHERE ime = 'posle'")[0] == posle_novi  # nije bio u migraciji
        assert _default_napada() == 250
        assert not _sql("SHOW TABLES LIKE 'players_pre_008'")

        # 4) ponovljen rollback se odbija i ništa ne menja
        pre = _sql(f"SELECT ime, {KOLONE} FROM players ORDER BY ime")
        r = _pokreni(ROLLBACK)
        assert r.returncode != 0 and b"008 nije primenjena" in r.stderr, r.stderr.decode()
        assert _sql(f"SELECT ime, {KOLONE} FROM players ORDER BY ime") == pre

        # 5) migracija ponovo prolazi
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        for ime in ("nivo3_ranjen", "nivo3_stit", "xp_iznad", "nivo25", "nivo20"):
            assert _stanje(ime) == _ocekivano_posle(ime), ime
        assert _stanje("nivo3")[:3] == (4, 20, s4["max_xp"]) and _stanje("nivo3")[4] == s4["max_hp"]
        assert _default_napada() == 10
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


if __name__ == "__main__":
    test_migracija_i_rollback()
    print("ok test_migracija_i_rollback")
