"""XingZhen (星阵围棋) API Client.

API Base: https://api.19x19.com/api/engine/golives

Endpoints:
- GET /all - All currently live matches
- GET /count - Count of live matches
- GET /history?page=0&size=10&live_type=TOP_LIVE - Historical matches
- GET /situation/{live_id}?no_cache=1 - Current position and moves
- GET /winrates/{live_id}?begin_move_num=X - Winrate history
- GET /base/{live_id}?begin_move_num=X&end_move_num=Y - Detailed analysis
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from katrain.web.live.models import LiveMatch, MatchSource, MatchStatus

logger = logging.getLogger("katrain_web.live.xingzhen")


class XingZhenClient:
    """Client for the XingZhen (19x19.com) live API."""

    DEFAULT_BASE_URL = "https://api.19x19.com/api/engine/golives"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an HTTP request with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (will be appended to base_url)
            **kwargs: Additional arguments to pass to httpx

        Returns:
            JSON response as dict

        Raises:
            Exception: If all retries fail
        """
        url = f"{self.base_url}{endpoint}"
        backoff = self.initial_backoff

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    logger.warning(f"XingZhen API HTTP error on attempt {attempt + 1}: {e.response.status_code}")
                    if e.response.status_code == 429:  # Rate limited
                        backoff *= 2  # More aggressive backoff for rate limits
                    elif e.response.status_code >= 500:
                        pass  # Retry server errors
                    else:
                        raise  # Don't retry client errors (4xx except 429)
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.warning(f"XingZhen API connection error on attempt {attempt + 1}: {e}")
                except Exception as e:
                    logger.error(f"XingZhen API unexpected error: {e}")
                    raise

                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff *= 2  # Exponential backoff

            raise Exception(f"XingZhen API request failed after {self.max_retries} attempts: {url}")

    async def get_live_matches(self) -> list[dict]:
        """Get all currently live matches.

        Returns:
            List of raw match data dicts from API
        """
        try:
            data = await self._request("GET", "/all")
            logger.debug(f"XingZhen /all raw response type: {type(data)}")

            if isinstance(data, list):
                logger.info(f"XingZhen /all returned {len(data)} matches (list)")
                if data:
                    logger.debug(f"First match sample: {data[0]}")
                return data

            # API returns {"code": "0", "msg": "", "data": [...]}
            inner = data.get("data", [])
            if isinstance(inner, list):
                logger.info(f"XingZhen /all returned {len(inner)} matches (data array)")
                if inner:
                    logger.debug(f"First match sample: {inner[0]}")
                return inner

            # Might be {"data": {"matches": [...]}}
            matches = inner.get("matches", inner.get("list", []))
            logger.info(f"XingZhen /all returned {len(matches)} matches (nested)")
            if matches:
                logger.debug(f"First match sample: {matches[0]}")
            return matches
        except Exception as e:
            logger.error(f"Failed to get live matches: {e}")
            return []

    async def get_live_count(self) -> int:
        """Get count of currently live matches."""
        try:
            data = await self._request("GET", "/count")
            if isinstance(data, int):
                return data
            return data.get("count", data.get("data", 0))
        except Exception as e:
            logger.error(f"Failed to get live count: {e}")
            return 0

    async def get_history(self, page: int = 0, size: int = 20, live_type: str = "TOP_LIVE") -> list[dict]:
        """Get historical matches.

        Args:
            page: Page number (0-indexed)
            size: Page size
            live_type: Type of matches to retrieve (TOP_LIVE for important matches)

        Returns:
            List of raw match data dicts
        """
        try:
            params = {"page": page, "size": size, "live_type": live_type}
            data = await self._request("GET", "/history", params=params)
            logger.debug(f"XingZhen /history raw response type: {type(data)}")

            if isinstance(data, list):
                logger.info(f"XingZhen /history returned {len(data)} matches (list)")
                return data

            # API returns {"code": "0", "msg": "", "data": {"matches": [...]}}
            inner = data.get("data", {})
            if isinstance(inner, list):
                logger.info(f"XingZhen /history returned {len(inner)} matches (data array)")
                return inner

            # Extract matches from nested structure
            matches = inner.get("matches", inner.get("content", inner.get("list", [])))
            logger.info(f"XingZhen /history returned {len(matches)} matches (nested)")
            return matches
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    async def get_situation(self, live_id: str, no_cache: bool = True) -> Optional[dict]:
        """Get current situation (position + moves) for a match.

        Args:
            live_id: Match ID from XingZhen
            no_cache: Whether to bypass cache

        Returns:
            Dict with match situation data or None, including:
            - liveMatch: Match metadata
            - moves: Comma-separated move indices
        """
        try:
            params = {"no_cache": 1 if no_cache else 0}
            data = await self._request("GET", f"/situation/{live_id}", params=params)
            # API returns {"code": "0", "data": {"liveMatch": {...}, "moves": "..."}}
            if isinstance(data, dict):
                inner = data.get("data", data)
                return inner
            return data
        except Exception as e:
            logger.error(f"Failed to get situation for {live_id}: {e}")
            return None

    async def get_winrates(self, live_id: str, begin_move_num: int = 0) -> Optional[dict]:
        """Get winrate history for a match.

        Args:
            live_id: Match ID from XingZhen
            begin_move_num: Starting move number

        Returns:
            Dict with winrate data or None
        """
        try:
            params = {"begin_move_num": begin_move_num}
            data = await self._request("GET", f"/winrates/{live_id}", params=params)
            return data
        except Exception as e:
            logger.error(f"Failed to get winrates for {live_id}: {e}")
            return None

    async def get_analysis(
        self, live_id: str, begin_move_num: int = 0, end_move_num: Optional[int] = None
    ) -> Optional[dict]:
        """Get detailed analysis for a range of moves.

        Args:
            live_id: Match ID from XingZhen
            begin_move_num: Starting move number
            end_move_num: Ending move number (optional)

        Returns:
            Dict with analysis data or None
        """
        try:
            params = {"begin_move_num": begin_move_num}
            if end_move_num is not None:
                params["end_move_num"] = end_move_num
            data = await self._request("GET", f"/base/{live_id}", params=params)
            return data
        except Exception as e:
            logger.error(f"Failed to get analysis for {live_id}: {e}")
            return None

    def parse_match(self, raw: dict) -> Optional[LiveMatch]:
        """Parse raw API response into LiveMatch model.

        Args:
            raw: Raw match data from XingZhen API
                 Can be flat structure or nested {"liveMatch": {...}, "moves": "..."}

        Returns:
            LiveMatch instance, or None if data is invalid
        """
        # Handle nested structure: {"liveMatch": {...}, "moves": "..."}
        # The /all endpoint returns this nested format
        if "liveMatch" in raw:
            match_data = raw["liveMatch"]
            # Moves might be at top level in nested structure
            top_level_moves = raw.get("moves")
        else:
            match_data = raw
            top_level_moves = None

        # XingZhen API field mapping:
        # liveId -> source_id
        # pb/pw -> player_black/player_white
        # liveStatus: 0=live, 40=finished
        # moveNum -> move_count
        # winrate -> current_winrate (0-1, black's winrate)
        # name -> tournament name

        live_id = str(match_data.get("liveId", match_data.get("id", "")))

        # Validate required fields
        if not live_id:
            logger.warning(f"Skipping match with empty liveId: {match_data}")
            return None

        player_black = match_data.get("pb") or match_data.get("blackPlayer")
        player_white = match_data.get("pw") or match_data.get("whitePlayer")

        if not player_black or not player_white:
            logger.warning(f"Skipping match {live_id} with missing players: pb={player_black}, pw={player_white}")
            return None

        status = MatchStatus.LIVE if match_data.get("liveStatus", 0) == 0 else MatchStatus.FINISHED

        # Parse date - handle complex startTime object or string
        match_date = datetime.now(timezone.utc)
        start_time = match_data.get("startTime")
        if start_time:
            if isinstance(start_time, dict):
                # Complex format: {"date": {"year": 2026, "month": 1, "day": 23}, "time": {...}}
                try:
                    date_part = start_time.get("date", {})
                    time_part = start_time.get("time", {})
                    match_date = datetime(
                        year=date_part.get("year", 2026),
                        month=date_part.get("month", 1),
                        day=date_part.get("day", 1),
                        hour=time_part.get("hour", 0),
                        minute=time_part.get("minute", 0),
                        second=time_part.get("second", 0),
                    )
                except (TypeError, ValueError):
                    pass
            elif isinstance(start_time, str):
                try:
                    match_date = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        match_date = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

        # Extract moves - check top_level_moves first (for nested structure), then match_data
        moves = []
        moves_data = top_level_moves or match_data.get("moves") or match_data.get("moveList")
        if moves_data:
            if isinstance(moves_data, str):
                moves = self._parse_moves_string(moves_data)
            elif isinstance(moves_data, list):
                moves = [str(m) for m in moves_data]

        # Get tournament name from 'name' field
        tournament = match_data.get("name") or match_data.get("eventName") or match_data.get("matchName") or "Unknown Tournament"

        # Parse game rules and komi
        board_size = match_data.get("boardSize") or 19
        komi = match_data.get("komi")
        if komi is None:
            # Default based on rules
            rules = match_data.get("rule") or match_data.get("rules") or "chinese"
            komi = 6.5 if rules == "japanese" else 7.5
        else:
            rules = match_data.get("rule") or match_data.get("rules") or "chinese"

        return LiveMatch(
            id=f"xingzhen_{live_id}",
            source=MatchSource.XINGZHEN,
            source_id=live_id,
            tournament=tournament,
            round_name=match_data.get("roundInfo") or match_data.get("round"),
            date=match_date,
            player_black=player_black,
            player_white=player_white,
            black_rank=match_data.get("pbLevel") or match_data.get("pbRank") or match_data.get("blackRank"),
            white_rank=match_data.get("pwLevel") or match_data.get("pwRank") or match_data.get("whiteRank"),
            status=status,
            result=match_data.get("gameResult") or match_data.get("result") or match_data.get("matchResult"),
            move_count=match_data.get("moveNum") or match_data.get("moveCount") or len(moves),
            current_winrate=match_data.get("winrate") if match_data.get("winrate") is not None else 0.5,
            current_score=match_data.get("score") or match_data.get("blackScore") or 0.0,
            moves=moves,
            last_updated=datetime.now(timezone.utc),
            board_size=board_size,
            komi=komi,
            rules=rules,
        )

    def _parse_moves_string(self, moves_str: str) -> list[str]:
        """Parse a moves string (various formats) into list of coordinates.

        Handles:
        - Comma-separated integers: "73,60,300,288,..." (XingZhen format: index = row * 19 + col)
        - SGF format: ;B[pd];W[dd];B[pq]...
        - Semicolon-separated: pd;dd;pq...
        - Space-separated: pd dd pq...
        """
        if not moves_str:
            return []

        moves = []

        # Check for comma-separated integers (XingZhen format)
        if "," in moves_str:
            parts = moves_str.split(",")
            try:
                # Test if these are integers
                int(parts[0].strip())
                # Parse as integer indices
                for p in parts:
                    p = p.strip()
                    if p:
                        try:
                            idx = int(p)
                            move = self._index_to_display(idx)
                            if move:
                                moves.append(move)
                        except ValueError:
                            pass
                return moves
            except ValueError:
                pass  # Not integer format, try other formats

        # Check for SGF format
        if "[" in moves_str and "]" in moves_str:
            import re
            # Extract moves from SGF notation: B[xx] or W[xx]
            pattern = r"[BW]\[([a-s]{2})\]"
            matches = re.findall(pattern, moves_str.lower())
            for coord in matches:
                # Convert SGF coords (a-s) to display coords
                moves.append(self._sgf_to_display(coord))
        elif ";" in moves_str:
            parts = moves_str.split(";")
            for p in parts:
                p = p.strip()
                if p and len(p) >= 2:
                    moves.append(p.upper())
        elif " " in moves_str:
            parts = moves_str.split()
            for p in parts:
                p = p.strip()
                if p and len(p) >= 2:
                    moves.append(p.upper())
        else:
            # Maybe already a single move or unknown format
            if len(moves_str) >= 2:
                moves.append(moves_str.upper())

        return moves

    def _index_to_display(self, index: int, board_size: int = 19) -> Optional[str]:
        """Convert XingZhen move index to display format.

        XingZhen uses index = row * 19 + col where:
        - row 0 = top row (row 19 in display)
        - col 0 = left column (column A)

        Args:
            index: Move index from XingZhen
            board_size: Board size (default 19)

        Returns:
            Display coordinate like "Q16" or None if invalid
        """
        if index < 0 or index >= board_size * board_size:
            return None

        row = index // board_size  # 0 = top
        col = index % board_size   # 0 = left (A)

        # Column: A=0, B=1, ..., H=7, J=8 (skip I)
        col_char = chr(ord('A') + col + (1 if col >= 8 else 0))

        # Row: 0=top(19), 18=bottom(1)
        display_row = board_size - row

        return f"{col_char}{display_row}"

    def _sgf_to_display(self, sgf_coord: str) -> str:
        """Convert SGF coordinate (e.g., 'pd') to display format (e.g., 'Q16').

        SGF uses a-s for columns and rows (1-indexed from top-left).
        Display uses A-T (skip I) for columns and 1-19 for rows (from bottom).
        """
        if len(sgf_coord) != 2:
            return sgf_coord.upper()

        col_char = sgf_coord[0].lower()
        row_char = sgf_coord[1].lower()

        # SGF column: a=0, b=1, ... s=18
        col_idx = ord(col_char) - ord("a")

        # Convert to display column (skip I): A=0, B=1, ..., H=7, J=8, ...
        display_col = chr(ord("A") + col_idx + (1 if col_idx >= 8 else 0))

        # SGF row: a=top (row 19), s=bottom (row 1)
        sgf_row = ord(row_char) - ord("a")
        display_row = 19 - sgf_row

        return f"{display_col}{display_row}"
