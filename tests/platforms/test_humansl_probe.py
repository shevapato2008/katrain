import importlib.util
import json
from pathlib import Path

import pytest


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


def _analysis(alias, move, psv, order):
    return {
        "moveInfos": [
            {"move": candidate, "playSelectionValue": value, "order": rank}
            for candidate, value, rank in zip(move, psv, order)
        ],
        "rootInfo": {"visits": 40, "scoreLead": 0.5},
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


def test_builds_exact_four_requests_for_each_locked_lambda():
    probe = _load_probe()

    assert len(probe.LOCKED_HISTORY) > 1
    assert len(probe.LOCKED_LAMBDAS) == 2
    assert all(value > 0 for value in probe.LOCKED_LAMBDAS)
    for pikl_lambda in probe.LOCKED_LAMBDAS:
        requests = probe.build_probe_requests(pikl_lambda)
        assert list(requests) == ["b18_base", "b18_profile_zero", "b18_pikl", "b28_base"]
        assert all(query["moves"] == probe.LOCKED_HISTORY for query in requests.values())
        assert all(query["maxVisits"] == probe.LOCKED_VISITS for query in requests.values())
        assert requests["b18_base"]["overrideSettings"] == {"model": "b18"}
        assert requests["b28_base"]["overrideSettings"] == {"model": "b28"}

        zero = requests["b18_profile_zero"]["overrideSettings"]
        assert zero["model"] == "b18"
        assert zero["humanSLProfile"] == probe.LOCKED_PROFILE
        assert all(zero[key] == 0.0 for key in probe.HUMANSL_BLEND_KEYS)

        pikl = requests["b18_pikl"]["overrideSettings"]
        assert pikl["model"] == "b18"
        assert pikl["humanSLProfile"] == probe.LOCKED_PROFILE
        assert pikl["humanSLChosenMovePiklLambda"] == pikl_lambda
        assert {key: pikl[key] for key in probe.PIKL_BASELINE} == {
            **probe.PIKL_BASELINE,
            "humanSLChosenMovePiklLambda": pikl_lambda,
        }


def test_locked_fixture_declares_different_pikl_moves_values_and_orders():
    probe = _load_probe()

    low, high = probe.LOCKED_LAMBDAS
    assert probe.LOCKED_EXPECTED[low]["move"] != probe.LOCKED_EXPECTED[high]["move"]
    assert probe.LOCKED_EXPECTED[low]["play_selection_values"] != probe.LOCKED_EXPECTED[high]["play_selection_values"]
    assert probe.LOCKED_EXPECTED[low]["orders"] != probe.LOCKED_EXPECTED[high]["orders"]


def test_validate_results_checks_attestation_and_semantic_differences():
    probe = _load_probe()
    low, high = probe.LOCKED_LAMBDAS
    low_move = probe.LOCKED_EXPECTED[low]["move"]
    high_move = probe.LOCKED_EXPECTED[high]["move"]
    other = "pass" if low_move != "pass" and high_move != "pass" else "A1"
    responses = {
        str(low): {
            "b18_base": _analysis("b18", [low_move, other], [10.0, 9.0], [0, 1]),
            "b18_profile_zero": _analysis("b18", [low_move, other], [10.0, 9.0], [0, 1]),
            "b18_pikl": _analysis("b18", [low_move, high_move], [10.0, 9.0], [0, 1]),
            "b28_base": _analysis("b28", [other, low_move], [11.0, 8.0], [0, 1]),
        },
        str(high): {
            "b18_base": _analysis("b18", [low_move, other], [10.0, 9.0], [0, 1]),
            "b18_profile_zero": _analysis("b18", [low_move, other], [10.0, 9.0], [0, 1]),
            "b18_pikl": _analysis("b18", [high_move, low_move], [12.0, 7.0], [0, 1]),
            "b28_base": _analysis("b28", [other, low_move], [11.0, 8.0], [0, 1]),
        },
    }

    summary = probe.validate_probe_results(_health(), responses)

    assert summary["passed"] is True
    assert summary["selected_moves"][str(low)] == low_move
    assert summary["selected_moves"][str(high)] == high_move
    assert summary["request_fingerprints"]["b18_base"] != summary["request_fingerprints"]["b28_base"]


def test_validate_results_rejects_wrong_model_attestation():
    probe = _load_probe()
    low, high = probe.LOCKED_LAMBDAS
    low_move = probe.LOCKED_EXPECTED[low]["move"]
    high_move = probe.LOCKED_EXPECTED[high]["move"]
    responses = {}
    for value, move in ((low, low_move), (high, high_move)):
        responses[str(value)] = {
            "b18_base": _analysis("b18", [move, "pass"], [2.0, 1.0], [0, 1]),
            "b18_profile_zero": _analysis("b18", [move, "pass"], [2.0, 1.0], [0, 1]),
            "b18_pikl": _analysis("b18", [move, "pass"], [3.0, 1.0], [0, 1]),
            "b28_base": _analysis("b28", ["pass", move], [2.0, 1.0], [0, 1]),
        }
    responses[str(low)]["b18_pikl"]["_wrapper"]["selected_model"] = "b28"

    with pytest.raises(ValueError, match="attestation"):
        probe.validate_probe_results(_health(), responses)


def test_result_writer_uses_timestamped_semantic_probe_namespace(tmp_path, monkeypatch):
    probe = _load_probe()
    monkeypatch.setattr(probe, "RESULTS_DIR", tmp_path)

    output = probe.write_result({"passed": True}, timestamp="20260722T012345Z")

    assert output == tmp_path / "humansl_semantic_probe_20260722T012345Z.json"
    assert json.loads(output.read_text()) == {"passed": True}
