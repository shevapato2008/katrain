"""Private ownership estimates for server-owned ordinary human lobby positions."""

import asyncio
import logging
import math

import httpx
from fastapi import HTTPException

from katrain.core.constants import PLAYER_HUMAN
from katrain.core.engine import KataGoEngine
from katrain.web.core.game_end_rules import is_awaiting_count
from katrain.web.core.pvp_box_bridge import PvpBoxAuthError, PvpBoxRemoteError
from katrain.web.core.ranked_session_guard import temporary_analysis_lease


def guard_lobby_territory(app, session, current_user):
    runtime = session.katrain
    seats = (session.player_b_id, session.player_w_id)
    gateway = getattr(app.state, "platform_gateway", None)
    if (
        current_user is None
        or type(current_user.id) is not int
        or current_user.id not in seats
        or not all(type(seat) is int and seat > 0 for seat in seats)
        or getattr(session, "game_type", None) != "free"
        or getattr(runtime, "game_type", None) != "free"
        or session.mode != "play"
        or getattr(runtime, "pvp_lobby_human_session", False) is not True
        or getattr(session, "bot_game", False) is True
        # create_multiplayer_session currently writes the legacy "human" spelling.
        or any(
            getattr(runtime.players_info.get(color), "player_type", None) not in (PLAYER_HUMAN, "human")
            for color in "BW"
        )
        or getattr(runtime, "platform_engine_color", None) in ("B", "W")
        or (gateway is not None and gateway.is_platform_game(session.session_id))
    ):
        raise HTTPException(status_code=403, detail="Territory is restricted to ordinary human lobby participants")
    if (
        session.game_ended
        or runtime.game.terminal is not None
        or runtime.game.current_node.end_state
        or is_awaiting_count(runtime)
        or getattr(runtime, "pvp_lobby_awaiting_count", False)
    ):
        raise HTTPException(status_code=409, detail="Territory is unavailable after play has ended")


def ownership_values(analysis, board_size):
    ownership = analysis.get("ownership") if isinstance(analysis, dict) else None
    if not ownership and isinstance(analysis, dict) and isinstance(analysis.get("rootInfo"), dict):
        ownership = analysis["rootInfo"].get("ownership")
    if (
        not isinstance(ownership, list)
        or len(ownership) != board_size[0] * board_size[1]
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not -1 <= value <= 1
            for value in ownership
        )
    ):
        raise ValueError("Invalid territory ownership")
    return ownership


def _box_territory_room(app, bridge, generation, session, current_user):
    bridge.check_user(generation, current_user.id)
    room = bridge.rooms.for_local(generation, session.session_id)
    if room is None or room.local_user_id != current_user.id:
        raise PvpBoxAuthError("Room is no longer current")
    if getattr(session, "game_type", None) != "pvp_lobby" or current_user.id not in (
        session.player_b_id,
        session.player_w_id,
    ):
        raise HTTPException(status_code=403, detail="Territory is restricted to a room participant")
    state = session.last_state or {}
    if session.game_ended or any(state.get(key) for key in ("terminal_result", "end_result", "awaiting_count")):
        raise HTTPException(status_code=409, detail="Territory is unavailable after play has ended")
    return room


def _box_territory_result(payload):
    board_size = payload.get("board_size")
    if (
        not isinstance(payload.get("game_id"), str)
        or not payload["game_id"]
        or type(payload.get("current_node_id")) is not int
        or payload["current_node_id"] <= 0
        or type(payload.get("move_count")) is not int
        or payload["move_count"] < 0
        or type(payload.get("stale")) is not bool
        or not isinstance(board_size, list)
        or len(board_size) != 2
        or any(type(size) is not int or size <= 0 for size in board_size)
    ):
        raise ValueError("Invalid territory position")
    ownership = ownership_values(payload, board_size)
    return {
        "session_id": payload["session_id"],
        "game_id": payload["game_id"],
        "current_node_id": payload["current_node_id"],
        "move_count": payload["move_count"],
        "board_size": board_size,
        "ownership": ownership,
        "black_area": sum(value > 0.5 for value in ownership),
        "white_area": sum(value < -0.5 for value in ownership),
        "stale": payload["stale"],
    }


