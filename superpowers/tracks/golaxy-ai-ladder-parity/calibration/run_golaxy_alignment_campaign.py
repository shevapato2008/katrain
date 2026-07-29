#!/usr/bin/env python3
"""Fail-closed adapters and strictly serial live runner for the Golaxy campaign."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import fcntl
import json
import math
import re
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Awaitable, Callable, Mapping

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import adapters  # noqa: E402
import golaxy_alignment_campaign  # noqa: E402
import run_golaxy_9d_alignment  # noqa: E402
import run_selfplay  # noqa: E402

from katrain.core.ladder import (  # noqa: E402
    HUMANSL_PIKL_BASELINE,
    LadderMoveError,
    LadderRung,
    colrow_to_golaxy,
    pick_ladder_move,
    rung_strength_spec,
)
from katrain.core.ladder_calibration import GameOutcome, play_one_game  # noqa: E402


BASE_URL = "http://127.0.0.1:8000"
BOARD_SIZE = 19
KOMI = 7.5
RULES = "chinese"
WIDE_ROOT_NOISE = 0.04
COOLDOWN_SECONDS = 5.0
REFEREE_VISITS = 200
STABILITY_VISITS = 800
STABILITY_DELTA = 1.0
UNAVAILABLE_IDENTITY_SNAPSHOT = {"status": "unavailable", "reason": "health_bootstrap_failed"}
QUASI_PROFILES = dict(golaxy_alignment_campaign.QUASI_PROFILES)
_GRID_VISITS = {4, 8, 16, 32, 64}
_PROFILE_RE = re.compile(r"rank_[4-8]d")
FROZEN_STAGE_PLAYERS = {
    "seven_d": ("rank_7d@1s",),
    "one_star_b18_1": ("b18@1",),
    **{
        stage: tuple(f"{profile}@{tier}" for tier in golaxy_alignment_campaign.GRID)
        for stage, profile in QUASI_PROFILES.items()
    },
}
_FROZEN_PLAYERS = frozenset(player for players in FROZEN_STAGE_PLAYERS.values() for player in players)


@dataclass(frozen=True)
class CampaignPlayer:
    label: str
    rung: LadderRung
    selection: str

    def __iter__(self):
        yield self.label
        yield self.rung
        yield self.selection


def _custom_quasi_5d_opponent() -> LadderRung:
    """Create the sole campaign opponent which has no product ladder rung."""
    return dataclasses.replace(
        run_golaxy_9d_alignment.get_rung(26),
        rung=0,
        golaxy_level_name="准5段",
        golaxy_api_level=2000,
        display_elo=2000,
        ref_rank="业余准5段",
        rank_name="准5D",
    )


_OPPONENTS = {
    "quasi_5d": _custom_quasi_5d_opponent(),
    "quasi_6d": run_golaxy_9d_alignment.get_rung(26),
    "quasi_7d": run_golaxy_9d_alignment.get_rung(28),
    "quasi_8d": run_golaxy_9d_alignment.get_rung(30),
    "quasi_9d": run_golaxy_9d_alignment.get_rung(32),
    "seven_d": run_golaxy_9d_alignment.get_rung(29),
    "one_star_b18_1": run_golaxy_9d_alignment.get_rung(34),
}


def resolve_opponent(opponent: LadderRung) -> LadderRung:
    if not isinstance(opponent, LadderRung):
        raise ValueError("Golaxy campaign opponent must be a LadderRung")
    adapters._assert_real_wire_level(opponent.golaxy_api_level)
    rung_strength_spec(opponent)
    return opponent


def opponent_for_stage(stage: str) -> LadderRung:
    try:
        opponent = _OPPONENTS[stage]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unknown Golaxy campaign stage {stage!r}") from exc
    return resolve_opponent(opponent)


def validate_base_url(value: object) -> str:
    # Keep a single literal and reuse the older runner's strict URL parser.
    if value != BASE_URL:
        raise ValueError(f"base URL must be exactly {BASE_URL}")
    return run_golaxy_9d_alignment.validate_base_url(value)


def _pure_b18_player() -> CampaignPlayer:
    rung = LadderRung(
        rung=0,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank="b18",
        rank_name="b18",
        net="b18",
        mechanism="net_search",
        human_sl_profile=None,
        max_visits=1,
        human_sl_params={},
        backend_hint="server",
        root_policy_temperature=1.0,
    )
    rung_strength_spec(rung)
    return CampaignPlayer("b18@1", rung, "policy_argmax")


def make_campaign_player(spec: str) -> CampaignPlayer:
    """Construct exactly one player from the campaign's frozen candidate set."""
    if spec == "b18@1":
        player = _pure_b18_player()
    else:
        if not isinstance(spec, str):
            raise ValueError("campaign player must be a frozen candidate string")
        profile, separator, suffix = spec.partition("@")
        if not separator or _PROFILE_RE.fullmatch(profile) is None:
            raise ValueError(f"campaign player is not a frozen candidate: {spec!r}")
        if suffix == "1s":
            pass
        elif suffix.isdigit() and int(suffix) in _GRID_VISITS:
            pass
        else:
            raise ValueError(f"campaign player is not on the frozen visit grid: {spec!r}")
        label, rung, selection = run_selfplay.make_player(spec, experimental_min_humansl_search_visits=2)
        player = CampaignPlayer(label, rung, selection)
    validate_campaign_player(player)
    return player


