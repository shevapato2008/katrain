"""Pure, exact-scope checks for literal translations of existing raw event titles."""

import hashlib
import json
import re
from datetime import datetime, timezone


VERSION = "raw-event-title-translation-v1"
OWNER_REVIEW_VERSION = "raw-event-title-owner-review-v1"
PRIMARY_LANGUAGES = frozenset({"cn", "tw", "jp", "ko", "en"})
_ORDINAL = re.compile(r"第[一二三四五六七八九十百千万0-9０-９]+(?:届|屆|轮|輪)\Z")
_YEAR = re.compile(r"(?:18|19|20)\d{2}年\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


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
    if not isinstance(owner, dict) or set(owner) != {"kind", "id"} or owner["kind"] != "raw_event":
        raise ValueError("literal raw title needs an existing raw event ID")
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
    if any(part["kind"] not in {"core", "year", "edition", "round"}
           or part["kind"] in {"edition", "round"} and not _ORDINAL.fullmatch(part["text"])
           or part["kind"] == "year" and not _YEAR.fullmatch(part["text"])
           for part in parts):
        raise ValueError("literal raw title has an unsupported year or ordinal")
    if len({part["kind"] for part in parts}) != len(parts):
        raise ValueError("literal raw title repeats a component")
    checks = record.get("source_checks")
    if not isinstance(checks, list) or not any(
        isinstance(check, dict) and check.get("owner") == owner and check.get("status") == "found"
        and check.get("candidate_name") == cores[0] and cores[0] in str(check.get("body_excerpt", ""))
        and check.get("url") == record.get("original_language_basis_url")
        and _SHA.fullmatch(str(check.get("body_sha256", "")))
        for check in checks
    ):
        raise ValueError("literal raw title core lacks captured source evidence")
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
                    and review["producer_id"] and review["producer_model"]
                    and review["reviewer_id"] and review["reviewer_model"]
                    and review["producer_id"] != review["reviewer_id"]
                    and _time(review["produced_at"]) and _time(review["reviewed_at"])
                    and _time(review["reviewed_at"]) >= _time(review["produced_at"])
                    and review["review_conclusion"] and review["category_basis"])
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
        if not (candidate.get("producer_id") == research.get("producer_id") == evidence["producer_id"]
                and candidate.get("producer_model") == research.get("producer_model") == evidence["producer_model"]
                and candidate.get("reviewer_id") == evidence["reviewer_id"]
                and candidate.get("reviewer_model") == evidence["reviewer_model"]
                and _time(candidate.get("produced_at")) == _stored_time(evidence.get("produced_at"))
                and _time(candidate.get("reviewed_at")) == _stored_time(evidence.get("reviewed_at"))
                and candidate.get("reviewer_id") != candidate.get("producer_id")
                and candidate.get("review_conclusion")
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
