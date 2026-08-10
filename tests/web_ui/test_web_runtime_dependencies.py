"""The web server's declared dependency set must be able to serve what it routes.

These are declaration contracts, not import smoke tests. The bug they exist to stop is
the one this repo has now hit twice: a package declared in `requirements-web.txt` but
missing from `pyproject.toml`, so `pip install -r requirements-web.txt` works and
`uv sync` -- the install path CLAUDE.md documents -- silently produces a broken server.

For WebSockets the breakage is invisible until a real browser plays a real game:
uvicorn without the `standard` extra has no WebSocket implementation, so `/ws/{session}`
404s at handshake. The game page has no polling fallback (`useGameSession.ts` opens one
WebSocket and never reconnects), and a human move renders from its own HTTP response --
so the board shows YOUR stone and the AI's reply never arrives. It looks like a dead
engine, not a missing dependency.
"""

import importlib.util
import tomllib
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"

_WEBSOCKET_IMPLEMENTATIONS = ("websockets", "wsproto")


def _web_extra_requirements() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["optional-dependencies"]["web"]


def test_the_web_extra_declares_a_websocket_capable_uvicorn():
    """`uv sync` must install something that can answer a WebSocket handshake.

    Either uvicorn carries its `standard` extra, or an implementation is declared
    outright. Asserting on the declaration (not on the current venv) is the point:
    a developer who happens to have websockets installed cannot make this pass.
    """
    requirements = _web_extra_requirements()

    uvicorn_requirements = [r for r in requirements if r.split(">=")[0].split("==")[0].split("[")[0].strip() == "uvicorn"]
    assert uvicorn_requirements, f"the web extra no longer declares uvicorn at all: {requirements}"

    declares_standard_extra = any("[standard]" in r for r in uvicorn_requirements)
    declares_implementation = any(
        r.split(">=")[0].split("==")[0].split("[")[0].strip() in _WEBSOCKET_IMPLEMENTATIONS for r in requirements
    )

    assert declares_standard_extra or declares_implementation, (
        "pyproject's web extra declares bare uvicorn, so `uv sync` installs a server whose "
        "/ws/{session_id} endpoint 404s at handshake. requirements-web.txt gets this right "
        "(`uvicorn[standard]`), which is exactly why the gap survives: the pip path works and "
        "the uv path does not. Declare `uvicorn[standard]` here too.\n"
        f"  declared: {uvicorn_requirements}"
    )


def test_a_websocket_implementation_is_importable():
    """The installed environment honors the declaration above.

    Separate from the declaration test on purpose: this one catches an environment that
    drifted from the manifest (a stale venv, a partial install), which is a different
    failure than a wrong manifest and wants a different fix.
    """
    found = [name for name in _WEBSOCKET_IMPLEMENTATIONS if importlib.util.find_spec(name) is not None]

    if not found:
        pytest.fail(
            "no WebSocket implementation installed, so uvicorn serves /ws/{session_id} as 404. "
            "Live game state never reaches the browser: the AI's move is broadcast only over "
            "that socket. Re-sync the environment after the declaration fix "
            "(`uv sync`), or `pip install -r requirements-web.txt`."
        )
