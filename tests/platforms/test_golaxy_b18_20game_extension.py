import dataclasses
import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

CALIBRATION = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

extension = importlib.import_module("golaxy_b18_20game_extension")


PARENT = (
    Path(__file__).parents[2]
    / "superpowers/tracks/golaxy-ai-ladder-parity/calibration/results"
    / "golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result(visits: int, color: str, result: str, *, conclusive: bool = True, result_id: str | None = None):
    row = {
        "type": "result",
        "visits": visits,
        "color": color,
        "outcome": result,
        "result": result,
        "conclusive": conclusive,
    }
    if result_id is not None:
        row["origin_result_id"] = result_id
    return row


def _conclusive_sequence(visits: int, count: int):
    return [
        _result(visits, "B" if index % 2 == 0 else "W", "our_win" if index % 3 else "our_loss")
        for index in range(count)
    ]


def _write_parent(tmp_path: Path, mutate) -> Path:
    rows = [json.loads(line) for line in PARENT.read_text(encoding="utf-8").splitlines()]
    mutate(rows)
    path = tmp_path / "parent.jsonl"
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def test_constants_freeze_approved_campaign():
    assert extension.MODEL == "b18"
    assert extension.MODEL_SHA256 == "9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d"
    assert extension.REFEREE_MODEL == "b28"
    assert extension.REFEREE_MODEL_SHA256 == "798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0"
    assert extension.GOLAXY_LEVEL == 36
    assert extension.GOLAXY_LEVEL_NAME == "星阵3星"
    assert extension.GOLAXY_API_LEVEL == 3300
    assert extension.CANDIDATE_VISITS == (32, 64)
    assert extension.TARGET_CONCLUSIVE == 20
    assert extension.PARENT_PATH == PARENT
    assert extension.PARENT_SHA256 == "9a5796b624924266efa6eb6937a4cb4833468bfa0270e5f115fc6d2714fc4082"


def test_campaign_value_objects_are_immutable():
    for cls in (extension.GameRequest, extension.CandidateSummary, extension.CampaignDecision):
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen


def test_load_frozen_carries_selects_only_approved_rows_in_parent_order():
    carries = extension.load_frozen_carries(PARENT, extension.PARENT_SHA256)

    assert len(carries) == 14
    assert [row["direct_parent_line"] for row in carries] == [2, 3, 4, 5, 6, 17, 18, 19, 20, 21, 22, 23, 24, 25]
    assert [row["visits"] for row in carries] == [64] * 5 + [32] * 4 + [64] * 5
    assert all(row["type"] == "carry_result" for row in carries)
    assert all(row["direct_parent_sha256"] == extension.PARENT_SHA256 for row in carries)
    assert all(
        row["origin_result_id"] == f"legacy:{extension.PARENT_SHA256}:{row['direct_parent_line']}" for row in carries
    )
    assert all(row["outcome"] == row["result"] for row in carries)
    assert all(row["conclusive"] is True for row in carries)
    assert carries[0]["source_outcome"] == json.loads(PARENT.read_text(encoding="utf-8").splitlines()[1])["outcome"]

    at_32 = extension.summarize_candidate(carries, 32)
    at_64 = extension.summarize_candidate(carries, 64)
    assert at_32 == extension.CandidateSummary(32, 4, 1, 3, 0, 2, 2)
    assert at_64 == extension.CandidateSummary(64, 10, 7, 3, 0, 5, 5)


def test_load_frozen_carries_rejects_changed_parent_bytes(tmp_path):
    changed = tmp_path / "changed.jsonl"
    changed.write_bytes(PARENT.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="SHA256"):
        extension.load_frozen_carries(changed, extension.PARENT_SHA256)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda rows: rows[0].__setitem__("model", "b28"), "model"),
        (lambda rows: rows[1].__setitem__("level", 35), "level"),
        (lambda rows: rows[1].__setitem__("rung", 35), "rung"),
        (lambda rows: rows[1].__setitem__("level_name", "星阵2星"), "level_name"),
        (lambda rows: rows[1].__setitem__("api_level", 3200), "api_level"),
        (lambda rows: rows[1].__setitem__("visits", 32), "visits"),
        (lambda rows: rows[1]["outcome"].__setitem__("result", "inconclusive_unsettled"), "outcome"),
        (lambda rows: rows[1]["outcome"].__setitem__("conclusive", False), "conclusive"),
        (lambda rows: rows.__setitem__(2, dict(rows[1])), "duplicate"),
    ],
)
def test_load_frozen_carries_rejects_invalid_selected_source_rows(tmp_path, mutate, message):
    changed = _write_parent(tmp_path, mutate)

    with pytest.raises(ValueError, match=message):
        extension.load_frozen_carries(changed, _sha256(changed))


