"""
Coordinate mapping between pixel, physical (mm), and grid spaces.

Ported from Fe-Fool:
- code/robot/tools.py:104 (coordinate_mapping)
- code/robot/robot_master.py:330-357 (coordinate_to_pos, pos_to_coordinate)
"""

from katrain.vision.config import BoardConfig


def pixel_to_physical(
    x_pixel: float, y_pixel: float, img_w: int, img_h: int, config: BoardConfig
) -> tuple[float, float]:
    """Convert pixel coordinates to physical coordinates (mm)."""
    x_mm = x_pixel * config.total_width / img_w
    y_mm = y_pixel * config.total_length / img_h
    return x_mm, y_mm


def physical_to_grid(x_mm: float, y_mm: float, config: BoardConfig) -> tuple[int, int]:
    """Convert physical coordinates (mm) to grid intersection position (0..grid_size-1)."""
    gs = config.grid_size - 1
    pos_x = round((x_mm - config.border_width_mm) / config.board_width_mm * gs)
    pos_y = round((y_mm - config.border_length_mm) / config.board_length_mm * gs)
    pos_x = max(0, min(gs, pos_x))
    pos_y = max(0, min(gs, pos_y))
    return pos_x, pos_y


def continuous_grid_pos(x_mm: float, y_mm: float, config: BoardConfig) -> tuple[float, float]:
    """Unrounded grid coordinates (fx, fy). ``physical_to_grid`` is ``round()`` + clamp of this.
    Used by occupancy-aware assignment, which needs the sub-cell position, not just the cell."""
    gs = config.grid_size - 1
    fx = (x_mm - config.border_width_mm) / config.board_width_mm * gs
    fy = (y_mm - config.border_length_mm) / config.board_length_mm * gs
    return fx, fy


def grid_to_physical(pos_x: int, pos_y: int, config: BoardConfig) -> tuple[float, float]:
    """Convert grid position to physical coordinates (mm). Used for robot arm targeting."""
    gs = config.grid_size - 1
    x_mm = config.border_width_mm + pos_x * config.board_width_mm / gs
    y_mm = config.border_length_mm + pos_y * config.board_length_mm / gs
    return x_mm, y_mm


def grid_to_pixel_float(fx: float, fy: float, img_w: int, img_h: int, config: BoardConfig) -> tuple[float, float]:
    """Continuous grid position -> warped-image pixel, unrounded. `grid_to_pixel` truncates this."""
    x_mm, y_mm = grid_to_physical(fx, fy, config)
    return x_mm / config.total_width * img_w, y_mm / config.total_length * img_h


def grid_to_pixel(pos_x: int, pos_y: int, img_w: int, img_h: int, config: BoardConfig) -> tuple[int, int]:
    """Convert grid intersection to pixel coordinates in the warped image."""
    px, py = grid_to_pixel_float(pos_x, pos_y, img_w, img_h, config)
    return int(px), int(py)


def apply_parallax(fx: float, fy: float, nadir: tuple[float, float] | None, k: float | None) -> tuple[float, float]:
    """Undo stone-thickness parallax on a continuous grid position (vision-stone-parallax track).

    A stone's detected centre sits above the board, so the camera sees it pushed outward from the
    nadir (the lens centre dropped onto the board plane) by a homothety of factor 1/k; the contact
    point is ``nadir + (detected - nadir) * k``. The factor survives the affine pixel -> mm -> grid
    chain unchanged, so this runs directly on (fx, fy) with ``nadir`` in the same grid coordinates.

    NOT idempotent (applying twice contracts by k**2): call it exactly once per detection.
    Identity when uncalibrated (``nadir`` or ``k`` is None), and returns the inputs untouched when
    ``k == 1.0`` -- ``nadir + (fx - nadir) * 1.0`` is not always ``fx`` in floating point, and
    "parallax off" must be bit-identical to not calling this at all.
    """
    if nadir is None or k is None or k == 1.0:
        return fx, fy
    return nadir[0] + (fx - nadir[0]) * k, nadir[1] + (fy - nadir[1]) * k
