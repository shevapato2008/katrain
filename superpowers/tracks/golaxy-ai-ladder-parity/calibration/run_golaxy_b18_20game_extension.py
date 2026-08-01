#!/usr/bin/env python3
"""Strict live runner for the frozen Golaxy b18 three-star extension."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import fcntl
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Mapping

import httpx

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]
for _path in (str(_REPO_ROOT), str(_SCRIPT_DIR)):
    while _path in sys.path:
        sys.path.remove(_path)
sys.path[:0] = [str(_REPO_ROOT), str(_SCRIPT_DIR)]
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")

with redirect_stdout(io.StringIO()):
    import adapters  # noqa: E402
    import golaxy_b18_20game_extension as protocol  # noqa: E402
    import run_golaxy_9d_alignment  # noqa: E402

from katrain.core.engine import BaseEngine  # noqa: E402
from katrain.core.ladder import (
    LadderMoveError,
    LadderRung,
    LadderStrengthSpec,
    colrow_to_golaxy,
    pick_ladder_move,
    rung_strength_spec,
    validate_analysis_attestation,
)  # noqa: E402
from katrain.core.ladder_calibration import GameOutcome, play_one_game  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
BOARD_SIZE = 19
RULES = "chinese"
KOMI = 7.5
WIDE_ROOT_NOISE = 0.04
MOVE_CAP = 400
REFEREE_VISITS = 200
STABILITY_VISITS = 800
STABILITY_DELTA = 1.0
COOLDOWN_SECONDS = 5.0
DEFAULT_SMOKE_REPORT = run_golaxy_9d_alignment.DEFAULT_SMOKE_REPORT


@dataclass(frozen=True)
class PreflightProof:
    health_canonical: str
    health_sha256: str
    token: str
    pass_code: int
    resign_code: int
    b18_identity_canonical: str
    b28_identity_canonical: str

    @property
    def health(self) -> dict:
        return json.loads(self.health_canonical)


class CampaignStopped(RuntimeError):
    """A play failure was durably closed in the ledger."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def make_player(visits: int) -> LadderRung:
    if type(visits) is not int or visits not in protocol.CANDIDATE_VISITS:
        raise ValueError("candidate visits must be exactly 32 or 64")
    rung = LadderRung(
        rung=0,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank=f"b18@{visits}",
        rank_name=f"b18@{visits}",
        net=protocol.MODEL,
        mechanism="net_search",
        human_sl_profile=None,
        max_visits=visits,
        human_sl_params={},
        backend_hint="server",
        root_policy_temperature=1.0,
    )
    spec = rung_strength_spec(rung)
    if (
        spec.main_model != "b18"
        or spec.human_model is not None
        or dict(spec.override_settings) != {"reportAnalysisWinratesAs": "BLACK"}
    ):
        raise ValueError("pure b18 player construction drift")
    return rung


def build_player_query(history: list, visits: int) -> dict:
    query = adapters.build_ladder_analysis_query(history, make_player(visits), BOARD_SIZE, KOMI, RULES, WIDE_ROOT_NOISE)
    expected_overrides = {"reportAnalysisWinratesAs": "BLACK", "wideRootNoise": WIDE_ROOT_NOISE, "model": "b18"}
    if query.get("overrideSettings") != expected_overrides or "humanSLProfile" in query["overrideSettings"]:
        raise ValueError("pure b18 query construction drift")
    return query


def validate_complete_health(health: object) -> tuple[str, str]:
    if not isinstance(health, Mapping):
        raise ValueError("complete health response must be a mapping")
    copied = json.loads(_canonical_json(health))
    if copied.get("status") != "ok":
        raise ValueError("health status must be exactly ok")
    try:
        adapters.retain_health_snapshot(copied)
    except ValueError as exc:
        raise ValueError(f"invalid complete health response: {exc}") from exc
    models = copied.get("models")
    if not isinstance(models, Mapping):
        raise ValueError("health models must be a mapping")
    for alias, expected_sha in (("b18", protocol.MODEL_SHA256), ("b28", protocol.REFEREE_MODEL_SHA256)):
        identity = models.get(alias)
        if not isinstance(identity, Mapping):
            raise ValueError(f"health is missing {alias} identity")
        if identity.get("running") is not True:
            raise ValueError(f"health {alias} is not running")
        if identity.get("model_sha256_verified") is not True or identity.get("model_sha256") != expected_sha:
            raise ValueError(f"health {alias} model SHA256 is not the frozen verified identity")
        if not isinstance(identity.get("model_path"), str) or not identity["model_path"]:
            raise ValueError(f"health {alias} model path is invalid")
    default_model = copied.get("default_model")
    if (
        default_model not in models
        or not isinstance(models[default_model], Mapping)
        or models[default_model].get("running") is not True
    ):
        raise ValueError("health default model is not applicable to requests")
    canonical = _canonical_json(copied)
    return canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _identity(health: Mapping[str, object], alias: str) -> dict:
    model = health["models"][alias]
    return {
        "selected_model": alias,
        "model_path": model["model_path"],
        "model_sha256": model["model_sha256"],
        "human_model_path": model.get("human_model_path"),
        "human_model_sha256": model.get("human_model_sha256"),
        "katago_version": health["katago_version"],
    }


