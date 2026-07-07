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
from katrain.web.platforms.golaxy.engine_client import (
    AreaResult,
    AuthExpired,
    Fatal,
    GenmoveResult,
    JudgeResult,
    OptionsResult,
    Retryable,
    VariationResult,
)
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


def _handicap_stones(n: int, board_size: int = 19) -> list[int]:
    """Golaxy coords of the N standard handicap stones (black).

    Replicates KaTrain's ``SGFNode.place_handicap_stones`` (sgf_parser.py, non-tygem,
    n<=9 branch) so the stateless Golaxy genmove tunnel is seeded with the SAME stones
    the manager auto-places on the local board. Returns [] for n < 2. Do NOT apply the
    tygem corner swap — manager/game use the default non-tygem placement.
    """
    if n < 2:
        return []
    near = 3 if board_size >= 13 else min(2, board_size - 1)
    far = board_size - 1 - near
    middle = board_size // 2
    stones = [(far, far), (near, near), (far, near), (near, far)]
    if n % 2 == 1:
        stones.append((middle, middle))
    stones += [(near, middle), (far, middle), (middle, near), (middle, far)]
    stones = stones[:n]
    return [katrain_to_golaxy(x, y, board_size) for (x, y) in stones]


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


# --- Engine analysis (area/options/judge/variation) result types -----------
#
# Typed, JSON-serializable (via dataclasses.asdict) per-kind results returned
# by GolaxyAdapter.engine_analysis. These decode the Task-1 engine_client
# results (raw Golaxy int coords / the 722-float area list / the 361-char
# judge belong string) into KaTrain (col, row) structures using
# coords.golaxy_to_katrain -- see golaxy-protocol.md Section 9.5.


@dataclass(frozen=True)
class OwnershipPoint:
    """One board point's 领地 (territory) ownership value from the area tunnel.

    `value` is the raw signed float from Golaxy: positive = 黑地 (black
    territory), negative = 白地 (white territory). Not thresholded here --
    the frontend renders intensity."""

    col: int
    row: int
    value: float


@dataclass(frozen=True)
class AreaAnalysis:
    """Decoded result of the `area` (领地) tunnel: 361 ownership points plus
    the resulting winrate/delta (passed through verbatim)."""

    ownership: list[OwnershipPoint]
    winrate: float
    delta: float


@dataclass(frozen=True)
class Candidate:
    """One candidate move from the `options` (支招) tunnel, decoded to
    (col, row) with its recommendation probability and resulting
    winrate/delta."""

    col: int
    row: int
    prob: float
    winrate: float
    delta: float


@dataclass(frozen=True)
class OptionsAnalysis:
    """Decoded result of the `options` (支招) tunnel: ranked candidate moves.
    No top-level winrate/delta -- each candidate carries its own."""

    candidates: list[Candidate]


@dataclass(frozen=True)
class Point:
    """A bare board point, in KaTrain (col, row) convention."""

    col: int
    row: int


@dataclass(frozen=True)
class VariationAnalysis:
    """Decoded result of the `variation` (变化图) tunnel: the AI's principal
    variation as an ordered point sequence, plus the resulting winrate/delta."""

    sequence: list[Point]
    winrate: float
    delta: float


@dataclass(frozen=True)
class JudgePoint:
    """One board point's whole-board verdict from the judge tunnel.

    `owner` is one of "U" (undecided) / "B" (black) / "W" (white)."""

    col: int
    row: int
    owner: str


@dataclass(frozen=True)
class JudgeAnalysis:
    """Decoded result of the `judge` (形势) tunnel: 361 verdict points plus
    the overall winner ("U"/"B"/"W"/"D") and score delta."""

    ownership: list[JudgePoint]
    winner: str
    delta: float


AnalysisResult = AreaAnalysis | OptionsAnalysis | VariationAnalysis | JudgeAnalysis


def _decode_area(result: AreaResult, board_size: int) -> AreaAnalysis:
    """Use only the first board_size*board_size entries -- the rest (observed
    722 = 361*2 in the live capture) is a degenerate second channel (§9.5)."""
    n = board_size * board_size
    if len(result.area) < n:
        raise Fatal(f"Golaxy area: expected at least {n} entries, got {len(result.area)}")
    ownership = []
    for i in range(n):
        m = golaxy_to_katrain(i, board_size)  # always a Move for i in [0, n)
        ownership.append(OwnershipPoint(col=m.col, row=m.row, value=result.area[i]))
    return AreaAnalysis(ownership=ownership, winrate=result.winrate, delta=result.delta)


def _decode_options(result: OptionsResult, board_size: int) -> OptionsAnalysis:
    candidates = []
    for coord, prob, winrate, delta in zip(result.coord, result.prob, result.winrate, result.delta):
        decoded = golaxy_to_katrain(coord, board_size)
        if not isinstance(decoded, Move):
            continue  # defensive: skip UnknownSpecial rather than emit a bogus point
        candidates.append(Candidate(col=decoded.col, row=decoded.row, prob=prob, winrate=winrate, delta=delta))
    return OptionsAnalysis(candidates=candidates)


def _decode_variation(result: VariationResult, board_size: int) -> VariationAnalysis:
    sequence = []
    for coord in result.coord:
        decoded = golaxy_to_katrain(coord, board_size)
        if not isinstance(decoded, Move):
            continue  # defensive: skip UnknownSpecial rather than emit a bogus point
        sequence.append(Point(col=decoded.col, row=decoded.row))
    return VariationAnalysis(sequence=sequence, winrate=result.winrate, delta=result.delta)


