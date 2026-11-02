# Account baipu history — independent ASTRA/MAX plan review, round 2

**Verdict: APPROVED. No blocking plan findings remain.**

This is the second and final plan-review round. Proceed with the planned contract freeze and implementation, followed by spec review and independent ASTRA/MAX code review. Approval covers account history persistence and synchronization; the separate physical full-replay scope remains subject to its user clarification.

Reviewed `docs/superpowers/plans/2026-11-03-account-baipu-history.md` at SHA-256 `db291f354f700cc59cf442a6ac5d845ae20cbe6529e2f910ea7cd3fd877b6b5b`, against baseline `9e83f1ad5eaf61f354b71bd6e8bb3dab28717531` on `feature/baipu-physical-history-20261103`. The reviewed version includes the 11-catalog localization clarification. Read the repository instructions, round-1 report, and relevant auth, remote client, worker/connectivity, lifespan, step-builder, and frontend entry/session code. Only this review report was written; no product, plan, database, device, or commit changes were made.

## Round-1 findings are closed

| Finding | Revised contract | Assessment |
| --- | --- | --- |
| R1: Missing cloud revision on reads and authoritative public writes | Public summaries/details contain `cloud_revision` (line 64); authoritative cursor saves and cloud acceptance atomically advance both revisions (line 146). | A fresh board can establish its CAS base, and a later browser write invalidates an older board base. Duplicate retries do not manufacture revisions. |
| R2: Delayed GET can rewind acknowledged progress | Clean adoption atomically checks current cleanliness and incoming revision, protects insertion races, and returns the actual merged winner (line 97). The delayed-GET-after-save-and-sync test is explicit (line 123). | The earlier stale-read race is covered in storage and in the returned response. |
| R3: Resolution can discard progress made during its cloud fetch | Resolve carries `expected_local_revision`, captures the pre-fetch writer/version, and rechecks revision, writer, and conflict state transactionally after awaiting cloud (lines 52, 99, 140–142). The concurrent local-save test is explicit (line 123). | The earlier destructive resolution race is covered; writer rotation also excludes old receipts. |

## Coherence and scope

The cloud rules distinguish causal writes from one durable writer from competing writers. Retaining the original pending base while coalescing local updates prevents an intermediate receipt or unrelated GET from silently authorizing an overwrite. Conditional receipt handling preserves newer local cursors, stops old writers after resolution, and keeps conflicts out of automatic retry. These rules can be implemented within the dedicated row and focused service.

The owner boundary is appropriately explicit: non-guest authenticated routes, owner-filtered records, browser identity preconditions, and strict local-owner binding before/after cloud requests and refresh retries. The plan correctly rejects absent binding instead of copying the permissive user-games guard. Its identity-tagged navigation and stale-response suppression address the current frontend entry paths.

The repository/service split fits the existing injected session factories. The existing worker already serializes runs, and ConnectivityManager drains while online as well as on reconnect; an optional callback is sufficient. Protected-table and guest-pristine registration are the relevant schema/auth changes. There is no reason to alter the generic queue, repair unrelated bootstrap behavior, add a scheduler, or broaden physical replay semantics.

## Implementation attention points within the approved scope

Carry forward the round-1 integration notes when freezing the concrete types and tests:

- On an online local-cache miss, `open` must discover an existing cloud record before creating a zero cursor. List summaries lack SGF; hydrate a missing immutable snapshot from detail when selected. Existing cached snapshots can merge validated summaries. No additional cache table or bulk prefetch is required.
- Put the returned durable history ID in a reloadable URL. Navigation state alone cannot satisfy browser-restart resume. Retain completed records and offer an explicit restart that persists zero.
- An equal-revision, identical cloud snapshot should be a no-op. Resolution must carry its pre-await guard into the repository transaction; every successful resolution must invalidate stale local CAS callers, including `keep_local` when the cursor value itself is unchanged. A rejected resolution must not automatically repeat the user's destructive choice or move the physical session cursor.

These are execution details of the approved read/merge, resume, and resolution requirements, not requests for additional architecture or another plan-review round.

## Validation assessment

The proposed checks are proportionate to this account/data-integrity change: isolated SQLite reopen/API tests, disposable PostgreSQL concurrent acceptance, focused owner-switch and in-flight race tests, frontend reload/completion/guest behavior, and one representative runtime preview at the established geometry. The added tests target the three actual protocol gaps. Exact database results should be reported during implementation; this plan review did not execute runtime tests.

Keep the reported pre-existing `44 passed / 1 failed / 12 deselected` auth baseline separately identified. It does not justify weakening guest isolation or expanding this work into bootstrap/credit changes.
