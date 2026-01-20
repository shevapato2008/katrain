# Implementation Plan - Web UI Top Moves Parity

## Phase 1: Configuration & State Management
- [x] Task: Backend Configuration Update
    - [x] Add `max_top_moves_on_board` to `katrain/config.json` with default value `3`.
    - [x] Verify `top_moves_show` default settings align with requirements (Loss & Visits).
- [x] Task: Frontend State & API
    - [x] Update `GameState` interface in `katrain/web/ui/src/api.ts` to include the new setting.
    - [x] Update `TeachingSettingsDialog.tsx` to include a number input/slider for `max_top_moves_on_board`.
    - [x] Ensure the new setting is persisted/synced via existing API endpoints (update `api.ts` if needed).
- [x] Task: Conductor - User Manual Verification 'Configuration & State Management' (Protocol in workflow.md)

## Phase 2: Board Rendering Logic
- [x] Task: Update Board Component (`Board.tsx`) - Filtering
    - [x] Modify `renderBoard` function to access `max_top_moves_on_board` from settings.
    - [x] Implement filtering logic to only process/render the top N moves from `gameState.analysis.moves`.
- [x] Task: Update Board Component (`Board.tsx`) - Rendering
    - [x] Update loop for rendering hints to draw `Score Loss` (top) and `Visits` (bottom) on the stone.
    - [x] Adjust font sizes and positioning for legibility of two lines of text.
    - [x] Ensure the "Top Move" indicator (circle/texture) is applied correctly to the #1 move (index 0).
    - [x] Ensure colors (Score Loss based) are consistent for all displayed moves.
- [x] Task: Conductor - User Manual Verification 'Board Rendering Logic' (Protocol in workflow.md)

## Phase 3: Validation & Polish
- [ ] Task: User Acceptance Testing
    - [ ] Verify only 3 (or N) moves are shown.
    - [ ] Verify stats are correct (Loss/Visits) and legible.
    - [ ] Verify configuring the limit in settings updates the board immediately.
    - [ ] Check against Kivy UI screenshot for visual parity.
- [ ] Task: Conductor - User Manual Verification 'Validation & Polish' (Protocol in workflow.md)
