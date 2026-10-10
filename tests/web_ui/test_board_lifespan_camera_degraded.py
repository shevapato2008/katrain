"""Board startup degrades without a camera and wires opt-in baipu collection."""

import asyncio
import importlib.util
import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType

import pytest
from fastapi import APIRouter, HTTPException

from katrain.web.api.v1.endpoints import baipu as baipu_api
from katrain.web.core import baipu_capture, capture_service
from katrain.web.core.device_lease import DeviceBusy
from katrain.web.core.camera_hub import CameraHub, CameraHubConfig
from katrain.web.api.v1.endpoints.vision import vision_status

from katrain.web.models import EndgameConflict, GameEnd


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
    controls_effective = None

    def __init__(self, config):
        self.config = config
        self.started = False
        type(self).instances.append(self)

    def start(self, *, allow_unavailable=False):
        self.started = True
        if not allow_unavailable:
            raise RuntimeError("Failed to open camera /dev/video0")

    def request_controls(self, **kwargs):
        pass


class _CameraAvailable(_CameraUnavailable):
    def start(self, *, allow_unavailable=False):
        self.started = True


class _CameraBusy(_CameraUnavailable):
    def start(self, *, allow_unavailable=False):
        self.started = True
        raise DeviceBusy("camera device 0 is busy (occupied)")


class _Led:
    instances = []

    def __init__(self, config):
        self.config = config
        self.started = False
        type(self).instances.append(self)

    def start(self):
        self.started = True


class _LedBusy(_Led):
    def start(self):
        self.started = True
        raise DeviceBusy("led device fake is busy (occupied)")


class _OptionalService:
    bound_session_id = None

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

    def start(self):
        pass

    def set_geometry(self, geometry):
        pass

    def poll_events(self):
        return []


class _Manager:
    on_session_removed = None

    def attach_loop(self, loop):
        self.loop = loop

    def remove_session(self, session_id):
        pass


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
    models = ModuleType("katrain.web.models")
    models.EndgameConflict = EndgameConflict
    models.GameEnd = GameEnd
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
        "katrain.web.models": models,
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
    task_names = (
        "cleanup_task",
        "ai_ladder_heartbeat_task",
        "led_failsafe_task",
        "vision_pump_task",
        "vision_poller_task",
    )
    for name in task_names:
        task = getattr(app.state, name, None)
        if task is not None:
            task.cancel()
    await asyncio.gather(
        *(task for task in (getattr(app.state, name, None) for name in task_names) if task),
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
    # 盒上报告 / 成长日历的本机兜底库(develop 2026-09 加进 board lifespan),同一族假仓库。
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.report_diagnosis_repo",
        SimpleNamespace(ReportDiagnosisRepository=_Repository),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.growth_activity",
        SimpleNamespace(GrowthActivityRepository=_Repository),
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
        "katrain.web.core.pvp_box_bridge",
        SimpleNamespace(PvpBoxBridge=lambda *args: SimpleNamespace(), PvpBoxRooms=lambda: SimpleNamespace()),
    )
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
    monkeypatch.setitem(sys.modules, "katrain.vision.service", SimpleNamespace(VisionService=_OptionalService))
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.capture_service",
        SimpleNamespace(CaptureService=_OptionalService),
    )
    for name, exports in {
        "katrain.vision.parallax_store": {
            "attach_parallax": lambda config, *args: (config, logging.INFO, "parallax off")
        },
        "katrain.web.core.physical_play": {"PhysicalPlayConfig": lambda: SimpleNamespace(hint_engine="local")},
        "katrain.web.core.physical_play_orchestrator": {"PhysicalPlayOrchestrator": _OptionalService},
        "katrain.web.core.hint_gate": {"DefaultHintGate": lambda engine: object()},
        "katrain.web.core.vision_pump": {"route_vision_event": lambda *args, **kwargs: None},
        "katrain.web.core.geometry_calibration_service": {"GeometryCalibrationService": _OptionalService},
        "katrain.web.core.baipu_capture": dict(
            resolve_baipu_collect=baipu_capture.resolve_baipu_collect,
            resolve_fiducial_mode=baipu_capture.resolve_fiducial_mode,
        ),
    }.items():
        monkeypatch.setitem(sys.modules, name, SimpleNamespace(**exports))
    monkeypatch.setitem(sys.modules, "katrain.web.core.led_service", SimpleNamespace(LedService=_Led))


