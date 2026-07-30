import asyncio
import dataclasses
import hashlib
import importlib
import json
import math
import os
import subprocess
import struct
import sys
from fractions import Fraction
from pathlib import Path

import httpx
import pytest


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

campaign = importlib.import_module("golaxy_sampling_campaign")
runner = importlib.import_module("run_golaxy_sampling_campaign")


def ledger_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_canonical_rows(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n" for row in rows)
    )


def expected_uniform(seed, reservation_id, ply):
    reservation_bytes = reservation_id.encode("utf-8")
    payload = (
        b"golaxy-humansl-weighted-v1\0"
        + struct.pack(">Q", seed)
        + struct.pack(">H", len(reservation_bytes))
        + reservation_bytes
        + struct.pack(">I", ply)
    )
    digest = hashlib.sha256(payload).digest()
    return Fraction(int.from_bytes(digest[:8], "big"), 2**64), digest.hex()


def expected_policy_sha256(policy):
    payload = b"".join(struct.pack(">d", float(weight)) for weight in policy)
    return hashlib.sha256(payload).hexdigest()


def result(
    origin_id,
    *,
    stage="sampling_quasi_5d",
    player="rank_5d@1",
    slot=0,
    color="B",
    outcome="win",
):
    return {
        "type": "result",
        "origin_id": origin_id,
        "stage": stage,
        "player": player,
        "slot": slot,
        "color": color,
        "outcome": outcome,
    }


def completed_stage(stage_index, *, origin_prefix=None):
    stage, player, _api_level = campaign.STAGES[stage_index]
    prefix = origin_prefix or stage
    return [
        result(
            f"{prefix}-{slot}",
            stage=stage,
            player=player,
            slot=slot,
            color="B" if slot % 2 == 0 else "W",
            outcome="win" if slot < 6 else "loss",
        )
        for slot in range(10)
    ]


def test_protocol_mapping_and_frozen_value_objects_are_exact():
    assert campaign.STAGES == (
        ("sampling_quasi_5d", "rank_5d@1", 25),
        ("sampling_quasi_6d", "rank_6d@1", 27),
        ("sampling_quasi_7d", "rank_7d@1", 29),
        ("sampling_quasi_8d", "rank_8d@1", 31),
        ("sampling_quasi_9d", "rank_9d@1", 32),
    )
    assert campaign.STAGE_ORDER == tuple(stage for stage, _player, _level in campaign.STAGES)

    for value in (
        campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B"),
        campaign.CandidateSummary("sampling_quasi_5d", "rank_5d@1", 25, 0, 0, 0, 0),
        campaign.StageDecision(
            "sampling_quasi_5d",
            "completed",
            campaign.CandidateSummary("sampling_quasi_5d", "rank_5d@1", 25, 10, 6, 4, 0),
        ),
        campaign.CampaignDecision("completed", ()),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            value.status = "changed"


def test_initialize_sampling_ledger_freezes_parent_identity_and_protocol(tmp_path):
    parent_rows = [json.loads(line) for line in campaign.PARENT_PATH.read_text().splitlines()]
    path = tmp_path / "sampling.jsonl"

    loaded = campaign.initialize_campaign(path, "sampling-campaign", seed=2**64 - 1)

    assert (
        ledger_sha(campaign.PARENT_PATH)
        == campaign.PARENT_SHA256
        == ("4eff5434cd864215a35171d635e4268d06f31f45ca6be27e82e4e0a1105f64d5")
    )
    assert loaded.header == {
        "type": "campaign_header",
        "sequence": 0,
        "protocol": "golaxy-humansl-sampling-v1",
        "campaign_id": "sampling-campaign",
        "sampler": "golaxy-humansl-weighted-v1",
        "adjudication": {
            "protocol": "golaxy-sampling-adjudication-v1",
            "board_size": 19,
            "rules": "Chinese",
            "komi": 7.5,
            "move_cap": 400,
            "referee_visits": 200,
            "stability_visits": 800,
            "stability_delta": 1.0,
        },
        "stages": [
            {"stage": stage, "player": player, "golaxy_api_level": level} for stage, player, level in campaign.STAGES
        ],
        "valid_slots_per_stage": 10,
        "first_humansl_color": "B",
        "cooldown_seconds": 5.0,
        "seed": 2**64 - 1,
        "parent_path": str(campaign.PARENT_PATH.resolve()),
        "parent_sha256": campaign.PARENT_SHA256,
        "identity_snapshot": parent_rows[0]["identity_snapshot"],
    }
    assert loaded.records == ()
    assert loaded.action == campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")
    assert loaded.stopped is False
    assert loaded.unknown_charged_attempts == ()
    assert path.read_bytes().endswith(b"\n")
    assert len(path.read_text().splitlines()) == 1


@pytest.mark.parametrize("failure", ["sha", "protocol", "incomplete", "stopped"])
def test_initialize_rejects_invalid_parent_before_creating_child(tmp_path, monkeypatch, failure):
    parent = tmp_path / "parent.jsonl"
    parent.write_bytes(campaign.PARENT_PATH.read_bytes())
    rows = [json.loads(line) for line in parent.read_text().splitlines()]
    if failure == "protocol":
        rows[0]["protocol"] = "golaxy-alignment-campaign-v1"
    elif failure == "incomplete":
        rows = rows[:-2]
    elif failure == "stopped":
        rows.append({"type": "campaign_stopped", "reason": "closed"})
    parent.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
    monkeypatch.setattr(campaign, "PARENT_PATH", parent)
    expected_sha = "0" * 64 if failure == "sha" else ledger_sha(parent)
    monkeypatch.setattr(campaign, "PARENT_SHA256", expected_sha)
    child = tmp_path / "child.jsonl"

    with pytest.raises(ValueError, match="SHA|protocol|completed|stopped|parent"):
        campaign.initialize_campaign(child, "child", seed=1)

    assert not child.exists()


@pytest.mark.parametrize("campaign_id", ["", " padded", "padded ", True, 7])
def test_initialize_rejects_invalid_campaign_id_before_create(tmp_path, campaign_id):
    path = tmp_path / "sampling.jsonl"
    with pytest.raises(ValueError, match="campaign_id"):
        campaign.initialize_campaign(path, campaign_id, seed=0)
    assert not path.exists()


@pytest.mark.parametrize("seed", [True, -1, 2**64, 1.0, "1"])
def test_initialize_requires_plain_uint64_seed_before_create(tmp_path, seed):
    path = tmp_path / "sampling.jsonl"
    with pytest.raises(ValueError, match="uint64"):
        campaign.initialize_campaign(path, "sampling", seed=seed)
    assert not path.exists()


def test_initialize_uses_exclusive_create_and_preserves_existing_closed_ledger(tmp_path):
    path = tmp_path / "sampling.jsonl"
    campaign.initialize_campaign(path, "first", seed=1)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="already exists"):
        campaign.initialize_campaign(path, "second", seed=2)

    assert path.read_bytes() == before


def test_append_pairs_attempts_durably_and_closed_partial_ledger_resumes_uniquely(tmp_path):
    path = tmp_path / "sampling.jsonl"
    campaign.initialize_campaign(path, "sampling", seed=7)
    initial = path.read_bytes()
    first = campaign.replay_campaign(path)

    campaign.append_reservation(path, 1, first)
    with pytest.raises(ValueError, match="open|unmatched|unknown"):
        campaign.load_campaign(path)
    open_summary = campaign.campaign_summary(path)
    assert open_summary.unknown_charged_attempts == (1,)
    assert open_summary.action == first

    campaign.append_result(path, 1, "inconclusive", move_audits=[])
    assert campaign.replay_campaign(path) == first
    campaign.append_reservation(path, 2, campaign.replay_campaign(path))
    campaign.append_result(path, 2, "win", move_audits=[])

    loaded = campaign.load_campaign(path)
    assert loaded.unknown_charged_attempts == ()
    assert loaded.action == campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 1, "W")
    assert path.read_bytes().startswith(initial)
    assert [row["sequence"] for row in [loaded.header, *loaded.records]] == list(range(5))
    assert [row["attempt_id"] for row in loaded.records if row["type"] == "reservation"] == [1, 2]
    for line in path.read_text().splitlines():
        row = json.loads(line)
        assert line == json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)


