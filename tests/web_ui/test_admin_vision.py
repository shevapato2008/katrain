"""Local admin vision boundaries, exercised without opening real hardware."""

import base64
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from jose import jwt

SECRET = "vision-admin-secret-" * 3
PASSWORD_HASH = "$2b$12$" + "a" * 53
PATH = "/api/admin/vision"


class Camera:
    def __init__(self, device_id):
        self.device_id = device_id
        self.started = False
        self.stops = 0
        self.reads = 0
        self.frame = np.full((1080, 1920, 3), 90, dtype=np.uint8)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False
        self.stops += 1
        self.frame = None

    def is_connected(self):
        return self.started

    def grab_fresh(self, after_ts=None, settle_ms=0):
        self.reads += 1
        return self.frame, self.reads, time.monotonic()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("KATRAIN_MODE", "server")
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", PASSWORD_HASH)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", SECRET)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "local")
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_LOCAL", "1")
    monkeypatch.delenv("KATRAIN_ADMIN_VISION_LED_PORT", raising=False)


def headers(env="local", **claims):
    payload = {
        "sub": "admin:fan",
        "type": "admin_session",
        "aud": "katrain-admin",
        "env": env,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    payload.update(claims)
    return {"Authorization": "Bearer " + jwt.encode(payload, SECRET, algorithm="HS256")}


def make_app(tmp_path, bind_host="127.0.0.1"):
    from katrain.web.admin.app import create_admin_app

    return create_admin_app(session_factory=object(), static_dir=tmp_path, bind_host=bind_host)


@pytest.mark.parametrize(
    "method,route,body",
    [
        ("GET", "status", None),
        ("GET", "devices", None),
        ("GET", "preview", None),
        ("POST", "connect", {"device_id": 0, "mode": "stones2"}),
        ("POST", "disconnect", None),
        ("POST", "calibrate", {"empty_confirmed": True}),
    ],
)
def test_every_vision_route_requires_dedicated_admin(configured, tmp_path, method, route, body):
    client = TestClient(make_app(tmp_path))
    for auth in ({}, headers(type="access"), headers(exp=datetime.now(timezone.utc) - timedelta(seconds=1))):
        assert client.request(method, f"{PATH}/{route}", json=body, headers=auth).status_code == 401


@pytest.mark.parametrize(
    "env,switch,bind",
    [
        ("test", "1", "127.0.0.1"),
        ("prod", "1", "127.0.0.1"),
        ("local", "0", "127.0.0.1"),
        ("local", None, "127.0.0.1"),
        ("local", "1", "0.0.0.0"),
        ("local", "1", None),
    ],
)
def test_disabled_configuration_fails_closed(configured, monkeypatch, tmp_path, env, switch, bind):
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", env)
    if switch is None:
        monkeypatch.delenv("KATRAIN_ADMIN_VISION_LOCAL")
    else:
        monkeypatch.setenv("KATRAIN_ADMIN_VISION_LOCAL", switch)
    client = TestClient(make_app(tmp_path, bind))
    status = client.get(f"{PATH}/status", headers=headers(env)).json()
    assert status["enabled"] is False
    assert status["local_only"] is True
    assert status["camera"]["state"] == "unknown"
    for method, route, body in [
        ("GET", "devices", None),
        ("GET", "preview", None),
        ("POST", "connect", {"device_id": 0, "mode": "stones2"}),
        ("POST", "disconnect", None),
        ("POST", "calibrate", {"empty_confirmed": True}),
    ]:
        assert client.request(method, f"{PATH}/{route}", json=body, headers=headers(env)).status_code == 403


@pytest.fixture
def hardware(configured, monkeypatch):
    from katrain.web.admin import vision_runtime

    cameras = []

    def create_camera(device_id):
        camera = Camera(device_id)
        cameras.append(camera)
        return camera

    monkeypatch.setattr(vision_runtime, "create_camera", create_camera)
    return cameras


def test_creation_status_devices_and_unconnected_preview_never_open_hardware(hardware, tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        status = client.get(f"{PATH}/status", headers=headers()).json()
        assert status["enabled"] is True
        assert status["camera"]["state"] == "unknown"
        assert status["geometry"]["state"] == "required"
        assert status["sgf"]["state"] == status["dataset"]["state"] == "none"
        assert status["observed_at"]
        candidates = client.get(f"{PATH}/devices", headers=headers()).json()["candidates"]
        assert [item["device_id"] for item in candidates] == list(range(9))
        assert all(item["probed"] is False for item in candidates)
        assert client.get(f"{PATH}/preview", headers=headers()).status_code == 409
        assert hardware == []


def test_explicit_connect_disconnect_and_shutdown_release_hardware(hardware, tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        connected = client.post(f"{PATH}/connect", json={"device_id": 2, "mode": "stones2"}, headers=headers())
        assert connected.status_code == 200
        assert connected.json()["camera"]["state"] == "connected"
        assert connected.json()["led"]["state"] == "disabled"
        assert hardware[0].device_id == 2
        assert (
            client.post(f"{PATH}/connect", json={"device_id": 3, "mode": "stones2"}, headers=headers()).status_code
            == 409
        )
        for _ in range(2):
            assert client.post(f"{PATH}/disconnect", headers=headers()).json()["camera"]["state"] == "disconnected"
        assert hardware[0].stops == 1
        client.post(f"{PATH}/connect", json={"device_id": 2, "mode": "stones2"}, headers=headers())
    assert hardware[1].stops == 1
    assert client.app.state.vision_runtime.camera is None


@pytest.mark.parametrize(
    "body",
    [
        {"device_id": -1, "mode": "stones2"},
        {"device_id": 9, "mode": "stones2"},
        {"device_id": True, "mode": "stones2"},
        {"device_id": "0", "mode": "stones2"},
        {"device_id": 0, "mode": "unknown"},
        {"device_id": 0, "mode": "stones2", "output_path": "/tmp/x"},
    ],
)
def test_connect_rejects_invalid_device_mode_and_paths(hardware, tmp_path, body):
    assert TestClient(make_app(tmp_path)).post(f"{PATH}/connect", json=body, headers=headers()).status_code == 422
    assert hardware == []


def test_led_mode_without_config_refuses_before_camera_open(hardware, tmp_path):
    assert (
        TestClient(make_app(tmp_path))
        .post(f"{PATH}/connect", json={"device_id": 0, "mode": "led4"}, headers=headers())
        .status_code
        == 503
    )
    assert hardware == []


@pytest.mark.parametrize("busy", [True, False])
def test_failed_open_reports_occupied_or_error_and_cleans_up(configured, monkeypatch, tmp_path, busy):
    from katrain.web.admin import vision_runtime
    from katrain.web.core.device_lease import DeviceBusy

    camera = Camera(0)

    def fail():
        raise DeviceBusy("busy") if busy else RuntimeError("open failed")

    camera.start = fail
    monkeypatch.setattr(vision_runtime, "create_camera", lambda _: camera)
    client = TestClient(make_app(tmp_path))
    result = client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
    assert result.status_code == (409 if busy else 503)
    assert client.get(f"{PATH}/status", headers=headers()).json()["camera"]["state"] == (
        "occupied" if busy else "error"
    )
    assert camera.stops == 1


def test_preview_acquires_once_bounds_jpeg_and_does_not_cache(hardware, tmp_path):
    cv2 = pytest.importorskip("cv2")
    with TestClient(make_app(tmp_path)) as client:
        client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
        result = client.get(f"{PATH}/preview", headers=headers())
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        data = result.json()
        assert data["frame_id"] and data["captured_at"]
        assert data["captured_at_source"] == "runtime_observed_at"
        assert data["camera_seq"] == 1 and data["camera_monotonic_ts"] > 0
        assert data["geometry_revision"] is None and data["warped_jpeg_base64"] is None
        image = cv2.imdecode(np.frombuffer(base64.b64decode(data["raw_jpeg_base64"]), np.uint8), cv2.IMREAD_COLOR)
        assert max(image.shape[:2]) <= 960
        assert hardware[0].reads == 1
        assert client.get(f"{PATH}/preview", headers=headers()).status_code == 429
        assert hardware[0].reads == 1


def test_unavailable_frame_is_a_real_error(hardware, tmp_path):
    client = TestClient(make_app(tmp_path))
    client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
    hardware[0].frame = None
    assert client.get(f"{PATH}/preview", headers=headers()).status_code == 503


def test_timed_out_old_preview_frame_is_rejected(hardware, tmp_path):
    client = TestClient(make_app(tmp_path))
    client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
    hardware[0].grab_fresh = lambda after_ts=None, settle_ms=0: (hardware[0].frame, 1, after_ts)
    assert client.get(f"{PATH}/preview", headers=headers()).status_code == 503


def test_preview_warps_the_same_acquired_frame(hardware, tmp_path):
    cv2 = pytest.importorskip("cv2")
    client = TestClient(make_app(tmp_path))
    client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
    runtime = client.app.state.vision_runtime
    runtime.geometry = SimpleNamespace(
        M=np.eye(3), source_width=1920, source_height=1080, out_size=1200, confidence=0.9
    )
    runtime.geometry_revision = "geometry-1"
    result = client.get(f"{PATH}/preview", headers=headers()).json()
    assert result["geometry_revision"] == "geometry-1"
    warped = cv2.imdecode(np.frombuffer(base64.b64decode(result["warped_jpeg_base64"]), np.uint8), cv2.IMREAD_COLOR)
    assert warped.shape[:2] == (960, 960)
    # Original 1200-pixel warp extends below the 1080-high camera frame; resizing must keep that margin.
    assert warped[-1].mean() < 5
    assert warped[0].mean() > 80
    assert hardware[0].reads == 1


def test_preview_errors_are_also_no_store(hardware, tmp_path):
    client = TestClient(make_app(tmp_path))
    result = client.get(f"{PATH}/preview", headers=headers())
    assert result.status_code == 409
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("outcome", ["connected", "busy", "failed"])
def test_led_connect_outcome_releases_both_devices(hardware, monkeypatch, tmp_path, outcome):
    from katrain.web.admin import vision_runtime
    from katrain.web.core.device_lease import DeviceBusy

    monkeypatch.setenv("KATRAIN_ADMIN_VISION_LED_PORT", "/dev/cu.test")
    led = Camera("/dev/cu.test")
    if outcome == "busy":

        def fail():
            raise DeviceBusy("LED owned by kiosk")

        led.start = fail
    elif outcome == "failed":
        led.is_connected = lambda: False
    monkeypatch.setattr(vision_runtime, "create_led", lambda port: led)
    with TestClient(make_app(tmp_path)) as client:
        result = client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "led4"}, headers=headers())
        assert result.status_code == {"connected": 200, "busy": 409, "failed": 503}[outcome]
        state = client.get(f"{PATH}/status", headers=headers()).json()
        assert state["led"]["state"] == {"connected": "connected", "busy": "occupied", "failed": "error"}[outcome]
    assert led.stops == 1
    assert hardware[0].stops == 1


def test_led_status_records_observed_transition_time(hardware, monkeypatch, tmp_path):
    from katrain.web.admin import vision_runtime

    monkeypatch.setenv("KATRAIN_ADMIN_VISION_LED_PORT", "/dev/cu.test")
    led = Camera("/dev/cu.test")
    monkeypatch.setattr(vision_runtime, "create_led", lambda port: led)
    observed_at = datetime(2026, 9, 26, tzinfo=timezone.utc)
    monkeypatch.setattr(vision_runtime, "_now", lambda: observed_at)
    with TestClient(make_app(tmp_path)) as client:
        connected = client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "led4"}, headers=headers()).json()
        initial_update = connected["led"]["updated_at"]
        assert connected["led"]["state"] == "connected"

        led.started = False
        observed_at += timedelta(seconds=1)
        disconnected = client.get(f"{PATH}/status", headers=headers()).json()
        assert disconnected["led"]["state"] == "disconnected"
        assert disconnected["led"]["updated_at"] == disconnected["observed_at"]
        assert disconnected["led"]["updated_at"] != initial_update

        observed_at += timedelta(seconds=1)
        unchanged = client.get(f"{PATH}/status", headers=headers()).json()
        assert unchanged["led"]["updated_at"] == disconnected["led"]["updated_at"]

        led.started = True
        observed_at += timedelta(seconds=1)
        reconnected = client.get(f"{PATH}/status", headers=headers()).json()
        assert reconnected["led"]["state"] == "connected"
        assert reconnected["led"]["updated_at"] == reconnected["observed_at"]