def select_player_move(analysis: object, visits: int, health: Mapping[str, object]) -> int | str:
    rung = make_player(visits)
    if not isinstance(analysis, Mapping):
        raise LadderMoveError("analysis attestation: response is not a mapping")
    try:
        from katrain.core.ladder import validate_analysis_attestation

        validate_analysis_attestation(analysis, rung_strength_spec(rung), _identity(health, "b18"))
        root_info = analysis.get("rootInfo")
        reported_visits = root_info.get("visits") if isinstance(root_info, Mapping) else None
        run_golaxy_9d_alignment.validate_reported_visits(reported_visits, visits)
        picked = pick_ladder_move(analysis, (BOARD_SIZE, BOARD_SIZE), rung.mechanism)
    except LadderMoveError as exc:
        raise LadderMoveError(f"analysis attestation or legal move validation failed: {exc}") from exc
    return "pass" if picked == "pass" else colrow_to_golaxy(picked[0], picked[1], BOARD_SIZE)


async def analyze_player_move(client, history: list, visits: int, health: Mapping[str, object]) -> int | str:
    response = await client.post(
        f"{BASE_URL}/analyze", json=build_player_query(history, visits), timeout=httpx.Timeout(180.0, connect=10.0)
    )
    analysis = run_golaxy_9d_alignment._json_response(response, "/analyze")
    return select_player_move(analysis, visits, health)


async def fetch_complete_health(client) -> dict:
    response = await client.get(f"{BASE_URL}/health", timeout=httpx.Timeout(30.0, connect=10.0))
    return dict(run_golaxy_9d_alignment._json_response(response, "/health"))


async def _probe_player(client, visits: int, health: Mapping[str, object]) -> int | str:
    return await analyze_player_move(client, [], visits, health)


def build_referee_query(history: list, visits: int) -> dict:
    if type(visits) is not int or visits not in {REFEREE_VISITS, STABILITY_VISITS}:
        raise ValueError("referee visits must be exactly 200 or 800")
    return {
        "rules": BaseEngine.get_rules(RULES),
        "komi": KOMI,
        "boardXSize": BOARD_SIZE,
        "boardYSize": BOARD_SIZE,
        "moves": adapters._golaxy_history_to_gtp(history, BOARD_SIZE),
        "analyzeTurns": [len(history)],
        "maxVisits": visits,
        "includeOwnership": True,
        "includePolicy": False,
        "overrideSettings": {"reportAnalysisWinratesAs": "BLACK", "model": "b28"},
    }


async def _strict_referee_result(
    client, history: list, visits: int, health: Mapping[str, object]
) -> tuple[float | None, bool, int]:
    query = build_referee_query(history, visits)
    response = await client.post(f"{BASE_URL}/analyze", json=query, timeout=httpx.Timeout(180.0, connect=10.0))
    analysis = run_golaxy_9d_alignment._json_response(response, f"referee b28@{visits} /analyze")
    spec = LadderStrengthSpec(
        visits=visits,
        main_model="b28",
        human_model=None,
        override_settings={"reportAnalysisWinratesAs": "BLACK"},
    )
    validate_analysis_attestation(analysis, spec, _identity(health, "b28"))
    root = analysis.get("rootInfo")
    if not isinstance(root, Mapping):
        raise ValueError("referee rootInfo is missing or malformed")
    reported_visits = run_golaxy_9d_alignment.validate_reported_visits(root.get("visits"), visits)
    score = root.get("scoreLead")
    if score is None:
        return None, False, reported_visits
    if type(score) not in (int, float):
        raise ValueError("referee scoreLead must be a plain int or float when present")
    if not math.isfinite(score):
        return None, False, reported_visits
    score = float(score)
    ownership = analysis.get("ownership")
    if ownership is None:
        return score, False, reported_visits
    if type(ownership) is not list:
        raise ValueError("referee ownership must be a list when present")
    if len(ownership) != BOARD_SIZE * BOARD_SIZE:
        return score, False, reported_visits
    for value in ownership:
        if type(value) not in (int, float):
            raise ValueError("referee ownership values must be plain numeric values")
        if not math.isfinite(value):
            return score, False, reported_visits
    return score, adapters._is_settled(dict(analysis), BOARD_SIZE, score), reported_visits


