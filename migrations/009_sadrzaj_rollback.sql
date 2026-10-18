-- Rollback 009: uklanja SAMO ono što je 009 dodala ili promenila, iz items_pre_009 / quests_pre_009:
--   - 9 novih predmeta i 6 novih questova se brišu (predmeti koje igrači već imaju ostaju u njihovom inventaru kao id
--     bez reda u items: igra ih preskače; završeni questovi u zavrseni_questovi ostaju, ne smetaju)
--   - igrači kojima je aktivan jedan od obrisanih questova ostaju bez aktivnog questa (inače ne mogu da ga predaju)
--   - stamina_potion i antidote dobijaju stare efekte, a kosti_za_supu i q2 stari sledeci_quest, samo ako se od
--     migracije nisu menjali (inače ostaju; ispis pokazuje razliku)
-- Rezervne tabele se na kraju brišu, pa se ponovljen rollback odbija.
-- Pokrenuti POSLE vraćanja starog .pck (novi game server bi tražio obrisane questove i predmete).
-- Pokretati: mariadb --default-character-set=utf8mb4 mmorpg < migrations/009_sadrzaj_rollback.sql
SET NAMES utf8mb4;

SELECT DATABASE() AS baza, (SELECT COUNT(*) FROM items) AS predmeta, (SELECT COUNT(*) FROM quests) AS questova;

DELIMITER //
BEGIN NOT ATOMIC
  IF NOT EXISTS (SELECT 1 FROM information_schema.TABLES
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'items_pre_009') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'items_pre_009 ne postoji: 009 nije primenjena, rollback prekinut';
  END IF;
END //
DELIMITER ;

-- izmenjeno posle migracije (ostaje kako je)
SELECT i.id, 'promenjen posle 009, ostaje' AS napomena FROM items i JOIN items_pre_009 b USING (id)
WHERE (i.hp_efekat, i.mana_efekat, i.cooldown_ms) <> (b.novi_hp_efekat, b.novi_mana_efekat, b.novi_cooldown_ms)
UNION ALL
SELECT q.id, 'promenjen posle 009, ostaje' FROM quests q JOIN quests_pre_009 b USING (id)
WHERE NOT (q.sledeci_quest <=> b.novi_sledeci_quest);

START TRANSACTION;
UPDATE players SET aktivni_quest_id = NULL, quest_progres = 0
WHERE aktivni_quest_id IN ('vucja_krzna', 'svila_za_krojaca', 'lek_od_otrova', 'prah_za_napitke', 'senke_u_sumi', 'kraj_utvara');
UPDATE items i JOIN items_pre_009 b USING (id) SET
  i.hp_efekat = b.hp_efekat, i.mana_efekat = b.mana_efekat, i.cooldown_ms = b.cooldown_ms
WHERE (i.hp_efekat, i.mana_efekat, i.cooldown_ms) = (b.novi_hp_efekat, b.novi_mana_efekat, b.novi_cooldown_ms);
UPDATE quests q JOIN quests_pre_009 b USING (id) SET q.sledeci_quest = b.sledeci_quest
WHERE q.sledeci_quest <=> b.novi_sledeci_quest;
DELETE FROM quests WHERE id IN ('vucja_krzna', 'svila_za_krojaca', 'lek_od_otrova', 'prah_za_napitke', 'senke_u_sumi', 'kraj_utvara');
DELETE FROM items WHERE id IN ('cloth_trousers', 'leather_pants', 'steel_greaves', 'dragonscale_leggings', 'steel_sabatons',
                               'shadow_boots', 'wooden_shield', 'tower_shield', 'dragon_shield');
COMMIT;

DROP TABLE items_pre_009;
DROP TABLE quests_pre_009;

SELECT (SELECT COUNT(*) FROM items) AS predmeta, (SELECT COUNT(*) FROM quests) AS questova;
