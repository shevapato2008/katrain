"""Geometry lock endpoint — empty-board zero-touch calibration (plan §3.3).

POST /geometry/lock: (optionally) blackout the LED, grab an empty-board burst,
run the ported autocal pipeline, self-check the board is empty, and persist the
lock (npz + sidecar). Depends on CaptureService (P3); LED blackout depends on
P2 and degrades gracefully if the LED service isn't running.
"""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()
log = logging.getLogger("katrain_web")

DEFAULT_GEOMETRY_PATH = Path("~/.katrain/geometry_lock.npz").expanduser()


class GeometryCalibrateRequest(BaseModel):
    trigger: str = "manual"
    empty_confirmed: bool = False


def _get_capture(request: Request):
    cap = getattr(request.app.state, "capture", None)
    if cap is None:
        raise HTTPException(status_code=404, detail="Capture service not enabled")
    return cap


def _geometry_snapshot(request: Request):
    calibration = getattr(request.app.state, "geometry_calibration", None)
    if calibration is not None:
        calibration_status = calibration.status()
        return (
            getattr(calibration, "current_lock", None),
            calibration_status.get("phase", "required"),
            int(calibration_status.get("geometry_revision", 0)),
        )
    lock = getattr(request.app.state, "geometry", None)
    return lock, "ready" if lock is not None else "required", 0


def _encode_warped_frame(frame, lock) -> bytes:
    import cv2

    from katrain.vision.config import DEFAULT_MARGIN_CELLS
    from katrain.vision.warp import warp_with_margin

    # Match the recognition path (worker_inprocess uses warp_with_margin too): warp WITH a 1-cell
    # board margin so the 俯视矫正 preview shows wood around the grid — not flush to the outermost
    # lines — and looks identical to what the detector actually sees. The overlay insets to match
    # via layout.warped_margin_cells (see geometry_layout / buildWarpedGeometryModel).
    warped = warp_with_margin(frame, lock.M, int(lock.out_size), margin_cells=DEFAULT_MARGIN_CELLS)
    ok, jpeg = cv2.imencode(".jpg", warped, [cv2.IMWRITE_JPEG_QUALITY, 65])
    if not ok:
        raise RuntimeError("failed to encode warped geometry frame")
    return jpeg.tobytes()


def _mjpeg_part(payload: bytes) -> bytes:
    return (
        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
        + str(len(payload)).encode()
        + b"\r\n\r\n"
        + payload
        + b"\r\n"
    )


@router.post("/calibrate", status_code=status.HTTP_202_ACCEPTED)
async def geometry_calibrate(request: Request, body: GeometryCalibrateRequest):
    calibration = getattr(request.app.state, "geometry_calibration", None)
    if calibration is None:
        raise HTTPException(status_code=404, detail="LED geometry calibration not enabled")
    try:
        calibration.start(trigger=body.trigger, empty_confirmed=body.empty_confirmed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from katrain.web.core.geometry_calibration_service import CalibrationBusy

        if isinstance(exc, CalibrationBusy):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise
    return calibration.status()


@router.post("/cancel")
async def geometry_cancel(request: Request):
    calibration = getattr(request.app.state, "geometry_calibration", None)
    if calibration is None:
        raise HTTPException(status_code=404, detail="LED geometry calibration not enabled")
    calibration.cancel()
    return calibration.status()


@router.post("/confirm-existing")
async def geometry_confirm_existing(request: Request):
    calibration = getattr(request.app.state, "geometry_calibration", None)
    if calibration is None:
        raise HTTPException(status_code=404, detail="LED geometry calibration not enabled")
    try:
        return calibration.confirm_existing()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/stream")
async def geometry_stream(request: Request):
    capture = _get_capture(request)

    async def generate():
        import cv2

        while True:
            frame = capture.read_frame()
            if frame is not None:
                ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                if ok:
                    yield _mjpeg_part(jpeg.tobytes())
            await asyncio.sleep(0.2)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")


@router.get("/layout")
async def geometry_layout(request: Request):
    capture = _get_capture(request)
    lock, phase, revision = _geometry_snapshot(request)
    if lock is None:
        raise HTTPException(status_code=409, detail="geometry_not_available")
    frame = capture.read_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="camera_frame_not_available")
    from katrain.vision.config import DEFAULT_MARGIN_CELLS

    height, width = frame.shape[:2]
    corner_specs = (
        (0, 0, "左上"),
        (0, 18, "右上"),
        (18, 18, "右下"),
        (18, 0, "左下"),
    )
    corners = [
        {
            "row": row,
            "col": col,
            "label": label,
            "x": float(point[0]),
            "y": float(point[1]),
        }
        for (row, col, label), point in zip(corner_specs, lock.corners)
    ]
    return {
        "revision": revision,
        "phase": phase,
        "stale": phase != "ready",
        "frame": {"width": int(width), "height": int(height)},
        "out_size": int(lock.out_size),
        # Margin (in grid cells) the warped-stream is rendered with, so the client overlay can
        # inset the grid to match the wood border. Mirrors DEFAULT_MARGIN_CELLS in _encode_warped_frame.
        "warped_margin_cells": float(DEFAULT_MARGIN_CELLS),
        "corners": corners,
        "points": lock.points.astype(float).tolist(),
    }


@router.get("/warped-stream")
async def geometry_warped_stream(request: Request):
    capture = _get_capture(request)
    lock, _phase, _revision = _geometry_snapshot(request)
    if lock is None:
        raise HTTPException(status_code=409, detail="geometry_not_available")

    async def generate():
        while not await request.is_disconnected():
            frame = capture.read_frame()
            if frame is not None:
                yield _mjpeg_part(_encode_warped_frame(frame, lock))
            await asyncio.sleep(0.2)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")


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
    calibration = getattr(request.app.state, "geometry_calibration", None)
    if calibration is not None:
        try:
            calibration.start(trigger="legacy", empty_confirmed=True)
        except Exception as exc:
            from katrain.web.core.geometry_calibration_service import CalibrationBusy

            if isinstance(exc, CalibrationBusy):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise
        await asyncio.to_thread(calibration.wait, 30)
        return calibration.status()

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
    calibration = getattr(request.app.state, "geometry_calibration", None)
    if calibration is not None:
        result = calibration.status()
        capabilities = result.setdefault("capabilities", {})
        vision = getattr(request.app.state, "vision", None)
        if vision is not None:
            vision.refresh_status()
            capabilities.update(
                model_ready=bool(vision._latest_status.model_ready),
                recognition_ready=bool(vision._latest_status.recognition_ready),
            )
        else:
            capabilities.update(model_ready=False, recognition_ready=False)
        return result
    lock = getattr(request.app.state, "geometry", None)
    if lock is None:
        return {"locked": False}
    return {
        "locked": True,
        "confidence": getattr(lock, "confidence", None),
        "out_size": getattr(lock, "out_size", None),
    }
