# Transformer Analysis and Professional Kifu Implementation Plan

> **For agentic workers:** Execute in order. Check off steps with concrete evidence. The user requested at most two `gpt-6-astra` review rounds before implementation, then a dedicated branch and worktree.

**Goal:** Run personal reports, live analysis, and professional kifu analysis on the pinned `kata1-tf3-b11c768-s11003M-d5973M-7gres` network at the existing visit counts; store professional analysis separately from personal reports.

**Architecture:** Upgrade only the `:8002` KataGo service; leave `:8000` and certified ladder models untouched. The cron service uses one verified model identity and validates the response contract before persisting results. Professional game jobs and move rows live in their own tables keyed to `kifu_albums`, with a bounded, resumable backfill that yields to user reports and live analysis.

**Tech Stack:** KataGo analysis JSON API, Python/FastAPI/SQLAlchemy, PostgreSQL, React/Vite. Test on `home-ubuntu` (two RTX 3090s), then promote the exact tested artifact to `ucloud-v100` (16 GB V100).

---

## Confirmed baseline and boundaries

- Both environments currently run KataGo v1.16.4 on `:8002`, defaulting to `kata1-b28c512nbt-adam-s11165M-d5387M.bin.gz`. A transformer needs KataGo v1.17 or newer; choose a compatible current engine build after a real startup/benchmark probe on the V100.
- `katrain/cron/jobs/report_analyze.py` and `katrain/cron/jobs/analyze.py` both use `KataGoClient` and `:8002`. The gameplay/ladder service uses `:8000` and must keep its present model identities.
- `kifu_albums` already stores professional SGFs. `report_tasks` and `report_task_moves` require a user-owned `user_game_id`; they are not the professional-analysis store.
- The pinned network file is `https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz`. Record its downloaded SHA-256 in configuration and the deployment manifest; never commit the weight file.
- Initial corpus scope: canonical `kifu_albums` rows (`duplicate_of_id IS NULL`); duplicate aliases use the canonical analysis. Future imports enter the same scheduler. Validate this assumption before implementation if the user requests per-duplicate copies.
- Existing completed reports retain their historical results. Do not silently relabel them as transformer reports or resume a partially analyzed b28 report with transformer output.
- The user confirmed that phase one includes displaying the stored move-by-move professional analysis in the kifu library UI.
- UI correction: professional games must open a dedicated deep-report view modeled on the current personal deep report on both Galaxy and kiosk. The Galaxy action is “查看分析报告”; the kifu library is the professional-report entry, while Review remains the personal-report entry. The earlier compact analysis panel was rejected and removed.
- Capacity decision (2026-10-02): implement the system and run a small representative pilot; **do not start full-corpus backfill**. The 200G production disk device still has a ~100G root partition, leaving ~35G on the PostgreSQL volume. Even after resizing, ~97–104 GB of analysis rows plus indexes/WAL would leave limited headroom, and measured V100 throughput projects years of compute. Revisit both storage and GPU capacity before bulk admission.
- Preserve current personal-report credit pricing during this model rollout. `analysis_cost.report_cost` does not receive a model from its callers, and settlement recalculates from the current default. Any later price change needs its own authorized, per-task frozen pricing contract.

## Chunk 1: Engine switch and downstream contract

### Task 1: Capture and pin a reproducible engine artifact

**Files:** `deploy/katago-cron/README.md`, `deploy/katago-cron/config.yaml`, `deploy/katago-cron/Dockerfile` (new, if a separate image is required); external KataGo checkout for build only.

- [ ] Record the current `:8002` `/health` identity, container image digest, report/live queue counts, and a small representative b28 `/analyze` response on both environments. Use read-only commands and redact secrets.
- [ ] Obtain the exact network from KataGo's official site, verify SHA-256, and record network, engine source/release, CUDA/backend versions, and image digest in `deploy/katago-cron/README.md`.
- [ ] Pin the KataGo release, Python `realtime_api` source commit/patches, and CUDA/backend stack in one immutable image. Select a V100-compatible CUDA 12/cuDNN or TensorRT >=10 stack, not the old TensorRT 8.6 base or CUDA 13. Configure only the transformer in the cron service to conserve V100 memory; retain the old image as the rollback artifact. Do not change the `:8000` image or config.
- [ ] Start the candidate on an unused **test** port. Require `ready=true`, exact verified model SHA, and a successful `maxVisits=2000` request. A free TCP port does not isolate GPU memory; measure with `:8000` operating.
- [ ] Run a limited candidate probe on the production V100 without replacing `:8002`, after measuring available GPU memory. Benchmark representative SGFs at 500 and 2000 visits with report/live contention and record wall time, GPU memory, and throughput. If the candidate cannot run, revise the engine artifact rather than silently changing the network choice. Avoid two simultaneous large engines on the 16 GB GPU.
- [ ] **Feasibility gate before the professional schema/UI:** benchmark a representative corpus sample, including long and historical SGFs, and estimate full 2000-visits-per-position GPU time and stored JSON/index size. At 173k games × 200 moves, ~34.8 million positions need analysis; one position/second would take ~402 days before yielding to users. Report the projection and adjust capacity or schedule before admitting the full corpus.

