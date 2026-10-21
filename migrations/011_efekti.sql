-- Efekti (odobreno, faza 2): invisibility_potion, resurrection_potion i antidote dobijaju buff. Samo UPDATE tri reda u
-- items, bez novih kolona (buff_* iz 010); players se ne dira (buffovi i otrov su samo u memoriji game servera).
--   - invisibility_potion: nevidljivost 20 s, cooldown 60 s, quest_item 1 -> 0 (u prodavnici, 150 zlata)
--   - resurrection_potion: vaskrsenje 50% max HP, 10 min ili do prve smrti, cooldown 5 s, quest_item 1 -> 0 (500 zlata)
--   - antidote: protivotrov 30 s (skida otrov pauka i ne da novi), +20 HP i cooldown 5 s ostaju
--   vrednost 1 za nevidljivost i protivotrov je samo oznaka (buff() > 0)
-- Stare vrednosti tri reda idu u items_pre_011, napravljenu PRE izmene (CREATE ... AS SELECT preuzima tipove i collation
-- iz items, na Pi-ju utf8mb3_uca1400_ai_ci).
-- "Već primenjena" = sva tri reda u novom stanju. Rezervna tabela dok redovi nisu izmenjeni = ostatak neuspelog
-- pokušaja: briše se i pravi ponovo.
-- ROLLBACK (011_efekti_rollback.sql) vraća stare vrednosti (ako se od migracije nisu menjale) i briše items_pre_011.
-- Redosled: migracija, pa novi .pck (stari game server ne zna nove tipove: invisibility i resurrection odbija pre
-- trošenja, antidote i dalje leči 20 HP). Backend se ne menja.
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/011_efekti.sql
SET NAMES utf8mb4;

-- 1) provera: prava baza, 010 primenjena, 011 još nije, tri predmeta u očekivanom starom stanju -> inače prekid
SELECT DATABASE() AS baza, (SELECT COUNT(*) FROM items) AS predmeta;

DELIMITER //
BEGIN NOT ATOMIC
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items' AND COLUMN_NAME = 'buff_tip') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'kolona buff_tip ne postoji: 010 nije primenjena, migracija prekinuta';
  END IF;
  IF (SELECT COUNT(*) FROM items WHERE (id, buff_tip) IN (('invisibility_potion', 'nevidljivost'),
        ('resurrection_potion', 'vaskrsenje'), ('antidote', 'protivotrov'))) = 3 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'buff_tip vec postavljen: 011 vec primenjena, migracija prekinuta';
  END IF;
  -- staro: bez buff-a; napici bez efekta, cooldown 1000, quest_item; antidote +20 HP, cooldown 5000
  IF (SELECT COUNT(*) FROM items WHERE tip = 'consumable' AND buff_tip IS NULL AND buff_vrednost = 0 AND buff_trajanje_ms = 0
        AND mana_efekat = 0 AND (
          (id IN ('invisibility_potion', 'resurrection_potion') AND hp_efekat = 0 AND cooldown_ms = 1000 AND quest_item = 1)
          OR (id = 'antidote' AND hp_efekat = 20 AND cooldown_ms = 5000 AND quest_item = 0))) <> 3 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'invisibility_potion, resurrection_potion ili antidote nisu u ocekivanom stanju, migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) rezervna tabela pre izmene: stare vrednosti tri reda
DROP TABLE IF EXISTS items_pre_011; -- samo ostatak neuspelog pokušaja: redovi su u starom stanju (provera gore)
CREATE TABLE items_pre_011 AS SELECT id, quest_item, cooldown_ms, buff_tip, buff_vrednost, buff_trajanje_ms FROM items
WHERE id IN ('invisibility_potion', 'resurrection_potion', 'antidote');
ALTER TABLE items_pre_011 ADD PRIMARY KEY (id), ADD COLUMN migrirano TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- 3) vrednosti, samo iz očekivanog stanja (provereno gore, i ovde u WHERE)
START TRANSACTION;
UPDATE items i JOIN items_pre_011 b USING (id) SET
  i.buff_tip = CASE i.id WHEN 'invisibility_potion' THEN 'nevidljivost' WHEN 'resurrection_potion' THEN 'vaskrsenje'
    ELSE 'protivotrov' END,
  i.buff_vrednost = IF(i.id = 'resurrection_potion', 50, 1),
  i.buff_trajanje_ms = CASE i.id WHEN 'invisibility_potion' THEN 20000 WHEN 'resurrection_potion' THEN 600000 ELSE 30000 END,
  i.cooldown_ms = IF(i.id = 'invisibility_potion', 60000, 5000),
  i.quest_item = 0
WHERE i.buff_tip IS NULL;
COMMIT;

SELECT b.id AS predmet, CONCAT('cd ', b.cooldown_ms, ' quest_item ', b.quest_item, ' bez buff-a') AS pre,
       CONCAT('cd ', i.cooldown_ms, ' quest_item ', i.quest_item, ' ', i.buff_tip, ' ', i.buff_vrednost, ' ',
              i.buff_trajanje_ms DIV 1000, ' s') AS posle
FROM items_pre_011 b JOIN items i USING (id) ORDER BY b.id;
