"""L2 QA (decision ③): compare the physical board against the expected board.

The classical-CV classifier (ported ``stone_classifier``) plus the locked
geometry give us a (19,19) read of the physical board; we diff it against the
backend-authoritative expected board (from the SGF). A mismatch blocks the
capture (operator can correct, or override) so we never write a poisoned frame.

The classifier's (19,19) array is already in canonical orientation: the warp maps
corners TL/TR/BR/BL to a square, so row index = top→bottom, col index = left→right.
"""

from __future__ import annotations

from typing import List, Optional

from katrain.vision import stone_classifier

_CODE_TO_COLOR = {
    stone_classifier.EMPTY: None,
    stone_classifier.BLACK: "B",
    stone_classifier.WHITE: "W",
}


def classify_canonical(frame, geometry) -> List[List[Optional[str]]]:
    """Warp ``frame`` by the locked geometry and classify → (19,19) of 'B'/'W'/None."""
    import cv2

    warp = cv2.warpPerspective(frame, geometry.M, (geometry.out_size, geometry.out_size))
    state, _ = stone_classifier.classify(warp, geometry.xs, geometry.ys, geometry.baseline)
    n = state.shape[0]
    return [[_CODE_TO_COLOR[int(state[r][c])] for c in range(n)] for r in range(n)]


def diff_expected(expected: List[List[Optional[str]]], classified: List[List[Optional[str]]]) -> List[dict]:
    """Return mismatches as ``[{row, col, expected, actual, reason}]`` (canonical coords).

    ``reason`` ∈ {missing (expected stone, none seen), extra (unexpected stone),
    color_mismatch (wrong color)}. ``expected``/``actual`` use 'B'/'W'/'empty'.
    """
    diffs: List[dict] = []
    for r in range(len(expected)):
        for c in range(len(expected[r])):
            e = expected[r][c]
            a = classified[r][c]
            if e == a:
                continue
            if e is not None and a is None:
                reason = "missing"
            elif e is None and a is not None:
                reason = "extra"
            else:
                reason = "color_mismatch"
            diffs.append({"row": r, "col": c, "expected": e or "empty", "actual": a or "empty", "reason": reason})
    return diffs
