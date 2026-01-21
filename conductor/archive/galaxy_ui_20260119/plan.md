# Implementation Plan: Galaxy Go UI Redesign

This plan covers the end-to-end implementation of the new Galaxy Go style UI for KaTrain Web.

## Phase 1: Infrastructure & Design System Setup
*Goal: Establish layout, routing, and design tokens.*

- [x] Task: Project Structure & Routing [checkpoint: p1_structure]
    - [x] Create directory structure.
    - [x] Install React Router v6.
    - [x] Configure `AppRouter.tsx` for `/galaxy/*` and `/`.
- [x] Task: Theme Extraction [checkpoint: p1_theme]
    - [x] Extract MUI theme to `src/theme.ts`.
- [x] Task: Global Layout Implementation [checkpoint: p1_layout]
    - [x] Implement `GalaxySidebar` and `MainLayout`.

## Phase 1.5: Data Layer (PostgreSQL)
*Goal: Setup database for persistent user data.*

- [x] Task: Database Setup [checkpoint: p1_db_setup]
    - [x] Verify `docker-compose.db.yml` functionality.
    - [x] Create init scripts for tables: `users`, `games`, `relationships`.
- [x] Task: Backend API - User Data [checkpoint: p1_db_api] 747d659
    - [x] Implement/Update endpoints for User Profile (Credits, Rank).
    - [x] Implement endpoints for Cloud SGF (CRUD).

## Phase 2: Home Page & Authentication
*Goal: Entry point, User Management, and Credits display.*

- [x] Task: Auth Infrastructure [checkpoint: p2_auth] 4a8b6b2
    - [x] `AuthContext` + `AuthGuard`.
    - [x] Connect to backend User Profile API (fetch Credits/Rank).
- [x] Task: Sidebar Integration [checkpoint: p2_sidebar] 38e6428
    - [x] Display User Credits and Rank in Sidebar (Mocked UI).
- [x] Task: Home Page [checkpoint: p2_dashboard]
    - [x] Dashboard with Module Cards.

## Phase 3: Research Module & Cloud Library
*Goal: Analysis workbench with Cloud SGF support.*

- [x] Task: Research Page [checkpoint: p3_page]
    - [x] Protected by `AuthGuard`.
    - [x] Layout with Board + Analysis Panels.
- [x] Task: Cloud SGF Integration [checkpoint: p3_cloud_sgf] 681814f
    - [x] "My Games" side panel fetching from DB.
    - [x] "Save to Cloud" functionality.
- [x] Task: Conductor - User Manual Verification [checkpoint: 64b83a4]

## Phase 4: Play Module - Rated vs Free (REVISED v4)
*Goal: Feature parity with KaTrain desktop and professional UI details.*

- [x] Task: Backend Ranking System [checkpoint: p4_backend]
- [x] Task: AI Setup & Initialization Fixes [checkpoint: p4_setup]
    - [x] Add Ruleset selection to `AiSetupPage`.
    - [x] Fix Handicap initialization (Backend stone placement).
    - [x] Implement Rank Labeling utility (mapping internal values to 20k-9d).
- [x] Task: Galaxy Game UI & Timer Redesign [checkpoint: p4_game_ui]
    - [x] Redesign `PlayerCard` to show Main Time, Byoyomi, and Periods.
    - [x] Fix AI rank display using mapping utility.
    - [x] Integrate `ScoreGraph` and Items in sidebar.
- [x] Task: Bug Fixes & Polish [checkpoint: p4_bugfixes]
    - [x] Fix slow "Start Game" by removing blocking AI move call (AI moves now handled via WebSocket).
    - [x] Fix Komi slider to allow 0.25 increments (was 1.0).
    - [x] Display Ruleset and Komi in game page sidebar (`RightSidebarPanel`).
    - [x] Fix AI Strategy dropdown display (remove "ai:" prefix).
    - [x] Load AI strategy-specific default settings when opponent changes.
    - [x] Fix player name display in `PlayerCard` (add `name` field to `UpdatePlayerRequest`).


## Phase 5: Play Module - Human vs Human & Social [checkpoint: caffd87]
*Goal: Functional multiplayer lobby and game rooms with social integration.*

- [x] Task: Social Integration (Friends & Follows) [checkpoint: p5_social] bb487fe
    - [x] Implement `FriendsPanel` in the right sidebar (fetching from `relationships` table). 34361b4
    - [x] Add "Follow/Unfollow" buttons to User Profiles and Player Cards. 34361b4
    - [x] Backend: Create endpoints for following/unfollowing and fetching followers/following lists.
    - [x] **[FIXED: Optional Auth for Profile Retrieval]** 31cb74b
