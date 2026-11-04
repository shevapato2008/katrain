# Numadate Canonical Correction — Astra Plan Review

**Status: APPROVED — Round 2 of 2; both R1 blockers are closed.**

Reviewed revision: the 208-line plan with SHA256 `5c44048c1039648004f08979c51ef9d4566f2983cb128d09a3640ba20eed4bf1`, at worktree HEAD `07cba438c3fe2586ef3fff5df65d862fbbe6fb27`. This is plan approval for implementation under the controller's workflow. No third plan-review round is requested. The concrete identity/text evidence approval, final implementation review and production-operation gates already stated in the plan remain applicable.

## R2 disposition

- **R1-1 closed.** Lines 131 and 149–155 give the child a reciprocal, allowlisted parent binding and make post-commit undo explicitly unsupported in this version. The common generic undo entry must reject both parent and child before reverse writes or batch-status/partial-undo branches, including emergency options. The four-cell correction marker prevents a stripped or corrupt child binding from becoming an ordinary undo path. Task 1 tests those refusals before and after the new publication/fact, with unchanged business rows, journals and statuses. Removing the dedicated undo implementation is a valid, proportionate alternative to implementing the guarded undo originally proposed; the required safety property is that the child cannot be reversed independently. Full before/after evidence remains available for any future separately reviewed rollback.
- **R1-2 closed.** The operator contract and lines 157–163 select the existing `name_apply` operation keyed by the frozen standard child bundle SHA and put parent and child in one `_locked_write` business transaction. The child keeps the artifact shape understood by current search readers and has no custom receipt. Its journals and explicit finite owner/album binding feed normal scope expansion, including the two old albums and spelling terms. The plan preserves session locks through real commit, projection and ready state, distinguishes rollback from uncertain/post-commit failure, retains the original pending operation and uses `recover_pending`. The focused post-commit ES failure test proves stable parent/child IDs, revisions, journals and receipt, followed by ready search without a second business mutation.
- **R1 implementation notes addressed.** The operator code digest now has a fixed running-file coverage/order, separate from protected b009. Preparation keeps PostgreSQL RR READ ONLY, with focused real-isolation/lock verification. The exact two-slot/zero-fact census is explicitly an apply-admission condition; the planned post-`0ef` case requires both old overlays and correction verification to remain valid after the legitimate new slot/fact. No new general undo, search, identity or authority infrastructure was added.

The fixed same-ID correction, original alias preservation, unchanged b009 recomputation/binding, truthful five-name qualification, old native876 source receipt, and original `0ef` M/key remain intact. The stable supersession commit is the sequential integration base. Proceed to the planned implementation and focused verification; this document itself performs or approves no live mutation.

R2 activity was limited to the revised plan and the relevant existing local search-scope code. No product edit, live database/service query, source-library filesystem access, publication or deployment occurred.

## R1 history — superseded by the R2 approval above

**Original status: NEEDS REVISION — Round 1 of at most 2.**

Reviewed plan SHA256: `72749c009a83f7f51322d032621069c934dc63040dac56704e059323f0e9f4b0`, at worktree HEAD `07cba438c3fe2586ef3fff5df65d862fbbe6fb27`. The review used the 193-line plan, relevant local implementation and the supplied finite dependency/predecessor summaries. No live database/service query, source-library filesystem access, product implementation, publication or deployment occurred.

The same-row correction and finite authority proof are viable. Two operational boundaries must be made explicit before implementation; neither needs a new table, generic authority framework or a protected b009 change.

## R1-1 — The standard child name batch can bypass the correction's atomic undo boundary

**Plan locations:** lines 127 and 145–149; Task 1 undo tests at line 162.

The plan prohibits generic `name_batch` undo of the **parent**, but puts the five name updates and evidence creations in an ordinary, independently applied child batch. The parent already fails generic undo because it has no ordinary signed `bundle`. The child is the exposed path.

`name_batch.undo_batch` at `katrain/web/kifu/name_batch.py:1810` accepts an ordinary applied child. Both its v4 atomic path and its older per-row path can restore the old names and delete the newly created evidence using only the child's current afterimages. There is no parent-correction dependency gate. A successful direct child undo would leave the canonical player and both corrected snapshots in place while restoring names whose first-pass source hashes bind the old canonical owner. The child would be undone, the parent still applied, and current names would fail qualification. This can also bypass the intended refusal after the new `0ef` publication/fact exists.

**Minimum revision:**

