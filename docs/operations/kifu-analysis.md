# Professional kifu analysis pilot

Professional SGFs remain in `kifu_albums`. Analysis jobs and position snapshots are in `kifu_analysis_jobs` and `kifu_analysis_moves`; personal `report_tasks` and `report_task_moves` are not used. A duplicate album with identical SGF bytes reads its canonical album's job. A changed SGF or model SHA makes the old job invisible to the read API.

The system is intentionally closed to automatic corpus admission. `CRON_KIFU_ANALYZE_ENABLED=false` is the default. The only admission command requires 1–20 explicit album IDs and defaults to a dry run:

```sh
KATAGO_EXPECTED_MODEL_SHA256=93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871 \
  python -m scripts.backfill_kifu_analysis 101 102
```

After checking the selected SGFs and available space, add `--apply`. This inserts idempotent pending jobs for canonical albums at 2000 visits per position. Start the cron worker with `CRON_KIFU_ANALYZE_ENABLED=true`. The interval job analyzes one position per run, commits it, then yields to pending personal reports and active high-priority live analysis before the next position. Pause `kifu_analyze` through the existing cron job control or disable the flag and restart cron. A stopped worker resumes from contiguous, depth-verified rows. After three failures a job becomes `failed`; an operator should inspect `error_message` before resetting it to `pending`.

The public read route is `GET /api/v1/kifu/albums/{id}/analysis`. It returns `unavailable` until a matching pinned SGF/model/visits job exists; partial `running` rows are visible. Only positions with `root_visits >= 2000` are returned. A completed job is downgraded to `failed` in the read response if any position is missing. Board mode forwards this read to cloud and reports 503 if cloud is unreachable.

Production must deploy the web schema before enabling the cron worker. The web schema creates the two new tables and unique indexes through `Base.metadata.create_all`; it never rebuilds the existing kifu or personal report tables. Keep full-corpus admission off until storage and GPU capacity are revisited. The 200G disk device observed on 2026-10-02 still had a ~100G root partition and ~35G free on the PostgreSQL volume; projected full-corpus rows alone exceed that. The measured V100 throughput would take years for ~34.8 million positions, so a small pilot must report its actual row size and throughput before any larger batch.
