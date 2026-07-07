"""Geometry lock — katrain's integration point for the ported autocal pipeline.

Locks the empty-board geometry into a session file whose schema is **binary
round-trip compatible** with autoresearch's ``session.npz`` (exactly 8 arrays:
corners, points, xs, ys, M, Minv, out_size, baseline). Transient diagnostics
(confidence, matched teeth, empty self-check counts) are written to a sidecar
``.json`` — never into the npz — so autoresearch can load our locks unchanged.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from katrain.vision import geometry_autocal, geometry_calibrate, stone_classifier

log = logging.getLogger(__name__)

# The 8 arrays persisted to npz (order/shape match autoresearch session.npz).
NPZ_FIELDS = ("corners", "points", "xs", "ys", "M", "Minv", "out_size", "baseline")


@dataclass
class GeometryLock:
    corners: np.ndarray  # (4,2) float32  TL/TR/BR/BL
    points: np.ndarray  # (19,19,2) float32 intersection pixel coords
    xs: np.ndarray  # (19,) float32 warped column positions
    ys: np.ndarray  # (19,) float32 warped row positions
    M: np.ndarray  # (3,3) float64 perspective transform (orig->warp)
    Minv: np.ndarray  # (3,3) float64 inverse
    out_size: int  # warp square size (950)
    baseline: np.ndarray  # (19,19,3) float32 empty-board HSV baseline
    # transient diagnostics (sidecar json, NOT in npz)
    confidence: float = 0.0
    nmatch: int = 0
    empty_black: int = 0
    empty_white: int = 0
    diag: dict = field(default_factory=dict)
    # source camera-frame resolution M was calibrated against (sidecar json; None for old locks).
    # Consumers reconcile the live frame to this via warp.adjust_M_for_resolution.
    source_width: Optional[int] = None
    source_height: Optional[int] = None

    @property
    def empty_self_check_ok(self) -> bool:
        return self.empty_black == 0 and self.empty_white == 0


def lock_geometry_from_frames(
    frames: List[np.ndarray], conf_min: float = geometry_autocal.CONF_MIN, out_size: int = geometry_autocal.OUT_SIZE
) -> Optional[GeometryLock]:
    """Run autocal on EMPTY-board frames and build a GeometryLock (or None if coarse
    detection fails). Confidence/empty-self-check are filled in for the caller to gate."""
    import cv2

    if not frames:
        return None
    res = geometry_autocal.auto_calibrate(frames)
    corners = res.get("corners")
    if corners is None:
        log.warning("geometry lock: coarse detection failed (%s)", res.get("reason"))
        return None
    corners = np.asarray(corners, np.float32)

    dst = np.array([[0, 0], [out_size - 1, 0], [out_size - 1, out_size - 1], [0, out_size - 1]], np.float32)
    M = cv2.getPerspectiveTransform(corners, dst)
    Minv = cv2.getPerspectiveTransform(dst, corners)
    xs = np.linspace(0, out_size - 1, 19).astype(np.float32)
    ys = np.linspace(0, out_size - 1, 19).astype(np.float32)
    points = geometry_calibrate.grid_points_from_corners(corners, size=out_size)
    warps = [cv2.warpPerspective(f, M, (out_size, out_size)) for f in frames[-8:]]
    baseline = stone_classifier.build_baseline(warps, xs, ys)
    state, _ = stone_classifier.classify(warps[-1], xs, ys, baseline)
    nb = int((state == stone_classifier.BLACK).sum())
    nw = int((state == stone_classifier.WHITE).sum())

    return GeometryLock(
        corners=corners,
        points=points.astype(np.float32),
        xs=xs,
        ys=ys,
        M=M,
        Minv=Minv,
        out_size=int(out_size),
        baseline=baseline.astype(np.float32),
        confidence=float(res.get("confidence", 0.0)),
        nmatch=int(min(res.get("nmatch_x", 0), res.get("nmatch_y", 0))),
        empty_black=nb,
        empty_white=nw,
        diag={k: res.get(k) for k in ("confidence", "nmatch_x", "nmatch_y", "moved_px", "diag_px")},
        source_height=int(frames[-1].shape[0]),
        source_width=int(frames[-1].shape[1]),
    )


def _sidecar_path(npz_path) -> Path:
    p = Path(npz_path)
    return p.with_suffix(".json")


def save_geometry_lock(lock: GeometryLock, npz_path) -> None:
    """Write the 8-array npz (autoresearch-compatible) plus a diagnostics sidecar json."""
    p = Path(npz_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    sidecar = {
        "confidence": lock.confidence,
        "nmatch": lock.nmatch,
        "empty_black": lock.empty_black,
        "empty_white": lock.empty_white,
        "diag": lock.diag,
        "source_width": lock.source_width,
        "source_height": lock.source_height,
    }
    sidecar_json = json.dumps(
        sidecar,
        indent=2,
        default=lambda value: value.item() if isinstance(value, np.generic) else _raise_json_type_error(value),
    )

    npz_tmp = json_tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp", delete=False) as fh:
            npz_tmp = Path(fh.name)
            np.savez(
                fh,
                corners=lock.corners,
                points=lock.points,
                xs=lock.xs,
                ys=lock.ys,
                M=lock.M,
                Minv=lock.Minv,
                out_size=np.int64(lock.out_size),
                baseline=lock.baseline,
            )
        sidecar_path = _sidecar_path(p)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=p.parent, prefix=f".{sidecar_path.name}.", suffix=".tmp", delete=False
        ) as fh:
            json_tmp = Path(fh.name)
            fh.write(sidecar_json)
        os.replace(npz_tmp, p)
        npz_tmp = None
        os.replace(json_tmp, sidecar_path)
        json_tmp = None
    finally:
        for tmp in (npz_tmp, json_tmp):
            if tmp is not None:
                tmp.unlink(missing_ok=True)


def _raise_json_type_error(value):
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def load_geometry_lock(npz_path) -> GeometryLock:
    """Load a GeometryLock from npz (+ sidecar json diagnostics if present)."""
    d = np.load(str(npz_path))
    missing = [k for k in NPZ_FIELDS if k not in d.files]
    if missing:
        raise ValueError(f"geometry npz missing fields: {missing}")
    lock = GeometryLock(
        corners=d["corners"],
        points=d["points"],
        xs=d["xs"],
        ys=d["ys"],
        M=d["M"],
        Minv=d["Minv"],
        out_size=int(d["out_size"]),
        baseline=d["baseline"],
    )
    sidecar = _sidecar_path(npz_path)
    if sidecar.exists():
        try:
            with open(sidecar, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
            lock.confidence = meta.get("confidence", 0.0)
            lock.nmatch = meta.get("nmatch", 0)
            lock.empty_black = meta.get("empty_black", 0)
            lock.empty_white = meta.get("empty_white", 0)
            lock.diag = meta.get("diag", {})
            lock.source_width = meta.get("source_width")
            lock.source_height = meta.get("source_height")
        except Exception:
            pass
    return lock
