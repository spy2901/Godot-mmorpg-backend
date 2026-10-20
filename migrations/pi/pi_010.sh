# NE POKRETATI bez odobrenja. Na Pi-ju: ssh spy2901@100.79.170.67 'bash -s' < migrations/pi/pi_010.sh
# Pre toga sa Mac-a (kopije, ništa se ne menja dok se ne pokrene skripta):
#   scp ~/mmorpg-server/routers/players.py spy2901@100.79.170.67:~/mmorpg-backend/routers/players.py.novi
#   scp ~/mmorpg-server/migrations/010_buffovi*.sql spy2901@100.79.170.67:~/mmorpg-backend/migrations/
#   (u ~/mmorpg na grani buff-sistem: Godot --headless --path . --export-pack "Linux (server)" export/mmorpg-server.pck)
#   scp ~/mmorpg/export/mmorpg-server.pck spy2901@100.79.170.67:~/mmorpg-server/mmorpg-server.pck.novi
# Pregled pre (samo čitanje): $M < migrations/pi/pi_pregled_010.sql
# Redosled: migracija, pa novi players.py (čita buff_* kolone, ali radi i bez njih: SELECT *), pa novi .pck.
set -euo pipefail
umask 077
# 0) pre svega: sudo bez lozinke za stop i start oba servisa, inače prekid (ništa nije promenjeno)
for c in "stop mmorpg-game" "stop mmorpg-api" "start mmorpg-api" "start mmorpg-game"; do
  sudo -n -l systemctl $c > /dev/null 2>&1 || { echo "SUDO -n NE DOZVOLJAVA: systemctl $c"; exit 1; }
done
echo "sudo -n: stop/start mmorpg-game i mmorpg-api dozvoljeni"
cd ~/mmorpg-backend
set -a; . ./.env; set +a
export MYSQL_PWD="$DB_PASSWORD"
M="mariadb --default-character-set=utf8mb4 -h$DB_HOST -u$DB_USER $DB_NAME"
[ "$DB_NAME" = "mmorpg" ] || { echo "POGREŠNA BAZA"; exit 1; }
[ -s routers/players.py.novi ] && [ -s migrations/010_buffovi.sql ] && [ -s migrations/010_buffovi_rollback.sql ] \
  && [ -s ~/mmorpg-server/mmorpg-server.pck.novi ] || { echo "NEMA NOVIH FAJLOVA"; exit 1; }
# 1) game server pa API stoje dok traju backup, migracija i zamena koda (niko ne pije eliksir ni ne kupuje usred zamene)
sudo -n systemctl stop mmorpg-game
sudo -n systemctl stop mmorpg-api
# 2) backup baze, players.py i .pck
mkdir -p ~/backup-010
F=~/backup-010/mmorpg-$(date +%F-%H%M).sql
mariadb-dump -h"$DB_HOST" -u"$DB_USER" --single-transaction --routines --no-tablespaces "$DB_NAME" > "$F"
[ -s "$F" ] && tail -n1 "$F" | grep -q '^-- Dump completed' || { echo "BACKUP PRAZAN ILI NEZAVRŠEN"; exit 1; }
ls -la "$F"
cp -p routers/players.py ~/backup-010/players.py.pre
cp -p ~/mmorpg-server/mmorpg-server.pck ~/backup-010/mmorpg-server.pck.pre
# 3) migracija (ispisuje tabelu predmet | pre | posle), pa provera
$M < migrations/010_buffovi.sql
[ "$($M -N -e "SELECT (SELECT COUNT(*) FROM items_pre_010) = 5
  AND (SELECT COUNT(*) FROM items WHERE buff_tip IS NOT NULL) = 5
  AND (SELECT COUNT(*) FROM items WHERE id IN ('elixir_of_strength', 'elixir_of_defense', 'elixir_of_wisdom', 'elixir_of_luck',
       'speed_potion') AND cooldown_ms = 5000 AND quest_item = 0 AND buff_trajanje_ms > 0) = 5
  AND (SELECT COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items'
       AND COLUMN_NAME = 'buff_tip') = (SELECT TABLE_COLLATION FROM information_schema.TABLES
       WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items')")" = 1 ] || { echo "MIGRACIJA NEPOTPUNA"; exit 1; }
# 4) kod i .pck
mv routers/players.py.novi routers/players.py
mv ~/mmorpg-server/mmorpg-server.pck.novi ~/mmorpg-server/mmorpg-server.pck
# 5) start API pa game server, provera
sudo -n systemctl start mmorpg-api
sleep 2
curl -s http://localhost:8001/items/elixir_of_strength
echo
sudo -n systemctl start mmorpg-game
sleep 2
systemctl is-active mmorpg-api mmorpg-game
journalctl -u mmorpg-api -n 15 --no-pager
journalctl -u mmorpg-game -n 15 --no-pager
# ROLLBACK (posebno odobrenje): stop mmorpg-game i mmorpg-api;
#   cp ~/backup-010/players.py.pre routers/players.py; cp ~/backup-010/mmorpg-server.pck.pre ~/mmorpg-server/mmorpg-server.pck;
#   $M < migrations/010_buffovi_rollback.sql (vraća cooldown i quest_item ako se nisu menjali, briše buff_* kolone i
#   items_pre_010); start mmorpg-api pa mmorpg-game. Buffovi nisu u bazi, pa igrači gube samo aktivne buffove (kao restart).
