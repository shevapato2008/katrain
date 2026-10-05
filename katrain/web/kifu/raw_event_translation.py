"""Pure, exact-scope checks for literal translations of existing raw event titles."""

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


VERSION = "raw-event-title-translation-v1"
OWNER_REVIEW_VERSION = "raw-event-title-owner-review-v1"
PRIMARY_LANGUAGES = frozenset({"cn", "tw", "jp", "ko", "en"})
TOKYO11_RAW_VALUES = frozenset(
    f"{ordinal} Tokyo Shinbun Cup"
    for ordinal in ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th")
)
GEOGRAPHIC39_RAW_VALUES = frozenset({
    "2001年中国围棋段位赛",
    "2007年中国围棋段位赛第一轮",
    "2007年中国围棋段位赛第12轮",
    "2007年中国围棋段位赛第六轮",
    "2005年中国围棋段位赛",
    "2013年中国围棋段位赛",
    "2002年中国围棋段位赛",
    "2007年中国围棋段位赛第二轮",
    "2007年中国围棋段位赛第九轮",
    "2004年中国围棋段位赛",
    "2007年中国围棋段位赛第11轮",
    "2007年中国围棋段位赛第七轮",
    "2007年中国围棋段位赛第三轮",
    "2007年中国围棋段位赛第五轮",
    "2007年中国围棋段位赛第八轮",
    "2007年中国围棋段位赛第十轮",
    "2007年中国围棋段位赛第四轮",
    "2008年中国围棋段位赛第12轮",
    "2008年中国围棋段位赛第三轮",
    "2008年中国围棋段位赛第五轮",
    "2008年中国围棋段位赛第八轮",
    "2008年中国围棋段位赛第六轮",
    "2008年中国围棋段位赛第四轮",
    "2004年中国围棋段位赛第10轮",
    "2004年中国围棋段位赛第11轮",
    "2004年中国围棋段位赛第12轮",
    "2004年中国围棋段位赛第4轮",
    "2004年中国围棋段位赛第5轮",
    "2004年中国围棋段位赛第6轮",
    "2004年中国围棋段位赛第7轮",
    "2004年中国围棋段位赛第8轮",
    "2004年中国围棋段位赛第9轮",
    "2007年中国围棋段位赛第10轮",
    "2008年中国围棋段位赛第11轮",
    "2008年中国围棋段位赛第一轮",
    "2008年中国围棋段位赛第七轮",
    "2008年中国围棋段位赛第九轮",
    "2008年中国围棋段位赛第二轮",
    "2008年中国围棋段位赛第十轮",
})
_ORDINAL = re.compile(r"第[一二三四五六七八九十百千万0-9０-９]+(?:届|屆|轮|輪)\Z")
_YEAR = re.compile(r"(?:18|19|20)\d{2}年\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")
_UNSAFE = re.compile(r"[\[\]\x00-\x1f]")
_DISPLAY_SCRIPT = {
    "en": re.compile(r"[A-Za-z]"),
    "cn": re.compile(r"[\u3400-\u9fff]"),
    "tw": re.compile(r"[\u3400-\u9fff]"),
    "jp": re.compile(r"[\u3400-\u9fff\u3040-\u30ff]"),
    "ko": re.compile(r"[\u3400-\u9fff\uac00-\ud7af]"),
}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _https_url(value):
    if not _text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def _matches_language(observed, target):
    if not _text(observed) or not _text(target):
        return False
    observed = observed.lower().replace("_", "-")
    target = target.lower()
    if observed in {"mul", "und", "auto", "fallback"}:
        return False
    if target == "zh-hans":
        return observed == "zh-hans" or observed.startswith("zh-hans-") or observed in {"zh-cn", "zh-sg"}
    if target == "zh-hant":
        return observed == "zh-hant" or observed.startswith("zh-hant-") or observed in {"zh-tw", "zh-hk", "zh-mo"}
    return observed == target or observed.startswith(target + "-")


