"""KataGo HTTP client for batch analysis (port 8002)."""

import logging
from typing import Optional

import httpx

from katrain.cron import config

logger = logging.getLogger("katrain_cron.katago")


class KataGoClient:
    """Send analysis requests to KataGo's HTTP analysis endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        analyze_path: str | None = None,
        health_path: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or config.KATAGO_URL).rstrip("/")
        self.analyze_path = analyze_path or config.KATAGO_ANALYZE_PATH
        self.health_path = health_path or config.KATAGO_HEALTH_PATH
        self.timeout = timeout or config.ANALYSIS_REQUEST_TIMEOUT

    async def analyze(
        self,
        request_id: str,
        moves: list[list[str]],
        rules: str = "chinese",
        komi: float = 7.5,
        board_size: int = 19,
        max_visits: int | None = None,
        analyze_turns: list[int] | None = None,
        include_ownership: bool = True,
        include_policy: bool = True,
        priority: int = 0,
    ) -> dict:
        """Send a single analysis request to KataGo.

        Args:
            request_id: Unique ID echoed back in response.
            moves: List of [player, GTP_coord] pairs, e.g. [["B","Q16"],["W","D4"]].
            rules: Game rules (chinese, japanese, korean, etc.).
            komi: Komi value.
            board_size: Board width/height.
            max_visits: Search depth (default from config).
            analyze_turns: Which turn(s) to analyze (default: last move).
            include_ownership: Include territory ownership map.
            include_policy: Include policy priors.
            priority: KataGo-side priority.

        Returns:
            Raw KataGo JSON response dict.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            httpx.TimeoutException: If request exceeds timeout.
        """
        if max_visits is None:
            max_visits = config.ANALYSIS_MAX_VISITS
        if analyze_turns is None:
            analyze_turns = [len(moves)]

        payload = {
            "id": request_id,
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "moves": moves,
            "analyzeTurns": analyze_turns,
            "maxVisits": max_visits,
            "includeOwnership": include_ownership,
            "includePolicy": include_policy,
            "overrideSettings": {
                "reportAnalysisWinratesAs": "BLACK",
            },
            "priority": priority,
        }

        url = f"{self.base_url}{self.analyze_path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def health_check(self) -> bool:
        """Return True if KataGo is reachable."""
        url = f"{self.base_url}{self.health_path}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def parse_result(response: dict) -> Optional[dict]:
        """Extract analysis fields from KataGo response.

        Returns None if the response contains an error.
        Returns a dict with: winrate, score_lead, top_moves, ownership.
        """
        if "error" in response:
            logger.error("KataGo analysis error: %s", response["error"])
            return None

        root = response.get("rootInfo", {})
        move_infos = response.get("moveInfos", [])

        top_moves = []
        for mi in move_infos[:10]:
            top_moves.append({
                "move": mi.get("move", ""),
                "visits": mi.get("visits", 0),
                "winrate": mi.get("winrate", 0.5),
                "score_lead": mi.get("scoreLead", 0.0),
                "prior": mi.get("prior", 0.0),
                "pv": mi.get("pv", []),
            })

        ownership_flat = response.get("ownership")
        ownership = None
        if ownership_flat and isinstance(ownership_flat, list):
            board_size = int(len(ownership_flat) ** 0.5)
            ownership = []
            for y in range(board_size):
                row = []
                for x in range(board_size):
                    idx = y * board_size + x
                    row.append(ownership_flat[idx] if idx < len(ownership_flat) else 0.0)
                ownership.append(row)

        return {
            "winrate": root.get("winrate", 0.5),
            "score_lead": root.get("scoreLead", 0.0),
            "top_moves": top_moves,
            "ownership": ownership,
        }
