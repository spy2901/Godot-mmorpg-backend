"""Integracioni test za action bar (GET /players/{ime} i POST /players/{ime}/action_bar) protiv lokalne baze.
Traži migraciju 005_action_bar.sql. Koristi privremenog igraca TEST_IME i brise ga na kraju.
Pokretanje: python3.12 test_action_bar.py (ili pytest test_action_bar.py).
DB_* se po potrebi zadaju kroz env (npr. DB_PORT=8889 DB_USER=root DB_PASSWORD=root)."""
import json
import os

os.environ["SERVER_KEY"] = "test-kljuc"  # pre importa; load_dotenv ne pregazi postojeci env

import pymysql
from fastapi.testclient import TestClient

from db import DB_CONFIG
from main import app

TEST_IME = "__test_action_bar"
KLJUC = {"X-Server-Key": "test-kljuc"}
client = TestClient(app)
RASPORED = ["small_health_potion", "apple", None, None, None, None, "mana_potion", None, None, None]


def _sql(upit, args=()):
    c = pymysql.connect(**DB_CONFIG, autocommit=True)
    try:
        with c.cursor() as cur:
            cur.execute(upit, args)
            return cur.fetchall()
    finally:
        c.close()


def _postavi():
    _sql("DELETE FROM players WHERE ime = %s", (TEST_IME,))
    _sql("INSERT INTO players (ime, inventory, equipment) VALUES (%s, '[]', '{}')", (TEST_IME,))


def _u_bazi():
    v = _sql("SELECT action_bar FROM players WHERE ime = %s", (TEST_IME,))[0][0]
    return None if v is None else json.loads(v)


def _sacuvaj(slotovi, ime=TEST_IME, headers=KLJUC):
    return client.post(f"/players/{ime}/action_bar", json={"slotovi": slotovi}, headers=headers)


def test_nov_lik_nema_raspored():
    _postavi()
    assert client.get(f"/players/{TEST_IME}", headers=KLJUC).json()["action_bar"] is None


def test_raspored_se_cuva_i_vraca():
    _postavi()
    assert _sacuvaj(RASPORED).json() == {"status": "ok", "action_bar": RASPORED}
    assert _u_bazi() == RASPORED
    assert client.get(f"/players/{TEST_IME}", headers=KLJUC).json()["action_bar"] == RASPORED
    prazan = [None] * 10  # sacuvan prazan raspored nije isto sto i "nema rasporeda"
    assert _sacuvaj(prazan).json()["status"] == "ok" and _u_bazi() == prazan


def test_pogresan_broj_slotova_odbijen():
    _postavi()
    _sacuvaj(RASPORED)
    assert "error" in _sacuvaj(RASPORED[:9]).json()
    assert "error" in _sacuvaj(RASPORED + [None]).json()
    assert _u_bazi() == RASPORED


def test_nepostojeci_item_odbijen():
    _postavi()
    _sacuvaj(RASPORED)
    assert _sacuvaj(["nema_ovog_itema"] + RASPORED[1:]).json() == {"error": "Item not found"}
    assert _sacuvaj([""] + RASPORED[1:]).json() == {"error": "Item not found"}
    assert _sacuvaj([5] + RASPORED[1:]).status_code == 422
    assert _u_bazi() == RASPORED


def test_save_i_inventar_ne_diraju_raspored():
    # game server pri odjavi i reset_stanje.py (test-pi): /save bez polja action_bar, inventory/change pre toga
    _postavi()
    _sacuvaj(RASPORED)
    telo = {"hp": 60, "mana": 100, "pos_x": 1.0, "pos_y": 1.16, "pos_z": 2.0, "inventory": [], "equipment": {}}
    assert client.post(f"/players/{TEST_IME}/save", json=telo, headers=KLJUC).json() == {"status": "ok"}
    assert _u_bazi() == RASPORED
    r = client.post(f"/players/{TEST_IME}/inventory/change",
                    json={"item_id": "small_health_potion", "delta": 3}, headers=KLJUC).json()
    assert r["status"] == "ok"
    telo["inventory"] = r["inventory"]
    assert client.post(f"/players/{TEST_IME}/save", json=telo, headers=KLJUC).json() == {"status": "ok"}
    assert _u_bazi() == RASPORED
    # i kad save posalje polje action_bar, ignorise se (raspored menja samo /action_bar)
    telo["action_bar"] = None
    assert client.post(f"/players/{TEST_IME}/save", json=telo, headers=KLJUC).json() == {"status": "ok"}
    assert _u_bazi() == RASPORED


def test_nepostojeci_igrac_i_bez_kljuca():
    assert _sacuvaj(RASPORED, ime="__nema_igraca").json() == {"error": "Player not found"}
    _postavi()
    assert _sacuvaj(RASPORED, headers={}).status_code == 403
    assert _u_bazi() is None


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
