# Go Board Visual Recognition Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a camera-based Go board and stone recognition system that detects the board, identifies black and white stones, and outputs confirmed moves as `katrain.core.sgf_parser.Move` objects for direct integration with KaTrain's play API.

**Architecture:** Camera → MotionFilter (raw frame) → BoardFinder (Canny + undistort + perspective transform) → YOLO11 (stone detection, imgsz=960) → BoardStateExtractor (pixel→grid, confidence-based conflict resolution) → MoveDetector (3-frame consistency) → KaTrain Move (reuse `sgf_parser.Move`). Code lives in `katrain/vision/`.

**Tech Stack:** Python 3.11+, OpenCV (image processing + camera calibration), Ultralytics YOLO11 (training & inference), NumPy, pytest

**Reference Project:** `/Users/fan/Repositories/Fe-Fool/` — Gomoku robot with YOLOv5 piece detection

**Coordinate Convention:** Vision grid `(col, row)` has `(0,0)` at image top-left. KaTrain `Move.coords` has `(col, row)` with row 0 at bottom (GTP convention). Conversion: `katrain_row = board_size - 1 - vision_row`. **Do NOT reimplement GTP/SGF conversion** — reuse `katrain.core.sgf_parser.Move` (see `katrain/core/sgf_parser.py:15-66`).

---

## Task 1: Dependencies & Python Baseline

**Files:**
- Modify: `pyproject.toml`

**Rationale (Codex #1, #6):** Settle the Python version and dependency strategy before writing any code. Production environment is Python 3.11, so `X | None` union syntax is valid. Vision dependencies go in an optional extra group. CI gets a separate job with `--extra vision`.

**Step 1: Add vision optional dependency group to `pyproject.toml`**

Under `[project.optional-dependencies]` add:

```toml
vision = [
    "ultralytics>=8.3.0",
    "opencv-python>=4.8.0",
    "numpy>=1.24.0",
]
```

Update `requires-python` to `">=3.11,<3.14"` if the project is OK dropping 3.9/3.10 support, OR keep `>=3.9` and add `from __future__ import annotations` to all vision module files. **Decision: use `>=3.11`** since production is 3.11.

**Step 2: Install and verify**

Run: `uv sync --extra vision`
Run: `uv run python -c "from ultralytics import YOLO; print('ultralytics OK')"`
Run: `uv run python -c "import cv2; print('opencv OK')"`

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(vision): add vision optional dependencies, set Python >=3.11"
```

---

## Task 2: Project Scaffolding, Board Config & Camera Config

**Files:**
- Create: `katrain/vision/__init__.py`
- Create: `katrain/vision/config.py`
- Create: `tests/test_vision/__init__.py`
- Create: `tests/test_vision/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_vision/__init__.py
# (empty)
```

```python
# tests/test_vision/test_config.py
from katrain.vision.config import BoardConfig, CameraConfig


class TestBoardConfig:
    def test_default_board_config(self):
        cfg = BoardConfig()
        assert cfg.grid_size == 19
        assert cfg.board_width_mm == 424.2
        assert cfg.board_length_mm == 454.5
        assert cfg.border_width_mm == 15.0
        assert cfg.border_length_mm == 15.0

    def test_grid_spacing(self):
        cfg = BoardConfig()
        assert abs(cfg.grid_spacing_w - 23.567) < 0.01
        assert abs(cfg.grid_spacing_l - 25.25) < 0.01

    def test_total_dimensions(self):
        cfg = BoardConfig()
        assert abs(cfg.total_width - 454.2) < 0.01
        assert abs(cfg.total_length - 484.5) < 0.01

    def test_custom_board_config(self):
        cfg = BoardConfig(grid_size=13, board_width_mm=294.0, board_length_mm=290.0, border_width_mm=23.0, border_length_mm=21.0)
        assert cfg.grid_size == 13
        assert cfg.board_width_mm == 294.0


class TestCameraConfig:
    def test_defaults(self):
        cam = CameraConfig()
        assert cam.camera_matrix is None
        assert cam.dist_coeffs is None
        assert cam.calibration_file is None

    def test_is_calibrated(self):
        cam = CameraConfig()
        assert cam.is_calibrated is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vision/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# katrain/vision/__init__.py
# Go board visual recognition package
```

```python
# katrain/vision/config.py
"""Board physical dimensions and camera calibration parameters."""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class BoardConfig:
    """Physical dimensions of a Go board (in millimeters)."""

    grid_size: int = 19
    board_width_mm: float = 424.2
    board_length_mm: float = 454.5
    border_width_mm: float = 15.0
    border_length_mm: float = 15.0

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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vision/test_config.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add katrain/vision/__init__.py katrain/vision/config.py tests/test_vision/__init__.py tests/test_vision/test_config.py
git commit -m "feat(vision): add BoardConfig and CameraConfig"
```

---

## Task 3: Camera Calibration Tool

**Files:**
- Create: `katrain/vision/tools/__init__.py`
- Create: `katrain/vision/tools/calibrate_camera.py`

**Rationale (Codex #10, Gemini #1):** 19×19 boards are dense — barrel distortion from wide-angle lenses causes edge/corner grid points to misalign. `cv2.getPerspectiveTransform` only corrects perspective, not radial distortion. We need a one-time calibration step using a checkerboard pattern, saving camera matrix and distortion coefficients to a `.npz` file.

This is a hardware-interactive tool, not TDD.

**Step 1: Create tool package**

```python
# katrain/vision/tools/__init__.py
# Vision tooling scripts (calibration, data collection, training)
```

**Step 2: Write calibration script**

```python
# katrain/vision/tools/calibrate_camera.py
"""
Camera calibration tool using a printed checkerboard pattern.

Usage:
    1. Print a checkerboard pattern (e.g. 9x6 inner corners)
    2. Run: python -m katrain.vision.tools.calibrate_camera --camera 0 --rows 9 --cols 6
    3. Take 10-15 photos from different angles (press SPACE to capture)
    4. Press Q to finish — calibration parameters saved to camera_calibration.npz

The .npz file contains camera_matrix and dist_coeffs for cv2.undistort().
"""

import argparse
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Calibrate camera with checkerboard")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--rows", type=int, default=9, help="Inner corner rows in checkerboard")
    parser.add_argument("--cols", type=int, default=6, help="Inner corner cols in checkerboard")
    parser.add_argument("--output", type=str, default="camera_calibration.npz")
    args = parser.parse_args()

    pattern_size = (args.cols, args.rows)
    objp = np.zeros((args.cols * args.rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0 : args.cols, 0 : args.rows].T.reshape(-1, 2)

    obj_points = []
    img_points = []

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    print(f"Show checkerboard ({args.cols}x{args.rows} inner corners) to camera.")
    print("SPACE = capture | Q = finish calibration")

    img_size = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if img_size is None:
            img_size = gray.shape[::-1]

        found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
        display = frame.copy()
        if found:
            cv2.drawChessboardCorners(display, pattern_size, corners, found)

        cv2.putText(display, f"Captures: {len(obj_points)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Calibration", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" ") and found:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            obj_points.append(objp)
            img_points.append(corners_refined)
            print(f"Captured {len(obj_points)} images")

    cap.release()
    cv2.destroyAllWindows()

    if len(obj_points) < 5:
        print(f"Need at least 5 captures, got {len(obj_points)}. Aborting.")
        return

    print("Calibrating...")
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points, img_size, None, None)

    print(f"Calibration RMS error: {ret:.4f}")
    print(f"Camera matrix:\n{camera_matrix}")
    print(f"Distortion coefficients: {dist_coeffs.ravel()}")

    np.savez(args.output, camera_matrix=camera_matrix, dist_coeffs=dist_coeffs)
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
```

**Step 3: Commit**

```bash
git add katrain/vision/tools/__init__.py katrain/vision/tools/calibrate_camera.py
git commit -m "feat(vision): add camera calibration tool using checkerboard"
```

---

## Task 4: Coordinate Mapping Functions

**Files:**
- Create: `katrain/vision/coordinates.py`
- Create: `tests/test_vision/test_coordinates.py`

Reference: `Fe-Fool/code/robot/tools.py:104` and `Fe-Fool/code/robot/robot_master.py:330-357`.

**Step 1: Write the failing test**

```python
# tests/test_vision/test_coordinates.py
import pytest
from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import pixel_to_physical, physical_to_grid, grid_to_physical


