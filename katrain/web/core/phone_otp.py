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
from .auth import get_password_hash, verify_password
from .config import INSECURE_DEFAULT_SECRET_KEY
from .phone import mask_phone, normalize_phone
from .public_identity import is_generated_phone_username, validate_public_username, validate_signup_password


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
    def __init__(self, code: str, status_code: int, retry_after: int | None = None, *, mode: str | None = None):
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after
        self.mode = mode
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
    def _bind_actor(db, actor_id, *, require_unbound=True):
        user = db.get(models_db.User, actor_id) if type(actor_id) is int else None
        username = (user.username if user else "").strip().lower()
        if (
            user is None
            or user.is_admin
            or username in {"guest", "admin"}
            or username.startswith("admin:")
            or user.hashed_password == "SHADOW_USER_NO_LOCAL_AUTH"
        ):
            raise PhoneOtpError("bind_not_allowed", 403)
        if require_unbound and (
            db.execute(
                select(models_db.PhoneIdentity).where(models_db.PhoneIdentity.user_id == actor_id)
            ).scalar_one_or_none()
            is not None
        ):
            raise PhoneOtpError("phone_in_use", 409)
        return user

    def _reserve_bucket(self, db, *, kind, key, start, end, limit, now, error_code="sms_limited"):
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
            raise PhoneOtpError(error_code, 429, _retry_until(end, now))

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

    def _locked_challenge(
        self, db, challenge_id, flow_digest, now, *, purpose="login", actor_id=None, allow_consumed=False
    ):
        if not isinstance(challenge_id, str) or not _CHALLENGE_ID.fullmatch(challenge_id):
            raise PhoneOtpError("challenge_invalid", 400)
        phone = db.execute(
            select(models_db.SmsChallenge.phone_e164).where(models_db.SmsChallenge.id == challenge_id)
        ).scalar_one_or_none()
        if phone is None:
            raise PhoneOtpError("challenge_invalid", 400)
        state = self._lock_phone(db, phone)
        self._check_lock(state, _now())
        challenge = db.execute(
            select(models_db.SmsChallenge).where(models_db.SmsChallenge.id == challenge_id).with_for_update()
        ).scalar_one()
        if challenge.state == "consumed" and not allow_consumed:
            raise PhoneOtpError("challenge_used", 400)
        # Acquiring another worker's lock can outlive the proof TTL.
        if _utc(challenge.expires_at) <= _now():
            raise PhoneOtpError("challenge_expired", 400)
        if (
            state.active_challenge_id != challenge.id
            or challenge.state not in ({"sent", "unknown", "consumed"} if allow_consumed else {"sent", "unknown"})
            or challenge.purpose != purpose
            or challenge.bind_user_id != actor_id
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
                "public_username",
                "rank",
                "net_wins",
                "elo_points",
                "credits",
                "is_admin",
                "avatar_url",
                "created_at",
            )
        }

    @staticmethod
    def _constraint(error):
        return getattr(getattr(error.orig, "diag", None), "constraint_name", None)

    @classmethod
    def _is_public_name_conflict(cls, error):
        return cls._constraint(error) == "uq_user_public_username" or (
            cls._constraint(error) is None and str(error.orig) == "UNIQUE constraint failed: users.public_username"
        )

    def _create_user(self, db, *, public_username, password_hash):
        for _ in range(5):
            try:
                with db.begin_nested():
                    user = models_db.User(
                        username="u_" + secrets.token_hex(10),
                        public_username=public_username,
                        hashed_password=password_hash,
                        credits=0,
                        is_admin=False,
                    )
                    db.add(user)
                    db.flush()
                return user
            except IntegrityError as error:
                # A name conflict is handled after the whole finalization rolls
                # back. Only our random internal handle collision is retryable.
                if self._constraint(error) not in {"ix_users_username", "users_username_key"} and not (
                    self._constraint(error) is None and str(error.orig) == "UNIQUE constraint failed: users.username"
                ):
                    raise
        raise PhoneOtpError("sms_unavailable", 503)

    def _proof_error(self, state, challenge, code, flow_digest, now):
        candidate = code if isinstance(code, str) and _CODE.fullmatch(code) else ""
        digest = self._code_digest(challenge.id, challenge.purpose, challenge.phone_e164, flow_digest, candidate)
        if hmac.compare_digest(challenge.code_digest, digest):
            return None
        state.error_count += 1
        if state.error_count >= _ERROR_LIMIT:
            state.blocked_until = now + timedelta(seconds=_LOCK_SECONDS)
            return PhoneOtpError("otp_locked", 429, _LOCK_SECONDS)
        return PhoneOtpError("invalid_code", 400)

    @staticmethod
    def _phone_user(db, phone):
        identity = db.execute(
            select(models_db.PhoneIdentity).where(models_db.PhoneIdentity.phone_e164 == phone)
        ).scalar_one_or_none()
        if identity is None:
            return None
        # Match binding's lock order: phone -> challenge -> user.
        user = db.execute(
            select(models_db.User).where(models_db.User.id == identity.user_id).with_for_update()
        ).scalar_one_or_none()
        if user is None:
            raise PhoneOtpError("sms_unavailable", 503)
        return user

    @staticmethod
    def _needs_completion(db, user, phone):
        if user.public_username is not None or user.is_admin or not is_generated_phone_username(user.username):
            return False
        claim = db.get(models_db.PhoneSignupClaim, phone)
        return not (claim is not None and claim.user_id == user.id and claim.claim_type == "bound_existing")

    def login(self, *, challenge_id, code, flow_id):
        self._ensure_available()
        flow_digest = self._flow_digest(flow_id)
        now = _now()
        result = None
        with self.session_factory() as db, db.begin():
            state, challenge = self._locked_challenge(db, challenge_id, flow_digest, now)
            error = self._proof_error(state, challenge, code, flow_digest, now)
            if error is None:
                user = self._phone_user(db, challenge.phone_e164)
                now = _now()
                if _utc(challenge.expires_at) <= now:
                    raise PhoneOtpError("challenge_expired", 400)
                if user is None or self._needs_completion(db, user, challenge.phone_e164):
                    error = PhoneOtpError("profile_required", 409, mode="register" if user is None else "complete")
                else:
                    challenge.state = "consumed"
                    challenge.consumed_at = now
                    result = self._public_user(user)
        # Wrong-code counters commit even when the caller receives an error.
        if error:
            raise error
        return result

    def register(self, *, challenge_id, code, flow_id, public_username, password):
        self._ensure_available()
        try:
            validate_public_username(public_username)
        except (ValueError, TypeError, AttributeError):
            folded = public_username.casefold() if isinstance(public_username, str) else ""
            reserved = folded in {"guest", "admin"} or folded.startswith(("admin:", "u_"))
            raise PhoneOtpError("reserved_public_username" if reserved else "invalid_public_username", 400) from None
        try:
            validate_signup_password(password)
        except (ValueError, TypeError, AttributeError):
            raise PhoneOtpError("invalid_password", 400) from None
        flow_digest = self._flow_digest(flow_id)
        # Do not spend a slow password hash for an invalid/used proof. Release
        # these short locks, hash, then recheck proof and account before writing.
        with self.session_factory() as db, db.begin():
            now = _now()
            state, challenge = self._locked_challenge(db, challenge_id, flow_digest, now)
            error = self._proof_error(state, challenge, code, flow_digest, now)
            if error is None:
                user = self._phone_user(db, challenge.phone_e164)
                now = _now()
                if _utc(challenge.expires_at) <= now:
                    raise PhoneOtpError("challenge_expired", 400)
                if user is not None and not self._needs_completion(db, user, challenge.phone_e164):
                    error = PhoneOtpError("profile_already_complete", 409)
        if error:
            raise error
        password_hash = get_password_hash(password)
        result = None
        try:
            with self.session_factory() as db, db.begin():
                now = _now()
                state, challenge = self._locked_challenge(db, challenge_id, flow_digest, now)
                error = self._proof_error(state, challenge, code, flow_digest, now)
                if error is None:
                    user = self._phone_user(db, challenge.phone_e164)
                    now = _now()
                    if _utc(challenge.expires_at) <= now:
                        raise PhoneOtpError("challenge_expired", 400)
                    grant = 0
                    if user is None:
                        user = self._create_user(db, public_username=public_username, password_hash=password_hash)
                        db.add(
                            models_db.PhoneIdentity(phone_e164=challenge.phone_e164, user_id=user.id, verified_at=now)
                        )
                        if db.get(models_db.PhoneSignupClaim, challenge.phone_e164) is None:
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
                            grant = _SIGNUP_CREDITS
                    else:
                        if not self._needs_completion(db, user, challenge.phone_e164):
                            raise PhoneOtpError("profile_already_complete", 409)
                        user.public_username = public_username
                        user.hashed_password = password_hash
                    challenge.state = "consumed"
                    challenge.consumed_at = now
                    db.flush()
                    db.refresh(user)
                    # Public-name uniqueness can wait after the account lock.
                    # Expiry here rolls back the grant and proof consumption too.
                    if _utc(challenge.expires_at) <= _now():
                        raise PhoneOtpError("challenge_expired", 400)
                    result = {**self._public_user(user), "signup_grant_credits": grant}
        except IntegrityError as error:
            if self._is_public_name_conflict(error):
                raise PhoneOtpError("public_username_taken", 409) from None
            raise
        if error:
            raise error
        return result

    def _bind_reauthentication(self, user_id, current_password, now):
        start = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        with self.session_factory() as db, db.begin():
            user = self._bind_actor(db, user_id, require_unbound=False)
            self._reserve_bucket(
                db,
                kind="bind_reauth",
                key=str(user_id),
                start=start,
                end=start + timedelta(minutes=15),
                limit=5,
                now=now,
                error_code="bind_reauth_locked",
            )
            password_hash = user.hashed_password
        # Both the failed password and every later OTP/DB failure retain the
        # committed per-user attempt. No password check holds database locks.
        valid_password = False
        if isinstance(current_password, str) and current_password:
            try:
                valid_password = verify_password(current_password, password_hash)
            except (TypeError, ValueError):
                pass
        if not valid_password:
            raise PhoneOtpError("bind_reauth_failed", 401)
        return password_hash

    def bind(self, *, user_id, challenge_id, code, flow_id, current_password=None):
        self._ensure_available()
        now = _now()
        password_hash = self._bind_reauthentication(user_id, current_password, now)
        now = _now()
        flow_digest = self._flow_digest(flow_id)
        error = None
        result = None
        try:
            with self.session_factory() as db, db.begin():
                state, challenge = self._locked_challenge(
                    db, challenge_id, flow_digest, now, purpose="bind", actor_id=user_id, allow_consumed=True
                )
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
                    # A cloud user's row serializes different phones targeting
                    # the same account. Always lock after phone -> challenge.
                    db.execute(
                        select(models_db.User).where(models_db.User.id == user_id).with_for_update()
                    ).scalar_one_or_none()
                    user = self._bind_actor(db, user_id, require_unbound=False)
                    if not hmac.compare_digest(user.hashed_password, password_hash):
                        raise PhoneOtpError("bind_reauth_failed", 401)
                    target = db.execute(
                        select(models_db.PhoneIdentity).where(
                            models_db.PhoneIdentity.phone_e164 == challenge.phone_e164
                        )
                    ).scalar_one_or_none()
                    own = db.execute(
                        select(models_db.PhoneIdentity).where(models_db.PhoneIdentity.user_id == user_id)
                    ).scalar_one_or_none()
                    if (target is not None and target.user_id != user_id) or (
                        own is not None and own.phone_e164 != challenge.phone_e164
                    ):
                        raise PhoneOtpError("phone_in_use", 409)
                    if own is None:
                        if challenge.state == "consumed":
                            raise PhoneOtpError("challenge_used", 400)
                        db.add(
                            models_db.PhoneIdentity(phone_e164=challenge.phone_e164, user_id=user_id, verified_at=now)
                        )
                    if db.get(models_db.PhoneSignupClaim, challenge.phone_e164) is None:
                        db.add(
                            models_db.PhoneSignupClaim(
                                phone_e164=challenge.phone_e164, claim_type="bound_existing", user_id=user_id
                            )
                        )
                    challenge.state = "consumed"
                    challenge.consumed_at = challenge.consumed_at or now
                    db.flush()
                    result = {"bound": True, "masked_phone": mask_phone(challenge.phone_e164)}
        except IntegrityError as integrity_error:
            constraint = getattr(getattr(integrity_error.orig, "diag", None), "constraint_name", None)
            if constraint in {"uq_phone_identity_phone", "uq_phone_identity_user"}:
                raise PhoneOtpError("phone_in_use", 409) from None
            raise
        if error:
            raise error
        return result

    def status(self, *, user_id):
        with self.session_factory() as db:
            phone = db.execute(
                select(models_db.PhoneIdentity.phone_e164).where(models_db.PhoneIdentity.user_id == user_id)
            ).scalar_one_or_none()
            return {"bound": True, "masked_phone": mask_phone(phone)} if phone else {"bound": False}
