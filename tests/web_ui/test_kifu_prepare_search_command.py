"""Operator commands keep preparation explicit, bounded, and resumable."""

import json
from contextlib import contextmanager

import pytest
from sqlalchemy import inspect, select, text

from katrain.web.core.models_db import KifuAlbum, KifuPlayerAlias
from katrain.web.kifu import prepared_models as m
from katrain.web.kifu.prepared_migration import apply_migration, verify_schema
from scripts import kifu_prepare_search as command
from tests.web_ui.test_kifu_name_batch import engine  # noqa: F401


def invoke(engine, capsys, *args):
    code = command.main(["--database-url", str(engine.url), *args])
    return code, json.loads(capsys.readouterr().out)


def test_plan_counts_detail_only_albums_without_installing_tables(engine, capsys):
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert(),
            [
                {
                    "id": 12,
                    "player_black": "Hidden",
                    "player_white": "?",
                    "event": "",
                    "source_path": "hidden.sgf",
                    "sgf_content": "(;)",
                    "list_hidden_reason": "review",
                    "duplicate_of_id": None,
                },
                {
                    "id": 13,
                    "player_black": "Duplicate",
                    "player_white": "?",
                    "event": "",
                    "source_path": "duplicate.sgf",
                    "sgf_content": "(;)",
                    "duplicate_of_id": 11,
                    "list_hidden_reason": None,
                },
            ],
        )
    code, result = invoke(engine, capsys, "plan", "--sample-albums", "2")
    assert code == 0, result
    assert result["counts"]["visible_albums"] == 1
    assert result["counts"]["detail_albums"] == 3
    assert result["estimated_rows"]["displays"] == 15
    assert result["sample"]["albums"] == 2
    assert result["sample"]["proof_observed"] is True
    assert not set(m.metadata.tables).intersection(inspect(engine).get_table_names())


def test_migrate_remains_dry_by_default(engine, capsys):
    code, result = invoke(engine, capsys, "migrate")
    assert code == 0 and result["default_enabled"] is False
    assert not set(m.metadata.tables).intersection(inspect(engine).get_table_names())


def test_plan_samples_head_middle_and_tail_within_one_album_limit(engine, capsys):
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert(),
            [
                {
                    "id": album_id,
                    "player_black": "?",
                    "player_white": "?",
                    "event": "",
                    "sgf_content": "(;)",
                    "source_path": f"sample-{album_id}.sgf",
                }
                for album_id in range(12, 20)
            ],
        )
    code, result = invoke(engine, capsys, "plan", "--sample-albums", "3")
    assert code == 0
    assert result["sample"]["albums"] == 3
    assert result["sample"]["id_ranges"] == [[11, 11], [15, 15], [19, 19]]
    assert result["relation_model"]["basis"].startswith("PostgreSQL 15.15")


def test_plan_uses_fresh_bounded_proof_context_for_each_source_domain(engine, capsys, monkeypatch):
    original = command.identity._qualified_name_rows
    calls = []

    def observe(db, query, model, owner_column, *entities, **kwargs):
        context = kwargs.get("orthographic_batch_contexts")
        calls.append((db, model, context, isinstance(context, dict) and not context))
        return original(db, query, model, owner_column, *entities, **kwargs)

    monkeypatch.setattr(command.identity, "_qualified_name_rows", observe)
    code, result = invoke(engine, capsys, "plan", "--sample-albums", "1000")
    assert code == 0, result
    assert {model for _db, model, _context, _empty in calls} == {spec[1] for spec in command.SPECS.values()}
    assert len(calls) == 4
    assert all(empty for _db, _model, _context, empty in calls)
    assert len({id(context) for _db, _model, context, _empty in calls}) == 4
    assert len({id(db) for db, _model, _context, _empty in calls}) == 1
    assert result["sample"]["proof_observed"] is True


