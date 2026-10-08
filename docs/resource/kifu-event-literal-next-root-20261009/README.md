# Next literal SGF event titles: unsigned early selection

This directory is a source and binder preparation packet. It contains no database approval, signed plan, or applied name row.

## Finite selection

`selection-v2-english150.json` pins 150 exact raw strings from the collision-free part of the next212 source-only file:

| Source | Raw titles | Owner profile | Saved-snapshot games |
| --- | ---: | --- | ---: |
| next212, 150 largest collision-free English scopes | 150 | `sgf_english` | 1,571 |

The 1,571 saved games are selection guidance only. They are not current coverage. The 150 raw strings and 750 proposed CN/TW/JP/KO/EN displays pass the existing pure English parser and within-selection normalized-name checks. The source packet carries the 13 shared core translations once; this packet does not revise the translations or claim formal event identity. The 32 duplicate-display English proposals and the separate Hoensha historic label remain outside this selection.

The first proposed selection is preserved as `selection-v1-mixed150.json` and `source-packet-v1-mixed150.json`. An import-only check against the deployed TEST r4 image showed that its mixed-Chinese validator rejects a `game` parser part on the first C76 title. That check never reached the inventory or album queries. The source-only C76 and next174 Han proposals remain deferred until that exact runtime profile is supported and reviewed. `runtime-compatibility.json` records both code hashes and the hold reason.

## Fresh read-only capture

After the current r4 deployment closes, stage this entire directory on each corresponding remote host. Run `run.py` on `home-ubuntu` for TEST and `ucloud-v100` for PROD, sequentially:

```bash
python3 run.py TEST
python3 run.py PROD
```

`run.py` verifies the pinned native r4 importer image ID, borrows the running web container's database URL without printing it, mounts this directory read only, and writes one `ENV-capture.json.gz` file on the remote host. Captures are roughly 150 owners plus their complete linked album scopes and SGF references; actual compressed size is reported after the run. Run the two environments sequentially because each computes one full inventory hash. Copy both captures back into this directory and run `PYTHONPATH=. python bind_unsigned.py` from the repository root. It emits one finite unsigned English owner research manifest and a report of exclusions. The common translated core lexicon stays in `source-packet-v2-english150.json` once.

Each capture uses one PostgreSQL `REPEATABLE READ, READ ONLY` transaction. It pins the current inventory-format-4 and catalog hashes, owner full images and exact parser parts, all current raw-event name/evidence preimages, every album with the exact raw event, its original SGF hash and root GN/EV, and all selection, FK, hidden and duplicate checks. It records normalized collisions against verified names already in the database. Each environment resolves one current owner by exact raw value; archived owner IDs are PROD hints only. A PROD ID drift is held for review, while TEST records its current ID even when it differs from that PROD hint. Any mismatch remains a rejection in the capture. A rejected raw is excluded from an approval request; never silently remap its parser parts, scope, or display. The catalog helper uses the native three-field player image, avoiding the newer `authoritative_pages` column on older database schemas.

The owner reviewer must use the finite `sgf_english` manifest from the actual passing TEST and PROD intersection, no more than 150 raw owners per owner plan. `scripts/kifu_raw_event_title_owners.py` is the established owner tool. It changes only owner review fields; name binding requires fresh post-owner captures and the existing name-batch gate. Root handles independent review, signatures, SQL writes, verification and deployment. No title is counted as translated until five verified names display in both environments.

## Captured result

Both read-only captures completed against the pinned native images. The TEST gzip SHA-256 is `3030b7dba62edf83c715ed7adad73d3852983d441e50d7ce5950624aaa084057`; PROD is `729620a1ff34ab4384bbd93221ae5b93d80193584707943db4ba6a77484694b8`. Both physical databases expose `event_edition_id` and `list_hidden_reason`; the capture reads and checks their actual values separately from the older native ORM model.

