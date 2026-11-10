# 3D Board & Stone Systematic Alignment with Showcase v6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Systematically align the production 3D board (`Board3D`, `BoardMesh`, `CoordinateLabels`, `Lights`, `StoneMesh`, `stoneModel`, `SolidWoodSlab`) and 2D `Board.tsx` loader with the approved `stone-and-board-showcase-v6.html` preview so that all 4 wood styles (`kaya`, `shin-kaya`, `bamboo`, `walnut`) and 4 stone styles (`clamshell-slate`, `yunzi`, `jade-agate`, `minimal`) look identical in brightness, color, grid crispness, coordinate legibility, contact shadows, and PBR sheen between 2D, 3D, and the preview showcase.

**Architecture:**
1. **Eliminate 3D Texture Double-Darkening (`BoardMesh.tsx`)**: Remove `color: cfg.topColor` / `color: cfg.sideColor` from `topMat` and `sideMat` when `map` is bound (use `#ffffff` so Three.js does not multiply the 2K wood veneer texture by dark brown `#5C402C`, which crushed `walnut` brightness by 90%). Upgrade `topTex` to `2048×2048` with `anisotropy = 16` and `THREE.MeshPhysicalMaterial` (`roughness: 0.36, clearcoat: 0.18, clearcoatRoughness: 0.28, metalness: 0.0`). Bake crisp anti-aliased grid lines and star points directly onto `topTex` (aligned with `[-halfExtent, halfExtent]`) in addition to `<lineSegments>`, and remove procedural grain loops from `createWoodTexture`.
2. **Fix 3D Coordinate Label Color (`CoordinateLabels.tsx` & `BoardMesh.tsx`)**: Pass `palette.coordColor` from `BoardMesh.tsx` into `CoordinateLabels.tsx` instead of hardcoding `#2a1a0a`, so `walnut` coordinates render in warm cream `#d9c3ac` just like 2D.
3. **Add Studio PMREM Environment & Balanced Studio Lighting (`Lights.tsx` & `Board3D/index.tsx`)**: Port `buildStudioEnvironment(gl)` and studio light intensities from `stone-and-board-showcase-v6.html` into `Lights.tsx` so `MeshPhysicalMaterial` on both the board and stones reflects soft overhead studio light cards instead of a black void.
4. **Align 3D Stone Geometry Profiles, PBR Materials, Contact Shadows & Jade Caustics (`stoneModel.ts` & `StoneMesh.tsx`)**: Port per-style 3D lathe profiles (`clamshell`, `yunzi`, `agate-dome`, `flat-dome`) and exact `stone-and-board-showcase-v6.html` PBR material recipes into `stoneModel.ts`; render the soft radial contact shadow disc under every 3D stone and the warm lower-right caustic glow disc under white `jade-agate` stones in `StoneMesh.tsx`; keep `transparent = opacity < 1` on `jade-agate` so Three.js physical `transmission` remains active.
5. **Fix `Board.tsx` 2D Veneer Image Loading (`boardUtils.ts` & `Board.tsx`)**: Ensure `loadBoardImages({ ...BOARD_ASSETS, board: ... }, stoneStyle)` in `boardUtils.ts` always loads the 2K wood veneer image (`loadBoardVeneerImage(resolvedBoardStyle)`) for `key === "board"`, and pass `boardStyle` from `Board.tsx`.

**Tech Stack:** TypeScript, React 18, Three.js / `@react-three/fiber` / `@react-three/drei`, Vitest, Playwright.

---

### Task 1: Fix 3D Board Material, 2K Texture Resolution, Baked Crisp Grid/Stars & Coordinate Colors

**Files:**
- Modify: `katrain/web/ui/src/components/Board3D/BoardMesh.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/CoordinateLabels.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/SolidWoodSlab.tsx`
- Test: `katrain/web/ui/src/components/Board3D/Board3D.test.tsx`

- [ ] **Step 1: Update `CoordinateLabels.tsx` to accept `color` prop**
  - Add `color?: string` to `CoordinateLabelsProps` (defaulting to `'#2a1a0a'`) and pass `color={color}` and `fillOpacity={0.9}` to `<Text>`.
