"""Opt-in actual PostgreSQL trigger tests. Never accepts business TEST/PROD DSNs."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url

from katrain.web.core.models_db import Base
from katrain.web.kifu import prepared_models as m, prepared_migration as migration


def isolated_test_url():
    dsn = os.getenv("KIFU_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip(
            "PostgreSQL guards NOT verified: set KIFU_TEST_POSTGRES_URL to isolated local kifu_prepared_test* database"
        )
    url = make_url(dsn)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"127.0.0.1", "localhost"}
        or not (url.database or "").startswith("kifu_prepared_test")
    ):
        pytest.fail(
            "KIFU_TEST_POSTGRES_URL must be an isolated local kifu_prepared_test* database; business TEST/PROD are forbidden"
        )
    return dsn


@pytest.fixture
def pg_engine():
    dsn = isolated_test_url()
    admin = create_engine(dsn)
    schema = "prepared_" + uuid4().hex
    with admin.begin() as db:
        db.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(dsn, connect_args={"options": f"-csearch_path={schema},public"})
    try:
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in migration.INPUT_TABLES])
        migration.apply_migration(engine)
        with engine.begin() as db:
            db.exec_driver_sql("INSERT INTO kifu_players (id,canonical_name) VALUES (7,'Owner')")
            db.exec_driver_sql("INSERT INTO kifu_events (id,canonical_name) VALUES (3,'Cup')")
            db.exec_driver_sql("INSERT INTO kifu_sources (id,source_key) VALUES (9,'example')")
            db.exec_driver_sql(
                "INSERT INTO kifu_name_source_registry (id,version,sha256,registry) VALUES (2,'v','sha','{}')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_name_batches (id,bundle_sha256,inventory_sha256,source_registry_id,reviewed_artifact) VALUES (4,'bundle','inventory',2,'{}')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_albums (id,player_black,player_white,black_player_id,event,source_path,sgf_content) VALUES (11,'Owner','Other',7,'Cup','test-11.sgf','(;PB[Owner]PW[Other])')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_player_names (id,player_id,lang,display_name,status) VALUES (8,7,'cn','Ａ','review')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_raw_player_values (id,raw_value,category) VALUES (12,'Raw','person_candidate')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_raw_event_values (id,raw_value,category) VALUES (13,'Raw cup','formal_event_candidate')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_event_names (id,event_id,lang,display_name,status) VALUES (24,3,'cn','Cup translated','review')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_name_research_evidence (id,player_id,lang,revision,source_registry_id,candidate_name,decision_kind,generation_rule_version,research_payload,producer_id) VALUES (21,7,'cn',1,2,'Owner translated','conventional','v1','{}','producer')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_name_changes (id,batch_id,sequence,target_table,target_row_id) VALUES (23,4,2,'kifu_players',99)"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_event_selection_batches (id,bundle_sha256,member_set_sha256,reviewed_artifact,producer_id,reviewer_id,reviewed_at,status) VALUES (22,repeat('a',64),repeat('b',64),'{}','producer','reviewer',CURRENT_TIMESTAMP,'applied')"
            )
            db.exec_driver_sql(
                "INSERT INTO kifu_album_event_selections (album_id,event_id,batch_id,selected_raw,sgf_sha256,property_name,property_index,status,rule_version,reviewer_id,reviewed_at) VALUES (11,3,22,'Cup GN',repeat('c',64),'GN',1,'approved','v1','reviewer',CURRENT_TIMESTAMP)"
            )
            db.execute(m.dirty.delete())
            db.execute(update(m.state).values(ready=True))
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


MUTATIONS = [
    ("INSERT INTO kifu_players (canonical_name) VALUES ('Inserted')", "kifu_players"),
    ("INSERT INTO kifu_events (canonical_name) VALUES ('Inserted')", "kifu_events"),
    (
        "INSERT INTO kifu_player_aliases (player_id,alias,normalized_alias) VALUES (7,'Alias','alias')",
        "kifu_player_aliases",
    ),
    (
        "INSERT INTO kifu_event_aliases (event_id,alias,normalized_alias) VALUES (3,'Alias','alias')",
        "kifu_event_aliases",
    ),
    (
        "INSERT INTO kifu_raw_player_values (raw_value,category) VALUES ('New raw','person_candidate')",
        "kifu_raw_player_values",
    ),
    (
        "INSERT INTO kifu_raw_event_values (raw_value,category) VALUES ('New raw','formal_event_candidate')",
        "kifu_raw_event_values",
    ),
    (
        "INSERT INTO kifu_raw_player_names (raw_player_id,lang,display_name,status) VALUES (12,'en','Raw translated','review')",
        "kifu_raw_player_names",
    ),
    (
        "INSERT INTO kifu_raw_event_names (raw_event_id,lang,display_name,status) VALUES (13,'en','Raw cup translated','review')",
        "kifu_raw_event_names",
    ),
    ("UPDATE kifu_name_batches SET reviewed_artifact='{\"changed\":true}' WHERE id=4", "kifu_name_batches"),
    ("UPDATE kifu_name_batches SET status='undone' WHERE id=4", "kifu_name_batches"),
    ("UPDATE kifu_name_source_registry SET registry='{\"changed\":true}' WHERE id=2", "kifu_name_source_registry"),
    (
        "INSERT INTO kifu_name_changes (batch_id,sequence,target_table,target_row_id) VALUES (4,1,'kifu_players',7)",
        "kifu_name_changes",
    ),
    (
        "INSERT INTO kifu_album_sources (album_id,source_id,origin_path,match_method) VALUES (11,9,'new.sgf','exact')",
        "kifu_album_sources",
    ),
    ("UPDATE kifu_sources SET display_name='Changed' WHERE id=9", "kifu_sources"),
    ("UPDATE kifu_albums SET sgf_content='(;GN[Changed])' WHERE id=11", "kifu_albums"),
    ("DELETE FROM kifu_player_names WHERE id=8", "kifu_player_names"),
    ("TRUNCATE kifu_player_names", "kifu_player_names"),
    ("TRUNCATE kifu_event_selection_batches CASCADE", "kifu_event_selection_batches"),
    (
        "UPDATE kifu_name_research_evidence SET research_payload='{\"changed\":true}' WHERE id=21",
        "kifu_name_research_evidence",
    ),
    ("DELETE FROM kifu_name_research_evidence WHERE id=21", "kifu_name_research_evidence"),
    ("UPDATE kifu_name_changes SET after_image='{}' WHERE id=23", "kifu_name_changes"),
    ("DELETE FROM kifu_name_changes WHERE id=23", "kifu_name_changes"),
    (
        "UPDATE kifu_event_selection_batches SET reviewed_artifact='{\"changed\":true}' WHERE id=22",
        "kifu_event_selection_batches",
    ),
    ("UPDATE kifu_event_selection_batches SET status='undone' WHERE id=22", "kifu_event_selection_batches"),
    ("DELETE FROM kifu_album_event_selections WHERE album_id=11", "kifu_album_event_selections"),
    (
        "UPDATE kifu_album_event_selections SET selected_raw='Other Cup' WHERE album_id=11",
        "kifu_album_event_selections",
    ),
    ("DELETE FROM kifu_event_names WHERE id=24", "kifu_event_names"),
    ("TRUNCATE kifu_name_source_registry CASCADE", "kifu_name_source_registry"),
]


def test_pg_dml_and_truncate_force_dirty(pg_engine):
    # Every mutation gets a fresh business snapshot, with one schema/guard setup.
    for sql, input_kind in MUTATIONS:
        with pg_engine.connect() as db:
            tx = db.begin()
            try:
                db.exec_driver_sql(sql)
                assert not db.execute(select(m.state.c.ready)).scalar_one(), sql
                row = db.execute(select(m.dirty).where(m.dirty.c.input_kind == input_kind)).mappings().first()
                assert row and row["reason"] in {"INSERT", "UPDATE", "DELETE", "TRUNCATE"}, sql
                assert "reviewed_artifact" not in (row["old_values"] or {}), sql
                assert "sgf_content" not in (row["old_values"] or {}), sql
            finally:
                tx.rollback()


def test_pg_raw_old_new_and_transaction_rollback(pg_engine):
    with pg_engine.connect() as db:
        tx = db.begin()
        db.exec_driver_sql("UPDATE kifu_player_names SET display_name='B' WHERE id=8")
        db.exec_driver_sql("UPDATE kifu_player_names SET display_name='C' WHERE id=8")
        row = db.execute(select(m.dirty).where(m.dirty.c.input_kind == "kifu_player_names")).mappings().one()
        assert row["old_values"]["display_name"] == "Ａ"
        assert row["new_values"]["display_name"] == "C"
        assert row["old_values"]["name_kind"] == "player"
        assert row["old_values"]["lang"] == "cn"
        tx.rollback()
        assert db.execute(select(m.dirty)).first() is None
        assert db.execute(select(m.state.c.ready)).scalar_one()


def test_pg_dependency_and_direct_album_targets_are_invalidated(pg_engine):
    with pg_engine.begin() as db:
        db.execute(
            m.names.insert().values(
                id=1,
                name_kind="player",
                source_key="8",
                lang="cn",
                display_name="Ａ",
                normalized_term="a",
                match_class="approved_exact",
                owner_id=7,
                eligible=True,
                valid=True,
                policy_version=1,
            )
        )
        db.execute(
            m.displays.insert().values(
                album_id=11,
                name_lang="cn",
                valid=True,
                policy_version=1,
                player_black="Ａ",
                player_white="Other",
                event="Cup",
            )
        )
        db.execute(
            m.dependencies.insert().values(
                target_kind="display", target_key="11", input_kind="kifu_player_names", input_key="8"
            )
        )
        db.exec_driver_sql("UPDATE kifu_player_names SET display_name='B' WHERE id=8")
        assert not db.execute(select(m.names.c.valid)).scalar_one()
        assert not db.execute(select(m.displays.c.valid)).scalar_one()


def test_pg_schema_checks_actual_guard_enabled_state_and_role(pg_engine):
    assert migration.verify_schema(pg_engine)["ok"]
    assert migration.verify_schema(pg_engine)["role"]["name"]
    with pg_engine.begin() as db:
        db.exec_driver_sql("ALTER TABLE kifu_player_names DISABLE TRIGGER kifu_prepared_kifu_player_names_dml")
    assert not migration.verify_schema(pg_engine)["ok"]


def test_pg_schema_rejects_when_false_guard(pg_engine):
    with pg_engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER kifu_prepared_kifu_players_dml ON kifu_players")
        db.exec_driver_sql(
            "CREATE TRIGGER kifu_prepared_kifu_players_dml AFTER INSERT OR UPDATE OR DELETE ON kifu_players FOR EACH ROW WHEN (false) EXECUTE FUNCTION kifu_prepared_invalidate()"
        )
        db.exec_driver_sql("ALTER TABLE kifu_players ENABLE ALWAYS TRIGGER kifu_prepared_kifu_players_dml")
    assert not migration.verify_schema(pg_engine)["ok"]
