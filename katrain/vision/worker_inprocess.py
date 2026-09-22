"""In-process vision adapter for development on MacBook.

Same interface as VisionWorkerProcess but runs the pipeline directly
in-thread — no subprocess overhead, easy to debug.
"""

from __future__ import annotations

import logging
import math
import os
import queue
import threading
import time
from typing import Any

import cv2
import numpy as np

from katrain.vision.auto_exposure import ExposureController, meter_brightness
from katrain.vision.board_finder import BoardFinder
from katrain.vision.board_state import EMPTY, SUSTAIN_RADIUS, BoardStateExtractor
from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig, CameraConfig
from katrain.vision.enhance import enhance_for_inference
from katrain.vision.gating import (
    mean_detection_confidence,
    move_event,
    should_detect_moves,
    should_feed_sync,
    should_feed_sync_frame,
)
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand, WorkerStatus
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.motion_roi import MotionRoiMaskCache
from katrain.vision.parallax import ParallaxParams, mount_parallax_for_lock
from katrain.vision.move_detector import (
    AmbiguousPromoter,
    MoveDetector,
    PendingConfidencePeak,
    SUSPECT_CONFIDENCE_BONUS,
)
from katrain.vision.stone_detector import StoneDetector
from katrain.vision.temporal import FrameAverager
from katrain.vision.warp import adjust_M_for_resolution, warp_with_margin
from katrain.vision.sync import SyncEventType, SyncState, SyncStateMachine

logger = logging.getLogger(__name__)

# 960px @ q75: the browser displays the debug preview at ~1000px wide, so a 480px/q60
# stream upscales into visible mush — including the overlay boxes/labels drawn on it.
# Mac dev path only (the SBC worker.py preview keeps its own smaller settings).
PREVIEW_SIZE = 960
PREVIEW_FPS = 3
JPEG_QUALITY = 75
# An unanswered low-confidence move prompt re-fires (MoveDetector no longer advances its
# baseline at confirm time), so re-emission of the ambiguous_stone event is rate-limited.
IDLE_POLL_S = 0.25  # 没人要画面时多久看一次指令队列
AMBIG_REPROMPT_FRAMES = 40  # ~4s at ~10fps
# Per-frame latency trace: `touch` this file on the box to get one "vtrace" INFO line per processed frame
# (stage timings + what the frame decided), `rm` it to stop. Checked every frame, no restart needed.
TRACE_FLAG = "/tmp/katrain-vision-trace"


