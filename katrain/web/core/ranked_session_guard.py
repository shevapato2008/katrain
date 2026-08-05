"""Central fail-closed guard for public actions on ranked-AI sessions."""

from dataclasses import dataclass
from contextlib import contextmanager
from threading import RLock
from types import SimpleNamespace

from fastapi import HTTPException

RANKED_SAFE_UI_TOGGLES = frozenset({"coords", "coordinates", "numbers", "move_numbers", "zen_mode"})


@dataclass(frozen=True)
class RankedVisionBinding:
    session_id: str
    user_id: int
    user_color: str
    game_id: str


class RankedAnalysisActivity:
    """Coordinates persistent free-session analysis with ranked start per user."""

    def __init__(self):
        self.lock = RLock()
        self._background: dict[int, dict[str, dict[str, int]]] = {}
        self._temporary: dict[int, dict[str, dict[str, int]]] = {}
        self._ranked_starting: set[int] = set()

    @staticmethod
    def _increment(store, user_id: int, session_id: str, kind: str) -> None:
        kinds = store.setdefault(user_id, {}).setdefault(session_id, {})
        kinds[kind] = kinds.get(kind, 0) + 1

    @staticmethod
    def _decrement(store, user_id: int, session_id: str, kind: str) -> None:
        sessions = store.get(user_id)
        if sessions is None:
            return
        kinds = sessions.get(session_id)
        if kinds is not None:
            remaining = kinds.get(kind, 0) - 1
            if remaining > 0:
                kinds[kind] = remaining
            else:
                kinds.pop(kind, None)
            if not kinds:
                sessions.pop(session_id, None)
        if not sessions:
            store.pop(user_id, None)

    def begin_background(self, user_id: int, session_id: str, kind: str) -> None:
        with self.lock:
            if user_id in self._ranked_starting:
                raise HTTPException(status_code=409, detail="ranked game start is in progress")
            self._increment(self._background, user_id, session_id, kind)

    def begin_temporary(self, user_id: int, session_id: str, kind: str) -> None:
        with self.lock:
            if user_id in self._ranked_starting:
                raise HTTPException(status_code=409, detail="ranked game start is in progress")
            self._increment(self._temporary, user_id, session_id, kind)

    def end_temporary(self, user_id: int, session_id: str, kind: str) -> None:
        with self.lock:
            self._decrement(self._temporary, user_id, session_id, kind)

    def end_background(self, user_id: int, session_id: str, kind: str | None = None) -> None:
        with self.lock:
            sessions = self._background.get(user_id)
            if sessions is None:
                return
            if kind is None:
                sessions.pop(session_id, None)
            else:
                self._decrement(self._background, user_id, session_id, kind)
                return
            if not sessions:
                self._background.pop(user_id, None)

    def end_session(self, session_id: str) -> None:
        """Drop every user's leases for a reset or deleted shared session."""

        with self.lock:
            empty_users = []
            for user_id, sessions in self._background.items():
                sessions.pop(session_id, None)
                if not sessions:
                    empty_users.append(user_id)
            for user_id in empty_users:
                self._background.pop(user_id, None)

    def reserve_ranked_start(self, user_id: int, active_check=None) -> bool:
        with self.lock:
            if self._temporary.get(user_id):
                return False
            sessions = self._background.get(user_id, {})
            if active_check is not None:
                stale = [session_id for session_id, kinds in sessions.items() if not active_check(session_id, kinds)]
                for session_id in stale:
                    sessions.pop(session_id, None)
                if not sessions:
                    self._background.pop(user_id, None)
            if self._background.get(user_id) or user_id in self._ranked_starting:
                return False
            self._ranked_starting.add(user_id)
            return True

    def release_ranked_start(self, user_id: int) -> None:
        with self.lock:
            self._ranked_starting.discard(user_id)


@contextmanager
def temporary_analysis_lease(app, current_user, session_id: str, kind: str, action: str):
    """Block ranked start for the complete lifetime of an awaited analysis call."""

    activity = getattr(app.state, "ranked_analysis_activity", None)
    if activity is None:
        guard_user_has_no_pending_ranked_game(app, current_user, action)
        yield
        guard_user_has_no_pending_ranked_game(app, current_user, action)
        return
    with activity.lock:
        guard_user_has_no_pending_ranked_game(app, current_user, action)
        activity.begin_temporary(current_user.id, session_id, kind)
    try:
        yield
        guard_user_has_no_pending_ranked_game(app, current_user, action)
    finally:
        activity.end_temporary(current_user.id, session_id, kind)


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


def guard_ai_ladder_ranked_not_ended(session, action: str) -> None:
    """Reject every ranked mutation once any authoritative terminal marker exists."""

    if not is_ai_ladder_ranked_session(session):
        return
    runtime = getattr(session, "katrain", None)
    state = runtime.get_state() if runtime is not None else {}
    game = getattr(runtime, "game", None)
    current_node = getattr(game, "current_node", None)
    end_result = state.get("end_result") if isinstance(state, dict) else None
    if (
        end_result
        or getattr(current_node, "end_state", None)
        or getattr(session, "_recorded", False)
        or getattr(game, "end_result", None)
    ):
        raise HTTPException(status_code=403, detail=f"{action} is not allowed after the ranked game has ended")


def guard_ai_ladder_ranked_human_action(session, current_user, action: str) -> None:
    """Allow public play/terminal actions only for the owner on the human turn."""

    runtime = getattr(session, "katrain", None)
    if not is_ai_ladder_ranked_session(session):
        return

    snapshot = guard_ai_ladder_ranked_owner(session, current_user, action)

    guard_ai_ladder_ranked_not_ended(session, action)
    state = runtime.get_state() if runtime is not None else {}
    player_to_move = state.get("player_to_move") if isinstance(state, dict) else None
    if player_to_move not in {"B", "W"} or player_to_move != getattr(snapshot, "user_color", None):
        raise HTTPException(status_code=403, detail=f"{action} is only allowed on the human turn")
