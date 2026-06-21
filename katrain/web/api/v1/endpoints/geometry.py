"""Geometry lock endpoint — empty-board zero-touch calibration (plan §3.3).

POST /geometry/lock: (optionally) blackout the LED, grab an empty-board burst,
run the ported autocal pipeline, self-check the board is empty, and persist the
lock (npz + sidecar). Depends on CaptureService (P3); LED blackout depends on
P2 and degrades gracefully if the LED service isn't running.
"""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
log = logging.getLogger("katrain_web")

DEFAULT_GEOMETRY_PATH = Path("~/.katrain/geometry_lock.npz").expanduser()


def _get_capture(request: Request):
    cap = getattr(request.app.state, "capture", None)
    if cap is None:
        raise HTTPException(status_code=404, detail="Capture service not enabled")
    return cap


def _run_lock(capture, led_cleared: bool):
    """Blocking work: burst grab + autocal + save. Run in a worker thread."""
    from katrain.vision.geometry_lock import lock_geometry_from_frames, save_geometry_lock

    frames = capture.grab_burst(n=8)
    if not frames:
        return {"ok": False, "reason": "no_frames"}
    lock = lock_geometry_from_frames(frames)
    if lock is None:
        return {"ok": False, "reason": "coarse_detection_failed"}
    if not lock.empty_self_check_ok:
        return {
            "ok": False,
            "reason": "non_empty_baseline",
            "confidence": lock.confidence,
            "empty_self_check": {"black": lock.empty_black, "white": lock.empty_white},
        }
    if lock.confidence < 0.80:
        return {
            "ok": False,
            "reason": "low_confidence",
            "confidence": lock.confidence,
            "nmatch": lock.nmatch,
            "empty_self_check": {"black": lock.empty_black, "white": lock.empty_white},
            "led_cleared": led_cleared,
        }
    save_geometry_lock(lock, DEFAULT_GEOMETRY_PATH)
    return {
        "ok": True,
        "confidence": lock.confidence,
        "nmatch": lock.nmatch,
        "empty_self_check": {"black": lock.empty_black, "white": lock.empty_white},
        "led_cleared": led_cleared,
        "_lock": lock,
    }


@router.post("/lock")
async def geometry_lock(request: Request):
    capture = _get_capture(request)

    # Prerequisite (plan §3.3): LED off so it doesn't pollute the empty baseline.
    led = getattr(request.app.state, "led", None)
    led_cleared = False
    if led is not None:
        try:
            res = led.clear(strict=True)
            led_cleared = bool(res.get("ok"))
        except Exception as e:  # pragma: no cover - defensive
            log.warning("geometry lock: led.clear failed: %s", e)
    # If LED unavailable, degrade: the frontend asks the operator to confirm the
    # board is empty and the LED is off before calling this.

    result = await asyncio.to_thread(_run_lock, capture, led_cleared)
    lock = result.pop("_lock", None)
    if lock is not None:
        request.app.state.geometry = lock
    return result


@router.get("/status")
async def geometry_status(request: Request):
    lock = getattr(request.app.state, "geometry", None)
    if lock is None:
        return {"locked": False}
    return {
        "locked": True,
        "confidence": getattr(lock, "confidence", None),
        "out_size": getattr(lock, "out_size", None),
    }
