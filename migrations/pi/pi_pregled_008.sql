-- SAMO ČITANJE: kako bi 008 promenila svakog lika (ništa se ne upisuje)
SELECT ime AS lik, level AS nivo, napad_damage AS napad,
  CONCAT('Lv', level, ' xp ', xp, '/', max_xp, ' hp ', hp, '/', max_hp, ' mana ', mana, '/', max_mana, ' napad ', napad_damage) AS pre,
  CONCAT('Lv', L, ' xp ', IF(L = 20, 0, LEAST(GREATEST(xp, 0), mx - 1)), '/', mx,
         ' hp ', LEAST(hp, 100 + 15 * (L - 1) + bonus), '/', 100 + 15 * (L - 1),
         ' mana ', LEAST(mana, 100 + 10 * (L - 1)), '/', 100 + 10 * (L - 1), ' napad ', 10 + 2 * (L - 1)) AS posle
FROM (SELECT p.*, LEAST(GREATEST(level, 1), 20) AS L,
        IF(LEAST(GREATEST(level, 1), 20) = 20, 0, 25 * POW(LEAST(GREATEST(level, 1), 20), 2) + 75 * LEAST(GREATEST(level, 1), 20)) AS mx,
        (SELECT COALESCE(SUM(i.hp_bonus), 0) FROM items i WHERE i.id IN (JSON_VALUE(p.equipment, '$.head'),
          JSON_VALUE(p.equipment, '$.chest'), JSON_VALUE(p.equipment, '$.legs'), JSON_VALUE(p.equipment, '$.boots'),
          JSON_VALUE(p.equipment, '$.weapon'), JSON_VALUE(p.equipment, '$.shield'))) AS bonus
      FROM players p) x
ORDER BY ime;
