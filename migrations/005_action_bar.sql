-- Raspored action bara po liku: JSON lista od 10 slotova (item_id ili null).
-- NULL u koloni = lik jos nema sacuvan raspored; game server ga tada popuni iz inventara i upise.
-- Pokrenuti PRE novog koda (stari kod radi i na ovoj semi: SELECT * je vrati, niko je ne pise).
-- Rollback: 005_action_bar_rollback.sql

-- 1) provera: prava baza, tabela players postoji, kolona jos ne postoji -> inace prekid pre ALTER-a
SELECT DATABASE() AS baza, COUNT(*) AS likova FROM players;

DELIMITER //
BEGIN NOT ATOMIC
  IF EXISTS (SELECT 1 FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'players' AND COLUMN_NAME = 'action_bar') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'players.action_bar vec postoji, migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) JSON u MariaDB = LONGTEXT sa CHECK (JSON_VALID): neispravan JSON baza odbija sama
ALTER TABLE players ADD COLUMN action_bar JSON NULL DEFAULT NULL;

SHOW CREATE TABLE players;
