# Numadate Canonical Correction Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan after controller approval. Steps use checkbox (`- [ ]`) syntax. This task writes the plan only. The controller owns independent Astra max plan review, at most two rounds, and a fresh Astra final review; do not start implementation, production writes, or additional reviewers from this planning task.

**Goal:** Restore publication of the original frozen `0ef` package by correcting the one PROD player5364 canonical typo, its five current display names, and exactly two dependent current source-rank snapshots without changing the original package or historical evidence.

**Architecture:** Add one person-specific, independently reviewed correction operator using existing native writer locks, evidence revisions, and before/after journals. A single transaction formally renames the existing player, preserves spelling aliases, writes new truthful name revisions, and replaces exactly two current `source/basis0` V3 snapshots with results recomputed by the unchanged b009 resolver. Old snapshots and receipts remain as historical evidence; a bounded verifier proves the new correction authority from the old applied repairs through the exact owner transition to the current rows.

**Tech Stack:** Existing Python, SQLAlchemy/PostgreSQL, native name batches/journals, unchanged historical-rank V3 policy/resolver, pytest, existing fixed SSH/deployment/recovery tooling. No schema migration, stable UUID, fuzzy identity lookup, generic identity-recovery framework, journal-chain search, or new service.

---

## Chunk 1: Fixed evidence, ownership, and contracts

### Evidence and scope

Worktree: `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kifu-rank-hourly-20261103`. Run commands here and preserve other agents' edits.

The original package is `19x19-batch-0ef14d803cd49221b37f4648`, 19 games /38 V3 slots, with zero name decisions. HOME native1438 has already applied it and its saved TEST report is verified. Source92045923 /white freezes owner `沼馆沙辉哉`, `origin=source`, `basis=[]`, raw `七段`. PROD resolves this name through alias58 to player5364, whose canonical is `沼官沙辉哉`; the strict `_owner` assertion correctly refuses that mismatch. Freeze the actual complete M/key, HOME receipt/report digests, and durable queue phase before live work; do not invent missing digests in this plan.

Existing finite evidence, containing no SGF bodies:

- `output/kifu-rank-hourly-20261103/hourly-natural-220332/92045923-finite-dependencies.json` and `.md`.
- `output/kifu-rank-hourly-20261103/hourly-natural-220332/92045923-manifest-and-small-proofs.json`.
- `output/kifu-rank-hourly-20261103/hourly-natural-220332/92045923-indexed-preimages-and-native-binding-registry.json`.
- `output/kifu-rank-hourly-20261103/hourly-natural-220332/92045923-exact-preimages-and-native-authority.md`.

The exact PROD scope is:

| Item | Current evidence / allowed result |
| --- | --- |
| Player | Existing5364, `沼官沙辉哉` → `沼馆沙辉哉`; same ID, created_at and authoritative_pages. No new player. |
| Alias | Existing58, `沼馆沙辉哉` →5364 remains exact; create the old canonical spelling alias only after collision/absence checks. |
| Album124026 /black | 19x19 source41442702, 2014-03-06, raw name `沼官沙辉哉`, raw `二段`; snapshot186520, applied repair2189, SHA `2882abee9e7224cb7b023c59b3905d3a54ee01d7f50d7468476302b248982c64`. |
| Album178495 /white | 19x19 source91342440, 2026-10-15, raw name `沼馆沙辉哉`, raw `七段`; snapshot233062, applied repair2518, SHA `3b1128f935c5c5aba4411c1f4abb8430f5aabdbe6bf285865e118b6c8cf86939`. |
| Both current snapshots | V3/source, basis0, old portable owner `沼官沙辉哉`, target.player_id5364, rank_fact_id null. Replace current rows through the new audited operator, preserving row IDs and all original source/raw/numeric evidence. |
| Names | Exactly player5364's five current name rows; append five evidence revisions and journal each name's complete before/after image. Keep old evidence rows. |
| Rank facts | PROD5364 currently0. Do not create/rewrite facts during this correction; the original0ef publication subsequently creates its own frozen observations through existing code. |

