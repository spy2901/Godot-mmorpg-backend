#!/usr/bin/env bash
# Dnevni backup baze mmorpg na Pi-ju (pokreće ga mmorpg-backup.timer, 04:15 UTC). Izlaz i greške idu u journal:
# journalctl -u mmorpg-backup. Igra radi za vreme backup-a (sve tabele su InnoDB, --single-transaction ne zaključava).
# Tabela sessions: samo šema. Zadržavanje 14 dnevnih + 8 nedeljnih (nedelja); nedeljno i config arhiva (.env, unit-i, .pck).
# Uspeh = $DEST/LAST_OK (UTC vreme); Mac javlja kad je stariji od 2 dana (ops/pull_backup_mac.sh).
set -Eeuo pipefail
umask 077
trap 'echo "GREŠKA: linija $LINENO: $BASH_COMMAND" >&2' ERR

BACKEND="${BACKEND:-$HOME/mmorpg-backend}"
DEST="${DEST:-$HOME/mmorpg-backups}"
DNEVNIH=14
NEDELJNIH=8
DAN="$(date -u +%F)"

# DB_* iz .env bez source-a; lozinka samo u privremenom defaults fajlu (600), ne u argumentima
getvar() { grep -E "^$1=" "$BACKEND/.env" | tail -n1 | cut -d= -f2- | sed -e 's/^["'"'"']//' -e 's/["'"'"']$//'; }
DB_NAME="$(getvar DB_NAME)"
[ -n "$DB_NAME" ] || { echo "GREŠKA: DB_NAME prazan u $BACKEND/.env" >&2; exit 1; }
CNF="$(mktemp)"
TMP=()
trap 'rm -f "$CNF" "${TMP[@]}"' EXIT
printf '[client]\nhost=%s\nport=%s\nuser=%s\npassword=%s\n' "$(getvar DB_HOST)" "$(getvar DB_PORT)" "$(getvar DB_USER)" \
  "$(getvar DB_PASSWORD)" > "$CNF"
sql() { mariadb --defaults-extra-file="$CNF" -N -B "$DB_NAME" "$@"; }
dump() { mariadb-dump --defaults-extra-file="$CNF" --single-transaction --quick --routines --events --triggers \
  --no-tablespaces --hex-blob --default-character-set=utf8mb4 "$@"; }

mkdir -p "$DEST"/daily "$DEST"/weekly "$DEST"/config
chmod 700 "$DEST"

# manifest: broj redova po tabeli neposredno pre dump-a (verify_restore.sh ga poredi posle vraćanja); sessions = 0
F="$DEST/daily/mmorpg-$DAN.sql.zst"
M="$DEST/daily/mmorpg-$DAN.manifest"
TMP+=("$F.part" "$M.part")
TABELE="$(sql -e "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()
                  AND table_type = 'BASE TABLE' ORDER BY 1")"
for t in $TABELE; do
  if [ "$t" = sessions ]; then echo "$t 0"; else echo "$t $(sql -e "SELECT COUNT(*) FROM \`$t\`")"; fi
done > "$M.part"
[ -s "$M.part" ] || { echo "GREŠKA: baza $DB_NAME nema tabela" >&2; exit 1; }

{ dump --ignore-table="$DB_NAME.sessions" "$DB_NAME"; dump --no-data "$DB_NAME" sessions; } | zstd -q -19 > "$F.part"

# provera pre upisa: nije prazan, dekompresuje se, oba dump-a završena
[ -s "$F.part" ] || { echo "GREŠKA: dump prazan" >&2; exit 1; }
zstd -t -q "$F.part" || { echo "GREŠKA: zstd -t pada za $F.part" >&2; exit 1; }
[ "$(zstd -dc "$F.part" | grep -c '^-- Dump completed')" = 2 ] || { echo "GREŠKA: dump nije završen" >&2; exit 1; }
mv "$M.part" "$M"
mv "$F.part" "$F"
echo "OK dump $F ($(stat -c %s "$F") B), tabela $(wc -l < "$M")"

# nedeljno (nedelja, ili kad još nema nijedne config arhive): tvrdi link dump-a i config arhiva
if [ "$(date -u +%u)" = 7 ] || [ -z "$(ls -A "$DEST/config")" ]; then
  ln -f "$F" "$DEST/weekly/"
  ln -f "$M" "$DEST/weekly/"
  C="$DEST/config/config-$DAN.tar.zst"
  TMP+=("$C.part" "$DEST/config/grants.txt")
  sql -e "SHOW GRANTS" > "$DEST/config/grants.txt"
  tar -c --zstd -f "$C.part" --exclude=venv --exclude=__pycache__ \
    -C "$HOME" mmorpg-backend mmorpg-game.env mmorpg-server/mmorpg-server.pck mmorpg-server/mmorpg-server.sh \
    -C / etc/systemd/system/mmorpg-api.service etc/systemd/system/mmorpg-game.service \
    etc/systemd/system/mmorpg-backup.service etc/systemd/system/mmorpg-backup.timer \
    etc/systemd/journald.conf.d/90-persistent.conf \
    -C "$DEST/config" grants.txt
  zstd -t -q "$C.part"
  mv "$C.part" "$C"
  echo "OK config $C ($(stat -c %s "$C") B)"
fi

# zadržavanje po broju fajlova, tek posle uspeha (ime sadrži datum, pa sort = hronološki)
obrisi_stare() { { ls -1 "$1"/*"$2" 2>/dev/null || true; } | sort | head -n -"$3" | while read -r f; do rm -f "$f" "${f%"$2"}.manifest"; done; }
obrisi_stare "$DEST/daily" .sql.zst "$DNEVNIH"
obrisi_stare "$DEST/weekly" .sql.zst "$NEDELJNIH"
obrisi_stare "$DEST/config" .tar.zst "$NEDELJNIH"

date -u +%FT%TZ > "$DEST/LAST_OK.part"
mv "$DEST/LAST_OK.part" "$DEST/LAST_OK"
echo "OK LAST_OK $(cat "$DEST/LAST_OK")"