@pytest.mark.parametrize(
    "args",
    [
        ("plan", "--sample-albums", "1001"),
        ("plan", "--max-seconds", "31"),
        ("prepare", "--batch-size", "501"),
        ("prepare", "--max-seconds", "1801"),
        ("prepare", "--max-memory-mib", "513"),
    ],
)
def test_cli_refuses_budget_escalation(engine, args):
    with pytest.raises(SystemExit) as caught:
        command.main(["--database-url", str(engine.url), *args])
    assert caught.value.code == 2


def test_prepare_requires_migration_and_never_creates_tables(engine, capsys):
    code, result = invoke(engine, capsys, "prepare")
    assert code == 1 and "migration" in result["reason"]
    assert not set(m.metadata.tables).intersection(inspect(engine).get_table_names())


def test_prepare_checkpoints_then_resume_uses_last_committed_cursor(engine, capsys, monkeypatch):
    apply_migration(engine)
    original = command.prepare_initial_batch
    seen = []

    def interrupted(conn, **kwargs):
        seen.append(dict(command.read_state(conn)))
        if len(seen) == 2:
            raise command.PreparationError("simulated busy writer")
        return original(conn, **kwargs)

    monkeypatch.setattr(command, "prepare_initial_batch", interrupted)
    code, result = invoke(engine, capsys, "prepare", "--batch-size", "1")
    assert code == 1 and result["committed_batches"] == 1
    with engine.connect() as conn:
        checkpoint = dict(command.read_state(conn))
        assert checkpoint["cursor"] == {"kind": 0, "owner": 17}
        assert checkpoint["enabled"] is False
    monkeypatch.setattr(command, "prepare_initial_batch", original)
    code, result = invoke(engine, capsys, "prepare", "--batch-size", "1", "--resume")
    assert code == 0 and result["ready"] is True
    with engine.connect() as conn:
        assert conn.scalar(select(m.displays.c.album_id).limit(1)) == 11
        assert command.read_state(conn)["enabled"] is False


def test_resume_checkpoint_requires_explicit_resume(engine, capsys):
    apply_migration(engine)
    with engine.begin() as conn:
        command.prepare_initial_batch(conn, batch_size=1)
    code, result = invoke(engine, capsys, "prepare")
    assert code == 1 and "--resume" in result["reason"]


def test_global_prepare_deadline_does_not_reset_for_each_batch(engine, capsys, monkeypatch):
    apply_migration(engine)
    original = command.prepare_initial_batch
    now = [0.0]

    def one_second():
        return now[0]

    def timed(conn, **kwargs):
        result = original(conn, **kwargs)
        now[0] += 2
        return result

    monkeypatch.setattr(command, "monotonic", one_second)
    monkeypatch.setattr(command, "prepare_initial_batch", timed)
    code, result = invoke(engine, capsys, "prepare", "--batch-size", "1", "--max-seconds", "3")
    assert code == 1 and result["committed_batches"] == 1
    assert "time budget" in result["reason"]
    assert result["last_committed_batch"]["cursor"] == {"kind": 0, "owner": 17}


def test_verify_does_not_claim_unobserved_comparison(engine, capsys):
    apply_migration(engine)
    code, _ = invoke(engine, capsys, "prepare")
    assert code == 0
    code, result = invoke(engine, capsys, "verify", "--all-coverage", "--compare-sample", "24")
    assert code == 1
    assert result["coverage"]["ok"] is True
    assert result["comparison"]["observed"] is False
    assert "not yet observed" in result["comparison"]["reason"]


