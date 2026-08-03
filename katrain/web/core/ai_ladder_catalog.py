"""Stable product projection and immutable per-game snapshots for the AI ladder."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from katrain.web.core.ai_ladder_ranked import AI_LADDER_GAME_TYPE, AiLadderOpponentSnapshot


def catalog_projection() -> dict[str, list[dict[str, object]]]:
    """Expose only the stable product contract; the catalog remains the single name source."""

    from katrain.core import ladder

    return {
        "rungs": [
            {
                "rung": level.rung,
                "rank_name": level.rank_name,
                "certification_status": level.certification_status,
                "availability": level.availability,
                "route": level.route,
            }
            for level in ladder.LADDER_LEVELS
        ]
    }


def catalog_entry(rung: int) -> dict[str, object]:
    entries = catalog_projection()["rungs"]
    if type(rung) is not int or not 1 <= rung <= len(entries):
        raise ValueError("AI ladder rung is outside the product catalog")
    entry = entries[rung - 1]
    if entry["rung"] != rung:
        raise RuntimeError("AI ladder catalog is not ordered by rung")
    return entry


def build_opponent_snapshot(rung: int) -> tuple[AiLadderOpponentSnapshot, str]:
    """Resolve exactly one rung and freeze its recipe identity without any fallback."""

    from katrain.core import ladder

    if type(rung) is not int or not 1 <= rung <= len(ladder.LADDER_LEVELS):
        raise ValueError("AI ladder rung is outside the product catalog")
    level = ladder.LADDER_LEVELS[rung - 1]
    if level.rung != rung:
        raise RuntimeError("AI ladder catalog is not ordered by rung")
    if level.certification_status != "certified" or level.availability != "available" or level.recipe is None:
        raise ValueError("selected AI ladder opponent is not certified and available")

    recipe = level.recipe.to_dict()
    canonical = json.dumps(recipe, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    identity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    config: Mapping[str, Any] = {
        "config_digest": identity,
        "config_version": ladder.LADDER_VERSION,
        "recipe_identity": identity,
        "recipe": recipe,
    }
    return (
        AiLadderOpponentSnapshot(
            rung=level.rung,
            rank_name=level.rank_name,
            config_snapshot=config,
            certification_status=level.certification_status,
            availability=level.availability,
            route=level.route,
        ),
        identity,
    )


@dataclass(frozen=True)
class AiLadderSessionSnapshot:
    game_id: str
    session_id: str
    user_id: int
    user_color: str
    game_type: str
    opponent: AiLadderOpponentSnapshot
    ai_subtype: str
    execution_identity: str

    def __post_init__(self) -> None:
        if len(self.game_id) != 32:
            raise ValueError("game_id must be a UUID4 hex value")
        int(self.game_id, 16)
        if not self.session_id:
            raise ValueError("session_id must be non-empty")
        if self.user_color not in {"B", "W"}:
            raise ValueError("user_color must be B or W")
        if self.game_type != AI_LADDER_GAME_TYPE:
            raise ValueError("invalid ranked AI game type")
        if self.ai_subtype != "ai:ladder":
            raise ValueError("ranked AI sessions require ai:ladder")
        if not self.execution_identity:
            raise ValueError("execution identity must be non-empty")
