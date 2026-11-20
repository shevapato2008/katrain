"""User consent to generate selected TEST media, independent of human review."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select, text

from katrain.web.tutorials.manual_review import (
    _registered_source_identity,
    board_approval,
    board_content_sha256,
    board_problem,
)
from katrain.web.tutorials.media_timing import digest

COHORT_ID = "ogs-book-sources-20261113-user-generation-20261114"
RECORD_KEY = "media_generation_authorization"
USER_AUTHORIZATION = "我不需要人工确认了，我看了大部分需要人工确认的你做的都没有问题，你就直接把它们都生成了吧"
COHORT = json.loads(Path(__file__).with_name("generation_cohort_20261114.json").read_text())


def is_test_database(db):
    from katrain.web.admin.settings import check_startup

    if check_startup().env != "test" or db.get_bind().dialect.name != "postgresql":
        return False
    identity = db.execute(text("SELECT current_database(), system_identifier::text FROM pg_control_system()")).one()
    return tuple(identity) == ("katrain_db", "7596941912817897507")


def require_service(request):
    from katrain.web.admin.session import bearer_token, username_from_service_assertion

    token = bearer_token(request)
    if not token or not username_from_service_assertion(token, request.app.state.admin_config):
        raise HTTPException(status_code=403, detail="Generation consent requires service authentication")


def generation_identity(figure, db):
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure

    source, book_id = _registered_source_identity(figure, db)
    versions = db.execute(
        select(TutorialSourceBook.id, TutorialSourceBook.source_json_sha256, TutorialSourceBook.assets_manifest_sha256)
        .join(TutorialSourceFigure, TutorialSourceFigure.source_book_id == TutorialSourceBook.id)
        .where(
            TutorialSourceBook.book_id == book_id,
            TutorialSourceFigure.page == figure.page,
            TutorialSourceFigure.source_pointer == source["source_pointer"],
        )
        .distinct()
        .order_by(TutorialSourceBook.id)
    ).all()
    return {
        "figure_id": figure.id,
        "book_id": book_id,
        "page": figure.page,
        "board_sha256": digest(figure.board_payload),
        "static_content_sha256": board_content_sha256(figure),
        "source_identity": source,
        "source_versions": [list(row) for row in versions],
        "applied_candidate_id": (figure.recognition_debug or {}).get("applied_candidate_id"),
    }


def _cohort_matches(figure_id, identity):
    allowed = COHORT.get(str(figure_id))
    checksum = digest(identity)
    return checksum in allowed if isinstance(allowed, list) else checksum == allowed


def make_authorization(figure, db, admin):
    problem = board_problem(figure)
    if problem:
        raise ValueError(problem)
    identity = generation_identity(figure, db)
    if not _cohort_matches(figure.id, identity):
        raise ValueError("Figure is outside the authorized cohort or its board/source version changed")
    return {
        "schema_version": 1,
        "cohort_id": COHORT_ID,
        "identity": identity,
        "authorized_by": admin["username"],
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "authorized_figure_updated_at": figure.updated_at.isoformat() if figure.updated_at else None,
        "user_authorization": USER_AUTHORIZATION,
    }


def generation_eligibility(figure, *, db):
    approval = board_approval(figure)
    if approval["approved"]:
        return {"authorized": True, "basis": "manual_board_approval", "reason": None, "record": None}
    denied = {"authorized": False, "basis": None, "reason": approval["reason"], "record": None}
    record = (figure.recognition_debug or {}).get(RECORD_KEY)
    if not isinstance(record, dict) or not is_test_database(db):
        return denied
    if (
        record.get("schema_version") != 1
        or record.get("cohort_id") != COHORT_ID
        or record.get("user_authorization") != USER_AUTHORIZATION
        or not record.get("authorized_by")
        or not record.get("authorized_at")
    ):
        return denied
    try:
        timestamp = datetime.fromisoformat(record["authorized_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or board_problem(figure):
            return denied
        identity = generation_identity(figure, db)
    except (ValueError, TypeError, AttributeError):
        return denied
    if identity != record.get("identity") or not _cohort_matches(figure.id, identity):
        return {**denied, "reason": "Generation consent expired: board/source version changed"}
    return {
        "authorized": True,
        "basis": "explicit_user_generation_consent",
        "reason": None,
        "record": copy.deepcopy(record),
    }
