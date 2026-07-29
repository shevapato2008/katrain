import asyncio
import dataclasses
import hashlib
import importlib
import json
import os
import stat
import sys
import typing
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

import golaxy_alignment_campaign as campaign


runner = importlib.import_module("run_golaxy_alignment_campaign")


def campaign_health():
    return {
        "status": "ok",
        "capability_schema": 1,
        "katago_version": "KataGo v1.16.3",
        "default_model": "b28",
        "models": {
            alias: {
                "running": True,
                "model_path": f"/models/{alias}.bin.gz",
                "model_sha256": f"{alias}-sha",
                "model_sha256_verified": True,
                "has_human_model": True,
                "human_model_path": "/models/humanv0.bin.gz",
                "human_model_sha256": "humanv0-sha",
                "human_model_sha256_verified": True,
            }
            for alias in ("b18", "b28")
        },
    }


def campaign_wrapper(alias="b18", **changes):
    wrapper = {
        "selected_model": alias,
        "model_path": f"/models/{alias}.bin.gz",
        "model_sha256": f"{alias}-sha",
        "human_model_path": "/models/humanv0.bin.gz",
        "human_model_sha256": "humanv0-sha",
        "katago_version": "KataGo v1.16.3",
    }
    wrapper.update(changes)
    return wrapper


@pytest.fixture
def captured_b18_one_visit_response():
    """Shape captured from the local b18 one-visit probe; identity values are test-frozen."""
    policy = [0.0] * 362
    policy[60] = 0.73
    policy[361] = 0.12
    return {
        "id": "campaign-b18-one-visit-probe",
        "rootInfo": {"visits": 1, "scoreLead": 0.18},
        "moveInfos": [],
        "policy": policy,
        "_wrapper": campaign_wrapper(),
    }


@pytest.mark.parametrize(
    ("stage", "name", "api_level"),
    [
        ("quasi_5d", "准5段", 2000),
        ("quasi_6d", "准6段", 2200),
        ("quasi_7d", "准7段", 2400),
        ("quasi_8d", "准8段", 2600),
        ("quasi_9d", "准9段", 2900),
        ("seven_d", "7段", 2500),
        ("one_star_b18_1", "星阵1星", 3100),
    ],
)
def test_campaign_opponents_are_exact_validated_ladder_descriptors(stage, name, api_level):
    rung = runner.opponent_for_stage(stage)

    assert isinstance(rung, runner.LadderRung)
    assert (rung.golaxy_level_name, rung.golaxy_api_level) == (name, api_level)
    assert runner.resolve_opponent(rung) is rung


def test_campaign_lower_profiles_are_frozen_one_rank_below():
    assert runner.QUASI_PROFILES == {
        "quasi_5d": "rank_4d",
        "quasi_6d": "rank_5d",
        "quasi_7d": "rank_6d",
        "quasi_8d": "rank_7d",
        "quasi_9d": "rank_8d",
    }


def test_identity_snapshot_is_serializable_and_freezes_default_b18_and_attached_humanv0():
    snapshot = runner.build_identity_snapshot(campaign_health())

    assert json.loads(json.dumps(snapshot)) == snapshot
    assert snapshot == {
        "status": "ok",
        "capability_schema": 1,
        "katago_version": "KataGo v1.16.3",
        "default_model": "b28",
        "models": {
            "b28": {
                "running": True,
                "model_path": "/models/b28.bin.gz",
                "model_sha256": "b28-sha",
                "model_sha256_verified": True,
                "human_model": "humanv0",
                "human_model_path": "/models/humanv0.bin.gz",
                "human_model_sha256": "humanv0-sha",
                "human_model_sha256_verified": True,
            },
            "b18": {
                "running": True,
                "model_path": "/models/b18.bin.gz",
                "model_sha256": "b18-sha",
                "model_sha256_verified": True,
                "human_model": "humanv0",
                "human_model_path": "/models/humanv0.bin.gz",
                "human_model_sha256": "humanv0-sha",
                "human_model_sha256_verified": True,
            },
        },
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda health: health.update(status="starting"),
        lambda health: health.update(capability_schema=2),
        lambda health: health["models"]["b18"].update(running=False),
        lambda health: health["models"]["b18"].update(model_sha256_verified=False),
        lambda health: health["models"]["b28"].update(human_model_sha256_verified=False),
        lambda health: health["models"]["b18"].update(human_model_path=""),
        lambda health: health.update(katago_version=""),
    ],
)
def test_identity_snapshot_rejects_unhealthy_or_unverified_process_identity(mutate):
    health = campaign_health()
    mutate(health)
    with pytest.raises(ValueError, match="status|schema|running|verified|identity|human|katago"):
        runner.build_identity_snapshot(health)


def test_native_one_second_player_omits_model_and_uses_human_policy_argmax_only():
    player = runner.make_campaign_player("rank_4d@1s")
    query = runner.build_player_query([], player)
    human_policy = [0.0] * 362
    human_policy[0] = 0.8
    analysis = {
        "humanPolicy": human_policy,
        "moveInfos": [{"move": "Q16", "order": 0}],
        "_wrapper": {"selected_model": "untrusted"},
    }

    assert player.selection == "argmax_human"
    assert query == {
        "rules": "chinese",
        "komi": 7.5,
        "boardXSize": 19,
        "boardYSize": 19,
        "moves": [],
        "analyzeTurns": [0],
        "maxVisits": 1,
        "includePolicy": True,
        "includeOwnership": False,
        "overrideSettings": {
            "reportAnalysisWinratesAs": "BLACK",
            "humanSLProfile": "rank_4d",
            "ignorePreRootHistory": False,
            "wideRootNoise": 0.04,
        },
    }
    assert runner.select_player_move(analysis, player, runner.build_identity_snapshot(campaign_health())) == (0, 18)


@pytest.mark.parametrize("analysis", [{}, {"humanPolicy": []}, {"humanPolicy": [0.0] * 361 + [float("nan")]}])
def test_native_one_second_requires_valid_human_policy_without_requiring_wrapper(analysis):
    player = runner.make_campaign_player("rank_8d@1s")
    with pytest.raises(runner.LadderMoveError, match="humanPolicy"):
        runner.select_player_move(analysis, player, runner.build_identity_snapshot(campaign_health()))


def test_native_one_second_rejects_boolean_in_human_policy():
    player = runner.make_campaign_player("rank_8d@1s")
    human_policy = [0.0] * 362
    human_policy[0] = 0.8
    human_policy[1] = True

    with pytest.raises(runner.LadderMoveError, match="humanPolicy"):
        runner.select_player_move(
            {"humanPolicy": human_policy}, player, runner.build_identity_snapshot(campaign_health())
        )


@pytest.mark.parametrize("visits", [4, 8, 16, 32, 64])
def test_humansl_search_query_routes_b18_with_profile_and_full_canonical_pikl(visits):
    player = runner.make_campaign_player(f"rank_6d@{visits}")
    query = runner.build_player_query([], player)

    assert player.selection == "search"
    assert query["maxVisits"] == visits
    assert query["overrideSettings"] == {
        "reportAnalysisWinratesAs": "BLACK",
        "humanSLProfile": "rank_6d",
        "ignorePreRootHistory": False,
        **runner.HUMANSL_PIKL_BASELINE,
        "wideRootNoise": 0.04,
        "model": "b18",
    }


