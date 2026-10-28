"""Explicit prepared-schema contract; business metadata remains untouched."""

import importlib.util
import json

import pytest
from sqlalchemy import create_engine, inspect, select, update

from katrain.web.core.models_db import Base, KifuPlayer, KifuPlayerName


def prepared_modules():
    assert importlib.util.find_spec("katrain.web.kifu.prepared_models"), "prepared schema is not implemented"
    from katrain.web.kifu import prepared_models as m, prepared_migration as migration, prepared_read as read

    return m, migration, read


def test_six_tables_are_independent_and_explicit():
    before = {name: tuple(table.columns.keys()) for name, table in Base.metadata.tables.items()}
    m, migration, _ = prepared_modules()
    assert len(m.metadata.tables) == 6
    assert set(m.metadata.tables) == {
        "kifu_search_prepared_" + suffix
        for suffix in ("state", "names", "members", "displays", "dependencies", "dirty")
    }
    assert not (m.metadata.tables.keys() & Base.metadata.tables.keys())
    assert before == {name: tuple(table.columns.keys()) for name, table in Base.metadata.tables.items()}
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    original = set(inspect(engine).get_table_names())
    plan = migration.migration_plan(engine)
    assert plan["statements"]
    assert original == set(inspect(engine).get_table_names())
    migration.apply_migration(engine)
    assert set(inspect(engine).get_table_names()) - original == set(m.metadata.tables)
    with engine.connect() as db:
        row = db.execute(select(m.state)).mappings().one()
        assert row["id"] == 1
        assert not any(row[key] for key in ("enabled", "ready", "initial_coverage_complete"))
    assert migration.verify_schema(engine)["ok"]
    migration.apply_migration(engine)  # repeat migration does not reset operator state
    engine.dispose()