Decisive predecessor checks are complete: both full repair `part.change.snapshot_before` values are JSON null, and both original repair journals' `before_image` values are JSON null (journal811430 /857999). These are repairs that created their current V3 rows, not repairs replacing native V1/V2 snapshots.

There **is** an older source publication for91342440: native876, format `kifu-incremental-manifest-v1`, key `19x19-event-recovery-870a06d9f6b3f234b354a5f4`, M `0f64c2b366a0d9ba59b452d4aac4148dc5609d19c57c6befa1deacde06459e67`, original receipt SHA `674c34b37294cca5929bdf8ba6aaa528c3214c50ad630712ddc999ba5def5f0f`. Its rank_bindings field is absent and its original snapshot journal count for this album is zero. The small-field query additionally observed absent rank payload on the first logical game; do not treat that as proof of every game's fields. Source41442702 has no native source record in the complete applied V1/V2 exact-source query within the existing native binding registry385. Fresh apply preflight must reconfirm the registry, format, receipt and snapshot-membership facts, and select the exact91342440 target game to freeze its actual original rank-field presence/absence. If a native rank snapshot/fact or another predecessor appears, refuse this operator and report the new dependency; do not add replay compatibility opportunistically.

The official primary source already examined is `https://www.nihonkiin.or.jp/player/htm/ki000430.html`: `沼舘沙輝哉`, `NUMADATE, Sakiya`, professional2010, seven dan2021. Its spelling supports correcting 官. Official name similarity alone and the existing alias alone do not authorize a person merge. The data review must bind this public person to the exact existing5364 row using the two frozen source contexts, their existing same-row links, the raw correct spelling already present in91342440, and actual corroborating identity evidence. Record any uncertainty; no broader identity claim is authorized.

Explicit exclusions: HOME1016, HOME11140, raw-value review_metadata,143 unlinked raw-name slots, other aliases/players, source/album/FK/raw/SGF changes, event repairs, global historical repair, and a new ingestion key. Do not read/list/traverse the filesystem `data/kifu-album` directory. Runtime original bodies come only from the exact two database albums; never print SGFs, DSNs, credentials or full private artifacts.

### Protected code and parallel ownership

These two files are immutable for this work:

- `katrain/web/kifu/historical_ranks.py`, file SHA `b719462b4fcbc939b44745c0c54085e530b33e29a9887c8745546a7eb91395c8`.
- `katrain/web/kifu/historical_rank_repair.py`, file SHA `8e0c985594446d9cc4bd9b6a05568f584a0f484dc7fecac5bfd55e62a362b2a2`.
- `historical_rank_repair._code_sha256()` must remain `b009f59cb7160689a2ee48ebc1ac328ebbffe3fdb1ccb0217b42183e977d7300`, preserving all approved HOME211207 /PROD227846 corpus parts. Do not relax `_validate_part`, change policy/version, modify `_owner`/`_bind_target`, use an ordinary historical part to replace V3, or alter `_replaceable`.

The authoritative-rank-supersession `catalog.py` change is now committed as `07cba438c3fe2586ef3fff5df65d862fbbe6fb27`. Implement the new correction module, name marker, API reader/authority hook and their focused tests independently first, then add the small correction-authority hook sequentially on that stable result. Do not edit the other agent's native supersession resolver or expand it to V3→V3/name-change chains.

