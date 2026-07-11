"""Directory-scoped hermeticity fixture for tests/platforms.

Task 5 finding: `BaseGame.__init__` (katrain/core/game.py) silently seeds handicap
placement stones from `katrain.config("game/handicap")` for every freshly-created
session that doesn't pass an explicit `handicap` kwarg -- the normal
`SessionManager.create_session()` / `.create_multiplayer_session()` path used
throughout this directory's real-stack tests. A dev box that has ever played (or
configured) a local handicap game leaves stray pre-placed stones on EVERY session
these tests create, unrelated to whatever the test is actually exercising --
dirtying checked-in fixtures (test_engine_manager.py's contract dump) and desyncing
assertions that expect a clean board (test_engine_integration.py, test_engine_rebuild.py).

This autouse fixture forces the single `"game/handicap"` config lookup to 0 for
every test under this directory; every other config key (and every EXPLICIT
handicap a test passes via `edit_game`/`EngineGameConfig`) is untouched.
"""

import pytest

from katrain.core.base_katrain import KaTrainBase


@pytest.fixture(autouse=True)
def _hermetic_handicap_default(monkeypatch):
    original_config = KaTrainBase.config

    def _patched(self, setting, default=None):
        if setting == "game/handicap":
            return 0
        return original_config(self, setting, default)

    monkeypatch.setattr(KaTrainBase, "config", _patched)
