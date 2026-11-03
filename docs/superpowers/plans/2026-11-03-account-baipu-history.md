# Account-backed baipu history implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. The user requests the previous complete workflow: independent astra/max plan review (maximum two rounds), parallel work on independent files after the contract is stable, spec review, then independent astra/max code review with fixes until approved.

**Goal:** Make 最近摆过 and replay progress survive Chromium/box restarts and synchronize for the authenticated account, retaining guest zero-persistence and honest offline states.

**Architecture:** A dedicated account-owned immutable SGF snapshot plus mutable cursor in PostgreSQL/server mode and SQLite/board mode. The SQLite history row also holds its pending synchronization state; reuse the existing SyncWorker lock and connectivity lifecycle rather than redesigning generic sync_queue. The existing recent-tab layout remains; replace its browser-only data source and wire physical-session progress.

**Tech Stack:** Existing FastAPI, Pydantic, SQLAlchemy, SQLite/PostgreSQL, React/TypeScript/Vitest/pytest. No new runtime dependency or scheduler.

**Baseline:** `9e83f1ad5` contains the previously approved screen SGF alignment. New work is on `feature/baipu-physical-history-20261103`; previous changes are preserved in that local checkpoint. No release or production database write is authorized by this plan.

## Chunk 1: Scope, contract and ownership

### Evidence

- `api/baipuApi.ts` caches recent entries/SGF/cursor only in identity-scoped localStorage; guest/unresolved uses memory.
- RK3562 Chromium uses `--incognito`, so browser restart discards that storage. Current device has no old baipu cache. Already lost historical browser data cannot be reconstructed from an account record that never existed.
- `KifuPage` reads recent only in a state initializer, before async identity resolution; it does not reload on account change.
- `PhysicalBoardButton` is the common start path from kifu and personal reports; `BaipuSessionPage` currently saves from inside `setK`, clears progress on completion and restart, and reads navigation state/cache without a durable server record.
- Both server and board lifespans expose injected `app.state.session_factory`; board has SQLite and existing SyncWorker / ConnectivityManager. `require_writable_user` blocks guest persistence. `cloud_session_is` is the existing fail-closed binding precedent.
- Do not store baipu history in `user_games`: that table feeds game statistics, growth, report tasks and personal game lists.

### Record contract

A record belongs to the **authenticated** owner. Record identifier is deterministic from exact SGF SHA-256 and a replay schema version, independent of kifu album ID, title, device or username. Use one row per owner and immutable replay identity. SGF content, hash, total and replay version cannot be replaced under an existing identity. Keep `source_id` (e.g. `kifu_140859`) and display `name` for navigation/presentation, never as ownership proof.

Suggested model `BaipuHistory` / table `baipu_history`:

```text
user_id + record_id: composite key (user FK; record_id lower hex64)
source_id, name, sgf_content, sgf_sha256, replay_version, total
k, completed_at, updated_at
local_revision (browser -> this node optimistic concurrency)
writer_id (durable device-generated UUID), writer_seq (transactional counter)
cloud_revision, pending_base_revision
sync_state (synced/pending/conflict/refused), conflict_remote (JSON, nullable)
last_mutation_id (idempotent public save retry)
```

Store the exact source SGF. Derive hash, supported replay version and total on the server; validate `0 <= k <= total`. Step interpretation comes from `build_steps_from_sgf`, so a future replay schema change cannot silently reuse another version's cursor. The physical-replay extension is being investigated separately; if authorized, both plans use the same explicitly versioned identity contract. No cursor migration from unknown-version or unscoped browser storage.

### Authenticated API (new router `baipu_history.py`, mounted `/baipu/history`)

All routes depend on authenticated non-guest ownership, with `extra='forbid'` request schemas. No authoritative user ID is accepted from the browser. Another owner's record is 404. Apply bounded source/name/SGF/limit fields; do not accept path-like record identifiers. Browser requests carry optional bearer or same-origin cookies, plus an expected-identity precondition header derived from the resolved AuthContext identity. If that header names a different authenticated identity, reject before writing; it is a precondition, never an owner selector. Remote board->cloud traffic relies on strict bound-owner token handling rather than assuming local/cloud UUID or numeric-ID equality.

