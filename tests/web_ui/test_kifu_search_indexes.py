"""The large search indexes are explicit operations, never startup DDL."""

from types import SimpleNamespace

import pytest

from katrain.web.core import migrations


def _ready():
    return {name: (table, keys, True, True, True) for name, (table, keys) in migrations.KIFU_SEARCH_INDEX_SPECS.items()}


def test_search_indexes_plan_only_the_three_missing_concurrent_indexes():
    statements = migrations.postgres_kifu_search_index_statements(existing_indexes={})
    assert len(statements) == 3
    assert all(sql.startswith("CREATE INDEX CONCURRENTLY ") for sql in statements)
    assert any('("target_table", "target_row_id")' in sql for sql in statements)
    assert any('(lower("display_name"))' in sql for sql in statements)
    assert migrations.postgres_kifu_search_index_statements(existing_indexes=_ready()) == []


@pytest.mark.parametrize(
    "bad",
    [
        ("other_table", ("display_name",), True, True, True),
        ("kifu_raw_event_names", ("other_column",), True, True, True),
        ("kifu_raw_event_names", ("display_name",), False, True, True),
        ("kifu_raw_event_names", ("display_name",), True, False, True),
        ("kifu_raw_event_names", ("display_name",), True, True, False),
    ],
)
def test_search_indexes_reject_wrong_definition_invalid_or_not_ready(bad):
    actual = _ready()
    actual["ix_kifu_raw_event_names_display"] = bad
    with pytest.raises(RuntimeError, match="ix_kifu_raw_event_names_display"):
        migrations.postgres_kifu_search_index_statements(existing_indexes=actual)


def test_expression_definition_allows_postgres_text_cast_but_not_other_column():
    actual = _ready()
    key = "ix_kifu_raw_event_names_lower_display"
    actual[key] = ("kifu_raw_event_names", ("lower((display_name)::text)",), True, True, True)
    assert migrations.postgres_kifu_search_index_statements(existing_indexes=actual) == []
    actual[key] = ("kifu_raw_event_names", ("lowerdisplay_name",), True, True, True)
    with pytest.raises(RuntimeError):
        migrations.postgres_kifu_search_index_statements(existing_indexes=actual)


def test_search_index_apply_uses_one_autocommit_connection_per_statement_and_rechecks(monkeypatch):
    calls = []
    snapshots = iter([{}, _ready()])
    monkeypatch.setattr(migrations, "_postgres_kifu_search_index_status", lambda engine: next(snapshots))

    class Connection:
        def execution_options(self, **options):
            calls.append(options)
            return self

        def execute(self, statement, params=None):
            calls.append(str(statement))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=Connection)
    migrations.apply_kifu_search_indexes(engine, timeout_ms=1000)
    assert calls.count({"isolation_level": "AUTOCOMMIT"}) == 3
    assert sum(isinstance(call, str) and call.startswith("CREATE INDEX CONCURRENTLY") for call in calls) == 3
