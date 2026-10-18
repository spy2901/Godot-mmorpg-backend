-- Sadržaj 2 (odobreno, faza 2): zona 2 (nivoi 11-20). Samo items i quests; players se ne dira.
--   - 9 novih predmeta za legs, boots i shield (T1 cloth/leather/wooden u prodavnici; T3 i T4 padaju od neprijatelja
--     zone 2 sa min_nivo ili su nagrada questa, van prodavnice: Config.VAN_PRODAVNICE u igri)
--   - 6 novih questova (Hunter: vucja_krzna -> svila_za_krojaca -> senke_u_sumi -> kraj_utvara; Old Witch posle
--     kosti_za_supu: lek_od_otrova -> prah_za_napitke; kraj_utvara i posle q2)
--   - stamina_potion +40 mane, antidote +20 HP (cooldown 5 s, kao napici); ostali potrošni bez efekta ostaju
--   - lanac postojećih: kosti_za_supu.sledeci_quest = lek_od_otrova, q2.sledeci_quest = kraj_utvara (bili NULL)
-- Stare i nove vrednosti izmenjenih redova idu u items_pre_009 / quests_pre_009 (rollback ih koristi i briše).
-- ROLLBACK (009_sadrzaj_rollback.sql) uklanja SAMO ono što je ova migracija dodala ili promenila (vidi tamo).
-- Redosled: migracija pa novi .pck (stari game server ne zna nove vrste, a novi predmeti i questovi mu ne smetaju).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/009_sadrzaj.sql
SET NAMES utf8mb4;

-- 1) provera: prava baza, 009 još nije primenjena, nijedan novi id već ne postoji -> inače prekid
SELECT DATABASE() AS baza, (SELECT COUNT(*) FROM items) AS predmeta, (SELECT COUNT(*) FROM quests) AS questova;

