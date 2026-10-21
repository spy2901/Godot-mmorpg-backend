-- SAMO ČITANJE: šta bi 011 promenila (ništa se ne upisuje). Pokretati pre migracije.
-- 1) predmet | pre | posle za tri predmeta
SELECT id AS predmet, CONCAT('cd ', cooldown_ms, ' quest_item ', quest_item, ' hp ', hp_efekat, ' ',
         COALESCE(buff_tip, 'bez buff-a')) AS pre,
       CONCAT('cd ', IF(id = 'invisibility_potion', 60000, 5000), ' quest_item 0 hp ', hp_efekat, ' ', CASE id
         WHEN 'invisibility_potion' THEN 'nevidljivost 1 20 s' WHEN 'resurrection_potion' THEN 'vaskrsenje 50 600 s'
         ELSE 'protivotrov 1 30 s' END) AS posle
FROM items WHERE id IN ('invisibility_potion', 'resurrection_potion', 'antidote') ORDER BY id;
-- 2) 011 već primenjena? (prazno = nije) i ostatak neuspelog pokušaja (items_pre_011 se briše u migraciji)
SELECT id AS vec_primenjeno, buff_tip FROM items
WHERE id IN ('invisibility_potion', 'resurrection_potion', 'antidote') AND buff_tip IS NOT NULL;
SELECT TABLE_NAME AS ostatak FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items_pre_011';
-- 3) očekivano stanje kao provera u 011 (1 = migracija prolazi, 0 = prekid)
SELECT (SELECT COUNT(*) FROM items WHERE tip = 'consumable' AND buff_tip IS NULL AND buff_vrednost = 0 AND buff_trajanje_ms = 0
          AND mana_efekat = 0 AND (
            (id IN ('invisibility_potion', 'resurrection_potion') AND hp_efekat = 0 AND cooldown_ms = 1000 AND quest_item = 1)
            OR (id = 'antidote' AND hp_efekat = 20 AND cooldown_ms = 5000 AND quest_item = 0))) = 3 AS ocekivano_stanje;
-- 4) ko već ima neki od tri predmeta (posle 011 + novi .pck postaju upotrebljivi)
SELECT p.ime AS lik, j.id AS predmet, j.kolicina
FROM players p, JSON_TABLE(p.inventory, '$[*]' COLUMNS (id VARCHAR(50) PATH '$.id', kolicina INT PATH '$.kolicina')) j
WHERE j.id IN ('invisibility_potion', 'resurrection_potion', 'antidote')
ORDER BY p.ime, j.id;