def _raw_player_query(history: list, player: CampaignPlayer) -> dict:
    return adapters.build_ladder_analysis_query(
        history,
        player.rung,
        BOARD_SIZE,
        KOMI,
        RULES,
        WIDE_ROOT_NOISE,
    )


def _expected_empty_query(player: CampaignPlayer) -> dict:
    overrides = {"reportAnalysisWinratesAs": "BLACK"}
    if player.rung.human_sl_profile is not None:
        overrides.update(humanSLProfile=player.rung.human_sl_profile, ignorePreRootHistory=False)
    overrides.update(player.rung.human_sl_params)
    overrides["wideRootNoise"] = WIDE_ROOT_NOISE
    if player.rung.net != "humanv0":
        overrides["model"] = player.rung.net
    return {
        "rules": RULES,
        "komi": KOMI,
        "boardXSize": BOARD_SIZE,
        "boardYSize": BOARD_SIZE,
        "moves": [],
        "analyzeTurns": [0],
        "maxVisits": player.rung.max_visits,
        "includePolicy": True,
        "includeOwnership": False,
        "overrideSettings": overrides,
    }


def validate_campaign_player(player: CampaignPlayer) -> CampaignPlayer:
    """Reject any label, rung, selection, or effective-query drift."""
    if not isinstance(player, CampaignPlayer):
        raise ValueError("campaign player must be a CampaignPlayer")
    if player.label not in _FROZEN_PLAYERS:
        raise ValueError(f"player {player.label!r} is not in the frozen campaign player set")
    try:
        spec = rung_strength_spec(player.rung)
    except ValueError as exc:
        raise ValueError(f"campaign player strength is invalid: {exc}") from exc
    if player.rung.mechanism == "humansl":
        expected_label = f"{player.rung.human_sl_profile}@1s"
        expected_selection = "argmax_human"
    elif player.rung.mechanism == "humansl_search":
        expected_label = f"{player.rung.human_sl_profile}@{player.rung.max_visits}"
        expected_selection = "search"
    elif player.rung.mechanism == "net_search" and player.rung.net == "b18" and player.rung.max_visits == 1:
        expected_label = "b18@1"
        expected_selection = "policy_argmax"
    else:
        raise ValueError("campaign player strength is not one of the frozen campaign mechanisms")
    if player.label != expected_label:
        raise ValueError(f"campaign player label mismatch: expected {expected_label!r}, got {player.label!r}")
    if player.selection != expected_selection:
        raise ValueError(
            f"campaign player selection mismatch: expected {expected_selection!r}, got {player.selection!r}"
        )
    query = _raw_player_query([], player)
    overrides = query["overrideSettings"]
    if player.label == "b18@1":
        valid = (
            spec.visits == 1
            and spec.main_model == "b18"
            and spec.human_model is None
            and player.selection == "policy_argmax"
            and overrides == {"reportAnalysisWinratesAs": "BLACK", "wideRootNoise": WIDE_ROOT_NOISE, "model": "b18"}
        )
    elif player.label.endswith("@1s"):
        valid = (
            spec.visits == 1
            and spec.main_model is None
            and spec.human_model == "humanv0"
            and player.selection == "argmax_human"
            and "model" not in overrides
        )
    else:
        expected = {
            "reportAnalysisWinratesAs": "BLACK",
            "humanSLProfile": player.rung.human_sl_profile,
            "ignorePreRootHistory": False,
            **HUMANSL_PIKL_BASELINE,
            "wideRootNoise": WIDE_ROOT_NOISE,
            "model": "b18",
        }
        valid = (
            spec.visits in _GRID_VISITS
            and spec.main_model == "b18"
            and spec.human_model == "humanv0"
            and player.selection == "search"
            and overrides == expected
        )
    if not valid:
        raise ValueError("campaign player strength or effective query drifted from the frozen configuration")
    if query != _expected_empty_query(player):
        raise ValueError("campaign player effective query drifted from the frozen configuration")
    return player


