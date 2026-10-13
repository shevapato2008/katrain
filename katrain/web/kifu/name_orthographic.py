"""Frozen, independently approved Chinese orthography and official KBA Hanja retention."""

from datetime import datetime
import unicodedata

from sqlalchemy import select

from katrain.web.core.models_db import KifuPlayerName
from katrain.web.kifu.name_evidence import (
    EvidenceError,
    owner_key,
    registry_sha256,
    validate_transliteration_review,
    validate_primary_orthographic_anchor,
    _https_url,
    _HEX_SHA256,
    _aware_timestamp,
)

VERSION = "primary-orthographic-v1"
# These require individual actual-name evidence; a general table cannot settle them.
EXCLUDED_CHARACTERS = frozenset("于於钟鍾鐘岳嶽杰傑升昇")
EXCLUDED_NAMES = frozenset({"胡子扬", "胡子揚", "鬍子揚", "孔杰", "孔傑"})


def _require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_orthographic(row):
    return row.get("decision_kind") == "generated" and row.get("generation_rule_version") == VERSION


def _han(value):
    return (
        isinstance(value, str) and len(value) == 1 and unicodedata.name(value, "").startswith("CJK UNIFIED IDEOGRAPH")
    )


def _normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate_orthographic(section, candidates, anchors, snapshot, catalog_sha256):
    """Recheck the complete frozen sources, directional rules and full-name approvals."""
    _require(
        isinstance(section, dict)
        and set(section) == {"version", "rules", "batches"}
        and section.get("version") == VERSION,
        "orthographic section/version invalid",
    )
    _require(
        isinstance(snapshot, list) and bool(_HEX_SHA256.fullmatch(str(catalog_sha256))),
        "orthographic approved-name/catalog snapshots required",
    )
    snapshot_by_owner_lang, snapshot_by_normalized = {}, {}
    for row in snapshot:
        _require(
            isinstance(row, dict)
            and isinstance(row.get("display_name"), str)
            and row.get("review_status") == "approved",
            "orthographic approved-name snapshot invalid",
        )
        snapshot_key = owner_key(row.get("owner"), row["lang"])
        snapshot_by_owner_lang.setdefault(snapshot_key, []).append(row)
        if isinstance(row.get("lang"), str):
            normalized_key = (row["lang"], _normalize(row["display_name"]))
            snapshot_by_normalized.setdefault(normalized_key, set()).add(snapshot_key)
    _require(
        isinstance(section["rules"], list)
        and section["rules"]
        and isinstance(section["batches"], list)
        and section["batches"],
        "orthographic finite rules/batches required",
    )
    rules, maps = {}, {}
    for rule in section["rules"]:
        content = validate_transliteration_review(rule, "approved_orthographic_rule")
        retained = content.get("reference_kind") == "official_hanja_preserved"
        if retained:
            _require(
                content
                == {
                    "version": VERSION,
                    "reference_kind": "official_hanja_preserved",
                    "lang": "tw",
                    "source_lang": "ko",
                    "source_script": "Hanja",
                    "target_script": "Hanja",
                    "target_region": "TW",
                    "preservation": "exact_codepoints",
                },
                "official Hanja rule must preserve exact Korean Hanja for TW",
            )
            digest = registry_sha256(rule)
            _require(digest not in rules, "duplicate orthographic rule")
            rules[digest], maps[digest] = rule, None
            continue
        japanese_display = content.get("reference_kind") == "verified_japanese_display"
        catalog_default = content.get("reference_kind") == "catalog_chinese_default"
        if catalog_default and content.get("lang") == "cn":
            _require(content == {
                "version": VERSION,
                "reference_kind": "catalog_chinese_default",
                "lang": "cn",
                "source_lang": "zh",
                "source_script": "Han",
                "target_script": "Han",
                "target_region": "CN",
                "preservation": "exact_codepoints",
            }, "catalog Chinese CN rule must preserve exact codepoints")
            digest = registry_sha256(rule)
            _require(digest not in rules, "duplicate orthographic rule")
            rules[digest], maps[digest] = rule, None
            continue
        if japanese_display and content.get("lang") == "cn":
            _require(content == {
                "version": VERSION,
                "reference_kind": "verified_japanese_display",
                "lang": "cn",
                "source_lang": "ja",
                "source_script": "Kanji",
                "target_script": "Kanji",
                "target_region": "CN",
                "preservation": "exact_codepoints",
            }, "Japanese original CN display rule must preserve exact codepoints")
            digest = registry_sha256(rule)
            _require(digest not in rules, "duplicate orthographic rule")
            rules[digest], maps[digest] = rule, None
            continue
        _require(
            set(content)
            == {
                "version",
                "lang",
                "source_lang",
                "source_script",
                "target_script",
                "target_region",
                "mappings",
                "excluded_characters",
                "excluded_names",
                "exceptions_checked",
            }
            | ({"reference_kind"} if japanese_display or catalog_default else set()),
            "orthographic rule fields invalid",
        )
        expected = ({"tw": ("ja", "Kanji", "Hant", "TW")} if japanese_display else
                    {"tw": ("zh", "Han", "Hant", "TW")} if catalog_default else
                    {"tw": ("zh-Hans", "Hans", "Hant", "TW"), "cn": ("zh-Hant", "Hant", "Hans", "CN")})
        _require(
            content.get("version") == VERSION
            and (not japanese_display or content.get("reference_kind") == "verified_japanese_display")
            and (not catalog_default or content.get("reference_kind") == "catalog_chinese_default")
            and content.get("lang") in expected
            and tuple(content.get(k) for k in ("source_lang", "source_script", "target_script", "target_region"))
            == expected[content["lang"]],
            "orthographic directional Chinese rule scope invalid",
        )
        _require(
            content.get("exceptions_checked") is True
            and isinstance(content.get("excluded_characters"), list)
            and all(_han(char) for char in content["excluded_characters"])
            and isinstance(content.get("excluded_names"), list)
            and all(isinstance(name, str) and name for name in content["excluded_names"]),
            "orthographic explicit exclusions required",
        )
        mapping = {}
        _require(isinstance(content.get("mappings"), list) and content["mappings"], "orthographic mappings required")
        for entry in content["mappings"]:
            _require(
                isinstance(entry, dict)
                and set(entry)
                == {"input", "output", "normative_version", "normative_url", "location", "human_name_applicable"}
                and _han(entry.get("input"))
                and _han(entry.get("output"))
                and isinstance(entry.get("normative_version"), str)
                and entry["normative_version"]
                and _https_url(entry.get("normative_url"))
                and isinstance(entry.get("location"), str)
                and entry["location"]
                and entry.get("human_name_applicable") is True
                and entry["input"] not in mapping,
                "orthographic mapping must be single-valued and independently approved for human names",
            )
            mapping[entry["input"]] = entry["output"]
        digest = registry_sha256(rule)
        _require(digest not in rules, "duplicate orthographic rule")
        rules[digest], maps[digest] = rule, mapping
    bindings, used_anchors, used_rules, outputs = {}, set(), set(), {}
    for batch in section["batches"]:
        content = validate_transliteration_review(batch, "approved_orthographic_batch")
        _require(
            set(content)
            == {
                "version",
                "rule_sha256",
                "members",
                "members_sha256",
                "catalog_sha256",
                "approved_name_snapshot_sha256",
                "known_aliases",
                "unresolved_conflicts",
                "complete_name_review",
                "sampled_members",
                "frozen_at",
            }
            and content.get("version") == VERSION,
            "orthographic batch fields/version invalid",
        )
        rule_hash = content.get("rule_sha256")
        _require(rule_hash in rules, "orthographic batch rule missing")
        rule, mapping = rules[rule_hash], maps[rule_hash]
        r = rule["content"]
        retained = r.get("reference_kind") == "official_hanja_preserved"
        _require(
            content.get("catalog_sha256") == catalog_sha256
            and content.get("approved_name_snapshot_sha256") == registry_sha256(snapshot),
            "orthographic catalog/approved-name snapshot hash mismatch",
        )
        _require(
            content.get("unresolved_conflicts") == [] and isinstance(content.get("known_aliases"), list),
            "orthographic unresolved conventional-name/alias conflict",
        )
        _require(
            _aware_timestamp(content.get("frozen_at"))
            and _time(batch["approval"]["produced_at"])
            <= _time(content["frozen_at"])
            < _time(batch["approval"]["reviewed_at"]),
            "orthographic independent review must follow final freeze",
        )
        members = content.get("members")
        _require(
            isinstance(members, list)
            and members
            and content.get("members_sha256") == registry_sha256(members)
            and content.get("complete_name_review") == members,
            "orthographic complete frozen member review required",
        )
        samples = content.get("sampled_members")
        _require(
            isinstance(samples, list)
            and samples
            and len(samples) == len(set(samples))
            and set(samples) <= {registry_sha256(member) for member in members}
            and len(samples) >= min(20, len(members)),
            "orthographic actual sample set missing or outside members",
        )
        _require(
            _time(batch["approval"]["produced_at"]) >= _time(rule["approval"]["reviewed_at"]),
            "orthographic member freeze predates rule approval",
        )
        batch_digest = registry_sha256(batch)
        for member in members:
            _require(isinstance(member, dict), "orthographic member required")
            owner = member.get("owner")
            key = owner_key(owner, member.get("lang"))
            raw = owner["kind"] == "raw_player"
            reference_kind = member.get("reference_kind")
            verified_display = reference_kind in {"verified_chinese_display", "verified_japanese_display"}
            japanese_display = reference_kind == "verified_japanese_display"
            catalog_default = reference_kind == "catalog_chinese_default"
            _require(
                set(member)
                == {
                    "owner",
                    "original_name",
                    "lang",
                    "display_name",
                    "source_anchor_sha256",
                    "rule_sha256",
                    "codepoint_changes",
                    "name_preimage_sha256",
                    "preimage_binding_sha256",
                }
                | ({"raw_value", "raw_display_scope_sha256"} if raw else set())
                | ({"reference_kind"} if retained or verified_display or catalog_default else set())
                and owner["kind"] in (
                    {"player"} if retained or verified_display or catalog_default else {"player", "raw_player"}
                )
                and (not retained or member.get("reference_kind") == "official_hanja_preserved")
                and key not in bindings
                and member.get("lang") == r["lang"]
                and member.get("rule_sha256") == rule_hash,
                "orthographic member owner/language/rule scope invalid",
            )
            anchor_hash = member.get("source_anchor_sha256")
            _require(anchor_hash in anchors, "orthographic original anchor missing")
            anchor = anchors[anchor_hash]
            source = validate_primary_orthographic_anchor(anchor)
            original = source["original_name"]
            _require(
                source["owner"] == owner
                and member.get("original_name") == original
                and source["source_lang"] == r["source_lang"]
                and source["source_script"] == r["source_script"]
                and (source.get("reference_kind") == "catalog_chinese_default") == catalog_default
                and (not catalog_default or source.get("reference_kind") == "catalog_chinese_default"
                     and source["binding"]["catalog_sha256"] == catalog_sha256
                     and r.get("reference_kind") == "catalog_chinese_default")
                and (not retained or source.get("reference_kind") == "official_hanja_preserved"),
                "orthographic member source/owner scope mismatch",
            )
            _require(
                (verified_display and source.get("reference_kind") == reference_kind
                 and r.get("reference_kind") == (reference_kind if japanese_display else None)
                 and (japanese_display or r["lang"] == "tw"))
                or (not verified_display and source.get("reference_kind") not in
                    {"verified_chinese_display", "verified_japanese_display"}
                    and r.get("reference_kind") != "verified_japanese_display"),
                "orthographic verified display reference mismatch",
            )
            if verified_display:
                _require(not japanese_display or member.get("name_preimage_sha256") is None,
                         "verified display requires absent target name preimage")
                binding = source["binding"]
                source_name, source_evidence = binding["source_name"], binding["source_evidence"]
                source_lang = "jp" if japanese_display else "cn"
                source_rows = snapshot_by_owner_lang.get(owner_key(owner, source_lang), ())
                source_name_sha256 = registry_sha256(source_name)
                source_evidence_sha256 = registry_sha256(source_evidence)
                _require(
                    any(
                        existing.get("owner") == owner
                        and existing.get("lang") == source_lang
                        and existing.get("display_name") == original
                        and existing.get("decision_kind") == "conventional"
                        and existing.get("review_status") == "approved"
                        and existing.get("name_sha256") == source_name_sha256
                        and existing.get("evidence_sha256") == source_evidence_sha256
                        for existing in source_rows
                    ),
                    "orthographic verified source absent from qualified snapshot",
                )
            _require(
                _time(batch["approval"]["produced_at"]) >= _time(anchor["approval"]["reviewed_at"])
                and batch["approval"]["reviewer_id"] != anchor["approval"]["producer_id"],
                "orthographic full-name review predates anchor or shares its producer",
            )
            if raw:
                _require(
                    all(member.get(k) == source.get(k) for k in ("raw_value", "raw_display_scope_sha256")),
                    "orthographic raw scope mismatch",
                )
            if retained or (r["lang"] == "cn" and (japanese_display or catalog_default)):
                output = original
            else:
                exclusions = EXCLUDED_CHARACTERS | set(r["excluded_characters"])
                _require(
                    original not in EXCLUDED_NAMES | set(r["excluded_names"])
                    and not any(char in exclusions for char in original)
                    and all(char in mapping for char in original),
                    "orthographic name contains unknown or exceptional mapping",
                )
                output = "".join(mapping[char] for char in original)
                _require(
                    output not in EXCLUDED_NAMES and not any(char in EXCLUDED_CHARACTERS for char in output),
                    "orthographic output contains a known exception",
                )
            changes = [
                {"position": i, "input": f"U+{ord(a):04X}", "output": f"U+{ord(b):04X}"}
                for i, (a, b) in enumerate(zip(original, output))
            ]
            _require(
                member.get("display_name") == output and member.get("codepoint_changes") == changes,
                "orthographic complete output/codepoint mismatch",
            )
            normalized = (member["lang"], _normalize(output))
            _require(normalized not in outputs or outputs[normalized] == owner, "orthographic output collision")
            _require(
                not any(
                    retained or verified_display or catalog_default or existing.get("decision_kind") == "conventional"
                        for existing in snapshot_by_owner_lang.get(key, ())),
                "orthographic cannot replace known conventional name",
            )
            _require(
                all(existing_key == key for existing_key in snapshot_by_normalized.get(normalized, ())),
                "orthographic approved-name collision",
            )
            for alias in content["known_aliases"]:
                _require(
                    isinstance(alias, dict) and set(alias) == {"owner", "name"} and isinstance(alias.get("name"), str),
                    "orthographic alias snapshot invalid",
                )
                owner_key(alias.get("owner"), member["lang"])
                _require(
                    alias["owner"] == owner or _normalize(alias["name"]) != normalized[1],
                    "orthographic known alias collision",
                )
            bindings[key] = (batch, member, rule, batch_digest)
            outputs[normalized] = owner
            used_anchors.add(anchor_hash)
            used_rules.add(rule_hash)
    actual = [
        owner_key(row.get("owner"), row.get("lang"))
        for row in candidates
        if isinstance(row, dict) and is_orthographic(row)
    ]
    _require(
        len(actual) == len(set(actual))
        and set(actual) == set(bindings)
        and used_anchors == set(anchors)
        and used_rules == set(rules),
        "orthographic exact complete candidate/anchor/rule set required",
    )
    for row in candidates:
        if isinstance(row, dict) and is_orthographic(row):
            validate_orthographic_candidate(row, bindings)
    return bindings


