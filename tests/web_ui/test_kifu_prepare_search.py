"""Prepared output is a materialization of the existing proof, never an approval."""

from copy import deepcopy
import importlib
import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.kifu import prepared_models as prepared
from katrain.web.kifu.identity import (
    live_event_selections,
    obscured_program_event_ids,
    resolve_strict_display,
    strict_display_maps,
    strict_matching_names,
)
from katrain.web.kifu.name_batch import _image, apply_bundle
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuNameBatch,
    KifuNameChange,
    KifuNameResearchEvidence,
    KifuPlayer,
    KifuPlayerName,
    KifuSource,
    KifuRawEventName,
    KifuRawEventValue,
    KifuEventName,
)
from tests.web_ui.test_kifu_name_api import _evidence
from tests.web_ui.test_kifu_name_batch import engine, registry  # noqa: F401
from tests.web_ui.test_kifu_name_first_pass import (
    bound_player_bundle,
    bound_raw_player_bundle,
    bound_shared_raw_event_bundle,
)


def _prepare_module():
    # Keep the first red failure at the missing preparer, rather than a fixture.
    return importlib.import_module("katrain.web.kifu.prepare_search")


def test_preparer_uses_uncached_proof_groups_and_scalar_batch_dependencies(engine, monkeypatch):
    module = _prepare_module()
    from katrain.web.kifu import identity
    from sqlalchemy import event

    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    original = identity._qualified_name_rows
    contexts = []

    def prove(*args, **kwargs):
        context = kwargs.get("orthographic_batch_contexts")
        assert context is None, "offline preparation must not retain full snapshot contexts"
        contexts.append(context)
        return original(*args, **kwargs)

    _install(engine)
    monkeypatch.setattr(identity, "_qualified_name_rows", prove)
    with engine.begin() as conn:
        module.prepare_all(conn)
    assert contexts
    with Session(engine) as db:
        name = db.query(KifuPlayerName).one()
        evidence = db.get(KifuNameResearchEvidence, name.evidence_id)
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", capture)
        try:
            inputs = module._proof_inputs(db, "player", name, evidence, {}, {})
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        assert ("kifu_name_batches", str(applied["batch_id"])) in inputs
        batch_reads = [statement for statement in statements if "from kifu_name_batches" in statement]
        assert batch_reads and all("reviewed_artifact" not in statement for statement in batch_reads)
        change_reads = [statement for statement in statements if "from kifu_name_changes" in statement]
        assert change_reads and all(
            "after_image" not in statement and "before_image" not in statement for statement in change_reads
        )


def _install(engine):
    from katrain.web.kifu.prepared_migration import apply_migration

    apply_migration(engine)


def _outputs(conn):
    return {(row["album_id"], row["name_lang"]): row for row in conn.execute(select(prepared.displays)).mappings()}


def _old_outputs(db, albums, lang):
    selected = live_event_selections(db, albums)
    obscured = obscured_program_event_ids(db, albums, selected_events=selected)
    players, events, canonical, sources, raw_players, raw_events = strict_display_maps(
        db, albums, lang, selected_events=selected
    )
    return {
        album.id: (
            *resolve_strict_display(
                album,
                lang,
                players,
                events,
                canonical,
                raw_players,
                raw_events,
                selected_events=selected,
                obscured_event_ids=obscured,
            ),
            sources[album.id],
        )
        for album in albums
    }


def test_owner_dependency_union_keeps_every_language_alias_and_domain():
    module = _prepare_module()
    from katrain.web.kifu.identity import LANGUAGES

    rows = [{"name_kind": "player", "owner_id": 17, "source_key": lang} for lang in LANGUAGES]
    rows += [
        {"name_kind": "player", "owner_id": 17, "source_key": "alias:1"},
        {"name_kind": "player", "owner_id": 18, "source_key": "other"},
        {"name_kind": "raw_event", "owner_id": 17, "source_key": "raw"},
    ]
    inputs = {lang: {("token", lang), ("kifu_albums", "11")} for lang in LANGUAGES}
    inputs.update({"alias:1": {("alias", "1")}, "other": {("source", "18")}, "raw": {("source", "raw")}})
    assert module._owner_dependency_inputs(rows, inputs) == {
        ("player", 17): {("token", lang) for lang in LANGUAGES} | {("kifu_albums", "11"), ("alias", "1")},
        ("player", 18): {("source", "18")},
        ("raw_event", 17): {("source", "raw")},
    }
    assert module._owner_dependency_inputs([], {}) == {}


def test_owner_dependency_representative_moves_then_clears_and_rebuilds_from_new_alias(engine, monkeypatch):
    module = _prepare_module()
    from katrain.web.core.models_db import KifuPlayerAlias

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=18, canonical_name="Other"))
        first = conn.execute(
            KifuPlayerName.__table__.insert().values(player_id=17, lang="cn", display_name="First", status="verified")
        ).inserted_primary_key[0]
        second = conn.execute(
            KifuPlayerName.__table__.insert().values(player_id=17, lang="ru", display_name="Rejected", status="review")
        ).inserted_primary_key[0]
        alias = conn.execute(
            KifuPlayerAlias.__table__.insert().values(player_id=17, alias="Alias", normalized_alias="alias")
        ).inserted_primary_key[0]
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)

        def checked(owner_id):
            rows = (
                conn.execute(
                    select(prepared.names).where(
                        prepared.names.c.name_kind == "player", prepared.names.c.owner_id == owner_id
                    )
                )
                .mappings()
                .all()
            )
            ids = {str(row["id"]) for row in rows}
            deps = (
                conn.execute(
                    select(prepared.dependencies).where(
                        prepared.dependencies.c.target_kind == "name", prepared.dependencies.c.target_key.in_(ids)
                    )
                )
                .mappings()
                .all()
            )
            assert {row["target_key"] for row in deps} == ({str(min(row["id"] for row in rows))} if rows else set())
            assert all(row["valid"] for row in rows)
            return rows, {(row["input_kind"], row["input_key"]) for row in deps}

        rows, inputs = checked(17)
        old_rep = min(row["id"] for row in rows)
        assert {
            ("kifu_player_names", str(first)),
            ("kifu_player_names", str(second)),
            ("kifu_player_aliases", str(alias)),
        } <= inputs
        # A moved representative's source row must rebuild both old/new owners.
        conn.execute(KifuPlayerName.__table__.update().where(KifuPlayerName.id == first).values(player_id=18))
        module.prepare_changed(conn)
        rows, inputs = checked(17)
        assert str(old_rep) not in {str(row["id"]) for row in rows}
        assert ("kifu_player_names", str(first)) not in inputs
        assert ("kifu_player_names", str(first)) in checked(18)[1]
        # Deleting the new representative leaves the alias as its successor.
        conn.execute(KifuPlayerName.__table__.delete().where(KifuPlayerName.id == second))
        module.prepare_changed(conn)
        assert len(checked(17)[0]) == 1
        conn.execute(KifuPlayerAlias.__table__.delete().where(KifuPlayerAlias.id == alias))
        module.prepare_changed(conn)
        assert checked(17) == ([], set())
        conn.execute(KifuPlayerAlias.__table__.insert().values(player_id=17, alias="New", normalized_alias="new"))
        module.prepare_changed(conn)
        assert len(checked(17)[0]) == 1
        assert module.verify_coverage(conn)["ready"]


