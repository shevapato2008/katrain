# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KaTrain is a Go/Baduk/Weiqi playing and teaching application that integrates with the KataGo AI engine. It features dual UI implementations:
- **Desktop GUI**: Kivy-based cross-platform application
- **Web UI**: FastAPI backend + React/Vite frontend

The project enables game analysis, AI-assisted play with immediate feedback, and automatic SGF review generation.

## Build & Development Commands

### Installation
```bash
uv sync                              # Install all deps including dev tools
pip install -e .                     # Alternative: editable install
pip install -r requirements-web.txt  # Web-specific deps only
```

### Running the Application
```bash
python -m katrain                    # Web UI (default)
python -m katrain --ui desktop       # Desktop GUI
python -m katrain --ui web --host 127.0.0.1 --port 8001  # Custom host/port
```

### Testing
```bash
uv run pytest tests                  # Full test suite
CI=true uv run pytest tests          # Skip GPU-dependent AI tests
uv run pytest tests/test_board.py    # Specific test file
```

### Web Frontend Development
```bash
cd katrain/web/ui
npm install
npm run dev                          # Dev server with HMR
npm run build                        # Production build → katrain/web/static/
npm test                             # Unit tests (vitest)
npm run test:e2e                     # Playwright e2e (serves the BUILT bundle from :8002 —
                                     #   source edits need `npm run build` first)
npm run fourup                       # 27-screen four-up visual capture (vite dev server, :5173)
```

`npm run fourup` regenerates `superpowers/tracks/kiosk-go-shell-align/visual/**`. Judge the result
**per screen, as a set of four**: an implementation shot committed without its side-by-side leaves a
self-contradicting archive.

**The jitter floor is not one number — it depends on what renders the board.** Screens whose board is
DOM/SVG jitter under ~200 changed pixels; screens whose board is a `<canvas>` (`LiveBoard`, e.g. 05 /
20 / 21 / 10) jitter by **~4500** run to run. A pixel count alone will therefore mislead you on canvas
screens. The reliable discriminator is **run the capture twice and diff the two runs** — that gives
this screen's own floor. Failing that, look at the bbox: jitter is scattered across the whole frame,
a content change is clustered. Revert the jitter-only screens (`git checkout HEAD -- <screen dir>`)
rather than committing them.

The reference half of every four-up lives in **another repo** (`smartbox-software`), pinned by sha256
in `tests/helpers/reference-shots.json`. If a shot's bytes don't match the pin, the harness fetches the
pinned version from that repo's git by the recorded branch — so the capture does not depend on which
branch that working tree happens to be on. A pin mismatch on the recorded branch means the design
actually changed: look at what moved, re-shoot, and commit new images and new pins together.

`python -m katrain --ui web` auto-builds the frontend on first run (creates `katrain/web/static/index.html`). Subsequent runs **reuse** the existing dist — critical on slow ARM SBCs where `npm run build` takes ~60s. To rebuild after pulling new UI code:
```bash
python -m katrain --ui web --force-build       # explicit rebuild flag
# or:
rm -rf katrain/web/static && python -m katrain --ui web   # nuke and re-trigger first-run build
```

### Code Formatting
```bash
uv run black -l 120 katrain tests    # Format Python code (120 char lines)
```

### i18n
```bash
uv run python i18n.py -todo          # Check translation status
uv run python i18n.py                # Regenerate .mo files
```

## Architecture

### Project Structure
```
katrain/
├── core/           # Game logic & KataGo engine integration
│   ├── game.py         # Game tree representation
│   ├── game_node.py    # Individual nodes with analysis data
│   ├── engine.py       # KataGo subprocess & HTTP client
│   ├── ai.py           # 15+ AI strategy implementations
│   └── sgf_parser.py   # SGF format handling
├── gui/            # Kivy-based desktop interface
├── web/            # FastAPI backend
│   ├── server.py       # App initialization, lifespan hooks
│   ├── session.py      # SessionManager for user sessions
│   ├── core/           # DB, auth, engine client, router
│   ├── api/v1/         # REST endpoints
│   └── ui/             # React/Vite frontend source
└── {img,fonts,sounds,models,i18n,KataGo}/  # Assets
```

### Key Architectural Patterns

**Dual-UI Mode Detection**: `katrain/__main__.py` auto-detects UI mode via CLI args (`--ui web/desktop`), config file, or defaults to web. Both UIs share `katrain/core` logic.

**Dual-Engine Routing** (Smart Board feature): Routes "playing" queries to local CPU KataGo (fast, weak) and "analysis" queries to cloud GPU KataGo (slow, strong) via `katrain/web/core/router.py`.

**Session Snapshotting**: Settings are snapshotted at game start so mid-game changes don't disrupt active sessions.

**Game Node Tree**: Games are trees of `GameNode` objects containing move data, KataGo analysis (evaluation, top moves, policy), and teaching metadata.

**AI Strategy Registry**: Strategies use `@register_strategy` decorator for pluggable implementations.

### Engine Abstraction

`BaseEngine` supports:
- Local subprocess (KataGo binary)
- HTTP remote (KataGo server API)
- Contribute engine (distributed training)

