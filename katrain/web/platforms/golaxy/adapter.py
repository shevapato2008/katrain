"""Golaxy / 星阵围棋 (19x19.com) platform adapter.

REST API for game actions + STOMP over SockJS for real-time events.
Auth: phone number with selected international calling code.
"""

from __future__ import annotations

import base64
import itertools
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

import httpx

from katrain.web.platforms.base import PlatformAdapter
from katrain.web.platforms.golaxy import engine_client
from katrain.web.platforms.golaxy.coords import Move, Pass, Resign, UnknownSpecial, golaxy_to_katrain, katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import (
    AreaResult,
    AuthExpired,
    Fatal,
    GenmoveResult,
    ItemCountsResult,
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
    PlatformEngineReply,
    PlatformGameSession,
    PlatformMove,
    PlatformPass,
    PlatformResign,
    TimeControl,
)

logger = logging.getLogger("katrain_web")


class GolaxyLobbyError(RuntimeError):
    """The upstream lobby did not return a usable response."""


class GolaxyLobbyAuthError(GolaxyLobbyError):
    """The current Golaxy credential is invalid or expired."""


class GolaxySnapshotUnsupported(GolaxyLobbyError):
    """This room uses a board setup not yet verified for spectating."""


# Exact `computerLevel` Elo-to-label rows in the official client (PROTOCOL.md).
# Its 1–18 级 rows match our already captured AI table; the human list extends
# through 25 级. Missing Elo values such as 2700 deliberately stay unknown.
_LOBBY_RANKS = {str(row["elo_score"]): row["level_name"] for row in engine_client.GOLAXY_AI_LEVELS}
_LOBBY_RANKS.update({"210": "19级", "200": "20级", "190": "21级", "180": "22级", "170": "23级", "160": "24级", "150": "25级"})
_LOBBY_GAME_TYPES = {"80": "自由战", "82": "升降战"}
_LOBBY_PRESENCE = {
    "-1": "拒绝",
    "0": "创建",
    "10": "登录",
    "20": "空闲",
    "30": "忙碌",
    "40": "对弈",
    "50": "离线",
    "90": "退出",
    "WSGAME_WATCH": "观战",
    "AI_LIFE_DEATH": "AI解题中",
    "AI_ANALYSIS": "研究中",
    "AI_GAME": "对弈",
}
_LOBBY_STATUS_PRIORITY = {"0": 0, "10": 0, "20": 1, "30": 2, "40": 3, "50": 0, "90": 0}


def _lobby_label(value, labels: dict[str, str]) -> Optional[str]:
    return labels.get(str(value)) if type(value) in (int, str) else None


def _lobby_count(value) -> Optional[int]:
    return value if type(value) is int and value >= 0 else None


def _lobby_presence(row: dict) -> Optional[str]:
    connection = _lobby_label(row.get("connectionStatus"), {"0": "closed", "1": "open"})
    web = _lobby_label(row.get("webConnectionStatus"), {"0": "closed", "1": "open"})
    app = _lobby_label(row.get("appConnectionStatus"), {"0": "closed", "1": "open"})
    if connection is None:
        connection = "open" if "open" in (web, app) else "closed" if web == app == "closed" else None
    if connection == "closed":
        return "离线"
    if connection != "open":
        return None
    if row.get("inviteAble") in (False, 0, "0"):
        return "拒绝"
    for device in ("web", "app"):
        if _lobby_label(row.get(f"{device}ConnectionStatus"), {"1": "open"}) and row.get(f"{device}UserStatusDetail"):
            label = _lobby_label(row[f"{device}UserStatusDetail"], _LOBBY_PRESENCE)
            if label:
                return label
    statuses = [row.get(f"{device}UserStatus") for device, state in (("web", web), ("app", app)) if state == "open"]
    statuses = [value for value in statuses if _lobby_label(value, _LOBBY_PRESENCE)]
    if statuses:
        return _lobby_label(
            max(statuses, key=lambda value: _LOBBY_STATUS_PRIORITY.get(str(value), -1)), _LOBBY_PRESENCE
        )
    return _lobby_label(row.get("userStatus"), _LOBBY_PRESENCE)


