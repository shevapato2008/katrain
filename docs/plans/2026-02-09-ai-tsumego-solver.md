# AI Tsumego Solver ("AI解题") Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an "AI解题" feature where users set up a Go position, optionally draw a region rectangle, and KataGo analyzes the best moves within that region.

**Architecture:** New `/tsumego-solve` backend endpoint wraps KataGo's `regionBounds` feature. Frontend adds a TsumegoHubPage routing layer and a new AiSolverPage with board editing + rectangle overlay. Follows existing ResearchPage (left board + right sidebar) and PlayMenu (card grid) patterns.

**Tech Stack:** FastAPI + Pydantic (backend), React + TypeScript + MUI (frontend), KataGo HTTP API with regionBounds

---

### Task 1: Backend — Add `/tsumego-solve` endpoint

**Files:**
- Modify: `katrain/web/api/v1/endpoints/analysis.py`
- Test: `tests/test_tsumego_solve.py` (Create)

**Step 1: Write the failing test**

Create `tests/test_tsumego_solve.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from katrain.web.server import create_app


@pytest.fixture
def mock_router():
    router = MagicMock()
    router.route = AsyncMock(return_value={
        "id": "tsumego-test",
        "moveInfos": [
            {"move": "D4", "order": 0, "visits": 1000, "winrate": 0.85, "scoreLead": 5.0, "pv": ["D4", "E5"]}
        ],
        "rootInfo": {"visits": 1000, "winrate": 0.85, "scoreLead": 5.0},
    })
    return router


@pytest.fixture
def app(mock_router):
    application = create_app()
    application.state.router = mock_router
    return application


@pytest.mark.asyncio
async def test_tsumego_solve_basic(app, mock_router):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/analysis/tsumego-solve", json={
            "initial_stones": [["B", "Q16"], ["W", "R17"]],
            "board_size": 19,
            "player_to_move": "B",
        })
    assert response.status_code == 200
    payload = mock_router.route.call_args[0][0]
    assert payload["initialStones"] == [["B", "Q16"], ["W", "R17"]]
    assert payload["boardXSize"] == 19
    assert payload["komi"] == 0
    assert "regionBounds" not in payload


@pytest.mark.asyncio
async def test_tsumego_solve_with_region(app, mock_router):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/analysis/tsumego-solve", json={
            "initial_stones": [["B", "Q16"], ["W", "R17"]],
            "board_size": 19,
            "player_to_move": "B",
            "region": {"x1": 13, "y1": 0, "x2": 18, "y2": 6},
        })
    assert response.status_code == 200
    payload = mock_router.route.call_args[0][0]
    assert payload["regionBounds"] == {"x1": 13, "y1": 0, "x2": 18, "y2": 6}
```

**Step 2: Run test to verify it fails**

Run: `CI=true uv run pytest tests/test_tsumego_solve.py -v`
Expected: FAIL — endpoint `/tsumego-solve` not found (404)

**Step 3: Write minimal implementation**

Add to `katrain/web/api/v1/endpoints/analysis.py` after the `QuickAnalyzeRequest` class (line 36):

```python
class TsumegoRegion(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class TsumegoSolveRequest(BaseModel):
    initial_stones: List[List[str]]  # [["B","Q16"],["W","R17"],...]
    moves: List[List[str]] = []
    board_size: int = 19
    komi: float = 0
    rules: str = "chinese"
    max_visits: int = 10000
    player_to_move: str = "B"  # "B" or "W"
    region: Optional[TsumegoRegion] = None


@router.post("/tsumego-solve")
async def tsumego_solve(request: Request, data: TsumegoSolveRequest) -> Any:
    """Tsumego analysis — region-restricted KataGo evaluation."""
    router_instance = getattr(request.app.state, "router", None)
    if not router_instance:
        raise HTTPException(status_code=503, detail="Routing engine not initialized")

    payload = {
        "rules": data.rules,
        "komi": data.komi,
        "boardXSize": data.board_size,
        "boardYSize": data.board_size,
        "initialStones": data.initial_stones,
        "moves": data.moves,
        "maxVisits": data.max_visits,
        "analyzeTurns": [len(data.moves)],
        "includeOwnership": False,
        "includePolicy": False,
    }

    if data.region:
        payload["regionBounds"] = {
            "x1": data.region.x1,
            "y1": data.region.y1,
            "x2": data.region.x2,
            "y2": data.region.y2,
        }

    try:
        result = await router_instance.route(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Step 4: Run test to verify it passes**

Run: `CI=true uv run pytest tests/test_tsumego_solve.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add katrain/web/api/v1/endpoints/analysis.py tests/test_tsumego_solve.py
git commit -m "feat: add /tsumego-solve endpoint with regionBounds support"
```

---

### Task 2: Frontend API — Add `tsumegoSolve` method

**Files:**
- Modify: `katrain/web/ui/src/api.ts`

**Step 1: Add the API method**

Add after `quickAnalyze` method (after line 183 in `api.ts`):

```typescript
  tsumegoSolve: (params: {
    initial_stones: string[][]; moves?: string[][]; board_size?: number;
    komi?: number; rules?: string; max_visits?: number; player_to_move?: string;
    region?: { x1: number; y1: number; x2: number; y2: number } | null;
  }): Promise<any> =>
    apiPost("/api/v1/analysis/tsumego-solve", params),
