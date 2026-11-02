# Account baipu history — independent ASTRA/MAX plan review, round 1

**Verdict: CHANGES REQUESTED — three important protocol gaps.**

Reviewed `docs/superpowers/plans/2026-11-03-account-baipu-history.md` at SHA-256 `4d7e0cbd555df6d4070967914e71a544d59f83b293ac407aabb4396579157f2f`, against baseline `9e83f1ad5eaf61f354b71bd6e8bb3dab28717531` on `feature/baipu-physical-history-20261103`. This includes the added frozen public response/error section. References below use that revision's line numbers. No product, database, device, or plan changes were made during this review.

## R1 — P1: The cloud revision contract is incomplete for reads and public writes

**Plan references:** lines 47–52, 61–79, 83, 90, 97–99, 146.

`GET` detail returns `BaipuHistoryDetail`, which has no current `cloud_revision`; that field exists only inside an optional conflict summary. Line 79 offers the complete revision only for **sync-only responses**. Nevertheless, clean cloud adoption and `keep_local` require a freshly fetched cloud revision. A board reading an existing cloud record cannot populate its CAS base from the specified response. Inferring it from `local_revision` is not a frozen invariant, and the plan deliberately gives node-local and cloud revisions different meanings.

There is a related missing transition: line 146 explicitly increments both revisions for cloud sync acceptance, but does not explicitly increment `cloud_revision` for an authoritative browser save. Rotating the writer UUID is not enough. If cloud revision remains R after that save, a board with an old base R and a different writer still passes rule 4 and overwrites the browser's newer progress.

**Narrow fix:** expose a current cloud revision on cloud-readable detail responses (adding `cloud_revision` is sufficient), and define it as increasing on every accepted authoritative cursor mutation, including public saves and restarts. Freeze the exact transport shape used by remote GET/resolve rather than leaving a sync-only superset optional. Also specify how summary reads hydrate the immutable row: summaries contain no SGF, so new snapshot rows must come from a detail fetch; lazily caching a selected detail is sufficient and does not require a second cache table or bulk prefetch.

**Focused checks:** read an existing cloud record on a fresh board, cache it, and save with the fetched base; resolve `keep_local` against a fetched revision; accept a direct server/browser save, then prove a different board's earlier base conflicts.

## R2 — P1: A delayed cloud GET can overwrite a newer, already-synced local cursor

**Plan references:** lines 95–97, 117, 142, 146.

The read rule protects dirty rows, but it does not require incoming cloud revisions to be monotonic. Consider a GET that reads revision 4 and is delayed. While it waits, the user completes a step, the worker uploads it as revision 5, and its receipt marks the local row synced. When the old GET finally arrives, the row is now clean, so the stated `adopt_clean` rule permits revision 4 to replace the newer cursor. This loses the locally acknowledged step without any identity change or second device.

The existing worker lock cannot prevent this: it serializes drains (`sync_worker.py:77–87`), while the proposed service GET and public save paths run independently. Frontend cancellation of identity-stale responses also does not cover this same-account race.

**Narrow fix:** make adoption an atomic repository operation requiring a still-synced row and an incoming cloud revision newer than the stored acknowledged revision; an identical equal-revision snapshot is a no-op. Never regress the cached revision, cursor, or local revision, and never adopt over pending/conflict/refused state. The service must return the repository's merged winner after this check, not the stale remote body it just fetched. Apply the same rule to list-based updates and detail reads.

**Focused check:** delay a cloud GET, complete and acknowledge a newer local save, release the old GET, and assert both SQLite and the returned detail retain the newer cursor/revision. A second delayed-read test is unnecessary if this covers the same repository operation used by list and get.

## R3 — P1: Conflict resolution lacks a local CAS precondition

**Plan references:** lines 52, 83, 99, 133–135, 140–142.

The plan expressly allows further locally durable writes while a row is conflicted. Resolution then awaits a fresh remote GET, but the frozen route/service/repository signatures accept only the strategy and remote snapshot. A user can choose `use_cloud`, complete another local step during that request (or another browser can save), and have resolution silently overwrite that new step. Writer rotation prevents old **sync receipts** from applying afterward; it does not protect local edits made before the resolution transaction.

**Narrow fix:** require `expected_local_revision` for resolve, pass it through both service and repository seams, and atomically verify it after the remote read before adopting a cursor or rotating the writer. On mismatch return `stale_local_revision` with the current owner-scoped snapshot and retain the current branch. The frontend should reload/re-present the decision, not automatically repeat a destructive `use_cloud` choice against the newer state. Apply the returned cursor to the physical session only after resolution succeeds.

**Focused check:** hold the resolve GET, save another local step, finish resolve, and verify 409 plus preservation of that step, writer, and conflict evidence.

## Scope and implementation notes

The dedicated owned table, exact immutable SGF, durable row outbox, strict bound-owner network handling, and existing worker lifecycle are proportionate to the requested restart/offline/account behavior. No generic queue rewrite, new scheduler, or unrelated auth repair is needed. Existing `remote_client.py:122–149` already snapshots the refresh token/binding across 401 retry; the new helper should retain that behavior and add the specified strict owner checks.

The startup/session-factory seam and protected-table/guest-pristine additions are correctly scoped. Guest-owned enumeration is in `api/v1/endpoints/auth.py:245–298`; `core/auth.py:118–215` owns startup DDL. Tests must continue using injected disposable stores. The reported pre-existing guest-bootstrap failure does not justify expanding this history work into unrelated bootstrap behavior.

For frontend implementation, preserve the plan's existing acceptance requirements explicitly: online `open` on a local cache miss must discover the account's existing cloud progress before creating a zero cursor; after open, the durable history ID must be encoded in a reloadable URL rather than exist only in navigation state; reopening a completed record must offer an explicit restart that saves zero. The current code only shows the resume dialog for `0 < k < total` (`BaipuSessionPage.tsx:209–213`) and its physical entry URL currently carries the source ID (`PhysicalBoardButton.tsx:29–30`). These are concrete integration points, not a request for a new layout or broader test suite.

Approval can follow a focused plan amendment for R1–R3 in the second allowed round. The separate physical SGF semantics decision does not block these history corrections.