async def forward_lobby_territory(app, session, current_user):
    """Forward without applying a state response or broadcasting private engine output."""
    bridge = getattr(app.state, "pvp_box_bridge", None)
    if bridge is None:
        raise HTTPException(status_code=503, detail="Central lobby unavailable")
    generation = app.state.box_sso.active_generation
    try:
        with session.lock:
            room = _box_territory_room(app, bridge, generation, session, current_user)
        with temporary_analysis_lease(app, current_user, session.session_id, "pvp-territory", "lobby territory"):
            payload = await bridge.forward_action(generation, session.session_id, "POST", "/api/pvp/territory")
            result = _box_territory_result(payload)
            with session.lock:
                try:
                    current_session = app.state.session_manager.get_session(session.session_id)
                except KeyError as exc:
                    raise HTTPException(status_code=404, detail="Session not found") from exc
                if current_session is not session:
                    raise HTTPException(status_code=404, detail="Session not found")
                if _box_territory_room(app, bridge, generation, session, current_user) is not room:
                    raise PvpBoxAuthError("Room is no longer current")
                state = session.last_state or {}
                if any(
                    state.get(key) is not None and state[key] != result[key] for key in ("game_id", "current_node_id")
                ):
                    result["stale"] = True
                return result
    except PvpBoxAuthError as exc:
        raise HTTPException(status_code=401, detail="Box room is no longer current") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Lobby territory unavailable; retry") from exc
    except (PvpBoxRemoteError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Lobby territory unavailable; retry") from exc


async def analyze_lobby_territory(app, session, current_user):
    with session.lock:
        guard_lobby_territory(app, session, current_user)
        if getattr(session, "_pvp_territory_in_flight", False):
            raise HTTPException(status_code=409, detail="Territory request is already in progress")
        game = session.katrain.game
        node = game.current_node
        nodes = node.nodes_from_root
        if any(n.clear_placements for n in nodes):
            raise HTTPException(
                status_code=409, detail="Territory is unavailable for a position with removed setup stones"
            )
        moves = [[move.player, move.gtp()] for n in nodes for move in n.moves]
        board_size = list(node.board_size)
        game_id = game.game_id
        payload = {
            "rules": KataGoEngine.get_rules(node.ruleset),
            "komi": node.komi,
            "boardXSize": board_size[0],
            "boardYSize": board_size[1],
            "initialStones": [[move.player, move.gtp()] for n in nodes for move in n.placements],
            "initialPlayer": node.initial_player,
            "moves": moves,
            "analyzeTurns": [len(moves)],
            "maxVisits": 200,
            "includeOwnership": True,
            "includePolicy": False,
        }
        session._pvp_territory_in_flight = True

    try:
        with temporary_analysis_lease(app, current_user, session.session_id, "pvp-territory", "lobby territory"):
            try:
                client = getattr(getattr(app.state, "router", None), "local_client", None)
                if client is None:
                    raise RuntimeError("Territory engine unavailable")
                analysis = await asyncio.wait_for(client.analyze(payload), timeout=30)
                ownership = ownership_values(analysis, board_size)
            except Exception as exc:
                logging.getLogger("katrain_web").warning("Private lobby territory failed: %s", exc)
                raise HTTPException(status_code=503, detail="Lobby territory unavailable; retry") from exc

            with session.lock:
                try:
                    current_session = app.state.session_manager.get_session(session.session_id)
                except KeyError as exc:
                    raise HTTPException(status_code=404, detail="Session not found") from exc
                if current_session is not session:
                    raise HTTPException(status_code=404, detail="Session not found")
                guard_lobby_territory(app, session, current_user)
                return {
                    "session_id": session.session_id,
                    "game_id": game_id,
                    "current_node_id": id(node),
                    "move_count": len(moves),
                    "board_size": board_size,
                    "ownership": ownership,
                    "black_area": sum(value > 0.5 for value in ownership),
                    "white_area": sum(value < -0.5 for value in ownership),
                    "stale": session.katrain.game is not game or game.current_node is not node,
                }
    finally:
        with session.lock:
            session._pvp_territory_in_flight = False
