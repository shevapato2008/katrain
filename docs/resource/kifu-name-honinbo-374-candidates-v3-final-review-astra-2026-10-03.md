# Honinbo v3: final independent review of 374 composed candidates

**PASS — the exact 374 composed candidate copies are independently approved.** The new finite bundle contains **385 approved names** (11 preserved series bases + 374 edition displays), 34 raw owners and 1,617 preserved identity links. Offline API validation and the actual `scripts/kifu_name_batch.py validate` command both return **`ready=true`, `write_ready=true`**, with zero errors, write errors, pending, rejected or missing candidates. This is not a production-release or full-localization approval.

Reviewer: `/root/oza_ua_display_decision_astra`, parent-configured `gpt-6-astra` / max, without runtime attestation. Actual signature time: **2026-10-02T18:31:19.236956Z**. Input: [v3 producer/preimage memo](kifu-name-honinbo-374-candidates-v3-preimage-pending-2026-10-03.md), retained SQL/capture, source/bound candidate files, manifests, earlier signed dependencies, frozen inventory and registry `.5`.

## Producer/binder independence decision

The disclosed producer and binder are both `/root/honinbo_final_candidates`, model `inherited/unverified`. The [review runbook](kifu-name-review-runbook.md) and current validator require the final reviewer to differ from both roles; they do not require the producer and binder to differ from each other.

**For this finite batch, I accept that disclosed role combination and explicitly replace the separate-binder workflow step in the earlier Honinbo memos.** I independently recomputed the complete capture, actual null preimages, every archived source-candidate hash and the binding chronology. The final reviewer is independent of both roles, source authorship is preserved, and every write-time preimage/snapshot check remains required. A third actor repeating this mechanical binding is unnecessary. This decision does not authorize a producer to approve its own candidates or invent missing preimages.

## Independent checks

- **Dependencies and timing:** all 34 category declarations, the complete scope and eleven rule records exactly equal their signed artifacts. The candidate producer time `18:13:08.047666Z` is after the latest rule approval `18:08:12.461696Z`. Capture runs from `18:14:28.912084+00:00` through `18:14:29.622795+00:00`; binding is `18:17:13.459128Z`; this final review follows both. All dates are 2026-10-02 UTC. The eleven base candidates and 1,617 link reviews remain unchanged.
- **Production capture:** independently checked the retained `REPEATABLE READ READ ONLY` SQL ending in `ROLLBACK` and its transaction-boundary records for `katrain_prod_20260725`, snapshot **`1603055:1603055:`**. Recomputed all six catalog tables to SHA-256 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`. Both raw-owner and both raw-name tables are empty in this complete capture, supporting the 34 absent raw owners and **374 explicit null name preimages**.
- **Exact cohort:** all 34 raw-value occurrence sets and counts match the frozen inventory and signed scope. The same **1,617** albums have null event IDs; all compared original/player/date/round/rank/duplicate/link fields and all production SGF hashes match the signed links and frozen inventory. No adjacent raw spelling is admitted.
- **Collisions:** independently compared all **4,485 existing name rows, across all statuses**, against the 385 proposed names; zero normalized collisions. The proposed series canonical name has no normalized existing canonical/alias collision. All 385 proposed locale/name keys are distinct.
- **Candidate binding and outputs:** every bound row differs from its archived unbound source only by the two preimage fields. All 374 `source_candidate_sha256` and `capture_sha256` references resolve to their actual files/objects. Every row binds its exact raw owner/value, edition, full approved rule record, same-language base and raw scope. Independent expansion of all 374 displays matches the importer renderer byte for byte, including every ordinal/case/spacing branch. Display-map SHA-256 remains `ba6fbbe44090ba2ef0c9ea537aceb2c94d29c201ce59ce2f0317c334ed1da793`.

The pending bundle independently reproduced exactly its 34 missing-approval errors and zero write errors. I then signed only the 374 composed copies, preserved all preimage metadata and earlier signatures, recomputed every candidate review hash, and validated the saved final bundle successfully. No additional product test suite was needed for this data-only review.

## New protected outputs

Directory: `/Users/fan/.local/share/kifu-name-audit/2026-10-03/honinbo-final-review-astra-v3/` (mode `0700`; files `0600`). The manifest records all **374 individual source/bound/final candidate hashes**, input pins, approved dependency hashes, captured-state checks, the role decision and final validation result.

| Artifact | Byte SHA-256 |
| --- | --- |
| `honinbo-v3-composed-bundle.final-reviewed.json` | `80628846722928263fbe64971c11e492293fe95243f79e42a289c07ce9bf26a8` |
| `honinbo-34x11-candidates-v3.final-reviewed.jsonl` | `09b349c2b234e037f68031e8f74e61195446e9f035c0b4ee118107ad5f01125c` |
| `final-review-manifest.json` | `17d9a444bf584026c6c977a3f2876145bab84ea91863e3c66b3f96df4503454d` |
| `offline-validation.json` | `01f7c99a923aef759b7d307f8a4864e55ec1fff70f0d9738ac260b4ae840e1b0` |

Final bundle canonical SHA-256: **`c142e9a5c81335c1fe82f9118c5add3059ff432b9cef4d2e561f67813b5bb3c8`**. Complete 385-candidate list canonical SHA-256: `65b9cb0a4e72f57581fc888a564a518b0cdd336c8ba3296a2a7e30ac175c6cea`. The 374 composed-candidate list canonical SHA-256 is `9617824bd7c1d607d0eddcbcee6fca3b5d5757604ed035d4da0c206dcef95ab2`.

Pinned original bound bundle: `d93b7ffa85d7b01bf3a6592a310eaac4b90f285e404de63a48f3d7b64f07edbc`; source pending bundle: `a0a17e40d7e92594c1f0450dd37d55b50877bc45dc4773a422ccfedf3a815121`; production capture: `92d09b6dbe14c95831865ec459d9271b2da34c6da6bad1b87f97c93931736680`. These and all earlier artifacts are unchanged.

## Reproduction and remaining gates

Use the batch's pinned registry at `~/.local/share/kifu-name-audit/2026-10-02/honinbo-clone-rehearsal-sol/registry.5.json`, canonical SHA-256 `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`. The repository default is `.2` and cannot validate this `.5` bundle. The successful CLI used that explicit registry, the existing `2026-10-02/kifu-name-inventory-prod-v2-20261002.json.gz`, and `2026-10-02/honinbo-final-review-astra-v2/validator-evidence.jsonl` (evidence byte SHA-256 `a000df1ad82b01a00945c3384ba3c299fc443f2f0fa4fa17d0cd4d784f9c4470`).

`ready/write_ready=true` covers this finite base/edition/identity bundle only. The retained production query checked the exact cohort and catalog; **it did not recompute the full current inventory hash**. Fresh full-inventory/catalog/preimage checks and isolated-clone dry-run/apply/repeat/conditional-undo remain before a write. After import, real strict display/coverage must verify **17,787 Honinbo event-language slots**; both player slots and full eleven-language catalog coverage remain separate release requirements. No database, clone, code or deployed service was changed by this review.
