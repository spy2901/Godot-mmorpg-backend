-- SAMO ČITANJE: šta bi 010 promenila (ništa se ne upisuje). Pokretati pre migracije.
-- 1) predmet | pre | posle za pet predmeta
SELECT id AS predmet, CONCAT('cd ', cooldown_ms, ' quest_item ', quest_item, ' bez buff-a') AS pre,
       CONCAT('cd 5000 quest_item 0 ', CASE id WHEN 'elixir_of_strength' THEN 'napad 20 60 s'
         WHEN 'elixir_of_defense' THEN 'oklop 30 60 s' WHEN 'elixir_of_wisdom' THEN 'xp 25 300 s'
         WHEN 'elixir_of_luck' THEN 'loot 50 300 s' ELSE 'brzina 30 20 s' END) AS posle
FROM items WHERE id IN ('elixir_of_strength', 'elixir_of_defense', 'elixir_of_wisdom', 'elixir_of_luck', 'speed_potion')
ORDER BY id;
-- 2) 010 već primenjena? (prazno = nije) i ostatak neuspelog pokušaja (items_pre_010 bez kolona se briše u migraciji)
SELECT COLUMN_NAME AS vec_postoji FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items' AND COLUMN_NAME LIKE 'buff\_%';
SELECT TABLE_NAME AS ostatak FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items_pre_010';
-- 3) očekivano stanje kao provera u 010 (1 = migracija prolazi, 0 = prekid)
SELECT (SELECT COUNT(*) FROM items WHERE id IN ('elixir_of_strength', 'elixir_of_defense', 'elixir_of_wisdom', 'elixir_of_luck',
          'speed_potion') AND tip = 'consumable' AND hp_efekat = 0 AND mana_efekat = 0 AND cooldown_ms = 1000
          AND quest_item = IF(id = 'elixir_of_luck', 1, 0)) = 5 AS ocekivano_stanje;
-- 4) collation tabele items (nove kolone ga preuzimaju) i broj predmeta
SELECT TABLE_COLLATION AS items_collation, (SELECT COUNT(*) FROM items) AS predmeta
FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items';
-- 5) ko već ima neki od pet predmeta (posle 010 postaju upotrebljivi; speed_potion i dalje ne, dok se ne uključi u igri)
SELECT p.ime AS lik, j.id AS predmet, j.kolicina
FROM players p, JSON_TABLE(p.inventory, '$[*]' COLUMNS (id VARCHAR(50) PATH '$.id', kolicina INT PATH '$.kolicina')) j
WHERE j.id IN ('elixir_of_strength', 'elixir_of_defense', 'elixir_of_wisdom', 'elixir_of_luck', 'speed_potion')
ORDER BY p.ime, j.id;