- `GET /baipu/history?limit=30`: summaries, bounded latest-activity order, no SGF body; include cursor, total, completion, source/name and authority/sync state.
- `GET /baipu/history/{record_id}`: full exact SGF snapshot and saved cursor/revisions, owner-filtered.
- `POST /baipu/history/open`: `{sgf_content, source_id, name}`. Validate/resolve replay identity, create a new cursor-zero entry only if absent, return existing progress without resetting it. Call only after entering a usable physical replay, not on library preview selection. For existing unfinished records, the frontend offers resume/restart before recording a new cursor.
- `PUT /baipu/history/{record_id}`: `{k, expected_local_revision, mutation_id}`. Advance, undo and explicit restart all use this route. Repeated mutation ID is idempotent; stale local revision is 409. Completion persists; do not delete the row or cursor when done.
- `PUT /baipu/history/{record_id}/sync`: full immutable snapshot plus `{k, writer_id, writer_seq, expected_revision}`. This is the cloud merge contract; identity still derives from authentication. Board-generated immutable requests are sent only under a bound matching account.
- `POST /baipu/history/{record_id}/resolve`: `{strategy: use_cloud | keep_local, expected_local_revision}` explicit conflict resolution. Fetch latest cloud record under the same bound owner; do not silently pick a side. If offline, return a bounded service error and retain the conflict.

Responses distinguish `authority: cloud | local_cache | this_node` and `sync_state`. API unavailability/auth/loading must not appear as “this account has never replayed a game.” Guest UI uses its existing ephemeral browser memory and does not call these APIs.

### Frozen public response/error types

```ts
type HistoryAuthority = 'cloud' | 'local_cache' | 'this_node';
type HistorySyncState = 'synced' | 'pending' | 'conflict' | 'refused';
interface BaipuHistorySummary {
  id: string; source_id: string; name: string; sgf_sha256: string;
  replay_version: number; k: number; total: number; completed: boolean;
  local_revision: number; cloud_revision: number; updated_at: string; completed_at: string | null;
  authority: HistoryAuthority; sync_state: HistorySyncState;
}
interface BaipuHistoryDetail extends BaipuHistorySummary {
  sgf_content: string;
  conflict_remote?: { k: number; total: number; updated_at: string; cloud_revision: number } | null;
}
// GET list -> {items: BaipuHistorySummary[], authority: HistoryAuthority}
// open/get/save/resolve -> BaipuHistoryDetail
```

`id` is the public name for `record_id`; do not expose internal owner IDs or mutable writer bookkeeping in browser summaries. Timestamps are UTC ISO8601 strings. `k` is the count of completed backend steps, matching the existing physical progress convention (including initial setup/pass/clear steps); it is not a screen-only B/W move number. Do not save an incomplete removal phase as completed progress. History accepts usable 19x19 physical replay only, with total >0, exact UTF8 SGF <=1MiB, display name <=512 and source ID <=128 characters.

Use structured409 details with stable codes: `stale_local_revision`, `cloud_progress_conflict`, `identity_changed`, `immutable_snapshot_mismatch`; current owner-scoped snapshot may accompany a cursor conflict. Unsupported replay version/invalid cursor/content is422. Unauthenticated401, guest403, other owner404. The expected-identity header compares the same canonical identity string AuthContext uses (UUID, otherwise `id:username`); it never changes the selected owner.

For sync-only responses, the service may use an internal superset containing `cloud_revision`, `last_writer_id`, `last_writer_seq` and immutable snapshot fields. Keep that transport model separate from the bounded browser response. Cloud conflict payload contains the full validated remote snapshot so the device can retain it; browser conflict summary need not duplicate its SGF body.

### Synchronization protocol (row is the outbox)

**Local write, one SQLite transaction:** check expected local revision; preserve immutable snapshot; update cursor/completion; increment local revision and durable writer sequence. Transition synced→pending with `pending_base_revision = cloud_revision`. Further pending writes preserve that base. Conflict/refused writes can remain locally durable, but do not restart automatic sends.

**Cloud acceptance, atomic row lock/conditional update:**

1. Same writer, greater sequence: accept current cursor, including decreasing cursor for undo/restart, and increment revision.
2. Same writer, equal sequence: idempotent only if the snapshot/cursor payload matches; differing reused sequence conflicts.
3. Same writer, smaller sequence: return current state as superseded, do not rewind.
4. Different writer: require expected revision equal current cloud revision, otherwise 409 with the complete current remote snapshot.
5. New record requires expected revision zero. Content/version/total validation precedes any upsert.

