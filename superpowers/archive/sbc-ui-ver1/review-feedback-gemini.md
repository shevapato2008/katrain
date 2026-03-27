# Review Feedback: RK3588 Kiosk UI Plan

**Reviewer:** Gemini Agent
**Date:** 2026-02-17
**Status:** Approved with Modifications

---

## 1. Architecture & Code Organization

### Parallel Directory Structure (`kiosk/` vs `galaxy/`)
**Verdict:** **Acceptable for Phase 1, but risky.**
*   **Pros:** Allows rapid iteration on the kiosk UI without regression risks to the stable Galaxy web UI. Keeps the "throwaway" mock code isolated.
*   **Cons:** High risk of logic drift. If Phase 3 (Shared Layer Extraction) is delayed, you will end up maintaining two separate `Board` components, two game state hooks, etc.
*   **Recommendation:** Strictly time-box Phase 1. Do not start adding complex business logic (like real game rules or WebSocket handling) until the shared layer is established. If you find yourself copying `useGameSession.ts` to `kiosk/hooks/`, stop and refactor to `shared/` immediately.

### AppRouter & Theme Switching
**Verdict:** **Needs Improvement.**
*   **Issue:** `const isKiosk = window.location.pathname.startsWith('/kiosk')` in `AppRouter` is fragile. It runs once on mount. If a user navigates from `/galaxy` to `/kiosk` (unlikely in kiosk mode, but possible during dev), the theme won't update without a full reload.
*   **Recommendation:** Nest the `ThemeProvider` *inside* the route wrappers.
    ```tsx
    // GalaxyApp.tsx
    export default () => (
      <ThemeProvider theme={zenTheme}>
        <GalaxyRoutes />
      </ThemeProvider>
    );

    // KioskApp.tsx
    export default () => (
      <ThemeProvider theme={kioskTheme}>
        <KioskRoutes />
      </ThemeProvider>
    );
    ```
    This makes the theme part of the component tree, not a top-level global switch.

### Single Vite Build
**Verdict:** **Approved.**
*   Code splitting via `React.lazy` is recommended for the top-level apps (`GalaxyApp` and `KioskApp`). This ensures the kiosk bundle doesn't load heavy Galaxy-specific dependencies (like complex charts) and vice versa.

---

## 2. UX & Visual Design

### 8-Tab Bottom Navigation
**Verdict:** **Critical Concern.**
*   **Issue:** 8 tabs on a 7-inch width (landscape) is extremely crowded.
    *   Assuming 1024px width: ~128px per tab. Doable.
    *   Assuming 800px width: ~100px per tab. Tight.
    *   **The real issue:** Visual overload. 8 cognitive choices is too many for a "glanceable" kiosk interface.
*   **Recommendation:** Group secondary items.
    *   **Primary (Visible):** Play (AI/PvP/Online), Learn (Tsumego/Kifu), Live.
    *   **Secondary (Overflow "More" tab):** Research, Platforms, Settings.
    *   Alternatively, use a **Left Vertical Rail** (Navigation Rail). Landscape screens have more width than height. A 64-80px wide vertical rail saves precious vertical space for the board and fits better with the "Left Board + Right Panel" layout pattern.

### Vertical Space (Chrome vs Content)
**Verdict:** **Concern.**
*   **Math:** 40px (Status) + 64px (Nav) = 104px.
*   **Screen:** On a 1024x600 screen, you have 496px height left.
*   **Impact:** A square Go board needs height. 496px height means the board is max 496x496. On a 7" screen, that's small.
*   **Recommendation:**
    1.  **Vertical Nav Rail:** Saves 64px vertical space. Board can be ~560px height.
    2.  **Immersive Mode:** Auto-hide status bar or merge it into the top of the right panel.

### Virtual Keyboard
**Verdict:** **Missing Requirement.**
*   **Issue:** Kiosk = no keyboard. How does a user enter a Player Name, search for a Kifu, or search for a Tsumego?
*   **Recommendation:** You need an on-screen keyboard solution (OS level or React component). Design your forms (inputs) to trigger this.

---

## 3. Implementation Details

### Mock Data Management
**Verdict:** **Minor Improvement.**
*   Inline mocks in components (`GamePage.tsx` Task 10) are fine for "hello world", but quickly become unmaintainable clutter.
*   **Recommendation:** Create `src/kiosk/data/mocks.ts` and import from there. It keeps the component code clean and readable.

### Component Granularity (`GameControlPanel`)
**Verdict:** **Approved.**
*   Starting with one file is fine. Split it when it exceeds ~150 lines or when you need to reuse parts (e.g., "PlayerInfo" might be reused in the Lobby).

### Routing Logic (`startsWith`)
**Verdict:** **Correction Needed.**
*   **Issue:** `location.pathname.startsWith(t.path)` can match false positives (e.g., `/kiosk/art` matches `/kiosk/ai` if not careful).
*   **Recommendation:** Use `matchPath` from `react-router-dom`:
    ```typescript
    import { matchPath } from 'react-router-dom';
    // ...
    const isActive = !!matchPath(`${tab.path}/*`, location.pathname);
    ```

---

## 4. Hardware & Performance (RK3588)

### Chromium & Animations
**Verdict:** **Approved.**
*   RK3588 is powerful (Mali-G610 MP4 GPU). CSS transforms will be buttery smooth.
*   **Note:** Ensure `will-change: transform` is used sparingly and only when needed to avoid excessive memory use.

### WebSockets vs Polling
**Verdict:** **Approved.**
*   WebSockets are mandatory for real-time sensor feedback (stone placement). Polling would feel laggy and disconnected.

---

## 5. Summary of Action Items

1.  **Refactor AppRouter:** Move `ThemeProvider` inside `GalaxyApp`/`KioskApp`.
2.  **Reconsider Navigation:** seriously evaluate a **Vertical Navigation Rail** for landscape optimization.
3.  **Add Virtual Keyboard:** Add a task to investigate/implement text input handling.
4.  **Mock Data:** Move mocks to a separate file/folder.
5.  **Fix Routing Match:** Use `matchPath` instead of string `startsWith`.

The plan is otherwise solid and follows good TDD practices. Proceed with Phase 1.
