"""Test migracije 009 (sadržaj zone 2) i njenog rollback-a na posebnoj bazi mmorpg_test_009.
Struktura i podaci tabela items i quests se kopiraju iz baze DB_NAME (podaci te baze se ne diraju), players samo struktura.
Traži mariadb CLI (DELIMITER blokovi) i pravo CREATE DATABASE.
Pokretanje: DB_HOST=127.0.0.1 DB_PORT=33077 DB_USER=root DB_PASSWORD=... python3.12 test_migracija_009.py"""
import os
import subprocess

import pymysql

from db import DB_CONFIG

TEST_DB = "mmorpg_test_009"
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
MIGRACIJA = os.path.join(DIR, "009_sadrzaj.sql")
ROLLBACK = os.path.join(DIR, "009_sadrzaj_rollback.sql")

NOVI_PREDMETI = {  # id: (slot, armor, hp_bonus, vrednost)
    "cloth_trousers": ("legs", 2, 0, 6), "leather_pants": ("legs", 6, 0, 18), "steel_greaves": ("legs", 18, 10, 90),
    "dragonscale_leggings": ("legs", 26, 30, 450), "steel_sabatons": ("boots", 10, 5, 70),
    "shadow_boots": ("boots", 14, 15, 280), "wooden_shield": ("shield", 6, 0, 10), "tower_shield": ("shield", 28, 20, 120),
    "dragon_shield": ("shield", 36, 40, 520),
}
NOVI_QUESTOVI = {  # id: (tip, cilj, kolicina, xp, gold, item, sledeci)
    "vucja_krzna": ("fetch", "wolf_pelt", 6, 1200, 150, None, "svila_za_krojaca"),
    "svila_za_krojaca": ("fetch", "spider_web", 8, 1500, 200, "steel_sabatons", "senke_u_sumi"),
    "senke_u_sumi": ("kill", "wraith", 8, 2500, 300, "tower_shield", "kraj_utvara"),
    "kraj_utvara": ("kill", "wraith", 3, 3000, 500, "dragon_shield", None),
    "lek_od_otrova": ("fetch", "poison_gland", 4, 1400, 150, "antidote", "prah_za_napitke"),
    "prah_za_napitke": ("fetch", "magic_dust", 5, 2200, 250, None, None),
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
    return (_sql("SELECT * FROM items ORDER BY id"), _sql("SELECT * FROM quests ORDER BY id"),
            _sql("SELECT ime, aktivni_quest_id, quest_progres FROM players ORDER BY ime"),
            _sql("SHOW TABLES"))


def _napravi_bazu():
    _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)
    _sql(f"CREATE DATABASE {TEST_DB}", db=None)
    izvor = DB_CONFIG["db"]
    for t in ("items", "quests"):
        _sql(f"CREATE TABLE {t} LIKE {izvor}.{t}")
        _sql(f"INSERT INTO {t} SELECT * FROM {izvor}.{t}")
    _sql(f"CREATE TABLE players LIKE {izvor}.players")
    for ime, q, n in (("bez_questa", None, 0), ("stari_quest", "goblin_killer", 2)):
        _sql("INSERT INTO players (ime, inventory, equipment, aktivni_quest_id, quest_progres) VALUES (%s, '[]', '{}', %s, %s)",
             (ime, q, n))


