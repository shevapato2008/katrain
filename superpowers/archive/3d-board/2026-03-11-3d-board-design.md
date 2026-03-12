# 3D Board Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 3D Go board view to KaTrain's Galaxy Game Page, allowing users to toggle between the existing 2D Canvas board and a new Three.js-rendered 3D board with full analysis overlay support.

**Architecture:** New `Board3D` React component using React Three Fiber, sharing the exact same `BoardProps` interface as the existing `Board.tsx`. Game pages conditionally render `<Board3D>` or `<Board>` based on an `analysisToggles.view3d` flag. The 3D bundle is lazy-loaded via `lazy()` so 2D-only users pay zero download cost. No backend changes required.

**Tech Stack:** React Three Fiber (`@react-three/fiber`), drei (`@react-three/drei`), Three.js (`three`), TypeScript, Vite (rolldown-vite)

**TypeScript constraints:** `verbatimModuleSyntax: true` (must use `import type` for type-only imports), `noUnusedLocals: true`, `noUnusedParameters: true`, `jsx: react-jsx` (no need to import `React` for JSX).

---

## File Structure

```
katrain/web/ui/src/components/Board3D/
├── index.tsx              # R3F <Canvas>, scene composition, lazy export
├── constants.ts           # Board dimensions, stone sizes, colors shared across files
├── BoardMesh.tsx          # Wood board box + grid lines + star points + coordinates
├── Lights.tsx             # Ambient, directional, spot lighting
├── CameraController.tsx   # Vertical-only tilt + scroll zoom + reset
├── StoneMesh.tsx          # Single Hamaguri stone mesh (black or white)
├── StoneGroup.tsx         # Renders all stones from gameState.stones + drop animation
├── GhostStone.tsx         # Hover preview stone + ghost_stones (variations)
├── RaycastClick.tsx       # Invisible board plane + pointer events → onMove/onNavigate
├── Overlays/
│   ├── Territory.tsx      # Surface-projected ownership heatmap (flat planes)
│   ├── LastMove.tsx       # Glowing ring on last-played stone
│   ├── EvalDots.tsx       # Colored discs on stone tops (blunder→excellent)
│   ├── BestMoves.tsx      # Surface circles + billboard text (winrate/visits)
│   └── PolicyMap.tsx      # Surface circles + text for policy heatmap
└── __tests__/
    └── constants.test.ts  # Unit tests for coordinate conversion & color logic
```

**Modified files:**
- `katrain/web/ui/package.json` — add three, @react-three/fiber, @react-three/drei, @types/three
- `katrain/web/ui/src/components/Board.tsx` — export `BoardProps` interface for sharing
- `katrain/web/ui/src/galaxy/pages/GamePage.tsx` — conditional Board/Board3D render
- `katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx` — conditional Board/Board3D render
- `katrain/web/ui/src/galaxy/components/game/RightSidebarPanel.tsx` — add 3D toggle button

---

## Chunk 1: Foundation (Tasks 1–5)

### Task 1: Install R3F Dependencies

**Files:**
- Modify: `katrain/web/ui/package.json`

- [ ] **Step 1: Install packages**

```bash
cd katrain/web/ui && npm install three @react-three/fiber @react-three/drei && npm install -D @types/three
```

- [ ] **Step 2: Verify installation**

```bash
cd katrain/web/ui && node -e "require('three'); require('@react-three/fiber'); console.log('OK')"
```

Expected: `OK` (no errors)

- [ ] **Step 3: Commit**

```bash
git add katrain/web/ui/package.json katrain/web/ui/package-lock.json
git commit -m "feat(3d): add three.js, react-three-fiber, and drei dependencies"
```

---

### Task 2: Constants & Coordinate Utilities

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/constants.ts`
- Create: `katrain/web/ui/src/components/Board3D/__tests__/constants.test.ts`

- [ ] **Step 1: Write coordinate conversion tests**

```typescript
// katrain/web/ui/src/components/Board3D/__tests__/constants.test.ts
import { describe, it, expect } from 'vitest';
import {
  gridToWorld,
  worldToGrid,
  getBoardDimensions,
  getEvalColor,
  EVAL_COLORS,
  SURFACE_EPSILON,
  BOARD_SURFACE_Y,
} from '../constants';

describe('getBoardDimensions', () => {
  it('calculates correct dimensions for 19x19', () => {
    const dims = getBoardDimensions(19);
    expect(dims.boardSize).toBe(19);
    expect(dims.gridSpacing).toBe(1.0);
    expect(dims.boardExtent).toBe(18.0);
    expect(dims.boardWidth).toBeCloseTo(19.6);
  });

  it('calculates correct dimensions for 9x9', () => {
    const dims = getBoardDimensions(9);
    expect(dims.boardSize).toBe(9);
    expect(dims.boardExtent).toBe(8.0);
  });

  it('calculates correct dimensions for 13x13', () => {
    const dims = getBoardDimensions(13);
    expect(dims.boardSize).toBe(13);
    expect(dims.boardExtent).toBe(12.0);
  });
});

describe('gridToWorld', () => {
  it('converts grid (0,0) to correct world position for 19x19', () => {
    const pos = gridToWorld(0, 0, 19);
    // col=0 → x = -9, row=0 → z = +9 (near camera, Z inverted)
    expect(pos[0]).toBeCloseTo(-9);
    expect(pos[2]).toBeCloseTo(9);
    expect(pos[1]).toBeCloseTo(1.20 + 0.22);
  });

  it('converts grid center to origin for 19x19', () => {
    const pos = gridToWorld(9, 9, 19);
    expect(pos[0]).toBeCloseTo(0);
    expect(pos[2]).toBeCloseTo(0);
  });

  it('converts grid (18,18) to far corner for 19x19', () => {
    const pos = gridToWorld(18, 18, 19);
    // col=18 → x = +9, row=18 → z = -9 (far from camera)
    expect(pos[0]).toBeCloseTo(9);
    expect(pos[2]).toBeCloseTo(-9);
  });

  it('works for 9x9 board', () => {
    const pos = gridToWorld(4, 4, 9);
    expect(pos[0]).toBeCloseTo(0);
    expect(pos[2]).toBeCloseTo(0);
  });
});

describe('worldToGrid', () => {
  it('round-trips with gridToWorld for 19x19', () => {
    // gridToWorld(col, row) -> worldToGrid returns { col, row }
    for (const [col, row] of [[0, 0], [3, 3], [9, 9], [15, 15], [18, 18]]) {
      const world = gridToWorld(col, row, 19);
      const grid = worldToGrid(world[0], world[2], 19);
      expect(grid).toEqual({ col, row });
    }
  });

  it('returns null for out-of-bounds positions', () => {
    expect(worldToGrid(-20, -20, 19)).toBeNull();
    expect(worldToGrid(20, 20, 19)).toBeNull();
  });
});

