# Authoritative Rank Supersession — Astra Plan Review

**Status: APPROVED — Round 2 of 2; both R1 blockers are closed.**

Reviewed revision: commit `21cf4175819296e23215d683acc457ecb30642e9`; plan SHA256 `93885134248e660b141016fe88bbe3f994162c8cc766787441f059bec39bf6ee`. This is final plan approval for implementation under the controller's workflow. It does not substitute for the planned implementation verification or the review of concrete deployment/recovery/repair commands. No third plan-review round is requested.

## R2 disposition

- **R1-1 closed.** Tasks 4–5 now test the actual scope/tail branch, freshly evaluate complete source timestamps and exact source-version checks, and keep expired natural recovery at `allow_prod=False`. A separately pinned one-package operator has a concrete minimal boundary: actual TEST Cron role, ING/staging locks and existing native/ES protocol, original key/M/report/receipts/five-source scope, due backoff and phase, fresh integrity/state pins, and a reviewed age-only exception through existing public orchestration. It cannot widen the global window or fabricate natural success; an un-PROD package remains incomplete. This provides an actionable completion route without changing general scheduling or requesting the user's existing authorization again.
- **R1-2 closed.** Task 4 now places the unchanged original report validator and TEST receipt-SHA binding before the durable `test_verified` transition. The planned negative case explicitly proves that valid current evidence without the original report cannot populate the original slot, advance that phase or call sync. The existing saved-report transport case remains required.
- **Isolation clarification closed.** The resolver must establish PostgreSQL REPEATABLE READ and READ ONLY before its first proof/identity read, keep one connection/transaction snapshot, and assert the actual isolation/read-only settings in the existing disposable PostgreSQL test. This is sufficient; no extra concurrency framework is needed.
- **08b is within scope.** The local diagnostic artifact's SHA matches `35b93b837f65bd030c2047d889680a0db723d1573f4bc206ec3626e917ed49be`; its summary reports applied native967, 36 slots, 28 unchanged, 8 superseded and all proof checks passed. The revision uses the existing `prod_published` replay/current-context route, retains the original receipt and imports no new games. It exercises the already-planned mixed unchanged/superseded contract. The separate `0ef` owner/alias mismatch remains outside scope.

Two execution notes do not block approval or require another plan loop: when the private operator is concretized, “honor phase and due backoff” should reuse the existing `process_package_queue` transition into the durable resume phase before `resume_batch` (the latter alone does nothing for `retry_wait`), and `_session_lock` acquisition must be checked before continuing. Task 5's phrase `all36sources/slots` means the already-declared **18 source games / 36 slots**; correct that wording when convenient, with exact membership still derived from the immutable original manifest/receipt.

The four-product-file scope, shared single-hop resolver, unchanged repair policy/code hash, separate current-context verification and exact-five-album later PROD repair remain proportionate. Review activity was limited to the plan diff, relevant local orchestration code and safe diagnostic hashes/counts; no implementation, database/service query, deployment or source-library filesystem access occurred.

## R1 history — superseded by the R2 approval above

Round 1 of at most 2. Reviewed plan: `docs/superpowers/plans/2026-11-04-kifu-authoritative-rank-supersession.md`, commit `de047b650595e298cb401433af74208f8d1b02e5`. Review is limited to planning and local source inspection. No product implementation, tests against live services, publication, deployment, database query or source-library filesystem access was performed. The diagnostic Markdown hash matches the plan's `087a2f3d673d5c2fed714eab8708b5970548dd785760bf52294b49d57ae7d08a`.

## R1-1 — The real hourly admission path can prevent Task 5 from ever publishing this package

**Blocking locations:** plan Tasks 4–5, especially lines 162 and 188–190.

The planned end-to-end success assumes that a repaired replay lets the unchanged package naturally reach PROD. The real scheduler has another independent gate:

- `katrain/kifu_ingest/recent.py:155,187–188` uses a rolling seven-day window, including complete source time rather than calendar date alone.
- `katrain/cron/jobs/kifu_ingest.py:548–575` returns `test_verify` when even one frozen member is outside that window; it also requires this round's exact source recheck for `recent` admission.
- `katrain/cron/jobs/kifu_ingest.py:933–947` runs that tail with `allow_prod=False`.
- `resume_batch` at line 504 requires `allow_prod` before transporting the saved TEST report to PROD.

The five source games are dated 2026-10-28. The controller confirms that at review time they still have only about 1 hour 45 minutes of seven-day eligibility. Code review and deployment cannot rely on finishing before that expiry. Once outside the window, successful native replay alone leaves the original package un-PROD indefinitely, and Task 6 has no five original PROD albums to repair. Calling `resume_batch` directly with its default `allow_prod=True` in a test would miss this actual route.

