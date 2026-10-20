-- Buffovi (odobreno, faza 2): privremeni efekti potrošnih predmeta. Samo items; players se ne dira (buffovi su samo u
-- memoriji game servera: smrt, odjava i restart ih brišu).
--   - nove kolone: buff_tip (napad | oklop | xp | loot | brzina), buff_vrednost (procenat; za oklop apsolutno),
--     buff_trajanje_ms
--   - elixir_of_strength napad +20% 60 s, elixir_of_defense oklop +30 60 s, elixir_of_wisdom xp +25% 5 min,
--     elixir_of_luck loot +50% 5 min, speed_potion brzina +30% 20 s; cooldown 5 s za svih pet
--   - elixir_of_luck: quest_item 1 -> 0 (do sada nije mogao da se kupi ni dobije)
-- Stare vrednosti izmenjenih redova idu u items_pre_010, napravljenu PRE ALTER-a (bez novih kolona; CREATE ... AS SELECT
-- preuzima tipove i collation iz items). Nove kolone dobijaju podrazumevani charset/collation tabele items (na Pi-ju
-- utf8mb3_uca1400_ai_ci), kao ostale tekstualne kolone.
-- "Već primenjena" = kolona buff_tip postoji. Rezervna tabela bez kolone buff_tip = ostatak neuspelog pokušaja: briše se.
-- ROLLBACK (010_buffovi_rollback.sql) vraća stare vrednosti (ako se od migracije nisu menjale) i briše kolone.
-- Redosled: migracija, pa novi backend (players.py čita buff_* kolone), pa novi .pck.
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/010_buffovi.sql
SET NAMES utf8mb4;

-- 1) provera: prava baza, 010 još nije primenjena, pet predmeta u očekivanom starom stanju -> inače prekid
SELECT DATABASE() AS baza, (SELECT COUNT(*) FROM items) AS predmeta;

DELIMITER //
BEGIN NOT ATOMIC
  IF EXISTS (SELECT 1 FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items' AND COLUMN_NAME = 'buff_tip') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'kolona buff_tip postoji: 010 vec primenjena, migracija prekinuta';
  END IF;
  -- bez efekta, cooldown 1000; luck je jedini quest_item
  IF (SELECT COUNT(*) FROM items WHERE id IN ('elixir_of_strength', 'elixir_of_defense', 'elixir_of_wisdom', 'elixir_of_luck',
        'speed_potion') AND tip = 'consumable' AND hp_efekat = 0 AND mana_efekat = 0 AND cooldown_ms = 1000
        AND quest_item = IF(id = 'elixir_of_luck', 1, 0)) <> 5 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'elixir_* ili speed_potion nisu u ocekivanom stanju, migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) rezervna tabela pre ALTER-a: stare vrednosti pet predmeta
DROP TABLE IF EXISTS items_pre_010; -- samo ostatak neuspelog pokušaja: 010 nije primenjena (provera gore)
CREATE TABLE items_pre_010 AS SELECT id, quest_item, cooldown_ms FROM items
WHERE id IN ('elixir_of_strength', 'elixir_of_defense', 'elixir_of_wisdom', 'elixir_of_luck', 'speed_potion');
ALTER TABLE items_pre_010 ADD PRIMARY KEY (id), ADD COLUMN migrirano TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- 3) kolone (ALTER sam potvrđuje; posle njega 010 važi kao primenjena)
ALTER TABLE items
  ADD COLUMN buff_tip VARCHAR(16) NULL DEFAULT NULL,
  ADD COLUMN buff_vrednost INT NOT NULL DEFAULT 0,
  ADD COLUMN buff_trajanje_ms INT NOT NULL DEFAULT 0;

-- 4) vrednosti, samo iz očekivanog stanja (provereno gore, i ovde u WHERE)
START TRANSACTION;
UPDATE items i JOIN items_pre_010 b USING (id) SET
  i.buff_tip = CASE i.id WHEN 'elixir_of_strength' THEN 'napad' WHEN 'elixir_of_defense' THEN 'oklop'
    WHEN 'elixir_of_wisdom' THEN 'xp' WHEN 'elixir_of_luck' THEN 'loot' ELSE 'brzina' END,
  i.buff_vrednost = CASE i.id WHEN 'elixir_of_strength' THEN 20 WHEN 'elixir_of_defense' THEN 30
    WHEN 'elixir_of_wisdom' THEN 25 WHEN 'elixir_of_luck' THEN 50 ELSE 30 END,
  i.buff_trajanje_ms = CASE i.id WHEN 'elixir_of_wisdom' THEN 300000 WHEN 'elixir_of_luck' THEN 300000
    WHEN 'speed_potion' THEN 20000 ELSE 60000 END,
  i.cooldown_ms = 5000,
  i.quest_item = 0
WHERE i.cooldown_ms = 1000 AND i.hp_efekat = 0 AND i.mana_efekat = 0 AND i.buff_tip IS NULL;
COMMIT;

SELECT b.id AS predmet, CONCAT('cd ', b.cooldown_ms, ' quest_item ', b.quest_item, ' bez buff-a') AS pre,
       CONCAT('cd ', i.cooldown_ms, ' quest_item ', i.quest_item, ' ', i.buff_tip, ' ', i.buff_vrednost, ' ',
              i.buff_trajanje_ms DIV 1000, ' s') AS posle
FROM items_pre_010 b JOIN items i USING (id) ORDER BY b.id;