def test_append_result_copies_reservation_and_generates_unique_origin(tmp_path):
    path = tmp_path / "sampling.jsonl"
    campaign.initialize_campaign(path, "campaign-a", seed=9)
    request = campaign.replay_campaign(path)
    campaign.append_reservation(path, 1, request)
    campaign.append_result(path, 1, "loss", conclusive=True, move_audits=[])

    result_row = campaign.load_campaign(path).records[-1]
    assert result_row == {
        "type": "result",
        "sequence": 2,
        "attempt_id": 1,
        "origin_id": "campaign-a:1",
        "stage": request.stage,
        "player": request.player,
        "golaxy_api_level": request.golaxy_api_level,
        "slot": request.slot,
        "color": request.color,
        "outcome": "loss",
        "conclusive": True,
        "move_audits": [],
    }


def test_open_reservation_fails_closed_and_append_stop_is_terminal(tmp_path):
    path = tmp_path / "sampling.jsonl"
    campaign.initialize_campaign(path, "sampling", seed=11)
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))

    with pytest.raises(ValueError, match="open|unmatched|unknown"):
        campaign.replay_campaign(path)
    campaign.append_stop(path, "remote outcome unknown", attempt_id=1, move_audits=[])

    summary = campaign.campaign_summary(path)
    assert summary.stopped is True
    assert summary.unknown_charged_attempts == ()
    assert isinstance(summary.action, campaign.CampaignDecision)
    assert summary.action.status == "stopped"
    with pytest.raises(ValueError, match="stopped"):
        campaign.load_campaign(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="stopped"):
        campaign.append_result(path, 1, "win", move_audits=[])
    assert path.read_bytes() == before


def make_two_closed_attempts(path):
    campaign.initialize_campaign(path, "tamper", seed=13)
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))
    campaign.append_result(path, 1, "inconclusive", move_audits=[])
    campaign.append_reservation(path, 2, campaign.replay_campaign(path))
    campaign.append_result(path, 2, "win", move_audits=[])
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda rows: rows[1].update(sequence=7), "sequence"),
        (lambda rows: rows.append({**rows[0], "sequence": 5}), "header"),
        (lambda rows: rows[3].update(attempt_id=4), "attempt_id|order|reservation"),
        (lambda rows: rows[3].update(slot=1, color="W"), "next action|reservation"),
        (lambda rows: rows[3].update(stage="sampling_quasi_9d", player="rank_9d@1"), "next action|reservation"),
        (lambda rows: rows[4].update(color="W"), "match|reservation"),
        (lambda rows: rows[4].update(golaxy_api_level=999), "match|reservation"),
        (lambda rows: rows[4].update(outcome="draw"), "outcome"),
        (lambda rows: rows[4].update(outcome="inconclusive", conclusive=True), "conclusive"),
        (lambda rows: rows[4].update(origin_id=rows[2]["origin_id"]), "origin_id"),
        (lambda rows: rows[4].update(extra="forbidden"), "extra|fields"),
    ],
)
def test_loader_rejects_sequence_schema_schedule_and_closure_tampering(tmp_path, mutation, message):
    path = tmp_path / "sampling.jsonl"
    rows = make_two_closed_attempts(path)
    mutation(rows)
    write_canonical_rows(path, rows)

    with pytest.raises(ValueError, match=message):
        campaign.campaign_summary(path)


def test_loader_rejects_truncated_noncanonical_and_non_object_json_lines(tmp_path):
    truncated = tmp_path / "truncated.jsonl"
    campaign.initialize_campaign(truncated, "truncated", seed=1)
    truncated.write_bytes(truncated.read_bytes()[:-1])
    with pytest.raises(ValueError, match="truncated"):
        campaign.load_campaign(truncated)

    invalid_json = tmp_path / "invalid.jsonl"
    invalid_json.write_text('{"type":"campaign_header"\n')
    with pytest.raises(ValueError, match="JSON"):
        campaign.load_campaign(invalid_json)

    noncanonical = tmp_path / "noncanonical.jsonl"
    noncanonical.write_text(json.dumps({"sequence": 0}) + "\n")
    with pytest.raises(ValueError, match="canonical|header"):
        campaign.load_campaign(noncanonical)

    non_object = tmp_path / "non-object.jsonl"
    non_object.write_text("[]\n")
    with pytest.raises(ValueError, match="object"):
        campaign.load_campaign(non_object)


def test_output_lock_rejects_second_writer_and_releases_cleanly(tmp_path):
    path = tmp_path / "sampling.jsonl"
    with campaign.output_lock(path):
        with pytest.raises(RuntimeError, match="locked|writer"):
            with campaign.output_lock(path):
                pass

    with campaign.output_lock(path):
        pass


def test_loader_rejects_tampered_parent_identity_and_rows_after_stop(tmp_path):
    identity_path = tmp_path / "identity.jsonl"
    campaign.initialize_campaign(identity_path, "identity", seed=1)
    rows = [json.loads(line) for line in identity_path.read_text().splitlines()]
    rows[0]["identity_snapshot"] = {"status": "tampered"}
    write_canonical_rows(identity_path, rows)
    with pytest.raises(ValueError, match="identity|parent"):
        campaign.load_campaign(identity_path)

    stopped_path = tmp_path / "stopped.jsonl"
    campaign.initialize_campaign(stopped_path, "stopped", seed=1)
    campaign.append_reservation(stopped_path, 1, campaign.replay_campaign(stopped_path))
    campaign.append_stop(stopped_path, "operator", attempt_id=1, move_audits=[])
    stopped_rows = [json.loads(line) for line in stopped_path.read_text().splitlines()]
    stopped_rows.append({**stopped_rows[1], "sequence": 3, "attempt_id": 2})
    write_canonical_rows(stopped_path, stopped_rows)
    with pytest.raises(ValueError, match="after stopped"):
        campaign.campaign_summary(stopped_path)


def test_parent_replay_uses_the_same_verified_byte_snapshot(tmp_path, monkeypatch):
    parent = tmp_path / "parent.jsonl"
    parent.write_bytes(campaign.PARENT_PATH.read_bytes())
    monkeypatch.setattr(campaign, "PARENT_PATH", parent)
    monkeypatch.setattr(campaign, "PARENT_SHA256", ledger_sha(parent))
    alignment = importlib.import_module("golaxy_alignment_campaign")
    original_summary = alignment.campaign_summary
    replayed_paths = []

    def recording_summary(path):
        replayed_paths.append(Path(path).resolve())
        return original_summary(path)

    monkeypatch.setattr(alignment, "campaign_summary", recording_summary)
    campaign.initialize_campaign(tmp_path / "child.jsonl", "snapshot", seed=1)

    assert replayed_paths
    assert replayed_paths[0] != parent.resolve()


