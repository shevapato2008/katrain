"""额度桶：惰性开桶、原子消费、周期到点自动换桶（无 cron 重置任务）。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def db_user(db):
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    return db, u


def test_quota_bucket_table_exists():
    assert hasattr(models_db, "QuotaBucket")


def test_bucket_is_unique_per_user_kind_period(db_user):
    db, u = db_user
    mk = lambda: models_db.QuotaBucket(
        user_id=u.id, kind="free_report", period_key="W:2026-W36", allowance=1, used=0
    )
    db.add(mk()); db.commit()
    db.add(mk())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_quota_buckets_is_protected_from_drift_rebuild():
    """重建这张表 = 给所有人重置额度，必须进保护名单。"""
    from katrain.web.core import migrations
    assert "quota_buckets" in migrations.PROTECTED_TABLES


from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))


def test_period_keys_shape():
    from katrain.web.core import quota
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    assert quota.period_key("day", t) == "D:2026-09-05"
    assert quota.period_key("week", t) == "W:2026-W36"
    assert quota.period_key("month", t) == "M:2026-09"


def test_period_key_uses_shanghai_not_utc():
    """UTC 的 2026-09-05 23:00 在上海已是 09-06。按 UTC 算会让用户晚上 8 点提前换桶。"""
    from katrain.web.core import quota
    t = datetime(2026, 9, 5, 23, 0, tzinfo=timezone.utc)
    assert quota.period_key("day", t) == "D:2026-09-06"


def test_unknown_period_raises():
    from katrain.web.core import quota
    with pytest.raises(ValueError):
        quota.period_key("fortnight")


def test_consume_within_allowance(db_user):
    from katrain.web.core import quota
    db, u = db_user
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is True
    assert quota.peek(db, u.id, "report_standard:week", allowance=3)[0] == 1


def test_consume_stops_at_allowance(db_user):
    from katrain.web.core import quota
    db, u = db_user
    for _ in range(3):
        assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is True
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is False
    assert quota.peek(db, u.id, "report_standard:week", allowance=3)[0] == 3, "失败不得计数"


def test_new_period_gets_a_fresh_bucket(db_user):
    from katrain.web.core import quota
    db, u = db_user
    t1 = datetime(2026, 9, 5, 10, 0, tzinfo=CST)     # W36
    t2 = datetime(2026, 9, 12, 10, 0, tzinfo=CST)    # W37
    for _ in range(3):
        quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t1)
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t1) is False
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t2) is True


def test_allowance_snapshot_survives_plan_change(db_user):
    """开桶时的限额是快照 —— 中途降级套餐不该把已用额度变成超额。"""
    from katrain.web.core import quota
    db, u = db_user
    quota.try_consume(db, u.id, "report_standard:week", allowance=25)
    used, allowance = quota.peek(db, u.id, "report_standard:week", allowance=8)
    assert allowance == 25, "读的是桶上的快照，不是当前套餐"


def test_release_returns_a_consumed_unit(db_user):
    from katrain.web.core import quota
    db, u = db_user
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    pk = quota.period_key("week", t)
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is False
    assert quota.release(db, u.id, "free_report", pk) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is True


def test_release_never_goes_below_zero(db_user):
    from katrain.web.core import quota
    db, u = db_user
    pk = quota.period_key("week")
    assert quota.release(db, u.id, "free_report", pk) is False


def test_release_targets_the_stored_period_not_today(db_user):
    """回归：上周崩掉的任务下周才被回收，必须还回**上周**那个桶。

    若 release 自己重算当前周期，就会既没还上旧桶、又把新周别人的 used 减掉。
    """
    from katrain.web.core import quota
    db, u = db_user
    t_old = datetime(2026, 9, 5, 10, 0, tzinfo=CST)     # W36
    t_new = datetime(2026, 9, 12, 10, 0, tzinfo=CST)    # W37
    old_pk = quota.period_key("week", t_old)
    quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t_old)
    quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t_new)

    assert quota.release(db, u.id, "free_report", old_pk) is True
    assert quota.peek(db, u.id, "free_report:week", allowance=1, now=t_old)[0] == 0
    assert quota.peek(db, u.id, "free_report:week", allowance=1, now=t_new)[0] == 1, \
        "新周的桶不得被误减"


import os


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_DSN"),
                    reason="并发行锁只能在 PG 上证；设 TEST_POSTGRES_DSN 后本用例会真的跑")
def test_concurrent_consume_never_exceeds_allowance_on_postgres():
    """两个连接同时抢最后一份额度，必须恰好一个成功。

    SQLite 会把并发串行化，在那里跑绿属于「保证在本机不存在而不会红」，
    不构成证据。上线前必须在 home-ubuntu 的 PG 上跑过这一条。
    """
    import threading
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from katrain.web.core import models_db, quota

    engine = create_engine(os.environ["TEST_POSTGRES_DSN"])
    models_db.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s0 = Session()
    u = models_db.User(username=f"race{os.getpid()}", hashed_password="x")
    s0.add(u); s0.commit(); s0.refresh(u)

    results = []
    def worker():
        s = Session()
        try:
            results.append(quota.try_consume(s, u.id, "free_report:week", allowance=1))
        finally:
            s.close()

    ts = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(results) == [False, True], f"恰好一个成功，实得 {results}"
