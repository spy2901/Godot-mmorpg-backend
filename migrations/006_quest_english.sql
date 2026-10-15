-- Questovi na engleskom: naziv i opis 6 questova (prevod odobren, stari srpski tekst u 006_quest_english_rollback.sql).
-- Menja samo naziv i opis po ID-u; ID-evi, ciljevi i nagrade ostaju. Pokretati sa utf8mb4:
--   mariadb --default-character-set=utf8mb4 mmorpg < migrations/006_quest_english.sql
-- Bez backslash escape-a u stringovima (prelom strane u opisu = CHAR(10)), radi i uz NO_BACKSLASH_ESCAPES.
SET NAMES utf8mb4;

-- 1) provera: prava baza i svih 6 questova ima tačno očekivani tekst (bajt-po-bajt) -> inače prekid pre izmene
SELECT DATABASE() AS baza, COUNT(*) AS questova FROM quests;

DELIMITER //
BEGIN NOT ATOMIC
  IF (SELECT COUNT(*) FROM quests
      WHERE (id = 'goblin_killer' AND BINARY naziv = BINARY 'Goblinski problem' AND BINARY opis = BINARY 'Goblini haraju okolicom. Ubij 5 goblina i vrati se po nagradu.')
     OR (id = 'kosti_za_supu' AND BINARY naziv = BINARY 'Kosti za supu' AND BINARY opis = BINARY 'Donesi 5 kostiju skeleta za staru vješticu.')
     OR (id = 'q2' AND BINARY naziv = BINARY 'Goblinske uši' AND BINARY opis = BINARY CONCAT('Trebaju mi dokazi da si ih stvarno pobio.', CHAR(10 USING utf8mb4), '', CHAR(10 USING utf8mb4), 'Donesi mi pet goblinskih ušiju.'))
     OR (id = 'skeleton_hunter' AND BINARY naziv = BINARY 'Kosturnica' AND BINARY opis = BINARY 'Nešto oživljava mrtve. Ubij 5 skeleta da saznaš više.')
     OR (id = 'skupljac_oruzja' AND BINARY naziv = BINARY 'Skupljač oružja' AND BINARY opis = BINARY 'Donesi 2 Iron Sword za lokalnog kovača.')
     OR (id = 'troll_slayer' AND BINARY naziv = BINARY 'Trollov kraj' AND BINARY opis = BINARY 'Ubij 3 trola koji blokiraju put prema gradu.')) <> 6 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'quests: tekst nije ocekivani srpski (vec migrirano ili izmenjeno), migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) izmena u jednoj transakciji
START TRANSACTION;
UPDATE quests SET naziv = 'Goblin Trouble',
    opis = 'Goblins are raiding the area. Kill 5 goblins and come back for your reward.'
  WHERE id = 'goblin_killer';
UPDATE quests SET naziv = 'Bones for Soup',
    opis = 'Bring 5 skeleton ribs to the old witch.'
  WHERE id = 'kosti_za_supu';
UPDATE quests SET naziv = 'Goblin Ears',
    opis = CONCAT('I need proof that you really killed them.', CHAR(10 USING utf8mb4), '', CHAR(10 USING utf8mb4), 'Bring me 5 goblin ears.')
  WHERE id = 'q2';
UPDATE quests SET naziv = 'Rise of the Dead',
    opis = 'Something is raising the dead. Kill 5 skeletons to find out more.'
  WHERE id = 'skeleton_hunter';
UPDATE quests SET naziv = 'Weapon Collector',
    opis = 'Bring 2 Iron Swords to the local blacksmith.'
  WHERE id = 'skupljac_oruzja';
UPDATE quests SET naziv = 'Troll Hunt',
    opis = 'Kill 3 trolls that are blocking the road to the town.'
  WHERE id = 'troll_slayer';
COMMIT;

SELECT id, naziv, REPLACE(opis, CHAR(10), ' // ') AS opis FROM quests ORDER BY id;
