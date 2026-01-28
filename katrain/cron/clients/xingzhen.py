"""XingZhen (星阵围棋) API client for katrain-cron.

API Base: https://api.19x19.com/api/engine/golives

Endpoints:
- GET /all       — all currently live matches
- GET /history   — historical matches (paginated)
- GET /situation/{live_id} — current position and moves
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

from katrain.cron import config

logger = logging.getLogger("katrain_cron.xingzhen")


class XingZhenClient:
    """HTTP client for the XingZhen (19x19.com) live match API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.base_url = (base_url or config.XINGZHEN_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    # ── HTTP helper ──────────────────────────────────────────

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict | list:
        url = f"{self.base_url}{endpoint}"
        backoff = 1.0
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    resp = await client.request(method, url, **kwargs)
                    resp.raise_for_status()
                    return resp.json()
                except httpx.HTTPStatusError as exc:
                    logger.warning("XingZhen HTTP %s on attempt %d: %s", exc.response.status_code, attempt + 1, url)
                    if exc.response.status_code == 429:
                        backoff *= 2
                    elif exc.response.status_code < 500:
                        raise
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    logger.warning("XingZhen connection error attempt %d: %s", attempt + 1, exc)
                except Exception:
                    logger.exception("XingZhen unexpected error")
                    raise

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        raise RuntimeError(f"XingZhen request failed after {self.max_retries} attempts: {url}")

    # ── Public API ───────────────────────────────────────────

    async def get_live_matches(self) -> list[dict]:
        """Return raw match dicts from /all."""
        try:
            data = await self._request("GET", "/all")
            return self._extract_list(data)
        except Exception:
            logger.exception("Failed to get live matches")
            return []

    async def get_history(self, page: int = 0, size: int = 20) -> list[dict]:
        """Return raw match dicts from /history."""
        try:
            data = await self._request("GET", "/history", params={"page": page, "size": size, "live_type": "TOP_LIVE"})
            return self._extract_list(data)
        except Exception:
            logger.exception("Failed to get history")
            return []

    async def get_situation(self, live_id: str) -> Optional[dict]:
        """Return situation dict for a live match."""
        try:
            data = await self._request("GET", f"/situation/{live_id}", params={"no_cache": 1})
            if isinstance(data, dict):
                return data.get("data", data)
            return data
        except Exception:
            logger.exception("Failed to get situation for %s", live_id)
            return None

    # ── Parsing helpers ──────────────────────────────────────

    @staticmethod
    def _extract_list(data) -> list[dict]:
        """Normalise various API response shapes into a plain list."""
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        inner = data.get("data", data)
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            return inner.get("matches", inner.get("content", inner.get("list", [])))
        return []

    @staticmethod
    def parse_match_to_row(raw: dict) -> Optional[dict]:
        """Convert raw API dict to a flat dict suitable for DB upsert.

        Returns None if required fields are missing.
        """
        if "liveMatch" in raw:
            md = raw["liveMatch"]
            top_moves = raw.get("moves")
        else:
            md = raw
            top_moves = None

        live_id = str(md.get("liveId", md.get("id", "")))
        if not live_id:
            return None

        player_black = md.get("pb") or md.get("blackPlayer")
        player_white = md.get("pw") or md.get("whitePlayer")
        if not player_black or not player_white:
            return None

        status = "live" if md.get("liveStatus", 0) == 0 else "finished"

        # Parse date
        match_date = datetime.now()
        start_time = md.get("startTime")
        if isinstance(start_time, dict):
            try:
                dp = start_time.get("date", {})
                tp = start_time.get("time", {})
                match_date = datetime(
                    dp.get("year", 2026), dp.get("month", 1), dp.get("day", 1),
                    tp.get("hour", 0), tp.get("minute", 0), tp.get("second", 0),
                )
            except (TypeError, ValueError):
                pass
        elif isinstance(start_time, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
                try:
                    match_date = datetime.fromisoformat(start_time.replace("Z", "+00:00")) if "T" in start_time else datetime.strptime(start_time, fmt)
                    break
                except ValueError:
                    continue

        # Parse moves
        moves_data = top_moves or md.get("moves") or md.get("moveList")
        moves = _parse_moves(moves_data)

        tournament = md.get("name") or md.get("eventName") or md.get("matchName") or "Unknown Tournament"

        board_size = md.get("boardSize") or 19
        rules = md.get("rule") or md.get("rules") or "chinese"
        komi = md.get("komi")
        if komi is None:
            komi = 6.5 if rules == "japanese" else 7.5

        return {
            "match_id": f"xingzhen_{live_id}",
            "source": "xingzhen",
            "source_id": live_id,
            "tournament": tournament,
            "round_name": md.get("roundInfo") or md.get("round"),
            "match_date": match_date,
            "player_black": player_black,
            "player_white": player_white,
            "black_rank": md.get("pbLevel") or md.get("pbRank") or md.get("blackRank"),
            "white_rank": md.get("pwLevel") or md.get("pwRank") or md.get("whiteRank"),
            "status": status,
            "result": md.get("gameResult") or md.get("result") or md.get("matchResult"),
            "move_count": md.get("moveNum") or md.get("moveCount") or len(moves),
            "current_winrate": md.get("winrate") if md.get("winrate") is not None else 0.5,
            "current_score": md.get("score") or md.get("blackScore") or 0.0,
            "moves": moves,
            "board_size": board_size,
            "komi": komi,
            "rules": rules,
        }


# ── Move parsing utilities ──────────────────────────────────


def _parse_moves(moves_data) -> list[str]:
    if not moves_data:
        return []
    if isinstance(moves_data, list):
        return [str(m) for m in moves_data]
    if not isinstance(moves_data, str):
        return []
    return _parse_moves_string(moves_data)


def _parse_moves_string(moves_str: str) -> list[str]:
    """Parse various move string formats into GTP coordinate list."""
    if not moves_str:
        return []

    # Comma-separated integers (XingZhen native format)
    if "," in moves_str:
        parts = moves_str.split(",")
        try:
            int(parts[0].strip())
            out = []
            for p in parts:
                p = p.strip()
                if p:
                    mv = _index_to_gtp(int(p))
                    if mv:
                        out.append(mv)
            return out
        except ValueError:
            pass

    # SGF notation: ;B[pd];W[dd]
    if "[" in moves_str and "]" in moves_str:
        import re
        coords = re.findall(r"[BW]\[([a-s]{2})\]", moves_str, re.IGNORECASE)
        return [_sgf_to_gtp(c) for c in coords]

    # Semicolon or space separated
    sep = ";" if ";" in moves_str else " "
    return [p.strip().upper() for p in moves_str.split(sep) if p.strip() and len(p.strip()) >= 2]


def _index_to_gtp(index: int, board_size: int = 19) -> Optional[str]:
    """XingZhen index (row*19+col) to GTP coordinate (e.g. Q16)."""
    if index < 0 or index >= board_size * board_size:
        return None
    row = index // board_size
    col = index % board_size
    col_char = chr(ord("A") + col + (1 if col >= 8 else 0))  # skip I
    display_row = board_size - row
    return f"{col_char}{display_row}"


def _sgf_to_gtp(sgf_coord: str) -> str:
    """SGF coordinate (e.g. 'pd') to GTP coordinate (e.g. 'Q16')."""
    if len(sgf_coord) != 2:
        return sgf_coord.upper()
    col_idx = ord(sgf_coord[0].lower()) - ord("a")
    row_idx = ord(sgf_coord[1].lower()) - ord("a")
    col_char = chr(ord("A") + col_idx + (1 if col_idx >= 8 else 0))
    display_row = 19 - row_idx
    return f"{col_char}{display_row}"
