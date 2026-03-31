# Review Prompt: Kiosk UI Alignment Plan — SBC v2

## Your Role

You are reviewing an implementation plan for fixing kiosk UI bugs in KaTrain, a Go/Baduk teaching application. The kiosk UI runs on RK3562 SBC (single-board computer) devices with 5"/7"/10" touchscreens. The plan was written by Claude and will be executed by Claude. Your job is to identify flaws, risks, and missed edge cases before implementation begins.

## Project Context

- **KaTrain** is a Go/Baduk teaching app with dual UI: a Galaxy web UI (desktop browsers) and a Kiosk UI (SBC touchscreen devices).
- Both UIs share a React frontend (`katrain/web/ui/src/`) with shared components in `components/` and UI-specific pages in `galaxy/` and `kiosk/`.
- The backend is FastAPI (`katrain/web/server.py`) with game sessions managed via WebSocket.
- The kiosk runs in Chromium `--kiosk` mode on Debian/ARM64, connecting to a remote KaTrain server in "board mode."
- The Galaxy web UI is the mature reference implementation. The kiosk was built more recently and has multiple bugs.

## User's Original Requirements

Four issue groups were identified during on-device testing:

### Issue 1.1 — Board Preview in Setup Page

The AI game setup page (AiSetupPage) shows a plain brown/yellow box on the left side where a board preview should be. Regardless of board size selection (9x9, 13x13, 19x19), it's just a colored rectangle with text. **Expected:** A real board with wood texture, grid lines, star points, and coordinates — matching the Galaxy web UI.

### Issue 1.2 — Stone Placement Offset

When playing a game in the kiosk, stones appear at the **upper-left of the clicked intersection** instead of at the center. The offset is consistent and proportional to distance from the board origin. This makes the game effectively unplayable on the touchscreen.

### Issue 1.3 — Online Lobby Non-Functional

Clicking "在线大厅" (Online Lobby) in the Play page does nothing. No navigation occurs. This feature works correctly in the Galaxy web UI. The fix must also be responsive across SBC screen sizes (5"/7"/10").

### Issue 2 — Tsumego 404

After selecting a difficulty level (e.g., 15K) in the tsumego (life-and-death problems) module, the page shows an HTTP 404 error. The entire tsumego workflow beyond level selection is broken.

## Proposed Plan

See the attached `plan.md` for the full implementation plan. Summary of the 4 tasks:

### Task 1: Fix Stone Placement Offset

**Diagnosis:** The `<canvas>` element in `Board.tsx` has `width`/`height` attributes (drawing buffer) but no CSS `width`/`height` in its inline style. This causes a mismatch between `canvas.getBoundingClientRect()` and `canvas.width`, making the `scaleX`/`scaleY` conversion in `canvasToGridPos()` incorrect.

**Proposed Fix:** Add `width: '100%'`, `height: '100%'`, `display: 'block'` to the canvas element's inline style.

### Task 2: Fix Tsumego 404

**Diagnosis:** `TsumegoLevelPage.tsx` calls `GET /api/v1/tsumego/levels/${levelId}` which doesn't exist. Available API endpoints are `/levels`, `/levels/{level}/categories`, `/levels/{level}/categories/{category}`, and `/problems/{problem_id}`.

**Proposed Fix:** Rewrite data fetching to: (1) fetch categories for the level, (2) fetch problems for each category in parallel, (3) combine and display.

### Task 3: Board Preview in Setup Page

**Diagnosis:** `AiSetupPage.tsx` renders a `<Box bgcolor="#8b7355">` placeholder instead of a real board.

**Proposed Fix:** Create a minimal empty `GameState` object and render the shared `Board` component in read-only mode.

### Task 4: Wire Online Lobby Route

**Diagnosis:** `PlayPage.tsx` navigates to `/kiosk/play/pvp/lobby` but this route doesn't exist in `KioskApp.tsx`. Galaxy has a working `HvHLobbyPage`.

**Proposed Fix:** Add the missing route and reuse Galaxy's `HvHLobbyPage` component (or wrap it for kiosk-specific navigation paths).

## Review Checklist

Please evaluate each task against these criteria:

### Correctness

- [ ] Is the root cause diagnosis accurate? Could there be alternative or additional causes?
- [ ] Will the proposed fix actually solve the problem, or could it introduce new issues?
- [ ] Are there edge cases not addressed (e.g., devicePixelRatio on HiDPI screens, touch events vs mouse events)?

### Completeness

- [ ] Are all files that need modification identified?
- [ ] Are there dependencies between tasks that affect implementation order?
- [ ] Does the tsumego fix handle the case where the remote API (board mode) has different response formats?
- [ ] Does the online lobby reuse account for navigation path differences (`/galaxy/` vs `/kiosk/` prefixes)?

### Risk Assessment

- [ ] Could the canvas CSS fix (`width: 100%`, `height: 100%`) cause regressions in Galaxy web UI where it currently works?
- [ ] Could the canvas become blurry if CSS size doesn't match drawing buffer size (scaling artifacts)?
- [ ] Is the empty `GameState` object for the board preview type-safe? What happens if `Board` component tries to access nested properties that don't exist?
- [ ] Does `HvHLobbyPage` have hardcoded Galaxy navigation paths (e.g., `/galaxy/play/human/room/`) that would break in kiosk context?

### Architecture

- [ ] Is creating a fake `GameState` object the right approach for board preview, or should there be a dedicated `BoardPreview` component?
- [ ] Should the tsumego data fetching be moved to a custom hook for reusability?
- [ ] Is reusing Galaxy's `HvHLobbyPage` directly the right call, or should there be a kiosk-specific version to avoid coupling?

### Performance

- [ ] The tsumego fix makes N+1 API calls (1 for categories + N for each category's problems). Is this acceptable on a slow SBC network connection? Should there be a single backend endpoint instead?
- [ ] Does the `Board` component in preview mode trigger unnecessary analysis/WebSocket connections?

### Touchscreen Considerations

- [ ] The canvas fix addresses mouse events. Do touch events (`onTouchStart`, `onTouchEnd`) use the same coordinate conversion? Are they handled at all?
- [ ] Are click targets large enough for finger interaction (48px minimum)?
- [ ] Does the lobby page account for on-screen keyboard taking up screen space?

## Key Files for Reference

```
katrain/web/ui/src/components/Board.tsx          # Shared board canvas component
katrain/web/ui/src/kiosk/KioskApp.tsx            # Kiosk router
katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx   # AI game setup
katrain/web/ui/src/kiosk/pages/GamePage.tsx       # Active game page
katrain/web/ui/src/kiosk/pages/TsumegoLevelPage.tsx  # Tsumego level problems
katrain/web/ui/src/kiosk/pages/PlayPage.tsx       # Play mode selection
katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx  # Galaxy online lobby (reference)
katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx   # Galaxy AI setup (reference)
katrain/web/ui/src/api.ts                         # API client + GameState type
katrain/web/api/v1/endpoints/tsumego.py           # Backend tsumego API
katrain/web/server.py                             # FastAPI server + SPA routing
```

## Expected Output

For each task, provide:

1. **Agreement or disagreement** with the diagnosis
2. **Concerns or risks** with the proposed fix
3. **Alternative approaches** if you see a better way
4. **Missing considerations** the plan doesn't address

End with an overall assessment: **Approve**, **Approve with changes**, or **Reject with reasons**.
