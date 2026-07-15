# SBC Kiosk Report Parity Design

**Date:** 2026-07-15

**Status:** Confirmed

## Objective

Add a complete Report module to the 1024×600 kiosk client. Its functional behavior must match the current Galaxy Report module, while its layout, typography, touch targets, dialogs, and overflow behavior follow existing kiosk patterns for a seven-inch landscape display.

The kiosk remains a thin client. It reuses the existing Report API, user-game database, server-side `katrain-cron` jobs, and server-side KataGo analysis. This work must not install, configure, start, or otherwise depend on `katrain-cron` on the SBC.

## Confirmed Product Decisions

- Replicate all current Galaxy Report capabilities, not a reduced MVP.
- Add `/kiosk/report` and `/kiosk/report/:taskId`.
- Replace Settings in the eight-item bottom Dock with Report.
- Keep `/kiosk/settings`, but expose it from the top header/user area instead of the Dock.
- Do not add physical-board recognition, LED guidance, or board synchronization to Report.
- Support SGF board sizes already supported by the shared board and parser, including 9×9, 13×13, and 19×19.
- Use Simplified Chinese by default and retain the existing translation mechanism.
- Minimum critical touch target is 48×48 CSS pixels.
- A 1024×600 viewport must not clip critical content or actions.

## Functional Parity

### Report list

The kiosk list page provides the same behaviors as Galaxy:

- list the signed-in user's games;
- search by player, title, or event;
- paginate results;
- select a game and preview its SGF on a board;
- navigate through the preview with the shared playback control;
- import a local SGF;
- import a game from the server kifu library;
- import without analysis, or immediately request normal/deep analysis;
- request normal or deep reports for an existing game;
- show optimistic queued state immediately after creation;
- display pending, running, completed, and failed states;
- show analyzed-move progress;
- poll active tasks every two seconds;
- open completed reports;
- retry failed reports;
- delete a game after confirmation and surface server rejection.

### Report detail

The kiosk detail page provides the same review tools as Galaxy:

- board playback and first/previous/play/next/last navigation;
- current move, total moves, report type, status, players, result, rules, komi, win rate, and score lead;
- AI recommendations and principal-variation preview;
- win-rate and score-lead trend chart with touch navigation;
- territory/ownership overlay where data exists;
- move-number toggle;
- AI-marker toggle;
- try-move mode and clear action;
- progressive display while the report is pending or running;
- two-second polling until the task leaves an active state;
- retryable error states instead of blank screens;
- “在研究中打开”, navigating to `/kiosk/research?user_game_id=<id>`.

While a running task gains analyzed moves, the page follows the newest analyzed move only if the user is already at the previous analysis frontier. If the user moved back to inspect history, polling must not force the selection forward.

## Information Architecture and Layout

### Navigation

The Dock remains eight equal-width items. Report takes the old Settings position and uses `/kiosk/report`. The Settings page remains routable, and a 48×48 settings/account control in the header opens `/kiosk/settings`. `/kiosk/report` is a first-level page with Header and Dock. `/kiosk/report/:taskId` is immersive and owns its back navigation, like the live-analysis page.

### First-level page: `/kiosk/report`

Use the established kiosk list-and-preview composition:

- left: the same shared `LiveBoard` and `PlaybackBar` pattern used by the kiosk live/game views;
- right: title, queue summary, search, scrollable report cards, pagination, and import/create actions;
- cards: match Kifu/Live card density, colors, radii, selection state, result presentation, truncation, and touch/live scenes.
- Selected game loads its SGF and initializes at the final move.
- Changing cards changes the preview.
- Playback uses the shared kiosk `PlaybackBar` with the same slider, previous/next, first/last, and autoplay interaction.
- Loading, empty, malformed-SGF, and network states are visible and never produce a blank panel.

### Right list

