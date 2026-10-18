-- SAMO ČITANJE: šta bi 009 promenila (ništa se ne upisuje). Pokretati pre migracije.
-- 1) predmeti koji se menjaju i novi id-jevi koji ne smeju već postojati (prazno = u redu)
SELECT id AS predmet, CONCAT('hp ', hp_efekat, ' mana ', mana_efekat, ' cd ', cooldown_ms) AS pre,
       CONCAT('hp ', IF(id = 'antidote', 20, hp_efekat), ' mana ', IF(id = 'stamina_potion', 40, mana_efekat), ' cd 5000') AS posle
FROM items WHERE id IN ('stamina_potion', 'antidote')
UNION ALL
SELECT CONCAT('quest ', id), COALESCE(sledeci_quest, 'NULL'), IF(id = 'kosti_za_supu', 'lek_od_otrova', 'kraj_utvara')
FROM quests WHERE id IN ('kosti_za_supu', 'q2');
SELECT id AS vec_postoji FROM items WHERE id IN ('cloth_trousers', 'leather_pants', 'steel_greaves', 'dragonscale_leggings',
  'steel_sabatons', 'shadow_boots', 'wooden_shield', 'tower_shield', 'dragon_shield')
UNION ALL SELECT id FROM quests WHERE id IN ('vucja_krzna', 'svila_za_krojaca', 'lek_od_otrova', 'prah_za_napitke',
  'senke_u_sumi', 'kraj_utvara');
-- 2) materijali koje novi questovi traže moraju postojati (4 reda)
SELECT id, ime FROM items WHERE id IN ('wolf_pelt', 'spider_web', 'poison_gland', 'magic_dust') ORDER BY id;
-- 3) stanje pre: broj predmeta i questova, likovi sa aktivnim questom
SELECT (SELECT COUNT(*) FROM items) AS predmeta, (SELECT COUNT(*) FROM quests) AS questova,
       (SELECT COUNT(*) FROM players WHERE aktivni_quest_id IS NOT NULL) AS aktivnih_questova;
-- 4) očekivano stanje kao provera u 009 (1 = migracija prolazi, 0 = prekid): stamina/antidote bez efekta i cd 1000,
--    kosti_za_supu i q2 bez sledećeg questa, nijedan nov id
SELECT (SELECT COUNT(*) FROM items WHERE id IN ('stamina_potion', 'antidote') AND hp_efekat = 0 AND mana_efekat = 0
          AND cooldown_ms = 1000) = 2
   AND (SELECT COUNT(*) FROM quests WHERE id IN ('kosti_za_supu', 'q2') AND sledeci_quest IS NULL) = 2 AS ocekivano_stanje;
-- 5) kosti_za_supu i q2 po liku: završen, aktivan (sa progresom) ili ništa (dobijaju sledeći quest u lancu posle 009)
SELECT p.ime AS lik, q.id AS quest,
       CASE WHEN z.quest_id IS NOT NULL THEN 'zavrsen'
            WHEN p.aktivni_quest_id = q.id THEN CONCAT('aktivan ', p.quest_progres, '/', q.kolicina)
            ELSE '-' END AS stanje
FROM players p CROSS JOIN quests q
LEFT JOIN zavrseni_questovi z ON z.player_ime = p.ime AND z.quest_id = q.id
WHERE q.id IN ('kosti_za_supu', 'q2') ORDER BY p.ime, q.id;
