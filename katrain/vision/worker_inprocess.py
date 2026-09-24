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
from katrain.vision.led_geometry_calibrator import ROI_CELLS, ROI_RADIUS_MIN_PX, detect_led_centroid
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.motion_roi import MotionRoiMaskCache
from katrain.vision.parallax import ParallaxParams, mount_parallax_for_lock
from katrain.vision.reference_frame import CellSampler, ReferenceFrame, build_sampler, to_gray
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


# Frames to skip after a lamp changes before measuring its glow: the LED board shows it asynchronously.
GLOW_SETTLE_FRAMES = 2

# Reference-frame check (2026-09-23). A cell whose ZNCC against the reference is at least this counts
# as structurally unchanged -- evidence, not proof, so every veto is bounded:
REFERENCE_ZNCC = 0.90
# ... a stone the game record knows but the detector now reads as EMPTY may be held through a long
# glare (far-side white stones were measured below the keep threshold for up to 45 s). If the hold is
# wrong (the player really took that stone off), the board surfaces it after this many frames plus
# Sync's own 7 s missing hold, so keep it well under a minute.
REFERENCE_HOLD_KEEP = 90  # frames, ~36 s at 2.3 fps
# ... while everything else is held only briefly: a stone on a point the game thinks is empty (the
# reference may be the wrong one -- captured with that stone already on the board and unnoticed), and
# a colour disagreement, which board_state.py:316 already releases on its own after 15 raw frames and
# must not be re-blocked for longer than that.
REFERENCE_HOLD_SUPPRESS = 10  # frames, ~4 s at 2.3 fps
# While the game does not advance (a long think), light drifts and the reference ages out. Every this
# many seconds the next frame that passes every capture guard re-samples, cell by cell, only what still
# matches -- the current sample at REFERENCE_ZNCC and the sample from when the game last advanced at
# REFERENCE_ANCHOR_ZNCC. On the synthetic board a soft shadow edge sweeping across a cell bottoms out at
# 0.545 against the anchor while every real occupancy change measures <= 0.21, hence 0.45 (0.70 would
# refuse exactly the drift this exists for). Provisional until the board's shadow logs. See design §4.1.
REFERENCE_REFRESH_S = 60.0
REFERENCE_ANCHOR_ZNCC = 0.45
REFERENCE_MODES = ("off", "shadow", "on")


def _glow_roi(frame: np.ndarray, geometry, row: int, col: int):
    """The crop and ROI circle the lamp at (row, col) is looked for in.

    Split out so the glare probe below measures **exactly the pixels the lamp was looked for in** —
    a probe that picks its own window would answer a different question than the one that failed."""
    pts = np.asarray(geometry.points, dtype=float)
    sw, sh = getattr(geometry, "source_width", None), getattr(geometry, "source_height", None)
    sx = frame.shape[1] / sw if sw else 1.0
    sy = frame.shape[0] / sh if sh else 1.0
    here = pts[row][col]
    near = pts[row][col + 1] if col < pts.shape[1] - 1 else pts[row][col - 1]
    cx, cy = here[0] * sx, here[1] * sy
    cell = float(np.hypot((near[0] - here[0]) * sx, (near[1] - here[1]) * sy))
    radius = max(ROI_RADIUS_MIN_PX, ROI_CELLS * cell)
    x0, y0 = max(0, int(cx - radius) - 4), max(0, int(cy - radius) - 4)
    x1, y1 = min(frame.shape[1], int(cx + radius) + 5), min(frame.shape[0], int(cy + radius) + 5)
    return x0, y0, x1, y1, (cx - x0, cy - y0, radius)


