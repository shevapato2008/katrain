"""Vision worker process — runs camera capture, inference, and sync in isolation.

On SBC this runs as a separate process to isolate vision memory from
FastAPI/Chromium. On dev machines an in-process adapter is used instead
(see worker_inprocess.py).

Architecture:
  - CameraManager: background thread continuously reads camera, holds latest frame
  - Preview thread: reads latest frame at high FPS, encodes JPEG → preview_queue
  - Processing thread (main loop): reads latest frame, runs board finder + YOLO,
    sends sync events — completely independent of preview
"""

from __future__ import annotations

import copy
import logging
import multiprocessing as mp
import queue
import threading
import time
from dataclasses import dataclass, field
from multiprocessing import Queue
from typing import Any

import cv2
import numpy as np

from katrain.vision.auto_exposure import ExposureController, meter_brightness
from katrain.vision.board_state import EMPTY, BoardStateExtractor
from katrain.vision.camera import CameraManager
from katrain.vision.config import BoardConfig, CameraConfig
from katrain.vision.enhance import enhance_for_inference
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand, WorkerStatus
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.move_detector import AmbiguousPromoter, MoveDetector
from katrain.vision.sync import SyncState, SyncStateMachine
from katrain.vision.temporal import FrameAverager

logger = logging.getLogger(__name__)

# Preview frame settings
PREVIEW_SIZE = 480
PREVIEW_FPS = 15
JPEG_QUALITY = 60
# An unanswered low-confidence move prompt re-fires (MoveDetector no longer advances its
# baseline at confirm time), so re-emission of the ambiguous_stone event is rate-limited.
AMBIG_REPROMPT_FRAMES = 40


@dataclass
class ProcessingOverlay:
    """Shared state between processing thread and preview thread."""

    board_corners: list[tuple[int, int]] | None = None  # 4 corners in raw frame coords
    detections: list | None = None  # YOLO Detection results
    warped_size: tuple[int, int] | None = None  # (w, h) of warped board
    transform_matrix: np.ndarray | None = None  # perspective transform M
    timing: dict[str, float] = field(default_factory=dict)  # ms timings


def _run_worker(
    cmd_queue: Queue,
    event_queue: Queue,
    status_queue: Queue,
    preview_queue: Queue,
    config: dict[str, Any],
) -> None:
    """Entry point for the worker process. Runs the main loop until SHUTDOWN."""
    logging.basicConfig(level=logging.INFO, format="[vision-worker] %(levelname)s %(message)s")
    w = _VisionWorkerLoop(cmd_queue, event_queue, status_queue, preview_queue, config)
    w.run()


