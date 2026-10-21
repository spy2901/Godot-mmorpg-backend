"""Integracioni test za POST /players/{ime}/item/use protiv lokalne baze (MAMP).
Koristi privremenog igraca TEST_IME i brise ga na kraju; pravi igraci se ne diraju.
Pokretanje: python3.12 test_item_use.py (ili pytest test_item_use.py).
DB_* se po potrebi zadaju kroz env (npr. DB_PORT=8889 DB_USER=root DB_PASSWORD=root)."""
import json
import os

os.environ["SERVER_KEY"] = "test-kljuc"  # pre importa; load_dotenv ne pregazi postojeci env

import pymysql
from fastapi.testclient import TestClient

from db import DB_CONFIG
from main import app

TEST_IME = "__test_item_use"
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


def _postavi(inventory, equipment=None):
    _sql("DELETE FROM players WHERE ime = %s", (TEST_IME,))
    _sql("INSERT INTO players (ime, inventory, equipment) VALUES (%s, %s, %s)",
         (TEST_IME, json.dumps(inventory), json.dumps(equipment or {})))


def _inv():
    return json.loads(_sql("SELECT inventory FROM players WHERE ime = %s", (TEST_IME,))[0][0])


def _use(item_id, ime=TEST_IME, headers=KLJUC):
    return client.post(f"/players/{ime}/item/use", json={"item_id": item_id}, headers=headers)


def test_uspesna_potrosnja():
    _postavi([{"id": "small_health_potion", "kolicina": 3, "slot": 0}])
    r = _use("small_health_potion").json()
    assert r["status"] == "ok" and r["item_id"] == "small_health_potion"
    assert r["hp_efekat"] == 30 and r["mana_efekat"] == 0 and r["cooldown_ms"] == 5000
    assert r["inventory"] == [{"id": "small_health_potion", "kolicina": 2, "slot": 0}]
    assert _inv() == r["inventory"]


def test_stack_nestaje_na_nuli_i_drugi_poziv_pada():
    _postavi([{"id": "mana_potion", "kolicina": 1, "slot": 4},
              {"id": "iron_ore", "kolicina": 5, "slot": 1}])
    r = _use("mana_potion").json()
    assert r["status"] == "ok" and r["mana_efekat"] == 50
    assert r["inventory"] == [{"id": "iron_ore", "kolicina": 5, "slot": 1}]
    assert _use("mana_potion").json() == {"error": "Nedovoljno itema"}
    assert _inv() == [{"id": "iron_ore", "kolicina": 5, "slot": 1}]


def test_nepotrosni_predmet():
    _postavi([{"id": "iron_ore", "kolicina": 5, "slot": 0}])
    assert _use("iron_ore").json() == {"error": "Item nije potrosni"}
    # consumable bez hp/mana efekta
    _postavi([{"id": "antidote", "kolicina": 1, "slot": 0}])
    assert _use("antidote").json() == {"error": "Item nije potrosni"}
    assert _inv() == [{"id": "antidote", "kolicina": 1, "slot": 0}]


def test_buff_predmet_bez_010_odbijen():
    # baza pre migracije 010 (nema buff_* kolona): eliksir je i dalje "nije potrosni", ostalo radi kao ranije
    if _sql("SHOW COLUMNS FROM items LIKE 'buff_tip'"):
        return
    _postavi([{"id": "elixir_of_strength", "kolicina": 1, "slot": 0}])
    assert _use("elixir_of_strength").json() == {"error": "Item nije potrosni"}


def test_buff_predmet_posle_010():
    # posebna baza sa primenjenom 010 (DB_NAME ostaje u stanju koje traže testovi migracija 008/009)
    import test_migracija_010 as m010
    m010._napravi_bazu()
    stara = DB_CONFIG["db"]
    try:
        assert m010._pokreni(m010.MIGRACIJA).returncode == 0
        DB_CONFIG["db"] = m010.TEST_DB
        for id, (tip, vrednost, trajanje) in m010.BUFFOVI.items():
            _postavi([{"id": id, "kolicina": 2, "slot": 3}])
            r = _use(id).json()
            assert r["status"] == "ok" and r["item_id"] == id, r
            assert (r["buff_tip"], r["buff_vrednost"], r["buff_trajanje_ms"]) == (tip, vrednost, trajanje)
            assert (r["hp_efekat"], r["mana_efekat"], r["cooldown_ms"]) == (0, 0, 5000)
            assert r["inventory"] == [{"id": id, "kolicina": 1, "slot": 3}] and _inv() == r["inventory"]
        # predmet bez buff-a i bez efekta i dalje nije potrošan; napitak vraća prazan buff
        _postavi([{"id": "iron_ore", "kolicina": 1, "slot": 0}, {"id": "small_health_potion", "kolicina": 1, "slot": 1}])
        assert _use("iron_ore").json() == {"error": "Item nije potrosni"}
        r = _use("small_health_potion").json()
        assert r["hp_efekat"] == 30 and (r["buff_tip"], r["buff_vrednost"], r["buff_trajanje_ms"]) == (None, 0, 0)
    finally:
        DB_CONFIG["db"] = stara
        m010._sql(f"DROP DATABASE IF EXISTS {m010.TEST_DB}", db=None)


def test_efekti_posle_011():
    # posebna baza sa primenjenom 011: backend samo prosleđuje nove buff_tip (efekte primenjuje game server)
    import test_migracija_011 as m011
    m011._napravi_bazu()
    stara = DB_CONFIG["db"]
    try:
        assert m011._pokreni(m011.MIGRACIJA).returncode == 0
        DB_CONFIG["db"] = m011.TEST_DB
        for id, (_q, cd, hp, tip, vrednost, trajanje) in m011.EFEKTI.items():
            _postavi([{"id": id, "kolicina": 2, "slot": 0}])
            r = _use(id).json()
            assert r["status"] == "ok" and (r["hp_efekat"], r["cooldown_ms"]) == (hp, cd), r
            assert (r["buff_tip"], r["buff_vrednost"], r["buff_trajanje_ms"]) == (tip, vrednost, trajanje), r
            assert r["inventory"] == [{"id": id, "kolicina": 1, "slot": 0}] and _inv() == r["inventory"]
    finally:
        DB_CONFIG["db"] = stara
        m011._sql(f"DROP DATABASE IF EXISTS {m011.TEST_DB}", db=None)


def test_predmet_koji_igrac_nema():
    _postavi([{"id": "iron_ore", "kolicina": 5, "slot": 0}])
    assert _use("large_health_potion").json() == {"error": "Nedovoljno itema"}


def test_nepostojeci_item_i_igrac():
    _postavi([])
    assert _use("nema_ovog_itema").json() == {"error": "Item not found"}
    assert _use("small_health_potion", ime="__nema_igraca").json() == {"error": "Player not found"}


def test_bez_kljuca_odbijeno():
    _postavi([{"id": "small_health_potion", "kolicina": 1, "slot": 0}])
    assert _use("small_health_potion", headers={}).status_code == 403
    assert _use("small_health_potion", headers={"X-Server-Key": "pogresan"}).status_code == 403
    assert _inv() == [{"id": "small_health_potion", "kolicina": 1, "slot": 0}]


def test_items_vraca_nove_kolone():
    r = client.get("/items/large_health_potion").json()
    assert (r["hp_efekat"], r["mana_efekat"], r["cooldown_ms"]) == (150, 0, 10000)


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
