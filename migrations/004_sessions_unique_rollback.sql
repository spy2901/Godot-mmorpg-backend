-- Rollback za 004_sessions_unique.sql: vraca obican indeks na account_id.
-- Redosled: PRVO vratiti kod na verziju bez ON DUPLICATE KEY UPDATE, pa tek onda ovo
-- (bez UNIQUE indeksa novi kod bi pri svakoj prijavi dodavao sesiju umesto da zameni staru).
ALTER TABLE sessions
  ADD KEY idx_sessions_account (account_id),
  DROP KEY uq_sessions_account;

SHOW CREATE TABLE sessions;
