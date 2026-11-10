# 2D/3D Board & Stone Styles, Galaxy Two-Level Settings Menu, and Kiosk Synchronization Implementation Plan (v2 — Revised after Round 1 Review)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the StellaBox favicon, 4 curated Go stone styles (`蛤碁石`, `云子`, `玉石玛瑙`, `简约`) and 4 board wood styles (`日式本榧`, `新榧云杉`, `碳化楠竹`, `胡桃沉香`) across 2D Canvas/SVG and 3D WebGL boards, upgrade the Galaxy sidebar Settings menu to a 2-level cascading menu (`语言`, `棋盘样式`, `棋子样式`, `中文字体`), add board/stone style selectors to Kiosk Settings, and ensure all live/kifu preview boards and play/analysis boards reactively update on change without memory leaks or race conditions.

**Architecture & Invariants:**
1. **Strict Kiosk 2D Bundle Boundary (`scripts/verify-kiosk.sh`)**:
   - `src/components/board/stoneAppearance.ts`, `src/components/board/boardUtils.ts`, and `src/context/SettingsContext.tsx` are bundled into Kiosk 2D (`static-kiosk-2d`).
   - **Hard Invariant**: These files must **NEVER** import anything from `three`, `@react-three/*`, or `src/galaxy/*`, and must **NEVER** contain the string literal `"/galaxy/"` or `"/api/v1/live"` (even in comments!).
2. **Pure-2D Appearance Store & Procedural Sprites (`src/components/board/stoneAppearance.ts` & `boardUtils.ts`)**:
   - Strictly defines:
     - `StoneStyleId = 'clamshell-slate' | 'yunzi' | 'jade-agate' | 'minimal'` (`STONE_STYLE_IDS = ['clamshell-slate', 'yunzi', 'jade-agate', 'minimal']`, permanently excluding `'mineral-stone'` and `'galaxy-star'`).
     - `BoardStyleId = 'kaya' | 'shin-kaya' | 'bamboo' | 'walnut'` (`BOARD_STYLE_IDS = ['kaya', 'shin-kaya', 'bamboo', 'walnut']`).
     - `ChineseFontId = 'wenkai' | 'kaiti' | 'lishu' | 'heiti'`.
   - `normalizeStoneStyleId(id)` maps legacy `'shell-slate'` to `'clamshell-slate'` and falls back safely to `'clamshell-slate'` on `null`/`undefined`/unknown values.
   - `normalizeBoardStyleId(id)` falls back safely to `'kaya'` on `null`/`undefined`/unknown values.
   - Provides reactive external store hook `useBoardAppearance()` backed by `localStorage` (`katrain_stone_style`, `katrain_board_style`) with safe `null` handling when `localStorage.clear()` is called in tests.
3. **2D Race-Free Asset Loading & Fallback Colors**:
   - `drawBoardBackground(ctx, layout, boardImg, boardStyle?)` uses `getBoardStylePalette(boardStyle).woodFill` instead of hardcoded `#dcb35c` so switching to `walnut` never flashes yellow.
   - `drawStone` and `stoneImage` default `stoneStyle` to `getActiveStoneStyle()` and `stoneSpriteUrl` defaults `appearanceId` to `getActiveStoneStyle()` when omitted, guaranteeing zero missed call sites.
   - All 2D Canvas boards (`Board.tsx`, `LiveBoard.tsx`, `TsumegoBoard.tsx`) use an incrementing `assetsVersion` state (`setAssetsVersion(v => v + 1)`) plus a `let cancelled = false` cleanup flag inside `useEffect([boardStyle, stoneStyle])`, and include `assetsVersion`, `boardStyle`, and `stoneStyle` in `renderBoard`'s dependency array.
   - Orphaned duplicate files `src/galaxy/components/live/LiveBoard.tsx` and `src/galaxy/components/tsumego/TsumegoBoard.tsx` are replaced with clean re-exports of `src/components/live/LiveBoard` and `src/components/tsumego/TsumegoBoard`.
4. **3D Reactivity & GPU Memory Management (`BoardMesh.tsx`, `SolidWoodSlab.tsx`, `StoneMesh.tsx`, `stoneModel.ts`)**:
   - `BoardMesh.tsx` returns `{ textures, materials }` from `useMemo(..., [boardSize, solidWood, boardStyle])` and disposes `resources.textures` and `resources.materials` in `useEffect(() => () => { ... }, [resources])` (fixing `C-1` GPU texture leak).
   - `StoneMesh.tsx` subscribes to `const { stoneStyle } = useBoardAppearance();`, includes `stoneStyle` in the `material` `useMemo` dependency array (`[color, opacity, variant, satinFinish, spriteTexture, stoneStyle]`), and calls `invalidate()` on `useThree()` when `stoneStyle` changes (fixing `C-2`).
   - Procedural 3D textures for `jade-agate` and `yunzi` in `stoneModel.ts` are cached in module-level static `Map`s (8 variants max per style, indexed by `variant % 8`) so 180 stones on a 19x19 board share cached `THREE.CanvasTexture` instances instead of allocating per mesh (`M-4`).
