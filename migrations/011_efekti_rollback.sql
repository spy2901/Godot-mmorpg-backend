-- Rollback 011: vraća quest_item, cooldown_ms i buff_* tri predmeta iz items_pre_011 (samo ako se od migracije nisu
-- menjali; ispis pokazuje razliku). Rezervna tabela se na kraju briše, pa se ponovljen rollback odbija.
-- Pokrenuti POSLE vraćanja starog .pck (novi game server bi bez buff-a samo izgubio efekte; stari ih ne zna).
-- Buffovi i otrov nisu u bazi, pa igrači gube samo aktivne efekte (kao restart).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/011_efekti_rollback.sql
SET NAMES utf8mb4;

SELECT DATABASE() AS baza, (SELECT COUNT(*) FROM items) AS predmeta;

DELIMITER //
BEGIN NOT ATOMIC
  IF NOT EXISTS (SELECT 1 FROM information_schema.TABLES
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items_pre_011') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'items_pre_011 ne postoji: 011 nije primenjena, rollback prekinut';
  END IF;
END //
DELIMITER ;

-- izmenjeno posle migracije (ostaje kako je)
SELECT i.id, 'promenjen posle 011, ostaje' AS napomena FROM items i JOIN items_pre_011 b USING (id)
WHERE (i.id, i.quest_item, i.cooldown_ms, i.buff_tip, i.buff_vrednost, i.buff_trajanje_ms) NOT IN (
  ('invisibility_potion', 0, 60000, 'nevidljivost', 1, 20000), ('resurrection_potion', 0, 5000, 'vaskrsenje', 50, 600000),
  ('antidote', 0, 5000, 'protivotrov', 1, 30000));

START TRANSACTION;
UPDATE items i JOIN items_pre_011 b USING (id) SET i.quest_item = b.quest_item, i.cooldown_ms = b.cooldown_ms,
  i.buff_tip = b.buff_tip, i.buff_vrednost = b.buff_vrednost, i.buff_trajanje_ms = b.buff_trajanje_ms
WHERE (i.id, i.quest_item, i.cooldown_ms, i.buff_tip, i.buff_vrednost, i.buff_trajanje_ms) IN (
  ('invisibility_potion', 0, 60000, 'nevidljivost', 1, 20000), ('resurrection_potion', 0, 5000, 'vaskrsenje', 50, 600000),
  ('antidote', 0, 5000, 'protivotrov', 1, 30000));
COMMIT;

DROP TABLE items_pre_011;

SELECT id AS predmet, quest_item, cooldown_ms, buff_tip, buff_vrednost, buff_trajanje_ms FROM items
WHERE id IN ('invisibility_potion', 'resurrection_potion', 'antidote') ORDER BY id;
