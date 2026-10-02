"""Lossless structural hints for raw event strings.

These hints never establish an event identity or approve a translated display.
"""

from collections import Counter, defaultdict
import hashlib
import json
import re

from katrain.web.kifu.name_parse import parse_event
from katrain.web.kifu.name_inventory import SELECTION_COLUMNS, _hash_row


RULE_VERSION = "event-components-v5"
_YEAR = re.compile(r"([12]\d{3})年(?:度)?\s*")
_NUMBER = r"(?:[0-9]{1,3}|[一二三四五六七八九]|十[一二三四五六七八九]?|[一二三四五六七八九]十[一二三四五六七八九]?)"
_EDITION = re.compile(rf"(?:(?:第)?({_NUMBER})|首)(届|期)\s*")
_INFIX_EDITION = re.compile(rf"第({_NUMBER}|[０-９]{{1,3}})(期|届)")
_EXPLICIT_NUMBERED_FRAGMENT = re.compile(r"第[0-9０-９一二三四五六七八九十百]+[期届轮回局场]")
_SINGLE_ROUND_NUMBER = r"(?:[1-9][0-9]{0,2}|[１-９][０-９]{0,2}|[一二三四五六七八九]|十[一二三四五六七八九]?|[一二三四五六七八九]十[一二三四五六七八九]?)"
_SINGLE_ROUND_FRAGMENT = re.compile(rf"(?P<left>.+?)第(?P<number>{_SINGLE_ROUND_NUMBER})轮(?P<tail>主将|快棋)?\Z")
_ROUND = re.compile(rf"\s*(?:第)?({_NUMBER})(轮|局)\s*\Z")
_OTEAI_YEAR = re.compile(r"(Oteai)\s+([12]\d{3})\Z", re.IGNORECASE)
_CWI = re.compile(r"(JapanPromotionTournament),([12]\d{3}),(Spring|Fall)\Z", re.IGNORECASE)
_ENGLISH_ORDINAL = re.compile(r"([1-9]\d{0,2})(st|nd|rd|th)\s+(\S.*)\Z", re.IGNORECASE)
_ENGLISH_ORDINAL_SUFFIX = re.compile(r"(\S(?:.*\S)?),([1-9]\d{0,2})(st|nd|rd|th)\Z", re.IGNORECASE)
_ENGLISH_ORDINAL_JOINED = re.compile(r"([1-9]\d{0,2})(st|nd|rd|th)([A-Za-z(].*)\Z", re.IGNORECASE)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _ordinal_suffix(number: int) -> str:
    if number % 100 in {11, 12, 13}:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def _part(raw: str, kind: str, value: str, start: int, end: int) -> dict:
    return {"kind": kind, "value": value, "text": raw[start:end], "start": start, "end": end}


def _result(raw: str, parts: list[dict], grammar: str, exceptions: list[str] | None = None) -> dict:
    core = "".join(part["text"] for part in parts if part["kind"] == "core")
    return {
        "raw_value": raw,
        "core": core,
        "grammar": grammar,
        "parts": parts,
        "components": [part for part in parts if part["kind"] != "core"],
        "status": "pending_review",
        "rule_version": RULE_VERSION,
        "exceptions": exceptions or [],
    }


def _unparsed(raw: str, exception: str | None = None) -> dict:
    return _result(raw, [_part(raw, "core", raw, 0, len(raw))], "unparsed", [exception] if exception else [])


