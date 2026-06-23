"""Board physical dimensions and camera calibration parameters."""

from dataclasses import dataclass

import numpy as np


@dataclass
class BoardConfig:
    """Physical dimensions of a Go board (in millimeters)."""

    grid_size: int = 19
    board_width_mm: float = 424.2
    board_length_mm: float = 454.5
    border_width_mm: float = 0.0
    border_length_mm: float = 0.0

    @property
    def grid_spacing_w(self) -> float:
        return self.board_width_mm / (self.grid_size - 1)

    @property
    def grid_spacing_l(self) -> float:
        return self.board_length_mm / (self.grid_size - 1)

    @property
    def total_width(self) -> float:
        return self.board_width_mm + 2 * self.border_width_mm

    @property
    def total_length(self) -> float:
        return self.board_length_mm + 2 * self.border_length_mm


@dataclass
class CameraConfig:
    """Camera intrinsic parameters from calibration."""

    camera_matrix: np.ndarray | None = None
    dist_coeffs: np.ndarray | None = None
    calibration_file: str | None = None

    @property
    def is_calibrated(self) -> bool:
        return self.camera_matrix is not None and self.dist_coeffs is not None


@dataclass
class LedAnchorConfig:
    """HSV thresholds for locating the guide LED as a drift anchor (NOT for labeling —
    the LED's class/position come from manifest ground truth). Parameterized so a new
    board/light is a config edit, not a code change. Red hue wraps 0/180."""

    red_hue_hi: int = 12
    red_hue_lo: int = 168
    green_hue_lo: int = 40
    green_hue_hi: int = 90
    s_min: int = 80
    v_min: int = 120