| File | Responsibility |
| --- | --- |
| Create `katrain/web/kifu/numadate_canonical_correction.py` | Fixed scope, prepare/apply/verify contracts, name correction context, complete old/new authority proof. All special-case identity knowledge stays here; this version provides no undo. |
| Create `scripts/correct_kifu_numadate.py` | Thin strict CLI for prepare/verify/apply; production PostgreSQL database identity and pinned digest checks; safe summaries and original search-operation recovery reference. No undo or arbitrary IDs/SQL/path target options. |
| Modify `katrain/web/kifu/name_batch.py` | Recognize one finite generated-player correction marker, reuse normal evidence/name revision writing, and reject generic undo of the correction parent/child before any reverse business write, including emergency/partial paths. No general rename/undo framework. |
| Modify `katrain/web/kifu/player_ranks.py` | Only when this new authority format is present, invoke the bounded trusted DB verifier once per correction batch and attach an internal verified flag to exact current rows. Ordinary pages remain unchanged. |
| Modify `katrain/web/api/v1/endpoints/kifu.py` | Accept the new authority only with that internal verified flag plus every existing exact row/source/owner/raw check. No old-owner compatibility branch. |
| Modify `katrain/kifu_ingest/catalog.py`, sequentially after the committed supersession change | Add the new verifier as one explicit authority option in retained-rank validation; leave owner/fact checks and original replay rules intact. |
| Create `tests/web_ui/test_kifu_numadate_canonical_correction.py` | Meaningful synthetic end-to-end correction, refusal, rollback and original replay tests. Extend existing native/API tests only where their fixtures save duplication. |

### Operator contract

Use format `kifu-numadate-canonical-correction-v1` and key `canonical-correction:<planSHA>`. The format is not `kifu-historical-rank-repair-v1`; its two current-row replacements have their own explicit authority. Reuse the existing tables, image/record helpers, source/body budgets and unchanged resolver functions. The one parent-plus-child business transaction must run inside `name_batch._locked_write(engine, search_operation=("name_apply", {"bundle_sha256": child_bundle_sha}))`, using the already frozen standard child bundle SHA. Historical-rank table locks alone do not supply this search protocol. No new table or generic framework.

The frozen private plan must include an allowlisted schema with:

```text
format, operator_code_sha256, protected_rank_code_sha256, database_identity
fixed_person = {official_profile: ki000430, player_id: 5364}
owner_before, owner_after; existing alias58 complete image; old-alias intended create
identity_review = actual independent producer/reviewer + captured source evidence
targets[exactly2] = {
  album/source complete scalar images and source body SHA, source link images,
  old snapshot complete row, old repair batch/part/journal pins,
  old repair snapshot_before = null, old original private binding,
  expected new V3 snapshot, numeric/source-preservation assertions
}
old five name/evidence images + exact old first-pass creation proof pins
new signed five-name bundle/research, bounded source captures and review identity
native876 original M/key/receipt/source/absence-of-rank assertions
snapshot/fact/FK/name reference sets and all approved mutation counts
matched_at, identity_transition_sha256, independent final approval, content_sha256
```

Avoid a hash cycle: `identity_transition_sha256` hashes only the fixed identity/source/old-name preimage transition section, excluding candidates and final approval. New name markers reference this transition hash; the final independent review signs the complete plan including candidates and expected snapshot bytes. A digest alone is not approval or local DB authority. Define `operator_code_sha256` over the reviewed file bytes for the new correction module/CLI plus its modified name_batch, player_ranks, API and catalog hooks, in a fixed path order; compare with the running files at prepare/apply, never an echoed caller value. Protected b009 remains its separate unchanged two-file pin.

Preparation is PostgreSQL REPEATABLE READ, READ ONLY from its first query. It only reads the fixed row sets and the exact predecessor artifacts; use count/UTF-8-size guards before JSON/body fetch. Each old repair part retains its existing4MiB cap; total authority JSON≤12MiB, source SGFs≤256KiB each and≤512KiB total, selected name/evidence/source-capture material≤512KiB, SQL≤5s and a finite operation deadline. Do not select whole native/name artifacts when indexed selected fields/journals are sufficient; exact old repair parts may be loaded to recompute their approved hashes, never unrelated SGF bodies.

Prepare the two new candidates without mutating PROD. Starting from the already validated source/basis0 old decisions, change only `player_ref` to the new canonical, `matched_at` to the reviewed freeze time, and their self-hashes. Run unchanged `validate_rank_decision` and freeze the exact bytes for review. All other portable fields, including raw names, raw ranks, dates, source refs, values, systems, display, qualification and basis, must remain equal. This is a reviewed candidate, not authority to bypass fresh source computation.

The actual apply gate is stronger:

