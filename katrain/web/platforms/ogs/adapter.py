"""OGS platform adapter — connects KaTrain to online-go.com."""

from __future__ import annotations

import logging
import asyncio
import time
from dataclasses import dataclass, replace
from typing import Callable, Optional

from katrain.web.platforms.base import PlatformAdapter
from katrain.web.platforms.coords import katrain_to_sgf, sgf_to_katrain
from katrain.web.platforms.models import (
    ClockState,
    GamePhase,
    OnlineUser,
    PlatformChallenge,
    PlatformCredentials,
    PlatformGameSession,
    PlatformGameSnapshot,
    PlatformMove,
    TimeControl,
)
from katrain.web.platforms.ogs.realtime_client import OGSRealtimeClient
from katrain.web.platforms.ogs.rest_client import OGSRestClient

logger = logging.getLogger("katrain_web")
FINAL_RESULT_RETRY_DELAYS = (0.5, 1.0, 2.0)


@dataclass
class _PendingDirectChallenge:
    game_id: int
    on_gamedata: Callable
    task: Optional[asyncio.Task] = None


def ogs_to_core(col: int, row: int, size: int) -> tuple[int, int]:
    """OGS top-left coordinates to KaTrain core bottom-left coordinates."""
    if type(col) is not int or type(row) is not int or not 0 <= col < size or not 0 <= row < size:
        raise ValueError("OGS coordinate outside board")
    return col, size - 1 - row


def core_to_ogs(col: int, row: int, size: int) -> tuple[int, int]:
    """KaTrain core bottom-left coordinates to OGS top-left coordinates."""
    if type(col) is not int or type(row) is not int or not 0 <= col < size or not 0 <= row < size:
        raise ValueError("KaTrain coordinate outside board")
    return col, size - 1 - row


def _parse_rank(ranking: float) -> tuple[str, float]:
    """Convert OGS numeric ranking to display rank and numeric value.

    OGS ranking: 0 = 30k, 29 = 1k, 30 = 1d, 38 = 9d, 39+ = pro
    """
    if ranking < 30:
        kyu = 30 - int(ranking)
        return f"{kyu}k", ranking
    else:
        dan = int(ranking) - 29
        return f"{dan}d", ranking


def _parse_time_control(tc: dict) -> TimeControl:
    """Parse OGS time control dict into our TimeControl model."""
    if not isinstance(tc, dict):
        raise ValueError("OGS time control parameters are missing")
    system = tc.get("system", tc.get("time_control"))
    if system not in ("byoyomi", "fischer", "canadian", "absolute", "simple"):
        raise ValueError("unsupported OGS time control")
    return TimeControl(
        system=system,
        main_time=tc.get("main_time", tc.get("initial_time", 0)),
        period_time=tc.get("period_time"),
        periods=tc.get("periods"),
        time_increment=tc.get("time_increment"),
        max_time=tc.get("max_time"),
        stones_per_period=tc.get("stones_per_period"),
    )


def _parse_clock(clock_data: dict, my_color: str) -> ClockState:
    """Parse OGS clock event into ClockState."""
    current_player = "B" if clock_data.get("current_player") == clock_data.get("black_player_id") else "W"
    return ClockState(
        black_time=clock_data.get("black_time", {}),
        white_time=clock_data.get("white_time", {}),
        current_player=current_player,
        paused=clock_data.get("pause", {}).get("paused", False) if isinstance(clock_data.get("pause"), dict) else False,
    )