async def strict_referee(client, history: list, visits: int, health: Mapping[str, object]) -> tuple[float | None, bool]:
    score, settled, _reported_visits = await _strict_referee_result(client, history, visits, health)
    return score, settled


async def _probe_referee(client, visits: int, health: Mapping[str, object]) -> dict:
    score, settled, reported_visits = await _strict_referee_result(client, [], visits, health)
    return {
        "requested_visits": visits,
        "reported_visits": reported_visits,
        "score": score,
        "settled": settled,
        "identity": _identity(health, "b28"),
        "effective_query": build_referee_query([], visits),
    }


async def preflight_campaign(
    local_client,
    *,
    expected_health: Mapping[str, object],
    fetch_health: Callable[[object], Awaitable[Mapping[str, object]]] = fetch_complete_health,
    probe_player: Callable[[object, int, Mapping[str, object]], Awaitable[object]] = _probe_player,
    probe_referee: Callable[[object, int, Mapping[str, object]], Awaitable[object]] = _probe_referee,
    token_loader: Callable[[str | None], str] = run_golaxy_9d_alignment.load_token,
    smoke_loader: Callable[[Path], Mapping[str, object]] = run_golaxy_9d_alignment.load_verified_smoke_codes,
    token_env: str | None = None,
    smoke_path: Path = DEFAULT_SMOKE_REPORT,
) -> PreflightProof:
    expected_canonical, expected_hash = validate_complete_health(expected_health)
    current = dict(await fetch_health(local_client))
    current_canonical, current_hash = validate_complete_health(current)
    if current_canonical != expected_canonical or current_hash != expected_hash:
        raise ValueError("complete health response differs from ledger header")
    for visits in protocol.CANDIDATE_VISITS:
        await probe_player(local_client, visits, current)
    for visits in (REFEREE_VISITS, STABILITY_VISITS):
        await probe_referee(local_client, visits, current)
    opponent = run_golaxy_9d_alignment.get_rung(protocol.GOLAXY_LEVEL)
    if (
        opponent.golaxy_api_level != protocol.GOLAXY_API_LEVEL
        or opponent.golaxy_level_name != protocol.GOLAXY_LEVEL_NAME
    ):
        raise ValueError("Golaxy rung 36 wire mapping drift")
    adapters._assert_real_wire_level(opponent.golaxy_api_level)
    token = token_loader(token_env)
    smoke = smoke_loader(Path(smoke_path))
    pass_code, resign_code = adapters._valid_sentinels(smoke.get("pass_code"), smoke.get("resign_code"), BOARD_SIZE)
    if pass_code is None or resign_code is None or pass_code == resign_code:
        raise ValueError("verified smoke pass/resign codes are invalid")
    return PreflightProof(
        current_canonical,
        current_hash,
        token,
        pass_code,
        resign_code,
        _canonical_json(_identity(current, "b18")),
        _canonical_json(_identity(current, "b28")),
    )


def _proof_matches_header(proof: PreflightProof, header: Mapping[str, object]) -> None:
    if not isinstance(proof, PreflightProof):
        raise ValueError("a complete PreflightProof is required")
    canonical, digest = validate_complete_health(header.get("complete_health_response"))
    if canonical != proof.health_canonical or digest != proof.health_sha256:
        raise ValueError("preflight proof does not match ledger header")
    health = json.loads(canonical)
    if proof.b18_identity_canonical != _canonical_json(_identity(health, "b18")) or proof.b28_identity_canonical != (
        _canonical_json(_identity(health, "b28"))
    ):
        raise ValueError("preflight proof model identities do not match its complete health response")
    if not proof.token.strip():
        raise ValueError("preflight proof has no Golaxy token")
    if adapters._valid_sentinels(proof.pass_code, proof.resign_code, BOARD_SIZE) != (
        proof.pass_code,
        proof.resign_code,
    ):
        raise ValueError("preflight proof smoke codes are invalid")


