"""One authorized generated-name profile; no external publication is claimed."""

import re
from collections import Counter

VERSION = "user_authorized_first_pass_v1"
LEVEL = "generated_first_pass"
LANGUAGES = frozenset({"en", "cn", "tw", "jp", "ko"})
METHODS = frozenset({"retain_original", "orthographic_conversion", "transliteration", "translation"})
READABLE_RAW_CATEGORIES = frozenset({"formal_event_candidate", "game_description", "unclassified_pending"})
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SGF_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}(?:\.sgf|sgf)$", re.I)
RECORD_LABEL_MODE = "literal_record_label"
RECORD_LABELS = {"cn": "棋谱标记：{raw}", "tw": "棋譜標記：{raw}",
                 "jp": "棋譜ラベル：{raw}", "ko": "기보 표기: {raw}", "en": "Record label: {raw}"}


def record_label_kind(raw):
    if raw == "GNUGo3.8":
        return "program_token"
    if isinstance(raw, str) and _SGF_TOKEN.fullmatch(raw):
        return "sgf_token"
    return None


def record_label_display(lang, raw):
    return RECORD_LABELS[lang].format(raw=raw)


def eligible_record_label(research, owner_category):
    source = research.get("source_input") if isinstance(research, dict) else None
    generation = research.get("generation") if isinstance(research, dict) else None
    if not (isinstance(source, dict) and isinstance(generation, dict)
            and source.get("kind") == "raw_event_literal"
            and generation.get("method") == "translation"
            and generation.get("submode") == RECORD_LABEL_MODE
            and research.get("lang") in RECORD_LABELS):
        return False
    raw = source.get("text")
    kind = record_label_kind(raw)
    expected_category = {"program_token": "program_source_label", "sgf_token": "unclassified_pending"}.get(kind)
    from katrain.web.kifu.name_parse import parse_event
    return (kind is not None and source.get("record_label_basis") == kind
            and owner_category == expected_category
            and parse_event(raw, None).category == expected_category
            and research.get("candidate_name") == record_label_display(research["lang"], raw))


def is_first_pass(row):
    return isinstance(row, dict) and any(row.get(key) == value for key, value in (
        ("source_basis", VERSION), ("generation_rule_version", VERSION),
        ("scope_status", LEVEL), ("verification_level", LEVEL)))


