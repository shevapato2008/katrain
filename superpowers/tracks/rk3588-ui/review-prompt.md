# RK3588 Kiosk UI — Development Plan Review Request

> Please review the following design decisions and implementation plan for a kiosk UI variant of a Go/Baduk teaching application. Point out any architectural issues, missing considerations, questionable decisions, or improvements you'd suggest. Be specific and critical.

---

## Project Background

**KaTrain** is an open-source Go/Baduk playing and teaching application integrating with the KataGo AI engine. It currently has:
- A desktop GUI (Kivy-based)
- A web UI ("Galaxy" theme) — React 19 + TypeScript + MUI v7 + FastAPI backend

We are building a **kiosk UI variant** for RK3588-based smart Go board terminals — embedded devices with 7-10 inch touchscreens and a physical Go board with sensor input (image recognition / Hall effect sensors).

### Tech Stack (Fixed)

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend framework | React | 19.2 |
| UI library | MUI | v7.3 |
| Router | React Router | v6.30 |
| Build tool | Vite (rolldown-vite) | 7.2 |
| Language | TypeScript | 5.9 |
| Test | Vitest + Testing Library | 4.0 / 16.3 |
| Backend | FastAPI + Uvicorn | — |
| AI Engine | KataGo (HTTP API) | — |
| OS | Ubuntu on RK3588 | — |

---

## Part 1: Requirements Summary

### Hardware & Environment

- **Display**: 7-10 inch touchscreen, landscape-only (phase 1)
- **Input**: Physical board sensors for stone placement; touchscreen for UI controls
- **Screen board role**: Display AI suggestions overlaid on board, NOT primary move input (except tsumego module, which requires touch-to-place)
- **Kiosk mode**: Boot-to-app via Chromium `--kiosk` + systemd, no exit, auto-restart on crash
- **Auth**: Multi-user, login required on each boot
- **Network**: Local (backend on same device), fonts bundled locally (no CDN dependency)

### Functional Scope

Full-featured compact edition — **all existing Galaxy modules retained**, touch-adapted:

| Module | Description |
|--------|-------------|
| Human vs AI | Free play + ranked play (auto-matched difficulty) |
| Human vs Human | Local game (physical board) + online lobby |
| Tsumego | Problem library, touch-to-solve on screen |
| Research | Board analysis with AI, place stones + navigate variations |
| Kifu Library | Saved game records, replay with analysis |
| Live | Spectate ongoing matches |
| External Platforms | Reserved entry points for 99Go, FoxGo, Tencent Go, Sina Go |
| Settings | Language selector only |

### Implementation Strategy

Frontend-first: build all kiosk pages with mock data, validate visual design, then integrate backend.

---

## Part 2: Architecture Decisions

### Decision 1: Code Organization — Parallel Theme Directory

```
katrain/web/ui/src/
├── shared/              # Extracted shared layer (phase 2)
│   ├── api/             # REST + WebSocket communication
│   ├── components/      # Board.tsx, ScoreGraph.tsx, PlayerCard.tsx
│   ├── hooks/           # useGameSession, useResearchBoard, etc.
│   ├── types/           # game.ts, analysis.ts, kifu.ts
│   └── utils/           # sgfSerializer, rankUtils, etc.
├── galaxy/              # Existing web UI (unchanged in phase 1)
│   ├── components/
│   ├── pages/           # 17 page components
│   ├── context/         # AuthContext, SettingsContext, GameNavigationContext
│   └── hooks/
├── kiosk/               # NEW: Terminal UI
│   ├── components/
│   │   ├── layout/      # StatusBar, BottomTabBar, KioskLayout
│   │   ├── common/      # ModeCard, OptionChips
│   │   └── game/        # MockBoard, GameControlPanel
│   ├── pages/           # AiPlayPage, AiSetupPage, GamePage, etc.
│   ├── styles/          # fonts.css
│   ├── __tests__/       # All kiosk tests
│   ├── theme.ts
│   └── KioskApp.tsx
└── main.tsx             # Entry point
```

