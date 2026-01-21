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
