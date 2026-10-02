"""Full inventory event groups remain exact, pending review manifests."""

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from katrain.web.kifu.name_inventory import SELECTION_COLUMNS, SELECTION_COLUMNS_V4, _hash_row
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_structure import build_event_group_manifest
from scripts.kifu_name_groups import main


def _inventory(values):
    associations = []
    for row in values:
        associations.extend([[len(associations) + i + 1, row["value"]] for i in range(row["occurrences"])])
    return {
        "inventory_format": 2,
        "sha256": "a" * 64,
        "counts": {"all": len(associations)},
        "distinct_values": {"all": {"event": len({row["value"] for row in values})}},
        "association_columns": ["id", "event"],
        "album_associations": associations,
        "scopes": {"all": {"values": {"event": values}}},
    }


def _selected_inventory(values, selected_rows):
    inventory = _inventory(values)
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
    for row in selected_rows:
        _hash_row(digest, b"E", row)
    inventory.update(
        inventory_format=3,
        base_sha256="b" * 64,
        event_selection={
            "selection_format": 1,
            "columns": list(SELECTION_COLUMNS),
            "rows": selected_rows,
            "sha256": digest.hexdigest(),
        },
    )
    return inventory


def _selected_v4_inventory(values, selected_rows):
    inventory = _selected_inventory(values, selected_rows)
    rows = []
    for album_id, raw, sgf, reviewer, reviewed_at, batch_id, bundle_sha in selected_rows:
        image = {"album_id": album_id, "event_id": None, "batch_id": batch_id, "selected_raw": raw,
                 "sgf_sha256": sgf, "property_name": "GN", "property_index": 1,
                 "status": "approved", "rule_version": "19x19-gnugo-second-gn-v1",
                 "reviewer_id": reviewer, "reviewed_at": reviewed_at,
                 "created_at": "2026-10-02T10:00:00"}
        rows.append([album_id, raw, sgf, reviewer, reviewed_at, batch_id, bundle_sha,
                     None, image, canonical_sha256(image), None, None])
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (2, SELECTION_COLUMNS_V4))
    for row in rows:
        _hash_row(digest, b"E", row)
    inventory.update(inventory_format=4, event_selection={"selection_format": 2,
        "columns": list(SELECTION_COLUMNS_V4), "rows": rows, "sha256": digest.hexdigest()})
    return inventory


def _selection(album_id, raw):
    return [album_id, raw, "c" * 64, "independent-reviewer", "2026-10-02T10:00:00", 5, "d" * 64]


def _artifact_sha(inventory):
    canonical = json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_group_manifest_binds_inventory_and_exact_raw_members_without_approval():
    rows = [
        {"value": "2026年世界围棋团体赛第2轮", "occurrences": 4, "affected_games": 4},
        {"value": "2027年世界围棋团体赛第3局", "occurrences": 2, "affected_games": 2},
        {"value": "2026年世界女子围棋团体赛第2轮", "occurrences": 1, "affected_games": 1},
        {"value": None, "occurrences": 3, "affected_games": 3},
    ]
    manifest = build_event_group_manifest(_inventory(rows))
    assert manifest["inventory_format"] == 2
    assert manifest["inventory_sha256"] == "a" * 64
    assert len(manifest["sha256"]) == 64
    assert manifest["group_count"] == 3
    group = next(item for item in manifest["groups"] if item["core"] == "世界围棋团体赛")
    assert group["status"] == "pending_review"
    assert group["occurrences"] == 6
    assert [item["raw_value"] for item in group["members"]] == [
        "2026年世界围棋团体赛第2轮", "2027年世界围棋团体赛第3局"
    ]
    assert group["members"][0]["structure"]["components"][-1]["kind"] == "round"
    assert group["members"][1]["structure"]["components"][-1]["kind"] == "game"
    assert build_event_group_manifest(_inventory(list(reversed(rows))))["sha256"] == manifest["sha256"]


def test_ordinal_editions_group_only_within_the_same_full_series_name():
    rows = [
        {"value": raw, "occurrences": 1, "affected_games": 1}
        for raw in ("28th Honinbo", "29th Honinbo", "14th Old Meijin", "1st Meijin")
    ]
    manifest = build_event_group_manifest(_inventory(rows))
    assert manifest["rule_version"] == "event-components-v4"
    assert manifest["group_count"] == 3
    honinbo = next(group for group in manifest["groups"] if group["core"] == "Honinbo")
    assert {member["raw_value"] for member in honinbo["members"]} == {"28th Honinbo", "29th Honinbo"}
    assert all(group["status"] == "pending_review" for group in manifest["groups"])
    assert {group["core"] for group in manifest["groups"]} == {"Honinbo", "Old Meijin", "Meijin"}


