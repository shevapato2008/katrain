"""Central fail-closed guard for public actions on ranked-AI sessions."""

from dataclasses import dataclass
from types import SimpleNamespace

from fastapi import HTTPException

RANKED_SAFE_UI_TOGGLES = frozenset({"coords", "coordinates", "numbers", "move_numbers", "zen_mode"})


@dataclass(frozen=True)
class RankedVisionBinding:
    session_id: str
    user_id: int
    user_color: str
    game_id: str


def is_ai_ladder_ranked_session(session) -> bool:
    session_game_type = getattr(session, "game_type", None)
    runtime_game_type = getattr(getattr(session, "katrain", None), "game_type", None)
    return "ai_ladder_ranked" in {session_game_type, runtime_game_type}


def guard_ai_ladder_ranked_session(session, action: str) -> None:
    if is_ai_ladder_ranked_session(session):
        raise HTTPException(status_code=403, detail=f"{action} is not allowed during a ranked AI game")


def guard_user_has_no_pending_ranked_game(app, current_user, action: str) -> None:
    """Block sessionless/live analysis while this user has an unsettled ranked game."""

    repo = getattr(app.state, "ai_ladder_repo", None)
    if repo is not None and repo.get_pending_game(current_user.id) is not None:
        raise HTTPException(status_code=403, detail=f"{action} is unavailable during a ranked AI game")


def guard_ai_ladder_ranked_ui_toggle(session, setting: str) -> None:
    """Allow only presentation-only toggles; unknown settings fail closed."""

    if is_ai_ladder_ranked_session(session) and setting not in RANKED_SAFE_UI_TOGGLES:
        guard_ai_ladder_ranked_session(session, f"toggle-ui:{setting}")


def validate_ai_ladder_ranked_players(snapshot, players_info) -> None:
    """Verify actual player seats still match the server-issued ranked snapshot."""

    ai_color = "W" if snapshot.user_color == "B" else "B"
    human = players_info.get(snapshot.user_color)
    ai_player = players_info.get(ai_color)
    if (
        human is None
        or not bool(getattr(human, "human", False))
        or bool(getattr(human, "ai", False))
        or getattr(human, "player_subtype", None) != "player:human"
        or ai_player is None
        or not bool(getattr(ai_player, "ai", False))
        or bool(getattr(ai_player, "human", False))
        or getattr(ai_player, "player_subtype", None) != snapshot.ai_subtype
    ):
        raise ValueError("ranked AI player seats do not match the authoritative snapshot")


def guard_ai_ladder_ranked_owner(session, current_user, action: str):
    """Return the fixed snapshot after validating owner and player seats."""

    if not is_ai_ladder_ranked_session(session):
        return None
    snapshot = getattr(session, "ai_ladder_snapshot", None)
    current_user_id = getattr(current_user, "id", None)
    if (
        snapshot is None
        or current_user_id is None
        or current_user_id != getattr(session, "user_id", None)
        or current_user_id != getattr(snapshot, "user_id", None)
        or getattr(snapshot, "session_id", None) != getattr(session, "session_id", None)
        or getattr(snapshot, "user_color", None) not in {"B", "W"}
    ):
        raise HTTPException(status_code=403, detail=f"{action} is restricted to the ranked game owner")
    try:
        validate_ai_ladder_ranked_players(snapshot, getattr(session.katrain, "players_info", {}))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return snapshot


def guard_ranked_vision_binding(session, binding, action: str):
    """Validate the server-created physical-board binding against the live snapshot."""

    if binding is None or getattr(binding, "session_id", None) != getattr(session, "session_id", None):
        raise HTTPException(status_code=403, detail=f"{action} has no trusted ranked vision binding")
    snapshot = guard_ai_ladder_ranked_owner(session, SimpleNamespace(id=binding.user_id), action)
    if (
        binding.user_color != snapshot.user_color
        or binding.game_id != snapshot.game_id
        or binding.user_id != snapshot.user_id
    ):
        raise HTTPException(status_code=403, detail=f"{action} ranked vision binding is stale")
    return snapshot


def guard_ai_ladder_ranked_human_action(session, current_user, action: str) -> None:
    """Allow public play/terminal actions only for the owner on the human turn."""

    runtime = getattr(session, "katrain", None)
    if not is_ai_ladder_ranked_session(session):
        return

    snapshot = guard_ai_ladder_ranked_owner(session, current_user, action)

    state = runtime.get_state() if runtime is not None else {}
    end_result = state.get("end_result") if isinstance(state, dict) else None
    if (
        end_result
        or getattr(session, "_recorded", False)
        or getattr(getattr(runtime, "game", None), "end_result", None)
    ):
        raise HTTPException(status_code=403, detail=f"{action} is not allowed after the ranked game has ended")
    player_to_move = state.get("player_to_move") if isinstance(state, dict) else None
    if player_to_move not in {"B", "W"} or player_to_move != getattr(snapshot, "user_color", None):
        raise HTTPException(status_code=403, detail=f"{action} is only allowed on the human turn")
