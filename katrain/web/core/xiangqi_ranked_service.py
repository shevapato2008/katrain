"""Cloud-authoritative preview and reservation orchestration for Xiangqi ranked play."""

from __future__ import annotations

import secrets
import uuid
import hashlib
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable, Iterable, Mapping

from jose import JWTError, jwt
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
from smartbox_xiangqi_ranked.canonical import canonical_event, hash_event, hash_preview
from smartbox_xiangqi_ranked.catalog import profile_public_config
from xiangqi_rules_core import Move, Position, legal_moves, terminal_status

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
START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
TIME_CONTROL_MS = {"blitz5": 300_000, "standard10": 600_000, "slow20": 1_200_000}
ENGINE_FAILURE_RETRY_LIMIT = 3
DEVICE_CURSOR_AUDIENCE = "xiangqi-ranked-device-reconcile"
HISTORY_CURSOR_AUDIENCE = "xiangqi-ranked-settlement-history"
CURSOR_TTL = timedelta(minutes=15)


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
        self._consumed_device_cursors: set[str] = set()
        self._cursor_lock = Lock()

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

    @staticmethod
    def _position_hash(position: Position) -> str:
        return hashlib.sha256(position.identity().encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_snapshot(payload: Mapping[str, Any], claims, reservation) -> Mapping[str, Any]:
        frozen = reservation.frozen_snapshot
        expected = {
            "user_uuid": claims.user_uuid,
            "device_id": claims.device_id,
            "game_id": claims.game_id,
            "reservation_id": claims.reservation_id,
            "projection_fingerprint": reservation.projection_fingerprint,
            "scoring_contract_version": frozen["scoring_contract_version"],
            "catalog_version": frozen["catalog_version"],
            "opponent_profile_hash": frozen["opponent_profile_hash"],
            "time_control": frozen["time_control"],
        }
        if any(payload.get(field) != value for field, value in expected.items()):
            raise RankedServiceError(
                422, "invalid_snapshot", "Terminal evidence does not match the frozen reservation."
            )
        if payload["event_kind"] != "system_abort" and payload.get("player_color") != frozen["player_color"]:
            raise RankedServiceError(
                422, "invalid_snapshot", "Terminal evidence does not match the frozen reservation."
            )
        return frozen

    @classmethod
    def _replay_terminal(cls, payload: Mapping[str, Any]) -> str:
        if payload["clock_revision"] != len(payload["moves"]):
            raise ValueError("clock revision is discontinuous")
        clock_limit = TIME_CONTROL_MS.get(payload["time_control"])
        if clock_limit is None:
            if payload["time_control"] == "unlimited" and payload["player_clock_ms"] != 0:
                raise ValueError("unlimited games use a zero clock value")
        elif payload["player_clock_ms"] > clock_limit:
            raise ValueError("remaining clock exceeds the frozen time control")

        position = Position.from_fen(START_FEN)
        repetitions = {position.identity(): 1}
        for move_text in payload["moves"]:
            if (
                terminal_status(position) != "ongoing"
                or position.halfmove >= 120
                or repetitions[position.identity()] >= 3
            ):
                raise ValueError("moves continue after a terminal position")
            move = Move.from_iccs(move_text)
            if move not in legal_moves(position):
                raise ValueError("illegal move")
            position = position.apply(move)
            repetitions[position.identity()] = repetitions.get(position.identity(), 0) + 1

        if payload["final_fen"] != position.to_fen() or payload["final_position_hash"] != cls._position_hash(position):
            raise ValueError("final position does not match replay")
        kind = payload["terminal_kind"]
        if kind == "resign":
            if payload["event_kind"] != "resign" or payload["result"] != "loss":
                raise ValueError("resign must be a player loss")
            return "loss"
        if kind == "timeout":
            if payload["event_kind"] != "settle" or payload["player_clock_ms"] != 0 or payload["result"] != "loss":
                raise ValueError("timeout must be a player clock loss")
            return "loss"

        status = terminal_status(position)
        is_draw = position.halfmove >= 120 or repetitions.get(position.identity(), 0) >= 3
        if status == "ongoing" and not is_draw:
            raise ValueError("rules settlement is not terminal")
        expected_result = "draw" if is_draw else ("loss" if payload["player_color"] == position.side else "win")
        if payload["result"] != expected_result:
            raise ValueError("reported result does not match the replayed terminal")
        return expected_result

    @staticmethod
    def _validate_fault_evidence(payload: Mapping[str, Any]) -> str:
        evidence = payload["fault_evidence"]
        reason = evidence["fault_kind"]
        if reason == "engine_unavailable" and evidence["retry_count"] < ENGINE_FAILURE_RETRY_LIMIT:
            raise ValueError("engine retry limit was not reached")
        if reason == "system_fault" and evidence["retry_count"] < 1:
            raise ValueError("system fault lacks a server retry observation")
        return reason

    def settle(
        self, *, event_payload: Mapping[str, Any], payload_hash: str, terminal_capability: str
    ) -> dict[str, Any]:
        event_kind = event_payload.get("event_kind") if isinstance(event_payload, Mapping) else None
        if event_kind not in {"settle", "resign", "system_abort"}:
            raise RankedServiceError(422, "invalid_terminal_evidence", "Terminal evidence is invalid.")
        try:
            claims = self.capabilities.verify(terminal_capability, required_action=event_kind)
        except TerminalCapabilityError:
            raise RankedServiceError(401, "invalid_terminal_capability", "Invalid terminal capability.") from None
        try:
            canonical_event(event_payload)
            computed_hash = hash_event(event_payload)
        except (TypeError, ValueError):
            raise RankedServiceError(422, "invalid_terminal_evidence", "Terminal evidence is invalid.") from None
        if payload_hash != computed_hash:
            self.repository._record_terminal_conflict("payload_conflict")
            raise RankedServiceError(
                409, "payload_conflict", "The supplied payload hash does not match canonical evidence."
            )

        with self.session_factory() as session:
            reservation = session.execute(
                select(models_db.XiangqiRankedReservation).where(
                    models_db.XiangqiRankedReservation.reservation_id == claims.reservation_id
                )
            ).scalar_one_or_none()
            if reservation is None:
                raise RankedServiceError(409, "reservation_terminal_conflict", "The reservation is unavailable.")
            frozen = self._validate_snapshot(event_payload, claims, reservation)

        terminal_state = {
            "settle": "settled",
            "resign": "resigned",
            "system_abort": "system_aborted",
        }[event_kind]
        existing = self.repository.get_receipt(user_uuid=claims.user_uuid, game_id=claims.game_id)
        if existing is not None:
            if existing["status"] == terminal_state and existing["payload_hash"] == computed_hash:
                return {"code": "idempotent_replay", "receipt": existing}
            code = "reservation_terminal_conflict" if existing["status"] != terminal_state else "payload_conflict"
            self.repository._record_terminal_conflict(code)
            raise RankedServiceError(409, code, "Another immutable terminal fact already won this reservation.")
        try:
            if event_kind == "system_abort":
                reason = self._validate_fault_evidence(event_payload)
                result = None
                counted = False
                rating_after = None
                rating_delta = None
                tier_after = None
            else:
                result = self._replay_terminal(event_payload)
                counted = True
                reason = None
                rating_after = float.fromhex(frozen[f"outcome_{result}_hex"])
                rating_delta = frozen[f"delta_{result}"]
                tier_after = frozen[f"tier_{result}"]
        except (KeyError, TypeError, ValueError):
            raise RankedServiceError(422, "invalid_terminal_evidence", "Terminal evidence is invalid.") from None

        try:
            receipt = self.repository.settle_terminal(
                user_uuid=claims.user_uuid,
                reservation_id=claims.reservation_id,
                game_id=claims.game_id,
                device_id=claims.device_id,
                terminal_status=terminal_state,
                local_seq=event_payload["local_seq"],
                payload_hash=computed_hash,
                canonical_payload=event_payload,
                result=result,
                counted=counted,
                reason=reason,
                rating_after=rating_after,
                rating_delta=rating_delta,
                tier_before=frozen["tier"],
                tier_after=tier_after,
                receipt_id=self.id_factory(),
                now=_utc(self.now()),
            )
        except TerminalConflict:
            original = self.repository.get_receipt(user_uuid=claims.user_uuid, game_id=claims.game_id)
            code = (
                "reservation_terminal_conflict"
                if original and original["status"] != terminal_state
                else "payload_conflict"
            )
            raise RankedServiceError(
                409, code, "Another immutable terminal fact already won this reservation."
            ) from None
        except (ReservationConflict, StaleProfile):
            raise RankedServiceError(
                409, "reservation_terminal_conflict", "Another immutable terminal fact already won this reservation."
            ) from None
        return {"code": "confirmed", "receipt": receipt}

    def health_metrics(self) -> dict[str, Any]:
        return self.repository.health_metrics(now=_utc(self.now()))

    def _profile_snapshot(self, user_uuid: str) -> dict[str, Any]:
        now = _utc(self.now())
        session = self.session_factory()
        try:
            self.repository._begin_write_transaction(session)
            profile = self.repository.get_or_create_profile_for_update(session, user_uuid, now=now)
            result = {
                "rating_hex": float(profile.rating).hex(),
                "rating_display": round(float(profile.rating)),
                "rated_games": profile.rated_games,
                "profile_version": profile.profile_version,
                "active_algo_version": profile.active_algo_version,
                "settlement_seq": profile.settlement_seq,
            }
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _issue_cursor(self, audience: str, cursor_type: str, **claims: Any) -> str:
        now = _utc(self.now())
        payload = {
            "aud": audience,
            "type": cursor_type,
            "nonce": secrets.token_urlsafe(16),
            "iat": int(now.timestamp()),
            "exp": int((now + CURSOR_TTL).timestamp()),
            **claims,
        }
        return jwt.encode(payload, self.capabilities.codec.secret, algorithm=self.capabilities.codec.algorithm)

    def _verify_cursor(self, token: str, audience: str, cursor_type: str) -> Mapping[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.capabilities.codec.secret,
                algorithms=[self.capabilities.codec.algorithm],
                audience=audience,
                options={"verify_exp": False, "verify_iat": False},
            )
            if payload.get("type") != cursor_type:
                raise ValueError("wrong cursor type")
            current = int(_utc(self.now()).timestamp())
            if (
                isinstance(payload.get("iat"), bool)
                or not isinstance(payload.get("iat"), int)
                or isinstance(payload.get("exp"), bool)
                or not isinstance(payload.get("exp"), int)
                or payload["iat"] > current
                or payload["exp"] <= current
            ):
                raise ValueError("expired cursor")
            return payload
        except (JWTError, TypeError, ValueError):
            raise RankedServiceError(409, "invalid_cursor", "The ranked pagination cursor is invalid.") from None

    def receipt(
        self,
        *,
        game_id: str,
        user_uuid: str | None,
        terminal_capability: str | None,
        payload_hash: str | None = None,
    ) -> dict[str, Any]:
        if user_uuid is None:
            if terminal_capability is None:
                raise RankedServiceError(401, "ranked_login_required", "Ranked authentication is required.")
            try:
                claims = self.capabilities.verify(
                    terminal_capability,
                    expected_game_id=game_id,
                    required_action="receipt",
                )
            except TerminalCapabilityError:
                raise RankedServiceError(401, "invalid_terminal_capability", "Invalid terminal capability.") from None
            user_uuid = claims.user_uuid

        with self.session_factory() as session:
            reservation = session.execute(
                select(models_db.XiangqiRankedReservation).where(
                    models_db.XiangqiRankedReservation.game_id == game_id,
                    models_db.XiangqiRankedReservation.user_uuid == user_uuid,
                )
            ).scalar_one_or_none()
        if reservation is None:
            raise RankedServiceError(404, "not_found", "The ranked game was not found.")
        original = self.repository.get_receipt(user_uuid=user_uuid, game_id=game_id)
        if original is None:
            return {"code": "missing", "game_id": game_id, "payload_hash": None, "receipt": None}
        original_hash = original.get("payload_hash")
        if payload_hash is not None and payload_hash != original_hash:
            return {"code": "conflict", "game_id": game_id, "payload_hash": original_hash, "receipt": original}
        status = {"settled": "confirmed"}.get(str(original.get("status")), str(original.get("status")))
        if status not in {"accepted", "confirmed", "resigned", "system_aborted", "conflict"}:
            status = "conflict"
        return {"code": status, "game_id": game_id, "payload_hash": original_hash, "receipt": original}

    def reconcile(
        self,
        *,
        user_uuid: str,
        device_id: str,
        known_profile_version: int,
        known_settlement_seq: int,
        through_local_seq: int,
        device_cursor: int | None,
        event_snapshot_token: str | None,
        events: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        del known_profile_version, known_settlement_seq
        first_page = device_cursor is None and event_snapshot_token is None
        if (device_cursor is None) != (event_snapshot_token is None):
            raise RankedServiceError(
                409, "invalid_cursor", "The device cursor and snapshot token must advance together."
            )
        after = 0 if first_page else int(device_cursor)
        if not first_page:
            claims = self._verify_cursor(event_snapshot_token, DEVICE_CURSOR_AUDIENCE, "device_reconcile")
            expected = {
                "user_uuid": user_uuid,
                "device_id": device_id,
                "through_local_seq": through_local_seq,
                "cursor": after,
            }
            if any(claims.get(field) != value for field, value in expected.items()):
                raise RankedServiceError(409, "invalid_cursor", "The device cursor does not match this snapshot.")
        if through_local_seq < after:
            raise RankedServiceError(422, "invalid_event_page", "The reconcile upper bound precedes its cursor.")
        seqs = [int(event["local_seq"]) for event in events]
        if seqs != list(range(after + 1, after + 1 + len(seqs))):
            raise RankedServiceError(422, "invalid_event_page", "Device event local sequences must be continuous.")
        if seqs and seqs[-1] > through_local_seq:
            raise RankedServiceError(422, "invalid_event_page", "A device event exceeds the frozen upper bound.")
        next_cursor = seqs[-1] if seqs else after
        if next_cursor < through_local_seq and len(events) != 100:
            raise RankedServiceError(422, "invalid_event_page", "A non-final reconcile page must contain 100 events.")
        if not events and next_cursor != through_local_seq:
            raise RankedServiceError(422, "invalid_event_page", "The reconcile page omits frozen device events.")

        statuses = self.repository.statuses_for_device_events(
            user_uuid=user_uuid,
            device_id=device_id,
            events=[dict(event) for event in events],
        )
        if not first_page:
            cursor_digest = hashlib.sha256(event_snapshot_token.encode("utf-8")).hexdigest()
            with self._cursor_lock:
                if cursor_digest in self._consumed_device_cursors:
                    raise RankedServiceError(409, "cursor_replayed", "The device cursor page was already consumed.")
                self._consumed_device_cursors.add(cursor_digest)
        token = self._issue_cursor(
            DEVICE_CURSOR_AUDIENCE,
            "device_reconcile",
            user_uuid=user_uuid,
            device_id=device_id,
            through_local_seq=through_local_seq,
            cursor=next_cursor,
        )
        return {
            "code": "reconciled",
            "event_snapshot_token": token,
            "next_device_cursor": next_cursor,
            "has_more": next_cursor < through_local_seq,
            "event_statuses": statuses,
            "profile": self._profile_snapshot(user_uuid),
        }

    def history(
        self,
        *,
        user_uuid: str,
        after_seq: int,
        snapshot_seq: int | None,
        summary_cursor: str | None,
    ) -> dict[str, Any]:
        profile = self._profile_snapshot(user_uuid)
        if summary_cursor is None:
            if snapshot_seq is not None:
                raise RankedServiceError(409, "invalid_cursor", "A snapshot sequence requires its history cursor.")
            frozen_snapshot = profile["settlement_seq"]
            cursor = after_seq
        else:
            if snapshot_seq is None:
                raise RankedServiceError(409, "invalid_cursor", "The history cursor requires its snapshot sequence.")
            claims = self._verify_cursor(summary_cursor, HISTORY_CURSOR_AUDIENCE, "settlement_history")
            expected = {"user_uuid": user_uuid, "snapshot_seq": snapshot_seq, "after_seq": after_seq}
            if any(claims.get(field) != value for field, value in expected.items()):
                raise RankedServiceError(409, "invalid_cursor", "The history cursor does not match this snapshot.")
            frozen_snapshot = snapshot_seq
            cursor = claims.get("cursor")
            if isinstance(cursor, bool) or not isinstance(cursor, int):
                raise RankedServiceError(409, "invalid_cursor", "The history cursor is invalid.")
        if after_seq > frozen_snapshot or cursor < after_seq or cursor > frozen_snapshot:
            raise RankedServiceError(422, "invalid_history_range", "The settlement history range is invalid.")
        page = self.repository.page_settlement_summaries(
            user_uuid=user_uuid,
            after_seq=cursor,
            snapshot_seq=frozen_snapshot,
            limit=100,
        )
        next_cursor = self._issue_cursor(
            HISTORY_CURSOR_AUDIENCE,
            "settlement_history",
            user_uuid=user_uuid,
            snapshot_seq=frozen_snapshot,
            after_seq=after_seq,
            cursor=page["next_cursor"],
        )
        return {
            "code": "history",
            "snapshot_seq": frozen_snapshot,
            "next_summary_cursor": next_cursor,
            "has_more": page["has_more"],
            "summaries": page["items"],
            "profile": profile,
        }
