import asyncio
import dataclasses
import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

from katrain.core.ladder_calibration import GameOutcome

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


@pytest.mark.parametrize(
    ("result", "black_score"),
    [
        ("inconclusive_score", None),
        ("inconclusive_unsettled", 1.25),
        ("inconclusive_unstable", -0.5),
    ],
)
def test_all_accepted_real_game_outcome_inconclusives_append_and_replay(tmp_path, result, black_score):
    path = tmp_path / f"{result}.jsonl"
    extension.initialize_v6_campaign(path, result, HEALTH)
    extension.append_reservation(path, 1, extension.load_campaign(path).action)
    outcome = GameOutcome("B", result, False, 400, black_score, False, "move_cap")

    extension.append_result(path, 1, outcome, 3.0)

    loaded = extension.load_campaign(path)
    assert loaded.action == extension.GameRequest(32, "B")
    assert loaded.evidence[-1]["result"] == result
    assert loaded.evidence[-1]["black_score"] == black_score


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_replay_rejects_nonstandard_json_constants_in_tampered_elapsed(tmp_path, constant):
    path = tmp_path / f"tampered-{constant}.jsonl"
    extension.initialize_v6_campaign(path, f"tampered-{constant}", HEALTH)
    extension.append_reservation(path, 1, extension.load_campaign(path).action)
    reservation = json.loads(path.read_text().splitlines()[-1])
    row = {
        "type": "result",
        "attempt_id": 1,
        "request_id": reservation["request_id"],
        "visits": 32,
        "color": "B",
        "target_valid": 20,
        "origin_result_id": f"tampered-{constant}:1",
        "our_color": "B",
        "result": "our_win",
        "our_win": True,
        "num_moves": 1,
        "black_score": 1.0,
        "conclusive": True,
        "end_reason": "move_cap",
        "elapsed_seconds": 1.0,
        "completed_at": "now",
    }
    serialized = json.dumps(row, separators=(",", ":")).replace(
        '"elapsed_seconds":1.0', f'"elapsed_seconds":{constant}'
    )
    with path.open("a") as handle:
        handle.write(serialized + "\n")

    with pytest.raises(ValueError, match="non-standard JSON constant"):
        extension.load_campaign(path, summary=True)


def _runner():
    return importlib.import_module("run_golaxy_b18_20game_extension")


def _live_health():
    health = {
        "status": "ok",
        "capability_schema": 1,
        "katago_version": "KataGo v1.16.3",
        "default_model": "b18",
        "models": {},
    }
    for alias, sha in (("b18", extension.MODEL_SHA256), ("b28", extension.REFEREE_MODEL_SHA256)):
        health["models"][alias] = {
            "running": True,
            "model_path": f"/models/{alias}.bin.gz",
            "model_sha256": sha,
            "model_sha256_verified": True,
            "has_human_model": False,
            "human_model_path": None,
            "human_model_sha256": None,
            "human_model_sha256_verified": False,
        }
    return health


def _wrapper(alias):
    health = _live_health()
    model = health["models"][alias]
    return {
        "selected_model": alias,
        "model_path": model["model_path"],
        "model_sha256": model["model_sha256"],
        "human_model_path": None,
        "human_model_sha256": None,
        "katago_version": health["katago_version"],
    }


def _referee_analysis(visits, *, score=3.5, ownership=None):
    return {
        "rootInfo": {"visits": visits, "scoreLead": score},
        "moveInfos": [{"move": "D4", "visits": visits, "order": 0}],
        "ownership": [1.0] * 361 if ownership is None else ownership,
        "_wrapper": _wrapper("b28"),
    }


class _AnalysisClient:
    def __init__(self, analyses):
        self.analyses = list(analyses)
        self.queries = []

    async def post(self, url, *, json, timeout):
        self.queries.append(json)
        return httpx.Response(200, json=self.analyses.pop(0), request=httpx.Request("POST", url))


def test_live_player_and_query_are_exact_pure_b18():
    runner = _runner()
    player = runner.make_player(32)
    query = runner.build_player_query([0], 32)
    assert (player.net, player.mechanism, player.max_visits, player.human_sl_profile) == ("b18", "net_search", 32, None)
    assert player.human_sl_params == {}
    assert query == {
        "rules": "chinese",
        "komi": 7.5,
        "boardXSize": 19,
        "boardYSize": 19,
        "moves": [["B", "A19"]],
        "analyzeTurns": [1],
        "maxVisits": 32,
        "includePolicy": True,
        "includeOwnership": False,
        "overrideSettings": {"reportAnalysisWinratesAs": "BLACK", "wideRootNoise": 0.04, "model": "b18"},
    }


def test_complete_health_is_canonical_and_rejects_either_identity_drift():
    runner = _runner()
    health = _live_health()
    canonical, digest = runner.validate_complete_health(health)
    assert json.loads(canonical) == health
    assert hashlib.sha256(canonical.encode()).hexdigest() == digest
    for alias in ("b18", "b28"):
        changed = json.loads(json.dumps(health))
        changed["models"][alias]["model_sha256"] = "0" * 64
        with pytest.raises(ValueError, match=alias):
            runner.validate_complete_health(changed)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda health: health.update(katago_version="different"),
        lambda health: health["models"]["b18"].update(model_path="/different/b18.bin.gz"),
        lambda health: health.update(default_model="missing"),
        lambda health: health["models"]["b18"].update(running=False),
        lambda health: health["models"]["b28"].update(running=False),
    ],
)
def test_complete_health_rejects_version_path_default_and_running_drift(mutate):
    runner = _runner()
    baseline = _live_health()
    canonical, _digest = runner.validate_complete_health(baseline)
    changed = json.loads(json.dumps(baseline))
    mutate(changed)
    if changed["katago_version"] == "different" or changed["models"]["b18"]["model_path"].startswith("/different"):
        # Each value can be valid in isolation, but canonical live/header comparison must detect it.
        assert runner.validate_complete_health(changed)[0] != canonical
    else:
        with pytest.raises(ValueError):
            runner.validate_complete_health(changed)


