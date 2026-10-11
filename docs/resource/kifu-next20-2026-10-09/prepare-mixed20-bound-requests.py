"""Prepare unsigned mixed20 binding and batch review requests from fresh read-only context."""

import copy
import datetime
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_evidence import (
    registry_sha256, validate_primary_orthographic_anchor,
    validate_research_record, validate_transliteration_review,
)
from katrain.web.kifu.name_orthographic import VERSION


D = Path(__file__).parent
ACTOR = "/root/next20_packet_recovered"
MODEL = "gpt-6-sol"
GROUPS = {"jp9": (4771, 5397, 5297, 6599, 6626, 4235, 6629, 6686, 6259),
          "cn7": (600, 229, 595, 385, 662, 320, 391),
          "kba1": (446,)}
KO_IDS = (5396, 4276, 4782)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    with gzip.open(path, "rt") if str(path).endswith(".gz") else open(path) as stream:
        return json.load(stream)


def write_json(path, value, compressed=False):
    if path.exists():
        raise FileExistsError(path)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if compressed:
        path.write_bytes(gzip.compress(raw, mtime=0))
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rules_by_group():
    rules = read(D / "tw-rules.approved.json")
    require(len(rules) == 3, "exact three approved TW rules required")
    indexed = {}
    for rule in rules:
        content = validate_transliteration_review(rule, "approved_orthographic_rule")
        kind = content.get("reference_kind")
        group = "jp9" if kind == "verified_japanese_display" else "kba1" if kind == "official_hanja_preserved" else "cn7"
        require(group not in indexed, "duplicate rule group")
        indexed[group] = rule
    require(set(indexed) == set(GROUPS), "finite rule groups incomplete")
    return indexed


