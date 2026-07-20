import sys
from pathlib import Path
from unittest.mock import MagicMock

# Force pytest to import the current workspace before similarly named sibling repos.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Define a list of kivy modules to mock
kivy_modules = [
    "kivy",
    "kivy.config",
    "kivy.storage",
    "kivy.storage.jsonstore",
    "kivy.utils",
    "kivy.clock",
    "kivy.properties",
    "kivy.uix",
    "kivy.uix.boxlayout",
    "kivy.uix.widget",
    "kivy.core",
    "kivy.core.window",
    "kivy.metrics",
    "kivy._event",
    "kivy.lang",
    "kivy.resources",
    "kivy.app",
    "kivy.core.clipboard",
    "kivymd",
    "kivymd.app",
    "kivymd.uix",
    "kivymd.uix.floatlayout",
]

for mod in kivy_modules:
    sys.modules[mod] = MagicMock()

# Specific mocks for values and classes
sys.modules["kivy.utils"].platform = "linux"


class MockObservable:
    pass


sys.modules["kivy._event"].Observable = MockObservable

# Mock JsonStore to behave like a dict for simple tests
import json
import os


class MockJsonStore(dict):
    def __init__(self, filename, **kwargs):
        super().__init__()
        self.filename = filename
        # Initialize with some default values to avoid KeyError in KaTrainBase
        self["general"] = {"version": "0.0.0", "debug_level": 0}
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    self.update(json.load(f))
            except Exception:
                pass

    def put(self, key, **kwargs):
        self[key] = kwargs

    def get(self, key):
        return self[key]


sys.modules["kivy.storage.jsonstore"].JsonStore = MockJsonStore

# Mock Config
sys.modules["kivy"].Config = MagicMock()
sys.modules["kivy.config"].Config = MagicMock()

# Mock katrain.web.interface to prevent kivy/lang import chain triggered
# by katrain/web/__init__.py → katrain/web/interface.py → katrain.core...
sys.modules["katrain.web.interface"] = MagicMock()

# ---------------------------------------------------------------------------
# Shared `app()` fixture (moved here from test_ai_game_autosave.py, R3-F4/R4-F5):
# a non-strict (server-mode) app wired with real SQLite-backed repos, used by
# both test_ai_game_autosave.py and test_guest_write_block.py. pytest discovers
# fixtures defined in conftest.py for every sibling module in this directory,
# so this single definition is enough for both -- unlike a plain function
# (see tests/web_ui/_helpers.py for why `_create_user_and_login` had to move
# to an importable module instead of also living here).
#
# `settings.DATABASE_URL` is assigned at IMPORT time (module level), not inside
# the fixture body: several sibling test modules (test_billing_api.py,
# test_reports_api.py, test_user_data_api.py, ...) read `settings.DATABASE_URL`
# fresh inside THEIR OWN fixture bodies at test-run time. `settings` is one
# process-wide singleton, so reassigning it at fixture-RUN time here would
# stomp their value every time this fixture runs interleaved with theirs
# (confirmed: it made test_user_data_api.py silently create its users against
# THIS file's sqlite db instead of its own, tripping a duplicate-username
# IntegrityError several tests later). Assigning once at collection time
# (like every sibling module already does) avoids that.
#
# Symmetrically, THIS fixture's own engine is built from a hardcoded path/URL
# constant, NOT a fresh read of `settings.DATABASE_URL` at fixture-run time --
# collection imports every sibling test module up front, each doing its own
# module-level `settings.DATABASE_URL = ...`, so by the time any fixture
# actually RUNS, the shared global could hold whichever sibling module's
# value was collected last. Hardcoding here decouples this fixture from that
# collection-order lottery entirely (confirmed: reading `settings.DATABASE_URL`
# at fixture-run time intermittently pointed this fixture at test_user_data.db
# instead of its own file, leaking UserGame rows across this file's own tests).
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from katrain.web.core.config import settings  # noqa: E402
from katrain.web.core.db import Base  # noqa: E402
from katrain.web.core.auth import SQLAlchemyUserRepository  # noqa: E402
from katrain.web.core.game_repo import GameRepository  # noqa: E402
from katrain.web.core.user_game_repo import UserGameRepository, UserGameAnalysisRepository  # noqa: E402
from katrain.web.server import create_app  # noqa: E402

_APP_FIXTURE_DB_PATH = "./test_ai_autosave.db"
_APP_FIXTURE_DB_URL = f"sqlite:///{_APP_FIXTURE_DB_PATH}"

settings.DATABASE_URL = _APP_FIXTURE_DB_URL


@pytest.fixture
def app():
    if os.path.exists(_APP_FIXTURE_DB_PATH):
        os.remove(_APP_FIXTURE_DB_PATH)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine(_APP_FIXTURE_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    app = create_app(enable_engine=False)
    app.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)
    app.state.game_repo = GameRepository(TestSessionLocal)
    app.state.user_game_repo = UserGameRepository(TestSessionLocal)
    app.state.user_game_analysis_repo = UserGameAnalysisRepository(TestSessionLocal)
    app.state.report_session_factory = TestSessionLocal

    yield app

    if os.path.exists(_APP_FIXTURE_DB_PATH):
        os.remove(_APP_FIXTURE_DB_PATH)
