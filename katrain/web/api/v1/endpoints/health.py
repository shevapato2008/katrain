import httpx
from fastapi import APIRouter
from katrain.web.core.config import settings

router = APIRouter()

@router.get("/health")
async def health():
    engines = {
        "local": "unknown",
        "cloud": "unknown"
    }
    
    # Check local
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            # Most KataGo HTTP APIs have a health check, but if not, we might just check connectivity
            resp = await client.get(settings.LOCAL_KATAGO_URL.rstrip("/") + "/health")
            engines["local"] = "reachable" if resp.status_code == 200 else f"error_{resp.status_code}"
    except Exception:
        engines["local"] = "unreachable"
        
    # Check cloud
    if not settings.CLOUD_KATAGO_URL:
        engines["cloud"] = "unconfigured"
    else:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.get(settings.CLOUD_KATAGO_URL.rstrip("/") + "/health")
                engines["cloud"] = "reachable" if resp.status_code == 200 else f"error_{resp.status_code}"
        except Exception:
            engines["cloud"] = "unreachable"
            
    return {"status": "ok", "engines": engines}