5. **Kiosk Settings Test Compatibility (`SettingsPage.tsx` & `SettingsPage.test.tsx`)**:
   - Keep the exact 6 navigation groups (`['实体棋盘', '落子与提示', '声音', '语言', '字体与字号', '关于']`) and never render `'棋盘外观'` or `'对局默认值'` headings.
   - Place `棋盘样式` and `棋子样式` `.kiosk-row` segmented controls inside the `实体棋盘` (`data-group="board"`) section and bind them via `useBoardAppearance()` directly so existing tests with partial `useSettings()` mocks continue to pass without modification.

---

### Task 1: Browser Favicon & Pure-2D Board/Stone Appearance Store (`stoneAppearance.ts` & `boardUtils.ts`)

**Files:**
- Copy: `katrain/img/logo-white.png` -> `katrain/web/ui/public/assets/img/logo-white.png`
- Modify: `katrain/web/ui/index.html`
- Modify: `katrain/web/ui/src/components/board/stoneAppearance.ts`
- Modify: `katrain/web/ui/src/components/board/stoneAppearance.test.ts`
- Modify: `katrain/web/ui/src/components/board/boardUtils.ts`
- Modify: `katrain/web/ui/src/components/board/boardUtils.test.ts`

- [ ] **Step 1: Copy `logo-white.png` into `public/assets/img/` and update `index.html`**
  - Copy `katrain/img/logo-white.png` to `katrain/web/ui/public/assets/img/logo-white.png` so standalone Vite builds (`static` and `static-kiosk-2d`) include the favicon asset (`M-3`).
  - Update `katrain/web/ui/index.html` line 5 to `<link rel="icon" type="image/png" href="/assets/img/logo-white.png" />`.

- [ ] **Step 2: Write failing tests in `stoneAppearance.test.ts` and `boardUtils.test.ts`**
  - Assert `STONE_STYLE_IDS` equals `['clamshell-slate', 'yunzi', 'jade-agate', 'minimal']` and does not include `'mineral-stone'` or `'galaxy-star'`.
  - Assert `BOARD_STYLE_IDS` equals `['kaya', 'shin-kaya', 'bamboo', 'walnut']`.
  - Assert `normalizeStoneStyleId('shell-slate') === 'clamshell-slate'`, `normalizeStoneStyleId(null) === 'clamshell-slate'`, and `normalizeBoardStyleId(null) === 'kaya'`.
  - Assert `setActiveStoneStyle` / `getActiveStoneStyle` and `setActiveBoardStyle` / `getActiveBoardStyle` update `localStorage` (`katrain_stone_style`, `katrain_board_style`), notify subscribers, and recover gracefully after `localStorage.clear()`.
  - Assert `stoneSpriteUrl(color, seed, col, row)` (when `styleId` is omitted) uses `getActiveStoneStyle()` so changing the active stone style immediately changes returned sprite URLs.
  - Assert `getBoardStylePalette(style)` and `getBoardTextureDataUrl(style)` return distinct palettes and valid `data:` URLs for all 4 board styles.

- [ ] **Step 3: Implement `stoneAppearance.ts` and `boardUtils.ts` (Pure 2D, Zero `three` / `galaxy` references)**
  - Implement the 4 stone styles (`clamshell-slate`, `yunzi`, `jade-agate`, `minimal`) and 4 board wood styles (`kaya`, `shin-kaya`, `bamboo`, `walnut`) in `stoneAppearance.ts` with cached high-DPI Canvas 2D data URLs and deterministic SVG data-URL fallbacks when Canvas 2D is unavailable in headless JSDOM.
  - Update `boardUtils.ts` (`loadBoardImages`, `drawBoardBackground`, `drawBoardGrid`, `drawStone`, `stoneImage`) to use `getActiveBoardStyle()` / `getActiveStoneStyle()` by default and `getBoardStylePalette(boardStyle)` for wood fill, grid lines, star points, and coordinates.

- [ ] **Step 4: Run Vitest on `stoneAppearance.test.ts` and `boardUtils.test.ts`**
  - Run: `cd katrain/web/ui && npx vitest run src/components/board/stoneAppearance.test.ts src/components/board/boardUtils.test.ts`

---

### Task 2: Global `SettingsContext`, Chinese Font Integration in `galaxy/theme.ts` & `GalaxyApp.tsx`