DELIMITER //
BEGIN NOT ATOMIC
  IF EXISTS (SELECT 1 FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ('items_pre_009', 'quests_pre_009')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'items_pre_009 postoji: 009 vec primenjena, migracija prekinuta';
  END IF;
  IF EXISTS (SELECT 1 FROM items WHERE id IN ('cloth_trousers', 'leather_pants', 'steel_greaves', 'dragonscale_leggings',
               'steel_sabatons', 'shadow_boots', 'wooden_shield', 'tower_shield', 'dragon_shield'))
     OR EXISTS (SELECT 1 FROM quests WHERE id IN ('vucja_krzna', 'svila_za_krojaca', 'lek_od_otrova', 'prah_za_napitke',
               'senke_u_sumi', 'kraj_utvara')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'novi predmet ili quest vec postoji, migracija prekinuta';
  END IF;
  IF (SELECT COUNT(*) FROM items WHERE id IN ('stamina_potion', 'antidote')) <> 2
     OR (SELECT COUNT(*) FROM quests WHERE id IN ('kosti_za_supu', 'q2')) <> 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'nema predmeta ili questa koji se menja, migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) rezervne tabele: stare i nove vrednosti izmenjenih redova
CREATE TABLE items_pre_009 (
  id VARCHAR(50) NOT NULL PRIMARY KEY, hp_efekat INT NOT NULL, mana_efekat INT NOT NULL, cooldown_ms INT NOT NULL,
  novi_hp_efekat INT NOT NULL, novi_mana_efekat INT NOT NULL, novi_cooldown_ms INT NOT NULL,
  migrirano TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE quests_pre_009 (
  id VARCHAR(50) NOT NULL PRIMARY KEY, sledeci_quest VARCHAR(50) NULL, novi_sledeci_quest VARCHAR(50) NULL,
  migrirano TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

START TRANSACTION;
INSERT INTO items_pre_009 (id, hp_efekat, mana_efekat, cooldown_ms, novi_hp_efekat, novi_mana_efekat, novi_cooldown_ms)
SELECT id, hp_efekat, mana_efekat, cooldown_ms, IF(id = 'antidote', 20, hp_efekat), IF(id = 'stamina_potion', 40, mana_efekat), 5000
FROM items WHERE id IN ('stamina_potion', 'antidote') FOR UPDATE;
INSERT INTO quests_pre_009 (id, sledeci_quest, novi_sledeci_quest)
SELECT id, sledeci_quest, IF(id = 'kosti_za_supu', 'lek_od_otrova', 'kraj_utvara')
FROM quests WHERE id IN ('kosti_za_supu', 'q2') FOR UPDATE;

INSERT INTO items (id, ime, tip, slot, ikonica, stackable, max_stack, vrednost, quest_item, damage, armor, hp_bonus,
                   hp_efekat, mana_efekat, cooldown_ms) VALUES
  ('cloth_trousers', 'Cloth Trousers', 'armor', 'legs', '👖', 0, 1, 6, 0, 0, 2, 0, 0, 0, 1000),
  ('leather_pants', 'Leather Pants', 'armor', 'legs', '👖', 0, 1, 18, 0, 0, 6, 0, 0, 0, 1000),
  ('steel_greaves', 'Steel Greaves', 'armor', 'legs', '👖', 0, 1, 90, 0, 0, 18, 10, 0, 0, 1000),
  ('dragonscale_leggings', 'Dragonscale Leggings', 'armor', 'legs', '👖', 0, 1, 450, 0, 0, 26, 30, 0, 0, 1000),
  ('steel_sabatons', 'Steel Sabatons', 'armor', 'boots', '🥾', 0, 1, 70, 0, 0, 10, 5, 0, 0, 1000),
  ('shadow_boots', 'Shadow Boots', 'armor', 'boots', '🥾', 0, 1, 280, 0, 0, 14, 15, 0, 0, 1000),
  ('wooden_shield', 'Wooden Shield', 'armor', 'shield', '🛡️', 0, 1, 10, 0, 0, 6, 0, 0, 0, 1000),
  ('tower_shield', 'Tower Shield', 'armor', 'shield', '🛡️', 0, 1, 120, 0, 0, 28, 20, 0, 0, 1000),
  ('dragon_shield', 'Dragon Shield', 'armor', 'shield', '🛡️', 0, 1, 520, 0, 0, 36, 40, 0, 0, 1000);

INSERT INTO quests (id, naziv, opis, tip, cilj, kolicina, nagrada_gold, nagrada_xp, nagrada_item, sledeci_quest) VALUES
  ('vucja_krzna', 'Wolf Pelts', 'Wolves have come down from the hills east of the village.\n\nBring me 6 wolf pelts.',
   'fetch', 'wolf_pelt', 6, 150, 1200, NULL, 'svila_za_krojaca'),
  ('svila_za_krojaca', 'Silk for the Tailor', 'The tailor needs strong thread.\n\nBring 8 spider webs from the eastern woods.',
   'fetch', 'spider_web', 8, 200, 1500, 'steel_sabatons', 'senke_u_sumi'),
  ('senke_u_sumi', 'Shadows in the Forest', 'Something cold moves between the trees at night.\n\nKill 8 wraiths.',
   'kill', 'wraith', 8, 300, 2500, 'tower_shield', 'kraj_utvara'),
  ('kraj_utvara', 'The End of the Wraiths', 'The strongest wraiths still guard the far end of the forest.\n\nKill 3 more wraiths.',
   'kill', 'wraith', 3, 500, 3000, 'dragon_shield', NULL),
  ('lek_od_otrova', 'A Cure for Venom', 'Spider venom can be turned into a cure.\n\nBring me 4 poison glands.',
   'fetch', 'poison_gland', 4, 150, 1400, 'antidote', 'prah_za_napitke'),
  ('prah_za_napitke', 'Dust for Potions', 'Wraiths leave a strange dust behind.\n\nBring me 5 pinches of magic dust.',
   'fetch', 'magic_dust', 5, 250, 2200, NULL, NULL);

UPDATE items i JOIN items_pre_009 b USING (id) SET
  i.hp_efekat = b.novi_hp_efekat, i.mana_efekat = b.novi_mana_efekat, i.cooldown_ms = b.novi_cooldown_ms;
UPDATE quests q JOIN quests_pre_009 b USING (id) SET q.sledeci_quest = b.novi_sledeci_quest;
COMMIT;

SELECT id AS predmet, CONCAT('hp ', hp_efekat, ' mana ', mana_efekat, ' cd ', cooldown_ms) AS pre,
       CONCAT('hp ', novi_hp_efekat, ' mana ', novi_mana_efekat, ' cd ', novi_cooldown_ms) AS posle FROM items_pre_009
UNION ALL
SELECT id, '(nema)', CONCAT(slot, ' armor ', armor, ' max_hp +', hp_bonus, ' vrednost ', vrednost) FROM items
WHERE id IN ('cloth_trousers', 'leather_pants', 'steel_greaves', 'dragonscale_leggings', 'steel_sabatons', 'shadow_boots',
             'wooden_shield', 'tower_shield', 'dragon_shield')
UNION ALL
SELECT CONCAT('quest ', id), COALESCE(sledeci_quest, 'NULL'), novi_sledeci_quest FROM quests_pre_009;
