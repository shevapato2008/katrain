# Kifu Rejection Audit and Cron Recovery Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement the two independent tasks below. Preserve the approved publication/receipt contracts and existing paid-call accounting.

**Goal:** Make every name rejection explainable and durable, keep unrelated new games moving, and prevent a cron restart from bypassing an unreadable manual-pause control.

**Architecture:** Extend the existing name-review protocol and Stage diagnostic storage rather than adding database tables or a monitoring service. Keep per-item isolation and package retry behavior. Wait for the first successful controls snapshot before starting interval execution; derive missed scheduling from existing status timestamps and report unavailable controls honestly.

**Tech Stack:** Existing Python async Qwen client, Stage atomic JSON files, PostgreSQL/SQLite state journal, APScheduler, FastAPI admin health, pytest.

---

## Evidence and boundaries

- The affected item is `19x19/92176443`, the **2026-11-03** Xu Haohong–Lai Junfu game, not an October game. Its old candidate and review response were not retained. The old protocol allowed only `decision`; an explicit reject and an invalid response shape produced the same error.
- A preview-only run on 2026-11-04 used the normal paid ledger, the real cached input and existing Stage lock: one event proposal and one review, 2,461 tokens. It approved. This does **not** recover the old reason or approve publication. Detailed safe reproduction evidence is `/tmp/92176443-preview-reproduction-complete.json`.
- Current qualified player names mean the preview skipped player generation. Historic ledger token counts alone cannot identify the rejected entity.
- Existing source quarantine isolates that item, not the whole source; bad packages do not prevent subsequent packages. Four existing focused tests verified this. Existing transport cooldown, package retry/backoff, `max_instances=1`, database/file locks and receipt guards remain authoritative.
- The current global maintenance pause is deliberate and stays in place. No cron resume/run, quarantine release, historical batch recovery, model approval override, PG/ES business write, deployment or additional paid calls are included in this implementation.
- Do not read, list or traverse `data/kifu-album/` on any machine. Do not edit protected historical rank modules, native publication manifests, prior receipts or the role configuration.
- The existing role-preserving deployment helper is an audited operational artifact, not a runtime watchdog. This change must not claim automatic recovery from intentional disable, manual pause, or an unknown in-flight remote publication.

## Chunk 1: Rejection evidence and safe scheduling

### Task A: Durable name rejection reasons

**Files:**
- Modify: `katrain/kifu_ingest/names.py`
- Modify: `katrain/kifu_ingest/staging.py` only for the small Stage audit writer if needed
- Modify: `katrain/cron/jobs/kifu_ingest.py` only to wire the normal audit callback
- Modify: `katrain/kifu_ingest/orchestration.py` only to preserve a concise reason/audit reference in existing isolation errors
- Tests: existing `tests/test_kifu_incremental_names.py`, `tests/test_kifu_incremental_decision_checkpoint.py`, `tests/cron/test_kifu_ingest.py` or one narrowly scoped companion where useful

- [x] Add focused failing checks: explicit semantic rejection includes the returned reason; a rejection without a reason is a distinct protocol failure; candidate validation and malformed/truncated model output are distinct from a semantic reject. Cover both initial and narrowed-scope review.
- [x] Require the reviewer to return a decision with a concise reason for rejection. An old `{"decision":"approve"}` remains acceptable; a reject must have a nonblank bounded reason. Validate the response shape without silently treating an extra/invalid field as a semantic reject. Unknown/invalid responses still fail closed.
- [x] Keep the approved portable decision/review format unchanged: do not append new fields to immutable publication decisions or alter their hashes. Reasons belong to diagnostic evidence; valid approvals retain today's catalog validation.
- [x] Persist one bounded, atomic diagnostic record for each rejected attempt **before** repair/rethrow/quarantine, including an earlier rejection followed by successful repair. Reuse Stage storage and one optional callback; do not create a generic event bus or schema migration.
- [x] Each record identifies source members, kind/key, phase, attempt, stable reason code, human reason, available candidate and parsed review, model/request IDs, prompt/output hashes and time. Capture available metadata for malformed or failed calls; absence must be explicit. Store only final response content needed for diagnosis, never credentials, headers, SGF bodies or private chain-of-thought. Bound text/JSON sizes and preserve an integrity hash/truncation marker where raw evidence cannot fit.
- [x] Preserve the normal reserve/settle and one-call usage audit. Link actual call audit entries to the entity and source IDs without counting diagnostic events as additional paid calls. A diagnostic-write failure must not silently approve/publish or lose the rejection; propagate an explicit storage error without automatic approval.
- [x] Preserve concise reason plus diagnostic reference through the existing Stage/journal isolation path. The persisted full diagnostic remains available when the journal's error string is truncated. Do not change quarantine/retry policy or invent an automatic release path.
- [x] Test with temporary Stage storage and fake model responses: the record survives service recreation; first-reject/second-approve preserves the first reason; invalid protocol/output is classified; narrowed-scope reject is recorded; paid calls are not duplicated; audit I/O failure remains closed. Reuse existing source/package isolation tests to prove an unrelated valid source still proceeds.
- [x] Run only affected name/checkpoint/ingest tests, then inspect the diff. No live model call is needed to test explicit rejects.

