-- Migration: Add live_upcoming table for upcoming match events
-- Run this on your PostgreSQL database before starting katrain-cron

CREATE TABLE IF NOT EXISTS live_upcoming (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(128) UNIQUE NOT NULL,
    tournament VARCHAR(256) NOT NULL,
    round_name VARCHAR(128),
    scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
    player_black VARCHAR(128),
    player_white VARCHAR(128),
    source VARCHAR(32) NOT NULL,
    source_url VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for filtering by scheduled_time (for getting future events)
CREATE INDEX IF NOT EXISTS idx_upcoming_scheduled_time ON live_upcoming(scheduled_time);

-- Index for event_id lookups
CREATE INDEX IF NOT EXISTS idx_upcoming_event_id ON live_upcoming(event_id);