**Drain:** `SyncWorker` calls focused history sync using its existing run lock and connectivity/reconnect lifecycle. Require bound owner equality, including rejecting absent binding; do not copy the more permissive user-games owner guard. Capture an immutable payload before HTTP. No generic sync queue coalescing, lease or 409 change. A network/5xx failure remains pending; authentication mismatch waits for owner; validation refusal stops; 409 records conflict and stops automatic retry for that record.

**Receipt W/S while local cursor advances:** ignore for local state if writer rotated. For same durable writer, monotonically remember acknowledged cloud revision, but mark synced only if the current local sequence is still S. Preserve newer local cursor and pending state. Never overwrite a newer cursor or clear a recorded conflict with an old receipt. **Do not rebase a dirty pending branch after intermediate success or a cloud GET**: same-writer sequence acceptance already allows subsequent causal writes; another writer changing cloud must still conflict.

**Read/merge:** all owner-scoped GET/list/detail cloud responses include `cloud_revision`; fresh cloud revision is available to clean adoption and resolution without using a sync-only response. Online history and details require a bound owner before/after requests and after 401-refresh retries. Refresh clean local rows from cloud for offline availability, retaining this device's writer identity. Adoption is an atomic conditional operation: update only if the row is still clean and incoming cloud_revision >= cached cloud_revision; use insert-on-conflict protection for new rows. Return the actual merged winning row to the caller, never the original remote payload after a failed adoption condition. Thus an old GET arriving after local-save+sync cannot rewind a now-clean row. Never overwrite pending/conflicted local progress with a list refresh. Return pending/conflict rows as visible local records even while online. A server failure falls back to only that authenticated owner's durable cache with honest authority.

**Resolution:** the request includes expected_local_revision. Capture the local writer and conflicted row version before fetching cloud, then in the repository transaction recheck expected local revision, writer identity and conflicted state. If local progress or resolution changed while GET awaited, return409 with the current local snapshot; do not discard or rebase it. use_cloud adopts latest remote cursor; keep_local retains local cursor and explicitly bases it on a fresh remote revision. Both rotate the durable writer UUID, reset sequence, and retain the other snapshot in conflict evidence until resolution completes. Late receipts from the prior writer cannot settle the new branch. Another concurrent cloud edit can conflict again and waits; no automatic overwrite loop.

## Chunk 2: Implementation work, with frozen contracts

### Task H1 — model, repository and endpoint (owned backend foundation)

**Files:** new `katrain/web/core/baipu_history.py`, `katrain/web/api/v1/endpoints/baipu_history.py`; modify `models_db.py`, `migrations.py`, `core/auth.py` only if startup needs a narrow hook, `api/v1/endpoints/auth.py` guest-owned-row enumeration, `api/v1/api.py`, the two lifespan wiring points in `server.py`; new isolated `tests/web_ui/test_baipu_history.py`, `test_baipu_history_api.py`; guest-pristine regression in `tests/web_ui/test_box_sso.py` as needed.

- [ ] Write failing isolated SQLite/API tests first. Every fixture uses its injected session factory; never run startup DDL against the developer/production DB.
- [ ] Add the small owned table, index owner+updated_at, unique replay identity and bounded cursor/check constraints. Add it to protected authoritative and guest-pristine owned-table checks; use additive startup creation, no drop/rebuild or kifu DDL.
- [ ] Implement open/list/get/local save/cloud accept/conflict resolution repository methods under the frozen contract. Keep storage separate from HTTP and transport. No source-SGF metadata rewrite.
- [ ] Register authenticated routes and inject the repository in both lifespans without replacing test injections.
- [ ] Verify persistence after reopening SQLite, ownership/guest guards, immutable hash/version, cursor bounds, completion, decreasing cursor, local CAS, idempotency and atomic two-writer cloud conflict. Use a disposable local postgres:15-alpine container (available in local Docker) for authoritative atomic-update/concurrent-writer checks; never use production or developer databases. State exact SQLite/PostgreSQL test results.

### Task H2 — bound-owner cloud adapter and row outbox

**Files:** new focused `katrain/web/core/baipu_history_sync.py` (or equivalent cohesive service); limited `remote_client.py` helper and `sync_worker.py` hook; coordinate `server.py` wiring through H1/controller, not concurrent edits; new `tests/web_ui/test_baipu_history_sync.py`.