def test_new_ordinal_groups_do_not_erase_distinct_series_qualifiers():
    rows = [
        {"value": raw, "occurrences": 1, "affected_games": 1}
        for raw in ("Judan,31st", "Judan,32nd", "Meijin(Yomiuri),14th", "27thTengen", "28thTengen", "27thOldTengen")
    ]
    manifest = build_event_group_manifest(_inventory(rows))
    assert manifest["group_count"] == 4
    judan = next(group for group in manifest["groups"] if group["core"] == "Judan")
    assert {member["raw_value"] for member in judan["members"]} == {"Judan,31st", "Judan,32nd"}
    assert {group["core"] for group in manifest["groups"]} == {"Judan", "Meijin(Yomiuri)", "Tengen", "OldTengen"}


def test_group_manifest_refuses_old_inventory_and_duplicate_raw_values():
    rows = [{"value": "赛事", "occurrences": 1, "affected_games": 1}]
    old = _inventory(rows)
    old["inventory_format"] = 1
    try:
        build_event_group_manifest(old)
    except ValueError as exc:
        assert "inventory_format" in str(exc)
    else:
        raise AssertionError("old inventory accepted")
    try:
        build_event_group_manifest(_inventory(rows + rows))
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate raw value accepted")


def test_group_manifest_refuses_truncated_value_rows_even_with_plausible_hash():
    rows = [
        {"value": "赛事甲", "occurrences": 2, "affected_games": 2},
        {"value": "赛事乙", "occurrences": 1, "affected_games": 1},
    ]
    inventory = _inventory(rows)
    inventory["scopes"]["all"]["values"]["event"] = rows[:1]
    try:
        build_event_group_manifest(inventory)
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("truncated event rows accepted")


def test_group_manifest_refuses_inflated_affected_game_count():
    inventory = _inventory([{"value": "赛事甲", "occurrences": 2, "affected_games": 3}])
    try:
        build_event_group_manifest(inventory)
    except ValueError as exc:
        assert "affected_games" in str(exc)
    else:
        raise AssertionError("inflated affected_games accepted")


def test_v3_group_manifest_uses_selected_raw_by_album_and_keeps_groups_pending():
    rows = [
        {"value": "GNUGo3.8", "occurrences": 3, "affected_games": 3},
        {"value": "1st Meijin", "occurrences": 1, "affected_games": 1},
    ]
    inventory = _selected_inventory(rows, [_selection(1, "28th Honinbo"), _selection(2, "29th Honinbo")])
    manifest = build_event_group_manifest(inventory, expected_artifact_sha256=_artifact_sha(inventory))
    assert manifest["inventory_format"] == 3
    assert manifest["inventory_sha256"] == inventory["sha256"]
    assert manifest["event_selection_sha256"] == inventory["event_selection"]["sha256"]
    assert manifest["group_count"] == 3
    grouped = {group["core"]: group for group in manifest["groups"]}
    assert grouped["Honinbo"]["occurrences"] == 2
    assert {member["raw_value"] for member in grouped["Honinbo"]["members"]} == {
        "28th Honinbo", "29th Honinbo",
    }
    assert grouped["GNUGo3.8"]["occurrences"] == 1
    assert grouped["Meijin"]["occurrences"] == 1
    assert sum(group["affected_games"] for group in manifest["groups"]) == 4
    assert all(group["status"] == "pending_review" for group in manifest["groups"])


def test_v3_group_manifest_rejects_tampered_or_unbound_selection_rows():
    rows = [{"value": "GNUGo3.8", "occurrences": 2, "affected_games": 2}]
    inventory = _selected_inventory(rows, [_selection(1, "28th Honinbo")])
    tampered = json.loads(json.dumps(inventory))
    tampered["event_selection"]["rows"][0][1] = "Other Event"
    with pytest.raises(ValueError, match="selection.*hash"):
        build_event_group_manifest(tampered, expected_artifact_sha256=_artifact_sha(tampered))

    for selected in ([_selection(3, "28th Honinbo")],
                     [_selection(1, "28th Honinbo"), _selection(1, "29th Honinbo")]):
        with pytest.raises(ValueError, match="selection"):
            invalid = _selected_inventory(rows, selected)
            build_event_group_manifest(invalid, expected_artifact_sha256=_artifact_sha(invalid))

    truncated = _selected_inventory(rows, [_selection(1, "28th Honinbo")])
    truncated["event_selection"]["rows"] = []
    with pytest.raises(ValueError, match="selection.*hash"):
        build_event_group_manifest(truncated, expected_artifact_sha256=_artifact_sha(truncated))