**Route dispatch** (in AppRouter.tsx):
```
/galaxy/*  → GalaxyApp (existing web UI, zenTheme)
/kiosk/*   → KioskApp (terminal UI, kioskTheme)
/*         → ZenModeApp (legacy compatibility)
```

**Current AppRouter.tsx** (before modification):
```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import ZenModeApp from './ZenModeApp';
import GalaxyApp from './GalaxyApp';

const AppRouter = () => (
  <ThemeProvider theme={zenTheme}>
    <CssBaseline />
    <BrowserRouter>
      <Routes>
        <Route path="/galaxy/*" element={<GalaxyApp />} />
        <Route path="/*" element={<ZenModeApp />} />
      </Routes>
    </BrowserRouter>
  </ThemeProvider>
);
```

**Proposed change**: Add `<Route path="/kiosk/*" element={<KioskApp />} />` and conditionally switch `ThemeProvider` theme based on URL prefix.

**Review questions:**
1. Is conditional `ThemeProvider` based on `window.location.pathname` the right approach, or should we nest `ThemeProvider` inside each app component?
2. Single Vite build for both galaxy + kiosk — is tree-shaking sufficient, or should we consider code-splitting/lazy loading?
3. The `shared/` layer extraction is deferred to phase 2. In phase 1, kiosk will create its own mock components. Is this the right sequencing?

### Decision 2: Visual Design — "Ink Stone" Theme

Dark theme inspired by Go aesthetics (ink, stone, wood):

```
--ink-black:      #1a1714     (background — warmer than Galaxy's #0f0f0f)
--stone-white:    #e8e4dc     (primary text — warm ivory)
--wood-amber:     #8b7355     (board wood color)
--jade-deep:      #2d5a3d     (dark accent)
--jade-glow:      #5cb57a     (primary / AI suggestion highlight)
--ember:          #c45d3e     (error / bad move)
--mist:           #6b6560     (secondary text)
--parchment:      #f5f0e8     (card backgrounds, sparingly)
```

Typography: Noto Serif SC (headings), Noto Sans SC (body), JetBrains Mono (data/numbers). All CJK-capable, locally bundled.

**Review questions:**
1. Color contrast — does `#e8e4dc` on `#1a1714` meet WCAG AA for body text? Does `#6b6560` (mist) on `#1a1714` meet AA for secondary text?
2. Three font families — is this excessive for a 7-inch embedded display? Performance concern?

### Decision 3: Navigation — 8 Bottom Tabs

```
┌──────────────────────────────────────────────────────────────┐
│  ⚔️     👥     📖     🔬     📋     📡     🌐     ⚙️      │
│ 人机    人人    死活    研究    棋谱    直播    平台    设置    │
└──────────────────────────────────────────────────────────────┘
```

8 tabs in a `MuiBottomNavigation` (64px height) on a 7-10 inch screen.

**Review questions:**
1. 8 tabs — is this too many for a 7-inch display? Material Design recommends 3-5. Should we consider a "More" overflow tab?
2. Tab icons use `@mui/icons-material`. Are these distinctive enough for Go-specific concepts (AI play, tsumego)?
3. Game pages render fullscreen (no tab bar). Is hiding/showing bottom nav on route change the right UX pattern?

### Decision 4: Touch Interaction Specs

| Spec | Value |
|------|-------|
| Min touch target | 48x48px |
| Min button height | 56px |
| Element spacing | >=12px |
| Bottom nav height | 64px |
| Status bar height | 40px |
| Press feedback | `scale(0.96)` + darken, 100ms |

All using CSS transforms for GPU acceleration. No JS animation libraries.

### Decision 5: Kiosk Infrastructure