- Cards follow kiosk kifu/live card density, border, selection, player, result, date, and move-count conventions.
- Header includes title, queue counts, touch-sized import action, and search.
- Search and page are reflected in query parameters.
- Cards expose all Galaxy Report states and actions:
  - no report: normal/deep generation;
  - pending/running: type, analyzed/total moves, and progress;
  - completed: open normal/deep report;
  - failed: retry;
  - delete: confirmation before deleting the user game.
- Creating a report inserts an optimistic pending state immediately and reconciles it with the server response.
- Poll report list and queue summary every two seconds only while an active task exists.

### Import dialogs

Both import flows are touch-first, near-full-screen dialogs constrained inside 1024×600:

- Local SGF: choose file or paste SGF, optional title, parsed metadata, import only, import + normal, import + deep.
- Kifu library: search, paginate, select a record, import only, import + normal, import + deep.
- Content scrolls independently; action buttons remain fixed and visible.
- All important targets are at least 48 CSS pixels in both dimensions.

## 6. Level-two page: `/kiosk/report/:taskId`

The detail page follows the kiosk `LiveMatchPage` analysis layout:

- Immersive 1024×600 split view.
- Full-height square board on the left, matching the game interface.
- A `min-width: 0` right panel with fixed header/actions and bounded scrolling so no critical action is clipped.
- Back bar contains an ellipsized game title, report status/type, and **在研究中打开**.
- Compact report metadata shows players, result, source, rules, komi, current win rate/lead, and analysis progress.
- Persistent touch labels replace hover-only discovery.
- AI recommendations can be tapped to preview a PV on the board.
- Trend chart is clickable to jump to a move.
- Try moves, territory, move numbers, and AI markers match the live-analysis interaction model.
- Playback stays fixed at the bottom of the right panel.

The board supports SGF board sizes 9, 13, and 19. Report review has no physical-board synchronization requirement and must not inherit a physical 19×19-only restriction.

### Progressive reports

Pending and running reports can be opened. The page loads the task, available move rows, and user game, then polls every two seconds until terminal state.

When new analyzed moves arrive:

- If the user was following the previous analysis frontier, advance to the new frontier.
- If the user moved to a historical position, keep that selection.
- Clamp only when necessary to remain within available moves.
- Stop polling on completed or failed state.

### Research handoff

**在研究中打开** navigates to:

`/kiosk/research?user_game_id=<id>`

The report remains unchanged. If navigation or required data fails, show feedback and stay on the Report page.

## 7. Error and accessibility behavior

- Default UI language is Simplified Chinese and all new strings use the existing translation hook with fallbacks.
- Minimum touch target: 48×48 CSS pixels.
- Loading, empty, authentication, not-found, permission, malformed/missing SGF, network, delete-rejection, and analysis-failure states have explicit recovery paths.
- Destructive deletion requires confirmation.
- Titles and metadata use `min-width: 0`, ellipsis, or deliberate wrapping; action areas never shrink below their touch size.
- No critical content may extend beyond a 1024×600 viewport.

## 8. Verification and acceptance

- Pure unit tests cover task derivation, optimistic reconciliation, polling decisions, move mapping, and frontier-preserving cursor behavior.
- React tests cover routing, Dock/Header navigation, list actions, both import dialogs, progress polling, retry/delete, progressive detail loading, all analysis toggles, research handoff, and error states.
- Existing Galaxy Report tests continue to pass after shared-layer extraction.
- Backend Report API/analyzer tests run as regression coverage; no backend behavior change is expected.
- Playwright exercises the two kiosk routes and import dialogs at exactly 1024×600 and asserts that key actions fit inside the viewport.
- Run lint, Vitest, production build, kiosk 2D build, and the kiosk bundle-boundary verifier.
- Manually verify on the 7-inch SBC: touch targets, no clipping, normal/deep creation, server cron progress, completed detail review, and Settings access from the header.
- Inspect SBC deployment artifacts to confirm no `katrain-cron` service or local KataGo Report worker was added.