def _comparison_file(tmp_path, cases=None):
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "cases": cases
                or [
                    {"id": "fixture-1", "category": "unique_name", "params": {"q": "吴清源", "lang": "cn"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_compare_uses_real_prepared_reader_while_disabled(engine, capsys, tmp_path):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    path = _comparison_file(tmp_path)
    code, result = invoke(
        engine, capsys, "verify", "--all-coverage", "--compare-sample", "1", "--compare-queries", str(path)
    )
    assert code == 0 and result["comparison"]["observed"] is True
    assert result["comparison"]["cases"][0]["equivalent"] is True
    with engine.begin() as conn:
        assert not command.read_state(conn)["enabled"]
        conn.execute(
            m.displays.update()
            .where(m.displays.c.album_id == 11, m.displays.c.name_lang == "cn")
            .values(player_black="changed prepared only")
        )
    code, result = invoke(
        engine, capsys, "verify", "--all-coverage", "--compare-sample", "1", "--compare-queries", str(path)
    )
    assert code == 1 and result["comparison"]["observed"] is True
    case = result["comparison"]["cases"][0]
    assert case["id"] == "fixture-1" and case["equivalent"] is False
    assert case["legacy_sha256"] != case["prepared_sha256"]
    assert "changed prepared only" not in json.dumps(result)
    assert "吴清源" not in json.dumps(result, ensure_ascii=False)


def test_compare_refuses_short_manifest_without_claiming_observation(engine, capsys, tmp_path):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    path = _comparison_file(tmp_path)
    code, result = invoke(
        engine, capsys, "verify", "--all-coverage", "--compare-sample", "24", "--compare-queries", str(path)
    )
    assert code == 1 and result["comparison"]["observed"] is False
    assert "24" in result["comparison"]["reason"]


def test_enable_refuses_incomplete_then_checks_policy_and_closes_dirty(engine, capsys):
    apply_migration(engine)
    code, result = invoke(engine, capsys, "enable", "--expected-policy-version", "1")
    assert code == 1 and "coverage" in result["reason"]
    assert invoke(engine, capsys, "prepare")[0] == 0
    assert invoke(engine, capsys, "enable", "--expected-policy-version", "2")[0] == 1
    with engine.begin() as conn:
        conn.execute(KifuPlayerAlias.__table__.insert().values(player_id=17, alias="Go", normalized_alias="go"))
        assert conn.scalar(select(m.dirty.c.input_key).limit(1)) is not None
    code, result = invoke(engine, capsys, "enable", "--expected-policy-version", "1")
    assert code == 0 and result["enabled"] is True
    with engine.connect() as conn:
        assert not conn.execute(select(m.dirty)).first()
        before = conn.scalar(select(text("count(*)")).select_from(m.names))
    assert invoke(engine, capsys, "disable")[0] == 0
    with engine.connect() as conn:
        state = command.read_state(conn)
        assert state["ready"] and not state["enabled"]
        assert conn.scalar(select(text("count(*)")).select_from(m.names)) == before


def test_enable_refuses_missing_display_without_altering_flag(engine, capsys):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    with engine.begin() as conn:
        conn.execute(m.displays.delete().where(m.displays.c.name_lang == "en"))
    code, result = invoke(engine, capsys, "enable", "--expected-policy-version", "1")
    assert code == 1 and "coverage" in result["reason"]
    with engine.connect() as conn:
        assert not command.read_state(conn)["enabled"]


def test_disable_remains_available_when_schema_verification_fails(engine, capsys):
    apply_migration(engine)
    with engine.begin() as conn:
        conn.execute(m.state.update().values(enabled=True))
        conn.exec_driver_sql("DROP TRIGGER kifu_prepared_kifu_albums_update")
    code, result = invoke(engine, capsys, "disable")
    assert code == 0 and result["enabled"] is False


def test_enable_rechecks_guards_on_the_locked_connection(engine, capsys, monkeypatch):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    original = command._writer_transaction

    @contextmanager
    def changed_after_preflight(engine, **kwargs):
        with original(engine, **kwargs) as conn:
            conn.exec_driver_sql("DROP TRIGGER kifu_prepared_kifu_albums_update")
            yield conn

    monkeypatch.setattr(command, "_writer_transaction", changed_after_preflight)
    code, result = invoke(engine, capsys, "enable", "--expected-policy-version", "1")
    assert code == 1 and "guard definition mismatch" in result["reason"]
    with engine.connect() as conn:
        assert not command.read_state(conn)["enabled"]
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM sqlite_master WHERE type='trigger' "
                    "AND name='kifu_prepared_kifu_albums_update'"
                )
            )
            == 1
        )


