"""Real PostgreSQL send reservations, cross-worker attempts and send outcomes."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from tests.web_ui.membership_test_support import membership_pg_engine


FLOW = "b209a74fad5b4091a1376bbfe5e37963"
PHONE = "+8613800000011"


class FakeSender:
    def __init__(self, outcome=None):
        self.outcome = outcome
        self.calls = []
        self.lock = Lock()

    async def send(self, phone_e164, code):
        with self.lock:
            self.calls.append((phone_e164, code))
        if self.outcome:
            raise self.outcome


def otp_config(**overrides):
    values = dict(
        KATRAIN_SMS_ENABLED=True,
        KATRAIN_SMS_DAILY_LIMIT=10,
        KATRAIN_ENVIRONMENT="test",
        SECRET_KEY="test-only-otp-secret-" * 3,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def make_service(engine, sender=None, config=None):
    from katrain.web.core.phone_otp import PhoneOtpService

    from katrain.web.core.migrations import migrate_public_username_schema

    migrate_public_username_schema(engine, mode="server")
    sender = sender or FakeSender()
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return PhoneOtpService(sessions, config or otp_config(), sender_factory=lambda config: sender), sender, sessions


def issue(service, phone=PHONE, ip="127.0.0.1", purpose="login", actor_id=None, flow=FLOW):
    return asyncio.run(
        service.request_challenge(phone=phone, purpose=purpose, flow_id=flow, client_ip=ip, actor_id=actor_id)
    )


def test_phone_service_contract_is_present():
    from katrain.web.core import phone_otp

    assert callable(getattr(phone_otp, "PhoneOtpService", None))
    error = phone_otp.PhoneOtpError("sms_unavailable", 503, 60)
    assert (error.code, error.status_code, error.retry_after) == ("sms_unavailable", 503, 60)


def test_sms_settings_read_environment_and_fail_closed_for_invalid_values(monkeypatch):
    from katrain.web.core.config import Settings

    monkeypatch.setenv("KATRAIN_SMS_ENABLED", "true")
    monkeypatch.setenv("KATRAIN_SMS_DAILY_LIMIT", "7")
    monkeypatch.setenv("KATRAIN_SMS_CREDENTIALS_FILE", "/test-only/no-read.env")
    monkeypatch.setenv("KATRAIN_SMS_SIGN_NAME", "test-sign")
    monkeypatch.setenv("KATRAIN_SMS_TEMPLATE_CODE", "test-template")
    monkeypatch.setenv("KATRAIN_SMS_TRUSTED_PROXY_IPS", "")
    config = Settings()
    assert getattr(config, "KATRAIN_SMS_ENABLED", False) is True
    assert config.KATRAIN_SMS_DAILY_LIMIT == 7
    assert config.KATRAIN_SMS_CREDENTIALS_FILE == "/test-only/no-read.env"
    assert (config.KATRAIN_SMS_SIGN_NAME, config.KATRAIN_SMS_TEMPLATE_CODE) == ("test-sign", "test-template")
    monkeypatch.setenv("KATRAIN_SMS_DAILY_LIMIT", "not-an-integer")
    assert Settings().KATRAIN_SMS_DAILY_LIMIT == 0
    monkeypatch.setenv("KATRAIN_SMS_ENABLED", "invalid-bool")
    assert Settings().KATRAIN_SMS_ENABLED is False


def test_same_phone_first_send_race_only_reserves_and_sends_once(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    barrier = Barrier(2)

    def attempt(phone):
        barrier.wait()
        try:
            return issue(service, phone=phone)
        except PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, [PHONE, "13800000011"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "sms_limited" in results
    assert len(sender.calls) == 1
    with sessions() as db:
        assert db.query(models_db.SmsChallenge).count() == 1
        assert {bucket.count for bucket in db.query(models_db.SmsSendBucket)} == {1}


def test_global_last_budget_race_rolls_back_every_losing_bucket(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine, config=otp_config(KATRAIN_SMS_DAILY_LIMIT=1))
    barrier = Barrier(2)

    def attempt(phone):
        barrier.wait()
        try:
            return issue(service, phone=phone)
        except PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, [PHONE, "+8613900000011"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "sms_limited" in results
    assert len(sender.calls) == 1
    with sessions() as db:
        assert db.query(models_db.SmsChallenge).count() == 1
        assert db.query(models_db.SmsPhoneState).count() == 1
        assert db.query(models_db.SmsSendBucket).count() == 3
        assert {bucket.count for bucket in db.query(models_db.SmsSendBucket)} == {1}


@pytest.mark.parametrize(
    "outcome,delivery,code", [("unknown", "unknown", None), ("rejected", "rejected", "sms_rejected")]
)
def test_failed_delivery_keeps_budget_and_cooldown(membership_pg_engine, outcome, delivery, code):
    from katrain.web.core.phone_otp import PhoneOtpError
    from katrain.web.core.sms import SmsRejected, SmsUnknown

    sender = FakeSender(SmsUnknown() if outcome == "unknown" else SmsRejected())
    service, sender, sessions = make_service(membership_pg_engine, sender)
    if code:
        with pytest.raises(PhoneOtpError) as caught:
            issue(service)
        assert caught.value.code == code
    else:
        result = issue(service)
        assert result["delivery"] == delivery and result["challenge_id"]
    with sessions() as db:
        assert db.scalar(select(models_db.SmsChallenge.state)) == delivery
        assert {bucket.count for bucket in db.query(models_db.SmsSendBucket)} == {1}
    with pytest.raises(PhoneOtpError) as caught:
        issue(service)
    assert caught.value.code == "sms_limited"
    assert len(sender.calls) == 1


def test_errors_survive_resend_flow_and_worker_then_unlock(membership_pg_engine, monkeypatch):
    from katrain.web.core import phone_otp

    current = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: current)
    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    for _ in range(3):
        with pytest.raises(phone_otp.PhoneOtpError):
            service.login(challenge_id=challenge["challenge_id"], code="wrong", flow_id=FLOW)
    current += timedelta(seconds=61)
    other, _, _ = make_service(membership_pg_engine, sender)
    new_flow = "b" * 32
    challenge = issue(other, flow=new_flow)
    for _ in range(2):
        with pytest.raises(phone_otp.PhoneOtpError):
            other.login(challenge_id=challenge["challenge_id"], code="wrong", flow_id=new_flow)
    with sessions() as db:
        state = db.get(models_db.SmsPhoneState, PHONE)
        assert state.error_count == 5 and state.blocked_until == current + timedelta(minutes=15)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        issue(other, phone="008613800000011")
    assert caught.value.code == "otp_locked" and caught.value.retry_after == 900
    current += timedelta(minutes=15, seconds=1)
    issue(other)
    with sessions() as db:
        assert db.get(models_db.SmsPhoneState, PHONE).error_count == 0


def test_phone_and_ip_windows_are_enforced_without_partial_reservations(membership_pg_engine, monkeypatch):
    from katrain.web.core import phone_otp

    current = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: current)
    service, sender, sessions = make_service(membership_pg_engine)
    for _ in range(5):
        issue(service)
        current += timedelta(seconds=61)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        issue(service)
    assert caught.value.code == "sms_limited"
    with sessions() as db:
        assert sorted(bucket.count for bucket in db.query(models_db.SmsSendBucket)) == [5, 5, 5]
        # Fixed hour bucket filled by other users; new phone must not leave rows.
        db.query(models_db.SmsSendBucket).filter_by(kind="ip_hour").update({"count": 20})
        db.commit()
    with pytest.raises(phone_otp.PhoneOtpError):
        issue(service, phone="13900000011")
    assert len(sender.calls) == 5
    with sessions() as db:
        assert db.query(models_db.SmsPhoneState).count() == 1


def test_bad_config_and_invalid_flow_never_send(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine, config=otp_config(KATRAIN_SMS_DAILY_LIMIT=100))
    with pytest.raises(PhoneOtpError) as caught:
        issue(service)
    assert caught.value.code == "sms_unavailable"
    service, _, _ = make_service(membership_pg_engine, sender)
    with pytest.raises(PhoneOtpError) as caught:
        issue(service, flow="predictable")
    assert caught.value.code == "challenge_invalid"
    assert sender.calls == []
    with sessions() as db:
        assert db.query(models_db.SmsChallenge).count() == 0


def test_sender_observes_committed_pending_without_phone_or_budget_locks(membership_pg_engine):
    class InspectingSender(FakeSender):
        async def send(self, phone_e164, code):
            with membership_pg_engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout='500ms'"))
                assert (
                    conn.execute(text("SELECT state FROM sms_challenges FOR UPDATE NOWAIT")).scalar_one() == "pending"
                )
                assert len(conn.execute(text("SELECT phone_e164 FROM sms_phone_state FOR UPDATE NOWAIT")).all()) == 1
                assert len(conn.execute(text("SELECT count FROM sms_send_buckets FOR UPDATE NOWAIT")).all()) == 3
            await super().send(phone_e164, code)

    service, sender, _ = make_service(membership_pg_engine, InspectingSender())
    assert issue(service)["delivery"] == "sent"
    assert len(sender.calls) == 1


@pytest.mark.parametrize(
    "username,is_admin,password",
    [
        ("guest", False, "$2b$fake"),
        ("admin:reserved", False, "$2b$fake"),
        ("owner", True, "$2b$fake"),
        ("shadow", False, "SHADOW_USER_NO_LOCAL_AUTH"),
    ],
)
def test_bind_challenge_rejects_ineligible_actor_without_sms(membership_pg_engine, username, is_admin, password):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db:
        actor = models_db.User(username=username, hashed_password=password, is_admin=is_admin, credits=12345)
        db.add(actor)
        db.commit()
        actor_id = actor.id
    with pytest.raises(PhoneOtpError) as caught:
        issue(service, purpose="bind", actor_id=actor_id)
    assert caught.value.code == "bind_not_allowed"
    assert sender.calls == []
    with sessions() as db:
        assert db.query(models_db.SmsChallenge).count() == 0
        assert db.get(models_db.User, actor_id).credits == 12345


@pytest.mark.parametrize("budget_full", [True, False])
def test_bind_challenge_does_not_disclose_target_phone_ownership(membership_pg_engine, monkeypatch, budget_full):
    from katrain.web.core import phone_otp
    from katrain.web.core.auth import get_password_hash

    current = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: current)
    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db:
        password_hash = get_password_hash("current-test-password")
        actor = models_db.User(username="eligible-unbound-actor", hashed_password=password_hash)
        owner = models_db.User(username="other-phone-owner", hashed_password=password_hash)
        db.add_all([actor, owner])
        db.flush()
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=owner.id))
        if budget_full:
            db.add(
                models_db.SmsSendBucket(
                    kind="global_day",
                    key="all",
                    window_start=datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc),
                    count=10,
                )
            )
        db.commit()
        actor_id = actor.id
        assert db.query(models_db.SmsPhoneState).count() == 0

    responses = []
    for target in (PHONE, "+8613900000011"):
        if budget_full:
            with pytest.raises(phone_otp.PhoneOtpError) as caught:
                issue(service, phone=target, purpose="bind", actor_id=actor_id)
            assert (caught.value.status_code, caught.value.code) == (429, "sms_limited")
            responses.append(caught.value.retry_after)
        else:
            responses.append(issue(service, phone=target, purpose="bind", actor_id=actor_id))
    if budget_full:
        assert responses[0] == responses[1]
        assert sender.calls == []
    else:
        assert set(responses[0]) == set(responses[1]) == {"challenge_id", "retry_after", "expires_in", "delivery"}
        assert responses[0]["challenge_id"] != responses[1]["challenge_id"]
        assert [(r["retry_after"], r["expires_in"], r["delivery"]) for r in responses] == [(60, 300, "sent")] * 2
        assert len(sender.calls) == 2
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.query(models_db.SmsPhoneState).count() == (0 if budget_full else 2)