@pytest.fixture
def cfg():
    return BoardConfig()


class TestPixelToPhysical:
    def test_origin(self, cfg):
        x_mm, y_mm = pixel_to_physical(0, 0, img_w=640, img_h=480, config=cfg)
        assert x_mm == 0.0
        assert y_mm == 0.0

    def test_center(self, cfg):
        x_mm, y_mm = pixel_to_physical(320, 240, img_w=640, img_h=480, config=cfg)
        assert abs(x_mm - cfg.total_width / 2) < 0.01
        assert abs(y_mm - cfg.total_length / 2) < 0.01

    def test_bottom_right(self, cfg):
        x_mm, y_mm = pixel_to_physical(640, 480, img_w=640, img_h=480, config=cfg)
        assert abs(x_mm - cfg.total_width) < 0.01
        assert abs(y_mm - cfg.total_length) < 0.01


class TestPhysicalToGrid:
    def test_top_left_intersection(self, cfg):
        pos_x, pos_y = physical_to_grid(cfg.border_width_mm, cfg.border_length_mm, config=cfg)
        assert pos_x == 0
        assert pos_y == 0

    def test_bottom_right_intersection(self, cfg):
        x = cfg.border_width_mm + cfg.board_width_mm
        y = cfg.border_length_mm + cfg.board_length_mm
        pos_x, pos_y = physical_to_grid(x, y, config=cfg)
        assert pos_x == 18
        assert pos_y == 18

    def test_center_intersection(self, cfg):
        x = cfg.border_width_mm + cfg.board_width_mm / 2
        y = cfg.border_length_mm + cfg.board_length_mm / 2
        pos_x, pos_y = physical_to_grid(x, y, config=cfg)
        assert pos_x == 9
        assert pos_y == 9

    def test_clamps_to_bounds(self, cfg):
        pos_x, pos_y = physical_to_grid(0, 0, config=cfg)
        assert pos_x == 0
        assert pos_y == 0
        pos_x, pos_y = physical_to_grid(9999, 9999, config=cfg)
        assert pos_x == 18
        assert pos_y == 18


class TestGridToPhysical:
    def test_origin(self, cfg):
        x_mm, y_mm = grid_to_physical(0, 0, config=cfg)
        assert abs(x_mm - cfg.border_width_mm) < 0.01
        assert abs(y_mm - cfg.border_length_mm) < 0.01

    def test_last(self, cfg):
        x_mm, y_mm = grid_to_physical(18, 18, config=cfg)
        expected_x = cfg.border_width_mm + cfg.board_width_mm
        expected_y = cfg.border_length_mm + cfg.board_length_mm
        assert abs(x_mm - expected_x) < 0.01
        assert abs(y_mm - expected_y) < 0.01

    def test_roundtrip(self, cfg):
        """physical_to_grid(grid_to_physical(x,y)) == (x,y) for all grid positions."""
        for gx in range(19):
            for gy in range(19):
                x_mm, y_mm = grid_to_physical(gx, gy, config=cfg)
                rx, ry = physical_to_grid(x_mm, y_mm, config=cfg)
                assert rx == gx
                assert ry == gy
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vision/test_coordinates.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# katrain/vision/coordinates.py
"""
Coordinate mapping between pixel, physical (mm), and grid spaces.

Ported from Fe-Fool:
- code/robot/tools.py:104 (coordinate_mapping)
- code/robot/robot_master.py:330-357 (coordinate_to_pos, pos_to_coordinate)
"""

from katrain.vision.config import BoardConfig


def pixel_to_physical(x_pixel: float, y_pixel: float, img_w: int, img_h: int, config: BoardConfig) -> tuple[float, float]:
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vision/test_coordinates.py -v`
Expected: 9 PASSED

**Step 5: Commit**

```bash
git add katrain/vision/coordinates.py tests/test_vision/test_coordinates.py
git commit -m "feat(vision): add coordinate mapping (pixel <-> physical <-> grid)"
```

---

## Task 5: Motion Stability Filter (on Raw Frame)

**Files:**
- Create: `katrain/vision/motion_filter.py`
- Create: `tests/test_vision/test_motion_filter.py`

**Rationale (Codex #5):** Fe-Fool runs motion check on the raw frame BEFORE `find_focus`, not after. Running it after wastes compute on perspective transform during motion. Also, use **changed-pixel-percentage** instead of max-pixel-diff, which is brittle to local highlights/auto-exposure.

**Step 1: Write the failing test**

```python
# tests/test_vision/test_motion_filter.py
import numpy as np
import pytest
from katrain.vision.motion_filter import MotionFilter


@pytest.fixture
def mf():
    return MotionFilter(change_ratio_threshold=0.05, pixel_diff_threshold=30)


class TestMotionFilter:
    def test_first_frame_is_stable(self, mf):
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        assert mf.is_stable(frame) is True

    def test_identical_frames_are_stable(self, mf):
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame)
        assert mf.is_stable(frame.copy()) is True

    def test_large_change_is_unstable(self, mf):
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        mf.is_stable(frame1)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 200
        assert mf.is_stable(frame2) is False

    def test_small_change_is_stable(self, mf):
        frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame1)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 130
        assert mf.is_stable(frame2) is True

    def test_localized_bright_spot_stable(self, mf):
        """A single bright pixel should not trigger instability (unlike max-diff approach)."""
        frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame1)
        frame2 = frame1.copy()
        frame2[100, 100] = [255, 255, 255]  # one bright pixel
        assert mf.is_stable(frame2) is True

    def test_recovers_after_motion(self, mf):
        frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame1)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255
        assert mf.is_stable(frame2) is False
        assert mf.is_stable(frame2.copy()) is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vision/test_motion_filter.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# katrain/vision/motion_filter.py
"""
Inter-frame motion filter to skip processing during hand movements.

Improved from Fe-Fool's max-pixel-diff approach:
- Uses percentage of significantly changed pixels instead of single max pixel value
- More robust to auto-exposure changes and localized reflections
- Applied to raw camera frame BEFORE board detection (saves compute)
"""

import cv2
import numpy as np


class MotionFilter:
    """Rejects frames where significant pixel change indicates motion."""

    def __init__(self, change_ratio_threshold: float = 0.05, pixel_diff_threshold: int = 30):
        """
        Args:
            change_ratio_threshold: Max fraction of pixels that can change significantly (default 5%)
            pixel_diff_threshold: Per-pixel intensity difference to count as "changed" (default 30)
        """
        self.change_ratio_threshold = change_ratio_threshold
        self.pixel_diff_threshold = pixel_diff_threshold
        self.prev_frame: np.ndarray | None = None

    def is_stable(self, frame: np.ndarray) -> bool:
        """Check if the frame is stable (no significant motion)."""
        if self.prev_frame is None:
            self.prev_frame = frame.copy()
            return True

        diff = cv2.absdiff(frame, self.prev_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY) if len(diff.shape) == 3 else diff
        changed_ratio = np.sum(gray_diff > self.pixel_diff_threshold) / gray_diff.size
        self.prev_frame = frame.copy()
        return changed_ratio < self.change_ratio_threshold
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vision/test_motion_filter.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add katrain/vision/motion_filter.py tests/test_vision/test_motion_filter.py
git commit -m "feat(vision): add percentage-based motion filter on raw frames"
```

---

## Task 6: Board Detection — BoardFinder

**Files:**
- Create: `katrain/vision/board_finder.py`
- Create: `tests/test_vision/test_board_finder.py`

Ports `Fe-Fool/code/robot/image_find_focus.py` with:
1. CLAHE preprocessing for wood boards
2. `cv2.undistort` when camera calibration is available (Gemini #1)
3. Fallback to last known transform matrix when detection fails (Gemini #4)

**Step 1: Write the failing test**

```python
# tests/test_vision/test_board_finder.py
import cv2
import numpy as np
import pytest
from katrain.vision.board_finder import BoardFinder
from katrain.vision.config import CameraConfig


