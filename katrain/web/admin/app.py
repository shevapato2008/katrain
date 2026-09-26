"""Separate admin ASGI app with no public routes or database initialization."""

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from katrain.web.admin.routers.auth import router as auth_router
from katrain.web.admin.routers.cron import router as cron_router
from katrain.web.admin.routers.tutorials import get_admin_db, router as tutorial_write_router
from katrain.web.admin.routers.vision import router as vision_router
from katrain.web.admin.settings import check_startup
from katrain.web.admin.vision_runtime import AdminVisionRuntime
from katrain.web.api.v1.endpoints.tutorials import router as tutorial_read_router
from katrain.web.core.config import settings as web_settings
from katrain.web.core.db import get_db

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static-admin"
NOT_BUILT = "Admin frontend has not been built"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; media-src 'self'; font-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


def _media_csp() -> str:
    """Allow only the configured public media origin when storage redirects."""
    if web_settings.STORAGE_BACKEND != "s3":
        return CSP
    url = web_settings.S3_ENDPOINT_URL if web_settings.S3_USE_PRESIGNED else web_settings.S3_PUBLIC_BASE_URL
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return CSP
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    origin = f"{parsed.scheme}://{host}{f':{parsed.port}' if parsed.port else ''}"
    return CSP.replace("img-src 'self' data:", f"img-src 'self' data: {origin}").replace(
        "media-src 'self'", f"media-src 'self' {origin}"
    )


def create_admin_app(session_factory=None, static_dir: Path | None = None, bind_host: str | None = None) -> FastAPI:
    config = check_startup()
    if session_factory is None:
        from katrain.web.core.db import SessionLocal

        session_factory = SessionLocal
    vision_runtime = AdminVisionRuntime(config, bind_host=bind_host)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            vision_runtime.shutdown()

    app = FastAPI(title="katrain-admin", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.admin_config = config
    app.state.session_factory = session_factory
    app.state.vision_runtime = vision_runtime
    content_security_policy = _media_csp()

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = content_security_policy
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path == "/api/admin/vision/preview":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/admin/health")
    async def health():
        return {"status": "ok", "env": config.env}

    app.include_router(auth_router)
    app.include_router(cron_router, prefix="/api/admin/cron", tags=["admin-cron"])
    app.include_router(vision_router, prefix="/api/admin/vision", tags=["admin-vision"])
    app.include_router(tutorial_write_router, prefix="/api/admin/tutorials", tags=["admin-tutorials"])
    app.include_router(tutorial_read_router, prefix="/api/v1/tutorials", tags=["tutorial-reads"])
    app.dependency_overrides[get_db] = get_admin_db

    static_root = Path(static_dir) if static_dir is not None else DEFAULT_STATIC_DIR
    index = static_root / "admin.html"
    assets = static_root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="admin-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return PlainTextResponse("Not Found", status_code=404)
        if not index.is_file():
            return PlainTextResponse(NOT_BUILT, status_code=503)
        return FileResponse(index)

    return app