- [x] Task: Multiplayer Lobby (HvH) [checkpoint: p5_lobby] 587cb91
    - [x] Implement `HvHLobbyPage` showing:
        - [x] Online players list (prioritize following). **[FIXED: Route ordering issue]**
        - [x] Active games list with "Watch" button (for Spectator Mode).
        - [x] "Quick Match" entry for Free/Rated modes.
        - [x] Integrate FriendsPanel. 34361b4
    - [x] Backend: WebSocket state for tracking online users and their statuses.
- [x] Task: Matchmaking & Room Management [checkpoint: p5_matchmaking] cf71df5
    - [x] Implement matchmaking queue UI (Overlay with "Finding opponent..." animation and timer).
    - [x] Enforce "AI Rating" prerequisite check before allowing Rated HvH matches. 34361b4
    - [x] Implement `GameRoomPage` for active HvH matches:
        - [x] Real-time timer synchronization via WebSocket.
        - [x] Turn-based move validation and resignation logic.
- [x] Task: Spectator Mode & WebSocket Broadcast [checkpoint: p5_spectator] 39d317e
    - [x] Implement "Spectator View" for `GamePage` (Read-only board, live move updates).
    - [x] Display "Spectator Count" and live chat area in the game sidebar. 34361b4
    - [x] Backend: WebSocket broadcasting logic for room-specific events (moves, chat, end-game). 34361b4

## Phase 6: Polish [checkpoint: p6_complete] 62b9b6d
*Goal: I18n and UX.*

- [x] Task: Localization & Polish. 
    - [x] **[FIXED: KataGo Engine HTTP 500 Buffer Issue]** 2026-01-21
    - [x] **[FIX: User ID Mismatch]** Fix mismatch between authenticated User UUID and KataGo Engine User ID. 6d3b7e4
    - [x] **[FIX: Invite Button]** Enabled direct invitations in lobby. 62b9b6d
    - [x] **[FIX: Friends Panel]** Improved layout visibility on large screens. 62b9b6d
    - [x] **[FIX: Matchmaking Hang]** Optimized user fetching and added debug logging. 62b9b6d
    - [x] **[FIXED: User Model Mismatch]** Resolved HTTP 500 error by adding `net_wins` and `elo_points` to `UserRepository._to_dict`.
    - [x] **UI Refinements (User Feedback):**
        - [x] Remove Chat functionality and UI (avoid conflicts).
        - [x] Add "Exit" button for Spectators in Game Room.
        - [x] Add "Exit" button for PvAI (require resignation first).
        - [x] Ensure "Resign" button is available in all modes.
        - [x] Fix Rank display in Lobby (show "No Rank" instead of "20k" for new users).

## Phase 7: Internationalization (i18n) & Global Settings [checkpoint: p7_complete]
*Goal: Implement comprehensive multi-language support (11 languages) and persistent user preferences.*

- [x] Task: Language Settings Integration
    - [x] Update `GalaxySidebar` to include a "Settings" menu with a language selection dropdown.
    - [x] Support 11 languages: English (en), Chinese (cn), Traditional Chinese (tw), Japanese (jp), Korean (ko), German (de), Spanish (es), French (fr), Russian (ru), Turkish (tr), and Ukrainian (ua).
    - [x] Implement language switching logic: sync with backend config (`general/language`) and update frontend `i18n` context.
    - [x] Set default language to Chinese (`cn`) for new sessions.
- [x] Task: Galaxy UI String Audit & Translation
    - [x] **[CRITICAL] Define Professional Go Glossary**:
        - [x] Create a mapping of key Go/AI terms (Winrate, Score Lead, Policy, Ownership, Handicap, Komi, Rated Game, etc.) across 11 languages to ensure professional terminology.
        - [x] Reference established Go servers (Fox, Tygem, OGS) for Korean, Japanese, and English terms.
    - [x] Identify and extract all hardcoded strings from Galaxy modules (`katrain/web/ui/src/galaxy/`):
        - [x] Dashboard / Home Page.
        - [x] Play Menu (Free/Rated).
        - [x] AI Setup Page.
        - [x] Game Page (PvAI).
        - [x] Lobby Page (HvH).
        - [x] Game Room Page.
        - [x] Research Page.
    - [x] Update `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` with new keys following the `katrain-i18n-expert` standard.
    - [x] Run `python i18n.py` to synchronize and compile translations for all 11 languages.
    - [x] **AI-Assisted Professional Translation**:
        - [x] Use AI to generate translations for the 10 non-English languages using the Professional Glossary as a hard constraint.
        - [x] Populate all `.po` files with professional translations (prioritizing `cn`, `tw`, `jp`).
    - [x] Replace hardcoded strings in components with `i18n.t` from custom `i18n` class.

---
**Status: 100% Complete**
*Final Track Review: All core modules (Home, Play, Research) implemented with Galaxy Go styling. Backend PostgreSQL layer integrated for persistence. Social features (Friends/Lobby) fully functional. Professional internationalization for 11 languages completed.*


