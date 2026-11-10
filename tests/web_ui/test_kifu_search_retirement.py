"""A lost DDL COMMIT reply is resolved without repeating the mutation."""
from contextlib import contextmanager
from copy import deepcopy

import pytest

from scripts import kifu_search_retire_prepared as retirement
from katrain.kifu_ingest import catalog
from katrain.web.kifu import name_batch


@pytest.mark.parametrize("outcome", ["committed", "unchanged", "mixed", "unreachable"])
def test_lost_commit_uses_bounded_readonly_catalog_check_and_never_retries(monkeypatch, outcome):
    statements, options = [], []
    before = {"tables": [{"relname": name} for name in retirement.DERIVED_TABLES],
              "triggers": [{"tgname": "kifu_prepared_kifu_albums_dml", "table_name": "kifu_albums"}],
              "function_exists": True, "prepared_enabled": False, "active_prepared_transactions": 0}
    after = {**before, "tables": [], "triggers": [], "function_exists": False}
    if outcome == "unchanged":
        after = before
    elif outcome == "mixed":
        after = {**before, "tables": before["tables"][:1]}

    class Connection:
        def exec_driver_sql(self, sql):
            statements.append(sql)

        def execution_options(self, **kwargs):
            options.append(kwargs)
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    conn = Connection()

    class Engine:
        def connect(self):
            return conn

    @contextmanager
    def guard(engine):
        yield

    @contextmanager
    def lost_commit(engine, **kwargs):
        yield conn
        raise ConnectionError("COMMIT reply lost")

    reads = []

    def inspect(connection, schema, database):
        reads.append((schema, database))
        if len(reads) == 1:
            return deepcopy(before)
        if outcome == "unreachable":
            raise ConnectionError("unreachable")
        return deepcopy(after)

    monkeypatch.setattr(catalog, "_publication_guard", guard)
    monkeypatch.setattr(name_batch, "_locked_write", lost_commit)
    monkeypatch.setattr(retirement, "inspect_target", inspect)
    args = dict(schema="public", expected_database="isolated", runtime_build_sha="a" * 40, writers_quiescent=True)
    if outcome == "committed":
        result = retirement.apply_retirement(Engine(), **args)
        assert result["committed"] and result["commit_verified_after_lost_response"]
    else:
        message = "not committed" if outcome == "unchanged" else "outcome unknown"
        with pytest.raises(RuntimeError, match=message):
            retirement.apply_retirement(Engine(), **args)
    assert len(reads) == 2
    assert options == [{"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}]
    assert statements[-2:] == ["SET LOCAL lock_timeout = '1s'", "SET LOCAL statement_timeout = '30s'"]
    drops = [sql for sql in statements if sql.startswith("DROP")]
    assert len(drops) == 8 and len(drops) == len(set(drops))
    assert all("CASCADE" not in sql and sql.endswith(" RESTRICT") for sql in drops)
