# Kiosk UI Alignment Plan — SBC v2 (Revised)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 critical kiosk UI issues to bring the SBC kiosk experience to parity with the Galaxy web UI.

**Affected UI:** Kiosk frontend (`katrain/web/ui/src/kiosk/`), shared components (`Board.tsx`, `TsumegoBoard.tsx`, `LiveBoard.tsx`, `boardUtils.ts`)

**Screen targets:** SBC displays — 5" (800x480), 7" (1024x600), 10" (1280x800), landscape primary

**Revision notes:** Incorporates Codex review feedback (all items). Key changes: diagnostic-first approach for Task 1, pointer events consideration for Task 1, `LiveBoard` for Task 3, kiosk wrapper for Task 4, auth/token handling for Task 4, partial failure handling for Task 2, explicit test plan with named test files.

---

## Task 0: Pre-Flight Diagnostic (On-Device)

**Purpose:** Establish root cause for stone placement offset before coding any fix.

**Run on RK3562 via SSH**, in a kiosk game session. Open browser devtools console (or inject via a temporary `window.__debug` function) and log:

```javascript
// In Board.tsx handleCanvasClick, temporarily add:
const canvas = canvasRef.current;
const rect = canvas.getBoundingClientRect();
console.log({
  canvasWidth: canvas.width,
  canvasHeight: canvas.height,
  cssWidth: rect.width,
  cssHeight: rect.height,
  devicePixelRatio: window.devicePixelRatio,
  visualViewportScale: window.visualViewport?.scale,
  innerWidth: window.innerWidth,
  innerHeight: window.innerHeight,
  rotation: document.querySelector('[data-rotation]')?.dataset.rotation ?? 'none',
});
```

**Decision tree:**
- If `canvasWidth !== cssWidth` → CSS sizing mismatch (proceed with canvas CSS fix)
- If `devicePixelRatio !== 1` → need DPR-aware coordinate scaling
- If rotation is `90`/`270` → `RotationWrapper.tsx` transforms are distorting `getBoundingClientRect()`
- If all match → problem is in `boardLayout()` math or container constraints

**Also check:** Does the offset occur with touch taps, mouse clicks, or both?

---

## Task 1: Fix Stone Placement Offset (Board Canvas Sizing)

**Priority:** Critical — makes the game unplayable on kiosk

**Problem:** Stones appear at the upper-left of the clicked intersection instead of at the center.

**Most likely root cause:** Canvas drawing buffer size (`canvas.width`) does not match CSS rendered size (`rect.width`). The canvas `style` prop (Board.tsx:587) has no `width`/`height`, so the browser renders it at intrinsic pixel size then the flex container stretches it.

**Additional factors to verify:**
- `canvasSize` is capped by `window.innerHeight - 100` (Board.tsx:85). On 600px-tall kiosk screen, this may produce a drawing buffer smaller than the board container.
- `RotationWrapper.tsx` applies CSS transforms for rotated displays — `getBoundingClientRect()` returns transformed geometry which may distort coordinates.
- `TsumegoBoard.tsx:346` uses the same sizing/click pattern and needs the same fix.

**Files:**
- Modify: `katrain/web/ui/src/components/Board.tsx` (canvas style + canvasSize logic)
- Modify: `katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx` (same pattern)

**Step 1: Fix canvas CSS sizing**

At Board.tsx ~line 587, add CSS dimensions matching `LiveBoard.tsx`'s approach:
```tsx
style={{
  maxWidth: '100%',
  maxHeight: '100%',
  display: 'block',
  borderRadius: '4px',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 80px rgba(212, 165, 116, 0.05)',
  cursor: 'pointer'
}}
```

Use `maxWidth`/`maxHeight` instead of `width: 100%`/`height: 100%` to avoid forcing the canvas larger than its drawing buffer (which would cause blur).

**Step 2: Review canvasSize calculation**

At Board.tsx ~line 85, the `Math.min(width, height, window.innerHeight - 100)` clamp may be too aggressive for kiosk layouts. Evaluate whether the `-100` offset is needed in kiosk context where there's no browser chrome.

**Step 3: Apply same fix to TsumegoBoard.tsx**

Check TsumegoBoard.tsx canvas style and coordinate conversion. Apply consistent sizing approach.

**Step 4: Consider pointer events for touch reliability**

The current click handlers use `React.MouseEvent` only (Board.tsx:498, 530). On touchscreen kiosks, synthesized click events may behave differently. If on-device testing reveals touch-specific issues, migrate `onMouseMove`/`onClick`/`onMouseLeave` to `onPointerMove`/`onPointerUp`/`onPointerLeave` for unified mouse+touch handling.

**Step 5: On-device verification**

Test on RK3562 at rotation 0:
- Click corners, center, edges — stones must appear at exact intersection
- Touch tap — same behavior as mouse click
- Galaxy web UI on desktop — no regression