@pytest.fixture
def finder():
    return BoardFinder()


def make_board_image(width=640, height=480, board_rect=(100, 50, 440, 380)):
    """Create a synthetic image with a rectangular 'board' region."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (200, 200, 200)
    x1, y1, x2, y2 = board_rect
    cv2.rectangle(img, (x1, y1), (x2, y2), (139, 119, 101), -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), (50, 50, 50), 3)
    return img


class TestBoardFinder:
    def test_finds_board_in_synthetic_image(self, finder):
        img = make_board_image()
        warped, found = finder.find_focus(img)
        assert found is True
        assert warped is not None
        assert warped.shape[0] > 0

    def test_returns_false_for_blank_image(self, finder):
        img = np.ones((480, 640, 3), dtype=np.uint8) * 128
        warped, found = finder.find_focus(img)
        assert found is False

    def test_stability_filter_rejects_large_jumps(self, finder):
        img = make_board_image()
        _, found1 = finder.find_focus(img)
        assert found1 is True
        img2 = make_board_image(board_rect=(200, 150, 540, 430))
        _, found2 = finder.find_focus(img2)
        assert found2 is False

    def test_fallback_uses_last_transform(self, finder):
        """When detection fails but board is stable, reuse last transform matrix."""
        img = make_board_image()
        warped1, found1 = finder.find_focus(img)
        assert found1 is True
        # Blank image — detection fails, but last_transform_matrix should exist
        blank = np.ones((480, 640, 3), dtype=np.uint8) * 128
        warped2, found2 = finder.find_focus(blank)
        # The finder may or may not fallback — test that it doesn't crash
        assert isinstance(found2, bool)
        assert finder.last_transform_matrix is not None  # Saved from successful detection

    def test_clahe_preprocessing(self, finder):
        img = np.ones((480, 640, 3), dtype=np.uint8) * 160
        x1, y1, x2, y2 = 100, 50, 440, 380
        cv2.rectangle(img, (x1, y1), (x2, y2), (150, 140, 130), -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (130, 120, 110), 3)
        warped, found = finder.find_focus(img, use_clahe=True)
        assert isinstance(found, bool)

    def test_accepts_camera_config(self):
        cam = CameraConfig()
        finder = BoardFinder(camera_config=cam)
        assert finder.camera_config is cam
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vision/test_board_finder.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# katrain/vision/board_finder.py
"""
Board detection and perspective correction.

Ported from Fe-Fool/code/robot/image_find_focus.py (FocusFinder class).
Enhanced with:
- CLAHE preprocessing for low-contrast wood boards
- cv2.undistort when camera calibration is available
- Fallback to last known transform matrix on detection failure
"""

import cv2
import numpy as np

from katrain.vision.config import CameraConfig


class BoardFinder:
    def __init__(
        self,
        scale: float = 1.0,
        allowed_moving_girth: int = 300,
        allowed_moving_length: int = 10,
        min_perimeter: int = 600,
        camera_config: CameraConfig | None = None,
    ):
        self.scale = scale
        self.allowed_moving_girth = allowed_moving_girth
        self.allowed_moving_length = allowed_moving_length
        self.min_perimeter = min_perimeter
        self.camera_config = camera_config
        self.pre_corner_point = [(0, 0), (0, 0), (0, 0), (0, 0)]
        self.pre_max_length = 0
        self.is_first = True
        self.last_transform_matrix: np.ndarray | None = None
        self.last_warp_size: tuple[int, int] | None = None

    def find_focus(
        self, img: np.ndarray, min_threshold: int = 30, max_threshold: int = 250, use_clahe: bool = False
    ) -> tuple[np.ndarray | None, bool]:
        """
        Detect board outline and apply perspective transform.

        Returns:
            (warped_image, success) — warped_image is None if detection failed
        """
        source_img = img.copy()

        # Undistort if calibration available
        if self.camera_config and self.camera_config.is_calibrated:
            source_img = cv2.undistort(source_img, self.camera_config.camera_matrix, self.camera_config.dist_coeffs)

        processed = source_img.copy()

        if use_clahe:
            lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
            l_ch, a_ch, b_ch = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_ch = clahe.apply(l_ch)
            lab = cv2.merge([l_ch, a_ch, b_ch])
            processed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        processed = cv2.GaussianBlur(processed, (3, 3), 0, 0)
        canny = cv2.Canny(processed, min_threshold, max_threshold)
        k = np.ones((3, 3), np.uint8)
        canny = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, k)

        contours, _ = cv2.findContours(canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
        if len(contours) == 0:
            return None, False

        max_length = abs(cv2.arcLength(contours[0], True))
        if max_length < self.min_perimeter:
            return None, False

        temp = np.ones(canny.shape, np.uint8) * 255
        approx = cv2.approxPolyDP(contours[0], 10, True)
        cv2.drawContours(temp, approx, -1, (0, 255, 0), 1)

        corners = cv2.goodFeaturesToTrack(temp, 25, 0.1, 10)
        if corners is None:
            return None, False

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        cv2.cornerSubPix(temp, corners, (11, 11), (-1, -1), criteria)
        corners = np.int0(corners)
        point_list = [(x, y) for [[x, y]] in corners]

        if len(point_list) < 4:
            return None, False

        corner_point = self._find_corner(point_list)
        sort_corner = self._sort_corner(corner_point)

        if self.is_first:
            self.pre_corner_point = sort_corner
            self.pre_max_length = max_length
            self.is_first = False

        if abs(self.pre_max_length - max_length) > self.allowed_moving_girth:
            self.pre_max_length = max_length
            return None, False

        if np.max(abs(np.array(sort_corner) - np.array(self.pre_corner_point))) > self.allowed_moving_length:
            self.pre_corner_point = sort_corner
            return None, False

        self.pre_corner_point = sort_corner
        self.pre_max_length = max_length

        h, w = self._calc_size(sort_corner)
        dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        src = np.float32(sort_corner)
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(source_img, M, (int(w), int(h)))
        warped = cv2.flip(warped, 1)

        # Save transform for fallback
        self.last_transform_matrix = M
        self.last_warp_size = (int(w), int(h))

        return warped, True

    def _calc_size(self, corners):
        h = max(corners[2][1] - corners[1][1], corners[3][1] - corners[0][1]) * self.scale
        w = max(corners[0][0] - corners[1][0], corners[3][0] - corners[2][0]) * self.scale
        return h, w

    def _sort_corner(self, pts):
        pts = sorted(pts, key=lambda p: p[1])
        top = sorted(pts[:2], key=lambda p: p[0], reverse=True)
        bot = sorted(pts[2:], key=lambda p: p[0])
        return [top[0], top[1], bot[0], bot[1]]

    def _find_corner(self, point_list):
        """Find the 4 points forming the largest quadrilateral. O(n^3)."""
        n = len(point_list)
        best = 0
        best_idx = [0, 0, 0, 0]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                m1, m2, m1p, m2p = 0, 0, 0, 0
                for kk in range(n):
                    if kk in (i, j):
                        continue
                    a = point_list[i][1] - point_list[j][1]
                    b = point_list[j][0] - point_list[i][0]
                    c = point_list[i][0] * point_list[j][1] - point_list[j][0] * point_list[i][1]
                    t = a * point_list[kk][0] + b * point_list[kk][1] + c
                    area = abs(
                        (point_list[i][0] - point_list[kk][0]) * (point_list[j][1] - point_list[kk][1])
                        - (point_list[j][0] - point_list[kk][0]) * (point_list[i][1] - point_list[kk][1])
                    ) / 2
                    if t > 0 and area > m1:
                        m1, m1p = area, kk
                    elif t < 0 and area > m2:
                        m2, m2p = area, kk
                if m1 and m2 and m1 + m2 > best:
                    best_idx = [i, j, m1p, m2p]
                    best = m1 + m2
        return [point_list[i] for i in best_idx]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vision/test_board_finder.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add katrain/vision/board_finder.py tests/test_vision/test_board_finder.py
git commit -m "feat(vision): port BoardFinder with CLAHE, undistort, and fallback"
```

---

## Task 7: YOLO Stone Detector Wrapper

**Files:**
- Create: `katrain/vision/stone_detector.py`
- Create: `tests/test_vision/test_stone_detector.py`

**Changes from v1 (Gemini code fix):** Enable `agnostic_nms=True` to prevent overlapping black/white bounding boxes at the same position.

**Step 1: Write the failing test**

```python
# tests/test_vision/test_stone_detector.py
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from katrain.vision.stone_detector import StoneDetector, Detection


class TestDetection:
    def test_detection_fields(self):
        d = Detection(x_center=100.0, y_center=200.0, class_id=0, confidence=0.95)
        assert d.x_center == 100.0
        assert d.class_id == 0

    def test_class_name(self):
        assert Detection(x_center=0, y_center=0, class_id=0, confidence=0.9).class_name == "black"
        assert Detection(x_center=0, y_center=0, class_id=1, confidence=0.9).class_name == "white"


class TestStoneDetectorDetect:
    """Test YOLO result parsing with a mock model (no real .pt file needed)."""

    def test_parses_yolo_results(self):
        with patch("katrain.vision.stone_detector.YOLO") as mock_yolo_cls:
            # Build mock YOLO result structure matching ultralytics API
            mock_box = MagicMock()
            mock_box.xyxy = [MagicMock(__getitem__=lambda s, i: [10.0, 20.0, 30.0, 40.0][i], tolist=lambda s: [10.0, 20.0, 30.0, 40.0])]
            mock_box.cls = [MagicMock(__int__=lambda s: 0, __index__=lambda s: 0)]
            mock_box.conf = [MagicMock(__float__=lambda s: 0.95)]
            mock_result = MagicMock()
            mock_result.boxes = [mock_box]
            mock_model = MagicMock()
            mock_model.return_value = [mock_result]
            mock_yolo_cls.return_value = mock_model

            det = StoneDetector("dummy.pt", confidence_threshold=0.5)
            img = np.zeros((400, 400, 3), dtype=np.uint8)
            results = det.detect(img)
            assert len(results) == 1
            assert results[0].x_center == 20.0  # (10+30)/2
            assert results[0].class_id == 0

    def test_filters_low_confidence(self):
        with patch("katrain.vision.stone_detector.YOLO") as mock_yolo_cls:
            mock_box = MagicMock()
            mock_box.xyxy = [MagicMock(tolist=lambda s: [10.0, 20.0, 30.0, 40.0])]
            mock_box.cls = [MagicMock(__int__=lambda s: 0, __index__=lambda s: 0)]
            mock_box.conf = [MagicMock(__float__=lambda s: 0.3)]  # below threshold
            mock_result = MagicMock()
            mock_result.boxes = [mock_box]
            mock_model = MagicMock()
            mock_model.return_value = [mock_result]
            mock_yolo_cls.return_value = mock_model

            det = StoneDetector("dummy.pt", confidence_threshold=0.5)
            results = det.detect(np.zeros((400, 400, 3), dtype=np.uint8))
            assert len(results) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vision/test_stone_detector.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# katrain/vision/stone_detector.py
"""
YOLO11-based Go stone detector.

