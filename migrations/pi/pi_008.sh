# NE POKRETATI bez odobrenja. Na Pi-ju: ssh spy2901@100.79.170.67 'bash -s' < migrations/pi/pi_008.sh
# Pre toga sa Mac-a (kopije, ništa se ne menja dok se ne pokrene skripta):
#   scp ~/mmorpg-server/napredak.py spy2901@100.79.170.67:~/mmorpg-backend/napredak.py.novi
#   scp ~/mmorpg-server/routers/players.py spy2901@100.79.170.67:~/mmorpg-backend/routers/players.py.novi
#   scp ~/mmorpg-server/migrations/008_napredak*.sql spy2901@100.79.170.67:~/mmorpg-backend/migrations/
set -euo pipefail
umask 077
# 0) pre svega: sudo bez lozinke za stop i start oba servisa, inace prekid (nista nije promenjeno)
for c in "stop mmorpg-game" "stop mmorpg-api" "start mmorpg-api" "start mmorpg-game"; do
  sudo -n -l systemctl $c > /dev/null 2>&1 || { echo "SUDO -n NE DOZVOLJAVA: systemctl $c"; exit 1; }
done
echo "sudo -n: stop/start mmorpg-game i mmorpg-api dozvoljeni"
cd ~/mmorpg-backend
set -a; . ./.env; set +a
export MYSQL_PWD="$DB_PASSWORD"
M="mariadb --default-character-set=utf8mb4 -h$DB_HOST -u$DB_USER $DB_NAME"
[ "$DB_NAME" = "mmorpg" ] || { echo "POGREŠNA BAZA"; exit 1; }
[ -s napredak.py.novi ] && [ -s routers/players.py.novi ] && [ -s migrations/008_napredak.sql ] || { echo "NEMA NOVIH FAJLOVA"; exit 1; }
# 1) game server pa API stoje dok traju backup, migracija i zamena koda (stari kod bi na novim vrednostima opet
#    mnozio pri level-up-u; bez game servera nema XP-a koji bi se izgubio dok API stoji)
sudo -n systemctl stop mmorpg-game
sudo -n systemctl stop mmorpg-api
# 2) backup baze i koda
mkdir -p ~/backup-008
F=~/backup-008/mmorpg-$(date +%F-%H%M).sql
mariadb-dump -h"$DB_HOST" -u"$DB_USER" --single-transaction --routines "$DB_NAME" > "$F"
[ -s "$F" ] || { echo "BACKUP PRAZAN"; exit 1; }
ls -la "$F"
cp -p routers/players.py ~/backup-008/players.py.pre
# 3) migracija (ispisuje tabelu pre/posle za sve likove)
$M < migrations/008_napredak.sql
[ "$($M -N -e "SELECT (SELECT COUNT(*) FROM players_pre_008) = (SELECT COUNT(*) FROM players)")" = 1 ] || { echo "REZERVNA TABELA NEPOTPUNA"; exit 1; }
[ "$($M -N -e "SELECT COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='mmorpg' AND TABLE_NAME='players' AND COLUMN_NAME='napad_damage'")" = 10 ] || { echo "DEFAULT NIJE 10"; exit 1; }
# 4) kod
mv napredak.py.novi napredak.py
mv routers/players.py.novi routers/players.py
# 5) start API pa game server, provera
sudo -n systemctl start mmorpg-api
sleep 2
sudo -n systemctl start mmorpg-game
sleep 2
systemctl is-active mmorpg-api mmorpg-game
journalctl -u mmorpg-api -n 15 --no-pager
journalctl -u mmorpg-game -n 15 --no-pager
# ROLLBACK (posebno odobrenje): stop mmorpg-game i mmorpg-api; cp ~/backup-008/players.py.pre routers/players.py;
#   $M < migrations/008_napredak_rollback.sql; start mmorpg-api pa mmorpg-game (napredak.py može da ostane, stari kod ga ne uvozi)
