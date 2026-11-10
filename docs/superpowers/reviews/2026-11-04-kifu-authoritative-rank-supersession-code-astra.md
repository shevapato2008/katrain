# Authoritative Rank Supersession — Independent Code/Security Review

**Status: APPROVED — both reproduced findings are closed; no remaining blocking code/security finding.**

Final reviewed range: `21cf4175819296e23215d683acc457ecb30642e9..de9faeed5743fd25e3b8e940a28219095527a42a`, including the corrections below to initial implementation `07cba438c3fe2586ef3fff5df65d862fbbe6fb27`. The governing plan is `2026-11-04-kifu-authoritative-rank-supersession.md`, SHA256 `93885134248e660b141016fe88bbe3f994162c8cc766787441f059bec39bf6ee`, approved in plan review R2. Specification compliance was checked before code quality, authorization and resource boundaries. This approval does not approve a deployment or a later recovery/repair operation, and excludes the concurrent uncommitted canonical-owner/name-marker work.

The final planned five-suite run reports **262 passed, 1 skipped in 29.84s**. The skipped opt-in PostgreSQL node was separately executed against the final pinned catalog/test bytes: **1 passed in 1.98s**, return code 0, no remaining temporary schema. The reviewer inspected the complete five-suite output and byte-bound PostgreSQL evidence, and independently ran each newly added regression node.

## R1-1 — P1: the new loader blocks an existing valid mixed V1/V3 publication

`sync.verify_album_api` selects the compatibility loader when **any** requested snapshot is V1. `catalog.resolve_rank_publication_context` deliberately accepts only an original publication whose **every** requested slot is V1, and rejects native V3 outcomes. Existing `orchestration.prepare_staged_games` can combine immutable cached V1 game decisions with newly frozen V3 games; that supported combination is not an all-V1 compatibility request.

Independent reproduction used a disposable SQLite fixture and actual native publication, replay and API serializers. One original V1 game (`7p`, 2026-01-01) and one V3 game (`8p`, 2026-02-01) publish and replay successfully. Existing API verification returns `verified` with 10 language checks. Adding the local resolver callback now installed by Cron makes the same verification fail after one loader call with `rank publication context requires original legacy slots`, before current API checking. Thus a valid fresh mixed batch can stall at `test_published`, and an already published mixed batch can stall at PROD verification.

Minimum correction: enable this narrow compatibility loader only for its supported complete legacy-V1 original-publication request. Leave ordinary mixed and V3 requests on their existing verification/outcome path. Add one focused mixed-manifest regression proving no loader/RPC call and unchanged successful verification; there is no need to extend supersession to mixed publications.

**Closed by `8aa9a4e177775c3af8f3a7f7bdf5deea9aa47a44`:** the guard is now `all(V1)` and the real two-game regression preserves the complete ordinary report without calling the loader. The reviewer independently ran `test_current_rank_context_mixed_v1_v3_publication_keeps_original_no_rpc_verification`: **1 passed in 0.94s**.

## R1-2 — P2: external legacy-fact preflight omits a subsequently fetched unbounded scalar

`_RankPublicationProof.preflight_fact_source` measures only ID, selected owner/rank/date and SGF byte length. The deliberately retained `player_ranks.verify_rank_fact_for_player` then executes `select(KifuAlbum)` for that external source. This returns every column, including the unbounded `search_text` field, without charging that field to the shared scalar budget. A coherent repeatable snapshot protects equality between the reads but does not bound omitted columns.

Independent disposable-fixture reproduction kept the source body/fact/owner unchanged, set the external album's `search_text` to 1 MiB, and lowered `MAX_SCALAR_BYTES` to 64 KiB for the focused check. The resolver accepted an empty proven context and issued the old full-row SELECT, returning more scalar data than its configured operation ceiling. The same omitted-field issue applies to the normal 32 MiB ceiling.

Minimum correction: before the unchanged old guard, include all non-SGF columns that its full-row SELECT will return in the shared scalar preflight. Keep the SGF charged separately by the existing shared `EvidenceBudget` and retain the original verifier; no synthetic `source_games`, protected-module edit or additional inference is needed. One focused over-budget scalar case should reject before the old verifier is called.

**Closed by `de9faeed5743fd25e3b8e940a28219095527a42a`:** every non-SGF external album column is now measured by the existing shared scalar preflight before retrieval. The original guard remains intact. The reviewer independently ran the new `[scalar]` case: **1 passed in 0.47s**, proving refusal before the old full-row guard.

## Specification and safety checks

