-- Migration script to add missing columns to remote database
-- Run with: psql -U katrain_user -d katrain_db -f migrate_db.sql

-- ==========================================
-- Users table: Add missing columns
-- ==========================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS rank VARCHAR DEFAULT '20k';
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits FLOAT DEFAULT 10000.00;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS net_wins INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS elo_points INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS uuid VARCHAR UNIQUE;

-- Generate UUIDs for existing users that don't have one
UPDATE users SET uuid = md5(random()::text || clock_timestamp()::text) WHERE uuid IS NULL;

-- Create index on uuid if not exists
CREATE INDEX IF NOT EXISTS ix_users_uuid ON users(uuid);

-- ==========================================
-- Games table: Create if not exists
-- ==========================================
CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    black_player_id INTEGER REFERENCES users(id),
    white_player_id INTEGER REFERENCES users(id),
    winner_id INTEGER REFERENCES users(id),
    sgf_content TEXT,
    result VARCHAR,
    game_type VARCHAR NOT NULL DEFAULT 'free',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_games_id ON games(id);

-- ==========================================
-- Relationships table: Create if not exists
-- ==========================================
CREATE TABLE IF NOT EXISTS relationships (
    follower_id INTEGER REFERENCES users(id),
    following_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id)
);

-- ==========================================
-- Rating History table: Create if not exists
-- ==========================================
CREATE TABLE IF NOT EXISTS rating_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    old_rank VARCHAR,
    new_rank VARCHAR,
    elo_change INTEGER DEFAULT 0,
    game_id INTEGER REFERENCES games(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rating_history_id ON rating_history(id);

-- ==========================================
-- Verify the migration
-- ==========================================
\echo 'Migration complete. Verifying tables:'
\d users
\dt
