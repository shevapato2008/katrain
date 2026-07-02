"""Golaxy / 星阵围棋 (19x19.com) platform adapter.

REST API for game actions + STOMP over SockJS for real-time events.
Auth: phone-only (+86 Chinese mobile number).
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from katrain.web.platforms.base import PlatformAdapter
from katrain.web.platforms.golaxy import engine_client
from katrain.web.platforms.golaxy.coords import Move, golaxy_to_katrain, katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import AuthExpired, GenmoveResult, Retryable
from katrain.web.platforms.models import (
    ClockState,
    GamePhase,
    OnlineUser,
    PlatformChallenge,
    PlatformCredentials,
    PlatformGameSession,
    PlatformMove,
    TimeControl,
)

logger = logging.getLogger("katrain_web")

GOLAXY_API_BASE = "https://api.19x19.com"
GOLAXY_WEB_BASE = "https://www.19x19.com"
GOLAXY_WS = "wss://ws.19x19.com/api/social/channel/WS_STOMP_ENDPOINT_GOLAXY"
GOLAXY_CLIENT_CREDENTIALS = base64.b64encode(b"golaxy_web:xingzhen0730").decode()


# --- Engine-play (human-vs-AI) types --------------------------------------- #


@dataclass
class EngineGameConfig:
    """Immutable-ish config for a human-vs-AI engine game."""

    level: int  # Golaxy `elo_score` == the genmove `level` query param
    human_color: str  # "B" or "W"
    komi: float = 7.5
    rule: str = "chinese"
    handicap: int = 0
    board_size: int = 19


@dataclass
class EngineGameContext:
    """Server-side state for one engine game.

    The Golaxy genmove tunnel is STATELESS, so this context is the sole source
    of truth for the move history: `moves` is the full ordered list of Golaxy
    coord ints. It is committed exactly once per turn, only after a valid AI
    coord returns (see GolaxyAdapter._genmove_committing).
    """

    game_id: str
    config: EngineGameConfig
    moves: list[int] = field(default_factory=list)  # golaxy coord ints, full history
    status: str = "playing"  # "playing" | "finished" | "error"


@dataclass
class EngineGameStart:
    """Result of start_engine_game: the session plus the AI's opening move (if any)."""

    session: PlatformGameSession
    first_ai_move: Optional[PlatformMove]  # populated iff human plays White (AI black opens)


class GolaxyEngineTerminal(Exception):
    """The engine returned a non-move coord (pass/resign/unknown special).

    Distinct from engine_client's AuthExpired/Retryable/Fatal: this is raised
    by the adapter after a *successful* genmove call whose coord cannot be
    committed as a normal on-board move, so the caller terminates the game
    defensively rather than forwarding garbage into the local session.
    """


