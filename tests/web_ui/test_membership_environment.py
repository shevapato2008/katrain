"""TEST payment mode cannot reach implicit or unmarked application databases."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from katrain.web.core import billing_environment as boundary, models_db as m
from katrain.web.core.auth import SQLAlchemyUserRepository
from katrain.web.core.config import Settings


def test_settings_defaults_and_membership_requires_billing(monkeypatch):
    monkeypatch.delenv("MEMBERSHIP_MODE", raising=False)
    monkeypatch.delenv("PAYMENTS_MODE", raising=False)
    monkeypatch.delenv("KATRAIN_ENVIRONMENT", raising=False)
    monkeypatch.delenv("MEMBERSHIP_MAX_SALE_ENABLED", raising=False)
    settings = Settings()
    assert (settings.KATRAIN_ENVIRONMENT, settings.PAYMENTS_MODE, settings.MEMBERSHIP_MODE) == (
        "production",
        "disabled",
        "legacy",
    )
    assert settings.MEMBERSHIP_MAX_SALE_ENABLED is True
    for mode in ("enabled", "paused"):
        with pytest.raises(ValueError, match="BILLING_ENFORCED"):
            Settings(MEMBERSHIP_MODE=mode, BILLING_ENFORCED=False)


def test_mock_requires_explicit_environment_url_before_config_file_read(monkeypatch):
    monkeypatch.delenv("KATRAIN_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="KATRAIN_DATABASE_URL"):
        Settings(KATRAIN_ENVIRONMENT="test", PAYMENTS_MODE="mock", DATABASE_URL="sqlite:///:memory:")
    with pytest.raises(ValueError, match="production"):
        Settings(KATRAIN_ENVIRONMENT="production", PAYMENTS_MODE="mock")


def test_environment_variables_load_mode_and_minimal_runtime_limits(monkeypatch):
    for key, value in {
        "MEMBERSHIP_MODE": "enabled",
        "BILLING_ENFORCED": "true",
        "KATRAIN_ENVIRONMENT": "test",
        "PAYMENTS_MODE": "disabled",
        "MEMBERSHIP_REPORT_QUEUE_LIMIT": "9",
        "MEMBERSHIP_POSITION_QUEUE_LIMIT": "3",
        "MEMBERSHIP_POSITION_LEASE_SECONDS": "88",
        "MEMBERSHIP_MAX_SALE_ENABLED": "true",
        "PAYMENT_MOCK_EVENT_SECRET": "unit-test-event-secret",
    }.items():
        monkeypatch.setenv(key, value)
    settings = Settings()
    assert settings.MEMBERSHIP_MODE == "enabled" and settings.BILLING_ENFORCED
    assert (
        settings.MEMBERSHIP_REPORT_QUEUE_LIMIT,
        settings.MEMBERSHIP_POSITION_QUEUE_LIMIT,
        settings.MEMBERSHIP_POSITION_LEASE_SECONDS,
    ) == (9, 3, 88)
    assert settings.MEMBERSHIP_MAX_SALE_ENABLED
    assert settings.PAYMENT_MOCK_EVENT_SECRET == "unit-test-event-secret"


def test_max_sale_can_be_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("MEMBERSHIP_MAX_SALE_ENABLED", "false")
    assert Settings().MEMBERSHIP_MAX_SALE_ENABLED is False


def _config(**kwargs):
    return SimpleNamespace(
        KATRAIN_ENVIRONMENT=kwargs.get("environment", "test"),
        PAYMENTS_MODE="mock",
        MEMBERSHIP_MODE="legacy",
        BILLING_ENFORCED=False,
    )


def _pg_engine(database="membership_validation_unit", marker=True):
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.url = make_url(f"postgresql://127.0.0.1/{database}")
    connection = engine.connect.return_value.__enter__.return_value

    def execute(statement, params=None):
        sql = str(statement)
        result = MagicMock()
        if "current_database()" in sql:
            result.scalar_one.return_value = database
        elif "billing_test_identity.environment" in sql:
            result.scalar_one_or_none.return_value = "TEST" if marker else None
        elif "to_regclass" in sql:
            result.scalar_one.return_value = None
        else:
            raise AssertionError(f"Unexpected environment write/query: {sql}")
        return result

    connection.execute.side_effect = execute
    return engine


@pytest.mark.parametrize(
    "database,marker,expected", [("unknown", False, "TEST"), ("membership_validation_unit", False, "TEST")]
)
def test_mock_actual_database_requires_independently_created_marker(monkeypatch, database, marker, expected):
    monkeypatch.setenv("KATRAIN_DATABASE_URL", f"postgresql://127.0.0.1/{database}")
    engine = _pg_engine(database, marker)
    with pytest.raises(RuntimeError, match=expected):
        boundary.validate_runtime_environment(engine, _config())
    assert all(
        not str(call.args[0]).lstrip().upper().startswith(("CREATE", "ALTER", "INSERT", "UPDATE", "DELETE"))
        for call in engine.connect.return_value.__enter__.return_value.execute.call_args_list
    )


def test_mock_rejects_wrong_actual_database(monkeypatch):
    monkeypatch.setenv("KATRAIN_DATABASE_URL", "postgresql://127.0.0.1/membership_validation_expected")
    with pytest.raises(RuntimeError, match="database"):
        boundary.validate_runtime_environment(_pg_engine("membership_validation_wrong"), _config())


def test_mock_database_guard_runs_before_any_startup_ddl(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    monkeypatch.setattr("katrain.web.core.auth.settings.PAYMENTS_MODE", "mock")
    monkeypatch.setattr("katrain.web.core.auth.settings.KATRAIN_ENVIRONMENT", "test")
    create_all = MagicMock()
    monkeypatch.setattr(m.Base.metadata, "create_all", create_all)
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        repo.init_db()
    create_all.assert_not_called()


def test_membership_activation_is_flush_only_and_prevents_legacy_downgrade():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    enabled = Settings(MEMBERSHIP_MODE="enabled", BILLING_ENFORCED=True)
    with Session(engine) as session:
        boundary.activate_membership_mode(session, enabled)
        assert session.get(m.SystemConfigDB, "membership_activated_v1") is not None
        session.rollback()
        assert session.get(m.SystemConfigDB, "membership_activated_v1") is None
        boundary.activate_membership_mode(session, enabled)
        session.commit()
    with pytest.raises(RuntimeError, match="legacy"):
        boundary.validate_runtime_environment(engine, Settings(MEMBERSHIP_MODE="legacy"))


def test_new_version_financial_fact_prevents_legacy_even_if_activation_marker_is_missing():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO recharge_orders (out_trade_no,user_id,package_id,amount_fen,credits,provider,status,catalog_version) VALUES ('new',1,'topup_10',1000,1000,'mock','pending','membership_20261102_v1')"
            )
        )
    with pytest.raises(RuntimeError, match="legacy"):
        boundary.validate_runtime_environment(engine, Settings(MEMBERSHIP_MODE="legacy"))


@pytest.mark.parametrize("case", ["production_mock", "unknown_database", "wrong_database"])
def test_each_unsafe_mock_startup_stops_before_metadata_ddl(monkeypatch, case):
    database = "membership_validation_unit"
    engine = _pg_engine(database, marker=case != "unknown_database")
    monkeypatch.setenv(
        "KATRAIN_DATABASE_URL",
        f"postgresql://127.0.0.1/{database if case != 'wrong_database' else 'membership_validation_other'}",
    )
    monkeypatch.setattr("katrain.web.core.auth.settings.PAYMENTS_MODE", "mock")
    monkeypatch.setattr(
        "katrain.web.core.auth.settings.KATRAIN_ENVIRONMENT", "production" if case == "production_mock" else "test"
    )
    monkeypatch.setattr("katrain.web.core.auth.settings.MEMBERSHIP_MODE", "legacy")
    repo = SQLAlchemyUserRepository(None)
    monkeypatch.setattr(repo, "_bind", lambda: engine)
    ddl = MagicMock()
    monkeypatch.setattr(m.Base.metadata, "create_all", ddl)
    with pytest.raises(RuntimeError):
        repo.init_db()
    ddl.assert_not_called()
