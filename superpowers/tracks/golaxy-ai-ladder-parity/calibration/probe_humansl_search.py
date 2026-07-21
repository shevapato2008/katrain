#!/usr/bin/env python3
"""Fail-closed, local-only semantic probe for b18 + humanv0 PIKL search."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from katrain.core.ladder import HUMANSL_PIKL_BASELINE, LadderRung, rung_strength_spec


RESULTS_DIR = Path(__file__).parent / "results" / "semantic_probe"
LOCKED_PROFILE = "rank_9d"
LOCKED_VISITS = 500
LOCKED_LAMBDAS = (0.01, 100.0)

# First 20 moves of tests/data/fox sgf works.sgf, copied here deliberately so
# the executable probe cannot drift when an unrelated SGF fixture is edited.
LOCKED_HISTORY = [
    ["B", "Q16"],
    ["W", "D4"],
    ["B", "Q4"],
    ["W", "D16"],
    ["B", "F17"],
    ["W", "R3"],
    ["B", "Q3"],
    ["W", "R4"],
    ["B", "R6"],
    ["W", "R5"],
    ["B", "Q6"],
    ["W", "Q5"],
    ["B", "P5"],
    ["W", "S6"],
    ["B", "S7"],
    ["W", "T6"],
    ["B", "R8"],
    ["W", "R14"],
    ["B", "O17"],
    ["W", "R11"],
]

HUMANSL_BLEND_KEYS = (
    "humanSLChosenMoveProp",
    "humanSLRootExploreProbWeightless",
    "humanSLCpuctPermanent",
    "subtreeValueBiasFactor",
)
LOCKED_EXPECTED = {
    "b18_base": {"move": "R2", "orders": {"R2": 0, "O6": 1}},
    "b18_profile_zero": {"move": "R2", "orders": {"R2": 0, "O6": 1}},
    "b18_pikl_low": {"move": "R2", "orders": {"R2": 0, "O6": 1}},
    "b18_pikl_high": {"move": "O6", "orders": {"R2": 1, "O6": 0}},
}
PROBE_CASES = ("b18_base", "b18_profile_zero", "b18_pikl_low", "b18_pikl_high", "b28_base")
_IDENTITY_KEYS = (
    "selected_model",
    "model_path",
    "model_sha256",
    "human_model_path",
    "human_model_sha256",
    "katago_version",
)
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9-]+$")


def _rung(*, model: str, mechanism: str, profile: str | None = None, params: dict | None = None) -> LadderRung:
    return LadderRung(
        rung=0,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank=profile or model,
        rank_name=profile or model,
        net=model,
        mechanism=mechanism,
        human_sl_profile=profile,
        max_visits=LOCKED_VISITS,
        human_sl_params=params or {},
    )


def _net_overrides(model: str) -> dict:
    return dict(rung_strength_spec(_rung(model=model, mechanism="net_search")).override_settings)


def _pikl_overrides(pikl_lambda: float) -> dict:
    params = dict(HUMANSL_PIKL_BASELINE)
    params["humanSLChosenMovePiklLambda"] = pikl_lambda
    spec = rung_strength_spec(_rung(model="b18", mechanism="humansl_search", profile=LOCKED_PROFILE, params=params))
    return dict(spec.override_settings)


def _base_query(case: str, run_id: str) -> dict:
    return {
        "id": f"semantic-probe-{run_id}:{case}",
        "rules": "chinese",
        "komi": 7.5,
        "boardXSize": 19,
        "boardYSize": 19,
        "moves": deepcopy(LOCKED_HISTORY),
        "analyzeTurns": [len(LOCKED_HISTORY)],
        "maxVisits": LOCKED_VISITS,
        "includePolicy": True,
        "includeOwnership": False,
    }


def _validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("run_id must contain only ASCII letters, digits, and hyphens")
    return run_id


def build_probe_requests(run_id: str) -> dict[str, dict]:
    """Build the exact five JSON bodies posted by one probe run."""
    run_id = _validate_run_id(run_id)
    low_overrides = _pikl_overrides(LOCKED_LAMBDAS[0])
    high_overrides = _pikl_overrides(LOCKED_LAMBDAS[1])
    zero_overrides = _pikl_overrides(HUMANSL_PIKL_BASELINE["humanSLChosenMovePiklLambda"])
    zero_overrides.update({key: 0.0 for key in HUMANSL_BLEND_KEYS})
    overrides = {
        "b18_base": {"model": "b18", **_net_overrides("b18")},
        "b18_profile_zero": {"model": "b18", **zero_overrides},
        "b18_pikl_low": {"model": "b18", **low_overrides},
        "b18_pikl_high": {"model": "b18", **high_overrides},
        "b28_base": {"model": "b28", **_net_overrides("b28")},
    }
    return {case: {**_base_query(case, run_id), "overrideSettings": overrides[case]} for case in PROBE_CASES}


def fingerprint_wire_body(value: dict) -> str:
    try:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("wire body is not strict JSON") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _health_identity(health: dict, alias: str) -> dict:
    if health.get("capability_schema") != 1:
        raise ValueError("health capability schema is not 1")
    models = health.get("models")
    model = models.get(alias) if isinstance(models, dict) else None
    if not isinstance(model, dict) or model.get("running") is not True:
        raise ValueError(f"health does not advertise running model {alias!r}")
    for key in ("model_path", "model_sha256", "human_model_path", "human_model_sha256"):
        if not isinstance(model.get(key), str) or not model[key]:
            raise ValueError(f"health model {alias!r} has no {key}")
    if model.get("model_sha256_verified") is not True or model.get("human_model_sha256_verified") is not True:
        raise ValueError(f"health model {alias!r} is not checksum verified")
    if model.get("has_human_model") is not True:
        raise ValueError(f"health model {alias!r} has no human model")
    version = health.get("katago_version")
    if not isinstance(version, str) or not version.startswith("KataGo v"):
        raise ValueError("health has no KataGo version")
    return {
        "selected_model": alias,
        "model_path": model["model_path"],
        "model_sha256": model["model_sha256"],
        "human_model_path": model["human_model_path"],
        "human_model_sha256": model["human_model_sha256"],
        "katago_version": version,
    }


def _validate_attestation(response: dict, expected: dict) -> None:
    wrapper = response.get("_wrapper")
    if not isinstance(wrapper, dict) or any(wrapper.get(key) != expected[key] for key in _IDENTITY_KEYS):
        raise ValueError(f"response attestation does not match health identity for {expected['selected_model']!r}")


def _observation(response: dict) -> dict:
    infos = response.get("moveInfos")
    if not isinstance(infos, list) or not infos:
        raise ValueError("analysis has no moveInfos")
    rows = {}
    selected = []
    for info in infos:
        if not isinstance(info, dict):
            raise ValueError("analysis has malformed moveInfos")
        move, value, order = info.get("move"), info.get("playSelectionValue"), info.get("order")
        if not isinstance(move, str) or type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("analysis has malformed move/playSelectionValue")
        if type(order) is not int:
            raise ValueError("analysis has malformed order")
        rows[move] = {"playSelectionValue": float(value), "order": order}
        if order == 0:
            selected.append(move)
    if len(selected) != 1:
        raise ValueError("analysis must have exactly one order=0 move")
    return {"selected_move": selected[0], "moves": rows, "root_info": response.get("rootInfo")}


def validate_probe_results(health: dict, wire_requests: dict[str, dict], responses: dict[str, dict]) -> dict:
    if list(wire_requests) != list(PROBE_CASES) or set(responses) != set(PROBE_CASES):
        raise ValueError("probe exchange must contain the exact five cases")
    identities = {alias: _health_identity(health, alias) for alias in ("b18", "b28")}
    observations = {}
    fingerprints = {}
    for case in PROBE_CASES:
        request = wire_requests[case]
        response = responses[case]
        expected_id = request.get("id")
        if not isinstance(expected_id, str) or response.get("id") != expected_id:
            raise ValueError(f"response id mismatch for {case}")
        alias = "b28" if case == "b28_base" else "b18"
        if request.get("overrideSettings", {}).get("model") != alias:
            raise ValueError(f"wire request model mismatch for {case}")
        _validate_attestation(response, identities[alias])
        observations[case] = _observation(response)
        fingerprints[case] = fingerprint_wire_body(request)

    watched = {"R2", "O6"}
    for case, expected in LOCKED_EXPECTED.items():
        observation = observations[case]
        if observation["selected_move"] != expected["move"]:
            raise ValueError(f"{case} selected move drifted from the locked fixture")
        if not watched.issubset(observation["moves"]):
            raise ValueError(f"{case} locked comparison moves are missing")
        orders = {move: observation["moves"][move]["order"] for move in watched}
        if orders != expected["orders"]:
            raise ValueError(f"{case} order drifted from the locked fixture")

    control = observations["b18_base"]
    zero = observations["b18_profile_zero"]
    low = observations["b18_pikl_low"]
    high = observations["b18_pikl_high"]
    if not (control["selected_move"] == zero["selected_move"] == low["selected_move"]):
        raise ValueError("same-run b18 controls and low-lambda selection are unstable")
    low_values = {move: low["moves"][move]["playSelectionValue"] for move in watched}
    high_values = {move: high["moves"][move]["playSelectionValue"] for move in watched}
    low_orders = {move: low["moves"][move]["order"] for move in watched}
    high_orders = {move: high["moves"][move]["order"] for move in watched}
    if low_values == high_values:
        raise ValueError("changing PIKL lambda did not change playSelectionValue")
    if any(value <= 0.0 for value in (*low_values.values(), *high_values.values())):
        raise ValueError("locked PIKL comparison requires stable positive playSelectionValue values")
    if low_orders == high_orders or low["selected_move"] == high["selected_move"]:
        raise ValueError("changing PIKL lambda did not change order=0 move")
    if fingerprints["b18_base"] == fingerprints["b28_base"]:
        raise ValueError("b18 and b28 request fingerprints unexpectedly match")

    return {
        "passed": True,
        "selected_moves": {case: observations[case]["selected_move"] for case in PROBE_CASES},
        "pikl_play_selection_values": {"low": low_values, "high": high_values},
        "pikl_orders": {"low": low_orders, "high": high_orders},
        "request_fingerprints": fingerprints,
        "observations": observations,
    }


def write_result(payload: dict, *, timestamp: str | None = None, run_id: str) -> Path:
    run_id = _validate_run_id(run_id)
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    try:
        encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise ValueError("result is not strict JSON") from exc
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output = RESULTS_DIR / f"humansl_semantic_probe_{stamp}_{run_id}.json"
    with output.open("x", encoding="utf-8") as result_file:
        result_file.write(encoded)
    return output


def _assert_local_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("semantic probe is local-only; base URL must use a loopback host")
    return base_url.rstrip("/")


async def run_probe(
    base_url: str, *, run_id: str | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> tuple[dict, Path]:
    base_url = _assert_local_url(base_url)
    run_id = _validate_run_id(run_id or uuid.uuid4().hex[:12])
    timeout = httpx.Timeout(180.0, connect=10.0)
    wire_requests = build_probe_requests(run_id)
    responses = {}
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        health_response = await client.get(f"{base_url}/health")
        health_response.raise_for_status()
        health = health_response.json()
        for case, wire_body in wire_requests.items():
            response = await client.post(f"{base_url}/analyze", json=wire_body)
            response.raise_for_status()
            responses[case] = response.json()

    summary = validate_probe_results(health, wire_requests, responses)
    payload = {
        "probe_schema": 2,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "locked_fixture": {
            "history": LOCKED_HISTORY,
            "profile": LOCKED_PROFILE,
            "visits": LOCKED_VISITS,
            "lambdas": LOCKED_LAMBDAS,
            "expected": LOCKED_EXPECTED,
        },
        "health": health,
        "wire_requests": wire_requests,
        "responses": responses,
        "summary": summary,
        "passed": True,
    }
    return payload, write_result(payload, run_id=run_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        payload, output = asyncio.run(run_probe(args.base_url))
    except Exception as exc:
        print(f"FAILED: {exc}")
        return 1
    print(f"PASS: {output}")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