@pytest.mark.parametrize("wrapper", [None, campaign_wrapper("b28")])
def test_humansl_search_fails_closed_without_exact_b18_response_attestation(wrapper):
    player = runner.make_campaign_player("rank_6d@4")
    analysis = {"moveInfos": [{"move": "Q16", "order": 0}], "_wrapper": wrapper}

    with pytest.raises(runner.LadderMoveError, match="attestation|selected_model"):
        runner.select_player_move(analysis, player, runner.build_identity_snapshot(campaign_health()))


def test_humansl_search_validates_frozen_b18_and_humanv0_identity():
    player = runner.make_campaign_player("rank_6d@4")
    analysis = {"moveInfos": [{"move": "Q16", "order": 0}], "_wrapper": campaign_wrapper()}
    snapshot = runner.build_identity_snapshot(campaign_health())

    assert runner.select_player_move(analysis, player, snapshot) == (15, 15)
    for drift in ("model_path", "model_sha256", "human_model_path", "human_model_sha256", "katago_version"):
        bad = {"moveInfos": analysis["moveInfos"], "_wrapper": campaign_wrapper(**{drift: "drifted"})}
        with pytest.raises(runner.LadderMoveError, match=drift):
            runner.select_player_move(bad, player, snapshot)


def test_pure_b18_one_visit_is_direct_search_without_humansl_controls():
    player = runner.make_campaign_player("b18@1")
    query = runner.build_player_query([], player)

    assert (player.rung.net, player.rung.mechanism, player.rung.max_visits, player.selection) == (
        "b18",
        "net_search",
        1,
        "policy_argmax",
    )
    assert query["maxVisits"] == 1
    assert query["overrideSettings"] == {
        "reportAnalysisWinratesAs": "BLACK",
        "wideRootNoise": 0.04,
        "model": "b18",
    }
    assert not any(key.startswith("humanSL") for key in query["overrideSettings"])


@pytest.mark.parametrize("wrapper", [None, campaign_wrapper("b28")])
def test_pure_b18_fails_closed_on_missing_or_b28_wrapper(wrapper):
    player = runner.make_campaign_player("b18@1")
    analysis = {"moveInfos": [{"move": "Q16", "order": 0}], "_wrapper": wrapper}
    with pytest.raises(runner.LadderMoveError, match="attestation|selected_model"):
        runner.select_player_move(analysis, player, runner.build_identity_snapshot(campaign_health()))


def test_pure_b18_uses_captured_native_policy_argmax_with_empty_move_infos(captured_b18_one_visit_response):
    player = runner.make_campaign_player("b18@1")
    snapshot = runner.build_identity_snapshot(campaign_health())

    assert runner.select_player_move(captured_b18_one_visit_response, player, snapshot) == (3, 15)


def test_pure_b18_rejects_nonempty_move_infos_or_invalid_native_policy(captured_b18_one_visit_response):
    player = runner.make_campaign_player("b18@1")
    snapshot = runner.build_identity_snapshot(campaign_health())
    nonempty = dict(captured_b18_one_visit_response, moveInfos=[{"move": "D4", "order": 0}])
    missing = dict(captured_b18_one_visit_response)
    missing.pop("policy")

    with pytest.raises(runner.LadderMoveError, match="empty moveInfos"):
        runner.select_player_move(nonempty, player, snapshot)
    with pytest.raises(runner.LadderMoveError, match="policy"):
        runner.select_player_move(missing, player, snapshot)


def test_pure_b18_rejects_policy_when_root_visits_are_not_exactly_one(captured_b18_one_visit_response):
    player = runner.make_campaign_player("b18@1")
    snapshot = runner.build_identity_snapshot(campaign_health())
    wrong_visits = dict(captured_b18_one_visit_response, rootInfo={"visits": 99, "scoreLead": 0.18})

    with pytest.raises(runner.LadderMoveError, match="rootInfo.visits.*exactly 1"):
        runner.select_player_move(wrong_visits, player, snapshot)


def test_pure_b18_rejects_boolean_in_native_policy(captured_b18_one_visit_response):
    player = runner.make_campaign_player("b18@1")
    snapshot = runner.build_identity_snapshot(campaign_health())
    policy = list(captured_b18_one_visit_response["policy"])
    policy[1] = False
    response = dict(captured_b18_one_visit_response, policy=policy)

    with pytest.raises(runner.LadderMoveError, match="native policy"):
        runner.select_player_move(response, player, snapshot)


def test_campaign_policy_validation_retains_finite_negative_sentinels(captured_b18_one_visit_response):
    snapshot = runner.build_identity_snapshot(campaign_health())
    human_policy = [0.0] * 362
    human_policy[0], human_policy[1] = 0.8, -1.0
    assert runner.select_player_move(
        {"humanPolicy": human_policy}, runner.make_campaign_player("rank_8d@1s"), snapshot
    ) == (0, 18)

    native_policy = list(captured_b18_one_visit_response["policy"])
    native_policy[1] = -1.0
    response = dict(captured_b18_one_visit_response, policy=native_policy)
    assert runner.select_player_move(response, runner.make_campaign_player("b18@1"), snapshot) == (3, 15)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda player: dataclasses.replace(player, label="rank_5d@1s"),
        lambda player: dataclasses.replace(player, selection="weighted"),
        lambda player: dataclasses.replace(player, rung=dataclasses.replace(player.rung, root_policy_temperature=1.1)),
        lambda player: dataclasses.replace(player, rung=dataclasses.replace(player.rung, human_sl_profile="rank_5d")),
        lambda player: dataclasses.replace(player, rung=dataclasses.replace(player.rung, max_visits=4)),
    ],
)
def test_campaign_player_validation_rejects_label_selection_and_query_mutations(mutate):
    mutated = mutate(runner.make_campaign_player("rank_4d@1s"))

    with pytest.raises(ValueError, match="label|selection|query|profile|visits|strength"):
        runner.validate_campaign_player(mutated)


@pytest.mark.parametrize("spec", ["rank_9d@1s", "rank_9d@4"])
def test_coordinated_canonical_but_out_of_campaign_player_is_rejected(spec):
    label, rung, selection = runner.run_selfplay.make_player(spec, experimental_min_humansl_search_visits=2)
    player = runner.CampaignPlayer(label, rung, selection)

    with pytest.raises(ValueError, match="frozen campaign player set"):
        runner.validate_campaign_player(player)