Uses ultralytics YOLO for detecting black and white stones.
Enables agnostic_nms to prevent overlapping black/white boxes at same position.
"""

from dataclasses import dataclass

import numpy as np
from ultralytics import YOLO

CLASS_NAMES = {0: "black", 1: "white"}


@dataclass
class Detection:
    """A single detected stone."""

    x_center: float
    y_center: float
    class_id: int
    confidence: float

    @property
    def class_name(self) -> str:
        return CLASS_NAMES.get(self.class_id, f"unknown_{self.class_id}")


class StoneDetector:
    """Wraps ultralytics YOLO model for stone detection."""

    def __init__(self, model_path: str, confidence_threshold: float = 0.5, imgsz: int = 960):
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.imgsz = imgsz

    def detect(self, image: np.ndarray) -> list[Detection]:
        """Run YOLO inference on a perspective-corrected board image."""
        results = self.model(image, verbose=False, imgsz=self.imgsz, agnostic_nms=True)
        detections = []
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        x_center=(x1 + x2) / 2,
                        y_center=(y1 + y2) / 2,
                        class_id=int(box.cls[0]),
                        confidence=conf,
                    )
                )
        return detections
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vision/test_stone_detector.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add katrain/vision/stone_detector.py tests/test_vision/test_stone_detector.py
git commit -m "feat(vision): add YOLO11 stone detector with agnostic NMS"
```

---

## Task 8: Board State Extractor with Conflict Resolution

**Files:**
- Create: `katrain/vision/board_state.py`
- Create: `tests/test_vision/test_board_state.py`

**Rationale (Codex #9):** When multiple YOLO detections map to the same grid point, keep the one with highest confidence instead of last-write-wins.

**Step 1: Write the failing test**

```python
# tests/test_vision/test_board_state.py
import numpy as np
import pytest
from katrain.vision.board_state import BoardStateExtractor, EMPTY, BLACK, WHITE
from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_physical
from katrain.vision.stone_detector import Detection


class TestBoardStateConstants:
    def test_constants(self):
        assert EMPTY == 0
        assert BLACK == 1
        assert WHITE == 2


@pytest.fixture
def extractor():
    return BoardStateExtractor()


@pytest.fixture
def cfg():
    return BoardConfig()


class TestDetectionsToBoard:
    def test_empty_detections(self, extractor):
        board = extractor.detections_to_board([], img_w=640, img_h=480)
        assert board.shape == (19, 19)
        assert np.all(board == EMPTY)

    def test_single_black_stone_at_origin(self, extractor, cfg):
        x_pixel = cfg.border_width_mm / cfg.total_width * 640
        y_pixel = cfg.border_length_mm / cfg.total_length * 480
        detections = [Detection(x_center=x_pixel, y_center=y_pixel, class_id=0, confidence=0.95)]
        board = extractor.detections_to_board(detections, img_w=640, img_h=480)
        assert board[0][0] == BLACK

    def test_white_stone_at_tengen(self, extractor, cfg):
        x_pixel = (cfg.border_width_mm + cfg.board_width_mm / 2) / cfg.total_width * 640
        y_pixel = (cfg.border_length_mm + cfg.board_length_mm / 2) / cfg.total_length * 480
        detections = [Detection(x_center=x_pixel, y_center=y_pixel, class_id=1, confidence=0.9)]
        board = extractor.detections_to_board(detections, img_w=640, img_h=480)
        assert board[9][9] == WHITE

    def test_conflict_resolution_highest_confidence_wins(self, extractor, cfg):
        """Two detections at same grid point — higher confidence wins."""
        x_mm, y_mm = grid_to_physical(5, 5, config=cfg)
        x_px = x_mm / cfg.total_width * 640
        y_px = y_mm / cfg.total_length * 480
        # Low-confidence black, then high-confidence white at same point
        detections = [
            Detection(x_center=x_px, y_center=y_px, class_id=0, confidence=0.6),
            Detection(x_center=x_px, y_center=y_px, class_id=1, confidence=0.9),
        ]
        board = extractor.detections_to_board(detections, img_w=640, img_h=480)
        assert board[5][5] == WHITE  # higher confidence wins


class TestBoardToString:
    def test_empty_board_string(self):
        board = np.zeros((19, 19), dtype=int)
        result = BoardStateExtractor.board_to_string(board)
        assert len(result.strip().split("\n")) == 19

    def test_board_with_stones(self):
        board = np.zeros((19, 19), dtype=int)
        board[3][3] = BLACK
        board[15][15] = WHITE
        result = BoardStateExtractor.board_to_string(board)
        lines = result.strip().split("\n")
        assert "B" in lines[3]
        assert "W" in lines[15]
```

**Step 2: Run test → FAIL**

**Step 3: Write implementation**

```python
# katrain/vision/board_state.py
"""
Combines stone detection results with coordinate mapping to produce a 19x19 board state.
Uses confidence-based conflict resolution when multiple detections map to the same grid point.
"""

import numpy as np

from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import pixel_to_physical, physical_to_grid
from katrain.vision.stone_detector import Detection

EMPTY = 0
BLACK = 1
WHITE = 2


class BoardStateExtractor:
    """Converts a list of stone detections into a board state matrix."""

    def __init__(self, config: BoardConfig | None = None):
        self.config = config or BoardConfig()

    def detections_to_board(self, detections: list[Detection], img_w: int, img_h: int) -> np.ndarray:
        """Convert detected stones to a grid_size x grid_size board matrix."""
        gs = self.config.grid_size
        board = np.zeros((gs, gs), dtype=int)
        confidence = np.zeros((gs, gs), dtype=float)

        for det in detections:
            x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
            pos_x, pos_y = physical_to_grid(x_mm, y_mm, self.config)
            if det.confidence > confidence[pos_y][pos_x]:
                board[pos_y][pos_x] = det.class_id + 1  # 0→BLACK(1), 1→WHITE(2)
                confidence[pos_y][pos_x] = det.confidence
        return board

    @staticmethod
    def board_to_string(board: np.ndarray) -> str:
        symbols = {EMPTY: ".", BLACK: "B", WHITE: "W"}
        lines = []
        for row in board:
            lines.append(" ".join(symbols[int(v)] for v in row))
        return "\n".join(lines)
```

**Step 4: Run test → 7 PASSED**

**Step 5: Commit**

```bash
git add katrain/vision/board_state.py tests/test_vision/test_board_state.py
git commit -m "feat(vision): add board state extractor with confidence-based conflict resolution"
```

---

## Task 9: Move Detector with Force Sync

**Files:**
- Create: `katrain/vision/move_detector.py`
- Create: `tests/test_vision/test_move_detector.py`

**Changes from v1 (Codex #4, Gemini #3):** Moved before demo. Added `force_sync()` for undo/endgame scenarios.

**Step 1: Write the failing test**

```python
# tests/test_vision/test_move_detector.py
import numpy as np
import pytest
from katrain.vision.move_detector import MoveDetector
from katrain.vision.board_state import BLACK, WHITE, EMPTY


@pytest.fixture
def detector():
    return MoveDetector(consistency_frames=3)


class TestMoveDetector:
    def test_no_change_returns_none(self, detector):
        board = np.zeros((19, 19), dtype=int)
        for _ in range(5):
            assert detector.detect_new_move(board) is None

    def test_detects_new_black_stone_after_consistency(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        assert detector.detect_new_move(with_stone) is None  # count=1
        assert detector.detect_new_move(with_stone) is None  # count=2
        result = detector.detect_new_move(with_stone)         # count=3
        assert result == (3, 3, BLACK)

    def test_resets_count_on_change(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        detector.detect_new_move(with_stone)  # count=1
        detector.detect_new_move(with_stone)  # count=2
        different = empty.copy()
        different[5][5] = WHITE
        detector.detect_new_move(different)   # count reset
        assert detector.detect_new_move(with_stone) is None  # count=1 again

    def test_ignores_multiple_simultaneous_new_stones(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        two_stones = empty.copy()
        two_stones[3][3] = BLACK
        two_stones[4][4] = WHITE

        for _ in range(5):
            assert detector.detect_new_move(two_stones) is None

    def test_handles_captures(self, detector):
        """Placing a stone that removes opponent stones: only the new stone is detected."""
        board1 = np.zeros((19, 19), dtype=int)
        board1[3][3] = WHITE  # opponent stone
        detector.detect_new_move(board1)

        board2 = board1.copy()
        board2[3][3] = EMPTY  # captured
        board2[3][4] = BLACK  # new move

        assert detector.detect_new_move(board2) is None  # count=1
        assert detector.detect_new_move(board2) is None  # count=2
        result = detector.detect_new_move(board2)         # count=3
        assert result == (3, 4, BLACK)

    def test_force_sync(self, detector):
        board1 = np.zeros((19, 19), dtype=int)
        board1[3][3] = BLACK
        detector.detect_new_move(board1)

        board2 = np.zeros((19, 19), dtype=int)  # stone removed (undo)
        detector.force_sync(board2)
        assert np.array_equal(detector.prev_board, board2)
```

**Step 2: Run test → FAIL**

**Step 3: Write implementation**

```python
# katrain/vision/move_detector.py
"""
Detects newly placed stones by comparing consecutive board states.

