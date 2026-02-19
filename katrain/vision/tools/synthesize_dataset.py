"""
Synthesize YOLO training data from SGF game records + seed board photo.

Pipeline:
  1. Extract assets from seed photo: empty board (inpainted), stone patch templates, perspective matrices
  2. Parse SGF files → stone positions at each move interval
  3. Place stones on empty board in warped space, inverse-warp to camera perspective
  4. Add random off-board stones for detector robustness
  5. Output images + YOLO labels (normalized bboxes in original image coordinates)

Usage:
    python -m katrain.vision.tools.synthesize_dataset \
        --seed-image tests/data/board_recognition_case1_real.png \
        --sgf-dir /path/to/sgf/files/ \
        --output ./go_dataset \
        --max-games 1 --move-interval 10 --verify
"""

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from katrain.core.sgf_parser import SGF
from katrain.vision.board_finder import BoardFinder
from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_pixel
from katrain.vision.tools.auto_label import STONE_BBOX_H, STONE_BBOX_W


@dataclass
class SeedAssets:
    """Assets extracted from a seed board image."""

    empty_board: np.ndarray
    black_patches: list  # list of (BGR patch, alpha mask) tuples
    white_patches: list
    transform_matrix: np.ndarray  # M: original -> warped
    inv_transform_matrix: np.ndarray  # M_inv: warped -> original
    warp_size: tuple[int, int]  # (width, height) of warped image
    original_bg: np.ndarray
    original_shape: tuple
    board_mask: np.ndarray  # binary mask of board in original image
    stone_size: tuple[int, int]  # (width, height) in warped pixels


