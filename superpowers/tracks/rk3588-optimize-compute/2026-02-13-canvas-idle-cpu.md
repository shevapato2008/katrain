# Canvas 空闲 CPU 优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate 60fps continuous canvas redraws when idle, reducing RK3588 Chromium CPU usage from ~620% to near-zero during idle.

**Architecture:** Replace `requestAnimationFrame` infinite loops in Board.tsx and LiveBoard.tsx with on-demand rendering. Canvas redraws only when (a) React state changes, (b) mouse hover changes, or (c) a pulsing animation is active (throttled to ~10fps via `setInterval`).

**Tech Stack:** React, TypeScript, Canvas 2D API

---

### Task 1: Board.tsx — Replace rAF loop with on-demand rendering

**Files:**
- Modify: `katrain/web/ui/src/components/Board.tsx:111-126` (animation loop)
- Modify: `katrain/web/ui/src/components/Board.tsx:509-516` (mouse handlers)

**Step 1: Replace the animation useEffect**

Replace lines 111-126:

```typescript
  // Add a ref for animation time
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  // Hover position for ghost stone preview
  const hoverPosRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const animate = () => {
      renderBoard();
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    animate();
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [gameState, analysisToggles, canvasSize]);
```

With:

```typescript
  // Add a ref for animation time
  const startTimeRef = useRef<number>(Date.now());
  // Hover position for ghost stone preview
  const hoverPosRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    renderBoard();

    // Only run animation when pulsing hints are visible (~10fps is enough for pulse)
    const needsAnimation = analysisToggles.hints && gameState?.analysis?.moves?.length > 0;
    if (needsAnimation) {
      const interval = setInterval(renderBoard, 100);
      return () => clearInterval(interval);
    }
  }, [gameState, analysisToggles, canvasSize]);
```

Key changes:
- Removed `animationFrameRef` (no longer needed)
- Kept `startTimeRef` (still used by pulse animation in `renderBoard`)
- Single `renderBoard()` call on state change
- `setInterval` at 100ms only when hints with moves are active

**Step 2: Add direct renderBoard calls to mouse handlers**

Replace lines 509-516:

```typescript
  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const pos = canvasToGridPos(event);
    hoverPosRef.current = pos;
  };

  const handleMouseLeave = () => {
    hoverPosRef.current = null;
  };
```

With:

```typescript
  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const pos = canvasToGridPos(event);
    hoverPosRef.current = pos;
    renderBoard();
  };

  const handleMouseLeave = () => {
    hoverPosRef.current = null;
    renderBoard();
  };
```

**Step 3: Build and verify compilation**

Run: `cd katrain/web/ui && npm run build`
Expected: Build succeeds with no TypeScript errors.

**Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board.tsx
git commit -m "perf(Board): replace 60fps rAF loop with on-demand canvas rendering

Render only when state changes or mouse moves. Pulse animation
throttled to ~10fps via setInterval when hints are active."
```

---

### Task 2: LiveBoard.tsx — Replace rAF loop with on-demand rendering

**Files:**
- Modify: `katrain/web/ui/src/galaxy/components/live/LiveBoard.tsx:318-321` (refs)
- Modify: `katrain/web/ui/src/galaxy/components/live/LiveBoard.tsx:584-599` (animation loop)
- Modify: `katrain/web/ui/src/galaxy/components/live/LiveBoard.tsx:610-631` (mouse handlers)

**Step 1: Remove animationFrameRef declaration**

Replace lines 318-321:

```typescript
  // Animation refs for pulsing effect
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  // Hover position for ghost stone preview
  const hoverPosRef = useRef<{ x: number; y: number } | null>(null);
```

With:

```typescript
  // Animation ref for pulsing effect timing
  const startTimeRef = useRef<number>(Date.now());
  // Hover position for ghost stone preview
  const hoverPosRef = useRef<{ x: number; y: number } | null>(null);
