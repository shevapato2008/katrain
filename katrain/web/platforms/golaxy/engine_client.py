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

Protocol reference (live-verified 2026-07-02):
    GET https://api.19x19.com/api/engine/dcnn/tunnel/genmove
    Header: Auth_token: <access_token>   # NOT "Authorization"
    Query params: moves, board_size, boardSize, komi, rule, handicap,
        level, style, elodiff, resign, org, context_name.
    Response: {"code": "0", "msg": "", "data": {"coord": 286, "prob": 0.19}}

See `superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md` Section 2 for
the full capture and Section 4 for the AI level table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

GOLAXY_GENMOVE_URL = "https://api.19x19.com/api/engine/dcnn/tunnel/genmove"
GENMOVE_TIMEOUT_SECONDS = 180.0  # strong bots think well past the default 30s client timeout

# Fixed/observed values from the live capture -- see golaxy-protocol.md
# Section 2. Not configurable; pass through verbatim.
_STYLE = 555559
_ELODIFF = 0
_RESIGN = 6
_ORG = "golaxy_web"
_CONTEXT_NAME = "ai_game_player"


@dataclass(frozen=True)
class GenmoveResult:
    """The AI's next move as decoded from the genmove tunnel response.

    `coord` is the raw Golaxy int coord (0..360 for a 19x19 board) --
    decoding it into a KaTrain (col, row) is the caller's job, using
    `golaxy/coords.py`. `prob` is the engine's confidence, informational.
    """

    coord: int
    prob: float


# --- Error taxonomy --------------------------------------------------------
#
# Callers MUST NOT swallow these -- a later task (the adapter) is expected to
# catch AuthExpired to refresh-and-retry-once, and Retryable to retry with
# the SAME request, while treating Fatal as non-retryable.


class GolaxyEngineError(Exception):
    """Base class for all errors raised by `engine_genmove`."""


class AuthExpired(GolaxyEngineError):
    """The access token is no longer valid.

    Raised on HTTP 401. The exact `code` string returned on a *200* auth
    failure was not captured during the live protocol dump (see
    golaxy-protocol.md Section 2) -- HTTP 401 is the only signal currently
    treated as authoritative for this. See `_classify_response_code` below
    for the single place to extend this once a real auth-failure `code` is
    observed on the wire.
    """


class Retryable(GolaxyEngineError):
    """A transient failure -- network error, timeout, or suspected
    rate-limiting (HTTP 429). Safe to retry with the SAME request."""


class Fatal(GolaxyEngineError):
    """A non-retryable failure: `code != "0"` (other than auth), a
    malformed/missing `data.coord`, or another 4xx/5xx not covered above."""


def _classify_response_code(code: str, msg: str) -> GolaxyEngineError:
    """Single place where a 200-response `code` maps to an error category.

    Today we have no verified auth-failure `code` string (only HTTP 401 is
    authoritative for AuthExpired -- see AuthExpired's docstring), so any
    non-"0" code on a 200 response is classified Fatal. When a real
    auth-failure `code` is captured, add it here rather than scattering the
    check elsewhere.
    """
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
    headers = {"Auth_token": access_token}

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


# --- AI level table ---------------------------------------------------------
#
# Copied verbatim (strongest-first) from
# superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md Section 4, sourced
# from the web client's Vuex `state.gameConfig.aiLevelList` (2026-07-02).
# `elo_score` is exactly the `level` query param for `engine_genmove`.

GOLAXY_AI_LEVELS: list[dict] = [
    {"elo_score": 3300, "level_name": "星阵3星", "name": "星猛虎", "goal_difference": 6, "timing": "60|60|3"},
    {"elo_score": 3200, "level_name": "星阵2星", "name": "星雄狮", "goal_difference": 6, "timing": "60|60|3"},
    {"elo_score": 3100, "level_name": "星阵1星", "name": "星巨象", "goal_difference": 6, "timing": "60|60|3"},
    {"elo_score": 3000, "level_name": "9段", "name": "星壮牛", "goal_difference": 5, "timing": "45|40|3"},
    {"elo_score": 2900, "level_name": "准9段", "name": "星蓝鲸", "goal_difference": 5, "timing": "45|40|3"},
    {"elo_score": 2800, "level_name": "8段", "name": "星美鹿", "goal_difference": 5, "timing": "45|40|3"},
    {"elo_score": 2600, "level_name": "准8段", "name": "星孤狼", "goal_difference": 5, "timing": "45|40|3"},
    {"elo_score": 2500, "level_name": "7段", "name": "星奇豚", "goal_difference": 4, "timing": "45|40|3"},
    {"elo_score": 2400, "level_name": "准7段", "name": "星萌猪", "goal_difference": 4, "timing": "45|40|3"},
    {"elo_score": 2300, "level_name": "6段", "name": "星骏马", "goal_difference": 4, "timing": "45|40|3"},
    {"elo_score": 2200, "level_name": "准6段", "name": "星呆羊", "goal_difference": 4, "timing": "45|40|3"},
    {"elo_score": 2100, "level_name": "5段", "name": "星跳鼠", "goal_difference": 4, "timing": "45|40|3"},
    {"elo_score": 2000, "level_name": "准5段", "name": "星云鹤", "goal_difference": 4, "timing": "40|30|3"},
    {"elo_score": 1900, "level_name": "4段", "name": "星灵狐", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1800, "level_name": "准4段", "name": "星白鹭", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1700, "level_name": "3段", "name": "星智狗", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1600, "level_name": "准3段", "name": "星巧猫", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1500, "level_name": "2段", "name": "星皮猴", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1400, "level_name": "准2段", "name": "星乖兔", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1300, "level_name": "1段", "name": "星树熊", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1200, "level_name": "准1段", "name": "星长蛇", "goal_difference": 3, "timing": "40|30|3"},
    {"elo_score": 1100, "level_name": "1级", "name": "星铠虾", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 1000, "level_name": "2级", "name": "星夜鹰", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 900, "level_name": "3级", "name": "星憨鹅", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 800, "level_name": "4级", "name": "星刺头", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 700, "level_name": "5级", "name": "星黄鸭", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 620, "level_name": "6级", "name": "星轻燕", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 540, "level_name": "7级", "name": "星绿蛙", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 460, "level_name": "8级", "name": "星老龟", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 380, "level_name": "9级", "name": "星钳蟹", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 300, "level_name": "10级", "name": "星尾鱼", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 290, "level_name": "11级", "name": "星敏螳", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 280, "level_name": "12级", "name": "星鸣蝉", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 270, "level_name": "13级", "name": "星飞蜓", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 260, "level_name": "14级", "name": "星舞蝶", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 250, "level_name": "15级", "name": "星忙蜂", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 240, "level_name": "16级", "name": "星慢蜗", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 230, "level_name": "17级", "name": "星花虫", "goal_difference": 2, "timing": "30|30|3"},
    {"elo_score": 220, "level_name": "18级", "name": "星小蚁", "goal_difference": 2, "timing": "30|30|3"},
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
