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
