"""Narrow transactional candidate insertion; applying evidence is a separate action."""

import copy
import hashlib
import json

from sqlalchemy import select

from katrain.web.core.models_db import TutorialChapter, TutorialFigure, TutorialSection
from katrain.web.tutorials.recognition_models import TutorialRecognitionCandidate
from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure


def content_sha256(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def import_candidate(
    db,
    *,
    source_book_id,
    dataset,
    recognition_id,
    figure_id,
    page,
    raw_result,
    board_payload,
    source_figure_id=None,
    source_pointer=None,
):
    """Insert immutable evidence within caller's transaction. Never edits current."""
    digest = content_sha256(raw_result)
    existing = db.scalar(
        select(TutorialRecognitionCandidate).where(
            TutorialRecognitionCandidate.source_book_id == source_book_id,
            TutorialRecognitionCandidate.dataset == dataset,
            TutorialRecognitionCandidate.recognition_id == recognition_id,
        )
    )
    if existing:
        if (
            existing.source_content_sha256 != digest
            or existing.board_payload != board_payload
            or existing.figure_id != figure_id
            or existing.page != page
            or (source_figure_id is not None and existing.source_figure_id != source_figure_id)
            or (source_pointer is not None and existing.source_pointer != source_pointer)
        ):
            raise ValueError("Recognition identity already exists with different immutable content or target")
        return existing
    source = db.get(TutorialSourceBook, source_book_id)
    figure_book = db.scalar(
        select(TutorialChapter.book_id)
        .join(TutorialSection, TutorialSection.chapter_id == TutorialChapter.id)
        .join(TutorialFigure, TutorialFigure.section_id == TutorialSection.id)
        .where(TutorialFigure.id == figure_id)
    )
    if source is None or figure_book != source.book_id:
        raise ValueError("Candidate requires a real figure belonging to its source book")
    if source_figure_id is not None:
        reference = db.get(TutorialSourceFigure, source_figure_id)
        if reference is None or reference.source_book_id != source_book_id:
            raise ValueError("Candidate source reference must belong to its source book")
    candidate = TutorialRecognitionCandidate(
        source_book_id=source_book_id,
        dataset=dataset,
        recognition_id=recognition_id,
        figure_id=figure_id,
        page=page,
        source_figure_id=source_figure_id,
        source_pointer=source_pointer,
        source_content_sha256=digest,
        raw_result=copy.deepcopy(raw_result),
        board_payload=copy.deepcopy(board_payload),
    )
    db.add(candidate)
    db.flush()
    return candidate
