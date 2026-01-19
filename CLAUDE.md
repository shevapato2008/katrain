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
npm test                             # Playwright e2e tests
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
