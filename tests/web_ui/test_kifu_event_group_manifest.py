"""Full inventory event groups remain exact, pending review manifests."""

import gzip
import json
import subprocess
import sys
from pathlib import Path

from katrain.web.kifu.name_structure import build_event_group_manifest
from scripts.kifu_name_groups import main


def _inventory(values):
    return {
        "inventory_format": 2,
        "sha256": "a" * 64,
        "scopes": {"all": {"values": {"event": values}}},
    }


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


def test_cli_runs_directly_from_repository_root():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/kifu_name_groups.py", "--help"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
