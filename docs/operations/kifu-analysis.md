# Professional kifu analysis pilot

Professional SGFs remain in `kifu_albums`. Analysis jobs and position snapshots are in `kifu_analysis_jobs` and `kifu_analysis_moves`; personal `report_tasks` and `report_task_moves` are not used. A duplicate album with identical SGF bytes reads its canonical album's job. A changed SGF or model SHA makes the old job invisible to the read API.

The system is intentionally closed to automatic corpus admission. `CRON_KIFU_ANALYZE_ENABLED=false` is the default. The only admission command requires 1–20 explicit album IDs and defaults to a dry run:

```sh
KATAGO_EXPECTED_MODEL_SHA256=93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871 \
  python -m scripts.backfill_kifu_analysis 101 102
```

After checking the selected SGFs and available space, add `--apply`. This inserts idempotent pending jobs for canonical albums at 2000 visits per position. Start the cron worker with `CRON_KIFU_ANALYZE_ENABLED=true`. The interval job analyzes one position per run, commits it, then yields to pending personal reports and active high-priority live analysis before the next position. Pause `kifu_analyze` through the existing cron job control or disable the flag and restart cron. A stopped worker resumes from contiguous, depth-verified rows. After three failures a job becomes `failed`; an operator should inspect `error_message` before resetting it to `pending`.

The public read route is `GET /api/v1/kifu/albums/{id}/analysis`. It returns `unavailable` until a matching pinned SGF/model/visits job exists; partial `running` rows are visible. Only positions with `root_visits >= 2000` are returned. A completed job is downgraded to `failed` in the read response if any position is missing. Board mode forwards this read to cloud and reports 503 if cloud is unreachable.

Production must deploy the web schema before enabling the cron worker. The web schema creates the two new tables and unique indexes through `Base.metadata.create_all`; it never rebuilds the existing kifu or personal report tables. Keep full-corpus admission off until storage and GPU capacity are revisited. The 200 GB production disk has now been applied to the root partition and ext4 filesystem (194 GiB total, about 131 GiB free); the observed row-size estimate still needs indexes, WAL, and operating headroom. The measured V100 throughput would take years for ~34.8 million positions, so a small pilot must report its actual row size and throughput before any larger batch.

## Test-host pilot, 2026-10-02

On `home-ubuntu`, three explicitly selected canonical albums completed through one-off cron containers: `12087` (11 moves), `85633` (21 moves), and `151913` (27 moves, 2-stone handicap from 1851). All 62 stored positions, including position zero for each game, have `root_visits >= 2000`; the public read API returned `completed` for each with the pinned model SHA and no job failures. The first two games took 87.35 seconds together; the handicap game took 97.89 seconds. This is about 2.99 seconds per position on this test host, including one-off worker overhead. At that rate, 34.8 million positions would take about 3.3 years for one worker before user-work priority, so it is **not** a production completion-time promise.

The test rows averaged 2,650 bytes by `pg_column_size` across these 62 positions. The moves table occupied 319,488 bytes including indexes at this tiny sample size. Multiplying the row average by 34.8 million gives roughly 92 GB before indexes, WAL, and free-space headroom; this sample cannot establish a full-corpus capacity budget. The test-host Web integration was verified in an isolated image on port 18081 against the real pilot database; the normal test Web container was not replaced. The persistent professional worker remains disabled and no full-corpus jobs were admitted.

## Production rollout, 2026-10-02

The release candidate `release/kifu-report-20261002` (`ea2f9a67`) replays the transformer and professional-report commits on production base `42d28292`. Production Web and cron run `katrain-web:kifu-report-ea2f9a67` and `katrain-cron:kifu-report-ea2f9a67`. The transformer engine remains `katago-transformer:20261002-tf3-b11c768`, verified SHA `93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871`. Both Web and cron are healthy; `CRON_KIFU_ANALYZE_ENABLED=false` is explicit in the production Compose override.

The only admitted production album was `12087` (11 moves). Its one-off pilot completed 12 positions in 69.53 seconds; the live read API returned `completed`, 12 rows, and minimum `root_visits=2003`. No automatic corpus admission or persistent professional worker was started. After the pilot, `/dev/vda1` was grown online from ~100 GB to the full 200 GB disk with `growpart` and `resize2fs`; `df -h /` then showed 194 GiB total, 63 GiB used, and 131 GiB available. PostgreSQL and Docker stayed on the same filesystem and their services remained healthy. Do not schedule a larger batch until storage overhead and GPU capacity are decided separately.

Before migration, a compressed PostgreSQL backup was saved at `/home/ubuntu/katrain-kifu-release-ea2f9a67/production-before-kifu.dump` and verified with `pg_restore --list`. The partition table before expansion is saved as `vda-before-kifu-resize.sfdisk` in the same directory. The previous deployment settings are `/etc/katrain/ucloud.env.pre-kifu-ea2f9a67` and `/home/ubuntu/katrain-transformer/ucloud.override.pre-kifu-ea2f9a67.yml`. To roll back application code, restore those two settings and recreate **only** `katrain-web` and `katrain-cron` with the existing production Compose files; leave PostgreSQL, MinIO, KataGo, and the new additive analysis tables in place. The deployed artifacts and one-game runner are retained under `/home/ubuntu/katrain-kifu-release-ea2f9a67`.