def test_disconnect_releases_real_camera_hub_lease(configured, monkeypatch, tmp_path):
    from katrain.web.admin import vision_runtime
    from katrain.web.core.camera_hub import CameraHub, CameraHubConfig
    from katrain.web.core.device_lease import DeviceBusy, DeviceLease

    monkeypatch.setattr("katrain.web.core.device_lease.Path.home", lambda: tmp_path)
    camera = Camera(0)
    camera.open = lambda: setattr(camera, "started", True) or True
    camera.close = camera.stop

    # CameraManager exposes a property while CameraHub exposes a method.
    class CameraAdapter:
        def open(self):
            return camera.open()

        def close(self):
            camera.close()

        @property
        def is_connected(self):
            return camera.started

    monkeypatch.setattr(
        vision_runtime, "create_camera", lambda device_id: CameraHub(CameraHubConfig(device_id), camera=CameraAdapter())
    )
    with TestClient(make_app(tmp_path)) as client:
        assert (
            client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers()).status_code
            == 200
        )
        with pytest.raises(DeviceBusy):
            DeviceLease.acquire("camera", 0)
        assert client.post(f"{PATH}/disconnect", headers=headers()).status_code == 200
        lease = DeviceLease.acquire("camera", 0)
        lease.release()


@pytest.mark.parametrize(
    "env,switch,expected",
    [("local", "1", "127.0.0.1"), ("local", "0", "0.0.0.0"), ("test", "1", "0.0.0.0"), ("prod", "1", "0.0.0.0")],
)
def test_cli_passes_actual_bind_host(configured, monkeypatch, env, switch, expected):
    from katrain.web.admin import __main__ as cli

    monkeypatch.setenv("KATRAIN_ADMIN_ENV", env)
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_LOCAL", switch)
    calls = []
    app = object()
    monkeypatch.setattr(cli, "create_admin_app", lambda **kwargs: calls.append(kwargs) or app)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    cli.main()
    assert calls == [{"bind_host": expected}, ((app,), {"host": expected, "port": 8010})]


