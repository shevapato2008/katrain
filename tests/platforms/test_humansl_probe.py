import importlib.util
import json
import math
from pathlib import Path

import httpx
import pytest

from katrain.core.ladder import HUMANSL_PIKL_BASELINE, LadderRung, rung_strength_spec


PROBE_PATH = (
    Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py"
)


def _load_probe():
    spec = importlib.util.spec_from_file_location("probe_humansl_search", PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _attestation(alias):
    return {
        "selected_model": alias,
        "model_path": f"/models/{alias}.bin.gz",
        "model_sha256": f"{alias}-sha",
        "human_model_path": "/models/human.bin.gz",
        "human_model_sha256": "human-sha",
        "katago_version": "KataGo v1.16.3",
    }


def _analysis(alias, request_id, moves, psv, orders):
    return {
        "id": request_id,
        "moveInfos": [
            {"move": candidate, "playSelectionValue": value, "order": rank}
            for candidate, value, rank in zip(moves, psv, orders)
        ],
        "rootInfo": {"visits": 500, "scoreLead": 0.5},
        "_wrapper": _attestation(alias),
    }


def _health():
    return {
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
                "human_model_path": "/models/human.bin.gz",
                "human_model_sha256": "human-sha",
                "human_model_sha256_verified": True,
            }
            for alias in ("b18", "b28")
        },
    }


def _valid_exchange(probe, run_id="run-abc"):
    requests = probe.build_probe_requests(run_id)
    low_move = probe.LOCKED_EXPECTED["b18_pikl_low"]["move"]
    high_move = probe.LOCKED_EXPECTED["b18_pikl_high"]["move"]
    responses = {
        "b18_base": _analysis("b18", requests["b18_base"]["id"], [low_move, high_move], [20.0, 8.0], [0, 1]),
        "b18_profile_zero": _analysis(
            "b18", requests["b18_profile_zero"]["id"], [low_move, high_move], [19.0, 8.0], [0, 1]
        ),
        "b18_pikl_low": _analysis("b18", requests["b18_pikl_low"]["id"], [low_move, high_move], [85.0, 0.5], [0, 1]),
        "b18_pikl_high": _analysis("b18", requests["b18_pikl_high"]["id"], [high_move, low_move], [35.0, 23.0], [0, 1]),
        "b28_base": _analysis("b28", requests["b28_base"]["id"], [high_move, low_move], [30.0, 12.0], [0, 1]),
    }
    return requests, responses


def _validate(probe, requests, responses):
    return probe.validate_probe_results(_health(), requests, responses, case_order=list(probe.PROBE_CASES))


def _canonical_pikl_spec(probe, pikl_lambda):
    params = dict(HUMANSL_PIKL_BASELINE)
    params["humanSLChosenMovePiklLambda"] = pikl_lambda
    rung = LadderRung(
        rung=0,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank=probe.LOCKED_PROFILE,
        rank_name=probe.LOCKED_PROFILE,
        net="b18",
        mechanism="humansl_search",
        human_sl_profile=probe.LOCKED_PROFILE,
        max_visits=probe.LOCKED_VISITS,
        human_sl_params=params,
    )
    return rung_strength_spec(rung)


def test_builds_exact_five_run_unique_wire_requests_from_production_recipe():
    probe = _load_probe()
    requests = probe.build_probe_requests("run-abc")

    assert list(requests) == ["b18_base", "b18_profile_zero", "b18_pikl_low", "b18_pikl_high", "b28_base"]
    assert len({query["id"] for query in requests.values()}) == 5
    assert all(query["id"].startswith("semantic-probe-run-abc:") for query in requests.values())
    assert all(query["moves"] == probe.LOCKED_HISTORY for query in requests.values())
    assert all(query["maxVisits"] == probe.LOCKED_VISITS for query in requests.values())

    for case, pikl_lambda in zip(("b18_pikl_low", "b18_pikl_high"), probe.LOCKED_LAMBDAS):
        expected = dict(_canonical_pikl_spec(probe, pikl_lambda).override_settings)
        assert requests[case]["overrideSettings"] == {"model": "b18", **expected}
        assert expected["ignorePreRootHistory"] is False
        assert {key: expected[key] for key in HUMANSL_PIKL_BASELINE} == {
            **HUMANSL_PIKL_BASELINE,
            "humanSLChosenMovePiklLambda": pikl_lambda,
        }

    zero = requests["b18_profile_zero"]["overrideSettings"]
    assert zero["model"] == "b18"
    assert zero["humanSLProfile"] == probe.LOCKED_PROFILE
    assert zero["ignorePreRootHistory"] is False
    assert set(zero) == {
        "model",
        "reportAnalysisWinratesAs",
        "humanSLProfile",
        "ignorePreRootHistory",
        *HUMANSL_PIKL_BASELINE,
    }
    assert all(zero[key] == 0.0 for key in probe.HUMANSL_BLEND_KEYS)


