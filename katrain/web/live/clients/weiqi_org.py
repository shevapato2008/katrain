"""China Weiqi Association (中国围棋协会) API Client.

API Base: https://wqapi.cwql.org.cn

Endpoints:
- POST /playerInfo/battle/list - Get battle/match list
- GET /playerInfo/battle/{battleNo} - Get battle details with SGF
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

from katrain.web.live.models import LiveMatch, MatchSource, MatchStatus

logger = logging.getLogger("katrain_web.live.weiqi_org")


class WeiqiOrgClient:
    """Client for the China Weiqi Association API (wqapi.cwql.org.cn)."""

    DEFAULT_BASE_URL = "https://wqapi.cwql.org.cn"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
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

        # Default headers for this API
        headers = kwargs.pop("headers", {})
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.request(method, url, headers=headers, **kwargs)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    logger.warning(f"WeiqiOrg API HTTP error on attempt {attempt + 1}: {e.response.status_code}")
                    if e.response.status_code == 429:
                        backoff *= 2
                    elif e.response.status_code >= 500:
                        pass
                    else:
                        raise
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.warning(f"WeiqiOrg API connection error on attempt {attempt + 1}: {e}")
                except Exception as e:
                    logger.error(f"WeiqiOrg API unexpected error: {e}")
                    raise

                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff *= 2

            raise Exception(f"WeiqiOrg API request failed after {self.max_retries} attempts: {url}")

    async def get_battle_list(
        self,
        page_num: int = 1,
        page_size: int = 20,
        game_kifu: int = 1,
        player_name: Optional[str] = None,
        game_name: Optional[str] = None,
    ) -> list[dict]:
        """Get list of battles/matches.

        Args:
            page_num: Page number (1-indexed)
            page_size: Number of results per page
            game_kifu: Filter for games with kifu (1=has SGF)
            player_name: Filter by player name
            game_name: Filter by tournament name

        Returns:
            List of raw battle data dicts
        """
        try:
            payload = {
                "pageNum": page_num,
                "pageSize": page_size,
                "gameKifu": game_kifu,
            }
            if player_name:
                payload["playerName"] = player_name
            if game_name:
                payload["gameName"] = game_name

            data = await self._request("POST", "/playerInfo/battle/list", json=payload)

            # Response format: {"code": 0, "msg": "...", "data": {"records": [...]}}
            # Note: code is 0 for success, not 200
            if data.get("code") == 0:
                inner = data.get("data", {})
                return inner.get("records", inner.get("list", []))
            else:
                logger.warning(f"WeiqiOrg API returned error code: {data.get('code')}, msg: {data.get('msg')}")
                return []
        except Exception as e:
            logger.error(f"Failed to get battle list: {e}")
            return []

    async def get_battle_detail(self, battle_no: str) -> Optional[dict]:
        """Get detailed battle info including SGF.

        Args:
            battle_no: Battle number/ID

        Returns:
            Dict with battle details or None
        """
        try:
            data = await self._request("GET", f"/playerInfo/battle/{battle_no}")

            # code is 0 for success
            if data.get("code") == 0:
                return data.get("data")
            else:
                logger.warning(f"WeiqiOrg API returned error for battle {battle_no}: code={data.get('code')}, msg={data.get('msg')}")
                return None
        except Exception as e:
            logger.error(f"Failed to get battle detail for {battle_no}: {e}")
            return None

    def parse_match(self, raw: dict, detail: Optional[dict] = None) -> LiveMatch:
        """Parse raw API response into LiveMatch model.

        Args:
            raw: Raw battle data from list endpoint
            detail: Optional detailed data from detail endpoint

        Returns:
            LiveMatch instance
        """
        # WeiqiOrg API field mapping:
        # battleNo -> source_id
        # player1Name/player2Name with player1Piece (1=black, 2=white) -> player_black/player_white
        # gameFullName -> tournament
        # battleResultComment -> result
        # gameKifuSgf -> sgf

        battle_no = str(raw.get("battleNo", ""))

        # Use detail data if available
        if detail:
            raw = {**raw, **detail}

        # Parse date
        date_str = raw.get("battleDate") or raw.get("createTime") or raw.get("gameDate")
        if date_str:
            try:
                if "T" in str(date_str):
                    match_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                else:
                    match_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            except ValueError:
                match_date = datetime.now()
        else:
            match_date = datetime.now()

        # Games from weiqi.org are always finished (they provide historical kifu)
        status = MatchStatus.FINISHED

        # Parse SGF if available
        sgf = raw.get("gameKifuSgf") or raw.get("sgf")
        moves = []
        if sgf:
            moves = self._parse_sgf_moves(sgf)

        # Determine result
        result = raw.get("battleResultComment") or raw.get("result")
        if not result:
            # Try to parse from SGF
            if sgf and "RE[" in sgf:
                import re
                re_match = re.search(r"RE\[([^\]]+)\]", sgf)
                if re_match:
                    result = re_match.group(1)

        # Determine black/white players from piece field
        # player1Piece: 1=black, 2=white
        player1_name = raw.get("player1Name", "")
        player2_name = raw.get("player2Name", "")
        player1_piece = raw.get("player1Piece", 1)

        if player1_piece == 1:
            player_black = player1_name or "Unknown"
            player_white = player2_name or "Unknown"
        else:
            player_black = player2_name or "Unknown"
            player_white = player1_name or "Unknown"

        # Fallback to explicit black/white fields if available
        if raw.get("blackName"):
            player_black = raw.get("blackName")
        if raw.get("whiteName"):
            player_white = raw.get("whiteName")

        return LiveMatch(
            id=f"weiqi_org_{battle_no}",
            source=MatchSource.WEIQI_ORG,
            source_id=battle_no,
            tournament=raw.get("gameFullName") or raw.get("gameName") or "Unknown Tournament",
            round_name=raw.get("roundName") or raw.get("round") or raw.get("gameNo"),
            date=match_date,
            player_black=player_black,
            player_white=player_white,
            black_rank=raw.get("blackLevel") or raw.get("blackRank"),
            white_rank=raw.get("whiteLevel") or raw.get("whiteRank"),
            status=status,
            result=result,
            move_count=len(moves),
            sgf=sgf,
            moves=moves,
            last_updated=datetime.now(),
        )

    def _parse_sgf_moves(self, sgf: str) -> list[str]:
        """Parse moves from SGF content.

        Args:
            sgf: SGF content string

        Returns:
            List of moves in display format (e.g., ["Q16", "D4", ...])
        """
        if not sgf:
            return []

        import re
        moves = []

        # Extract moves: ;B[xx] or ;W[xx]
        pattern = r";([BW])\[([a-s]{2})\]"
        matches = re.findall(pattern, sgf.lower())

        for _, coord in matches:
            if coord and len(coord) == 2:
                moves.append(self._sgf_to_display(coord))

        return moves

    def _sgf_to_display(self, sgf_coord: str) -> str:
        """Convert SGF coordinate to display format.

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

    async def search_recent_pro_games(self, days: int = 7, page_size: int = 50) -> list[LiveMatch]:
        """Search for recent professional games.

        This is a convenience method that fetches recent games and parses them.

        Args:
            days: Number of days to look back
            page_size: Max number of games to retrieve

        Returns:
            List of LiveMatch objects
        """
        raw_list = await self.get_battle_list(page_num=1, page_size=page_size, game_kifu=1)

        matches = []
        for raw in raw_list:
            try:
                # Optionally fetch detail for SGF
                battle_no = raw.get("battleNo")
                detail = None
                if battle_no and not raw.get("gameKifuSgf"):
                    detail = await self.get_battle_detail(str(battle_no))

                match = self.parse_match(raw, detail)
                matches.append(match)
            except Exception as e:
                logger.warning(f"Failed to parse match: {e}")
                continue

        return matches