```

**Step 2: Replace the animation useEffect**

Replace lines 584-599:

```typescript
  // Animation loop for pulsing effect
  useEffect(() => {
    if (!imagesLoaded) return;

    const animate = () => {
      renderBoard();
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [moves, stoneColors, currentMove, boardSize, canvasSize, imagesLoaded, showCoordinates, pvMoves, aiMarkers, showAiMarkers, showMoveNumbers, showTerritory, ownership, tryMoves, nextColor]);
```

With:

```typescript
  // Render on state change; animate only when AI markers need pulsing
  useEffect(() => {
    if (!imagesLoaded) return;
    renderBoard();

    const needsAnimation = showAiMarkers && aiMarkers && aiMarkers.length > 0;
    if (needsAnimation) {
      const interval = setInterval(renderBoard, 100); // ~10fps for pulse
      return () => clearInterval(interval);
    }
  }, [moves, stoneColors, currentMove, boardSize, canvasSize, imagesLoaded, showCoordinates, pvMoves, aiMarkers, showAiMarkers, showMoveNumbers, showTerritory, ownership, tryMoves, nextColor]);
```

**Step 3: Add direct renderBoard calls to mouse handlers**

Replace lines 610-631:

```typescript
  // Handle mouse move for hover ghost stone
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !onIntersectionClick) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvasSize / rect.width;
    const scaleY = canvasSize / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;

    const layout = calculateBoardLayout(canvasSize, canvasSize, boardSize);
    const gridPos = canvasToGrid(layout, mx, my, boardSize);
    if (gridPos) {
      hoverPosRef.current = gridPos;
    } else {
      hoverPosRef.current = null;
    }
  };

  const handleMouseLeave = () => {
    hoverPosRef.current = null;
  };
```

With:

```typescript
  // Handle mouse move for hover ghost stone
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !onIntersectionClick) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvasSize / rect.width;
    const scaleY = canvasSize / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;

    const layout = calculateBoardLayout(canvasSize, canvasSize, boardSize);
    const gridPos = canvasToGrid(layout, mx, my, boardSize);
    if (gridPos) {
      hoverPosRef.current = gridPos;
    } else {
      hoverPosRef.current = null;
    }
    renderBoard();
  };

  const handleMouseLeave = () => {
    hoverPosRef.current = null;
    renderBoard();
  };
```

**Step 4: Build and verify compilation**

Run: `cd katrain/web/ui && npm run build`
Expected: Build succeeds with no TypeScript errors.

**Step 5: Commit**

```bash
git add katrain/web/ui/src/galaxy/components/live/LiveBoard.tsx
git commit -m "perf(LiveBoard): replace 60fps rAF loop with on-demand canvas rendering

Same optimization as Board.tsx: render only on state change or mouse
interaction. AI marker pulse throttled to ~10fps."
```

---

### Task 3: Backend tests — verify no regression

**Step 1: Run Python core tests**

Run: `CI=true python -m pytest tests/ --ignore=tests/web_ui -x -q`
Expected: All tests pass (58 passed, 5 skipped).

**Step 2: Production build**

Run: `cd katrain/web/ui && npm run build`
Expected: Build succeeds. Output in `katrain/web/static/`.

---

### Task 4: Manual smoke test

**Step 1: Start server locally**

Run: `python -m katrain --ui web --port 8001`

**Step 2: Verify in browser (DevTools → Performance tab)**

1. Open `http://127.0.0.1:8001`, start a game
2. Play a few moves, confirm board renders correctly
3. Wait for analysis to complete (board idle)
4. Open DevTools → Performance → Record 5 seconds while idle
   - **With hints OFF:** expect zero Canvas paint operations
   - **With hints ON:** expect ~10 paint ops/sec (not 60)
5. Hover mouse over board, confirm ghost stone preview appears immediately
6. Toggle hints on/off, confirm pulse animation starts/stops

**Step 3: Final commit (if any adjustments needed)**

```bash
git add -A
git commit -m "perf: canvas idle CPU optimization for RK3588 smart board"
```

---

## Expected Impact

| Scenario | Before | After |
|----------|--------|-------|
| Idle, hints OFF | 60fps redraw (~620% CPU on RK3588) | 0fps (no redraws) |
| Idle, hints ON | 60fps redraw | ~10fps redraw |
| Mouse hover | 60fps (always running) | On-demand (only on move) |
| State change | 60fps (already running) | Single immediate render |