def test_analysis_validates_attestation_and_never_falls_back():
    runner = _runner()
    analysis = {
        "rootInfo": {"visits": 32},
        "moveInfos": [{"move": "D4", "visits": 32, "order": 0}],
        "policy": [0.0] * 362,
        "_wrapper": _wrapper("b18"),
    }
    assert runner.select_player_move(analysis, 32, _live_health()) == 288
    analysis["_wrapper"]["model_sha256"] = "bad"
    with pytest.raises(Exception, match="attestation"):
        runner.select_player_move(analysis, 32, _live_health())


@pytest.mark.parametrize("requested", [32, 64])
@pytest.mark.parametrize("reported_kind", ["missing", "bool", "float", "zero", "negative", "plus8"])
def test_b18_probe_and_live_selection_reject_invalid_reported_visits(requested, reported_kind):
    runner = _runner()
    reported = {
        "missing": None,
        "bool": True,
        "float": float(requested),
        "zero": 0,
        "negative": -1,
        "plus8": requested + 8,
    }[reported_kind]
    analysis = {
        "rootInfo": {"visits": reported},
        "moveInfos": [{"move": "D4", "visits": requested, "order": 0}],
        "policy": [0.0] * 362,
        "_wrapper": _wrapper("b18"),
    }
    with pytest.raises(ValueError, match="visits"):
        runner.select_player_move(analysis, requested, _live_health())


@pytest.mark.parametrize(
    ("requested", "reported"),
    [(requested, requested + extra) for requested in (32, 64) for extra in range(1, 8)],
)
def test_b18_accepts_katago_thread_visit_overshoot_through_plus_seven(requested, reported):
    runner = _runner()
    analysis = {
        "rootInfo": {"visits": reported},
        "moveInfos": [{"move": "D4", "visits": reported, "order": 0}],
        "policy": [0.0] * 362,
        "_wrapper": _wrapper("b18"),
    }
    assert runner.select_player_move(analysis, requested, _live_health()) == 288


@pytest.mark.parametrize("visits", [32, 64])
def test_b18_probe_and_live_http_path_enforces_reported_visit_upper_bound(visits):
    runner = _runner()

    class Client:
        def __init__(self, reported):
            self.reported = reported
            self.queries = []

        async def post(self, url, *, json, timeout):
            self.queries.append((url, json, timeout))
            analysis = {
                "rootInfo": {"visits": self.reported},
                "moveInfos": [{"move": "D4", "visits": visits, "order": 0}],
                "policy": [0.0] * 362,
                "_wrapper": _wrapper("b18"),
            }
            return httpx.Response(200, json=analysis, request=httpx.Request("POST", url))

    valid = Client(visits)
    assert asyncio.run(runner.analyze_player_move(valid, [], visits, _live_health())) == 288
    assert valid.queries[0][1]["maxVisits"] == visits
    invalid = Client(visits + 8)
    with pytest.raises(ValueError, match="no greater"):
        asyncio.run(runner._probe_player(invalid, visits, _live_health()))


@pytest.mark.parametrize(("requested", "reported"), [(32, 35), (64, 71)])
def test_b18_http_query_budget_stays_exact_while_observed_visits_overshoot(requested, reported):
    runner = _runner()

    class Client:
        def __init__(self):
            self.query = None

        async def post(self, url, *, json, timeout):
            self.query = json
            analysis = {
                "rootInfo": {"visits": reported},
                "moveInfos": [{"move": "D4", "visits": reported, "order": 0}],
                "policy": [0.0] * 362,
                "_wrapper": _wrapper("b18"),
            }
            return httpx.Response(200, json=analysis, request=httpx.Request("POST", url))

    client = Client()
    assert asyncio.run(runner.analyze_player_move(client, [], requested, _live_health())) == 288
    assert client.query["maxVisits"] == requested


@pytest.mark.parametrize("visits", [200, 800])
def test_shared_strict_referee_probe_uses_exact_live_query_and_response(visits):
    runner = _runner()
    client = _AnalysisClient([_referee_analysis(visits)])
    probe = asyncio.run(runner._probe_referee(client, visits, _live_health()))
    assert probe["requested_visits"] == probe["reported_visits"] == visits
    assert probe["score"] == 3.5 and probe["settled"] is True
    assert client.queries == [
        {
            "rules": "chinese",
            "komi": 7.5,
            "boardXSize": 19,
            "boardYSize": 19,
            "moves": [],
            "analyzeTurns": [0],
            "maxVisits": visits,
            "includeOwnership": True,
            "includePolicy": False,
            "overrideSettings": {"reportAnalysisWinratesAs": "BLACK", "model": "b28"},
        }
    ]


@pytest.mark.parametrize("requested", [200, 800])
@pytest.mark.parametrize("reported_kind", ["missing", "bool", "float", "zero", "negative", "plus8"])
def test_shared_referee_probe_rejects_invalid_reported_visits(requested, reported_kind):
    runner = _runner()
    reported = {
        "missing": None,
        "bool": True,
        "float": float(requested),
        "zero": 0,
        "negative": -1,
        "plus8": requested + 8,
    }[reported_kind]
    client = _AnalysisClient([_referee_analysis(reported)])
    with pytest.raises(ValueError, match="visits"):
        asyncio.run(runner._probe_referee(client, requested, _live_health()))


@pytest.mark.parametrize(
    ("requested", "reported"),
    [(requested, requested + extra) for requested in (200, 800) for extra in range(1, 8)],
)
def test_shared_referee_accepts_thread_overshoot_without_broadening_query_budget(requested, reported):
    runner = _runner()
    client = _AnalysisClient([_referee_analysis(reported)])
    assert asyncio.run(runner.strict_referee(client, [], requested, _live_health())) == (3.5, True)
    assert client.queries[0]["maxVisits"] == requested