- The supported successor path proves the original native journal afterimage, exact single-hop repair beforeimage/afterimage, applied batch and canonical part/artifact hashes, unchanged repair code identity, DB identity, original source membership, full album/source image and freshly bound target/basis. It rechecks the current row and continues the original immutable fact verifier. Generic rank correction, multi-hop, missing journal, altered binding and stale/undone authority are refused.
- Native replay retains the existing publication/writer locks and original receipt. The context resolver establishes PostgreSQL `REPEATABLE READ` before `begin`, then `SET TRANSACTION READ ONLY` before its first proof query. It supplies `lock=False`, uses one connection/transaction and does not enter publishing, providers, search writes or initial rank reselection.
- The fixed read wire operation permits only operation/M/receipt SHA, rejects its schema before opening the engine, uses the existing forced SSH receiver, bounds response bytes and timeout, and returns a fixed safe error. It cannot supply arbitrary rank, path, SQL, batch selection or a publication request.
- Current expectations come from the trusted local/fixed-SSH loader, retain full display/origin/provenance checks and bind the current supplement/checkpoint to exact context, M, receipt, source mapping, DB and API target. Original TEST authorization remains a distinct validator; its receipt hash is checked before the durable `test_verified` transition. Existing seven-day/tail admission is unchanged.
- Receipt membership bounds target owners to at most 200. The short canonical ID/name namespace scan preserves the existing NFKC/casefold collision guard under a 50,000-row and shared 32 MiB authority/scalar ceiling; it is not rank/cohort discovery. Source/basis bodies share one `EvidenceBudget`. External legacy-fact source preflight retains the original verifier, including its permitted second fetch of an already bounded exact body in the same repeatable snapshot; content is counted once. The implementation does not fabricate `source_games` or claim zero duplicate reads.
- The changed product scope is the four planned files. Both protected repair modules are unchanged; independently recomputed `_code_sha256()` is `b009f59cb7160689a2ee48ebc1ac328ebbffe3fdb1ccb0217b42183e977d7300`. Final `git diff --check 21cf41758..de9faeed5` passes.

## Verification and initial evidence disposition

Final planned command, run by the controller from the named worktree:

```sh
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_rank_native.py tests/web_ui/test_kifu_rank_publication.py tests/test_kifu_api_verification.py tests/test_kifu_incremental_cli.py tests/cron/test_kifu_hourly_orchestration.py
```

Full log: `/tmp/kifu-supersession-integrated-five-suites-final.log` — **262 passed, 1 skipped in 29.84s**. Separate exact PostgreSQL node: `tests/web_ui/test_kifu_historical_rank_native.py::test_publication_context_disposable_postgresql_repeatable_read_only_snapshot`. Evidence: `output/kifu-rank-hourly-20261103/pg-supersession-authority-exact-node-v2.json` — **1 passed in 1.98s**, return code 0, UUID schema counts 0 before/after. Its before/after SHA256 values exactly match the final reviewed files:

- `catalog.py`: `10840d3a80a53a84962188d4dfed3e46e1ceaaa83873ce4ce11964da874cea56`.
- `test_kifu_historical_rank_native.py`: `674304a5fc850b62fdbf70b7eac65ff6129666b41b027b7346a74f0e274dc440`.

The PostgreSQL node asserts actual `repeatable read`/`on` settings during the proof, preserves the transaction's view across a concurrent snapshot-row mutation, refuses the changed state on a subsequent resolver call and restores the connection's normal isolation/read-only settings. This review read the evidence; it did not itself connect to that database.

The initial combined five-suite log reports **259 passed, 1 skipped, 1 failed**. The failure is the new natural first-PROD fixture: its TEST-only synthetic approved professional identity capture is absent from the independent PROD fixture, so the unchanged strict fact verifier correctly refuses first publication. This test setup defect is corrected by `8abf939bf25ad4e98df5a36a76cb000d1c0fb4c4` and `17ff4b9c6c71ecbb3f9ceb94f9a06d2a9fbf0cae`: independently seed the same approved identity capture in the PROD fixture before ordinary first native publication. The professional-to-unspecified assertions and unchanged strict fact verifier remain. The reviewer inspected both test-only corrections.

The older PostgreSQL evidence reported one pass in 2.05 seconds against earlier catalog bytes. It is retained as history and is superseded for this approval by the exact-byte V2 record above. No full PostgreSQL suite or broader operational audit was required.

Review used only local disposable SQLite fixtures and source/evidence inspection: no production/service operation, live database access, source-library filesystem traversal, real SGF disclosure, product edit, commit or deployment. The separate canonical-owner correction and later concretely reviewed recovery/five-album repair remain outside this code diff.
