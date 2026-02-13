# AI Tsumego Solver ("AI解题") - Implementation Plan

## Summary

Add an "AI解题" feature: users manually set up a Go position, optionally draw a region rectangle, and KataGo analyzes the best moves within that region. Static analysis display only (no interactive play).

## Navigation Restructure

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

### Backward-compatible redirects

Add React Router `<Navigate>` redirects for old routes to prevent broken bookmarks:

```tsx
<Route path="tsumego/:level" element={<Navigate to="/galaxy/tsumego/workbook/:level" replace />} />
<Route path="tsumego/:level/:category" element={<Navigate to="/galaxy/tsumego/workbook/:level/:category" replace />} />
<Route path="tsumego/:level/:category/:unit" element={<Navigate to="/galaxy/tsumego/workbook/:level/:category/:unit" replace />} />
```

Implementation: use a small `RedirectWithParams` wrapper that reads `useParams()` and constructs the target path, since React Router `<Navigate>` doesn't interpolate `:param` in `to`.

---

## Phase 1: Backend — Add regionBounds to analysis endpoint

### 1.1 Modify `katrain/web/api/v1/endpoints/analysis.py`
- Add `TsumegoSolveRequest` model with fields: `initial_stones`, `moves`, `board_size`, `komi` (default 0), `rules`, `max_visits` (default 10000), `player_to_move` ("B"/"W"), `region` (optional `{x1, y1, x2, y2}`)
- Add `POST /tsumego-solve` endpoint that builds KataGo payload with `regionBounds` when region is provided
- No auth required (matches `quick-analyze` pattern)
- **Extract shared `_build_katago_payload()` helper** used by both `/tsumego-solve` and `/quick-analyze` to avoid duplicating payload construction logic, default values, and error handling

### 1.2 Backend validation
- Validate `region` coordinates: `0 ≤ x1 ≤ x2 < board_size`, `0 ≤ y1 ≤ y2 < board_size`
- Validate `player_to_move` ∈ {"B", "W"}
- Return 422 with descriptive message on invalid input
- Backend timeout: set `httpx` request timeout proportional to `max_visits` (e.g., `max(30, max_visits / 500)` seconds) to prevent indefinite hangs

### 1.3 Modify `katrain/web/ui/src/api.ts`
- Add `tsumegoSolve` method to `API` object calling `POST /api/v1/analysis/tsumego-solve`

**No changes needed to**: `engine_client.py` (passes payload dict as-is), `router.py` (routing logic unchanged)

---

## Phase 2: Route restructuring

### 2.1 Create `katrain/web/ui/src/galaxy/pages/TsumegoHubPage.tsx` (NEW)
- Follow `PlayMenu.tsx` card grid pattern
- Two cards: "练习册" → `/galaxy/tsumego/workbook`, "AI解题" → `/galaxy/tsumego/ai-solver`
- Use MUI icons (MenuBookIcon, PsychologyIcon or similar)

### 2.2 Modify `katrain/web/ui/src/GalaxyApp.tsx`
- Replace `<Route path="tsumego" element={<TsumegoLevelsPage />} />` with TsumegoHubPage
- Add `tsumego/workbook` route pointing to TsumegoLevelsPage
- Prefix existing `tsumego/:level` etc. with `tsumego/workbook/`
- Add `tsumego/ai-solver` route for AiSolverPage
- **Add redirect routes** for old paths (`tsumego/:level` → `tsumego/workbook/:level` etc.)

### 2.3 Update internal navigation links
Files with `/galaxy/tsumego/${level}` links that need `/workbook/` inserted:

| File | Lines to update |
|------|----------------|
| `TsumegoLevelsPage.tsx` | L89: navigate to `tsumego/workbook/${level.level}` |
| `TsumegoCategoriesPage.tsx` | L92: navigate to `tsumego/workbook/${level}/${cat.category}` |
| `TsumegoUnitsPage.tsx` | L151, L166: navigate back to `tsumego/workbook/${level}`; L207: navigate to `tsumego/workbook/${level}/${category}/${unit}` |
| `TsumegoListPage.tsx` | L131: to `tsumego/workbook/${level}`; L139: to `tsumego/workbook/${level}/${category}` |
| `TsumegoProblemPage.tsx` | L170: to `tsumego/workbook/${level}/${category}`; L381: to `tsumego/workbook/${level}`; L389: to `tsumego/workbook/${level}/${category}` |

