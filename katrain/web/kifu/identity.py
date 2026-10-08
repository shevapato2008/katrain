"""Resolve multilingual kifu names without changing original SGF metadata."""

import hashlib
import os
import unicodedata
from copy import deepcopy

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuAlbumSource,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuEventSelectionBatch,
    KifuNameResearchEvidence,
    KifuNameBatch,
    KifuPlayerAlias,
    KifuPlayer,
    KifuPlayerName,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
    KifuSource,
)
from katrain.web.kifu.name_parse import parse_event, parse_player
from katrain.web.kifu.name_structure import structure_event
from katrain.web.kifu.name_raw_player_scope import prepare_raw_player_scope, raw_player_scope_slot
from katrain.web.kifu.name_evidence import EvidenceError

LANGUAGES = frozenset({"en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"})
PRIMARY_NAME_LANGUAGES = frozenset({"en", "cn", "tw", "jp", "ko"})


def name_display_language(lang: str) -> str:
    """Use English kifu metadata for UI locales outside the five name languages."""
    return lang if lang in PRIMARY_NAME_LANGUAGES else "en"
_DECISIONS = frozenset({"conventional", "generated", "generic", "hidden", "placeholder", "error", "corrected"})
_UNAVAILABLE_LABELS = {
    "en": ("Player name unverified", "Event name unverified"),
    "cn": ("棋手姓名待核实", "赛事名称待核实"),
    "tw": ("棋手姓名待核實", "賽事名稱待核實"),
    "jp": ("棋士名は未確認", "棋戦名は未確認"),
    "ko": ("기사 이름 미확인", "대회 이름 미확인"),
    "de": ("Spielername ungeprüft", "Turniername ungeprüft"),
    "es": ("Nombre del jugador sin verificar", "Nombre del torneo sin verificar"),
    "fr": ("Nom du joueur non vérifié", "Nom du tournoi non vérifié"),
    "ru": ("Имя игрока не проверено", "Название турнира не проверено"),
    "tr": ("Oyuncu adı doğrulanmadı", "Turnuva adı doğrulanmadı"),
    "ua": ("Ім’я гравця не перевірено", "Назву турніру не перевірено"),
}


def strict_unavailable_label(lang: str, kind: str) -> str:
    """A visible coverage gap, distinct from a reviewed placeholder or damaged value."""
    return _UNAVAILABLE_LABELS[lang][0 if kind == "player" else 1]


def strict_names_enabled() -> bool:
    """Activate only after the full catalog has passed coverage review."""
    return os.getenv("KIFU_STRICT_NAMES", "").lower() in {"1", "true", "yes"}


def _approved_names(db: Session, model, owner_column: str, ids: set[int] | None = None, lang: str | None = None):
    """Reject legacy verified rows and evidence for another owner or revision."""
    owner = getattr(model, owner_column)
    evidence_owner = getattr(KifuNameResearchEvidence, owner_column)
    query = (
        db.query(model)
        .join(KifuNameResearchEvidence, model.evidence_id == KifuNameResearchEvidence.id)
        .filter(
            owner == evidence_owner,
            model.lang == KifuNameResearchEvidence.lang,
            model.status == "verified",
            KifuNameResearchEvidence.review_status == "approved",
            KifuNameResearchEvidence.producer_model.isnot(None),
            KifuNameResearchEvidence.reviewer_model.isnot(None),
            KifuNameResearchEvidence.reviewer_id.isnot(None),
            KifuNameResearchEvidence.reviewed_at.isnot(None),
            KifuNameResearchEvidence.reviewer_id != KifuNameResearchEvidence.producer_id,
            model.revision == KifuNameResearchEvidence.revision,
            model.decision_kind == KifuNameResearchEvidence.decision_kind,
            model.decision_kind.in_(
                _DECISIONS | {"transliterated"}
                | ({"translated"} if model is KifuEventName else set())
                | ({"composed", "archive_description", "translated"} if model is KifuRawEventName else set())
            ),
            model.generation_rule_version == KifuNameResearchEvidence.generation_rule_version,
            model.display_name == KifuNameResearchEvidence.candidate_name,
        )
    )
    if ids is not None:
        query = query.filter(owner.in_(ids))
    if lang is not None:
        query = query.filter(model.lang == lang)
    return query