The TEST/PROD intersection is **122 raw titles, 938 current public NULL-event games, and 610 proposed name cells**. `sgf_english-owner-research-unsigned.json` has canonical SHA-256 `170cd67ab820c50575d7dd65cceb43bd300acb7f4a9ee596fcf553e6c2cc9747` and passes the existing SGF English owner profile shape check. `sgf_english-name-matrix-unsigned.json` presents the exact five-language values and scope hashes for review, with shared core translations listed once. `binding-report.json` records 28 excluded raw titles: 25 fail the strict first-GN/empty-EV rule, and three have normalized matches to verified names on another owner. These remain unapproved and unwritten.

## Root-only owner review and admin wrapper

`owner-review-request-unsigned.json` is a review request, not an approval. Its canonical SHA-256 is `41c9c85ea1c2c0916f24c07835de30f7de8e8af895165847acc5bc7835c95ec1`. It pins the manifest, name matrix, both capture files, actual source producer `/root/event_literal_fresh_binding` and model `gpt-6-sol`. After the current player batch closes, root may independently review it and create a separate `owner-root-approval.json` with these exact fields:

```json
{
  "status": "approved_owner_review",
  "request_canonical_sha256": "41c9c85ea1c2c0916f24c07835de30f7de8e8af895165847acc5bc7835c95ec1",
  "manifest_canonical_sha256": "170cd67ab820c50575d7dd65cceb43bd300acb7f4a9ee596fcf553e6c2cc9747",
  "name_matrix_canonical_sha256": "d4a25340b2d2ac20ff138dd49c07f92ac726f882534e4dd5ad5de7ae88c8bab1",
  "reviewer_id": "/root",
  "reviewer_model": "ACTUAL_ROOT_MODEL",
  "reviewed_at": "ACTUAL_UTC_TIME",
  "review_conclusion": "ACTUAL_REVIEW_FINDING"
}
```

Stage the whole directory on each corresponding host. Root can then run these read-only modes sequentially:

```bash
python3 owner_run.py TEST prepare
python3 owner_run.py TEST dry-run
python3 owner_run.py PROD prepare
python3 owner_run.py PROD dry-run
```

`owner_run.py` pins the native importer image, borrows the running web database URL without printing it, and saves `ENV-owner-prepare.json.gz` or `ENV-owner-dry-run.json.gz`. The prepare artifact contains the existing tool's exact owner plan, pinned registry, 938-album physical preimage guard, and canonical plan SHA-256. The dry-run artifact must report 122 owners, 938 albums, zero name writes and zero FK writes. Its apply mode requires a separate root-signed `owner-plan-execution-approval.json` with both actual plan hashes. After a root-run apply, `python3 owner_run.py ENV verify` checks all 122 owner afterimages, the 122-row owner-only journal, absence of name rows, the complete scoped physical album guard and the unchanged inventory hash.

The wrapper adds only `list_hidden_reason` to the admin process's native `KifuAlbum` mapping after verifying the physical `VARCHAR(64)` column. It separately checks physical `event_edition_id` and all mapped FKs, ranks, SGF hashes, first GN/empty EV, selection and name collisions. The native inventory hash columns remain fixed. It creates no database table or schema change. Five-language name binding remains a later fresh post-owner step.

After both owner verifies, stage the updated `run.py`, `capture.py`, the v2 selection and source packet, and the unsigned name matrix in one directory on each host. Root runs `python3 run.py TEST --post-owner` and then `python3 run.py PROD --post-owner` on their respective hosts. These read-only modes save `ENV-postowner-capture.json.gz` only after all 122 approved owners, 938 exact first-GN/empty-EV album scopes, 610 collision-free display keys, physical FK/hidden/edition checks, and empty name/evidence preimages pass. The capture includes the current registry, catalog and inventory hashes and full physical album image hashes for the bounded scope.

