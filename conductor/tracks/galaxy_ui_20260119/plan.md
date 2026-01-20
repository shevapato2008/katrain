# Implementation Plan: Galaxy Go UI Redesign

This plan covers the end-to-end implementation of the new Galaxy Go style UI for KaTrain Web.

## Phase 1: Infrastructure & Design System Setup
*Goal: Establish layout, routing, and design tokens.*

- [ ] Task: Project Structure & Routing [checkpoint: p1_structure]
    - [ ] Create directory structure.
    - [ ] Install React Router v6.
    - [ ] Configure `AppRouter.tsx` for `/galaxy/*` and `/`.
- [ ] Task: Theme Extraction [checkpoint: p1_theme]
    - [ ] Extract MUI theme to `src/theme.ts`.
- [ ] Task: Global Layout Implementation [checkpoint: p1_layout]
    - [ ] Implement `GalaxySidebar` and `MainLayout`.

## Phase 1.5: Data Layer (PostgreSQL)
*Goal: Setup database for persistent user data.*

- [ ] Task: Database Setup [checkpoint: p1_db_setup]
    - [ ] Verify `docker-compose.db.yml` functionality.
    - [ ] Create init scripts for tables: `users`, `games`, `relationships`.
- [ ] Task: Backend API - User Data [checkpoint: p1_db_api]
    - [ ] Implement/Update endpoints for User Profile (Credits, Rank).
    - [ ] Implement endpoints for Cloud SGF (CRUD).

## Phase 2: Home Page & Authentication
*Goal: Entry point, User Management, and Credits display.*

- [ ] Task: Auth Infrastructure [checkpoint: p2_auth]
    - [ ] `AuthContext` + `AuthGuard`.
    - [ ] Connect to backend User Profile API (fetch Credits/Rank).
- [ ] Task: Sidebar Integration [checkpoint: p2_sidebar]
    - [ ] Display User Credits and Rank in Sidebar.
- [ ] Task: Home Page [checkpoint: p2_dashboard]
    - [ ] Dashboard with Module Cards.

## Phase 3: Research Module & Cloud Library
*Goal: Analysis workbench with Cloud SGF support.*

- [ ] Task: Research Page [checkpoint: p3_page]
    - [ ] Protected by `AuthGuard`.
    - [ ] Layout with Board + Analysis Panels.
- [ ] Task: Cloud SGF Integration [checkpoint: p3_cloud_sgf]
    - [ ] "My Games" side panel fetching from DB.
    - [ ] "Save to Cloud" functionality.
- [ ] Task: Conductor - User Manual Verification

## Phase 4: Play Module - Rated vs Free
*Goal: AI Game interface with specific Rating logic.*

- [ ] Task: Play Menu [checkpoint: p4_menu]
    - [ ] UI to select "Free" vs "Rated" game.
- [ ] Task: AI Setup & Rating Logic [checkpoint: p4_setup]
    - [ ] **Rated Mode:** Enforce "Human-like AI" model. Implement "3-game placement" logic if unranked.
    - [ ] **Free Mode:** Allow full AI configuration.
- [ ] Task: Game Loop [checkpoint: p4_game]
    - [ ] Human vs AI implementation.
    - [ ] Unlimited "Items" (Analysis tools) available in UI.

## Phase 5: Play Module - Human vs Human & Social
*Goal: Multiplayer prototype backed by DB.*

- [ ] Task: Lobby & Social [checkpoint: p5_lobby]
    - [ ] Lobby UI showing Online Players.
    - [ ] "Friends List" side panel (fetching from `relationships` table).
- [ ] Task: Matchmaking & Room [checkpoint: p5_room]
    - [ ] Mocked or Real matchmaking logic.
    - [ ] Game Room with Spectator support.

## Phase 6: Polish
*Goal: I18n and UX.*

- [ ] Task: Localization & Polish.