describe('getEvalColor', () => {
  it('returns purple (index 0) for blunders (>12)', () => {
    expect(getEvalColor(15)).toBe(EVAL_COLORS[0]);
  });

  it('returns jade green (index 5) for excellent (<=0.5)', () => {
    expect(getEvalColor(0.2)).toBe(EVAL_COLORS[5]);
  });

  it('returns yellow (index 3) for inaccuracy (>1.5)', () => {
    expect(getEvalColor(2.0)).toBe(EVAL_COLORS[3]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd katrain/web/ui && npx vitest run src/components/Board3D/__tests__/constants.test.ts
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement constants.ts**

```typescript
// katrain/web/ui/src/components/Board3D/constants.ts

// ===== Board Geometry =====
// BOARD_SURFACE_Y equals boardHeight: slab goes from y=0 to y=boardHeight

const GRID_SPACING = 1.0;
const BOARD_PADDING = 0.8;
export const STONE_RADIUS = 0.42;
export const STONE_HEIGHT = 0.22;
export const BOARD_SURFACE_Y = 1.20;
export const DROP_HEIGHT = 5;

// ===== Z-offset constants (prevent z-fighting) =====
export const SURFACE_EPSILON = 0.005;   // Flat overlays sitting on the board surface
export const OVERLAY_OFFSET = 0.01;     // Elements slightly above board (click plane, text)
export const ABOVE_STONE = 0.005;       // Markers on top of stones (LastMove ring, EvalDots)

export interface BoardDimensions {
  boardSize: number;
  gridSpacing: number;
  boardExtent: number;
  boardWidth: number;
  boardHeight: number;
}

export function getBoardDimensions(boardSize: number): BoardDimensions {
  const boardExtent = (boardSize - 1) * GRID_SPACING;
  const boardWidth = boardExtent + BOARD_PADDING * 2;
  return {
    boardSize,
    gridSpacing: GRID_SPACING,
    boardExtent,
    boardWidth,
    boardHeight: 1.2,
  };
}

/**
 * Convert grid (col, row) to 3D world [x, y, z].
 * col → x axis, row → z axis (inverted so row=0 is near camera), y = board surface + stone height.
 * col maps to GameState x, row maps to GameState y.
 *
 * Z is inverted vs X: row=0 maps to +z (near camera at positive z),
 * matching the 2D Board.tsx where row=0 is drawn at the bottom (near player).
 */
export function gridToWorld(col: number, row: number, boardSize: number): [number, number, number] {
  const extent = (boardSize - 1) * GRID_SPACING;
  const halfExtent = extent / 2;
  return [
    -halfExtent + col * GRID_SPACING,
    BOARD_SURFACE_Y + STONE_HEIGHT,
    halfExtent - row * GRID_SPACING,
  ];
}

/**
 * Convert world (x, z) to grid {col, row}, or null if out of bounds.
 * Z is inverted: positive z maps to row=0, negative z maps to row=boardSize-1.
 */
export function worldToGrid(worldX: number, worldZ: number, boardSize: number): { col: number; row: number } | null {
  const extent = (boardSize - 1) * GRID_SPACING;
  const halfExtent = extent / 2;
  const col = Math.round((worldX + halfExtent) / GRID_SPACING);
  const row = Math.round((halfExtent - worldZ) / GRID_SPACING);
  if (col >= 0 && col < boardSize && row >= 0 && row < boardSize) {
    return { col, row };
  }
  return null;
}

/**
 * Grid position on the board surface (y = BOARD_SURFACE_Y + SURFACE_EPSILON).
 * Used for flat overlays that sit on the board, not on stones.
 * Z is inverted to match gridToWorld orientation.
 */
export function gridToSurface(col: number, row: number, boardSize: number): [number, number, number] {
  const extent = (boardSize - 1) * GRID_SPACING;
  const halfExtent = extent / 2;
  return [
    -halfExtent + col * GRID_SPACING,
    BOARD_SURFACE_Y + SURFACE_EPSILON,
    halfExtent - row * GRID_SPACING,
  ];
}

// ===== Eval Colors (matches Board.tsx EVAL_COLORS) =====

export const EVAL_COLORS = [
  '#964196', // Purple - blunder (>12)
  '#e16b5c', // Red - big mistake (>6)
  '#d4a574', // Warm orange - mistake (>3)
  '#e8c864', // Yellow - inaccuracy (>1.5)
  '#abc864', // Light green - ok (>0.5)
  '#4a6b5c', // Jade green - excellent (<=0.5)
] as const;

export const EVAL_THRESHOLDS = [12, 6, 3, 1.5, 0.5, 0] as const;

export function getEvalColor(scoreLoss: number): string {
  for (let i = 0; i < EVAL_THRESHOLDS.length; i++) {
    if (scoreLoss >= EVAL_THRESHOLDS[i]) return EVAL_COLORS[i];
  }
  return EVAL_COLORS[5];
}

// ===== Star Points =====

export function getStarPoints(boardSize: number): [number, number][] {
  const stars =
    boardSize === 19 ? [3, 9, 15] :
    boardSize === 13 ? [3, 6, 9] :
    boardSize === 9 ? [2, 4, 6] : [];
  const points: [number, number][] = [];
  for (const x of stars) {
    for (const y of stars) {
      points.push([x, y]);
    }
  }
  return points;
}

// ===== Coordinate Labels =====

const LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';

export function getColumnLabel(col: number): string {
  return LETTERS[col] || '';
}

export function getRowLabel(row: number): string {
  return (row + 1).toString();
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd katrain/web/ui && npx vitest run src/components/Board3D/__tests__/constants.test.ts
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/constants.ts katrain/web/ui/src/components/Board3D/__tests__/constants.test.ts
git commit -m "feat(3d): add board dimension constants and coordinate conversion utilities"
```

---

### Task 3: Board3D Scaffold + Lights

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/Lights.tsx`
- Create: `katrain/web/ui/src/components/Board3D/index.tsx`
- Modify: `katrain/web/ui/src/components/Board.tsx` — export `BoardProps`

- [ ] **Step 1: Export BoardProps from Board.tsx**

In `katrain/web/ui/src/components/Board.tsx`, change the interface declaration from:

```typescript
interface BoardProps {
```

to:

```typescript
export interface BoardProps {
```

This allows Board3D to import the shared interface.

- [ ] **Step 2: Create Lights.tsx**

Port the lighting setup from the prototype (`go-board-3d.html:478-525`).

```typescript
// katrain/web/ui/src/components/Board3D/Lights.tsx
import { memo } from 'react';

/**
 * Scene lighting: warm ambient + hemisphere + directional key/fill/rim + spot.
 * Ported from go-board-3d.html setupLights().
 */
const Lights = () => {
  return (
    <>
      <ambientLight color={0xffecd2} intensity={0.5} />
      <hemisphereLight args={[0xfff8f0, 0x8b7355, 0.3]} />
      <directionalLight
        color={0xfff4e0}
        intensity={1.0}
        position={[10, 18, 12]}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={1}
        shadow-camera-far={50}
        shadow-camera-left={-16}
        shadow-camera-right={16}
        shadow-camera-top={16}
        shadow-camera-bottom={-16}
        shadow-bias={-0.0005}
        shadow-normalBias={0.02}
      />
      <directionalLight color={0xd4e0ff} intensity={0.35} position={[-8, 10, -4]} />
      <directionalLight color={0xffc87c} intensity={0.25} position={[-2, 5, -14]} />
      <spotLight
        color={0xfff8f0}
        intensity={0.4}
        position={[0, 20, 0]}
        angle={Math.PI / 6}
        penumbra={0.5}
        decay={1}
        distance={35}
      />
      <pointLight color={0xffe8c8} intensity={0.2} distance={20} position={[0, 3, 14]} />
    </>
  );
};

export default memo(Lights);
```

- [ ] **Step 3: Create Board3D/index.tsx scaffold**

Minimal R3F Canvas with lights only. Imports `BoardProps` from the shared Board.tsx.

```typescript
// katrain/web/ui/src/components/Board3D/index.tsx
import { memo } from 'react';
import { Canvas } from '@react-three/fiber';
import { ACESFilmicToneMapping } from 'three';
import Lights from './Lights';
import type { BoardProps } from '../Board';

const Board3D = ({ gameState, onMove, onNavigate, analysisToggles, playerColor }: BoardProps) => {
  const boardSize = gameState.board_size[0];

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <Canvas
        shadows
        camera={{ position: [0, 20, 22], fov: 35, near: 0.1, far: 100 }}
        gl={{ antialias: true, toneMapping: ACESFilmicToneMapping, toneMappingExposure: 1.2 }}
        style={{ borderRadius: '4px', cursor: 'pointer' }}
      >
        <color attach="background" args={['#0f0f0f']} />
        <fog attach="fog" args={['#0f0f0f', 30, 60]} />
        <Lights />
      </Canvas>

      {/* End-game result overlay (HTML layer on top of Canvas) */}
      {gameState.end_result && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0, 0, 0, 0.6)',
          borderRadius: '4px', pointerEvents: 'none',
        }}>
          <span style={{ color: '#fff', fontSize: '2rem', fontWeight: 'bold', textAlign: 'center' }}>
            {gameState.end_result}
          </span>
        </div>
      )}
    </div>
  );
};

export default memo(Board3D);
```

Note: `useState`, `useCallback` are not imported at this step — they will be added in Task 8 when we wire RaycastClick hover state. Only import what's needed at each step to satisfy `noUnusedLocals`.

- [ ] **Step 4: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

Expected: No type errors. If unused import warnings appear, remove the offending imports and keep only what's needed at this step.

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/components/Board.tsx katrain/web/ui/src/components/Board3D/index.tsx katrain/web/ui/src/components/Board3D/Lights.tsx
git commit -m "feat(3d): scaffold Board3D component with R3F canvas and lighting"
```

---

### Task 4: BoardMesh (Wood Board + Grid + Stars + Coordinates)

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/BoardMesh.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create BoardMesh.tsx**

Port board geometry from prototype. Uses `<lineSegments>` with a single `BufferGeometry` for grid lines (1 draw call for entire grid). Coordinates use drei `<Text>` with default font (no external font file needed). Textures and materials are created in `useMemo` and cleaned up via `useEffect` to prevent GPU memory leaks.

```typescript
// katrain/web/ui/src/components/Board3D/BoardMesh.tsx
import { useMemo, useEffect, useRef, memo } from 'react';
import * as THREE from 'three';
import { Text } from '@react-three/drei';
import {
  getBoardDimensions,
  getStarPoints,
  getColumnLabel,
  getRowLabel,
  BOARD_SURFACE_Y,
  SURFACE_EPSILON,
} from './constants';

interface BoardMeshProps {
  boardSize: number;
  showCoordinates: boolean;
}

/** Procedural wood-grain canvas texture. Ported from go-board-3d.html. */
function createWoodTexture(
  width: number, height: number,
  baseColor: string, grainColor: [number, number, number], grainCount: number,
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = baseColor;
  ctx.fillRect(0, 0, width, height);

  for (let i = 0; i < 12; i++) {
    const y = Math.random() * height;
    const bandH = 20 + Math.random() * 60;
    const grad = ctx.createLinearGradient(0, y, 0, y + bandH);
    grad.addColorStop(0, 'rgba(180, 140, 70, 0)');
    grad.addColorStop(0.5, `rgba(180, 140, 70, ${0.05 + Math.random() * 0.08})`);
    grad.addColorStop(1, 'rgba(180, 140, 70, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, y, width, bandH);
  }

  for (let i = 0; i < grainCount; i++) {
    const y = Math.random() * height;
    const alpha = 0.04 + Math.random() * 0.1;
    ctx.strokeStyle = `rgba(${grainColor[0]}, ${grainColor[1]}, ${grainColor[2]}, ${alpha})`;
    ctx.lineWidth = 0.5 + Math.random() * 2.5;
    ctx.beginPath();
    ctx.moveTo(0, y);
    const freq = 0.01 + Math.random() * 0.03;
    const amp = 3 + Math.random() * 12;
    for (let x = 0; x < width; x += 8) {
      ctx.lineTo(x, y + Math.sin(x * freq) * amp + Math.sin(x * 0.005) * 6 + (Math.random() - 0.5) * 2);
    }
    ctx.stroke();
  }

  for (let i = 0; i < grainCount / 3; i++) {
    const y = Math.random() * height;
    ctx.strokeStyle = `rgba(100, 60, 20, ${0.03 + Math.random() * 0.05})`;
    ctx.lineWidth = 2 + Math.random() * 4;
    ctx.beginPath();
    ctx.moveTo(0, y);
    for (let x = 0; x < width; x += 15) {
      ctx.lineTo(x, y + Math.sin(x * 0.015) * 10 + (Math.random() - 0.5) * 3);
    }
    ctx.stroke();
  }

  const imgData = ctx.getImageData(0, 0, width, height);
  const pixels = imgData.data;
  const noiseCount = width * height * 0.3;
  for (let i = 0; i < noiseCount; i++) {
    const idx = Math.floor(Math.random() * width * height) * 4;
    const noise = (Math.random() - 0.5) * 18;
    pixels[idx] = Math.max(0, Math.min(255, pixels[idx] + noise));
    pixels[idx + 1] = Math.max(0, Math.min(255, pixels[idx + 1] + noise));
    pixels[idx + 2] = Math.max(0, Math.min(255, pixels[idx + 2] + noise * 0.5));
  }
  ctx.putImageData(imgData, 0, 0);

  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

const BoardMesh = ({ boardSize, showCoordinates }: BoardMeshProps) => {
  const dims = useMemo(() => getBoardDimensions(boardSize), [boardSize]);
  const starPoints = useMemo(() => getStarPoints(boardSize), [boardSize]);
  const halfExtent = dims.boardExtent / 2;

  // Textures with cleanup
  const texturesRef = useRef<THREE.CanvasTexture[]>([]);
  const materialsRef = useRef<THREE.Material[]>([]);

  const { materials } = useMemo(() => {
    const topTex = createWoodTexture(1024, 1024, '#DBA85A', [120, 75, 30], 150);
    const sideTex = createWoodTexture(1024, 256, '#C89848', [110, 70, 28], 120);

    const topMat = new THREE.MeshStandardMaterial({
      map: topTex, roughness: 0.4, metalness: 0.02, color: 0xdba85a,
    });
    const sideMat = new THREE.MeshStandardMaterial({
      map: sideTex, roughness: 0.5, metalness: 0.03, color: 0xc89848,
    });
    const bottomMat = new THREE.MeshStandardMaterial({
      color: 0xb08040, roughness: 0.7, metalness: 0.02,
    });

    texturesRef.current = [topTex, sideTex];
    materialsRef.current = [topMat, sideMat, bottomMat];

    // BoxGeometry face order: +x, -x, +y, -y, +z, -z
    return { materials: [sideMat, sideMat, topMat, bottomMat, sideMat, sideMat] };
  }, [boardSize]);

  // Cleanup on boardSize change and unmount (dispose is a side effect → useEffect, not useMemo)
  useEffect(() => {
    return () => {
      texturesRef.current.forEach(t => t.dispose());
      materialsRef.current.forEach(m => m.dispose());
    };
  }, [boardSize]);

  // Grid lines as a single LineSegments geometry (1 draw call instead of 38)
  const gridGeometry = useMemo(() => {
    const lineY = BOARD_SURFACE_Y + SURFACE_EPSILON;
    const vertices: number[] = [];

    for (let i = 0; i < boardSize; i++) {
      const pos = -halfExtent + i * dims.gridSpacing;
      // Vertical line (pair of endpoints)
      vertices.push(pos, lineY, -halfExtent, pos, lineY, halfExtent);
      // Horizontal line
      vertices.push(-halfExtent, lineY, pos, halfExtent, lineY, pos);
    }
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    return geom;
  }, [boardSize, dims, halfExtent]);

  useEffect(() => {
    return () => { gridGeometry.dispose(); };
  }, [gridGeometry]);

  // Coordinate label data
  const coordLabels = useMemo(() => {
    if (!showCoordinates) return [];
    const labelOffset = 0.75; // within board padding (0.8)
    const labelY = BOARD_SURFACE_Y + SURFACE_EPSILON;
    const labels: { text: string; position: [number, number, number] }[] = [];

    for (let i = 0; i < boardSize; i++) {
      const pos = -halfExtent + i * dims.gridSpacing;
      labels.push({ text: getColumnLabel(i), position: [pos, labelY, halfExtent + labelOffset] });
      labels.push({ text: getColumnLabel(i), position: [pos, labelY, -halfExtent - labelOffset] });
      labels.push({ text: getRowLabel(i), position: [-halfExtent - labelOffset, labelY, pos] });
      labels.push({ text: getRowLabel(i), position: [halfExtent + labelOffset, labelY, pos] });
    }
    return labels;
  }, [boardSize, dims, halfExtent, showCoordinates]);

  return (
    <group>
      {/* Board slab */}
      <mesh
        position={[0, dims.boardHeight / 2, 0]}
        material={materials}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[dims.boardWidth, dims.boardHeight, dims.boardWidth]} />
      </mesh>

      {/* Grid lines — single LineSegments for efficiency (1 draw call) */}
      <lineSegments geometry={gridGeometry}>
        <lineBasicMaterial color="black" transparent opacity={0.7} />
      </lineSegments>

      {/* Star points */}
      {starPoints.map(([col, row], i) => {
        const x = -halfExtent + col * dims.gridSpacing;
        const z = -halfExtent + row * dims.gridSpacing;
        return (
          <mesh key={`star-${i}`} position={[x, BOARD_SURFACE_Y + SURFACE_EPSILON, z]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.08, 16]} />
            <meshBasicMaterial color="black" opacity={0.85} transparent />
          </mesh>
        );
      })}

      {/* Coordinate labels — drei <Text> with default font */}
      {coordLabels.map((label, i) => (
        <Text
          key={`coord-${i}`}
          position={label.position}
          rotation={[-Math.PI / 2, 0, 0]}
          fontSize={0.35}
          color="rgba(0,0,0,0.65)"
          anchorX="center"
          anchorY="middle"
        >
          {label.text}
        </Text>
      ))}
    </group>
  );
};

export default memo(BoardMesh);
```

- [ ] **Step 2: Wire BoardMesh into index.tsx**

In `Board3D/index.tsx`, add import and render inside `<Canvas>`:

```typescript
import BoardMesh from './BoardMesh';

// Inside <Canvas>, after <Lights />:
<BoardMesh boardSize={boardSize} showCoordinates={!!analysisToggles.coords} />
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/BoardMesh.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add wood board mesh with grid lines, star points, and coordinates"
```

---

### Task 5: CameraController (Vertical Tilt + Zoom)

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/CameraController.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create CameraController.tsx**

Constrains OrbitControls to vertical tilt only. Azimuth locked to 0 (no horizontal rotation). Uses `MOUSE` enum from three for proper type safety.

```typescript
// katrain/web/ui/src/components/Board3D/CameraController.tsx
import { memo } from 'react';
import { OrbitControls } from '@react-three/drei';
import { MOUSE } from 'three';
import { BOARD_SURFACE_Y } from './constants';

const CameraController = () => {
  return (
    <OrbitControls
      target={[0, BOARD_SURFACE_Y, 0]}
      enableDamping
      dampingFactor={0.08}
      minDistance={10}
      maxDistance={40}
      minPolarAngle={Math.PI * 0.05}
      maxPolarAngle={Math.PI * 0.38}
      minAzimuthAngle={0}
      maxAzimuthAngle={0}
      enablePan={false}
      mouseButtons={{
        LEFT: MOUSE.ROTATE,
        MIDDLE: MOUSE.DOLLY,
      }}
    />
  );
};

export default memo(CameraController);
```

- [ ] **Step 2: Wire into index.tsx**

```typescript
import CameraController from './CameraController';

// Inside <Canvas>, after <Lights />:
<CameraController />
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/CameraController.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add vertical-only camera controller with zoom"
```

---

## Chunk 2: Stones & Interaction (Tasks 6–9)

### Task 6: StoneMesh

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/StoneMesh.tsx`

- [ ] **Step 1: Create StoneMesh.tsx**

Port Hamaguri stone from prototype. Black: glossy dark sphere. White: shell-textured. Geometry is shared at module level (not per-stone). Materials are cleaned up on unmount. Stones use `raycast={() => {}}` (noop) so they don't block pointer events from reaching the click plane.

```typescript
// katrain/web/ui/src/components/Board3D/StoneMesh.tsx
import { useMemo, useEffect, memo, forwardRef } from 'react';
import * as THREE from 'three';
import type { Mesh } from 'three';
import { STONE_RADIUS, STONE_HEIGHT } from './constants';

interface StoneMeshProps {
  color: 'B' | 'W';
  position: [number, number, number];
  opacity?: number;
  scale?: number;
}

// Shared geometry — all stones use the same sphere (1 geometry, not 361)
const sharedGeometry = new THREE.SphereGeometry(STONE_RADIUS, 48, 32);

// Noop raycast — prevents stones from intercepting pointer events
const noopRaycast = () => {};

/** Shell texture for Hamaguri white stones. Cached at module level. */
let cachedShellTexture: THREE.CanvasTexture | null = null;

function getShellTexture(): THREE.CanvasTexture {
  if (cachedShellTexture) return cachedShellTexture;
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#f5edd8';
  ctx.fillRect(0, 0, size, size);

  const cx = size * 0.48, cy = size * 0.7;
  for (let i = 0; i < 40; i++) {
    const r = 6 + i * (size * 0.024);
    const dark = i % 2 === 0;
    ctx.strokeStyle = dark
      ? `rgba(110, 80, 30, ${0.7 + Math.random() * 0.3})`
      : `rgba(150, 120, 60, ${0.5 + Math.random() * 0.3})`;
    ctx.lineWidth = dark ? 3 + Math.random() * 3 : 1.5 + Math.random() * 2;
    ctx.beginPath();
    ctx.arc(cx + (Math.random() - 0.5) * 4, cy + (Math.random() - 0.5) * 3, r, Math.PI * 0.08, Math.PI * 0.92);
    ctx.stroke();
  }

  const cx2 = size * 0.55, cy2 = size * 0.75;
  for (let i = 0; i < 15; i++) {
    const r = 10 + i * (size * 0.035);
    ctx.strokeStyle = `rgba(130, 100, 45, ${0.2 + Math.random() * 0.2})`;
    ctx.lineWidth = 1 + Math.random() * 1.5;
    ctx.beginPath();
    ctx.arc(cx2, cy2, r, Math.PI * 0.15, Math.PI * 0.85);
    ctx.stroke();
  }

  const g = ctx.createRadialGradient(size * 0.38, size * 0.3, size * 0.02, size * 0.45, size * 0.4, size * 0.2);
  g.addColorStop(0, 'rgba(255, 252, 240, 0.35)');
  g.addColorStop(1, 'rgba(255, 252, 240, 0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);

  cachedShellTexture = new THREE.CanvasTexture(canvas);
  return cachedShellTexture;
}

const StoneMesh = forwardRef<Mesh, StoneMeshProps>(({ color, position, opacity = 1, scale = 1 }, ref) => {
  const material = useMemo(() => {
    if (color === 'B') {
      return new THREE.MeshStandardMaterial({
        color: 0x0a0a0a, roughness: 0.06, metalness: 0.15,
        transparent: opacity < 1, opacity,
      });
    } else {
      return new THREE.MeshStandardMaterial({
        map: getShellTexture(), color: 0xf5edd8, roughness: 0.1, metalness: 0.04,
        transparent: opacity < 1, opacity,
      });
    }
  }, [color, opacity]);

  // Dispose material on change/unmount (but NOT the shared shell texture)
  useEffect(() => {
    return () => { material.dispose(); };
  }, [material]);

  const scaleY = STONE_HEIGHT / STONE_RADIUS;

  return (
    <mesh
      ref={ref}
      position={position}
      scale={[scale, scale * scaleY, scale]}
      geometry={sharedGeometry}
      material={material}
      castShadow
      receiveShadow
      raycast={noopRaycast}
    />
  );
});

StoneMesh.displayName = 'StoneMesh';
export default memo(StoneMesh);
```

- [ ] **Step 2: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/StoneMesh.tsx
git commit -m "feat(3d): add Hamaguri stone mesh component"
```

---

### Task 7: StoneGroup + DropAnimation

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/StoneGroup.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create StoneGroup.tsx**

Renders all stones from `gameState.stones`. Includes built-in drop animation for new moves only.

**New-move detection:** Compares `last_move` coordinates (not stone count, which fails on captures where total stones decrease). Only triggers animation when `current_node_index` increases AND the `last_move` coordinate changes to a new position.

**Animation approach:** The animating stone uses a dedicated `<mesh>` with a ref. `useFrame` directly mutates `meshRef.current.position.y` and `meshRef.current.scale` — this bypasses React's render cycle, which is the correct R3F pattern for per-frame updates. All other stones render normally via React.

```typescript
// katrain/web/ui/src/components/Board3D/StoneGroup.tsx
import { useRef, useEffect, memo } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Mesh } from 'three';
import StoneMesh from './StoneMesh';
import { gridToWorld, DROP_HEIGHT, STONE_HEIGHT } from './constants';
import type { GameState } from '../../api';

interface StoneGroupProps {
  gameState: GameState;
}

interface DropAnim {
  yOffset: number;
  velocity: number;
  scaleFactor: number;
  done: boolean;
  targetY: number;
}

const StoneGroup = ({ gameState }: StoneGroupProps) => {
  const boardSize = gameState.board_size[0];
  const prevNodeIndexRef = useRef(gameState.current_node_index);
  const prevLastMoveRef = useRef<[number, number] | null>(gameState.last_move);
  const animRef = useRef<DropAnim | null>(null);
  const animMeshRef = useRef<Mesh>(null);

  // Detect new move vs navigation
  // Uses last_move comparison instead of stone count (captures reduce stone count)
  useEffect(() => {
    const prevLastMove = prevLastMoveRef.current;
    const currLastMove = gameState.last_move;

    const isNewMove =
      gameState.current_node_index > prevNodeIndexRef.current &&
      currLastMove != null &&
      (prevLastMove == null ||
        currLastMove[0] !== prevLastMove[0] ||
        currLastMove[1] !== prevLastMove[1]);

    if (isNewMove && currLastMove) {
      const targetPos = gridToWorld(currLastMove[0], currLastMove[1], boardSize);
      animRef.current = {
        yOffset: DROP_HEIGHT,
        velocity: 0,
        scaleFactor: 0.5,
        done: false,
        targetY: targetPos[1],
      };
    } else {
      animRef.current = null;
    }

    prevNodeIndexRef.current = gameState.current_node_index;
    prevLastMoveRef.current = currLastMove;
  }, [gameState.current_node_index, gameState.last_move, boardSize]);

  // Animate the drop each frame — directly mutates mesh ref (correct R3F pattern)
  useFrame((_, delta) => {
    const anim = animRef.current;
    const mesh = animMeshRef.current;
    if (!anim || anim.done || !mesh) return;

    const dt = Math.min(delta, 0.05);
    anim.velocity += 40 * dt;
    anim.yOffset -= anim.velocity * dt;

    if (anim.scaleFactor < 1) {
      anim.scaleFactor = Math.min(1, anim.scaleFactor + dt * 3);
    }

    if (anim.yOffset <= 0) {
      anim.yOffset = 0;
      anim.scaleFactor = 1;
      anim.done = true;
    }

    // Directly mutate mesh transform (bypasses React render — correct for useFrame)
    mesh.position.y = anim.targetY + anim.yOffset;
    const scaleY = (STONE_HEIGHT / 0.42) * anim.scaleFactor; // 0.42 = STONE_RADIUS
    mesh.scale.set(anim.scaleFactor, scaleY, anim.scaleFactor);
  });

  // Find the animating stone's coords (if any)
  const animCoords = !animRef.current?.done && gameState.last_move ? gameState.last_move : null;

  return (
    <group>
      {gameState.stones.map(([player, coords], index) => {
        if (!coords) return null;
        const [x, y] = coords;

        // Skip the animating stone — it's rendered separately with a mesh ref
        if (animCoords && x === animCoords[0] && y === animCoords[1] && !animRef.current?.done) {
          return null;
        }

        const basePos = gridToWorld(x, y, boardSize);
        return (
          <StoneMesh
            key={`stone-${x}-${y}-${index}`}
            color={player as 'B' | 'W'}
            position={basePos}
          />
        );
      })}

      {/* Animating stone — uses mesh ref for direct useFrame mutation */}
      {animCoords && !animRef.current?.done && (() => {
        const animStone = gameState.stones.find(
          s => s[1] && s[1][0] === animCoords[0] && s[1][1] === animCoords[1]
        );
        if (!animStone || !animStone[1]) return null;
        const basePos = gridToWorld(animStone[1][0], animStone[1][1], boardSize);
        return (
          <StoneMesh
            key="animating-stone"
            ref={animMeshRef}
            color={animStone[0] as 'B' | 'W'}
            position={[basePos[0], basePos[1] + DROP_HEIGHT, basePos[2]]}
            scale={0.5}
          />
        );
      })()}
    </group>
  );
};

export default memo(StoneGroup);
```

> **Note:** `StoneMesh` already uses `forwardRef` (updated in Task 6) so the ref is forwarded to the underlying `<mesh>`. No additional changes needed.

- [ ] **Step 2: Wire into index.tsx**

```typescript
import StoneGroup from './StoneGroup';

// Inside <Canvas>, after <BoardMesh ... />:
<StoneGroup gameState={gameState} />
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/StoneGroup.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add stone group renderer with drop animation"
```

---

### Task 8: RaycastClick (Mouse → Grid → onMove/onNavigate)

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/RaycastClick.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create RaycastClick.tsx**

Invisible plane at board surface. Pointer events convert world position to grid, then call `onMove` or `onNavigate`. Stone meshes have `raycast={noopRaycast}` (set in StoneMesh), so clicks pass through to this plane even when clicking on occupied intersections.

```typescript
// katrain/web/ui/src/components/Board3D/RaycastClick.tsx
import { useCallback, memo } from 'react';
import type { ThreeEvent } from '@react-three/fiber';
import { getBoardDimensions, worldToGrid, BOARD_SURFACE_Y, OVERLAY_OFFSET } from './constants';
import type { GameState } from '../../api';

interface RaycastClickProps {
  gameState: GameState;
  onMove: (x: number, y: number) => void;
  onNavigate?: (nodeId: number) => void;
  playerColor?: 'B' | 'W' | null;
  onHover: (pos: { col: number; row: number } | null) => void;
}

const RaycastClick = ({
  gameState, onMove, onNavigate, playerColor, onHover,
}: RaycastClickProps) => {
  const boardSize = gameState.board_size[0];
  const dims = getBoardDimensions(boardSize);

  const handleClick = useCallback((event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    if (gameState.end_result) return;
    if (playerColor && gameState.player_to_move !== playerColor) return;

    const grid = worldToGrid(event.point.x, event.point.z, boardSize);
    if (!grid) return;

    const { col, row } = grid;

    // Check for existing stone → navigate to that move
    const clickedStone = gameState.stones.find(
      s => s[1] && s[1][0] === col && s[1][1] === row
    );

    if (clickedStone && onNavigate) {
      const moveNumber = clickedStone[3];
      if (moveNumber != null && moveNumber >= 0 && moveNumber < gameState.history.length) {
        onNavigate(gameState.history[moveNumber].node_id);
      }
    } else if (!clickedStone) {
      onMove(col, row);
    }
  }, [gameState.end_result, gameState.player_to_move, gameState.stones, gameState.history, boardSize, onMove, onNavigate, playerColor]);

  const handlePointerMove = useCallback((event: ThreeEvent<PointerEvent>) => {
    const grid = worldToGrid(event.point.x, event.point.z, boardSize);
    onHover(grid ? { col: grid.col, row: grid.row } : null);
  }, [boardSize, onHover]);

  const handlePointerLeave = useCallback(() => {
    onHover(null);
  }, [onHover]);

  return (
    <mesh
      position={[0, BOARD_SURFACE_Y + OVERLAY_OFFSET, 0]}
      rotation={[-Math.PI / 2, 0, 0]}
      onClick={handleClick}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <planeGeometry args={[dims.boardWidth, dims.boardWidth]} />
      <meshBasicMaterial visible={false} />
    </mesh>
  );
};

export default memo(RaycastClick);
```

- [ ] **Step 2: Wire into index.tsx with hover state**

Update `Board3D/index.tsx` — add hover state and `RaycastClick`:

```typescript
import { useState, useCallback, memo } from 'react';
import RaycastClick from './RaycastClick';

// Inside Board3D, before the return:
const [hoverPos, setHoverPos] = useState<{ col: number; row: number } | null>(null);
const handleHover = useCallback((pos: { col: number; row: number } | null) => {
  setHoverPos(pos);
}, []);

// Inside <Canvas>:
<RaycastClick
  gameState={gameState}
  onMove={onMove}
  onNavigate={onNavigate}
  playerColor={playerColor}
  onHover={handleHover}
/>
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/RaycastClick.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add raycast click handler for move placement and navigation"
```

---

### Task 9: GhostStone (Hover Preview + Variations)

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/GhostStone.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create GhostStone.tsx**

```typescript
// katrain/web/ui/src/components/Board3D/GhostStone.tsx
import { memo } from 'react';
import StoneMesh from './StoneMesh';
import { gridToWorld } from './constants';
import type { GameState } from '../../api';

interface GhostStoneProps {
  gameState: GameState;
  hoverPos: { col: number; row: number } | null;
  showChildren: boolean;
  playerColor?: 'B' | 'W' | null;
}

const GhostStone = ({ gameState, hoverPos, showChildren, playerColor }: GhostStoneProps) => {
  const boardSize = gameState.board_size[0];
  const playerToMove = gameState.player_to_move as 'B' | 'W';

  let hoverStone = null;
  // Only show hover preview if it's the player's turn (or no restriction)
  // Matches Board.tsx behavior: !playerColor || gameState.player_to_move === playerColor
  if (hoverPos && !gameState.end_result && (!playerColor || playerToMove === playerColor)) {
    const { col, row } = hoverPos;
    const occupied = gameState.stones.some(s => s[1] && s[1][0] === col && s[1][1] === row);
    if (!occupied) {
      hoverStone = <StoneMesh color={playerToMove} position={gridToWorld(col, row, boardSize)} opacity={0.5} />;
    }
  }

  const ghostStones = showChildren && gameState.ghost_stones
    ? gameState.ghost_stones.map(([player, coords], i) => {
        if (!coords) return null;
        return <StoneMesh key={`ghost-${i}`} color={player as 'B' | 'W'} position={gridToWorld(coords[0], coords[1], boardSize)} opacity={0.5} />;
      })
    : null;

  return (
    <group>
      {hoverStone}
      {ghostStones}
    </group>
  );
};

export default memo(GhostStone);
```

- [ ] **Step 2: Wire into index.tsx**

```typescript
import GhostStone from './GhostStone';

// Inside <Canvas>:
<GhostStone gameState={gameState} hoverPos={hoverPos} showChildren={!!analysisToggles.children} playerColor={playerColor} />
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/GhostStone.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add ghost stone hover preview and variation display"
```

---

## Chunk 3: Analysis Overlays (Tasks 10–14)

### Task 10: Territory Overlay

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/Overlays/Territory.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create Territory.tsx**

```typescript
// katrain/web/ui/src/components/Board3D/Overlays/Territory.tsx
import { useMemo, memo } from 'react';
import { gridToSurface, getBoardDimensions } from '../constants';
import type { GameState } from '../../../api';

interface TerritoryProps {
  gameState: GameState;
}

const Territory = ({ gameState }: TerritoryProps) => {
  const boardSize = gameState.board_size[0];
  const ownership = gameState.analysis?.ownership;
  const dims = getBoardDimensions(boardSize);

  const patches = useMemo(() => {
    if (!ownership) return [];
    const result: { pos: [number, number, number]; color: string; alpha: number }[] = [];
    for (let y = 0; y < boardSize; y++) {
      for (let x = 0; x < boardSize; x++) {
        const val = ownership[y][x];
        if (Math.abs(val) > 0.05) {
          result.push({
            pos: gridToSurface(x, y, boardSize),
            color: val > 0 ? '#000000' : '#ffffff',
            alpha: Math.abs(val) * 0.4,
          });
        }
      }
    }
    return result;
  }, [ownership, boardSize]);

  const halfGrid = dims.gridSpacing * 0.48;

  return (
    <group>
      {patches.map((patch, i) => (
        <mesh key={i} position={patch.pos} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[halfGrid * 2, halfGrid * 2]} />
          <meshBasicMaterial color={patch.color} transparent opacity={patch.alpha} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
};

export default memo(Territory);
```

- [ ] **Step 2: Wire into index.tsx**

```typescript
import Territory from './Overlays/Territory';

// Inside <Canvas>:
{analysisToggles.ownership && gameState.analysis?.ownership && (
  <Territory gameState={gameState} />
)}
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/Overlays/Territory.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add territory/ownership overlay"
```

---

### Task 11: LastMove Overlay

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/Overlays/LastMove.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create LastMove.tsx**

Ring on top of the last-played stone. `gridToWorld` returns stone center Y; the ring sits at the stone apex (center Y + STONE_HEIGHT) plus a small epsilon to prevent z-fighting.

```typescript
// katrain/web/ui/src/components/Board3D/Overlays/LastMove.tsx
import { memo } from 'react';
import { gridToWorld, STONE_HEIGHT, ABOVE_STONE } from '../constants';
import type { GameState } from '../../../api';

interface LastMoveProps {
  gameState: GameState;
}

const LastMove = ({ gameState }: LastMoveProps) => {
  if (!gameState.last_move) return null;

  const boardSize = gameState.board_size[0];
  const [lx, ly] = gameState.last_move;
  const pos = gridToWorld(lx, ly, boardSize);

  const lastStone = gameState.stones.find(s => s[1] && s[1][0] === lx && s[1][1] === ly);
  const markerColor = lastStone?.[0] === 'B' ? '#ffffff' : '#000000';

  // Stone center is at pos[1]. Stone apex (top of flattened sphere) is at pos[1] + STONE_HEIGHT.
  // Ring sits just above the apex to avoid clipping.
  const ringY = pos[1] + STONE_HEIGHT + ABOVE_STONE;

  return (
    <mesh position={[pos[0], ringY, pos[2]]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[0.12, 0.18, 32]} />
      <meshBasicMaterial color={markerColor} transparent opacity={0.9} depthWrite={false} />
    </mesh>
  );
};

export default memo(LastMove);
```

- [ ] **Step 2: Wire into index.tsx**

```typescript
import LastMove from './Overlays/LastMove';

// Inside <Canvas>:
<LastMove gameState={gameState} />
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/Overlays/LastMove.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add last move glow marker overlay"
```

---

### Task 12: EvalDots Overlay

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/Overlays/EvalDots.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create EvalDots.tsx**

Colored discs on the top surface of each stone. `gridToWorld` returns stone center; dots sit above the stone apex (center Y + STONE_HEIGHT + epsilon) to avoid clipping into the curved sphere surface.

```typescript
// katrain/web/ui/src/components/Board3D/Overlays/EvalDots.tsx
import { memo } from 'react';
import { gridToWorld, getEvalColor, STONE_HEIGHT, ABOVE_STONE } from '../constants';
import type { GameState } from '../../../api';

interface EvalDotsProps {
  gameState: GameState;
}

const EvalDots = ({ gameState }: EvalDotsProps) => {
  const boardSize = gameState.board_size[0];

  return (
    <group>
      {gameState.stones.map(([, coords, scoreLoss], index) => {
        if (!coords || scoreLoss == null) return null;
        const [x, y] = coords;
        const pos = gridToWorld(x, y, boardSize);
        const color = getEvalColor(scoreLoss);

        // Stone apex is at center Y + STONE_HEIGHT. Dot sits just above to avoid clipping.
        const dotY = pos[1] + STONE_HEIGHT + ABOVE_STONE;

        return (
          <mesh key={`eval-${index}`} position={[pos[0], dotY, pos[2]]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.12, 16]} />
            <meshBasicMaterial color={color} transparent opacity={0.85} depthWrite={false} />
          </mesh>
        );
      })}
    </group>
  );
};

export default memo(EvalDots);
```

- [ ] **Step 2: Wire into index.tsx**

```typescript
import EvalDots from './Overlays/EvalDots';

// Inside <Canvas>:
{analysisToggles.eval && <EvalDots gameState={gameState} />}
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/Overlays/EvalDots.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add eval dots overlay on stones"
```

---

### Task 13: BestMoves Overlay

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/Overlays/BestMoves.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create BestMoves.tsx**

Hybrid overlay: colored circles on board surface + billboard text labels above.

```typescript
// katrain/web/ui/src/components/Board3D/Overlays/BestMoves.tsx
import { useMemo, memo } from 'react';
import { Billboard, Text } from '@react-three/drei';
import { gridToSurface, getEvalColor, EVAL_THRESHOLDS, BOARD_SURFACE_Y, STONE_HEIGHT, SURFACE_EPSILON } from '../constants';
import type { GameState } from '../../../api';

interface BestMovesProps {
  gameState: GameState;
}

const BestMoves = ({ gameState }: BestMovesProps) => {
  const boardSize = gameState.board_size[0];
  const moves = gameState.analysis?.moves;
  const maxMoves = gameState.trainer_settings?.max_top_moves_on_board || 3;

  const topMoves = useMemo(() => {
    if (!moves) return [];
    return moves.slice(0, maxMoves).filter((m: any) => m.coords);
  }, [moves, maxMoves]);

  if (topMoves.length === 0) return null;

  return (
    <group>
      {topMoves.map((move: any, index: number) => {
        const [x, y] = move.coords;
        const surfacePos = gridToSurface(x, y, boardSize);
        const color = getEvalColor(move.scoreLoss);
        const winrateText = (move.winrate * 100).toFixed(1);
        const visitsText = move.visits >= 1000
          ? `${(move.visits / 1000).toFixed(1)}k`
          : move.visits.toString();

        // Text contrast: dark backgrounds get white text
        const evalIdx = EVAL_THRESHOLDS.findIndex(t => move.scoreLoss >= t);
        const isDarkBg = evalIdx === -1 || evalIdx <= 2 || evalIdx === 5;
        const textColor = isDarkBg ? '#ffffff' : '#000000';
        const outlineColor = isDarkBg ? '#000000' : '#ffffff';

        return (
          <group key={`best-${index}`}>
            {/* Surface circle */}
            <mesh position={surfacePos} rotation={[-Math.PI / 2, 0, 0]}>
              <circleGeometry args={[0.4, 32]} />
              <meshBasicMaterial color={color} transparent opacity={0.85} depthWrite={false} />
            </mesh>

            {/* Best move white ring */}
            {index === 0 && (
              <mesh position={[surfacePos[0], surfacePos[1] + SURFACE_EPSILON, surfacePos[2]]} rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry args={[0.38, 0.44, 32]} />
                <meshBasicMaterial color="#ffffff" transparent opacity={0.8} depthWrite={false} />
              </mesh>
            )}

            {/* Billboard text (always faces camera) */}
            <Billboard position={[surfacePos[0], BOARD_SURFACE_Y + STONE_HEIGHT + 0.3, surfacePos[2]]}>
              <Text fontSize={0.22} color={textColor} anchorX="center" anchorY="bottom" outlineWidth={0.02} outlineColor={outlineColor}>
                {winrateText}
              </Text>
              <Text fontSize={0.18} color={textColor} anchorX="center" anchorY="top" position={[0, -0.04, 0]} outlineWidth={0.02} outlineColor={outlineColor}>
                {visitsText}
              </Text>
            </Billboard>
          </group>
        );
      })}
    </group>
  );
};

export default memo(BestMoves);
```

- [ ] **Step 2: Wire into index.tsx**

```typescript
import BestMoves from './Overlays/BestMoves';

// Inside <Canvas>:
{analysisToggles.hints && <BestMoves gameState={gameState} />}
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/Overlays/BestMoves.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add best moves overlay with billboard text labels"
```

---

### Task 14: PolicyMap Overlay

**Files:**
- Create: `katrain/web/ui/src/components/Board3D/Overlays/PolicyMap.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx`

- [ ] **Step 1: Create PolicyMap.tsx**

```typescript
// katrain/web/ui/src/components/Board3D/Overlays/PolicyMap.tsx
import { useMemo, memo } from 'react';
import { Billboard, Text } from '@react-three/drei';
import { gridToSurface, EVAL_COLORS, BOARD_SURFACE_Y, STONE_HEIGHT } from '../constants';
import type { GameState } from '../../../api';

interface PolicyMapProps {
  gameState: GameState;
}

const PolicyMap = ({ gameState }: PolicyMapProps) => {
  const boardSize = gameState.board_size[0];
  const policy = gameState.analysis?.policy;

  const cells = useMemo(() => {
    if (!policy) return [];
    const result: { pos: [number, number, number]; color: string; prob: number }[] = [];
    for (let y = 0; y < boardSize; y++) {
      for (let x = 0; x < boardSize; x++) {
        const prob = policy[y][x];
        if (prob > 0.001) {
          const polOrder = Math.max(0, 5 + Math.floor(Math.log10(Math.max(1e-9, prob - 1e-9))));
          result.push({
            pos: gridToSurface(x, y, boardSize),
            color: EVAL_COLORS[Math.min(polOrder, 5)],
            prob,
          });
        }
      }
    }
    return result;
  }, [policy, boardSize]);

  return (
    <group>
      {cells.map((cell, i) => (
        <group key={i}>
          <mesh position={cell.pos} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.28, 16]} />
            <meshBasicMaterial color={cell.color} transparent opacity={0.5} depthWrite={false} />
          </mesh>
          {cell.prob > 0.01 && (
            <Billboard position={[cell.pos[0], BOARD_SURFACE_Y + STONE_HEIGHT * 0.5, cell.pos[2]]}>
              <Text
                fontSize={0.2}
                color="#ffffff"
                anchorX="center"
                anchorY="middle"
                outlineWidth={0.015}
                outlineColor="#000000"
              >
                {`${(cell.prob * 100).toFixed(0)}%`}
              </Text>
            </Billboard>
          )}
        </group>
      ))}
    </group>
  );
};

export default memo(PolicyMap);
```

- [ ] **Step 2: Wire into index.tsx**

```typescript
import PolicyMap from './Overlays/PolicyMap';

// Inside <Canvas>:
{analysisToggles.policy && gameState.analysis?.policy && (
  <PolicyMap gameState={gameState} />
)}
```

- [ ] **Step 3: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/Overlays/PolicyMap.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(3d): add policy heatmap overlay"
```

---

## Chunk 4: Integration & Lazy Loading (Tasks 15–16)

### Task 15: Toggle Integration (RightSidebarPanel + Game Pages)

**Files:**
- Modify: `katrain/web/ui/src/galaxy/components/game/RightSidebarPanel.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/GamePage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx`

- [ ] **Step 1: Add 3D toggle to RightSidebarPanel**

In `RightSidebarPanel.tsx`, add import:

```typescript
import ViewInArIcon from '@mui/icons-material/ViewInAr';
```

Add the toggle after the `Count` `<ItemToggle>` (inside the tools grid `<Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>`):

```tsx
<ItemToggle
    icon={<ViewInArIcon />}
    label={t('3D', '3D')}
    active={analysisToggles.view3d}
    onClick={() => onToggleChange('view3d')}
/>
```

This makes 8 items in the 2-column grid (4 complete rows). The 3D toggle has no `disabled` prop — it's always available regardless of game mode.

- [ ] **Step 2: Update GamePage with view3d toggle and conditional Board3D**

In `GamePage.tsx`, make these changes:

**2a.** Add imports (note: no `React` import needed with `react-jsx`):

```typescript
import { useState, useEffect, useCallback, useRef, Suspense, lazy } from 'react';

const Board3D = lazy(() => import('../../components/Board3D'));
```

**2b.** Update initial `analysisToggles` state to include `view3d` with localStorage:

Replace the existing `useState` for `analysisToggles` with:

```typescript
const [analysisToggles, setAnalysisToggles] = useState<Record<string, boolean>>(() => ({
    children: false,
    eval: false,
    hints: false,
    policy: false,
    ownership: false,
    coords: true,
    numbers: false,
    score: true,
    winrate: true,
    view3d: localStorage.getItem('katrain_view3d') === 'true',
}));
```

**2c.** Update `handleToggleChange` to handle `view3d`:

Replace the existing `handleToggleChange` function with:

```typescript
const handleToggleChange = (setting: string) => {
    if (setting === 'view3d') {
        setAnalysisToggles(prev => {
            const next = { ...prev, view3d: !prev.view3d };
            localStorage.setItem('katrain_view3d', String(next.view3d));
            return next;
        });
        return;
    }
    if (setting === 'hints') {
        const hasAnalysis = !!gameState?.analysis?.moves?.length;
        const currentlyOn = analysisToggles.hints;

        if (currentlyOn) {
            setAnalysisToggles(prev => ({ ...prev, hints: false }));
            waitingForAnalysisRef.current = false;
        } else {
            if (hasAnalysis) {
                setAnalysisToggles(prev => ({ ...prev, hints: true }));
            } else {
                setAnalysisToggles(prev => ({ ...prev, hints: true }));
                waitingForAnalysisRef.current = true;
            }
        }
    } else {
        setAnalysisToggles(prev => ({ ...prev, [setting]: !prev[setting] }));
    }
};
```

**2d.** Fix pre-existing `isAnalysisPending` field name: In GamePage.tsx, find the `isAnalysisPending` prop (around line 321) and change `top_moves` to `moves` for consistency:

```typescript
// Before:
isAnalysisPending={analysisToggles.hints && !gameState.analysis?.top_moves?.length}
// After:
isAnalysisPending={analysisToggles.hints && !gameState.analysis?.moves?.length}
```

**2e.** Replace the `<Board>` JSX (around line 300-308) with conditional rendering:

```tsx
<Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 0.5 }}>
    {analysisToggles.view3d ? (
        <Suspense fallback={<CircularProgress />}>
            <Board3D
                gameState={gameState}
                onMove={onMove}
                onNavigate={onNavigate}
                analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
                playerColor={humanColor}
            />
        </Suspense>
    ) : (
        <Board
            gameState={gameState}
            onMove={onMove}
            onNavigate={onNavigate}
            analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
            playerColor={humanColor}
        />
    )}
</Box>
```

- [ ] **Step 3: Update GameRoomPage with view3d toggle and conditional Board3D**

In `GameRoomPage.tsx`, make these changes:

**3a.** Add imports:

```typescript
import { useEffect, useState, useCallback, Suspense, lazy } from 'react';

const Board3D = lazy(() => import('../../components/Board3D'));
```

**3b.** Add view3d state inside the component:

```typescript
const [view3d, setView3d] = useState(() => localStorage.getItem('katrain_view3d') === 'true');
```

**3c.** Replace the `<Board>` JSX (around line 294-301) with conditional rendering:

```tsx
<Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 2 }}>
    {view3d ? (
        <Suspense fallback={<CircularProgress />}>
            <Board3D
                gameState={gameState}
                onMove={(x, y) => isPlayer ? onMove(x, y) : {}}
                onNavigate={onNavigate}
                analysisToggles={{ coords: true, numbers: false }}
            />
        </Suspense>
    ) : (
        <Board
            gameState={gameState}
            onMove={(x, y) => isPlayer ? onMove(x, y) : {}}
            onNavigate={onNavigate}
            analysisToggles={{ coords: true, numbers: false }}
        />
    )}