def validate_stage_player(stage: str, player: CampaignPlayer) -> CampaignPlayer:
    validate_campaign_player(player)
    allowed = FROZEN_STAGE_PLAYERS.get(stage)
    if allowed is None:
        raise ValueError(f"unknown campaign stage {stage!r}")
    if player.label not in allowed:
        raise ValueError(f"player {player.label!r} is not valid for campaign stage {stage!r}")
    return player


def build_player_query(history: list, player: CampaignPlayer) -> dict:
    validate_campaign_player(player)
    return _raw_player_query(history, player)


def build_identity_snapshot(health: dict) -> dict:
    """Validate `/health` and return the JSON-safe identity stored in a campaign header."""
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise ValueError("health status must be exactly 'ok'")
    try:
        capabilities = adapters.retain_health_snapshot(health)
    except ValueError as exc:
        raise ValueError(f"invalid health capability schema or identity: {exc}") from exc
    default_model = capabilities["default_model"]
    models = capabilities["models"]
    aliases = tuple(dict.fromkeys((default_model, "b18", "b28")))
    frozen_models = {}
    for alias in aliases:
        model = models.get(alias)
        if not isinstance(model, Mapping):
            raise ValueError(f"health identity is missing required model {alias!r}")
        if model.get("running") is not True:
            raise ValueError(f"health model {alias!r} is not running")
        if model.get("model_sha256_verified") is not True:
            raise ValueError(f"health model {alias!r} identity is not verified")
        if (
            model.get("has_human_model") is not True
            or model.get("human_model_sha256_verified") is not True
            or not isinstance(model.get("human_model_path"), str)
            or not model["human_model_path"]
            or not isinstance(model.get("human_model_sha256"), str)
            or not model["human_model_sha256"]
        ):
            raise ValueError(f"health model {alias!r} has no verified attached humanv0 identity")
        frozen_models[alias] = {
            "running": True,
            "model_path": model["model_path"],
            "model_sha256": model["model_sha256"],
            "model_sha256_verified": True,
            "human_model": "humanv0",
            "human_model_path": model["human_model_path"],
            "human_model_sha256": model["human_model_sha256"],
            "human_model_sha256_verified": True,
        }
    snapshot = {
        "status": "ok",
        "capability_schema": capabilities["capability_schema"],
        "katago_version": capabilities["katago_version"],
        "default_model": default_model,
        "models": frozen_models,
    }
    # Assert the exact object handed to initialize_campaign is serializable now, not at game time.
    json.dumps(snapshot, sort_keys=True, allow_nan=False)
    return snapshot


def _snapshot_identity(snapshot: Mapping[str, object], alias: str) -> Mapping[str, object]:
    models = snapshot.get("models")
    if not isinstance(models, Mapping) or not isinstance(models.get(alias), Mapping):
        raise LadderMoveError(f"frozen identity snapshot has no model {alias!r}")
    return models[alias]


def _valid_campaign_policy(policy: object) -> bool:
    return bool(
        isinstance(policy, list)
        and len(policy) == BOARD_SIZE * BOARD_SIZE + 1
        and all(type(value) in (int, float) and math.isfinite(value) for value in policy)
        and sum(value for value in policy if value > 0) > 0
    )