def _proveri_posle_migracije(pre_items):
    for id, (slot, armor, hp_bonus, vrednost) in NOVI_PREDMETI.items():
        r = _sql("SELECT tip, slot, armor, hp_bonus, vrednost, quest_item, damage, stackable, max_stack FROM items WHERE id = %s", (id,))
        assert r == (("armor", slot, armor, hp_bonus, vrednost, 0, 0, 0, 1),), (id, r)
    for id, (tip, cilj, kol, xp, gold, item, sledeci) in NOVI_QUESTOVI.items():
        r = _sql("SELECT tip, cilj, kolicina, nagrada_xp, nagrada_gold, nagrada_item, sledeci_quest FROM quests WHERE id = %s", (id,))
        assert r == ((tip, cilj, kol, xp, gold, item, sledeci),), (id, r)
    assert _sql("SELECT id, hp_efekat, mana_efekat, cooldown_ms FROM items WHERE id IN ('stamina_potion', 'antidote') ORDER BY id") \
        == (("antidote", 20, 0, 5000), ("stamina_potion", 0, 40, 5000))
    assert _sql("SELECT id, sledeci_quest FROM quests WHERE id IN ('kosti_za_supu', 'q2') ORDER BY id") \
        == (("kosti_za_supu", "lek_od_otrova"), ("q2", "kraj_utvara"))
    # ostali predmeti netaknuti
    posle = {r[0]: r for r in _sql("SELECT * FROM items")}
    for r in pre_items:
        if r[0] not in ("stamina_potion", "antidote"):
            assert posle[r[0]] == r, r[0]
    assert len(posle) == len(pre_items) + 9
    # svaki predmet koji questovi traže ili daju postoji
    for (id,) in _sql("SELECT cilj FROM quests WHERE tip = 'fetch' UNION SELECT nagrada_item FROM quests WHERE nagrada_item IS NOT NULL"):
        assert id in posle, id


def test_migracija_i_rollback():
    _napravi_bazu()
    pocetak = _snimak()
    try:
        # 1) migracija
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _proveri_posle_migracije(pocetak[0])
        posle_1 = _snimak()

        # 2) ponovljena migracija se odbija i ništa ne menja
        r = _pokreni(MIGRACIJA)
        assert r.returncode != 0 and b"009 vec primenjena" in r.stderr, r.stderr.decode()
        assert _snimak() == posle_1

        # posle migracije: igrač prihvati nov quest, drugi ima stari; neko ručno promeni q2 (ostaje posle rollback-a)
        _sql("INSERT INTO players (ime, inventory, equipment, aktivni_quest_id, quest_progres) "
             "VALUES ('novi_quest', '[]', '{}', 'senke_u_sumi', 3)")

        # 3) rollback: tačno početno stanje items/quests; igrač sa obrisanim questom ostaje bez aktivnog
        r = _pokreni(ROLLBACK)
        assert r.returncode == 0, r.stderr.decode()
        s = _snimak()
        assert s[0] == pocetak[0] and s[1] == pocetak[1] and s[3] == pocetak[3]
        assert s[2] == (("bez_questa", None, 0), ("novi_quest", None, 0), ("stari_quest", "goblin_killer", 2))

        # 4) ponovljen rollback se odbija i ništa ne menja
        pre = _snimak()
        r = _pokreni(ROLLBACK)
        assert r.returncode != 0 and b"009 nije primenjena" in r.stderr, r.stderr.decode()
        assert _snimak() == pre

        # 5) migracija ponovo prolazi
        r = _pokreni(MIGRACIJA)
        assert r.returncode == 0, r.stderr.decode()
        _proveri_posle_migracije(pocetak[0])
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


def test_rollback_ne_vraca_izmenjeno_posle_migracije():
    _napravi_bazu()
    try:
        assert _pokreni(MIGRACIJA).returncode == 0
        _sql("UPDATE items SET mana_efekat = 45 WHERE id = 'stamina_potion'")
        _sql("UPDATE quests SET sledeci_quest = 'goblin_killer' WHERE id = 'q2'")
        r = _pokreni(ROLLBACK)
        assert r.returncode == 0, r.stderr.decode()
        assert _sql("SELECT mana_efekat FROM items WHERE id = 'stamina_potion'") == ((45,),)
        assert _sql("SELECT sledeci_quest FROM quests WHERE id = 'q2'") == (("goblin_killer",),)
        assert _sql("SELECT hp_efekat, cooldown_ms FROM items WHERE id = 'antidote'") == ((0, 1000),)
        assert _sql("SELECT sledeci_quest FROM quests WHERE id = 'kosti_za_supu'") == ((None,),)
    finally:
        _sql(f"DROP DATABASE IF EXISTS {TEST_DB}", db=None)


if __name__ == "__main__":
    test_migracija_i_rollback()
    test_rollback_ne_vraca_izmenjeno_posle_migracije()
    print("ok")
