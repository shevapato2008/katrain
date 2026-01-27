# Specification: Galaxy-Style Live Game Module

## 1. Overview
Implement a "Live Game" (直播) module for KaTrain Galaxy GUI (Desktop/Kivy) that allows users to watch professional Go games in real-time. The visual style and functionality will mimic the Galaxy Go (19x19.com) live interface. The system will fetch game data (moves, player info, commentary) from external sources but will use the local KataGo engine for real-time analysis.

## 2. Functional Requirements

### 2.1 Game Source & Data Architecture
*   **Architecture:** Use a **Poller + Cache** pattern. A background thread (`LivePoller`) periodically fetches data from external APIs and updates a local cache (`LiveCache`) to ensure the GUI never freezes.
*   **Data Sources:**
    *   **Primary (Live - XingZhen):**
        *   Base URL: `https://api.19x19.com/api/engine/golives`
        *   Endpoints: `/all` (Active List), `/situation/{live_id}` (Moves), `/winrates/{live_id}` (Stats).
    *   **Secondary (Recent/SGF - CWQL):**
        *   Base URL: `https://wqapi.cwql.org.cn`
        *   Endpoints: `/playerInfo/battle/list` (List), `/playerInfo/battle/{battleNo}` (SGF).
*   **Lobby UI:**
    *   Display a list of live games as clickable "cards".
    *   Status indicators: "Live" (Green), "Finished" (Gray).

### 2.2 Live Board & Analysis
*   **Real-time Updates:** The board automatically plays new moves as they are fetched by the Poller.
*   **Local AI Analysis:**
    *   The local KataGo engine analyzes the current board state.
    *   **Graphs:** Display Win Rate and Score Lead curves.
    *   **Move Evaluation:**
        *   **"Brilliant Move" (妙手):** Delta > +2.0 points (configurable).
        *   **"Mistake" (问题手):** Delta < -3.0 points (configurable).
        *   **"Questionable" (疑问手):** Delta < -1.5 points (configurable).
*   **Interactive Variations (Hover):**
    *   **Hover Effect:** Hovering over AI suggestions displays the **Pv (Principal Variation)** as ghost stones.
    *   **Ref:** Re-implement logic similar to `draw_pv()` in `badukpan.py`.

### 2.3 Right Sidebar Layout (Live Mode)
The Right Sidebar will use a **Tabbed Layout**:
*   **Tab 1: Live Commentary (直播):**
    *   **Top:** Analysis Stats & Graphs.
    *   **Middle:** Dedicated scrollable commentary/chat area (Data from XingZhen).
    *   **Bottom:** Live Controls ("Try", "Territory", "Moves", "No Hint").
*   **Tab 2: Future Schedule (赛事预告):**
    *   Display a list of upcoming tournaments.
    *   Data Source: To be implemented (likely scraping weiqi.org or manually curated for MVP).

## 3. Configuration (Default Values)
*   `live.polling.list_interval`: 60s
*   `live.polling.moves_interval`: 3s
*   `live.display.brilliant_threshold`: 2.0
*   `live.display.mistake_threshold`: -3.0

## 4. Non-Functional Requirements
*   **Performance:** Move fetching must not block the UI (Kivy Main Thread).
*   **Resilience:** Handle network errors gracefully (retry logic in Poller).

## 5. Out of Scope
*   Video Streaming.
*   Server-side AI Analysis (we use local).
*   User Login/Posting Comments (Read-only for MVP).
