-- Explicit PostgreSQL migration; run before deploying code that reads this field.
-- Does not change player identities, aliases, album FKs, or localized names.
ALTER TABLE kifu_players
    ADD COLUMN IF NOT EXISTS authoritative_pages JSON NOT NULL DEFAULT '[]';
