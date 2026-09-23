"""Pre-inference image enhancement for stone detection.

CLAHE on the LAB lightness channel measurably lifts weak-light stone confidence
(A/B on real dim frames, m-model: weak black 0.31->0.67, LED-tinted black
0.60->0.76, strong stones unchanged) while plain gamma/brightness boosts HURT
black stones by washing out their contrast. Parameters match the validated A/B run.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

_CLAHE_CLIP_LIMIT = 3.0
_CLAHE_TILE_GRID = (8, 8)

# One CLAHE object per thread, built once.  cv2.createCLAHE() allocates and sets up
# internal LUT/tile buffers, and the vision loop was paying for that on every frame;
# the object itself is reusable across apply() calls.  Kept thread-local rather than
# module-global because an OpenCV algorithm object carries scratch state and is not
# documented as safe for concurrent apply() (two vision workers can coexist in one
# process), and a per-thread object costs nothing.
_local = threading.local()


def _clahe() -> cv2.CLAHE:
    clahe = getattr(_local, "clahe", None)
    if clahe is None:
        clahe = cv2.createCLAHE(clipLimit=_CLAHE_CLIP_LIMIT, tileGridSize=_CLAHE_TILE_GRID)
        _local.clahe = clahe
    return clahe


def enhance_for_inference(frame: np.ndarray, mode: str = "clahe") -> np.ndarray:
    """Return the frame to feed the detector. mode: "clahe" | "off"."""
    if mode != "clahe":
        return frame
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = _clahe().apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