def structure_event(raw: str) -> dict:
    """Extract only anchored, explicit components while preserving character spans."""
    category = parse_event(raw, None).category
    if category in {"corrupt_data", "game_description", "program_source_label", "empty"}:
        return _unparsed(raw, category)

    named = _OTEAI_YEAR.fullmatch(raw)
    if named:
        core_end = named.end(1)
        return _result(raw, [
            _part(raw, "core", named.group(1), 0, core_end),
            _part(raw, "year", named.group(2), core_end, len(raw)),
        ], "oteai_year")
    named = _CWI.fullmatch(raw)
    if named:
        core_end = named.end(1)
        year_end = named.end(2)
        return _result(raw, [
            _part(raw, "core", named.group(1), 0, core_end),
            _part(raw, "year", named.group(2), core_end, year_end),
            _part(raw, "season", named.group(3), year_end, len(raw)),
        ], "cwi_japan_promotion")

    ordinal = _ENGLISH_ORDINAL.fullmatch(raw)
    if ordinal and ordinal.group(2).lower() == _ordinal_suffix(int(ordinal.group(1))):
        core_start = ordinal.start(3)
        return _result(raw, [
            _part(raw, "edition", ordinal.group(1) + ordinal.group(2), 0, core_start),
            _part(raw, "core", ordinal.group(3), core_start, len(raw)),
        ], "english_ordinal_edition")

    suffix_ordinal = _ENGLISH_ORDINAL_SUFFIX.fullmatch(raw)
    if suffix_ordinal and suffix_ordinal.group(3).lower() == _ordinal_suffix(int(suffix_ordinal.group(2))):
        core_end = suffix_ordinal.end(1)
        return _result(raw, [
            _part(raw, "core", suffix_ordinal.group(1), 0, core_end),
            _part(raw, "edition", suffix_ordinal.group(2) + suffix_ordinal.group(3), core_end, len(raw)),
        ], "english_ordinal_suffix")

    joined_ordinal = _ENGLISH_ORDINAL_JOINED.fullmatch(raw)
    if joined_ordinal and joined_ordinal.group(2).lower() == _ordinal_suffix(int(joined_ordinal.group(1))):
        core_start = joined_ordinal.start(3)
        return _result(raw, [
            _part(raw, "edition", joined_ordinal.group(1) + joined_ordinal.group(2), 0, core_start),
            _part(raw, "core", joined_ordinal.group(3), core_start, len(raw)),
        ], "english_ordinal_joined")

    start, end = 0, len(raw)
    prefixes = []
    seen = set()
    for _ in range(2):
        year = _YEAR.match(raw, start)
        edition = _EDITION.match(raw, start)
        if year and "year" not in seen:
            prefixes.append(_part(raw, "year", year.group(1), start, year.end()))
            start = year.end()
            seen.add("year")
        elif edition and "edition" not in seen:
            number = edition.group(1) or "首"
            prefixes.append(_part(raw, "edition", number + edition.group(2), start, edition.end()))
            start = edition.end()
            seen.add("edition")
        else:
            break

    suffix = _ROUND.search(raw, start)
    if suffix:
        end = suffix.start()
    core = raw[start:end]
    if not core.strip():
        return _unparsed(raw)
    parts = [*prefixes, _part(raw, "core", core, start, end)]
    if suffix:
        unit = suffix.group(2)
        parts.append(_part(raw, "round" if unit == "轮" else "game", suffix.group(1) + unit, end, len(raw)))
    if len(parts) == 1:
        # Only previously unparsed values: one explicit interior edition marker.
        # Multiple numbered fragments need series-specific semantic review.
        edition = _INFIX_EDITION.search(raw)
        if (
            edition and edition.start() > 0 and edition.end() < len(raw)
            and len(_EXPLICIT_NUMBERED_FRAGMENT.findall(raw)) == 1
            and raw[:edition.start()].strip() and raw[edition.end():].strip()
        ):
            return _result(raw, [
                _part(raw, "core", raw[:edition.start()], 0, edition.start()),
                _part(raw, "edition", edition.group(1) + edition.group(2), edition.start(), edition.end()),
                _part(raw, "core", raw[edition.end():], edition.end(), len(raw)),
            ], "single_edition_fragment")
        # Fallback after all existing grammars, with no normalization or identity inference.
        round_fragment = _SINGLE_ROUND_FRAGMENT.fullmatch(raw)
        if round_fragment and raw.count("第") == 1 and round_fragment.group("left").strip():
            round_start = round_fragment.end("left")
            round_end = round_fragment.end("number") + 1
            round_parts = [
                _part(raw, "core", round_fragment.group("left"), 0, round_start),
                _part(raw, "round", round_fragment.group("number") + "轮", round_start, round_end),
            ]
            if round_fragment.group("tail"):
                round_parts.append(_part(raw, "core", round_fragment.group("tail"), round_end, len(raw)))
            return _result(raw, round_parts, "single_round_fragment")
    return _result(raw, parts, "explicit_components" if len(parts) > 1 else "unparsed")


def _canonical_hash(value: dict) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _selected_event_rows(inventory: dict, original_events: dict[int, str | None]) -> dict[int, str]:
    if inventory["inventory_format"] == 2:
        if "event_selection" in inventory:
            raise ValueError("inventory_format 2 cannot include event selection")
        return {}
    if inventory["inventory_format"] == 4:
        from katrain.web.kifu.name_candidates import _selection_rows

        selected = {}
        for row in _selection_rows(inventory):
            album_id, raw = row[:2]
            if album_id not in original_events:
                raise ValueError("event selection album ID is absent from inventory")
            if original_events[album_id] != "GNUGo3.8":
                raise ValueError("event selection original event is not GNUGo3.8")
            selected[album_id] = raw
        return selected
    selection = inventory.get("event_selection")
    if (
        not isinstance(selection, dict)
        or selection.get("selection_format") != 1
        or selection.get("columns") != list(SELECTION_COLUMNS)
        or not isinstance(selection.get("rows"), list)
        or not _SHA256.fullmatch(str(inventory.get("base_sha256", "")))
    ):
        raise ValueError("inventory event selection supplement is incomplete")
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
    selected = {}
    previous_id = -1
    for row in selection["rows"]:
        if not isinstance(row, list) or len(row) != len(SELECTION_COLUMNS):
            raise ValueError("event selection row is malformed")
        album_id, raw, sgf_sha, reviewer, reviewed_at, batch_id, bundle_sha = row
        if not (
            type(album_id) is int and album_id > previous_id
            and isinstance(raw, str) and bool(raw.strip())
            and isinstance(sgf_sha, str) and _SHA256.fullmatch(sgf_sha)
            and isinstance(reviewer, str) and bool(reviewer)
            and isinstance(reviewed_at, str) and bool(reviewed_at)
            and type(batch_id) is int and batch_id > 0
            and isinstance(bundle_sha, str) and _SHA256.fullmatch(bundle_sha)
        ):
            raise ValueError("event selection row is invalid or unsorted")
        if album_id not in original_events:
            raise ValueError("event selection album ID is absent from inventory")
        if original_events[album_id] != "GNUGo3.8":
            raise ValueError("event selection original event is not GNUGo3.8")
        selected[album_id] = raw
        previous_id = album_id
        _hash_row(digest, b"E", row)
    if selection.get("sha256") != digest.hexdigest():
        raise ValueError("event selection supplement hash mismatch")
    return selected