</Box>
```

**3d.** Update the `RightSidebarPanel` props to pass `view3d` and handle the toggle:

```tsx
<RightSidebarPanel
    gameState={gameState}
    analysisToggles={{ ownership: false, hints: false, score: false, policy: false, coords: true, numbers: false, view3d }}
    onToggleChange={(setting) => {
        if (setting === 'view3d') {
            setView3d(prev => {
                const next = !prev;
                localStorage.setItem('katrain_view3d', String(next));
                return next;
            });
        }
        // Other toggles are disabled for HvH — no-op
    }}
    onNavigate={onNavigate}
    onAction={isPlayer ? handleActionWrapper : () => {}}
    isRated={true}
/>
```

- [ ] **Step 4: Verify it compiles**

```bash
cd katrain/web/ui && npx tsc --noEmit
```

Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/galaxy/components/game/RightSidebarPanel.tsx katrain/web/ui/src/galaxy/pages/GamePage.tsx katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx
git commit -m "feat(3d): add 3D toggle to sidebar and wire conditional board rendering"
```

---

### Task 16: Final Verification & Build

**Files:** None new — verification only.

- [ ] **Step 1: Run all existing tests**

```bash
cd katrain/web/ui && npx vitest run
```

Expected: All existing tests still pass.

- [ ] **Step 2: Run Board3D constants tests**