@pytest.mark.parametrize(
    ("score", "ownership"),
    [
        (True, [1.0] * 361),
        ("3.5", [1.0] * 361),
        (3.5, [True] + [1.0] * 360),
        (3.5, ["1.0"] + [1.0] * 360),
        (3.5, "not ownership"),
    ],
)
def test_shared_referee_rejects_true_numeric_type_violations(score, ownership):
    runner = _runner()
    client = _AnalysisClient([_referee_analysis(200, score=score, ownership=ownership)])
    with pytest.raises(ValueError, match="scoreLead|ownership"):
        asyncio.run(runner._probe_referee(client, 200, _live_health()))


@pytest.mark.parametrize(
    "uncertainty", ["score_missing", "score_nan", "ownership_missing", "ownership_short", "ownership_nan", "unsettled"]
)
def test_live_b28_200_maps_numeric_uncertainty_to_replenishable_outcomes(monkeypatch, uncertainty):
    runner = _runner()
    analysis = _referee_analysis(200)
    if uncertainty == "score_missing":
        del analysis["rootInfo"]["scoreLead"]
    elif uncertainty == "score_nan":
        analysis["rootInfo"]["scoreLead"] = float("nan")
    elif uncertainty == "ownership_missing":
        del analysis["ownership"]
    elif uncertainty == "ownership_short":
        analysis["ownership"] = [1.0] * 360
    elif uncertainty == "ownership_nan":
        analysis["ownership"][0] = float("nan")
    else:
        analysis["ownership"] = [0.0] * 361
    client = _AnalysisClient([analysis])

    async def pass_move(*_args, **_kwargs):
        return "pass"

    monkeypatch.setattr(runner, "analyze_player_move", pass_move)
    outcome = asyncio.run(runner.play_extension_game(client, object(), extension.GameRequest(32, "B"), _proof(runner)))
    expected = "inconclusive_score" if uncertainty.startswith("score_") else "inconclusive_unsettled"
    assert outcome.result == expected and outcome.conclusive is False


@pytest.mark.parametrize(
    "uncertainty", ["score_missing", "score_inf", "ownership_missing", "ownership_short", "ownership_inf", "unsettled"]
)
def test_live_b28_800_maps_all_numeric_uncertainty_to_unstable(monkeypatch, uncertainty):
    runner = _runner()
    stability = _referee_analysis(800)
    if uncertainty == "score_missing":
        del stability["rootInfo"]["scoreLead"]
    elif uncertainty == "score_inf":
        stability["rootInfo"]["scoreLead"] = float("inf")
    elif uncertainty == "ownership_missing":
        del stability["ownership"]
    elif uncertainty == "ownership_short":
        stability["ownership"] = [1.0] * 360
    elif uncertainty == "ownership_inf":
        stability["ownership"][0] = float("inf")
    else:
        stability["ownership"] = [0.0] * 361
    client = _AnalysisClient([_referee_analysis(200), stability])

    async def pass_move(*_args, **_kwargs):
        return "pass"

    monkeypatch.setattr(runner, "analyze_player_move", pass_move)
    outcome = asyncio.run(runner.play_extension_game(client, object(), extension.GameRequest(32, "B"), _proof(runner)))
    assert outcome.result == "inconclusive_unstable" and outcome.conclusive is False


@pytest.mark.parametrize("visits", [200, 800])
def test_preflight_referee_accepts_unsettled_or_missing_numeric_evidence(visits):
    runner = _runner()
    analysis = _referee_analysis(visits)
    del analysis["ownership"]
    probe = asyncio.run(runner._probe_referee(_AnalysisClient([analysis]), visits, _live_health()))
    assert probe["score"] == 3.5 and probe["settled"] is False


def test_live_initial_and_stability_adjudication_share_strict_referee_path(monkeypatch):
    runner = _runner()
    client = _AnalysisClient([_referee_analysis(200), _referee_analysis(800)])

    async def play(**kwargs):
        assert await kwargs["adjudicate"]([]) == (3.5, True)
        return GameOutcome("B", "our_win", True, 0, 3.5, True, "move_cap")

    monkeypatch.setattr(runner, "play_one_game", play)
    outcome = asyncio.run(runner.play_extension_game(client, object(), extension.GameRequest(32, "B"), _proof(runner)))
    assert outcome.result == "our_win"
    assert [query["maxVisits"] for query in client.queries] == [200, 800]


@pytest.mark.parametrize(
    "malformed",
    ["visits", "score_bool", "score_string", "ownership_bool", "ownership_string"],
)
def test_live_true_referee_type_violation_raises_definite_error(monkeypatch, malformed):
    runner = _runner()
    analysis = _referee_analysis(200)
    if malformed == "visits":
        analysis["rootInfo"]["visits"] = 208
    elif malformed == "score_bool":
        analysis["rootInfo"]["scoreLead"] = True
    elif malformed == "score_string":
        analysis["rootInfo"]["scoreLead"] = "3.5"
    elif malformed == "ownership_bool":
        analysis["ownership"][0] = False
    else:
        analysis["ownership"][0] = "1.0"
    client = _AnalysisClient([analysis])

    async def play(**kwargs):
        await kwargs["adjudicate"]([])
        raise AssertionError("unreachable")

    monkeypatch.setattr(runner, "play_one_game", play)
    with pytest.raises(ValueError, match="visits|scoreLead|ownership"):
        asyncio.run(runner.play_extension_game(client, object(), extension.GameRequest(32, "B"), _proof(runner)))


def test_preflight_finishes_every_gate_in_order_and_returns_frozen_proof():
    runner = _runner()
    calls, health = [], _live_health()

    async def health_fetch(_client):
        calls.append("health")
        return health

    async def player_probe(_client, visits, _identity):
        calls.append(f"b18:{visits}")
        return visits

    async def referee_probe(_client, visits, _identity):
        calls.append(f"b28:{visits}")
        return visits

    proof = asyncio.run(
        runner.preflight_campaign(
            object(),
            expected_health=health,
            fetch_health=health_fetch,
            probe_player=player_probe,
            probe_referee=referee_probe,
            token_loader=lambda _env: calls.append("token") or "secret",
            smoke_loader=lambda _path: calls.append("smoke") or {"pass_code": 361, "resign_code": 362},
        )
    )
    assert calls == ["health", "b18:32", "b18:64", "b28:200", "b28:800", "token", "smoke"]
    assert dataclasses.is_dataclass(proof) and proof.__dataclass_params__.frozen
    assert proof.token == "secret" and proof.pass_code != proof.resign_code


