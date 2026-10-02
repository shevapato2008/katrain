"""SQLite catalog rehearsals for imported, persisted transliteration approvals."""

import asyncio
from copy import deepcopy

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuEvent,
    KifuEventName,
    KifuNameBatch,
    KifuNameResearchEvidence,
    KifuPlayer,
    KifuPlayerName,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
)
from katrain.web.kifu import identity, name_transliteration
from katrain.web.kifu.name_batch import BatchError, apply_bundle, dry_run_bundle, undo_batch, approved_name_snapshot
from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_coverage import coverage_report
from katrain.web.kifu.name_inventory import build_inventory
from tests.web_ui.test_kifu_name_api import _evidence, _request
from tests.web_ui.test_kifu_name_batch import _v2_wrap
from tests.web_ui.test_kifu_name_transliteration import refresh_bindings, registry, transliteration_bundle

MODELS = {
    "player": (KifuPlayer, KifuPlayerName, "player_id", 17),
    "event": (KifuEvent, KifuEventName, "event_id", 3),
    "raw_player": (KifuRawPlayerValue, KifuRawPlayerName, "raw_player_id", 7),
    "raw_event": (KifuRawEventValue, KifuRawEventName, "raw_event_id", 8),
}


def catalog(kind="player", count=1):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    owner_model, _, _, owner_id = MODELS[kind]
    with Session(engine) as db:
        db.add(
            owner_model(
                **(
                    {
                        "id": owner_id,
                        "raw_value": "李元赫",
                        "review_status": "approved",
                        "category": "readable_unlinked" if kind == "raw_player" else "unclassified_pending",
                    }
                    if kind.startswith("raw_")
                    else {"id": owner_id, "canonical_name": "李元赫"}
                )
            )
        )
        db.flush()
        for number in range(count):
            db.add(
                KifuAlbum(
                    player_black="李元赫" if "player" in kind else "Black",
                    player_white="White",
                    black_player_id=owner_id if kind == "player" else None,
                    event="李元赫" if "event" in kind else None,
                    event_id=owner_id if kind == "event" else None,
                    sgf_content="(;PB[李元赫]PW[White];B[aa])",
                    source_path=f"transliteration-{number}.sgf",
                )
            )
        db.commit()
    proposed, anchors, snapshot = transliteration_bundle()
    owner = {"kind": kind, "id": owner_id}
    row = proposed["candidates"][0]
    row["owner"] = proposed["members"][0]["owner"] = owner
    anchors[0]["content"].update(owner=owner, entity_kind="event" if "event" in kind else "player")
    rule = proposed["transliteration"]["rules"][0]
    batch = proposed["transliteration"]["batches"][0]
    rule["content"]["entity_kind"] = batch["content"]["entity_kind"] = anchors[0]["content"]["entity_kind"]
    if kind.startswith("raw_"):
        row["raw_value"] = proposed["members"][0]["raw_value"] = anchors[0]["content"]["raw_value"] = "李元赫"
        batch["content"]["members"][0]["raw_value"] = "李元赫"
    refresh_bindings(proposed, anchors)
    row["name_preimage_sha256"] = None
    row["preimage_binding"] = {
        "actor_id": "binder",
        "actor_model": "gpt-6-sol",
        "captured_at": "2026-10-03T12:05:00Z",
        "bound_at": "2026-10-03T12:30:00Z",
        "name_preimage_sha256": None,
        "source_candidate_sha256": canonical_sha256(row),
        "capture_sha256": "d" * 64,
    }
    inventory = build_inventory(engine)
    proposed.update(inventory_format=inventory["inventory_format"], inventory_sha256=inventory["sha256"])
    return engine, proposed, anchors, inventory