**Minimum required revision:**

1. Task 5 must freshly determine actual `_frozen_scope` eligibility, current source-check coverage/version pins, original stage/report/receipt pins and exact PROD absence or idempotent existing publication before choosing a route. Preserve normal hourly processing when that route is genuinely admissible.
2. Specify a concrete, finite old-package recovery route for the expiry case within the user's already-authorized recovery/release work. Bind it to the exact original key/M, unchanged saved verified TEST report and receipt SHA, exact five-source membership, actual environment/role, current source integrity and independent PROD state. Use existing public orchestration/native publication and fixed receiver, with the existing staging/publication locks and ES protocol. Do not bypass native proof, accept new ranks, rewrite a stage/report/receipt, create a new ingestion key, alter the global window, or add general historical discovery. An absent or changed prerequisite fails before transport; an unknown/committed result is retained for idempotent recovery.
3. Freeze the exact recovery command/pins for the controller's operational review; this is concretization of existing authorization, not a new permission request. Record an explicit finite recovery as such, never as natural scheduler success. A package left un-PROD is not completion of the requested five-game journey.
4. Extend the existing Task 4 fixture with the real scope/admission branch: an expired five-game package must not naturally call PROD sync; the separately pinned recovery route must use the exact old report/M/key and yield the original idempotent receipts. One focused admission/recovery scenario is sufficient; do not build a second scheduler or broad new test framework.

## R1-2 — A current supplement must be rejected before it can populate the original TEST evidence slot

**Blocking locations:** plan Tasks 3–4, especially lines 155 and 163; contract lines 84–86 states the right rule but the planned wiring does not identify its durable-state gate.

The current `resume_batch` implementation takes any dictionary returned by `test_verify`, adds M, writes it to `test_verification`, and advances `test_published → test_verified` (`katrain/cron/jobs/kifu_ingest.py:497–502`). `StateStore._advance` initially requires only a dictionary for a verification receipt (`katrain/kifu_ingest/state.py:293–296`). Transport validates the original report later.

After Task 3 introduces a distinct current-supplement return format and Task 4 supplies the authority loader to this verifier, a legacy package repaired while still at `test_published` could therefore store the supplement in the original TEST verification slot. The receiver would correctly reject it later, but the state would already claim original verification and hold an incompatible immutable report. That violates the plan's own requirement that missing original TEST evidence stays refused.

**Minimum required revision:** explicitly validate the publication-authorizing report with the existing original `validate_test_verification` path, or an equivalently strict callback guard, **before** `advance_batch(..., "test_verified", ...)`. The separate current report remains usable through its trusted current validator and cannot populate or replace that original TEST evidence slot. Do not teach the original transport validator to accept the supplement, add a stage/table, or manufacture an old report from current API output.

Add one focused orchestration negative case: original V1 receipt exists, official successor is applied, phase is `test_published`, original TEST verification is absent, and current API evidence is valid. Assert refusal before any `test_verified` transition, an unchanged original verification slot, and no `sync` call. Keep the existing `test_verified` case proving that an already-saved old report transports byte-for-byte.

## Implementation precision — coherent PostgreSQL reads

Nonblocking clarification for Task 2: spell out `REPEATABLE READ, READ ONLY` (established before the first proof query), or an equivalent single-snapshot mechanism. `READ ONLY` alone does not make multiple queries share a snapshot under PostgreSQL's usual `READ COMMITTED` isolation; the existing disposable repair fixture explicitly uses `READ COMMITTED`. Add isolation/read-only assertions to the already-planned PostgreSQL case. This needs no new concurrency framework or live production check.

## Accepted design boundaries

The plan otherwise supplies an implementable, appropriately limited authority model. Source inspection confirms that `historical_rank_repair._validate_part` preserves current code/policy bindings and only permits the relevant replaceable predecessor formats; the applied part, selected journal and frozen native afterimage can prove the requested single hop. Keeping the repair modules unchanged preserves the approved code hash. The explicit requirement to continue original immutable fact validation closes the dangerous early-`continue` shortcut in `_check_rank_replay`.

The separate trusted loader, exact M/receipt/DB/source mapping bindings, context-specific checkpoint algorithm, full provenance checks, fixed read request and prefetch budgets are sufficient design boundaries for this compatibility change. The original report remains historical transport authorization; TEST successor context cannot authorize remote rank writes. The separate exact-five-album PROD repair correctly acknowledges the existing streamed scalar census and does not pretend this resolver performs that repair. No new service, signature system, table, general journal-chain resolver, V3-to-V3 expansion or unrelated investigation is warranted.

Resolve R1-1 and R1-2 in the plan, then return once for the remaining review round. No implementation or live operation is approved by this review artifact.