def test_prepares_five_languages_real_fallback_and_detail_only_albums(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        for lang, name in (
            ("cn", "吴清源"),
            ("tw", "吳清源"),
            ("jp", "呉清源"),
            ("ko", "우칭위안"),
            ("en", "Go Seigen"),
        ):
            evidence = _evidence(db, "player", 17, lang, name)
            db.add(
                KifuPlayerName(
                    player_id=17,
                    lang=lang,
                    display_name=name,
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                )
            )
        db.add_all(
            [
                KifuAlbum(
                    id=12,
                    player_black="Mystery",
                    player_white="???",
                    event="",
                    list_hidden_reason="review",
                    sgf_content="(;B[aa])",
                    source_path="hidden.sgf",
                ),
                KifuAlbum(
                    id=13,
                    player_black="Other",
                    player_white="Other",
                    event="Cup",
                    duplicate_of_id=11,
                    sgf_content="(;B[bb])",
                    source_path="duplicate.sgf",
                ),
            ]
        )
        source = KifuSource(source_key="CWI", display_name="CWI")
        db.add(source)
        db.flush()
        db.add(KifuAlbumSource(album_id=11, source_id=source.id, origin_path="one.sgf", match_method="source_path"))
        db.commit()
        albums = db.query(KifuAlbum).order_by(KifuAlbum.id).all()
        expected = {lang: _old_outputs(db, albums, lang) for lang in prepared.NAME_LANGUAGES}
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        outputs = _outputs(conn)
        assert len(outputs) == 3 * 5
        for lang, values in expected.items():
            for album_id, (black, white, event, sources) in values.items():
                output = outputs[album_id, lang]
                assert (output["player_black"], output["player_white"], output["event"]) == (black, white, event)
                assert output["strict_outputs"]["sources"] == sources
                assert output["valid"]
        assert outputs[12, "en"]["player_black"] == "Player name unverified"
        names = conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "player")).mappings().all()
        dependencies = (
            conn.execute(select(prepared.dependencies).where(prepared.dependencies.c.target_kind == "name"))
            .mappings()
            .all()
        )
        assert {row["target_key"] for row in dependencies} == {str(min(row["id"] for row in names))}
        assert {(row["input_kind"], row["input_key"]) for row in dependencies} >= {
            ("kifu_player_names", str(row["source_name_id"])) for row in names
        }
        assert not conn.execute(
            select(prepared.dependencies).where(
                prepared.dependencies.c.target_kind == "display",
                prepared.dependencies.c.input_kind == "kifu_player_names",
            )
        ).first()
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()


def test_prepare_reads_uncommitted_changes_and_rollback_restores_both(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
    with pytest.raises(RuntimeError, match="abort publication"):
        with engine.begin() as conn:
            with Session(bind=conn) as db:
                evidence = _evidence(db, "player", 17, "en", "Go Seigen")
                db.add(
                    KifuPlayerName(
                        player_id=17,
                        lang="en",
                        display_name="Go Seigen",
                        status="verified",
                        decision_kind="conventional",
                        generation_rule_version="test-v1",
                        revision=1,
                        evidence_id=evidence.id,
                    )
                )
                db.flush()
                module.prepare_changed(conn)
                assert _outputs(conn)[11, "en"]["player_black"] == "Go Seigen"
            raise RuntimeError("abort publication")
    with engine.connect() as conn:
        assert _outputs(conn)[11, "en"]["player_black"] == "Player name unverified"
        assert not conn.execute(select(KifuPlayerName.id)).first()
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert not conn.execute(select(prepared.dirty)).first()


def test_initial_names_terminal_budget_failure_rolls_back_rows_and_cursor(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "en", "Go Seigen")
        db.add(
            KifuPlayerName(
                player_id=17,
                lang="en",
                display_name="Go Seigen",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()
    _install(engine)
    with engine.connect() as conn:
        before = dict(conn.execute(select(prepared.state)).mappings().one())
    check = module._Budget.check

    def reject_final_write(limit, albums=()):
        check(limit, albums)
        cursor = limit.conn.scalar(select(prepared.state.c.cursor))
        if cursor == {"kind": 1, "owner": 0}:
            assert limit.conn.execute(select(prepared.names.c.id)).first()
            assert limit.conn.execute(select(prepared.dependencies)).first()
            raise module.PreparationError("final names size budget exceeded")

    monkeypatch.setattr(module._Budget, "check", reject_final_write)
    with pytest.raises(module.PreparationError, match="final names size budget exceeded"):
        with engine.begin() as conn:
            module.prepare_initial_batch(conn)
    with engine.connect() as conn:
        assert dict(conn.execute(select(prepared.state)).mappings().one()) == before
        assert not conn.execute(select(prepared.names)).first()
        assert not conn.execute(select(prepared.dependencies)).first()


def test_incremental_terminal_budget_failure_rolls_back_ready_and_data(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "0")
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        before_state = dict(conn.execute(select(prepared.state)).mappings().one())
        before_outputs = _outputs(conn)
    check = module._Budget.check

    def reject_final_write(limit, albums=()):
        check(limit, albums)
        if (
            limit.conn.scalar(select(prepared.state.c.ready))
            and not limit.conn.execute(select(prepared.dirty).limit(1)).first()
        ):
            assert _outputs(limit.conn)[11, "en"]["player_white"] == "Budget mutation"
            raise module.PreparationError("final incremental size budget exceeded")

    monkeypatch.setattr(module._Budget, "check", reject_final_write)
    with pytest.raises(module.PreparationError, match="final incremental size budget exceeded"):
        with engine.begin() as conn:
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(player_white="Budget mutation"))
            module.prepare_changed(conn)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.player_white).where(KifuAlbum.id == 11)) == "Unknown"
        assert _outputs(conn) == before_outputs
        assert dict(conn.execute(select(prepared.state)).mappings().one()) == before_state
        assert not conn.execute(select(prepared.dirty)).first()