@pytest.mark.parametrize("gate", ["health", "b18:32", "b18:64", "b28:200", "b28:800", "rung", "token", "smoke"])
def test_each_preflight_gate_failure_leaves_initialized_ledger_reservation_free(tmp_path, monkeypatch, gate):
    runner = _runner()
    path = tmp_path / f"{gate.replace(':', '-')}.jsonl"
    health = _live_health()
    extension.initialize_v6_campaign(path, gate.replace(":", "-"), health)

    async def fetch(_client):
        if gate == "health":
            raise RuntimeError("health gate")
        return health

    async def player(_client, visits, _health):
        if gate == f"b18:{visits}":
            raise RuntimeError(gate)

    async def referee(_client, visits, _health):
        if gate == f"b28:{visits}":
            raise RuntimeError(gate)

    if gate == "rung":
        monkeypatch.setattr(
            runner.run_golaxy_9d_alignment,
            "get_rung",
            lambda _rung: SimpleNamespace(golaxy_api_level=3200, golaxy_level_name="drift"),
        )
    original_preflight = runner.preflight_campaign

    async def integrated_preflight(client, *, expected_health):
        return await original_preflight(
            client,
            expected_health=expected_health,
            fetch_health=fetch,
            probe_player=player,
            probe_referee=referee,
            token_loader=lambda _env: (_ for _ in ()).throw(RuntimeError("token")) if gate == "token" else "token",
            smoke_loader=lambda _path: (
                (_ for _ in ()).throw(RuntimeError("smoke"))
                if gate == "smoke"
                else {"pass_code": 361, "resign_code": 362}
            ),
        )

    monkeypatch.setattr(runner, "preflight_campaign", integrated_preflight)
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: _NoopAsyncClient())
    monkeypatch.setattr(
        runner,
        "_execute_serial_campaign_unlocked",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("executor must not run")),
    )
    with pytest.raises(Exception):
        asyncio.run(runner._run_network_mode(SimpleNamespace(out=str(path)), "live"))
    loaded = extension.load_campaign(path)
    assert not any(row["type"] in {"reservation", "stopped"} for row in loaded.records)


@pytest.mark.parametrize("drift", ["version", "path", "default", "running", "b18", "b28"])
def test_each_header_current_health_drift_class_leaves_zero_reservations(tmp_path, drift, monkeypatch):
    runner = _runner()
    header_health = _live_health()
    path = tmp_path / f"drift-{drift}.jsonl"
    extension.initialize_v6_campaign(path, drift, header_health)
    current = json.loads(json.dumps(header_health))
    if drift == "version":
        current["katago_version"] = "KataGo drift"
    elif drift == "path":
        current["models"]["b18"]["model_path"] = "/models/drift.bin.gz"
    elif drift == "default":
        current["default_model"] = "b28"
    elif drift == "running":
        current["models"]["b18"]["running"] = False
    else:
        current["models"][drift]["model_sha256"] = "0" * 64

    async def fetch(_client):
        return current

    original_preflight = runner.preflight_campaign

    async def integrated_preflight(client, *, expected_health):
        return await original_preflight(client, expected_health=expected_health, fetch_health=fetch)

    monkeypatch.setattr(runner, "preflight_campaign", integrated_preflight)
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: _NoopAsyncClient())
    monkeypatch.setattr(
        runner,
        "_execute_serial_campaign_unlocked",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("executor must not run")),
    )
    with pytest.raises(ValueError):
        asyncio.run(runner._run_network_mode(SimpleNamespace(out=str(path)), "live"))
    assert not any(row["type"] in {"reservation", "stopped"} for row in extension.load_campaign(path).records)


def _proof(runner):
    canonical, digest = runner.validate_complete_health(_live_health())
    health = _live_health()
    return runner.PreflightProof(
        canonical,
        digest,
        "token",
        361,
        362,
        runner._canonical_json(runner._identity(health, "b18")),
        runner._canonical_json(runner._identity(health, "b28")),
    )


def test_executor_rejects_mutated_proof_identity_before_reservation(tmp_path):
    runner = _runner()
    path = tmp_path / "proof.jsonl"
    extension.initialize_v6_campaign(path, "proof", _live_health())
    bad = dataclasses.replace(_proof(runner), b18_identity_canonical="{}")

    async def never(*_args):
        raise AssertionError("play must not run")

    with pytest.raises(ValueError, match="proof"):
        asyncio.run(runner.execute_serial_campaign(path, bad, never, emit=lambda _event: None))
    assert not any(row["type"] == "reservation" for row in extension.load_campaign(path).records)


def test_game_wrapper_uses_exact_contract_and_stability_recheck(monkeypatch):
    runner = _runner()
    calls = []

    async def fake_play_one_game(**kwargs):
        calls.append((kwargs["board_size"], kwargs["move_cap"], kwargs["our_color"]))
        history = []
        assert await kwargs["our_move"](history) == 17
        history.append(17)
        assert await kwargs["golaxy_move"](history) == "pass"
        assert await kwargs["adjudicate"](history) == (3.5, True)
        return GameOutcome("B", "our_win", True, 1, 3.5, True, "golaxy_pass")

    async def fake_our(_client, history, visits, health):
        calls.append(("our", list(history), visits, health["status"]))
        return 17

    async def fake_golaxy(_client, history, **kwargs):
        calls.append(("golaxy", list(history), kwargs["rung"].golaxy_api_level, kwargs["token"]))
        return "pass"

    async def fake_adjudicate(_client, history, visits, _health):
        calls.append(("referee", list(history), visits, True))
        return (3.5, True)

    monkeypatch.setattr(runner, "play_one_game", fake_play_one_game)
    monkeypatch.setattr(runner, "analyze_player_move", fake_our)
    monkeypatch.setattr(runner.adapters, "golaxy_move", fake_golaxy)
    monkeypatch.setattr(runner, "strict_referee", fake_adjudicate)
    outcome = asyncio.run(
        runner.play_extension_game(object(), object(), extension.GameRequest(32, "B"), _proof(runner))
    )
    assert outcome.result == "our_win"
    assert calls[0] == (19, 400, "B")
    assert [call[2] for call in calls if call[0] == "referee"] == [200, 800]
    assert any(call[:3] == ("golaxy", [17], 3300) for call in calls)


