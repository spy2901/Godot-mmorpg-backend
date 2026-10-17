"""Integracioni test: obe rute koje daju XP (xp/change i quest/turnin) idu kroz napredak.primeni_xp i upisuju
statistike iz nivoa. Koristi privremenog igraca TEST_IME i quest TEST_QUEST i brise ih na kraju.
Pokretanje: python3.12 test_napredak.py (ili pytest test_napredak.py); DB_* kroz env kao za test_oprema.py."""
import json
import os

os.environ["SERVER_KEY"] = "test-kljuc"  # pre importa; load_dotenv ne pregazi postojeci env

import pymysql
from fastapi.testclient import TestClient

from db import DB_CONFIG
from main import app
from napredak import statistike_za_nivo

TEST_IME = "__test_napredak"
TEST_QUEST = "__test_napredak_quest"
KLJUC = {"X-Server-Key": "test-kljuc"}
KOLONE = "level, xp, max_xp, hp, max_hp, mana, max_mana, napad_damage"
client = TestClient(app)


def _sql(upit, args=()):
    c = pymysql.connect(**DB_CONFIG, autocommit=True)
    try:
        with c.cursor() as cur:
            cur.execute(upit, args)
            return cur.fetchall()
    finally:
        c.close()


def _postavi(level=1, xp=0, hp=30, mana=20, oprema=None):
    s = statistike_za_nivo(level)
    _sql("DELETE FROM players WHERE ime = %s", (TEST_IME,))
    _sql(f"INSERT INTO players (ime, {KOLONE}, inventory, equipment) VALUES (%s, {', '.join(['%s'] * 8)}, '[]', %s)",
         (TEST_IME, s["level"], xp, s["max_xp"], hp, s["max_hp"], mana, s["max_mana"], s["napad_damage"],
          json.dumps(oprema or {})))


def _u_bazi():
    return _sql(f"SELECT {KOLONE} FROM players WHERE ime = %s", (TEST_IME,))[0]


def _xp(delta):
    return client.post(f"/players/{TEST_IME}/xp/change", json={"delta": delta, "razlog": "test"}, headers=KLJUC).json()


def test_xp_change_level_up_puni_hp_sa_bonusom_opreme():
    _postavi(oprema={"shield": "steel_shield"})  # hp_bonus 10
    r = _xp(830)  # 100 + 250 + 450 -> nivo 4, 30 ostaje
    assert {k: r[k] for k in ("level", "xp", "max_xp", "max_hp", "max_mana", "napad_damage", "level_up")} == \
        {"level": 4, "xp": 30, "max_xp": 700, "max_hp": 145, "max_mana": 130, "napad_damage": 16, "level_up": True}
    assert _u_bazi() == (4, 30, 700, 155, 145, 130, 130, 16)  # hp = osnovni 145 + štit 10


def test_xp_change_bez_level_upa_statistike_iz_nivoa_hp_isti():
    # stare (uvecane) vrednosti nivoa 3 se ispravljaju iz nivoa i bez level-upa; hp i mana se ne diraju
    _postavi(level=3, xp=10, hp=40, mana=5)
    _sql("UPDATE players SET max_xp = 225, max_hp = 132, max_mana = 121, napad_damage = 302 WHERE ime = %s", (TEST_IME,))
    r = _xp(100)
    assert r["level_up"] is False and _u_bazi() == (3, 110, 450, 40, 130, 5, 120, 14)


def test_xp_change_na_nivou_20():
    _postavi(level=19, xp=10_000)
    assert _xp(5000)["level"] == 20
    assert _u_bazi() == (20, 0, 0, 385, 385, 290, 290, 48)
    r = _xp(500)
    assert r["xp"] == 0 and r["max_xp"] == 0 and r["level_up"] is False
    assert _u_bazi() == (20, 0, 0, 385, 385, 290, 290, 48)


def test_quest_turnin_ide_kroz_istu_krivu():
    _postavi(xp=50)
    _sql("DELETE FROM quests WHERE id = %s", (TEST_QUEST,))
    _sql("INSERT INTO quests (id, naziv, opis, tip, cilj, kolicina, nagrada_gold, nagrada_xp) "
         "VALUES (%s, 'Test', 'test', 'kill', 'goblin', 1, 0, 300)", (TEST_QUEST,))
    _sql("UPDATE players SET aktivni_quest_id = %s, quest_progres = 1 WHERE ime = %s", (TEST_QUEST, TEST_IME))
    r = client.post(f"/players/{TEST_IME}/quest/turnin", json={"quest_id": TEST_QUEST}, headers=KLJUC).json()
    assert r.get("status") == "ok", r
    # 50 + 300: 100 za nivo 2, 250 ostaje = tacno nivo 3
    assert r["stats"] == {**statistike_za_nivo(3), "xp": 0, "level_up": True}
    assert _u_bazi() == (3, 0, 450, 130, 130, 120, 120, 14)


def teardown_module(_=None):
    _sql("DELETE FROM zavrseni_questovi WHERE player_ime = %s", (TEST_IME,))
    _sql("DELETE FROM players WHERE ime = %s", (TEST_IME,))
    _sql("DELETE FROM quests WHERE id = %s", (TEST_QUEST,))


if __name__ == "__main__":
    try:
        for ime, f in list(globals().items()):
            if ime.startswith("test_"):
                f()
                print("ok", ime)
    finally:
        teardown_module()