def test_finite_raw_player_scope_and_rank_suffix_are_prepared_without_expansion(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_raw_player_bundle(engine, five_languages=True)
    apply_bundle(engine, bundle, registry(), inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        names = (
            conn.execute(
                select(prepared.names).where(prepared.names.c.name_kind == "raw_player", prepared.names.c.eligible)
            )
            .mappings()
            .all()
        )
        assert len(names) == 5
        assert {row["semantic"]["raw_value"] for row in names} == {"李元赫九段"}
        ids = {row["id"] for row in names}
        members = (
            conn.execute(select(prepared.members).where(prepared.members.c.prepared_name_id.in_(ids))).mappings().all()
        )
        assert {(row["album_id"], row["slot"]) for row in members} == {(12, "black"), (15, "white")}
        outputs = _outputs(conn)
        assert outputs[12, "en"]["player_black"] == "Lee Wonhyuk"
        assert outputs[15, "en"]["player_white"] == "Lee Wonhyuk"
        assert outputs[13, "en"]["player_black"] == "Player name unverified"
        assert outputs[14, "en"]["player_black"] == "Player name unverified"
        from sqlalchemy import event
        from katrain.web.kifu import identity

        with Session(bind=conn) as db:
            qualified = identity._approved_raw_player_names(db, values={"李元赫九段"})
            statements = []

            def capture(_conn, _cursor, statement, _parameters, _context, _many):
                statements.append(statement.lower())

            event.listen(engine, "before_cursor_execute", capture)
            try:
                actual = module._finite_members(db, "raw_player", qualified)
            finally:
                event.remove(engine, "before_cursor_execute", capture)
        source_ids = {row["id"]: row["source_name_id"] for row in names}
        stored = {
            (source_ids[row["prepared_name_id"]], row["album_id"], row["slot"]): {
                key: value for key, value in row.items() if key != "prepared_name_id"
            }
            for row in members
        }
        measured = {
            (name_id, row["album_id"], row["slot"]): row for name_id, values in actual.items() for row in values
        }
        assert measured == stored
        assert statements and all("sgf_content" not in statement for statement in statements)


def _shared_player_bundle(engine):
    with engine.begin() as conn:
        conn.execute(
            KifuPlayer.__table__.insert(),
            [{"id": 18, "canonical_name": "吴清源"}, {"id": 19, "canonical_name": "Other"}],
        )
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=12,
                black_player_id=18,
                player_black="Other",
                player_white="Other",
                event="Cup",
                sgf_content="(;B[aa])",
                source_path="shared.sgf",
            )
        )
    inventory, bundle, records = bound_player_bundle(engine)
    with engine.connect() as conn:
        second_image = _image(conn, KifuPlayer.__table__, 18)
    permission = {
        "version": "canonical-shared-display-v1",
        "environment": "TEST",
        "database_binding": f"{engine.url.drivername}://{engine.url.host or ''}:{engine.url.port or ''}/{engine.url.database or ''}",
        "normalizer": "normalize_alias-v1",
        "lang": "cn",
        "display_name": "吴清源",
        "normalized_key": "吴清源",
        "identity_relation": "unknown",
        "members": [
            {"id": 17, "source_preimage_sha256": canonical_sha256(bundle["owners"][0]["preimage"])},
            {"id": 18, "source_preimage_sha256": canonical_sha256(second_image)},
        ],
    }
    research = deepcopy(records[0])
    research["owner"] = {"kind": "player", "id": 18}
    research["source_input"].update(owner=research["owner"], owner_preimage_sha256=canonical_sha256(second_image))
    candidate = deepcopy(bundle["candidates"][0])
    candidate.update(owner=research["owner"], research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(owner=research["owner"], research_sha256=candidate["research_sha256"])
    for item in (bundle["candidates"][0], candidate):
        item.update(
            collision_decision="shared_display", collision_basis={"permission_sha256": canonical_sha256(permission)}
        )
        item["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(item)
    members = [{"owner": item["owner"], "lang": "cn"} for item in (bundle["candidates"][0], candidate)]
    owners = [bundle["owners"][0], {"owner": research["owner"], "preimage": second_image}]
    bundle.update(
        members=members,
        member_set_sha256=canonical_sha256(members),
        owners=owners,
        owner_set_sha256=canonical_sha256(owners),
        candidates=[bundle["candidates"][0], candidate],
        shared_displays=[permission],
    )
    return inventory, bundle, records + [research]


@pytest.mark.parametrize("invalid_verified_member", [False, True])
def test_prepare_reuses_literal_shared_authorization_across_proof_groups(engine, monkeypatch, invalid_verified_member):
    module = _prepare_module()
    from sqlalchemy import event
    from katrain.web.kifu import identity

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = _shared_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    if invalid_verified_member:
        with engine.begin() as conn:
            conn.execute(
                KifuPlayerName.__table__.insert().values(
                    player_id=19,
                    lang="cn",
                    display_name="吴清源",
                    status="verified",
                    decision_kind="generated",
                    generation_rule_version="user_authorized_first_pass_v1",
                    revision=1,
                )
            )
    _install(engine)
    groups = identity.iter_name_proof_groups
    authorize = identity._finite_shared_player_ids
    authorizations, scalar_matches = [], []

    def separate_groups(*args, **kwargs):
        for group in groups(*args, **kwargs):
            for name_id in sorted(group):
                yield {name_id}

    def record_authorization(db, rows, needle):
        result = authorize(db, rows, needle)
        authorizations.append((needle, result))
        return result

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        sql = statement.lower()
        if sql.startswith("select kifu_player_names.player_id ") and "lower(kifu_player_names.display_name)" in sql:
            scalar_matches.append(statement)

    monkeypatch.setattr(identity, "iter_name_proof_groups", separate_groups)
    monkeypatch.setattr(identity, "_finite_shared_player_ids", record_authorization)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        with engine.begin() as conn:
            module.prepare_all(conn)
            rows = conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "player")).mappings().all()
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    expected = set() if invalid_verified_member else {17, 18}
    assert authorizations == [("吴清源", expected)]
    assert len(scalar_matches) == 1
    assert {tuple(row["exact_group_authorized_ids"]) for row in rows} == {tuple(sorted(expected))}
    assert sum(row["eligible"] for row in rows) == 2


def test_invalid_verified_c_revokes_and_delete_restores_whole_shared_token_group(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = _shared_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        rows = conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "player")).mappings().all()
        assert {tuple(row["exact_group_authorized_ids"]) for row in rows} == {(17, 18)}
    with engine.begin() as conn:
        # A/B remain qualified. C is verified but cannot pass its own proof.
        result = conn.execute(
            KifuPlayerName.__table__.insert().values(
                player_id=19,
                lang="cn",
                display_name="吴清源",
                status="verified",
                decision_kind="generated",
                generation_rule_version="user_authorized_first_pass_v1",
                revision=1,
            )
        )
        c_id = result.inserted_primary_key[0]
        assert not conn.execute(select(prepared.state.c.ready)).scalar_one()
        module.prepare_changed(conn)
        rows = conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "player")).mappings().all()
        assert {tuple(row["exact_group_authorized_ids"]) for row in rows} == {()}
        assert any(row["source_name_id"] == c_id and not row["eligible"] and row["valid"] for row in rows)
        with Session(bind=conn) as db:
            assert strict_matching_names(db, "吴清源") == (set(), set(), set(), set())
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert not conn.execute(select(prepared.dirty)).first()
    with engine.begin() as conn:
        conn.execute(KifuPlayerName.__table__.delete().where(KifuPlayerName.id == c_id))
        module.prepare_changed(conn)
        rows = conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "player")).mappings().all()
        assert {tuple(row["exact_group_authorized_ids"]) for row in rows} == {(17, 18)}
        assert len(rows) == 2