Configure via `~/.katrain/config.json`:
```json
{
  "engine": {
    "backend": "http",
    "http_url": "http://localhost:8000",
    "http_analyze_path": "/analyze",
    "http_health_path": "/health"
  }
}
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop UI | Kivy 2.3.1 + KivyMD |
| Web Backend | FastAPI + Uvicorn |
| Web Frontend | React + TypeScript + Vite |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT + bcrypt |
| AI Engine | KataGo (HTTP API) |
| HTTP Client | httpx (async) |
| ORM | SQLAlchemy 2.0+ |
| Testing | pytest + Playwright |

## Code Style

- Python: Black with 120-char lines, snake_case for functions/variables, PascalCase for classes
- AI strategy constants: `AI_STRATEGY_NAME` prefix
- Localize strings via `i18n("key")` with `.po` files in `katrain/i18n/`

## Testing Guidelines

- Fixtures in `tests/data/` (SGF files)
- `CI=true` skips GPU-dependent tests
- Web frontend tests: Playwright in `katrain/web/ui/tests/`
- Test both local subprocess and HTTP engine backends when modifying engine code

## Key Files to Start With

1. `katrain/__main__.py` - Entry point, UI mode detection
2. `katrain/core/base_katrain.py` - Base class with config, logging, players
3. `katrain/core/game.py` - Game tree structure
4. `katrain/core/engine.py` - KataGo interface
5. `katrain/web/server.py` - FastAPI initialization
6. `katrain/web/session.py` - Session management

## SBC 构建边界契约

KaTrain ships **two web-UI build outputs** from a single codebase:

| Output | Produced by | Shipped to | Contents |
|---|---|---|---|
| `katrain/web/static/` | `npm run build` | Server (full web) | Everything — galaxy admin, 3D board, tutorial recording, etc. |
| `katrain/web/static-kiosk-2d/` | `npm run build:kiosk-2d` | **SBC kiosk terminals** (RK3562/RK3576/RK3588) | Kiosk UI only — **no three.js, no `@react-three/*`, no `/galaxy/*`, no `/record`** |

**How isolation is enforced (three layers):**
1. Compile-time flag `__KIOSK_2D_ONLY__` (declared in `katrain/web/ui/src/vite-env.d.ts`, wired via `define` in `vite.config.ts`). In `AppRouter.tsx` the kiosk ternary collapses to `null`, so Rollup DCEs the `/galaxy/*` and `/record` lazy `import()` chunks entirely.
2. `rollupOptions.external: ['three', '@react-three/fiber', '@react-three/drei']` in kiosk mode — if a surviving import path reaches these, Rollup fails/warns.
3. `npm run verify:kiosk-2d` (chained into `build:kiosk-2d`) greps the dist for `THREE.` and `three`/`@react-three` import strings. **Exit 0 = clean; any match = build fails.** CI (`.github/workflows/kiosk_build.yml`) runs this on every PR touching `katrain/web/ui/**`.

**Boundary rules (enforced by `katrain/web/ui/eslint.config.js`):**
- Files under `src/kiosk/**` may **not** import from `src/galaxy/**`, `src/components/Board3D/**`, or `src/pages/VideoRecorderPage*`
- Files under `src/galaxy/**`, `src/pages/**`, and `src/ZenModeApp.tsx` may **not** import from `src/kiosk/**`

**Shared territory (both builds may import):**
`src/components/` (except `Board3D/`), `src/hooks/`, `src/context/`, `src/features/`, `src/api.ts` + `src/api/`, `src/utils/`, `src/types/`, `src/theme.ts`, `src/i18n.ts`. ~10.6K LOC. **Modifying a shared file affects BOTH builds** — run both `npm run build` and `npm run build:kiosk-2d` before pushing.

Shared code must **not** import from `src/kiosk/`, `src/galaxy/`, or `src/pages/` — a shared file that reaches back into one side drags that side into the *other* bundle, and the two rules above only see the import line as written, so one hop through shared territory is invisible to them. `eslint.config.js` enforces this (test files are exempt: they are in neither bundle).

**When modifying the web UI:**
- Adding a page/route in `src/kiosk/` → use only shared territory + `src/kiosk/`.
- Adding a 3D-dependent feature → put it under `src/galaxy/` or `src/pages/` behind a non-kiosk route; `Board3D/` is OK from those paths.
- Changing something in shared territory (e.g. `Board.tsx`, `api.ts`, `useTsumegoProblem.ts`) → assume kiosk consumes it; keep the kiosk build green.

**Related docs:** `superpowers/tracks/sbc-ui-ver3/plan.md` (the kiosk-build implementation plan from 2026-04-24).

## gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

Available skills:
- `/office-hours` — YC-style office hours (startup or builder mode)
- `/plan-ceo-review` — CEO/founder-mode plan review
- `/plan-eng-review` — Eng manager plan review
- `/plan-design-review` — Designer's eye plan review
- `/design-consultation` — Design system consultation
- `/design-shotgun` — Generate multiple design variants
- `/design-html` — Production-quality HTML/CSS generation
- `/review` — Pre-landing PR review
- `/ship` — Ship workflow (test, bump, PR)
- `/land-and-deploy` — Merge, deploy, verify
- `/canary` — Post-deploy canary monitoring
- `/benchmark` — Performance regression detection
- `/browse` — Headless browser for QA and browsing
- `/connect-chrome` — Launch AI-controlled Chromium
- `/qa` — QA test and fix bugs
- `/qa-only` — QA report only (no fixes)
- `/design-review` — Visual QA and fix
- `/setup-browser-cookies` — Import browser cookies
- `/setup-deploy` — Configure deployment settings
- `/retro` — Weekly engineering retrospective
- `/investigate` — Systematic debugging
- `/document-release` — Post-ship docs update
- `/codex` — OpenAI Codex CLI wrapper
- `/cso` — Security audit
- `/autoplan` — Auto-review pipeline
- `/plan-devex-review` — DX plan review
- `/devex-review` — Live DX audit
- `/careful` — Destructive command warnings
- `/freeze` — Restrict edits to a directory
- `/guard` — Full safety mode
- `/unfreeze` — Clear freeze boundary
- `/gstack-upgrade` — Upgrade gstack
- `/learn` — Manage project learnings
