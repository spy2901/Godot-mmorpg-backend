#!/usr/bin/env bash
# Backend testovi na privremenoj MariaDB 11.8: baza iz ~/mmorpg_dump.sql + migracije 002-007 (stanje pre 008, vidi README).
# Ne dira Pi ni localhost:3306. Argumenti idu pytest-u. Pokretanje: tests/run_with_temp_db.sh [-q]
set -euo pipefail

MARIADB_BIN="${MARIADB_BIN:-/opt/homebrew/opt/mariadb@11.8/bin}"
DUMP="${DUMP:-$HOME/mmorpg_dump.sql}"
PYTHON="${PYTHON:-python3.12}"
KOREN="$(cd "$(dirname "$0")/.." && pwd)"

[ -f "$DUMP" ] || { echo "nema dump-a: $DUMP" >&2; exit 1; }
DIR="$(mktemp -d)"
PID=
PORT="$("$PYTHON" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"

ugasi() {
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$DIR"
}
trap ugasi EXIT

sql() { "$MARIADB_BIN/mariadb" -h127.0.0.1 -P"$PORT" -uroot --skip-ssl-verify-server-cert --default-character-set=utf8mb4 "$@" >/dev/null; }

"$MARIADB_BIN/mariadb-install-db" --datadir="$DIR/data" --auth-root-authentication-method=normal --skip-test-db >"$DIR/install.log" 2>&1
"$MARIADB_BIN/mariadbd" --no-defaults --datadir="$DIR/data" --port="$PORT" --bind-address=127.0.0.1 \
  --socket="$DIR/sock" --pid-file="$DIR/pid" --log-error="$DIR/err.log" &
PID=$!
for _ in $(seq 1 30); do
  "$MARIADB_BIN/mariadb-admin" -h127.0.0.1 -P"$PORT" -uroot ping >/dev/null 2>&1 && break
  sleep 1
done

sql -e 'CREATE DATABASE mmorpg'
sql mmorpg < "$DUMP"
# migrations.sql se preskače: dump već ima te kolone i tabelu players
for f in 002_accounts 003_potions 004_sessions_unique 005_action_bar 006_quest_english 007_oprema; do
  sql mmorpg < "$KOREN/migrations/$f.sql"
done

cd "$KOREN"
DB_HOST=127.0.0.1 DB_PORT="$PORT" DB_USER=root DB_PASSWORD= DB_NAME=mmorpg "$PYTHON" -m pytest "$@"
