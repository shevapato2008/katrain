#!/usr/bin/env python3
"""Fail-closed, local-only semantic probe for b18 + humanv0 PIKL search."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from katrain.core.ladder import HUMANSL_PIKL_BASELINE


RESULTS_DIR = Path(__file__).parent / "results" / "semantic_probe"
LOCKED_PROFILE = "rank_9d"
LOCKED_VISITS = 500
LOCKED_LAMBDAS = (0.000001, 100.0)

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

PIKL_BASELINE = dict(HUMANSL_PIKL_BASELINE)
HUMANSL_BLEND_KEYS = (
    "humanSLChosenMoveProp",
    "humanSLRootExploreProbWeightless",
    "humanSLCpuctPermanent",
    "subtreeValueBiasFactor",
)

# Representative discovery values are documentation, not brittle numeric
# assertions. The executable contract locks the selected move and relative order;
# exact PSV varies slightly with multithreaded search.
LOCKED_EXPECTED = {
    LOCKED_LAMBDAS[0]: {
        "move": "R2",
        "play_selection_values": {"R2": 88.0, "O6": 0.0},
        "orders": {"R2": 0, "O6": 1},
    },
    LOCKED_LAMBDAS[1]: {
        "move": "O6",
        "play_selection_values": {"R2": 28.12, "O6": 42.15},
        "orders": {"R2": 1, "O6": 0},
    },
}

_IDENTITY_KEYS = (
    "selected_model",
    "model_path",
    "model_sha256",
    "human_model_path",
    "human_model_sha256",
    "katago_version",
)


def _base_query() -> dict:
    return {
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


def build_probe_requests(pikl_lambda: float) -> dict[str, dict]:
    if pikl_lambda not in LOCKED_LAMBDAS:
        raise ValueError(f"lambda must be one of the locked values {LOCKED_LAMBDAS!r}")
    base = _base_query()
    zero_recipe = dict(PIKL_BASELINE)
    zero_recipe.update({key: 0.0 for key in HUMANSL_BLEND_KEYS})
    pikl_recipe = dict(PIKL_BASELINE)
    pikl_recipe["humanSLChosenMovePiklLambda"] = pikl_lambda
    return {
        "b18_base": {**deepcopy(base), "overrideSettings": {"model": "b18"}},
        "b18_profile_zero": {
            **deepcopy(base),
            "overrideSettings": {"model": "b18", "humanSLProfile": LOCKED_PROFILE, **zero_recipe},
        },
        "b18_pikl": {
            **deepcopy(base),
            "overrideSettings": {"model": "b18", "humanSLProfile": LOCKED_PROFILE, **pikl_recipe},
        },
        "b28_base": {**deepcopy(base), "overrideSettings": {"model": "b28"}},
    }


def _fingerprint(value: dict) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
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
        if not isinstance(move, str) or not isinstance(value, (int, float)) or type(order) is not int:
            raise ValueError("analysis lacks move/playSelectionValue/order")
        rows[move] = {"playSelectionValue": float(value), "order": order}
        if order == 0:
            selected.append(move)
    if len(selected) != 1:
        raise ValueError("analysis must have exactly one order=0 move")
    return {"selected_move": selected[0], "moves": rows}


def validate_probe_results(health: dict, responses: dict[str, dict[str, dict]]) -> dict:
    identities = {alias: _health_identity(health, alias) for alias in ("b18", "b28")}
    observations = {}
    fingerprints = {}
    expected_aliases = {"b18_base": "b18", "b18_profile_zero": "b18", "b18_pikl": "b18", "b28_base": "b28"}

    for pikl_lambda in LOCKED_LAMBDAS:
        lambda_key = str(pikl_lambda)
        group = responses.get(lambda_key)
        if not isinstance(group, dict) or set(group) != set(expected_aliases):
            raise ValueError(f"responses for lambda {lambda_key} do not contain the exact four probe cases")
        observations[lambda_key] = {}
        requests = build_probe_requests(pikl_lambda)
        for case, alias in expected_aliases.items():
            _validate_attestation(group[case], identities[alias])
            observations[lambda_key][case] = _observation(group[case])
            fingerprints[f"{lambda_key}:{case}"] = _fingerprint(requests[case])

        base_move = observations[lambda_key]["b18_base"]["selected_move"]
        zero_move = observations[lambda_key]["b18_profile_zero"]["selected_move"]
        if base_move != zero_move:
            raise ValueError("b18 profile-only zero-blend selection differs from b18 base")

    low_key, high_key = map(str, LOCKED_LAMBDAS)
    low = observations[low_key]["b18_pikl"]
    high = observations[high_key]["b18_pikl"]
    if low["selected_move"] != LOCKED_EXPECTED[LOCKED_LAMBDAS[0]]["move"]:
        raise ValueError("low-lambda selected move drifted from the locked fixture")
    if high["selected_move"] != LOCKED_EXPECTED[LOCKED_LAMBDAS[1]]["move"]:
        raise ValueError("high-lambda selected move drifted from the locked fixture")

    watched = set(LOCKED_EXPECTED[LOCKED_LAMBDAS[0]]["orders"])
    if not watched.issubset(low["moves"]) or not watched.issubset(high["moves"]):
        raise ValueError("locked PIKL comparison moves are missing")
    low_values = {move: low["moves"][move]["playSelectionValue"] for move in watched}
    high_values = {move: high["moves"][move]["playSelectionValue"] for move in watched}
    low_orders = {move: low["moves"][move]["order"] for move in watched}
    high_orders = {move: high["moves"][move]["order"] for move in watched}
    if low_values == high_values:
        raise ValueError("changing PIKL lambda did not change playSelectionValue")
    if low_orders == high_orders:
        raise ValueError("changing PIKL lambda did not change move order")

    # Stable convenience aliases for callers; all lambda-independent requests
    # have the same fingerprints in both groups.
    request_fingerprints = {case: fingerprints[f"{low_key}:{case}"] for case in expected_aliases}
    request_fingerprints["b18_pikl_high"] = fingerprints[f"{high_key}:b18_pikl"]
    if request_fingerprints["b18_base"] == request_fingerprints["b28_base"]:
        raise ValueError("b18 and b28 request fingerprints unexpectedly match")

    return {
        "passed": True,
        "selected_moves": {low_key: low["selected_move"], high_key: high["selected_move"]},
        "pikl_play_selection_values": {low_key: low_values, high_key: high_values},
        "pikl_orders": {low_key: low_orders, high_key: high_orders},
        "request_fingerprints": request_fingerprints,
        "observations": observations,
    }


def write_result(payload: dict, timestamp: str | None = None) -> Path:
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output = RESULTS_DIR / f"humansl_semantic_probe_{stamp}.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def _assert_local_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("semantic probe is local-only; base URL must use a loopback host")
    return base_url.rstrip("/")


async def run_probe(base_url: str) -> tuple[dict, Path]:
    base_url = _assert_local_url(base_url)
    timeout = httpx.Timeout(180.0, connect=10.0)
    responses = {}
    requests_record = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        health_response = await client.get(f"{base_url}/health")
        health_response.raise_for_status()
        health = health_response.json()
        for pikl_lambda in LOCKED_LAMBDAS:
            lambda_key = str(pikl_lambda)
            responses[lambda_key] = {}
            requests_record[lambda_key] = {}
            for case, query in build_probe_requests(pikl_lambda).items():
                wire_query = deepcopy(query)
                wire_query["id"] = f"semantic-probe-{lambda_key}-{case}"
                response = await client.post(f"{base_url}/analyze", json=wire_query)
                response.raise_for_status()
                responses[lambda_key][case] = response.json()
                requests_record[lambda_key][case] = query

    summary = validate_probe_results(health, responses)
    payload = {
        "probe_schema": 1,
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
        "requests": requests_record,
        "responses": responses,
        "summary": summary,
        "passed": True,
    }
    return payload, write_result(payload)


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
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
