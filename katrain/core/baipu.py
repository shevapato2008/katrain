"""Pure FF4 SGF record replay and authoritative physical-board instructions.

A recorded move is an instruction even when illegal in live Go: replace the
point, capture adjacent opponents, then remove a zero-liberty own group. Setup
assignments never capture. Live gameplay remains governed by BaseGame.
"""

import hashlib
from typing import Any, Dict, List

from katrain.core.baipu_identity import BAIPU_REPLAY_VERSION
from katrain.core.sgf_parser import Move, SGF


def _board_hash(board) -> str:
    """Retain the legacy hash for positions unchanged by the FF4 interpretation."""
    size = len(board)
    stones = sorted((c, size - 1 - r, color) for r, row in enumerate(board) for c, color in enumerate(row) if color)
    return hashlib.sha1(repr(stones).encode("utf-8")).hexdigest()[:16]


def _point(value: str, size: int):
    if len(value) != 2 or any(c not in Move.SGF_COORD for c in value):
        raise ValueError(f"invalid SGF coordinate: {value!r}")
    col, row = (Move.SGF_COORD.index(c) for c in value)
    if not (0 <= row < size and 0 <= col < size):
        raise ValueError(f"SGF coordinate {value!r} outside {size}x{size} board")
    return row, col


def _setup_points(values, size):
    """Expand in raw value order, retaining repeated setup operations."""
    points = []
    for value in values:
        if ":" not in value:
            points.append(_point(value, size))
            continue
        endpoints = value.split(":")
        if len(endpoints) != 2:
            raise ValueError(f"invalid setup coordinate range: {value!r}")
        (r0, c0), (r1, c1) = (_point(v, size) for v in endpoints)
        if r0 > r1 or c0 > c1:
            raise ValueError(f"reversed setup coordinate range: {value!r}")
        points.extend((r, c) for c in range(c0, c1 + 1) for r in range(r0, r1 + 1))
    return points


def _neighbors(point, size):
    row, col = point
    for r, c in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
        if 0 <= r < size and 0 <= c < size:
            yield r, c


def _group(board, point):
    color = board[point[0]][point[1]]
    group, pending, has_liberty = {point}, [point], False
    while pending:
        for r, c in _neighbors(pending.pop(), len(board)):
            if board[r][c] is None:
                has_liberty = True
            elif board[r][c] == color and (r, c) not in group:
                group.add((r, c))
                pending.append((r, c))
    return group, has_liberty


def _captures(board, point, color):
    removed = set()
    for r, c in _neighbors(point, len(board)):
        if board[r][c] is not None and board[r][c] != color:
            group, liberty = _group(board, (r, c))
            if not liberty:
                removed.update(group)
                for rr, cc in group:
                    board[rr][cc] = None
    group, liberty = _group(board, point)
    if not liberty:
        removed.update(group)
        for r, c in group:
            board[r][c] = None
    return [{"row": r, "col": c} for r, c in sorted(removed)]


def build_steps_from_sgf(sgf: str) -> Dict[str, Any]:
    """Emit dense setup/move/pass/clear steps in canonical row0-top coordinates.

    ``pre_removed`` precedes assignment; ``removed`` follows it and may contain
    the newly assigned stone. ``requires_placement`` describes a physical action,
    while the recorded operation and its original dense index are always kept.
    """
    root = SGF.parse_sgf(sgf)
    size, height = root.board_size
    if size != height or not 1 <= size <= len(Move.SGF_COORD):
        raise ValueError("SGF board size must be square and between 1 and 52")
    board = [[None] * size for _ in range(size)]
    steps: List[Dict[str, Any]] = []

    def append(kind, prop, point=None, color=None, pre_removed=None, removed=None, requires_placement=False):
        steps.append(
            {
                "kind": kind,
                "move_index": len(steps),
                "property": prop,
                "row": point[0] if point is not None else None,
                "col": point[1] if point is not None else None,
                "color": color,
                "pre_removed": pre_removed or [],
                "removed": removed or [],
                "requires_placement": requires_placement,
                "board_hash": _board_hash(board),
            }
        )

    node = root
    while node is not None:
        setup = {prop: _setup_points(node.get_list_property(prop, []), size) for prop in ("AB", "AW", "AE")}
        if set(setup["AB"]) & set(setup["AW"]):
            raise ValueError("conflicting AB/AW setup coordinates in one node")
        if set(setup["AE"]) & (set(setup["AB"]) | set(setup["AW"])):
            raise ValueError("conflicting AE/setup coordinates in one node")
        for prop, color in (("AB", "B"), ("AW", "W")):
            for point in setup[prop]:
                r, c = point
                old = board[r][c]
                board[r][c] = color
                append(
                    "setup",
                    prop,
                    point,
                    color,
                    pre_removed=[{"row": r, "col": c}] if old and old != color else [],
                    requires_placement=old != color,
                )
        for color in Move.PLAYERS:
            for value in node.get_list_property(color, []):
                if value == "" or (value == "tt" and size <= 19):
                    append("pass", color)
                    continue
                point = _point(value, size)
                r, c = point
                old = board[r][c]
                board[r][c] = color
                removed = _captures(board, point, color)
                append(
                    "move",
                    color,
                    point,
                    color,
                    pre_removed=[{"row": r, "col": c}] if old and old != color else [],
                    removed=removed,
                    requires_placement=old != color,
                )
        cleared = []
        for r, c in setup["AE"]:
            if board[r][c] is not None:
                board[r][c] = None
                cleared.append({"row": r, "col": c})
        if cleared:
            append("clear", "AE", removed=cleared)
        node = node.children[0] if node.children else None

    meta = {
        "player_black": root.get_property("PB", "") or "",
        "player_white": root.get_property("PW", "") or "",
        "player_black_rank": root.get_property("BR") or None,
        "player_white_rank": root.get_property("WR") or None,
        "result": root.get_property("RE", "") or "",
        "handicap": int(root.handicap or 0),
        "komi": float(root.komi),
        "ruleset": root.ruleset,
    }
    return {"board_size": size, "steps": steps, "meta": meta, "replay_version": BAIPU_REPLAY_VERSION}


