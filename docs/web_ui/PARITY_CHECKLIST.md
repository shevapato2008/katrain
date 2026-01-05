# KaTrain WebUI Parity Checklist

Use this checklist to track WebUI parity with the Kivy desktop app. Check items only when the WebUI behaves the same as the desktop UI.

Priority legend:
- P0: Core functionality needed for daily use (play, analyze, navigation, baseline settings).
- P1: Advanced workflows and polish needed for full parity.
- P2: Specialized or less frequently used features, still required for parity.

## 1) App Modes and Session Behavior
- [x] (P0) Start in web mode via config and CLI without breaking desktop mode.
- [x] (P0) Per-session game state and config isolation.
- [x] (P1) Persist ui_state (play/analyze panel state, toggles, and layout defaults).
- [x] (P0) Status and error messaging matches desktop behavior.
- [x] (P1) Multi-session support with cleanup and engine lifecycle management.

## 2) Navigation and Board Interaction
- [x] (P0) Click/tap to place stones with correct coordinate mapping.
- [x] (P0) Pass button behavior matches desktop.
- [x] (P0) Resign button behavior matches desktop.
- [x] (P0) Navigation: jump to start/end, step +/-1, step +/-10.
- [x] (P1) Previous/next mistake navigation.
- [x] (P1) Rotate board.
- [x] (P1) Toggle move numbers.
- [x] (P1) Toggle coordinates.
- [x] (P1) Zen mode toggle.
- [x] (P1) Clipboard copy/paste SGF.
- [x] (P1) Move tree selection and branch switching.
- [x] (P1) Move tree context actions: delete node, prune branch, make main branch, collapse/expand shortcuts.
- [x] (P1) Insert move mode.
- [x] (P1) Setup position and self-play setup.
- [x] (P0) Display last move marker and move number.
- [x] (P0) Board coordinates, star points, and overlay rendering.
- [x] (P1) Keyboard shortcuts for navigation and analysis actions.

## 3) Play/Analyze/Contribute Modes
- [x] (P0) Play/Analyze toggle with saved UI state per mode.
- [x] (P0) AI vs human selection with player setup controls.
- [x] (P1) Teaching mode behaviors (undo prompts, hints).
- [x] (P1) Show PV from comments interaction.
- [ ] (P2) Contribute mode dashboard, start/stop, and status output.

## 4) Analysis Controls and Actions
- [x] (P0) Analysis toggles: show children, eval dots, hints, policy, ownership.
- [x] (P0) Continuous analysis toggle.
- [x] (P1) Analysis menu actions: extra, equalize, sweep, alternatives, region, reset.
- [x] (P1) Insert mode, play to end, analyze whole game.
- [x] (P2) Game report popup and tsumego frame popup.
- [x] (P0) AI move action.
- [x] (P0) Top moves list with visits, score loss, and policy.
- [x] (P0) PV display and ownership/policy overlays.
- [ ] (P1) Engine status indicator and query count display.

## 5) Panels and Widgets
- [x] (P0) Graph panel with score/winrate toggles and click navigation.
- [x] (P0) Stats panel with score/winrate/points toggles.
- [x] (P0) Notes panel with info/info-details/notes toggles.
- [x] (P0) Timer panel and play clock behavior.
- [ ] (P1) Move tree panel in analyze mode.
- [x] (P0) Player info cards with captures, names, ranks, and AI strategy.

## 6) Hamburger Menu Parity
- [x] (P0) Player setup block (swap players, type, subtype, name).
- [x] (P0) New game / edit game.
- [ ] (P0) Save, Save As, Load SGF.
- [x] (P0) Timer settings.
- [x] (P0) Teacher settings.
- [x] (P0) AI settings.
- [x] (P0) General settings.
- [ ] (P2) Contribute settings.
- [x] (P1) Language switcher.
- [ ] (P1) Manual and support links.

## 7) Settings Popups and Flows
- [x] (P0) General config popup (paths, debug level, load options).
- [x] (P0) Engine config popup (katago, backend, model, visits/time).
- [x] (P0) AI config popup (strategy options, estimated rank).
- [x] (P0) Teacher/trainer config popup (thresholds, prompts, dots, theme).
- [x] (P0) Timer config popup (main time, byo-yomi, sound).
- [x] (P0) New game and edit game popups (rules, komi, handicap).
- [ ] (P2) Contribute popup (credentials, settings, save path).
- [ ] (P1) Engine recovery popup.
- [x] (P1) Re-analyze game popup.

## 8) File I/O and SGF
- [x] (P0) Load SGF/NGF/GIB with file browser and last-directory memory.
- [x] (P0) Save and Save As SGF to disk.
- [ ] (P1) Export trainer feedback and analysis data parity.

## 9) Theme, Assets, and Audio
- [x] (P1) Theme selection and evaluation color mapping.
- [x] (P0) Board/stone textures match Kivy assets.
- [x] (P0) Font usage consistent with Kivy (including CJK support).
- [x] (P1) Sound effects (stones, capture, countdown, minimum time).
- [x] (P0) Move-quality colors align with Theme.EVAL_COLORS.

## 10) Localization and i18n
- [x] (P1) Use existing i18n keys for labels and tooltips.
- [x] (P1) Language switcher supports all bundled locales.
- [x] (P1) Font fallback for CJK and RTL safety.

## 11) QA and Parity Audit
- [x] (P1) Endpoint coverage for all UI actions.
- [ ] (P1) Regression tests for API and session behavior.
- [ ] (P1) Visual parity review against Kivy screenshots.
- [ ] (P1) Cross-browser testing (Chrome, Firefox, Safari, Edge).

