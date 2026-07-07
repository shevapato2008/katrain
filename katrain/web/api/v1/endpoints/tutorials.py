"""Tutorial module API endpoints (V2 — database-backed).

Replaces the old JSON-file-based endpoints with DB queries.
"""

import logging
import mimetypes
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.core.db import get_db
from katrain.web.core.models_db import User
from katrain.web.core.storage import get_storage_backend, normalize_key
from katrain.web.core.storage.base import MEDIA_CACHE_CONTROL
from katrain.web.tutorials import db_queries
from katrain.web.tutorials.services import generate_figure_audio
from katrain.web.tutorials.models import (
    BoardPayloadUpdate,
    NarrationUpdate,
    NarrationUpdateRequest,
    TutorialBookDetailOut,
    TutorialBookOut,
    TutorialCategoryOut,
    TutorialChapterOut,
    TutorialFigureOut,
    TutorialSectionDetailOut,
    TutorialSectionOut,
)
from katrain.web.tutorials.viewport import compute_viewport

logger = logging.getLogger(__name__)
router = APIRouter()

# Asset paths are resolved via the storage backend (katrain.web.core.storage),
# which owns key normalization + path-traversal protection (normalize_key).


# ── Categories (hardcoded) ────────────────────────────────────────────────────


@router.get("/categories", response_model=List[TutorialCategoryOut])
async def get_categories(db: Session = Depends(get_db)):
    cats = [dict(c) for c in db_queries.get_categories()]
    counts = db_queries.get_book_counts_by_category(db)
    for cat in cats:
        cat["book_count"] = counts.get(cat["slug"], 0)
    return cats


# ── Books ─────────────────────────────────────────────────────────────────────


@router.get("/categories/{category}/books", response_model=List[TutorialBookOut])
async def get_books(category: str, db: Session = Depends(get_db)):
    books = db_queries.get_books_by_category(db, category)
    result = []
    for b in books:
        out = TutorialBookOut.model_validate(b)
        out.chapter_count = len(b.chapters) if b.chapters else 0
        result.append(out)
    return result


@router.get("/books/{book_id}", response_model=TutorialBookDetailOut)
async def get_book(book_id: int, db: Session = Depends(get_db)):
    book = db_queries.get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    out = TutorialBookDetailOut.model_validate(book)
    out.chapter_count = len(book.chapters)
    chapters_out = []
    for ch in book.chapters:
        ch_out = TutorialChapterOut.model_validate(ch)
        ch_out.section_count = len(ch.sections) if ch.sections else 0
        chapters_out.append(ch_out)
    out.chapters = chapters_out
    return out


# ── Chapters ──────────────────────────────────────────────────────────────────


@router.get("/books/{book_id}/chapters", response_model=List[TutorialChapterOut])
async def get_chapters(book_id: int, db: Session = Depends(get_db)):
    chapters = db_queries.get_chapters_by_book(db, book_id)
    result = []
    for ch in chapters:
        out = TutorialChapterOut.model_validate(ch)
        out.section_count = len(ch.sections) if ch.sections else 0
        result.append(out)
    return result


# ── Sections ──────────────────────────────────────────────────────────────────


@router.get("/chapters/{chapter_id}/sections", response_model=List[TutorialSectionOut])
async def get_sections(chapter_id: int, db: Session = Depends(get_db)):
    sections = db_queries.get_sections_by_chapter(db, chapter_id)
    # Resolve book slug once for section video file checks
    book_slug = None
    if sections:
        chapter = sections[0].chapter
        if chapter and chapter.book:
            book_slug = chapter.book.slug
    # Resolve which sections have a video in ONE storage lookup instead of a probe
    # per section: for the remote backend that turns N blocking head_object round
    # trips (on the event loop) into a single list_keys call.
    video_keys: set[str] = set()
    if book_slug:
        video_keys = get_storage_backend().list_keys(f"tutorial_assets/{book_slug}/video/")
    result = []
    for sec in sections:
        out = TutorialSectionOut.model_validate(sec)
        out.figure_count = len(sec.figures) if sec.figures else 0
        if book_slug:
            out.has_video = f"tutorial_assets/{book_slug}/video/section_{sec.id}.mp4" in video_keys
        result.append(out)
    return result