```python
operation_ref = {"bundle_sha256": child_bundle_sha}  # frozen before opening writer
with name_batch._locked_write(engine, search_operation=("name_apply", operation_ref)) as conn:
    assert protected_rank_code_sha256() == APPROVED_B009
    verify_old_repairs_and_names_against_live_beforeimages(conn, plan)
    assert_no_unreviewed_dependencies_or_native_rank_predecessors(conn, plan)
    rename_same_player_once_and_preserve_aliases(conn, plan)  # permanent intended mutation
    targets = exact_two_live_targets(conn)
    fresh = historical_ranks.prepare_rank_decisions(
        conn, targets, matched_at=plan["matched_at"], resource=resource
    )["decisions"]
    assert fresh == [target["expected_snapshot"] for target in plan["targets"]]
    historical_ranks.verify_initial_rank_decisions(conn, targets, fresh, resource=resource)
    bindings = [historical_ranks.bind_rank_decision(conn, t, s, resource=resource)
                for t, s in zip(targets, fresh)]
    # Exact snapshot CAS + new parent/standard child evidence/name journals here.
    # Validate the complete postimage and reciprocal parent/child binding.
    # _locked_write owns real commit, ES projection/refresh and session-lock release.
# Report complete only after this context exits with search ready.
```

No temporary PROD rename/revert, production write-based preparation, refreeze of0ef, copied snapshot accepted without resolver equality, or native replay used to discover a different expected result. Ordinary transaction rollback on an apply failure is required and does not authorize another mutation attempt with changed evidence.

### Name qualification and journaling

Use ordinary conventional evidence with actual official Japanese `source_checks` for JP `沼舘沙輝哉`. The official Japanese page does not prove published CN/TW/EN/KO names. For these four cells, append newly reviewed generated-first-pass revisions whose source_input binds the corrected canonical owner image. Proposed displays are CN `沼馆沙辉哉`, TW `沼館沙輝哉`, EN `Sakiya Numadate`, KO `누마다테 사키야`; the actual text producer/reviewer must approve them, and any changed proposal requires a new frozen review. Do not claim sourced reading/published usage or hide a conflicting actual source.

Existing `catalog_chinese_default`/verified-Japanese orthographic profiles prohibit replacing these existing approved/evidence-backed targets, and current first_pass_correction is raw-owner-specific. Do not weaken those profiles. Add one `numadate-canonical-first-pass-correction-v1` marker for exactly player5364's four generated cells, requiring exact old name/evidence/candidate/revision/batch proofs, the reviewed identity transition and new owner source hash. It must reject other players/languages/raw owners and calls outside this correction operator.

Use an operation-local trusted context passed through existing `prior_proofs` to `_check_name_preimages` and `_apply_candidate`; bind it to this connection and independently prevalidated plan. A serialized marker/self-hash alone cannot create that context. Do not add global mutable approval state, a public bypass flag, or a standalone marker acceptance path through generic name apply.

Reuse `_candidate_evidence`, `_apply_candidate` and `_record_change`: new evidence rows, incremented revisions and exact name before/after images. A parent correction batch holds player/alias/two-snapshot journals; a standard child name batch holds the five name updates/five evidence creations, with ordinary bundle/research hashes. Both are created/applied in the same transaction and the parent receipt pins the child ID/bundle SHA. The child's reviewed_artifact additionally has an allowlisted `canonical_correction_parent` field containing the binding version, exact parent ID/plan SHA, transition SHA, owner5364 and affected_album_ids124026/178495. Verify it reciprocally against the parent and reviewed plan; IDs are filled in the one transaction, outside the already hashed standard child bundle, avoiding hash cycles. Do not put a custom `receipt` in the child artifact: it remains a normal bundle/research/journal artifact that existing search readers understand. This preserves existing name-ledger membership rules without adding player/alias rows to a standard name batch.

Validate old first-pass evidence against the frozen **owner_before** image and its real original creation journals; do not rewrite old research or pretend its generated spelling was correct. New current names bind owner_after and pass existing native qualification readers, so `identity.py` needs no compatibility change. Leave authoritative_pages unchanged; the new official capture lives in evidence, and an unrelated biography-page sync is outside scope.

