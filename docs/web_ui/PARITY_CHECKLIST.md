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
- [ ] (P0) Navigation: jump to start/end, step +/-1, step +/-10.
- [ ] (P1) Previous/next mistake navigation.
- [ ] (P1) Rotate board.
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
