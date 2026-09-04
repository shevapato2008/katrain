"""复盘预扣被移出通用 TTL 回收器之后，这三类钱谁来管。"""
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


def test_deleting_the_game_does_not_freeze_credits_forever(db):
    """回归：级联删除会带走任务行，而预扣留在账本里没人管。"""
    from katrain.web.core.report_reaper import reap_orphaned_report_charges
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="pending", total_moves=250)
    db.add(t); db.commit(); db.refresh(t)
    ref = f"report:{t.id}"
    billing.reserve(db, u.id, 125, "report", ref)
    t.charge_ref = ref
    db.commit()
    assert billing.get_balance(db, u.id) == 875

    db.delete(g); db.commit()                       # 级联把任务行也删了
    assert db.query(models_db.ReportTask).count() == 0

    assert reap_orphaned_report_charges(db) == 1
    assert billing.get_balance(db, u.id) == 1000, "任务都没了，钱必须退回去"


def test_reaper_leaves_charges_whose_task_still_exists(db):
    from katrain.web.core.report_reaper import reap_orphaned_report_charges
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="running", total_moves=250)
    db.add(t); db.commit(); db.refresh(t)
    billing.reserve(db, u.id, 125, "report", f"report:{t.id}")
    t.charge_ref = f"report:{t.id}"
    db.commit()
    assert reap_orphaned_report_charges(db) == 0
    assert billing.get_balance(db, u.id) == 875


def test_stale_authorizing_task_is_rolled_back(db):
    """建任务途中崩溃：cron 不认领、结算器不看，额度和积分卡在半路。"""
    from katrain.web.core.report_reaper import reap_stale_authorizing
    from katrain.web.core import quota
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="authorizing", total_moves=250)
    db.add(t); db.commit(); db.refresh(t)
    billing.reserve(db, u.id, 125, "report", f"report:{t.id}")
    t.charge_ref = f"report:{t.id}"
    t.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    assert reap_stale_authorizing(db, ttl_sec=600) == 1
    assert billing.get_balance(db, u.id) == 1000
    assert db.query(models_db.ReportTask).count() == 0


def test_stale_authorizing_releases_the_free_weekly_unit(db):
    """用免费额度那条路崩在半路 —— 额度也要还回**当初那个周**的桶。"""
    from katrain.web.core.report_reaper import reap_stale_authorizing
    from katrain.web.core import quota
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    pk = quota.period_key("week")
    quota.try_consume(db, u.id, "free_report:week", allowance=1)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="authorizing", total_moves=250,
                             free_grant_period=pk)
    db.add(t); db.commit(); db.refresh(t)
    t.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    assert reap_stale_authorizing(db, ttl_sec=600) == 1
    assert quota.peek(db, u.id, "free_report:week", allowance=1)[0] == 0, "免费额度要还回去"


def test_fresh_authorizing_task_is_left_alone(db):
    """正在授权中的任务不能被回收器抢走。"""
    from katrain.web.core.report_reaper import reap_stale_authorizing
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="authorizing", total_moves=250)
    db.add(t); db.commit()
    assert reap_stale_authorizing(db, ttl_sec=600) == 0


def test_sgf_hash_is_frozen_at_authorization(db):
    """授权时冻结棋谱指纹 —— 之后改棋谱不能悄悄换掉被分析的内容。"""
    import hashlib
    from katrain.web.api.v1.endpoints.reports import sgf_fingerprint
    a = sgf_fingerprint("(;GM[1];B[pd])")
    b = sgf_fingerprint("(;GM[1];B[dp])")
    assert a != b
    assert a == sgf_fingerprint("(;GM[1];B[pd])")


def test_orphan_reaper_also_handles_retry_refs(db):
    """/retry 重新授权用的是 `report:{id}:retryN` 形状的 ref（Task 6 引入）。

    曾经用 `split(":", 1)[1]` 取任务号，对这种 ref 会拿到 "5:retry1"、
    int() 抛异常被 continue 跳过 —— 重试产生的孤儿预扣就永远收不回来。
    """
    from katrain.web.core.report_reaper import reap_orphaned_report_charges

    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(
        user_id=u.id, user_game_id=g.id, report_type="normal",
        requested_visits=500, status="failed", total_moves=250, analyzed_moves=100,
    )
    db.add(t); db.commit(); db.refresh(t)
    ref = f"report:{t.id}:retry1"
    billing.reserve(db, u.id, 75, "report", ref)
    t.charge_ref = ref
    db.commit()
    assert billing.get_balance(db, u.id) == 925

    db.delete(g); db.commit()                      # 级联带走任务行
    assert reap_orphaned_report_charges(db) == 1
    assert billing.get_balance(db, u.id) == 1000, "重试 ref 的孤儿预扣也必须退回来"
