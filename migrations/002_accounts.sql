-- Faza 1: nalozi i sesije. Pokrenuti jednom.

CREATE TABLE IF NOT EXISTS accounts (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(50)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_accounts_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- U bazi se cuva samo SHA-256 hash tokena (64 hex znaka), nikad sam token.
CREATE TABLE IF NOT EXISTS sessions (
  token_hash CHAR(64)     NOT NULL PRIMARY KEY,
  account_id INT UNSIGNED NOT NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME     NOT NULL,
  KEY idx_sessions_account (account_id),
  KEY idx_sessions_expires (expires_at),
  CONSTRAINT fk_sessions_account FOREIGN KEY (account_id)
    REFERENCES accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Jedan lik po nalogu.
ALTER TABLE players
  ADD COLUMN account_id INT UNSIGNED NULL,
  ADD UNIQUE KEY uq_players_account (account_id),
  ADD CONSTRAINT fk_players_account FOREIGN KEY (account_id)
    REFERENCES accounts(id) ON DELETE SET NULL;