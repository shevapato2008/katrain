-- Durable orchestration journal for incremental 19x19 kifu ingestion.
-- Apply explicitly on the target database; StateStore never runs DDL.

CREATE TABLE IF NOT EXISTS kifu_ingest_batches (
    id BIGSERIAL PRIMARY KEY,
    batch_uuid VARCHAR(36) NOT NULL UNIQUE,
    publication_key VARCHAR(160) NOT NULL UNIQUE,
    manifest_sha256 VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL,
    resume_phase VARCHAR(24),
    test_receipt JSON,
    test_verification JSON,
    prod_receipt JSON,
    prod_verification JSON,
    stats JSON,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    error VARCHAR(512),
    next_retry_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kifu_ingest_items (
    id BIGSERIAL PRIMARY KEY,
    source_key VARCHAR(16) NOT NULL CHECK (source_key = '19x19'),
    external_id VARCHAR(64) NOT NULL CHECK (external_id ~ '^[0-9]+$'),
    raw_sha256 VARCHAR(64),
    sgf_sha256 VARCHAR(64),
    staging_path VARCHAR(512),
    source_metadata JSON,
    status VARCHAR(24) NOT NULL,
    resume_phase VARCHAR(24),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    error VARCHAR(512),
    next_retry_at TIMESTAMPTZ,
    publication_key VARCHAR(160) REFERENCES kifu_ingest_batches(publication_key),
    test_album_id INTEGER,
    prod_album_id INTEGER,
    test_receipt JSON,
    test_verification JSON,
    prod_receipt JSON,
    prod_verification JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_kifu_ingest_items_source UNIQUE (source_key, external_id)
);

CREATE INDEX IF NOT EXISTS idx_kifu_ingest_items_status_retry
    ON kifu_ingest_items (status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_kifu_ingest_items_publication
    ON kifu_ingest_items (publication_key);
