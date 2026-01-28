-- Migration: Add cron service support
-- Date: 2026-01-28
-- Description: Add partial index for analysis queue and llm_model columns for translation auditing.

-- 1. Partial index on live_analysis for fast pending task queries.
--    The cron AnalyzeJob queries pending tasks ordered by priority DESC, created_at ASC.
--    This index keeps the query constant-time regardless of table size (10k+ historical tasks).
CREATE INDEX IF NOT EXISTS idx_analysis_pending_priority
ON live_analysis (priority DESC, created_at ASC)
WHERE status = 'pending';

-- 2. Add llm_model column to player_translations for auditing which LLM model produced the translation.
ALTER TABLE player_translations
ADD COLUMN IF NOT EXISTS llm_model VARCHAR(64);

-- 3. Add llm_model column to tournament_translations for the same reason.
ALTER TABLE tournament_translations
ADD COLUMN IF NOT EXISTS llm_model VARCHAR(64);