@pytest.mark.asyncio
async def test_board_lifespan_keeps_camera_consumers_available_during_initial_absence(
    server_module, monkeypatch, caplog
):
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
        SimpleNamespace(enabled=True, camera_device=0, camera_width=1280, camera_height=720, backend="fake"),
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
            out_dir="/tmp/camera-recovery-test",
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

    class MissingCamera:
        is_connected = False
        available = False
        recovered = threading.Event()

        def open(self):
            self.is_connected = self.available
            if self.is_connected:
                self.recovered.set()
            return self.is_connected

        def close(self):
            pass

        def read_frame(self):
            if not self.is_connected:
                self.open()
            return None

    camera = MissingCamera()
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    hub = CameraHub(CameraHubConfig(), camera=camera)

    class Vision:
        enabled = True
        pose_lock_status = "unlocked"
        sync_state = "idle"
        bound_session_id = None

        def __init__(self, config, frame_source):
            self.frame_source = frame_source

        def start(self):
            pass

        def refresh_status(self):
            connected = self.frame_source.is_connected()
            self.camera_status = "connected" if connected else "disconnected"
            self._latest_status = SimpleNamespace(
                camera_ready=connected, geometry_ready=False, model_ready=True, recognition_ready=False
            )

    async def idle(_app):
        await asyncio.Event().wait()

    monkeypatch.setattr(server, "_vision_event_pump", idle)
    monkeypatch.setattr(server, "_vision_move_poller", idle)
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.camera_hub",
        SimpleNamespace(CameraHub=lambda config: hub, CameraHubConfig=CameraHubConfig),
    )
    monkeypatch.setitem(sys.modules, "katrain.vision.service", SimpleNamespace(VisionService=Vision))
    monkeypatch.setitem(
        sys.modules,
        "katrain.vision.parallax_store",
        SimpleNamespace(attach_parallax=lambda config, *args: (config, logging.INFO, "parallax off")),
    )
    monkeypatch.setitem(sys.modules, "katrain.web.core.capture_service", capture_service)
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.geometry_calibration_service",
        SimpleNamespace(GeometryCalibrationService=lambda **kwargs: SimpleNamespace(**kwargs)),
    )
    monkeypatch.setitem(sys.modules, "katrain.web.core.baipu_capture", baipu_capture)
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.physical_play",
        SimpleNamespace(PhysicalPlayConfig=lambda: SimpleNamespace(hint_engine="local")),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.physical_play_orchestrator",
        SimpleNamespace(PhysicalPlayOrchestrator=lambda **kwargs: SimpleNamespace(**kwargs)),
    )
    monkeypatch.setitem(
        sys.modules, "katrain.web.core.hint_gate", SimpleNamespace(DefaultHintGate=lambda engine: object())
    )
    monkeypatch.setattr(_Led, "is_connected", lambda self: True, raising=False)

    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))
    try:
        await server._lifespan_board(app, server.logging.getLogger("test.camera-degraded"))
        assert _Led.instances[0].started is True
        assert app.state.camera_hub is hub
        assert app.state.vision.frame_source is hub
        assert app.state.capture._hub is hub
        assert app.state.geometry_calibration.capture is app.state.capture
        assert app.state.physical_play.vision is app.state.vision
        assert app.state.geometry is None
        status = await vision_status(SimpleNamespace(app=app))
        assert status["enabled"] is True
        assert status["camera_connected"] is False
        assert status["camera_ready"] is False
        assert status["recognition_ready"] is False
        assert "camera unavailable" in caplog.text.lower()
        camera.available = True
        assert await asyncio.to_thread(camera.recovered.wait, 1)
        recovered = await vision_status(SimpleNamespace(app=app))
        assert recovered["camera_connected"] is True
        assert app.state.capture.is_connected()
        assert recovered["recognition_ready"] is False  # Calibration is still required.
    finally:
        await _cancel_startup_tasks(app)
        hub.stop()