def test_game_wrapper_converts_unstable_and_stops_engine_terminal(monkeypatch):
    runner = _runner()

    async def conclusive(**_kwargs):
        return GameOutcome("B", "our_win", True, 10, 3.5, True, "move_cap")

    async def unstable(*_args, **_kwargs):
        return (4.5, True)

    monkeypatch.setattr(runner, "play_one_game", conclusive)
    monkeypatch.setattr(runner, "strict_referee", unstable)
    outcome = asyncio.run(
        runner.play_extension_game(object(), object(), extension.GameRequest(32, "B"), _proof(runner))
    )
    assert outcome.result == "inconclusive_unstable" and outcome.conclusive is False

    async def terminal(**_kwargs):
        return GameOutcome("B", "inconclusive_terminal", False, 10, None, False, "golaxy_terminal")

    monkeypatch.setattr(runner, "play_one_game", terminal)
    with pytest.raises(RuntimeError, match="definite runtime stop"):
        asyncio.run(runner.play_extension_game(object(), object(), extension.GameRequest(32, "B"), _proof(runner)))


def test_game_wrapper_rejects_nonfinite_stability_score(monkeypatch):
    runner = _runner()

    async def conclusive(**_kwargs):
        return GameOutcome("B", "our_win", True, 10, 3.5, True, "move_cap")

    async def nonfinite(*_args, **_kwargs):
        raise ValueError("referee scoreLead must be finite")

    monkeypatch.setattr(runner, "play_one_game", conclusive)
    monkeypatch.setattr(runner, "strict_referee", nonfinite)
    with pytest.raises(ValueError, match="scoreLead"):
        asyncio.run(runner.play_extension_game(object(), object(), extension.GameRequest(32, "B"), _proof(runner)))


def test_executor_cools_down_serially_and_play_failure_closes_attempt(tmp_path):
    runner = _runner()
    path = tmp_path / "live.jsonl"
    extension.initialize_v6_campaign(path, "live", _live_health())
    sleeps, active, calls = [], 0, 0

    async def play(request, _proof_value):
        nonlocal active, calls
        active += 1
        calls += 1
        assert active == 1
        active -= 1
        if calls == 2:
            raise RuntimeError("business 7002")
        return GameOutcome(request.color, "our_win", True, 10, 2.5 if request.color == "B" else -2.5, True)

    async def sleep(value):
        sleeps.append(value)

    with pytest.raises(runner.CampaignStopped, match="7002"):
        asyncio.run(runner.execute_serial_campaign(path, _proof(runner), play, sleep=sleep, emit=lambda _event: None))
    loaded = extension.load_campaign(path, summary=True)
    assert loaded.stopped and sleeps == [5.0]
    assert [row["type"] for row in loaded.records[-4:]] == ["reservation", "result", "reservation", "stopped"]


def test_executor_reaches_exact_20_20_completion_without_extra_reservation(tmp_path):
    runner = _runner()
    path = tmp_path / "complete.jsonl"
    extension.initialize_v6_campaign(path, "complete", _live_health())
    requests = []

    async def play(request, _proof_value):
        requests.append(request)
        score = 2.5 if request.color == "B" else -2.5
        return GameOutcome(request.color, "our_win", True, 10, score, True)

    result = asyncio.run(
        runner.execute_serial_campaign(
            path, _proof(runner), play, sleep=lambda _value: asyncio.sleep(0), emit=lambda _e: None
        )
    )
    loaded = extension.load_campaign(path)
    assert result["completion_status"] == "completed"
    assert [(v, sum(row["visits"] == v and row["conclusive"] for row in loaded.evidence)) for v in (32, 64)] == [
        (32, 20),
        (64, 20),
    ]
    assert len(requests) == 26
    assert sum(row["type"] == "reservation" for row in loaded.records) == 26


def test_executor_replenishes_inconclusive_with_same_color(tmp_path):
    runner = _runner()
    path = tmp_path / "replenish.jsonl"
    extension.initialize_v6_campaign(path, "replenish", _live_health())
    requests = []

    async def play(request, _proof_value):
        requests.append(request)
        if len(requests) == 1:
            return GameOutcome(request.color, "inconclusive_unsettled", False, 10, 0.5, False)
        raise RuntimeError("stop after proving continuation")

    with pytest.raises(runner.CampaignStopped):
        asyncio.run(
            runner.execute_serial_campaign(
                path, _proof(runner), play, sleep=lambda _value: asyncio.sleep(0), emit=lambda _e: None
            )
        )
    assert requests == [extension.GameRequest(32, "B"), extension.GameRequest(32, "B")]


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("golaxy", "business 7002"),
        ("golaxy", "quota exhausted"),
        ("golaxy", "rate limit"),
        ("local", "malformed response"),
        ("local", "identity drift"),
    ],
)
def test_each_definite_real_game_wrapper_failure_durably_stops(tmp_path, monkeypatch, source, reason):
    runner = _runner()
    path = tmp_path / f"failure-{reason.replace(' ', '-')}.jsonl"
    extension.initialize_v6_campaign(path, reason, _live_health())

    class LocalClient:
        async def post(self, url, **_kwargs):
            if reason == "malformed response":
                return SimpleNamespace(
                    status_code=200,
                    raise_for_status=lambda: None,
                    json=lambda: (_ for _ in ()).throw(ValueError("malformed response")),
                )
            analysis = {
                "rootInfo": {"visits": 32},
                "moveInfos": [{"move": "D4", "visits": 32, "order": 0}],
                "policy": [0.0] * 362,
                "_wrapper": _wrapper("b18"),
            }
            analysis["_wrapper"]["model_sha256"] = "identity drift"
            return httpx.Response(200, json=analysis, request=httpx.Request("POST", url))

    async def golaxy_failure(*_args, **_kwargs):
        raise RuntimeError(reason)

    monkeypatch.setattr(runner.adapters, "golaxy_move", golaxy_failure)

    async def drive_one_move(**kwargs):
        if source == "local":
            await kwargs["our_move"]([])
        else:
            await kwargs["golaxy_move"]([])
        raise AssertionError("unreachable")

    monkeypatch.setattr(runner, "play_one_game", drive_one_move)

    async def play(request, proof):
        return await runner.play_extension_game(LocalClient(), object(), request, proof)

    with pytest.raises(runner.CampaignStopped, match=reason):
        asyncio.run(runner.execute_serial_campaign(path, _proof(runner), play, emit=lambda _event: None))
    loaded = extension.load_campaign(path, summary=True)
    assert loaded.stopped and loaded.open_attempt is None and reason in loaded.records[-1]["reason"]


