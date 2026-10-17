"""Test za XP krivu i statistike po nivou bez baze. Pokretanje: python3.12 test_xp.py (ili pytest test_xp.py).
primeni_xp se uvozi iz routers.players: obe rute koje daju XP (xp/change i quest/turnin) zovu bas nju."""
from napredak import MAX_LEVEL, statistike_za_nivo
from routers.players import primeni_xp

POCETAK = {"level": 1, "xp": 0, "max_xp": 100, "max_hp": 100, "max_mana": 100, "napad_damage": 10}


def _nivo(level, xp, level_up):
    return {**statistike_za_nivo(level), "xp": xp, "level_up": level_up}


def test_kriva_i_statistike_po_tabeli():
    # (nivo, XP do sledeceg, max HP, mana, napad) iz odobrene tabele
    for L, max_xp, hp, mana, napad in [(1, 100, 100, 100, 10), (2, 250, 115, 110, 12), (5, 1000, 160, 140, 18),
                                       (10, 3250, 235, 190, 28), (19, 10450, 370, 280, 46), (20, 0, 385, 290, 48)]:
        assert statistike_za_nivo(L) == {"level": L, "max_xp": max_xp, "max_hp": hp, "max_mana": mana, "napad_damage": napad}
    assert sum(statistike_za_nivo(L)["max_xp"] for L in range(1, MAX_LEVEL)) == 76000


def test_delta_nula_i_negativna():
    assert primeni_xp(POCETAK, 0) == _nivo(1, 0, False)
    assert primeni_xp(POCETAK, -50) == _nivo(1, 0, False)


def test_tacno_do_level_upa():
    assert primeni_xp(POCETAK, 99) == _nivo(1, 99, False)
    assert primeni_xp(POCETAK, 100) == _nivo(2, 0, True)


def test_vise_nivoa_odjednom_sa_prenosom_viska():
    # 100 za nivo 2, 250 za 3, 450 za 4, 30 ostaje
    assert primeni_xp(POCETAK, 830) == _nivo(4, 30, True)


def test_statistike_iz_nivoa_ne_iz_starih_vrednosti():
    # stare (uvecane) vrednosti u redu se ne mnoze dalje: vazi samo nivo
    stari = {"level": 3, "xp": 10, "max_xp": 225, "max_hp": 132, "max_mana": 121, "napad_damage": 302}
    assert primeni_xp(stari, 5) == _nivo(3, 15, False)


def test_nivo_20_je_maksimum():
    s = primeni_xp(POCETAK, 10_000_000)
    assert s == _nivo(20, 0, True) and s["max_xp"] == 0
    na_maksimumu = {**POCETAK, "level": 20, "xp": 0, "max_xp": 0}
    assert primeni_xp(na_maksimumu, 500) == _nivo(20, 0, False)  # XP se ne skuplja, nema beskonacne petlje
    assert primeni_xp({**POCETAK, "level": 57}, 5) == _nivo(20, 0, False)  # nivo iznad maksimuma vazi kao 20


def test_poslednji_level_up_do_maksimuma():
    s19 = {**POCETAK, "level": 19, "xp": 10_000}
    assert primeni_xp(s19, 449) == _nivo(19, 10_449, False)
    assert primeni_xp(s19, 450 + 7) == _nivo(20, 0, True)  # visak posle nivoa 20 se ne cuva


if __name__ == "__main__":
    for ime, f in list(globals().items()):
        if ime.startswith("test_"):
            f()
            print("ok", ime)
