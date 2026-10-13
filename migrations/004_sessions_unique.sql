-- Jedna sesija po nalogu: UNIQUE (account_id) umesto obicnog indeksa.
-- Razlog: DELETE po neunikatnom indeksu u REPEATABLE READ uzima gap lock; dve istovremene
-- prijave (susedni account_id) zakljucaju isti gap pa se INSERT-i zaglave (1213 deadlock).
-- Sa UNIQUE indeksom login radi jedan INSERT ... ON DUPLICATE KEY UPDATE.
-- Pokrenuti PRE novog koda (stari kod radi i na ovoj semi). Rollback: 004_sessions_unique_rollback.sql

-- 1) provera duplikata: ako ih ima, prekid pre ALTER-a (sema ostaje netaknuta)
SELECT account_id, COUNT(*) AS sesija FROM sessions GROUP BY account_id HAVING COUNT(*) > 1;

DELIMITER //
BEGIN NOT ATOMIC
  IF EXISTS (SELECT 1 FROM sessions GROUP BY account_id HAVING COUNT(*) > 1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'sessions: duplikati account_id, migracija prekinuta';
  END IF;
END //
DELIMITER ;

-- 2) jedan ALTER: novi UNIQUE preuzima ulogu indeksa za FK, stari se brise
ALTER TABLE sessions
  ADD UNIQUE KEY uq_sessions_account (account_id),
  DROP KEY idx_sessions_account;

SHOW CREATE TABLE sessions;
