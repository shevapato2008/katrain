"""OTP consumption, permanent claims and real credit ledger commit together."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import select

from katrain.web.core import models_db
from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_phone_otp_limits_pg import PHONE, FLOW, FakeSender, issue, make_service


def login(service, sender, challenge, flow=FLOW):
    return service.login(challenge_id=challenge["challenge_id"], code=sender.calls[-1][1], flow_id=flow)


def test_signup_gives_once_and_subsequent_login_keeps_canonical_user(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError
    from katrain.web.core.auth import verify_password

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    user = login(service, sender, challenge)
    assert user["credits"] == 5000
    assert user["username"].startswith("u_") and len(user["username"]) == 22
    assert PHONE not in str(user) and "hashed_password" not in user
    assert service.status(user_id=user["id"]) == {"bound": True, "masked_phone": "+86 138****0011"}
    with pytest.raises(PhoneOtpError):
        login(service, sender, challenge)
    with sessions() as db:
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        db.commit()
    again = login(service, sender, issue(service, phone="008613800000011"))
    assert (again["id"], again["uuid"], again["username"], again["credits"]) == (
        user["id"],
        user["uuid"],
        user["username"],
        5000,
    )
    with sessions() as db:
        assert db.query(models_db.User).count() == 1
        assert db.query(models_db.PhoneIdentity).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == 1
        tx = db.query(models_db.CreditTransaction).one()
        assert (tx.delta, tx.reason, tx.status, tx.balance_after) == (5000, "signup_grant", "committed", 5000)
        assert PHONE not in tx.ref_id and "13800000011" not in tx.ref_id
        stored = db.get(models_db.User, user["id"])
        assert stored.hashed_password.startswith("$2")
        assert not verify_password("otp-only", stored.hashed_password)


def test_same_challenge_concurrent_login_has_one_account_and_grant(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    barrier = Barrier(2)

    def attempt(_):
        barrier.wait()
        try:
            return login(service, sender, challenge)
        except PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, range(2)))
    assert sum(isinstance(result, dict) for result in results) == 1
    with sessions() as db:
        assert db.query(models_db.User).count() == 1
        assert db.query(models_db.PhoneIdentity).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == 1
        assert db.query(models_db.CreditTransaction).count() == 1


def test_same_phone_different_challenges_only_active_can_create_user(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    old = issue(service)
    old_code = sender.calls[-1][1]
    with sessions() as db:
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        db.commit()
    current = issue(service)
    current_code = sender.calls[-1][1]
    barrier = Barrier(2)

    def attempt(values):
        challenge, code = values
        barrier.wait()
        try:
            return service.login(challenge_id=challenge["challenge_id"], code=code, flow_id=FLOW)
        except PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, [(old, old_code), (current, current_code)]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "challenge_invalid" in results
    with sessions() as db:
        assert db.query(models_db.User).count() == 1
        assert db.query(models_db.PhoneIdentity).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == 1
        assert db.query(models_db.CreditTransaction).count() == 1


def test_existing_bound_user_keeps_uuid_balance_membership_and_password(membership_pg_engine):
    from katrain.web.core.auth import get_password_hash, verify_password

    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db:
        user = models_db.User(
            username="canonical-owner",
            hashed_password=get_password_hash("old-password"),
            credits=123456,
            rank="5d",
            membership_revision=7,
        )
        db.add(user)
        db.flush()
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=user.id))
        db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, user_id=user.id, claim_type="bound_existing"))
        db.commit()
        user_id, user_uuid = user.id, user.uuid
    result = login(service, sender, issue(service))
    assert (result["id"], result["uuid"], result["username"], result["credits"], result["rank"]) == (
        user_id,
        user_uuid,
        "canonical-owner",
        123456,
        "5d",
    )
    with sessions() as db:
        assert db.query(models_db.CreditTransaction).count() == 0
        user = db.get(models_db.User, user_id)
        assert user.membership_revision == 7
        assert verify_password("old-password", user.hashed_password)


def test_ledger_failure_rolls_back_user_identity_claim_and_consumption(membership_pg_engine, monkeypatch):
    from katrain.web.core import billing

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    with sessions() as db:
        state = db.get(models_db.SmsPhoneState, PHONE)
        state.error_count = 2
        db.commit()
    apply = billing.apply_adjustment

    def fail_after_write(*args, **kwargs):
        apply(*args, **kwargs)
        raise RuntimeError("injected ledger failure")

    monkeypatch.setattr(billing, "apply_adjustment", fail_after_write)
    with pytest.raises(RuntimeError, match="injected ledger failure"):
        login(service, sender, challenge)
    with sessions() as db:
        assert db.query(models_db.User).count() == 0
        assert db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.SmsChallenge, challenge["challenge_id"]).state == "sent"
        assert db.get(models_db.SmsPhoneState, PHONE).error_count == 2
    monkeypatch.setattr(billing, "apply_adjustment", apply)
    assert login(service, sender, challenge)["credits"] == 5000


@pytest.mark.parametrize("claim_type", ["signup_grant", "bound_existing"])
def test_permanent_claim_without_identity_rebuilds_zero_grant(membership_pg_engine, claim_type):
    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db:
        db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type=claim_type, user_id=999))
        old = models_db.User(username="13800000011", hashed_password="existing", credits=9876)
        db.add(old)
        db.commit()
        old_id = old.id
    result = login(service, sender, issue(service))
    assert result["credits"] == 0 and result["id"] != old_id
    with sessions() as db:
        assert db.get(models_db.User, old_id).credits == 9876
        assert db.query(models_db.PhoneSignupClaim).count() == 1
        assert db.query(models_db.CreditTransaction).count() == 0


@pytest.mark.parametrize("bad", ["pending", "expired", "flow", "purpose", "superseded"])
def test_ineligible_challenge_never_creates_account(membership_pg_engine, bad):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    with sessions() as db:
        row = db.get(models_db.SmsChallenge, challenge["challenge_id"])
        if bad in {"pending", "superseded"}:
            row.state = bad
        elif bad == "expired":
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        elif bad == "purpose":
            row.purpose = "bind"
            row.bind_user_id = 999
        db.commit()
    with pytest.raises(PhoneOtpError):
        login(service, sender, challenge, flow="a" * 32 if bad == "flow" else FLOW)
    with sessions() as db:
        assert db.query(models_db.User).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0


def test_unknown_delivery_correct_code_can_be_consumed(membership_pg_engine):
    from katrain.web.core.sms import SmsUnknown

    service, sender, _ = make_service(membership_pg_engine, FakeSender(SmsUnknown()))
    challenge = issue(service)
    assert challenge["delivery"] == "unknown"
    assert login(service, sender, challenge)["credits"] == 5000
