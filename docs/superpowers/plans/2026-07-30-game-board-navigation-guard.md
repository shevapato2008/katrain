# Game Board Navigation Guard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent occupied-stone taps from rewinding live games and prevent any caller from navigating an unfinished native Galaxy multiplayer session.

**Architecture:** Centralize occupied-intersection decisions in a small pure helper shared by the 2D and 3D boards, while live-play pages stop opting into stone navigation. Add a persistent `WebSession.game_ended` lifecycle latch and a focused `/api/nav` guard that excludes platform-backed sessions, blocks active native multiplayer sessions, and requires authentication after game end.

**Tech Stack:** React 19, TypeScript, Vitest, FastAPI, Pydantic, pytest/httpx.

---

## Chunk 1: Frontend board interaction and live-page wiring

### Task 1: Define one occupied-intersection decision contract

**Files:**
- Create: `katrain/web/ui/src/components/boardInteraction.ts`
- Create: `katrain/web/ui/src/components/boardInteraction.test.ts`
- Modify: `katrain/web/ui/src/components/Board.tsx:625-660`
- Modify: `katrain/web/ui/src/components/Board3D/RaycastClick.tsx:20-43`

- [ ] **Step 1: Write failing pure decision tests**

Cover three cases with a minimal `GameState`: an empty point returns `{ kind: 'move', x, y }`; an occupied point without navigation permission returns `{ kind: 'ignore' }`; an occupied point with navigation permission returns `{ kind: 'navigate', nodeId }`. Also cover an occupied setup stone with no move number returning `ignore`.

- [ ] **Step 2: Run the new test and verify RED**

From `katrain/web/ui`, run: `npm test -- --run src/components/boardInteraction.test.ts`

Expected: FAIL because `resolveBoardIntersectionAction` does not exist.

- [ ] **Step 3: Implement the minimal pure helper**

Export a discriminated union and a function that reads `gameState.stones`/`gameState.history`. The helper must never classify an occupied point as a move:

```ts
export type BoardIntersectionAction =
  | { kind: 'move'; x: number; y: number }
  | { kind: 'navigate'; nodeId: number }
  | { kind: 'ignore' };

export function resolveBoardIntersectionAction(
  gameState: GameState,
  x: number,
  y: number,
  allowNavigation: boolean,
): BoardIntersectionAction;
```

- [ ] **Step 4: Run the helper test and verify GREEN**

From `katrain/web/ui`, run: `npm test -- --run src/components/boardInteraction.test.ts`

Expected: PASS.

- [ ] **Step 5: Use the helper in both board renderers**

In `Board.tsx` and `RaycastClick.tsx`, pass `Boolean(onNavigate)` as the explicit permission. Dispatch `move` to `onMove`, `navigate` to `onNavigate`, and do nothing for `ignore`. Preserve existing game-over, turn, bounds, and coordinate conversion checks.

- [ ] **Step 6: Re-run helper and existing 3D tests**

