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

from katrain.vision.auto_exposure import ExposureController, meter_brightness
from katrain.vision.board_finder import BoardFinder
from katrain.vision.board_state import EMPTY, BoardStateExtractor
from katrain.vision.camera import CameraManager
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig, CameraConfig
from katrain.vision.enhance import enhance_for_inference
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand, WorkerStatus
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.move_detector import AmbiguousPromoter, MoveDetector
from katrain.vision.stone_detector import StoneDetector
from katrain.vision.temporal import FrameAverager
from katrain.vision.warp import adjust_M_for_resolution, warp_with_margin
from katrain.vision.sync import SyncState, SyncStateMachine

logger = logging.getLogger(__name__)

# 960px @ q75: the browser displays the debug preview at ~1000px wide, so a 480px/q60
# stream upscales into visible mush — including the overlay boxes/labels drawn on it.
# Mac dev path only (the SBC worker.py preview keeps its own smaller settings).
PREVIEW_SIZE = 960
PREVIEW_FPS = 3
JPEG_QUALITY = 75


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
        # Hysteresis (weak-light flicker fix): the detector runs at the lower "keep"
        # threshold; board assignment requires the full "add" threshold for cells that
        # were empty in the last stable board (see BoardStateExtractor._passes_hysteresis).
        self._add_threshold = config.get("confidence_threshold", 0.5)
        self._keep_threshold = config.get("confidence_keep") or max(0.25, self._add_threshold - 0.15)
        self._enhance_mode = config.get("enhance", "clahe")
        # Static-scene rolling average (weak-light noise ~4.7x down at n=8); reset on
        # motion / geometry change / session reset so scene changes never ghost.
        self._averager = FrameAverager(config.get("frame_average", 8))
        # Software AE: board-median brightness -> target band via exposure steps.
        # Advisory-only where camera controls are inert (macOS).
        self._ae: ExposureController | None = None
        if config.get("auto_exposure", "software") == "software":
            self._ae = ExposureController(
                target_lo=config.get("ae_target_lo", 120.0), target_hi=config.get("ae_target_hi", 170.0)
            )
        self._ae_advisory = False  # set once camera controls prove ineffective
        self._last_bstats = None  # latest BrightnessStats (for the periodic log line)
        self._detector = StoneDetector(
            config.get("model_path", ""),
            backend=config.get("backend", "ultralytics"),
            confidence_threshold=self._keep_threshold,
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

        self._viewer_active = False
        self._bound = False
        self._last_preview_time = 0.0
        self._geometry = None
        self._frame_count = 0
        # 2-frame per-cell voting (ported from worker.py): a cell only updates when two
        # consecutive frames agree; otherwise it holds the last stable value.
        self._prev_observed_board: np.ndarray | None = None
        self._last_stable_board: np.ndarray | None = None

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

    def _promote_stuck_stone(self, detections, w: int, h: int, stable_board, masked) -> None:
        """Feed sub-add candidates to the promoter; emit ambiguous_stone on a hit.

        Candidates: highest detection per cell that is below the add threshold, on a
        cell empty in BOTH the stable and expected boards, and not an LED-masked cell."""
        top = self._active_extractor().cell_top(detections, img_w=w, img_h=h)
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
            return  # actuation proven inert (macOS) — brightness keeps flowing to the log
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
                    if self._ae is not None:
                        # Meter the raw warped frame (pre-average, pre-CLAHE) — the reading
                        # must reflect the actual sensor exposure, not our processing.
                        self._run_ae(meter_brightness(warped))
                    _t_enh = time.monotonic()
                    warped = self._averager.add(warped)
                    warped = enhance_for_inference(warped, self._enhance_mode)
                    _enh_ms = (time.monotonic() - _t_enh) * 1000
                    _t_inf = time.monotonic()
                    detections = self._detector.detect(warped)
                    _infer_ms = (time.monotonic() - _t_inf) * 1000
                    self._frame_count += 1
                    if self._frame_count % 30 == 0:
                        _mc = (sum(d.confidence for d in detections) / len(detections)) if detections else 0.0
                        logger.info(
                            "vision: %d stones, mean_conf=%.2f, %s enh=%.0fms infer=%.0fms, bound=%s paused=%s geom=%s",
                            len(detections),
                            _mc,
                            self._brightness_log(),
                            _enh_ms,
                            _infer_ms,
                            self._bound,
                            self._paused,
                            self._geometry is not None,
                        )
                    masked = None
                    if self._lit_points:
                        exp = self._expected_np
                        masked = {p for p in self._lit_points if exp is None or int(exp[p[0]][p[1]]) == 0}
                    observed_board = self._active_extractor().detections_to_board(
                        detections,
                        img_w=w,
                        img_h=h,
                        occupancy_aware=True,
                        masked_cells=masked,
                        prev_board=self._last_stable_board,
                        add_threshold=self._add_threshold,
                    )

                    # 2-frame per-cell voting (ported from worker.py): a cell may only
                    # change when two consecutive frames agree; disagreement holds the
                    # last stable value, absorbing single-frame flicker.
                    if self._prev_observed_board is not None and self._last_stable_board is not None:
                        stable_board = np.where(
                            observed_board == self._prev_observed_board, observed_board, self._last_stable_board
                        )
                    else:
                        stable_board = observed_board
                    self._prev_observed_board = observed_board
                    self._last_stable_board = stable_board
                    observed_board = stable_board

                    if detections:
                        mean_confidence = sum(d.confidence for d in detections) / len(detections)

                    if self._bound and not self._paused:
                        conf_map = self._active_extractor().cell_confidences(detections, img_w=w, img_h=h)
                        pending_before = self._move_detector.pending_move
                        move_result = self._move_detector.detect_new_move(observed_board)
                        if move_result is not None:
                            row, col, color = move_result
                            # A real stone that survived voting was detected in this frame or
                            # the previous one, so the two-frame lookup always finds its
                            # confidence. A confirmed cell with NO backing detection in either
                            # frame (spill-assigned or otherwise unbacked) falls to 0.0 and is
                            # routed to the ambiguous dialog — never silently injected.
                            conf = conf_map.get((row, col), self._prev_conf_map.get((row, col), 0.0))
                            if conf < self._ambiguous_confidence:
                                # PRD §3.4 row 1: low-confidence "move" asks the user instead
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
                                self._event_queue.put(ConfirmedMove(col=col, row=row, color=color))
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
                            self._promote_stuck_stone(detections, w, h, observed_board, masked)

                    self._maybe_send_preview(warped, detections)

            else:
                # Motion (or camera dropout): the scene is changing — restart the average
                # so pre-move frames never blend with the post-move board.
                self._averager.reset()

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
                self._paused = False  # defensive reset against a previous session's leftover pause
                self._sync.bind()
            elif cmd.action == CommandType.UNBIND:
                self._bound = False
                self._sync = SyncStateMachine()
                self._prev_observed_board = None  # drop voting state across sessions
                self._last_stable_board = None
                self._prev_conf_map = {}
                self._averager.reset()
                self._promoter.reset()
            elif cmd.action == CommandType.CONFIRM_POSE_LOCK:
                self._sync.confirm_pose_lock()
            elif cmd.action == CommandType.SET_EXPECTED_BOARD:
                board = np.array(cmd.data["board"], dtype=int)
                self._sync.set_expected_board(board)
                self._move_detector.force_sync(board)
                self._expected_np = board
            elif cmd.action == CommandType.ENTER_SETUP_MODE:
                target = np.array(cmd.data["target_board"], dtype=int)
                self._sync.enter_setup_mode(target)
            elif cmd.action == CommandType.RESET_SYNC:
                self._sync.reset()
                self._prev_observed_board = None  # rebuild voting baseline after recovery
                self._last_stable_board = None
                self._prev_conf_map = {}
                self._averager.reset()
                self._promoter.reset()  # declined ambiguous prompt resets sync — don't re-fire
            elif cmd.action == CommandType.SET_VIEWER_ACTIVE:
                self._viewer_active = cmd.data.get("active", False)
            elif cmd.action == CommandType.SET_GEOMETRY:
                self.set_geometry(cmd.data.get("geometry"))
                self._averager.reset()  # warp content changes with the new lock
            elif cmd.action == CommandType.PAUSE_DETECTION:
                self._paused = True
            elif cmd.action == CommandType.RESUME_DETECTION:
                self._paused = False
            elif cmd.action == CommandType.SET_LIT_POINTS:
                self._lit_points = {tuple(p) for p in cmd.data.get("points", [])}

    def _maybe_send_preview(self, warped: np.ndarray, detections: list | None = None) -> None:
        if not self._viewer_active:
            return
        now = time.monotonic()
        if now - self._last_preview_time < 1.0 / PREVIEW_FPS:
            return
        h, w = warped.shape[:2]
        preview = cv2.resize(warped, (PREVIEW_SIZE, PREVIEW_SIZE), interpolation=cv2.INTER_LINEAR)
        sx, sy = PREVIEW_SIZE / w, PREVIEW_SIZE / h
        # Debug overlay draws exactly what the pipeline ingests: the keep-threshold,
        # deduplicated detections. Green box = would ADD a new stone (>= add threshold);
        # red = keep-only (sustains an existing stone, can never add one). Re-detecting
        # at a lower threshold here previously drew boxes the pipeline never saw —
        # pure confusion, plus a wasted inference per preview frame.
        thr = self._add_threshold
        overlay_dets = detections or []
        label = {0: "B", 1: "W", 2: "R", 3: "G"}
        for d in overlay_dets:
            x1, y1, x2, y2 = d.bbox
            p1, p2 = (int(x1 * sx), int(y1 * sy)), (int(x2 * sx), int(y2 * sy))
            color = (0, 200, 0) if d.confidence >= thr else (0, 0, 235)  # BGR: green accepted, red rejected
            cv2.rectangle(preview, p1, p2, color, 2)
            cv2.putText(
                preview,
                f"{label.get(d.class_id, '?')}{d.confidence:.2f}",
                (p1[0], max(p1[1] - 4, 14)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                1,
                cv2.LINE_AA,
            )
        _, jpeg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        with self._preview_lock:
            self._preview_jpeg = jpeg.tobytes()
        self._last_preview_time = now
