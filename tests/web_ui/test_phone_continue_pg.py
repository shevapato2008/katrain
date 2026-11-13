"""Implicit continuation and optional password setting use the existing PG identity."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import event, text

from katrain.web.core import billing, models_db, phone_otp
from katrain.web.core.auth import get_password_hash, verify_password
from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_phone_otp_limits_pg import FLOW, PHONE, issue, make_service


PASSWORD = "old-account-password-2026"
NEW_PASSWORD = "my-new-private-password-2026"
OTHER_PHONE = "+8613900000011"


@pytest.fixture(scope="module")
def password_hash():
    return get_password_hash(PASSWORD)


def proof(service, sender, phone=PHONE, flow=FLOW):
    challenge = issue(service, phone=phone, flow=flow)
    return dict(challenge_id=challenge["challenge_id"], code=sender.calls[-1][1], flow_id=flow)


def old_user(sessions, password_hash, *, username="old account.name", public_username=None, phone=None, **extra):
    with sessions() as db, db.begin():
        user = models_db.User(
            username=username,
            public_username=public_username,
            hashed_password=password_hash,
            credits=123456,
            rank="5d",
            membership_revision=7,
            **extra,
        )
        db.add(user)
        db.flush()
        if phone:
            db.add(models_db.PhoneIdentity(phone_e164=phone, user_id=user.id))
        return user.id, user.uuid


def expect_error(code, operation, *, status=None):
    with pytest.raises(phone_otp.PhoneOtpError) as caught:
        operation()
    assert caught.value.code == code
    if status is not None:
        assert caught.value.status_code == status


def test_free_name_creates_once_with_random_valid_hash_and_preserved_proof(membership_pg_engine):
    service, sender, sessions = make_service(membership_pg_engine)
    assert callable(getattr(service, "continue_login", None)), "implicit continuation service is missing"
    values = proof(service, sender)
    expect_error("profile_required", lambda: service.login(**values))
    result = service.continue_login(**values, public_username="新棋手")
    assert result["credits"] == result["signup_grant_credits"] == 5000
    assert result["public_username"] == "新棋手" and result["username"].startswith("u_")
    with sessions() as db:
        user = db.get(models_db.User, result["id"])
        assert user.uuid == result["uuid"] and user.hashed_password.startswith("$2")
        assert not any(verify_password(candidate, user.hashed_password) for candidate in ("", "otp-only", "password"))
        claim = db.query(models_db.PhoneSignupClaim).one()
        ledger = db.query(models_db.CreditTransaction).one()
        assert (claim.user_id, claim.grant_ref) == (result["id"], ledger.ref_id)
        assert (ledger.delta, ledger.reason) == (5000, "signup_grant")
    expect_error("challenge_used", lambda: service.continue_login(**values, public_username="另个名字"))


@pytest.mark.parametrize("bound_phone", [None, OTHER_PHONE])
def test_existing_login_name_requires_password_before_any_phone_conflict(
    membership_pg_engine, password_hash, bound_phone
):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, user_uuid = old_user(sessions, password_hash, phone=bound_phone)
    now = phone_otp._now()
    with sessions() as db, db.begin():
        db.add(models_db.UserGame(id="a" * 32, user_id=user_id, source="play_ai", sgf_content="(;SZ[19];B[pd])"))
        db.add(
            models_db.CreditTransaction(
                user_id=user_id, delta=123456, reason="order", ref_id="historical-ledger", balance_after=123456
            )
        )
        order = models_db.RechargeOrder(
            user_id=user_id,
            out_trade_no="historical-order",
            package_id="member",
            amount_fen=100,
            credits=0,
            provider="manual",
            status="paid",
        )
        db.add(order)
        db.flush()
        db.add(
            models_db.MembershipTerm(
                user_id=user_id,
                plan_id="member",
                starts_at=now,
                ends_at=now + timedelta(days=30),
                limit=10000,
                used=321,
                reserved=0,
                order_id=order.id,
                catalog_version="historical",
            )
        )
    values = proof(service, sender)
    with sessions() as db:
        expires = db.get(models_db.SmsChallenge, values["challenge_id"]).expires_at
    for password in (None, ""):
        expect_error(
            "account_password_required",
            lambda: service.continue_login(**values, public_username="old account.name", current_password=password),
            status=409,
        )
    expect_error(
        "bind_reauth_failed",
        lambda: service.continue_login(**values, public_username="old account.name", current_password="wrong"),
        status=401,
    )
    if bound_phone:
        expect_error(
            "phone_in_use",
            lambda: service.continue_login(**values, public_username="old account.name", current_password=PASSWORD),
            status=409,
        )
    else:
        result = service.continue_login(**values, public_username="old account.name", current_password=PASSWORD)
        assert (result["id"], result["uuid"], result["credits"], result["signup_grant_credits"]) == (
            user_id,
            user_uuid,
            123456,
            0,
        )
    with sessions() as db:
        user = db.get(models_db.User, user_id)
        assert (user.uuid, user.rank, user.membership_revision, user.hashed_password) == (
            user_uuid,
            "5d",
            7,
            password_hash,
        )
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).expires_at == expires
        assert db.query(models_db.User).count() == 1
        ledger = db.query(models_db.CreditTransaction).one()
        assert (ledger.user_id, ledger.ref_id, ledger.delta, ledger.balance_after) == (
            user_id,
            "historical-ledger",
            123456,
            123456,
        )
        game = db.query(models_db.UserGame).one()
        assert (game.user_id, game.sgf_content) == (user_id, "(;SZ[19];B[pd])")
        membership = db.query(models_db.MembershipTerm).one()
        assert (membership.user_id, membership.used, membership.limit, membership.catalog_version) == (
            user_id,
            321,
            10000,
            "historical",
        )
        bucket = db.query(models_db.SmsSendBucket).filter_by(kind="bind_reauth", key=str(user_id)).one()
        assert bucket.count == 2
        if bound_phone:
            assert db.query(models_db.PhoneIdentity).one().phone_e164 == bound_phone
            assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"
        else:
            assert db.query(models_db.PhoneIdentity).one().user_id == user_id
            assert db.query(models_db.PhoneSignupClaim).one().claim_type == "bound_existing"


def test_alias_lookup_and_ambiguity_do_not_select_or_merge_another_account(membership_pg_engine, password_hash):
    service, sender, sessions = make_service(membership_pg_engine)
    old_user(sessions, password_hash, username="old-canonical", public_username="名人")
    other_id, _ = old_user(sessions, password_hash, username="名人")
    values = proof(service, sender)
    expect_error(
        "public_username_taken",
        lambda: service.continue_login(**values, public_username="名人", current_password=PASSWORD),
    )
    with sessions() as db, db.begin():
        db.get(models_db.User, other_id).username = "another-canonical"
    result = service.continue_login(**values, public_username="名人", current_password=PASSWORD)
    assert result["username"] == "old-canonical" and result["signup_grant_credits"] == 0


@pytest.mark.parametrize(
    "username,is_admin,hashed",
    [
        ("guest", False, None),
        ("admin", False, None),
        ("admin:boss", False, None),
        ("owner", True, None),
        ("shadow", False, "SHADOW_USER_NO_LOCAL_AUTH"),
    ],
)
def test_ineligible_existing_names_cannot_bind(membership_pg_engine, password_hash, username, is_admin, hashed):
    service, sender, sessions = make_service(membership_pg_engine)
    old_user(sessions, hashed or password_hash, username=username, is_admin=is_admin)
    values = proof(service, sender)
    expect_error(
        "public_username_taken",
        lambda: service.continue_login(**values, public_username=username, current_password=PASSWORD),
    )
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == db.query(models_db.CreditTransaction).count() == 0


@pytest.mark.parametrize("collision", [False, True])
def test_legacy_completion_keeps_same_uuid_password_assets_and_no_grant(membership_pg_engine, password_hash, collision):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, user_uuid = old_user(sessions, password_hash, username="u_" + "a" * 20, phone=PHONE)
    if collision:
        old_user(sessions, password_hash, username="taken", public_username="棋手")
    values = proof(service, sender)
    if collision:
        expect_error(
            "public_username_taken",
            lambda: service.continue_login(**values, public_username="棋手", current_password=PASSWORD),
        )
    result = service.continue_login(**values, public_username="新名字")
    assert (result["id"], result["uuid"], result["signup_grant_credits"]) == (user_id, user_uuid, 0)
    with sessions() as db:
        user = db.get(models_db.User, user_id)
        assert (user.hashed_password, user.credits, user.membership_revision) == (password_hash, 123456, 7)
        assert db.query(models_db.CreditTransaction).count() == 0


@pytest.mark.parametrize("bad", ["flow", "code", "expired", "superseded", "purpose"])
def test_proof_must_be_valid_before_existing_name_or_hash_work(membership_pg_engine, password_hash, monkeypatch, bad):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, _ = old_user(sessions, password_hash)
    values = proof(service, sender)
    if bad == "flow":
        values["flow_id"] = "a" * 32
    elif bad == "code":
        values["code"] = "000000" if values["code"] != "000000" else "999999"
    else:
        with sessions() as db, db.begin():
            row = db.get(models_db.SmsChallenge, values["challenge_id"])
            if bad == "expired":
                row.expires_at -= timedelta(hours=1)
            elif bad == "purpose":
                row.purpose = "bind"
                row.bind_user_id = user_id
            else:
                db.get(models_db.SmsPhoneState, PHONE).active_challenge_id = None

    def forbidden(*args, **kwargs):
        pytest.fail("invalid proof must not start password hashing/reauthentication")

    monkeypatch.setattr(service, "_bind_reauthentication", forbidden)
    monkeypatch.setattr(phone_otp, "get_password_hash", forbidden)
    expected = "invalid_code" if bad == "code" else "challenge_expired" if bad == "expired" else "challenge_invalid"
    expect_error(
        expected,
        lambda: service.continue_login(**values, public_username="old account.name", current_password=PASSWORD),
    )
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).count() == 0
        if bad == "code":
            assert db.get(models_db.SmsPhoneState, PHONE).error_count == 1


def test_wrong_password_budget_is_persistent_across_workers(membership_pg_engine, password_hash):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, _ = old_user(sessions, password_hash)
    values = proof(service, sender)
    other, _, _ = make_service(membership_pg_engine, sender)
    for index in range(5):
        selected = service if index % 2 else other
        expect_error(
            "bind_reauth_failed",
            lambda: selected.continue_login(**values, public_username="old account.name", current_password="wrong"),
        )
    expect_error(
        "bind_reauth_locked",
        lambda: service.continue_login(**values, public_username="old account.name", current_password=PASSWORD),
    )
    with sessions() as db:
        assert db.query(models_db.SmsSendBucket).filter_by(kind="bind_reauth", key=str(user_id)).one().count == 5
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"


def test_old_claim_suppresses_grant_for_new_account(membership_pg_engine):
    service, sender, sessions = make_service(membership_pg_engine)
    with sessions() as db, db.begin():
        db.add(models_db.PhoneSignupClaim(phone_e164=PHONE, claim_type="bound_existing", user_id=999))
    result = service.continue_login(**proof(service, sender), public_username="新棋手")
    assert result["signup_grant_credits"] == result["credits"] == 0
    with sessions() as db:
        assert db.query(models_db.PhoneSignupClaim).one().user_id == 999
        assert db.query(models_db.CreditTransaction).count() == 0


@pytest.mark.parametrize("race", ["same_proof", "same_name", "same_account"])
def test_concurrent_continuations_create_or_bind_at_most_once(membership_pg_engine, password_hash, race):
    service, sender, sessions = make_service(membership_pg_engine)
    first = proof(service, sender)
    second = first if race == "same_proof" else proof(service, sender, OTHER_PHONE)
    if race == "same_account":
        old_user(sessions, password_hash, username="原账号")
    barrier = Barrier(2)

    def attempt(values):
        barrier.wait()
        try:
            return service.continue_login(
                **values,
                public_username="原账号" if race == "same_account" else "新棋手",
                current_password=PASSWORD if race == "same_account" else None,
            )
        except phone_otp.PhoneOtpError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, [first, second]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert (
        "phone_in_use"
        if race == "same_account"
        else "public_username_taken" if race == "same_name" else "challenge_used"
    ) in results
    with sessions() as db:
        assert db.query(models_db.User).count() == db.query(models_db.PhoneIdentity).count() == 1
        assert db.query(models_db.PhoneSignupClaim).count() == 1
        assert db.query(models_db.CreditTransaction).count() == (0 if race == "same_account" else 1)


def test_signup_failure_rolls_back_everything_including_proof(membership_pg_engine, monkeypatch):
    service, sender, sessions = make_service(membership_pg_engine)
    values = proof(service, sender)
    apply = billing.apply_adjustment

    def fail(*args, **kwargs):
        apply(*args, **kwargs)
        raise RuntimeError("injected rollback")

    monkeypatch.setattr(billing, "apply_adjustment", fail)
    with pytest.raises(RuntimeError, match="injected rollback"):
        service.continue_login(**values, public_username="新棋手")
    with sessions() as db:
        assert db.query(models_db.User).count() == db.query(models_db.PhoneIdentity).count() == 0
        assert db.query(models_db.PhoneSignupClaim).count() == db.query(models_db.CreditTransaction).count() == 0
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"


@pytest.mark.parametrize("change", ["hash", "name", "eligibility", "phone", "expiry"])
def test_final_binding_revalidates_after_unlocked_password_verification(
    membership_pg_engine, password_hash, monkeypatch, change
):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, _ = old_user(sessions, password_hash)
    values = proof(service, sender)
    reauth = service._bind_reauthentication

    def mutate(*args, **kwargs):
        verified = reauth(*args, **kwargs)
        with sessions() as db, db.begin():
            user = db.get(models_db.User, user_id)
            if change == "hash":
                user.hashed_password = get_password_hash("different-private-password")
            elif change == "name":
                user.username = "changed-login-name"
            elif change == "eligibility":
                user.is_admin = True
            elif change == "phone":
                db.add(models_db.PhoneIdentity(phone_e164=OTHER_PHONE, user_id=user_id))
            else:
                db.get(models_db.SmsChallenge, values["challenge_id"]).expires_at -= timedelta(hours=1)
        return verified

    monkeypatch.setattr(service, "_bind_reauthentication", mutate)
    expected = {
        "hash": "bind_reauth_failed",
        "name": "public_username_taken",
        "eligibility": "bind_not_allowed",
        "phone": "phone_in_use",
        "expiry": "challenge_expired",
    }[change]
    expect_error(
        expected,
        lambda: service.continue_login(**values, public_username="old account.name", current_password=PASSWORD),
    )
    with sessions() as db:
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"
        assert db.query(models_db.CreditTransaction).count() == 0


def test_password_setting_and_reset_keep_uuid_and_use_fresh_own_phone_proof(membership_pg_engine, password_hash):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, user_uuid = old_user(sessions, password_hash, phone=PHONE)
    values = proof(service, sender)
    assert callable(getattr(service, "set_password", None)), "optional password service is missing"
    assert service.set_password(user_id=user_id, **values, new_password=NEW_PASSWORD) is None
    expect_error("challenge_used", lambda: service.set_password(user_id=user_id, **values, new_password=PASSWORD))
    with sessions() as db, db.begin():
        user = db.get(models_db.User, user_id)
        assert (user.uuid, user.credits) == (user_uuid, 123456)
        assert verify_password(NEW_PASSWORD, user.hashed_password) and not verify_password(
            PASSWORD, user.hashed_password
        )
        assert db.query(models_db.PhoneIdentity).one().user_id == user_id
        assert db.query(models_db.CreditTransaction).count() == db.query(models_db.PhoneSignupClaim).count() == 0
        db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
    fresh = proof(service, sender)
    service.set_password(user_id=user_id, **fresh, new_password=PASSWORD)
    with sessions() as db:
        assert verify_password(PASSWORD, db.get(models_db.User, user_id).hashed_password)


@pytest.mark.parametrize("bad", ["other_phone", "guest", "expired", "invalid_password", "bind_purpose"])
def test_password_refusals_keep_current_password_and_proof(membership_pg_engine, password_hash, bad):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, _ = old_user(sessions, password_hash, username="guest" if bad == "guest" else "owner", phone=PHONE)
    values = proof(service, sender, OTHER_PHONE if bad == "other_phone" else PHONE)
    if bad in {"expired", "bind_purpose"}:
        with sessions() as db, db.begin():
            row = db.get(models_db.SmsChallenge, values["challenge_id"])
            if bad == "expired":
                row.expires_at -= timedelta(hours=1)
            else:
                row.purpose = "bind"
                row.bind_user_id = user_id
    expected = {
        "other_phone": "challenge_invalid",
        "guest": "bind_not_allowed",
        "expired": "challenge_expired",
        "invalid_password": "invalid_password",
        "bind_purpose": "challenge_invalid",
    }[bad]
    expect_error(
        expected,
        lambda: service.set_password(
            user_id=user_id, **values, new_password="short" if bad == "invalid_password" else NEW_PASSWORD
        ),
    )
    with sessions() as db:
        assert db.get(models_db.User, user_id).hashed_password == password_hash
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"


def test_password_hashing_releases_locks_then_rechecks_current_phone(membership_pg_engine, password_hash, monkeypatch):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, _ = old_user(sessions, password_hash, phone=PHONE)
    values = proof(service, sender)
    original = phone_otp.get_password_hash

    def changed_phone(password):
        with sessions() as db, db.begin():
            db.execute(text("SELECT phone_e164 FROM sms_phone_state FOR UPDATE NOWAIT")).all()
            db.execute(text("SELECT id FROM users FOR UPDATE NOWAIT")).all()
            db.query(models_db.PhoneIdentity).filter_by(user_id=user_id).one().phone_e164 = OTHER_PHONE
        return original(password)

    monkeypatch.setattr(phone_otp, "get_password_hash", changed_phone)
    expect_error(
        "challenge_invalid", lambda: service.set_password(user_id=user_id, **values, new_password=NEW_PASSWORD)
    )
    with sessions() as db:
        assert db.get(models_db.User, user_id).hashed_password == password_hash
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"


def test_implicit_signup_rechecks_expiry_after_unlocked_hashing(membership_pg_engine, monkeypatch):
    service, sender, sessions = make_service(membership_pg_engine)
    values = proof(service, sender)
    hash_password = phone_otp.get_password_hash

    def expire(password):
        with sessions() as db, db.begin():
            db.execute(text("SELECT phone_e164 FROM sms_phone_state FOR UPDATE NOWAIT")).all()
            db.get(models_db.SmsChallenge, values["challenge_id"]).expires_at -= timedelta(hours=1)
        return hash_password(password)

    monkeypatch.setattr(phone_otp, "get_password_hash", expire)
    expect_error("challenge_expired", lambda: service.continue_login(**values, public_username="新棋手"))
    with sessions() as db:
        assert db.query(models_db.User).count() == db.query(models_db.PhoneSignupClaim).count() == 0
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"


def test_password_database_failure_rolls_back_hash_and_consumption(membership_pg_engine, password_hash):
    service, sender, sessions = make_service(membership_pg_engine)
    user_id, _ = old_user(sessions, password_hash, phone=PHONE)
    values = proof(service, sender)

    def fail_after_password(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE users SET hashed_password="):
            raise RuntimeError("injected password failure")

    event.listen(membership_pg_engine, "after_cursor_execute", fail_after_password)
    try:
        with pytest.raises(RuntimeError, match="injected password failure"):
            service.set_password(user_id=user_id, **values, new_password=NEW_PASSWORD)
    finally:
        event.remove(membership_pg_engine, "after_cursor_execute", fail_after_password)
    with sessions() as db:
        assert db.get(models_db.User, user_id).hashed_password == password_hash
        assert db.get(models_db.SmsChallenge, values["challenge_id"]).state == "sent"
