"""失败→结算→重试 这条链上不得出现免费续跑。

宽限期内（`REPORT_RETRY_GRACE_SEC`）`/retry` 复用原预扣；宽限期过后
`report_settlement.settle_finished_reports` 会把它结清（见 test_report_settlement.py），
这之后再 `/retry` 必须为剩余手数重新预扣，否则用户能白拿剩下的分析。

fixture 接线方式照抄 tests/web_ui/test_report_charging.py：裸 FastAPI app + 独立
sqlite 文件（带 uuid，避免收集阶段的模块顶层赋值互相覆盖）+ teardown 还原
`settings.DATABASE_URL`。
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

_session_factory = None


@pytest.fixture
def _test_app():
    """裸 FastAPI app —— 接线与隔离方式照抄 test_report_charging.py 的同名 fixture。"""
    global _session_factory
    previous_database_url = settings.DATABASE_URL
    db_path = f"./test_report_retry_auth_{uuid.uuid4().hex}.db"
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

    username = f"retrier-{uuid.uuid4().hex[:8]}"
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
    """与 app 同一个引擎上的直连会话 —— 用来直接改任务行的状态。"""
    session = _session_factory()
    yield session
    session.close()


async def _create_and_fail(app_with_game, monkeypatch, *, analyzed_moves: int):
    """建一份走积分计费的复盘任务，然后把它直接改成 failed（模拟 cron 跑挂）。

    返回 (client, token, user, task)。task 是刚失败、charge_ref 还挂着的原始状态——
    调用方按需再推 updated_at / 跑结算，得到「宽限期内」或「已被结算」两种夹具。
    """
    from katrain.web.core import models_db

    client, token, game_id, user = app_with_game
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)  # 只测积分路径

    r = await client.post(
        "/api/v1/reports/",
        json={"user_game_id": game_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]

    db = _session_factory()
    try:
        task = db.query(models_db.ReportTask).filter_by(id=task_id).one()
        assert task.charge_ref is not None, "fixture 前置条件：这份任务应该走了积分预扣"
        task.status = "failed"
        task.analyzed_moves = analyzed_moves
        task.error_message = "engine crashed"
        db.commit()
        db.refresh(task)
        db.expunge(task)
    finally:
        db.close()
    return client, token, user, task


@pytest.fixture
async def app_failed_task(app_with_game, monkeypatch):
    """(client, token, user, task) —— 刚失败、宽限期内、charge_ref 还挂着。"""
    yield await _create_and_fail(app_with_game, monkeypatch, analyzed_moves=1)


@pytest.fixture
async def app_settled_failed_task(app_with_game, monkeypatch):
    """(client, token, user, task) —— failed 且已经过了宽限期、被结算器结清

    （charge_ref 已经变回 None）。retry 撞见这种任务必须重新预扣，不能白跑。
    """
    from katrain.web.core import models_db
    from katrain.web.core.report_settlement import settle_finished_reports

    client, token, user, task = await _create_and_fail(app_with_game, monkeypatch, analyzed_moves=1)

    db = _session_factory()
    try:
        row = db.query(models_db.ReportTask).filter_by(id=task.id).one()
        row.updated_at = datetime.now(timezone.utc) - timedelta(seconds=settings.REPORT_RETRY_GRACE_SEC + 1)
        db.commit()
        n = settle_finished_reports(db)
        assert n == 1, "fixture 前置条件：结算应该正好结清这一份任务"
        db.refresh(row)
        assert row.charge_ref is None, "fixture 前置条件：结算之后 charge_ref 必须已被清掉"
        db.expunge(row)
    finally:
        db.close()
    yield client, token, user, row


@pytest.mark.asyncio
async def test_retry_within_grace_reuses_the_original_reservation(app_failed_task):
    client, token, user, task = app_failed_task  # 刚失败，未超宽限期
    before = _balance(user)
    r = await client.post(
        f"/api/v1/reports/{task.id}/retry", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert _balance(user) == before, "宽限期内重试不该二次扣费"


@pytest.mark.asyncio
async def test_retry_after_settlement_reauthorizes(app_settled_failed_task):
    """结算已把预扣落定 —— 重试必须为剩余手数重新预扣，不能白跑。"""
    client, token, user, task = app_settled_failed_task
    before = _balance(user)
    r = await client.post(
        f"/api/v1/reports/{task.id}/retry", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert _balance(user) < before, "结算之后重试必须重新授权"


@pytest.mark.asyncio
async def test_retry_without_credits_returns_402(app_settled_failed_task):
    client, token, user, task = app_settled_failed_task
    _set_balance(user, 0)
    r = await client.post(
        f"/api/v1/reports/{task.id}/retry", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "insufficient_credits"


@pytest.mark.asyncio
async def test_retry_reauthorization_does_not_reuse_the_settled_ref(app_settled_failed_task):
    """回归：复用已 committed 的旧 ref 会被幂等判断放行、不扣钱 —— 必须是新 ref。"""
    from katrain.web.core import billing

    client, token, user, task = app_settled_failed_task
    r = await client.post(
        f"/api/v1/reports/{task.id}/retry", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    db = _session_factory()
    try:
        from katrain.web.core import models_db

        row = db.query(models_db.ReportTask).filter_by(id=task.id).one()
        assert row.charge_ref is not None
        assert row.charge_ref != f"report:{task.id}", "不能复用已经 committed 的旧 ref"
        assert billing.transaction_status(db, row.charge_ref) == "reserved"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_requeued_task_is_marked_exempt_and_skipped_by_settlement(app, db):
    """运维 requeue_reports.py 重排的任务不得再被结算器收费。"""
    from katrain.web.core import billing, models_db
    from katrain.web.core.report_settlement import settle_finished_reports

    client, token, user = app
    g = models_db.UserGame(user_id=user.id, source="import", move_count=250)
    db.add(g)
    db.commit()
    db.refresh(g)
    t = models_db.ReportTask(
        user_id=user.id,
        user_game_id=g.id,
        report_type="normal",
        requested_visits=500,
        status="completed",
        total_moves=250,
        analyzed_moves=250,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    ref = f"report:{t.id}"
    billing.reserve(db, user.id, 125, "report", ref)
    # 模拟 katrain/cron/jobs/requeue_reports.py --commit 对这份任务做的事。
    t.charge_ref = None
    t.billing_exempt_reason = "requeue"
    db.commit()

    assert settle_finished_reports(db) == 0, "打了豁免标记的任务不得进入结算"
