"""Temporal frame averaging for static-scene noise reduction."""

from collections import deque

import numpy as np


class FrameAverager:
    """Rolling average over the last ``n`` frames of a static scene.

    Temporal sensor noise falls ~sqrt(N) with averaging (measured 4.7x at n=8 on the
    kiosk camera in weak light), which stabilizes both detection confidence and box
    centers — the frame-to-frame center jitter that breaks per-cell voting is largely
    noise-driven. MUST be reset whenever the scene actually changes (motion, geometry
    re-lock, session reset); blending across a scene change would ghost the old scene
    into the average. Resetting on motion also means a newly placed stone appears at
    full contrast immediately (buffer restarts from the first post-motion frame)
    instead of fading in over n frames.

    ``n`` <= 1 disables averaging (add() passes frames through).
    """

    def __init__(self, n: int = 8):
        self.n = max(1, int(n))
        self._frames: deque = deque()  # uint8 frames (memory: n * frame size)
        self._idents: deque = deque()  # caller-supplied identity of each buffered frame (diagnostics only)
        self._sum: np.ndarray | None = None  # float32 running sum (exact for uint8 inputs)

    def add(self, frame: np.ndarray, ident=None) -> np.ndarray:
        """Add a frame; return the average of the buffered frames (uint8)."""
        if self.n == 1:
            self._idents = deque([ident])
            return frame
        if self._frames and self._frames[0].shape != frame.shape:
            self.reset()  # warp out-size changed (new geometry) — old buffer is another scene
        self._frames.append(frame.copy())
        self._idents.append(ident)
        if self._sum is None:
            self._sum = frame.astype(np.float32)
        else:
            self._sum += frame
        if len(self._frames) > self.n:
            self._sum -= self._frames.popleft()
            self._idents.popleft()
        return (self._sum / len(self._frames) + 0.5).astype(np.uint8)

    @property
    def contributors(self) -> tuple:
        """Identities of exactly the frames in the current average, oldest first."""
        return tuple(self._idents)

    def reset(self) -> None:
        """Drop the buffer — call on motion, geometry change, or session reset."""
        self._frames.clear()
        self._idents.clear()
        self._sum = None
