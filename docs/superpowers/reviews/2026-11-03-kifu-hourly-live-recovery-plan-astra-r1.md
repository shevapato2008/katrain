# Hourly live recovery — independent Astra plan review, round 1

**Verdict: APPROVED.** No blocking findings. No second plan-review round is needed for the reviewed scope.

Reviewed plan: `docs/superpowers/plans/2026-11-03-kifu-hourly-live-recovery.md`, committed as `0d293de330502064927ae811e5db5d05068bedf2`.

## Assessment

- **Canonical name coverage:** The proposed change addresses the observed failure at the correct boundary: determine the verified public canonical album, then apply the existing strict five-language checks to that album. Keeping journal verification, invalid/cyclic-pointer rejection and original source/receipt/rank bindings avoids turning a display alias into new name authority. The requested public-path regression and negative canonical/proof cases are sufficient for this narrow change.
- **Receipt lookup:** An expression index preserves the existing original-receipt query and its membership, conflict, row/byte and timeout guards. Testing the actual compiled query on PostgreSQL is necessary because expression compatibility determines index use. The plan includes this check, representative large unrelated artifacts, and an explicit concurrent migration with definition/readiness checks and bounded waiting. It correctly stops for evidence if that index does not solve the measured query.
- **Parallel read-only audit:** Disjoint target ranges under one exported REPEATABLE READ snapshot preserve the inventory used by the unchanged public preparation function. Importing before the first data read, keeping the exporter alive, preserving original part hashes, checking coverage and refusing incomplete output cover the relevant consistency boundary. Host resource limits and service headroom are explicit.
- **Recovery and release:** The plan preserves the current collection round, frozen publication keys, existing receipt retry phases, exact deployment revisions, and per-part first-apply CAS. The required real TEST/PROD publication and API/ES checks distinguish a completed recovery from a successful build or restarted service.

The audit implementation should apply the plan's existing identity requirement as follows: compare invariant global census fields once, aggregate partition-scoped counts and refusals once, and preserve the same common manifest fields, including `matched_at`. Target partitioning must not restrict historical basis queries. These are interpretations of the stated unchanged-public-function and global-identity requirements, not additional infrastructure or a new review gate.

## Review evidence and limits

Read the complete committed plan and the relevant current implementations of `catalog._coverage`, `catalog._source_records`, `catalog_standardization.verified_display_duplicate`, and the public historical repair manifest scope/census contract. The existing duplicate proof checks immutable journal ancestry and current members; the receipt lookup remains bounded and checks conflicting committed source records.

The live failure descriptions and Qwen/token counts are controller observations, not new measurements by this reviewer. This was a plan-only review: no product or test changes, database operations, service changes, provider calls or accesses to the prohibited source-data directory. Implementation and operational artifacts still receive the final code/operational review already required by the plan.
