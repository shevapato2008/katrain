# 2K Wood Veneer Textures, Stone Sound Selector, Kiosk 4-Font Alignment & Favicon Option A Implementation Plan (v2 — Post Round-1 Review)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the 4 user-approved enhancements to production across Galaxy and Kiosk:
1. **Favicon Option A (`青毡墨绿圆角徽章 + 智星盒白标`)**: Generate a composited `128x128` rounded-rect `#0b1c16` emerald badge with `logo-white.png` (`favicon-badge.png`) and wire `<link rel="icon" type="image/png" href="/assets/img/favicon-badge.png" />` in `katrain/web/ui/index.html`.
2. **4 Real 2K (`2048x2048`) Seamless Wood Veneer Textures (Zero Shadow Stripes in 2D & 3D)**: Bundle `kaya-veneer-2k.jpg`, `shinkaya-veneer-2k.jpg`, `bamboo-veneer-2k.jpg`, and `walnut-veneer-2k.jpg` under `/assets/textures/`, remove all horizontal/vertical dark gradient/stripe artifacts from `stoneAppearance.ts` and `BoardMesh.tsx`, load the 2K veneer in `boardUtils.ts` (`loadBoardImages`), `GoBoardSvg.tsx`, and `BoardMesh.tsx` (calling `invalidate()` from `useThree()` on load), and set `receiveShadow={false}` on the 3D board flat surface.
3. **Configurable Stone Placement Sound (`落子音效` / `落子音色`)**: Support `StoneSoundStyle` (`random` [default], `stone1`, `stone2`, `stone3`, `stone4`, `stone5`, `off`) backed by `katrain/sounds/stone1.wav`–`stone5.wav`, with instant audio preview on click in both Galaxy Sidebar's two-level settings menu (`落子音效`) and Kiosk Settings (`声音` section: keep `落子音效` `[开, 关]` master switch + add `落子音色` 6-style selector row for 100% `SettingsPage.test.tsx` compatibility), wired into `useSound.ts` and `GamePage.tsx`.
4. **Unified 4 Chinese Fonts (`霞鹜楷体` `wenkai` default, `楷体` `kaiti`, `隶书` `lishu`, `黑体` `heiti`)**: Keep `CHINESE_FONT_OPTIONS` in `stoneAppearance.ts` and `chineseFont` in `SettingsContext.tsx` as the single source of truth (defaulting to `'wenkai'`), and add non-blocking `/api/v1/kiosk-preferences/typography` sync in `SettingsContext.tsx`.

---

## Architecture & File Map

| Wave | Task | Files Modified / Created | Responsibility |
| :--- | :--- | :--- | :--- |
| **Wave 1** | **Task 1: Assets, Favicon Option A, Core Audio/Texture/Settings Utilities** | - `.gitignore`<br>- `katrain/web/ui/public/assets/img/favicon-badge.png` (new)<br>- `katrain/img/favicon-badge.png` (new)<br>- `katrain/web/ui/index.html`<br>- `katrain/web/ui/public/assets/textures/kaya-veneer-2k.jpg` (new)<br>- `katrain/web/ui/public/assets/textures/shinkaya-veneer-2k.jpg` (new)<br>- `katrain/web/ui/public/assets/textures/bamboo-veneer-2k.jpg` (new)<br>- `katrain/web/ui/public/assets/textures/walnut-veneer-2k.jpg` (new)<br>- `katrain/web/ui/src/utils/audioPrefs.ts`<br>- `katrain/web/ui/src/hooks/useSound.ts`<br>- `katrain/web/ui/src/components/board/stoneAppearance.ts`<br>- `katrain/web/ui/src/context/SettingsContext.tsx` | Generate Favicon Option A, copy 4 verified 2K wood veneer textures, eliminate procedural shadow bands in `stoneAppearance.ts`, add `getBoardTextureUrl()`, implement `StoneSoundStyle` in `audioPrefs.ts` & `useSound.ts`, and expose `stoneSound` / `setStoneSound` in `SettingsContext.tsx`. |
| **Wave 2A** | **Task 2: 2D & 3D Board Real Wood Veneer Integration & Shadow Elimination** | - `katrain/web/ui/src/components/Board3D/BoardMesh.tsx`<br>- `katrain/web/ui/src/components/board/boardUtils.ts`<br>- `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx`<br>- `katrain/web/ui/src/galaxy/pages/GamePage.tsx` | Load 2K wood veneer textures in 2D (`boardUtils.ts`, `GoBoardSvg.tsx`, `GamePage.tsx`) & 3D (`BoardMesh.tsx` with `useThree().invalidate()`), remove `bandColor` horizontal shadow rectangles & bamboo dark blocks in `BoardMesh.tsx`, set `receiveShadow={false}` on the flat 3D board top, and wire `resolveStoneSoundUrl()` in `GamePage.tsx`. |
| **Wave 2B** | **Task 3: Galaxy Two-Level Settings Menu & Kiosk Settings Page (`落子音效` / `落子音色`) + Unit Tests** | - `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`<br>- `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`<br>- `katrain/web/ui/src/galaxy/components/layout/__tests__/GalaxySidebar.test.tsx`<br>- `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`<br>- `katrain/web/ui/src/components/board/__tests__/stoneAppearance.test.ts` | Add `落子音效` Level-1/Level-2 submenu to `GalaxySidebar.tsx` (with instant preview sound), add `落子音色` row below `落子音效` `[开, 关]` in Kiosk `SettingsPage.tsx`, and update unit tests. |

