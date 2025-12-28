# KaTrain

## Project Overview

KaTrain is a tool for analyzing games and playing Go (Baduk/Weiqi) with AI feedback from KataGo. It features a graphical user interface (GUI) built with Kivy and integrates deeply with the KataGo engine for analysis and gameplay.

**Key Features:**
*   Game review and analysis.
*   Play against AI with adjustable strength and styles.
*   SGF editor and parser.
*   Distributed training contribution.

**Tech Stack:**
*   **Language:** Python 3.9+
*   **GUI:** Kivy, KivyMD
*   **AI Engine:** KataGo (packaged with the application or external)
*   **Dependency Management:** `uv` (recommended), `pip`

## Directory Structure

*   `katrain/`: Main application source code.
    *   `core/`: Core logic, game state, AI integration (`engine.py`, `game.py`).
    *   `gui/`: Kivy-based UI code (`badukpan.py`, `controlspanel.py`).
    *   `i18n/`: Internationalization files (`locales/`).
    *   `KataGo/`: KataGo binaries and configuration files.
*   `tests/`: Unit and integration tests.
*   `themes/`: Visual themes for the board and UI.
*   `pyproject.toml`: Project configuration and dependencies.

## Building and Running

### Prerequisites

*   Python 3.9 or higher.
*   `uv` (optional but recommended for dependency management).
*   OpenCL-capable GPU (recommended for KataGo performance) or Eigen (CPU) version.

### Installation

1.  **Install Dependencies:**
    Using `uv`:
    ```bash
    uv sync
    ```
    Or using `pip`:
    ```bash
    pip install .
    ```

2.  **Run the Application:**
    ```bash
    python -m katrain
    ```

## Development Conventions

### Formatting and Linting

*   **Formatter:** `black` is used for code formatting.
    *   Line length: 120
    *   Command: `black -l 120 .`
*   **Linter:** `flake8` is configured in `.flake8`.
    *   Command: `flake8`

### Testing

*   **Test Runner:** `pytest`
*   **Run Tests:**
    ```bash
    pytest
    ```
    *Note: Some tests (like `test_ai.py`) may skip if OpenCL is not available or if running in a CI environment.*

### Internationalization (i18n)

*   Translation files are located in `katrain/i18n/locales/`.
*   New translations require creating a new `.po` file based on the English template.
*   See `CONTRIBUTIONS.md` for detailed instructions on updating or adding translations.

### Contribution Workflow

*   Discuss major changes via issues or Discord before starting.
*   Format code with `black` before submitting.
*   Ensure tests pass.
