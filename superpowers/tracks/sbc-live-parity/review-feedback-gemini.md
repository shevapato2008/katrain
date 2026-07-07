# Plan Review: sbc-live-parity — Feedback

**Reviewer**: Gemini
**Date**: 2026-06-23
**Verdict**: The revised plan is **vastly improved** and demonstrates a solid grasp of the complexities involved. It has correctly identified and addressed the most severe initial flaws (gate logic, routing order, error propagation, phantom parameters). The remaining risks are manageable. The plan is approved, contingent on the explicit implementation of all proposed fixes and careful validation of the points listed below.

---

### (a) Problem & Recommendation List

#### Blockers (Addressed in Plan, Must Be Implemented as Specified)

*   **[blocker] Freshness gate logic was fundamentally flawed, but the proposed fix is correct.**
    *   **Problem**: The original `length < move_count` check was broken due to `0..move_count` inclusive indexing (off-by-one), sparse analysis results from the DB (`get_successful_analysis` at `analysis_repo.py:127` only returns `SUCCESS` rows, ignoring pending/failed holes), and the inability to detect in-place updates (`update_analysis_result` at `analysis_repo.py:192`).
    *   **Evidence**: `analysis_repo.py:281` confirms `range(max_move + 1)` which is a `0..move_count` closed interval.
    *   **Fix**: The plan's pivot (`plan.md`, P2.2) to a **position-aware** check (`analysis[move_count] == null`, `analysis[currentMove] == null`) and a **mandatory delta-check** (`tipChanged`) is the correct and robust solution. The no-progress backstop is also a crucial addition for stability.
    *   **Recommendation**: **`go`**. Implement the freshness gate exactly as specified in the revised plan. The TDD cases must model sparse/failed states, not just ideal contiguous ones.

*   **[blocker] FastAPI route shadowing would have broken the featured match endpoint.**
    *   **Problem**: Placing the `/live/matches/featured` proxy after `/live/matches/{match_id}` would cause FastAPI to incorrectly interpret "featured" as a `match_id`.
    *   **Evidence**: Upstream `live.py` correctly declares `featured` (line 210) before `{match_id}` (line 264). The original plan's skeleton was incorrect.
    *   **Fix**: The plan (`plan.md`, P1.2) now explicitly requires placing `proxy_live_featured` *before* `proxy_live_match`, which is correct.
    *   **Recommendation**: **`go`**. Implement the routing order as specified in the revised plan.

