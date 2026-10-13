"""Board device management endpoints.

Server-side: nothing (box telemetry moved to the signed /api/v1/devices channel).
Board-side: live match proxy to remote server (when KATRAIN_MODE=board).
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse


logger = logging.getLogger("katrain_web")

router = APIRouter()


# ── Read-only proxies to the remote server (board mode only) ──
# The box has no local tutorial store; these endpoints forward reads to the cloud via RemoteAPIClient.
# (There used to be a /live/* proxy here for the kiosk live screens. The kiosk live module was removed
# on 2026-09-22 — Fan: live stays in galaxy only — and the proxy went with it on 2026-09-23.)


def _get_remote_client(request: Request):
    """Get RemoteAPIClient from app state (board mode only)."""
    client = getattr(request.app.state, "remote_client", None)
    if not client:
        raise HTTPException(status_code=503, detail="Not in board mode")
    return client


async def _proxy(call, what: str):
    """Forward a read-only upstream call.

    Upstream 4xx/5xx (e.g. 404 match/move not found) pass through verbatim;
    connection/timeout errors map to 502 so the kiosk can distinguish
    "not found" from "upstream unreachable".
    """
    try:
        return await call()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.warning(f"{what} proxy failed: {e}")
        raise HTTPException(status_code=502, detail="Remote server unavailable")


# ── Tutorial Proxy (board mode only) ──
@router.get("/tutorials/categories")
async def proxy_tutorial_categories(request: Request):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_categories(), "Tutorial categories")


@router.get("/tutorials/categories/{category}/books")
async def proxy_tutorial_books(request: Request, category: str):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_books(category), "Tutorial books")


@router.get("/tutorials/books/{book_id}")
async def proxy_tutorial_book(request: Request, book_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_book(book_id), "Tutorial book")


@router.get("/tutorials/books/{book_id}/chapters")
async def proxy_tutorial_chapters(request: Request, book_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_chapters(book_id), "Tutorial chapters")


@router.get("/tutorials/chapters/{chapter_id}/sections")
async def proxy_tutorial_sections(request: Request, chapter_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_sections(chapter_id), "Tutorial sections")


@router.get("/tutorials/sections/{section_id}")
async def proxy_tutorial_section(request: Request, section_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_section(section_id), "Tutorial section")


@router.get("/tutorials/figures/{figure_id}")
async def proxy_tutorial_figure(request: Request, figure_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_figure(figure_id), "Tutorial figure")


# Media: redirect to the remote asset gateway (which itself 302s to the public
# media domain). Bytes never traverse the board katrain; the browser follows the
# redirect chain and streams from media.<domain>.
@router.get("/tutorials/assets/{asset_path:path}")
async def proxy_tutorial_asset(request: Request, asset_path: str):
    c = _get_remote_client(request)
    return RedirectResponse(f"{c.base_url}/api/v1/tutorials/assets/{asset_path}", status_code=302)
