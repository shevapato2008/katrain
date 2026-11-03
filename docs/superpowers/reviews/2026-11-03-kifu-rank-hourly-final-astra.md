# Independent final code and data-integrity review

**Verdict: APPROVED.** No unresolved blocking findings remain for the reviewed candidate.

- Reviewer: fresh independent Astra max review requested by the user; no delegated review agents.
- Base: `bc248574d9b49ffecf641d08945938ca1c1e79aa` (`origin/develop`).
- Final candidate: `47711f9ec1def6130c2ad12cef77c1aab3941030`.
- The controller explicitly fixed this fully committed candidate before final verification. HEAD remained unchanged before and after the checks; this review document was the only untracked file.

## Scope and conclusion

Reviewed the shared historical rank policy, strict v3 snapshot schema/hash, original evidence and initial cohort checks, native freezing/publication/replay, historical repair CAS and compensation, finite hourly exact/semantic matching, dedup child journal/archive lifecycle, API snapshot authority and batched reads, ES pending/recovery, enabled collector preflight, and release configuration preservation.

The final implementation preserves raw SGF/ranks, original source ownership, old snapshot/receipt bytes and publication album IDs. Historical inference uses qualified original observations no later than the target; current profiles and inferred snapshots cannot become historical evidence. First application rechecks material qualification; applied replay validates frozen authority. The new retained/deferred outcome contract preserves an existing original owner's actual rank and requires TEST/PROD outcome agreement before receiver business writes.

Compensation validates parent/child and retained evidence dependencies before its first write. When deleting a newly inserted album requires releasing child journal foreign keys, the original complete journal, hashes and membership are archived transactionally before physical child rows are removed. Replay and ES scope retain archive authority, including deleted IDs. ES post-commit failures preserve the original pending operation for recovery.

## Findings resolved during this review

### R1 — Exact-SGF additional sources and retained rank authority

The initial native implementation rejected a valid second source whose SGF exactly matched an existing original album, because the incoming v3 source reference could not bind to the original owner's path. Independently reproduced with two distinct source items and a legacy first publication: the second publication raised `rank basis source SHA binding mismatch`.

`f2745f4ddaed7ddf023f3d93232f5e7332321734` and `2221199f0` close the complete path: applied/retained/deferred outcomes, immutable retained snapshot or explicit absence, original source/raw-body bindings, full receipt hash and API provenance verification, portable TEST/PROD outcome CAS, replay and undo. Multiple source items sharing an album retain complete source/language/card coverage.

Two follow-up integrity reproductions were also closed:

- An existing original-owner snapshot could be reused under a new publication key after its old journal afterimage was corrupted. `2221199f0` now applies the same old batch/journal/frozen-basis CAS to existing v3 rows in both original-owner and additional-source paths. Recreated local basis IDs are rejected rather than silently rebound.
- With two source links already present, standalone repair A could be undone after native B retained A's snapshot, leaving B applied but unreplayable. This was independently reproduced; incidental source-beforeimage checks did not protect it. `3572aa4a4c2ff77c046cbb898d8eedf51d0dbbd6` makes both historical and source-rank standalone undo consult the native receipt dependency guard before writing. Final regressions verify rejection without changes, successful B replay, then undo B followed by undo A.

### R2 — Original contradictions omitted from historical qualification

Independently reproduced: original 1960 `9p`, original 1967 root `8p` with embedded name rank `七段`, then a missing-rank 1968 target incorrectly inherited the older `9p`. The contradictory original had disappeared from the material cohort.

`f525f8054361bb2b6a40f29e8f72078eba762030` retains trusted root/name conflicts as negative material observations, including first-apply rechecks, and checks incoming originals as negative evidence without making them new positive basis. A further reproduction found that an incoming 1950 `9p` could be ignored against a database 1960 `7p` and missing 1968 target. `697631c5a65c1cf4c265ec83ba303ad474f6cb2f` now checks the professional maximum across every qualifying incoming original no later than the target, then performs the narrower nearest-observation checks. Frozen applied replay remains unchanged.

