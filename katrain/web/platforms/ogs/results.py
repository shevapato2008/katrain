"""Convert OGS's finished game fields into an SGF result."""

from __future__ import annotations

import math
import re


_POINTS = re.compile(r"^(\d+(?:\.\d+)?) points?$", re.IGNORECASE)


def parse_finished_result(gamedata: dict) -> str:
    """Use only the remote winner and outcome; unknown decisions remain Void."""
    if gamedata.get("phase") != "finished":
        raise ValueError("OGS game is not finished")
    if "outcome" not in gamedata or not isinstance(gamedata["outcome"], str) or not gamedata["outcome"].strip():
        raise ValueError("OGS finished game has no outcome yet")
    outcome = gamedata["outcome"].strip()
    if outcome in ("Resignation", "Timeout") or _POINTS.fullmatch(outcome):
        if gamedata.get("winner") is None:
            raise ValueError("OGS finished game has no winner yet")

    players = gamedata.get("players")
    winner_id = gamedata.get("winner")
    winner = None
    if isinstance(players, dict) and winner_id is not None:
        for color in ("B", "W"):
            seat = players.get("black" if color == "B" else "white")
            if isinstance(seat, dict) and seat.get("id") is not None and str(seat["id"]) == str(winner_id):
                winner = color
                break
    if winner is None:
        return "Void"

    if outcome == "Resignation":
        return f"{winner}+R"
    if outcome == "Timeout":
        return f"{winner}+T"
    points = _POINTS.fullmatch(outcome.strip())
    if points:
        margin = float(points.group(1))
        if math.isfinite(margin) and margin > 0:
            return f"{winner}+{margin:g}"
    return "Void"
