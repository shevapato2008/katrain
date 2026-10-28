"""Explicit six-table migration and transactional source-input guards.

Trusted DB owners retain their existing administration authority. ALWAYS guards
force ordinary DML to invalidate; they do not claim resistance to owner DDL.
No application startup imports or calls this migration.
"""

from contextlib import nullcontext
import re
import warnings

from sqlalchemy import Boolean, CheckConstraint, UniqueConstraint, inspect, select, text
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.exc import SAWarning
from sqlalchemy.engine import Connection

from katrain.web.kifu import prepared_models as m

# Only proof/display inputs. Analysis, reports and rank tables intentionally absent.
INPUT_TABLES = (
    "kifu_players",
    "kifu_events",
    "kifu_event_editions",
    "kifu_player_aliases",
    "kifu_event_aliases",
    "kifu_player_names",
    "kifu_event_names",
    "kifu_raw_player_values",
    "kifu_raw_event_values",
    "kifu_raw_player_names",
    "kifu_raw_event_names",
    "kifu_name_batches",
    "kifu_name_changes",
    "kifu_name_research_evidence",
    "kifu_name_source_registry",
    "kifu_albums",
    "kifu_album_sources",
    "kifu_sources",
    "kifu_album_event_selections",
    "kifu_event_selection_batches",
)
PAYLOAD_FIELDS = (
    "id",
    "album_id",
    "player_id",
    "event_id",
    "raw_player_id",
    "raw_event_id",
    "black_player_id",
    "white_player_id",
    "event_edition_id",
    "batch_id",
    "source_id",
    "source_registry_id",
    "evidence_id",
    "target_table",
    "target_row_id",
    "candidate_name",
    "lang",
    "canonical_name",
    "display_name",
    "alias",
    "raw_value",
    "selected_raw",
    "player_black",
    "player_white",
    "event",
    "status",
    "review_status",
)
FUNCTION_NAME = "kifu_prepared_invalidate"


def _kind(table):
    if table in {"kifu_players", "kifu_player_names", "kifu_player_aliases"}:
        return "player"
    if table in {"kifu_events", "kifu_event_names", "kifu_event_aliases"}:
        return "event"
    if "raw_player" in table:
        return "raw_player"
    if "raw_event" in table:
        return "raw_event"
    return ""


def _key(table):
    return "album_id" if table == "kifu_album_event_selections" else "id"


def _qualified(conn, name):
    quote = conn.dialect.identifier_preparer.quote
    if conn.dialect.name == "postgresql":
        schema = conn.info["kifu_prepared_schema"]
        return quote(schema) + "." + quote(name)
    return quote(name)


def _invalidation_sql(conn, table, old, new, key_expr):
    names = _qualified(conn, m.names.name)
    displays = _qualified(conn, m.displays.name)
    deps = _qualified(conn, m.dependencies.name)
    # Dependencies use ('name', str(prepared_name_id)) / ('display', str(album_id)).
    # A '*' input key watches insertion/removal from an entire input collection.
    statements = [
        f"UPDATE {names} SET valid = false WHERE valid AND id IN "
        f"(SELECT CAST(target_key AS INTEGER) FROM {deps} WHERE target_kind = 'name' AND input_kind = '{table}' "
        f"AND (input_key = {key_expr} OR input_key = '*'))",
        f"UPDATE {displays} SET valid = false WHERE valid AND album_id IN "
        f"(SELECT CAST(target_key AS INTEGER) FROM {deps} WHERE target_kind = 'display' AND input_kind = '{table}' "
        f"AND (input_key = {key_expr} OR input_key = '*'))",
    ]
    if table in {"kifu_albums", "kifu_album_sources", "kifu_album_event_selections"}:
        col = "id" if table == "kifu_albums" else "album_id"
        statements.append(f"UPDATE {displays} SET valid = false WHERE valid AND album_id IN ({old(col)}, {new(col)})")
    kind = _kind(table)
    if kind:
        owner = {
            "player": "player_id",
            "event": "event_id",
            "raw_player": "raw_player_id",
            "raw_event": "raw_event_id",
        }[kind]
        if table in {"kifu_players", "kifu_events", "kifu_raw_player_values", "kifu_raw_event_values"}:
            owner = "id"
        statements.append(
            f"UPDATE {names} SET valid = false WHERE valid AND name_kind = '{kind}' "
            f"AND owner_id IN ({old(owner)}, {new(owner)})"
        )
    return statements