def _validate_explicit_b18_attestation(
    analysis: object, snapshot: Mapping[str, object], *, require_human: bool
) -> None:
    if not isinstance(analysis, Mapping):
        raise LadderMoveError("analysis attestation: analysis is not a mapping")
    wrapper = analysis.get("_wrapper")
    if not isinstance(wrapper, Mapping):
        raise LadderMoveError("analysis attestation: missing/malformed _wrapper identity")
    if wrapper.get("selected_model") != "b18":
        raise LadderMoveError(
            f"analysis attestation selected_model mismatch: expected 'b18', got {wrapper.get('selected_model')!r}"
        )
    identity = _snapshot_identity(snapshot, "b18")
    fields = ["model_path", "model_sha256"]
    if require_human:
        fields.extend(("human_model_path", "human_model_sha256"))
    for field in fields:
        expected = identity.get(field)
        actual = wrapper.get(field)
        if not isinstance(actual, str) or not actual or actual != expected:
            raise LadderMoveError(f"analysis attestation {field} mismatch: expected {expected!r}, got {actual!r}")
    version = snapshot.get("katago_version")
    if wrapper.get("katago_version") != version:
        raise LadderMoveError(
            f"analysis attestation katago_version mismatch: expected {version!r}, got {wrapper.get('katago_version')!r}"
        )


def select_player_move(analysis: object, player: CampaignPlayer, identity_snapshot: Mapping[str, object]):
    """Validate one response and return its sole permitted `(col, row0)` move or ``pass``."""
    validate_campaign_player(player)
    if player.selection == "argmax_human":
        default_model = identity_snapshot.get("default_model")
        identity = _snapshot_identity(identity_snapshot, default_model)
        if identity.get("human_model") != "humanv0" or identity.get("human_model_sha256_verified") is not True:
            raise LadderMoveError("frozen default process has no verified attached humanv0")
        if not isinstance(analysis, Mapping):
            raise LadderMoveError("argmax HumanSL requires a valid humanPolicy")
        human_policy = analysis.get("humanPolicy")
        if not _valid_campaign_policy(human_policy):
            raise LadderMoveError("argmax HumanSL requires a valid humanPolicy")
        # `_wrapper` and moveInfos are intentionally untouched: neither may influence native @1s.
        return run_selfplay._pick_argmax_human(human_policy, (BOARD_SIZE, BOARD_SIZE))

    _validate_explicit_b18_attestation(
        analysis,
        identity_snapshot,
        require_human=player.rung.mechanism == "humansl_search",
    )
    if player.selection == "policy_argmax":
        root_info = analysis.get("rootInfo") if isinstance(analysis, Mapping) else None
        visits = root_info.get("visits") if isinstance(root_info, Mapping) else None
        if type(visits) is not int or visits != 1:
            raise LadderMoveError(f"b18@1 rootInfo.visits must be exactly 1, got {visits!r}")
        if not isinstance(analysis, Mapping) or analysis.get("moveInfos") != []:
            raise LadderMoveError("b18@1 requires exactly empty moveInfos")
        policy = analysis.get("policy")
        if not _valid_campaign_policy(policy):
            raise LadderMoveError("b18@1 requires a valid 362-entry native policy")
        return run_selfplay._pick_argmax_human(policy, (BOARD_SIZE, BOARD_SIZE))
    return pick_ladder_move(analysis, (BOARD_SIZE, BOARD_SIZE), player.rung.mechanism)


def preflight_player(health: dict, player_spec: str) -> tuple[CampaignPlayer, dict, dict]:
    """Pure local preflight used before Task 4 performs any HTTP or Golaxy operation."""
    validate_base_url(BASE_URL)
    player = make_campaign_player(player_spec)
    snapshot = build_identity_snapshot(health)
    return player, build_player_query([], player), snapshot


async def analyze_player_move(
    client,
    base_url: str,
    history: list,
    player: CampaignPlayer,
    identity_snapshot: Mapping[str, object],
):
    """Request and validate one campaign move from the local analysis service."""
    validate_base_url(base_url)
    query = build_player_query(history, player)
    response = await client.post(f"{base_url}/analyze", json=query, timeout=httpx.Timeout(180.0, connect=10.0))
    analysis = run_golaxy_9d_alignment._json_response(response, "/analyze")
    selected = select_player_move(analysis, player, identity_snapshot)
    return "pass" if selected == "pass" else colrow_to_golaxy(selected[0], selected[1], BOARD_SIZE)


