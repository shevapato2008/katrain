# KaTrain WebUI Parity Checklist

Use this checklist to track WebUI parity with the Kivy desktop app. Check items only when the WebUI behaves the same as the desktop UI.

Priority legend:
- P0: Core functionality needed for daily use (play, analyze, navigation, baseline settings).
- P1: Advanced workflows and polish needed for full parity.
- P2: Specialized or less frequently used features, still required for parity.

## 1) App Modes and Session Behavior
- [ ] (P0) Start in web mode via config and CLI without breaking desktop mode.
- [ ] (P0) Per-session game state and config isolation.
- [ ] (P1) Persist ui_state (play/analyze panel state, toggles, and layout defaults).
- [ ] (P0) Status and error messaging matches desktop behavior.
- [ ] (P1) Multi-session support with cleanup and engine lifecycle management.

## 2) Navigation and Board Interaction
- [ ] (P0) Click/tap to place stones with correct coordinate mapping.
- [ ] (P0) Pass button behavior matches desktop.
- [ ] (P0) Resign button behavior matches desktop.
- [ ] (P0) Navigation: jump to start/end, step +/-1, step +/-10.
- [ ] (P1) Previous/next mistake navigation.
- [ ] (P1) Rotate board.
- [ ] (P1) Toggle move numbers.
- [ ] (P1) Toggle coordinates.
- [ ] (P1) Zen mode toggle.
- [ ] (P1) Clipboard copy/paste SGF.
- [ ] (P1) Move tree selection and branch switching.
- [ ] (P1) Move tree context actions: delete node, prune branch, make main branch, collapse/expand shortcuts.
- [ ] (P1) Insert move mode.
- [ ] (P1) Setup position and self-play setup.
- [ ] (P0) Display last move marker and move number.
- [ ] (P0) Board coordinates, star points, and overlay rendering.
- [ ] (P1) Keyboard shortcuts for navigation and analysis actions.

## 3) Play/Analyze/Contribute Modes
- [ ] (P0) Play/Analyze toggle with saved UI state per mode.
- [ ] (P0) AI vs human selection with player setup controls.
- [ ] (P1) Teaching mode behaviors (undo prompts, hints).
- [ ] (P1) Show PV from comments interaction.
- [ ] (P2) Contribute mode dashboard, start/stop, and status output.

## 4) Analysis Controls and Actions
- [ ] (P0) Analysis toggles: show children, eval dots, hints, policy, ownership.
- [ ] (P0) Continuous analysis toggle.
- [ ] (P1) Analysis menu actions: extra, equalize, sweep, alternatives, region, reset.
- [ ] (P1) Insert mode, play to end, analyze whole game.
- [ ] (P2) Game report popup and tsumego frame popup.
- [ ] (P0) AI move action.
- [ ] (P0) Top moves list with visits, score loss, and policy.
- [ ] (P0) PV display and ownership/policy overlays.
- [ ] (P1) Engine status indicator and query count display.

## 5) Panels and Widgets
- [ ] (P0) Graph panel with score/winrate toggles and click navigation.
- [ ] (P0) Stats panel with score/winrate/points toggles.
- [ ] (P0) Notes panel with info/info-details/notes toggles.
- [ ] (P0) Timer panel and play clock behavior.
- [ ] (P1) Move tree panel in analyze mode.
- [ ] (P0) Player info cards with captures, names, ranks, and AI strategy.

## 6) Hamburger Menu Parity
- [ ] (P0) Player setup block (swap players, type, subtype, name).
- [ ] (P0) New game / edit game.
- [ ] (P0) Save, Save As, Load SGF.
- [ ] (P0) Timer settings.
- [ ] (P0) Teacher settings.
- [ ] (P0) AI settings.
- [ ] (P0) General settings.
- [ ] (P2) Contribute settings.
- [ ] (P1) Language switcher.
- [ ] (P1) Manual and support links.

## 7) Settings Popups and Flows
- [ ] (P0) General config popup (paths, debug level, load options).
- [ ] (P0) Engine config popup (katago, backend, model, visits/time).
- [ ] (P0) AI config popup (strategy options, estimated rank).
- [ ] (P0) Teacher/trainer config popup (thresholds, prompts, dots, theme).
- [ ] (P0) Timer config popup (main time, byo-yomi, sound).
- [ ] (P0) New game and edit game popups (rules, komi, handicap).
- [ ] (P2) Contribute popup (credentials, settings, save path).
- [ ] (P1) Engine recovery popup.
- [ ] (P1) Re-analyze game popup.

## 8) File I/O and SGF
- [ ] (P0) Load SGF/NGF/GIB with file browser and last-directory memory.
- [ ] (P0) Save and Save As SGF to disk.
- [ ] (P1) Export trainer feedback and analysis data parity.

## 9) Theme, Assets, and Audio
- [ ] (P1) Theme selection and evaluation color mapping.
- [ ] (P0) Board/stone textures match Kivy assets.
- [ ] (P0) Font usage consistent with Kivy (including CJK support).
- [ ] (P1) Sound effects (stones, capture, countdown, minimum time).
- [ ] (P0) Move-quality colors align with Theme.EVAL_COLORS.

## 10) Localization and i18n
- [ ] (P1) Use existing i18n keys for labels and tooltips.
- [ ] (P1) Language switcher supports all bundled locales.
- [ ] (P1) Font fallback for CJK and RTL safety.

## 11) QA and Parity Audit
- [ ] (P1) Endpoint coverage for all UI actions.
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
