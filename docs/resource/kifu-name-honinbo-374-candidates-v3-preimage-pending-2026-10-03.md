# Honinbo 374 composed candidates v3: fresh pending bundle and production preimages

**All eleven importer-format locale rules are independently signed; the 374 exact raw-event display candidates remain pending final review.** This new v3 packet was produced at `2026-10-02T18:13:08.047666Z`, after the last [four-rule approval](kifu-name-honinbo-four-importer-rules-independent-review-astra-2026-10-03.md). It incorporates the 34 signed raw-category declarations, signed finite scope and seven signed locale rules from the [partial review](kifu-name-honinbo-composition-partial-independent-review-astra-2026-10-03.md), plus the four corrected signed rules. The eleven already approved series base rows and all 1,617 signed identity links are unchanged. Every one of the **34 × 11 = 374** rendered names matches the previously independently reviewed output map, canonical SHA-256 `ba6fbbe44090ba2ef0c9ea537aceb2c94d29c201ce59ce2f0317c334ed1da793`.

All new artifacts are under `/Users/fan/.local/share/kifu-name-audit/2026-10-03/honinbo-final-candidates-v3/` (directory `0700`, files `0600`). Producer and preimage-capture actor `/root/honinbo_final_candidates` records the inherited model as `inherited/unverified`; no exact runtime model is asserted. The older pending bundle and review artifacts were not modified.

| Artifact | Byte SHA-256 |
| --- | --- |
| Fresh unsigned `honinbo-v3-composed-bundle.pending.json` | `a0a17e40d7e92594c1f0450dd37d55b50877bc45dc4773a422ccfedf3a815121` |
| Fresh 374-row `honinbo-34x11-candidates-v3.pending.jsonl` | `c523a2bf24f97e81b91312584c1258aa8cdca17bf22b10396b9bd573280ef5ea` |
| Fresh source `manifest.json` | `51619e4bc3bb5064c41cf6012c82da5aeffa8b5153be43b87af0e3c3262d3d4c` |
| `capture-prod.sql` | `f22d931ca2fa8fc5d93d4d1838361bee34b09e505c29f96a58fd1f8d43c0a70b` |
| `capture-prod.jsonl` | `92d09b6dbe14c95831865ec459d9271b2da34c6da6bad1b87f97c93931736680` |
| `production-capture-analysis.json` | `933a7e5bf7b4f96bb158a2fbcfc3d334858b63b8fd6dd9bebaf97e1f53302615` |
| Producer-preimage-bound `honinbo-v3-composed-bundle.preimage-bound.pending.json` | `d93b7ffa85d7b01bf3a6592a310eaac4b90f285e404de63a48f3d7b64f07edbc` |
| Bound 374-row `honinbo-34x11-candidates-v3.preimage-bound.pending.jsonl` | `5c28d0a8bfd78502137a3175ccef1a5d73bde0d7f6103ec4866112d42bec3450` |
| `preimage-binding-manifest.json` | `68289a946ea11c29d84d9c4faf83b47c264663ac0657ee42d90a2aebbe714e46` |
| `validator.bound-pending.json` | `30830f16fa65b837067b408691e9e63a72f07928e40b4dc6c5496e703a924501` |

## Fresh production read-only capture

`capture-prod.sql` executed once on `ucloud-v100` against `katrain_prod_20260725` through `psql` in a **`REPEATABLE READ READ ONLY`** transaction ending with `ROLLBACK`. Its start/end are `2026-10-02T18:14:28.912084Z` / `18:14:29.622795Z`, both snapshot `1603055:1603055:`. The query read six catalog tables, four name tables, evidence rows and the exact numbered Honinbo album group. It issued no write statement.

The recomputed six-table catalog SHA-256 is still `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`. Both raw-value tables and both raw-name tables had zero rows; the 34 proposed raw owners and their 374 language-name preimages were absent. All **1,617** exact cohort albums still have null `event_id`; their compared raw fields and production SGF byte hashes match the signed links and frozen inventory. The 34 exact raw-group counts match. Across 4,485 existing player/event name rows, there is no normalized display collision with any of the 385 base or composed bundle candidates. No normalized `本因坊戦` canonical/alias collision was found.

At `2026-10-02T18:17:13.459128Z` the producer made a **pending** preimage-bound copy: each of the 374 new-name rows has explicit `name_preimage_sha256: null`, a hash of its unbound source candidate, the exact capture file hash and actual capture/binding chronology. The candidate producer and binder are the same actor, stated openly. An independent reviewer must assess and sign the exact bound rows; this copy itself claims no independent binding or final approval. The old eleven approved base-name preimage bindings were preserved.

## Validation boundary

The focused composition suite passed: `pytest -q tests/web_ui/test_kifu_name_composition.py` → **47 passed**. Re-running the v3 builder and binder produced byte-identical bundle and manifest files. The bound bundle's offline validator reports 385 members/candidates, 11 approved base rows, 374 pending composed rows, zero missing and **`write_errors: []`**. Its 34 general errors are exactly one per new raw owner because the corresponding language decisions remain pending. Therefore `ready=false` and `write_ready=false`; there was no isolated-clone dry-run, apply, repeat apply or undo for this v3 packet. The earlier [clone rehearsal](kifu-name-honinbo-v2-clone-rehearsal-sol-2026-10-03.md) covered only the base/identity bundle.

The production query verified the exact cohort and catalog, not the full 173,000-game inventory hash at this time. A later import still needs its established full current-snapshot gate, independent final candidate review, and isolated-clone transaction/undo rehearsal. Even a ready Honinbo event packet would cover only 17,787 event-language slots; both player slots and the full eleven-language release gate remain separate. No production or live test database row, SGF or deployed service was changed.
