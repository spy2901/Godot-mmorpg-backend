# NE POKRETATI bez odobrenja. Na Pi-ju (PCK_SHA256 = sha256 lokalno izvezenog .pck-a):
#   ssh spy2901@100.79.170.67 "PCK_SHA256=$(shasum -a 256 ~/mmorpg/export/mmorpg-server.pck | cut -d' ' -f1) bash -s" < migrations/pi/pi_011.sh
# Pre toga sa Mac-a (kopije, ništa se ne menja dok se ne pokrene skripta):
#   provera da su 011 fajlovi iz commit-a 6a9f3b1 (sha256 ispod mora da se poklopi i lokalno: shasum -a 256 migrations/011_efekti*.sql)
#   scp ~/mmorpg-server/migrations/011_efekti*.sql spy2901@100.79.170.67:~/mmorpg-backend/migrations/
#   (u ~/mmorpg na grani potrosni-efekti: Godot --headless --path . --export-pack "Linux (server)" export/mmorpg-server.pck)
#   scp ~/mmorpg/export/mmorpg-server.pck spy2901@100.79.170.67:~/mmorpg-server/mmorpg-server.pck.novi
# Pregled pre (samo čitanje): $M < migrations/pi/pi_pregled_011.sql
# Migracija i novi .pck u jednom koraku: backend kod se ne menja i API se ne restartuje (radi i pre i posle 011).
set -euo pipefail
umask 077
# sha256 fajlova iz commit-a 6a9f3b1 (migracija i rollback) i lokalno izvezenog .pck-a (PCK_SHA256)
MIG_SHA256=132ce1dffb713726b08765ac99648b1418d6009757f8dbf5dff4fec61b3b2894
RB_SHA256=0dddf9d2d8d2576759af29d7dcdfd357928fdcc52402ac0b677d90ae4fd25f9d
[ -n "${PCK_SHA256:-}" ] || { echo "NEMA PCK_SHA256"; exit 1; }
# 0) pre svega: sudo bez lozinke za stop i start game servera, inače prekid (ništa nije promenjeno)
for c in "stop mmorpg-game" "start mmorpg-game"; do
  sudo -n -l systemctl $c > /dev/null 2>&1 || { echo "SUDO -n NE DOZVOLJAVA: systemctl $c"; exit 1; }
done
echo "sudo -n: stop/start mmorpg-game dozvoljeni"
cd ~/mmorpg-backend
set -a; . ./.env; set +a
export MYSQL_PWD="$DB_PASSWORD"
M="mariadb --default-character-set=utf8mb4 -h$DB_HOST -u$DB_USER $DB_NAME"
[ "$DB_NAME" = "mmorpg" ] || { echo "POGREŠNA BAZA"; exit 1; }
[ -s migrations/011_efekti.sql ] && [ -s migrations/011_efekti_rollback.sql ] \
  && [ -s ~/mmorpg-server/mmorpg-server.pck.novi ] || { echo "NEMA NOVIH FAJLOVA"; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[ "$(sha migrations/011_efekti.sql)" = "$MIG_SHA256" ] || { echo "SHA256 011_efekti.sql NE ODGOVARA"; exit 1; }
[ "$(sha migrations/011_efekti_rollback.sql)" = "$RB_SHA256" ] || { echo "SHA256 011_efekti_rollback.sql NE ODGOVARA"; exit 1; }
[ "$(sha ~/mmorpg-server/mmorpg-server.pck.novi)" = "$PCK_SHA256" ] || { echo "SHA256 .pck NE ODGOVARA"; exit 1; }
echo "sha256 migracije, rollback-a i .pck-a odgovaraju"
# 1) game server stoji dok traju backup, migracija i zamena .pck (niko ne pije napitak usred zamene)
sudo -n systemctl stop mmorpg-game
# 2) backup baze i .pck
mkdir -p ~/backup-011
F=~/backup-011/mmorpg-$(date +%F-%H%M).sql
mariadb-dump -h"$DB_HOST" -u"$DB_USER" --single-transaction --routines --no-tablespaces "$DB_NAME" > "$F"
[ -s "$F" ] && tail -n1 "$F" | grep -q '^-- Dump completed' || { echo "BACKUP PRAZAN ILI NEZAVRŠEN"; exit 1; }
ls -la "$F"
cp -p ~/mmorpg-server/mmorpg-server.pck ~/backup-011/mmorpg-server.pck.pre
# 3) migracija (ispisuje tabelu predmet | pre | posle), pa provera
$M < migrations/011_efekti.sql
[ "$($M -N -e "SELECT (SELECT COUNT(*) FROM items_pre_011) = 3
  AND (SELECT COUNT(*) FROM items WHERE (id, quest_item, cooldown_ms, buff_tip, buff_vrednost, buff_trajanje_ms) IN (
       ('invisibility_potion', 0, 60000, 'nevidljivost', 1, 20000), ('resurrection_potion', 0, 5000, 'vaskrsenje', 50, 600000),
       ('antidote', 0, 5000, 'protivotrov', 1, 30000))) = 3
  AND (SELECT hp_efekat FROM items WHERE id = 'antidote') = 20")" = 1 ] || { echo "MIGRACIJA NEPOTPUNA"; exit 1; }
# 4) .pck
mv ~/mmorpg-server/mmorpg-server.pck.novi ~/mmorpg-server/mmorpg-server.pck
# 5) start game servera, provera (API radi sve vreme)
curl -s http://localhost:8001/items/invisibility_potion
echo
sudo -n systemctl start mmorpg-game
sleep 2
systemctl is-active mmorpg-api mmorpg-game
journalctl -u mmorpg-game -n 15 --no-pager
# ROLLBACK (posebno odobrenje): stop mmorpg-game; cp ~/backup-011/mmorpg-server.pck.pre ~/mmorpg-server/mmorpg-server.pck;
#   $M < migrations/011_efekti_rollback.sql (vraća tri reda ako se nisu menjali, briše items_pre_011); start mmorpg-game.
#   Buffovi i otrov nisu u bazi, pa igrači gube samo aktivne efekte (kao restart).
