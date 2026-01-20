# Track: Web UI Top Moves Parity

## Overview
This track aims to update the KaTrain Web UI's top moves display on the board to better align with the Kivy-based desktop application. The goal is to provide a cleaner and more consistent visual experience by limiting the number of top moves shown and aligning the statistical information displayed on the candidate stones.

## Functional Requirements
1.  **Limit Top Moves on Board:**
    *   Add a configuration setting (in `katrain/config.json`) to limit the number of top moves displayed on the board (e.g., `max_top_moves_on_board`).
    *   Expose this setting in the Web UI (likely in the "AI Settings" or "Teaching Settings" dialog) to allow users to configure the limit.
    *   The default limit should be set to **3**.
    *   The board rendering logic (`katrain/web/ui/src/components/Board.tsx`) must respect this limit and only render the top N moves based on the engine's output order.

2.  **Align Statistics Display:**
    *   Update the rendering of candidate moves in the Web UI to display **two** statistics directly on the stones.
    *   **No Hover Effects:** The statistics must be visible at all times, not just on hover.
    *   The two statistics to be displayed are:
        1.  **Score Loss** (Top) - e.g., `-0.5`
        2.  **Number of Visits** (Bottom) - e.g., `500`
    *   The font size and layout should be adjusted to accommodate both values legibly within the stone/circle.
    *   The color coding of the stones (based on quality/score loss) should remain consistent with the existing logic.

## Acceptance Criteria
*   [ ] The Web UI board displays a maximum of 3 top moves (or the configured number) when analysis is active.
*   [ ] Users can change the maximum number of top moves in the settings.
*   [ ] The top candidate stones on the board display both Score Loss (top) and Visits (bottom) clearly and permanently (no hover).
*   [ ] The sidebar continues to show the full list of candidate moves with all detailed statistics.
*   [ ] The visual style (colors, fonts) is clean and readable.

## Out of Scope
*   Changing the engine's analysis logic itself (we only filter the display).
*   Implementing the full range of configurable display options from the Kivy GUI (e.g., specific font customizations) beyond what's needed for this alignment.
