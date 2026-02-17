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


def grid_to_physical(pos_x: int, pos_y: int, config: BoardConfig) -> tuple[float, float]:
    """Convert grid position to physical coordinates (mm). Used for robot arm targeting."""
    gs = config.grid_size - 1
    x_mm = config.border_width_mm + pos_x * config.board_width_mm / gs
    y_mm = config.border_length_mm + pos_y * config.board_length_mm / gs
    return x_mm, y_mm


def grid_to_pixel(pos_x: int, pos_y: int, img_w: int, img_h: int, config: BoardConfig) -> tuple[int, int]:
    """Convert grid intersection to pixel coordinates in the warped image."""
    x_mm, y_mm = grid_to_physical(pos_x, pos_y, config)
    px = int(x_mm / config.total_width * img_w)
    py = int(y_mm / config.total_length * img_h)
    return px, py