def test_invalid_append_inputs_leave_open_ledger_byte_for_byte_unchanged(tmp_path):
    path = tmp_path / "sampling.jsonl"
    campaign.initialize_campaign(path, "append-validation", seed=1)
    request = campaign.replay_campaign(path)
    before_reservation = path.read_bytes()
    with pytest.raises(ValueError, match="attempt_id"):
        campaign.append_reservation(path, True, request)
    wrong_type_request = campaign.GameRequest(
        request.stage, request.player, float(request.golaxy_api_level), request.slot, request.color
    )
    with pytest.raises(ValueError, match="next action|request"):
        campaign.append_reservation(path, 1, wrong_type_request)
    assert path.read_bytes() == before_reservation
    campaign.append_reservation(path, 1, request)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="attempt_id"):
        campaign.append_result(path, True, "win", move_audits=[])
    with pytest.raises(ValueError, match="outcome"):
        campaign.append_result(path, 1, "draw", move_audits=[])
    with pytest.raises(ValueError, match="conclusive"):
        campaign.append_result(path, 1, "win", conclusive=False, move_audits=[])
    with pytest.raises(ValueError, match="reason"):
        campaign.append_stop(path, "", attempt_id=1, move_audits=[])

    assert path.read_bytes() == before
    assert campaign.campaign_summary(path).unknown_charged_attempts == (1,)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda header: header.update(cooldown_seconds=5),
        lambda header: header["adjudication"].update(stability_delta=1),
        lambda header: header["stages"][0].update(golaxy_api_level=25.0),
    ],
)
def test_loader_preserves_frozen_json_number_types_in_header(tmp_path, mutate):
    path = tmp_path / "header.jsonl"
    campaign.initialize_campaign(path, "header", seed=1)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(rows[0])
    write_canonical_rows(path, rows)

    with pytest.raises(ValueError, match="header"):
        campaign.load_campaign(path)


def test_loader_rejects_float_record_integer_and_type_changed_identity(tmp_path):
    record_path = tmp_path / "record.jsonl"
    campaign.initialize_campaign(record_path, "record", seed=1)
    campaign.append_reservation(record_path, 1, campaign.replay_campaign(record_path))
    rows = [json.loads(line) for line in record_path.read_text().splitlines()]
    rows[1]["golaxy_api_level"] = float(rows[1]["golaxy_api_level"])
    write_canonical_rows(record_path, rows)
    with pytest.raises(ValueError, match="reservation|next action|integer"):
        campaign.campaign_summary(record_path)

    identity_path = tmp_path / "identity-type.jsonl"
    campaign.initialize_campaign(identity_path, "identity-type", seed=1)
    rows = [json.loads(line) for line in identity_path.read_text().splitlines()]
    rows[0]["identity_snapshot"]["capability_schema"] = 1.0
    write_canonical_rows(identity_path, rows)
    with pytest.raises(ValueError, match="identity"):
        campaign.load_campaign(identity_path)


def test_loader_rejects_crlf_as_noncanonical_jsonl(tmp_path):
    path = tmp_path / "crlf.jsonl"
    campaign.initialize_campaign(path, "crlf", seed=1)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    with pytest.raises(ValueError, match="canonical"):
        campaign.load_campaign(path)


def test_append_transaction_respects_an_existing_cross_process_output_lock(tmp_path):
    path = tmp_path / "locked.jsonl"
    campaign.initialize_campaign(path, "locked", seed=1)
    script = f"""
import sys
sys.path.insert(0, {str(CALIBRATION)!r})
import golaxy_sampling_campaign as campaign
campaign.append_reservation({str(path)!r}, 1, campaign.replay_campaign({str(path)!r}))
"""

    with campaign.output_lock(path):
        attempted = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)

    assert attempted.returncode != 0
    assert campaign.load_campaign(path).records == ()


def test_empty_campaign_requests_humansl_as_black_in_first_slot():
    assert campaign.next_action([]) == campaign.GameRequest(
        stage="sampling_quasi_5d",
        player="rank_5d@1",
        golaxy_api_level=25,
        slot=0,
        color="B",
    )


@pytest.mark.parametrize("stage_index", range(len(campaign.STAGES)), ids=campaign.STAGE_ORDER)
def test_each_stage_alternates_ten_conclusive_slots_and_advances_exactly(stage_index):
    records = [row for prefix_index in range(stage_index) for row in completed_stage(prefix_index)]
    stage, player, api_level = campaign.STAGES[stage_index]
    requested_colors = []
    for slot in range(10):
        action = campaign.next_action(records)
        expected_color = "B" if slot % 2 == 0 else "W"
        assert action == campaign.GameRequest(stage, player, api_level, slot, expected_color)
        requested_colors.append(action.color)
        records.append(
            result(
                f"{stage}-game-{slot}",
                stage=stage,
                player=player,
                slot=action.slot,
                color=action.color,
                outcome="win" if slot % 3 else "loss",
            )
        )

    assert requested_colors == ["B", "W"] * 5
    assert campaign.summarize_candidate(records, stage) == campaign.CandidateSummary(
        stage=stage,
        player=player,
        golaxy_api_level=api_level,
        valid=10,
        wins=6,
        losses=4,
        inconclusive=0,
    )

    action = campaign.next_action(records)
    if stage_index + 1 < len(campaign.STAGES):
        next_stage, next_player, next_api_level = campaign.STAGES[stage_index + 1]
        assert action == campaign.GameRequest(next_stage, next_player, next_api_level, 0, "B")
    else:
        assert isinstance(action, campaign.CampaignDecision)
        assert action.status == "completed"


def test_inconclusive_does_not_enter_denominator_and_retries_same_slot_and_color():
    records = [result("attempt-1", outcome="inconclusive")]

    assert campaign.next_action(records) == campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")
    assert campaign.summarize_candidate(records, "sampling_quasi_5d").inconclusive == 1

    records.append(result("attempt-2", outcome="win"))
    assert campaign.next_action(records) == campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 1, "W")


def test_ten_valid_results_complete_stage_and_advance_in_fixed_order():
    records = completed_stage(0)

    assert campaign.stage_decision(records, "sampling_quasi_5d") == campaign.StageDecision(
        stage="sampling_quasi_5d",
        status="completed",
        summary=campaign.CandidateSummary("sampling_quasi_5d", "rank_5d@1", 25, 10, 6, 4, 0),
    )
    assert campaign.next_action(records) == campaign.GameRequest("sampling_quasi_6d", "rank_6d@1", 27, 0, "B")


def test_all_five_stages_complete_campaign_with_stage_summaries():
    records = [row for stage_index in range(5) for row in completed_stage(stage_index)]

    decision = campaign.next_action(records)

    assert isinstance(decision, campaign.CampaignDecision)
    assert decision.status == "completed"
    assert tuple(stage.stage for stage in decision.stages) == campaign.STAGE_ORDER
    assert all(stage.status == "completed" and stage.summary.valid == 10 for stage in decision.stages)


@pytest.mark.parametrize(
    "bad_record",
    [
        result("bad", stage="sampling_quasi_10d"),
        result("bad", player="rank_5d@4"),
        result("bad", color="X"),
        result("bad", color="W"),
        result("bad", slot=-1),
        result("bad", slot=10),
        result("bad", slot=True),
        result("bad", outcome="draw"),
        {"type": "mystery", "origin_id": "bad"},
    ],
)
def test_unknown_or_illegal_result_fields_are_rejected(bad_record):
    with pytest.raises(ValueError):
        campaign.next_action([bad_record])


def test_result_must_describe_the_current_effective_slot():
    with pytest.raises(ValueError, match="slot"):
        campaign.next_action([result("future", slot=1, color="W")])


def test_duplicate_result_origin_ids_are_rejected():
    records = [result("same"), result("same", outcome="inconclusive")]

    with pytest.raises(ValueError, match="origin_id"):
        campaign.next_action(records)


def test_more_than_ten_valid_results_for_a_stage_are_rejected():
    records = completed_stage(0)
    records.append(result("eleventh", slot=9, color="W", outcome="win"))

    with pytest.raises(ValueError, match="more than 10 valid results"):
        campaign.next_action(records)


@pytest.mark.parametrize(
    "records",
    [
        [{"type": "stopped"}],
        [result("first"), {"type": "stopped", "reason": "operator stop"}],
        completed_stage(0) + [{"type": "stopped", "origin_id": "optional-stop-id"}],
    ],
)
def test_any_stopped_record_stops_campaign_without_a_game_request(records):
    decision = campaign.next_action(records)

    assert isinstance(decision, campaign.CampaignDecision)
    assert decision.status == "stopped"


