# Next Chinese-mixed literal event titles: source and native preparation

This directory is **source-only and unsigned**. It contains no owner approval, name approval, database plan, SQL write, or claim that saved games are still eligible. Batch 595 is closed in both environments. Its actual PROD baseline is 1,723/3,698 five-language players, 133,895 games with both player slots complete, 43,107 strict complete cards, and 39,853 five-language raw-event display games; see `../kifu-next-source20-roster3-20261009/595-PROD-progress-actual.json`.

## Frozen proposal

`build_source.py` reads the pinned C76 and Han174 source files and writes `selection.json` plus `source-packet.json`. The rule is all 76 C76 titles in source order, then the first 74 Han titles sorted by `(-saved_inventory_game_count, raw_value)`. The resulting 150 exact raw titles have 750 proposed five-language cells and 174 **saved-inventory** games (76 C76 + 98 Han). These counts are prioritization hints, not current TEST/PROD eligibility or public coverage. No English title, historical Hoensha label, or formal event identity is in this selection. The source packet lists each reused core once per original source, with full literal names and parser parts per raw title.

Canonical SHA-256: selection `f06a6a87d600f3fa6d710ce35914f65534b0a11d257c749941c7dedcd48d43eb`; packet `eacd589a90178e806c7b76239d7d9444cbfc7d3d46f628b683e16eced6a928bb`.

## Exact native r5 compatibility

Root fetched both native r5 `raw_event_translation.py` files read-only. TEST and PROD bytes are identical, SHA-256 `d97e8e88a4e484b684106e0b06296b372066645961b79647425154b5c5102499`. `backport_mixed_game.py` accepts only those bytes, checks each replacement occurs exactly once, and writes a separate output source file. Its output SHA-256 is `0aab89aa5a93541dde26381254d3e9ff1a1a1dc6707b6089ba6fd6f473506b1f`. The diff adds only `_POSITIVE_NUMBER`/`_MIXED_GAME`, a mixed-only `game` part in `_validate_chinese_literal_parts`, and the matching `mixed_sgf` research gate. Existing Chinese-only, English, ordinal, owner, SGF, and provenance rules remain in place. No parser, ORM, product module, or full modern module is copied here.

Local pure-module check: exact old r5 validates 2/250 C76+Han parts; this backport validates 250/250. The backport still rejects non-mixed `game` and tested malformed game numbers. The 250 source records have no `round` part, so this backport does not add the unrelated mixed-round expansion present in local HEAD.

Root can generate the patch source with:

```bash
python3 backport_mixed_game.py /path/to/fetched-native-r5-raw_event_translation.py /path/to/new-patched-raw_event_translation.py
```

Root owns deployment and records the new TEST/PROD image IDs. Do not use the old r4/r5 image IDs in the capture runner.

## Fresh read-only binding

`capture.py` adapts the validated 593/594 capture to `sgf_chinese_mixed` with this 150-title packet. It reads one repeatable-read, read-only transaction per environment, resolving current owners by unique exact raw value. Archived numeric IDs are recorded as hints but a mismatch is not an automatic exclusion. It validates exact old parser parts, pending owner state, zero name/evidence preimages, complete linked album scope, full physical album image/SGF hash, first GN equal to raw, empty EV, NULL formal event/edition, no duplicate/hidden/selection, inventory/catalog/registry hashes, and normalized verified-name collisions. Pre-owner captures include the full physical album hash and exact source-packet canonical SHA-256.

After root builds the patched administrative importer image and stages this directory on each host, root runs each environment separately with its **actual importer** image ID. Existing web services remain running; this compatibility patch needs no web restart:

```bash
python3 run_capture.py TEST --image-id sha256:<actual TEST image ID>
python3 run_capture.py PROD --image-id sha256:<actual PROD image ID>
```

The runner checks the supplied importer image ID and its patched module SHA-256 independently of the existing pinned TEST r5 / PROD r4 web images. The web container supplies only the database connection and network. It writes `ENV-capture.json.gz`, without logging the database URL. Copy both files back here, then run `PYTHONPATH=. python3 bind_unsigned.py`. Binding requires both captures to pin the current selection and source-packet hashes and compares each captured raw/profile/source/owner hint/parts/core/five-language proposal with that frozen packet. A stale packet or changed captured proposal fails before any matrix is assembled; `check_source_binding.py` demonstrates both cases. Successful binding emits the passing TEST/PROD intersection as `sgf_chinese_mixed-owner-research-unsigned.json`, a finite five-language name matrix, and a rejection report. These are review inputs only. A title is excluded if either environment rejects its current state, has a verified-name collision, or has a different current album count.

## Owner and name helper reuse after capture

