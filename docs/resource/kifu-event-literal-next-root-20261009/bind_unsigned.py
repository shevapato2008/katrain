"""Bind two actual read-only captures into finite, unsigned owner review manifests.

This performs no database access and does not invent approval. It excludes any
raw with stale owner/parts, album count disagreement, or a normalized collision.
"""

from datetime import datetime, timezone
import gzip
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256


D = Path(__file__).resolve().parent
PROFILES = ("sgf_chinese_mixed", "sgf_english")


def load(environment):
    return json.loads(gzip.decompress((D / f"{environment}-capture.json.gz").read_bytes()))


def bind(test, prod):
    assert test["environment"] == "TEST" and prod["environment"] == "PROD"
    assert test["selection_sha256"] == prod["selection_sha256"]
    by_env = {"TEST": test, "PROD": prod}
    by_raw = {env: {row["raw_value"]: row for row in cap["records"]}
              for env, cap in by_env.items()}
    assert len(by_raw["TEST"]) == len(by_raw["PROD"]) == 150
    assert set(by_raw["TEST"]) == set(by_raw["PROD"])
    collision = {env: {item["raw_value"] for item in cap["external_collisions"]}
                 for env, cap in by_env.items()}
    grouped = {profile: [] for profile in PROFILES}
    excluded = []
    for raw in sorted(by_raw["TEST"]):
        left, right = by_raw["TEST"][raw], by_raw["PROD"][raw]
        reasons = []
        for env, row in (("TEST", left), ("PROD", right)):
            reasons.extend(f"{env}: {reason}" for reason in row["reasons"])
            if raw in collision[env]:
                reasons.append(f"{env}: normalized external name collision")
        for key in ("profile", "old_parts", "core", "names", "source_file"):
            if left[key] != right[key]:
                reasons.append(f"TEST/PROD {key} mismatch")
        if len(left["album_ids"]) != len(right["album_ids"]):
            reasons.append("TEST/PROD current album count mismatch")
        if reasons:
            excluded.append({"raw_value": raw, "reasons": sorted(set(reasons))})
        else:
            grouped[left["profile"]].append(raw)
    manifests = {}
    for profile, raws in grouped.items():
        if not raws:
            continue
        records = []
        member_manifest = {}
        for env, cap in by_env.items():
            members = []
            for raw in raws:
                row = by_raw[env][raw]
                members.append({"raw_value": raw, "raw_event_id": row["owner"]["id"],
                                "album_ids": row["album_ids"], "scope_rows": row["scope_rows"],
                                "scope_sha256": row["scope_sha256"]})
            member_manifest[env] = {"base_sha256": cap["base_sha256"],
                                    "inventory_sha256": cap["inventory_sha256"],
                                    "catalog_sha256": cap["catalog_sha256"],
                                    "live_scope_captured_at": cap["captured_at"],
                                    "members": members}
        for raw in raws:
            row = by_raw["TEST"][raw]
            records.append({"raw_value": raw, "source_file": row["source_file"],
                            "raw_parts": row["old_parts"],
                            "owners": {env: {"raw_event_id": by_raw[env][raw]["owner"]["id"],
                                             "preimage": by_raw[env][raw]["owner"]}
                                       for env in by_env}})
        manifests[profile] = {"status": "unsigned_owner_research", "profile": profile,
                              "selection_sha256": test["selection_sha256"],
                              "source_packet_sha256": canonical_sha256(json.loads(
                                  (D / "source-packet-v2-english150.json").read_text())),
                              "source_basis": "sgf_literal_v1",
                              "assembled_at": datetime.now(timezone.utc).isoformat(),
                              "raw_value_count": len(raws),
                              "raw_value_set_sha256": canonical_sha256(sorted(raws)),
                              "current_null_games": sum(len(by_raw["TEST"][raw]["album_ids"]) for raw in raws),
                              "member_manifest": member_manifest, "records": records,
                              "approval": None}
    return manifests, excluded


def main():
    manifests, excluded = bind(load("TEST"), load("PROD"))
    for profile, manifest in manifests.items():
        path = D / f"{profile}-owner-research-unsigned.json"
        if path.exists():
            raise FileExistsError(path)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    report = {"status": "unsigned",
              "runtime_compatibility": json.loads((D / "runtime-compatibility.json").read_text()),
              "manifests": {
        profile: {"raw_titles": manifest["raw_value_count"],
                  "current_games": manifest["current_null_games"],
                  "canonical_sha256": canonical_sha256(manifest)}
        for profile, manifest in manifests.items()}, "excluded": excluded}
    path = D / "binding-report.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"profiles": report["manifests"], "excluded": len(excluded)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