@pytest.mark.parametrize(
    ("seed", "reservation_id", "ply", "expected_digest"),
    [
        (
            0,
            "reservation-α",
            0,
            "f26ef0bfa15d4ceadc16f430c95954cd09ae213ede3dde92c419317eb74ae416",
        ),
        (
            2**64 - 1,
            "x",
            2**32 - 1,
            "353ca81f116996e9268fcffb090e440d207e044bab4fb66e4b074c1a1c2b8e47",
        ),
    ],
)
def test_derive_uniform_uses_frozen_domain_separated_binary_protocol(seed, reservation_id, ply, expected_digest):
    independently_derived_u, independently_derived_digest = expected_uniform(seed, reservation_id, ply)

    assert campaign.SAMPLING_ALGORITHM == "golaxy-humansl-weighted-v1"
    assert independently_derived_digest == expected_digest
    assert campaign.derive_uniform(seed, reservation_id, ply) == independently_derived_u
    assert isinstance(campaign.derive_uniform(seed, reservation_id, ply), Fraction)
    assert Fraction(0) <= campaign.derive_uniform(seed, reservation_id, ply) < Fraction(1)


def test_weighted_golden_selection_differs_from_argmax_and_records_exact_audit():
    policy = [0.0] * 362
    policy[0] = 9.0
    policy[20] = 1.0
    expected_u, _digest = expected_uniform(1, "golden", 17)

    audit = campaign.sample_human_policy(policy, [20, 0], 1, "golden", 17)

    assert max(range(362), key=policy.__getitem__) == 0
    assert audit.algorithm == "golaxy-humansl-weighted-v1"
    assert expected_u == Fraction(0xF9BAC4199EF8C424, 2**64)
    assert audit.u == f"{0xF9BAC4199EF8C424}/{2**64}"
    assert audit.u_raw == 0xF9BAC4199EF8C424
    assert audit.u_denominator == 2**64
    assert audit.index == 20
    assert audit.move == (1, 17)
    assert audit.policy_sha256 == expected_policy_sha256(policy)
    assert audit.policy_sha256 == "b1b6a80c7fdcc036764b697e9956d1fff6062e1d69e9a48cdfd73b723eacb4be"
    assert audit.positive_total == math.fsum([9.0, 1.0])
    assert audit.interval_low == math.fsum([9.0])
    assert audit.interval_high == math.fsum([9.0, 1.0])
    with pytest.raises(dataclasses.FrozenInstanceError):
        audit.index = 0


def test_candidates_use_index_order_and_independent_fsum_cumulative_bounds():
    policy = [0.0] * 362
    policy[2] = 0.1
    policy[19] = 0.2
    policy[361] = 0.3
    expected_u, _digest = expected_uniform(5, "bounds", 9)
    expected_weights = [policy[index] for index in (2, 19, 361)]
    expected_total = math.fsum(expected_weights)
    expected_bounds = [math.fsum(expected_weights[:end]) for end in range(4)]
    expected_target = expected_u * Fraction.from_float(expected_total)
    expected_position = next(
        position for position, upper in enumerate(expected_bounds[1:]) if Fraction.from_float(upper) > expected_target
    )

    audit = campaign.sample_human_policy(policy, {361, 19, 2}, 5, "bounds", 9)

    expected_index = (2, 19, 361)[expected_position]
    assert audit.index == expected_index
    assert audit.positive_total == expected_total
    assert audit.interval_low == expected_bounds[expected_position]
    assert audit.interval_high == expected_bounds[expected_position + 1]


def test_target_on_a_cumulative_boundary_uses_strict_upper_comparison():
    expected_u, _digest = expected_uniform(0, "strict-753", 0)
    policy = [0.0] * 362
    policy[0] = float(expected_u)
    policy[1] = 1.0 - policy[0]
    expected_total = math.fsum([policy[0], policy[1]])
    expected_target = expected_u * Fraction.from_float(expected_total)
    assert expected_target == Fraction.from_float(math.fsum([policy[0]]))

    audit = campaign.sample_human_policy(policy, [1, 0], 0, "strict-753", 0)

    assert audit.index == 1
    assert audit.interval_low == math.fsum([policy[0]])
    assert audit.interval_high == math.fsum([policy[0], policy[1]])


def test_maximum_uint64_digest_is_exactly_below_one_and_selects_unique_candidate(monkeypatch):
    original_sha256 = campaign.hashlib.sha256
    domain = b"golaxy-humansl-weighted-v1\0"

    class MaximumPrefixDigest:
        @staticmethod
        def digest():
            return b"\xff" * 8 + b"\0" * 24

    def sha256_with_maximum_uniform(payload):
        if bytes(payload).startswith(domain):
            return MaximumPrefixDigest()
        return original_sha256(payload)

    monkeypatch.setattr(campaign.hashlib, "sha256", sha256_with_maximum_uniform)
    expected_u = Fraction(2**64 - 1, 2**64)
    policy = [0.0] * 362
    policy[361] = math.ulp(0.0)

    assert campaign.derive_uniform(0, "maximum", 0) == expected_u
    assert campaign.derive_uniform(0, "maximum", 0) < 1
    audit = campaign.sample_human_policy(policy, [361], 0, "maximum", 0)
    assert audit.u == f"{2**64 - 1}/{2**64}"
    assert audit.u_raw == 2**64 - 1
    assert audit.u_denominator == 2**64
    assert audit.index == 361


def test_sampling_audit_round_trips_through_standard_json():
    policy = [0.0] * 362
    policy[361] = 1.0
    audit = campaign.sample_human_policy(policy, [361], 3, "json-audit", 4)

    native_audit = dataclasses.asdict(audit)
    restored = json.loads(json.dumps(native_audit))

    assert restored == native_audit
    assert restored["u"] == f"{restored['u_raw']}/{restored['u_denominator']}"


def test_reservation_id_must_be_a_plain_string():
    class ReservationId(str):
        pass

    reservation_id = ReservationId("subclass")
    policy = [1.0] + [0.0] * 361

    with pytest.raises(ValueError):
        campaign.derive_uniform(0, reservation_id, 0)
    with pytest.raises(ValueError):
        campaign.sample_human_policy(policy, [0], 0, reservation_id, 0)


def test_pass_is_sampled_like_any_other_positive_legal_candidate():
    policy = [0.0] * 362
    policy[361] = 2.5

    audit = campaign.sample_human_policy(policy, {361}, 0, "pass-only", 0)

    assert audit.index == 361
    assert audit.move == "pass"
    assert audit.interval_low == 0.0
    assert audit.interval_high == audit.positive_total == 2.5


def test_illegal_points_and_nonpositive_weights_are_ignored_without_argmax_fallback():
    policy = [0.0] * 362
    policy[0] = 1000.0  # Illegal, despite being the global argmax.
    policy[1] = -7.0
    policy[2] = -0.0
    policy[360] = 4.0

    audit = campaign.sample_human_policy(policy, [360, 2, 1], 7, "filtered", 3)

    assert audit.index == 360
    assert audit.move == (18, 0)
    assert audit.positive_total == 4.0
    assert audit.interval_low == 0.0
    assert audit.interval_high == 4.0
    assert audit.policy_sha256 == expected_policy_sha256(policy)


@pytest.mark.parametrize(
    "policy",
    [
        [0.0] * 361,
        [0.0] * 363,
        tuple([0.0] * 362),
        [False] + [0.0] * 361,
        ["0"] + [0.0] * 361,
        [float("nan")] + [0.0] * 361,
        [float("inf")] + [0.0] * 361,
        [float("-inf")] + [0.0] * 361,
        [10**1000] + [0.0] * 361,
    ],
)
def test_policy_shape_type_and_binary64_values_fail_closed(policy):
    with pytest.raises(ValueError):
        campaign.sample_human_policy(policy, [0], 0, "reservation", 0)


@pytest.mark.parametrize(
    ("policy", "legal_indices"),
    [
        ([0.0] * 362, []),
        ([-1.0] * 362, range(362)),
        ([1.0] + [0.0] * 361, [1]),
    ],
)
def test_zero_legal_positive_mass_fails_closed(policy, legal_indices):
    with pytest.raises(ValueError, match="positive"):
        campaign.sample_human_policy(policy, legal_indices, 0, "reservation", 0)


