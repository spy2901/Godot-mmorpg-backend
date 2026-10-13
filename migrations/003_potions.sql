-- Potrosni predmeti: efekti i cooldown. Pokrenuti jednom.

ALTER TABLE items
  ADD COLUMN hp_efekat INT NOT NULL DEFAULT 0,
  ADD COLUMN mana_efekat INT NOT NULL DEFAULT 0,
  ADD COLUMN cooldown_ms INT NOT NULL DEFAULT 1000;

-- Samo predmeti koji lece hp/manu. Ostali consumable (antidote, elixiri,
-- speed/stamina/invisibility/resurrection) ostaju 0 dok ne dobiju svoje efekte.
UPDATE items SET hp_efekat = 30,  cooldown_ms = 5000  WHERE id = 'small_health_potion';
UPDATE items SET hp_efekat = 80,  cooldown_ms = 7000  WHERE id = 'medium_health_potion';
UPDATE items SET hp_efekat = 150, cooldown_ms = 10000 WHERE id = 'large_health_potion';
UPDATE items SET mana_efekat = 50, cooldown_ms = 5000 WHERE id = 'mana_potion';
UPDATE items SET mana_efekat = 30, cooldown_ms = 8000 WHERE id = 'energy_drink';

UPDATE items SET hp_efekat = 10, cooldown_ms = 5000 WHERE id = 'apple';
UPDATE items SET hp_efekat = 15, cooldown_ms = 5000 WHERE id = 'bread';
UPDATE items SET hp_efekat = 20, cooldown_ms = 5000 WHERE id = 'cheese';
UPDATE items SET hp_efekat = 25, cooldown_ms = 5000 WHERE id = 'cooked_fish';
UPDATE items SET hp_efekat = 35, cooldown_ms = 5000 WHERE id = 'roasted_meat';
UPDATE items SET hp_efekat = 20, mana_efekat = 10, cooldown_ms = 5000 WHERE id = 'mushroom_soup';
