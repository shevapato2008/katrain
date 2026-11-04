# Raw-event projection indexing — independent Astra final review

**Product verdict: APPROVED.** No blocking findings in `b5fd0828c539735b7ec216e63449e483533cc294` against base `a0d4e3cae`, under the approved projection-loop recovery plan.

The only product file changed is `katrain/web/kifu/search_projection.py`. Its per-batch index preserves input record order and repeated records, indexes direct and selected literals, avoids doubling a record whose two literals match, and keeps `None` distinct from the empty string. Both language maps and per-name eligibility use these candidates.

The existing identity mapper remains unchanged and receives each original proof row in its original order. Updating the result in that order preserves overwriting and dictionary insertion semantics; calling the mapper for empty buckets retains unscoped fallback entries. All scoped branches still execute the original qualification checks. Per-name eligibility retains both direct and selected name IDs. No global cache, scope truncation, proof/policy change or new source authority was introduced. Historical rank modules are unchanged.

Independent focused verification: **54 tests passed in 3.83s** across `test_kifu_projection_raw_event_index.py`, `test_kifu_search_documents.py` and `test_kifu_search_publication.py`. Coverage includes all mapper proof branches and row precedence, exact literal/duplicate handling, complete projection and classification equivalence, linear candidate visits, existing strict-name negatives and committed native publication recovery. Black for both changed Python files and the committed diff whitespace check passed.

The controller's bounded diagnostic reported 14,056 records, 42,813 raw-name rows, no duplicate records and 129,672 proof slots, confirming the planned cross-product trigger. Those live counts and the context duration are controller evidence; this reviewer did not repeat a live projection or claim a new production timing.

## Offline runtime builder

**Validation/copy logic: APPROVED** at `build-runtime.py` SHA256 `17493ff654d61c69b041ab7159f406d210fc7ca6713219c6b235ab1ec26ceacf`. Independently ran its **3 local selfchecks, all passed in 0.933s**.

The builder rejects a target whose UI inputs differ from its pinned reference, checks the frozen parent manifest and vendor revision, compares archived source-input bytes, and requires the complete two-tree static file set and byte hashes to match the frozen export. Static bytes are rechecked during copying. The image recipe deletes only the two old static directories before copying the verified runtime/export, preventing stale asset mixing. The existing helpers' complete HostConfig preservation retains the reviewed 8-GiB/12-GiB limits in the supplied fixture.

This is **not approval to reuse the old Raa assets after the newly reported foreign UI merge**. The current guard correctly rejects that mismatch. Before use with the final integrated release, `UI_RELEASE`, `UI_EXPORT` and `UI_MANIFEST_SHA` must be rebound to its fresh complete parent export and narrowly reverified. The selfcheck's old frozen static digest/file-count expectations must also match that actual export if changed. The validation/copy logic itself should remain unchanged.

No live recovery, Docker build/deployment, production database operation, provider call or source-data filesystem access was performed by this reviewer. The final publication/runtime pins and actual READY/API acceptance remain release evidence, separate from this code verdict.