def test_new_raw_event_occurrence_reproves_negative_scope_and_old_members(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_shared_raw_event_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        assert _outputs(conn)[12, "en"]["event"] == "28th Honinbo Tournament"
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=14,
                player_black="Black",
                player_white="White",
                event="28th Honinbo",
                sgf_content="(;EV[28th Honinbo])",
                source_path="new-occurrence.sgf",
            )
        )
        assert not conn.execute(select(prepared.state.c.ready)).scalar_one()
        module.prepare_changed(conn)
        outputs = _outputs(conn)
        # New occurrence changes the signed whole raw cohort. The prior member
        # must be re-evaluated too, rather than clearing dirty after album14.
        assert outputs[12, "en"]["event"] == "Event name unverified"
        assert outputs[14, "en"]["event"] == "Event name unverified"
        assert outputs[13, "en"]["event"] == "28th Honinbo Tournament"
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert not conn.execute(select(prepared.dirty)).first()


@pytest.mark.parametrize("drift", ["owner", "evidence", "ledger", "artifact"])
def test_first_pass_input_drift_reprepares_display_from_full_proof(engine, monkeypatch, drift):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        assert _outputs(conn)[11, "cn"]["player_black"] == "吴清源"
        if drift == "owner":
            conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 17).values(canonical_name="Different"))
        elif drift == "evidence":
            evidence = conn.execute(select(KifuNameResearchEvidence.__table__)).mappings().one()
            payload = deepcopy(evidence["research_payload"])
            payload["research"]["generation"]["method"] = "translation"
            conn.execute(
                KifuNameResearchEvidence.__table__.update()
                .where(KifuNameResearchEvidence.id == evidence["id"])
                .values(research_payload=payload)
            )
        elif drift == "ledger":
            change = (
                conn.execute(select(KifuNameChange.__table__).where(KifuNameChange.target_table == "kifu_player_names"))
                .mappings()
                .one()
            )
            after = dict(change["after_image"], display_name="Different")
            conn.execute(
                KifuNameChange.__table__.update().where(KifuNameChange.id == change["id"]).values(after_image=after)
            )
        else:
            batch = (
                conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == applied["batch_id"]))
                .mappings()
                .one()
            )
            artifact = deepcopy(batch["reviewed_artifact"])
            artifact["bundle"]["candidates"][0]["display_name"] = "Different"
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == batch["id"])
                .values(reviewed_artifact=artifact)
            )
        module.prepare_changed(conn)
        assert _outputs(conn)[11, "cn"]["player_black"] == "棋手姓名待核实"
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()


