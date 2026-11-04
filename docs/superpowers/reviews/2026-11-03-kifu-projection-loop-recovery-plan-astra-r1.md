# Projection loop recovery — independent Astra plan review, round 1

**APPROVED.** No blocking plan finding; no second plan-review round is needed for this scope.

Reviewed `docs/superpowers/plans/2026-11-03-kifu-projection-loop-recovery.md` and the relevant `project_album_batch`, `_maps` and unchanged identity `_raw_event_map` implementations.

The current projection already filters raw-name rows by literals, but subsequently passes the entire record list through repeated language/per-name mapping. A per-batch index of direct and selected raw-event literals addresses that repeated candidate scan without changing proof authority. The diagnostic-first condition is appropriate: expanded context counts must establish the actual workload before attributing improvement to this change.

The planned equivalence tests must preserve the mapper's original row precedence, unscoped fallback entries (including empty candidate subsets), direct and selected name IDs, labels and classification documents. Restrict only candidate records; retain all original proof qualification and the complete affected projection scope. Operation-count tests are a suitable focused guard against restoring the cross-product. No shared/global cache or signature change is needed.

The operational sequence retains the already-committed batch and original pending operation. Stopping only the exact controller-owned recovery process, stopping the diagnostic before projection/bulk, and later using the existing recovery path avoid business republishing or clearing the gate. Any actual phase change before intervention must be respected rather than resetting the observed gate. A separate concrete review before interrupting a trapped Cron preserves uncertain-commit handling.

Using the reviewed candidate projection module in an isolated recovery process is within the stated recovery scope when its source SHA is recorded; it must not modify the main application's files. Final publication, immutable deployment, preserved memory caps and unchanged rank-policy bytes remain part of completion.

The live CPU/memory, process and stack observations were supplied by the controller. This reviewer performed no live operation, diagnostic, provider call, source-data access or implementation. No broad test run was needed for this plan-only review.
