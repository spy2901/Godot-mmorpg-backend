-- Rollback 010: vraća cooldown_ms i quest_item pet predmeta iz items_pre_010 (samo ako se od migracije nisu menjali;
-- ispis pokazuje razliku) i briše kolone buff_tip, buff_vrednost, buff_trajanje_ms. Rezervna tabela se na kraju briše,
-- pa se ponovljen rollback odbija. Buffovi nisu u bazi, pa igrači nemaju šta da izgube.
-- Pokrenuti POSLE vraćanja starog backenda i .pck (novi players.py čita buff_* kolone).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/010_buffovi_rollback.sql
SET NAMES utf8mb4;

SELECT DATABASE() AS baza, (SELECT COUNT(*) FROM items) AS predmeta;

DELIMITER //
BEGIN NOT ATOMIC
  IF NOT EXISTS (SELECT 1 FROM information_schema.TABLES
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items_pre_010')
     OR NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items' AND COLUMN_NAME = 'buff_tip') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'items_pre_010 ili buff_tip ne postoji: 010 nije primenjena, rollback prekinut';
  END IF;
END //
DELIMITER ;

-- izmenjeno posle migracije (ostaje kako je)
SELECT i.id, 'promenjen posle 010, ostaje' AS napomena FROM items i JOIN items_pre_010 b USING (id)
WHERE (i.cooldown_ms, i.quest_item) <> (5000, 0);

START TRANSACTION;
UPDATE items i JOIN items_pre_010 b USING (id) SET i.cooldown_ms = b.cooldown_ms, i.quest_item = b.quest_item
WHERE (i.cooldown_ms, i.quest_item) = (5000, 0);
COMMIT;

ALTER TABLE items DROP COLUMN buff_tip, DROP COLUMN buff_vrednost, DROP COLUMN buff_trajanje_ms;
DROP TABLE items_pre_010;

SELECT id AS predmet, cooldown_ms, quest_item FROM items
WHERE id IN ('elixir_of_strength', 'elixir_of_defense', 'elixir_of_wisdom', 'elixir_of_luck', 'speed_potion') ORDER BY id;