def test_late_source_association_updates_existing_album_output(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        assert _outputs(conn)[11, "en"]["strict_outputs"]["sources"] == []
        source_id = conn.execute(
            KifuSource.__table__.insert().values(source_key="19x19", display_name="19x19")
        ).inserted_primary_key[0]
        conn.execute(
            KifuAlbumSource.__table__.insert().values(
                album_id=11, source_id=source_id, origin_path="later.sgf", match_method="exact_sgf"
            )
        )
        module.prepare_changed(conn)
        assert _outputs(conn)[11, "en"]["strict_outputs"]["sources"] == ["19x19"]
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        rows = conn.execute(select(prepared.names).where(prepared.names.c.owner_id.isnot(None))).mappings().all()
        source = conn.execute(select(KifuAlbumSource.__table__)).mappings().one()
        with Session(bind=conn) as db:
            inputs = module._album_display_dependencies(
                db.get(KifuAlbum, 11),
                rows,
                selected_event=None,
                selection=None,
                source_inputs={("kifu_album_sources", str(source["id"])), ("kifu_sources", str(source_id))},
                selection_inputs=set(),
            )
        stored = {
            (row.input_kind, row.input_key)
            for row in conn.execute(
                select(prepared.dependencies).where(
                    prepared.dependencies.c.target_kind == "display", prepared.dependencies.c.target_key == "11"
                )
            )
        }
        assert inputs == stored


def test_name_writer_apply_replay_and_undo_maintain_prepared_while_disabled(engine, monkeypatch):
    module = _prepare_module()
    from katrain.web.kifu.name_batch import undo_batch

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_player_bundle(engine)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with engine.connect() as conn:
        assert _outputs(conn)[11, "cn"]["player_black"] == "吴清源"
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert not conn.execute(select(prepared.state.c.enabled)).scalar_one()
    assert apply_bundle(engine, bundle, registry(), inventory, research)["status"] == "already_applied"
    undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert _outputs(conn)[11, "cn"]["player_black"] == "棋手姓名待核实"
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert not conn.execute(select(prepared.dirty)).first()


def test_writer_before_initial_coverage_keeps_dirty_for_initial_prepare(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_player_bundle(engine)
    _install(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    with engine.begin() as conn:
        assert not conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert conn.execute(select(prepared.dirty)).first()
        module.prepare_all(conn)
        assert _outputs(conn)[11, "cn"]["player_black"] == "吴清源"
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert not conn.execute(select(prepared.dirty)).first()


@pytest.mark.parametrize("name_lang", ["en", "ru"])
def test_selected_gn_apply_and_undo_reprepare_display_and_query_independent_members(engine, monkeypatch, name_lang):
    module = _prepare_module()
    from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
    from katrain.web.kifu.event_selection import undo_batch

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        album.source, album.source_path = "https://19x19.com", "data/kifu-album/19x19/one.sgf"
        album.date_played, album.board_size = "1934-10-01", 19
        album.sgf_content = "(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Other]GC[Other | 1手])"
        db.get(KifuRawEventValue, 8).review_status = "approved"
        evidence = _evidence(db, "raw_event", 8, name_lang, "Another event")
        db.add(
            KifuRawEventName(
                raw_event_id=8,
                lang=name_lang,
                display_name="Another event",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        assert _outputs(conn)[11, "en"]["event"] == "Event name unverified"
    selected = apply_reviewed_selection(engine, 11)
    with engine.connect() as conn:
        assert _outputs(conn)[11, "en"]["event"] == ("Another event" if name_lang == "en" else "Event name unverified")
        member = (
            conn.execute(
                select(prepared.members).where(
                    prepared.members.c.album_id == 11, prepared.members.c.slot == "selected_event"
                )
            )
            .mappings()
            .one()
        )
        assert member["semantic"]["raw_value"] == "Other"
        assert member["semantic"]["selected_search"]
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        rows = conn.execute(select(prepared.names).where(prepared.names.c.owner_id.isnot(None))).mappings().all()
        with Session(bind=conn) as db:
            album = db.get(KifuAlbum, 11)
            selected_events = live_event_selections(db, [album], album_ids={11})
            approvals = {}
            for lang in set(prepared.NAME_LANGUAGES) | {name_lang}:
                maps = module._display_maps([album], rows, [member], lang, {}, approvals=True)
                approvals[lang] = {11: module._slot_approval(album, maps, set(), selected_events)}
            measured = module._selected_event_members(
                album, rows, [member], selected_event=selected_events[11], approvals_by_lang=approvals
            )
        assert measured == [dict(member)]
    undo_batch(engine, selected["batch_id"])
    with engine.connect() as conn:
        assert _outputs(conn)[11, "en"]["event"] == "Event name unverified"
        assert not conn.execute(select(prepared.members).where(prepared.members.c.slot == "selected_event")).first()


def test_composed_base_revoke_invalidates_dependent_raw_display(engine, monkeypatch):
    module = _prepare_module()
    from tests.web_ui.test_kifu_name_batch import composition_bundle

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    bundle, sources, inventory, research = composition_bundle(engine)
    apply_bundle(engine, bundle, sources, inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        outputs = _outputs(conn)
        assert any("28" in row["event"] for (album_id, lang), row in outputs.items() if lang == "en")
        base = conn.execute(select(KifuEventName.__table__).where(KifuEventName.lang == "en")).mappings().one()
        conn.execute(
            KifuNameResearchEvidence.__table__.update()
            .where(KifuNameResearchEvidence.id == base["evidence_id"])
            .values(review_status="pending")
        )
        module.prepare_changed(conn)
        current = _outputs(conn)
        changed = [key for key, row in outputs.items() if key[1] == "en" and "28" in row["event"]]
        assert changed and all(current[key]["event"] == "Event name unverified" for key in changed)
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()


@pytest.mark.parametrize("source_drift", ["source_name", "source_evidence", "source_batch", "source_journal"])
def test_orthographic_display_rechecks_bound_source_dependencies(monkeypatch, source_drift):
    module = _prepare_module()
    from tests.web_ui.test_kifu_name_orthographic import verified_chinese_display_fixture
    from tests.web_ui.test_kifu_name_transliteration import registry as source_registry

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, bundle, anchors, inventory, _snapshot = verified_chinese_display_fixture()
    try:
        apply_bundle(engine, bundle, source_registry(), inventory, anchors)
        _install(engine)
        with engine.begin() as conn:
            module.prepare_all(conn)
            album_id = conn.execute(select(KifuAlbum.id)).scalar_one()
            assert _outputs(conn)[album_id, "tw"]["player_black"] == "加納一夫"
            binding = anchors[0]["content"]["binding"]
            if source_drift == "source_name":
                conn.execute(
                    KifuPlayerName.__table__.update()
                    .where(KifuPlayerName.id == binding["source_name"]["id"])
                    .values(display_name="加纳二夫")
                )
            elif source_drift == "source_evidence":
                conn.execute(
                    KifuNameResearchEvidence.__table__.update()
                    .where(KifuNameResearchEvidence.id == binding["source_evidence"]["id"])
                    .values(decision_kind="generated")
                )
            elif source_drift == "source_batch":
                conn.execute(
                    KifuNameBatch.__table__.update()
                    .where(KifuNameBatch.id == binding["source_batch"]["id"])
                    .values(bundle_sha256="f" * 64)
                )
            else:
                conn.execute(
                    KifuNameChange.__table__.update()
                    .where(
                        KifuNameChange.target_table == "kifu_name_research_evidence",
                        KifuNameChange.target_row_id == binding["source_evidence"]["id"],
                    )
                    .values(after_image={"changed": True})
                )
            module.prepare_changed(conn)
            assert _outputs(conn)[album_id, "tw"]["player_black"] == "棋手姓名待核實"
            assert conn.execute(select(prepared.state.c.ready)).scalar_one()
    finally:
        engine.dispose()


@pytest.fixture
def prepare_pg_engine():
    from tests.web_ui.test_kifu_prepared_invalidation_pg import isolated_test_url
    from katrain.web.core.models_db import Base
    from katrain.web.kifu.prepared_migration import INPUT_TABLES

    dsn = isolated_test_url()
    admin = create_engine(dsn)
    schema = "prepare_writer_" + uuid4().hex
    with admin.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(dsn, connect_args={"options": f"-csearch_path={schema},public"})
    try:
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in INPUT_TABLES])
        with engine.begin() as conn:
            conn.execute(KifuPlayer.__table__.insert().values(id=17, canonical_name="吴清源"))
            conn.execute(
                KifuRawEventValue.__table__.insert(),
                [
                    {"id": 7, "raw_value": "GNUGo3.8", "category": "program_source_label", "review_status": "approved"},
                    {"id": 8, "raw_value": "Other", "category": "unclassified_pending", "review_status": "pending"},
                ],
            )
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=11,
                    black_player_id=17,
                    player_black="吴清源九段",
                    player_white="Unknown",
                    event="GNUGo3.8",
                    sgf_content="(;PB[吴清源九段]PW[Unknown])",
                    source_path="one.sgf",
                )
            )
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def test_pg_two_connections_publish_rollback_and_revoke_visibility(prepare_pg_engine, monkeypatch):
    module = _prepare_module()
    from katrain.web.kifu.prepared_read import PreparedSearchNotReady, require_ready

    engine = prepare_pg_engine
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "en", "Go Seigen")
        evidence_id = evidence.id
        db.add(
            KifuPlayerName(
                player_id=17,
                lang="en",
                display_name="Go Seigen",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        conn.execute(prepared.state.update().values(enabled=True))
    with engine.connect() as writer:
        transaction = writer.begin()
        writer.execute(
            KifuNameResearchEvidence.__table__.update()
            .where(KifuNameResearchEvidence.id == evidence_id)
            .values(review_status="pending")
        )
        module.prepare_changed(writer)
        assert _outputs(writer)[11, "en"]["player_black"] == "Player name unverified"
        with engine.connect() as reader:
            assert require_ready(reader)
            assert _outputs(reader)[11, "en"]["player_black"] == "Go Seigen"
        transaction.rollback()
    with engine.connect() as reader:
        assert require_ready(reader)
        assert _outputs(reader)[11, "en"]["player_black"] == "Go Seigen"
    with engine.begin() as writer:
        writer.execute(
            KifuNameResearchEvidence.__table__.update()
            .where(KifuNameResearchEvidence.id == evidence_id)
            .values(review_status="pending")
        )
    with engine.connect() as reader:
        with pytest.raises(PreparedSearchNotReady):
            require_ready(reader)
    with engine.begin() as writer:
        module.prepare_changed(writer)
    with engine.connect() as reader:
        assert require_ready(reader)
        assert _outputs(reader)[11, "en"]["player_black"] == "Player name unverified"


def test_pg_new_scope_member_cannot_clear_old_closure_under_budget(prepare_pg_engine, monkeypatch):
    module = _prepare_module()
    engine = prepare_pg_engine
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_shared_raw_event_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
    with engine.begin() as writer:
        writer.execute(
            KifuAlbum.__table__.insert().values(
                id=14,
                player_black="Black",
                player_white="White",
                event="28th Honinbo",
                sgf_content="(;EV[28th Honinbo])",
                source_path="new-occurrence.sgf",
            )
        )
    with pytest.raises(module.PreparationError, match="time budget exceeded"):
        with engine.begin() as writer:
            module.prepare_changed(writer, budget=module.PrepareBudget(max_seconds=0))
    with engine.connect() as reader:
        assert not reader.execute(select(prepared.state.c.ready)).scalar_one()
        assert reader.execute(select(prepared.dirty)).first()
    with engine.begin() as writer:
        module.prepare_changed(writer)
    with engine.connect() as reader:
        assert _outputs(reader)[12, "en"]["event"] == "Event name unverified"
        assert _outputs(reader)[14, "en"]["event"] == "Event name unverified"
        assert reader.execute(select(prepared.state.c.ready)).scalar_one()


def test_canonical_new_album_uses_prepared_names_without_expanding_player_history(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "en", "Go Seigen")
        db.add(
            KifuPlayerName(
                player_id=17,
                lang="en",
                display_name="Go Seigen",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.add_all(
            [
                KifuAlbum(
                    id=album_id,
                    black_player_id=17,
                    player_black="吴清源九段",
                    player_white="Other",
                    sgf_content="(;B[aa])",
                    source_path=f"history-{album_id}.sgf",
                )
                for album_id in range(12, 612)
            ]
        )
        db.commit()
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=1000,
                black_player_id=17,
                player_black="吴清源九段",
                player_white="Other",
                sgf_content="(;B[aa])",
                source_path="new-canonical.sgf",
            )
        )
        with monkeypatch.context() as patch:
            patch.setattr(
                importlib.import_module("katrain.web.kifu.identity"),
                "_qualified_name_rows",
                lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected reproof")),
            )
            result = module.prepare_changed(conn)
        assert result["names"] == 0 and result["albums"] == 1
        assert _outputs(conn)[1000, "en"]["player_black"] == "Go Seigen"
        # A real owner mutation is different: prepare all 602 affected albums
        # atomically, writing displays in batches of at most500.
        conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 17).values(canonical_name="Changed owner"))
        result = module.prepare_changed(conn)
        assert result["albums"] == 602
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()


def test_progressive_outputs_preserve_legacy_names_and_absent_event_none(engine, monkeypatch):
    module = _prepare_module()
    from katrain.web.api.v1.endpoints.kifu import read_album_page

    monkeypatch.setenv("KIFU_STRICT_NAMES", "0")
    with Session(engine) as db:
        db.add(KifuPlayerName(player_id=17, lang="en", display_name="Legacy Go", status="verified"))
        db.get(KifuAlbum, 11).event = None
        db.commit()
        expected = {lang: read_album_page(db, lang=lang).items[0] for lang in prepared.NAME_LANGUAGES}
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        outputs = _outputs(conn)
        for lang, old in expected.items():
            row = outputs[11, lang]
            assert (row["player_black"], row["player_white"], row["event"]) == (
                old.display_player_black,
                old.display_player_white,
                old.display_event,
            )
        assert outputs[11, "en"]["event"] is None


def test_initial_final_dirty_reconciles_names_and_albums_inserted_behind_cursor(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _install(engine)
    # Commit each checkpoint, just as the initial CLI does.
    while True:
        with engine.begin() as conn:
            result = module.prepare_initial_batch(conn, batch_size=1)
            value = conn.execute(select(prepared.state)).mappings().one()
            if value["phase"] == "displays" and (value["cursor"] or {}).get("album") == 11:
                break
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=10, canonical_name="Early owner"))
        with Session(bind=conn) as db:
            evidence = _evidence(db, "player", 10, "en", "Early name")
            db.add(
                KifuPlayerName(
                    player_id=10,
                    lang="en",
                    display_name="Early name",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                )
            )
            db.add(
                KifuAlbum(
                    id=10,
                    black_player_id=10,
                    player_black="Early owner",
                    player_white="Other",
                    sgf_content="(;B[aa])",
                    source_path="behind-cursor.sgf",
                )
            )
            db.flush()
        module.maintain_after_write(conn)
        assert conn.execute(select(prepared.dirty)).first()
    with engine.begin() as conn:
        module.prepare_all(conn)
        assert _outputs(conn)[10, "en"]["player_black"] == "Early name"
        assert conn.execute(select(prepared.state.c.ready)).scalar_one()
        assert not conn.execute(select(prepared.dirty)).first()


