"""On-disk stone-parallax calibration: one JSON file per board under the hardware-vision dir.

It lives beside, never inside, HardwareVisionStateStore's generations: geometry is re-committed on
every drift recalibration, while parallax stays valid until the camera mount, the board or the stone
set changes (vision-stone-parallax design.md §0 D1). The generation it was fitted against is only
recorded for the startup log, never used as a switch.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from katrain.vision.parallax import ParallaxParams

SCHEMA = 1
BOARD_GO_19 = "go-19x19"
# The stones are 7 mm thick: an implied detected-centre height outside this window means the warp or
# the stone-to-intersection pairing was wrong, so the calibration is refused (prd P1-2 acceptance 4).
H_IMPLIED_WINDOW_MM = (2.0, 8.0)

_FLOAT_FIELDS = ("nadir_fx", "nadir_fy", "k", "m", "h_implied_mm", "camera_height_mm", "rms_cells", "max_resid_cells")
_COUNT_FIELDS = ("n_samples", "n_black", "n_white", "frames")


@dataclass(frozen=True)
class ParallaxCalibration:
    board: str
    stone_set: str
    nadir_fx: float
    nadir_fy: float
    k: float
    m: float
    h_implied_mm: float
    camera_height_mm: float
    rms_cells: float
    max_resid_cells: float
    n_samples: int
    n_black: int
    n_white: int
    frames: int
    geometry_generation: str | None
    fitted_at: str
    schema: int = SCHEMA

    @property
    def params(self) -> ParallaxParams:
        return ParallaxParams(self.nadir_fx, self.nadir_fy, self.k)

    def to_json_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, data, board: str = BOARD_GO_19) -> ParallaxCalibration:
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        expected = {f.name for f in fields(cls)}
        missing = sorted(expected - set(data))
        if missing:
            raise ValueError(f"missing fields {missing}")
        unexpected = sorted(set(data) - expected)
        if unexpected:
            raise ValueError(f"unexpected fields {unexpected}")
        if data["schema"] != SCHEMA:
            raise ValueError(f"schema {data['schema']!r} is not {SCHEMA}")
        if data["board"] != board:
            raise ValueError(f"calibrated for board {data['board']!r}, not {board!r}")
        for name in ("stone_set", "fitted_at"):
            if not isinstance(data[name], str) or not data[name]:
                raise ValueError(f"{name} must be a non-empty string")
        if data["geometry_generation"] is not None and not isinstance(data["geometry_generation"], str):
            raise ValueError("geometry_generation must be a string or null")
        for name in _FLOAT_FIELDS:
            value = data[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number, got {value!r}")
        for name in _COUNT_FIELDS:
            if type(data[name]) is not int or data[name] < 0:
                raise ValueError(f"{name} must be a non-negative integer, got {data[name]!r}")
        if not 0.0 < data["k"] < 1.0:
            raise ValueError(f"k={data['k']} is outside (0, 1): parallax always contracts toward the nadir")
        # The height gate must constrain the k that is actually applied, not a free-standing field: a
        # file whose k alone was damaged would otherwise pass on its stale h_implied_mm (codex review).
        if data["camera_height_mm"] <= 0:
            raise ValueError(f"camera_height_mm={data['camera_height_mm']} must be positive")
        if abs(data["m"] * data["k"] - 1.0) > 1e-9:
            raise ValueError(f"m={data['m']} is not 1/k (k={data['k']})")
        h_from_k = data["camera_height_mm"] * (1.0 - data["k"])
        if abs(h_from_k - data["h_implied_mm"]) > 1e-6:
            raise ValueError(
                f"h_implied_mm={data['h_implied_mm']} does not match camera_height_mm*(1-k)={h_from_k:.6f}"
            )
        lo, hi = H_IMPLIED_WINDOW_MM
        if not lo <= h_from_k <= hi:
            raise ValueError(f"h_implied_mm={h_from_k:.3f} (from k) is outside [{lo}, {hi}]")
        return cls(**{name: data[name] for name in expected})


def parallax_path(hardware_vision_dir, board: str = BOARD_GO_19) -> Path:
    return Path(hardware_vision_dir).expanduser() / "parallax" / f"{board}.json"


def load_parallax(path, board: str = BOARD_GO_19) -> tuple[ParallaxCalibration | None, str]:
    """(calibration, "ok") or (None, reason). Never raises for a bad file: a broken calibration
    turns the correction off, it must not take recognition down."""
    p = Path(path)
    if not p.exists():
        return None, f"not calibrated ({p} does not exist)"
    try:
        return ParallaxCalibration.from_json_dict(json.loads(p.read_text(encoding="utf-8")), board=board), "ok"
    except (OSError, ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError
        return None, f"invalid calibration file {p}: {exc}"


def save_parallax(path, calib: ParallaxCalibration) -> None:
    """Validate, then write atomically (temp file in the same directory + os.replace), so a refused
    or interrupted write never replaces a good calibration."""
    ParallaxCalibration.from_json_dict(calib.to_json_dict(), board=calib.board)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(calib.to_json_dict(), f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
