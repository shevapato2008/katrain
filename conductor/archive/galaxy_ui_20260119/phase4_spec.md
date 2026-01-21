# Specification: Phase 4 - Play Module (Revised v4)

## 1. Overview
Redesign the Play module to match Galaxy Go style, ensuring full feature parity with KaTrain desktop regarding rules, handicap, timer display, and rank labeling.

## 2. Functional Requirements

### 2.1 Game Setup (Setup Page)
*   **Ruleset Selection:** Add a dropdown for Rules (Japanese, Chinese, Korean, AGA, New Zealand, Tromp-Taylor). Default to Japanese.
*   **Handicap Initialization:** Ensure that selecting a handicap (e.g., 2-9 stones) correctly places stones on the board and sets the initial player turn (AI moves if User is Black with handicap).
*   **Time Control Details:** Clearly label the units (Minutes for Main Time, Seconds for Byo-yomi).

### 2.2 Audio & Visual Feedback
*   **Stone Placement Sound:** Functional sounds for moves.
*   **Rank Labeling (Crucial):** 
    *   Map internal AI rank values to human-readable strings: 20k...1k, 1d...9d.
    *   Ensure consistency between setup slider and in-game display.
*   **Winrate Graph:** Display winrate/score progression in the right sidebar.

### 2.3 Timer UI (In-Game)
*   **Display Components:** The Player Card MUST explicitly show:
    1.  **Main Time:** Remaining time in `MM:SS` format.
    2.  **Byo-yomi:** The length of the current period.
    3.  **Periods:** Number of remaining byo-yomi periods (e.g., `3x`).
*   **Automatic Start:** Timer starts immediately upon game load if enabled.

### 2.4 Rated Game vs AI (Ranked Mode)
*   **Constraints:** Fixed 19x19, Human-like AI, No Undo, No Analysis.
*   **Rank Progression:** Display player's net wins and progress toward the next rank.

## 3. Implementation Plan (Updated)

### 4.1 Backend - Core Logic Fixes
- [x] Ranking DB schema and Result recording.
- [x] **Fix Handicap:** Ensure `new_game` correctly applies handicap stones based on the ruleset.
- [x] **Fix AI Move Logic:** Add check in `_do_ai_move` to only generate moves when next player is AI.
- [x] **Fix Player Update API:** Add `name` field to `UpdatePlayerRequest` model.
- [x] **Add AI Strategy Defaults:** Expose `strategy_defaults` in `/api/ai-constants` endpoint.

### 4.2 Frontend - AI Setup & Initialization
- [x] **AiSetupPage:** Add Ruleset dropdown.
- [x] **AiSetupPage:** Fix unit labeling for Time Control.
- [x] **Rank Mapping Utility:** Create a central utility (`rankUtils.ts`) to map internal ranks to strings (20k to 9d).
- [x] **AiSetupPage:** Fix AI Strategy dropdown display (remove "ai:" prefix, add display names).
- [x] **AiSetupPage:** Load strategy-specific default settings when opponent changes.
- [x] **AiSetupPage:** Fix Komi slider step from 1.0 to 0.25 for quarter-point increments.
- [x] **AiSetupPage:** Remove blocking `API.aiMove()` call - navigate immediately, let WebSocket handle AI moves.

### 4.3 Frontend - Player Card & Sidebar
- [x] **PlayerCard:** Redesign timer display to show Main Time, Byo-yomi, and Periods simultaneously.
- [x] **PlayerCard:** Apply Rank Mapping utility to AI and User ranks.
- [x] **PlayerCard:** Display player names correctly (human username, AI strategy label).
- [x] **RightSidebarPanel:** Finalize "Items" and Graph integration.
- [x] **RightSidebarPanel:** Display Ruleset and Komi in game sidebar.