-- Rollback 007: armor i hp_bonus oklopa nazad na 0 (vrednost pre 007), kolona slot se briše.
-- Pokrenuti POSLE vraćanja starog koda (novi kod čita items.slot).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/007_oprema_rollback.sql
SET NAMES utf8mb4;

SELECT DATABASE() AS baza, COUNT(*) AS predmeta FROM items;

DELIMITER //
BEGIN NOT ATOMIC
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items' AND COLUMN_NAME = 'slot') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'items.slot ne postoji (007 nije primenjena), rollback prekinut';
  END IF;
END //
DELIMITER ;

UPDATE items SET armor = 0, hp_bonus = 0 WHERE id IN ('cloth_hood', 'leather_helmet', 'iron_helmet', 'golden_helmet', 'cloth_robe', 'shadow_cloak', 'leather_armor', 'iron_chestplate', 'dragon_scale_armor', 'iron_leggings', 'leather_boots', 'iron_boots', 'knight_shield', 'steel_shield', 'iron_gloves');
ALTER TABLE items DROP COLUMN slot;

SELECT id, tip, damage, armor, hp_bonus FROM items WHERE tip IN ('weapon', 'armor') ORDER BY tip, id;
