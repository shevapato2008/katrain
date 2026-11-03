# Independent scoped historical fallback review

**Verdict: APPROVED. No blocking findings in this delta.**

Reviewed code commit `6e7fd527ede926e894c81f40a6bb289ceee2826b` against its parent, and the matching performance addendum, including the subsequent documentation-only evidence commit `186339a6c5d55c722d9410dd490b64811cf009c2`. This is a fresh independent Astra max review of the measured fallback bottleneck, not a repetition of the earlier full feature review.

## Correctness and resource boundaries

At `katrain/web/kifu/historical_rank_repair.py:241`, a successful group returns its original decision list. The fallback catches the same `ValueError` class as before; a failing single target becomes `None` and is counted as `invalid_original_binding`. Failed larger groups are divided into ordered left/right halves. The existing 200-slot part bound also bounds recursion depth; output order and target/decision pairing are preserved.

Every attempt uses the same captured `pending_resource` at line 243. The recursive path neither creates a budget/cache nor resets consumed bytes. Body admission, exact original metadata/ownership checks, finite cohort limits, selected-evidence validation and subsequent local binding remain in their existing resolver paths.

Returned `resource_deferred` decisions are successful return values and are not subdivided. The combined-scalar-limit regression verifies that a valid subgroup stays deferred even when separate single-target calls could infer ranks. Consequently this optimization can conservatively reduce qualified scope compared with the former all-single-target fallback; the addendum states that explicitly. It does not manufacture a repaired result from a truncated cohort.

The downstream part construction, full beforeimages, snapshot/hash fields, first-apply fresh cohort/CAS verification, journal, replay and undo code are unchanged. The new public regression applies the remaining valid result through that existing CAS path. No native publication or collection code changes are included.

## Independent verification

On fixed code commit `6e7fd527ede926e894c81f40a6bb289ceee2826b`, ran the complete changed suite:

```text
tests/web_ui/test_kifu_historical_rank_repair.py
```

Result: **29 passed, 1 skipped in 9.98 seconds**. The skip requires an explicit disposable PostgreSQL opt-in DSN. The reviewer did not execute a PostgreSQL test or production query for this follow-up.

The passing cases include the 100-target/two-invalid-owner comparison of complete canonical decisions and refusal counts against the prior public single-target reference, a bounded cohort-call assertion, combined-resource deferral without single-target upgrade, shared body-budget checks, initial drift refusal, applied replay and guarded compensation.

Black at line length 120 passed for both changed Python files. The code and final documentation delta passed `git diff --check`. Commit `186339a6c` changes documentation only; no product code changed after the reviewer test run. The full 677-test feature suite was not repeated.

## Separately attributed real-data comparison

Read the controller/worker evidence at `output/kifu-rank-hourly-20261103/repair-fallback-profile-6e7fd527e.json`, SHA256 `6fd5a057166565062022a703ff728b46ba7262177fbd365473b34e305eabcb2e`. It records both calls against one REPEATABLE READ / READ ONLY snapshot for target IDs 4501–4600, with the same complete 176,949-album census.

The evidence reports equal census, refusals and all 23 complete frozen historical-prior decisions/hashes. Prepare calls fell from 201 to 29; cohort calls from 198 to 13. Target preparation fell from 9.800 to 6.015 seconds (1.63×); the complete scoped public call, including its full census, fell from 30.263 to 26.914 seconds (1.12×). These are supplied measurements inspected by the reviewer, not independently repeated production benchmarks, and they do not establish a whole-corpus ETA.

The repair source hash changes again with this code. Any future apply must use a newly prepared manifest bound to the final reviewed source; prior R050 exports remain audit evidence and must not be relabeled to bypass their code-hash CAS.

The reviewer changed only this review document, did not interrupt collection, perform live writes/restarts/provider calls, or read/list/traverse `data/kifu-album/`. Approval is for this scoped code change; it does not claim a completed full audit or live rank repair.
