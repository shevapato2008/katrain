# Committed PROD projection recovery — independent Astra operational plan review

**APPROVED.** No blocking plan finding. Reviewed `docs/superpowers/plans/2026-11-03-kifu-committed-projection-recovery.md` on 2026-11-03.

Reviewed plan SHA256: `0a9d7d7659f5ae64ca8363f209edb58f17e73b57d51c9ddb247dac27e9041573`.

The controller's measured cgroup OOM, already-applied PostgreSQL batch 967 and matching pending ES operation justify the proposed bounded recovery. Increasing only the actual Web container's Memory from 4 to 8 GiB and total MemorySwap from 8 to 12 GiB avoids restarting the surviving Web service. The private beforeimage, operator lock, fresh available-memory check, exact ID/image/cap/role CAS and post-update inspection are the required boundaries already present in the plan. Future replacements must retain that recorded actual delta.

Read the existing `search_sync.recover_pending`, `_operation_outcome`, `_apply_projection` and `name_batch._locked_write` paths. Recovery takes the existing writer locks, validates ES state, and resolves a catalog operation from its applied batch plus exact manifest/publication reference. A committed operation rebuilds its original scope, completes bulk/refresh, and only then writes READY. It does not republish business data or create a new publication key. Errors retain the gate for inspection; an unexpected change of the observed original operation must be inspected rather than cleared or re-keyed.

The plan correctly requires actual READY plus search HTTP 200 before resuming the frozen receipt/API checkpoint. Delaying UI replacement until the receiver is inactive and retaining the fresh-backup/idle-READY prerequisites for historical application prevents this outage recovery from bypassing those separate acceptance steps.

This was a focused plan/source review. The OOM, live batch/gate and host-capacity observations are controller evidence; this reviewer made no live query, Docker mutation, service change or provider call. No additional test infrastructure or product change is required for the stated operation.