### Independent authority verifier

Implement one read-only verifier used by CLI verify, the retained-rank hook and the API reader. It must independently prove:

1. Correct fixed DB/person/scope, actual independent identity/text review and approved protected/operator code pins. Recompute the frozen plan content; do not accept a caller-supplied verified flag or a self-consistent hash as authority.
2. Each old applied repair's real batch bundle SHA, complete `_artifact(part)`, unchanged b009 `_validate_part`, database identity and unique selected change/journal. Old part.snapshot_before and old journal.before_image are null; old journal.after_image equals the correction's complete snapshot beforeimage and selected old part result. Before the rename, prepare/apply must also fresh-bind each old snapshot with b009 and compare the old private binding. No arbitrary predecessor chain.
3. The exact owner-before → owner-after change is journaled on the same5364 row, changing only canonical_name; original alias58 is unchanged, the old-spelling alias has exact approved ownership, and collision checks pass. Source albums/links/FKs/raws/body SHAs remain exact.
4. Correction batch is applied, has the reviewed format/key/plan digest and unique exact current snapshot afterimages. The new snapshots validate under b009, preserve every source/numeric field and have correct current canonical owner. Fresh `bind_rank_decision(lock=False)` equals the new stored private basis_bindings. Both remain source/basis0 and fact-null. Old/new target bindings must match in every local ID/source field, differing only in their snapshot SHA and enclosing content hash. After the permanent rename, do not call the old decision's strict live binder with an invented old owner: prove its historical owner through the exact player before/after journal, its applied old repair/old binding, unchanged original source, and the freshly verified new binding. The basis0 restriction is what makes this complete without an old-owner exception.
5. Name child bundle/research/journals and reciprocal `canonical_correction_parent` binding qualify truthfully; old evidence/receipts remain intact. The original native876 receipt remains byte-for-byte and is not represented as a former rank snapshot authority.

Verification opens RR READ ONLY in the standalone CLI; when called inside existing API/native transactions it performs only bounded SELECTs with `lock=False` and compares the exact supplied/current rows before returning. Never call a writer/prepare/repair on a read path. Deduplicate this correction proof once per batch per request. The API's new branch requires an internal DB-verifier result bound to row ID/SHA and batch SHA, plus every existing journal/source/raw/date/current-owner check; ordinary/native/historical repair branches remain unchanged. Corrupt/missing/ambiguous/undone correction proof yields refusal/fallback, never alias-based acceptance.

Old repair receipts remain historical applied evidence with an explicitly audited successor. Re-running an old repair's **current-afterimage** assertion after this correction is expected to refuse because that row has been superseded; do not change its protected replay/code-hash behavior or call it a failure to preserve its original receipt.

### Undo boundary: explicitly unsupported in this correction version

Do not implement a dedicated undo API/CLI in this task. Keep full before/after evidence for a future concrete, separately approved rollback plan; that future work must handle parent/child atomically, later dependencies and the search protocol. This task supplies no force rollback, standalone child reversal or compensation of original native876.

Add a narrow guard at the common `name_batch.undo_batch` entry, after reading the batch and **before the first reverse business write, status change or v4/per-row/partial-undo branch**. Reject this parent format and any child carrying this binding or the four-cell correction marker. A valid child must have the reciprocally verifiable parent binding; missing/corrupt binding must fail closed rather than fall through to ordinary undo. The guard applies even when `emergency_invalidate_search=True`, to every status/partial path, and cannot be bypassed by an option or connection-local apply context. Direct generic parent and child undo therefore refuse both before and after0ef creates new slot/fact dependencies. Ordinary unrelated name undo remains unchanged. No new general undo framework or `name_undo` operation for this operator is required.

The pre-apply exact two-slot/zero-fact census is an admission condition, not a permanent read-authority restriction. After legitimate0ef publication adds a third5364 slot/fact, the correction verifier and both corrected old overlays must still succeed; rollback remains unavailable. Transaction rollback on an uncommitted apply failure remains mandatory and is unrelated to this unsupported post-commit undo.