def test_load_frozen_carries_rejects_wrong_inherited_color_balance(tmp_path):
    changed = _write_parent(tmp_path, lambda rows: rows[16].__setitem__("color", "W"))

    with pytest.raises(ValueError, match="color"):
        extension.load_frozen_carries(changed, _sha256(changed))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("level", 36.0),
        ("level", True),
        ("rung", 36.0),
        ("rung", True),
        ("api_level", 3300.0),
        ("api_level", True),
        ("visits", 64.0),
        ("visits", True),
    ],
)
def test_load_frozen_carries_rejects_non_plain_integer_protocol_numerics(tmp_path, field, value):
    changed = _write_parent(tmp_path, lambda rows: rows[1].__setitem__(field, value))

    with pytest.raises(ValueError, match=field):
        extension.load_frozen_carries(changed, _sha256(changed))


def test_scheduler_finishes_32_before_replenishing_64_and_alternates_conclusive_colors():
    inherited = extension.load_frozen_carries(PARENT, extension.PARENT_SHA256)
    assert extension.next_action(inherited) == extension.GameRequest(32, "B")

    evidence = list(inherited) + _conclusive_sequence(32, 16)
    assert extension.next_action(evidence) == extension.GameRequest(64, "B")

    evidence += _conclusive_sequence(64, 10)
    assert extension.next_action(evidence) == extension.CampaignDecision(
        "completed",
        (
            extension.CandidateSummary(32, 20, 11, 9, 0, 10, 10),
            extension.CandidateSummary(64, 20, 13, 7, 0, 10, 10),
        ),
    )


def test_scheduler_rejects_live_64_result_before_32_is_complete():
    inherited = extension.load_frozen_carries(PARENT, extension.PARENT_SHA256)

    with pytest.raises(ValueError, match="active candidate"):
        extension.next_action([*inherited, _result(64, "B", "our_win")])


def test_scheduler_rejects_reordered_or_spoofed_carry_rows():
    inherited = list(extension.load_frozen_carries(PARENT, extension.PARENT_SHA256))
    reordered = [inherited[1], inherited[0], *inherited[2:]]
    with pytest.raises(ValueError, match="frozen carry prefix"):
        extension.next_action(reordered)

    spoofed = _result(64, "B", "our_win")
    spoofed["type"] = "carry_result"
    with pytest.raises(ValueError, match="frozen carry prefix"):
        extension.next_action([*inherited, spoofed])


def test_scheduler_rejects_carry_after_live_evidence():
    inherited = list(extension.load_frozen_carries(PARENT, extension.PARENT_SHA256))
    live = _result(32, "B", "our_win")

    with pytest.raises(ValueError, match="carry_result after live evidence"):
        extension.next_action([*inherited, live, inherited[0]])


def test_scheduler_rejects_spoofed_carry_provenance_or_preserved_outcome():
    inherited = list(extension.load_frozen_carries(PARENT, extension.PARENT_SHA256))
    for field, value in (
        ("direct_parent_sha256", "0" * 64),
        ("direct_parent_line", 99),
        ("origin_result_id", "legacy:spoofed:2"),
        ("source_outcome", {"result": "our_loss"}),
    ):
        spoofed = [dict(row) for row in inherited]
        spoofed[0][field] = value
        with pytest.raises(ValueError, match="frozen carry prefix"):
            extension.next_action(spoofed)


@pytest.mark.parametrize(
    "outcome",
    ["inconclusive_score", "inconclusive_unsettled", "inconclusive_unstable"],
)
def test_inconclusive_is_replenishable_and_repeats_color(outcome):
    evidence = _conclusive_sequence(32, 4)
    evidence.append(_result(32, "B", outcome, conclusive=False))

    assert extension.summarize_candidate(evidence, 32) == extension.CandidateSummary(32, 4, 2, 2, 1, 2, 2)
    assert extension.next_action(evidence) == extension.GameRequest(32, "B")