@pytest.mark.parametrize("kind", list(MODELS))
def test_locked_apply_persists_batch_proof_repeats_without_changes_and_undoes(kind):
    engine, proposed, anchors, inventory = catalog(kind)
    try:
        candidate_before = deepcopy(proposed["candidates"][0])
        with Session(engine) as db:
            source_before = [
                (album.id, album.sgf_content, album.player_black, album.event) for album in db.query(KifuAlbum)
            ]
        assert (
            validate_bundle(proposed, registry(), inventory, anchors, approved_name_snapshot=[])["write_ready"] is True
        )
        assert dry_run_bundle(engine, proposed, registry(), inventory, anchors)["write_ready"] is True
        statements = []

        def record_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_sql)
        try:
            applied = apply_bundle(engine, proposed, registry(), inventory, anchors)
        finally:
            event.remove(engine, "before_cursor_execute", record_sql)
        assert statements.index("BEGIN IMMEDIATE") < next(
            index for index, sql in enumerate(statements) if "SELECT kifu_player_names." in sql
        )
        assert applied["status"] == "applied"
        with Session(engine) as db:
            evidence = db.query(KifuNameResearchEvidence).one()
            assert evidence.research_payload["candidate"] == candidate_before
            assert evidence.research_payload["transliteration"]["source_anchor"] == anchors[0]
            assert evidence.research_payload["transliteration"]["batch_id"] == applied["batch_id"]
        assert apply_bundle(engine, proposed, registry(), inventory, anchors)["change_count"] == 0
        assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
        with Session(engine) as db:
            assert db.query(MODELS[kind][1]).count() == 0
            assert db.query(KifuNameResearchEvidence).count() == 0
            assert source_before == [
                (album.id, album.sgf_content, album.player_black, album.event) for album in db.query(KifuAlbum)
            ]
    finally:
        engine.dispose()


def test_v2_new_raw_owner_ref_exact_repeat_preserves_signed_candidates_and_proofs():
    engine, proposed, anchors, _ = catalog("raw_player")
    try:
        with Session(engine) as db:
            db.query(KifuRawPlayerValue).delete()
            db.commit()
        inventory = build_inventory(engine)
        owner = {"kind": "raw_player", "ref": "li-yuanhe"}
        row = proposed["candidates"][0]
        row["owner"] = proposed["members"][0]["owner"] = anchors[0]["content"]["owner"] = owner
        refresh_bindings(proposed, anchors)
        binding = row.pop("preimage_binding")
        binding["source_candidate_sha256"] = canonical_sha256(row)
        row["preimage_binding"] = binding
        declaration = {
            "owner": owner,
            "create": {"raw_value": "李元赫", "category": "readable_unlinked"},
            "occurrence_album_ids": [1],
            "occurrence_sha256": canonical_sha256([1]),
            "category_review": {
                "status": "approved",
                "producer_id": "category-producer",
                "producer_model": "gpt-6-luna",
                "produced_at": "2026-10-03T10:00:00Z",
                "reviewer_id": "category-reviewer",
                "reviewer_model": "gpt-6-sol",
                "reviewed_at": "2026-10-03T11:00:00Z",
                "category_basis": "Original SGF player text is a readable unlinked name",
            },
        }
        proposed.update(inventory_sha256=inventory["sha256"])
        proposed = _v2_wrap(engine, inventory, proposed, [declaration], [])
        signed = deepcopy(proposed)
        applied = apply_bundle(engine, proposed, registry(), inventory, anchors)
        with Session(engine) as db:
            artifact = deepcopy(db.get(KifuNameBatch, applied["batch_id"]).reviewed_artifact)
            evidence_payload = deepcopy(db.query(KifuNameResearchEvidence).one().research_payload)
            owner_id = db.query(KifuRawPlayerValue).one().id
        assert artifact["resolved_refs"] == {"raw_player:@li-yuanhe": owner_id}
        repeated = apply_bundle(engine, proposed, registry(), inventory, anchors)
        assert repeated == {"status": "already_applied", "batch_id": applied["batch_id"], "change_count": 0}
        assert proposed == signed
        with Session(engine) as db:
            assert db.get(KifuNameBatch, applied["batch_id"]).reviewed_artifact == artifact
            assert db.query(KifuNameResearchEvidence).one().research_payload == evidence_payload
            assert evidence_payload["candidate"] == signed["candidates"][0]
            assert db.query(KifuRawPlayerValue).one().id == owner_id
            assert db.query(KifuRawPlayerName).count() == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind", list(MODELS))