- [ ] **Step 2: Update `BoardMesh.tsx` to match `stone-and-board-showcase-v6.html` 1:1**
  - Align `BOARD_3D_STYLE_CONFIG` base/side/bottom colors with `stone-and-board-showcase-v6.html` (`kaya: '#d9a657'`, `'shin-kaya': '#e5c687'`, `bamboo: '#c78c46'`, `walnut: '#876244'`).
  - In `createWoodTexture`:
    - Use `2048×2048` for `topTex`, set `tex.colorSpace = THREE.SRGBColorSpace` and `tex.anisotropy = 16`.
    - Remove all procedural grain/noise loops; fill canvas cleanly with `baseColor`, then draw `gridOverlay(ctx, width, height)` (crisp anti-aliased grid lines and star points mapped to `[-halfExtent, halfExtent]` within `dims.boardWidth`), and when `img.onload` fires, draw `img` (`2048×2048`) followed by `gridOverlay(ctx, width, height)`, set `tex.needsUpdate = true`, and call `onLoad?.()`.
  - Create `topMat` as `new THREE.MeshPhysicalMaterial({ map: topTex, color: '#ffffff', roughness: 0.36, clearcoat: 0.18, clearcoatRoughness: 0.28, metalness: 0.0 })` and `sideMat` as `new THREE.MeshPhysicalMaterial({ map: sideTex, color: '#ffffff', roughness: 0.52, metalness: 0.0 })` — NEVER pass `color: cfg.topColor` or `color: cfg.sideColor` when `map` is used!
  - Pass `color={palette.coordColor}` to `<CoordinateLabels labels={coordLabels} color={palette.coordColor} />`.
- [ ] **Step 3: Update `SolidWoodSlab.tsx` to also load 2K wood veneer without procedural bamboo blocks/stripes**
  - Load `getBoardTextureUrl(boardStyle)` on the top/side faces with `color: '#ffffff'` and stripe-free fallback.

---

### Task 2: Add Studio PMREM Environment & Align 3D Lighting, Stone Profiles, PBR Materials & Contact Shadows

**Files:**
- Modify: `katrain/web/ui/src/components/Board3D/Lights.tsx`
- Modify: `katrain/web/ui/src/components/tutorials/stoneModel.ts`
- Modify: `katrain/web/ui/src/components/Board3D/StoneMesh.tsx`
- Modify: `katrain/web/ui/src/components/ board/boardUtils.ts`
- Modify: `katrain/web/ui/src/components/Board.tsx`

- [ ] **Step 1: Upgrade `Lights.tsx` with Studio PMREM Environment & Showcase v6 Light Rig**
  - Inside `Lights.tsx`, use `useThree()` (in a try/catch for unit test safety) to build and attach the studio PMREM environment texture (`scene.environment = envTex`, `scene.environmentIntensity = 0.54`) with two softbox light cards (`[-3.2, 5.2, -3.8]` intensity `2.8` and `[4.8, 2.4, 3.8]` intensity `0.85`), matching `buildStudioEnvironment` in `stone-and-board-showcase-v6.html`.
  - Set `Lights` to match `stone-and-board-showcase-v6.html`:
    - `<ambientLight color={0xfff6e5} intensity={0.58} />`
    - `<hemisphereLight args={[0xfff8ee, 0x9b8362, 0.48]} />`
    - Key `<directionalLight color={0xfff9ea} intensity={1.55} position={[-10, 18, -11]} castShadow ... />`
    - Fill `<directionalLight color={0xe9efff} intensity={0.42} position={[11, 10, 10]} />`
    - Rim `<directionalLight color={0xffdfba} intensity={0.28} position={[0, 8, -14]} />`
- [ ] **Step 2: Align `stoneModel.ts` and `StoneMesh.tsx` with `stone-and-board-showcase-v6.html`**
  - In `stoneModel.ts`, support `stoneStyle` in `createStoneGeometry(color, detail, stoneStyle)` with the 4 exact Bezier profiles (`clamshell-slate`, `yunzi` with `lowerScale = 0.84`, `jade-agate` dome, `minimal` flat-dome) and update `createStoneMaterial` to match `stone-and-board-showcase-v6.html` lines 1573–1751 (`yunzi` warm radial texture + emissiveMap, `jade-agate` 512px chalcedony cloud/band texture + `transmission: 0.48, thickness: 1.35, ior: 1.544, clearcoat: 0.98, sheen: 0.35, emissiveIntensity: 0.20, envMapIntensity: 1.2`, `minimal` matte gradient).
  - In `StoneMesh.tsx`:
    - Render the soft radial contact shadow disc (`getContactTexture()`) beneath every non-sprite 3D stone (not just `satinFinish`), and render the warm lower-right caustic decal disc (`getCausticTexture()`) beneath white `jade-agate` stones.
    - Keep `mat.transparent = opacity < 1` so full-opacity `jade-agate` white stones use physical `transmission` without alpha-blend override.
- [ ] **Step 3: Fix `Board.tsx` and `boardUtils.ts` 2D Wood Veneer Loader**
  - In `boardUtils.ts`, when `boardStyleOrAssets` is an object and `key === "board"`, always load `await loadBoardVeneerImage(resolvedBoardStyle)` first.
  - In `Board.tsx`, pass `loadBoardImages(boardStyle, stoneStyle)` so `Board.tsx` (`对局` / `复盘`) loads the 2K wood veneer image and caches per `(boardStyle, stoneStyle)`.