class GolaxyRestClient:
    """HTTP client for Golaxy REST API."""

    def __init__(self, base_url: str = GOLAXY_API_BASE):
        self._base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._user_code: Optional[str] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
                headers={"User-Agent": "KaTrain-SmartBoard/0.1"},
            )
        return self._client

    def _auth_headers(self) -> dict:
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # --- Auth ---

    async def login_password(self, phone: str, password: str) -> dict:
        """Login with phone number and password."""
        client = await self._ensure_client()
        resp = await client.post(
            "/api/auth/oauth/token",
            data={
                "username": f"0086-{phone}",
                "password": password,
                "grant_type": "password",
                "client_id": "golaxy_web",
                "scope": "any",
            },
            headers={
                "Authorization": f"Basic {GOLAXY_CLIENT_CREDENTIALS}",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        return data

    async def login_sms(self, phone: str, code: str) -> dict:
        """Login with phone number and SMS verification code.

        Verified format from browser capture:
          username=0086-{phone}&password=null&grant_type=sms_code&client_id=golaxy_web&sms_code={code}&scope=any
        """
        client = await self._ensure_client()
        resp = await client.post(
            "/api/auth/oauth/token",
            data={
                "username": f"0086-{phone}",
                "password": "null",
                "grant_type": "sms_code",
                "client_id": "golaxy_web",
                "sms_code": code,
                "scope": "any",
            },
            headers={
                "Authorization": f"Basic {GOLAXY_CLIENT_CREDENTIALS}",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        return data

    async def request_sms_code(self, phone: str) -> bool:
        """Request SMS verification code."""
        client = await self._ensure_client()
        resp = await client.get(
            "/api/auth/sms/code",
            params={"username": phone, "login": "true", "area": "0086"},
            headers={
                "Authorization": f"Basic {GOLAXY_CLIENT_CREDENTIALS}",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        return resp.status_code == 200

    async def refresh_access_token(self) -> dict:
        """Refresh the access token."""
        client = await self._ensure_client()
        resp = await client.post(
            "/api/auth/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": "golaxy_web",
                "refresh_token": self._refresh_token,
            },
            headers={
                "Authorization": f"Basic {GOLAXY_CLIENT_CREDENTIALS}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        return data

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token

    def get_auth_data(self) -> dict:
        return {"access_token": self._access_token, "refresh_token": self._refresh_token, "user_code": self._user_code}

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    # --- Game service ---

    async def create_gameroom(self, settings: dict) -> dict:
        client = await self._ensure_client()
        resp = await client.post("/api/social/gameroom/reserve", json=settings, headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def join_gameroom(self, room_id: str) -> dict:
        client = await self._ensure_client()
        resp = await client.post(f"/api/social/gameroom/login/{room_id}", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def leave_gameroom(self, room_id: str) -> None:
        client = await self._ensure_client()
        await client.post(f"/api/social/gameroom/logout/{room_id}", headers=self._auth_headers())

    async def start_game(self, game_id: str) -> dict:
        client = await self._ensure_client()
        resp = await client.post(f"/api/social/wsgame/start/{game_id}", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def submit_move(self, game_id: str, move_data: dict) -> dict:
        client = await self._ensure_client()
        resp = await client.post(f"/api/social/wsgame/genmove/{game_id}", json=move_data, headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def request_undo(self, game_id: str) -> dict:
        client = await self._ensure_client()
        resp = await client.post(f"/api/social/wsgame/backmove/{game_id}", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def end_game(self, game_id: str) -> dict:
        client = await self._ensure_client()
        resp = await client.post(f"/api/social/wsgame/game/end/{game_id}", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def get_game_state(self, game_id: str) -> dict:
        client = await self._ensure_client()
        resp = await client.get(f"/api/social/wsgame/game/state/{game_id}", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def get_game_meta(self, game_id: str) -> dict:
        client = await self._ensure_client()
        resp = await client.get(f"/api/social/wsgame/game/meta/{game_id}", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    # --- Live/spectating (no auth required) ---

    async def get_all_lives(self) -> list[dict]:
        client = await self._ensure_client()
        resp = await client.get("/api/engine/golives/all")
        resp.raise_for_status()
        return resp.json()

    async def get_live_moves(self, live_id: str, begin: int = 0, end: int = 500) -> dict:
        client = await self._ensure_client()
        resp = await client.get(
            f"/api/engine/golives/base/{live_id}", params={"begin_move_num": begin, "end_move_num": end}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_live_sgf(self, game_id: str) -> str:
        client = await self._ensure_client()
        resp = await client.get(f"/api/engine/golives/{game_id}")
        resp.raise_for_status()
        return resp.text

    # --- Engine play (human-vs-AI stateless genmove tunnel) ---

    async def engine_genmove(
        self,
        *,
        moves: list[int],
        level: int,
        komi: float = 7.5,
        rule: str = "chinese",
        handicap: int = 0,
        board_size: int = 19,
    ) -> GenmoveResult:
        """Thin wrapper over engine_client.engine_genmove.

        Keeps the access token encapsulated so the adapter never reaches into
        private client/token state. Raises AuthExpired/Retryable/Fatal.
        """
        from katrain.web.platforms.golaxy.engine_client import engine_genmove as _genmove

        client = await self._ensure_client()
        return await _genmove(
            client,
            moves=moves,
            level=level,
            access_token=self._access_token,
            komi=komi,
            rule=rule,
            handicap=handicap,
            board_size=board_size,
        )


class GolaxyAdapter(PlatformAdapter):
    """PlatformAdapter implementation for Golaxy / 星阵围棋 (19x19.com).

    REST API for game actions. STOMP over SockJS for real-time events.
    Note: Live play via STOMP requires capturing payload schemas from browser traffic.
    Currently provides REST-based game flow (higher latency than WebSocket).
    """

    platform_name = "golaxy"
    supported_board_sizes = [9, 13, 19]
    supports_live_play = True
    supports_scoring = False  # Scoring handled server-side via judge endpoint
    supports_automatch = False  # TODO: verify automatch support
    supports_rooms = True
    supports_seek_graph = False
    supports_engine_play = True  # human-vs-AI via the stateless genmove tunnel

    def __init__(self):
        super().__init__()
        self._rest = GolaxyRestClient()
        self._active_game_id: Optional[str] = None
        self._engine_games: dict[str, EngineGameContext] = {}
        self._engine_seq = 0

    async def connect(self, credentials: PlatformCredentials) -> bool:
        try:
            auth_data = credentials.auth_data
            if "access_token" in auth_data and auth_data["access_token"]:
                # Try token-based reconnection
                self._rest.set_tokens(auth_data["access_token"], auth_data.get("refresh_token", ""))
                try:
                    # Verify token is still valid by making a test request
                    await self._rest.get_all_lives()
                    self._connected = True
                    return True
                except Exception:
                    # Token expired, try refresh
                    if auth_data.get("refresh_token"):
                        try:
                            await self._rest.refresh_access_token()
                            self._connected = True
                            await self._emit("token_refreshed", self._rest.get_auth_data())
                            return True
                        except Exception:
                            pass

            sms_code = auth_data.get("sms_code")
            if sms_code:
                await self._rest.login_sms(credentials.username, sms_code)
                self._connected = True
                await self._emit("token_refreshed", self._rest.get_auth_data())
                logger.info(f"Golaxy connected via SMS as {credentials.username}")
                return True

            # Fall through to password login
            password = auth_data.get("password", "")
            if password:
                await self._rest.login_password(credentials.username, password)
                self._connected = True
                await self._emit("token_refreshed", self._rest.get_auth_data())
                logger.info(f"Golaxy connected as {credentials.username}")
                return True

            return False
        except Exception as e:
            logger.error(f"Golaxy connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        await self._rest.close()
        self._connected = False
        self._active_game_id = None

    async def get_rooms(self) -> list[dict]:
        # Golaxy rooms are created on-demand; no global room list
        return []

    async def submit_move(self, game_id: str, col: int, row: int) -> bool:
        try:
            # Golaxy move format TBD — likely {"x": col, "y": row} or similar
            await self._rest.submit_move(game_id, {"x": col, "y": row})
            return True
        except Exception as e:
            logger.error(f"Golaxy move submission failed: {e}")
            return False

    async def submit_pass(self, game_id: str) -> bool:
        try:
            await self._rest.submit_move(game_id, {"pass": True})
            return True
        except Exception as e:
            logger.error(f"Golaxy pass failed: {e}")
            return False

    async def resign(self, game_id: str) -> None:
        await self._rest.end_game(game_id)

    async def fetch_game_snapshot(self, game_id: str) -> dict:
        return await self._rest.get_game_state(game_id)

    # --- Engine play (human-vs-AI, stateless genmove tunnel) ---
    #
    # Correctness core (§3.1): the human move is encoded into an immutable
    # `proposed_moves` snapshot BEFORE the network call; the canonical
    # `ctx.moves` is committed exactly once, only after a valid AI coord comes
    # back; and every retry reuses that same snapshot. This is why a
    # timeout/retry can never append the human move twice or land moves out of
    # order. These methods do NOT touch the human-vs-human submit_move/
    # submit_pass/resign gameroom path above.

    def get_engine_levels(self) -> list[dict]:
        """Return the full Golaxy AI level table (for the API layer)."""
        return engine_client.list_levels()

    async def start_engine_game(self, config: EngineGameConfig) -> EngineGameStart:
        """Create a new engine game. If the human plays White, the AI (Black)
        opens immediately and its move is returned as `first_ai_move`."""
        if not self._rest.is_authenticated:
            raise RuntimeError("not connected")

        self._engine_seq += 1
        game_id = f"golaxy-engine-{self._engine_seq}"
        ctx = EngineGameContext(game_id=game_id, config=config, moves=[], status="playing")
        self._engine_games[game_id] = ctx

        level_row = engine_client.get_level(config.level)
        if level_row is not None:
            bot_name = level_row.get("name", f"AI-{config.level}")
            level_name = level_row.get("level_name", f"AI-{config.level}")
        else:
            bot_name = f"AI-{config.level}"
            level_name = f"AI-{config.level}"

        session = PlatformGameSession(
            platform="golaxy",
            game_id=game_id,
            board_size=config.board_size,
            my_color=config.human_color,
            opponent=OnlineUser(
                platform="golaxy",
                user_id=str(config.level),
                username=bot_name,
                rank=level_name,
                rank_numeric=float(config.level),
            ),
            time_control=TimeControl(system="absolute", main_time=0),  # no timing this iteration
            rules=config.rule,
            ranked=False,
            handicap=config.handicap,
            komi=config.komi,
        )

        first_ai_move: Optional[PlatformMove] = None
        if config.human_color == "W":
            # AI opens as Black: genmove on an empty move list.
            first_ai_move = await self._genmove_committing(ctx, proposed_moves=[])

        return EngineGameStart(session=session, first_ai_move=first_ai_move)

    async def submit_engine_move(self, game_id: str, col: int, row: int) -> PlatformMove:
        """Submit the human's move and return the AI's reply as a PlatformMove.

        The human move is snapshotted into `proposed` BEFORE the network call;
        `ctx.moves` is NOT mutated here — it is committed exactly once inside
        _genmove_committing after a valid AI coord returns.
        """
        ctx = self._engine_games.get(game_id)
        if ctx is None:
            raise KeyError(game_id)
        if ctx.status != "playing":
            raise RuntimeError(f"engine game {game_id} not playing (status={ctx.status})")
        human_coord = katrain_to_golaxy(col, row, ctx.config.board_size)
        proposed = list(ctx.moves) + [human_coord]  # immutable snapshot; DO NOT write ctx.moves yet
        return await self._genmove_committing(ctx, proposed)

    async def _genmove_committing(self, ctx: EngineGameContext, proposed_moves: list[int]) -> PlatformMove:
        """Call genmove (with retry discipline) and commit exactly once.

        `proposed_moves` is the immutable snapshot of the history including the
        human move (if any). The canonical `ctx.moves` is written exactly once,
        only after a valid on-board AI coord returns.
        """
        result = await self._genmove_with_retry(ctx, proposed_moves)  # GenmoveResult
        decoded = golaxy_to_katrain(result.coord, ctx.config.board_size)
        ai_color = "W" if ctx.config.human_color == "B" else "B"
        if not isinstance(decoded, Move):
            # AI pass/resign/unknown special coord — defensive terminal, do NOT commit.
            ctx.status = "finished"
            await self._emit("game_ended", ctx.game_id, "ai_special_coord", ai_color)
            raise GolaxyEngineTerminal(f"AI returned non-move coord {result.coord!r}")
        ctx.moves = list(proposed_moves) + [result.coord]  # single atomic commit
        return PlatformMove(
            col=decoded.col,
            row=decoded.row,
            color=ai_color,
            move_number=len(ctx.moves),
            game_id=ctx.game_id,
        )

    async def _genmove_with_retry(self, ctx: EngineGameContext, proposed_moves: list[int]) -> GenmoveResult:
        """Call genmove with the retry discipline from §3.1.

        Invariant: `proposed_moves` is passed through unchanged on every attempt
        — the human move is encoded exactly once by the caller, so a retry can
        never append it twice. Fatal propagates immediately (no retry).
        """
        try:
            return await self._call_genmove(ctx, proposed_moves)
        except AuthExpired:
            # Refresh once, then retry the SAME proposed_moves.
            await self._rest.refresh_access_token()
            await self._emit("token_refreshed", self._rest.get_auth_data())
            try:
                return await self._call_genmove(ctx, proposed_moves)
            except AuthExpired:
                await self._emit("auth_expired")
                raise
        except Retryable:
            # Transient failure — retry the SAME proposed_moves once; if it
            # raises again, that exception propagates.
            return await self._call_genmove(ctx, proposed_moves)

    async def _call_genmove(self, ctx: EngineGameContext, proposed_moves: list[int]) -> GenmoveResult:
        return await self._rest.engine_genmove(
            moves=proposed_moves,
            level=ctx.config.level,
            komi=ctx.config.komi,
            rule=ctx.config.rule,
            handicap=ctx.config.handicap,
            board_size=ctx.config.board_size,
        )

    async def resign_engine_game(self, game_id: str) -> None:
        """Human resigns the engine game — the AI wins. No-op if unknown.

        Only emits game_ended; the manager's _on_game_ended does the cleanup
        (_active_games/_session_to_game) and broadcast.
        """
        ctx = self._engine_games.pop(game_id, None)
        if ctx is None:
            return
        ctx.status = "finished"
        winner = "W" if ctx.config.human_color == "B" else "B"  # human resigns → AI wins
        await self._emit("game_ended", game_id, "resign", winner)

    def rebuild_engine_moves(self, game_id: str, moves_coords: list[tuple[int, int]]) -> None:
        """Reset an engine context's move list from an already-extracted main line.

        Decoupled recovery helper: the manager (which owns the KaTrain session)
        extracts the ordered (col, row) main line from the game tree and calls
        this on reconnect/desync. This method does NOT read the session tree.
        """
        ctx = self._engine_games.get(game_id)
        if ctx is None:
            raise KeyError(game_id)
        ctx.moves = [katrain_to_golaxy(c, r, ctx.config.board_size) for (c, r) in moves_coords]
