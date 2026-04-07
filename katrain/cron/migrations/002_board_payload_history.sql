-- Migration: Add board_payload_history for audit trail of manual corrections
-- Date: 2026-04-07

CREATE TABLE IF NOT EXISTS board_payload_history (
    id SERIAL PRIMARY KEY,
    figure_id INTEGER NOT NULL REFERENCES tutorial_figures(id) ON DELETE CASCADE,
    board_payload JSON NOT NULL,
    changed_by VARCHAR(128) DEFAULT 'anonymous',
    change_type VARCHAR(16) NOT NULL DEFAULT 'edit',  -- 'edit' | 'verify'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bph_figure ON board_payload_history(figure_id);
CREATE INDEX IF NOT EXISTS idx_bph_time ON board_payload_history(created_at);