def validate_research(record):
    if not (record.get("source_basis") == VERSION and record.get("scope_status") == LEVEL
            and record.get("verification_level") == LEVEL and record.get("lang") in LANGUAGES):
        raise ValueError("first-pass markers or language differ")
    if any(key in record for key in (
        "source_checks", "negative_closure", "original_language_basis_url", "reading_basis_url",
        "positive_generation", "positive_zh_ko", "translation_support", "sgf_literal_evidence",
        "primary_orthographic", "transliteration")):
        raise ValueError("first pass cannot claim sourced or negative-search evidence")
    if record.get("generation_rule_version") not in {None, VERSION}:
        raise ValueError("first pass cannot mix another generation rule")
    owner = record.get("owner")
    source = record.get("source_input")
    generation = record.get("generation")
    if not (isinstance(owner, dict) and owner.get("kind") in {"player", "event", "raw_event", "raw_player"}
            and type(owner.get("id")) is int and owner["id"] > 0
            and isinstance(source, dict) and source.get("owner") == owner
            and source.get("kind") in {"catalog_canonical", "existing_locale", "raw_event_literal", "raw_player_literal"}
            and isinstance(source.get("text"), str) and source["text"]
            and _HASH.fullmatch(str(source.get("owner_preimage_sha256", "")))
            and record.get("original_name") == source["text"]
            and isinstance(record.get("original_language"), str) and record["original_language"]
            and isinstance(record.get("candidate_name"), str) and record["candidate_name"]
            and isinstance(generation, dict) and generation.get("method") in METHODS):
        raise ValueError("first pass needs exact owner, original, method and candidate")
    if source["kind"] == "catalog_canonical" and owner["kind"] not in {"player", "event"}:
        raise ValueError("canonical source must belong to player or event")
    if source["kind"] == "raw_event_literal" and owner["kind"] != "raw_event":
        raise ValueError("raw literal source needs raw event owner")
    if source["kind"] == "raw_player_literal":
        from katrain.web.kifu.name_parse import parse_player
        parsed = parse_player(source["text"], None)
        if (owner["kind"] != "raw_player" or parsed.category != "readable_unlinked" or not parsed.name
                or source.get("parsed_name") != parsed.name
                or source.get("embedded_rank") != parsed.embedded_rank
                or not _HASH.fullmatch(str(record.get("raw_display_scope_sha256", "")))):
            raise ValueError("raw player needs readable literal and signed finite scope")
    elif owner["kind"] == "raw_player":
        raise ValueError("raw player first pass needs its own literal source")
    if source["kind"] == "raw_event_literal":
        from katrain.web.kifu.name_parse import parse_event
        category = parse_event(source["text"], None).category
        if not eligible_record_label(record, category) and category not in READABLE_RAW_CATEGORIES:
            raise ValueError("first pass cannot rename a program, generic, damaged or archive value")
        if (generation.get("submode") == RECORD_LABEL_MODE or "record_label_basis" in source
                or record.get("candidate_name", "").startswith(tuple(
                    template.split("{raw}")[0] for template in RECORD_LABELS.values()))) and not eligible_record_label(
                    record, category):
            raise ValueError("record label needs exact source token, category, method and native template")
    elif generation.get("submode") == RECORD_LABEL_MODE or "record_label_basis" in source:
        raise ValueError("record label is only for raw event literal metadata")
    if source["kind"] == "existing_locale":
        if not (source.get("lang") in LANGUAGES and source["lang"] != record["lang"]
                and type(source.get("name_id")) is int and source["name_id"] > 0
                and _HASH.fullmatch(str(source.get("name_preimage_sha256", "")))
                and _HASH.fullmatch(str(source.get("evidence_preimage_sha256", "")))):
            raise ValueError("existing locale needs exact same-owner name and evidence")
    retained = source.get("parsed_name") if source["kind"] == "raw_player_literal" else source["text"]
    if generation["method"] == "retain_original" and record["candidate_name"] != retained:
        raise ValueError("retained original differs from output")
    if generation.get("reading_basis") not in {None, "model_inferred", "existing_locale"}:
        raise ValueError("first pass cannot claim sourced reading")
    if owner["kind"] == "raw_event":
        scope = record.get("raw_scope")
        if not (isinstance(scope, dict) and scope.get("raw_value") == source["text"]
                and isinstance(scope.get("slots"), list) and scope["slots"]):
            raise ValueError("raw title needs finite current occurrence scope")
        slots = scope["slots"]
        if (slots != sorted(slots, key=lambda item: (item.get("album_id", 0), item.get("slot", "")))
                or len({(item.get("album_id"), item.get("slot")) for item in slots}) != len(slots)
                or any(not isinstance(item, dict) or type(item.get("album_id")) is not int
                       or item.get("slot") not in {"event", "selected_event"}
                       or item.get("raw_value") != source["text"]
                       or item.get("event_id") is not None and type(item.get("event_id")) is not int
                       or not isinstance(item.get("approved"), bool)
                       for item in slots)):
            raise ValueError("raw title slots must be sorted exact current occurrences")
    elif "raw_scope" in record:
        raise ValueError("entity name cannot claim raw scope")
    return record


def raw_scope_rows(conn, raw):
    """Capture all current direct and selected occurrences of one literal raw title."""
    return raw_scope_rows_many(conn, {raw})[raw]


