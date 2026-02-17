# RK3588 Smart Board Terminal — Kiosk UI Design

## Overview

Design a touch-optimized kiosk UI variant for KaTrain running on RK3588-based smart Go board terminals with 7-10 inch displays. The terminal has a physical board with sensor input (image recognition / Hall effect sensors) and a touchscreen for controls and AI analysis display.

## Requirements

| Dimension | Decision |
|-----------|----------|
| Scope | Full-featured compact edition — all modules retained, touch-adapted |
| Screen | 7-10 inch touchscreen, landscape-only (phase 1), multiple resolutions |
| Input | Physical board sensors for stone placement; touchscreen for controls |
| Screen board role | Display AI suggestions, not primary move input (except tsumego) |
| Auth | Multi-user, login required on each boot |
| Hardware integration | To be designed — backend pushes sensor data via WebSocket |
| External platforms | Reserved entry point (99Go, FoxGo, Tencent Go, Sina Go) |
| Kiosk mode | Boot-to-app, no exit, auto-restart on crash |
| Implementation order | Frontend first (mock data), backend integration second |

## Architecture: Code Organization

**Approach A (selected)**: Independent theme directory `src/kiosk/` parallel to `src/galaxy/`, with shared layer extracted.

```
katrain/web/ui/src/
├── shared/                    # Extracted shared layer
│   ├── api/                   # REST + WebSocket communication
│   │   ├── gameApi.ts
│   │   ├── analysisApi.ts
│   │   ├── authApi.ts
│   │   └── wsClient.ts
│   ├── components/
│   │   ├── Board.tsx          # Canvas board rendering (display + event callbacks)
│   │   ├── ScoreGraph.tsx
│   │   └── PlayerCard.tsx
│   ├── hooks/
│   │   ├── useGameSession.ts
│   │   ├── useResearchBoard.ts
│   │   ├── useResearchSession.ts
│   │   └── useTsumegoProblem.ts
│   ├── types/
│   │   ├── game.ts
│   │   ├── analysis.ts
│   │   └── kifu.ts
│   └── utils/                 # sgfSerializer, rankUtils, etc.
│
├── galaxy/                    # Web UI (existing, imports refactored to shared/)
│
├── kiosk/                     # Terminal UI (new)
│   ├── components/
│   ├── pages/
│   ├── hooks/
│   ├── context/
│   ├── theme.ts
│   └── KioskApp.tsx
│
└── main.tsx                   # Route dispatch: /galaxy/* | /kiosk/* | /
```

### Build Strategy

- Single Vite project, no monorepo
- `npm run build` outputs both galaxy + kiosk
- `npm run dev` serves both at different URL prefixes
- Shared layer via ES imports, Vite tree-shaking handles dead code

### Entry Route Dispatch

```
/galaxy/*  → GalaxyApp (existing web UI)
/kiosk/*   → KioskApp (terminal UI)
/          → ZenModeApp (legacy compatibility)
```

## Visual Design: "Ink Stone" Aesthetic

A refined aesthetic inspired by Go itself — ink stones, wooden boards, zen restraint. Warmer and more grounded than Galaxy's space-tech theme.

### Color System

```css
--ink-black:      #1a1714;     /* Ink base — warmer than Galaxy's #0f0f0f */
--stone-white:    #e8e4dc;     /* Stone white — warm ivory tone */
--wood-amber:     #8b7355;     /* Board wood — warm amber brown */
--jade-deep:      #2d5a3d;     /* Deep jade — quieter than Galaxy's #4a6b5c */
--jade-glow:      #5cb57a;     /* Jade glow — AI suggestion highlight */
--ember:          #c45d3e;     /* Vermillion — warning/error/bad move */
--mist:           #6b6560;     /* Mist — secondary text, dividers */
--parchment:      #f5f0e8;     /* Parchment — card/panel background (sparingly) */
```

### Typography

| Role | Font | Rationale |
|------|------|-----------|
| Display | Noto Serif SC | Headlines, module names — calligraphic character |
| Body | Noto Sans SC | Text, buttons — clear readability |
| Mono | JetBrains Mono | Numbers, coordinates, win rates |

All fonts locally loaded (no network dependency), with full CJK support.

### Touch Interaction Specs

| Spec | Value | Rationale |
|------|-------|-----------|
| Min touch target | 48x48px | Google Material touch guideline |
| Min button height | 56px | Thumb comfort zone |
| Element spacing | >=12px | Prevent mis-taps |
| Feedback latency | <100ms | Immediate visual feedback |
| Long-press threshold | 500ms | Secondary actions |
| Swipe gesture | Horizontal page/panel switch | Replace mouse hover interactions |

### Touch Feedback Animations

- Press: `scale(0.96)` + slight darken, 100ms ease-out
- Release: `scale(1.0)` + ripple, 200ms
- Page transition: horizontal slide, 250ms ease-in-out
- Panel expand: bottom slide-up, 300ms cubic-bezier(0.32, 0.72, 0, 1)

CSS-first animations with `will-change` and `transform` for GPU acceleration. No heavy JS animation libraries.

