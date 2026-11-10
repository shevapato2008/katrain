# Original-source receipt filter index

This explicit PostgreSQL operation adds only
`ix_kifu_name_batches_status_publication_format` on
`kifu_name_batches (status, (reviewed_artifact ->> 'publication_format'))`.
It leaves the original-receipt lookup SQL, native v1/v2 membership, orphan and
conflicting-receipt guards, five-second lookup timeout and row/byte bounds intact.
Web/Cron startup never applies this migration.

Use the reviewed runtime and the target's existing private
`KATRAIN_DATABASE_URL` environment. Neither command prints credentials.
Inspection is read-only and exits 2 if the index is missing, mismatched or invalid:

```sh
python -m scripts.kifu_source_receipts_index --expected-database katrain_db
```

Only an explicit apply builds the index. Use a bounded analysis afterward so the
planner has expression statistics:

```sh
python -m scripts.kifu_source_receipts_index --apply --expected-database katrain_db \
  --analyze --timeout-ms 120000 --lock-timeout-ms 5000
```

The operator uses autocommit for `CREATE INDEX CONCURRENTLY`; do not wrap it in a
transaction. An already valid, exactly matching index is retained. Same-named
objects with another definition, or an incomplete index, are refused without DDL.
The independent `005_kifu_source_receipts_index.sql` is available for a dedicated
psql session with `ON_ERROR_STOP=1`, the verified database/search path and no outer
transaction. Its timeouts are session settings. Prefer the operator, which also
verifies index keys, table, btree options and both readiness flags.

A concurrent expression-index build can wait for an older REPEATABLE READ
snapshot even when that reader never writes the table. Coordinate with snapshot
export/audit workers; let them finish normally. The operation's statement and
lock timeouts bound the wait. A failure reports the backend PID, index OID,
full definition, `valid` and `ready`, then stops. `create_completed` records
whether CREATE returned successfully; false does not imply that no partial index
exists. No object is automatically dropped, rebuilt or retried. Inspect
`pg_stat_progress_create_index` and the reported exact OID/definition before any
separately reviewed correction. Never remove another pre-existing object.
If only ANALYZE failed, inspection can show the completed valid index; an explicit
subsequent `--apply --analyze` retains that index and retries only statistics.

Local PostgreSQL 15.15 validation used disposable UUID schemas, 954 unrelated
524,288-byte JSON artifacts and original native v1/v2 receipts. The exact compiled
lookup changed from about 4.22 seconds to 7.75 milliseconds; its indexed
count/size EXPLAIN ANALYZE took 0.129 milliseconds. No planner method was disabled.
The test also preserves conflicting/orphan receipts and both resource limits,
and reproduces an old-snapshot timeout leaving an invalid index that a subsequent
apply refuses. These are local measurements, not a claim of production DDL.

[PostgreSQL concurrent-build behavior](https://www.postgresql.org/docs/15/sql-createindex.html)
and [build progress phases](https://www.postgresql.org/docs/15/progress-reporting.html).
