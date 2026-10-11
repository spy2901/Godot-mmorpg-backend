import copy

MAX_SLOTOVA = 24


def dodaj_u_inventar(inv: list, item: dict, kolicina: int) -> bool:
    """Dodaje kolicina itema u inv. item mora imati id, stackable, max_stack.
    Vraca False ako nema mesta; tada inv ostaje nepromenjen."""
    novi_inv = copy.deepcopy(inv)
    ostalo = kolicina
    if item["stackable"] == 1:
        for e in novi_inv:
            if e["id"] == item["id"] and e["kolicina"] < item["max_stack"] and ostalo > 0:
                dodaj = min(ostalo, item["max_stack"] - e["kolicina"])
                e["kolicina"] += dodaj
                ostalo -= dodaj
    while ostalo > 0:
        novi = min(ostalo, item["max_stack"]) if item["stackable"] == 1 else 1
        if len(novi_inv) >= MAX_SLOTOVA:
            return False
        zauzeti = {e.get("slot") for e in novi_inv if "slot" in e}
        slot = next((i for i in range(MAX_SLOTOVA) if i not in zauzeti), None)
        if slot is None:  # pokvareni slotovi u starim podacima
            return False
        novi_inv.append({"id": item["id"], "kolicina": novi, "slot": slot})
        ostalo -= novi
    inv[:] = novi_inv
    return True


def ukloni_iz_inventara(inv: list, item_id: str, kolicina: int) -> bool:
    """Skida kolicina itema iz inv. Vraca False ako nema dovoljno; tada inv ostaje nepromenjen."""
    ukupno = sum(e["kolicina"] for e in inv if e["id"] == item_id)
    if ukupno < kolicina:
        return False
    potrebno = kolicina
    for e in list(inv):
        if e["id"] == item_id and potrebno > 0:
            skini = min(potrebno, e["kolicina"])
            e["kolicina"] -= skini
            potrebno -= skini
            if e["kolicina"] == 0:
                inv.remove(e)
    return True