@pytest.mark.asyncio
async def test_board_lifespan_degrades_on_camera_lease_conflict(server_module, monkeypatch, caplog):
    server = server_module
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(sys.modules["katrain.web.core.camera_hub"], "CameraHub", _CameraBusy)
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "DEVICE_ID", "device-1")
    monkeypatch.setattr(server.settings, "REMOTE_API_URL", "https://remote.example")
    monkeypatch.setattr(
        server.settings,
        "_vision_config",
        SimpleNamespace(enabled=True, camera_device=0, camera_width=1280, camera_height=720),
        raising=False,
    )
    monkeypatch.setattr(server.settings, "_capture_config", SimpleNamespace(enabled=False), raising=False)
    monkeypatch.setattr(
        server.settings, "_led_config", SimpleNamespace(enabled=True, serial_port="fake"), raising=False
    )
    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))

    await server._lifespan_board(app, server.logging.getLogger("test.camera-busy"))

    assert app.state.camera_hub is None
    assert app.state.vision is None
    assert isinstance(app.state.led, _Led)
    assert "camera device 0 is busy" in caplog.text.lower()
    await _cancel_startup_tasks(app)


@pytest.mark.asyncio
async def test_board_lifespan_degrades_on_led_lease_conflict_with_camera_running(server_module, monkeypatch, caplog):
    server = server_module
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(sys.modules["katrain.web.core.camera_hub"], "CameraHub", _CameraAvailable)
    monkeypatch.setattr(sys.modules["katrain.web.core.led_service"], "LedService", _LedBusy)
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.capture_service",
        SimpleNamespace(CaptureService=lambda *args, **kwargs: SimpleNamespace(start=lambda: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.baipu_capture",
        SimpleNamespace(resolve_baipu_collect=lambda *args: False, resolve_fiducial_mode=lambda *args: "auto"),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.geometry_calibration_service",
        SimpleNamespace(GeometryCalibrationService=lambda **kwargs: SimpleNamespace()),
    )
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "DEVICE_ID", "device-1")
    monkeypatch.setattr(server.settings, "REMOTE_API_URL", "https://remote.example")
    monkeypatch.setattr(server.settings, "_vision_config", SimpleNamespace(enabled=False), raising=False)
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
        server.settings, "_led_config", SimpleNamespace(enabled=True, serial_port="fake"), raising=False
    )
    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))

    await server._lifespan_board(app, server.logging.getLogger("test.led-busy"))

    assert isinstance(app.state.camera_hub, _CameraAvailable)
    assert app.state.capture is not None
    assert app.state.led is None
    assert getattr(app.state, "led_failsafe_task", None) is None
    assert "led device fake is busy" in caplog.text.lower()
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

    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))
    with pytest.raises(RuntimeError, match="Vision and capture must use the same camera device"):
        await server._lifespan_board(app, server.logging.getLogger("test.camera-config"))

    assert _CameraUnavailable.instances == []
    await _cancel_startup_tasks(app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cli", "env", "expected_collect"),
    [
        pytest.param([], None, False, id="default-off"),
        pytest.param(["--baipu-collect"], "0", True, id="cli-on"),
        pytest.param([], "1", True, id="env-on"),
    ],
)
async def test_baipu_collect_startup_wiring(server_module, monkeypatch, tmp_path, cli, env, expected_collect):
    """CLI/env must reach the HTTP gate through startup, not injected app.state."""
    server = server_module
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "KATRAIN_HOST", "127.0.0.1", raising=False)
    monkeypatch.setattr(server.settings, "KATRAIN_PORT", 8001, raising=False)
    monkeypatch.setattr(server.settings, "KATRAIN_MODE", "board", raising=False)
    monkeypatch.delenv("KATRAIN_BAIPU_COLLECT", raising=False)
    if env is not None:
        monkeypatch.setenv("KATRAIN_BAIPU_COLLECT", env)
    monkeypatch.setattr(sys, "argv", ["katrain", "--capture-camera", "0", "--capture-dir", str(tmp_path), *cli])

    # Keep the real resolver and CaptureService; only the camera and calibration
    # hardware are fake. A missing camera would let default-false hide broken wiring.
    monkeypatch.setattr(sys.modules["katrain.web.core.camera_hub"], "CameraHub", _CameraAvailable)
    monkeypatch.setitem(sys.modules, "katrain.web.core.capture_service", capture_service)
    monkeypatch.setitem(sys.modules, "katrain.web.core.baipu_capture", baipu_capture)
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.geometry_calibration_service",
        SimpleNamespace(GeometryCalibrationService=lambda **kwargs: object()),
    )
    monkeypatch.setitem(
        sys.modules, "katrain.vision.geometry_lock", SimpleNamespace(load_geometry_lock=lambda _path: None)
    )
    monkeypatch.setattr(server, "Path", lambda _path: tmp_path / "geometry_lock.npz")

    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))
    served_apps = []
    monkeypatch.setattr(server, "create_app", lambda **kwargs: app)
    monkeypatch.setattr(server, "build_frontend", lambda **kwargs: None)
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(
            config=SimpleNamespace(LOGGING_CONFIG={"formatters": {"default": {}, "access": {}}}),
            run=lambda app, **kwargs: served_apps.append(app),
        ),
    )

    try:
        server.run_web()  # Real argparse and settings assignments.
        assert served_apps == [app]
        await server._lifespan_board(served_apps[0], server.logging.getLogger("test.baipu-collect"))
        assert isinstance(app.state.capture, capture_service.CaptureService)
        assert app.state.camera_hub.started is True
        request = SimpleNamespace(app=app)
        assert await baipu_api.baipu_mode(request) == {"collect": expected_collect}
        # No geometry lock: enabled collection reaches the existing 409; disabled
        # collection must stop at the new 404 gate before touching the camera.
        with pytest.raises(HTTPException) as exc:
            await baipu_api.baipu_capture(
                request, baipu_api.BaipuCaptureRequest(game_id="g", move_index=-1, sgf="(;SZ[19];B[pd])")
            )
        assert exc.value.status_code == (409 if expected_collect else 404)
    finally:
        await _cancel_startup_tasks(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("has_generation", [True, False])
async def test_board_lifespan_selects_camera_mode_from_atomic_hardware_state(
    server_module, monkeypatch, tmp_path, has_generation
):
    server = server_module
    _CameraUnavailable.instances.clear()
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "DEVICE_ID", "device-1")
    monkeypatch.setattr(server.settings, "REMOTE_API_URL", "https://remote.example")
    monkeypatch.setattr(
        server.settings,
        "_vision_config",
        SimpleNamespace(
            enabled=True, camera_device="/dev/video73", camera_width=1280, camera_height=720, backend="fake"
        ),
        raising=False,
    )
    monkeypatch.setattr(
        server.settings,
        "_capture_config",
        SimpleNamespace(
            enabled=True,
            camera_device="/dev/video73",
            width=1280,
            height=720,
            lock_exposure=True,
            exposure=999.0,
            lock_awb=False,
        ),
        raising=False,
    )
    monkeypatch.setattr(server.settings, "_led_config", SimpleNamespace(enabled=False), raising=False)
    monkeypatch.setattr(server.settings, "_hardware_vision_dir", str(tmp_path), raising=False)

    geometry = object()
    state = (
        SimpleNamespace(
            geometry=geometry,
            profile=SimpleNamespace(strategy="hardware_auto_then_lock", exposure=None),
        )
        if has_generation
        else None
    )

    class FakeHardwareVisionStore:
        instances = []

        def __init__(self, root):
            self.root = root
            self.load_calls = []
            type(self).instances.append(self)

        def load_current(self, camera_device, width, height):
            self.load_calls.append((camera_device, width, height))
            return state

    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.hardware_vision_state",
        SimpleNamespace(
            HardwareVisionStateStore=FakeHardwareVisionStore,
            CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK="hardware_auto_then_lock",
            CameraProfile=lambda **kwargs: SimpleNamespace(**kwargs),
        ),
    )
    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))
    await server._lifespan_board(app, server.logging.getLogger("test.hardware-vision-startup"))

    assert FakeHardwareVisionStore.instances[0].load_calls == [("/dev/video73", 1280, 720)]
    config = _CameraUnavailable.instances[0].config
    assert config.lock_exposure is has_generation
    assert config.exposure is None

    await _cancel_startup_tasks(app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("has_generation", "controls_effective"),
    [(True, True), (True, False), (False, None)],
)
async def test_vision_only_startup_uses_geometry_from_atomic_hardware_state(
    server_module, monkeypatch, tmp_path, has_generation, controls_effective
):
    server = server_module
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "DEVICE_ID", "device-1")
    monkeypatch.setattr(server.settings, "REMOTE_API_URL", "https://remote.example")
    monkeypatch.setattr(
        server.settings,
        "_vision_config",
        SimpleNamespace(
            enabled=True,
            camera_device="/dev/video73",
            camera_width=1280,
            camera_height=720,
            backend="fake",
        ),
        raising=False,
    )
    monkeypatch.setattr(server.settings, "_capture_config", SimpleNamespace(enabled=False), raising=False)
    monkeypatch.setattr(server.settings, "_led_config", SimpleNamespace(enabled=False), raising=False)
    monkeypatch.setattr(server.settings, "_hardware_vision_dir", str(tmp_path), raising=False)

    async def idle_vision_task(_app):
        await asyncio.Event().wait()

    monkeypatch.setattr(server, "_vision_event_pump", idle_vision_task)
    monkeypatch.setattr(server, "_vision_move_poller", idle_vision_task)

    geometry = object()
    state = (
        SimpleNamespace(
            geometry=geometry,
            profile=SimpleNamespace(strategy="hardware_auto_then_lock", exposure=None),
            generation="gen-1",
        )
        if has_generation
        else None
    )

    class CameraHub:
        def __init__(self, config):
            self.config = config
            self.controls_effective = controls_effective
            self.control_calls = []
            type(self).instance = self

        def start(self, *, allow_unavailable=False):
            pass

        def request_controls(self, **controls):
            self.control_calls.append(controls)

    class VisionService:
        instances = []

        def __init__(self, config, frame_source):
            self.config = config
            self.frame_source = frame_source
            self.geometry_calls = []
            type(self).instances.append(self)

        def start(self):
            pass

        def set_geometry(self, lock):
            self.geometry_calls.append(lock)

    class HardwareVisionStateStore:
        def __init__(self, root):
            self.root = root

        def load_current(self, camera_device, width, height):
            return state

    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.camera_hub",
        SimpleNamespace(CameraHub=CameraHub, CameraHubConfig=lambda **kwargs: SimpleNamespace(**kwargs)),
    )
    monkeypatch.setitem(sys.modules, "katrain.vision.service", SimpleNamespace(VisionService=VisionService))

    attach_parallax_calls = []
    attached_config = SimpleNamespace(marker="attached-config", backend="fake")

    def fake_attach_parallax(vision_config, hardware_vision_dir, current_generation):
        attach_parallax_calls.append((vision_config, hardware_vision_dir, current_generation))
        return attached_config, logging.INFO, "parallax off: not calibrated"

    monkeypatch.setitem(
        sys.modules, "katrain.vision.parallax_store", SimpleNamespace(attach_parallax=fake_attach_parallax)
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.hardware_vision_state",
        SimpleNamespace(
            HardwareVisionStateStore=HardwareVisionStateStore,
            CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK="hardware_auto_then_lock",
        ),
    )
    monkeypatch.setitem(sys.modules, "katrain.vision.camera", SimpleNamespace(CAMERA_AUTO_EXPOSURE_ON=3.0))
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.physical_play",
        SimpleNamespace(PhysicalPlayConfig=lambda: SimpleNamespace(hint_engine="local")),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.physical_play_orchestrator",
        SimpleNamespace(PhysicalPlayOrchestrator=lambda **kwargs: SimpleNamespace()),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.hint_gate",
        SimpleNamespace(DefaultHintGate=lambda _engine: SimpleNamespace()),
    )

    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))
    await server._lifespan_board(app, server.logging.getLogger("test.vision-only-hardware-state"))

    try:
        strategy_verified = has_generation and controls_effective is True
        assert app.state.geometry is (geometry if strategy_verified else None)
        assert VisionService.instances[0].geometry_calls == ([geometry] if strategy_verified else [])
        if has_generation and not strategy_verified:
            assert CameraHub.instance.control_calls == [{"auto_exposure": 3.0}]
        else:
            assert CameraHub.instance.control_calls == []
        assert attach_parallax_calls == [
            (
                server.settings._vision_config,
                str(tmp_path),
                "gen-1" if strategy_verified else None,
            )
        ]
        assert VisionService.instances[0].config is attached_config
    finally:
        await _cancel_startup_tasks(app)


