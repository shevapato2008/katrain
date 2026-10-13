# Honinbo v2 importer bundle draft (2026-10-02)

Prepared a protected, unsigned `bundle_format=2` draft for event ref `honinbo-series-2026-10-02`, canonical name `本因坊戦`, 11 language members, and the exact 1,617 ordinary `event` links. All 1,617 `identity_review.status` values remain `pending`; this file does not approve an identity mapping or authorize a write.

## Pinned artifacts

The protected bundle and manifest are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-v2-bundle-draft/` (directory mode `0700`, files mode `0600`).

- `honinbo-series-2026-10-02-v2-bundle.draft.json`: byte SHA-256 `15747021dd15d5eacb942ed257a68ca4d15830932812fa1bb36fbc865ad5b3c3`; canonical bundle SHA-256 `684c6a86c2eb10154fd360efeb239adee740279127d2f7e3d5ed403382aa2a66`.
- `bundle-draft-manifest.json`: byte SHA-256 `038199d8955c9581dfa33c401ddce1e3421f7496ec0d76f0b01503b5c245728b`. It records input hashes and the 34 raw-value scope hashes.
- Current production catalog SHA-256: `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`, captured at `2026-10-02T14:16:27.391009Z` in a `REPEATABLE READ READ ONLY` transaction on `ucloud-v100`; transaction rolled back. The same snapshot had zero exact canonical-name matches and zero normalized event-alias matches for `本因坊戦`.
- The source-reviewed candidate artifact remains unchanged (byte SHA-256 `c9698402c05fa9863cc024c11f53b30229cd435c132620b4acf4775086bb9001`). The bundle contains pending final-review copies with source-review signatures removed. It does not turn source approval into approval of the later preimage binding.

## Validation and blockers

I ran the read-only v2 bundle validator against registry `.5`, the pinned inventory, and matching research JSONL. It reports `ready=false` and `write_ready=false`, as expected for this draft. It found 1,617 unapproved identity links and 11 missing `preimage_binding` records. The 11 member/candidate linkage errors are downstream of the pending links, which the validator does not count as approved targets.

Each exact raw group has a frozen `scope_frozen_at` and computable `scope_sha256`. Its `source_checks` array is empty: the input memos support the series boundary and game binding, but this draft does not attach independently checked per-link source excerpts with retained body hashes. Adding such evidence changes the identity-scope input, so recompute the corresponding scope hash after the reviewer completes that evidence. Do not change any scope to `approved` before that review.

The candidate copies also lack `preimage_binding`. Each new event language row correctly has `name_preimage_sha256: null`; a distinct binder still needs to record actual `actor_id`, `actor_model`, `captured_at`, `bound_at`, the same null value, `source_candidate_sha256`, and the preimage capture hash if a capture file is used. The candidate review must follow binding and be by someone other than the source producer and binder.

## Independent Sol handoff

For each of the 34 exact raw values, inspect the frozen album links and their complete context, the edition identity review, game-binding audit, retained source records, and any exceptions. Attach real source checks (`url`, captured `body_sha256`, exact `body_excerpt`, and `identity_match`) and substantiate `identity_basis` plus `event_period_basis`. Record authentic `producer_id`, `producer_model`, and `produced_at` for the frozen link preparation. Recompute one `scope_sha256` for the complete target/raw group and copy the same review object to every link in that group. Then fill `status: approved`, actual independent `reviewer_id`/`reviewer_model`, `reviewed_at` later than `scope_frozen_at`, and a precise `review_conclusion`; the reviewer must differ from the producer. Do not invent missing producer or reviewer metadata.

Then bind the 11 null name preimages using the steps above, create a new candidate copy with binding metadata, and have a reviewer independent from both candidate producer and binder sign all 11 rows after binding. Recompute `link_set_sha256` and any dependent bundle hashes, then rerun offline validation. Production apply still requires a fresh current-snapshot check and the established isolated-copy dry-run/apply/conditional-undo gate.

No database or SGF writes, code edits, changes to existing documents, or commit were made.
