# AI Tsumego Solver — Implementation Plan Review Request

## Background

I'm building a Go/Baduk teaching application (KaTrain) with a web UI (FastAPI + React/TypeScript). The app already has:
- A tsumego (life-and-death problem) workbook module with difficulty-based browsing
- A research mode where users set up board positions and run KataGo AI analysis
- A `LiveBoard` React component that renders Go boards with AI move markers
- A KataGo HTTP API backend that supports `regionBounds` for region-restricted analysis

I want to add a new **"AI解题" (AI Solver)** feature: users manually set up a Go position on the board, optionally draw a rectangle to define the analysis region, and KataGo analyzes the best moves within that region. This is static analysis display only — no interactive play mode.

## Existing Architecture (Key Context)

**Tech stack:** FastAPI + Uvicorn (backend), React + TypeScript + MUI + Vite (frontend), KataGo HTTP API (AI engine)

**Routing:** The app uses React Router. The Galaxy module routes are defined in `GalaxyApp.tsx`. Currently `/galaxy/tsumego` goes directly to the difficulty levels page.

**Existing patterns the plan reuses:**
- `PlayMenu.tsx` — card grid layout for mode selection (3-column MUI grid with hover effects)
- `ResearchPage.tsx` — left board + right sidebar layout for board editing
- `useResearchBoard.ts` — React hook for client-side board state management (stone placement, edit modes)
- `ResearchToolbar.tsx` — tool button grid with custom SVG stone icons and ToolButton component
- `LiveBoard.tsx` — canvas-based Go board renderer that accepts `aiMarkers?: AiMoveMarker[]` prop
- `boardUtils.ts` — exports `calculateBoardLayout()`, `gridToCanvas()`, `canvasToGrid()` for coordinate conversion
- `analysis.py` — FastAPI endpoint file with existing `/quick-analyze` (no auth, builds KataGo payload)

**KataGo regionBounds API:**
```json
{
  "initialStones": [["B", "D4"], ["W", "C5"]],
  "moves": [],
  "rules": "Chinese",
  "komi": 0,
  "boardXSize": 19, "boardYSize": 19,
  "regionBounds": { "x1": 0, "y1": 0, "x2": 6, "y2": 6 },
  "maxVisits": 10000
}
```
- Coordinates: 0-indexed, inclusive, (0,0) = top-left
- Response: only moves within the region in `moveInfos` array

**Coordinate system mismatch:** The frontend board uses y=0 at bottom (row 1), while KataGo uses y=0 at top. Conversion required.

---

## The Plan Under Review

Please review the following implementation plan and provide feedback:

---

### Summary

Add an "AI解题" feature: users manually set up a Go position, optionally draw a region rectangle, and KataGo analyzes the best moves within that region. Static analysis display only (no interactive play).

### Navigation Restructure

**Current**: `/galaxy/tsumego` → shows difficulty levels directly
**New**: `/galaxy/tsumego` → hub page with sub-module cards

```
/galaxy/tsumego              → TsumegoHubPage (NEW hub with cards)
/galaxy/tsumego/workbook     → TsumegoLevelsPage (MOVED)
/galaxy/tsumego/workbook/:level → TsumegoCategoriesPage (UPDATED prefix)
/galaxy/tsumego/workbook/:level/:category → TsumegoUnitsPage
/galaxy/tsumego/workbook/:level/:category/:unit → TsumegoListPage
/galaxy/tsumego/ai-solver    → AiSolverPage (NEW)
/galaxy/tsumego/problem/:problemId → TsumegoProblemPage (UNCHANGED)
```

### Phase 1: Backend — New `/tsumego-solve` endpoint

- Add `TsumegoSolveRequest` Pydantic model with: `initial_stones`, `moves`, `board_size`, `komi` (default 0), `rules`, `max_visits` (default 10000), `player_to_move` ("B"/"W"), `region` (optional `{x1, y1, x2, y2}`)
- Add `POST /tsumego-solve` endpoint that builds KataGo payload with `regionBounds` when region is provided
- No auth required (matches existing `quick-analyze` pattern)
- Add `tsumegoSolve` method to frontend `API` object

### Phase 2: Route restructuring

- Create `TsumegoHubPage.tsx` with 2 cards ("练习册" + "AI解题") following `PlayMenu.tsx` pattern
- Update `GalaxyApp.tsx` routes: add hub, prefix workbook routes with `/workbook/`
- Update 10 navigate calls across 5 tsumego page files to insert `/workbook/` segment

### Phase 3: AI Solver Page — Core functionality

