"""Camera lifecycle manager for Go board visual recognition on SBC devices."""

from __future__ import annotations

import glob
import logging
import os
import sys
import threading
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _device_to_capture_arg(device_id: int | str) -> str | int:
    """Convert device ID to the argument for cv2.VideoCapture.

    On Linux with high device numbers (e.g. /dev/video73 for USB cameras on
    Rockchip SBCs), OpenCV's V4L2 backend can't open by integer index.
    Using the path string with CAP_ANY (auto backend selection) works reliably.
    """
    if isinstance(device_id, str):
        return device_id  # Already a path like "/dev/video73"
    if sys.platform == "linux" and device_id > 9:
        return f"/dev/video{device_id}"
    return device_id


def _get_camera_name(device_id: int | str) -> str | None:
    """Read the V4L2 device name from sysfs (Linux only).

    Returns e.g. "USB Camera: USB Camera" or a model-specific string.
    This name is stable across reconnections for the same physical device.
    """
    if sys.platform != "linux":
        return None
    if isinstance(device_id, str):
        dev_num = device_id.replace("/dev/video", "")
    else:
        dev_num = str(device_id)
    try:
        with open(f"/sys/class/video4linux/video{dev_num}/name") as f:
            return f.read().strip()
    except OSError:
        return None


def _find_device_by_name(name: str, original_id: int | str) -> int | None:
    """Scan all /dev/video* devices to find one matching *name*.

    Skips the original device ID (already known to be gone).
    Returns the device number, or None if not found.
    """
    if sys.platform != "linux":
        return None
    orig_num = str(original_id).replace("/dev/video", "")
    for entry in sorted(glob.glob("/sys/class/video4linux/video*")):
        dev_num = entry.rsplit("video", 1)[-1]
        if dev_num == orig_num:
            continue
        try:
            with open(os.path.join(entry, "name")) as f:
                dev_name = f.read().strip()
            if dev_name == name and os.path.exists(f"/dev/video{dev_num}"):
                return int(dev_num)
        except (OSError, ValueError):
            continue
    return None


