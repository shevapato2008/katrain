#!/usr/bin/env python3
"""Fail-closed player, opponent, and identity adapters for the Golaxy campaign.

This module deliberately contains no live campaign loop.  It turns the frozen campaign
configuration into typed ladder descriptors and validates already-obtained local engine
responses; the serial network orchestration belongs to the next implementation task.
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).parent))
import adapters  # noqa: E402
import golaxy_alignment_campaign  # noqa: E402
import run_golaxy_9d_alignment  # noqa: E402
import run_selfplay  # noqa: E402

from katrain.core.ladder import (  # noqa: E402
    HUMANSL_PIKL_BASELINE,
    LadderMoveError,
    LadderRung,
    pick_ladder_move,
    rung_strength_spec,
)


BASE_URL = "http://127.0.0.1:8000"
BOARD_SIZE = 19
KOMI = 7.5
RULES = "chinese"
WIDE_ROOT_NOISE = 0.04
QUASI_PROFILES = dict(golaxy_alignment_campaign.QUASI_PROFILES)
_GRID_VISITS = {4, 8, 16, 32, 64}
_PROFILE_RE = re.compile(r"rank_[4-8]d")


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
    return CampaignPlayer("b18@1", rung, "search")


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
    _validate_player_definition(player)
    return player


def build_player_query(history: list, player: CampaignPlayer) -> dict:
    if not isinstance(player, CampaignPlayer):
        raise ValueError("player must be a CampaignPlayer")
    return adapters.build_ladder_analysis_query(
        history,
        player.rung,
        BOARD_SIZE,
        KOMI,
        RULES,
        WIDE_ROOT_NOISE,
    )


def _validate_player_definition(player: CampaignPlayer) -> None:
    spec = rung_strength_spec(player.rung)
    query = build_player_query([], player)
    overrides = query["overrideSettings"]
    if player.label == "b18@1":
        valid = (
            spec.visits == 1
            and spec.main_model == "b18"
            and spec.human_model is None
            and player.selection == "search"
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
    aliases = tuple(dict.fromkeys((default_model, "b18")))
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
    _validate_player_definition(player)
    if player.selection == "argmax_human":
        default_model = identity_snapshot.get("default_model")
        identity = _snapshot_identity(identity_snapshot, default_model)
        if identity.get("human_model") != "humanv0" or identity.get("human_model_sha256_verified") is not True:
            raise LadderMoveError("frozen default process has no verified attached humanv0")
        if not isinstance(analysis, Mapping):
            raise LadderMoveError("argmax HumanSL requires a valid humanPolicy")
        human_policy = analysis.get("humanPolicy")
        if not run_selfplay._valid_policy(human_policy, BOARD_SIZE * BOARD_SIZE + 1):
            raise LadderMoveError("argmax HumanSL requires a valid humanPolicy")
        # `_wrapper` and moveInfos are intentionally untouched: neither may influence native @1s.
        return run_selfplay._pick_argmax_human(human_policy, (BOARD_SIZE, BOARD_SIZE))

    _validate_explicit_b18_attestation(
        analysis,
        identity_snapshot,
        require_human=player.rung.mechanism == "humansl_search",
    )
    return pick_ladder_move(analysis, (BOARD_SIZE, BOARD_SIZE), player.rung.mechanism)


def preflight_player(health: dict, player_spec: str) -> tuple[CampaignPlayer, dict, dict]:
    """Pure local preflight used before Task 4 performs any HTTP or Golaxy operation."""
    validate_base_url(BASE_URL)
    player = make_campaign_player(player_spec)
    snapshot = build_identity_snapshot(health)
    return player, build_player_query([], player), snapshot


# These proven helpers remain the single transport/adjudication implementation for Task 4.
common_preflight = run_golaxy_9d_alignment.common_preflight
play_alignment_game = run_golaxy_9d_alignment.play_alignment_game