---

## Task 2: Fix Tsumego 404 After Selecting Difficulty Level

**Priority:** High — entire tsumego module is broken in kiosk

**Root Cause:** `TsumegoLevelPage.tsx:25` calls `GET /api/v1/tsumego/levels/${levelId}?per_page=50` — this endpoint does not exist.

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoLevelPage.tsx`

**Step 1: Rewrite data fetching using existing API endpoints**

```typescript
useEffect(() => {
  const controller = new AbortController();

  const fetchProblems = async () => {
    try {
      // Get categories for this level
      const catRes = await fetch(
        `/api/v1/tsumego/levels/${levelId}/categories`,
        { signal: controller.signal }
      );
      if (!catRes.ok) throw new Error(`HTTP ${catRes.status}`);
      const categories = await catRes.json();

      if (categories.length === 0) {
        setProblems([]);
        setLoading(false);
        return;
      }

      // Fetch problems for each category in parallel, with explicit high limit
      const allProblems: Problem[] = [];
      await Promise.all(categories.map(async (cat: any) => {
        const probRes = await fetch(
          `/api/v1/tsumego/levels/${levelId}/categories/${cat.category}?limit=1000`,
          { signal: controller.signal }
        );
        if (probRes.ok) {
          const data = await probRes.json();
          // Tag problems with their category for potential grouping
          const problems = Array.isArray(data) ? data : data.problems ?? [];
          allProblems.push(...problems.map((p: any) => ({ ...p, category: cat.category })));
        }
      }));

      setProblems(allProblems);
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  fetchProblems();
  return () => controller.abort();
}, [levelId]);
```

**Step 2: Handle partial failure and empty/offline state**

If some category fetches succeed and others fail, show the successfully loaded problems and log warnings for failed categories (do not block the whole page on a single category failure).

Add UI for:
- Empty result: "该难度暂无题目" (No problems for this level)
- Board mode offline: "离线模式暂不支持死活题" (Tsumego unavailable offline)
- API error: show error message with retry button

**Step 3: Update test file**

`katrain/web/ui/src/kiosk/__tests__/TsumegoLevelPage.test.tsx` mocks the old single-endpoint response shape (`{ problems: [...], total, page, per_page }`). Rewrite to mock the new two-step flow:
- Mock `GET /api/v1/tsumego/levels/${levelId}/categories` → returns category list
- Mock `GET /api/v1/tsumego/levels/${levelId}/categories/${cat}?limit=1000` → returns problems per category
- Add test case for partial category failure (one category 200, another 500)
- Add test case for empty categories response

**Verification:**
- Go to 死活题 → select 15K → problems list loads
- Click a problem → TsumegoProblemPage loads and is interactive
- Test with remote server disconnected → shows offline message

---

## Task 3: Replace AiSetupPage Board Preview Placeholder

**Priority:** Medium — cosmetic but affects first impression

**Root Cause:** `AiSetupPage.tsx:69-81` renders a `<Box bgcolor="#8b7355">` placeholder.

**Approach:** Use `LiveBoard` component (already used in kiosk's `ResearchPage.tsx:67` and `KifuPage.tsx:245`). This renders wood texture, grid, stars, and coordinates without requiring a fake GameState.

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`

**Step 1: Replace placeholder with LiveBoard**

```tsx
import LiveBoard from '../../components/live/LiveBoard';

// Replace the placeholder Box (lines 69-81) with:
<Box sx={{ aspectRatio: '1', height: '100%', flexShrink: 0, overflow: 'hidden' }}>
  <LiveBoard
    moves={[]}
    currentMove={0}
    boardSize={boardSize}
    showCoordinates={true}
  />
</Box>
```

**Step 2: Verify LiveBoard props**

Read `LiveBoard.tsx` to confirm exact prop interface. Confirmed props: `moves`, `currentMove`, `boardSize`, `showCoordinates`, `onIntersectionClick` (optional). Do NOT pass `onIntersectionClick` to ensure the preview is non-interactive.

**Step 3: Update test file**

`katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx` currently tests the placeholder box. Add/update test to verify that a canvas element (from LiveBoard) renders inside the board preview area. Example assertion:
```typescript
it('renders board preview canvas', () => {
  renderPage();
  const canvas = document.querySelector('canvas');
  expect(canvas).toBeInTheDocument();
});
```

**Verification:**
- Go to 自由对弈 setup page
- Left side shows real board with wood texture, grid lines, star points, coordinates
- Switching board size (9/13/19) updates the preview immediately
- Board is non-interactive (no click handlers fire)

---

## Task 4: Wire Online Lobby with Kiosk Wrapper

**Priority:** Medium — feature gap

**Root Cause:** `PlayPage.tsx:37` navigates to `/kiosk/play/pvp/lobby`, but `KioskApp.tsx` has no such route.

**Why not reuse HvHLobbyPage directly:**
- Line 104: hardcoded `/galaxy/play/human/room/${data.session_id}`
- Line 128: hardcoded `/galaxy/play/ai?mode=rated`
- Line 275: hardcoded `/galaxy/play/human/room/${game.session_id}`
- Imports `FriendsPanel` (desktop-oriented, not needed on SBC)
- Layout assumptions don't fit 800x480

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/LobbyPage.tsx` — kiosk wrapper
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx` — add route

**Step 1: Create kiosk LobbyPage**

Create a kiosk-specific lobby page that:
- Reuses the core matchmaking/WebSocket logic from `HvHLobbyPage` (extract shared hooks if possible)
- Uses kiosk navigation paths: `/kiosk/play/pvp/room/${sessionId}`
- Omits `FriendsPanel`
- Uses compact layout for small screens

If extraction is too complex, fork `HvHLobbyPage` into the kiosk version with path replacements.

**Step 2: Add route to KioskApp.tsx**

```tsx
<Route path="play/pvp/lobby" element={<LobbyPage />} />
```

**Step 3: Handle auth/token dependency**

`HvHLobbyPage` uses `useAuth()` to get `token` for:
- REST API calls with `Authorization: Bearer ${token}` header
- WebSocket connection at `/ws/lobby?token=${token}`

The kiosk `LobbyPage` must also use `useAuth()`. Ensure the kiosk auth context provides valid tokens. If the kiosk uses a different auth flow (e.g., device-level login), verify the token is available before attempting lobby connections. Show a user-friendly message if not authenticated.

**Step 4: Audit all navigation paths**

Search the new LobbyPage for any remaining `/galaxy/` references. Replace with `/kiosk/` equivalents.

**Step 5: Update test files**

- Add route test in `katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx`:
  ```typescript
  it('navigates to lobby from play page', async () => {
    renderApp('/kiosk/play/pvp/lobby');
    await waitFor(() => {
      expect(screen.getByText(/在线大厅/)).toBeInTheDocument();
    });
  });
  ```
- Create `katrain/web/ui/src/kiosk/__tests__/LobbyPage.test.tsx` with:
  - Mock WebSocket connection
  - Test online users list renders
  - Test navigation to `/kiosk/play/pvp/room/${sessionId}` on match found
  - Test unauthenticated state shows appropriate message

**Step 6: Responsive layout for SBC screens**

Test at:
- 800x480 (5" display)
- 1024x600 (7" display)
- 1280x800 (10" display)

Ensure no horizontal overflow and touch targets are >= 48px.

**Verification:**
- Click "在线大厅" → lobby page loads
- Online users list displays
- Match creation flow works
- Test at 800px width — no layout overflow

---

## Test Plan

### Frontend test files requiring updates

| Test File | Task | Change Required |
|-----------|------|-----------------|
| `kiosk/__tests__/TsumegoLevelPage.test.tsx` | 2 | Rewrite mock from single-endpoint to two-step categories+problems flow; add partial failure + empty state tests |
| `kiosk/__tests__/AiSetupPage.test.tsx` | 3 | Add assertion that canvas element renders (LiveBoard) |
| `kiosk/__tests__/navigation.integration.test.tsx` | 4 | Add route test for `/kiosk/play/pvp/lobby` |
| `kiosk/__tests__/LobbyPage.test.tsx` (**new**) | 4 | Mock WebSocket, test user list, match flow, auth guard |

### Backend test files (no changes needed)

Existing coverage is sufficient:
- `tests/web_ui/test_tsumego_api.py` — tsumego endpoints
- `tests/web_ui/test_lobby_api.py` — lobby/matchmaking

### Regression testing

After all tasks, run the full frontend test suite to catch shared-component regressions:
```bash
cd katrain/web/ui && npm test
```

---

## Implementation Order

| Order | Task | Effort | Notes |
|-------|------|--------|-------|
| 0 | Pre-flight diagnostic | ~15 min | Run on RK3562, determines Task 1 approach |
| 1 | Canvas sizing fix | ~30 min | Based on diagnostic results |
| 2 | Tsumego API fix | ~30 min | Independent of Task 1 |
| 3 | Board preview (LiveBoard) | ~15 min | Simple component swap |
| 4 | Online lobby wrapper | ~45 min | Most complex, fork + adapt |

## On-Device Verification Checklist

After all tasks, test on RK3562 in Chromium kiosk mode:

- [ ] Stone placement accurate via touch tap at corners, center, edges (rotation 0)
- [ ] AiSetupPage shows real board, updates with board size selector
- [ ] Tsumego 15K loads problems list
- [ ] Tsumego problem page is interactive (place stones, get feedback)
- [ ] Online lobby page loads from "在线大厅"
- [ ] All above work at 1024x600 resolution
- [ ] No regression in Galaxy web UI on desktop browser (MacBook)
- [ ] No regression in TsumegoBoard click handling