def build_event_group_manifest(inventory: dict, *, expected_artifact_sha256: str | None = None) -> dict:
    """Group every raw EV spelling for finite, separately reviewed batch manifests."""
    if inventory.get("inventory_format") not in {2, 3, 4}:
        raise ValueError("inventory_format 2, 3 or 4 is required")
    if inventory["inventory_format"] in {3, 4} or expected_artifact_sha256 is not None:
        if not isinstance(expected_artifact_sha256, str) or not _SHA256.fullmatch(expected_artifact_sha256):
            raise ValueError("external inventory artifact SHA-256 is required")
        if _canonical_hash(inventory) != expected_artifact_sha256:
            raise ValueError("inventory artifact SHA-256 differs from pinned checksum")
    if not _SHA256.fullmatch(str(inventory.get("sha256", ""))):
        raise ValueError("inventory SHA-256 is required")
    rows = inventory["scopes"]["all"]["values"]["event"]
    seen = set()
    inventory_counts = Counter()
    for row in rows:
        raw = row["value"]
        if raw in seen:
            raise ValueError(f"duplicate raw event value: {raw!r}")
        seen.add(raw)
        if type(row["occurrences"]) is not int or row["occurrences"] < 1:
            raise ValueError("event occurrence count must be positive")
        if row.get("affected_games") != row["occurrences"]:
            raise ValueError("event affected_games must equal occurrences")
        inventory_counts[raw] = row["occurrences"]
        if raw is not None and not isinstance(raw, str):
            raise ValueError("raw event value must be text or null")

    expected_distinct = inventory.get("distinct_values", {}).get("all", {}).get("event")
    expected_total = inventory.get("counts", {}).get("all")
    columns = inventory.get("association_columns", [])
    associations = inventory.get("album_associations", [])
    if "id" not in columns or "event" not in columns:
        raise ValueError("incomplete inventory: album event associations are required")
    id_index, event_index = columns.index("id"), columns.index("event")
    association_counts = Counter()
    original_events = {}
    for association in associations:
        if len(association) != len(columns):
            raise ValueError("incomplete inventory: malformed album association")
        album_id = association[id_index]
        if album_id in original_events:
            raise ValueError("incomplete inventory: duplicate album association")
        original_events[album_id] = association[event_index]
        association_counts[original_events[album_id]] += 1
    if (
        expected_distinct != len(rows)
        or expected_total != len(associations)
        or sum(inventory_counts.values()) != expected_total
        or inventory_counts != association_counts
    ):
        raise ValueError("incomplete inventory: event values disagree with album associations or counts")

    selected = _selected_event_rows(inventory, original_events)
    effective_counts = Counter(selected.get(album_id, raw) for album_id, raw in original_events.items())
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for raw, count in effective_counts.items():
        if raw is None or raw == "":
            structure = {
                "raw_value": raw, "core": "", "grammar": "empty", "parts": [], "components": [],
                "status": "pending_review", "rule_version": RULE_VERSION, "exceptions": [],
            }
        else:
            structure = structure_event(raw)
        groups[(structure["grammar"], structure["core"])].append({
            "raw_value": raw, "occurrences": count, "affected_games": count, "structure": structure,
        })

    result_groups = []
    for (grammar, core), members in groups.items():
        members.sort(key=lambda item: (item["raw_value"] is not None, (item["raw_value"] or "").encode("utf-8")))
        group = {
            "grammar": grammar,
            "core": core,
            "status": "pending_review",
            "occurrences": sum(item["occurrences"] for item in members),
            "affected_games": sum(item["affected_games"] for item in members),
            "members": members,
        }
        group["sha256"] = _canonical_hash(group)
        result_groups.append(group)
    result_groups.sort(key=lambda item: (-item["occurrences"], item["grammar"], item["core"].encode("utf-8")))
    manifest = {
        "inventory_format": inventory["inventory_format"],
        "inventory_sha256": inventory["sha256"],
        **({"inventory_artifact_sha256": expected_artifact_sha256}
           if inventory["inventory_format"] in {3, 4} else {}),
        **({"event_selection_sha256": inventory["event_selection"]["sha256"]}
           if inventory["inventory_format"] in {3, 4} else {}),
        "rule_version": RULE_VERSION,
        "group_count": len(result_groups),
        "groups": result_groups,
    }
    manifest["sha256"] = _canonical_hash(manifest)
    return manifest
