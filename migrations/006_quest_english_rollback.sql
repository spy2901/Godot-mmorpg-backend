-- Rollback 006: vraća srpski naziv i opis 6 questova (bajt-po-bajt kao pre 006).
-- Menja samo naziv i opis po ID-u; ID-evi, ciljevi i nagrade ostaju. Pokretati sa utf8mb4:
--   mariadb --default-character-set=utf8mb4 mmorpg < migrations/006_quest_english_rollback.sql
-- Bez backslash escape-a u stringovima (prelom strane u opisu = CHAR(10)), radi i uz NO_BACKSLASH_ESCAPES.
SET NAMES utf8mb4;

-- 1) provera: prava baza i svih 6 questova ima tačno očekivani tekst (bajt-po-bajt) -> inače prekid pre izmene
SELECT DATABASE() AS baza, COUNT(*) AS questova FROM quests;

DELIMITER //
BEGIN NOT ATOMIC
  IF (SELECT COUNT(*) FROM quests
      WHERE (id = 'goblin_killer' AND BINARY naziv = BINARY 'Goblin Trouble' AND BINARY opis = BINARY 'Goblins are raiding the area. Kill 5 goblins and come back for your reward.')
     OR (id = 'kosti_za_supu' AND BINARY naziv = BINARY 'Bones for Soup' AND BINARY opis = BINARY 'Bring 5 skeleton ribs to the old witch.')
     OR (id = 'q2' AND BINARY naziv = BINARY 'Goblin Ears' AND BINARY opis = BINARY CONCAT('I need proof that you really killed them.', CHAR(10 USING utf8mb4), '', CHAR(10 USING utf8mb4), 'Bring me 5 goblin ears.'))
     OR (id = 'skeleton_hunter' AND BINARY naziv = BINARY 'Rise of the Dead' AND BINARY opis = BINARY 'Something is raising the dead. Kill 5 skeletons to find out more.')
     OR (id = 'skupljac_oruzja' AND BINARY naziv = BINARY 'Weapon Collector' AND BINARY opis = BINARY 'Bring 2 Iron Swords to the local blacksmith.')
     OR (id = 'troll_slayer' AND BINARY naziv = BINARY 'Troll Hunt' AND BINARY opis = BINARY 'Kill 3 trolls that are blocking the road to the town.')) <> 6 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'quests: tekst nije ocekivani engleski (006 nije primenjena ili je tekst menjan), rollback prekinut';
  END IF;
END //
DELIMITER ;

-- 2) izmena u jednoj transakciji
START TRANSACTION;
UPDATE quests SET naziv = 'Goblinski problem',
    opis = 'Goblini haraju okolicom. Ubij 5 goblina i vrati se po nagradu.'
  WHERE id = 'goblin_killer';
UPDATE quests SET naziv = 'Kosti za supu',
    opis = 'Donesi 5 kostiju skeleta za staru vješticu.'
  WHERE id = 'kosti_za_supu';
UPDATE quests SET naziv = 'Goblinske uši',
    opis = CONCAT('Trebaju mi dokazi da si ih stvarno pobio.', CHAR(10 USING utf8mb4), '', CHAR(10 USING utf8mb4), 'Donesi mi pet goblinskih ušiju.')
  WHERE id = 'q2';
UPDATE quests SET naziv = 'Kosturnica',
    opis = 'Nešto oživljava mrtve. Ubij 5 skeleta da saznaš više.'
  WHERE id = 'skeleton_hunter';
UPDATE quests SET naziv = 'Skupljač oružja',
    opis = 'Donesi 2 Iron Sword za lokalnog kovača.'
  WHERE id = 'skupljac_oruzja';
UPDATE quests SET naziv = 'Trollov kraj',
    opis = 'Ubij 3 trola koji blokiraju put prema gradu.'
  WHERE id = 'troll_slayer';
COMMIT;

SELECT id, naziv, REPLACE(opis, CHAR(10), ' // ') AS opis FROM quests ORDER BY id;
