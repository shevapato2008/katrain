# Hourly live recovery completion plan

> Use subagent-driven-development for the independent coverage/index tasks. Request independent Astra max plan review at most twice, then final code review until approved. Do not interrupt the active restored collection round.

**Goal:** Complete the authorized TEST hourly → same frozen package PROD release and the historical rank backfill, preserving original receipts, raw SGFs, name approval, token ledger and ES gates.

**Observed facts:** Restored round started 2026-11-03T09:10:23Z. Forty-seven natural Qwen calls returned HTTP 200; 48,573 tokens settled. New package `0ef14d…` failed before writing because an old signed raw-player scope contains verified duplicate alias 6086 → 907. Alias pointer context changed during the prior reviewed dedup; canonical 907 has all fifteen approved display slots. New package `2798fe…` hit the existing five-second bound while `_source_records` scanned JSON in 954 applied/name batch rows. Current source-identity integrity checks must survive both fixes.

## 1. Validate the actual displayed canonical coverage

Owner: coverage worker in the main feature worktree. Files: `catalog.py`, a focused regression test file.

- Reproduce the public native publish failure using a previously signed raw-player scope, a journal-verified display alias, and a fully approved canonical record.
- Resolve only verified display duplicate pointers to their actual public canonical albums; deduplicate canonical IDs before the existing five-language strict approval check.
- Keep original source/receipt IDs, SGF/rank bindings, immutable old proof, missing canonical language failures, invalid/cyclic proof rejection and native transaction rollback intact. Do not mint or broaden name evidence or permit an unapproved canonical name.
- Run the regression, negative canonical/malformed-proof checks and relevant existing native/dedup tests. Commit only owned files.

## 2. Remove the measured JSON receipt scan bottleneck

Owner: independent index worker; no overlapping source edits.

- Prefer a PostgreSQL expression index for the existing `status` / `reviewed_artifact ->> 'publication_format'` filter. Keep `_source_records` membership, orphan/tampered receipt checks, byte/row bounds and statement timeout unchanged.
- First validate compilation and the actual equivalent query on a disposable PostgreSQL schema with representative unrelated large artifacts plus native receipts. Show EXPLAIN uses the expression index and that lookup results, conflicting receipts and limits are unchanged.
- Add an explicit opt-in migration/operator path using the repository's existing SQL migration convention, never an automatic startup DDL or a new table. Verify index definition/readiness; document concurrent build outside transactions, bounded waiting, and handling only this operation's incomplete index. Do not discard a pre-existing differently defined index.
- Do not replace the original receipt authority with a registry filter merely to make the query faster. If the index cannot solve the measured live query, return evidence before expanding the design.

## 3. Finish the full rank audit without repeated serial corpus work

Owner: operator/repair worker, isolated maintenance launcher only; public repair decisions remain unchanged.

- The approved bisect fix `6e7fd527` cuts the actual 100-target preparation 9.800 → 6.015s; it does not justify a minutes-long whole-library ETA.
- Prepare at most four disjoint, contiguous album-ID partitions in isolated read-only workers, all importing one coordinator-exported PostgreSQL REPEATABLE READ snapshot. Hold the exporter until every worker closes its read transaction. A child must import the snapshot before its first data read.
- Each worker uses the unchanged public `prepare_manifest(album_ids=...)`, exports original finite parts and numeric progress privately. Keep source bodies out of audit artifacts. Per-worker memory/CPU limits must fit the host, with room for the online service.
- Require identical code/database/inventory/global census identity across workers, complete and non-overlapping target coverage, and every original part SHA. An incomplete/failed worker blocks data application. No rank writes before reviewing the final census/refusals and representative positive/negative decisions.

## 4. Integrate, release and prove recovery

- Independent Astra code and operational review of the final combined changes; focused regression and opted-in disposable PG checks. No broad unrelated test expansion.
- Merge latest develop into feature; publish feature → develop → Smartbox gitlink. Rebuild the exact release. Deploy compatible readers/receiver first; let the current round finish before replacing Cron. Preserve the restored full role configuration with the approved native helper and stopped backups.
- Build and validate only the reviewed PostgreSQL index on both actual databases with explicit bounded DDL and identity checks. Reuse fresh backups; record new catalog state before rank application because the restored collector may have advanced it.
- Recover the same frozen packages/publication keys through the original guarded queue, respecting committed receipts and retry phases. No state resets, invented success, skipped name approval or fresh translation of already frozen decisions.
- Verify at least one real same-package TEST/PROD publication, five-language API checks, same-key replay, indexed visibility and ready state. Report real projection/bulk/refresh time separately from the round.
- Apply reviewed historical rank parts one transaction at a time with the existing writer locks, ES-ready check and first-apply CAS; stop on failure, retain completed receipts and handle only the reported remaining scope. Keep raw SGF and old journals unchanged.
- Update RK3562 to the final parent/vendor release and verify actual Galaxy/Kiosk ranks, representative missing-rank fills, amateur/unknown counterexamples, and the original user page/session. Camera remains explicitly offline unless observed otherwise.