def validate_orthographic_candidate(row, bindings):
    _require(
        is_orthographic(row) and row.get("review_status") == "approved" and isinstance(bindings, dict),
        "orthographic candidate requires approved finite context",
    )
    key = owner_key(row.get("owner"), row.get("lang"))
    _require(key in bindings, "orthographic candidate outside frozen scope")
    batch, member, _, batch_digest = bindings[key]
    _require(
        row.get("research_sha256") == ""
        and all(row.get(k) == v for k, v in member.items())
        and row.get("orthographic_batch_sha256") == batch_digest,
        "orthographic candidate signed dependency mismatch",
    )
    _require(
        all(
            row.get(k) == batch["approval"][k]
            for k in ("producer_id", "producer_model", "produced_at", "reviewer_id", "reviewer_model", "reviewed_at")
        )
        and row.get("review_conclusion") == "approved_orthographic_batch",
        "orthographic full-name independent review mismatch",
    )
    _require(
        not any(
            k in row
            for k in (
                "reading",
                "scope_status",
                "negative_closure",
                "absence_claim",
                "generated_review",
                "collision_decision",
                "collision_basis",
            )
        ),
        "orthographic candidate cannot claim reading, negative search or collision overrides",
    )
    binder = row.get("preimage_binding")
    _require(
        isinstance(binder, dict)
        and binder.get("actor_id") != row["reviewer_id"]
        and bool(_HEX_SHA256.fullmatch(str(binder.get("capture_sha256", ""))))
        and "name_preimage_sha256" in row
        and member.get("preimage_binding_sha256") == registry_sha256(binder)
        and member.get("name_preimage_sha256") == row["name_preimage_sha256"]
        and _aware_timestamp(binder.get("bound_at"))
        and _time(binder["bound_at"]) <= _time(batch["content"]["frozen_at"]),
        "orthographic final review must sign independently bound preimage before freeze",
    )
    if (member.get("reference_kind") in {"verified_chinese_display", "catalog_chinese_default"}
            and row["name_preimage_sha256"] is not None):
        target = binder.get("target_name_preimage")
        _require(
            row.get("lang") in ({"tw"} if member.get("reference_kind") == "verified_chinese_display" else {"cn", "tw"})
            and isinstance(target, dict)
            and set(target) == set(KifuPlayerName.__table__.columns.keys())
            and type(target.get("id")) is int and target["id"] > 0
            and type(target.get("player_id")) is int and target["player_id"] == row["owner"]["id"]
            and target.get("lang") == row["lang"]
            and target.get("status") == "review"
            and target.get("evidence_id") is None
            and registry_sha256(target) == row["name_preimage_sha256"],
            "catalog/verified Chinese display requires exact evidence-free review target preimage",
        )