- Bind the standard child to this exact correction parent in a bounded, verifiable artifact field, preserving the existing bundle/research/journal membership rules.
- Add the narrow guard in the existing `name_batch.undo_batch` entry path, before any reverse business write. Direct generic undo of this correction's child must refuse; emergency/partial-undo options must not bypass it. Only the correction operator may reverse parent and child together after the already-planned full dependency checks. No general parent/child undo framework is needed.
- Extend the existing fixture with a direct `undo_batch(child_id)` refusal and unchanged row/journal/batch assertions, including after the `0ef`-style fact/publication. Keep the planned successful operator undo before later dependencies.

## R1-2 — The production writer must preserve the existing search commit/recovery protocol

**Plan locations:** operator contract/apply pseudocode, Task 1 line 160, and production apply/verification lines 184–188.

The plan says to reuse writer locks and later verify search, but does not select the existing search operation or define a committed-but-index-pending result. This matters because this change updates canonical names, aliases and all five display names, which are indexed business data.

`name_batch._locked_write` at `katrain/web/kifu/name_batch.py:188` holds session writer locks through the actual database commit and search refresh. With search enabled it requires a recognized `search_operation`; `historical_rank_repair._lock_writer` alone does not establish that protocol. `search_sync._operation_outcome` and `_batch_scope` also require known artifact shapes. Passing the new parent format through `catalog_publish`, or placing an arbitrary correction `receipt` in a batch then using it as a search batch, is insufficient: the existing reader interprets such a receipt as a native publication with its full `undo_guard` contract.

**Minimum revision:**

- Specify the concrete existing wrapper and operation reference for both apply and guarded undo. A small compatible option is `_locked_write(search_operation=("name_apply", {"bundle_sha256": child_bundle_sha}))` around the one parent-plus-child business transaction, and `name_undo` with that child ID for the correction operator's guarded reversal. Keep the child a standard artifact understood by the current search reader. Its name/evidence journals identify player5364 and expand to the affected albums; verify that the resulting scope includes both existing albums and the relevant old/new name terms. An equivalent already-supported operation is acceptable if its exact journal and recovery requirements are specified.
- Preserve the existing session-lock, pending-state, real-commit, projection and refresh ordering. A pre-commit failure rolls back the whole correction; an uncertain commit or post-commit ES failure is reported as pending and recovered from the original parent/child journals and operation reference. It must not be described as rolled back, silently retried as a new correction, or reported complete before search becomes ready.
- Add one focused case using the existing search test machinery: inject a post-commit projection failure, recover the original operation, and prove unchanged correction/name batch IDs, evidence revisions and receipts with no second business mutation. Verify the affected old album documents and corrected owner/display classification after recovery. No new search protocol or report framework is requested.

## Accepted boundaries and implementation notes

- The two protected files currently match the exact SHA256 pins in the plan. Their `_code_sha256()` depends only on those two files, so the new module and thin hooks can preserve the approved b009 authority. The plan correctly forbids using ordinary historical repair to replace these V3 rows.
- The old repairs have null predecessors. Their complete validated artifacts, unique creation journals, exact same-row canonical transition, unchanged source evidence and fresh current basis0 bindings provide the required finite proof. This does not require replaying old strict owner bindings after the rename or allowing alias-based rank ownership.
- The existing batch/change/name/evidence schema accommodates the proposed parent and standard child without migration. The new four-cell marker can stay confined to the correction operator through connection-bound trusted context; the existing first-pass reader can qualify new current names against the corrected owner image. JP conventional evidence and four explicitly generated names are an honest qualification split, contingent on actual source/text review of the concrete production bundle.
- The original V1 native receipt is a source authority, not a predecessor rank authority. Preserving the old canonical spelling as an alias is compatible with the existing reused-identity lookup; the planned native replay test must still verify the real receipt and coverage path.
- When defining `operator_code_sha256`, list its precise reviewed file/function coverage and compare it to the running implementation, not merely to a value echoed from the plan. Keep the complete-plan approval outside the transition hash as specified. This is implementation precision, not a request for a signature service.
- Add the post-publication assertion to the already-planned `0ef`-style integration case: the correction verifier and both old album overlays still succeed after the legitimate new slot/fact, while guarded undo refuses. The pre-apply exact reference census and the undo dependency guard must not accidentally become a permanent "player has exactly two slots and zero facts" read-authority condition.
- Verify the real PostgreSQL isolation/lock setup through the existing disposable test machinery or the focused implementation review; SQLite alone does not exercise `REPEATABLE READ, READ ONLY` preparation or production table/session locks. Do not expand this into a concurrency test framework.

Revise the two blocking boundaries and return once for the remaining plan-review round. The identity/text approval of the concrete frozen production content and the planned final implementation review remain separate; this review does not authorize a live correction.