def test_v3_group_manifest_rejects_selected_row_for_wrong_original_event():
    rows = [{"value": "1st Meijin", "occurrences": 1, "affected_games": 1}]
    inventory = _selected_inventory(rows, [_selection(1, "28th Honinbo")])
    with pytest.raises(ValueError, match="selection.*original"):
        build_event_group_manifest(inventory, expected_artifact_sha256=_artifact_sha(inventory))


def test_v3_manifest_requires_an_external_full_inventory_digest():
    rows = [{"value": "GNUGo3.8", "occurrences": 1, "affected_games": 1}]
    inventory = _selected_inventory(rows, [_selection(1, "28th Honinbo")])
    pinned_sha = _artifact_sha(inventory)
    with pytest.raises(ValueError, match="artifact SHA"):
        build_event_group_manifest(inventory)
    assert build_event_group_manifest(inventory, expected_artifact_sha256=pinned_sha)["group_count"] == 1
    changed = json.loads(json.dumps(inventory))
    changed["event_selection"]["rows"][0][1] = "1st Meijin"
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
    _hash_row(digest, b"E", changed["event_selection"]["rows"][0])
    changed["event_selection"]["sha256"] = digest.hexdigest()
    with pytest.raises(ValueError, match="artifact SHA"):
        build_event_group_manifest(changed, expected_artifact_sha256=pinned_sha)


def test_v4_manifest_uses_selected_raw_only_with_external_full_artifact_pin():
    inventory = _selected_v4_inventory(
        [{"value": "GNUGo3.8", "occurrences": 1, "affected_games": 1}],
        [_selection(1, "28th Honinbo")],
    )
    pinned = _artifact_sha(inventory)
    with pytest.raises(ValueError, match="artifact SHA"):
        build_event_group_manifest(inventory)
    manifest = build_event_group_manifest(inventory, expected_artifact_sha256=pinned)
    assert manifest["inventory_format"] == 4
    assert manifest["inventory_artifact_sha256"] == pinned
    assert manifest["event_selection_sha256"] == inventory["event_selection"]["sha256"]
    assert manifest["groups"][0]["core"] == "Honinbo"
    changed = json.loads(json.dumps(inventory))
    changed["event_selection"]["rows"][0][8]["created_at"] = "2026-10-02T11:00:00"
    with pytest.raises(ValueError, match="artifact SHA"):
        build_event_group_manifest(changed, expected_artifact_sha256=pinned)


def test_cli_writes_compressed_manifest_for_complete_inventory(tmp_path):
    inventory = tmp_path / "inventory.json.gz"
    output = tmp_path / "groups.json.gz"
    rows = [{"value": "1934年日本大手合", "occurrences": 2, "affected_games": 2}]
    with gzip.open(inventory, "wt", encoding="utf-8") as stream:
        json.dump(_inventory(rows), stream)
    assert main(["--inventory", str(inventory), "--output", str(output)]) == 0
    with gzip.open(output, "rt", encoding="utf-8") as stream:
        result = json.load(stream)
    assert result == build_event_group_manifest(_inventory(rows))


def test_cli_v3_requires_independently_pinned_inventory_artifact(tmp_path):
    inventory_path = tmp_path / "inventory-v3.json.gz"
    output = tmp_path / "groups-v3.json.gz"
    inventory = _selected_inventory(
        [{"value": "GNUGo3.8", "occurrences": 1, "affected_games": 1}],
        [_selection(1, "28th Honinbo")],
    )
    with gzip.open(inventory_path, "wt", encoding="utf-8") as stream:
        json.dump(inventory, stream)
    args = ["--inventory", str(inventory_path), "--output", str(output)]
    with pytest.raises(ValueError, match="artifact SHA"):
        main(args)
    assert not output.exists()
    assert main([*args, "--expected-inventory-artifact-sha256", _artifact_sha(inventory)]) == 0
    with gzip.open(output, "rt", encoding="utf-8") as stream:
        manifest = json.load(stream)
    assert manifest["inventory_artifact_sha256"] == _artifact_sha(inventory)


def test_cli_runs_directly_from_repository_root():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/kifu_name_groups.py", "--help"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