@pytest.fixture
def calibration(monkeypatch):
    from katrain.vision.geometry_lock import GeometryLock

    lock = GeometryLock(
        corners=np.zeros((4, 2), np.float32),
        points=np.zeros((19, 19, 2), np.float32),
        xs=np.zeros(19, np.float32),
        ys=np.zeros(19, np.float32),
        M=np.eye(3),
        Minv=np.eye(3),
        out_size=950,
        baseline=np.zeros((19, 19, 3), np.float32),
        confidence=0.9,
        nmatch=18,
        source_width=1920,
        source_height=1080,
    )
    bursts = []

    def calibrate(frames):
        bursts.append(frames)
        return lock

    monkeypatch.setattr("katrain.vision.geometry_lock.lock_geometry_from_frames", calibrate)
    return lock, bursts


def test_calibration_locks_real_fresh_burst_and_preview_uses_revision(hardware, calibration, tmp_path):
    lock, bursts = calibration
    with TestClient(make_app(tmp_path)) as client:
        client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
        result = client.post(f"{PATH}/calibrate", json={"empty_confirmed": True}, headers=headers())
        assert result.status_code == 200
        geometry = result.json()
        assert geometry["state"] == "ready"
        assert geometry["revision"]
        assert geometry["confidence"] == 0.9
        assert geometry["source"] == "opencv_empty_board"
        assert len(bursts) == 1 and len(bursts[0]) == hardware[0].reads == 8
        assert all(np.array_equal(frame, hardware[0].frame) for frame in bursts[0])
        assert client.app.state.vision_runtime.geometry is lock
        assert client.get(f"{PATH}/status", headers=headers()).json()["geometry"] == geometry
        preview = client.get(f"{PATH}/preview", headers=headers()).json()
        assert preview["geometry_revision"] == geometry["revision"]
        assert preview["warped_jpeg_base64"]


