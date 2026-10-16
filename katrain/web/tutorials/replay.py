"""Server replay proof; static printed labels never become move history.

Coordinates at this boundary are full-board, top-left coordinates. KaTrain's
Move coordinates are bottom-left, so convert exactly once at the rule boundary.
"""

from collections import deque
from types import SimpleNamespace

from katrain.core.sgf_parser import Move


def _inside(point, region):
    return bool(
        region
        and region["col"] <= point[0] < region["col"] + region["cols"]
        and region["row"] <= point[1] < region["row"] + region["rows"]
    )


def _neighbors(point, size):
    x, y = point
    return [
        (nx, ny) for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if 0 <= nx < size and 0 <= ny < size
    ]


def _board(stones):
    return {tuple(point): color for color in ("B", "W") for point in stones.get(color, [])}


def _group(board, point, size):
    color = board.get(point)
    group, queue = set(), deque([point])
    while queue:
        current = queue.popleft()
        if current in group or board.get(current) != color:
            continue
        group.add(current)
        queue.extend(
            neighbor for neighbor in _neighbors(current, size) if neighbor not in group and board.get(neighbor) == color
        )
    return group


def _liberties(board, group, size, region, unknown):
    empty = {neighbor for point in group for neighbor in _neighbors(point, size) if neighbor not in board}
    known = {point for point in empty if _inside(point, region) and point not in unknown}
    return len(known), bool(empty - known)


def _uncertain_move(board, point, color, size, region, unknown):
    """Prove captures and survival without treating unseen points as empty."""
    candidate = {**board, point: color}
    checked = set()
    for neighbor in _neighbors(point, size):
        if neighbor in checked or candidate.get(neighbor) in (None, color):
            continue
        group = _group(candidate, neighbor, size)
        checked.update(group)
        known, unseen = _liberties(candidate, group, size, region, unknown)
        if known == 0 and unseen:
            return "capture depends on unknown neighboring points"
        if known == 0:
            for captured in group:
                candidate.pop(captured)
    known, unseen = _liberties(candidate, _group(candidate, point, size), size, region, unknown)
    if known == 0 and unseen:
        return "own group survival depends on unknown neighboring points"
    return None


def validate_replay(payload: dict) -> dict:
    """Return computed playability and issues, including for an incomplete draft."""
    issues = []
    replay = payload.get("replay")
    result = lambda: {"status": "needs_calibration" if issues else "complete", "issues": issues}
    if payload.get("schema_version") != 2 or not replay:
        issues.append("Explicit v2 initial state and moves are required")
        return result()
    if replay.get("status") != "complete":
        issues.append("Replay is a calibration draft")
    if not replay.get("moves"):
        issues.append("A static final position with zero moves is not a replay")
    evidence = replay.get("evidence") or {}
    if not evidence.get("description", "").strip() or not evidence.get("source_pointer", "").strip():
        issues.append("Source evidence for initial state and ordered moves is required")
    if evidence.get("kind") == "linked_record":
        digest = evidence.get("reference_sha256") or ""
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            issues.append("Linked record evidence requires its immutable SHA256")
    source = payload.get("source_region")
    if not source or not source.get("confirmed"):
        issues.append("A confirmed source region is required")
    if payload.get("unknown_stones"):
        issues.append("Static diagram contains unknown stones")
    initial = replay.get("initial")
    if not initial:
        issues.append("A known initial state is required")
        return result()
    region = initial.get("known_region")
    if not region:
        issues.append("Initial known_region must declare the known empty extent")
        return result()
    unknown = {tuple(stone["point"]) for stone in initial.get("unknown_stones", [])}
    if unknown:
        issues.append("Initial state contains unknown stones")
    turn = initial.get("to_play")
    if turn not in ("B", "W"):
        issues.append("Initial to_play must explicitly declare B or W")
        return result()
    # Import lazily: the core rules are shared with the game, not copied here.
    from katrain.core.game import BaseGame, IllegalMoveException
    from katrain.core.game_node import GameNode

    size = payload.get("size", 19)

    def move(point, color):
        return Move(coords=None if point is None else (point[0], size - point[1] - 1), player=color)

    properties = {"SZ": size, "RU": "japanese", "PL": turn}
    for color in ("B", "W"):
        properties["A" + color] = [move(point, color).sgf((size, size)) for point in initial["stones"].get(color, [])]
    try:
        game = BaseGame(SimpleNamespace(config=lambda _: "japanese"), move_tree=GameNode(properties=properties))
    except Exception as exc:
        issues.append(f"Initial setup is illegal: {exc}")
        return result()

    def current_board():
        return {(stone.coords[0], size - stone.coords[1] - 1): stone.player for stone in game.stones}

    board = current_board()
    if board != _board(initial["stones"]):
        issues.append("Initial setup changes occupancy under the game rules")
        return result()
    signatures = [tuple(sorted(board.items()))]
    for index, item in enumerate(replay["moves"], 1):

        def fail(message):
            issues.append(f"Step {index}: {message}")

        color, point = item.get("color"), item.get("point")
        if color != turn:
            fail("explicit color must alternate from to_play")
            break
        if item["kind"] == "move":
            if point is None:
                fail("a draft null point is not a pass")
                break
            point = tuple(point)
            if not _inside(point, region) or point in unknown:
                fail("point occupancy is unknown")
                break
            uncertain = _uncertain_move(board, point, color, size, region, unknown)
            if uncertain:
                fail(uncertain)
                break
        try:
            game.play(move(point, color))
        except IllegalMoveException as exc:
            fail(str(exc))
            break
        board = current_board()
        signature = tuple(sorted(board.items()))
        if item["kind"] == "move" and len(signatures) >= 2 and signature == signatures[-2]:
            fail("simple ko recapture is not legal")
            break
        signatures.append(signature)
        turn = "W" if color == "B" else "B"
    else:
        final = _board(payload["stones"])
        if source:
            for row in range(source["row"], source["row"] + source["rows"]):
                for col in range(source["col"], source["col"] + source["cols"]):
                    point = (col, row)
                    if board.get(point) != final.get(point) or (
                        point not in board and (not _inside(point, region) or point in unknown)
                    ):
                        issues.append("Replay final occupancy does not match the known static source region")
                        return result()
    return result()
