"""Finite, offline syllable transliteration from independently reviewed readings."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_evidence import (
    EvidenceError,
    SECONDARY_LANGUAGES,
    TRANSCRIPTION_SYSTEMS,
    owner_key,
    registry_sha256,
    validate_transliteration_review,
    validate_transliteration_sources,
)

VERSION = "secondary-transliteration-v1"
_CYRILLIC_ALPHABETS = {
    "ru": frozenset("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"),
    "ua": frozenset("абвгґдеєжзиіїйклмнопрстуфхцчшщьюяАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"),
}


def _require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _target_text(value, lang):
    if not isinstance(value, str) or not value or len(value) > 1024:
        return False
    letters = [char for char in value if char not in " -’'ʼ"]
    if lang in _CYRILLIC_ALPHABETS:
        return bool(letters) and all(char in _CYRILLIC_ALPHABETS[lang] for char in letters)
    if not letters or not all(unicodedata.name(char, "").startswith("LATIN") and char.isalpha() for char in letters):
        return False
    return True


def render_reading(rule, reading_words):
    """Two bounded data operations; unknown syllables have no fallback."""
    lang, operation = rule["lang"], rule["operation"]
    words = []
    for word in reading_words:
        if operation == "copy_roman_words_v1":
            output = "".join(word)
        else:
            _require(all(token in rule["token_map"] for token in word), "transliteration reading has unsupported token")
            output = "".join(rule["token_map"][token] for token in word)
        output = ("İ" if lang == "tr" and output[0] == "i" else output[0].upper()) + output[1:]
        words.append(output)
    result = " ".join(words)
    _require(_target_text(result, lang), "transliteration output has exceptional target spelling")
    return result


def validate_transliteration(section, candidates, anchors, snapshot):
    """Return bindings only after verifying the whole signed finite collection."""
    _require(
        isinstance(section, dict)
        and set(section) == {"version", "rules", "batches"}
        and section.get("version") == VERSION,
        "transliteration section/version invalid",
    )
    _require(isinstance(snapshot, list), "transliteration needs explicit approved name snapshot")
    snapshot_keys = set()
    for row in snapshot:
        _require(isinstance(row, dict), "approved name snapshot row required")
        key = owner_key(row.get("owner"), row.get("lang"))
        _require(
            row.get("lang") in {"en", "cn", "tw", "jp", "ko", *SECONDARY_LANGUAGES}
            and row.get("review_status") == "approved"
            and isinstance(row.get("display_name"), str)
            and isinstance(row.get("decision_kind"), str)
            and key not in snapshot_keys,
            "approved name snapshot row or uniqueness invalid",
        )
        snapshot_keys.add(key)
    rules, batches = section.get("rules"), section.get("batches")
    _require(
        isinstance(rules, list) and rules and isinstance(batches, list) and batches,
        "transliteration needs finite rules and batches",
    )
    rules_by_hash = {}
    rule_versions = set()
    for rule in rules:
        content = validate_transliteration_review(rule, "approved_transliteration_rule")
        _require(
            set(content)
            in (
                {
                    "version",
                    "lang",
                    "source_lang",
                    "reading_system",
                    "entity_kind",
                    "operation",
                    "token_map",
                    "sources",
                },
                {"version", "lang", "source_lang", "reading_system", "entity_kind", "operation", "sources"},
            ),
            "transliteration rule fields invalid",
        )
        lang = content.get("lang")
        _require(
            lang in SECONDARY_LANGUAGES
            and content.get("entity_kind") in {"player", "event"}
            and content.get("source_lang") in TRANSCRIPTION_SYSTEMS
            and content.get("reading_system") == TRANSCRIPTION_SYSTEMS[content["source_lang"]]
            and isinstance(content.get("version"), str)
            and content["version"] not in {"", "none"},
            "transliteration rule language, entity, reading system or version invalid",
        )
        version_key = tuple(
            content[field] for field in ("version", "lang", "source_lang", "reading_system", "entity_kind")
        )
        _require(version_key not in rule_versions, "duplicate transliteration rule version")
        rule_versions.add(version_key)
        operation = content.get("operation")
        mapping = content.get("token_map")
        _require(operation in {"syllable_map_v1", "copy_roman_words_v1"}, "transliteration operation invalid")
        if operation == "copy_roman_words_v1":
            _require(
                lang in {"de", "es", "fr", "tr"} and "token_map" not in content,
                "roman copy operation restricted to four Latin languages",
            )
        else:
            _require(
                isinstance(mapping, dict)
                and 0 < len(mapping) <= 4096
                and all(
                    isinstance(token, str)
                    and re.fullmatch(r"[a-zü]{1,16}", token)
                    and _target_text(output, lang)
                    and not any(char in output for char in " -’'ʼ")
                    for token, output in mapping.items()
                ),
                "transliteration token map invalid",
            )
        target = "uk" if lang == "ua" else lang
        validate_transliteration_sources(content.get("sources"), target, rule["approval"]["reviewed_at"])
        digest = registry_sha256(rule)
        _require(digest not in rules_by_hash, "duplicate transliteration rule")
        rules_by_hash[digest] = rule
    bindings = {}
    used_rules = set()
    used_anchors = set()
    outputs = {}
    for batch in batches:
        content = validate_transliteration_review(batch, "approved_transliteration_batch")
        _require(
            set(content)
            == {
                "version",
                "lang",
                "source_lang",
                "reading_system",
                "entity_kind",
                "rule_sha256",
                "approved_name_snapshot_sha256",
                "members",
            }
            and content.get("version") == VERSION,
            "transliteration batch fields/version invalid",
        )
        rule_hash = content.get("rule_sha256")
        _require(isinstance(rule_hash, str) and rule_hash in rules_by_hash, "transliteration batch rule missing")
        rule = rules_by_hash[rule_hash]
        _require(
            all(
                content.get(field) == rule["content"][field]
                for field in ("lang", "source_lang", "reading_system", "entity_kind")
            ),
            "transliteration batch differs from rule scope",
        )
        _require(
            content.get("approved_name_snapshot_sha256") == registry_sha256(snapshot),
            "transliteration approved name snapshot hash mismatch",
        )
        _require(
            _time(batch["approval"]["produced_at"]) >= _time(rule["approval"]["reviewed_at"]),
            "transliteration batch predates rule approval",
        )
        members = content.get("members")
        _require(isinstance(members, list) and members, "transliteration needs complete nonempty batch members")
        used_rules.add(rule_hash)
        for member in members:
            _require(isinstance(member, dict), "transliteration member required")
            key = owner_key(member.get("owner"), member.get("lang"))
            member_fields = {"owner", "lang", "display_name", "source_anchor_sha256", "rule_sha256"}
            is_raw = member["owner"]["kind"].startswith("raw_")
            _require(
                set(member) == member_fields | ({"raw_value"} if is_raw else set()),
                "transliteration member must sign exact raw spelling for raw owners",
            )
            _require(
                key not in bindings
                and member.get("lang") == content["lang"]
                and member.get("rule_sha256") == rule_hash,
                "transliteration member duplicate or outside batch scope",
            )
            anchor_hash = member.get("source_anchor_sha256")
            _require(isinstance(anchor_hash, str) and anchor_hash in anchors, "transliteration source anchor missing")
            anchor = anchors[anchor_hash]
            source = anchor["content"]
            if is_raw:
                _require(
                    member.get("raw_value") == source.get("raw_value"),
                    "transliteration signed raw spelling differs from source anchor",
                )
            _require(
                source["owner"] == member["owner"]
                and all(source[field] == content[field] for field in ("source_lang", "reading_system", "entity_kind")),
                "transliteration anchor differs from batch scope",
            )
            _require(
                _time(batch["approval"]["produced_at"]) >= _time(anchor["approval"]["reviewed_at"]),
                "transliteration batch predates original/reading approval",
            )
            output = render_reading(rule["content"], source["reading_words"])
            _require(
                member.get("display_name") == output,
                "transliteration stored output differs from mechanical recomputation",
            )
            name_key = (content["lang"], normalize_alias(output))
            _require(
                name_key not in outputs or outputs[name_key] == member["owner"],
                "transliteration same-language cross-batch collision",
            )
            outputs[name_key] = member["owner"]
            for existing in snapshot:
                _require(
                    not (
                        existing["owner"] == member["owner"]
                        and existing["lang"] == member["lang"]
                        and existing["decision_kind"] == "conventional"
                    ),
                    "transliteration cannot replace approved conventional name",
                )
                _require(
                    not (
                        existing["lang"] == member["lang"]
                        and existing["owner"] != member["owner"]
                        and normalize_alias(existing["display_name"]) == name_key[1]
                    ),
                    "transliteration collides with an approved name in another batch",
                )
            bindings[key] = (batch, member, rule)
            used_anchors.add(anchor_hash)
    actual = [
        owner_key(row.get("owner"), row.get("lang"))
        for row in candidates
        if isinstance(row, dict) and row.get("decision_kind") == "transliterated"
    ]
    _require(
        len(actual) == len(set(actual)) and set(actual) == set(bindings),
        "transliteration requires exact complete signed candidate set",
    )
    _require(
        used_rules == set(rules_by_hash) and used_anchors == set(anchors),
        "transliteration contains unused rule or source anchor",
    )
    return bindings


def validate_transliterated_candidate(row, bindings):
    """Bind one persisted candidate to its batch approval, without per-name review."""
    _require(
        row.get("lang") in SECONDARY_LANGUAGES and row.get("review_status") == "approved",
        "transliterated candidate restricted to six approved languages",
    )
    _require(isinstance(bindings, dict), "transliterated candidate needs complete batch context")
    key = owner_key(row.get("owner"), row.get("lang"))
    _require(key in bindings, "transliterated candidate lies outside signed batch")
    batch, member, rule = bindings[key]
    if row["owner"]["kind"].startswith("raw_"):
        _require(
            row.get("raw_value") == member["raw_value"],
            "transliterated candidate raw spelling differs from signed member",
        )
    _require(
        row.get("research_sha256") == ""
        and all(row.get(field) == member[field] for field in member)
        and row.get("transliteration_batch_sha256") == registry_sha256(batch)
        and row.get("generation_rule_version") == rule["content"]["version"],
        "transliterated candidate dependency or output binding mismatch",
    )
    _require(
        all(
            row.get(field) == batch["approval"][field]
            for field in (
                "producer_id",
                "producer_model",
                "produced_at",
                "reviewer_id",
                "reviewer_model",
                "reviewed_at",
            )
        )
        and row.get("review_conclusion") == "approved_transliteration_batch",
        "transliterated candidate must inherit exact independent batch signature",
    )
    _require(
        not any(field in row for field in ("scope_status", "negative_closure", "absence_claim", "generated_review")),
        "transliterated candidate must not claim absence of conventional names",
    )