From `katrain/web/ui`, run: `npm test -- --run src/components/boardInteraction.test.ts src/components/Board3D/index.test.tsx src/components/Board3D/__tests__/constants.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit the shared interaction contract**

```bash
git add katrain/web/ui/src/components/boardInteraction.ts katrain/web/ui/src/components/boardInteraction.test.ts katrain/web/ui/src/components/Board.tsx katrain/web/ui/src/components/Board3D/RaycastClick.tsx
git commit -m "fix: ignore occupied board taps outside review"
```

### Task 2: Remove stone navigation from every live-play surface

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/GamePage.tsx:327-340`
- Modify: `katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx:309-321`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:566-573`
- Modify: `katrain/web/ui/src/ZenModeApp.tsx:475-484`
- Modify: `katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx`
- Create: `katrain/web/ui/src/components/liveBoardWiring.test.ts`

- [ ] **Step 1: Add a failing kiosk live-page wiring test**

Change the existing Board mock to capture its props and assert that the rendered Kiosk live board has no `onNavigate` prop. Add a TypeScript-AST contract test that parses the four live-page source files and asserts that no `Board` or `Board3D` JSX element has an `onNavigate` attribute. Existing Galaxy and Kiosk research pages also omit this prop, so leave them untouched rather than introducing a new interaction. AST inspection is used instead of a loose regex, so multiline JSX and unrelated sidebar callbacks cannot create false results.

- [ ] **Step 2: Run the focused test and verify RED**

From `katrain/web/ui`, run: `npm test -- --run src/kiosk/__tests__/GamePage.test.tsx src/components/liveBoardWiring.test.ts`

Expected: FAIL because Kiosk `GamePage` currently passes `session.onNavigate` to Board.

- [ ] **Step 3: Remove `onNavigate` only from live board components**

Remove the prop from 2D/3D boards in Galaxy AI play and Galaxy multiplayer, from Kiosk live play, and from the legacy Zen live board. Do not remove navigation callbacks from `ScoreGraph`, sidebars, research pages, or review pages.

- [ ] **Step 4: Verify live/review wiring statically and run the focused test**

From `katrain/web/ui`, run: `npm test -- --run src/kiosk/__tests__/GamePage.test.tsx src/components/liveBoardWiring.test.ts`

Expected: both tests PASS; the AST contract proves Galaxy AI, Galaxy multiplayer, Kiosk, and Zen live boards omit the prop.

- [ ] **Step 5: Commit live-page wiring**

```bash
git add katrain/web/ui/src/galaxy/pages/GamePage.tsx katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/ZenModeApp.tsx katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx katrain/web/ui/src/components/liveBoardWiring.test.ts
git commit -m "fix: disable stone navigation during live play"
```

## Chunk 2: Multiplayer lifecycle, authentication, and API guard

### Task 3: Add a persistent session game-end latch

**Files:**
- Modify: `katrain/web/session.py:14-24,130-141`
- Modify: `katrain/web/server.py:740-920,1270-1318`
- Create: `tests/web_ui/test_navigation_guards.py`

- [ ] **Step 1: Write failing lifecycle tests**

Test `SessionManager._on_state` with an injected lightweight session: a state containing `end_result` latches `game_ended=True`; a later non-terminal state does not clear it. Add endpoint-level tests showing `/api/new-game` and `/api/game/setup` reset an already-true marker, and multiplayer count completion latches it.

- [ ] **Step 2: Run lifecycle tests and verify RED**

Run: `python -m pytest tests/web_ui/test_navigation_guards.py -q`

Expected: FAIL because `WebSession.game_ended` and reset/latch behavior do not exist.

- [ ] **Step 3: Implement the lifecycle marker**

Add `game_ended: bool = False` to `WebSession`. In `_on_state`, set it to true when `state.get('end_result')` is truthy and never clear it there. Reset it before starting/reconfiguring a game. Set it during `_complete_count` when the terminal result is created directly.

- [ ] **Step 4: Re-run lifecycle tests and verify GREEN**

Run: `python -m pytest tests/web_ui/test_navigation_guards.py -q`

Expected: lifecycle subset PASS.

### Task 4: Guard native Galaxy multiplayer navigation

**Files:**
- Modify: `katrain/web/server.py:940-948`
- Modify: `tests/web_ui/test_navigation_guards.py`
- Verify: `tests/platforms/test_engine_move_guards.py`

- [ ] **Step 1: Add failing endpoint tests for exact policy and precedence**

Use `ASGITransport` and injected mock sessions. Cover:

- missing session stays `404`;
- pending Golaxy engine session stays `409 engine move pending`;
- non-pending platform session remains `200` even with virtual player IDs;
- active native Galaxy multiplayer returns `409 navigation disabled during active multiplayer game` for anonymous and authenticated requests;
- terminal native multiplayer latches `game_ended`, returns `401 Authentication required for multiplayer navigation` anonymously, and returns `200` when `get_current_user_optional` is overridden with a user;
- a second authenticated navigation after the mocked current state loses `end_result` still returns `200` because the latch persists;
- plain local/research navigation remains `200`.

- [ ] **Step 2: Run endpoint tests and verify RED**

Run: `python -m pytest tests/web_ui/test_navigation_guards.py tests/platforms/test_engine_move_guards.py -q`

Expected: new guard tests FAIL on current permissive behavior; existing engine guard tests PASS.

- [ ] **Step 3: Implement the ordered `/api/nav` guard**

Add `current_user: User = Depends(get_current_user_optional)`. After session lookup and `_guard_engine_move_pending`, classify platform sessions through the gateway. For a native multiplayer session, latch `game_ended` from the current state under `session.lock`; return active-game `409` if false, finished-anonymous `401` if no user, otherwise perform navigation. Do not require the post-game authenticated user to be one of the former players, matching the approved spec.

- [ ] **Step 4: Run endpoint tests and verify GREEN**

Run: `python -m pytest tests/web_ui/test_navigation_guards.py tests/platforms/test_engine_move_guards.py -q`

Expected: all PASS.

- [ ] **Step 5: Commit lifecycle and server guard**

```bash
git add katrain/web/session.py katrain/web/server.py tests/web_ui/test_navigation_guards.py
git commit -m "fix: guard live multiplayer navigation"
```

### Task 5: Propagate authentication for post-game navigation

**Files:**
- Modify: `katrain/web/ui/src/api.ts:267-268`
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts:145-148`
- Modify: `katrain/web/ui/src/ZenModeApp.tsx:329-337`
- Create: `katrain/web/ui/src/hooks/useGameSession.navigation.test.tsx`