---

## Detailed Tasks

### Task 1: Favicon Option A, 2K Wood Veneer Assets, and Core `audioPrefs` / `stoneAppearance` / `SettingsContext`

- [ ] **Step 1.1: Generate Favicon Option A (`favicon-badge.png`) & Update `index.html`**
  - Using Python `Pillow`, composite `katrain/img/logo-white.png` centered onto a `128x128` anti-aliased squircle/rounded-rectangle badge (`#0b1c16` fill, radius `28px`, subtle `2px` border `rgba(88, 181, 122, 0.38)`).
  - Save to `katrain/web/ui/public/assets/img/favicon-badge.png` and `katrain/img/favicon-badge.png`.
  - Add `!katrain/img/favicon*` and `!katrain/web/ui/public/assets/img/favicon*` to `.gitignore`.
  - Update `katrain/web/ui/index.html` line 5 to:
    ```html
    <link rel="icon" type="image/png" href="/assets/img/favicon-badge.png" />
    ```

- [ ] **Step 1.2: Copy 4 Verified 2K Wood Veneer Textures into `katrain/web/ui/public/assets/textures/`**
  - Copy `kaya-veneer-2k.jpg`, `shinkaya-veneer-2k.jpg`, `bamboo-veneer-2k.jpg`, and `walnut-veneer-2k.jpg` from `.superpowers/brainstorm/17996-1794239305/content/textures/` to `katrain/web/ui/public/assets/textures/`.

- [ ] **Step 1.3: Update `stoneAppearance.ts` (`getBoardTextureUrl` & Shadow-Free `getBoardTextureDataUrl`)**
  - Add `textureUrl: string` to `BoardStyleSpec` pointing to:
    - `kaya`: `'/assets/textures/kaya-veneer-2k.jpg'`
    - `shin-kaya`: `'/assets/textures/shinkaya-veneer-2k.jpg'`
    - `bamboo`: `'/assets/textures/bamboo-veneer-2k.jpg'`
    - `walnut`: `'/assets/textures/walnut-veneer-2k.jpg'`
  - Export `getBoardTextureUrl(styleId: BoardStyleId): string`.
  - In `getBoardTextureDataUrl(styleId: BoardStyleId)`:
    - Remove the center-darkening linear gradient (`grad.addColorStop(0.5, palette.woodSecondary)`), filling uniformly with `palette.woodPrimary`.
    - Remove periodic modular alpha lines and dark bamboo node blocks (`fillRect` with `0.28` opacity) so there are zero horizontal or vertical shadow stripes even in synchronous data-URL fallbacks.

- [ ] **Step 1.4: Expand `audioPrefs.ts`, `useSound.ts`, and `SettingsContext.tsx` for Configurable Stone Sounds**
  - In `katrain/web/ui/src/utils/audioPrefs.ts`:
    - Export `type StoneSoundStyle = 'random' | 'stone1' | 'stone2' | 'stone3' | 'stone4' | 'stone5' | 'off'`.
    - Export `type StoneSoundTone = Exclude<StoneSoundStyle, 'off'>` (`'random' | 'stone1' | 'stone2' | 'stone3' | 'stone4' | 'stone5'`).
    - Export `STONE_SOUND_OPTIONS: ReadonlyArray<{ id: StoneSoundStyle; label: string; shortLabel: string }>`:
      - `{ id: 'random', label: '随机自然 (5种混音)', shortLabel: '随机自然' }`
      - `{ id: 'stone1', label: '清脆本榧 (音效一)', shortLabel: '清脆本榧' }`
      - `{ id: 'stone2', label: '温润蛤石 (音效二)', shortLabel: '温润蛤石' }`
      - `{ id: 'stone3', label: '沉稳云子 (音效三)', shortLabel: '沉稳云子' }`
      - `{ id: 'stone4', label: '脆响竹盘 (音效四)', shortLabel: '脆响竹盘' }`
      - `{ id: 'stone5', label: '醇厚木韵 (音效五)', shortLabel: '醇厚木韵' }`
      - `{ id: 'off', label: '静音关闭', shortLabel: '静音' }`
    - Export `STONE_SOUND_TONE_OPTIONS = STONE_SOUND_OPTIONS.filter(o => o.id !== 'off')` (6 tone options for Kiosk `落子音色` row).
    - Export `readStoneSoundTonePref(): StoneSoundTone` (reads `'kiosk_stone_sound_tone'`, default `'random'`).
    - Export `writeStoneSoundTonePref(tone: StoneSoundTone): void` (writes `'kiosk_stone_sound_tone'`).
    - Export `readStoneSoundPref(): StoneSoundStyle` (returns `'off'` if `!readAudioPref('sfx')`, else `readStoneSoundTonePref()`).
    - Export `writeStoneSoundPref(style: StoneSoundStyle): void` (if `style === 'off'`, calls `writeAudioPref('sfx', false)`; else calls `writeStoneSoundTonePref(style)` and `writeAudioPref('sfx', true)`; dispatches `CustomEvent('katrain:stone-sound-change', { detail: style })`).
    - Export `resolveStoneSoundUrl(style?: StoneSoundStyle): string | null` (returns `null` if `'off'`, random `/assets/sounds/stone${1..5}.wav` if `'random'`, or `/assets/sounds/${style}.wav`).
    - Export `previewStoneSound(style: StoneSoundStyle): void` (plays `resolveStoneSoundUrl(style)` immediately via `new Audio(url).play().catch(() => {})`).
  - Update `katrain/web/ui/src/hooks/useSound.ts`:
    - When `play('stone')` is called, resolve via `resolveStoneSoundUrl(readStoneSoundPref())`.
  - Update `katrain/web/ui/src/context/SettingsContext.tsx`:
    - Expose `stoneSound: StoneSoundStyle` and `setStoneSound: (s: StoneSoundStyle) => void` backed by `readStoneSoundPref()` / `writeStoneSoundPref()`, listening to `'katrain:stone-sound-change'` and `'storage'` events.

