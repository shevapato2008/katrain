# Numadate Canonical Correction — Independent Code/Security Review

**Status: APPROVED — both findings and the supplied-row precision item are closed; no remaining blocking code/security finding.**

Final reviewed implementation: `de9faeed5743fd25e3b8e940a28219095527a42a..335a3cfba488c81c0a71e5f76343a73b81354d50`, including the marker/undo change `a91442929`, API/catalog hooks `bf6af0078`, core/CLI `fb95dfcdbf8404af6e3c69d075fed5a2a7471b1b`, corrections `4eb452f5a9557afb0703ae2fb5474ecec9b37d91` / `693fc7404be7a91471862abd1c08ff916044963e`, and the exact original-package key correction `335a3cfba488c81c0a71e5f76343a73b81354d50`. Specification compliance was checked before code quality/security, against the approved R2 canonical-correction plan and its documented implementation clarifications, including the historical read-pin precision accepted below. This review includes the new catalog hook's effect on the already-approved native supersession guards; it does not reopen the prior supersession design.

Final running operator digest independently recomputed: `6663d04de97474e3e5d80bbcb09e45992e68ad7025d88404e999365058212663`. This approval concerns code only; the actual identity/text evidence, frozen production plan, live correction, original-package replay and deployment retain their separate review/authorization boundaries.

## R1-1 — P2: current child evidence bypasses the bounded-reader preflight

At `numadate_canonical_correction.py:1296–1302`, the correction verifier bounds the child **journals**, then calls the unchanged `name_batch._check_applied_v4`. That helper separately fetches each current name and evidence row in full, including `research_payload`, before comparing them to the bounded journals/candidates. The current new evidence rows are not preflighted by the correction verifier. A bounded journal afterimage does not bound a separately fetched, possibly changed current row.

An independent disposable SQLite reproduction applied the real correction fixture, enlarged only the new CN evidence's `research_payload` by `MAX_NAME_BYTES + 1` characters, then invoked `verify_correction`. The verifier issued the full evidence SELECT and only afterward rejected the altered payload. Thus a damaged row can make the API/native read proof load arbitrarily larger name material than the approved 512 KiB ceiling before refusing it.

The same bounded-read contract requires the full verifier's SQL to inherit a finite timeout. Standalone `_readonly` and apply set a 5-second timeout, but the API calls `verify_correction` directly. That wrapper currently enters neither `_readonly` nor `ranks._bounded_queries`; its initial aggregate, JSON-array and row queries inherit the caller's timeout. The protected binder's later local timeout does not cover those earlier queries. The monotonic budget is checked between SQL calls and cannot cancel a blocked/slow query.

Minimum correction:

- Before the unchanged standard name verifier, preflight the exact current five names and their current evidence IDs, including every column that the old helper will fetch; charge them to the existing selected-material/authority budget and retain all old validation.
- Wrap the complete proof in the existing protected timeout context, restoring the caller's previous timeout. Do not modify the protected module or add a new query framework.
- Add a focused oversized-current-evidence refusal-before-fetch regression and a focused complete-proof timeout/restoration check.

Independent reproduction: `/tmp/test_numadate_astra_focused_review.py::test_oversize_new_evidence_is_selected_before_rejection`; **1 passed** as part of the two-node review reproduction. A pass confirms the identified failure path; it is not an acceptance test for the required fix.

**Closed by `4eb452f5a9557afb0703ae2fb5474ecec9b37d91`.** `_guard_current_name_material` now preflights every column of the actual five player5364/language rows and their five current evidence rows, checks exact frozen name IDs/owner/language/evidence pointers and charges the combined material to the 512 KiB/shared authority budget before invoking the unchanged name verifier. Its query predicate matches the old qualifier, including a changed-owner/replacement-row regression. The public proof wrapper now uses the unchanged protected `_bounded_queries` context around all proof queries. Independent new-node verification and final-byte PostgreSQL context/restoration evidence below confirm the correction.

## R1-2 — P2: historical reads unnecessarily freeze all six current operator files

The controller identified that `_verify_correction` calls `_validate_plan`, which requires the plan's operator SHA to equal the running SHA over all six files, including the CLI and the frequently changed API/catalog modules. Consequently an unrelated later API/catalog edit revokes both already-applied overlays even when the complete historical authority, current owner, journals and protected b009 semantics remain unchanged.

The reviewer independently reproduced the coupling by applying the fixture, changing only the reported running operator SHA, then observing both read verification and apply refuse with `operator code changed`: **1 passed in 0.98s** in the temporary review reproduction. Read refusal is the defect; apply refusal must remain.