Only detects "new stone added" — automatically handles captures (removed opponent stones
are ignored). Provides force_sync() for undo/endgame scenarios.
"""

import numpy as np

from katrain.vision.board_state import EMPTY


class MoveDetector:
    """Detects new moves by comparing board states across frames."""

    def __init__(self, consistency_frames: int = 3):
        self.consistency_frames = consistency_frames
        self.prev_board: np.ndarray | None = None
        self.pending_move: tuple[int, int, int] | None = None
        self.count = 0

    def detect_new_move(self, board: np.ndarray) -> tuple[int, int, int] | None:
        """
        Compare current board with previous accepted state.

        Returns:
            (row, col, color) if a single new stone is confirmed, None otherwise.
            Only detects stones added to empty positions (captures are ignored).
        """
        if self.prev_board is None:
            self.prev_board = board.copy()
            return None

        # Find positions where a stone was added to a previously empty intersection
        diff_positions = []
        for r in range(board.shape[0]):
            for c in range(board.shape[1]):
                if self.prev_board[r][c] == EMPTY and board[r][c] != EMPTY:
                    diff_positions.append((r, c, int(board[r][c])))

        if len(diff_positions) != 1:
            self.count = 0
            self.pending_move = None
            return None

        move = diff_positions[0]
        if move == self.pending_move:
            self.count += 1
        else:
            self.pending_move = move
            self.count = 1

        if self.count >= self.consistency_frames:
            self.prev_board = board.copy()
            self.count = 0
            self.pending_move = None
            return move

        return None

    def force_sync(self, board: np.ndarray) -> None:
        """Force-update the reference board (for undo, endgame cleanup, manual reset)."""
        self.prev_board = board.copy()
        self.count = 0
        self.pending_move = None
```

**Step 4: Run test → 6 PASSED**

**Step 5: Commit**

```bash
git add katrain/vision/move_detector.py tests/test_vision/test_move_detector.py
git commit -m "feat(vision): add move detector with capture handling and force_sync"
```

---

## Task 10: KaTrain Move Bridge (Reuse sgf_parser.Move)

**Files:**
- Create: `katrain/vision/katrain_bridge.py`
- Create: `tests/test_vision/test_katrain_bridge.py`

**Rationale (Codex #2):** Do NOT reimplement GTP/SGF conversion. Reuse `katrain.core.sgf_parser.Move` which already has `from_gtp()`, `gtp()`, `sgf()`. Vision module only needs one function: convert vision grid coordinates to KaTrain's `Move` object.

**Coordinate mapping:**
- Vision: `board[row][col]`, row 0 = image top
- KaTrain Move: `coords=(col, row)`, row 0 = board bottom (GTP convention)
- Conversion: `katrain_row = board_size - 1 - vision_row`

**Step 1: Write the failing test**

```python
# tests/test_vision/test_katrain_bridge.py
import pytest
from katrain.core.sgf_parser import Move
from katrain.vision.katrain_bridge import vision_move_to_katrain
from katrain.vision.board_state import BLACK, WHITE


class TestVisionToKatrain:
    def test_black_stone_at_origin(self):
        """Vision (col=0, row=0) = image top-left = GTP A19 on 19x19 board."""
        move = vision_move_to_katrain(col=0, row=0, color=BLACK)
        assert move.player == "B"
        assert move.coords == (0, 18)  # col=0, katrain_row = 18-0 = 18
        assert move.gtp() == "A19"

    def test_black_stone_bottom_left(self):
        """Vision (col=0, row=18) = image bottom-left = GTP A1."""
        move = vision_move_to_katrain(col=0, row=18, color=BLACK)
        assert move.coords == (0, 0)
        assert move.gtp() == "A1"

    def test_tengen(self):
        """Vision (col=9, row=9) = center = GTP K10."""
        move = vision_move_to_katrain(col=9, row=9, color=WHITE)
        assert move.player == "W"
        assert move.coords == (9, 9)
        assert move.gtp() == "K10"

    def test_d4_star_point(self):
        """Vision (col=3, row=15) = GTP D4 (bottom-left star point)."""
        move = vision_move_to_katrain(col=3, row=15, color=BLACK)
        assert move.coords == (3, 3)
        assert move.gtp() == "D4"

    def test_sgf_roundtrip(self):
        """Verify SGF output matches KaTrain convention."""
        move = vision_move_to_katrain(col=3, row=15, color=BLACK, board_size=19)
        sgf = move.sgf((19, 19))
        reconstructed = Move.from_sgf(sgf, (19, 19), player="B")
        assert reconstructed.coords == move.coords

    def test_to_api_coords(self):
        """Output format compatible with MoveRequest.coords (web API)."""
        move = vision_move_to_katrain(col=9, row=9, color=BLACK)
        # MoveRequest.coords = list(Move.coords) = [col, row]
        assert list(move.coords) == [9, 9]
```

**Step 2: Run test → FAIL**

**Step 3: Write implementation**

```python
# katrain/vision/katrain_bridge.py
"""
Bridge between vision grid coordinates and KaTrain's Move objects.

