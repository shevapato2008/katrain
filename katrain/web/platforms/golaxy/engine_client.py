"""Golaxy / 星阵围棋 (19x19.com) human-vs-AI "genmove" tunnel client.

This is a **stateless** HTTP tunnel -- there is no gameId, no WebSocket, no
server-side session. The caller owns the full move history and, on every
turn, sends the complete `moves` list; the tunnel returns the AI's next raw
coord int (decoding it into a board point is the caller's job -- see
`katrain/web/platforms/golaxy/coords.py`, deliberately NOT imported here).

Keep this module SEPARATE from `golaxy/adapter.py`, which implements auth and
the human-vs-human gameroom REST/STOMP path -- an entirely different flow
that must not be confused with this one (see
`superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md` Section 7).

Protocol reference (auth header re-confirmed on real hardware 2026-07-03):
    GET https://api.19x19.com/api/engine/dcnn/tunnel/genmove
    Header: Authorization: bearer <access_token>   # + browser Origin/Referer/UA
    Query params: moves, board_size, boardSize, komi, rule, handicap,
        level, style, elodiff, resign, org, context_name.
    Response: {"code": "0", "msg": "", "data": {"coord": 286, "prob": 0.19}}

NOTE: the earlier capture (golaxy-protocol.md, 2026-07-02) documented the auth
header as `Auth_token: <access_token>`. Live testing on 2026-07-03 proved that
form is rejected with HTTP 200 `code=6003 msg="invalid token"` even for a valid
fresh token; the tunnel actually requires the SAME `Authorization: bearer <token>`
scheme as the social endpoints, plus browser-like Origin/Referer/User-Agent.

See `superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md` Section 2 for
the full capture and Section 4 for the AI level table.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import httpx

GOLAXY_GENMOVE_URL = "https://api.19x19.com/api/engine/dcnn/tunnel/genmove"
GOLAXY_AREA_URL = "https://api.19x19.com/api/engine/dcnn/tunnel/area"
GOLAXY_OPTIONS_URL = "https://api.19x19.com/api/engine/dcnn/tunnel/options"
GOLAXY_JUDGE_URL = "https://api.19x19.com/api/engine/dcnn/tunnel/judge"
GOLAXY_VARIATION_URL = "https://api.19x19.com/api/engine/dcnn/tunnel/variation"
# Remaining metered-道具 counts (领地/支招/变化图 badges). Account-level, not a
# tunnel: GET /items/{username}. Source-derived from app.js `userToolGet`; see
# golaxy-protocol.md Section 9.4a. Username == the Golaxy login principal
# `0086-{phone}` (== store.state.username / keep_login_username).
GOLAXY_ITEMS_URL = "https://api.19x19.com/api/engine/items/"
GENMOVE_TIMEOUT_SECONDS = 180.0  # strong bots think well past the default 30s client timeout
ITEMS_TIMEOUT_SECONDS = 20.0  # matches the web client (userToolGet timeout:2e4); a plain GET
_ANALYSIS_LEVEL = 8888  # full-strength analysis engine, independent of the opponent bot's level

# Fixed/observed values from the live capture -- see golaxy-protocol.md
# Section 2. Not configurable; pass through verbatim.
_STYLE = 555559
_ELODIFF = 0
_RESIGN = 6
_ORG = "golaxy_web"
_CONTEXT_NAME = "ai_game_player"

# Browser-like request headers. Live-confirmed on real hardware 2026-07-03 (Phase 5):
# the tunnel rejects the previously-documented `Auth_token: <token>` header with
# `code=6003 msg="invalid token"` (even for a valid fresh token) and requires the
# standard `Authorization: bearer <token>` scheme plus a browser-shaped request.
_ORIGIN = "https://19x19.com"
_REFERER = "https://19x19.com/engine/play/normal/game"
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class GenmoveResult:
    """The AI's next move as decoded from the genmove tunnel response.

    `coord` is the raw Golaxy int coord (0..360 for a 19x19 board) --
    decoding it into a KaTrain (col, row) is the caller's job, using
    `golaxy/coords.py`. `prob` is the engine's confidence, informational.
    """

    coord: int
    prob: float


@dataclass(frozen=True)
class AreaResult:
    """Per-point ownership + winrate/delta from the `area` (领地) tunnel.

    `area` is the RAW wire list verbatim (observed length 722 = 361*2 in the
    live capture) -- this client does NOT slice or interpret it; the adapter
    layer applies the first-361-is-ownership semantics (see
    golaxy-protocol.md Section 9.5).
    """

    area: list[float]
    winrate: float
    delta: float


@dataclass(frozen=True)
class OptionsResult:
    """Candidate moves from the `options` (支招) tunnel.

    Four equal-length parallel arrays indexed by candidate rank: `coord[i]`
    is the raw Golaxy coord int, `prob[i]` its recommendation probability,
    `winrate[i]`/`delta[i]` the resulting position evaluation.
    """

    coord: list[int]
    prob: list[float]
    winrate: list[float]
    delta: list[float]


@dataclass(frozen=True)
class VariationResult:
    """One AI variation line from the `variation` (变化图) tunnel.

    `coord` is the raw Golaxy coord int sequence for the variation (no need
    to specify which move to expand from -- the tunnel returns the main
    variation). `winrate`/`delta` evaluate the resulting position.
    """

    coord: list[int]
    winrate: float
    delta: float


@dataclass(frozen=True)
class JudgeResult:
    """Whole-board verdict from the `judge` (形势) tunnel.

    `belong` is a raw 361-char string, one char per board point (index =
    Golaxy coord), each `U` (undecided) / `B` (black) / `W` (white).
    `winner` is `U`/`B`/`W`/`D` (draw); `delta` is the score margin.
    """

    belong: str
    winner: str
    delta: float


@dataclass(frozen=True)
class ItemCountsResult:
    """Remaining metered-道具 use counts for the three in-game analysis tunnels.

    Each is the per-account remaining count from `GET /items/{username}`
    (领地=area, 支招=options, 变化图=variation) — the numbers Golaxy renders as
    button badges. `None` means the key was absent or non-integer in the
    response: surface it as "unknown" (no badge), NEVER as `0`, so a parse gap
    can't masquerade as "quota exhausted". `judge` (形势) is free and has no
    count, so it is deliberately absent here.
    """

    area: Optional[int]
    options: Optional[int]
    variation: Optional[int]


# --- Error taxonomy --------------------------------------------------------
#
# Callers MUST NOT swallow these -- a later task (the adapter) is expected to
# catch AuthExpired to refresh-and-retry-once, and Retryable to retry with
# the SAME request, while treating Fatal as non-retryable.


class GolaxyEngineError(Exception):
    """Base class for all errors raised by `engine_genmove`."""


class AuthExpired(GolaxyEngineError):
    """The access token is no longer valid.

    Raised on HTTP 401, and on the 200-response auth failure the tunnel
    actually returns: `code="6003" msg="invalid token"` (live-confirmed
    2026-07-03). The adapter catches this to refresh the token and retry once.
    See `_classify_response_code` for the single mapping point.
    """


class Retryable(GolaxyEngineError):
    """A transient failure -- network error, timeout, or suspected
    rate-limiting (HTTP 429). Safe to retry with the SAME request."""


class Fatal(GolaxyEngineError):
    """A non-retryable failure: `code != "0"` (other than auth), a
    malformed/missing `data.coord`, or another 4xx/5xx not covered above."""


class QuotaExhausted(GolaxyEngineError):
    """The analysis tunnel's metered 道具 (item) is out of uses.

    Raised on body `code == "7003" msg == "item is not sufficient"` --
    live-confirmed 2026-07-07 for `area`/`options`/`variation` (each has an
    independent per-account use count; `judge` was observed free). This is
    NOT retryable (retrying the same request just burns/re-hits the same
    empty quota) and NOT an auth failure -- surface it downstream as
    "次数不足·请在星阵充值" (top up on Golaxy), distinct from Fatal so callers
    can special-case the UI messaging.
    """


def _classify_response_code(code: str, msg: str) -> GolaxyEngineError:
    """Single place where a 200-response `code` maps to an error category.

    Golaxy signals an expired/invalid token as an HTTP-200 body with
    `code="6003" msg="invalid token"` (NOT an HTTP 401) -- live-confirmed
    2026-07-03. Map that to AuthExpired so the adapter refreshes-and-retries;
    every other non-"0" code is a genuine Fatal.
    """
    if code == "6003" or "invalid token" in (msg or "").lower():
        return AuthExpired(f"Golaxy genmove auth failure: code={code!r} msg={msg!r}")
    return Fatal(f"Golaxy genmove failed: code={code!r} msg={msg!r}")


async def engine_genmove(
    client: httpx.AsyncClient,
    *,
    moves: list[int],
    level: int,
    access_token: str,
    komi: float = 7.5,
    rule: str = "chinese",
    handicap: int = 0,
    board_size: int = 19,
) -> GenmoveResult:
    """Call the Golaxy genmove tunnel and return the AI's next raw coord.

    `client` is an injected `httpx.AsyncClient` (tests pass one built on
    `httpx.MockTransport`; the adapter can pass its own client) -- this
    function never constructs its own client. The full absolute URL is
    always used (see GOLAXY_GENMOVE_URL) so this works regardless of
    whether the injected client has a `base_url` configured.

    Raises `AuthExpired`, `Retryable`, or `Fatal` -- see the class
    docstrings above. Never swallows an error.
    """
    params = {
        "moves": ",".join(str(m) for m in moves),
        "board_size": board_size,
        "boardSize": board_size,
        "komi": komi,
        "rule": rule,
        "handicap": handicap,
        "level": level,
        "style": _STYLE,
        "elodiff": _ELODIFF,
        "resign": _RESIGN,
        "org": _ORG,
        "context_name": _CONTEXT_NAME,
    }
    headers = {
        "Authorization": f"bearer {access_token}",
        "Origin": _ORIGIN,
        "Referer": _REFERER,
        "User-Agent": _BROWSER_UA,
    }

    try:
        response = await client.get(
            GOLAXY_GENMOVE_URL,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(GENMOVE_TIMEOUT_SECONDS, connect=10.0),
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise Retryable(f"Golaxy genmove network error: {exc}") from exc

    if response.status_code == 401:
        raise AuthExpired("Golaxy genmove: HTTP 401 (token expired or invalid)")
    if response.status_code == 429:
        raise Retryable("Golaxy genmove: HTTP 429 (rate limited)")
    if not (200 <= response.status_code < 300):
        raise Fatal(f"Golaxy genmove: HTTP {response.status_code}: {response.text!r}")

    body = response.json()
    code = body.get("code")
    if code != "0":
        raise _classify_response_code(code, body.get("msg", ""))

    data = body.get("data") or {}
    coord = data.get("coord")
    if not isinstance(coord, int) or isinstance(coord, bool):
        raise Fatal(f"Golaxy genmove: missing or non-int data.coord: {coord!r}")

    prob = data.get("prob", 0.0)
    return GenmoveResult(coord=coord, prob=prob)


# --- In-game analysis tunnels (area/options/judge/variation) ---------------
#
# Siblings of `engine_genmove` above: same host, same auth, same coord
# encoding, GET with query params -- but these are the metered 道具 the
# Golaxy web client itself pays for (领地/支招/变化图), and `judge` (形势).
# See golaxy-protocol.md Section 9 (+ 9.5 for the live-captured bodies).

_ANALYSIS_URLS: dict[str, str] = {
    "area": GOLAXY_AREA_URL,
    "options": GOLAXY_OPTIONS_URL,
    "judge": GOLAXY_JUDGE_URL,
    "variation": GOLAXY_VARIATION_URL,
}


def _unwrap_data(data) -> dict:
    """`data` may arrive as a JSON string for `options`/`variation` (the web
    client's `parseData` does `JSON.parse` when it is a string) -- `area`
    and `judge` were observed as objects already. Handle both."""
    if isinstance(data, str):
        return json.loads(data) if data else {}
    return data if isinstance(data, dict) else {}


async def engine_analysis(
    client: httpx.AsyncClient,
    *,
    kind: str,
    moves: list[int],
    access_token: str,
    komi: float = 7.5,
    rule: str = "chinese",
    handicap: int = 0,
    board_size: int = 19,
    level: int = _ANALYSIS_LEVEL,
) -> AreaResult | OptionsResult | VariationResult | JudgeResult:
    """Call one of the Golaxy in-game analysis tunnels and return a typed result.

    `kind` selects the tunnel: `"area"` (领地), `"options"` (支招),
    `"judge"` (形势), or `"variation"` (变化图). An unknown `kind` is a
    programming error, not a wire error, so it raises `ValueError` directly
    (no network call is made).

    `client` is an injected `httpx.AsyncClient`, mirroring `engine_genmove`
    -- this function never constructs its own client. `level` defaults to
    8888 (full-strength analysis engine), independent of the opponent bot's
    level used for `engine_genmove`.

    Raises `AuthExpired`, `Retryable`, `Fatal`, or `QuotaExhausted` (the
    latter on body `code == "7003"`, meaning the metered 道具 is out of
    uses) -- see the class docstrings above. Never swallows an error.
    """
    if kind not in _ANALYSIS_URLS:
        raise ValueError(f"engine_analysis: unknown kind {kind!r}; expected one of {sorted(_ANALYSIS_URLS)}")
    url = _ANALYSIS_URLS[kind]

    params = {
        "moves": ",".join(str(m) for m in moves),
        "board_size": board_size,
        "boardSize": board_size,
        "boardsize": board_size,
        "komi": komi,
        "rule": rule,
        "handicap": handicap,
        "level": level,
        "style": _STYLE,
        "org": _ORG,
        "context_name": _CONTEXT_NAME,
    }
    headers = {
        "Authorization": f"bearer {access_token}",
        "Origin": _ORIGIN,
        "Referer": _REFERER,
        "User-Agent": _BROWSER_UA,
    }

    try:
        response = await client.get(
            url,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(GENMOVE_TIMEOUT_SECONDS, connect=10.0),
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise Retryable(f"Golaxy {kind} network error: {exc}") from exc

    if response.status_code == 401:
        raise AuthExpired(f"Golaxy {kind}: HTTP 401 (token expired or invalid)")
    if response.status_code == 429:
        raise Retryable(f"Golaxy {kind}: HTTP 429 (rate limited)")
    if not (200 <= response.status_code < 300):
        raise Fatal(f"Golaxy {kind}: HTTP {response.status_code}: {response.text!r}")

    body = response.json()
    code = body.get("code")
    if code == "7003":
        raise QuotaExhausted(f"Golaxy {kind}: item is not sufficient (code=7003 msg={body.get('msg', '')!r})")
    if code != "0":
        raise _classify_response_code(code, body.get("msg", ""))

    data = _unwrap_data(body.get("data"))

    if kind == "area":
        area = data.get("area")
        if not isinstance(area, list):
            raise Fatal(f"Golaxy area: missing or non-list data.area: {area!r}")
        return AreaResult(area=area, winrate=data.get("winrate"), delta=data.get("delta"))

    if kind == "options":
        coord = data.get("coord")
        if not isinstance(coord, list):
            raise Fatal(f"Golaxy options: missing or non-list data.coord: {coord!r}")
        # coord is required (candidates are drawn from it); the parallel
        # per-move fields (prob/winrate/delta) are best-effort per §13 --
        # default a missing/None array to [] rather than raise, so the
        # adapter can still draw candidate points from coord alone.
        return OptionsResult(
            coord=coord,
            prob=data.get("prob") or [],
            winrate=data.get("winrate") or [],
            delta=data.get("delta") or [],
        )

    if kind == "variation":
        coord = data.get("coord")
        if not isinstance(coord, list):
            raise Fatal(f"Golaxy variation: missing or non-list data.coord: {coord!r}")
        # winrate/delta are best-effort scalars per §13 -- default to 0.0
        # when absent rather than raise; coord stays required.
        return VariationResult(coord=coord, winrate=data.get("winrate") or 0.0, delta=data.get("delta") or 0.0)

    # kind == "judge"
    belong = data.get("belong")
    if not isinstance(belong, str):
        raise Fatal(f"Golaxy judge: missing or non-str data.belong: {belong!r}")
    return JudgeResult(belong=belong, winner=data.get("winner", "U"), delta=data.get("delta"))


# --- Remaining-道具 counts (button badges) ----------------------------------


def _coerce_count(value) -> Optional[int]:
    """Best-effort parse of a remaining-count field into an int, or None.

    Accepts a plain int or a numeric string (the web client's `data` may
    arrive JSON-string-encoded). `bool` is rejected (it is an int subclass but
    never a valid count), and anything else → None ("unknown", not 0).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


async def fetch_item_counts(
    client: httpx.AsyncClient,
    *,
    username: str,
    access_token: str,
) -> ItemCountsResult:
    """Fetch remaining metered-道具 counts via Golaxy `GET /items/{username}`.

    `username` is the Golaxy login principal, i.e. `0086-{phone}` (== what the
    login form sends, == `store.state.username` / localStorage
    `keep_login_username`). Source-derived from app.js `userToolGet`; see
    golaxy-protocol.md Section 9.4a.

    Same host/auth/browser-headers as the tunnels. Response is `{code, data}`
    where `data` may be a JSON string (parsed via `_unwrap_data`); the counts
    are top-level integer keys `area`/`options`/`variation`. Missing/malformed
    keys degrade to `None` (see `_coerce_count`) rather than raise, so a shape
    drift never blocks play. Raises `AuthExpired`/`Retryable`/`Fatal` on the
    wire like the sibling calls; never swallows an error.
    """
    if not username:
        raise Fatal("Golaxy items: no username available (cannot build /items/{username})")
    url = GOLAXY_ITEMS_URL + urllib.parse.quote(username, safe="")
    headers = {
        "Authorization": f"bearer {access_token}",
        "Origin": _ORIGIN,
        "Referer": _REFERER,
        "User-Agent": _BROWSER_UA,
    }

    try:
        response = await client.get(
            url,
            headers=headers,
            timeout=httpx.Timeout(ITEMS_TIMEOUT_SECONDS, connect=10.0),
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise Retryable(f"Golaxy items network error: {exc}") from exc

    if response.status_code == 401:
        raise AuthExpired("Golaxy items: HTTP 401 (token expired or invalid)")
    if response.status_code == 429:
        raise Retryable("Golaxy items: HTTP 429 (rate limited)")
    if not (200 <= response.status_code < 300):
        raise Fatal(f"Golaxy items: HTTP {response.status_code}: {response.text!r}")

    body = response.json()
    code = body.get("code")
    if code != "0":
        raise _classify_response_code(code, body.get("msg", ""))

    data = _unwrap_data(body.get("data"))
    return ItemCountsResult(
        area=_coerce_count(data.get("area")),
        options=_coerce_count(data.get("options")),
        variation=_coerce_count(data.get("variation")),
    )


# --- AI level table ---------------------------------------------------------
#
# Copied verbatim (strongest-first) from
# superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md Section 4, sourced
# from the web client's Vuex `state.gameConfig.aiLevelList` (2026-07-02).
# `elo_score` is exactly the `level` query param for `engine_genmove`.

_GOLAXY_ROWS = [
    (3300, "星阵3星", "星猛虎", 6, "60|60|3"),
    (3200, "星阵2星", "星雄狮", 6, "60|60|3"),
    (3100, "星阵1星", "星巨象", 6, "60|60|3"),
    (3000, "9段", "星壮牛", 5, "45|40|3"),
    (2900, "准9段", "星蓝鲸", 5, "45|40|3"),
    (2800, "8段", "星美鹿", 5, "45|40|3"),
    (2600, "准8段", "星孤狼", 5, "45|40|3"),
    (2500, "7段", "星奇豚", 4, "45|40|3"),
    (2400, "准7段", "星萌猪", 4, "45|40|3"),
    (2300, "6段", "星骏马", 4, "45|40|3"),
    (2200, "准6段", "星呆羊", 4, "45|40|3"),
    (2100, "5段", "星跳鼠", 4, "45|40|3"),
    (2000, "准5段", "星云鹤", 4, "40|30|3"),
    (1900, "4段", "星灵狐", 3, "40|30|3"),
    (1800, "准4段", "星白鹭", 3, "40|30|3"),
    (1700, "3段", "星智狗", 3, "40|30|3"),
    (1600, "准3段", "星巧猫", 3, "40|30|3"),
    (1500, "2段", "星皮猴", 3, "40|30|3"),
    (1400, "准2段", "星乖兔", 3, "40|30|3"),
    (1300, "1段", "星树熊", 3, "40|30|3"),
    (1200, "准1段", "星长蛇", 3, "40|30|3"),
    (1100, "1级", "星铠虾", 2, "30|30|3"),
    (1000, "2级", "星夜鹰", 2, "30|30|3"),
    (900, "3级", "星憨鹅", 2, "30|30|3"),
    (800, "4级", "星刺头", 2, "30|30|3"),
    (700, "5级", "星黄鸭", 2, "30|30|3"),
    (620, "6级", "星轻燕", 2, "30|30|3"),
    (540, "7级", "星绿蛙", 2, "30|30|3"),
    (460, "8级", "星老龟", 2, "30|30|3"),
    (380, "9级", "星钳蟹", 2, "30|30|3"),
    (300, "10级", "星尾鱼", 2, "30|30|3"),
    (290, "11级", "星敏螳", 2, "30|30|3"),
    (280, "12级", "星鸣蝉", 2, "30|30|3"),
    (270, "13级", "星飞蜓", 2, "30|30|3"),
    (260, "14级", "星舞蝶", 2, "30|30|3"),
    (250, "15级", "星忙蜂", 2, "30|30|3"),
    (240, "16级", "星慢蜗", 2, "30|30|3"),
    (230, "17级", "星花虫", 2, "30|30|3"),
    (220, "18级", "星小蚁", 2, "30|30|3"),
]
_DISPLAY_BOTTOM = {
    "6级": 600,
    "7级": 500,
    "8级": 400,
    "9级": 300,
    "10级": 200,
    "11级": 100,
    "12级": 0,
    "13级": -100,
    "14级": -200,
    "15级": -300,
    "16级": -400,
    "17级": -500,
    "18级": -600,
}
_DISPLAY_TOP = {"9段": 3100, "星阵1星": 3400, "星阵2星": 3700, "星阵3星": 4000}


def _display_elo(level_name, elo_score):
    if level_name in _DISPLAY_BOTTOM:
        return _DISPLAY_BOTTOM[level_name]
    if level_name in _DISPLAY_TOP:
        return _DISPLAY_TOP[level_name]
    return elo_score  # middle band 5级..准9段: identical (PRD §2)


def _ref_rank(level_name):
    # PROVISIONAL UI hint (Golaxy nominal runs strong; pro saturates to 野狐9D). Refined post-calibration.
    if level_name in ("星阵1星", "星阵2星", "星阵3星"):
        return "职业/野狐9D+"
    if level_name in ("9段", "准9段", "8段", "准8段", "7段", "准7段"):
        return "野狐9D"
    return f"业余{level_name}"


GOLAXY_AI_LEVELS: list[dict] = [
    {
        "elo_score": elo,
        "level_name": n,
        "name": bot,
        "goal_difference": gd,
        "timing": t,
        "display_elo": _display_elo(n, elo),
        "ref_rank": _ref_rank(n),
    }
    for (elo, n, bot, gd, t) in _GOLAXY_ROWS
]


def get_level(elo_score: int) -> Optional[dict]:
    """Look up a `GOLAXY_AI_LEVELS` row by `elo_score` (the `level` query
    param). Returns None if no row matches."""
    for entry in GOLAXY_AI_LEVELS:
        if entry["elo_score"] == elo_score:
            return entry
    return None


def list_levels() -> list[dict]:
    """Return the full AI level table (a shallow copy) for the API layer."""
    return list(GOLAXY_AI_LEVELS)
