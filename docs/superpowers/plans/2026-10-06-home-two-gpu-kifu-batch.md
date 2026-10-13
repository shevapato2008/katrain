# Home two-GPU professional analysis batch

## Goal

After the report UI/backend deployment and real visual verification on both hosts, analyze another 50 newest canonical professional games on home-ubuntu. Use the pinned tf3-b11c768 model and 2000 visits; preserve personal/live services. Import completed snapshots into the production professional analysis tables.

## Deployment and visual gate

- Preserve each host's latest backend overlays; mount the same built static directory read-only.
- Galaxy/Kiosk HTML must revalidate (`Cache-Control: no-cache`). Preserve hashed assets.
- Check real professional reports at 2048×1080 and the shorter 1366×768 viewport, and real kiosk at 1024×600. Confirm board, fixed panels, tabs, uniform controls, report entry, move navigation and 3D. Capture screenshots; inspect actual deployed bundle rather than a fixture. Obtain a focused independent Astra visual review.

## Batch implementation

1. Export a frozen production manifest in a read-only snapshot transaction. Sort canonical albums by date_sort DESC NULLS LAST, id DESC. Exclude completed results matching SGF SHA/model SHA/2000 visits; exclude duplicate SGF bytes. Validate SGF and freeze exactly 50 IDs, raw SGFs, dates, move counts and identity.
2. Transfer the manifest with SHA verification. Split its games into two disjoint groups balanced by position count. Each GPU worker uses a separate SQLite database, never the production/test queues. Create the three kifu tables plus empty ReportTaskDB, LiveMatchDB and LiveAnalysisDB tables required by the worker's priority queries. The existing admission entry point is CLI-only: invoke it in subprocesses with explicit SQLite/model environment, groups of at most 20, then verify every identity was admitted (skips can still exit zero).
3. GPU0: temporary transformer engine with the verified existing image, model and device 0, listening on loopback 18002. GPU1: verified existing transformer on 8002. Each worker runs one KifuAnalyzeJob request at a time, with fixed model identity and its own SessionLocal. Existing persistent pro workers stay disabled.
4. A thin runner records UTC starts/completions, per-game elapsed seconds, positions and actual root visits. Resume from persisted rows. Use persistent job timestamps for wall-clock timing including downtime; rates are effective root visits per elapsed second, not GPU kernel benchmarks. Stop on persisted failure or sustained lack of committed-position growth; retain databases/timings on /mnt/disk1. Set each process's local database/model environment before importing cron modules. Hold a per-worker file lock to prevent duplicate local runners.
5. Export only completed, contiguous 0..N results with root_visits >= 2000 and matching hashes. Import each game in one production transaction: lock and recheck canonical album/SGF, remap job foreign keys, reject inconsistent partial existing data, and publish completed only after every row validates. Identical completed imports are idempotent. Write only the two professional analysis tables.
6. Verify all 50 production API results, record per-game timing and per-GPU/combined throughput. Remove temporary GPU0 engine and worker containers after completion; retain manifest/results/timings for resumption and audit.

## Focused verification

- Deterministic tests for selection/dedup, complete-range/depth rejection, and idempotent import only where new logic needs coverage.
- Dry-run the exact production manifest before admission. Verify both engine health model SHAs and physical GPU pinning before starting.
- Observe initial positions on both GPUs, production web health, disk growth and final row/API counts. Do not start a full-corpus batch or modify personal report tables.

## Focused Astra plan review (round 1, 2026-10-06)

- Reviewed by gpt-6-astra in task `01a10cfe-f7ad-7a23-ad91-9fd872cc8e00`; no second plan round needed.
- Addressed the empty queue-table dependencies, CLI admission/process binding, and explicit post-admission verification above.
- Export uses an explicit catalog query because the cron album model lacks date_sort. Export/import independently require exactly N+1 positions numbered 0..N: the existing worker alone does not reject every overlong stored range.
- Private worker databases cannot observe home personal/live queues. GPU1 shares its existing engine; the operator checks that workload at the visual/execution gate. This tool does not claim cross-database priority enforcement.

## Implemented CLI and artifacts

Tool: `scripts/kifu_batch_transfer.py`. It imports only cron/common modules, so production's cron image does not need `katrain.web`. Production export/import require `KATRAIN_DATABASE_URL` from the process environment. No connection settings are written to artifacts. The home image must also expose the existing `scripts/backfill_kifu_analysis.py` for subprocess admission.

Use `/mnt/disk1/fan/kifu-analysis-50-20261006` as the persistent host directory, mounted as `/batch` in one-off containers. Execute worker containers detached with host networking; an optional on-failure restart policy resumes existing rows. Transport/import supervision runs on home, not on a laptop or SSH terminal. Commands below run inside the relevant containers with `/app` on Python's import path:

```sh
# Production cron: read-only snapshot of exactly 50.
python -m scripts.kifu_batch_transfer export-manifest --output /batch/manifest.json.gz
# Transfer that frozen file to home, then initialize both workers.
python -m scripts.kifu_batch_transfer init-workers --manifest /batch/manifest.json.gz --work-dir /batch
# Separate detached home containers; ports are fixed to 18002 / 8002.
python -m scripts.kifu_batch_transfer run-worker --work-dir /batch --worker 0 --stall-seconds 600
python -m scripts.kifu_batch_transfer run-worker --work-dir /batch --worker 1 --stall-seconds 600
# After each worker exits successfully, export its completed shard.
python -m scripts.kifu_batch_transfer export-results --work-dir /batch --worker 0 --output /batch/gpu0.results.json.gz
python -m scripts.kifu_batch_transfer export-results --work-dir /batch --worker 1 --output /batch/gpu1.results.json.gz
# Transfer both bundles to production. First validate without writes, then apply.
python -m scripts.kifu_batch_transfer import-results --manifest /batch/manifest.json.gz --results /batch/gpu0.results.json.gz /batch/gpu1.results.json.gz
python -m scripts.kifu_batch_transfer import-results --manifest /batch/manifest.json.gz --results /batch/gpu0.results.json.gz /batch/gpu1.results.json.gz --apply
```

- `manifest.json[.gz]`: `kifu-batch-manifest-v1`, canonical JSON SHA-256, pinned model/visits, 50 production IDs/raw SGFs/hashes/dates/parsed counts. init-workers retains an identical uncompressed `manifest.json`.
- `gpu0.sqlite3`, `gpu1.sqlite3`: disjoint position-balanced assignments, durable worker state; local job IDs are scoped to each worker/database.
- `gpuN.timings.json`: per-game and per-GPU elapsed wall time and effective root visits/second, including downtime.
- `gpuN.progress.csv`: one row per completed game, flushed and fsynced after each completion; rebuilt atomically from committed state on resume. Columns: manifest_sha256, worker_id, album_id, started_at, completed_at, wall_seconds, positions, root_visits, root_visits_per_second.
- `gpuN.results.json[.gz]`: `kifu-batch-results-v1`, manifest/result checksums, worker/model/visits identity, per-game timestamps and validated snapshots. Import requires both disjoint shards covering all 50 before it writes. Valid completed production identities are preserved; partial rows must exactly match the incoming prefix.
- Validation: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_kifu_batch_transfer.py` — 12 passed. Tests use isolated SQLite and a mocked KataGo client; no remote execution was performed by this tooling task.