**Files:**
- Modify: `katrain/web/ui/src/context/SettingsContext.tsx`
- Modify: `katrain/web/ui/src/galaxy/theme.ts`
- Modify: `katrain/web/ui/src/GalaxyApp.tsx`

- [ ] **Step 1: Extend `SettingsContext.tsx` (Strictly no `src/galaxy/` imports or `"/galaxy/"` strings)**
  - Expose `boardStyle`, `setBoardStyle`, `stoneStyle`, `setStoneStyle`, `chineseFont`, `setChineseFont` on `SettingsContextType`.
  - Sync `boardStyle` and `stoneStyle` with `useBoardAppearance()` from `../components/board/stoneAppearance`.
  - Persist `chineseFont` (`'wenkai' | 'kaiti' | 'lishu' | 'heiti'`, default `'wenkai'`) in `localStorage` under `'katrain_chinese_font'` and synchronize with `'kiosk.typography.v1'` when updated.

- [ ] **Step 2: Update `katrain/web/ui/src/galaxy/theme.ts` and `katrain/web/ui/src/GalaxyApp.tsx`**
  - Update `createGalaxyTheme(language: string = 'zh', chineseFont: ChineseFontId = 'wenkai')` to map `'wenkai' | 'kaiti' | 'lishu' | 'heiti'` to their respective font stacks loaded by `kiosk-shell/fonts.css`.
  - In `GalaxyApp.tsx`, pass `chineseFont` from `useSettings()` into `createGalaxyTheme(language, chineseFont)` and apply the font stack to `.galaxy-root`.

- [ ] **Step 3: Run Galaxy unit tests**
  - Run: `cd katrain/web/ui && npx vitest run src/galaxy/`

---

### Task 3: 2D Canvas, 2D SVG, and 3D WebGL Board Reactive Synchronization

**Files:**
- Modify: `katrain/web/ui/src/components/Board.tsx`
- Modify: `katrain/web/ui/src/components/live/LiveBoard.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/live/LiveBoard.tsx`
- Modify: `katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/tsumego/TsumegoBoard.tsx`
- Modify: `katrain/web/ui/src/components/MiniBoard.tsx`
- Modify: `katrain/web/ui/src/components/tutorials/SGFBoard.tsx`
- Modify: `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx`
- Modify: `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/BoardMesh.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/SolidWoodSlab.tsx`
- Modify: `katrain/web/ui/src/components/Board3D/StoneMesh.tsx`
- Modify: `katrain/web/ui/src/components/tutorials/stoneModel.ts`

- [ ] **Step 1: Update 2D Canvas Boards (`Board.tsx`, `LiveBoard.tsx`, `TsumegoBoard.tsx`) & Clean Up Orphaned Duplicates**
  - Subscribe to `const { boardStyle, stoneStyle } = useBoardAppearance();`.
  - Replace local hardcoded `ASSETS` in `Board.tsx` and `TsumegoBoard.tsx` with `loadBoardImages(boardStyle, stoneStyle)`.
  - Use `const [assetsVersion, setAssetsVersion] = useState(0);` with a `cancelled` flag in `useEffect([boardStyle, stoneStyle])`, and include `assetsVersion`, `boardStyle`, and `stoneStyle` in `renderBoard`'s dependency array (`I-2`).
  - Use `getBoardStylePalette(boardStyle)` for background fallback fill, grid lines, star points, and default coordinate labels (`M-2`).
  - Replace orphaned `src/galaxy/components/live/LiveBoard.tsx` and `src/galaxy/components/tsumego/TsumegoBoard.tsx` with clean re-exports of `../../../components/live/LiveBoard` and `../../../components/tsumego/TsumegoBoard` (`M-1`).

- [ ] **Step 2: Update 2D SVG Boards (`GoBoardSvg.tsx`, `MiniBoard.tsx`, `SGFBoard.tsx`, `OgsCourseBoard.tsx`)**
  - Subscribe to `const { boardStyle, stoneStyle } = useBoardAppearance();` in each component (`I-3`).
  - Replace `BOARD_ASSETS.board` and hardcoded wood fills/strokes (`#DEB887`, `#dcb468`, `#ogs-wood`) with `getBoardTextureDataUrl(boardStyle)` and `getBoardStylePalette(boardStyle)`.
  - Pass `stoneStyle` explicitly to every `stoneSpriteUrl(...)` call site.