After root supplies both fresh capture files locally, `PYTHONPATH=. python postowner_name_bind.py` emits `TEST-name-pending.json`, `PROD-name-pending.json`, `postowner-name-binding-unsigned.json`, and `name-review-request-unsigned.json`. The pending files contain format-2/4 bundles with 610 pending candidate records and 610 SGF literal research records per environment; they contain no name approval. Root independently reviews the request and writes `name-root-approval.json` with `status=approved_literal_name_review`, the request's canonical SHA-256, `allow_name_assembly=true`, and actual reviewer identity/model/time/conclusion. Only then may `PYTHONPATH=. python assemble_name_approval.py` copy that signature onto the candidates in two new approved bundle files. Live name prepare, dry-run, apply and verify remain separate root work.

The actual post-owner captures are now present. The unsigned name review request canonical SHA-256 is `a4f25eebdae53307c2b2a147981c57a53e6f244be9f8c00ebde1c4936b55f536`; the pending TEST and PROD artifact hashes are `502b6d0c451c477fa3e40f42d0527e08a372ab20dcc862f6fcc5d18e6281f272` and `1a85987a02902d6332248c78221a5fe59474cae8149c8da3c960e063ed7d1726`. `TEST-name-inventory-format4.json.gz` and `PROD-name-inventory-format4.json.gz` retain all 173,025 associations from the earlier matching format-2 base snapshots, then add the current captured empty format-4 event-selection supplement and full hash. Both pending bundles pass the existing validator with 610 pending and zero structural or write-preimage errors. They remain unready until independent name review.

After root's review and approval assembly, stage the approved and pending artifacts, request, root review, fresh capture, format-4 inventory, `name_inner.py`, and `name_run.py` together. Root runs `python3 name_run.py ENV dry-run` on each host. The read-only result must be ready, with 610 candidates and 938 affected albums. A separate root-authored `name-plan-execution-approval.json` must then pin `status=approved_name_bundle_execution`, `allow_apply=true`, the unsigned request canonical SHA, actual reviewer identity/model/time/conclusion, and per-environment current image ID, approved-artifact canonical SHA and bundle canonical SHA. Only then may root run `python3 name_run.py ENV apply`, followed by `python3 name_run.py ENV verify`. The apply wrapper adds a bounded 938-album and 122-owner guard inside the existing name-batch write lock, then calls the public `apply_bundle`; verification checks all 610 qualified literal names, 1,220 name/evidence journal rows, and unchanged album, owner, inventory and catalog images. This directory contains no name approval or apply receipt from this producer.

After PROD batch 594 verifies, root can run `python3 594_bounded_stats_run.py` on the PROD host. Stage the two stats scripts alongside the actual PROD name approval, post-owner capture, review request, apply receipt, and the sibling `592-PROD-progress-actual.json` baseline. This read-only runner checks the 594 name/evidence-only ledger, reads only the 938 captured album IDs through native `strict_slot_approvals`, and simulates the pre-594 event slot as empty. It measures the actual additional raw-event cards from games whose two player slots are already complete. Player and formal-event coverage inherit the actual 592 baseline; the output keeps literal raw-title owner coverage and distinct raw values as separate denominators. It writes `594-PROD-progress-actual.json` and `594-PROD-bounded-stats.json` without a full catalog completion scan.

## Actual closure

Both environments completed batch 593 owner apply/verify (122 owner changes) and batch 594 name apply/verify (610 names plus 610 evidence records). Each has 12 passing actual HTTP cases. The fetched PROD bounded result confirms 938 newly qualified five-language raw event slots and 567 additional strict complete cards; the actual report now shows 43,027 strict complete cards and 39,853 five-language raw event games. Player completion remains 1,707/3,698 and formal event completion 64/85. The product-qualified literal raw-title owner count is 9,650 against 50,222 distinct raw event values in albums; these are separate from formal event identities.

`archive_593_594.py` created the bounded actual archive at `../kifu-incremental-applied-2026-10-05/kifu-event-literal-593-594-20261009.json.gz` (file SHA-256 `0ca041f0c504a9f1eddf6aa9f3f48f7fe5869fa51b3c6b8a7459569955229a14`). It includes the reviewed full bundles and research, source bindings, both captures, actual approval and execution receipts, HTTP observations, and PROD statistics. Full inventory payloads are referenced by hash only.