```

**Step 2: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add katrain/web/ui/src/api.ts
git commit -m "feat: add tsumegoSolve API method"
```

---

### Task 3: TsumegoHubPage — Create hub with cards

**Files:**
- Create: `katrain/web/ui/src/galaxy/pages/TsumegoHubPage.tsx`

**Step 1: Create the hub page**

Create `katrain/web/ui/src/galaxy/pages/TsumegoHubPage.tsx` following `PlayMenu.tsx` card grid pattern:

```tsx
import { Box, Card, CardContent, Typography, CardActionArea } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { useSettings } from '../context/SettingsContext';
import { i18n } from '../../i18n';

const TsumegoHubPage = () => {
    const navigate = useNavigate();
    useSettings();

    const options = [
        {
            title: i18n.t('tsumego:workbook', '练习册'),
            desc: i18n.t('tsumego:workbook_desc', '按难度分类的死活题练习'),
            icon: <MenuBookIcon sx={{ fontSize: 60, color: 'primary.main' }} />,
            path: '/galaxy/tsumego/workbook',
        },
        {
            title: i18n.t('tsumego:ai_solver', 'AI解题'),
            desc: i18n.t('tsumego:ai_solver_desc', '摆放棋子，让AI分析最佳着法'),
            icon: <PsychologyIcon sx={{ fontSize: 60, color: 'secondary.main' }} />,
            path: '/galaxy/tsumego/ai-solver',
        },
    ];

    return (
        <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
            <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>
                {i18n.t('Tsumego', '死活题')}
            </Typography>
            <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 6 }}>
                {i18n.t('tsumego:choose_mode', '选择练习模式')}
            </Typography>

            <Box sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                gap: 4
            }}>
                {options.map((opt) => (
                    <Card
                        key={opt.title}
                        sx={{
                            height: '100%',
                            borderRadius: 4,
                            transition: 'transform 0.2s',
                            '&:hover': {
                                transform: 'translateY(-4px)',
                                boxShadow: 8
                            }
                        }}
                    >
                        <CardActionArea
                            sx={{ height: '100%', p: 2 }}
                            onClick={() => navigate(opt.path)}
                        >
                            <CardContent sx={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                                {opt.icon}
                                <Box>
                                    <Typography variant="h6" fontWeight="bold" gutterBottom>
                                        {opt.title}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {opt.desc}
                                    </Typography>
                                </Box>
                            </CardContent>
                        </CardActionArea>
                    </Card>
                ))}
            </Box>
        </Box>
    );
};

export default TsumegoHubPage;
```

**Step 2: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No errors (file is self-contained, not yet routed)

**Step 3: Commit**

```bash
git add katrain/web/ui/src/galaxy/pages/TsumegoHubPage.tsx
git commit -m "feat: add TsumegoHubPage with workbook and AI solver cards"
```

---

### Task 4: Route restructuring — Wire up hub and update links

**Files:**
- Modify: `katrain/web/ui/src/GalaxyApp.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/TsumegoLevelsPage.tsx` (L89)
- Modify: `katrain/web/ui/src/galaxy/pages/TsumegoCategoriesPage.tsx` (L92)
- Modify: `katrain/web/ui/src/galaxy/pages/TsumegoUnitsPage.tsx` (L151, L166, L207)
- Modify: `katrain/web/ui/src/galaxy/pages/TsumegoListPage.tsx` (L131, L139)
- Modify: `katrain/web/ui/src/galaxy/pages/TsumegoProblemPage.tsx` (L170, L381, L389)

