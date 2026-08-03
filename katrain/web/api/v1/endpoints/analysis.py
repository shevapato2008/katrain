from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.ranked_session_guard import (
    guard_ai_ladder_ranked_session,
    guard_user_has_no_pending_ranked_game,
    temporary_analysis_lease,
)
from katrain.web.models import User, AnalyzeRequest

router = APIRouter()


@router.post("/analyze")
async def analyze(request: Request, data: AnalyzeRequest, current_user: User = Depends(get_current_user)) -> Any:
    guard_user_has_no_pending_ranked_game(request.app, current_user, "analysis")
    manager = request.app.state.session_manager
    try:
        session = manager.get_session(data.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    guard_ai_ladder_ranked_session(session, "routed-analysis")

    router_instance = getattr(request.app.state, "router", None)
    if not router_instance:
        raise HTTPException(status_code=503, detail="Routing engine not initialized")

    with temporary_analysis_lease(request.app, current_user, data.session_id, "v1-analysis", "analysis"):
        try:
            result = await router_instance.route(data.payload)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        session.katrain.last_engine = result.get("engine")
        session.katrain.update_state()  # Broadcast new state with engine info
        return result


class QuickAnalyzeRequest(BaseModel):
    moves: List[List[str]]  # [["B","Q16"],["W","D4"],...]
    initial_stones: Optional[List[List[str]]] = []  # [["B","Q16"],...]
    board_size: int = 19
    komi: float = 7.5
    rules: str = "chinese"
    max_visits: int = 100


@router.post("/quick-analyze")
async def quick_analyze(
    request: Request, data: QuickAnalyzeRequest, current_user: User = Depends(get_current_user)
) -> Any:
    """Lightweight position analysis without a session — returns top moves + ownership."""
    guard_user_has_no_pending_ranked_game(request.app, current_user, "analysis")
    router_instance = getattr(request.app.state, "router", None)
    if not router_instance:
        raise HTTPException(status_code=503, detail="Routing engine not initialized")

    payload = {
        "rules": data.rules,
        "komi": data.komi,
        "boardXSize": data.board_size,
        "boardYSize": data.board_size,
        "analyzeTurns": [len(data.moves)],
        "maxVisits": data.max_visits,
        "includeOwnership": True,
        "includePolicy": False,
        "moves": data.moves,
        "initialStones": data.initial_stones or [],
    }

    lease_id = f"quick:{current_user.id}"
    with temporary_analysis_lease(request.app, current_user, lease_id, "quick-analysis", "analysis"):
        try:
            return await router_instance.route(payload)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