@router.get("/sections/{section_id}", response_model=TutorialSectionDetailOut)
async def get_section(section_id: int, db: Session = Depends(get_db)):
    section = db_queries.get_section(db, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    out = TutorialSectionDetailOut.model_validate(section)
    out.figure_count = len(section.figures)
    out.figures = [TutorialFigureOut.model_validate(f) for f in section.figures]
    return out


# ── Figures ───────────────────────────────────────────────────────────────────


@router.get("/figures/{figure_id}", response_model=TutorialFigureOut)
async def get_figure(figure_id: int, db: Session = Depends(get_db)):
    figure = db_queries.get_figure(db, figure_id)
    if figure is None:
        raise HTTPException(status_code=404, detail="Figure not found")
    return TutorialFigureOut.model_validate(figure)


@router.put("/figures/{figure_id}/board", response_model=TutorialFigureOut)
async def update_figure_board(
    figure_id: int,
    update: BoardPayloadUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Update the board_payload for a figure. Computes viewport server-side.
    Uses optimistic locking via expected_updated_at to prevent silent overwrites."""
    figure = db_queries.get_figure(db, figure_id)
    if figure is None:
        raise HTTPException(status_code=404, detail="Figure not found")
    # Optimistic locking — compare as datetime objects to avoid Z vs +00:00 format mismatch
    if update.expected_updated_at and figure.updated_at:
        try:
            expected_dt = datetime.fromisoformat(update.expected_updated_at.replace("Z", "+00:00"))
            actual_dt = figure.updated_at
            if expected_dt.tzinfo is None:
                expected_dt = expected_dt.replace(tzinfo=timezone.utc)
            if actual_dt.tzinfo is None:
                actual_dt = actual_dt.replace(tzinfo=timezone.utc)
            if actual_dt != expected_dt:
                raise HTTPException(status_code=409, detail="Board was modified by another session. Reload and retry.")
        except (ValueError, AttributeError):
            raise HTTPException(status_code=409, detail="Board was modified by another session. Reload and retry.")
    payload_dict = update.board_payload.model_dump()
    viewport = compute_viewport(payload_dict)
    payload_dict["viewport"] = viewport
    figure = db_queries.update_figure_board(db, figure, payload_dict)
    db_queries.record_payload_history(
        db,
        figure.id,
        payload_dict,
        changed_by=current_user.username if current_user else "anonymous",
        change_type="edit",
    )
    db.commit()
    return TutorialFigureOut.model_validate(figure)


# ── Narration ────────────────────────────────────────────────────────────────


@router.post("/figures/{figure_id}/generate-audio", response_model=TutorialFigureOut)
async def generate_audio_for_figure(
    figure_id: int,
    request: NarrationUpdateRequest,
    db: Session = Depends(get_db),
):
    figure = db_queries.get_figure(db, figure_id)
    if figure is None:
        raise HTTPException(status_code=404, detail="Figure not found")

    updated_figure = await generate_figure_audio(db, figure, request.narration)
    return TutorialFigureOut.model_validate(updated_figure)


@router.put("/figures/{figure_id}/narration", response_model=TutorialFigureOut)
async def update_figure_narration(
    figure_id: int,
    update: NarrationUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Update the narration text and optional audio_asset for a figure."""
    figure = db_queries.get_figure(db, figure_id)
    if figure is None:
        raise HTTPException(status_code=404, detail="Figure not found")
    figure = db_queries.update_figure_narration(db, figure, update.narration, update.audio_asset)
    return TutorialFigureOut.model_validate(figure)


# ── Verify ────────────────────────────────────────────────────────────────────


@router.put("/figures/{figure_id}/verify", response_model=TutorialFigureOut)
async def verify_figure(
    figure_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Mark a figure as human-verified. The current board_payload becomes ground truth."""
    import json as _json

    figure = db_queries.get_figure(db, figure_id)
    if figure is None:
        raise HTTPException(status_code=404, detail="Figure not found")
    debug = _json.loads(_json.dumps(figure.recognition_debug or {}))
    debug["human_verified"] = True
    debug["verified_at"] = datetime.now(timezone.utc).isoformat()
    debug["verified_by"] = current_user.username if current_user else "anonymous"
    db_queries.update_figure_recognition_debug(db, figure, debug)
    if figure.board_payload:
        db_queries.record_payload_history(
            db,
            figure.id,
            figure.board_payload,
            changed_by=current_user.username if current_user else "anonymous",
            change_type="verify",
        )
        db.commit()

    # Auto-export training samples from the verified figure
    try:
        from katrain.web.tutorials.training_export import export_figure_training_samples

        count = export_figure_training_samples(db, figure)
        logging.getLogger("katrain_web").info("Exported %d training samples for figure %d", count, figure.id)
    except Exception as e:
        logging.getLogger("katrain_web").warning("Training export failed for figure %d: %s", figure.id, e)

    return TutorialFigureOut.model_validate(figure)


# ── Assets ────────────────────────────────────────────────────────────────────


@router.get("/assets/{asset_path:path}")
async def get_asset(asset_path: str, request: Request):
    """Serve a tutorial asset through the configured storage backend.

    * Remote (S3 / MinIO / OSS) backend → 302 redirect to the object's public
      URL so video bytes never traverse FastAPI (offloaded to CDN / reverse proxy).
    * Local backend → serve bytes with HTTP Range support for video seeking.
    """
    backend = get_storage_backend()
    try:
        key = normalize_key(asset_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset path")

    # Remote object store: redirect straight to the public URL. We deliberately do
    # NOT probe existence first — that would add a blocking head_object round-trip
    # on the event loop to every media request and surface transient store errors
    # as 500s. The public-read store / CDN returns 404 itself on a real miss.
    if backend.is_remote:
        return RedirectResponse(backend.public_url(key), status_code=302)

    # Local disk: serve bytes ourselves with Range support.
    if not backend.exists(key):
        raise HTTPException(status_code=404, detail="Asset not found")
    file_size = backend.size(key)
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

    # Parse a single byte range. Tolerate malformed headers (serve the full body)
    # and reject unsatisfiable ones with 416 rather than crashing or mis-serving.
    start = end = None
    range_header = request.headers.get("range")
    if range_header and range_header.startswith("bytes="):
        spec = range_header[6:].split(",", 1)[0].strip()  # first range only
        if "-" in spec:
            lo, hi = spec.split("-", 1)
            try:
                if lo == "":
                    # Suffix range: the LAST `n` bytes.
                    n = int(hi)
                    if n > 0:
                        start, end = max(0, file_size - n), file_size - 1
                else:
                    start = int(lo)
                    end = min(int(hi), file_size - 1) if hi else file_size - 1
            except ValueError:
                start = end = None  # malformed -> ignore the header, serve full body

    if start is not None:
        if start >= file_size or start > end:
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{file_size}", "Accept-Ranges": "bytes"},
            )
        length = end - start + 1
        data = backend.read_range(key, start, length)
        return Response(
            content=data,
            status_code=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": content_type,
                "Cache-Control": MEDIA_CACHE_CONTROL,
            },
        )

    return FileResponse(
        backend.fspath(key),
        headers={"Accept-Ranges": "bytes", "Cache-Control": MEDIA_CACHE_CONTROL},
    )
