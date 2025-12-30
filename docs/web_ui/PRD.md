# KaTrain WebUI - Product Requirements Document (PRD)

## 1. Introduction
The goal of this project is to create a Web User Interface (WebUI) for KaTrain, enabling it to be deployed on a server and accessed by multiple clients via a web browser. This allows users to access KaTrain's powerful analysis and AI play features without installing the desktop application or the heavy KataGo engine locally.

## 2. Core Features
The WebUI must provide full feature parity with the existing Kivy-based desktop application. No desktop-only workflows should remain.

### 2.1. Game Play & Navigation
*   **Play against AI:** Users can play moves against the KataGo AI.
*   **Game Navigation:**
    *   Next/Previous Move.
    *   Jump to Start/End.
    *   Undo/Redo.
    *   Navigate through variations (game tree).
*   **Move Input:** Point-and-click to place stones.
*   **Game Info:** Display captured stones, player names (if applicable), and move number.

### 2.2. Analysis & Review
*   **Real-time Analysis:** Display KataGo's analysis for the current board position.
    *   Win rate.
    *   Score lead/deficit.
    *   Visits/Confidence.
*   **Visual Aids (Overlays):**
    *   **Next Move Hints:** Colored circles on the board indicating top AI moves, colored by quality (Blue=Best, etc.).
    *   **Territory/Ownership:** Heatmap visualization of predicted territory/ownership.
    *   **Policy Map:** Visualization of the AI's raw policy network output (optional but good).
*   **Game Graph:** A win-rate/score graph showing the game's progression.

### 2.3. Configuration
*   **AI Settings:**
    *   Adjust AI strength (Rank/Ky/Dan).
    *   Adjust AI style (Aggressive, Defensive, etc.).
*   **Game Settings:**
    *   Board Size (19x19, 13x13, 9x9).
    *   Rules (Japanese, Chinese, etc.).
    *   Komi.
    *   Handicap.
*   **Trainer Settings:**
    *   Teaching mode prompts and thresholds.
    *   Hint visibility and evaluation thresholds.
    *   Save analysis/feedback settings.
*   **Timer Settings:**
    *   Main time, byo-yomi, and minimal use limits.
    *   Sound on/off, countdown behavior.
*   **Engine Settings:**
    *   Model selection, config selection, and backend selection (local/HTTP).
    *   Fast/slow visits and analysis limits.
*   **Theme Settings:**
    *   Theme selection and related visual toggles.
*   **Language Settings:**
    *   Match Kivy's i18n options and stored preferences.

### 2.4. File I/O and SGF
*   **Load/Save SGF:** Load SGF/NGF/GIB from disk and export current game state.
*   **Auto-save/Auto-load:** Match existing KaTrain behaviors for last directories and default paths.
*   **Game Tree Editing:** Variation creation, pruning, and editing aligned with Kivy controls.

### 2.5. Modes and Workflows
*   **Play/Analyze Modes:** Full parity for Kivy mode toggles and UI states.
*   **Contribute Mode:** Distributed training contribution flow and status dashboard.
*   **Engine Recovery:** Recovery prompts and restart flows for KataGo failures.

### 2.6. System Features (Server-Side)
*   **Multi-Client Support:** The server must handle multiple concurrent user sessions, each with its own game state.
*   **Resource Management:** Efficiently manage the single (or pooled) KataGo instance shared among users.

### 2.7. Interface Selection
*   **Dual Mode Support:** The application must support starting in either the traditional Desktop (Kivy) mode or the new Web Server mode.
*   **Configuration:** The mode selection should be configurable via command-line arguments (e.g., `--ui web`) or configuration files.

## 3. User Interface Design
The UI should closely match the Kivy desktop application, including layout, controls, iconography, colors, and status text. Use KaTrain assets where possible to preserve familiarity.

### 3.1. Layout
*   **Main Board Area:** Central component displaying the Go board. Scalable and responsive.
*   **Sidebar/Panel:**
    *   **Controls:** Play/Pause, Undo/Redo, Navigation buttons.
    *   **Info:** Win rate, score, captures.
    *   **Analysis:** List of top moves with stats.
    *   **Chat/Log:** (Optional) System messages or analysis commentary.
*   **Settings Modal/Drawer:** Configuration options.

### 3.2. Visual Style
*   Preserve KaTrain's visual language: colors, icons, and board/stone rendering.
*   Maintain KaTrain's move-quality color coding (Cyan=Best, Green=Good, etc.).
*   Support both compact and wide layouts similar to the desktop layout.

## 4. Technical Constraints & Requirements
*   **Backend:** Python (to interface with existing `katrain.core`).
*   **Frontend:** Modern JavaScript Framework (React recommended).
*   **Communication:**
    *   **REST API:** For game actions and state retrieval.
    *   **WebSockets:** For streaming real-time analysis updates from KataGo.
*   **Performance:**
    *   The board rendering must be smooth (60fps) even with overlays.
    *   Latency between user action and server response should be minimized.
*   **Browser Support:** Modern browsers (Chrome, Firefox, Safari, Edge).

## 5. Out of Scope (MVP)
*   None for the parity target. All Kivy features should be available via the WebUI.
