"""The web baipu route must boot in the board venv without Kivy installed."""

import subprocess
import sys


def test_baipu_route_and_replay_import_without_kivy():
    code = """
import importlib.abc
import sys

class NoKivy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "kivy" or fullname.startswith("kivy."):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)

sys.meta_path.insert(0, NoKivy())
from katrain.web import server
from katrain.web.api.v1.endpoints.baipu import router
from katrain.core.baipu import build_steps_from_sgf
assert server is not None
assert router is not None
assert build_steps_from_sgf("(;SZ[19];B[pd])")["board_size"] == 19
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_web_game_initialization_and_language_switch_do_not_load_desktop_gui(tmp_path, monkeypatch):
    monkeypatch.setenv("KIVY_HOME", str(tmp_path / "kivy"))
    monkeypatch.setenv("KATRAIN_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("DISPLAY", raising=False)
    code = """
import builtins
import socket
import sys
from sqlalchemy.engine import Engine

def no_connection(*args, **kwargs):
    raise AssertionError("headless game initialization must not connect to network or database")

socket.socket.connect = no_connection
socket.getaddrinfo = no_connection
Engine.connect = no_connection
Engine.raw_connection = no_connection
original_import = builtins.__import__

def without_desktop_gui(name, *args, **kwargs):
    if name == "kivymd.app" or name.startswith("kivy.core.window"):
        print("desktop GUI import attempted: " + name, file=sys.stderr)
        raise SystemExit(102)
    return original_import(name, *args, **kwargs)

builtins.__import__ = without_desktop_gui
from katrain.web.interface import WebKaTrain, NullEngine
from katrain.core.lang import i18n
from katrain.gui.theme import Theme

game = WebKaTrain(force_package_config=True, enable_engine=False)
i18n.switch_lang("jp")
assert i18n.font_name == "NotoSansJP-Regular.otf"
assert isinstance(i18n._("New Game"), str)
i18n.switch_lang("cn")
assert i18n.font_name == Theme.DEFAULT_FONT
game.start()
assert isinstance(game.engine, NullEngine)
assert game.get_state()["board_size"] == [19, 19]
game("play", (3, 3))
state = game.get_state()
assert state["last_move"] == [3, 3]
assert state["player_to_move"] == "W"
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
