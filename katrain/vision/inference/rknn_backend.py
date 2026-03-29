"""RKNN NPU inference backend – placeholder.

The target RK3562 ships with RKNPU driver v0.9.8 which is too old for
rknn-toolkit-lite2 (requires >= v1.4.0).  This stub exists so that the
factory in ``base.py`` can resolve the ``"rknn"`` backend name and give
a clear error message at load time.
"""

from __future__ import annotations

import numpy as np

from katrain.vision.stone_detector import Detection


class RknnBackend:
    """Stub RKNN backend – raises on load until the device driver is updated."""

    def load(self, model_path: str, meta_path: str | None = None) -> None:
        raise RuntimeError(
            "RKNN backend requires rknn-toolkit-lite2 and RKNPU driver >= v1.4.0. " "Current device driver is too old."
        )

    def detect(self, image: np.ndarray, confidence_threshold: float) -> list[Detection]:
        raise RuntimeError("RKNN backend not loaded")

    def unload(self) -> None:
        pass

    @property
    def is_loaded(self) -> bool:
        return False
