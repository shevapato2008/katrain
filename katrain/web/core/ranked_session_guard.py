"""Central fail-closed guard for public actions on ranked-AI sessions."""

from fastapi import HTTPException

RANKED_SAFE_UI_TOGGLES = frozenset({"coords", "coordinates", "numbers", "move_numbers", "zen_mode"})


def is_ai_ladder_ranked_session(session) -> bool:
    session_game_type = getattr(session, "game_type", None)
    runtime_game_type = getattr(getattr(session, "katrain", None), "game_type", None)
    return "ai_ladder_ranked" in {session_game_type, runtime_game_type}


def guard_ai_ladder_ranked_session(session, action: str) -> None:
    if is_ai_ladder_ranked_session(session):
        raise HTTPException(status_code=403, detail=f"{action} is not allowed during a ranked AI game")


def guard_ai_ladder_ranked_ui_toggle(session, setting: str) -> None:
    """Allow only presentation-only toggles; unknown settings fail closed."""

    if is_ai_ladder_ranked_session(session) and setting not in RANKED_SAFE_UI_TOGGLES:
        guard_ai_ladder_ranked_session(session, f"toggle-ui:{setting}")


def guard_ai_ladder_ranked_human_action(session, current_user, action: str) -> None:
    """Allow public play/terminal actions only for the owner on the human turn."""

    runtime = getattr(session, "katrain", None)
    if not is_ai_ladder_ranked_session(session):
        return

    snapshot = getattr(session, "ai_ladder_snapshot", None)
    current_user_id = getattr(current_user, "id", None)
    if (
        snapshot is None
        or current_user_id is None
        or current_user_id != getattr(session, "user_id", None)
        or current_user_id != getattr(snapshot, "user_id", None)
    ):
        raise HTTPException(status_code=403, detail=f"{action} is restricted to the ranked game owner")

    state = runtime.get_state() if runtime is not None else {}
    player_to_move = state.get("player_to_move") if isinstance(state, dict) else None
    if player_to_move not in {"B", "W"} or player_to_move != getattr(snapshot, "user_color", None):
        raise HTTPException(status_code=403, detail=f"{action} is only allowed on the human turn")
