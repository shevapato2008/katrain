"""建复盘任务的计费闭环 —— 断言打在 POST /api/v1/reports/ 上。

不直接调 billing.reserve：那只证明「从我这层往里通」，证明不了端点本身
会不会扣费、会不会返 402、会不会留下未计费的任务。见
superpowers/tracks/galaxy-payment/plan.md 的 Task 5。

除了「BILLING_ENFORCED=False 行为不变」和「任何 pending 任务都已计费」两条，
其余聚焦积分扣费路径的用例都把 FREE_WEEKLY_REPORTS monkeypatch 成 0 ——
免费周额度的消费/不滚存行为由 quota.py 自己的单测（Task 7/8）覆盖，这里
再让它参与会把「按手数扣积分」和「免费额度抵扣」这两件事的断言混在一起。
"""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

# 由 _test_app() 设置，_balance / _set_balance 用它开自己的会话——这两个
# helper 只拿得到 user，拿不到 app（跟 plan.md 里的调用形态一致）。
_session_factory = None


@pytest.fixture
def _test_app():
    """裸 FastAPI app，接线方式照抄 tests/web_ui/test_reports_api.py 的 app fixture。

    **不在模块顶层** `settings.DATABASE_URL = "sqlite:///./test_report_charging.db"`：
    pytest 收集阶段会把 tests/web_ui 下所有测试文件先 import 一遍，那样写的话
    这个模块级赋值会被之后收集到的文件的同款赋值覆盖——真正跑到本文件用例时
    `settings.DATABASE_URL` 可能早已指向别的文件，几个用例就会跟别的测试文件
    共用同一个物理 sqlite 文件（`test_insufficient_credits_returns_402_and_leaves_no_task`
    断言 `count() == 0` 时曾因此在全量跑里看到别的测试留下的行）。改成在 fixture
    **运行时**（收集阶段早已结束）用带 uuid 的文件名现建，就不会再撞。

    **必须在 teardown 里把 `settings.DATABASE_URL` 还原**：它是全局单例，改了
    不还原就会一直停在本文件最后一次跑的 uuid 路径上。tests/web_ui 里不少其他
    文件也是「模块顶层写一次字面量路径,fixture 里只查`if os.path.exists(该字面量)`
    就 create_engine(settings.DATABASE_URL)」这同一种写法——它们的字面量路径在
    *收集阶段* 就定了,一旦跑到本文件时把全局值悄悄换掉且不换回来,alphabetically
    排在本文件后面的那些文件的 fixture 就会绑到本文件已经删掉的 uuid 路径上
    (sqlite 会在那个路径懒创建一个新空库),而它们自己的「先删旧文件」判的是
    另一个从未被绑定过的字面量路径,于是它们同一个文件内的多个用例之间也不再
    互相隔离(第一次实测命中的是 tests/web_ui/test_user_data_api.py 三个用例中
    的后两个,报 "testplayer" ValueError: User already exists)。
    """
    global _session_factory
    previous_database_url = settings.DATABASE_URL
    db_path = f"./test_report_charging_{uuid.uuid4().hex}.db"
    settings.DATABASE_URL = f"sqlite:///{db_path}"

    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository
    from katrain.web.core.user_game_repo import UserGameAnalysisRepository, UserGameRepository
    from katrain.web.server import create_app

    test_engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    _session_factory = TestSessionLocal

    fastapi_app = create_app(enable_engine=False)
    fastapi_app.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)
    fastapi_app.state.game_repo = GameRepository(TestSessionLocal)
    fastapi_app.state.user_game_repo = UserGameRepository(TestSessionLocal)
    fastapi_app.state.user_game_analysis_repo = UserGameAnalysisRepository(TestSessionLocal)
    fastapi_app.state.report_session_factory = TestSessionLocal

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    yield fastapi_app

    _session_factory = None
    test_engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)
    settings.DATABASE_URL = previous_database_url


def _balance(user) -> int:
    from katrain.web.core import billing

    db = _session_factory()
    try:
        return billing.get_balance(db, user.id)
    finally:
        db.close()


def _set_balance(user, n: int) -> None:
    from katrain.web.core import models_db

    db = _session_factory()
    try:
        row = db.query(models_db.User).filter_by(id=user.id).one()
        row.credits = n
        db.commit()
    finally:
        db.close()


@pytest.fixture
async def app(_test_app):
    """(client, token, user) —— 已登录的 client + 对应的 User 行(带满额积分)。"""
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    username = f"biller-{uuid.uuid4().hex[:8]}"
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _test_app.state.user_repo.create_user(username, pwd.hash("pw"))

    db = _session_factory()
    try:
        user = db.query(models_db.User).filter_by(username=username).one()
        user.credits = 10000
        db.commit()
        db.refresh(user)
        db.expunge(user)
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=_test_app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/auth/login", json={"username": username, "password": "pw"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        yield ac, token, user