The minimum accepted correction keeps prepare/apply's current-code comparison strict by default, but lets the internal applied read verifier validate the recorded operator SHA as historical execution evidence: a valid SHA bound by the exact reviewed plan, its approval and parent batch hash. The reader must retain fixed format v1 semantics, the current protected b009 check and the entire independent database evidence proof. This requires no new registry, signature system or old-owner exception. It implements the plan's explicit prepare/apply running-file admission and preserves meaningful reads after unrelated maintenance; the controller and reviewer agreed to this implementation precision within the current review.

**Closed by `4eb452f5a9557afb0703ae2fb5474ecec9b37d91` and `693fc7404be7a91471862abd1c08ff916044963e`.** `_validate_plan` remains strict by default; applied database verification explicitly validates the historical operator pin without equating it to current hot-file bytes. The thin CLI's read-only `verify` follows the same historical policy while its `apply` and the core/idempotent writer remain strict. The independent CLI test uses real applied disposable-fixture evidence: changed running hash still yields the original receipt for `verify`, while `apply` refuses and all business state stays unchanged. Current protected b009 and all independent authority checks remain mandatory.

## Small specification precision

At `numadate_canonical_correction.py:1321–1330`, `expected_rows` compares only row ID, snapshot SHA and batch ID, whereas the approved contract calls for exact supplied/current row comparison. A supplied row with changed `album_id` and `rank_fact_id` still receives a proof. Comparing the supplied complete row to the already-loaded current row would close this small contract gap without another database read.

This is not classified as a separate authority-bypass blocker: the actual API additionally compares the internal proof's album/side, the complete journal, source and canonical owner; catalog retains its complete-journal and fresh b009 binding guards. The reviewer did not find a path by which this reduced comparison defeats those existing call-site guards.

**Closed by `4eb452f5a9557afb0703ae2fb5474ecec9b37d91`.** The verifier now requires every real snapshot base column and compares its canonical full image to the already-loaded current row. Joined metadata cannot substitute for missing or altered base fields. Six independent regression parameters passed.

## Post-approval exact publication-key correction

**Approved at `335a3cfba488c81c0a71e5f76343a73b81354d50`.** Actual source capture showed that the original published key is `19x19-batch-0ef14d803cd49221b37f4648`. The earlier planning/implementation context omitted `batch-`, causing the fixed validator to reject a legitimate read-only preparation. The product diff changes only that exact literal; the fixture follows the actual contract, and the added test accepts the published key while refusing the former shortened key. It does not accept an arbitrary key or change the original stage, manifest, receipt or report.

The reviewer inspected `output/kifu-rank-hourly-20261103/numadate-production-data/original-package-provenance.json`, SHA256 `f6afb6525772d6323389919a306fedf55869b2bdcc6c7582fd50cd51210c822b`. Its producer confirms an actual HOME REPEATABLE READ / READ ONLY capture at `2026-11-04T00:34:12.507324+00:00`, indexed native1438 and the unique stage row for its M, matching native/stage receipts and report receipt binding, 19 games /38 slots /95 checks, durable `retry_wait` with resume `test_verified`, zero writes and zero database SGF-body reads. The saved original pins are:

- M: `4a0c37b8b54fa84071fa60df5b23c492b96aad04047a4076b1612d7ffe546ea4`.
- HOME1438 receipt SHA: `f7b3709802fc5ed1c7d15b43b163dd9ccece935f075a7e7c1bb17c71c867734f`.
- Original report SHA: `0ddebd91aff0383ebbc4c37f63b8d51240ea2bd359bd0b8aa1d8025730b68377`.

Independent focused execution of `test_original_package_requires_exact_published_batch_key`: **2 passed in 3.37s**, with the complete disposable database state unchanged for both parameters. The implementer additionally reports **5 passed in 2.12s** for these two cases, atomic correction and both CLI cases. The final core SHA is `b5e91720f0cbebb86f4b64631b42166ebd0e3e101985859f269fb66e085f3ab1`; core-test SHA is `f8712548a8575096542023e64007d82b0e5af92715e0de4a584f53ad2be918a8`. CLI and both protected files are unchanged. No full suite or PostgreSQL run was repeated for a literal-only admission correction; the previously verified PostgreSQL code paths are unchanged. This finite original-key verification does not approve the later complete production identity/text/plan artifact.

## Checks already completed

