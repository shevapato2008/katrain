"""Seven-stage viewer over the one real in-process recognition chain.

Start/stop are explicit; nothing opens on a read. The viewer never binds a game, starts a monitor,
submits moves or drives LEDs. Each published snapshot is one processing batch, encoded within fixed
budgets; anything over budget is reported unavailable rather than trimmed. A worker that does not
confirm exit keeps the lab blocked instead of being forgotten.
"""

from __future__ import annotations

import base64
import threading
import time
from datetime import datetime, timezone

import numpy as np

MAX_EDGE = 960
MAX_JPEG_BYTES = 1024 * 1024
MAX_BOXES = 4096
MAX_TOTAL_BYTES = 8 * 1024 * 1024
STALE_AFTER_S = 2.0
OBSERVE_INTERVAL_S = 0.5  # <= 2 Hz

STAGES = (
    ("raw", "raw"),
    ("warped", "warped"),
    ("nms", "input"),
    ("filtered", "input"),
    ("projection", None),
    ("assigned", None),
    ("published", None),
)


class DiagnosticsError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _default_adapter(config, camera):
    from katrain.vision.worker_inprocess import InProcessAdapter

    return InProcessAdapter(config, camera=camera)


def _jpeg(image: np.ndarray) -> dict:
    """Downscale to the edge budget, then lower quality until one JPEG fits 1 MiB."""
    import cv2

    height, width = image.shape[:2]
    scale = min(1.0, MAX_EDGE / max(height, width))
    if scale < 1.0:
        image = cv2.resize(
            image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA
        )
    for quality in (85, 70, 55, 40):
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if ok and len(encoded) <= MAX_JPEG_BYTES:
            return {
                "jpeg_base64": base64.b64encode(encoded.tobytes()).decode("ascii"),
                "width": int(image.shape[1]),
                "height": int(image.shape[0]),
            }
    raise ValueError("Image exceeds the JPEG budget")


