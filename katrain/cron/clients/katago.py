"""KataGo HTTP client for batch analysis (port 8002)."""

import logging
import math
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
        initial_stones: list[list[str]] | None = None,
        initial_player: str = "B",
        extra_override: dict | None = None,
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
            "initialStones": initial_stones or [],
            "initialPlayer": initial_player,
            "moves": moves,
            "analyzeTurns": analyze_turns,
            "maxVisits": max_visits,
            "includeOwnership": include_ownership,
            "includePolicy": include_policy,
            # 调用方塞进来的键**覆盖**默认值：默认这一层只有 reportAnalysisWinratesAs，
            # 谁想改它得是明确写出来的那个人。
            "overrideSettings": {
                "reportAnalysisWinratesAs": "BLACK",
                **(extra_override or {}),
            },
            "priority": priority,
        }

        url = f"{self.base_url}{self.analyze_path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if config.KATAGO_EXPECTED_MODEL_SHA256:
                self.validate_result(
                    result, request_id, analyze_turns[-1], board_size, config.KATAGO_EXPECTED_MODEL_SHA256
                )
            return result

    @staticmethod
    def validate_result(
        result: dict, request_id: str, turn: int, board_size: int, model_sha256: str, min_visits: int = 1
    ) -> None:
        """Fail closed before a model response can enter a report or live record."""
        if not isinstance(result, dict) or result.get("error"):
            raise ValueError(f"KataGo rejected analysis: {result.get('error') if isinstance(result, dict) else result}")
        if result.get("id") != request_id or result.get("turnNumber") != turn:
            raise ValueError("KataGo returned a different request or turn")
        if result.get("isDuringSearch") is not False:
            raise ValueError("KataGo did not return a final result")
        wrapper = result.get("_wrapper")
        if not isinstance(wrapper, dict) or wrapper.get("model_sha256") != model_sha256:
            raise ValueError("KataGo model SHA does not match the configured model")
        if wrapper.get("model_sha256_verified") is not True or not wrapper.get("selected_model"):
            raise ValueError("KataGo model identity is unverified")
        root = result.get("rootInfo")
        if not isinstance(root, dict) or not isinstance(root.get("visits"), int) or root["visits"] < min_visits:
            raise ValueError("KataGo root visits are below the required depth")
        for field in ("winrate", "scoreLead"):
            value = root.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"KataGo root {field} is invalid")
        move_infos = result.get("moveInfos")
        if not isinstance(move_infos, list) or not move_infos:
            raise ValueError("KataGo returned no candidate moves")
        for move in move_infos:
            if not isinstance(move, dict) or not isinstance(move.get("move"), str):
                raise ValueError("KataGo candidate move is invalid")
            if not isinstance(move.get("visits"), int) or move["visits"] < 0:
                raise ValueError("KataGo candidate visits are invalid")
            for field in ("winrate", "scoreLead", "prior"):
                value = move.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"KataGo candidate {field} is invalid")
        ownership = result.get("ownership")
        if not isinstance(ownership, list) or len(ownership) != board_size * board_size:
            raise ValueError("KataGo ownership has the wrong board size")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in ownership):
            raise ValueError("KataGo ownership contains invalid values")

    async def health_check(self) -> bool:
        """Return True only when the configured default model is ready."""
        url = f"{self.base_url}{self.health_path}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return False
                if not config.KATAGO_EXPECTED_MODEL_SHA256:
                    return True
                health = resp.json()
                name = health.get("default_model")
                model = health.get("models", {}).get(name, {})
                return (
                    health.get("ready") is True
                    and model.get("running") is True
                    and model.get("model_sha256") == config.KATAGO_EXPECTED_MODEL_SHA256
                    and model.get("model_sha256_verified") is True
                )
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
            top_moves.append(
                {
                    "move": mi.get("move", ""),
                    "visits": mi.get("visits", 0),
                    "winrate": mi.get("winrate", 0.5),
                    "score_lead": mi.get("scoreLead", 0.0),
                    "prior": mi.get("prior", 0.0),
                    "pv": mi.get("pv", []),
                    "psv": mi.get("playSelectionValue", 0.0),
                }
            )

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
