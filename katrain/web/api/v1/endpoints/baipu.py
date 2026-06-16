"""摆谱 (baipu / stone-placement guidance) HTTP endpoints.

`POST /baipu/load` is the **backend-authoritative** per-step truth source
(decision ②): it replays an SGF with the existing KaTrain engine and emits
per-step canonical-coordinate truth. The heavy lifting lives in
`katrain.core.baipu` (pure, CI-testable); this module is the thin HTTP layer.

P4's `/baipu/capture` endpoint is added later in the same router.
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from katrain.core.baipu import build_steps_from_sgf

router = APIRouter()


class BaipuPoint(BaseModel):
    row: int
    col: int


class BaipuStep(BaseModel):
    kind: str
    move_index: int
    property: str
    row: Optional[int] = None
    col: Optional[int] = None
    color: Optional[str] = None
    removed: List[BaipuPoint] = []
    board_hash: str


class BaipuMeta(BaseModel):
    player_black: str = ""
    player_white: str = ""
    handicap: int = 0
    komi: float = 0.0
    ruleset: str = "japanese"


class BaipuLoadRequest(BaseModel):
    sgf: Optional[str] = None
    kifu_id: Optional[int] = None


class BaipuLoadResponse(BaseModel):
    board_size: int
    steps: List[BaipuStep]
    meta: BaipuMeta


def _load_sgf_from_kifu(kifu_id: int) -> str:
    """Best-effort DB lookup of a kifu album's SGF (online/server mode only).

    Done lazily inside this branch so the primary offline path (``sgf`` text)
    never depends on the database being configured.
    """
    try:
        from katrain.web.core.db import SessionLocal
        from katrain.web.core.models_db import KifuAlbum
    except Exception as exc:  # pragma: no cover - import/config failure
        raise HTTPException(status_code=400, detail="kifu_id loading unavailable; send 'sgf' text") from exc

    db = SessionLocal()
    try:
        album = db.query(KifuAlbum).filter(KifuAlbum.id == kifu_id).first()
    finally:
        db.close()
    if album is None or not getattr(album, "sgf_content", None):
        raise HTTPException(status_code=404, detail=f"Kifu {kifu_id} not found")
    return album.sgf_content


@router.post("/load", response_model=BaipuLoadResponse)
async def baipu_load(body: BaipuLoadRequest) -> Dict[str, Any]:
    sgf = body.sgf
    if not sgf and body.kifu_id is not None:
        sgf = _load_sgf_from_kifu(body.kifu_id)
    if not sgf:
        raise HTTPException(status_code=400, detail="Provide 'sgf' text or 'kifu_id'")
    try:
        return build_steps_from_sgf(sgf)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse SGF: {exc}") from exc


class BaipuCaptureRequest(BaseModel):
    game_id: str
    move_index: int  # the step just placed; -1 = forced initial empty+LED frame
    sgf: str
    override: bool = False
    capture_condition: Optional[Dict[str, Any]] = None


@router.post("/capture")
async def baipu_capture(request: Request, body: BaipuCaptureRequest) -> Dict[str, Any]:
    capture = getattr(request.app.state, "capture", None)
    if capture is None:
        raise HTTPException(status_code=404, detail="Capture service not enabled")
    geometry = getattr(request.app.state, "geometry", None)
    if geometry is None:
        raise HTTPException(status_code=409, detail="Geometry not locked; run /geometry/lock first")
    led = getattr(request.app.state, "led", None)

    try:
        data = build_steps_from_sgf(body.sgf)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse SGF: {exc}") from exc

    from katrain.web.core.baipu_capture import run_capture, QAMismatch, LedUnavailable

    try:
        return await asyncio.to_thread(
            run_capture,
            led=led,
            capture=capture,
            geometry=geometry,
            steps=data["steps"],
            board_size=data["board_size"],
            out_dir=str(capture.out_dir),
            game_id=body.game_id,
            move_index=body.move_index,
            sgf=body.sgf,
            override=body.override,
            capture_condition=body.capture_condition,
        )
    except QAMismatch as qa:
        raise HTTPException(status_code=409, detail={"qa": "mismatch", "move_index": qa.move_index, "diffs": qa.diffs})
    except LedUnavailable as exc:
        raise HTTPException(status_code=409, detail={"error": "led_unavailable", "message": str(exc)})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