**Step 1: Update GalaxyApp.tsx routes**

Replace lines 38-42 in `GalaxyApp.tsx`:

```tsx
// Before:
<Route path="tsumego" element={<TsumegoLevelsPage />} />
<Route path="tsumego/:level" element={<TsumegoCategoriesPage />} />
<Route path="tsumego/:level/:category" element={<TsumegoUnitsPage />} />
<Route path="tsumego/:level/:category/:unit" element={<TsumegoListPage />} />
<Route path="tsumego/problem/:problemId" element={<TsumegoProblemPage />} />

// After:
<Route path="tsumego" element={<TsumegoHubPage />} />
<Route path="tsumego/workbook" element={<TsumegoLevelsPage />} />
<Route path="tsumego/workbook/:level" element={<TsumegoCategoriesPage />} />
<Route path="tsumego/workbook/:level/:category" element={<TsumegoUnitsPage />} />
<Route path="tsumego/workbook/:level/:category/:unit" element={<TsumegoListPage />} />
<Route path="tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
```

Add import at top:
```tsx
import TsumegoHubPage from './galaxy/pages/TsumegoHubPage';
```

**Step 2: Update navigate links in all tsumego pages**

In each file, insert `/workbook` into the tsumego path segments (but NOT links to `/galaxy/tsumego` hub or `/galaxy/tsumego/problem/`):

- `TsumegoLevelsPage.tsx` L89: `/galaxy/tsumego/${level.level}` → `/galaxy/tsumego/workbook/${level.level}`
- `TsumegoCategoriesPage.tsx` L92: `/galaxy/tsumego/${level}/${cat.category}` → `/galaxy/tsumego/workbook/${level}/${cat.category}`
- `TsumegoUnitsPage.tsx` L151: `/galaxy/tsumego/${level}` → `/galaxy/tsumego/workbook/${level}`
- `TsumegoUnitsPage.tsx` L166: `/galaxy/tsumego/${level}` → `/galaxy/tsumego/workbook/${level}`
- `TsumegoUnitsPage.tsx` L207: `/galaxy/tsumego/${level}/${category}/${unit.unitNumber}` → `/galaxy/tsumego/workbook/${level}/${category}/${unit.unitNumber}`
- `TsumegoListPage.tsx` L131: `/galaxy/tsumego/${level}` → `/galaxy/tsumego/workbook/${level}`
- `TsumegoListPage.tsx` L139: `/galaxy/tsumego/${level}/${category}` → `/galaxy/tsumego/workbook/${level}/${category}`
- `TsumegoProblemPage.tsx` L170: `/galaxy/tsumego/${problem.level}/${problem.category}` → `/galaxy/tsumego/workbook/${problem.level}/${problem.category}`
- `TsumegoProblemPage.tsx` L381: `/galaxy/tsumego/${problem.level}` → `/galaxy/tsumego/workbook/${problem.level}`
- `TsumegoProblemPage.tsx` L389: `/galaxy/tsumego/${problem.level}/${problem.category}` → `/galaxy/tsumego/workbook/${problem.level}/${problem.category}`

Leave unchanged: navigations to `/galaxy/tsumego` (hub) and `/galaxy/tsumego/problem/:id`.

**Step 3: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No errors

**Step 4: Verify in browser**

Manual check: Navigate to `/galaxy/tsumego` → see hub with 2 cards. Click "练习册" → see difficulty levels. All breadcrumb links work.

**Step 5: Commit**

```bash
git add katrain/web/ui/src/GalaxyApp.tsx \
  katrain/web/ui/src/galaxy/pages/TsumegoLevelsPage.tsx \
  katrain/web/ui/src/galaxy/pages/TsumegoCategoriesPage.tsx \
  katrain/web/ui/src/galaxy/pages/TsumegoUnitsPage.tsx \
  katrain/web/ui/src/galaxy/pages/TsumegoListPage.tsx \
  katrain/web/ui/src/galaxy/pages/TsumegoProblemPage.tsx
git commit -m "refactor: restructure tsumego routes with hub page and /workbook prefix"
```

---

### Task 5: AI Solver hook — `useAiSolverBoard`

**Files:**
- Create: `katrain/web/ui/src/galaxy/hooks/useAiSolverBoard.ts`

**Step 1: Create the hook**

Create `katrain/web/ui/src/galaxy/hooks/useAiSolverBoard.ts`:

