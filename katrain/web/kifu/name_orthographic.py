"""Frozen, independently approved Chinese person-name orthographic outputs."""

from datetime import datetime
import unicodedata

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
EXCLUDED_CHARACTERS = frozenset("于於钟鍾鐘岳嶽杰傑")
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
    for row in snapshot:
        _require(
            isinstance(row, dict)
            and isinstance(row.get("display_name"), str)
            and row.get("review_status") == "approved",
            "orthographic approved-name snapshot invalid",
        )
        owner_key(row.get("owner"), row.get("lang"))
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
            },
            "orthographic rule fields invalid",
        )
        expected = {"tw": ("zh-Hans", "Hans", "Hant", "TW"), "cn": ("zh-Hant", "Hant", "Hans", "CN")}
        _require(
            content.get("version") == VERSION
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
                and owner["kind"] in {"player", "raw_player"}
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
                and source["source_script"] == r["source_script"],
                "orthographic member source/owner scope mismatch",
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
            for existing in snapshot:
                _require(
                    not (
                        existing["owner"] == owner
                        and existing["lang"] == member["lang"]
                        and existing.get("decision_kind") == "conventional"
                    ),
                    "orthographic cannot replace known conventional name",
                )
                _require(
                    not (
                        existing["owner"] != owner
                        and existing["lang"] == member["lang"]
                        and _normalize(existing["display_name"]) == normalized[1]
                    ),
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


def persisted_name_eligible(name, evidence, owner_column, raw, batch, context):
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