- Protected file hashes independently match `historical_ranks.py=b719462b4fcbc939b44745c0c54085e530b33e29a9887c8745546a7eb91395c8` and `historical_rank_repair.py=8e0c985594446d9cc4bd9b6a05568f584a0f484dc7fecac5bfd55e62a362b2a2`; combined protected code remains `b009f59cb7160689a2ee48ebc1ac328ebbffe3fdb1ccb0217b42183e977d7300`.
- The approved qualification clarification changes `qualification.player_ref` together with the top-level canonical ref. Other source/numeric/qualification fields remain exact; apply permanently renames the same owner and requires unchanged b009 recomputation to equal the reviewed candidates before replacing the two rows.
- The read authority validates the real applied old repair artifacts and null-predecessor creation journals, exact same-row owner/alias transition, immutable source and native876 evidence, corrected current journal afterimages, reciprocal standard child binding and fresh basis0 bindings. It does not rerun the old strict binder using an invented owner.
- Generic parent/child undo refuses before reverse business mutation, including emergency and partial paths, stripped parent binding and the evidence-journal marker fallback. Marker acceptance requires the actual connection-bound operator context; serialized marker/hash input alone is insufficient.
- Apply uses the existing `name_apply` child SHA operation around the full transaction and preserves real commit/search recovery ordering. The focused post-commit search test asserts recovery of the original operation, stable evidence and receipts and no second business mutation.
- The new API authority cannot fall through the native-format branch. Catalog keeps the old full current journal, source, fact and owner/b009 guards; the added authority is an explicit separate branch. Lazy imports do not introduce an observed import cycle.
- The reviewed fixture covers the original V1/no-rank native replay, subsequent strict new-canonical V3 publication, preserved old overlays after a new slot/fact, and opposite-side snapshots remaining outside the two-slot admission scope.
- The controller's complete pre-closure integrated log `/tmp/kifu-numadate-final-integrated-tests.log` reports **487 passed, 3 skipped, 1 deselected in 155.16s**. The one deselected normative zh-ko bool/int failure was independently established as baseline; no product qualification relaxation was included. The initial independent review reproduction reports **2 passed in 1.50s**, and the separate historical-read reproduction **1 passed in 0.98s**; these reproduced the initial defects, not acceptance of them.
- After the core correction, the implementer/controller reports **115 passed, 1 skipped in 30.89s** for the three Numadate core/marker/authority files. The reviewer independently ran all **11 new focused parameters: 11 passed in 6.29s**, inspecting the final core diff and its exact `e06cce0b…22640` bytes. After the one-line CLI correction, the reviewer independently ran both additional CLI parameters: **2 passed in 1.04s**. No full unrelated suite was repeated for those final changes.
- The reviewer inspected PostgreSQL V2 evidence bound to the initially approved `693fc7404` bytes, `output/kifu-rank-hourly-20261103/pg-numadate-readonly-binder-exact-node-v2.json`, SHA256 `6e2003e3a0ab4b8895ccf1980b03f0d50bfa47433cad971a7ba9a069137e1960`: **1 passed in 1.50s**, return code 0, zero UUID schema residue, exact approved file/operator/protected pins before and after. It verifies the real protected b009 binder in RR READ ONLY without writer locks, plus the public proof wrapper's actual PostgreSQL 5-second timeout and restoration to its caller's `4321ms` on success and refusal. The wrapper check substitutes a small proof body; the separate focused SQLite test runs the complete proof and asserts every SELECT is inside that context. This is precise boundary coverage, not a claim that all authority queries were exercised against production PostgreSQL.
- `git diff --check de9faeed5` passes for the reviewed final working tree, including this review record.

The V2 record's source hashes were independently compared with the working tree at the initial `693fc7404` approval, before the literal-only correction above:

- Core: `e06cce0bd7872208fc0b87276ed045f405722fbc5905d51e96ec00da72622640`.
- CLI: `44dfedc182773cad89b14da1c81f5755eaf19312293bfeb4fcde7630851b979e`.
- Core test file: `188d537940993d3de1dce862cf2552629c8b32c4e309133c2cfc4306339b2df2`.

The earlier 1.44-second PostgreSQL evidence remains historical and is superseded by V2 for this approval. The historical read-pin clarification does not change writer admission or the frozen protected b009 algorithm.

This review has used local source inspection and disposable SQLite fixtures only. It has made no product edit, live database/service call, production write, deployment, publication or source-library filesystem traversal, and has not printed real SGF or credentials. The concrete live identity/text evidence, original package pins, frozen production plan and production apply remain subject to their separately required artifact reviews.
