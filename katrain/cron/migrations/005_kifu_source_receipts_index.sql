-- Explicit opt-in only; never run by Web/Cron startup or inside a transaction.
-- Prefer: python -m scripts.kifu_source_receipts_index --apply \
--           --expected-database <database> --analyze
-- The operator verifies the definition/readiness and bounds DDL waiting.
-- For manual psql use ON_ERROR_STOP=1, a verified search_path, lock_timeout and
-- statement_timeout. This deliberately has no IF NOT EXISTS: a same-named
-- foreign/incomplete index must be inspected, never silently accepted.
SET lock_timeout = '5s';
SET statement_timeout = '120s';
CREATE INDEX CONCURRENTLY ix_kifu_name_batches_status_publication_format
    ON kifu_name_batches (status, (reviewed_artifact ->> 'publication_format'));
-- Expression statistics require an explicitly bounded ANALYZE of this table
-- after a successful build; the operator's --analyze option performs it.
