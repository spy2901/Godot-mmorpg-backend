-- Rucno pokrenuti u MAMP MySQL (baza: mmorpg).

-- 1) Statovi na itemima. Vracaju se automatski kroz SELECT * - kod se ne menja.
ALTER TABLE items
  ADD COLUMN damage INT NOT NULL DEFAULT 0,
  ADD COLUMN armor INT NOT NULL DEFAULT 0,
  ADD COLUMN hp_bonus INT NOT NULL DEFAULT 0;

-- 2) Tabela players (ne postoji u bazi; /players rute je zahtevaju).
CREATE TABLE IF NOT EXISTS players (
  ime VARCHAR(50) NOT NULL PRIMARY KEY,
  level INT NOT NULL DEFAULT 1,
  xp INT NOT NULL DEFAULT 0,
  gold INT NOT NULL DEFAULT 100,
  hp INT NOT NULL DEFAULT 100,
  max_hp INT NOT NULL DEFAULT 100,
  inventory LONGTEXT,
  equipment LONGTEXT
);