### Existing search commit and recovery protocol

Use only the existing `name_apply` operation keyed by the frozen child bundle SHA around the complete parent/child business transaction. Preserve `_locked_write` session advisory locks, search pending gate, business table locks, real PostgreSQL commit, projection, refresh/ready, then lock release. Do not pass the new parent format to `catalog_publish`, call `finish_sync` early, open a second business transaction for the child, or bypass enabled search sync. The parent and child applied journals must both become durable in the same commit.

The standard child's artifact, owner5364, explicit affected_album_ids and ten name/evidence journal rows must feed existing `search_sync._batch_scope`/`_expand_scope`. Assert the derived scope includes player5364, albums124026/178495, old/new canonical/display spelling terms and the normal raw-derived owner/term expansion. Do not replace this with a hard-coded two-album projection that omits normal derived scope, and do not change business identity links for any143 unlinked slots. Reuse the current projection/classification logic; no new search format or recovery journal is needed.

A known pre-commit failure rolls back the entire correction and lets the existing wrapper cancel its search gate. An uncertain COMMIT or post-commit ES/projection/refresh failure must preserve/report `SearchIndexPending` with operation_type=`name_apply`, operation_ref=`{"bundle_sha256": child_bundle_sha}` and the original plan pin. Do not describe this as rolled back, issue a new bundle/parent, re-run new mutations, or report completion before the gate is ready. Recover with existing `search_sync.recover_pending(engine)` using the original operation reference and durable child bundle/journals; its `name_apply` outcome resolves whether the original business commit happened. After recovery, the ordinary idempotent apply/verify path may return only the same parent/child IDs, revisions and correction receipt, with no repeated business writes. Unknown authority remains pending/refused for operator attention.

## Chunk 2: Implementation and focused verification

### Task 1: Exact correction core and truthful new names

**Files:** new `numadate_canonical_correction.py`, new thin CLI, `name_batch.py`, new focused test file. Do not touch `catalog.py` yet.

- [ ] Add a meaningful synthetic fixture with one same-ID owner typo, old alias, both raw spellings, two real b009 source/basis0 repair-created snapshots (before null), five real first-pass names and a V1 source receipt without rank payload. Keep IDs/scope shaped like the actual case without copying production SGF content.
- [ ] Write RED tests for readonly prepare, candidate field restrictions, formal rename + two resolver-confirmed row replacements + five new name revisions, unchanged old evidence/receipts, and exact frozen0ef-style first publication/replay producing a usable new fact under the corrected canonical.
- [ ] Run `uv run pytest tests/web_ui/test_kifu_numadate_canonical_correction.py -q`; confirm failure is the missing correction behavior, not fixture setup.
- [ ] Implement fixed schemas, reviewed transition/marker, prepare/apply/verify and reciprocal parent/child binding with native helpers. Put the complete business transaction inside `_locked_write(search_operation=("name_apply", {"bundle_sha256": child_bundle_sha}))`. Add no undo command/API. The production CLI accepts only the configured PROD PostgreSQL identity; no arbitrary player/source target or testing bypass option. Synthetic in-process tests may exercise transaction helpers on SQLite; use the existing disposable PostgreSQL setup or focused review to verify real RR READ ONLY preparation and production session/table lock ordering, not a new concurrency framework.
- [ ] Add focused negative tests for wrong DB/person/alias/collision, incomplete source identity review, old repair or name journal drift, native rank predecessor, non-source/basis-nonempty target, source/raw/FK/SHA drift, numeric/category changes, missing old alias, forged/out-of-operator marker, and a name failure rolling back the entire correction. Parameterize related integrity cases; do not create a new fuzz/audit framework.
- [ ] Verify complete preflight/CAS; repeat apply returns only its original correction receipt after revalidating its actual current authority, while changed/undone state refuses. Call generic `name_batch.undo_batch(parent_id)` and `undo_batch(child_id)` normally and with `emergency_invalidate_search=True`, before and after the0ef-style publication/fact; all must refuse with business rows, journals and batch statuses unchanged. A stripped/corrupt child binding must not bypass the correction-marker guard. Preserve ordinary unrelated name undo tests.
- [ ] Reuse `tests/web_ui/test_kifu_search_publication.py`'s existing ES failure/recovery fixture for one focused correction case: assert the standard child-derived scope includes player5364, both old albums, old/new spelling terms and normal derived scope; inject failure **after the real business commit**. Capture the pending name_apply operation, original parent/child IDs, revisions, journals and receipt; clear the ES failure, run `search_sync.recover_pending(engine)`, then verify unchanged business evidence and ready search documents/classification for both corrected albums. Idempotent reentry must not perform a second business mutation. Preserve the existing lost-COMMIT-acknowledgement/session-lock tests for the reused wrapper.
- [ ] Re-run the focused file and existing name/search regression slice: `uv run pytest tests/web_ui/test_kifu_numadate_canonical_correction.py tests/web_ui/test_kifu_name_first_pass.py tests/web_ui/test_kifu_name_batch.py tests/web_ui/test_kifu_search_publication.py -q`. Expected: PASS with the existing strict raw-correction, qualification, undo and search recovery cases preserved.
- [ ] Commit only this task's exact files after inspecting the diff; preserve other agents' working-tree edits.

