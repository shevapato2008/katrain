"""Cloud-authoritative preview and reservation orchestration for Xiangqi ranked play."""

from __future__ import annotations

import secrets
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy import func, select

from smartbox_xiangqi_ranked import (
    SUPPORTED_CATALOGS,
    SUPPORTED_CONTRACTS,
    RatingState,
    canonical_hash,
    canonical_json,
    pick_level,
    project_three,
    tier_of,
)
from smartbox_xiangqi_ranked.canonical import hash_preview
from smartbox_xiangqi_ranked.catalog import profile_public_config

from katrain.web.core import models_db
from katrain.web.core.xiangqi_ranked_capabilities import (
    TerminalCapabilityError,
    TerminalCapabilityStore,
)
from katrain.web.core.xiangqi_ranked_repo import (
    ReservationConflict,
    StaleProfile,
    TerminalConflict,
    XiangqiRankedRepository,
    XiangqiRankedReservationDraft,
    XiangqiRankedReservationRecord,
)


FORCE_RESIGN_THRESHOLD_VERSION = 1
FORCE_RESIGN_THRESHOLD = timedelta(minutes=5)
TIME_CONTROLS = frozenset({"unlimited", "blitz5", "standard10", "slow20"})


@dataclass(frozen=True)
class RankedServiceError(ValueError):
    status_code: int
    code: str
    message: str
    context: Mapping[str, Any]

    def __init__(self, status_code: int, code: str, message: str, **context: Any):
        ValueError.__init__(self, message)
        object.__setattr__(self, "status_code", status_code)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "context", context)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else _utc(value).isoformat()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return deepcopy(value)