@pytest.mark.parametrize(
    "legal_indices",
    [
        [0, 0],
        [True],
        [-1],
        [362],
        [1.0],
        ["1"],
        {0: "not-a-set"},
        (index for index in [0]),
    ],
)
def test_invalid_legal_indices_fail_closed(legal_indices):
    policy = [1.0] + [0.0] * 361

    with pytest.raises(ValueError):
        campaign.sample_human_policy(policy, legal_indices, 0, "reservation", 0)


@pytest.mark.parametrize(
    ("seed", "reservation_id", "ply"),
    [
        (True, "reservation", 0),
        (-1, "reservation", 0),
        (2**64, "reservation", 0),
        (0, b"reservation", 0),
        (0, "", 0),
        (0, "a" * 65536, 0),
        (0, "\ud800", 0),
        (0, "reservation", True),
        (0, "reservation", -1),
        (0, "reservation", 2**32),
    ],
)
def test_uniform_seed_reservation_id_and_ply_boundaries_fail_closed(seed, reservation_id, ply):
    with pytest.raises(ValueError):
        campaign.derive_uniform(seed, reservation_id, ply)

    policy = [1.0] + [0.0] * 361
    with pytest.raises(ValueError):
        campaign.sample_human_policy(policy, [0], seed, reservation_id, ply)


def test_reservation_id_limit_is_measured_in_utf8_bytes():
    valid_id = "é" * 32767 + "a"
    invalid_id = valid_id + "a"

    assert campaign.derive_uniform(0, valid_id, 0) == expected_uniform(0, valid_id, 0)[0]
    with pytest.raises(ValueError):
        campaign.derive_uniform(0, invalid_id, 0)


@pytest.mark.parametrize(
    ("stage", "player_spec", "api_level", "profile"),
    [
        ("sampling_quasi_5d", "rank_5d@1", 25, "rank_5d"),
        ("sampling_quasi_6d", "rank_6d@1", 27, "rank_6d"),
        ("sampling_quasi_7d", "rank_7d@1", 29, "rank_7d"),
        ("sampling_quasi_8d", "rank_8d@1", 31, "rank_8d"),
        ("sampling_quasi_9d", "rank_9d@1", 32, "rank_9d"),
    ],
)
def test_sampling_runner_builds_exact_native_humansl_one_visit_queries(stage, player_spec, api_level, profile):
    request = campaign.GameRequest(stage, player_spec, api_level, 0, "B")
    player = runner.player_for_request(request)
    query = runner.build_player_query([], player)

    assert player.label == player_spec
    assert player.rung.mechanism == "humansl"
    assert player.rung.human_sl_profile == profile
    assert player.rung.max_visits == 1
    assert player.selection == "weighted"
    assert query["maxVisits"] == 1
    assert query["overrideSettings"]["humanSLProfile"] == profile
    assert "model" not in query["overrideSettings"]
    assert query["includePolicy"] is True


def test_sampling_move_uses_only_current_human_policy_and_attests_default_wrapper():
    identity = campaign._read_parent()
    default_model = identity["default_model"]
    wrapper = {
        "selected_model": default_model,
        "model_path": identity["models"][default_model]["model_path"],
        "model_sha256": identity["models"][default_model]["model_sha256"],
        "human_model_path": identity["models"][default_model]["human_model_path"],
        "human_model_sha256": identity["models"][default_model]["human_model_sha256"],
        "katago_version": identity["katago_version"],
    }
    policy = [0.0] * 362
    policy[0] = 1.0
    analysis = {
        "humanPolicy": policy,
        "policy": [0.0] * 361 + [1000.0],
        "moveInfos": [{"move": "pass", "order": 0}],
        "rootInfo": {"visits": 999},
        "_wrapper": wrapper,
    }
    request = campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")

    selected, audit = runner.select_sampling_move(
        analysis,
        request=request,
        identity_snapshot=identity,
        history=[],
        seed=1,
        reservation_id="sampling:1",
    )

    assert selected == runner.colrow_to_golaxy(0, 18, 19)
    assert audit["ply"] == 0
    assert audit["final_move"] == selected
    assert audit["policy_sha256"] == expected_policy_sha256(policy)
    assert audit["algorithm"] == campaign.SAMPLING_ALGORITHM


@pytest.mark.parametrize(
    "mutation",
    [
        lambda analysis: analysis.pop("humanPolicy"),
        lambda analysis: analysis.update(humanPolicy=[0.0] * 362),
        lambda analysis: analysis["_wrapper"].update(human_model_sha256="wrong"),
        lambda analysis: analysis["_wrapper"].update(selected_model="b18"),
    ],
)
def test_sampling_move_fails_closed_without_policy_or_exact_identity(mutation):
    identity = campaign._read_parent()
    default_model = identity["default_model"]
    analysis = {
        "humanPolicy": [1.0] + [0.0] * 361,
        "_wrapper": {
            "selected_model": default_model,
            "model_path": identity["models"][default_model]["model_path"],
            "model_sha256": identity["models"][default_model]["model_sha256"],
            "human_model_path": identity["models"][default_model]["human_model_path"],
            "human_model_sha256": identity["models"][default_model]["human_model_sha256"],
            "katago_version": identity["katago_version"],
        },
    }
    mutation(analysis)
    request = campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")

    with pytest.raises(ValueError, match="humanPolicy|identity|wrapper|model"):
        runner.select_sampling_move(
            analysis,
            request=request,
            identity_snapshot=identity,
            history=[],
            seed=1,
            reservation_id="sampling:1",
        )


def test_sampling_move_filters_occupied_points_and_hashes_canonical_sgf_history():
    identity = campaign._read_parent()
    default_model = identity["default_model"]
    wrapper = {
        "selected_model": default_model,
        "model_path": identity["models"][default_model]["model_path"],
        "model_sha256": identity["models"][default_model]["model_sha256"],
        "human_model_path": identity["models"][default_model]["human_model_path"],
        "human_model_sha256": identity["models"][default_model]["human_model_sha256"],
        "katago_version": identity["katago_version"],
    }
    occupied = runner.colrow_to_golaxy(0, 18, 19)
    policy = [0.0] * 362
    policy[0] = 1000.0
    policy[1] = 2.0
    request = campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")

    selected, audit = runner.select_sampling_move(
        {"humanPolicy": policy, "_wrapper": wrapper},
        request=request,
        identity_snapshot=identity,
        history=[occupied],
        seed=9,
        reservation_id="sampling:1",
    )

    canonical_history = b'[["B","aa"]]'
    assert runner.canonical_sgf_history([occupied]) == canonical_history
    assert selected == runner.colrow_to_golaxy(1, 18, 19)
    assert audit["position_sha256"] == hashlib.sha256(canonical_history).hexdigest()
    assert audit["positive_total"] == 2.0
    assert audit["interval_low"] == 0.0
    assert audit["interval_high"] == 2.0
    assert audit["final_move"] == selected


@pytest.mark.asyncio
async def test_analyze_sampling_move_uses_exact_query_and_appends_one_audit_from_that_response():
    identity = campaign._read_parent()
    default_model = identity["default_model"]
    wrapper = {
        "selected_model": default_model,
        "model_path": identity["models"][default_model]["model_path"],
        "model_sha256": identity["models"][default_model]["model_sha256"],
        "human_model_path": identity["models"][default_model]["human_model_path"],
        "human_model_sha256": identity["models"][default_model]["human_model_sha256"],
        "katago_version": identity["katago_version"],
    }
    policy = [0.0] * 362
    policy[361] = 1.0
    seen = []

    async def handler(request):
        query = json.loads(request.content)
        seen.append(query)
        return httpx.Response(
            200,
            json={
                "humanPolicy": policy,
                "policy": [1000.0] + [0.0] * 361,
                "moveInfos": [{"move": "A1", "order": 0}],
                "_wrapper": wrapper,
            },
        )

    request = campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")
    audits = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await runner.analyze_sampling_move(
            client,
            runner.BASE_URL,
            [],
            request=request,
            identity_snapshot=identity,
            seed=5,
            reservation_id="sampling:1",
            audits=audits,
        )

    assert move == "pass"
    assert len(audits) == 1
    assert audits[0]["final_move"] == "pass"
    assert seen[0]["maxVisits"] == 1
    assert seen[0]["overrideSettings"]["humanSLProfile"] == "rank_5d"
    assert "model" not in seen[0]["overrideSettings"]


