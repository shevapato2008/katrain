# 3D Board Design Review Prompt

> Give this document along with the implementation plan to external reviewers (Codex, Gemini, etc.) for feedback.

---

## Context

We're adding a 3D Go board view to **KaTrain**, an open-source Go/Baduk teaching app. The web UI is React + TypeScript + Vite. The existing 2D board is a Canvas-based component (`Board.tsx`). We have a standalone Three.js prototype (`go-board-3d.html`, ~1400 lines) that renders a photorealistic 3D Go board with Hamaguri stones, wood textures, and drop animations.

The implementation plan (`2026-03-11-3d-board-design.md`) describes how to integrate the 3D view into the app using React Three Fiber. It contains 16 tasks across 4 chunks, with complete TypeScript code for every new file.

## What to Review

Please review the implementation plan for correctness, completeness, and potential issues. Focus on these areas:

### 1. Architecture & Component Design

- Is the file decomposition reasonable? Too many files? Too few? Any responsibilities misplaced?
- Does the `BoardProps` sharing strategy (both 2D `Board.tsx` and 3D `Board3D/index.tsx` accept the same props interface) make sense? Any props that won't translate well to 3D?
- Is lazy loading via `lazy()` + `<Suspense>` the right approach for code splitting the Three.js bundle?
- The plan creates ~15 new files in `Board3D/`. Is this granularity appropriate for a React Three Fiber scene graph?

### 2. React Three Fiber Correctness

- Are there R3F anti-patterns? (e.g., creating objects inside render, missing `useMemo`/`useFrame` patterns, incorrect disposal)
- Is the `<Canvas>` setup correct? (`shadows`, `gl` config, `camera` positioning)
- Are pointer events handled correctly? The plan uses an invisible plane for raycasting and sets `raycast={null}` on stones so clicks pass through. Is this the right approach?
- Camera controls: The plan locks horizontal rotation (azimuth) and allows only vertical tilt (polar angle 5-38 degrees). Is `OrbitControls` the right tool for this, or would a simpler custom solution be better?

### 3. Coordinate System & Geometry

- The Go board coordinate system maps `col` to X-axis and `row` to Z-axis in world space. The `gridToWorld` / `worldToGrid` functions handle conversion. Is this mapping correct and consistent throughout all components?
- Stone placement: `y = BOARD_SURFACE_Y + STONE_HEIGHT` (1.20 + 0.22 = 1.42). Does this make geometric sense for a flattened sphere sitting on a board surface?
- The board surface is at `y = 1.20` (top of the board slab). Overlays use `y = BOARD_SURFACE_Y + 0.005` to avoid z-fighting. Is 0.005 sufficient?

### 4. Analysis Overlays in 3D

The 2D board renders several analysis overlays. Each must work in 3D perspective:

- **Territory/Ownership**: Flat semi-transparent planes on the board surface. Will these z-fight with the board mesh? Is the alpha blending approach correct?
- **Best Moves (Hints)**: Surface circles + billboard `<Text>` labels that always face the camera. Will the text be readable at low camera angles? Will multiple overlapping labels cause visual clutter?
- **Eval Dots**: Colored discs on stone tops (`y = stone_y + STONE_HEIGHT * 0.95`). Will these clip into the stone geometry?
- **Policy Heatmap**: Similar to territory but with text labels. Same z-fighting concerns.
- **Last Move Marker**: Glowing torus ring around the last stone. Is a `<torusGeometry>` the right primitive? Will the emissive glow be visible against various board/stone colors?

### 5. Drop Animation

- The plan detects new moves by comparing `current_node_index` changes via `useRef`. Is this reliable? Could it trigger false positives during history navigation?
- Animation uses spring physics (gravity + damping) in `useFrame`. Is this performant for rapid successive moves? Could the animation queue get stuck?
- Captured stones disappear instantly when a new move is played. Is this the right UX, or should there be a removal animation?

### 6. Performance

- Each stone is a separate `<mesh>` with its own geometry and material. For a 19x19 board (up to 361 stones), is this acceptable, or should we use `<InstancedMesh>` for better GPU batching?
- Grid lines use drei `<Line>` components (38 lines for 19x19). Is this efficient, or should a single `BufferGeometry` with line segments be preferred?
- The overlay components (`Territory`, `EvalDots`, etc.) create many small meshes. At what point should instancing be considered?
- Is GPU resource cleanup (texture/material disposal) handled correctly in the plan?

### 7. Integration & State Management

- The `view3d` toggle is added to `analysisToggles` (a `Record<string, boolean>`). This works but semantically it's a view mode, not an analysis toggle. Is there a better place for this state?
- `localStorage` persistence for the 3D preference: is the implementation correct? Race conditions?
- `GameRoomPage.tsx` (multiplayer) has fixed analysis toggles `{ coords: true, numbers: false }`. The plan adds a separate `view3d` state. Is this handled correctly?

### 8. TypeScript Strictness

The project uses strict TypeScript:
- `verbatimModuleSyntax: true` — must use `import type` for type-only imports
- `noUnusedLocals: true` / `noUnusedParameters: true`
- `jsx: react-jsx` — no need to `import React` for JSX

Check the plan's code for:
- Any bare `import React` that would fail
- Any unused imports/variables that would fail `noUnusedLocals`
- Missing `import type` for type-only imports
- Correct JSX pragma usage

### 9. Missing Features or Edge Cases

- What happens when the board size changes mid-game (it shouldn't, but what if the component receives new `board_size` props)?
- What about browser tab visibility? Should the R3F render loop pause when the tab is inactive?
- WebGL context loss/restoration — is this handled?
- Accessibility: the 2D Canvas has some basic accessibility. Does the 3D view lose all of that? Is that acceptable?
- Right-click handling: the 2D board may handle right-click for undo. Does the 3D view interfere with this?

### 10. Bundle Size Impact

- `three` + `@react-three/fiber` + `@react-three/drei` add significant bundle size (~500KB+ gzipped). The plan uses lazy loading to mitigate this. Is the lazy boundary drawn in the right place?
- Are there unused drei features that could be tree-shaken? Should specific imports (e.g., `import { OrbitControls, Text, Line } from '@react-three/drei'`) be used instead of barrel imports?

## Reference Files

When reviewing, you may want to cross-reference:

| File | Purpose |
|------|---------|
| `katrain/web/ui/src/components/Board.tsx` | Existing 2D board — the "source of truth" for what overlays look like and how props are used |
| `katrain/web/ui/src/api.ts` | `GameState` interface — the data model driving both 2D and 3D |
| `katrain/web/ui/src/galaxy/pages/GamePage.tsx` | AI play page — where 3D toggle integration happens |
| `katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx` | Multiplayer page — similar integration |
| `katrain/web/ui/src/galaxy/components/game/RightSidebarPanel.tsx` | Sidebar — where the 3D toggle button goes |
| `katrain/web/ui/tsconfig.app.json` | TypeScript config — strictness settings |
| `katrain/web/ui/package.json` | Current dependencies |
| `~/Downloads/go-board-3d.html` | 3D prototype — the visual/behavioral reference |

## Output Format

Please structure your feedback as:

1. **Critical issues** — things that will break or cause significant problems
2. **Important suggestions** — things that should be changed but won't break
3. **Minor notes** — style, naming, or optimization suggestions
4. **Questions** — things that need clarification before you can fully assess

For each issue, reference the specific task number and code section in the plan.