class XiangqiRankedService:
    def __init__(
        self,
        repository: XiangqiRankedRepository,
        capabilities: TerminalCapabilityStore,
        *,
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        color_chooser: Callable[[tuple[str, str]], str] | None = None,
        force_resign_threshold: timedelta = FORCE_RESIGN_THRESHOLD,
    ):
        self.repository = repository
        self.capabilities = capabilities
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self.color_chooser = color_chooser or secrets.choice
        self.force_resign_threshold = force_resign_threshold

    @property
    def session_factory(self):
        return self.repository.session_factory

    @staticmethod
    def _negotiate(catalog_version: str, device_contracts: Iterable[int]) -> tuple[str, int]:
        if catalog_version not in SUPPORTED_CATALOGS:
            raise RankedServiceError(
                422,
                "unsupported_catalog_version",
                "The requested engine catalog is not executable by this cloud deployment.",
            )
        requested = {value for value in device_contracts if isinstance(value, int) and not isinstance(value, bool)}
        common = requested.intersection(SUPPORTED_CONTRACTS)
        if not common:
            raise RankedServiceError(
                422,
                "unsupported_contract_version",
                "The device and cloud have no common ranked scoring contract.",
            )
        return catalog_version, max(common)

    def _active_reservation(self, session, user_uuid: str):
        return session.execute(
            select(models_db.XiangqiRankedReservation).where(
                models_db.XiangqiRankedReservation.user_uuid == user_uuid,
                models_db.XiangqiRankedReservation.status == "reserved",
            )
        ).scalar_one_or_none()

    @staticmethod
    def _reservation_summary(row) -> dict[str, Any]:
        return {
            "reservation_id": row.reservation_id,
            "game_id": row.game_id,
            "device_id": row.device_id,
            "status": row.status,
            "created_at": _iso(row.created_at),
            "last_heartbeat_at": _iso(row.last_heartbeat_at),
        }

    @staticmethod
    def _public_preview(fresh: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "code": fresh["code"],
            "profile": _plain(fresh["profile"]),
            "preview": {key: _plain(value) for key, value in fresh["preview"].items() if not key.startswith("_")},
        }

    def _compute_preview(
        self,
        *,
        user_uuid: str,
        catalog_version: str,
        supported_contract_versions: Iterable[int],
        reject_barrier: bool,
    ) -> dict[str, Any]:
        catalog_version, contract_version = self._negotiate(catalog_version, supported_contract_versions)
        now = _utc(self.now())
        session = self.session_factory()
        try:
            self.repository._begin_write_transaction(session)
            profile = self.repository.get_or_create_profile_for_update(session, user_uuid, now=now)
            active = self._active_reservation(session, user_uuid)
            active_summary = None if active is None else self._reservation_summary(active)
            if active is not None and reject_barrier:
                session.commit()
                raise RankedServiceError(
                    409,
                    "ranked_reserved_elsewhere",
                    "This account already has an active Xiangqi ranked reservation.",
                    reservation=active_summary,
                )
            fresh = self._build_preview_from_profile(
                user_uuid=user_uuid,
                rating=float(profile.rating),
                rated_games=profile.rated_games,
                profile_version=profile.profile_version,
                settlement_seq=profile.settlement_seq,
                catalog_version=catalog_version,
                contract_version=contract_version,
                active_summary=active_summary,
            )
            session.commit()
        except RankedServiceError:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return fresh

    @staticmethod
    def _build_preview_from_profile(
        *,
        user_uuid: str,
        rating: float,
        rated_games: int,
        profile_version: int,
        settlement_seq: int,
        catalog_version: str,
        contract_version: int,
        active_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        opponent_level = pick_level(rating)
        opponent = SUPPORTED_CATALOGS[catalog_version].profile(opponent_level)
        projections = project_three(
            RatingState(rating, rated_games),
            opponent_level=opponent_level,
            time_control="unlimited",
            contract_version=contract_version,
        )
        canonical = {
            "schema": "xiangqi-ranked-preview-v1",
            "user_uuid": user_uuid,
            "profile_version": profile_version,
            "rating_hex": rating.hex(),
            "rated_games": rated_games,
            "scoring_contract_version": contract_version,
            "catalog_version": catalog_version,
            "opponent_profile_hash": opponent.profile_hash,
        }
        outcomes: dict[str, dict[str, Any]] = {}
        for outcome, change in projections.items():
            tier = str(tier_of(change.after.rating)["name"])
            canonical[f"outcome_{outcome}_hex"] = change.after.rating.hex()
            canonical[f"delta_{outcome}"] = change.display_delta
            canonical[f"tier_{outcome}"] = tier
            outcomes[outcome] = {
                "rating_hex": change.after.rating.hex(),
                "rating_display": change.display_after,
                "delta": change.display_delta,
                "tier": tier,
            }
        fingerprint = hash_preview(canonical)
        return {
            "code": "ready",
            "profile": {
                "rating_hex": rating.hex(),
                "rating_display": round(rating),
                "rated_games": rated_games,
                "profile_version": profile_version,
                "settlement_seq": settlement_seq,
            },
            "preview": {
                "projection_fingerprint": fingerprint,
                "scoring_contract_version": contract_version,
                "catalog_version": catalog_version,
                "opponent": {
                    "level": opponent.level,
                    "name": opponent.name,
                    "anchor": opponent.anchor,
                    "profile_hash": opponent.profile_hash,
                    "config": profile_public_config(opponent),
                },
                "outcomes": outcomes,
                "_canonical": canonical,
            },
            "_reservation": active_summary,
        }

    def preview(
        self,
        *,
        user_uuid: str,
        device_id: str,
        catalog_version: str,
        supported_contract_versions: Iterable[int],
    ) -> dict[str, Any]:
        del device_id  # Device identity is required by the wire contract, not by rating selection.
        fresh = self._compute_preview(
            user_uuid=user_uuid,
            catalog_version=catalog_version,
            supported_contract_versions=supported_contract_versions,
            reject_barrier=True,
        )
        return self._public_preview(fresh)

    @staticmethod
    def _snapshot_from_preview(
        fresh: Mapping[str, Any], *, user_uuid: str, time_control: str, player_color: str
    ) -> dict[str, Any]:
        profile = fresh["profile"]
        preview = fresh["preview"]
        canonical = preview["_canonical"]
        opponent = preview["opponent"]
        snapshot = {
            "schema": "xiangqi-ranked-reservation-v1",
            "user_uuid": user_uuid,
            "profile_version": profile["profile_version"],
            "rating_hex": profile["rating_hex"],
            "rated_games": profile["rated_games"],
            "settlement_seq": profile["settlement_seq"],
            "tier": str(tier_of(float.fromhex(profile["rating_hex"]))["name"]),
            "scoring_contract_version": preview["scoring_contract_version"],
            "catalog_version": preview["catalog_version"],
            "opponent_level": opponent["level"],
            "opponent_name": opponent["name"],
            "opponent_anchor": opponent["anchor"],
            "opponent_profile_hash": opponent["profile_hash"],
            "opponent_config": deepcopy(opponent["config"]),
            "time_control": time_control,
            "player_color": player_color,
            "projection_fingerprint": preview["projection_fingerprint"],
        }
        for outcome in ("win", "draw", "loss"):
            snapshot[f"outcome_{outcome}_hex"] = canonical[f"outcome_{outcome}_hex"]
            snapshot[f"delta_{outcome}"] = canonical[f"delta_{outcome}"]
            snapshot[f"tier_{outcome}"] = canonical[f"tier_{outcome}"]
        canonical_json(snapshot)
        return snapshot

    @staticmethod
    def _stale(fresh: Mapping[str, Any]) -> RankedServiceError:
        return RankedServiceError(
            409,
            "stale_projection",
            "The ranked projection changed; refresh and confirm the new values.",
            profile=_plain(fresh["profile"]),
            preview=XiangqiRankedService._public_preview(fresh)["preview"],
        )

    def reserve(
        self,
        *,
        user_uuid: str,
        game_id: str,
        device_id: str,
        expected_profile_version: int,
        projection_fingerprint: str,
        scoring_contract_version: int,
        catalog_version: str,
        opponent_profile_hash: str,
        time_control: str,
    ) -> dict[str, Any]:
        if time_control not in TIME_CONTROLS:
            raise RankedServiceError(422, "invalid_time_control", "Unsupported ranked time control.")
        catalog_version, negotiated_contract = self._negotiate(catalog_version, [scoring_contract_version])
        reservation_id = self.id_factory()
        now = _utc(self.now())
        capability = self.capabilities.codec.issue(
            user_uuid=user_uuid,
            device_id=device_id,
            game_id=game_id,
            reservation_id=reservation_id,
            now=now,
        )
        capability_claims = self.capabilities.codec.verify(capability)
        locked_result: dict[str, Any] = {}

        def proposal_factory(profile) -> XiangqiRankedReservationDraft:
            fresh = self._build_preview_from_profile(
                user_uuid=user_uuid,
                rating=float(profile.rating),
                rated_games=profile.rated_games,
                profile_version=profile.profile_version,
                settlement_seq=profile.settlement_seq,
                catalog_version=catalog_version,
                contract_version=negotiated_contract,
            )
            preview = fresh["preview"]
            expected = {
                "expected_profile_version": fresh["profile"]["profile_version"],
                "projection_fingerprint": preview["projection_fingerprint"],
                "scoring_contract_version": preview["scoring_contract_version"],
                "catalog_version": preview["catalog_version"],
                "opponent_profile_hash": preview["opponent"]["profile_hash"],
            }
            supplied = {
                "expected_profile_version": expected_profile_version,
                "projection_fingerprint": projection_fingerprint,
                "scoring_contract_version": scoring_contract_version,
                "catalog_version": catalog_version,
                "opponent_profile_hash": opponent_profile_hash,
            }
            if supplied != expected:
                raise self._stale(fresh)
            player_color = self.color_chooser(("red", "black"))
            if player_color not in {"red", "black"}:
                raise RuntimeError("color chooser returned an invalid Xiangqi color")
            snapshot = self._snapshot_from_preview(
                fresh,
                user_uuid=user_uuid,
                time_control=time_control,
                player_color=player_color,
            )
            locked_result["player_color"] = player_color
            return XiangqiRankedReservationDraft(
                expected_profile_version=profile.profile_version,
                projection_fingerprint=preview["projection_fingerprint"],
                frozen_snapshot=snapshot,
            )

        try:
            record = self.repository.create_reservation_locked(
                user_uuid=user_uuid,
                reservation_id=reservation_id,
                game_id=game_id,
                device_id=device_id,
                capability_jti=capability_claims.jti,
                proposal_factory=proposal_factory,
                now=now,
            )
        except ReservationConflict:
            current = self.current(user_uuid=user_uuid)
            raise RankedServiceError(
                409,
                "ranked_reserved_elsewhere",
                "This account already has an active Xiangqi ranked reservation.",
                reservation=None if current is None else current["reservation"],
            ) from None
        return {
            "code": "reserved",
            "reservation_id": record.reservation_id,
            "game_id": record.game_id,
            "player_color": locked_result["player_color"],
            "frozen_preview": _plain(record.frozen_snapshot),
            "terminal_capability": capability,
        }

    def current(self, *, user_uuid: str) -> dict[str, Any] | None:
        session = self.session_factory()
        try:
            row = self._active_reservation(session, user_uuid)
            if row is None:
                return None
            reservation = self._reservation_summary(row)
            reservation.update(
                {
                    "expected_profile_version": row.expected_profile_version,
                    "projection_fingerprint": row.projection_fingerprint,
                    "frozen_preview": deepcopy(dict(row.frozen_snapshot)),
                    "materialized_at": _iso(row.materialized_at),
                    "force_resign_threshold_version": FORCE_RESIGN_THRESHOLD_VERSION,
                    "can_force_resign": _utc(self.now()) - _utc(row.last_heartbeat_at) >= self.force_resign_threshold,
                }
            )
            return {"code": "current", "reservation": reservation}
        finally:
            session.close()

    def rotate(self, *, user_uuid: str, reservation_id: str, game_id: str) -> dict[str, Any]:
        try:
            capability = self.capabilities.rotate(
                user_uuid=user_uuid,
                reservation_id=reservation_id,
                game_id=game_id,
                now=_utc(self.now()),
            )
        except TerminalCapabilityError:
            raise RankedServiceError(409, "reservation_not_rotatable", "The reservation cannot be rotated.") from None
        return {"code": "capability_rotated", "terminal_capability": capability}

    def heartbeat(self, *, reservation_id: str, terminal_capability: str) -> dict[str, Any]:
        try:
            claims = self.capabilities.verify(
                terminal_capability,
                expected_reservation_id=reservation_id,
                required_action="heartbeat",
            )
            record = self.repository.heartbeat(
                user_uuid=claims.user_uuid,
                reservation_id=claims.reservation_id,
                device_id=claims.device_id,
                now=_utc(self.now()),
            )
        except (TerminalCapabilityError, ReservationConflict):
            raise RankedServiceError(401, "invalid_terminal_capability", "Invalid terminal capability.") from None
        return {"code": "heartbeat_recorded", "last_heartbeat_at": _iso(record.last_heartbeat_at)}

    def force_resign(self, *, user_uuid: str, reservation_id: str, confirm: bool) -> dict[str, Any]:
        if confirm is not True:
            raise RankedServiceError(422, "confirmation_required", "Explicit confirmation is required.")
        session = self.session_factory()
        try:
            row = session.execute(
                select(models_db.XiangqiRankedReservation).where(
                    models_db.XiangqiRankedReservation.reservation_id == reservation_id,
                    models_db.XiangqiRankedReservation.user_uuid == user_uuid,
                    models_db.XiangqiRankedReservation.status == "reserved",
                )
            ).scalar_one_or_none()
            if row is None:
                raise RankedServiceError(409, "reservation_not_active", "No matching active reservation exists.")
            record = XiangqiRankedReservationRecord(
                reservation_id=row.reservation_id,
                game_id=row.game_id,
                user_uuid=row.user_uuid,
                device_id=row.device_id,
                status=row.status,
                expected_profile_version=row.expected_profile_version,
                projection_fingerprint=row.projection_fingerprint,
                frozen_snapshot=deepcopy(dict(row.frozen_snapshot)),
                last_heartbeat_at=row.last_heartbeat_at,
                created_at=row.created_at,
                materialized_at=row.materialized_at,
                terminal_at=row.terminal_at,
            )
        finally:
            session.close()
        now = _utc(self.now())
        if now - _utc(record.last_heartbeat_at) < self.force_resign_threshold:
            raise RankedServiceError(
                409,
                "heartbeat_threshold_not_reached",
                "The active device heartbeat is still within the takeover threshold.",
                threshold_version=FORCE_RESIGN_THRESHOLD_VERSION,
            )
        frozen = record.frozen_snapshot
        canonical_payload = {
            "payload_schema": "xiangqi-ranked-force-resign-v1",
            "event_kind": "resign",
            "result": "loss",
            "user_uuid": user_uuid,
            "device_id": record.device_id,
            "game_id": record.game_id,
            "reservation_id": record.reservation_id,
            "projection_fingerprint": record.projection_fingerprint,
            "scoring_contract_version": frozen["scoring_contract_version"],
            "catalog_version": frozen["catalog_version"],
            "opponent_profile_hash": frozen["opponent_profile_hash"],
            "time_control": frozen["time_control"],
            "player_color": frozen["player_color"],
            "threshold_version": FORCE_RESIGN_THRESHOLD_VERSION,
        }
        payload_hash = canonical_hash(canonical_payload)
        with self.session_factory() as session:
            last_local_seq = session.execute(
                select(func.max(models_db.XiangqiRankedLedger.local_seq)).where(
                    models_db.XiangqiRankedLedger.user_uuid == user_uuid,
                    models_db.XiangqiRankedLedger.device_id == record.device_id,
                )
            ).scalar_one()
        local_seq = 0 if last_local_seq is None else last_local_seq + 1
        try:
            receipt = self.repository.force_resign_after_threshold(
                user_uuid=user_uuid,
                reservation_id=record.reservation_id,
                game_id=record.game_id,
                now=now,
                stale_after=self.force_resign_threshold,
                local_seq=local_seq,
                payload_hash=payload_hash,
                canonical_payload=canonical_payload,
                rating_after=float.fromhex(frozen["outcome_loss_hex"]),
                rating_delta=frozen["delta_loss"],
                tier_before=frozen["tier"],
                tier_after=frozen["tier_loss"],
                receipt_id=self.id_factory(),
            )
        except ReservationConflict:
            raise RankedServiceError(
                409,
                "heartbeat_threshold_not_reached",
                "The active device heartbeat is still within the takeover threshold.",
                threshold_version=FORCE_RESIGN_THRESHOLD_VERSION,
            ) from None
        except (StaleProfile, TerminalConflict):
            raise RankedServiceError(
                409,
                "reservation_terminal_conflict",
                "Another terminal action already completed this reservation.",
            ) from None
        return {"code": "resigned", "receipt": receipt}

    def void_unmaterialized(self, *, user_uuid: str, reservation_id: str, game_id: str) -> dict[str, Any]:
        try:
            voided = self.repository.void_unmaterialized(
                user_uuid=user_uuid,
                reservation_id=reservation_id,
                game_id=game_id,
            )
        except ReservationConflict:
            raise RankedServiceError(409, "reservation_not_voidable", "The reservation cannot be voided.") from None
        return {"code": "voided", "voided": voided}