def test_stage_player_membership_is_exact_even_for_players_used_by_other_stages():
    assert runner.FROZEN_STAGE_PLAYERS == {
        "seven_d": ("rank_7d@1s",),
        "one_star_b18_1": ("b18@1",),
        "quasi_5d": tuple(f"rank_4d@{tier}" for tier in campaign.GRID),
        "quasi_6d": tuple(f"rank_5d@{tier}" for tier in campaign.GRID),
        "quasi_7d": tuple(f"rank_6d@{tier}" for tier in campaign.GRID),
        "quasi_8d": tuple(f"rank_7d@{tier}" for tier in campaign.GRID),
        "quasi_9d": tuple(f"rank_8d@{tier}" for tier in campaign.GRID),
    }
    runner.validate_stage_player("seven_d", runner.make_campaign_player("rank_7d@1s"))
    with pytest.raises(ValueError, match="stage.*quasi_5d"):
        runner.validate_stage_player("quasi_5d", runner.make_campaign_player("rank_7d@1s"))


def analysis_for_player(player, captured_b18):
    if player == "b18@1":
        return captured_b18
    if player.endswith("@1s"):
        human_policy = [0.0] * 362
        human_policy[0] = 0.9
        return {"rootInfo": {"visits": 1}, "moveInfos": [{"move": "Q16", "order": 0}], "humanPolicy": human_policy}
    return {
        "rootInfo": {"visits": 4},
        "moveInfos": [{"move": "Q16", "order": 0}],
        "_wrapper": campaign_wrapper(),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("player_spec", "expected_move"),
    [("rank_4d@1s", 0), ("rank_6d@4", 72), ("b18@1", 60)],
)
async def test_campaign_preflight_probes_each_mode_through_local_mock_transport_only(
    player_spec, expected_move, captured_b18_one_visit_response
):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(200, json=campaign_health())
        assert request.url.path == "/analyze"
        player = runner.make_campaign_player(player_spec)
        assert json.loads(request.content) == runner.build_player_query([], player)
        return httpx.Response(200, json=analysis_for_player(player_spec, captured_b18_one_visit_response))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        preflight = await runner.campaign_preflight(client, runner.BASE_URL, player_spec)

    assert calls == ["/health", "/analyze"]
    assert preflight["probe_move"] == expected_move
    assert preflight["player"].label == player_spec
    assert preflight["identity_snapshot"]["models"]["b18"]["model_sha256"] == "b18-sha"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("player_spec", "expected_move"),
    [("rank_8d@1s", 0), ("rank_6d@4", 72), ("b18@1", 60)],
)
async def test_per_move_local_analysis_uses_the_campaign_specific_mode_validator(
    player_spec, expected_move, captured_b18_one_visit_response
):
    requested = []

    def handler(request):
        query = json.loads(request.content)
        requested.append(query)
        return httpx.Response(200, json=analysis_for_player(player_spec, captured_b18_one_visit_response))

    player = runner.make_campaign_player(player_spec)
    snapshot = runner.build_identity_snapshot(campaign_health())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        move = await runner.analyze_player_move(client, runner.BASE_URL, [], player, snapshot)

    assert move == expected_move
    assert requested == [runner.build_player_query([], player)]


def test_runner_does_not_export_incompatible_old_alignment_helpers():
    assert not hasattr(runner, "common_preflight")
    assert not hasattr(runner, "play_alignment_game")


@pytest.mark.parametrize(
    "url",
    ["http://localhost:8000", "http://127.0.0.1:8001", "http://127.0.0.1:8000/", "https://127.0.0.1:8000"],
)
def test_campaign_base_url_rejects_every_nonliteral_alias(url):
    with pytest.raises(ValueError, match="exactly"):
        runner.validate_base_url(url)


def test_campaign_base_url_is_fixed_exactly():
    assert runner.BASE_URL == "http://127.0.0.1:8000"
    assert runner.validate_base_url(runner.BASE_URL) == runner.BASE_URL


def results(stage, player, outcomes):
    return [
        {
            "type": "result",
            "stage": stage,
            "player": player,
            "outcome": outcome,
            "conclusive": outcome != "inconclusive",
        }
        for outcome in outcomes
    ]


def wins(count, total):
    return ["win"] * count + ["loss"] * (total - count)


def b18_history(screen_wins, ten_wins=None):
    outcomes = wins(screen_wins, 4)
    if ten_wins is not None:
        added_wins = ten_wins - screen_wins
        assert 0 <= added_wins <= 6
        outcomes += wins(added_wins, 6)
    return outcomes


def completed_prefix():
    return results("seven_d", "rank_7d@1s", wins(5, 10)) + results("one_star_b18_1", "b18@1", wins(2, 4))


