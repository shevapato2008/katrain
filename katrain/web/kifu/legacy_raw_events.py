"""Reviewed generic, archive, and literal event displays for the old ORM.

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
from katrain.web.kifu.raw_event_translation import PRIMARY_LANGUAGES, eligible_literal_raw_name

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
        if row["decision_kind"] == "translated":
            approved = eligible_literal_raw_name(
                {"raw_event_id": row["raw_event_id"], "lang": row["lang"],
                 "display_name": row["display_name"], "decision_kind": row["decision_kind"],
                 "generation_rule_version": row["generation_rule_version"],
                 "status": row["name_status"], "revision": row["name_revision"]},
                {"raw_event_id": row["evidence_raw_event_id"], "lang": row["evidence_lang"],
                 "candidate_name": row["evidence_candidate_name"], "decision_kind": row["evidence_decision_kind"],
                 "generation_rule_version": row["evidence_rule_version"],
                 "review_status": row["evidence_status"], "revision": row["evidence_revision"],
                 "research_payload": payload, "producer_id": row["producer_id"],
                 "producer_model": row["producer_model"], "produced_at": row["produced_at"],
                 "reviewer_id": row["reviewer_id"], "reviewer_model": row["reviewer_model"],
                 "reviewed_at": row["reviewed_at"]},
                {"id": row["raw_event_id"], "raw_value": row["raw_value"],
                 "review_status": row["raw_owner_status"], "category": row["category"],
                 "review_metadata": _json(row["review_metadata"])},
            )
            return approved, None
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
    if values is not None and not values:
        return []
    conditions = []
    params = {}
    if values is not None:
        conditions.append("r.raw_value IN :raws")
        params["raws"] = tuple(values)
    if lang is not None:
        conditions.append("n.lang = :lang")
        params["lang"] = lang
    if display is not None:
        conditions.append("(n.display_name = :display OR lower(n.display_name) = lower(:display))")
        params["display"] = display
    query = text(
        """
        SELECT n.raw_event_id, n.lang, n.display_name, n.decision_kind, n.generation_rule_version,
               n.status AS name_status, n.revision AS name_revision,
               r.raw_value, r.category, r.parser_version, r.review_metadata,
               r.review_status AS raw_owner_status,
               e.raw_event_id AS evidence_raw_event_id, e.lang AS evidence_lang,
               e.candidate_name AS evidence_candidate_name, e.decision_kind AS evidence_decision_kind,
               e.generation_rule_version AS evidence_rule_version,
               e.review_status AS evidence_status, e.revision AS evidence_revision,
               e.research_payload, e.producer_id, e.producer_model, e.produced_at,
               e.reviewer_id, e.reviewer_model, e.reviewed_at
        FROM kifu_raw_event_names AS n
        JOIN kifu_raw_event_values AS r ON r.id = n.raw_event_id
        JOIN kifu_name_research_evidence AS e ON e.id = n.evidence_id
        WHERE r.review_status = 'approved' AND n.status = 'verified'
          AND e.review_status = 'approved' AND n.raw_event_id = e.raw_event_id
          AND n.lang = e.lang AND n.display_name = e.candidate_name
          AND n.revision = e.revision AND n.decision_kind = e.decision_kind
          AND n.generation_rule_version = e.generation_rule_version
          AND n.decision_kind IN ('generic', 'archive_description', 'translated')
          AND e.producer_model IS NOT NULL AND e.reviewer_model IS NOT NULL
          AND e.reviewer_id IS NOT NULL AND e.reviewed_at IS NOT NULL
          AND e.reviewer_id <> e.producer_id """
        + (" AND " + " AND ".join(conditions) if conditions else "")
    )
    if values is not None:
        query = query.bindparams(bindparam("raws", expanding=True))
    result = []
    for row in db.execute(query, params).mappings():
        eligible, ids = _eligible(row)
        if eligible:
            result.append((row, ids))
    return result


def reviewed_raw_event_hints(db, albums, lang):
    """One bounded name read and one selected-slot exclusion per result page."""
    eligible_albums = [a for a in albums if a.event_id is None and a.event
                       and a.duplicate_of_id is None and a.list_hidden_reason is None]
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
    for row, scope_ids in _approved_rows(db, values={a.event for a in eligible_albums},
                                         lang=lang if lang in PRIMARY_LANGUAGES else None):
        if row["lang"] != ("en" if row["decision_kind"] == "translated" and lang not in PRIMARY_LANGUAGES else lang):
            continue
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
    if not rows or (len({row["raw_event_id"] for row, _ in rows}) != 1
                    and not all(row["decision_kind"] == "translated" for row, _ in rows)):
        return None
    clauses = []
    for row, ids in rows:
        clause = and_(KifuAlbum.event == row["raw_value"], KifuAlbum.event_id.is_(None),
                      KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None), _NO_SELECTION)
        if ids is not None:
            clause = and_(clause, KifuAlbum.id.in_(ids))
        clauses.append(clause)
    return or_(*clauses)