def test_executor_emit_and_result_append_faults_never_compensate(tmp_path, monkeypatch):
    runner = _runner()

    async def play(request, _proof_value):
        return GameOutcome(request.color, "our_win", True, 10, 2.5, True)

    emit_path = tmp_path / "emit.jsonl"
    extension.initialize_v6_campaign(emit_path, "emit", _live_health())
    with pytest.raises(RuntimeError, match="emit"):
        asyncio.run(
            runner.execute_serial_campaign(
                emit_path, _proof(runner), play, emit=lambda _event: (_ for _ in ()).throw(RuntimeError("emit"))
            )
        )
    emitted = extension.load_campaign(emit_path, summary=True)
    assert emitted.open_attempt == 1 and not emitted.stopped

    result_path = tmp_path / "result.jsonl"
    extension.initialize_v6_campaign(result_path, "result", _live_health())
    monkeypatch.setattr(
        runner.protocol, "append_result", lambda *_args: (_ for _ in ()).throw(OSError("partial write"))
    )
    with pytest.raises(OSError, match="partial write"):
        asyncio.run(runner.execute_serial_campaign(result_path, _proof(runner), play, emit=lambda _event: None))
    failed = extension.load_campaign(result_path, summary=True)
    assert failed.open_attempt == 1 and not failed.stopped


def test_executor_reservation_stop_and_base_exception_faults_do_not_compensate(tmp_path, monkeypatch):
    runner = _runner()

    async def winning(request, _proof_value):
        return GameOutcome(request.color, "our_win", True, 10, 2.5, True)

    reservation_path = tmp_path / "reservation.jsonl"
    extension.initialize_v6_campaign(reservation_path, "reservation", _live_health())
    original_reservation = runner.protocol.append_reservation
    monkeypatch.setattr(runner.protocol, "append_reservation", lambda *_args: (_ for _ in ()).throw(OSError("fsync")))
    with pytest.raises(OSError, match="fsync"):
        asyncio.run(runner.execute_serial_campaign(reservation_path, _proof(runner), winning, emit=lambda _event: None))
    assert not any(
        row["type"] in {"reservation", "stopped"} for row in extension.load_campaign(reservation_path).records
    )
    monkeypatch.setattr(runner.protocol, "append_reservation", original_reservation)

    stop_path = tmp_path / "stop.jsonl"
    extension.initialize_v6_campaign(stop_path, "stop", _live_health())

    async def failing(*_args):
        raise RuntimeError("quota")

    monkeypatch.setattr(runner.protocol, "append_stop", lambda *_args: (_ for _ in ()).throw(OSError("stop fsync")))
    with pytest.raises(OSError, match="stop fsync"):
        asyncio.run(runner.execute_serial_campaign(stop_path, _proof(runner), failing, emit=lambda _event: None))
    stopped = extension.load_campaign(stop_path, summary=True)
    assert stopped.open_attempt == 1 and not stopped.stopped

    interrupt_path = tmp_path / "interrupt.jsonl"
    extension.initialize_v6_campaign(interrupt_path, "interrupt", _live_health())

    async def interrupted(*_args):
        raise KeyboardInterrupt("injected interrupt")

    with pytest.raises(KeyboardInterrupt, match="injected interrupt"):
        asyncio.run(
            runner.execute_serial_campaign(interrupt_path, _proof(runner), interrupted, emit=lambda _event: None)
        )
    interrupted_state = extension.load_campaign(interrupt_path, summary=True)
    assert interrupted_state.open_attempt == 1 and not interrupted_state.stopped


@pytest.mark.parametrize("boundary", ["reservation", "result", "stop"])
def test_executor_fsync_failure_at_each_ledger_boundary_never_compensates(tmp_path, monkeypatch, boundary):
    runner = _runner()
    path = tmp_path / f"fsync-{boundary}.jsonl"
    extension.initialize_v6_campaign(path, f"fsync-{boundary}", _live_health())

    async def play(request, _proof_value):
        if boundary == "stop":
            raise RuntimeError("play failed")
        return GameOutcome(request.color, "our_win", True, 10, 2.5, True)

    fsync_calls = 0

    def fail_target_fsync(_fd):
        nonlocal fsync_calls
        fsync_calls += 1
        target = 1 if boundary == "reservation" else 2
        if fsync_calls == target:
            raise OSError(f"{boundary} fsync")

    monkeypatch.setattr(runner.protocol.os, "fsync", fail_target_fsync)
    with pytest.raises(OSError, match=f"{boundary} fsync"):
        asyncio.run(runner.execute_serial_campaign(path, _proof(runner), play, emit=lambda _event: None))
    loaded = extension.load_campaign(path, summary=True)
    tail_types = [row["type"] for row in loaded.records[-2:]]
    if boundary == "reservation":
        assert loaded.open_attempt == 1 and tail_types[-1] == "reservation"
    elif boundary == "result":
        assert loaded.open_attempt is None and tail_types == ["reservation", "result"]
    else:
        assert loaded.stopped and tail_types == ["reservation", "stopped"]