class _FrameTrace:
    """Stage timer for one loop iteration; only built while TRACE_FLAG exists."""

    def __init__(self, start: float):
        self.start = self.last = start
        self.parts: list[str] = []
        self.notes: list[str] = []

    def mark(self, stage: str) -> None:
        now = time.monotonic()
        self.parts.append(f"{stage}={(now - self.last) * 1000:.0f}")
        self.last = now

    def note(self, text: str) -> None:
        self.notes.append(text)

    def emit(self) -> None:
        total = (time.monotonic() - self.start) * 1000
        logger.info(
            "vtrace wall=%.3f total=%.0f %s | %s", time.time(), total, " ".join(self.parts), " ".join(self.notes)
        )


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
        self._motion_mask_cache = MotionRoiMaskCache()
        self._last_motion_log: float | None = None
        self._last_motion_at: float | None = None
        self._last_motion_roi_ratio: float | None = None
        self._last_motion_full_ratio: float | None = None
        self._board_finder = BoardFinder(camera_config=CameraConfig())
        # Hysteresis (weak-light flicker fix): the detector runs at the lower "keep"
        # threshold; board assignment requires the full "add" threshold for cells that
        # were empty in the last stable board (see BoardStateExtractor._passes_hysteresis).
        self._add_threshold = config.get("confidence_threshold", 0.5)
        self._keep_threshold = config.get("confidence_keep") or max(0.25, self._add_threshold - 0.15)
        # Sustain tier (VisionServiceConfig.confidence_sustain): the detector runs at this lower
        # threshold, but sub-keep detections only ever reach board assignment, where they can keep
        # an existing stone alive and never add one. Absent -> keep (the pre-2026-09-22 behaviour).
        self._sustain_threshold = min(config.get("confidence_sustain") or self._keep_threshold, self._keep_threshold)
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
            confidence_threshold=self._sustain_threshold,
        )
        self._state_extractor = BoardStateExtractor(board_config)
        # Geometry-lock warps add a 1-cell margin (matching baipu_autolabel training images), so the
        # mapping for that path needs the matching border. BoardFinder fallback keeps border 0.
        # Stone parallax is calibrated in THIS warp's grid, so only this extractor may receive it.
        parallax_cfg = config.get("parallax")
        self._state_extractor_locked = BoardStateExtractor(
            BoardConfig(
                grid_size=board_config.grid_size,
                board_width_mm=board_config.board_width_mm,
                board_length_mm=board_config.board_length_mm,
                margin_cells=DEFAULT_MARGIN_CELLS,
            ),
            parallax=ParallaxParams(**parallax_cfg) if parallax_cfg else None,
        )
        # No calibration file: set_geometry derives the mount's parallax from each lock it receives.
        self._parallax_auto = bool(config.get("parallax_auto")) and not parallax_cfg
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
        # Confidence-adaptive confirmation: a stone we can already see clearly does not
        # need the full frame count. Defaults mirror VisionServiceConfig; keep them in
        # step with it (the literal here is the fallback when a caller builds a worker
        # config by hand, e.g. tests and the CLI path).
        self._fast_confirm_frames = int(self._config.get("move_confirm_fast_frames", 3))
        self._fast_confirm_confidence = float(self._config.get("move_confirm_fast_confidence", 0.70))
        self._prev_conf_map: dict = {}  # previous frame's cell confidences (flicker tolerance)
        self._conf_peak = PendingConfidencePeak()  # ambiguous gate uses the window peak, not one frame
        self._ambig_last_emit: dict = {}  # cell -> frame_count of last ambiguous prompt (cooldown)

        self._viewer_active = False
        self._bound = False
        self._monitor = False
        self._paused = False
        self._move_armed = False
        self._last_preview_time = 0.0
        self._geometry = None
        self._frame_count = 0
        # 2-frame per-cell voting (ported from worker.py): a cell only updates when two
        # consecutive frames agree; otherwise it holds the last stable value.
        self._prev_observed_board: np.ndarray | None = None
        self._last_stable_board: np.ndarray | None = None
        # Counts board OBSERVATIONS (a frame that produced a stable board), not camera
        # reads or loop iterations. Stamped onto both the published status and every
        # ConfirmedMove so a consumer can tell whether a board reading is newer than the
        # confirmation it is being used to judge.
        self._observation_seq = 0

    def set_geometry(self, geometry) -> None:
        self._geometry = geometry
        self._motion_mask_cache.invalidate()
        self._motion_filter.reset()
        if self._parallax_auto:
            params = None
            if geometry is not None:
                try:
                    params = mount_parallax_for_lock(geometry)
                except Exception:  # a lock it cannot read turns the correction off, never recognition
                    logger.warning("vision parallax off: cannot derive it from this geometry lock", exc_info=True)
            self._state_extractor_locked.parallax = params
            if params is not None:
                logger.info(
                    "vision parallax auto: nadir=(%.3f,%.3f) k=%.6f from the geometry lock",
                    params.nadir_fx,
                    params.nadir_fy,
                    params.k,
                )

    def _motion_mask(self, frame: np.ndarray) -> np.ndarray | None:
        """Return the cached board-region mask for the active geometry lock."""
        if self._geometry is None:
            return None
        return self._motion_mask_cache.get(
            frame.shape,
            getattr(self._geometry, "corners", None),
            (getattr(self._geometry, "source_width", None), getattr(self._geometry, "source_height", None)),
        )

    def _motion_diagnostic(self) -> str:
        """Format the latest region and full-frame motion ratios for periodic logs."""
        full = "N/A" if self._last_motion_full_ratio is None else f"{self._last_motion_full_ratio:.3f}"
        if self._last_motion_roi_ratio is None:
            return f"full:N/A/full:{full}"
        return f"roi:{self._last_motion_roi_ratio:.3f}/full:{full}"

    def _motion_is_stable(self, frame: np.ndarray) -> bool:
        """Apply board-region motion gating and reset the average when the scene moves."""
        stable, roi_ratio, full_ratio = self._motion_filter.is_stable_with_regions(frame, self._motion_mask(frame))
        self._last_motion_roi_ratio = roi_ratio
        self._last_motion_full_ratio = full_ratio
        if stable:
            return True

        self._averager.reset()
        now = time.monotonic()
        self._last_motion_at = now
        if self._last_motion_log is None or now - self._last_motion_log >= 5.0:
            logger.info("motion rejected: %s", self._motion_diagnostic())
            self._last_motion_log = now
        return False

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

    def _game_stone_sustain(self, weak: list, w: int, h: int) -> list:
        """The sustain-tier (below keep) detections allowed into board assignment: only those sitting within
        SUSTAIN_RADIUS of a stone the GAME has already played (the expected board). Owner rule 2026-09-22:
        the 0.20 tier exists so a played stone never reads as empty or as the other colour. The camera's
        own last stable board is not "played": a shadow read as a stone once (E1 on the RK3562) must not
        get the tier. No bound game -> no tier (tsumego / baipu monitor keep the pre-tier behaviour)."""
        exp = self._expected_np
        if not weak or exp is None or not self._bound:
            return []
        gs = exp.shape[0]
        points = self._active_extractor().detection_points(weak, img_w=w, img_h=h)
        kept = []
        for det, (fy, fx, _cls, _conf) in zip(weak, points):
            r, c = int(round(fy)), int(round(fx))
            if 0 <= r < gs and 0 <= c < gs and int(exp[r][c]) != EMPTY and math.hypot(fy - r, fx - c) <= SUSTAIN_RADIUS:
                kept.append(det)
        return kept

    def _active_extractor(self) -> BoardStateExtractor:
        """Margin-aware extractor for the geometry-lock warp; plain (border 0) for BoardFinder."""
        return self._state_extractor_locked if self._geometry is not None else self._state_extractor

    def _log_board_delta(self, before, after, detections, w: int, h: int) -> None:
        """One INFO line per stable-board change: which cells appeared/vanished and what the
        detector actually saw nearby — turns 'why did my stone drop?' into reading a log line.

        Each cell carries its nearest detection as
        <class><conf>@<distance> pl<shift>[*] (<fy_raw>,<fx_raw>)>(<fy>,<fx>): shift is how far the
        parallax correction moved it (cells; 0.00 when off), a * means the correction changed which
        intersection it rounds to — "this move was rescued by parallax" — and the coordinate pair is the
        raw -> corrected continuous (row, col) position (prd P2). The leading (r,c)<colour> token is
        unchanged: vision-recognition-stability §7 greps it."""
        pts = self._active_extractor().parallax_points(detections, img_w=w, img_h=h)
        names = {0: "B", 1: "W", 2: "R", 3: "G"}

        def near(r, c):
            best = None
            for fy_raw, fx_raw, fy, fx, cls, conf in pts:
                d = ((fy - r) ** 2 + (fx - c) ** 2) ** 0.5
                if best is None or d < best[0]:
                    best = (d, cls, conf, fy_raw, fx_raw, fy, fx)
            if best is None or best[0] > 1.0:
                return "none"
            d, cls, conf, fy_raw, fx_raw, fy, fx = best
            shift = ((fy - fy_raw) ** 2 + (fx - fx_raw) ** 2) ** 0.5
            rescued = (int(round(fy_raw)), int(round(fx_raw))) != (int(round(fy)), int(round(fx)))
            return (
                f"{names.get(cls, '?')}{conf:.2f}@{d:.2f} pl{shift:.2f}{'*' if rescued else ''} "
                f"({fy_raw:.2f},{fx_raw:.2f})>({fy:.2f},{fx:.2f})"
            )

        sym = {1: "B", 2: "W"}
        added = [
            f"({r},{c}){sym.get(int(after[r][c]), '?')}~{near(int(r), int(c))}"
            for r, c in zip(*np.where((before != after) & (after != 0)))
        ]
        removed = [
            f"({r},{c}){sym.get(int(before[r][c]), '?')}~{near(int(r), int(c))}"
            for r, c in zip(*np.where((before != after) & (after == 0)))
        ]
        logger.info("board delta: +%s -%s", added or "[]", removed or "[]")

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
        if self._move_detector.about_to_confirm:
            return  # never shift exposure on the frame that decides a confirmation
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
        request(exposure=new_exp, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
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

        was_idle = False  # 只在真的空闲过一轮之后才需要清累积;启动时它本来就是空的
        while self._running:
            loop_start = time.monotonic()
            self._drain_commands()

            if not self.needs_frames():
                # 启动器、菜单、屏幕对弈:不读帧、不做图像处理,只照常上报状态(左栏「摄像头已连接」
                # 与守卫的 recognition_ready 都读它)。RK3562 实测这条循环空转时占 katrain 的 35%。
                self._publish_status(None)
                was_idle = True
                time.sleep(IDLE_POLL_S)
                continue
            if was_idle:
                was_idle = False
                # 空闲之前攒下的观测不能和现在的画面混在一起投票。
                self._averager.reset()
                self._motion_filter.reset()
            tr = _FrameTrace(loop_start) if os.path.exists(TRACE_FLAG) else None

            frame = self._camera.read_frame()
            board_detected = False
            observed_board = None
            mean_confidence = 0.0
            if tr:
                tr.mark("read")

            motion_stable = False
            if frame is not None:
                motion_stable = self._motion_is_stable(frame)
            if tr:
                tr.mark("motion")
                tr.note(f"still={int(motion_stable)} {self._motion_diagnostic()}")

            if motion_stable:
                warped, found = self._warp_frame(frame)
                if tr:
                    tr.mark("warp")
                if found and warped is not None:
                    board_detected = True
                    h, w = warped.shape[:2]
                    if self._ae is not None:
                        # Meter the raw warped frame (pre-average, pre-CLAHE) — the reading
                        # must reflect the actual sensor exposure, not our processing.
                        self._run_ae(meter_brightness(warped))
                    if tr:
                        tr.mark("ae")
                    _t_enh = time.monotonic()
                    warped = self._averager.add(warped)
                    if tr:
                        tr.mark("avg")
                    warped = enhance_for_inference(warped, self._enhance_mode)
                    _enh_ms = (time.monotonic() - _t_enh) * 1000
                    if tr:
                        tr.mark("clahe")
                    _t_inf = time.monotonic()
                    all_detections = self._detector.detect(warped)
                    _infer_ms = (time.monotonic() - _t_inf) * 1000
                    # Sustain-tier detections (below keep) reach board assignment only on stones the game
                    # has played (_game_stone_sustain), plus the board-delta diagnostic and the preview;
                    # every other consumer sees exactly what it saw before the tier existed.
                    detections = [d for d in all_detections if d.confidence >= self._keep_threshold]
                    if tr:
                        tr.mark("detect")
                        pre, npu, post = getattr(
                            getattr(self._detector, "backend_impl", None), "last_timing_ms", (0.0, 0.0, 0.0)
                        )
                        tr.note(
                            f"det[pre={pre:.0f} npu={npu:.0f} post={post:.0f}] boxes={len(all_detections)} "
                            f"keep={len(detections)} avgN={len(getattr(self._averager, '_frames', ()))}"
                        )
                    self._frame_count += 1
                    if self._frame_count % 30 == 0:
                        _mc = (sum(d.confidence for d in detections) / len(detections)) if detections else 0.0
                        logger.info(
                            "vision: %d stones, mean_conf=%.2f, %s motion=%s enh=%.0fms infer=%.0fms, "
                            "bound=%s paused=%s geom=%s",
                            len(detections),
                            _mc,
                            self._brightness_log(),
                            self._motion_diagnostic(),
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
                    weak = [d for d in all_detections if d.confidence < self._keep_threshold]
                    observed_board = self._active_extractor().detections_to_board(
                        detections + self._game_stone_sustain(weak, w, h),
                        img_w=w,
                        img_h=h,
                        occupancy_aware=True,
                        masked_cells=masked,
                        prev_board=self._last_stable_board,
                        add_threshold=self._add_threshold,
                        sticky_board=self._prev_observed_board,
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
                    if self._last_stable_board is not None and not np.array_equal(
                        stable_board, self._last_stable_board
                    ):
                        self._log_board_delta(self._last_stable_board, stable_board, all_detections, w, h)
                    self._prev_observed_board = observed_board
                    self._last_stable_board = stable_board
                    observed_board = stable_board
                    self._observation_seq += 1
                    if tr:
                        tr.mark("assign")

                    # Confident-empty reads score 1.0 (our helper), so the tsumego "clear board" step
                    # doesn't rot into DEGRADED (which would skip the setup check and wedge clearing).
                    mean_confidence = mean_detection_confidence(detections)

                    # Outer gate = our monitor/armed/paused gate (subsumes develop's `not self._paused`).
                    # bound → develop's confidence-gated game pipeline (ambiguous dialog / ConfirmedMove);
                    # monitor (physical tsumego) → our move_event dict, no ambiguous dialog (the tsumego
                    # frontend consumes move_confirmed).
                    if should_detect_moves(
                        self._bound, self._monitor, self._paused, self._move_armed, self._sync.state.value
                    ):
                        conf_map = self._active_extractor().cell_confidences(detections, img_w=w, img_h=h)
                        pending_before = self._move_detector.pending_move
                        self._conf_peak.observe(pending_before, conf_map)
                        # `masked` (removal-lit ∩ expected-empty) can never be a new move —
                        # a leftover on a captured point is a "remove this", not a placement.
                        # Passing it here makes that protection survive the SET_EXPECTED_BOARD
                        # baseline clobber (the resync re-injection window — review wzceinjdc).
                        # Confidence-adaptive confirmation. Waiting out the frame count IS
                        # the recognition latency the user feels — nothing is computed
                        # during it — and at ~2.3 fps the full 5 frames are 1.73s. A stone
                        # the detector can already see clearly does not need that proof:
                        # measured over a real 117-move game, 80% of moves peak at >=0.70,
                        # and those confirm in 3 frames instead of 5. The peak is the
                        # window maximum (a marginal stone's per-frame value oscillates),
                        # and it is re-read every frame, so a candidate that decays back
                        # below the line loses the fast path instead of keeping it.
                        # Review Finding 6: the fast-path bar (0.70) sits ABOVE the
                        # suspect routing gate (device 0.42 + SUSPECT_CONFIDENCE_BONUS
                        # 0.25 = 0.67), so any cell that earns the shortcut here also
                        # clears the raised gate below — L2's routing gate can never
                        # divert a fast-path confirmation to the card. Both constants are
                        # frozen this round; if either moves, re-derive this relationship
                        # rather than assuming it still holds.
                        pending_peak = self._conf_peak.peak_for(self._move_detector.pending_move)
                        fast = pending_peak is not None and pending_peak >= self._fast_confirm_confidence
                        candidate_sightings = self._move_detector.count
                        selected_required_frames = (
                            self._fast_confirm_frames if fast else self._move_detector.consistency_frames
                        )
                        move_result = self._move_detector.detect_new_move(
                            observed_board,
                            ignore_cells=masked,
                            required_frames=self._fast_confirm_frames if fast else None,
                        )
                        if tr:
                            peak = "-" if pending_peak is None else f"{pending_peak:.2f}"
                            tr.note(
                                f"pend={self._move_detector.pending_move} seen={candidate_sightings + 1}/"
                                f"{selected_required_frames} peak={peak} confirmed={move_result}"
                            )
                        if move_result is not None:
                            row, col, color = move_result
                            if not self._bound:
                                # Monitor (physical tsumego): emit the confirmed move as a dict for
                                # /ws/vision and advance the baseline (develop's MoveDetector no longer
                                # self-advances) so the placed stone isn't re-detected every frame.
                                logger.info("monitor move confirmed: (%d,%d) color=%d", row, col, color)
                                self._event_queue.put(move_event(self._bound, row, col, color))
                                self._move_detector.force_sync(observed_board)
                            else:
                                # A real stone that survived voting was detected in this frame or
                                # the previous one, so the two-frame lookup always finds its
                                # confidence. A confirmed cell with NO backing detection in either
                                # frame (spill-assigned or otherwise unbacked) falls to 0.0 and is
                                # routed to the ambiguous dialog — never silently injected.
                                # The gate compares the WINDOW PEAK (a marginal stone's per-frame
                                # conf oscillates around the gate; the confirm-frame value alone
                                # made card-vs-autoplay a coin flip).
                                conf = conf_map.get((row, col), self._prev_conf_map.get((row, col), 0.0))
                                conf = self._conf_peak.gate_confidence(row, col, conf)
                                # A cell with a track record of lying must clear a
                                # higher bar before it may auto-play; it can still
                                # reach the user via the confirmation card.
                                ambiguous_gate = self._ambiguous_confidence
                                if self._move_detector.is_suspect(row, col):
                                    ambiguous_gate = min(0.95, ambiguous_gate + SUSPECT_CONFIDENCE_BONUS)
                                if conf < ambiguous_gate:
                                    # Charge the CELL, not the prompt: AMBIG_REPROMPT_FRAMES
                                    # suppresses the repeat *event*, but every suppressed
                                    # re-confirmation is still evidence this intersection keeps
                                    # producing moves nobody is willing to play. Never call this
                                    # on the auto-play branch below — that is D4's veto.
                                    self._move_detector.charge_carded_confirmation(row, col)
                                    # PRD §3.4 row 1: low-confidence "move" asks the user instead.
                                    # Baseline NOT advanced: an unanswered prompt re-fires after
                                    # the cooldown instead of silencing detection forever.
                                    if (
                                        self._frame_count - self._ambig_last_emit.get((row, col), -(10**9))
                                        >= AMBIG_REPROMPT_FRAMES
                                    ):
                                        self._ambig_last_emit[(row, col)] = self._frame_count
                                        logger.info(
                                            "move at (%d,%d) confirmed but peak conf %.2f < %.2f — ambiguous prompt; "
                                            "required_frames=%d observed_frames=%d suspicion=%d",
                                            row,
                                            col,
                                            conf,
                                            ambiguous_gate,
                                            selected_required_frames,
                                            candidate_sightings + 1,
                                            self._move_detector.suspicion_of(row, col),
                                        )
                                        self._event_queue.put(
                                            {
                                                "type": "ambiguous_stone",
                                                "data": {
                                                    "row": int(row),
                                                    "col": int(col),
                                                    "color": int(color),
                                                    "confidence": round(float(conf), 3),
                                                    # Exactly 0.0 means NO detection box backed this
                                                    # cell in either frame (see the comment above):
                                                    # the stone sits between intersections and got
                                                    # spill-assigned, or it rounded onto an occupied
                                                    # point. A merely weak stone reads 0.30-0.41.
                                                    # The two need different words on screen —
                                                    # "confirm this move?" is useless advice when the
                                                    # fix is to nudge the stone onto the line — so the
                                                    # distinction the detector already knows is
                                                    # published rather than left for the UI to guess.
                                                    "unbacked": conf <= 0.0,
                                                },
                                            }
                                        )
                                else:
                                    logger.info(
                                        "move confirmed: (%d,%d) color=%d peak_conf=%.2f "
                                        "required_frames=%d observed_frames=%d suspicion=%d",
                                        row,
                                        col,
                                        color,
                                        conf,
                                        selected_required_frames,
                                        candidate_sightings + 1,
                                        self._move_detector.suspicion_of(row, col),
                                    )
                                    self._event_queue.put(
                                        ConfirmedMove(
                                            col=col, row=row, color=color, observation_seq=self._observation_seq
                                        )
                                    )
                                    # Advance the baseline HERE (the detector no longer does):
                                    # prevents duplicate emissions until the game-update
                                    # round-trip force_syncs the new expected board. If the
                                    # poller rejects the move (out of turn / gateway), it
                                    # re-pushes the expected board, which re-arms detection
                                    # via the SET_EXPECTED_BOARD handler.
                                    self._move_detector.force_sync(observed_board)
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

                        if move_result is None and not self._move_detector.about_to_confirm:
                            self._promote_stuck_stone(detections, w, h, observed_board, masked)

                    if tr:
                        tr.mark("move")
                    self._maybe_send_preview(warped, all_detections)
                    if tr:
                        tr.mark("preview")

            elif frame is None:
                # Camera dropout has no motion-frame decision to reset the average for us.
                self._averager.reset()

            if should_feed_sync(self._bound, self._monitor, self._paused) and should_feed_sync_frame(
                frame is not None, motion_stable
            ):
                events = self._sync.update(
                    observed_board=observed_board,
                    mean_confidence=mean_confidence,
                    board_detected=board_detected,
                )
                if any(evt.type == SyncEventType.SETUP_COMPLETE for evt in events):
                    # Rebase move detection on the freshly converged board so a later
                    # arm doesn't diff against a stale baseline.
                    self._move_detector.force_sync(observed_board)
                for evt in events:
                    self._event_queue.put({"type": evt.type.value, "data": evt.data})

            self._publish_status(observed_board)
            if tr:
                tr.mark("sync")
                tr.emit()

            elapsed = time.monotonic() - loop_start
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        if self._owns_camera:
            self._camera.close()

    def needs_frames(self) -> bool:
        """有人要看棋盘才处理画面:实体对局绑定、做题/摆谱监视、摆棋准备、有人开着识别预览。"""
        return bool(
            self._bound or self._monitor or self._viewer_active or self._sync.state == SyncState.SETUP_IN_PROGRESS
        )

    def _publish_status(self, observed_board) -> None:
        self._status = WorkerStatus(
            camera_status="connected" if self._camera.is_connected else "disconnected",
            pose_lock_status=(
                "locked" if self._sync.state not in (SyncState.UNBOUND, SyncState.CALIBRATING) else "unlocked"
            ),
            sync_state=self._sync.state.value,
            detected_board=observed_board.tolist() if observed_board is not None else None,
            last_motion_at=self._last_motion_at,
            camera_ready=bool(self._camera.is_connected),
            geometry_ready=self._geometry is not None or not self._require_geometry,
            model_ready=True,
            recognition_ready=bool(
                self._camera.is_connected and (self._geometry is not None or not self._require_geometry)
            ),
            observation_seq=self._observation_seq,
        )

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
                self._motion_filter.reset()
                self._prev_observed_board = None  # drop voting state across sessions
                self._last_stable_board = None
                self._prev_conf_map = {}
                self._ambig_last_emit = {}
                self._averager.reset()
                self._promoter.reset()
                self._move_detector.reset_suspicion()  # a new session starts every cell at zero
            elif cmd.action == CommandType.CONFIRM_POSE_LOCK:
                self._sync.confirm_pose_lock()
            elif cmd.action == CommandType.SET_EXPECTED_BOARD:
                board = np.array(cmd.data["board"], dtype=int)
                unchanged = self._expected_np is not None and np.array_equal(board, self._expected_np)
                baseline_ok = self._move_detector.prev_board is not None and np.array_equal(
                    self._move_detector.prev_board, board
                )
                self._sync.set_expected_board(
                    board,
                    expected_node_id=cmd.data.get("expected_node_id"),
                )
                if not (unchanged and baseline_ok):
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
                expected = cmd.data.get("expected") if cmd.data else None
                if expected is not None:
                    # Trust-digital recovery (resync): sync compares against the digital
                    # board again, while the move detector baselines to the UNION of digital
                    # and the last physical read — so a leftover (undo/capture not lifted) or
                    # a glare-washed digital stone is already in the baseline and does NOT
                    # re-fire as a "new move" when detection resumes.
                    exp = np.array(expected, dtype=int)
                    self._sync.reset(exp)
                    base = exp
                    if self._last_stable_board is not None:
                        base = np.where(exp != EMPTY, exp, self._last_stable_board)
                    self._move_detector.force_sync(base)
                    self._expected_np = exp
                else:
                    self._sync.reset()
                    if self._last_stable_board is not None:
                        # "Ignore/reset = accept the physical board as baseline": adopt it in
                        # the move detector too, or the ignored stone re-confirms immediately.
                        self._move_detector.force_sync(self._last_stable_board)
                # Parity with worker.py RESET_SYNC (the SBC path): do NOT null the observed /
                # stable boards here. Keeping them means a leftover on a captured point stays
                # visible so the LED planner keeps its "remove" lamp burning (removal guidance
                # survives recovery); the durable `masked` skip in detect_new_move — not a
                # transient baseline — is what stops it re-injecting as a move (review wzceinjdc).
                self._prev_conf_map = {}
                self._ambig_last_emit = {}
                self._averager.reset()
                self._promoter.reset()  # declined ambiguous prompt resets sync — don't re-fire
            elif cmd.action == CommandType.SET_VIEWER_ACTIVE:
                self._viewer_active = cmd.data.get("active", False)
            elif cmd.action == CommandType.SET_GEOMETRY:
                self.set_geometry(cmd.data.get("geometry"))
                self._averager.reset()  # warp content changes with the new lock
            elif cmd.action == CommandType.SET_MONITOR:
                self._monitor = cmd.data.get("active", False)
                if not self._monitor and not self._bound:
                    self._sync = SyncStateMachine()  # Reset (mirror UNBIND)
                    self._move_armed = False
            elif cmd.action == CommandType.SET_PAUSED:
                self._paused = cmd.data.get("paused", False)
            elif cmd.action == CommandType.SET_MOVE_ARMED:
                self._move_armed = cmd.data.get("armed", False)
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