```typescript
import { useState, useCallback } from 'react';
import { API } from '../../api';
import type { AiMoveMarker } from '../components/live/LiveBoard';

export type AiSolverTool = 'placeBlack' | 'placeWhite' | 'alternate' | 'delete' | 'drawRect' | null;

interface Stone {
  color: 'B' | 'W';
  x: number;
  y: number;
}

interface Region {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface UseAiSolverBoardReturn {
  // State
  stones: Stone[];
  boardSize: number;
  activeTool: AiSolverTool;
  playerToMove: 'B' | 'W';
  region: Region | null;
  analysisResult: AiMoveMarker[] | null;
  isAnalyzing: boolean;

  // Actions
  handleIntersectionClick: (x: number, y: number) => void;
  setActiveTool: (tool: AiSolverTool) => void;
  setPlayerToMove: (color: 'B' | 'W') => void;
  setBoardSize: (size: number) => void;
  setRegion: (region: Region | null) => void;
  handleClear: () => void;
  startAnalysis: () => Promise<void>;

  // Computed
  moves: string[];
  stoneColors: ('B' | 'W')[];
  nextColor: 'B' | 'W' | null;
}

const LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'; // skip I

function stoneToGTP(stone: Stone): [string, string] {
  return [stone.color, `${LETTERS[stone.x]}${stone.y + 1}`];
}

function autoComputeRegion(stones: Stone[], boardSize: number): Region | null {
  if (stones.length === 0) return null;
  const margin = 1;
  const xs = stones.map(s => s.x);
  const ys = stones.map(s => s.y);
  return {
    x1: Math.max(0, Math.min(...xs) - margin),
    y1: Math.max(0, Math.min(...ys) - margin),
    x2: Math.min(boardSize - 1, Math.max(...xs) + margin),
    y2: Math.min(boardSize - 1, Math.max(...ys) + margin),
  };
}

export function useAiSolverBoard(): UseAiSolverBoardReturn {
  const [stones, setStones] = useState<Stone[]>([]);
  const [boardSize, setBoardSizeState] = useState(19);
  const [activeTool, setActiveTool] = useState<AiSolverTool>('alternate');
  const [playerToMove, setPlayerToMove] = useState<'B' | 'W'>('B');
  const [region, setRegion] = useState<Region | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AiMoveMarker[] | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [alternateColor, setAlternateColor] = useState<'B' | 'W'>('B');

  const handleIntersectionClick = useCallback((x: number, y: number) => {
    if (activeTool === 'drawRect') return;

    setStones(prev => {
      const existing = prev.findIndex(s => s.x === x && s.y === y);

      if (activeTool === 'delete') {
        if (existing >= 0) return prev.filter((_, i) => i !== existing);
        return prev;
      }

      let color: 'B' | 'W';
      if (activeTool === 'placeBlack') color = 'B';
      else if (activeTool === 'placeWhite') color = 'W';
      else if (activeTool === 'alternate') {
        color = alternateColor;
        setAlternateColor(c => c === 'B' ? 'W' : 'B');
      } else return prev;

      if (existing >= 0) {
        // Replace existing stone
        const updated = [...prev];
        updated[existing] = { color, x, y };
        return updated;
      }
      return [...prev, { color, x, y }];
    });
    setAnalysisResult(null);
  }, [activeTool, alternateColor]);

  const handleClear = useCallback(() => {
    setStones([]);
    setRegion(null);
    setAnalysisResult(null);
    setAlternateColor('B');
  }, []);

  const setBoardSize = useCallback((size: number) => {
    setBoardSizeState(size);
    setStones([]);
    setRegion(null);
    setAnalysisResult(null);
    setAlternateColor('B');
  }, []);

  const startAnalysis = useCallback(async () => {
    if (stones.length === 0) return;
    setIsAnalyzing(true);
    setAnalysisResult(null);

    const effectiveRegion = region || autoComputeRegion(stones, boardSize);

    // Board coords → KataGo coords (y-flip: y=0=bottom → y=0=top)
    let kataGoRegion: { x1: number; y1: number; x2: number; y2: number } | null = null;
    if (effectiveRegion) {
      kataGoRegion = {
        x1: effectiveRegion.x1,
        y1: boardSize - 1 - effectiveRegion.y2,
        x2: effectiveRegion.x2,
        y2: boardSize - 1 - effectiveRegion.y1,
      };
    }

    try {
      const result = await API.tsumegoSolve({
        initial_stones: stones.map(stoneToGTP),
        board_size: boardSize,
        player_to_move: playerToMove,
        region: kataGoRegion,
      });

      const moveInfos = result.moveInfos || [];
      const markers: AiMoveMarker[] = moveInfos
        .slice(0, 5)
        .map((info: any, idx: number) => ({
          move: info.move,
          rank: idx + 1,
          visits: info.visits,
          winrate: info.winrate,
          score_lead: info.scoreLead,
        }));
      setAnalysisResult(markers);
    } catch (err) {
      console.error('Tsumego analysis failed:', err);
    } finally {
      setIsAnalyzing(false);
    }
  }, [stones, boardSize, playerToMove, region]);

  // Convert stones to LiveBoard format
  const moves = stones.map(s => `${LETTERS[s.x]}${s.y + 1}`);
  const stoneColors = stones.map(s => s.color);

  const nextColor: 'B' | 'W' | null =
    activeTool === 'placeBlack' ? 'B' :
    activeTool === 'placeWhite' ? 'W' :
    activeTool === 'alternate' ? alternateColor :
    null;

  return {
    stones, boardSize, activeTool, playerToMove, region,
    analysisResult, isAnalyzing,
    handleIntersectionClick, setActiveTool, setPlayerToMove,
    setBoardSize, setRegion, handleClear, startAnalysis,
    moves, stoneColors, nextColor,
  };
}
```

