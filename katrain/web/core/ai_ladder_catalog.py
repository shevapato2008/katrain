"""Stable product projection and immutable per-game snapshots for the AI ladder."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
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


def frozen_recipe_identity(recipe: object) -> str:
    """Return the stable identity for the exact recipe used by the running game."""

    to_dict = getattr(recipe, "to_dict", None)
    if not callable(to_dict):
        raise ValueError("ranked AI runtime has no frozen recipe")
    canonical = json.dumps(to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_opponent_snapshot(rung: int) -> tuple[AiLadderOpponentSnapshot, str]:
    """Resolve exactly one rung and freeze its recipe identity without any fallback."""

    from katrain.core import ladder

    if type(rung) is not int or not 1 <= rung <= len(ladder.LADDER_LEVELS):
        raise ValueError("AI ladder rung is outside the product catalog")
    level = ladder.LADDER_LEVELS[rung - 1]
    if level.rung != rung:
        raise RuntimeError("AI ladder catalog is not ordered by rung")
    if level.recipe is None:
        # No amount of dev switching conjures a recipe that was never fitted.
        raise ValueError("selected AI ladder opponent has no fitted recipe")
    if level.certification_status != "certified" or level.availability != "available":
        # KATRAIN_LADDER_ALLOW_PROVISIONAL lets a deployment exercise the whole rated
        # pipeline before any rung is certified (read per call, never cached — see
        # ladder.provisional_play_allowed). It does NOT launder the rung: the snapshot
        # below still carries the real certification_status/availability, so the frozen
        # opponent record and the ledger say the game was played on an unmeasured rung.
        if not ladder.provisional_play_allowed():
            raise ValueError("selected AI ladder opponent is not certified and available")

    recipe = level.recipe.to_dict()
    identity = frozen_recipe_identity(level.recipe)
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


def frozen_recipe_from_snapshot(opponent: AiLadderOpponentSnapshot):
    """Rebuild the immutable LadderRung that the game must use for every move."""

    from katrain.core.ladder import LadderRung

    recipe = opponent.config_snapshot.get("recipe")
    if not isinstance(recipe, Mapping):
        raise ValueError("opponent snapshot has no frozen recipe")
    frozen = LadderRung(**deepcopy(dict(recipe)))
    if frozen.rung != opponent.rung or frozen.rank_name != opponent.rank_name:
        raise ValueError("frozen recipe identity does not match opponent snapshot")
    return frozen


def result_for_user(saved_result: str, user_color: str) -> str:
    """Derive the ladder result exclusively from a persisted authoritative result."""

    if not isinstance(saved_result, str) or not saved_result.strip():
        raise ValueError("ranked AI game has no authoritative saved result")
    winner = saved_result.strip().upper()[:1]
    if winner in {"B", "W"} and "+" in saved_result:
        return "win" if winner == user_color else "loss"
    return "inconclusive"


def session_snapshot_from_pending(pending: Mapping[str, Any]) -> AiLadderSessionSnapshot:
    opponent = AiLadderOpponentSnapshot(
        rung=pending["opponent_rung"],
        rank_name=pending["opponent_rank_name"],
        config_snapshot=pending["opponent_config_snapshot"],
        certification_status=pending["opponent_certification_status"],
        availability=pending["opponent_availability"],
        route=pending["opponent_route"],
    )
    return AiLadderSessionSnapshot(
        game_id=pending["game_id"],
        session_id=pending["session_id"],
        user_id=pending["user_id"],
        user_color=pending["user_color"],
        game_type=pending["game_type"],
        opponent=opponent,
        ai_subtype=pending["ai_subtype"],
        execution_identity=pending["execution_identity"],
    )
