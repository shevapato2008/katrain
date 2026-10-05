"""Reviewed generic/archive event displays for the old production ORM.

Uses SQL because that runtime has no raw-name ORM models. The overlay packages
unchanged pure validators from name_candidates; it does not replace the models.
"""

import json

from sqlalchemy import and_, bindparam, or_, text

from katrain.web.core.models_db import KifuAlbum
from katrain.web.kifu.name_candidates import (
    ARCHIVE_DESCRIPTION_CATEGORY,
    ARCHIVE_DESCRIPTION_VERSION,
    CandidateError,
    _CLASSIFICATION_TEMPLATES_V2,
    _check_signature,
    _time,
    classification_template_sha256,
    validate_archive_description_candidate,
    validate_archive_description_scope,
)

_RAWS = ("段位赛", "个人赛", "Hoensha game")
_NO_SELECTION = text("NOT EXISTS (SELECT 1 FROM kifu_album_event_selections AS s WHERE s.album_id = kifu_albums.id)")


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _eligible(row):
    """Use the same signature, exact template and archive proof as strict reads."""
    try:
        payload = _json(row["research_payload"])
        candidate = payload["candidate"]
        _check_signature(candidate)
        owner = candidate["owner"]
        if (
            candidate["review_status"] != "approved"
            or owner.get("kind") != "raw_event"
            or not (owner.get("id") == row["raw_event_id"] or isinstance(owner.get("ref"), str))
        ):
            return False, None
        if (
            any(
                candidate.get(key) != row[key]
                for key in (
                    "lang",
                    "display_name",
                    "decision_kind",
                    "generation_rule_version",
                    "producer_id",
                    "producer_model",
                    "reviewer_id",
                    "reviewer_model",
                )
            )
            or candidate.get("raw_value") != row["raw_value"]
        ):
            return False, None
        if payload.get("research") is not None:
            return False, None
        if row["decision_kind"] == "generic":
            key = {"段位赛": "rank_event", "个人赛": "individual_event"}.get(row["raw_value"])
            template = candidate["template_review"]
            if (
                key is None
                or row["category"] != "generic_event_description"
                or row["generation_rule_version"] != "classification-v2"
                or row["display_name"] != _CLASSIFICATION_TEMPLATES_V2[row["lang"]][key]
                or template.get("version") != "classification-v2"
                or template.get("lang") != row["lang"]
                or template.get("sha256") != classification_template_sha256(row["lang"], "classification-v2")
                or template.get("reviewer_id") != candidate["reviewer_id"]
                or template.get("reviewer_model") != candidate["reviewer_model"]
                or not template.get("conclusion")
                or not _time(template.get("reviewed_at"))
                or _time(template["reviewed_at"]) > _time(candidate["reviewed_at"])
            ):
                return False, None
            return True, None
        if row["decision_kind"] == "archive_description":
            scope = payload["archive_description"]
            validate_archive_description_scope(scope)
            validate_archive_description_candidate(candidate, scope)
            if (
                row["category"] != ARCHIVE_DESCRIPTION_CATEGORY
                or row["parser_version"] != ARCHIVE_DESCRIPTION_VERSION
                or _json(row["review_metadata"]) != scope["declaration"]["category_review"]
            ):
                return False, None
            return True, set(scope["declaration"]["occurrence_album_ids"])
    except (CandidateError, KeyError, TypeError, AttributeError, ValueError):
        pass
    return False, None


def _approved_rows(db, *, values=None, lang=None, display=None):
    if values is not None and not set(values).intersection(_RAWS):
        return []
    conditions = ["r.raw_value IN :raws"]
    params = {"raws": tuple(set(values).intersection(_RAWS)) if values is not None else _RAWS}
    if lang is not None:
        conditions.append("n.lang = :lang")
        params["lang"] = lang
    if display is not None:
        conditions.append("(n.display_name = :display OR lower(n.display_name) = lower(:display))")
        params["display"] = display
    query = text(
        """
        SELECT n.raw_event_id, n.lang, n.display_name, n.decision_kind, n.generation_rule_version,
               r.raw_value, r.category, r.parser_version, r.review_metadata,
               e.research_payload, e.producer_id, e.producer_model, e.reviewer_id, e.reviewer_model
        FROM kifu_raw_event_names AS n
        JOIN kifu_raw_event_values AS r ON r.id = n.raw_event_id
        JOIN kifu_name_research_evidence AS e ON e.id = n.evidence_id
        WHERE r.review_status = 'approved' AND n.status = 'verified'
          AND e.review_status = 'approved' AND n.raw_event_id = e.raw_event_id
          AND n.lang = e.lang AND n.display_name = e.candidate_name
          AND n.revision = e.revision AND n.decision_kind = e.decision_kind
          AND n.generation_rule_version = e.generation_rule_version
          AND n.decision_kind IN ('generic', 'archive_description')
          AND e.producer_model IS NOT NULL AND e.reviewer_model IS NOT NULL
          AND e.reviewer_id IS NOT NULL AND e.reviewed_at IS NOT NULL
          AND e.reviewer_id <> e.producer_id AND """
        + " AND ".join(conditions)
    ).bindparams(bindparam("raws", expanding=True))
    result = []
    for row in db.execute(query, params).mappings():
        eligible, ids = _eligible(row)
        if eligible:
            result.append((row, ids))
    return result


def reviewed_raw_event_hints(db, albums, lang):
    """One bounded name read and one selected-slot exclusion per result page."""
    eligible_albums = [a for a in albums if a.event_id is None and a.event in _RAWS]
    if not eligible_albums:
        return {}
    ids = [a.id for a in eligible_albums]
    selected = set(
        db.execute(
            text("SELECT album_id FROM kifu_album_event_selections WHERE album_id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": ids},
        ).scalars()
    )
    result = {}
    for row, scope_ids in _approved_rows(db, values={a.event for a in eligible_albums}, lang=lang):
        for album in eligible_albums:
            if (
                album.id not in selected
                and album.event == row["raw_value"]
                and (scope_ids is None or album.id in scope_ids)
            ):
                result[album.id] = row["display_name"]
    return result


def reviewed_raw_event_search_clause(db, query):
    """Use complete approved names; exact raw scope is shared with display."""
    rows = _approved_rows(db, display=query)
    if len({row["raw_event_id"] for row, _ in rows}) != 1:
        return None
    clauses = []
    for row, ids in rows:
        clause = and_(KifuAlbum.event == row["raw_value"], KifuAlbum.event_id.is_(None), _NO_SELECTION)
        if ids is not None:
            clause = and_(clause, KifuAlbum.id.in_(ids))
        clauses.append(clause)
    return or_(*clauses)
