"""Offline validation of reviewed kifu display-name decisions.

This module never translates or approves a name. It verifies an explicit,
finite candidate bundle against a pinned inventory and research records.
Raw-value table IDs are not present in inventory format 2: the importer must
also check that each raw ID resolves to the declared exact spelling in DB.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import re

from katrain.web.kifu.name_evidence import (
    EvidenceError,
    OWNER_KINDS,
    registry_sha256,
    validate_research_record,
)
from katrain.web.kifu.name_parse import parse_event, parse_player


LANGUAGES = frozenset(("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"))
DECISION_KINDS = frozenset(("conventional", "generated", "generic", "hidden", "placeholder", "error", "corrected"))
_HASH = re.compile(r"^[0-9a-f]{64}$")
_RANK_SUFFIX = re.compile(r"(?:[一二三四五六七八九十初]|[1-9]\d?)\s*(?:段|級|级|dan|kyu|[dkp])\Z", re.I)
_RESULT = re.compile(r"(?:中盘|中盤|目半|resign|resignation|points?)\s*(?:胜|勝|win|won)?", re.I)
_UNSAFE = re.compile(r"[\[\]\x00-\x1f]")
_MAX_NAME = {"player": 512, "event": 256, "raw_player": 1024, "raw_event": 4096}
_SCRIPT = {
    "en": re.compile(r"[A-Za-z]"), "de": re.compile(r"[A-Za-zÀ-ÿ]"),
    "es": re.compile(r"[A-Za-zÀ-ÿ]"), "fr": re.compile(r"[A-Za-zÀ-ÿ]"),
    "tr": re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü]"),
    "cn": re.compile(r"[\u3400-\u9fff]"), "tw": re.compile(r"[\u3400-\u9fff]"),
    "jp": re.compile(r"[\u3400-\u9fff\u3040-\u30ff]"),
    "ko": re.compile(r"[\u3400-\u9fff\uac00-\ud7af]"),
    "ru": re.compile(r"[\u0400-\u052f]"), "ua": re.compile(r"[\u0400-\u052f]"),
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


def canonical_sha256(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _owner_key(owner: object, lang: object) -> str:
    _require(isinstance(owner, dict) and set(owner) == {"kind", "id"}, "exact owner kind/id required")
    _require(isinstance(owner["kind"], str) and owner["kind"] in OWNER_KINDS
             and type(owner["id"]) is int and owner["id"] > 0,
             "invalid owner kind/id")
    _require(isinstance(lang, str) and lang in LANGUAGES, "one of the eleven product languages is required")
    return f"{owner['kind']}:{owner['id']}:{lang}"


def _inventory_values(inventory: dict) -> dict[str, set]:
    _require(inventory.get("inventory_format") == 2 and bool(_HASH.fullmatch(str(inventory.get("sha256", "")))),
             "inventory format 2 and SHA-256 required")
    columns = inventory.get("association_columns")
    rows = inventory.get("album_associations")
    required = {"player_black", "player_white", "event", "black_player_id", "white_player_id", "event_id"}
    _require(isinstance(columns, list) and required.issubset(columns) and isinstance(rows, list),
             "inventory associations are incomplete")
    values = {kind: set() for kind in OWNER_KINDS}
    for row in rows:
        _require(isinstance(row, list) and len(row) == len(columns), "inventory association is malformed")
        album = dict(zip(columns, row))
        values["raw_player"].update((album["player_black"], album["player_white"]))
        values["raw_event"].add(album["event"])
        values["player"].update((album["black_player_id"], album["white_player_id"]))
        values["event"].add(album["event_id"])
    return values


def _check_owner_in_inventory(row: dict, values: dict[str, set]) -> None:
    owner = row["owner"]
    if owner["kind"].startswith("raw_"):
        _require("raw_value" in row and isinstance(row["raw_value"], str),
                 "raw owner spelling must be text")
        _require(row["raw_value"] in values[owner["kind"]],
                 "raw owner needs exact spelling present in pinned inventory")
    else:
        _require(owner["id"] in values[owner["kind"]], "entity ID absent from pinned inventory")
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


def _validate_candidate(row: dict, research: dict | None, registry: dict, inventory_values: dict) -> dict:
    _require(isinstance(row, dict), "candidate must be an object")
    _owner_key(row.get("owner"), row.get("lang"))
    _check_owner_in_inventory(row, inventory_values)
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

    if decision in {"conventional", "generated", "corrected"}:
        checked = _research_for(row, research, registry)
        if decision == "generated":
            _require(checked["scope_status"] == "not_found_in_scope", "generated name needs complete negative search")
            if row["owner"]["kind"] in {"player", "raw_player"}:
                _require(_text(checked.get("reading")) and _text(checked.get("reading_basis_url")),
                         "generated player name needs sourced original reading")
            _require(row["generation_rule_version"] != "none", "generated name needs a named conversion rule")
            _require(bool(_SCRIPT[row["lang"]].search(display)), "generated name lacks target-language script")
        else:
            _require(checked["scope_status"] == "found" and display == checked["candidate_name"],
                     "adopted name must match found target-language evidence")
            sources = {source["id"]: source for source in registry["sources"]}
            _require(any(check["status"] == "found" and check["candidate_name"] == display
                         and sources[check["source_id"]]["tier"] in {"official", "language_go"}
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
    if row["owner"]["kind"] in {"player", "raw_player"} and decision not in {"error", "placeholder"}:
        _require(not _RANK_SUFFIX.search(display) and not _RESULT.search(display),
                 "player name contains a rank or result")
    if row["owner"]["kind"] == "event" and decision in {"conventional", "generated"}:
        _require(not re.search(r"\b[12]\d{3}\b", display), "event core name contains a year")
    return row


def validate_candidate(row: dict, research: dict | None, registry: dict, inventory: dict) -> dict:
    """Validate a proposed display decision, preserving its review status."""
    return _validate_candidate(row, research, registry, _inventory_values(inventory))


def validate_bundle(bundle: dict, registry: dict, inventory: dict, research_records: list[dict]) -> dict:
    """Report exact batch defects; ready means this finite bundle, not the whole catalog."""
    errors: list[str] = []
    _require(isinstance(bundle, dict), "bundle must be an object")
    _require(bundle.get("bundle_format") == 1 and bundle.get("inventory_format") == 2,
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
    member_keys = []
    member_map = {}
    for number, item in enumerate(members):
        try:
            key = _owner_key(item.get("owner"), item.get("lang"))
            _check_owner_in_inventory(item, values)
            if key in member_map:
                raise CandidateError("duplicate member")
            member_map[key] = item
            member_keys.append(key)
        except (AttributeError, CandidateError) as exc:
            errors.append(f"member[{number}]: {exc}")
    evidence_by_hash = defaultdict(list)
    for record in research_records:
        evidence_by_hash[canonical_sha256(record)].append(record)
    seen = set()
    decisions = []
    for number, item in enumerate(candidates):
        try:
            key = _owner_key(item.get("owner"), item.get("lang"))
            if key in seen:
                raise CandidateError("duplicate candidate")
            seen.add(key)
            if key not in member_map:
                raise CandidateError("candidate lies outside finite member set")
            if item.get("raw_value") != member_map[key].get("raw_value"):
                raise CandidateError("candidate raw spelling differs from member")
            evidence = evidence_by_hash.get(item.get("research_sha256"), [])
            if len(evidence) > 1:
                raise CandidateError("duplicate research record hash")
            checked = _validate_candidate(item, evidence[0] if evidence else None, registry, values)
            decisions.append(checked)
        except (AttributeError, CandidateError) as exc:
            errors.append(f"candidate[{number}]: {exc}")
    missing = sorted(set(member_keys) - seen)
    for key in missing:
        errors.append(f"missing candidate: {key}")
    collisions = defaultdict(list)
    for row in decisions:
        if row["review_status"] == "approved" and row["decision_kind"] in {"conventional", "generated", "corrected"}:
            collisions[(row["lang"], row["display_name"].casefold())].append(row["owner"])
    for (lang, name), owners in collisions.items():
        if len({(owner["kind"], owner["id"]) for owner in owners}) > 1:
            group = [row for row in decisions if row["lang"] == lang and row["display_name"].casefold() == name]
            if not all(row.get("collision_decision") == "distinct_people_confirmed"
                       and _text(row.get("collision_basis")) for row in group):
                errors.append(f"possible name collision: {lang}:{name} owners={owners}")
    statuses = Counter(row["review_status"] for row in decisions)
    return {
        "ready": not errors and not statuses["pending"] and not statuses["rejected"],
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


def _ordinal(value: str) -> str:
    number = int(value)
    if 10 <= number % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


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
        _require(isinstance(edition, str) and re.fullmatch(r"[1-9]\d{0,2}[届期]", edition), "invalid event edition")
        number = edition[:-1]
        parts.append(_ordinal(number) if lang == "en" else edition)
    for key in ("round", "game"):
        value = components.get(key)
        if value is not None:
            suffix = "轮" if key == "round" else "局"
            _require(isinstance(value, str) and re.fullmatch(rf"[1-9]\d{{0,2}}{suffix}", value),
                     "invalid event round/game")
            parts.append((_ROUND if key == "round" else _GAME)[lang].format(value[:-1]))
    return " · ".join(parts)
