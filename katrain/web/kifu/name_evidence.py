"""Validate auditable, pending kifu-name research records.

This module checks evidence format, not whether a name is historically correct.
Independent language review and the database import gate handle approval.
"""

from __future__ import annotations

import json
import re
import hashlib
import time
import unicodedata
from copy import deepcopy
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from katrain.web.kifu.raw_event_translation import SGF_LITERAL_BASIS, validate_raw_title_research


DEFAULT_REGISTRY = Path(__file__).resolve().parents[3] / "docs/resource/kifu-name-source-registry.json"
OWNER_KINDS = {"player", "event", "raw_player", "raw_event"}
CHECK_STATUSES = {"found", "not_found", "incomplete", "unavailable"}
SCOPE_STATUSES = {"found", "not_found_in_scope", "incomplete", "translated_from_original"}
LANGUAGE_BASIS = {"html_lang", "http_header", "reviewed_text"}
SECONDARY_LANGUAGES = {"de", "es", "fr", "ru", "tr", "ua"}
TRANSCRIPTION_SYSTEMS = {
    "zh-Hans": "pinyin-syllables-v1",
    "zh-Hant": "pinyin-syllables-v1",
    "ja": "hepburn-syllables-v1",
    "ko": "rr-syllables-v1",
}
READING_NORMALIZATION_VERSIONS = {
    "pinyin-syllables-v1": "pinyin-source-v1",
    "hepburn-syllables-v1": "hepburn-source-v1",
    "rr-syllables-v1": "rr-source-v1",
}
SOURCE_PRIORITY = {"official": 0, "language_go": 1, "reference": 2,
                   "wikipedia_article": 3, "encyclopedia": 3, "discovery": 4}
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OWNER_REF = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


class EvidenceError(ValueError):
    """A research claim lacks the evidence needed for review."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def owner_key(owner: object, lang: str) -> str:
    """Pin one existing DB ID or one new identity's bundle-local reference."""
    _require(isinstance(owner, dict) and owner.get("kind") in OWNER_KINDS, "one exact owner is required")
    if set(owner) == {"kind", "id"}:
        _require(type(owner["id"]) is int and owner["id"] > 0, "owner ID invalid")
        token = str(owner["id"])
    elif set(owner) == {"kind", "ref"}:
        _require(isinstance(owner["ref"], str) and bool(_OWNER_REF.fullmatch(owner["ref"])),
                 "owner symbolic reference invalid")
        token = "@" + owner["ref"]
    else:
        raise EvidenceError("one exact owner ID or symbolic reference is required")
    return f"{owner['kind']}:{token}:{lang}"


def _https_url(value: object) -> bool:
    if not _text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def _source_url_matches(url: str, source: dict) -> bool:
    if not _https_url(url):
        return False
    url_host = urlparse(url).hostname or ""
    source_host = urlparse(source["home_url"]).hostname or ""
    return url_host == source_host or url_host.endswith("." + source_host)


