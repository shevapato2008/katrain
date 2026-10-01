"""Pure, immutable SGF truth for a later admin capture transaction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from katrain.core.baipu import build_steps_from_sgf
from katrain.core.game import IllegalMoveException, KaTrainSGF
from katrain.core.sgf_parser import ParseError

MAX_SGF_BYTES = 2 * 1024 * 1024


class VisionSgfError(ValueError):
    """Invalid input suitable for a later HTTP 422 response."""


@dataclass(frozen=True)
class VisionSgfPoint:
    row: int
    col: int


@dataclass(frozen=True)
class VisionSgfStep:
    kind: str
    move_index: int
    property: str
    row: int | None
    col: int | None
    color: str | None
    removed: tuple[VisionSgfPoint, ...]
    board_hash: str


@dataclass(frozen=True)
class PreparedVisionSgf:
    original_sgf: str
    sgf_sha256: str
    game_id: str
    board_size: int
    steps: tuple[VisionSgfStep, ...]
    placement_indices: tuple[int, ...]

    def next_placement_index(self, after: int = -1) -> int | None:
        return next((index for index in self.placement_indices if index > after), None)


def prepare_vision_sgf(sgf: str) -> PreparedVisionSgf:
    """Validate a bounded 19×19 record and prepare truth; never persist or open devices."""
    if not isinstance(sgf, str):
        raise VisionSgfError("SGF must be UTF-8 text")
    # Every UTF-8 character needs at least one byte; reject huge text before allocating bytes.
    if len(sgf) > MAX_SGF_BYTES:
        raise VisionSgfError("SGF must be at most 2 MiB")
    try:
        encoded = sgf.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise VisionSgfError("SGF must be UTF-8 text") from exc
    if len(encoded) > MAX_SGF_BYTES:
        raise VisionSgfError("SGF must be at most 2 MiB")

    source = sgf.strip()
    try:
        if not re.match(r"\(\s*;", source):
            raise VisionSgfError("SGF must contain one complete game tree")
        # parse_sgf clips surrounding content; inspect the direct parse to reject trailing junk.
        parsed = KaTrainSGF(source)
        if source[parsed.ix :].strip():
            raise VisionSgfError("SGF must contain one complete game tree")
        # build_steps_from_sgf only returns width. Both source dimensions are authoritative.
        if len(parsed.root.get_list_property("SZ", [])) > 1 or parsed.root.board_size != (19, 19):
            raise VisionSgfError("Only 19×19 SGF boards are supported")
        # The shared parser tolerates long coordinates and clips out-of-board setup ranges.
        # Reject those inputs before replay so no supplied placement silently disappears.
        nodes = [parsed.root]
        while nodes:
            node = nodes.pop()
            nodes.extend(node.children)
            if len(node.get_list_property("B", [])) + len(node.get_list_property("W", [])) > 1:
                raise VisionSgfError("SGF contains multiple moves in one node")
            for prop in ("B", "W", "AB", "AW", "AE"):
                for point in node.get_list_property(prop, []):
                    if prop in ("B", "W") and point in ("", "tt"):
                        continue
                    pattern = r"[a-s]{2}" if prop in ("B", "W") else r"[a-s]{2}(?::[a-s]{2})?"
                    if not re.fullmatch(pattern, point):
                        raise VisionSgfError("SGF contains an invalid board point")
                    if ":" in point:
                        start, end = point.split(":")
                        if start[0] > end[0] or start[1] > end[1]:
                            raise VisionSgfError("SGF contains an inverted setup range")
        data = build_steps_from_sgf(source)
    except (ParseError, IllegalMoveException, ValueError, TypeError, IndexError, RecursionError) as exc:
        if isinstance(exc, VisionSgfError):
            raise
        raise VisionSgfError("SGF cannot be parsed or replayed") from exc

    digest = hashlib.sha256(encoded).hexdigest()
    steps = tuple(
        VisionSgfStep(**{**step, "removed": tuple(VisionSgfPoint(**point) for point in step["removed"])})
        for step in data["steps"]
    )
    return PreparedVisionSgf(
        original_sgf=sgf,
        sgf_sha256=digest,
        game_id=f"sgf-{digest}",
        board_size=data["board_size"],
        steps=steps,
        placement_indices=tuple(step.move_index for step in steps if step.kind in ("setup", "move")),
    )
