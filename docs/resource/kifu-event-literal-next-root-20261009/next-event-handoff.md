# Next literal event titles after batch 595

This is a source and runtime handoff, not an approved owner or name batch. The completed English 122-owner / 938-game batch 593–594 is excluded from this scope.

## Frozen source and current baseline

| Source | Frozen candidates | Saved PROD games | Five-language proposals | Status |
| --- | ---: | ---: | ---: | --- |
| [`C76 source-only`](../kifu-event-title-c76-source-only-20261009.json) | 76 | 76 | 380 | Six reused cores; 76 edition/core/game titles. |
| [`Han174 source-only`](../kifu-event-title-next174-han-source-only-20261009.json) and [`saved scope`](../kifu-event-title-next174-han-saved-scope-20261009.json) | 174 | 198 | 870 | Fifteen cores; 172 titles have a `game` part. |
| Combined | 250 | 274 | 1,250 | Exact raw strings are disjoint; no normalized display duplicates within these proposals. |

The C76 file SHA-256 is `9a7d598997a577f7c67c20a6c0608d7f85062b8d759c93e5aaad88b970119218`. Han174 source SHA-256 is `14eca96b9bac71d507b24ecab22598a8014fc4c565b12bbe508b22b5364f91b4`; its saved-scope SHA-256 is `e5d2f886d1acc11133613130e5edeac52f45f2db0aac3403429b01ad8136dc79`. The saved IDs, counts and album/source paths are **lookup hints**, not current eligible public games. Both files pass local HEAD `sgf_chinese_mixed` pure-part validation for all 250 titles. No live TEST/PROD SGF GN/EV, owner, hidden/duplicate/selection, name-preimage or cross-catalog collision check has yet qualified them. The C76 [`deferred binding notes`](../kifu-event-title-c76-deferred-binding-20261009.md) describe the source provenance; their old advice to stop on a numeric PROD owner-ID mismatch should be read as a review hold, not a requirement that TEST and PROD share IDs. Resolve each current owner by unique exact raw spelling.

Actual PROD batch-594 baseline: 1,707/3,698 five-language players, 64/85 formal event types, 133,760 games with both player names, 43,027 strict complete cards, 39,853 games with five-language raw event display, and 250 hidden games. The strict card gain in 594 was 567 from exactly 938 English-title games. Batch 595 may change the player/card baseline; use its actual verified PROD progress before reporting any next-batch delta. Do not count the 274 saved Chinese-scope games as live coverage.

## Minimal native Chinese-mixed compatibility

The recorded pinned r4 native `raw_event_translation.py` SHA-256 `d97e8e88a4e484b684106e0b06296b372066645961b79647425154b5c5102499` rejected the first C76 `game` part before any database scan. Current local HEAD SHA-256 `5806eddd74484a1ecae40c81f8e67a13120b28d3afb30e2b793b27e87d423507` accepts all C76 and Han174 parts. Check the actual r5 importer module hash before release; the r4 result alone does not prove its current bytes.

If r5 retains that validator gap, transplant only the Chinese-mixed part support from HEAD [`raw_event_translation.py`](../../../katrain/web/kifu/raw_event_translation.py):

1. The `_POSITIVE_NUMBER` and `_MIXED_GAME = re.compile(rf"第?{_POSITIVE_NUMBER}局\Z")` definitions around lines 68–73. Reuse an existing `_POSITIVE_NUMBER` if the native module already has it.
2. In `_validate_chinese_literal_parts` around lines 180–194, allow `kind == "game"` only when `mixed`, and require `_MIXED_GAME.fullmatch(part["text"])`. Keep lossless concatenation, one `core`, unique kinds and the old Chinese-only profile unchanged.
3. In `validate_raw_title_research` around lines 247–257, make the same `mixed_sgf`-only `game` exception and exact `_MIXED_GAME` check. Keep SGF scope, owner approval and five-language provenance gates unchanged.

Do not copy the full modern module or ORM into the older importer. This is a validator compatibility change for existing parser parts, not a parser, product-reader, schema, SGF or event-identity change. The existing source-only `selection-v1-mixed150.json` also contains 72 English titles: 49 are in completed batch 594 and 23 remain outside its approved scope, so it must not be used as the next write selection.

## Fresh post-595 binding

For an early batch of at most 150 owners, one deterministic source-only proposal is all 76 C76 titles plus the first 74 Han titles sorted by `(-saved_inventory_game_count, raw_value)`: 150 raw titles, 750 proposed cells and 174 **saved** games. This is a prioritization hint, not an eligibility or approval count. Hold any raw whose current exact owner/parts, first SGF GN, empty EV, public NULL event, duplicate/hidden/selection state, five-language name preimages or normalized-name collision differs. The remaining Han titles can follow in another batch; the historic Hoensha label and the 32 English duplicate-display spellings stay outside this proposal.

After 595 closes and the minimal ZH validator is in the pinned native image, take one read-only repeatable capture per environment for the finite Chinese selection. Capture unique exact raw owner and current full image, existing parser parts, all current names/evidence, complete linked album IDs and physical fields, SGF hash plus first GN/EV, catalog/inventory/registry hashes and verified-name collisions. Derive the actual passing TEST/PROD intersection and independently review an owner-only plan (maximum 150). Only after both owner applies verify should fresh post-owner captures bind pending format-2/4 name bundles and current NULL preimages for a separate root name review/apply. Reuse the established shared core lexicon once; literal sponsor/series wording does not require exhaustive external history research or assert a new formal event identity. Count display coverage only from actual qualified post-apply reads.