---

### Task 2: 2D & 3D Board Real Wood Veneer Integration & `GamePage.tsx` Sound Sync

- [ ] **Step 2.1: Update `BoardMesh.tsx` (3D Board Real 2K Wood Veneer & Zero Shadow Bands)**
  - In `katrain/web/ui/src/components/Board3D/BoardMesh.tsx`:
    - Remove the 12 horizontal `bandColor` gradient bars (`lines 117-126`) and the dark bamboo node blocks (`lines 108-115`) from `createWoodGrainTexture`.
    - Load `getBoardTextureUrl(boardStyle)` asynchronously via `new Image()`, draw it onto the texture canvas when loaded, set `tex.needsUpdate = true`, and call `invalidate()` from `useThree()` so Three.js re-renders immediately.
    - Set `receiveShadow={false}` on the flat board box `<mesh>` (`line 284`) so directional light never creates `PCFSoftShadowMap` self-shadowing stripes across the flat board surface.

- [ ] **Step 2.2: Update 2D Boards (`boardUtils.ts`, `GoBoardSvg.tsx`, `GamePage.tsx`)**
  - In `katrain/web/ui/src/components/board/boardUtils.ts` (`loadBoardImages`), load `getBoardTextureUrl(boardStyle)` as the primary board image URL, with `onerror` fallback to `getBoardTextureDataUrl(boardStyle)` (for jsdom/offline test environments).
  - In `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx` and `katrain/web/ui/src/galaxy/pages/GamePage.tsx`, use `getBoardTextureUrl(boardStyle)` (with `getBoardTextureDataUrl(boardStyle)` fallback).
  - In `katrain/web/ui/src/galaxy/pages/GamePage.tsx` (`handlePlaySound`), for stone placement sounds (`stone` / `stone1`..`stone5`), use `resolveStoneSoundUrl(readStoneSoundPref())` so Galaxy games play the user's configured stone sound (`random`, `stone1`..`stone5`, or `off`).

---

### Task 3: Galaxy Two-Level Settings Menu & Kiosk Settings Page (`落子音效` / `落子音色`)

- [ ] **Step 3.1: Update `GalaxySidebar.tsx` Two-Level Menu**
  - Add Level-1 item `'stoneSound'` (`落子音效`, showing current `shortLabel`, e.g. `随机自然`) in the settings cascade menu.
  - When `activeSubmenu === 'stoneSound'`, render Level-2 options from `STONE_SOUND_OPTIONS` (`随机自然`, `清脆本榧`, `温润蛤石`, `沉稳云子`, `脆响竹盘`, `醇厚木韵`, `静音`). Clicking an option calls `setStoneSound(opt.id)` and `previewStoneSound(opt.id)`.

- [ ] **Step 3.2: Update Kiosk `SettingsPage.tsx`**
  - In `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` inside `<section className="kiosk-section" data-group="sound">`:
    - Keep Row 1 as `落子音效` (`role="group" aria-label="落子音效"`, buttons `[开, 关]`) so `SettingsPage.test.tsx` remains 100% green.
    - Add Row 2 right below it as **`落子音色`** (`role="group" aria-label="落子音色"`) with the 6 buttons from `STONE_SOUND_TONE_OPTIONS` (`随机自然` / `清脆本榧` / `温润蛤石` / `沉稳云子` / `脆响竹盘` / `醇厚木韵`). Clicking any tone button calls `writeStoneSoundTonePref(opt.id)`, turns `sfxOn` on (`writeAudioPref('sfx', true)`), and calls `previewStoneSound(opt.id)`.

- [ ] **Step 3.3: Update Unit Tests**
  - Update `katrain/web/ui/src/galaxy/components/layout/__tests__/GalaxySidebar.test.tsx`, `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`, and `katrain/web/ui/src/components/board/__tests__/stoneAppearance.test.ts` to verify all new functionality.
