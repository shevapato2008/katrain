"""OTP consumption, permanent claims and real credit ledger commit together."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import select, text

from katrain.web.core import models_db
from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_phone_otp_limits_pg import PHONE, FLOW, FakeSender, issue, make_service


def login(service, sender, challenge, flow=FLOW):
    return service.login(challenge_id=challenge["challenge_id"], code=sender.calls[-1][1], flow_id=flow)


PASSWORD = "密码很长而且不被修剪的十五字以上"


def register(service, sender, challenge, flow=FLOW, name="棋手一", password=PASSWORD):
    return service.register(
        challenge_id=challenge["challenge_id"],
        code=sender.calls[-1][1],
        flow_id=flow,
        public_username=name,
        password=password,
    )


def test_unknown_login_requires_profile_without_writing_or_extending_proof(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    with sessions() as db:
        expires = db.get(models_db.SmsChallenge, challenge["challenge_id"]).expires_at
        db.get(models_db.SmsPhoneState, PHONE).error_count = 2
        db.commit()
    with pytest.raises(PhoneOtpError) as caught:
        login(service, sender, challenge)
    assert (caught.value.code, caught.value.status_code, caught.value.mode) == ("profile_required", 409, "register")
    with sessions() as db:
        assert db.query(models_db.User).count() == db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == db.query(models_db.CreditTransaction).count() == 0
        proof = db.get(models_db.SmsChallenge, challenge["challenge_id"])
        assert proof.state == "sent" and proof.expires_at == expires and proof.consumed_at is None
        assert db.get(models_db.SmsPhoneState, PHONE).error_count == 2


def test_signup_gives_once_and_subsequent_login_keeps_canonical_user(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError
    from katrain.web.core.auth import verify_password

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    user = register(service, sender, challenge)
    assert user["credits"] == user["signup_grant_credits"] == 5000
    assert user["public_username"] == "棋手一"
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


def test_same_challenge_concurrent_registration_has_one_account_and_grant(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    barrier = Barrier(2)

    def attempt(_):
        barrier.wait()
        try:
            return register(service, sender, challenge)
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
            return service.register(
                challenge_id=challenge["challenge_id"],
                code=code,
                flow_id=FLOW,
                public_username="棋手一",
                password=PASSWORD,
            )
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
        register(service, sender, challenge)
    with sessions() as db:
        assert db.query(models_db.User).count() == 0
        assert db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.SmsChallenge, challenge["challenge_id"]).state == "sent"
        assert db.get(models_db.SmsPhoneState, PHONE).error_count == 2
    monkeypatch.setattr(billing, "apply_adjustment", apply)
    assert register(service, sender, challenge)["credits"] == 5000


@pytest.mark.parametrize("claim_type", ["signup_grant", "bound_existing"])
def test_permanent_claim_without_identity_rebuilds_zero_grant(membership_pg_engine, claim_type):
    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db:
        db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type=claim_type, user_id=999))
        old = models_db.User(username="13800000011", hashed_password="existing", credits=9876)
        db.add(old)
        db.commit()
        old_id = old.id
    result = register(service, sender, issue(service))
    assert result["signup_grant_credits"] == 0
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
        register(service, sender, challenge, flow="a" * 32 if bad == "flow" else FLOW)
    with sessions() as db:
        assert db.query(models_db.User).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0


def test_unknown_delivery_correct_code_can_be_consumed(membership_pg_engine):
    from katrain.web.core.sms import SmsUnknown

    service, sender, _ = make_service(membership_pg_engine, FakeSender(SmsUnknown()))
    challenge = issue(service)
    assert challenge["delivery"] == "unknown"
    assert register(service, sender, challenge)["credits"] == 5000


def test_public_name_conflict_keeps_proof_for_retry(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db, db.begin():
        db.add(models_db.User(username="other-human", public_username="棋手一", hashed_password="old"))
    challenge = issue(service)
    with pytest.raises(PhoneOtpError) as caught:
        register(service, sender, challenge)
    assert caught.value.code == "public_username_taken"
    with sessions() as db:
        assert db.query(models_db.User).count() == 1
        assert db.query(models_db.PhoneIdentity).count() == db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.get(models_db.SmsChallenge, challenge["challenge_id"]).state == "sent"
    assert register(service, sender, challenge, name="棋手二")["signup_grant_credits"] == 5000


def test_two_phones_claiming_one_name_only_one_grant(membership_pg_engine):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    proofs = []
    for phone in (PHONE, "+8613800000012"):
        challenge = issue(service, phone=phone)
        proofs.append((challenge["challenge_id"], sender.calls[-1][1]))
    barrier = Barrier(2)

    def attempt(proof):
        barrier.wait()
        try:
            return service.register(
                challenge_id=proof[0], code=proof[1], flow_id=FLOW, public_username="同一个名字", password=PASSWORD
            )
        except PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, proofs))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "public_username_taken" in results
    with sessions() as db:
        assert db.query(models_db.User).count() == db.query(models_db.CreditTransaction).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == db.query(models_db.PhoneIdentity).count() == 1
        assert sorted(row.state for row in db.query(models_db.SmsChallenge)) == ["consumed", "sent"]


def test_legacy_completion_preserves_canonical_assets_and_claim(membership_pg_engine):
    from katrain.web.core.auth import get_password_hash, verify_password
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db, db.begin():
        user = models_db.User(
            username="u_" + "a" * 20,
            hashed_password=get_password_hash("old-password"),
            credits=18765,
            membership_revision=8,
            rank="6d",
        )
        db.add(user)
        db.flush()
        user_id, user_uuid = user.id, user.uuid
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=user_id))
        db.add(
            models_db.PhoneSignupClaim(phone_e164=PHONE, user_id=user_id, claim_type="signup_grant", grant_ref="old")
        )
        db.add(
            models_db.CreditTransaction(
                user_id=user_id, delta=5000, reason="signup_grant", ref_id="old", status="committed", balance_after=5000
            )
        )
    challenge = issue(service)
    with pytest.raises(PhoneOtpError) as caught:
        login(service, sender, challenge)
    assert caught.value.mode == "complete"
    result = register(service, sender, challenge)
    assert (result["id"], result["uuid"], result["username"], result["credits"], result["signup_grant_credits"]) == (
        user_id,
        user_uuid,
        "u_" + "a" * 20,
        18765,
        0,
    )
    with sessions() as db:
        user = db.get(models_db.User, user_id)
        assert (user.membership_revision, user.rank, user.public_username) == (8, "6d", "棋手一")
        assert verify_password(PASSWORD, user.hashed_password)
        assert db.query(models_db.CreditTransaction).one().ref_id == "old"
        assert db.query(models_db.PhoneSignupClaim).one().grant_ref == "old"
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        db.commit()
    second = issue(service)
    with pytest.raises(PhoneOtpError) as caught:
        register(service, sender, second, name="不能覆盖")
    assert caught.value.code == "profile_already_complete"
    assert login(service, sender, second)["public_username"] == "棋手一"


@pytest.mark.parametrize("password", ["a" * 14, "字" * 25, "a" * 15 + "\0", "a" * 73])
def test_new_password_validation_keeps_valid_proof(membership_pg_engine, password):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    with pytest.raises(PhoneOtpError) as caught:
        register(service, sender, challenge, password=password)
    assert caught.value.code == "invalid_password"
    assert register(service, sender, challenge, password="字" * 24)["signup_grant_credits"] == 5000


@pytest.mark.parametrize(
    "name, expected",
    [
        ("a", "invalid_public_username"),
        ("a b", "invalid_public_username"),
        ("Guest", "reserved_public_username"),
        ("ADMIN:foo", "reserved_public_username"),
        ("U_anything", "reserved_public_username"),
    ],
)
def test_new_public_name_validation(membership_pg_engine, name, expected):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    with pytest.raises(PhoneOtpError) as caught:
        register(service, sender, challenge, name=name)
    assert caught.value.code == expected
    with sessions() as db:
        assert db.query(models_db.User).count() == 0
        assert db.get(models_db.SmsChallenge, challenge["challenge_id"]).state == "sent"


@pytest.mark.parametrize("kind", ["bound_existing", "admin", "near_generated"])
def test_generated_looking_full_account_is_not_completed(membership_pg_engine, kind):
    from katrain.web.core.phone_otp import PhoneOtpError

    service, sender, sessions = make_service(membership_pg_engine)
    canonical = "u_" + "a" * 20 + ("suffix" if kind == "near_generated" else "")
    with sessions() as db, db.begin():
        user = models_db.User(username=canonical, hashed_password="old-hash", credits=7654, is_admin=kind == "admin")
        db.add(user)
        db.flush()
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=user.id))
        if kind == "bound_existing":
            db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, user_id=user.id, claim_type="bound_existing"))
    challenge = issue(service)
    with pytest.raises(PhoneOtpError) as caught:
        register(service, sender, challenge)
    assert caught.value.code == "profile_already_complete"
    assert login(service, sender, challenge)["username"] == canonical
    with sessions() as db:
        assert db.query(models_db.User).one().hashed_password == "old-hash"
        assert db.query(models_db.CreditTransaction).count() == 0


def test_register_wrong_codes_commit_budget_without_password_hash(membership_pg_engine, monkeypatch):
    from katrain.web.core import phone_otp

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)

    def forbidden_hash(password):
        raise AssertionError("invalid proof must not hash")

    monkeypatch.setattr(phone_otp, "get_password_hash", forbidden_hash)
    wrong = "000000" if sender.calls[-1][1] != "000000" else "000001"
    for expected in ["invalid_code"] * 4 + ["otp_locked"]:
        with pytest.raises(phone_otp.PhoneOtpError) as caught:
            service.register(
                challenge_id=challenge["challenge_id"],
                code=wrong,
                flow_id=FLOW,
                public_username="测试棋手",
                password=PASSWORD,
            )
        assert caught.value.code == expected
    with sessions() as db:
        assert db.get(models_db.SmsPhoneState, PHONE).error_count == 5
        assert db.query(models_db.User).count() == db.query(models_db.CreditTransaction).count() == 0


def test_hash_releases_locks_and_expired_proof_is_rechecked(membership_pg_engine, monkeypatch):
    from katrain.web.core import phone_otp

    service, sender, sessions = make_service(membership_pg_engine)
    challenge = issue(service)
    real_hash = phone_otp.get_password_hash

    def expire_during_hash(password):
        with sessions() as db, db.begin():
            db.execute(text("SELECT phone_e164 FROM sms_phone_state FOR UPDATE NOWAIT")).all()
            row = db.execute(select(models_db.SmsChallenge).with_for_update(nowait=True)).scalar_one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        return real_hash(password)

    monkeypatch.setattr(phone_otp, "get_password_hash", expire_during_hash)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        register(service, sender, challenge)
    assert caught.value.code == "challenge_expired"
    with sessions() as db:
        assert db.query(models_db.User).count() == db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.get(models_db.SmsChallenge, challenge["challenge_id"]).state == "sent"


def test_login_checks_expiry_after_waiting_for_phone_lock(membership_pg_engine, monkeypatch):
    from katrain.web.core import phone_otp

    service, sender, sessions = make_service(membership_pg_engine)
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: now)
    with sessions() as db, db.begin():
        user = models_db.User(username="complete-account", public_username="已完成", hashed_password="old")
        db.add(user)
        db.flush()
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=user.id))
    challenge = issue(service)
    lock = service._lock_phone

    def waited_for_lock(db, phone):
        nonlocal now
        state = lock(db, phone)
        now += timedelta(seconds=301)
        return state

    monkeypatch.setattr(service, "_lock_phone", waited_for_lock)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        login(service, sender, challenge)
    assert caught.value.code == "challenge_expired"
    with sessions() as db:
        assert db.get(models_db.SmsChallenge, challenge["challenge_id"]).state == "sent"


@pytest.mark.parametrize("operation", ["login", "complete"])
def test_proof_expiry_after_final_account_lock_rolls_back(membership_pg_engine, monkeypatch, operation):
    from katrain.web.core import phone_otp

    service, sender, sessions = make_service(membership_pg_engine)
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: now)
    public_name = "CompletedName" if operation == "login" else None
    with sessions() as db, db.begin():
        user = models_db.User(
            username="u_" + "a" * 20,
            public_username=public_name,
            hashed_password="old-hash",
            credits=7654,
            membership_revision=8,
        )
        db.add(user)
        db.flush()
        user_id, user_uuid = user.id, user.uuid
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=user_id))
        db.add(
            models_db.PhoneSignupClaim(
                phone_e164=PHONE, user_id=user_id, claim_type="signup_grant", grant_ref="old-grant"
            )
        )
    challenge = issue(service)
    get_user = service._phone_user
    calls = 0

    def waited_for_account_lock(db, phone):
        nonlocal now, calls
        user = get_user(db, phone)
        calls += 1
        if calls == (1 if operation == "login" else 2):
            now += timedelta(seconds=301)
        return user

    monkeypatch.setattr(service, "_phone_user", waited_for_account_lock)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        if operation == "login":
            login(service, sender, challenge)
        else:
            register(service, sender, challenge)
    assert caught.value.code == "challenge_expired"
    with sessions() as db:
        stored = db.get(models_db.User, user_id)
        assert (
            stored.uuid,
            stored.public_username,
            stored.hashed_password,
            stored.credits,
            stored.membership_revision,
        ) == (user_uuid, public_name, "old-hash", 7654, 8)
        assert db.query(models_db.PhoneSignupClaim).one().grant_ref == "old-grant"
        assert db.query(models_db.CreditTransaction).count() == 0
        proof = db.get(models_db.SmsChallenge, challenge["challenge_id"])
        assert proof.state == "sent" and proof.consumed_at is None


def test_registration_expiry_during_name_insert_rolls_back_every_write(membership_pg_engine, monkeypatch):
    from katrain.web.core import phone_otp

    service, sender, sessions = make_service(membership_pg_engine)
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: now)
    challenge = issue(service)
    create_user = service._create_user

    def waited_for_public_name(db, **kwargs):
        nonlocal now
        user = create_user(db, **kwargs)
        now += timedelta(seconds=301)
        return user

    monkeypatch.setattr(service, "_create_user", waited_for_public_name)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        register(service, sender, challenge)
    assert caught.value.code == "challenge_expired"
    with sessions() as db:
        assert db.query(models_db.User).count() == db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == db.query(models_db.CreditTransaction).count() == 0
        proof = db.get(models_db.SmsChallenge, challenge["challenge_id"])
        assert proof.state == "sent" and proof.consumed_at is None
