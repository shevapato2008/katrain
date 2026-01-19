# Track Specification: Session-Isolated Settings Alignment (Revised)

## Overview
Achieve strict feature parity with the Kivy GUI for Timer and Teaching settings. Key focus is on **Session Isolation** and **Timer Snapshotting**: timer settings are locked at the start of a game and mid-game changes only apply to future games.

## Functional Requirements

### 1. Timer Settings (F5) - Snapshot Mechanism
- **Initial Setup**: When a session starts, it loads defaults from `~/.katrain/config.json`.
- **Game Locking (Snapshot)**: At the moment a new game is started (`_do_new_game`), the current timer settings must be "snapshotted" into the active game state.
- **Mid-Game Immutability**: Changes made in the "Timer Settings (F5)" dialog during an active game will update the session's configuration but **must not** affect the current game's timer logic. 
- **Persistence**: These updates apply to the next game in the same session but are **not** written back to the global `config.json` file.

### 2. Teaching/Analysis Settings (F6) - Parity & Isolation
- **Feature Parity**: Full alignment with Kivy GUI controls:
    - 6-level Evaluation Thresholds.
    - "Save Feedback" and "Save Marks" per-level arrays.
    - "Show Dots" and analysis visibility per-level arrays.
    - AI logic: "Lock AI" and "Eval show AI".
- **Session-Scoped**: Changes apply immediately to the current view but are isolated to the specific browser session (memory-only).

## Technical Requirements
- **Data Source Redirection**: `update_timer` must read from the `active_game_timer` snapshot instead of the live session config.
- **Disable Disk Sync**: Intercept `save_config` calls for `timer/` and `trainer/` paths in the web interface to prevent global config pollution.

## Acceptance Criteria
- [ ] Changing Timer settings during a game does not change the countdown clock of the current game.
- [ ] Starting a "New Game" after changing settings correctly applies the new values.
- [ ] Different browser sessions maintain independent settings and independent game timers.
- [ ] SGF generation uses the session's current teaching settings.