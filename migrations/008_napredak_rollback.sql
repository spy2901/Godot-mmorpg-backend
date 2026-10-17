-- Rollback 008: vraca SAMO kolone koje je 008 promenila, iz players_pre_008, i NE brise napredak posle migracije:
--   - lik bez napretka (nivo i XP isti kao posle 008): nivo, xp, max_xp nazad na stare
--   - lik sa napretkom (nivo ili XP promenjen posle 008): nivo, xp i max_xp ostaju
--   - svima iz rezervne tabele: max_hp, max_mana i napad_damage nazad na stare; hp i mana nazad samo ako se od
--     migracije nisu menjali (inace ostaju; maksimum ih ogranici pri ucitavanju i /save)
--   - likovi napravljeni posle 008 se ne diraju (napad 10); podrazumevani napad nazad na 250
-- Rezervna tabela se na kraju brise, pa se ponovljen rollback odbija.
-- Pokrenuti POSLE vracanja starog koda (novi kod bi statistike opet racunao iz nivoa).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/008_napredak_rollback.sql
SET NAMES utf8mb4;

SELECT DATABASE() AS baza, COUNT(*) AS likova FROM players;

DELIMITER //
BEGIN NOT ATOMIC
  IF NOT EXISTS (SELECT 1 FROM information_schema.TABLES
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'players_pre_008') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'players_pre_008 ne postoji: 008 nije primenjena, rollback prekinut';
  END IF;
END //
DELIMITER ;

SELECT b.ime, CONCAT(b.novi_level, ' -> ', p.level) AS nivo_posle_008, CONCAT(b.novi_xp, ' -> ', p.xp) AS xp_posle_008
FROM players_pre_008 b JOIN players p USING (ime)
WHERE p.level <> b.novi_level OR p.xp <> b.novi_xp ORDER BY b.ime;

START TRANSACTION;
SELECT COUNT(*) INTO @zakljucano FROM players FOR UPDATE;
-- nivo i XP prvo: WHERE poredi stanje pre rollback-a
UPDATE players p JOIN players_pre_008 b USING (ime) SET p.level = b.level, p.xp = b.xp, p.max_xp = b.max_xp
WHERE p.level = b.novi_level AND p.xp = b.novi_xp;
UPDATE players p JOIN players_pre_008 b USING (ime) SET
  p.hp = IF(p.hp = b.novi_hp, b.hp, p.hp), p.mana = IF(p.mana = b.novi_mana, b.mana, p.mana),
  p.max_hp = b.max_hp, p.max_mana = b.max_mana, p.napad_damage = b.napad_damage;
COMMIT;

ALTER TABLE players ALTER COLUMN napad_damage SET DEFAULT 250;
DROP TABLE players_pre_008;

SELECT ime, level, CONCAT(xp, '/', max_xp) AS xp, CONCAT(hp, '/', max_hp) AS hp, CONCAT(mana, '/', max_mana) AS mana,
       napad_damage FROM players ORDER BY ime;
