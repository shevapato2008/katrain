# Repository Guidelines

## Project Structure & Module Organization
- `katrain/` holds the application: `core/` links game logic to the KataGo engine; `gui/` is the Kivy/MD interface; `i18n/` contains `.po` locales; assets live in `img/`, `fonts/`, `models/`, `sounds/`, and the bundled `KataGo/` binaries/configs.
- `tests/` contains the pytest suite for board rules, SGF parsing, and AI integration, with fixtures in `tests/data/`.
- `themes/` and `THEMES.md` document UI theme files; `spec/` and `test_katrain.spec` support PyInstaller builds; top-level docs (`README.md`, `INSTALL.md`, `ENGINE.md`, `CONTRIBUTIONS.md`) cover usage and troubleshooting.

## Build, Test, and Development Commands
- Install deps: `uv sync` (includes dev tools per `pyproject.toml`), or `pip install .` for runtime only and `pip install black pytest` for tooling.
- Run the app from source after installing deps: `python -m katrain` (or the installed `katrain` script). Use a terminal to view KataGo logs.
- Format: `black -l 120 katrain tests`.
- Tests: `pytest` for the full suite. The AI test expects a working KataGo/OpenCL setup; set `CI=true pytest` to skip it on machines without GPU support.
- Package (optional): `pyinstaller test_katrain.spec` creates a desktop bundle; ensure assets and KataGo binaries are present.

## Coding Style & Naming Conventions
- Python code follows Black with 120-character lines; prefer idiomatic snake_case for functions/variables and PascalCase for classes.
- Keep UI changes aligned with existing Kivy widget patterns in `katrain/gui/`; reuse shared widgets and themes rather than duplicating styles.
- Localize user-facing strings through `katrain/i18n` and keep placeholders (`{}`) intact.

## Testing Guidelines
- Add or extend `tests/test_*.py` alongside new features; place SGF/NGF fixtures in `tests/data/`.
- When touching engine interactions, verify both parser tests and the AI test if GPU support is available; otherwise document skipped coverage in the PR.
- Favor small, deterministic game fragments to keep test runtime short.

## Commit & Pull Request Guidelines
- Commit messages are short, present-tense summaries (e.g., `allow 3.13`, `add mac app icon (#774)`); reference issues/PRs with `#` when applicable.
- For PRs, include: intent summary, test results (`pytest` and manual app run/OS tested), and screenshots or screen recordings for UI changes.
- For larger features, open an issue or start a discussion before implementation (see `CONTRIBUTIONS.md`); call out engine/KataGo config impacts explicitly.
