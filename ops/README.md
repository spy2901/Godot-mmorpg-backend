# ops: backup baze i trajni journal na Pi-ju

| Fajl | Gde radi | Šta radi |
|---|---|---|
| `mmorpg_backup.sh` | Pi, `~/mmorpg-backend/ops/` | dump baze `mmorpg` (sessions samo šema) u `~/mmorpg-backups/daily`, nedeljom i `weekly` + config arhiva; 14 dnevnih, 8 nedeljnih; `LAST_OK` |
| `systemd/mmorpg-backup.{service,timer}` | Pi, `/etc/systemd/system/` | pokreće skriptu svaki dan u 04:15 UTC (`Persistent=true`) |
| `journald/90-persistent.conf` | Pi, `/etc/systemd/journald.conf.d/` | trajni journal, najviše 200M (nadjačava RPi `Storage=volatile`) |
| `pull_backup_mac.sh` | Mac | povlači `~/mmorpg-backups` na Mac (700), javlja kad je `LAST_OK` stariji od 2 dana, proverava oporavak |
| `verify_restore.sh` | Mac | vraća dump na privremenu MariaDB 11.8 i poredi broj redova po tabeli sa manifestom |
| `launchd/local.mmorpg-backup-pull.plist` | Mac | `pull_backup_mac.sh` svaki dan u 09:00 |

Greške: `journalctl -u mmorpg-backup` i `systemctl --failed` na Pi-ju; `~/mmorpg-backups/pull.log` i notifikacija na Mac-u.

Sadržaj backup-a: `daily/mmorpg-DAN.sql.zst` + `.manifest` (redova po tabeli pre dump-a);
`config/config-DAN.tar.zst` (backend bez venv-a sa `.env`, `~/mmorpg-game.env`, `.pck`, `mmorpg-server.sh`, unit fajlovi,
journald konfiguracija, `SHOW GRANTS`). Sadrži tajne: prava 600, na Mac-u u `~/mmorpg-backups` (700, FileVault uključen).
`mmorpg-server.arm64` se ne čuva (Godot šablon, ponovo se izveze).

## Vraćanje baze iz backup-a (Pi)

```bash
sudo systemctl stop mmorpg-game
cd ~/mmorpg-backend; set -a; . ./.env; set +a; export MYSQL_PWD="$DB_PASSWORD"
zstd -dc ~/mmorpg-backups/daily/mmorpg-DAN.sql.zst | mariadb -h"$DB_HOST" -u"$DB_USER" "$DB_NAME"
sudo systemctl start mmorpg-game
```

Tabela `sessions` se vraća prazna: igrači se ponovo prijave. Config: `tar -x --zstd -f config-DAN.tar.zst -C /tmp/vrati`, pa
fajlove ručno na mesto (`etc/...` sa sudo).

## Vraćanje izmena na Pi-ju

| Izmena | Vraćanje |
|---|---|
| `chmod 600 ~/mmorpg-backend/.env` (bilo 664) | `chmod 664 ~/mmorpg-backend/.env` |
| `/etc/systemd/journald.conf.d/90-persistent.conf` | `sudo rm` fajla, `sudo systemctl restart systemd-journald` (journal opet u RAM-u; stari zapisi ostaju u `/var/log/journal/<machine-id>` dok se ne obrišu) |
| `mmorpg-backup.timer` + `.service` | `sudo systemctl disable --now mmorpg-backup.timer`, `sudo rm /etc/systemd/system/mmorpg-backup.{service,timer}`, `sudo systemctl daemon-reload` |
| `~/mmorpg-backend/ops/mmorpg_backup.sh` | `rm -r ~/mmorpg-backend/ops` |
| `~/mmorpg-backups/` | `rm -r ~/mmorpg-backups` (briše backup-ove; prvo ih povuci) |

Postojeći cron (DDNS, `~/scripts/backup_db.sh` za travel_planner) i ručni backup-ovi (`~/backup-0*`, `~/mmorpg_pre_007.sql`)
se ne diraju.
