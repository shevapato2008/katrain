import importlib
import json
import sys
from pathlib import Path

import httpx
import pytest

from katrain.core.ladder import HUMANSL_PIKL_BASELINE


CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
selfplay = importlib.import_module("run_selfplay")


def test_player_constructs_attested_b18_humansl_search_recipe():
    label, rung, selection = selfplay.make_player("rank_9d@40")

    assert label == "rank_9d@40"
    assert rung.net == "b18"
    assert rung.mechanism == "humansl_search"
    assert rung.human_sl_profile == "rank_9d"
    assert rung.max_visits == 40
    assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
    assert rung.human_sl_params is not HUMANSL_PIKL_BASELINE
    assert selection == "search"


def test_player_gives_each_humansl_search_player_a_fresh_recipe():
    _, first, _ = selfplay.make_player("rank_5d@40")
    _, second, _ = selfplay.make_player("rank_5d@80")

    assert first.human_sl_params == second.human_sl_params == HUMANSL_PIKL_BASELINE
    assert first.human_sl_params is not second.human_sl_params


@pytest.mark.parametrize(
    ("spec", "mechanism", "net", "selection"),
    [
        ("rank_9d@1", "humansl", "humanv0", "weighted"),
        ("rank_9d@1s", "humansl", "humanv0", "argmax_human"),
        ("b28@20", "net_search", "b28", "search"),
    ],
)
def test_player_preserves_native_and_pure_search_modes(spec, mechanism, net, selection):
    _, rung, actual_selection = selfplay.make_player(spec)

    assert rung.mechanism == mechanism
    assert rung.net == net
    assert rung.human_sl_params == {}
    assert actual_selection == selection


@pytest.mark.parametrize("visits", [2, 7, 16, 32, 39])
def test_player_rejects_unsupported_humansl_search_visits(visits):
    with pytest.raises(ValueError, match=r"HumanSL search.*minimum.*40"):
        selfplay.make_player(f"rank_9d@{visits}")


def test_player_rejects_search_suffix_above_one_visit():
    with pytest.raises(ValueError, match=r"1s"):
        selfplay.make_player("rank_9d@40s")


@pytest.mark.parametrize(
    "profile",
    [
        "rank_20k",
        "rank_1k",
        "rank_1d",
        "rank_9d",
        "rank_20k_9d",
        "preaz_20k",
        "preaz_9d",
        "preaz_1d_1k",
        "proyear_1800",
        "proyear_2023",
    ],
)
def test_player_accepts_exact_katago_humansl_profile_boundaries(profile):
    _, rung, _ = selfplay.make_player(f"{profile}@40")

    assert rung.human_sl_profile == profile


@pytest.mark.parametrize(
    "profile",
    [
        "rank_0k",
        "rank_21k",
        "rank_0d",
        "rank_10d",
        "rank_09d",
        "rank_1x",
        "rank_1d_extra",
        "preaz_21k",
        "preaz_10d",
        "preaz_1d_extra_piece",
        "proyear_1799",
        "proyear_2024",
        "proyear_20x0",
        "proyear_",
    ],
)
def test_player_rejects_out_of_range_or_malformed_humansl_profiles(profile):
    with pytest.raises(ValueError, match=r"bad player profile"):
        selfplay.make_player(f"{profile}@40")


def _health_snapshot():
    return selfplay.adapters.retain_health_snapshot(
        {
            "capability_schema": 1,
            "katago_version": "KataGo v1.16.3",
            "default_model": "b28",
            "models": {
                "b28": {
                    "running": True,
                    "model_path": "/models/b28.bin.gz",
                    "model_sha256": "b28-sha",
                    "model_sha256_verified": True,
                    "has_human_model": True,
                    "human_model_path": "/models/human.bin.gz",
                    "human_model_sha256": "human-sha",
                    "human_model_sha256_verified": True,
                }
            },
        }
    )


def _attestation(**changes):
    wrapper = {
        "selected_model": "b28",
        "model_path": "/models/b28.bin.gz",
        "model_sha256": "b28-sha",
        "human_model_path": "/models/human.bin.gz",
        "human_model_sha256": "human-sha",
        "katago_version": "KataGo v1.16.3",
    }
    wrapper.update(changes)
    return wrapper


@pytest.mark.asyncio
@pytest.mark.parametrize("player_spec", ["rank_9d@1", "rank_9d@1s"])
@pytest.mark.parametrize("wrapper", [None, _attestation(human_model_sha256="drifted")])
async def test_native_humansl_selection_rejects_missing_or_drifted_attestation(player_spec, wrapper):
    _, rung, selection = selfplay.make_player(player_spec)

    def handler(request):
        body = json.loads(request.content)
        assert body["overrideSettings"].get("model") is None
        human_policy = [0.0] * (19 * 19 + 1)
        human_policy[0] = 1.0
        response = {"humanPolicy": human_policy}
        if wrapper is not None:
            response["_wrapper"] = wrapper
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
        )

    assert result == "unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("player_spec", ["rank_9d@1", "rank_9d@1s"])
async def test_native_humansl_selection_accepts_full_default_model_attestation(player_spec):
    _, rung, selection = selfplay.make_player(player_spec)

    def handler(_request):
        human_policy = [0.0] * (19 * 19 + 1)
        human_policy[0] = 1.0
        return httpx.Response(200, json={"humanPolicy": human_policy, "_wrapper": _attestation()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
        )

    assert result != "unavailable"


def test_default_result_namespace_is_v2_pikl_and_legacy_namespace_is_rejected():
    args = selfplay.build_arg_parser().parse_args(["--matchups", "rank_9d@80:rank_9d@40:1"])

    assert Path(args.out).name == "selfplay_v2_pikl"
    with pytest.raises(ValueError, match=r"legacy.*selfplay_v2_pikl"):
        selfplay._validated_out_dir(Path(selfplay.__file__).parent / "results" / "selfplay")
