"""LED control endpoints (UI-tolerant path).

These drive the LED board for on-screen navigation (摆谱 guidance). All calls use
the non-strict path: failures are reported but never block the UI. The strict
capture path (P4) talks to the LedService directly, not through REST.
"""

import logging
import time
from typing import List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()
log = logging.getLogger(__name__)


def _get_led(request: Request):
    led = getattr(request.app.state, "led", None)
    if led is None:
        raise HTTPException(status_code=404, detail="LED service not enabled")
    return led


def _touch(request: Request) -> None:
    # Mark activity so the idle-failsafe loop knows the board is in use.
    request.app.state.led_last_activity = time.monotonic()


def _tell_vision(request: Request, points: list[tuple[int, int]]) -> None:
    """Keep monitor-mode glare masking and ambient brightness in step with UI-owned lamps."""
    vision = getattr(request.app.state, "vision", None)
    if vision is not None and hasattr(vision, "set_lit_points"):
        try:
            vision.set_lit_points(points)
        except Exception:
            log.warning("Could not report lit points to vision", exc_info=True)


class PointRequest(BaseModel):
    row: int = Field(ge=0, le=18)
    col: int = Field(ge=0, le=18)
    color: str = "black"


class PointsRequest(BaseModel):
    points: List[PointRequest]


@router.post("/point")
async def led_point(request: Request, body: PointRequest):
    led = _get_led(request)
    _touch(request)
    result = led.set_points([body.model_dump()], strict=False)
    _tell_vision(request, [(body.row, body.col)])
    return result


@router.post("/points")
async def led_points(request: Request, body: PointsRequest):
    led = _get_led(request)
    _touch(request)
    result = led.set_points([p.model_dump() for p in body.points], strict=False)
    _tell_vision(request, [(p.row, p.col) for p in body.points])
    return result


@router.post("/clear")
async def led_clear(request: Request):
    led = _get_led(request)
    _touch(request)
    result = led.clear(strict=False)
    _tell_vision(request, [])
    return result


@router.get("/status")
async def led_status(request: Request):
    led = _get_led(request)
    return {"connected": led.is_connected(), "last_errors": led.last_errors}
