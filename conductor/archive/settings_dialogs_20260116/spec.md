# Track Specification: Time and Teaching Settings Dialogs

## Overview
This track implements two key configuration dialogs in the KaTrain Web UI: "Time Settings" (accessible via F5) and "Teaching/Analysis Settings" (accessible via F6). The goal is to achieve full feature parity with the existing Kivy desktop application, providing users with fine-grained control over game timing and AI analysis behavior directly from the web interface.

**Crucial Requirement:** Settings must be scoped to the individual client session (browser tab/window). Changes made by one user or in one tab must NOT affect other users or other tabs.

## Functional Requirements

### 1. Time Settings Dialog (F5)
*   **Main Time:** Numeric input for base game time in minutes.
*   **Byoyomi Length:** Numeric input for byoyomi period duration in seconds.
*   **Byoyomi Periods:** Numeric input for the number of byoyomi periods.
*   **Minimal time usage:** Numeric input for the minimum time deducted per move.
*   **Sounds Toggle:** Checkbox to enable or disable game audio feedback.
*   **Persistence:** Settings must be stored in `sessionStorage` (or memory) to ensure isolation between tabs/windows.

### 2. Teaching/Analysis Settings Dialog (F6)
*   **Teaching Settings:**
    *   "Show dots" checkboxes for different move quality ranges.
    *   "Save feedback" checkboxes for SGF export configuration.
    *   "Evaluation Thresholds" inputs/sliders to define point-loss categories.
*   **Analysis Settings:**
    *   "Show AI" toggle to enable/disable engine hints.
    *   "Top moves" display mode selection (e.g., show delta score, show visits).
    *   "Visits" configuration for Fast, Low, and Maximum visit counts.
*   **Persistence:** Settings must be stored in `sessionStorage` (or memory) to ensure isolation between tabs/windows.

### 3. Sidebar Integration
*   The "Time Settings" and "Teaching/Analysis Settings" buttons in the right sidebar must be enabled.
*   Clicking these buttons (or pressing the respective F5/F6 keys) must open the corresponding dialog.

### 4. Internationalization (i18n)
*   All labels, placeholders, and tooltips in both dialogs must support multi-language switching using the existing `useTranslation` hook.

## Non-Functional Requirements
*   **UI/UX:** Use Material UI (MUI) components to match the existing design language of the Web UI.
*   **Session Isolation:** Explicitly avoid `localStorage` for these settings to prevent cross-tab interference.
*   **Responsiveness:** Dialogs should be readable and functional on both desktop and mobile screens.
*   **TDD:** Unit tests must be written for the settings logic and component rendering.

## Acceptance Criteria
*   [ ] Both dialogs open correctly from the sidebar and keyboard shortcuts (F5/F6).
*   [ ] Changes to settings in one browser tab DO NOT affect the settings in another open tab.
*   [ ] Settings persist if the specific tab is refreshed (via `sessionStorage`).
*   [ ] All UI text updates correctly when the application language is changed.
*   [ ] Unit tests for the new components achieve >80% coverage.

## Out of Scope
*   Server-side synchronization of these specific settings.
*   Integration with external sound packs (only the internal toggle is required).
