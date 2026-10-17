"""Napredak lika kroz nivoe (bez zavisnosti: koristi ga i stub iz run-mmorpg testova).
Statistike se uvek racunaju iz nivoa; kolone u bazi (max_xp, max_hp, max_mana, napad_damage) su njihova kopija."""

MAX_LEVEL = 20


def statistike_za_nivo(level: int) -> dict:
    L = min(max(int(level), 1), MAX_LEVEL)
    return {
        "level": L,
        "max_xp": 0 if L == MAX_LEVEL else 25 * L * L + 75 * L,  # XP do sledeceg nivoa; 0 = maksimum
        "max_hp": 100 + 15 * (L - 1),  # osnovni, bez hp_bonus opreme
        "max_mana": 100 + 10 * (L - 1),
        "napad_damage": 10 + 2 * (L - 1),  # osnovni, bez oruzja
    }


def primeni_xp(row: dict, delta: int) -> dict:
    """Doda XP (negativno se ignorise), visak prelazi u sledeci nivo, vise nivoa odjednom.
    Na MAX_LEVEL se XP ne skuplja (xp = 0, max_xp = 0)."""
    pocetni = min(max(int(row.get("level") or 1), 1), MAX_LEVEL)
    s = statistike_za_nivo(pocetni)
    xp = int(row.get("xp") or 0) + max(int(delta), 0)
    while s["max_xp"] and xp >= s["max_xp"]:
        xp -= s["max_xp"]
        s = statistike_za_nivo(s["level"] + 1)
    s["xp"] = xp if s["max_xp"] else 0
    s["level_up"] = s["level"] > pocetni
    return s