class CameraManager:
    """Manages a single camera with a background reader thread.

    A dedicated thread continuously reads frames from the camera, ensuring
    that ``read_frame()`` always returns the **latest** frame rather than a
    stale buffered one.  This is critical on SBCs where heavy processing
    (YOLO inference ~600ms) causes OpenCV's internal buffer to fill up.
    """

    RECONNECT_COOLDOWN = 5.0  # seconds between reconnect attempts

    def __init__(
        self,
        device_id: int | str = 0,
        width: int = 1280,
        height: int = 720,
        warmup_seconds: float = 2.0,
        lock_exposure: bool = False,
        exposure: float | None = None,
        lock_awb: bool = False,
    ) -> None:
        """Initialize with device ID (int) or path (e.g. "/dev/video73").

        ``lock_exposure``/``lock_awb`` disable auto exposure / white balance so a
        lit LED can't trigger global auto-darkening that crushes black stones into
        the background (plan §3.1). ``exposure`` is the fixed manual value; it is
        camera-specific (V4L2 has no portable scale) and is calibrated on the box.
        """
        self._device_id = device_id
        self._capture_arg = _device_to_capture_arg(device_id)
        self._width = width
        self._height = height
        self._warmup_seconds = warmup_seconds
        self._lock_exposure = lock_exposure
        self._exposure = exposure
        self._lock_awb = lock_awb
        self._cap: cv2.VideoCapture | None = None
        self._connected = False
        self._last_reconnect_attempt = 0.0
        self._camera_name: str | None = None  # V4L2 device name for reconnection
        # Background reader thread state
        self._reader_thread: threading.Thread | None = None
        self._latest_frame: np.ndarray | None = None
        self._frame_seq = 0  # increments per frame read (under _frame_lock)
        self._frame_ts = 0.0  # time.monotonic() when the frame was read
        self._frame_lock = threading.Lock()
        # Runtime camera controls (software AE): requests are queued here and applied
        # by the reader thread between reads — cv2.VideoCapture is not thread-safe.
        self._pending_controls: dict[str, float] = {}
        self._controls_lock = threading.Lock()
        self._controls_effective: bool | None = None  # None = never attempted
        self._initial_exposure: float | None = None  # readback at open()
        self._stop_event = threading.Event()

    @property
    def is_connected(self) -> bool:
        """Whether the camera is currently open and readable."""
        return self._connected and self._cap is not None and self._cap.isOpened()

    def open(self) -> bool:
        """Open the camera device and start the background reader thread."""
        self.close()
        cap = cv2.VideoCapture(self._capture_arg)
        if cap.isOpened():
            # Use MJPEG to reduce USB bandwidth (critical for USB cameras on SBC)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc_raw = int(cap.get(cv2.CAP_PROP_FOURCC))
            fourcc_str = "".join(chr((fourcc_raw >> (8 * i)) & 0xFF) for i in range(4))
            logger.info(
                "Camera %s opened: %dx%d format=%s (threaded reader)",
                self._device_id,
                actual_w,
                actual_h,
                fourcc_str,
            )

            # Record V4L2 device name for reconnection after device renumbering
            if self._camera_name is None:
                self._camera_name = _get_camera_name(self._device_id)
                if self._camera_name:
                    logger.info("Camera identity recorded: %r", self._camera_name)

            # Enable auto-focus if supported
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

            # Optionally lock exposure / white balance for capture (plan §3.1).
            # CAP_PROP_AUTO_EXPOSURE=0.25 is the V4L2 "manual" sentinel; the exact
            # value is backend/camera-specific and tuned on the box.
            if self._lock_exposure:
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                if self._exposure is not None:
                    cap.set(cv2.CAP_PROP_EXPOSURE, self._exposure)
            # White balance: only DISABLE auto-WB when explicitly locking (plan §3.1). The SBC's
            # HBV UVC camera has no working manual WB — disabling auto-WB leaves a ~3x red cast
            # (manual white_balance_temperature=4600 does not neutralize). So the default is
            # auto-WB ON. V4L2 control state PERSISTS across processes, so when NOT locking we must
            # explicitly (re)enable auto-WB — otherwise a camera a prior run left at AUTO_WB=0
            # stays red after restart. (macOS AVFoundation silently ignores this control.)
            if self._lock_awb:
                cap.set(cv2.CAP_PROP_AUTO_WB, 0)
            else:
                cap.set(cv2.CAP_PROP_AUTO_WB, 1)
            try:
                self._initial_exposure = float(cap.get(cv2.CAP_PROP_EXPOSURE))  # AE seed value
            except cv2.error:
                self._initial_exposure = None

            # Drain frames to let auto-focus and auto-exposure settle
            if self._warmup_seconds > 0:
                deadline = time.monotonic() + self._warmup_seconds
                while time.monotonic() < deadline:
                    cap.read()
                logger.info("Camera %s focus stabilized (%.1fs warmup)", self._device_id, self._warmup_seconds)

            self._cap = cap
            self._connected = True

            # Start background reader thread
            self._stop_event.clear()
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True, name="cam-reader")
            self._reader_thread.start()
            return True
        cap.release()
        logger.warning("Failed to open camera %s", self._device_id)
        return False

    def close(self) -> None:
        """Stop the reader thread and release the camera device."""
        self._stop_event.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)
            self._reader_thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            self._connected = False
            with self._frame_lock:
                self._latest_frame = None
            logger.info("Camera %s closed", self._device_id)

    def read_frame(self) -> np.ndarray | None:
        """Return the latest frame captured by the background thread.

        Always returns the freshest available frame, never a stale buffered
        one.  Returns None if the camera is disconnected.
        """
        if not self._connected:
            return self._try_reconnect()

        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    # ------------------------------------------------------------------
    # Background reader
    # ------------------------------------------------------------------

    def _reader_loop(self) -> None:
        """Continuously read frames in background, keeping only the latest."""
        while not self._stop_event.is_set():
            self._apply_pending_controls()
            try:
                ret, frame = self._cap.read()  # type: ignore[union-attr]
            except cv2.error as exc:
                logger.warning("Camera %s read error: %s", self._device_id, exc)
                self._mark_disconnected()
                return

            if not ret or frame is None:
                logger.warning("Camera %s returned empty frame", self._device_id)
                self._mark_disconnected()
                return

            with self._frame_lock:
                self._latest_frame = frame
                self._frame_seq += 1
                self._frame_ts = time.monotonic()

    # ------------------------------------------------------------------
    # Runtime camera controls (software AE)
    # ------------------------------------------------------------------

    def request_controls(self, exposure: float | None = None, auto_exposure: float | None = None) -> None:
        """Queue camera control changes; the reader thread applies them between reads."""
        with self._controls_lock:
            if auto_exposure is not None:
                self._pending_controls["auto_exposure"] = float(auto_exposure)
            if exposure is not None:
                self._pending_controls["exposure"] = float(exposure)

    @property
    def controls_effective(self) -> bool | None:
        """Whether the last applied control change actually took (None = never attempted).

        macOS AVFoundation silently rejects UVC exposure controls — the readback check
        catches that so software AE can fall back to advisory mode."""
        return self._controls_effective

    @property
    def initial_exposure(self) -> float | None:
        """Exposure readback at open() — seed value for the software-AE controller."""
        return self._initial_exposure

    def _apply_pending_controls(self) -> None:
        with self._controls_lock:
            if not self._pending_controls:
                return
            pending, self._pending_controls = self._pending_controls, {}
        if self._cap is None:
            return
        try:
            ok = True
            if "auto_exposure" in pending:
                ok = bool(self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, pending["auto_exposure"])) and ok
            if "exposure" in pending:
                target = pending["exposure"]
                ok = bool(self._cap.set(cv2.CAP_PROP_EXPOSURE, target)) and ok
                readback = float(self._cap.get(cv2.CAP_PROP_EXPOSURE))
                ok = ok and abs(readback - target) <= max(1.0, 0.1 * abs(target))
            self._controls_effective = ok
        except cv2.error as exc:
            logger.warning("Camera %s control apply failed: %s", self._device_id, exc)
            self._controls_effective = False

    # ------------------------------------------------------------------
    # Fresh-frame grab (capture path)
    # ------------------------------------------------------------------

    def grab_fresh(
        self, after_ts: float | None = None, settle_ms: float = 150.0, timeout: float = 2.0
    ) -> tuple[np.ndarray | None, int, float]:
        """Return ``(frame, seq, ts)`` for a frame read after ``after_ts + settle``.

        Correctness comes from the **timestamp gate**: because the background
        reader stamps ``time.monotonic()`` on every frame it reads, waiting for
        ``ts > after_ts + settle`` guarantees a frame captured after the LED was
        lit and settled — regardless of any OpenCV buffer depth (plan §3.1). On
        timeout it returns the latest frame available (or ``(None, seq, ts)``).
        """
        if after_ts is None:
            after_ts = time.monotonic()
        target = after_ts + settle_ms / 1000.0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._frame_lock:
                frame, seq, ts = self._latest_frame, self._frame_seq, self._frame_ts
            if frame is not None and ts > target:
                return frame.copy(), seq, ts
            time.sleep(0.005)
        with self._frame_lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy(), self._frame_seq, self._frame_ts
            return None, self._frame_seq, self._frame_ts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mark_disconnected(self) -> None:
        self._connected = False
        logger.warning("Camera %s marked as disconnected", self._device_id)

    def _try_reconnect(self) -> np.ndarray | None:
        """Attempt reconnect after cooldown. Returns a frame on success, else None.

        If the original device path no longer exists (USB renumbering after
        physical disconnect/reconnect), scans all video devices by the V4L2
        device name recorded on first connection.
        """
        now = time.monotonic()
        if now - self._last_reconnect_attempt < self.RECONNECT_COOLDOWN:
            return None

        self._last_reconnect_attempt = now
        logger.info("Attempting to reconnect camera %s ...", self._device_id)

        # Try the original device path first
        if self.open():
            logger.info("Camera %s reconnected", self._device_id)
            return self.read_frame()

        # Original path failed — scan by device name (handles USB renumbering)
        if self._camera_name:
            new_id = _find_device_by_name(self._camera_name, self._device_id)
            if new_id is not None:
                logger.info(
                    "Camera %r found at new device /dev/video%d (was %s)",
                    self._camera_name,
                    new_id,
                    self._device_id,
                )
                self._device_id = new_id
                self._capture_arg = _device_to_capture_arg(new_id)
                if self.open():
                    logger.info("Camera reconnected at /dev/video%d", new_id)
                    return self.read_frame()

        logger.warning("Camera %s reconnect failed, will retry in %.0fs", self._device_id, self.RECONNECT_COOLDOWN)
        return None

    # ------------------------------------------------------------------
    # Static utilities
    # ------------------------------------------------------------------

    @staticmethod
    def detect_cameras(max_id: int = 4) -> list[int]:
        """Probe /dev/video0..max_id to find available cameras."""
        available: list[int] = []
        for dev_id in range(max_id + 1):
            cap = cv2.VideoCapture(_device_to_capture_arg(dev_id))
            if cap.isOpened():
                available.append(dev_id)
            cap.release()
        logger.info("Detected cameras: %s", available)
        return available

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> CameraManager:
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"CameraManager(device_id={self._device_id}, {status})"
