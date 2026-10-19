"""Bind two actual read-only captures into finite, unsigned owner review manifests.

This performs no database access and does not invent approval. It excludes any
raw with stale owner/parts, album count disagreement, or a normalized collision.
"""

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256


D = Path(__file__).resolve().parent
PROFILES = ("sgf_chinese_mixed",)
SOURCE_FIELDS = ("raw_value", "profile", "source_file", "owner_id_hint", "old_parts", "core", "names")


def load(environment):
    return json.loads(gzip.decompress((D / f"{environment}-capture.json.gz").read_bytes()))


def verify_source_binding(capture, selection, packet):
    """Reject a captured proposal if the currently frozen source or any value drifted."""
    selection_sha = canonical_sha256(selection)
    packet_sha = canonical_sha256(packet)
    assert packet["selection_sha256"] == selection_sha
    assert capture["selection_sha256"] == selection_sha
    assert capture["source_packet_sha256"] == packet_sha
    expected = {}
    for source in selection["sources"]:
        source_rows = {row["raw_value"]: row for row in packet["sources"][source["file"]]["records"]}
        assert len(source_rows) == len(source["raw_values"])
        for raw in source["raw_values"]:
            row = source_rows[raw]
            assert raw not in expected
            expected[raw] = {
                "raw_value": raw, "profile": source["profile"], "source_file": source["file"],
                "owner_id_hint": row.get("owner_id_from_2026_10_04_snapshot",
                                         row.get("raw_owner_id_hint_2026_10_04")),
                "old_parts": row.get("parts", row.get("old_parser_parts")),
                "core": row["core"], "names": row["names"],
            }
    assert len(expected) == capture["raw_count_requested"] == 150
    captured = {row["raw_value"]: row for row in capture["records"]}
    assert len(captured) == len(capture["records"]) == 150 and set(captured) == set(expected)
    for raw, source in expected.items():
        assert {key: captured[raw][key] for key in SOURCE_FIELDS} == source, raw


def bind(test, prod, *, selection=None, packet=None):
    selection = selection or json.loads((D / "selection.json").read_text())
    packet = packet or json.loads((D / "source-packet.json").read_text())
    verify_source_binding(test, selection, packet)
    verify_source_binding(prod, selection, packet)
    assert test["environment"] == "TEST" and prod["environment"] == "PROD"
    assert test["selection_sha256"] == prod["selection_sha256"]
    assert all(row["profile"] == "sgf_chinese_mixed" for cap in (test, prod) for row in cap["records"])
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
                              "source_packet_sha256": canonical_sha256(packet),
                              "source_basis": "sgf_literal_v1",
                              "assembled_at": datetime.now(timezone.utc).isoformat(),
                              "raw_value_count": len(raws),
                              "raw_value_set_sha256": canonical_sha256(sorted(raws)),
                              "current_null_games": sum(len(by_raw["TEST"][raw]["album_ids"]) for raw in raws),
                              "member_manifest": member_manifest, "records": records,
                              "approval": None}
    return manifests, excluded


def main():
    captures = {env: load(env) for env in ("TEST", "PROD")}
    selection = json.loads((D / "selection.json").read_text())
    source_packet = json.loads((D / "source-packet.json").read_text())
    manifests, excluded = bind(captures["TEST"], captures["PROD"],
                               selection=selection, packet=source_packet)
    source_rows = {row["raw_value"]: row for source in source_packet["sources"].values()
                   for row in source["records"]}
    core_lexicon = {}
    for source in source_packet["sources"].values():
        core_lexicon.update(source["core_lexicon"])
    for profile, manifest in manifests.items():
        path = D / f"{profile}-owner-research-unsigned.json"
        if path.exists():
            raise FileExistsError(path)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        rows_by_env = {env: {row["raw_value"]: row for row in capture["records"]}
                       for env, capture in captures.items()}
        matrix_rows = []
        for member in manifest["records"]:
            raw = member["raw_value"]
            source = source_rows[raw]
            matrix_rows.append({"raw_value": raw, "core_key": source["core"],
                                "raw_parts": member["raw_parts"], "names": source["names"],
                                "current_games": len(rows_by_env["TEST"][raw]["album_ids"]),
                                "scope_sha256": {env: rows_by_env[env][raw]["scope_sha256"]
                                                 for env in captures},
                                "owner_id": {env: rows_by_env[env][raw]["owner"]["id"]
                                             for env in captures}})
        matrix = {"status": "unsigned_name_matrix_for_review", "profile": profile,
                  "owner_manifest_canonical_sha256": canonical_sha256(manifest),
                  "source_packet_canonical_sha256": canonical_sha256(source_packet),
                  "capture_file_sha256": {env: hashlib.sha256(
                      (D / f"{env}-capture.json.gz").read_bytes()).hexdigest() for env in captures},
                  "core_lexicon": {core: core_lexicon[core] for core in sorted(
                      {row["core_key"] for row in matrix_rows})},
                  "raw_titles": len(matrix_rows), "proposed_name_cells": 5 * len(matrix_rows),
                  "current_games": manifest["current_null_games"],
                  "records": matrix_rows, "approval": None}
        matrix_path = D / f"{profile}-name-matrix-unsigned.json"
        if matrix_path.exists():
            raise FileExistsError(matrix_path)
        matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n")
    report = {"status": "unsigned",
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