## Navigation Structure

### Status Bar (40px)

```
┌──────────────────────────────────────────────────┐
│  KaTrain   ● Engine OK  │  张三(2D)  🌐中文  12:30 │
└──────────────────────────────────────────────────┘
```

Language switch as status bar button. User profile accessible via username tap.

### Bottom Tab Bar — 8 First-Level Entries

```
┌──────────────────────────────────────────────────────────────┐
│  ⚔️     👥     📖     🔬     📋     📡     🌐     ⚙️      │
│ 人机    人人    死活    研究    棋谱    直播    平台    设置    │
└──────────────────────────────────────────────────────────────┘
```

### Navigation Map

| Tab | Content | Sub-pages |
|-----|---------|-----------|
| ⚔️ Human vs AI | Two cards: Free Play / Ranked Play | Setup → Game (fullscreen) |
| 👥 Human vs Human | Two cards: Local Game / Online Lobby | Setup → Game (fullscreen) |
| 📖 Tsumego | Problem grid (flattened from Galaxy's 4 levels) | Problem solving page |
| 🔬 Research | Research board + analysis | Single page |
| 📋 Kifu Library | Game list + preview | Replay page |
| 📡 Live | Match list | Spectator page |
| 🌐 Platforms | Platform selection grid (99Go, FoxGo, Tencent, Sina...) | WebView/redirect |
| ⚙️ Settings | Language settings (consistent with Galaxy) | — |

### Galaxy → Kiosk Module Mapping

| Galaxy Module | Kiosk Location | Change |
|---------------|---------------|--------|
| Dashboard (module cards) | **Removed** | Tabs provide direct access |
| Play → Free Play | ⚔️ AI → Free Play | Merged setup into one page |
| Play → Ranked Play | ⚔️ AI → Ranked Play | Merged setup into one page |
| HvH Lobby | 👥 PvP → Online Lobby | First-level access |
| *(New)* Local Game | 👥 PvP → Local Game | New: two players on physical board |
| Tsumego (4-level nav) | 📖 Tsumego | Flattened to 2 levels |
| Research (L1/L2 state machine) | 🔬 Research | Simplified single flow |
| Kifu Library | 📋 Kifu | Adapted layout |
| Live | 📡 Live | First-level access |
| External platforms | 🌐 Platforms | First-level access, reserved |
| Settings | ⚙️ Settings | Language only |
| System update / About | Hidden: long-press Logo | Maintenance access |

## Page Layouts (Landscape-Only)

### Unified Layout Principle

**Left: board area (square, maximized) + Right: control/info panel**

### ⚔️ Game Page (Core — During Active Game)

```
┌──────────────────────────────────────────┐
│ Status: ● Black Zhang  vs  ○ White AI-5D │
├──────────────────┬───────────────────────┤
│                  │  ● Zhang (2D)   ○:32  │
│                  │  ○ KataGo-5D    ●:31  │
│                  ├───────────────────────┤
│                  │  Win rate: 56.3%      │
│   Board +        │  ▓▓▓▓▓▓▓░░░░░        │
│   AI overlay     │  [Score trend mini]   │
│   (square)       ├───────────────────────┤
│                  │  Best: R16 (94.2%)    │
│                  │  Alt:  Q3  (3.1%)     │
│                  ├───────────────────────┤
│                  │  [Undo] [Pass] [Count]│
│                  │  [Resign][Settings][X] │
└──────────────────┴───────────────────────┘
  (Tab bar hidden during active game)
```

Board overlay: AI suggested moves shown as pulsing `jade-glow` dots, size proportional to probability.

### ⚔️ AI Game Setup (Merged PlayMenu + AiSetup)

```
┌──────────────────────────────────────────┐
│ AI Setup                    [Start →]    │
├──────────────────┬───────────────────────┤
│                  │  Board: [9] [13] [19] │
│                  │                       │
│   Board preview  │  Color: [● B] [○ W]  │
│   (empty)        │                       │
│                  │  AI: ━━━●━━━━  ~5D    │
│                  │                       │
│                  │  Handicap: [0][2][3][4]│
│                  │                       │
│                  │  Time: [None] [10min] │
│                  │        [20min] [30min]│
└──────────────────┴───────────────────────┘
```

All options are large buttons/sliders — no dropdowns, no text input.

### 📖 Tsumego — Problem Selection

```
┌──────────────────────────────────────────┐
│ ← Tsumego                  Filter: [All] │
├──────────────────┬───────────────────────┤
│                  │ ┌─────┐ ┌─────┐      │
│   Preview board  │ │Beg.1│ │Beg.2│ ...  │
│   (MiniBoard)    │ └─────┘ └─────┘      │
│                  │ ┌─────┐ ┌─────┐      │
│                  │ │Int.1│ │Int.2│ ...  │
│                  │ └─────┘ └─────┘      │
│                  │   (scrollable grid)   │
└──────────────────┴───────────────────────┘
```

### 📖 Tsumego — Problem Solving

```
┌──────────────────────────────────────────┐
│ ← Beginner #3              [Hint] [Next] │
├──────────────────┬───────────────────────┤
│                  │                       │
│                  │   Black to play,      │
│   Tsumego board  │   capture white       │
│   (zoomed local) │                       │
│   ★ TOUCH INPUT  │   Time: 00:42        │
│                  │                       │
│                  │  [Reset] [Previous]   │
│                  │  [Hint]  [Next]       │
└──────────────────┴───────────────────────┘
```

Note: Tsumego is the ONLY module requiring touch-to-place on screen (no physical board equivalent).

### 🔬 Research

```
┌──────────────────────────────────────────┐
│ ← Research       [Load SGF] [Clear] [Go] │
├──────────────────┬───────────────────────┤
│                  │  Analysis:            │
│                  │  Win: 62.1%           │
│   Research board │  Best: [D4][Q16][C6]  │
│   (touch place)  │                       │
│                  │  [Score trend]        │
│                  │                       │
│                  │  ◀ ◁  Move:34  ▷ ▶   │
│                  │  [Variations] [AI Go] │
└──────────────────┴───────────────────────┘
```

### 📋 Kifu Library

```
┌──────────────────────────────────────────┐
│ ← Kifu Library             [Search][Add] │
├──────────────────┬───────────────────────┤
│                  │  Ke Jie vs Shin J.    │
│   Preview board  │  2024 LG Cup Final    │
│   (MiniBoard)    │  Result: W+R          │
│                  ├───────────────────────┤
│                  │  Li Changho vs Cho    │
│                  │  Zhang vs AI-5D (me)  │
│                  │  ... (scrollable)     │
└──────────────────┴───────────────────────┘
```

### 🌐 External Platforms

```
┌──────────────────────────────────────────┐
│ External Platforms                        │
├──────────────────────────────────────────┤
│                                          │
│  ┌──────────┐  ┌──────────┐             │
│  │  99围棋   │  │ 野狐围棋  │             │
│  └──────────┘  └──────────┘             │
│  ┌──────────┐  ┌──────────┐             │
│  │ 腾讯围棋  │  │ 新浪围棋  │             │
│  └──────────┘  └──────────┘             │
│                                          │
│         (large card grid)                │
└──────────────────────────────────────────┘
```

## Kiosk Infrastructure

### Recommended: Chromium Kiosk Mode

| Approach | Pros | Cons |
|----------|------|------|
| **Chromium --kiosk** | Simplest, zero extra deps, native web redirect for external platforms | No direct local hardware API |
| Electron | Local hardware access, window control | Large bundle, extra maintenance |
| Tauri | Lightweight, hardware access | Rust toolchain, smaller community |

**Selected: Chromium kiosk.** Hardware sensor data flows through the backend via WebSocket — no need for frontend-to-hardware direct access.

### Boot Sequence

```
Power on
  → systemd starts katrain-server.service (FastAPI + KataGo)
  → systemd starts katrain-kiosk.service (Chromium, depends on server)
  → Chromium fullscreen opens http://localhost:8001/kiosk/
  → Login page displayed
  → User logs in → main interface
```

### systemd Services

**katrain-server.service**: `python -m katrain --ui web --host 127.0.0.1 --port 8001`, `Restart=always`, starts before kiosk.

**katrain-kiosk.service**: `chromium --kiosk --no-first-run --disable-translate --noerrdialogs --touch-events=enabled http://localhost:8001/kiosk/`, `Depends=katrain-server.service`, `Restart=always`.

### Crash Recovery

- Chromium crash → systemd auto-restart → page reload
- Backend crash → systemd auto-restart → frontend shows "Connecting..." with auto-reconnect
- Frontend adds enhanced WebSocket reconnect UI (building on existing logic)

## Hardware Input Integration

### Data Flow

```
Physical board (sensors)
    ↓  Serial/GPIO/USB
Hardware driver service (Python)
    ↓  Internal call
KaTrain backend (FastAPI)
    ↓  WebSocket push
Kiosk frontend
    ↓  Canvas render
Screen display
```

### WebSocket Messages (Reserved)

```json
// Single stone event
{
  "type": "board_input",
  "data": {
    "action": "place",
    "position": [3, 15],
    "color": "black",
    "timestamp": 1708123456
  }
}

// Full board sync (game start / calibration)
{
  "type": "board_sync",
  "data": {
    "stones": [[3,15,"B"], [4,4,"W"]],
    "source": "hall_sensor"
  }
}
```

### Frontend Handling

Kiosk frontend listens for `board_input` alongside existing `game_update`:
- Receive `board_input` → call backend `/api/move` → triggers normal `game_update` push
- Frontend is input-source agnostic — same rendering whether move comes from touch or physical board

## Implementation Order

1. **Frontend first** — build all kiosk pages with mock data, verify visual design
2. **Shared layer extraction** — refactor galaxy imports to shared/
3. **Backend routing** — serve kiosk at /kiosk/* path
4. **Backend integration** — connect real game sessions, WebSocket, auth
5. **Kiosk infrastructure** — systemd services, Chromium kiosk config
6. **Hardware integration** — board sensor driver + WebSocket bridge