async def play_extension_game(
    local_client, golaxy_client, request: protocol.GameRequest, proof: PreflightProof
) -> GameOutcome:
    _proof_matches_header(proof, {"complete_health_response": proof.health})
    health = proof.health
    history_holder: dict[str, list | None] = {"history": None}

    async def our_move(history):
        history_holder["history"] = history
        return await analyze_player_move(local_client, history, request.visits, health)

    opponent = run_golaxy_9d_alignment.get_rung(protocol.GOLAXY_LEVEL)

    async def golaxy_move(history):
        history_holder["history"] = history
        return await adapters.golaxy_move(
            golaxy_client,
            history,
            rung=opponent,
            token=proof.token,
            board_size=BOARD_SIZE,
            komi=KOMI,
            rule=RULES,
            pass_code=proof.pass_code,
            resign_code=proof.resign_code,
        )

    async def adjudicate(history):
        history_holder["history"] = history
        return await strict_referee(local_client, history, REFEREE_VISITS, health)

    outcome = await play_one_game(
        our_move=our_move,
        golaxy_move=golaxy_move,
        adjudicate=adjudicate,
        our_color=request.color,
        board_size=BOARD_SIZE,
        move_cap=MOVE_CAP,
    )
    if outcome.result in {"inconclusive_engine", "inconclusive_terminal"}:
        raise RuntimeError(f"definite runtime stop: {outcome.result}")
    if outcome.conclusive and outcome.end_reason != "golaxy_resign":
        history = history_holder["history"]
        score, settled = await strict_referee(local_client, history, STABILITY_VISITS, health)
        if (
            score is None
            or outcome.black_score is None
            or not settled
            or abs(score - outcome.black_score) >= STABILITY_DELTA
        ):
            outcome = dataclasses.replace(outcome, result="inconclusive_unstable", our_win=False, conclusive=False)
    return outcome


