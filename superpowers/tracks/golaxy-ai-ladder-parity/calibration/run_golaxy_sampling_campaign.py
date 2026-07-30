#!/usr/bin/env python3
"""Strictly serial live runner for the Golaxy HumanSL sampling campaign."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import os
import secrets
import sys
import uuid
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Awaitable, Callable, Mapping

import httpx

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]
for _bootstrap_path in (str(_REPO_ROOT), str(_SCRIPT_DIR)):
    while _bootstrap_path in sys.path:
        sys.path.remove(_bootstrap_path)
sys.path[:0] = [str(_REPO_ROOT), str(_SCRIPT_DIR)]
os.environ.setdefault("KIVY_NO_ARGS", "1")

import adapters  # noqa: E402
import golaxy_sampling_campaign  # noqa: E402
import run_golaxy_9d_alignment  # noqa: E402
import run_golaxy_alignment_campaign  # noqa: E402
import run_selfplay  # noqa: E402

from katrain.core.game import BaseGame, IllegalMoveException  # noqa: E402
from katrain.core.ladder import colrow_to_golaxy, golaxy_to_colrow, rung_strength_spec  # noqa: E402
from katrain.core.ladder_calibration import GameOutcome, play_one_game  # noqa: E402
from katrain.core.sgf_parser import Move  # noqa: E402


BASE_URL = "http://127.0.0.1:8000"
BOARD_SIZE = 19
KOMI = 7.5
RULES = "chinese"
WIDE_ROOT_NOISE = 0.04
REFEREE_VISITS = 200
STABILITY_VISITS = 800
STABILITY_DELTA = 1.0


class CampaignStopped(RuntimeError):
    """A one-shot campaign failure after a durable reservation."""


class SamplingGameStopped(RuntimeError):
    """A game failure carrying all HumanSL move audits completed before it stopped."""

    def __init__(self, reason: str, move_audits: tuple[Mapping[str, object], ...]):
        super().__init__(reason)
        self.move_audits = move_audits


@dataclass(frozen=True)
class PlayedSamplingGame:
    outcome: GameOutcome
    move_audits: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class SamplingPlayer:
    label: str
    rung: object
    selection: str


class _BoardConfig:
    @staticmethod
    def config(key):
        return 0 if key == "game/handicap" else RULES


def player_for_request(request: golaxy_sampling_campaign.GameRequest) -> SamplingPlayer:
    if not isinstance(request, golaxy_sampling_campaign.GameRequest):
        raise ValueError("sampling request must be a GameRequest")
    expected = next((stage for stage in golaxy_sampling_campaign.STAGES if stage[0] == request.stage), None)
    if expected is None or (request.player, request.golaxy_api_level) != expected[1:]:
        raise ValueError("sampling request does not match the frozen stage mapping")
    label, rung, selection = run_selfplay.make_player(request.player)
    spec = rung_strength_spec(rung)
    if (
        label != request.player
        or selection != "weighted"
        or rung.mechanism != "humansl"
        or spec.visits != 1
        or spec.human_model != "humanv0"
    ):
        raise ValueError("sampling player is not the frozen native HumanSL @1 configuration")
    return SamplingPlayer(label, rung, selection)


def opponent_for_request(request: golaxy_sampling_campaign.GameRequest):
    player_for_request(request)
    alignment_stage = request.stage.removeprefix("sampling_")
    return run_golaxy_alignment_campaign.opponent_for_stage(alignment_stage)


def requires_stability_probe(outcome: GameOutcome) -> bool:
    return bool(outcome.conclusive and outcome.end_reason != "golaxy_resign")


def stabilize_outcome(outcome: GameOutcome, *, second_score: float | None, second_settled: bool) -> GameOutcome:
    if not isinstance(outcome, GameOutcome):
        raise ValueError("sampling outcome must be a GameOutcome")
    if outcome.end_reason == "golaxy_resign":
        return outcome
    if not outcome.conclusive:
        return outcome
    if outcome.black_score == 0 or second_score == 0:
        return dataclasses.replace(outcome, result="inconclusive_score", our_win=False, conclusive=False)
    if (
        outcome.black_score is None
        or second_score is None
        or not second_settled
        or abs(second_score - outcome.black_score) >= STABILITY_DELTA
    ):
        return dataclasses.replace(outcome, result="inconclusive_unstable", our_win=False, conclusive=False)
    return outcome


def build_player_query(history: list[int], player: SamplingPlayer) -> dict:
    if not isinstance(player, SamplingPlayer) or player.selection != "weighted":
        raise ValueError("sampling player must use weighted HumanSL selection")
    return adapters.build_ladder_analysis_query(
        history,
        player.rung,
        BOARD_SIZE,
        KOMI,
        RULES,
        WIDE_ROOT_NOISE,
    )


def _validate_default_humansl_wrapper(
    analysis: object, identity_snapshot: Mapping[str, object]
) -> Mapping[str, object]:
    if not isinstance(analysis, Mapping):
        raise ValueError("sampling analysis must be an object containing humanPolicy")
    default_model = identity_snapshot.get("default_model")
    models = identity_snapshot.get("models")
    if type(default_model) is not str or not isinstance(models, Mapping):
        raise ValueError("sampling identity snapshot has no default model")
    identity = models.get(default_model)
    wrapper = analysis.get("_wrapper")
    if not isinstance(identity, Mapping) or not isinstance(wrapper, Mapping):
        raise ValueError("sampling response has no valid wrapper identity")
    expected = {
        "selected_model": default_model,
        "model_path": identity.get("model_path"),
        "model_sha256": identity.get("model_sha256"),
        "human_model_path": identity.get("human_model_path"),
        "human_model_sha256": identity.get("human_model_sha256"),
        "katago_version": identity_snapshot.get("katago_version"),
    }
    for field, value in expected.items():
        if type(value) is not str or not value or wrapper.get(field) != value:
            raise ValueError(f"sampling wrapper identity mismatch for {field}")
    if identity.get("human_model") != "humanv0" or identity.get("human_model_sha256_verified") is not True:
        raise ValueError("sampling identity is not a verified humanv0 attachment")
    return wrapper


def _game_from_history(history: list[int]) -> BaseGame:
    if not isinstance(history, list):
        raise ValueError("sampling history must be a list")
    game = BaseGame(
        _BoardConfig(),
        game_properties={"SZ": BOARD_SIZE, "KM": KOMI, "RU": RULES},
        bypass_config=True,
    )
    for ply, wire in enumerate(history):
        if type(wire) is not int or not 0 <= wire < BOARD_SIZE * BOARD_SIZE:
            raise ValueError("sampling history contains an invalid wire coordinate")
        colrow = golaxy_to_colrow(wire, BOARD_SIZE)
        if not isinstance(colrow, tuple):
            raise ValueError("sampling history contains a non-board move")
        try:
            game.play(Move(colrow, player="B" if ply % 2 == 0 else "W"))
        except IllegalMoveException as exc:
            raise ValueError(f"sampling history is illegal at ply {ply}: {exc}") from exc
    return game


def legal_policy_indices(history: list[int]) -> tuple[int, ...]:
    game = _game_from_history(history)
    player = "B" if len(history) % 2 == 0 else "W"
    legal: list[int] = []
    for index in range(BOARD_SIZE * BOARD_SIZE):
        move = Move((index % BOARD_SIZE, BOARD_SIZE - 1 - index // BOARD_SIZE), player=player)
        parent = game.current_node
        try:
            game.play(move)
        except IllegalMoveException:
            continue
        game.set_current_node(parent)
        legal.append(index)
    legal.append(BOARD_SIZE * BOARD_SIZE)
    return tuple(legal)


def canonical_sgf_history(history: list[int]) -> bytes:
    _game_from_history(history)
    moves = []
    for ply, wire in enumerate(history):
        colrow = golaxy_to_colrow(wire, BOARD_SIZE)
        moves.append(["B" if ply % 2 == 0 else "W", Move(colrow).sgf((BOARD_SIZE, BOARD_SIZE))])
    return json.dumps(moves, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def select_sampling_move(
    analysis: object,
    *,
    request: golaxy_sampling_campaign.GameRequest,
    identity_snapshot: Mapping[str, object],
    history: list[int],
    seed: int,
    reservation_id: str,
) -> tuple[int | str, dict]:
    player_for_request(request)
    _validate_default_humansl_wrapper(analysis, identity_snapshot)
    policy = analysis.get("humanPolicy")
    try:
        audit = golaxy_sampling_campaign.sample_human_policy(
            policy,
            legal_policy_indices(history),
            seed,
            reservation_id,
            len(history),
        )
    except ValueError as exc:
        raise ValueError(f"invalid humanPolicy: {exc}") from exc
    final_move = "pass" if audit.move == "pass" else colrow_to_golaxy(audit.move[0], audit.move[1], BOARD_SIZE)
    audit_row = {
        "ply": len(history),
        "position_sha256": hashlib.sha256(canonical_sgf_history(history)).hexdigest(),
        **dataclasses.asdict(audit),
        "final_move": final_move,
    }
    return final_move, audit_row


async def analyze_sampling_move(
    client,
    base_url: str,
    history: list[int],
    *,
    request: golaxy_sampling_campaign.GameRequest,
    identity_snapshot: Mapping[str, object],
    seed: int,
    reservation_id: str,
    audits: list[dict],
) -> int | str:
    if base_url != BASE_URL:
        raise ValueError(f"base URL must be exactly {BASE_URL}")
    if type(audits) is not list:
        raise ValueError("sampling audits must be a list")
    player = player_for_request(request)
    query = build_player_query(history, player)
    response = await client.post(f"{base_url}/analyze", json=query, timeout=httpx.Timeout(180.0, connect=10.0))
    analysis = run_golaxy_9d_alignment._json_response(response, "/analyze")
    move, audit = select_sampling_move(
        analysis,
        request=request,
        identity_snapshot=identity_snapshot,
        history=history,
        seed=seed,
        reservation_id=reservation_id,
    )
    audits.append(audit)
    return move


async def play_sampling_game(
    *,
    local_client,
    golaxy_client,
    token: str,
    smoke: Mapping[str, object],
    request: golaxy_sampling_campaign.GameRequest,
    header: Mapping[str, object],
    reservation_id: str,
) -> PlayedSamplingGame:
    audits: list[dict] = []
    try:
        return await _play_sampling_game(
            local_client=local_client,
            golaxy_client=golaxy_client,
            token=token,
            smoke=smoke,
            request=request,
            header=header,
            reservation_id=reservation_id,
            audits=audits,
        )
    except Exception as exc:
        reason = str(exc) or type(exc).__name__
        raise SamplingGameStopped(reason, tuple(audits)) from exc


async def _play_sampling_game(
    *,
    local_client,
    golaxy_client,
    token: str,
    smoke: Mapping[str, object],
    request: golaxy_sampling_campaign.GameRequest,
    header: Mapping[str, object],
    reservation_id: str,
    audits: list[dict],
) -> PlayedSamplingGame:
    opponent = opponent_for_request(request)
    identity_snapshot = header.get("identity_snapshot")
    seed = header.get("seed")
    if not isinstance(identity_snapshot, Mapping) or type(seed) is not int:
        raise ValueError("sampling ledger header lacks seed or identity snapshot")
    history_holder: dict[str, list[int] | None] = {"history": None}

    async def our_move(history):
        history_holder["history"] = history
        return await analyze_sampling_move(
            local_client,
            BASE_URL,
            history,
            request=request,
            identity_snapshot=identity_snapshot,
            seed=seed,
            reservation_id=reservation_id,
            audits=audits,
        )

    async def golaxy_move(history):
        history_holder["history"] = history
        return await adapters.golaxy_move(
            golaxy_client,
            history,
            rung=opponent,
            token=token,
            pass_code=smoke["pass_code"],
            resign_code=smoke["resign_code"],
        )

    adjudicate = partial(
        adapters.adjudicate,
        local_client,
        BASE_URL,
        visits=REFEREE_VISITS,
        capabilities=identity_snapshot,
        strict_identity=True,
    )
    outcome = await play_one_game(
        our_move=our_move,
        golaxy_move=golaxy_move,
        adjudicate=adjudicate,
        our_color=request.color,
        board_size=BOARD_SIZE,
        move_cap=golaxy_sampling_campaign.ADJUDICATION["move_cap"],
    )
    if requires_stability_probe(outcome):
        second_score, second_settled = await adapters.adjudicate(
            local_client,
            BASE_URL,
            history_holder["history"],
            visits=STABILITY_VISITS,
            capabilities=identity_snapshot,
            strict_identity=True,
        )
        outcome = stabilize_outcome(outcome, second_score=second_score, second_settled=second_settled)
    return PlayedSamplingGame(outcome, tuple(audits))


def _outcome_value(outcome: GameOutcome) -> str:
    if not isinstance(outcome, GameOutcome):
        raise ValueError("sampling game did not return a GameOutcome")
    if outcome.conclusive:
        return "win" if outcome.our_win else "loss"
    if outcome.result in {
        "inconclusive_score",
        "inconclusive_unsettled",
        "inconclusive_unstable",
        "inconclusive_terminal",
    }:
        return "inconclusive"
    raise ValueError(f"non-replenishable sampling outcome: {outcome.result!r}")


def _emit_default(event: Mapping[str, object]) -> None:
    print(json.dumps(dict(event), sort_keys=True), flush=True)


def summarize_campaign(path: str | Path) -> dict:
    loaded = golaxy_sampling_campaign.campaign_summary(path)
    action = loaded.action
    return {
        "campaign_id": loaded.header["campaign_id"],
        "stopped": loaded.stopped,
        "unknown_charged_attempts": list(loaded.unknown_charged_attempts),
        "results": sum(row.get("type") == "result" for row in loaded.records),
        "next_action": {"type": type(action).__name__, **dataclasses.asdict(action)},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--parent")
    parser.add_argument("--parent-sha256")
    parser.add_argument("--summary", action="store_true")
    return parser


def validate_args(args: argparse.Namespace) -> str:
    if args.summary:
        if args.parent is not None or args.parent_sha256 is not None:
            raise ValueError("--summary rejects live parent arguments")
        return "summary"
    if args.parent is None or args.parent_sha256 is None:
        raise ValueError("live sampling requires the exact fixed --parent and --parent-sha256")
    if Path(args.parent).resolve() != Path(golaxy_sampling_campaign.PARENT_PATH).resolve():
        raise ValueError("--parent differs from the fixed sampling parent")
    if args.parent_sha256 != golaxy_sampling_campaign.PARENT_SHA256:
        raise ValueError("--parent-sha256 differs from the exact fixed SHA-256")
    if Path(args.out).resolve() == Path(args.parent).resolve():
        raise ValueError("sampling output must differ from the fixed parent")
    return "live"


async def execute_serial_campaign(
    path: str | Path,
    *,
    play_game: Callable[
        [golaxy_sampling_campaign.GameRequest, Mapping[str, object], str], Awaitable[PlayedSamplingGame]
    ],
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    emit: Callable[[Mapping[str, object]], object] = _emit_default,
) -> dict:
    """Run one append-only sampling ledger with no retry and one in-flight game."""
    path = Path(path).resolve()
    with golaxy_sampling_campaign.output_lock(path):
        loaded = golaxy_sampling_campaign.load_campaign(path)
        needs_cooldown = any(row.get("type") == "result" for row in loaded.records)
        while True:
            loaded = golaxy_sampling_campaign.load_campaign(path)
            action = loaded.action
            if isinstance(action, golaxy_sampling_campaign.CampaignDecision):
                return summarize_campaign(path)
            if needs_cooldown:
                await sleep(golaxy_sampling_campaign.COOLDOWN_SECONDS)
                needs_cooldown = False
                loaded = golaxy_sampling_campaign.load_campaign(path)
                action = loaded.action
                if not isinstance(action, golaxy_sampling_campaign.GameRequest):
                    return summarize_campaign(path)
            attempt_id = 1 + sum(row.get("type") == "reservation" for row in loaded.records)
            reservation_id = f"{loaded.header['campaign_id']}:{attempt_id}"
            golaxy_sampling_campaign.append_reservation(path, attempt_id, action)
            try:
                emit(
                    {
                        "event": "game_start",
                        "attempt_id": attempt_id,
                        "stage": action.stage,
                        "player": action.player,
                        "slot": action.slot,
                        "color": action.color,
                    }
                )
                played = await play_game(action, loaded.header, reservation_id)
                if not isinstance(played, PlayedSamplingGame):
                    raise ValueError("sampling game callback returned the wrong result type")
                result = _outcome_value(played.outcome)
            except Exception as exc:
                reason = str(exc) or type(exc).__name__
                failed_audits = [dict(audit) for audit in getattr(exc, "move_audits", ())]
                try:
                    golaxy_sampling_campaign.append_stop(
                        path,
                        reason,
                        attempt_id,
                        move_audits=failed_audits,
                    )
                except Exception as stop_exc:
                    raise CampaignStopped(str(stop_exc) or type(stop_exc).__name__) from stop_exc
                emit(
                    {
                        "event": "campaign_stopped",
                        "attempt_id": attempt_id,
                        "stage": action.stage,
                        "reason": reason,
                    }
                )
                raise CampaignStopped(reason) from exc
            golaxy_sampling_campaign.append_result(
                path,
                attempt_id,
                result,
                move_audits=[dict(audit) for audit in played.move_audits],
            )
            emit(
                {
                    "event": "game_result",
                    "attempt_id": attempt_id,
                    "stage": action.stage,
                    "player": action.player,
                    "slot": action.slot,
                    "color": action.color,
                    "outcome": result,
                }
            )
            needs_cooldown = True


async def _run_live(args: argparse.Namespace) -> dict:
    validate_args(args)
    path = Path(args.out).resolve()
    with golaxy_sampling_campaign.output_lock(path):
        if path.exists():
            golaxy_sampling_campaign.load_campaign(path)
        else:
            golaxy_sampling_campaign.initialize_campaign(
                path,
                f"sampling-{uuid.uuid4().hex}",
                seed=secrets.randbits(64),
            )

    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:
            prerequisites: dict[str, object] = {}

            async def play(request, header, reservation_id):
                if not prerequisites:
                    response = await local_client.get(
                        f"{BASE_URL}/health",
                        timeout=httpx.Timeout(30.0, connect=10.0),
                    )
                    health = dict(run_golaxy_9d_alignment._json_response(response, "/health"))
                    snapshot = run_golaxy_alignment_campaign.build_identity_snapshot(health)
                    if snapshot != header["identity_snapshot"]:
                        raise ValueError("health identity differs from the frozen sampling ledger")
                    await run_golaxy_alignment_campaign.preflight_referees(local_client, snapshot)
                    prerequisites.update(
                        token=run_golaxy_9d_alignment.load_token(None),
                        smoke=run_golaxy_9d_alignment.load_verified_smoke_codes(
                            run_golaxy_9d_alignment.DEFAULT_SMOKE_REPORT
                        ),
                    )
                return await play_sampling_game(
                    local_client=local_client,
                    golaxy_client=golaxy_client,
                    token=str(prerequisites["token"]),
                    smoke=prerequisites["smoke"],
                    request=request,
                    header=header,
                    reservation_id=reservation_id,
                )

            return await execute_serial_campaign(path, play_game=play, sleep=asyncio.sleep, emit=_emit_default)


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        mode = validate_args(args)
        result = summarize_campaign(args.out) if mode == "summary" else asyncio.run(_run_live(args))
    except Exception as exc:
        print(f"sampling campaign stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
