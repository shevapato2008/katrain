# Review Prompt: KaTrain Report Module Design & Plan

Hi Codex,

I need you to review the design and implementation plan for a new "Report" module (复盘模块) I'm building for my Go analysis application, KaTrain.

## My Needs (User Requirements)
I want to build a module similar to the "Report" feature in Galaxy Go (星阵围棋) [Reference: https://19x19.com/engine/document/report_detail, https://19x19.com/engine/report/public]. 

Key differences and requirements for my module:
1. **Scope:** It only covers the logged-in user's own games and imported games, NOT a public database of professional games.
2. **Trigger:** Games are automatically saved to the database as SGF files upon completion, but **analysis is NOT automatic** because it's computationally expensive (and may be a paid feature later). Users must manually trigger the report generation.
3. **Analysis Method:** Uses the KataGo engine to calculate top moves for every step and saves the results to the database (similar to my existing Live and Play modules).
4. **Frontend - Level 1 Page (My Reports):**
    *   Right sidebar: List of historical games/imported games, sorted reverse chronologically.
    *   List items must show status: Not Generated, Generating (with real-time progress bar, e.g., "50% (100/200 moves)"), or Completed.
    *   Clicking a completed game loads its SGF into the main center board.
    *   Bottom of right sidebar: "View Report" button to enter the Level 2 page.
5. **Frontend - Level 1 Page (Generate Report):**
    *   Allows importing from historical games or uploading an SGF.
    *   Two types of reports: Normal (500 visits/move) and Deep (2000 visits/move).
    *   After clicking "Generate", it redirects to "My Reports" and shows the real-time progress.
6. **Frontend - Level 2 Page (Report Detail):**
    *   Similar to the existing analysis views in Play/Live modules.
    *   Shows Winrate Graph and Score Graph.
    *   Board shows recommended Top Moves with stats (winrate, score difference).
    *   Supports exploring variations.

## What to Review
I have attached two files below:
1.  `design.md`: The system design specification.
2.  `plan.md`: The step-by-step implementation plan.

Please review these documents and answer the following questions:

1.  **Requirement Alignment:** Does the `design.md` fully capture all of my stated needs? Did the AI miss any nuances (especially regarding the async progress tracking, manual triggers, or specific UI layout requirements)?
2.  **Implementation Feasibility:** Look at `plan.md`. Are the proposed database schema, API endpoints, and React components logically sound for achieving the design? 
3.  **Missing Pieces:** What is missing from the `plan.md`? For example:
    *   Are the database queries efficient enough for fetching move data?
    *   Is polling/WebSocket actually planned for in the UI tasks, or did the plan gloss over the real-time progress implementation?
    *   How will the heavy KataGo analysis worker be managed? Is FastAPI's `BackgroundTasks` robust enough for this, or should we be using Celery/Redis given the heavy computation?
4.  **Actionable Feedback:** Provide a bulleted list of specific changes I should ask the AI to make to improve the design or the plan.

---

### Attachment 1: design.md
(Reviewer: Please refer to the design.md content provided previously)

### Attachment 2: plan.md
(Reviewer: Please refer to the plan.md content provided previously)