def _lobby_avatar(row: dict) -> Optional[str]:
    """Keep verified official HTTPS assets; filename resolution is not verified."""
    value = row.get("photoFile") or row.get("photo")
    if not isinstance(value, str) or any(char.isspace() for char in value) or "\\" in value:
        return None
    try:
        url = urlsplit(value)
        if (
            url.scheme == "https"
            and url.hostname == "assets.19x19.com"
            and url.port in (None, 443)
            and url.username is None
            and url.password is None
        ):
            return value
    except ValueError:
        pass
    return None


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
    first_ai_move: Optional[PlatformEngineReply]  # populated iff the AI is initially to move


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
    """Candidates are driven by `coord` -- the per-move fields (prob/winrate/
    delta) are best-effort per §13 and may be missing or shorter than `coord`
    (the Golaxy `options` body sometimes omits them entirely). Use
    `zip_longest` (not `zip`) so a short/absent parallel array never silently
    truncates the candidate list, and default a missing field to 0.0 rather
    than block on it.
    """
    candidates = []
    for coord, prob, winrate, delta in itertools.zip_longest(
        result.coord, result.prob, result.winrate, result.delta, fillvalue=None
    ):
        if coord is None:
            continue  # only coord can be authoritatively absent-driven; nothing to decode
        decoded = golaxy_to_katrain(coord, board_size)
        if not isinstance(decoded, Move):
            continue  # defensive: skip UnknownSpecial rather than emit a bogus point
        candidates.append(
            Candidate(
                col=decoded.col,
                row=decoded.row,
                prob=0.0 if prob is None else prob,
                winrate=0.0 if winrate is None else winrate,
                delta=0.0 if delta is None else delta,
            )
        )
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
    """The engine returned an unknown non-move coordinate.

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
        self._username: Optional[str] = None  # Golaxy login principal, for /items/{username}

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
        # F1 (task-6a review): `GolaxyAdapter` is a per-platform SINGLETON,
        # created once at startup and never rebuilt — the SAME `_username`
        # otherwise survives across completely different katrain users who
        # each connect/disconnect it over the box's lifetime. Necessary but
        # NOT sufficient on its own: `connect()` also clears it explicitly,
        # because a user re-logging in WITHOUT an intervening disconnect
        # never reaches this method.
        self._username = None
        self._user_code = None

    # --- Auth ---

    @staticmethod
    def _phone_principal(phone: str) -> str:
        """Accept the selected area prefix while keeping old bare +86 credentials working."""
        return phone if re.match(r"00[1-9]\d{0,3}-", phone) else f"0086-{phone}"

    async def login_password(self, phone: str, password: str) -> dict:
        """Login with phone number and password."""
        client = await self._ensure_client()
        resp = await client.post(
            "/api/auth/oauth/token",
            data={
                "username": self._phone_principal(phone),
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

        Browser format: username=00{dial}-{phone}, with the other OAuth fields
        unchanged. A bare phone uses +86 for saved-credential compatibility.
        """
        client = await self._ensure_client()
        resp = await client.post(
            "/api/auth/oauth/token",
            data={
                "username": self._phone_principal(phone),
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

    async def login_scan_code(self, uuid: str) -> dict:
        """Exchange a CONFIRMED scan-login uuid for tokens.

        Same `/api/auth/oauth/token` endpoint as SMS/password login (R-31,
        task-6a-brief.md) — just a different `grant_type`. Scan login has no
        phone number at this layer; the uuid IS the credential, so unlike
        `login_sms`/`login_password` there is no `username` field to send.
        """
        client = await self._ensure_client()
        resp = await client.post(
            "/api/auth/oauth/token",
            data={
                "uuid": uuid,
                "grant_type": "scan_code",
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

    async def request_sms_code(self, phone: str) -> bool:
        """Request SMS verification code."""
        area, local_phone = self._phone_principal(phone).split("-", 1)
        client = await self._ensure_client()
        resp = await client.get(
            "/api/auth/sms/code",
            params={"username": local_phone, "login": "true", "area": area},
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

    def set_username(self, username: Optional[str]) -> None:
        """Record the Golaxy login principal for account-level calls like
        `/items/{username}`. Normalizes a bare phone to the `0086-{phone}`
        form the API expects (== store.state.username); leaves an
        already-prefixed value untouched. No-op on falsy input — by itself
        that's ambiguous between "this login path legitimately has no
        principal" and "just don't touch whatever's already there", which is
        exactly the bug in F1 (task-6a review). Callers that need the FIRST
        meaning must call `clear_username()` first; this method alone can
        only ever ADD a principal, never remove one."""
        if not username:
            return
        self._username = self._phone_principal(username)

    def clear_username(self) -> None:
        """Explicitly forget the login principal — the deliberate counterpart
        to `set_username`'s falsy no-op. `connect()` calls this at the start
        of EVERY login attempt, before deciding which branch handles it, so a
        login with no verified principal (scan-login, R-29 path 2) can never
        silently inherit whoever was connected through this SAME adapter
        instance before it (`GolaxyAdapter` is a per-platform singleton that
        outlives any one katrain user's session — see F1, task-6a review)."""
        self._username = None
        self._user_code = None

    def get_auth_data(self) -> dict:
        return {"access_token": self._access_token, "refresh_token": self._refresh_token, "user_code": self._user_code}

    async def get_account_identity(self) -> dict[str, str]:
        """Read the nickname and login principal attached to the current token."""
        if not self._access_token:
            raise GolaxyLobbyAuthError("Golaxy login required")
        client = await self._ensure_client()
        try:
            response = await client.post(
                "/api/auth/oauth/check_token",
                data={"token": self._access_token},
                headers={"Authorization": f"Basic {GOLAXY_CLIENT_CREDENTIALS}"},
                timeout=8.0,
            )
            if response.status_code in (401, 403):
                raise GolaxyLobbyAuthError("Golaxy login expired")
            response.raise_for_status()
            body = response.json()
        except GolaxyLobbyError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise GolaxyLobbyError("Golaxy account unavailable") from exc
        if not isinstance(body, dict) or body.get("active") is not True:
            raise GolaxyLobbyAuthError("Golaxy login expired")
        nickname = body.get("nickname")
        username = body.get("username")
        if not isinstance(nickname, str) or not nickname.strip():
            raise GolaxyLobbyError("Golaxy nickname unavailable")
        if not isinstance(username, str) or not re.fullmatch(r"00[1-9]\d{0,3}-\d{4,15}", username):
            raise GolaxyLobbyError("Golaxy login principal unavailable")
        self.set_username(username)
        user_code = body.get("usercode")
        if isinstance(user_code, (str, int)) and not isinstance(user_code, bool) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(user_code)):
            self._user_code = str(user_code)
        return {"nickname": nickname.strip(), "username": username}

    async def _get_user_code(self) -> str:
        if self._user_code is None:
            await self.get_account_identity()
        if self._user_code is None:
            raise GolaxyLobbyError("Golaxy user code unavailable")
        return self._user_code

    async def _enveloped_data(self, method: str, path: str, *, params: Optional[dict] = None, payload: Optional[dict] = None) -> object:
        client = await self._ensure_client()
        try:
            response = await client.request(
                method, path, params=params, json=payload, headers=self._auth_headers(), timeout=10.0,
            )
            if response.status_code in (401, 403):
                raise GolaxyLobbyAuthError("Golaxy login expired")
            response.raise_for_status()
            body = response.json()
        except GolaxyLobbyError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise GolaxyLobbyError("Golaxy request unavailable") from exc
        if not isinstance(body, dict):
            raise GolaxyLobbyError("Golaxy response malformed")
        if str(body.get("code")) == "6003":
            raise GolaxyLobbyAuthError("Golaxy login expired")
        if str(body.get("code")) != "0":
            raise GolaxyLobbyError("Golaxy request failed")
        return body.get("data")

    async def get_player_profile(self, peer_code: str) -> dict:
        caller_code = await self._get_user_code()
        data = await self._enveloped_data(
            "GET",
            f"/api/social/follow/user/info/user_code/{caller_code}",
            params={"peer_user_code": peer_code},
        )
        if not isinstance(data, dict) or str(data.get("userCode")) != peer_code:
            raise GolaxyLobbyError("Golaxy profile malformed")
        return data

    async def get_player_games(self, peer_code: str, page: int = 0) -> dict:
        data = await self._enveloped_data(
            "GET",
            f"/api/engine/games/user_code/{peer_code}",
            params={"game_type": 8, "page": page, "size": 10},
        )
        if not isinstance(data, dict) or not isinstance(data.get("gameMetaList"), list):
            raise GolaxyLobbyError("Golaxy game history malformed")
        return data

    async def change_player_follow(self, peer_code: str, follow: bool) -> None:
        caller_code = await self._get_user_code()
        action = "follow" if follow else "unfollow"
        key = "followee_user_code" if follow else "peer_user_code"
        await self._enveloped_data(
            "POST", f"/api/social/follow/{action}/user_code/{caller_code}", payload={key: peer_code},
        )

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

    async def _lobby_list(self, path: str, params: dict) -> list[dict]:
        """Read and validate a Golaxy list envelope; never expose its body in errors."""
        client = await self._ensure_client()
        try:
            resp = await client.get(path, params=params, headers=self._auth_headers())
            if resp.status_code in (401, 403):
                raise GolaxyLobbyAuthError("Golaxy login expired")
            resp.raise_for_status()
            body = resp.json()
        except GolaxyLobbyError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise GolaxyLobbyError("Golaxy lobby unavailable") from exc
        if not isinstance(body, dict):
            raise GolaxyLobbyError("Golaxy lobby response malformed")
        if str(body.get("code")) == "6003":
            raise GolaxyLobbyAuthError("Golaxy login expired")
        if str(body.get("code")) != "0" or not isinstance(body.get("data"), list):
            raise GolaxyLobbyError("Golaxy lobby response malformed")
        if not all(isinstance(row, dict) for row in body["data"]):
            raise GolaxyLobbyError("Golaxy lobby response malformed")
        return body["data"]

    async def list_gamerooms(self) -> list[dict]:
        return await self._lobby_list("/api/social/gameroom/list", {"page": 0, "size": 15})

    async def list_gamezone_users(self) -> list[dict]:
        return await self._lobby_list("/api/social/gamezone/user/list", {"page": 0, "size": 15, "level": -1})

    async def get_gameroom_info(self, room_id: str) -> dict:
        """Read one authenticated room, without forwarding upstream response bodies on errors."""
        if re.fullmatch(r"[0-9]+", room_id) is None:
            raise GolaxyLobbyError("Golaxy room ID malformed")
        client = await self._ensure_client()
        try:
            resp = await client.get(f"/api/social/gameroom/info/{room_id}", headers=self._auth_headers())
            if resp.status_code in (401, 403):
                raise GolaxyLobbyAuthError("Golaxy login expired")
            resp.raise_for_status()
            body = resp.json()
        except GolaxyLobbyError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise GolaxyLobbyError("Golaxy room unavailable") from exc
        if not isinstance(body, dict):
            raise GolaxyLobbyError("Golaxy room response malformed")
        if str(body.get("code")) == "6003":
            raise GolaxyLobbyAuthError("Golaxy login expired")
        if str(body.get("code")) != "0" or not isinstance(body.get("data"), dict):
            raise GolaxyLobbyError("Golaxy room response malformed")
        return body["data"]

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

    async def fetch_item_counts(self) -> ItemCountsResult:
        """Thin wrapper over engine_client.fetch_item_counts.

        Keeps the access token and username encapsulated so the adapter never
        reaches into private client state. Raises AuthExpired/Retryable/Fatal.
        """
        from katrain.web.platforms.golaxy.engine_client import fetch_item_counts as _fetch

        client = await self._ensure_client()
        return await _fetch(client, username=self._username, access_token=self._access_token)


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
            # F1 (task-6a review): forget whoever was connected through this
            # SAME adapter instance before — `GolaxyAdapter` is a per-platform
            # singleton, never rebuilt, so without this a login with no
            # verified principal (scan-login below) would silently inherit
            # the PREVIOUS owner's `0086-{phone}` via `set_username`'s falsy
            # no-op. Then record the login principal up front so account-level
            # calls (/items/{username} for the 道具 badges) work on every auth
            # path, including token-based reconnect.
            self._rest.clear_username()
            self._rest.set_username(credentials.username)
            auth_data = credentials.auth_data
            if "access_token" in auth_data and auth_data["access_token"]:
                # Try token-based reconnection
                self._rest.set_tokens(auth_data["access_token"], auth_data.get("refresh_token", ""))
                try:
                    # The public live-game feed cannot verify a saved token.
                    await self._rest.list_gamezone_users()
                    self._connected = True
                    return True
                except GolaxyLobbyAuthError:
                    # Refresh only an explicitly rejected credential.
                    if auth_data.get("refresh_token"):
                        try:
                            await self._rest.refresh_access_token()
                            if not self._rest.is_authenticated:
                                raise GolaxyLobbyAuthError("Golaxy login expired")
                            await self._rest.list_gamezone_users()
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
                logger.info("Golaxy connected via SMS")
                return True

            # Scan-login uses the confirmed uuid to obtain tokens. The caller
            # may supply the verified phone principal from /scan/username;
            # clear_username above prevents an older account's principal from
            # surviving when that lookup fails.
            scan_uuid = auth_data.get("scan_uuid")
            if scan_uuid:
                await self._rest.login_scan_code(scan_uuid)
                self._connected = True
                await self._emit("token_refreshed", self._rest.get_auth_data())
                logger.info("Golaxy connected via scan code")
                return True

            # Fall through to password login
            password = auth_data.get("password", "")
            if password:
                await self._rest.login_password(credentials.username, password)
                self._connected = True
                await self._emit("token_refreshed", self._rest.get_auth_data())
                logger.info("Golaxy connected via password")
                return True

            return False
        except Exception as e:
            logger.error("Golaxy connection failed: %s", type(e).__name__)
            return False

    async def disconnect(self) -> None:
        await self._rest.close()
        self._connected = False
        self._active_game_id = None
        # Backstop for `PlatformManager.disconnect_platform`, which already
        # walks `_active_games` and calls `discard_engine_game` per game — but
        # anything that disconnects this adapter WITHOUT going through the
        # manager (a future caller, a test double) must not leave a stale
        # tunnel history an attacker/next-owner could resume against.
        self._engine_games.clear()

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

    async def get_account_identity(self) -> dict[str, str]:
        return await self._rest.get_account_identity()

    async def get_player_profile(self, peer_code: str) -> dict:
        row = await self._rest.get_player_profile(peer_code)
        name = row.get("followAlias") or row.get("nickname")
        if not isinstance(name, str) or not name.strip():
            raise GolaxyLobbyError("Golaxy profile malformed")
        follow_type = row.get("followType")
        return {
            "user_id": peer_code,
            "username": name.strip(),
            "rank": _lobby_label(row.get("level"), _LOBBY_RANKS),
            "wins": _lobby_count(row.get("winNum")),
            "losses": _lobby_count(row.get("loseNum")),
            "followed": follow_type in (1, 3) if follow_type in (0, 1, 2, 3) else None,
        }

    async def get_player_games(self, peer_code: str, page: int = 0) -> dict:
        data = await self._rest.get_player_games(peer_code, page=page)
        total = _lobby_count(data.get("total"))
        games = []
        for row in data["gameMetaList"]:
            if not isinstance(row, dict) or not isinstance(row.get("id"), (str, int)):
                raise GolaxyLobbyError("Golaxy game history malformed")
            games.append({
                "game_id": str(row["id"]),
                "black": row.get("pb") if isinstance(row.get("pb"), str) else None,
                "white": row.get("pw") if isinstance(row.get("pw"), str) else None,
                "move_number": _lobby_count(row.get("moveNum")),
                "result": row.get("gameResult") if isinstance(row.get("gameResult"), str) else None,
                "board_size": row.get("boardSize") if row.get("boardSize") in (9, 13, 19) else None,
            })
        return {"total": total, "games": games}

    async def change_player_follow(self, peer_code: str, follow: bool) -> dict:
        await self._rest.change_player_follow(peer_code, follow)
        return await self.get_player_profile(peer_code)

    async def get_rooms(self) -> list[dict]:
        rows = await self._rest.list_gamerooms()
        rooms = []
        for row in rows:
            room_id = row.get("id")
            if not isinstance(room_id, (str, int)) or isinstance(room_id, bool) or not str(room_id):
                raise GolaxyLobbyError("Golaxy room response malformed")
            meta = row.get("gameMetaDto") if isinstance(row.get("gameMetaDto"), dict) else {}
            state = meta.get("gameState") if isinstance(meta.get("gameState"), dict) else {}
            move_num = _lobby_count(state.get("moveNum"))
            room_state = row.get("gameroomStateDto") if isinstance(row.get("gameroomStateDto"), dict) else {}

            def player(color: str):
                code, name = meta.get(f"{color}UserCode"), meta.get(f"{color}Nickname")
                if not code or not name:
                    return None
                return {
                    "user_id": str(code),
                    "username": str(name),
                    "rank": _lobby_label(meta.get(f"{color}Level"), _LOBBY_RANKS),
                }

            rooms.append(
                {
                    "room_id": str(room_id),
                    "room_number": str(row["gameroomCode"]) if row.get("gameroomCode") is not None else None,
                    "room_type": _lobby_label(meta.get("gameType"), _LOBBY_GAME_TYPES),
                    "handicap": meta.get("handicap") if type(meta.get("handicap")) is int else None,
                    "black": player("black"),
                    "white": player("white"),
                    "phase": f"{move_num}手" if move_num is not None else None,
                    "move_number": move_num,
                    "room_user_count": _lobby_count(room_state.get("onlineUserCount")),
                    "spectator_count": None,
                }
            )
        return rooms

    async def get_room_snapshot(self, room_id: str) -> dict:
        """Replay the verified 19x19, no-handicap ordered history from room info."""
        room = await self._rest.get_gameroom_info(room_id)
        if str(room.get("id")) != room_id:
            raise GolaxyLobbyError("Golaxy room response malformed")
        meta = room.get("gameMetaDto")
        if not isinstance(meta, dict):
            raise GolaxyLobbyError("Golaxy room response malformed")
        setup = (meta.get("boardSize"), meta.get("handicap"), meta.get("startMoveNum"))
        if any(type(value) is not int for value in setup):
            raise GolaxyLobbyError("Golaxy room response malformed")
        if not isinstance(meta.get("gameType"), str) or not isinstance(meta.get("rule"), str):
            raise GolaxyLobbyError("Golaxy room response malformed")
        if setup != (19, 0, 0) or meta["gameType"] != "82" or meta["rule"] != "chinese":
            raise GolaxySnapshotUnsupported("Golaxy room setup not yet supported")
        state = meta.get("gameState")
        if not isinstance(state, dict):
            raise GolaxyLobbyError("Golaxy room response malformed")
        move_number = state.get("moveNum")
        if (
            type(move_number) is not int
            or type(meta.get("moveNum")) is not int
            or move_number < 0
            or meta["moveNum"] != move_number
        ):
            raise GolaxyLobbyError("Golaxy room response malformed")
        situation = state.get("situation")
        if not isinstance(situation, str):
            raise GolaxyLobbyError("Golaxy room response malformed")
        moves = [] if not situation and move_number == 0 else situation.split(",")
        if len(moves) != move_number or any(re.fullmatch(r"-?(?:0|[1-9][0-9]*)", item) is None for item in moves):
            raise GolaxyLobbyError("Golaxy room history malformed")

        from sgfmill import boards

        board = boards.Board(19)
        columns = "ABCDEFGHJKLMNOPQRST"
        ko_point = None
        history = []

        def position(number: int, last_move: dict | None) -> dict:
            black_stones = []
            white_stones = []
            for row in range(19):
                for col in range(19):
                    color = board.get(row, col)
                    if color == "b":
                        black_stones.append(f"{columns[col]}{row + 1}")
                    elif color == "w":
                        white_stones.append(f"{columns[col]}{row + 1}")
            return {
                "black_stones": black_stones,
                "white_stones": white_stones,
                "move_number": number,
                "last_move": last_move,
            }

        history.append(position(0, None))
        for turn, item in enumerate(moves):
            point = golaxy_to_katrain(int(item), 19)
            color = "B" if turn % 2 == 0 else "W"
            if isinstance(point, Pass):
                ko_point = None
                history.append(position(turn + 1, {"color": color, "coordinate": None}))
                continue
            if not isinstance(point, Move) or (point.row, point.col) == ko_point:
                raise GolaxyLobbyError("Golaxy room history malformed")
            try:
                ko_point = board.play(point.row, point.col, color.lower())
            except ValueError as exc:
                raise GolaxyLobbyError("Golaxy room history malformed") from exc
            # sgfmill handles captures but deliberately permits self-capture.
            if board.get(point.row, point.col) != color.lower():
                raise GolaxyLobbyError("Golaxy room history malformed")
            history.append(position(turn + 1, {"color": color, "coordinate": f"{columns[point.col]}{point.row + 1}"}))

        raw_game_ids = (room.get("wsGameId"), meta.get("wsGameId"), state.get("wsGameId"))
        meta_room_id = meta.get("gameroomId")
        game_id = (
            str(raw_game_ids[0])
            if all(type(value) is int and value > 0 and value == raw_game_ids[0] for value in raw_game_ids)
            and (meta_room_id is None or (type(meta_room_id) is int and meta_room_id == room["id"]))
            else None
        )
        latest = history[-1]

        def player(color: str) -> dict | None:
            name = meta.get(f"{color}Nickname")
            return {"username": name, "rank": None} if isinstance(name, str) and name else None

        room_status = room.get("gameroomStatus")
        phase = "进行中" if room_status == 30 else "已结束" if room_status == 40 else None
        room_number = room.get("gameroomCode")
        return {
            "room_id": room_id,
            "room_number": (
                str(room_number) if isinstance(room_number, (str, int)) and not isinstance(room_number, bool) else None
            ),
            "room_type": None,
            "handicap": 0,
            "board_size": 19,
            "black": player("black"),
            "white": player("white"),
            "black_stones": latest["black_stones"],
            "white_stones": latest["white_stones"],
            "move_number": move_number,
            "game_id": game_id,
            "last_move": latest["last_move"],
            "history": history,
            "clocks": None,
            "members": None,
            "phase": phase,
            "result": None,
        }

    async def get_online_users(self, room: Optional[str] = None) -> list[dict]:
        rows = await self._rest.list_gamezone_users()
        users = []
        for row in rows:
            code = row.get("userCode")
            name = row.get("followAlias") or row.get("nickname")
            if not code or not name:
                raise GolaxyLobbyError("Golaxy user response malformed")
            users.append(
                {
                    "user_id": str(code),
                    "username": str(name),
                    "rank": _lobby_label(row.get("level"), _LOBBY_RANKS),
                    "status": _lobby_presence(row),
                    "wins": _lobby_count(row.get("winNum")),
                    "losses": _lobby_count(row.get("loseNum")),
                    "invite_able": (
                        row["inviteAble"] in (True, 1, "1")
                        if row.get("inviteAble") in (True, False, 0, 1, "0", "1")
                        else None
                    ),
                    "avatar_url": _lobby_avatar(row),
                }
            )
        return users

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

        first_ai_move: Optional[PlatformEngineReply] = None
        # After N black handicap stones the side-to-move is White; with no handicap it
        # is Black. The AI opens exactly when the side-to-move equals the AI's color.
        # This preserves the existing 分先 behavior: human W + handicap 0 -> AI(black)
        # opens on an empty move list; human B + handicap 0 -> human(black) plays first.
        side_to_move = "W" if config.handicap >= 2 else "B"
        ai_color = "W" if config.human_color == "B" else "B"
        if side_to_move == ai_color:
            first_ai_move = await self._genmove_committing(ctx, proposed_moves=list(ctx.moves))

        return EngineGameStart(session=session, first_ai_move=first_ai_move)

    async def submit_engine_move(self, game_id: str, col: int, row: int) -> PlatformEngineReply:
        """Submit the human's move and return the AI's typed reply.

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

    async def submit_engine_pass(self, game_id: str) -> PlatformEngineReply:
        """Submit a verified Golaxy pass sentinel, then return the AI's reply."""
        ctx = self._engine_games.get(game_id)
        if ctx is None:
            raise KeyError(game_id)
        if ctx.status != "playing":
            raise RuntimeError(f"engine game {game_id} not playing (status={ctx.status})")
        proposed = list(ctx.moves) + [-1]
        return await self._genmove_committing(ctx, proposed)

    async def _genmove_committing(self, ctx: EngineGameContext, proposed_moves: list[int]) -> PlatformEngineReply:
        """Call genmove (with retry discipline) and commit exactly once.

        `proposed_moves` is the immutable snapshot of the history including the
        human move (if any). The canonical `ctx.moves` is written exactly once,
        only after a valid on-board AI coord returns.
        """
        result = await self._genmove_with_retry(ctx, proposed_moves)  # GenmoveResult
        decoded = golaxy_to_katrain(result.coord, ctx.config.board_size)
        ai_color = "W" if ctx.config.human_color == "B" else "B"
        if isinstance(decoded, Move):
            ctx.moves = list(proposed_moves) + [result.coord]  # single atomic commit
            return PlatformMove(
                col=decoded.col,
                row=decoded.row,
                color=ai_color,
                move_number=len(ctx.moves),
                game_id=ctx.game_id,
            )
        if isinstance(decoded, Pass):
            ctx.moves = list(proposed_moves) + [-1]
            return PlatformPass(color=ai_color, move_number=len(ctx.moves), game_id=ctx.game_id)
        if isinstance(decoded, Resign):
            ctx.moves = list(proposed_moves)
            ctx.status = "finished"
            winner = ctx.config.human_color
            await self._emit("game_ended", ctx.game_id, "ai_resign", winner)
            return PlatformResign(
                color=ai_color,
                winner=winner,
                move_number=len(ctx.moves),
                game_id=ctx.game_id,
            )
        assert isinstance(decoded, UnknownSpecial)
        ctx.moves = list(proposed_moves)
        ctx.status = "finished"
        await self._emit("game_ended", ctx.game_id, "ai_unknown_special", "")
        raise GolaxyEngineTerminal(f"AI returned unknown coord {decoded.raw!r}")

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

    async def fetch_item_counts(self) -> ItemCountsResult:
        """Remaining metered-道具 counts (领地/支招/变化图) for the connected
        account — powers the button badges. Account-level: no game context,
        so it works before/independently of any engine game.

        Mirrors _analysis_with_retry's auth-refresh-retry discipline:
        AuthExpired → refresh once + retry; Retryable → retry once; Fatal
        propagates. Missing/malformed counts come back as None from the client
        (never raise), so the badges degrade to "unknown" rather than block.
        """
        try:
            return await self._rest.fetch_item_counts()
        except AuthExpired:
            await self._rest.refresh_access_token()
            await self._emit("token_refreshed", self._rest.get_auth_data())
            try:
                return await self._rest.fetch_item_counts()
            except AuthExpired:
                await self._emit("auth_expired")
                raise
        except Retryable:
            return await self._rest.fetch_item_counts()

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

    def discard_engine_game(self, game_id: str) -> None:
        """Drop the stateless tunnel history after manager-side detachment."""

        ctx = self._engine_games.pop(game_id, None)
        if ctx is not None:
            ctx.status = "finished"

    def rebuild_engine_moves(self, game_id: str, path_moves: list[Optional[tuple[int, int]]]) -> None:
        """Reset an engine context's move list to handicap-prefix + the given
        post-handicap path (B3/G4).

        Decoupled recovery helper: the manager (which owns the KaTrain session)
        extracts the ordered (col, row) path from the CURRENT node back to the
        root (PlatformManager.rebuild_engine_context) and calls this after an
        undo/branch-nav, before the next genmove. This method does NOT read
        the session tree itself.

        `path_moves` must NOT include handicap stones -- those are ROOT SETUP
        placements locally (`place_handicap_stones`), not move nodes, so the
        manager's traversal naturally excludes them. This method re-derives
        the SAME handicap prefix `start_engine_game` originally seeded
        `ctx.moves` with (from `ctx.config.handicap`/`board_size`), so the
        rebuilt `ctx.moves` is byte-for-byte what the tunnel expects: prefix
        first, then the alternating post-handicap history.
        """
        ctx = self._engine_games.get(game_id)
        if ctx is None:
            raise KeyError(game_id)
        prefix = _handicap_stones(ctx.config.handicap, ctx.config.board_size)
        encoded = [
            -1 if move is None else katrain_to_golaxy(move[0], move[1], ctx.config.board_size) for move in path_moves
        ]
        ctx.moves = prefix + encoded
