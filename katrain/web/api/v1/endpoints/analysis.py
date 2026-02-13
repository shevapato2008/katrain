import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, model_validator
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User, AnalyzeRequest

logger = logging.getLogger("katrain_web")
router = APIRouter()


def _build_katago_payload(
    *,
    moves: List[List[str]],
    initial_stones: List[List[str]],
    board_size: int,
    komi: float,
    rules: str,
    max_visits: int,
    include_ownership: bool = False,
    include_policy: bool = False,
    region: Optional[Dict[str, int]] = None,
) -> dict:
    """Build a KataGo analysis payload dict. Shared by /quick-analyze and /tsumego-solve."""
    payload: dict = {
        "rules": rules,
        "komi": komi,
        "boardXSize": board_size,
        "boardYSize": board_size,
        "analyzeTurns": [len(moves)],
        "maxVisits": max_visits,
        "includeOwnership": include_ownership,
        "includePolicy": include_policy,
        "moves": moves,
        "initialStones": initial_stones,
    }
    if region:
        payload["regionBounds"] = region
    return payload


def _get_router(request: Request):
    """Get router instance or raise 503."""
    router_instance = getattr(request.app.state, "router", None)
    if not router_instance:
        raise HTTPException(status_code=503, detail="Routing engine not initialized")
    return router_instance


@router.post("/analyze")
async def analyze(request: Request, data: AnalyzeRequest, current_user: User = Depends(get_current_user)) -> Any:
    router_instance = _get_router(request)

    manager = request.app.state.session_manager
    try:
        session = manager.get_session(data.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = await router_instance.route(data.payload)
        session.katrain.last_engine = result.get("engine")
        session.katrain.update_state()  # Broadcast new state with engine info
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


class QuickAnalyzeRequest(BaseModel):
    moves: List[List[str]]  # [["B","Q16"],["W","D4"],...]
    initial_stones: Optional[List[List[str]]] = []  # [["B","Q16"],...]
    board_size: int = 19
    komi: float = 7.5
    rules: str = "chinese"
    max_visits: int = 100


@router.post("/quick-analyze")
async def quick_analyze(request: Request, data: QuickAnalyzeRequest) -> Any:
    """Lightweight position analysis without a session — returns top moves + ownership."""
    router_instance = _get_router(request)
    payload = _build_katago_payload(
        moves=data.moves,
        initial_stones=data.initial_stones or [],
        board_size=data.board_size,
        komi=data.komi,
        rules=data.rules,
        max_visits=data.max_visits,
        include_ownership=True,
    )
    try:
        result = await router_instance.route(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


class TsumegoRegion(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class TsumegoSolveRequest(BaseModel):
    initial_stones: List[List[str]]  # [["B","Q16"],["W","R17"],...]
    moves: List[List[str]] = []
    board_size: int = 19
    komi: float = 0
    rules: str = "chinese"
    max_visits: int = 500
    player_to_move: str = "B"
    region: Optional[TsumegoRegion] = None

    @model_validator(mode="after")
    def validate_fields(self):
        if self.player_to_move not in ("B", "W"):
            raise ValueError("player_to_move must be 'B' or 'W'")
        if self.region:
            r = self.region
            bs = self.board_size
            if not (0 <= r.x1 <= r.x2 < bs and 0 <= r.y1 <= r.y2 < bs):
                raise ValueError(f"region coordinates out of bounds for board_size={bs}: {r}")
        return self


@router.post("/tsumego-solve")
async def tsumego_solve(request: Request, data: TsumegoSolveRequest) -> Any:
    """Tsumego analysis — region-restricted KataGo evaluation."""
    router_instance = _get_router(request)
    region_dict = None
    if data.region:
        region_dict = {"x1": data.region.x1, "y1": data.region.y1, "x2": data.region.x2, "y2": data.region.y2}
    payload = _build_katago_payload(
        moves=data.moves,
        initial_stones=data.initial_stones,
        board_size=data.board_size,
        komi=data.komi,
        rules=data.rules,
        max_visits=data.max_visits,
        region=region_dict,
    )
    # Dynamic timeout: ~10s per 10k visits, minimum 30s
    timeout = max(30.0, data.max_visits / 1000 * 10)
    logger.info(f"[tsumego-solve] visits={data.max_visits}, region={region_dict}, timeout={timeout}s")
    try:
        result = await router_instance.route(payload, timeout=timeout)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