def _pg_function(conn):
    qualified = lambda name: _qualified(conn, name)
    # Keep payload small and preserve literal Unicode; artifact/SGF/receipts stay out.
    fields = ",".join("'" + field + "'" for field in PAYLOAD_FIELDS)
    cases = " ".join(f"WHEN '{table}' THEN '{_kind(table)}'" for table in INPUT_TABLES if _kind(table))
    body = f"""
DECLARE
    before_row jsonb; after_row jsonb; before_payload jsonb; after_payload jsonb;
    row_key text; old_key text; new_key text; domain text;
BEGIN
    -- Consistent writer order: singleton gate before any prepared target locks.
    UPDATE {qualified(m.state.name)} SET ready=false WHERE id=1;
    IF TG_OP = 'TRUNCATE' THEN
        INSERT INTO {qualified(m.dirty.name)} (input_kind,input_key,reason)
        VALUES (TG_TABLE_NAME,'*','TRUNCATE')
        ON CONFLICT (input_kind,input_key) DO UPDATE SET reason=EXCLUDED.reason;
        -- A truncated collection has no finite OLD rows. The global readiness gate
        -- remains closed until the explicit preparer resolves this domain.
        UPDATE {qualified(m.names.name)} SET valid=false WHERE valid AND id IN
          (SELECT CAST(target_key AS INTEGER) FROM {qualified(m.dependencies.name)} WHERE target_kind='name' AND input_kind=TG_TABLE_NAME);
        UPDATE {qualified(m.displays.name)} SET valid=false WHERE valid AND album_id IN
          (SELECT CAST(target_key AS INTEGER) FROM {qualified(m.dependencies.name)} WHERE target_kind='display' AND input_kind=TG_TABLE_NAME);
        RETURN NULL;
    END IF;
    IF TG_OP <> 'INSERT' THEN before_row := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN after_row := to_jsonb(NEW); END IF;
    domain := CASE TG_TABLE_NAME {cases} ELSE '' END;
    IF before_row IS NOT NULL THEN
        SELECT coalesce(jsonb_object_agg(key,value),'{{}}'::jsonb) INTO before_payload
        FROM jsonb_each(before_row) WHERE key IN ({fields});
        before_payload := before_payload || jsonb_build_object('name_kind', CASE WHEN TG_TABLE_NAME='kifu_name_research_evidence' THEN
          CASE WHEN before_row->>'player_id' IS NOT NULL THEN 'player' WHEN before_row->>'event_id' IS NOT NULL THEN 'event'
          WHEN before_row->>'raw_player_id' IS NOT NULL THEN 'raw_player' ELSE 'raw_event' END ELSE domain END);
    END IF;
    IF after_row IS NOT NULL THEN
        SELECT coalesce(jsonb_object_agg(key,value),'{{}}'::jsonb) INTO after_payload
        FROM jsonb_each(after_row) WHERE key IN ({fields});
        after_payload := after_payload || jsonb_build_object('name_kind', CASE WHEN TG_TABLE_NAME='kifu_name_research_evidence' THEN
          CASE WHEN after_row->>'player_id' IS NOT NULL THEN 'player' WHEN after_row->>'event_id' IS NOT NULL THEN 'event'
          WHEN after_row->>'raw_player_id' IS NOT NULL THEN 'raw_player' ELSE 'raw_event' END ELSE domain END);
    END IF;
    old_key := before_row->>(CASE WHEN TG_TABLE_NAME='kifu_album_event_selections' THEN 'album_id' ELSE 'id' END);
    new_key := after_row->>(CASE WHEN TG_TABLE_NAME='kifu_album_event_selections' THEN 'album_id' ELSE 'id' END);
    FOR row_key IN SELECT DISTINCT value FROM unnest(ARRAY[old_key,new_key]) value WHERE value IS NOT NULL LOOP
        INSERT INTO {qualified(m.dirty.name)} (input_kind,input_key,reason,old_values,new_values)
        VALUES (TG_TABLE_NAME,row_key,TG_OP,before_payload,after_payload)
        ON CONFLICT (input_kind,input_key) DO UPDATE SET reason=EXCLUDED.reason,new_values=EXCLUDED.new_values;
        -- first OLD intentionally retained even when it is SQL NULL (new INSERT).
"""
    for table in INPUT_TABLES:
        old = lambda column: f"CAST(before_row->>'{column}' AS INTEGER)"
        new = lambda column: f"CAST(after_row->>'{column}' AS INTEGER)"
        body += f"IF TG_TABLE_NAME = '{table}' THEN\n"
        body += ";\n".join(_invalidation_sql(conn, table, old, new, "row_key")) + ";\nEND IF;\n"
    body += """
    END LOOP;
    RETURN NULL;
END
"""
    return f"CREATE OR REPLACE FUNCTION {qualified(FUNCTION_NAME)}() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $kifu_guard${body}$kifu_guard$"