def _qualified_name_rows(db, query, model, owner_column, *entities, orthographic_batch_contexts=None):
    """Validate persisted finite generation proofs with one batch read per name query."""
    from katrain.web.kifu.name_transliteration import persisted_batch_bindings, persisted_name_eligible

    from katrain.web.kifu import name_orthographic
    from katrain.web.kifu.name_evidence import is_positive_ja_ko, persisted_positive_ja_ko_eligible
    from katrain.web.core.models_db import KifuNameChange, KifuNameSourceRegistry

    def image(row):
        return {column.name: (value.isoformat() if hasattr(value, "isoformat") else value)
                for column in row.__table__.columns for value in [getattr(row, column.name)]}

    def positive_proof(name, evidence):
        payload = evidence.research_payload
        candidate = payload.get("candidate") if isinstance(payload, dict) else None
        return (evidence.id in positive_ledger_ids or is_positive_ja_ko(candidate, payload, name.generation_rule_version)
                or evidence.generation_rule_version == "nikl-ja-ko-personal-name-v1")

    rows = query.with_entities(model, KifuNameResearchEvidence, *entities).all()
    # The creation ledger retains the original method even if every mutable
    # discriminator was removed. Bound this lookup to evidence already returned.
    evidence_ids = {evidence.id for _, evidence, *_ in rows}
    positive_ledger_ids = set()
    verified_display_ledger_ids = set()
    if evidence_ids:
        for change in db.query(KifuNameChange).filter(
            KifuNameChange.target_table == "kifu_name_research_evidence",
            KifuNameChange.target_row_id.in_(evidence_ids),
        ):
            after = change.after_image
            if isinstance(after, dict) and is_positive_ja_ko(
                payload=after.get("research_payload"), rule=after.get("generation_rule_version")
            ):
                positive_ledger_ids.add(change.target_row_id)
            if isinstance(after, dict):
                created_payload = after.get("research_payload")
                created_candidate = created_payload.get("candidate") if isinstance(created_payload, dict) else None
                created_proof = created_payload.get("primary_orthographic") if isinstance(created_payload, dict) else None
                created_anchor = created_proof.get("source_anchor") if isinstance(created_proof, dict) else None
                created_source = created_anchor.get("content") if isinstance(created_anchor, dict) else None
                if (isinstance(created_candidate, dict)
                    and created_candidate.get("reference_kind") in {"verified_chinese_display", "verified_japanese_display"}
                    or isinstance(created_source, dict)
                    and created_source.get("reference_kind") in {"verified_chinese_display", "verified_japanese_display"}):
                    verified_display_ledger_ids.add(change.target_row_id)

    def orthographic_proof(name, evidence):
        payload = evidence.research_payload
        candidate = payload.get("candidate") if isinstance(payload, dict) else None
        return (
            evidence.id in verified_display_ledger_ids
            or name.generation_rule_version == name_orthographic.VERSION
            or isinstance(payload, dict)
            and "primary_orthographic" in payload
            or isinstance(candidate, dict)
            and candidate.get("generation_rule_version") == name_orthographic.VERSION
        )

    batch_ids = set()
    for name, evidence, *_ in rows:
        if (name.decision_kind == "transliterated" or orthographic_proof(name, evidence) or positive_proof(name, evidence)) and isinstance(
            evidence.research_payload, dict
        ):
            proof = evidence.research_payload.get(
                "normative_ja_ko" if positive_proof(name, evidence)
                else "primary_orthographic" if orthographic_proof(name, evidence) else "transliteration"
            )
            if isinstance(proof, dict) and type(proof.get("batch_id")) is int:
                batch_ids.add(proof["batch_id"])
    use_contexts = orthographic_batch_contexts is not None and not (db.new or db.dirty or db.deleted)
    batch_query = db.query(KifuNameBatch).filter(KifuNameBatch.id.in_(batch_ids))
    if use_contexts:
        batch_query = batch_query.populate_existing()
    batches = {batch.id: batch for batch in batch_query} if batch_ids else {}
    contexts = {key: persisted_batch_bindings(batch) for key, batch in batches.items()}
    orthographic_contexts = {}
    for key, batch in batches.items():
        cached = orthographic_batch_contexts.get(key) if use_contexts else None
        snapshot = (batch.status, batch.bundle_sha256, batch.reviewed_artifact)
        if cached is not None and batch.status == "applied" and cached[:3] == snapshot:
            orthographic_contexts[key] = cached[3]
            continue
        if use_contexts:
            orthographic_batch_contexts.pop(key, None)
        context = name_orthographic.persisted_batch_bindings(batch)
        orthographic_contexts[key] = context
        if use_contexts and context is not None:
            orthographic_batch_contexts[key] = (*deepcopy(snapshot), context)
    positive_batch_ids = {evidence.research_payload.get("normative_ja_ko", {}).get("batch_id")
                          for name, evidence, *_ in rows if positive_proof(name, evidence)
                          and isinstance(evidence.research_payload, dict)
                          and isinstance(evidence.research_payload.get("normative_ja_ko"), dict)
                          and type(evidence.research_payload["normative_ja_ko"].get("batch_id")) is int}
    positive_batch_ids = {key for key in positive_batch_ids if type(key) is int and key in batches}
    registry_ids = {batches[key].source_registry_id for key in positive_batch_ids}
    registries = {row.id: row.registry for row in db.query(KifuNameSourceRegistry).filter(
        KifuNameSourceRegistry.id.in_(registry_ids))} if registry_ids else {}
    positive_changes = {key: [] for key in positive_batch_ids}
    if positive_batch_ids:
        for change in db.query(KifuNameChange).filter(KifuNameChange.batch_id.in_(positive_batch_ids)):
            positive_changes[change.batch_id].append(image(change))
    result = []
    for row in rows:
        name, evidence, *extra = row
        if positive_proof(name, evidence):
            payload = evidence.research_payload
            proof = payload.get("normative_ja_ko") if isinstance(payload, dict) else None
            batch_id = proof.get("batch_id") if isinstance(proof, dict) else None
            if type(batch_id) is int and batch_id in positive_batch_ids:
                batch = batches[batch_id]
                registry = registries.get(batch.source_registry_id)
                if persisted_positive_ja_ko_eligible(image(name), image(evidence), image(batch), registry,
                                                    positive_changes[batch_id]):
                    result.append(row)
            continue
        orthographic = orthographic_proof(name, evidence)
        if name.decision_kind != "transliterated" and not orthographic:
            result.append(row)
            continue
        proof = (
            evidence.research_payload.get("primary_orthographic" if orthographic else "transliteration")
            if isinstance(evidence.research_payload, dict)
            else None
        )
        batch_id = proof.get("batch_id") if isinstance(proof, dict) else None
        if type(batch_id) is not int or batch_id not in batches:
            continue
        raw = extra[0] if owner_column.startswith("raw_") and extra else None
        eligible = name_orthographic.persisted_name_eligible if orthographic else persisted_name_eligible
        context = orthographic_contexts[batch_id] if orthographic else contexts[batch_id]
        if (eligible(name, evidence, owner_column, raw, batches[batch_id], context, db)
            if orthographic else eligible(name, evidence, owner_column, raw, batches[batch_id], context)):
            result.append(row)
    return result


