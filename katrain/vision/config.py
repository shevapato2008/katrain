"""Board physical dimensions and camera calibration parameters."""

from dataclasses import dataclass

import numpy as np

# Blank border (in grid cells) added around the 19x19 grid in the rectified warp so edge/corner
# stones aren't clipped. Single source of truth shared by the training labeler (baipu_autolabel)
# and the geometry-lock inference warp, so train and serve see the same geometry.
DEFAULT_MARGIN_CELLS = 1.0


@dataclass
class BoardConfig:
    """Physical dimensions of a Go board (in millimeters).

    ``margin_cells`` > 0 derives ``border_*_mm`` = that many cells of physical border, so
    ``physical_to_grid`` correctly maps a margined warp (default 0 → no border, unchanged for
    the BoardFinder paths)."""

    grid_size: int = 19
    board_width_mm: float = 424.2
    board_length_mm: float = 454.5
    border_width_mm: float = 0.0
    border_length_mm: float = 0.0
    margin_cells: float = 0.0

    def __post_init__(self):
        if self.margin_cells:
            cells = self.grid_size - 1
            self.border_width_mm = self.margin_cells * self.board_width_mm / cells
            self.border_length_mm = self.margin_cells * self.board_length_mm / cells

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
