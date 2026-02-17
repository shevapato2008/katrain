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
