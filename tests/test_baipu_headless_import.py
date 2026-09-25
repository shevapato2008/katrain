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
