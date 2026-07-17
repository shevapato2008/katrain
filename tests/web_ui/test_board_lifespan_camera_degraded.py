"""Board startup remains available when the optional camera is absent."""

import asyncio
import sys
from types import SimpleNamespace

import pytest
from fastapi import APIRouter

# Keep this lifecycle unit test independent from the full endpoint import tree,
# which loads desktop i18n assets that are deliberately absent in web CI.
sys.modules["katrain.web.api.v1.api"] = SimpleNamespace(api_router=APIRouter())
from katrain.web import server


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
async def test_board_lifespan_degrades_when_camera_hub_cannot_start(monkeypatch, caplog):
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
async def test_board_lifespan_keeps_shared_camera_config_mismatch_fatal(monkeypatch):
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
