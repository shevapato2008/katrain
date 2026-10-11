"""Assemble signed-dependency 20-name bundles; leave outer execution approval unsigned."""

import gzip
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_evidence import validate_transliteration_review
from katrain.web.kifu.name_orthographic import VERSION


DIRECTORY = Path(__file__).parent


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def write_gzip(path, value):
    path.write_bytes(gzip.compress(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        mtime=0,
    ))


def build(environment, rule):
    approved = json.loads((DIRECTORY / f"{environment}-batch.approved.json").read_text())
    validate_transliteration_review(approved, "approved_orthographic_batch")
    request = json.loads((DIRECTORY / f"{environment}-batch-review-request.json").read_text())
    assert approved["content"] == request["content"]
    assert all(approved["approval"][field] == request["production"][field]
               for field in ("content_sha256", "producer_id", "producer_model", "produced_at"))
    data = json.load(gzip.open(DIRECTORY / f"{environment}-product-snapshots.json.gz", "rt"))
    inventory = data["inventory"]
    snapshot = data["approved_name_snapshot"]
    aliases = data["known_aliases"]
    registry_row = json.loads((DIRECTORY / f"{environment}-source-registry-readonly.json").read_text())
    registry = registry_row["registry"]
    anchors = json.loads((DIRECTORY / f"{environment}-anchors.approved.json").read_text())
    bindings = json.loads((DIRECTORY / f"{environment}-preimage-bindings.json").read_text())
    binding_by_id = {item["owner"]["id"]: item["binding"] for item in bindings}
    assert len(anchors) == len(bindings) == 20
    assert approved["content"]["catalog_sha256"] == data["catalog_sha256"]
    assert approved["content"]["known_aliases"] == aliases
    batch_hash = canonical_sha256(approved)
    candidates = []
    members = []
    for member in approved["content"]["members"]:
        owner = member["owner"]
        members.append({"owner": owner, "lang": "tw"})
        candidate = {
            **member,
            "decision_kind": "generated",
            "generation_rule_version": VERSION,
            "research_sha256": "",
            "orthographic_batch_sha256": batch_hash,
            "review_status": "approved",
            "review_conclusion": "approved_orthographic_batch",
            "preimage_binding": binding_by_id[owner["id"]],
            **{field: approved["approval"][field] for field in (
                "producer_id", "producer_model", "produced_at",
                "reviewer_id", "reviewer_model", "reviewed_at",
            )},
        }
        candidates.append(candidate)
    assert len(candidates) == len(members) == 20
    bundle = {
        "bundle_format": 1,
        "inventory_format": inventory["inventory_format"],
        "inventory_sha256": inventory["sha256"],
        "registry_version": registry["version"],
        "registry_sha256": canonical_sha256(registry),
        "rule_version": "candidate-v1",
        "catalog_sha256": data["catalog_sha256"],
        "members": members,
        "member_set_sha256": canonical_sha256(members),
        "candidates": candidates,
        "primary_orthographic": {"version": VERSION, "rules": [rule], "batches": [approved]},
    }
    result = validate_bundle(bundle, registry, inventory, anchors,
                             approved_name_snapshot=snapshot)
    if not (result["ready"] and result["write_ready"] and result["approved"] == 20):
        raise RuntimeError(f"{environment}: product validation failed: {result}")
    write_gzip(DIRECTORY / f"{environment}-inventory.json.gz", inventory)
    write_gzip(DIRECTORY / f"{environment}-approved-name-snapshot.json.gz", snapshot)
    write_json(DIRECTORY / f"{environment}-source-registry.json", registry)
    write_json(DIRECTORY / f"{environment}-orthographic-evidence.json", anchors)
    write_gzip(DIRECTORY / f"{environment}-unsigned-bundle.json.gz", bundle)
    summary = {
        "environment": environment,
        "status": "candidate_dependencies_approved_outer_execution_unsigned",
        "bundle_sha256": canonical_sha256(bundle),
        "bundle_members": 20,
        "validation": result,
        "inventory_sha256": inventory["sha256"],
        "catalog_sha256": data["catalog_sha256"],
        "registry_sha256": bundle["registry_sha256"],
        "approved_name_snapshot_sha256": canonical_sha256(snapshot),
        "orthographic_batch_sha256": batch_hash,
    }
    write_json(DIRECTORY / f"{environment}-unsigned-bundle-summary.json", summary)
    print(environment, summary["bundle_sha256"], result)


if __name__ == "__main__":
    rule = json.loads((DIRECTORY / "rule.approved.json").read_text())
    validate_transliteration_review(rule, "approved_orthographic_rule")
    for env in ("PROD", "TEST"):
        build(env, rule)