Actual fresh TEST and PROD captures each passed all 150 selected raw titles, 174 current public NULL-event games, zero rejections and zero normalized-name collisions. The unsigned manifest canonical SHA-256 is `aa8e33006d43f0b23736555a4b0a072e0f3c1311354a703f55d3ff300816f2e4`; the name matrix canonical SHA-256 is `5ff473a4fe24c7aedfc6b5283601d7996b2343341445ebb36fe50496de6a635d`. These are current eligibility observations, not owner or name approval.

`owner_inner.py` / `owner_run.py` adapt the 593/594 native owner-only path to `sgf_chinese_mixed`, the 150/174/750 scope, and actual r6 importer image IDs. `owner-review-request-unsigned.json` pins both captures, manifest, matrix, selection, packet, producer and importer images. `owner-execution-manifest-unsigned.json` records the intended order. The two `*-template.json` files have `template_only_not_approved` status and empty reviewer/plan fields; they cannot enable prepare or apply. Root must independently review and create separate `owner-root-approval.json` and, after seeing both actual plans and dry-runs, `owner-plan-execution-approval.json` with actual reviewer identity/model/time/conclusion and plan hashes.

After root's owner review, root stages this directory and runs `python3 owner_run.py TEST prepare`, `python3 owner_run.py TEST dry-run`, then the corresponding PROD commands. The pinned administrative image borrows only the existing web container's database connection and network. Prepare/dry-run do not write. The helper retains the native `prepare_plan` / `inspect_plan` / `apply_plan` locks, CAS and journal; apply is gated by the separate root execution approval. It checks each exact current owner preimage before apply, all 174 album IDs and full physical SGF/FK/rank/visibility hashes, first GN/empty EV, zero names and selections, and the 750 normalized-name collision boundary. The narrow in-memory `list_hidden_reason` mapping leaves `ALBUM_COLUMNS` fixed. Root verifies TEST before PROD apply.

After independently reviewed owner-only applies verify in both environments, root stages that environment's **own** `ENV-capture.json.gz`, `sgf_chinese_mixed-owner-research-unsigned.json`, and `sgf_chinese_mixed-name-matrix-unsigned.json` alongside these scripts, then may run `run_capture.py ENV --image-id ... --post-owner`. The matrix pins the exact pre-owner capture file hash and owner manifest. That mode restricts to the manifest and requires approved literal owners, unchanged exact owner ID and parser parts, no name preimages, and no collisions. It compares current album IDs, scope rows/hash, SGF references and full physical album-image hash against both the same-environment frozen pre-owner capture and manifest. Any drift rejects post-owner name readiness; changed owner review fields are allowed. `check_postowner_scope.py` demonstrates the pure scope guard locally.

`postowner_name_bind.py` is prepared for the later **offline** step only. Once actual TEST/PROD post-owner captures pass, it checks their frozen pre-owner capture, manifest, selection and packet pins and emits unsigned pending 750-cell format-2/4 name materials with original language `zh-Hans`. It does not assemble an approved bundle or write names.

`assemble_name_approval.py`, `name_inner.py`, and `name_run.py` now adapt the 593/594 name path to 150 owners, 174 physically frozen albums, 750 exact NULL name targets, 1,500 expected name/evidence journal rows, actual r6 administrative image IDs, and existing web image pins. They cannot run until root supplies fresh post-owner captures, matching format-4 inventory files, an independent `name-root-approval.json`, and the approved bundles assembled from the pending files. Dry-run is read-only. Apply uses the native name batch lock, CAS and journal behind a separate root execution approval. The guard checks unchanged owner review metadata, all scoped SGF/FK/rank/visibility bytes, no pre-existing name/evidence rows, the unchanged inventory/catalog, and the 250 hidden-game count; verify checks all 750 qualified translated names and 1,500 ledger rows. The expected next name batch is 597, but root must use the actual apply receipt as the authority. Root checks TEST before PROD. Owner and name approval remain separate root decisions. Count display coverage only from actual qualified post-apply reads.

## Corrected PROD progress after batch 597

The first 597 bounded result measures the new 174 albums and 148 newly complete cards, but r6 also restores older `sgf_chinese_mixed` `game` titles that the 595 r5 baseline rejected. Keep that first result as a diagnostic. `597_r6_correction.py` reconstructs the exact r5 pure module from r6 bytes, verifies both source hashes, and identifies older owners with five r6-qualified translated names and five r5-rejected names. It requires the unchanged r5-qualified owner ID set to match the actual 595 baseline and the restoration set to contain exactly 1,241 owners, disjoint from the new 150. It runs `strict_slot_approvals` only for the new 174 albums and public, unselected, visible albums of those older restored owners. The new output is `597-r6-PROD-progress-actual.json` with a separate correction audit; global player and formal event values remain inherited from 595. Root alone runs `python3 597_r6_correction_run.py` in the pinned r6 PROD importer image after reviewing the script. A source, owner, scope or batch mismatch aborts without an output file.
