"""Source-station caching for tutorial *catalog* (read-only JSON) endpoints.

Adds `Cache-Control` + a weak `ETag` to `GET /api/v1/tutorials/*` JSON responses
(excludes `/assets/*`, which already carry their own long TTL + 302) and answers
`If-None-Match` with 304. Lets an edge/CDN cache the catalog so a large fleet does
not hammer the source DB. Media keeps its own immutable-leaning long TTL.
"""
import hashlib
import os

from fastapi import FastAPI, Request, Response

# Catalog changes rarely; short TTL + SWR lets edges serve stale while revalidating.
_MAX_AGE = int(os.getenv("KATRAIN_TUTORIAL_CATALOG_MAX_AGE", "300"))
CATALOG_CACHE_CONTROL = f"public, max-age={_MAX_AGE}, stale-while-revalidate=86400"


def _is_catalog(request: Request) -> bool:
    p = request.url.path
    return request.method == "GET" and p.startswith("/api/v1/tutorials/") and "/assets/" not in p


def add_catalog_cache_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _catalog_cache(request: Request, call_next):
        response = await call_next(request)
        if not (_is_catalog(request) and response.status_code == 200):
            return response
        # Buffer the (small) JSON body to compute a weak validator.
        body = b"".join([chunk async for chunk in response.body_iterator])
        etag = 'W/"' + hashlib.sha256(body).hexdigest()[:32] + '"'
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": CATALOG_CACHE_CONTROL},
            )
        headers = dict(response.headers)
        headers["ETag"] = etag
        headers["Cache-Control"] = CATALOG_CACHE_CONTROL
        headers.pop("content-length", None)  # re-sent below; let Starlette recompute
        return Response(content=body, status_code=200, headers=headers, media_type=response.media_type)
