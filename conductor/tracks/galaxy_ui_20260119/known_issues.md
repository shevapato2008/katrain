# Known Issues: Galaxy Go UI Redesign

This document tracks bugs and functional gaps discovered during the implementation of the Galaxy Go UI.

## Phase 5: Multiplayer & Social

### 1. Online Players list always shows 0
- **Status:** ✅ Fixed (2026-01-21)
- **Discovered:** 2026-01-21
- **Description:** Even when multiple users are logged in and in the lobby, the "Online Players" list remains empty.
- **Root Cause:** Two issues were found:
  1. **Route ordering conflict:** The `/ws/{session_id}` WebSocket endpoint was defined before `/ws/lobby`, causing `/ws/lobby` requests to be routed to the session endpoint with `session_id="lobby"`. This resulted in a KeyError and HTTP 403 rejection.
  2. **WebSocket close without accept:** When closing a WebSocket connection due to auth failure, `websocket.close()` was called without first calling `websocket.accept()`, which causes FastAPI/Starlette to return HTTP 403 instead of a proper WebSocket close frame.
- **Fix:**
  1. Moved `/ws/lobby` endpoint definition before `/ws/{session_id}` to ensure proper routing.
  2. Added `await websocket.accept()` before `await websocket.close()` in error paths.
- **Files Changed:**
  - `katrain/web/server.py`: Reordered WebSocket routes and fixed close handling

### 2. KataGo Engine Response Buffer Limit (HTTP 500)
- **Status:** ✅ Fixed (2026-01-21)
- **Discovered:** 2026-01-21
- **Description:** When playing with full analysis (ownership/heatmaps) via the HTTP backend, the engine would crash with an `HTTP 500` error or "Read timed out".
- **Root Cause:** The `realtime_api` server (KataGo wrapper) used Python's default `asyncio` buffer limit of 64KB. Analysis responses containing detailed ownership data for multiple candidate moves exceeded this limit, causing the server to fail while reading the KataGo output.
- **Fix:** Patched `KataGo/python/realtime_api/katago_wrapper.py` to increase the `stdout` buffer limit to 200KB. Reverted temporary client-side restrictions in KaTrain to restore full feature parity.
- **Files Changed:**
  - `../KataGo/python/realtime_api/katago_wrapper.py`: Increased buffer limit.
  - `katrain/core/engine.py`: Reverted workarounds and fixed indentation.

### 3. Invite Button in Lobby is Unfunctional
- **Status:** ⏳ Pending
- **Discovered:** 2026-01-21
- **Description:** Clicking the "Invite" button next to an online player in the lobby does nothing.
- **Root Cause:** The button in `HvHLobbyPage.tsx` is currently a UI placeholder. There is no `onClick` handler defined, and the backend WebSocket logic does not yet support direct 1-on-1 game invitations (challenges).
- **Fix:** Requires implementing an `invite_user` WebSocket message type, a notification system for the recipient, and logic to create a private room upon acceptance.

### 4. Friends Panel Layout Visibility
- **Status:** ⏳ Pending
- **Discovered:** 2026-01-21
- **Description:** The "Friends Panel" is not appearing on the far right of the lobby screen as intended. Only the "Following" list (which might be the same component) is visible in the sidebar, or the layout is collapsing it unexpectedly.
- **Root Cause:** Responsive layout breakpoints might be hiding the panel on smaller screens, or the integration in `HvHLobbyPage` is conditional on screen size (`display: { xs: 'none', lg: 'block' }`).
- **Workaround:** Check if the window width is sufficient (>= 1200px for `lg` breakpoint).

### 5. Custom Game Matchmaking Hangs
- **Status:** ⏳ Pending
- **Discovered:** 2026-01-21
- **Description:** When two unranked players (e.g., "fan" and "fan124") both queue for a "Custom Game" (Free Mode), the matchmaking dialog ("Finding Opponent...") remains open indefinitely, and they are never matched.
- **Root Cause:** Likely an issue in the `Matchmaker` logic in `session.py`. It may be enforcing strict rank matching even for "Free" games, or failing to match players with `None` or `?` ranks.
- **Fix:** Debug `Matchmaker.add_to_queue` logic to ensure "Free" games have relaxed matching criteria.