### Shared evidence budget

Initial full album reads in `_rank_local_owners`, `_coverage` and `_apply_decisions` bypassed the candidate-evidence budget. `a3bd8359c42a7dfd7e4a2f9356452893c6afa57c`, together with foundation/repair resource commits, removes those bypasses and shares one resource through rank, exact and semantic candidate phases. Cached bodies still require fresh metadata and exact-text equality checks; staged content is counted once. Final tests observe actual returned SQL body columns, not just counters, and cover unique-body reservations, same-length drift, combined ceilings and whole-cohort deferral.

## Independent final verification

Executed locally against `47711f9ec1def6130c2ad12cef77c1aab3941030` using the repository virtualenv, `CI=true`, and the worktree as `PYTHONPATH`. Both PostgreSQL opt-in environment variables were explicitly unset for these reviewer runs.

| Focused group | Result |
| --- | --- |
| Historical policy/repair/native, hourly consistency/retained ranks, rank outcome reports and cron preflight | **183 passed, 2 skipped** in 77.84 seconds |
| Existing source/native/catalog/API/ES/staging/CLI/cron compatibility | **494 passed, 2 skipped** in 67.88 seconds |
| Total | **677 passed, 4 skipped; no failures** |

The four skips are explicit disposable PostgreSQL opt-in tests. This reviewer did not run PostgreSQL checks; controller PostgreSQL evidence is separate and is not represented as independent reviewer execution.

The first group ran:

```text
tests/web_ui/test_kifu_historical_ranks.py
tests/web_ui/test_kifu_historical_rank_repair.py
tests/web_ui/test_kifu_historical_rank_native.py
tests/web_ui/test_kifu_hourly_catalog_consistency.py
tests/web_ui/test_kifu_hourly_retained_ranks.py
tests/test_kifu_rank_outcomes.py
tests/cron/test_kifu_ingest_preflight.py
```

The compatibility group ran:

```text
tests/web_ui/test_kifu_source_rank_normalization.py
tests/web_ui/test_kifu_source_rank_repair.py
tests/web_ui/test_kifu_incremental_catalog.py
tests/web_ui/test_kifu_catalog_standardization.py
tests/web_ui/test_kifu_rank_publication.py
tests/web_ui/test_kifu_rank_snapshots_api.py
tests/web_ui/test_kifu_search_publication.py
tests/test_kifu_rank_freeze.py
tests/test_kifu_incremental_decision_resume.py
tests/test_kifu_api_verification.py
tests/test_kifu_incremental_cli.py
tests/test_kifu_rank_correction_cli.py
tests/test_kifu_player_ranks.py
tests/cron/test_kifu_ingest.py
```

`git diff --check` passed for the complete base-to-candidate diff. Black with line length 120 accepted 24 of the 25 modified Python files. The sole difference is the pre-existing envelope literal near line 39 of `tests/test_kifu_incremental_cli.py`; the same formatting defect was verified directly in base `bc248574`. It is an inherited, nonblocking formatting issue, not a claim that the whole-file Black check passed.

## Material boundaries

- Retained v2 snapshots preserve their original local IDs and hash. If these differ across TEST/PROD, publication conservatively refuses; it does not re-sign old v2 bytes or claim v2 portability. New v3 portable snapshots and local binding checks remain separate.
- The shared 8 MiB operation ceiling covers this change's rank/exact/semantic candidate evidence, including supplied staged bodies. Existing immutable audit afterimages, specialized identity proofs and post-commit ES projection retain their established guards; they are not a claim that every SQL body read in the entire pipeline shares that counter. The plan and operations guide state this boundary.
- The controller reports a successful Compose configuration check with fake credentials and no container startup. The reviewer inspected the committed Compose, deployment-skill and operations changes. This review does not claim that deployment, historical live-data application, collector restoration or actual production timing has occurred.
- The reviewer made no live database writes, deployment/configuration changes or paid calls, and did not access, list or traverse the filesystem under `data/kifu-album/`. Product code, tests and the plan were not edited by this reviewer.
