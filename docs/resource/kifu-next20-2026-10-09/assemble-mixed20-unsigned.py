"""Assemble the next mixed 17 TW + 3 KO format-2 packet after root review.

This deliberately has no capture, signature, database, or network code. The root
supplies fresh, approved input only after batch 590 and page synchronization.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_evidence import (
    registry_sha256,
    validate_positive_ja_ko_candidate,
    validate_primary_orthographic_anchor,
    validate_transliteration_review,
)
from katrain.web.kifu.name_orthographic import VERSION


D = Path(__file__).parent
TW_IDS = (4771, 5397, 5297, 6599, 6626, 4235, 6629, 6686, 6259,
          600, 229, 595, 385, 662, 320, 446, 391)
KO = {
    5396: ("浜中隆光", "하마나카 다카미쓰"),
    4276: ("奥村靖", "오쿠무라 야스시"),
    4782: ("明戸和巳", "아케도 가즈미"),
}


def read(path):
    with gzip.open(path, "rt") if str(path).endswith(".gz") else open(path) as stream:
        return json.load(stream)


def save_gzip(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_rows(environment):
    source = read(D / f"{environment}-tw-source-readonly.json.gz")
    rows = {row["prod_id"]: row for row in source["rows"]}
    require(tuple(rows) == TW_IDS, "TW source row order or membership changed")
    require(all(row["source_qualified_product_gate"]
                and (row["verified_source_live"] is True if prod_id != 446
                     else row["verified_source_live"] is None)
                for prod_id, row in rows.items()), "TW source not qualified")
    return rows


def pending_anchors(environment):
    requests = [read(D / "tw-unsigned-anchor-review-requests.json"),
                read(D / "tw-cn7-pending-gate-anchor-review-requests.json")]
    pending = [row for request in requests for row in request["rows"]
               if row["environment"] == environment]
    require(len(pending) == 17, "expected exactly 17 pending TW anchors")
    return {row["content"]["owner"]["id"]: row for row in pending}


def checked_anchors(environment, approved, rows):
    pending = pending_anchors(environment)
    require(len(approved) == 17, "expected 17 approved TW anchors")
    by_owner = {}
    for anchor in approved:
        validate_primary_orthographic_anchor(anchor)
        owner_id = anchor["content"]["owner"]["id"]
        require(owner_id in pending and owner_id not in by_owner, "unplanned TW anchor owner")
        original = pending[owner_id]
        require(anchor["content"] == original["content"]
                and anchor["approval"]["content_sha256"] == original["production"]["content_sha256"]
                and all(anchor["approval"][key] == original["production"][key]
                        for key in ("producer_id", "producer_model", "produced_at")),
                "TW anchor differs from retained actual source packet")
        require(anchor["content"]["owner"] == {"kind": "player", "id": owner_id},
                "TW anchor owner mismatch")
        by_owner[owner_id] = anchor
    require(set(by_owner) == {row["id"] for row in rows.values()}, "TW anchor set mismatch")
    return by_owner


def checked_rules(approved):
    requests = [read(D / name) for name in (
        "tw-jp-retention-rule-request.json", "tw-cn7-finite-rule-request.json",
        "tw-official-hanja-rule-request.json")]
    require(len(approved) == 3, "expected exactly three orthographic rules")
    expected = {registry_sha256(request["content"]): request for request in requests}
    rules = {}
    for rule in approved:
        validate_transliteration_review(rule, "approved_orthographic_rule")
        digest = registry_sha256(rule["content"])
        require(digest in expected and digest not in rules, "unplanned orthographic rule")
        original = expected[digest]
        require(rule["content"] == original["content"]
                and rule["approval"]["content_sha256"] == original["production"]["content_sha256"]
                and all(rule["approval"][key] == original["production"][key]
                        for key in ("producer_id", "producer_model", "produced_at")),
                "orthographic rule differs from retained request")
        rules[digest] = rule
    return rules


def checked_tw_candidates(environment, candidates, anchors, rows, fresh_targets):
    plan = read(D / "mixed20-source-review.json")
    planned = {row["prod_id"]: row for row in plan["tw"] if row["environment"] == environment}
    require(set(planned) == set(TW_IDS), "review sheet TW set mismatch")
    require(len(candidates) == 17, "expected 17 TW candidates")
    by_owner = {}
    for candidate in candidates:
        owner = candidate["owner"]
        require(owner["kind"] == "player" and candidate["lang"] == "tw"
                and candidate["decision_kind"] == "generated"
                and candidate["generation_rule_version"] == VERSION,
                "TW candidate scope invalid")
        owner_id = owner["id"]
        require(owner_id in anchors and owner_id not in by_owner, "unplanned TW candidate")
        row = next(item for item in rows.values() if item["id"] == owner_id)
        reviewed = planned[row["prod_id"]]
        require(candidate["display_name"] == reviewed["display_name"]
                and candidate["original_name"] == reviewed["original_name"]
                and candidate["source_anchor_sha256"] == registry_sha256(anchors[owner_id]),
                "TW candidate differs from source review sheet")
        target = fresh_targets[str(owner_id)]
        expected_hash = registry_sha256(target) if target is not None else None
        require(candidate["name_preimage_sha256"] == expected_hash,
                "TW candidate differs from fresh complete target preimage")
        binding = candidate["preimage_binding"]
        require(binding["name_preimage_sha256"] == expected_hash,
                "TW binding hash differs from target preimage")
        if target is None:
            require(row["prod_id"] in TW_IDS[:9], "unexpected empty TW target")
        else:
            require(row["prod_id"] in TW_IDS[9:] and target["id"] > 0
                    and target["player_id"] == owner_id and target["lang"] == "tw"
                    and target["status"] == "review" and target["evidence_id"] is None,
                    "existing TW target is not an unqualified REVIEW row")
            require(binding.get("target_name_preimage") == target,
                    "complete REVIEW target must be signed in the candidate binding")
        by_owner[owner_id] = candidate
    require(set(by_owner) == set(anchors), "TW candidate set incomplete")


def checked_ko(environment, candidates, research, prod_to_owner, fresh_targets, registry):
    original = read(D / "ko3-unsigned-research.json.gz")
    original_by_prod = {row["owner"]["id"]: row for row in original}
    require(set(original_by_prod) == set(KO), "retained KO research set changed")
    require(set(map(int, prod_to_owner)) == set(KO), "KO PROD-to-environment owner map incomplete")
    require(len(set(prod_to_owner.values())) == 3, "KO owners must be distinct")
    require(len(candidates) == len(research) == 3, "expected three KO candidates/research records")
    by_owner = {row["owner"]["id"]: row for row in research}
    for prod_id, (original_name, output) in KO.items():
        owner_id = prod_to_owner[str(prod_id)]
        require(owner_id in by_owner, "KO research owner missing")
        row = by_owner[owner_id]
        frozen = original_by_prod[prod_id]
        require(row["original_name"] == frozen["original_name"] == original_name
                and row["candidate_name"] == frozen["candidate_name"] == output
                and row["reading"] == frozen["reading"]
                and row["positive_generation"]["rules"] == frozen["positive_generation"]["rules"]
                and [(s["url"], s["body_sha256"]) for s in row["source_checks"]]
                == [(s["url"], s["body_sha256"]) for s in frozen["source_checks"]],
                "KO source, reading or NIKL rule differs from retained capture")
    require({row["owner"]["id"] for row in candidates} == set(by_owner), "KO candidate/research owners differ")
    for candidate in candidates:
        owner_id = candidate["owner"]["id"]
        row = by_owner[owner_id]
        require(candidate["lang"] == "ko" and candidate["display_name"] == row["candidate_name"]
                and candidate["research_sha256"] == registry_sha256(row),
                "KO candidate differs from approved positive research")
        target = fresh_targets[str(owner_id)]
        expected_hash = registry_sha256(target) if target is not None else None
        require(candidate["name_preimage_sha256"] == expected_hash
                and candidate["preimage_binding"]["name_preimage_sha256"] == expected_hash,
                "KO candidate differs from fresh target preimage")
        validate_positive_ja_ko_candidate(candidate, row, registry)


def assemble(environment, input_path):
    data = read(input_path)
    require(data["environment"] == environment and data["status"] == "root_approved_fresh_post590_pages",
            "root fresh-context release missing")
    require(data["context_refreshed_at"] and data["preceding_batch_applied"] >= 590
            and data["pages_synchronized"] is True, "preceding batch/page context incomplete")
    rows = source_rows(environment)
    anchors = checked_anchors(environment, data["tw_anchors"], rows)
    rules = checked_rules(data["orthographic_rules"])
    batches = data["orthographic_batches"]
    require(len(batches) == 3, "expected JP9, CN7 and KBA1 orthographic batches")
    for batch in batches:
        validate_transliteration_review(batch, "approved_orthographic_batch")
        require(batch["content"]["rule_sha256"] in {registry_sha256(rule) for rule in rules.values()},
                "batch rule outside reviewed set")
    candidates = data["candidates"]
    require(len(candidates) == 20, "mixed packet requires exactly 20 candidates")
    tw = [row for row in candidates if row["lang"] == "tw"]
    ko = [row for row in candidates if row["lang"] == "ko"]
    checked_tw_candidates(environment, tw, anchors, rows, data["fresh_targets"])
    inventory, registry = data["inventory"], data["registry"]
    checked_ko(environment, ko, data["ko_research"], data["ko_prod_to_owner"],
               data["fresh_targets"], registry)
    members = [{"owner": row["owner"], "lang": row["lang"]} for row in candidates]
    owners = data["owners"]
    require(len(owners) == 20 and len({entry["owner"]["id"] for entry in owners}) == 20,
            "format-2 requires all 20 distinct owner declarations")
    require({entry["owner"]["id"] for entry in owners}
            == {row["owner"]["id"] for row in candidates}, "owner declarations differ from candidates")
    bundle = {
        "bundle_format": 2, "inventory_format": inventory["inventory_format"],
        "inventory_sha256": inventory["sha256"], "registry_version": registry["version"],
        "registry_sha256": registry_sha256(registry), "rule_version": "candidate-v1",
        "catalog_sha256": data["catalog_sha256"], "members": members,
        "member_set_sha256": canonical_sha256(members), "candidates": candidates,
        "owners": owners, "owner_set_sha256": canonical_sha256(owners),
        "album_links": [], "link_set_sha256": canonical_sha256([]),
        "primary_orthographic": {"version": VERSION, "rules": list(rules.values()), "batches": batches},
    }
    evidence = list(anchors.values()) + data["ko_research"]
    report = validate_bundle(bundle, registry, inventory, evidence,
                             approved_name_snapshot=data["approved_name_snapshot"])
    require(report["ready"] and report["write_ready"] and report["approved"] == 20,
            f"native product validation failed: {report}")
    output = D / f"{environment}-mixed20-unsigned-bundle.json.gz"
    require(not output.exists(), f"refusing to overwrite {output}")
    save_gzip(output, bundle)
    save_gzip(D / f"{environment}-mixed20-unsigned-evidence.json.gz", evidence)
    (D / f"{environment}-mixed20-unsigned-summary.json").write_text(
        json.dumps({"status": "dependencies_approved_outer_execution_unsigned",
                    "environment": environment, "bundle_sha256": canonical_sha256(bundle),
                    "evidence_sha256": canonical_sha256(evidence), "validation": report,
                    "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest()},
                   ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(environment, "PASS unsigned mixed20 format2", canonical_sha256(bundle))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=("TEST", "PROD"))
    parser.add_argument("approved_input", type=Path,
                        help="root-approved fresh post-590/page JSON or JSON.gz input")
    args = parser.parse_args()
    assemble(args.environment, args.approved_input)
