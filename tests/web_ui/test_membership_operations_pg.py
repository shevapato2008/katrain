"""The membership ledger is exercised against isolated, real PostgreSQL schemas."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import partial
from threading import Barrier

import pytest
from sqlalchemy.orm import sessionmaker as sqlalchemy_sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from katrain.web.core import models_db as m

NOW = datetime(2026, 11, 2, 3, tzinfo=timezone.utc)
SECRET = "membership-operation-test-signing-secret"
# Match core.db.SessionLocal: correctness may not depend on query-triggered flushes.
sessionmaker = partial(sqlalchemy_sessionmaker, autoflush=False)


def services():
    from katrain.web.core import billing_operations as ops, membership

    return ops, membership


def seed(engine, *, credits=0, member=False, remaining=1, username="member"):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session.begin() as db:
        u = m.User(username=username, hashed_password="x", credits=credits)
        db.add(u)
        db.flush()
        if member:
            order = m.RechargeOrder(
                user_id=u.id,
                out_trade_no=username,
                package_id="plus",
                amount_fen=3900,
                credits=0,
                provider="manual",
                status="paid",
            )
            db.add(order)
            db.flush()
            db.add(
                m.MembershipTerm(
                    user_id=u.id,
                    plan_id="plus",
                    starts_at=NOW - timedelta(days=1),
                    ends_at=NOW + timedelta(days=29),
                    limit=9030,
                    used=9030 - remaining,
                    reserved=0,
                    order_id=order.id,
                    catalog_version="membership_20261102_v1",
                )
            )
        return u.id


def quote(db, uid, *, units=1, kind="position", fingerprint="a" * 64, profile="normal", **kw):
    ops, _ = services()
    return ops.quote_operation(
        db,
        user_id=uid,
        now=NOW,
        kind=kind,
        fingerprint=fingerprint,
        profile=profile,
        units=units,
        environment="test",
        secret=SECRET,
        **kw,
    )


def reserve(
    db, uid, token, *, key="operation", units=1, kind="position", fingerprint="a" * 64, profile="normal", now=NOW, **kw
):
    ops, _ = services()
    return ops.reserve_operation_in_transaction(
        db,
        user_id=uid,
        now=now,
        kind=kind,
        fingerprint=fingerprint,
        profile=profile,
        units=units,
        environment="test",
        secret=SECRET,
        quote_token=token,
        idempotency_key=key,
        **kw,
    )


@pytest.mark.parametrize("member", [False, True])
def test_last_unit_competition_never_overdraws(membership_pg_engine, member):
    engine = membership_pg_engine
    uid = seed(engine, credits=0 if member else 2, member=member, remaining=2)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        tokens = [quote(db, uid)["token"], quote(db, uid, kind="report", units=2)["token"]]
    barrier = Barrier(2)

    def attempt(index):
        with Session() as db:
            barrier.wait()
            try:
                op = reserve(
                    db, uid, tokens[index], key=str(index), kind="position" if index == 0 else "report", units=index + 1
                )
                db.commit()
                return op.id
            except Exception as exc:
                db.rollback()
                from katrain.web.core.billing_operations import MembershipError

                assert isinstance(exc, MembershipError)
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(isinstance(r, int) for r in results) == 1
    with Session() as db:
        assert db.query(m.BillingOperation).count() == 1
        if member:
            term = db.query(m.MembershipTerm).one()
            assert term.used + term.reserved <= term.limit
            assert term.reserved in (1, 2)
        else:
            assert db.get(m.User, uid).credits in (0, 1)


def test_window_shortage_falls_back_entirely_to_wallet(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=8, member=True, remaining=3)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        q = quote(db, uid, units=4, profile="advanced")
        op = reserve(db, uid, q["token"], units=4, profile="advanced")
        assert op.source == "wallet"
        assert db.query(m.MembershipTerm).one().reserved == 0
        assert db.get(m.User, uid).credits == 4
        assert db.query(m.QuotaBucket).count() == 0


def test_idempotency_replays_before_expired_quote_and_conflicts_on_content(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=5)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        token = quote(db, uid)["token"]
        op = reserve(db, uid, token)
        ident = op.id
    with Session.begin() as db:
        assert reserve(db, uid, token, now=NOW + timedelta(minutes=5)).id == ident
        with pytest.raises(ops.MembershipError, match="idempotency_conflict"):
            reserve(db, uid, token, fingerprint="b" * 64)
        assert db.get(m.User, uid).credits == 4


def test_cross_account_last_global_position_slot(membership_pg_engine):
    ops, _ = services()
    engine = membership_pg_engine
    users = [seed(engine, credits=10, username=f"u{i}") for i in range(2)]
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        tokens = [quote(db, uid)["token"] for uid in users]
    barrier = Barrier(2)

    def attempt(i):
        with Session() as db:
            barrier.wait()
            try:
                op = reserve(db, users[i], tokens[i], position_queue_limit=1)
                db.commit()
                return op.user_id, op.id
            except ops.MembershipError as exc:
                db.rollback()
                assert exc.code == "queue_full"

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [x for x in pool.map(attempt, range(2)) if x]
    assert len(winners) == 1
    uid, ident = winners[0]
    with Session.begin() as db:
        ops.commit_operation_in_transaction(
            db, user_id=uid, operation_id=ident, now=NOW, generation=0, result={"ok": True}
        )
    other = users[1] if uid == users[0] else users[0]
    with Session.begin() as db:
        reserve(db, other, tokens[users.index(other)], position_queue_limit=1)


def test_crash_reconcile_refunds_once_and_fences_late_completion(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        op = reserve(db, uid, quote(db, uid)["token"])
        ident = op.id
    later = NOW + timedelta(seconds=100)
    with Session.begin() as db:
        assert ops.reconcile_expired_positions(db, now=later) == 1
    with Session.begin() as db:
        assert ops.reconcile_expired_positions(db, now=later) == 0
        assert db.get(m.User, uid).credits == 10
        assert db.get(m.BillingOperation, ident).generation == 1
        with pytest.raises(ops.MembershipError, match="stale_generation"):
            ops.commit_operation_in_transaction(db, user_id=uid, operation_id=ident, now=later, generation=0, result={})


def test_free_requires_trusted_verification_and_usage_is_read_only(membership_pg_engine):
    ops, membership = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        usage = membership.usage_snapshot(db, user_id=uid, now=NOW, environment="test", payments_mode="test")
        assert usage["free"]["eligible"] is False
        assert usage["free"]["reason"] == "verification_required"
        assert db.query(m.QuotaBucket).count() == 0
        with pytest.raises(ops.MembershipError):
            quote(db, uid, kind="report", units=2)
        q = quote(db, uid, kind="report", units=2, trusted_free_eligible=True)
        op = reserve(db, uid, q["token"], kind="report", units=2, trusted_free_eligible=True)
        assert op.source == "free_report"
        assert membership.can_claim_free_report(db, user_id=uid, now=NOW, trusted_free_eligible=True)[0] is False


def test_refund_returns_to_original_week_and_term(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, member=True, remaining=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        op = reserve(db, uid, quote(db, uid)["token"])
        ident, bucket = op.id, op.week_bucket_id
    with Session.begin() as db:
        ops.refund_operation_in_transaction(db, user_id=uid, operation_id=ident, now=NOW + timedelta(days=40))
        assert db.get(m.QuotaBucket, bucket).reserved == 0
        assert db.query(m.QuotaBucket).count() == 1
        assert db.query(m.MembershipTerm).one().reserved == 0


def test_week_shortage_does_not_partially_reserve_term(membership_pg_engine):
    ops, membership = services()
    uid = seed(membership_pg_engine, credits=8, member=True, remaining=8)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        key, start, end = membership.week_window(NOW)
        db.add(
            m.QuotaBucket(
                user_id=uid,
                kind=membership.WEEK_KIND,
                period_key=key,
                allowance=3010,
                used=3008,
                reserved=0,
                starts_at=start,
                ends_at=end,
            )
        )
    with Session.begin() as db:
        q = quote(db, uid, units=4, profile="advanced")
        op = reserve(db, uid, q["token"], units=4, profile="advanced")
        assert op.source == "wallet"
        assert db.query(m.MembershipTerm).one().reserved == 0
        assert db.query(m.QuotaBucket).one().reserved == 0


def test_membership_quote_fallback_obeys_signed_cap(membership_pg_engine):
    uid = seed(membership_pg_engine, credits=1, member=True, remaining=2)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        q = quote(db, uid)
        report = quote(db, uid, kind="report", units=2, fingerprint="b" * 64)
        reserve(db, uid, report["token"], kind="report", units=2, key="report", fingerprint="b" * 64)
        op = reserve(db, uid, q["token"], wallet_max_credits=999999)
        assert op.source == "wallet" and db.get(m.User, uid).credits == 0


def test_transaction_rollback_restores_operation_wallet_and_revision(membership_pg_engine):
    uid = seed(membership_pg_engine, credits=3)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session() as db:
        reserve(db, uid, quote(db, uid)["token"])
        db.rollback()
    with Session() as db:
        assert db.get(m.User, uid).credits == 3
        assert db.get(m.User, uid).membership_revision == 0
        assert db.query(m.BillingOperation).count() == db.query(m.CreditTransaction).count() == 0


def test_completed_receipt_expiry_cannot_rerun_old_key(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=3)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        token = quote(db, uid)["token"]
        op = reserve(db, uid, token)
        ident = op.id
        ops.commit_operation_in_transaction(
            db, user_id=uid, operation_id=ident, now=NOW, generation=0, result={"ok": True}
        )
    later = NOW + timedelta(hours=25)
    with Session.begin() as db:
        ops.reconcile_expired_positions(db, now=later)
        assert db.get(m.BillingOperation, ident).result is None
        with pytest.raises(ops.MembershipError, match="result_expired"):
            reserve(db, uid, token, now=later)
        assert db.get(m.User, uid).credits == 2


def test_paused_rejects_new_authorization_but_settles_reserved(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=2)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        token = quote(db, uid)["token"]
        op = reserve(db, uid, token)
        assert reserve(db, uid, token, membership_mode="paused").id == op.id
        with pytest.raises(ops.MembershipError, match="membership_paused"):
            reserve(db, uid, token, key="new", membership_mode="paused")
        ops.refund_operation_in_transaction(db, user_id=uid, operation_id=op.id, now=NOW)
        assert db.get(m.User, uid).credits == 2


def test_new_wallet_ledger_is_not_refunded_by_legacy_ttl(membership_pg_engine):
    from katrain.web.core import billing

    uid = seed(membership_pg_engine, credits=3)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        op = reserve(db, uid, quote(db, uid, kind="report", units=2)["token"], kind="report", units=2)
        ref = op.wallet_ref
        db.query(m.CreditTransaction).filter_by(ref_id=ref).one().created_at = NOW - timedelta(days=30)
    with Session() as db:
        assert billing.reconcile_stale_reservations(db, ttl_seconds=1) == 0
        assert billing.transaction_status(db, ref) == "reserved"


def test_legacy_deleted_free_fact_blocks_claim_without_inventing_units(membership_pg_engine):
    ops, membership = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        key, _, _ = membership.week_window(NOW)
        db.add(m.QuotaBucket(user_id=uid, kind="free_report", period_key=key, allowance=1, used=1, reserved=0))
    with Session() as db:
        assert membership.legacy_free_facts(db, user_id=uid, now=NOW) == (True, 0)
        assert membership.can_claim_free_report(db, user_id=uid, now=NOW, trusted_free_eligible=True)[0] is False


def test_free_completed_units_carry_into_membership_week_but_not_new_term(membership_pg_engine):
    ops, membership = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        q = quote(db, uid, kind="report", units=2, trusted_free_eligible=True)
        op = reserve(db, uid, q["token"], kind="report", units=2, trusted_free_eligible=True)
        ops.commit_operation_in_transaction(db, user_id=uid, operation_id=op.id, now=NOW, result={"ok": True})
        order = m.RechargeOrder(
            user_id=uid,
            out_trade_no="purchase",
            package_id="plus",
            amount_fen=3900,
            credits=0,
            provider="manual",
            status="paid",
        )
        db.add(order)
        db.flush()
        term = membership.create_term_in_transaction(db, user_id=uid, plan_id="plus", order_id=order.id, now=NOW)
        assert term.used == term.reserved == 0
        usage = membership.usage_snapshot(
            db, user_id=uid, now=NOW, environment="test", payments_mode="test", trusted_free_eligible=True
        )
        assert usage["week"]["used"] == 2 and usage["free"]["eligible"] is False


def test_renewal_terms_are_fixed_thirty_days_and_never_overlap(membership_pg_engine):
    _, membership = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        terms = []
        for i in range(3):
            order = m.RechargeOrder(
                user_id=uid,
                out_trade_no=f"buy{i}",
                package_id="plus",
                amount_fen=3900,
                credits=0,
                provider="manual",
                status="paid",
            )
            db.add(order)
            db.flush()
            terms.append(
                membership.create_term_in_transaction(db, user_id=uid, plan_id="plus", order_id=order.id, now=NOW)
            )
        assert all(t.ends_at - t.starts_at == timedelta(days=30) for t in terms)
        assert terms[0].ends_at == terms[1].starts_at and terms[1].ends_at == terms[2].starts_at


def test_report_owned_result_survives_day_but_requires_actual_task_and_game(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=6)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        game = m.UserGame(user_id=uid, source="import", sgf_content="(;SZ[19];B[aa])")
        db.add(game)
        db.flush()
        q = quote(db, uid, kind="report", units=2)
        op = reserve(db, uid, q["token"], kind="report", units=2, game_id=game.id)
        task = m.ReportTask(
            user_id=uid,
            user_game_id=game.id,
            status="completed",
            operation_id=op.id,
            report_type="normal",
            requested_visits=500,
            model_sha256=op.model_sha256,
            generation=0,
        )
        db.add(task)
        db.flush()
        op.task_id = task.id
        db.flush()
        ops.commit_operation_in_transaction(db, user_id=uid, operation_id=op.id, now=NOW)
        ident = op.id
        assert op.result_expires_at is None
    with Session.begin() as db:
        later = NOW + timedelta(days=2)
        q = ops.quote_operation(
            db,
            user_id=uid,
            now=later,
            kind="report",
            fingerprint="a" * 64,
            profile="normal",
            units=2,
            environment="test",
            secret=SECRET,
        )
        assert q["source"] == "owned"
        alias = reserve(db, uid, q["token"], kind="report", units=2, key="another", now=later)
        assert alias.source == "owned" and alias.idempotency_key == "another"
        assert ops.resolve_owned_operation(db, alias).id == ident
        db.query(m.ReportTask).delete()
        q = ops.quote_operation(
            db,
            user_id=uid,
            now=later,
            kind="report",
            fingerprint="a" * 64,
            profile="normal",
            units=2,
            environment="test",
            secret=SECRET,
        )
        assert q["source"] == "wallet"


def test_legacy_free_units_use_legal_sgf_and_survive_upgrade(membership_pg_engine):
    _, membership = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        key, _, _ = membership.week_window(NOW)
        db.add(m.QuotaBucket(user_id=uid, kind="free_report", period_key=key, allowance=1, used=1, reserved=0))
        game = m.UserGame(user_id=uid, source="import", sgf_content="(;SZ[19];B[aa];W[bb])", move_count=400)
        bad = m.UserGame(user_id=uid, source="import", sgf_content="(;SZ[19];B[zz])", move_count=400)
        db.add_all([game, bad])
        db.flush()
        db.add_all(
            [
                m.ReportTask(user_id=uid, user_game_id=g.id, free_grant_period=key, status="completed", total_moves=400)
                for g in (game, bad)
            ]
        )
    with Session.begin() as db:
        assert membership.legacy_free_facts(db, user_id=uid, now=NOW) == (True, 3)
        order = m.RechargeOrder(
            user_id=uid,
            out_trade_no="upgrade",
            package_id="plus",
            amount_fen=3900,
            credits=0,
            provider="manual",
            status="paid",
        )
        db.add(order)
        db.flush()
        term = membership.create_term_in_transaction(db, user_id=uid, plan_id="plus", order_id=order.id, now=NOW)
        bucket = membership.ensure_week_bucket_in_transaction(db, user_id=uid, now=NOW, allowance=3010)
        assert bucket.used == 3 and term.used == 0


def test_successful_member_reports_consume_free_eligibility_after_term_expires(membership_pg_engine):
    ops, membership = services()
    uid = seed(membership_pg_engine, member=True, remaining=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        db.query(m.MembershipTerm).one().ends_at = NOW + timedelta(minutes=1)
        db.flush()
        op = reserve(db, uid, quote(db, uid, kind="report", units=2)["token"], kind="report", units=2)
        ops.commit_operation_in_transaction(db, user_id=uid, operation_id=op.id, now=NOW)
    with Session() as db:
        eligible, reason = membership.can_claim_free_report(
            db, user_id=uid, now=NOW + timedelta(hours=1), trusted_free_eligible=True
        )
        assert eligible is False and reason == "weekly_report_used"


def test_failed_free_report_releases_original_week_without_granting_wallet(membership_pg_engine):
    ops, membership = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        q = quote(db, uid, kind="report", units=2, trusted_free_eligible=True)
        op = reserve(db, uid, q["token"], kind="report", units=2, trusted_free_eligible=True)
        ident, bucket = op.id, op.week_bucket_id
    with Session.begin() as db:
        ops.refund_operation_in_transaction(db, user_id=uid, operation_id=ident, now=NOW + timedelta(days=8))
        assert db.get(m.QuotaBucket, bucket).reserved == 0
        assert membership.can_claim_free_report(db, user_id=uid, now=NOW, trusted_free_eligible=True)[0] is True
        assert db.get(m.User, uid).credits == 0


def test_report_last_global_slot_counts_legacy_tasks(membership_pg_engine):
    ops, _ = services()
    first = seed(membership_pg_engine, credits=5, username="first")
    second = seed(membership_pg_engine, credits=5, username="second")
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        game = m.UserGame(user_id=first, source="import", sgf_content="(;SZ[19];B[aa])")
        db.add(game)
        db.flush()
        db.add(m.ReportTask(user_id=first, user_game_id=game.id, status="authorizing"))
    with Session.begin() as db:
        q = quote(db, second, kind="report", units=2)
        with pytest.raises(ops.MembershipError, match="queue_full"):
            reserve(db, second, q["token"], kind="report", units=2, report_queue_limit=1)
        assert db.get(m.User, second).credits == 5
        assert db.query(m.BillingOperation).count() == 0


def test_deleted_owned_result_requires_fresh_price_acceptance(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=3, member=True, remaining=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        op = reserve(db, uid, quote(db, uid)["token"])
        ops.commit_operation_in_transaction(db, user_id=uid, operation_id=op.id, now=NOW, result={"ok": True})
        q = quote(db, uid)
        assert q["source"] == "owned"
        op.result = None
    with Session.begin() as db:
        with pytest.raises(ops.MembershipError, match="owned_result_unavailable"):
            reserve(db, uid, q["token"], key="new")
        assert db.query(m.MembershipTerm).one().reserved == 0


def test_legacy_terminal_task_with_unsettled_wallet_blocks_new_auth(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=5)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        game = m.UserGame(user_id=uid, source="import", sgf_content="(;SZ[19];B[aa])")
        db.add(game)
        db.flush()
        db.add(m.ReportTask(user_id=uid, user_game_id=game.id, status="completed", charge_ref="old-report"))
        db.add(
            m.CreditTransaction(
                user_id=uid, reason="report", delta=-1, ref_id="old-report", status="reserved", balance_after=5
            )
        )
    with Session.begin() as db:
        with pytest.raises(ops.MembershipError, match="legacy_report_in_progress"):
            reserve(db, uid, quote(db, uid)["token"])
        assert db.query(m.BillingOperation).count() == 0


@pytest.mark.parametrize("status", ["pending", "paid"])
def test_legacy_settle_order_cannot_fulfill_versioned_order(membership_pg_engine, status):
    from katrain.web.core import billing

    uid = seed(membership_pg_engine, credits=5)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        db.add(
            m.RechargeOrder(
                user_id=uid,
                out_trade_no="versioned",
                package_id="plus",
                amount_fen=3900,
                credits=9000,
                provider="manual",
                status=status,
                catalog_version="membership_20261102_v1",
            )
        )
    with Session() as db:
        with pytest.raises(billing.BillingError, match="versioned_order_requires_payment_service"):
            billing.settle_order(db, "versioned")
        assert db.get(m.User, uid).credits == 5
        assert db.query(m.CreditTransaction).count() == 0


def test_owned_reuse_key_also_gets_durable_expiring_receipt(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=3)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        original = reserve(db, uid, quote(db, uid)["token"])
        ops.commit_operation_in_transaction(db, user_id=uid, operation_id=original.id, now=NOW, result={"ok": True})
        reused = reserve(db, uid, quote(db, uid)["token"], key="reused")
        assert reused.idempotency_key == "reused"
        assert db.get(m.User, uid).credits == 2
    later = NOW + timedelta(hours=25)
    with Session.begin() as db:
        fresh = ops.quote_operation(
            db,
            user_id=uid,
            now=later,
            kind="position",
            fingerprint="a" * 64,
            profile="normal",
            units=1,
            environment="test",
            secret=SECRET,
        )
        with pytest.raises(ops.MembershipError, match="result_expired"):
            reserve(db, uid, fresh["token"], key="reused", now=later)
        assert db.get(m.User, uid).credits == 2


@pytest.mark.parametrize("trusted_at_execution", [False, None])
def test_free_quote_losing_verification_cannot_fall_back_to_wallet(membership_pg_engine, trusted_at_execution):
    from katrain.web.core.billing_quotes import verify_quote

    ops, _ = services()
    uid = seed(membership_pg_engine, credits=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session() as db:
        accepted = quote(db, uid, kind="report", units=2, trusted_free_eligible=True)
        payload = verify_quote(accepted["token"], secret=SECRET, now=NOW, user_id=uid, environment="test")
        assert payload["free_eligibility_policy"] == "trusted_identity_v1"
    with Session.begin() as db:
        with pytest.raises(ops.MembershipError, match="verification_required") as error:
            reserve(db, uid, accepted["token"], kind="report", units=2, trusted_free_eligible=trusted_at_execution)
        assert error.value.status_code == 403
        assert db.get(m.User, uid).credits == 10
        assert db.query(m.BillingOperation).count() == db.query(m.CreditTransaction).count() == 0


def test_verified_free_quote_can_fall_back_when_only_weekly_claim_was_used(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        accepted = quote(db, uid, kind="report", units=2, trusted_free_eligible=True)
        other = quote(db, uid, kind="report", units=2, fingerprint="b" * 64, trusted_free_eligible=True)
        free = reserve(
            db,
            uid,
            other["token"],
            kind="report",
            units=2,
            fingerprint="b" * 64,
            key="first",
            trusted_free_eligible=True,
        )
        ops.commit_operation_in_transaction(db, user_id=uid, operation_id=free.id, now=NOW)
        paid = reserve(db, uid, accepted["token"], kind="report", units=2, key="second", trusted_free_eligible=True)
        assert paid.source == "wallet" and db.get(m.User, uid).credits == 8


def test_stale_session_refreshes_term_and_week_before_reserving(membership_pg_engine):
    _, membership = services()
    uid = seed(membership_pg_engine, member=True, remaining=10)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    with Session.begin() as db:
        membership.ensure_week_bucket_in_transaction(db, user_id=uid, now=NOW, allowance=3010)
        position_token = quote(db, uid)["token"]
        report_token = quote(db, uid, kind="report", units=2, fingerprint="b" * 64)["token"]
    with Session() as stale:
        cached_term = stale.query(m.MembershipTerm).filter_by(user_id=uid).one()
        cached_bucket = membership.week_bucket(stale, user_id=uid, now=NOW)
        with Session.begin() as fresh:
            reserve(fresh, uid, report_token, kind="report", units=2, fingerprint="b" * 64, key="report")
        reserve(stale, uid, position_token, key="position")
        stale.commit()
        assert cached_term.reserved == cached_bucket.reserved == 3
    with Session() as db:
        assert sum(op.units for op in db.query(m.BillingOperation).all()) == 3
        assert db.query(m.MembershipTerm).one().reserved == db.query(m.QuotaBucket).one().reserved == 3


def test_stale_membership_source_is_recomputed_before_wallet_fallback(membership_pg_engine):
    _, membership = services()
    uid = seed(membership_pg_engine, member=True, remaining=2, credits=1)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    with Session.begin() as db:
        membership.ensure_week_bucket_in_transaction(db, user_id=uid, now=NOW, allowance=3010)
        position_token = quote(db, uid)["token"]
        report_token = quote(db, uid, kind="report", units=2, fingerprint="b" * 64)["token"]
    with Session() as stale:
        cached_term = stale.query(m.MembershipTerm).filter_by(user_id=uid).one()
        cached_bucket = membership.week_bucket(stale, user_id=uid, now=NOW)
        with Session.begin() as fresh:
            reserve(fresh, uid, report_token, kind="report", units=2, fingerprint="b" * 64, key="report")
        position = reserve(stale, uid, position_token, key="position")
        assert position.source == "wallet"
        stale.commit()
        assert cached_term.reserved == cached_bucket.reserved == 2
    with Session() as db:
        assert db.get(m.User, uid).credits == 0


@pytest.mark.parametrize("action", ["commit", "refund"])
def test_stale_session_refreshes_term_week_before_settlement(membership_pg_engine, action):
    ops, membership = services()
    uid = seed(membership_pg_engine, member=True, remaining=10)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    with Session.begin() as db:
        position = reserve(db, uid, quote(db, uid)["token"], key="position")
        report = reserve(
            db,
            uid,
            quote(db, uid, kind="report", units=2, fingerprint="b" * 64)["token"],
            kind="report",
            units=2,
            fingerprint="b" * 64,
            key="report",
        )
        position_id, report_id = position.id, report.id
    with Session() as stale:
        cached_term = stale.query(m.MembershipTerm).filter_by(user_id=uid).one()
        cached_bucket = membership.week_bucket(stale, user_id=uid, now=NOW)
        with Session.begin() as fresh:
            ops.commit_operation_in_transaction(fresh, user_id=uid, operation_id=report_id, now=NOW)
        settle = ops.commit_operation_in_transaction if action == "commit" else ops.refund_operation_in_transaction
        settle(stale, user_id=uid, operation_id=position_id, now=NOW)
        stale.commit()
        assert cached_term.reserved == cached_bucket.reserved == 0
        assert cached_term.used == 9020 + (3 if action == "commit" else 2)
        assert cached_bucket.used == (3 if action == "commit" else 2)


@pytest.mark.parametrize("action", ["commit", "refund"])
def test_stale_wallet_primitive_cannot_reopen_or_refund_closed_credit(membership_pg_engine, action):
    from katrain.web.core import billing

    ops, _ = services()
    uid = seed(membership_pg_engine, credits=10)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    with Session.begin() as db:
        operation = reserve(db, uid, quote(db, uid)["token"])
        ident, ref = operation.id, operation.wallet_ref
    with Session() as stale:
        cached_tx = stale.query(m.CreditTransaction).filter_by(ref_id=ref).one()
        with Session.begin() as fresh:
            ops.refund_operation_in_transaction(fresh, user_id=uid, operation_id=ident, now=NOW)
        ops._user(stale, uid)
        settle = billing.commit_in_transaction if action == "commit" else billing.refund_in_transaction
        assert settle(stale, user_id=uid, ref_id=ref, now=NOW) == 10
        stale.commit()
        assert cached_tx.status == "refunded"


@pytest.mark.parametrize("lookup", ["existing", "tail"])
def test_term_creation_refreshes_cached_tail_before_scheduling(membership_pg_engine, lookup):
    ops, membership = services()
    uid = seed(membership_pg_engine, member=True, remaining=10)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    extended_end = NOW + timedelta(days=40)
    with Session() as stale:
        cached_tail = stale.query(m.MembershipTerm).filter_by(user_id=uid).one()
        with Session.begin() as fresh:
            ops._user(fresh, uid)
            fresh.query(m.MembershipTerm).filter_by(user_id=uid).with_for_update().one().ends_at = extended_end
        ops._user(stale, uid)
        if lookup == "existing":
            existing = membership.create_term_in_transaction(
                stale, user_id=uid, plan_id="plus", order_id=cached_tail.order_id, now=NOW
            )
            assert existing.ends_at == extended_end
            return
        order = m.RechargeOrder(
            user_id=uid,
            out_trade_no="renew-after-extension",
            package_id="plus",
            amount_fen=3900,
            credits=0,
            provider="manual",
            status="paid",
        )
        stale.add(order)
        stale.flush()
        term = membership.create_term_in_transaction(stale, user_id=uid, plan_id="plus", order_id=order.id, now=NOW)
        assert term.starts_at == extended_end
        assert cached_tail.ends_at == extended_end


def test_owned_receipt_refreshes_cached_operation_after_other_session_commit(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=10)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    with Session.begin() as db:
        ident = reserve(db, uid, quote(db, uid)["token"]).id
    with Session() as stale:
        cached = stale.get(m.BillingOperation, ident)
        assert cached.status == "reserved" and cached.result is None
        with Session.begin() as fresh:
            ops.commit_operation_in_transaction(fresh, user_id=uid, operation_id=ident, now=NOW, result={"ok": True})
        alias = reserve(stale, uid, "", key="owned-after-commit")
        assert alias.source == "owned" and alias.result == {"ok": True}


def test_reconcile_persists_generation_with_runtime_autoflush_disabled(membership_pg_engine):
    ops, _ = services()
    uid = seed(membership_pg_engine, credits=10)
    Session = sessionmaker(bind=membership_pg_engine, autoflush=False)
    with Session.begin() as db:
        ident = reserve(db, uid, quote(db, uid)["token"]).id
    with Session.begin() as db:
        assert ops.reconcile_expired_positions(db, now=NOW + timedelta(seconds=100)) == 1
    with Session() as db:
        op = db.get(m.BillingOperation, ident)
        assert op.status == "refunded" and db.get(m.User, uid).credits == 10
        assert op.generation == 1


def frozen_plus_snapshot():
    return {
        "sku": "membership_plus",
        "kind": "membership",
        "plan_code": "plus",
        "amount_fen": 3900,
        "credits": 0,
        "term_days": 30,
        "term_units": 9030,
        "week_units": 3010,
    }


def test_frozen_pending_membership_fulfills_after_plan_is_retired(membership_pg_engine, monkeypatch):
    from katrain.web.core.billing_catalog import CATALOG_VERSION, PLANS

    ops, membership = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        order = m.RechargeOrder(
            user_id=uid,
            out_trade_no="frozen-pending",
            package_id="membership_plus",
            amount_fen=3900,
            credits=0,
            provider="mock",
            status="pending",
            catalog_version=CATALOG_VERSION,
            sku_snapshot=frozen_plus_snapshot(),
            environment="test",
        )
        db.add(order)
        db.flush()
        order_id = order.id
    monkeypatch.setitem(PLANS, "plus", {**PLANS["plus"], "sellable": False, "term_units": 1})
    with Session.begin() as db:
        ops._user(db, uid)
        db.query(m.RechargeOrder).filter_by(id=order_id, user_id=uid).with_for_update().populate_existing().one()
        term = membership.create_term_in_transaction(db, user_id=uid, plan_id="plus", order_id=order_id, now=NOW)
        assert term.limit == 9030 and term.ends_at - term.starts_at == timedelta(days=30)
        assert term.catalog_version == CATALOG_VERSION


def test_frozen_week_units_drive_usage_quote_and_reservation_after_catalog_change(membership_pg_engine, monkeypatch):
    from katrain.web.core.billing_catalog import CATALOG_VERSION, PLANS

    _, membership = services()
    uid = seed(membership_pg_engine, member=True, remaining=10, credits=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        order = db.query(m.RechargeOrder).filter_by(user_id=uid).one()
        order.catalog_version, order.sku_snapshot, order.package_id = (
            CATALOG_VERSION,
            frozen_plus_snapshot(),
            "membership_plus",
        )
    monkeypatch.setitem(PLANS, "plus", {**PLANS["plus"], "week_units": 1})
    with Session.begin() as db:
        usage = membership.usage_snapshot(db, user_id=uid, now=NOW, environment="test", payments_mode="mock")
        assert usage["week"]["limit"] == 3010
        q = quote(db, uid, units=4, profile="advanced")
        assert q["source"] == "membership"
        op = reserve(db, uid, q["token"], units=4, profile="advanced")
        assert op.source == "membership" and db.get(m.User, uid).credits == 10
        assert db.query(m.QuotaBucket).one().allowance == 3010


def test_versioned_term_missing_frozen_snapshot_never_uses_current_catalog(membership_pg_engine):
    from katrain.web.core.billing_catalog import CATALOG_VERSION

    _, membership = services()
    uid = seed(membership_pg_engine, member=True, remaining=10, credits=10)
    Session = sessionmaker(bind=membership_pg_engine)
    with Session.begin() as db:
        db.query(m.RechargeOrder).filter_by(user_id=uid).one().catalog_version = CATALOG_VERSION
    with Session() as db:
        with pytest.raises(ValueError, match="invalid_membership_order_snapshot"):
            membership.usage_snapshot(db, user_id=uid, now=NOW, environment="test", payments_mode="mock")
        assert db.get(m.User, uid).credits == 10