### Task 2: Pin model identity and validate responses in cron

**Files:** `katrain/cron/clients/katago.py`, `katrain/cron/config.py`, `katrain/cron/jobs/report_analyze.py`, `katrain/cron/jobs/analyze.py`, `katrain/cron/models.py`, `katrain/web/core/models_db.py`, `tests/web_ui/test_katago_client.py`, `tests/web_ui/test_report_analyzer.py`, focused live-analysis tests.

- [ ] Add a configured expected model SHA to cron. On startup, inspect `/health` and fail closed for report/live analysis if the default model is not the pinned transformer and verified SHA.
- [ ] Validate each final `/analyze` result: no `error`, matching request ID and turn, `isDuringSearch=false`, matching `_wrapper` selected model/SHA, `rootInfo` numeric `winrate`/`scoreLead`/positive `visits`, valid `moveInfos` entries, and `ownership` sized to the requested board. Verify the 2000-visit request reaches its expected root visit count on representative positions. Reject malformed responses instead of persisting 0.5/0 fallbacks; allow additional JSON fields.
- [ ] Add focused tests for accepted transformer-shaped responses, missing fields, wrong model SHA, HTTP 200 `error`, and existing report/live parsers. Preserve `reportAnalysisWinratesAs=BLACK` and current grading semantics.
- [ ] Add nullable model SHA to personal report tasks and live analysis rows; stamp at first analysis, not just at creation. On every resume/retry, require the same SHA. For legacy reports with stored moves and no identity, finish on the old engine or restart the entire report under the new model with a billing-safe refund/authorization path; never append new-model moves to an unknown/b28 prefix. Treat completed legacy rows as unknown unless separately proven.
- [ ] Preserve `initialPlayer` through the HTTP wrapper. Reject SGFs that the current parser would silently alter or skip (especially midgame setup and malformed moves) before declaring an analysis job valid; verify move/position alignment against playback rather than another parser invocation alone.
- [ ] Verify the test environment end to end: one representative personal deep report and one live analysis record must reach their existing APIs with correct values, top moves, ownership, and grade. Compare schema/types with captured b28 responses; numeric values need not match.
- [ ] During cutover pause both report and live analysis consumers, drain active work, reconcile pending/failed/retryable reports (including previously settled prefixes), then deploy schema and SHA-aware cron/web code before switching the engine. Reconcile outstanding reservations; whole-report restart cannot charge twice. Rollback must restore both the old cron model expectation/code and the b28 engine, and handle any partial transformer reports without mixing them.

### Task 3: Promote the tested engine

**Files:** `deploy/katago-cron/README.md`, relevant environment deployment manifest (do not expose secrets).

- [ ] Promote the tested immutable artifact to `ucloud-v100` only after test gates pass. Record actual test-host `docker run` and production Compose procedures separately. On the production **engine Compose command**, dry run and ensure only `katago-cron` is recreated; cron/web code and schema use their own ordered deployment steps. Retain old image/code digests for rollback. Verify `:8000` SHA unchanged before and after.
- [ ] Repeat `/health`, a 2000-visit analysis probe, personal-report and live-analysis checks on production. Confirm model SHA in actual responses. Keep personal-report credit pricing unchanged in this rollout.
- [ ] If validation fails, restore the old cron/web model expectation together with the old `:8002` image and confirm the old `/health` identity. Record the failed gate. Do not begin professional backfill until this chunk passes.

## Chunk 2: Professional kifu analysis store and scheduler

### Task 4: Confirm the professional analysis UI with a small fixture

**Files:** `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx`, `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx`, shared presentation components and focused page tests.

- [ ] Use `ui-ux-pro-max` to inspect the existing design system. Produce a minimal fixture-backed preview of completed, running, failed, and unavailable professional analysis in the existing kifu views; use the existing board/report components.
- [ ] At a representative target viewport, compare reference and implementation screenshots side by side and in an overlay/diff; record material layout, status, and copy differences. Obtain the project's required user visual confirmation **before** professional backend work.
- [ ] Freeze the read contract (`album_id`, current SGF hash/model/visits, status/progress, position-zero and move rows, error), and state exactly when the fixture will be removed.

### Task 5: Add independent professional tables and safe migrations

**Files:** `katrain/web/core/models_db.py`, `katrain/cron/models.py`, `katrain/web/core/migrations.py`, `tests/web_ui/test_kifu_analysis_schema.py` (new).

