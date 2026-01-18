# Implementation Plan: Session-Isolated Settings Alignment (Revised)

This plan focuses on implementing a snapshot-based timer system and aligning teaching settings with the Kivy GUI, ensuring session-level isolation and mid-game stability.

## Phase 1: Backend Snapshotting & Persistence [checkpoint: 36dd1a7]
- [x] Task: Implement Timer Snapshot Logic (5ab7255)
    - [x] Add `self.active_game_timer` attribute to `WebKaTrain`.
    - [x] Modify `WebKaTrain._do_new_game` to clone `self.config("timer")` into `self.active_game_timer`.
- [x] Task: Refactor Timer Calculation (5ab7255)
    - [x] Update `WebKaTrain.update_timer` to read `main_time`, `byo_length`, and `byo_periods` exclusively from `self.active_game_timer`.
    - [x] Ensure `update_state` correctly broadcasts the snapshotted settings to the frontend.
- [x] Task: Enable Persistence with Snapshot Protection (330f779 & subsequent fix)
    - [x] Allow `WebKaTrain.update_config` to call `self.save_config()` to update `~/.katrain/config.json`.
    - [x] Verified that mid-game changes do not affect the current game due to snapshotting.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Snapshot Logic' (Protocol in workflow.md)

## Phase 2: Teaching/Analysis Settings Parity & UI Polish (Frontend) [checkpoint: 394fb58]
- [x] Task: Redesign `TeachingSettingsDialog.tsx` (394fb58)
    - [x] Implement 6-level threshold inputs (array mapping).
    - [x] Add checkboxes for "Save Feedback" and "Save Marks" per evaluation level.
    - [x] Add toggles for "Lock AI" and "Eval show AI".
- [x] Task: Refactor Numeric Inputs to Text Mode (394fb58)
    - [x] Remove up/down arrows (spinners) from all settings inputs.
    - [x] Implement regex-based validation for integers and floats.
    - [x] Remove redundant "minutes/seconds" helper text under input boxes.
- [x] Task: Update Frontend State Management & Sync (394fb58)
    - [x] Update `api.ts` types to match backend `trainer_settings` and `minimal_use` key.
    - [x] Implement `wasOpen` logic in `useEffect` to prevent real-time data push from overwriting user input.
    - [x] Use `updateConfigBulk` for efficient synchronization.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Frontend Parity' (Protocol in workflow.md)

## Phase 3: Internationalization (i18n) [checkpoint: 394fb58]
- [x] Task: Update PO Files & Compile (394fb58)
    - [x] Added `update timer`, `update teacher`, `lock ai`, `save marks`, etc. to `en.po` and `cn.po`.
    - [x] Run `i18n.py` to synchronize keys across all locales and generate `.mo` binaries.
- [x] Task: Verification (394fb58)
    - [x] Switch language in Web UI and verify all buttons ("Update Timer", "Update Feedback Settings") and labels are correctly translated.
- [x] Task: Conductor - User Manual Verification 'Phase 3: i18n' (Protocol in workflow.md)

## Phase 4: Automated Session & Snapshot Testing [checkpoint: 394fb58]
- [x] Task: Create Playwright Test Script (394fb58 - Python pytest used instead for stability)
    - [x] Script Step: Verify that changing Timer Settings during a game DOES NOT change the current clock.
    - [x] Script Step: Verify that a New Game starts with the updated settings.
    - [x] Script Step: Verify Session Isolation (different browser contexts).
- [x] Task: Execute Verification using Chrome MCP (394fb58)
    - [x] Run the test script and capture logs/screenshots to prove isolation and snapshotting.
- [x] Task: Conductor - User Manual Verification 'Phase 4: Testing & Final Sign-off' (Protocol in workflow.md)