- Chromium `--kiosk --no-first-run --disable-translate --noerrdialogs --touch-events=enabled`
- Two systemd services: `katrain-server.service` (FastAPI) and `katrain-kiosk.service` (Chromium, depends on server)
- Hardware sensor data flows: Physical board → Python driver → FastAPI backend → WebSocket push → Frontend
- Frontend is input-source agnostic (same rendering for touch vs physical board moves)

**Review questions:**
1. Chromium on RK3588 (ARM64) with 7-inch display — any known performance pitfalls?
2. WebSocket for hardware input vs HTTP polling — correct choice for real-time stone placement?

### Decision 6: Layout Pattern

All pages follow: **left = board (square, maximized height) + right = control/info panel**

During active games, the layout is fullscreen (no status bar, no tab bar).

---

## Part 3: Implementation Plan Summary

14 tasks following strict TDD (test → verify fail → implement → verify pass → commit):

| # | Task | Files Created | Tests |
|---|------|--------------|-------|
| 1 | Kiosk theme (`createTheme`) | `kiosk/theme.ts` | 8 assertions: palette, typography, touch targets |
| 2 | StatusBar component | `kiosk/components/layout/StatusBar.tsx` | 3: branding, engine status, clock |
| 3 | BottomTabBar component | `kiosk/components/layout/BottomTabBar.tsx` | 2: 8 labels render, active route highlighting |
| 4 | KioskLayout shell | `kiosk/components/layout/KioskLayout.tsx` | 1: composes StatusBar + Outlet + TabBar |
| 5 | KioskApp + AppRouter wiring | `kiosk/KioskApp.tsx`, `kiosk/pages/PlaceholderPage.tsx`, fonts.css, modify `AppRouter.tsx` | 3: routing, placeholder, redirect |
| 6 | ModeCard reusable component | `kiosk/components/common/ModeCard.tsx` | 2: render props, navigation |
| 7 | OptionChips reusable component | `kiosk/components/common/OptionChips.tsx` | 2: render options, onChange callback |
| 8 | AI Play selection page | `kiosk/pages/AiPlayPage.tsx` | visual verify |
| 9 | AI Setup page | `kiosk/pages/AiSetupPage.tsx` | visual verify |
| 10 | Game page (fullscreen, mock) | `kiosk/pages/GamePage.tsx`, `MockBoard.tsx`, `GameControlPanel.tsx` | visual verify |
| 11 | PvP selection page | `kiosk/pages/PvpPlayPage.tsx` | visual verify |
| 12 | Tsumego selection page | `kiosk/pages/TsumegoPage.tsx` | visual verify |
| 13 | Remaining pages (Research, Kifu, Live, Platforms, Settings) | 5 page components | visual verify |
| 14 | Full test suite + visual review | — | regression check |

### Plan Review Questions

1. **Test coverage**: Tasks 8-13 rely on visual verification instead of unit tests. Should we add rendering tests for these pages too?
2. **Mock data approach**: All pages use hardcoded mock data inline. Should we create a `kiosk/mocks/` directory with shared mock data fixtures?
3. **Component granularity**: `GameControlPanel` is a single 60-line component with players, win rate, AI suggestion, and 6 control buttons. Should it be split into smaller components?
4. **PlaceholderPage pattern**: Used as a temporary component for unimplemented routes, then replaced one by one. Is this a reasonable scaffolding approach?
5. **AppRouter theme switching**: `const isKiosk = window.location.pathname.startsWith('/kiosk')` evaluated once at render — does this handle React Router navigation correctly, or should theme selection be reactive?

---

## Part 4: Specific Code Review Points

### Theme definition (Task 1)

```typescript
export const kioskTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#5cb57a' },
    background: { default: '#1a1714', paper: '#252019' },
    text: { primary: '#e8e4dc', secondary: '#6b6560' },
    error: { main: '#c45d3e' },
  },
  typography: {
    fontFamily: "'Noto Sans SC', 'Noto Sans', sans-serif",
    h1: { fontFamily: "'Noto Serif SC', 'Noto Serif', serif", fontWeight: 700 },
    // h2-h4 also Noto Serif SC
    caption: { fontFamily: "'JetBrains Mono', monospace", fontSize: 12 },
  },
  components: {
    MuiButton: { styleOverrides: { root: { minHeight: 56, '&:active': { transform: 'scale(0.96)' } } } },
    MuiIconButton: { styleOverrides: { root: { minWidth: 48, minHeight: 48 } } },
    MuiBottomNavigation: { styleOverrides: { root: { height: 64 } } },
  },
});
```

