# UCloud initial PostgreSQL restore — 2026-10-27

Completed on target `10-60-162-188`. Receipt status: `restored_initial_online_not_final`.
This is the online initial snapshot. Final stopped-writer consistency and production cutover remain controller tasks.

All 17 source files were rehashed (13 custom database archives + 4 globals). All 13 TOCs were readable and matched the immutable image major; all database restores exited 0.

| Source instance | Exact image version | Databases | Volume |
|---|---:|---:|---|
| `platform-postgres` | 15.19 | 2 | `lobby-pgdata` |
| `pitch-booking-postgres-1` | 17.11 | 2 | `pitch-booking_postgres_data` |
| `smartbox-kifu-postgres-1` | 16.14 | 2 | `smartbox-kifu_kifu_db` |
| `katrain-ucloud-postgres-1` | 15.18 | 7 | `katrain-ucloud_postgres-data` |

| Database / source instance | TOC | Restore | Tables | Sequences |
|---|---:|---:|---:|---:|
| `lobby` / `platform-postgres` | 0 | 0 | 14 | 3 |
| `postgres` / `platform-postgres` | 0 | 0 | 0 | 0 |
| `pitch` / `pitch-booking-postgres-1` | 0 | 0 | 35 | 0 |
| `postgres` / `pitch-booking-postgres-1` | 0 | 0 | 0 | 0 |
| `kifu` / `smartbox-kifu-postgres-1` | 0 | 0 | 8 | 2 |
| `postgres` / `smartbox-kifu-postgres-1` | 0 | 0 | 0 | 0 |
| `katrain_db` / `katrain-ucloud-postgres-1` | 0 | 0 | 30 | 21 |
| `katrain_import_preview` / `katrain-ucloud-postgres-1` | 0 | 0 | 30 | 21 |
| `katrain_prod_20260725` / `katrain-ucloud-postgres-1` | 0 | 0 | 79 | 56 |
| `katrain_slice1_20260725_baseline` / `katrain-ucloud-postgres-1` | 0 | 0 | 30 | 21 |
| `katrain_slice1c_20260725` / `katrain-ucloud-postgres-1` | 0 | 0 | 30 | 21 |
| `katrain_slice1c_20260725_baseline` / `katrain-ucloud-postgres-1` | 0 | 0 | 30 | 21 |
| `postgres` / `katrain-ucloud-postgres-1` | 0 | 0 | 0 | 0 |

Globals ran with `psql ON_ERROR_STOP` in one transaction per instance. Exactly one existing bootstrap-user `CREATE ROLE` was removed per globals file; ALTER/password and remaining role/grant statements were retained. Restored role password hashes matched source SQL in memory.
Restores used `--exit-on-error --clean --if-exists --create --jobs=4`, connected to `template1`, and kept owner and ACL restoration enabled. Database/object owners, extensions, sequence inventory and readable sequence state were checked; sequence counts matched archive SEQUENCE SET entries.
All four original PostgreSQL volume roots were checked after bootstrap shutdown: UID 70, mode 0700, and correct PG_VERSION. All four `migration-restore-*` containers were stopped and removed. No PostgreSQL volume was mounted and no container was running at handoff.

Known bounded PROD sample checks used a read-only transaction and did not read SGF content:
- `kifu_albums`: 176884; `tsumego_problems`: 21072; `tutorial_books`: 10; `tutorial_figures`: 7486.
- Rank history: 46 rows; rank snapshots: 54 rows.
- Albums 178743/178744/178745: six snapshots present; stored hash equals content hash and canonical snapshot body SHA256 matches for all six.
- Album 178743: black/white 9p/9p; 178744 white 9p; 178745 white 8p.
- Native rank snapshot links: batch 931 / `rank-only-page-coverage-20261026-v1` has 36 rows; batch 932 / `rank-only-current-page-tail-20261026-v1` has 10 rows.

RestoredVolumes (only these four PostgreSQL volumes):
```json
[
  "lobby-pgdata",
  "pitch-booking_postgres_data",
  "smartbox-kifu_kifu_db",
  "katrain-ucloud_postgres-data"
]
```

Concurrent controller-created `katrain-ucloud-minio-1` was Created/stopped, matched its original immutable image and Env, and mounted only its non-PG volume. The initial final whole-host-empty check exited 1 solely because of that container; a separate root-private finalizer rechecked PostgreSQL isolation and completed with exit 0. No restore was repeated, and the original gate failure remains in the receipt audit.
Preexisting non-PG volumes were left untouched by this restore and are not marked ready by this receipt.
Root free space at finalization: 46.3 GiB (15 GiB minimum; controller image loads continue independently).

Root-private evidence on the new host:
- `/var/lib/ucloud-migration-20261027/initial-database-restore-receipt.json` (root:root, 0600)
- `/var/lib/ucloud-migration-20261027/restore-initial-databases.py` (root:root, 0700)
- `/var/lib/ucloud-migration-20261027/sample-restored-production.py` (root:root, 0700)
- `/var/lib/ucloud-migration-20261027/finalize-initial-database-restore.py` (root:root, 0700)
- `/var/lib/ucloud-migration-20261027/database-restore/` (0700; logs and sample JSON 0600).

No changes were made to the old host, TEST, RK, gateway, DNS, VPN or ingress. No business service, production cron, model or collection job was started by the database restore operator.

## Read-only native artifact supplement

Corrected the earlier lookup: `KifuNameBatch.__tablename__` is `kifu_name_batches`. The empty result from `kifu_ingest_batches` was a wrong-table lookup and did not establish missing native artifacts.

After controller handoff, exact read-only transactions queried only IDs 931 and 932 on new `10-60-162-188` and old `10-60-219-118`, in `katrain_prod_20260725`. Both queries exited 0. No container, restore, job or business data was changed.

For each row, ID, status, bundle SHA256, publication key, and the complete `reviewed_artifact::text` MD5/SHA256/byte length matched exactly between old and new. Raw artifact JSON and SGF content were not output.

| ID | Status on both | Publication key | Artifact bytes on both | Artifact MD5 on both | Artifact SHA256 on both |
|---|---|---|---:|---|---|
| 931 | applied | `rank-only-page-coverage-20261026-v1` | 308171 | `c54907dab9d1d56153a4e49db705d2e6` | `e18f8b1f7b1e9955c6b632a7b57f3acd5e68636e2d741770be2d4bbd4350141d` |
| 932 | applied | `rank-only-current-page-tail-20261026-v1` | 82285 | `98c80fe6b6e85cd20588f06cc6854306` | `fa194ded66faaf4ebb04162e24a1df5e7ddea7d26bc9a6b55a192b2dcd3814fe` |

Bundle SHA256 matched on both hosts:

- 931: `7abc3136e13992127caf98bf670f6aa92e72b6651ca2f5092c3add8b9d549f44`.
- 932: `133dc7ae199afd5a3b692a45d2edff05480709753c910652354aeb45438254ce`.

Root-private supplement: `/var/lib/ucloud-migration-20261027/database-restore/native-artifact-compare.private.json` (0600).
