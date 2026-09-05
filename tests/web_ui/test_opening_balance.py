"""存量余额必须有一条对应的开账账本行，否则账本解释不了余额。"""
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


def test_backfill_creates_one_opening_row_per_legacy_user(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances

    u = models_db.User(username="legacy", hashed_password="x", credits=10000)
    db.add(u)
    db.commit()
    db.refresh(u)

    assert backfill_opening_balances(db) == 1
    rows = db.query(models_db.CreditTransaction).filter_by(user_id=u.id).all()
    assert len(rows) == 1
    assert rows[0].reason == "opening_balance"
    assert rows[0].delta == 10000
    assert rows[0].balance_after == 10000
    assert billing.get_balance(db, u.id) == 10000, "开账不得改变余额，只补账"


def test_backfill_is_idempotent(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances

    u = models_db.User(username="legacy", hashed_password="x", credits=10000)
    db.add(u)
    db.commit()
    backfill_opening_balances(db)
    assert backfill_opening_balances(db) == 0
    assert db.query(models_db.CreditTransaction).count() == 1


def test_backfill_covers_a_user_whose_ledger_only_explains_part_of_the_balance(db):
    """最典型的一类人：列默认值给了 10000，又兑换过 500 ⇒ 余额 10500、账本只有 +500。

    「跳过已有账本行的用户」这个写法会永久漏掉他们 —— 判据必须是残差。
    """
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances

    u = models_db.User(username="mixed", hashed_password="x", credits=10000)
    db.add(u)
    db.commit()
    db.refresh(u)
    billing.grant(db, u.id, 500, "redeem", "redeem:abc")  # 余额变 10500，账本 +500

    assert backfill_opening_balances(db) == 1
    row = db.query(models_db.CreditTransaction).filter_by(reason="opening_balance").one()
    assert row.delta == 10000, "补的是残差，不是全额"
    assert billing.get_balance(db, u.id) == 10500, "开账不得改变余额"


def test_backfill_skips_users_whose_ledger_already_explains_the_balance(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances

    u = models_db.User(username="clean", hashed_password="x", credits=0)
    db.add(u)
    db.commit()
    db.refresh(u)
    billing.grant(db, u.id, 500, "redeem", "redeem:abc")
    assert backfill_opening_balances(db) == 0, "残差为 0 不需要开账"


def test_backfill_all_loops_until_converged(db):
    """启动只调一次单批函数，batch 之外的用户会永久留在不一致状态。"""
    from katrain.web.core.migrations_opening_balance import backfill_all_opening_balances

    for i in range(7):
        db.add(models_db.User(username=f"legacy{i}", hashed_password="x", credits=10000))
    db.commit()
    assert backfill_all_opening_balances(db, batch=3) == 7


def test_backfill_skips_zero_balance_users(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances

    db.add(models_db.User(username="fresh", hashed_password="x", credits=0))
    db.commit()
    assert backfill_opening_balances(db) == 0


def test_backfill_all_stops_and_warns_when_it_cannot_make_progress(db, caplog):
    """收敛判据是「还有几个用户对不上」，不是「这一轮写了几条」。

    构造：用户已经有 opening_balance 行，但余额又被账本之外的路径改过
    （残差非 0）。这一批会全部落进报警分支、一条都写不成。
    若按「写了几条」收敛，循环会**提前退出并返回 0**，看起来像迁移完成；
    实际上还有对不上的用户 —— 而那正是最不该静默的时候。
    """
    import logging

    from katrain.web.core.migrations_opening_balance import (
        backfill_all_opening_balances,
        count_users_needing_opening_balance,
    )

    u = models_db.User(username="drifted", hashed_password="x", credits=10000)
    db.add(u)
    db.commit()
    db.refresh(u)
    # 先补一次账，让他有 opening_balance 行
    backfill_all_opening_balances(db)
    assert count_users_needing_opening_balance(db) == 0

    # 账本之外把余额改掉 —— 残差再次非 0，但 opening_balance 行已存在
    u.credits = 12345
    db.commit()
    assert count_users_needing_opening_balance(db) == 1

    with caplog.at_level(logging.ERROR, logger="katrain_web"):
        assert backfill_all_opening_balances(db) == 0
    assert any("迁移未完成" in r.getMessage() for r in caplog.records), (
        "无法推进时必须报警，不能静默返回"
    )
    assert count_users_needing_opening_balance(db) == 1, "问题仍在，不许被当成已完成"