**Review**: Is `MuiButton.styleOverrides.root.minHeight: 56` globally appropriate? What about compact contexts like game control panels where 6 buttons need to fit in a grid?

### BottomTabBar routing (Task 3)

```typescript
const currentTab = tabs.findIndex((t) => location.pathname.startsWith(t.path));
```

**Review**: `startsWith` matching — if a user is at `/kiosk/ai/setup/free`, this matches the `/kiosk/ai` tab. Is this correct for all nested routes, or could `/kiosk/live` incorrectly match a hypothetical `/kiosk/livewatch`?

### KioskApp route structure (Task 5)

```typescript
<Routes>
  {/* Fullscreen — no tab bar */}
  <Route path="ai/game/:sessionId" element={<GamePage />} />
  <Route path="pvp/local/game/:sessionId" element={<GamePage />} />
  <Route path="pvp/room/:sessionId" element={<GamePage />} />

  {/* Standard — with tab bar */}
  <Route element={<KioskLayout />}>
    <Route index element={<Navigate to="/kiosk/ai" replace />} />
    <Route path="ai" element={<AiPlayPage />} />
    <Route path="ai/setup/:mode" element={<AiSetupPage />} />
    {/* ... other tabbed routes */}
  </Route>
</Routes>
```

**Review**: Fullscreen game routes are outside `<KioskLayout>` to hide the tab bar. Is there a cleaner pattern than duplicating route prefix handling?

### Font loading (Task 5)

```css
/* fonts.css — dev mode loads from Google Fonts CDN */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&...');
```

Production plan: bundle fonts locally. **Review**: Should the plan include the local font bundling setup now, or is deferring it acceptable?

---

## Part 5: What I'd Like You to Focus On

1. **Architecture**: Is the parallel `kiosk/` directory approach sound? Any better patterns for multi-theme React apps sharing a backend?
2. **UX for small screens**: 8 bottom tabs, 40px status bar, 64px tab bar — that's 104px of chrome on a ~400px-height landscape display. Is this too much? Should we consider collapsible chrome?
3. **Performance on RK3588**: MUI v7 + React 19 on Chromium/ARM64 with a 7-inch display — any red flags? Should we consider lighter alternatives?
4. **Missing considerations**: What are we not thinking about? Offline mode? Font rendering on low-DPI? Screen burn-in for kiosk? Touch calibration?
5. **Plan completeness**: The 14-task plan covers phase 1 (frontend mock). Are there any tasks missing before we can meaningfully evaluate the UI?
6. **Code quality**: Any anti-patterns in the proposed component code? Over-engineering? Under-engineering?

---

## Reference: Existing Galaxy Module Structure

For context, the existing Galaxy web UI has these routes and components:

```
Galaxy routes:
  /galaxy/          → Dashboard (module card grid)
  /galaxy/play      → PlayMenu (AI/Human choice)
  /galaxy/play/ai   → AiSetupPage
  /galaxy/play/game/:id → GamePage
  /galaxy/play/human    → HvHLobbyPage
  /galaxy/research      → ResearchPage
  /galaxy/kifu          → KifuLibraryPage
  /galaxy/live          → LivePage
  /galaxy/tsumego       → TsumegoLevelsPage (4-level deep navigation)

Galaxy components: ~48 .tsx files across components/, pages/, context/
Galaxy layout: 240px sidebar + main content area
```

The kiosk UI flattens navigation (removes Dashboard, promotes sub-modules to first-level tabs) and replaces the sidebar with a bottom tab bar.
