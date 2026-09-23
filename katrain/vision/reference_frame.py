"""Per-cell comparison against the last frame whose board matched the game record (2026-09-23).

Daylight glare and uneven window light make the detector drop stones it already saw (false negative)
and invent stones on bright patches (false positive). Both are model failures on a board that did not
physically change, so the cheapest evidence is the picture itself.

The comparison is a zero-mean normalised cross-correlation (ZNCC) per cell, not a pixel difference:
a cell that simply got brighter, darker or crossed by a soft shadow edge still correlates ~1, while a
stone appearing, disappearing, changing colour or shifting half a cell destroys the correlation. That
invariance is the whole point -- plain differencing reports "changed" for exactly the lighting events
this is meant to survive.

High correlation is EVIDENCE, not proof (a review of the first draft was right to insist): clipping,
blur and partially averaged transitions can all correlate. The caller therefore bounds how long it may
act on it and never writes the result back into recognition's own history. See the spec.

A cell that cannot be compared -- flat (blown out or pitch black) or mostly clipped -- comes back NaN,
and the caller falls back to the detector. See docs/known-issue-overexposure.md.

Design: superpowers/tracks/vision-reference-frame/design.md
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_pixel_float

# Gray levels. Below this std the patch has no structure to correlate.
MIN_PATCH_STD = 3.0
# A pixel at or above CLIP_LEVEL is blown out, one at or below CRUSH_LEVEL is crushed black. A patch
# with more than MAX_SATURATED_FRACTION of either carries no usable structure even when a surviving
# grid line keeps its std up -- the glare case and its mirror, a corner lost in deep shadow. A black
# stone reads ~20-40 in play, well above CRUSH_LEVEL.
CLIP_LEVEL = 250
CRUSH_LEVEL = 5
MAX_SATURATED_FRACTION = 0.25
# Patch radius as a fraction of one cell. Larger leaks the neighbours' changes in (which only makes
# the rule stay silent, the safe direction); smaller stops covering the stone.
PATCH_RADIUS_CELLS = 0.45
# Sample every Nth pixel of that footprint: a stone-vs-wood-grain difference is far coarser than one
# pixel, and this cuts the per-frame gather, the statistics and the index table by step**2.
SAMPLE_STEP = 2


@dataclass(frozen=True, eq=False)  # holds an ndarray: identity equality and hash, not elementwise
class CellSampler:
    """Which pixels of a warped frame belong to each intersection.

    Built once per (geometry lock, frame size): the warp puts the board on a regular grid, so a
    cell's pixel block never moves until the lock changes.
    """

    img_w: int
    img_h: int
    grid_size: int
    points: int  # samples per cell
    flat_index: np.ndarray  # (grid_size**2, points) int32, into a flattened gray frame

    def sample(self, gray: np.ndarray) -> np.ndarray:
        """(cells, points) float32 blocks, row-major by (row, col)."""
        if gray.shape[:2] != (self.img_h, self.img_w):
            raise ValueError(f"frame {gray.shape[:2]} does not match the sampler {(self.img_h, self.img_w)}")
        return gray.reshape(-1)[self.flat_index].astype(np.float32)


def to_gray(warped: np.ndarray) -> np.ndarray:
    """The image the comparison runs on: warped, but BEFORE the frame averager and BEFORE CLAHE.

    CLAHE is adaptive, so the same cell renders differently when something elsewhere on the board
    changes. The averager shows a new stone at partial weight for several frames, which is exactly the
    window where a veto would erase a move mid-appearance.
    """
    # A 2-D input is copied, never aliased: the caller hands the same buffer on to the averager.
    return cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if warped.ndim == 3 else warped.copy()


def build_sampler(
    img_w: int,
    img_h: int,
    config: BoardConfig | None = None,
    parallax=None,
    radius_cells: float = PATCH_RADIUS_CELLS,
    step: int = SAMPLE_STEP,
) -> CellSampler:
    """Patch centres sit where a stone on that intersection is *imaged*, not on the intersection.

    A stone's centre is above the board, so the camera pushes it outward from the nadir by 1/k --
    the shift `apply_parallax` undoes for detections. Here we go the other way, to aim the patch at
    the stone. Without parallax params the intersection itself is used.
    """
    config = config or BoardConfig()
    grid = config.grid_size
    cell_px = min(
        config.grid_spacing_w / config.total_width * img_w,
        config.grid_spacing_l / config.total_length * img_h,
    )
    patch = min(2 * max(4, int(round(radius_cells * cell_px))), img_w, img_h)
    half = patch // 2
    # From the block's top-left corner, NOT its centre (x0 already subtracts `half`), and started at
    # step // 2 so the samples stay centred on the block: arange(0, ...) would sit step/2 px up-left.
    offsets = np.arange(step // 2, patch, step, dtype=np.int32)

    nadir_x = nadir_y = None
    k = getattr(parallax, "k", None)
    if parallax is not None and k:
        nadir_x, nadir_y = parallax.nadir

    index = np.empty((grid * grid, offsets.size * offsets.size), dtype=np.int32)
    for row in range(grid):
        for col in range(grid):
            fx, fy = float(col), float(row)
            if nadir_x is not None:
                # inverse of apply_parallax: where a stone on this intersection appears
                fx = nadir_x + (fx - nadir_x) / k
                fy = nadir_y + (fy - nadir_y) / k
            px, py = grid_to_pixel_float(fx, fy, img_w, img_h, config)
            x0 = min(max(int(round(px)) - half, 0), img_w - patch)
            y0 = min(max(int(round(py)) - half, 0), img_h - patch)
            index[row * grid + col] = ((y0 + offsets)[:, None] * img_w + (x0 + offsets)[None, :]).reshape(-1)
    return CellSampler(img_w=img_w, img_h=img_h, grid_size=grid, points=index.shape[1], flat_index=index)


def _usable(patches: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(std, usable): a patch is usable when it has structure and is neither mostly blown out nor
    mostly crushed black."""
    std = patches.std(axis=1)
    blown = (patches >= CLIP_LEVEL).mean(axis=1)
    crushed = (patches <= CRUSH_LEVEL).mean(axis=1)
    return std, (std >= MIN_PATCH_STD) & (blown <= MAX_SATURATED_FRACTION) & (crushed <= MAX_SATURATED_FRACTION)