@contextmanager
def campaign_output_lock(path: str | Path):
    requested = Path(path)
    cursor = requested.absolute()
    while True:
        if cursor.is_symlink():
            raise ValueError("campaign output may not traverse a symlink alias")
        if cursor == cursor.parent:
            break
        cursor = cursor.parent
    canonical = requested.resolve()
    lock_path = Path(f"{canonical}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"campaign output is locked by another writer: {canonical}") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _next_attempt_id(records: tuple[Mapping[str, object], ...]) -> int:
    return max((row["attempt_id"] for row in records if row.get("type") == "reservation"), default=0) + 1


def _emit_default(event: Mapping[str, object]) -> None:
    print(_canonical_json(dict(event)), flush=True)


async def _execute_serial_campaign_unlocked(
    path: Path,
    preflight_proof: PreflightProof,
    play_game: Callable[[protocol.GameRequest, PreflightProof], Awaitable[GameOutcome]],
    sleep: Callable[[float], Awaitable[object]],
    emit: Callable[[Mapping[str, object]], object],
) -> dict:
    loaded = protocol.load_campaign(path)
    _proof_matches_header(preflight_proof, loaded.header)
    needs_cooldown = any(row.get("type") == "result" for row in loaded.records)
    while True:
        loaded = protocol.load_campaign(path)
        action = loaded.action
        if isinstance(action, protocol.CampaignDecision):
            return protocol.campaign_summary(path)
        if needs_cooldown:
            await sleep(COOLDOWN_SECONDS)
            needs_cooldown = False
        attempt_id = _next_attempt_id(loaded.records)
        protocol.append_reservation(path, attempt_id, action)
        emit({"event": "game_start", "attempt_id": attempt_id, "visits": action.visits, "color": action.color})
        started = time.monotonic()
        failure: Exception | None = None
        try:
            outcome = await play_game(action, preflight_proof)
            if getattr(outcome, "result", None) in {"inconclusive_engine", "inconclusive_terminal"}:
                raise RuntimeError(f"definite runtime stop: {outcome.result}")
        except Exception as exc:
            failure = exc
        if failure is not None:
            reason = str(failure) or type(failure).__name__
            protocol.append_stop(path, attempt_id, reason)
            raise CampaignStopped(reason) from failure
        elapsed = time.monotonic() - started
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("elapsed game time is not finite")
        protocol.append_result(path, attempt_id, outcome, elapsed)
        emit(
            {
                "event": "game_result",
                "attempt_id": attempt_id,
                "visits": action.visits,
                "color": action.color,
                "outcome": outcome.result,
            }
        )
        needs_cooldown = True


async def execute_serial_campaign(
    path: str | Path,
    preflight_proof: PreflightProof,
    play_game: Callable[[protocol.GameRequest, PreflightProof], Awaitable[GameOutcome]],
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    emit: Callable[[Mapping[str, object]], object] = _emit_default,
) -> dict:
    canonical = Path(path).resolve()
    with campaign_output_lock(path):
        return await _execute_serial_campaign_unlocked(canonical, preflight_proof, play_game, sleep, emit)


def campaign_summary(path: str | Path) -> dict:
    return protocol.campaign_summary(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--audit-parent", action="store_true")
    modes.add_argument("--initialize", action="store_true")
    modes.add_argument("--summary", action="store_true")
    modes.add_argument("--authorize-continuation", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--parent")
    parser.add_argument("--parent-sha256")
    return parser


def validate_args(args: argparse.Namespace) -> str:
    if args.audit_parent:
        if any((args.out, args.parent, args.parent_sha256)):
            raise ValueError("--audit-parent accepts no output or recovery arguments")
        return "audit"
    if args.authorize_continuation:
        if not all((args.out, args.parent, args.parent_sha256)):
            raise ValueError("continuation requires --parent, --parent-sha256, and --out")
        if re.fullmatch(r"[0-9a-f]{64}", args.parent_sha256) is None:
            raise ValueError("--parent-sha256 must be exact lowercase SHA-256")
        if Path(args.parent).resolve() == Path(args.out).resolve():
            raise ValueError("continuation output must differ from parent")
        return "continue"
    if args.parent or args.parent_sha256:
        raise ValueError("parent arguments require --authorize-continuation")
    if not args.out:
        raise ValueError("this mode requires --out")
    return "initialize" if args.initialize else "summary" if args.summary else "live"


async def _preflight_for_header(local_client, header: Mapping[str, object]) -> PreflightProof:
    return await preflight_campaign(local_client, expected_health=header["complete_health_response"])


async def _run_network_mode(args: argparse.Namespace, mode: str) -> dict:
    requested_path = Path(args.out)
    path = requested_path.resolve()
    if mode == "live":
        with campaign_output_lock(requested_path):
            loaded = protocol.load_campaign(path)
            async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
                proof = await _preflight_for_header(local_client, loaded.header)
                async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:

                    async def play(request, bound_proof):
                        return await play_extension_game(local_client, golaxy_client, request, bound_proof)

                    return await _execute_serial_campaign_unlocked(path, proof, play, asyncio.sleep, _emit_default)
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
        health = await fetch_complete_health(local_client)
        validate_complete_health(health)
        with campaign_output_lock(requested_path):
            if mode == "initialize":
                loaded = protocol.initialize_v6_campaign(path, f"campaign-{uuid.uuid4().hex}", health)
                await _preflight_for_header(local_client, loaded.header)
                return protocol.campaign_summary(path)
            if mode == "continue":
                loaded = protocol.initialize_v7_continuation(
                    path,
                    f"campaign-{uuid.uuid4().hex}",
                    health,
                    parent_path=args.parent,
                    parent_sha256=args.parent_sha256,
                    authorization=protocol.CONTINUATION_AUTHORIZATION,
                )
                await _preflight_for_header(local_client, loaded.header)
                return protocol.campaign_summary(path)
            raise ValueError(f"unsupported network mode: {mode}")


def _audit_parent() -> dict:
    carries = protocol.load_frozen_carries(protocol.PARENT_PATH, protocol.PARENT_SHA256)
    return {"path": str(protocol.PARENT_PATH), "sha256": protocol.PARENT_SHA256, "accepted_carries": len(carries)}


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        mode = validate_args(args)
        if mode == "audit":
            result = _audit_parent()
        elif mode == "summary":
            result = campaign_summary(args.out)
        else:
            result = asyncio.run(_run_network_mode(args, mode))
    except Exception as exc:
        print(f"campaign stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