**Frozen repository seam:** expose owner-scoped `pending_snapshots`, immutable request snapshot, conditional receipt/conflict/refusal absorption and clean-cloud adoption methods. Agree exact signatures with H1 before code; H1 owns table/repository, H2 owns network service. A callback injected into SyncWorker may be preferable to a broad worker dependency.

- [ ] Write failing owner-mismatch/unbound/401-switch and in-flight receipt tests before implementation.
- [ ] Reuse the existing worker lock and connectivity drain; no new scheduler, queue, or whole generic worker rewrite. Add only the focused row-outbox drain hook.
- [ ] Protect before-send, refresh retry and after-response identity. Never send or return another account's payload; stale responses are discarded.
- [ ] Implement causal receipts, dirty-GET protection and explicit conflict resolution exactly above. Leave generic queue 409 behavior unchanged.
- [ ] Verify advance during HTTP, browser reload (same persisted writer), process death/retry, newer local undo, other-device write, writer rotation before late receipt, delayed old GET arriving after local save+successful sync, and local progress changing while conflict resolution fetches cloud. Network errors keep pending; permanent/conflict does not loop.

### Task H3 — frontend history hook and existing recent Tab

**Files:** new `api/baipuHistoryApi.ts`, `kiosk/hooks/useBaipuHistory.ts` (list/read) and `useBaipuSessionHistory.ts` (session persistence); modify `KifuPage.tsx`, `PhysicalBoardButton.tsx`; narrowly integrate `BaipuSessionPage.tsx` only after any physical-frontend worker finishes or through that worker's frozen hook contract. Add focused API/hook/component tests. New visible strings use the existing kifu namespace and real translations in all 11 `katrain/i18n/locales/{cn,tw,en,jp,ko,de,es,fr,ru,tr,ua}/LC_MESSAGES/katrain.po` catalogs; compile their MO artifacts for runtime as the repository requires. Preserve placeholders and pass `tests/web_ui/test_kiosk_i18n.py`; do not add empty/TODO/English-as-non-English placeholders.

- [ ] Write identity-resolution/loading/empty/error and account-switch regressions first. Current synchronous browser-only initializer must fail these tests before the fix.
- [ ] Authenticated requests capture identity and bearer/cookie mode. Await resolved real identity; cancel/ignore stale list/detail responses. Gate SGF navigation state to its originating identity so logging into another account cannot attribute the prior account's SGF or cursor to it.
- [ ] Real users load durable recent summaries; guests use the existing memory store. Preserve the current row layout/scroll behavior. Replace “存在这台盒子上” with accurate account/cloud/local status. Render loading and service error explicitly, not false empty.
- [ ] Resume obtains the exact authenticated snapshot, not browser cache. PhysicalBoardButton passes an identity-tagged navigation payload; session hook can reload by history ID after browser restart.
- [ ] Session loads history after authoritative SGF parse, presents existing resume/restart choice, and persists only completed physical-step cursor changes. Serialize writes, coalesce only unsent cursor updates, use returned local revision; an identity switch invalidates old work. Do not perform network writes inside a React state updater.
- [ ] Completion remains visible as completed; restart persists k=0 instead of deleting history. Local browser cache is optional guest/temporary navigation, not real-user authority.
- [ ] Add small status text and two explicit conflict resolution actions using existing button patterns. Keep working SGF/physical session usable when a cloud sync is pending; report persistence failures honestly. No account-history backfill from unowned/unscoped cache.
- [ ] Verify server reopen/browser reload resume, completed history, undo/restart, unavailable service, delayed /me and logout/account switch, and guest disk/API silence.

### Frozen H1/H2 seam

Implement one focused `BaipuHistoryService(repo, remote_client=None, connectivity=None)` owned by H2. With no remote client it calls the authoritative repository; board mode adds bound remote read/merge and row-outbox behavior. Routes inject `request.app.state.baipu_history_service`. Public async service methods: `open(user_id, data)`, `list(user_id, limit)`, `get(user_id, record_id)`, `save(user_id, record_id, data)`, `accept_sync(user_id, record_id, data)`, `resolve(user_id, record_id, strategy, expected_local_revision)`, and `sync_pending()`.