*   **[blocker] Touch-based PV preview was impossible without modifying the shared component.**
    *   **Problem**: The original plan claimed `AiAnalysis` could remain unchanged, but the component has no click/tap handlers, only `onMouseEnter/Leave` (`AiAnalysis.tsx:222-223`), making the "tap-to-preview" goal on the page level impossible.
    *   **Evidence**: `AiAnalysis.tsx` code confirms the absence of any click or tap event handling within `MoveRow`.
    *   **Fix**: The plan (`plan.md`, P5) has been revised to include adding an **optional `onMoveSelect` prop** to `AiAnalysis`. This is a sound, "opt-in" approach that prevents regression in Galaxy (which won't pass the prop) while enabling the new functionality in Kiosk.
    *   **Recommendation**: **`go`**. Implement the `onMoveSelect` prop as described. This is a critical change.

#### Major Issues (Addressed in Plan)

*   **[major] The `fetch_detail` parameter was a phantom, and the plan to remove it is correct.**
    *   **Problem**: The frontend and original proxy plan were built around a `fetch_detail` parameter that does not exist in the upstream `get_match` API.
    *   **Evidence**: `live.py:264-297` (`get_match` function) has no `fetch_detail` parameter and unconditionally returns the full `MatchDetail` object.
    *   **Fix**: The plan (`plan.md`, P1.1, P2.2) correctly identifies this, removes the entire `fetch_detail` propagation logic, and accepts that a lightweight details poll is not possible with the current backend.
    *   **Recommendation**: **`go`**. The analysis and resulting simplification are correct.

*   **[major] Error code propagation was lossy, but the new `_proxy` wrapper fixes it.**
    *   **Problem**: The original proxy blanket-mapped all upstream errors to 502, hiding important distinctions like 404 (Not Found).
    *   **Evidence**: Existing code in `board.py:145` shows the `except Exception ... HTTPException(status_code=502)` pattern.
    *   **Fix**: The plan's new `_proxy` helper function (`plan.md`, P1.2) correctly differentiates `httpx.HTTPStatusError` (preserving 4xx codes) from connection errors (mapped to 502).
    *   **Recommendation**: **`go`**. This is a significant improvement in robustness and debuggability.

*   **[major] Cross-build contamination risks from hardcoded routes and missed imports were real.**
    *   **Problem**: `MatchCard.tsx` had a hardcoded `/galaxy/live` route, and the plan initially missed `report` pages as consumers of the components being moved.
    *   **Evidence**: `MatchCard.tsx:43` confirms `navigate('/galaxy/live/${match.id}')`. `ReportDetailPage.tsx` imports `AiAnalysis`, `PlaybackBar`, and `TrendChart`.
    *   **Fix**: The plan (`plan.md`, P3) now explicitly includes tasks to parameterize the `MatchCard` navigation and to update the import paths in the `report` pages and their corresponding test files.
    *   **Recommendation**: **`go`**. The plan is now much more complete and safer from a build-boundary perspective.

#### Minor Issues & Nits

*   **[minor] Kiosk i18n is not just "reuse" but requires new wiring.**
    *   **Problem**: The plan understates the i18n effort. Kiosk currently makes zero calls to `i18n.translatePlayer` or `loadLiveTranslations`. This is a new integration, not just reuse.
    *   **Evidence**: `kiosk/` folder has no calls to these functions (based on prompt's `grep` finding). `i18n.ts:52-53` shows that if `liveTranslations` isn't loaded, `translatePlayer` is a no-op, returning the original name.
    *   **Recommendation**: **Amend P6**. Add an explicit task to call `loadLiveTranslations` during Kiosk app initialization to prevent untranslated names and `live:key` strings from appearing.

*   **[minor] The `verify:kiosk-2d` script is a weak safeguard.**
    *   **Problem**: The script only checks for `three.js`, as confirmed by the failed `npm run` attempt and prompt description. It wouldn't catch the hardcoded `/galaxy/` route string or other logic-level cross-boundary contamination.
    *   **Recommendation**: **Strengthen P6**. The "全量回归" step should include extending `verify-kiosk-2d` (or adding a new script) to `grep` the kiosk build output (`dist/`) for forbidden strings like `"/galaxy/"` or `"/api/v1/live"`.

---

### (b) Per-Stage Verdict

*   **P0 (基线)**: `go`. Simple setup verification.
*   **P1 (后端代理)**: `go`. The plan correctly addresses routing order and error propagation.
*   **P2 (前端数据层)**: `go`. The revised freshness gate logic is sound and a massive improvement.
*   **P3 (组件提升)**: `go`. The plan now correctly identifies all necessary file modifications, including the critical `MatchCard` and `report` page fixes.
*   **P4 (kiosk 列表页)**: `go`. Straightforward implementation using the newly-lifted components.
*   **P5 (kiosk 详情页)**: `go`. The plan now correctly includes the necessary opt-in change to the shared `AiAnalysis` component for touch support. The question of vertical layout (Q3) must be resolved before this stage is considered complete, but it doesn't block starting the work.
*   **P6 (收尾)**: `go`. Needs the minor amendments suggested above (i18n wiring, stronger verification script).

---

### (c) Single Biggest Risk

The single biggest risk is **Galaxy regression**.

Even with the careful, opt-in changes, modifying a shared, time-sensitive hook like `useLiveMatch.ts` and a core component like `AiAnalysis.tsx` carries inherent risk. A subtle bug in the new freshness gate's state management (`liveRef`, `staleRef`) or the new `onMoveSelect` prop could silently degrade the live viewing experience for the primary Galaxy user base (e.g., missed updates, incorrect hover behavior). The consequence is breaking the main product while trying to add a feature to a secondary one. The mitigation is thorough, isolated testing of the hook and dedicated regression testing on the Galaxy UI after P2 and P5 are merged.

---

### (d) Scope Judgment

*   **Over-designed (Can be cut)**:
    *   Nothing. The plan is lean and focused. The original `fetchDetail` optimization was correctly identified as based on a false premise and cut.

*   **Under-designed (Must be added/clarified)**:
    *   **`useLiveMatch` ref stability (Needs clarification)**: The plan notes `fetchMatch` must be stabilized but doesn't specify *how*. The implementation should wrap it in `useCallback` with an empty dependency array and read `matchId` and `currentMove` from `liveRef.current` inside the function body to prevent the polling `setInterval` from churning. This is an implementation detail, but a critical one for stability.
    *   **Kiosk i18n Wiring (Must be added)**: As noted, P6 needs an explicit task to integrate `loadLiveTranslations` into the Kiosk app's startup sequence.
    *   **Vertical Layout (Q3) (Must be resolved)**: This is marked as an open question, but for a primarily vertical device, it's a core design constraint, not a polish item. P5 should not be considered "done" until a functional vertical layout is in place, even if it's simple stacking initially. Deferring this risks a feature that is functionally complete but unusable on target hardware.
    *   **`verify-kiosk-2d` Script (Should be enhanced)**: The final verification in P6 should include improving this script to be a more meaningful safeguard against cross-build contamination.