@pytest.mark.parametrize("boundary", ["reservation", "result", "stop"])
def test_executor_partial_write_at_each_ledger_boundary_freezes_replay_without_compensation(
    tmp_path, monkeypatch, boundary
):
    runner = _runner()
    path = tmp_path / f"partial-{boundary}.jsonl"
    extension.initialize_v6_campaign(path, f"partial-{boundary}", _live_health())

    def partial(*_args):
        with path.open("ab") as handle:
            handle.write(b'{"type":')
            handle.flush()
        raise OSError(f"{boundary} partial")

    monkeypatch.setattr(runner.protocol, f"append_{boundary}", partial)

    async def play(request, _proof_value):
        if boundary == "stop":
            raise RuntimeError("play failed")
        return GameOutcome(request.color, "our_win", True, 10, 2.5, True)

    with pytest.raises(OSError, match=f"{boundary} partial"):
        asyncio.run(runner.execute_serial_campaign(path, _proof(runner), play, emit=lambda _event: None))
    with pytest.raises(ValueError, match="JSONL"):
        extension.load_campaign(path, summary=True)
    assert path.read_bytes().endswith(b'{"type":')


def test_executor_actual_async_cancellation_leaves_unmatched_without_stop(tmp_path):
    runner = _runner()
    path = tmp_path / "cancel.jsonl"
    extension.initialize_v6_campaign(path, "cancel", _live_health())

    async def cancelled(*_args):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runner.execute_serial_campaign(path, _proof(runner), cancelled, emit=lambda _event: None))
    loaded = extension.load_campaign(path, summary=True)
    assert loaded.open_attempt == 1 and not loaded.stopped


def test_cli_modes_are_strict_and_summary_is_offline(tmp_path, monkeypatch, capsys):
    runner = _runner()
    parser = runner.build_parser()
    assert runner.validate_args(parser.parse_args(["--audit-parent"])) == "audit"
    assert runner.validate_args(parser.parse_args(["--initialize", "--out", "x"])) == "initialize"
    assert runner.validate_args(parser.parse_args(["--summary", "--out", "x"])) == "summary"
    assert runner.validate_args(parser.parse_args(["--out", "x"])) == "live"
    with pytest.raises(ValueError):
        runner.validate_args(parser.parse_args(["--summary", "--out", "x", "--parent", "p"]))
    with pytest.raises(ValueError, match="SHA"):
        runner.validate_args(
            parser.parse_args(["--authorize-continuation", "--parent", "p", "--parent-sha256", "bad", "--out", "new"])
        )
    with pytest.raises(ValueError, match="differ"):
        runner.validate_args(
            parser.parse_args(
                ["--authorize-continuation", "--parent", "same", "--parent-sha256", "0" * 64, "--out", "same"]
            )
        )
    path = tmp_path / "summary.jsonl"
    extension.initialize_v6_campaign(path, "summary", _live_health())
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("network")))
    assert runner.main(["--summary", "--out", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["protocol"] == extension.V6_PROTOCOL


def test_output_lock_rejects_file_and_directory_symlink_aliases(tmp_path):
    runner = _runner()
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real = real_dir / "campaign.jsonl"
    real.write_text("x")
    file_alias = tmp_path / "alias.jsonl"
    file_alias.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        with runner.campaign_output_lock(file_alias):
            pass
    dir_alias = tmp_path / "alias-dir"
    dir_alias.symlink_to(real_dir, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        with runner.campaign_output_lock(dir_alias / "campaign.jsonl"):
            pass


def test_output_lock_rejects_actual_second_writer(tmp_path):
    runner = _runner()
    path = tmp_path / "campaign.jsonl"
    with runner.campaign_output_lock(path):
        with pytest.raises(RuntimeError, match="locked"):
            with runner.campaign_output_lock(path):
                pass


def test_live_requires_existing_strict_ledger_before_health_network(tmp_path, monkeypatch):
    runner = _runner()
    calls = []

    class Client:
        async def __aenter__(self):
            calls.append("network")
            return self

        async def __aexit__(self, *_args):
            pass

    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: Client())
    with pytest.raises(ValueError, match="ledger"):
        asyncio.run(runner._run_network_mode(SimpleNamespace(out=str(tmp_path / "missing")), "live"))
    assert calls == []


class _NoopAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def test_initialize_health_failure_creates_no_output(tmp_path, monkeypatch):
    runner = _runner()
    out = tmp_path / "initialize.jsonl"
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: _NoopAsyncClient())

    async def fail_health(_client):
        raise RuntimeError("health failed")

    monkeypatch.setattr(runner, "fetch_complete_health", fail_health)
    with pytest.raises(RuntimeError, match="health failed"):
        asyncio.run(runner._run_network_mode(SimpleNamespace(out=str(out)), "initialize"))
    assert not out.exists() and not Path(f"{out}.lock").exists()


def test_initialize_later_preflight_failure_leaves_header_carries_and_zero_reservations(tmp_path, monkeypatch):
    runner = _runner()
    out = tmp_path / "initialize-probe.jsonl"
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: _NoopAsyncClient())

    async def health(_client):
        return _live_health()

    async def fail_preflight(*_args, **_kwargs):
        raise RuntimeError("probe failed")

    monkeypatch.setattr(runner, "fetch_complete_health", health)
    monkeypatch.setattr(runner, "_preflight_for_header", fail_preflight)
    with pytest.raises(RuntimeError, match="probe failed"):
        asyncio.run(runner._run_network_mode(SimpleNamespace(out=str(out)), "initialize"))
    loaded = extension.load_campaign(out)
    assert len(loaded.records) == 14 and not any(row["type"] == "reservation" for row in loaded.records)


def _uncertain_parent(tmp_path):
    parent = tmp_path / "parent-v6.jsonl"
    extension.initialize_v6_campaign(parent, "parent-v6", _live_health())
    extension.append_reservation(parent, 1, extension.load_campaign(parent).action)
    return parent


