"""Lossless structural hints for raw event strings.

These hints never establish an event identity or approve a translated display.
"""

import re

from katrain.web.kifu.name_parse import parse_event


RULE_VERSION = "event-components-v1"
_YEAR = re.compile(r"([12]\d{3})年(?:度)?\s*")
_NUMBER = r"(?:[0-9]{1,3}|[一二三四五六七八九]|十[一二三四五六七八九]?|[一二三四五六七八九]十[一二三四五六七八九]?)"
_EDITION = re.compile(rf"(?:(?:第)?({_NUMBER})|首)(届|期)\s*")
_ROUND = re.compile(rf"\s*(?:第)?({_NUMBER})(轮|局)\s*\Z")
_OTEAI_YEAR = re.compile(r"(Oteai)\s+([12]\d{3})\Z", re.IGNORECASE)
_CWI = re.compile(r"(JapanPromotionTournament),([12]\d{3}),(Spring|Fall)\Z", re.IGNORECASE)


def _part(raw: str, kind: str, value: str, start: int, end: int) -> dict:
    return {"kind": kind, "value": value, "text": raw[start:end], "start": start, "end": end}


def _result(raw: str, parts: list[dict], grammar: str, exceptions: list[str] | None = None) -> dict:
    core = next(part["text"] for part in parts if part["kind"] == "core")
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
    return _result(raw, parts, "explicit_components" if len(parts) > 1 else "unparsed")
