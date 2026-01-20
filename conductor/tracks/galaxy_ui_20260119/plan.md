# Implementation Plan: Galaxy Go UI Redesign

This plan covers the end-to-end implementation of the new Galaxy Go style UI for KaTrain Web. It prioritizes the infrastructure first, followed by the core functional modules (Play, Research), and utilizes the `ui-ux-pro-max` skill for design guidance.

## Phase 1: Infrastructure & Design System Setup
*Goal: Establish the new layout structure, routing, and shared design tokens/components.*

- [ ] Task: Project Structure & Routing [checkpoint: p1_done]
    - [ ] Create new directory structure for `katrain/web/ui/src/galaxy` (or refactor root if replacing).
    - [ ] Install/Configure React Router (if not already optimized for new routes).
    - [ ] Define routes: `/`, `/play`, `/research`.
- [ ] Task: UI/UX Design System Definition (using `ui-ux-pro-max`) [checkpoint: p1_done]
    - [ ] Run design system query: `python3 .claude/skills/ui-ux-pro-max/scripts/search.py "Go Board Game Strategy Platform Clean Modern" --design-system -p "Galaxy Go Clone"`.
    - [ ] Define global CSS variables (colors, fonts, spacing) based on Galaxy reference and tool output.
    - [ ] Create shared functional components: `Button`, `Card`, `Modal`, `Tooltip` (matching Galaxy style).
- [ ] Task: Global Layout Implementation [checkpoint: p1_done]
    - [ ] Implement `Sidebar` component (Left nav, collapsible sections).
    - [ ] Implement `MainLayout` shell (Sidebar + Content Area).
    - [ ] Integrate i18n switching logic into the Sidebar.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md) [checkpoint: p1_done]

## Phase 2: Home Page & Authentication
*Goal: Create the entry point and user management interface.*

- [ ] Task: Authentication UI [checkpoint: p2_done]
    - [ ] Implement `LoginForm` and `RegisterForm` components in the sidebar/modal.
    - [ ] Connect auth forms to existing `/api/auth` endpoints.
    - [ ] Implement "User Profile" state in Sidebar (post-login view).
- [ ] Task: Home Page Dashboard [checkpoint: p2_done]
    - [ ] Create `Dashboard` component.
    - [ ] Implement "Module Cards" (Play, Research, Report, Live) using provided assets.
    - [ ] Add interaction: Play/Research buttons navigate; others disabled.
    - [ ] Load and display introductory text from `docs/galaxy_module_intro/*.txt`.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md) [checkpoint: p2_done]

## Phase 3: Play Module - Human vs AI (Core Feature)
*Goal: A fully functional AI game interface with a new setup flow.*

- [ ] Task: Play Module Auth Guard [checkpoint: p3_guard_done]
    - [ ] Implement `AuthGuard` or similar logic to detect login status.
    - [ ] Create `LoginReminder` component matching `@.gemini-clipboard/login_reminder.png`.
    - [ ] Display reminder if user attempts to access Play without being logged in.
- [ ] Task: AI Setup Page
    - [ ] Create `AiSetupPage` component.
    - [ ] Fetch AI constants from `/api/ai-constants`.
    - [ ] Build configuration form (Strategy, Rank, Handicap, Time).
    - [ ] Implement "Start Game" action connecting to `/api/new-game`.
- [ ] Task: Game Board Refactoring (Visuals)
    - [ ] Refactor existing `Board` component to support "Galaxy Theme" (styling/assets).
    - [ ] Ensure responsiveness and high-resolution rendering.
- [ ] Task: Game Controls Integration
    - [ ] Implement "Galaxy Style" control panel (Pass, Resign, Undo).
    - [ ] Connect controls to existing game session API.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: Play Module - Human vs Human (Mocked)
*Goal: A visual prototype of the multi-player lobby.*

- [ ] Task: Mock Services
    - [ ] Create `mock/lobbyService.ts` to simulate player lists and matching.
- [ ] Task: Lobby UI
    - [ ] Create `LobbyPage` component.
    - [ ] Implement "Player List" table/grid.
    - [ ] Implement "Quick Match" button with searching animation.
- [ ] Task: Game Room Mock
    - [ ] Create `MultiPlayerGamePage` (reusing Board component).
    - [ ] Add "Opponent Info" panel (mocked avatar/rank).
- [ ] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)

## Phase 5: Research Module & Analysis Tools
*Goal: A professional analysis workbench matching Galaxy's tabular style.*

- [ ] Task: Research Layout
    - [ ] Create `ResearchPage` layout (Board + Analysis Panels).
- [ ] Task: Analysis Panel Redesign
    - [ ] Implement "Move Suggestions" table (Winrate, Score, Visits) - matching Galaxy's tabular look.
    - [ ] Redesign "Winrate Graph" to fit the new layout.
- [ ] Task: SGF Editor Integration
    - [ ] Style the SGF node tree/navigation.
    - [ ] Ensure "Load SGF" and "Save SGF" flows work within the new UI.
- [ ] Task: Conductor - User Manual Verification 'Phase 5' (Protocol in workflow.md)

## Phase 6: Localization & Polish
*Goal: Ensure all content is translated and the UI is refined.*

- [ ] Task: Localization
    - [ ] Use `katrain-i18n-expert` or equivalent logic to ensure all Go terminology is accurately translated in the UI.
    - [ ] Verify flags and language switching.
- [ ] Task: Final Polish
    - [ ] Review all mocked states and transitions.
    - [ ] Optimize responsiveness.
- [ ] Task: Conductor - User Manual Verification 'Phase 6' (Protocol in workflow.md)