def test_sampling_runner_resolves_exact_real_golaxy_wire_levels():
    expected_wire_levels = {
        "sampling_quasi_5d": 2000,
        "sampling_quasi_6d": 2200,
        "sampling_quasi_7d": 2400,
        "sampling_quasi_8d": 2600,
        "sampling_quasi_9d": 2900,
    }
    for stage, player, frozen_level in campaign.STAGES:
        request = campaign.GameRequest(stage, player, frozen_level, 0, "B")
        assert runner.opponent_for_request(request).golaxy_api_level == expected_wire_levels[stage]


@pytest.mark.parametrize(
    ("black_score", "second_score", "settled", "end_reason", "expected_conclusive", "expected_result"),
    [
        (2.0, 2.999, True, "move_cap", True, "our_win"),
        (2.0, 3.0, True, "move_cap", False, "inconclusive_unstable"),
        (2.0, 2.5, False, "move_cap", False, "inconclusive_unstable"),
        (0.0, 0.0, True, "move_cap", False, "inconclusive_score"),
        (None, None, False, "golaxy_terminal", False, "inconclusive_terminal"),
        (None, None, False, "golaxy_resign", True, "our_win"),
    ],
)
def test_sampling_adjudication_boundaries(
    black_score,
    second_score,
    settled,
    end_reason,
    expected_conclusive,
    expected_result,
):
    initial = runner.GameOutcome(
        "B",
        "our_win" if end_reason == "golaxy_resign" or black_score is not None else "inconclusive_terminal",
        end_reason == "golaxy_resign" or (black_score is not None and black_score > 0),
        400,
        black_score,
        end_reason == "golaxy_resign" or black_score is not None,
        end_reason,
    )

    outcome = runner.stabilize_outcome(initial, second_score=second_score, second_settled=settled)

    assert outcome.conclusive is expected_conclusive
    assert outcome.result == expected_result


def test_verified_golaxy_resignation_is_the_only_outcome_that_skips_stability_probe():
    resign = runner.GameOutcome("W", "our_win", True, 31, None, True, "golaxy_resign")
    ordinary = runner.GameOutcome("W", "our_win", True, 31, -2.0, True, "golaxy_pass")

    assert runner.requires_stability_probe(resign) is False
    assert runner.requires_stability_probe(ordinary) is True


def test_sampling_result_persists_strict_per_move_audits(tmp_path):
    path = tmp_path / "audited.jsonl"
    campaign.initialize_campaign(path, "audited", seed=17)
    request = campaign.replay_campaign(path)
    campaign.append_reservation(path, 1, request)
    audit = runner_audit(17, "audited:1")

    campaign.append_result(path, 1, "win", move_audits=[audit])

    loaded = campaign.load_campaign(path)
    assert loaded.records[-1]["move_audits"] == [audit]
    assert json.loads(json.dumps(loaded.records[-1], allow_nan=False))["move_audits"] == [audit]


@pytest.mark.parametrize(
    "bad_audits",
    [
        None,
        {},
        [{"ply": 0}],
        [
            {
                "ply": 0,
                "position_sha256": "a" * 64,
                "algorithm": campaign.SAMPLING_ALGORITHM,
                "u": f"1/{2**64}",
                "u_raw": 1,
                "u_denominator": 2**64,
                "index": 361,
                "move": "pass",
                "policy_sha256": "b" * 64,
                "positive_total": float("nan"),
                "interval_low": 0.0,
                "interval_high": 1.0,
                "final_move": "pass",
            }
        ],
    ],
)
def test_sampling_result_rejects_missing_or_malformed_move_audits(tmp_path, bad_audits):
    path = tmp_path / "bad-audit.jsonl"
    campaign.initialize_campaign(path, "bad-audit", seed=19)
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))

    with pytest.raises(ValueError, match="audit"):
        campaign.append_result(path, 1, "win", move_audits=bad_audits)

    assert campaign.campaign_summary(path).unknown_charged_attempts == (1,)


def test_sampling_result_requires_move_audits_and_loader_rejects_the_legacy_shape(tmp_path):
    path = tmp_path / "missing-audits.jsonl"
    campaign.initialize_campaign(path, "missing-audits", seed=20)
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))

    with pytest.raises(TypeError, match="move_audits"):
        campaign.append_result(path, 1, "win")

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    reservation = rows[-1]
    rows.append(
        {
            "type": "result",
            "sequence": 2,
            "attempt_id": 1,
            "origin_id": "missing-audits:1",
            "stage": reservation["stage"],
            "player": reservation["player"],
            "golaxy_api_level": reservation["golaxy_api_level"],
            "slot": reservation["slot"],
            "color": reservation["color"],
            "outcome": "win",
            "conclusive": True,
        }
    )
    write_canonical_rows(path, rows)
    with pytest.raises(ValueError, match="audit|fields"):
        campaign.campaign_summary(path)


def test_sampling_result_allows_empty_audits_when_golaxy_stops_before_first_humansl_move(tmp_path):
    path = tmp_path / "no-local-move.jsonl"
    campaign.initialize_campaign(path, "no-local-move", seed=21)
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))

    campaign.append_result(path, 1, "inconclusive", move_audits=[])

    loaded = campaign.load_campaign(path)
    assert loaded.records[-1]["move_audits"] == []
    assert loaded.action == campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")


@pytest.mark.parametrize("tamper", ["random", "parity", "final_move", "interval"])
def test_loader_recomputes_sampling_audit_context_and_rejects_tampering(tmp_path, tamper):
    path = tmp_path / f"audit-{tamper}.jsonl"
    campaign.initialize_campaign(path, "audit-context", seed=61)
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))
    audit = runner_audit(61, "audit-context:1")
    campaign.append_result(path, 1, "win", move_audits=[audit])
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    stored = rows[-1]["move_audits"][0]
    if tamper == "random":
        stored["u_raw"] = (stored["u_raw"] + 1) % 2**64
        stored["u"] = f"{stored['u_raw']}/{2**64}"
    elif tamper == "parity":
        stored["ply"] = 1
    elif tamper == "final_move":
        stored.update(index=0, move=[0, 18], final_move=5)
    else:
        target = stored["u_raw"] / 2**64
        if target < 0.5:
            stored.update(interval_low=0.75, interval_high=1.0)
        else:
            stored.update(interval_low=0.0, interval_high=0.25)
    write_canonical_rows(path, rows)

    with pytest.raises(ValueError, match="audit|random|ply|color|interval|mapping"):
        campaign.campaign_summary(path)


def test_stopped_row_persists_and_replays_sampling_audits(tmp_path):
    path = tmp_path / "stopped-audits.jsonl"
    campaign.initialize_campaign(path, "stopped-audits", seed=67)
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))
    audit = runner_audit(67, "stopped-audits:1")

    campaign.append_stop(path, "disconnect", attempt_id=1, move_audits=[audit])

    loaded = campaign.campaign_summary(path)
    assert loaded.stopped is True
    assert loaded.records[-1]["move_audits"] == [audit]


def runner_audit(seed=0, reservation_id="sampling:1", ply=0):
    u, _digest = expected_uniform(seed, reservation_id, ply)
    u_raw = int(u * 2**64)
    return {
        "ply": ply,
        "position_sha256": "a" * 64,
        "algorithm": campaign.SAMPLING_ALGORITHM,
        "u": f"{u_raw}/{2**64}",
        "u_raw": u_raw,
        "u_denominator": 2**64,
        "index": 361,
        "move": "pass",
        "policy_sha256": "b" * 64,
        "positive_total": 1.0,
        "interval_low": 0.0,
        "interval_high": 1.0,
        "final_move": "pass",
    }


