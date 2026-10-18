# NE POKRETATI bez odobrenja. Na Pi-ju: ssh spy2901@100.79.170.67 'bash -s' < migrations/pi/pi_009.sh
# Pre toga sa Mac-a (kopije, ništa se ne menja dok se ne pokrene skripta):
#   scp ~/mmorpg-server/migrations/009_sadrzaj*.sql spy2901@100.79.170.67:~/mmorpg-backend/migrations/
#   (u ~/mmorpg: Godot --headless --path . --export-pack "Linux (server)" export/mmorpg-server.pck)
#   scp ~/mmorpg/export/mmorpg-server.pck spy2901@100.79.170.67:~/mmorpg-server/mmorpg-server.pck.novi
# Pregled pre (samo čitanje): $M < migrations/pi/pi_pregled_009.sql
# Backend kod se ne menja (009 menja samo podatke u items i quests), pa mmorpg-api radi sve vreme.
set -euo pipefail
umask 077
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
[ -s migrations/009_sadrzaj.sql ] && [ -s ~/mmorpg-server/mmorpg-server.pck.novi ] || { echo "NEMA NOVIH FAJLOVA"; exit 1; }
# 1) game server stoji dok traju backup, migracija i zamena .pck (niko ne prima loot ni ne predaje quest u međuvremenu)
sudo -n systemctl stop mmorpg-game
# 2) backup baze i starog .pck
mkdir -p ~/backup-009
F=~/backup-009/mmorpg-$(date +%F-%H%M).sql
mariadb-dump -h"$DB_HOST" -u"$DB_USER" --single-transaction --routines "$DB_NAME" > "$F"
[ -s "$F" ] || { echo "BACKUP PRAZAN"; exit 1; }
ls -la "$F"
cp -p ~/mmorpg-server/mmorpg-server.pck ~/backup-009/mmorpg-server.pck.pre
# 3) migracija (ispisuje tabelu predmet | pre | posle)
$M < migrations/009_sadrzaj.sql
[ "$($M -N -e "SELECT (SELECT COUNT(*) FROM items_pre_009) = 2 AND (SELECT COUNT(*) FROM quests_pre_009) = 2
  AND (SELECT COUNT(*) FROM items WHERE id IN ('cloth_trousers','leather_pants','steel_greaves','dragonscale_leggings',
       'steel_sabatons','shadow_boots','wooden_shield','tower_shield','dragon_shield')) = 9
  AND (SELECT COUNT(*) FROM quests WHERE id IN ('vucja_krzna','svila_za_krojaca','lek_od_otrova','prah_za_napitke',
       'senke_u_sumi','kraj_utvara')) = 6")" = 1 ] || { echo "MIGRACIJA NEPOTPUNA"; exit 1; }
# 4) novi .pck
mv ~/mmorpg-server/mmorpg-server.pck.novi ~/mmorpg-server/mmorpg-server.pck
# 5) start game servera, provera
sudo -n systemctl start mmorpg-game
sleep 2
systemctl is-active mmorpg-api mmorpg-game
journalctl -u mmorpg-game -n 25 --no-pager
# ROLLBACK (posebno odobrenje): stop mmorpg-game; cp ~/backup-009/mmorpg-server.pck.pre ~/mmorpg-server/mmorpg-server.pck;
#   $M < migrations/009_sadrzaj_rollback.sql; start mmorpg-game
