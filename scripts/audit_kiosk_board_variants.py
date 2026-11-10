#!/usr/bin/env python3
"""Audit a previously exported snapshot, offline. Never opens a database/network.

Example:
  .venv/bin/python scripts/audit_kiosk_board_variants.py \
    --input /tmp/kiosk-small-content-20261024.json --output /tmp/kiosk19-audit.json

The policy is a review artifact, not generated/expanded by this audit. A newly
changed source stays unavailable until its text and executable goal are reviewed.
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.content import board_variants as bv


def source_detail(record):
    """Use actual exported hint; never infer a source instruction from PL/category."""
    fields = {
        "id": "id",
        "level": "level",
        "category": "category",
        "hint": "hint",
        "boardSize": "board_size",
        "initialBlack": "initial_black",
        "initialWhite": "initial_white",
        "sgfContent": "sgf_content",
    }
    return {api: record[db] for api, db in fields.items()}


def public_step(record, language):
    payload = record["payload"]
    effective = language if language in payload["translations"] else "en"
    return {key: payload[key] for key in bv.STRUCTURE_FIELDS} | {
        "book_id": 0,
        "figure_id": 0,
        "locale": {"requested": language, "effective": effective, "text": payload["translations"][effective]},
        "screenshot": None,
        "screenshot_status": "pending",
    }


def audit(snapshot, language="zh-cn"):
    policy = bv._policy()
    report = {
        "policy_version": bv.POLICY_VERSION,
        "locale": language,
        "proof_scope": policy.get("proof_scope"),
        "summary": {},
        "tsumego": [],
        "ogs": [],
    }
    for kind in ("tsumego", "ogs"):
        for record in snapshot[kind]:
            source = source_detail(record) if kind == "tsumego" else public_step(record, language)
            source_id = str(source["id"] if kind == "tsumego" else source["source_id"])
            adapted = bv.adapt_tsumego_detail(source) if kind == "tsumego" else bv.adapt_ogs_step(source)
            metadata = adapted["board_variant"]
            entry = policy.get(kind, {}).get(source_id, {})
            locale_approved = kind == "tsumego" or source["locale"]["effective"] in entry.get("locale_sha256", {})
            result = {
                "id": source_id,
                **metadata,
                "reason_code": entry.get("reason_code", "unreviewed"),
                "policy_declared_available": entry.get("available", False) and locale_approved,
                "source_declared_available": entry.get("available", False),
                "derived_sha256": bv.digest({k: v for k, v in adapted.items() if k != "board_variant"}),
                "branch_count": None,
                "node_count": None,
                "certificate_sha256": None,
            }
            if kind == "ogs":
                result["page"] = source["page"]
                if entry.get("available") and not locale_approved:
                    result["reason_code"] = "locale_unreviewed"
            if metadata["status"] == "adapted":
                prepare = bv._prepare_tsumego if kind == "tsumego" else bv._prepare_ogs
                certificate = bv.verify_goal(prepare(source), entry["goal"], source.get("exercise"))
                result.update(
                    branch_count=certificate["branch_count"],
                    node_count=certificate["node_count"],
                    certificate_sha256=bv.digest(certificate),
                    goal=entry["goal"],
                )
            else:
                # Counts describe all source branches, including excluded content.
                try:
                    if kind == "tsumego":
                        from katrain.core.sgf_parser import SGF

                        nodes = SGF.parse_sgf(source["sgfContent"]).nodes_in_tree
                        result.update(branch_count=sum(not n.children for n in nodes), node_count=len(nodes))
                    elif source["exercise"].get("tree"):
                        nodes, stack = [], [source["exercise"]["tree"]]
                        while stack:
                            node = stack.pop()
                            nodes.append(node)
                            stack.extend(node["children"])
                        result.update(branch_count=sum(not n["children"] for n in nodes), node_count=len(nodes))
                    else:
                        result.update(branch_count=0, node_count=1)
                except (KeyError, ValueError, TypeError, AttributeError):
                    pass
            report[kind].append(result)
        records = report[kind]
        report["summary"][kind] = {
            "total": len(records),
            "status": dict(Counter(r["status"] for r in records)),
            "reason_codes": dict(Counter(r["reason_code"] for r in records if r["status"] != "adapted")),
            "reasons": dict(Counter(r["reason"] for r in records if r["status"] != "adapted")),
            "approved_but_failed": sum(r["policy_declared_available"] and r["status"] != "adapted" for r in records),
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--locale", default="zh-cn")
    args = parser.parse_args()
    raw = args.input.read_bytes()
    report = audit(json.loads(raw), args.locale)
    report["input_sha256"] = hashlib.sha256(raw).hexdigest()
    report["policy_sha256"] = hashlib.sha256(
        Path(bv.__file__).with_name("kiosk19_policy.json").read_bytes()
    ).hexdigest()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.csv:
        fields = (
            "kind",
            "id",
            "status",
            "source_size",
            "target_size",
            "offset",
            "reason_code",
            "reason",
            "source_sha256",
            "derived_sha256",
            "branch_count",
            "node_count",
            "certificate_sha256",
        )
        with args.csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for kind in ("tsumego", "ogs"):
                for row in report[kind]:
                    writer.writerow({"kind": kind, **row})
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    # Other requested locales honestly remain unavailable; only reviewed locales
    # must have no policy-declared source fail verification.
    return int(args.locale in ("en", "zh-cn") and any(v["approved_but_failed"] for v in report["summary"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
