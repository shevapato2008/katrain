# Implementation Plan - Life and Death Training Module

## Phase 1: Data Preparation & Backend Core
- [ ] Task: Create `LifeDeath` Data Processing Script
    - [ ] Sub-task: Implement SGF parser to extract `GC` (Game Comment) and filter for "死活题".
    - [ ] Sub-task: Implement Metadata extraction (Level, ID, Correct Rate) to structured JSON.
    - [ ] Sub-task: Create a "Verification" routine (stub for now, can integrate KataGo later if needed for simple SGF matching).
    - [ ] Sub-task: Run script on `data/life-n-death/` to generate `problems_index.json`.
- [ ] Task: Backend API for Tsumego
    - [ ] Sub-task: Create new endpoints in `katrain/core/` (or web server) to serve the `problems_index.json`.
    - [ ] Sub-task: Create endpoint to serve individual SGF content by ID.
    - [ ] Sub-task: Create simple `ProgressManager` class to read/write `user_progress.json`.
    - [ ] Sub-task: Expose "save progress" and "load progress" APIs.
- [ ] Task: Conductor - User Manual Verification 'Data Preparation & Backend Core' (Protocol in workflow.md)

## Phase 2: Frontend - Navigation & Selection
- [ ] Task: Create "Training" Section in Galaxy Web UI
    - [ ] Sub-task: Add "Training" route and button in the main Galaxy navigation.
    - [ ] Sub-task: Create `LevelSelection` component (Bento grid style).
    - [ ] Sub-task: Fetch and display available levels from API.
- [ ] Task: Problem Selection Grid
    - [ ] Sub-task: Create `ProblemList` component.
    - [ ] Sub-task: Display grid of problems for a selected level.
    - [ ] Sub-task: Integrate "Solved" status indicators based on `user_progress.json`.
- [ ] Task: Conductor - User Manual Verification 'Frontend - Navigation & Selection' (Protocol in workflow.md)

## Phase 3: Frontend - Interactive Board & Gameplay
- [ ] Task: Tsumego Board Implementation
    - [ ] Sub-task: Reuse or adapt existing `GalaxyBoard` component for Tsumego mode.
    - [ ] Sub-task: Implement SGF Move Tree navigation logic in JS (Client-side validation).
    - [ ] Sub-task: Handle user clicks: Validate against SGF variations.
- [ ] Task: Gameplay Controls & Feedback
    - [ ] Sub-task: Implement "Success" and "Failure" overlays/animations.
    - [ ] Sub-task: Implement Sidebar controls: Hint, Restart, Next/Prev.
    - [ ] Sub-task: Wire up "Success" event to Backend API to save progress.
- [ ] Task: Conductor - User Manual Verification 'Frontend - Interactive Board & Gameplay' (Protocol in workflow.md)

## Phase 4: Polish & Integration
- [ ] Task: UI Refinement
    - [ ] Sub-task: Style the selection screens to match Galaxy theme (Dark/Light mode).
    - [ ] Sub-task: Ensure responsive layout for sidebar/board.
- [ ] Task: Integration Testing
    - [ ] Sub-task: Verify end-to-end flow: Select Level -> Select Problem -> Solve -> Checkmark appears.
- [ ] Task: Conductor - User Manual Verification 'Polish & Integration' (Protocol in workflow.md)
