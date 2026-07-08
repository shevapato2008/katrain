# Review of Kiosk UI Redesign Implementation Plan

## Overall Verdict: Ship with Fixes

This is an exceptionally detailed and well-grounded implementation plan. The grounding in existing file paths, component names, and API endpoints provides a strong foundation for execution. The phased approach is logical, and the isolation of shared dependencies shows a mature understanding of the codebase's architecture.

However, the plan's high level of detail makes it rigid, and it contains several critical, incorrect assumptions that will lead to significant problems during implementation. The most severe issues are a likely boundary violation in Phase C regarding shared component modification and a flawed stub contract in Phase D.

The plan is salvageable and does not require a full rewrite. With the recommended fixes below, it can be a successful guide for implementation.

---

## 1. Correctness Defects & Boundary Violations

These issues represent the highest risk and will cause build failures or incorrect behavior.

### MAJOR: Phase C — Unacknowledged Edit to Shared Territory (`Board.tsx`)

*   **Defect:** The plan for Phase C (Research Down-port), particularly **Task C1.5**, assumes that the shared component `katrain/web/ui/src/components/Board.tsx` can be reused **as-is** to build the research analysis report view. The design document (`design.md` §5.3) requires this view to show features like `eval 色点` (evaluation color dots for candidate moves). These features are specific to the analysis context and are not present in the generic `GamePage` use of the board. It is highly probable that `Board.tsx` will require modifications (e.g., new props) to support these overlays.
*   **Boundary Violation:** The plan explicitly states that the only edit to shared territory will be `package.json` (Task A1). Modifying `Board.tsx` is a direct violation of this claim and is not flagged as a "Gate S" task. This will impact the main `galaxy` build and risks introducing regressions.
*   **Fix:**
    1.  Insert a new investigation task **C1.0: Verify Shared Component Interfaces**. This task must analyze `Board.tsx`, `useResearchSession`, and `LiveBoard` to determine what changes are necessary to support the Phase C features.
    2.  Based on the findings, create explicit tasks to modify these shared components.
    3.  Flag these new tasks as **Gate S**, acknowledging they are critical, cross-boundary changes that require both kiosk and galaxy builds to be verified.

### CRITICAL: Phase D — Flawed `physical-tsumego` Stub Contract

*   **Defect:** The review request (§7, Decision 8) and **Task D1.1** explicitly state that the hook signature in the *already-existing* `../katrain-kiosk-physical-tsumego` worktree **does not match** the stub contract proposed in the plan. The plan's decision is to proceed with the incorrect stub.
*   **Failure Scenario:** This guarantees a breaking API change upon integration. The purpose of a stub is to provide a compatible placeholder. Building against a known-incorrect contract defeats the purpose and creates guaranteed rework.
*   **Fix:** Modify **Task D1.2 (Create `usePhysicalTsumego.ts` stub)**. The stub's exported hook signature **must match the signature of the hook in the `katrain-kiosk-physical-tsumego` worktree.** The plan should adopt the real, known interface now to prevent a breaking change later.

---

## 2. Coverage Gaps

The plan fails to account for several states specified in the `design.md`.

*   **Gap:** **Phase B7 (摆谱 / Baipu)** is missing tasks for UI states detailed in `design.md` §5.5 under "待补" (to be added).
    *   `GeometryDriftBanner` when the board moves.
    *   Error state for when image capture fails.
    *   Confirmation dialogs for `resume`/`undo`/`exit`.
    *   UI state when the `capture` service is disabled.
*   **Gap:** **Phase B6 (设置 / Settings)** is missing tasks for the calibration states detailed in `design.md` §5.8 under "待补".
    *   UI states for the multi-step calibration process (`clearing`/`dark-ref`/`corners`/etc.).
    *   UI for failure diagnosis (e.g., "anchor not found").
*   **Fix:** Add new tasks within Phase B7 and B6 to explicitly implement these missing UI states. The current high-level "reskin" tasks are insufficient and risk these states being forgotten.

---

## 3. Verdicts on §7 Decisions

I have reviewed the 8 judgment calls and agree with most of them.

*   **A3 Atomic `isPortrait` Removal:** **Agree.** It's a single logical change. A "mega-commit" is appropriate for such a sweeping, mechanical refactor.
*   **`ImmersiveContext`:** **Agree.** Cleaner and more robust than managing state via routes.
*   **SmartBoardConsole Static Preview:** **Agree.** An acceptable stub that unblocks layout work.
*   **Header Hardware Status:** **Agree.** This is essential context for a hardware appliance. Not clutter.
*   **Baipu as Phase B Reskin:** **Agree.** It's a self-contained module, fitting the parallel nature of Phase B.
*   **Kifu Retargeting Post-Phase C:** **Agree.** Excellent sequencing that decouples module dependencies.
*   **Single Owner for Theme/Nav:** **Agree.** Prevents chaos in foundational files.
*   **Physical-Tsumego Stub-First:** **Disagree.** As noted in section 1, the stub contract must match the real, known implementation to be useful. The plan should be changed to use the correct signature.

---

## 4. Verdicts on §8 Risks

My assessment of the identified risks.

*   **`ImmersiveContext` Scope:** **Low Risk.** The plan's description of using the context from `KioskLayout` and having children set it is a standard and workable React pattern.
*   **Research Down-port Fidelity:** **High Risk.** As detailed in section 1, this is the plan's biggest flaw. The assumption of "as-is" component reuse is unfounded and will break the "no shared edits" rule.
*   **State A in 对弈 (B1):** **Medium Risk.** The plan's logic of using precedence seems sound, but this is a complex interaction zone between virtual and physical state machines. The implementation will require careful, exhaustive testing of race conditions.
*   **`PhysicalBoardGuard` Pass-through:** **Low Risk.** The plan directly addresses this with a dedicated verification test (B2.5). The approach is correct.
*   **i18n Coverage (B6):** **Low Risk (for this track).** The plan makes a pragmatic choice to scope the work tightly. This is an acceptable deferral, but the created technical debt should be tracked for a follow-up effort.
*   **Panel Width Refits (Phase C):** **Medium Risk.** The plan provides specific values, which is good, but these can easily be wrong. **Recommendation:** Add an explicit verification step to each relevant task in Phase C: "Verify layout on a 1024x600 viewport and ensure no overflow or clipping occurs."
*   **Test-mock Sweep (A3):** **Low Risk.** The plan includes a `grep` verification step (A3.2), which is the correct way to ensure full coverage of this mechanical change.
*   **Board-loss Surface Consolidation (B1.4):** **Low Risk.** The plan proposes a robust solution (`BoardSyncManager`) that directly addresses the problem of overlapping dialogs.

This plan is a strong starting point, but the identified issues, particularly in Phase C and D, must be addressed before execution to avoid significant rework and schedule slips.
