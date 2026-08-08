"""Narrow, revocable credentials for one Xiangqi ranked reservation."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from katrain.web.core import models_db


TERMINAL_AUDIENCE = "xiangqi-ranked-terminal"
TERMINAL_ACTIONS = frozenset({"settle", "resign", "system_abort", "heartbeat", "receipt"})
_REQUIRED_CLAIMS = frozenset(
    {
        "aud",
        "type",
        "user_uuid",
        "device_id",
        "game_id",
        "reservation_id",
        "jti",
        "actions",
        "iat",
        "exp",
    }
)


class TerminalCapabilityError(ValueError):
    """A deliberately opaque capability validation failure."""


def _invalid() -> TerminalCapabilityError:
    return TerminalCapabilityError("invalid terminal capability")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class TerminalCapabilityClaims:
    user_uuid: str
    device_id: str
    game_id: str
    reservation_id: str
    jti: str
    actions: frozenset[str]
    issued_at: datetime
    expires_at: datetime


class TerminalCapabilityCodec:
    """Sign and validate the distinct terminal JWT namespace."""

    def __init__(
        self,
        *,
        secret: str,
        algorithm: str,
        ttl: timedelta = timedelta(hours=24),
        now: Callable[[], datetime] | None = None,
        jti_factory: Callable[[], str] | None = None,
    ):
        self.secret = secret
        self.algorithm = algorithm
        self.ttl = ttl
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.jti_factory = jti_factory or (lambda: secrets.token_urlsafe(32))

    def issue(
        self,
        *,
        user_uuid: str,
        device_id: str,
        game_id: str,
        reservation_id: str,
        now: datetime | None = None,
    ) -> str:
        issued_at = _utc(now or self.now())
        expires_at = issued_at + self.ttl
        payload = {
            "aud": TERMINAL_AUDIENCE,
            "type": "terminal",
            "user_uuid": user_uuid,
            "device_id": device_id,
            "game_id": game_id,
            "reservation_id": reservation_id,
            "jti": self.jti_factory(),
            "actions": sorted(TERMINAL_ACTIONS),
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify(
        self,
        token: str,
        *,
        expected_user_uuid: str | None = None,
        expected_device_id: str | None = None,
        expected_game_id: str | None = None,
        expected_reservation_id: str | None = None,
        required_action: str | None = None,
    ) -> TerminalCapabilityClaims:
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                audience=TERMINAL_AUDIENCE,
                options={"verify_exp": False, "verify_iat": False},
            )
            if frozenset(payload) != _REQUIRED_CLAIMS or payload["type"] != "terminal":
                raise _invalid()
            actions = payload["actions"]
            if (
                not isinstance(actions, list)
                or frozenset(actions) != TERMINAL_ACTIONS
                or len(actions) != len(TERMINAL_ACTIONS)
            ):
                raise _invalid()
            for field in ("user_uuid", "device_id", "game_id", "reservation_id", "jti"):
                if not isinstance(payload[field], str) or not payload[field]:
                    raise _invalid()
            if isinstance(payload["iat"], bool) or not isinstance(payload["iat"], int):
                raise _invalid()
            if isinstance(payload["exp"], bool) or not isinstance(payload["exp"], int):
                raise _invalid()
            issued_at = datetime.fromtimestamp(payload["iat"], timezone.utc)
            expires_at = datetime.fromtimestamp(payload["exp"], timezone.utc)
            current = _utc(self.now())
            if issued_at > current or expires_at <= current or expires_at <= issued_at:
                raise _invalid()
            expected = {
                "user_uuid": expected_user_uuid,
                "device_id": expected_device_id,
                "game_id": expected_game_id,
                "reservation_id": expected_reservation_id,
            }
            if any(value is not None and payload[field] != value for field, value in expected.items()):
                raise _invalid()
            if required_action is not None and required_action not in TERMINAL_ACTIONS:
                raise _invalid()
            return TerminalCapabilityClaims(
                user_uuid=payload["user_uuid"],
                device_id=payload["device_id"],
                game_id=payload["game_id"],
                reservation_id=payload["reservation_id"],
                jti=payload["jti"],
                actions=frozenset(actions),
                issued_at=issued_at,
                expires_at=expires_at,
            )
        except (JWTError, KeyError, TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, TerminalCapabilityError):
                raise
            raise _invalid() from None


class TerminalCapabilityStore:
    """Persist capability currentness and rotate it under the reservation lock."""

    def __init__(self, session_factory, codec: TerminalCapabilityCodec):
        self.session_factory = session_factory
        self.codec = codec

    @staticmethod
    def _begin_write(session) -> None:
        if session.get_bind().dialect.name == "sqlite":
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    def issue(
        self,
        *,
        user_uuid: str,
        device_id: str,
        game_id: str,
        reservation_id: str,
        now: datetime,
    ) -> str:
        token = self.codec.issue(
            user_uuid=user_uuid,
            device_id=device_id,
            game_id=game_id,
            reservation_id=reservation_id,
            now=now,
        )
        claims = self.codec.verify(token)
        session = self.session_factory()
        try:
            self._begin_write(session)
            reservation = session.execute(
                select(models_db.XiangqiRankedReservation)
                .where(models_db.XiangqiRankedReservation.reservation_id == reservation_id)
                .with_for_update()
            ).scalar_one_or_none()
            if (
                reservation is None
                or reservation.status != "reserved"
                or reservation.user_uuid != user_uuid
                or reservation.device_id != device_id
                or reservation.game_id != game_id
            ):
                raise _invalid()
            session.add(
                models_db.XiangqiRankedCapabilityJti(
                    jti=claims.jti,
                    reservation_id=reservation_id,
                    issued_at=now,
                    revoked_at=None,
                )
            )
            session.commit()
            return token
        except (IntegrityError, TerminalCapabilityError):
            session.rollback()
            raise _invalid() from None
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def verify(self, token: str, *, required_action: str, **expected) -> TerminalCapabilityClaims:
        claims = self.codec.verify(token, required_action=required_action, **expected)
        session = self.session_factory()
        try:
            row = session.get(models_db.XiangqiRankedCapabilityJti, claims.jti)
            if row is None or row.revoked_at is not None or row.reservation_id != claims.reservation_id:
                raise _invalid()
            return claims
        finally:
            session.close()

    def rotate(
        self,
        *,
        user_uuid: str,
        reservation_id: str,
        game_id: str,
        now: datetime,
    ) -> str:
        session = self.session_factory()
        try:
            self._begin_write(session)
            reservation = session.execute(
                select(models_db.XiangqiRankedReservation)
                .where(models_db.XiangqiRankedReservation.reservation_id == reservation_id)
                .with_for_update()
            ).scalar_one_or_none()
            if (
                reservation is None
                or reservation.status != "reserved"
                or reservation.user_uuid != user_uuid
                or reservation.game_id != game_id
            ):
                raise _invalid()
            current = session.execute(
                select(models_db.XiangqiRankedCapabilityJti)
                .where(
                    models_db.XiangqiRankedCapabilityJti.reservation_id == reservation_id,
                    models_db.XiangqiRankedCapabilityJti.revoked_at.is_(None),
                )
                .with_for_update()
            ).scalar_one_or_none()
            if current is not None:
                current.revoked_at = now
            token = self.codec.issue(
                user_uuid=user_uuid,
                device_id=reservation.device_id,
                game_id=game_id,
                reservation_id=reservation_id,
                now=now,
            )
            claims = self.codec.verify(token)
            session.add(
                models_db.XiangqiRankedCapabilityJti(
                    jti=claims.jti,
                    reservation_id=reservation_id,
                    issued_at=now,
                    revoked_at=None,
                )
            )
            session.commit()
            return token
        except (IntegrityError, TerminalCapabilityError):
            session.rollback()
            raise _invalid() from None
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