def _approved_raw_player_names(db, *, values=None, lang=None, display=None, orthographic_batch_contexts=None):
    """Return approved raw names with a verified finite scope when one was signed."""
    from katrain.web.kifu.name_candidates import canonical_sha256

    query = (
        _approved_names(db, KifuRawPlayerName, "raw_player_id", lang=lang)
        .join(KifuRawPlayerValue, KifuRawPlayerName.raw_player_id == KifuRawPlayerValue.id)
        .filter(KifuRawPlayerValue.review_status == "approved")
    )
    if values is not None:
        query = query.filter(KifuRawPlayerValue.raw_value.in_(values))
    if display is not None:
        query = query.filter(or_(KifuRawPlayerName.display_name == display,
                                 func.lower(KifuRawPlayerName.display_name) == display.lower()))
    rows = _qualified_name_rows(db, query, KifuRawPlayerName, "raw_player_id", KifuRawPlayerValue.raw_value,
                                orthographic_batch_contexts=orthographic_batch_contexts)
    batch_ids = set()
    for _, evidence, _ in rows:
        payload = evidence.research_payload
        proof = payload.get("raw_display_scope") if isinstance(payload, dict) else None
        if isinstance(proof, dict) and type(proof.get("batch_id")) is int:
            batch_ids.add(proof["batch_id"])
    batches = ({batch.id: batch for batch in db.query(KifuNameBatch).filter(KifuNameBatch.id.in_(batch_ids))}
               if batch_ids else {})
    result = []
    for name, evidence, raw in rows:
        payload = evidence.research_payload
        candidate = payload.get("candidate") if isinstance(payload, dict) else None
        proof = payload.get("raw_display_scope") if isinstance(payload, dict) else None
        if not isinstance(candidate, dict) or "raw_display_scope_sha256" not in candidate:
            if proof is None:
                result.append((name, raw, None))
            continue
        if not isinstance(proof, dict):
            continue
        batch = batches.get(proof.get("batch_id"))
        if batch is None or batch.status != "applied" or not isinstance(batch.reviewed_artifact, dict):
            continue
        bundle = batch.reviewed_artifact.get("bundle")
        if not isinstance(bundle, dict) or canonical_sha256(bundle) != batch.bundle_sha256:
            continue
        if candidate not in bundle.get("candidates", ()):
            continue
        owner = candidate.get("owner")
        owner_id = owner.get("id") if isinstance(owner, dict) else None
        if isinstance(owner, dict) and "ref" in owner:
            owner_id = batch.reviewed_artifact.get("resolved_refs", {}).get(
                f"raw_player:@{owner['ref']}")
        if (not isinstance(owner, dict) or owner.get("kind") != "raw_player"
                or owner_id != name.raw_player_id or candidate.get("raw_value") != raw
                or candidate.get("lang") != name.lang or candidate.get("display_name") != name.display_name
                or candidate.get("decision_kind") != name.decision_kind):
            continue
        declaration = next((item for item in bundle.get("owners", ())
                            if item.get("owner") == candidate.get("owner")), None)
        scope = declaration.get("raw_display_scope") if isinstance(declaration, dict) else None
        content = scope.get("content") if isinstance(scope, dict) else None
        if (not isinstance(scope, dict) or canonical_sha256(scope) != proof.get("scope_sha256")
                or proof["scope_sha256"] != candidate["raw_display_scope_sha256"]
                or not isinstance(content, dict) or not isinstance(content.get("slots"), list)
                or any(not isinstance(member, dict) or type(member.get("album_id")) is not int
                       or member.get("slot") not in {"black", "white"} for member in content["slots"])
                or content.get("raw_value") != raw
                or content.get("inventory_sha256") != bundle.get("inventory_sha256")):
            continue
        research = payload.get("research")
        if name.decision_kind != "transliterated" and name.generation_rule_version != "primary-orthographic-v1" and (
                not isinstance(research, dict)
                or research.get("raw_display_scope_sha256") != proof["scope_sha256"]):
            continue
        try:
            prepared = prepare_raw_player_scope(scope)
        except (EvidenceError, KeyError, TypeError, AttributeError):
            continue
        result.append((name, raw, prepared))
    return result


def _raw_player_slot(names, album, slot):
    raw = getattr(album, f"player_{slot}")
    item = names.get(raw)
    if item is None:
        return None
    value, scope = item
    return value if scope is None or raw_player_scope_slot(scope, album, slot, raw) else None


def strict_raw_player_search_clause(db, raw_values: set[str], display: str, *, names=None):
    """Expand a translated raw name only to eligible unlinked album slots."""
    clauses = []
    if names is None:
        names = _approved_raw_player_names(db, values=raw_values, display=display)
    for name, raw, scope in names:
        if raw not in raw_values:
            continue
        if scope is None:
            clauses.extend(((KifuAlbum.player_black == raw) & KifuAlbum.black_player_id.is_(None),
                            (KifuAlbum.player_white == raw) & KifuAlbum.white_player_id.is_(None)))
            continue
        for (album_id, _slot), context in scope.members.items():
            clauses.append(and_(KifuAlbum.id == album_id, *(
                getattr(KifuAlbum, field).is_(None) if value is None else getattr(KifuAlbum, field) == value
                for field, value in context.items()
            )))
    return or_(*clauses) if clauses else KifuAlbum.id.in_([])


