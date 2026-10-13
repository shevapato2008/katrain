"""Freeze one unsigned 20-name review batch per environment after source/rule approval."""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_evidence import (
    registry_sha256, validate_primary_orthographic_anchor, validate_transliteration_review,
)
from katrain.web.kifu.name_orthographic import VERSION


DIRECTORY = Path(__file__).parent
PRODUCER = "/root/restore_tw_twenty"
MODEL = "GPT-6 (exact runtime variant unavailable)"


def now():
    return datetime.now(timezone.utc).isoformat()


def write(name, value):
    (DIRECTORY / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def build(environment, rule):
    captured = json.load(gzip.open(DIRECTORY / f"{environment}-product-snapshots.json.gz", "rt"))
    manifest = [row for row in json.loads((DIRECTORY / "unsigned-manifest.json").read_text())["rows"]
                if row["environment"] == environment]
    anchors = json.loads((DIRECTORY / f"{environment}-anchors.approved.json").read_text())
    assert len(manifest) == len(anchors) == 20
    for anchor in anchors:
        validate_primary_orthographic_anchor(anchor)
    anchors_by_id = {anchor["content"]["owner"]["id"]: anchor for anchor in anchors}
    assert set(anchors_by_id) == {row["player_id"] for row in manifest}
    snapshot = captured["approved_name_snapshot"]
    aliases = captured["known_aliases"]
    rule_hash = registry_sha256(rule)
    approved_rule_at = datetime.fromisoformat(rule["approval"]["reviewed_at"])
    approved_anchor_at = max(datetime.fromisoformat(anchor["approval"]["reviewed_at"]) for anchor in anchors)
    produced_at = now()
    assert datetime.fromisoformat(produced_at) > max(approved_rule_at, approved_anchor_at)
    capture_time = now()
    source_scope = []
    members = []
    bindings = []
    for row in manifest:
        owner = {"kind": "player", "id": row["player_id"]}
        anchor = anchors_by_id[row["player_id"]]
        original = anchor["content"]["original_name"]
        output = row["candidate_tw_display"]
        assert original == row["cn_display"] and len(original) == len(output)
        assert row["tw_preimage"] is None
        current_cn = [item for item in snapshot if item["owner"] == owner and item["lang"] == "cn"]
        assert len(current_cn) == 1
        assert current_cn[0]["display_name"] == original
        assert current_cn[0]["name_sha256"] == row["source_name_sha256"]
        assert current_cn[0]["evidence_sha256"] == row["source_evidence_sha256"]
        assert not any(item["owner"] == owner and item["lang"] == "tw" for item in snapshot)
        key = normalize_alias(output)
        assert not any(item["owner"] != owner and item["lang"] == "tw"
                       and normalize_alias(item["display_name"]) == key for item in snapshot)
        assert not any(item["owner"] != owner and normalize_alias(item["name"]) == key for item in aliases)
        source_scope.append({"owner": owner, "lang": "tw", "name_preimage_sha256": None,
                             "source_anchor_sha256": registry_sha256(anchor),
                             "source_name_sha256": row["source_name_sha256"],
                             "source_evidence_sha256": row["source_evidence_sha256"]})
    capture = {
        "environment": environment, "captured_at": capture_time,
        "inventory_sha256": captured["inventory"]["sha256"],
        "catalog_sha256": captured["catalog_sha256"],
        "approved_name_snapshot_sha256": registry_sha256(snapshot),
        "known_aliases_sha256": registry_sha256(aliases),
        "scope": source_scope,
    }
    capture_hash = registry_sha256(capture)
    write(f"{environment}-preimage-binding-capture.json", capture)
    for row in manifest:
        owner = {"kind": "player", "id": row["player_id"]}
        anchor = anchors_by_id[row["player_id"]]
        original, output = row["cn_display"], row["candidate_tw_display"]
        candidate_source = {
            "owner": owner, "lang": "tw", "display_name": output,
            "decision_kind": "generated", "generation_rule_version": VERSION,
            "name_preimage_sha256": None,
            "source_anchor_sha256": registry_sha256(anchor),
            "rule_sha256": rule_hash,
        }
        bound_at = now()
        binding = {
            "actor_id": PRODUCER, "actor_model": MODEL,
            "captured_at": capture_time, "bound_at": bound_at,
            "name_preimage_sha256": None,
            "source_candidate_sha256": registry_sha256(candidate_source),
            "capture_sha256": capture_hash,
        }
        bindings.append({"owner": owner, "binding": binding})
        members.append({
            "owner": owner, "original_name": original, "lang": "tw",
            "display_name": output,
            "source_anchor_sha256": registry_sha256(anchor),
            "rule_sha256": rule_hash,
            "codepoint_changes": [
                {"position": index, "input": f"U+{ord(source):04X}", "output": f"U+{ord(target):04X}"}
                for index, (source, target) in enumerate(zip(original, output))
            ],
            "name_preimage_sha256": None,
            "preimage_binding_sha256": registry_sha256(binding),
            "reference_kind": "verified_chinese_display",
        })
    assert len({(member["lang"], normalize_alias(member["display_name"])) for member in members}) == 20
    frozen_at = now()
    assert all(datetime.fromisoformat(item["binding"]["bound_at"])
               <= datetime.fromisoformat(frozen_at) for item in bindings)
    content = {
        "version": VERSION, "rule_sha256": rule_hash,
        "members": members, "members_sha256": registry_sha256(members),
        "catalog_sha256": captured["catalog_sha256"],
        "approved_name_snapshot_sha256": registry_sha256(snapshot),
        "known_aliases": aliases, "unresolved_conflicts": [],
        "complete_name_review": members,
        "sampled_members": [registry_sha256(member) for member in members],
        "frozen_at": frozen_at,
    }
    write(f"{environment}-preimage-bindings.json", bindings)
    write(f"{environment}-batch-review-request.json", {
        "status": "pending_independent_batch_approval", "content": content,
        "production": {"producer_id": PRODUCER, "producer_model": MODEL,
                       "produced_at": produced_at, "content_sha256": registry_sha256(content)},
        "dependencies": {"rule_sha256": rule_hash,
                         "anchor_sha256": sorted(registry_sha256(anchor) for anchor in anchors),
                         "preimage_capture_sha256": capture_hash},
    })
    print(environment, "members", len(members), "produced", produced_at,
          "frozen", frozen_at, "content sha256", registry_sha256(content))


if __name__ == "__main__":
    rule = json.loads((DIRECTORY / "rule.approved.json").read_text())
    validate_transliteration_review(rule, "approved_orthographic_rule")
    for env in ("PROD", "TEST"):
        build(env, rule)