def extract_assets(
    seed_image_path: str,
    marker_ids: list[int] | None = None,
    empty_board_path: str | None = None,
    detect_method: str = "auto",
    crop_method: str = "fixed",
    sam_model_name: str = "mobile_sam.pt",
) -> SeedAssets:
    """Extract reusable assets from a seed board image.

    Runs BoardFinder to get perspective-corrected view, detects stones using the
    chosen method, crops real stone patches when possible, and falls back to
    synthetic patches.

    Args:
        seed_image_path: path to seed board photo with ArUco markers
        marker_ids: ArUco marker IDs to detect
        empty_board_path: optional pre-photographed empty board (highest quality)
        detect_method: "auto", "diff", "vision", or "adaptive"
    """
    if marker_ids is None:
        marker_ids = [0, 1, 2, 3]

    img = cv2.imread(seed_image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read seed image: {seed_image_path}")

    finder = BoardFinder(marker_ids=marker_ids)
    warped, ok = finder.find_focus(img)
    if not ok or warped is None:
        raise RuntimeError("Board detection failed on seed image")

    M = finder.last_transform_matrix
    warp_size = finder.last_warp_size  # (w, h)
    M_inv = np.linalg.inv(M)

    warp_h, warp_w = warped.shape[:2]
    stone_w = int(STONE_BBOX_W * warp_w)
    stone_h = int(STONE_BBOX_H * warp_h)
    half_w, half_h = stone_w // 2, stone_h // 2

    # --- Detect stones and obtain empty board ---
    stone_positions: list[tuple[int, int, str]] = []
    empty_board: np.ndarray | None = None

    if empty_board_path is not None:
        # User-provided empty board photo → warp with same finder
        empty_img = cv2.imread(empty_board_path)
        if empty_img is None:
            raise FileNotFoundError(f"Cannot read empty board image: {empty_board_path}")
        empty_warped, ok2 = finder.find_focus(empty_img)
        if not ok2 or empty_warped is None:
            raise RuntimeError("Board detection failed on empty board image")
        # Resize to match seed warp (ArUco corners differ slightly between shots)
        if empty_warped.shape[:2] != (warp_h, warp_w):
            empty_warped = cv2.resize(empty_warped, (warp_w, warp_h), interpolation=cv2.INTER_AREA)
        empty_board = empty_warped
        print(f"  Using user-provided empty board: {empty_board_path}")

    # Choose detection method
    effective_method = detect_method
    if detect_method == "auto":
        if empty_board is not None:
            effective_method = "diff"
        else:
            effective_method = "vision"  # will fallback to adaptive if unavailable

    if effective_method == "diff":
        if empty_board is None:
            raise ValueError("--detect-method diff requires --empty-board")
        stone_positions = _detect_stones_by_diff(warped, empty_board, stone_h)
        print(
            f"  Diff detection: {len(stone_positions)} stones ({sum(1 for *_, c in stone_positions if c == 'B')}B + {sum(1 for *_, c in stone_positions if c == 'W')}W)"
        )
    elif effective_method == "vision":
        result = _detect_stones_vision(warped)
        if result is not None:
            stone_positions = result
        else:
            print("  [vision] Falling back to adaptive detection")
            stone_positions = _detect_stones_adaptive(warped, stone_h)
            print(f"  Adaptive detection: {len(stone_positions)} stones")
    elif effective_method == "adaptive":
        stone_positions = _detect_stones_adaptive(warped, stone_h)
        print(f"  Adaptive detection: {len(stone_positions)} stones")
    else:
        raise ValueError(f"Unknown detect method: {detect_method}")

    # --- Empty board (inpaint if not provided) ---
    if empty_board is None:
        inpaint_mask = np.zeros(warped.shape[:2], dtype=np.uint8)
        for px, py, _color in stone_positions:
            cv2.ellipse(inpaint_mask, (px, py), (half_w + 2, half_h + 2), 0, 0, 360, 255, -1)
        empty_board = cv2.inpaint(warped, inpaint_mask, inpaintRadius=20, flags=cv2.INPAINT_TELEA)
        print(f"  Inpainted {len(stone_positions)} stone positions for empty board")

    # --- Crop real stone patches from warped seed image ---
    black_patches: list[tuple[np.ndarray, np.ndarray]] = []
    white_patches: list[tuple[np.ndarray, np.ndarray]] = []
    for px, py, color in stone_positions:
        patch, mask = _crop_stone_patch_dispatch(
            warped, empty_board, px, py, half_w, half_h, color, crop_method, sam_model_name
        )
        if patch is not None:
            if color == "B":
                black_patches.append((patch, mask))
            else:
                white_patches.append((patch, mask))

    # Fallback: generate synthetic if a color has 0 real patches
    if not black_patches or not white_patches:
        synth_b, synth_w = generate_synthetic_stones(stone_w, stone_h, n_variants=20)
        if not black_patches:
            black_patches = synth_b
            print(f"  No real black patches found, using {len(synth_b)} synthetic")
        if not white_patches:
            white_patches = synth_w
            print(f"  No real white patches found, using {len(synth_w)} synthetic")
    print(f"  Stone patches: {len(black_patches)} black, {len(white_patches)} white")

    # Board mask in original image space: transform warped corners back
    warped_corners = np.float32([[0, 0], [warp_size[0], 0], [warp_size[0], warp_size[1]], [0, warp_size[1]]]).reshape(
        -1, 1, 2
    )
    original_corners = cv2.perspectiveTransform(warped_corners, M_inv).reshape(-1, 2).astype(np.int32)
    board_mask = np.zeros(img.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(board_mask, original_corners, 255)

    return SeedAssets(
        empty_board=empty_board,
        black_patches=black_patches,
        white_patches=white_patches,
        transform_matrix=M,
        inv_transform_matrix=M_inv,
        warp_size=warp_size,
        original_bg=img,
        original_shape=img.shape,
        board_mask=board_mask,
        stone_size=(stone_w, stone_h),
    )


def _make_elliptical_alpha(w: int, h: int, feather: float = 0.12) -> np.ndarray:
    """Generate a feathered elliptical alpha mask.

    Args:
        w: width in pixels
        h: height in pixels
        feather: fraction of radius used for soft edge (0 = hard, 0.2 = very soft)
    Returns:
        uint8 alpha mask (h, w)
    """
    half_w, half_h = w / 2.0, h / 2.0
    y, x = np.mgrid[:h, :w]
    # Normalized elliptical distance: 1.0 at the ellipse boundary
    dist = np.sqrt(((x - half_w + 0.5) / half_w) ** 2 + ((y - half_h + 0.5) / half_h) ** 2)
    inner = 1.0 - feather
    alpha = np.clip((1.0 - dist) / (1.0 - inner + 1e-6), 0.0, 1.0)
    return (alpha * 255).astype(np.uint8)


def generate_synthetic_stones(
    stone_w: int, stone_h: int, n_variants: int = 20
) -> tuple[list[tuple[np.ndarray, np.ndarray]], list[tuple[np.ndarray, np.ndarray]]]:
    """Generate synthetic elliptical stone patches (no real image needed).

    Args:
        stone_w: stone width in pixels
        stone_h: stone height in pixels
    Returns (black_patches, white_patches), each a list of (BGR, alpha_mask).
    """
    alpha = _make_elliptical_alpha(stone_w, stone_h, feather=0.12)

    # Distance from center, normalized to [0, 1] (elliptical)
    half_w, half_h = stone_w / 2.0, stone_h / 2.0
    y, x = np.mgrid[:stone_h, :stone_w]
    dist = np.sqrt(((x - half_w + 0.5) / half_w) ** 2 + ((y - half_h + 0.5) / half_h) ** 2)
    dist = np.clip(dist, 0, 1)

    black_patches = []
    white_patches = []
    rng = np.random.RandomState(42)

    for i in range(n_variants):
        # --- Black stone ---
        base_v = rng.uniform(25, 65)
        # Radial darkening toward edges
        v_black = base_v + (1.0 - dist) * 15
        # Specular highlight: Gaussian blob at random offset
        hx = half_w + rng.uniform(-stone_w * 0.15, stone_w * 0.15)
        hy = half_h + rng.uniform(-stone_h * 0.25, -stone_h * 0.05)
        highlight_dist = np.sqrt((x - hx) ** 2 + (y - hy) ** 2)
        sigma = min(stone_w, stone_h) * rng.uniform(0.12, 0.22)
        highlight = np.exp(-0.5 * (highlight_dist / sigma) ** 2) * rng.uniform(40, 80)
        v_black = v_black + highlight
        v_black = np.clip(v_black, 0, 255).astype(np.uint8)
        bgr_black = cv2.merge([v_black, v_black, v_black])
        black_patches.append((bgr_black, alpha.copy()))

        # --- White stone ---
        base_v_w = rng.uniform(215, 245)
        # Edge darkening for 3D look
        v_white = base_v_w - dist * rng.uniform(15, 35)
        # Warm tint: slight +R, -B
        r_shift = rng.uniform(2, 8)
        b_shift = rng.uniform(-6, -1)
        b_ch = np.clip(v_white + b_shift, 0, 255).astype(np.uint8)
        g_ch = np.clip(v_white, 0, 255).astype(np.uint8)
        r_ch = np.clip(v_white + r_shift, 0, 255).astype(np.uint8)
        bgr_white = cv2.merge([b_ch, g_ch, r_ch])
        white_patches.append((bgr_white, alpha.copy()))

    return black_patches, white_patches


def _crop_stone_patch(image: np.ndarray, cx: int, cy: int, half_w: int, half_h: int):
    """Crop a rectangular patch centered at (cx, cy) with an elliptical alpha mask."""
    img_h, img_w = image.shape[:2]
    x1, y1 = cx - half_w, cy - half_h
    x2, y2 = cx + half_w, cy + half_h

    # Skip if too close to edge
    if x1 < 0 or y1 < 0 or x2 > img_w or y2 > img_h:
        return None, None

    patch = image[y1:y2, x1:x2].copy()
    pw, ph = x2 - x1, y2 - y1
    mask = _make_elliptical_alpha(pw, ph, feather=0.12)

    return patch, mask


def _crop_stone_patch_cv(image: np.ndarray, cx: int, cy: int, half_w: int, half_h: int):
    """Crop a stone patch using HoughCircles detection within a 1.5x search ROI.

    Detects circles in a region around the grid intersection, picks the one closest
    to the nominal center, and crops with a circular alpha mask.
    """
    img_h, img_w = image.shape[:2]
    # 1.5x search ROI around intersection
    roi_hw, roi_hh = int(half_w * 1.5), int(half_h * 1.5)
    rx1 = max(0, cx - roi_hw)
    ry1 = max(0, cy - roi_hh)
    rx2 = min(img_w, cx + roi_hw)
    ry2 = min(img_h, cy + roi_hh)

    roi = image[ry1:ry2, rx1:rx2]
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray_roi, (9, 9), 2)

    expected_r = (half_w + half_h) // 2
    min_r = max(int(expected_r * 0.5), 3)
    max_r = int(expected_r * 1.5)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=expected_r,
        param1=80,
        param2=30,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if circles is None:
        return None, None

    # Pick circle closest to nominal grid center (in ROI coords)
    local_cx, local_cy = cx - rx1, cy - ry1
    circles = np.round(circles[0]).astype(int)
    dists = np.sqrt((circles[:, 0] - local_cx) ** 2 + (circles[:, 1] - local_cy) ** 2)
    best = circles[np.argmin(dists)]
    det_x, det_y, det_r = int(best[0]), int(best[1]), int(best[2])

    # Crop with 1.02x padding
    pad_r = int(det_r * 1.02)
    crop_x1 = rx1 + det_x - pad_r
    crop_y1 = ry1 + det_y - pad_r
    crop_x2 = rx1 + det_x + pad_r
    crop_y2 = ry1 + det_y + pad_r

    if crop_x1 < 0 or crop_y1 < 0 or crop_x2 > img_w or crop_y2 > img_h:
        return None, None

    patch = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()
    size = crop_x2 - crop_x1

    # Circular alpha mask from detected radius, feathered
    y, x = np.mgrid[:size, :size]
    center = size / 2.0
    dist = np.sqrt((x - center + 0.5) ** 2 + (y - center + 0.5) ** 2)
    mask = np.clip((det_r - dist) / max(det_r * 0.12, 1.0), 0.0, 1.0)
    mask = (mask * 255).astype(np.uint8)
    mask = cv2.GaussianBlur(mask, (5, 5), 1.5)

    return patch, mask


def _crop_stone_patch_grabcut(
    image: np.ndarray, empty_board: np.ndarray | None, cx: int, cy: int, half_w: int, half_h: int
):
    """Crop a stone patch using GrabCut segmentation.

    If empty_board is available, uses image difference to seed the mask (GC_INIT_WITH_MASK).
    Otherwise falls back to rectangle-based initialization (GC_INIT_WITH_RECT).
    """
    img_h, img_w = image.shape[:2]
    # 2x search ROI for GrabCut
    roi_hw, roi_hh = half_w * 2, half_h * 2
    rx1 = max(0, cx - roi_hw)
    ry1 = max(0, cy - roi_hh)
    rx2 = min(img_w, cx + roi_hw)
    ry2 = min(img_h, cy + roi_hh)

    roi = image[ry1:ry2, rx1:rx2].copy()
    roi_h, roi_w = roi.shape[:2]
    if roi_h < 4 or roi_w < 4:
        return None, None

    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    if empty_board is not None:
        # Diff-seeded mask
        empty_roi = empty_board[ry1:ry2, rx1:rx2]
        diff = np.mean(np.abs(roi.astype(np.float32) - empty_roi.astype(np.float32)), axis=2)

        gc_mask = np.full((roi_h, roi_w), cv2.GC_BGD, dtype=np.uint8)
        gc_mask[diff > 15] = cv2.GC_PR_FGD
        gc_mask[diff > 40] = cv2.GC_FGD

        # Ensure some foreground pixels exist
        if np.sum(gc_mask == cv2.GC_FGD) < 4 and np.sum(gc_mask == cv2.GC_PR_FGD) < 4:
            return None, None

        try:
            cv2.grabCut(roi, gc_mask, None, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_MASK)
        except cv2.error:
            return None, None
    else:
        # Rectangle mode using stone bbox
        local_cx, local_cy = cx - rx1, cy - ry1
        rect_x1 = max(0, local_cx - half_w)
        rect_y1 = max(0, local_cy - half_h)
        rect_w = min(roi_w - rect_x1, half_w * 2)
        rect_h = min(roi_h - rect_y1, half_h * 2)

        if rect_w < 4 or rect_h < 4:
            return None, None

        gc_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
        rect = (rect_x1, rect_y1, rect_w, rect_h)
        try:
            cv2.grabCut(roi, gc_mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
        except cv2.error:
            return None, None

    # Extract foreground
    fg = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # Keep only the connected component closest to the stone center
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fg)
    if num_labels > 1:
        local_cx, local_cy = cx - rx1, cy - ry1
        best_label = None
        best_dist = float("inf")
        for i in range(1, num_labels):  # skip background (label 0)
            ccx, ccy = centroids[i]
            dist = np.sqrt((ccx - local_cx) ** 2 + (ccy - local_cy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_label = i
        fg = np.where(labels == best_label, 255, 0).astype(np.uint8)

    # Morphological close to fill holes
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    # Find tight bounding box of foreground
    coords = cv2.findNonZero(fg)
    if coords is None:
        return None, None

    bx, by, bw, bh = cv2.boundingRect(coords)
    if bw < 4 or bh < 4:
        return None, None

    patch = roi[by : by + bh, bx : bx + bw].copy()
    mask = fg[by : by + bh, bx : bx + bw].copy()
    # Feather edges
    mask = cv2.GaussianBlur(mask, (5, 5), 1.5)

    return patch, mask


# Module-level cache for SAM model to avoid reloading per stone
_SAM_MODEL_CACHE: dict[str, object] = {}


def _crop_stone_patch_sam(image: np.ndarray, cx: int, cy: int, half_w: int, half_h: int, sam_model_name: str):
    """Crop a stone patch using SAM (Segment Anything Model) with a point prompt.

    Uses ultralytics.SAM with a foreground point at (cx, cy). Picks the mask whose
    centroid is closest to the prompt point. Caches the model at module level.
    """
    try:
        from ultralytics import SAM
    except ImportError:
        print("  [sam] ultralytics package not available, skipping SAM crop")
        return None, None

    # Load or retrieve cached model
    if sam_model_name not in _SAM_MODEL_CACHE:
        print(f"  [sam] Loading SAM model: {sam_model_name}")
        _SAM_MODEL_CACHE[sam_model_name] = SAM(sam_model_name)
    model = _SAM_MODEL_CACHE[sam_model_name]

    # Run inference with point prompt
    try:
        results = model(image, points=[[cx, cy]], labels=[1])
    except Exception as e:
        print(f"  [sam] Inference failed: {e}")
        return None, None

    if not results or results[0].masks is None or len(results[0].masks.data) == 0:
        return None, None

    masks = results[0].masks.data.cpu().numpy()

    # Pick mask whose centroid is closest to prompt point,
    # filtering out masks that are too large (board-level segments)
    expected_area = np.pi * half_w * half_h  # approximate stone area
    max_area = expected_area * 6  # allow up to ~6x for shadows/reflections

    best_mask = None
    best_dist = float("inf")
    for i in range(masks.shape[0]):
        m = masks[i]
        ys, xs = np.where(m > 0.5)
        if len(ys) == 0:
            continue
        # Skip masks that are much larger than a stone
        if len(ys) > max_area:
            continue
        mcx, mcy = np.mean(xs), np.mean(ys)
        dist = np.sqrt((mcx - cx) ** 2 + (mcy - cy) ** 2)
        if dist < best_dist:
            best_dist = dist
            best_mask = m

    if best_mask is None:
        return None, None

    # Bounding box of the mask
    binary = (best_mask > 0.5).astype(np.uint8)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return None, None

    bx, by, bw, bh = cv2.boundingRect(coords)
    if bw < 4 or bh < 4:
        return None, None

    # Reject if bounding box is much larger than expected stone size
    if bw > half_w * 6 or bh > half_h * 6:
        return None, None

    img_h, img_w = image.shape[:2]
    # Clamp to image bounds
    bx2, by2 = min(bx + bw, img_w), min(by + bh, img_h)
    bx, by = max(bx, 0), max(by, 0)

    patch = image[by:by2, bx:bx2].copy()
    mask = (binary[by:by2, bx:bx2] * 255).astype(np.uint8)

    return patch, mask


def _crop_stone_patch_dispatch(
    image: np.ndarray,
    empty_board: np.ndarray | None,
    cx: int,
    cy: int,
    half_w: int,
    half_h: int,
    color: str,
    method: str,
    sam_model_name: str,
):
    """Route to the chosen crop method, falling back to fixed crop on failure."""
    patch, mask = None, None

    if method == "fixed":
        patch, mask = _crop_stone_patch(image, cx, cy, half_w, half_h)
    elif method == "cv":
        patch, mask = _crop_stone_patch_cv(image, cx, cy, half_w, half_h)
    elif method == "grabcut":
        patch, mask = _crop_stone_patch_grabcut(image, empty_board, cx, cy, half_w, half_h)
    elif method == "sam":
        patch, mask = _crop_stone_patch_sam(image, cx, cy, half_w, half_h, sam_model_name)
    else:
        raise ValueError(f"Unknown crop method: {method}")

    # Fallback to fixed if chosen method returned nothing
    if patch is None and method != "fixed":
        patch, mask = _crop_stone_patch(image, cx, cy, half_w, half_h)

    # Re-center at grid intersection for non-fixed methods.
    # SAM/grabcut tight bounding boxes can be offset from (cx, cy),
    # causing shadow/side-profile artifacts. Use centered rectangle
    # (same as fixed method) for consistent patch content.
    if patch is not None and method not in ("fixed",):
        y1, y2 = cy - half_h, cy + half_h
        x1, x2 = cx - half_w, cx + half_w
        img_h, img_w = image.shape[:2]
        if 0 <= x1 and 0 <= y1 and x2 <= img_w and y2 <= img_h:
            patch = image[y1:y2, x1:x2].copy()

    # Normalize to standard stone size so synthesize_image's
    # perspective resize starts from the expected aspect ratio
    target_w, target_h = 2 * half_w, 2 * half_h
    if patch is not None and (patch.shape[1] != target_w or patch.shape[0] != target_h):
        patch = cv2.resize(patch, (target_w, target_h), interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # Replace binary masks (SAM/cv/grabcut) with feathered elliptical mask
    # to match the fixed method's smooth blending and prevent hard-edged
    # rectangular artifacts (especially visible on white stones)
    if patch is not None and method != "fixed":
        mask = _make_elliptical_alpha(target_w, target_h, feather=0.12)

    return patch, mask


def _detect_stones_adaptive(warped: np.ndarray, stone_h: int) -> list[tuple[int, int, str]]:
    """Detect stones on the warped board using adaptive thresholds with area sampling.

    Uses median brightness of all 361 intersections as baseline, then:
      - Black: mean_v < median_v - 60
      - White: mean_v > median_v + 15  AND  local stddev < 15

    Returns list of (px, py, color) where color is "B" or "W".
    """
    config = BoardConfig()
    warp_h, warp_w = warped.shape[:2]
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    r = max(stone_h // 3, 3)

    # Area-sample brightness at every intersection
    positions = []
    mean_values = []
    for gy in range(config.grid_size):
        for gx in range(config.grid_size):
            px, py = grid_to_pixel(gx, gy, warp_w, warp_h, config)
            positions.append((px, py))
            y1, y2 = max(0, py - r), min(warp_h, py + r)
            x1, x2 = max(0, px - r), min(warp_w, px + r)
            mean_values.append(float(np.mean(gray[y1:y2, x1:x2])))

    median_v = np.median(mean_values)

    detected: list[tuple[int, int, str]] = []
    for (px, py), v in zip(positions, mean_values):
        if v < median_v - 60:
            detected.append((px, py, "B"))
            continue
        if v > median_v + 15:
            y1, y2 = max(0, py - r), min(warp_h, py + r)
            x1, x2 = max(0, px - r), min(warp_w, px + r)
            local_std = float(np.std(gray[y1:y2, x1:x2]))
            if local_std < 15:
                detected.append((px, py, "W"))

    return detected


def _detect_stones_by_diff(
    warped_stones: np.ndarray, warped_empty: np.ndarray, stone_h: int, threshold: float = 25.0
) -> list[tuple[int, int, str]]:
    """Detect stones by image difference between board-with-stones and empty board.

    Args:
        warped_stones: warped image of board with stones
        warped_empty: warped image of the same board empty
        stone_h: stone height in warped pixels (used for sampling area)
        threshold: mean diff above this → stone present

    Returns list of (px, py, color) where color is "B" or "W".
    """
    config = BoardConfig()
    warp_h, warp_w = warped_stones.shape[:2]
    diff = np.mean(np.abs(warped_stones.astype(np.float32) - warped_empty.astype(np.float32)), axis=2)
    gray = cv2.cvtColor(warped_stones, cv2.COLOR_BGR2GRAY)
    r = max(stone_h // 3, 3)

    detected: list[tuple[int, int, str]] = []
    for gy in range(config.grid_size):
        for gx in range(config.grid_size):
            px, py = grid_to_pixel(gx, gy, warp_w, warp_h, config)
            y1, y2 = max(0, py - r), min(warp_h, py + r)
            x1, x2 = max(0, px - r), min(warp_w, px + r)
            mean_diff = float(np.mean(diff[y1:y2, x1:x2]))
            if mean_diff > threshold:
                mean_gray = float(np.mean(gray[y1:y2, x1:x2]))
                color = "B" if mean_gray < 128 else "W"
                detected.append((px, py, color))

    return detected


def _detect_stones_vision(warped: np.ndarray) -> list[tuple[int, int, str]] | None:
    """Detect stones using Claude Haiku vision API.

    Requires the `anthropic` package and ANTHROPIC_API_KEY env var.
    Returns list of (px, py, color) or None if unavailable.
    """
    import base64
    import json
    import os

    try:
        import anthropic
    except ImportError:
        print("  [vision] anthropic package not installed, skipping vision detection")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [vision] ANTHROPIC_API_KEY not set, skipping vision detection")
        return None

    config = BoardConfig()
    warp_h, warp_w = warped.shape[:2]

    # Resize for API efficiency (max 1024px wide)
    scale = min(1.0, 1024.0 / max(warp_w, warp_h))
    if scale < 1.0:
        small = cv2.resize(warped, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = warped

    _, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "This is a top-down photo of a 19x19 Go board that has been perspective-corrected.\n"
        "Identify ALL stones on the board. For each stone, return its grid column (col, 0-18 left to right) "
        "and grid row (row, 0-18 top to bottom), and color ('B' for black, 'W' for white).\n\n"
        "Return ONLY a JSON array, no other text. Example:\n"
        '[{"color":"B","col":3,"row":5},{"color":"W","col":15,"row":3}]'
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
    except Exception as e:
        print(f"  [vision] API call failed: {e}")
        return None

    # Parse response
    text = response.content[0].text.strip()
    # Extract JSON array from response (may have markdown fences)
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        stones_data = json.loads(text)
    except json.JSONDecodeError:
        print(f"  [vision] Failed to parse JSON response: {text[:200]}")
        return None

    detected: list[tuple[int, int, str]] = []
    for s in stones_data:
        col = int(s["col"])
        row = int(s["row"])
        color = s["color"]
        if 0 <= col < config.grid_size and 0 <= row < config.grid_size and color in ("B", "W"):
            px, py = grid_to_pixel(col, row, warp_w, warp_h, config)
            detected.append((px, py, color))

    print(
        f"  [vision] Claude Haiku detected {len(detected)} stones ({sum(1 for _, _, c in detected if c == 'B')}B + {sum(1 for _, _, c in detected if c == 'W')}W)"
    )
    return detected


def _paste_patch(canvas: np.ndarray, patch: np.ndarray, mask: np.ndarray, cx: int, cy: int):
    """Alpha-blend a patch onto canvas centered at (cx, cy)."""
    ph, pw = patch.shape[:2]
    ch, cw = canvas.shape[:2]

    x1, y1 = cx - pw // 2, cy - ph // 2
    x2, y2 = x1 + pw, y1 + ph

    # Clip source and dest regions
    sx1, sy1 = max(0, -x1), max(0, -y1)
    dx1, dy1 = max(0, x1), max(0, y1)
    dx2, dy2 = min(cw, x2), min(ch, y2)
    sx2, sy2 = sx1 + (dx2 - dx1), sy1 + (dy2 - dy1)

    if dx2 <= dx1 or dy2 <= dy1:
        return

    roi_patch = patch[sy1:sy2, sx1:sx2]
    alpha = mask[sy1:sy2, sx1:sx2].astype(np.float32) / 255.0
    alpha_3 = alpha[:, :, np.newaxis]
    canvas[dy1:dy2, dx1:dx2] = (roi_patch * alpha_3 + canvas[dy1:dy2, dx1:dx2] * (1.0 - alpha_3)).astype(np.uint8)


def _random_augment_patch(patch: np.ndarray, mask: np.ndarray):
    """Randomly flip a patch (preserves aspect ratio for elliptical stones)."""
    if random.random() < 0.5:
        patch = np.flip(patch, axis=1).copy()  # horizontal flip
        mask = np.flip(mask, axis=1).copy()
    if random.random() < 0.5:
        patch = np.flip(patch, axis=0).copy()  # vertical flip
        mask = np.flip(mask, axis=0).copy()
    return patch, mask


def _perspective_transform_points(points: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Transform 2D points through a 3x3 perspective matrix."""
    pts = np.float32(points).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, M).reshape(-1, 2)


# ---------------------------------------------------------------------------
# SGF loading
# ---------------------------------------------------------------------------


def load_game_position(sgf_path: str, move_number: int, board_size: int = 19) -> list[tuple[int, int, str]]:
    """Parse an SGF and return stone positions at move N as vision-grid coordinates.

    Returns list of (gx, gy, color) where gx/gy use top-left origin (vision convention).
    Simplified: does not handle captures (phantom stones from captured groups remain).
    """
    root = SGF.parse_file(sgf_path)

    stones: dict[tuple[int, int], str] = {}

    # Root node may have handicap placements (AB)
    for move in root.move_with_placements:
        if move.coords is not None:
            stones[move.coords] = move.player

    # Walk main line
    node = root
    moves_played = 0
    while node.children and moves_played < move_number:
        node = node.children[0]
        for move in node.move_with_placements:
            if move.coords is not None:
                stones[move.coords] = move.player
        if node.move and not node.move.is_pass:
            moves_played += 1

    # Convert: KaTrain (x, y=bottom-up) -> vision grid (gx, gy=top-down)
    return [(kx, board_size - 1 - ky, color) for (kx, ky), color in stones.items()]


def count_sgf_moves(sgf_path: str) -> int:
    """Count non-pass moves in the main line of an SGF file."""
    root = SGF.parse_file(sgf_path)
    count = 0
    node = root
    while node.children:
        node = node.children[0]
        if node.move and not node.move.is_pass:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------


def synthesize_image(
    assets: SeedAssets,
    positions: list[tuple[int, int, str]],
    off_board_range: tuple[int, int] = (3, 15),
) -> tuple[np.ndarray, list[tuple[int, int, str]], list[tuple[float, float, float, float, str]]]:
    """Synthesize a training image: composite empty board + paste stones in original space.

    Returns:
        (result_image, on_board_stones, off_board_stones)
        on_board_stones: list of (gx, gy, color) in vision grid
        off_board_stones: list of (norm_cx, norm_cy, norm_bw, norm_bh, color) in original image
    """
    config = BoardConfig()
    warp_w, warp_h = assets.warp_size
    orig_h, orig_w = assets.original_shape[:2]

    # Step 1: Warp empty board back to original perspective
    warped_empty = cv2.warpPerspective(
        assets.empty_board,
        assets.inv_transform_matrix,
        (orig_w, orig_h),
        borderMode=cv2.BORDER_REPLICATE,
    )

    # Step 2: Composite empty board onto original using feathered board mask
    mask_f = cv2.GaussianBlur(assets.board_mask, (5, 5), 1.5).astype(np.float32) / 255.0
    mask_f = mask_f[:, :, np.newaxis]
    result = (
        (assets.original_bg.astype(np.float32) * (1.0 - mask_f) + warped_empty.astype(np.float32) * mask_f)
        .clip(0, 255)
        .astype(np.uint8)
    )

    # Step 3: Paste stones directly in original image space
    half_w = int(STONE_BBOX_W * warp_w) // 2
    half_h = int(STONE_BBOX_H * warp_h) // 2
    M_inv = assets.inv_transform_matrix

    on_board_stones = []
    for gx, gy, color in positions:
        wpx, wpy = grid_to_pixel(gx, gy, warp_w, warp_h, config)

        # Stone center in original image
        center = _perspective_transform_points(np.float32([[wpx, wpy]]), M_inv)[0]
        cx, cy = int(round(center[0])), int(round(center[1]))

        # Stone bbox corners in warped space -> original space -> local size
        corners_w = np.float32(
            [
                [wpx - half_w, wpy - half_h],
                [wpx + half_w, wpy - half_h],
                [wpx + half_w, wpy + half_h],
                [wpx - half_w, wpy + half_h],
            ]
        )
        corners_o = _perspective_transform_points(corners_w, M_inv)
        local_w = max(int(round(np.ptp(corners_o[:, 0]))), 4)
        local_h = max(int(round(np.ptp(corners_o[:, 1]))), 4)

        patches = assets.black_patches if color == "B" else assets.white_patches
        patch, mask = random.choice(patches)
        patch, mask = _random_augment_patch(patch, mask)
        patch = cv2.resize(patch, (local_w, local_h), interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask, (local_w, local_h), interpolation=cv2.INTER_AREA)
        _paste_patch(result, patch, mask, cx, cy)
        on_board_stones.append((gx, gy, color))

    # Step 4: Random off-board stones
    n_off = random.randint(*off_board_range)
    off_board_stones = _place_off_board_stones(result, assets, n_off)

    return result, on_board_stones, off_board_stones


def _place_off_board_stones(image: np.ndarray, assets: SeedAssets, count: int):
    """Place random stone patches outside the board area. Returns normalized bbox list."""
    h, w = image.shape[:2]
    placed = []
    all_patches = [(p, m, "B") for p, m in assets.black_patches] + [(p, m, "W") for p, m in assets.white_patches]
    if not all_patches:
        return placed

    sw, sh = assets.stone_size
    margin = max(sw, sh)
    min_dist = margin * 1.5
    attempts = 0
    max_attempts = count * 30

    while len(placed) < count and attempts < max_attempts:
        attempts += 1
        cx = random.randint(margin, w - margin - 1)
        cy = random.randint(margin, h - margin - 1)

        # Must be outside board mask
        if assets.board_mask[cy, cx] > 0:
            continue

        # Must not overlap with previously placed off-board stones
        too_close = any(abs(cx - px) < min_dist and abs(cy - py) < min_dist for px, py, _, _, _ in placed)
        if too_close:
            continue

        patch, mask, color = random.choice(all_patches)
        patch, mask = _random_augment_patch(patch, mask)
        # Resize to standard stone size for consistent off-board appearance
        patch = cv2.resize(patch, (sw, sh), interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask, (sw, sh), interpolation=cv2.INTER_AREA)
        _paste_patch(image, patch, mask, cx, cy)

        bw = sw / w
        bh = sh / h
        placed.append((cx, cy, bw, bh, color))

    # Convert pixel centers to normalized
    return [(px / w, py / h, bw, bh, color) for px, py, bw, bh, color in placed]


# ---------------------------------------------------------------------------
# YOLO label generation
# ---------------------------------------------------------------------------


def generate_labels(
    on_board_stones: list[tuple[int, int, str]],
    off_board_stones: list[tuple[float, float, float, float, str]],
    assets: SeedAssets,
    img_w: int,
    img_h: int,
) -> str:
    """Generate YOLO-format labels for all stones (original image coordinates, normalized)."""
    lines = []
    config = BoardConfig()
    warp_w, warp_h = assets.warp_size
    half_w = int(STONE_BBOX_W * warp_w / 2)
    half_h = int(STONE_BBOX_H * warp_h / 2)

    for gx, gy, color in on_board_stones:
        wpx, wpy = grid_to_pixel(gx, gy, warp_w, warp_h, config)

        # Bbox corners in warped space
        corners = np.float32(
            [
                [wpx - half_w, wpy - half_h],
                [wpx + half_w, wpy - half_h],
                [wpx + half_w, wpy + half_h],
                [wpx - half_w, wpy + half_h],
            ]
        )

        # Transform to original image coordinates
        orig_corners = _perspective_transform_points(corners, assets.inv_transform_matrix)
        xs, ys = orig_corners[:, 0], orig_corners[:, 1]
        cx = np.clip((xs.min() + xs.max()) / 2 / img_w, 0, 1)
        cy = np.clip((ys.min() + ys.max()) / 2 / img_h, 0, 1)
        bw = np.clip((xs.max() - xs.min()) / img_w, 0, 1)
        bh = np.clip((ys.max() - ys.min()) / img_h, 0, 1)

        class_id = 0 if color == "B" else 1
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    for ncx, ncy, nbw, nbh, color in off_board_stones:
        class_id = 0 if color == "B" else 1
        lines.append(f"{class_id} {ncx:.6f} {ncy:.6f} {nbw:.6f} {nbh:.6f}")

    return "\n".join(lines) + "\n" if lines else ""


# ---------------------------------------------------------------------------
# Verification visualization
# ---------------------------------------------------------------------------


def draw_verification(
    image: np.ndarray,
    on_board_stones: list[tuple[int, int, str]],
    off_board_stones: list[tuple[float, float, float, float, str]],
    assets: SeedAssets,
) -> np.ndarray:
    """Draw bounding boxes on image for visual verification."""
    vis = image.copy()
    img_h, img_w = vis.shape[:2]
    config = BoardConfig()
    warp_w, warp_h = assets.warp_size
    half_w = int(STONE_BBOX_W * warp_w / 2)
    half_h = int(STONE_BBOX_H * warp_h / 2)

    for gx, gy, color in on_board_stones:
        wpx, wpy = grid_to_pixel(gx, gy, warp_w, warp_h, config)
        corners = np.float32(
            [
                [wpx - half_w, wpy - half_h],
                [wpx + half_w, wpy - half_h],
                [wpx + half_w, wpy + half_h],
                [wpx - half_w, wpy + half_h],
            ]
        )
        orig_corners = _perspective_transform_points(corners, assets.inv_transform_matrix)
        xs, ys = orig_corners[:, 0], orig_corners[:, 1]
        x1, y1 = int(xs.min()), int(ys.min())
        x2, y2 = int(xs.max()), int(ys.max())
        draw_color = (0, 0, 255) if color == "B" else (255, 255, 255)
        cv2.rectangle(vis, (x1, y1), (x2, y2), draw_color, 2)
        cv2.putText(vis, "B" if color == "B" else "W", (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, draw_color, 1)

    for ncx, ncy, nbw, nbh, color in off_board_stones:
        x1 = int((ncx - nbw / 2) * img_w)
        y1 = int((ncy - nbh / 2) * img_h)
        x2 = int((ncx + nbw / 2) * img_w)
        y2 = int((ncy + nbh / 2) * img_h)
        draw_color = (0, 128, 255) if color == "B" else (200, 200, 0)
        cv2.rectangle(vis, (x1, y1), (x2, y2), draw_color, 2)
        cv2.putText(vis, "B*" if color == "B" else "W*", (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, draw_color, 1)

    return vis


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Synthesize YOLO training data from SGF + seed board photo")
    parser.add_argument("--seed-image", type=str, required=True, help="Seed board photo with ArUco markers")
    parser.add_argument("--sgf-dir", type=str, required=True, help="Directory containing SGF files")
    parser.add_argument("--output", type=str, required=True, help="Output directory (images/ + labels/)")
    parser.add_argument("--max-games", type=int, default=1, help="Max SGF games to process")
    parser.add_argument("--move-interval", type=int, default=10, help="Generate one image every N moves")
    parser.add_argument("--off-board-stones", type=str, default="3-15", help="Off-board stone count range (e.g. 3-15)")
    parser.add_argument("--marker-ids", type=int, nargs=4, default=[0, 1, 2, 3], help="ArUco marker IDs")
    parser.add_argument("--empty-board", type=str, default=None, help="Pre-photographed empty board (best quality)")
    parser.add_argument(
        "--detect-method",
        type=str,
        default="auto",
        choices=["auto", "diff", "vision", "adaptive"],
        help="Stone detection method: auto (diff if empty-board else vision→adaptive), diff, vision, adaptive",
    )
    parser.add_argument("--verify", action="store_true", help="Generate bbox verification images")
    parser.add_argument(
        "--crop-method",
        type=str,
        default="fixed",
        choices=["fixed", "cv", "grabcut", "sam"],
        help="Stone patch crop method: fixed (bbox), cv (HoughCircles), grabcut, sam (Segment Anything)",
    )
    parser.add_argument("--sam-model", type=str, default="mobile_sam.pt", help="SAM model name (default: mobile_sam.pt)")
    args = parser.parse_args()

    off_min, off_max = map(int, args.off_board_stones.split("-"))
    off_board_range = (off_min, off_max)

    # Setup output directories
    output = Path(args.output)
    img_dir = output / "images"
    label_dir = output / "labels"
    assets_dir = output / "assets"
    for d in [img_dir, label_dir, assets_dir]:
        d.mkdir(parents=True, exist_ok=True)
    if args.verify:
        verify_dir = output / "verify"
        verify_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract assets from seed image
    print(f"Extracting assets from: {args.seed_image}")
    assets = extract_assets(
        args.seed_image,
        marker_ids=args.marker_ids,
        empty_board_path=args.empty_board,
        detect_method=args.detect_method,
        crop_method=args.crop_method,
        sam_model_name=args.sam_model,
    )
    sw, sh = assets.stone_size
    print(f"  Empty board: {assets.empty_board.shape[1]}x{assets.empty_board.shape[0]}")
    print(f"  Patches: {len(assets.black_patches)} black, {len(assets.white_patches)} white")
    print(f"  Stone size: {sw}x{sh}px (warped)")
    print(f"  Warp size: {assets.warp_size}")

    # Save intermediate assets
    cv2.imwrite(str(assets_dir / "empty_board.png"), assets.empty_board)
    cv2.imwrite(str(assets_dir / "board_mask.png"), assets.board_mask)
    method_tag = args.crop_method
    for i, (p, _) in enumerate(assets.black_patches):
        cv2.imwrite(str(assets_dir / f"patch_black_{method_tag}_{i}.png"), p)
    for i, (p, _) in enumerate(assets.white_patches):
        cv2.imwrite(str(assets_dir / f"patch_white_{method_tag}_{i}.png"), p)

    # Step 2: Find SGF files
    sgf_dir = Path(args.sgf_dir)
    sgf_files = sorted(sgf_dir.glob("**/*.sgf"))[: args.max_games]
    if not sgf_files:
        print(f"No SGF files found in {sgf_dir}")
        return
    print(f"\nUsing {len(sgf_files)} SGF file(s) from {sgf_dir}")

    # Step 3: Generate synthetic images
    total_images = 0
    total_on_board = 0
    total_off_board = 0

    for game_idx, sgf_path in enumerate(sgf_files):
        print(f"\nGame {game_idx}: {sgf_path.name}")
        try:
            total_moves = count_sgf_moves(str(sgf_path))
        except Exception as e:
            print(f"  Skip (parse error): {e}")
            continue
        print(f"  Total moves: {total_moves}")

        for move_num in range(args.move_interval, total_moves + 1, args.move_interval):
            try:
                positions = load_game_position(str(sgf_path), move_num)
            except Exception as e:
                print(f"  Skip move {move_num}: {e}")
                continue

            result, on_board, off_board = synthesize_image(assets, positions, off_board_range)

            img_h, img_w = result.shape[:2]
            labels_text = generate_labels(on_board, off_board, assets, img_w, img_h)

            name = f"game{game_idx:04d}_move{move_num:03d}"
            cv2.imwrite(str(img_dir / f"{name}.jpg"), result)
            (label_dir / f"{name}.txt").write_text(labels_text)

            total_images += 1
            total_on_board += len(on_board)
            total_off_board += len(off_board)
            print(
                f"  move {move_num:3d}: {len(on_board)} on-board + {len(off_board)} off-board = {len(on_board) + len(off_board)} stones"
            )

            if args.verify:
                vis = draw_verification(result, on_board, off_board, assets)
                cv2.imwrite(str(verify_dir / f"{name}.jpg"), vis)

    print(f"\nDone. Generated {total_images} images.")
    print(f"  On-board stones: {total_on_board}")
    print(f"  Off-board stones: {total_off_board}")
    print(f"  Total annotations: {total_on_board + total_off_board}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