def test_verify_schema_uses_existing_connection_without_owning_transaction(engine):
    apply_migration(engine)
    with engine.connect() as conn:
        original_phase = command.read_state(conn)["phase"]
        conn.rollback()
        outer = conn.begin()
        conn.execute(m.state.update().values(phase="caller-uncommitted"))
        result = verify_schema(conn)
        assert result["ok"] and result["state"]["phase"] == "caller-uncommitted"
        assert outer.is_active and conn.in_transaction() and not conn.closed
        outer.rollback()
        assert command.read_state(conn)["phase"] == original_phase
        assert not conn.closed


def _collection_invalidated(engine):
    with engine.begin() as conn:
        conn.execute(m.dirty.insert().values(input_kind="kifu_players", input_key="*", reason="TRUNCATE"))
        conn.execute(m.state.update().values(ready=False))


def test_full_rebuild_resolves_existing_collection_invalidation(engine, capsys):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    _collection_invalidated(engine)
    assert invoke(engine, capsys, "prepare", "--resume")[0] == 1
    code, result = invoke(engine, capsys, "prepare", "--full")
    assert code == 0 and result["ready"]
    with engine.connect() as conn:
        state = command.read_state(conn)
        assert state["initial_coverage_complete"] and not state["enabled"]
        assert not conn.execute(select(m.dirty)).first()


def test_full_rebuild_requires_explicit_disable(engine, capsys):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    assert invoke(engine, capsys, "enable", "--expected-policy-version", "1")[0] == 0
    code, result = invoke(engine, capsys, "prepare", "--full")
    assert code == 1 and "disable" in result["reason"]
    with engine.connect() as conn:
        state = command.read_state(conn)
        assert state["enabled"] and state["ready"] and state["initial_coverage_complete"]


def test_full_start_is_committed_once_and_resume_does_not_reset(engine, capsys, monkeypatch):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    _collection_invalidated(engine)
    original_batch, original_full = command.prepare_initial_batch, command.begin_full_prepare
    calls, starts = [], []

    def start(conn):
        starts.append(True)
        return original_full(conn)

    def interrupted(conn, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise command.PreparationError("simulated interruption")
        return original_batch(conn, **kwargs)

    monkeypatch.setattr(command, "begin_full_prepare", start)
    monkeypatch.setattr(command, "prepare_initial_batch", interrupted)
    code, result = invoke(engine, capsys, "prepare", "--full", "--batch-size", "1")
    assert code == 1 and result["committed_batches"] == 1
    assert starts == [True]
    with engine.connect() as conn:
        state = command.read_state(conn)
        assert not state["initial_coverage_complete"] and not state["enabled"]
        assert state["cursor"] == {"kind": 0, "owner": 17}
    monkeypatch.setattr(command, "prepare_initial_batch", original_batch)
    assert invoke(engine, capsys, "prepare", "--resume", "--batch-size", "1")[0] == 0
    assert starts == [True]


def test_new_collection_invalidation_during_rebuild_refuses_completion(engine, capsys, monkeypatch):
    apply_migration(engine)
    assert invoke(engine, capsys, "prepare")[0] == 0
    _collection_invalidated(engine)
    original = command.prepare_initial_batch
    calls = []

    def newly_invalidated(conn, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            conn.execute(m.dirty.insert().values(input_kind="kifu_events", input_key="*", reason="TRUNCATE"))
        return original(conn, **kwargs)

    monkeypatch.setattr(command, "prepare_initial_batch", newly_invalidated)
    code, result = invoke(engine, capsys, "prepare", "--full", "--batch-size", "1")
    assert code == 1 and not result["ready"]
    with engine.connect() as conn:
        assert not command.read_state(conn)["initial_coverage_complete"]
        assert conn.execute(select(m.dirty).where(m.dirty.c.input_key == "*")).first()
    monkeypatch.setattr(command, "prepare_initial_batch", original)
    assert invoke(engine, capsys, "prepare", "--full")[0] == 0


def test_full_and_resume_cannot_be_combined(engine):
    with pytest.raises(SystemExit) as caught:
        command.main(["--database-url", str(engine.url), "prepare", "--full", "--resume"])
    assert caught.value.code == 2
