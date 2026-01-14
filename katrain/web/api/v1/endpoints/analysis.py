from typing import Any
from fastapi import APIRouter, Depends, Request, HTTPException
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User, AnalyzeRequest

router = APIRouter()

@router.post("/analyze")
async def analyze(request: Request, data: AnalyzeRequest, current_user: User = Depends(get_current_user)) -> Any:
    router_instance = getattr(request.app.state, "router", None)
    if not router_instance:
        raise HTTPException(status_code=503, detail="Routing engine not initialized")
    
    manager = request.app.state.session_manager
    try:
        session = manager.get_session(data.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = await router_instance.route(data.payload)
        session.katrain.last_engine = result.get("engine")
        session.katrain.update_state() # Broadcast new state with engine info
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