### Task 2: Trusted API authority and sequential native integration

**Files:** `player_ranks.py`, API endpoint, existing API/native focused tests; `catalog.py` only after the controller confirms ownership handoff.

- [ ] Write RED API tests: both corrected current overlays render their new exact V3 SHA/source/numeric data; forged format/hash alone, altered predecessor/owner/current journal or an undone correction cannot authorize an overlay. Ordinary native/historical overlays remain unchanged.
- [ ] Add the page reader's bounded per-correction-batch verifier call and the API branch requiring its internal row-bound proof. No new HTTP route, caller proof, old-owner exception or source filesystem access.
- [ ] On the stable `07cba438c3` supersession result, inspect its final diff, add only the explicit new correction-authority call in retained-rank validation, and preserve all existing owner/fact/source/native-supersession gates.
- [ ] Write/run a native integration test in which the old V1/no-rank receipt replays unchanged through the retained old alias and the new0ef-style V3 source publication passes the original strict owner/fact path. Confirm real b009 validation/binding is used and no old native rank receipt is synthesized. After that legitimate new slot/fact, assert the correction verifier and both old album overlays still succeed while direct parent/child undo continues to refuse.
- [ ] Run `uv run pytest tests/web_ui/test_kifu_numadate_canonical_correction.py tests/web_ui/test_kifu_historical_rank_native.py tests/web_ui/test_kifu_historical_rank_repair.py tests/web_ui/test_kifu_rank_snapshots_api.py tests/test_kifu_rank_freeze.py tests/test_kifu_player_ranks.py -q`. Expected: PASS, including the new rendering case in the correction fixture and all strict native/historical cases. Repeat only when a new change/failure warrants it.
- [ ] Check protected files with `git diff --exit-code -- katrain/web/kifu/historical_ranks.py katrain/web/kifu/historical_rank_repair.py` and compare the two file hashes and `_code_sha256()` with the pins above. Verify an existing b009 approved-part validation still accepts its original bytes. No new protected hash/version is allowed.
- [ ] Commit only this task's exact files. Request the controller's fresh Astra final review; no production write is authorized by passing unit tests alone.

### Task 3: Concrete reviewed production correction and original package recovery

**Files:** private bounded evidence/plan/receipt/report artifacts only, plus a concise applied record when authorized. No additional product feature.

