# Exact next-event batch: execution notes

The script is `scripts/apply_kifu_event_next_scope_exact.py`. It pins Astra's decision JSON by byte SHA-256 (`84eace6d…32d5088`) and permits only the 743 approved exact album IDs (637 中日围棋对抗赛, 106 日本职业十杰战). It checks all 453 held rows in the same capture. No edition is assigned.

## Current evidence and status

- A fresh, read-only, repeatable-read PROD capture was taken from `ucloud-v100` / `katrain-ucloud-katrain-web-1` / `katrain_prod_20260725`, with rollback. It is `kifu-event-next-scope-PROD-capture-2026-10-04.json`; all 1,196 frozen identity and SGF preimages matched. PROD Japanese Pro Best Ten remains ID 44 and no exact 中日围棋对抗赛 catalog type or alias was found. The capture binds the current PROD player FKs.
- A TEST attempt against a database named `katrain_db` on the **PROD host** failed read only because that database has no `event_id` column. It is not the proper TEST deployment. The proper TEST deployment is `home-ubuntu` / `katrain-web`; its SSH gateway timed out once. No TEST capture or compared write plan has been produced.
- No DB writes or transactional dry run have been performed for this batch.

## Gate sequence

1. Run `capture` against the proper TEST database and save the JSON. The script validates the database name, all 1,196 exact IDs, raw event/date/date_sort/source/source_path, both player names, result, existing event/edition/duplicate links, and SGF MD5/SHA256. Its current player FKs and event catalog IDs are captured for TEST separately.
2. Run `plan` with the TEST and PROD capture JSON. The command revalidates both captures against the pinned decision, requires the same identity digest and exact approved/held IDs, and emits a SHA-256-bound compared plan. Differences in player FKs and existing event IDs are allowed across environments.
3. Run `dry` with that plan on each database. It locks albums, events, and aliases; recaptures current scope; inserts the one new canonical type only after the collision check; updates only approved `event_id` values with row-level CAS; checks all 1,196 postimages; then rolls back.
4. Only after review, run `apply` with `approved_plan_sha256` equal to the compared plan SHA-256. Then run read-only `verify` using the committed `applied_target_ids` from apply output. Each environment uses its own capture and target IDs.

For CLI use, supply a JSON payload file with `mode` and the fields described above; database modes also require `environment` (`TEST` or `PROD`) and `KATRAIN_DATABASE_URL`. The checked decision path defaults to `docs/resource/kifu-event-next-scope-independent-decision-astra-2026-10-04.json` relative to the repository. `plan` requires `TEST` and `PROD` captures; `dry`, `apply`, and `verify` require the complete compared `plan`.