def test_public_records_are_frozen_and_stage_and_grid_order_are_fixed():
    request = campaign.GameRequest("seven_d", "rank_7d@1s", "B", 10, "confirm")
    decision = campaign.StageDecision("seven_d", "completed_at_10", "rank_7d@1s", None, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.color = "W"
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.status = "changed"

    assert campaign.STAGE_ORDER == (
        "seven_d",
        "one_star_b18_1",
        "quasi_5d",
        "quasi_6d",
        "quasi_7d",
        "quasi_8d",
        "quasi_9d",
    )
    assert campaign.GRID == ("1s", "4", "8", "16", "32", "64")


@pytest.mark.parametrize("candidate_index", [-1, True, False, 6, 99])
def test_candidate_index_must_be_a_plain_in_range_integer(candidate_index):
    with pytest.raises(ValueError, match="candidate_index"):
        campaign.summarize_candidate([], "quasi_5d", candidate_index)


@pytest.mark.parametrize(
    ("stage", "player", "candidate_index"),
    [
        ("seven_d", "rank_7d@1s", None),
        ("one_star_b18_1", "b18@1", None),
        ("quasi_5d", "rank_4d@8", 2),
    ],
)
def test_candidate_rejects_more_than_ten_valid_results(stage, player, candidate_index):
    with pytest.raises(ValueError, match="more than 10 valid"):
        campaign.summarize_candidate(results(stage, player, wins(6, 11)), stage, candidate_index)


def test_next_action_return_annotation_matches_runtime_variants():
    assert typing.get_type_hints(campaign.next_action)["return"] == campaign.GameRequest | campaign.CampaignDecision


def test_seven_d_reuses_seven_valid_results_and_completes_at_ten():
    records = results("seven_d", "rank_7d@1s", wins(4, 7))
    assert campaign.next_action(records) == campaign.GameRequest("seven_d", "rank_7d@1s", "W", 10, "confirm")

    decision = campaign.stage_decision(records + results("seven_d", "rank_7d@1s", wins(2, 3)), "seven_d")
    assert (decision.status, decision.selected_player) == ("completed_at_10", "rank_7d@1s")


@pytest.mark.parametrize(
    ("screen_wins", "ten_wins", "status"),
    [
        (0, None, "weak_screen"),
        (2, None, "weak_screen"),
        (3, 3, "weak_at_10"),
        (3, 4, "aligned_at_10"),
        (4, 6, "aligned_at_10"),
        (4, 7, "overstrong_at_10"),
        (4, 10, "overstrong_at_10"),
    ],
)
def test_b18_fixed_point_terminal_statuses(screen_wins, ten_wins, status):
    records = results("seven_d", "rank_7d@1s", wins(5, 10))
    records += results("one_star_b18_1", "b18@1", b18_history(screen_wins, ten_wins))
    decision = campaign.stage_decision(records, "one_star_b18_1")
    assert (decision.status, decision.selected_player) == (status, "b18@1")


def test_b18_weak_first_four_remains_weak_screen_when_trailing_evidence_exists():
    records = results("one_star_b18_1", "b18@1", b18_history(2, 8))
    decision = campaign.stage_decision(records, "one_star_b18_1")
    assert (decision.status, decision.selected_player) == ("weak_screen", "b18@1")


def test_b18_strong_screen_is_extended_to_ten():
    records = results("seven_d", "rank_7d@1s", wins(5, 10))
    records += results("one_star_b18_1", "b18@1", wins(3, 4))
    assert campaign.next_action(records) == campaign.GameRequest("one_star_b18_1", "b18@1", "B", 10, "confirm")


def test_quasi_starts_at_exact_virtual_boundary_midpoint_eight():
    assert campaign.next_action(completed_prefix()) == campaign.GameRequest("quasi_5d", "rank_4d@8", "B", 4, "screen")


@pytest.mark.parametrize(
    ("screens", "expected_tier"),
    [
        ({"8": 3}, "1s"),
        ({"8": 2}, "32"),
        ({"8": 3, "1s": 2}, "4"),
        ({"8": 2, "32": 3}, "16"),
        ({"8": 2, "32": 2}, "64"),
    ],
)
def test_binary_search_uses_exact_floor_midpoints_and_both_endpoints(screens, expected_tier):
    records = completed_prefix()
    for tier, win_count in screens.items():
        records += results("quasi_5d", f"rank_4d@{tier}", wins(win_count, 4))
    assert campaign.next_action(records).player == f"rank_4d@{expected_tier}"


@pytest.mark.parametrize("win_count", [0, 1, 2])
def test_four_game_weak_classification(win_count):
    candidate = campaign.summarize_candidate(results("quasi_5d", "rank_4d@8", wins(win_count, 4)), "quasi_5d", 2)
    assert candidate.classification == "weak"


@pytest.mark.parametrize("win_count", [3, 4])
def test_four_game_strong_classification(win_count):
    candidate = campaign.summarize_candidate(results("quasi_5d", "rank_4d@8", wins(win_count, 4)), "quasi_5d", 2)
    assert candidate.classification == "strong"


def test_colors_alternate_independently_per_candidate():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", ["win", "loss", "win", "win"])
    first_at_one_second = campaign.next_action(records)
    assert first_at_one_second.color == "B"

    records += results("quasi_5d", "rank_4d@1s", ["loss"])
    assert campaign.next_action(records).color == "W"


def test_inconclusive_repeats_color_and_does_not_advance_valid_denominator():
    records = completed_prefix() + results("quasi_5d", "rank_4d@8", ["win", "inconclusive"])
    request = campaign.next_action(records)
    assert request == campaign.GameRequest("quasi_5d", "rank_4d@8", "W", 4, "screen")
    candidate = campaign.summarize_candidate(records, "quasi_5d", 2)
    assert (candidate.valid, candidate.inconclusive) == (1, 1)


def test_no_strong_candidate_at_upper_endpoint_has_best_observed():
    records = completed_prefix()
    for tier in ("8", "32", "64"):
        records += results("quasi_5d", f"rank_4d@{tier}", wins(2, 4))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert decision.status == "no_strong_candidate_in_grid"
    assert decision.selected_player is None
    assert decision.best_observed is not None


@pytest.mark.parametrize("win_count", [4, 5, 6])
def test_lowest_strong_confirmed_near_five_is_aligned(win_count):
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(win_count, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert (decision.status, decision.selected_player) == ("aligned_at_10", "rank_4d@4")


def test_overstrong_at_grid_floor_terminates_without_lower_neighbor():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(8, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert (decision.status, decision.selected_player) == ("overstrong_at_grid_floor", "rank_4d@1s")


def test_overstrong_confirmation_requests_lower_neighbor_then_selects_closest_with_lower_tie_break():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(8, 10))
    assert campaign.next_action(records) == campaign.GameRequest("quasi_5d", "rank_4d@1s", "B", 10, "compare_lower")

    records += results("quasi_5d", "rank_4d@1s", wins(2, 6))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert decision.status == "selected_closest_confirmed"
    assert decision.selected_player == "rank_4d@1s"
    assert decision.best_observed.player == "rank_4d@1s"


def test_weak_confirmation_walks_upward_until_first_qualified_candidate():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(3, 10))
    assert campaign.next_action(records).player == "rank_4d@8"
    assert campaign.next_action(records).phase == "confirm_upward"

    records += results("quasi_5d", "rank_4d@8", ["loss"] * 6)
    assert campaign.next_action(records).player == "rank_4d@16"
    records += results("quasi_5d", "rank_4d@16", wins(4, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert (decision.status, decision.selected_player) == ("selected_closest_confirmed", "rank_4d@16")


def test_upward_grid_exhaustion_reports_best_confirmed_observation():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(3, 10))
    records += results("quasi_5d", "rank_4d@8", ["loss"] * 6)
    for tier, win_count in (("16", 2), ("32", 3), ("64", 3)):
        records += results("quasi_5d", f"rank_4d@{tier}", wins(win_count, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert decision.status == "no_qualified_candidate_in_grid"
    assert decision.selected_player is None
    assert decision.best_observed.player == "rank_4d@4"


def test_final_ranking_uses_distance_then_index_and_excludes_four_game_screens():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@1s", wins(4, 4))
    records += results("quasi_5d", "rank_4d@4", wins(7, 10))
    records += results("quasi_5d", "rank_4d@8", wins(3, 10))
    records += results("quasi_5d", "rank_4d@16", wins(5, 10))
    ranked = campaign.rank_confirmed(records, "quasi_5d")
    assert [item.player for item in ranked] == ["rank_4d@16", "rank_4d@4", "rank_4d@8"]


def test_all_quasi_stages_use_the_supplied_lower_rank_profile_and_campaign_terminates():
    records = completed_prefix()
    for stage in campaign.STAGE_ORDER[2:]:
        profile = campaign.QUASI_PROFILES[stage]
        assert campaign.next_action(records).player == f"{profile}@8"
        records += results(stage, f"{profile}@8", wins(3, 4))
        records += results(stage, f"{profile}@1s", wins(2, 4))
        records += results(stage, f"{profile}@4", wins(5, 10))

    terminal = campaign.next_action(records)
    assert terminal.status == "completed"
    assert tuple(item.stage for item in terminal.stages) == campaign.STAGE_ORDER


def ledger_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_raw(path, row):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def finish_request(path, attempt_id, outcome="win"):
    request = campaign.replay_campaign(path)
    campaign.append_reservation(path, attempt_id, request)
    campaign.append_result(path, attempt_id, outcome)


def test_initialize_writes_valid_append_only_header_seeds_exact_frozen_evidence_and_fsyncs(tmp_path, monkeypatch):
    fsync_calls = []

    def record_fsync(fd):
        fsync_calls.append(os.fstat(fd).st_mode)

    monkeypatch.setattr(os, "fsync", record_fsync)
    path = tmp_path / "campaign.jsonl"

    campaign.initialize_campaign(path, "campaign-a", {"engine": "snapshot-a"})

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0] == {
        "type": "campaign_header",
        "protocol": campaign.LEDGER_PROTOCOL,
        "campaign_id": "campaign-a",
        "identity_snapshot": {"engine": "snapshot-a"},
    }
    assert len(rows) == 8
    assert {row["origin_result_id"] for row in rows[1:]} == {
        f"legacy:{campaign.SEED_SHA256}:{line}" for line in (2, 3, 4, 5, 12, 14, 16)
    }
    assert all(row["stage"] == "seven_d" and row["player"] == "rank_7d@1s" for row in rows[1:])
    assert any(stat.S_ISREG(mode) for mode in fsync_calls)
    assert any(stat.S_ISDIR(mode) for mode in fsync_calls)
    assert campaign.replay_campaign(path) == campaign.GameRequest("seven_d", "rank_7d@1s", "W", 10, "confirm")

    fsync_calls.clear()
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))
    campaign.append_result(path, 1, "win")
    assert len(fsync_calls) == 2
    assert all(stat.S_ISREG(mode) for mode in fsync_calls)


@pytest.mark.parametrize(
    ("campaign_id", "identity_snapshot"),
    [
        ("", {}),
        ("   ", {}),
        (True, {}),
        (7, {}),
        ("bad:delimiter", {}),
        ("valid-after-fix", {"not_json": {object()}}),
    ],
)
def test_invalid_header_input_never_creates_destination_and_corrected_retry_succeeds(
    tmp_path, campaign_id, identity_snapshot
):
    path = tmp_path / "campaign.jsonl"
    with pytest.raises(ValueError, match="campaign_id|JSON|identity"):
        campaign.initialize_campaign(path, campaign_id, identity_snapshot)
    assert not path.exists()

    campaign.initialize_campaign(path, "corrected", {"engine": "valid"})
    assert campaign.load_campaign(path).header["campaign_id"] == "corrected"


def test_child_rejects_reused_ancestor_campaign_id_before_creating_destination(tmp_path):
    parent = tmp_path / "parent.jsonl"
    campaign.initialize_campaign(parent, "same-id", {})
    campaign.append_stop(parent, "rotate")
    child = tmp_path / "child.jsonl"

    with pytest.raises(ValueError, match="ancestor|campaign_id"):
        campaign.initialize_campaign(child, "same-id", {}, parent, ledger_sha(parent))
    assert not child.exists()

    campaign.initialize_campaign(child, "unique-child", {}, parent, ledger_sha(parent))
    campaign.append_stop(child, "rotate")
    grandchild = tmp_path / "grandchild.jsonl"
    with pytest.raises(ValueError, match="ancestor|campaign_id"):
        campaign.initialize_campaign(grandchild, "same-id", {}, child, ledger_sha(child))
    assert not grandchild.exists()


def test_load_rejects_invalid_or_nonfirst_header(tmp_path):
    missing_protocol = tmp_path / "missing.jsonl"
    missing_protocol.write_text('{"type":"campaign_header","campaign_id":"x","identity_snapshot":{}}\n')
    with pytest.raises(ValueError, match="header"):
        campaign.load_campaign(missing_protocol)

    duplicate = tmp_path / "duplicate.jsonl"
    campaign.initialize_campaign(duplicate, "duplicate", {})
    append_raw(duplicate, json.loads(duplicate.read_text().splitlines()[0]))
    with pytest.raises(ValueError, match="header"):
        campaign.load_campaign(duplicate)


def test_load_rejects_missing_root_or_child_carries(tmp_path):
    root = tmp_path / "root.jsonl"
    campaign.initialize_campaign(root, "root", {})
    root.write_text("\n".join(root.read_text().splitlines()[:-1]) + "\n")
    with pytest.raises(ValueError, match="complete.*carry|carry.*complete"):
        campaign.load_campaign(root)

    campaign.initialize_campaign(root := tmp_path / "complete-root.jsonl", "complete-root", {})
    campaign.append_stop(root, "rotate")
    child = tmp_path / "child.jsonl"
    campaign.initialize_campaign(child, "child", {}, root, ledger_sha(root))
    child.write_text("\n".join(child.read_text().splitlines()[:-1]) + "\n")
    with pytest.raises(ValueError, match="complete.*carry|carry.*complete"):
        campaign.load_campaign(child)


def test_load_rejects_reordered_carries_that_would_change_first_four_replay(tmp_path):
    parent = tmp_path / "parent.jsonl"
    campaign.initialize_campaign(parent, "parent", {})
    for attempt, outcome in enumerate(["win", "win", "win", "win", "win", "win", "loss", "loss"], 1):
        finish_request(parent, attempt, outcome)
    assert campaign.replay_campaign(parent).stage == "one_star_b18_1"
    campaign.append_stop(parent, "rotate")
    child = tmp_path / "child.jsonl"
    campaign.initialize_campaign(child, "child", {}, parent, ledger_sha(parent))
    rows = [json.loads(line) for line in child.read_text().splitlines()]
    carries = rows[1:]
    seven_d = [row for row in carries if row["stage"] == "seven_d"]
    b18 = [row for row in carries if row["stage"] == "one_star_b18_1"]
    reordered = seven_d + sorted(b18, key=lambda row: row["outcome"] == "win")
    child.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in [rows[0], *reordered]))

    with pytest.raises(ValueError, match="order|sequence|prefix"):
        campaign.load_campaign(child)