@pytest.mark.parametrize("mutation", ["update_negative", "undo"])
def test_initial_display_resume_refreshes_names_invalidated_after_names_checkpoint(engine, monkeypatch, mutation):
    module = _prepare_module()
    from katrain.web.kifu import name_batch

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    if mutation == "undo":
        inventory, bundle, research = bound_player_bundle(engine)
        applied = apply_bundle(engine, bundle, registry(), inventory, research)
    else:
        with Session(engine) as db:
            db.add(KifuPlayerName(player_id=17, lang="en", display_name="Negative before", status="review"))
            db.commit()
    _install(engine)
    while True:
        with engine.begin() as conn:
            module.prepare_initial_batch(conn)
            value = conn.execute(select(prepared.state)).mappings().one()
            if value["phase"] == "displays":
                assert value["cursor"] == {"album": 0}
                break
    if mutation == "undo":
        name_batch.undo_batch(engine, applied["batch_id"])
    else:
        with name_batch._locked_write(engine) as conn:
            conn.execute(
                KifuPlayerName.__table__.update()
                .where(KifuPlayerName.player_id == 17)
                .values(display_name="Negative after")
            )
    with engine.begin() as conn:
        assert conn.execute(select(prepared.names.c.id).where(~prepared.names.c.valid)).first()
        dirty_before = {(row.input_kind, row.input_key) for row in conn.execute(select(prepared.dirty))}
        assert dirty_before
        module.prepare_initial_batch(conn, batch_size=1)
        value = conn.execute(select(prepared.state)).mappings().one()
        assert value["cursor"] == {"album": 11}
        assert not value["ready"] and not value["initial_coverage_complete"]
        assert {(row.input_kind, row.input_key) for row in conn.execute(select(prepared.dirty))} == dirty_before
        assert _outputs(conn)[11, "en"]["player_black"] == "Player name unverified"
        if mutation == "update_negative":
            row = conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "player")).mappings().one()
            assert row["display_name"] == "Negative after" and row["valid"] and not row["eligible"]
        else:
            assert not conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "player")).first()
    with engine.begin() as conn:
        module.prepare_all(conn)
        assert module.verify_coverage(conn)["ready"]


def test_ready_requires_negative_source_and_alias_coverage(engine, monkeypatch):
    module = _prepare_module()
    from katrain.web.core.models_db import KifuPlayerAlias

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        db.add(KifuPlayerName(player_id=17, lang="en", display_name="Rejected", status="verified"))
        db.add(KifuPlayerAlias(player_id=17, alias="Alias", normalized_alias="alias"))
        db.commit()
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        conn.execute(prepared.names.delete().where(prepared.names.c.match_class == "approved_exact"))
        with pytest.raises(module.PreparationError, match="unprepared source name"):
            module.prepare_changed(conn)
    with engine.begin() as conn:
        # Rebuild explicitly; then test alias coverage independently.
        conn.execute(prepared.state.update().values(phase="unprepared", initial_coverage_complete=False, ready=False))
        module.prepare_all(conn)
        conn.execute(prepared.names.delete().where(prepared.names.c.match_class == "legacy_alias"))
        with pytest.raises(module.PreparationError, match="unprepared source alias"):
            module.prepare_changed(conn)


