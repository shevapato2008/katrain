# Physical SGF replay — independent ASTRA/MAX plan review, round 1

**Decision: CHANGES REQUESTED.** Three narrow contract gaps should be resolved before physical implementation. The overall FF4 interpreter and atomic physical-step approach are appropriate.

Reviewed `docs/superpowers/plans/2026-11-03-physical-sgf-replay.md` on `feature/baipu-physical-history-20261103`, product baseline `9e83f1ad5`, before the round-1 amendments. Account-history changes in progress were treated as separate, authorized work, not physical implementation. This review made no product, plan, database, or device changes.

## R1 — Separate placement acknowledgement from completed-step promotion

**Priority: P1.** Plan lines 59–65 correctly order pre-removal, placement, and post-removal, but then permit promotion only when the complete transaction target is verified. That misses a valid intermediate physical state and leaves a self-capture ambiguity.

A concrete example exists in the requested records: **118394, dense backend index 192, M3** replaces white with black and then removes white L3. If the user swaps M3 directly without the camera observing an empty intersection, the camera sees the valid board after placement with L3 still present. It matches neither the cleared pre-target nor the final target. Requiring the final target before acknowledging that placement prevents entry into the very phase that should light L3 blue. The existing single-extra-stone promotion (`physicalBaipuMachine.ts:123–133`) also cannot simply become a completed-step event.

Conversely, a single-stone suicide can leave the final board identical to the cleared pre-target, or even to the original board. **140859, dense index 245, S9** is such a single-stone suicide on an empty point. Matching that final board alone is not evidence that the required placement happened.

**Narrow fix:** Define the before, pre-cleared, placed, and final matrices from the authoritative step instructions. In an eligible placement stage, a verified placed matrix may acknowledge placement and enter post-removal without committing `k`; optionally allow already-removed subsets of the authoritative post-removal list. Require the placed stone to be observed in its correct color, and require all other differences to be explained by that step. Retain this placement evidence for the transaction. In post-removal, disable all next-move promotion. A final-board match must never stand in for missing required placement evidence when the stone self-captures. Give each new verification stage a fresh setup ID.

**Focused acceptance:** Cover one-motion replacement plus capture using the M3/L3 case, and a required suicidal placement whose before/final matrices match. The former must show removal guidance without forcing the correct replacement back off the board; the latter must not complete before placement and removal are separately acknowledged. Both commit once, after the final target is established.

## R2 — Explicitly remove observed-board adoption as an authoritative shortcut

**Priority: P1.** The plan requires authoritative entry and final-board verification, but does not resolve the existing ten-second fallback. `usePhysicalBaipu.ts:306–312` implements `adopt()` by reading the detected board and making that observation the new setup target. `BaipuSessionPage.tsx:668–670` exposes it as “摆好了，继续”; existing hook/reducer/page tests deliberately preserve this behavior.

Keeping that path lets a mismatching board certify itself. During a new post-removal phase, a stone that still needs removal can become part of the adopted target. Its subsequent `setup_complete` can then appear to finish the step, despite the authoritative SGF final board still differing. Same-color repeat auto-completion makes the same shortcut dangerous during entry verification.

**Narrow fix:** Specify that retry/recheck retains the current authoritative target and cannot replace it with `visionDetectedBoard()`. If recognition remains unusable, preserve a practical fallback through an explicit switch to operator-confirmed manual stages using the same pre/place/post instructions. The fallback must not describe an observed matrix as SGF truth or silently certify all remaining stages. Invalidate any pending detected-board request on transaction/session changes.

**Focused acceptance:** Exercise the stuck action with a mismatching post-removal board. Assert that it cannot change the authoritative target or trigger camera-verified completion; the explicit manual path, if selected, follows the declared stage confirmations.

## R3 — Pin and validate capture interpretation across the schema change

**Priority: P1.** Replay version 2 protects history identity (plan line 44), but the collection/autolabel contract at line 73 has no equivalent compatibility rule for already captured files.

`web/core/baipu_capture.py:370–378` writes no replay version. Its idempotency path at lines 385–395 reuses a frame by `applied_move_index` without verifying the current SGF interpretation. `vision/tools/baipu_autolabel.py:49–51` reparses the archived SGF with the latest builder, and line 446 reconstructs its board without checking the stored frame `board_hash`.

This is a concrete semantic change for an SGF accepted by the current builder, not only for the three formerly rejected records. I ran the current builder on:

```sgf
(;SZ[19]AB[aa]AW[ba][ab])
```

Current step 2 removes `aa` and has hash `76cacfde3937876c`; FF4 setup assignment retains the black stone at `aa`. An old image therefore has the same dense step index but a different board from the new reconstruction. Without a guard, it can silently receive a false black-stone label or be returned as an idempotent v2 capture.

**Narrow fix:** Persist replay version and exact SGF identity for new capture manifests, and validate identity, frame index, and persisted board hash before reusing/appending to an existing capture or autolabeling it with the new interpreter. Compatible legacy captures may remain usable when their existing hashes prove compatibility. Reject incompatible or unverifiable interpretation clearly while preserving the archive. No legacy interpreter, migration, or archive rewrite is required. Assign the small autolabel compatibility guard explicitly to P1; that production file is currently absent from its ownership list.

**Focused acceptance:** Use the setup SGF above as a legacy mismatch fixture, plus one ordinary legal legacy capture that remains compatible. Verify that neither idempotent capture reuse nor autolabeling silently crosses the mismatching interpretation.

## Findings that do not require expansion

The primary FF4 move and setup semantics are correct: [Go move execution](https://www.red-bean.com/sgf/go.html) replaces the destination, resolves adjacent opponent captures, then own-group suicide; [setup properties](https://www.red-bean.com/sgf/properties.html) assign stones without captures. Keeping `BaseGame` strict, preserving dense operation indices, treating AE as physical removal, and comparing every recorded state with the independent oracle are sound choices.

The plan already addresses final-step removal before done, pass mover identity, hint snapshot fallback, stale setup IDs, pause/undo/session cancellation, safe capture LEDs, and nonfinal no-LED frames. No new general SGF parser, camera-stack repair, gameplay refactor, or broad visual regression work is requested. After the three contracts above are explicit, one fresh round-2 review should be sufficient.