def _decode_judge(result: JudgeResult, board_size: int) -> JudgeAnalysis:
    n = board_size * board_size
    if len(result.belong) < n:
        raise Fatal(f"Golaxy judge: expected at least {n} chars, got {len(result.belong)}")
    ownership = []
    for i, ch in enumerate(result.belong[:n]):
        m = golaxy_to_katrain(i, board_size)  # always a Move for i in [0, n)
        ownership.append(JudgePoint(col=m.col, row=m.row, owner=ch))
    return JudgeAnalysis(ownership=ownership, winner=result.winner, delta=result.delta)


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

    async def engine_analysis(
        self,
        *,
        kind: str,
        moves: list[int],
        komi: float = 7.5,
        rule: str = "chinese",
        handicap: int = 0,
        board_size: int = 19,
        level: int = 8888,
    ) -> AreaResult | OptionsResult | VariationResult | JudgeResult:
        """Thin wrapper over engine_client.engine_analysis.

        Sibling of engine_genmove above: keeps the access token encapsulated
        so the adapter never reaches into private client/token state. Raises
        AuthExpired/Retryable/Fatal/QuotaExhausted.
        """
        from katrain.web.platforms.golaxy.engine_client import engine_analysis as _analysis

        client = await self._ensure_client()
        return await _analysis(
            client,
            kind=kind,
            moves=moves,
            access_token=self._access_token,
            komi=komi,
            rule=rule,
            handicap=handicap,
            board_size=board_size,
            level=level,
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

    async def request_sms_code(self, phone: str) -> bool:
        """Request an SMS verification code for phone-based login.

        Thin delegate to the REST client so the API layer never reaches into
        private client state. Returns True on success.
        """
        return await self._rest.request_sms_code(phone)

    def get_auth_data(self) -> dict:
        """Return the current auth tokens (access/refresh/user_code).

        Thin delegate to the REST client. Used by PlatformManager.connect_platform
        to persist the resulting tokens (not the transient sms_code) so a restart
        can reconnect without a fresh SMS login.
        """
        return self._rest.get_auth_data()

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
        """Create a new engine game, seeding any handicap stones and letting the AI
        open when it is the side-to-move.

        For a handicap game (config.handicap >= 2) the N black handicap stones are
        seeded into ctx.moves and White is to move; for 分先 (handicap 0) Black is to
        move. The AI opens (returning its move as `first_ai_move`) exactly when the
        side-to-move equals the AI's color."""
        if not self._rest.is_authenticated:
            raise RuntimeError("not connected")

        self._engine_seq += 1
        game_id = f"golaxy-engine-{self._engine_seq}"
        # Seed the N standard handicap stones (black) so the stateless tunnel and the
        # local board agree on the opening position. config.handicap is a stone count.
        seeded = _handicap_stones(config.handicap, config.board_size)
        ctx = EngineGameContext(game_id=game_id, config=config, moves=list(seeded), status="playing")
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
        # After N black handicap stones the side-to-move is White; with no handicap it
        # is Black. The AI opens exactly when the side-to-move equals the AI's color.
        # This preserves the existing 分先 behavior: human W + handicap 0 -> AI(black)
        # opens on an empty move list; human B + handicap 0 -> human(black) plays first.
        side_to_move = "W" if config.handicap >= 2 else "B"
        ai_color = "W" if config.human_color == "B" else "B"
        if side_to_move == ai_color:
            first_ai_move = await self._genmove_committing(ctx, proposed_moves=list(ctx.moves))

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

    # --- Engine analysis (read-only; area/options/judge/variation) ---------
    #
    # Parallel structure to _genmove_with_retry/_call_genmove above --
    # intentionally duplicated rather than refactored in, since the genmove
    # path is regression-forbidden. Analysis never mutates ctx.moves/status
    # and never commits anything, so it works on the current committed
    # ctx.moves regardless of status (reviewing a finished game is fine).

    async def engine_analysis(self, game_id: str, kind: str) -> AnalysisResult:
        """Run one of the area/options/judge/variation analysis tunnels for
        an existing engine game and return the decoded, typed result.

        Raises KeyError for an unknown game_id (mirrors submit_engine_move).
        Propagates QuotaExhausted/Fatal from the client unretried; AuthExpired
        triggers a refresh+retry, Retryable a plain retry (see
        _analysis_with_retry).
        """
        ctx = self._engine_games.get(game_id)
        if ctx is None:
            raise KeyError(game_id)
        result = await self._analysis_with_retry(ctx, kind)
        board_size = ctx.config.board_size
        if isinstance(result, AreaResult):
            return _decode_area(result, board_size)
        if isinstance(result, OptionsResult):
            return _decode_options(result, board_size)
        if isinstance(result, VariationResult):
            return _decode_variation(result, board_size)
        if isinstance(result, JudgeResult):
            return _decode_judge(result, board_size)
        raise Fatal(f"engine_analysis: unexpected result type {type(result)!r} for kind={kind!r}")

    async def _analysis_with_retry(self, ctx: EngineGameContext, kind: str):
        """Mirror _genmove_with_retry's auth-refresh-retry discipline for the
        analysis tunnels. QuotaExhausted and Fatal propagate immediately (no
        retry) — only AuthExpired (refresh + retry once) and Retryable
        (retry once) are handled here.
        """
        try:
            return await self._call_analysis(ctx, kind)
        except AuthExpired:
            # Refresh once, then retry the SAME request.
            await self._rest.refresh_access_token()
            await self._emit("token_refreshed", self._rest.get_auth_data())
            try:
                return await self._call_analysis(ctx, kind)
            except AuthExpired:
                await self._emit("auth_expired")
                raise
        except Retryable:
            # Transient failure — retry the SAME request once; if it raises
            # again, that exception propagates.
            return await self._call_analysis(ctx, kind)

    async def _call_analysis(self, ctx: EngineGameContext, kind: str):
        return await self._rest.engine_analysis(
            kind=kind,
            moves=ctx.moves,
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
