"""YikeWeiQi (弈客围棋) API client for katrain-cron.

API Base: https://api-new.yikeweiqi.com
Auth: HMAC-SHA1 with AppKey/AppSecret from public frontend JS.

Endpoints:
- GET /v1/golives?status=2&type=0&page_size=50  — live professional matches
- GET /v1/golives/{id}                           — match detail with full SGF
"""

import asyncio
import hashlib
import logging
import random
import re
import time
from datetime import datetime
from typing import Optional

import httpx

from katrain.cron import config
from katrain.cron.clients.xingzhen import _sgf_to_gtp

logger = logging.getLogger("katrain_cron.yike")


class YikeWeiQiClient:
    """HTTP client for the YikeWeiQi (弈客围棋) api-new."""

    def __init__(
        self,
        base_url: str | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
    ):
        self.base_url = (base_url or config.YIKE_BASE_URL).rstrip("/")
        self.app_key = app_key or config.YIKE_APP_KEY
        self.app_secret = app_secret or config.YIKE_APP_SECRET
        self.timeout = timeout
        self.max_retries = max_retries

    # ── Auth ────────────────────────────────────────────────

    def _make_headers(self) -> dict:
        """Generate HMAC-SHA1 auth headers (keys from public frontend JS)."""
        cur_time = str(int(time.time() * 1000))
        nonce = str(random.randint(100000, 999999))
        check_sum = hashlib.sha1((self.app_secret + nonce + cur_time).encode()).hexdigest()
        return {
            "AppKey": self.app_key,
            "CurTime": cur_time,
            "CheckSum": check_sum,
            "Nonce": nonce,
            "usertoken": "-1",
            "version": "96813",
            "Platform": "web",
            "app_id": "yike",
            "organization": "yike",
            "Accept": "application/json",
        }

    # ── HTTP helper ─────────────────────────────────────────

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}{endpoint}"
        backoff = 1.0
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    headers = self._make_headers()
                    headers.update(kwargs.pop("headers", {}))
                    resp = await client.request(method, url, headers=headers, **kwargs)
                    resp.raise_for_status()
                    data = resp.json()
                    if data.get("status") != 0:
                        logger.warning("YikeWeiQi API error: %s (endpoint=%s)", data, endpoint)
                        return {}
                    return data
                except httpx.HTTPStatusError as exc:
                    logger.warning("YikeWeiQi HTTP %s on attempt %d: %s", exc.response.status_code, attempt + 1, url)
                    if exc.response.status_code == 429:
                        backoff *= 2
                    elif exc.response.status_code < 500:
                        raise
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    logger.warning("YikeWeiQi connection error attempt %d: %s", attempt + 1, exc)
                except Exception:
                    logger.exception("YikeWeiQi unexpected error")
                    raise

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        raise RuntimeError(f"YikeWeiQi request failed after {self.max_retries} attempts: {url}")

    # ── Public API ──────────────────────────────────────────

    @staticmethod
    def _extract_data(data: dict) -> list[dict]:
        """Extract match list from API response (handles result.data or data nesting)."""
        if not data:
            return []
        # api-new wraps in result.data
        result = data.get("result", data)
        if isinstance(result, dict):
            return result.get("data", [])
        return []

    async def get_live_matches(self, match_type: int = 0) -> list[dict]:
        """Return list of currently live professional matches.

        Args:
            match_type: 0=professional (default), 1=broadcast, 4=smart board.
        """
        try:
            params = {"status": 2, "type": match_type, "page": 1, "page_size": 50}
            data = await self._request("GET", "/v1/golives", params=params)
            return self._extract_data(data)
        except Exception:
            logger.exception("Failed to get live matches from YikeWeiQi")
            return []

    async def get_finished_matches(self, page_size: int = 20) -> list[dict]:
        """Return recently finished professional matches."""
        try:
            data = await self._request("GET", "/v1/golives", params={"status": 3, "type": 0, "page": 1, "page_size": page_size})
            return self._extract_data(data)
        except Exception:
            logger.exception("Failed to get finished matches from YikeWeiQi")
            return []

    async def get_detail(self, game_id: int) -> dict | None:
        """Return full match detail including SGF."""
        try:
            data = await self._request("GET", f"/v1/golives/{game_id}")
            # Detail wraps in result
            result = data.get("result", data)
            if isinstance(result, dict) and "data" in result:
                return result["data"]
            return result if result else None
        except Exception:
            logger.exception("Failed to get detail for game %d from YikeWeiQi", game_id)
            return None

    # ── Parsing ─────────────────────────────────────────────

    # Tournament names that indicate non-professional content
    _NON_PRO_KEYWORDS = {"课堂记录", "高水平对弈", "教学", "课堂"}

    @staticmethod
    def parse_match_to_row(raw: dict) -> Optional[dict]:
        """Convert YikeWeiQi API response dict to a flat DB row dict.

        Returns None if required fields are missing or content is non-professional.
        """
        game_id = str(raw.get("id", ""))
        if not game_id:
            return None

        # Filter out non-professional content (classroom records, practice games)
        tournament = raw.get("game_name") or ""
        if any(kw in tournament for kw in YikeWeiQiClient._NON_PRO_KEYWORDS):
            return None

        player_black = raw.get("black_name") or (raw.get("black_player") or {}).get("player_name")
        player_white = raw.get("white_name") or (raw.get("white_player") or {}).get("player_name")
        if not player_black or not player_white:
            return None

        raw_status = str(raw.get("status", ""))
        status = "live" if raw_status == "2" else "finished" if raw_status == "3" else "live"

        # Parse date
        match_date = datetime.now()
        date_str = raw.get("game_date") or raw.get("broadcast_time")
        if date_str:
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    match_date = datetime.strptime(date_str[:len(fmt.replace("%", ""))], fmt)
                    break
                except (ValueError, IndexError):
                    continue

        # Parse moves from SGF
        sgf = raw.get("sgf") or raw.get("clean_sgf") or ""
        moves = _parse_sgf_moves(sgf)

        # Winrate: YikeWeiQi provides percentage (0-100), we store as ratio (0-1)
        winrate = 0.5
        meta = raw.get("meta") or {}
        if meta.get("black_win_rate") is not None:
            try:
                winrate = float(meta["black_win_rate"]) / 100.0
            except (TypeError, ValueError):
                pass

        tournament = raw.get("game_name") or "Unknown Tournament"

        komi = 7.5
        paste_val = raw.get("paste")
        if paste_val:
            try:
                komi = float(paste_val)
            except (TypeError, ValueError):
                pass

        return {
            "match_id": f"yike_{game_id}",
            "source": "yike",
            "source_id": game_id,
            "tournament": tournament,
            "round_name": None,
            "match_date": match_date,
            "player_black": player_black,
            "player_white": player_white,
            "black_rank": None,
            "white_rank": None,
            "status": status,
            "result": raw.get("game_result") or None,
            "move_count": raw.get("hands_count") or len(moves),
            "current_winrate": winrate,
            "current_score": 0.0,
            "moves": moves,
            "board_size": 19,
            "komi": komi,
            "rules": "chinese",
        }


# ── Move parsing ────────────────────────────────────────────


def _parse_sgf_moves(sgf: str) -> list[str]:
    """Extract GTP coordinate list from an SGF string."""
    if not sgf:
        return []
    coords = re.findall(r";[BW]\[([a-s]{2})\]", sgf, re.IGNORECASE)
    return [_sgf_to_gtp(c) for c in coords]