async def campaign_preflight(client, base_url: str, player_spec: str) -> dict:
    """Probe one mode against the local service; never contacts Golaxy."""
    validate_base_url(base_url)
    player = make_campaign_player(player_spec)
    response = await client.get(f"{base_url}/health", timeout=httpx.Timeout(30.0, connect=10.0))
    health = dict(run_golaxy_9d_alignment._json_response(response, "/health"))
    identity_snapshot = build_identity_snapshot(health)
    probe_move = await analyze_player_move(client, base_url, [], player, identity_snapshot)
    return {
        "player": player,
        "effective_query": build_player_query([], player),
        "identity_snapshot": identity_snapshot,
        "probe_move": probe_move,
    }


async def preflight_referees(client, identity_snapshot: Mapping[str, object]) -> dict:
    """Semantically probe both frozen b28 referee paths before any game is reserved."""
    if "b28" not in identity_snapshot.get("models", {}):
        raise ValueError("frozen identity snapshot is missing the explicit b28 referee")
    return {
        "adjudication": await run_golaxy_9d_alignment._probe_referee(
            client, BASE_URL, identity_snapshot, REFEREE_VISITS
        ),
        "stability": await run_golaxy_9d_alignment._probe_referee(
            client, BASE_URL, identity_snapshot, STABILITY_VISITS
        ),
    }


class CampaignStopped(RuntimeError):
    """One-shot campaign failure already persisted in the append-only ledger."""


