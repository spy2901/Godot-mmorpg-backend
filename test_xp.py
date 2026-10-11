"""Test za _primeni_xp bez baze. Pokretanje: python3.12 test_xp.py (ili pytest test_xp.py)."""
from routers.players import _primeni_xp

POCETAK = {"level": 1, "xp": 0, "max_xp": 100, "max_hp": 100, "max_mana": 100, "napad_damage": 250}


def test_delta_nula():
    assert _primeni_xp(POCETAK, 0) == {**POCETAK, "level_up": False}


def test_negativna_delta_se_ignorise():
    assert _primeni_xp(POCETAK, -50) == {**POCETAK, "level_up": False}


def test_tacno_do_level_upa():
    assert _primeni_xp(POCETAK, 99) == {**POCETAK, "xp": 99, "level_up": False}
    assert _primeni_xp(POCETAK, 100) == {
        "level": 2, "xp": 0, "max_xp": 150, "max_hp": 115,
        "max_mana": 110, "napad_damage": 275, "level_up": True,
    }


def test_dva_levela_sa_prenosom_viska():
    # 100 za level 2, 150 za level 3, 30 ostaje
    assert _primeni_xp(POCETAK, 280) == {
        "level": 3, "xp": 30, "max_xp": 225, "max_hp": 132,
        "max_mana": 121, "napad_damage": 302, "level_up": True,
    }


def test_max_xp_nula_ne_vrti_beskonacno():
    s = _primeni_xp({**POCETAK, "max_xp": 0}, 5)
    assert s["level"] > 1


if __name__ == "__main__":
    for ime, f in list(globals().items()):
        if ime.startswith("test_"):
            f()
            print("ok", ime)
