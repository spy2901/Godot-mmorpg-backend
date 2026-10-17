-- Napredak lika (odobreno, faza 2): statistike iz nivoa kao napredak.statistike_za_nivo, maksimalni nivo 20,
-- osnovni napad 10 umesto 250 (i kao podrazumevana vrednost kolone, za nove likove).
--   max_xp = 25*L^2 + 75*L (0 na nivou 20), max_hp = 100 + 15*(L-1), max_mana = 100 + 10*(L-1), napad = 10 + 2*(L-1)
--   nivo > 20 -> 20 (xp 0, max_xp 0); nivo < 1 -> 1
--   XP veci ili jednak novom max_xp -> max_xp - 1: migracija ne daje nivoe (nema level-up-a ni punjenja HP-a
--     bez igraca), a lik je jedno ubistvo od sledeceg nivoa. Starim krivom XP ispod nivoa 10 nikad ne prelazi novi max_xp.
--   hp -> najvise novi max_hp + hp_bonus opremljenih predmeta (kao /save), mana -> najvise novi max_mana
-- Stare i nove vrednosti promenjenih kolona idu u rezervnu tabelu players_pre_008 (rollback ih koristi i brise je).
-- ROLLBACK (008_napredak_rollback.sql) vraca SAMO kolone koje je ova migracija promenila i NE brise napredak
-- stecen posle migracije: lik ciji su nivo ili XP promenjeni posle 008 zadrzava nivo, XP i max_xp; max_hp, max_mana
-- i napad_damage dobijaju stare vrednosti; hp i mana se vracaju samo ako se od migracije nisu menjali.
-- Redosled: migracija pa novi kod (stari kod na novoj semi radi, samo bi level-up opet mnozio vrednosti).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/008_napredak.sql
SET NAMES utf8mb4;

-- 1) provera: prava baza, 008 jos nije primenjena -> inace prekid
SELECT DATABASE() AS baza, COUNT(*) AS likova, MAX(level) AS najvisi_nivo FROM players;

DELIMITER //
BEGIN NOT ATOMIC
  IF EXISTS (SELECT 1 FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'players_pre_008') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'players_pre_008 postoji: 008 vec primenjena, migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) rezervna tabela: stare vrednosti (level..mana) i nove (novi_*)
CREATE TABLE players_pre_008 (
  ime VARCHAR(50) NOT NULL PRIMARY KEY,
  level INT NOT NULL, xp INT NOT NULL, max_xp INT NOT NULL, max_hp INT NOT NULL, max_mana INT NOT NULL,
  napad_damage INT NOT NULL, hp INT NOT NULL, mana INT NOT NULL,
  novi_level INT NOT NULL, novi_xp INT NULL, novi_max_xp INT NULL, novi_max_hp INT NULL, novi_max_mana INT NULL,
  novi_napad_damage INT NULL, novi_hp INT NULL, novi_mana INT NULL,
  migrirano TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

START TRANSACTION;
INSERT INTO players_pre_008 (ime, level, xp, max_xp, max_hp, max_mana, napad_damage, hp, mana, novi_level)
SELECT ime, level, xp, max_xp, max_hp, max_mana, napad_damage, hp, mana, LEAST(GREATEST(level, 1), 20)
FROM players FOR UPDATE;

UPDATE players_pre_008 SET
  novi_max_xp = IF(novi_level = 20, 0, 25 * novi_level * novi_level + 75 * novi_level),
  novi_max_hp = 100 + 15 * (novi_level - 1),
  novi_max_mana = 100 + 10 * (novi_level - 1),
  novi_napad_damage = 10 + 2 * (novi_level - 1);

UPDATE players_pre_008 b JOIN players p USING (ime) SET
  b.novi_xp = IF(b.novi_max_xp = 0, 0, LEAST(GREATEST(b.xp, 0), b.novi_max_xp - 1)),
  b.novi_mana = LEAST(b.mana, b.novi_max_mana),
  b.novi_hp = LEAST(b.hp, b.novi_max_hp + (
    SELECT COALESCE(SUM(i.hp_bonus), 0) FROM items i
    WHERE i.id IN (JSON_VALUE(p.equipment, '$.head'), JSON_VALUE(p.equipment, '$.chest'),
                   JSON_VALUE(p.equipment, '$.legs'), JSON_VALUE(p.equipment, '$.boots'),
                   JSON_VALUE(p.equipment, '$.weapon'), JSON_VALUE(p.equipment, '$.shield'))));

UPDATE players p JOIN players_pre_008 b USING (ime) SET
  p.level = b.novi_level, p.xp = b.novi_xp, p.max_xp = b.novi_max_xp, p.max_hp = b.novi_max_hp,
  p.max_mana = b.novi_max_mana, p.napad_damage = b.novi_napad_damage, p.hp = b.novi_hp, p.mana = b.novi_mana;
COMMIT;

-- 3) novi likovi pocinju sa osnovnim napadom 10 (ostale podrazumevane vrednosti su vec nivo 1)
ALTER TABLE players ALTER COLUMN napad_damage SET DEFAULT 10;

SELECT b.ime, b.level AS nivo_pre, p.level AS nivo, CONCAT(b.xp, '/', b.max_xp) AS xp_pre, CONCAT(p.xp, '/', p.max_xp) AS xp,
       CONCAT(b.hp, '/', b.max_hp) AS hp_pre, CONCAT(p.hp, '/', p.max_hp) AS hp,
       CONCAT(b.mana, '/', b.max_mana) AS mana_pre, CONCAT(p.mana, '/', p.max_mana) AS mana,
       b.napad_damage AS napad_pre, p.napad_damage AS napad
FROM players_pre_008 b JOIN players p USING (ime) ORDER BY b.ime;