```bash
cd katrain/web/ui && npx vitest run src/components/Board3D/__tests__/constants.test.ts
```

Expected: All pass.

- [ ] **Step 3: Production build**

```bash
cd katrain/web/ui && npm run build
```

Expected: Build succeeds. Check output for separate chunk for Board3D (lazy loading creates a separate bundle).

- [ ] **Step 4: Manual visual verification**

```bash
cd katrain/web/ui && npm run dev
```

Open Galaxy Game Page, start a game against AI. In sidebar, click "3D" toggle. Verify:
- Board renders in 3D with wood texture, grid lines, star points
- **Board orientation matches 2D**: row 1 is near camera (bottom), row 19 is far (top)
- Stones appear on moves with drop animation
- **Drop animation works for captures** (stone count decreases but animation still plays)
- Hover preview ghost stone on empty intersections
- **No hover preview when spectating** (playerColor restriction works)
- Clicking on occupied intersection navigates to that move
- Territory overlay works (toggle in sidebar)
- Best moves / Advice overlay works (billboard text readable at all angles)
- **Policy heatmap text is readable** (billboard, not flat)
- Eval dots on stones (clearly above stone surface, no clipping)
- Last move marker ring (clearly above stone surface, not buried inside)
- Camera tilts vertically on drag, zooms on scroll
- No horizontal rotation possible
- Coordinates display when enabled
- **End-game result overlay displays** when game ends
- Toggle back to 2D works seamlessly
- Refreshing page preserves 3D preference via localStorage

