# 智星盒 StellaBox Kiosk UI 重开发 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the KaTrain kiosk web UI from the current web-shell (72px `NavigationRail` + 40px `StatusBar` + portrait fork) into the locked-in **direction ③ "Board Console"** design — a landscape-only 1024×600 shell (Header + bottom Dock + on-`/kiosk/play` SmartBoardConsole), reskinning all 8 modules to the slate/Anthropic design system, down-porting galaxy's Research analysis experience, and leaving clean stubs for the LED/camera physical-play track.

**Architecture:** A tightly-ordered **Phase A foundation** (fonts → theme+hex sweep → atomic orientation removal → new shell components + `ImmersiveContext` → shared primitives → geometry-workspace reskin) that every later task depends on; then **Phase B** independent module reskins (对弈 · 死活 · 棋谱 · 直播 · 教程 · 设置 · 摆谱); then **Phase C** the Research down-port (heaviest, new-build); then **Phase D** the 死活 physical 5-state stub. The whole track edits exactly **one** shared-territory file (`package.json`, for fonts) — everything else in shared territory is consume-only, so the galaxy build and the SBC dual-build boundary stay green throughout.

**Tech Stack:** React 19 + TypeScript + Vite + MUI (kiosk theme `src/kiosk/theme.ts`), `@fontsource` self-hosted fonts, vitest (jsdom) unit tests, react-router v6. Backend/engine unchanged. Board rendering via shared `components/Board.tsx` / `components/live/LiveBoard.tsx` / `components/tsumego/TsumegoBoard.tsx` (canvas, galaxy-identical, consume-only).

## Global Constraints

- **SBC dual-build contract (root CLAUDE.md):** two outputs — `web/static/` (`npm run build`) and `web/static-kiosk-2d/` (`npm run build:kiosk-2d`, chains `verify:kiosk-2d`). `src/kiosk/**` MUST NOT import `src/galaxy/**`, `components/Board3D/**`, or `pages/VideoRecorderPage*` (enforced by `eslint.config.js` no-restricted-imports).
- **Shared territory is consume-only.** Shared = `components/` (except `Board3D/`), `hooks/`, `context/`, `api.ts` + `api/`, `utils/`, `types/`, `src/theme.ts`, `i18n.ts`. The ONLY planned shared-territory edit in the whole track is `katrain/web/ui/package.json` (Task A1, fonts). Everything else in shared territory is imported unchanged. Drive read-only/preview/thinking/review behavior via EXISTING props (no-op `onMove`, `playerColor` gating, omitting `onIntersectionClick`) — never add props to a shared component. `src/kiosk/theme.ts` is **kiosk-only** (not the shared `src/theme.ts`).
- **No emoji in kiosk.** SBC ships no emoji font → 🎉/⚔️ render as 豆腐块 (tofu). Use `@mui/icons-material` SVG only (celebration = `EmojiEvents` trophy, not 🎉). Two live tofu bugs are fixed in Task B2.x (`SuccessOverlay` 🎉, `TsumegoCategoriesPage` CATEGORY_ICONS).
- **Landscape only.** 1024×600; portrait is deleted (Task A3). `OrientationContext`/`RotationWrapper` stay only for the 0°/180° panel-flip setting.
- **LED color semantics are fixed** via `src/kiosk/constants/ledColors.ts` (Task A4): 黑→红 `#ff3b30` · 白→绿 `#34c759` · 提子/拿除→蓝 `#2f6fff` · 提示/庆祝→白 `#ffffff`. 摆谱 and 死活-physical both consume this constant.
- **Brand:** Header shows "智星盒 StellaBox" text next to the existing (not-yet-redrawn) `logo-white.png`. The code-level 弈航/BoardNavi → StellaBox rename (galaxy + shared + i18n + tests + logo image + legal ToS) is a **separate track** (design.md §7.6) — do not chase it here.
- **Preserve all `data-testid`s and all hardware-留桩 advisory fall-throughs** (LedAPI failure → gray dot; capture 404 → advance) through every reskin.
- **Match the artifact.** Each module task visually matches its `superpowers/tracks/kiosk-ui-redesign/artifacts/*.html` mock at 1024×600.

## Verification Gate Matrix

Every task ends by running the gate(s) for the kind of change it made. All commands run from `katrain/web/ui/`.

| Gate | When | Commands |
|---|---|---|
| **K** (kiosk-only edit) | edits only under `src/kiosk/**` (incl. `kiosk/theme.ts`) | `npm run build:kiosk-2d` (chains `verify:kiosk-2d`) · `npm run lint` · `npx vitest run <file>` |
| **S** (shared-territory EDIT) | any **EDIT** to a shared-territory file (merely *consuming* an already-kiosk-bundled shared file is **Gate K**, not S) | Gate K **plus** `npm run build` (full/galaxy green) |
| **R** (research / galaxy-adjacent) | Phase C down-port | `npm run lint` **first** (import boundary) → Gate S → rewritten vitest |
| **E** (emoji / i18n) | emoji-tofu fixes, language wiring | `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" src/kiosk` returns nothing → builds |
| **Runtime** | any user-visible flow | `python -m katrain --ui web --force-build` → drive the route at 1024×600 → compare to the named artifact |

> CI (`.github/workflows/kiosk_build.yml`) runs `build:kiosk-2d` on every PR touching `katrain/web/ui/**` — the enforced merge gate.

## Shared Interface Contracts

These names/paths are fixed so tasks stay type-consistent across phases.

- **Theme tokens** (`src/kiosk/theme.ts`, Task A2): `background.default #0f1416` · `background.paper #18211f` · `divider #2b3a35` · `text.primary #eef3f1` · `text.secondary #93a49d` · `text.disabled #5f716b` · `primary.main #58b57a` · `primary.dark #26463a` · **`warning.main #e0a24a`** (the single amber token; 进行中/待校准/继续/物理提示 all consume `theme.warning.main`) · `error.main #e2685c` · CSS var `--raise2:#1d2725`. Fonts: `typography.fontFamily "'Hanken Grotesk','Noto Sans SC',sans-serif"`; brand serif stack `"'Newsreader','Noto Serif SC',serif"`.
- **ImmersiveContext** (`src/kiosk/context/ImmersiveContext.tsx`, Task A6): `useImmersive(): { immersive: boolean; setImmersive(v: boolean): void }` + `<ImmersiveProvider>` (mounted in `KioskLayout`, Task A10). A page hides Dock + console via `useEffect(() => { setImmersive(true); return () => setImmersive(false); }, [])`.
- **LED colors** (`src/kiosk/constants/ledColors.ts`, Task A4): `type LedIntent = 'black'|'white'|'remove'|'hint'`; `LED_HEX: Record<LedIntent,string>`; `LED_LABEL: Record<LedIntent,string>` (values above).
- **Active-session store** (`src/kiosk/utils/activeSession.ts`, Task A5): `type ActiveSessionKind='game'|'practice'`; `interface ActiveSession { kind; label; route; ts }`; `readActiveSession(kind)`, `writeActiveSession(s)`, `clearActiveSession(kind)`; keys `kiosk_active_game`/`kiosk_active_practice`. 对弈「继续上一局」+ 死活「继续练习」both consume it.
- **Physical-tsumego** (Phase D): indirection `src/kiosk/hooks/usePhysicalTsumego.ts` re-exports `usePhysicalTsumego.stub.ts` (physical track swaps one line). `type PhysicalTsumegoPhase='off'|'clearing'|'setup'|'ready'|'replying'|'removing'|'solved'|'clearing_next'`; `interface PhysicalTsumegoState { phase; setupProgress?; removalList: [number,number][]; ledIntent: { intent: LedIntent|null; points: [number,number][] } }`; `interface UsePhysicalTsumego extends PhysicalTsumegoState { enabled; enable(); disable(); __devSetPhase? }`. Persistence in `tsumegoUnits.ts`: key `kiosk_tsumego_physical`, `readPhysicalMode()`(default false)/`writePhysicalMode(v)`.
- **Settings language**: 中→'cn', 英→'en' via `useSettings().setLanguage`; value from `useSettings().language` (SettingsContext already wires i18n; do not rebuild it).

## Phase & Dependency Order

```
Phase A (foundation — land in ID order; A1→A13)
  A1  fonts (package.json)            ── Gate S
  A2  theme re-token + hex sweep      ── Gate K   (single owner of kiosk/theme.ts + the amber token)
  A3  orientation sweep (ATOMIC)      ── Gate K   (isPortrait removal: 9 pages + 14 test mocks in ONE task)
  A4  ledColors.ts                    ── Gate K
  A5  activeSession.ts                ── Gate K
  A6  ImmersiveContext.tsx            ── Gate K
  A7  Header  A8 Dock  A9 SmartBoardConsole
  A10 KioskLayout rewrite + navTabs icons + delete StatusBar/NavigationRail/TopTabBar
  A11 immersive wiring (TsumegoProblemPage)
  A12 LoginPage reskin + logout→login redirect contract
  A13 GeometryCalibrationWorkspace reskin (EARLY — 死活/摆谱 guards + 对弈 state-B inherit it)
        │
        ▼
Phase B (module reskins — mutually independent, any order after A)
  B1 对弈    B2 死活(reskin+toggle seam)   B3 棋谱   B4 直播   B5 教程   B6 设置   B7 摆谱
        │
        ▼
Phase C (research down-port — self-contained; C1.* then post-C kifu retarget)
        │
        ▼
Phase D (死活 physical 5-state stub — consumes B2 seam + A4 ledColors; read sibling worktree first)
```

**Couplings that shaped this order (from the map + adversarial critique):**
- Everything depends on Phase A (theme token + orientation type + shell + immersive mechanism). The isPortrait removal is atomic because 9 pages + 18 test mocks reference it — splitting it reddens the build.
- `kiosk/theme.ts` and `navTabs.tsx` each have a **single owner** (A2 and A10) to avoid three tasks editing the same file with divergent amber/icon assumptions.
- 棋谱's「在研究中打开」keeps its **existing** `GamePage` target in Phase B (works today); the retarget to the new Research entry is an isolated **post-Phase-C** task — no cycle (Research does not depend on 棋谱).
- 摆谱 is a **pure reskin in Phase B**, not a Phase-D stub — it is fully built with hardware-留桩; its only extra dependency is A13's reskinned geometry guard.
- The tsumego physical work splits: B2 ships the **default-OFF toggle seam** (zero physical UI visible); D1 builds the **stub machine + 5-state panel** behind the indirection file, after the sibling-worktree contract is confirmed.

---

---

## Phase A — Foundation

> Land in ID order **A1 → A13**. This is the shared base every later phase depends on. Three files are single-owner/atomic by design: `kiosk/theme.ts` + the amber token (A2), the `isPortrait` removal across 9 pages + 14 test mocks (A3), and `navTabs.tsx` icons (A10). Design specs: `design.md §4`.

---

### Task A1: Add Newsreader + Hanken Grotesk fontsource dependencies

**Files:**
- Modify: `katrain/web/ui/package.json` (dependencies block, lines 16–31 — current `@fontsource/*` entries are `@fontsource/jetbrains-mono` line 19, `@fontsource/noto-sans-sc` line 20)
- Modify (auto): `katrain/web/ui/package-lock.json` (written by `npm install`)

**Interfaces:**
- Consumes: nothing.
- Produces: npm packages `@fontsource/newsreader` and `@fontsource/hanken-grotesk` resolvable for `import '@fontsource/<pkg>/{400,500,600}.css'` — consumed by A2. This is the **single shared-territory edit** of the whole track (root CLAUDE.md: package.json is shared → Gate S).

