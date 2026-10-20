#!/usr/bin/env bash
# Provera oporavka na Mac-u: vrati dump na privremenu MariaDB 11.8 (slobodan port, kao tests/run_with_temp_db.sh),
# uporedi broj redova po tabeli sa manifestom iz ops/mmorpg_backup.sh, pa bazu ugasi i obriše.
# FAIL (exit 1): tabela iz manifesta ne postoji, ili je prazna a u manifestu nije. WARN: broj se razlikuje
# (brojanje i dump nisu u istoj transakciji). Pokretanje: ops/verify_restore.sh mmorpg-DAN.sql.zst [mmorpg-DAN.manifest]
set -euo pipefail

MARIADB_BIN="${MARIADB_BIN:-/opt/homebrew/opt/mariadb@11.8/bin}"
DUMP="$1"
MANIFEST="${2:-${DUMP%.sql.zst}.manifest}"
[ -s "$DUMP" ] && [ -s "$MANIFEST" ] || { echo "FAIL nema dump-a ili manifesta: $DUMP $MANIFEST" >&2; exit 1; }
zstd -t -q "$DUMP" || { echo "FAIL zstd -t pada: $DUMP" >&2; exit 1; }

DIR="$(mktemp -d)"
PID=
PORT="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
ugasi() {
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$DIR"
}
trap ugasi EXIT
sql() { "$MARIADB_BIN/mariadb" -h127.0.0.1 -P"$PORT" -uroot --skip-ssl-verify-server-cert --default-character-set=utf8mb4 "$@"; }

"$MARIADB_BIN/mariadb-install-db" --datadir="$DIR/data" --auth-root-authentication-method=normal --skip-test-db >"$DIR/install.log" 2>&1
"$MARIADB_BIN/mariadbd" --no-defaults --datadir="$DIR/data" --port="$PORT" --bind-address=127.0.0.1 \
  --socket="$DIR/sock" --pid-file="$DIR/pid" --log-error="$DIR/err.log" &
PID=$!
for _ in $(seq 1 30); do
  "$MARIADB_BIN/mariadb-admin" -h127.0.0.1 -P"$PORT" -uroot ping >/dev/null 2>&1 && break
  sleep 1
done

sql -e 'CREATE DATABASE mmorpg'
zstd -dc "$DUMP" | sql mmorpg

GRESKA=0
printf '%-20s %10s %10s\n' tabela manifest vraceno
while read -r t n; do
  v="$(sql -N -B mmorpg -e "SELECT COUNT(*) FROM \`$t\`" 2>/dev/null)" || v=NEMA
  if [ "$v" = NEMA ] || { [ "$v" = 0 ] && [ "$n" != 0 ]; }; then s=FAIL; GRESKA=1
  elif [ "$v" != "$n" ]; then s=WARN
  else s=OK; fi
  printf '%-20s %10s %10s  %s\n' "$t" "$n" "$v" "$s"
done < "$MANIFEST"
[ "$GRESKA" = 0 ] && echo "OK oporavak $DUMP" || { echo "FAIL oporavak $DUMP" >&2; exit 1; }