- [ ] **Step 5: Final commit**

```bash
git add katrain/web/ui/src/components/Board3D/
git commit -m "feat(3d): complete 3D board integration with all overlays and lazy loading"
```

---

## Reference Files

| Purpose | File |
|---------|------|
| 3D prototype (geometry, textures, animation params) | `~/Downloads/go-board-3d.html` |
| Existing 2D board (props interface, overlay logic) | `katrain/web/ui/src/components/Board.tsx` |
| Board utilities (layout, coord conversion) | `katrain/web/ui/src/components/board/boardUtils.ts` |
| GameState type definition | `katrain/web/ui/src/api.ts:10-72` |
| Game page (AI play) | `katrain/web/ui/src/galaxy/pages/GamePage.tsx` |
| Game page (multiplayer) | `katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx` |
| Right sidebar panel | `katrain/web/ui/src/galaxy/components/game/RightSidebarPanel.tsx` |
| App theme (background colors) | `katrain/web/ui/src/theme.ts` |
| TypeScript config (strict settings) | `katrain/web/ui/tsconfig.app.json` |

## Design Decisions Summary

| Decision | Choice |
|----------|--------|
| 3D Framework | React Three Fiber + drei |
| Analysis overlays | Hybrid: surface-projected territory/eval + billboard text for best moves & policy |
| View toggle | Toggle button in RightSidebarPanel tools grid |
| Camera control | Vertical tilt only (drag up/down), scroll zoom, no horizontal rotation |
| Stone animation | Drop animation for new moves only; instant for navigation |
| Bundle strategy | Lazy load via `lazy()` from react |
| Board sizes | 9x9, 13x13, 19x19 |
| Stone style | Hamaguri (蛤碁石) only |
| Platform | Desktop only |
| Background | Match app theme (#0f0f0f) |