def _approved_raw_event_names(db: Session, *, values=None, lang=None, display=None, name_ids=None):
    """Read complete names and their live base dependencies in at most two queries.

    Composition is checked against stored approvals; no renderer or source lookup
    runs here. Album membership and the live series link are checked by callers.
    """
    from katrain.web.kifu.name_candidates import (
        ARCHIVE_DESCRIPTION_CATEGORY, ARCHIVE_DESCRIPTION_VERSION, CandidateError, _check_signature,
        canonical_sha256, validate_archive_description_scope, validate_archive_description_candidate,
    )
    from katrain.web.kifu.name_composition import COMPOSITION_VERSION, HONINBO_EDITION, base_candidate_sha256
    from katrain.web.kifu.raw_event_translation import eligible_literal_raw_name

    query = (
        _approved_names(db, KifuRawEventName, "raw_event_id", lang=lang)
        .join(KifuRawEventValue, KifuRawEventName.raw_event_id == KifuRawEventValue.id)
        .filter(KifuRawEventValue.review_status == "approved")
    )
    if values is not None:
        query = query.filter(KifuRawEventValue.raw_value.in_(values))
    if name_ids is not None:
        query = query.filter(KifuRawEventName.id.in_(name_ids))
    if display is not None:
        query = query.filter(
            or_(KifuRawEventName.display_name == display, func.lower(KifuRawEventName.display_name) == display.lower())
        )
    rows = [
        (name, raw, evidence, raw_owner)
        for name, evidence, raw, raw_owner in _qualified_name_rows(
            db, query, KifuRawEventName, "raw_event_id", KifuRawEventValue.raw_value, KifuRawEventValue
        )
    ]
    composed = [row for row in rows if row[0].decision_kind == "composed"]
    bases = {}
    if composed:
        base_ids = set()
        for _, _, evidence, _ in composed:
            payload = evidence.research_payload
            composition = payload.get("composition") if isinstance(payload, dict) else None
            dependencies = composition.get("dependencies") if isinstance(composition, dict) else None
            if isinstance(dependencies, dict) and type(dependencies.get("base_name_id")) is int:
                base_ids.add(dependencies["base_name_id"])
        bases = {
            name.id: (name, evidence)
            for name, evidence in _qualified_name_rows(
                db,
                _approved_names(db, KifuEventName, "event_id").filter(KifuEventName.id.in_(base_ids)),
                KifuEventName,
                "event_id",
            )
        }
    result = []
    for name, raw, evidence, raw_owner in rows:
        if name.decision_kind == "translated":
            if eligible_literal_raw_name(vars(name), vars(evidence), vars(raw_owner)):
                result.append((name, raw, None))
            continue
        if (raw_owner.category == ARCHIVE_DESCRIPTION_CATEGORY
                or raw_owner.parser_version == ARCHIVE_DESCRIPTION_VERSION) and name.decision_kind != "archive_description":
            continue
        if name.decision_kind == "archive_description":
            payload = evidence.research_payload
            if not isinstance(payload, dict) or payload.get("research") is not None:
                continue
            scope, candidate = payload.get("archive_description"), payload.get("candidate")
            try:
                validate_archive_description_scope(scope)
                _check_signature(candidate)
                validate_archive_description_candidate(candidate, scope)
                owner = candidate["owner"]
                if not (candidate["raw_value"] == raw and candidate["lang"] == name.lang
                        and candidate["display_name"] == name.display_name
                        and candidate["decision_kind"] == name.decision_kind == evidence.decision_kind == "archive_description"
                        and candidate["generation_rule_version"] == name.generation_rule_version
                        == evidence.generation_rule_version == ARCHIVE_DESCRIPTION_VERSION
                        and (owner.get("id") == name.raw_event_id or isinstance(owner.get("ref"), str))
                        and raw_owner.category == ARCHIVE_DESCRIPTION_CATEGORY
                        and raw_owner.parser_version == ARCHIVE_DESCRIPTION_VERSION
                        and raw_owner.review_metadata == scope["declaration"]["category_review"]):
                    continue
            except (CandidateError, KeyError, TypeError, AttributeError, ValueError):
                continue
            result.append((name, raw, scope))
            continue
        if name.decision_kind != "composed":
            result.append((name, raw, None))
            continue
        payload = evidence.research_payload
        if not isinstance(payload, dict):
            continue
        composition, candidate = payload.get("composition"), payload.get("candidate")
        if not isinstance(composition, dict) or not isinstance(candidate, dict):
            continue
        dependencies = composition.get("dependencies")
        rule, scope = composition.get("rule"), composition.get("scope")
        if not all(isinstance(value, dict) for value in (dependencies, rule, scope)):
            continue
        if type(dependencies.get("base_name_id")) is not int:
            continue
        rule_content, scope_content = rule.get("content"), scope.get("content")
        if not isinstance(rule_content, dict) or not isinstance(scope_content, dict):
            continue
        base_pair = bases.get(dependencies.get("base_name_id"))
        if not base_pair:
            continue
        base, base_evidence = base_pair
        base_payload = base_evidence.research_payload
        base_candidate = base_payload.get("candidate") if isinstance(base_payload, dict) else None
        raw_entries = scope_content.get("raws")
        if not isinstance(base_candidate, dict) or not isinstance(raw_entries, list):
            continue
        entries = [entry for entry in raw_entries if isinstance(entry, dict) and entry.get("raw_value") == raw]
        if len(entries) != 1:
            continue
        entry = entries[0]
        owner = candidate.get("owner")
        series_owner = candidate.get("series_owner")
        ids = entry.get("occurrence_album_ids")
        if not (
            isinstance(owner, dict)
            and owner.get("kind") == "raw_event"
            and (owner.get("id") == name.raw_event_id or isinstance(owner.get("ref"), str))
            and owner == entry.get("owner")
            and isinstance(series_owner, dict)
            and series_owner.get("kind") == "event"
            and (series_owner.get("id") == base.event_id or isinstance(series_owner.get("ref"), str))
            and series_owner
            == scope_content.get("series_owner")
            == rule_content.get("series_owner")
            == base_candidate.get("owner")
            and isinstance(ids, list)
            and ids
            and all(type(value) is int for value in ids)
        ):
            continue
        if not (
            composition.get("version") == COMPOSITION_VERSION
            and candidate.get("raw_value") == raw
            and candidate.get("lang") == name.lang
            and candidate.get("display_name") == name.display_name
            and candidate.get("decision_kind") == "composed"
            and candidate.get("edition") == entry.get("edition") == HONINBO_EDITION.get(raw)
            and dependencies.get("series_event_id") == base.event_id
            and dependencies.get("base_evidence_id") == base.evidence_id
            and dependencies.get("base_revision") == base.revision
            and base.lang == name.lang == base_candidate.get("lang") == rule_content.get("lang")
            and base.display_name == base_candidate.get("display_name")
            and dependencies.get("base_candidate_sha256")
            == base_candidate_sha256(base_candidate)
            == candidate.get("base_candidate_sha256")
            == rule_content.get("base_candidate_sha256")
            and dependencies.get("composition_rule_sha256")
            == canonical_sha256(rule)
            == candidate.get("composition_rule_sha256")
            and dependencies.get("scope_sha256") == canonical_sha256(scope)
            and dependencies.get("raw_scope_sha256")
            == entry.get("raw_scope_sha256")
            == candidate.get("raw_scope_sha256")
            and entry.get("occurrence_sha256") == canonical_sha256(ids)
            and ids == sorted(set(ids))
            and entry.get("raw_scope_sha256") == canonical_sha256([[album_id, "event"] for album_id in ids])
        ):
            continue
        result.append((name, raw, composition))
    return result


def _raw_event_map(rows, albums, selected_events, *, approvals=False, selected_ids=frozenset()):
    result = {}
    for name, raw, composition in rows:
        value = (name.decision_kind, name.evidence_id) if approvals else name.display_name
        if name.decision_kind == "translated":
            for album in albums:
                if (album.id not in selected_events and album.id not in selected_ids
                        and album.event == raw and album.event_id is None
                        and album.duplicate_of_id is None and album.list_hidden_reason is None):
                    result[(album.id, raw, None)] = value
            continue
        if composition is None:
            result[raw] = value
            continue
        if name.decision_kind == "archive_description":
            ids = set(composition["declaration"]["occurrence_album_ids"])
            for album in albums:
                if (album.id in ids and album.id not in selected_events
                        and album.event == raw and album.event_id is None):
                    result[(album.id, raw, None)] = value
            continue
        dependencies = composition["dependencies"]
        entry = next(entry for entry in composition["scope"]["content"]["raws"] if entry["raw_value"] == raw)
        ids = set(entry["occurrence_album_ids"])
        for album in albums:
            # The frozen Honinbo cohort contains direct event slots only.
            if album.id in selected_events:
                continue
            current_raw, event_id = selected_events.get(album.id, (album.event, album.event_id))
            if album.id in ids and current_raw == raw and event_id == dependencies["series_event_id"]:
                result[(album.id, raw, event_id)] = value
    return result


def _raw_event_value(values, album_id, raw, event_id, default=None):
    return values.get((album_id, raw, event_id), values.get(raw, default))


