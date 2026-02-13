# AI Tsumego Solver — Implementation Plan Review

This is an excellent and detailed implementation plan. It demonstrates a clear understanding of the existing architecture and proposes a logical path forward. The feature will be a valuable addition to the application.

My review is below, structured as requested.

### **Overall Assessment**

*   **Approval Status:** **Needs Minor Revision**
*   **Summary:** The plan is solid, well-structured, and ready for implementation after addressing a few critical points related to robustness and user experience. The core architectural decisions are sound.

---

### **1. Critical Issues (Must Address Before Implementation)**

These are items that represent potential bugs or significant user experience regressions and should be integrated into the plan before coding begins.

1.  **Robust Error & Loading State Handling:** The plan focuses on the success path. It needs to explicitly define how the UI will handle loading states and potential failures.
    *   **Loading State:** While the analysis is running, the "Analyze" button should be disabled, and a loading indicator (e.g., a spinner on the button or an overlay on the board) should be visible.
    *   **Error Handling:** The UI must gracefully manage scenarios where the `/tsumego-solve` endpoint fails (e.g., KataGo timeout, network error, invalid position from KataGo's perspective). The plan should include displaying a user-friendly error message (e.g., using a toast notification) and ensuring the UI returns to an idle state, allowing the user to try again.

2.  **Input Validation on Frontend:** The plan should specify that the frontend is responsible for validating the `region` coordinates *before* sending the request. An API call should not be made if the user-drawn or auto-computed region has coordinates outside the board (e.g., `x > 18` on a 19x19 board). This prevents unnecessary and invalid API calls.

3.  **Handling Broken Links from Restructuring:** The navigation restructure (`/galaxy/tsumego/workbook/...`) is a clean approach, but it will break any existing bookmarks or direct links. The plan should include a strategy to prevent 404 errors for users.
    *   **Recommendation:** Implement redirects. In `GalaxyApp.tsx`, use React Router to set up redirects from the old paths (e.g., `/galaxy/tsumego/5-kyu/...`) to the new, prefixed paths (`/galaxy/tsumego/workbook/5-kyu/...`).

---

### **2. Suggestions for Improvement (Recommended)**

These are high-impact suggestions that will improve the quality, performance, and maintainability of the feature.

1.  **API Performance (Connection Pooling):** In `analysis.py`, instead of creating a new `httpx.AsyncClient` for each request, a single client instance should be created and reused for the application's lifespan. This is a standard best practice in FastAPI that significantly improves performance by reusing HTTP connections.

2.  **Code Reuse vs. Duplication:** The plan correctly notes the similarity between new and existing components (e.g., `AiSolverToolbar` vs. `ResearchToolbar`). While duplicating components might be faster initially, it creates long-term maintenance overhead.
    *   **Pragmatic Approach:** For the initial implementation, it's acceptable to duplicate the `ToolButton` and toolbar structure to maintain velocity. However, **the plan should include creating a tech debt ticket** to refactor these into a single, configurable `BoardEditToolbar` component in the future.

3.  **User-Controlled Analysis Depth:** A fixed `max_visits: 10000` is inflexible. Users will want to balance speed and accuracy.
    *   **Recommendation:** Expose this setting in the `AiSolverSidebar`. A simple dropdown with presets like "Quick" (e.g., 2000 visits), "Standard" (10,000 visits), and "Deep" (50,000 visits) would provide a much better user experience.

4.  **Richer Analysis Results Display:** The current plan for showing top moves and a PV with ghost stones is good. To make it great, also display the Principal Variation (PV) as a **text sequence** (e.g., "AI Suggests: A1, B2, C3...") in the sidebar. This provides a clear, standard, and accessible way to read the AI's top line of play.

5.  **Clarify Auto-Region Behavior:** The "auto-region" heuristic (bounding box + 1) is a good default. The UX will be much clearer if the **UI visually represents this computed region on the board** (e.g., with a dashed rectangle) when the user clicks "Analyze" without having drawn their own. This shows the user precisely what area is being analyzed.

---

### **3. Questions & Future Considerations (For the Backlog)**

These are ideas sparked by the plan that are likely outside the scope of V1 but are valuable for future iterations.

1.  **SGF Import/Export:** Manually placing stones is tedious for complex problems. Would adding a simple "Import from SGF" text box be a valuable addition for V2? Similarly, an "Export to SGF" button would allow users to save their created positions.
2.  **Undo/Redo:** When setting up a board, users often make mistakes. Is an undo/redo stack for stone placements feasible and worth considering for a future update?
3.  **Cross-Feature Integration:** The idea of a "Send to AI Solver" button on a workbook problem page is excellent. This would create a powerful, seamless learning loop for users and should be a high-priority V2 feature.
4.  **Mobile/Touch Support:** Has touch support for the rectangle drawing been considered? The drag-and-drop logic should handle `touch` events (`touchstart`, `touchmove`, `touchend`) to be usable on tablets and mobile devices.
5.  **Result Caching:** For identical board positions and analysis settings, the result will always be the same. A future optimization could be to implement a backend cache (e.g., using Redis) to store and serve results for common problems instantly, reducing redundant computation.

---

### **Answers to Specific Review Questions**

*   **Architecture (Hub Page):** Yes, the hub page is a clean and scalable approach. (Addressed in "Critical Issues").
*   **Architecture (Component Separation):** Yes, the hook/component separation is well-balanced and follows modern React best practices.
*   **Architecture (Canvas Overlay):** Yes, a separate canvas overlay is the right choice. It's performant and correctly decouples the drawing logic from the `LiveBoard` component.
*   **API (New Endpoint):** Yes, a new `/tsumego-solve` endpoint is better than extending `/quick-analyze`. It keeps the API clean and focused (Single Responsibility Principle).
*   **API (Coordinate Conversion):** Yes, the frontend hook is the correct layer to handle the y-flip conversion. The backend API should remain agnostic to the frontend's coordinate system.
*   **Testing:** The plan needs more frontend testing. At a minimum, **add unit tests for the `useAiSolverBoard` hook**, especially for the coordinate conversion and API payload generation logic. For E2E tests (if you have them), a simple case of placing stones, drawing a region, and verifying an API call is made would be valuable.