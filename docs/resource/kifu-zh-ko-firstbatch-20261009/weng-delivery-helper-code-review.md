# Weng delivery helper independent code review

**Decision: PASS after corrections. No Essential/Important issue remains.**

Reviewer: `/root/zh_ko_task2_review_astra`, `gpt-6-astra`, 2026-10-09. Reviewed `/tmp/kifu-zh-ko-weng-delivery-root-20261009/delivery.py`, its README, and the actual r7 importer interfaces used by the helper. Final reviewed script SHA-256: `3b4d8518ffe2fd612e5746da41ad3bbf01c40147810fcd573d8b4ca97b2608d6`.

## Spec review — PASS

- Scope is one generated KO name: PROD 5739 / TEST 11508, 翁子瑜 → 웡쯔위. The source research retains the exact independently signed Weng CN/EN anchors. Wang is excluded.
- Capture requires a PostgreSQL read-only connection and checks the pinned importer manifest against `/app`. It imports `name_inventory` before adding the existing physical `list_hidden_reason String(64)` column to the old mapper. It checks physical `event_edition_id` presence and preserves native inventory hashing. There is no schema change or full ORM replacement.
- Fresh capture and the transaction guard require the null KO target, unchanged canonical owner, exact CN/EN names, both live source proofs and normalized KO collision rejection. The owner preimage now uses raw `SELECT *`, retaining existing source/authority page columns missing from the old mapper. Scoped albums also use all physical columns plus exact SGF UTF-8 hashes, covering FK, rank, hidden and edition fields.
- `prepare` creates a pending candidate with a real capture binding. `finalize` preserves every pending input except review status and invokes the exact ZH review validator and original native bundle validator. The actual registry version is 45 characters, within the native `String(64)` limit. Native `(bundle_format=1, inventory_format=4)` is supported.
- `apply` retains the native importer transaction, locks and journals. A bounded wrapper performs captured catalog, physical owner/albums/SGF, latest-batch and source/target checks on the **same locked connection before the importer writes**. It additionally protects batch/journal tables against concurrent direct edits and restores the original context manager afterward.
- Exact already-applied bundles can reach native idempotent validation. Native replay checks the frozen artifact/research, current creation after-images, collisions and live anchors before returning `already_applied` with zero changes. New writes retain the null-target/latest-batch checks.
- The one-name bundle contains no owner, alias, album-link, SGF, rank or source-page writes. Verification checks unchanged scoped albums, exact qualified owner ID, KO display, generated coverage for every captured Weng slot and the retained English source name.

## Corrected Important findings

1. **The initial exact-preimage checks were outside the write transaction.** Initial `run_native` checked catalog, complete owner and physical albums on separate connections, then called `apply_bundle`. Native format 1 does not itself enforce the catalog supplement, and inventory does not cover every physical album/SGF field. A change between preflight and lock acquisition could therefore commit before the post-apply comparison reported it. `check_captured_write_scope` now runs inside the native `_locked_write` connection before `yield`, closing that gap.
2. **The initial helper rejected a valid retry after success.** Its latest-batch equality and KO-null prechecks always failed after the first successful apply, so native `already_applied` was unreachable. The corrected guard identifies the exact existing bundle and permits only its applied replay path; pending/undone records are denied, while native integrity checks still run.

The requested physical owner preservation was also completed: all capture/guard/verify owner reads now use `physical_owner()` rather than the old three-column ORM selection.

## Quality and verification

The corrections are confined to this single-use helper and reuse the original importer; they introduce no alternate approval or write implementation. The native context manager is restored in `finally`.

Independent checks performed:

- Compiled the final helper and recomputed its SHA-256.
- Validated both actual final pending research records and confirmed their Weng anchors are byte-for-byte equal as JSON values to this reviewer's previously signed anchors; no new candidate signature was created.
- Inspected actual r7 `_locked_write`, `_inspect`, inventory/catalog checks, approved replay and bundle-format validation to confirm the helper's calls and lock placement.
- Executed bounded in-memory guard branches with stubbed reads: new write accepted, exact applied replay accepted without the null-target branch, pending prior bundle denied, latest-batch drift denied, and drift in an unmapped physical owner field denied. All assertions passed. These checks created no database connection and executed no SQL.

No SSH, SQL, Git, candidate approval or deployment operation was performed in this review. Native capture/dry-run/apply and deployed readback remain root's subsequent execution checks; this report approves the helper code only.

## Bounded follow-up: disable connection reuse — PASS

Reviewed the added `from sqlalchemy.pool import NullPool` and `poolclass=NullPool` argument in `engine_from_environment`. New script SHA-256: `09ec0dd8c0d5f9b4a7ed62f310579ff5119cc5a7d17ab49a72c3ebd868a05d1f`. Removing exactly those two additions reconstructs the previously reviewed SHA-256 `3b4d8518ffe2fd612e5746da41ad3bbf01c40147810fcd573d8b4ca97b2608d6`, proving the remaining source, including all scope/transaction guards, is unchanged. The final file compiles.

For this one-shot CLI, opening a fresh DBAPI connection for each checkout preserves the supplied read-only connection startup option without reuse of a connection whose readonly setting was reset by inventory execution options. Read-only checks still fail closed, and the apply connection retains the original native locked transaction. No broader retest or database operation was performed; root will retry the real capture.