**Step 2: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add katrain/web/ui/src/galaxy/hooks/useAiSolverBoard.ts
git commit -m "feat: add useAiSolverBoard hook for AI solver state management"
```

---

### Task 6: AI Solver toolbar component

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverToolbar.tsx`

**Step 1: Create toolbar**

Create `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverToolbar.tsx`:

```tsx
import { Box, Typography, Tooltip } from '@mui/material';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import CropFreeIcon from '@mui/icons-material/CropFree';
import LayersClearIcon from '@mui/icons-material/LayersClear';
import type { AiSolverTool } from '../../hooks/useAiSolverBoard';

interface AiSolverToolbarProps {
  activeTool: AiSolverTool;
  onToolChange: (tool: AiSolverTool) => void;
  onClear: () => void;
}

const ICON_SIZE = 22;

// Reuse stone icon pattern from ResearchToolbar
const BlackStoneIcon = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" fill="#1a1a1a" stroke="#333" strokeWidth="1" />
  </svg>
);

const WhiteStoneIcon = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" fill="#f5f5f0" stroke="#999" strokeWidth="1" />
  </svg>
);

const AlternateIcon = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24">
    <circle cx="8" cy="12" r="7" fill="#1a1a1a" stroke="#333" strokeWidth="1" />
    <circle cx="16" cy="12" r="7" fill="#f5f5f0" stroke="#999" strokeWidth="1" />
  </svg>
);

interface ToolButtonProps {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}

const ToolButton = ({ icon, label, active, onClick }: ToolButtonProps) => (
  <Tooltip title={label} placement="top">
    <Box
      onClick={onClick}
      sx={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5,
        p: 1, borderRadius: 1.5, cursor: 'pointer', minWidth: 56,
        bgcolor: active ? 'action.selected' : 'transparent',
        border: active ? '2px solid' : '2px solid transparent',
        borderColor: active ? 'primary.main' : 'transparent',
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      {icon}
      <Typography variant="caption" sx={{ fontSize: '0.65rem', lineHeight: 1 }}>
        {label}
      </Typography>
    </Box>
  </Tooltip>
);

const AiSolverToolbar = ({ activeTool, onToolChange, onClear }: AiSolverToolbarProps) => (
  <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0.5 }}>
    <ToolButton icon={<BlackStoneIcon />} label="摆黑" active={activeTool === 'placeBlack'} onClick={() => onToolChange('placeBlack')} />
    <ToolButton icon={<WhiteStoneIcon />} label="摆白" active={activeTool === 'placeWhite'} onClick={() => onToolChange('placeWhite')} />
    <ToolButton icon={<AlternateIcon />} label="交替" active={activeTool === 'alternate'} onClick={() => onToolChange('alternate')} />
    <ToolButton icon={<DeleteForeverIcon sx={{ fontSize: ICON_SIZE }} />} label="删除" active={activeTool === 'delete'} onClick={() => onToolChange('delete')} />
    <ToolButton icon={<CropFreeIcon sx={{ fontSize: ICON_SIZE }} />} label="画框" active={activeTool === 'drawRect'} onClick={() => onToolChange('drawRect')} />
    <Box />
    <Box />
    <ToolButton icon={<LayersClearIcon sx={{ fontSize: ICON_SIZE }} />} label="清空" active={false} onClick={onClear} />
  </Box>
);

export default AiSolverToolbar;
```