- [ ] **Step 1: Install both fontsource packages (weights 400/500/600 ship inside each package).** From `katrain/web/ui`, run `npm install --save @fontsource/newsreader@^5 @fontsource/hanken-grotesk@^5`. This adds two `dependencies` entries and updates `package-lock.json`; npm writes the resolved `^5.x` caret range (matching the existing `@fontsource/*` `^5.2.x` style).
- [ ] **Step 2: Verify the resulting `dependencies` block is alpha-ordered.** Confirm the `@fontsource/*` run reads: `@fontsource/hanken-grotesk` → `@fontsource/jetbrains-mono` (existing `^5.2.8`) → `@fontsource/newsreader` → `@fontsource/noto-sans-sc` (existing `^5.2.9`). If npm appended them out of order, reorder with an Edit so the block stays sorted (no functional effect, keeps the diff clean).
- [ ] **Step 3: Confirm the weight CSS files exist on disk** (A2 depends on them): `ls node_modules/@fontsource/newsreader/400.css node_modules/@fontsource/newsreader/500.css node_modules/@fontsource/newsreader/600.css node_modules/@fontsource/hanken-grotesk/400.css node_modules/@fontsource/hanken-grotesk/500.css node_modules/@fontsource/hanken-grotesk/600.css` — all six must resolve. (Both packages ship these static weights; if a weight is missing the package layout changed and A2's import list must match what exists.)
- [ ] **Step 4: Run the verification gates — Gate S** (shared-territory edit → both builds must stay green). From `katrain/web/ui`: `npm run lint`, then `npm run build` (full/galaxy green — proves the new deps don't perturb the full graph), then `npm run build:kiosk-2d` (chains `verify:kiosk-2d`; kiosk boundary clean), then a smoke `npx vitest run src/kiosk/__tests__/theme.test.ts` (theme still imports only the old fonts here, so it stays green). All four must pass.
- [ ] **Step 5: Commit.** `git add package.json package-lock.json && git commit` with message `chore(kiosk-ui): add Newsreader + Hanken Grotesk fontsource deps (A1)` ending with the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

---

### Task A2: Slate theme re-token + coordinated hardcoded-hex sweep

**Files:**
- Modify: `katrain/web/ui/src/kiosk/theme.ts` (full rewrite, current lines 1–79)
- Modify: `katrain/web/ui/src/kiosk/__tests__/theme.test.ts` (rewrite assertions, lines 5–41)
- Modify (sweep, hex→token): `katrain/web/ui/src/kiosk/components/layout/TopTabBar.tsx` (L26), `.../layout/RotationSelector.tsx` (L76), `.../layout/NavigationRail.tsx` (L29), `.../game/PlatformTimer.tsx` (L47), `.../game/ItemToggle.tsx` (L22, L26), `.../tsumego/SuccessOverlay.tsx` (L39), `.../tsumego/ProblemCard.tsx` (L49, L51, L85, L92), `.../tsumego/ProgressDots.tsx` (L41), `.../pages/TutorialBooksPage.tsx` (L120), `.../pages/TsumegoCategoriesPage.tsx` (L130, L131, L134, L143), `.../pages/BaipuSessionPage.tsx` (L106, L392), `.../pages/ResearchPage.tsx` (L65), `.../pages/BaipuListPage.tsx` (L295), `.../pages/TsumegoPage.tsx` (L83), `.../pages/TsumegoLevelPage.tsx` (L100, L101), `.../pages/KifuPage.tsx` (L300), `.../pages/TutorialCategoriesPage.tsx` (L102), `.../pages/TutorialBookDetailPage.tsx` (L23), `.../pages/TsumegoUnitsPage.tsx` (L142, L163)
- Modify (sweep test expectations): `katrain/web/ui/src/kiosk/__tests__/tsumego-components.test.tsx` (L23–25), `katrain/web/ui/src/kiosk/__tests__/TsumegoLevelPage.test.tsx` (L187–188)

**Interfaces:**
- Consumes: A1 fonts (`@fontsource/newsreader`, `@fontsource/hanken-grotesk`).
- Produces: `kioskTheme` with the §4.3 slate palette + single amber token `warning.main=#e0a24a` + Newsreader/Hanken font stacks + CSS var `--raise2:#1d2725` (via `MuiCssBaseline`). Every kiosk file consumes these tokens instead of warm literals. Kiosk-only → **Gate K**.

- [ ] **Step 1: Rewrite `theme.ts` to the slate palette + fonts + `--raise2`.** Replace the whole file with the following (real, load-bearing code):
  ```ts
  import { createTheme } from '@mui/material';

  // Self-hosted fonts via @fontsource — no CDN dependency
  import '@fontsource/noto-sans-sc/400.css';
  import '@fontsource/noto-sans-sc/600.css';
  import '@fontsource/noto-sans-sc/700.css';
  import '@fontsource/jetbrains-mono/400.css';
  import '@fontsource/jetbrains-mono/500.css';
  import '@fontsource/newsreader/400.css';
  import '@fontsource/newsreader/500.css';
  import '@fontsource/newsreader/600.css';
  import '@fontsource/hanken-grotesk/400.css';
  import '@fontsource/hanken-grotesk/500.css';
  import '@fontsource/hanken-grotesk/600.css';

  const SANS = "'Hanken Grotesk','Noto Sans SC',sans-serif";
  const SERIF = "'Newsreader','Noto Serif SC',serif"; // brand + greeting h1
  const MONO = "'JetBrains Mono',monospace";           // clock / metrics

  export const kioskTheme = createTheme({
    palette: {
      mode: 'dark',
      primary:   { main: '#58b57a', light: '#7ec994', dark: '#26463a' }, // jade / jade-deep
      secondary: { main: '#caa66f' }, // §4.3 --wood (board fallback)
      background: { default: '#0f1416', paper: '#18211f' }, // --slate / --raise
      text:      { primary: '#eef3f1', secondary: '#93a49d', disabled: '#5f716b' }, // ice/sub/dim
      divider:   '#2b3a35', // --hair
      success:   { main: '#58b57a' },
      warning:   { main: '#e0a24a' }, // THE single amber token
      error:     { main: '#e2685c' },
      info:      { main: '#5b9bd5' },
    },
    typography: {
      fontFamily: SANS,
      fontSize: 16,
      h1: { fontFamily: SERIF, fontWeight: 500 }, // brand / greeting
      h2: { fontFamily: SANS, fontWeight: 600 },
      h3: { fontFamily: SANS, fontWeight: 600 },
      h4: { fontFamily: SANS, fontWeight: 600 },
      h5: { fontFamily: SANS, fontWeight: 600 },
      h6: { fontFamily: SANS, fontWeight: 600 },
      body1: { fontFamily: SANS, fontSize: 16 },
      body2: { fontFamily: SANS, fontSize: 14 },
      button: { fontFamily: SANS, fontWeight: 600 },
      caption: { fontFamily: MONO, fontSize: 12 },
    },
    shape: { borderRadius: 12 },
    components: {
      MuiCssBaseline: {
        styleOverrides: { ':root': { '--raise2': '#1d2725' } },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none' as const,
            borderRadius: '12px',
            padding: '12px 24px',
            fontSize: '1rem',
            transition: 'transform 100ms ease-out, background-color 150ms',
            '&:active': { transform: 'scale(0.96)' },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: { minWidth: 48, minHeight: 48, '&:active': { transform: 'scale(0.96)' } },
        },
      },
      MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
    },
  });
  ```
- [ ] **Step 2: Fix the theme unit test (assertions now reference the slate tokens).** In `__tests__/theme.test.ts` update: `background.default` → `'#0f1416'`; `primary.main` → `'#58b57a'`; `error.main` → `'#e2685c'`; `text.secondary` → `'#93a49d'`; the `fontFamily` assertion → `.toContain('Hanken Grotesk')`; the headings assertion → `expect((kioskTheme.typography.h1 as any).fontFamily).toContain('Newsreader')` and `h3` → `.toContain('Hanken Grotesk')`. Add two assertions: `warning.main === '#e0a24a'` (the single amber token) and `text.primary === '#eef3f1'`. Keep the two existing behavioral assertions unchanged (MuiButton has no `minHeight`; MuiIconButton `minWidth/minHeight === 48`).
- [ ] **Step 3: Apply the sweep mapping in every `sx`/`bgcolor`/`color` usage.** Use this fixed table (hex → MUI theme token). For `sx` string form use the token string; for alpha tints import `import { alpha } from '@mui/material/styles'` and read `const theme = useTheme()` (`import { useTheme } from '@mui/material'`) inside the component:

  | old literal | replacement |
  |---|---|
  | `#1a1714` | `'background.default'` |
  | `#252019` | `'background.paper'` |
  | `#0f0f0f` (board wells) | `'background.default'` (darkest surface = `--slate #0f1416`) |
  | `#5cb57a` | `'primary.main'` |
  | `#c49a3c` | `'warning.main'` |
  | `#c45d3e` | `'error.main'` |
  | `rgba(92,181,122,α)` | `alpha(theme.palette.primary.main, α)` |
  | `rgba(196,93,62,α)` | `alpha(theme.palette.error.main, α)` |
  | `rgba(232,228,220,0.18)` (ProgressDots empty dot) | `'divider'` |

  Apply to the pure-`sx` sites: `TopTabBar.tsx:26`, `RotationSelector.tsx:76`, `NavigationRail.tsx:29`, `PlatformTimer.tsx:47`, `ItemToggle.tsx:22,26`, `TsumegoCategoriesPage.tsx:130,131,134,143`, `BaipuSessionPage.tsx:106,392`, `ResearchPage.tsx:65` (only the `bgcolor:'#0f0f0f'` — the `...(isPortrait…)` on that line is A3's), `BaipuListPage.tsx:295`, `KifuPage.tsx:300`, `TsumegoPage.tsx:83`, `TutorialBooksPage.tsx:120`, `TutorialCategoriesPage.tsx:102`, `ProgressDots.tsx:41`, `TsumegoUnitsPage.tsx:142,163`.
- [ ] **Step 4: Convert the four helper/return-color sites to `useTheme()` reads (no literals leak).** `ProblemCard.tsx` — add `const theme = useTheme()`; the border-color helper returns `theme.palette.primary.main` (was `#5cb57a` L49) / `theme.palette.warning.main` (was `#c49a3c` L51); L85 `color:'#c49a3c'` → `'warning.main'`; L92 `'#c45d3e'` → `'error.main'`. `TsumegoLevelPage.tsx` — the color helper (L100 `#5cb57a`, L101 `#c49a3c`): read `useTheme()` and return `theme.palette.primary.main` / `theme.palette.warning.main`.
- [ ] **Step 5: Handle the two module-level constant sites (outside render — flip the literal, no token hook available).** `TutorialBookDetailPage.tsx:23` `const JADE = '#5cb57a'` → delete the const and replace its `sx` usages with `'primary.main'` (grep `JADE` in that file to catch every usage). `SuccessOverlay.tsx:39` `CONFETTI_COLORS` — flip the three swept members to the new palette values so no warm literal survives: `'#5cb57a'`→`'#58b57a'`, `'#c49a3c'`→`'#e0a24a'`, `'#c45d3e'`→`'#e2685c'` (leave `'#5b9bd5'` info and `'#7ec994'` primary-light — not in the sweep; decorative confetti array stays a module const).
- [ ] **Step 6: Update the two sweep-affected component tests' expected rgb() values.** New jade `#58b57a` = `rgb(88, 181, 122)`; new amber `#e0a24a` = `rgb(224, 162, 74)`. In `__tests__/tsumego-components.test.tsx` L23–25 set `FILLED`/`GREEN` → `'rgb(88, 181, 122)'`, `AMBER` → `'rgb(224, 162, 74)'`. In `__tests__/TsumegoLevelPage.test.tsx` L187 → `'border-color: rgb(88, 181, 122)'`, L188 → `'border-color: rgb(224, 162, 74)'`.
- [ ] **Step 7: Confirm the warm→cold flip is total.** Re-run the enumeration grep and expect only `theme.ts` (definition) + `SuccessOverlay.tsx` (decorative confetti values, now the new hexes) to remain: `grep -rnE "#1a1714|#252019|#0f0f0f|#5cb57a|#c49a3c|#c45d3e|rgba\(92, ?181, ?122" src/kiosk --include="*.tsx" --include="*.ts"` — the app must not be left half-migrated (no warm literal in any consumer `sx`). Also `grep -n "#8b7355" src/kiosk/theme.ts` returns nothing (wood-amber replaced by `#caa66f`).
- [ ] **Step 8: Run the verification gates — Gate K** (kiosk-only). From `katrain/web/ui`: `npx vitest run src/kiosk` (full kiosk unit suite — theme + every swept component test green), `npm run lint`, `npm run build:kiosk-2d` (chains `verify:kiosk-2d`). Then **Runtime**: `python -m katrain --ui web --force-build`, drive `/kiosk/play` at 1024×600, and confirm the shell reads cold-slate (background `#0f1416`, jade `#58b57a`, amber accents `#e0a24a`) matching `superpowers/tracks/kiosk-ui-redesign/artifacts/d3-board-console.html` — no residual warm brown.
- [ ] **Step 9: Commit.** `git commit` all touched files with message `refactor(kiosk-ui): slate re-token + Newsreader/Hanken fonts + hardcoded-hex sweep (A2)` and the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

---

### Task A3: Orientation sweep — landscape-only (ONE atomic task)

**Files:**
- Modify: `katrain/web/ui/src/kiosk/context/OrientationContext.tsx` (full rewrite, lines 1–41)
- Modify: `katrain/web/ui/src/kiosk/components/layout/RotationWrapper.tsx` (STYLES, lines 4–9)
- Delete: `katrain/web/ui/src/kiosk/components/layout/RotationSelector.tsx` and its test `katrain/web/ui/src/kiosk/__tests__/RotationSelector.test.tsx` (confirmed: **no non-test importer**)
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` (OptionChips options, lines 40–45)
- Modify (collapse `isPortrait` → landscape): `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx` (L13, L27–47), `.../pages/GamePage.tsx` (L25, L201–202), `.../pages/ResearchPage.tsx` (L26, L63, L65, L116), `.../pages/BaipuListPage.tsx` (L31, L158, L160, L296), `.../pages/TsumegoProblemPage.tsx` (L43, L234, L238), `.../pages/KifuPage.tsx` (L24, L137, L139, L301), `.../pages/TutorialSectionPage.tsx` (L48, L277), `.../pages/LivePage.tsx` (L17, L65, L69), `.../pages/LiveMatchPage.tsx` (L34, L115, L119, L141)
- Modify (test mocks/rewrites): `__tests__/OrientationContext.test.tsx`, `__tests__/orientation.integration.test.tsx`, `__tests__/KioskLayout.test.tsx` (rewrites); strip `isPortrait: false,` from the mock in `__tests__/GamePageEngine.test.tsx:9`, `NavigationRail.test.tsx:15`, `KifuPage.test.tsx:16`, `GamePage.test.tsx:9`, `TopTabBar.test.tsx:15`, `LivePage.test.tsx:20`, `SettingsPage.test.tsx:10`, `KioskApp.test.tsx:12`, `ResearchPage.test.tsx:10`, `LiveMatchPage.test.tsx:9`, `GamePageLedBadge.test.tsx:9`, `KioskAuth.test.tsx:9`, `TsumegoProblemPage.test.tsx:20`, and `pages/TutorialSectionPage.test.tsx:19`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Rotation = 0 | 180`; `useOrientation(): { rotation: Rotation; setRotation(r: Rotation): void }` (**`isPortrait` removed**). `readStored()` migrates stale `90`/`270` in localStorage → `0`. Kiosk-only, but many files change → **Gate K with full kiosk vitest**.

> **Note (file-list is a hint, not authoritative):** the consumer/test file lists + line numbers above are a snapshot. **Regenerate the authoritative list at execution time** with `rg 'isPortrait' src` and edit exactly what it reports — do not trust the cited lines if the tree has drifted.

- [ ] **Step 1: Rewrite `OrientationContext.tsx` — drop `isPortrait`, narrow `Rotation`, migrate stale values.** Replace the file with:
  ```tsx
  import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

  export type Rotation = 0 | 180;

  interface OrientationContextType {
    rotation: Rotation;
    setRotation: (rotation: Rotation) => void;
  }

  const OrientationContext = createContext<OrientationContextType | undefined>(undefined);

  const STORAGE_KEY = 'katrain_kiosk_rotation';
  const VALID: Rotation[] = [0, 180];

  // Clamp: stale 90/270 (portrait, removed 2026-07-06) or garbage → 0, and rewrite storage.
  const readStored = (): Rotation => {
    const v = Number(localStorage.getItem(STORAGE_KEY));
    if (VALID.includes(v as Rotation)) return v as Rotation;
    localStorage.setItem(STORAGE_KEY, '0');
    return 0;
  };

  export const OrientationProvider = ({ children }: { children: ReactNode }) => {
    const [rotation, setRotationState] = useState<Rotation>(readStored);
    const setRotation = useCallback((r: Rotation) => {
      setRotationState(r);
      localStorage.setItem(STORAGE_KEY, String(r));
    }, []);
    return (
      <OrientationContext.Provider value={{ rotation, setRotation }}>
        {children}
      </OrientationContext.Provider>
    );
  };

  export const useOrientation = () => {
    const ctx = useContext(OrientationContext);
    if (!ctx) throw new Error('useOrientation must be used within an OrientationProvider');
    return ctx;
  };
  ```
- [ ] **Step 2: Trim `RotationWrapper.tsx` STYLES to `0 | 180`** (preserve `data-testid="rotation-wrapper"`). Replace the `STYLES` record (L4–9) with only the two landscape rows:
  ```ts
  const STYLES: Record<Rotation, { transform: string; width: string; height: string }> = {
    0:   { transform: '',                                       width: '100vw', height: '100vh' },
    180: { transform: 'rotate(180deg) translate(-100%, -100%)', width: '100vw', height: '100vh' },
  };
  ```
- [ ] **Step 3: Delete `RotationSelector.tsx` + `RotationSelector.test.tsx`.** Grep first to prove safety: `grep -rn "RotationSelector\|rotation-selector-button" src` returns only these two files → `git rm` both. (Rotation control now lives solely in SettingsPage OptionChips.)
- [ ] **Step 4: Trim `SettingsPage.tsx` rotation OptionChips to two landscape options** (L40–45). Replace the `options` array with exactly:
  ```tsx
  options={[
    { value: 0 as Rotation, label: '0° 横屏' },
    { value: 180 as Rotation, label: '180° 横屏翻转' },
  ]}
  ```
  (Leave the `useOrientation`/`type Rotation` import and `rotation`/`setRotation` usage intact — both still exist.)
- [ ] **Step 5: Collapse the `isPortrait` branch in `KioskLayout.tsx` to the landscape shell.** Remove `const { isPortrait } = useOrientation();` (L13) and the whole `useOrientation` import (L6 — no longer used here). Delete the `{isPortrait ? ( …TopTabBar… ) : ( …NavigationRail… )}` ternary (L27–47), keeping only the `NavigationRail` branch body: the `<Box sx={{ display:'flex', flex:1, overflow:'hidden' }}>` containing `<NavigationRail />` + the `<Box component="main">` Outlet. Drop the now-unused `TopTabBar` import (L5). (TopTabBar.tsx stays on disk with its own test — not in this task's scope; Dock replacement is Phase B.)
- [ ] **Step 6: Collapse `isPortrait` in the 8 consumer pages using one deterministic rule: take the `false` (landscape) side.** For each page, delete the `const { isPortrait } = useOrientation();` line and the `useOrientation` import if it becomes unused, then transform (read the 3–8 line block at each cited line first to capture its exact braces):
  - `flexDirection: isPortrait ? 'column' : 'row'` → `flexDirection: 'row'`
  - `...(isPortrait && { maxHeight: '50%' })` → remove the spread entirely
  - any `isPortrait ? <portraitValue> : <landscapeValue>` → keep only `<landscapeValue>`
  Sites: `GamePage.tsx` L201 (flexDirection), L202 (`sx={isPortrait ? {…} : { height:'100%', aspectRatio:'1' }}` → keep the landscape object); `ResearchPage.tsx` L63 (flexDirection), L65 (drop spread), L116 (keep landscape side); `BaipuListPage.tsx` L158, L160, L296 (`isPortrait ? {borderTop…} : {borderLeft…}` → keep `borderLeft`); `TsumegoProblemPage.tsx` L234, L238; `KifuPage.tsx` L137, L139, L301; `TutorialSectionPage.tsx` L277; `LivePage.tsx` L65, L69; `LiveMatchPage.tsx` L115, L119, L141 (`borderLeft: isPortrait ? 'none' : '1px solid'` → `'1px solid'`; `borderTop: isPortrait ? '1px solid' : 'none'` → `'none'`).
- [ ] **Step 7: Rewrite the three assertion-dependent tests.** `__tests__/OrientationContext.test.tsx`: drop the `is-portrait` span and the `isPortrait` destructure from `TestConsumer`; remove the `set-90` button; keep "defaults to 0", "setRotation persists (use 180)", "ignores invalid → 0"; add a test `'migrates stale 90 to 0 and rewrites storage'` — `localStorage.setItem(STORAGE_KEY,'90'); render(...); expect(getByTestId('rotation').textContent).toBe('0'); expect(localStorage.getItem(STORAGE_KEY)).toBe('0')`. `__tests__/orientation.integration.test.tsx`: remove the `set-90`/`set-270` buttons and every `is-portrait` assertion; change the "persisted 90/270" cases to assert they read back as `'0'`; keep the 0↔180 round-trip. `__tests__/KioskLayout.test.tsx`: replace the `mockUseOrientation.mockReturnValue({ isPortrait })` pattern — mock `useOrientation` as `() => ({ rotation: 0, setRotation: vi.fn() })`; delete the portrait test (L38–46); keep one landscape test asserting `getByText('弈航')` (branding unchanged — rename is a separate track), `getByText('对弈')`, `getByText('设置')`, `PLAY_CONTENT`, and `getByRole('navigation')`.
- [ ] **Step 8: Strip `isPortrait: false,` from the 14 pass-through mock factories** (they compile either way, but the mock should match the real hook shape `{ rotation, setRotation }`): edit each cited `useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: vi.fn() })` to `useOrientation: () => ({ rotation: 0, setRotation: vi.fn() })` in the 14 files listed under **Files** (GamePageEngine, NavigationRail, KifuPage, GamePage, TopTabBar, LivePage, SettingsPage, KioskApp, ResearchPage, LiveMatchPage, GamePageLedBadge, KioskAuth, TsumegoProblemPage, pages/TutorialSectionPage.test).
- [ ] **Step 9: Prove `isPortrait` is fully eliminated.** `grep -rn "isPortrait" src` returns **nothing**. `grep -rn "\b90\b\|\b270\b" src/kiosk/context src/kiosk/components/layout/RotationWrapper.tsx src/kiosk/pages/SettingsPage.tsx` shows no residual portrait rotation.
- [ ] **Step 10: Run the verification gates — Gate K (full kiosk vitest, many files changed).** From `katrain/web/ui`: `npx vitest run src/kiosk` (whole kiosk suite green, incl. rewritten orientation + layout tests), `npm run lint` (no unused-import errors from the removed `useOrientation` imports), `npm run build:kiosk-2d` (chains `verify:kiosk-2d`). Then **Runtime**: `python -m katrain --ui web --force-build`, load `/kiosk/settings` at 1024×600, confirm the Screen-Rotation control shows exactly `0° 横屏` / `180° 横屏翻转` and toggling 180° flips the shell (via `RotationWrapper`) without portrait reflow.
- [ ] **Step 11: Commit.** `git add -A && git commit` with message `refactor(kiosk-ui): landscape-only orientation sweep — drop isPortrait, Rotation=0|180 (A3)` and the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

---

### Task A4: Shared primitive — LED color constants

**Files:**
- Create: `katrain/web/ui/src/kiosk/constants/ledColors.ts`
- Create: `katrain/web/ui/src/kiosk/__tests__/ledColors.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `type LedIntent = 'black'|'white'|'remove'|'hint'`; `LED_HEX: Record<LedIntent,string>`; `LED_LABEL: Record<LedIntent,string>`. Consumed later by physical-play/tsumego/baipu LED badges and `usePhysicalTsumego` (Phase D). New file, no galaxy import → **Gate K**.

- [ ] **Step 1: Write `constants/ledColors.ts` exactly per the shared contract** (fixed LED color semantics: black→red, white→green, remove→blue, hint→white):
  ```ts
  /** Fixed LED colour semantics for physical play / tsumego / baipu (§5.2, §5.5). */
  export type LedIntent = 'black' | 'white' | 'remove' | 'hint';

  export const LED_HEX: Record<LedIntent, string> = {
    black: '#ff3b30',  // 红
    white: '#34c759',  // 绿
    remove: '#2f6fff', // 蓝
    hint: '#ffffff',   // 白 (提示 / 庆祝)
  };

  export const LED_LABEL: Record<LedIntent, string> = {
    black: '红',
    white: '绿',
    remove: '蓝',
    hint: '白',
  };
  ```
- [ ] **Step 2: Write the unit test `__tests__/ledColors.test.ts`** (vitest skeleton):
  ```ts
  import { describe, it, expect } from 'vitest';
  import { LED_HEX, LED_LABEL, type LedIntent } from '../constants/ledColors';

  const intents: LedIntent[] = ['black', 'white', 'remove', 'hint'];

  describe('ledColors', () => {
    it('maps every intent to a 6-digit hex', () => {
      intents.forEach((i) => expect(LED_HEX[i]).toMatch(/^#[0-9a-f]{6}$/));
    });

    it('pins the fixed LED colour semantics', () => {
      expect(LED_HEX.black).toBe('#ff3b30');
      expect(LED_HEX.white).toBe('#34c759');
      expect(LED_HEX.remove).toBe('#2f6fff');
      expect(LED_HEX.hint).toBe('#ffffff');
    });

    it('labels are the Chinese colour names', () => {
      expect(LED_LABEL).toEqual({ black: '红', white: '绿', remove: '蓝', hint: '白' });
    });
  });
  ```
- [ ] **Step 3: Run the verification gates — Gate K.** From `katrain/web/ui`: `npx vitest run src/kiosk/__tests__/ledColors.test.ts` (3 green), `npm run lint`, `npm run build:kiosk-2d`.
- [ ] **Step 4: Commit.** `git add src/kiosk/constants/ledColors.ts src/kiosk/__tests__/ledColors.test.ts && git commit` with message `feat(kiosk-ui): LED colour constants (LedIntent/LED_HEX/LED_LABEL) (A4)` and the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

---

### Task A5: Shared primitive — active-session store

**Files:**
- Create: `katrain/web/ui/src/kiosk/utils/activeSession.ts`
- Create: `katrain/web/ui/src/kiosk/__tests__/activeSession.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `type ActiveSessionKind='game'|'practice'`; `interface ActiveSession { kind; label; route; ts }`; `readActiveSession(kind): ActiveSession|null`; `writeActiveSession(s): void`; `clearActiveSession(kind): void`. localStorage keys `kiosk_active_game` / `kiosk_active_practice`. Consumed by 对弈「继续上一局」and 死活「继续练习」. New file → **Gate K**.

- [ ] **Step 1: Write `utils/activeSession.ts` per the contract** (best-effort try/catch mirroring `pages/tsumegoUnits.ts`; validates `kind` matches the slot so a corrupt/mismatched blob returns `null`):
  ```ts
  /** Persisted "continue where you left off" pointer for 对弈 / 死活 (contract §Active-session). */
  export type ActiveSessionKind = 'game' | 'practice';

  export interface ActiveSession {
    kind: ActiveSessionKind;
    label: string;
    route: string;
    ts: number;
  }

  const KEY: Record<ActiveSessionKind, string> = {
    game: 'kiosk_active_game',
    practice: 'kiosk_active_practice',
  };

  export function readActiveSession(kind: ActiveSessionKind): ActiveSession | null {
    try {
      const raw = localStorage.getItem(KEY[kind]);
      if (!raw) return null;
      const p = JSON.parse(raw) as Partial<ActiveSession>;
      if (
        p && p.kind === kind &&
        typeof p.label === 'string' &&
        typeof p.route === 'string' &&
        typeof p.ts === 'number'
      ) {
        return p as ActiveSession;
      }
      return null;
    } catch {
      return null;
    }
  }

  export function writeActiveSession(s: ActiveSession): void {
    try {
      localStorage.setItem(KEY[s.kind], JSON.stringify(s));
    } catch {
      /* best-effort */
    }
  }

  export function clearActiveSession(kind: ActiveSessionKind): void {
    try {
      localStorage.removeItem(KEY[kind]);
    } catch {
      /* best-effort */
    }
  }
  ```
- [ ] **Step 2: Write `__tests__/activeSession.test.ts`** (localStorage mock in the established kiosk style; covers round-trip, slot independence, clear, corrupt JSON, kind-mismatch rejection):
  ```ts
  import { describe, it, expect, beforeEach } from 'vitest';
  import { readActiveSession, writeActiveSession, clearActiveSession, type ActiveSession } from '../utils/activeSession';

  const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => { store[k] = String(v); },
      removeItem: (k: string) => { delete store[k]; },
      clear: () => { store = {}; },
    };
  })();
  Object.defineProperty(window, 'localStorage', { value: localStorageMock });

  const sample: ActiveSession = {
    kind: 'game', label: '自由对弈 · 执黑', route: '/kiosk/play/ai/game/abc', ts: 1_720_000_000_000,
  };

  describe('activeSession', () => {
    beforeEach(() => localStorage.clear());

    it('returns null when nothing is stored', () => {
      expect(readActiveSession('game')).toBeNull();
      expect(readActiveSession('practice')).toBeNull();
    });

    it('round-trips a game session under kiosk_active_game', () => {
      writeActiveSession(sample);
      expect(localStorage.getItem('kiosk_active_game')).toContain('/kiosk/play/ai/game/abc');
      expect(readActiveSession('game')).toEqual(sample);
    });

    it('keeps game and practice slots independent', () => {
      writeActiveSession(sample);
      expect(readActiveSession('practice')).toBeNull();
    });

    it('clearActiveSession removes only its slot', () => {
      writeActiveSession(sample);
      writeActiveSession({ ...sample, kind: 'practice', route: '/kiosk/tsumego/problem/9' });
      clearActiveSession('game');
      expect(readActiveSession('game')).toBeNull();
      expect(readActiveSession('practice')).not.toBeNull();
    });

    it('returns null on corrupt JSON', () => {
      localStorage.setItem('kiosk_active_game', '{not json');
      expect(readActiveSession('game')).toBeNull();
    });

    it('rejects a blob whose kind mismatches the slot', () => {
      localStorage.setItem('kiosk_active_practice', JSON.stringify({ ...sample, kind: 'game' }));
      expect(readActiveSession('practice')).toBeNull();
    });
  });
  ```
- [ ] **Step 3: Run the verification gates — Gate K.** From `katrain/web/ui`: `npx vitest run src/kiosk/__tests__/activeSession.test.ts` (6 green), `npm run lint`, `npm run build:kiosk-2d`.
- [ ] **Step 4: Commit.** `git add src/kiosk/utils/activeSession.ts src/kiosk/__tests__/activeSession.test.ts && git commit` with message `feat(kiosk-ui): active-session store for 继续上一局 / 继续练习 (A5)` and the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

---

### Task A6: Shared primitive — ImmersiveContext

**Files:**
- Create: `katrain/web/ui/src/kiosk/context/ImmersiveContext.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/ImmersiveContext.test.tsx`

**Interfaces:**
- Consumes: nothing.
- Produces: `useImmersive(): { immersive: boolean; setImmersive(v: boolean): void }` + `<ImmersiveProvider>`. A page goes immersive via `useEffect(() => { setImmersive(true); return () => setImmersive(false); }, [])` (hides Dock + console). **Hand-off:** `KioskLayout` mounts `<ImmersiveProvider>` and reads `immersive` in the Phase B A-shell rebuild (not mounted here). New file → **Gate K**.

- [ ] **Step 1: Write `context/ImmersiveContext.tsx`** — mirror the lint-clean provider+hook pattern of `OrientationContext.tsx` (provider component + hook from one file passes the repo's react-refresh config); `setImmersive` from `useState` satisfies the `(v: boolean) => void` contract signature:
  ```tsx
  import { createContext, useContext, useState, type ReactNode } from 'react';

  interface ImmersiveContextValue {
    immersive: boolean;
    setImmersive: (v: boolean) => void;
  }

  const ImmersiveContext = createContext<ImmersiveContextValue | undefined>(undefined);

  export const ImmersiveProvider = ({ children }: { children: ReactNode }) => {
    const [immersive, setImmersive] = useState(false);
    return (
      <ImmersiveContext.Provider value={{ immersive, setImmersive }}>
        {children}
      </ImmersiveContext.Provider>
    );
  };

  export function useImmersive(): ImmersiveContextValue {
    const ctx = useContext(ImmersiveContext);
    if (!ctx) throw new Error('useImmersive must be used within an ImmersiveProvider');
    return ctx;
  }
  ```
- [ ] **Step 2: Write `__tests__/ImmersiveContext.test.tsx`** (vitest + testing-library; covers default false, toggle on/off, throw-outside-provider):
  ```tsx
  import { describe, it, expect, vi } from 'vitest';
  import { render, screen, act } from '@testing-library/react';
  import { ImmersiveProvider, useImmersive } from '../context/ImmersiveContext';

  const Probe = () => {
    const { immersive, setImmersive } = useImmersive();
    return (
      <div>
        <span data-testid="immersive">{String(immersive)}</span>
        <button onClick={() => setImmersive(true)}>on</button>
        <button onClick={() => setImmersive(false)}>off</button>
      </div>
    );
  };

  describe('ImmersiveContext', () => {
    it('defaults to non-immersive (false)', () => {
      render(<ImmersiveProvider><Probe /></ImmersiveProvider>);
      expect(screen.getByTestId('immersive').textContent).toBe('false');
    });

    it('setImmersive(true) then (false) flips and restores the flag', () => {
      render(<ImmersiveProvider><Probe /></ImmersiveProvider>);
      act(() => { screen.getByText('on').click(); });
      expect(screen.getByTestId('immersive').textContent).toBe('true');
      act(() => { screen.getByText('off').click(); });
      expect(screen.getByTestId('immersive').textContent).toBe('false');
    });

    it('throws when used outside an ImmersiveProvider', () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      expect(() => render(<Probe />)).toThrow(/ImmersiveProvider/);
      spy.mockRestore();
    });
  });
  ```
- [ ] **Step 3: Run the verification gates — Gate K.** From `katrain/web/ui`: `npx vitest run src/kiosk/__tests__/ImmersiveContext.test.tsx` (3 green), `npm run lint` (react-refresh clean — same shape as OrientationContext), `npm run build:kiosk-2d`.
- [ ] **Step 4: Commit.** `git add src/kiosk/context/ImmersiveContext.tsx src/kiosk/__tests__/ImmersiveContext.test.tsx && git commit` with message `feat(kiosk-ui): ImmersiveContext (useImmersive + ImmersiveProvider) (A6)` and the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

---

### Task A7: Header component (brand + clock + compact hardware cluster)

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/Header.tsx`
- Test (create): `katrain/web/ui/src/kiosk/__tests__/Header.test.tsx`

**Interfaces:**
- Consumes: `kioskTheme` tokens (A2) via MUI keys `background.default`, `primary.main`, `text.secondary`, `success.main`, `error.main`, `warning.main`; `useOptionalVision` from `../../context/VisionContext` → `visionStatus { enabled, cameraConnected, poseLocked, syncState }`; `useOptionalGeometry` from `../../context/GeometryContext` → `status.phase`; brand serif stack `"'Newsreader','Noto Serif SC',serif"`; logo asset served at runtime path `/assets/img/logo-white.png`.
- Produces: `export default Header`, props `interface HeaderProps { username?: string }`. **Preserves** `data-testid="clock"` and `data-testid="engine-status"` (lifted from StatusBar). Height = 50px.

- [ ] **Step 1: Scaffold `Header.tsx`.** Create the file with imports (`useState`, `useEffect` from react; `Box`, `Typography`, `IconButton`, `Tooltip` from `@mui/material`; `Videocam`, `GridOn` from `@mui/icons-material`; the two optional-context hooks) and the signature:
  ```tsx
  interface HeaderProps { username?: string }
  const Header = ({ username }: HeaderProps) => { /* ... */ };
  export default Header;
  ```
- [ ] **Step 2: Lift the live clock verbatim** from `StatusBar.tsx` lines 80–91 (the `useState(() => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))` + `useEffect` with `setInterval(..., 10_000)` + cleanup). Render it as `<Typography data-testid="clock" variant="caption" sx={{ color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>{time}</Typography>` (keep the exact `data-testid="clock"`).
- [ ] **Step 3: Brand block** — reskin to match artifact `.brand`/`.wname`/`.logo` (`d3-board-console.html` lines 25–28, markup line 99). Render `<img src="/assets/img/logo-white.png" alt="智星盒 StellaBox" style={{ width: 34, height: 34, objectFit: 'contain' }} />` (path reused from `StatusBar.tsx` line 108), then **two separate text nodes** so tests can query each: `<Typography sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 600, fontSize: 20 }}>智星盒</Typography>` and a sibling `<Typography component="span" sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontStyle: 'italic', fontSize: 12, color: 'text.secondary' }}>StellaBox</Typography>`. Do NOT keep the old `弈航` text.
- [ ] **Step 4: Compact global hardware cluster.** Migrate the two indicator components from `StatusBar.tsx` (`VisionIndicators` lines 27–63, `GeometryIndicator` lines 65–78) into this file as compact mini-indicators next to the brand: (a) the engine dot — **label/aria it "assumed-ready"** (there is no real engine-health wiring yet, so this dot is a static optimistic placeholder; give it `aria-label={t('engine assumed ready','引擎假定就绪')}` or a `title="assumed-ready"` so it is not read as live health): `<Box data-testid="engine-status" aria-label="engine assumed-ready" sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'success.main' }} />` (StatusBar line 113–115). NOTE: the camera (b) and calibration (c) indicators below stay **live** (real `useOptionalVision`/`useOptionalGeometry` state) — only the engine dot is assumed-ready; (b) camera `<Videocam sx={{ fontSize: 18, color: visionStatus.cameraConnected ? 'success.main' : 'error.main' }} />` guarded by `useOptionalVision()` + `visionStatus.enabled` (StatusBar lines 29–36, 41–51); (c) calibration `<GridOn sx={{ fontSize: 18, color }} />` guarded by `useOptionalGeometry()`, hidden when `status.phase === 'disabled'`, using the inline phase→color ternary from StatusBar line 70 (`ready`→`success.main`, `degraded`/`failed`→`error.main`, else `warning.main`). Keep the `component="a" href="/kiosk/vision/setup"` on the clickable icons (StatusBar lines 43, 73) so browse pages retain a tap target after StatusBar deletion.
- [ ] **Step 5: Assemble the 50px bar.** Left group = brand + hardware cluster; right group = `{username && <Typography variant="body2" sx={{ color: 'text.secondary' }}>{username}</Typography>}` + clock (StatusBar lines 119–132). Reskin container to match artifact `.hdr` (lines 23–32): `height: 50`, `flexShrink: 0`, `display: flex`, `alignItems: center`, `justifyContent: 'space-between'`, `px: 3`, `borderBottom: '1px solid'`, `borderColor: 'divider'`, `bgcolor: 'background.default'`.
- [ ] **Step 6: Write `Header.test.tsx`** (provider-less, mirroring `StatusBar.test.tsx` — no VisionProvider/GeometryProvider, so `useOptional*` return `undefined`/`null` and the camera/calibration icons stay hidden). Wrap in `<ThemeProvider theme={kioskTheme}>`. Assert: `getByText('智星盒')`, `getByText('StellaBox')`, `getByText('张三')` (pass `username="张三"`), `getByTestId('engine-status')`, `getByTestId('clock')`.
- [ ] **Step 7: Verification gates.** From `katrain/web/ui`: `npm run build:kiosk-2d` (chains `verify:kiosk-2d`) + `npm run lint` + `npx vitest run src/kiosk/__tests__/Header.test.tsx` — all green (Gate K; Header imports only kiosk contexts + MUI, no new shared source import).
- [ ] **Step 8: Commit.** `feat(kiosk-ui): A7 Header — brand + clock + compact hardware cluster`.

---

### Task A8: Dock component (8 equal-width nav targets, raised jade selected)

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/Dock.tsx`
- Test (create): `katrain/web/ui/src/kiosk/__tests__/Dock.test.tsx`

**Interfaces:**
- Consumes: `primaryTabs`, `settingsTab`, `type NavTab` from `./navTabs`; `useNavigate`, `useLocation`, `matchPath` from `react-router-dom`; theme tokens `primary.main`, `text.secondary`, `divider`.
- Produces: `export default Dock` (no props). Each item carries `data-active={active}` (for testability, reused from NavigationRail line 21). Height = 86px.

- [ ] **Step 1: Scaffold `Dock.tsx`.** Import `Box`, `ButtonBase`, `Typography` from `@mui/material` and the router hooks + navTabs. Reuse NavigationRail's active logic verbatim: `const isActive = (pattern: string) => !!matchPath(pattern, location.pathname);` (NavigationRail line 9) and `onClick={() => navigate(tab.path)}` (line 16).
- [ ] **Step 2: Render 8 equal-width targets.** Map `primaryTabs` (7) then append `settingsTab` (1) into `ButtonBase` items, each `sx={{ flex: 1, ... }}` (≈120×70 touch target per design.md §4.1 line 40), `data-active`, icon `<Box sx={{ display: 'flex', '& svg': { fontSize: 24 } }}>{tab.icon}</Box>`, and CJK label `<Typography sx={{ fontSize: 13, fontWeight: 600, letterSpacing: '.5px' }}>{tab.label}</Typography>`. Base this on `NavigationRail.renderItem` (lines 11–40) but drop the vertical-rail `data-section`/footer separator.
- [ ] **Step 3: Reskin to artifact `.dock`/`.dk`/`.dk.on`** (`d3-board-console.html` lines 83–91). Selected (`active`) = **raised jade solid**, NOT the old `rgba(92,181,122,0.08)` tint: `bgcolor: 'primary.main'`, dark ink foreground `color: '#0e1a13'`, `transform: 'translateY(-2px)'`, `boxShadow: '0 10px 24px -10px'` in jade; non-selected `color: 'text.secondary'` with a subtle hover (`bgcolor: 'rgba(255,255,255,0.03)'`). Container: `height: 86`, `flexShrink: 0`, `display: 'flex'`, `alignItems: 'stretch'`, `px: 1.75`, `py: 1`, `gap: 0.5`, `borderTop: '1px solid'`, `borderColor: 'divider'`.
- [ ] **Step 4: Write `Dock.test.tsx`** (mirror `NavigationRail.test.tsx` patterns lines 8–23: `vi.mock('react-router-dom', ...)` for `useNavigate`, wrap in `ThemeProvider` + `MemoryRouter`; **no OrientationContext mock needed** — Dock does not use it). Assert: all 8 labels `['对弈','死活','研究','棋谱','摆谱','直播','教程','设置']` present; at route `/kiosk/play`, `screen.getByText('对弈').closest('button')` has `data-active="true"` and `screen.getByText('死活').closest('button')` has `data-active="false"`; clicking `死活` calls `mockNavigate` with `/kiosk/tsumego`.
- [ ] **Step 5: Verification gates.** From `katrain/web/ui`: `npm run build:kiosk-2d` + `npm run lint` + `npx vitest run src/kiosk/__tests__/Dock.test.tsx` — all green (Gate K).
- [ ] **Step 6: Commit.** `feat(kiosk-ui): A8 Dock — 8 equal-width nav targets, raised jade selected`.

---

### Task A9: SmartBoardConsole (read-only live board + 3 status cells)

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/SmartBoardConsole.tsx`
- Test (create): `katrain/web/ui/src/kiosk/__tests__/SmartBoardConsole.test.tsx`

**Interfaces:**
- Consumes: **shared** `LiveBoard` from `../../../components/live/LiveBoard` (props `moves: string[]`, `currentMove: number`, `boardSize?: number`, `showCoordinates?: boolean`, optional `onIntersectionClick?` — see `LiveBoard.tsx` lines 25–47); `useOptionalVision`, `useOptionalGeometry`; `useNavigate`; theme tokens `background.paper` (raise), `divider`, `text.primary`, `text.secondary`, `primary.main` (jade), `warning.main` (amber), `error.main`.
- Produces: `export default SmartBoardConsole`, props `interface SmartBoardConsoleProps { moves?: string[]; currentMove?: number }`. Owns module-local `syncStateColor` + `geometryPhaseColor` helpers (migrated OUT of StatusBar).

> **Boundary note:** this component newly-imports the shared `components/live/LiveBoard` at the layout level. `LiveBoard` is **already** bundled into the kiosk build (imported today by `kiosk/pages/{BaipuSessionPage,LivePage,LiveMatchPage,ResearchPage,BaipuListPage,AiSetupPage,KifuPage}.tsx`), and this task does **not edit** it — so galaxy is unaffected and this remains **Gate K**. Called out per contract.

- [ ] **Step 1: Scaffold + migrate helpers.** Create `SmartBoardConsole.tsx`. Move `syncStateColor` verbatim from `StatusBar.tsx` lines 11–25 (returns `success.main` / `warning.main` / `error.main` / `grey.500`) and add `const geometryPhaseColor = (phase: string) => phase === 'ready' ? 'success.main' : phase === 'degraded' || phase === 'failed' ? 'error.main' : 'warning.main';` (from StatusBar line 70) as module-local functions in this file. Add the props interface + signature.
- [ ] **Step 2: Read-only board preview.** Render `<LiveBoard moves={moves ?? []} currentMove={currentMove ?? 0} boardSize={19} showCoordinates={false} />` — **omit `onIntersectionClick`** (read-only; per `LiveBoard.tsx` line 31 it is optional so board becomes non-interactive). Static/empty 19×19 for now; add `// TODO: feed recognized board state when available — no recognized-board feed exists yet`. **Render a visible "实时预览暂不可用 / no live feed" label over/under the static board** (e.g. an overlaid `<Typography variant="caption" sx={{ color:'text.disabled' }}>实时预览暂不可用 · no live feed</Typography>`) so the empty 19×19 is not mistaken for recognized-board data.
- [ ] **Step 3: Reskin container + title** to artifact `.console`/`.ch` (`d3-board-console.html` lines 37–42, markup 105–106): `bgcolor: 'background.paper'`, `border: '1px solid'`, `borderColor: 'divider'`, `borderRadius: '18px'`, `p: 1.875`, own outer spacing (`m: 2.5`) since KioskLayout's middle row is flush. Title row: `<Typography>智能棋盘</Typography>` (letter-spaced, `text.primary`) + `<Typography>Live board</Typography>` (serif italic, `text.secondary`) matching `.ch h3`/`.ch em`.
- [ ] **Step 4: Three status cells (摄像头 / 标定 / LED).** Reskin to artifact `.stat`/`.scell` (lines 43–48, markup 119–123): a flex row of three `Box` cells, each a coloured dot (`.k b`) + label + value, wrapped in a clickable target that calls `navigate('/kiosk/vision/setup')`. Colours: 摄像头 dot = `useOptionalVision()?.visionStatus.cameraConnected ? 'primary.main' : 'error.main'`; 标定 dot = `geometryPhaseColor(useOptionalGeometry()?.status.phase ?? 'required')`; LED dot = `useOptionalVision()?.visionStatus.ledConnected ? 'primary.main' : 'warning.main'` (VisionContext exposes `ledConnected`, `VisionContext.tsx` lines 10, 38). Guard all `useOptional*` for `undefined`/`null` so the component renders standalone without providers.
- [ ] **Step 5: Write `SmartBoardConsole.test.tsx`** (provider-less; `vi.mock('react-router-dom', ...)` for `useNavigate` mirroring NavigationRail.test lines 8–12; wrap in `ThemeProvider` + `MemoryRouter`). Assert: labels `摄像头`, `标定`, `LED` and the `智能棋盘` title render; clicking the `摄像头` cell calls `mockNavigate` with `/kiosk/vision/setup`. (LiveBoard is jsdom-safe — already rendered by the existing `LivePage.test.tsx`/`ResearchPage.test.tsx`; assert on cell text, not canvas.)
- [ ] **Step 6: Verification gates.** From `katrain/web/ui`: `npm run build:kiosk-2d` + `npm run lint` + `npx vitest run src/kiosk/__tests__/SmartBoardConsole.test.tsx` — all green (Gate K per boundary note above).
- [ ] **Step 7: Commit.** `feat(kiosk-ui): A9 SmartBoardConsole — read-only live board + status cells`.

---

### Task A10: KioskLayout rewrite + navTabs icon fix + delete legacy shell + test cleanup

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx` (full rewrite; current lines 1–52)
- Modify: `katrain/web/ui/src/kiosk/components/layout/navTabs.tsx` (imports lines 2–11; usages line 24 `棋谱`, line 27 `教程`) — this task is the **single owner** of navTabs edits
- Delete: `katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx`
- Delete: `katrain/web/ui/src/kiosk/components/layout/NavigationRail.tsx`
- Delete: `katrain/web/ui/src/kiosk/components/layout/TopTabBar.tsx`
- Modify (Test): `katrain/web/ui/src/kiosk/__tests__/KioskLayout.test.tsx` (rewrite)
- Delete (Test): `katrain/web/ui/src/kiosk/__tests__/StatusBar.test.tsx`, `NavigationRail.test.tsx`, `TopTabBar.test.tsx`
- Modify (Test): `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx` (line 64)

**Interfaces:**
- Consumes: `Header` (A7), `Dock` (A8), `SmartBoardConsole` (A9); `ImmersiveProvider`, `useImmersive` from `../../context/ImmersiveContext` (A6); `useLocation`, `Outlet` from `react-router-dom`.
- Produces: `export default KioskLayout`, props `interface KioskLayoutProps { username?: string }`. Module const `CONSOLE_ROUTES = ['/kiosk/play']`.

- [ ] **Step 1: Fix `navTabs.tsx` icons** (design.md §4.4 line 94). Rewrite the import block (lines 2–11) to swap `MenuBook as KifuIcon` → `LibraryBooks as KifuIcon`, and `School as SchoolIcon` → `MenuBook as TutorialIcon`, keeping the rest:
  ```tsx
  import {
    SportsEsports as PlayIcon,
    Extension as TsumegoIcon,
    Science as ResearchIcon,
    LibraryBooks as KifuIcon,   // 棋谱: was MenuBook → LibraryBooks (galaxy 同款)
    LiveTv as LiveIcon,
    GridOn as BaipuIcon,
    MenuBook as TutorialIcon,   // 教程: was School → MenuBook (galaxy 同款)
    Settings as SettingsIcon,
  } from '@mui/icons-material';
  ```
  Line 24 (`棋谱`) keeps `icon: <KifuIcon />` (now LibraryBooks); line 27 (`教程`) change `icon: <SchoolIcon />` → `icon: <TutorialIcon />`. Leave `path`/`pattern` untouched.
- [ ] **Step 2: Rewrite `KioskLayout.tsx`** to a single landscape shell — remove all `StatusBar`/`NavigationRail`/`TopTabBar`/`useOrientation` imports (the old `isPortrait` branch is gone; A3 removed `isPortrait`). Mount `ImmersiveProvider` here (per shared contract) wrapping an inner shell that consumes `useImmersive()` + `useLocation()`:
  ```tsx
  import { Box } from '@mui/material';
  import { Outlet, useLocation } from 'react-router-dom';
  import { ImmersiveProvider, useImmersive } from '../../context/ImmersiveContext';
  import Header from './Header';
  import Dock from './Dock';
  import SmartBoardConsole from './SmartBoardConsole';

  const CONSOLE_ROUTES = ['/kiosk/play'];
  interface KioskLayoutProps { username?: string }

  const KioskShell = ({ username }: KioskLayoutProps) => {
    const { immersive } = useImmersive();
    const location = useLocation();
    const showConsole = !immersive && CONSOLE_ROUTES.includes(location.pathname);
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden', bgcolor: 'background.default' }}>
        {!immersive && <Header username={username} />}
        <Box sx={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
          {showConsole && <SmartBoardConsole />}
          <Box component="main" sx={{ flex: 1, minWidth: 0, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
            <Outlet />
          </Box>
        </Box>
        {!immersive && <Dock />}
      </Box>
    );
  };

  const KioskLayout = ({ username }: KioskLayoutProps) => (
    <ImmersiveProvider>
      <KioskShell username={username} />
    </ImmersiveProvider>
  );
  export default KioskLayout;
  ```
  (`SmartBoardConsole` owns its own outer spacing per A9 Step 3, so `main` stays flush — pages keep managing their own padding exactly as they did under `NavigationRail`.)
- [ ] **Step 3: Delete the three legacy shell files** `StatusBar.tsx`, `NavigationRail.tsx`, `TopTabBar.tsx`. (Verified: the only non-test importer was `KioskLayout.tsx`; `GamePage.tsx` line 161 only mentions `StatusBar` in a comment. No source import remains.)
- [ ] **Step 4: Delete the three obsolete test files** `StatusBar.test.tsx`, `NavigationRail.test.tsx`, `TopTabBar.test.tsx` (their subjects no longer exist).
- [ ] **Step 5: Rewrite `KioskLayout.test.tsx`.** Remove the `vi.mock('../context/OrientationContext', ...)` (lines 8–11) — KioskLayout no longer uses orientation. Render `<KioskLayout username="张三" />` inside `ThemeProvider` + `MemoryRouter` + `Routes` with a layout route exposing two children:
  ```tsx
  <Route element={<KioskLayout username="张三" />}>
    <Route path="/kiosk/play" element={<div>PLAY_CONTENT</div>} />
    <Route path="/kiosk/settings" element={<div>SETTINGS_CONTENT</div>} />
  </Route>
  ```
  Assert (no Vision/Geometry providers → optional hardware icons stay hidden, fine): at `/kiosk/play` → `getByText('智星盒')`, Dock labels `对弈` + `设置`, `PLAY_CONTENT`, and SmartBoardConsole present via `getByText('智能棋盘')`; at `/kiosk/settings` → `SETTINGS_CONTENT` present and `queryByText('智能棋盘')` is `null` (console gated to `CONSOLE_ROUTES`). Drop the old `弈航`/`isPortrait` assertions.
- [ ] **Step 5b: Add the immersive-collapse integration test.** In `KioskLayout.test.tsx` add a case that renders `<KioskLayout />` with a child route whose element is a small `<Outlet/>` child component that calls `setImmersive(true)` on mount (via `useImmersive()` — the real `ImmersiveProvider` is mounted by `KioskLayout`, so no mock). Assert that after render the Header brand (`queryByText('智星盒')`) **and** a Dock label (`queryByText('对弈')`) are both `null` — proving the child's `setImmersive(true)` collapses Header + Dock. This is the end-to-end proof of the A6→A10 immersive mechanism.
- [ ] **Step 6: Update `KioskApp.test.tsx`.** Change line 64 `expect(screen.getByText('弈航')).toBeInTheDocument();` → `expect(screen.getByText('智星盒')).toBeInTheDocument();` (the `对弈` Dock assertion on line 63 stays). No other kiosk tests assert `弈航` except the deleted StatusBar test — verified by grep: `KioskAuth.test.tsx` tests only `LoginPage` (which still renders `弈航` and is unchanged) so it needs **no** edit; `navigation.integration.test.tsx` asserts the `对弈` Dock label + page content (`人机对弈`), both preserved.
- [ ] **Step 7: Verification gates.** From `katrain/web/ui`: `npm run build:kiosk-2d` (chains `verify:kiosk-2d`) + `npm run lint` + `npx vitest run src/kiosk/__tests__/KioskLayout.test.tsx src/kiosk/__tests__/KioskApp.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx` — all green (Gate K; navTabs/KioskLayout are kiosk-only, no shared-file edit).
- [ ] **Step 8: Commit.** `refactor(kiosk-ui): A10 KioskLayout Board-Console shell + navTabs icon fix; drop StatusBar/NavigationRail/TopTabBar`.

---

### Task A11: Immersive wiring for `TsumegoProblemPage`

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx` (384 lines): imports L1–26; context-hook block L41–43 + L69–72; effects begin L91.
- Modify `katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx` (369 lines): mock block L19–99; `renderPage` L106–115.

**Interfaces:**
- **Consumes:** `useImmersive(): {immersive: boolean; setImmersive(v: boolean): void}` from `src/kiosk/context/ImmersiveContext.tsx` (created in **A6**); `ImmersiveProvider` is mounted inside `KioskLayout` by **A10**, and A10's Dock/console read `immersive` to hide themselves. `TsumegoProblemPage` renders under `KioskLayout` (KioskApp L58/L69), so the provider is in scope at runtime.
- **Produces:** on-mount `setImmersive(true)` / on-unmount `setImmersive(false)` — the single flag A10's shell reads to collapse the Dock + left board console for the solve screen. (Research L2 report wiring is **Phase C** — do NOT touch it here.)

- [ ] **Step 1: Import the hook.** In the `../context/*` import cluster (alongside `useVision` L23 / `useOrientation` L25), add:
  ```ts
  import { useImmersive } from '../context/ImmersiveContext';
  ```
- [ ] **Step 2: Call the hook.** After `const { progress } = useTsumegoProgress();` (L43), add:
  ```ts
  const { setImmersive } = useImmersive();
  ```
- [ ] **Step 3: Add the immersive effect** near the other effects, immediately before the sequence-loading effect at L91:
  ```ts
  // Immersive solve screen — hide the Dock + left board console while a problem is open.
  useEffect(() => {
    setImmersive(true);
    return () => setImmersive(false);
  }, [setImmersive]);
  ```
  `useEffect` is already imported (L1); no board/JSX changes — this task is pure wiring, not the §5.2 tsumego reskin.
- [ ] **Step 4: Keep the test green (required — not a Dock assertion, but a provider dependency).** The suite renders `TsumegoProblemPage` standalone (no `KioskLayout` ⇒ no `ImmersiveProvider`), so `useImmersive()` would throw. Add a mock alongside the existing context mocks (after the `VisionContext` mock at L24–30):
  ```ts
  vi.mock('../context/ImmersiveContext', () => ({
    useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }),
  }));
  ```
  No existing test asserts Dock presence, so no assertion edits are needed.
- [ ] **Step 5: Verification gates (Gate K — kiosk-only files).**
  ```bash
  cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/TsumegoProblemPage.test.tsx
  ```
  All 3 must pass; confirm the 5 auto-advance / prev-next tests still pass (effect adds no timers).
- [ ] **Step 6: Commit.** `feat(kiosk-ui): A11 — immersive flag hides Dock/console on TsumegoProblemPage`.

---

### Task A12: `LoginPage` reskin + logout→login redirect contract

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/LoginPage.tsx` (62 lines): wordmark block L31–33; error Alert L34; TextFields L35–47; submit Button L48–55. `handleLogin` logic L16–27 stays byte-for-byte.
- Modify `katrain/web/ui/src/kiosk/components/guards/KioskAuthGuard.tsx` (9 lines): add the contract comment above L4.
- (Verify-only, no edit) `katrain/web/ui/src/kiosk/__tests__/KioskAuth.test.tsx` (88 lines).

**Interfaces:**
- **Consumes:** `useAuth().login` from shared `context/AuthContext.tsx` (consume-only, unchanged); slate/serif tokens from **A2** (`kiosk/theme.ts`), which maps heading variants to the Newsreader serif stack (`'Newsreader','Noto Serif SC',serif`).
- **Produces — `LOGOUT_REDIRECT` contract** (consumed by the Phase B Settings 退出登录 task): `AuthContext.logout()` only clears state (AuthContext L87–99: `API.logout` best-effort, then `removeItem('token')` + `setToken(null)` + `setUser(null)`); it does **not** navigate. `KioskAuthGuard` (confirmed L5–6) redirects any `!isAuthenticated` view via `<Navigate to="/kiosk/login" replace />`. The Settings button must therefore call `await logout(); navigate('/kiosk/login', { replace: true });` — the explicit navigate avoids the one-render flash before the guard bounces. This contract is captured as a comment in `KioskAuthGuard.tsx` so Phase B has the canonical redirect path in-code.

- [ ] **Step 1: Document the redirect contract in the guard.** Above `const KioskAuthGuard` (L4) in `KioskAuthGuard.tsx`, add:
  ```tsx
  // LOGOUT_REDIRECT contract (consumed by Settings 退出登录, Phase B):
  //   AuthContext.logout() only clears state — it does NOT navigate.
  //   This guard bounces any unauthenticated view to /kiosk/login (Navigate below).
  //   Callers must run: await logout(); navigate('/kiosk/login', { replace: true }).
  ```
  Redirect path/behavior confirmed unchanged.
- [ ] **Step 2: Reskin the shell + wordmark.** Component: `LoginPage`. Header-less standalone (route `login` sits OUTSIDE `KioskLayout` — KioskApp L47), so it owns its own centered layout. Tokens/artifact: no dedicated login artifact exists — follow the §5.8 `settings-flow.html` card aesthetic + shared token table. Apply: outer `Box` `bgcolor: 'background.default'` (#0f1416); wrap the fields in a paper card (`bgcolor: 'background.paper'` #18211f, `border: '1px solid'` `borderColor: 'divider'` #2b3a35, `borderRadius`, padding, `maxWidth: 360`). Render the wordmark (currently plain `Typography variant="h4"` 弈航, L32) as `variant="h3"` so it inherits A2's Newsreader serif; subtitle 棋道导航者 (L33) → `color: 'text.secondary'` (#93a49d). Keep the `<img src="/assets/img/logo.png" alt="弈航">` (L31) as-is — the 弈航→StellaBox wordmark-image swap belongs to the brand-rename track.
- [ ] **Step 3: Reskin the controls.** TextFields (L35–47) keep labels `用户名`/`密码` and type; sit on the paper card. Submit Button (L48–55): `variant="contained"` `color="primary"` (jade #58b57a), retain `disabled={loading || !username}` and label `登录`/`登录中...`. Error Alert (L34): `severity="error"` (error.main #e2685c). No fake CSS — token props only.
- [ ] **Step 4: Preserve test contract.** Do not alter `handleLogin` (L16–27) or any accessible name: `getByLabelText(/用户名/i)`, `getByLabelText(/密码/i)`, `getByRole('button', { name: /登录/i })`, disabled-when-empty, navigate to `/kiosk/play`, and error text `登录失败` must all still resolve. This is kiosk-only (`kiosk/pages/` + `kiosk/components/guards/`; the AuthContext import is consume-only, no shared file edited) ⇒ **Gate K**.
- [ ] **Step 5: Verification gates (Gate K).**
  ```bash
  cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/KioskAuth.test.tsx
  ```
  All 5 `KioskAuth` tests must pass unmodified.
- [ ] **Step 6: Commit.** `feat(kiosk-ui): A12 — LoginPage slate/serif reskin + logout→login contract`.

---

### Task A13: `GeometryCalibrationWorkspace` + `VisionSetupPage` reskin (early — shared vision guard)

**Files:**
- Modify `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx` (306 lines): header/phase titles L163–192; degraded Alert L194–196; diagnostic card L197–223 (hardcoded oranges at L206–207 `rgba(255,149,0,…)` + L210 `#ff9f0a`); advisory Alerts L224–232; dual video panels L234–251; active progress L253–261; metrics line L263–267; button row L269–300 (labels via `buttonLabel` L155–159 + reuse button L285).
- Modify `katrain/web/ui/src/kiosk/pages/VisionSetupPage.tsx` (20 lines): back button L11; container L9.
- Modify `katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx` (151 lines): add one assertion for the new advisory.

**Interfaces:**
- **Consumes:** slate tokens + `warning.main` amber (#e0a24a) + `success`/`error` tokens from **A2** (`kiosk/theme.ts`); `useGeometry()` from `kiosk/context/GeometryContext.tsx` (unchanged); MUI `alpha` for token-derived tints.
- **Produces:** reskinned settings/guard vision surface (inherited by 死活-solve / 摆谱 guards via `PhysicalBoardGuard` and 对弈 state-B); a standing amber advisory with `data-testid="geometry-led-advisory"`.

- [ ] **Step 1: Add the §5.8 amber advisory (new copy).** Component: `GeometryCalibrationWorkspace`. Insert a standing, non-active advisory line directly under the header `Box` (after L192, before the degraded Alert L194) — visible whenever `!active`. Real code:
  ```tsx
  {!active && (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }} data-testid="geometry-led-advisory">
      <WarningAmberOutlined sx={{ fontSize: 18, color: 'warning.main' }} />
      <Typography variant="body2" sx={{ color: 'warning.main' }}>
        先清空棋盘 · 手动触发 · 不会自动点亮 LED
      </Typography>
    </Box>
  )}
  ```
  Add `WarningAmberOutlined` to the `@mui/icons-material` import (L3) — MUI SVG, **no emoji**. This copy states the `[[feedback_no_auto_led_geometry]]` rule; the rule is **already structurally honored** (manual `trigger` at L119, `confirmingManual` empty-board gate L128–134/L227–229) — do **not** rework the algorithm. **OUT OF SCOPE (future track):** the `[[project_geometry_recalib_arch]]` no-LED-outer-frame-PRIMARY rework — leave the LED-anchor flow as-is; add only the advisory copy.

  > **Scope note (Gemini-B6, modified):** A13 only **reskins the EXISTING** calibration phase-title + diagnostic/failure surfaces that `GeometryCalibrationWorkspace` already renders (retheme to tokens, preserve testids). The genuinely-**new** multi-step progress states (清空 / 暗参考 / 角点 / 校验 / 建基线) are `design.md §5.8 待补` = a future build, **out of scope here** — do not scaffold them.
- [ ] **Step 2: Reskin the diagnostic card to tokens.** In the `diagnostic` card (L197–223), replace the hardcoded Apple-orange with amber tokens: L206 `bgcolor: 'rgba(255, 149, 0, 0.10)'` → `bgcolor: (t) => alpha(t.palette.warning.main, 0.1)`; L207 `border: '1px solid rgba(255, 149, 0, 0.45)'` → `border: (t) => \`1px solid ${alpha(t.palette.warning.main, 0.45)}\``; L210 `ErrorOutline sx={{ color: '#ff9f0a' }}` → `color: 'warning.main'`. Import `alpha` from `@mui/material` (extend L2 import). Keep `data-testid="geometry-diagnostic-card"`, the `CheckCircle`/`success.main` line (L214–216), and `text.disabled` detail line (L218–220) as token refs. Preserve all `buildDiagnostic` copy (L32–67).
- [ ] **Step 3: Reskin remaining chrome to tokens (no label changes).** Header titles L165–186 → keep text, ensure `Typography` inherits A2 serif for the `variant="h5"` title + `text.secondary` for the body. Status chips L189–190 keep `color={... ? 'success' : 'error'}` and labels `摄像头已连接/未连接`, `LED 已连接/未连接`. Standing Alerts L224–232 (`warning`/`error`/`info`) → token severities (they already resolve to A2 palette; no hardcoded colors to change). Metrics line L263–267 keeps `success.main`. Button row L269–300: preserve exact labels — `取消标定`, `网格无误，使用上次标定`, and `buttonLabel` values (`重新标定` / `已清空，重新标定` / `已清空，开始自动标定`); `variant="contained"` primary CTA is jade via A2. Video panels L234–251 unchanged (stream URLs/overlays are load-bearing).
- [ ] **Step 4: Reskin `VisionSetupPage`.** Component: `VisionSetupPage` (20 lines). Container `Box` L9 → `bgcolor: 'background.default'`. Back button L11 keeps text `返回` + `ArrowBack`; style `variant="text"` `color="inherit"`, `text.secondary` resting color. Workspace mount L13–14 unchanged. Tokens per settings-flow.html.
- [ ] **Step 5: Add the advisory test + keep existing green.** In `GeometryCalibrationWorkspace.test.tsx`, add to the first `it` (the `required`/empty-board case, ~L41–52):
  ```ts
  expect(screen.getByTestId('geometry-led-advisory')).toHaveTextContent('不会自动点亮 LED');
  ```
  Verify no other assertion regressed — all button-name lookups (`已清空，开始自动标定`, `取消标定`, `已清空，重新标定`, `网格无误，使用上次标定`, `重新标定`), the `geometry-diagnostic-card` testid + `无法定位 Q4 的定位灯`, metrics `13/13` / `RMS 1.385 px`, and `摄像头未连接` still resolve (reskin changed only colors/tokens, not text). Both files are kiosk-only ⇒ **Gate K**.
- [ ] **Step 6: Verification gates (Gate K).**
  ```bash
  cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx
  ```
  All 8 (7 existing + 1 new) tests must pass.
- [ ] **Step 7: Commit.** `feat(kiosk-ui): A13 — geometry/vision slate reskin + §5.8 amber no-auto-LED advisory`.

---

## Phase B — Module Reskins

> Mutually independent after Phase A — any order. Each module visually matches its `artifacts/*.html` mock at 1024×600. All shared boards/hooks are **consume-only** (Gate K unless a shared file is newly consumed). Design specs: `design.md §5`.

---

**B1 · 对弈 (Play)** — artifacts: `play-hub-states.html`, `play-flow-setup-game.html`, `game-states.html` · spec `design.md §4.5 / §5.1`

---

### Task B1.1: PlayPage hub reskin — six-equal grid, jade-fill primary, 继续上一局 bar

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/PlayPage.tsx` (rewrite the body, current lines 1–55)
- Modify `katrain/web/ui/src/kiosk/components/common/ModeCard.tsx` (current lines 1–47)
- Create `katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx`

**Interfaces:**
- Consumes (from Phase A): `readActiveSession` from `../utils/activeSession` (`ActiveSession|null`); slate tokens on `theme.*` from `kiosk/theme.ts`.
- Consumes: `ModeCard` props extended below; `useTranslation` from `../../hooks/useTranslation`.
- Produces: `ModeCard` prop `variant?: 'default' | 'primary'` (replaces `compact`) consumed only by kiosk pages.

- [ ] **Step 1: ModeCard — swap `compact` for a `variant` prop + focus ring.** In `ModeCard.tsx` change the interface (lines 4–10) to:
```ts
interface ModeCardProps {
  title: string; subtitle: string; icon: React.ReactNode; to: string;
  variant?: 'default' | 'primary';
}
```
Delete every `compact ?` ternary (lines 23,25,30,38,39). Set fixed `minHeight: 132`, `gap: 1.25`, `p: 2`, icon `fontSize: 40`, title `variant="h6"`. This drops the size-emphasis path per design.md §4.4 ("六按钮等大").
- [ ] **Step 2: ModeCard — jade-fill primary variant.** When `variant==='primary'`: `bgcolor: 'primary.dark'` (`#26463a`), `borderColor: 'primary.main'`, icon+title `color: 'primary.main'` remains, subtitle `color: 'text.primary'`. When default: `bgcolor: 'background.paper'`, `borderColor: 'divider'`. No arrow, no scale-up — only the jade fill distinguishes primary (design.md §4.4/§4.5).
- [ ] **Step 3: ModeCard — five interaction states + reduced-motion.** Add to `sx`: `'&:hover': { borderColor: 'primary.main' }`, keep `'&:active': { transform: 'scale(0.96)' }`, add `'&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2 }`, and `'@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:active': { transform: 'none' } }`. States = default/hover/pressed/focus/disabled per `play-hub-states.html`.
- [ ] **Step 4: PlayPage — six-equal 3fr grid + galaxy PlayMenu icons.** Rewrite PlayPage layout: replace the two `display:flex` rows (lines 11,28) with two `display:'grid', gridTemplateColumns:'repeat(3, 3fr)', gap: 2` rows. Import icons `SmartToy, SportsEsports, Hub, Groups, Public` from `@mui/icons-material` (design.md §4.4 icon table). Cards: row1 人机 = 自由对弈 `SmartToy` `variant="primary"` `to="/kiosk/play/ai/setup/free"`; 升降级 `SportsEsports` `to="/kiosk/play/ai/setup/ranked"`; 跨平台 `Hub` `to="/kiosk/play/cross-platform"`. Row2 人人 = 本地对局 `Groups` `to="/kiosk/play/pvp/setup"`; 在线大厅 `Public` `to="/kiosk/play/pvp/lobby"`; 跨平台对弈 `Hub` `to="/kiosk/play/cross-platform"`. Keep all `t(...)` strings from current lines 13–48. Section labels 人机对弈 / 人人对弈 use `variant="h6"`, `color:'text.secondary'`.

  > **Disposition — `/kiosk/play/pvp/setup` (本地对局 card):** this route currently resolves to `PlaceholderPage` (`KioskApp:62`). **Decision: point it at the AiSetupPage setup skeleton** (design.md §5.1 "复用设置页骨架" — B1.2's canonical left-preview-console + right-form skeleton, PvP-flavored), NOT a placeholder. If that reuse is deferred, the fallback is to mark the 本地对局 hub card `敬请期待` (disabled, `text.disabled`) — but the **recommended and default choice is reuse the AiSetupPage skeleton**. State whichever is shipped explicitly in the PR.
- [ ] **Step 5: PlayPage — 继续上一局 bar consuming `readActiveSession('game')`.** At top of component:
```ts
const resume = readActiveSession('game');
```
Render, above the 人机对弈 label, only when `resume`:
```tsx
{resume && (
  <ButtonBase onClick={() => navigate(resume.route)} data-testid="resume-game-bar"
    sx={{ display:'flex', justifyContent:'space-between', alignItems:'center', gap:1.5,
          px:2, py:1.5, borderRadius:2, border:'1px solid', borderColor:'warning.main',
          bgcolor:'var(--raise2)', width:'100%' }}>
    <Typography sx={{ color:'text.primary' }}>{t('Resume last game', '继续上一局')} · {resume.label}</Typography>
    <PlayArrow sx={{ color:'warning.main' }} />
  </ButtonBase>
)}
```
Amber = the single `theme.warning.main` token (contract). When `resume===null` the bar is absent and the grid flows up (design.md §4.5 "无数据时整条隐藏、hub 上移"). Match `play-hub-states.html` "continue" state.
- [ ] **Step 6: Test.** Write `PlayPage.test.tsx` with vitest + `@testing-library/react`: (a) renders 6 ModeCards (`getAllByRole('button')` filtered) and exactly one has the primary jade fill (assert 自由对弈 card style via `data-testid` you add `mode-card-primary`); (b) mock `../utils/activeSession` `readActiveSession` → `null` asserts `queryByTestId('resume-game-bar')` is null; → an `ActiveSession` object asserts the bar renders and clicking calls navigate to `resume.route` (mock `useNavigate`). No emoji in assertions.
- [ ] **Step 7: Run the verification gates.** Gate K: `cd /Users/fan/Repositories/katrain-kiosk-ui-redesign/katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/pages/PlayPage.test.tsx`. Then Gate E emoji grep over `src/kiosk` returns nothing. Runtime: `python -m katrain --ui web --force-build`, drive `/kiosk/play` at 1024×600, compare to `play-hub-states.html` (default + continue states).
- [ ] **Step 8: Commit.** `feat(kiosk-play): PlayPage six-equal hub + jade-primary ModeCard + resume bar`.

---

### Task B1.2: AiSetupPage canonical setup reskin + PlatformEngineSetupPage token reconcile

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx` (restyle only; state/handlers current lines 12–67 unchanged, JSX 69–272)
- Modify `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx` (delete const `C` lines 12–16; de-emoji `avatarFor` lines 57–67; retheme)
- Create `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`

**Interfaces:**
- Consumes: `LiveBoard` (shared, already imported line 10 — consume-only); `OptionChips`, `API.createSession`/`API.gameSetup`, `internalToRank`/`sliderToInternal` (all unchanged); slate tokens from `kiosk/theme.ts`.
- Consumes (from Phase A / B1.1): `writeActiveSession` from `../utils/activeSession`.
- Produces: the canonical left-console+right-form skeleton that pvp/cross-platform setup pages restyle against (no flow change).

- [ ] **Step 1: AiSetupPage — left board-preview console frame.** Keep the `LiveBoard` block (lines 72–79) and its `aspectRatio:'1'` square. Wrap it in a console card: `bgcolor:'background.paper'`, `border:'1px solid'`, `borderColor:'divider'`, `borderRadius:3`, and add a small header row above the board `盘面预览` `variant="overline"` `color:'text.secondary'`. This is the reusable "棋盘台预览 console" of design.md §5.1① / `play-flow-setup-game.html` left screen. Do NOT touch `boardSize`/state.
- [ ] **Step 2: AiSetupPage — right form retheme to tokens.** Restyle the right column (lines 82–270): header title `variant="h5"` `color:'text.primary'`; back button keep. All `OptionChips`/`Slider`/`Switch` keep props; wrap each field group `label` in `color:'text.secondary'` (already). Section dividers use `borderColor:'divider'`. Keep every `t(...)` string and every control. This is a reskin step — match `play-flow-setup-game.html`; do not alter `handleStart` field payload (lines 48–60).
- [ ] **Step 3: AiSetupPage — jade CTA + writeActiveSession on create.** Restyle the Start button (lines 266–268) to the jade primary CTA: `variant="contained"` already maps to `primary.main`; add `bgcolor:'primary.main'`, `'&:hover':{bgcolor:'primary.dark'}`, keep `minHeight:56`. In `handleStart`, immediately before `navigate(...)` (line 61) insert the active-session write:
```ts
writeActiveSession({
  kind: 'game',
  label: isRanked ? t('Ranked Game', '升降级对弈') : t('Free Game', '自由对弈'),
  route: `/kiosk/play/ai/game/${session_id}`,
  ts: Date.now(),
});
```
so 继续上一局 (B1.1) has data. (GamePage clears on end — B1.3.)
- [ ] **Step 4: PlatformEngineSetupPage — replace const `C` with theme tokens.** Delete the `C` object (lines 12–16). Map every `C.*` usage to tokens: `C.panel`/`C.surface`→`background.paper`, `C.surface2`/`#161616`→`var(--raise2)`, `C.line`→`divider`, `C.txt`→`text.primary`, `C.txt2`→`text.secondary`, `C.txt3`→`text.disabled`, `C.jade`/`C.jadeLight`/`C.jadeBright`→`primary.dark`/`primary.main`/`primary.light`, `C.neu`→`warning.main` (the single amber), `C.wood` (board bg in `BoardPreview`) → keep a local literal since it is the goban wood, not a UI surface. Convert `sx` string interpolations like `` `1px solid ${C.line}` `` to `` `1px solid` `` + `borderColor:'divider'`. This is the "reconcile inline palette const C to theme tokens" of the brief.
- [ ] **Step 5: PlatformEngineSetupPage — de-emoji `avatarFor` (Gate E).** The current `avatarFor` (lines 57–67) returns 🐻/🤖 etc — these render as tofu on SBC and fail Gate E. Replace the whole function + its two call sites (line 355 avatar box, line 380 menu label) with a non-emoji bot avatar: render `<SmartToy fontSize="small" />` (import from `@mui/icons-material`) inside the 44×44 avatar box instead of `avatarFor(currentLevel?.name)`, and in the `MenuItem` label (line 380) drop the leading emoji so it reads `` `${l.name} · ${l.level_name} · elo ${l.elo_score}` ``. Delete `avatarFor` entirely.
- [ ] **Step 6: Note for reviewers (no code) — pvp/cross reuse.** Add a one-line code comment at the top of `AiSetupPage.tsx`: `// Canonical kiosk setup skeleton: left preview console + right token-themed form. pvp/cross-platform setup pages restyle against this — tokens only, no flow change.` PlatformConnectPage/PlatformLobbyPage/LobbyPage are not restyled in this task (separate; they already use tokens per earlier reads — no const-C debt).
- [ ] **Step 7: Test.** `AiSetupPage.test.tsx`: mock `../../api` `API.createSession`→`{session_id:'s1'}` and `API.gameSetup`→resolve; mock `../utils/activeSession`; render `/kiosk/play/ai/setup/free`, click Start, assert `writeActiveSession` called with `{kind:'game', route:'/kiosk/play/ai/game/s1', ...}` and `navigate` to that route. Assert the board-preview console header `盘面预览` renders.
- [ ] **Step 8: Run the verification gates.** Gate K on both files: `npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/pages/AiSetupPage.test.tsx`. Gate E: emoji grep over `src/kiosk` returns nothing (confirms `avatarFor` removal). LiveBoard is already-consumed shared (no new shared import) so Gate K suffices — but run `npm run build` too since PlatformEngineSetupPage is a widely-reached page. Runtime: drive `/kiosk/play/ai/setup/free` and `/kiosk/play/cross-platform/engine/golaxy`, compare to `play-flow-setup-game.html`.
- [ ] **Step 9: Commit.** `refactor(kiosk-play): AiSetup canonical setup skeleton + PlatformEngineSetup tokens/de-emoji`.

---

### Task B1.3: GamePage reskin skeleton — persistent amber banner, AI-turn arbitration, activeSession, remove debug img

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/GamePage.tsx` (current lines 1–319)
- Create `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`

**Interfaces:**
- Consumes: `Board`, `GameControlPanel`, `useGameSession` (returns `{gameState, onMove, onNavigate, handleAction, setSessionId, error, physicalReminder, ...}` per useGameSession.ts:169) — all consume-only via existing props; `PhysicalPlayStatusChip` (`latestEvent`, `currentNodeId`).
- Consumes (from Phase A/B1.1): `writeActiveSession`, `clearActiveSession` from `../utils/activeSession`.
- Produces: derived flags `aiThinking`, `aiLastMoveLabel` used by states in B1.4 wiring; single-owner AI-turn indicator.

- [ ] **Step 1: Remove the TEMP DEBUG vision-stream `<img>`.** Delete the whole debug block lines 212–225 (the `实时识别（调试）` caption + `<Box component="img" src="/api/v1/vision/stream" ...>`). The `GameControlPanel` (line 226) stays as the right-column content.
- [ ] **Step 2: AI-turn state derivation (single owner) — state A source.** Below `humanColor` (line 108), add the **per-color** derivation (accepts BOTH `player_type` literals) and arbitration with the 确认中 chip:
```ts
// Per-color AI detection — accept BOTH literals: 'player:ai' (kiosk HvAI, server.py:723/727)
// AND bare 'ai' (multiplayer session.py:80/82 + tests). Do NOT infer AI from "the non-human color".
const isAI = (c: 'B' | 'W') => {
  const pt = gameState.players_info[c].player_type;
  return pt === 'player:ai' || pt === 'ai';
};
const aiColor = isAI('B') ? 'B' : isAI('W') ? 'W' : null;
const aiThinking = !!aiColor && gameState.player_to_move === aiColor && !gameState.end_result;
// One owner for the AI-turn indicator: while the physical layer is confirming a
// move (chip shows 确认中), suppress the 思考中 banner so they never stack.
const physicalConfirming = visionSync.latestEvent?.type === 'move_pending';
const showThinking = aiThinking && !physicalConfirming;
```
`PhysicalPlayStatusChip` (lines 174–179) remains the owner of 确认中; the 思考中 surface (added in B1.4-A) is gated by `showThinking`. This resolves the "arbitrate with move_pending" requirement. **A both-human PVP game has `aiColor === null`**, so `aiThinking`/`showThinking` are always false and no "AI思考中" ever renders; the persistent AI-move banner (Step 3) and state A (B1.4 Step 1) are both gated on `aiColor !== null`.
- [ ] **Step 3: Persistent amber "AI 已落子" banner — replace the Snackbar.** Delete the `aiMoveToast` Snackbar (lines 276–280) and the `aiMoveToast` state (line 36). Keep the col/row compute effect (lines 64–76) but store into a persistent value that clears on human's own move. Replace the effect body's `setAiMoveToast(...)` with `setAiMoveBanner(\`${col}${row}\`)`, add state `const [aiMoveBanner, setAiMoveBanner] = useState<string | null>(null)`, and clear it inside `handleBoardMove` (after a successful `session.onMove`, line 121) via `setAiMoveBanner(null)`. Render a persistent bottom banner (not a Snackbar) just inside the root Box:
```tsx
{isVisionEnabled && aiColor !== null && aiMoveBanner && (
  <Box data-testid="ai-move-banner"
    sx={{ position:'absolute', bottom:0, left:0, right:0, zIndex:60,
          px:2, py:1.5, display:'flex', alignItems:'center', gap:1.5,
          bgcolor:'var(--raise2)', borderTop:'2px solid', borderColor:'warning.main' }}>
    <Lightbulb sx={{ color:'warning.main' }} />
    <Typography sx={{ color:'text.primary' }}>
      {t('AI played', 'AI 已落子')} <b>{aiMoveBanner}</b> · {t('place the white stone at the matching point on the board', '请在实体棋盘对应交叉点摆放白子')}
    </Typography>
  </Box>
)}
```
Amber = `theme.warning.main` (contract single token). Matches `game-states.html` physical-hint banner and design.md §5.1② ("底部 amber 提示条「AI 已落子 R16 …」").
- [ ] **Step 4: activeSession write-on-load + clear-on-end.** Add after the `setSessionId` effect (line 61):
```ts
useEffect(() => {
  const gs = session.gameState;
  if (!gs || !sessionId) return;
  if (gs.end_result) { clearActiveSession('game'); return; }
  writeActiveSession({
    kind: 'game',
    label: `${gs.players_info.B.name} vs ${gs.players_info.W.name}`,
    route: window.location.pathname,
    ts: Date.now(),
  });
}, [session.gameState?.current_node_id, session.gameState?.end_result, sessionId]);
```
This covers ai/pvp/cross entry routes uniformly and clears when the game ends (design.md §5.1: 继续上一局 clears on end).
- [ ] **Step 5: Header + board-panel retheme to tokens.** Retheme root Box (line 157) `bgcolor:'background.default'` (already), header (lines 186–199) title `color:'text.primary'`, Exit/Hint buttons `variant="outlined"` → `borderColor:'divider'`, `color:'text.secondary'`. Landscape-only: drop the `isPortrait` branch — the board+panel row (lines 201–210) is always `flexDirection:'row'`, board `height:'100%', aspectRatio:'1'`, panel `flex:1`. Remove `useOrientation`/`isPortrait` usage (lines 13,25,201,202). Match `d3-board-console.html` right console. Preserve every `data-testid`.
- [ ] **Step 6: Test — cover an AI game AND a both-human PVP game.** `GamePage.test.tsx`: (i) **AI game** — mock `useGameSession` with `players_info.W.player_type='player:ai'` (and a second case using bare `'ai'` to prove both literals work), human=B, `player_to_move='W'`, `end_result=null`; assert `aiColor==='W'`-driven `aiThinking` surface renders, and assert `showThinking` gating by also setting `visionSync.latestEvent.type='move_pending'` (mock `useVisionSync`) and asserting the 思考中 banner is absent while the 确认中 chip owner is untouched. (ii) **both-human PVP** — `players_info.B.player_type` and `.W.player_type` both `'human'` (bare) ⇒ assert `aiColor===null`: **no** 思考中 surface (`queryByTestId('ai-thinking')` null) and **no** `ai-move-banner` even when vision is enabled + a last move exists. Mock `../utils/activeSession`: on a `gameState` with `end_result='B+4.5'` assert `clearActiveSession('game')`; on live state assert `writeActiveSession` called with `kind:'game'`. Assert no `img[src="/api/v1/vision/stream"]` renders. Assert `data-testid="ai-move-banner"` shows only when vision enabled + `aiColor!==null` + last_move + AI just moved.
- [ ] **Step 7: Run the verification gates.** Gate K: `npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/pages/GamePage.test.tsx`. Gate E emoji grep over `src/kiosk` returns nothing. Runtime: drive `/kiosk/play/ai/game/<id>` at 1024×600, verify persistent amber banner + no debug img, compare to `game-states.html`.
- [ ] **Step 8: Commit.** `feat(kiosk-play): GamePage persistent AI-move banner + activeSession + AI-turn single owner`.

---

### Task B1.4: GamePage four states (A 思考中 · B 需校准挡屏 · C 终局数子 · D 认输) + consolidate board-loss surfaces

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/GamePage.tsx` (builds on B1.3)
- Modify `katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx` (promote to blocking modal; current lines 1–52)
- Create `katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx` (**NEW component — does not exist yet**)
- Modify `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx` (add a `suppressBoardLost?: boolean` prop — this file is **kiosk-owned**, so editing it is Gate K, not a shared-territory edit; current lines 36–42 props, 94–97 internal `board_lost` modal)
- Modify `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx` (extend from B1.3)

**Interfaces:**
- Consumes: `showThinking`, `aiThinking` (from B1.3); `GeometryAPI.calibrate('manual')` from `../../api/geometryApi` (sig `calibrate(trigger:'auto'|'manual')`, geometryApi.ts:85); `API.visionResetSync`; `Board` `analysisToggles.ownership` (existing prop, consume-only); `KioskResultBadge` (`result`, `rules`); `visionStatus.poseLocked` from `useVision`.
- Produces: `RecalibrationModal` (kiosk-only) with props `{ open: boolean; onClose(): void }`.

- [ ] **Step 1: State A — AI 思考中 surface.** Using `showThinking` (B1.3), render a jade spinner banner near the top of the board column (design.md §5.1 state A "AI 卡「思考中…」点动画，jade spinner 提示条"):
```tsx
{showThinking && (
  <Box data-testid="ai-thinking"
    sx={{ position:'absolute', top:44, left:'50%', transform:'translateX(-50%)', zIndex:55,
          display:'flex', alignItems:'center', gap:1, px:2, py:0.75, borderRadius:2,
          bgcolor:'var(--raise2)', border:'1px solid', borderColor:'primary.main' }}>
    <CircularProgress size={16} sx={{ color:'primary.main' }} />
    <Typography sx={{ color:'primary.main' }}>{t('AI is thinking…', 'AI 思考中…')}</Typography>
  </Box>
)}
```
Board interaction is already gated by `playerColor={humanColor}` (Board.tsx consume-only) so no extra disable needed. Reduced-motion: `CircularProgress` respects it; add `@media (prefers-reduced-motion: reduce){ }` no-op is unnecessary for MUI spinner.
- [ ] **Step 2: State B — promote PoseLostBanner logic into a blocking `RecalibrationModal`.** Create `RecalibrationModal.tsx` as an amber blocking `Dialog` (`open`, `onClose`), lifting the `recalibrate` logic verbatim from `PoseLostBanner.tsx` (lines 18–31: `GeometryAPI.calibrate('manual')` then `API.visionResetSync()`, busy/error state). Content per design.md §5.1 state B: title `t('Board may have moved', '棋盘可能被移动')`, body line `t('No LED needed — just align the outer frame', '无需 LED，对齐外框即可')` (aligns [[feedback_no_auto_led_geometry]]), two actions: `重新标定` (calls recalibrate) amber `warning.main`, `仍要继续` (calls `onClose`) `text.secondary`. Keep the exact `calibrate('manual')` call + comment about D2③. This is a modal (blocks), not the old top `Alert`.
- [ ] **Step 3: Rewire PoseLostBanner → RecalibrationModal in GamePage.** Replace the `<PoseLostBanner ... />` usage (GamePage lines 181–183) with `<RecalibrationModal open={visionEnabled && !visionStatus.poseLocked && !gameState.end_result} onClose={...} />`. Keep the `PoseLostBanner.tsx` file but have it re-export nothing new (or delete its import). Preserve the LedAPI/geometry fall-through advisories.
- [ ] **Step 4: Consolidate the three board-loss surfaces to one-visible-at-a-time (single-modal arbiter).** GamePage mounts three overlapping surfaces: `RecalibrationModal` (pose-lost, Step 2/3), `VisionSyncOverlay`'s internal `board_lost` modal (`VisionSyncOverlay.tsx:95,278–302`), and `PhysicalSyncEscalationDialog` (escalation, lines 300–305). Priority: **escalation > board-lost > recalibration**. Because `VisionSyncOverlay` is **kiosk-owned** (`src/kiosk/components/vision/`, not shared), **add a `suppressBoardLost?: boolean` prop to it** (default false) that short-circuits its internal `boardLostOpen` state (props are at `VisionSyncOverlay.tsx:36–42`, board-lost modal at `:95,278–302`), and from GamePage pass `suppressBoardLost={escalationOpen || recalOpen}` (where `recalOpen` is GamePage's local RecalibrationModal-open boolean from Step 3). Also gate `RecalibrationModal` `open` with `&& !escalationOpen` so escalation wins over recalibration. `PhysicalSyncEscalationDialog` is highest and needs no suppression prop. Document the precedence in a comment. Editing kiosk-owned `VisionSyncOverlay` is **Gate K** (not a shared edit).
- [ ] **Step 5: State C — 终局数子 territory coloring + result card + score breakdown.** When `isGameOver` (line 100): force `analysisToggles.ownership=true` for the Board (territory coloring via existing `analysisToggles.ownership` prop — consume-only), and render a result-card overlay (`KioskResultBadge` + a score-breakdown line) gated by a **local** `resultDismissed` flag. Add `const [resultDismissed, setResultDismissed] = useState(false)` and reset it when a new `sessionId`/game loads:
```tsx
{isGameOver && !resultDismissed && (
  <Box data-testid="endgame-card" sx={{ position:'absolute', top:12, left:'50%', transform:'translateX(-50%)', zIndex:70,
        display:'flex', flexDirection:'column', alignItems:'center', gap:1, px:3, py:2, borderRadius:3,
        bgcolor:'background.paper', border:'1px solid', borderColor:'divider' }}>
    <EmojiEvents sx={{ color:'primary.main' }} />
    <KioskResultBadge result={gameState.end_result!} rules={gameState.ruleset} />
    {/* score breakdown (目/子/贴目) read from gameState — display only */}
    <Box sx={{ display:'flex', gap:1.5 }}>
      <Button variant="outlined" onClick={() => setResultDismissed(true)}>{t('Resume game', '继续对弈')}</Button>
      <Button variant="contained" onClick={handleExit} sx={{ bgcolor:'primary.main' }}>{t('Confirm result', '确认终局')}</Button>
    </Box>
  </Box>
)}
```
**继续对弈** only dismisses the overlay via local `resultDismissed` state — the **game stays ended**; do NOT call `session.handleAction('resume')` (`useGameSession.ts:126–152` has no `resume` branch → unmatched action is a silent no-op). **确认终局** (`handleExit`) navigates out.
**DESCOPED — 死子淡化 + 红叉:** state C ships territory coloring + result card + score breakdown ONLY. Dead-stone dimming (opacity .4) + red-X is NOT rendered by shared `Board.tsx` today (`Board.tsx:187–200` draws ownership as translucent squares only; `api.ts:23` `analysis:any` exposes no `dead`/`dead_stones` field). It needs a **backend `dead_stones` field + a kiosk-only overlay (Gate S)** — **deferred, out of scope for this cut** (do not add props to shared `Board.tsx`). `EmojiEvents` = trophy SVG (NOT 🎉 — constraint #3). Match `game-states.html` state C.
- [ ] **Step 6: State D — 认输 error-red modal retheme.** The resign `Dialog` (lines 240–248) already exists; retheme its confirm `Button` to `color="error"` (`error.main` `#e2685c`) and title `color:'text.primary'`. Keep cancel/confirm handlers. This is state D of `game-states.html`.
- [ ] **Step 7: Test.** Extend `GamePage.test.tsx`: (A) with `showThinking` true assert `data-testid="ai-thinking"` present, and absent when `physicalConfirming`; (B) with `visionStatus.poseLocked=false` + live game assert `RecalibrationModal` open and clicking 重新标定 calls `GeometryAPI.calibrate` with `'manual'` (mock `../../api/geometryApi`); assert it is suppressed when `escalationOpen`; (B2) with a `board_lost` condition active AND `escalationOpen` true, assert the `VisionSyncOverlay` board-lost modal does **not** render (it receives `suppressBoardLost={true}`) while the escalation dialog does — proving board_lost + escalation can never both render; (C) with `end_result='B+4.5'` assert `data-testid="endgame-card"` + `result-badge` render and Board receives `analysisToggles.ownership===true`; (C2) clicking 继续对弈 hides `endgame-card` (local `resultDismissed`) and does **not** call `session.handleAction`; (D) resign confirm button has `color=error`.
- [ ] **Step 8: Run the verification gates.** Gate K: `npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/pages/GamePage.test.tsx`. Gate E emoji grep over `src/kiosk` returns nothing (confirms `EmojiEvents`, no 🎉). Runtime: drive `/kiosk/play/ai/game/<id>`, exercise all four states (force via mocked engine states), compare each to `game-states.html` A/B/C/D.
- [ ] **Step 9: Commit.** `feat(kiosk-play): GamePage 4 states + consolidated board-loss surfaces + RecalibrationModal`.

---

### Task B1.5: GameControlPanel / ItemToggle / KioskResultBadge reskin to slate tokens

**Files:**
- Modify `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx` (current lines 1–115)
- Modify `katrain/web/ui/src/kiosk/components/game/ItemToggle.tsx` (current lines 1–35)
- Modify `katrain/web/ui/src/kiosk/components/game/KioskResultBadge.tsx` (current lines 1–41)

**Interfaces:**
- Consumes: `ScoreGraph` (shared, `{gameState, onNavigate, showScore?, showWinrate?}` — ScoreGraph.tsx:6–10) — KEEP as the §5.1② win-rate graph, consume-only; `PlayerCard` (shared, consume-only). No prop/handler changes to any of the three components.
- Produces: retheme only.

- [ ] **Step 1: ItemToggle — retheme to tokens (keep props).** Replace the hardcoded `rgba(...)` in `ItemToggle.tsx` (lines 21–26): `borderColor` active → `activeColor` (`primary.main` / `error.main`) else `divider`; active `bgcolor` → `primary.dark` (jade) / a red-tint for destructive `'rgba(226,104,92,0.15)'` derived from `error.main`; inactive `color:'text.secondary'`; disabled `opacity:0.3` keep. Hover uses `borderColor: activeColor`. No prop changes (`ItemToggleProps` lines 3–10 unchanged).
- [ ] **Step 2: GameControlPanel — retheme surfaces, keep ScoreGraph.** In `GameControlPanel.tsx`: the game-info bar `bgcolor:'rgba(0,0,0,0.15)'` (line 52) → `var(--raise2)`; ScoreGraph wrapper `bgcolor:'rgba(0,0,0,0.1)'` (line 76) → `var(--raise2)`; keep `data-testid="score-graph"` and `data-testid="nav-controls"`. Keep `<ScoreGraph gameState=... onNavigate=... />` (line 77) exactly — it IS the §5.1② win-rate graph; do NOT switch to a live/TrendChart component (design.md §5.1② note "kiosk GameControlPanel 本就 import ScoreGraph"). Captions/dividers → `text.secondary` / `divider`.
- [ ] **Step 3: KioskResultBadge — retheme to tokens.** In `KioskResultBadge.tsx` (lines 19–33): keep the black/white split but source colors from tokens — black badge `bgcolor:'#0a0a0a'`, white badge `bgcolor:'var(--raise2)'`, `color:'text.primary'`, `borderColor:'divider'`. Keep `data-testid="result-badge"` and the mono `fontFamily`. No prop change (`result`, `rules`).
- [ ] **Step 4: Run the verification gates.** These are kiosk-only files consuming already-consumed shared `ScoreGraph`/`PlayerCard` (no NEW shared import) → Gate K: `npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk` (existing GameControlPanel/ItemToggle tests if any; else run the GamePage suite that mounts them). Gate E emoji grep over `src/kiosk` returns nothing. Runtime: drive a live game, toggle 领地/建议/图表, confirm ScoreGraph still renders and colors match `d3-board-console.html`.
- [ ] **Step 5: Commit.** `style(kiosk-play): retheme GameControlPanel/ItemToggle/KioskResultBadge to slate tokens`.

---

### Task B1.6: Reskin play sub-routes (Lobby / PlatformConnect / PlatformLobby / PlatformEngineSetup) to slate tokens

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/LobbyPage.tsx` (326 lines)
- Modify `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx` (300 lines)
- Modify `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx` (224 lines)
- Modify `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx` (415 lines — const-`C`/`avatarFor` de-emoji already done in **B1.2**; here only finish any residual slate-token reskin, do **not** re-do that work)

**Interfaces:**
- Consumes: `kioskTheme` slate tokens; `useTranslation`. All shared imports consume-only — **no props added**. Kiosk-only edits + emoji/hex gates → **Gate K + Gate E**.

- [ ] **Step 1: Confirm these are REAL user-visible routes, not placeholders.** `LobbyPage` (326), `PlatformConnectPage` (300), `PlatformLobbyPage` (224) are live pages **linked from `PlayPage`** (人人对弈「在线大厅」 + 跨平台 flows) — reskin them, do not stub. (Verified route coverage: only `/kiosk/play/pvp/setup` and `kifu/:kifuId` still resolve to `PlaceholderPage` — see the B1.1 disposition + the B3 note.)
- [ ] **Step 2: Reskin each page to slate tokens.** Sweep hardcoded warm/grey literals (`rgba(255,255,255,*)`, `#1a…`, jade `#5cb57a`, amber `#c49a3c`) → theme tokens (`background.paper` / `var(--raise2)` / `divider` / `primary.main` / `warning.main`) matching the play-flow artifacts. Preserve every `data-testid`, `t(...)` string, and navigation target.
- [ ] **Step 3: Verify no surviving warm hex + no emoji.** Per file: `grep -nE "#5cb57a|#c49a3c|#c45d3e|rgba\(255, ?255, ?255" <file>` returns nothing; the broadened Gate-E grep `grep -rP '[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]' src/kiosk` returns nothing.
- [ ] **Step 4: Run the verification gates (Gate K + E).** `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk` (preserve any existing tests for these pages green). Runtime: drive `/kiosk/play/pvp/lobby`, `/kiosk/play/cross-platform`, and the connect / engine-setup flows at 1024×600, compare to the play-flow artifacts.
- [ ] **Step 5: Commit.** `reskin(kiosk-play): B1.6 play sub-routes (Lobby/PlatformConnect/PlatformLobby/PlatformEngineSetup) → slate tokens`.

---

**B2 · 死活 (Tsumego)** — reskin + emoji-tofu fixes + default-OFF physical-toggle **seam only** (5-state panel is Phase D) · artifact `tsumego-flow.html` · spec `design.md §5.2`

---

### Task B2.1: §4.2 emoji-tofu fixes — SuccessOverlay 🎉 and CATEGORY_ICONS ⚔️✨🎯📋 → MUI SVG

**Files:**
- Modify `katrain/web/ui/src/kiosk/components/tsumego/SuccessOverlay.tsx` (lines 39, 117–131 — `CONFETTI_COLORS`, the `🎉` `<Typography>` block, message color `#e8e4dc`)
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoCategoriesPage.tsx` (lines 3 import, 19–23 `CATEGORY_ICONS`, 155–157 map body, 173–176 icon render)
- Test `katrain/web/ui/src/kiosk/__tests__/tsumego-components.test.tsx` (add EmojiEvents-present assertion), `katrain/web/ui/src/kiosk/__tests__/TsumegoCategoriesPage.test.tsx` (unchanged text asserts must still pass; add no-emoji assert)

**Interfaces:** Consumes: `@mui/icons-material` (`EmojiEvents`, `Extension`, `AutoAwesome`, `TrackChanges`, `Assignment`), theme tokens `primary.main`/`text.primary`. Produces: nothing new (bug fix only — this IS the named T9 "答对乱码" fix).

- [ ] **Step 1: SuccessOverlay — trophy replaces 🎉.** In `SuccessOverlay.tsx` add `import { EmojiEvents } from '@mui/icons-material';`. Replace the `<Typography variant="h2" sx={{ mb: 1 }}>🎉</Typography>` (lines 118–120) with:
```tsx
<EmojiEvents sx={{ fontSize: 72, color: 'primary.main', mb: 1, filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.5))' }} />
```
Change the message `<Typography>`'s `color: '#e8e4dc'` (line 124) to `color: 'text.primary'` (consumes §4.3 `#eef3f1`).
- [ ] **Step 2: Retheme confetti to the slate palette.** Replace `CONFETTI_COLORS` (line 39) with the §4.3 tokens: `const CONFETTI_COLORS = ['#58b57a', '#e0a24a', '#e2685c', '#7ec994', '#26463a'];` (jade / the single amber / error / jade-light / primary.dark — no new hard-coded non-token colors).
- [ ] **Step 3: CATEGORY_ICONS → component map.** In `TsumegoCategoriesPage.tsx` change the import (line 3) to `import { ArrowBack, GridView, Extension, AutoAwesome, TrackChanges, Assignment } from '@mui/icons-material';` plus `import type { SvgIconComponent } from '@mui/icons-material';`. Replace the `Record<string, string>` map (lines 19–23) with (§5.2: 死活⚔️→module icon `Extension`, 手筋✨→`AutoAwesome`, 官子🎯→`TrackChanges`):
```tsx
const CATEGORY_ICONS: Record<string, SvgIconComponent> = {
  'life-death': Extension,
  tesuji: AutoAwesome,
  endgame: TrackChanges,
};
```
- [ ] **Step 4: Render the SVG, drop the tofu `📋` default.** In the `categories.map` body (near line 156) add `const CatIcon = CATEGORY_ICONS[cat.category] ?? Assignment;`. Replace the `<Typography sx={{ fontSize: 28 }}>{CATEGORY_ICONS[cat.category] || '📋'}</Typography>` (lines 174–176) with `<CatIcon sx={{ fontSize: 28, color: 'primary.main' }} />`.
- [ ] **Step 5: Test — trophy + no-emoji.** In `tsumego-components.test.tsx` render `<SuccessOverlay show message="恭喜答对！" />` inside the kioskTheme provider and assert `container.querySelector('[data-testid="EmojiEventsIcon"]')` is present and `container.textContent` does not contain `'🎉'`. **`@mui/icons-material` (v7) auto-appends `Icon` to the rendered `data-testid`** — the queried testid is `EmojiEventsIcon`, NOT `EmojiEvents` (this **+`Icon`** rule applies to every MUI-icon `data-testid` assertion in this plan; e.g. `PanToolIcon`, `ExtensionIcon`). In `TsumegoCategoriesPage.test.tsx` confirm the existing `getByText('手筋')` / `getByText('全部题目')` still pass and add `expect(container.textContent).not.toMatch(/[⚔️✨🎯📋]/)`.
- [ ] **Run the verification gates:** Gate E — `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk/components/tsumego/SuccessOverlay.tsx katrain/web/ui/src/kiosk/pages/TsumegoCategoriesPage.tsx` returns nothing; then Gate K — `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/tsumego-components.test.tsx src/kiosk/__tests__/TsumegoCategoriesPage.test.tsx`.
- [ ] **Commit:** `fix(kiosk-tsumego): replace 🎉/⚔️✨🎯 emoji with MUI SVG (T9 答对乱码 tofu fix)`.

---

### Task B2.2: 死活 hub reskin — full-width, 继续练习 card, kyu/dan color, last-practiced highlight

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts` (append `isDanLevel`, `levelChinese`, `readLastLevel`/`writeLastLevel`)
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx` (lines 61–103 — header, add 继续练习 card, retheme level cards)
- Test `katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx` (existing asserts stay; add 继续练习 + kyu/dan cases)

**Interfaces:** Consumes: `readActiveSession` from `../utils/activeSession` (Phase A), theme tokens (`primary.main`, `primary.dark`, `text.primary`, `background.paper`, `--raise2`, `warning.main`). Produces: `isDanLevel(level: string): boolean`, `levelChinese(level: string): string`, `readLastLevel(): string | null`, `writeLastLevel(level: string): void` (all in `tsumegoUnits.ts`, consumed by B2.5 breadcrumb/session-write). Matches `tsumego-flow.html` ① (`.tl` / `.cont` 继续练习 / `.lvl` / `.lc.dan` / `.here`+`.tag` / `.ldots`).

- [ ] **Step 1: Add level helpers to tsumegoUnits.ts.** Append (data format is lowercase e.g. `'15k'`, `'3d'` per the levels API):
```ts
export function isDanLevel(level: string): boolean {
  return level.trim().toLowerCase().endsWith('d');
}
export function levelChinese(level: string): string {
  const n = level.replace(/[^0-9]/g, '');
  return isDanLevel(level) ? `${n} 段` : `${n} 级`;
}
```
- [ ] **Step 2: Add last-practiced-level persistence.** Append (single string, cheap — does NOT reintroduce the deliberately-omitted per-level completion stat, R2):
```ts
export const LAST_LEVEL_KEY = 'kiosk_tsumego_last_level';
export function readLastLevel(): string | null {
  try { return localStorage.getItem(LAST_LEVEL_KEY); } catch { return null; }
}
export function writeLastLevel(level: string): void {
  try { localStorage.setItem(LAST_LEVEL_KEY, level); } catch { /* best-effort */ }
}
```
- [ ] **Step 3: Reskin the hub header + confirm full-width.** In `TsumegoPage.tsx` keep the existing full-width `Box` (this browse page mounts no console, so it stays full-width under the Dock by default — no `useImmersive` needed). Retheme the header (lines 63–66): title `死活题` stays `variant="h5"`; append the artistic subtitle from `tsumego-flow` `.tl .sub` → `选择难度级别 · 练习死活以提高计算力`, color `text.secondary`.
- [ ] **Step 4: Add the 继续练习 card (consumes activeSession).** Add `import { readActiveSession } from '../utils/activeSession';` and `import { isDanLevel, readLastLevel } from './tsumegoUnits';`. Before the level `<Grid>` (after line 66), compute `const resume = readActiveSession('practice');` and render, only when `resume` is non-null, a jade-filled resume card matching `.cont` (line 125 of the artifact) — `bgcolor: 'primary.dark'`, a left jade accent bar (`.rl`), heading `继续练习`, body `{resume.label}`, an `ArrowForward` MUI icon (import from `@mui/icons-material`; NO emoji), `onClick={() => navigate(resume.route)}`, wrapped in `CardActionArea`.
- [ ] **Step 5: kyu=white / dan=jade level cards + 上次 highlight.** In the `levels.map` (lines 69–99) retheme each `Card`: `bgcolor` from `rgba(255,255,255,0.05)` → `'background.paper'` (hover `--raise2` via `bgcolor: 'var(--raise2)'`). Change the level `<Typography variant="h4">` color (line 83) from `'#5cb57a'` to `isDanLevel(level.level) ? 'primary.main' : 'text.primary'`. Compute `const lastLevel = readLastLevel();` once above the map; when `level.level === lastLevel` add a jade ring (`border: '2px solid', borderColor: 'primary.main'`) and a small `上次` tag chip (`bgcolor: 'primary.main'`, text `background.default`) matching `.here .tag`. Keep the total-count line and category breakdown as-is; do NOT add per-level ProgressDots (honors the source-comment R2 "no per-level stat" decision the design says to keep — the artifact's per-level `.ldots` are decorative; real ProgressDots stay in the drilldown pages B2.3).
- [ ] **Step 6: Tests.** In `TsumegoPage.test.tsx` keep the existing `15K`/`14K`/`1000 题` asserts. Add: (a) seed `localStorage.setItem('kiosk_active_practice', JSON.stringify({ kind:'practice', label:'3 段 · 死活题 · 第 12 题', route:'/kiosk/tsumego/problem/p12', ts: Date.now() }))` then assert `getByText('继续练习')` and `getByText('3 段 · 死活题 · 第 12 题')`; (b) seed `localStorage.setItem('kiosk_tsumego_last_level','15k')` and assert the `15K` card container carries the `上次` tag text.
- [ ] **Run the verification gates:** Gate K — `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx`.
- [ ] **Commit:** `feat(kiosk-tsumego): reskin 死活 hub — 继续练习 card + kyu/dan color + 上次 highlight`.

---

### Task B2.3: browse drilldown reskin — categories / units / unit-list / all → slate tokens

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoCategoriesPage.tsx` (card bg/borders lines 128–192)
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx` (lines 140–166 — card bg/border, complete-ring, count color)
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx` (lines 129–133 header chip)
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoLevelPage.tsx` (lines 98–103 `borderFor`, 120 card bg)
- Test `katrain/web/ui/src/kiosk/__tests__/{TsumegoUnitsPage,TsumegoUnitListPage,TsumegoLevelPage}.test.tsx` (existing behavior asserts must still pass)

**Interfaces:** Consumes: theme tokens (`primary.main`, `warning.main`, `background.paper`, `--raise2`, `divider`), existing shared `ProgressDots`/`ProblemCard`/`useTsumegoProgress` (consume-only). Produces: nothing. Match `tsumego-flow.html` browse-grid styling; these are the same layout, retheme only.

- [ ] **Step 1: Categories cards → tokens.** In `TsumegoCategoriesPage.tsx` retheme the "全部题目" shortcut card (lines 128–152): `bgcolor: 'primary.dark'` tint, `border: '2px solid', borderColor: 'primary.main'`, `GridView` icon color `'primary.main'`; and the per-category cards (lines 160–167): `bgcolor: 'background.paper'`, hover `bgcolor: 'var(--raise2)'`. Keep `ProgressDots` at line 188 unchanged (already correct green). Preserve every text label (`t()` calls).
- [ ] **Step 2: Units cards → tokens + jade complete-ring.** In `TsumegoUnitsPage.tsx` (lines 140–145) change `bgcolor: 'rgba(255,255,255,0.05)'` → `'background.paper'`; change the complete ring `'2px solid #5cb57a'` → ``border: `2px solid`, borderColor: isComplete ? 'primary.main' : 'transparent'``; change the count `<Typography>` color (line 163) `'#5cb57a'` → `'primary.main'`. Keep `ProgressDots`, `unitProgress`, and the `navigate` routes untouched.
- [ ] **Step 3: Unit-list header chip.** In `TsumegoUnitListPage.tsx` the completed `<Chip>` (lines 129–133) already uses MUI `color="success"` — leave semantics, only confirm it resolves to the slate success token (it does via theme). No hard-coded hex to change; verify `ProblemCard` grid spacing untouched (`ProblemCard` internal colors are B-out-of-scope shared component, consume-only).
- [ ] **Step 4: All-list border states → tokens.** In `TsumegoLevelPage.tsx` rewrite `borderFor` (lines 98–103) to token hexes matching §4.3: completed `'#58b57a'` (primary.main), attempted `'#e0a24a'` (the single amber `warning.main`), untouched `'#2b3a35'` (divider) — replacing `#5cb57a`/`#c49a3c`/`rgba(232,228,220,0.10)`. Change the card `bgcolor` (line 120) to `'background.paper'`, hover `'var(--raise2)'`.
- [ ] **Step 5: Preserve tests.** Run the three existing page test files unchanged; they assert navigation + counts + labels (not colors), so no test edits are expected. If any asserts a literal old hex, update that one assertion to the new token hex.
- [ ] **Run the verification gates:** Gate K — `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/TsumegoLevelPage.test.tsx src/kiosk/__tests__/TsumegoCategoriesPage.test.tsx`.
- [ ] **Commit:** `style(kiosk-tsumego): reskin browse drilldown (categories/units/list/all) to slate tokens`.

---

### Task B2.4: physical-mode persistence seam + PhysicalModeToggle (default-OFF, zero physical rendering)

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts` (append physical-mode key + read/write)
- Create `katrain/web/ui/src/kiosk/components/tsumego/PhysicalModeToggle.tsx`
- Test `katrain/web/ui/src/kiosk/__tests__/PhysicalModeToggle.test.tsx`

**Interfaces:** Consumes: `@mui/icons-material` `ViewInAr`, theme `warning.main`/`text.disabled`. Produces: `readPhysicalMode(): boolean` (default **FALSE**), `writePhysicalMode(v: boolean): void`, key `kiosk_tsumego_physical`; component `PhysicalModeToggle` with props `{ checked: boolean; onChange: (v: boolean) => void; capable: boolean }`. **Both are consumed by Phase D** (the 5-state `PhysicalStatePanel` + `usePhysicalTsumego.stub`). This task ships NO physical rendering — the toggle is the only physical-related surface, and Phase B never shows a state panel.

- [ ] **Step 1: Add physical-mode persistence to tsumegoUnits.ts.** Append (mirrors the existing `readAutoAdvance` pattern at lines 28–45 but defaults FALSE):
```ts
export const PHYSICAL_MODE_KEY = 'kiosk_tsumego_physical';
/** Read the "use physical board" preference. Defaults to FALSE (opt-in, T1). */
export function readPhysicalMode(): boolean {
  try { return localStorage.getItem(PHYSICAL_MODE_KEY) === 'true'; } catch { return false; }
}
export function writePhysicalMode(v: boolean): void {
  try { localStorage.setItem(PHYSICAL_MODE_KEY, v ? 'true' : 'false'); } catch { /* best-effort */ }
}
```
- [ ] **Step 2: Create PhysicalModeToggle.tsx.** Write the seam component (NO emoji, `使用物理棋盘` label, single amber `warning.main` token; `capable=false` disables + relabels):
```tsx
import { Box, FormControlLabel, Switch, Typography } from '@mui/material';
import { ViewInAr } from '@mui/icons-material';

interface PhysicalModeToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  capable: boolean;
}

const PhysicalModeToggle = ({ checked, onChange, capable }: PhysicalModeToggleProps) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, opacity: capable ? 1 : 0.6 }} data-testid="physical-mode-toggle">
    <ViewInAr sx={{ color: capable ? 'warning.main' : 'text.disabled' }} />
    <FormControlLabel
      sx={{ ml: 0 }}
      control={
        <Switch
          color="warning"
          checked={checked && capable}
          disabled={!capable}
          onChange={(e) => onChange(e.target.checked)}
          inputProps={{ 'aria-label': '使用物理棋盘' }}
        />
      }
      label={<Typography variant="body2">{capable ? '使用物理棋盘' : '未检测到实体棋盘'}</Typography>}
    />
  </Box>
);

export default PhysicalModeToggle;
```
- [ ] **Step 3: Tests.** In `PhysicalModeToggle.test.tsx`: (a) default `readPhysicalMode()` with empty localStorage returns `false`; `writePhysicalMode(true)` then `readPhysicalMode()` returns `true`; (b) render `capable={false}` → switch is disabled and label reads `未检测到实体棋盘`; (c) render `capable checked={false}`, `fireEvent.click` the switch, assert `onChange` called with `true`.
- [ ] **Run the verification gates:** Gate E — `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk/components/tsumego/PhysicalModeToggle.tsx` returns nothing; Gate K — `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/PhysicalModeToggle.test.tsx`.
- [ ] **Commit:** `feat(kiosk-tsumego): add default-OFF physical-mode seam (readPhysicalMode + PhysicalModeToggle) for Phase D`.

---

### Task B2.5: 沉浸 solve-page reskin — immersive, breadcrumb, retheme, mount toggle, verify guard pass-through

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx` (imports 1–26; add immersive effect + session write; breadcrumb lines 270–278; chips/status/timer/prev-next retheme 284–363; mount toggle after 322)
- Modify `katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx` (mock `useImmersive`; update `15K`→breadcrumb assert; add toggle assert)
- Modify `katrain/web/ui/src/kiosk/__tests__/PhysicalBoardGuard.test.tsx` (add `phase:'disabled'` pass-through case + a `phase:'ready', geometry_ready:true, recognition_ready:false` case)
- Modify `katrain/web/ui/src/kiosk/KioskApp.tsx` (**remove `requireRecognition`** from the `tsumego/problem/:problemId` route, `KioskApp.tsx:69`)

**Interfaces:** Consumes: `useImmersive` from `../context/ImmersiveContext` (Phase A / A11), `PhysicalModeToggle` + `readPhysicalMode`/`writePhysicalMode` + `levelChinese`/`writeLastLevel` (B2.2/B2.4), `writeActiveSession` from `../utils/activeSession`, theme tokens. Produces: writes `kiosk_active_practice` + `kiosk_tsumego_last_level` so the hub 继续练习 card + 上次 highlight (B2.2) are populated. Match `tsumego-flow.html` ② (`.bc` breadcrumb, `.chiprow` pills, `.mrow` timer, immersive full-bleed board). Keep all data-testids: `tsumego-board`, `timer`, `attempts`, `last-time`, `prev-problem`, `next-problem`.

- [ ] **Step 1: Verify/preserve the A11 immersive effect (do NOT re-add).** **A11 already added** the `import { useImmersive } from '../context/ImmersiveContext';`, the `const { setImmersive } = useImmersive();` call, and the mount effect `useEffect(() => { setImmersive(true); return () => setImmersive(false); }, [setImmersive]);` to `TsumegoProblemPage`. Confirm it is still present (it hides the Dock + console so the solve page is full-bleed, design §5.2 ②) — **do not duplicate it**. If A11 has not yet landed, this task is blocked on it.
- [ ] **Step 2: Populate hub resume state on problem load.** Add `import { writeActiveSession } from '../utils/activeSession';` and `import { sequenceKey, readAutoAdvance, levelChinese, readPhysicalMode, writePhysicalMode, writeLastLevel } from './tsumegoUnits';` (extend the existing line-26 import). In an effect keyed on `[problem, currentIndex]`, when `problem` is set:
```tsx
writeLastLevel(problem.level);
writeActiveSession({
  kind: 'practice',
  label: `${levelChinese(problem.level)} · ${problem.category} · 第 ${currentIndex + 1} 题`,
  route: `/kiosk/tsumego/problem/${problem.id}`,
  ts: Date.now(),
});
```
- [ ] **Step 3: Replace the header with a breadcrumb.** Swap the header `<Box>` (lines 270–278: `ArrowBack` + category `<Typography variant="h6">` + level `<Chip>`) for a back button + breadcrumb matching `.bc` (死活 › 段/级 › 类别 › 第 N 题):
```tsx
<Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 2, flexWrap: 'wrap' }}>
  <Button onClick={goToUnits} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
  {problem && (
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      死活<Box component="span" sx={{ mx: 0.75, color: 'text.disabled' }}>›</Box>
      {levelChinese(problem.level)}<Box component="span" sx={{ mx: 0.75, color: 'text.disabled' }}>›</Box>
      {t(`tsumego:${problem.category}`, problem.category)}<Box component="span" sx={{ mx: 0.75, color: 'text.disabled' }}>›</Box>
      <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>第 {currentIndex + 1} 题</Box>
    </Typography>
  )}
</Box>
```
- [ ] **Step 4: Retheme status/timer/chips (single amber token).** The MUI `<Alert severity>` blocks (285–293) already resolve to theme success/error/info — leave them. Retheme the 黑先/hint chip row and the timer/attempts row (296–308) to `.chiprow`/`.mrow` styling: wrap timer/attempts/last-time in a `background.paper` pill row; keep the three data-testids (`timer`, `attempts`, `last-time`). The prev/next buttons (325–362) keep `color="primary"`; change the `色="inherit"` prev button to `background.paper` bg so it reads as secondary against the immersive board. Do not introduce any local amber hex — status "in-progress"/hint styling consumes `theme.warning.main` only.
- [ ] **Step 5: Mount PhysicalModeToggle (OFF ⇒ nothing else physical).** Add `import PhysicalModeToggle from '../components/tsumego/PhysicalModeToggle';`. Add state `const [physicalMode, setPhysicalMode] = useState(readPhysicalMode());` and `const capable = isVisionEnabled;`. After the action-button row (line 322) render:
```tsx
<Box sx={{ mt: 2 }}>
  <PhysicalModeToggle
    checked={physicalMode}
    capable={capable}
    onChange={(v) => { writePhysicalMode(v); setPhysicalMode(v); }}
  />
</Box>
```
Render NO physical state panel here — the 5-state `PhysicalStatePanel` + `usePhysicalTsumego` are Phase D and will read `physicalMode`. When OFF (default) this is the only physical surface; screen point-select solving is unchanged. **This step is the SINGLE declaration of `physicalMode` + the ONLY mount of `PhysicalModeToggle` in the whole track — Phase D's D1.3 CONSUMES this same `physicalMode` state and must NOT re-declare or re-read it.**
- [ ] **Step 6: Remove `requireRecognition` from the screen-solve route + verify guard pass-through.** First, in `KioskApp.tsx` **remove the `requireRecognition` prop from the `tsumego/problem/:problemId` route** (`KioskApp.tsx:69`) — screen solving is the DEFAULT; physical mode owns recognition only when the toggle is ON. Then add two cases to `PhysicalBoardGuard.test.tsx`: **(a)** mock `GeometryAPI.status` resolving `{ phase: 'disabled', session_calibrated: false, last_valid: false, capabilities: { camera_ready: false, led_ready: false, geometry_ready: false } }`, render `<PhysicalBoardGuard requireRecognition><div>实体棋盘内容</div></PhysicalBoardGuard>`, assert `await findByText('实体棋盘内容')` (phase `'disabled'` short-circuits to `ready` even with `requireRecognition`); **(b)** mock `{ phase: 'ready', … capabilities: { camera_ready: true, led_ready: false, geometry_ready: true }, recognition_ready: false }`, render the guard **without** `requireRecognition`, and assert the child content renders — proving a ready camera kiosk lacking `recognition_ready` still solves on screen once the route drops `requireRecognition`.
- [ ] **Step 7: Update the solve-page test.** In `TsumegoProblemPage.test.tsx` add `vi.mock('../context/ImmersiveContext', () => ({ useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }) }));` (page rendered without provider). Replace the `getByText('15K')` assert (line 132) with `getByText('15 级')` (breadcrumb via `levelChinese('15k')`); keep `getByText('手筋')`. Add `expect(screen.getByTestId('physical-mode-toggle')).toBeInTheDocument()`. Confirm `timer`/`attempts`/`prev-problem`/`next-problem` testid asserts still pass.
- [ ] **Run the verification gates:** Gate E — `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx` returns nothing; Gate K — `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/TsumegoProblemPage.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`. Runtime: `python -m katrain --ui web --force-build`, drive `/kiosk/tsumego/problem/<id>` at 1024×600, compare to `tsumego-flow.html` ② (immersive board + breadcrumb + toggle OFF shows no panel; return to hub shows 继续练习 card).
- [ ] **Commit:** `feat(kiosk-tsumego): immersive solve-page reskin — breadcrumb + slate tokens + physical-mode toggle seam`.

---

**B3 · 棋谱 (Kifu)** + **B4 · 直播 (Live)** — pure reskins · artifacts `kifu-flow.html`, `live-flow.html` · spec `design.md §5.4 / §5.6`

> **Route note:** the `kifu/:kifuId` route (`KioskApp:77`) **intentionally stays `PlaceholderPage`** — kifu is opened via Research («在研究中打开» → `/kiosk/research?kifu_id=…`, see C1.8), so no per-kifu page is scaffolded here. Do not build it.

---

### Task B3.1: Reskin KifuPage list panel to slate tokens

**Files:** Modify `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` (header/search block lines 141–182; card list lines 185–278; pagination lines 282–293). Test (keep green, no edit): `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx`.

**Interfaces:** Consumes: `kioskTheme` slate tokens (`background.paper #18211f`, `divider #2b3a35`, `primary.main #58b57a`, `primary.dark #26463a`, `text.secondary #93a49d`, `--raise2 #1d2725`), serif stack `"'Newsreader','Noto Serif SC',serif"`. Produces: no new exports; preserves all existing text ("棋谱库", "搜索棋手、赛事...", "N 局", "决赛", `data-testid="result-badge"` via `KioskResultBadge`, `data-testid="kifu-preview-nav"`).

- [ ] **Step 1: Header title → serif.** In the `<Typography variant="h4">` at lines 143–145, replace `sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}` with `sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500, letterSpacing: 0 }}` to match `kifu-flow.html` `.klhead h1` (serif, weight 500, 23px). Leave the "棋谱库" fallback text untouched (KifuPage.test line 100 asserts it).
- [ ] **Step 2: Search field → raise2 tokens.** In the `TextField` `sx` (lines 164–180) replace the four `rgba(255,255,255,*)` bg/border literals and the `rgba(74,107,92,0.4)` focus border with theme tokens matching `.ksearch`: `bgcolor: 'var(--raise2)'`, `& fieldset { borderColor: 'divider' }`, hover `borderColor: '#3a4d45'`, focused `borderColor: 'primary.main'`. Keep `borderRadius:'10px'`, size `small`, and the `SearchIcon` start adornment.
- [ ] **Step 3: Cards → jade-selected gradient.** In the `Card` `sx` (lines 205–214) replace the `rgba(76,175,80,*)` / `rgba(255,255,255,*)` literals: unselected `bgcolor:'background.paper'`, `borderColor:'divider'`; selected `border:1, borderColor:'primary.main', background:'linear-gradient(135deg,#1f3a30,#18211f)'`; hover unselected `borderColor:'#3a4d45'`. Match `.kcard` / `.kcard.sel` in `kifu-flow.html`. Keep `CardActionArea onClick={() => setSelectedId(kifu.id)}` and `borderRadius:'13px'`.
- [ ] **Step 4: Result badge chip tint + pagination.** Leave `<KioskResultBadge>` (shared) untouched. In the `Pagination` block (lines 282–293) change the divider literal `1px solid rgba(255,255,255,0.04)` → `1px solid`, `borderColor:'divider'`; keep `color="primary" shape="rounded" size="small"` (design `.kpage .pg.on` uses jade-deep, which `color="primary"` supplies).
- [ ] **Step 5: Run the verification gates (Gate K).** `cd /Users/fan/Repositories/katrain-kiosk-ui-redesign/katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/KifuPage.test.tsx` — all 16 KifuPage tests must stay green (title/search/cards/badge/round_name/total-count/nav/pagination). No `components/live/*` file edited → Gate K only.
- [ ] **Step 6: Commit.** `git commit -m "reskin(kiosk-kifu): B3.1 list panel → slate tokens + serif title"`.

---

### Task B3.2: KifuPage no-results empty state with echoed keyword

**Files:** Modify `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` (total-count line 146–148; card-list render branch 185–278). Test: add one case to `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx`.

**Interfaces:** Consumes: existing `query` (committed search string, line 28), `total`, `kifuList`, `loading`, `error`, `SearchIcon`. Produces: new empty block gated on `!loading && !error && kifuList.length === 0`; no prop/API changes.

- [ ] **Step 1: Total-count line echoes query.** Replace lines 146–148 body `{total.toLocaleString()} {t('games', '局')}` with a conditional: when `query` is non-empty show `{total.toLocaleString()} {t('games','局')} · "{query}"` (matches `kifu-flow.html` ② `0 局 · "柯杰九段"`); else the plain count. Keep the same `<Typography variant="body2" color="text.secondary">` wrapper.
- [ ] **Step 2: Add no-results branch in the list body.** Inside the scrollable list `Box` (lines 185–279), in the final `else` (line 194) that currently always maps cards, add a guard before the `.map`: when `kifuList.length === 0`, render an empty block instead of the empty `<Box>` of cards. Block: centered column, `SearchIcon` at `fontSize:50, color:'divider'`, `<Typography>` h6-ish "未找到棋谱" (`color:'text.secondary'`), and a body line `t('No records match "{q}"...', '没有匹配「{query}」的记录。试试棋手名、赛事名或年份。')`. Match `.kempty` in `kifu-flow.html` (dashed `divider` border, `background.paper`).
- [ ] **Step 3: Wire i18n.** Use `t('No games found','未找到棋谱')` for the heading and interpolate `query` into the body via template string (no new i18n infra — `useTranslation().t` already in scope, line 23).
- [ ] **Step 4: Add regression test.** In `KifuPage.test.tsx` add: mock `installFetch` to return `{ items: [], total: 0 }`, type into the search box `无此棋手`, advance past the 350ms debounce (`await waitFor` on empty state), then `expect(screen.getByText('未找到棋谱')).toBeInTheDocument()` and `expect(screen.getByText(/无此棋手/)).toBeInTheDocument()`. Follow the existing `installFetch`/`renderPage` harness (lines 66–88).
- [ ] **Step 5: Run the verification gates (Gate K + E).** Emoji check `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk` returns nothing (SearchIcon is SVG, not emoji), then `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/KifuPage.test.tsx`.
- [ ] **Step 6: Commit.** `git commit -m "feat(kiosk-kifu): B3.2 no-results empty state echoing search keyword"`.

---

### Task B3.3: KifuPage preview panel reskin + getAlbum loading skeleton + SVG scrub icons

**Files:** Modify `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` (imports lines 1–15; selection effect 78–107; preview panel 297–385; scrub buttons 334–353; open button 356–375). Test (keep green): `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx`.

**Interfaces:** Consumes: `KifuAPI.getAlbum(selectedId)`, `previewSgf`, `previewMoves`, `previewCurrentMove`, `LiveBoard` (shared, consume-only), `createSession`. Produces: new `previewLoading` state; preserves `data-testid="kifu-preview-nav"`, `aria-label` `first`/`prev`/`next`/`last`, and the "在研究中打开" → `/kiosk/research/session/${sessionId}` flow (NOT retargeted — post-Phase-C task).

- [ ] **Step 1: Add loading state + Skeleton import.** Add `Skeleton` to the `@mui/material` import (line 2–5). Add `const [previewLoading, setPreviewLoading] = useState(false);` beside the other preview states (near line 40).
- [ ] **Step 2: Gate the skeleton on the fetch.** In the selection effect (lines 78–107): after `if (selectedId === null) return;` add `setPreviewLoading(true);`; add `.finally(() => { if (!cancelled) setPreviewLoading(false); })` to the `KifuAPI.getAlbum` chain (line 87–104), preserving the existing `.catch` `console.error` fall-through.
- [ ] **Step 3: Render skeleton over the board only.** In the board `Box` (lines 308–316) render `previewLoading ? <Skeleton variant="rounded" sx={{ width:'88%', aspectRatio:'1', maxHeight:'100%', bgcolor:'var(--raise2)' }} /> : <LiveBoard ... />`. Leave the bottom nav bar (`data-testid="kifu-preview-nav"`, lines 324–376) OUTSIDE the skeleton gate so KifuPage.test "shows preview area with navigation" (line 150) and "disables Open until SGF loads" (line 162) stay green. Match `.kbwrap` sizing in `kifu-flow.html`.
- [ ] **Step 4: Preview panel + scrub reskin.** Change the preview `Box` bg (line 300) `bgcolor:'#0f0f0f'` → `bgcolor:'background.default'`; the nav bar bg (line 327) `#1a1a1a` → `'background.paper'`, divider literals → `borderColor:'divider'`. Replace the move-counter `fontFamily:'"IBM Plex Mono", monospace'` (line 342) with `'"JetBrains Mono", monospace'` (theme mono).
- [ ] **Step 5: Swap unicode scrub glyphs → SVG icons (no-emoji).** Import `SkipPrevious`, `NavigateBefore`, `NavigateNext`, `SkipNext` from `@mui/icons-material`. In the four scrub `<Button>`s (lines 334–353) replace the `⏮ ◀ ▶ ⏭` text children with these icons, KEEPING each button's existing `aria-label` (`first`/`prev`/`next`/`last`), `disabled`, and `onClick` intact so KifuPage.test boundary assertions (lines 200–219, `getByLabelText`) stay green. Matches `.kscrub .ico` SVGs in `kifu-flow.html`.
- [ ] **Step 6: Open button → jade.** In the "在研究中打开" `Button` sx (lines 362–372) replace `bgcolor:'rgba(74,107,92,0.8)'` / hover `rgba(74,107,92,1)` with `bgcolor:'primary.main'`, hover `bgcolor:'primary.dark'`; keep `ScienceIcon` startIcon, `disabled={!previewSgf || opening}`, and `handleOpenInResearch` unchanged (guard pass-through: `createSession` null → `openError` Snackbar preserved).
- [ ] **Step 7: Run the verification gates (Gate K + E).** `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk` returns nothing (confirms the ⏮/⏭ glyphs are gone), then `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/KifuPage.test.tsx` (all 16 green, incl. "opens in research… navigates to `/kiosk/research/session/sess-1`", line 174). Runtime: `python -m katrain --ui web --force-build`, drive `/kiosk/kifu` at 1024×600, select a card, confirm skeleton→board and SVG scrub icons vs `kifu-flow.html`.
- [ ] **Step 8: Commit.** `git commit -m "reskin(kiosk-kifu): B3.3 preview panel tokens + getAlbum skeleton + SVG scrub icons"`.

---

### Task B4.1: Reskin LivePage (list + preview) to slate tokens

**Files:** Modify `katrain/web/ui/src/kiosk/pages/LivePage.tsx` (left panel 67–104; right header 108–110; tabs 111–116; section labels 121–149; enter button 156–169). Do NOT edit `src/components/live/*` (SHARED). Do NOT edit `navTabs` (A10 owns the Dock 棋谱/直播 icons).

**Interfaces:** Consumes: `useLiveMatches({ limit: 50 })` (list poll = its default `pollInterval = 30000`, `useLiveMatches.ts` line 23), `useLiveMatch(selectedMatchId, { pollInterval: 5000, analysisMode: 'none' })` (LivePage line 36 — preview polls detail at 5s, never fetches analysis), shared `MatchList`/`LiveBoard`/`PlaybackBar`/`UpcomingList` (untouched). Produces: no new exports; preserves the `/kiosk/live/${selectedMatchId}` navigation (line 43) and the "进入直播"/"复盘" enter-button label logic (line 166).

- [ ] **Step 1: Right-panel header → serif.** The `<Typography variant="h5">{t('Live','直播')}` (line 109) — add `sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500 }}` to match `.lrhd h1` in `live-flow.html`. Keep the "直播" fallback.
- [ ] **Step 2: Tabs → jade pill treatment.** On the `<Tabs>` (lines 112–115) add `sx={{ minHeight:36, '& .MuiTabs-indicator':{ bgcolor:'primary.main' }, '& .Mui-selected':{ color:'primary.main' } }}` and `textColor="inherit"`. Keep the two `<Tab label="热门对局"/"即将开始">` — matches `.ltab` / `.ltab.on`.
- [ ] **Step 3: Section labels + divider tokens.** The two `<Typography variant="subtitle2" color="text.secondary">` "直播中 (N)" / "历史" (lines 122, 139) — keep tokens (already `text.secondary`); for the live-count label add a leading pulsing dot: a small `Box` `sx={{ width:7,height:7,borderRadius:'50%',bgcolor:'error.main',boxShadow:'0 0 7px', mr:0.8 }}` inline before the text, matching `.lsec .lv b` (the red live pulse). No emoji.
- [ ] **Step 4: Left panel + enter button.** The left preview `Box` border (lines 71–72) already uses `borderColor:'divider'` — leave. The enter `<Button variant="contained">` (lines 158–167) already resolves to `primary.main`; keep as-is (jade). Confirm `PlaybackBar` (shared) is passed `isLive={selectedMatch.status === 'live'}` (line 92) so the 跟播 Sync icon renders — untouched.
- [ ] **Step 5: Run the verification gates (Gate K).** `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint`. Verify poll defaults unchanged by reading back: `useLiveMatches` still called `{ limit: 50 }` (→ 30000 list poll) and preview `useLiveMatch` still `{ pollInterval: 5000, analysisMode: 'none' }`. No `components/live/*` edited → Gate K, no galaxy visual-regression needed.
- [ ] **Step 6: Commit.** `git commit -m "reskin(kiosk-live): B4.1 LivePage list+preview → slate tokens + serif header"`.

---

### Task B4.2: LivePage §5.6 page-level empty / match-ended states

**Files:** Modify `katrain/web/ui/src/kiosk/pages/LivePage.tsx` (no-live empty 132–136; preview header region 78–94; upcoming tab 151–153). Shared `MatchList`/`UpcomingList` stay untouched.

**Interfaces:** Consumes: `liveMatches` (derived, line 46), `finishedMatches` (line 47), `selectedMatch.status` (`'live'|'finished'`), `matchLoading`. Produces: page-level empty blocks only; `即将开始` empty remains delegated to shared `UpcomingList` (renders its own empty internally — NOT edited).

- [ ] **Step 1: No-live empty block reskin.** Replace the bare `<Typography>暂无直播` (lines 133–135) with a centered empty block: a `LiveTvIcon` (or `SportsEsportsIcon`) from `@mui/icons-material` at `fontSize:40, color:'divider'` + `<Typography color="text.secondary">{t('No live matches','暂无直播')}` in a `Box` (dashed `divider` border, `background.paper`), matching the `.kempty` idiom from `kifu-flow.html`. SVG icon only — no emoji.
- [ ] **Step 2: Match-ended chip in preview header.** In the left preview panel, above `<LiveBoard>` (before line 81), add a one-line status row: when `selectedMatch.status === 'finished'`, render a `<Chip label={t('Ended','已结束')} size="small">` (`bgcolor:'var(--raise2)', color:'text.secondary'`); when `'live'`, a red-dot "直播中" chip (`color:'error.main'`). Matches the `.wtop .live` / ended treatment in `live-flow.html`. Import `Chip` from `@mui/material`.
- [ ] **Step 3: Upcoming tab wrapper.** Around `<UpcomingList limit={20} />` (line 152) keep the shared component but ensure its container inherits `p:2` tokens; add a code comment that the `即将开始` empty state is owned by `UpcomingList` (shared, untouched) per §5.6 boundary. Do not add a duplicate page-level empty (would double-render).
- [ ] **Step 4: Run the verification gates (Gate K + E).** `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk` → nothing; then `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint`. Runtime: drive `/kiosk/live` at 1024×600 with an empty/finished dataset and compare the ended chip + no-live empty to `live-flow.html`.
- [ ] **Step 5: Commit.** `git commit -m "feat(kiosk-live): B4.2 LivePage §5.6 no-live empty + match-ended chip"`.

---

### Task B4.3: Reskin LiveMatchPage (spectate) to slate tokens

**Files:** Modify `katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx` (header 143–155; toggles 161–194; AiAnalysis wrapper 197–204; trend 207–209; playback 212). Do NOT edit `src/components/live/*` (SHARED — incl. `AiAnalysis`, `TrendChart`, `MatchInfo`). Keep green: `katrain/web/ui/src/components/live/AiAnalysis.test.tsx`.

**Interfaces:** Consumes: `useLiveMatch(matchId)` (detail poll = its default `pollInterval = 5000`, `analysisMode = 'poll'`, `useLiveMatch.ts` line 28), tap-for-PV state `activeMove`/`setActiveMove` (lines 44, 74–77) wired to `AiAnalysis onMoveSelect`/`activeMove` (lines 200–203) and `LiveBoard onIntersectionClick` (line 136). Produces: no new exports; preserves the tap-to-close PV behavior (galaxy hover path in `AiAnalysis` untouched → AiAnalysis.test line 43 stays green).

- [ ] **Step 1: Header + status chip tokens.** The header row (lines 143–155): `<Typography variant="h6">` player names → add `sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight:500 }}` (matches `.wtop h3`). The `<Chip>` (lines 150–154) keep `color={match.status==='live'?'success':'default'}` (success = `primary/#58b57a`), matches `.wtop .live`; keep the "直播中"/"已结束" labels.
- [ ] **Step 2: Feature-toggle bar → jade-selected.** The toggle `Box` (line 161) `bgcolor:'rgba(255,255,255,0.03)'` → `bgcolor:'background.paper'`, `borderColor:'divider'`. The four `<ToggleButton>`s keep their `selected`/`onChange` and MUI-default selected color (`primary.main`), matching `.wtg.on`. Keep the persistent `<Typography variant="caption">` labels (试下/形势/手数/AI) — no hover tooltips on touch. All four icons (`TouchAppIcon`/`MapIcon`/`FormatListNumberedIcon`/`TipsAndUpdatesIcon`) are SVG — no emoji.
- [ ] **Step 3: AiAnalysis + trend + playback wrappers.** The `Box` wrapping `<AiAnalysis>` (line 197) and the `<TrendChart>` container (line 207) — swap any `divider`/border literals to `borderColor:'divider'`; leave the shared components' internals untouched. `AiAnalysis` receives `onMoveSelect={setActiveMove}` + `activeMove` (tap-for-PV, not hover) — do not change to `onMoveHover`. `PlaybackBar` (line 212) gets `isLive={match.status==='live'}` — keep (Sync 跟播 icon).
- [ ] **Step 4: Run the verification gates (Gate K).** `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/components/live/AiAnalysis.test.tsx` (all 3 cases green — tap onMoveSelect, toggle-off, hover path intact). No `components/live/*` edited → Gate K (no galaxy visual-regression). Confirm `useLiveMatch(matchId)` still uses defaults (5000 poll / `analysisMode:'poll'`).
- [ ] **Step 5: Commit.** `git commit -m "reskin(kiosk-live): B4.3 LiveMatchPage spectate → slate tokens (tap-for-PV preserved)"`.

---

### Task B4.4: LiveMatchPage §5.6 PV-preview overlay + ended state polish

**Files:** Modify `katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx` (board `Box` 117–138; error/ended path 103–112). Shared `LiveBoard`/`AiAnalysis` untouched.

**Interfaces:** Consumes: `pvMoves` (derived from tapped `activeMove`, lines 74–77), `activeMove`, `handleMoveChange` (clears PV on navigation, lines 80–86). Produces: a page-level PV-active affordance driven by EXISTING `activeMove` state (no new props on shared `LiveBoard` — it already accepts `pvMoves` and `onIntersectionClick`, lines 128, 136).

- [ ] **Step 1: PV-preview overlay chip.** When `activeMove !== null` (a recommended move is tapped open), render a small absolutely-positioned chip over the board `Box` (lines 117–138): `<Chip>` labeled `t('Variation preview · tap board to close','变化预览 · 点击棋盘关闭')` (`bgcolor:'var(--raise2)', color:'text.secondary'`, `position:'absolute', top:8, left:8, zIndex:2`). The board `Box` needs `position:'relative'`. This surfaces the already-wired `onIntersectionClick={... () => setActiveMove(null)}` (line 136) to the user — matches the §5.6 待补 "PV 预览浮层". Import `Chip` if not present.
- [ ] **Step 2: Ended/error path token polish.** In the error/`!match` branch (lines 103–112) change `<Alert severity="error">` container `p:2` region to use `background.default`; keep the "加载对局失败" text and the back `<Button startIcon={ArrowBackIcon}>` → `/kiosk/live` (line 107). Confirm the live→finished `Chip` "已结束" (from B4.3) reads correctly when `match.status==='finished'`.
- [ ] **Step 3: Run the verification gates (Gate K + E).** `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk` → nothing; `cd katrain/web/ui && npm run build:kiosk-2d && npm run lint && npx vitest run src/components/live/AiAnalysis.test.tsx`. Runtime: drive `/kiosk/live/:id` at 1024×600, tap an AI-recommendation row → confirm PV overlay chip appears and tapping the board clears it (activeMove→null); compare to `live-flow.html` ② observation panel.
- [ ] **Step 4: Commit.** `git commit -m "feat(kiosk-live): B4.4 LiveMatchPage §5.6 PV-preview overlay + ended polish"`.

---

**B5 · 教程 (Tutorial)** + **B6 · 设置 (Settings)** — reskin + i18n wiring + account/logout · artifacts `tutorial-flow.html`, `settings-flow.html` · spec `design.md §5.7 / §5.8`

---

### Task B5.1: Reskin TutorialCategoriesPage to slate tokens

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.tsx` (whole file, 1–135; card block 86–127, header 71–76, loading 48–54, error 56–65, empty 79–84)
- Test: none exists for this page — verified by build + runtime artifact compare (`tutorial-flow.html`, "教程分类" grid state).

**Interfaces:** Consumes: `TutorialReadAPI.getCategories()`, `TutorialCategory` (unchanged). Produces: no new exports; route `/kiosk/tutorial` markup only. Preserves navigation target `/kiosk/tutorial/${cat.slug}`.

- [ ] **Step 1: Replace hardcoded card surfaces with tokens.** In the `<Card>` sx (lines 89–96), swap `bgcolor: 'rgba(255,255,255,0.05)'` → `bgcolor: 'background.paper'`, hover `'rgba(255,255,255,0.08)'` → `'var(--raise2)'`, add `border: '1px solid', borderColor: 'divider'`. Match the category-card look in `tutorial-flow.html` (rounded slate cards on `#0f1416`). No new state.
- [ ] **Step 2: Retokenize the category title.** Line 102 `color: '#5cb57a'` → `color: 'primary.main'` (the single jade token). Keep `fontWeight: 600`.
- [ ] **Step 3: Retokenize the loading spinner.** Line 51 `<CircularProgress />` → add `sx={{ color: 'primary.main' }}` so the spinner reads jade as in the artifact's loading state.
- [ ] **Step 4: Retokenize header + empty text.** Header `Typography variant="h5"` (line 72) — leave text `t('tutorial:title','教程')` intact; the empty-state text (81–83) already uses `color="text.secondary"` which now resolves to `#93a49d` — no change needed, just confirm no local hex remains via grep in Step 5.
- [ ] **Step 5: Grep for surviving hex.** `grep -nE "#|rgba" katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.tsx` must return nothing (all color literals now tokens/CSS vars).
- [ ] **Run the verification gates:** Gate K — `cd /Users/fan/Repositories/katrain-kiosk-ui-redesign/katrain/web/ui && npm run build:kiosk-2d && npm run lint`. (No vitest file for this page.) Then Runtime: `python -m katrain --ui web --force-build`, drive `/kiosk/tutorial` at 1024×600 and compare the grid to `tutorial-flow.html`.
- [ ] **Commit:** `git commit -m "reskin(kiosk-tutorial): TutorialCategoriesPage → slate tokens [B5.1]"`

### Task B5.2: Reskin TutorialBooksPage to slate tokens

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TutorialBooksPage.tsx` (whole file, 1–135; cards 96–128, header 72–86, loading 49–55, error 57–70)
- Test: none — build + runtime compare (`tutorial-flow.html`, "书籍列表" state).

**Interfaces:** Consumes: `TutorialReadAPI.getBooks(cat)`, `TutorialBook` (unchanged). Preserves back nav to `/kiosk/tutorial` and drill target `/kiosk/tutorial/book/${book.id}`.

- [ ] **Step 1: Retokenize book cards.** In `<Card>` sx (99–106) apply the SAME swap as B5.1 Step 1 (`background.paper` / `var(--raise2)` hover / `border` + `divider`). Match the book-card row in `tutorial-flow.html`.
- [ ] **Step 2: Retokenize the chapter-count accent.** Line 120 `color: '#5cb57a'` → `color: 'primary.main'`.
- [ ] **Step 3: Retokenize spinner + confirm back button.** Line 51 `<CircularProgress />` → `sx={{ color: 'primary.main' }}`. Leave the `ArrowBack` icon-button (line 75) as-is — it is the standard back affordance; verify it inherits `text.primary`.
- [ ] **Step 4: Grep for surviving hex.** `grep -nE "#|rgba" katrain/web/ui/src/kiosk/pages/TutorialBooksPage.tsx` returns nothing.
- [ ] **Run the verification gates:** Gate K — `npm run build:kiosk-2d && npm run lint`. Runtime: drive `/kiosk/tutorial/<category>` at 1024×600, compare to `tutorial-flow.html` book-list state.
- [ ] **Commit:** `git commit -m "reskin(kiosk-tutorial): TutorialBooksPage → slate tokens [B5.2]"`

### Task B5.3: Reskin TutorialBookDetailPage chapter tree to slate tokens

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TutorialBookDetailPage.tsx` (whole file, 1–210; `JADE` const line 23, accordion block 137–201, header 108–124, loading 85–91, error 93–106)
- Test: none — build + runtime compare (`tutorial-flow.html`, "章节目录/accordion" state).

**Interfaces:** Consumes: `TutorialReadAPI.getBook`/`getSections`, `TutorialBookDetail`, `TutorialSection`, `SectionNavState` (unchanged). MUST keep the parallel `Promise.all` chapter fetch (55–63) and the `SectionNavState` object built at 161–168 (drives the section-page breadcrumb) byte-for-byte.

- [ ] **Step 1: Remove the local `JADE` const, use the token.** Delete `const JADE = '#5cb57a';` (line 23). Replace its one consumer — the `PlayCircleOutline` at line 191 `sx={{ color: JADE }}` → `sx={{ color: 'primary.main' }}`.
- [ ] **Step 2: Retokenize the Accordion surface.** In the `<Accordion>` sx (141–146) swap `bgcolor: 'rgba(255,255,255,0.05)'` → `'background.paper'`; keep `'&:before': { display: 'none' }` and `borderRadius: '12px'`. Add `border: '1px solid', borderColor: 'divider'`. Match the collapsible chapter card in `tutorial-flow.html`.
- [ ] **Step 3: Retokenize the section rows.** Confirm `ListItemButton` (171–174) uses default `text.primary`; the `figure_count` "图" caption (188–190) stays `color="text.secondary"`. No hex to change here — verify only.
- [ ] **Step 4: Retokenize spinner.** Line 88 `<CircularProgress />` → `sx={{ color: 'primary.main' }}`.
- [ ] **Step 5: Grep for surviving hex.** `grep -nE "#|rgba|JADE" katrain/web/ui/src/kiosk/pages/TutorialBookDetailPage.tsx` returns nothing.
- [ ] **Run the verification gates:** Gate K — `npm run build:kiosk-2d && npm run lint`. Runtime: drive `/kiosk/tutorial/book/<id>` at 1024×600, expand/collapse a chapter, compare to `tutorial-flow.html` accordion state.
- [ ] **Commit:** `git commit -m "reskin(kiosk-tutorial): TutorialBookDetailPage → slate tokens [B5.3]"`

### Task B5.4: Reskin TutorialSectionPage + update its test

> **isPortrait is NOT this task's concern — Task A3 owns it.** A3 already removed the `useOrientation` import + `isPortrait` destructure from this page, collapsed the `flexDirection` split to `'row'`, and stripped the `isPortrait: false` field from this test's `OrientationContext` mock. Start from that landscape-only state; this task is pure visual reskin.

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TutorialSectionPage.tsx` (no-video fallback bg ~223, loading 97–103, board/media split 150–246 — post-A3 line numbers; the `isPortrait` sites at former 18/48/277 are already gone)
- Modify `katrain/web/ui/src/kiosk/pages/TutorialSectionPage.test.tsx` (assertions 62–115 only — the mock is A3's)

**Interfaces:** Consumes: `TutorialReadAPI.getSection`/`assetUrl`, `SGFBoard`+`SGFPayload`, `TutorialVideoPlayer` (all SHARED, consume-only — no prop changes). Preserves: aria-labels `上一图`/`下一图`/`move-step`, the per-figure `video_asset` playback model, `referrerPolicy` behavior, breadcrumb string builder (117–120), and figure-nav text `图X (i / N)`.

- [ ] **Step 1: Confirm the A3 landscape baseline.** `grep -n isPortrait src/kiosk/pages/TutorialSectionPage.tsx` returns nothing and the media split is already `flexDirection: 'row'` (A3 landed this). If A3 has not landed yet, this task is blocked on it — do not re-introduce or re-remove `isPortrait` here.
- [ ] **Step 2: Retokenize the no-video fallback panel.** In the fallback `<Box>` sx (~215–226) swap `bgcolor: 'rgba(0,0,0,0.18)'` → `bgcolor: 'var(--raise2)'`; keep `borderRadius: 2`. Match the "本图暂无视频" narration-fallback card in `tutorial-flow.html` (study split, right column, text figure).
- [ ] **Step 3: Retokenize spinner + slider accent.** Line ~100 `<CircularProgress />` → `sx={{ color: 'primary.main' }}`. The `<Slider>` (~186–193) inherits `primary.main` — confirm no local color override needed. Grep the file for `#|rgba` → nothing.
- [ ] **Step 4: Keep the test assertions green.** In `TutorialSectionPage.test.tsx` do NOT touch the `OrientationContext` mock (A3 already trimmed it). All text/aria assertions (`手数`, `图1 (1 / 2)`, `本图暂无视频`, breadcrumb `教程 ▸ 1. 第一节`, `测试教程书 ▸ 基础 ▸ 1. 第一节`) survive the reskin unchanged — keep them.
- [ ] **Run the verification gates:** Gate K — `npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/pages/TutorialSectionPage.test.tsx` (all 5 cases green). Runtime: drive `/kiosk/tutorial/section/<id>` at 1024×600, step 图1→图2, compare board-left / media-right split and the narration fallback to `tutorial-flow.html`.
- [ ] **Commit:** `git commit -m "reskin(kiosk-tutorial): TutorialSectionPage slate tokens [B5.4]"`

### Task B6.1: Wire real i18n on SettingsPage language chips (中/英 only)

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` (imports 1–7, dead `useState('zh')` line 13, language `OptionChips` block 65–75)
- Test: none for SettingsPage — build + runtime language-switch verification.

**Interfaces:** Consumes (NEWLY, shared consume-only): `useSettings(): { language: string; setLanguage(l): Promise<void> }` from `../../context/SettingsContext`. Produces: language chips bound to real persisted i18n. Chip↔code map: 中→`'cn'`, 英→`'en'`.

- [ ] **Step 1: Import the real settings hook and drop the dead local state.** Add `import { useSettings } from '../../context/SettingsContext';`. Delete line 13 `const [language, setLanguage] = useState('zh');`. In the body add:
  ```ts
  const { language, setLanguage } = useSettings();
  // kiosk exposes only 中/英; map the 2 chip values to the app's language codes.
  const langChip = language === 'en' ? 'en' : 'cn';
  ```
  Remove the now-unused `useState` import if no other consumer remains (autoAdvance still uses it — keep `useState`).
- [ ] **Step 2: Trim the chips to 中/英 and wire onChange.** Replace the language `OptionChips` (65–75) options+value+onChange with:
  ```tsx
  options={[
    { value: 'cn', label: t('中', '中') },
    { value: 'en', label: t('英', '英') },
  ]}
  value={langChip}
  onChange={(v) => { void setLanguage(v as string); }}
  ```
  Drop the `ja`/`ko` entries entirely (matches `settings-flow.html` "仅中 / 英").
- [ ] **Step 3: Scope guard — do NOT rebuild i18n infra.** `SettingsContext.setLanguage` already calls `i18n.loadTranslations` + persists `katrain_language` (verified 61–70). Add a one-line code comment noting that switching to `'en'` may surface hardcoded 中文 in other kiosk pages, and that broader `t()`-wrapping is a **follow-up track**, out of scope here.
- [ ] **Run the verification gates:** Gate K (this only **consumes** shared `SettingsContext` — a consume, not an edit — so no full `npm run build` is required) — `npm run build:kiosk-2d && npm run lint`. Gate E — `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk` returns nothing. Runtime: drive `/kiosk/settings`, tap 英 then 中, confirm the toggle persists across reload (localStorage `katrain_language`).
- [ ] **Commit:** `git commit -m "feat(kiosk-settings): wire real i18n on 中/英 language chips [B6.1]"`

### Task B6.2: Create AccountSection component (user + 退出登录)

**Files:**
- Create `katrain/web/ui/src/kiosk/components/settings/AccountSection.tsx`
- Test: none — build + runtime compare (`settings-flow.html`, "已登录 · 智星盒账户" row).

**Interfaces:** Consumes (NEWLY, shared consume-only): `useAuth(): { user: { username; rank; credits; avatar_url? } | null; logout(): Promise<void> }` from `../../../context/AuthContext`; `useNavigate`. Produces: `export default function AccountSection` (no props). Implements the A12 redirect contract: after `logout()` navigate to `/kiosk/login`.

- [ ] **Step 1: Write the component skeleton + signature.**
  ```tsx
  import { Box, Typography, Button } from '@mui/material';
  import LogoutIcon from '@mui/icons-material/Logout';
  import { useNavigate } from 'react-router-dom';
  import { useAuth } from '../../../context/AuthContext';
  import { useTranslation } from '../../../hooks/useTranslation';

  export default function AccountSection() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const handleLogout = async () => { await logout(); navigate('/kiosk/login', { replace: true }); };
    // …section markup…
  }
  ```
  (Use the `@mui/icons-material` SVG `Logout` — NO emoji per rule 3.)
- [ ] **Step 2: Render the logged-in row.** Show `t('Signed in', '已登录')` label + `user?.username ?? t('Guest','访客')` and a secondary `智星盒账户` caption, styled with tokens (`background.paper` surface, `divider` border, `text.primary`/`text.secondary`). Match the "已登录 · 智星盒账户 / fan" block in `settings-flow.html`.
- [ ] **Step 3: Render the 退出登录 button.** `<Button variant="outlined" color="error" startIcon={<LogoutIcon />} onClick={handleLogout}>{t('Sign out','退出登录')}</Button>` — `error` resolves to the `#e2685c` token. Add `data-testid="settings-logout"` for future QA.
- [ ] **Step 4: Confirm import boundary.** The path `../../../context/AuthContext` is SHARED (not `src/galaxy`/`Board3D`/`VideoRecorder`), so eslint `no-restricted-imports` is satisfied; grep the new file for any `#|rgba` hex → nothing (tokens only).
- [ ] **Run the verification gates:** Gate K (this only **consumes** shared `AuthContext` — a consume, not an edit — so no full `npm run build` is required) — `npm run lint && npm run build:kiosk-2d`. Runtime deferred to B6.4 (component is mounted there); for now confirm it compiles standalone.
- [ ] **Commit:** `git commit -m "feat(kiosk-settings): AccountSection with 退出登录 → /kiosk/login [B6.2]"`

### Task B6.3: Create PhysicalBoardStatus component (camera/LED/calibration)

**Files:**
- Create `katrain/web/ui/src/kiosk/components/settings/PhysicalBoardStatus.tsx`
- Create `katrain/web/ui/src/kiosk/__tests__/PhysicalBoardStatus.test.tsx` (render test — see Step 5)

**Interfaces:** Consumes: `useGeometry(): { status: GeometryStatus }` from `../../context/GeometryContext` (kiosk context — NOT shared); `GeometryStatus.capabilities.{camera_ready,led_ready,geometry_ready}` + `session_calibrated` from shared `api/geometryApi` (already consumed elsewhere). Produces: `export default function PhysicalBoardStatus` (no props). Preserves the hardware-留桩 fall-through: unknown/false capability → neutral gray dot, never a thrown error.

- [ ] **Step 1: Write signature + read status.**
  ```tsx
  import { Box, Typography } from '@mui/material';
  import { useGeometry } from '../../context/GeometryContext';
  import { useTranslation } from '../../../hooks/useTranslation';
  export default function PhysicalBoardStatus() {
    const { status } = useGeometry();
    const { t } = useTranslation();
    const { camera_ready, led_ready, geometry_ready } = status.capabilities;
    // …three status dots…
  }
  ```
  (Steps 2–3 call `t(...)` — the `useTranslation` import + `const { t } = useTranslation();` above are **required** or the file will not compile.)
- [ ] **Step 2: Define the three rows.** Build `const rows = [{ key:'camera', label: t('Camera','摄像头'), ok: camera_ready }, { key:'led', label:'LED', ok: led_ready }, { key:'calib', label: t('Calibration','几何标定'), ok: geometry_ready }];` Render each as label + a status dot.
- [ ] **Step 3: Token the status dot (留桩 fall-through).** Dot color = `ok ? 'primary.main' (jade ready)` : `'text.disabled' (gray, hardware absent)` — a false/unknown capability yields the gray dot per rule 4, never an error. Use a small `Box` (8px circle). Add a top-line 状态 chip: when `status.session_calibrated` show `t('Geometry locked','几何已锁定')` in `warning.main` (the single amber token), else `t('Not calibrated','待校准')`.
- [ ] **Step 4: Grep for hex + confirm no emoji.** `grep -nE "#|rgba" …/PhysicalBoardStatus.tsx` returns nothing; dots use SVG/`Box`, no emoji.
- [ ] **Step 5: Add a render test.** Create `PhysicalBoardStatus.test.tsx`: mock `../../context/GeometryContext`'s `useGeometry` → `{ status: { session_calibrated: true, capabilities: { camera_ready: true, led_ready: false, geometry_ready: true } } }`; render inside `<ThemeProvider theme={kioskTheme}>`; assert the three row labels (`摄像头`, `LED`, `几何标定`) render and the top status chip shows `几何已锁定`. Add a `session_calibrated:false` case → `待校准`, and an all-`false`-capabilities case → three neutral/gray dots with **no throw** (留桩 fall-through).
- [ ] **Run the verification gates:** Gate K (consumes only kiosk `GeometryContext` + already-consumed shared type) — `npm run build:kiosk-2d && npm run lint && npx vitest run src/kiosk/__tests__/PhysicalBoardStatus.test.tsx`. Runtime deferred to B6.4.
- [ ] **Commit:** `git commit -m "feat(kiosk-settings): PhysicalBoardStatus camera/LED/calibration row [B6.3]"`

### Task B6.4: Assemble & reskin SettingsPage (external cards 敬请期待, mount sections, tokens)

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` (imports 1–7, `platforms` array 21–26, page root 28–29, header 30–31, physical-board block 33–36, external-platform grid 77–91)
- Test: none — build + runtime compare (`settings-flow.html`, full "设置主页" state).

**Interfaces:** Consumes: `AccountSection` (B6.2), `PhysicalBoardStatus` (B6.3). Preserves: existing rotation `OptionChips` (already 0/180 from A3 — reference, don't re-trim), 死活题 auto-advance `Switch` + `readAutoAdvance`/`writeAutoAdvance`, and the `/kiosk/vision/setup` recalibrate button.

- [ ] **Step 1: Import the two new sections.** Add `import AccountSection from '../components/settings/AccountSection';` and `import PhysicalBoardStatus from '../components/settings/PhysicalBoardStatus';`.
- [ ] **Step 2: Mount PhysicalBoardStatus in the 实体棋盘 block.** Inside the block at 33–36, above the existing `Button` (重新标定棋盘), insert `<PhysicalBoardStatus />`. Keep the recalibrate `Button onClick={() => navigate('/kiosk/vision/setup')}` intact. Match the "实体棋盘 → 几何已锁定 → 摄像头·LED·几何标定 → 重新标定棋盘" stack in `settings-flow.html`.
- [ ] **Step 3: Make external-platform cards non-interactive + 敬请期待.** In the grid (80–91) remove `CardActionArea` (dead nav target) and its import if unused; render each platform as a plain `<Card variant="outlined">` with the name + a `t('Coming soon','敬请期待')` caption in `text.disabled`, and set `sx={{ opacity: 0.6, pointerEvents: 'none' }}`. Keep the `platforms` array (21–26) as the data source.
- [ ] **Step 4: Mount AccountSection at the page foot.** Append `<AccountSection />` after the external-platform grid, separated by a `<Divider sx={{ my: 3 }} />`.
- [ ] **Step 5: Retokenize the page shell + header.** Root `<Box sx={{ …, p: 3 }}>` — confirm it inherits `background.default`. Header `Typography variant="h5"` "设置": keep text; the whole page must carry only tokens — grep `grep -nE "#|rgba" katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` returns nothing. Match section spacing/dividers to `settings-flow.html`.
- [ ] **Run the verification gates:** Gate K — `npm run build:kiosk-2d && npm run lint`. Gate E — `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk` returns nothing. Runtime: `python -m katrain --ui web --force-build`, drive `/kiosk/settings` at 1024×600 — verify (a) PhysicalBoardStatus dots render with the LedAPI/geometry fall-through (gray dots when hardware absent, no crash), (b) external cards read 敬请期待 and are non-tappable, (c) 退出登录 routes to `/kiosk/login` — and compare the whole page to `settings-flow.html`.
- [ ] **Commit:** `git commit -m "reskin(kiosk-settings): assemble account + board-status sections, 敬请期待 platforms, slate tokens [B6.4]"`

---

**B7 · 摆谱 (Baipu)** — pure reskin (reclassified out of Phase D); preserves phase machine + all `data-testid` + hardware-留桩 fall-throughs · artifact `baipu-flow.html` · spec `design.md §5.5`

---

### Task B7.1: Reskin 摆谱 list page (screen ①) to slate tokens

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx` (whole file, 332 lines; edits concentrated at 161–322)
- Test `katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx` (reskin — verified by build + runtime drive; no new unit test, existing `src/api/baipuApi.test.ts` remains the contract test)

**Interfaces:**
- Consumes (unchanged): `KifuAPI.getAlbums/getAlbum` (`../api/kifuApi`), `cacheSgf/listRecent/getCachedSgf/BaipuRecentEntry` (`../../api/baipuApi`), `sgfToMoves` (`../../utils/sgfSerializer`), `LiveBoard` (`../../components/live/LiveBoard`), `useTranslation`, `useOrientation`. All shared/consume-only — **no props added**.
- Produces (unchanged): route `/kiosk/baipu/session/:source` via `startSession`; navigation `state:{sgf,name}`. Preserves data-testids `baipu-import`, `baipu-recent-chip`, `baipu-empty`, `baipu-start`.
- Depends on Phase A: `kioskTheme` slate palette (`background.paper #18211f`, `background.default #0f1416`, `divider #2b3a35`, `text.*`, `primary.main #58b57a`, `primary.dark #26463a`) and `--raise2 #1d2725` CssBaseline var already in place.

- [ ] **Step 1: Swap the search `TextField` ad-hoc greys to slate raise tokens.** In the `sx` at lines 195–200 replace `bgcolor: 'rgba(255,255,255,0.025)'` → `bgcolor: 'var(--raise2)'` and the fieldset `borderColor: 'rgba(255,255,255,0.05)'` → `borderColor: 'divider'`. Keep `borderRadius:'10px'`, `fontSize:'0.88rem'`, and the `SearchIcon` adornment (color `text.secondary`) intact. Match screen ① search bar in `baipu-flow.html`.
- [ ] **Step 2: Reskin the recent-resume chips (留桩 resume path).** At the `Chip` (lines 213–220) change `sx={{ bgcolor: 'rgba(255,255,255,0.06)', maxWidth: 180 }}` → `sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', maxWidth: 180 }}`. Do NOT touch `onClick={() => handleResume(r)}`, `data-testid="baipu-recent-chip"`, or the `getCachedSgf` fall-through in `handleResume` (lines 144–152). Update the `Divider` at line 223 `borderColor: 'rgba(255,255,255,0.05)'` → `borderColor: 'divider'`.
- [ ] **Step 3: Reskin the kifu cards + selected state to jade tokens.** In the `Card` `sx` (lines 253–258) replace: selected `bgcolor` `'rgba(76,175,80,0.12)'` → `'primary.dark'`, unselected `'rgba(255,255,255,0.05)'` → `'background.paper'`; `borderColor` selected `'primary.main'` (keep), unselected `'rgba(255,255,255,0.1)'` → `'divider'`. Keep the `border: selected ? 2 : 1`, `borderRadius:'8px'`, the `Fade` stagger (`ROW_STAGGER`), and all inner `Typography` (event / move_count / players). Match the selected-card treatment in screen ① of `baipu-flow.html`.
- [ ] **Step 4: Reskin the preview panel + 开始摆谱 CTA surfaces.** Preview `Box` (lines 292–297) `bgcolor: '#0f0f0f'` → `bgcolor: 'background.default'`, and both border lines `'1px solid rgba(255,255,255,0.06)'` → `'1px solid'` + `borderColor:'divider'`. The CTA footer `Box` (line 304) `bgcolor: '#1a1a1a'` → `bgcolor: 'background.paper'`, its `borderTop` rgba → `divider`. Leave the `baipu-start` `Button` (`variant="contained"`, `minWidth:220`, `minHeight:52`) and `LiveBoard` (consume-only, `showCoordinates`, `currentMove={previewMoves.length}` end-preview) untouched — the CTA already inherits `primary.main` jade.
- [ ] **Step 5: Reskin the empty state + pagination border.** `baipu-empty` `Box` (line 236): keep `GridOnIcon` SVG (no emoji), leave text; it already uses `text.secondary`. Pagination wrapper (line 285) `borderTop: '1px solid rgba(255,255,255,0.04)'` → `borderTop:'1px solid'` + `borderColor:'divider'`; `Pagination color="primary"` stays. Confirm `data-testid="baipu-empty"` and the `visibleKifu.filter(k=>k.board_size===19)` 19-only gate (line 87) are unchanged.
- [ ] **Step 6: Verify no emoji / no raw greys leaked.** `grep -nE "rgba\(255,255,255|#0f0f0f|#1a1a1a|rgba\(76,175,80" katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx` returns nothing; `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx` returns nothing (Gate E). Icons remain `@mui/icons-material` SVG (`Search/GridOn/UploadFile/History`).
- [ ] **Step 7: Run the verification gates (Gate K).** `cd /Users/fan/Repositories/katrain-kiosk-ui-redesign/katrain/web/ui && npm run build:kiosk-2d` (chains `verify:kiosk-2d`) + `npm run lint` (import-boundary clean; no new import outside shared/kiosk) + `npx vitest run src/api/baipuApi.test.ts`. Kiosk-only file, no shared edit → Gate K (not S).
- [ ] **Step 8: Commit.** `git add katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx && git commit -m "reskin(kiosk): 摆谱 list page → slate tokens (B7.1)"`.

---

### Task B7.2: Reskin 摆谱 session page (screens ②③④) to slate + consume LED_HEX

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` (whole file, 583 lines; edits at 20–61, 91–113, 362–526)
- Test `katrain/web/ui/src/api/baipuApi.test.ts` (existing contract test re-run — no logic change; reskin verified by runtime drive)

**Interfaces:**
- Consumes (unchanged): `BaipuAPI.load/capture`, `getCachedSgf/saveProgress/getProgress/clearProgress`, `canonToBoard/canonToGtp`, types `BaipuStep/BaipuMeta/BaipuGeometryCorrection` (`../../api/baipuApi`); `LedAPI`, `LedColor` (`../../api/ledApi`); `LiveBoard` with existing props `nextMovePoint`/`capturedPositions`/`currentMove` (consume-only, **no props added**).
- **New consume:** `import { LED_HEX } from '../constants/ledColors'` (kiosk-only constant created in Phase A/A4; `LedIntent='black'|'white'|'remove'|'hint'`, `LED_HEX.black='#ff3b30'`, `.white='#34c759'`, `.remove='#2f6fff'`). Kiosk→kiosk import, not shared → stays Gate K.
- Produces (unchanged): full phase machine `loading→guiding→await_removal→done|error`. Preserves data-testids `baipu-drift-banner`(+`data-drift-status`), `baipu-status-bar`, `baipu-progress`, `baipu-frame-count`, `baipu-player-B/W`, `baipu-next-chip`, `baipu-current-move`, `baipu-latest-frame`, `baipu-confirm`, `baipu-removed`, `baipu-done-back`, `baipu-relight`, `baipu-undo`, `baipu-exit`, `baipu-removal-banner`, `baipu-capture-error`, `baipu-capture-pending`, `baipu-resume-continue`.
- Depends on Phase A: slate palette + the single amber token `warning.main #e0a24a`.

- [ ] **Step 1: Centralize the LED-intent hexes into `LED_HEX` (preservation item a).** Add `import { LED_HEX } from '../constants/ledColors';` at top. Replace every raw LED-semantic literal 1:1, same value/semantics: `baipu-next-chip` (lines 415–416) `border: `2px solid ${nextColor==='B' ? '#ff3b30' : '#34c759'}`` → use `LED_HEX.black`/`LED_HEX.white`, and its `bgcolor` `rgba(255,59,48,0.14)`/`rgba(52,199,89,0.14)` → `alpha(LED_HEX.black,0.14)`/`alpha(LED_HEX.white,0.14)` (add `import { alpha } from '@mui/material/styles'`). `baipu-removal-banner` (line 489) `#2f6fff`/`rgba(47,111,255,0.18)` → `LED_HEX.remove`/`alpha(LED_HEX.remove,0.18)`. `DriftBanner` corrected branch (line 31) `#2f6fff`/`rgba(47,111,255,0.18)` → `LED_HEX.remove`/`alpha(...)`.
- [ ] **Step 2: Reskin `HealthDot` (留桩 gray-dot preservation).** At line 93 replace the ternary `bgcolor: ok == null ? '#666' : ok ? '#34c759' : '#ff3b30'` → `bgcolor: ok == null ? 'text.disabled' : ok ? 'success.main' : 'error.main'`. **Do not change the conditional itself** — `ok==null` (LED unknown / LedAPI not driven) must still render the muted dot per constraint 4. Label typography stays `text.secondary`.
- [ ] **Step 3: Reskin the amber drift banners to the single warning token.** In `DriftBanner`, the shared `warn` style object (line 24) `bgcolor:'rgba(255,149,0,0.20)'`, `borderTop:'2px solid #ff9500'` → `bgcolor: alpha(theme.warning.main,0.20)`, `borderTop: `2px solid ${theme.warning.main}`` (pull `theme` via `useTheme()` inside `DriftBanner`, or use `warning.main` sx string form: `bgcolor:'warning.main'` at 0.2 alpha via `sx` callback `(th)=>alpha(th.palette.warning.main,0.2)`). This replaces the local `#ff9500` with `theme.warning.main #e0a24a` (the one amber token — 待校准/物理提示 all consume it). Keep both `data-drift-status="stale"`/`"frozen"` testids and the exact bilingual strings.
- [ ] **Step 4: Reskin the status bar + right rail surfaces.** `baipu-status-bar` (line 369) `bgcolor:'#1a1a1a'`, `borderBottom:'1px solid rgba(255,255,255,0.06)'` → `bgcolor:'background.paper'`, `borderBottom:'1px solid'`+`borderColor:'divider'`. `baipu-progress` chip (line 380) `bgcolor:'rgba(255,255,255,0.08)'` → `bgcolor:'var(--raise2)'`; swap its `fontFamily:'"IBM Plex Mono", monospace'` → `'"JetBrains Mono", monospace'` (theme mono). Board `Box` (line 392) `bgcolor:'#0f0f0f'` → `background.default`. Right rail `borderLeft` rgba → `divider`. `baipu-latest-frame` (lines 431–432) `bgcolor:'rgba(255,255,255,0.05)'`/`border rgba(255,255,255,0.1)` → `background.paper`/`divider`, and its mono `Typography` (line 435) `"IBM Plex Mono"` → `"JetBrains Mono"`.
- [ ] **Step 5: Reskin `PlayerPanel` active/idle to jade tokens; keep physical-stone swatches.** Lines 103–107: active `borderColor:'primary.main'` (keep), `bgcolor:'rgba(92,181,122,0.12)'` → `'primary.dark'`; idle `borderColor:'rgba(255,255,255,0.12)'` → `'divider'`, `bgcolor:'rgba(255,255,255,0.04)'` → `'background.paper'`. **Leave the stone dot (line 109) `#1a1a1a`/`#e8e4df` as-is** — it depicts physical black/white stones, not a theme surface. Keep `data-testid`, `data-active`, and the `to place / 落子中` `Chip color="primary"`.
- [ ] **Step 6: Reskin the capture-error banner; confirm the capturePending barrier stays a true blocking overlay (preservation c).** `baipu-capture-error` (line 504) `bgcolor:'rgba(255,59,48,0.18)'`, `borderTop:'2px solid #ff3b30'` → `alpha(theme.error.main,0.18)` + `2px solid` `error.main` (semantic error surface, NOT `LED_HEX`). For `baipu-capture-pending` (lines 514–526): **do not convert to a Snackbar/toast** — keep `position:'absolute', inset:0, zIndex:10` and the dimmed scrim `bgcolor:'rgba(0,0,0,0.55)'`; only confirm the `Typography` uses readable on-scrim color (keep `#fff`). This is the "keep hands clear" barrier and must remain modal.
- [ ] **Step 7: Confirm the primary CTAs keep 88px touch height + no emoji.** `baipu-confirm` (line 444) `minHeight:88` and `baipu-removed` (line 457) `minHeight:88` unchanged; `baipu-removed` stays `color="warning"` (now the slate amber token). No icon/emoji added anywhere — the "done" surface uses text only (no 🎉/EmojiEvents needed here; celebration lives in the tsumego track, not baipu). `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` → empty (Gate E).
- [ ] **Step 7b: Reskin the remaining EXISTING interactive surfaces (retheme only — do NOT rebuild).** Beyond the `DriftBanner` (Step 3) and capture-error banner (Step 6) already covered, retheme to slate tokens the other surfaces that **already exist** in `BaipuSessionPage`: the **resume / undo / exit confirm dialogs** (triggered from `baipu-resume-continue` / `baipu-undo` / `baipu-exit` — MUI `<Dialog>` paper → `background.paper`, `divider` hairlines, primary/error CTAs via tokens) and the **capture-`disabled` advisory** (the `{kind:'disabled'}` "拍照不可用 → 继续" note). Preserve every `data-testid` and the exact confirm/cancel handlers + the 留桩 fall-through (retheme touches only `sx`/color). **Truly-unbuilt §5.5 待补 states stay OUT OF SCOPE** — this step only re-themes surfaces that already render.
- [ ] **Step 8: Confirm the 留桩 fall-throughs are byte-for-byte intact (preservation d).** Re-read lines 208–236 (`doCapture`: `out.kind==='error'`→set error+return; `ok|disabled`→`advance()`), lines 268–280 (LED `.then(setLedOk).catch(()=>setLedOk(false))`), and lines 239–256 (initial `move_index:-1` best-effort capture with `.catch(()=>undefined)`). **No edits to any of these** — the reskin touched only `sx`/color. Verify via `git diff` that no line inside `doCapture`/the LED effect/`advance` changed.
- [ ] **Step 9: No raw-hex leak check.** `grep -nE "#ff3b30|#34c759|#2f6fff|#ff9500|#1a1a1a|#0f0f0f|rgba\(255,255,255|IBM Plex Mono" katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` returns nothing except the two physical-stone swatches `#1a1a1a`/`#e8e4df` on line 109 and the on-scrim `#fff` on line ~522 (allowed). Cross-check screens ②③④ against `baipu-flow.html` (下一手点灯 red/green, 拍照中 barrier, 提子移除 blue banner).
- [ ] **Step 10: Run the verification gates (Gate K) + no-hardware runtime drive.** `cd /Users/fan/Repositories/katrain-kiosk-ui-redesign/katrain/web/ui && npm run build:kiosk-2d` (chains `verify:kiosk-2d`) + `npm run lint` + `npx vitest run src/api/baipuApi.test.ts`. Then the **required runtime drive**: `python -m katrain --ui web --force-build`, open `/kiosk/baipu` at 1024×600, pick a 19-路 kifu → 开始摆谱, and confirm on real hardware-absent boot: (i) the LED health dot renders muted/gray then red per LedAPI outcome (unchanged fall-through), (ii) 确认落子 with capture endpoint 404 → `{kind:'disabled'}` → placement **advances** (no blocking error), (iii) stepping to the last move reaches `phase==='done'` with `baipu-done-back` visible. Compare styling to `baipu-flow.html` screens ②③④.
- [ ] **Step 11: Commit.** `git add katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx && git commit -m "reskin(kiosk): 摆谱 session page → slate + LED_HEX (B7.2)"`.

---

## Phase C — Research Down-Port

> Heaviest work — a **new build**, not a reskin. Re-implement galaxy's research components UNDER `kiosk/` (galaxy is import-forbidden); reuse shared `Board.tsx`/`LiveBoard`/`useResearchSession` **as-is**. Use **Gate R** (lint first). Artifacts `research-flow.html`, `research-states.html` · spec `design.md §5.3`.

---

**C1 · 研究 (Research)** — down-port L1 edit → L2a analyzing → L2b report; C1.8 retargets 棋谱「在研究中打开」post-C

---

### Task C1.1: Down-port `ResearchToolbar` to kiosk (12-cell tool grid, no cloud-save)

**Files:**
- Create `katrain/web/ui/src/kiosk/components/research/ResearchToolbar.tsx` (near-verbatim from `src/galaxy/components/research/ResearchToolbar.tsx` L1–358, READ-ONLY blueprint)

**Interfaces:**
- Produces: `export type PlaceMode = 'alternate'|'black'|'white'|null`; `export type EditMode = 'place'|'move'|'delete'|null`; `export default ResearchToolbar` with props = galaxy's `ResearchToolbarProps` **minus `onSaveToCloud`** (i.e. keep `onOpenFromCloud`).
- Consumes: shared `useTranslation` from `../../../hooks/useTranslation`.

- [ ] **Step 1: Copy the galaxy file verbatim, fix the import depth.** New file lives at `kiosk/components/research/` (same 3-deep nesting as galaxy `galaxy/components/research/`), so the `useTranslation` import stays `'../../../hooks/useTranslation'` (shared — unchanged). Confirm the 12 MUI icon imports (`FormatListNumberedIcon`, `PanToolAltIcon`, `OpenWithIcon`, `DeleteForeverIcon`, `TipsAndUpdatesIcon`, `MapIcon`, `LayersClearIcon`, `FolderOpenIcon`, `SaveIcon`, `UploadFileIcon`, `CloudDownloadIcon`, `ContentCopyIcon`) are kept; **delete the `CloudUploadIcon` import** (L16).
- [ ] **Step 2: Keep the 12-cell grid, drop the "保存到棋谱库" menu item.** Preserve both `<Box display:grid repeat(4,1fr)>` rows (Row 1 = 手数/停一手/移动/删除/摆黑/摆白/交替/清空; Row 2 = 建议/领地/打开/保存 — 12 cells total, matching artifact `research-flow.html` `.tgrid`). In the Save `<Menu>` (galaxy L273–292) delete the middle `<MenuItem>` that calls `onSaveToCloud` (the `CloudUploadIcon` / `研究:save_to_library` item). Keep 保存 SGF (`onSave`) and 复制 SGF (`onCopyToClipboard`). Leave the Open `<Menu>` intact (打开本地 SGF + 从棋谱库导入 both kept).
- [ ] **Step 3: Remove `onSaveToCloud` from the props interface + destructure.** Delete `onSaveToCloud?: () => void;` from `ResearchToolbarProps` (galaxy L43) and from the destructured params (galaxy L134). Nothing else references it.
- [ ] **Step 4: Reskin `ToolButton` + `.tool.on` states to slate tokens (match `research-flow.html` `.tool`/`.tool.on` and `research-states.html` states A/B).** Component = the inline `ToolButton` (galaxy L309–358). Replace hardcoded hovers/actives with `kiosk/theme.ts` tokens: inactive bg `theme.palette.background.paper` → active jade uses `primary.dark` bg + `primary.main` icon/label (`--jade-d`/`--jade` in artifact); destructive active uses `error.main` (`#e2685c`); borders `divider`. Keep the `blink` keyframes (loading state). States to preserve: `active`, `disabled` (建议/领地 gated by `isAnalyzing`), `loading` (建议 pending pulse), `isDestructive` (删除 red — artifact state **B** `research-states.html`). Custom `BlackStoneIcon`/`WhiteStoneIcon`/`AlternateIcon` (galaxy L51–115) carry over unchanged (match `.dotb`/`.dotw` in artifact). **No emoji** — all-SVG already.
- [ ] **Step 5: Run the verification gates (Gate R).** From `/Users/fan/Repositories/katrain-kiosk-ui-redesign/katrain/web/ui`, run `npm run lint` **first** (proves the new `kiosk/**` file imported nothing from `galaxy/**` — eslint `no-restricted-imports`), then `npm run build:kiosk-2d` (chains `verify:kiosk-2d`), then `npm run build` (full/galaxy stays green — Gate S). Also `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" src/kiosk/components/research/ResearchToolbar.tsx` returns nothing (Gate E).
- [ ] **Step 6: Commit.** `git commit -m "feat(kiosk-research): down-port ResearchToolbar (12-cell, drop cloud-save, slate reskin)"` (append the Co-Authored-By trailer).

---

### Task C1.2: Down-port `useResearchBoard` L1 board-state hook to kiosk

**Files:**
- Create `katrain/web/ui/src/kiosk/hooks/useResearchBoard.ts` (near-verbatim from `src/galaxy/hooks/useResearchBoard.ts` L1–353, READ-ONLY blueprint)

**Interfaces:**
- Produces: `export function useResearchBoard(): UseResearchBoardReturn`; `export interface ResearchBoardState`; `export interface UseResearchBoardReturn` (identical shape to galaxy).
- Consumes: `PlaceMode`, `EditMode` from `../components/research/ResearchToolbar` (C1.1 — kiosk copy); shared `movesToSGF`/`sgfToMoves`/`SGFMetadata`/`SerializedSGF` from `../../utils/sgfSerializer`.

- [ ] **Step 1: Copy galaxy hook verbatim; re-point the type import.** New file is at `kiosk/hooks/` (2-deep). Change galaxy's `import type { PlaceMode, EditMode } from '../components/research/ResearchToolbar'` (galaxy L8) → **kiosk** copy `'../components/research/ResearchToolbar'` (resolves to `kiosk/components/research/ResearchToolbar` — the C1.1 file). Keep the **shared** serializer import but fix depth: galaxy uses `'../../utils/sgfSerializer'` from `galaxy/hooks/`; from `kiosk/hooks/` it is also `'../../utils/sgfSerializer'` (both 2-deep off `src/`) — verify it resolves to `src/utils/sgfSerializer` (shared, consume AS-IS).
- [ ] **Step 2: Board size is 19-only — clamp after `loadFromSGF`.** Confirm `const [boardSize, setBoardSize] = useState(19)` (galaxy L74) stays. **Remove the `setBoardSize(metadata.boardSize)` call in the kiosk `loadFromSGF` (galaxy L213)** so an imported SGF can never switch the board off 19 — after **any** `loadFromSGF`, `boardSize` is force-held at 19. When a **non-19** SGF is imported, the page (C1.6) shows a toast `仅支持 19 路` and the board stays clamped to 19. **Komi / handicap / rules from the SGF are still honored** — only the size is clamped. (Expose a `lastLoadedSize`/`lastLoadClamped` signal from the hook so C1.6 knows when to toast.)
- [ ] **Step 3: Leave all board logic verbatim** (the one exception is the Step 2 `setBoardSize` clamp — `loadFromSGF` is otherwise unchanged). `handleIntersectionClick` (place/move/delete modes), `handlePass`, `handleClear`, `handleMoveChange`, `serializeToSGF`, `loadFromSGF`, `openLocalSGF`, `saveLocalSGF`, `copyToClipboard`, `getSnapshot`/`restoreSnapshot`, `handicapCount`, `nextColor` — no other changes (this is a pure client-side hook, no reskin surface).
- [ ] **Step 4: Run the verification gates (Gate R).** `cd katrain/web/ui` → `npm run lint` first (import-boundary), then `npm run build:kiosk-2d`, then `npm run build`. Add a smoke unit test file OR fold coverage into C1.7 (this hook is exercised transitively by the page test); at minimum `npx tsc -b` clean via the builds.
- [ ] **Step 5: Commit.** `git commit -m "feat(kiosk-research): down-port useResearchBoard L1 hook (kiosk toolbar types, board 19)"`.

---

### Task C1.3: Down-port `ResearchSetupPanel` (L1 rail, refit 500→340, drop board-size picker)

**Files:**
- Create `katrain/web/ui/src/kiosk/components/research/ResearchSetupPanel.tsx` (from `src/galaxy/components/research/ResearchSetupPanel.tsx` L1–241, READ-ONLY blueprint)

**Interfaces:**
- Produces: `export default ResearchSetupPanel`, props = galaxy `ResearchSetupPanelProps` **minus `boardSize`, `onBoardSizeChange`, `onSaveToCloud`**.
- Consumes: kiosk `ResearchToolbar` + `PlaceMode`/`EditMode` (C1.1); shared `useTranslation`.

- [ ] **Step 1: Copy verbatim; re-point `ResearchToolbar` import to the kiosk copy.** Galaxy L3 `import ResearchToolbar, { type PlaceMode, type EditMode } from './ResearchToolbar'` — resolves to the sibling kiosk file automatically (same dir). `useTranslation` stays `'../../../hooks/useTranslation'` (shared).
- [ ] **Step 2: Drop the board-size `Select` and its props.** Remove the 9×9/13×13/19×19 `FormControl` (galaxy L133–144). Remove `boardSize` + `onBoardSizeChange` from `ResearchSetupPanelProps` (galaxy L11–12) and the destructure. Keep the Komi `TextField`, Rules `Select`, Handicap `Select` in a `1fr 1fr` grid (now 3 controls) — matches `research-flow.html` ① where board is a read-only `19 路` fact but komi/rules/handicap stay editable per the down-port brief.
- [ ] **Step 3: Drop `onSaveToCloud`.** Remove from props/destructure and from the `<ResearchToolbar>` prop pass-through (galaxy L213). Keep `onOpenFromCloud`.
- [ ] **Step 4: Refit rail width 500→340 + slate reskin (match `research-flow.html` `.rrail` = 340px).** Component root `<Box>` (galaxy L84): `width: 500` → `width: 340`; `bgcolor: 'background.paper'` (`#18211f`), `borderLeft` → `1px solid`, `borderColor: 'divider'`. Section labels use `text.secondary`; player-dot swatches keep black/white.
- [ ] **Step 5: Reskin the 开始研究 CTA to jade + add the "500 visits/手" subtitle (artifact `.cta`).** The pinned-bottom `<Button>` (galaxy L221–237): `bgcolor: 'primary.main'` (jade `#58b57a`), dark ink label color `#0d1a13`, hover `primary.dark`. Add a caption line under the label reading `全局扫描 · 500 visits/手` (per artifact ① `.cta small`) via a stacked `<Box>` label; keep `ScienceIcon` startIcon. State to preserve: button always enabled in L1 (parent gates by wiring, not disabled prop).
- [ ] **Step 6: Run the verification gates (Gate R + runtime overflow check).** `npm run lint` first, then `npm run build:kiosk-2d`, then `npm run build`. Emoji grep on the new file returns nothing. **Runtime:** at 1024×600, verify the **340px L1 setup rail + board** shows no overflow/clip (no horizontal scroll, board not cropped) against `research-flow.html` ①.
- [ ] **Step 7: Commit.** `git commit -m "feat(kiosk-research): down-port ResearchSetupPanel (340px rail, no size picker, jade CTA)"`.

---

### Task C1.4: Down-port `ResearchAnalysisPanel` (L2b report rail, refit widths + trend SVG viewBox)

**Files:**
- Create `katrain/web/ui/src/kiosk/components/research/ResearchAnalysisPanel.tsx` (from `src/galaxy/components/research/ResearchAnalysisPanel.tsx` L1–877, READ-ONLY blueprint — largest file)

**Interfaces:**
- Produces: `export default ResearchAnalysisPanel`, props = galaxy `ResearchAnalysisPanelProps` **minus `onSaveToCloud`** (keeps `onOpenFromCloud`, `analysisMoves`, `history`, `playerToMove`, `children`).
- Consumes: kiosk `ResearchToolbar` (C1.1); shared `useTranslation`.

- [ ] **Step 1: Copy verbatim; re-point `ResearchToolbar` import; drop `onSaveToCloud`.** Sibling import auto-resolves to kiosk copy. Remove `onSaveToCloud` from props/destructure and from the `<ResearchToolbar>` pass-through (galaxy L549). Keep the classification constants (`BRILLIANT_THRESHOLD`, `MISTAKE_THRESHOLD`, `QUESTIONABLE_THRESHOLD`), `goodMoves`/`badMoves` memo, `displayMoves` memo, the sound `useEffect`s, and the auto-play `useEffect` — all unchanged (pure logic).
- [ ] **Step 2: Refit rail width 500→404 (report is the wide rail `.srail.wide` in `research-flow.html`).** Root `<Box>` (galaxy L413): `width: 500` → `width: 404`; `bgcolor: 'background.paper'`, `borderColor: 'divider'`.
- [ ] **Step 3: Refit the hard-coded 420×140 trend SVG to the narrow rail.** In `renderTrendChart` (galaxy L288–395) change `width = 420; height = 140; leftPad = 42; rightPad = 42; topPad = 12; bottomPad = 12` → `width = 300; height = 78; leftPad = 24; rightPad = 10; topPad = 6; bottomPad = 6` and drop the axis `fontSize="11"` → `"8"` (target `viewBox="0 0 300 78"` matches artifact `.trend svg`). In `handleChartClick` (galaxy L397–410) change the mirrored `svgWidth = 420; leftPad = 42; rightPad = 42` to the same `300/24/10` so click→move mapping stays correct.
- [ ] **Step 4: Reskin winrate bar + AI table + trend + nav to slate tokens (match `research-flow.html` ③ `.winbar`/`.aitbl`/`.trend`/`.anav`).** Named surfaces to restyle (no logic change):
  - Winrate `<LinearProgress>` (galaxy L518–527): replace the solid-black bar with the two-segment black/white bar per `.winbar .bar` (`.bk` dark gradient + `.wt` warm gradient); the lead-目 text uses `primary.main` (jade), matching artifact `.lead2`.
  - AI-recommendation table rows (galaxy L586–695): the **actual-move** highlight row (galaxy `bgcolor:'rgba(76,175,80,0.15)'` + `success.main` border) → **amber** `theme.palette.warning.main` (`#e0a24a`, the single amber token) bg/border/text per artifact `.aitbl tr.actual`. Rank chip `.rk` uses `primary.dark`/`primary.main`.
  - Trend tabs (galaxy L702–716) → jade-on chips per `.trend .th .tb.on`; 妙手/问题手 tags use `primary.main`/`error.main` (artifact `.tg.good`/`.tg.bad`).
  - Bottom nav bar (galaxy L816–873): `bgcolor:'#1a1a1a'` → `--raise2` (`#1d2725`); play `<IconButton>` stays jade (`primary.main`). Replace `fontFamily:'"IBM Plex Mono", monospace'` occurrences with `fontVariantNumeric:'tabular-nums'` on the sans stack (kiosk ships no IBM Plex Mono). MUI nav icons (`KeyboardDoubleArrowLeft/Right`, `ChevronLeft/Right`, `PlayArrow`, `Pause`) already used — **no glyphs, no emoji**.
- [ ] **Step 5: Reskin the 走势图 hardcoded greens/oranges inside the SVG + tab bodies.** Replace `stroke="#4caf50"` / `rgba(76,175,80,*)` fills with `theme.palette.primary.main` / jade rgba; `#ff9800` lead text and `#f44336` mistake text → `warning.main` / `error.main`. (Read the token values from `kiosk/theme.ts` via `useTheme()` where an inline SVG can't take an sx token.)
- [ ] **Step 6: Run the verification gates (Gate R + runtime overflow check).** `npm run lint` first, then `npm run build:kiosk-2d`, then `npm run build`. Emoji grep clean. **Runtime:** at 1024×600, verify the **404px report rail + board** shows no overflow/clip (no horizontal scroll; trend SVG + AI table fit the rail) against `research-flow.html` ③.
- [ ] **Step 7: Commit.** `git commit -m "feat(kiosk-research): down-port ResearchAnalysisPanel (404px rail, 300x78 trend, amber actual-row)"`.

---

### Task C1.5: Down-port `CloudSGFPanel` — public KifuAPI only (drop UserGamesAPI/auth/categories)

**Files:**
- Create `katrain/web/ui/src/kiosk/components/research/CloudSGFPanel.tsx` (from `src/galaxy/components/research/CloudSGFPanel.tsx` L1–304, READ-ONLY blueprint)

**Interfaces:**
- Produces: `export default GameLibraryModal` with props `{ open: boolean; onClose: () => void; onLoadGame: (sgf: string) => void }` (unchanged signature so C1.6 can drop it in).
- Consumes: shared `KifuAPI` from `../../../api/kifuApi`; shared `useTranslation`. **Must NOT import** `useAuth` (`context/AuthContext`) or `UserGamesAPI` (`galaxy/api/userGamesApi`).

- [ ] **Step 1: Copy the modal shell; strip the auth + user-games imports.** Delete galaxy imports L17–18 (`useAuth`, `UserGamesAPI`/`UserGameSummary`). Keep `KifuAPI` (fix depth: from `kiosk/components/research/` it's `'../../../api/kifuApi'` — shared). Delete the `Category` type (galaxy L22) and `CATEGORY_KEYS` array (galaxy L30–34).
- [ ] **Step 2: Collapse to a single public-kifu list.** Remove the left category sidebar `<Box width:160>` (galaxy L169–212) and the `token`/`category`/`handleCategoryChange` state. `fetchData` (galaxy L58–105) reduces to the `public_kifu` branch only: `KifuAPI.getAlbums({ q: searchQuery || undefined, page, page_size: PAGE_SIZE })` → map to the local `GameListItem` shape. `handleSelectGame` (galaxy L116–139) keeps only the `public_kifu` path: use `item.sgfContent` if present else `KifuAPI.getAlbum(Number(item.id))` → `onLoadGame(sgf); onClose()`.
- [ ] **Step 3: Reskin to the slate modal in `research-states.html` state E (`.modal`/`.krow`).** Component surfaces: `<Dialog>` paper → `background.paper` (`#18211f`), `divider` hairlines; search `<TextField>`; each result `<ListItemButton>` → `.krow` card (border `divider`, hover `#3a4d45`, selected `primary.main` border). Header title 从棋谱库打开 in the serif/brand stack; keep the black/white player dots. Footer keeps 取消 + the click-to-load behavior (galaxy loads on row click — retain; the artifact's footer "在研究中打开" is decorative, do not add a second confirm step).
- [ ] **Step 4: Keep the empty/loading states, drop the login-gate copy.** Preserve `<CircularProgress>` loading and the "暂无棋谱" empty state (galaxy L236–245); delete the `!token` "请先登录 / 登录后可查看个人棋谱" branches (no auth in kiosk).
- [ ] **Step 5: Run the verification gates (Gate R).** `npm run lint` **first** — this is the highest-risk import-boundary file (galaxy original pulls `galaxy/api/userGamesApi` + `context/AuthContext`); lint must confirm neither survived. Then `npm run build:kiosk-2d`, then `npm run build`. Emoji grep clean.
- [ ] **Step 6: Commit.** `git commit -m "feat(kiosk-research): down-port CloudSGFPanel simplified to public KifuAPI (no auth/user-games)"`.

---

### Task C1.6: Rewrite kiosk `ResearchPage` into the L1→L2a→L2b in-component state machine (+ failure/retry, immersive, local confirm)

**Files:**
- Modify (full rewrite) `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx` (current placeholder L1–242 — replace entirely)

**Interfaces:**
- Consumes: kiosk `useResearchBoard` (C1.2), `ResearchSetupPanel` (C1.3), `ResearchAnalysisPanel` (C1.4), `GameLibraryModal` (C1.5); shared `LiveBoard`+`AiMoveMarker` (`../../components/live/LiveBoard`), `Board` (`../../components/Board`), `useResearchSession` (`../../hooks/useResearchSession`), `API` (`../../api`), `KifuAPI` (`../../api/kifuApi`), `useTranslation`; kiosk `useImmersive` (`../context/ImmersiveContext`, Phase B).
- Produces: the `/kiosk/research` route component (default export). **All four shared board/session/api pieces are consumed AS-IS — zero prop additions** (driven via existing props: L2b `Board` gets `gameState`+`onMove`+`analysisToggles`; L1 `LiveBoard` gets `onIntersectionClick`).

- [ ] **Step 1: Port galaxy L1-mode state + quick-analysis wiring verbatim, minus cloud/auth/portrait.** Bring over from galaxy `ResearchPage.tsx`: `board = useResearchBoard()`, the L1 quick-analysis effect (galaxy L74–144, `API.quickAnalyze({ …, max_visits: 200 })`), `l1ShowHints`/`l1ShowTerritory`/`l1AiMarkers`/`l1Ownership`, the `analysisToggles` state + `toggleAnalysis`, `session = useResearchSession()`, and the L1 stone-sound effect. **Drop**: `useAuth`/`token`, `UserGamesAPI`, `handleSaveToCloud`, `savedGameIdRef`, the auto-save-to-cloud effect (galaxy L254–285), `useOrientation`/portrait branches, and 9/13 board sizing.
- [ ] **Step 2: Add the explicit view state + failure state.** Replace galaxy's `useGameNavigation` guard with local state:
```tsx
const [isAnalyzing, setIsAnalyzing] = useState(false);
const [analysisProgress, setAnalysisProgress] = useState<{ analyzed: number; total: number } | null>(null);
const [analysisError, setAnalysisError] = useState<string | null>(null);
const [confirmLeaveOpen, setConfirmLeaveOpen] = useState(false);
const analysisComplete = analysisProgress !== null && analysisProgress.total > 0 && analysisProgress.analyzed >= analysisProgress.total;
const frozenSnapshot = useRef<ResearchBoardState | null>(null);
const activeSessionIdRef = useRef<string | null>(null);
const pollFailRef = useRef(0);
// declared here so Steps 4/5/6 (which reference them) compile:
const analysisStartRef = useRef<{ time: number; analyzed: number } | null>(null);
const hintsEnabledRef = useRef(false);
const [etaSeconds, setEtaSeconds] = useState<number | null>(null);
const { setImmersive } = useImmersive();
```
- [ ] **Step 3: Drive immersive off `isAnalyzing` (hide Dock for L2a/L2b only) + destroy session on unmount.**
```tsx
useEffect(() => { setImmersive(isAnalyzing); return () => setImmersive(false); }, [isAnalyzing, setImmersive]);
// leak-guard: mirror galaxy ResearchPage.tsx:165-174 EXACTLY — keepalive DELETE keyed on
// session.sessionId (deps re-run so the current id is captured). Do NOT use a []-dep
// destroySession() cleanup: it captures sessionId===null and no-ops (Codex #9).
useEffect(() => {
  const cleanup = () => {
    if (session.sessionId) fetch(`/api/session/${session.sessionId}`, { method: 'DELETE', keepalive: true }).catch(() => {});
  };
  window.addEventListener('beforeunload', cleanup);
  return () => { window.removeEventListener('beforeunload', cleanup); cleanup(); };
}, [session.sessionId]);
```
- [ ] **Step 4: Write `handleStartAnalysis` (freeze → serialize → createSession skipAnalysis → analysisScan 500), wrapped for failure.**
```tsx
const handleStartAnalysis = useCallback(async () => {
  frozenSnapshot.current = board.getSnapshot();
  const { sgf } = board.serializeToSGF();
  const sgfToLoad = board.moves.length > 0 ? sgf : undefined;
  const newSessionId = await session.createSession(sgfToLoad, { skipAnalysis: true, initialMove: board.currentMove });
  if (!newSessionId) { setAnalysisError(t('research:session_failed', '无法创建研究会话，请重试')); setIsAnalyzing(true); return; }
  activeSessionIdRef.current = newSessionId;
  setAnalysisProgress(null); setEtaSeconds(null); setAnalysisError(null);
  analysisStartRef.current = null; hintsEnabledRef.current = false; pollFailRef.current = 0;
  setIsAnalyzing(true);
  try { await API.analysisScan(newSessionId, 500); }
  catch { setAnalysisError(t('research:scan_failed', '启动分析失败，请重试')); }
}, [board, session, t]);
```
- [ ] **Step 5: Port the progress-poll effect and add failure detection (state D).** Keep galaxy's poll + ETA math (galaxy L202–237); guard on `!analysisError`; count consecutive poll failures and trip the error after 5:
```tsx
useEffect(() => {
  if (!isAnalyzing || analysisComplete || analysisError) return;
  const sid = activeSessionIdRef.current; if (!sid) return;
  const interval = setInterval(async () => {
    try {
      const progress = await API.analysisProgress(sid);
      pollFailRef.current = 0;
      if (activeSessionIdRef.current === sid) { setAnalysisProgress({ analyzed: progress.analyzed, total: progress.total }); /* …ETA calc verbatim… */ }
    } catch {
      pollFailRef.current += 1;
      if (pollFailRef.current >= 5) setAnalysisError(t('research:engine_unresponsive', '引擎无响应，已保留已完成结果'));
    }
  }, 1000);
  return () => clearInterval(interval);
}, [isAnalyzing, analysisComplete, analysisError]); // eslint-disable-line react-hooks/exhaustive-deps
```
- [ ] **Step 6: Write `handleRetryAnalysis` + `handleReturnToEdit`.**
```tsx
const handleRetryAnalysis = useCallback(async () => {
  const sid = activeSessionIdRef.current;
  if (!sid) { await handleReturnToEdit(); return; }
  setAnalysisError(null); pollFailRef.current = 0; analysisStartRef.current = null;
  try { await API.analysisScan(sid, 500); }
  catch { setAnalysisError(t('research:scan_failed', '启动分析失败，请重试')); }
}, [t]); // eslint-disable-line react-hooks/exhaustive-deps

const handleReturnToEdit = useCallback(async () => {   // galaxy L360-379 minus savedGameIdRef
  activeSessionIdRef.current = null;
  await session.destroySession();
  if (frozenSnapshot.current) { board.restoreSnapshot(frozenSnapshot.current); frozenSnapshot.current = null; }
  setIsAnalyzing(false); setAnalysisProgress(null); setEtaSeconds(null); setAnalysisError(null);
  analysisStartRef.current = null; hintsEnabledRef.current = false;
  setAnalysisToggles(prev => ({ ...prev, hints: false, ownership: false, policy: false }));
}, [session, board]);
```
Keep galaxy's `handleL2MoveChange` (L396–406) and the analysis-complete "navigate + enable hints" effect (galaxy L240–252) verbatim. **Failure/retry (state D) re-calls `analysisScan` on the SAME live session** — `_do_analysis_scan` (`interface.py:798-827`) only queues `not node.analysis_exists`, so it resumes incrementally. **Do NOT `destroySession` on failure** (`analysis_exists` is in-memory; destroying restarts the scan from 0). Only `handleReturnToEdit` (返回编辑) destroys the session.
- [ ] **Step 7: Render precedence — four views.** Replace galaxy's two `if` blocks with:
```tsx
if (isAnalyzing && analysisError)                                return <FailureView … onRetry={handleRetryAnalysis} onBack={handleReturnToEdit} />;   // artifact research-states.html state D
if (isAnalyzing && analysisComplete && session.gameState)        return <ReportView … />;                                                              // research-flow.html ③
if (isAnalyzing)                                                 return <AnalyzingView … onCancel={handleReturnToEdit} onBack={() => setConfirmLeaveOpen(true)} />; // ②
return <EditView … />;                                                                                                                                 // ①
```
Implement each as an inline block (not new files):
  - **EditView** — `LiveBoard` (editable: `onIntersectionClick={board.handleIntersectionClick}`, `aiMarkers`/`ownership` from L1 quick-analysis) + a slim bottom move-nav bar that **preserves `data-testid="move-navigation"`** (constraint #4) with MUI icons (`KeyboardDoubleArrowLeft`/`ChevronLeft`/`ChevronRight`/`KeyboardDoubleArrowRight`) replacing the placeholder's `⏮◀▶⏭` glyphs, + `<ResearchSetupPanel … onStartAnalysis={handleStartAnalysis} />`. Dock stays visible (not immersive).
  - **AnalyzingView** — immersive top bar (back → `setConfirmLeaveOpen(true)`), the jade orb/spinner, progress bar, `已分析手数 / 进度 / 预计剩余` stats, inline `取消分析，回到编辑` → `handleReturnToEdit` (artifact ②).
  - **ReportView** — immersive top bar (返回编辑 → `handleReturnToEdit`), shared `<Board gameState={gs} onMove={session.onMove} analysisToggles={analysisToggles} />` **AS-IS**, + `<ResearchAnalysisPanel … />` (all props from galaxy L457–496 **minus `onSaveToCloud`**).
  - **FailureView** — red error icon, 分析失败 copy, 重试分析 (`onRetry`) + 返回编辑 (`onBack`) (artifact state D).
- [ ] **Step 8: Local confirm dialog (replaces `useGameNavigation`).** Add a MUI `<Dialog open={confirmLeaveOpen}>` with 取消分析？ / 继续分析 / 取消并离开; 取消并离开 → `setConfirmLeaveOpen(false); handleReturnToEdit()`. Render it alongside every view.
- [ ] **Step 9: `?kifu_id` deep-link — do NOT port `?analyze=1` verbatim (stale-state bug).** Add `useSearchParams` → `KifuAPI.getAlbum(Number(kifuId))` → `board.loadFromSGF(album.sgf_content, …)` so KifuPage can navigate `/kiosk/research?kifu_id=…`. **Do NOT re-use galaxy's `?analyze=1 → handleStartAnalysis()`** (`ResearchPage.tsx:187-199`): its effect dep `[searchParams]` captures `handleStartAnalysis` from the empty-board render and `serializeToSGF` reads the stale `moves` state → `createSession(undefined,…)` (deterministic, not timing). Instead either **(a) drop the auto-start** (open into the editor), OR **(b)** add a `startAnalysisFromSgf(sgf, initialMove)` path that serializes the **just-fetched `album.sgf_content`** and passes it directly into `createSession(sgf, { skipAnalysis:true, initialMove })` — never the stale board. If a **non-19** album loads, fire the `仅支持 19 路` toast (C1.2 clamp). C1.7's deep-link test asserts `createSession` receives the album SGF, not `undefined`.
- [ ] **Step 10: De-emoji + de-glyph sweep.** Replace all `⏮◀▶⏭` (present in the current placeholder L84–107) with the MUI icons above; confirm no `🎉/⚔️`-style celebration emoji introduced (use `EmojiEvents`/`Science` SVG if any celebratory affordance is added).
- [ ] **Step 11: Run the verification gates (Gate R + Gate E + Runtime).** `cd katrain/web/ui`; `npm run lint` first; `npm run build:kiosk-2d`; `npm run build`; `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" src/kiosk/pages/ResearchPage.tsx` empty. **C1.6's own gate is build + lint only** — the `ResearchPage.test.tsx` vitest suite is REWRITTEN in **C1.7** and lands in the **same commit / immediately after** (C1.6 cannot pass a vitest gate against a test it has not written yet). Runtime: `python -m katrain --ui web --force-build`, drive `/kiosk/research` at 1024×600, verify ① edit → ② analyzing → ③ report matches `research-flow.html`, kill the analysis engine to confirm state D matches `research-states.html`, **and verify no overflow/clip at 1024×600 (340px L1 rail / 404px report rail + board)**.
- [ ] **Step 12: Commit.** `git commit -m "feat(kiosk-research): rewrite ResearchPage as L1→analyzing→report state machine with failure/retry + immersive"`.

---

### Task C1.7: Rewrite `ResearchPage.test.tsx` for the new state machine

**Files:**
- Modify (full rewrite) `katrain/web/ui/src/kiosk/__tests__/ResearchPage.test.tsx` (current L1–105 — every assertion breaks; replace entirely)

**Interfaces:**
- Consumes: the C1.6 page; mocks shared `useResearchSession` + `API` + kiosk `useImmersive`.

> **Sequencing:** C1.7 **lands atomically with C1.6** — same commit, or immediately after in the same PR. C1.6's gate is build+lint only; this rewritten test is what makes the vitest gate green, so it cannot lag behind.

- [ ] **Step 1: Replace the mocks.** Drop the `OrientationContext` mock (page no longer uses it). Mock `../context/ImmersiveContext` → `useImmersive: () => ({ immersive: false, setImmersive: vi.fn() })`. Mock `../../api` → `API` with `quickAnalyze: vi.fn().mockResolvedValue({ turnInfos: [{ moveInfos: [], ownership: null }] })`, `analysisScan: vi.fn().mockResolvedValue({})`, `analysisProgress: vi.fn()`. Keep the `useResearchSession` mock but let `createSession` resolve a real id and expose a settable `gameState`.
- [ ] **Step 2: Test L1 renders editable board + setup.** `renderPage()` (wrap in `<ThemeProvider theme={kioskTheme}><MemoryRouter>`); assert 对局信息 fields (`getByPlaceholderText('黑方')`/`'白方'`), the 编辑工具 grid (`getByText('交替')`, `'摆黑'`, `'删除'`), the 开始研究 CTA (`getByRole('button', { name: /开始研究/ })`), and `getByTestId('move-navigation')` (preserved). Assert **no** 棋盘大小 size picker is rendered (`queryByText('9×9')` is null).
- [ ] **Step 3: Test start → analyzing.** Stub `analysisProgress` to resolve `{ analyzed: 10, total: 100 }`; click 开始研究; `waitFor` the analyzing view (正在分析全局 / progress text) and assert `API.analysisScan` was called with `(expect.any(String), 500)`.
- [ ] **Step 4: Test complete → report.** Drive the session mock's `gameState` to a minimal `GameState` (history length ≥ 2, `analysis: { winrate, score }`) and `analysisProgress` → `{ analyzed: 100, total: 100 }`; assert the report renders the shared `Board` (query its container/`canvas`) + `ResearchAnalysisPanel` markers (AI 推荐 header, winrate %). 
- [ ] **Step 5: Test failure → retry, and return-to-edit restores L1.** Make `analysisProgress` reject 5× → assert 分析失败 view; click 重试分析 → assert `API.analysisScan` re-called. Separately, from the report/analyzing view click 返回编辑 → assert `session.destroySession` called and 开始研究 CTA is back (L1 restored).
- [ ] **Step 5b: Test the `?kifu_id` deep-link passes the album SGF (not `undefined`).** Render at `/kiosk/research?kifu_id=1&analyze=1`; mock `KifuAPI.getAlbum` → `{ sgf_content: '(;GM[1]FF[4]SZ[19];B[pd];W[dp])' }`; assert `session.createSession` is called with a first arg **containing the album SGF** (e.g. `expect.stringContaining('B[pd]')`), NOT `undefined` — proving the C1.6 Step 9 fix (serialize the fetched `album.sgf_content` directly). This guards against galaxy's stale-empty-board `createSession(undefined,…)` regression.
- [ ] **Step 6: Run the verification gates (Gate R).** `npm run lint` first; `npx vitest run src/kiosk/__tests__/ResearchPage.test.tsx` green; then `npm run build:kiosk-2d` + `npm run build` (land together with C1.6).
- [ ] **Step 7: Commit.** `git commit -m "test(kiosk-research): rewrite ResearchPage.test for edit/analyzing/report/failure machine"`.

---

### Task C1.8: POST-C — retarget KifuPage "在研究中打开" to the new research entry + remove the stale session route

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` — `handleOpenInResearch` L109–131, `useResearchSession` import L12, navigate L121
- Modify `katrain/web/ui/src/kiosk/KioskApp.tsx` — research routes L74–75
- Modify `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx` — the navigate assertion

**Interfaces:**
- Consumes: the C1.6 `/kiosk/research?kifu_id=…` deep-link (Step 9). Produces: KifuPage navigates straight to the report entry; the dead `research/session/:sessionId` → `GamePage` route is removed.

- [ ] **Step 1: Retarget the navigate to the kifu deep-link.** In `handleOpenInResearch` (KifuPage L109–131) replace the `createSession(...)` + `navigate('/kiosk/research/session/${sessionId}')` (L119–121) with `navigate('/kiosk/research?kifu_id=' + selectedId + '&analyze=1')` (the new page loads the SGF via `KifuAPI.getAlbum` and auto-starts the scan). Keep the `opening`/`openError` UX guards and the `Snackbar`.
- [ ] **Step 2: Drop the now-unused research-session plumbing from KifuPage.** Remove `import { useResearchSession }` (L12) and the `const { createSession } = useResearchSession()` (L25). Confirm `previewSgf`/`previewHandicap`/`initialMove` are no longer needed by the navigate (or keep `initialMove` only if you thread a `&move=` param — otherwise delete the `initialMove` computation L118).
- [ ] **Step 3: Remove the stale route.** In `KioskApp.tsx` delete `<Route path="research/session/:sessionId" … ><GamePage /></…>` (L75); nothing navigates there after Step 1. If `GamePage` becomes import-unused, drop its import too (verify no other route uses it — L52–55 still do, so keep the import).
- [ ] **Step 4: Update the KifuPage test.** In `KifuPage.test.tsx` change the "在研究中打开" assertion from the old `/kiosk/research/session/...` expectation to `expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('/kiosk/research?kifu_id='))`; drop any `createSession` mock expectation.
- [ ] **Step 5: Run the verification gates (Gate R).** `cd katrain/web/ui`; `npm run lint` first; `npx vitest run src/kiosk/__tests__/KifuPage.test.tsx`; `npm run build:kiosk-2d`; `npm run build`. Runtime: from `/kiosk/kifu`, pick a game → 在研究中打开 → lands on the research report for that kifu.
- [ ] **Step 6: Commit.** `git commit -m "feat(kiosk-research): retarget KifuPage 在研究中打开 to /kiosk/research?kifu_id and drop stale session route"`.

---

## Phase D — 死活 Physical 5-State Stub

> Consumes the B2 toggle seam + A4 `ledColors`. **Read the real `physicalTsumegoMachine` in the sibling worktree `/Users/fan/Repositories/katrain-kiosk-physical-tsumego` first** to lock the contract, then ship the stub behind an indirection file so the physical track swaps one line. Artifact `tsumego-states.html` · spec `design.md §5.2`.

---

**D1 · 死活物理** — stub hook + indirection seam + `PhysicalStatePanel` (5 states, MUI icons, LED/voice as no-op seams)

---

### Task D1.1: Physical-tsumego STUB hook + indirection seam

**Files:**
- Create `katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.stub.ts`
- Create `katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.ts` (indirection re-export)
- Create `katrain/web/ui/src/kiosk/__tests__/usePhysicalTsumego.stub.test.tsx`
- Consumes (dependency, must already exist): `katrain/web/ui/src/kiosk/constants/ledColors.ts` (A4) — `LedIntent`.

**Interfaces:**
- Produces: `PhysicalTsumegoPhase`, `PhysicalTsumegoState`, `UsePhysicalTsumego`, and the hook `usePhysicalTsumego(): UsePhysicalTsumego` (exact names from the shared-contract block). Task D1.2 (panel) and D1.3 (page) consume these via the indirection file `./usePhysicalTsumego`, never the `.stub` directly.
- Consumes: `LedIntent` from `../constants/ledColors`.

- [ ] **Step 1: Read the REAL hook FIRST and ADOPT its exact exported signature (adapter — real signature wins).** READ the sibling worktree files `/Users/fan/Repositories/katrain-kiosk-physical-tsumego/katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.ts` + `physicalTsumegoMachine.ts` (present + fully implemented). **The stub is an ADAPTER whose exported types/shape conform to the REAL hook — the real signature WINS over the invented `PhysicalTsumegoState`/`UsePhysicalTsumego` shown in Steps 2–3.** Where the real hook diverges (opts-driven `usePhysicalTsumego(opts: PhysicalTsumegoOptions)` + WS-fed; a 9th phase `'restoring'`; setup progress `stage/missing/extra/stageMatched/stageTotal`; removals via a machine command stream; `ledOk` + `onScreenMove` passthrough), **adopt the REAL names/shape** and update `PhysicalStatePanel` (D1.2) to match — so landing the real hook is a genuine drop-in swap of the indirection re-export (no consumer edits). Put this note atop `usePhysicalTsumego.stub.ts`:
  ```ts
  // STUB (Phase D). Side-effect-free ADAPTER conforming to the REAL physical-track hook's
  //   exported signature (katrain-kiosk-physical-tsumego/.../hooks/usePhysicalTsumego.ts).
  //   The REAL signature is AUTHORITATIVE — the types in this file mirror it; they are NOT an
  //   independent contract. Real-hook shape this stub conforms to:
  //     • signature: usePhysicalTsumego(opts: PhysicalTsumegoOptions) — opts-driven + WS-fed
  //     • phase enum includes a 9th phase 'restoring' (try-mode exit)
  //     • setup progress: stage/missing/extra/stageMatched/stageTotal
  //     • removals via a machine command stream; plus ledOk + onScreenMove passthrough
  //   Landing the real hook = re-point the indirection re-export at an adapter over it,
  //   keeping PhysicalStatePanel/TsumegoProblemPage untouched.
  ```
- [ ] **Step 2: Declare the contract types.** In `usePhysicalTsumego.stub.ts`:
  ```ts
  import { useCallback, useState } from 'react';
  import type { LedIntent } from '../constants/ledColors';

  export type PhysicalTsumegoPhase =
    'off'|'clearing'|'setup'|'ready'|'replying'|'removing'|'solved'|'clearing_next';

  export interface PhysicalTsumegoState {
    phase: PhysicalTsumegoPhase;
    setupProgress?: { matched: number; total: number };
    removalList: [number, number][];
    ledIntent: { intent: LedIntent | null; points: [number, number][] };
  }

  export interface UsePhysicalTsumego extends PhysicalTsumegoState {
    enabled: boolean;
    enable(): void;
    disable(): void;
    __devSetPhase?(p: PhysicalTsumegoPhase): void;
  }
  ```
- [ ] **Step 3: Deterministic per-phase derivation (drives dev + panel + tests), no IO.** Add a pure helper so `__devSetPhase` fully populates the state a phase implies (matches the 5 visual states A–E in `tsumego-states.html`):
  ```ts
  function deriveState(phase: PhysicalTsumegoPhase): PhysicalTsumegoState {
    switch (phase) {
      case 'setup':    // A 摆放黑棋 — black LED (红)
        return { phase, setupProgress: { matched: 2, total: 5 },
                 removalList: [], ledIntent: { intent: 'black', points: [[3,3],[15,15]] } };
      case 'ready':    // B 做题中 — no LED, move detection armed
        return { phase, removalList: [], ledIntent: { intent: null, points: [] } };
      case 'replying': // C 应手 — white LED (绿)
        return { phase, removalList: [], ledIntent: { intent: 'white', points: [[9,9]] } };
      case 'removing': // D 答错拿除 — remove LED (蓝) + removalList
        return { phase, removalList: [[9,9]], ledIntent: { intent: 'remove', points: [[9,9]] } };
      case 'solved':   // E 答对 — white double-blink (白)
        return { phase, removalList: [], ledIntent: { intent: 'hint', points: [] } };
      default:         // off / clearing / clearing_next — neutral
        return { phase, removalList: [], ledIntent: { intent: null, points: [] } };
    }
  }
  ```
- [ ] **Step 4: The stub hook — imperative, no `useEffect`, no network, no voice.** Confirm the body imports NOTHING from the `api` layer. **`api/ledApi.ts` DOES exist** (`src/api/ledApi.ts`, used by Baipu) — the real-hook adapter will reuse it, but this STUB must stay **side-effect-free** and must NOT import/call it. `enable()` advances to the **`'setup'`** phase (a visible state; `'clearing'` renders `null` in D1.2) so turning physical mode on immediately shows the panel:
  ```ts
  export function usePhysicalTsumego(): UsePhysicalTsumego {
    const [phase, setPhase] = useState<PhysicalTsumegoPhase>('off');
    const enable  = useCallback(() => setPhase('setup'), []);
    const disable = useCallback(() => setPhase('off'), []);
    const __devSetPhase = useCallback((p: PhysicalTsumegoPhase) => setPhase(p), []);
    return { ...deriveState(phase), enabled: phase !== 'off', enable, disable, __devSetPhase };
  }
  ```
- [ ] **Step 5: Indirection file — the ONE line the physical track later swaps.** Write `usePhysicalTsumego.ts`:
  ```ts
  // Indirection seam: the physical track swaps the target of these two re-exports
  // (to an adapter over the real hook) without touching any consumer. See the ⚠ note in .stub.
  export * from './usePhysicalTsumego.stub';
  export { usePhysicalTsumego } from './usePhysicalTsumego.stub';
  ```
- [ ] **Step 6: Stub unit test — cycle all phases + assert zero network.** In `usePhysicalTsumego.stub.test.tsx`, use `@testing-library/react`'s `renderHook`/`act`. Spy `const fetchSpy = vi.spyOn(globalThis, 'fetch')` before rendering. Drive `result.current.__devSetPhase!('setup'|'ready'|'replying'|'removing'|'solved')` inside `act`, asserting after each: `expect(result.current.phase).toBe(p)` and the derived shape (`setupProgress`, `removalList`, `ledIntent.intent`). After the full cycle assert `expect(fetchSpy).not.toHaveBeenCalled()`. Also assert `enable()` → `enabled===true && phase==='setup'` and `disable()` → `enabled===false && phase==='off'`. Import the hook from `../hooks/usePhysicalTsumego` (through the indirection, not `.stub`).
- [ ] **Run the verification gates (Gate K):** `cd /Users/fan/Repositories/katrain-kiosk-ui-redesign/katrain/web/ui && npm run lint && npx vitest run src/kiosk/__tests__/usePhysicalTsumego.stub.test.tsx && npm run build:kiosk-2d`. (Gate K only — stub touches kiosk-only `constants/ledColors.ts` + `hooks/`, no shared-territory edit, so `npm run build` full is not required.)
- [ ] **Commit:** `feat(kiosk): Phase D — physical-tsumego 8-phase STUB + indirection seam`

---

### Task D1.2: PhysicalStatePanel — 5 states, MUI icons + LED labels, no emoji

**Files:**
- Create `katrain/web/ui/src/kiosk/components/tsumego/PhysicalStatePanel.tsx`
- Create/append `katrain/web/ui/src/kiosk/__tests__/tsumego-components.test.tsx` (existing file, lines 1–40 read; append a `describe('PhysicalStatePanel')` block using the same `ThemeProvider theme={kioskTheme}` harness at its top).

**Interfaces:**
- Produces: `default` React component `PhysicalStatePanel`, props `{ state: UsePhysicalTsumego; onDismiss?(): void }`.
- Consumes: `UsePhysicalTsumego` from `../../hooks/usePhysicalTsumego`; `LED_LABEL`, `LED_HEX`, `LedIntent` from `../../constants/ledColors`; `kioskTheme` warning token via `theme.palette.warning.main`.

- [ ] **Step 1: Imports + prop type.** Header comment: "Read-only status panel for physical-board tsumego (Phase D stub-driven). NO emoji — SBC ships no emoji font; celebration uses the EmojiEvents trophy SVG." Import from `@mui/material`: `Box, Typography, Chip, IconButton`; from `@mui/icons-material`: `PanTool` (A 摆放), `TouchApp` (B 做题中 dual-input), `SwapCalls` or `Reply` (C 应手), `DeleteSweep` (D 拿除), `EmojiEvents` (E 答对 trophy — NOT 🎉), `Close` (dismiss). Import `LED_LABEL, LED_HEX, type LedIntent` from `../../constants/ledColors`, `type UsePhysicalTsumego` from `../../hooks/usePhysicalTsumego`.
- [ ] **Step 2: LED chip subcomponent.** A small inline `LedChip` that, given `intent: LedIntent`, renders a dot `sx={{ width:12, height:12, borderRadius:'50%', bgcolor: LED_HEX[intent] }}` + label `LED_LABEL[intent]` (红/绿/蓝/白). Assert it reads `LED_HEX`/`LED_LABEL` — no local hex. This is the hardware-留桩 advisory surface; keep it rendering even if `state.ledIntent.points` is empty.
- [ ] **Step 3: Phase→visual-state map (A–E) matching `tsumego-states.html`.** A `switch (state.phase)` returning `{ icon, titleZh, intent, testid }`; map `setup→A 摆放黑棋 (PanTool, intent 'black')`, `ready→B 做题中 (TouchApp, intent null — show "屏幕点击 + 实体落子" dual-input hint)`, `replying→C 应手 (Reply, intent 'white')`, `removing→D 答错拿除 (DeleteSweep, intent 'remove')`, `solved→E 答对 (EmojiEvents, intent 'hint')`. For `off|clearing|clearing_next` return `null` → component renders nothing. All titles Chinese only (per language rule).
- [ ] **Step 4: Render the panel.** A raised card `sx={{ bgcolor:'var(--raise2)', border:'1px solid', borderColor:'divider', borderRadius:2, p:1.5 }}` with `data-testid="physical-state-panel"` and `data-phase={state.phase}`. Row: state icon (color from intent's `LED_HEX` or `text.secondary` for null) + `titleZh` (`Typography variant="subtitle1"`). Amber accent (进行中) uses `theme.palette.warning.main` token ONLY — never a local hex. When `onDismiss` provided, render a `<IconButton onClick={onDismiss} data-testid="physical-state-dismiss"><Close/></IconButton>`.
- [ ] **Step 5: State-D removal list + voice-cue no-op slot.** When `phase==='removing'`, render each `state.removalList` coord as a `<Chip data-testid="removal-item">` labelled `"拿除 (r,c)"` in `LED_HEX.remove` (蓝). Leave an explicit empty element `{/* voice-cue slot: physical track wires speak('wrong_remove') here — stub is silent */}` so the real-hook swap has an anchor. No audio API call in the stub panel.
- [ ] **Step 6: State-E celebration — trophy + white double-blink, no emoji.** When `phase==='solved'`, wrap the `EmojiEvents` trophy in a `keyframes` double-blink (`opacity 1→0.2→1` twice, ~350ms each — mirror the LED double-flash cadence in the real machine's `celebrate()`), color `LED_HEX.hint` (`#ffffff`). Do NOT reuse SuccessOverlay's 🎉 path.
- [ ] **Step 7: Per-phase render test.** Append to `tsumego-components.test.tsx`: a tiny harness component that calls `usePhysicalTsumego()` and exposes `__devSetPhase` via a ref/button, wrapped in `<ThemeProvider theme={kioskTheme}>`. For each of setup/ready/replying/removing/solved: set the phase, then assert the panel shows the right icon (`getByTestId('...')` on `svg[data-testid]` from MUI icons, e.g. `PanToolIcon`, `EmojiEventsIcon`) AND the correct LED label text (`红`/absent/`绿`/`蓝`/`白`) via `screen.getByText`. Assert `removing` renders a `removal-item` chip. Assert `off`/`clearing` render nothing (`queryByTestId('physical-state-panel')` is null). Spy `globalThis.fetch` and assert `not.toHaveBeenCalled()` across the whole cycle (panel + stub stay network-silent).
- [ ] **Run the verification gates (Gate K + Gate E):** `cd .../web/ui && npm run lint && npx vitest run src/kiosk/__tests__/tsumego-components.test.tsx && npm run build:kiosk-2d`. Then the emoji gate scoped to Phase-D-owned files (the global whole-kiosk grep is blocked on Phase B's SuccessOverlay 🎉 removal + pre-existing debt in `TsumegoCategoriesPage.tsx`/`PlatformEngineSetupPage.tsx` — flag this): `grep -rP "[\x{2190}-\x{27BF}\x{2B00}-\x{2BFF}\x{1F000}-\x{1FAFF}\x{FE0F}]" src/kiosk/components/tsumego/PhysicalStatePanel.tsx src/kiosk/hooks/usePhysicalTsumego*.ts` must return nothing.
- [ ] **Commit:** `feat(kiosk): Phase D — PhysicalStatePanel 5-state render (MUI icons, LED labels, no emoji)`

---

### Task D1.3: Wire PhysicalStatePanel into TsumegoProblemPage behind `readPhysicalMode()`

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx` (imports lines 1–26; controls panel `<Box sx={{ flex: 1, … }}>` lines 269–378).
- Modify `katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx` (add physical-mode-on / physical-mode-off cases).
- Consumes: `readPhysicalMode` from `./tsumegoUnits` (Phase B adds `kiosk_tsumego_physical` key + `readPhysicalMode()` default FALSE / `writePhysicalMode(v)` — dependency; if Phase B not yet landed, this task blocks on it).

**Interfaces:**
- Consumes: `usePhysicalTsumego` (D1.1), `PhysicalStatePanel` (D1.2), `readPhysicalMode` (Phase B).
- Produces: no new exports; adds `data-testid="physical-state-panel"` surface into the page when physical mode is ON.

- [ ] **Step 1: Imports.** Add to the import block (after line 26): `import PhysicalStatePanel from '../components/tsumego/PhysicalStatePanel';`, `import { usePhysicalTsumego } from '../hooks/usePhysicalTsumego';`, and extend the existing `./tsumegoUnits` import (line 26) to `import { sequenceKey, readAutoAdvance, readPhysicalMode } from './tsumegoUnits';`.
- [ ] **Step 2: Call the hook unconditionally (rules of hooks); REUSE B2.5's `physicalMode` state.** After the `useVision()`/`useVisionSync` block (~line 70), add `const physical = usePhysicalTsumego();`. **Do NOT declare a new `physicalMode` state** — B2.5 already declared `const [physicalMode, setPhysicalMode] = useState(readPhysicalMode())` on this same page (single owner, driving the `PhysicalModeToggle`). **Reuse that state** here; if B2.5 has not landed, this task is blocked on it.
- [ ] **Step 3: Enable/disable the stub with the physical-mode lifecycle.** Add an effect near the existing per-problem reset effect (lines 179–183):
  ```ts
  useEffect(() => {
    if (!physicalMode) return;
    physical.enable();
    return () => physical.disable();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [physicalMode, problemId]);
  ```
  Comment: stub is side-effect-free, so enable/disable only advance the local phase; the real-hook adapter later drives vision/LED here.
- [ ] **Step 4: Mount the panel in the controls column (physical mode ON only).** Inside the controls `<Box sx={{ flex: 1, … }}>` (after the status-indicator Alerts block, ~line 293, before the timer Box), add: `{physicalMode && <Box sx={{ mb: 2 }}><PhysicalStatePanel state={physical} /></Box>}`. Default (physicalMode false → Phase B behavior) renders nothing — preserving every existing `data-testid` (`tsumego-board`, `timer`, `attempts`, `prev-problem`, `next-problem`) unchanged.
- [ ] **Step 5: Confirm dual-input coexistence (TR1) is untouched.** Verify no change to `TsumegoBoard`'s `onPlaceStone` (lines 252–255) and no `disabled` gating added — screen clicks keep working alongside the physical panel. The stub does not consume `placeStone`; the real-hook adapter will add the `onScreenMove` passthrough later. Add an inline comment at the panel mount noting this.
- [ ] **Step 6: Page test — on/off.** In `TsumegoProblemPage.test.tsx`, add two cases mocking `./tsumegoUnits`'s `readPhysicalMode`: (a) returns `true` → after render, `screen.getByTestId('physical-state-panel')` exists and `data-phase` starts at **`setup`** (from `enable()` → `setPhase('setup')`; `clearing`/`clearing_next` render `null`, D1.2); (b) returns `false` (default) → `screen.queryByTestId('physical-state-panel')` is null and existing assertions (board/timer testids) still pass. Do NOT mock the stub hook — let the real stub drive so the wiring is exercised end to end.
- [ ] **Run the verification gates (Gate K):** `cd .../web/ui && npm run lint && npx vitest run src/kiosk/__tests__/TsumegoProblemPage.test.tsx && npm run build:kiosk-2d`. (Page + hook + panel are all kiosk-only; `tsumegoUnits.ts`/`ledColors.ts`/`hooks/` are kiosk territory, not the shared list — Gate K suffices, no full `npm run build`.) Runtime: `python -m katrain --ui web --force-build`, drive `/kiosk/tsumego/problem/<id>` at 1024×600 with `kiosk_tsumego_physical='true'` in localStorage, dev-cycle phases via `physical.__devSetPhase` in console, and compare each state to `tsumego-states.html` (A 红 / B dual / C 绿 / D 蓝+list / E trophy white blink).
- [ ] **Commit:** `feat(kiosk): Phase D — mount PhysicalStatePanel in TsumegoProblemPage behind readPhysicalMode`

---

**Cross-phase flags for the assembler:**
1. **Sign-off dependency (real-hook swap is NOT drop-in):** the physical-track hook at `katrain-kiosk-physical-tsumego/.../hooks/usePhysicalTsumego.ts` is already built but exposes `usePhysicalTsumego(opts: PhysicalTsumegoOptions): PhysicalTsumegoState` with a 9-phase enum (adds `'restoring'`) and stage/missing/extra/stageMatched/stageTotal/ledOk/onScreenMove — divergent from this contract. Landing it requires an **adapter** at the indirection file, not a one-line re-export. Captured verbatim in the stub header (Task D1.1 Step 1).
2. **Global Gate E is blocked on sibling phases:** `grep` over all of `src/kiosk` currently hits `components/tsumego/SuccessOverlay.tsx` (🎉, line 119 — Phase B's reskin owns this), `pages/TsumegoCategoriesPage.tsx`, and `pages/PlatformEngineSetupPage.tsx`. Phase D's own files are emoji-clean; the whole-kiosk Gate E only turns green once those sibling files drop their emoji.
3. **Hard dependencies:** A4 `constants/ledColors.ts` (LedIntent/LED_HEX/LED_LABEL) and Phase B `tsumegoUnits.ts::readPhysicalMode` must land before D1.1 and D1.3 respectively.

---

## Appendix: design-phase record

The design track (direction selection, per-module visual specs, artifact index, decision log) lives in `design.md`, `HANDOFF.md`, and the pre-implementation activity log preserved at `plan-design-phase.md` (this file's former content). This `plan.md` supersedes that log as the execution plan.
