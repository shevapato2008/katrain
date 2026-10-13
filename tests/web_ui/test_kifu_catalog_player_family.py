import gzip
import hashlib
import json
from pathlib import Path

import pytest

from katrain.web.kifu.catalog_player_family import run_family_plan


ROOT = Path(__file__).resolve().parents[2]
RESOURCE = ROOT / "docs/resource"


def _plan(environment):
    raw = (RESOURCE / f"kifu-player-family-{environment}-plan-2026-10-04.json.gz").read_bytes()
    return hashlib.sha256(raw).hexdigest(), json.loads(gzip.decompress(raw))


def test_two_environment_plans_freeze_exact_reviewed_slots():
    test_sha, test = _plan("test")
    prod_sha, prod = _plan("prod")
    assert test_sha == "fd47872f33b487b14416e16928a23db7559352af4ab402b9442d46aca979dcc3"
    assert prod_sha == "4c5fd9f2691c77c7ba9a1973c41e3f152d96a656c6bbd7e5bddcfd54bb40497a"
    assert test_sha != prod_sha
    for plan in (test, prod):
        assert plan["counts"] == {
            "games": 173025, "families": 8, "new_fk_slots": 504, "repoint_fk_slots": 20,
            "canonical_corrections": 2, "new_player_ids": 0, "metadata_repoints": 5, "held_slots": 8,
        }
        assert all(row[-2] is None for row in plan["new_slots"])
        assert all(row[-2] is not None and row[-2] != row[-1] for row in plan["old_slots"])
        assert len({(row[0], row[1]) for row in plan["new_slots"] + plan["old_slots"]}) == 524
        assert (135904, "black", "岩田达明七段") in {tuple(row[:3]) for row in plan["new_slots"]}
        assert {(row[0], row[1]) for row in plan["held_slots"]}.isdisjoint(
            {(row[0], row[1]) for row in plan["new_slots"] + plan["old_slots"]}
        )
        assert len(plan["protected_slots"]) == 9
        assert {row[1] for row in plan["old_metadata_rows"]} == {
            "林海蜂", "岩本熏", "岩本薫", "加纳嘉徳", "藤泽朋斎",
        }


def test_apply_requires_separate_exact_sha_approval():
    _, plan = _plan("test")
    with pytest.raises(ValueError, match="separate exact plan SHA approval"):
        run_family_plan({}, {}, "", "test", plan, None, apply=True,
                        plan_sha256="the-captured-sha", approved_plan_sha256=None)