**Step 2: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add katrain/web/ui/src/galaxy/components/ai-solver/AiSolverToolbar.tsx
git commit -m "feat: add AiSolverToolbar component"
```

---

### Task 7: AI Solver board with rectangle overlay

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverBoard.tsx`

**Step 1: Create board component**

Create `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverBoard.tsx`:

```tsx
import { useRef, useEffect, useCallback, useState } from 'react';
import { Box } from '@mui/material';
import LiveBoard from '../live/LiveBoard';
import { calculateBoardLayout, gridToCanvas, canvasToGrid } from '../../../components/board/boardUtils';
import type { AiMoveMarker } from '../live/LiveBoard';

interface Region {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface AiSolverBoardProps {
  moves: string[];
  stoneColors: ('B' | 'W')[];
  boardSize: number;
  nextColor: 'B' | 'W' | null;
  aiMarkers: AiMoveMarker[] | null;
  region: Region | null;
  isRectMode: boolean;
  onIntersectionClick: (x: number, y: number) => void;
  onRegionChange: (region: Region | null) => void;
}

const AiSolverBoard = ({
  moves, stoneColors, boardSize, nextColor, aiMarkers,
  region, isRectMode, onIntersectionClick, onRegionChange,
}: AiSolverBoardProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragPreview, setDragPreview] = useState<Region | null>(null);

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const layout = calculateBoardLayout(canvas.width, canvas.height, boardSize, true);
    const regionToDraw = dragPreview || region;
    if (!regionToDraw) return;

    const topLeft = gridToCanvas(regionToDraw.x1, regionToDraw.y2, layout); // y2 is higher on board
    const bottomRight = gridToCanvas(regionToDraw.x2, regionToDraw.y1, layout);
    const halfCell = layout.cellSize / 2;

    ctx.strokeStyle = 'rgba(33, 150, 243, 0.8)';
    ctx.lineWidth = 2;
    ctx.setLineDash(dragPreview ? [6, 4] : []);
    ctx.strokeRect(
      topLeft.x - halfCell, topLeft.y - halfCell,
      bottomRight.x - topLeft.x + layout.cellSize,
      bottomRight.y - topLeft.y + layout.cellSize,
    );
    ctx.fillStyle = 'rgba(33, 150, 243, 0.08)';
    ctx.fillRect(
      topLeft.x - halfCell, topLeft.y - halfCell,
      bottomRight.x - topLeft.x + layout.cellSize,
      bottomRight.y - topLeft.y + layout.cellSize,
    );
  }, [boardSize, region, dragPreview]);

  useEffect(() => {
    drawOverlay();
  }, [drawOverlay]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => drawOverlay());
    observer.observe(container);
    return () => observer.disconnect();
  }, [drawOverlay]);

  const getGridCoords = useCallback((e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const layout = calculateBoardLayout(rect.width, rect.height, boardSize, true);
    return canvasToGrid(e.clientX - rect.left, e.clientY - rect.top, layout);
  }, [boardSize]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!isRectMode) return;
    const coords = getGridCoords(e);
    if (coords) setDragStart(coords);
  }, [isRectMode, getGridCoords]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isRectMode || !dragStart) return;
    const coords = getGridCoords(e);
    if (coords) {
      setDragPreview({
        x1: Math.min(dragStart.x, coords.x),
        y1: Math.min(dragStart.y, coords.y),
        x2: Math.max(dragStart.x, coords.x),
        y2: Math.max(dragStart.y, coords.y),
      });
    }
  }, [isRectMode, dragStart, getGridCoords]);

  const handleMouseUp = useCallback(() => {
    if (dragPreview) {
      onRegionChange(dragPreview);
    }
    setDragStart(null);
    setDragPreview(null);
  }, [dragPreview, onRegionChange]);

  return (
    <Box ref={containerRef} sx={{ position: 'relative', width: '100%', height: '100%' }}>
      <LiveBoard
        moves={moves}
        stoneColors={stoneColors}
        currentMove={moves.length}
        boardSize={boardSize}
        showCoordinates
        nextColor={nextColor}
        onIntersectionClick={onIntersectionClick}
        aiMarkers={aiMarkers}
      />
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
          pointerEvents: isRectMode ? 'auto' : 'none',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />
    </Box>
  );
};

export default AiSolverBoard;
```

