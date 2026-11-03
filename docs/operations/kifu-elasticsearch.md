# Kifu Elasticsearch operation record

The business database remains PostgreSQL. This release replaces only the library search projection and its prepared PostgreSQL relations. Full SGF, analysis, frozen ranks, receipts and audit journals remain in PG.

## Release identity and evidence

- Base: `07d1ddce9e8808fa6c7b840e1a0cd928048ac4bd`.
- Feature: `feature/kifu-elasticsearch-gemini-20261031`, sibling worktree `/Users/fan/Repositories/katrain-elasticsearch`. Prior implementation came from `feature/kifu-elasticsearch-20261030`; continue only in the new worktree. Handoff: `../superpowers/handoffs/2026-10-31-kifu-elasticsearch-gemini.md`.
- Approved plan: `../superpowers/plans/2026-10-30-kifu-elasticsearch-search.md`, including section 0.1 language decisions.
- Read-only TEST snapshot on 2026-10-30 06:29:40 UTC: 176949 albums, 176690 visible; 31 complete JSON cases. Definitions and snapshot counts are in `kifu-elasticsearch-cases.json`. Full oracle is private mode0600, SHA256 `db5d71fb4563aeff580956509e9b60fee5378e13d96b9355f03a597b972051a5`.
- Runtime/index/performance and cleanup records must be appended from actual operations. Code tests do not constitute production acceptance.

## Modes and credentials

`KIFU_SEARCH_BACKEND` is explicitly `legacy` (default) or `elasticsearch`; an invalid value fails configuration. ES has no per-request fallback. Operator fallback sets `legacy` and reloads the actual Web package; that reader no longer imports prepared tables.

`KIFU_SEARCH_SYNC_MODE` is `disabled`, `bootstrap`, or `enabled`. Bootstrap requires the explicitly quiescent initial-build window. It must not become an unattended fallback. Before collector admission resumes, the actual publisher/receiver and TEST cron must load the published package, normal writer credentials, and active alias. After a failed bootstrap, retain legacy plus explicit disabled synchronization and report that search release incomplete.

`KIFU_ES_URL`, `KIFU_ES_INDEX_ALIAS`, and `KIFU_ES_CA_CERT` identify the private HTTPS service. Read, writer, and admin credentials use separate `KIFU_ES_<ROLE>_API_KEY` or username/password variables. Never place credentials, private CA keys, full oracle responses, or SGF in Git or public logs. Web credentials have no write/delete permission.

One physical index contains album, finite classification/public-player documents and one sync state. All album queries require `doc_kind=album` and visible=true. `display.<lang>.event` uses keyword plus one selected words multi-field; no duplicate event-search source text. `date_sort` remains a keyword, including zero month/day. ES stores no SGF or analysis moves.

## Initial build and cutover

Prepare and review packages, locked plugin image and configuration before acquiring the maintenance window. Stop new ingest admission and let native work finish. Keep the existing collector/stage/publication guards; never kill an in-flight publication or restart unrelated services.

On TEST, use the old CLI to disable prepared search before replacing any kifu package. Deploy the replacement with legacy reads and explicit bootstrap writes. Keep writers naturally quiescent through the all-metadata/albums read-only repeatable-read snapshot, one candidate build, language probe, first1000 measurements, full ID/visibility/classification checks and frozen complete-response comparisons. Set ready, refresh and atomically activate the alias; then verify real writer hooks and normal incremental credentials before precisely restoring the original admission control.

The entire initial build has a30-minute limit. The whole physical index store, including classifications and state, stops at2GiB. Budget10GiB new peak space per host; stop before remaining host free space falls below15GiB. Do not pre-credit old table reclamation. Record image layers, index store/translog, logs, RSS, CPU and df independently. Restore temporary refresh/control state and delete only a specifically unreferenced failed candidate after retaining small audit statistics.

Keep1primary/0replicas,2CPU/2GiB container and1GiB heap. This is a rebuildable single-node replica, not ES high availability. Existing Web/PG allocations remain unchanged. ES port9200 is private or loopback only. Docker, JVM GC and application log bounds are separate in `deploy/elasticsearch`.

## Incremental failure and recovery

Each actual writer has a stable operation reference before PG changes. Pending increments the epoch while the original writer session locks remain held. Business commit precedes finite PG-current projection/bulk/refresh/ready. The original outer publication guard remains on its independent connection. The read path verifies the same concrete index, ready state and unchanged epoch both before and after search plus PG enrichment, including empty pages.

A known PG commit followed by ES failure remains pending and reports `search_index_pending`. Never claim rollback or automatically undo business data. Retry the original manifest/batch or the explicit finite recovery operation. Unknown commit outcomes remain pending until the existing receipt/journal resolves them. Do not overwrite another pending operation.

PROD recovery reuses the same verified manifest and original verification material through the existing restricted receiver. TEST never accesses PROD ES/database and the forced-command protocol is not expanded. Manual import writes its small0600 operation record before pending; recovery reads current source keys and does not claim that an interrupted business import succeeded.

## Acceptance and retirement

Accept the final cleaned package on TEST, then on actual PROD117.50.177.254. Full frozen JSON, exact total/order, all11 display-language inputs, public/authorized/raw scope, report/rank binding and every nonempty page preview are required. New event-word semantics use separately frozen positive/negative expectations; do not weaken the old oracle.

The hard performance run is actual PROD100fixedQPS×30seconds:3000 distinct complete samples; sent and correlated ingress within window≥2970;≤32inflight and≤2seconds drain; every full HTTP≤200ms; zero error, timeout, semantic difference or missing response. HTTPp50/p95/p99/max and>200count are recorded. Low1QPS/20ms and ASGIp95 are diagnostics. Deep pages/max page size and publication-window503/recovery are measured separately.

Public HTTPS and browser checks for 王星昊 and 吴清源 record first/repeat list and correct board timing, API/transfer/render segments, bytes and actual Content-Encoding. The5Mbps public path is separate from local PROD100QPS. Do not remove preview/rank/source fields to improve numbers. Galaxy/RK checks require legitimate session/device access; unavailable access is explicitly unverified.

After the replacement Web/cron/receiver, ES acceptance and legacy fallback are verified, run `scripts/kifu_search_retire_prepared.py --plan` against the exact schema/database. Apply only in the short original-guard quiescent window with the verified runtime SHA. The script drops only40whitelisted guards, their function and6derived tables using RESTRICT,1second lock timeout and30second statement timeout in one transaction. Unknown COMMIT responses trigger bounded fresh catalog inspection; no DDL automatically repeats. No CASCADE, business-table rebuild, VACUUM FULL or WAL deletion is permitted.

Record before/after relation bytes, PG volume/host df and WAL separately per host. Remove only task-owned, unreferenced containers, packages/build directories and images by exact ID/path. Keep the live Web/cron images and at most one usable legacy fallback image; never run docker system prune. Published feature/develop/Smartbox SHAs must match the actually deployed packages.