def test_orphan_name_retains_free_q_eligibility_but_never_public_player_id(monkeypatch):
    module = _prepare_module()
    from tests.web_ui.test_kifu_name_api import _db
    from katrain.web.kifu.library_search import public_player_id

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        player = KifuPlayer(canonical_name="Owner")
        db.add(player)
        db.flush()
        player_id = player.id
        evidence = _evidence(db, "player", player_id, "en", "Orphan name")
        db.add(
            KifuPlayerName(
                player_id=player_id,
                lang="en",
                display_name="Orphan name",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()
        db.delete(player)
        db.commit()
        assert strict_matching_names(db, "Orphan name")[0] == {player_id}
        assert not public_player_id(db, player_id)
        db.close()
        _install(engine)
        with engine.begin() as conn:
            module.prepare_all(conn)
            row = (
                conn.execute(select(prepared.names).where(prepared.names.c.match_class == "approved_exact"))
                .mappings()
                .one()
            )
            assert row["eligible"] and not row["semantic"]["public_primary"]
            assert module.verify_coverage(conn)["ready"]
    finally:
        db.close()
        engine.dispose()


def test_orphan_event_name_keeps_search_eligibility_but_requires_owner_for_display(monkeypatch):
    module = _prepare_module()
    from tests.web_ui.test_kifu_name_api import _db
    from katrain.web.core.models_db import KifuEvent

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        event = KifuEvent(canonical_name="Original cup")
        db.add(event)
        db.flush()
        evidence = _evidence(db, "event", event.id, "en", "Approved cup")
        db.add(
            KifuEventName(
                event_id=event.id,
                lang="en",
                display_name="Approved cup",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.add(
            KifuAlbum(
                id=11,
                event="Original cup",
                event_id=event.id,
                player_black="Black",
                player_white="White",
                sgf_content="(;B[aa])",
                source_path="orphan-event.sgf",
            )
        )
        db.commit()
        db.delete(event)
        db.commit()
        expected = _old_outputs(db, db.query(KifuAlbum).all(), "en")[11][2]
        db.close()
        _install(engine)
        with engine.begin() as conn:
            module.prepare_all(conn)
            assert _outputs(conn)[11, "en"]["event"] == expected == "Event name unverified"
            row = conn.execute(select(prepared.names).where(prepared.names.c.name_kind == "event")).mappings().one()
            assert row["eligible"]
    finally:
        db.close()
        engine.dispose()


def test_language_change_removes_old_prepared_identity_and_reproves_new_token(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "cn", "Name")
        evidence_id = evidence.id
        name = KifuPlayerName(
            player_id=17,
            lang="cn",
            display_name="Name",
            status="verified",
            decision_kind="conventional",
            generation_rule_version="test-v1",
            revision=1,
            evidence_id=evidence.id,
        )
        db.add(name)
        db.commit()
        name_id = name.id
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        conn.execute(KifuPlayerName.__table__.update().where(KifuPlayerName.id == name_id).values(lang="tw"))
        conn.execute(
            KifuNameResearchEvidence.__table__.update()
            .where(KifuNameResearchEvidence.id == evidence_id)
            .values(lang="tw")
        )
        module.prepare_changed(conn)
        rows = (
            conn.execute(select(prepared.names).where(prepared.names.c.match_class == "approved_exact"))
            .mappings()
            .all()
        )
        assert len(rows) == 1 and rows[0]["lang"] == "tw" and rows[0]["eligible"] and rows[0]["valid"]
        assert _outputs(conn)[11, "cn"]["player_black"] == "棋手姓名待核实"
        assert _outputs(conn)[11, "tw"]["player_black"] == "Name"
        assert module.verify_coverage(conn)["ready"]


def test_incremental_publication_replay_and_undo_preserve_receipt_hash_and_prepared(tmp_path, monkeypatch):
    module = _prepare_module()
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish
    from katrain.kifu_ingest.catalog import undo_publication

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine = make_engine(tmp_path / "prepared-publication.db")
    try:
        value = manifest()
        _install(engine)
        with engine.begin() as conn:
            module.prepare_all(conn)
        receipt = publish(engine, value)
        receipt_sha = canonical_sha256(receipt)
        album_id = receipt["games"][0]["album_id"]
        with engine.connect() as conn:
            assert _outputs(conn)[album_id, "en"]["event"] == "Summer Cup"
            artifact = _image(conn, KifuNameBatch.__table__, receipt["batch_id"])
            artifact_sha = canonical_sha256(artifact)
            assert module.verify_coverage(conn)["ready"]
        assert canonical_sha256(publish(engine, value)) == receipt_sha
        with engine.connect() as conn:
            assert canonical_sha256(_image(conn, KifuNameBatch.__table__, receipt["batch_id"])) == artifact_sha
            assert module.verify_coverage(conn)["ready"]
        undo_publication(engine, receipt["batch_id"])
        with engine.connect() as conn:
            assert album_id not in {key[0] for key in _outputs(conn)}
            assert _outputs(conn)[11, "en"]["event"] == "Summer Cup"
            assert module.verify_coverage(conn)["ready"]
    finally:
        engine.dispose()


def test_same_token_old_new_rename_reproves_both_shared_groups(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = _shared_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        c_id = conn.execute(
            KifuPlayerName.__table__.insert().values(
                player_id=19,
                lang="cn",
                display_name="吴清源",
                status="verified",
                decision_kind="generated",
                generation_rule_version="user_authorized_first_pass_v1",
                revision=1,
            )
        ).inserted_primary_key[0]
        module.prepare_changed(conn)
        conn.execute(
            KifuPlayerName.__table__.update().where(KifuPlayerName.id == c_id).values(display_name="Other group")
        )
        module.prepare_changed(conn)
        rows = (
            conn.execute(
                select(prepared.names).where(prepared.names.c.name_kind == "player", prepared.names.c.eligible)
            )
            .mappings()
            .all()
        )
        assert {tuple(row["exact_group_authorized_ids"]) for row in rows} == {(17, 18)}
        conn.execute(KifuPlayerName.__table__.update().where(KifuPlayerName.id == c_id).values(display_name="吴清源"))
        module.prepare_changed(conn)
        rows = (
            conn.execute(
                select(prepared.names).where(prepared.names.c.name_kind == "player", prepared.names.c.eligible)
            )
            .mappings()
            .all()
        )
        assert {tuple(row["exact_group_authorized_ids"]) for row in rows} == {()}


def test_failed_writer_preparation_rolls_back_business_and_prepared_together(engine, monkeypatch, caplog):
    module = _prepare_module()
    from katrain.web.kifu.name_batch import catalog_snapshot_sha

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_player_bundle(engine)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
    before = catalog_snapshot_sha(engine)
    maintain = module.maintain_after_write
    with monkeypatch.context() as patch:
        patch.setattr(
            module, "maintain_after_write", lambda conn: maintain(conn, budget=module.PrepareBudget(max_seconds=0))
        )
        with pytest.raises(module.PreparationError, match="time budget exceeded"):
            apply_bundle(engine, bundle, registry(), inventory, research)
    assert catalog_snapshot_sha(engine) == before
    with engine.connect() as conn:
        assert not conn.execute(select(KifuNameBatch.id)).first()
        assert not conn.execute(select(KifuPlayerName.id)).first()
        assert _outputs(conn)[11, "cn"]["player_black"] == "棋手姓名待核实"
        assert module.verify_coverage(conn)["ready"]
    with caplog.at_level("INFO", logger="katrain.web.kifu.prepare_search"):
        apply_bundle(engine, bundle, registry(), inventory, research)
    assert "kifu_search_writer_prepare" in caplog.text
    assert "policy_signature" in caplog.text and "build_sha" in caplog.text
    assert "吴清源" not in caplog.text and "sgf_content" not in caplog.text


def test_raw_player_rank_context_drift_reproves_frozen_scope(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_raw_player_bundle(engine, five_languages=True)
    apply_bundle(engine, bundle, registry(), inventory, research)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        assert _outputs(conn)[12, "en"]["player_black"] == "Lee Wonhyuk"
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(black_rank="7p"))
        module.prepare_changed(conn)
        assert _outputs(conn)[12, "en"]["player_black"] == "Player name unverified"
        assert _outputs(conn)[15, "en"]["player_white"] == "Player name unverified"
        assert module.verify_coverage(conn)["ready"]


def test_explicit_full_rebuild_transfers_old_collection_dirty_and_keeps_new_dirty(engine, monkeypatch):
    module = _prepare_module()
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        conn.execute(prepared.state.update().values(enabled=True))
        with pytest.raises(module.PreparationError, match="disable"):
            module.begin_full_prepare(conn)
        conn.execute(prepared.state.update().values(enabled=False, ready=False))
        conn.execute(prepared.dirty.insert().values(input_kind="kifu_player_names", input_key="*", reason="TRUNCATE"))
        outcome = module.begin_full_prepare(conn)
        assert outcome["consumed_collections"] == 1
        value = conn.execute(select(prepared.state)).mappings().one()
        assert not value["ready"] and not value["initial_coverage_complete"] and value["phase"] == "unprepared"
        module.prepare_initial_batch(conn, batch_size=1)
        conn.execute(prepared.dirty.insert().values(input_kind="kifu_event_names", input_key="*", reason="TRUNCATE"))
    with pytest.raises(module.PreparationError, match="full prepare"):
        with engine.begin() as conn:
            module.prepare_all(conn)
    with engine.begin() as conn:
        assert conn.execute(select(prepared.dirty)).first()
        module.begin_full_prepare(conn)
        module.prepare_all(conn)
        assert module.verify_coverage(conn)["ready"]


def test_pg_real_name_writer_rollback_replay_and_undo_keep_business_sha(prepare_pg_engine, monkeypatch):
    module = _prepare_module()
    from katrain.web.kifu.name_batch import undo_batch

    engine = prepare_pg_engine
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inventory, bundle, research = bound_player_bundle(engine)
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
    maintain = module.maintain_after_write
    with monkeypatch.context() as patch:
        patch.setattr(
            module, "maintain_after_write", lambda conn: maintain(conn, budget=module.PrepareBudget(max_seconds=0))
        )
        with pytest.raises(module.PreparationError, match="time budget exceeded"):
            apply_bundle(engine, bundle, registry(), inventory, research)
    with engine.connect() as observer:
        assert not observer.execute(select(KifuNameBatch.id)).first()
        assert not observer.execute(select(KifuPlayerName.id)).first()
        assert module.verify_coverage(observer)["ready"]
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with engine.connect() as observer:
        image_sha = canonical_sha256(_image(observer, KifuNameBatch.__table__, applied["batch_id"]))
    replayed = apply_bundle(engine, bundle, registry(), inventory, research)
    assert replayed["status"] == "already_applied"
    with engine.connect() as observer:
        assert canonical_sha256(_image(observer, KifuNameBatch.__table__, applied["batch_id"])) == image_sha
        assert module.verify_coverage(observer)["ready"]
    undo_batch(engine, applied["batch_id"])
    with engine.connect() as observer:
        assert _outputs(observer)[11, "cn"]["player_black"] == "棋手姓名待核实"
        assert module.verify_coverage(observer)["ready"]


@pytest.mark.parametrize("kind", ["name", "selection"])
def test_emergency_undo_commits_revocation_and_dirty_when_normal_prepare_fails(engine, monkeypatch, capsys, kind):
    module = _prepare_module()
    from katrain.web.kifu import name_batch, event_selection
    from katrain.web.kifu.prepared_read import require_ready, PreparedSearchNotReady
    from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    if kind == "name":
        inventory, bundle, research = bound_player_bundle(engine)
        applied = apply_bundle(engine, bundle, registry(), inventory, research)
        undo = name_batch.undo_batch
        model = KifuNameBatch
    else:
        from katrain.web.core.models_db import KifuEventSelectionBatch

        with engine.begin() as conn:
            conn.execute(
                KifuAlbum.__table__.update()
                .where(KifuAlbum.id == 11)
                .values(
                    source="https://19x19.com",
                    source_path="data/kifu-album/19x19/one.sgf",
                    date_played="1934-10-01",
                    board_size=19,
                    sgf_content="(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Other]GC[Other | 1手])",
                )
            )
        applied = apply_reviewed_selection(engine, 11)
        undo, model = event_selection.undo_batch, KifuEventSelectionBatch
    _install(engine)
    with engine.begin() as conn:
        module.prepare_all(conn)
        conn.execute(prepared.state.update().values(enabled=True))
    maintain = module.maintain_after_write
    monkeypatch.setattr(
        module, "maintain_after_write", lambda conn: maintain(conn, budget=module.PrepareBudget(max_seconds=0))
    )
    with pytest.raises(module.PreparationError, match="time budget exceeded"):
        undo(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.execute(select(model.status).where(model.id == applied["batch_id"])).scalar_one() == "applied"
        assert module.verify_coverage(conn)["ready"]
    if kind == "name":
        from scripts.kifu_name_batch import main
    else:
        from scripts.kifu_event_selection import main
    assert (
        main(
            [
                "undo",
                "--database-url",
                str(engine.url),
                "--batch-id",
                str(applied["batch_id"]),
                "--emergency-invalidate-search",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "undone" and result["search_repair_required"]
    assert result["search_prepared_installed"] and not result["search_ready"]
    with engine.connect() as conn:
        assert conn.execute(select(model.status).where(model.id == applied["batch_id"])).scalar_one() == "undone"
        assert conn.execute(select(prepared.dirty)).first()
        with pytest.raises(PreparedSearchNotReady):
            require_ready(conn)