def strict_raw_event_search_clause(db: Session, name_ids: set[int]):
    """Restrict finite raw descriptions to their approved current direct event slots."""
    clauses = []
    for name, raw, composition in _approved_raw_event_names(db, name_ids=name_ids):
        if name.decision_kind == "translated":
            clauses.append((KifuAlbum.event == raw) & KifuAlbum.event_id.is_(None)
                           & KifuAlbum.duplicate_of_id.is_(None) & KifuAlbum.list_hidden_reason.is_(None)
                           & ~KifuAlbum.id.in_(db.query(KifuAlbumEventSelection.album_id)))
        elif composition is None:
            clauses.append(KifuAlbum.event == raw)
        elif name.decision_kind == "archive_description":
            clauses.append((KifuAlbum.event == raw) & KifuAlbum.event_id.is_(None)
                           & KifuAlbum.id.in_(composition["declaration"]["occurrence_album_ids"]))
        else:
            entry = next(entry for entry in composition["scope"]["content"]["raws"] if entry["raw_value"] == raw)
            clauses.append(
                (KifuAlbum.event == raw)
                & (KifuAlbum.event_id == composition["dependencies"]["series_event_id"])
                & KifuAlbum.id.in_(entry["occurrence_album_ids"])
            )
    return or_(*clauses) if clauses else KifuAlbum.id.in_([])


def strict_matching_names(
    db: Session, query: str, *, raw_name_rows=None, orthographic_batch_contexts=None
) -> tuple[set[int], set[int], set[str], set[int]]:
    """Expand only a unique approved owner across identity and raw-name scopes."""
    needle = normalize_alias(query)
    if not needle:
        return set(), set(), set(), set()
    identity_matches = []
    for model, owner in ((KifuPlayerName, "player_id"), (KifuEventName, "event_id")):
        rows = _approved_names(db, model, owner).filter(
            or_(model.display_name == query, func.lower(model.display_name) == query.lower())
        )
        identity_matches.append(
            {
                getattr(row, owner)
                for row, _ in _qualified_name_rows(
                    db, rows, model, owner,
                    orthographic_batch_contexts=orthographic_batch_contexts if model is KifuPlayerName else None
                )
                if normalize_alias(row.display_name) == needle
            }
        )
    raw_matches = []
    raw_event_name_ids = set()
    for model, value_model, owner in (
        (KifuRawPlayerName, KifuRawPlayerValue, "raw_player_id"),
        (KifuRawEventName, KifuRawEventValue, "raw_event_id"),
    ):
        if model is KifuRawEventName:
            matched = [
                (name, raw)
                for name, raw, _ in _approved_raw_event_names(db, display=query)
                if normalize_alias(name.display_name) == needle
            ]
            raw_matches.append({raw for _, raw in matched})
            raw_event_name_ids = {name.id for name, _ in matched}
            continue
        scoped_matches = _approved_raw_player_names(db, display=query,
                                                    orthographic_batch_contexts=orthographic_batch_contexts)
        if raw_name_rows is not None:
            raw_name_rows.extend(scoped_matches)
        matches = {
            raw
            for name, raw, _ in scoped_matches
            if normalize_alias(name.display_name) == needle
        }
        raw_matches.append(matches)
    matches_by_owner = (*identity_matches, *raw_matches)
    raw_title_group = (not any(identity_matches) and not raw_matches[0]
                       and len(raw_matches[1]) > 1
                       and all(name.decision_kind == "translated" for name, _ in matched))
    if sum(len(matches) for matches in matches_by_owner) != 1 and not raw_title_group:
        return set(), set(), set(), set()
    return matches_by_owner[0], matches_by_owner[1], matches_by_owner[2], raw_event_name_ids


def live_event_selections(
    db: Session, albums: list, *, album_ids: set[int] | None = None
) -> dict[int, tuple[str, int | None]]:
    """Read current approved GN[1] choices for a page, rejecting changed SGF content."""
    from katrain.web.kifu.event_selection import verified_selection_rows

    if album_ids is None:
        album_ids = {album.id for album in albums if album.event == "GNUGo3.8"}
    if not album_ids:
        return {}
    table = KifuAlbumEventSelection.__table__
    selected_rows = db.execute(table.select().where(table.c.album_id.in_(album_ids))).mappings().all()
    proofs = verified_selection_rows(db.connection(), selected_rows)
    return {
        row["album_id"]: (row["selected_raw"], proofs[row["album_id"]]["event_id"])
        for row in selected_rows if row["album_id"] in proofs
    }