def expected_board_from_steps(steps: List[Dict[str, Any]], k: int, board_size: int = 19):
    """Canonical board after steps[0..k]; k=-1 yields the empty board."""
    board = [[None] * board_size for _ in range(board_size)]
    for s in steps[: max(0, min(k + 1, len(steps)))]:
        for rm in s.get("pre_removed", []):
            board[rm["row"]][rm["col"]] = None
        if s["kind"] in ("setup", "move") and s["row"] is not None:
            board[s["row"]][s["col"]] = s["color"]
        for rm in s.get("removed", []):
            board[rm["row"]][rm["col"]] = None
    return board


NON_PLACEMENT_KINDS = ("pass", "clear")


def next_placement_index(steps: List[Dict[str, Any]], after: int):
    """First later recorded operation that needs a new physical stone."""
    for j in range(after + 1, len(steps)):
        if steps[j]["kind"] not in NON_PLACEMENT_KINDS and steps[j].get("requires_placement", True):
            return j
    return None


def next_guided_placement_index(steps: List[Dict[str, Any]], after: int):
    """Skip only physical no-ops; pending removal keeps collection LEDs dark."""
    for j in range(after + 1, len(steps)):
        step = steps[j]
        if step.get("pre_removed") or step.get("removed") or step["kind"] == "clear":
            return None
        if step["kind"] not in NON_PLACEMENT_KINDS and step.get("requires_placement", True):
            return j
    return None


def validate_capture_archive(manifest, sgf: str, steps, board_size: int, archived_sgf: str):
    """Require evidence that archived frames use this exact replay interpretation.

    Shared by collection and offline autolabel. Validation is pure and must run
    before idempotent reuse, deletion, capture, or output. Unversioned archives
    are accepted only when every real-step hash proves compatibility. Historical
    initial-empty frames may omit a hash because their position is unambiguous.
    """
    from katrain.core.baipu_identity import sgf_sha256

    def reject(reason):
        raise ValueError(f"incompatible baipu archive: {reason}; preserve archive and start a new game_id")

    if not isinstance(manifest, dict):
        reject("invalid manifest")
    version = manifest.get("replay_version")
    if version is not None and (type(version) is not int or version != BAIPU_REPLAY_VERSION):
        reject("replay version differs")
    if archived_sgf != sgf:
        reject("frozen SGF differs from requested SGF")
    pinned_hash = manifest.get("sgf_sha256")
    if (pinned_hash is not None or version is not None) and pinned_hash != sgf_sha256(sgf):
        reject("SGF hash is missing or differs")
    if type(manifest.get("board_size")) is not int or manifest["board_size"] != board_size:
        reject("board size differs")
    count = manifest.get("total_steps")
    if (count is not None or version is not None) and (type(count) is not int or count != len(steps)):
        reject("step count differs")
    frames = manifest.get("frames")
    if not isinstance(frames, list):
        reject("frames are missing")
    empty_hash = _board_hash([[None] * board_size for _ in range(board_size)])
    for frame in frames:
        if not isinstance(frame, dict) or not isinstance(frame.get("file"), str) or not frame["file"]:
            reject("invalid frame entry")
        index = frame.get("applied_move_index")
        if type(index) is not int or not -1 <= index < len(steps):
            reject("frame step index is invalid")
        if "board_through_index" in frame and (
            type(frame["board_through_index"]) is not int or frame["board_through_index"] != index
        ):
            reject("frame board index differs")
        guided = frame.get("next_guided_move_index")
        if guided is not None and (type(guided) is not int or not index < guided < len(steps)):
            reject("frame guidance index is invalid")
        expected = empty_hash if index == -1 else steps[index]["board_hash"]
        actual = frame.get("board_hash")
        if index == -1 and actual is None:
            continue
        if not actual or actual != expected:
            reject(f"frame board hash is missing or differs at step {index}")
