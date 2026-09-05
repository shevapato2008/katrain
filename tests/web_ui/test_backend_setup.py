from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from katrain.web.server import create_app


@pytest_asyncio.fixture
async def client():
    app = create_app(enable_engine=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "engines" in data


@pytest.mark.asyncio
async def test_versioned_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "engines" in data
    assert "local" in data["engines"]
    assert "cloud" in data["engines"]


def test_settings_override(monkeypatch):
    monkeypatch.setenv("KATRAIN_PORT", "9000")
    # We need to reload the module to see the change if it's evaluated at import time
    # Or we can test if we can create a new Settings instance
    from katrain.web.core.config import Settings

    new_settings = Settings()
    assert new_settings.KATRAIN_PORT == 9000


def test_preview_mode_settings_from_environment(monkeypatch):
    monkeypatch.setenv("KATRAIN_PREVIEW_MODE", "1")

    from katrain.web.core.config import Settings

    preview_settings = Settings()

    assert preview_settings.PREVIEW_MODE is True


@pytest.mark.asyncio
async def test_preview_mode_keeps_local_app_without_production_effects(monkeypatch, tmp_path, caplog):
    database_path = tmp_path / "preview.db"
    monkeypatch.setenv("KATRAIN_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("KATRAIN_PREVIEW_MODE", "yes")
    # 初始管理员不再是硬编码的 admin/admin，只在显式注入口令时创建（develop 侧改动）。
    monkeypatch.setenv("KATRAIN_ADMIN_BOOTSTRAP_PASSWORD", "preview-bootstrap-only")

    from katrain.web import server
    from katrain.web.core import billing, db, migrations_opening_balance, report_reaper, report_settlement
    from katrain.web.core.config import Settings
    from katrain.web import live
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    preview_settings = Settings()
    test_engine = create_engine(preview_settings.DATABASE_URL, connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(server, "settings", preview_settings)
    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(db, "SessionLocal", test_session_local)

    init_platform_manager = Mock()
    live_service = Mock(start=AsyncMock(), stop=AsyncMock())
    create_live_service = Mock(return_value=live_service)
    reconcile_billing = Mock()
    # 这四件同样是**往生产库写钱**：结算、回收孤儿预扣、回收滞留 authorizing、补开账账本行。
    # preview 与生产共用同一套 postgres 与库名，所以它们必须和 reconcile 一样被守卫挡住。
    # （合并 develop 时 git 无冲突自动合并把它们留在了守卫之外，是人工挪进来的——这条用例
    #   就是那次人工判断的闸。）
    settle_reports = Mock()
    reap_orphaned = Mock()
    reap_authorizing = Mock()
    backfill_opening = Mock()
    monkeypatch.setattr(server, "_init_platform_manager", init_platform_manager)
    monkeypatch.setattr(live, "create_live_service", create_live_service)
    monkeypatch.setattr(billing, "reconcile_stale_reservations", reconcile_billing)
    monkeypatch.setattr(report_settlement, "settle_finished_reports", settle_reports)
    monkeypatch.setattr(report_reaper, "reap_orphaned_report_charges", reap_orphaned)
    monkeypatch.setattr(report_reaper, "reap_stale_authorizing", reap_authorizing)
    monkeypatch.setattr(migrations_opening_balance, "backfill_all_opening_balances", backfill_opening)

    try:
        app = server.create_app(enable_engine=False)
        with caplog.at_level("INFO", logger="katrain_web"):
            async with app.router.lifespan_context(app):
                assert app.state.user_repo is not None
                assert app.state.game_repo is not None
                assert app.state.user_game_repo is not None
                assert app.state.user_game_analysis_repo is not None
                assert app.state.router is not None

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/auth/login",
                        json={"username": "admin", "password": "preview-bootstrap-only"},
                    )

                assert response.status_code == 200
                # 周期结算循环也不许在 preview 里起来——它每 60 秒往同一个库结一次账。
                assert getattr(app.state, "report_settlement_task", None) is None

        init_platform_manager.assert_not_called()
        create_live_service.assert_not_called()
        reconcile_billing.assert_not_called()
        settle_reports.assert_not_called()
        reap_orphaned.assert_not_called()
        reap_authorizing.assert_not_called()
        backfill_opening.assert_not_called()
        assert [record.message for record in caplog.records].count(
            "Preview mode: production external effects disabled"
        ) == 1
    finally:
        test_engine.dispose()


def test_models_validation():
    from katrain.web.models import MoveRequest
    import pytest
    from pydantic import ValidationError

    # Valid
    req = MoveRequest(session_id="test", coords=[1, 2])
    assert req.session_id == "test"

    # Invalid coords length
    with pytest.raises(ValidationError):
        MoveRequest(session_id="test", coords=[1])

    # Invalid type
    with pytest.raises(ValidationError):
        MoveRequest(session_id="test", coords="invalid")


@pytest.mark.asyncio
async def test_static_mounts(client):
    # Check routes in app
    from fastapi import FastAPI

    app = create_app(enable_engine=False)
    routes = [route.path for route in app.routes]
    assert "/assets/img" in routes
    assert "/assets/fonts" in routes
    assert "/assets/sounds" in routes
