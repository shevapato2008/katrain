# Specification: Galaxy Go UI Redesign (Frontend Focus)

## 1. Overview
This track involves a complete redesign of the KaTrain Web UI (`katrain/web/ui`) to match the aesthetic and layout of [Galaxy Go (星阵围棋)](https://19x19.com/engine/index). The goal is to implement a high-fidelity frontend that utilizes the existing KaTrain backend for AI features while introducing PostgreSQL-backed persistence for user data, rank, and social features.

**Key Design Decisions:**
*   **Co-existence:** The new UI will live under `/galaxy` route prefix.
*   **Design Style:** Maintain "Zen Mode" palette, adopt Galaxy Go layout.
*   **Access Control:** Research and Multiplayer features require login.
*   **Data Persistence:** Utilize PostgreSQL for User Profiles, Credits, Cloud SGFs, and Match History.

## 2. User Interface Structure

### 2.1 Global Layout (Shell)
*   **Route:** `/galaxy/*`
*   **Sidebar (Left):**
    *   **Modules:** Play (Active), Research (Active), Report (Disabled), Live (Disabled).
    *   **User Area:** Credits balance display (Placeholder/High value), Profile link, Login/Logout.

### 2.2 Home Page (Dashboard)
*   **Route:** `/galaxy`
*   **Content:** Dashboard with module cards.

### 2.3 Play Module (对弈)

#### A. Play Menu & Setup
*   **Route:** `/galaxy/play`
*   **Game Types:**
    *   **Free (娱乐):** Unranked, customizable settings.
    *   **Rated (升降):** Affects rank, strict settings.
*   **AI Opponents:**
    *   **Ranked Games:** MUST use "Human-like AI" (20k-9D levels).
    *   **Free Games:** Access to all strategies (Ky, KataGo, etc.).

#### B. Human vs AI (人机对弈)
*   **Route:** `/galaxy/play/ai`
*   **Features:**
    *   **AI Rating:** Initial 3-game placement series using Human-like AI.
    *   **Items:** Analysis tools (Ownership, Hints) available without limit (UI styled as items).

#### C. Human vs Human (人人对弈) - *Mocked -> Real*
*   **Lobby UI:**
    *   **Route:** `/galaxy/play/human`
    *   **Features:** List of active games, Online players (Friends highlighted).
    *   **Matchmaking:** Queue for Rated games.
*   **Game Room:**
    *   **Route:** `/galaxy/play/human/room/:id`
    *   **Features:** Board, Player Cards (with Rank/Credits), Chat.

### 2.4 Research Module (研究)
*   **Route:** `/galaxy/research`
*   **Access:** Login Required.
*   **Features:**
    *   **Cloud Library:** Access "My Games" and "Public Games" stored in PostgreSQL.
    *   **Analysis:** Full SGF editor with AI analysis tools.

## 3. Data & Backend Requirements (PostgreSQL)

### 3.1 Database Schema (Conceptual)
*   **`users`**: `id`, `username`, `password_hash`, `rank` (e.g., "5k", "2d"), `credits` (decimal).
*   **`games`**: `id`, `black_player_id`, `white_player_id`, `sgf_content`, `result`, `is_rated`, `played_at`.
*   **`relationships`**: `follower_id`, `following_id`, `created_at`.

### 3.2 API Extensions
*   **Rank/Rating:** Endpoints to update user rank based on Rated game results (Human-like AI or HvH).
*   **Cloud SGF:** CRUD endpoints for `/api/v1/games`.
*   **Credits:** Simple transaction log or balance update endpoints.

## 4. Technical Constraints
*   **Framework:** React + TypeScript + Vite.
*   **Database:** PostgreSQL (docker-compose.db.yml).
*   **Shortcuts:** Keep KaTrain defaults.
*   **Theme:** Zen Mode colors, Galaxy layout.

## 5. Assets
*   **Reference:** Galaxy Go website screenshots (layout/spacing).
*   **Icons:** MUI Icons.
