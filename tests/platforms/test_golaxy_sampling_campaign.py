import dataclasses
import hashlib
import importlib
import math
import struct
import sys
from fractions import Fraction
from pathlib import Path

import pytest


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

campaign = importlib.import_module("golaxy_sampling_campaign")


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
    assert audit.u == expected_u == Fraction(0xF9BAC4199EF8C424, 2**64)
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
    assert audit.u == expected_u
    assert audit.index == 361


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