- [ ] **Step 3: Update 3D Board & Stone Meshes (`BoardMesh.tsx`, `SolidWoodSlab.tsx`, `StoneMesh.tsx`, `stoneModel.ts`)**
  - In `BoardMesh.tsx` and `SolidWoodSlab.tsx`:
    - Subscribe to `const { boardStyle } = useBoardAppearance();` and call `invalidate()` on `boardStyle` change.
    - Support `'kaya'`, `'shin-kaya'`, `'bamboo'`, and `'walnut'` 3D procedural wood textures and grid/star colors.
    - Fix `BoardMesh.tsx` texture/material disposal by returning `{ materials, textures, allMaterials }` from `useMemo(..., [boardSize, solidWood, boardStyle])` and disposing them in `useEffect(() => () => { ... }, [resources])` (`C-1`).
  - In `stoneModel.ts` and `StoneMesh.tsx`:
    - Subscribe to `const { stoneStyle } = useBoardAppearance();` in `StoneMesh.tsx`, add `stoneStyle` to `material` `useMemo` dependencies (`C-2`), and call `invalidate()` when `stoneStyle` changes.
    - Implement cached static texture pools (max 8 variants per style, indexed by `variant % 8`) in `stoneModel.ts` for `'jade-agate'` (translucent chalcedony with warm caustic glow and `transmission: 0.52`, `ior: 1.544`, `clearcoat: 0.98`, `roughness: 0.07` + glossy black onyx) and `'yunzi'` (warm ivory porcelain + black with subtle emerald-teal rim sheen), plus `'minimal'` matte material (`M-4`).

- [ ] **Step 4: Run Board2D, Board3D, and Kiosk unit tests**
  - Run: `cd katrain/web/ui && npx vitest run src/components/Board3D/ src/components/board/ src/kiosk/`

---

### Task 4: Galaxy Two-Level Cascading Settings Menu (`GalaxySidebar.tsx` & `GalaxySidebar.test.tsx`)

**Files:**
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.test.tsx`

- [ ] **Step 1: Write unit tests in `GalaxySidebar.test.tsx`**
  - Verify clicking `设置` opens Level 1 with `语言`, `棋盘样式`, `棋子样式`, `中文字体` and their active summary labels.
  - Verify clicking `棋子样式` opens Level 2 with strictly 4 options (`蛤碁石`, `云子`, `玉石玛瑙`, `简约`), asserting `石材` and `星河` are absent, and clicking `玉石玛瑙` sets `stoneStyle` to `'jade-agate'`.
  - Verify clicking `棋盘样式` opens Level 2 with 4 options (`日式本榧`, `新榧云杉`, `碳化楠竹`, `胡桃沉香`) and clicking `胡桃沉香` sets `boardStyle` to `'walnut'`.
  - Verify clicking `中文字体` opens Level 2 with 4 options (`霞鹜楷体`, `楷体`, `隶书`, `黑体`) and clicking `楷体` sets `chineseFont` to `'kaiti'`.
  - Verify clicking the back header in Level 2 returns to Level 1, and closing the menu resets `settingsSubMenu` to `null`.

- [ ] **Step 2: Implement Two-Level Cascading Settings Menu in `GalaxySidebar.tsx`**
  - Implement Level 1 and Level 2 navigation in `GalaxySidebar.tsx` with visual wood swatches and dual-stone preview dots.

- [ ] **Step 3: Run `GalaxySidebar.test.tsx`**
  - Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/layout/GalaxySidebar.test.tsx`

---

### Task 5: Kiosk Settings Page Board & Stone Appearance Controls (`SettingsPage.tsx` & `SettingsPage.test.tsx`)

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`

- [ ] **Step 1: Add unit tests in `SettingsPage.test.tsx`**
  - Keep all existing tests (including the 6-group navigation invariant and absence of `'棋盘外观'` / `'对局默认值'`).
  - Add a test verifying `棋盘样式` and `棋子样式` segmented buttons render inside `实体棋盘` (`data-group="board"`) and clicking `玉石玛瑙` / `碳化楠竹` updates `getActiveStoneStyle()` / `getActiveBoardStyle()` and persists to `localStorage`.

- [ ] **Step 2: Implement `棋盘样式` and `棋子样式` in `SettingsPage.tsx`**
  - Subscribe directly to `useBoardAppearance()` in `SettingsPage.tsx` (`I-4`).
  - Add `棋盘样式` (`日式本榧`, `新榧云杉`, `碳化楠竹`, `胡桃沉香`) and `棋子样式` (`蛤碁石`, `云子`, `玉石玛瑙`, `简约`) `.kiosk-row` segmented controls inside the `实体棋盘` (`data-group="board"`) section.

- [ ] **Step 3: Run full Vitest suite and both production builds (`npm run build` & `npm run build:kiosk-2d`)**
  - Run: `cd katrain/web/ui && npx vitest run && npm run build && npm run build:kiosk-2d`
