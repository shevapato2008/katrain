"""Validate that professional SGF main lines can be sent to KataGo faithfully."""

import re

from katrain.cron.kifu_parameters import ParameterError
from katrain.cron.sgf import ParsedGame, _main_line_nodes, parse_game, sgf_to_gtp


_BOARD_SIZE = re.compile(r"([0-9]{1,2})(?::([0-9]{1,2}))?")
_HANDICAP = re.compile(r"\+?[0-9]{1,4}")


def parse_professional_replay(
    sgf: str, *, expected_moves: int | None = None, required_board_size: int | None = None
) -> ParsedGame:
    """Check representability. KataGo validates position and move legality."""
    nodes = _main_line_nodes(sgf)
    if not nodes:
        raise ParameterError("invalid_sgf", "SGF contains no main line")
    root, *subsequent = nodes
    sizes = root.get("SZ", ["19"])
    size = _BOARD_SIZE.fullmatch(sizes[0].strip()) if len(sizes) == 1 else None
    width = int(size[1]) if size else 0
    if (
        not 2 <= width <= 52
        or (size[2] is not None and int(size[2]) != width)
        or (required_board_size is not None and width != required_board_size)
        or any("SZ" in node for node in subsequent)
    ):
        message = (
            f"Professional analysis requires a {required_board_size}x{required_board_size} board"
            if required_board_size is not None
            else "Professional analysis requires a single square board declaration"
        )
        raise ParameterError("unsupported_board_size", message)

    player = root.get("PL", ["B"])
    if len(player) != 1 or player[0].strip() not in {"B", "W"}:
        raise ParameterError("invalid_sgf", "Root PL must specify exactly one player, B or W")
    if any("PL" in node for node in subsequent):
        raise ParameterError("invalid_sgf", "Non-root PL cannot be replayed by the analysis engine")

    handicap = root.get("HA", ["0"])
    if len(handicap) != 1 or not _HANDICAP.fullmatch(handicap[0].strip()):
        raise ParameterError("invalid_sgf", "Root HA must specify one nonnegative handicap")
    if any("HA" in node for node in subsequent):
        raise ParameterError("invalid_sgf", "Non-root HA cannot be replayed by the analysis engine")

    for node in nodes:
        moves = [point for prop in ("B", "W") for point in node.get(prop, ())]
        if len(moves) > 1:
            raise ParameterError("invalid_sgf", "Multiple moves in one node cannot be replayed faithfully")
        setup = [point for prop in ("AB", "AW", "AE") for point in node.get(prop, ())]
        if any(sgf_to_gtp(point, width) in (None, "pass") for point in setup):
            raise ParameterError("invalid_sgf", "Compressed or invalid setup points cannot be replayed faithfully")
        if len(set(setup)) != len(setup) or (setup and moves):
            raise ParameterError("invalid_sgf", "Conflicting setup or setup combined with a move cannot be replayed")

    parsed = parse_game(sgf)
    if (
        not parsed.moves
        or parsed.invalid_moves
        or parsed.dropped_midgame_setup
        or (expected_moves is not None and len(parsed.moves) != expected_moves)
    ):
        raise ParameterError("invalid_sgf", "SGF main line cannot be replayed faithfully")
    if "PL" in root and parsed.initial_player != parsed.moves[0][0]:
        raise ParameterError("invalid_sgf", "Root PL disagrees with the first recorded move")
    if any(first[0] == second[0] for first, second in zip(parsed.moves, parsed.moves[1:])):
        raise ParameterError("invalid_sgf", "Moves must alternate to replay each position faithfully")
    if parsed.handicap >= 2 and (
        len(parsed.initial_stones) != parsed.handicap or any(color != "B" for color, _ in parsed.initial_stones)
    ):
        raise ParameterError("invalid_sgf", "Handicap setup must declare the matching number of black stones")
    return parsed
