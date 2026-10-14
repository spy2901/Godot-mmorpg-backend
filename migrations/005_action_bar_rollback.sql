-- Rollback za 005_action_bar.sql: brise players.action_bar (sacuvani rasporedi se gube).
-- Redosled: PRVO vratiti kod na verziju bez action bar rute, pa tek onda ovo
-- (novi kod bez kolone: GET /players vraca action_bar null, a svaki upis rasporeda pada).
ALTER TABLE players DROP COLUMN action_bar;

SHOW CREATE TABLE players;
