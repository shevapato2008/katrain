# Test main database report synchronization — 2026-10-06

The dual-GPU batch wrote its results to isolated SQLite databases and then to
production. The home-ubuntu website reads the main PostgreSQL database, which
still contained only the four pilot reports. This caused the latest game to show
`not_started` in the test website even though its production report was complete.

## Completed synchronization

At 2026-10-06 06:13:58 CST, home-ubuntu main PostgreSQL contained the 60 requested
recent reports plus the four existing pilots: **64 completed professional jobs**.

- Previous 10: read-only production PostgreSQL export of albums 24171, 24169,
  24168, 24167, 24166, 24165, 24164, 24163, 24162, 24161.
- New 50: the existing `manifest-source.json.gz` and both `gpuN.results.json.gz`
  files in `/mnt/disk1/fan/kifu-analysis-50-20261006` on home-ubuntu.
- Inserted: **60 jobs / 12,664 analysis positions**.
- Source/target SGF mismatches: **0**. Every canonical album and raw SGF matched.
- Read-back comparison: every move payload, SGF identity, move count and job
  timing matched the source. Minimum actual root visits across all 60: **2,001**.
- Model SHA256: `93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871`;
  requested visits: **2,000**.

Public test API verified at 06:14:00 CST:

`GET https://go.sailorvoyage.top/api/v1/kifu/albums/24171/analysis`

Returned HTTP 200, `completed`, 211/211 moves, 212 contiguous analysis positions,
minimum root visits 2,003 and SGF SHA256
`d401e89779b33a2a0de6fc90149e762c2d8308138f8c9340a85a85ccb69dd0ef`.

No GPU analysis was started. Only `kifu_analysis_jobs` and `kifu_analysis_moves`
were written. The source production database was read-only; SGFs and personal
reports were not modified. No application image, endpoint or frontend was changed
by this data repair.

## Scoped synchronization tool

`scripts/sync_kifu_analysis.py` reuses the existing batch importer's SGF/model/depth
validation, album row locks, per-game transaction and idempotency. It supports at
most 60 explicit reports. All source payloads and all target identities are
preflighted before the first write; identities are rechecked under locks during
each transaction. It does not invoke KataGo.

Run within the desired database environment (the tool reads
`KATRAIN_DATABASE_URL`; do not put credentials into commands or artifacts):

```sh
python -m scripts.sync_kifu_analysis export \
  --album-ids 24171 24169 24168 24167 24166 24165 24164 24163 24162 24161 \
  --output previous10.json.gz

python -m scripts.sync_kifu_analysis import \
  --reports previous10.json.gz \
  --batch-manifest manifest-source.json.gz \
  --batch-results gpu0.results.json.gz gpu1.results.json.gz
```

The import command is a dry run by default; add `--apply` for the validated writes.
The three focused tests cover strict export identity/depth, rejecting a late
target mismatch before any writes, artifact integrity, dry-run behavior,
idempotency and preserving personal reports/SGFs. Result: **3 passed**.

Home evidence directory: `/mnt/disk1/fan/kifu-report-sync-20261006/` contains
`previous10.json.gz`, `preflight.json`, `applied.json`, `verified.json` and the
executed code. The previous-10 export payload checksum is
`e6de240c21e53c09081d8e53c159e95b3f91c90e292998b53600f97cc1a536d2`.

Before deploying unrelated web changes, note that the current image observed
during this repair was `katrain-web:geographic39-title-test-20261006` on home and
`katrain-web:geographic39-title-prod-20261006` on production. Preserve these later
overlays rather than restoring an older report-cache base image.