@pytest.mark.parametrize("body", [{}, {"empty_confirmed": False}])
def test_calibration_requires_operator_empty_confirmation(hardware, calibration, tmp_path, body):
    client = TestClient(make_app(tmp_path))
    client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
    assert client.post(f"{PATH}/calibrate", json=body, headers=headers()).status_code == 409
    assert hardware[0].reads == 0
    assert calibration[1] == []


@pytest.mark.parametrize(
    "body", [{"empty_confirmed": "true"}, {"empty_confirmed": 1}, {"empty_confirmed": True, "path": "/tmp/x"}]
)
def test_calibration_rejects_coerced_confirmation_and_extra_fields(hardware, tmp_path, body):
    assert TestClient(make_app(tmp_path)).post(f"{PATH}/calibrate", json=body, headers=headers()).status_code == 422
    assert hardware == []


@pytest.mark.parametrize("state", ["unknown", "disconnected", "occupied"])
def test_calibration_requires_connected_camera(hardware, calibration, tmp_path, state):
    client = TestClient(make_app(tmp_path))
    client.app.state.vision_runtime._camera_state = state
    assert client.post(f"{PATH}/calibrate", json={"empty_confirmed": True}, headers=headers()).status_code == 409
    assert hardware == [] and calibration[1] == []


@pytest.mark.parametrize("failure", ["no_frame", "stale", "duplicate_seq", "duplicate_ts", "nan_ts", "disconnected"])
def test_calibration_rejects_unfresh_or_lost_burst(hardware, calibration, tmp_path, failure):
    client = TestClient(make_app(tmp_path))
    client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
    camera = hardware[0]
    first_ts = None

    def grab(after_ts=None, settle_ms=0):
        nonlocal first_ts
        camera.reads += 1
        ts = time.monotonic()
        first_ts = first_ts or ts
        if failure == "disconnected":
            camera.started = False
        return (
            None if failure == "no_frame" else camera.frame,
            1 if failure == "duplicate_seq" else camera.reads,
            {"stale": after_ts, "duplicate_ts": first_ts, "nan_ts": float("nan")}.get(failure, ts),
        )

    camera.grab_fresh = grab
    result = client.post(f"{PATH}/calibrate", json={"empty_confirmed": True}, headers=headers())
    assert result.status_code == (409 if failure == "disconnected" else 422)
    assert calibration[1] == []
    assert client.get(f"{PATH}/status", headers=headers()).json()["geometry"]["state"] == "required"


