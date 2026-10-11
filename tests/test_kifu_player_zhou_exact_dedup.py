"""Focused safety boundaries for the reviewed Zhou Heyang B/C directory repair."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[1] / "scripts/kifu_player_zhou_exact_dedup.py"
    assert path.exists(), "the exact B/C repair implementation is missing"
    spec = importlib.util.spec_from_file_location("zhou_exact_dedup", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def raw_row():
    return {
        "id": 10145,
        "raw_value": "周鹤样",
        "review_status": "pending",
        "parsed_data": {"name": "周鹤样", "exceptions": [], "slot_count": 1},
        "review_metadata": {
            "player_id": 9988,
            "kind": "provisional_person_link",
            "inventory_sha256": "frozen-inventory",
            "extra": {"audit": ["keep", 7]},
        },
    }


def test_metadata_repoint_preserves_entire_raw_row_and_pending_status():
    m = module()
    before = raw_row()
    untouched = copy.deepcopy(before)
    after = m.repoint_raw(before, 9988, 1048)
    expected = copy.deepcopy(before)
    expected["review_metadata"]["player_id"] = 1048
    assert after == expected
    assert before == untouched


@pytest.mark.parametrize("field,value", [("review_status", "approved"), ("review_metadata", {"player_id": 9989})])
def test_repoint_rejects_changed_status_or_old_pointer(field, value):
    m = module()
    row = raw_row()
    row[field] = value
    with pytest.raises(ValueError, match="raw preimage"):
        m.repoint_raw(row, 9988, 1048)


@pytest.mark.parametrize("reference", ["kifu_albums.white_player_id", "new_table.player_id", "raw_metadata.player_id"])
def test_deletion_refuses_any_residual_reference(reference):
    m = module()
    with pytest.raises(ValueError, match="remaining references"):
        m.require_no_references({reference: 1})
    m.require_no_references({reference: 0})


def test_cas_compares_the_complete_json_row():
    m = module()
    before = raw_row()
    current = copy.deepcopy(before)
    current["review_metadata"]["extra"]["audit"].append("concurrent edit")
    with pytest.raises(ValueError, match="preimage changed"):
        m.require_equal_preimage(before, current)
    current = copy.deepcopy(before)
    current["parsed_data"]["slot_count"] = 2
    with pytest.raises(ValueError, match="preimage changed"):
        m.require_equal_preimage(before, current)


def test_environment_specific_approved_scope_has_no_global_typo_alias():
    m = module()
    test = m.scope("TEST")
    prod = m.scope("PROD")
    assert test["survivor"] == 1048
    assert test["retire"] == [1028, 9988, 9989]
    assert prod["survivor"] == 4193
    assert prod["retire"] == [4194]
    assert [(s["album_id"], s["side"], s["old_fk"], s["new_fk"]) for s in test["slots"]] == [
        (87152, "white", 9988, 1048), (148135, "black", 9989, 1048)
    ]
    assert [(s["album_id"], s["side"], s["old_fk"], s["new_fk"]) for s in prod["slots"]] == [
        (87152, "white", 4193, 4193), (148135, "black", 4194, 4193)
    ]
    assert test["aliases_to_create"] == prod["aliases_to_create"] == []


def test_apply_requires_reviewed_plan_digest_before_database_access(monkeypatch):
    m = module()
    monkeypatch.delenv("KATRAIN_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="approved plan"):
        m.execute({"mode": "apply", "environment": "TEST", "plan": {"sha256": "not-approved"}})


def test_unknown_mode_rejected_before_database_access(monkeypatch):
    m = module()
    monkeypatch.delenv("KATRAIN_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="unsupported mode"):
        m.execute({"mode": "automatic", "environment": "TEST"})


def captured_test_plan():
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "docs/resource/kifu-player-zhou-dedup-TEST-plan-2026-10-04.json").read_text())


def test_frozen_sgf_identity_check_rejects_content_change():
    m = module()
    state = captured_test_plan()["preimage"]
    state["albums"][0]["sgf_content"] += "\n"
    with pytest.raises(ValueError, match="album/SGF differs"):
        m.validate_preimage(state, m.scope("TEST"))


def test_self_opponent_and_extra_reference_are_not_absorbed_by_merge():
    m = module()
    state = captured_test_plan()["preimage"]
    state["albums"][0]["black_player_id"] = 1048
    with pytest.raises(ValueError, match="same-person opponent"):
        m.validate_preimage(state, m.scope("TEST"))
    state = captured_test_plan()["preimage"]
    extra = copy.deepcopy(state["albums"][0])
    extra.update(id=900000, white_player_id=1028)
    state["albums"].append(extra)
    with pytest.raises(ValueError, match="extra album reference"):
        m.validate_preimage(state, m.scope("TEST"))


def test_postimage_preserves_survivor_names_raw_status_and_sgf():
    m = module()
    before = captured_test_plan()["preimage"]
    after = m.expected_postimage(before, m.scope("TEST"))
    assert after["names"] == [r for r in before["names"] if r["player_id"] == 1048]
    assert after["aliases"] == before["aliases"] == []
    for old, new in zip(before["albums"], after["albums"]):
        only_fk_changed = copy.deepcopy(new)
        for key in ("black_player_id", "white_player_id"):
            only_fk_changed[key] = old[key]
        assert only_fk_changed == old
    for old, new in zip(before["raw_rows"], after["raw_rows"]):
        if old["id"] not in {10145, 10148}:
            assert new == old
        else:
            expected = copy.deepcopy(old)
            expected["review_metadata"]["player_id"] = 1048
            assert new == expected


def test_plan_tamper_and_cross_environment_reuse_are_rejected():
    m = module()
    plan = captured_test_plan()
    plan["preimage"]["raw_rows"][0]["parsed_data"]["slot_count"] = 999
    with pytest.raises(ValueError, match="frozen plan"):
        m.validate_plan(plan, "TEST")
    with pytest.raises(ValueError):
        m.validate_plan(captured_test_plan(), "PROD")
