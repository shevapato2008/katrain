"""Admin seven-stage diagnostics: explicit start/stop, one real chain, bounded snapshots, strict exclusion."""

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from katrain.vision.stone_detector import Detection
from tests.web_ui.test_admin_vision import PATH, headers, post, take, import_game  # noqa: F401 (fixtures below)
from tests.web_ui.test_admin_vision import calibration, capture_client, configured, hardware  # noqa: F401
from tests.web_ui.test_admin_vision_models import Loader, trust, write_model


class FakeAdapter:
    instances = []

    def __init__(self, config, camera):
        self.config, self.camera = config, camera
        self.observer = None
        self.commands, self.geometry = [], None
        self.started = self.stopped = False
        self.stuck = False
        FakeAdapter.instances.append(self)

    def set_geometry(self, geometry):
        self.geometry = geometry

    def send_command(self, command):
        self.commands.append(command)

    def set_observer(self, callback, interval=0.5):
        self.observer, self.interval = callback, interval

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    @property
    def is_alive(self):
        return self.started and (not self.stopped or self.stuck)


def batch(seq=7, boxes=3, size=(1080, 1920)):
    raw = np.full((*size, 3), 80, np.uint8)
    warped = np.full((1000, 1000, 3), 120, np.uint8)
    dets = [
        Detection(x_center=100 + i, y_center=200, class_id=i % 2, confidence=0.9, bbox=(90 + i, 190, 110 + i, 210))
        for i in range(boxes)
    ]
    board = np.zeros((19, 19), int)
    board[3, 3] = 1
    return {
        "kind": "batch",
        "observation_seq": seq,
        "observed_monotonic": time.monotonic(),
        "camera_seq": 100 + seq,
        "camera_ts": 1.0,
        "raw": raw,
        "pure_warped": warped,
        "input": warped,
        "contributors": (100 + seq - 2, 100 + seq - 1, 100 + seq),
        "nms": dets,
        "filtered": [(d, "keep") for d in dets[:2]],
        "img_w": 1000,
        "img_h": 1000,
        "projection": board,
        "assigned": board,
        "published": board,
        "geometry": None,
        "reference_mode": "shadow",
        "bound": False,
        "monitor": False,
    }


@pytest.fixture
def diag(capture_client):
    runtime = capture_client.app.state.vision_runtime
    FakeAdapter.instances = []
    runtime._diagnostic_adapter_factory = FakeAdapter
    root = runtime.out_dir / "models"
    root.mkdir(parents=True, exist_ok=True)
    model = write_model(root, "run-diag")
    trust(root, model)
    runtime._model_loader = Loader()
    clock = {"now": 1000.0}
    runtime._diagnostics_clock = lambda: clock["now"]
    return capture_client, runtime, model[0], clock


def dpost(client, route, **body):
    return client.post(f"{PATH}/diagnostics/{route}", json=body, headers=headers())


def dget(client, route):
    return client.get(f"{PATH}/diagnostics/{route}", headers=headers())


def test_start_needs_confirmation_and_an_active_model_and_opens_nothing_on_read(diag):
    client, runtime, model_id, _ = diag
    assert dget(client, "status").json()["state"] == "idle"
    assert dget(client, "snapshot").status_code == 404
    assert FakeAdapter.instances == []
    assert dpost(client, "start", confirmed=True).status_code == 409  # no active model
    post(client, "models/activate", model_id=model_id, confirmed=True)
    assert dpost(client, "start", confirmed=False).status_code == 409
    started = dpost(client, "start", confirmed=True)
    assert started.status_code == 200, started.text
    adapter = FakeAdapter.instances[-1]
    assert adapter.started and adapter.observer is not None and adapter.interval == pytest.approx(0.5)
    assert adapter.config["model_path"].endswith(f"{model_id}/best.pt") and adapter.config["imgsz"] == 960
    assert adapter.camera is runtime.camera and adapter.geometry is runtime.geometry
    assert [c.data for c in adapter.commands] == [{"active": True}]
    status = dget(client, "status").json()
    assert status["state"] == "running" and status["model_id"] == model_id