@contextmanager
def campaign_output_lock(path: str | Path):
    """Hold a non-blocking cross-process lock for the full mutation session."""
    canonical_path = Path(path).resolve()
    lock_path = Path(f"{canonical_path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"campaign output is locked by another writer: {path}") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _next_attempt_id(records: tuple[Mapping[str, object], ...]) -> int:
    attempts = [row["attempt_id"] for row in records if row.get("type") == "reservation"]
    return max(attempts, default=0) + 1


def _outcome_value(outcome: object) -> str:
    if getattr(outcome, "conclusive", None) is True:
        return "win" if getattr(outcome, "our_win", None) is True else "loss"
    if getattr(outcome, "conclusive", None) is False and getattr(outcome, "result", None) in {
        "inconclusive_score",
        "inconclusive_unsettled",
        "inconclusive_unstable",
    }:
        return "inconclusive"
    raise ValueError(f"non-replenishable game outcome: {getattr(outcome, 'result', None)!r}")


def _emit_default(event: Mapping[str, object]) -> None:
    print(json.dumps(dict(event), sort_keys=True), flush=True)


def _persisted_active_stage(records: tuple[Mapping[str, object], ...]) -> str | None:
    active: str | None = None
    for row in records:
        if row.get("type") == "stage_started":
            if active is not None:
                raise ValueError("campaign ledger has overlapping stage_started events")
            active = str(row["stage"])
        elif row.get("type") == "stage_completed":
            if active != row.get("stage"):
                raise ValueError("campaign ledger has unmatched stage_completed event")
            active = None
    return active


async def _execute_serial_campaign_unlocked(
    path: Path,
    *,
    preflight_player: Callable[[golaxy_alignment_campaign.GameRequest, Mapping[str, object]], Awaitable[object]],
    play_game: Callable[[golaxy_alignment_campaign.GameRequest, Mapping[str, object]], Awaitable[object]],
    sleep: Callable[[float], Awaitable[object]],
    emit: Callable[[Mapping[str, object]], object],
) -> dict:
    loaded = golaxy_alignment_campaign.load_campaign(path)
    _validate_summary_control_flow(loaded)
    snapshot = loaded.header["identity_snapshot"]
    active_stage = _persisted_active_stage(loaded.records)
    if active_stage is not None and golaxy_alignment_campaign.stage_decision(loaded.evidence, active_stage) is not None:
        golaxy_alignment_campaign.append_stage_event(path, "stage_completed", active_stage)
        active_stage = None
    preflighted_players: set[str] = set()
    needs_cooldown = any(row.get("type") == "result" for row in loaded.records)

    while True:
        loaded = golaxy_alignment_campaign.load_campaign(path)
        action = loaded.action
        if isinstance(action, golaxy_alignment_campaign.CampaignDecision):
            return summarize_campaign(path)
        if active_stage != action.stage:
            if active_stage is not None:
                raise ValueError("campaign stage changed without a persisted stage_completed event")
            stage_index = golaxy_alignment_campaign.STAGE_ORDER.index(action.stage)
            if any(
                golaxy_alignment_campaign.stage_decision(loaded.evidence, predecessor) is None
                for predecessor in golaxy_alignment_campaign.STAGE_ORDER[:stage_index]
            ):
                raise ValueError("campaign predecessor evidence is not terminal")
            golaxy_alignment_campaign.append_stage_event(path, "stage_started", action.stage)
            active_stage = action.stage

        if action.player not in preflighted_players:
            try:
                await preflight_player(action, snapshot)
            except Exception as exc:
                reason = f"local preflight failed: {exc}"
                golaxy_alignment_campaign.append_stop(path, reason)
                emit({"event": "campaign_stopped", "stage": action.stage, "reason": reason})
                raise CampaignStopped(reason) from exc
            preflighted_players.add(action.player)

        if needs_cooldown:
            await sleep(COOLDOWN_SECONDS)
            needs_cooldown = False

        loaded = golaxy_alignment_campaign.load_campaign(path)
        attempt_id = _next_attempt_id(loaded.records)
        golaxy_alignment_campaign.append_reservation(path, attempt_id, action)
        try:
            emit(
                {
                    "event": "game_start",
                    "attempt_id": attempt_id,
                    "stage": action.stage,
                    "player": action.player,
                    "color": action.color,
                }
            )
            outcome = await play_game(action, snapshot)
            result = _outcome_value(outcome)
        except Exception as exc:
            reason = str(exc) or type(exc).__name__
            golaxy_alignment_campaign.append_stop(path, reason, event_type="stopped", attempt_id=attempt_id)
            golaxy_alignment_campaign.append_stop(path, reason, event_type="campaign_stopped")
            emit({"event": "campaign_stopped", "stage": action.stage, "attempt_id": attempt_id, "reason": reason})
            raise CampaignStopped(reason) from exc
        golaxy_alignment_campaign.append_result(path, attempt_id, result)
        emit(
            {
                "event": "game_result",
                "attempt_id": attempt_id,
                "stage": action.stage,
                "player": action.player,
                "color": action.color,
                "outcome": result,
            }
        )
        needs_cooldown = True

        next_action = golaxy_alignment_campaign.replay_campaign(path)
        if isinstance(next_action, golaxy_alignment_campaign.CampaignDecision) or next_action.stage != action.stage:
            decision = golaxy_alignment_campaign.stage_decision(
                golaxy_alignment_campaign.campaign_summary(path).evidence, action.stage
            )
            if decision is None:
                raise ValueError("stage transition occurred without a terminal stage decision")
            golaxy_alignment_campaign.append_stage_event(path, "stage_completed", action.stage)
            emit(
                {
                    "event": "stage_complete",
                    "stage": action.stage,
                    "status": decision.status,
                    "selected_player": decision.selected_player,
                }
            )
            active_stage = None


async def execute_serial_campaign(
    path: str | Path,
    *,
    preflight_player: Callable[[golaxy_alignment_campaign.GameRequest, Mapping[str, object]], Awaitable[object]],
    play_game: Callable[[golaxy_alignment_campaign.GameRequest, Mapping[str, object]], Awaitable[object]],
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    emit: Callable[[Mapping[str, object]], object] = _emit_default,
) -> dict:
    """Execute an existing ledger with exactly one in-flight game and no retry path."""
    path = Path(path).resolve()
    with campaign_output_lock(path):
        # This load intentionally precedes either injected callback, so stopped/unmatched ledgers
        # cannot touch the local service or Golaxy.
        golaxy_alignment_campaign.load_campaign(path)
        return await _execute_serial_campaign_unlocked(
            path, preflight_player=preflight_player, play_game=play_game, sleep=sleep, emit=emit
        )


def _validate_summary_control_flow(loaded: golaxy_alignment_campaign.LoadedCampaign) -> None:
    replayed: list[Mapping[str, object]] = []
    active_stage: str | None = None
    for line_number, row in enumerate(loaded.records, 2):
        row_type = row.get("type")
        if row_type == "carry_result":
            replayed.append(row)
        elif row_type == "stage_started":
            expected = golaxy_alignment_campaign.next_action(replayed)
            if (
                active_stage is not None
                or not isinstance(expected, golaxy_alignment_campaign.GameRequest)
                or row.get("stage") != expected.stage
            ):
                raise ValueError(f"invalid stage_started ordering on line {line_number}")
            active_stage = str(row["stage"])
        elif row_type == "reservation":
            if active_stage != row.get("stage"):
                raise ValueError(f"game reservation on line {line_number} has no matching active stage_started")
        elif row_type == "result":
            if active_stage != row.get("stage"):
                raise ValueError(f"game result on line {line_number} has no matching active stage_started")
            replayed.append(row)
        elif row_type == "stage_completed":
            stage = row.get("stage")
            if active_stage != stage or golaxy_alignment_campaign.stage_decision(replayed, str(stage)) is None:
                raise ValueError(f"invalid stage_completed ordering on line {line_number}")
            active_stage = None


def summarize_campaign(path: str | Path) -> dict:
    """Read and strictly replay a ledger without constructing any network client."""
    loaded = golaxy_alignment_campaign.campaign_summary(path)
    _validate_summary_control_flow(loaded)
    decisions = []
    for stage in golaxy_alignment_campaign.STAGE_ORDER:
        decision = golaxy_alignment_campaign.stage_decision(loaded.evidence, stage)
        if decision is None:
            break
        decisions.append(dataclasses.asdict(decision))
    action = loaded.action
    action_dict = {"type": type(action).__name__, **dataclasses.asdict(action)}
    origins = [str(row["origin_result_id"]) for row in loaded.evidence]
    return {
        "campaign_id": loaded.header["campaign_id"],
        "stopped": loaded.stopped,
        "unknown_charged_attempts": list(loaded.unknown_charged_attempts),
        "results": len(loaded.evidence),
        "origin_result_ids_unique": len(origins) == len(set(origins)),
        "stages": decisions,
        "next_action": action_dict,
    }


async def play_campaign_game(
    *,
    local_client,
    golaxy_client,
    token: str,
    smoke: Mapping[str, object],
    request: golaxy_alignment_campaign.GameRequest,
    identity_snapshot: Mapping[str, object],
) -> GameOutcome:
    """Play one game using campaign-specific selection and lower-level transport primitives."""
    player = validate_stage_player(request.stage, make_campaign_player(request.player))
    opponent = opponent_for_stage(request.stage)
    history_holder: dict[str, list[int] | None] = {"history": None}

    async def our_move(history):
        history_holder["history"] = history
        return await analyze_player_move(local_client, BASE_URL, history, player, identity_snapshot)

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
        our_move=our_move, golaxy_move=golaxy_move, adjudicate=adjudicate, our_color=request.color
    )
    if outcome.result in {"inconclusive_engine", "inconclusive_terminal"}:
        raise ValueError(f"non-replenishable runtime drift: {outcome.result}")
    if outcome.conclusive and outcome.end_reason != "golaxy_resign":
        history = history_holder["history"]
        score, settled = await adapters.adjudicate(
            local_client,
            BASE_URL,
            history,
            visits=STABILITY_VISITS,
            capabilities=identity_snapshot,
            strict_identity=True,
        )
        if (
            outcome.black_score is None
            or score is None
            or not settled
            or abs(score - outcome.black_score) >= STABILITY_DELTA
        ):
            outcome = dataclasses.replace(outcome, result="inconclusive_unstable", our_win=False, conclusive=False)
    return outcome


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
            raise ValueError("--summary does not accept parent recovery arguments")
        return "summary"
    if (args.parent is None) != (args.parent_sha256 is None):
        raise ValueError("--parent and --parent-sha256 are both required for recovery")
    if args.parent_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", args.parent_sha256) is None:
        raise ValueError("--parent-sha256 must be an exact lowercase 64-hex SHA-256")
    if args.parent is not None and Path(args.out).resolve() == Path(args.parent).resolve():
        raise ValueError("recovery requires a different output ledger")
    return "live"


