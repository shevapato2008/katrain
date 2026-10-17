"""Authenticated page workbench, immutable evidence, calibration and SGF exports."""

import copy
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import Field, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from katrain.web.admin.routers.tutorial_sources import _asset_path, _load_source
from katrain.web.admin.routers.tutorials import (
    BoardWrite,
    VerifyWrite,
    VersionedWrite,
    _audit,
    _cas_update,
    _commit,
    _load,
    _output,
    get_admin_db,
)
from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import (
    BoardPayloadHistory,
    TrainingSample,
    TutorialChapter,
    TutorialFigure,
    TutorialSection,
)
from katrain.web.tutorials.models import StrictBoardPayload, TutorialFigureAdminOut as TutorialFigureOut
from katrain.web.tutorials.manual_review import (
    board_approval,
    board_content_sha256,
    board_problem,
    make_review,
    review_validity,
)
from katrain.web.tutorials.recognition_import import content_sha256
from katrain.web.tutorials.recognition_models import TutorialRecognitionCandidate
from katrain.web.tutorials.replay import validate_replay
from katrain.web.tutorials.media_tasks import invalidate_media, media_metadata
from katrain.web.tutorials.sgf_export import diagram_extent, diagram_sgf
from katrain.web.tutorials.source_models import TutorialSourceFigure, TutorialSourcePage
from katrain.web.tutorials.viewport import compute_viewport

router = APIRouter(dependencies=[Depends(get_current_admin)])
ACCEPTED_RECOGNITION_DATASET = "ishida-full195-gpt61sol-v1"


class ApplyCandidateWrite(VersionedWrite):
    candidate_id: int = Field(gt=0)


class BoardVerifyWrite(VerifyWrite):
    confirmation_source: Literal["admin_ui", "user_confirmation"] = "admin_ui"
    confirmation_note: str | None = Field(default=None, max_length=1000)


def _review(figure):
    value = (figure.recognition_debug or {}).get("calibration_review") or {}
    return {"board": value.get("board"), "sequence": value.get("sequence")}


def _reset_reviews(debug, old, new, *, force=False):
    review = {"board": None, "sequence": None, **(debug.get("calibration_review") or {})}
    before = {key: value for key, value in (old or {}).items() if key != "replay"}
    after = {key: value for key, value in new.items() if key != "replay"}
    if force or before != after:
        review = {"board": None, "sequence": None}
        debug["human_verified"] = False
        debug.pop("verified_by", None)
        debug.pop("verified_at", None)
    elif (old or {}).get("replay") != new.get("replay"):
        review["sequence"] = None
    debug["calibration_review"] = review
    return debug


def _save_payload(
    db,
    figure,
    *,
    payload,
    expected,
    admin,
    narration_set=False,
    narration=None,
    action="tutorial.calibration",
    change_type="edit",
    candidate_id=None,
):
    payload = copy.deepcopy(payload)
    payload.setdefault("size", 19)
    original = copy.deepcopy(figure.board_payload)
    preserve_original = (
        original is not None
        and original != payload
        and db.scalar(select(BoardPayloadHistory.id).where(BoardPayloadHistory.figure_id == figure.id).limit(1)) is None
    )
    if payload.get("schema_version") != 2:
        if (figure.board_payload or {}).get("schema_version") == 2:
            raise HTTPException(
                status_code=409, detail="A legacy write cannot replace a v2 calibration. Reload in the workbench."
            )
        payload["viewport"] = compute_viewport(payload)
    debug = _reset_reviews(
        copy.deepcopy(figure.recognition_debug or {}), figure.board_payload, payload, force=candidate_id is not None
    )
    if original != payload:
        debug = invalidate_media(debug)
    if candidate_id is not None:
        debug["applied_candidate_id"] = candidate_id
    values = {
        "board_payload": payload,
        "recognition_debug": debug,
    }
    if candidate_id is not None or original != payload:
        values["board_review"] = None
    if original != payload or candidate_id is not None or (narration_set and figure.narration != narration):
        values.update(video_2d_review=None, video_3d_review=None)
        values.update(video_asset=None, video_duration_ms=None, video_size_bytes=None)
    if narration_set:
        values["narration"] = narration
        if figure.narration != narration:
            values["audio_asset"] = None
            values["recognition_debug"] = invalidate_media(debug, narration=True)
    figure = _cas_update(db, figure, expected, values)
    db.execute(delete(TrainingSample).where(TrainingSample.figure_id == figure.id))
    if preserve_original:
        db.add(
            BoardPayloadHistory(
                figure_id=figure.id, board_payload=original, changed_by="system:preserved", change_type="original"
            )
        )
    db.add(
        BoardPayloadHistory(
            figure_id=figure.id, board_payload=payload, changed_by=admin["username"], change_type=change_type
        )
    )
    _audit(db, admin, action, figure.id)
    return figure