H1 repository owns synchronous `open(user_id, data, board=False)`, `list(user_id, limit)`, `get(user_id, record_id)`, `save(user_id, record_id, data, board=False)`, `accept_sync(user_id, record_id, data)`, `pending_snapshots()`, `absorb_success(user_id, record_id, sent, remote)`, `absorb_conflict(user_id, record_id, sent, remote)`, `mark_refused(user_id, record_id, sent, reason)`, `adopt_clean(user_id, remote_records)` returning merged winning rows, and `resolve(user_id, record_id, strategy, remote, expected_local_revision)` with atomic local version/state checks. Each return is a plain dictionary or bounded list; missing records raise a small typed not-found exception; conflicts carry a structured current snapshot and are translated to HTTP409 at the route. Private pending snapshots include owner ID and a copied immutable sync payload; public response schemas omit internal owner IDs.

Add one `BAIPU_REPLAY_VERSION` constant beside the existing backend step builder. History identity includes that constant; no replay semantic change belongs to H1. If the physical plan is approved later, its core owner bumps the same constant with explicit tests.

For authoritative public saves (not board mode), the expected local revision protects direct browser writes. Every accepted cursor-changing save increments BOTH local_revision and cloud_revision atomically, and assigns a new writer ID; otherwise a board with an old unchanged cloud revision could pass CAS and overwrite that browser save. Idempotent duplicate saves increment neither revision. Cloud sync acceptance increments the authoritative local/cloud revisions together. For board saves, the device writer remains stable and local revision changes only on actual cursor/open activity or clean remote adoption, not merely a sync receipt.

H1 owns `server.py` and route registration wiring. H2 supplies the service and a `SyncWorker(..., baipu_sync=None)` optional async callback invoked under its existing run lock; H1 injects it after creating the board service. Do not edit these shared wiring files concurrently. A standalone server service uses no sync callback. Tests inject the exact service/repository with isolated factories.

### Execution ordering

- [ ] Independent astra/max plan review round 1; fix material findings; if needed round 2 (maximum). No product implementation before approval.
- [ ] Freeze H1/H2 method/types, then develop backend foundation and independent frontend hook/UI in parallel with explicit file ownership. H1 and H2 may develop separate files concurrently only after method signatures stabilize.
- [ ] Close one integrated recent→resume journey before expanding other UI. Use the existing tab composition; no visual redesign or unrelated user-games/growth changes. If a new layout is actually required, create a 1024x600 fixture preview for user confirmation before its backend integration.
- [ ] Spec compliance review, followed by independent astra/max final code quality review. Fix findings and re-review until explicitly approved.

## Chunk 3: Acceptance and handoff

- [ ] Targeted backend auth/repository/sync tests plus existing relevant SSO/sync regressions, frontend API/hook/session/recent tests, TypeScript and Kiosk 2D build guard. Avoid unrelated broad regressions once sufficient checks pass.
- [ ] Real runtime journey against an isolated local service/SQLite and authenticated disposable accounts: open a real SGF, complete a step, reload/restart browser, see recent, resume exact cursor; complete and retain; offline save/reopen/reconnect; switch to another account and guest without exposing prior history.
- [ ] Account history UI uses the established geometry at 1024x600; capture one representative real preview and material loading/error/sync states only. Do not run hardware capture/LED writes merely to test persistence.
- [ ] If physical replay extension is authorized, integrate its completed-step and replay-version contract; do not silently import old cursors using a changed interpreter.
- [ ] No production deploy, DB mutation, library deletion, or restore of already-lost historical cache. Record local commits, reviewed plan/code, validation and precise remaining limits.

### Baseline test note

Before product edits, `CI=true .venv/bin/python -m pytest tests/web_ui/test_user_game_cloud_owner.py tests/web_ui/test_box_sso.py -k 'guest or owner' -q` yielded44passed/1failed/12deselected. The pre-existing pristine-existing-guest bootstrap test returns409 rather than200. Keep this baseline separately identified; do not weaken guest data isolation or change credit/bootstrap semantics to make an unrelated test green.

## Implementation record — 2026-11-03

H1/H2/H3 and physical-session integration implemented. Backend protocol spec review is SPEC COMPLIANT; combined physical/history spec review and ASTRA/MAX code quality review passed. Concrete review fixes include truthful board conflict authority, retaining conflict evidence until the current success receipt, immutable in-flight save credentials across unmount, explicit save retry and pending-save exit guard. Actual RK retrieved account progress saved from a different browser in a disposable runtime. Older lost/unowned/version-unknown browser history is not fabricated or imported. See `2026-11-03-baipu-physical-history-runtime.md`; production deployment remains separate.