def test_display_search_and_coverage_use_persisted_batch_approval_in_bounded_queries(monkeypatch, kind):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, proposed, anchors, inventory = catalog(kind, count=20)
    try:
        applied = apply_bundle(engine, proposed, registry(), inventory, anchors)
        monkeypatch.setattr(
            name_transliteration, "render_reading", lambda *_: pytest.fail("request rendered transliteration")
        )
        with Session(engine) as db:
            statements = []

            def record_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
                statements.append(statement)

            event.listen(engine, "before_cursor_execute", record_sql)
            try:
                page = asyncio.run(
                    kifu.list_kifu_albums(_request(), q="Ли Юаньхэ", page=1, page_size=20, lang="ru", db=db)
                )
            finally:
                event.remove(engine, "before_cursor_execute", record_sql)
            assert page.total == 20
            assert len(statements) <= 18
            slot = "display_player_black" if "player" in kind else "display_event"
            assert all(getattr(item, slot) == "Ли Юаньхэ" for item in page.items)
            detail = asyncio.run(kifu.get_kifu_album(_request(), page.items[0].id, lang="ru", db=db))
            assert getattr(detail, slot) == "Ли Юаньхэ"
            other_language = asyncio.run(
                kifu.list_kifu_albums(_request(), q="Ли Юаньхэ", page=1, page_size=20, lang="cn", db=db)
            )
            assert other_language.total == 20
            assert all(
                getattr(item, slot) == ("棋手姓名待核实" if "player" in kind else "赛事名称待核实")
                for item in other_language.items
            )
        result = coverage_report(engine, inventory, languages=("ru",))
        assert result["languages"]["ru"]["by_decision"]["transliterated"] == 20
        with engine.begin() as conn:
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == applied["batch_id"])
                .values(status="partial_undo")
            )
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q="Ли Юаньхэ", page=1, page_size=20, lang="ru", db=db))
            assert page.total == 0
            albums = db.query(KifuAlbum).all()
            approvals = identity.strict_slot_approvals(db, albums, "ru")
            assert all(values[0 if "player" in kind else 2] is None for values in approvals.values())
        result = coverage_report(engine, inventory, languages=("ru",))
        assert result["languages"]["ru"]["by_decision"].get("transliterated", 0) == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "drift", ["anchor", "batch_artifact", "rule", "candidate", "revision", "lang", "raw_value", "research"]
)
def test_persisted_dependency_drift_is_rejected_for_display_search_and_coverage(monkeypatch, drift):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    kind = "raw_player" if drift == "raw_value" else "player"
    engine, proposed, anchors, inventory = catalog(kind)
    try:
        applied = apply_bundle(engine, proposed, registry(), inventory, anchors)
        with Session(engine) as db:
            evidence = db.query(KifuNameResearchEvidence).one()
            payload = deepcopy(evidence.research_payload)
            batch = db.get(KifuNameBatch, applied["batch_id"])
            if drift == "anchor":
                payload["transliteration"]["source_anchor"]["content"]["reading_words"] = [["li"]]
            elif drift in {"batch_artifact", "rule"}:
                artifact = deepcopy(batch.reviewed_artifact)
                if drift == "batch_artifact":
                    artifact["bundle"]["transliteration"]["batches"][0]["content"]["members"] = []
                else:
                    artifact["bundle"]["transliteration"]["rules"][0]["content"]["token_map"]["li"] = "лю"
                batch.reviewed_artifact = artifact
            elif drift == "candidate":
                payload["candidate"]["source_anchor_sha256"] = "0" * 64
            elif drift == "research":
                payload["research"] = {"scope_status": "not_found_in_scope"}
            elif drift == "revision":
                evidence.revision += 1
            elif drift == "lang":
                evidence.lang = "fr"
            elif drift == "raw_value":
                db.query(KifuRawPlayerValue).one().raw_value = "Another raw"
            evidence.research_payload = payload
            db.commit()
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q="Ли Юаньхэ", page=1, page_size=20, lang="ru", db=db))
            assert page.total == 0
            album = db.query(KifuAlbum).one()
            detail = asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="ru", db=db))
            assert detail.display_player_black == "Имя игрока не проверено"
        assert (
            coverage_report(engine, inventory, languages=("ru",))["languages"]["ru"]["by_decision"].get(
                "transliterated", 0
            )
            == 0
        )
    finally:
        engine.dispose()


