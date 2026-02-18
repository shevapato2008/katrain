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
        patch, mask = _crop_stone_patch(warped, px, py, half_w, half_h)
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


def _stamp_alpha(alpha_canvas: np.ndarray, mask: np.ndarray, cx: int, cy: int):
    """Stamp stone mask onto alpha canvas using max blending."""
    ph, pw = mask.shape[:2]
    ch, cw = alpha_canvas.shape[:2]
    x1, y1 = cx - pw // 2, cy - ph // 2
    x2, y2 = x1 + pw, y1 + ph
    sx1, sy1 = max(0, -x1), max(0, -y1)
    dx1, dy1 = max(0, x1), max(0, y1)
    dx2, dy2 = min(cw, x2), min(ch, y2)
    sx2, sy2 = sx1 + (dx2 - dx1), sy1 + (dy2 - dy1)
    if dx2 <= dx1 or dy2 <= dy1:
        return
    roi_mask = mask[sy1:sy2, sx1:sx2]
    np.maximum(alpha_canvas[dy1:dy2, dx1:dx2], roi_mask, out=alpha_canvas[dy1:dy2, dx1:dx2])


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
    """Synthesize a training image: stones on empty board -> inverse warp -> composite.

    Returns:
        (result_image, on_board_stones, off_board_stones)
        on_board_stones: list of (gx, gy, color) in vision grid
        off_board_stones: list of (norm_cx, norm_cy, norm_bw, norm_bh, color) in original image
    """
    config = BoardConfig()
    warped = assets.empty_board.copy()
    warp_h, warp_w = warped.shape[:2]

    # Pad warped board so edge stones aren't clipped
    pad_x = int(STONE_BBOX_W * warp_w) // 2 + 2
    pad_y = int(STONE_BBOX_H * warp_h) // 2 + 2
    warped = cv2.copyMakeBorder(warped, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_REPLICATE)

    # Alpha canvas: 255 inside board region, 0 in padding (transparent)
    alpha_canvas = np.zeros(warped.shape[:2], dtype=np.uint8)
    alpha_canvas[pad_y : pad_y + warp_h, pad_x : pad_x + warp_w] = 255

    # Place stones in warped space (offset by padding)
    on_board_stones = []
    for gx, gy, color in positions:
        px, py = grid_to_pixel(gx, gy, warp_w, warp_h, config)
        px += pad_x
        py += pad_y
        patches = assets.black_patches if color == "B" else assets.white_patches
        patch, mask = random.choice(patches)
        patch, mask = _random_augment_patch(patch, mask)
        _paste_patch(warped, patch, mask, px, py)
        _stamp_alpha(alpha_canvas, mask, px, py)
        on_board_stones.append((gx, gy, color))

    # Adjust inverse transform for padded canvas: shift back before warping
    T_shift = np.eye(3, dtype=np.float64)
    T_shift[0, 2] = -pad_x
    T_shift[1, 2] = -pad_y
    M_inv_padded = assets.inv_transform_matrix @ T_shift

    # Inverse warp with selective alpha compositing.
    # alpha_canvas: 255 inside board region, 0 in padding, stone mask in padding overlap.
    # Bilinear interpolation at board boundaries produces soft alpha transitions.
    orig_h, orig_w = assets.original_shape[:2]
    warped_rgba = np.concatenate([warped, alpha_canvas[:, :, np.newaxis]], axis=2)
    warped_back = cv2.warpPerspective(warped_rgba, M_inv_padded, (orig_w, orig_h))

    # Alpha composite onto background
    alpha_f = warped_back[:, :, 3:4].astype(np.float32) / 255.0
    result = (
        (assets.original_bg.astype(np.float32) * (1.0 - alpha_f) + warped_back[:, :, :3].astype(np.float32))
        .clip(0, 255)
        .astype(np.uint8)
    )

    # Random off-board stones
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
    )
    sw, sh = assets.stone_size
    print(f"  Empty board: {assets.empty_board.shape[1]}x{assets.empty_board.shape[0]}")
    print(f"  Patches: {len(assets.black_patches)} black, {len(assets.white_patches)} white")
    print(f"  Stone size: {sw}x{sh}px (warped)")
    print(f"  Warp size: {assets.warp_size}")

    # Save intermediate assets
    cv2.imwrite(str(assets_dir / "empty_board.png"), assets.empty_board)
    cv2.imwrite(str(assets_dir / "board_mask.png"), assets.board_mask)
    for i, (p, _) in enumerate(assets.black_patches[:5]):
        cv2.imwrite(str(assets_dir / f"patch_black_{i}.png"), p)
    for i, (p, _) in enumerate(assets.white_patches[:5]):
        cv2.imwrite(str(assets_dir / f"patch_white_{i}.png"), p)

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