## 12) Kivy UI Reference
For future reference, these are screenshots of the original Kivy-based interface:
- [Main Interface](kivy_ui/kivy_main_interface.png)
- [Sidebar Buttons](kivy_ui/kivy_sidebar_buttons.png)
- [Analysis Dropdown](kivy_ui/kivy_analysis_dropdown.png)

### Kivy-based UI Button Logic List

| Button Name | Location | Function & Logic (Code Related) |
| :--- | :--- | :--- |
| **Pass** | Board Controls (Bottom) | Plays a pass move for the current player. `_do_play(None)` |
| **Previous Mistake** | Board Controls (Bottom) | Undoes moves until the previous AI-identified mistake. `_do_find_mistake('undo')` |
| **Previous-End** | Board Controls (Bottom) | Returns to the game's starting position (root). `_do_undo(9999)` |
| **Previous-5** | Board Controls (Bottom) | Undoes 10 moves. `_do_undo(10)` |
| **Previous** | Board Controls (Bottom) | Undoes the last move. `_do_undo(1)` |
| **Next** | Board Controls (Bottom) | Redoes the next move in the current branch. `_do_redo(1)` |
| **Next-5** | Board Controls (Bottom) | Redoes the next 10 moves. `_do_redo(10)` |
| **Next-End** | Board Controls (Bottom) | Redoes all moves until the end of the current branch. `_do_redo(9999)` |
| **Next-Mistake** | Board Controls (Bottom) | Redoes moves until the next AI-identified mistake. `_do_find_mistake('redo')` |
| **Rotate** | Board Controls (Bottom) | Rotates the board visualization by 90 degrees. `_do_rotate()` |
| **Hamburger Menu** | Top Left | Opens/closes the main navigation drawer. `nav_drawer.set_state("open")` |
| **Show Children** | Analysis Controls (Top) | Toggles display of immediate child moves on the board. `analysis_controls.show_children` |
| **Dots** | Analysis Controls (Top) | Toggles display of evaluation dots on stones. `analysis_controls.eval` |
| **Top Moves (Hints)** | Analysis Controls (Top) | Toggles display of AI's suggested top moves. `analysis_controls.hints` |
| **Policy** | Analysis Controls (Top) | Toggles display of the AI's policy network heatmap. `analysis_controls.policy` |
| **Territory (Ownership)**| Analysis Controls (Top) | Toggles display of the territory ownership heatmap. `analysis_controls.ownership` |
| **Analyze** | Analysis Controls (Top) | Toggles the analysis actions dropdown menu. `root.toggle_dropdown()` |
| **Extra** | Analyze Dropdown | Adds more visits to the current node's analysis. `_do_analyze_extra("extra")` |
| **Equalize** | Analyze Dropdown | Equalizes visits among candidates. `_do_analyze_extra("equalize")` |
| **Sweep** | Analyze Dropdown | Performs a wide search for potential moves. `_do_analyze_extra("sweep")` |
| **Alternatives** | Analyze Dropdown | Searches for moves not currently in the top list. `_do_analyze_extra("alternative")` |
| **Region** | Analyze Dropdown | Activates region-of-interest selection mode. `_do_select_box()` |
| **Reset** | Analyze Dropdown | Clears current analysis for the node and restarts it. `_do_reset_analysis()` |
| **Insert** | Analyze Dropdown | Toggles "Insert Move" mode for branch editing. `_do_insert_mode()` |
| **Play to End** | Analyze Dropdown | AI plays out the game to the end from current position. `_do_selfplay_setup("end")` |
| **Game Analysis** | Analyze Dropdown | Opens popup to analyze the entire game. `open_game_analysis_popup()` |
| **Report** | Analyze Dropdown | Generates and displays a game report. `open_report_popup()` |
| **Tsumego Frame** | Analyze Dropdown | Creates a local Tsumego problem from the current position. `open_tsumego_frame_popup()` |
| **Continuous Analysis** | Analyze Dropdown | Toggles the pondering (background analysis) state. `toggle_continuous_analysis()` |
| **AI Move** | Analyze Dropdown | Forces the AI to generate and play a move immediately. `_do_ai_move()` |
| **Play (Mode)** | Right Panel (Top) | Switches to play mode (hides some analysis info). `select_mode(MODE_PLAY)` |
| **Analysis (Mode)** | Right Panel (Top) | Switches to analysis mode (shows all info). `select_mode(MODE_ANALYZE)` |
| **Undo** | Right Panel (Controls) | In Play mode, undos 1 or 2 moves depending on who is AI. `_do_undo("smart")` |
| **Resign** | Right Panel (Controls) | Resigns the current game. `_do_resign()` |
| **Pause (Timer)** | Right Panel (Controls) | Pauses or resumes the game clock. `timer.paused = not timer.paused` |
| **New Game** | Hamburger Menu | Opens the New Game settings popup. `_do_new_game_popup()` |
| **Save** | Hamburger Menu | Saves the current game to the current SGF file. `_do_save_game()` |
| **Save As** | Hamburger Menu | Opens the Save As popup to save to a new file. `_do_save_game_as_popup()` |
| **Load** | Hamburger Menu | Opens the Load SGF popup. `_do_analyze_sgf_popup()` |
| **Clock Settings** | Hamburger Menu | Opens the Clock Settings configuration popup. `_do_timer_popup()` |
| **Teacher Settings** | Hamburger Menu | Opens the Teacher/Trainer configuration popup. `_do_teacher_popup()` |
| **AI Settings** | Hamburger Menu | Opens AI strategy settings popup. `_do_ai_popup()` |
| **General Settings** | Hamburger Menu | Opens General app settings popup. `_do_config_popup()` |
| **Distributed Training** | Hamburger Menu | Opens Distributed Training (Contribute) popup. `_do_contribute_popup()` |
