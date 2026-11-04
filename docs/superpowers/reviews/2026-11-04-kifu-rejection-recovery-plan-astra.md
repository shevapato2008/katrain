# Kifu Rejection Audit and Cron Recovery — Plan Review

**Verdict: APPROVED (round 1).** No blocking plan changes are required.

Reviewed the implementation plan against `names.py`, Stage atomic/checkpoint storage, the ingestion ledger and isolation paths, `CronScheduler`, `ControlPoller`, `RunRecorder`, and admin cron health/control handling. Product files were not changed; no services, model calls, or album data were accessed.

- The diagnostic callback and Stage records can retain both initial and narrowed-scope rejections without changing approved decision fields, hashes, receipts, or reserve/settle accounting. Recording before repair preserves the first rejected candidate even when the second succeeds.
- The plan explicitly separates semantic rejection, malformed reviewer protocol, invalid candidate, and malformed/truncated output. Bounded evidence, explicit missing metadata, stable codes, and a durable audit reference address the historical observability gap.
- Waiting for the first successful controls read closes the demonstrated six-failure startup bypass. Reusing the existing poll cadence and shutdown event provides automatic recovery when the database returns while preserving manual pause and the last readable snapshot.
- The proposed health ordering correctly lets overdue scheduling surface above an old failure, retains the prior run details, applies resume grace to never-run jobs, and preserves the higher-priority offline/disabled/paused/running states. Returning the existing 503 response avoids reporting an unknown pause state as false.
- Focused fake-response, temporary-Stage, startup/control, health, and existing isolation regressions are proportionate. No deployment, paid reproduction, quarantine release, watchdog, schema migration, or broader publication changes are needed.

Implementation checks already implied by the plan: keep diagnostic metadata out of the returned producer/review records; retain the original rejection reason if audit storage fails; use the existing directory-fsync pattern for durable new diagnostic files; carry the audit reference early enough in isolation errors to survive journal truncation. These are execution details, not additional scope or a reason for another plan-review round.

The historical reject reason remains unrecoverable. The later successful preview is separate evidence and cannot be presented as recovery of that reason or authorization to publish.