@pytest.mark.parametrize("visits", [0, 16, 128])
def test_scheduler_rejects_unknown_candidate(visits):
    with pytest.raises(ValueError, match="visits"):
        extension.next_action([_result(visits, "B", "our_win")])


@pytest.mark.parametrize("visits", [32.0, True])
def test_scheduler_rejects_non_plain_integer_visits(visits):
    with pytest.raises(ValueError, match="visits"):
        extension.next_action([_result(visits, "B", "our_win")])


@pytest.mark.parametrize("visits", [32.0, True])
def test_summarize_candidate_rejects_non_plain_integer_visits(visits):
    with pytest.raises(ValueError, match="visits"):
        extension.summarize_candidate([], visits)


def test_scheduler_rejects_more_than_target_conclusive():
    with pytest.raises(ValueError, match="more than 20"):
        extension.next_action(_conclusive_sequence(32, 21))


def test_scheduler_rejects_duplicate_or_empty_origin_result_ids():
    duplicate = [
        _result(32, "B", "our_win", result_id="same"),
        _result(32, "W", "our_loss", result_id="same"),
    ]
    with pytest.raises(ValueError, match="duplicate"):
        extension.next_action(duplicate)

    with pytest.raises(ValueError, match="origin_result_id"):
        extension.next_action([_result(32, "B", "our_win", result_id="")])


@pytest.mark.parametrize(
    "row",
    [
        _result(32, "B", "unknown"),
        _result(32, "B", "our_win", conclusive=False),
        _result(32, "B", "inconclusive_score", conclusive=True),
        _result(32, "W", "our_win"),
    ],
)
def test_scheduler_rejects_invalid_outcome_or_color_sequence(row):
    with pytest.raises(ValueError):
        extension.next_action([row])


HEALTH = {"status": "ok", "models": {"b18": {"running": True}, "b28": {"running": True}}}


def _outcome(color="B", result="our_win", *, score=3.5, conclusive=True, our_win=True):
    return SimpleNamespace(
        our_color=color,
        result=result,
        our_win=our_win,
        num_moves=123,
        black_score=score,
        conclusive=conclusive,
        end_reason="move_cap",
    )


def test_v6_ledger_round_trip_uses_exact_schemas_and_append_only_rows(tmp_path):
    path = tmp_path / "campaign-v6.jsonl"
    loaded = extension.initialize_v6_campaign(path, "campaign-v6", HEALTH)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert set(rows[0]) == {
        "type",
        "protocol",
        "campaign_id",
        "created_at",
        "source_v5_path",
        "source_v5_sha256",
        "target_valid",
        "candidate_order",
        "game_contract",
        "complete_health_response",
    }
    assert rows[0]["protocol"] == "golaxy-b18-three-star-20game-extension-v6"
    assert rows[0]["complete_health_response"] == HEALTH
    assert rows[1:] == list(extension.load_frozen_carries(PARENT, extension.PARENT_SHA256))
    assert loaded.action == extension.GameRequest(32, "B")

    extension.append_reservation(path, 1, loaded.action)
    reservation = json.loads(path.read_text().splitlines()[-1])
    assert set(reservation) == {"type", "attempt_id", "request_id", "visits", "color", "target_valid", "created_at"}
    assert reservation["request_id"] == "campaign-v6:1"
    extension.append_result(path, 1, _outcome(), 12.25)
    result = json.loads(path.read_text().splitlines()[-1])
    assert set(result) == {
        "type",
        "attempt_id",
        "request_id",
        "visits",
        "color",
        "target_valid",
        "origin_result_id",
        "our_color",
        "result",
        "our_win",
        "num_moves",
        "black_score",
        "conclusive",
        "end_reason",
        "elapsed_seconds",
        "completed_at",
    }
    assert result["origin_result_id"] == "campaign-v6:1"
    assert extension.load_campaign(path).action == extension.GameRequest(32, "W")


def test_init_is_exclusive_health_is_serializable_and_mutations_require_open_reservation(tmp_path):
    path = tmp_path / "campaign.jsonl"
    extension.initialize_v6_campaign(path, "campaign", HEALTH)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        extension.initialize_v6_campaign(path, "other", HEALTH)
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="serializable"):
        extension.initialize_v6_campaign(tmp_path / "bad.jsonl", "bad", {"bad": object()})
    assert not (tmp_path / "bad.jsonl").exists()
    with pytest.raises(ValueError, match="open reservation"):
        extension.append_result(path, 1, _outcome(), 1.0)


