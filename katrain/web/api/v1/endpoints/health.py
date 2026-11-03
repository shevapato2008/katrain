import re

import httpx
from fastapi import APIRouter, Request
from katrain.core.constants import VERSION
from katrain.web.core.config import settings

router = APIRouter()


def _safe_model_id(value):
    """Accept only a bounded filename identifier, never a path or upstream metadata."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,119}", value):
        return None
    return value


def _analysis_model_id(payload):
    if not isinstance(payload, dict):
        return None
    models = payload.get("models")
    alias = payload.get("default_model")
    if not isinstance(models, dict) or not isinstance(alias, str):
        return None
    model = models.get(alias)
    if (
        not isinstance(model, dict)
        or model.get("running") is not True
        or model.get("model_sha256_verified") is not True
    ):
        return None
    path = model.get("model_path")
    if not isinstance(path, str):
        return None
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    for extension in (".bin.gz", ".txt.gz", ".bin", ".txt", ".gz"):
        if name.endswith(extension):
            name = name[: -len(extension)]
            break
    return _safe_model_id(name)


async def _current_model_id():
    board = settings.KATRAIN_MODE == "board"
    if board:
        base = settings.REMOTE_API_URL.rstrip("/")
        if not base:
            return None
        if base.endswith("/api/v1"):
            base = base[: -len("/api/v1")]
        url = base + "/api/v1/health"
    else:
        url = settings.REPORT_ENGINE_HEALTH_URL
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        if board:
            return _safe_model_id(payload.get("katago_model")) if isinstance(payload, dict) else None
        return _analysis_model_id(payload)
    except Exception:
        return None


@router.get("/health")
async def health(request: Request):
    engines = {"local": "unknown", "cloud": "unknown"}

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

    # 盒子设置屏「关于」的版本号只能从这里拿(前端 package.json 是 0.0.0)。
    result = {"status": "ok", "version": VERSION, "engines": engines}
    result["katago_model"] = await _current_model_id()
    return result
