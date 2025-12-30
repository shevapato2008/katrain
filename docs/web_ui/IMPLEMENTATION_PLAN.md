# KaTrain WebUI - Implementation Plan

## 1. Architecture Overview

The system will follow a classic Client-Server architecture.

*   **Server (Backend):**
    *   **Language:** Python 3.9+
    *   **Framework:** FastAPI (High performance, async support, easy WebSocket integration).
    *   **Responsibility:**
        *   Host the `katrain.core` logic.
        *   Manage user sessions and Game instances.
        *   Interface with `KataGoEngine`.
        *   Serve the frontend static files (production).
*   **Client (Frontend):**
    *   **Language:** TypeScript
    *   **Framework:** React
    *   **Styling:** Material UI (MUI) or Tailwind CSS.
    *   **Board Rendering:** HTML5 Canvas (via a wrapper like `react-konva` or a custom implementation for performance).
    *   **Responsibility:**
        *   Render the game state.
        *   Handle user input.
        *   Display analysis data.

## 2. Backend Implementation Strategy

### 2.1. Decoupling Core from UI
*   **Task:** Create a `WebKaTrain` class.
*   **Details:**
    *   Inherit from `KaTrainBase` or wrap it.
    *   Mock or remove Kivy dependencies (`kivy.Config`, `kivy.storage.JsonStore` if it relies on app dirs that don't exist in server context).
    *   Ensure `log` functions redirect to standard Python logging or stdout.
    *   Ensure `update_state` callbacks trigger WebSocket broadcasts instead of GUI updates.

### 2.2. Session Management
*   **Task:** Implement a Session Manager.
*   **Details:**
    *   Use a unique Session ID (UUID) for each connected client.
    *   Store `WebKaTrain` instances in a dictionary: `sessions: Dict[str, WebKaTrain]`.
    *   Implement cleanup logic for inactive sessions to free up memory/engine resources.

### 2.3. API Design
*   **REST Endpoints:**
    *   `POST /api/session`: Create a new session.
    *   `GET /api/state`: Get full game state (SGF, current node, config).
    *   `POST /api/move`: Play a move `{coords: [x, y]}`.
    *   `POST /api/undo`: Undo last move.
    *   `POST /api/redo`: Redo move.
    *   `POST /api/nav/{node_id}`: Jump to specific node.
    *   `POST /api/new-game`: Start a new game with settings.
    *   `POST /api/config`: Update config sections (engine, trainer, timer, theme, ai, game).
    *   `POST /api/sgf/load`: Load SGF/NGF/GIB into the session.
    *   `POST /api/sgf/save`: Export SGF from the current session.
    *   `POST /api/analysis/toggle`: Toggle continuous analysis.
    *   `POST /api/contribute/start`: Start contribution mode.
    *   `POST /api/contribute/stop`: Stop contribution mode.
    *   `GET /api/logs`: Stream or fetch recent log/status messages.
*   **WebSockets (`/ws/{session_id}`):**
*   **Client -> Server:**
    *   Requests for analysis (`analyze_node`).
    *   UI state updates (panel visibility, overlay toggles, graph view).
*   **Server -> Client:**
    *   `game_update`: Full or partial state update (e.g., after a move).
    *   `analysis_update`: Streaming JSON from KataGo (winrate, policy, ownership).
    *   `log_update`: Engine and system log updates.

### 2.4. Entry Point Refactoring
*   **Task:** Update `katrain.py` / `__main__.py`.
*   **Details:**
    *   Implement command-line argument parsing to select the interface mode (e.g., `--ui desktop` (default) vs `--ui web`).
    *   If `web` is selected, initialize `WebKaTrain` and start the FastAPI server (Uvicorn).
    *   If `desktop` is selected, proceed with the existing Kivy application startup.

## 3. Frontend Implementation Strategy

### 3.1. Project Setup
*   Initialize a standard React project (Vite is recommended for speed).
*   Setup TypeScript, ESLint, Prettier.
*   Configure static asset bundling so the FastAPI server can serve the built WebUI.

### 3.2. Board Component (`<Goban />`)
*   **Tech:** `Canvas` API is preferred over DOM elements for performance with many overlays (heatmaps).
*   **Layers:**
    1.  **Background:** Board texture/color, Grid lines, Star points.
    2.  **Stones:** Black/White stones, Ghost stones.
    3.  **Decorations:** Coordinates.
    4.  **Overlays:** Last move marker, Territory heatmap, Move hints (circles with text).
*   **Interactions:** Handle `onClick` and `onMouseMove` (for ghost stones/hover).

### 3.3. State Management
*   Use React Context or a lightweight store (Zustand/Jotai) to manage the Game State received from the server.
*   The WebSocket connection should feed directly into this store.

### 3.4. Kivy Parity UI Components
*   **Top Bar/Toolbar:** Match layout and actions from Kivy.
*   **Left/Right Panels:** Move list, analysis, settings, and stats.
*   **Graph Panel:** Winrate/score graph with Kivy-like styling.
*   **Settings Dialogs:** Recreate teacher, timer, AI, engine, and general settings with the same defaults.
*   **Status and Logs:** Match Kivy status messages, analysis indicators, and error banners.

### 3.5. Localization and Assets
*   Reuse KaTrain fonts, icons, and board textures.
*   Map i18n keys to WebUI labels to keep translations aligned.

## 4. Development Milestones

### Phase 1: Core Backend & API
1.  Setup FastAPI project structure.
2.  Implement `WebKaTrain` wrapper to initialize `KaTrainBase` without Kivy.
3.  Create session management.
4.  Implement basic REST API for Play/Undo.
5.  **Deliverable:** A backend that can play a game internally and return state via API.

### Phase 2: Basic Frontend & Play
1.  Setup React project.
2.  Implement basic `<Goban />` component (Grid + Stones).
3.  Connect Frontend to Backend API.
4.  Implement Play, Undo, Redo buttons.
5.  **Deliverable:** A web page where you can play moves and see them appear.

### Phase 3: Analysis Integration
1.  Implement WebSocket handler in Backend.
2.  Hook up `KataGoEngine` callbacks to push data to WebSocket.
3.  Frontend: Implement overlays for `<Goban />` (Hints, Territory).
4.  Frontend: Display Analysis Info panel (Winrate graph/text).
5.  **Deliverable:** Full analysis features available in the WebUI.

### Phase 4: Polish & Advanced Features
1.  Settings UI (AI strength, Board size).
2.  SGF Upload/Download.
3.  Responsiveness (Mobile layout).
4.  Performance tuning (Engine pooling if needed).

### Phase 5: Feature Parity (Kivy)
1.  Trainer and teacher prompts, thresholds, and feedback saving.
2.  Analysis toggles (policy/ownership/hints) and continuous analysis controls.
3.  Graph panel parity (score/winrate toggles and styling).
4.  Game tree and variation navigation (branch, prune, add, delete).
5.  Timer and sound settings with parity to Kivy.
6.  Theme selection and UI state persistence.
7.  Contribute mode dashboard and controls.

### Phase 6: QA, Parity Audit, and Release
1.  Create a parity checklist covering all Kivy controls and workflows.
2.  Add regression tests for API and state updates.
3.  Manual QA across browsers and platforms.
4.  Package static assets and document deployment.

Reference: `docs/web_ui/PARITY_CHECKLIST.md`.
