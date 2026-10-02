"""Offline validation of reviewed kifu display-name decisions.

This module never translates or approves a name. It verifies an explicit,
finite candidate bundle against a pinned inventory and research records.
Raw-value table IDs are not present in inventory format 2: the importer must
also check that each raw ID resolves to the declared exact spelling in DB.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from calendar import monthrange
from datetime import date, datetime
import hashlib
import json
import re

from katrain.web.kifu.name_evidence import (
    EvidenceError,
    OWNER_KINDS,
    registry_sha256,
    owner_key as evidence_owner_key,
    validate_research_record,
    validate_transliteration_anchor,
)
from katrain.web.kifu.name_parse import parse_event, parse_player
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_inventory import SELECTION_COLUMNS, SELECTION_COLUMNS_V4, _hash_row
from katrain.web.kifu.name_composition import (
    CompositionError, HONINBO_RAWS, validate_composition, validate_composed_candidate,
)
from katrain.web.kifu.name_transliteration import validate_transliteration, validate_transliterated_candidate
from katrain.web.kifu.name_raw_player_scope import CONTEXT_FIELDS, validate_raw_player_scope


LANGUAGES = frozenset(("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"))
DECISION_KINDS = frozenset(
    (
        "conventional",
        "generated",
        "generic",
        "hidden",
        "placeholder",
        "error",
        "corrected",
        "composed",
        "transliterated",
    )
)
_HASH = re.compile(r"^[0-9a-f]{64}$")
_RANK_SUFFIX = re.compile(r"(?:[一二三四五六七八九十初]|[1-9]\d?)\s*(?:段|級|级|dan|kyu|[dkp])\Z", re.I)
_RESULT = re.compile(r"(?:中盘|中盤|目半|resign|resignation|points?)\s*(?:胜|勝|win|won)?", re.I)
_UNSAFE = re.compile(r"[\[\]\x00-\x1f]")
_MAX_NAME = {"player": 512, "event": 256, "raw_player": 1024, "raw_event": 4096}
CLASSIFICATION_RULE_VERSION = "classification-v1"
_SELECTION_RULE_VERSION = "19x19-gnugo-second-gn-v1"
_SELECTION_IMAGE_KEYS = {"album_id", "event_id", "batch_id", "selected_raw", "sgf_sha256",
                         "property_name", "property_index", "status", "rule_version",
                         "reviewer_id", "reviewed_at", "created_at"}
_CLASSIFICATION_TEMPLATES = {
    "en": {"placeholder": "Unknown player", "player_error": "Player name unavailable",
           "event_error": "Event data unavailable", "rank_event": "Rank Tournament",
           "individual_event": "Individual Tournament"},
    "cn": {"placeholder": "未知棋手", "player_error": "棋手姓名有误",
           "event_error": "赛事资料有误", "rank_event": "段位赛", "individual_event": "个人赛"},
    "tw": {"placeholder": "未知棋手", "player_error": "棋手姓名有誤",
           "event_error": "賽事資料有誤", "rank_event": "段位賽", "individual_event": "個人賽"},
    "jp": {"placeholder": "不明な棋士", "player_error": "棋士名のデータに誤りがあります",
           "event_error": "棋戦データに誤りがあります", "rank_event": "段位戦", "individual_event": "個人戦"},
    "ko": {"placeholder": "알 수 없는 기사", "player_error": "기사 이름 데이터 오류",
           "event_error": "대회 데이터 오류", "rank_event": "단위 대회", "individual_event": "개인전"},
    "de": {"placeholder": "Unbekannter Spieler", "player_error": "Spielername fehlerhaft",
           "event_error": "Turnierdaten fehlerhaft", "rank_event": "Rangturnier",
           "individual_event": "Einzelturnier"},
    "es": {"placeholder": "Jugador desconocido", "player_error": "Nombre del jugador incorrecto",
           "event_error": "Datos del torneo incorrectos", "rank_event": "Torneo de grados",
           "individual_event": "Torneo individual"},
    "fr": {"placeholder": "Joueur inconnu", "player_error": "Nom du joueur invalide",
           "event_error": "Données du tournoi invalides", "rank_event": "Tournoi de niveaux",
           "individual_event": "Tournoi individuel"},
    "ru": {"placeholder": "Неизвестный игрок", "player_error": "Ошибка в имени игрока",
           "event_error": "Ошибка в данных турнира", "rank_event": "Турнир разрядов",
           "individual_event": "Личный турнир"},
    "tr": {"placeholder": "Bilinmeyen oyuncu", "player_error": "Oyuncu adında hata",
           "event_error": "Turnuva verilerinde hata", "rank_event": "Seviye turnuvası",
           "individual_event": "Bireysel turnuva"},
    "ua": {"placeholder": "Невідомий гравець", "player_error": "Помилка в імені гравця",
           "event_error": "Помилка в даних турніру", "rank_event": "Турнір розрядів",
           "individual_event": "Особистий турнір"},
}
_SCRIPT = {
    "en": re.compile(r"[A-Za-z]"), "de": re.compile(r"[A-Za-zÀ-ÿ]"),
    "es": re.compile(r"[A-Za-zÀ-ÿ]"), "fr": re.compile(r"[A-Za-zÀ-ÿ]"),
    "tr": re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü]"),
    "cn": re.compile(r"[\u3400-\u9fff]"), "tw": re.compile(r"[\u3400-\u9fff]"),
    "jp": re.compile(r"[\u3400-\u9fff\u3040-\u30ff]"),
    "ko": re.compile(r"[\u3400-\u9fff\uac00-\ud7af]"),
    "ru": re.compile(r"[\u0400-\u052f]"), "ua": re.compile(r"[\u0400-\u052f]"),
}
_RAW_CATEGORY_DECISIONS = {
    "raw_player": {
        "placeholder": {"placeholder"},
        "corrupt_pending": {"error", "corrected"},
        "readable_unlinked": {"conventional", "generated", "transliterated"},
    },
    "raw_event": {
        "empty": {"hidden"},
        "program_source_label": {"hidden"},
        "generic_event_description": {"generic"},
        "corrupt_data": {"error", "corrected"},
        "formal_event_candidate": {"conventional", "generated", "transliterated"},
        "game_description": {"conventional", "generated", "transliterated"},
        "unclassified_pending": {"conventional", "generated", "composed", "transliterated"},
    },
}


class CandidateError(ValueError):
    """A proposed decision cannot be approved from its supplied evidence."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CandidateError(message)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _time(value: object) -> datetime | None:
    if not _text(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _iso_date(value: object) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _played_date_bounds(value: object) -> tuple[date, date] | None:
    """Return the full possible span of a supported raw SGF date."""
    if not isinstance(value, str) or len(value) > 32:
        return None
    if re.fullmatch(r"\d{4}", value):
        try:
            year = int(value)
            return date(year, 1, 1), date(year, 12, 31)
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            year, month = map(int, value.split("-"))
            return date(year, month, 1), date(year, month, monthrange(year, month)[1])
        except ValueError:
            return None
    parts = value.split(",")
    first = _iso_date(parts[0])
    if first is None:
        return None
    days = [first]
    anchor = first
    for part in parts[1:]:
        if re.fullmatch(r"\d{2}", part):
            try:
                days.append(date(anchor.year, anchor.month, int(part)))
            except ValueError:
                return None
        else:
            parsed = _iso_date(part)
            if parsed is None:
                return None
            days.append(parsed)
            anchor = parsed
    return min(days), max(days)


def canonical_sha256(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def classification_template_sha256(lang: str) -> str:
    _require(lang in LANGUAGES, "unknown classification template language")
    return canonical_sha256({"version": CLASSIFICATION_RULE_VERSION, "lang": lang,
                             "templates": _CLASSIFICATION_TEMPLATES[lang]})


def _owner_key(owner: object, lang: object) -> str:
    _require(isinstance(lang, str) and lang in LANGUAGES, "one of the eleven product languages is required")
    try:
        return evidence_owner_key(owner, lang)
    except EvidenceError as exc:
        raise CandidateError(str(exc)) from exc


def _owner_token(owner: dict) -> str:
    return _owner_key(owner, "en").rsplit(":", 1)[0]


def _selection_rows(inventory: dict) -> list[list]:
    if inventory.get("inventory_format") == 2:
        _require("event_selection" not in inventory, "v2 inventory cannot include event selections")
        return []
    version = inventory.get("inventory_format")
    _require(version in {3, 4}, "inventory format 2, 3 or 4 required")
    if version == 4:
        _require(bool(_HASH.fullmatch(str(inventory.get("base_sha256", "")))),
                 "v4 inventory base SHA-256 required")
    selection = inventory.get("event_selection")
    selection_version = 2 if version == 4 else 1
    columns = SELECTION_COLUMNS_V4 if version == 4 else SELECTION_COLUMNS
    _require(isinstance(selection, dict) and selection.get("selection_format") == selection_version
             and selection.get("columns") == list(columns)
             and isinstance(selection.get("rows"), list), "event selection supplement is incomplete")
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (selection_version, columns))
    previous_id = -1
    for row in selection["rows"]:
        _require(isinstance(row, list) and len(row) == len(columns),
                 "event selection row is malformed")
        album_id, raw, sgf_sha, reviewer, reviewed_at, batch_id, bundle_sha = row[:7]
        _require(type(album_id) is int and album_id > previous_id and isinstance(raw, str) and bool(raw.strip())
                 and isinstance(sgf_sha, str) and _HASH.fullmatch(sgf_sha)
                 and isinstance(reviewer, str) and bool(reviewer)
                 and isinstance(reviewed_at, str) and bool(reviewed_at)
                 and type(batch_id) is int and batch_id > 0
                 and isinstance(bundle_sha, str) and _HASH.fullmatch(bundle_sha),
                 "event selection row is invalid or unsorted")
        if version == 4:
            event_id, image, image_sha, name_batch_id, proof_sha = row[7:]
            _require(event_id is None or (type(event_id) is int and event_id > 0),
                     "event selection target ID invalid")
            _require(isinstance(image, dict) and set(image) == _SELECTION_IMAGE_KEYS
                     and image.get("album_id") == album_id and image.get("event_id") is None
                     and image.get("batch_id") == batch_id and image.get("selected_raw") == raw
                     and image.get("sgf_sha256") == sgf_sha and image.get("reviewer_id") == reviewer
                     and image.get("reviewed_at") == reviewed_at and image.get("property_name") == "GN"
                     and image.get("property_index") == 1 and image.get("status") == "approved"
                     and image.get("rule_version") == _SELECTION_RULE_VERSION
                     and _text(image.get("created_at"))
                     and image_sha == canonical_sha256(image),
                     "event selection original after-image or hash invalid")
            _require((event_id is None and name_batch_id is None and proof_sha is None) or
                     (event_id is not None and type(name_batch_id) is int and name_batch_id > 0
                      and isinstance(proof_sha, str) and _HASH.fullmatch(proof_sha)),
                     "event selection name proof invalid")
        previous_id = album_id
        _hash_row(digest, b"E", row)
    _require(selection.get("sha256") == digest.hexdigest(), "event selection supplement hash mismatch")
    return selection["rows"]


def _inventory_values(inventory: dict) -> dict[str, set]:
    _require(inventory.get("inventory_format") in {2, 3, 4}
             and bool(_HASH.fullmatch(str(inventory.get("sha256", "")))),
             "inventory format 2, 3 or 4 and SHA-256 required")
    columns = inventory.get("association_columns")
    rows = inventory.get("album_associations")
    required = {"player_black", "player_white", "event", "black_player_id", "white_player_id", "event_id"}
    _require(isinstance(columns, list) and required.issubset(columns) and isinstance(rows, list),
             "inventory associations are incomplete")
    values = {kind: set() for kind in OWNER_KINDS}
    album_ids = set()
    for row in rows:
        _require(isinstance(row, list) and len(row) == len(columns), "inventory association is malformed")
        album = dict(zip(columns, row))
        album_ids.add(album["id"])
        values["raw_player"].update((album["player_black"], album["player_white"]))
        values["raw_event"].add(album["event"])
        values["player"].update((album["black_player_id"], album["white_player_id"]))
        values["event"].add(album["event_id"])
    for row in _selection_rows(inventory):
        album_id, raw = row[:2]
        _require(album_id in album_ids,
                 "event selection album absent from inventory")
        values["raw_event"].add(raw)
        if inventory["inventory_format"] == 4:
            values["event"].add(row[7])
    return values


def _check_owner_in_inventory(row: dict, values: dict[str, set], *,
                              declarations: dict[str, dict] | None = None,
                              link_targets: set[str] | None = None) -> None:
    owner = row["owner"]
    declaration = declarations.get(_owner_token(owner)) if declarations is not None else None
    if declarations is not None:
        _require(declaration is not None, "owner missing from finite v2 manifest")
        pinned = declaration.get("create") or declaration.get("preimage")
        _require(isinstance(pinned, dict), "owner manifest preimage/create is missing")
    if owner["kind"].startswith("raw_"):
        _require("raw_value" in row and isinstance(row["raw_value"], str),
                 "raw owner spelling must be text")
        _require(row["raw_value"] in values[owner["kind"]],
                 "raw owner needs exact spelling present in pinned inventory")
        if declaration is not None:
            _require(pinned.get("raw_value") == row["raw_value"], "raw spelling differs from owner manifest")
    else:
        linked = owner.get("id") in values[owner["kind"]] if "id" in owner else False
        _require(linked or (link_targets is not None and _owner_token(owner) in link_targets),
                 "entity ID/ref absent from pinned inventory and approved links")
        _require("raw_value" not in row, "entity candidate must not claim a raw spelling")


def _check_signature(row: dict) -> None:
    _require(_text(row.get("producer_id")) and _text(row.get("producer_model")) and _time(row.get("produced_at")),
             "candidate needs actual producer ID, model and time")
    status = row.get("review_status")
    _require(status in {"pending", "approved", "rejected"}, "review status invalid")
    reviewer = row.get("reviewer_id")
    if status == "pending":
        _require(not any(row.get(field) for field in ("reviewer_id", "reviewer_model", "reviewed_at", "review_conclusion")),
                 "pending candidate cannot carry a review signature")
    else:
        _require(_text(reviewer) and reviewer != row["producer_id"] and _text(row.get("reviewer_model"))
                 and _text(row.get("review_conclusion")) and _time(row.get("reviewed_at")),
                 "review must be signed by an independent agent with its actual model and conclusion")
        _require(_time(row["reviewed_at"]) >= _time(row["produced_at"]), "review time precedes candidate")


def _research_for(row: dict, research: dict | None, registry: dict) -> dict:
    _require(isinstance(research, dict), "research record required")
    _require(row.get("research_sha256") == canonical_sha256(research), "research record hash mismatch")
    try:
        checked = validate_research_record(research, registry)
    except EvidenceError as exc:
        raise CandidateError(f"invalid research: {exc}") from exc
    _require(checked["owner"] == row["owner"] and checked["lang"] == row["lang"],
             "research owner/language differs from candidate")
    _require(checked["producer_id"] == row["producer_id"] and checked["producer_model"] == row["producer_model"],
             "candidate producer differs from research producer")
    return checked


def _validate_candidate(
    row: dict,
    research: dict | None,
    registry: dict,
    inventory_values: dict,
    *,
    declarations: dict[str, dict] | None = None,
    link_targets: set[str] | None = None,
    composition_context: tuple[dict, dict, dict, dict] | None = None,
    transliteration_context: dict | None = None,
) -> dict:
    _require(isinstance(row, dict), "candidate must be an object")
    _owner_key(row.get("owner"), row.get("lang"))
    _check_owner_in_inventory(row, inventory_values, declarations=declarations, link_targets=link_targets)
    _check_signature(row)
    decision = row.get("decision_kind")
    _require(isinstance(decision, str) and decision in DECISION_KINDS, "decision kind invalid")
    display = row.get("display_name")
    _require(isinstance(display, str) and len(display) <= _MAX_NAME[row["owner"]["kind"]]
             and not _UNSAFE.search(display),
             "display name has invalid or unsafe characters")
    _require(_text(row.get("generation_rule_version")), "generation/classification rule version required")
    if decision != "hidden":
        _require(_text(display), "non-hidden decision needs a display name")
    else:
        _require(display == "", "hidden decision must have empty display")

    if decision == "transliterated":
        _require(research is None, "transliterated candidate uses dedicated original/reading evidence")
        try:
            validate_transliterated_candidate(row, transliteration_context)
        except EvidenceError as exc:
            raise CandidateError(str(exc)) from exc
    elif decision == "composed":
        _require(row["owner"]["kind"] == "raw_event" and parse_event(row["raw_value"], None).category == "unclassified_pending",
                 "composed name requires a pending raw event, never the Oteai branch")
        _require(research is None and composition_context is not None,
                 "composed candidate requires dedicated approved composition evidence")
        raw_by_value, rule_by_lang, base_by_lang, scope = composition_context
        raw = raw_by_value.get(row["raw_value"])
        rule = rule_by_lang.get(row["lang"])
        base = base_by_lang.get(row["lang"])
        _require(raw is not None and rule is not None and base is not None,
                 "composed candidate lacks exact raw, locale rule or approved base")
        try:
            validate_composed_candidate(row, raw, rule, base, scope)
        except CompositionError as exc:
            raise CandidateError(str(exc)) from exc
    elif decision in {"conventional", "generated", "corrected"}:
        checked = _research_for(row, research, registry)
        if row["review_status"] == "approved":
            captures = []
            for source_check in checked["source_checks"]:
                captures.append(source_check["fetched_at"])
                for nested_key in ("identity_corroboration", "label_evidence"):
                    nested = source_check.get(nested_key)
                    if isinstance(nested, dict):
                        captures.append(nested["fetched_at"])
            _require(all(_time(row["reviewed_at"]) >= _time(captured_at) for captured_at in captures),
                     "candidate approval predates a source capture")
        if decision == "generated":
            _require(checked["scope_status"] == "not_found_in_scope", "generated name needs complete negative search")
            _require(_text(checked.get("reading")) and _text(checked.get("reading_basis_url")),
                     "generated name needs sourced original reading")
            if row["review_status"] == "approved":
                review = row.get("generated_review")
                _require(isinstance(review, dict)
                         and row.get("review_conclusion") == "approved_generated_display_and_rule"
                         and review.get("decision") == "approve_generated"
                         and review.get("display_name") == display
                         and review.get("owner") == row["owner"] and review.get("lang") == row["lang"]
                         and review.get("generation_rule_version") == row["generation_rule_version"]
                         and review.get("research_sha256") == row["research_sha256"]
                         and review.get("original_name") == checked["original_name"]
                         and review.get("reading") == checked["reading"]
                         and review.get("reading_basis_url") == checked["reading_basis_url"]
                         and review.get("reviewer_id") == row["reviewer_id"]
                         and review.get("reviewer_model") == row["reviewer_model"]
                         and review.get("reviewed_at") == row["reviewed_at"]
                         and _text(review.get("reason")),
                         "approved generated name needs an affirmative exact generated review")
            closure = checked.get("negative_closure")
            if closure and row["review_status"] == "approved":
                _require(_time(row["reviewed_at"]) > _time(closure["reviewed_at"]),
                         "generated name review must follow its negative closure")
            _require(row["generation_rule_version"] != "none", "generated name needs a named conversion rule")
            _require(bool(_SCRIPT[row["lang"]].search(display)), "generated name lacks target-language script")
        else:
            _require(checked["scope_status"] == "found" and display == checked["candidate_name"],
                     "adopted name must match found target-language evidence")
            sources = {source["id"]: source for source in registry["sources"]}
            _require(any(check["status"] == "found" and check["candidate_name"] == display
                         and sources[check["source_id"]]["tier"] in {
                             "official", "language_go", "wikipedia_article", "encyclopedia"
                         }
                         for check in checked["source_checks"]),
                     "discovery tier alone cannot attest a final conventional name")
            conflicts = {(item["source_id"], item["candidate_name"])
                         for item in checked["source_checks"]
                         if item["status"] == "found" and item["candidate_name"] != display}
            exclusions = row.get("excluded_candidates", [])
            _require(isinstance(exclusions, list), "conflicting candidates need exclusion records")
            explained = {(item.get("source_id"), item.get("candidate_name")) for item in exclusions
                         if isinstance(item, dict) and _text(item.get("reason"))}
            _require(conflicts <= explained, "conflicting source names need documented exclusion reasons")
            if conflicts:
                adjudication = row.get("conflict_adjudication")
                _require(isinstance(adjudication, dict), "conflicting names need documented Sol adjudication")
                if row["review_status"] == "pending":
                    _require(row["producer_model"] == "gpt-6-sol"
                             and adjudication.get("agent_id") == row["producer_id"]
                             and adjudication.get("model") == "gpt-6-sol",
                             "pending conflicting names need their actual Sol producer decision")
                else:
                    _require(row.get("reviewer_model") in {"gpt-6-sol", "gpt-6-astra"}
                             and adjudication.get("model") == "gpt-6-sol"
                             and adjudication.get("agent_id") in {row["producer_id"], row.get("reviewer_id")}
                             and adjudication.get("model") == (
                                 row["producer_model"] if adjudication.get("agent_id") == row["producer_id"]
                                 else row.get("reviewer_model")),
                             "conflicting names require independent Sol or Astra reviewer and gpt-6-sol adjudication")
                _require(_time(adjudication.get("decided_at")) and _text(adjudication.get("rationale")),
                         "conflicting names need documented Sol decision time and rationale")
                if row["review_status"] != "pending":
                    _require(_time(adjudication["decided_at"]) <= _time(row["reviewed_at"]),
                             "conflicting names need gpt-6-sol decision before reviewer approval")
                urls = adjudication.get("source_urls")
                found_urls = {item["url"] for item in checked["source_checks"] if item["status"] == "found"}
                _require(isinstance(urls, list) and bool(urls)
                         and all(isinstance(url, str) and url.startswith("https://") for url in urls)
                         and found_urls <= set(urls),
                         "conflicting names need exact attested source URLs")
                _require(all(_time(adjudication["decided_at"]) >= _time(item["fetched_at"])
                             for item in checked["source_checks"] if item["url"] in urls),
                         "conflict adjudication predates a cited source capture")
        if decision == "corrected":
            _require(row["owner"]["kind"] in {"raw_player", "raw_event"}, "correction needs raw owner")
            raw = row["raw_value"]
            damaged = parse_player(raw, None).category == "corrupt_pending" if row["owner"]["kind"] == "raw_player" else parse_event(raw, None).category == "corrupt_data"
            _require(damaged, "correction requires a damaged original value")
    else:
        _require(not row.get("research_sha256") and research is None,
                 "classification decision must not claim unrelated name research")
        kind = row["owner"]["kind"]
        _require(kind in {"raw_player", "raw_event"}, "classification decision needs raw owner")
        raw = row["raw_value"]
        category = parse_player(raw, None).category if kind == "raw_player" else parse_event(raw, None).category
        if decision == "hidden":
            _require(kind == "raw_event" and category in {"empty", "program_source_label"},
                     "only an empty event or program label may be hidden")
        elif decision == "placeholder":
            _require(kind == "raw_player" and category == "placeholder",
                     "placeholder decision requires a placeholder player value")
        elif decision == "generic":
            _require(kind == "raw_event" and category == "generic_event_description",
                     "generic decision requires an explicit generic event, not a real event")
        elif decision == "error":
            _require((kind == "raw_player" and category == "corrupt_pending")
                     or (kind == "raw_event" and category == "corrupt_data"),
                     "error display requires a damaged raw value")
        _require(row["generation_rule_version"] == CLASSIFICATION_RULE_VERSION,
                 "classification decision must bind the reviewed template version")
        template_key = (
            "placeholder" if decision == "placeholder"
            else ("player_error" if kind == "raw_player" else "event_error") if decision == "error"
            else "rank_event" if raw.strip() in {"段位赛", "段位賽"}
            else "individual_event" if decision == "generic"
            else "hidden"
        )
        expected = "" if template_key == "hidden" else _CLASSIFICATION_TEMPLATES[row["lang"]][template_key]
        _require(display == expected, "classification display differs from versioned language template")
        if row["review_status"] == "approved":
            template_review = row.get("template_review")
            _require(isinstance(template_review, dict)
                     and template_review.get("version") == CLASSIFICATION_RULE_VERSION
                     and template_review.get("lang") == row["lang"]
                     and template_review.get("sha256") == classification_template_sha256(row["lang"])
                     and template_review.get("reviewer_id") == row.get("reviewer_id")
                     and template_review.get("reviewer_model") == row.get("reviewer_model")
                     and _time(template_review.get("reviewed_at"))
                     and _time(template_review["reviewed_at"]) <= _time(row["reviewed_at"])
                     and _text(template_review.get("conclusion")),
                     "approved classification needs signed review of exact language template version")
    if row["owner"]["kind"] in {"player", "raw_player"} and decision not in {"error", "placeholder"}:
        _require(not _RANK_SUFFIX.search(display) and not _RESULT.search(display),
                 "player name contains a rank or result")
    if row["owner"]["kind"] == "event" and decision in {"conventional", "generated", "transliterated"}:
        _require(not re.search(r"\b[12]\d{3}\b", display), "event core name contains a year")
    return row


def validate_candidate(row: dict, research: dict | None, registry: dict, inventory: dict) -> dict:
    """Validate a proposed display decision, preserving its review status."""
    return _validate_candidate(row, research, registry, _inventory_values(inventory))


def _occurrence_indexes(associations: dict[int, dict], selection_rows: list[list] = ()) -> tuple[
    dict[str, list[int]], dict[str, list[int]], dict[str, list[list]], dict[str, list[list]]
]:
    """Build global exact-spelling scopes once, retaining black/white slot multiplicity."""
    player_games = defaultdict(set)
    event_games = defaultdict(set)
    player_slots = defaultdict(list)
    event_slots = defaultdict(list)
    for album_id, album in associations.items():
        for slot, field in (("black", "player_black"), ("white", "player_white")):
            raw = album[field]
            player_games[raw].add(album_id)
            player_slots[raw].append([album_id, slot])
        event = album["event"]
        event_games[event].add(album_id)
        event_slots[event].append([album_id, "event"])
    for album_id, raw, *_ in selection_rows:
        event_games[raw].add(album_id)
        event_slots[raw].append([album_id, "selected_event"])
    return ({raw: sorted(ids) for raw, ids in player_games.items()},
            {raw: sorted(ids) for raw, ids in event_games.items()},
            {raw: sorted(slots) for raw, slots in player_slots.items()},
            {raw: sorted(slots) for raw, slots in event_slots.items()})


def identity_scope_sha256(bundle: dict, links: list[dict], declaration: dict) -> str:
    """Hash one exact target/raw scope before its independent approval is issued.

    Approval provenance stays outside the payload; evidence and freeze time are
    pinned so an old approval cannot authorize replacement evidence or members.
    """
    members = []
    v4 = bundle.get("bundle_format") == 4
    for link in links:
        review = link["identity_review"]
        member = {
            "album_id": link["album_id"], "slot": link["slot"],
            "association_sha256": link["association_sha256"],
            "production_sgf_sha256": link.get("production_sgf_sha256"),
            "expected": link["expected"], "target": link["target"],
            "raw_scope_sha256": link["raw_scope_sha256"],
            "corrects_existing": link.get("corrects_existing", False),
            "source_checks": review.get("source_checks"),
            "identity_basis": review.get("identity_basis"),
            "event_period_basis": review.get("event_period_basis"),
            "scope_frozen_at": review.get("scope_frozen_at"),
        }
        if v4:
            member.update(member_type="selected_event", selection_batch_id=link.get("selection_batch_id"),
                          selection_bundle_sha256=link.get("selection_bundle_sha256"),
                          selection_before_image=link.get("selection_before_image"),
                          selection_before_sha256=link.get("selection_before_sha256"),
                          event_period=review.get("event_period"), event_region=review.get("event_region"),
                          event_region_basis=review.get("event_region_basis"))
        members.append(member)
    return canonical_sha256({
        "inventory_sha256": bundle["inventory_sha256"],
        "catalog_sha256": bundle["catalog_sha256"], "rule_version": bundle["rule_version"],
        "target_declaration": declaration,
        "members": sorted(members, key=lambda item: (item["album_id"], item["slot"])),
    })


def _v2_scope(bundle: dict, inventory: dict) -> tuple[dict[str, dict], set[str], list[str]]:
    """Validate finite owner/link declarations without treating a ref as a DB ID."""
    errors = []
    _require(bool(_HASH.fullmatch(str(bundle.get("catalog_sha256", "")))),
             "v2 requires a pinned catalog supplement SHA-256")
    owners = bundle.get("owners")
    links = bundle.get("album_links")
    _require(isinstance(owners, list) and owners and isinstance(links, list),
             "v2 requires finite owners and album links lists")
    _require(bundle.get("owner_set_sha256") == canonical_sha256(owners), "owner set hash mismatch")
    _require(bundle.get("link_set_sha256") == canonical_sha256(links), "album link set hash mismatch")
    columns = inventory["association_columns"]
    associations = {dict(zip(columns, row))["id"]: dict(zip(columns, row))
                    for row in inventory["album_associations"] if len(row) == len(columns)}
    player_games, event_games, player_slots, event_slots = _occurrence_indexes(
        associations, _selection_rows(inventory))
    v4 = bundle["bundle_format"] == 4
    selections = ({row[0]: dict(zip(SELECTION_COLUMNS_V4, row))
                   for row in _selection_rows(inventory)} if v4 else {})
    raw_scope_hashes = {}
    declarations = {}
    for number, declaration in enumerate(owners):
        try:
            _require(isinstance(declaration, dict), "owner declaration must be an object")
            owner = declaration.get("owner")
            token = _owner_token(owner)
            if v4:
                _require(owner["kind"] in {"event", "raw_event"},
                         "v4 writes only event and raw_event names")
            _require(token not in declarations, "duplicate owner declaration")
            is_new = "ref" in owner
            if v4 and owner["kind"] == "raw_event":
                _require(not is_new, "v4 cannot create or mutate a raw field")
            pinned_key = "create" if is_new else "preimage"
            _require(set(declaration) >= {"owner", pinned_key} and
                     ("preimage" not in declaration if is_new else "create" not in declaration),
                     "owner declaration needs exactly one create or preimage")
            pinned = declaration[pinned_key]
            _require(isinstance(pinned, dict), "owner preimage/create must be an object")
            if owner["kind"].startswith("raw_"):
                raw = pinned.get("raw_value")
                _require(isinstance(raw, str), "raw owner needs exact text spelling")
                actual_ids = (player_games if owner["kind"] == "raw_player" else event_games).get(raw, [])
                ids = declaration.get("occurrence_album_ids")
                _require(ids == actual_ids and bool(ids), "raw global occurrences differ from inventory")
                _require(declaration.get("occurrence_sha256") == canonical_sha256(ids),
                         "raw global occurrence hash mismatch")
                if owner["kind"] == "raw_player" and "raw_display_scope" in declaration:
                    contexts = {album_id: {field: album[field] for field in CONTEXT_FIELDS}
                                for album_id, album in associations.items()}
                    slots = {(album_id, slot) for album_id, slot in player_slots.get(raw, [])
                             if contexts[album_id][f"{slot}_player_id"] is None}
                    validate_raw_player_scope(declaration["raw_display_scope"], inventory["sha256"], raw,
                                              slots, contexts)
                if is_new:
                    parsed = parse_player(raw, None) if owner["kind"] == "raw_player" else parse_event(raw, None)
                    _require(pinned.get("category") == parsed.category,
                             "new raw category must match conservative parser; exceptions remain pending")
                if is_new:
                    review = declaration.get("category_review")
                    _require(isinstance(review, dict) and review.get("status") == "approved"
                             and _text(review.get("producer_id")) and _text(review.get("producer_model"))
                             and _time(review.get("produced_at")) and _text(review.get("reviewer_id"))
                             and review["reviewer_id"] != review["producer_id"]
                             and _text(review.get("reviewer_model")) and _time(review.get("reviewed_at"))
                             and _text(review.get("category_basis")),
                             "new raw value needs independent category review")
            else:
                _require(_text(pinned.get("canonical_name")), "identity owner needs canonical name preimage/create")
                if v4:
                    context = declaration.get("identity_context")
                    _require(isinstance(context, dict) and set(context) == {"start_date", "end_date", "region"}
                             and _text(context.get("region"))
                             and _iso_date(context.get("start_date"))
                             and _iso_date(context.get("end_date"))
                             and context["start_date"] <= context["end_date"],
                             "selected_event target needs bounded period and region context")
            declarations[token] = declaration
        except (AttributeError, TypeError, CandidateError, EvidenceError, KeyError) as exc:
            errors.append(f"owner[{number}]: {exc}")
    review_groups = defaultdict(list)
    link_targets = set()
    seen_slots = set()
    required_context = {"player_black", "player_white", "event", "date_played", "round_name",
                        "black_rank", "white_rank", "old_id"}
    slot_ids = {"black": "black_player_id", "white": "white_player_id", "event": "event_id",
                **({"selected_event": "event_id"} if v4 else {})}
    for number, link in enumerate(links):
        try:
            _require(isinstance(link, dict), "link must be an object")
            album_id, slot = link.get("album_id"), link.get("slot")
            _require(type(album_id) is int and album_id in associations and slot in slot_ids,
                     "link album ID/slot absent from inventory")
            if v4:
                _require(slot == "selected_event", "v4 permits only selected_event album links")
                _require(set(link) <= {"album_id", "slot", "association_sha256", "production_sgf_sha256",
                                        "expected", "target", "raw_scope_sha256", "raw_scope_slots",
                                        "identity_review", "selection_batch_id", "selection_bundle_sha256",
                                        "selection_before_image", "selection_before_sha256"},
                         "selected_event link contains unsupported write fields")
            _require((album_id, slot) not in seen_slots, "duplicate album slot link")
            seen_slots.add((album_id, slot))
            album = associations[album_id]
            _require(link.get("association_sha256") == canonical_sha256(album),
                     "link source/context association hash mismatch")
            sgf_hash = link.get("production_sgf_sha256")
            _require(isinstance(sgf_hash, str) and bool(_HASH.fullmatch(sgf_hash)),
                     "link requires a valid production SGF SHA-256 preimage")
            expected = link.get("expected")
            _require(isinstance(expected, dict) and set(expected) == required_context,
                     "link needs complete raw/date/round/rank/old-ID context")
            for field in required_context - {"old_id"}:
                _require(expected[field] == album.get(field), f"link expected {field} differs from inventory")
            if slot == "selected_event":
                selection = selections.get(album_id)
                _require(selection is not None, "selected_event album absent from pinned selection scope")
                _require(selection["event_id"] is None and selection["name_batch_id"] is None
                         and selection["name_proof_sha256"] is None,
                         "selected_event is already linked or proved")
                _require(expected["old_id"] is None and album.get("event_id") is None,
                         "selected_event requires null old event ID")
                _require(selection["selected_raw"] != album.get("event"),
                         "selected_event must be a distinct reviewed selection")
                _require(selection["sgf_sha256"] == sgf_hash,
                         "selected_event production SGF hash differs from source selection")
                _require(link.get("selection_batch_id") == selection["batch_id"]
                         and link.get("selection_bundle_sha256") == selection["bundle_sha256"]
                         and link.get("selection_before_image") == selection["source_after_image"]
                         and link.get("selection_before_sha256") == selection["source_after_sha256"],
                         "selected_event original batch or complete after-image differs from inventory")
                raw_value = selection["selected_raw"]
                actual_scope = event_slots.get(raw_value, [])
            else:
                _require(expected["old_id"] == album.get(slot_ids[slot]), "link old ID differs from inventory")
                raw_field = {"black": "player_black", "white": "player_white", "event": "event"}[slot]
                raw_value = expected[raw_field]
                actual_scope = (event_slots if slot == "event" else player_slots).get(raw_value, [])
            _require(bool(actual_scope), "link raw global occurrence slots absent from inventory")
            if "raw_scope_slots" in link:
                _require(link["raw_scope_slots"] == actual_scope,
                         "link raw global occurrence slots differ from inventory")
            scope_key = ("raw_event" if slot in {"event", "selected_event"} else "raw_player", raw_value)
            if scope_key not in raw_scope_hashes:
                raw_scope_hashes[scope_key] = canonical_sha256(actual_scope)
            _require(link.get("raw_scope_sha256") == raw_scope_hashes[scope_key],
                     "link raw global scope hash mismatch")
            target = link.get("target")
            target_key = _owner_token(target)
            _require(target_key in declarations, "link target missing from owner manifest")
            _require(target["kind"] == ("event" if slot in {"event", "selected_event"} else "player"),
                     "link target kind differs from slot")
            if expected["old_id"] is not None and target.get("id") != expected["old_id"]:
                _require(link.get("corrects_existing") is True, "non-null identity correction needs explicit approval")
            review = link.get("identity_review")
            _require(isinstance(review, dict) and review.get("status") == "approved",
                     "link needs approved identity-mapping review")
            _require(_text(review.get("producer_id")) and _text(review.get("producer_model"))
                     and _time(review.get("produced_at")) and _text(review.get("reviewer_id"))
                     and review["reviewer_id"] != review["producer_id"]
                     and _text(review.get("reviewer_model")) and _time(review.get("reviewed_at"))
                     and _time(review["reviewed_at"]) >= _time(review["produced_at"])
                     and _text(review.get("identity_basis")) and _text(review.get("review_conclusion")),
                     "link identity review lacks independent signed decision")
            checks = review.get("source_checks")
            _require(isinstance(checks, list) and checks, "link identity review needs source checks")
            for check in checks:
                _require(isinstance(check, dict) and isinstance(check.get("url"), str)
                         and check["url"].startswith("https://")
                         and bool(_HASH.fullmatch(str(check.get("body_sha256", ""))))
                         and _text(check.get("body_excerpt")) and _text(check.get("identity_match")),
                         "link source check lacks real body or identity match")
            if slot in {"event", "selected_event"}:
                _require(_text(review.get("event_period_basis")),
                         "event identity link needs naming-period evidence")
            if slot == "selected_event":
                context = declarations[target_key].get("identity_context")
                _require(isinstance(context, dict), "selected_event target identity context missing")
                _require(review.get("event_period") == {key: context[key] for key in ("start_date", "end_date")},
                         "selected_event event_period differs from target context")
                _require(review.get("event_region") == context["region"]
                         and _text(review.get("event_region_basis")),
                         "selected_event event_region differs from target context or lacks evidence")
                played_bounds = _played_date_bounds(album.get("date_played"))
                _require(played_bounds is not None,
                         "selected_event album date is ambiguous or unsupported")
                _require(_iso_date(context["start_date"]) <= played_bounds[0]
                         and played_bounds[1] <= _iso_date(context["end_date"]),
                         "selected_event period excludes album date")
            frozen_at = _time(review.get("scope_frozen_at"))
            _require(frozen_at and _time(review["reviewed_at"]) > frozen_at,
                     "link identity review must follow scope freeze")
            if slot == "selected_event":
                produced_at = _time(review["produced_at"])
                _require(produced_at <= frozen_at,
                         "selected_event evidence, production and freeze chronology invalid")
                for check in checks:
                    captured = _time(check.get("fetched_at"))
                    _require(captured is not None and captured <= produced_at,
                             "selected_event evidence, production and freeze chronology invalid")
            review_groups[(target_key, raw_value)].append((number, link))
            link_targets.add(target_key)
        except (AttributeError, KeyError, TypeError, CandidateError) as exc:
            errors.append(f"album_link[{number}]: {exc}")
    for (target_key, raw_value), group in review_groups.items():
        scope_hash = identity_scope_sha256(bundle, [link for _, link in group], declarations[target_key])
        first_review = group[0][1]["identity_review"]
        for number, link in group:
            review = link["identity_review"]
            if review.get("scope_sha256") != scope_hash:
                errors.append(f"album_link[{number}]: identity review scope hash mismatch")
            if review != first_review:
                errors.append(f"album_link[{number}]: identity review scope needs the same independent decision")
    if v4:
        selected_raws = {raw for _, raw in review_groups}
        if not review_groups:
            errors.append("v4 requires a finite selected_event link")
        for token, declaration in declarations.items():
            owner = declaration["owner"]
            if owner["kind"] == "event" and token not in link_targets:
                errors.append(f"irrelevant v4 event owner: {token}")
            elif owner["kind"] == "raw_event":
                pinned = declaration.get("create") or declaration.get("preimage") or {}
                if pinned.get("raw_value") not in selected_raws:
                    errors.append(f"irrelevant v4 raw_event owner: {token}")
    return declarations, link_targets, errors


def validate_bundle(
    bundle: dict,
    registry: dict,
    inventory: dict,
    research_records: list[dict],
    *,
    approved_name_snapshot: list[dict] | None = None,
) -> dict:
    """Report exact batch defects; ready means this finite bundle, not the whole catalog."""
    errors: list[str] = []
    _require(isinstance(bundle, dict), "bundle must be an object")
    _require((bundle.get("bundle_format"), bundle.get("inventory_format"), inventory.get("inventory_format"))
             in {(1, 2, 2), (2, 2, 2), (3, 3, 3),
                 (1, 4, 4), (2, 4, 4), (3, 4, 4), (4, 4, 4)},
             "bundle and inventory format mismatch")
    _require(bundle.get("inventory_sha256") == inventory.get("sha256")
             and bool(_HASH.fullmatch(str(bundle.get("inventory_sha256", "")))), "inventory hash mismatch")
    _require(bundle.get("registry_version") == registry["version"]
             and bundle.get("registry_sha256") == registry_sha256(registry), "source registry mismatch")
    _require(_text(bundle.get("rule_version")), "bundle rule version required")
    members = bundle.get("members")
    candidates = bundle.get("candidates")
    _require(isinstance(members, list) and members and isinstance(candidates, list), "finite members and candidates required")
    _require(bundle.get("member_set_sha256") == canonical_sha256(members), "member set hash mismatch")
    _require(set(registry["language_tags"]) == LANGUAGES, "source registry must define eleven product languages")
    values = _inventory_values(inventory)
    declarations = link_targets = None
    if bundle["bundle_format"] in {2, 3, 4}:
        declarations, link_targets, v2_errors = _v2_scope(bundle, inventory)
        errors.extend(v2_errors)
    member_keys = []
    member_map = {}
    raw_spellings = {}
    for number, item in enumerate(members):
        try:
            key = _owner_key(item.get("owner"), item.get("lang"))
            if bundle["bundle_format"] == 4:
                _require(item["owner"]["kind"] in {"event", "raw_event"},
                         "v4 writes only event and raw_event names")
            if bundle["bundle_format"] == 1:
                _require("id" in item["owner"], "v1 members need existing DB IDs")
            _check_owner_in_inventory(item, values, declarations=declarations, link_targets=link_targets)
            if key in member_map:
                raise CandidateError("duplicate member")
            owner = item["owner"]
            if owner["kind"].startswith("raw_"):
                raw_key = _owner_token(owner)
                if raw_key in raw_spellings and raw_spellings[raw_key] != item["raw_value"]:
                    raise CandidateError("same raw ID has different raw spellings across languages")
                raw_spellings[raw_key] = item["raw_value"]
            member_map[key] = item
            member_keys.append(key)
        except (AttributeError, CandidateError) as exc:
            errors.append(f"member[{number}]: {exc}")
    evidence_by_hash = defaultdict(list)
    research_keys = defaultdict(list)
    anchors_by_hash = {}
    for number, record in enumerate(research_records):
        try:
            if isinstance(record, dict) and record.get("evidence_kind") == "transliteration_anchor":
                validate_transliteration_anchor(record)
                digest = canonical_sha256(record)
                _require(digest not in anchors_by_hash, "duplicate transliteration source anchor")
                anchors_by_hash[digest] = record
                continue
            key = _owner_key(record.get("owner"), record.get("lang"))
            validate_research_record(record, registry)
            digest = canonical_sha256(record)
            evidence_by_hash[digest].append(record)
            research_keys[key].append(digest)
        except (AttributeError, CandidateError, EvidenceError) as exc:
            errors.append(f"research[{number}]: {exc}")
    for key, hashes in research_keys.items():
        if len(hashes) > 1:
            errors.append(f"multiple research records for {key}; consolidate findings before approval")
    if bundle["bundle_format"] == 1 and (
        any(record["content"].get("anchor_format") == 3 for record in anchors_by_hash.values())
        or any(isinstance(item, dict) and "raw_display_scope_sha256" in item for item in candidates)
    ):
        errors.append("raw-player display scope requires a validated v2 owner declaration")
    transliteration_context = None
    has_transliteration = bundle.get("transliteration") is not None or any(
        isinstance(item, dict) and item.get("decision_kind") == "transliterated" for item in candidates
    )
    if has_transliteration:
        try:
            transliteration_context = validate_transliteration(
                bundle.get("transliteration"), candidates, anchors_by_hash, approved_name_snapshot
            )
        except (AttributeError, KeyError, TypeError, EvidenceError) as exc:
            errors.append(f"transliteration: {exc}")
    elif anchors_by_hash:
        errors.append("transliteration source anchors require a signed finite transliteration section")
    composition_context = None
    if bundle.get("composition") is not None or any(isinstance(item, dict) and item.get("decision_kind") == "composed"
                                                    for item in candidates):
        try:
            _, event_games, _, event_slots = _occurrence_indexes(
                {dict(zip(inventory["association_columns"], row))["id"]: dict(zip(inventory["association_columns"], row))
                 for row in inventory["album_associations"]}, _selection_rows(inventory))
            raw_by_value, rule_by_lang, scope = validate_composition(bundle.get("composition"), bundle, inventory,
                                                                      event_games, event_slots)
            series = bundle["composition"]["scope"]["content"]["series_owner"]
            base_by_lang = {}
            for item in candidates:
                if (isinstance(item, dict) and item.get("owner") == series and item.get("lang") in LANGUAGES
                        and item.get("decision_kind") in {"conventional", "generated"}):
                    matched = evidence_by_hash.get(item.get("research_sha256"), [])
                    _require(len(matched) == 1, "composed series base research missing or duplicate")
                    _validate_candidate(item, matched[0], registry, values,
                                        declarations=declarations, link_targets=link_targets)
                    _require(item["review_status"] == "approved", "composed series base must be approved")
                    base_by_lang[item["lang"]] = item
            _require(set(base_by_lang) == LANGUAGES, "composition needs all eleven approved series bases")
            composition_context = raw_by_value, rule_by_lang, base_by_lang, scope
        except (AttributeError, KeyError, CandidateError, CompositionError) as exc:
            errors.append(f"composition: {exc}")
    seen = set()
    decisions = []
    for number, item in enumerate(candidates):
        try:
            key = _owner_key(item.get("owner"), item.get("lang"))
            if bundle["bundle_format"] == 4:
                _require(item["owner"]["kind"] in {"event", "raw_event"},
                         "v4 writes only event and raw_event names")
            if key in seen:
                raise CandidateError("duplicate candidate")
            seen.add(key)
            if key not in member_map:
                raise CandidateError("candidate lies outside finite member set")
            if item.get("raw_value") != member_map[key].get("raw_value"):
                raise CandidateError("candidate raw spelling differs from member")
            if item["owner"]["kind"] == "raw_player" and declarations is not None:
                declaration = declarations[_owner_token(item["owner"])]
                scope = declaration.get("raw_display_scope")
                if scope is not None:
                    scope_hash = canonical_sha256(scope)
                    _require(item.get("raw_display_scope_sha256") == scope_hash,
                             "raw-player candidate differs from signed display scope")
                    if item.get("decision_kind") != "transliterated":
                        research = evidence_by_hash.get(item.get("research_sha256"), [])
                        _require(len(research) == 1 and research[0].get("raw_display_scope_sha256") == scope_hash,
                                 "raw-player research differs from signed display scope")
                else:
                    _require("raw_display_scope_sha256" not in item,
                             "raw-player candidate has no signed display scope")
            if item["owner"]["kind"] == "raw_player" and item.get("decision_kind") == "transliterated" \
                    and "raw_display_scope_sha256" in item:
                binding = transliteration_context.get(key) if isinstance(transliteration_context, dict) else None
                anchor = anchors_by_hash.get(item.get("source_anchor_sha256"))
                _require(
                    binding is not None and anchor is not None
                    and anchor["content"].get("anchor_format") == 3
                    and anchor["content"].get("raw_display_scope_sha256") == item["raw_display_scope_sha256"]
                    and binding[1].get("raw_display_scope_sha256") == item["raw_display_scope_sha256"],
                    "scoped raw-player transliteration requires one matching format-3 source and signed member",
                )
            evidence = evidence_by_hash.get(item.get("research_sha256"), [])
            if len(evidence) > 1:
                raise CandidateError("duplicate research record hash")
            checked = _validate_candidate(
                item,
                evidence[0] if evidence else None,
                registry,
                values,
                declarations=declarations,
                link_targets=link_targets,
                composition_context=composition_context,
                transliteration_context=transliteration_context,
            )
            decisions.append(checked)
        except (AttributeError, CandidateError) as exc:
            errors.append(f"candidate[{number}]: {exc}")
    missing = sorted(set(member_keys) - seen)
    for key in missing:
        errors.append(f"missing candidate: {key}")
    if composition_context is not None:
        expected = {(raw, lang) for raw in HONINBO_RAWS for lang in LANGUAGES}
        actual = {(row["raw_value"], row["lang"]) for row in decisions if row["decision_kind"] == "composed"}
        if actual != expected:
            errors.append("composition requires exact 34 x 11 candidate set")
    if bundle["bundle_format"] in {2, 3, 4}:
        approved_keys = {_owner_key(row["owner"], row["lang"]) for row in decisions
                         if row["review_status"] == "approved"}
        decisions_by_owner = defaultdict(list)
        for row in decisions:
            decisions_by_owner[_owner_token(row["owner"])].append(row)
        for token, declaration in declarations.items():
            owner = declaration["owner"]
            if "ref" in owner and owner["kind"].startswith("raw_"):
                category = declaration["create"]["category"]
                allowed = _RAW_CATEGORY_DECISIONS[owner["kind"]][category]
                rows = decisions_by_owner[token]
                if not rows or any(row["review_status"] != "approved"
                                   or row["decision_kind"] not in allowed for row in rows):
                    errors.append(f"new raw category lacks corresponding approved display decision: {token}")
            if "ref" in owner and owner["kind"] in {"player", "event"}:
                if token not in link_targets:
                    errors.append(f"new identity lacks approved album link: {token}")
            if owner["kind"] in {"player", "event"} and ("ref" in owner or token in link_targets):
                if any(_owner_key(owner, lang) not in approved_keys for lang in LANGUAGES):
                    errors.append(f"linked identity lacks all eleven approved language names: {token}")
    collisions = defaultdict(list)
    for row in decisions:
        if row["review_status"] == "approved" and row["decision_kind"] in {
            "conventional",
            "generated",
            "corrected",
            "composed",
            "transliterated",
        }:
            collisions[(row["lang"], normalize_alias(row["display_name"]))].append(row["owner"])
    for (lang, name), owners in collisions.items():
        if len({_owner_token(owner) for owner in owners}) > 1:
            group = [row for row in decisions if row["lang"] == lang
                     and normalize_alias(row["display_name"]) == name]
            if any(
                row["review_status"] == "approved" and row["decision_kind"] in {"composed", "transliterated"}
                for row in group
            ) or not all(
                row.get("collision_decision") == "distinct_people_confirmed" and _text(row.get("collision_basis"))
                for row in group
            ):
                errors.append(f"possible name collision: {lang}:{name} owners={owners}")
    statuses = Counter(row["review_status"] for row in decisions)
    write_errors = []
    for number, item in enumerate(candidates):
        if not isinstance(item, dict) or "name_preimage_sha256" not in item:
            write_errors.append(f"candidate[{number}]: name preimage missing")
            continue
        preimage = item["name_preimage_sha256"]
        if preimage is not None and not (isinstance(preimage, str) and _HASH.fullmatch(preimage)):
            write_errors.append(f"candidate[{number}]: name preimage must be null or lowercase SHA-256")
        if isinstance(item.get("owner"), dict) and "ref" in item["owner"] and preimage is not None:
            write_errors.append(f"candidate[{number}]: new owner name preimage must be null")
        binding = item.get("preimage_binding")
        if not isinstance(binding, dict):
            write_errors.append(f"candidate[{number}]: independently reviewed preimage binding missing")
            continue
        actor = binding.get("actor_id")
        captured_at = _time(binding.get("captured_at"))
        bound_at = _time(binding.get("bound_at"))
        produced_at = _time(item.get("produced_at"))
        reviewed_at = _time(item.get("reviewed_at"))
        if not (_text(actor) and _text(binding.get("actor_model"))
                and "name_preimage_sha256" in binding
                and binding["name_preimage_sha256"] == preimage
                and captured_at and bound_at and produced_at
                and produced_at <= bound_at and captured_at <= bound_at
                and (item.get("review_status") != "approved"
                     or (reviewed_at and bound_at <= reviewed_at and actor != item.get("reviewer_id")))):
            write_errors.append(f"candidate[{number}]: preimage binding identity, value or chronology invalid")
        source_hash = binding.get("source_candidate_sha256")
        capture_hash = binding.get("capture_sha256")
        if actor != item.get("producer_id") and not (isinstance(source_hash, str) and _HASH.fullmatch(source_hash)):
            write_errors.append(f"candidate[{number}]: separate binder needs source candidate hash")
        if source_hash is not None and not (isinstance(source_hash, str) and _HASH.fullmatch(source_hash)):
            write_errors.append(f"candidate[{number}]: source candidate hash invalid")
        if capture_hash is not None and not (isinstance(capture_hash, str) and _HASH.fullmatch(capture_hash)):
            write_errors.append(f"candidate[{number}]: preimage capture hash invalid")
    ready = not errors and not statuses["pending"] and not statuses["rejected"]
    return {
        "ready": ready, "write_ready": ready and not write_errors, "write_errors": write_errors,
        "inventory_sha256": inventory["sha256"], "member_count": len(members),
        "candidate_count": len(candidates), "approved": statuses["approved"],
        "pending": statuses["pending"], "rejected": statuses["rejected"],
        "missing": len(missing), "errors": errors,
    }


_SEASONS = {
    "en": ("Spring", "Fall"), "cn": ("春", "秋"), "tw": ("春", "秋"),
    "jp": ("春", "秋"), "ko": ("봄", "가을"), "de": ("Frühling", "Herbst"),
    "es": ("Primavera", "Otoño"), "fr": ("Printemps", "Automne"),
    "ru": ("Весна", "Осень"), "tr": ("İlkbahar", "Sonbahar"), "ua": ("Весна", "Осінь"),
}
_ROUND = {"en": "Round {}", "cn": "第{}轮", "tw": "第{}輪", "jp": "第{}回", "ko": "{}회전",
          "de": "Runde {}", "es": "Ronda {}", "fr": "Tour {}", "ru": "Тур {}", "tr": "{}. tur", "ua": "Тур {}"}
_GAME = {"en": "Game {}", "cn": "第{}局", "tw": "第{}局", "jp": "第{}局", "ko": "{}국",
         "de": "Partie {}", "es": "Partida {}", "fr": "Partie {}", "ru": "Партия {}", "tr": "{}. oyun", "ua": "Партія {}"}
_EDITION = {
    "cn": "第{}届", "tw": "第{}屆", "jp": "第{}回", "ko": "제{}회", "de": "{}. Ausgabe",
    "es": "{}.ª edición", "fr": "{}e édition", "ru": "{}-й розыгрыш", "tr": "{}. edisyon", "ua": "{}-й розіграш",
}
_HAN_NUMERALS = {char: number for number, char in enumerate("一二三四五六七八九", 1)}


def _ordinal(value: str) -> str:
    number = int(value)
    if 10 <= number % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _edition_number(value: str) -> int:
    if isinstance(value, str):
        english = re.fullmatch(r"([1-9]\d{0,2})(st|nd|rd|th)", value, re.IGNORECASE)
        if english:
            number = int(english.group(1))
            _require(_ordinal(str(number)).casefold() == value.casefold(), "invalid event edition")
            return number
    _require(isinstance(value, str) and re.fullmatch(r"(?:[1-9]\d{0,2}|[一二三四五六七八九十]{1,3}|首)[届期]", value),
             "invalid event edition")
    raw = value[:-1]
    if raw == "首":
        return 1
    if raw.isascii():
        return int(raw)
    if raw == "十":
        return 10
    if "十" in raw:
        tens, ones = raw.split("十")
        _require(tens in {"", *_HAN_NUMERALS} and ones in {"", *_HAN_NUMERALS}, "invalid event edition")
        return (1 if not tens else _HAN_NUMERALS[tens]) * 10 + (0 if not ones else _HAN_NUMERALS[ones])
    _require(raw in _HAN_NUMERALS, "invalid event edition")
    return _HAN_NUMERALS[raw]


def render_event_components(core_name: str, components: dict, lang: str) -> str:
    """Format independently approved event core plus explicit structured parts."""
    _require(_text(core_name) and lang in LANGUAGES and isinstance(components, dict), "event core/lang/parts invalid")
    _require(set(components) <= {"year", "season", "edition", "round", "game"}, "unknown event component")
    parts = [core_name]
    year = components.get("year")
    if year is not None:
        _require(isinstance(year, str) and re.fullmatch(r"[12]\d{3}", year), "invalid event year")
        parts.append(f"{year}年" if lang in {"cn", "tw", "jp"} else year)
    season = components.get("season")
    if season is not None:
        _require(season in {"Spring", "Fall"}, "unknown event season")
        parts.append(_SEASONS[lang][0 if season == "Spring" else 1])
    edition = components.get("edition")
    if edition is not None:
        number = _edition_number(edition)
        if lang == "en":
            parts.append(_ordinal(str(number)))
        elif lang == "jp" and edition.endswith("期"):
            parts.append(f"第{number}期")
        else:
            parts.append(_EDITION[lang].format(number))
    for key in ("round", "game"):
        value = components.get(key)
        if value is not None:
            suffix = "轮" if key == "round" else "局"
            _require(isinstance(value, str) and re.fullmatch(rf"[1-9]\d{{0,2}}{suffix}", value),
                     "invalid event round/game")
            parts.append((_ROUND if key == "round" else _GAME)[lang].format(value[:-1]))
    return " · ".join(parts)