Links to `/galaxy/tsumego` (hub) and `/galaxy/tsumego/problem/:id` stay as-is.

---

## Phase 3: AI Solver Page — Core functionality

### 3.1 Create `katrain/web/ui/src/galaxy/hooks/useAiSolverBoard.ts` (NEW)
Based on `useResearchBoard.ts` pattern but simplified:

**State**:
- `stones: Array<{color: 'B'|'W', x: number, y: number}>` — flat array of placed stones
- `boardSize: number` (9/13/19)
- `activeTool: 'placeBlack'|'placeWhite'|'alternate'|'delete'|'drawRect'|null`
- `playerToMove: 'B'|'W'` — who plays first
- `region: {x1,y1,x2,y2}|null` — manual region (board coords, y=0=bottom)
- `rectDragState: {start, preview, isDragging}` — for rectangle drawing
- `analysisResult: {markers, bestPV}|null`, `isAnalyzing: boolean`
- `analysisError: string|null` — error message from failed analysis
- `analysisDepth: 'quick'|'standard'|'deep'` — controls max_visits

**Analysis depth presets**:
| Preset | max_visits | Use case |
|--------|-----------|----------|
| `quick` | 2000 | Fast preview, 9x9 |
| `standard` | 10000 | Default, most positions |
| `deep` | 50000 | Complex positions, thoroughness |

**Key functions**:
- `handleIntersectionClick(x, y)` — place/delete stone based on activeTool
- `handleMouseDown/Move/Up(x, y)` — rectangle drawing when drawRect tool active
- `handleClear()` — clear all stones and region
- `clearRegion()` — clear manual region only
- `autoComputeRegion()` — bounding box of stones + 1 margin, clamped to board edges
- `getEffectiveRegion()` — returns manual region or auto-computed; used for both display and API call
- `startAnalysis()` — validate inputs, convert stones to `[["B","D4"],...]`, convert region to KataGo coords (y-flip), call `API.tsumegoSolve()`, handle errors with `analysisError` state
- `parseResults(response)` — extract `moveInfos` → AiMoveMarker array + bestPV string array for LiveBoard

**Frontend validation before API call** (`startAnalysis`):
- Ensure `stones.length > 0`
- Validate region: `0 ≤ x1 ≤ x2 < boardSize`, `0 ≤ y1 ≤ y2 < boardSize`
- If invalid, set `analysisError` and abort without calling API

**Error handling** (`startAnalysis`):
- Wrap API call in try/catch
- On network error or non-200 response: set `analysisError` with user-readable message
- On success: clear `analysisError`, set `analysisResult`
- Always: set `isAnalyzing = false` in finally block

### 3.2 Create `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverToolbar.tsx` (NEW)
Reuse `ToolButton` pattern and stone icons from `ResearchToolbar.tsx`:
```
Row 1: 摆黑 | 摆白 | 交替 | 删除
Row 2: 画框(CropFreeIcon) | (reserved) | (reserved) | 清空
```

**Note on code reuse**: V1 duplicates `ToolButton` from `ResearchToolbar` for velocity. Tech debt: extract shared `ToolButton` component in follow-up.

### 3.3 Create `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverBoard.tsx` (NEW)
Wrapper around `LiveBoard` with transparent overlay canvas for rectangle drawing:
```tsx
<Box sx={{ position: 'relative' }}>
  <LiveBoard {...boardProps} />
  <canvas  // overlay for rectangle drawing + auto-region visualization
    style={{ position: 'absolute', top: 0, left: 0,
             pointerEvents: isRectMode ? 'auto' : 'none' }}
    onMouseDown/Move/Up={...}
  />
</Box>
```
- Overlay draws: finalized region rect (solid blue border), preview rect (dashed blue)
- **Auto-region visualization**: when no manual region is set and stones exist, draw the auto-computed region as a dashed gray rectangle so users see exactly what area will be analyzed
- Uses same `calculateBoardLayout()` + `gridToCanvas()` from `boardUtils.ts` for coordinate conversion