**New hook `useAiSolverBoard.ts`** (based on `useResearchBoard.ts` but simplified):
- State: stones array, boardSize, activeTool, playerToMove, region, analysisResult, isAnalyzing
- Tools: placeBlack, placeWhite, alternate, delete, drawRect
- Functions: handleIntersectionClick, rectangle drag handlers, handleClear, autoComputeRegion (bounding box + 1 margin), startAnalysis (with y-flip coordinate conversion)

**New components:**
- `AiSolverToolbar.tsx` — 4x2 tool grid (摆黑/摆白/交替/删除/画框/清空)
- `AiSolverBoard.tsx` — LiveBoard wrapper with transparent canvas overlay for rectangle drawing
- `AiSolverSidebar.tsx` — right panel: player toggle, board size select, toolbar, region info, analyze button
- `AiSolverPage.tsx` — left board + right sidebar layout

### Phase 4: Analysis results display

- Parse KataGo `moveInfos` → `AiMoveMarker[]` (top 5 moves)
- Pass as `aiMarkers` prop to LiveBoard (existing rendering)
- Show best move PV as ghost stones on board

### New files (7), Modified files (8)

---

## Review Questions

Please evaluate the plan on these dimensions and provide specific, actionable feedback:

### 1. Architecture & Design
- Is the navigation restructure (adding a hub page with `/workbook/` prefix) a clean approach? Any concerns about breaking existing bookmarks/links or SEO?
- Is the separation of hook (`useAiSolverBoard`) vs components (`AiSolverBoard`, `AiSolverToolbar`, `AiSolverSidebar`) well-balanced, or is anything over/under-abstracted?
- Should the rectangle drawing overlay use a canvas layer on top of LiveBoard, or would a different approach (e.g., SVG overlay, or integrating into LiveBoard itself) be better?

### 2. API Design
- Is adding a separate `/tsumego-solve` endpoint the right approach, or should we extend the existing `/quick-analyze` endpoint with an optional `region` parameter?
- Is the coordinate conversion (y-flip between board display and KataGo) handled at the right layer (frontend hook)? Should it be in the backend instead?
- Is `max_visits: 10000` a reasonable default for tsumego analysis? Too high for UX responsiveness? Too low for accuracy?

### 3. UX Concerns
- The plan uses "auto-region" (bounding box of stones + 1 margin) when no rectangle is drawn. Is this always correct for tsumego? What about positions where the vital point is outside the stone cluster?
- Should there be an SGF import option so users can paste/load positions instead of placing stones one by one?
- Is the tool palette (摆黑/摆白/交替/删除/画框/清空) sufficient, or are there common tsumego setup operations missing?
- Should the analysis results include a principal variation (PV) display as a move sequence, not just top move markers?

### 4. Edge Cases & Robustness
- What happens when the user places an illegal position (e.g., stones that would be captured, ko situations)?
- How should the UI handle KataGo timeout or network errors during analysis?
- What happens if the auto-computed region is too small or too large for meaningful analysis?
- Should there be validation that `region` coordinates are within board bounds before sending to KataGo?

### 5. Performance
- Will the canvas overlay for rectangle drawing cause performance issues, especially with ResizeObserver redraws?
- Is creating a new `httpx.AsyncClient` per request in the engine client acceptable, or should it use a connection pool?

### 6. Missing Features / Future Considerations
- Should the plan account for mobile/touch support for the rectangle drawing?
- Should analysis results be cacheable (same position → same result)?
- Is there a need for "analysis depth" control (quick vs deep analysis)?
- Should the feature support loading positions from existing tsumego problems (e.g., a "send to AI solver" button from the problem page)?

### 7. Code Reuse
- The plan creates new components that closely mirror existing research components. Would it be better to extract shared components (e.g., a generic `BoardEditToolbar`, `BoardWithOverlay`) to avoid duplication?
- The `ToolButton` component in `ResearchToolbar.tsx` could potentially be shared. Is duplicating it in `AiSolverToolbar.tsx` the right call?

### 8. Testing Strategy
- The plan mentions running existing tests but doesn't propose new frontend tests. What would you recommend for testing the AI solver feature?
- Is the backend test approach (mocking the router and testing payload construction) sufficient?

---

## Deliverable

Please provide:
1. **Critical issues** — things that should be changed before implementation
2. **Suggestions** — improvements that would make the plan better but aren't blockers
3. **Questions** — areas where you need more information to give a proper review
4. **Approval status** — overall assessment (ready to implement / needs revision / needs major rework)
