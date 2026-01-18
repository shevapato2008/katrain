# Implementation Plan: Session-Isolated Settings Alignment (Revised)

This plan focuses on implementing a snapshot-based timer system and aligning teaching settings with the Kivy GUI, ensuring session-level isolation and mid-game stability.

## Phase 1: Backend Session Isolation & Timer Snapshotting [checkpoint: 36dd1a7]
- [x] Task: Disable Global Persistence (330f779)
    - [ ] Modify `WebKaTrain.update_config` to skip `self.save_config()` for `timer/` and `trainer/` domains.
- [x] Task: Implement Timer Snapshot Logic (5ab7255)
    - [x] Add `self.active_game_timer` attribute to `WebKaTrain`.
    - [x] Modify `WebKaTrain._do_new_game` to clone `self.config("timer")` into `self.active_game_timer`.
- [x] Task: Refactor Timer Calculation (5ab7255)
    - [x] Update `WebKaTrain.update_timer` to read `main_time`, `byo_length`, and `byo_periods` exclusively from `self.active_game_timer`.
    - [x] Ensure `update_state` correctly broadcasts the snapshotted settings to the frontend.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Snapshot Logic' (Protocol in workflow.md)

## Phase 2: Teaching/Analysis Settings Parity (Frontend)
- [ ] Task: Redesign `TeachingSettingsDialog.tsx`
    - [ ] Implement 6-level threshold inputs (array mapping).
    - [ ] Add checkboxes for "Save Feedback" and "Save Marks" per evaluation level.
    - [ ] Add toggles for "Lock AI" and "Eval show AI".
    - [ ] Align UI visibility toggles with the Kivy GUI array structure.
- [ ] Task: Update Frontend State Management
    - [ ] Ensure the dialog fetches current session state correctly upon opening.
    - [ ] Use `updateConfigBulk` for efficient synchronization.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Frontend Parity' (Protocol in workflow.md)

## Phase 3: Internationalization (i18n)
- [ ] Task: Update PO Files
    - [ ] Add `Update Timer` and `Update Feedback Settings` keys to `katrain/i18n/locales/*.po`.
    - [ ] Ensure all new labels in the Teaching dialog have corresponding translation keys.
- [ ] Task: Verification
    - [ ] Switch language in Web UI and verify all settings text updates correctly.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: i18n' (Protocol in workflow.md)

## Phase 4: Automated Session & Snapshot Testing
- [ ] Task: Create Playwright Test Script (`tests/web_ui/test_settings.spec.ts`)
    - [ ] Script Step: Verify that changing Timer Settings during a game DOES NOT change the current clock.
    - [ ] Script Step: Verify that a New Game starts with the updated settings.
    - [ ] Script Step: Verify Session Isolation between two different browser contexts.
- [ ] Task: Execute Verification using Chrome MCP
    - [ ] Run the test script and capture logs/screenshots to prove isolation and snapshotting.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Testing & Final Sign-off' (Protocol in workflow.md)