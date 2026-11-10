# 2D/3D Board & Stone Styles, Galaxy Two-Level Settings Menu, and Kiosk Appearance Synchronization — Design Spec

- **Date**: 2026-11-10
- **Status**: Approved
- **Target Surfaces**: Galaxy Web UI (`/`) & Kiosk RK3568 UI (`/?mode=kiosk`)

## 1. Overview & Goals

1. **Browser Tab Favicon (`智星盒 · 围棋`)**:
   - Replace the default `/vite.svg` favicon in `katrain/web/ui/index.html` with the StellaBox Go logo (`/assets/img/logo-white.png`, `type="image/png"`).
2. **4 Curated Stone Styles (`StoneStyleId`) across 2D & 3D**:
   - Strictly include **only 4 stone styles** (`mineral-stone` 石材棋子 and `galaxy-star` 星河棋子 are permanently excluded):
     1. `clamshell-slate` (`蛤碁石`, with backward-compatible alias `'shell-slate'`): Hyuga Tokusei clamshell white stones with subtle diagonal growth lines (`32` sprite variants) + Nachi Kuroishi matte-satin black slate stones.
     2. `yunzi` (`云子`): Traditional Yunnan Yunzi — warm ivory-jade porcelain white stones + deep ink black stones with a subtle emerald-teal rim glow (`#10b981` / `#1f6f58`) under light.
     3. `jade-agate` (`玉石玛瑙`): High-translucency chalcedony white agate (`冰种白玛瑙`) with semi-transparent board/grid show-through (`alpha 0.84–0.92` in 2D, `transmission: 0.52`, `ior: 1.544`, `clearcoat: 0.98`, `roughness: 0.07` in 3D), lower-right lens caustic glow, sharp upper-left vitreous crescent highlight, and natural mineral tint/banding variation across stones + glossy black onyx agate (`黑曜玛瑙`).
     4. `minimal` (`简约`): High-contrast, zero-glare matte tournament stones for extended reading and review.
3. **4 Curated Board Wood Styles (`BoardStyleId`) across 2D & 3D**:
   - `kaya` (`日式本榧`): Warm golden Hon-Kaya with fine vertical masame straight grain.
   - `shin-kaya` (`新榧云杉`): Pale creamy Shin-Kaya spruce with delicate tight straight grain.
   - `bamboo` (`碳化楠竹`): Warm amber carbonized bamboo with laminated vertical strip joints and periodic bamboo nodes.
   - `walnut` (`胡桃沉香`): Eye-friendly dark walnut wood with low glare and tailored dark-walnut grid lines and star points.
4. **Galaxy Two-Level Cascading Settings Menu (`GalaxySidebar.tsx`)**:
   - Upgrade the bottom-left `设置` (`Settings`) menu in `GalaxySidebar.tsx` from a flat language list to a two-level cascading menu:
     - **Level 1**:
       1. `语言` (`Language`) → shows current language badge, opens Level 2 language list.
       2. `棋盘样式` (`Board Style`) → shows current board style badge, opens Level 2 with the 4 board wood styles + color swatch preview.
       3. `棋子样式` (`Stone Style`) → shows current stone style badge, opens Level 2 with the 4 stone styles + dual stone preview badge.
       4. `中文字体` (`Chinese Font`) → shows current Chinese font badge, opens Level 2 with 4 Chinese fonts (`霞鹜楷体` `wenkai`, `楷体` `kaiti`, `隶书` `lishu`, `黑体` `heiti`). Note: font size is omitted in Galaxy because browser keyboard zoom handles scaling.
5. **Kiosk Go Settings (`katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`)**:
   - Add `棋盘样式` and `棋子样式` segmented/pill selectors in Kiosk Settings (`实体棋盘` section or dedicated appearance controls) so Kiosk users can switch between the 4 board styles and 4 stone styles, persisted and shared via `localStorage`.
6. **Universal Reactive Synchronization Across All Preview & Active Boards**:
   - Every 2D Canvas board (`Board.tsx`, `LiveBoard.tsx`, `TsumegoBoard.tsx`), 2D SVG board (`GoBoardSvg.tsx`, `MiniBoard.tsx`, `SGFBoard.tsx`, `OgsCourseBoard.tsx`), and 3D WebGL board (`BoardMesh.tsx`, `SolidWoodSlab.tsx`, `StoneMesh.tsx`, `ReplayBoard3D.tsx`) must reactively re-render immediately when `boardStyle` or `stoneStyle` changes—including when previewing a match in **Galaxy Live (`LivePage.tsx`)**, **Galaxy Kifu Library (`KifuLibraryPage.tsx`)**, or **Kiosk Kifu Library (`KifuPage.tsx`)**.

## 2. Architecture & Build Boundary Invariants

- **Strict Kiosk 2D Bundle Boundary (`scripts/verify-kiosk.sh`)**:
  - `npm run build:kiosk-2d` verifies that the Kiosk 2D bundle contains **zero** `three` / `@react-three` imports and **zero** `galaxy/` imports.
  - Therefore, all shared appearance state, 2D stone sprite generators, and 2D wood grain generators live in `src/components/board/stoneAppearance.ts` and `src/components/board/boardUtils.ts` using pure TypeScript / HTML5 Canvas 2D without any `three` or `galaxy/` imports.
  - 3D material and procedural texture adaptation lives inside `src/components/Board3D/` (`StoneMesh.tsx`, `BoardMesh.tsx`, `SolidWoodSlab.tsx`).
- **Reactive Appearance Store (`stoneAppearance.ts`)**:
  - Maintain an external reactive store in `stoneAppearance.ts` (`getActiveStoneStyle`, `setActiveStoneStyle`, `getActiveBoardStyle`, `setActiveBoardStyle`, `subscribeBoardAppearance`, `useBoardAppearance`) backed by `localStorage` (`katrain_stone_style`, `katrain_board_style`).
  - Synchronize `SettingsContext.tsx` (`stoneStyle`, `setStoneStyle`, `boardStyle`, `setBoardStyle`, `chineseFont`, `setChineseFont`) with this store so both components reading `useSettings()` and lower-level board renderers calling `useBoardAppearance()` update synchronously on change.
