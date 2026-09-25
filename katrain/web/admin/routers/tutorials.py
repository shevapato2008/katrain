"""Versioned tutorial authoring for the dedicated admin process."""

import logging
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import String, cast, delete, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import AdminAuditLog, BoardPayloadHistory, TrainingSample, TutorialFigure
from katrain.web.core.storage import get_storage_backend
from katrain.web.tutorials.models import StrictBoardPayload, TutorialFigureOut
from katrain.web.tutorials.services import _get_book_slug
from katrain.web.tutorials.viewport import compute_viewport


logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_admin)])


def get_admin_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


class VersionedWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_updated_at: str | None = Field(...)

    @field_validator("expected_updated_at")
    @classmethod
    def valid_iso_timestamp(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("expected_updated_at must be an ISO timestamp") from exc
        if parsed.tzinfo is None:
            raise ValueError("expected_updated_at must include a timezone")
        return value


class BoardWrite(VersionedWrite):
    board_payload: StrictBoardPayload
    narration: str | None = None


class NarrationWrite(VersionedWrite):
    narration: str


class AudioWrite(VersionedWrite):
    narration: str = Field(min_length=1)


class VerifyWrite(VersionedWrite):
    pass


class TrainingExportResult(BaseModel):
    status: str
    count: int
    reason: str | None = None


class VerifyResult(BaseModel):
    figure: TutorialFigureOut
    training_export: TrainingExportResult


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _output(figure: TutorialFigure) -> TutorialFigureOut:
    result = TutorialFigureOut.model_validate(figure)
    if result.updated_at is not None:
        result.updated_at = _utc(result.updated_at)
    return result


def _load(db: Session, figure_id: int) -> TutorialFigure:
    figure = db.get(TutorialFigure, figure_id)
    if figure is None:
        raise HTTPException(status_code=404, detail="Figure not found")
    return figure


def _version_filter(db: Session, figure: TutorialFigure, expected: str | None):
    current = figure.updated_at
    if db.get_bind().dialect.name == "sqlite":
        # SQLite CURRENT_TIMESTAMP writes `YYYY-MM-DD HH:MM:SS`, whereas
        # SQLAlchemy-bound datetimes include `.000000`; raw text CAS handles
        # both existing rows and new microsecond-resolution rows exactly.
        raw = db.execute(
            select(cast(TutorialFigure.updated_at, String)).where(TutorialFigure.id == figure.id)
        ).scalar_one()
        current = datetime.fromisoformat(raw) if raw is not None else None
    if expected is None:
        if current is not None:
            raise HTTPException(status_code=409, detail="Figure was modified by another session. Reload and retry.")
        return TutorialFigure.updated_at.is_(None)
    parsed = datetime.fromisoformat(expected.replace("Z", "+00:00"))
    if current is None or _utc(current) != _utc(parsed):
        raise HTTPException(status_code=409, detail="Figure was modified by another session. Reload and retry.")
    if db.get_bind().dialect.name == "sqlite":
        return cast(TutorialFigure.updated_at, String) == raw
    return TutorialFigure.updated_at == current


def _next_updated_at(current: datetime | None) -> datetime:
    now = datetime.now(timezone.utc)
    return max(now, _utc(current) + timedelta(microseconds=1)) if current is not None else now


def _cas_update(db: Session, figure: TutorialFigure, expected: str | None, values: dict) -> TutorialFigure:
    values["updated_at"] = _next_updated_at(figure.updated_at)
    changed = db.execute(
        update(TutorialFigure)
        .where(TutorialFigure.id == figure.id, _version_filter(db, figure, expected))
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise HTTPException(status_code=409, detail="Figure was modified by another session. Reload and retry.")
    db.expire_all()
    return _load(db, figure.id)


def _audit(db: Session, admin: dict, action: str, figure_id: int) -> None:
    db.add(
        AdminAuditLog(
            actor_realm="admin",
            actor_username=admin["username"],
            action=action,
            target_type="tutorial_figure",
            target_id=figure_id,
            success=True,
        )
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except OperationalError as exc:
        db.rollback()
        if "admin_audit_log" in str(exc):
            raise HTTPException(status_code=503, detail="Admin audit table unavailable") from exc
        raise
    except Exception:
        db.rollback()
        raise


@router.put("/figures/{figure_id}/board", response_model=TutorialFigureOut)
def update_board(
    figure_id: int,
    body: BoardWrite,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    figure = _load(db, figure_id)
    payload = body.board_payload.model_dump(exclude_none=True)
    payload["viewport"] = compute_viewport(payload)
    debug = dict(figure.recognition_debug or {})
    debug["human_verified"] = False
    debug.pop("verified_at", None)
    debug.pop("verified_by", None)
    # A rendered video belongs to the previous board (and its audio).
    values = {
        "board_payload": payload,
        "recognition_debug": debug,
        "video_asset": None,
        "video_duration_ms": None,
        "video_size_bytes": None,
    }
    if "narration" in body.model_fields_set:
        values["narration"] = body.narration
        if figure.narration != body.narration:
            values["audio_asset"] = None
    figure = _cas_update(db, figure, body.expected_updated_at, values)
    db.execute(delete(TrainingSample).where(TrainingSample.figure_id == figure_id))
    db.add(
        BoardPayloadHistory(
            figure_id=figure_id,
            board_payload=payload,
            changed_by=admin["username"],
            change_type="edit",
        )
    )
    _audit(db, admin, "tutorial.board", figure_id)
    _commit(db)
    db.refresh(figure)
    return _output(figure)


@router.put("/figures/{figure_id}/narration", response_model=TutorialFigureOut)
def update_narration(
    figure_id: int,
    body: NarrationWrite,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    figure = _load(db, figure_id)
    values = {"narration": body.narration}
    if figure.narration != body.narration:
        values["audio_asset"] = None
        values["video_asset"] = None
        values["video_duration_ms"] = None
        values["video_size_bytes"] = None
    figure = _cas_update(db, figure, body.expected_updated_at, values)
    _audit(db, admin, "tutorial.narration", figure_id)
    _commit(db)
    db.refresh(figure)
    return _output(figure)


async def _synthesize_audio(text: str, path: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural").save(str(path))


@router.post("/figures/{figure_id}/generate-audio", response_model=TutorialFigureOut)
async def generate_audio(
    figure_id: int,
    body: AudioWrite,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    figure = _load(db, figure_id)
    # A preflight avoids generating an object for an already stale editor.
    if body.expected_updated_at is None:
        stale = figure.updated_at is not None
    else:
        stale = figure.updated_at is None or _utc(figure.updated_at) != _utc(
            datetime.fromisoformat(body.expected_updated_at.replace("Z", "+00:00"))
        )
    if stale:
        raise HTTPException(status_code=409, detail="Figure was modified by another session. Reload and retry.")

    book_slug = _get_book_slug(db, figure)
    key = f"tutorial_assets/{book_slug}/audio/fig_{figure_id}_{uuid.uuid4().hex}.mp3"
    with tempfile.TemporaryDirectory(prefix="katrain-admin-tts-") as directory:
        path = Path(directory) / "audio.mp3"
        try:
            await _synthesize_audio(body.narration, path)
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError("TTS returned empty audio")
            with path.open("rb") as audio:
                get_storage_backend().put(key, audio, content_type="audio/mpeg")
        except Exception as exc:
            logger.warning("Admin TTS or upload failed for figure %d: %s", figure_id, exc)
            raise HTTPException(status_code=502, detail="Audio generation or upload failed") from exc

    figure = _cas_update(
        db,
        figure,
        body.expected_updated_at,
        {
            "narration": body.narration,
            "audio_asset": key,
            "video_asset": None,
            "video_duration_ms": None,
            "video_size_bytes": None,
        },
    )
    _audit(db, admin, "tutorial.generate_audio", figure_id)
    _commit(db)
    db.refresh(figure)
    return _output(figure)


def _export_training(db: Session, figure: TutorialFigure) -> TrainingExportResult:
    if not figure.board_payload:
        return TrainingExportResult(status="skipped", count=0, reason="no_board_payload")
    debug = figure.recognition_debug or {}
    if not debug.get("classification", {}).get("label_map"):
        return TrainingExportResult(status="skipped", count=0, reason="no_label_map")
    existing = db.query(TrainingSample).filter_by(figure_id=figure.id).count()
    if existing:
        return TrainingExportResult(status="skipped", count=existing, reason="already_exported")
    backend = get_storage_backend()
    if backend.is_remote:
        return TrainingExportResult(status="skipped", count=0, reason="shared_crop_unavailable")
    book_slug = _get_book_slug(db, figure)
    crop_key = f"tutorial_assets/{book_slug}/debug/{figure.figure_label}/crop.png"
    if not backend.exists(crop_key):
        return TrainingExportResult(status="skipped", count=0, reason="crop_unavailable")
    try:
        from katrain.web.tutorials.training_export import export_figure_training_samples

        with db.begin_nested():
            count = export_figure_training_samples(
                db,
                figure,
                commit=False,
                asset_base=backend.fspath("tutorial_assets").parent,
                book_slug=book_slug,
            )
    except Exception:
        logger.exception("Training export failed for figure %d", figure.id)
        return TrainingExportResult(status="failed", count=0, reason="training_export_error")
    if count == 0:
        return TrainingExportResult(status="skipped", count=0, reason="no_training_samples")
    return TrainingExportResult(status="exported", count=count)


@router.put("/figures/{figure_id}/verify", response_model=VerifyResult)
def verify_figure(
    figure_id: int,
    body: VerifyWrite,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    figure = _load(db, figure_id)
    debug = dict(figure.recognition_debug or {})
    debug.update(human_verified=True, verified_at=datetime.now(timezone.utc).isoformat(), verified_by=admin["username"])
    figure = _cas_update(db, figure, body.expected_updated_at, {"recognition_debug": debug})
    if figure.board_payload:
        db.add(
            BoardPayloadHistory(
                figure_id=figure_id,
                board_payload=figure.board_payload,
                changed_by=admin["username"],
                change_type="verify",
            )
        )
    export = _export_training(db, figure)
    _audit(db, admin, "tutorial.verify", figure_id)
    _commit(db)
    db.refresh(figure)
    return VerifyResult(figure=_output(figure), training_export=export)