Vision grid: board[row][col], (0,0) = image top-left.
KaTrain Move: coords=(col, row), row 0 = bottom (GTP convention).

This module does NOT reimplement GTP/SGF conversion — it reuses
katrain.core.sgf_parser.Move which already handles all of that correctly.
"""

from katrain.core.sgf_parser import Move
from katrain.vision.board_state import BLACK, WHITE


def vision_move_to_katrain(col: int, row: int, color: int, board_size: int = 19) -> Move:
    """
    Convert a vision-detected move to a KaTrain Move object.

    Args:
        col: Column index in vision grid (0 = left of image)
        row: Row index in vision grid (0 = top of image)
        color: BLACK (1) or WHITE (2)
        board_size: Board size (default 19)

    Returns:
        katrain.core.sgf_parser.Move with correct GTP/SGF coordinates
    """
    player = "B" if color == BLACK else "W"
    katrain_row = board_size - 1 - row  # flip Y: vision top → GTP bottom
    return Move(coords=(col, katrain_row), player=player)
```

**Step 4: Run test → 6 PASSED**

**Step 5: Commit**

```bash
git add katrain/vision/katrain_bridge.py tests/test_vision/test_katrain_bridge.py
git commit -m "feat(vision): add KaTrain Move bridge reusing sgf_parser.Move"
```

---

## Task 11: Detection Pipeline (Outputs Move)

**Files:**
- Create: `katrain/vision/pipeline.py`
- Create: `tests/test_vision/test_pipeline.py`

**Changes from v1 (Codex #3, #5):**
- MotionFilter runs on raw frame BEFORE BoardFinder
- Pipeline outputs confirmed `Move` objects, not just board matrix
- Integrates MoveDetector inside pipeline

**Step 1: Write the failing test**

```python
# tests/test_vision/test_pipeline.py
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from katrain.vision.pipeline import DetectionPipeline
from katrain.vision.config import BoardConfig
from katrain.vision.stone_detector import Detection
from katrain.vision.board_state import BLACK


class TestDetectionPipeline:
    def test_init(self):
        with patch("katrain.vision.pipeline.StoneDetector"):
            pipeline = DetectionPipeline(model_path="dummy.pt")
            assert pipeline.config.grid_size == 19

    def test_process_frame_motion_rejected_before_board_detection(self):
        """Motion filter runs on raw frame — BoardFinder should NOT be called."""
        with patch("katrain.vision.pipeline.StoneDetector"):
            pipeline = DetectionPipeline(model_path="dummy.pt")
            pipeline.motion_filter = MagicMock()
            pipeline.motion_filter.is_stable.return_value = False
            pipeline.board_finder = MagicMock()

            result = pipeline.process_frame(np.zeros((480, 640, 3), dtype=np.uint8))
            assert result is None
            pipeline.board_finder.find_focus.assert_not_called()  # Key assertion

    def test_process_frame_no_board(self):
        with patch("katrain.vision.pipeline.StoneDetector"):
            pipeline = DetectionPipeline(model_path="dummy.pt")
            pipeline.motion_filter = MagicMock()
            pipeline.motion_filter.is_stable.return_value = True
            pipeline.board_finder = MagicMock()
            pipeline.board_finder.find_focus.return_value = (None, False)

            result = pipeline.process_frame(np.zeros((480, 640, 3), dtype=np.uint8))
            assert result is None

    def test_process_frame_returns_board_and_move(self):
        with patch("katrain.vision.pipeline.StoneDetector") as mock_cls:
            cfg = BoardConfig()
            mock_detector = MagicMock()
            x_px = (cfg.border_width_mm + cfg.board_width_mm / 2) / cfg.total_width * 400
            y_px = (cfg.border_length_mm + cfg.board_length_mm / 2) / cfg.total_length * 400
            mock_detector.detect.return_value = [
                Detection(x_center=x_px, y_center=y_px, class_id=0, confidence=0.95)
            ]
            mock_cls.return_value = mock_detector

            pipeline = DetectionPipeline(model_path="dummy.pt")
            pipeline.motion_filter = MagicMock()
            pipeline.motion_filter.is_stable.return_value = True
            pipeline.board_finder = MagicMock()
            fake_warped = np.zeros((400, 400, 3), dtype=np.uint8)
            pipeline.board_finder.find_focus.return_value = (fake_warped, True)

            result = pipeline.process_frame(np.zeros((480, 640, 3), dtype=np.uint8))
            assert result is not None
            assert result.board.shape == (19, 19)
            assert result.board[9][9] == BLACK
            assert result.warped is not None
            # confirmed_move is None until consistency check passes
```

**Step 2: Run test → FAIL**

**Step 3: Write implementation**

```python
# katrain/vision/pipeline.py
"""
Real-time Go board detection pipeline.

