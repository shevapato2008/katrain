"""Old-account binding proves password and phone without changing account assets."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event

import pytest
from sqlalchemy import event, select

from katrain.web.core import billing, models_db, phone_otp
from katrain.web.core.auth import get_password_hash, verify_password
from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_phone_otp_limits_pg import FLOW, PHONE, issue, make_service


PASSWORD = "current-password-2026"
OTHER_PHONE = "+8613900000011"


@pytest.fixture(scope="module")
def password_hash():
    return get_password_hash(PASSWORD)


@pytest.fixture
def binding(membership_pg_engine, password_hash):
    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db:
        user = models_db.User(
            username="old-canonical-owner",
            hashed_password=password_hash,
            credits=123456,
            rank="5d",
            membership_revision=7,
        )
        db.add(user)
        db.commit()
        user_id, user_uuid = user.id, user.uuid
    return service, sender, sessions, user_id, user_uuid


def bind_challenge(binding, *, phone=PHONE, actor_id=None, flow=FLOW, purpose="bind"):
    service, sender, _, user_id, _ = binding
    result = issue(
        service, phone=phone, purpose=purpose, actor_id=actor_id or user_id if purpose == "bind" else None, flow=flow
    )
    return result["challenge_id"], sender.calls[-1][1]


def submit(binding, challenge_id, code, *, user_id=None, flow=FLOW, password=PASSWORD):
    service, _, _, default_user_id, _ = binding
    return service.bind(
        user_id=user_id or default_user_id,
        challenge_id=challenge_id,
        code=code,
        flow_id=flow,
        current_password=password,
    )


def reauth_count(sessions, user_id):
    with sessions() as db:
        return db.scalar(
            select(models_db.SmsSendBucket.count).where(
                models_db.SmsSendBucket.kind == "bind_reauth", models_db.SmsSendBucket.key == str(user_id)
            )
        )


@pytest.mark.parametrize("password", [None, "", "wrong-password", 123, {"invalid": "type"}])
def test_correct_phone_code_without_current_password_cannot_bind(binding, password):
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, code, password=password)
    assert (caught.value.status_code, caught.value.code) == (401, "bind_reauth_failed")
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.User, user_id).credits == 123456
        assert db.get(models_db.SmsChallenge, challenge_id).state == "sent"
    assert reauth_count(sessions, user_id) == 1


def test_reauth_limit_is_per_user_across_phone_flow_challenge_and_worker(binding, monkeypatch):
    current = datetime(2026, 11, 11, 4, 7, tzinfo=timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: current)
    service, sender, sessions, user_id, _ = binding
    first_id, first_code = bind_challenge(binding)
    second_id, second_code = bind_challenge(binding, phone=OTHER_PHONE, flow="a" * 32)
    other, _, _ = make_service(sessions.kw["bind"], sender)
    for index in range(5):
        selected = service if index % 2 == 0 else other
        challenge_id, code, flow = (
            (first_id, first_code, FLOW) if index % 2 == 0 else (second_id, second_code, "a" * 32)
        )
        with pytest.raises(phone_otp.PhoneOtpError) as caught:
            selected.bind(user_id=user_id, challenge_id=challenge_id, code=code, flow_id=flow, current_password="wrong")
        assert caught.value.code == "bind_reauth_failed"
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, first_id, first_code)
    assert (caught.value.status_code, caught.value.code, caught.value.retry_after) == (429, "bind_reauth_locked", 480)
    assert reauth_count(sessions, user_id) == 5
    current = current.replace(minute=15)
    # Password is still checked before the now-expired OTP; the new fixed bucket
    # is available without creating a binding.
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, first_id, first_code, password="wrong")
    assert caught.value.code == "bind_reauth_failed"
    with sessions() as db:
        assert sorted(
            db.scalars(select(models_db.SmsSendBucket.count).where(models_db.SmsSendBucket.kind == "bind_reauth"))
        ) == [1, 5]


def test_password_is_checked_before_otp_and_invalid_flow_still_spends_reauth(binding):
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, "nonexistent-challenge", "000000", flow="bad", password="wrong")
    assert caught.value.code == "bind_reauth_failed"
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, code, flow="bad")
    assert caught.value.code == "challenge_invalid"
    assert reauth_count(sessions, user_id) == 2


def test_concurrent_reauthentication_only_reserves_last_user_attempt(binding, monkeypatch):
    current = datetime(2026, 11, 11, 4, 7, tzinfo=timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: current)
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)
    with sessions() as db:
        db.add(
            models_db.SmsSendBucket(
                kind="bind_reauth", key=str(user_id), window_start=current.replace(minute=0), count=4
            )
        )
        db.commit()
    barrier = Barrier(2)

    def attempt(_):
        barrier.wait()
        try:
            submit(binding, challenge_id, code, password="wrong")
        except phone_otp.PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, range(2)))
    assert set(results) == {"bind_reauth_failed", "bind_reauth_locked"}
    assert reauth_count(sessions, user_id) == 5


def test_existing_permanent_signup_claim_is_preserved_when_binding(binding):
    _, _, sessions, user_id, _ = binding
    with sessions() as db:
        db.add(
            models_db.PhoneSignupClaim(
                phone_e164=PHONE, claim_type="signup_grant", user_id=999, grant_ref="historical-test-phone-claim"
            )
        )
        db.commit()
    challenge_id, code = bind_challenge(binding)
    assert submit(binding, challenge_id, code)["bound"] is True
    with sessions() as db:
        claim = db.query(models_db.PhoneSignupClaim).one()
        assert (claim.claim_type, claim.user_id, claim.grant_ref) == (
            "signup_grant",
            999,
            "historical-test-phone-claim",
        )
        assert db.query(models_db.PhoneIdentity).one().user_id == user_id
        assert db.query(models_db.CreditTransaction).count() == 0


def test_bind_grants_once_and_keeps_old_identity_and_assets(binding):
    service, sender, sessions, user_id, user_uuid = binding
    challenge_id, code = bind_challenge(binding)
    result = submit(binding, challenge_id, code)
    assert result == {"bound": True, "masked_phone": "+86 138****0011", "signup_grant_credits": 2000}
    assert submit(binding, challenge_id, code) == {**result, "signup_grant_credits": 0}
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 1
        claim = db.query(models_db.PhoneSignupClaim).one()
        ledger = db.query(models_db.CreditTransaction).one()
        assert (claim.claim_type, claim.user_id, claim.grant_ref) == ("bound_existing", user_id, ledger.ref_id)
        assert (ledger.delta, ledger.reason, ledger.status) == (2000, "signup_grant", "committed")
        old = db.get(models_db.User, user_id)
        assert (old.uuid, old.username, old.credits, old.rank, old.membership_revision) == (
            user_uuid,
            "old-canonical-owner",
            125456,
            "5d",
            7,
        )
        assert verify_password(PASSWORD, old.hashed_password)
        assert db.get(models_db.SmsChallenge, challenge_id).state == "consumed"
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        db.commit()
    login_challenge = issue(service)
    logged_in = service.login(challenge_id=login_challenge["challenge_id"], code=sender.calls[-1][1], flow_id=FLOW)
    assert (logged_in["id"], logged_in["uuid"], logged_in["username"], logged_in["credits"]) == (
        user_id,
        user_uuid,
        "old-canonical-owner",
        125456,
    )
    with sessions() as db:
        db.delete(db.query(models_db.PhoneIdentity).one())
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        db.commit()
        assert db.query(models_db.PhoneSignupClaim).count() == 1
    login_challenge = issue(service)
    rebuilt = service.register(
        challenge_id=login_challenge["challenge_id"],
        code=sender.calls[-1][1],
        flow_id=FLOW,
        public_username="新手机棋手",
        password="a-long-private-password",
    )
    assert rebuilt["id"] != user_id and rebuilt["credits"] == 0
    with sessions() as db:
        assert db.query(models_db.CreditTransaction).count() == 1


@pytest.mark.parametrize("continuation", [False, True])
@pytest.mark.parametrize("historical_zero_claim", [False, True])
def test_generated_legacy_account_binding_does_not_require_new_profile(binding, continuation, historical_zero_claim):
    service, sender, sessions, user_id, _ = binding
    canonical = "u_" + "a" * 20
    with sessions() as db, db.begin():
        db.get(models_db.User, user_id).username = canonical
        if historical_zero_claim:
            db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type="bound_existing", user_id=999))
    challenge_id, code = bind_challenge(binding, purpose="login" if continuation else "bind")
    result = (
        service.continue_login(
            challenge_id=challenge_id, code=code, flow_id=FLOW, public_username=canonical, current_password=PASSWORD
        )
        if continuation
        else submit(binding, challenge_id, code)
    )
    assert result["signup_grant_credits"] == 2000
    with sessions() as db, db.begin():
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
    challenge = issue(service)
    logged_in = service.login(challenge_id=challenge["challenge_id"], code=sender.calls[-1][1], flow_id=FLOW)
    assert logged_in["id"] == user_id and logged_in["username"] == canonical


@pytest.mark.parametrize("continuation", [False, True])
def test_ambiguous_zero_claim_profile_completion_keeps_same_account_and_never_grants(binding, continuation):
    service, sender, sessions, user_id, user_uuid = binding
    canonical = "u_" + "a" * 20
    with sessions() as db, db.begin():
        db.get(models_db.User, user_id).username = canonical
        db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type="bound_existing", user_id=999))
        db.add(
            models_db.CreditTransaction(
                user_id=user_id,
                delta=10000,
                reason="signup",
                status="committed",
                ref_id="old-account-gift",
                balance_after=10000,
            )
        )
    challenge_id, code = bind_challenge(binding, purpose="login" if continuation else "bind")
    result = (
        service.continue_login(
            challenge_id=challenge_id, code=code, flow_id=FLOW, public_username=canonical, current_password=PASSWORD
        )
        if continuation
        else submit(binding, challenge_id, code)
    )
    assert result["signup_grant_credits"] == 0
    with sessions() as db, db.begin():
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
    challenge = issue(service)
    values = dict(challenge_id=challenge["challenge_id"], code=sender.calls[-1][1], flow_id=FLOW)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        service.login(**values)
    assert caught.value.code == "profile_required"
    completed = service.continue_login(**values, public_username="真实公开名字")
    assert (completed["id"], completed["uuid"], completed["credits"], completed["signup_grant_credits"]) == (
        user_id,
        user_uuid,
        123456,
        0,
    )
    with sessions() as db:
        assert db.get(models_db.User, user_id).username == canonical
        assert db.query(models_db.CreditTransaction).count() == 1
        claim = db.get(models_db.PhoneSignupClaim, PHONE)
        assert claim.user_id == 999 and claim.grant_ref is None


def test_bind_failure_rolls_back_consumption_and_identity_but_not_reauth_budget(binding):
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)

    def reject_claim(mapper, connection, target):
        raise RuntimeError("injected binding claim failure")

    event.listen(models_db.PhoneSignupClaim, "before_insert", reject_claim)
    try:
        with pytest.raises(RuntimeError, match="injected binding claim failure"):
            submit(binding, challenge_id, code)
    finally:
        event.remove(models_db.PhoneSignupClaim, "before_insert", reject_claim)
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.get(models_db.SmsChallenge, challenge_id).state == "sent"
        assert db.get(models_db.User, user_id).credits == 123456
    assert reauth_count(sessions, user_id) == 1
    assert submit(binding, challenge_id, code)["bound"] is True


@pytest.mark.parametrize(
    "username,is_admin,hashed_password",
    [
        ("guest", False, None),
        ("admin", False, None),
        ("admin:reserved", False, None),
        ("normal-admin", True, None),
        ("shadow", False, "SHADOW_USER_NO_LOCAL_AUTH"),
    ],
)
def test_final_bind_and_challenge_reject_ineligible_actor(binding, username, is_admin, hashed_password):
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)
    with sessions() as db:
        user = db.get(models_db.User, user_id)
        user.username = username
        user.is_admin = is_admin
        if hashed_password:
            user.hashed_password = hashed_password
        db.commit()
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, code)
    assert caught.value.code == "bind_not_allowed"
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        bind_challenge(binding, phone=OTHER_PHONE)
    assert caught.value.code == "bind_not_allowed"
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == 0


def test_malformed_password_hash_fails_safely_and_counts_attempt(binding):
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)
    with sessions() as db:
        db.get(models_db.User, user_id).hashed_password = "corrupt-password-hash"
        db.commit()
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, code)
    assert caught.value.code == "bind_reauth_failed"
    assert reauth_count(sessions, user_id) == 1


@pytest.mark.parametrize("bad", ["wrong_code", "flow", "login_purpose", "other_actor", "expired"])
def test_bind_otp_is_scoped_to_challenge_flow_purpose_and_cloud_actor(binding, password_hash, bad):
    _, _, sessions, user_id, _ = binding
    if bad == "login_purpose":
        challenge_id, code = bind_challenge(binding, purpose="login")
    elif bad == "other_actor":
        with sessions() as db:
            other = models_db.User(username="other-cloud-actor", hashed_password=password_hash)
            db.add(other)
            db.commit()
            actor_id = other.id
        challenge_id, code = bind_challenge(binding, actor_id=actor_id)
    else:
        challenge_id, code = bind_challenge(binding)
    if bad == "expired":
        with sessions() as db:
            db.get(models_db.SmsChallenge, challenge_id).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(
            binding,
            challenge_id,
            "000000" if bad == "wrong_code" and code != "000000" else "999999" if bad == "wrong_code" else code,
            flow="a" * 32 if bad == "flow" else FLOW,
        )
    assert caught.value.code == (
        "invalid_code" if bad == "wrong_code" else "challenge_expired" if bad == "expired" else "challenge_invalid"
    )
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.get(models_db.SmsPhoneState, PHONE).error_count == (1 if bad == "wrong_code" else 0)
    assert reauth_count(sessions, user_id) == 1


def test_bind_wrong_code_counter_commits_and_locks_phone(binding):
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)
    wrong = "000000" if code != "000000" else "999999"
    for _ in range(4):
        with pytest.raises(phone_otp.PhoneOtpError) as caught:
            submit(binding, challenge_id, wrong)
        assert caught.value.code == "invalid_code"
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, wrong)
    assert caught.value.code == "otp_locked"
    with sessions() as db:
        assert db.get(models_db.SmsPhoneState, PHONE).error_count == 5
        assert db.get(models_db.SmsPhoneState, PHONE).blocked_until is not None
        assert db.query(models_db.PhoneIdentity).count() == 0
    assert reauth_count(sessions, user_id) == 5


def test_target_phone_conflict_is_reported_only_after_password_and_otp(binding, password_hash):
    _, _, sessions, _, _ = binding
    with sessions() as db:
        other = models_db.User(username="existing-phone-owner", hashed_password=password_hash)
        db.add(other)
        db.flush()
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=other.id))
        db.commit()
    challenge_id, code = bind_challenge(binding)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, code, password="wrong")
    assert caught.value.code == "bind_reauth_failed"
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, "000000" if code != "000000" else "999999")
    assert caught.value.code == "invalid_code"
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, code)
    assert caught.value.code == "phone_in_use"
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.get(models_db.SmsChallenge, challenge_id).state == "sent"


def test_one_user_two_phones_concurrent_submissions_bind_only_once(binding):
    _, _, sessions, user_id, _ = binding
    first = bind_challenge(binding)
    second = bind_challenge(binding, phone=OTHER_PHONE)
    barrier = Barrier(2)

    def attempt(values):
        barrier.wait()
        try:
            return submit(binding, *values)
        except phone_otp.PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, [first, second]))
    assert [result["signup_grant_credits"] for result in results if isinstance(result, dict)] == [2000]
    assert "phone_in_use" in results
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == 1
        assert db.query(models_db.CreditTransaction).one().delta == 2000
    assert reauth_count(sessions, user_id) == 2


def test_one_phone_two_users_only_active_actor_challenge_can_bind(binding, password_hash):
    _, _, sessions, _, _ = binding
    old = bind_challenge(binding)
    with sessions() as db:
        other = models_db.User(username="second-bind-actor", hashed_password=password_hash)
        db.add(other)
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        db.commit()
        other_id = other.id
    current = bind_challenge(binding, actor_id=other_id)
    barrier = Barrier(2)

    def attempt(values):
        challenge_id, code, actor_id = values
        barrier.wait()
        try:
            return submit(binding, challenge_id, code, user_id=actor_id)
        except phone_otp.PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, [(*old, binding[3]), (*current, other_id)]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "challenge_invalid" in results
    with sessions() as db:
        identity = db.query(models_db.PhoneIdentity).one()
        assert identity.user_id == other_id
        assert db.query(models_db.PhoneSignupClaim).count() == 1
        assert db.query(models_db.CreditTransaction).count() == 1


@pytest.mark.parametrize("continuation", [False, True])
@pytest.mark.parametrize(
    "reason,delta,status,expected",
    [
        ("signup", 10000, "committed", 0),
        ("signup", 100, "committed", 0),
        ("signup_grant", 5000, "committed", 0),
        ("opening_balance", 10000, "committed", 0),
        ("signup", 0, "committed", 2000),
        ("signup", 5000, "refunded", 2000),
        ("signup", 5000, "reserved", 2000),
        ("opening_balance", -100, "committed", 2000),
        ("order", 10000, "committed", 2000),
        ("admin_grant", 10000, "committed", 2000),
    ],
)
def test_binding_eligibility_uses_committed_gift_history_not_balance(
    binding, continuation, reason, delta, status, expected
):
    service, _, sessions, user_id, _ = binding
    with sessions() as db, db.begin():
        # Spending every prior credit must not restore gift eligibility.
        db.get(models_db.User, user_id).credits = 0
        db.add(
            models_db.CreditTransaction(
                user_id=user_id,
                delta=delta,
                reason=reason,
                status=status,
                ref_id="historical-gift-evidence",
                balance_after=max(0, delta),
            )
        )
    challenge_id, code = bind_challenge(binding, purpose="login" if continuation else "bind")
    result = (
        service.continue_login(
            challenge_id=challenge_id,
            code=code,
            flow_id=FLOW,
            public_username="old-canonical-owner",
            current_password=PASSWORD,
        )
        if continuation
        else submit(binding, challenge_id, code)
    )
    assert result["signup_grant_credits"] == expected
    with sessions() as db:
        assert db.get(models_db.User, user_id).credits == expected
        assert db.query(models_db.CreditTransaction).count() == (2 if expected else 1)


@pytest.mark.parametrize("continuation", [False, True])
def test_account_permanent_gift_claim_on_another_phone_blocks_repeat(binding, continuation):
    service, _, sessions, user_id, _ = binding
    with sessions() as db, db.begin():
        db.add(
            models_db.PhoneSignupClaim(
                phone_e164=OTHER_PHONE, claim_type="signup_grant", user_id=user_id, grant_ref="old-gift"
            )
        )
    challenge_id, code = bind_challenge(binding, purpose="login" if continuation else "bind")
    result = (
        service.continue_login(
            challenge_id=challenge_id,
            code=code,
            flow_id=FLOW,
            public_username="old-canonical-owner",
            current_password=PASSWORD,
        )
        if continuation
        else submit(binding, challenge_id, code)
    )
    assert result["signup_grant_credits"] == 0
    with sessions() as db:
        assert db.get(models_db.User, user_id).credits == 123456
        assert db.query(models_db.CreditTransaction).count() == 0


@pytest.mark.parametrize("continuation", [False, True])
def test_fresh_binding_with_historical_zero_claim_keeps_attribution_and_grants_once(binding, continuation):
    service, _, sessions, user_id, _ = binding
    with sessions() as db, db.begin():
        claim = models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type="bound_existing", user_id=999)
        db.add(claim)
        db.flush()
        created_at = claim.created_at
    challenge_id, code = bind_challenge(binding, purpose="login" if continuation else "bind")
    result = (
        service.continue_login(
            challenge_id=challenge_id,
            code=code,
            flow_id=FLOW,
            public_username="old-canonical-owner",
            current_password=PASSWORD,
        )
        if continuation
        else submit(binding, challenge_id, code)
    )
    assert result["signup_grant_credits"] == 2000
    with sessions() as db:
        claim = db.get(models_db.PhoneSignupClaim, PHONE)
        ledger = db.query(models_db.CreditTransaction).one()
        assert (claim.claim_type, claim.user_id, claim.created_at) == ("bound_existing", 999, created_at)
        assert claim.grant_ref == ledger.ref_id and ledger.user_id == user_id
        # Simulate deletion of the recipient; the phone receipt must survive.
        db.delete(db.query(models_db.PhoneIdentity).one())
        db.delete(ledger)
        db.delete(db.get(models_db.User, user_id))
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        db.commit()
    challenge = issue(service)
    result = service.continue_login(
        challenge_id=challenge["challenge_id"], code=binding[1].calls[-1][1], flow_id=FLOW, public_username="新的账号"
    )
    assert result["signup_grant_credits"] == 0
    with sessions() as db:
        assert db.get(models_db.PhoneSignupClaim, PHONE).user_id == 999


def test_already_bound_user_cannot_request_gift_challenge_or_retroactively_grant(binding):
    _, _, sessions, user_id, _ = binding
    challenge_id, code = bind_challenge(binding)
    with sessions() as db, db.begin():
        db.add(models_db.PhoneIdentity(phone_e164=PHONE, user_id=user_id))
        db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type="bound_existing", user_id=user_id))
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        bind_challenge(binding, phone=OTHER_PHONE)
    assert caught.value.code == "phone_in_use"
    assert submit(binding, challenge_id, code)["signup_grant_credits"] == 0
    with sessions() as db:
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.User, user_id).credits == 123456


@pytest.mark.parametrize("continuation", [False, True])
def test_binding_ledger_failure_rolls_back_identity_claim_and_gift(binding, monkeypatch, continuation):
    service, _, sessions, user_id, _ = binding
    if continuation:
        with sessions() as db, db.begin():
            db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type="bound_existing", user_id=999))
    challenge_id, code = bind_challenge(binding, purpose="login" if continuation else "bind")
    apply = billing.apply_adjustment

    def fail(*args, **kwargs):
        apply(*args, **kwargs)
        raise RuntimeError("injected gift failure")

    monkeypatch.setattr(billing, "apply_adjustment", fail)
    with pytest.raises(RuntimeError, match="injected gift failure"):
        if continuation:
            service.continue_login(
                challenge_id=challenge_id,
                code=code,
                flow_id=FLOW,
                public_username="old-canonical-owner",
                current_password=PASSWORD,
            )
        else:
            submit(binding, challenge_id, code)
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == int(continuation)
        if continuation:
            claim = db.get(models_db.PhoneSignupClaim, PHONE)
            assert claim.grant_ref is None and claim.user_id == 999
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.User, user_id).credits == 123456
        assert db.get(models_db.SmsChallenge, challenge_id).state == "sent"


@pytest.mark.parametrize("continuation", [False, True])
def test_binding_rechecks_expiry_after_account_lock_wait(binding, monkeypatch, continuation):
    service, _, sessions, user_id, _ = binding
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: now)
    challenge_id, code = bind_challenge(binding, purpose="login" if continuation else "bind")
    waiting = Event()
    engine = sessions.kw["bind"]
    gift_calls = []
    apply = billing.apply_adjustment

    def observe_gift(*args, **kwargs):
        gift_calls.append(True)
        return apply(*args, **kwargs)

    monkeypatch.setattr(billing, "apply_adjustment", observe_gift)

    def account_lock(connection, cursor, statement, parameters, context, executemany):
        if "FROM users" in statement and "FOR UPDATE" in statement:
            waiting.set()

    event.listen(engine, "before_cursor_execute", account_lock)

    def attempt():
        try:
            if continuation:
                return service.continue_login(
                    challenge_id=challenge_id,
                    code=code,
                    flow_id=FLOW,
                    public_username="old-canonical-owner",
                    current_password=PASSWORD,
                )
            return submit(binding, challenge_id, code)
        except phone_otp.PhoneOtpError as error:
            return error.code

    try:
        with sessions() as locked, ThreadPoolExecutor(max_workers=1) as workers:
            locked.execute(select(models_db.User).where(models_db.User.id == user_id).with_for_update()).scalar_one()
            waiting.clear()
            future = workers.submit(attempt)
            try:
                assert waiting.wait(10), "binding did not reach account lock"
                now += timedelta(seconds=301)
            finally:
                locked.rollback()
            assert future.result(timeout=10) == "challenge_expired"
            assert gift_calls == []
    finally:
        event.remove(engine, "before_cursor_execute", account_lock)
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.User, user_id).credits == 123456
        assert db.get(models_db.SmsChallenge, challenge_id).state == "sent"


def test_expiry_after_gift_write_rolls_back_everything(binding, monkeypatch):
    _, _, sessions, user_id, _ = binding
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: now)
    challenge_id, code = bind_challenge(binding)
    apply = billing.apply_adjustment

    def expire_after_write(*args, **kwargs):
        nonlocal now
        result = apply(*args, **kwargs)
        now += timedelta(seconds=301)
        return result

    monkeypatch.setattr(billing, "apply_adjustment", expire_after_write)
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        submit(binding, challenge_id, code)
    assert caught.value.code == "challenge_expired"
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.User, user_id).credits == 123456
        assert db.get(models_db.SmsChallenge, challenge_id).state == "sent"