@pytest.fixture
async def app_with_game(app):
    """(client, token, game_id, user) —— 已存好一份 3 手 SGF 的对局。"""
    client, token, user = app
    sgf = "(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[pq])"  # 3 手
    r = await client.post(
        "/api/v1/user-games/",
        json={"sgf_content": sgf, "source": "import", "move_count": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    game_id = r.json()["id"]
    yield client, token, game_id, user


@pytest.fixture
def db(_test_app):
    """与 app 同一个引擎上的直连会话 —— 用来断言任务行的状态。"""
    session = _session_factory()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_disabled_flag_keeps_todays_behaviour(app_with_game, monkeypatch):
    """BILLING_ENFORCED=False 时不得扣费、不得返 402、不得消费额度。"""
    client, token, game_id, user = app_with_game
    monkeypatch.setattr(settings, "BILLING_ENFORCED", False)
    before = _balance(user)
    r = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert _balance(user) == before


@pytest.mark.asyncio
async def test_charges_by_parsed_move_count(app_with_game, monkeypatch):
    client, token, game_id, user = app_with_game  # fixture 的 SGF 是 3 手
    from katrain.web.core import analysis_cost

    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)  # 只测积分路径
    before = _balance(user)
    r = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    expected = analysis_cost.report_cost(3, 500)
    assert before - _balance(user) == expected


@pytest.mark.asyncio
async def test_lying_move_count_does_not_reduce_the_charge(app, monkeypatch):
    """回归白嫖路：客户端声明 move_count=0，仍按 SGF 真实手数扣。"""
    client, token, user = app
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)
    sgf = "(;GM[1]FF[4]SZ[19]" + "".join(f";B[aa];W[bb]" for _ in range(50)) + ")"
    g = await client.post(
        "/api/v1/user-games/",
        json={"sgf_content": sgf, "source": "import", "move_count": 0},  # ← 谎报
        headers={"Authorization": f"Bearer {token}"},
    )
    assert g.status_code == 200, g.text
    gid = g.json()["id"]
    before = _balance(user)
    r = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": gid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert before - _balance(user) > 0, "谎报手数不得导致零扣费"


@pytest.mark.asyncio
async def test_insufficient_credits_returns_402_and_leaves_no_task(app_with_game, monkeypatch, db):
    client, token, game_id, user = app_with_game
    from katrain.web.core import models_db

    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)
    _set_balance(user, 0)
    r = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "insufficient_credits"
    assert db.query(models_db.ReportTask).count() == 0, "计费失败不得留下任务行"


@pytest.mark.asyncio
async def test_no_task_is_left_claimable_without_a_charge(app_with_game, monkeypatch, db):
    """任何时刻，status=pending 的任务必须已经有 charge_ref 或已用免费额度。"""
    client, token, game_id, user = app_with_game
    from katrain.web.core import models_db

    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    r = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    for t in db.query(models_db.ReportTask).filter_by(status="pending").all():
        assert t.charge_ref is not None or t.free_grant_period is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


@pytest.mark.asyncio
async def test_first_report_of_the_week_is_free_second_is_charged(app_with_game, monkeypatch):
    """端到端：本周第一份复盘走免费额度，第二份扣积分（裁决 D2）。

    这条是免费额度唯一一条穿过真实端点的断言。本文件其它几条专测积分路径的用例
    刻意把 FREE_WEEKLY_REPORTS 调到 0 隔离掉免费分支 —— 那样谁都没有真的验证过
    「免费那一份从端点走得通」。这条补上。
    """
    client, token, game_id, user = app_with_game
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)
    _set_balance(user, 10_000)
    before = _balance(user)

    r1 = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id, "force": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200, r1.text
    assert _balance(user) == before, "本周第一份应该走免费额度，不扣积分"

    r2 = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id, "force": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200, r2.text
    assert _balance(user) < before, "本周第二份免费额度已用尽，必须扣积分"


@pytest.mark.asyncio
async def test_free_report_records_its_period_not_a_charge_ref(app_with_game, monkeypatch, db):
    """走免费额度的任务必须留下 free_grant_period，且不留 charge_ref。

    这两个字段是回收器认路的凭据：崩在半路时它要靠 free_grant_period 知道
    该把额度还给**哪一周**的桶（不能重算当前周，那会减错桶）。
    """
    from katrain.web.core import models_db, quota

    client, token, game_id, user = app_with_game
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)
    _set_balance(user, 10_000)

    r = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id, "force": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    task = db.query(models_db.ReportTask).filter_by(id=r.json()["id"]).one()
    assert task.free_grant_period == quota.period_key("week")
    assert task.charge_ref is None
    assert task.status == "pending", "计费落定后才放给 cron"
