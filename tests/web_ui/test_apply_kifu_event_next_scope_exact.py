import copy
import json
from pathlib import Path

import pytest

from scripts.apply_kifu_event_next_scope_exact import (
    checked_applied_target_ids, checked_capture, checked_decision, compare_captures, digest,
)


DECISION = Path(__file__).resolve().parents[2] / "docs/resource/kifu-event-next-scope-independent-decision-astra-2026-10-04.json"


def test_decision_exact_partition_and_targets():
    decision = checked_decision(DECISION)
    approved, held = decision["approved"], decision["held"]
    assert (len(approved), len(held)) == (743, 453)
    assert len({row["id"] for row in approved + held}) == 1196
    assert {row["target_event_key"] for row in approved} == {
        "china_japan_regular_exchange", "japan_professional_best_ten"
    }
    assert all(row["before"]["event_edition_id"] is None for row in approved)


def test_decision_tamper_rejected(tmp_path):
    decision = json.loads(DECISION.read_text())
    decision["approved"][0]["target_event_key"] = "japan_professional_best_ten"
    changed = tmp_path / "decision.json"
    changed.write_text(json.dumps(decision))
    with pytest.raises(ValueError, match="decision digest"):
        checked_decision(changed)


def test_compare_requires_same_identity_but_allows_environment_fks_and_event_ids():
    common = {"decision_sha256": "x", "identity_sha256": "same", "approved_ids": [1], "held_ids": [2]}
    test = {**common, "environment": "TEST", "database": "katrain_db", "player_fk_sha256": "a", "target_ids": {"best": 44}}
    prod = {**common, "environment": "PROD", "database": "katrain_prod_20260725", "player_fk_sha256": "b", "target_ids": {"best": 45}}
    test["sha256"] = digest(test)
    prod["sha256"] = digest(prod)
    result = compare_captures(test, prod)
    assert result["identity_sha256"] == "same"
    changed = copy.deepcopy(test)
    changed["identity_sha256"] = "different"
    changed["sha256"] = digest({k: v for k, v in changed.items() if k != "sha256"})
    with pytest.raises(ValueError, match="identity"):
        compare_captures(changed, prod)


def test_prod_read_only_capture_matches_frozen_identity():
    path = DECISION.parent / "kifu-event-next-scope-PROD-capture-2026-10-04.json"
    capture = json.loads(path.read_text())
    checked_capture(capture, checked_decision(DECISION), "PROD")
    assert len(capture["rows"]) == 1196
    assert capture["target_ids"]["japan_professional_best_ten"] == 44
    assert capture["target_ids"]["china_japan_regular_exchange"] is None


@pytest.mark.parametrize("applied", [
    {"china_japan_regular_exchange": 44, "japan_professional_best_ten": 44},
    {"china_japan_regular_exchange": 75, "japan_professional_best_ten": 45},
    {"china_japan_regular_exchange": 0, "japan_professional_best_ten": 44},
    {"china_japan_regular_exchange": 75, "japan_professional_best_ten": 44, "extra": 76},
])
def test_verify_rejects_invalid_applied_target_ids(applied):
    with pytest.raises(ValueError, match="applied target IDs"):
        checked_applied_target_ids(applied, {"china_japan_regular_exchange": None,
                                             "japan_professional_best_ten": 44})


def test_verify_accepts_distinct_new_target_and_captured_best_ten_id():
    applied = {"china_japan_regular_exchange": 75, "japan_professional_best_ten": 44}
    assert checked_applied_target_ids(applied, {"china_japan_regular_exchange": None,
                                                "japan_professional_best_ten": 44}) == applied