def _sqlite_triggers(conn, table):
    columns = {column["name"] for column in inspect(conn).get_columns(table)}
    payload_fields = [field for field in PAYLOAD_FIELDS if field in columns]
    result = []
    for op in ("INSERT", "UPDATE", "DELETE"):
        old = lambda column: "NULL" if op == "INSERT" or column not in columns else f'OLD."{column}"'
        new = lambda column: "NULL" if op == "DELETE" or column not in columns else f'NEW."{column}"'

        def payload(side):
            if (side == "OLD" and op == "INSERT") or (side == "NEW" and op == "DELETE"):
                return "NULL"
            pairs = [f"'{field}', {side}.\"{field}\"" for field in payload_fields]
            kind_sql = f"'{_kind(table)}'"
            if table == "kifu_name_research_evidence":
                kind_sql = (
                    f"CASE WHEN {side}.player_id IS NOT NULL THEN 'player' "
                    f"WHEN {side}.event_id IS NOT NULL THEN 'event' "
                    f"WHEN {side}.raw_player_id IS NOT NULL THEN 'raw_player' ELSE 'raw_event' END"
                )
            pairs.append(f"'name_kind', {kind_sql}")
            return "json_object(" + ", ".join(pairs) + ")"

        keys = [new(_key(table))] if op == "INSERT" else [old(_key(table))]
        if op == "UPDATE":
            keys.append(new(_key(table)))
        statements = []
        for key in keys:
            statements.append(
                f"INSERT INTO {m.dirty.name} (input_kind,input_key,reason,old_values,new_values) "
                f"VALUES ('{table}',CAST({key} AS TEXT),'{op}',{payload('OLD')},{payload('NEW')}) "
                "ON CONFLICT(input_kind,input_key) DO UPDATE SET reason=excluded.reason,new_values=excluded.new_values"
            )
            statements.extend(_invalidation_sql(conn, table, old, new, f"CAST({key} AS TEXT)"))
        statements.append(f"UPDATE {m.state.name} SET ready=false WHERE id=1")
        result.append(
            f'CREATE TRIGGER kifu_prepared_{table}_{op.lower()} AFTER {op} ON "{table}" BEGIN '
            + "; ".join(statements)
            + "; END"
        )
    return result


def _guard_statements(conn):
    if conn.dialect.name == "sqlite":
        return [sql for table in INPUT_TABLES for sql in _sqlite_triggers(conn, table)]
    if conn.dialect.name != "postgresql":
        raise ValueError("prepared search supports PostgreSQL or SQLite only")
    statements = [_pg_function(conn)]
    for table in INPUT_TABLES:
        for suffix, events, level in (
            ("dml", "INSERT OR UPDATE OR DELETE", "ROW"),
            ("truncate", "TRUNCATE", "STATEMENT"),
        ):
            name = f"kifu_prepared_{table}_{suffix}"
            statements.extend(
                [
                    f'DROP TRIGGER IF EXISTS "{name}" ON {_qualified(conn, table)}',
                    f'CREATE TRIGGER "{name}" AFTER {events} ON {_qualified(conn, table)} FOR EACH {level} EXECUTE FUNCTION {_qualified(conn, FUNCTION_NAME)}()',
                    f'ALTER TABLE {_qualified(conn, table)} ENABLE ALWAYS TRIGGER "{name}"',
                ]
            )
    return statements


def _set_schema(conn):
    if conn.dialect.name == "postgresql":
        conn.info["kifu_prepared_schema"] = conn.exec_driver_sql("SELECT current_schema()").scalar_one()


def migration_plan(engine):
    with engine.connect() as conn:
        _set_schema(conn)
        existing = set(inspect(conn).get_table_names())
        statements = []
        for table in m.metadata.sorted_tables:
            if table.name not in existing:
                statements.append(str(CreateTable(table).compile(dialect=conn.dialect)))
                statements.extend(
                    str(CreateIndex(index).compile(dialect=conn.dialect))
                    for index in sorted(table.indexes, key=lambda i: i.name)
                )
        missing_inputs = sorted(set(INPUT_TABLES) - existing)
        # Inputs must already have their normal business migration applied.
        if not missing_inputs:
            statements.extend(_guard_statements(conn))
        return {
            "dialect": conn.dialect.name,
            "statements": statements,
            "missing_inputs": missing_inputs,
            "default_enabled": False,
        }