def test_postgresql_migration_sets_timeouts_before_ddl_and_busy_rolls_back(tmp_path, monkeypatch, capsys):
    """SQLite executes the transaction; only PG timeout/lock behavior is simulated."""
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    from scripts import kifu_prepare_search as command

    m, migration, _ = prepared_modules()
    engine = create_engine(f"sqlite:///{tmp_path / 'migration-timeout.db'}")
    Base.metadata.create_all(engine)
    original_tables = set(inspect(engine).get_table_names())
    statements, observed_enabled = [], []

    @event.listens_for(engine, "begin")
    def explicit_transaction(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def simulate_postgresql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if statement.startswith("SET LOCAL "):
            return "SELECT 1", ()
        if statement == "DROP TRIGGER IF EXISTS busy_source_guard":
            raise OperationalError(statement, parameters, RuntimeError("source writer lock busy"))
        return statement, parameters

    def busy_guard(conn):
        observed_enabled.append(conn.scalar(select(m.state.c.enabled)))
        return ["DROP TRIGGER IF EXISTS busy_source_guard"]

    monkeypatch.setattr(engine.dialect, "name", "postgresql")
    monkeypatch.setattr(migration, "_set_schema", lambda conn: None)
    monkeypatch.setattr(migration, "_guard_statements", busy_guard)
    monkeypatch.setattr(command, "create_engine", lambda *args, **kwargs: engine)
    assert command.main(["migrate", "--apply"]) == 1
    assert not json.loads(capsys.readouterr().out)["ok"]
    first_ddl = next(
        index for index, sql in enumerate(statements) if sql.lstrip().startswith(("CREATE ", "DROP ", "ALTER "))
    )
    assert statements.index("SET LOCAL lock_timeout = '1000ms'") < first_ddl
    assert statements.index("SET LOCAL statement_timeout = '30000ms'") < first_ddl
    assert observed_enabled == [False]
    assert set(inspect(engine).get_table_names()) == original_tables
    assert not set(m.metadata.tables).intersection(original_tables)
    engine.dispose()


def test_indexes_and_finite_scope_contract():
    m, _, _ = prepared_modules()
    assert {"source_key", "semantic", "exact_group_authorized_ids", "eligible", "valid"} <= set(m.names.c.keys())
    assert tuple(m.members.primary_key.columns.keys()) == ("prepared_name_id", "album_id", "slot")
    assert tuple(m.displays.primary_key.columns.keys()) == ("album_id", "name_lang")
    assert {"old_values", "new_values", "first_changed_at"} <= set(m.dirty.c.keys())
    indexes = {index.name for index in m.names.indexes}
    assert {"ix_kifu_prepared_names_exact", "ix_kifu_prepared_names_lower", "ix_kifu_prepared_names_token"} <= indexes


def test_readiness_is_closed_on_dirty_policy_and_missing_coverage(monkeypatch):
    m, migration, read = prepared_modules()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    migration.apply_migration(engine)
    with engine.begin() as db:
        assert read.require_ready(db) is None
        db.execute(update(m.state).values(enabled=True))
        with pytest.raises(read.PreparedSearchNotReady):
            read.require_ready(db)
        db.execute(
            update(m.state).values(
                ready=True,
                initial_coverage_complete=True,
                policy_version=m.POLICY_VERSION,
                policy_signature=read.current_policy_signature(),
            )
        )
        assert read.require_ready(db)["ready"]
        db.execute(m.dirty.insert().values(input_kind="kifu_players", input_key="9", reason="INSERT"))
        with pytest.raises(read.PreparedSearchNotReady):
            read.require_ready(db)
        db.execute(m.dirty.delete())
        monkeypatch.setenv("KIFU_STRICT_NAMES", "true")
        with pytest.raises(read.PreparedSearchNotReady):
            read.require_ready(db)
    engine.dispose()


def test_sqlite_name_dirty_preserves_first_old_and_latest_new_and_rollback():
    m, migration, read = prepared_modules()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    migration.apply_migration(engine)
    with engine.begin() as db:
        db.execute(KifuPlayer.__table__.insert().values(id=7, canonical_name="Owner"))
        db.execute(
            KifuPlayerName.__table__.insert().values(id=5, player_id=7, lang="cn", display_name="Ａ", status="review")
        )
        db.execute(m.dirty.delete())
        db.execute(update(m.state).values(ready=True))
    with engine.begin() as db:
        db.execute(update(KifuPlayerName).where(KifuPlayerName.id == 5).values(display_name="B"))
        db.execute(update(KifuPlayerName).where(KifuPlayerName.id == 5).values(display_name="C"))
        row = db.execute(select(m.dirty).where(m.dirty.c.input_kind == "kifu_player_names")).mappings().one()
        assert row["old_values"]["display_name"] == "Ａ"
        assert row["new_values"]["display_name"] == "C"
        assert row["old_values"]["name_kind"] == "player"
        assert row["old_values"]["lang"] == "cn"
        assert not db.execute(select(m.state.c.ready)).scalar_one()
    with engine.connect() as db:
        tx = db.begin()
        db.execute(m.dirty.delete())
        db.execute(update(m.state).values(ready=True))
        tx.commit()
        tx = db.begin()
        db.execute(update(KifuPlayerName).where(KifuPlayerName.id == 5).values(display_name="D"))
        tx.rollback()
        assert db.execute(select(m.dirty)).first() is None
        assert db.execute(select(m.state.c.ready)).scalar_one()
    engine.dispose()


def test_verify_schema_detects_disabled_guard():
    _, migration, _ = prepared_modules()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    migration.apply_migration(engine)
    with engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER kifu_prepared_kifu_players_insert")
    status = migration.verify_schema(engine)
    assert not status["ok"]
    assert status["errors"]
    engine.dispose()


def test_nullable_event_preserves_legacy_detail_contract():
    m, migration, _ = prepared_modules()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    migration.apply_migration(engine)
    with engine.begin() as db:
        db.execute(
            m.displays.insert().values(
                album_id=9, name_lang="en", valid=True, policy_version=1, player_black="A", player_white="B", event=None
            )
        )
        assert db.execute(select(m.displays.c.event)).scalar_one() is None


def test_verify_schema_checks_index_definition_not_just_name():
    _, migration, _ = prepared_modules()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    migration.apply_migration(engine)
    with engine.begin() as db:
        db.exec_driver_sql("DROP INDEX ix_kifu_prepared_names_exact")
        db.exec_driver_sql("CREATE INDEX ix_kifu_prepared_names_exact ON kifu_search_prepared_names(owner_id)")
    assert not migration.verify_schema(engine)["ok"]


def test_evidence_dirty_domain_is_derived_from_actual_old_and_new_owner():
    m, migration, _ = prepared_modules()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    migration.apply_migration(engine)
    with engine.begin() as db:
        db.exec_driver_sql(
            "INSERT INTO kifu_name_research_evidence (id,player_id,lang,revision,source_registry_id,candidate_name,decision_kind,generation_rule_version,research_payload,producer_id) VALUES (7,1,'cn',1,1,'Name','conventional','v1','{}','producer')"
        )
        db.execute(m.dirty.delete())
        db.exec_driver_sql("UPDATE kifu_name_research_evidence SET player_id=NULL,raw_event_id=9 WHERE id=7")
        row = db.execute(select(m.dirty).where(m.dirty.c.input_kind == "kifu_name_research_evidence")).mappings().one()
        assert row["old_values"]["name_kind"] == "player"
        assert row["new_values"]["name_kind"] == "raw_event"


@pytest.mark.parametrize(
    "needle,replacement",
    [
        ("enabled BOOLEAN DEFAULT 0", "enabled BOOLEAN DEFAULT 1"),
        ("CHECK (id = 1)", "CHECK (id > 0)"),
        (
            "UNIQUE (name_kind, source_key, lang, match_class)",
            "UNIQUE (name_kind, source_key, lang, match_class, owner_id)",
        ),
        ("policy_version INTEGER", "policy_version TEXT"),
    ],
)
def test_verify_schema_checks_key_defaults_types_and_constraints(needle, replacement):
    from sqlalchemy.schema import CreateTable, CreateIndex

    m, migration, _ = prepared_modules()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    replaced = False
    with engine.begin() as db:
        for table in m.metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(dialect=db.dialect))
            if needle in ddl:
                ddl = ddl.replace(needle, replacement)
                replaced = True
            db.exec_driver_sql(ddl)
            for index in table.indexes:
                db.exec_driver_sql(str(CreateIndex(index).compile(dialect=db.dialect)))
    assert replaced
    status = migration.apply_migration(engine)
    assert not status["ok"]


def test_cli_migration_is_explicit_and_defaults_to_dry_run(tmp_path, capsys):
    from scripts.kifu_prepare_search import main

    engine = create_engine("sqlite:///" + str(tmp_path / "migration.sqlite"))
    Base.metadata.create_all(engine)
    database_url = str(engine.url)
    assert main(["--database-url", database_url, "migrate"]) == 0
    assert not any(name.startswith("kifu_search_prepared_") for name in inspect(engine).get_table_names())
    assert main(["--database-url", database_url, "migrate", "--apply"]) == 0
    assert main(["--database-url", database_url, "verify-schema"]) == 0
    capsys.readouterr()
    engine.dispose()
