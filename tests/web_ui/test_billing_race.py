"""账本幂等竞争分支：丢失竞争时余额净变化必须为 0。

**这份测试证明什么、不证明什么**（别让它替自己说大话）：
- 证明：一旦出现「读到无行 → 别人先提交 → 自己插入撞唯一索引」这个交错，
  代码的净效果必须是 0。IntegrityError 是 `credit_transactions.ref_id`
  那条真索引抛的，不是打桩伪造的。
- **不证明**：真并发下这个交错**会**发生。那是断言，不是量出来的。
- **不证明** PostgreSQL 上的行为（这里跑 SQLite）。差异（PG 语句失败即整事务
  abort）落在安全方向：修复后 rollback 之后不再有任何写，PG 更严的语义咬不到。
  要真证跨连接冲突，得用两个真 Session + before_commit 事件挂钩，见 track 的
  非阻塞跟进项。

现有 test_billing.py 的幂等用例走的是 `_existing_tx` 早退路径，
碰不到 db.commit() 抛 IntegrityError 的那条分支。这里用「预置同 ref_id 行
+ 让 _existing_tx 第一次谎报 None」把执行强行赶进那条分支。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mkuser(db, credits=100):
    u = models_db.User(username="u1", hashed_password="x", credits=credits)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _force_lost_race(monkeypatch, db, fn, user_id, amount, ref_id):
    """预置赢家行，并让第一次 _existing_tx 返回 None。"""
    db.add(
        models_db.CreditTransaction(
            user_id=user_id, delta=-1, reason="winner",
            ref_id=ref_id, status="reserved", balance_after=99,
        )
    )
    db.commit()
    real = billing._existing_tx
    calls = {"n": 0}

    def fake(session, rid):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(session, rid)

    monkeypatch.setattr(billing, "_existing_tx", fake)
    return fn(db, user_id, amount, "probe", ref_id)


def test_reserve_lost_race_does_not_gift_credits(monkeypatch, db):
    u = _mkuser(db, credits=100)
    before = billing.get_balance(db, u.id)
    _force_lost_race(monkeypatch, db, billing.reserve, u.id, 30, "race-r")
    assert billing.get_balance(db, u.id) == before, "丢失竞争不得改变余额"


def test_grant_lost_race_does_not_debit(monkeypatch, db):
    u = _mkuser(db, credits=100)
    before = billing.get_balance(db, u.id)
    _force_lost_race(monkeypatch, db, billing.grant, u.id, 30, "race-g")
    assert billing.get_balance(db, u.id) == before, "丢失竞争不得改变余额"


def test_grant_lost_race_returns_winner_balance(monkeypatch, db):
    """grant 的返回值也要是赢家那一行的 balance_after，不是当前余额。

    赢家行写死 balance_after=99 而活余额是 100 —— 两者不同才说明读的是快照。
    """
    u = _mkuser(db, credits=100)
    got = _force_lost_race(monkeypatch, db, billing.grant, u.id, 30, "race-g2")
    assert got == 99


def test_reserve_lost_race_returns_winner_balance(monkeypatch, db):
    u = _mkuser(db, credits=100)
    got = _force_lost_race(monkeypatch, db, billing.reserve, u.id, 30, "race-r2")
    assert got == 99, "应返回赢家那一行记录的 balance_after"