def measure_led_glow(ref: np.ndarray, frame: np.ndarray, geometry, row: int, col: int):
    """Glow of the lamp at (row, col): the geometry calibrator's own lit-minus-dark blob measure
    (detect_led_centroid, same ROI rule), so `score` is in the units the calibration logs. Measured on the
    raw camera frame around the intersection (cropped, for speed); the strongest colour channel wins."""
    x0, y0, x1, y1, roi = _glow_roi(frame, geometry, row, col)
    results = [
        detect_led_centroid(ref[y0:y1, x0:x1], frame[y0:y1, x0:x1], channel=channel, roi=roi) for channel in range(3)
    ]
    # `ok` before `score`: `score` is only comparable between **successes**. `ambiguous_blobs` is the one
    # failure that carries a non-zero score (the losing blob's weight, not evidence that a lamp was found),
    # so ranking on score alone let a failed channel outrank a channel that had actually located the lamp.
    return max(results, key=lambda result: (result.ok, result.score))


CLIPPED_LEVEL = 250  # same "this pixel is blown out" level check_frame_exposure uses


def reference_clipped_fraction(ref: np.ndarray, geometry, row: int, col: int) -> float:
    """Fraction of the lamp's own ROI that was **already saturated before the lamp came on**.

    This is the glare discriminator: specular reflection pins those pixels at white in *both* frames, so
    lit-minus-dark is 0 and the lamp stays invisible however bright it gets.

    What it separates, which `reason` cannot (every one of these reads back as `low_signal`): a hand
    resting over the lamp leaves the reference dark; a lamp that never lit leaves it at ambient; a stale
    geometry lock points this ROI at ordinary board; **a stone already sitting on the lamp while the
    stable board still says EMPTY** leaves it at stone, not white — that last one matters most, because
    it is the state the 09-24 freeze was stuck in, and calling it glare would brighten straight into it.

    Reference, not lit frame: the two only disagree when the lit frame is saturated and the reference is
    not — and that cannot be glare, because the difference would then be large and the lamp would have
    been found. What it would be is the camera's exposure drifting between the two frames, which
    brightening does not fix. (A lamp bright enough to clip its own pixels is not the case being ruled
    out here: it is found, so `_measure_pending_glow` never asks this question about it.)
    """
    x0, y0, x1, y1, (rx, ry, radius) = _glow_roi(ref, geometry, row, col)
    # 每 4 个像素取一个 —— check_frame_exposure 判整帧过曝用的就是这个口径。判据问的是「有没有
    # 一片盖得住灯的高光」(阈值 2% 的 ROI,灯斑本身就有 450-2500px),降采样 16 倍仍然远大于 1 格,
    # 而全分辨率下这个探针比它旁边那个三通道测量还贵。
    step = 4
    crop = ref[y0:y1:step, x0:x1:step]
    if crop.size == 0:
        return 0.0
    keep = np.zeros(crop.shape[:2], np.uint8)
    cv2.circle(keep, (int(round(rx / step)), int(round(ry / step))), max(1, int(round(radius / step))), 1, -1)
    inside = keep.astype(bool)
    if not inside.any():
        return 0.0
    # max across BGR, not grey: a highlight that has pinned any one channel already destroys the
    # lit-minus-dark signal on that channel, and the lamp only ever shows on one channel (green/red).
    return float((crop.max(axis=2)[inside] >= CLIPPED_LEVEL).mean())


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
        # Guidance-lamp glow (ambient LED brightness loop, 2026-09-22): the raw frame from just before a lamp
        # came on is the dark reference; newly lit cells are measured once the lamp shows (led_glow event).
        self._last_raw: np.ndarray | None = None
        self._glow_ref: np.ndarray | None = None
        # Reference-frame check: the last frame whose *raw* board matched the game record, kept as
        # normalised per-cell patches in memory only -- never a file, one reference at a time.
        self._ref_mode = str(config.get("reference_check", "shadow"))
        if self._ref_mode not in REFERENCE_MODES:
            # Only argparse validates the CLI; a config dict could say "On" or "true" and silently get
            # shadow. Say so, and fall back to the mode that changes nothing.
            logger.warning("reference_check=%r is not one of %s; using 'shadow'", self._ref_mode, REFERENCE_MODES)
            self._ref_mode = "shadow"
        self._ref_sampler: CellSampler | None = None
        self._reference: ReferenceFrame | None = None
        grid = (board_config.grid_size, board_config.grid_size)
        self._ref_hold = np.zeros(grid, dtype=int)  # veto frames spent per cell, over this reference's life
        self._ref_released = np.zeros(grid, dtype=bool)  # cells whose budget ran out: no longer vetoed
        self._ref_vetoing = False  # the last check disagreed somewhere (applied in "on", logged in shadow)
        self._ref_log_frame = -1
        self._ref_taken_at = 0.0  # monotonic time of the last capture or refresh
        self._glow_pending: set[tuple[int, int]] = set()
        self._glow_wait = 0
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
        self._shadow_dropped_since_log = 0
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
        self._ref_sampler = None
        self._invalidate_reference("geometry")  # patches are tied to this warp
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

    def _invalidate_reference(self, reason: str) -> None:
        if self._reference is not None:
            logger.info("refcheck reference dropped: %s", reason)
        self._reference = None
        self._reset_reference_budget()

    def _reset_reference_budget(self) -> None:
        self._ref_hold[:] = 0
        self._ref_released[:] = False
        self._ref_vetoing = False

    def _reference_check(self, board: np.ndarray, gray: np.ndarray | None) -> np.ndarray:
        """The board to hand downstream: cells that still look exactly as they did when the board last
        matched the game record keep that value, for a bounded number of frames.

        The caller's array is board assignment's own history (_last_stable_board, and through it the
        hysteresis, the sustain tier and the colour-flip release) and is never modified: a veto fed
        back there would re-assert itself through the state it corrupted and have no way out.
        Everything downstream -- MoveDetector (including the baseline its force_sync takes after a
        confirmed move), the stuck-stone promoter, Sync, status -- consistently sees the board this
        returns; MoveDetector's baseline is re-synced to the game record on every SET_EXPECTED_BOARD.
        """
        reference = self._reference
        if reference is None or gray is None:
            return board
        sampler = reference.sampler
        if gray.shape[:2] != (sampler.img_h, sampler.img_w):  # the next capture rebuilds the sampler
            self._ref_sampler = None
            self._invalidate_reference("frame size")
            return board
        try:
            unchanged, sim = reference.unchanged(gray, REFERENCE_ZNCC)
        except Exception:  # a real bug here must be loud, and must never take recognition down with it
            logger.warning("refcheck comparison failed; dropping the reference", exc_info=True)
            self._invalidate_reference("comparison failed")
            return board
        for row, col in self._lit_points:
            unchanged[row][col] = False  # a lit lamp changes the cell's look on its own
        disagree = unchanged & (board != reference.board) & ~self._ref_released
        self._ref_vetoing = bool(disagree.any())
        if not self._ref_vetoing:
            return board
        # Counted over this reference's whole life, never reset on an agreeing frame: a detector that
        # sees the stone only every other frame would never exhaust a consecutive counter, and the
        # veto would become permanent -- exactly the failure the limit exists to prevent. A new
        # reference zeroes them.
        self._ref_hold[disagree] += 1
        # Only "the game knows a stone here and the detector now sees nothing" earns the long hold.
        # A colour disagreement gets the short one: board_state.py:316 releases a wrong colour after
        # 15 raw frames by design, and this must not quietly re-block that for half a minute.
        missing = (reference.board != EMPTY) & (board == EMPTY)
        limit = np.where(missing, REFERENCE_HOLD_KEEP, REFERENCE_HOLD_SUPPRESS)
        exhausted = disagree & (self._ref_hold > limit)
        if exhausted.any():
            # The detector has insisted on these cells for too long: it wins there, for the rest of
            # this reference's life. Only those cells -- one daylight glare often loses a stone AND
            # invents another in the same frames, and releasing the invented one must not cut the long
            # hold on the lost one. If the reference was the poisoned one (a stone already on the
            # board when it was taken), this is the exit: the real stone lands, the game moves on, and
            # the next capture replaces the reference.
            self._ref_released |= exhausted
            er, ec = np.nonzero(exhausted)
            logger.info(
                "refcheck releases %s: the detector kept disagreeing",
                ", ".join(f"({r},{c})" for r, c in zip(er.tolist(), ec.tolist())),
            )
            disagree &= ~exhausted
            self._ref_vetoing = bool(disagree.any())
            if not self._ref_vetoing:
                return board
        rows, cols = np.nonzero(disagree)
        if self._frame_count != self._ref_log_frame:
            self._ref_log_frame = self._frame_count
            shown = ", ".join(
                f"({r},{c}) board={board[r][c]} ref={reference.board[r][c]} zncc={sim[r][c]:.2f} "
                f"held={self._ref_hold[r][c]}/{limit[r][c]}"
                for r, c in list(zip(rows.tolist(), cols.tolist()))[:4]
            )
            logger.info(
                "refcheck %s %d cell(s): %s%s",
                "keeps" if self._ref_mode == "on" else "would keep",
                len(rows),
                shown,
                " ..." if len(rows) > 4 else "",
            )
        if self._ref_mode != "on":
            return board  # shadow: the same object, so nothing downstream can diverge
        effective = board.copy()
        effective[disagree] = reference.board[disagree]
        return effective

    def _maybe_capture_reference(self, board: np.ndarray, observed: np.ndarray, gray: np.ndarray | None) -> None:
        """Take a new reference only when nothing can be hiding in the picture.

        `board` is the RAW voted board and `observed` this frame's pre-vote observation; both must
        equal the game record. Requiring only the voted one is not enough: the two-frame vote holds
        the previous value on the first frame a cell changes, so the very frame a new stone appears
        still votes "empty" while `pending_move` is not set yet (MoveDetector runs later in the loop).
        That frame would photograph the stone and label its cell empty. The pre-vote board sees the
        stone immediately, so demanding both closes that window.

        Never pass the reference-corrected board here: a corrected board would let a wrong veto
        authorise its own replacement reference. Even with all of this, board == game record is
        agreement between two fallible matrices, not proof of the pixels -- REFERENCE_HOLD_SUPPRESS is
        the last line.

        Only ever called on a still frame (the loop reaches it inside its motion gate), so motion is
        not re-checked here.
        """
        expected = self._expected_np
        if (
            self._ref_mode == "off"
            or gray is None
            or not self._bound
            or self._paused
            or self._lit_points
            or expected is None
            or self._geometry is None
            or self._move_detector.pending_move is not None
            or self._ref_vetoing  # this frame's board is being corrected: don't freeze that state
            or not np.array_equal(board, expected)
            or not np.array_equal(observed, expected)
        ):
            return
        now = time.monotonic()
        if self._reference is not None and np.array_equal(self._reference.board, board):
            if now - self._ref_taken_at >= REFERENCE_REFRESH_S:
                self._refresh_reference(gray, now)
            return
        h, w = gray.shape[:2]
        if self._ref_sampler is None or (self._ref_sampler.img_w, self._ref_sampler.img_h) != (w, h):
            extractor = self._active_extractor()
            self._ref_sampler = build_sampler(w, h, extractor.config, extractor.parallax)
        self._reference = ReferenceFrame(self._ref_sampler, gray, board)
        self._ref_taken_at = now
        self._reset_reference_budget()

    def _refresh_reference(self, gray: np.ndarray, now: float) -> None:
        """Same board, a minute on: re-sample what still matches, keep the rest. Hold counts and released
        cells carry over -- a refresh must not give a poisoned reference a new life (design §4.1)."""
        self._reference, kept = self._reference.refreshed(gray, REFERENCE_ZNCC, REFERENCE_ANCHOR_ZNCC)
        self._ref_taken_at = now
        blind = ~self._reference.usable.reshape(kept.shape)  # neither frame could ever compare these
        rows, cols = np.nonzero(kept & ~blind)
        logger.info(
            "refcheck refreshed: kept %d changed cell(s) from the old reference%s%s (+%d that cannot be compared)",
            len(rows),
            ": " if len(rows) else "",
            ", ".join(f"({r},{c})" for r, c in list(zip(rows.tolist(), cols.tolist()))[:6])
            + (" ..." if len(rows) > 6 else ""),
            int((kept & blind).sum()),
        )

    def _measure_pending_glow(self, frame: np.ndarray) -> None:
        """Measure each newly lit lamp that is still a bare lamp (no stone on the camera's board there) and
        report it as a led_glow event. The AI's move is already on the expected board while its lamp waits
        for the player, so only the camera's own board decides "bare"."""
        cells, self._glow_pending = self._glow_pending, set()
        ref, geometry, stable = self._glow_ref, self._geometry, self._last_stable_board
        if ref is None or geometry is None or getattr(geometry, "points", None) is None or ref.shape != frame.shape:
            return
        readings = []
        for row, col in sorted(cells):
            if stable is not None and int(stable[row][col]) != EMPTY:
                continue
            result = measure_led_glow(ref, frame, geometry, row, col)
            clipped = 0.0 if result.ok else reference_clipped_fraction(ref, geometry, row, col)
            readings.append((row, col, result, clipped))
        if not readings:
            return
        # **一次观测只发一个读数。** 补多手时(lag 恢复:`to_place` 里有几手就点几盏)这一批灯全是在
        # 同一帧、同一个亮度下量出来的 —— 它们是一次观测的 N 个样本,不是 N 次观测。原来逐个发出去,
        # 服务端就把同一个偏差修正了 N 遍,每一遍还乘在上一遍改过的亮度上:实测 6 盏 4x 偏亮的读数把
        # 亮度从 1.0 一路打到 0.08 地板(正确答案是 0.5),第 3 盏就已经暗到人看不见灯了。
        # 挑法:有测到灯的就用**最亮的那个干净读数**;全都没测到,就用**最像反光的那个**(过曝比例最高)。
        if any(result.ok for _r, _c, result, _clip in readings):
            row, col, result, clipped = max((r for r in readings if r[2].ok), key=lambda r: r[2].score)
        else:
            row, col, result, clipped = max(readings, key=lambda r: r[3])
        if len(readings) > 1:
            logger.info(
                "led_glow batch of %d, steering on (%s,%s): %s",
                len(readings),
                row,
                col,
                " ".join(
                    f"({r},{c})={'ok' if x.ok else x.reason}:{x.score:.0f}/clip{clip:.3f}" for r, c, x, clip in readings
                ),
            )
        self._event_queue.put(
            {
                "type": "led_glow",
                "data": {
                    "row": int(row),
                    "col": int(col),
                    "ok": bool(result.ok),
                    "score": round(float(result.score), 1),
                    "peak": round(float(result.peak), 1),
                    "area": int(result.area),
                    "reason": str(getattr(result, "reason", "") or ""),  # 诊断用,**不**作判据 —— 见下
                    # 反光判据。`reason` 当不了这个判据:白灯纯绿 (0,255,0)、黑灯纯红,BGR 的通道 0(蓝)
                    # 按构造就没有灯信号,必然 peak<PEAK_MIN_ROI 返回 low_signal 且 score=0.0;三通道全失败时
                    # score 全是 0.0,max 返回第一个 ⇒ **reason 恒为蓝通道的 low_signal**。于是反光、手挡住、
                    # 串口掉线、几何锁过期、整帧过曝全读成同一个字符串。真正分得开的是这个数。
                    "clipped": round(float(clipped), 4),
                },
            }
        )

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
            if self._glow_pending and frame is not None and motion_stable:
                if self._glow_wait > 0:
                    self._glow_wait -= 1
                else:
                    self._measure_pending_glow(frame)
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
                    # Reference-frame check runs on the warped frame BEFORE the averager and BEFORE
                    # CLAHE -- see to_gray's docstring for why either one would break it.
                    ref_gray = to_gray(warped) if self._ref_mode != "off" and self._bound and not self._paused else None
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
                    # A stone's shadow boxed a second time (side light) is dropped before the keep/sustain split,
                    # so no consumer -- board assignment, the sustain tier, the ambiguous-move promoter -- sees it.
                    _n_boxes = len(all_detections)
                    all_detections = self._active_extractor().drop_shadow_boxes(all_detections, w, h)
                    _shadow_dropped = _n_boxes - len(all_detections)
                    self._shadow_dropped_since_log += _shadow_dropped
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
                            f"shadow={_shadow_dropped} keep={len(detections)} "
                            f"avgN={len(getattr(self._averager, '_frames', ()))}"
                        )
                    self._frame_count += 1
                    if self._frame_count % 30 == 0:
                        _mc = (sum(d.confidence for d in detections) / len(detections)) if detections else 0.0
                        logger.info(
                            "vision: %d stones, mean_conf=%.2f, shadow=%d, %s motion=%s enh=%.0fms infer=%.0fms, "
                            "bound=%s paused=%s geom=%s",
                            len(detections),
                            _mc,
                            self._shadow_dropped_since_log,
                            self._brightness_log(),
                            self._motion_diagnostic(),
                            _enh_ms,
                            _infer_ms,
                            self._bound,
                            self._paused,
                            self._geometry is not None,
                        )
                        self._shadow_dropped_since_log = 0
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
                    raw_observation = observed_board  # pre-vote, needed by the capture guard
                    self._prev_observed_board = observed_board
                    self._last_stable_board = stable_board
                    if tr:
                        tr.mark("assign")
                    observed_board = self._reference_check(stable_board, ref_gray)
                    self._maybe_capture_reference(stable_board, raw_observation, ref_gray)
                    if tr:
                        tr.mark("refchk")
                    self._observation_seq += 1

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
            if frame is not None:
                self._last_raw = frame
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
                self._invalidate_reference("bind")
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
                self._invalidate_reference("unbind")
            elif cmd.action == CommandType.CONFIRM_POSE_LOCK:
                self._sync.confirm_pose_lock()
            elif cmd.action == CommandType.SET_EXPECTED_BOARD:
                board = np.array(cmd.data["board"], dtype=int)
                unchanged = self._expected_np is not None and np.array_equal(board, self._expected_np)
                if self._reference is not None and not np.array_equal(board, self._reference.board):
                    # The reference stays valid only while the game moved FORWARD from the position it
                    # shows: every stone it holds is still there in the same colour, and at most one
                    # new stone appeared. Undo, navigation to a sibling, a new game and an undone
                    # capture all take a stone away from that position, so they drop it. The
                    # orchestrator re-sends the same expected board off game state
                    # (physical_play_orchestrator.py:160), several times a second while the engine
                    # streams: a re-send must keep the reference, which this rule does (kept, zero
                    # added). Do NOT "simplify" it to `added != 1` -- that drops the reference on every
                    # re-send and the feature would silently never hold anything. The equality check
                    # above only skips the arithmetic.
                    # Known and accepted: a setup edit that only adds one stone looks like a move
                    # here. The capture guards and REFERENCE_HOLD_SUPPRESS bound that case.
                    ref_board = self._reference.board
                    kept = bool(np.all((ref_board == EMPTY) | (board == ref_board)))
                    added = int(((ref_board == EMPTY) & (board != EMPTY)).sum())
                    if not kept or added > 1:
                        self._invalidate_reference("expected board is no longer a move ahead")
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
                self._invalidate_reference("setup mode")
            elif cmd.action == CommandType.RESET_SYNC:
                self._invalidate_reference("resync")
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
                if self._paused:
                    self._invalidate_reference("paused")
            elif cmd.action == CommandType.SET_MOVE_ARMED:
                self._move_armed = cmd.data.get("armed", False)
            elif cmd.action == CommandType.PAUSE_DETECTION:
                self._paused = True
                self._invalidate_reference("paused")
            elif cmd.action == CommandType.RESUME_DETECTION:
                self._paused = False
            elif cmd.action == CommandType.SET_LIT_POINTS:
                lit = {tuple(p) for p in cmd.data.get("points", [])}
                if lit - self._lit_points:
                    # A lamp just came on: the last frame read before this command is its dark reference.
                    self._glow_ref = self._last_raw
                    self._glow_pending = lit - self._lit_points
                    self._glow_wait = GLOW_SETTLE_FRAMES
                elif not lit:
                    self._glow_ref, self._glow_pending = None, set()
                self._lit_points = lit

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