async def _run_live(args: argparse.Namespace) -> dict:
    path = Path(args.out).resolve()
    with campaign_output_lock(path):
        if path.exists():
            if args.parent is not None:
                raise ValueError("parent recovery requires a new output ledger")
            loaded = golaxy_alignment_campaign.load_campaign(path)
        else:
            if args.parent is not None:
                parent = Path(args.parent).resolve()
                if golaxy_alignment_campaign._sha256(parent) != args.parent_sha256:
                    raise ValueError(f"parent SHA-256 mismatch for {parent}")
                if not golaxy_alignment_campaign.campaign_summary(parent).stopped:
                    raise ValueError("parent campaign must be stopped before recovery")
            try:
                async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
                    response = await local_client.get(f"{BASE_URL}/health", timeout=httpx.Timeout(30.0, connect=10.0))
                    health = dict(run_golaxy_9d_alignment._json_response(response, "/health"))
                    snapshot = build_identity_snapshot(health)
            except Exception as exc:
                # No trustworthy engine identity exists to freeze. Persist an explicitly unusable
                # header so this charged campaign lineage has a durable terminal audit record,
                # while successful ledgers continue to contain only the actual attested snapshot.
                golaxy_alignment_campaign.initialize_campaign(
                    path,
                    f"campaign-{uuid.uuid4().hex}",
                    UNAVAILABLE_IDENTITY_SNAPSHOT,
                    args.parent,
                    args.parent_sha256,
                )
                reason = f"health bootstrap failed: {exc}"
                golaxy_alignment_campaign.append_stop(path, reason)
                _emit_default({"event": "campaign_stopped", "reason": reason})
                raise CampaignStopped(reason) from exc
            loaded = golaxy_alignment_campaign.initialize_campaign(
                path,
                f"campaign-{uuid.uuid4().hex}",
                snapshot,
                args.parent,
                args.parent_sha256,
            )
        # Persisted orchestration state is a local gate: reject it before constructing any
        # analysis client or invoking a campaign callback.
        _validate_summary_control_flow(loaded)
        try:
            async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
                response = await local_client.get(f"{BASE_URL}/health", timeout=httpx.Timeout(30.0, connect=10.0))
                current_snapshot = build_identity_snapshot(
                    dict(run_golaxy_9d_alignment._json_response(response, "/health"))
                )
                if current_snapshot != loaded.header["identity_snapshot"]:
                    raise ValueError("health identity differs from campaign header")

                await preflight_referees(local_client, current_snapshot)

                async def preflight(request, snapshot):
                    player = validate_stage_player(request.stage, make_campaign_player(request.player))
                    await analyze_player_move(local_client, BASE_URL, [], player, snapshot)

                token = run_golaxy_9d_alignment.load_token(None)
                # Resolve every local prerequisite before the serial executor can reserve a game.
                smoke = run_golaxy_9d_alignment.load_verified_smoke_codes(run_golaxy_9d_alignment.DEFAULT_SMOKE_REPORT)
                async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:

                    async def play(request, snapshot):
                        return await play_campaign_game(
                            local_client=local_client,
                            golaxy_client=golaxy_client,
                            token=token,
                            smoke=smoke,
                            request=request,
                            identity_snapshot=snapshot,
                        )

                    return await _execute_serial_campaign_unlocked(
                        path,
                        preflight_player=preflight,
                        play_game=play,
                        sleep=asyncio.sleep,
                        emit=_emit_default,
                    )
        except CampaignStopped:
            raise
        except Exception as exc:
            loaded_after_failure = golaxy_alignment_campaign.campaign_summary(path)
            if not loaded_after_failure.stopped:
                reason = f"local preflight failed: {exc}"
                golaxy_alignment_campaign.append_stop(path, reason)
                _emit_default({"event": "campaign_stopped", "reason": reason})
                raise CampaignStopped(reason) from exc
            raise


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        mode = validate_args(args)
        result = summarize_campaign(args.out) if mode == "summary" else asyncio.run(_run_live(args))
    except Exception as exc:
        print(f"campaign stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
