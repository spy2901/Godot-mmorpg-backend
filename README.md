# mmorpg-server

## Testovi

```bash
tests/run_with_temp_db.sh -q
```

Skripta podigne privremenu MariaDB 11.8 na slobodnom portu, napravi bazu `mmorpg` iz `~/mmorpg_dump.sql`, primeni
migracije 002-007, pokrene pytest i na kraju bazu ugasi i obriše. Pi i lokalni MySQL (localhost:3306) se ne diraju.

Baza namerno staje na 007: `test_migracija_008.py` i `test_migracija_009.py` kopiraju tabele iz te baze i na kopiji
puštaju 008/009, pa traže stanje pre njih (npr. podrazumevani napad 250, antidote nije potrošan). Na bazi sa
primenjenim 008/009 ti testovi i `test_nepotrosni_predmet` padaju (27/32).