@router.put("/figures/{figure_id}/calibration", response_model=TutorialFigureOut)
def save_calibration(
    figure_id: int, body: BoardWrite, db: Session = Depends(get_admin_db), admin: dict = Depends(get_current_admin)
):
    figure = _save_payload(
        db,
        _load(db, figure_id),
        payload=body.board_payload.model_dump(exclude_unset=True),
        expected=body.expected_updated_at,
        admin=admin,
        narration_set="narration" in body.model_fields_set,
        narration=body.narration,
    )
    _commit(db)
    return _output(figure)


def _verify(figure_id, body, db, admin, scope):
    figure = _load(db, figure_id)
    if not figure.board_payload:
        raise HTTPException(status_code=422, detail="Save a board before verification")
    if scope == "board":
        problem = board_problem(figure)
        if problem:
            raise HTTPException(status_code=422, detail=problem)
    else:
        try:
            StrictBoardPayload.model_validate(figure.board_payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Saved diagram needs calibration") from exc
        if validate_replay(figure.board_payload)["status"] != "complete":
            raise HTTPException(
                status_code=422, detail={"message": "Replay needs calibration", **validate_replay(figure.board_payload)}
            )
    debug = copy.deepcopy(figure.recognition_debug or {})
    review = _review(figure)
    review[scope] = {"verified_by": admin["username"], "verified_at": datetime.now(timezone.utc).isoformat()}
    debug["calibration_review"] = review
    if scope == "board":
        debug.update(human_verified=True, verified_by=admin["username"], verified_at=review[scope]["verified_at"])
    values = {"recognition_debug": debug}
    if scope == "board":
        values["board_review"] = make_review(
            admin,
            board_content_sha256(figure),
            confirmation_source=getattr(body, "confirmation_source", "admin_ui"),
            confirmation_note=getattr(body, "confirmation_note", None),
        )
    figure = _cas_update(db, figure, body.expected_updated_at, values)
    db.add(
        BoardPayloadHistory(
            figure_id=figure.id,
            board_payload=figure.board_payload,
            changed_by=admin["username"],
            change_type=f"verify_{scope}",
        )
    )
    _audit(db, admin, f"tutorial.verify_{scope}", figure.id)
    _commit(db)
    return _output(figure)


@router.put("/figures/{figure_id}/verify-board", response_model=TutorialFigureOut)
def verify_board(
    figure_id: int,
    body: BoardVerifyWrite,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    return _verify(figure_id, body, db, admin, "board")


@router.put("/figures/{figure_id}/verify-sequence", response_model=TutorialFigureOut)
def verify_sequence(
    figure_id: int, body: VerifyWrite, db: Session = Depends(get_admin_db), admin: dict = Depends(get_current_admin)
):
    return _verify(figure_id, body, db, admin, "sequence")


@router.post("/figures/{figure_id}/apply-candidate", response_model=TutorialFigureOut)
def apply_candidate(
    figure_id: int,
    body: ApplyCandidateWrite,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    figure = _load(db, figure_id)
    candidate = db.get(TutorialRecognitionCandidate, body.candidate_id)
    if candidate is None or candidate.figure_id != figure_id:
        raise HTTPException(status_code=404, detail="Recognition candidate not found for this figure")
    try:
        StrictBoardPayload.model_validate(candidate.board_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Recognition candidate needs schema calibration") from exc
    figure = _save_payload(
        db,
        figure,
        payload=candidate.board_payload,
        expected=body.expected_updated_at,
        admin=admin,
        action="tutorial.apply_candidate",
        change_type="candidate",
        candidate_id=candidate.id,
    )
    _commit(db)
    return _output(figure)


@router.get("/figures/{figure_id}/history")
def get_history(figure_id: int, db: Session = Depends(get_admin_db)):
    _load(db, figure_id)
    rows = db.scalars(
        select(BoardPayloadHistory).where(BoardPayloadHistory.figure_id == figure_id).order_by(BoardPayloadHistory.id)
    ).all()
    return {
        "figure_id": figure_id,
        "history": [
            {
                "id": row.id,
                "board_payload": row.board_payload,
                "changed_by": row.changed_by,
                "change_type": row.change_type,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


def _candidate(candidate):
    return {
        key: getattr(candidate, key)
        for key in (
            "id",
            "dataset",
            "recognition_id",
            "page",
            "board_payload",
            "raw_result",
            "source_content_sha256",
            "source_pointer",
            "source_figure_id",
            "created_at",
        )
    }


def _reference(reference):
    return {
        key: getattr(reference, key)
        for key in ("id", "source_figure_id", "source_pointer", "page", "figure_id", "source_metadata", "match_reason")
    }


def _flag(value, keys):
    if isinstance(value, dict):
        return any(
            (key in keys and bool(item)) or _flag(item, keys) for key, item in value.items() if key != "workbench_media"
        )
    if isinstance(value, list):
        return any(_flag(item, keys) for item in value)
    return False


def _entry(figure, candidates, references):
    current = figure.board_payload
    review = _review(figure)
    board_review_status = "unreviewed"
    if current is not None:
        if board_approval(figure)["approved"]:
            board_review_status = "verified"

    chosen = current if current is not None else (candidates[-1].board_payload if candidates else None)
    evidence = [candidate.raw_result for candidate in candidates]
    inference = _flag(
        [evidence, figure.recognition_debug or {}], {"inference", "inferences", "inferred", "inference_notes"}
    )
    uncertainty = bool((chosen or {}).get("unknown_stones")) or _flag(
        [evidence, figure.recognition_debug or {}],
        {"uncertainty", "uncertainties", "doubts", "uncertain", "origin_uncertain", "issues"},
    )
    return {
        "figure": _output(figure),
        "current": current,
        "media": media_metadata(figure),
        "candidates": [_candidate(candidate) for candidate in candidates],
        "source_references": [_reference(reference) for reference in references],
        "review": review,
        "review_validity": review_validity(figure),
        "board_review_status": board_review_status,
        "replay": validate_replay(chosen or {}),
        "inference": inference,
        "uncertainty": uncertainty,
    }


def _matches(entry, filter):
    return {
        "all": True,
        "uncalibrated": entry["board_review_status"] == "unreviewed",
        "inference": entry["inference"],
        "uncertainty": entry["uncertainty"],
        "sequence_pending": entry["replay"]["status"] != "complete",
    }[filter]


def _book_entries(db, book_id, source):
    figures = db.scalars(
        select(TutorialFigure)
        .join(TutorialSection)
        .join(TutorialChapter)
        .where(TutorialChapter.book_id == book_id)
        .order_by(TutorialFigure.page, TutorialFigure.order, TutorialFigure.id)
    ).all()
    candidates = (
        db.scalars(
            select(TutorialRecognitionCandidate)
            .where(TutorialRecognitionCandidate.source_book_id == source.id)
            .order_by(TutorialRecognitionCandidate.id)
        ).all()
        if source
        else []
    )
    references = (
        db.scalars(
            select(TutorialSourceFigure)
            .where(TutorialSourceFigure.source_book_id == source.id)
            .order_by(TutorialSourceFigure.id)
        ).all()
        if source
        else []
    )
    by_figure, refs = {}, {}
    for candidate in candidates:
        by_figure.setdefault(candidate.figure_id, []).append(candidate)
    by_reference = {reference.id: reference for reference in references}
    for reference in references:
        refs.setdefault(reference.figure_id, []).append(reference)
    for candidate in candidates:
        reference = by_reference.get(candidate.source_figure_id)
        if reference is not None and reference not in refs.get(candidate.figure_id, []):
            refs.setdefault(candidate.figure_id, []).append(reference)
    return [
        (figure, _entry(figure, by_figure.get(figure.id, []), refs.get(figure.id, []))) for figure in figures
    ], references


def _select_book_collection(entries):
    """Use the accepted physical targets without changing or identifying legacy rows."""
    accepted_ids = {
        figure.id
        for figure, entry in entries
        if any(candidate["dataset"] == ACCEPTED_RECOGNITION_DATASET for candidate in entry["candidates"])
    }
    selected, legacy_unlinked = [], []
    for figure, entry in entries:
        legacy = bool(accepted_ids) and figure.id not in accepted_ids
        entry["scope_status"] = "legacy_unlinked" if legacy else "recognized_physical" if accepted_ids else "all"
        entry["scope_label"] = "旧数据未关联" if legacy else "已接受的识别集合" if accepted_ids else "全部图记录"
        (legacy_unlinked if legacy else selected).append((figure, entry))
    scope = {
        "dataset": ACCEPTED_RECOGNITION_DATASET if accepted_ids else None,
        "physical_figure_count": len(selected),
        "legacy_unlinked_count": len(legacy_unlinked),
        "legacy_unlinked_label": "旧数据未关联",
    }
    return selected, legacy_unlinked, scope


@router.get("/books/{book_id}/workbench")
def get_workbench(
    book_id: int,
    page: int = Query(ge=1),
    filter: Literal["all", "uncalibrated", "inference", "uncertainty", "sequence_pending", "legacy_unlinked"] = "all",
    db: Session = Depends(get_admin_db),
):
    source = _load_source(db, book_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Book has no source pages")
    pages = db.scalars(
        select(TutorialSourcePage)
        .where(TutorialSourcePage.source_book_id == source.id)
        .order_by(TutorialSourcePage.page)
    ).all()
    selected = next((item for item in pages if item.page == page), None)
    if selected is None:
        raise HTTPException(status_code=404, detail="Source page not found")
    entries, references = _book_entries(db, book_id, source)
    selected_entries, legacy_entries, scope = _select_book_collection(entries)

    def page_entries(collection, number):
        return [
            entry
            for figure, entry in collection
            if figure.page == number or any(candidate["page"] == number for candidate in entry["candidates"])
        ]

    def filtered_page_entries(number):
        if filter == "legacy_unlinked":
            return page_entries(legacy_entries, number)
        return [entry for entry in page_entries(selected_entries, number) if _matches(entry, filter)]

    return {
        "book_id": book_id,
        "source_catalog_id": source.catalog_id,
        "filter": filter,
        "scope": scope,
        "pages": [
            {
                "page": item.page,
                "page_image_path": _asset_path(item.page_image_path),
                "has_text": bool(item.page_context_text.strip() or item.text_fragments),
                "figure_count": len(page_entries(selected_entries, item.page)),
                "filtered_figure_count": len(filtered_page_entries(item.page)),
                "legacy_unlinked_count": len(page_entries(legacy_entries, item.page)),
            }
            for item in pages
        ],
        "page": {
            "page": page,
            "page_image_path": _asset_path(selected.page_image_path),
            "page_context_text": selected.page_context_text,
            "text_fragments": selected.text_fragments,
            "source_references": [_reference(reference) for reference in references if reference.page == page],
        },
        "figures": filtered_page_entries(page),
    }


def _export_record(figure, entry):
    candidates = entry["candidates"]
    if figure.board_payload is not None:
        payload, kind, version = figure.board_payload, "current", _output(figure).updated_at
    elif candidates:
        payload, kind, version = candidates[-1]["board_payload"], "candidate", candidates[-1]["id"]
    else:
        return None
    try:
        StrictBoardPayload.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Figure {figure.id} has an invalid saved diagram") from exc
    metadata = {
        "figure_id": figure.id,
        "page": figure.page,
        "figure_label": figure.figure_label,
        "version_kind": kind,
        "version": version.isoformat() if isinstance(version, datetime) else version,
        "payload_sha256": content_sha256(payload),
        "extent": diagram_extent(payload, using_replay=entry["replay"]["status"] == "complete"),
        "source": entry["source_references"],
        "review": entry["review"],
        "inference": entry["inference"],
        "uncertainty": entry["uncertainty"],
        "evidence": [candidate["raw_result"] for candidate in candidates],
    }
    return payload, metadata


def _figure_export(db, figure_id):
    figure = _load(db, figure_id)
    book_id = db.scalar(
        select(TutorialChapter.book_id).join(TutorialSection).where(TutorialSection.id == figure.section_id)
    )
    source = _load_source(db, book_id)
    entries, _ = _book_entries(db, book_id, source)
    entry = next(entry for item, entry in entries if item.id == figure_id)
    record = _export_record(figure, entry)
    if record is None:
        raise HTTPException(status_code=422, detail="Figure has no saved diagram or recognition candidate")
    return record


@router.get("/figures/{figure_id}/export.sgf")
def export_figure(figure_id: int, db: Session = Depends(get_admin_db)):
    payload, metadata = _figure_export(db, figure_id)
    return Response(
        diagram_sgf(payload, metadata=metadata).encode("utf-8"),
        media_type="application/x-go-sgf",
        headers={"Content-Disposition": f'attachment; filename="figure-{figure_id}.sgf"'},
    )


@router.get("/books/{book_id}/export.zip")
def export_book(book_id: int, db: Session = Depends(get_admin_db)):
    source = _load_source(db, book_id)
    entries, _ = _book_entries(db, book_id, source)
    selected_entries, legacy_entries, scope = _select_book_collection(entries)
    index = {
        "book_id": book_id,
        "source_catalog_id": source.catalog_id if source else None,
        "scope": scope,
        "figures": [],
        "skipped": [],
        "legacy_unlinked": [
            {
                "figure_id": figure.id,
                "page": figure.page,
                "figure_label": figure.figure_label,
                "version": _output(figure).updated_at.isoformat() if figure.updated_at is not None else None,
                "status": "legacy_unlinked",
                "reason": "not_linked_to_accepted_recognition_dataset",
            }
            for figure, _ in legacy_entries
        ],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for figure, entry in selected_entries:
            record = _export_record(figure, entry)
            if record is None:
                index["skipped"].append({"figure_id": figure.id, "reason": "no_saved_diagram_or_candidate"})
                continue
            payload, metadata = record
            basename = f"p{figure.page:03d}-figure-{figure.id}"
            sgf_file, json_file = f"{basename}.sgf", f"{basename}.json"
            archive.writestr(sgf_file, diagram_sgf(payload, metadata=metadata))
            archive.writestr(
                json_file,
                json.dumps(
                    {**metadata, "board_payload": payload, "candidates": entry["candidates"]},
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ),
            )
            index["figures"].append({**metadata, "sgf_file": sgf_file, "json_file": json_file})
        if not index["figures"]:
            raise HTTPException(status_code=422, detail="Book has no saved diagrams or recognition candidates")
        archive.writestr("index.json", json.dumps(index, ensure_ascii=False, sort_keys=True, default=str))
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="book-{book_id}-diagrams.zip"'},
    )