def _overlay(raw: np.ndarray, geometry) -> np.ndarray:
    """Raw anchor frame with the locked board outline (corners are in calibration resolution)."""
    import cv2

    image = raw.copy()
    corners = getattr(geometry, "corners", None)
    if corners is None:
        return image
    points = np.asarray(corners, dtype=np.float64).reshape(-1, 2)
    source_w, source_h = getattr(geometry, "source_width", None), getattr(geometry, "source_height", None)
    if source_w and source_h:
        points = points * [raw.shape[1] / source_w, raw.shape[0] / source_h]
    cv2.polylines(image, [points.astype(np.int32)], True, (104, 214, 255), max(2, raw.shape[1] // 480))
    return image


def _boxes(detections, width: int, height: int, tiers=None):
    if detections is None:
        return None, "The model's pre-dedup boxes were not exposed for this batch"
    if len(detections) > MAX_BOXES:
        return None, f"More than {MAX_BOXES} boxes; not shown rather than trimmed"
    boxes = []
    for index, det in enumerate(detections):
        x1, y1, x2, y2 = det.bbox
        box = {
            "x1": round(float(x1) / width, 5),
            "y1": round(float(y1) / height, 5),
            "x2": round(float(x2) / width, 5),
            "y2": round(float(y2) / height, 5),
            "class_id": int(det.class_id),
            "confidence": round(float(det.confidence), 4),
        }
        if tiers is not None:
            box["tier"] = tiers[index]
        boxes.append(box)
    return boxes, None


def _board(board) -> str:
    return "".join(str(int(value)) for value in np.asarray(board, dtype=int).reshape(-1))


class VisionDiagnostics:
    def __init__(self, *, adapter_factory=None, clock=time.monotonic):
        self.adapter_factory = adapter_factory or _default_adapter
        self.clock = clock
        self.lock = threading.Lock()
        self.adapter = None
        self.state = "idle"  # idle | running | stopping | error
        self.error: str | None = None
        self.context: dict | None = None
        self.latest: dict | None = None
        self.latest_at: float | None = None
        self.started_at: str | None = None

    @property
    def blocking(self) -> bool:
        """Capture, calibration, disconnect and model changes must wait while this is True."""
        return self.state in ("running", "stopping")

    def start(self, *, camera, geometry, geometry_revision: str, model_info: dict, model_path) -> dict:
        from katrain.vision.ipc import CommandType, WorkerCommand

        if self.blocking:
            raise DiagnosticsError(409, "Diagnostics are already running or still stopping")
        imgsz = int(model_info.get("parameters", {}).get("imgsz", 960))
        from katrain.vision.config_service import VisionServiceConfig

        # The chain the kiosk runs (thresholds, averaging, enhancement, parallax, reference check),
        # with this model, and without software auto-exposure: a viewer must not step the capture camera.
        config = {
            **VisionServiceConfig().to_worker_config(),
            "model_path": str(model_path),
            "backend": "ultralytics",
            "imgsz": imgsz,
            "board_size": 19,
            "auto_exposure": "off",
        }
        adapter = self.adapter_factory(config, camera)
        adapter.set_geometry(geometry)
        adapter.send_command(WorkerCommand(CommandType.SET_VIEWER_ACTIVE, {"active": True}))
        with self.lock:
            self.latest = self.latest_at = None
            self.context = {
                "model_id": model_info["id"],
                "model_sha256": model_info.get("weights_sha256"),
                "imgsz": imgsz,
                "class_names": list(model_info.get("class_names", [])),
                "geometry_revision": geometry_revision,
            }
        adapter.set_observer(self._observe, interval=OBSERVE_INTERVAL_S)
        adapter.start()
        self.adapter, self.state, self.error = adapter, "running", None
        self.started_at = datetime.now(timezone.utc).isoformat()
        return self.status()

    def stop(self) -> dict:
        """Stop and confirm the worker exited; if it is still alive, stay blocking and say so."""
        adapter = self.adapter
        if adapter is None:
            self.state = "idle"
            return self.status()
        adapter.set_observer(None)
        adapter.stop()
        if adapter.is_alive:
            self.state = "stopping"
            return self.status()
        self.adapter, self.state = None, "idle"
        return self.status()

    def _observe(self, batch: dict) -> None:
        try:
            snapshot = self._encode(batch)
        except Exception as exc:  # budgets or encoding: keep the old whole snapshot, report why
            with self.lock:
                self.error = f"Snapshot unavailable: {exc}"
            return
        with self.lock:
            self.latest, self.latest_at, self.error = snapshot, self.clock(), None

    def _encode(self, batch: dict) -> dict:
        context = self.context or {}
        images = {
            "raw": _jpeg(_overlay(batch["raw"], batch.get("geometry"))),
            "warped": _jpeg(batch["pure_warped"]),
            "input": _jpeg(batch["input"]),
        }
        width, height = batch["img_w"], batch["img_h"]
        nms_boxes, nms_missing = _boxes(batch.get("nms"), width, height)
        filtered = batch.get("filtered") or []
        kept_boxes, kept_missing = _boxes([d for d, _ in filtered], width, height, [tier for _, tier in filtered])
        stages = []
        for stage_id, image in STAGES:
            stage = {
                "id": stage_id,
                "image": image,
                "boxes": None,
                "board": None,
                "unavailable": None,
                "derived": False,
            }
            if stage_id == "nms":
                stage["boxes"], stage["unavailable"] = nms_boxes, nms_missing
            elif stage_id == "filtered":
                stage["boxes"], stage["unavailable"] = kept_boxes, kept_missing
            elif stage_id in ("projection", "assigned", "published"):
                stage["board"] = _board(batch[stage_id])
                stage["derived"] = stage_id == "projection"
            stages.append(stage)
        snapshot = {
            "batch_id": f"batch-{batch['observation_seq']}",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "camera_seq": batch.get("camera_seq"),
            "contributors": [value for value in batch.get("contributors", ()) if value is not None],
            "contributor_count": len(batch.get("contributors", ())),
            "model_id": context.get("model_id"),
            "model_sha256": context.get("model_sha256"),
            "imgsz": context.get("imgsz"),
            "class_names": context.get("class_names"),
            "geometry_revision": context.get("geometry_revision"),
            "reference_participates": bool(batch.get("bound") or batch.get("monitor")),
            "reference_mode": batch.get("reference_mode"),
            "images": images,
            "stages": stages,
        }
        if sum(len(image["jpeg_base64"]) for image in images.values()) > MAX_TOTAL_BYTES:
            raise ValueError("Snapshot exceeds the 8 MiB response budget")
        return snapshot

    def status(self) -> dict:
        with self.lock:
            age = None if self.latest_at is None else self.clock() - self.latest_at
            if self.state == "running" and self.adapter is not None and not self.adapter.is_alive:
                self.state, self.error = "error", "Recognition worker stopped unexpectedly"
            return {
                "state": self.state,
                "error": self.error,
                "started_at": self.started_at if self.state != "idle" else None,
                "model_id": (self.context or {}).get("model_id") if self.state != "idle" else None,
                "snapshot_age_s": None if age is None else round(age, 2),
            }

    def snapshot(self) -> dict:
        with self.lock:
            if self.latest is None:
                raise DiagnosticsError(404, "No diagnostic batch yet")
            age = self.clock() - self.latest_at
            return {**self.latest, "stale": age > STALE_AFTER_S or self.state != "running", "age_s": round(age, 2)}