def test_reservation_result_pairing_is_validated_and_new_result_has_immutable_origin(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign-a", {})
    request = campaign.replay_campaign(path)
    campaign.append_reservation(path, 1, request)
    campaign.append_result(path, 1, "win")

    loaded = campaign.load_campaign(path)
    result = loaded.records[-1]
    assert result["origin_result_id"] == "campaign-a:1"
    assert (result["stage"], result["player"], result["color"]) == (request.stage, request.player, request.color)

    append_raw(
        path,
        {
            "type": "result",
            "attempt_id": 99,
            "origin_result_id": "campaign-a:99",
            "stage": request.stage,
            "player": request.player,
            "color": request.color,
            "outcome": "loss",
            "conclusive": True,
        },
    )
    with pytest.raises(ValueError, match="reservation"):
        campaign.load_campaign(path)


def test_append_result_defensively_rejects_existing_generated_origin_without_appending(tmp_path):
    parent = tmp_path / "parent.jsonl"
    campaign.initialize_campaign(parent, "parent", {})
    finish_request(parent, 1)
    campaign.append_stop(parent, "rotate")
    child = tmp_path / "child.jsonl"
    campaign.initialize_campaign(child, "child", {}, parent, ledger_sha(parent))
    rows = [json.loads(line) for line in child.read_text().splitlines()]
    rows[0]["campaign_id"] = "parent"
    child.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    campaign.append_reservation(child, 1, campaign.replay_campaign(child))
    before = child.read_bytes()

    with pytest.raises(ValueError, match="origin_result_id|already"):
        campaign.append_result(child, 1, "win")
    assert child.read_bytes() == before
    assert campaign.campaign_summary(child).unknown_charged_attempts == (1,)


def test_reservation_must_match_the_unique_replayed_task1_request(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign", {})
    future = campaign.GameRequest("quasi_9d", "rank_8d@8", "B", 4, "screen")
    with pytest.raises(ValueError, match="expected|next"):
        campaign.append_reservation(path, 1, future)

    append_raw(
        path,
        {
            "type": "reservation",
            "attempt_id": 1,
            "stage": future.stage,
            "player": future.player,
            "color": future.color,
            "target_valid": future.target_valid,
            "phase": future.phase,
        },
    )
    append_raw(
        path,
        {
            "type": "result",
            "attempt_id": 1,
            "origin_result_id": "campaign:1",
            "stage": future.stage,
            "player": future.player,
            "color": future.color,
            "outcome": "win",
            "conclusive": True,
        },
    )
    with pytest.raises(ValueError, match="expected|next"):
        campaign.load_campaign(path)


def test_same_ledger_resume_refuses_stop_stopped_and_unmatched_reservation(tmp_path):
    for stop_type in ("campaign_stopped", "stopped"):
        path = tmp_path / f"{stop_type}.jsonl"
        campaign.initialize_campaign(path, stop_type, {})
        append_raw(path, {"type": stop_type, "reason": "operator"})
        with pytest.raises(ValueError, match="stopped"):
            campaign.load_campaign(path)
        assert campaign.load_campaign(path, allow_stopped_for_summary=True).stopped

    unmatched = tmp_path / "unmatched.jsonl"
    campaign.initialize_campaign(unmatched, "unmatched", {})
    campaign.append_reservation(unmatched, 1, campaign.replay_campaign(unmatched))
    with pytest.raises(ValueError, match="unmatched reservation"):
        campaign.load_campaign(unmatched)
    summary = campaign.load_campaign(unmatched, allow_stopped_for_summary=True)
    assert summary.unknown_charged_attempts == (1,)


def test_stopped_game_pairs_its_reservation_but_is_never_evidence(tmp_path):
    path = tmp_path / "stopped-game.jsonl"
    campaign.initialize_campaign(path, "stopped-game", {})
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))
    campaign.append_stop(path, "remote error", event_type="stopped", attempt_id=1)

    summary = campaign.load_campaign(path, allow_stopped_for_summary=True)
    assert summary.unknown_charged_attempts == ()
    assert len(summary.evidence) == 7


