from typing import Any
from fastapi import APIRouter, Depends, Request, HTTPException
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User

router = APIRouter()

@router.post("/analyze")
async def analyze(request: Request, payload: dict, current_user: User = Depends(get_current_user)) -> Any:
    router_instance = getattr(request.app.state, "router", None)
    if not router_instance:
        raise HTTPException(status_code=503, detail="Routing engine not initialized")
    
    try:
        result = await router_instance.route(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
