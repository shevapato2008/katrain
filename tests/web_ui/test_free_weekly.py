"""每周免费复盘：一周一次，用掉就没，**不累积**。

这条是裁决 D2/D3 的落点，也是第一版设计被推翻的地方：原方案用
`billing.grant` 每周发一笔积分，但积分进的是单池账本、**永久滚存** ——
三周不用就攒三份，与需求里「额度按周重置、不滚存」自相矛盾，而且攒下来的
积分可以花在任何地方。改成周额度桶之后，它是**计数器不是货币**。
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db

CST = timezone(timedelta(hours=8))


@pytest.fixture
def db_user():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    u = models_db.User(username="u1", hashed_password="x", credits=0)
    session.add(u)
    session.commit()
    session.refresh(u)
    yield session, u
    session.close()


def test_one_free_report_per_week(db_user):
    from katrain.web.core import quota

    db, u = db_user
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)  # W36
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is False


def test_free_quota_does_not_accumulate(db_user):
    """前三周一次都没用，第四周依然只有一份。

    这正是 `billing.grant` 方案做不到的：那边攒三周就有三份可用积分。
    """
    from katrain.web.core import quota

    db, u = db_user
    t4 = datetime(2026, 9, 26, 10, 0, tzinfo=CST)  # W39，前三周完全没碰
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t4) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t4) is False, (
        "攒了三周也只有当周这一份"
    )


def test_next_week_gets_a_fresh_one(db_user):
    from katrain.web.core import quota

    db, u = db_user
    t1 = datetime(2026, 9, 5, 10, 0, tzinfo=CST)   # W36
    t2 = datetime(2026, 9, 12, 10, 0, tzinfo=CST)  # W37
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t1) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t2) is True


def test_free_report_leaves_no_ledger_row(db_user):
    """免费额度是计数器不是货币 —— 不进账本。

    2026-06-07 裁决：不要「星币 + 道具次数」两种货币。额度桶只记数，
    账本仍是单池积分、只记真金白银。
    """
    from katrain.web.core import quota

    db, u = db_user
    quota.try_consume(db, u.id, "free_report:week", allowance=1)
    assert db.query(models_db.CreditTransaction).filter_by(user_id=u.id).count() == 0
    assert u.credits == 0, "免费额度不得改变积分余额"


def test_allowance_zero_disables_the_free_report(db_user):
    """把 FREE_WEEKLY_REPORTS 配成 0 就是关掉这个福利，不是「无限」。"""
    from katrain.web.core import quota

    db, u = db_user
    assert quota.try_consume(db, u.id, "free_report:week", allowance=0) is False


def test_default_allowance_is_one_per_week():
    """裁决 D2：每周免费送一次复盘。"""
    from katrain.web.core.config import settings

    assert settings.FREE_WEEKLY_REPORTS == 1