def test_stop_is_terminal_except_for_the_companion_campaign_stop(tmp_path):
    path = tmp_path / "stopped.jsonl"
    campaign.initialize_campaign(path, "stopped", {})
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))
    campaign.append_stop(path, "remote error", event_type="stopped", attempt_id=1)
    campaign.append_stop(path, "remote error", event_type="campaign_stopped")
    append_raw(path, {"type": "stage_started", "stage": "seven_d"})

    with pytest.raises(ValueError, match="after stop"):
        campaign.load_campaign(path, allow_stopped_for_summary=True)

    reverse = tmp_path / "reverse.jsonl"
    campaign.initialize_campaign(reverse, "reverse", {})
    campaign.append_reservation(reverse, 1, campaign.replay_campaign(reverse))
    campaign.append_stop(reverse, "preflight", event_type="campaign_stopped")
    append_raw(reverse, {"type": "stopped", "attempt_id": 1, "reason": "late"})
    with pytest.raises(ValueError, match="after stop"):
        campaign.load_campaign(reverse, allow_stopped_for_summary=True)


def test_new_child_imports_only_completed_parent_evidence_with_explicit_exact_sha(tmp_path):
    parent = tmp_path / "parent.jsonl"
    campaign.initialize_campaign(parent, "parent", {})
    finish_request(parent, 1)
    append_raw(parent, {"type": "stage_completed", "stage": "quasi_9d"})
    campaign.append_reservation(parent, 2, campaign.replay_campaign(parent))
    campaign.append_stop(parent, "remote failure", event_type="stopped")
    parent_sha = ledger_sha(parent)

    with pytest.raises(ValueError, match="SHA-256"):
        campaign.initialize_campaign(tmp_path / "bad.jsonl", "bad", {}, parent, "0" * 64)
    child = tmp_path / "child.jsonl"
    campaign.initialize_campaign(child, "child", {}, parent, parent_sha)
    loaded = campaign.load_campaign(child)

    assert len(loaded.evidence) == 8
    assert loaded.unknown_charged_attempts == ()
    inherited = next(row for row in loaded.evidence if row["origin_result_id"] == "parent:1")
    assert inherited["type"] == "carry_result"
    assert inherited["direct_parent_sha256"] == parent_sha
    assert inherited["direct_parent_line"] == 10
    assert not any(row.get("origin_result_id") == "parent:2" for row in loaded.evidence)
    assert not any(row["type"] in {"stage_started", "stage_completed"} for row in loaded.records)


