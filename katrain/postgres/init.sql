-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    rank VARCHAR(10) DEFAULT '20k',
    net_wins INTEGER DEFAULT 0,
    elo_points INTEGER DEFAULT 0,
    credits NUMERIC(15, 2) DEFAULT 10000.00,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Games table
CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    black_player_id INTEGER REFERENCES users(id),
    white_player_id INTEGER REFERENCES users(id),
    winner_id INTEGER REFERENCES users(id),
    sgf_content TEXT,
    result VARCHAR(50),
    game_type VARCHAR(20) DEFAULT 'free', -- 'free' or 'rated'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Relationships (follows)
CREATE TABLE IF NOT EXISTS relationships (
    follower_id INTEGER REFERENCES users(id),
    following_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, following_id)
);

-- Rating History
CREATE TABLE IF NOT EXISTS rating_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    old_rank VARCHAR(10),
    new_rank VARCHAR(10),
    elo_change INTEGER DEFAULT 0,
    game_id INTEGER REFERENCES games(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_games_black ON games(black_player_id);
CREATE INDEX idx_games_white ON games(white_player_id);
CREATE INDEX idx_relationships_follower ON relationships(follower_id);