### 3.4 Create `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverSidebar.tsx` (NEW)
Follow `ResearchSetupPanel.tsx` pattern (width: ~420px, flex column):
- Header: "AI解题"
- Color selector: 黑先/白先 toggle buttons
- AiSolverToolbar (tool grid)
- Board size dropdown (9x9, 13x13, 19x19)
- **Analysis depth selector**: 快速/标准/深入 三挡 (maps to quick/standard/deep)
- Region info display (shows "auto" or manual coords)
- "开始解题" green button (pinned to bottom, disabled when `isAnalyzing` or `stones.length === 0`)
- **Error display**: when `analysisError` is set, show red alert below the button with the error message and a dismiss/retry option

### 3.5 Create `katrain/web/ui/src/galaxy/pages/AiSolverPage.tsx` (NEW)
Layout: left board (AiSolverBoard) + right sidebar (AiSolverSidebar), following ResearchPage L1 pattern.

---

## Phase 4: Analysis results display

After "开始解题":
- **Loading state**: disable analyze button, show spinner icon on button, optionally show semi-transparent overlay on board
- Parse KataGo response `moveInfos` → `AiMoveMarker[]` (top 5 moves with winrate, visits, scoreLead)
- Pass as `aiMarkers` prop to LiveBoard (existing rendering support: colored circles with stats)
- Show best move PV as ghost stones on board
- **PV text display**: show the principal variation as a move sequence in the sidebar (e.g., "1. D4 2. E5 3. F6 ..."), collapsible, with hover highlighting ghost stones on board
- **Error state**: on failure, show error toast/alert in sidebar, return UI to idle state so user can retry

---

## KataGo Region-Restricted API Reference

The KataGo engine supports `regionBounds` in analysis requests:
```json
{
  "id": "tsumego-1",
  "initialStones": [["B", "D4"], ["W", "C5"]],
  "moves": [],
  "rules": "Chinese",
  "komi": 0,
  "boardXSize": 19,
  "boardYSize": 19,
  "regionBounds": { "x1": 0, "y1": 0, "x2": 6, "y2": 6 },
  "maxVisits": 10000
}
```
- Coordinates: 0-indexed, inclusive, (0,0) = top-left
- Works for 9x9, 13x13, 19x19
- Response: only moves within the region in `moveInfos` array
- Pass moves always allowed
- Source: `/Users/fan/Repositories/KataGo/cpp/command/analysis.cpp` (regionBounds parsing at L830-849)
- API wrapper: `/Users/fan/Repositories/KataGo/python/realtime_api/main.py`

---

## Coordinate Conversion Reference

Board display: y=0 is bottom (row 1). KataGo regionBounds: y=0 is top.

```typescript
// Board coords → KataGo regionBounds
kataGoRegion = {
  x1: region.x1,
  y1: boardSize - 1 - region.y2,
  x2: region.x2,
  y2: boardSize - 1 - region.y1,
}
```

Stones → KataGo initialStones:
```typescript
const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'; // skip I
[stone.color, `${letters[stone.x]}${stone.y + 1}`]
```

**Coordinate conversion is done in the frontend hook** (`useAiSolverBoard.startAnalysis`). The backend API accepts KataGo-native coordinates (y=0=top) and passes through as-is. This keeps the backend stateless and agnostic to display conventions.

---

## Files Summary

### New files (7)
| File | Purpose |
|------|---------|
| `katrain/web/ui/src/galaxy/pages/TsumegoHubPage.tsx` | Hub with Workbook + AI Solver cards |
| `katrain/web/ui/src/galaxy/pages/AiSolverPage.tsx` | Main AI solver page layout |
| `katrain/web/ui/src/galaxy/hooks/useAiSolverBoard.ts` | State management hook |
| `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverToolbar.tsx` | Tool button grid |
| `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverSidebar.tsx` | Right sidebar panel |
| `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverBoard.tsx` | Board + rectangle overlay |

### Modified files (8)
| File | Change |
|------|--------|
| `katrain/web/api/v1/endpoints/analysis.py` | Add `/tsumego-solve` endpoint + shared helper |
| `katrain/web/ui/src/api.ts` | Add `tsumegoSolve` API method |
| `katrain/web/ui/src/GalaxyApp.tsx` | Restructure tsumego routes + add redirects |
| `katrain/web/ui/src/galaxy/pages/TsumegoLevelsPage.tsx` | Update card link → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoCategoriesPage.tsx` | Update card link → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoUnitsPage.tsx` | Update nav links → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoListPage.tsx` | Update nav links → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoProblemPage.tsx` | Update breadcrumb links → `/workbook/` |