def test_unmatched_and_stopped_ledgers_are_inspectable_but_not_resumable(tmp_path):
    unmatched = tmp_path / "unmatched.jsonl"
    extension.initialize_v6_campaign(unmatched, "unmatched", HEALTH)
    extension.append_reservation(unmatched, 1, extension.load_campaign(unmatched).action)
    with pytest.raises(ValueError, match="open reservation"):
        extension.load_campaign(unmatched)
    assert extension.load_campaign(unmatched, summary=True).open_attempt == 1

    stopped = tmp_path / "stopped.jsonl"
    extension.initialize_v6_campaign(stopped, "stopped", HEALTH)
    extension.append_reservation(stopped, 1, extension.load_campaign(stopped).action)
    extension.append_stop(stopped, 1, "engine unavailable")
    with pytest.raises(ValueError, match="stopped"):
        extension.load_campaign(stopped)
    assert extension.load_campaign(stopped, summary=True).stopped is True
    with pytest.raises(ValueError, match="stopped"):
        extension.append_result(stopped, 1, _outcome(), 1.0)


@pytest.mark.parametrize("parent_state", ["stopped", "unmatched"])
def test_v7_continuation_requires_exact_hash_authorization_and_health(tmp_path, parent_state):
    parent = tmp_path / "parent.jsonl"
    extension.initialize_v6_campaign(parent, "parent", HEALTH)
    extension.append_reservation(parent, 1, extension.load_campaign(parent).action)
    if parent_state == "stopped":
        extension.append_stop(parent, 1, "terminal engine failure")
    parent_sha = _sha256(parent)
    child = tmp_path / "child.jsonl"
    loaded = extension.initialize_v7_continuation(
        child,
        "child",
        HEALTH,
        parent_path=parent,
        parent_sha256=parent_sha,
        authorization="explicit_user_continue",
    )
    header = loaded.header
    assert header["protocol"] == "golaxy-b18-three-star-20game-extension-v7"
    assert header["parent_path"] == str(parent.resolve())
    assert header["parent_sha256"] == parent_sha
    assert header["authorization"] == "explicit_user_continue"
    if parent_state == "unmatched":
        assert header["excluded_uncertain_reservation"]["direct_parent_line"] == 16
        assert header["excluded_uncertain_reservation"]["reservation"]["request_id"] == "parent:1"
    else:
        assert "excluded_uncertain_reservation" not in header


def test_v7_rejections_do_not_create_output(tmp_path):
    parent = tmp_path / "parent.jsonl"
    extension.initialize_v6_campaign(parent, "parent", HEALTH)
    extension.append_reservation(parent, 1, extension.load_campaign(parent).action)
    sha = _sha256(parent)
    cases = [
        ("bad-auth", HEALTH, sha, "no"),
        ("bad-sha", HEALTH, "0" * 64, "explicit_user_continue"),
        ("health-drift", {"status": "drift"}, sha, "explicit_user_continue"),
    ]
    for name, health, parent_sha, auth in cases:
        output = tmp_path / f"{name}.jsonl"
        with pytest.raises(ValueError):
            extension.initialize_v7_continuation(
                output, name, health, parent_path=parent, parent_sha256=parent_sha, authorization=auth
            )
        assert not output.exists()


def test_result_acceptance_is_strict_and_preserves_all_game_outcome_fields(tmp_path):
    for index, bad in enumerate(
        (
            _outcome(result="inconclusive_terminal", conclusive=False, our_win=False, score=None),
            _outcome(result="our_win", conclusive=False),
            _outcome(result="inconclusive_score", conclusive=False, our_win=False, score="3.5"),
        )
    ):
        path = tmp_path / f"bad-{index}.jsonl"
        extension.initialize_v6_campaign(path, f"bad-{index}", HEALTH)
        extension.append_reservation(path, 1, extension.load_campaign(path).action)
        before = path.read_bytes()
        with pytest.raises(ValueError):
            extension.append_result(path, 1, bad, 1.0)
        assert path.read_bytes() == before