def apply_migration(engine):
    with engine.begin() as conn:
        _set_schema(conn)
        missing = set(INPUT_TABLES) - set(inspect(conn).get_table_names())
        if missing:
            raise ValueError("missing business inputs: " + ", ".join(sorted(missing)))
        m.metadata.create_all(conn)
        # ON CONFLICT preserves operator enable/checkpoint state on a repeated migration.
        conn.execute(text(f"INSERT INTO {m.state.name} (id) VALUES (1) ON CONFLICT(id) DO NOTHING"))
        if conn.dialect.name == "sqlite":
            for table in INPUT_TABLES:
                for op in ("insert", "update", "delete"):
                    conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS kifu_prepared_{table}_{op}")
        for sql in _guard_statements(conn):
            conn.exec_driver_sql(sql)
    return verify_schema(engine)


def _canonical_sql(sql):
    return " ".join(sql.strip().rstrip(";").split())


def _default_sql(value):
    if value is None:
        return None
    value = re.sub(r"::(?:text|json|character varying)", "", str(value)).strip()
    return value.strip("()").strip(chr(39))


def _check_sql(value):
    # PG15 deparses IN as = ANY (ARRAY[...]); compare the same finite predicate.
    value = re.sub(r"::(?:text|character varying)", "", str(value)).lower()
    value = re.sub(r"[\s()\[\]\"]", "", value)
    return value.replace("=anyarray", "in")


def _verify_table_contract(conn, inspector, table, actual, errors):
    for column in table.c:
        fact = actual.get(column.name)
        if not fact:
            continue
        if fact["type"]._type_affinity != column.type._type_affinity:
            errors.append("column type mismatch: " + table.name + "." + column.name)
        expected = (
            str(column.server_default.arg.compile(dialect=conn.dialect))
            if column.server_default is not None and hasattr(column.server_default.arg, "compile")
            else (str(column.server_default.arg) if column.server_default is not None else None)
        )
        observed = fact.get("default")
        if column.primary_key and expected is None and str(observed).startswith("nextval("):
            continue  # PostgreSQL's ordinary SERIAL PK default.
        if isinstance(column.type, Boolean):
            normalize = lambda v: {"0": "false", "1": "true"}.get(_default_sql(v), _default_sql(v))
        else:
            normalize = _default_sql
        if normalize(observed) != normalize(expected):
            errors.append("column default mismatch: " + table.name + "." + column.name)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="Skipped unsupported reflection of expression-based index", category=SAWarning
        )
        uniques = {tuple(value["column_names"]) for value in inspector.get_unique_constraints(table.name)}
    checks = {value["name"]: _check_sql(value["sqltext"]) for value in inspector.get_check_constraints(table.name)}
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint) and tuple(constraint.columns.keys()) not in uniques:
            errors.append("unique constraint mismatch: " + constraint.name)
        if isinstance(constraint, CheckConstraint) and checks.get(constraint.name) != _check_sql(constraint.sqltext):
            errors.append("check constraint mismatch: " + constraint.name)
    foreign_keys = inspector.get_foreign_keys(table.name)
    for constraint in table.foreign_key_constraints:
        columns = [element.parent.name for element in constraint.elements]
        referred = [element.column.name for element in constraint.elements]
        target = next(iter(constraint.elements)).column.table.name
        if not any(
            value["constrained_columns"] == columns
            and value["referred_columns"] == referred
            and value["referred_table"] == target
            and value.get("options", {}).get("ondelete") == constraint.ondelete
            for value in foreign_keys
        ):
            errors.append("foreign key mismatch: " + table.name)