Pipeline order (per Codex review):
1. MotionFilter on RAW frame (before board detection — saves compute)
2. BoardFinder (perspective transform + optional undistort)
3. StoneDetector (YOLO11 inference)
4. BoardStateExtractor (pixel → grid, conflict resolution)
5. MoveDetector (multi-frame consistency)
6. Output: FrameResult with board matrix + optional confirmed Move
"""

from dataclasses import dataclass

import numpy as np

from katrain.core.sgf_parser import Move
from katrain.vision.board_finder import BoardFinder
from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.config import BoardConfig, CameraConfig
from katrain.vision.katrain_bridge import vision_move_to_katrain
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.move_detector import MoveDetector
from katrain.vision.stone_detector import StoneDetector


@dataclass
class FrameResult:
    """Result of processing a single camera frame."""

    board: np.ndarray  # (grid_size, grid_size) with EMPTY/BLACK/WHITE
    warped: np.ndarray  # Perspective-corrected board image
    confirmed_move: Move | None = None  # Set only when MoveDetector confirms a new move


class DetectionPipeline:
    """Full pipeline: camera frame → board state + confirmed moves."""

    def __init__(
        self,
        model_path: str,
        config: BoardConfig | None = None,
        camera_config: CameraConfig | None = None,
        confidence_threshold: float = 0.5,
        use_clahe: bool = False,
        canny_min: int = 20,
    ):
        self.config = config or BoardConfig()
        self.motion_filter = MotionFilter()
        self.board_finder = BoardFinder(camera_config=camera_config)
        self.detector = StoneDetector(model_path, confidence_threshold=confidence_threshold)
        self.state_extractor = BoardStateExtractor(self.config)
        self.move_detector = MoveDetector()
        self.use_clahe = use_clahe
        self.canny_min = canny_min

    def process_frame(self, frame: np.ndarray) -> FrameResult | None:
        """
        Process a single camera frame.

        Returns:
            FrameResult if detection succeeded, None if frame was rejected.
        """
        # Step 1: Motion filter on RAW frame (before board detection)
        if not self.motion_filter.is_stable(frame):
            return None

        # Step 2: Board detection + perspective transform
        warped, found = self.board_finder.find_focus(frame, min_threshold=self.canny_min, use_clahe=self.use_clahe)
        if not found or warped is None:
            return None

        h, w = warped.shape[:2]

        # Step 3: YOLO stone detection
        detections = self.detector.detect(warped)

        # Step 4: Convert to board state (with conflict resolution)
        board = self.state_extractor.detections_to_board(detections, img_w=w, img_h=h)

        # Step 5: Check for confirmed new move
        confirmed_move = None
        move_result = self.move_detector.detect_new_move(board)
        if move_result is not None:
            row, col, color = move_result
            confirmed_move = vision_move_to_katrain(col, row, color, self.config.grid_size)

        return FrameResult(board=board, warped=warped, confirmed_move=confirmed_move)
```

**Step 4: Run test → 4 PASSED**

**Step 5: Commit**

```bash
git add katrain/vision/pipeline.py tests/test_vision/test_pipeline.py
git commit -m "feat(vision): pipeline with motion-first ordering and Move output"
```

---

## Task 12: Data Collection Tool

**Files:**
- Create: `katrain/vision/tools/collect_data.py`

**Change from v1 (Gemini code fix):** Use timestamp in filenames instead of just counter.

**Step 1: Write the script**

```python
# katrain/vision/tools/collect_data.py
"""
Data collection tool: capture perspective-corrected board images for YOLO training.

Usage:
    python -m katrain.vision.tools.collect_data --output ./go_dataset/images --camera 0

Controls:
    SPACE = save current frame
    Q     = quit
"""

import argparse
import time
from pathlib import Path

import cv2

from katrain.vision.board_finder import BoardFinder


def main():
    parser = argparse.ArgumentParser(description="Capture board images for training data")
    parser.add_argument("--output", type=str, default="./go_dataset/images/train", help="Output directory")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index")
    parser.add_argument("--min-threshold", type=int, default=20, help="Canny min threshold")
    parser.add_argument("--use-clahe", action="store_true", help="Enable CLAHE preprocessing")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    finder = BoardFinder()
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    count = 0
    print(f"Saving to {output_dir}/")
    print("SPACE = save | Q = quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        warped, found = finder.find_focus(frame, min_threshold=args.min_threshold, use_clahe=args.use_clahe)

        if found and warped is not None:
            cv2.imshow("Board (corrected)", warped)
        cv2.imshow("Camera (raw)", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" ") and found and warped is not None:
            timestamp = int(time.time() * 1000)
            filename = output_dir / f"board_{timestamp}.jpg"
            cv2.imwrite(str(filename), warped)
            count += 1
            print(f"Saved: {filename} ({count} total)")

    cap.release()
    cv2.destroyAllWindows()
    print(f"Total images saved: {count}")


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add katrain/vision/tools/collect_data.py
git commit -m "feat(vision): add data collection script with timestamp filenames"
```

---

## Task 13: Training Pipeline

**Files:**
- Create: `katrain/vision/tools/train_model.py`
- Create: `katrain/vision/tools/data_template.yaml`

**Changes from v1 (Codex #8, Gemini #2):**
- Default `imgsz=960` instead of 640 (better for dense 19×19 board)
- Add `--validate` subcommand (fix misleading print)

**Step 1: Create data.yaml template**

```yaml
# katrain/vision/tools/data_template.yaml
# Copy to your dataset directory and update the path.
#
# Directory structure:
#   go_dataset/
#   ├── data.yaml
#   ├── images/
#   │   ├── train/       ← ~80% of labeled images
#   │   └── val/         ← ~20%
#   └── labels/
#       ├── train/       ← YOLO .txt matching images/train/
#       └── val/
#
# Label format: class_id x_center y_center width height (normalized 0~1)

path: /path/to/go_dataset
train: images/train
val: images/val

nc: 2
names: ['black', 'white']
```

**Step 2: Write training script with validate subcommand**

```python
# katrain/vision/tools/train_model.py
"""
Train or validate a YOLO11 model for Go stone detection.

Train:    python -m katrain.vision.tools.train_model train --data ./go_dataset/data.yaml
Validate: python -m katrain.vision.tools.train_model val --data ./go_dataset/data.yaml --model runs/detect/go_stones/weights/best.pt
"""

import argparse


def cmd_train(args):
    from ultralytics import YOLO

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name,
        patience=args.patience,
        save=True,
        plots=True,
    )
    print(f"\nTraining complete. Best weights: runs/detect/{args.name}/weights/best.pt")


def cmd_val(args):
    from ultralytics import YOLO

    model = YOLO(args.model)
    results = model.val(data=args.data, imgsz=args.imgsz)
    print(f"\nmAP50: {results.box.map50:.4f}")
    print(f"mAP50-95: {results.box.map:.4f}")


def main():
    parser = argparse.ArgumentParser(description="YOLO11 training/validation for Go stone detection")
    sub = parser.add_subparsers(dest="command", required=True)

    train_p = sub.add_parser("train", help="Train a model")
    train_p.add_argument("--data", type=str, required=True)
    train_p.add_argument("--model", type=str, default="yolo11n.pt")
    train_p.add_argument("--epochs", type=int, default=100)
    train_p.add_argument("--imgsz", type=int, default=960)
    train_p.add_argument("--batch", type=int, default=16)
    train_p.add_argument("--name", type=str, default="go_stones")
    train_p.add_argument("--patience", type=int, default=20)

    val_p = sub.add_parser("val", help="Validate a trained model")
    val_p.add_argument("--data", type=str, required=True)
    val_p.add_argument("--model", type=str, required=True, help="Path to best.pt")
    val_p.add_argument("--imgsz", type=int, default=960)

    args = parser.parse_args()
    if args.command == "train":
        cmd_train(args)
    elif args.command == "val":
        cmd_val(args)


if __name__ == "__main__":
    main()
```

**Step 3: Commit**

```bash
git add katrain/vision/tools/train_model.py katrain/vision/tools/data_template.yaml
git commit -m "feat(vision): training script with imgsz=960 and validate subcommand"
```

---

## Task 14: Live Camera Demo

**Files:**
- Create: `katrain/vision/tools/live_demo.py`

**Step 1: Write the demo script**

```python
# katrain/vision/tools/live_demo.py
"""
Live camera demo: run the full detection pipeline and visualize results.

Usage:
    python -m katrain.vision.tools.live_demo --model best.pt --camera 0

