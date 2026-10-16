-- Oprema menja statistike: slot predmeta + armor i hp_bonus za oklop (odobrena tabela, faza 1).
-- attack = postojeća kolona damage (oružje se ne menja). iron_gloves: slot NULL = ne može da se opremi.
-- Pokrenuti PRE novog koda (stari kod radi i na ovoj šemi: SELECT * vrati i slot, niko ga ne koristi).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/007_oprema.sql
-- Rollback: 007_oprema_rollback.sql
SET NAMES utf8mb4;

-- 1) provera: prava baza, kolona slot još ne postoji, svih 30 predmeta postoji, oklop nema vrednosti -> inače prekid
SELECT DATABASE() AS baza, COUNT(*) AS predmeta FROM items;

DELIMITER //
BEGIN NOT ATOMIC
  IF EXISTS (SELECT 1 FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items' AND COLUMN_NAME = 'slot') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'items.slot vec postoji, migracija prekinuta';
  END IF;
  IF (SELECT COUNT(*) FROM items WHERE id IN ('apprentice_staff', 'arcane_staff', 'battle_axe', 'crossbow', 'dragon_staff', 'golden_sword', 'hunters_bow', 'iron_dagger', 'iron_sword', 'oak_bow', 'rusty_sword', 'shadow_dagger', 'spear', 'steel_longsword', 'war_hammer', 'cloth_hood', 'leather_helmet', 'iron_helmet', 'golden_helmet', 'cloth_robe', 'shadow_cloak', 'leather_armor', 'iron_chestplate', 'dragon_scale_armor', 'iron_leggings', 'leather_boots', 'iron_boots', 'knight_shield', 'steel_shield', 'iron_gloves')) <> 30 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'nedostaje predmet iz tabele opreme, migracija prekinuta';
  END IF;
  IF EXISTS (SELECT 1 FROM items WHERE id IN ('cloth_hood', 'leather_helmet', 'iron_helmet', 'golden_helmet', 'cloth_robe', 'shadow_cloak', 'leather_armor', 'iron_chestplate', 'dragon_scale_armor', 'iron_leggings', 'leather_boots', 'iron_boots', 'knight_shield', 'steel_shield', 'iron_gloves') AND (armor <> 0 OR hp_bonus <> 0)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'oklop vec ima armor/hp_bonus, migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) kolona (NULL = predmet se ne oprema), pa vrednosti po ID-u
ALTER TABLE items ADD COLUMN slot ENUM('head', 'chest', 'legs', 'boots', 'weapon', 'shield') NULL DEFAULT NULL AFTER tip;

START TRANSACTION;
UPDATE items SET slot = 'weapon' WHERE id IN ('apprentice_staff', 'arcane_staff', 'battle_axe', 'crossbow', 'dragon_staff', 'golden_sword', 'hunters_bow', 'iron_dagger', 'iron_sword', 'oak_bow', 'rusty_sword', 'shadow_dagger', 'spear', 'steel_longsword', 'war_hammer');
UPDATE items SET slot = 'head', armor = 2, hp_bonus = 0 WHERE id = 'cloth_hood';
UPDATE items SET slot = 'head', armor = 5, hp_bonus = 0 WHERE id = 'leather_helmet';
UPDATE items SET slot = 'head', armor = 10, hp_bonus = 0 WHERE id = 'iron_helmet';
UPDATE items SET slot = 'head', armor = 15, hp_bonus = 20 WHERE id = 'golden_helmet';
UPDATE items SET slot = 'chest', armor = 4, hp_bonus = 0 WHERE id = 'cloth_robe';
UPDATE items SET slot = 'chest', armor = 8, hp_bonus = 15 WHERE id = 'shadow_cloak';
UPDATE items SET slot = 'chest', armor = 10, hp_bonus = 0 WHERE id = 'leather_armor';
UPDATE items SET slot = 'chest', armor = 20, hp_bonus = 0 WHERE id = 'iron_chestplate';
UPDATE items SET slot = 'chest', armor = 35, hp_bonus = 50 WHERE id = 'dragon_scale_armor';
UPDATE items SET slot = 'legs', armor = 12, hp_bonus = 0 WHERE id = 'iron_leggings';
UPDATE items SET slot = 'boots', armor = 3, hp_bonus = 0 WHERE id = 'leather_boots';
UPDATE items SET slot = 'boots', armor = 6, hp_bonus = 0 WHERE id = 'iron_boots';
UPDATE items SET slot = 'shield', armor = 15, hp_bonus = 0 WHERE id = 'knight_shield';
UPDATE items SET slot = 'shield', armor = 20, hp_bonus = 10 WHERE id = 'steel_shield';
UPDATE items SET slot = NULL, armor = 5, hp_bonus = 0 WHERE id = 'iron_gloves';
COMMIT;

SELECT id, tip, slot, damage, armor, hp_bonus FROM items WHERE tip IN ('weapon', 'armor') ORDER BY tip, slot, id;