### Task B: Safe startup and truthful liveness

**Files:**
- Modify: `katrain/cron/scheduler.py`
- Modify: `katrain/web/admin/cron_health.py`
- Modify: `katrain/web/admin/routers/cron.py`
- Modify only if required by the smallest implementation: `katrain/cron/controls.py` or `katrain/cron/run_recorder.py`
- Tests: `tests/test_cron_controls.py`, `tests/test_cron_run_recorder.py`, `tests/web_ui/test_admin_cron_health.py`, `tests/web_ui/test_admin_cron_controls.py`

- [x] Add a failing startup test: more than six initial control-read failures must never allow an interval job to execute. Once the existing poll succeeds, a persisted paused job still skips and an unpaused job can be scheduled normally. Use deterministic fakes rather than real waits or services.
- [x] Replace the six-failures-then-start behavior with the smallest wait-until-known startup path. Reuse the existing controls polling cadence; support shutdown promptly while waiting. Keep the process recoverable when the DB returns, without resetting controls, spawning a watchdog or forcibly restarting publishers. Preserve the last valid controls snapshot after later failures.
- [x] Make the admin jobs API return its existing database-unavailable response if control tables cannot be read. Never represent unknown pause state as `paused=false`. No frontend schema or layout change is required; the existing API error state is sufficient.
- [x] Add focused health tests: a never-run enabled interval becomes `overdue` after the existing interval grace measured from process start; overdue takes precedence over an old `failed`/`errors` result. Keep the prior result/error in its existing fields. Preserve startup grace, heartbeat/offline, running/stuck, configured-disabled and manual-pause precedence.
- [x] Use the existing resumed timestamp to exclude intentionally paused time from overdue calculations, including a never-run job. Do not infer expected collector roles from hostnames or silently flip disabled configuration.
- [x] Run affected scheduler/controls/health tests and the four existing item/package-isolation regressions. Do not run a real cron round or change service lifecycle.

### Task C: Independent review and delivery

- [x] ROOT obtains independent Astra max plan review, at most two rounds, before product edits. Task A and B may then be implemented in parallel because their owned files are separate except existing ingest tests; coordinate before editing shared tests.
- [x] Keep no-model reproduction and real paid-preview facts separate from deterministic tests and from the unrecoverable historical reason. Do not claim the old reject has been reproduced.
- [x] Integrate the two diffs and run the union of their focused tests once. Broaden only if an actual cross-task failure requires it. Check `git diff --check` and verify immutable rank files have no diff.
- [x] Obtain independent Astra max spec-compliance and code-quality review, fix substantive findings until approved. Avoid repeated whole-suite runs or unrelated repairs.
- [x] Commit the scoped implementation and review records on `fix/kifu-rejection-resilience-20261104` (base `4f7d17b738`, preserving the separately reviewed pagination fix). Preserve all unrelated worktrees.
- [x] Report the historical limitation, the new audit behavior, what automatic recovery already does, the new control/health fixes, test evidence, and commit. Explicitly state that current manual pause and the isolated game are unchanged and code is not yet deployed. Do not leave a running model preview or temporary fixture/service.


## Delivery evidence

- Independent Astra max plan review: APPROVED in round 1. Final spec/code review: APPROVED after one bounded malformed-output correction; see the two review documents in `docs/superpowers/reviews/`.
- ROOT integrated focused verification: 241 passed, 4 existing cleanup UTC deprecation warnings, 3.00 seconds. After the final strict-JSON correction, ROOT reran the affected names file: 84 passed, 0.47 seconds; the independent reviewer also ran the new overflow-number regression: 1 passed. No full-suite rerun was needed.
- Protected historical rank modules have no diff. No schema migration, native receipt/publication change, automatic quarantine release or live cron execution was performed.
- One normal-protocol paid preview used 2 calls and 2,461 tokens; it approved. The historical rejection remains unproven because its original candidate/response were never retained. Safe exact evidence is retained locally under `output/kifu-rejection-resilience-20261104/` and in the HOME Stage diagnostic directory.
- Current production maintenance pause, the source's existing quarantine, deployed containers and business data are unchanged. This commit is an implementation/review handoff, not a deployment or service restoration.
- Operational boundary incident: the Task A author issued one empty-output `git status` with the restricted album-directory pathspec during final checks. No explicit content-reading command was issued, but Git-internal metadata traversal cannot be excluded. ROOT disclosed this and stopped further checks of that path.


## Published-release integration

The original local develop baseline diverged from the already-published canonical/rank fixes and included unrelated material work. It is preserved untouched in its original worktrees. The release is assembled from fresh `origin/develop` at `8c4b6296bbc445f88e5b9e2994b7681a5a0a27c0`, cherry-picking only the two reviewed changes. Existing identity/rank/supersession fixes and the latest published stone/UI work remain present.

The current strict TEST verifier exposed an old incomplete test response on remote develop. Only that test fixture was supplied with its existing one-game/five-language report shape; the product verifier was not weakened. Final integrated checks passed: 435 backend tests, 1 optional PostgreSQL skip, and 46 frontend tests across the two kifu pages plus rank formatting. Independent Astra integration review approved both picks and merge boundaries. Deployment and controlled seven-item recovery proceed only against this exact integrated release.