def strict_selected_event_search_ids(
    db: Session, query: str, raw_name_ids: set[int], event_ids: set[int]
) -> set[int]:
    """Match reviewed selected events and validate the same live SGF hash as display."""
    matched_names = _approved_raw_event_names(db, name_ids=raw_name_ids) if raw_name_ids else []
    raw_aliases = {raw for name, raw, _ in matched_names if name.decision_kind != "translated"}
    selected_conditions = [KifuAlbumEventSelection.selected_raw.contains(query, autoescape=True)]
    if raw_aliases:
        selected_conditions.append(KifuAlbumEventSelection.selected_raw.in_(raw_aliases))
    if event_ids:
        selected_conditions.append(KifuAlbumEventSelection.event_id.in_(event_ids))
    selected_raws = {
        raw for (raw,) in db.query(KifuAlbumEventSelection.selected_raw).filter(or_(*selected_conditions)).distinct()
    }
    if not selected_raws:
        return set()
    names_by_raw = {}
    for name, raw, _ in _approved_raw_event_names(db, values=selected_raws):
        if name.decision_kind == "translated":
            continue
        names_by_raw.setdefault(raw, []).append(name)
    raw_matches = {
        raw
        for raw, names in names_by_raw.items()
        if query.lower() in raw.lower() or any(name.id in raw_name_ids for name in names)
    }
    conditions = []
    if raw_matches:
        conditions.append(KifuAlbumEventSelection.selected_raw.in_(raw_matches))
    if event_ids:
        conditions.append(KifuAlbumEventSelection.event_id.in_(event_ids))
    if not conditions:
        return set()
    selected = (
        db.query(KifuAlbumEventSelection.album_id, KifuAlbumEventSelection.sgf_sha256, KifuAlbum.sgf_content)
        .join(KifuAlbum, KifuAlbum.id == KifuAlbumEventSelection.album_id)
        .join(KifuEventSelectionBatch, KifuEventSelectionBatch.id == KifuAlbumEventSelection.batch_id)
        .filter(
            KifuAlbum.duplicate_of_id.is_(None),
            KifuAlbum.event == "GNUGo3.8",
            KifuAlbumEventSelection.status == "approved",
            KifuEventSelectionBatch.status == "applied",
            or_(*conditions),
        )
    )
    if db.bind.dialect.name == "postgresql":
        live_hash = func.encode(func.sha256(func.convert_to(KifuAlbum.sgf_content, "UTF8")), "hex")
        candidate_ids = {
            album_id for (album_id,) in selected.filter(live_hash == KifuAlbumEventSelection.sgf_sha256)
            .with_entities(KifuAlbumEventSelection.album_id)
        }
    else:
        candidate_ids = {
            album_id for album_id, pinned_hash, content in selected
            if hashlib.sha256(content.encode("utf-8")).hexdigest() == pinned_hash
        }
    verified = live_event_selections(db, [], album_ids=candidate_ids)
    if not verified:
        return set()
    albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_(verified)).all()
    candidate_names = {
        album_id: [
            name for name in names_by_raw.get(raw, [])
            if query.lower() in raw.lower() or name.id in raw_name_ids
        ]
        for album_id, (raw, _) in verified.items()
    }
    languages = {name.lang for names in candidate_names.values() for name in names if name.lang in LANGUAGES}
    # An identity match can use any complete current event approval. A raw-name
    # match must retain the exact name evidence that matched the query.
    if event_ids:
        languages.update(name.lang for names in names_by_raw.values() for name in names if name.lang in LANGUAGES)
    approvals_by_lang = {
        lang: strict_slot_approvals(db, albums, lang, obscured_event_ids=set(), selected_events=verified)
        for lang in languages
    }
    approved_ids = set()
    for album_id, (raw, event_id) in verified.items():
        structured = bool(structure_event(raw)["components"]) or (
            parse_event(raw, None).category == "formal_event_candidate"
        )
        if event_id in event_ids and not structured:
            approved_ids.add(album_id)
            continue
        if event_id in event_ids and any(
            approvals[album_id][2] is not None for approvals in approvals_by_lang.values()
        ):
            approved_ids.add(album_id)
            continue
        for name in candidate_names[album_id]:
            approvals = approvals_by_lang.get(name.lang)
            if approvals and approvals[album_id][2] == (name.decision_kind, name.evidence_id):
                approved_ids.add(album_id)
                break
    return approved_ids


def strict_display_maps(
    db: Session, albums: list, lang: str, *, selected_events=None, orthographic_batch_contexts=None
):
    """Read names for the current page in bounded, batched queries."""
    player_ids = {v for album in albums for v in (album.black_player_id, album.white_player_id) if v}
    selected_events = selected_events or {}
    event_ids = {album.event_id for album in albums if album.event_id}
    event_ids.update(event_id for _, event_id in selected_events.values() if event_id)
    raw_players = {v for album in albums for v in (album.player_black, album.player_white) if v is not None}
    raw_events = {album.event or "" for album in albums}
    raw_events.update(raw for raw, _ in selected_events.values())
    players = {
        row.player_id: row.display_name
        for row, _ in _qualified_name_rows(
            db, _approved_names(db, KifuPlayerName, "player_id", player_ids, lang), KifuPlayerName, "player_id",
            orthographic_batch_contexts=orthographic_batch_contexts
        )
    }
    event_rows = _qualified_name_rows(
        db,
        _approved_names(db, KifuEventName, "event_id", event_ids, lang).join(
            KifuEvent, KifuEventName.event_id == KifuEvent.id
        ),
        KifuEventName,
        "event_id",
        KifuEvent.canonical_name,
    )
    events = {row.event_id: row.display_name for row, _, _ in event_rows}
    canonical = {row.event_id: canonical for row, _, canonical in event_rows}
    raw_maps = []
    for model, value_model, owner, values in (
        (KifuRawPlayerName, KifuRawPlayerValue, "raw_player_id", raw_players),
        (KifuRawEventName, KifuRawEventValue, "raw_event_id", raw_events),
    ):
        if model is KifuRawEventName:
            rows = _approved_raw_event_names(db, values=values, lang=lang)
            selected_ids = ({album_id for (album_id,) in db.query(KifuAlbumEventSelection.album_id).filter(
                KifuAlbumEventSelection.album_id.in_([album.id for album in albums]))}
                if any(name.decision_kind == "translated" for name, _, _ in rows) else set())
            raw_maps.append(
                _raw_event_map(rows, albums, selected_events, selected_ids=selected_ids)
            )
            continue
        raw_maps.append({raw: (name.display_name, scope)
                         for name, raw, scope in _approved_raw_player_names(
                             db, values=values, lang=lang, orthographic_batch_contexts=orthographic_batch_contexts
                         )})
    album_ids = [album.id for album in albums]
    sources: dict[int, set[str]] = {album_id: set() for album_id in album_ids}
    if album_ids:
        for album_id, source_key in (
            db.query(KifuAlbumSource.album_id, KifuSource.source_key)
            .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
            .filter(KifuAlbumSource.album_id.in_(album_ids))
        ):
            sources[album_id].add(source_key)
    return players, events, canonical, {k: sorted(v) for k, v in sources.items()}, *raw_maps


def _empty_event(raw: str | None) -> bool:
    """An absent SGF event has one explicit, language-independent empty display."""
    return parse_event(raw, None).category == "empty"


def obscured_program_event_ids(db: Session, albums: list, *, selected_events=None) -> set[int]:
    """Find albums where an imported program label conceals another root game name.

    This is a coverage guard, not approval of the second GN as a translated
    event. Read candidate SGFs in one query when the caller deferred content.
    """
    selected_events = selected_events or {}
    candidates = [album.id for album in albums if album.event == "GNUGo3.8" and album.id not in selected_events]
    if not candidates:
        return set()
    rows = db.query(KifuAlbum.id, KifuAlbum.sgf_content).filter(KifuAlbum.id.in_(candidates))
    # An existing selection that failed shared proof cannot become a hidden
    # program label merely because its replacement SGF no longer has a second GN.
    obscured = {album_id for (album_id,) in db.query(KifuAlbumEventSelection.album_id)
                .filter(KifuAlbumEventSelection.album_id.in_(candidates))}
    for album_id, content in rows:
        try:
            names = SGF.parse_sgf(content).get_list_property("GN") or []
        except Exception:
            # A program label with unreadable source cannot earn a hidden approval.
            obscured.add(album_id)
            continue
        if names and names[0] == "GNUGo3.8" and any(
            name and name != names[0]
            and parse_event(name, None).category not in {"program_source_label", "corrupt_data"}
            for name in names[1:]
        ):
            obscured.add(album_id)
    return obscured