class ReferenceFrame:
    """One reference: the normalised cell patches of a frame plus the board it is known to show."""

    def __init__(self, sampler: CellSampler, gray: np.ndarray, board: np.ndarray):
        patches = sampler.sample(gray)
        std, usable = _usable(patches)
        self.sampler = sampler
        self.board = np.array(board, dtype=int, copy=True)
        self.usable = usable
        self.normalised = (patches - patches.mean(axis=1, keepdims=True)) / np.where(usable, std, 1.0)[:, None]

    def similarity(self, gray: np.ndarray) -> np.ndarray:
        """(grid, grid) float32 ZNCC in [-1, 1]; NaN where either frame's patch cannot be compared."""
        patches = self.sampler.sample(gray)
        std, usable = _usable(patches)
        usable &= self.usable
        normalised = (patches - patches.mean(axis=1, keepdims=True)) / np.where(usable, std, 1.0)[:, None]
        zncc = (self.normalised * normalised).sum(axis=1) / normalised.shape[1]
        return np.where(usable, zncc, np.nan).astype(np.float32).reshape(self.sampler.grid_size, -1)

    def unchanged(self, gray: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray]:
        """(mask, similarity): mask is True where the cell is structurally the same as the reference.
        Evidence that its occupancy is still `self.board` -- see the module docstring on how far the
        caller may act on it."""
        sim = self.similarity(gray)
        return np.nan_to_num(sim, nan=-1.0) >= threshold, sim