class OGSAdapter(PlatformAdapter):
    """PlatformAdapter implementation for OGS (online-go.com)."""

    platform_name = "ogs"
    supported_board_sizes = [9, 13, 19]
    supports_live_play = True
    supports_scoring = True
    supports_automatch = True
    supports_rooms = False
    supports_seek_graph = True

    def __init__(self):
        super().__init__()
        self._rest = OGSRestClient()
        self._rt: Optional[OGSRealtimeClient] = None
        self._active_game_id: Optional[int] = None
        self._game_data: dict[int, dict] = {}  # game_id -> gamedata
        self._snapshots: dict[int, PlatformGameSnapshot] = {}
        self._game_handlers: dict[int, list[tuple[str, object]]] = {}
        self._game_locks: dict[int, asyncio.Lock] = {}
        self._connecting_games: set[int] = set()
        self._early_moves: dict[int, list[dict]] = {}
        self._final_retry_tasks: dict[int, asyncio.Task] = {}
        self._automatch_uuid: Optional[str] = None
        self._seek_graph: dict[str, PlatformChallenge] = {}  # challenge_id -> challenge
        self._seek_graph_ready = False
        self._pending_challenges: dict[int, _PendingDirectChallenge] = {}
        self._challenge_keepalive_interval = 1.0

    # --- Connection lifecycle ---

    async def connect(self, credentials: PlatformCredentials) -> bool:
        self._seek_graph.clear()
        self._seek_graph_ready = False
        try:
            # Try token-based reconnection first
            if "user_jwt" in credentials.auth_data and credentials.auth_data.get("user_jwt"):
                try:
                    config = await self._rest.login_with_token(credentials.auth_data)
                except Exception:
                    # Token expired, fall through to password login
                    if "password" not in credentials.auth_data:
                        return False
                    config = await self._rest.login(credentials.username, credentials.auth_data["password"])
            else:
                config = await self._rest.login(credentials.username, credentials.auth_data.get("password", ""))

            # Connect realtime
            self._rt = OGSRealtimeClient()
            # Authenticate can deliver active_game immediately. Register
            # before the socket starts receiving its first frame.
            self._register_events()
            await self._rt.connect(
                jwt=self._rest.user_jwt,
                user_id=self._rest.user_id,
                username=self._rest.username,
            )

            self._connected = True

            # Subscribe to seek graph for open challenges
            await self._rt.seek_graph_connect()

            # Notify about updated tokens for storage
            await self._emit("token_refreshed", self._rest.get_auth_data_for_storage())

            return True
        except Exception as e:
            logger.error(f"OGS connection failed: {e}")
            if self._rt:
                try:
                    await self._rt.disconnect()
                except Exception:
                    logger.exception("OGS failed connection cleanup")
                self._rt = None
            self._connected = False
            return False

    async def disconnect(self) -> None:
        for challenge_id in list(self._pending_challenges):
            await self._stop_pending_challenge(challenge_id)
        for task in self._final_retry_tasks.values():
            task.cancel()
        self._final_retry_tasks.clear()
        if self._rt:
            await self._rt.disconnect()
            self._rt = None
        await self._rest.close()
        self._connected = False
        self._active_game_id = None
        self._game_data.clear()
        self._snapshots.clear()
        self._game_handlers.clear()
        self._game_locks.clear()
        self._early_moves.clear()
        self._seek_graph.clear()
        self._seek_graph_ready = False

    # --- Event registration ---

    def _register_events(self) -> None:
        """Register all OGS realtime event handlers."""
        # We register handlers for game-specific events dynamically when connecting to a game.
        # Global events:
        self._rt.on("active_game", self._on_active_game)
        self._rt.on("notification", self._on_notification)
        self._rt.on("net/pong", self._on_net_pong)
        self._rt.on("automatch/entry", self._on_automatch_entry)
        self._rt.on("automatch/start", self._on_automatch_start)
        self._rt.on("seekgraph/global", self._on_seekgraph)
        self._rt.on("_connection_lost", self._on_connection_lost_internal)
        self._rt.on("_reconnected", self._on_reconnected_internal)

    def _register_game_events(self, game_id: int) -> None:
        """Register event handlers for a specific game."""
        if game_id in self._game_handlers:
            return
        handlers = [
            (f"game/{game_id}/gamedata", lambda data: self._on_gamedata(game_id, data)),
            (f"game/{game_id}/move", lambda data: self._on_move(game_id, data)),
            (f"game/{game_id}/clock", lambda data: self._on_clock(game_id, data)),
            (f"game/{game_id}/phase", lambda data: self._on_phase(game_id, data)),
        ]
        for name, handler in handlers:
            self._rt.on(name, handler)
        self._game_handlers[game_id] = handlers

    def _unregister_game_events(self, game_id: int) -> None:
        for name, handler in self._game_handlers.pop(game_id, []):
            self._rt.off(name, handler)

    # --- Lobby ---

    async def get_open_challenges(self) -> list[PlatformChallenge]:
        """Return verified real-time seeks after the initial WebSocket snapshot."""
        if not self._seek_graph_ready:
            raise RuntimeError("OGS seek graph snapshot is not available")
        return list(self._seek_graph.values())

    async def get_online_users(self, room: Optional[str] = None) -> list[OnlineUser]:
        """Fetch online players via OGS REST API (active game players)."""
        try:
            data = await self._rest.search_players(room or "", page_size=50)
            users = []
            for p in data:
                rank_str, rank_num = _parse_rank(p.get("ranking", 15))
                users.append(
                    OnlineUser(
                        platform="ogs",
                        user_id=str(p.get("id", "")),
                        username=p.get("username", "?"),
                        rank=rank_str,
                        rank_numeric=rank_num,
                        status="idle",
                    )
                )
            return users
        except Exception as e:
            logger.error(f"Failed to fetch OGS users: {e}")
            return []

    # --- Challenge ---

    async def send_challenge(self, user_id: str, settings: dict) -> str:
        challenge_id, game_id = await self._rest.challenge_player(int(user_id), settings)
        if type(challenge_id) is not int or challenge_id <= 0 or type(game_id) is not int or game_id <= 0:
            raise ValueError("OGS direct challenge has no verified challenge and game ids")
        if self._rt is None:
            raise RuntimeError("OGS realtime is not connected")

        async def on_gamedata(_data):
            # If active-game restoration already owns this subscription, do not
            # disconnect the live game just to end the challenge wait.
            await self._stop_pending_challenge(challenge_id, disconnect_game=game_id not in self._game_handlers)
            await self._on_active_game({"id": game_id})

        pending = _PendingDirectChallenge(game_id, on_gamedata)
        self._pending_challenges[challenge_id] = pending
        event = f"game/{game_id}/gamedata"
        self._rt.on(event, on_gamedata)
        try:
            await self._rt.game_connect(game_id)
            if challenge_id in self._pending_challenges:
                pending.task = asyncio.create_task(self._keep_pending_challenge(challenge_id, game_id))
        except Exception:
            await self._stop_pending_challenge(challenge_id)
            try:
                await self._rest.decline_challenge(challenge_id)
            except Exception:
                logger.exception("OGS could not cancel direct challenge %s after subscription failure", challenge_id)
            raise
        return str(challenge_id)

    def pending_direct_challenge_id(self) -> Optional[str]:
        """Current outgoing invitation owned by this adapter connection."""
        challenge_id = next(iter(self._pending_challenges), None)
        return str(challenge_id) if challenge_id is not None else None

    async def _keep_pending_challenge(self, challenge_id: int, game_id: int) -> None:
        try:
            while challenge_id in self._pending_challenges:
                await asyncio.sleep(self._challenge_keepalive_interval)
                if challenge_id in self._pending_challenges:
                    await self._rt.challenge_keepalive(challenge_id, game_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("OGS direct challenge %s keepalive failed", challenge_id)
            await self._stop_pending_challenge(challenge_id)

    async def _stop_pending_challenge(self, challenge_id: int, *, disconnect_game: bool = True) -> None:
        pending = self._pending_challenges.pop(challenge_id, None)
        if pending is None or self._rt is None:
            return
        if pending.task is not None and pending.task is not asyncio.current_task():
            pending.task.cancel()
        self._rt.off(f"game/{pending.game_id}/gamedata", pending.on_gamedata)
        if not disconnect_game:
            return
        try:
            await self._rt.game_disconnect(pending.game_id)
        except Exception:
            logger.exception("OGS direct challenge %s disconnect failed", challenge_id)

    async def accept_challenge(self, challenge_id: str) -> PlatformGameSession:
        # Public seek acceptance is a different endpoint from direct-invite
        # acceptance. Its response need not contain a game id: retain the
        # explicit game_id from the verified seek before posting.
        challenge = self._seek_graph.get(str(challenge_id))
        if challenge is None or not challenge.game_id or not challenge.game_id.isdecimal():
            raise ValueError("OGS public challenge has no verified game id")
        game_id = int(challenge.game_id)
        await self._rest.accept_open_challenge(int(challenge_id))
        return await self._connect_to_game(game_id)

    async def decline_challenge(self, challenge_id: str) -> None:
        numeric_id = int(challenge_id)
        await self._rest.decline_challenge(numeric_id)
        await self._stop_pending_challenge(numeric_id)

    async def create_open_challenge(self, settings: dict) -> str:
        # OGS open challenges are created via REST API
        challenge_id, _ = await self._rest.challenge_player(0, settings)  # player_id=0 for open challenge
        return str(challenge_id)

    async def start_automatch(self, preferences: dict) -> None:
        if self._rt:
            self._automatch_uuid = await self._rt.automatch_find(preferences)

    async def cancel_automatch(self) -> None:
        if self._rt and self._automatch_uuid:
            await self._rt.automatch_cancel(self._automatch_uuid)
            self._automatch_uuid = None

    # --- In-game ---

    async def submit_move(self, game_id: str, col: int, row: int) -> bool:
        if not self._rt:
            return False
        snapshot = self.get_game_snapshot(game_id)
        ogs_col, ogs_row = core_to_ogs(col, row, snapshot.board_size)
        sgf_move = katrain_to_sgf(ogs_col, ogs_row)
        await self._rt.game_move(int(game_id), sgf_move)
        # OGS doesn't send explicit ACK — if the move is invalid, we get an error event.
        # For now, assume success. The gateway timeout handles failures.
        return True

    async def submit_pass(self, game_id: str) -> bool:
        if not self._rt:
            return False
        await self._rt.game_move(int(game_id), "..")
        return True

    async def resign(self, game_id: str) -> None:
        if self._rt:
            await self._rt.game_resign(int(game_id))

    async def fetch_game_snapshot(self, game_id: str) -> dict:
        try:
            raw = self._normalize_rest_game(int(game_id), await self._rest.get_game(int(game_id)))
            snapshot = self.parse_game_snapshot(int(game_id), raw)
        except Exception:
            cached = self._snapshots.get(int(game_id))
            if cached is not None and cached.phase == GamePhase.FINISHED:
                self._schedule_final_result_retry(int(game_id))
            raise
        previous = self._snapshots.get(int(game_id))
        if previous is not None and previous.phase == GamePhase.FINISHED and snapshot.phase != GamePhase.FINISHED:
            raise ValueError("OGS REST snapshot regressed after finish")
        if previous is not None and snapshot.move_number < previous.move_number:
            raise ValueError("OGS REST snapshot lost confirmed moves")
        self._game_data[int(game_id)] = raw
        self._snapshots[int(game_id)] = snapshot
        await self._emit("game_snapshot", str(game_id), snapshot)
        result_emitted = False
        if snapshot.phase == GamePhase.FINISHED:
            result_emitted = await self._emit_finished_result(int(game_id), raw)
            if not result_emitted:
                self._schedule_final_result_retry(int(game_id))
        return {"phase": snapshot.phase.value, "move_number": snapshot.move_number,
                "result_emitted": result_emitted}

    def get_game_snapshot(self, game_id: str) -> PlatformGameSnapshot:
        try:
            return self._snapshots[int(game_id)]
        except (KeyError, ValueError) as exc:
            raise RuntimeError("OGS authoritative game snapshot is unavailable") from exc

    async def refresh_game_session(self, game_id: str) -> PlatformGameSession:
        """Verify the remote board and account seat before a local resume."""
        await self.fetch_game_snapshot(game_id)
        return self._session_from_game_data(int(game_id), self._game_data[int(game_id)])

    def parse_game_snapshot(self, game_id: int, data: dict) -> PlatformGameSnapshot:
        """Decode the documented Goban shape; unknown shapes stop play."""
        if not isinstance(data, dict):
            raise ValueError("invalid OGS game snapshot")
        if "gamedata" in data:
            data = self._normalize_rest_game(game_id, data)
        size = data.get("width")
        if type(size) is not int or size not in self.supported_board_sizes or data.get("height") != size:
            raise ValueError("unsupported OGS board dimensions")
        phase = {"play": GamePhase.PLAYING, "stone removal": GamePhase.SCORING,
                 "finished": GamePhase.FINISHED}.get(data.get("phase"))
        if phase is None:
            raise ValueError("unsupported OGS game phase")
        initial = data.get("initial_state", {"black": "", "white": ""})
        if not isinstance(initial, dict):
            raise ValueError("invalid OGS initial state")
        setup = []
        occupied = set()
        for color, key in (("B", "black"), ("W", "white")):
            encoded = initial.get(key, "")
            if not isinstance(encoded, str) or len(encoded) % 2:
                raise ValueError("invalid OGS initial state")
            for i in range(0, len(encoded), 2):
                pair = encoded[i:i + 2]
                if not all("a" <= char <= "z" for char in pair):
                    raise ValueError("invalid OGS initial coordinate")
                point = ogs_to_core(ord(pair[0]) - 97, ord(pair[1]) - 97, size)
                if point in occupied:
                    raise ValueError("overlapping OGS setup stones")
                occupied.add(point)
                setup.append((color, *point))
        handicap = data.get("handicap", 0)
        if type(handicap) is not int or not 0 <= handicap <= 9:
            raise ValueError("invalid OGS handicap")
        if handicap >= 2 and len([stone for stone in setup if stone[0] == "B"]) < handicap:
            raise ValueError("OGS handicap setup is incomplete")
        raw_moves = data.get("moves")
        if not isinstance(raw_moves, list):
            raise ValueError("invalid OGS move history")
        moves = []
        first_color = "W" if handicap else "B"
        for index, packed in enumerate(raw_moves, 1):
            if isinstance(packed, list) and len(packed) >= 2:
                x, y = packed[:2]
                if len(packed) > 3 and packed[3] not in (None, 0):
                    raise ValueError("unsupported edited OGS move")
            elif isinstance(packed, dict) and "x" in packed and "y" in packed:
                if packed.get("edited") or packed.get("player_update"):
                    raise ValueError("unsupported edited OGS move")
                x, y = packed["x"], packed["y"]
            else:
                raise ValueError("unsupported OGS move encoding")
            if (x, y) == (-1, -1) and type(x) is int and type(y) is int:
                col = row = -1
            else:
                col, row = ogs_to_core(x, y, size)
            color = first_color if index % 2 else ("W" if first_color == "B" else "B")
            moves.append(PlatformMove(col, row, color, index, str(game_id)))
        return PlatformGameSnapshot(str(game_id), size, tuple(setup), tuple(moves), phase)

    @staticmethod
    def _normalize_rest_game(game_id: int, raw: dict) -> dict:
        """REST envelope has metadata outside, live history inside gamedata."""
        if not isinstance(raw, dict):
            raise ValueError("invalid OGS REST game")
        inner = raw.get("gamedata")
        if inner is None:
            return raw  # game/connect's already-flat test/source shape
        if not isinstance(inner, dict):
            raise ValueError("invalid OGS gamedata")
        for source in (raw, inner):
            for key in ("id", "game_id"):
                if source.get(key) is not None and str(source[key]) != str(game_id):
                    raise ValueError("OGS game identity mismatch")
        for key in ("width", "height"):
            if key in raw and key in inner and raw[key] != inner[key]:
                raise ValueError("OGS game board mismatch")
        outer_players, inner_players = raw.get("players"), inner.get("players")
        if isinstance(outer_players, dict) and isinstance(inner_players, dict):
            for color in ("black", "white"):
                outer_seat = outer_players.get(color)
                inner_seat = inner_players.get(color)
                if isinstance(outer_seat, dict) and isinstance(inner_seat, dict):
                    if str(outer_seat.get("id")) != str(inner_seat.get("id")):
                        raise ValueError("OGS player seat mismatch")
        if "phase" not in inner or "moves" not in inner:
            raise ValueError("OGS REST gamedata has no complete history")
        merged = {**raw, **inner, "players": outer_players or inner_players,
                  "width": raw.get("width", inner.get("width")),
                  "height": raw.get("height", inner.get("height"))}
        merged.pop("gamedata", None)
        # REST's outer envelope may carry a stale outcome while its nested
        # gamedata is still being finalized. Only inner result fields count.
        for field in ("winner", "outcome"):
            if field not in inner:
                merged.pop(field, None)
        return merged

    async def submit_scoring_action(self, game_id: str, action: dict) -> bool:
        if not self._rt:
            return False
        if action.get("action") == "accept":
            stones = action.get("stones", "")
            await self._rt.game_removed_stones_accept(int(game_id), stones)
            return True
        if action.get("action") == "reject":
            await self._rt.game_removed_stones_reject(int(game_id))
            return True
        return False

    # --- Internal: connect to a game ---

    async def _connect_to_game(self, game_id: int) -> PlatformGameSession:
        """Connect to an OGS game and return a PlatformGameSession."""
        if type(game_id) is not int or game_id <= 0:
            raise ValueError("invalid OGS game id")
        async with self._game_locks.setdefault(game_id, asyncio.Lock()):
            if game_id in self._snapshots:
                return self._session_from_game_data(game_id, self._game_data[game_id])
            self._connecting_games.add(game_id)
            try:
                return await self._connect_to_game_once(game_id)
            except Exception:
                if self._rt is not None:
                    disconnect = getattr(self._rt, "game_disconnect", None)
                    if disconnect is not None:
                        try:
                            await disconnect(game_id)
                        except Exception:
                            logger.exception("OGS game disconnect after failed validation")
                    self._unregister_game_events(game_id)
                self._game_data.pop(game_id, None)
                self._snapshots.pop(game_id, None)
                self._early_moves.pop(game_id, None)
                raise
            finally:
                self._connecting_games.discard(game_id)

    async def _connect_to_game_once(self, game_id: int) -> PlatformGameSession:
        # Subscribe first so a move between subscription and REST snapshot is
        # available for later reconciliation. Do not publish a local seat until
        # the REST identity is validated; missing/mismatched IDs cannot become White.
        self._register_game_events(game_id)
        await self._rt.game_connect(game_id)
        game_data = self._normalize_rest_game(game_id, await self._rest.get_game(game_id))
        width, height = game_data.get("width"), game_data.get("height")
        if type(width) is not int or type(height) is not int or width != height or width not in self.supported_board_sizes:
            raise ValueError("unsupported OGS board dimensions")
        self._verified_seats(game_data)

        # A gamedata/move event can arrive while REST is in flight. Keep that
        # early payload for the snapshot bridge to reconcile instead of erasing
        # it with the REST response. Seat and board metadata remain the
        # validated REST values, even if an early event includes stale fields.
        early_data = self._game_data.get(game_id, {})
        self._game_data[game_id] = {
            **game_data,
            **early_data,
            "players": game_data["players"],
            "width": width,
            "height": height,
            "handicap": game_data.get("handicap", 0),
        }
        # The REST response was fetched after subscribing. If a full gamedata
        # callback won the race, keep whichever complete history is newer.
        rest_snapshot = self.parse_game_snapshot(game_id, game_data)
        if early_data:
            early_snapshot = self.parse_game_snapshot(game_id, self._game_data[game_id])
            if early_snapshot.move_number < rest_snapshot.move_number:
                self._game_data[game_id] = game_data
                snapshot = rest_snapshot
            else:
                snapshot = early_snapshot
        else:
            snapshot = rest_snapshot
        self._snapshots[game_id] = snapshot
        early_moves = self._early_moves.pop(game_id, [])
        if early_moves:
            # A delta raced the REST response. A fresh authoritative read is
            # simpler and safer than replaying potentially duplicated events.
            fresh = self._normalize_rest_game(game_id, await self._rest.get_game(game_id))
            fresh_snapshot = self.parse_game_snapshot(game_id, fresh)
            for event in early_moves:
                number = event["move_number"]
                if number > fresh_snapshot.move_number:
                    raise RuntimeError("early OGS move missing from authoritative snapshot")
                candidate_raw = {**fresh, "moves": [*fresh["moves"][:number - 1], event["move"]]}
                candidate = self.parse_game_snapshot(game_id, candidate_raw).moves[-1]
                if candidate != fresh_snapshot.moves[number - 1]:
                    raise RuntimeError("early OGS move conflicts with authoritative snapshot")
            if fresh_snapshot.move_number < snapshot.move_number:
                raise RuntimeError("OGS authoritative snapshot regressed during connection")
            snapshot = fresh_snapshot
            self._game_data[game_id] = fresh
            self._snapshots[game_id] = snapshot
        self._active_game_id = game_id
        return self._session_from_game_data(game_id, game_data)

    def _verified_seats(self, game_data: dict) -> tuple[str, dict]:
        players = game_data.get("players")
        if not isinstance(players, dict):
            raise ValueError("OGS game has no verified seats")
        black, white = players.get("black"), players.get("white")
        if not isinstance(black, dict) or not isinstance(white, dict):
            raise ValueError("OGS game has no verified seats")
        black_id, white_id, owner_id = black.get("id"), white.get("id"), self._rest.user_id
        if any(type(value) not in (int, str) or not str(value).strip() for value in (black_id, white_id, owner_id)):
            raise ValueError("OGS game has no verified seats")
        if str(black_id) == str(white_id) or str(owner_id) not in (str(black_id), str(white_id)):
            raise ValueError("OGS game is not seated for this account")
        my_color = "B" if str(owner_id) == str(black_id) else "W"
        return my_color, white if my_color == "B" else black

    def _session_from_game_data(self, game_id: int, game_data: dict) -> PlatformGameSession:
        my_color, opponent_data = self._verified_seats(game_data)
        opp_rank, opp_rank_num = _parse_rank(opponent_data.get("ranking", 15))
        return PlatformGameSession(
            platform="ogs",
            game_id=str(game_id),
            board_size=game_data["width"],
            my_color=my_color,
            opponent=OnlineUser(
                platform="ogs",
                user_id=str(opponent_data.get("id", "")),
                username=opponent_data.get("username", "?"),
                rank=opp_rank,
                rank_numeric=opp_rank_num,
            ),
            time_control=_parse_time_control(game_data.get("time_control", {})),
            rules=game_data.get("rules", "chinese"),
            ranked=game_data.get("ranked", False),
            handicap=game_data.get("handicap", 0),
            komi=game_data.get("komi", 6.5),
        )

    # --- Event handlers ---

    async def _on_active_game(self, data) -> None:
        """Received active game notification."""
        if data and isinstance(data, dict):
            game_id = data.get("id", data.get("game_id"))
            if type(game_id) is not int or game_id <= 0:
                return
            try:
                session = await self._connect_to_game(game_id)
                await self._emit("game_started", session)
            except Exception:
                logger.exception("Could not restore OGS active game %s", game_id)

    async def _on_notification(self, data) -> None:
        """Received a notification (may be a challenge)."""
        if not data or not isinstance(data, dict):
            return
        ntype = data.get("type")
        if ntype == "challenge":
            await self._handle_challenge_notification(data)
        elif ntype == "gameOfferRejected":
            for challenge_id, pending in list(self._pending_challenges.items()):
                if str(pending.game_id) == str(data.get("game_id")):
                    await self._stop_pending_challenge(challenge_id)

    async def _handle_challenge_notification(self, data: dict) -> None:
        """Convert OGS challenge notification to PlatformChallenge."""
        challenge = data.get("challenge", data)
        challenger = challenge.get("challenger", {})
        rank_str, rank_num = _parse_rank(challenger.get("ranking", 15))
        tc = _parse_time_control(challenge.get("time_control", challenge.get("time_control_parameters", {})))

        platform_challenge = PlatformChallenge(
            platform="ogs",
            challenge_id=str(challenge.get("id", data.get("id", ""))),
            from_user=OnlineUser(
                platform="ogs",
                user_id=str(challenger.get("id", "")),
                username=challenger.get("username", "?"),
                rank=rank_str,
                rank_numeric=rank_num,
            ),
            board_size=challenge.get("width", challenge.get("game", {}).get("width", 19)),
            time_control=tc,
            rules=challenge.get("rules", "chinese"),
            ranked=challenge.get("ranked", False),
            handicap=challenge.get("handicap", 0),
            komi=challenge.get("komi"),
        )
        await self._emit("challenge_received", platform_challenge)

    async def _on_gamedata(self, game_id: int, data: dict) -> None:
        """Store a full authoritative game state without changing move shape."""
        snapshot = self.parse_game_snapshot(game_id, data)
        current = self._snapshots.get(game_id)
        if current is not None and current.phase == GamePhase.FINISHED and snapshot.phase != GamePhase.FINISHED:
            return
        if current and snapshot.move_number < current.move_number:
            return
        self._game_data[game_id] = data
        self._snapshots[game_id] = snapshot
        await self._emit("game_snapshot", str(game_id), snapshot)
        if snapshot.phase == GamePhase.FINISHED:
            if not await self._emit_finished_result(game_id, data):
                self._schedule_final_result_retry(game_id)

    async def _on_move(self, game_id: int, data) -> None:
        """Move received (both ours and opponent's). OGS sends all moves."""
        if not isinstance(data, dict) or str(data.get("game_id")) != str(game_id):
            return
        number = data.get("move_number")
        if type(number) is not int or number <= 0:
            return
        current = self._snapshots.get(game_id)
        if current is None:
            self._early_moves.setdefault(game_id, []).append(data)
            return
        if number != current.move_number + 1:
            if number <= current.move_number:
                try:
                    candidate = self._decode_single_move(game_id, data, current, number)
                except ValueError:
                    candidate = None
                if candidate == current.moves[number - 1]:
                    return
            await self.fetch_game_snapshot(str(game_id))
            return
        platform_move = self._decode_single_move(game_id, data, current, number)
        raw = self._game_data.get(game_id)
        if raw is None:
            await self.fetch_game_snapshot(str(game_id))
            return
        raw["moves"] = [*raw["moves"], data["move"]]
        next_snapshot = self.parse_game_snapshot(game_id, raw)
        self._snapshots[game_id] = next_snapshot
        # This includes our own echo. Only the manager may confirm/commit it.
        await self._emit("opponent_move", platform_move)

    def _decode_single_move(self, game_id: int, data: dict, snapshot: PlatformGameSnapshot, number: int) -> PlatformMove:
        raw = self._game_data.get(game_id)
        if raw is None:
            raise ValueError("missing OGS game context")
        synthetic = {**raw, "moves": [*raw["moves"][:number - 1], data.get("move")]}
        parsed = self.parse_game_snapshot(game_id, synthetic)
        if parsed.move_number != number:
            raise ValueError("invalid OGS move event")
        return parsed.moves[-1]

    async def _on_clock(self, game_id: int, data: dict) -> None:
        """Clock update received."""
        if not data:
            return
        gamedata = self._game_data.get(game_id, {})
        players = gamedata.get("players", {})
        black_id = players.get("black", {}).get("id")
        my_color = "B" if black_id == self._rest.user_id else "W"
        clock = _parse_clock(data, my_color)
        clock.game_id = str(game_id)
        await self._emit("clock_update", clock)

    async def _on_phase(self, game_id: int, data) -> None:
        """Game phase changed (play -> stone removal -> finished)."""
        phase_str = data if isinstance(data, str) else data.get("phase", "") if isinstance(data, dict) else ""
        phase_map = {
            "play": GamePhase.PLAYING,
            "stone removal": GamePhase.SCORING,
            "finished": GamePhase.FINISHED,
        }
        phase = phase_map.get(phase_str)
        if phase is None:
            logger.warning("Unknown OGS game phase for %s: %r", game_id, phase_str)
            return
        current = self._snapshots.get(game_id)
        if current is not None and current.phase == GamePhase.FINISHED and phase != GamePhase.FINISHED:
            return
        if current is not None:
            self._snapshots[game_id] = replace(current, phase=phase)
        await self._emit("game_phase_changed", str(game_id), phase)

        if phase == GamePhase.FINISHED:
            # A phase event does not carry the winner. Never settle from stale
            # in-memory gamedata if this authoritative read fails.
            if not await self._read_finished_result(game_id):
                self._schedule_final_result_retry(game_id)

    async def _read_finished_result(self, game_id: int) -> bool:
        try:
            # fetch_game_snapshot emits the final board before game_ended. A
            # phase frame may arrive after the last move while its move frame
            # was lost, so settling directly from REST result would save a
            # truncated local game tree.
            state = await self.fetch_game_snapshot(str(game_id))
        except Exception:
            logger.warning("OGS final result fetch failed for game %s", game_id, exc_info=True)
            return False
        return bool(state["result_emitted"])

    def _schedule_final_result_retry(self, game_id: int) -> None:
        task = self._final_retry_tasks.get(game_id)
        if task is not None and not task.done():
            return
        self._final_retry_tasks[game_id] = asyncio.create_task(self._retry_finished_result(game_id))

    async def _retry_finished_result(self, game_id: int) -> None:
        for delay in FINAL_RESULT_RETRY_DELAYS:
            await asyncio.sleep(delay)
            if await self._read_finished_result(game_id):
                return
        logger.error("OGS final result remains unavailable for game %s; waiting for a new frame/reconnect", game_id)

    async def _emit_finished_result(self, game_id: int, data: dict) -> bool:
        from katrain.web.platforms.ogs.results import parse_finished_result

        try:
            result = parse_finished_result(data)
        except ValueError:
            # A phase frame can race the REST result write. A later gamedata
            # frame, snapshot fetch or reconnect will retry.
            return False
        winner = result[0] if result.startswith(("B+", "W+")) else ""
        try:
            await self._emit("game_ended", str(game_id), result, winner)
        except Exception:
            logger.exception("OGS final result could not be applied for game %s", game_id)
            return False
        task = self._final_retry_tasks.pop(game_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        return True

    async def _on_net_pong(self, data: dict) -> None:
        """Latency measurement response."""
        if data and isinstance(data, dict):
            client_time = data.get("client", 0)
            server_time = data.get("server", 0)
            now = int(time.time() * 1000)
            self._rt.latency = now - client_time
            self._rt.drift = server_time - now

    async def _on_seekgraph(self, data) -> None:
        """Seek graph update — maintain cache of open challenges.

        OGS always sends seekgraph/global as a list, even for single updates:
        - Initial snapshot: [{seek1}, {seek2}, ...] — many entries
        - Delete: [{"challenge_id": X, "delete": 1}]
        - New seek: [{seek_data}]
        - Game started: [{"game_started": true, ...}]
        """
        if not isinstance(data, list):
            return

        # The first event is the snapshot even when OGS has zero/few seeks.
        is_snapshot = not self._seek_graph_ready

        if is_snapshot:
            self._seek_graph.clear()
            total, parsed, failed = 0, 0, 0
            first_fail_reason = None
            for seek in data:
                if not isinstance(seek, dict):
                    continue
                if seek.get("delete") or seek.get("game_started"):
                    continue
                total += 1
                challenge = self._parse_seek(seek)
                if challenge:
                    self._seek_graph[challenge.challenge_id] = challenge
                    parsed += 1
                else:
                    failed += 1
                    if first_fail_reason is None:
                        first_fail_reason = f"keys={list(seek.keys())[:10]}"
            logger.info(f"OGS seek graph snapshot: {parsed}/{total} parsed, {failed} failed")
            if first_fail_reason:
                logger.warning(f"OGS seek graph parse failure sample: {first_fail_reason}")
        else:
            # Incremental update: process each entry
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                seek_id = str(entry.get("challenge_id", entry.get("game_id", "")))
                if entry.get("delete") or entry.get("game_started"):
                    self._seek_graph.pop(seek_id, None)
                else:
                    challenge = self._parse_seek(entry)
                    if challenge:
                        self._seek_graph[challenge.challenge_id] = challenge
        self._seek_graph_ready = True

    def _parse_seek(self, seek: dict) -> Optional[PlatformChallenge]:
        """Parse an OGS seek graph entry into PlatformChallenge.

        Seek entries have flat fields: username, ranking, challenge_id, width, etc.
        time_control is a STRING ("byoyomi"), time_control_parameters is the dict.
        """
        try:
            width, height = seek.get("width"), seek.get("height")
            public_game_id = seek.get("game_id")
            tc_params = seek.get("time_control_parameters")
            if (
                type(public_game_id) not in (int, str) or
                not str(public_game_id).isdecimal() or int(public_game_id) <= 0 or
                type(width) is not int or width not in self.supported_board_sizes or
                type(height) is not int or height != width or
                seek.get("rengo") is not False or
                seek.get("invite_only") is not False or
                seek.get("private") is not False or
                not isinstance(tc_params, dict) or
                tc_params.get("speed") not in ("live", "rapid", "blitz")
            ):
                return None
            user = seek.get("user", seek)
            ranking = user.get("rank", user.get("ranking"))
            if not isinstance(ranking, (int, float)) or isinstance(ranking, bool):
                return None
            rank_str, rank_num = _parse_rank(ranking)
            # time_control is a string in seek data; time_control_parameters is the dict
            tc = _parse_time_control(tc_params)

            return PlatformChallenge(
                platform="ogs",
                challenge_id=str(seek.get("challenge_id", seek.get("game_id", ""))),
                from_user=OnlineUser(
                    platform="ogs",
                    user_id=str(user.get("user_id", user.get("player_id", user.get("id", "")))),
                    username=user.get("username", "?"),
                    rank=rank_str,
                    rank_numeric=rank_num,
                ),
                board_size=width,
                time_control=tc,
                rules=seek.get("rules", "chinese"),
                ranked=seek.get("ranked", False),
                handicap=seek.get("handicap", 0),
                komi=seek.get("komi"),
                game_id=str(public_game_id),
            )
        except Exception as e:
            logger.debug(f"Failed to parse seek: {e}")
            return None

    async def _on_automatch_entry(self, data) -> None:
        """Automatch queue status update."""
        pass

    async def _on_automatch_start(self, data) -> None:
        """Automatch found a game."""
        if data and isinstance(data, dict):
            game_id = data.get("game_id")
            if game_id:
                game_session = await self._connect_to_game(game_id)
                await self._emit("automatch_found", game_session)

    async def _on_connection_lost_internal(self, data) -> None:
        """Internal connection lost handler."""
        for challenge_id in list(self._pending_challenges):
            await self._stop_pending_challenge(challenge_id)
        self._connected = False
        self._seek_graph.clear()
        self._seek_graph_ready = False
        await self._emit("connection_lost")

    async def _on_reconnected_internal(self, data) -> None:
        """Refresh each subscribed game after the socket has rejoined it."""
        self._connected = True
        await self._emit("reconnected")
        for game_id in list(self._game_handlers):
            try:
                await self.fetch_game_snapshot(str(game_id))
            except Exception:
                logger.exception("OGS snapshot resync failed for game %s", game_id)