def strict_slot_approvals(
    db: Session, albums: list, lang: str, *, obscured_event_ids: set[int] | None = None,
    selected_events: dict[int, tuple[str, int | None]] | None = None,
) -> dict[int, tuple[tuple[str, int | None] | None, ...]]:
    """Return approved decision/evidence for each visible slot; None is a coverage gap.

    Structured events need both an approved identity name and their own approved
    exact raw-event display; CWI editions additionally require an Oteai identity.
    An absent event has an explicit empty decision with
    no evidence row because there is no source value to research. Queries remain
    bounded by the supplied album page.
    """
    selected_events = selected_events or {}
    if obscured_event_ids is None:
        obscured_event_ids = obscured_program_event_ids(db, albums, selected_events=selected_events)
    player_ids = {v for album in albums for v in (album.black_player_id, album.white_player_id) if v}
    event_ids = {album.event_id for album in albums if album.event_id}
    event_ids.update(event_id for _, event_id in selected_events.values() if event_id)
    raw_player_values = {v for album in albums for v in (album.player_black, album.player_white)}
    raw_event_values = {album.event or "" for album in albums}
    raw_event_values.update(raw for raw, _ in selected_events.values())
    entity_approvals = []
    for model, owner, ids in (
        (KifuPlayerName, "player_id", player_ids),
        (KifuEventName, "event_id", event_ids),
    ):
        rows = _qualified_name_rows(db, _approved_names(db, model, owner, ids, lang), model, owner)
        entity_approvals.append({getattr(name, owner): (name.decision_kind, name.evidence_id) for name, _ in rows})
    raw_approvals = []
    for model, value_model, owner, values in (
        (KifuRawPlayerName, KifuRawPlayerValue, "raw_player_id", raw_player_values),
        (KifuRawEventName, KifuRawEventValue, "raw_event_id", raw_event_values),
    ):
        if model is KifuRawEventName:
            rows = _approved_raw_event_names(db, values=values, lang=lang)
            selected_ids = ({album_id for (album_id,) in db.query(KifuAlbumEventSelection.album_id).filter(
                KifuAlbumEventSelection.album_id.in_([album.id for album in albums]))}
                if any(name.decision_kind == "translated" for name, _, _ in rows) else set())
            raw_approvals.append(
                _raw_event_map(rows, albums, selected_events, approvals=True, selected_ids=selected_ids)
            )
            continue
        raw_approvals.append({raw: ((name.decision_kind, name.evidence_id), scope)
                              for name, raw, scope in _approved_raw_player_names(db, values=values, lang=lang)})
    canonical = dict(db.query(KifuEvent.id, KifuEvent.canonical_name).filter(KifuEvent.id.in_(event_ids)))
    players, events = entity_approvals
    raw_players, raw_events = raw_approvals
    result = {}
    for album in albums:
        event_raw, event_id = selected_events.get(album.id, (album.event, album.event_id))
        black = players.get(album.black_player_id) if album.black_player_id else _raw_player_slot(raw_players, album, "black")
        white = players.get(album.white_player_id) if album.white_player_id else _raw_player_slot(raw_players, album, "white")
        if event_id:
            event_approval = events.get(event_id)
            if parse_event(event_raw, None).category == "formal_event_candidate":
                event_approval = (
                    _raw_event_value(raw_events, album.id, event_raw, event_id)
                    if event_approval and canonical.get(event_id) == "Oteai"
                    else None
                )
            elif event_approval:
                event_approval = _raw_event_value(
                    raw_events,
                    album.id,
                    event_raw,
                    event_id,
                    None if structure_event(event_raw or "")["components"] else event_approval,
                )
        else:
            event_approval = (("hidden", None) if _empty_event(event_raw)
                              else _raw_event_value(raw_events, album.id, event_raw or "", event_id))
        if album.id in obscured_event_ids:
            event_approval = None
        result[album.id] = black, white, event_approval
    return result


def strict_fallback(raw: str | None, lang: str, kind: str) -> str:
    """An explicit localized fallback keeps malformed SGF outside display fields."""
    from katrain.web.kifu.name_candidates import _CLASSIFICATION_TEMPLATES

    labels = _CLASSIFICATION_TEMPLATES[lang]
    if kind == "player":
        category = parse_player(raw, None).category
        if category == "corrupt_pending":
            return labels["player_error"]
        if category == "placeholder":
            return labels["placeholder"]
        return strict_unavailable_label(lang, kind)
    category = parse_event(raw, None).category
    if _empty_event(raw):
        return ""
    if category == "corrupt_data":
        return labels["event_error"]
    return strict_unavailable_label(lang, kind)


def resolve_strict_display(
    album,
    lang: str,
    players: dict[int, str],
    events: dict[int, str],
    canonical_events: dict[int, str],
    raw_players: dict[str, str],
    raw_events: dict[str, str],
    *,
    obscured_event_ids: set[int] | None = None,
    selected_events: dict[int, tuple[str, int | None]] | None = None,
    fallback_names: tuple[str, str, str] | None = None,
) -> tuple[str, str, str]:
    """Resolve approved slots; optional existing names support progressive display outside strict mode."""
    black = (
        players.get(album.black_player_id) if album.black_player_id else _raw_player_slot(raw_players, album, "black")
    )
    white = (
        players.get(album.white_player_id) if album.white_player_id else _raw_player_slot(raw_players, album, "white")
    )
    event_raw, event_id = (selected_events or {}).get(album.id, (album.event, album.event_id))
    event_name = events.get(event_id) if event_id else _raw_event_value(raw_events, album.id, event_raw or "", event_id)
    if obscured_event_ids and album.id in obscured_event_ids:
        displayed_event = None if fallback_names else strict_unavailable_label(lang, "event")
    elif event_id and event_name is not None:
        if parse_event(event_raw, None).category == "formal_event_candidate":
            displayed_event = (
                _raw_event_value(raw_events, album.id, event_raw, event_id)
                if canonical_events.get(event_id) == "Oteai"
                else None
            )
        else:
            # Progressive display can use the approved series title; strict
            # display still requires an exact approval for structured raw text.
            displayed_event = _raw_event_value(
                raw_events,
                album.id,
                event_raw,
                event_id,
                None
                if fallback_names is None and structure_event(event_raw or "")["components"]
                else event_name,
            )
    else:
        displayed_event = event_name
    return (
        black
        if black is not None
        else (fallback_names[0] if fallback_names else strict_fallback(album.player_black, lang, "player")),
        white
        if white is not None
        else (fallback_names[1] if fallback_names else strict_fallback(album.player_white, lang, "player")),
        displayed_event
        if displayed_event is not None
        else (fallback_names[2] if fallback_names else strict_fallback(event_raw, lang, "event")),
    )