@pytest.mark.parametrize("failure", ["detection", "low_confidence", "nan_confidence", "nonempty"])
def test_failed_recalibration_preserves_existing_lock(hardware, calibration, monkeypatch, tmp_path, failure):
    client = TestClient(make_app(tmp_path))
    client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
    first = client.post(f"{PATH}/calibrate", json={"empty_confirmed": True}, headers=headers())
    assert first.status_code == 200
    runtime = client.app.state.vision_runtime
    old_lock, old_revision = runtime.geometry, runtime.geometry_revision
    from dataclasses import replace

    rejected = {
        "detection": None,
        "low_confidence": replace(old_lock, confidence=0.4),
        "nan_confidence": replace(old_lock, confidence=float("nan")),
        "nonempty": replace(old_lock, empty_black=1),
    }[failure]
    monkeypatch.setattr("katrain.vision.geometry_lock.lock_geometry_from_frames", lambda frames: rejected)
    result = client.post(f"{PATH}/calibrate", json={"empty_confirmed": True}, headers=headers())
    assert result.status_code == 422
    assert runtime.geometry is old_lock and runtime.geometry_revision == old_revision
    geometry = client.get(f"{PATH}/status", headers=headers()).json()["geometry"]
    for field in ("state", "revision", "source", "confidence"):
        assert geometry[field] == first.json()[field]
    assert geometry["error"] == result.json()["detail"]


@pytest.mark.parametrize("clear_ok", [True, False])
def test_led_calibration_clears_led_and_records_actual_opencv_source(
    hardware, calibration, monkeypatch, tmp_path, clear_ok
):
    from katrain.web.admin import vision_runtime

    monkeypatch.setenv("KATRAIN_ADMIN_VISION_LED_PORT", "/dev/cu.test")
    led = Camera("/dev/cu.test")
    led.clear = lambda strict=False: {"ok": clear_ok, "connected": True, "shown_at": time.monotonic(), "errors": []}
    monkeypatch.setattr(vision_runtime, "create_led", lambda port: led)
    client = TestClient(make_app(tmp_path))
    client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "led4"}, headers=headers())
    result = client.post(f"{PATH}/calibrate", json={"empty_confirmed": True}, headers=headers())
    assert result.status_code == (200 if clear_ok else 409)
    if clear_ok:
        assert result.json()["source"] == "opencv_empty_board"
        assert client.get(f"{PATH}/status", headers=headers()).json()["led"]["state"] == "connected"
    else:
        assert hardware[0].reads == 0 and calibration[1] == []


@pytest.mark.parametrize("stone_color", [None, (10, 10, 10), (245, 245, 245)])
def test_real_calibration_rejects_stationary_stones(hardware, tmp_path, stone_color):
    cv2 = pytest.importorskip("cv2")
    image = np.full((1400, 1800, 3), 40, np.uint8)
    image[200:1201, 400:1401] = (100, 165, 205)
    for index in range(19):
        cv2.line(image, (450, 250 + index * 50), (1350, 250 + index * 50), (30, 40, 50), 2)
        cv2.line(image, (450 + index * 50, 250), (450 + index * 50, 1150), (30, 40, 50), 2)
    if stone_color is not None:
        cv2.circle(image, (900, 700), 21, stone_color, -1)
    with TestClient(make_app(tmp_path)) as client:
        client.post(f"{PATH}/connect", json={"device_id": 0, "mode": "stones2"}, headers=headers())
        hardware[0].frame = image
        response = client.post(f"{PATH}/calibrate", json={"empty_confirmed": True}, headers=headers())
        assert response.status_code == (200 if stone_color is None else 422)
        if stone_color is not None:
            assert client.app.state.vision_runtime.geometry is None
            assert "empty" in response.json()["detail"].lower()