def persisted_batch_bindings(batch):
    if batch.status != "applied" or not isinstance(batch.reviewed_artifact, dict):
        return None
    artifact = batch.reviewed_artifact
    bundle = artifact.get("bundle")
    if not isinstance(bundle, dict) or registry_sha256(bundle) != batch.bundle_sha256:
        return None
    try:
        anchors = artifact.get("orthographic_anchors")
        if not isinstance(anchors, list):
            return None
        anchors_by_hash = {registry_sha256(a): a for a in anchors}
        if len(anchors_by_hash) != len(anchors) or sorted(anchors_by_hash) != artifact.get(
            "orthographic_anchor_hashes"
        ):
            return None
        if not set(anchors_by_hash) <= set(artifact["research_hashes"]):
            return None
        bindings = validate_orthographic(
            bundle["primary_orthographic"],
            bundle["candidates"],
            anchors_by_hash,
            artifact["approved_name_snapshot"],
            bundle["catalog_sha256"],
        )
        candidates = {owner_key(row["owner"], row["lang"]): row for row in bundle["candidates"] if is_orthographic(row)}
        return bindings, candidates, anchors_by_hash, artifact
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def verified_source_live(conn, anchor, *, allow_authoritative_pages_drift=False):
    """Recheck the exact conventional source and its creation record."""
    from katrain.web.core.models_db import KifuNameBatch, KifuNameChange, KifuNameResearchEvidence, KifuPlayerName
    from katrain.web.kifu.name_batch import _image

    try:
        source = anchor["content"]
        if source.get("reference_kind") == "catalog_chinese_default":
            from katrain.web.core.models_db import KifuPlayer

            binding = source["binding"]
            current = _image(conn, KifuPlayer.__table__, source["owner"]["id"])
            if not allow_authoritative_pages_drift:
                return current == binding["owner_preimage"]
            return current is not None and all(
                current[field] == binding["owner_preimage"][field]
                for field in ("id", "canonical_name", "created_at")
            )
        if source.get("reference_kind") not in {
            "verified_chinese_display", "verified_japanese_display", "verified_english_display"
        }:
            return True
        binding = source["binding"]
        name, evidence, batch = (binding[key] for key in ("source_name", "source_evidence", "source_batch"))
        if _image(conn, KifuPlayerName.__table__, name["id"]) != name:
            return False
        if _image(conn, KifuNameResearchEvidence.__table__, evidence["id"]) != evidence:
            return False
        stored_batch = conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == batch["id"])).mappings().one_or_none()
        if stored_batch is None or stored_batch["status"] != "applied" or stored_batch["bundle_sha256"] != batch["bundle_sha256"]:
            return False
        artifact = stored_batch["reviewed_artifact"]
        payload = evidence["research_payload"]
        source_bundle = artifact.get("bundle") if isinstance(artifact, dict) else None
        if (not isinstance(source_bundle, dict)
            or registry_sha256(source_bundle) != stored_batch["bundle_sha256"]
            or payload.get("candidate") not in source_bundle.get("candidates", ())
            or payload["candidate"].get("research_sha256") != registry_sha256(payload["research"])
            or registry_sha256(payload["research"]) not in artifact.get("research_hashes", ())):
            return False
        for table, row in (("kifu_name_research_evidence", evidence), ("kifu_player_names", name)):
            changes = conn.execute(select(KifuNameChange.__table__).where(
                KifuNameChange.batch_id == batch["id"],
                KifuNameChange.target_table == table,
                KifuNameChange.target_row_id == row["id"],
            )).mappings().all()
            if len(changes) != 1 or changes[0]["after_image"] != row:
                return False
            if table == "kifu_name_research_evidence" and changes[0]["before_image"] is not None:
                return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def persisted_name_eligible(name, evidence, owner_column, raw, batch, context, db=None):
    if context is None or not isinstance(evidence.research_payload, dict):
        return False
    payload = evidence.research_payload
    row, proof = payload.get("candidate"), payload.get("primary_orthographic")
    try:
        if (
            not isinstance(row, dict)
            or not isinstance(proof, dict)
            or proof.get("batch_id") != batch.id
            or payload.get("research") is not None
        ):
            return False
        bindings, candidates, anchors_by_hash, artifact = context
        key = owner_key(row["owner"], row["lang"])
        expected = candidates.get(key)
        if row != expected or proof.get("source_anchor") != anchors_by_hash[row["source_anchor_sha256"]]:
            return False
        if db is not None and not verified_source_live(
            db.connection(), proof["source_anchor"], allow_authoritative_pages_drift=True
        ):
            return False
        # The context already validated every frozen candidate. Equality above binds
        # this untrusted payload to that checked value without hashing the whole batch again.
        owner = row["owner"]
        expected_id = (
            owner.get("id")
            if "id" in owner
            else artifact.get("resolved_refs", {}).get(f"{owner['kind']}:@{owner['ref']}")
        )
        if owner["kind"] != owner_column.removesuffix("_id") or expected_id != getattr(name, owner_column):
            return False
        if (
            row["decision_kind"] != name.decision_kind
            or row["decision_kind"] != evidence.decision_kind
            or row["lang"] != name.lang
            or row["display_name"] != name.display_name
            or row["generation_rule_version"] != name.generation_rule_version
        ):
            return False
        if owner["kind"] == "raw_player" and row.get("raw_value") != raw:
            return False
        for field in ("producer_id", "producer_model", "reviewer_id", "reviewer_model"):
            if getattr(evidence, field) != row[field]:
                return False
        for field in ("produced_at", "reviewed_at"):
            stored, expected_time = getattr(evidence, field), _time(row[field])
            if stored.tzinfo is None:
                expected_time = expected_time.replace(tzinfo=None)
            if stored != expected_time:
                return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
