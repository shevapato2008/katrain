"""Transactional persistence boundary for cloud-authoritative Xiangqi ranked play.

Inputs to this module are already validated domain values. HTTP parsing, token
validation, terminal rule replay, opponent selection, and rating math belong to
the service layer. This repository owns row locks, CAS, idempotency and the one
transaction that turns a reservation into an immutable receipt fact.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from smartbox_xiangqi_ranked import SCORING_CONTRACT_VERSION, canonical_json

from katrain.web.core import models_db


class XiangqiRankedConflict(ValueError):
    """Base class for deterministic ranked transaction conflicts."""


class StaleProfile(XiangqiRankedConflict):
    """The profile version used to create a preview is no longer current."""


class ReservationConflict(XiangqiRankedConflict):
    """A reservation barrier exists or cannot take the requested transition."""


class TerminalConflict(XiangqiRankedConflict):
    """A different immutable terminal fact already won for this game."""


FailureHook = Callable[[str], None]
ReservationProposalFactory = Callable[[models_db.XiangqiRatingProfile], "XiangqiRankedReservationDraft"]


@dataclass(frozen=True)
class XiangqiRankedReservationDraft:
    """Service-computed promise derived only from the transaction-locked profile."""

    expected_profile_version: int
    projection_fingerprint: str
    frozen_snapshot: Mapping[str, Any]


@dataclass(frozen=True)
class XiangqiRankedReservationRecord:
    """Stable value returned after a repository-owned session is closed."""

    reservation_id: str
    game_id: str
    user_uuid: str
    device_id: str
    status: str
    expected_profile_version: int
    projection_fingerprint: str
    frozen_snapshot: Mapping[str, Any]
    last_heartbeat_at: datetime
    created_at: datetime
    materialized_at: datetime | None
    terminal_at: datetime | None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _copy_canonical_snapshot(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be a mapping")
    # The shared encoder rejects JSON floats, NaN/Infinity and unsupported
    # values. Exact binary64 fields cross this boundary only as float.hex().
    canonical_json(value)
    return deepcopy(dict(value))


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _reservation_record(row: models_db.XiangqiRankedReservation) -> XiangqiRankedReservationRecord:
    return XiangqiRankedReservationRecord(
        reservation_id=row.reservation_id,
        game_id=row.game_id,
        user_uuid=row.user_uuid,
        device_id=row.device_id,
        status=row.status,
        expected_profile_version=row.expected_profile_version,
        projection_fingerprint=row.projection_fingerprint,
        frozen_snapshot=_freeze_json(row.frozen_snapshot),
        last_heartbeat_at=row.last_heartbeat_at,
        created_at=row.created_at,
        materialized_at=row.materialized_at,
        terminal_at=row.terminal_at,
    )


class XiangqiRankedRepository:
    """Own cloud profile/reservation/ledger locking and commit boundaries."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _begin_write_transaction(session) -> None:
        if session.get_bind().dialect.name == "sqlite":
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    def get_or_create_profile_for_update(
        self,
        session,
        user_uuid: str,
        *,
        now: datetime,
        active_algo_version: int = SCORING_CONTRACT_VERSION,
    ) -> models_db.XiangqiRatingProfile:
        """Return a locked ORM row valid only inside the caller-owned session."""

        user = session.execute(
            select(models_db.User).where(models_db.User.uuid == user_uuid).with_for_update()
        ).scalar_one_or_none()
        if user is None:
            raise ValueError(f"unknown user_uuid: {user_uuid}")
        profile = session.execute(
            select(models_db.XiangqiRatingProfile)
            .where(models_db.XiangqiRatingProfile.user_uuid == user_uuid)
            .with_for_update()
        ).scalar_one_or_none()
        if profile is None:
            profile = models_db.XiangqiRatingProfile(
                user_uuid=user_uuid,
                rating=1000.0,
                rated_games=0,
                profile_version=0,
                active_algo_version=active_algo_version,
                settlement_seq=0,
                updated_at=now,
            )
            session.add(profile)
            session.flush()
        return profile

    def create_reservation_cas(
        self,
        *,
        user_uuid: str,
        reservation_id: str,
        game_id: str,
        device_id: str,
        expected_profile_version: int,
        projection_fingerprint: str,
        frozen_snapshot: Mapping[str, Any],
        now: datetime,
    ) -> XiangqiRankedReservationRecord:
        frozen = _copy_canonical_snapshot(frozen_snapshot, "frozen_snapshot")
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            profile = self.get_or_create_profile_for_update(session, user_uuid, now=now)
            if profile.profile_version != expected_profile_version:
                raise StaleProfile(
                    f"expected profile version {expected_profile_version}, current version is {profile.profile_version}"
                )
            active = session.execute(
                select(models_db.XiangqiRankedReservation)
                .where(
                    models_db.XiangqiRankedReservation.user_uuid == user_uuid,
                    models_db.XiangqiRankedReservation.status == "reserved",
                )
                .with_for_update()
            ).scalar_one_or_none()
            if active is not None:
                raise ReservationConflict("account already has a reserved Xiangqi ranked game")
            reservation = models_db.XiangqiRankedReservation(
                reservation_id=reservation_id,
                game_id=game_id,
                user_uuid=user_uuid,
                device_id=device_id,
                status="reserved",
                expected_profile_version=expected_profile_version,
                projection_fingerprint=projection_fingerprint,
                frozen_snapshot=frozen,
                last_heartbeat_at=now,
                created_at=now,
                materialized_at=None,
                terminal_at=None,
            )
            session.add(reservation)
            session.flush()
            record = _reservation_record(reservation)
            session.commit()
            return record
        except (StaleProfile, ReservationConflict):
            session.rollback()
            raise
        except IntegrityError as exc:
            session.rollback()
            raise ReservationConflict("reservation CAS lost to another writer or game_id already exists") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_reservation_locked(
        self,
        *,
        user_uuid: str,
        reservation_id: str,
        game_id: str,
        device_id: str,
        capability_jti: str,
        proposal_factory: ReservationProposalFactory,
        now: datetime,
    ) -> XiangqiRankedReservationRecord:
        """Build and insert one promise while the account profile lock remains held.

        The service callback owns pure catalog/scoring projection and request
        comparison. This repository owns the profile/barrier locks and makes the
        reservation plus initial capability JTI visible in one commit.
        """

        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            profile = self.get_or_create_profile_for_update(session, user_uuid, now=now)
            active = session.execute(
                select(models_db.XiangqiRankedReservation)
                .where(
                    models_db.XiangqiRankedReservation.user_uuid == user_uuid,
                    models_db.XiangqiRankedReservation.status == "reserved",
                )
                .with_for_update()
            ).scalar_one_or_none()
            if active is not None:
                raise ReservationConflict("account already has a reserved Xiangqi ranked game")
            proposal = proposal_factory(profile)
            if proposal.expected_profile_version != profile.profile_version:
                raise StaleProfile("reservation proposal does not match the locked profile version")
            frozen = _copy_canonical_snapshot(proposal.frozen_snapshot, "frozen_snapshot")
            reservation = models_db.XiangqiRankedReservation(
                reservation_id=reservation_id,
                game_id=game_id,
                user_uuid=user_uuid,
                device_id=device_id,
                status="reserved",
                expected_profile_version=proposal.expected_profile_version,
                projection_fingerprint=proposal.projection_fingerprint,
                frozen_snapshot=frozen,
                last_heartbeat_at=now,
                created_at=now,
                materialized_at=None,
                terminal_at=None,
            )
            session.add(reservation)
            session.add(
                models_db.XiangqiRankedCapabilityJti(
                    jti=capability_jti,
                    reservation_id=reservation_id,
                    issued_at=now,
                    revoked_at=None,
                )
            )
            session.flush()
            record = _reservation_record(reservation)
            session.commit()
            return record
        except (StaleProfile, ReservationConflict):
            session.rollback()
            raise
        except IntegrityError as exc:
            session.rollback()
            raise ReservationConflict("reservation or initial capability lost an atomic uniqueness race") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def heartbeat(
        self,
        *,
        user_uuid: str,
        reservation_id: str,
        device_id: str,
        now: datetime,
    ) -> XiangqiRankedReservationRecord:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            reservation = session.execute(
                select(models_db.XiangqiRankedReservation)
                .where(models_db.XiangqiRankedReservation.reservation_id == reservation_id)
                .with_for_update()
            ).scalar_one_or_none()
            if (
                reservation is None
                or reservation.user_uuid != user_uuid
                or reservation.device_id != device_id
                or reservation.status != "reserved"
            ):
                raise ReservationConflict("reserved Xiangqi ranked game not found for heartbeat")
            if _as_utc(now) < _as_utc(reservation.last_heartbeat_at):
                raise ReservationConflict("heartbeat time cannot move backwards")
            reservation.last_heartbeat_at = now
            if reservation.materialized_at is None:
                reservation.materialized_at = now
            session.flush()
            record = _reservation_record(reservation)
            session.commit()
            return record
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def void_unmaterialized(self, *, user_uuid: str, reservation_id: str, game_id: str) -> bool:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            # Match terminal lock order so a void cannot deadlock a settlement.
            profile = session.execute(
                select(models_db.XiangqiRatingProfile)
                .where(models_db.XiangqiRatingProfile.user_uuid == user_uuid)
                .with_for_update()
            ).scalar_one_or_none()
            if profile is None:
                raise ReservationConflict("ranked profile not found")
            reservation = session.execute(
                select(models_db.XiangqiRankedReservation)
                .where(models_db.XiangqiRankedReservation.reservation_id == reservation_id)
                .with_for_update()
            ).scalar_one_or_none()
            if reservation is None:
                session.rollback()
                return False
            if reservation.user_uuid != user_uuid or reservation.game_id != game_id:
                raise ReservationConflict("reservation ownership mismatch")
            if reservation.status != "reserved":
                raise ReservationConflict("terminal reservation cannot be voided")
            if reservation.materialized_at is not None:
                raise ReservationConflict("materialized reservation cannot be voided")
            capabilities = session.execute(
                select(models_db.XiangqiRankedCapabilityJti).where(
                    models_db.XiangqiRankedCapabilityJti.reservation_id == reservation_id
                )
            ).scalars()
            for capability in capabilities:
                session.delete(capability)
            session.delete(reservation)
            session.commit()
            return True
        except ReservationConflict:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def settle_terminal(
        self,
        *,
        user_uuid: str,
        reservation_id: str,
        game_id: str,
        device_id: str,
        terminal_status: str,
        local_seq: int,
        payload_hash: str,
        canonical_payload: Mapping[str, Any],
        result: str | None,
        counted: bool,
        reason: str | None,
        rating_after: float | None,
        rating_delta: int | None,
        tier_before: str,
        tier_after: str | None,
        receipt_id: str,
        now: datetime,
        failure_hook: FailureHook | None = None,
    ) -> dict[str, Any]:
        payload = _copy_canonical_snapshot(canonical_payload, "canonical_payload")
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            receipt = self._settle_in_session(
                session,
                user_uuid=user_uuid,
                reservation_id=reservation_id,
                game_id=game_id,
                device_id=device_id,
                terminal_status=terminal_status,
                local_seq=local_seq,
                payload_hash=payload_hash,
                canonical_payload=payload,
                result=result,
                counted=counted,
                reason=reason,
                rating_after=rating_after,
                rating_delta=rating_delta,
                tier_before=tier_before,
                tier_after=tier_after,
                receipt_id=receipt_id,
                now=now,
                stale_after=None,
                failure_hook=failure_hook,
            )
            session.commit()
            return receipt
        except (ReservationConflict, TerminalConflict, StaleProfile):
            session.rollback()
            raise
        except IntegrityError as exc:
            session.rollback()
            existing = self._receipt_after_integrity_error(
                session,
                user_uuid=user_uuid,
                game_id=game_id,
                terminal_status=terminal_status,
                payload_hash=payload_hash,
            )
            if existing is not None:
                return existing
            raise TerminalConflict("terminal transaction lost an immutable uniqueness race") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def force_resign_after_threshold(
        self,
        *,
        user_uuid: str,
        reservation_id: str,
        game_id: str,
        now: datetime,
        stale_after: timedelta,
        local_seq: int,
        payload_hash: str,
        canonical_payload: Mapping[str, Any],
        rating_after: float,
        rating_delta: int,
        tier_before: str,
        tier_after: str,
        receipt_id: str,
        failure_hook: FailureHook | None = None,
    ) -> dict[str, Any]:
        payload = _copy_canonical_snapshot(canonical_payload, "canonical_payload")
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            receipt = self._settle_in_session(
                session,
                user_uuid=user_uuid,
                reservation_id=reservation_id,
                game_id=game_id,
                device_id=None,
                terminal_status="resigned",
                local_seq=local_seq,
                payload_hash=payload_hash,
                canonical_payload=payload,
                result="loss",
                counted=True,
                reason=None,
                rating_after=rating_after,
                rating_delta=rating_delta,
                tier_before=tier_before,
                tier_after=tier_after,
                receipt_id=receipt_id,
                now=now,
                stale_after=stale_after,
                failure_hook=failure_hook,
            )
            session.commit()
            return receipt
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _settle_in_session(
        self,
        session,
        *,
        user_uuid: str,
        reservation_id: str,
        game_id: str,
        device_id: str | None,
        terminal_status: str,
        local_seq: int,
        payload_hash: str,
        canonical_payload: dict[str, Any],
        result: str | None,
        counted: bool,
        reason: str | None,
        rating_after: float | None,
        rating_delta: int | None,
        tier_before: str,
        tier_after: str | None,
        receipt_id: str,
        now: datetime,
        stale_after: timedelta | None,
        failure_hook: FailureHook | None,
    ) -> dict[str, Any]:
        existing = session.execute(
            select(models_db.XiangqiRankedLedger).where(models_db.XiangqiRankedLedger.game_id == game_id)
        ).scalar_one_or_none()
        if existing is not None:
            return self._replay_or_conflict(existing, user_uuid, terminal_status, payload_hash)

        profile = self.get_or_create_profile_for_update(session, user_uuid, now=now)
        reservation = session.execute(
            select(models_db.XiangqiRankedReservation)
            .where(models_db.XiangqiRankedReservation.reservation_id == reservation_id)
            .with_for_update()
        ).scalar_one_or_none()
        if reservation is None or reservation.user_uuid != user_uuid or reservation.game_id != game_id:
            raise ReservationConflict("reserved Xiangqi ranked game not found")
        if device_id is not None and reservation.device_id != device_id:
            raise ReservationConflict("reservation device mismatch")
        if reservation.status != "reserved":
            existing = session.execute(
                select(models_db.XiangqiRankedLedger).where(models_db.XiangqiRankedLedger.game_id == game_id)
            ).scalar_one_or_none()
            if existing is not None:
                return self._replay_or_conflict(existing, user_uuid, terminal_status, payload_hash)
            raise TerminalConflict(f"reservation is already {reservation.status}")
        if reservation.expected_profile_version != profile.profile_version:
            raise StaleProfile("reservation profile version no longer matches authority")
        if stale_after is not None and _as_utc(now) - _as_utc(reservation.last_heartbeat_at) < stale_after:
            raise ReservationConflict("reservation heartbeat is still within the takeover threshold")
        self._validate_terminal_values(
            terminal_status=terminal_status,
            result=result,
            counted=counted,
            reason=reason,
            rating_after=rating_after,
            rating_delta=rating_delta,
            tier_after=tier_after,
        )

        rating_before = float(profile.rating)
        profile_version_before = profile.profile_version
        settlement_seq = profile.settlement_seq + 1
        profile_version_after = profile_version_before + (1 if counted else 0)
        if counted:
            profile.rating = rating_after
            profile.rated_games += 1
            profile.profile_version = profile_version_after
        profile.settlement_seq = settlement_seq
        profile.updated_at = now
        reservation.status = terminal_status
        reservation.terminal_at = now
        if reservation.materialized_at is None:
            reservation.materialized_at = now

        receipt = {
            "receipt_id": receipt_id,
            "game_id": game_id,
            "reservation_id": reservation_id,
            "payload_hash": payload_hash,
            "status": terminal_status,
            "counted": counted,
            "reason": reason,
            "rating_before_hex": rating_before.hex(),
            "rating_after_hex": rating_after.hex() if rating_after is not None else None,
            "delta": rating_delta,
            "tier_before": tier_before,
            "tier_after": tier_after,
            "profile_version_after": profile_version_after,
            "settlement_seq": settlement_seq,
            "profile": {
                "user_uuid": user_uuid,
                "rating_hex": (rating_after if counted else rating_before).hex(),
                "rated_games": profile.rated_games,
                "profile_version": profile_version_after,
                "active_algo_version": profile.active_algo_version,
                "settlement_seq": settlement_seq,
            },
        }
        ledger = models_db.XiangqiRankedLedger(
            game_id=game_id,
            receipt_id=receipt_id,
            reservation_id=reservation_id,
            user_uuid=user_uuid,
            device_id=reservation.device_id,
            local_seq=local_seq,
            terminal_status=terminal_status,
            payload_hash=payload_hash,
            canonical_payload=deepcopy(canonical_payload),
            frozen_snapshot=deepcopy(dict(reservation.frozen_snapshot)),
            result=result,
            counted=counted,
            reason=reason,
            rating_before=rating_before,
            rating_after=rating_after,
            rating_delta=rating_delta,
            tier_before=tier_before,
            tier_after=tier_after,
            profile_version_before=profile_version_before,
            profile_version_after=profile_version_after,
            settlement_seq=settlement_seq,
            received_at=now,
            settled_at=now,
            receipt=deepcopy(receipt),
        )
        session.add(ledger)
        session.flush()
        if failure_hook is not None:
            failure_hook("before_commit")
        return receipt

    @staticmethod
    def _validate_terminal_values(
        *,
        terminal_status: str,
        result: str | None,
        counted: bool,
        reason: str | None,
        rating_after: float | None,
        rating_delta: int | None,
        tier_after: str | None,
    ) -> None:
        if terminal_status not in {"settled", "resigned", "system_aborted"}:
            raise ValueError("unsupported terminal status")
        if terminal_status == "system_aborted":
            if (
                counted
                or reason is None
                or result is not None
                or any(value is not None for value in (rating_after, rating_delta, tier_after))
            ):
                raise ValueError("system_aborted must be an uncounted reason without rating output")
            return
        if not counted or reason is not None or result not in {"win", "draw", "loss"}:
            raise ValueError("settled/resigned terminals must be counted conclusive results")
        if terminal_status == "resigned" and result != "loss":
            raise ValueError("resigned terminal must be a loss")
        if rating_after is None or rating_delta is None or tier_after is None:
            raise ValueError("counted terminal requires complete rating output")

    @staticmethod
    def _replay_or_conflict(existing, user_uuid: str, terminal_status: str, payload_hash: str) -> dict[str, Any]:
        if (
            existing.user_uuid == user_uuid
            and existing.terminal_status == terminal_status
            and existing.payload_hash == payload_hash
        ):
            return deepcopy(dict(existing.receipt))
        raise TerminalConflict(
            f"game already has immutable terminal status {existing.terminal_status} and payload {existing.payload_hash}"
        )

    def _receipt_after_integrity_error(
        self, session, *, user_uuid: str, game_id: str, terminal_status: str, payload_hash: str
    ) -> dict[str, Any] | None:
        existing = session.execute(
            select(models_db.XiangqiRankedLedger).where(models_db.XiangqiRankedLedger.game_id == game_id)
        ).scalar_one_or_none()
        if existing is None:
            return None
        return self._replay_or_conflict(existing, user_uuid, terminal_status, payload_hash)

    def get_receipt(self, *, user_uuid: str, game_id: str) -> dict[str, Any] | None:
        session = self.session_factory()
        try:
            ledger = session.execute(
                select(models_db.XiangqiRankedLedger).where(
                    models_db.XiangqiRankedLedger.user_uuid == user_uuid,
                    models_db.XiangqiRankedLedger.game_id == game_id,
                )
            ).scalar_one_or_none()
            return None if ledger is None else deepcopy(dict(ledger.receipt))
        finally:
            session.close()

    def page_device_statuses(
        self,
        *,
        user_uuid: str,
        device_id: str,
        after_local_seq: int,
        through_local_seq: int,
        limit: int = 100,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be in 1..100")
        session = self.session_factory()
        try:
            rows = (
                session.execute(
                    select(models_db.XiangqiRankedLedger)
                    .where(
                        models_db.XiangqiRankedLedger.user_uuid == user_uuid,
                        models_db.XiangqiRankedLedger.device_id == device_id,
                        models_db.XiangqiRankedLedger.local_seq > after_local_seq,
                        models_db.XiangqiRankedLedger.local_seq <= through_local_seq,
                    )
                    .order_by(models_db.XiangqiRankedLedger.local_seq)
                    .limit(limit + 1)
                )
                .scalars()
                .all()
            )
            has_more = len(rows) > limit
            page = rows[:limit]
            items = [
                {
                    "game_id": row.game_id,
                    "local_seq": row.local_seq,
                    "payload_hash": row.payload_hash,
                    "status": row.terminal_status,
                    "receipt": deepcopy(dict(row.receipt)),
                }
                for row in page
            ]
            return {
                "items": items,
                "next_cursor": page[-1].local_seq if page else after_local_seq,
                "has_more": has_more,
            }
        finally:
            session.close()

    def page_settlement_summaries(
        self,
        *,
        user_uuid: str,
        after_seq: int,
        snapshot_seq: int,
        limit: int = 100,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be in 1..100")
        session = self.session_factory()
        try:
            rows = (
                session.execute(
                    select(models_db.XiangqiRankedLedger)
                    .where(
                        models_db.XiangqiRankedLedger.user_uuid == user_uuid,
                        models_db.XiangqiRankedLedger.settlement_seq > after_seq,
                        models_db.XiangqiRankedLedger.settlement_seq <= snapshot_seq,
                    )
                    .order_by(models_db.XiangqiRankedLedger.settlement_seq)
                    .limit(limit + 1)
                )
                .scalars()
                .all()
            )
            has_more = len(rows) > limit
            page = rows[:limit]
            items = [deepcopy(dict(row.receipt)) for row in page]
            return {
                "items": items,
                "next_cursor": page[-1].settlement_seq if page else after_seq,
                "has_more": has_more,
            }
        finally:
            session.close()
