-- Explicit-only rank foundation migration. Application startup must not run this DDL.
-- Existing kifu_players/kifu_albums rows and their proof shapes remain unchanged.
BEGIN;
CREATE TABLE IF NOT EXISTS kifu_player_rank_history (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES kifu_players(id),
    rank_value INTEGER NOT NULL,
    rank_system VARCHAR(24) NOT NULL,
    source_as_of DATE,
    valid_from DATE,
    observed_at TIMESTAMPTZ NOT NULL,
    last_checked_at TIMESTAMPTZ,
    source_kind VARCHAR(32) NOT NULL,
    source_ref JSON NOT NULL,
    evidence JSON NOT NULL,
    content_sha256 VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_kifu_player_rank_fact UNIQUE (player_id, content_sha256),
    CONSTRAINT ck_kifu_player_rank_system CHECK (
        rank_system IN ('professional_dan', 'amateur_dan', 'kyu', 'dan_unspecified')),
    CONSTRAINT ck_kifu_player_rank_value CHECK (
        rank_value >= 1 AND ((rank_system = 'kyu' AND rank_value <= 30) OR
                            (rank_system <> 'kyu' AND rank_value <= 9))),
    CONSTRAINT ck_kifu_player_rank_status CHECK (status IN ('qualified', 'conflict')),
    CONSTRAINT ck_kifu_player_rank_sha256 CHECK (content_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_kifu_player_rank_current
    ON kifu_player_rank_history(player_id) WHERE is_current;
CREATE INDEX IF NOT EXISTS ix_kifu_player_rank_date
    ON kifu_player_rank_history(player_id, source_as_of);
CREATE TABLE IF NOT EXISTS kifu_album_rank_snapshots (
    id SERIAL PRIMARY KEY,
    album_id INTEGER NOT NULL REFERENCES kifu_albums(id),
    side VARCHAR(5) NOT NULL,
    rank_fact_id INTEGER REFERENCES kifu_player_rank_history(id) ON DELETE RESTRICT,
    snapshot JSON NOT NULL,
    snapshot_sha256 VARCHAR(64) NOT NULL,
    publication_key VARCHAR(160) NOT NULL,
    native_batch_id INTEGER NOT NULL,
    CONSTRAINT uq_kifu_album_rank_side UNIQUE (album_id, side),
    CONSTRAINT ck_kifu_album_rank_side CHECK (side IN ('black', 'white')),
    CONSTRAINT ck_kifu_album_rank_sha256 CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS ix_kifu_album_rank_snapshots_rank_fact_id
    ON kifu_album_rank_snapshots(rank_fact_id);
COMMIT;