def test_locked_fixture_declares_controls_and_lambda_order_swap():
    probe = _load_probe()

    assert probe.LOCKED_LAMBDAS == (0.01, 100.0)
    assert {case: expected["move"] for case, expected in probe.LOCKED_EXPECTED.items()} == {
        "b18_base": "R2",
        "b18_profile_zero": "R2",
        "b18_pikl_low": "R2",
        "b18_pikl_high": "O6",
    }
    assert probe.LOCKED_EXPECTED["b18_pikl_low"]["orders"] == {"R2": 0, "O6": 1}
    assert probe.LOCKED_EXPECTED["b18_pikl_high"]["orders"] == {"R2": 1, "O6": 0}


def test_validate_results_checks_ids_attestation_wire_fingerprints_and_semantics():
    probe = _load_probe()
    requests, responses = _valid_exchange(probe)

    summary = _validate(probe, requests, responses)

    assert summary["passed"] is True
    assert summary["selected_moves"] == {
        "b18_base": "R2",
        "b18_profile_zero": "R2",
        "b18_pikl_low": "R2",
        "b18_pikl_high": "O6",
        "b28_base": "O6",
    }
    assert summary["request_fingerprints"] == {
        case: probe.fingerprint_wire_body(body) for case, body in requests.items()
    }
    assert all(value > 0 for value in summary["pikl_play_selection_values"]["low"].values())


def test_validate_results_rejects_response_id_mismatch():
    probe = _load_probe()
    requests, responses = _valid_exchange(probe)
    responses["b18_pikl_low"]["id"] = requests["b18_pikl_high"]["id"]

    with pytest.raises(ValueError, match="response id"):
        _validate(probe, requests, responses)


def test_validate_results_rejects_wrong_model_attestation():
    probe = _load_probe()
    requests, responses = _valid_exchange(probe)
    responses["b18_pikl_low"]["_wrapper"]["selected_model"] = "b28"

    with pytest.raises(ValueError, match="attestation"):
        _validate(probe, requests, responses)


def test_control_nondeterminism_cannot_masquerade_as_lambda_effect():
    probe = _load_probe()
    requests, responses = _valid_exchange(probe)
    # The old two-group validator accepted this shape when each lambda's controls
    # drifted along with its PIKL result. A single locked control must now fail.
    responses["b18_profile_zero"] = _analysis(
        "b18", requests["b18_profile_zero"]["id"], ["O6", "R2"], [30.0, 12.0], [0, 1]
    )

    with pytest.raises(ValueError, match="locked fixture"):
        _validate(probe, requests, responses)


def test_locked_pikl_comparison_rejects_zero_psv_ties():
    probe = _load_probe()
    requests, responses = _valid_exchange(probe)
    responses["b18_pikl_low"]["moveInfos"][1]["playSelectionValue"] = 0.0

    with pytest.raises(ValueError, match="stable positive"):
        _validate(probe, requests, responses)


@pytest.mark.parametrize("bad_value", [True, math.nan, math.inf, -math.inf])
def test_observation_rejects_non_plain_or_nonfinite_psv(bad_value):
    probe = _load_probe()
    requests, responses = _valid_exchange(probe)
    responses["b18_pikl_low"]["moveInfos"][0]["playSelectionValue"] = bad_value

    with pytest.raises(ValueError, match="playSelectionValue"):
        _validate(probe, requests, responses)


