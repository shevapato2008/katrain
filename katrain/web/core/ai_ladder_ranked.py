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
        config = deepcopy(dict(self.config_snapshot))
        digest = config.get("config_digest")
        identity = config.get("config_version") or config.get("recipe_identity")
        if not isinstance(digest, str) or not digest.strip() or not isinstance(identity, str) or not identity.strip():
            raise ValueError(
                "opponent config_snapshot requires nonempty config_digest and config_version or recipe_identity"
            )
        object.__setattr__(self, "config_snapshot", config)
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

    def recent_counted_results(self, user_id: int, *, limit: int = 5) -> list[str]:
        """Return newest valid win/loss decisions; excluded receipts never enter recent form."""

        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        session = self.session_factory()
        try:
            rows = (
                session.query(models_db.AiLadderGameLedger.result)
                .filter(
                    models_db.AiLadderGameLedger.user_id == user_id,
                    models_db.AiLadderGameLedger.counted.is_(True),
                    models_db.AiLadderGameLedger.result.in_(("win", "loss")),
                )
                .order_by(models_db.AiLadderGameLedger.settled_at.desc(), models_db.AiLadderGameLedger.id.desc())
                .limit(limit)
                .all()
            )
            return [row[0] for row in rows]
        finally:
            session.close()

    def has_ladder_rank(self, user_id: int) -> bool:
        """Whether placement has resolved into a rung -- the rated-PvP prerequisite.

        Replaces a count of finished `game_type == "rated"` games: nothing writes
        that value for an AI game, so the counter sat at 0 forever while the lobby
        told players to go and earn it on a page that could not move it.
        """
        session = self.session_factory()
        try:
            rung = (
                session.query(models_db.AiLadderProfile.ai_ladder_rung)
                .filter(models_db.AiLadderProfile.user_id == user_id)
                .scalar()
            )
            return rung is not None
        finally:
            session.close()

    def adopt_remote_profile(self, user_id: int, profile: Mapping[str, Any]) -> bool:
        """Overwrite this node's profile with the cloud's answer for the same account.

        A board settles its own games, but an account can play on more than one device,
        and only one of them can be right about the rank. The cloud is the merge point:
        it re-ran the settlement against everything it knows, so when it replies with a
        profile, that is the number to show. Returns whether anything changed.

        A settlement the cloud did not count carries no profile (all fields null), which
        is not an instruction to reset anyone -- those are ignored.
        """
        fields = ("ai_ladder_rung", "placement_lo", "placement_hi", "placement_completed", "net_score")
        if not isinstance(profile, Mapping):
            return False
        values = {name: profile.get(name) for name in fields}
        if any(values[name] is None for name in fields if name != "ai_ladder_rung"):
            return False
        if type(values["placement_lo"]) is not int or type(values["placement_hi"]) is not int:
            return False

        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = session.get(models_db.AiLadderProfile, user_id)
            if row is None:
                row = models_db.AiLadderProfile(user_id=user_id, version=0, **values)
                session.add(row)
                session.commit()
                return True
            if all(getattr(row, name) == values[name] for name in fields):
                return False
            for name in fields:
                setattr(row, name, values[name])
            row.version = (row.version or 0) + 1
            session.commit()
            return True
        finally:
            session.close()

    def create_pending_game(self, snapshot) -> None:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            session.add(
                models_db.AiLadderPendingGame(
                    game_id=snapshot.game_id,
                    user_id=snapshot.user_id,
                    session_id=snapshot.session_id,
                    user_color=snapshot.user_color,
                    game_type=snapshot.game_type,
                    opponent_rung=snapshot.opponent.rung,
                    opponent_rank_name=snapshot.opponent.rank_name,
                    opponent_config_snapshot=deepcopy(dict(snapshot.opponent.config_snapshot)),
                    opponent_certification_status=snapshot.opponent.certification_status,
                    opponent_availability=snapshot.opponent.availability,
                    opponent_route=snapshot.opponent.route,
                    ai_subtype=snapshot.ai_subtype,
                    execution_identity=snapshot.execution_identity,
                    game_saved=False,
                    saved_result=None,
                )
            )
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError("user already has a pending ranked AI game") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_pending_game(self, user_id: int) -> Optional[dict[str, Any]]:
        session = self.session_factory()
        try:
            row = (
                session.query(models_db.AiLadderPendingGame)
                .filter(models_db.AiLadderPendingGame.user_id == user_id)
                .one_or_none()
            )
            if row is None:
                return None
            return {
                "game_id": row.game_id,
                "user_id": row.user_id,
                "session_id": row.session_id,
                "user_color": row.user_color,
                "game_type": row.game_type,
                "opponent_rung": row.opponent_rung,
                "opponent_rank_name": row.opponent_rank_name,
                "opponent_config_snapshot": deepcopy(dict(row.opponent_config_snapshot)),
                "opponent_certification_status": row.opponent_certification_status,
                "opponent_availability": row.opponent_availability,
                "opponent_route": row.opponent_route,
                "ai_subtype": row.ai_subtype,
                "execution_identity": row.execution_identity,
                "game_saved": row.game_saved,
                "saved_result": row.saved_result,
            }
        finally:
            session.close()

    def get_settlement_receipt(self, *, user_id: int, game_id: str) -> Optional[dict[str, Any]]:
        """Return only this account's public lifecycle receipt for one ranked game."""

        session = self.session_factory()
        try:
            ledger = (
                session.query(models_db.AiLadderGameLedger)
                .filter(
                    models_db.AiLadderGameLedger.user_id == user_id,
                    models_db.AiLadderGameLedger.game_id == game_id,
                )
                .one_or_none()
            )
            if ledger is not None:
                return {
                    "state": "settled",
                    "game_id": ledger.game_id,
                    "counted": ledger.counted,
                    "reason": ledger.reason,
                }
            pending = (
                session.query(models_db.AiLadderPendingGame.game_id)
                .filter(
                    models_db.AiLadderPendingGame.user_id == user_id,
                    models_db.AiLadderPendingGame.game_id == game_id,
                )
                .one_or_none()
            )
            return {"state": "pending"} if pending is not None else None
        finally:
            session.close()

    def mark_pending_game_saved(self, *, user_id: int, game_id: str, result: str) -> None:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = (
                session.query(models_db.AiLadderPendingGame)
                .filter(
                    models_db.AiLadderPendingGame.user_id == user_id,
                    models_db.AiLadderPendingGame.game_id == game_id,
                )
                .with_for_update()
                .one_or_none()
            )
            if row is None:
                raise ValueError("pending ranked AI game not found")
            if row.game_saved and row.saved_result != result:
                raise ValueError("pending ranked AI saved result is immutable")
            row.game_saved = True
            row.saved_result = result
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def clear_pending_game(self, *, user_id: int, game_id: str) -> None:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = (
                session.query(models_db.AiLadderPendingGame)
                .filter(
                    models_db.AiLadderPendingGame.user_id == user_id,
                    models_db.AiLadderPendingGame.game_id == game_id,
                )
                .with_for_update()
                .one_or_none()
            )
            if row is not None:
                session.delete(row)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def settle_game(
        self,
        *,
        user_id: int,
        game_id: str,
        user_color: str,
        result: str,
        game_type: str,
        opponent: Optional[AiLadderOpponentSnapshot],
        engine_stalled: bool = False,
    ) -> AiLadderSettlementResult:
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

            ignored_reason = self._ignored_reason(
                game_type=game_type, result=result, opponent=opponent, engine_stalled=engine_stalled
            )
            profile = None
            if ignored_reason is None:
                assert opponent is not None
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
                        ignored_reason = "opponent_rung_mismatch"
                    else:
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
                        ignored_reason = "opponent_rung_mismatch"

            ledger = self._new_ledger(
                user_id=user_id,
                game_id=game_id,
                user_color=user_color,
                result=result,
                game_type=game_type,
                opponent=opponent,
                reason=ignored_reason,
            )
            session.add(ledger)
            if ignored_reason is not None:
                session.commit()
                return self._ignored(ignored_reason)

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
    def _ignored_reason(
        *,
        game_type: str,
        result: str,
        opponent: Optional[AiLadderOpponentSnapshot],
        engine_stalled: bool = False,
    ) -> Optional[str]:
        if game_type != AI_LADDER_GAME_TYPE:
            return "invalid_game_type"
        # The seated rung could not be played at its calibrated strength, so the AI
        # refused to move at all (interface._surface_ladder_unavailable). Whatever
        # ended the game after that -- the player giving up on a board that will
        # never answer, or the AI's own clock expiring -- is an artefact of our
        # engine, not a result. Checked before `result` so a conclusive-looking
        # B+T/W+R over a stalled board cannot bank a promotion for a game nobody
        # played. Observed on an RK3562 kiosk, 2026-08-05.
        if engine_stalled:
            return "engine_unavailable"
        if result not in {"win", "loss"}:
            return "inconclusive"
        if opponent is None:
            return "opponent_not_eligible"
        if opponent.certification_status != "certified" or opponent.availability != "available":
            # Deliberately NOT relaxed by KATRAIN_LADDER_ALLOW_PROVISIONAL. That switch
            # decides whether an uncertified rung may be SEATED; whether its result may
            # move a rank is not a per-node choice -- `ck_ai_ladder_ledger_decision`
            # refuses to store a counted row whose opponent is not certified+available,
            # because a rank earned against unmeasured strength does not mean anything.
            # So a provisional game is played, recorded, and openly not counted.
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
    def _new_ledger(
        *,
        user_id: int,
        game_id: str,
        user_color: str,
        result: str,
        game_type: str,
        opponent: Optional[AiLadderOpponentSnapshot],
        reason: Optional[str],
    ) -> models_db.AiLadderGameLedger:
        return models_db.AiLadderGameLedger(
            game_id=game_id,
            user_id=user_id,
            user_color=user_color,
            result=result,
            game_type=game_type,
            opponent_rung=opponent.rung if opponent is not None else None,
            opponent_rank_name=opponent.rank_name if opponent is not None else None,
            opponent_config_snapshot=(deepcopy(dict(opponent.config_snapshot)) if opponent is not None else None),
            opponent_certification_status=opponent.certification_status if opponent is not None else None,
            opponent_availability=opponent.availability if opponent is not None else None,
            opponent_route=opponent.route if opponent is not None else None,
            counted=reason is None,
            reason=reason,
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
        if not ledger.counted:
            return AiLadderSettlementResult(
                counted=False,
                replayed=True,
                reason=ledger.reason,
                ai_ladder_rung=None,
                placement_lo=None,
                placement_hi=None,
                placement_completed=None,
                net_score=None,
            )
        profile = session.get(models_db.AiLadderProfile, user_id)
        if profile is None:
            raise RuntimeError("settled game has no AI ladder profile")
        return self._counted_result(profile, replayed=True)
