"""Private phone authentication and transactional, persistent SMS budgets."""

import hashlib
import hmac
import ipaddress
import math
import re
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from . import billing, models_db, sms
from .auth import get_password_hash
from .config import INSECURE_DEFAULT_SECRET_KEY
from .phone import mask_phone, normalize_phone


_SHANGHAI = ZoneInfo("Asia/Shanghai")
_FLOW = re.compile(r"[A-Za-z0-9_-]{22,128}\Z", re.ASCII)
_CHALLENGE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)
_CODE = re.compile(r"[0-9]{6}\Z", re.ASCII)
_TTL = 300
_COOLDOWN = 60
_ERROR_LIMIT = 5
_LOCK_SECONDS = 900
_SIGNUP_CREDITS = 5000


def _now():
    return datetime.now(timezone.utc)


def _utc(value):
    # SQLite drops timezone information; PostgreSQL preserves the UTC instant.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _retry_until(end, now):
    return max(1, math.ceil((_utc(end) - now).total_seconds()))


class PhoneOtpError(Exception):
    def __init__(self, code: str, status_code: int, retry_after: int | None = None):
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(code)


class PhoneOtpService:
    def __init__(self, session_factory, config, *, sender_factory=None):
        self.session_factory = session_factory
        self.config = config
        self.sender_factory = sender_factory or sms.sender_from_settings

    def _ensure_available(self):
        limit = getattr(self.config, "KATRAIN_SMS_DAILY_LIMIT", 0)
        cap = 50 if getattr(self.config, "KATRAIN_ENVIRONMENT", "production") == "production" else 10
        secret = getattr(self.config, "SECRET_KEY", "")
        if (
            getattr(self.config, "KATRAIN_SMS_ENABLED", False) is not True
            or type(limit) is not int
            or not 1 <= limit <= cap
            or not isinstance(secret, str)
            or len(secret.strip()) < 32
            or secret == INSECURE_DEFAULT_SECRET_KEY
        ):
            raise PhoneOtpError("sms_unavailable", 503)

    def _flow_digest(self, flow_id):
        if not isinstance(flow_id, str) or not _FLOW.fullmatch(flow_id):
            raise PhoneOtpError("challenge_invalid", 400)
        return hashlib.sha256(flow_id.encode("ascii")).hexdigest()

    def _code_digest(self, challenge_id, purpose, phone, flow_digest, code):
        message = "\0".join(("katrain-phone-otp-v1", challenge_id, purpose, phone, flow_digest, code))
        return hmac.new(self.config.SECRET_KEY.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _upsert(db, model, values):
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise PhoneOtpError("sms_unavailable", 503)
        db.execute(insert(model).values(**values).on_conflict_do_nothing())

    def _lock_phone(self, db, phone):
        # INSERT ON CONFLICT waits for a concurrent first insert before we take
        # the row lock; no count-then-insert hole on a previously unseen phone.
        self._upsert(db, models_db.SmsPhoneState, {"phone_e164": phone, "error_count": 0})
        return db.execute(
            select(models_db.SmsPhoneState).where(models_db.SmsPhoneState.phone_e164 == phone).with_for_update()
        ).scalar_one()

    @staticmethod
    def _check_lock(state, now):
        if state.blocked_until is None:
            return
        if _utc(state.blocked_until) > now:
            raise PhoneOtpError("otp_locked", 429, _retry_until(state.blocked_until, now))
        # Resending/success does not clear failed attempts; only lock expiry can.
        state.error_count = 0
        state.blocked_until = None

    @staticmethod
    def _bind_actor(db, actor_id):
        user = db.get(models_db.User, actor_id) if type(actor_id) is int else None
        username = (user.username if user else "").strip().lower()
        if (
            user is None
            or user.is_admin
            or username in {"guest", "admin"}
            or username.startswith("admin:")
            or not user.hashed_password.startswith(("$2a$", "$2b$", "$2y$"))
        ):
            raise PhoneOtpError("bind_not_allowed", 403)
        if (
            db.execute(
                select(models_db.PhoneIdentity).where(models_db.PhoneIdentity.user_id == actor_id)
            ).scalar_one_or_none()
            is not None
        ):
            raise PhoneOtpError("phone_in_use", 409)
        return user

    def _reserve_bucket(self, db, *, kind, key, start, end, limit, now):
        values = {"kind": kind, "key": key, "window_start": start, "count": 0}
        self._upsert(db, models_db.SmsSendBucket, values)
        result = db.execute(
            update(models_db.SmsSendBucket)
            .where(
                models_db.SmsSendBucket.kind == kind,
                models_db.SmsSendBucket.key == key,
                models_db.SmsSendBucket.window_start == start,
                models_db.SmsSendBucket.count < limit,
            )
            .values(count=models_db.SmsSendBucket.count + 1)
        )
        if result.rowcount != 1:
            raise PhoneOtpError("sms_limited", 429, _retry_until(end, now))

    async def request_challenge(self, *, phone, purpose, flow_id, client_ip, actor_id=None):
        try:
            normalized = normalize_phone(phone)
        except (ValueError, TypeError):
            raise PhoneOtpError("invalid_phone", 400) from None
        flow_digest = self._flow_digest(flow_id)
        if purpose not in {"login", "bind"} or (purpose == "login" and actor_id is not None):
            raise PhoneOtpError("challenge_invalid", 400)
        try:
            peer = str(ipaddress.ip_address(client_ip))
        except (ValueError, TypeError):
            raise PhoneOtpError("sms_unavailable", 503) from None
        self._ensure_available()
        try:
            sender = self.sender_factory(self.config)
        except sms.SmsUnavailable:
            raise PhoneOtpError("sms_unavailable", 503) from None

        now = _now()
        day = now.astimezone(_SHANGHAI).replace(hour=0, minute=0, second=0, microsecond=0)
        day_start, day_end = day.astimezone(timezone.utc), (day + timedelta(days=1)).astimezone(timezone.utc)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        challenge_id = secrets.token_hex(24)
        code = f"{secrets.randbelow(1_000_000):06d}"
        with self.session_factory() as db, db.begin():
            state = self._lock_phone(db, normalized)
            self._check_lock(state, now)
            if purpose == "bind":
                self._bind_actor(db, actor_id)
            if state.last_send_at and (_utc(state.last_send_at) + timedelta(seconds=_COOLDOWN)) > now:
                raise PhoneOtpError(
                    "sms_limited", 429, _retry_until(_utc(state.last_send_at) + timedelta(seconds=_COOLDOWN), now)
                )
            # Global lock order: phone state -> phone/day -> peer/hour -> global/day.
            self._reserve_bucket(db, kind="phone_day", key=normalized, start=day_start, end=day_end, limit=5, now=now)
            self._reserve_bucket(
                db, kind="ip_hour", key=peer, start=hour_start, end=hour_start + timedelta(hours=1), limit=20, now=now
            )
            self._reserve_bucket(
                db,
                kind="global_day",
                key="all",
                start=day_start,
                end=day_end,
                limit=self.config.KATRAIN_SMS_DAILY_LIMIT,
                now=now,
            )
            if state.active_challenge_id:
                db.execute(
                    update(models_db.SmsChallenge)
                    .where(
                        models_db.SmsChallenge.id == state.active_challenge_id,
                        models_db.SmsChallenge.state.in_(("pending", "sent", "unknown")),
                    )
                    .values(state="superseded")
                )
            db.add(
                models_db.SmsChallenge(
                    id=challenge_id,
                    phone_e164=normalized,
                    purpose=purpose,
                    flow_digest=flow_digest,
                    bind_user_id=actor_id if purpose == "bind" else None,
                    code_digest=self._code_digest(challenge_id, purpose, normalized, flow_digest, code),
                    expires_at=now + timedelta(seconds=_TTL),
                    state="pending",
                )
            )
            state.last_send_at = now
            state.active_challenge_id = challenge_id

        # Deliberately outside every DB transaction. Every outcome spends the
        # reservation, including rejection, unknown delivery or process death.
        delivery = "sent"
        try:
            await sender.send(normalized, code)
        except sms.SmsRejected:
            delivery = "rejected"
        except sms.SmsUnknown:
            delivery = "unknown"
        except sms.SmsUnavailable:
            delivery = "rejected"
        with self.session_factory() as db, db.begin():
            db.execute(
                update(models_db.SmsChallenge)
                .where(models_db.SmsChallenge.id == challenge_id, models_db.SmsChallenge.state == "pending")
                .values(state=delivery)
            )
        if delivery == "rejected":
            raise PhoneOtpError("sms_rejected", 503)
        return {"challenge_id": challenge_id, "retry_after": _COOLDOWN, "expires_in": _TTL, "delivery": delivery}

    def _locked_login_challenge(self, db, challenge_id, flow_digest, now):
        if not isinstance(challenge_id, str) or not _CHALLENGE_ID.fullmatch(challenge_id):
            raise PhoneOtpError("challenge_invalid", 400)
        phone = db.execute(
            select(models_db.SmsChallenge.phone_e164).where(models_db.SmsChallenge.id == challenge_id)
        ).scalar_one_or_none()
        if phone is None:
            raise PhoneOtpError("challenge_invalid", 400)
        state = self._lock_phone(db, phone)
        self._check_lock(state, now)
        challenge = db.execute(
            select(models_db.SmsChallenge).where(models_db.SmsChallenge.id == challenge_id).with_for_update()
        ).scalar_one()
        if challenge.state == "consumed":
            raise PhoneOtpError("challenge_used", 400)
        if _utc(challenge.expires_at) <= now:
            raise PhoneOtpError("challenge_expired", 400)
        if (
            state.active_challenge_id != challenge.id
            or challenge.state not in {"sent", "unknown"}
            or challenge.purpose != "login"
            or challenge.bind_user_id is not None
            or not hmac.compare_digest(challenge.flow_digest, flow_digest)
        ):
            raise PhoneOtpError("challenge_invalid", 400)
        return state, challenge

    @staticmethod
    def _public_user(user):
        return {
            name: getattr(user, name)
            for name in (
                "id",
                "uuid",
                "username",
                "rank",
                "net_wins",
                "elo_points",
                "credits",
                "is_admin",
                "avatar_url",
                "created_at",
            )
        }

    def _create_user(self, db):
        password_hash = get_password_hash(secrets.token_urlsafe(48))
        for _ in range(5):
            try:
                with db.begin_nested():
                    user = models_db.User(
                        username="u_" + secrets.token_hex(10), hashed_password=password_hash, credits=0, is_admin=False
                    )
                    db.add(user)
                    db.flush()
                return user
            except IntegrityError:
                # Only generated handle collision is retryable. No caller input
                # can select a guest/admin identity or visible OTP password.
                continue
        raise PhoneOtpError("sms_unavailable", 503)

    def login(self, *, challenge_id, code, flow_id):
        self._ensure_available()
        flow_digest = self._flow_digest(flow_id)
        now = _now()
        error = None
        result = None
        with self.session_factory() as db:
            with db.begin():
                state, challenge = self._locked_login_challenge(db, challenge_id, flow_digest, now)
                candidate = code if isinstance(code, str) and _CODE.fullmatch(code) else ""
                digest = self._code_digest(
                    challenge.id, challenge.purpose, challenge.phone_e164, flow_digest, candidate
                )
                if not hmac.compare_digest(challenge.code_digest, digest):
                    state.error_count += 1
                    if state.error_count >= _ERROR_LIMIT:
                        state.blocked_until = now + timedelta(seconds=_LOCK_SECONDS)
                        error = PhoneOtpError("otp_locked", 429, _LOCK_SECONDS)
                    else:
                        error = PhoneOtpError("invalid_code", 400)
                else:
                    challenge.state = "consumed"
                    challenge.consumed_at = now
                    identity = db.execute(
                        select(models_db.PhoneIdentity).where(
                            models_db.PhoneIdentity.phone_e164 == challenge.phone_e164
                        )
                    ).scalar_one_or_none()
                    if identity is not None:
                        user = db.get(models_db.User, identity.user_id)
                        if user is None:
                            raise PhoneOtpError("sms_unavailable", 503)
                    else:
                        user = self._create_user(db)
                        db.add(
                            models_db.PhoneIdentity(phone_e164=challenge.phone_e164, user_id=user.id, verified_at=now)
                        )
                        claim = db.get(models_db.PhoneSignupClaim, challenge.phone_e164)
                        if claim is None:
                            grant_ref = "phone_signup:" + secrets.token_hex(24)
                            db.add(
                                models_db.PhoneSignupClaim(
                                    phone_e164=challenge.phone_e164,
                                    claim_type="signup_grant",
                                    user_id=user.id,
                                    grant_ref=grant_ref,
                                )
                            )
                            db.flush()
                            billing.apply_adjustment(db, user.id, _SIGNUP_CREDITS, "signup_grant", grant_ref)
                        db.flush()
                    db.refresh(user)
                    result = self._public_user(user)
            # The error is deliberately raised after committing the wrong-code
            # transaction, so an HTTP exception cannot erase the phone counter.
        if error:
            raise error
        return result

    def status(self, *, user_id):
        with self.session_factory() as db:
            phone = db.execute(
                select(models_db.PhoneIdentity.phone_e164).where(models_db.PhoneIdentity.user_id == user_id)
            ).scalar_one_or_none()
            return {"bound": True, "masked_phone": mask_phone(phone)} if phone else {"bound": False}