@pytest.mark.asyncio
async def test_capture_startup_forwards_publish_gate_to_hardware_store(server_module, monkeypatch, tmp_path):
    server = server_module
    _install_board_startup_fakes(monkeypatch)
    monkeypatch.setattr(server, "_init_platform_manager", lambda *args: None)
    monkeypatch.setattr(server.settings, "DEVICE_ID", "device-1")
    monkeypatch.setattr(server.settings, "REMOTE_API_URL", "https://remote.example")
    monkeypatch.setattr(server.settings, "_vision_config", SimpleNamespace(enabled=False), raising=False)
    monkeypatch.setattr(
        server.settings,
        "_capture_config",
        SimpleNamespace(
            enabled=True,
            camera_device="/dev/video73",
            width=1280,
            height=720,
            lock_exposure=False,
            exposure=None,
            lock_awb=False,
        ),
        raising=False,
    )
    monkeypatch.setattr(server.settings, "_led_config", SimpleNamespace(enabled=False), raising=False)
    monkeypatch.setattr(server.settings, "_hardware_vision_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(server.settings, "_baipu_fiducial_mode", "off", raising=False)

    class CameraHub:
        def __init__(self, config):
            self.config = config

        def start(self, *, allow_unavailable=False):
            pass

    class CaptureService:
        def __init__(self, config, hub):
            self.config = config
            self.hub = hub

        def start(self):
            pass

    class HardwareVisionStateStore:
        instances = []

        def __init__(self, root):
            self.root = root
            self.commit_calls = []
            type(self).instances.append(self)

        def load_current(self, camera_device, width, height):
            return None

        def commit(self, lock, profile, before_publish=None):
            self.commit_calls.append((lock, profile, before_publish))

    class CameraProfile:
        def __init__(self, **kwargs):
            self.values = kwargs

    class GeometryCalibrationService:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.camera_hub",
        SimpleNamespace(CameraHub=CameraHub, CameraHubConfig=lambda **kwargs: SimpleNamespace(**kwargs)),
    )
    monkeypatch.setitem(sys.modules, "katrain.web.core.capture_service", SimpleNamespace(CaptureService=CaptureService))
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.baipu_capture",
        SimpleNamespace(
            resolve_fiducial_mode=lambda configured, env: configured,
            resolve_baipu_collect=lambda configured, env: False,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.hardware_vision_state",
        SimpleNamespace(
            HardwareVisionStateStore=HardwareVisionStateStore,
            CameraProfile=CameraProfile,
            CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK="hardware_auto_then_lock",
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.core.geometry_calibration_service",
        SimpleNamespace(GeometryCalibrationService=GeometryCalibrationService),
    )

    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager(), box_sso=SimpleNamespace()))
    await server._lifespan_board(app, server.logging.getLogger("test.hardware-state-persist-hook"))

    lock = object()
    before_publish = lambda: None
    app.state.geometry_calibration.kwargs["persist_state"](lock, "hardware_auto_then_lock", before_publish)

    committed_lock, profile, committed_hook = HardwareVisionStateStore.instances[0].commit_calls[0]
    assert committed_lock is lock
    assert profile.values["strategy"] == "hardware_auto_then_lock"
    assert "exposure" not in profile.values
    assert committed_hook is before_publish

    await _cancel_startup_tasks(app)