def test_root_seed_carry_must_exactly_match_its_sha_validated_source_line(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign", {})
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["outcome"] = "win"
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

    with pytest.raises(ValueError, match="seed"):
        campaign.load_campaign(path)


def test_recursive_chain_preserves_origins_and_rejects_tampered_intermediate_sha(tmp_path):
    root = tmp_path / "root.jsonl"
    campaign.initialize_campaign(root, "root", {})
    finish_request(root, 1)
    campaign.append_stop(root, "rotate")
    child = tmp_path / "child.jsonl"
    campaign.initialize_campaign(child, "child", {}, root, ledger_sha(root))
    finish_request(child, 1)
    campaign.append_stop(child, "rotate")
    child_sha = ledger_sha(child)
    grandchild = tmp_path / "grandchild.jsonl"
    campaign.initialize_campaign(grandchild, "grandchild", {}, child, child_sha)

    loaded = campaign.load_campaign(grandchild)
    assert {"root:1", "child:1"} <= {row["origin_result_id"] for row in loaded.evidence}
    assert (
        next(row for row in loaded.evidence if row["origin_result_id"] == "root:1")["direct_parent_sha256"] == child_sha
    )

    append_raw(child, {"type": "stage_completed", "stage": "seven_d"})
    with pytest.raises(ValueError, match="SHA-256"):
        campaign.load_campaign(grandchild)


def test_generation_three_duplicate_origin_is_rejected_across_result_and_carry(tmp_path):
    root = tmp_path / "root.jsonl"
    campaign.initialize_campaign(root, "root", {})
    finish_request(root, 1)
    campaign.append_stop(root, "rotate")
    child = tmp_path / "child.jsonl"
    campaign.initialize_campaign(child, "child", {}, root, ledger_sha(root))
    campaign.append_stop(child, "rotate")
    child_sha = ledger_sha(child)
    grandchild = tmp_path / "grandchild.jsonl"
    campaign.initialize_campaign(grandchild, "grandchild", {}, child, child_sha)
    duplicate = dict(
        next(row for row in campaign.load_campaign(grandchild).evidence if row["origin_result_id"] == "root:1")
    )
    duplicate.update(type="result", attempt_id=999)
    append_raw(grandchild, duplicate)
    with pytest.raises(ValueError, match="duplicate origin_result_id"):
        campaign.load_campaign(grandchild, allow_stopped_for_summary=True)


def test_control_rows_are_ignored_and_resume_is_reconstructed_from_evidence(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign", {})
    append_raw(path, {"type": "stage_started", "stage": "quasi_9d"})
    append_raw(path, {"type": "stage_completed", "stage": "seven_d"})
    assert campaign.replay_campaign(path).stage == "seven_d"


@pytest.mark.parametrize(
    "row",
    [
        {"type": "stage_started", "stage": True},
        {"type": "stage_completed", "stage": "not_a_stage"},
        {"type": "stopped", "reason": ""},
        {"type": "stopped", "reason": 7},
        {"type": "stopped", "reason": "error", "attempt_id": True},
        {"type": "campaign_stopped", "reason": "error", "attempt_id": 1},
        {"type": "campaign_stopped", "reason": "error", "attempt_id": None},
        {"type": "campaign_stopped", "reason": "   "},
        {"type": "campaign_stopped", "reason": "error", "extra": "field"},
        {"type": "stopped", "reason": "error", "extra": "field"},
        {"type": "stage_started", "stage": "seven_d", "extra": "field"},
    ],
)
def test_loader_strictly_validates_control_and_stop_record_schema(tmp_path, row):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign", {})
    append_raw(path, row)
    with pytest.raises(ValueError, match="stage|stop|reason|attempt"):
        campaign.load_campaign(path, allow_stopped_for_summary=True)


def test_loader_rejects_explicit_parent_cycle(tmp_path, monkeypatch):
    path = tmp_path / "cycle.jsonl"
    append_raw(
        path,
        {
            "type": "campaign_header",
            "protocol": campaign.LEDGER_PROTOCOL,
            "campaign_id": "cycle",
            "identity_snapshot": {},
            "parent_path": str(path),
            "parent_sha256": "0" * 64,
        },
    )
    monkeypatch.setattr(campaign, "_sha256", lambda _path: "0" * 64)
    with pytest.raises(ValueError, match="cycle"):
        campaign.load_campaign(path)


@pytest.mark.parametrize(
    ("completed_outcomes", "expected_stage"),
    [
        ([], "seven_d"),
        (["win", "win", "win"], "one_star_b18_1"),
        (["win", "win", "win", "loss", "loss", "loss", "win"], "quasi_5d"),
    ],
)
def test_fresh_load_reconstructs_unique_resume_stage_from_evidence(tmp_path, completed_outcomes, expected_stage):
    path = tmp_path / f"{expected_stage}.jsonl"
    campaign.initialize_campaign(path, expected_stage, {})
    for attempt, outcome in enumerate(completed_outcomes, 1):
        finish_request(path, attempt, outcome)

    loaded = campaign.load_campaign(path)
    assert loaded.action.stage == expected_stage


def test_load_rejects_more_than_ten_replayed_candidate_results(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign", {})
    for attempt in range(1, 5):
        color = "W" if attempt % 2 else "B"
        append_raw(
            path,
            {
                "type": "reservation",
                "attempt_id": attempt,
                "stage": "seven_d",
                "player": "rank_7d@1s",
                "color": color,
                "target_valid": 10,
                "phase": "confirm",
            },
        )
        append_raw(
            path,
            {
                "type": "result",
                "attempt_id": attempt,
                "origin_result_id": f"campaign:{attempt}",
                "stage": "seven_d",
                "player": "rank_7d@1s",
                "color": color,
                "outcome": "win",
                "conclusive": True,
            },
        )
    with pytest.raises(ValueError, match="more than 10 valid"):
        campaign.load_campaign(path)


def test_load_rejects_more_than_ten_results_hidden_in_a_later_stage(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign", {})
    for attempt in range(1, 12):
        append_raw(
            path,
            {
                "type": "reservation",
                "attempt_id": attempt,
                "stage": "quasi_9d",
                "player": "rank_8d@1s",
                "color": "B" if attempt % 2 else "W",
            },
        )
        append_raw(
            path,
            {
                "type": "result",
                "attempt_id": attempt,
                "origin_result_id": f"campaign:{attempt}",
                "stage": "quasi_9d",
                "player": "rank_8d@1s",
                "color": "B" if attempt % 2 else "W",
                "outcome": "win",
                "conclusive": True,
            },
        )
    with pytest.raises(ValueError, match="more than 10 valid"):
        campaign.load_campaign(path)


def test_append_result_rejects_boolean_attempt_without_corrupting_ledger(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "campaign", {})
    campaign.append_reservation(path, 1, campaign.replay_campaign(path))

    with pytest.raises(ValueError, match="attempt_id"):
        campaign.append_result(path, True, "win")
    assert campaign.campaign_summary(path).unknown_charged_attempts == (1,)


def _campaign_at_nine_seven_d_results(path):
    campaign.initialize_campaign(path, "serial-test", campaign_health())
    finish_request(path, 1, "loss")
    finish_request(path, 2, "win")
    assert campaign.replay_campaign(path).stage == "seven_d"
    assert campaign.replay_campaign(path).color == "W"


@pytest.mark.asyncio
async def test_serial_loop_reserves_before_request_persists_results_and_repeats_inconclusive_color(tmp_path):
    path = tmp_path / "campaign.jsonl"
    _campaign_at_nine_seven_d_results(path)
    calls = []
    sleeps = []
    outcomes = iter(
        [
            SimpleNamespace(conclusive=False, result="inconclusive_score", our_win=False),
            SimpleNamespace(conclusive=True, result="our_win", our_win=True),
        ]
    )

    async def preflight(request, _snapshot):
        calls.append(("preflight", request.stage, request.player, request.color))

    async def play(request, _snapshot):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert rows[-1]["type"] == "reservation"
        assert rows[-1]["color"] == request.color
        calls.append(("play", request.stage, request.player, request.color))
        return next(outcomes)

    async def sleep(seconds):
        sleeps.append(seconds)

    async def stop_on_next_stage(request, _snapshot):
        if request.stage != "seven_d":
            raise RuntimeError("local probe failed")
        await preflight(request, _snapshot)

    with pytest.raises(runner.CampaignStopped, match="local probe failed"):
        await runner.execute_serial_campaign(
            path,
            preflight_player=stop_on_next_stage,
            play_game=play,
            sleep=sleep,
            emit=lambda _event: None,
        )

    summary = campaign.campaign_summary(path)
    new_results = [row for row in summary.records if row.get("type") == "result"][-2:]
    assert [(row["color"], row["outcome"]) for row in new_results] == [
        ("W", "inconclusive"),
        ("W", "win"),
    ]
    assert sleeps == [5.0]
    stage_rows = [row for row in summary.records if row["type"].startswith("stage_")]
    assert [(row["type"], row["stage"]) for row in stage_rows] == [
        ("stage_started", "seven_d"),
        ("stage_completed", "seven_d"),
        ("stage_started", "one_star_b18_1"),
    ]
    assert summary.records[-1]["type"] == "campaign_stopped"


@pytest.mark.asyncio
async def test_preflight_failure_stops_before_reservation_or_golaxy_call(tmp_path):
    path = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(path, "preflight-stop", campaign_health())
    played = False

    async def fail_preflight(_request, _snapshot):
        raise RuntimeError("identity mismatch")

    async def play(*_args):
        nonlocal played
        played = True

    with pytest.raises(runner.CampaignStopped, match="identity mismatch"):
        await runner.execute_serial_campaign(
            path,
            preflight_player=fail_preflight,
            play_game=play,
            sleep=asyncio.sleep,
            emit=lambda _event: None,
        )

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert not played
    assert not any(row["type"] == "reservation" for row in rows)
    assert [row["type"] for row in rows[-2:]] == ["stage_started", "campaign_stopped"]


@pytest.mark.asyncio
async def test_stopped_ledger_refuses_before_any_local_or_golaxy_access(tmp_path):
    path = tmp_path / "stopped.jsonl"
    campaign.initialize_campaign(path, "stopped-live", campaign_health())
    campaign.append_stop(path, "prior remote error")
    touched = []

    async def touch(*_args):
        touched.append(True)

    with pytest.raises(ValueError, match="stopped"):
        await runner.execute_serial_campaign(
            path,
            preflight_player=touch,
            play_game=touch,
            sleep=touch,
            emit=lambda _event: None,
        )
    assert touched == []


@pytest.mark.asyncio
async def test_remote_error_closes_reserved_attempt_and_stops_without_retry(tmp_path):
    path = tmp_path / "remote-stop.jsonl"
    campaign.initialize_campaign(path, "remote-stop", campaign_health())
    plays = 0

    async def preflight(*_args):
        return None

    async def play(*_args):
        nonlocal plays
        plays += 1
        raise RuntimeError("Golaxy 7002")

    with pytest.raises(runner.CampaignStopped, match="7002"):
        await runner.execute_serial_campaign(
            path,
            preflight_player=preflight,
            play_game=play,
            sleep=asyncio.sleep,
            emit=lambda _event: None,
        )

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert plays == 1
    assert [row["type"] for row in rows[-3:]] == ["reservation", "stopped", "campaign_stopped"]
    assert rows[-2]["attempt_id"] == rows[-3]["attempt_id"]


@pytest.mark.asyncio
async def test_child_recovery_rebuilds_completed_predecessor_from_evidence_not_control_rows(tmp_path):
    parent = tmp_path / "parent.jsonl"
    _campaign_at_nine_seven_d_results(parent)
    finish_request(parent, 3, "win")
    campaign.append_stop(parent, "operator recovery")
    child = tmp_path / "child.jsonl"
    campaign.initialize_campaign(child, "child-live", campaign_health(), parent, ledger_sha(parent))

    async def fail_after_recovery(request, _snapshot):
        assert request.stage == "one_star_b18_1"
        raise RuntimeError("probe after recovery")

    with pytest.raises(runner.CampaignStopped, match="probe after recovery"):
        await runner.execute_serial_campaign(
            child,
            preflight_player=fail_after_recovery,
            play_game=lambda *_args: pytest.fail("game must not start"),
            emit=lambda _event: None,
        )

    rows = [json.loads(line) for line in child.read_text().splitlines()]
    assert not any(row["type"] == "stage_completed" for row in rows)
    assert [(row["type"], row.get("stage")) for row in rows[-2:]] == [
        ("stage_started", "one_star_b18_1"),
        ("campaign_stopped", None),
    ]


@pytest.mark.asyncio
async def test_serial_loop_resumes_a_persisted_open_stage_without_duplicate_start(tmp_path):
    path = tmp_path / "open-stage.jsonl"
    campaign.initialize_campaign(path, "open-stage", campaign_health())
    campaign.append_stage_event(path, "stage_started", "seven_d")

    async def fail_preflight(*_args):
        raise RuntimeError("stop after resumed start")

    with pytest.raises(runner.CampaignStopped):
        await runner.execute_serial_campaign(
            path,
            preflight_player=fail_preflight,
            play_game=lambda *_args: pytest.fail("game must not start"),
            emit=lambda _event: None,
        )
    rows = [row for row in map(json.loads, path.read_text().splitlines()) if row["type"] == "stage_started"]
    assert len(rows) == 1


def test_output_lock_rejects_a_second_process_writer(tmp_path):
    path = tmp_path / "campaign.jsonl"
    with runner.campaign_output_lock(path):
        with pytest.raises(RuntimeError, match="locked"):
            with runner.campaign_output_lock(path):
                pass


def test_live_cli_requires_exact_parent_pair_and_a_new_output(tmp_path):
    parser = runner.build_parser()
    parent = tmp_path / "parent.jsonl"
    campaign.initialize_campaign(parent, "parent-cli", campaign_health())
    campaign.append_stop(parent, "rotate")
    sha = hashlib.sha256(parent.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="both"):
        runner.validate_args(parser.parse_args(["--out", str(tmp_path / "child.jsonl"), "--parent", str(parent)]))
    args = parser.parse_args(["--out", str(tmp_path / "child.jsonl"), "--parent", str(parent), "--parent-sha256", sha])
    assert runner.validate_args(args) == "live"
    with pytest.raises(ValueError, match="different output"):
        args = parser.parse_args(["--out", str(parent), "--parent", str(parent), "--parent-sha256", sha])
        runner.validate_args(args)
    with pytest.raises(ValueError, match="SHA-256"):
        runner.validate_args(
            parser.parse_args(
                [
                    "--out",
                    str(tmp_path / "bad-sha-child.jsonl"),
                    "--parent",
                    str(parent),
                    "--parent-sha256",
                    "not-a-sha",
                ]
            )
        )


def test_read_only_summary_validates_control_order_without_network(tmp_path, monkeypatch):
    path = tmp_path / "summary.jsonl"
    _campaign_at_nine_seven_d_results(path)
    campaign.append_stage_event(path, "stage_started", "seven_d")
    finish_request(path, 3, "win")
    campaign.append_stage_event(path, "stage_completed", "seven_d")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: pytest.fail("summary opened network client"))
    summary = runner.summarize_campaign(path)
    assert summary["next_action"]["stage"] == "one_star_b18_1"
    assert summary["stages"][0]["status"] == "completed_at_10"
    assert summary["origin_result_ids_unique"] is True

    bad = tmp_path / "bad-order.jsonl"
    campaign.initialize_campaign(bad, "bad-order", campaign_health())
    campaign.append_stage_event(bad, "stage_started", "one_star_b18_1")
    with pytest.raises(ValueError, match="stage_started"):
        runner.summarize_campaign(bad)
