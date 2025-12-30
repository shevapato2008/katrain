import json
import os
import sys
import types


def _platform_label():
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "macosx"
    return "linux"


class _MockConfig:
    @staticmethod
    def set(*_args, **_kwargs):
        return None


class _MockObservable:
    def __init__(self, *_args, **_kwargs):
        pass


class _MockClock:
    @staticmethod
    def schedule_once(func, _timeout=0):
        if func:
            func(0)
        return None

    @staticmethod
    def schedule_interval(_func, _timeout):
        return None


class _MockJsonStore(dict):
    def __init__(self, filename, **_kwargs):
        super().__init__()
        self.filename = filename
        self["general"] = {"version": "0.0.0", "debug_level": 0}
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.update(data)
            except Exception:
                pass

    def put(self, key, **kwargs):
        self[key] = kwargs

    def get(self, key):
        return self[key]


class _MockMDApp:
    @staticmethod
    def get_running_app():
        return _MockMDApp
    gui = None

def _ensure_module(name):
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    return module


def ensure_kivy():
    # Force headless environment variables
    os.environ["KIVY_NO_ARGS"] = "1"
    os.environ["KIVY_NO_FILELOG"] = "1"
    os.environ["KIVY_NO_WINDOW"] = "1"
    os.environ["KIVY_USE_ASSET_LOADER"] = "1"
    os.environ["KCFG_KIVY_LOG_LEVEL"] = "warning"

    if "kivy" in sys.modules:
        print("WARNING: kivy already imported before ensure_kivy called!")

    try:
        import kivy  # noqa: F401
        from kivy.base import EventLoop
        if not EventLoop.window:
             # Prevent window creation by setting a dummy if not exists
             class MockWindow:
                 def __init__(self, *args, **kwargs): pass
                 def bind(self, *args, **kwargs): pass
                 def remove_widget(self, *args, **kwargs): pass
                 def add_widget(self, *args, **kwargs): pass
                 @property
                 def size(self): return (800, 600)
                 @property
                 def width(self): return 800
                 @property
                 def height(self): return 600
                 @property
                 def dpi(self): return 96
                 @property
                 def system_size(self): return (800, 600)
                 
             EventLoop.window = MockWindow()
        return False
    except Exception:
        kivy_mod = _ensure_module("kivy")
        kivy_mod.Config = _MockConfig

        config_mod = _ensure_module("kivy.config")
        config_mod.Config = _MockConfig

        storage_mod = _ensure_module("kivy.storage")
        jsonstore_mod = _ensure_module("kivy.storage.jsonstore")
        jsonstore_mod.JsonStore = _MockJsonStore
        storage_mod.jsonstore = jsonstore_mod

        utils_mod = _ensure_module("kivy.utils")
        utils_mod.platform = _platform_label()

        clock_mod = _ensure_module("kivy.clock")
        clock_mod.Clock = _MockClock

        event_mod = _ensure_module("kivy._event")
        event_mod.Observable = _MockObservable

        kivymd_mod = _ensure_module("kivymd")
        kivymd_app_mod = _ensure_module("kivymd.app")
        kivymd_app_mod.MDApp = _MockMDApp
        kivymd_mod.app = kivymd_app_mod

        return True
