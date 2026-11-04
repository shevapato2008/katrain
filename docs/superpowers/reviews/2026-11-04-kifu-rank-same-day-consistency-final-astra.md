# Same-day rank consistency — independent Astra final code review

**APPROVED.** No blocking findings in `76693f11767900633921c0b20db0eb4e8734575f` against `bbcc3af47`, under the plan approved in round two.

Only `historical_ranks.py` and two focused test files changed. The additional target-day equality condition in `_qualification` closes the stored-cohort gap independently of which targets share a repair part: an original bare 7 on the target day prevents refining another original bare 9 to professional 9p. Earlier compatible progression, equal target-day values, future exclusion and explicit source ranks retain their existing behavior.

`_incoming_rank_refusal` extracts the prior first-write predicates in the same order: professional maximum across all prior dates, nearest-basis interval, original root/name conflict, missing-grade handling, then system/value compatibility with exact target-day equality. The first-write caller preserves its owner/ID/date/self-reference filters and original static error messages. No guard was weakened.

Preparation applies this predicate only to already-validated original inputs, after it has selected a candidate from the stored cohort. Incoming originals never enter positive evidence selection. A fixed refusal priority makes multiple incoming contradictions independent of input order. Refusal leaves the original source grade/system, or unknown for a missing grade, with no inferred basis. The existing snapshot validator still validates every emitted decision. Resource limits, original body/source/owner verification, applied native replay, schema/policy/snapshot versions and repair `_replaceable` remain unchanged.

The preparation loop's unused `other_pid` does not introduce an unknown-owner authority path: inference first requires an existing resolved target owner, and the same explicit canonical reference resolves through `_owner` in the stable audit view. Unknown owner references cannot match that candidate. The first-write non-null-ID requirement remains intact.

## Independent verification

- Historical rank, historical repair and historical native suites: **140 passed, 2 opt-in PostgreSQL tests skipped in 19.24s**. The new cases cover stored targets alone/together/reversed, incoming order, earlier progression, same-day equality, future and missing-rank counterexamples, real native persistence/API output and exact receipt replay.
- A temporary in-memory differential check compiled the actual old and current `_verify_incoming_rank_observations` function bodies, replacing only database/source adapters with synthetic originals. Across **2,720** combinations of grade/system, date interval, owner and self-reference, acceptance/rejection and static error messages were identical. This checks guard extraction; it is not a PostgreSQL/concurrency test.
- Black for the three changed Python files and the complete committed diff whitespace check: passed.

No production query/write, service change, provider call or source-data filesystem access was performed by this reviewer. No new PostgreSQL run was needed for this predicate-only change; unchanged lock/query paths remain outside the new verification claim.

This is code approval, not authorization to reuse old code-bound manifests or a claim that the 149 committed HOME parts are correct. The approved plan still requires their exact receipt/journal-bound read-only requalification. Any differences require a separately reviewed finite correction before further data application; ordinary fresh audit continues to skip existing v3 rows.