def verify_schema(engine):
    """Inspect an Engine or a caller-owned Connection without changing its transaction."""
    errors = []
    role = None
    with nullcontext(engine) if isinstance(engine, Connection) else engine.connect() as conn:
        _set_schema(conn)
        inspector = inspect(conn)
        existing = set(inspector.get_table_names())
        for table in m.metadata.sorted_tables:
            if table.name not in existing:
                errors.append("missing table: " + table.name)
                continue
            actual = {column["name"]: column for column in inspector.get_columns(table.name)}
            if set(actual) != set(table.c.keys()):
                errors.append("column definition mismatch: " + table.name)
            for column in table.c:
                if column.name in actual and bool(actual[column.name]["nullable"]) != column.nullable:
                    errors.append("column nullability mismatch: " + table.name + "." + column.name)
            _verify_table_contract(conn, inspector, table, actual, errors)
            if inspector.get_pk_constraint(table.name)["constrained_columns"] != list(table.primary_key.columns.keys()):
                errors.append("primary key mismatch: " + table.name)
            if conn.dialect.name == "sqlite":
                indexes = dict(
                    conn.execute(
                        text("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name=:name"),
                        {"name": table.name},
                    ).all()
                )
                for index in table.indexes:
                    expected = str(CreateIndex(index).compile(dialect=conn.dialect))
                    if _canonical_sql(indexes.get(index.name) or "") != _canonical_sql(expected):
                        errors.append("index definition mismatch: " + index.name)
            else:
                indexes = {index["name"]: index for index in inspector.get_indexes(table.name)}
                for index in table.indexes:
                    actual_index = indexes.get(index.name)
                    columns = [
                        getattr(expr, "name", None) if not hasattr(expr, "clauses") else None
                        for expr in index.expressions
                    ]
                    expressions = [
                        str(expr.compile(dialect=conn.dialect, compile_kwargs={"include_table": False}))
                        for expr in index.expressions
                    ]
                    if (
                        not actual_index
                        or actual_index["unique"] != index.unique
                        or actual_index["column_names"] != columns
                        or ("expressions" in actual_index and actual_index["expressions"] != expressions)
                    ):
                        errors.append("index definition mismatch: " + index.name)
        missing_inputs = set(INPUT_TABLES) - existing
        errors.extend("missing input: " + table for table in sorted(missing_inputs))
        if not missing_inputs:
            if conn.dialect.name == "sqlite":
                guards = dict(conn.exec_driver_sql("SELECT name,sql FROM sqlite_master WHERE type='trigger'").all())
                for table in INPUT_TABLES:
                    for sql in _sqlite_triggers(conn, table):
                        name = sql.split()[2]
                        if _canonical_sql(guards.get(name, "")) != _canonical_sql(sql):
                            errors.append("guard definition mismatch: " + name)
            else:
                role = dict(
                    conn.execute(
                        text(
                            "SELECT current_user AS name, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user"
                        )
                    )
                    .mappings()
                    .one()
                )
                guards = (
                    conn.execute(
                        text(
                            "SELECT c.relname,t.tgname,t.tgenabled,t.tgtype,t.tgnargs,t.tgargs,t.tgattr::text,t.tgqual IS NULL AS unconditional,p.proname,pn.nspname AS function_schema,pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace WHERE c.relnamespace=current_schema()::regnamespace AND NOT t.tgisinternal"
                        )
                    )
                    .mappings()
                    .all()
                )
                actual_guards = {(row["relname"], row["tgname"]): row for row in guards}
                for table in INPUT_TABLES:
                    for suffix, tgtype in (("dml", 29), ("truncate", 32)):
                        name = f"kifu_prepared_{table}_{suffix}"
                        guard = actual_guards.get((table, name))
                        if (
                            not guard
                            or guard["tgenabled"] != "A"
                            or guard["tgtype"] != tgtype
                            or guard["proname"] != FUNCTION_NAME
                            or guard["function_schema"] != conn.info["kifu_prepared_schema"]
                            or not guard["unconditional"]
                            or guard["tgnargs"] != 0
                            or guard["tgattr"] != ""
                            or bytes(guard["tgargs"]) != b""
                        ):
                            errors.append("guard definition/enabled mismatch: " + name)
                function = (
                    conn.execute(
                        text(
                            "SELECT p.prosrc,p.prosecdef,p.proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=current_schema() AND p.proname=:name AND p.pronargs=0"
                        ),
                        {"name": FUNCTION_NAME},
                    )
                    .mappings()
                    .first()
                )
                expected_body = _pg_function(conn).split("$kifu_guard$")[1]
                if (
                    not function
                    or function["prosrc"] != expected_body
                    or function["prosecdef"]
                    or function["proconfig"] != ["search_path=pg_catalog"]
                ):
                    errors.append("guard function definition mismatch")
                role["owns_inputs"] = conn.execute(
                    text(
                        "SELECT bool_and(c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)) FROM pg_class c WHERE c.oid = ANY(ARRAY["
                        + ",".join(f"to_regclass('{table}')" for table in INPUT_TABLES)
                        + "])"
                    )
                ).scalar_one()
        value = None
        if m.state.name in existing:
            value = conn.execute(select(m.state)).mappings().first()
            if value is None:
                errors.append("missing singleton state")
    return {
        "ok": not errors,
        "errors": errors,
        "dialect": engine.dialect.name,
        "role": role,
        "state": dict(value) if value else None,
    }
