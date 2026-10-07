"""Shared KataGo position normalization for personal and professional reports."""

from typing import Any

from katrain.cron import move_grade


def position_snapshot(response: dict, parsed: Any, move_number: int, previous: Any = None, human_profile: str | None = None) -> dict:
    root = response["rootInfo"]
    move_infos = response["moveInfos"]
    actual_move = parsed.moves[move_number - 1][1] if move_number else None
    actual_player = parsed.moves[move_number - 1][0] if move_number else None
    winrate = root["winrate"]
    score_lead = root["scoreLead"]
    delta_score = delta_winrate = None
    if previous is not None and previous.score_lead is not None and previous.winrate is not None and actual_player in ("B", "W"):
        sign = 1 if actual_player == "B" else -1
        delta_score = sign * (score_lead - previous.score_lead)
        delta_winrate = sign * (winrate - previous.winrate)

    top_moves = []
    for move in move_infos[:10]:
        human_prior = move.get("humanPrior") if human_profile else None
        top_moves.append({
            "move": move.get("move"), "visits": move.get("visits"), "winrate": move.get("winrate"),
            "score_lead": move.get("scoreLead"), "prior": move.get("prior"), "pv": move.get("pv"),
            "psv": move.get("playSelectionValue", 0.0), "human_prior": human_prior,
            "human_profile": human_profile if human_prior is not None else None,
        })
    grade = move_grade.grade(
        prev_top_moves=previous.top_moves if previous is not None else None,
        prev_visits=previous.root_visits if previous is not None else None,
        actual_move=actual_move, actual_player=actual_player,
        actual_score_lead=score_lead, actual_winrate=winrate, move_number=move_number,
    )
    flat_ownership = response["ownership"]
    size = parsed.board_size
    ownership = [[float(v) for v in flat_ownership[y * size:(y + 1) * size]] for y in range(size)]
    return {
        "status": "success", "grade": grade["grade"], "points_lost": grade["points_lost"],
        "points_lost_source": grade["points_lost_source"], "root_visits": root.get("visits"),
        "is_top_move": grade["is_top_move"], "top_prior": grade["top_prior"],
        "brilliance": grade["brilliance"], "winrate": winrate, "score_lead": score_lead,
        "visits": move_infos[0].get("visits", 0) if move_infos else 0, "top_moves": top_moves, "ownership": ownership,
        "actual_move": actual_move, "actual_player": actual_player,
        "delta_score": delta_score, "delta_winrate": delta_winrate,
    }