def add_conventional(engine, owner_id=17, display="Confirmed variant"):
    with Session(engine) as db:
        if owner_id != 17:
            db.add(KifuPlayer(id=owner_id, canonical_name="Another player"))
            db.flush()
        evidence = _evidence(db, "player", owner_id, "ru", display)
        db.add(
            KifuPlayerName(
                player_id=owner_id,
                lang="ru",
                display_name=display,
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()


def sign_current_snapshot(proposed, anchors, engine):
    snapshot = approved_name_snapshot(engine)
    proposed["transliteration"]["batches"][0]["content"]["approved_name_snapshot_sha256"] = canonical_sha256(snapshot)
    refresh_bindings(proposed, anchors)
    return snapshot


def test_lock_time_snapshot_rejects_names_added_after_batch_was_signed():
    engine, proposed, anchors, inventory = catalog()
    try:
        add_conventional(engine)
        before = approved_name_snapshot(engine)
        with pytest.raises(BatchError, match="snapshot hash mismatch"):
            apply_bundle(engine, proposed, registry(), inventory, anchors)
        assert approved_name_snapshot(engine) == before
        with Session(engine) as db:
            assert db.query(KifuNameBatch).count() == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "owner_id,display,expected", [(17, "Confirmed variant", "conventional"), (18, "Ли Юаньхэ", "collides")]
)
def test_current_snapshot_blocks_conventional_replacement_and_cross_batch_collision(owner_id, display, expected):
    engine, proposed, anchors, inventory = catalog()
    try:
        add_conventional(engine, owner_id=owner_id, display=display)
        before = sign_current_snapshot(proposed, anchors, engine)
        with pytest.raises(BatchError, match=expected):
            apply_bundle(engine, proposed, registry(), inventory, anchors)
        assert approved_name_snapshot(engine) == before
        with Session(engine) as db:
            assert db.query(KifuNameBatch).count() == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("drift", ["name_metadata", "evidence_metadata"])
def test_snapshot_pins_complete_current_approved_name_and_evidence_images(drift):
    engine, proposed, anchors, inventory = catalog()
    try:
        add_conventional(engine, owner_id=18)
        sign_current_snapshot(proposed, anchors, engine)
        with Session(engine) as db:
            if drift == "name_metadata":
                db.query(KifuPlayerName).one().reference_url = "https://changed.example.org"
            else:
                db.query(KifuNameResearchEvidence).one().research_payload = {"changed": True}
            db.commit()
        with pytest.raises(BatchError, match="snapshot hash mismatch"):
            apply_bundle(engine, proposed, registry(), inventory, anchors)
    finally:
        engine.dispose()


def test_repeat_rejects_changed_evidence_and_conditional_undo_keeps_later_manual_edit():
    engine, proposed, anchors, inventory = catalog()
    try:
        applied = apply_bundle(engine, proposed, registry(), inventory, anchors)
        with Session(engine) as db:
            db.query(KifuPlayerName).one().display_name = "Later manual edit"
            db.commit()
        with pytest.raises(BatchError, match="after-image"):
            apply_bundle(engine, proposed, registry(), inventory, anchors)
        assert undo_batch(engine, applied["batch_id"])["status"] == "partial_undo"
        with Session(engine) as db:
            assert db.query(KifuPlayerName).one().display_name == "Later manual edit"
            assert db.query(KifuNameResearchEvidence).count() == 1
    finally:
        engine.dispose()
