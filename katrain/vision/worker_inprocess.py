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
from katrain.vision.config import BoardConfig, CameraConfig
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand, WorkerStatus
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.move_detector import MoveDetector
from katrain.vision.stone_detector import StoneDetector
from katrain.vision.sync import SyncState, SyncStateMachine

logger = logging.getLogger(__name__)

PREVIEW_SIZE = 480
PREVIEW_FPS = 3
JPEG_QUALITY = 60


class InProcessAdapter:
    """Runs the vision pipeline in a background thread (dev mode).

    Mimics the VisionWorkerProcess API so VisionService can use either.
    """

    def __init__(self, config: dict[str, Any]):
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
        self._camera = CameraManager(device_id=config.get("camera_device", 0))
        self._motion_filter = MotionFilter()
        self._board_finder = BoardFinder(camera_config=CameraConfig())
        self._detector = StoneDetector(
            config.get("model_path", ""),
            backend=config.get("backend", "ultralytics"),
            confidence_threshold=config.get("confidence_threshold", 0.5),
        )
        self._state_extractor = BoardStateExtractor(board_config)
        self._move_detector = MoveDetector()
        self._sync = SyncStateMachine()

        self._viewer_active = False
        self._bound = False
        self._last_preview_time = 0.0

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="vision-inprocess")
        self._thread.start()
        logger.info("In-process vision adapter started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
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
        if not self._camera.open():
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
                warped, found = self._board_finder.find_focus(
                    frame, min_threshold=20, use_clahe=self._config.get("use_clahe", False)
                )
                if found and warped is not None:
                    board_detected = True
                    h, w = warped.shape[:2]
                    detections = self._detector.detect(warped)
                    observed_board = self._state_extractor.detections_to_board(detections, img_w=w, img_h=h)

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
                pose_lock_status="locked" if self._sync.state not in (SyncState.UNBOUND, SyncState.CALIBRATING) else "unlocked",
                sync_state=self._sync.state.value,
            )

            elapsed = time.monotonic() - loop_start
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

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
