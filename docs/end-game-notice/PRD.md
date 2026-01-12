# Product Requirement Document: End Game & Pass Notifications

## 1. Overview
This feature aims to improve the user experience in the KaTrain Web UI by providing clear visual and audio feedback when significant game events occur, specifically "PASS" moves and game end conditions. Currently, users may miss these events, leading to confusion about the game state.

## 2. Goals
*   **Clarity:** Ensure users are immediately aware when a player passes.
*   **Feedback:** Provide multi-modal feedback (visual and audio) for critical game events.
*   **Control:** Allow users to configure these notifications according to their preference.

## 3. User Stories
*   **As a player**, I want to hear a sound when the AI passes, so I don't wait for a move that has already happened.
*   **As a player**, I want to see a visual notification ("Black Passed") when a pass occurs, to confirm the game state.
*   **As a user**, I want to be able to disable these sounds if I am in a quiet environment.
*   **As a user**, I want to know clearly when the game has ended due to two consecutive passes or resignation.

## 4. Features & Requirements

### 4.1. Pass Notification
*   **Trigger:** A player (Human or AI) plays a "PASS" move.
*   **Visual:** A transient notification (Snackbar/Toast) appearing at the bottom/top of the screen.
    *   Text: "{Player} Passed" (e.g., "White Passed").
    *   Duration: ~3 seconds.
    *   Action: Optional "Dismiss" button.
*   **Audio:** A distinctive sound effect (e.g., `boing.wav` or a soft chime) played immediately.
*   **Logic:**
    *   Must trigger *only* on the occurrence of a new pass move.
    *   Should ideally not trigger when navigating history to an existing pass move (though acceptable for MVP if non-intrusive).

### 4.2. Game End Notification
*   **Trigger:** Game state changes to "Ended" (End result string is populated).
*   **Visual:**
    *   Existing behavior: Text overlay on board.
    *   Enhancement: A more prominent dialog or persistent notification stating the result (e.g., "Game Ended: W+Resign").
*   **Audio:** Optional "Game Over" sound.

### 4.3. Configuration
*   **Location:** Sidebar -> Settings (or a new "UI Settings" section).
*   **Options:**
    *   `Enable Pass Alert (Visual)`: Toggle (Default: On).
    *   `Enable Pass Sound`: Toggle (Default: On).
*   **Persistence:** Settings should be saved in `localStorage` so they persist across sessions.

## 5. Technical Constraints
*   **Frontend Only:** This feature should be implementable entirely within the React frontend (`katrain/web/ui`), utilizing the existing WebSocket state updates.
*   **Assets:** Use existing sound assets where possible (`/assets/sounds/boing.wav`).

## 6. Future Scope (Non-MVP)
*   **Event Log:** A dedicated side panel logging all major events (Passes, Atari, Tenuki, etc.) for review.
*   **Custom Sounds:** Allow users to upload or select different notification sounds.