@pytest.mark.asyncio
async def test_serial_sampling_loop_replenishes_inconclusive_same_color_and_cools_before_reservation(tmp_path):
    path = tmp_path / "serial.jsonl"
    campaign.initialize_campaign(path, "serial", seed=23)
    calls = []
    sleeps = []
    outcomes = iter(
        [
            runner.GameOutcome("B", "inconclusive_unstable", False, 10, 1.0, False, "move_cap"),
            runner.GameOutcome("B", "our_win", True, 11, 2.0, True, "move_cap"),
        ]
    )

    async def play(request, _header, reservation_id):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert rows[-1]["type"] == "reservation"
        assert reservation_id == f"serial:{rows[-1]['attempt_id']}"
        calls.append((request.slot, request.color))
        if len(calls) == 3:
            raise RuntimeError("Golaxy 7002")
        return runner.PlayedSamplingGame(next(outcomes), (runner_audit(_header["seed"], reservation_id),))

    async def sleep(seconds):
        sleeps.append(seconds)

    with pytest.raises(runner.CampaignStopped, match="7002"):
        await runner.execute_serial_campaign(path, play_game=play, sleep=sleep, emit=lambda _event: None)

    assert calls == [(0, "B"), (0, "B"), (1, "W")]
    assert sleeps == [5.0, 5.0]
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["type"] for row in rows[-3:]] == ["result", "reservation", "stopped"]
    assert rows[2]["move_audits"] == [runner_audit(23, "serial:1")]


@pytest.mark.asyncio
async def test_reservation_write_failure_prevents_game_request(tmp_path, monkeypatch):
    path = tmp_path / "reservation-failure.jsonl"
    campaign.initialize_campaign(path, "reservation-failure", seed=29)
    played = False

    def fail_reservation(*_args, **_kwargs):
        raise OSError("reservation fsync failed")

    async def play(*_args):
        nonlocal played
        played = True

    monkeypatch.setattr(runner.golaxy_sampling_campaign, "append_reservation", fail_reservation)
    with pytest.raises(OSError, match="reservation fsync failed"):
        await runner.execute_serial_campaign(path, play_game=play, emit=lambda _event: None)

    assert played is False
    assert campaign.campaign_summary(path).records == ()


@pytest.mark.asyncio
async def test_result_write_failure_exits_with_open_reservation_and_no_cooldown(tmp_path, monkeypatch):
    path = tmp_path / "result-failure.jsonl"
    campaign.initialize_campaign(path, "result-failure", seed=31)
    plays = 0
    sleeps = []

    async def play(*_args):
        nonlocal plays
        plays += 1
        return runner.PlayedSamplingGame(
            runner.GameOutcome("B", "our_win", True, 1, 2.0, True, "golaxy_resign"),
            (runner_audit(),),
        )

    def fail_result(*_args, **_kwargs):
        raise OSError("result fsync failed")

    monkeypatch.setattr(runner.golaxy_sampling_campaign, "append_result", fail_result)
    with pytest.raises(OSError, match="result fsync failed"):
        await runner.execute_serial_campaign(path, play_game=play, sleep=sleeps.append, emit=lambda _event: None)

    assert plays == 1
    assert sleeps == []
    assert campaign.campaign_summary(path).unknown_charged_attempts == (1,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("Golaxy API 7002"),
        RuntimeError("Golaxy API 429"),
        RuntimeError("invalid response"),
        httpx.ConnectError("disconnect"),
        httpx.TimeoutException("timeout"),
        ValueError("invalid humanPolicy"),
        ValueError("identity mismatch"),
    ],
)
async def test_any_game_failure_stops_once_without_retry_or_post_error_cooldown(tmp_path, failure):
    path = tmp_path / "stop-once.jsonl"
    campaign.initialize_campaign(path, "stop-once", seed=37)
    plays = 0
    sleeps = []

    async def play(*_args):
        nonlocal plays
        plays += 1
        raise failure

    with pytest.raises(runner.CampaignStopped):
        await runner.execute_serial_campaign(path, play_game=play, sleep=sleeps.append, emit=lambda _event: None)

    assert plays == 1
    assert sleeps == []
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["type"] for row in rows[-2:]] == ["reservation", "stopped"]


@pytest.mark.asyncio
async def test_stop_write_failure_still_exits_without_later_request(tmp_path, monkeypatch):
    path = tmp_path / "stop-write-failure.jsonl"
    campaign.initialize_campaign(path, "stop-write-failure", seed=41)
    plays = 0

    async def play(*_args):
        nonlocal plays
        plays += 1
        raise RuntimeError("remote failure")

    def fail_stop(*_args, **_kwargs):
        raise OSError("stop fsync failed")

    monkeypatch.setattr(runner.golaxy_sampling_campaign, "append_stop", fail_stop)
    with pytest.raises(runner.CampaignStopped, match="stop fsync failed"):
        await runner.execute_serial_campaign(path, play_game=play, emit=lambda _event: None)

    assert plays == 1
    assert campaign.campaign_summary(path).unknown_charged_attempts == (1,)


@pytest.mark.asyncio
async def test_serial_runner_persists_audits_carried_by_a_failed_game(tmp_path):
    path = tmp_path / "failed-game-audits.jsonl"
    campaign.initialize_campaign(path, "failed-game-audits", seed=71)
    audit = runner_audit(71, "failed-game-audits:1")

    async def play(*_args):
        raise runner.SamplingGameStopped("disconnect after sampled move", (audit,))

    with pytest.raises(runner.CampaignStopped, match="disconnect"):
        await runner.execute_serial_campaign(path, play_game=play, emit=lambda _event: None)

    loaded = campaign.campaign_summary(path)
    assert loaded.records[-1]["type"] == "stopped"
    assert loaded.records[-1]["move_audits"] == [audit]


@pytest.mark.asyncio
async def test_play_sampling_game_uses_audited_policy_golaxy_transport_and_200_800_referees(monkeypatch):
    request = campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "W")
    identity = campaign._read_parent()
    header = {"campaign_id": "play", "seed": 43, "identity_snapshot": identity}
    calls = []

    async def analyze(*_args, audits, **_kwargs):
        audits.append(runner_audit(1))
        calls.append("our")
        return 7

    async def golaxy(*_args, rung, **_kwargs):
        calls.append(("golaxy", rung.golaxy_api_level))
        return 8

    async def adjudicate(*_args, visits, **_kwargs):
        calls.append(("referee", visits))
        return (2.5 if visits == 200 else 3.4), True

    async def play_one_game(*, our_move, golaxy_move, adjudicate, our_color, board_size, move_cap):
        assert our_color == "W"
        assert board_size == 19
        assert move_cap == 400
        assert await golaxy_move([]) == 8
        assert await our_move([8]) == 7
        score, settled = await adjudicate([8, 7])
        assert (score, settled) == (2.5, True)
        return runner.GameOutcome("W", "our_loss", False, 2, score, True, "move_cap")

    monkeypatch.setattr(runner, "analyze_sampling_move", analyze)
    monkeypatch.setattr(runner.adapters, "golaxy_move", golaxy)
    monkeypatch.setattr(runner.adapters, "adjudicate", adjudicate)
    monkeypatch.setattr(runner, "play_one_game", play_one_game)

    played = await runner.play_sampling_game(
        local_client=object(),
        golaxy_client=object(),
        token="token",
        smoke={"pass_code": -1, "resign_code": -3},
        request=request,
        header=header,
        reservation_id="play:1",
    )

    assert played.outcome.conclusive is True
    assert played.outcome.result == "our_loss"
    assert played.move_audits == (runner_audit(1),)
    assert calls == [("golaxy", 2000), "our", ("referee", 200), ("referee", 800)]