def prepare(environment):
    capture_path = D / f"{environment}-mixed20-fresh-post590-pages.json.gz"
    fresh = read(capture_path)
    require(fresh["environment"] == environment and fresh["read_only"] is True
            and fresh["batch590"]["status"] == "applied"
            and len(fresh["rows"]) == 20, "fresh post-590 read-only context invalid")
    capture_sha = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    byprod = {row["prod_id"]: row for row in fresh["rows"]}
    require(set(byprod) == set(sum((list(group) for group in GROUPS.values()), [])) | set(KO_IDS),
            "mixed20 owner set changed")
    plan = read(D / "mixed20-source-review.json")
    planned = {row["prod_id"]: row for row in plan["tw"] if row["environment"] == environment}
    old = read(D / f"{environment}-tw-source-readonly.json.gz")
    old_byprod = {row["prod_id"]: row for row in old["rows"]}
    approved_anchors = read(D / f"{environment}-tw-anchors.approved.json.gz")
    for anchor in approved_anchors:
        validate_primary_orthographic_anchor(anchor)
    anchors = {anchor["content"]["owner"]["id"]: anchor for anchor in approved_anchors}
    require(len(anchors) == 17, "TW approved anchor set incomplete")
    rules = rules_by_group()
    snapshot = fresh["approved_name_snapshot"]
    aliases = fresh["known_aliases"]
    produced_at = utcnow()
    latest_source_review = max(datetime.datetime.fromisoformat(a["approval"]["reviewed_at"])
                               for a in approved_anchors)
    latest_rule_review = max(datetime.datetime.fromisoformat(r["approval"]["reviewed_at"])
                             for r in rules.values())
    require(datetime.datetime.fromisoformat(produced_at) > max(latest_source_review, latest_rule_review),
            "batch producer timestamp must follow actual source/rule approvals")
    all_bindings = []
    group_members = {group: [] for group in GROUPS}
    for group, prod_ids in GROUPS.items():
        rule = rules[group]
        rule_hash = registry_sha256(rule)
        for prod_id in prod_ids:
            current = byprod[prod_id]
            source = old_byprod[prod_id]
            owner_id = current["id"]
            owner = {"kind": "player", "id": owner_id}
            anchor = anchors[owner_id]
            reviewed = planned[prod_id]
            original, output = reviewed["original_name"], reviewed["display_name"]
            require(current["canonical_name"] == source["canonical_name"]
                    and anchor["content"]["original_name"] == original
                    and anchor["content"]["owner"] == owner,
                    "TW source/owner changed")
            old_source_name = source["source_name"]
            require(old_source_name in current["current_names"], "qualified source name row changed")
            fresh_source = [row for row in snapshot if row["owner"] == owner
                            and row["lang"] == old_source_name["lang"]]
            require(len(fresh_source) == 1
                    and fresh_source[0]["name_sha256"] == registry_sha256(old_source_name)
                    and fresh_source[0]["evidence_sha256"] == registry_sha256(source["source_evidence"]),
                    "source qualification/evidence changed")
            target = current["target_name_preimage"]
            prehash = registry_sha256(target) if target is not None else None
            if group == "jp9":
                require(target is None, "Japanese original TW display target became non-NULL")
            else:
                require(isinstance(target, dict) and target["status"] == "review"
                        and target["evidence_id"] is None and target["player_id"] == owner_id
                        and target["lang"] == "tw", "existing TW target is not evidence-free REVIEW")
            anchor_hash = registry_sha256(anchor)
            candidate_source = {"owner": owner, "lang": "tw", "display_name": output,
                                "decision_kind": "generated", "generation_rule_version": VERSION,
                                "name_preimage_sha256": prehash,
                                "source_anchor_sha256": anchor_hash, "rule_sha256": rule_hash}
            binding = {"actor_id": ACTOR, "actor_model": MODEL,
                       "captured_at": fresh["captured_at"], "bound_at": utcnow(),
                       "name_preimage_sha256": prehash,
                       "source_candidate_sha256": registry_sha256(candidate_source),
                       "capture_sha256": capture_sha}
            if target is not None:
                binding["target_name_preimage"] = target
            member = {"owner": owner, "original_name": original, "lang": "tw",
                      "display_name": output, "source_anchor_sha256": anchor_hash,
                      "rule_sha256": rule_hash,
                      "codepoint_changes": [{"position": index, "input": f"U+{ord(a):04X}",
                                             "output": f"U+{ord(b):04X}"}
                                            for index, (a, b) in enumerate(zip(original, output))],
                      "name_preimage_sha256": prehash,
                      "preimage_binding_sha256": registry_sha256(binding)}
            if group in ("jp9", "kba1", "cn7"):
                member["reference_kind"] = ("verified_japanese_display" if group == "jp9" else
                                            "official_hanja_preserved" if group == "kba1" else
                                            "verified_chinese_display")
            group_members[group].append(member)
            all_bindings.append({"prod_id": prod_id, "owner": owner, "lang": "tw",
                                 "preimage_binding": binding})
    requests = {}
    for group, members in group_members.items():
        require(len(members) == len(GROUPS[group]), "orthographic group incomplete")
        frozen_at = utcnow()
        content = {"version": VERSION, "rule_sha256": registry_sha256(rules[group]),
                   "members": members, "members_sha256": registry_sha256(members),
                   "catalog_sha256": fresh["catalog_sha256"],
                   "approved_name_snapshot_sha256": registry_sha256(snapshot),
                   "known_aliases": aliases, "unresolved_conflicts": [],
                   "complete_name_review": members,
                   "sampled_members": [registry_sha256(member) for member in members],
                   "frozen_at": frozen_at}
        requests[group] = {"status": "pending_root_independent_batch_approval",
                           "content": content,
                           "production": {"producer_id": ACTOR, "producer_model": MODEL,
                                          "produced_at": produced_at,
                                          "content_sha256": registry_sha256(content)},
                           "dependencies": {"source_capture_file_sha256": capture_sha,
                                            "rule_sha256": registry_sha256(rules[group]),
                                            "anchor_sha256": sorted(member["source_anchor_sha256"]
                                                                    for member in members)}}
    source_research = read(D / "ko3-unsigned-research.json.gz")
    ko_records, ko_candidates, ko_bindings = [], [], []
    registry = fresh["source_registry"]["registry"]
    for source in source_research:
        prod_id = source["owner"]["id"]
        require(prod_id in KO_IDS, "unplanned Korean source record")
        current = byprod[prod_id]
        owner = {"kind": "player", "id": current["id"]}
        research = copy.deepcopy(source)
        research["owner"] = research["positive_generation"]["identity"]["owner"] = owner
        for check in research["source_checks"]:
            check["owner"] = owner
        require(research["registry_version"] == registry["version"]
                and research["registry_sha256"] == registry_sha256(registry),
                "source registry changed; KO research needs new root review")
        validate_research_record(research, registry)
        target = current["target_name_preimage"]
        prehash = registry_sha256(target) if target is not None else None
        source_candidate = {"owner": owner, "lang": "ko", "display_name": research["candidate_name"],
                            "decision_kind": "generated", "generation_rule_version": research["generation_rule_version"],
                            "research_sha256": registry_sha256(research), "name_preimage_sha256": prehash}
        binding = {"actor_id": ACTOR, "actor_model": MODEL,
                   "captured_at": fresh["captured_at"], "bound_at": utcnow(),
                   "name_preimage_sha256": prehash,
                   "source_candidate_sha256": registry_sha256(source_candidate),
                   "capture_sha256": capture_sha}
        if target is not None:
            binding["target_name_preimage"] = target
        ko_records.append(research)
        ko_candidates.append({**source_candidate, "review_status": "pending",
                              "producer_id": research["producer_id"],
                              "producer_model": research["producer_model"],
                              "produced_at": research["produced_at"],
                              "preimage_binding": binding})
        ko_bindings.append({"prod_id": prod_id, "owner": owner, "lang": "ko",
                            "preimage_binding": binding})
    ko_request = {"status": "pending_root_positive_source_output_and_binding_approval",
                  "environment": environment, "research_file": f"{environment}-mixed20-ko-research-unsigned.json.gz",
                  "research_sha256": registry_sha256(ko_records),
                  "candidates": ko_candidates,
                  "bindings": ko_bindings,
                  "source_approval": "root-source-rule-review.json",
                  "capture_file_sha256": capture_sha,
                  "requirements": ["Approve exact owner, original, full kana, NIKL steps, generated output and both bounded conflict queries per person.",
                                   "Add generated_review and independent candidate signature only after reviewing these fresh bindings."]}
    tw_binding_by_owner = {row["owner"]["id"]: row["preimage_binding"] for row in all_bindings}
    pending_tw = []
    for group, members in group_members.items():
        for member in members:
            pending_tw.append({**member, "decision_kind": "generated",
                               "generation_rule_version": VERSION, "research_sha256": "",
                               "review_status": "pending", "pending_batch_group": group,
                               "preimage_binding": tw_binding_by_owner[member["owner"]["id"]],
                               "producer_id": ACTOR, "producer_model": MODEL,
                               "produced_at": produced_at})
    for candidate, research in zip(ko_candidates, ko_records):
        candidate["generated_review"] = {
            "decision": "pending", "owner": candidate["owner"], "lang": "ko",
            "display_name": candidate["display_name"],
            "generation_rule_version": candidate["generation_rule_version"],
            "original_name": research["original_name"], "reading": research["reading"],
            "reading_basis_url": research["reading_basis_url"],
            "research_sha256": candidate["research_sha256"],
            "positive_generation_sha256": registry_sha256(research["positive_generation"]),
            "identity_input_review": "pending", "rule_review": "pending",
            "output_review": "pending", "reason": "Pending root review of source, rule, output and fresh binding.",
            "reviewer_id": "", "reviewer_model": "", "reviewed_at": ""}
    pending_input = {
        "status": "pending_root_batch_and_positive_candidate_approval",
        "environment": environment,
        "context_refreshed_at": fresh["captured_at"],
        "preceding_batch_applied": 590,
        "pages_synchronized": True,
        "fresh_capture_file_sha256": capture_sha,
        "inventory": fresh["inventory"], "catalog_sha256": fresh["catalog_sha256"],
        "approved_name_snapshot": snapshot, "known_aliases": aliases,
        "registry": registry,
        "tw_anchors": approved_anchors,
        "orthographic_rules": list(rules.values()),
        "orthographic_batches": [requests[group] for group in GROUPS],
        "ko_research": ko_records,
        "candidates": pending_tw + ko_candidates,
        "ko_prod_to_owner": {str(prod_id): byprod[prod_id]["id"] for prod_id in KO_IDS},
        "owners": [{"owner": {"kind": "player", "id": row["id"]},
                    "preimage": row["owner_preimage"]} for row in fresh["rows"]],
        "fresh_targets": {str(row["id"]): row["target_name_preimage"] for row in fresh["rows"]},
    }
    for group, request in requests.items():
        write_json(D / f"{environment}-{group}-batch-review-request.json", request)
    write_json(D / f"{environment}-mixed20-tw-preimage-bindings.json", all_bindings)
    write_json(D / f"{environment}-mixed20-ko-research-unsigned.json.gz", ko_records, True)
    write_json(D / f"{environment}-mixed20-ko-candidate-review-request.json", ko_request)
    write_json(D / f"{environment}-mixed20-pending-input.json.gz", pending_input, True)
    print(environment, "prepared", sum(len(x) for x in group_members.values()),
          "TW members and", len(ko_candidates), "KO pending candidates")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=("TEST", "PROD"))
    args = parser.parse_args()
    prepare(args.environment)