- [ ] With plan/final reviews approved and the existing deployment workflow coordinated by the controller, freshly capture PROD5364's exact sets, original0ef M/key/HOME receipt/report/queue phase, native876 original receipt and absent rank membership, both old repair parts/journals, five old names/evidence, aliases/collisions and DB/code identity. Reuse the finite indexed predicates; do not retry timed-out broad JSON scans or traverse source files.
- [ ] Prepare the readonly correction candidate and obtain actual independent identity/text reviews of its frozen complete content. JP has true official source checks; the other four displays retain their honest generated status. Present the exact mutation counts and plan SHA for final production authorization through the controller.
- [ ] Apply that exact approved digest once inside the specified `name_apply(child_bundle_sha)` wrapper. Pre-commit drift/refusal rolls back everything. If commit outcome is unknown or ES remains pending after a committed correction, retain the original operation reference and parent/child journals, report pending and use existing recovery before proceeding; do not claim rollback or repeat the business mutation. Do not re-freeze0ef, select another player, skip the slot, change key/M or silently issue new expected snapshots.
- [ ] Verify independently in RR READ ONLY: one same player rename; existing alias58 preserved and old alias correct; exactly two current snapshot replacements with b009 resolver/binding proof; five new name/evidence revisions; old rank/source/name journals/receipts intact; no facts created yet; source/SGF/raw/FK/event data unchanged; protected b009 pins unchanged. Retain the new exact correction receipt and old→new proof.
- [ ] Require the original name_apply operation's search gate to be ready, with the child-derived projection scope including5364/both target albums and normal raw-derived scope. Verify actual search documents/classification and representative PROD API pages for both old albums in all five languages, including exact new rank provenance/SHA and corrected CN/TW/JP displays, using existing verification machinery rather than a new report system.
- [ ] Replay original native876 through the existing authorized recovery interface and prove the exact original receipt returns with no business writes. Preserve its original M/key and source ownership.
- [ ] Recover the already-frozen0ef package at its actual durable phase using the existing queue path and existing HOME TEST report. Confirm original HOME1438 receipt/report stay byte-for-byte, PROD publishes19games/38slots under original M/key, the92045923 white slot binds same5364 under the corrected canonical, and its original frozen fact validates/rebuilds normally. Complete the existing actual API/search verification and durable terminal state; do not use a new ingestion key or fresh import.
- [ ] Report published/deployed code versions, correction plan/batch/name-child/receipt pins, original search operation reference and ready state, original0ef M/key/native receipts, actual terminal state and API verification. State that this correction version supports no undo; any future rollback needs a separate concrete approval and must account for new0ef dependencies. No unrelated143-slot cleanup or HOME person merge.

## Handoff

### Implementation clarifications within the approved identity correction

- The unchanged b009 validator requires `qualification.player_ref` to equal the top-level `player_ref`. The identity-only correction therefore updates those two references together, plus `matched_at` and the self-hash. Every other qualification field, numeric value, system, date, source field and basis remains exact. A failing test demonstrated this constraint; actual apply still requires byte-for-byte equality with the unchanged resolver's recomputed result.
- Read verification retains the full protected `bind_rank_decision(lock=False)` call. Its existing bounded-query helper uses `SHOW`, savepoints, transaction-local timeout configuration and savepoint release; these read-only transaction controls are allowed. The boundary prohibits business DML/DDL and row/advisory writer locks, rather than replacing the protected binder with a partial implementation to satisfy a literal SELECT-only description. PostgreSQL read-only behavior and timeout restoration remain verification requirements.
- The running operator-file hash remains a strict preparation/application admission gate, including idempotent apply. For an already-applied read, its original operator hash is historical execution evidence bound by the approved plan and applied parent; it is not compared with subsequently edited API/catalog files. Read verification still requires the current protected b009 pin and the complete versioned database proof. This avoids invalidating the corrected records after an unrelated application release without granting new write authority.
- Actual HOME batch1438 and its durable stage independently confirm the complete publication key above, including `-batch-`. The earlier shortened spelling was a planning transcription error, not another package; the strict input contract accepts the original complete key and rejects that shortened value. No manifest, key, receipt or stage is rewritten to accommodate the operator.

This plan's delivery does not authorize implementation, live correction, replay or deployment by its author. The controller first sends this exact document and the finite predecessor evidence for independent Astra max plan review (maximum two rounds), then uses SDD, focused verification and a fresh Astra final review. Controller-owned integration/deployment remains ordered with the separate native rank-supersession change; no concurrent edits to `catalog.py` and no changes to the two protected b009 modules.
