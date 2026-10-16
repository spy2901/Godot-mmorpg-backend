"""Integracioni test za opremu u POST /players/{ime}/save protiv lokalne baze (traži migraciju 007_oprema.sql).
Koristi privremenog igraca TEST_IME i brise ga na kraju.
Pokretanje: python3.12 test_oprema.py (ili pytest test_oprema.py).
DB_* se po potrebi zadaju kroz env (npr. DB_PORT=8889 DB_USER=root DB_PASSWORD=root)."""
import json
import os

os.environ["SERVER_KEY"] = "test-kljuc"  # pre importa; load_dotenv ne pregazi postojeci env

import pymysql
from fastapi.testclient import TestClient

from db import DB_CONFIG
from main import app

TEST_IME = "__test_oprema"
KLJUC = {"X-Server-Key": "test-kljuc"}
client = TestClient(app)


def _sql(upit, args=()):
    c = pymysql.connect(**DB_CONFIG, autocommit=True)
    try:
        with c.cursor() as cur:
            cur.execute(upit, args)
            return cur.fetchall()
    finally:
        c.close()


def _postavi(inventar, oprema=None, hp=100, max_hp=100):
    _sql("DELETE FROM players WHERE ime = %s", (TEST_IME,))
    _sql("INSERT INTO players (ime, hp, max_hp, inventory, equipment) VALUES (%s, %s, %s, %s, %s)",
         (TEST_IME, hp, max_hp, json.dumps(inventar), json.dumps(oprema or {})))


def _u_bazi():
    hp, eq = _sql("SELECT hp, equipment FROM players WHERE ime = %s", (TEST_IME,))[0]
    return int(hp), json.loads(eq or "{}")


def _sacuvaj(inventar, oprema, hp=100):
    telo = {"hp": hp, "mana": 100, "pos_x": 0.0, "pos_y": 1.16, "pos_z": 0.0, "inventory": inventar, "equipment": oprema}
    return client.post(f"/players/{TEST_IME}/save", json=telo, headers=KLJUC).json()


def _inv(*ids):
    return [{"slot": i, "id": item_id, "kolicina": 1} for i, item_id in enumerate(ids)]


def test_oprema_mora_u_svoj_slot():
    # ispravan slot prolazi, pa kaciga u slotu za cizme ne: ostaje stanje iz baze
    _postavi(_inv("iron_helmet", "iron_sword"))
    assert _sacuvaj([], {"head": "iron_helmet", "weapon": "iron_sword"}) == {"status": "ok"}
    assert _u_bazi()[1] == {"head": "iron_helmet", "weapon": "iron_sword"}
    assert _sacuvaj(_inv("iron_sword"), {"boots": "iron_helmet"}) == {"status": "ok"}
    assert _u_bazi()[1] == {"head": "iron_helmet", "weapon": "iron_sword"}


def test_predmet_bez_slota_se_ne_oprema():
    # iron_gloves ima slot NULL: ne ide ni u jedan slot
    _postavi(_inv("iron_gloves"))
    for slot in ("head", "chest", "legs", "boots", "shield", "weapon"):
        _sacuvaj([], {slot: "iron_gloves"})
        assert _u_bazi()[1] == {}, slot


def test_hp_iznad_osnovnog_prezivi_save():
    # osnovni max 100 + dragon_scale_armor 50: HP do 150 se čuva, preko toga se seče na 150
    _postavi(_inv("dragon_scale_armor"))
    _sacuvaj([], {"chest": "dragon_scale_armor"}, hp=140)
    assert _u_bazi() == (140, {"chest": "dragon_scale_armor"})
    _sacuvaj([], {"chest": "dragon_scale_armor"}, hp=999)
    assert _u_bazi()[0] == 150
    # skinut oklop: maksimum je opet osnovni
    _sacuvaj(_inv("dragon_scale_armor"), {}, hp=150)
    assert _u_bazi() == (100, {})


def teardown_module(_=None):
    _sql("DELETE FROM players WHERE ime = %s", (TEST_IME,))


if __name__ == "__main__":
    try:
        for ime, f in list(globals().items()):
            if ime.startswith("test_"):
                f()
                print("ok", ime)
    finally:
        teardown_module()
