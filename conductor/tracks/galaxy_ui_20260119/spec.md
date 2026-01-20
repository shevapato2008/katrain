# Specification: Galaxy Go UI Redesign (Frontend Focus)

## 1. Overview
This track involves a complete redesign of the KaTrain Web UI (`katrain/web/ui`) to match the aesthetic and layout of [Galaxy Go (星阵围棋)](https://19x19.com/engine/index). The goal is to implement a high-fidelity frontend that utilizes the existing KaTrain backend for AI features while mocking missing backend capabilities (like multi-player matching) to ensure a complete visual prototype.

## 2. User Interface Structure

### 2.1 Global Layout (Shell)
*   **Sidebar (Left):**
    *   **Top:** Navigation menu listing main modules: "Play" (对弈), "Research" (研究), "Report" (报告), "Live" (直播).
        *   *Note:* "Report" and "Live" will be visually present but disabled (greyed out).
    *   **Bottom:**
        *   **Settings:** Language selection with flag icons (reusing existing i18n logic).
        *   **Account Area:**
            *   **Pre-login:** Login/Register forms.
            *   **Post-login:** User profile summary (Avatar, Username, Logout).
*   **Main Content Area (Right):** Dynamic content based on selected module.

### 2.2 Home Page
*   **Content:** A dashboard displaying detailed cards/introductions for the four modules.
*   **Interactions:** "Enter" buttons for "Play" and "Research" navigate to their respective pages. "Report" and "Live" buttons are disabled.

### 2.3 Play Module (对弈)
This module acts as a sub-router with two main paths:

#### A. Human vs Human (人人对弈) - *Frontend Only / Mocked*
*   **Lobby UI:** A list of available games/players (mocked data).
*   **Matching UI:** A "Quick Match" button showing a searching animation (mocked state).
*   **Game Room UI:** A visual representation of a multi-player game room with a board, chat placeholder, and player avatars.
*   **Gap Analysis:**
    *   *Backend:* No lobby/socket matching logic exists.
    *   *Task:* Create mock API services in the frontend to simulate player lists and matching success.

#### B. Human vs AI (人机对弈) - *Fully Functional*
*   **AI Setup Page (New Interface):**
    *   A dedicated configuration page replacing the current "New Game" popup.
    *   **Controls:** AI Strategy (Ky, KaTrain, etc.), Rank/Strength slider, Handicap, Komi, Time settings.
    *   *Backend:* Maps to `/api/ai-constants` (options) and `/api/new-game`.
*   **Game Board:**
    *   The active game interface.
    *   *Reuse:* Refactor existing board components to match Galaxy styling.
    *   *Backend:* Fully supported by existing Session/Game APIs.

### 2.4 Research Module (研究) - *Fully Functional*
*   **Interface:** A dedicated analysis workbench.
*   **Features:**
    *   SGF Editor (Load/Save/Edit).
    *   Analysis Graph (Winrate/Score).
    *   Move suggestions (colored circles on board).
    *   Branch navigation (Game Tree).
*   **Galaxy Style:**
    *   Redesign the "Analysis Info" panel to match Galaxy's clean, tabular look.
    *   Integrate the "Winrate Graph" more seamlessly into the bottom or side panel.
*   **Gap Analysis:**
    *   *Backend:* Fully supported by `/api/analysis/*`, `/api/nav/*`, `/api/sgf/*`.
    *   *Task:* Heavy CSS/Layout refactoring of existing components.

## 3. Functional Requirements

| Feature | Galaxy UI Component | Backend Status | Implementation Strategy |
| :--- | :--- | :--- | :--- |
| **Auth** | Sidebar Bottom | **Ready** (`/api/auth/*`) | Wire new forms to existing API. |
| **Play Auth**| Play Module | **Ready** (Frontend Auth) | Implement an Auth Guard: show "Please login to play" reminder if not authenticated. |
| **i18n** | Sidebar Settings | **Ready** (`/api/language`) | Reuse logic, update UI to flags. |
| **Nav** | Sidebar Top | N/A | React Router implementation. |
| **H-H Play** | Play -> Human | **Missing** | Build UI with **Mock Services**. |
| **H-AI Setup**| Play -> AI Setup | **Ready** (`/api/new-game`) | New Form UI consuming `ai-constants`. |
| **Game Board**| Play / Research | **Ready** (Session/Game) | Restyle existing Board component. |
| **Analysis** | Research Panel | **Ready** (Analysis API) | Restyle Graph & Move tables. |

## 4. Technical Constraints
*   **Framework:** React + TypeScript + Vite (Existing `katrain/web/ui` stack).
*   **State Management:** Use Context API or Zustand (if already present) to manage "Mock Mode" vs "Real Mode" states.
*   **Styling:** CSS Modules or SCSS. Avoid heavy UI libraries if possible to maintain custom Galaxy look; utilize Tailwind if currently in use, otherwise stick to standard CSS.
*   **Translation:** Use `katrain-i18n-expert` skill or similar context-aware translation for Go terminology to ensure high-quality localization.

## 5. Assets
*   Use screenshots provided in the `gemini-clipboard` as primary design references.
*   Use `docs/galaxy_module_intro/*.txt` for text content and tooltips.