def _aware_timestamp(value: object) -> bool:
    if not _text(value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def load_registry(path: str | Path = DEFAULT_REGISTRY) -> dict:
    """Load the pinned discovery scope; it does not assert that any name is verified."""
    registry = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(_text(registry.get("version")) and len(registry["version"]) <= 64,
             "registry version is required and must fit the database column")
    tags = registry.get("language_tags")
    _require(isinstance(tags, dict) and bool(tags), "registry language_tags are required")
    scopes = registry.get("language_scopes")
    _require(isinstance(scopes, dict) and set(scopes) == set(tags), "registry language scopes must cover all tags")
    sources = registry.get("sources")
    _require(isinstance(sources, list) and bool(sources), "registry sources are required")
    ids = [source.get("id") for source in sources]
    _require(all(_text(source_id) for source_id in ids) and len(ids) == len(set(ids)), "source IDs must be unique")
    for source in sources:
        _require(_https_url(source.get("home_url")), "source home_url must be HTTPS")
        _require(_text(source.get("tier")) and _text(source.get("language")), "source tier/language required")
    for lang, scope in scopes.items():
        required = scope.get("required_source_ids")
        _require(isinstance(required, list) and bool(required), f"{lang} scope must name sources")
        _require(all(source_id in ids for source_id in required), f"{lang} scope references unknown source")
        _require(isinstance(scope.get("complete_for_negative_claims"), bool), f"{lang} scope completion required")
    return registry


def registry_sha256(registry: dict) -> str:
    """Canonical content hash, independent of JSON whitespace and key order."""
    canonical = json.dumps(registry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_transliteration_review(record: dict, conclusion: str) -> dict:
    """Require independent approval of one immutable source, rule, or finite batch."""
    _require(isinstance(record, dict), "transliteration reviewed record required")
    content, approval = record.get("content"), record.get("approval")
    _require(isinstance(content, dict) and isinstance(approval, dict), "transliteration content and approval required")
    _require(
        approval.get("status") == "approved" and approval.get("content_sha256") == registry_sha256(content),
        "transliteration content lacks exact approval",
    )
    _require(
        all(_text(approval.get(field)) for field in ("producer_id", "producer_model", "reviewer_id", "reviewer_model"))
        and approval["producer_id"] != approval["reviewer_id"]
        and _aware_timestamp(approval.get("produced_at"))
        and _aware_timestamp(approval.get("reviewed_at"))
        and approval.get("conclusion") == conclusion,
        "transliteration needs independent signed approval",
    )
    _require(
        datetime.fromisoformat(approval["reviewed_at"].replace("Z", "+00:00"))
        >= datetime.fromisoformat(approval["produced_at"].replace("Z", "+00:00")),
        "transliteration review precedes production",
    )
    return content


def validate_transliteration_sources(
    sources: object, source_lang: str, reviewed_at: str, *, allowed_languages: frozenset[str] | None = None
) -> None:
    """Validate captured provenance, without fetching or making an absence claim."""
    _require(isinstance(sources, list) and bool(sources), "transliteration needs captured sources")
    review_time = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    for source in sources:
        _require(
            isinstance(source, dict)
            and _https_url(source.get("url"))
            and source.get("http_status") == 200
            and _aware_timestamp(source.get("fetched_at"))
            and bool(_HEX_SHA256.fullmatch(str(source.get("body_sha256", ""))))
            and _text(source.get("body_excerpt"))
            and _text(source.get("identity_basis"))
            and source.get("language_basis") in LANGUAGE_BASIS
            and any(
                _matches_target(str(source.get("observed_lang", "")), lang)
                for lang in (allowed_languages if allowed_languages is not None else (source_lang,))
            ),
            "transliteration source provenance or language invalid",
        )
        _require(
            review_time >= datetime.fromisoformat(source["fetched_at"].replace("Z", "+00:00")),
            "transliteration approval predates source capture",
        )


def _normalized_phonetic_reading(value: str, system: str) -> str:
    """Remove only the declared roman system's separators and pronunciation marks."""
    _require(len(value) <= 1024, "transliteration phonetic reading too long")
    text = unicodedata.normalize("NFD", value.lower())
    if system == "pinyin-syllables-v1":
        text = text.replace("u\u0308", "ü").replace("u:", "ü").replace("v", "ü")
        marks, tones = "\u0300\u0301\u0304\u030c", "12345"
    elif system == "hepburn-syllables-v1":
        marks, tones = "\u0304", ""
    else:
        marks, tones = "", ""
    letters = []
    for char in text:
        if char in " -’'ʼ" or char in marks or char in tones:
            continue
        _require(
            char in "abcdefghijklmnopqrstuvwxyz" or char == "ü" and system == "pinyin-syllables-v1",
            "transliteration source reading must be phonetic in the declared roman system",
        )
        letters.append(char)
    _require(bool(letters), "transliteration source reading needs phonetic letters")
    return "".join(letters)


def _validate_two_publisher_reading(content: dict, reviewed_at: str) -> None:
    """Bind an official Han name to one bilingual professional profile and its reading."""
    _require(
        content.get("entity_kind") == "player"
        and content["owner"]["kind"] == ("raw_player" if content.get("anchor_format") == 3 else "player")
        and content.get("source_lang") == "zh-Hans"
        and content.get("source_reading_kind") == "published_roman_name",
        "two-publisher reading supports only Chinese player profiles",
    )
    sources = content.get("sources")
    _require(
        isinstance(sources, list) and len(sources) == 3
        and [source.get("role") for source in sources if isinstance(source, dict)]
        == ["original", "identity_bridge", "reading"],
        "two-publisher reading needs original, bridge and reading records",
    )
    original, bridge, reading = sources
    for source, observed_language in ((original, "zh"), (bridge, "zh"), (reading, "en")):
        validate_transliteration_sources([source], observed_language, reviewed_at)
        if source is original:
            _require(
                _matches_target(source["observed_lang"], "zh-Hans"),
                "two-publisher official source is not Simplified Chinese",
            )
        elif source is bridge:
            _require(
                source["observed_lang"].lower() == "zh"
                or _matches_target(source["observed_lang"], "zh-Hans"),
                "two-publisher bridge source is not Simplified Chinese",
            )
        _require(
            all(_text(source.get(field)) for field in (
                "publisher_id", "person_id_namespace", "person_id", "exact_name", "birthdate", "record_locator"
            )),
            "two-publisher source person facts missing",
        )
        birthdate = source["birthdate"]
        try:
            valid_birthdate = bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", birthdate)) and date.fromisoformat(
                birthdate
            )
        except ValueError:
            valid_birthdate = False
        _require(valid_birthdate, "two-publisher birth date invalid")
        _require(
            source["exact_name"] in source["body_excerpt"] and birthdate in source["body_excerpt"],
            "two-publisher source excerpt does not identify the person and date",
        )
    _require(
        original["publisher_id"] == "china_go_association"
        and original["person_id_namespace"] == "cwa_player_no"
        and bool(re.fullmatch(r"CWA[0-9]{6}", original["person_id"]))
        and original["url"] == "https://wqapi.cwql.org.cn/playerInfo/professional/list"
        and original["person_id"] in original["body_excerpt"],
        "two-publisher official roster identity invalid",
    )
    for source, lang in ((bridge, "zh"), (reading, "en")):
        _require(
            source["publisher_id"] == "goratings"
            and source["person_id_namespace"] == "goratings_player_id"
            and bool(re.fullmatch(r"[1-9][0-9]*", source["person_id"]))
            and source["url"] == f"https://www.goratings.org/{lang}/players/{source['person_id']}.html",
            "two-publisher profile identity or language path invalid",
        )
    _require(
        original["exact_name"] == bridge["exact_name"] == content["original_name"]
        and reading["exact_name"] == content["source_reading"]
        and original["birthdate"] == bridge["birthdate"] == reading["birthdate"]
        and bridge["person_id"] == reading["person_id"],
        "two-publisher name, birth date or profile ID mismatch",
    )
    link = content.get("source_link")
    required_link_fields = {
        "method", "official_match_count", "official_scope_sha256", "unresolved_conflicts", "review_basis"
    }
    _require(
        isinstance(link, dict)
        and set(link) == required_link_fields
        and link["method"] == "official_name_dob_to_localized_profile_id_v1"
        and type(link["official_match_count"]) is int and link["official_match_count"] == 1
        and bool(_HEX_SHA256.fullmatch(str(link["official_scope_sha256"])))
        and link["official_scope_sha256"] == original["body_sha256"]
        and link["unresolved_conflicts"] == []
        and _text(link["review_basis"]),
        "two-publisher source link is unresolved or unbound",
    )
    published_words = content["source_reading"].split()
    reviewed_words = content["reading_words"]
    _require(
        len(published_words) == len(reviewed_words)
        and all(
            _normalized_phonetic_reading(published, content["reading_system"]) == "".join(syllables)
            for published, syllables in zip(published_words, reviewed_words)
        ),
        "two-publisher reading word boundaries differ from published name",
    )


def _validate_localized_raw_reading(content: dict, reviewed_at: str, produced_at: str, verify_captured_body: bool) -> None:
    """Bind a finite raw reading to captured GoRatings localized person records."""
    _require(
        content["entity_kind"] == "player"
        and content["owner"]["kind"] == "raw_player"
        and content.get("source_reading_kind") == "published_roman_name",
        "localized reading requires a raw player",
    )
    link = content.get("source_link")
    _require(
        isinstance(link, dict)
        and set(link) == {"method", "unresolved_conflicts", "review_basis"}
        and link["method"] == "localized_name_dob_to_profile_id_v1"
        and link["unresolved_conflicts"] == []
        and _text(link["review_basis"]),
        "localized source link unresolved or invalid",
    )
    sources = content.get("sources")
    different = content["raw_value"] != content["original_name"]
    has_raw_page = different and isinstance(sources, list) and len(sources) == 3
    roles = ["original", "reading"] + (["raw_spelling"] if has_raw_page else [])
    _require(
        isinstance(sources, list)
        and len(sources) == len(roles)
        and all(isinstance(source, dict) for source in sources)
        and [source.get("role") for source in sources] == roles,
        "localized reading needs exact localized person records",
    )
    lang_path = {"zh-Hans": "zh", "zh-Hant": "zh", "ja": "ja", "ko": "ko"}
    for source in sources:
        role = source["role"]
        lang = "en" if role == "reading" else content["source_lang"]
        if role == "raw_spelling":
            lang = source.get("observed_lang")
            _require(lang in {"zh", "zh-Hans", "zh-Hant", "ja", "ko"}, "raw spelling language invalid")
        validate_transliteration_sources(
            [source],
            lang,
            reviewed_at,
            allowed_languages=frozenset({lang, "zh"}) if lang in {"zh-Hans", "zh-Hant"} else None,
        )
        path_lang = "zh" if lang == "zh" else lang_path.get(lang, lang)
        _require(
            source.get("publisher_id") == "goratings"
            and source.get("person_id_namespace") == "goratings_player_id"
            and bool(re.fullmatch(r"[1-9][0-9]*", str(source.get("person_id", ""))))
            and source["url"] == f"https://www.goratings.org/{path_lang}/players/{source['person_id']}.html"
            and _text(source.get("record_locator")),
            "localized profile identity or language path invalid",
        )
        dob = source.get("birthdate", "")
        try:
            valid_dob = (
                isinstance(dob, str)
                and bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", dob))
                and date.fromisoformat(dob)
            )
        except ValueError:
            valid_dob = False
        _require(valid_dob, "localized birth date invalid")
        expected = (
            content["source_reading"]
            if role == "reading"
            else content["raw_value"] if role == "raw_spelling" else content["original_name"]
        )
        _require(source.get("exact_name") == expected, "localized exact name mismatch")
        try:
            _require(
                _text(source.get("body_path")) and source.get("body_encoding") == "utf-8",
                "localized captured body path or encoding invalid",
            )
            if verify_captured_body:
                raw = Path(source["body_path"]).read_bytes()
                body = raw.decode(source["body_encoding"])
            else:
                body = " " * source["record_span"][0] + source["body_excerpt"]
        except (OSError, UnicodeError) as exc:
            raise EvidenceError("localized captured body unavailable") from exc
        if verify_captured_body:
            _require(hashlib.sha256(raw).hexdigest() == source["body_sha256"], "localized captured body hash mismatch")
        spans = []
        for field in ("record_span", "name_span", "birthdate_span"):
            span = source.get(field)
            _require(
                isinstance(span, list)
                and len(span) == 2
                and all(type(value) is int for value in span)
                and 0 <= span[0] < span[1] <= len(body),
                "localized captured span invalid",
            )
            spans.append(span)
        record, name, birth = spans
        _require(
            all(record[0] <= span[0] < span[1] <= record[1] for span in (name, birth))
            and body[name[0] : name[1]] == expected
            and body[birth[0] : birth[1]] == dob
            and source["body_excerpt"] == body[record[0] : record[1]],
            "localized name and birth date must belong to the captured record",
        )
    _require(
        len({source["person_id"] for source in sources}) == 1 and len({source["birthdate"] for source in sources}) == 1,
        "localized profile ID or birth date mismatch",
    )
    if different:
        mapping = content.get("raw_original_mapping")
        if not has_raw_page or isinstance(mapping, dict) and "content" in mapping:
            mapping_content = validate_transliteration_review(mapping, "approved_exact_raw_original_mapping")
            _require(
                set(mapping_content) == {"raw_value", "original_name", "source_lang", "raw_display_scope_sha256",
                                         "method", "research_record_sha256", "research_record_url", "review_basis"}
                and all(mapping_content.get(field) == content[field] for field in
                        ("raw_value", "original_name", "source_lang", "raw_display_scope_sha256"))
                and mapping_content["method"] == "prior_reviewed_exact_raw_mapping_v1"
                and bool(_HEX_SHA256.fullmatch(str(mapping_content["research_record_sha256"])))
                and _https_url(mapping_content["research_record_url"])
                and _text(mapping_content["review_basis"])
                and datetime.fromisoformat(mapping["approval"]["reviewed_at"].replace("Z", "+00:00"))
                    <= datetime.fromisoformat(produced_at.replace("Z", "+00:00")),
                "localized prior mapping requires exact signed scope and research provenance",
            )
        else:
            _require(
                isinstance(mapping, dict)
                and set(mapping) == {"raw_value", "original_name", "review_basis"}
                and mapping["raw_value"] == content["raw_value"]
                and mapping["original_name"] == content["original_name"]
                and _text(mapping["review_basis"]),
                "localized raw spelling requires exact reviewed mapping",
            )
    else:
        _require("raw_original_mapping" not in content, "unexpected localized raw spelling mapping")
    published = content["source_reading"].split()
    _require(
        len(published) == len(content["reading_words"])
        and all(
            _normalized_phonetic_reading(word, content["reading_system"]) == "".join(tokens)
            for word, tokens in zip(published, content["reading_words"])
        ),
        "localized reading word boundaries differ from published name",
    )


def validate_transliteration_anchor(record: dict, *, verify_captured_body: bool = True) -> dict:
    """Check a source-approved original and segmented reading, never infer it from Hanzi."""
    _require(
        isinstance(record, dict) and record.get("evidence_kind") == "transliteration_anchor",
        "transliteration source anchor required",
    )
    content = validate_transliteration_review(record, "approved_original_name_and_reading")
    owner_key(content.get("owner"), "source")
    kind = content.get("entity_kind")
    _require(
        kind in {"player", "event"} and content["owner"]["kind"] in {kind, "raw_" + kind},
        "transliteration source entity category differs from owner",
    )
    if content["owner"]["kind"].startswith("raw_"):
        _require(_text(content.get("raw_value")), "transliteration raw source anchor needs exact raw spelling")
    else:
        _require("raw_value" not in content, "transliteration entity anchor cannot claim raw spelling")
    source_lang = content.get("source_lang")
    _require(
        source_lang in TRANSCRIPTION_SYSTEMS and content.get("reading_system") == TRANSCRIPTION_SYSTEMS[source_lang],
        "transliteration source reading system invalid",
    )
    _require(
        _text(content.get("original_name"))
        and len(content["original_name"]) <= 1024
        and not re.search(r"[\[\]\x00-\x1f]", content["original_name"]),
        "transliteration original name invalid",
    )
    words = content.get("reading_words")
    _require(
        isinstance(words, list)
        and 0 < len(words) <= 32
        and all(
            isinstance(word, list)
            and 0 < len(word) <= 32
            and all(isinstance(token, str) and re.fullmatch(r"[a-zü]{1,16}", token) for token in word)
            for word in words
        ),
        "transliteration reading needs explicit normalized syllable words",
    )
    _require(
        content.get("reading_text") == " ".join(token for word in words for token in word)
        and _text(content.get("source_reading"))
        and _text(content.get("reading_normalization_basis")),
        "transliteration source reading and normalization basis required",
    )
    _require(
        content.get("reading_normalization_version") == READING_NORMALIZATION_VERSIONS[content["reading_system"]],
        "transliteration reading normalization version invalid",
    )
    _require(
        _normalized_phonetic_reading(content["source_reading"], content["reading_system"])
        == "".join(token for word in words for token in word),
        "transliteration reviewed normalization differs from sourced phonetic reading",
    )
    sources = content.get("sources")
    anchor_format = content.get("anchor_format", 1)
    _require(type(anchor_format) is int and anchor_format in {1, 2, 3, 4}, "transliteration anchor format invalid")
    if anchor_format in {3, 4}:
        _require(
            content["owner"]["kind"] == "raw_player"
            and (anchor_format == 4 or content.get("raw_value") == content["original_name"])
            and bool(_HEX_SHA256.fullmatch(str(content.get("raw_display_scope_sha256", ""))))
            and all(
                _text(content.get(field))
                for field in ("original_language_basis", "reading_applicability_basis", "spelling_exceptions_basis")
            ),
            "raw transliteration anchor requires exact spelling, finite scope and reviewed applicability",
        )
    if anchor_format == 4:
        _validate_localized_raw_reading(
            content, record["approval"]["reviewed_at"], record["approval"]["produced_at"], verify_captured_body
        )
        _require(
            all(
                datetime.fromisoformat(record["approval"]["produced_at"].replace("Z", "+00:00"))
                >= datetime.fromisoformat(source["fetched_at"].replace("Z", "+00:00"))
                for source in sources
            ),
            "localized production predates source capture",
        )
    elif anchor_format in {2, 3}:
        _validate_two_publisher_reading(content, record["approval"]["reviewed_at"])
    else:
        _require(
            "source_link" not in content and "source_reading_kind" not in content,
            "two-publisher fields require anchor format 2",
        )
        validate_transliteration_sources(sources, source_lang, record["approval"]["reviewed_at"])
        _require(
            any(
                content["original_name"] in source["body_excerpt"]
                and content["source_reading"] in source["body_excerpt"]
                for source in sources
            ),
            "transliteration exact original and sourced reading must occur in captured body",
        )
    _require(
        not any(key in content or key in record for key in ("scope_status", "negative_closure", "absence_claim")),
        "transliteration must not claim absence of conventional names",
    )
    return deepcopy(record)


def negative_closure_evidence_sha256(record: dict) -> str:
    """Hash the exact finite scope, checks, and source-language anchors, excluding the review itself."""
    closure = record.get("negative_closure") or {}
    evidence = {
        "owner": record.get("owner"), "lang": record.get("lang"),
        "source_lang": record.get("source_lang"),
        "registry_sha256": record.get("registry_sha256"),
        "scope_id": closure.get("scope_id"), "scope_version": closure.get("scope_version"),
        "scope_boundary": closure.get("scope_boundary"),
        "retained_limitations": closure.get("retained_limitations"),
        "required_check_ids": closure.get("required_check_ids"),
        "required_checks": closure.get("required_checks"),
        "known_leads": closure.get("known_leads"),
        "scope_template_sha256": closure.get("scope_template_sha256"),
        "scope_sha256": closure.get("scope_sha256"),
        "source_checks": record.get("source_checks"),
        "original_name": record.get("original_name"),
        "original_language": record.get("original_language"),
        "original_language_basis_url": record.get("original_language_basis_url"),
        "reading": record.get("reading"), "reading_basis_url": record.get("reading_basis_url"),
    }
    if closure.get("version") == 2:
        evidence.update(version=2, search_policy=closure.get("search_policy"),
                        bounded_scan_ids=closure.get("bounded_scan_ids"),
                        unsearched_source_ids=closure.get("unsearched_source_ids"))
    canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _negative_scope_template(record: dict) -> dict:
    closure = record.get("negative_closure") or {}
    scope = {
        "lang": record.get("lang"),
        "source_lang": record.get("source_lang"), "registry_sha256": record.get("registry_sha256"),
        "scope_id": closure.get("scope_id"), "scope_version": closure.get("scope_version"),
        "scope_boundary": closure.get("scope_boundary"),
        "retained_limitations": closure.get("retained_limitations"),
        "required_check_ids": closure.get("required_check_ids"),
        "required_checks": closure.get("required_checks"), "known_leads": closure.get("known_leads"),
    }
    if closure.get("version") == 2:
        scope.update(version=2, search_policy=closure.get("search_policy"),
                     bounded_scan_ids=closure.get("bounded_scan_ids"),
                     unsearched_source_ids=closure.get("unsearched_source_ids"))
    return scope


def negative_closure_template_sha256(record: dict) -> str:
    """Hash a reusable scope template before binding it to a database owner."""
    scope = _negative_scope_template(record)
    canonical = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def negative_closure_scope_sha256(record: dict) -> str:
    """Identify reviewed obligations and their exact owner without hashing observed results."""
    scope = {"owner": record.get("owner"), "template_sha256": negative_closure_template_sha256(record)}
    canonical = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def product_language_tag(lang: str, registry: dict) -> str:
    try:
        return registry["language_tags"][lang]
    except (KeyError, TypeError) as exc:
        raise EvidenceError(f"unknown product language: {lang}") from exc


def source_plan(lang: str, registry: dict) -> list[dict]:
    """Return the registered target-language search scope in research order."""
    product_language_tag(lang, registry)
    sources = {source["id"]: source for source in registry["sources"]}
    required = registry["language_scopes"][lang]["required_source_ids"]
    return sorted((sources[source_id] for source_id in required),
                  key=lambda source: (SOURCE_PRIORITY.get(source["tier"], 99), source["id"]))


def _matches_target(observed: str, target: str) -> bool:
    observed = observed.lower().replace("_", "-")
    target = target.lower()
    if observed in {"mul", "und", "auto", "fallback", ""}:
        return False
    if target == "zh-hans":
        return observed == "zh-hans" or observed.startswith("zh-hans-") or observed in {"zh-cn", "zh-sg"}
    if target == "zh-hant":
        return observed == "zh-hant" or observed.startswith("zh-hant-") or observed in {"zh-tw", "zh-hk", "zh-mo"}
    return observed == target or observed.startswith(target + "-")


def _validate_discovery_label(check: dict, source: dict, target: str) -> None:
    """Require a separately captured language-specific API field for discovery leads."""
    evidence = check.get("label_evidence")
    _require(isinstance(evidence, dict), "discovery hit needs explicit API label evidence")
    api_url = evidence.get("api_url")
    _require(_source_url_matches(api_url, source), "API label URL must be on registered host")
    _require(urlparse(api_url).path.endswith(".json") or urlparse(api_url).path.endswith("/api.php"),
             "API label URL must identify a JSON or API response")
    _require(_aware_timestamp(evidence.get("fetched_at")), "API label timestamp required")
    _require(evidence.get("http_status") == 200, "API label response must have HTTP 200")
    _require(bool(_HEX_SHA256.fullmatch(str(evidence.get("response_sha256", "")))),
             "API label response hash required")
    pointer = evidence.get("json_pointer")
    _require(_text(pointer) and pointer.startswith("/") and "/labels/" in pointer
             and _matches_target(pointer.rsplit("/", 1)[-1], target),
             "API label field must explicitly name target language")
    if (urlparse(api_url).hostname or "").endswith("wikidata.org"):
        page_entity = re.fullmatch(r"/wiki/(Q[1-9][0-9]*)", urlparse(check["url"]).path)
        api_entity = re.fullmatch(r"/wiki/Special:EntityData/(Q[1-9][0-9]*)\.json", urlparse(api_url).path)
        _require(bool(page_entity and api_entity and page_entity.group(1) == api_entity.group(1)
                      and f"/entities/{page_entity.group(1)}/labels/" in pointer),
                 "Wikidata page, API and label pointer must identify the same entity")
    label = evidence.get("label")
    _require(isinstance(label, dict) and _text(label.get("language")) and _text(label.get("value")),
             "API label object must contain language and value")
    _require(_matches_target(label["language"], target) and label["value"] == check.get("candidate_name"),
             "API label language/value differs from candidate")
    _require(not check.get("label_lang") or check["label_lang"] == label["language"],
             "page label language conflicts with API label language")
    _require(evidence.get("fallback") is False, "API label cannot be a fallback")
    try:
        excerpt_label = json.loads(evidence.get("body_excerpt", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise EvidenceError("API label body excerpt must contain the returned label object") from exc
    _require(excerpt_label == label, "API label excerpt differs from the claimed label")


def _validate_article_evidence(check: dict, sources: dict[str, dict], original_name: str) -> None:
    """Article usage is separate from an API label and needs outside identity evidence."""
    source = sources[check["source_id"]]
    article = check.get("article_evidence")
    _require(isinstance(article, dict), "article needs captured article evidence")
    if source["tier"] == "wikipedia_article":
        _require(_text(article.get("revision_id")) and str(article["revision_id"]).isdigit(),
                 "Wikipedia article revision ID required")
    else:
        _require(_text(article.get("edition")) or _text(article.get("revision_id")),
                 "encyclopedia edition or revision required")
    passage = article.get("passage")
    _require(_text(article.get("title")) and _text(passage)
             and check["candidate_name"] in passage
             and passage in check["body_excerpt"]
             and hashlib.sha256(passage.encode("utf-8")).hexdigest() == article.get("passage_sha256")
             and _text(article.get("subject_identity")),
             "article title, exact passage/hash and subject identity required")
    corroboration = check.get("identity_corroboration")
    _require(isinstance(corroboration, dict), "article needs separately published identity corroboration")
    other_id = corroboration.get("source_id")
    _require(other_id in sources and sources[other_id]["tier"] in {"official", "language_go", "reference"}
             and _source_url_matches(corroboration.get("url"), sources[other_id]),
             "identity corroboration needs a registered independent reference")
    article_host = urlparse(check["url"]).hostname
    other_host = urlparse(corroboration["url"]).hostname
    _require(article_host != other_host, "identity corroboration must be separately published")
    _require(_aware_timestamp(corroboration.get("fetched_at")) and corroboration.get("http_status") == 200
             and bool(_HEX_SHA256.fullmatch(str(corroboration.get("body_sha256", ""))))
             and _text(corroboration.get("body_excerpt")) and _text(corroboration.get("identity_basis"))
             and corroboration.get("original_name") == original_name
             and original_name in corroboration["body_excerpt"],
             "corroboration needs real body evidence for the exact original name")


def _validate_negative_outcome(check: dict, source: dict, producer_id: str, *, finite: bool = False) -> None:
    outcome = check.get("negative_outcome")
    _require(outcome in {"no_target_string", "rejected_leads"},
             "completed negative source needs an explicit outcome")
    leads = check.get("rejected_leads", [])
    if outcome == "no_target_string":
        _require(not leads, "no-string outcome cannot hide rejected leads")
        return
    _require(isinstance(leads, list) and bool(leads), "rejected lead outcome needs lead records")
    for lead in leads:
        _require(isinstance(lead, dict) and _text(lead.get("candidate_name"))
                 and _source_url_matches(lead.get("url"), source)
                 and bool(_HEX_SHA256.fullmatch(str(lead.get("body_sha256", ""))))
                 and _text(lead.get("body_excerpt"))
                 and lead["candidate_name"] in lead["body_excerpt"]
                 and _text(lead.get("rejection_basis"))
                 and _text(lead.get("reviewer_id")) and lead["reviewer_id"] != producer_id
                 and lead.get("reviewer_model") == "gpt-6-sol"
                 and _aware_timestamp(lead.get("reviewed_at")),
                 "rejected lead needs sourced body and independent Sol rejection")
        if finite:
            _require(_text(lead.get("original_name")) and _text(lead.get("observed_lang"))
                     and lead.get("language_basis") in LANGUAGE_BASIS
                     and lead.get("decision") == "rejected_for_target_language",
                     "finite rejected lead needs original name, actual language and independent decision")


class _AnchorLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href"))


def _entity_excerpt(excerpt: object, entity_id: str) -> dict:
    try:
        response = json.loads(excerpt)
    except (TypeError, json.JSONDecodeError) as exc:
        raise EvidenceError("Wikidata entity evidence needs captured JSON") from exc
    entities = response.get("entities") if isinstance(response, dict) else None
    entity = entities.get(entity_id) if isinstance(entities, dict) else None
    _require(isinstance(entity, dict) and entity.get("id") == entity_id,
             "Wikidata captured entity differs from requested subject")
    return entity


def _validate_entity_identity(check: dict, record: dict, source: dict) -> None:
    """Bind target-field absence to a separately captured original-language subject label."""
    entity_scope = check["entity_field_scope"]
    entity_id = entity_scope["entity_id"]
    target_entity = _entity_excerpt(check.get("body_excerpt"), entity_id)
    for field in entity_scope["fields"]:
        values = target_entity.get(field, {})
        key = entity_scope["sitelink_site"] if field == "sitelinks" else entity_scope["requested_lang"]
        _require(isinstance(values, dict) and key not in values,
                 "Wikidata target field exists or is malformed; cannot claim absence")
    identity = check.get("entity_identity_evidence")
    _require(isinstance(identity, dict), "Wikidata needs separate entity identity evidence")
    api_url = identity.get("api_url")
    _require(_source_url_matches(api_url, source), "entity identity URL must be on registered Wikidata host")
    parsed = urlparse(api_url)
    params = parse_qs(parsed.query)
    _require(parsed.path == "/w/api.php" and params.get("action") == ["wbgetentities"]
             and params.get("ids") == [entity_id] and params.get("languages") == [record["source_lang"]]
             and params.get("props") == ["labels"] and params.get("format") == ["json"]
             and params.get("languagefallback", ["0"]) == ["0"],
             "entity identity request differs from exact entity or original language")
    _require(_aware_timestamp(identity.get("fetched_at")) and identity.get("http_status") == 200
             and bool(_HEX_SHA256.fullmatch(str(identity.get("response_sha256", ""))))
             and _text(identity.get("identity_basis")), "entity identity needs a completed separate capture")
    entity = _entity_excerpt(identity.get("body_excerpt"), entity_id)
    labels = entity.get("labels")
    label = labels.get(record["source_lang"]) if isinstance(labels, dict) else None
    _require(isinstance(label, dict) and _matches_target(str(label.get("language", "")), record["source_lang"])
             and label.get("value") == record["original_name"],
             "entity identity captured original name or language differs from research subject")


def _validate_negative_closure(record: dict, registry: dict, checks: list[dict]) -> None:
    closure = record.get("negative_closure")
    _require(isinstance(closure, dict), "finite negative closure must be an object")
    _require(type(closure.get("version")) is int and closure["version"] in {1, 2}
             and closure.get("owner") == record["owner"]
             and closure.get("lang") == record["lang"]
             and _text(record.get("source_lang"))
             and record["source_lang"] == record.get("original_language")
             and closure.get("source_lang") == record["source_lang"],
             "negative closure owner, language or source language mismatch")
    secondary = closure["version"] == 2
    if secondary:
        _require(record["lang"] in SECONDARY_LANGUAGES
                 and closure.get("search_policy") == "secondary_reasonable_v1",
                 "secondary reasonable search policy is restricted to the six secondary languages")
        bounded = closure.get("bounded_scan_ids")
        _require(isinstance(bounded, list) and all(_text(item) for item in bounded)
                 and len(bounded) == len(set(bounded)), "bounded scan IDs must be explicit and unique")
    else:
        bounded = []
    _require(_text(closure.get("scope_id")) and _text(closure.get("scope_version"))
             and _text(closure.get("scope_boundary"))
             and isinstance(closure.get("retained_limitations"), list)
             and all(_text(item) for item in closure["retained_limitations"]),
             "finite negative closure needs a named scope, boundary and limitations")
    _require(closure.get("registry_sha256") == record["registry_sha256"] == registry_sha256(registry),
             "negative closure registry mismatch")
    required = closure.get("required_check_ids")
    check_ids = [check.get("check_id") for check in checks]
    _require(isinstance(required, list) and bool(required)
             and all(_text(item) for item in required)
             and all(_text(item) for item in check_ids)
             and len(required) == len(set(required))
             and len(check_ids) == len(set(check_ids)) and set(required) == set(check_ids),
             "finite negative closure must bind every unique check ID")
    manifest = closure.get("required_checks")
    fields = ("check_id", "source_id", "method", "query", "url", "searched_forms",
              "entity_field_scope", "scan_id", "page_index", "page_count", "next_page_url",
              "pagination_exhausted", "pagination_basis")
    _require(isinstance(manifest, list) and len(manifest) == len(checks)
             and all(isinstance(item, dict) and set(item) == set(fields) for item in manifest)
             and all(_text(item["check_id"]) for item in manifest)
             and {item["check_id"] for item in manifest} == set(required),
             "finite negative closure needs an exact required check manifest")
    declared = {item["check_id"]: item for item in manifest}
    observed_checks = {check["check_id"]: check for check in checks}
    _require(all({field: check.get(field) for field in fields} == declared[check["check_id"]]
                 for check in checks), "source check differs from required check manifest")
    pages: dict[str, list[dict]] = {}
    for item in manifest:
        _require(type(item["page_index"]) is int and type(item["page_count"]) is int
                 and 1 <= item["page_index"] <= item["page_count"]
                 and _text(item["scan_id"]) and _text(item["pagination_basis"]),
                 "required check page index/count invalid")
        pages.setdefault(item["scan_id"], []).append(item)
    _require(set(bounded) <= set(pages), "bounded scan ID is absent from the manifest")
    sources = {source["id"]: source for source in registry["sources"]}
    for scan_id, group in pages.items():
        count = group[0]["page_count"]
        _require(all(item["page_count"] == count and item["source_id"] == group[0]["source_id"]
                     and item["method"] == group[0]["method"] and item["query"] == group[0]["query"]
                     for item in group)
                 and len(group) == count
                 and {item["page_index"] for item in group} == set(range(1, count + 1)),
                 "required check manifest omits or duplicates a page")
        by_page = {item["page_index"]: item for item in group}
        if secondary:
            _require(len({item["url"] for item in group}) == count,
                     "secondary scan cannot count duplicate page URLs")
        is_bounded = scan_id in bounded
        terminal = by_page[count]
        if is_bounded:
            _require(sources[terminal["source_id"]]["tier"] != "discovery"
                     and _source_url_matches(terminal["next_page_url"], sources[terminal["source_id"]])
                     and terminal["next_page_url"] not in {item["url"] for item in group}
                     and terminal["pagination_exhausted"] is False,
                     "bounded scan must retain a real unvisited next page without claiming exhaustion")
            captured = observed_checks[terminal["check_id"]]
            href, excerpt = captured.get("continuation_href"), captured.get("continuation_excerpt")
            _require(_text(href) and _text(excerpt), "bounded scan needs a captured continuation anchor")
            _require(excerpt in captured["body_excerpt"],
                     "bounded scan continuation anchor must occur in the captured terminal body")
            links = _AnchorLinks()
            links.feed(excerpt)
            _require(href in links.hrefs and urljoin(terminal["url"], href) == terminal["next_page_url"],
                     "bounded scan continuation anchor differs from the unvisited next page")
            _require(any(scan_id in limitation and terminal["next_page_url"] in limitation
                         for limitation in closure["retained_limitations"]),
                     "bounded scan needs a retained limitation naming its scan ID and remaining page URL")
        for index, item in by_page.items():
            expected_next = by_page[index + 1]["url"] if index < count else ""
            if index == count and is_bounded:
                expected_next = terminal["next_page_url"]
            _require(item["next_page_url"] == expected_next
                     and item["pagination_exhausted"] is (index == count and not is_bounded),
                     "required check page chain lacks terminal exhaustion evidence")
    registered = set(registry["language_scopes"][record["lang"]]["required_source_ids"])
    target = product_language_tag(record["lang"], registry)
    for item in manifest:
        if sources[item["source_id"]]["tier"] == "discovery":
            entity = item["entity_field_scope"]
            parsed = urlparse(item["url"])
            params = parse_qs(parsed.query)
            if secondary:
                _require(parsed.hostname in {"www.wikidata.org", "wikidata.org"},
                         "secondary discovery leg must check exact Wikidata entity fields")
                _require(params.get("languagefallback", ["0"]) == ["0"],
                         "secondary Wikidata check cannot request language fallback")
            _require(item["method"] == "entity_api" and isinstance(entity, dict)
                     and parsed.path == "/w/api.php"
                     and params.get("action") == ["wbgetentities"]
                     and params.get("format") == ["json"]
                     and set(entity) == {"entity_id", "requested_lang", "fields", "sitelink_site"}
                     and bool(re.fullmatch(r"Q[1-9][0-9]*", str(entity["entity_id"])))
                     and entity["requested_lang"] == target
                     and entity["sitelink_site"] == target.split("-")[0] + "wiki"
                     and isinstance(entity["fields"], list)
                     and all(_text(field) for field in entity["fields"])
                     and set(entity["fields"]) == {"labels", "aliases", "sitelinks"}
                     and params.get("ids") == [entity["entity_id"]]
                     and params.get("languages") == [target]
                     and set(params.get("props", [""])[0].split("|")) == set(entity["fields"]),
                     "discovery check needs exact entity and target-language fields")
            if secondary:
                _validate_entity_identity(observed_checks[item["check_id"]], record, sources[item["source_id"]])
        else:
            _require(item["entity_field_scope"] is None,
                     "non-entity check cannot claim entity fields")
    if secondary:
        _require(all(_matches_target(check.get("observed_lang", ""), target)
                     or check.get("negative_outcome") == "rejected_leads" for check in checks),
                 "secondary non-target-language checks need independently rejected leads")
        target_checks = [check for check in checks if _matches_target(check.get("observed_lang", ""), target)]
        tiers = {sources[check["source_id"]]["tier"] for check in target_checks
                 if _matches_target(sources[check["source_id"]]["language"], target)}
        _require(bool(tiers & {"official", "language_go"}),
                 "secondary reasonable search needs a target-language professional source")
        _require(bool(tiers & {"wikipedia_article", "encyclopedia"})
                 or any(sources[check["source_id"]]["tier"] == "discovery" for check in target_checks),
                 "secondary reasonable search needs a target-language encyclopedia or exact Wikidata check")
        unsearched = closure.get("unsearched_source_ids")
        completed_target_sources = {check["source_id"] for check in target_checks}
        _require(isinstance(unsearched, list) and all(_text(item) for item in unsearched)
                 and len(unsearched) == len(set(unsearched)) and set(unsearched) == registered - completed_target_sources,
                 "secondary scope must list exact unsearched registered source IDs")
        _require(all(any(source_id in limitation for limitation in closure["retained_limitations"])
                     for source_id in unsearched), "unsearched source needs an explicit retained limitation")
    else:
        _require(registered <= {check["source_id"] for check in checks
                                if _matches_target(check.get("observed_lang", ""), target)},
                 "finite negative closure lacks a completed target-language check for a required source")
    _require(all(check.get("status") == "not_found" and check.get("completeness") == "complete"
                 and check.get("scope_complete") is True and _text(check.get("method"))
                 and isinstance(check.get("searched_forms"), list) and bool(check["searched_forms"])
                 and all(_text(form) for form in check["searched_forms"])
                 and bool(_HEX_SHA256.fullmatch(str(check.get("response_sha256", ""))))
                 for check in checks), "finite negative closure has partial or unavailable checks")
    known_leads = closure.get("known_leads")
    _require(isinstance(known_leads, list)
             and all(isinstance(item, dict) and set(item) == {"check_id", "candidate_name", "url"}
                     and _text(item["check_id"]) and item["check_id"] in declared
                     and _text(item["candidate_name"])
                     and _https_url(item["url"]) for item in known_leads),
             "finite negative closure needs an explicit known lead list")
    _require(len({(item["check_id"], item["candidate_name"], item["url"])
                  for item in known_leads}) == len(known_leads), "duplicate known lead")
    for check in checks:
        leads = check.get("rejected_leads", [])
        _require(isinstance(leads, list) and all(isinstance(lead, dict) for lead in leads),
                 "rejected leads must be a list of records")
        _require(all(_text(lead.get("candidate_name")) for lead in leads),
                 "rejected lead needs a candidate name")
        forms = [*check["searched_forms"], record["original_name"],
                 *(item["candidate_name"] for item in known_leads if item["check_id"] == check["check_id"])]
        matched = {form.casefold() for form in forms
                   if form.casefold() in check["body_excerpt"].casefold()}
        rejected = {lead["candidate_name"].casefold() for lead in leads}
        _require(not matched or check.get("negative_outcome") == "rejected_leads" and matched <= rejected,
                 "captured known form needs an independently rejected lead")
    _require(all(any(check["check_id"] == item["check_id"]
                     and check.get("negative_outcome") == "rejected_leads"
                     and any(lead.get("candidate_name") == item["candidate_name"]
                             and lead.get("url") == item["url"] for lead in check.get("rejected_leads", []))
                     for check in checks) for item in known_leads),
             "declared known lead lacks adjudication")
    _require(_text(closure.get("reviewer_id")) and closure["reviewer_id"] != record["producer_id"]
             and _text(closure.get("reviewer_model")) and _aware_timestamp(closure.get("reviewed_at"))
             and closure.get("conclusion") == "approved_not_found_in_scope"
             and _text(closure.get("reason")),
             "finite negative closure needs independent signed approval of absence in scope")
    reviewed_at = datetime.fromisoformat(closure["reviewed_at"].replace("Z", "+00:00"))
    _require(all(reviewed_at >= datetime.fromisoformat(check["fetched_at"].replace("Z", "+00:00"))
                 for check in checks), "negative closure review precedes a source check")
    if secondary:
        _require(all(reviewed_at >= datetime.fromisoformat(check["entity_identity_evidence"]["fetched_at"].replace("Z", "+00:00"))
                     for check in checks if sources[check["source_id"]]["tier"] == "discovery"),
                 "negative closure review precedes entity identity capture")
    _require(all(reviewed_at >= datetime.fromisoformat(lead["reviewed_at"].replace("Z", "+00:00"))
                 for check in checks for lead in check.get("rejected_leads", [])
                 if _aware_timestamp(lead.get("reviewed_at"))),
             "negative closure precedes a rejected lead review")
    _require(closure.get("scope_template_sha256") == negative_closure_template_sha256(record),
             "finite negative closure scope template hash mismatch")
    _require(closure.get("scope_sha256") == negative_closure_scope_sha256(record),
             "finite negative closure scope hash mismatch")
    _require(closure.get("evidence_sha256") == negative_closure_evidence_sha256(record),
             "finite negative closure evidence hash mismatch")


def _validate_check(check: dict, owner: dict, target: str, sources: dict[str, dict],
                    *, finite_negative: bool = False) -> None:
    _require(isinstance(check, dict), "source check must be an object")
    _require(check.get("owner") == owner, "source check owner differs from research record")
    source_id = check.get("source_id")
    _require(source_id in sources, f"unknown source: {source_id}")
    _require(_text(check.get("query")), "each source check needs its own query")
    status = check.get("status")
    _require(status in CHECK_STATUSES, "invalid source check status")
    _require(_source_url_matches(check.get("url"), sources[source_id]),
             "source check URL must be HTTPS on registered host")
    _require(_aware_timestamp(check.get("fetched_at")), "source check needs timezone-aware timestamp")
    if status in {"incomplete", "unavailable"}:
        _require(not _text(check.get("candidate_name")), "incomplete source cannot claim a candidate")
        return
    _require(check.get("http_status") == 200, "completed search requires HTTP 200")
    _require(bool(_HEX_SHA256.fullmatch(str(check.get("body_sha256", "")))), "completed search needs body SHA-256")
    _require(_text(check.get("body_excerpt")), "completed search needs real body excerpt")
    _require(check.get("language_basis") in LANGUAGE_BASIS, "completed search needs actual-language basis")
    observed = check.get("observed_lang")
    _require(_text(observed), "actual page language must be recorded")
    if (sources[source_id]["tier"] != "discovery" or status == "not_found") and not (
        finite_negative and status == "not_found"
    ):
        _require(_matches_target(observed, target), "actual page language differs from target")
    returned = check.get("returned_lang")
    _require(not returned or _matches_target(returned, target), "returned label language differs from target")
    _require(not check.get("fallback"), "fallback label is not target-language evidence")
    if status == "found":
        _require(_text(check.get("candidate_name")), "found check needs candidate name")
        _require(check["candidate_name"] in check["body_excerpt"], "candidate must occur in captured body excerpt")
        _require(_text(check.get("identity_basis")), "found check needs identity matching basis")
        if sources[source_id]["tier"] == "discovery":
            _validate_discovery_label(check, sources[source_id], target)
    else:
        _require(not _text(check.get("candidate_name")), "not-found check cannot contain candidate")
        _require(check.get("scope_complete") is True and _text(check.get("search_scope")),
                 "not-found requires documented complete search scope")


POSITIVE_SOURCE_BASIS = "normative_ja_ko_v1"
POSITIVE_SCOPE = "generated_from_original"
POSITIVE_RULE = "nikl-ja-ko-personal-name-v1"
_POSITIVE_RULE_PAGES = {"personal_names": "P000146", "kana_table": "P000108", "japanese_details": "P000129"}


def positive_ja_ko_captures(record: dict) -> list[dict]:
    positive = record["positive_generation"]
    return [positive["identity"]["capture"], positive["reading"]["capture"],
            *[item["capture"] for item in positive["rules"]],
            *[item["capture"] for item in positive["conflict_queries"]]]


def _validate_positive_capture(capture: dict) -> None:
    fields = {"url", "http_status", "fetched_at", "body_text", "body_sha256", "body_excerpt",
              "locator", "source_role", "observed_lang"}
    _require(isinstance(capture, dict) and set(capture) == fields, "positive capture fields invalid")
    _require(_https_url(capture["url"]) and capture["http_status"] == 200
             and _aware_timestamp(capture["fetched_at"]), "positive capture requires actual usable HTTP 200")
    _require(all(_text(capture[key]) for key in ("body_text", "body_excerpt", "locator", "source_role", "observed_lang")),
             "positive capture needs actual body, excerpt, locator and source role")
    _require(capture["body_sha256"] == hashlib.sha256(capture["body_text"].encode("utf-8")).hexdigest()
             and capture["body_excerpt"] in capture["body_text"], "positive capture body hash/excerpt mismatch")


def _validate_positive_ja_ko(record: dict) -> None:
    _require(record.get("source_basis") == POSITIVE_SOURCE_BASIS
             and record.get("scope_status") == POSITIVE_SCOPE
             and record.get("generation_rule_version") == POSITIVE_RULE
             and record["owner"]["kind"] == "player" and set(record["owner"]) == {"kind", "id"}
             and record["lang"] == "ko" and record.get("original_language") == "ja",
             "positive generation is restricted to existing player ja-to-ko and its exact rule")
    _require("positive_zh_ko" not in record, "Japanese and Chinese positive evidence cannot be mixed")
    _require("negative_closure" not in record, "positive generation cannot claim negative closure")
    positive = record.get("positive_generation")
    _require(isinstance(positive, dict) and set(positive) == {
        "version", "identity", "reading", "rules", "explanation", "conflict_queries", "unresolved_conflicts"
    } and positive["version"] == 1, "positive generation fields invalid")
    identity, reading = positive["identity"], positive["reading"]
    _require(isinstance(identity, dict) and set(identity) == {
        "owner", "original_name", "reading", "status", "method", "basis", "capture"
    } and identity["owner"] == record["owner"] and identity["original_name"] == record["original_name"]
             and identity["reading"] == record["reading"] and identity["status"] == "verified"
             and identity["method"] == "reviewed_owner_binding" and _text(identity["basis"]),
             "positive identity must bind the verified exact owner, original name and reading")
    _require(isinstance(reading, dict) and set(reading) == {"surname", "given", "capture"}
             and all(_text(reading[key]) and re.fullmatch(r"[\u3041-\u3096\u30a1-\u30faー]+", reading[key])
                     for key in ("surname", "given"))
             and record["reading"] == reading["surname"] + " " + reading["given"],
             "positive reading requires full kana with exact surname/given boundaries")
    rules, queries = positive["rules"], positive["conflict_queries"]
    _require(isinstance(rules, list) and len(rules) == 3
             and all(isinstance(item, dict) and set(item) == {"role", "capture"} for item in rules)
             and {item["role"] for item in rules} == set(_POSITIVE_RULE_PAGES), "positive generation needs three NIKL rule pages")
    _require(isinstance(queries, list) and len(queries) == 2
             and all(isinstance(item, dict) and set(item) == {
                 "role", "query", "capture", "relevant_results", "conclusion"
             } for item in queries)
             and {item["role"] for item in queries} == {"original_go", "candidate_go"},
             "positive generation needs two actual usable conflict queries")
    for capture in positive_ja_ko_captures(record):
        _validate_positive_capture(capture)
    for capture, url in ((identity["capture"], record["original_language_basis_url"]),
                         (reading["capture"], record["reading_basis_url"])):
        visible = _VisibleHTML()
        visible.feed(capture["body_excerpt"])
        text = re.sub(r"\s+", "", "".join(visible.parts))
        _require(capture["url"] == url and capture["observed_lang"] == "ja"
                 and capture["source_role"] in {
                     "official_person_page", "professional_go_rating_archive", "professional_go_history_compilation",
                     "biographical_dictionary", "professional_archive", "official_profile"
                 } and re.sub(r"\s+", "", record["original_name"]) in text
                 and reading["surname"] + reading["given"] in text,
                 "positive identity/reading must occur together in actual Japanese source")
    for item in rules:
        capture = item["capture"]
        parsed = urlparse(capture["url"])
        parameters = parse_qs(parsed.query)
        _require(parsed.hostname in {"www.korean.go.kr", "korean.go.kr"}
                 and parsed.path == "/front/page/pageView.do" and parameters == {
                     "mn_id": ["97"], "page_id": [_POSITIVE_RULE_PAGES[item["role"]]]
                 } and capture["observed_lang"] == "ko" and capture["source_role"] == "normative_rule",
                 "positive rules require the exact official NIKL pages")
    explanation = positive["explanation"]
    _require(isinstance(explanation, dict) and set(explanation) == {"surname", "given", "output", "rule_applications"}
             and all(_text(explanation[key]) for key in ("surname", "given", "output"))
             and explanation["output"] == record["candidate_name"] == explanation["surname"] + " " + explanation["given"]
             and re.fullmatch(r"[가-힣]+ [가-힣]+", explanation["output"]), "positive output must exactly match reviewed surname/given")
    applications = explanation["rule_applications"]
    _require(isinstance(applications, list) and bool(applications)
             and all(isinstance(item, dict) and set(item) == {"rule_role", "locator", "input", "output", "reason"}
                     and item["rule_role"] in _POSITIVE_RULE_PAGES
                     and all(_text(item[key]) for key in ("locator", "input", "output", "reason"))
                     and item["locator"] == next(rule["capture"]["locator"] for rule in rules
                                                if rule["role"] == item["rule_role"])
                     for item in applications)
             and {item["rule_role"] for item in applications} == set(_POSITIVE_RULE_PAGES),
             "positive generation needs complete per-name rule explanations")
    _require(positive["unresolved_conflicts"] == [], "positive generation has unresolved conflicts")
    for item in queries:
        query = item["query"]
        _require(_text(query) and "바둑" in query
                 and (record["original_name"] if item["role"] == "original_go" else record["candidate_name"]) in query
                 and item["capture"]["source_role"] == "search_results"
                 and item["conclusion"] == "no_unresolved_conflict", "positive query tokens or conclusion invalid")
        results = item["relevant_results"]
        _require(isinstance(results, list) and all(
            isinstance(result, dict) and set(result) == {"url", "text", "resolution"}
            and _https_url(result["url"]) and _text(result["text"]) and _text(result["resolution"])
            and result["text"] in item["capture"]["body_text"] for result in results),
            "positive queries require captured relevant results and resolved explanations")
    for check in record["source_checks"]:
        _require(check["status"] == "found" and check["candidate_name"] == record["original_name"],
                 "positive source checks support original Japanese identity, not published Korean usage")
    _require(any(check["url"] == identity["capture"]["url"]
                 and check["body_sha256"] == identity["capture"]["body_sha256"]
                 and check["body_excerpt"] in identity["capture"]["body_text"] for check in record["source_checks"]),
             "positive source check must bind actual identity capture")


def _validate_positive_zh_ko(record: dict) -> None:
    """Validate the first finite Mandarin profile without inferring pronunciation from Han."""
    from katrain.web.kifu.name_zh_ko import (
        RULE_BODY_SHA256, RULE_LOCATORS, RULE_URL, RULE_VERSION, SOURCE_BASIS, render_name, used_entries,
    )

    _require(record.get("source_basis") == SOURCE_BASIS
             and record.get("scope_status") == POSITIVE_SCOPE
             and record.get("generation_rule_version") == RULE_VERSION
             and record["owner"]["kind"] == "player" and set(record["owner"]) == {"kind", "id"}
             and record["lang"] == "ko" and record.get("original_language") in {"zh-Hans", "zh-Hant"},
             "Chinese positive generation requires existing player, Chinese original and exact rule")
    _require("positive_generation" not in record and "negative_closure" not in record,
             "Chinese positive evidence cannot mix Japanese or negative markers")
    positive = record.get("positive_zh_ko")
    _require(isinstance(positive, dict) and set(positive) == {
        "version", "scope", "identity", "reading", "rule", "contrary_checks", "unresolved_conflicts", "source_anchors"
    } and positive["version"] == 1, "Chinese positive evidence fields invalid")
    scope = positive["scope"]
    common_scope = {"ordinary_mandarin", "personal_name", "basis", "unresolved_reading_variants"}
    _require(isinstance(scope, dict) and (
        set(scope) == common_scope | {"modern_mainland"} and scope["modern_mainland"] is True
        or set(scope) == common_scope | {"modern_standard_mandarin"}
        and scope["modern_standard_mandarin"] is True)
             and scope["ordinary_mandarin"] is True and scope["personal_name"] is True
             and _text(scope["basis"]) and scope["unresolved_reading_variants"] == [],
             "Chinese scope must be reviewed modern ordinary Mandarin with no reading conflict")
    identity, reading = positive["identity"], positive["reading"]
    _require(isinstance(identity, dict) and set(identity) == {
        "owner", "original_name", "status", "method", "basis", "capture"
    } and identity["owner"] == record["owner"] and identity["original_name"] == record["original_name"]
             and identity["status"] == "verified" and identity["method"] == "reviewed_owner_binding"
             and _text(identity["basis"]), "Chinese identity must bind exact owner and original name")
    paired = isinstance(reading, dict) and "profile_pair" in reading
    _require(isinstance(reading, dict) and set(reading) == {
        "published", "system", "reading_words", "determination", "capture"
    } | ({"profile_pair"} if paired else set()) and reading["published"] == record["reading"]
             and reading["system"] == "pinyin-syllables-v1" and _text(reading["determination"]),
             "Chinese reading must be complete published Hanyu Pinyin")
    words = reading["reading_words"]
    try:
        entries = used_entries(words)
        output = render_name(words)
        published = reading["published"].split()
        _require(len(published) == 2 and all(
            _normalized_phonetic_reading(word, reading["system"]) == "".join(syllables)
            for word, syllables in zip(published, words)),
            "Chinese surname/given and syllable boundaries differ from published spelling")
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc
    for capture in (identity["capture"], reading["capture"]):
        _validate_positive_capture(capture)
    original_capture, reading_capture = identity["capture"], reading["capture"]
    _require(original_capture["url"] == record["original_language_basis_url"]
             and record["original_name"] in original_capture["body_excerpt"]
             and original_capture["observed_lang"] in {"zh", "zh-Hans", "zh-Hant"}
             and (scope.get("modern_standard_mandarin") is not True
                  or original_capture["observed_lang"] == record["original_language"])
             and reading_capture["url"] == record["reading_basis_url"]
             and (paired or record["original_name"] in reading_capture["body_excerpt"])
             and reading["published"] in reading_capture["body_excerpt"]
             and reading_capture["source_role"] in {"published_player_profile", "official_person_page"}
             and reading_capture["observed_lang"] in {"en", "zh", "zh-Hans", "zh-Hant"},
             "Chinese identity and published reading need exact same-person captured source rows")
    if paired:
        pair = reading["profile_pair"]
        _require(isinstance(pair, dict) and set(pair) == {
            "provider", "player_id", "original_url", "authority_url"
        } and pair["provider"] == "goratings" and type(pair["player_id"]) is int
                 and pair["player_id"] > 0 and _https_url(pair["authority_url"])
                 and urlparse(pair["authority_url"]).netloc not in {"goratings.org", "www.goratings.org"}
                 and pair["original_url"] == original_capture["url"]
                 and all(urlparse(url).scheme == "https"
                         and urlparse(url).netloc in {"goratings.org", "www.goratings.org"}
                         and not urlparse(url).params and not urlparse(url).query
                         and not urlparse(url).fragment
                         for url in (original_capture["url"], reading_capture["url"]))
                 and urlparse(original_capture["url"]).path == f"/zh/players/{pair['player_id']}.html"
                 and urlparse(reading_capture["url"]).path == f"/en/players/{pair['player_id']}.html"
                 and pair["authority_url"] in original_capture["body_text"]
                 and pair["authority_url"] in reading_capture["body_text"],
                 "Chinese paired profile requires two exact same-ID GoRatings captures and shared authority")
    rule = positive["rule"]
    _require(isinstance(rule, dict) and set(rule) == {"capture", "used_entries", "output", "format"}
             and rule["used_entries"] == entries and rule["output"] == output == record["candidate_name"]
             and rule["format"] == "joined_surname_given_project_format",
             "Chinese rule entries and full output must be exactly reproducible")
    rule_capture = rule["capture"]
    _require(isinstance(rule_capture, dict) and rule_capture == {
        "url": RULE_URL, "http_status": 200, "fetched_at": rule_capture.get("fetched_at"),
        "body_sha256": RULE_BODY_SHA256, "source_role": "normative_rule", "observed_lang": "ko",
        **RULE_LOCATORS,
    } and _aware_timestamp(rule_capture.get("fetched_at")),
             "Chinese rule requires the exact captured official body, URL and locators")
    _require(positive["unresolved_conflicts"] == [], "Chinese name has unresolved conflicts")
    checks = positive["contrary_checks"]
    _require(isinstance(checks, list) and bool(checks)
             and {item.get("role") for item in checks if isinstance(item, dict)}
                >= {"original_go", "candidate_go"},
             "Chinese generation needs finite original and candidate Go-context checks")
    for item in checks:
        _require(isinstance(item, dict) and set(item) == {
            "role", "query", "search_scope", "status", "capture", "relevant_matches", "resolution",
            "conventional_gate_qualified"
        } and item["role"] in {"original_go", "candidate_go"}
                 and item["status"] in {"found", "not_found", "unavailable"}
                 and _text(item["query"]) and _text(item["search_scope"]) and _text(item["resolution"])
                 and item["conventional_gate_qualified"] is False
                 and isinstance(item["relevant_matches"], list)
                 and all(_text(match) for match in item["relevant_matches"]),
                 "Chinese contrary check fields or result invalid")
        tokens = (record["original_name"], reading["published"]) if item["role"] == "original_go" else (output,)
        _require((any(token in item["query"] for token in tokens) if item["role"] == "original_go"
                  else output in item["query"])
                 and ("Go" in item["search_scope"] or "바둑" in item["search_scope"]),
                 "Chinese contrary query must use an exact name in documented Go corpus context")
        capture = item["capture"]
        _require(isinstance(capture, dict), "Chinese contrary capture must be an object")
        allowed_roles = ({"professional_go_search", "published_player_profile", "official_person_page",
                          "search_tool_response"} if item["role"] == "original_go" else
                         {"reference_go_roster", "professional_go_roster", "professional_go_profile",
                          "official_go_roster", "official_roster", "search_tool_response"})
        _require(capture.get("source_role") in allowed_roles,
                 "Chinese contrary capture role differs from documented Go corpus")
        if capture["source_role"] == "professional_go_search":
            _require(parse_qs(urlparse(capture.get("url", "")).query).get("q") == [item["query"]],
                     "Chinese professional Go search URL differs from the actual query")
        if item["status"] == "unavailable":
            _require(isinstance(capture, dict) and set(capture) == {
                "url", "queried_at", "response_status", "source_role", "locator", "reason"
            } and _https_url(capture["url"]) and _aware_timestamp(capture["queried_at"])
                     and capture["response_status"] == "unavailable"
                     and all(_text(capture[key]) for key in ("source_role", "locator", "reason"))
                     and item["relevant_matches"] == [],
                     "unavailable contrary response cannot claim absence")
        else:
            if capture.get("capture_kind") == "web_tool_response":
                _require(set(capture) == {"capture_kind", "queried_at", "response_status", "body_text",
                                          "body_sha256", "body_excerpt", "locator", "source_role", "observed_lang"}
                         and item["status"] == "found" and _aware_timestamp(capture["queried_at"])
                         and capture["response_status"] == "completed_with_results"
                         and capture["source_role"] == "search_tool_response"
                         and all(_text(capture[key]) for key in
                                 ("body_text", "body_excerpt", "locator", "observed_lang"))
                         and capture["body_sha256"] == hashlib.sha256(capture["body_text"].encode("utf-8")).hexdigest()
                         and capture["body_excerpt"] in capture["body_text"],
                         "Chinese search-tool transcript needs its actual response without HTTP claims")
            else:
                _validate_positive_capture(capture)
                reliable_ko_source = capture["source_role"] in {
                    "official_go_roster", "official_roster", "professional_go_roster", "professional_go_profile"
                }
                # A captured excerpt with both exact forms cannot be concealed
                # by splitting or omitting relevant_matches.
                same_person_ko_row = (record["original_name"] in capture["body_excerpt"]
                                      and output in capture["body_excerpt"])
                _require(not (item["role"] == "candidate_go" and item["status"] == "found"
                              and reliable_ko_source and same_person_ko_row),
                         "reliable published Korean player name needs conventional review")
            _require(all(match in capture["body_text"] for match in item["relevant_matches"])
                     and (item["status"] != "not_found" or item["relevant_matches"] == []
                          and not any(token in capture["body_text"] for token in tokens)),
                     "Chinese contrary matches must occur in captured response; captured name is not absent")
    anchors = positive["source_anchors"]
    _require(isinstance(anchors, list), "Chinese qualified source anchors must be a list")
    for anchor in anchors:
        content = validate_primary_orthographic_anchor(anchor)
        anchored_name = record["reading"] if content.get("reference_kind") == "verified_english_display" else record["original_name"]
        _require(content["owner"] == record["owner"] and content["original_name"] == anchored_name,
                 "Chinese qualified source anchor differs from owner or published name")
    _require(any(check["status"] == "found" and check["candidate_name"] == record["original_name"]
                 and check["url"] == original_capture["url"]
                 and check["body_sha256"] == original_capture["body_sha256"]
                 for check in record["source_checks"]),
             "Chinese original source check must bind the captured original row")


def validate_research_record(record: dict, registry: dict) -> dict:
    """Validate one candidate or negative search claim, always returning pending status."""
    _require(isinstance(record, dict), "research record must be an object")
    owner = record.get("owner")
    lang = record.get("lang")
    exact_owner_key = owner_key(owner, lang)
    target = product_language_tag(lang, registry)
    _require(record.get("registry_version") == registry["version"], "registry version mismatch")
    _require(record.get("registry_sha256") == registry_sha256(registry), "registry hash mismatch")
    _require(record.get("review_status") == "pending", "research records must remain pending")
    _require(not any(record.get(key) for key in ("reviewer_id", "reviewer_model", "reviewed_at")),
             "research record cannot contain a review signature")
    _require(_text(record.get("producer_id")) and _text(record.get("producer_model")),
             "actual producer identity/model required")
    scope_status = record.get("scope_status")
    from katrain.web.kifu.name_zh_ko import RULE_VERSION as ZH_RULE, SOURCE_BASIS as ZH_BASIS
    ja_positive = any((record.get("source_basis") == POSITIVE_SOURCE_BASIS,
                       record.get("generation_rule_version") == POSITIVE_RULE, "positive_generation" in record))
    zh_positive = any((record.get("source_basis") == ZH_BASIS,
                       record.get("generation_rule_version") == ZH_RULE, "positive_zh_ko" in record))
    _require(not (ja_positive and zh_positive), "Japanese and Chinese positive markers are mixed")
    _require(scope_status != POSITIVE_SCOPE or ja_positive or zh_positive,
             "positive scope requires one exact language profile")
    positive = ja_positive or zh_positive
    if ja_positive:
        try:
            _validate_positive_ja_ko(record)
        except (KeyError, TypeError, StopIteration) as exc:
            raise EvidenceError("positive generation has missing or malformed evidence fields") from exc
        target = "ja"
    elif zh_positive:
        try:
            _validate_positive_zh_ko(record)
        except (KeyError, TypeError, StopIteration) as exc:
            raise EvidenceError("Chinese positive generation has missing or malformed evidence fields") from exc
        target = record["original_language"]
    sgf_literal = record.get("source_basis") == SGF_LITERAL_BASIS
    _require(not sgf_literal or owner["kind"] == "raw_event" and scope_status == "translated_from_original",
             "SGF literal evidence requires a translated existing raw event")
    _require(scope_status in SCOPE_STATUSES or positive, "invalid scope status")
    _require("negative_closure" not in record or scope_status == "not_found_in_scope",
             "negative closure applies only to a negative scope")
    if scope_status != "incomplete":
        _require(_text(record.get("original_name")) and _text(record.get("original_language")),
                 "completed research needs original name and language")
        _require(sgf_literal or _https_url(record.get("original_language_basis_url")),
                 "completed research needs original-language source URL")
        if _text(record.get("reading")):
            _require(_https_url(record.get("reading_basis_url")), "reading needs source URL")
    if scope_status == "translated_from_original":
        _require(owner["kind"] in {"event", "raw_event"} and "id" in owner,
                 "title translation requires an existing event or raw event ID")
        if owner["kind"] == "raw_event":
            try:
                validate_raw_title_research(record)
            except ValueError as exc:
                raise EvidenceError(str(exc)) from exc
        _require(lang in {"cn", "tw", "jp", "ko", "en"}, "title translation supports the five primary languages")
        _require(record.get("translation_method") == "literal_event_title", "title translation method required")
        _require(_text(record.get("candidate_name")), "title translation needs a target candidate")
        target = record["original_language"]
        _require(target in registry["language_tags"].values(), "title translation needs a concrete original language")
    checks = record.get("source_checks")
    if sgf_literal:
        result = deepcopy(record)
        result["owner_key"] = exact_owner_key
        return result
    _require(isinstance(checks, list) and bool(checks), "source checks required")
    sources = {source["id"]: source for source in registry["sources"]}
    for check in checks:
        _validate_check(check, owner, target, sources, finite_negative="negative_closure" in record)
        if positive:
            _require(sources[check["source_id"]]["tier"] in {
                "official", "language_go", "encyclopedia", "wikipedia_article"
            }, "positive original identity requires a substantive source, not discovery labels")
        if scope_status == "translated_from_original":
            _require(check["status"] == "found" and check["candidate_name"] == record["original_name"]
                     and sources[check["source_id"]]["tier"] in {
                         "official", "language_go", "wikipedia_article", "encyclopedia"
                     }, "title translation needs positive identity evidence for the original name")
        if check["status"] == "found" and sources[check["source_id"]]["tier"] in {
            "wikipedia_article", "encyclopedia"
        }:
            _require(_text(record.get("original_name")), "article identity needs original name")
            _validate_article_evidence(check, sources, record["original_name"])
    if positive:
        pass
    elif scope_status == "translated_from_original":
        _require(any(check["url"] == record["original_language_basis_url"] for check in checks),
                 "title translation original-language source must be a captured identity source")
    elif scope_status == "found":
        candidate = record.get("candidate_name")
        _require(_text(candidate), "found record needs candidate name")
        _require(any(check["status"] == "found" and check["candidate_name"] == candidate for check in checks),
                 "candidate is not supported by a found source check")
    elif scope_status == "not_found_in_scope":
        _require(not _text(record.get("candidate_name")), "negative scope cannot claim a candidate")
        scope = registry["language_scopes"][lang]
        finite = "negative_closure" in record
        if finite:
            _validate_negative_closure(record, registry, checks)
        else:
            _require(scope["complete_for_negative_claims"], "source scope is incomplete for negative claims")
        if not finite or record["negative_closure"]["version"] == 1:
            for source_id in scope["required_source_ids"]:
                _require(any(check["source_id"] == source_id and check["status"] == "not_found" for check in checks),
                         f"source scope lacks completed negative search for {source_id}")
        _require(all(check["status"] == "not_found" for check in checks), "negative source scope has unresolved checks")
        for check in checks:
            _validate_negative_outcome(check, sources[check["source_id"]], record["producer_id"], finite=finite)
    else:
        _require(not _text(record.get("candidate_name")), "incomplete scope cannot claim a candidate")
    result = deepcopy(record)
    result["owner_key"] = exact_owner_key
    return result


class _VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.language = ""
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.language = dict(attrs).get("lang", "")
        if tag in {"script", "style"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())


def _excerpt(body_text: str, needle: str, limit: int = 500) -> str:
    at = body_text.find(needle) if needle else -1
    start = max(0, at - 120) if at >= 0 else 0
    return body_text[start:start + limit]


def capture_source_check(
    task: dict,
    registry: dict,
    *,
    open_url=urlopen,
    sleep=time.sleep,
    max_attempts: int = 3,
    timeout: float = 10.0,
    max_bytes: int = 2_000_000,
) -> dict:
    """Capture a page for one owner/language query; a page miss is never proof of absence.

    The caller supplies the intended candidate and identity basis. This routine only
    checks that the text appears on a same-language page and leaves review pending.
    """
    _require(isinstance(task, dict), "capture task must be an object")
    owner = task.get("owner")
    owner_key(owner, task.get("lang"))
    lang = task.get("lang")
    target = product_language_tag(lang, registry)
    source = next((item for item in registry["sources"] if item["id"] == task.get("source_id")), None)
    _require(source is not None, "capture task has unknown source")
    url = task.get("url")
    _require(_source_url_matches(url, source), "capture URL must be HTTPS on registered host")
    _require(_text(task.get("query")), "capture query required")
    _require(max_attempts >= 1 and max_bytes >= 1, "invalid capture limits")
    candidate = task.get("candidate_name", "")
    check = {
        "owner": deepcopy(owner),
        "source_id": source["id"],
        "query": task["query"],
        "status": "unavailable",
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "http_status": None,
        "body_sha256": "",
        "body_excerpt": "",
        "observed_lang": "",
        "language_basis": "",
        "candidate_name": "",
    }
    request = Request(url, headers={"User-Agent": "KifuNameResearch/1.0 (+evidence capture; no auto approval)"})
    for attempt in range(max_attempts):
        try:
            with open_url(request, timeout=timeout) as response:
                check["http_status"] = getattr(response, "status", 200)
                resolved_url = getattr(response, "url", url)
                _require(_source_url_matches(resolved_url, source), "redirect left registered source host")
                check["url"] = resolved_url
                raw = response.read(max_bytes + 1)
                if check["http_status"] != 200 or len(raw) > max_bytes or not raw.strip():
                    check["status"] = "incomplete"
                    return check
                charset = response.headers.get_content_charset() or "utf-8"
                try:
                    markup = raw.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    check["status"] = "incomplete"
                    return check
                parser = _VisibleHTML()
                parser.feed(markup)
                body_text = " ".join(parser.parts)
                observed = parser.language or response.headers.get("Content-Language", "")
                check.update({
                    "body_sha256": hashlib.sha256(raw).hexdigest(),
                    "body_excerpt": _excerpt(body_text, candidate),
                    "observed_lang": observed,
                    "language_basis": "html_lang" if parser.language else "http_header" if observed else "",
                })
                if not body_text or not _matches_target(observed, target):
                    check["status"] = "incomplete"
                    return check
                if not (_text(candidate) and candidate in body_text and _text(task.get("identity_basis"))):
                    check["status"] = "incomplete"
                    return check
                if source["tier"] == "discovery":
                    # An HTML page language says nothing about API label fallback.
                    check["status"] = "incomplete"
                    return check
                check["status"] = "found"
                check["candidate_name"] = candidate
                check["identity_basis"] = task["identity_basis"]
                return check
        except HTTPError as exc:
            check["http_status"] = exc.code
            if exc.code not in {429, 500, 502, 503, 504} or attempt == max_attempts - 1:
                return check
        except (URLError, OSError):
            if attempt == max_attempts - 1:
                return check
        sleep(min(2 ** attempt, 8))
    return check


def validate_primary_orthographic_anchor(record: dict) -> dict:
    """Validate a reviewed original or an exact existing qualified display source."""
    _require(
        isinstance(record, dict)
        and record.get("evidence_kind") == "primary_orthographic"
        and type(record.get("version")) is int
        and record["version"] == 1
        and set(record) == {"evidence_kind", "version", "content", "approval"},
        "primary orthographic evidence kind/version invalid",
    )
    content = validate_transliteration_review(record, "approved_orthographic_original")
    produced_at = datetime.fromisoformat(record["approval"]["produced_at"].replace("Z", "+00:00"))
    reviewed_at = datetime.fromisoformat(record["approval"]["reviewed_at"].replace("Z", "+00:00"))
    _require(reviewed_at > produced_at, "orthographic original independent review must follow production")
    owner = content.get("owner")
    owner_key(owner, "tw")
    _require(owner["kind"] in {"player", "raw_player"}, "orthographic names only permit players")
    retained = content.get("reference_kind") == "official_hanja_preserved"
    verified_sources = {
        "verified_chinese_display": ("cn", "zh-Hans", "Hans"),
        "verified_japanese_display": ("jp", "ja", "Kanji"),
        "verified_english_display": ("en", "en", "Latin"),
    }
    verified_display = content.get("reference_kind") in verified_sources
    original = content.get("original_name")
    _require(content.get("reference_kind") in {None, "official_hanja_preserved", *verified_sources},
             "unknown primary orthographic reference kind")
    if verified_display:
        source_language, source_lang, source_script = verified_sources[content["reference_kind"]]
        _require(owner["kind"] == "player" and set(content) == {
            "reference_kind", "owner", "original_name", "source_lang", "source_script", "binding"
        } and content.get("source_lang") == source_lang and content.get("source_script") == source_script
        and isinstance(original, str) and 2 <= len(original) <= 16
        and (bool(re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", original)) if source_language == "en"
             else all(unicodedata.name(char, "").startswith("CJK UNIFIED IDEOGRAPH") for char in original)),
                 "verified display requires same-player source name")
        binding = content.get("binding")
        _require(isinstance(binding, dict) and set(binding) == {
            "kind", "owner", "source_name", "source_evidence", "source_batch"
        } and binding.get("kind") == content["reference_kind"] and binding.get("owner") == owner,
                 "verified display binding invalid")
        name, evidence, batch = (binding.get(key) for key in ("source_name", "source_evidence", "source_batch"))
        _require(isinstance(name, dict) and isinstance(evidence, dict) and isinstance(batch, dict)
                 and set(batch) == {"id", "bundle_sha256", "evidence_creation_sha256"}
                 and type(batch.get("id")) is int and batch["id"] > 0
                 and bool(_HEX_SHA256.fullmatch(str(batch.get("bundle_sha256"))))
                 and batch.get("evidence_creation_sha256") == registry_sha256(evidence),
                 "verified display source batch proof invalid")
        payload = evidence.get("research_payload")
        candidate = payload.get("candidate") if isinstance(payload, dict) else None
        research = payload.get("research") if isinstance(payload, dict) else None
        source_reviewed = evidence.get("reviewed_at")
        try:
            source_reviewed = datetime.fromisoformat(source_reviewed.replace("Z", "+00:00"))
            if source_reviewed.tzinfo is None:
                source_reviewed = source_reviewed.replace(tzinfo=timezone.utc)
        except (AttributeError, ValueError):
            source_reviewed = None
        _require(
            name.get("player_id") == owner.get("id")
            and name.get("lang") == evidence.get("lang") == source_language
            and name.get("display_name") == evidence.get("candidate_name") == original
            and name.get("status") == "verified"
            and name.get("decision_kind") == evidence.get("decision_kind") == "conventional"
            and name.get("evidence_id") == evidence.get("id")
            and name.get("revision") == evidence.get("revision")
            and name.get("generation_rule_version") == evidence.get("generation_rule_version")
            and evidence.get("player_id") == owner.get("id")
            and evidence.get("review_status") == "approved"
            and source_reviewed is not None
            and source_reviewed <= produced_at
            and isinstance(candidate, dict)
            and candidate.get("owner") == owner
            and candidate.get("lang") == source_language
            and candidate.get("display_name") == original
            and candidate.get("decision_kind") == "conventional"
            and candidate.get("review_status") == "approved"
            and isinstance(research, dict)
            and research.get("scope_status") == "found"
            and research.get("candidate_name") == original
            and candidate.get("research_sha256") == registry_sha256(research)
            and payload.get("primary_orthographic") is None
            and payload.get("transliteration") is None,
            "verified display requires complete qualified conventional source name and evidence",
        )
        return content
    required = {"owner", "original_name", "source_lang", "source_script", "binding", "sources"}
    required |= {"reference_kind", "korean_name"} if retained else {"chinese_origin"}
    if owner["kind"] == "raw_player":
        required |= {"raw_value", "raw_display_scope_sha256"}
    _require(set(content) == required, "orthographic original fields invalid; no reading or absence claims")
    _require(
        isinstance(original, str)
        and 2 <= len(original) <= 16
        and all(
            unicodedata.name(char, "").startswith("CJK UNIFIED IDEOGRAPH")
            or retained
            and unicodedata.name(char, "").startswith("CJK COMPATIBILITY IDEOGRAPH")
            for char in original
        ),
        "orthographic original must be a complete Han person name",
    )
    if retained:
        _require(
            owner["kind"] == "player"
            and content.get("source_lang") == "ko"
            and content.get("source_script") == "Hanja"
            and isinstance(content.get("korean_name"), str)
            and bool(re.fullmatch(r"[가-힣]{2,16}", content["korean_name"])),
            "official Hanja preservation requires Korean player original",
        )
    else:
        _require(
            content.get("chinese_origin") is True
            and content.get("source_lang") in {"zh-Hans", "zh-Hant"}
            and content.get("source_script") == {"zh-Hans": "Hans", "zh-Hant": "Hant"}[content["source_lang"]],
            "orthographic original requires reviewed Chinese origin/script",
        )
    binding = content.get("binding")
    _require(
        isinstance(binding, dict)
        and binding.get("owner") == owner
        and _text(binding.get("identity_basis"))
        and _text(binding.get("person_id_namespace"))
        and _text(binding.get("person_id")),
        "orthographic original owner binding missing",
    )
    if owner["kind"] == "player":
        _require(
            set(binding) == {"kind", "person_id_namespace", "person_id", "owner", "identity_basis"}
            and binding.get("kind") == "official_person"
            and _text(binding.get("person_id_namespace"))
            and _text(binding.get("person_id")),
            "orthographic original requires official person binding",
        )
    else:
        _require(
            set(binding) == {"kind", "owner", "identity_basis", "mapping", "person_id_namespace", "person_id"}
            and binding.get("kind") == "finite_raw_scope"
            and content.get("raw_value") == original
            and bool(_HEX_SHA256.fullmatch(str(content.get("raw_display_scope_sha256", "")))),
            "orthographic raw name requires exact finite approved scope",
        )
        mapping = validate_transliteration_review(binding.get("mapping"), "approved_exact_raw_original_mapping")
        _require(
            mapping.get("owner") == owner
            and mapping.get("raw_value") == original
            and mapping.get("original_name") == original
            and mapping.get("raw_display_scope_sha256") == content["raw_display_scope_sha256"],
            "orthographic raw mapping differs from original/scope",
        )
        _require(
            produced_at >= datetime.fromisoformat(binding["mapping"]["approval"]["reviewed_at"].replace("Z", "+00:00")),
            "orthographic original production predates raw mapping approval",
        )
    sources = content.get("sources")
    validate_transliteration_sources(sources, content["source_lang"], record["approval"]["reviewed_at"])
    for source in sources:
        _require(
            produced_at >= datetime.fromisoformat(source["fetched_at"].replace("Z", "+00:00")),
            "orthographic original production predates source capture",
        )
        body = source.get("body_text")
        _require(
            isinstance(body, str)
            and hashlib.sha256(body.encode("utf-8")).hexdigest() == source["body_sha256"]
            and source["body_excerpt"] in body
            and original in source["body_excerpt"]
            and _text(source.get("record_locator")),
            "orthographic captured body/name/locator mismatch",
        )
    if retained:
        _require(
            binding["person_id_namespace"] == "kba_pkey" and bool(re.fullmatch(r"[0-9]+", binding["person_id"])),
            "official Hanja preservation requires stable KBA person ID",
        )
        for source in sources:
            parsed = urlparse(source["url"])
            _require(
                source.get("tier") == "official"
                and source.get("source_role") == "official_person_page"
                and parsed.hostname in {"baduk.or.kr", "www.baduk.or.kr"}
                and parsed.path == "/record/player_view.asp"
                and parse_qs(parsed.query) == {"pkey": [binding["person_id"]]}
                and source["record_locator"] == "pkey=" + binding["person_id"],
                "official Hanja person page/ID/role mismatch",
            )
            parser = _VisibleHTML()
            parser.feed(source["body_text"])
            _require(parser.language == "ko", "official Hanja body must declare actual Korean language")
            pair = r"(?<![가-힣])" + re.escape(content["korean_name"]) + r"\s*\(\s*" + re.escape(original) + r"\s*\)"
            excerpt = _VisibleHTML()
            excerpt.feed(source["body_excerpt"])
            _require(
                re.search(pair, " ".join(excerpt.parts)) is not None,
                "official Hanja excerpt must contain the complete Korean/Hanja name pair",
            )
            rows = re.findall(r"<p\b[^>]*>.*?</p\s*>", source["body_text"], flags=re.I | re.S)
            same_row = False
            for markup in rows:
                visible = _VisibleHTML()
                visible.feed(markup)
                if re.search(pair, " ".join(visible.parts)):
                    same_row = True
                    break
            links = re.findall(r'<a\b[^>]*\bhref=[\'"]([^\'"]+)', source["body_text"], flags=re.I)
            stable_id = any(
                urlparse(urljoin(source["url"], link)).hostname in {"baduk.or.kr", "www.baduk.or.kr"}
                and urlparse(link).path == "/record/diary.asp"
                and parse_qs(urlparse(link).query) == {"foreignKey": [binding["person_id"]]}
                for link in links
            )
            _require(same_row and stable_id, "official Hanja name row or captured stable person ID missing")
    else:
        _require(
            any(
                source.get("tier") == "official" and binding["person_id"] in source["body_excerpt"]
                for source in sources
            ),
            "orthographic original needs official name and person-ID body",
        )
    return content


def is_positive_ja_ko(candidate: dict | None = None, payload: dict | None = None, rule: str | None = None) -> bool:
    """Recognize every retained discriminator so partial proof tampering cannot bypass the gate."""
    candidate = candidate if isinstance(candidate, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    research = payload.get("research")
    from katrain.web.kifu.name_zh_ko import RULE_VERSION as ZH_RULE, SOURCE_BASIS as ZH_BASIS
    if (rule == ZH_RULE or candidate.get("generation_rule_version") == ZH_RULE
            or "normative_zh_ko" in payload
            or isinstance(research, dict) and (research.get("source_basis") == ZH_BASIS
                or "positive_zh_ko" in research)):
        return False
    return (rule == POSITIVE_RULE or candidate.get("generation_rule_version") == POSITIVE_RULE
            or "normative_ja_ko" in payload
            or isinstance(research, dict) and (research.get("source_basis") == POSITIVE_SOURCE_BASIS
                or research.get("scope_status") == POSITIVE_SCOPE or "positive_generation" in research))


def is_positive_zh_ko(candidate: dict | None = None, payload: dict | None = None, rule: str | None = None) -> bool:
    """Recognize retained Chinese markers, including partial mutable proof damage."""
    from katrain.web.kifu.name_zh_ko import RULE_VERSION, SOURCE_BASIS

    candidate = candidate if isinstance(candidate, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    research = payload.get("research")
    return (rule == RULE_VERSION or candidate.get("generation_rule_version") == RULE_VERSION
            or "normative_zh_ko" in payload
            or isinstance(research, dict) and (research.get("source_basis") == SOURCE_BASIS
                or "positive_zh_ko" in research))


def _positive_content_sha256(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def persisted_legacy_zh_negative_eligible(name: dict, evidence: dict, batch: dict, registry: dict,
                                          creation_changes: list[dict]) -> bool:
    """Read only the exact, applied negative profile created under the older Chinese rule."""
    from katrain.web.kifu.name_zh_ko import RULE_VERSION as ZH_RULE

    try:
        if (type(batch["id"]) is not int or batch["status"] != "applied"
                or evidence["source_registry_id"] != batch["source_registry_id"]
                or len(creation_changes) != 1):
            return False
        creation = creation_changes[0]
        if (creation["target_table"] != "kifu_name_research_evidence"
                or type(creation["target_row_id"]) is not int or creation["target_row_id"] != evidence["id"]
                or type(creation["batch_id"]) is not int or creation["batch_id"] != batch["id"]
                or creation["before_image"] is not None
                or _positive_content_sha256(creation["after_image"]) != _positive_content_sha256(evidence)):
            return False
        created = creation["after_image"]
        payload = created["research_payload"]
        if not isinstance(payload, dict) or set(payload) != {"candidate", "research"}:
            return False
        row, research = payload["candidate"], payload["research"]
        if (not isinstance(row, dict) or not isinstance(research, dict)
                or research.get("scope_status") != "not_found_in_scope"
                or research.get("candidate_name") != ""
                or any(key in research for key in ("source_basis", "positive_zh_ko", "positive_generation"))
                or research["negative_closure"]["version"] != 1):
            return False
        checked = validate_research_record(research, registry)
        owner = {"kind": "player", "id": name["player_id"]}
        if (name["lang"] != "ko" or name["status"] != "verified"
                or name["decision_kind"] != "generated" or name["generation_rule_version"] != ZH_RULE
                or evidence["player_id"] != name["player_id"] or evidence["lang"] != "ko"
                or evidence["review_status"] != "approved" or evidence["decision_kind"] != "generated"
                or evidence["generation_rule_version"] != ZH_RULE
                or name["evidence_id"] != evidence["id"] or name["revision"] != evidence["revision"]
                or evidence["candidate_name"] != name["display_name"]
                or row["owner"] != owner or checked["owner"] != owner
                or row["lang"] != "ko" or checked["lang"] != "ko"
                or row["display_name"] != name["display_name"]
                or row["decision_kind"] != "generated" or row["generation_rule_version"] != ZH_RULE
                or row["research_sha256"] != _positive_content_sha256(research)
                or row["review_status"] != "approved"
                or row["review_conclusion"] != "approved_generated_display_and_rule"
                or row["producer_id"] != evidence["producer_id"]
                or row["producer_model"] != evidence["producer_model"]
                or row["reviewer_id"] != evidence["reviewer_id"]
                or row["reviewer_model"] != evidence["reviewer_model"]
                or row["producer_id"] == row["reviewer_id"]):
            return False
        def parsed(value):
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
        if (not all(_aware_timestamp(row[key]) for key in ("produced_at", "reviewed_at"))
                or not _aware_timestamp(research["produced_at"])
                or parsed(row["produced_at"]) != parsed(evidence["produced_at"])
                or parsed(row["reviewed_at"]) != parsed(evidence["reviewed_at"])
                or parsed(row["produced_at"]) <= parsed(research["negative_closure"]["reviewed_at"])
                or parsed(row["produced_at"]) < parsed(research["produced_at"])
                or parsed(row["reviewed_at"]) < parsed(row["produced_at"])
                or parsed(row["reviewed_at"]) <= parsed(research["negative_closure"]["reviewed_at"])):
            return False
        review = row["generated_review"]
        expected = {
            "decision": "approve_generated", "owner": owner, "lang": "ko",
            "display_name": row["display_name"], "generation_rule_version": ZH_RULE,
            "original_name": research["original_name"], "reading": research["reading"],
            "reading_basis_url": research["reading_basis_url"],
            "research_sha256": row["research_sha256"], "reviewer_id": row["reviewer_id"],
            "reviewer_model": row["reviewer_model"], "reviewed_at": row["reviewed_at"],
        }
        return (isinstance(review, dict) and set(review) == set(expected) | {"reason"}
                and all(review[key] == value for key, value in expected.items())
                and _text(review["reason"]))
    except (EvidenceError, KeyError, TypeError, ValueError, AttributeError):
        return False


def persisted_positive_ja_ko_eligible(name: dict, evidence: dict, batch: dict, registry: dict,
                                     changes: list[dict]) -> bool:
    """Pure applied-proof gate shared by ORM and bounded SQL readers; never trusts status alone."""
    canonical_sha256 = _positive_content_sha256

    try:
        artifact = batch["reviewed_artifact"]
        bundle = artifact["bundle"]
        payload = evidence["research_payload"]
        row, research, proof = payload["candidate"], payload["research"], payload["normative_ja_ko"]
        if (batch["status"] != "applied" or canonical_sha256(bundle) != batch["bundle_sha256"]
                or bundle["registry_sha256"] != registry_sha256(registry)
                or bundle["registry_version"] != registry["version"]
                or evidence["source_registry_id"] != batch["source_registry_id"]
                or not isinstance(proof, dict) or set(proof) != {"batch_id", "research_sha256", "candidate_sha256"}
                or proof != {"batch_id": batch["id"], "research_sha256": canonical_sha256(research),
                            "candidate_sha256": canonical_sha256(row)}
                or row["research_sha256"] != proof["research_sha256"]
                or proof["research_sha256"] not in artifact["research_hashes"]
                or [item for item in artifact["normative_research"]
                    if canonical_sha256(item) == proof["research_sha256"]] != [research]
                or [item for item in bundle["candidates"] if item["owner"] == row["owner"]
                    and item["lang"] == row["lang"]] != [row]
                or [item for item in bundle["members"] if item["owner"] == row["owner"]
                    and item["lang"] == row["lang"]] != [{"owner": row["owner"], "lang": row["lang"]}]
                or canonical_sha256(bundle["members"]) != bundle["member_set_sha256"]
                or row["review_status"] != "approved" or row["decision_kind"] != "generated"
                or row["generation_rule_version"] != POSITIVE_RULE
                or research["source_basis"] != POSITIVE_SOURCE_BASIS
                or row["owner"] != {"kind": "player", "id": name["player_id"]}
                or name["player_id"] != evidence["player_id"] or name["lang"] != evidence["lang"]
                or name["lang"] != "ko" or row["lang"] != "ko"
                or name["status"] != "verified" or evidence["review_status"] != "approved"
                or name["evidence_id"] != evidence["id"] or name["revision"] != evidence["revision"]
                or name["display_name"] != row["display_name"] or evidence["candidate_name"] != row["display_name"]
                or name["decision_kind"] != row["decision_kind"] or evidence["decision_kind"] != row["decision_kind"]
                or name["generation_rule_version"] != POSITIVE_RULE or evidence["generation_rule_version"] != POSITIVE_RULE):
            return False
        name_changes = [change for change in changes if change["target_table"] == "kifu_player_names"
                        and change["target_row_id"] == name["id"]]
        evidence_changes = [change for change in changes if change["target_table"] == "kifu_name_research_evidence"
                            and change["target_row_id"] == evidence["id"]]
        if (len(name_changes) != 1 or len(evidence_changes) != 1
                or name_changes[0]["batch_id"] != batch["id"] or evidence_changes[0]["batch_id"] != batch["id"]
                or name_changes[0]["after_image"] != name or evidence_changes[0]["after_image"] != evidence
                or evidence_changes[0]["before_image"] is not None
                or row["name_preimage_sha256"] != (canonical_sha256(name_changes[0]["before_image"])
                    if name_changes[0]["before_image"] is not None else None)):
            return False
        validate_positive_ja_ko_candidate(row, research, registry)
        return True
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration):
        return False


def persisted_positive_zh_ko_eligible(name: dict, evidence: dict, batch: dict, registry: dict,
                                      changes: list[dict], *, source_live=None) -> bool:
    """Pure applied-proof gate shared by ORM and bounded SQL readers; never trusts status alone."""
    from katrain.web.kifu.name_zh_ko import RULE_VERSION as ZH_RULE, SOURCE_BASIS as ZH_BASIS

    canonical_sha256 = _positive_content_sha256

    try:
        artifact = batch["reviewed_artifact"]
        bundle = artifact["bundle"]
        payload = evidence["research_payload"]
        row, research, proof = payload["candidate"], payload["research"], payload["normative_zh_ko"]
        if (batch["status"] != "applied" or canonical_sha256(bundle) != batch["bundle_sha256"]
                or bundle["registry_sha256"] != registry_sha256(registry)
                or bundle["registry_version"] != registry["version"]
                or evidence["source_registry_id"] != batch["source_registry_id"]
                or not isinstance(proof, dict) or set(proof) != {"batch_id", "research_sha256", "candidate_sha256"}
                or type(proof["batch_id"]) is not int or type(batch["id"]) is not int
                or proof != {"batch_id": batch["id"], "research_sha256": canonical_sha256(research),
                            "candidate_sha256": canonical_sha256(row)}
                or row["research_sha256"] != proof["research_sha256"]
                or proof["research_sha256"] not in artifact["research_hashes"]
                or [item for item in artifact["normative_research"]
                    if canonical_sha256(item) == proof["research_sha256"]] != [research]
                or [item for item in bundle["candidates"] if item["owner"] == row["owner"]
                    and item["lang"] == row["lang"]] != [row]
                or [item for item in bundle["members"] if item["owner"] == row["owner"]
                    and item["lang"] == row["lang"]] != [{"owner": row["owner"], "lang": row["lang"]}]
                or canonical_sha256(bundle["members"]) != bundle["member_set_sha256"]
                or row["review_status"] != "approved" or row["decision_kind"] != "generated"
                or row["generation_rule_version"] != ZH_RULE
                or research["source_basis"] != ZH_BASIS
                or row["owner"] != {"kind": "player", "id": name["player_id"]}
                or name["player_id"] != evidence["player_id"] or name["lang"] != evidence["lang"]
                or name["lang"] != "ko" or row["lang"] != "ko"
                or name["status"] != "verified" or evidence["review_status"] != "approved"
                or name["evidence_id"] != evidence["id"] or name["revision"] != evidence["revision"]
                or name["display_name"] != row["display_name"] or evidence["candidate_name"] != row["display_name"]
                or name["decision_kind"] != row["decision_kind"] or evidence["decision_kind"] != row["decision_kind"]
                or name["generation_rule_version"] != ZH_RULE or evidence["generation_rule_version"] != ZH_RULE):
            return False
        name_changes = [change for change in changes if change["target_table"] == "kifu_player_names"
                        and change["target_row_id"] == name["id"]]
        evidence_changes = [change for change in changes if change["target_table"] == "kifu_name_research_evidence"
                            and change["target_row_id"] == evidence["id"]]
        if (len(name_changes) != 1 or len(evidence_changes) != 1
                or name_changes[0]["batch_id"] != batch["id"] or evidence_changes[0]["batch_id"] != batch["id"]
                or name_changes[0]["after_image"] != name or evidence_changes[0]["after_image"] != evidence
                or evidence_changes[0]["before_image"] is not None
                or row["name_preimage_sha256"] != (canonical_sha256(name_changes[0]["before_image"])
                    if name_changes[0]["before_image"] is not None else None)):
            return False
        validate_positive_zh_ko_candidate(row, research, registry)
        # Keep SQL access outside this pure helper, but require a fresh check
        # of every bound source when the research references live DB names.
        anchors = research["positive_zh_ko"]["source_anchors"]
        return not anchors or callable(source_live) and all(
            anchor["content"]["reference_kind"] in {"verified_chinese_display", "verified_english_display"}
            and source_live(anchor) for anchor in anchors)
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration):
        return False


def validate_positive_ja_ko_candidate(row, research, registry):
    """Same finite positive input and exact review contract, without importer/ORM imports."""
    checked = validate_research_record(research, registry)
    _require(row['research_sha256'] == _positive_content_sha256(research)
             and row['owner'] == checked['owner'] and row['lang'] == checked['lang']
             and row['display_name'] == checked['candidate_name']
             and row['generation_rule_version'] == POSITIVE_RULE
             and row['review_status'] == 'approved' and row['decision_kind'] == 'generated',
             'positive candidate differs from exact research')
    for key in ('producer_id', 'producer_model'):
        _require(row[key] == checked[key], 'positive producer differs from research')
    for key in ('producer_id', 'producer_model', 'reviewer_id', 'reviewer_model', 'review_conclusion'):
        _require(_text(row[key]), 'positive review metadata missing')
    _require(row['producer_id'] != row['reviewer_id'], 'positive review must be independent')
    for key in ('produced_at', 'reviewed_at'):
        _require(_aware_timestamp(row[key]), 'positive review timestamp invalid')
    reviewed = datetime.fromisoformat(row['reviewed_at'].replace('Z', '+00:00'))
    _require(reviewed >= datetime.fromisoformat(row['produced_at'].replace('Z', '+00:00')),
             'positive review predates production')
    captures = positive_ja_ko_captures(checked)
    captures += checked['source_checks']
    for check in checked['source_checks']:
        for key in ('identity_corroboration', 'label_evidence'):
            if isinstance(check.get(key), dict):
                captures.append(check[key])
    _require(all(reviewed >= datetime.fromisoformat(c['fetched_at'].replace('Z', '+00:00')) for c in captures),
             'positive review predates capture')
    review = row['generated_review']
    _require(row['review_conclusion'] == 'approved_generated_display_and_rule'
             and review['decision'] == 'approve_generated' and _text(review['reason'])
             and review['positive_generation_sha256'] == _positive_content_sha256(checked['positive_generation'])
             and all(review[key] == 'approved' for key in ('identity_input_review', 'rule_review', 'output_review')),
             'positive exact input/rule/output review missing')
    for key in ('display_name', 'owner', 'lang', 'generation_rule_version', 'research_sha256',
                'reviewer_id', 'reviewer_model', 'reviewed_at'):
        _require(review[key] == row[key], 'positive exact candidate review mismatch')
    for key in ('original_name', 'reading', 'reading_basis_url'):
        _require(review[key] == checked[key], 'positive exact reading review mismatch')


def validate_positive_zh_ko_candidate(row: dict, research: dict, registry: dict) -> dict:
    """Require independent approval of exact Chinese inputs, six-entry rule and output."""
    from katrain.web.kifu.name_zh_ko import RULE_VERSION

    try:
        checked = validate_research_record(research, registry)
        _require(row["research_sha256"] == _positive_content_sha256(research)
                 and row["owner"] == checked["owner"] and row["lang"] == checked["lang"] == "ko"
                 and row["display_name"] == checked["candidate_name"]
                 and row["generation_rule_version"] == RULE_VERSION
                 and row["review_status"] == "approved" and row["decision_kind"] == "generated",
                 "Chinese candidate differs from exact pending research")
        for key in ("producer_id", "producer_model"):
            _require(row[key] == checked[key], "Chinese candidate producer differs from research")
        for key in ("producer_id", "producer_model", "reviewer_id", "reviewer_model", "review_conclusion"):
            _require(_text(row[key]), "Chinese candidate review metadata missing")
        _require(row["producer_id"] != row["reviewer_id"], "Chinese candidate review must be independent")
        for key in ("produced_at", "reviewed_at"):
            _require(_aware_timestamp(row[key]), "Chinese candidate review timestamp invalid")
        reviewed = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
        _require(reviewed >= datetime.fromisoformat(row["produced_at"].replace("Z", "+00:00")),
                 "Chinese candidate review predates production")
        positive = checked["positive_zh_ko"]
        captures = [positive["identity"]["capture"], positive["reading"]["capture"],
                    positive["rule"]["capture"], *[item["capture"] for item in positive["contrary_checks"]],
                    *checked["source_checks"]]
        _require(all(reviewed >= datetime.fromisoformat(c.get("fetched_at", c.get("queried_at")).replace("Z", "+00:00"))
                     for c in captures if "fetched_at" in c or "queried_at" in c),
                 "Chinese candidate review predates source or contrary capture")
        review = row["generated_review"]
        _require(isinstance(review, dict) and set(review) == {
            "decision", "display_name", "owner", "lang", "generation_rule_version", "research_sha256",
            "original_name", "reading", "reading_words", "reading_basis_url", "used_entries",
            "positive_zh_ko_sha256", "identity_input_review", "rule_review", "output_review",
            "reviewer_id", "reviewer_model", "reviewed_at", "reason"
        } and row["review_conclusion"] == "approved_generated_display_and_rule"
                 and review["decision"] == "approve_generated" and _text(review["reason"])
                 and review["positive_zh_ko_sha256"] == _positive_content_sha256(positive)
                 and all(review[key] == "approved" for key in
                         ("identity_input_review", "rule_review", "output_review")),
                 "Chinese exact input/rule/output review missing")
        for key in ("display_name", "owner", "lang", "generation_rule_version", "research_sha256",
                    "reviewer_id", "reviewer_model", "reviewed_at"):
            _require(review[key] == row[key], "Chinese candidate review differs from exact row")
        for key in ("original_name", "reading", "reading_basis_url"):
            _require(review[key] == checked[key], "Chinese candidate review differs from exact research")
        _require(review["reading_words"] == positive["reading"]["reading_words"]
                 and review["used_entries"] == positive["rule"]["used_entries"],
                 "Chinese candidate review differs from syllable boundaries or frozen entries")
        return row
    except (KeyError, TypeError, StopIteration) as exc:
        raise EvidenceError("Chinese candidate has missing or malformed review fields") from exc