- [ ] Create `kifu_analysis_jobs`: FK to canonical `kifu_albums.id`, pinned SGF hash, model SHA, requested visits (2000), status/progress/retry timestamps/error, and an idempotency key for game + SGF hash + model SHA + visits.
- [ ] Create `kifu_analysis_moves`: FK to job, unique `(job_id, move_number)`, fields matching the useful personal report analysis snapshot, including root visits, top moves, ownership, winrate, score lead, move grade, and deltas. Keep these tables separate from `report_tasks`/`report_task_moves` and `user_games`.
- [ ] Add PostgreSQL migration with actual FKs/unique indexes and add both tables to schema drift protection. Verify migration is safe to rerun and does not rebuild existing kifu or report tables.
- [ ] Test uniqueness, FK enforcement, model and SGF versioning, and repeat migration on an existing DB schema.

### Task 6: Reuse analysis semantics without mixing persistence

**Files:** `katrain/cron/jobs/report_analyze.py`, `katrain/cron/jobs/kifu_analyze.py` (new), `katrain/cron/models.py`, `katrain/cron/config.py`, `katrain/cron/main.py` or job registry, `tests/web_ui/test_kifu_analyze.py` (new).

- [ ] Extract only the common KataGo response normalization and move-grading computation used by personal reports; leave personal billing/task lifecycle separate. No copied grading thresholds.
- [ ] Implement a bounded professional worker with at most one outstanding request, admitted only at move boundaries when user-report/live capacity allows, ordered persistent claims, per-move commits, restart resume, retry/failure state, and a pause switch. Set timeout from the V100 pilot. Require exact SGF hash and transformer SHA on every resume.
- [ ] Before persisting each professional position, require `rootInfo.visits >= 2000` (engine overshoot is allowed). Retry or visibly fail an under-depth response; do not advance progress. Define any terminal-position exception only if the real engine pilot proves it necessary and the user accepts the resulting analysis contract. Mark a game completed only when every expected position, including position zero, has a depth-validated row.
- [ ] Make professional jobs low priority to personal reports and live analysis. Keep report/live concurrency and billing unchanged. An invalid or changed SGF must fail visibly, never produce a mixed report.
- [ ] Seed missing canonical games incrementally, including newly imported games, without inserting ~173k queued jobs in one transaction. Ignore exact duplicates via `duplicate_of_id`, while keeping source links intact.
- [ ] Test one full deterministic SGF, restart/resume, changed SGF, duplicate alias, import after scheduler start, temporary KataGo failure, an under-depth response, and no writes to personal tables.

### Task 7: Read API and product integration

**Files:** `katrain/web/api/v1/endpoints/kifu.py`, `katrain/web/core/repository.py` and remote client where board mode delegates, `katrain/web/ui/src/api/kifuApi.ts`, `katrain/web/ui/src/types/kifu.ts`, kifu page and focused tests.

- [ ] Return truthful `pending/running/completed/failed` status and progress for an album; return stored move rows only when present. Resolve duplicate album IDs to the canonical job. Select by the album's **current SGF hash**, pinned model SHA, and 2000 visits so an obsolete completed job is never displayed for changed content. Keep personal report APIs untouched.
- [ ] Extend the board-mode remote repository path for these new reads, with 503 on remote failure.
- [ ] Connect both relevant kifu views to the frozen contract using the shared winrate/top-move/grade presentation. The page must never imply an unfinished job is complete; remove the temporary fixture.
- [ ] Test API authorization/read behavior and one representative real-runtime UI preview at the target viewport. Remove any temporary fixture before completion.

### Task 8: Pilot with full-corpus admission disabled

**Files:** `scripts/backfill_kifu_analysis.py` (new, if admin CLI is needed), `docs/operations/kifu-analysis.md` (new).

- [ ] Run a small representative pilot on the test DB: normal, long, historical, handicap/pass, and known duplicate SGFs. Compare parsed moves and stored rows with the personal report contract.
- [ ] Recheck measured per-game duration and row/JSON size against the initial feasibility estimate, then set a conservative work rate and storage budget. Explicitly report projected completion time before starting the full backlog.
- [ ] Promote schema and worker through test then production; use dry run and migration checks. Run only a bounded, explicit small pilot with observable completion/failure counts and pause/resume control. Keep automatic discovery and full-corpus admission disabled for now.
- [ ] Report pilot status, model SHA, throughput, failures, and remaining eligible games. A future full-corpus run requires a separate capacity decision; the current task does not claim all canonical games are analyzed.

## Verification gates

1. The new `:8002` engine identifies the exact pinned network SHA, handles representative 2000-visit positions, and yields the same required JSON field shapes to KaTrain. `:8000` identities remain unchanged.
2. Personal report and live analysis complete under the transformer with truthful output and preserved billing behavior. No report combines positions from two model SHAs.
3. Professional analysis uses only `kifu_analysis_*` tables and canonical `kifu_albums`; it is resumable, observable, and yields to user work.
4. Production rollout follows a tested immutable image and migration, with explicit rollback and a measured estimate for the full corpus.