- [ ] **Step 1: Write a failing hook/API integration test**

Mock `API.navigate`, render `useGameSession({ token: 'auth-token' })`, set a session ID, invoke `onNavigate`, and assert `API.navigate(sessionId, nodeId, 'auth-token')`. Add a direct API fetch assertion only if the existing API test pattern supports it without duplicating infrastructure.

- [ ] **Step 2: Run the new test and verify RED**

From `katrain/web/ui`, run: `npm test -- --run src/hooks/useGameSession.navigation.test.tsx`

Expected: FAIL because `API.navigate` accepts only session/node arguments and the hook omits the token.

- [ ] **Step 3: Implement optional token propagation**

Extend `API.navigate(sessionId, nodeId, token?)` and pass the token to `apiPost`. Pass `token` from `useGameSession.onNavigate` and add it to the callback dependency list. Pass the legacy Zen app token to its explicit navigation request. Leave `useSessionBase` tokenless for research/local use.

- [ ] **Step 4: Run the hook test and TypeScript build check**

From `katrain/web/ui`, run: `npm test -- --run src/hooks/useGameSession.navigation.test.tsx`

From `katrain/web/ui`, run: `npx tsc -b --pretty false`

Expected: PASS and exit 0.

- [ ] **Step 5: Commit token propagation**

```bash
git add katrain/web/ui/src/api.ts katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/ZenModeApp.tsx katrain/web/ui/src/hooks/useGameSession.navigation.test.tsx
git commit -m "fix: authenticate post-game navigation"
```

## Chunk 3: Verification and handoff

### Task 6: Run focused and broad regression checks

**Files:**
- Verify only; no expected production edits.

- [ ] **Step 1: Run all focused frontend tests**

```bash
cd katrain/web/ui
npm test -- --run \
  src/components/boardInteraction.test.ts \
  src/components/Board3D/index.test.tsx \
  src/components/Board3D/__tests__/constants.test.ts \
  src/components/liveBoardWiring.test.ts \
  src/kiosk/__tests__/GamePage.test.tsx \
  src/hooks/useGameSession.navigation.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run backend navigation and engine-guard tests**

Run: `python -m pytest tests/web_ui/test_navigation_guards.py tests/platforms/test_engine_move_guards.py -q`

Expected: PASS.

- [ ] **Step 3: Run build boundaries**

From `katrain/web/ui` run:

```bash
npm run build
npm run build:kiosk-2d
```

Expected: both exit 0 and kiosk verification reports no forbidden 3D dependency.

- [ ] **Step 4: Inspect the final diff and worktree**

Run: `git diff --check develop...HEAD`, `git status --short`, and `git log --oneline --decorate -8`.

Expected: no whitespace errors; clean worktree; only scoped commits plus the two spec commits.

- [ ] **Step 5: Apply verification-before-completion and request code review**

Use `superpowers:verification-before-completion`, then `superpowers:requesting-code-review`. Address only verified in-scope issues, re-run affected tests, and report the branch/worktree plus the known Node 26 baseline limitation.