def _hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _time(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except (AttributeError, ValueError):
        return None


def _stored_time(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (AttributeError, ValueError):
        return None


def validate_raw_title_research(record):
    """Bind the sourced core to every exact, losslessly parsed raw component."""
    owner = record.get("owner")
    if (not isinstance(owner, dict) or set(owner) != {"kind", "id"} or owner["kind"] != "raw_event"
            or type(owner["id"]) is not int or owner["id"] <= 0):
        raise ValueError("literal raw title needs an existing raw event ID")
    lang = record.get("lang")
    display = record.get("candidate_name")
    original_language = record.get("original_language")
    if (lang not in PRIMARY_LANGUAGES or not _text(display) or len(display) > 4096
            or _UNSAFE.search(display) or not _DISPLAY_SCRIPT[lang].search(display)):
        raise ValueError("literal raw title needs a valid primary-language display")
    if (record.get("scope_status") != "translated_from_original"
            or record.get("translation_method") != "literal_event_title"
            or not _text(record.get("registry_version"))
            or not _SHA.fullmatch(str(record.get("registry_sha256", "")))
            or not _text(record.get("producer_id")) or not _text(record.get("producer_model"))
            or record.get("review_status") != "pending"
            or any(record.get(key) for key in ("reviewer_id", "reviewer_model", "reviewed_at"))):
        raise ValueError("literal raw title research provenance is incomplete")
    if (not _text(original_language) or not _LANGUAGE.fullmatch(original_language)
            or not _https_url(record.get("original_language_basis_url"))):
        raise ValueError("literal raw title needs an original language and captured source URL")
    raw = record.get("raw_value")
    parts = record.get("raw_parts")
    if not isinstance(raw, str) or not isinstance(parts, list) or not parts:
        raise ValueError("literal raw title needs exact raw text and parts")
    if any(not isinstance(part, dict) or set(part) != {"kind", "text"}
           or not isinstance(part["text"], str) or not part["text"] for part in parts):
        raise ValueError("literal raw title has an invalid component")
    if "".join(part["text"] for part in parts) != raw:
        raise ValueError("literal raw title parts must reproduce exact raw text")
    cores = [part["text"] for part in parts if part["kind"] == "core"]
    if len(cores) != 1 or cores[0] != record.get("original_name"):
        raise ValueError("literal raw title must have one sourced core")
    tokyo_edition = raw in TOKYO11_RAW_VALUES and parts == [
        {"kind": "edition", "text": raw.removesuffix("Tokyo Shinbun Cup")},
        {"kind": "core", "text": "Tokyo Shinbun Cup"},
    ]
    if any(part["kind"] not in {"core", "year", "edition", "round", "geographic_qualifier"}
           or part["kind"] in {"edition", "round"} and not _ORDINAL.fullmatch(part["text"])
           and not (part["kind"] == "edition" and tokyo_edition)
           or part["kind"] == "year" and not _YEAR.fullmatch(part["text"])
           for part in parts):
        raise ValueError("literal raw title has an unsupported year or ordinal")
    if len({part["kind"] for part in parts}) != len(parts):
        raise ValueError("literal raw title repeats a component")
    geographic = [(index, part) for index, part in enumerate(parts) if part["kind"] == "geographic_qualifier"]
    if raw in GEOGRAPHIC39_RAW_VALUES:
        if (len(geographic) != 1 or geographic[0][1]["text"] != "中国"
                or geographic[0][0] + 1 >= len(parts)
                or parts[geographic[0][0] + 1] != {"kind": "core", "text": "围棋段位赛"}):
            raise ValueError("fixed geographic title needs 中国 immediately before its sourced core")
    elif geographic:
        raise ValueError("geographic qualifier is outside the fixed raw title scope")
    checks = record.get("source_checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("literal raw title core lacks captured source evidence")
    for check in checks:
        if (not isinstance(check, dict) or check.get("owner") != owner or check.get("status") != "found"
                or check.get("candidate_name") != cores[0] or not _text(check.get("query"))
                or not _text(check.get("source_id")) or not _text(check.get("identity_basis"))
                or not _https_url(check.get("url")) or not _time(check.get("fetched_at"))
                or check.get("http_status") != 200
                or not _SHA.fullmatch(str(check.get("body_sha256", "")))
                or not _text(check.get("body_excerpt")) or cores[0] not in check["body_excerpt"]
                or check.get("language_basis") not in {"html_lang", "http_header", "reviewed_text"}
                or not _matches_language(check.get("observed_lang"), original_language)
                or check.get("fallback")
                or check.get("returned_lang") and not _matches_language(check["returned_lang"], original_language)):
            raise ValueError("literal raw title source capture or identity evidence is incomplete")
    if not any(check["url"] == record["original_language_basis_url"] for check in checks):
        raise ValueError("literal raw title original-language source was not captured")
    return True


def eligible_raw_title_owner(raw_owner):
    """A raw ID becomes readable only through its finite independent owner review."""
    try:
        review = raw_owner["review_metadata"]
        return bool(raw_owner["category"] == "unclassified_pending"
                    and raw_owner["review_status"] == review["status"] == review["review_status"] == "approved"
                    and review["version"] == OWNER_REVIEW_VERSION
                    and review["raw_event_id"] == raw_owner["id"]
                    and review["raw_value"] == raw_owner["raw_value"]
                    and _SHA.fullmatch(review["scope_sha256"])
                    and _SHA.fullmatch(review["research_manifest_sha256"])
                    and _text(review["producer_id"]) and _text(review["producer_model"])
                    and _text(review["reviewer_id"]) and _text(review["reviewer_model"])
                    and review["producer_id"] != review["reviewer_id"]
                    and _time(review["produced_at"]) and _time(review["reviewed_at"])
                    and _time(review["reviewed_at"]) >= _time(review["produced_at"])
                    and _text(review["review_conclusion"]) and _text(review["category_basis"]))
    except (KeyError, TypeError, AttributeError, ValueError):
        return False


def eligible_literal_raw_name(name, evidence, raw_owner):
    """Recheck the same persisted owner, candidate, source, and approval on every reader."""
    try:
        if not eligible_raw_title_owner(raw_owner):
            return False
        if name["decision_kind"] != "translated" or evidence["decision_kind"] != "translated":
            return False
        if not (name["generation_rule_version"] == evidence["generation_rule_version"] == VERSION):
            return False
        if not (name["status"] == "verified"
                and evidence["review_status"] == raw_owner["review_status"] == "approved"):
            return False
        if not (name["raw_event_id"] == evidence["raw_event_id"] == raw_owner["id"]
                and name["lang"] == evidence["lang"] in PRIMARY_LANGUAGES
                and name["display_name"] == evidence["candidate_name"]
                and name["revision"] == evidence["revision"]):
            return False
        payload = evidence["research_payload"]
        candidate, research = payload["candidate"], payload["research"]
        if not isinstance(candidate, dict) or not isinstance(research, dict):
            return False
        owner = {"kind": "raw_event", "id": raw_owner["id"]}
        if not (candidate.get("owner") == research.get("owner") == owner
                and candidate.get("raw_value") == research.get("raw_value") == raw_owner["raw_value"]
                and candidate.get("lang") == research.get("lang") == name["lang"]
                and candidate.get("display_name") == research.get("candidate_name") == name["display_name"]
                and candidate.get("decision_kind") == name["decision_kind"]
                and candidate.get("generation_rule_version") == VERSION
                and candidate.get("translation_method") == research.get("translation_method") == "literal_event_title"
                and candidate.get("research_sha256") == _hash(research)
                and research.get("scope_status") == "translated_from_original"
                and research.get("review_status") == "pending"
                and candidate.get("review_status") == "approved"):
            return False
        if not (_text(candidate.get("producer_id")) and _text(candidate.get("producer_model"))
                and _text(candidate.get("reviewer_id")) and _text(candidate.get("reviewer_model"))
                and _text(candidate.get("review_conclusion"))
                and candidate.get("producer_id") == research.get("producer_id") == evidence["producer_id"]
                and candidate.get("producer_model") == research.get("producer_model") == evidence["producer_model"]
                and candidate.get("reviewer_id") == evidence["reviewer_id"]
                and candidate.get("reviewer_model") == evidence["reviewer_model"]
                and _time(candidate.get("produced_at")) == _stored_time(evidence.get("produced_at"))
                and _time(candidate.get("reviewed_at")) == _stored_time(evidence.get("reviewed_at"))
                and candidate.get("reviewer_id") != candidate.get("producer_id")
                and _time(candidate.get("produced_at"))
                and _time(candidate.get("reviewed_at"))
                and _time(candidate["reviewed_at"]) >= _time(candidate["produced_at"])):
            return False
        if any(_time(check.get("fetched_at")) is None or _time(candidate["reviewed_at"]) < _time(check["fetched_at"])
               for check in research.get("source_checks", [])):
            return False
        return validate_raw_title_research(research)
    except (KeyError, TypeError, AttributeError, ValueError):
        return False