def test_a_snapshot_is_one_bounded_batch_with_seven_stages(diag):
    client, runtime, model_id, clock = diag
    post(client, "models/activate", model_id=model_id, confirmed=True)
    dpost(client, "start", confirmed=True)
    FakeAdapter.instances[-1].observer(batch())
    snap = dget(client, "snapshot")
    assert snap.status_code == 200 and snap.headers["cache-control"] == "no-store"
    body = snap.json()
    assert body["batch_id"] and body["camera_seq"] == 107 and body["contributors"] == [105, 106, 107]
    assert body["model_id"] == model_id and body["geometry_revision"] == runtime.geometry_revision
    assert body["stale"] is False
    stages = body["stages"]
    assert [stage["id"] for stage in stages] == [
        "raw",
        "warped",
        "nms",
        "filtered",
        "projection",
        "assigned",
        "published",
    ]
    images = body["images"]
    assert set(images) == {"raw", "warped", "input"}
    for image in images.values():
        assert max(image["width"], image["height"]) <= 960 and len(image["jpeg_base64"]) * 3 / 4 <= 1024 * 1024
    assert stages[2]["image"] == stages[3]["image"] == "input"
    assert len(stages[2]["boxes"]) == 3 and [box["tier"] for box in stages[3]["boxes"]] == ["keep", "keep"]
    assert all(0 <= box["x1"] <= 1 for box in stages[2]["boxes"])
    assert stages[4]["derived"] is True and stages[6]["board"][3 * 19 + 3] == "1"
    clock["now"] += 3.0
    assert dget(client, "snapshot").json()["stale"] is True


def test_oversized_box_lists_are_reported_unavailable_not_trimmed(diag):
    client, runtime, model_id, _ = diag
    post(client, "models/activate", model_id=model_id, confirmed=True)
    dpost(client, "start", confirmed=True)
    FakeAdapter.instances[-1].observer(batch(boxes=5000))
    stage = dget(client, "snapshot").json()["stages"][2]
    assert stage["boxes"] is None and "4096" in stage["unavailable"]


def test_running_diagnostics_block_capture_calibration_and_model_changes(diag):
    client, runtime, model_id, _ = diag
    post(client, "models/activate", model_id=model_id, confirmed=True)
    game_id = import_game(client)
    dpost(client, "start", confirmed=True)
    assert take(client, game_id).status_code == 409
    assert post(client, "calibrate", empty_confirmed=True).status_code == 409
    assert post(client, "disconnect").status_code == 409
    assert post(client, "models/activate", model_id=model_id, confirmed=True).status_code == 409
    assert dpost(client, "start", confirmed=True).status_code == 409
    assert dpost(client, "stop").json()["state"] == "idle"
    assert take(client, game_id).status_code == 200


def test_a_worker_that_will_not_exit_keeps_everything_blocked(diag):
    client, runtime, model_id, _ = diag
    post(client, "models/activate", model_id=model_id, confirmed=True)
    dpost(client, "start", confirmed=True)
    FakeAdapter.instances[-1].stuck = True
    stopped = dpost(client, "stop")
    assert stopped.status_code == 200 and stopped.json()["state"] == "stopping"
    assert post(client, "calibrate", empty_confirmed=True).status_code == 409
    assert dpost(client, "start", confirmed=True).status_code == 409
    FakeAdapter.instances[-1].stuck = False
    assert dpost(client, "stop").json()["state"] == "idle"
    assert post(client, "calibrate", empty_confirmed=True).status_code == 200


def test_viewer_uses_the_kiosk_recognition_settings_but_never_touches_exposure(diag):
    from katrain.vision.config_service import VisionServiceConfig

    client, runtime, model_id, _ = diag
    post(client, "models/activate", model_id=model_id, confirmed=True)
    dpost(client, "start", confirmed=True)
    config = FakeAdapter.instances[-1].config
    kiosk = VisionServiceConfig().to_worker_config()
    assert config["auto_exposure"] == "off"
    for key in (
        "confidence_threshold",
        "confidence_keep",
        "confidence_sustain",
        "frame_average",
        "enhance",
        "parallax_auto",
        "reference_check",
    ):
        assert config[key] == kiosk[key], key


def test_start_rechecks_the_weights_it_is_about_to_load(diag):
    client, runtime, model_id, _ = diag
    post(client, "models/activate", model_id=model_id, confirmed=True)
    best = runtime.out_dir / "models" / model_id / "best.pt"
    best.chmod(0o644)
    best.write_bytes(b"replaced after activation")
    refused = dpost(client, "start", confirmed=True)
    assert refused.status_code == 409 and FakeAdapter.instances == []


def test_led_guidance_and_session_edits_wait_for_diagnostics_too(diag):
    client, runtime, model_id, _ = diag
    post(client, "models/activate", model_id=model_id, confirmed=True)
    game_id = import_game(client)
    take(client, game_id)
    frame = take(client, game_id, 0).json()
    dpost(client, "start", confirmed=True)
    assert (
        post(client, f"sessions/{game_id}/undo", frame_id=frame["frame_id"], operator_confirmed=True).status_code == 409
    )
    assert post(client, f"sessions/{game_id}/end", operator_confirmed=True).status_code == 409
    assert post(client, "removal-guide", game_id=game_id, move_index=2).status_code == 409
