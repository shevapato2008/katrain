# Implementation Plan - Galaxy-Style Live Game Module

## Phase 1: Foundation & Data Sources
Goal: Establish the module structure, implement the Poller/Cache architecture, and connect to XingZhen/CWQL APIs.

- [ ] Task: Scaffold "Live Game" Module Structure
    - [ ] Create `katrain/core/live/` package.
    - [ ] Create `katrain/core/live/models.py` (LiveMatch, MoveAnalysis).
    - [ ] Create `katrain/core/live/cache.py` (Thread-safe storage).
    - [ ] Write tests for data model initialization.
- [ ] Task: Implement Data Source Clients
    - [ ] Create `katrain/core/live/clients/xingzhen.py` (19x19 API).
    - [ ] Create `katrain/core/live/clients/cwql.py` (Weiqi.org API).
    - [ ] **TDD:** Write tests mocking the specific JSON responses from the design doc to verify parsing.
- [ ] Task: Implement LivePoller
    - [ ] Create `katrain/core/live/poller.py` (Background thread management).
    - [ ] Implement start/stop logic and interval handling.
    - [ ] **TDD:** Test that the poller updates the cache at expected intervals.

## Phase 2: Game Lobby UI
Goal: Build the UI to list and select games.

- [ ] Task: Build Game Lobby UI
    - [ ] Create `katrain/gui/live_lobby.py`.
    - [ ] Implement `LiveGameList` widget (ScrollView + Cards).
    - [ ] Design "Game Card" widget (Player names, Tournament, Status).
    - [ ] Integrate "Live" button into the main Navigation.
    - [ ] **TDD:** Test that clicking a card triggers a `load_live_game` event.

## Phase 3: Live Board & Local Analysis
Goal: Enable the board to play moves automatically and run local analysis.

- [ ] Task: Connect Live Data to Board
    - [ ] Create `katrain/core/live_controller.py` to bridge Cache and Game Engine.
    - [ ] Implement logic to "sync" the board with the latest SGF/Moves from the cache.
    - [ ] Update `katrain/core/game.py` to support "Live Mode" (read-only, auto-forward).
- [ ] Task: Integrate Local KataGo Analysis
    - [ ] Ensure KataGo analyzes the new tip of the game tree automatically.
    - [ ] Verify graphs update in real-time.

## Phase 4: Sidebar, Commentary & Schedule
Goal: Implement the Tabbed Sidebar and "Atmosphere" features.

- [ ] Task: Implement Tabbed Sidebar
    - [ ] Refactor Right Sidebar to support Tabs.
    - [ ] Create `CommentaryPanel` (Tab 1) and connect to `LiveMatch.comments`.
    - [ ] Create `SchedulePanel` (Tab 2) and connect to `LivePoller.upcoming`.
- [ ] Task: Implement Live Control Buttons
    - [ ] Implement "Try", "Territory", "Moves", "No Hint" toggles.
    - [ ] Ensure "Try" pauses live updates and creates a local branch.

## Phase 5: Polish & Advanced Features
Goal: Add "Good/Bad Move" alerts and Hover Variations.

- [ ] Task: Implement Move Evaluation Alerts
    - [ ] Add logic to check delta score/winrate against config thresholds.
    - [ ] Visual indicators for Brilliant/Mistake moves.
- [ ] Task: Implement Hover Variations (PV)
    - [ ] Port `draw_pv` logic to the Live Board context.
    - [ ] Ensure ghost stones appear on hover.
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Polish & Advanced Features' (Protocol in workflow.md)