def test_result_writer_is_collision_safe_and_strict_json(tmp_path, monkeypatch):
    probe = _load_probe()
    monkeypatch.setattr(probe, "RESULTS_DIR", tmp_path)

    output = probe.write_result({"passed": True}, timestamp="20260722T012345.123456Z", run_id="abc123")

    assert output == tmp_path / "humansl_semantic_probe_20260722T012345.123456Z_abc123.json"
    assert json.loads(output.read_text()) == {"passed": True}
    with pytest.raises(FileExistsError):
        probe.write_result({"passed": False}, timestamp="20260722T012345.123456Z", run_id="abc123")
    with pytest.raises(ValueError, match="JSON"):
        probe.write_result({"bad": math.nan}, timestamp="20260722T012346.123456Z", run_id="def456")


@pytest.mark.asyncio
async def test_run_probe_posts_exactly_five_and_persists_exact_wire_bodies(tmp_path, monkeypatch):
    probe = _load_probe()
    monkeypatch.setattr(probe, "RESULTS_DIR", tmp_path)
    posted = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=_health())
        body = json.loads(request.content)
        posted.append(body)
        case = body["id"].rsplit(":", 1)[1]
        expected_alias = "b28" if case == "b28_base" else "b18"
        moves = ["O6", "R2"] if case in {"b18_pikl_high", "b28_base"} else ["R2", "O6"]
        values = [35.0, 23.0] if moves[0] == "O6" else [85.0, 0.5]
        return httpx.Response(200, json=_analysis(expected_alias, body["id"], moves, values, [0, 1]))

    transport = httpx.MockTransport(handler)
    payload, output = await probe.run_probe("http://127.0.0.1:8000", run_id="fixed-run", transport=transport)

    assert len(posted) == 5
    assert posted == list(payload["wire_requests"].values())
    assert payload["summary"]["request_fingerprints"] == {
        case: probe.fingerprint_wire_body(body) for case, body in payload["wire_requests"].items()
    }
    assert json.loads(output.read_text())["wire_requests"] == payload["wire_requests"]


@pytest.mark.asyncio
async def test_written_result_roundtrips_and_revalidates_after_sorted_json(tmp_path, monkeypatch):
    probe = _load_probe()
    monkeypatch.setattr(probe, "RESULTS_DIR", tmp_path)

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=_health())
        body = json.loads(request.content)
        case = body["id"].rsplit(":", 1)[1]
        alias = "b28" if case == "b28_base" else "b18"
        moves = ["O6", "R2"] if case in {"b18_pikl_high", "b28_base"} else ["R2", "O6"]
        values = [35.0, 23.0] if moves[0] == "O6" else [85.0, 0.5]
        return httpx.Response(200, json=_analysis(alias, body["id"], moves, values, [0, 1]))

    _, output = await probe.run_probe(
        "http://127.0.0.1:8000", run_id="roundtrip", transport=httpx.MockTransport(handler)
    )
    saved = json.loads(output.read_text())

    assert saved["case_order"] == list(probe.PROBE_CASES)
    assert list(saved["wire_requests"]) != saved["case_order"]  # sort_keys reordered the mapping
    summary = probe.validate_probe_results(
        saved["health"], saved["wire_requests"], saved["responses"], case_order=saved["case_order"]
    )
    assert summary["passed"] is True


def test_validator_rejects_wrong_explicit_case_order_but_not_mapping_key_order():
    probe = _load_probe()
    requests, responses = _valid_exchange(probe)
    sorted_requests = dict(sorted(requests.items()))
    sorted_responses = dict(sorted(responses.items()))

    assert probe.validate_probe_results(
        _health(), sorted_requests, sorted_responses, case_order=list(probe.PROBE_CASES)
    )["passed"]
    with pytest.raises(ValueError, match="case_order"):
        probe.validate_probe_results(
            _health(), sorted_requests, sorted_responses, case_order=list(reversed(probe.PROBE_CASES))
        )
