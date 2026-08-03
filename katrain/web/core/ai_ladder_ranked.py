"""Transactional domain service for the independent ranked-AI ladder."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from sqlalchemy.exc import IntegrityError

from katrain.web.core import models_db

AI_LADDER_GAME_TYPE = "ai_ladder_ranked"
PLACEMENT_GAMES = 5


@dataclass(frozen=True)
class AiLadderOpponentSnapshot:
    rung: int
    rank_name: str
    config_snapshot: Mapping[str, Any]
    certification_status: str
    availability: str
    route: str

    def __post_init__(self) -> None:
        if type(self.rung) is not int or not 1 <= self.rung <= 41:
            raise ValueError("opponent rung must be an integer in 1..41")
        if not isinstance(self.rank_name, str) or not self.rank_name.strip():
            raise ValueError("opponent rank_name must be non-empty")
        if not isinstance(self.config_snapshot, Mapping):
            raise ValueError("opponent config_snapshot must be a mapping")
        if self.route not in {"local", "server"}:
            raise ValueError("opponent route must be local or server")


@dataclass(frozen=True)
class AiLadderSettlementResult:
    counted: bool
    replayed: bool
    reason: Optional[str]
    ai_ladder_rung: Optional[int]
    placement_lo: Optional[int]
    placement_hi: Optional[int]
    placement_completed: Optional[int]
    net_score: Optional[int]


def initial_placement_window(legacy_rank: Optional[str]) -> tuple[int, int]:
    """Map a legacy rank to a 32-rung search window without granting a rung."""

    mapped = _legacy_rank_to_rung(legacy_rank)
    if mapped is None:
        return 1, 32
    start = max(1, min(mapped - 16, 10))
    return start, start + 31


def _legacy_rank_to_rung(legacy_rank: Optional[str]) -> Optional[int]:
    if not isinstance(legacy_rank, str):
        return None
    rank = legacy_rank.strip().lower()
    if len(rank) < 2 or not rank[:-1].isdigit():
        return None
    value = int(rank[:-1])
    if rank.endswith("k") and 1 <= value <= 20:
        return 21 - value
    if rank.endswith("d") and value >= 1:
        return min(20 + 2 * value, 38)
    return None


class AiLadderRankedRepository:
    """Own the complete lock/load/ledger/update/commit settlement boundary."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def settle_game(
        self,
        *,
        user_id: int,
        game_id: str,
        user_color: str,
        result: str,
        game_type: str,
        opponent: AiLadderOpponentSnapshot,
    ) -> AiLadderSettlementResult:
        ignored_reason = self._ignored_reason(game_type=game_type, result=result, opponent=opponent)
        if ignored_reason is not None:
            return self._ignored(ignored_reason)
        if user_color not in {"B", "W"}:
            raise ValueError("user_color must be B or W")
        if not isinstance(game_id, str) or not game_id.strip():
            raise ValueError("game_id must be non-empty")

        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            existing = (
                session.query(models_db.AiLadderGameLedger)
                .filter(models_db.AiLadderGameLedger.game_id == game_id)
                .one_or_none()
            )
            if existing is not None:
                return self._replay_result(session, existing, user_id)

            user = session.query(models_db.User).filter(models_db.User.id == user_id).with_for_update().one_or_none()
            if user is None:
                raise ValueError(f"unknown user_id: {user_id}")

            profile = (
                session.query(models_db.AiLadderProfile)
                .filter(models_db.AiLadderProfile.user_id == user_id)
                .with_for_update()
                .one_or_none()
            )
            if profile is None:
                lo, hi = initial_placement_window(user.rank)
                expected_opponent_rung = (lo + hi) // 2
                if opponent.rung != expected_opponent_rung:
                    return self._ignored("opponent_rung_mismatch")
                profile = models_db.AiLadderProfile(
                    user_id=user_id,
                    ai_ladder_rung=None,
                    placement_lo=lo,
                    placement_hi=hi,
                    placement_completed=0,
                    net_score=0,
                    version=0,
                )
                session.add(profile)
            else:
                expected_opponent_rung = (
                    profile.ai_ladder_rung
                    if profile.ai_ladder_rung is not None
                    else (profile.placement_lo + profile.placement_hi) // 2
                )
                if opponent.rung != expected_opponent_rung:
                    return self._ignored("opponent_rung_mismatch")

            ledger = models_db.AiLadderGameLedger(
                game_id=game_id,
                user_id=user_id,
                user_color=user_color,
                result=result,
                game_type=game_type,
                opponent_rung=opponent.rung,
                opponent_rank_name=opponent.rank_name,
                opponent_config_snapshot=deepcopy(dict(opponent.config_snapshot)),
                opponent_certification_status=opponent.certification_status,
                opponent_availability=opponent.availability,
                opponent_route=opponent.route,
            )
            session.add(ledger)
            self._apply_result(profile, result)
            profile.version += 1

            session.commit()
            return self._counted_result(profile)
        except IntegrityError:
            session.rollback()
            existing = (
                session.query(models_db.AiLadderGameLedger)
                .filter(models_db.AiLadderGameLedger.game_id == game_id)
                .one_or_none()
            )
            if existing is None:
                raise
            return self._replay_result(session, existing, user_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _begin_write_transaction(session) -> None:
        """Serialize SQLite writers before any profile or idempotency reads.

        PostgreSQL uses the row locks below. SQLite ignores ``FOR UPDATE``, so
        BEGIN IMMEDIATE obtains its database write reservation up front and
        prevents two callbacks from reading the same profile version.
        """

        if session.get_bind().dialect.name == "sqlite":
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    @staticmethod
    def _ignored_reason(*, game_type: str, result: str, opponent: AiLadderOpponentSnapshot) -> Optional[str]:
        if game_type != AI_LADDER_GAME_TYPE:
            return "invalid_game_type"
        if result not in {"win", "loss"}:
            return "inconclusive"
        if opponent.certification_status != "certified" or opponent.availability != "available":
            return "opponent_not_eligible"
        return None

    @staticmethod
    def _apply_result(profile: models_db.AiLadderProfile, result: str) -> None:
        if profile.ai_ladder_rung is None:
            mid = (profile.placement_lo + profile.placement_hi) // 2
            if result == "win":
                profile.placement_lo = mid + 1
            else:
                profile.placement_hi = mid
            profile.placement_completed += 1
            if profile.placement_completed == PLACEMENT_GAMES:
                profile.ai_ladder_rung = profile.placement_lo
                profile.net_score = 0
            return

        profile.net_score += 1 if result == "win" else -1
        if profile.net_score >= 3:
            profile.ai_ladder_rung = min(profile.ai_ladder_rung + 1, 41)
            profile.net_score = 0
        elif profile.net_score <= -3:
            profile.ai_ladder_rung = max(profile.ai_ladder_rung - 1, 1)
            profile.net_score = 0

    @staticmethod
    def _ignored(reason: str) -> AiLadderSettlementResult:
        return AiLadderSettlementResult(
            counted=False,
            replayed=False,
            reason=reason,
            ai_ladder_rung=None,
            placement_lo=None,
            placement_hi=None,
            placement_completed=None,
            net_score=None,
        )

    @staticmethod
    def _counted_result(profile: models_db.AiLadderProfile, *, replayed: bool = False) -> AiLadderSettlementResult:
        return AiLadderSettlementResult(
            counted=True,
            replayed=replayed,
            reason=None,
            ai_ladder_rung=profile.ai_ladder_rung,
            placement_lo=profile.placement_lo,
            placement_hi=profile.placement_hi,
            placement_completed=profile.placement_completed,
            net_score=profile.net_score,
        )

    def _replay_result(self, session, ledger: models_db.AiLadderGameLedger, user_id: int) -> AiLadderSettlementResult:
        if ledger.user_id != user_id:
            raise ValueError("game_id belongs to another user")
        profile = session.get(models_db.AiLadderProfile, user_id)
        if profile is None:
            raise RuntimeError("settled game has no AI ladder profile")
        return self._counted_result(profile, replayed=True)
