-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rank VARCHAR(10) DEFAULT '20k', -- Initial rank
    credits DECIMAL(10, 2) DEFAULT 10000.00, -- High initial balance for testing
    avatar_url VARCHAR(255),
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
    result VARCHAR(20), -- e.g., "B+Resign", "W+0.5"
    game_type VARCHAR(20) NOT NULL CHECK (game_type IN ('free', 'rated')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Relationships (Social)
CREATE TABLE IF NOT EXISTS relationships (
    follower_id INTEGER REFERENCES users(id),
    following_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, following_id)
);

-- Rating History (for tracking progress)
CREATE TABLE IF NOT EXISTS rating_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    old_rank VARCHAR(10),
    new_rank VARCHAR(10),
    game_id INTEGER REFERENCES games(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_games_black ON games(black_player_id);
CREATE INDEX idx_games_white ON games(white_player_id);
CREATE INDEX idx_relationships_follower ON relationships(follower_id);
