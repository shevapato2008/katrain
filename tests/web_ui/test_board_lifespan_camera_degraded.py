"""Board startup remains available when the optional camera is absent."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType

import pytest
from fastapi import APIRouter

class _Repository:
    def __init__(self, *args, **kwargs):
        pass

    def init_db(self):
        pass


class _SyncWorker:
    def __init__(self, *args, **kwargs):
        pass

    def recover_stale_leases(self):
        pass


class _Connectivity:
    def __init__(self, *args, **kwargs):
        self.started = False

    def start(self):
        self.started = True


class _CameraUnavailable:
    instances = []

    def __init__(self, config):
        self.config = config
        self.started = False
        type(self).instances.append(self)

    def start(self):
        self.started = True
        raise RuntimeError("Failed to open camera /dev/video0")


class _Led:
    instances = []

    def __init__(self, config):
        self.config = config
        self.started = False
        type(self).instances.append(self)

    def start(self):
        self.started = True


class _MustNotConstruct:
    def __init__(self, *args, **kwargs):
        raise AssertionError("camera-dependent service must not be constructed")


class _Manager:
    def attach_loop(self, loop):
        self.loop = loop


def _package(name):
    module = ModuleType(name)
    module.__path__ = []
    return module


@pytest.fixture
def server_module(monkeypatch):
    """Load server.py as a leaf and restore every temporary package afterwards."""
    katrain = _package("katrain")
    web = _package("katrain.web")
    api = _package("katrain.web.api")
    api_v1 = _package("katrain.web.api.v1")
    core = _package("katrain.web.core")
    katrain.web = web
    web.api = api
    web.core = core
    api.v1 = api_v1
    modules = {
        "katrain": katrain,
        "katrain.web": web,
        "katrain.web.api": api,
        "katrain.web.api.v1": api_v1,
        "katrain.web.core": core,
        "katrain.web.api.v1.api": SimpleNamespace(api_router=APIRouter()),
        "katrain.web.core.catalog_cache": SimpleNamespace(add_catalog_cache_middleware=lambda app: None),
        "katrain.web.core.config": SimpleNamespace(
            settings=SimpleNamespace(
                DEVICE_ID="",
                REMOTE_API_URL="",
                LOCAL_KATAGO_URL="",
                CLOUD_KATAGO_URL="",
            )
        ),
        "katrain.web.session": SimpleNamespace(
            SessionManager=object,
            LobbyManager=lambda: object(),
            Matchmaker=lambda: object(),
        ),
        "katrain.web.models": ModuleType("katrain.web.models"),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location(
        "test_board_lifespan_server",
        Path(__file__).resolve().parents[2] / "katrain" / "web" / "server.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


async def _cancel_startup_tasks(app):
    for name in ("cleanup_task", "led_failsafe_task"):
        task = getattr(app.state, name, None)
        if task is not None:
            task.cancel()
    await asyncio.gather(
        *(
            task
            for task in (
                getattr(app.state, "cleanup_task", None),
                getattr(app.state, "led_failsafe_task", None),
            )
            if task
        ),
        return_exceptions=True,
    )


def _install_board_startup_fakes(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.auth",
        SimpleNamespace(SQLAlchemyUserRepository=_Repository),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.user_game_repo",
        SimpleNamespace(UserGameRepository=_Repository, UserGameAnalysisRepository=_Repository),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.tsumego_progress_repo",
        SimpleNamespace(LocalTsumegoProgressRepository=_Repository),
    )
    monkeypatch.setitem(sys.modules, "katrain.web.core.db", SimpleNamespace(SessionLocal=object()))
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.remote_client",
        SimpleNamespace(RemoteAPIClient=lambda **kwargs: SimpleNamespace()),
    )
    monkeypatch.setitem(sys.modules, "katrain.web.core.sync_worker", SimpleNamespace(SyncWorker=_SyncWorker))
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.connectivity",
        SimpleNamespace(ConnectivityManager=_Connectivity),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.repository",
        SimpleNamespace(
            RepositoryDispatcher=_Repository,
            RemoteTsumegoRepository=_Repository,
            RemoteKifuRepository=_Repository,
            RemoteUserGameRepository=_Repository,
            enqueue_sync_item=lambda *args, **kwargs: None,
        ),
    )
    monkeypatch.setitem(sys.modules, "katrain.web.core.router", SimpleNamespace(build_router=lambda *args: object()))
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.box_sso",
        SimpleNamespace(strict_box_sso_enabled=lambda: True),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.interface",
        SimpleNamespace(WebKaTrain=lambda **kwargs: SimpleNamespace(config=lambda _name: {})),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.camera_hub",
        SimpleNamespace(CameraHub=_CameraUnavailable, CameraHubConfig=lambda **kwargs: SimpleNamespace(**kwargs)),
    )
    monkeypatch.setitem(sys.modules, "katrain.vision.service", SimpleNamespace(VisionService=_MustNotConstruct))
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.capture_service",
        SimpleNamespace(CaptureService=_MustNotConstruct),
    )
    monkeypatch.setitem(sys.modules, "katrain.web.core.led_service", SimpleNamespace(LedService=_Led))


@pytest.mark.asyncio
async def test_board_lifespan_degrades_when_camera_hub_cannot_start(server_module, monkeypatch, caplog):
    server = server_module
    _CameraUnavailable.instances.clear()
    _Led.instances.clear()
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "DEVICE_ID", "device-1")
    monkeypatch.setattr(server.settings, "REMOTE_API_URL", "https://remote.example")
    monkeypatch.setattr(
        server.settings,
        "_vision_config",
        SimpleNamespace(enabled=True, camera_device=0, camera_width=1280, camera_height=720),
        raising=False,
    )
    monkeypatch.setattr(
        server.settings,
        "_capture_config",
        SimpleNamespace(
            enabled=True,
            camera_device=0,
            width=1280,
            height=720,
            lock_exposure=False,
            exposure=None,
            lock_awb=False,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        server.settings,
        "_led_config",
        SimpleNamespace(enabled=True, serial_port="fake"),
        raising=False,
    )

    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager()))
    await server._lifespan_board(app, server.logging.getLogger("test.camera-degraded"))

    assert _CameraUnavailable.instances[0].started is True
    assert _Led.instances[0].started is True
    assert app.state.camera_hub is None
    assert app.state.vision is None
    assert app.state.vision_ws_clients == {}
    assert app.state.vision_move_queue is None
    assert app.state.vision_pump_task is None
    assert app.state.vision_poller_task is None
    assert app.state.capture is None
    assert app.state.geometry is None
    assert app.state.geometry_calibration is None
    assert app.state.physical_play is None
    assert app.state.physical_play_config is None
    assert "camera unavailable" in caplog.text.lower()

    await _cancel_startup_tasks(app)


@pytest.mark.asyncio
async def test_board_lifespan_keeps_shared_camera_config_mismatch_fatal(server_module, monkeypatch):
    server = server_module
    _CameraUnavailable.instances.clear()
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "DEVICE_ID", "device-1")
    monkeypatch.setattr(server.settings, "REMOTE_API_URL", "https://remote.example")
    monkeypatch.setattr(
        server.settings,
        "_vision_config",
        SimpleNamespace(enabled=True, camera_device=0, camera_width=1280, camera_height=720),
        raising=False,
    )
    monkeypatch.setattr(
        server.settings,
        "_capture_config",
        SimpleNamespace(
            enabled=True,
            camera_device=1,
            width=1280,
            height=720,
            lock_exposure=False,
            exposure=None,
            lock_awb=False,
        ),
        raising=False,
    )
    monkeypatch.setattr(server.settings, "_led_config", SimpleNamespace(enabled=False), raising=False)

    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager()))
    with pytest.raises(RuntimeError, match="Vision and capture must use the same camera device"):
        await server._lifespan_board(app, server.logging.getLogger("test.camera-config"))

    assert _CameraUnavailable.instances == []
    await _cancel_startup_tasks(app)
