"""终态结算 + 通用 TTL 回收器不得碰复盘预扣。"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _user(db, credits=1000):
    u = models_db.User(username="u1", hashed_password="x", credits=credits)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _task(db, user, *, status, total, analyzed, reserve):
    g = models_db.UserGame(user_id=user.id, source="import", move_count=total)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=user.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status=status,
                             total_moves=total, analyzed_moves=analyzed)
    db.add(t); db.commit(); db.refresh(t)
    ref = f"report:{t.id}"
    billing.reserve(db, user.id, reserve, "report", ref)
    t.charge_ref = ref
    db.commit()
    return t


def test_ttl_reaper_leaves_a_running_report_reservation_alone(db):
    """回归最要命的一条：web 重启不得把在跑的复盘退款。"""
    u = _user(db)
    t = _task(db, u, status="running", total=250, analyzed=40, reserve=125)
    # 把预扣时间推到 TTL 之外
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id=t.charge_ref).one()
    tx.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    n = billing.reconcile_stale_reservations(db, 120)
    assert n == 0, "复盘预扣不属于通用 TTL 回收器的管辖范围"
    assert billing.get_balance(db, u.id) == 875
    assert billing.transaction_status(db, t.charge_ref) == "reserved"


def test_ttl_reaper_still_reaps_other_stale_reservations(db):
    """隔离不能把回收器整个废掉 —— 别的预扣照收。"""
    u = _user(db)
    billing.reserve(db, u.id, 10, "analysis_territory", "hint:1")
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id="hint:1").one()
    tx.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()
    assert billing.reconcile_stale_reservations(db, 120) == 1
    assert billing.get_balance(db, u.id) == 1000


def test_settlement_refunds_the_unused_estimate(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="pending", total=250, analyzed=0, reserve=125)
    t.status, t.analyzed_moves = "completed", 100      # 100 手认输
    db.commit()
    assert settle_finished_reports(db) == 1
    assert billing.get_balance(db, u.id) == 950       # 125 预扣，实收 50


def test_settlement_ignores_unfinished_tasks(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    _task(db, u, status="running", total=250, analyzed=40, reserve=125)
    assert settle_finished_reports(db) == 0
    assert billing.get_balance(db, u.id) == 875


def test_settlement_is_idempotent(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=100, analyzed=100, reserve=50)
    settle_finished_reports(db)
    once = billing.get_balance(db, u.id)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == once


def _past_grace(db, t):
    """把 failed 任务的 updated_at 推到 REPORT_RETRY_GRACE_SEC 之外。

    failed 不立刻结算（见 Task 6 Step 7：/retry 要能在宽限期内免费复用原预扣），
    所以「failed 任务最终按 analyzed_moves 结算」这条断言必须先让宽限期过去，
    否则测的其实是另一件事（宽限期内不结算，TTL 回收器同款用例已经覆盖）。
    """
    from katrain.web.core.config import settings

    t.updated_at = datetime.now(timezone.utc) - timedelta(seconds=settings.REPORT_RETRY_GRACE_SEC + 1)
    db.commit()


def test_failed_within_grace_is_not_settled(db):
    """宽限期内的 failed 任务必须原地不动 —— /retry 要能免费复用原预扣。"""
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    _task(db, u, status="failed", total=250, analyzed=60, reserve=125)
    assert settle_finished_reports(db) == 0
    assert billing.get_balance(db, u.id) == 875


def test_failed_with_zero_analysis_is_fully_refunded(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="failed", total=250, analyzed=0, reserve=125)
    _past_grace(db, t)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == 1000


def test_failed_after_partial_analysis_charges_only_what_ran(db):
    """跑挂了但已经烧了算力 —— 收已发生的那部分，不是全免也不是全收。"""
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="failed", total=250, analyzed=60, reserve=125)
    _past_grace(db, t)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == 1000 - 30   # 60×500 = 30 credits


def test_settlement_resumes_a_half_done_commit(db):
    """回归：上一轮在 commit 与 grant 之间崩了，差额必须补退，不能永久按预估收。"""
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=100, reserve=125)
    billing.commit(db, t.charge_ref)          # 模拟"只做了一半"
    assert billing.get_balance(db, u.id) == 875
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == 950, "125 预扣、实收 50，差额 75 必须退回"


def test_resume_does_not_double_refund(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=100, reserve=125)
    settle_finished_reports(db)
    once = billing.get_balance(db, u.id)
    t.charge_ref = f"report:{t.id}"            # 人为把引用放回去，模拟重复扫描
    db.commit()
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == once, "退款行已存在就不能再退一次"


def test_settlement_skips_a_reservation_someone_else_already_refunded(db):
    """防御：万一预扣已被别处退掉，结算必须原地跳过、不得再补一笔赠额。"""
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=100, reserve=125)
    billing.refund(db, t.charge_ref)
    before = billing.get_balance(db, u.id)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == before, "已退款的预扣不得再生出一笔钱"


def test_requeued_task_still_holding_a_reservation_is_refunded_not_skipped(db):
    """回归一条漏钱：运维 requeue 一个**还持着预扣**的任务。

    曾经的写法是在结算查询里加 `billing_exempt_reason.is_(None)`，于是这类任务被
    **永久跳过**；而 reason="report" 的预扣又被排除在通用 TTL 回收器之外
    （billing.LONG_RUNNING_REASONS），那笔积分就冻结在账本里、没有任何管理者够得着。

    现在 exempt 只决定**怎么结**（全额退），不决定**结不结**。
    全额退而不是按 analyzed_moves 结算，是因为运维把那份报告的结果删掉重跑了 ——
    用户不该为一份已经不存在的报告付钱。
    """
    from katrain.web.core.report_settlement import settle_finished_reports

    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=250, reserve=125)
    assert billing.get_balance(db, u.id) == 875

    # 运维重排：删结果、回到 pending、标记豁免（charge_ref 仍挂着）
    t.status = "pending"
    t.analyzed_moves = 0
    t.billing_exempt_reason = "requeue"
    db.commit()

    assert settle_finished_reports(db) == 1
    assert billing.get_balance(db, u.id) == 1000, "运维重排掉的报告必须全额退，不能把钱冻死"
    assert t.charge_ref is None


def test_retry_then_settle_charges_each_move_exactly_once(db):
    """回归：结算按**增量**收费，已结清的前缀不得再收一遍。

    终审实测过的形状：250 手 / 500 visits。
      建任务  预扣 125（250 手）        余额 875
      结算①  analyzed=100 → 收 50      余额 950
      retry   预扣 75（剩余 150 手）    余额 875
      结算②  analyzed=180 → 增量 80 手 → 收 40   余额 910
    合计扣 90 = cost(180 手)。

    用累计 analyzed_moves 去对增量预扣时，结算②会按 180 手算成本（90）、
    而预扣只有 75，于是不但不退差还报"契约被破坏"，前 100 手被收了两遍：
    合计扣 125 而不是 90。
    """
    from katrain.web.core import analysis_cost
    from katrain.web.core.report_settlement import settle_finished_reports

    u = _user(db)                                    # credits=1000
    t = _task(db, u, status="completed", total=250, analyzed=100, reserve=125)
    assert billing.get_balance(db, u.id) == 875

    assert settle_finished_reports(db) == 1
    assert billing.get_balance(db, u.id) == 950, "第一次只该收 100 手的钱"
    assert t.settled_moves == 100, "水位要跟着推进"

    # 模拟 /retry 为剩余 150 手重新预扣
    retry_ref = f"report:{t.id}:retry1"
    remaining_cost = analysis_cost.report_cost(250 - 100, 500)
    assert remaining_cost == 75
    t.charge_ref = retry_ref
    db.commit()
    billing.reserve(db, u.id, remaining_cost, "report", retry_ref)
    assert billing.get_balance(db, u.id) == 875

    t.analyzed_moves = 180
    db.commit()
    assert settle_finished_reports(db) == 1

    total_charged = 1000 - billing.get_balance(db, u.id)
    assert total_charged == analysis_cost.report_cost(180, 500) == 90, (
        f"180 手总共只该扣 90，实扣 {total_charged}"
    )
    assert t.settled_moves == 180


def test_requeue_resets_the_settled_watermark(db):
    """运维重排把 analyzed_moves 归零，水位也要回零，否则增量会算出负数。"""
    from katrain.web.core.report_settlement import settle_finished_reports

    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=250, reserve=125)
    settle_finished_reports(db)
    assert t.settled_moves == 250

    # 运维重排：删结果、回 pending、标豁免，并重新挂一笔预扣
    t.status = "pending"
    t.analyzed_moves = 0
    t.billing_exempt_reason = "requeue"
    t.charge_ref = f"report:{t.id}:retry1"
    db.commit()
    billing.reserve(db, u.id, 125, "report", t.charge_ref)

    settle_finished_reports(db)
    assert t.settled_moves == 0, "水位要跟着 analyzed_moves 一起回零"