def raw_scope_rows_many(conn, raws):
    """Capture a page or batch of literal scopes with shared database reads."""
    from sqlalchemy import bindparam, select, text
    from katrain.web.core.models_db import KifuAlbumEventSelection
    from katrain.web.kifu.event_selection import verified_selection_rows

    raws = set(raws)
    if not raws:
        return {}
    physical = ("SELECT id, event, event_id, event_edition_id, duplicate_of_id, list_hidden_reason, source_path "
                "FROM kifu_albums WHERE {column} IN :values")
    direct = conn.execute(text(physical.format(column="event")).bindparams(
        bindparam("values", expanding=True)), {"values": sorted(raws)}).mappings().all()
    selected = conn.execute(select(KifuAlbumEventSelection.__table__).where(
        KifuAlbumEventSelection.selected_raw.in_(raws))).mappings().all()
    proofs = verified_selection_rows(conn, selected) if selected else {}
    selected_ids = [row["album_id"] for row in selected]
    selected_albums = {row["id"]: row for row in conn.execute(text(
        "SELECT id, event, event_id, event_edition_id, duplicate_of_id, list_hidden_reason, source_path "
        "FROM kifu_albums WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
        {"ids": selected_ids}).mappings()} if selected_ids else {}
    result = {raw: [] for raw in raws}
    for row in direct:
        result[row["event"]].append({"album_id": row["id"], "slot": "event", "raw_value": row["event"],
                       "event_id": row["event_id"], "event_edition_id": row["event_edition_id"],
                       "duplicate_of_id": row["duplicate_of_id"],
                       "list_hidden_reason": row["list_hidden_reason"], "source_path": row["source_path"],
                       "approved": True})
    for selection in selected:
        row = selected_albums.get(selection["album_id"])
        if row is None:
            continue
        proof = proofs.get(selection["album_id"])
        raw = selection["selected_raw"]
        result[raw].append({"album_id": row["id"], "slot": "selected_event", "raw_value": raw,
                       "event_id": proof["event_id"] if proof else selection["event_id"],
                       "event_edition_id": row["event_edition_id"],
                       "duplicate_of_id": row["duplicate_of_id"],
                       "list_hidden_reason": row["list_hidden_reason"], "source_path": row["source_path"],
                       "approved": proof is not None})
    return {raw: sorted(rows, key=lambda item: (item["album_id"], item["slot"]))
            for raw, rows in result.items()}


def raw_player_scope_live(conn, scope):
    """Check signed raw-player members against physical public, unlinked slots."""
    from sqlalchemy import bindparam, text
    from katrain.web.kifu.name_raw_player_scope import CONTEXT_FIELDS, PreparedRawPlayerScope, prepare_raw_player_scope

    try:
        prepared = scope if isinstance(scope, PreparedRawPlayerScope) else prepare_raw_player_scope(scope)
    except (ValueError, KeyError, TypeError):
        return False
    ids = sorted({album_id for album_id, _ in prepared.members})
    columns = ", ".join(("id", *CONTEXT_FIELDS, "list_hidden_reason"))
    rows = conn.execute(text(f"SELECT {columns} FROM kifu_albums WHERE id IN :ids").bindparams(
        bindparam("ids", expanding=True)), {"ids": ids}).mappings()
    live = {row["id"]: row for row in rows}
    return all(
        (row := live.get(album_id)) is not None
        and row["duplicate_of_id"] is None and row["list_hidden_reason"] is None
        and row[f"{slot}_player_id"] is None
        and {field: row[field] for field in CONTEXT_FIELDS} == context
        for (album_id, slot), context in prepared.members.items()
    )


def shared_display_candidate(row, scope=None, *, require_approval=True):
    """A raw literal may share display text without asserting player identity."""
    from katrain.web.kifu.name_candidates import canonical_sha256
    from katrain.web.kifu.name_parse import parse_player
    from katrain.web.kifu.name_raw_player_scope import prepare_raw_player_scope

    if (not isinstance(row, dict) or not isinstance(row.get("owner"), dict)
            or row["owner"].get("kind") != "raw_player"
            or row.get("decision_kind") != "generated"
            or row.get("generation_rule_version") != VERSION
            or row.get("review_status") not in ({"approved"} if require_approval else {"pending", "approved"})
            or row.get("collision_decision") != "shared_display"):
        return False
    raw = row.get("raw_value")
    parsed = parse_player(raw, None) if isinstance(raw, str) else None
    if (parsed is None or parsed.category != "readable_unlinked" or not parsed.name
            or row.get("collision_basis") != {
                "kind": "literal_translation", "source_text": raw,
                "parsed_name": parsed.name, "provenance": "signed_raw_player_literal",
            }):
        return False
    if scope is None:
        return True
    try:
        prepared = prepare_raw_player_scope(scope)
    except (ValueError, KeyError, TypeError, AttributeError):
        return False
    return (bool(prepared.members) and prepared.raw_value == raw
            and canonical_sha256(scope) == row.get("raw_display_scope_sha256"))


def shared_event_display_candidate(row, research, *, require_approval=True):
    """Permit a shared raw title as text only, with its own finite literal source."""
    if (not isinstance(row, dict) or not isinstance(research, dict)
            or row.get("owner", {}).get("kind") != "raw_event"
            or row.get("decision_kind") != "generated"
            or row.get("generation_rule_version") != VERSION
            or row.get("review_status") not in ({"approved"} if require_approval else {"pending", "approved"})
            or row.get("collision_decision") != "shared_display"):
        return False
    raw = row.get("raw_value")
    source = research.get("source_input")
    scope = research.get("raw_scope")
    if (not isinstance(raw, str) or not isinstance(source, dict) or not isinstance(scope, dict)
            or source.get("kind") != "raw_event_literal" or source.get("text") != raw
            or research.get("generation", {}).get("submode") == RECORD_LABEL_MODE
            or research.get("candidate_name") != row.get("display_name")
            or scope.get("raw_value") != raw or not isinstance(scope.get("slots"), list)
            or not scope["slots"] or row.get("collision_basis") != {
                "kind": "literal_title_translation", "source_text": raw,
                "provenance": "signed_raw_event_literal",
            }):
        return False
    return not (Counter(re.findall(r"\d+", raw)) - Counter(re.findall(r"\d+", row["display_name"])))


def validate_candidate(row, research):
    from katrain.web.kifu.name_parse import parse_event
    if not (row.get("decision_kind") == "generated" and row.get("generation_rule_version") == VERSION
            and research.get("source_basis") == VERSION
            and row.get("display_name") == research.get("candidate_name")):
        raise ValueError("first-pass generated candidate markers or output differ")
    if row["owner"]["kind"] == "raw_event" and row.get("raw_value") != research["source_input"]["text"]:
        raise ValueError("first-pass raw candidate differs from exact original")
    record_mode = research["generation"].get("submode") == RECORD_LABEL_MODE
    if record_mode != (row.get("record_label_mode") == RECORD_LABEL_MODE) or (
            "record_label_mode" in row and not record_mode):
        raise ValueError("record label candidate marker differs from signed research")
    if record_mode and not eligible_record_label(
            research, parse_event(research["source_input"]["text"], None).category):
        raise ValueError("record label candidate differs from exact template")
    if row["owner"]["kind"] == "raw_player" and (row.get("raw_value") != research["source_input"]["text"]
            or row.get("raw_display_scope_sha256") != research.get("raw_display_scope_sha256")):
        raise ValueError("first-pass raw player differs from literal or signed scope")
    if ("collision_decision" in row or "collision_basis" in row) and not (
            shared_display_candidate(row, require_approval=False)
            or shared_event_display_candidate(row, research, require_approval=False)):
        raise ValueError("first-pass shared display needs its exact raw literal basis")
    if row.get("review_status") == "pending":
        if "generated_review" in row:
            raise ValueError("pending first pass cannot carry approval")
        return row
    if row.get("review_status") != "approved" or row.get("review_conclusion") != "approved_first_pass_display_and_source":
        raise ValueError("first pass needs explicit approval")
    review = row.get("generated_review")
    if not (isinstance(review, dict) and review.get("decision") == "approve_generated_first_pass"
            and all(review.get(key) == row.get(key) for key in (
                "owner", "lang", "display_name", "research_sha256", "reviewer_id",
                "reviewer_model", "reviewed_at"))):
        raise ValueError("first pass needs exact independent display/source approval")
    return row


def persisted_eligible(name, evidence, owner_kind, owner, batch, changes,
                       source_names=None, source_evidence=None, batch_members=None):
    """A signed, applied creation with unchanged live name, evidence and source."""
    from katrain.web.kifu.name_candidates import canonical_sha256

    payload = evidence.get("research_payload")
    if not isinstance(payload, dict):
        return False
    candidate, research, proof = (payload.get(key) for key in ("candidate", "research", "first_pass"))
    if not all(isinstance(value, dict) for value in (candidate, research, proof, batch, owner)):
        return False
    try:
        validate_research(research)
        validate_candidate(candidate, research)
    except (ValueError, KeyError, TypeError):
        return False
    artifact = batch.get("reviewed_artifact")
    bundle = artifact.get("bundle") if isinstance(artifact, dict) else None
    candidate_hash = canonical_sha256(candidate)
    research_hash = canonical_sha256(research)
    if (batch.get("status") != "applied" or not isinstance(bundle, dict)
            or batch_members is None or candidate_hash not in batch_members[0]
            or research_hash not in batch_members[1]
            or proof != {"batch_id": batch["id"], "candidate_sha256": canonical_sha256(candidate),
                         "research_sha256": research_hash, "verification_level": LEVEL,
                         "raw_scope_sha256": canonical_sha256(research["raw_scope"])
                         if owner_kind == "raw_event" else research.get("raw_display_scope_sha256")
                         if owner_kind == "raw_player" else None}):
        return False
    owner_id = name.get({"player": "player_id", "event": "event_id", "raw_event": "raw_event_id",
                         "raw_player": "raw_player_id"}[owner_kind])
    if (candidate.get("owner") != {"kind": owner_kind, "id": owner_id}
            or name.get("lang") != candidate.get("lang")
            or name.get("display_name") != candidate.get("display_name")
            or name.get("decision_kind") != evidence.get("decision_kind") != "generated"
            or name.get("generation_rule_version") != evidence.get("generation_rule_version") != VERSION
            or name.get("revision") != evidence.get("revision")
            or name.get("evidence_id") != evidence.get("id")
            or evidence.get("candidate_name") != name.get("display_name")
            or evidence.get("review_status") != "approved"
            or canonical_sha256(owner) != research["source_input"]["owner_preimage_sha256"]):
        return False
    source = research["source_input"]
    if source["kind"] == "catalog_canonical" and owner.get("canonical_name") != source["text"]:
        return False
    if source["kind"] == "raw_event_literal" and owner.get("raw_value") != source["text"]:
        return False
    if source["kind"] == "raw_event_literal":
        record_mode = research["generation"].get("submode") == RECORD_LABEL_MODE
        if record_mode and not eligible_record_label(research, owner.get("category")):
            return False
        if not record_mode and owner.get("category") not in READABLE_RAW_CATEGORIES:
            return False
    if source["kind"] == "raw_player_literal" and (owner.get("raw_value") != source["text"]
            or owner.get("category") != "readable_unlinked"
            or owner.get("review_status") not in {"pending", "approved"}):
        return False
    if source["kind"] == "existing_locale":
        existing = (source_names or {}).get(source["name_id"])
        existing_evidence = (source_evidence or {}).get(existing.get("evidence_id")) if existing else None
        if (not existing or not existing_evidence or existing.get("display_name") != source["text"]
                or existing.get("lang") != source["lang"]
                or existing.get({"player": "player_id", "event": "event_id", "raw_event": "raw_event_id",
                                 "raw_player": "raw_player_id"}[owner_kind]) != owner_id
                or existing.get("status") != "verified"
                or existing_evidence.get("review_status") != "approved"
                or canonical_sha256(existing) != source["name_preimage_sha256"]
                or canonical_sha256(existing_evidence) != source["evidence_preimage_sha256"]):
            return False
    evidence_change = changes.get(("kifu_name_research_evidence", evidence["id"]))
    name_change = changes.get(({
        "player": "kifu_player_names", "event": "kifu_event_names", "raw_event": "kifu_raw_event_names",
        "raw_player": "kifu_raw_player_names"
    }[owner_kind], name["id"]))
    return (isinstance(evidence_change, dict) and isinstance(name_change, dict)
            and evidence_change.get("before_image") is None
            and evidence_change.get("after_image") == evidence
            and name_change.get("after_image") == name
            and candidate.get("name_preimage_sha256") == (
                canonical_sha256(name_change["before_image"])
                if name_change["before_image"] is not None else None))