**Step 2: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add katrain/web/ui/src/galaxy/components/ai-solver/AiSolverBoard.tsx
git commit -m "feat: add AiSolverBoard with rectangle overlay"
```

---

### Task 8: AI Solver sidebar

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverSidebar.tsx`

**Step 1: Create sidebar component**

Create `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverSidebar.tsx`:

```tsx
import { Box, Typography, Button, ToggleButton, ToggleButtonGroup, Select, MenuItem, CircularProgress } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AiSolverToolbar from './AiSolverToolbar';
import type { AiSolverTool } from '../../hooks/useAiSolverBoard';

interface Region {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface AiSolverSidebarProps {
  playerToMove: 'B' | 'W';
  onPlayerToMoveChange: (color: 'B' | 'W') => void;
  activeTool: AiSolverTool;
  onToolChange: (tool: AiSolverTool) => void;
  boardSize: number;
  onBoardSizeChange: (size: number) => void;
  region: Region | null;
  onClear: () => void;
  onClearRegion: () => void;
  onStartAnalysis: () => void;
  isAnalyzing: boolean;
  stoneCount: number;
}

const AiSolverSidebar = ({
  playerToMove, onPlayerToMoveChange,
  activeTool, onToolChange,
  boardSize, onBoardSizeChange,
  region, onClear, onClearRegion,
  onStartAnalysis, isAnalyzing, stoneCount,
}: AiSolverSidebarProps) => (
  <Box sx={{ width: 380, display: 'flex', flexDirection: 'column', gap: 3, p: 3, overflow: 'auto' }}>
    <Typography variant="h5" fontWeight="bold">AI解题</Typography>

    {/* Player to move */}
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>先手</Typography>
      <ToggleButtonGroup
        value={playerToMove}
        exclusive
        onChange={(_, val) => val && onPlayerToMoveChange(val)}
        size="small"
        fullWidth
      >
        <ToggleButton value="B">黑先</ToggleButton>
        <ToggleButton value="W">白先</ToggleButton>
      </ToggleButtonGroup>
    </Box>

    {/* Board size */}
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>棋盘</Typography>
      <Select
        value={boardSize}
        onChange={(e) => onBoardSizeChange(Number(e.target.value))}
        size="small"
        fullWidth
      >
        <MenuItem value={9}>9x9</MenuItem>
        <MenuItem value={13}>13x13</MenuItem>
        <MenuItem value={19}>19x19</MenuItem>
      </Select>
    </Box>

    {/* Toolbar */}
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>工具</Typography>
      <AiSolverToolbar activeTool={activeTool} onToolChange={onToolChange} onClear={onClear} />
    </Box>

    {/* Region info */}
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>分析区域</Typography>
      {region ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.secondary">
            ({region.x1},{region.y1}) - ({region.x2},{region.y2})
          </Typography>
          <Button size="small" onClick={onClearRegion}>清除</Button>
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">自动 (棋子范围+1)</Typography>
      )}
    </Box>

    {/* Spacer */}
    <Box sx={{ flexGrow: 1 }} />

    {/* Analyze button */}
    <Button
      variant="contained"
      color="success"
      size="large"
      startIcon={isAnalyzing ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
      onClick={onStartAnalysis}
      disabled={isAnalyzing || stoneCount === 0}
      fullWidth
      sx={{ py: 1.5 }}
    >
      {isAnalyzing ? '分析中...' : '开始解题'}
    </Button>
  </Box>
);

export default AiSolverSidebar;
```

**Step 2: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add katrain/web/ui/src/galaxy/components/ai-solver/AiSolverSidebar.tsx
git commit -m "feat: add AiSolverSidebar component"
```

---

### Task 9: AI Solver page — Wire everything together

**Files:**
- Create: `katrain/web/ui/src/galaxy/pages/AiSolverPage.tsx`
- Modify: `katrain/web/ui/src/GalaxyApp.tsx` (add route)

**Step 1: Create the page**

Create `katrain/web/ui/src/galaxy/pages/AiSolverPage.tsx`:

```tsx
import { Box } from '@mui/material';
import AiSolverBoard from '../components/ai-solver/AiSolverBoard';
import AiSolverSidebar from '../components/ai-solver/AiSolverSidebar';
import { useAiSolverBoard } from '../hooks/useAiSolverBoard';