def test_continuation_health_drift_creates_no_output(tmp_path, monkeypatch):
    runner = _runner()
    parent = _uncertain_parent(tmp_path)
    out = tmp_path / "continuation.jsonl"
    current = _live_health()
    current["models"]["b18"]["model_path"] = "/models/drift-b18.bin.gz"
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: _NoopAsyncClient())

    async def health(_client):
        return current

    monkeypatch.setattr(runner, "fetch_complete_health", health)
    args = SimpleNamespace(out=str(out), parent=str(parent), parent_sha256=_sha256(parent))
    with pytest.raises(ValueError, match="health response drifted"):
        asyncio.run(runner._run_network_mode(args, "continue"))
    assert not out.exists()


def test_continuation_later_preflight_failure_leaves_v7_reservation_free(tmp_path, monkeypatch):
    runner = _runner()
    parent = _uncertain_parent(tmp_path)
    out = tmp_path / "continuation-probe.jsonl"
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: _NoopAsyncClient())

    async def health(_client):
        return _live_health()

    async def fail_preflight(*_args, **_kwargs):
        raise RuntimeError("referee probe failed")

    monkeypatch.setattr(runner, "fetch_complete_health", health)
    monkeypatch.setattr(runner, "_preflight_for_header", fail_preflight)
    args = SimpleNamespace(out=str(out), parent=str(parent), parent_sha256=_sha256(parent))
    with pytest.raises(RuntimeError, match="referee probe failed"):
        asyncio.run(runner._run_network_mode(args, "continue"))
    loaded = extension.load_campaign(out)
    assert loaded.header["protocol"] == extension.V7_PROTOCOL
    assert not any(row["type"] == "reservation" for row in loaded.records)


@pytest.mark.parametrize("mode", ["initialize", "continue"])
def test_initialize_and_continuation_reject_existing_output(tmp_path, monkeypatch, mode):
    runner = _runner()
    parent = _uncertain_parent(tmp_path)
    out = tmp_path / f"existing-{mode}.jsonl"
    out.write_text("do not overwrite", encoding="utf-8")
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: _NoopAsyncClient())

    async def health(_client):
        return _live_health()

    monkeypatch.setattr(runner, "fetch_complete_health", health)
    args = SimpleNamespace(out=str(out), parent=str(parent), parent_sha256=_sha256(parent))
    with pytest.raises(ValueError, match="already exists"):
        asyncio.run(runner._run_network_mode(args, mode))
    assert out.read_text(encoding="utf-8") == "do not overwrite"


@pytest.mark.parametrize("elapsed", [True, float("nan"), float("inf"), float("-inf")])
def test_append_result_rejects_nonfinite_or_nonplain_elapsed_without_mutation(tmp_path, elapsed):
    path = tmp_path / "nonfinite.jsonl"
    extension.initialize_v6_campaign(path, "nonfinite", HEALTH)
    extension.append_reservation(path, 1, extension.load_campaign(path).action)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="finite"):
        extension.append_result(path, 1, GameOutcome("B", "our_win", True, 1, 1.0, True), elapsed)

    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "outcome",
    [
        GameOutcome("B", "our_win", True, 10, None, True, "arbitrary"),
        GameOutcome("B", "our_loss", False, 10, None, True, "golaxy_resign"),
        GameOutcome("B", "our_win", True, 10, 1.0, True, "golaxy_resign"),
        GameOutcome("B", "our_win", True, 10, None, True, "move_cap"),
        GameOutcome("B", "our_win", True, 10, -1.0, True, "move_cap"),
        GameOutcome("B", "our_loss", False, 10, 1.0, True, "our_pass"),
        GameOutcome("B", "inconclusive_score", False, 10, None, False, "golaxy_resign"),
        GameOutcome("B", "inconclusive_unsettled", False, 10, 1.0, False, "golaxy_resign"),
    ],
)
def test_append_result_rejects_contradictory_game_outcomes_without_mutation(tmp_path, outcome):
    path = tmp_path / "contradiction.jsonl"
    extension.initialize_v6_campaign(path, "contradiction", HEALTH)
    extension.append_reservation(path, 1, extension.load_campaign(path).action)
    before = path.read_bytes()

    with pytest.raises(ValueError):
        extension.append_result(path, 1, outcome, 1.0)

    assert path.read_bytes() == before


def test_replay_rejects_tampered_game_outcome_contradiction(tmp_path):
    path = tmp_path / "tampered-outcome.jsonl"
    extension.initialize_v6_campaign(path, "tampered-outcome", HEALTH)
    extension.append_reservation(path, 1, extension.load_campaign(path).action)
    extension.append_result(path, 1, GameOutcome("B", "our_win", True, 10, None, True, "golaxy_resign"), 1.0)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[-1]["result"] = "our_loss"
    rows[-1]["our_win"] = False
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(ValueError):
        extension.load_campaign(path, summary=True)


@pytest.mark.parametrize(
    ("terminal", "timestamp_field", "timestamp_value"),
    [
        ("header", "created_at", ""),
        ("header", "created_at", "2026-08-01T12:00:00+08:00"),
        ("reservation", "created_at", "not-a-timestamp"),
        ("result", "completed_at", "2026-08-01 12:00:00Z"),
        ("stopped", "stopped_at", "2026-13-01T12:00:00Z"),
    ],
)
def test_replay_rejects_empty_or_malformed_non_utc_rfc3339_timestamps(
    tmp_path, terminal, timestamp_field, timestamp_value
):
    path = tmp_path / f"bad-time-{terminal}.jsonl"
    extension.initialize_v6_campaign(path, f"bad-time-{terminal}", HEALTH)
    if terminal != "header":
        extension.append_reservation(path, 1, extension.load_campaign(path).action)
    if terminal == "result":
        extension.append_result(path, 1, GameOutcome("B", "our_win", True, 10, None, True, "golaxy_resign"), 1.0)
    elif terminal == "stopped":
        extension.append_stop(path, 1, "engine stopped")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    target = {"header": 0, "reservation": -1, "result": -1, "stopped": -1}[terminal]
    rows[target][timestamp_field] = timestamp_value
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(ValueError, match="RFC3339"):
        extension.load_campaign(path, summary=True)
