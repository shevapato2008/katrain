"""In-process vision adapter for development on MacBook.

Same interface as VisionWorkerProcess but runs the pipeline directly
in-thread — no subprocess overhead, easy to debug.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

import cv2
import numpy as np

from katrain.vision.board_finder import BoardFinder
from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.camera import CameraManager
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig, CameraConfig
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand, WorkerStatus
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.move_detector import MoveDetector
from katrain.vision.stone_detector import StoneDetector
from katrain.vision.warp import adjust_M_for_resolution, warp_with_margin
from katrain.vision.sync import SyncState, SyncStateMachine

logger = logging.getLogger(__name__)

PREVIEW_SIZE = 480
PREVIEW_FPS = 3
JPEG_QUALITY = 60


class InProcessAdapter:
    """Runs the vision pipeline in a background thread (dev mode).

    Mimics the VisionWorkerProcess API so VisionService can use either.
    """

    def __init__(self, config: dict[str, Any], camera=None):
        self._config = config
        self._thread: threading.Thread | None = None
        self._running = False

        self._event_queue: queue.Queue = queue.Queue()
        self._status: WorkerStatus = WorkerStatus()
        self._preview_jpeg: bytes | None = None
        self._preview_lock = threading.Lock()

        self._cmd_queue: queue.Queue = queue.Queue()

        # Components
        board_config = BoardConfig()
        self._owns_camera = camera is None
        self._require_geometry = camera is not None
        self._camera = camera or CameraManager(device_id=config.get("camera_device", 0))
        self._motion_filter = MotionFilter()
        self._board_finder = BoardFinder(camera_config=CameraConfig())
        self._detector = StoneDetector(
            config.get("model_path", ""),
            backend=config.get("backend", "ultralytics"),
            confidence_threshold=config.get("confidence_threshold", 0.5),
        )
        self._state_extractor = BoardStateExtractor(board_config)
        # Geometry-lock warps add a 1-cell margin (matching baipu_autolabel training images), so the
        # mapping for that path needs the matching border. BoardFinder fallback keeps border 0.
        self._state_extractor_locked = BoardStateExtractor(
            BoardConfig(
                grid_size=board_config.grid_size,
                board_width_mm=board_config.board_width_mm,
                board_length_mm=board_config.board_length_mm,
                margin_cells=DEFAULT_MARGIN_CELLS,
            )
        )
        self._move_detector = MoveDetector()
        self._sync = SyncStateMachine()

        self._viewer_active = False
        self._bound = False
        self._last_preview_time = 0.0
        self._geometry = None

    def set_geometry(self, geometry) -> None:
        self._geometry = geometry

    def _warp_frame(self, frame):
        if self._geometry is not None:
            # Reconcile the live frame to the resolution M was calibrated at (no-op when they match
            # or the lock predates source_width/height), then add the same 1-cell margin the training
            # labeler uses, so serve geometry == train.
            M = adjust_M_for_resolution(
                self._geometry.M,
                (getattr(self._geometry, "source_width", None), getattr(self._geometry, "source_height", None)),
                (frame.shape[1], frame.shape[0]),
            )
            warped = warp_with_margin(frame, M, int(self._geometry.out_size), margin_cells=DEFAULT_MARGIN_CELLS)
            return warped, True
        if self._require_geometry:
            return None, False
        return self._board_finder.find_focus(frame, min_threshold=20, use_clahe=self._config.get("use_clahe", False))

    def _active_extractor(self) -> BoardStateExtractor:
        """Margin-aware extractor for the geometry-lock warp; plain (border 0) for BoardFinder."""
        return self._state_extractor_locked if self._geometry is not None else self._state_extractor

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="vision-inprocess")
        self._thread.start()
        logger.info("In-process vision adapter started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._owns_camera:
            self._camera.close()

    def send_command(self, cmd: WorkerCommand) -> None:
        self._cmd_queue.put(cmd)

    def get_event(self, timeout: float = 0) -> Any | None:
        try:
            return self._event_queue.get(timeout=timeout) if timeout > 0 else self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def get_status(self) -> WorkerStatus | None:
        return self._status

    def get_preview_jpeg(self) -> bytes | None:
        with self._preview_lock:
            jpeg = self._preview_jpeg
            self._preview_jpeg = None
            return jpeg

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        if self._owns_camera and not self._camera.open():
            logger.error("Failed to open camera")

        target_interval = 1.0 / self._config.get("capture_fps", 8)

        while self._running:
            loop_start = time.monotonic()
            self._drain_commands()

            frame = self._camera.read_frame()
            board_detected = False
            observed_board = None
            mean_confidence = 0.0

            if frame is not None and self._motion_filter.is_stable(frame):
                warped, found = self._warp_frame(frame)
                if found and warped is not None:
                    board_detected = True
                    h, w = warped.shape[:2]
                    detections = self._detector.detect(warped)
                    observed_board = self._active_extractor().detections_to_board(
                        detections, img_w=w, img_h=h, occupancy_aware=True
                    )

                    if detections:
                        mean_confidence = sum(d.confidence for d in detections) / len(detections)

                    if self._bound:
                        move_result = self._move_detector.detect_new_move(observed_board)
                        if move_result is not None:
                            row, col, color = move_result
                            self._event_queue.put(ConfirmedMove(col=col, row=row, color=color))

                    self._maybe_send_preview(warped)

            if self._bound:
                events = self._sync.update(
                    observed_board=observed_board,
                    mean_confidence=mean_confidence,
                    board_detected=board_detected,
                )
                for evt in events:
                    self._event_queue.put({"type": evt.type.value, "data": evt.data})

            self._status = WorkerStatus(
                camera_status="connected" if self._camera.is_connected else "disconnected",
                pose_lock_status=(
                    "locked" if self._sync.state not in (SyncState.UNBOUND, SyncState.CALIBRATING) else "unlocked"
                ),
                sync_state=self._sync.state.value,
                detected_board=observed_board.tolist() if observed_board is not None else None,
                camera_ready=bool(self._camera.is_connected),
                geometry_ready=self._geometry is not None or not self._require_geometry,
                model_ready=True,
                recognition_ready=bool(
                    self._camera.is_connected and (self._geometry is not None or not self._require_geometry)
                ),
            )

            elapsed = time.monotonic() - loop_start
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        if self._owns_camera:
            self._camera.close()

    def _drain_commands(self) -> None:
        while True:
            try:
                cmd: WorkerCommand = self._cmd_queue.get_nowait()
            except queue.Empty:
                break

            if cmd.action == CommandType.SHUTDOWN:
                self._running = False
            elif cmd.action == CommandType.BIND:
                self._bound = True
                self._sync.bind()
            elif cmd.action == CommandType.UNBIND:
                self._bound = False
                self._sync = SyncStateMachine()
            elif cmd.action == CommandType.CONFIRM_POSE_LOCK:
                self._sync.confirm_pose_lock()
            elif cmd.action == CommandType.SET_EXPECTED_BOARD:
                board = np.array(cmd.data["board"], dtype=int)
                self._sync.set_expected_board(board)
                self._move_detector.force_sync(board)
            elif cmd.action == CommandType.ENTER_SETUP_MODE:
                target = np.array(cmd.data["target_board"], dtype=int)
                self._sync.enter_setup_mode(target)
            elif cmd.action == CommandType.RESET_SYNC:
                self._sync.reset()
            elif cmd.action == CommandType.SET_VIEWER_ACTIVE:
                self._viewer_active = cmd.data.get("active", False)
            elif cmd.action == CommandType.SET_GEOMETRY:
                self.set_geometry(cmd.data.get("geometry"))

    def _maybe_send_preview(self, warped: np.ndarray) -> None:
        if not self._viewer_active:
            return
        now = time.monotonic()
        if now - self._last_preview_time < 1.0 / PREVIEW_FPS:
            return
        preview = cv2.resize(warped, (PREVIEW_SIZE, PREVIEW_SIZE), interpolation=cv2.INTER_LINEAR)
        _, jpeg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        with self._preview_lock:
            self._preview_jpeg = jpeg.tobytes()
        self._last_preview_time = now
