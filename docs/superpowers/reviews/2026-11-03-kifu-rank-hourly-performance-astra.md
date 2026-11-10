# Independent scoped performance review

**Verdict: APPROVED.** No blocking findings in the reviewed performance delta.

- Reviewer: independent Astra max follow-up; no delegated reviewers.
- Base: `c9e7db96d`, containing the previously approved feature and its review record.
- Candidate: `e92a1275b8f2c61dad964a9bc2907aa84a1a9509`.
- Reviewed commits: `264bba207287c7e35dfb294eb2e59cf721bc6292` and `e92a1275b8f2c61dad964a9bc2907aa84a1a9509`.
- Scope: the two production modules, their regression tests, and [the performance addendum](../plans/2026-11-03-kifu-rank-and-hourly-consistency-performance.md). The proposed operational restoration wrapper is outside this delta and requires its separate review.

## Integrity review

At `katrain/web/kifu/historical_rank_repair.py:139`, source-v2 selects only the batch hash/status and exact journal afterimage. The omitted JSON fields were not used by that branch. The target batch/table/row predicates, applied status, complete afterimage equality and `source-rank:` hash binding remain unchanged. Native-v1 still selects `publication_format` and `publication_key` at lines 144–145 and validates both at lines 165–167. The public preparation regressions confirm that source-v2 emits no `reviewed_artifact` projection while batch-hash or journal drift remains a refusal and original records remain unchanged.

At `katrain/web/kifu/historical_ranks.py:337`, root-cache access first calls the existing `remember_body`. Thus entries remain limited to exact body hashes admitted by the operation's existing 256 KiB per-SGF, 500-body and cumulative 8 MiB limits, including its album-to-body consistency check. The cache belongs to that `EvidenceBudget`; a new operation starts empty. Values are immutable tuples of the original PB/PW/BR/WR/DT strings, not parsed trees, validation outcomes or rank decisions.

Lines 347–357 compare the current album names, ranks and date on every call, even on a cache hit. Storage occurs only after these metadata checks succeed at line 359. A new result dictionary is constructed each time. Calls without a resource preserve their former parsing behavior. Cached root extraction does not replace source-link/owner checks in `_validate_original`, fresh column reads in `_live_target`, exact live SQL body equality/length/SHA checks in `load_rank_body`, or target/basis CAS in `bind_rank_decision`.

No rank policy, portable snapshot fields, snapshot hashing rules, database schema, writer locks, historical qualification rules or compensation rules changed. The measured optimization is proportionate to the demonstrated repeated parsing and unused large-JSON extraction; no global cache or new persistence mechanism was introduced.

## Independent verification

On the fixed candidate, the reviewer ran:

```text
tests/web_ui/test_kifu_historical_ranks.py
tests/web_ui/test_kifu_historical_rank_repair.py
tests/web_ui/test_kifu_historical_rank_native.py
tests/web_ui/test_kifu_hourly_catalog_consistency.py::test_native_rank_exact_and_semantic_share_one_cumulative_body_budget
tests/web_ui/test_kifu_hourly_catalog_consistency.py::test_proved_exact_original_reuses_provided_body_without_second_reservation
```

Result: **124 passed, 2 skipped in 25.53 seconds**. This includes parse-once behavior across prepare/initial verification/bind, fresh-operation independence, cached-body metadata drift, invalid metadata rejection, body budgets, same-length original-body drift, native/repair replay, and the new source-v2 projection/CAS cases. The earlier 677-test suite was not repeated for this narrow delta.

Black at line length 120 passed for all four changed Python files. `git diff --check c9e7db96d..HEAD` passed. HEAD remained `e92a1275b8f2c61dad964a9bc2907aa84a1a9509` through verification.

The two skips require explicit disposable PostgreSQL opt-in configuration, absent from this reviewer process. The reviewer read the controller's prior `output/kifu-rank-hourly-20261103/pg-native-result.json`: passed, two native cases across three isolated schemas, covering child dedup/replay/undo/archive and portable v3 TEST/PROD/API/replay. This is separately attributed earlier controller evidence, not a new reviewer PostgreSQL run. The author-reported timings in the performance addendum and read-only SQL measurements were inspected as motivation; this reviewer does not claim to have independently rerun production benchmarks or a full census.

## Application boundary

These source changes intentionally change the historical repair's computed code hash. Future application must use a manifest prepared with the reviewed final source; an older frozen manifest must not be relabeled to evade its existing code-hash CAS. The old artifact remains useful as audit evidence.

This review authorizes no additional data or deployment scope. The reviewer changed only this report, performed no live database writes, restarts, configuration changes or provider calls, and did not read, list or traverse the filesystem under `data/kifu-album/`.
