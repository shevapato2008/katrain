# Bounded root-metadata reuse performance addendum

This is the measured implementation detail of Task 1's bounded original-SGF reuse in [the approved rank/hourly plan](2026-11-03-kifu-rank-and-hourly-consistency.md). It changes no policy, portable decision fields, evidence authority, database schema, or deployment scope.

The full read-only historical preparation exposed repeated complete SGF parsing for the same original body while validating the black/white slots, selected evidence, local bindings and initial qualification. Preparation already shared an operation-local 8 MiB body budget/cache; it did not share the pure root extraction.

## Measured baseline and result

A local SQLite public `prepare_manifest` benchmark used 100 target games, 200 changed slots, 300 moves per SGF, and roughly 3.3 KiB per SGF. The source case normalized `9pro`; the historical case refined CWI bare `9d` against one existing original `9p` game. A benchmark-only wrapper bypassed the new root cache for the paired baseline. It changed no repository files or persistent data.

| Public preparation case | Cache bypass, seconds | Operation cache, seconds | Ratio | Complete SGF parses before → after |
| --- | ---: | ---: | ---: | ---: |
| Source normalization | 1.3400 | 0.5791 | 2.31× | 400 → 100 |
| Historical type, two finite parts | 3.6014 | 0.9949 | 3.62× | 1200 → 102 |

The wall times above were measured without `cProfile`. The separate profiled runs showed exactly the same SQL counts before and after: 1,906 and 3,729 respectively. In the original profiled runs, root metadata validation accounted for 1.997/3.062 seconds (source) and 6.408/8.225 seconds (historical). Profiling adds overhead; those values are not production latency or a whole-library ETA.

A separate bounded read-only HOME sample of 100 real CWI albums (IDs 24173–24285, 144,239 total SGF bytes) measured 492/979/1,417 ms for two/four/six root validations per body. A profiled 100-call sample spent 512.6 of 515.8 ms inside `SGF.parse_sgf`. The database-repair worker separately identified expensive legacy artifact JSON extraction; that SQL change and its verification belong to its own patch. The root cache leaves those database queries unchanged.

## Cache contract

- `EvidenceBudget` owns the cache, so each finite operation/part releases it with its existing body cache. There is no global cache and no retained SGF tree.
- The key is the exact SHA of a body already registered through `remember_body`, preserving the existing 8 MiB/500-body limits. The value is an immutable tuple of original PB/PW/BR/WR/DT literals.
- `validate_rank_source_metadata(album, resource=...)` checks the current album names, ranks and date on every call. Only successful validation stores root literals; neither acceptance decisions nor invalid metadata results are cached. Calls without a resource retain their original behavior.
- Source links, canonical owners, raw columns, lengths, frozen SHA bindings and live scalar exact-text comparisons retain their existing fresh validation and locks. A changed body cannot reuse the old hash's literals.

Focused regressions verify one complete parse per original body across prepare/initial verification/bind, independent caches for new operations, rejection of changed database metadata against cached literals, and enforcement of the existing body budget. Existing same-length body drift, native/repair replay, and aggregate evidence-budget tests remain part of verification. This addendum does not authorize production data writes or claim that a one-hour interval is a running collector.

Verification on the feature worktree: `PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_ranks.py tests/web_ui/test_kifu_historical_rank_repair.py tests/web_ui/test_kifu_historical_rank_native.py tests/web_ui/test_kifu_source_rank_normalization.py tests/web_ui/test_kifu_source_rank_repair.py --tb=short` → **174 passed, 3 skipped in 27.17s**. The skips require explicitly configured disposable PostgreSQL test DSNs. Black and the scoped diff whitespace check passed. This is local verification; deployment and a fresh independent review remain controller-owned gates.

## Isolating invalid historical targets without replaying every cohort

A subsequent isolated HOME PostgreSQL profile called the actual public `prepare_manifest` under REPEATABLE READ / READ ONLY for album IDs 4501–4600. The normal complete census still covered 176,949 albums. Two invalid owner bindings caused the original 200-slot attempt to fail, followed by 200 single-slot attempts: **201 prepare calls and 198 cohort calls**. Target preparation took 14.524 seconds, including 12.201 seconds in cohort processing; complete SGF parsing took only 0.675 seconds. The full profiled call, including the census, took 45.752 seconds. These are bounded diagnostic measurements with profiler overhead, not a whole-library ETA. The result contained 23 historical-prior changes.

The repair tool now bisects only a group that raises a validation error. A failing single target remains an `invalid_original_binding` refusal. Valid subgroups retain batched cohort resolution and share the same existing `EvidenceBudget`; no new cache, table, policy field, or native publication interface is introduced. Original row/SGF/body limits and first-apply cohort/CAS verification remain unchanged.

Resource-deferred decisions do not raise and therefore never trigger subdivision. A valid subgroup can exceed a combined scalar limit even when its individual owners would each fit. Such a subgroup remains explicitly deferred; the tool does not retry smaller pieces to obtain a more permissive decision. This can conservatively reduce the qualified scope relative to the former single-slot fallback and must remain visible in census/refusal review.

Regressions compare all decisions and refusals for 100 targets with two invalid owners against the original single-target public resolver reference, while requiring at most 24 cohort calls. A separate combined-resource case proves that two newly deferred targets are not reported as repaired, that the invalid leaf remains refused, and that the remaining frozen decision passes the unchanged first-apply CAS path. The two repair suites passed **63 tests, with 2 disposable-PostgreSQL opt-in skips**.

After commit `6e7fd527ede926e894c81f40a6bb289ceee2826b`, an authorized independent HOME process compared the deployed baseline and a private copy of the candidate against the **same REPEATABLE READ / READ ONLY snapshot** for IDs 4501–4600. Both public calls performed the complete 176,949-album census and returned exactly the same 23 historical-prior snapshots, including their hashes, refusal counts and census. Nothing was applied.

| Real public comparison | Baseline | Candidate |
| --- | ---: | ---: |
| Prepare calls | 201 | 29 |
| Cohort calls | 198 | 13 |
| Cumulative observation rows | 54,763 | 43,185 |
| Target preparation, seconds | 9.800 | 6.015 |
| Entire public call including full census, seconds | 30.263 | 26.914 |
| SQL calls | 9,667 | 7,071 |

Grouped owner/date bounds make each remaining cohort larger, so fewer calls do not imply a proportional wall-time reduction. The measured target phase improved 1.63×; the scoped public call, dominated by the same full census, improved 1.12×. These results do not establish a whole-corpus ETA. Numeric evidence is retained privately at `output/kifu-rank-hourly-20261103/repair-fallback-profile-6e7fd527e.json`; the candidate code SHA was `e377bc2d47179f7a088d5035b0fb74938cf0a887548df97c864e8458c5656866`. No production application is authorized by this addendum.
