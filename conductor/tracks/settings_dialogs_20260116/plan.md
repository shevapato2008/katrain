# Implementation Plan: Time and Teaching Settings Dialogs

## Phase 1: Session-Scoped State Management
- [x] Task: Define TypeScript interfaces for Time and Teaching settings. 298417e
- [x] Task: Create a custom hook `useSessionSettings` to manage `sessionStorage` sync and state updates. 4452617
    - [x] Write tests for the hook (verify isolation, persistence on reload).
    - [x] Implement the hook using `sessionStorage`.
- [x] Task: Conductor - User Manual Verification 'Phase 1: State Management' (Protocol in workflow.md) [checkpoint: ddcf273]

## Phase 2: Time Settings Dialog (F5)
- [x] Task: Create the `TimeSettingsDialog.tsx` component using MUI.
    - [x] Write unit tests for component rendering and user input changes.
    - [x] Implement the dialog layout and logic using `useSessionSettings`.
- [x] Task: Add i18n keys for Time Settings in translation files.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Time Settings' (Protocol in workflow.md)

## Phase 3: Teaching/Analysis Settings Dialog (F6)
- [ ] Task: Create the `TeachingSettingsDialog.tsx` component using MUI.
    - [ ] Write unit tests for rendering and complex input handling (sliders, multiple checkboxes).
    - [ ] Implement the dialog layout and logic using `useSessionSettings`.
- [ ] Task: Add i18n keys for Teaching/Analysis Settings in translation files.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Teaching Settings' (Protocol in workflow.md)

## Phase 4: UI Integration and Shortcuts
- [ ] Task: Enable "Time Settings" and "Teaching/Analysis Settings" buttons in `Sidebar.tsx`.
- [ ] Task: Implement F5/F6 keyboard shortcuts in `App.tsx` or the keyboard shortcuts hook.
- [ ] Task: Integrate the new dialogs into the main `App.tsx` component.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Integration' (Protocol in workflow.md)