def test_v7_replay_rederives_uncertainty_and_health_from_sha_validated_parent(tmp_path):
    parent = tmp_path / "parent.jsonl"
    extension.initialize_v6_campaign(parent, "parent", HEALTH)
    extension.append_reservation(parent, 1, extension.load_campaign(parent).action)
    child = tmp_path / "child.jsonl"
    extension.initialize_v7_continuation(
        child,
        "child",
        HEALTH,
        parent_path=parent,
        parent_sha256=_sha256(parent),
        authorization="explicit_user_continue",
    )
    original = child.read_text()
    rows = [json.loads(line) for line in original.splitlines()]
    rows[0]["excluded_uncertain_reservation"]["reservation"]["visits"] = 64
    child.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="uncertain"):
        extension.load_campaign(child, summary=True)

    rows = [json.loads(line) for line in original.splitlines()]
    rows[0]["complete_health_response"] = {"status": "drift"}
    child.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="health"):
        extension.load_campaign(child, summary=True)


def test_v7_carries_only_closed_evidence_and_summary_counts_lineage_attempts(tmp_path):
    parent = tmp_path / "parent.jsonl"
    extension.initialize_v6_campaign(parent, "parent", HEALTH)
    extension.append_reservation(parent, 1, extension.load_campaign(parent).action)
    extension.append_result(parent, 1, _outcome(), 1.0)
    extension.append_reservation(parent, 2, extension.load_campaign(parent).action)
    extension.append_stop(parent, 2, "terminal engine failure")

    child = tmp_path / "child.jsonl"
    extension.initialize_v7_continuation(
        child,
        "child",
        HEALTH,
        parent_path=parent,
        parent_sha256=_sha256(parent),
        authorization="explicit_user_continue",
    )
    rows = [json.loads(line) for line in child.read_text().splitlines()]
    assert all(row["type"] == "carry_result" for row in rows[1:])
    carried = rows[-1]
    assert carried["origin_result_id"] == "parent:1"
    assert carried["direct_parent_line"] == 17
    assert all(row.get("request_id") != "parent:2" for row in rows[1:])

    extension.append_reservation(child, 1, extension.load_campaign(child).action)
    extension.append_result(child, 1, _outcome(color="W", result="our_loss", our_win=False), 2.0)
    summary = extension.campaign_summary(child)
    assert set(summary) == {
        "path",
        "sha256",
        "protocol",
        "stopped",
        "open_attempt",
        "completion_status",
        "next_action",
        "candidates",
        "total_attempts",
        "inconclusive",
        "warning",
    }
    assert summary["total_attempts"] == 3
    assert summary["candidates"]["32"]["inherited"] == {"wins": 1, "losses": 3, "black": 2, "white": 2}
    assert summary["candidates"]["32"]["new"] == {"wins": 1, "losses": 1, "black": 1, "white": 1}


def test_v7_replay_rejects_campaign_id_reused_from_parent(tmp_path):
    parent = tmp_path / "parent.jsonl"
    extension.initialize_v6_campaign(parent, "parent", HEALTH)
    extension.append_reservation(parent, 1, extension.load_campaign(parent).action)
    extension.append_stop(parent, 1, "terminal engine failure")
    child = tmp_path / "child.jsonl"
    extension.initialize_v7_continuation(
        child,
        "child",
        HEALTH,
        parent_path=parent,
        parent_sha256=_sha256(parent),
        authorization="explicit_user_continue",
    )
    rows = [json.loads(line) for line in child.read_text().splitlines()]
    rows[0]["campaign_id"] = "parent"
    child.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(ValueError, match="campaign_id"):
        extension.load_campaign(child, summary=True)


def test_stopped_parent_v7_header_forbids_even_null_uncertainty_descriptor(tmp_path):
    parent = tmp_path / "parent.jsonl"
    extension.initialize_v6_campaign(parent, "parent", HEALTH)
    extension.append_reservation(parent, 1, extension.load_campaign(parent).action)
    extension.append_stop(parent, 1, "terminal engine failure")
    child = tmp_path / "child.jsonl"
    extension.initialize_v7_continuation(
        child,
        "child",
        HEALTH,
        parent_path=parent,
        parent_sha256=_sha256(parent),
        authorization="explicit_user_continue",
    )
    rows = [json.loads(line) for line in child.read_text().splitlines()]
    rows[0]["excluded_uncertain_reservation"] = None
    child.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(ValueError, match="uncertain"):
        extension.load_campaign(child, summary=True)