class _VisionWorkerLoop:
    """Internal class encapsulating the worker main loop."""

    def __init__(
        self,
        cmd_queue: Queue,
        event_queue: Queue,
        status_queue: Queue,
        preview_queue: Queue,
        config: dict[str, Any],
    ):
        self._cmd_queue = cmd_queue
        self._event_queue = event_queue
        self._status_queue = status_queue
        self._preview_queue = preview_queue
        self._config = config

        self._running = False
        self._viewer_active = False
        self._bound = False

        # Initialise components
        board_config = BoardConfig()
        camera_config = CameraConfig()

        self._camera = CameraManager(
            device_id=config.get("camera_device", 0),
            width=config.get("camera_width", 1280),
            height=config.get("camera_height", 720),
            warmup_seconds=config.get("camera_warmup_seconds", 2.0),
        )
        self._motion_filter = MotionFilter()
        self._state_extractor = BoardStateExtractor(board_config)
        # Static-scene rolling average (weak-light noise ~4.7x down at n=8); reset on
        # motion / transform change / session reset so scene changes never ghost.
        self._averager = FrameAverager(config.get("frame_average", 8))
        # Software AE: board-median brightness -> target band via exposure steps.
        # Advisory-only where camera controls are inert (macOS).
        self._ae: ExposureController | None = None
        if config.get("auto_exposure", "software") == "software":
            self._ae = ExposureController(
                target_lo=config.get("ae_target_lo", 120.0), target_hi=config.get("ae_target_hi", 170.0)
            )
        self._ae_advisory = False
        self._last_bstats = None
        self._move_detector = MoveDetector(
            consistency_frames=config.get("move_confirm_frames", 3),
            miss_grace=config.get("move_miss_grace", 2),
        )
        # Sub-add promotion: a real stone stuck below the add threshold (hysteresis gives
        # it no path onto the board) persists frame after frame — promote it to an
        # ambiguous_stone confirmation prompt instead of silently ignoring it forever.
        self._promoter = AmbiguousPromoter(promote_frames=config.get("ambiguous_promote_frames", 12))
        self._sync = SyncStateMachine()

        self._paused = False
        self._lit_points: set[tuple[int, int]] = set()
        self._expected_np: np.ndarray | None = None
        self._ambiguous_confidence = self._config.get("ambiguous_confidence", 0.55)
        self._prev_conf_map: dict = {}  # previous frame's cell confidences (flicker tolerance)
        self._ambig_last_emit: dict = {}  # cell -> frame_count of last ambiguous prompt (cooldown)

        # Inference backend — lazy import so the heavy deps only load in the worker process
        self._detector = None
        self._board_finder = None

        self._last_status_time = 0.0
        self._last_detected_board: list[list[int]] | None = None
        self._board_locked = False  # When True, reuse locked transform instead of re-detecting
        self._consecutive_failures = 0  # Track detection failures for auto-unlock
        self._prev_observed_board: np.ndarray | None = None  # For temporal smoothing
        self._last_stable_board: np.ndarray | None = None
        self._frame_count = 0  # Throttle for per-gate debug logging

    def _init_inference(self) -> None:
        """Load inference backend and board finder (heavy imports)."""
        from katrain.vision.board_finder import BoardFinder
        from katrain.vision.stone_detector import StoneDetector

        backend = self._config.get("backend", "onnx")
        model_path = self._config.get("model_path", "")
        # Hysteresis (weak-light flicker fix): detector runs at the lower "keep" threshold;
        # board assignment demands the full "add" threshold for newly-occupied cells.
        self._add_threshold = self._config.get("confidence_threshold", 0.5)
        keep = self._config.get("confidence_keep") or max(0.25, self._add_threshold - 0.15)
        self._enhance_mode = self._config.get("enhance", "clahe")

        logger.info("Loading inference backend=%s model=%s", backend, model_path)
        self._detector = StoneDetector(model_path, backend=backend, confidence_threshold=keep)
        self._board_finder = BoardFinder(camera_config=CameraConfig())
        logger.info("Inference backend ready")

    def run(self) -> None:
        """Start preview thread + processing loop, then clean up."""
        self._running = True

        # Open camera
        if not self._camera.open():
            logger.error("Failed to open camera, will keep retrying")

        # Load inference backend
        try:
            self._init_inference()
        except Exception as e:
            logger.error("Failed to load inference backend: %s", e)
            self._running = False
            return

        # Shared overlay state (lock-protected)
        self._overlay = ProcessingOverlay()
        self._overlay_lock = threading.Lock()

        # Start independent preview thread
        preview_thread = threading.Thread(target=self._preview_loop, daemon=True, name="preview")
        preview_thread.start()

        # Main thread runs the processing loop (board detection + YOLO)
        self._processing_loop()

        self._camera.close()
        logger.info("Worker process exiting")

    def _processing_loop(self) -> None:
        """Processing loop: board detection + YOLO inference.
        Results written to shared overlay state for preview thread to consume."""
        while self._running:
            self._process_commands()

            frame = self._camera.read_frame()
            board_detected = False
            observed_board = None
            mean_confidence = 0.0

            self._frame_count += 1
            stable_ok = False
            if frame is None:
                if self._frame_count % 30 == 0:
                    logger.info("camera read_frame returned None (frame #%d)", self._frame_count)
            else:
                stable_ok, motion_ratio = self._motion_filter.is_stable_with_ratio(frame)
                if not stable_ok:
                    # Motion: the scene is changing — restart the average so pre-move
                    # frames never blend with the post-move board.
                    self._averager.reset()
                if not stable_ok and self._frame_count % 30 == 0:
                    logger.info(
                        "motion filter rejected frame #%d (changed_ratio=%.3f, threshold=%.3f)",
                        self._frame_count,
                        motion_ratio,
                        self._motion_filter.change_ratio_threshold,
                    )

            if stable_ok:
                # Board detection + perspective transform
                t0 = time.monotonic()

                if self._board_locked and self._board_finder.last_transform_matrix is not None:
                    # Locked mode: reuse frozen transform, skip re-detection.
                    # Auto-unlock if detection fails repeatedly (board/camera moved).
                    M = self._board_finder.last_transform_matrix
                    warp_w, warp_h = self._board_finder.last_warp_size
                    warped = cv2.warpPerspective(frame, M, (warp_w, warp_h))
                    found = True
                else:
                    warped, found = self._board_finder.find_focus(
                        frame, min_threshold=20, use_clahe=self._config.get("use_clahe", False)
                    )
                board_finder_ms = (time.monotonic() - t0) * 1000

                if found and warped is not None:
                    board_detected = True
                    self._consecutive_failures = 0
                    if self._ae is not None:
                        # Meter the raw warped frame (pre-average, pre-CLAHE) — the reading
                        # must reflect the actual sensor exposure, not our processing.
                        self._run_ae(meter_brightness(warped))
                    warped = self._averager.add(warped)
                    # Pre-inference enhancement (CLAHE: validated weak-light confidence lift)
                    warped = enhance_for_inference(warped, self._enhance_mode)
                    h, w = warped.shape[:2]

                    # YOLO inference
                    t1 = time.monotonic()
                    detections = self._detector.detect(warped)
                    yolo_ms = (time.monotonic() - t1) * 1000

                    total_ms = board_finder_ms + yolo_ms

                    # Update shared overlay state for preview thread
                    with self._overlay_lock:
                        self._overlay.board_corners = list(self._board_finder.pre_corner_point)
                        self._overlay.detections = detections
                        self._overlay.warped_size = (w, h)
                        self._overlay.transform_matrix = self._board_finder.last_transform_matrix
                        self._overlay.timing = {
                            "board_finder_ms": round(board_finder_ms, 1),
                            "yolo_ms": round(yolo_ms, 1),
                            "total_ms": round(total_ms, 1),
                        }

                    # Board state + move detection
                    masked = None
                    if self._lit_points:
                        exp = self._expected_np
                        masked = {p for p in self._lit_points if exp is None or int(exp[p[0]][p[1]]) == 0}
                    observed_board = self._state_extractor.detections_to_board(
                        detections,
                        img_w=w,
                        img_h=h,
                        occupancy_aware=True,
                        masked_cells=masked,
                        prev_board=self._last_stable_board,
                        add_threshold=self._add_threshold,
                        sticky_board=self._prev_observed_board,
                    )

                    # Temporal smoothing: require 2-frame agreement per grid position
                    if self._prev_observed_board is not None and self._last_stable_board is not None:
                        stable_board = np.where(
                            observed_board == self._prev_observed_board,
                            observed_board,
                            self._last_stable_board,
                        )
                        if not np.array_equal(stable_board, self._last_stable_board):
                            self._log_board_delta(self._last_stable_board, stable_board, detections, w, h)
                        self._last_stable_board = stable_board
                    else:
                        self._last_stable_board = observed_board
                    self._prev_observed_board = observed_board
                    self._last_detected_board = self._last_stable_board.tolist()

                    if detections:
                        mean_confidence = sum(d.confidence for d in detections) / len(detections)
                    if self._frame_count % 30 == 0:
                        logger.info(
                            "detection ok: %d stones, mean_conf=%.2f, %s board=%.0fms + yolo=%.0fms",
                            len(detections),
                            mean_confidence,
                            self._brightness_log(),
                            board_finder_ms,
                            yolo_ms,
                        )
                    if self._bound and not self._paused:
                        conf_map = self._state_extractor.cell_confidences(detections, img_w=w, img_h=h)
                        pending_before = self._move_detector.pending_move
                        move_result = self._move_detector.detect_new_move(self._last_stable_board)
                        if move_result is not None:
                            row, col, color = move_result
                            # A real stone that survived voting was detected in this frame or
                            # the previous one, so the two-frame lookup always finds its
                            # confidence. A confirmed cell with NO backing detection in either
                            # frame (spill-assigned or otherwise unbacked) falls to 0.0 and is
                            # routed to the ambiguous dialog — never silently injected.
                            conf = conf_map.get((row, col), self._prev_conf_map.get((row, col), 0.0))
                            if conf < self._ambiguous_confidence:
                                # PRD §3.4 row 1: low-confidence "move" asks the user instead.
                                # Baseline NOT advanced: an unanswered prompt re-fires after
                                # the cooldown instead of silencing detection forever.
                                if (
                                    self._frame_count - self._ambig_last_emit.get((row, col), -(10**9))
                                    >= AMBIG_REPROMPT_FRAMES
                                ):
                                    self._ambig_last_emit[(row, col)] = self._frame_count
                                    logger.info(
                                        "move at (%d,%d) confirmed but conf %.2f < %.2f — ambiguous prompt",
                                        row,
                                        col,
                                        conf,
                                        self._ambiguous_confidence,
                                    )
                                    self._event_queue.put(
                                        {
                                            "type": "ambiguous_stone",
                                            "data": {
                                                "row": int(row),
                                                "col": int(col),
                                                "color": int(color),
                                                "confidence": round(float(conf), 3),
                                            },
                                        }
                                    )
                            else:
                                logger.info(
                                    "move confirmed: (%d,%d) color=%d conf=%.2f", row, col, color, conf
                                )
                                self._event_queue.put(ConfirmedMove(col=col, row=row, color=color))
                                # Advance the baseline HERE (the detector no longer does):
                                # prevents duplicate emissions until the game-update
                                # round-trip force_syncs the new expected board. If the
                                # poller rejects the move (out of turn / gateway), it
                                # re-pushes the expected board, which re-arms detection
                                # via the SET_EXPECTED_BOARD handler.
                                self._move_detector.force_sync(self._last_stable_board)
                        else:
                            pending_after = self._move_detector.pending_move
                            if pending_after is not None and pending_after != pending_before:
                                r, c, clr = pending_after
                                # "确认中" chip (PRD §3.2/Q3): first frame of the 3-frame window
                                self._event_queue.put(
                                    {
                                        "type": "move_pending",
                                        "data": {"row": int(r), "col": int(c), "color": int(clr)},
                                    }
                                )
                        self._prev_conf_map = conf_map

                        if move_result is None and self._move_detector.pending_move is None:
                            self._promote_stuck_stone(detections, w, h, self._last_stable_board, masked)
                else:
                    # Board not found
                    self._consecutive_failures += 1
                    if self._frame_count % 30 == 0:
                        logger.info(
                            "board finder failed (frame #%d, board_finder_ms=%.0f, consecutive_failures=%d)",
                            self._frame_count,
                            board_finder_ms,
                            self._consecutive_failures,
                        )

                    # Auto-unlock if locked but detection fails 10+ times
                    # (camera or board moved out of locked position)
                    if self._board_locked and self._consecutive_failures >= 10:
                        logger.info("Auto-unlocking board (detection failed %d times)", self._consecutive_failures)
                        self._board_locked = False
                        self._board_finder.is_first = True
                        self._consecutive_failures = 0
                        self._averager.reset()  # transform will change after re-detection

                    with self._overlay_lock:
                        self._overlay.board_corners = None
                        self._overlay.detections = None
                        self._overlay.warped_size = None
                        self._overlay.transform_matrix = None
                        self._overlay.timing = {
                            "board_finder_ms": round(board_finder_ms, 1),
                        }

            # Sync state machine update
            if self._bound:
                events = self._sync.update(
                    observed_board=observed_board,
                    mean_confidence=mean_confidence,
                    board_detected=board_detected,
                )
                for evt in events:
                    self._event_queue.put({"type": evt.type.value, "data": evt.data})

            self._maybe_publish_status()
            # No throttle — processing runs as fast as inference allows

    def _log_board_delta(self, before, after, detections, w: int, h: int) -> None:
        """One INFO line per stable-board change: which cells appeared/vanished and what the
        detector actually saw nearby — turns 'why did my stone drop?' into reading a log line."""
        pts = self._state_extractor.detection_points(detections, img_w=w, img_h=h)
        names = {0: "B", 1: "W", 2: "R", 3: "G"}

        def near(r, c):
            best = None
            for fy, fx, cls, conf in pts:
                d = ((fy - r) ** 2 + (fx - c) ** 2) ** 0.5
                if best is None or d < best[0]:
                    best = (d, cls, conf)
            if best is None or best[0] > 1.0:
                return "none"
            return f"{names.get(best[1], '?')}{best[2]:.2f}@{best[0]:.2f}"

        sym = {1: "B", 2: "W"}
        added = [f"({r},{c}){sym.get(int(after[r][c]), '?')}" for r, c in zip(*np.where((before != after) & (after != 0)))]
        removed = [
            f"({r},{c}){sym.get(int(before[r][c]), '?')}~{near(int(r), int(c))}"
            for r, c in zip(*np.where((before != after) & (after == 0)))
        ]
        logger.info("board delta: +%s -%s", added or "[]", removed or "[]")

    def _promote_stuck_stone(self, detections, w: int, h: int, stable_board, masked) -> None:
        """Feed sub-add candidates to the promoter; emit ambiguous_stone on a hit.

        Candidates: highest detection per cell that is below the add threshold, on a
        cell empty in BOTH the stable and expected boards, and not an LED-masked cell."""
        top = self._state_extractor.cell_top(detections, img_w=w, img_h=h)
        exp = self._expected_np
        candidates = {
            cell: v
            for cell, v in top.items()
            if v[0] < self._add_threshold
            and int(stable_board[cell[0]][cell[1]]) == EMPTY
            and (exp is None or int(exp[cell[0]][cell[1]]) == EMPTY)
            and not (masked and cell in masked)
        }
        hit = self._promoter.step(candidates)
        if hit is None:
            return
        r, c, class_id, conf = hit
        self._event_queue.put(
            {
                "type": "ambiguous_stone",
                "data": {"row": int(r), "col": int(c), "color": int(class_id) + 1, "confidence": round(float(conf), 3)},
            }
        )
        logger.info("ambiguous promotion: sustained sub-add stone at (%d,%d) conf=%.2f", r, c, conf)

    def _brightness_log(self) -> str:
        if self._last_bstats is None or self._ae is None:
            return ""
        return f"bright={self._last_bstats.median:.0f}({self._ae.band_position(self._last_bstats)})"

    def _run_ae(self, stats) -> None:
        """One software-AE step: seed, actuate, or fall back to advisory mode."""
        self._last_bstats = stats
        if self._ae_advisory:
            return  # actuation proven inert — brightness keeps flowing to the log
        if getattr(self._camera, "controls_effective", None) is False:
            self._ae_advisory = True
            logger.info("AE: exposure controls ineffective on this platform — advisory mode only")
            return
        if self._move_detector.pending_move is not None:
            return  # never shift exposure mid move-confirmation
        if self._ae.current_exposure is None:
            self._ae.seed(getattr(self._camera, "initial_exposure", None))
        new_exp = self._ae.update(stats, time.monotonic())
        if new_exp is None:
            return
        request = getattr(self._camera, "request_controls", None)
        if request is None:
            self._ae_advisory = True
            logger.info("AE: camera has no runtime controls — advisory mode only")
            return
        request(exposure=new_exp, auto_exposure=0.25)
        self._averager.reset()  # the brightness step must not blend into the average
        logger.info("AE: median=%.0f clip=%.1f%% -> exposure %.0f", stats.median, stats.clip_frac * 100, new_exp)

    def _process_commands(self) -> None:
        """Drain the command queue (non-blocking)."""
        while True:
            try:
                cmd: WorkerCommand = self._cmd_queue.get_nowait()
            except queue.Empty:
                break

            if cmd.action == CommandType.SHUTDOWN:
                self._running = False
            elif cmd.action == CommandType.BIND:
                self._bound = True
                self._paused = False  # defensive reset against a previous session's leftover pause
                self._sync.bind()
            elif cmd.action == CommandType.UNBIND:
                self._bound = False
                self._sync = SyncStateMachine()  # Reset
                self._prev_conf_map = {}
                self._ambig_last_emit = {}
                self._averager.reset()
                self._promoter.reset()
            elif cmd.action == CommandType.CONFIRM_POSE_LOCK:
                self._board_locked = True
                logger.info("Board pose locked — reusing transform for subsequent frames")
                self._sync.confirm_pose_lock()
                self._averager.reset()  # warp switches to the frozen transform
            elif cmd.action == CommandType.SET_EXPECTED_BOARD:
                board = np.array(cmd.data["board"], dtype=int)
                unchanged = self._expected_np is not None and np.array_equal(board, self._expected_np)
                baseline_ok = self._move_detector.prev_board is not None and np.array_equal(
                    self._move_detector.prev_board, board
                )
                if not (unchanged and baseline_ok):
                    self._sync.set_expected_board(board)
                    self._move_detector.force_sync(board)
                    self._expected_np = board
                # else: analysis-stream repeat (game_updates arrive every ~0.25s while the
                # engine streams) with a clean baseline. force_syncing on every repeat reset
                # the confirmation counter faster than it could ever reach
                # move_confirm_frames — the "first move never registers" killer. A repeat
                # with a POLLUTED baseline (prev_board != expected: a confirmed move was
                # rejected downstream) still force_syncs — that is the poller's re-arm.
            elif cmd.action == CommandType.ENTER_SETUP_MODE:
                target = np.array(cmd.data["target_board"], dtype=int)
                self._sync.enter_setup_mode(target)
            elif cmd.action == CommandType.RESET_SYNC:
                self._board_locked = False
                self._board_finder.is_first = True  # Reset corner baseline
                self._sync.reset()
                if self._last_stable_board is not None:
                    # "Ignore/reset = accept the physical board as baseline": adopt it in
                    # the move detector too, or the ignored stone re-confirms immediately.
                    self._move_detector.force_sync(self._last_stable_board)
                self._prev_conf_map = {}
                self._ambig_last_emit = {}
                self._averager.reset()
                self._promoter.reset()  # declined ambiguous prompt resets sync — don't re-fire
            elif cmd.action == CommandType.SET_VIEWER_ACTIVE:
                self._viewer_active = cmd.data.get("active", False)
            elif cmd.action == CommandType.PAUSE_DETECTION:
                self._paused = True
            elif cmd.action == CommandType.RESUME_DETECTION:
                self._paused = False
            elif cmd.action == CommandType.SET_LIT_POINTS:
                self._lit_points = {tuple(p) for p in cmd.data.get("points", [])}

    def _draw_overlays(self, frame: np.ndarray, overlay: ProcessingOverlay) -> None:
        """Draw detection results and timing info on the raw camera frame."""
        h, w = frame.shape[:2]

        # 1. Board boundary (green quadrilateral)
        if overlay.board_corners:
            corners = np.array(overlay.board_corners, dtype=np.int32)
            cv2.polylines(frame, [corners.reshape((-1, 1, 2))], True, (0, 255, 0), 2)

        # 2. Stones back-projected from warped coords to raw frame
        if overlay.detections and overlay.transform_matrix is not None and overlay.warped_size:
            try:
                M_inv = np.linalg.inv(overlay.transform_matrix)
            except np.linalg.LinAlgError:
                M_inv = None
            if M_inv is not None:
                for det in overlay.detections:
                    pt = np.float32([[det.x_center, det.y_center]]).reshape(-1, 1, 2)
                    orig_pt = cv2.perspectiveTransform(pt, M_inv)
                    ox, oy = int(orig_pt[0, 0, 0]), int(orig_pt[0, 0, 1])
                    color = (0, 0, 0) if det.class_id == 0 else (255, 255, 255)
                    cv2.circle(frame, (ox, oy), 8, color, -1)
                    cv2.circle(frame, (ox, oy), 8, (0, 255, 0), 1)
                    label = f"{det.confidence:.2f}"
                    cv2.putText(
                        frame,
                        label,
                        (ox + 10, oy - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        (0, 255, 0),
                        1,
                        cv2.LINE_AA,
                    )

        # 3. Timing info (bottom-left with black background)
        if overlay.timing:
            lines = [
                f"Board: {overlay.timing.get('board_finder_ms', 0):.0f}ms",
                f"YOLO:  {overlay.timing.get('yolo_ms', 0):.0f}ms",
                f"Total: {overlay.timing.get('total_ms', 0):.0f}ms",
            ]
            y_base = h - 20
            for line in reversed(lines):
                (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (5, y_base - th - 4), (15 + tw, y_base + 4), (0, 0, 0), -1)
                cv2.putText(frame, line, (10, y_base), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                y_base -= th + 10

    @staticmethod
    def _resize_for_preview(frame: np.ndarray) -> np.ndarray:
        """Resize frame to PREVIEW_SIZE, preserving aspect ratio with letterboxing."""
        h, w = frame.shape[:2]
        scale = PREVIEW_SIZE / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        preview = np.zeros((PREVIEW_SIZE, PREVIEW_SIZE, 3), dtype=np.uint8)
        y_off, x_off = (PREVIEW_SIZE - new_h) // 2, (PREVIEW_SIZE - new_w) // 2
        preview[y_off : y_off + new_h, x_off : x_off + new_w] = resized
        return preview

    def _preview_loop(self) -> None:
        """Independent preview thread: reads latest camera frame, overlays
        detection results, encodes JPEG at high FPS."""
        interval = 1.0 / PREVIEW_FPS
        while self._running:
            if not self._viewer_active:
                time.sleep(0.1)
                continue

            frame = self._camera.read_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            # Read overlay data (non-blocking snapshot)
            with self._overlay_lock:
                overlay = copy.copy(self._overlay)

            # Draw overlays on a copy of the raw frame
            display = frame.copy()
            self._draw_overlays(display, overlay)

            # Resize and encode
            preview = self._resize_for_preview(display)
            _, jpeg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

            # Overwrite semantics: drain old frame, put new one
            try:
                self._preview_queue.get_nowait()
            except queue.Empty:
                pass
            self._preview_queue.put(jpeg.tobytes())

            time.sleep(interval)

    def _maybe_publish_status(self) -> None:
        """Publish status to main process every ~1 second."""
        now = time.monotonic()
        if now - self._last_status_time < 1.0:
            return

        status = WorkerStatus(
            camera_status="connected" if self._camera.is_connected else "disconnected",
            pose_lock_status=(
                "locked" if self._sync.state not in (SyncState.UNBOUND, SyncState.CALIBRATING) else "unlocked"
            ),
            sync_state=self._sync.state.value,
            detected_board=self._last_detected_board,
            camera_ready=bool(self._camera.is_connected),
            geometry_ready=self._board_finder.last_transform_matrix is not None,
            model_ready=self._detector is not None,
            recognition_ready=bool(self._camera.is_connected and self._detector is not None),
        )

        # Overwrite: drain old, put new
        try:
            self._status_queue.get_nowait()
        except queue.Empty:
            pass
        self._status_queue.put(status)
        self._last_status_time = now


class VisionWorkerProcess:
    """Manages the vision worker subprocess from the main process side."""

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._process: mp.Process | None = None
        self._cmd_queue: Queue = Queue()
        self._event_queue: Queue = Queue()
        self._status_queue: Queue = Queue()
        self._preview_queue: Queue = Queue(maxsize=1)

    def start(self) -> None:
        """Spawn the worker process."""
        self._process = mp.Process(
            target=_run_worker,
            args=(self._cmd_queue, self._event_queue, self._status_queue, self._preview_queue, self._config),
            daemon=True,
            name="vision-worker",
        )
        self._process.start()
        logger.info("Vision worker process started (pid=%s)", self._process.pid)

    def stop(self) -> None:
        """Send SHUTDOWN command and wait for process to exit."""
        if self._process and self._process.is_alive():
            self.send_command(WorkerCommand(action=CommandType.SHUTDOWN))
            self._process.join(timeout=5)
            if self._process.is_alive():
                logger.warning("Vision worker did not exit cleanly, terminating")
                self._process.terminate()
        self._process = None

    def send_command(self, cmd: WorkerCommand) -> None:
        """Send a command to the worker."""
        self._cmd_queue.put(cmd)

    def get_event(self, timeout: float = 0) -> Any | None:
        """Get next event from worker. Returns None if queue is empty."""
        try:
            return self._event_queue.get(timeout=timeout) if timeout > 0 else self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def get_status(self) -> WorkerStatus | None:
        """Get latest worker status (or None)."""
        status = None
        # Drain to get latest
        while True:
            try:
                status = self._status_queue.get_nowait()
            except queue.Empty:
                break
        return status

    def get_preview_jpeg(self) -> bytes | None:
        """Get latest preview JPEG (or None)."""
        try:
            return self._preview_queue.get_nowait()
        except queue.Empty:
            return None

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()