def normalize_alias(value: str) -> str:
    """Normalize spacing, width and case while preserving the original script."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def split_player_rank(raw: str | None) -> tuple[str, str | None]:
    """Separate an unambiguous Chinese dan suffix from a player's raw SGF name."""
    parsed = parse_player(raw, None)
    return parsed.name, parsed.embedded_rank


def player_identity_name(raw: str | None) -> str:
    return split_player_rank(raw)[0]


def event_identity_name(raw: str | None) -> str:
    """Find a provisional identity lookup key without approving the event."""
    return parse_event(raw, None).event_candidate or raw or ""


def identity_lookup_name(kind: str, raw: str | None) -> str:
    return event_identity_name(raw) if kind == "event" else player_identity_name(raw)


def display_event_name(
    raw: str | None, translated: str | None, lang: str, *, linked_canonical_name: str | None
) -> str | None:
    """Decorate a CWI edition only for a linked Oteai with a verified name."""
    parsed = parse_event(raw, None)
    if parsed.category != "formal_event_candidate":
        return translated or raw
    if not translated or linked_canonical_name != "Oteai":
        return raw
    year, season = parsed.year, parsed.season
    labels = {
        "en": ("Spring", "Autumn"),
        "cn": ("春季", "秋季"),
        "tw": ("春季", "秋季"),
        "jp": ("春季", "秋季"),
        "ko": ("봄", "가을"),
        "de": ("Frühjahr", "Herbst"),
        "es": ("primavera", "otoño"),
        "fr": ("printemps", "automne"),
        "ru": ("весна", "осень"),
        "tr": ("ilkbahar", "sonbahar"),
        "ua": ("весна", "осінь"),
    }
    if lang not in labels:
        return raw
    label = labels[lang][0 if season.casefold() == "spring" else 1]
    if lang in {"cn", "tw", "jp"}:
        return f"{year}年{label}{translated}"
    if lang == "ko":
        return f"{year}년 {label} {translated}"
    return f"{translated} · {label} {year}"


def matching_entity_ids(db: Session, query: str, *, exact: bool) -> tuple[set[int], set[int]]:
    needle = normalize_alias(query)
    if not needle:
        return set(), set()
    player_query = db.query(KifuPlayerAlias.player_id)
    event_query = db.query(KifuEventAlias.event_id)
    if exact:
        player_query = player_query.filter(KifuPlayerAlias.normalized_alias == needle)
        event_query = event_query.filter(KifuEventAlias.normalized_alias == needle)
    else:
        player_query = player_query.filter(KifuPlayerAlias.normalized_alias.contains(needle, autoescape=True))
        event_query = event_query.filter(KifuEventAlias.normalized_alias.contains(needle, autoescape=True))
    player_ids = {row[0] for row in player_query.distinct()}
    event_ids = {row[0] for row in event_query.distinct()}
    if exact:
        # The existing proof gate checks the applied batch and official source.
        query_rows = _approved_names(db, KifuPlayerName, "player_id", lang="tw").filter(
            KifuPlayerName.decision_kind == "generated",
            KifuPlayerName.generation_rule_version == "primary-orthographic-v1",
            KifuPlayerName.display_name == query,
        )
        player_ids.update(
            name.player_id
            for name, _ in _qualified_name_rows(db, query_rows, KifuPlayerName, "player_id")
            if normalize_alias(name.display_name) == needle
        )
    return player_ids, event_ids


def display_maps(db: Session, albums: list, lang: str, *, selected_events=None):
    """Load legacy names and provisional Chinese hints for non-strict display."""
    player_ids = {value for album in albums for value in (album.black_player_id, album.white_player_id) if value}
    event_ids = {album.event_id for album in albums if album.event_id}
    album_ids = [album.id for album in albums]
    players = {}
    events = {}
    event_canonical_names = {}
    sources: dict[int, set[str]] = {album_id: set() for album_id in album_ids}
    if player_ids:
        players = {
            row.player_id: row.display_name
            for row in db.query(KifuPlayerName).filter(
                KifuPlayerName.player_id.in_(player_ids),
                KifuPlayerName.lang == lang,
                KifuPlayerName.status == "verified",
                KifuPlayerName.evidence_id.is_(None),
                KifuPlayerName.decision_kind.is_(None),
                KifuPlayerName.generation_rule_version.is_(None),
                KifuPlayerName.revision.is_(None),
            )
        }
        if lang == "cn":
            for player_id, canonical in db.query(KifuPlayer.id, KifuPlayer.canonical_name).filter(
                KifuPlayer.id.in_(player_ids)
            ):
                if any("\u3400" <= char <= "\u9fff" for char in canonical):
                    players.setdefault(player_id, canonical)
    if event_ids:
        event_rows = (
            db.query(KifuEventName.event_id, KifuEventName.display_name, KifuEvent.canonical_name)
            .join(KifuEvent, KifuEventName.event_id == KifuEvent.id)
            .filter(
                KifuEventName.event_id.in_(event_ids),
                KifuEventName.lang == lang,
                KifuEventName.status == "verified",
                KifuEventName.evidence_id.is_(None),
                KifuEventName.decision_kind.is_(None),
                KifuEventName.generation_rule_version.is_(None),
                KifuEventName.revision.is_(None),
            )
            .all()
        )
        events = {row.event_id: row.display_name for row in event_rows}
        event_canonical_names = {row.event_id: row.canonical_name for row in event_rows}
        if lang == "cn":
            for event_id, canonical in db.query(KifuEvent.id, KifuEvent.canonical_name).filter(
                KifuEvent.id.in_(event_ids)
            ):
                event_canonical_names[event_id] = canonical
    if album_ids:
        for album_id, source_key in (
            db.query(KifuAlbumSource.album_id, KifuSource.source_key)
            .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
            .filter(KifuAlbumSource.album_id.in_(album_ids))
        ):
            sources[album_id].add(source_key)
    hints = {}
    if lang == "cn":
        from katrain.web.kifu.first_pass_cn import event_hints

        hints = event_hints(db, albums, event_canonical_names, selected_events=selected_events)
    return players, events, event_canonical_names, {album_id: sorted(keys) for album_id, keys in sources.items()}, hints
