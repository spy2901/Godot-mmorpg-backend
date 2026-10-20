#!/usr/bin/env bash
# Kopija van Pi-ja: povuče ~/mmorpg-backups sa Pi-ja u ~/mmorpg-backups na Mac-u (700), javi notifikacijom kad je
# LAST_OK stariji od 2 dana (i kad povlačenje ne uspe), pa proveri oporavak najnovijeg dnevnog dump-a.
# Log: ~/mmorpg-backups/pull.log. Pokretanje: ops/pull_backup_mac.sh (launchd: ops/launchd/*.plist).
# IZVOR: rsync izvor (podrazumevano spy2901 preko Tailscale-a; vidi ops/README.md, način pristupa još nije izabran).
set -uo pipefail

IZVOR="${IZVOR:-spy2901@100.79.170.67:mmorpg-backups/}"
CILJ="${CILJ:-$HOME/mmorpg-backups}"
MAX_STAROST_S="${MAX_STAROST_S:-172800}"
OPS="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:$PATH"

mkdir -p "$CILJ"
chmod 700 "$CILJ"
exec >>"$CILJ/pull.log" 2>&1
echo "== $(date -u +%FT%TZ) povlačenje iz $IZVOR"
javi() { echo "GREŠKA: $1"; osascript -e "display notification \"$1\" with title \"mmorpg backup\"" || true; }

# ponytail: na Mac-u se ništa ne briše (dump ~5 KB, config ~200 KB nedeljno); dodaj čišćenje kad zauzeće postane bitno
rsync -a -e "ssh -o BatchMode=yes -o ConnectTimeout=20" "$IZVOR" "$CILJ/" || javi "povlačenje sa Pi-ja nije uspelo"

POSLEDNJI="$(cat "$CILJ/LAST_OK" 2>/dev/null || true)"
T="$(date -j -u -f %Y-%m-%dT%H:%M:%SZ "$POSLEDNJI" +%s 2>/dev/null || echo 0)"
STAROST=$(( $(date +%s) - T ))
if [ "$STAROST" -gt "$MAX_STAROST_S" ]; then
  javi "poslednji uspešan backup: ${POSLEDNJI:-nikad} (pre $((STAROST / 3600)) h)"
  exit 1
fi
echo "LAST_OK $POSLEDNJI (pre $((STAROST / 3600)) h)"

NAJNOVIJI="$(ls -1 "$CILJ"/daily/mmorpg-*.sql.zst 2>/dev/null | sort | tail -n1)"
[ -n "$NAJNOVIJI" ] || { javi "nema dnevnog dump-a"; exit 1; }
"$OPS/verify_restore.sh" "$NAJNOVIJI" || { javi "provera oporavka pala: $(basename "$NAJNOVIJI")"; exit 1; }