@pytest.mark.asyncio
async def test_play_sampling_game_keeps_unverified_terminal_inconclusive_and_skips_second_probe(monkeypatch):
    request = campaign.GameRequest("sampling_quasi_9d", "rank_9d@1", 32, 0, "B")
    identity = campaign._read_parent()
    header = {"campaign_id": "terminal", "seed": 47, "identity_snapshot": identity}
    referee_calls = []

    async def play_one_game(**_kwargs):
        return runner.GameOutcome("B", "inconclusive_terminal", False, 3, None, False, "golaxy_terminal")

    async def adjudicate(*_args, **_kwargs):
        referee_calls.append(True)
        return 1.0, True

    monkeypatch.setattr(runner, "play_one_game", play_one_game)
    monkeypatch.setattr(runner.adapters, "adjudicate", adjudicate)

    played = await runner.play_sampling_game(
        local_client=object(),
        golaxy_client=object(),
        token="token",
        smoke={"pass_code": -1, "resign_code": -3},
        request=request,
        header=header,
        reservation_id="terminal:1",
    )

    assert played.outcome.result == "inconclusive_terminal"
    assert played.outcome.conclusive is False
    assert referee_calls == []


@pytest.mark.asyncio
async def test_play_sampling_game_carries_completed_move_audits_when_later_transport_fails(monkeypatch):
    request = campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")
    identity = campaign._read_parent()
    header = {"campaign_id": "carry", "seed": 73, "identity_snapshot": identity}
    audit = runner_audit(73, "carry:1")

    async def analyze(*_args, audits, **_kwargs):
        audits.append(audit)
        return 0

    async def play_one_game(*, our_move, **_kwargs):
        assert await our_move([]) == 0
        raise httpx.ConnectError("disconnect after local move")

    monkeypatch.setattr(runner, "analyze_sampling_move", analyze)
    monkeypatch.setattr(runner, "play_one_game", play_one_game)

    with pytest.raises(runner.SamplingGameStopped, match="disconnect") as stopped:
        await runner.play_sampling_game(
            local_client=object(),
            golaxy_client=object(),
            token="token",
            smoke={"pass_code": -1, "resign_code": -3},
            request=request,
            header=header,
            reservation_id="carry:1",
        )

    assert stopped.value.move_audits == (audit,)


def test_sampling_cli_requires_the_exact_frozen_parent_pair(tmp_path):
    parser = runner.build_parser()
    out = tmp_path / "sampling.jsonl"
    exact = parser.parse_args(
        [
            "--out",
            str(out),
            "--parent",
            str(campaign.PARENT_PATH),
            "--parent-sha256",
            campaign.PARENT_SHA256,
        ]
    )
    assert runner.validate_args(exact) == "live"

    for argv in (
        ["--out", str(out)],
        ["--out", str(out), "--parent", str(campaign.PARENT_PATH)],
        [
            "--out",
            str(out),
            "--parent",
            str(tmp_path / "other.jsonl"),
            "--parent-sha256",
            campaign.PARENT_SHA256,
        ],
        [
            "--out",
            str(out),
            "--parent",
            str(campaign.PARENT_PATH),
            "--parent-sha256",
            "0" * 64,
        ],
    ):
        with pytest.raises(ValueError, match="parent|SHA|fixed|exact"):
            runner.validate_args(parser.parse_args(argv))


def test_sampling_summary_is_read_only_and_never_constructs_network_client(tmp_path, monkeypatch):
    path = tmp_path / "summary.jsonl"
    campaign.initialize_campaign(path, "summary", seed=53)
    before = path.read_bytes()
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda *args, **kwargs: pytest.fail("summary opened network"))

    args = runner.build_parser().parse_args(["--out", str(path), "--summary"])
    assert runner.validate_args(args) == "summary"
    summary = runner.summarize_campaign(path)

    assert summary["campaign_id"] == "summary"
    assert summary["next_action"]["stage"] == "sampling_quasi_5d"
    assert path.read_bytes() == before


def test_summary_rejects_live_parent_arguments(tmp_path):
    args = runner.build_parser().parse_args(
        [
            "--out",
            str(tmp_path / "summary.jsonl"),
            "--summary",
            "--parent",
            str(campaign.PARENT_PATH),
            "--parent-sha256",
            campaign.PARENT_SHA256,
        ]
    )
    with pytest.raises(ValueError, match="summary"):
        runner.validate_args(args)


def test_sampling_direct_cli_pins_current_repo_before_poisoned_pythonpath(tmp_path):
    poison = tmp_path / "poison"
    fake_katrain = poison / "katrain"
    fake_katrain.mkdir(parents=True)
    (fake_katrain / "__init__.py").write_text("raise RuntimeError('POISON_KATRAIN')\n", encoding="utf-8")
    script = CALIBRATION / "run_golaxy_sampling_campaign.py"
    python = Path(__file__).resolve().parents[2] / ".venv/bin/python"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(poison)
    env.pop("KIVY_NO_ARGS", None)

    completed = subprocess.run(
        [str(python), str(script), "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--parent-sha256" in completed.stdout
    assert "Kivy Usage" not in completed.stdout
    assert "POISON_KATRAIN" not in completed.stderr


@pytest.mark.asyncio
async def test_run_live_validates_parent_before_token_smoke_or_clients(tmp_path, monkeypatch):
    out = tmp_path / "bad-parent.jsonl"
    monkeypatch.setattr(runner.golaxy_sampling_campaign, "PARENT_SHA256", "0" * 64)
    args = runner.build_parser().parse_args(
        [
            "--out",
            str(out),
            "--parent",
            str(campaign.PARENT_PATH),
            "--parent-sha256",
            "0" * 64,
        ]
    )
    touched = []
    monkeypatch.setattr(runner.run_golaxy_9d_alignment, "load_token", lambda *_args: touched.append("token"))
    monkeypatch.setattr(
        runner.run_golaxy_9d_alignment,
        "load_verified_smoke_codes",
        lambda *_args: touched.append("smoke"),
    )
    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda **_kwargs: touched.append("client"))

    with pytest.raises(ValueError, match="parent|SHA"):
        await runner._run_live(args)

    assert touched == []
    assert not out.exists()


@pytest.mark.asyncio
async def test_run_live_persists_local_preflight_failure_after_reservation(tmp_path, monkeypatch):
    out = tmp_path / "preflight-stop.jsonl"
    args = runner.build_parser().parse_args(
        [
            "--out",
            str(out),
            "--parent",
            str(campaign.PARENT_PATH),
            "--parent-sha256",
            campaign.PARENT_SHA256,
        ]
    )
    identity = campaign._read_parent()
    clients = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, **_kwargs):
            return httpx.Response(200, json=identity, request=httpx.Request("GET", url))

    def client_factory(**kwargs):
        clients.append(kwargs)
        return Client()

    async def fail_referees(*_args):
        raise RuntimeError("b28 probe failed")

    monkeypatch.setattr(runner.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(runner.run_golaxy_alignment_campaign, "build_identity_snapshot", lambda health: health)
    monkeypatch.setattr(runner.run_golaxy_alignment_campaign, "preflight_referees", fail_referees)
    monkeypatch.setattr(runner.run_golaxy_9d_alignment, "load_token", lambda *_args: "token")
    monkeypatch.setattr(
        runner.run_golaxy_9d_alignment,
        "load_verified_smoke_codes",
        lambda *_args: {"pass_code": -1, "resign_code": -3},
    )
    monkeypatch.setattr(runner, "play_sampling_game", lambda **_kwargs: pytest.fail("game reached Golaxy"))

    with pytest.raises(runner.CampaignStopped, match="b28 probe failed"):
        await runner._run_live(args)

    loaded = campaign.campaign_summary(out)
    assert loaded.stopped is True
    assert [row["type"] for row in loaded.records] == ["reservation", "stopped"]
    assert len(clients) == 2
    assert all(kwargs == {"follow_redirects": False, "trust_env": False} for kwargs in clients)
