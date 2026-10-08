"""Pure decisions for the self-owned PvP lobby bot population."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Mapping

from katrain.core import ladder


@dataclass(frozen=True)
class PlayableRung:
    rung: int
    rank_label: str


def playable_rungs() -> tuple[PlayableRung, ...]:
    """Use the current fitted, certified catalog rather than legacy user ranks."""
    return tuple(
        PlayableRung(level.rung, level.rank_name)
        for level in ladder.LADDER_LEVELS
        if level.recipe is not None and level.certification_status == "certified" and level.availability == "available"
    )


def validate_config(config: Mapping[str, object]) -> dict[str, object]:
    """Validate and fill a version-one JSON configuration without changing its input."""
    if not isinstance(config, Mapping) or set(config) != {"version", "enabled", "bot_game_limit", "idle_targets"}:
        raise ValueError("invalid PvP lobby bot config fields")
    if type(config["version"]) is not int or config["version"] != 1:
        raise ValueError("unsupported PvP lobby bot config version")
    if type(config["enabled"]) is not bool:
        raise ValueError("enabled must be a boolean")
    limit = config["bot_game_limit"]
    if type(limit) is not int or not 0 <= limit <= 6:
        raise ValueError("bot_game_limit must be 0..6")
    supplied = config["idle_targets"]
    if not isinstance(supplied, Mapping):
        raise ValueError("idle_targets must be an object")
    playable = {str(level.rung) for level in playable_rungs()}
    if any(type(key) is not str or key not in playable for key in supplied):
        raise ValueError("idle_targets contains an unknown rung")
    if any(type(target) is not int or not 1 <= target <= 20 for target in supplied.values()):
        raise ValueError("idle_targets must be 1..20 per rung")
    return {
        "version": 1,
        "enabled": config["enabled"],
        "bot_game_limit": limit,
        "idle_targets": {str(level.rung): supplied.get(str(level.rung), 2) for level in playable_rungs()},
    }


def _check_identity_coordinates(rung: int, slot: int) -> None:
    if type(rung) is not int or rung < 1 or type(slot) is not int or slot < 1:
        raise ValueError("bot rung and slot must be positive integers")


def bot_id(rung: int, slot: int) -> int:
    """A stable negative ID, injective even if a rung needs many slots."""
    _check_identity_coordinates(rung, slot)
    pair_sum = rung + slot
    return -(pair_sum * (pair_sum + 1) // 2 + slot + 1)


def bot_name(rung: int, slot: int) -> str:
    _check_identity_coordinates(rung, slot)
    return f"棋友·{rung}·{slot}"


def idle_reserve_deficit(config: Mapping[str, object], idle_now: Mapping[int, int]) -> dict[int, int]:
    """Count missing unreserved bots independently at each playable rung."""
    normalized = validate_config(config)
    targets = normalized["idle_targets"]
    assert isinstance(targets, dict)
    if any(type(count) is not int or count < 0 for count in idle_now.values()):
        raise ValueError("idle bot counts must be nonnegative integers")
    if not normalized["enabled"]:
        return {int(rung): 0 for rung in targets}
    return {int(rung): max(0, target - idle_now.get(int(rung), 0)) for rung, target in targets.items()}


def choose_next_rung(eligible_rungs: Iterable[int], *, after_rung: int | None = None) -> int | None:
    """Select the next eligible rung in catalog order, wrapping at the end."""
    raw_rungs = tuple(eligible_rungs)
    playable = {level.rung for level in playable_rungs()}
    if any(type(rung) is not int or rung not in playable for rung in raw_rungs):
        raise ValueError("rotation contains an unplayable rung")
    if after_rung is not None and type(after_rung) is not int:
        raise ValueError("after_rung must be an integer or None")
    eligible = sorted(set(raw_rungs))
    return next(
        (rung for rung in eligible if after_rung is None or rung > after_rung),
        eligible[0] if eligible else None,
    )


def next_move_delay(rng: random.Random | None = None) -> int:
    """Draw an independent 5..30-second delay for each bot turn."""
    return (rng or random).randint(5, 30)