### Key reference files (reuse patterns from)
| File | What to reuse |
|------|---------------|
| `katrain/web/ui/src/galaxy/pages/PlayMenu.tsx` | Card grid layout for TsumegoHubPage |
| `katrain/web/ui/src/galaxy/pages/ResearchPage.tsx` | Left board + right sidebar page layout |
| `katrain/web/ui/src/galaxy/hooks/useResearchBoard.ts` | Stone placement / edit mode logic |
| `katrain/web/ui/src/galaxy/components/research/ResearchToolbar.tsx` | ToolButton component + stone icons |
| `katrain/web/ui/src/galaxy/components/live/LiveBoard.tsx` | Board rendering, AI markers |
| `katrain/web/ui/src/components/board/boardUtils.ts` | `calculateBoardLayout()`, `gridToCanvas()`, `canvasToGrid()` |

---

## Verification

1. **Backend**: `curl -X POST http://localhost:8001/api/v1/analysis/tsumego-solve -H 'Content-Type: application/json' -d '{"initial_stones":[["B","Q16"],["W","R17"]],"board_size":19,"region":{"x1":13,"y1":0,"x2":18,"y2":6}}'` — should return moveInfos within region
2. **Backend validation**: send invalid region `{"x1":20,"y1":0,"x2":18,"y2":6}` → expect 422
3. **Navigation**: Click 死活题 sidebar → see hub with 2 cards. Click 练习册 → see difficulty levels. Click AI解题 → see solver page. All existing tsumego problem links still work.
4. **Redirects**: Visit old URL `/galaxy/tsumego/5-kyu` → should redirect to `/galaxy/tsumego/workbook/5-kyu`
5. **Stone placement**: Place black/white stones on AI solver board, verify delete/clear work
6. **Rectangle drawing**: Activate 画框 tool, drag on board → see blue rectangle overlay
7. **Auto-region visualization**: Place stones without drawing rectangle → see dashed gray auto-region box on board
8. **Analysis**: Place stones, click 开始解题 → see top move markers + PV text in sidebar
9. **Analysis depth**: Switch to "快速" and "深入", verify response time difference
10. **Error handling**: Stop KataGo server, click 开始解题 → see error message, UI returns to idle
11. **Board sizes**: Repeat analysis with 9x9 and 13x13 boards
12. **Run tests**: `CI=true uv run pytest tests` and `cd katrain/web/ui && npm test`

---

## V2 Backlog

Features deferred from V1, informed by review feedback:

| Feature | Description | Priority |
|---------|-------------|----------|
| SGF import/export | Paste or upload SGF to load positions; export current position | High |
| "Send to AI Solver" | Button on TsumegoProblemPage to send problem position to AI solver | High |
| Touch support | Handle `touchstart/move/end` for rectangle drawing on mobile/tablet | Medium |
| Undo/redo | Undo stack for stone placement operations | Medium |
| Result caching | Cache analysis results by position hash to avoid duplicate KataGo calls | Medium |
| Shared BoardEditToolbar | Extract shared `ToolButton` + toolbar grid from Research and AiSolver | Low (tech debt) |
| Connection pooling | Create `httpx.AsyncClient` at app startup with connection pool instead of per-request | Low (tech debt) |
| Rate limiting | Add rate limit to `/tsumego-solve` to prevent KataGo overload from unauthenticated abuse | Low |

---

## Review History

- **2026-02-08**: Initial plan drafted
- **2026-02-09**: Revised based on Codex and Gemini review feedback:
  - Added backward-compatible redirect routes for old URLs
  - Added backend + frontend input validation for region coordinates
  - Added error handling (loading/error/retry states) throughout
  - Replaced fixed `max_visits` with 3-tier analysis depth presets (quick/standard/deep)
  - Added shared `_build_katago_payload()` helper to avoid code duplication with `/quick-analyze`
  - Added auto-region visualization on board (dashed gray rectangle)
  - Added PV text display in sidebar
  - Added V2 backlog section (SGF import, touch support, caching, cross-feature integration, etc.)
  - Noted tech debt items for shared components and connection pooling
