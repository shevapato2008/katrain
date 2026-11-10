# Task 3 Orchestration Review — 2026-10-23

Scope: `9d8f36f29..19459b95d5f4bd72d0dc7fdb6d28696a2f9a226b`, limited to `katrain/cron/jobs/kifu_ingest.py`, `katrain/cron/config.py`, `katrain/kifu_ingest/exclusions.py` and the two cron test files. The Task 3 plan and root's explicit acceptance requirements were reviewed against the actual diff. Task 1/2 implementations were read only where necessary to understand call contracts.

Final review HEAD: `22fff109ea98f495c36cd527c0a28e941b5cb0c9`. **Spec compliance passed; independent quality review passed. No remaining must-fix findings in the Task 3 scope.** This is a local review approval, not a production rollout or a full-repository audit.

## Stage 1 — Initial spec compliance: changes requested, subsequently fixed

### Must fix: missing Stage raw baseline still authorizes PROD publication

- Location: `katrain/cron/jobs/kifu_ingest.py:546–552` (`_frozen_scope`).
- Requirement: an un-PROD frozen recent package may continue only after current-window source checking and a three-way match between manifest raw SHA, Stage original raw SHA and current observed raw SHA. Missing/changed/unchecked evidence must hold the package before PROD.
- Actual behavior: the Stage raw comparison is conditional on `item.get("raw_sha256") is not None`. Thus a missing Stage original SHA is treated as a successful comparison. A published TEST candidate gets only an observation baseline from `discover_recent`, so it has a current observed SHA but still no Stage original SHA or raw artifact; `_frozen_scope` returns `recent` and the package is sent to PROD.
- Minimal local reproduction: use the existing mocked `hourly` fixture, call `freeze(h, "40", original=False)`, expose `[source_metadata("40")]` as the current head, then run `KifuIngestJob()._run_locked()`. No real network, model, publication, production data, SSH or album data is used.
- Observed result:

```text
stage_raw_sha256=None
stage_raw_sgf_path=None
observed_raw_sha256=b8123e1bf7f7100440570091529627899d6f32764bcd8251696fe5d7edadd2e4
batch_status=prod_synced
publish_sync_events=[('sync', 'frozen-40')]
```

- Smallest fix: require the Stage original raw SHA to exist and equal both other hashes before returning `recent`; otherwise retain receipt/evidence and hold the un-PROD package. Add the missing-baseline case with an otherwise unchanged manifest/current observation to the existing frozen-version orchestration test.

Validation run independently:

```text
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/cron/test_kifu_hourly_orchestration.py tests/cron/test_kifu_ingest.py -q
59 passed in 0.67s
```

The current tests pass but do not cover the absent Stage baseline. The `different_raw_baseline` case changes the manifest hash, so it proves a different condition.

## Stage 1 — Fix re-review: passed

The initial review stopped before quality review, as requested. Fix commit `22fff109ea98f495c36cd527c0a28e941b5cb0c9` now requires nonempty `original` and `observed` raw SHA values and equality with the manifest. The new `missing_original_baseline` parameter preserves the TEST receipt and current observation SHA, verifies the missing original SHA/path stay missing, and asserts `source_version_mismatch` quarantine with no publish/sync calls. The prior source-change, unchecked and differing-manifest cases remain in place.

The final Task 3 diff also meets the reviewed ordering and authority requirements: only local manifest validation/packaged-ID collection precedes source discovery; catalog/native-receipt lookup receives the bounded candidate set rather than pending-item membership; only checked eligible items reach preparation; published-only observations do not create ingestion journals; original PROD state/receipts survive terminal source observations. Recent frozen TEST packages can continue through the existing pipeline after the exact source-version guard, while historical native receipts only enter verification and no-receipt historical work is explicitly deferred.

## Stage 2 — Independent quality review: passed

Reviewed the final actual diff separately for data preservation, idempotence, budgets and single-writer behavior. The PostgreSQL session lock and shared Stage writer lock enclose Stage construction and all round work; source bounds/configuration retain the requested hard caps and existing enable/interval/token/name restrictions. Publication workers are awaited without `wait_for` cancellation; native receipt transitions are preserved before the next cooperative boundary. Historical verification receives one shared `min(round_deadline, now + recovery_seconds)` deadline, and receiver subprocess calls still receive finite remaining timeouts. Error persistence includes actual exception class and phase. Successful receipt-based retry paths reuse existing verification helpers and the round shares the existing SGF cache parameter.

No additional must-fix or material nonblocking findings were identified in the requested Task 3 scope.

Independent final validation:

```text
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/cron/test_kifu_hourly_orchestration.py tests/cron/test_kifu_ingest.py -q
60 passed in 0.72s

/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/test_kifu_incremental_source.py tests/test_kifu_incremental_staging.py tests/test_kifu_incremental_state.py tests/test_kifu_incremental_cli.py tests/cron/test_kifu_ingest.py tests/cron/test_kifu_hourly_orchestration.py tests/test_kifu_api_verification.py -q
188 passed in 1.60s

git diff --check 9d8f36f29..22fff109ea98f495c36cd527c0a28e941b5cb0c9 -- katrain/cron/jobs/kifu_ingest.py katrain/cron/config.py katrain/kifu_ingest/exclusions.py tests/cron/test_kifu_hourly_orchestration.py tests/cron/test_kifu_ingest.py
exit 0; no output
```

All verification was local and mocked or temporary-database based. No production SSH/API, model, import, deployment or album-data access was performed. This report remains uncommitted for the parent to include with final handoff artifacts.