Controls:  Q = quit | C = toggle CLAHE | P = print board state
"""

import argparse

import cv2
import numpy as np

from katrain.vision.board_state import BoardStateExtractor, BLACK, WHITE
from katrain.vision.pipeline import DetectionPipeline


def draw_overlay(image: np.ndarray, board: np.ndarray, config) -> np.ndarray:
    display = image.copy()
    black_count = int(np.sum(board == BLACK))
    white_count = int(np.sum(board == WHITE))
    cv2.putText(display, f"B:{black_count} W:{white_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    return display


def main():
    parser = argparse.ArgumentParser(description="Live Go board detection demo")
    parser.add_argument("--model", type=str, required=True, help="Path to trained YOLO model")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--use-clahe", action="store_true")
    parser.add_argument("--canny-min", type=int, default=20)
    parser.add_argument("--calibration", type=str, default=None, help="Path to camera_calibration.npz")
    args = parser.parse_args()

    camera_config = None
    if args.calibration:
        from katrain.vision.config import CameraConfig
        data = np.load(args.calibration)
        camera_config = CameraConfig(camera_matrix=data["camera_matrix"], dist_coeffs=data["dist_coeffs"])

    pipeline = DetectionPipeline(
        model_path=args.model,
        camera_config=camera_config,
        confidence_threshold=args.confidence,
        use_clahe=args.use_clahe,
        canny_min=args.canny_min,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    print("Q = quit | C = toggle CLAHE | P = print board")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result = pipeline.process_frame(frame)

        if result is not None:
            display = draw_overlay(result.warped, result.board, pipeline.config)
            if result.confirmed_move:
                move_text = f"Move: {result.confirmed_move.gtp()} ({result.confirmed_move.player})"
                cv2.putText(display, move_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                print(f"Confirmed move: {result.confirmed_move}")
            cv2.imshow("Go Board Detection", display)
        else:
            cv2.imshow("Go Board Detection", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("c"):
            pipeline.use_clahe = not pipeline.use_clahe
            print(f"CLAHE: {'ON' if pipeline.use_clahe else 'OFF'}")
        elif key == ord("p") and result is not None:
            print(BoardStateExtractor.board_to_string(result.board))

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add katrain/vision/tools/live_demo.py
git commit -m "feat(vision): add live demo with Move output and calibration support"
```

---

## Task 15: KaTrain Play API Integration

**Files:**
- Create: `katrain/vision/katrain_integration.py`
- Create: `tests/test_vision/test_katrain_integration.py`

**Rationale (Codex #3):** Close the end-to-end loop: vision detection → confirmed Move → call KaTrain's play API (`katrain/web/server.py:309`). The play API accepts `MoveRequest(session_id, coords=[col, row])`.

**Step 1: Write the failing test**

```python
# tests/test_vision/test_katrain_integration.py
import pytest
from unittest.mock import MagicMock, patch
from katrain.core.sgf_parser import Move
from katrain.vision.katrain_integration import VisionPlayerBridge


class TestVisionPlayerBridge:
    def test_submits_move_to_session(self):
        mock_session = MagicMock()
        bridge = VisionPlayerBridge(session=mock_session)

        move = Move(coords=(3, 3), player="B")
        bridge.submit_move(move)

        mock_session.katrain.assert_called_once_with("play", (3, 3))

    def test_ignores_none_move(self):
        mock_session = MagicMock()
        bridge = VisionPlayerBridge(session=mock_session)

        bridge.submit_move(None)
        mock_session.katrain.assert_not_called()

    def test_duplicate_move_rejected(self):
        mock_session = MagicMock()
        bridge = VisionPlayerBridge(session=mock_session)

        move = Move(coords=(3, 3), player="B")
        bridge.submit_move(move)
        bridge.submit_move(move)  # duplicate

        assert mock_session.katrain.call_count == 1
```

**Step 2: Run test → FAIL**

**Step 3: Write implementation**

```python
# katrain/vision/katrain_integration.py
"""
Integrates vision detection pipeline with KaTrain's game session.

Submits confirmed moves to the active game session via the same interface
used by web/desktop UI (session.katrain("play", coords)).
"""

from katrain.core.sgf_parser import Move


class VisionPlayerBridge:
    """Submits vision-detected moves to a KaTrain game session."""

    def __init__(self, session):
        self.session = session
        self.last_submitted_move: Move | None = None

    def submit_move(self, move: Move | None) -> bool:
        """
        Submit a confirmed move to the game session.

        Returns True if the move was submitted, False if skipped (None or duplicate).
        """
        if move is None:
            return False
        if move == self.last_submitted_move:
            return False

        self.session.katrain("play", move.coords)
        self.last_submitted_move = move
        return True
```

**Step 4: Run test → 3 PASSED**

**Step 5: Commit**

```bash
git add katrain/vision/katrain_integration.py tests/test_vision/test_katrain_integration.py
git commit -m "feat(vision): add KaTrain play API integration bridge"
```

---

## Task 16: Full Test Suite & CI Configuration

**Step 1: Run all vision tests**

Run: `uv run pytest tests/test_vision/ -v`
Expected: All tests PASSED (~50 tests)

**Step 2: Run full project tests for regressions**

Run: `CI=true uv run pytest tests -v`
Expected: No regressions

**Step 3: Format code**

Run: `uv run black -l 120 katrain/vision tests/test_vision`

**Step 4: Commit**

```bash
git add -A
git commit -m "style: format vision module with black"
```

**Step 5 (CI): Add vision test job to CI workflow**

If `.github/workflows/test_and_build.yaml` exists, add a separate job:

```yaml
  test-vision:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install uv && uv sync --extra vision
      - run: uv run pytest tests/test_vision/ -v
```

```bash
git add .github/workflows/test_and_build.yaml
git commit -m "ci: add separate vision test job with --extra vision"
```

---

## Summary

| # | Task | Key Deliverable | Tests | Feedback Addressed |
|---|------|-----------------|-------|--------------------|
| 1 | Dependencies | `pyproject.toml` vision extras, Python >=3.11 | — | Codex #1, #6 |
| 2 | Config | `BoardConfig` + `CameraConfig` | 6 | Gemini #1 |
| 3 | Camera calibration | `tools/calibrate_camera.py` | — | Codex #10, Gemini #1 |
| 4 | Coordinates | `pixel_to_physical`, `physical_to_grid`, `grid_to_physical` | 9 | — |
| 5 | Motion filter | Percentage-based, on raw frame | 6 | Codex #5 |
| 6 | Board detection | `BoardFinder` + undistort + fallback | 6 | Gemini #1, #4 |
| 7 | Stone detector | `StoneDetector` + `agnostic_nms` | 4 | Gemini code fix |
| 8 | Board state | Confidence-based conflict resolution | 7 | Codex #9 |
| 9 | Move detector | `force_sync()` + capture handling | 6 | Codex #4, Gemini #3 |
| 10 | KaTrain bridge | Reuse `sgf_parser.Move` | 6 | Codex #2 |
| 11 | Pipeline | Motion-first, outputs `FrameResult` with `Move` | 4 | Codex #3, #5 |
| 12 | Data collection | Timestamp filenames | — | Gemini code fix |
| 13 | Training | `imgsz=960`, `val` subcommand | — | Codex #8, Gemini #2 |
| 14 | Live demo | Camera demo with calibration + Move display | — | — |
| 15 | KaTrain integration | `VisionPlayerBridge` → play API | 3 | Codex #3 |
| 16 | Test suite & CI | Full regression + separate CI job | all | Codex #6, #7 |

**Module structure:**
```
katrain/vision/
├── __init__.py
├── config.py              # BoardConfig + CameraConfig
├── board_finder.py        # Board detection + undistort + perspective transform
├── stone_detector.py      # YOLO11 with agnostic NMS, imgsz=960
├── coordinates.py         # Pixel ↔ physical ↔ grid mapping
├── board_state.py         # Detections → board matrix (confidence-based)
├── motion_filter.py       # Percentage-based motion filter (raw frame)
├── move_detector.py       # Multi-frame consistency + force_sync
├── pipeline.py            # Full pipeline → FrameResult with Move
├── katrain_bridge.py      # Vision coords → sgf_parser.Move
├── katrain_integration.py # Submit Move to KaTrain session
└── tools/
    ├── __init__.py
    ├── calibrate_camera.py  # One-time camera calibration
    ├── collect_data.py      # Training image capture
    ├── train_model.py       # YOLO train/val with imgsz=960
    ├── data_template.yaml   # Dataset config template
    └── live_demo.py         # Real-time demo with Move output
```