const AiSolverPage = () => {
  const board = useAiSolverBoard();

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left: Board */}
      <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
        <Box sx={{ width: '100%', maxWidth: 700, aspectRatio: '1', position: 'relative' }}>
          <AiSolverBoard
            moves={board.moves}
            stoneColors={board.stoneColors}
            boardSize={board.boardSize}
            nextColor={board.nextColor}
            aiMarkers={board.analysisResult}
            region={board.region}
            isRectMode={board.activeTool === 'drawRect'}
            onIntersectionClick={board.handleIntersectionClick}
            onRegionChange={board.setRegion}
          />
        </Box>
      </Box>

      {/* Right: Sidebar */}
      <AiSolverSidebar
        playerToMove={board.playerToMove}
        onPlayerToMoveChange={board.setPlayerToMove}
        activeTool={board.activeTool}
        onToolChange={board.setActiveTool}
        boardSize={board.boardSize}
        onBoardSizeChange={board.setBoardSize}
        region={board.region}
        onClear={board.handleClear}
        onClearRegion={() => board.setRegion(null)}
        onStartAnalysis={board.startAnalysis}
        isAnalyzing={board.isAnalyzing}
        stoneCount={board.stones.length}
      />
    </Box>
  );
};

export default AiSolverPage;
```

**Step 2: Add route to GalaxyApp.tsx**

Add import:
```tsx
import AiSolverPage from './galaxy/pages/AiSolverPage';
```

Add route after the existing tsumego routes:
```tsx
<Route path="tsumego/ai-solver" element={<AiSolverPage />} />
```

**Step 3: Verify build**

Run: `cd katrain/web/ui && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add katrain/web/ui/src/galaxy/pages/AiSolverPage.tsx katrain/web/ui/src/GalaxyApp.tsx
git commit -m "feat: add AiSolverPage and wire up route"
```

---

### Task 10: Build and verify end-to-end

**Step 1: Build frontend**

Run: `cd katrain/web/ui && npm run build`
Expected: Build succeeds, output in `katrain/web/static/`

**Step 2: Run backend tests**

Run: `CI=true uv run pytest tests -v`
Expected: All tests pass

**Step 3: Manual verification**

1. Start app: `python -m katrain --ui web --port 8001`
2. Navigate to `/galaxy/tsumego` → see hub with 2 cards
3. Click "练习册" → see difficulty levels
4. Click "AI解题" → see solver page with board + sidebar
5. Place stones, draw region rectangle, click "开始解题"
6. Verify AI markers appear on board

**Step 4: Commit build output**

```bash
git add katrain/web/static/
git commit -m "build: compile frontend with AI solver feature"
```

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

---

## Files Summary

### New files (7)
| File | Purpose |
|------|---------|
| `tests/test_tsumego_solve.py` | Backend endpoint tests |
| `katrain/web/ui/src/galaxy/pages/TsumegoHubPage.tsx` | Hub with Workbook + AI Solver cards |
| `katrain/web/ui/src/galaxy/pages/AiSolverPage.tsx` | Main AI solver page layout |
| `katrain/web/ui/src/galaxy/hooks/useAiSolverBoard.ts` | State management hook |
| `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverToolbar.tsx` | Tool button grid |
| `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverSidebar.tsx` | Right sidebar panel |
| `katrain/web/ui/src/galaxy/components/ai-solver/AiSolverBoard.tsx` | Board + rectangle overlay |

### Modified files (8)
| File | Change |
|------|--------|
| `katrain/web/api/v1/endpoints/analysis.py` | Add `/tsumego-solve` endpoint |
| `katrain/web/ui/src/api.ts` | Add `tsumegoSolve` API method |
| `katrain/web/ui/src/GalaxyApp.tsx` | Add hub route, workbook prefix, ai-solver route |
| `katrain/web/ui/src/galaxy/pages/TsumegoLevelsPage.tsx` | Update link → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoCategoriesPage.tsx` | Update link → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoUnitsPage.tsx` | Update nav links → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoListPage.tsx` | Update nav links → `/workbook/` |
| `katrain/web/ui/src/galaxy/pages/TsumegoProblemPage.tsx` | Update breadcrumb links → `/workbook/` |
