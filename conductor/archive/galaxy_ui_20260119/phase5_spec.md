# Specification: Phase 5 - Multiplayer & Social (HvH)

## 1. Overview
Implement the social and competitive multiplayer infrastructure for KaTrain Galaxy UI. This includes a global lobby, matchmaking for rated/free games, real-time social panels, and a spectator mode.

## 2. Functional Requirements

### 2.1 Social Integration
*   **Friends & Relationships:**
    *   Utilize the `relationships` table for "Follow" logic.
    *   Display `FriendsPanel` in the right sidebar of the Dashboard and Lobby.
    *   Show online/offline status for friends (requires WebSocket presence tracking).
*   **User Profiles:**
    *   Popups or pages showing user statistics: Rank, Elo, Credits, Net Wins, and Recent Games.

### 2.2 Multiplayer Lobby (`/galaxy/play/human`)
*   **Game Discovery:**
    *   List of active game rooms with metadata (Players, Ranks, Game Type, Spectator count).
    *   "Watch" button for any ongoing game.
*   **Matchmaking:**
    *   **Prerequisite:** Users MUST complete the AI Rating placement (3 games) before joining "Rated" HvH matchmaking.
    *   **Modes:** Separate queues for "Rated" (ELO-based) and "Free" (Open) matches.
    *   **UI:** Overlay showing queue time and search status.

### 2.3 Game Room (`/galaxy/play/human/room/:id`)
*   **Real-time Interaction:**
    *   WebSocket-based move synchronization.
    *   Shared timers (Main Time + Byo-yomi) that stop/start based on turns.
    *   "Resign" and "Request Counting" functionality.
*   **Spectator Support:**
    *   Multiple users can join as "Spectators".
    *   Spectators see the board and analysis but cannot make moves.
    *   Live chat for players and spectators.

### 2.4 Backend Requirements
*   **WebSocket Hub:** A central hub to manage room states, player presence, and event broadcasting.
*   **Matchmaking Service:** A simple ELO-based matching logic that pairs players in the "Rated" queue.
*   **Game State Persistence:** Periodically save current SGF to the `games` table to allow recovery from disconnects.

## 3. Visual & UX Requirements
*   **Interactive Elements:** Use "claymorphism" or "glassmorphism" subtle effects for hover states on lobby cards.
*   **Notifications:** Toast notifications for match found, friend login, or game invites.
