"""Deterministic detection corpus that characterizes BoardStateExtractor (vision-stone-parallax track).

The golden file was produced by the pre-parallax extractor. With parallax off, the extractor must
reproduce it bit-for-bit (prd P1-1 acceptance 1). The corpus covers every path the parallax change
touches: on-grid stones with jitter, cell-boundary straddlers (sticky / spill), same-point
collisions, warp-margin objects on both sides of the drop line, LED classes, lit-cell masks,
hysteresis, presence sustain and colour flips carried across frames.

Regenerate ONLY from a commit whose board_state.py predates the parallax change:
    .venv/bin/python -m tests.test_vision.board_state_corpus --write
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.stone_detector import Detection

GOLDEN_PATH = Path(__file__).parent / "data" / "board_state_golden.json"
IMG = 1056  # 950 + 2 * 53: the geometry-lock warp canvas with its 1-cell margin
FRAMES = 24
SEED = 20260922
CONFIGS = {
    "margin": lambda: BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS),
    "plain": lambda: BoardConfig(),
}


def grid_to_px(cfg, fx, fy, img=IMG):
    """Inverse of pixel_to_physical + continuous_grid_pos: continuous grid (fx, fy) -> warped pixel."""
    gs = cfg.grid_size - 1
    x_mm = cfg.border_width_mm + fx * cfg.board_width_mm / gs
    y_mm = cfg.border_length_mm + fy * cfg.board_length_mm / gs
    return x_mm * img / cfg.total_width, y_mm * img / cfg.total_length


def build_frames(cfg, seed=SEED):
    rng = np.random.default_rng(seed)
    scene = {}
    frames = []

    def det(fx, fy, cls, conf):
        x, y = grid_to_px(cfg, fx, fy)
        return Detection(x_center=float(x), y_center=float(y), class_id=int(cls), confidence=float(conf))

    for t in range(FRAMES):
        for _ in range(2):
            r, c = (int(v) for v in rng.integers(0, 19, 2))
            scene[(r, c)] = int(rng.integers(0, 2))
        keys = sorted(scene)
        if keys and rng.random() < 0.3:
            del scene[keys[int(rng.integers(0, len(keys)))]]
        keys = sorted(scene)
        if keys and rng.random() < 0.3:
            k = keys[int(rng.integers(0, len(keys)))]
            scene[k] = 1 - scene[k]
        dets = []
        for (r, c), cls in sorted(scene.items()):
            jx, jy = rng.normal(0, 0.15, 2)
            dets.append(det(c + jx, r + jy, cls, rng.uniform(0.3, 0.95)))
        for _ in range(3):  # cell-boundary straddlers (sticky / spill)
            r, c = (int(v) for v in rng.integers(0, 19, 2))
            off = float(rng.choice([-0.5, 0.5]) + rng.normal(0, 0.05))
            fx, fy = (c + off, r) if rng.random() < 0.5 else (c, r + off)
            dets.append(det(fx, fy, rng.integers(0, 2), rng.uniform(0.3, 0.95)))
        for _ in range(2):  # same-point collisions
            if scene:
                r, c = sorted(scene)[int(rng.integers(0, len(scene)))]
                jx, jy = rng.normal(0, 0.1, 2)
                dets.append(det(c + jx, r + jy, rng.integers(0, 2), rng.uniform(0.3, 0.95)))
        for _ in range(4):  # warp-margin objects on all four sides, both sides of the drop line
            u, v = float(rng.uniform(-0.95, -0.3)), float(rng.uniform(0, 18))
            fx, fy = [(u, v), (18 - u, v), (v, u), (v, 18 - u)][int(rng.integers(0, 4))]
            dets.append(det(fx, fy, rng.integers(0, 4), rng.uniform(0.3, 0.95)))
        for _ in range(2):  # LED-class detections on the grid
            r, c = (int(v) for v in rng.integers(0, 19, 2))
            dets.append(det(c, r, rng.integers(2, 4), rng.uniform(0.3, 0.95)))
        masked = {tuple(int(v) for v in rng.integers(0, 19, 2)) for _ in range(3)}
        add_threshold = None if t % 3 == 0 else 0.5
        frames.append((dets, masked, add_threshold))
    return frames


def _board_str(board):
    return "".join(str(int(v)) for v in np.asarray(board).ravel())


def run(extractor, frames):
    """Every BoardStateExtractor output the parallax change can reach, frame by frame, on ONE
    extractor instance (the colour-flip streak is instance state carried across frames)."""
    out = []
    prev_stable = None
    prev_raw = None
    for dets, masked, add_threshold in frames:
        cells = [extractor._grid_cell(d, IMG, IMG) for d in dets]
        legacy = extractor.detections_to_board(
            dets,
            IMG,
            IMG,
            occupancy_aware=False,
            masked_cells=masked,
            prev_board=prev_stable,
            add_threshold=add_threshold,
        )
        occ = extractor.detections_to_board(
            dets,
            IMG,
            IMG,
            occupancy_aware=True,
            masked_cells=masked,
            prev_board=prev_stable,
            add_threshold=add_threshold,
            sticky_board=prev_raw,
        )
        out.append(
            {
                "grid_cell": [None if g is None else [int(g[0]), int(g[1])] for g in cells],
                "points": [
                    [float(fy), float(fx), int(cls), float(conf)]
                    for fy, fx, cls, conf in extractor.detection_points(dets, IMG, IMG)
                ],
                "legacy": _board_str(legacy),
                "occupancy": _board_str(occ),
                "cell_top": sorted(
                    [int(r), int(c), float(conf), int(cls)]
                    for (r, c), (conf, cls) in extractor.cell_top(dets, IMG, IMG).items()
                ),
                "cell_conf": sorted(
                    [int(r), int(c), float(v)] for (r, c), v in extractor.cell_confidences(dets, IMG, IMG).items()
                ),
            }
        )
        prev_raw = occ
        prev_stable = occ.copy()
    return out


def run_all(make_extractor):
    """make_extractor(config) -> BoardStateExtractor; returns {config name: [per-frame outputs]}."""
    return {name: run(make_extractor(factory()), build_frames(factory())) for name, factory in CONFIGS.items()}


def _write_golden():
    import katrain.vision.board_state as board_state

    if "parallax" in Path(board_state.__file__).read_text():
        sys.exit("refusing: board_state.py already knows about parallax; the golden must come from pre-parallax code")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    payload = {"generated_at_commit": commit, "outputs": run_all(BoardStateExtractor)}
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"wrote {GOLDEN_PATH} ({GOLDEN_PATH.stat().st_size} bytes) from {commit}")


if __name__ == "__main__":
    if sys.argv[1:] != ["--write"]:
        sys.exit("usage: python -m tests.test_vision.board_state_corpus --write")
    _write_golden()
