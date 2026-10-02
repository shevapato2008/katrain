"""Reviewed name bundles apply atomically and undo only their own unchanged writes."""

from copy import deepcopy
import hashlib
import json

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    Base, KifuAlbum, KifuAlbumEventSelection, KifuEvent, KifuEventName, KifuEventSelectionBatch,
    KifuNameBatch, KifuNameChange, KifuNameResearchEvidence,
    KifuNameSourceRegistry, KifuPlayer, KifuPlayerName, KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.name_batch import (
    BatchError, apply_bundle, batch_status, catalog_snapshot_sha, dry_run_bundle,
    name_preimage_sha256, undo_batch,
)
from katrain.web.kifu.name_candidates import canonical_sha256, classification_template_sha256, identity_scope_sha256, validate_bundle
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.identity import live_event_selections
from katrain.web.kifu.name_parse import parse_event
from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
from scripts.kifu_name_batch import main


LANGS = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")


def bind_fixture_candidate(row):
    row["preimage_binding"] = {
        "actor_id": "fixture-binder-3", "actor_model": "gpt-6.1-sol",
        "captured_at": "2026-10-02T10:05:00Z", "bound_at": "2026-10-02T10:30:00Z",
        "name_preimage_sha256": row["name_preimage_sha256"],
        "source_candidate_sha256": canonical_sha256(row),
        "capture_sha256": hashlib.sha256(b"synthetic fixture preimage capture").hexdigest(),
    }
    return row


def set_fixture_preimage(row, preimage):
    row["name_preimage_sha256"] = preimage
    row["preimage_binding"]["name_preimage_sha256"] = preimage


def registry():
    return {
        "version": "test-1",
        "language_tags": {lang: {"cn": "zh-Hans", "tw": "zh-Hant", "jp": "ja", "ua": "uk"}.get(lang, lang)
                          for lang in LANGS},
        "sources": [{"id": "go", "tier": "language_go", "home_url": "https://example.org/", "language": "ru"}],
        "language_scopes": {lang: {"required_source_ids": ["go"], "complete_for_negative_claims": False}
                            for lang in LANGS},
    }


@pytest.fixture
def engine(tmp_path):
    db = create_engine(f"sqlite:///{tmp_path / 'names.db'}")

    @event.listens_for(db, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db)
    with db.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=17, canonical_name="吴清源"))
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=7, raw_value="GNUGo3.8", category="program_source_label", review_status="approved"))
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=8, raw_value="Other", category="unclassified_pending", review_status="pending"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=11, black_player_id=17, player_black="吴清源九段", player_white="Unknown", event="GNUGo3.8",
            sgf_content="(;FF[4]PB[吴清源九段]PW[Unknown]EV[GNUGo3.8])", source_path="one.sgf"))
    yield db
    db.dispose()


def approved_bundle(inventory):
    owner = {"kind": "raw_event", "id": 7}
    member = {"owner": owner, "lang": "ru", "raw_value": "GNUGo3.8"}
    candidate = bind_fixture_candidate({
        **member, "display_name": "", "decision_kind": "hidden", "research_sha256": "",
        "name_preimage_sha256": None,
        "generation_rule_version": "classification-v1",
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-02T10:01:00Z", "review_status": "approved",
        "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
        "reviewed_at": "2026-10-02T11:00:00Z", "review_conclusion": "Checked exact program label",
        "template_review": {
            "version": "classification-v1", "lang": "ru", "sha256": classification_template_sha256("ru"),
            "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
            "reviewed_at": "2026-10-02T10:30:00Z", "conclusion": "Checked this language template",
        },
    })
    return {
        "bundle_format": 1, "inventory_format": 2, "inventory_sha256": inventory["sha256"],
        "registry_version": "test-1", "registry_sha256": registry_sha256(registry()),
        "rule_version": "candidate-v1", "members": [member],
        "member_set_sha256": canonical_sha256([member]), "candidates": [candidate],
    }


def player_bundle(inventory, owner_id=17, display="Го Сэйгэн"):
    owner = {"kind": "player", "id": owner_id}
    member = {"owner": owner, "lang": "ru"}
    check = {
        "owner": owner, "source_id": "go", "query": "Go Seigen", "status": "found",
        "url": "https://example.org/go", "fetched_at": "2026-10-02T10:00:00Z", "http_status": 200,
        "body_sha256": hashlib.sha256(display.encode()).hexdigest(),
        "body_excerpt": f"Player profile {display}", "observed_lang": "ru",
        "language_basis": "reviewed_text", "candidate_name": display,
        "identity_basis": "Official profile matches historical player ID",
    }
    research = {
        "owner": owner, "lang": "ru", "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()), "scope_status": "found",
        "candidate_name": display, "source_checks": [check], "original_name": "呉清源",
        "original_language": "ja", "original_language_basis_url": "https://example.org/go",
        "reading": "ご せいげん", "reading_basis_url": "https://example.org/go",
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    candidate = bind_fixture_candidate({
        **member, "display_name": display, "decision_kind": "conventional",
        "name_preimage_sha256": None,
        "research_sha256": canonical_sha256(research), "generation_rule_version": "none",
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-02T10:01:00Z", "review_status": "approved",
        "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
        "reviewed_at": "2026-10-02T11:00:00Z", "review_conclusion": "Confirmed exact Russian professional profile",
    })
    return {
        "bundle_format": 1, "inventory_format": 2, "inventory_sha256": inventory["sha256"],
        "registry_version": "test-1", "registry_sha256": registry_sha256(registry()),
        "rule_version": "candidate-v1", "members": [member],
        "member_set_sha256": canonical_sha256([member]), "candidates": [candidate],
    }, [research]


def counts(engine):
    with engine.connect() as conn:
        return tuple(conn.scalar(select(func.count()).select_from(model)) for model in (
            KifuNameSourceRegistry, KifuNameResearchEvidence, KifuRawEventName, KifuNameBatch, KifuNameChange))


def test_dry_run_is_strictly_read_only_and_reports_scope(engine):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    before = counts(engine)
    report = dry_run_bundle(engine, bundle, registry(), inv, [])
    assert report["ready"] and report["affected_albums"] == [11]
    assert report["candidate_count"] == 1
    assert counts(engine) == before == (0, 0, 0, 0, 0)


def test_selected_only_raw_event_can_be_imported_and_live_scope_is_rechecked(engine):
    raw = "Selected Cup"
    sgf = ("(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Selected Cup]"
           "GC[Selected Cup | 194 moves])")
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            sgf_content=sgf, source="https://19x19.com", source_path="data/kifu-album/19x19/a.sgf"))
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=9, raw_value=raw, category=parse_event(raw, None).category, review_status="approved"))
    selection_batch_id = apply_reviewed_selection(engine, 11)["batch_id"]
    inv = build_inventory(engine)
    owner = {"kind": "raw_event", "id": 9}
    base, records = player_bundle(inv)
    member = {"owner": owner, "lang": "ru", "raw_value": raw}
    base["members"] = [member]
    base["member_set_sha256"] = canonical_sha256([member])
    base["inventory_format"] = 3
    base["candidates"][0].update(member, display_name="Кубок")
    record = records[0]
    record.update(owner=owner, candidate_name="Кубок", original_name=raw, reading=raw)
    record["source_checks"][0].update(
        owner=owner, candidate_name="Кубок", body_excerpt="Tournament profile: Кубок")
    base["candidates"][0]["research_sha256"] = canonical_sha256(record)
    declaration = {"owner": owner, "preimage": {"raw_value": raw},
                   "occurrence_album_ids": [11], "occurrence_sha256": canonical_sha256([11])}
    reviewed = _v2_wrap(engine, inv, base, [declaration], [])
    reviewed["bundle_format"] = 3
    assert dry_run_bundle(engine, reviewed, registry(), inv, records)["affected_albums"] == [11]
    with engine.begin() as conn:
        conn.execute(KifuAlbumEventSelection.__table__.update().where(KifuAlbumEventSelection.album_id == 11)
                     .values(selected_raw="Changed Cup"))
    with pytest.raises(BatchError, match="snapshot|selection"):
        dry_run_bundle(engine, reviewed, registry(), inv, records)
    with engine.begin() as conn:
        conn.execute(KifuAlbumEventSelection.__table__.update().where(KifuAlbumEventSelection.album_id == 11)
                     .values(selected_raw=raw))
        conn.execute(KifuEventSelectionBatch.__table__.update().where(KifuEventSelectionBatch.id == selection_batch_id)
                     .values(status="undone"))
    with pytest.raises(BatchError, match="snapshot|selection"):
        dry_run_bundle(engine, reviewed, registry(), inv, records)
    with engine.begin() as conn:
        conn.execute(KifuEventSelectionBatch.__table__.update().where(KifuEventSelectionBatch.id == selection_batch_id)
                     .values(status="applied"))
        pinned = dict(conn.execute(select(KifuAlbumEventSelection.__table__)).mappings().one())
        conn.execute(KifuAlbumEventSelection.__table__.delete().where(KifuAlbumEventSelection.album_id == 11))
    with pytest.raises(BatchError, match="snapshot|selection"):
        dry_run_bundle(engine, reviewed, registry(), inv, records)
    with engine.begin() as conn:
        conn.execute(KifuAlbumEventSelection.__table__.insert().values(**pinned))
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(sgf_content=sgf + "\n"))
    with pytest.raises(BatchError, match="snapshot|selection"):
        dry_run_bundle(engine, reviewed, registry(), inv, records)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(sgf_content=sgf))
    assert apply_bundle(engine, reviewed, registry(), inv, records)["status"] == "applied"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventName.display_name).where(KifuRawEventName.raw_event_id == 9)) == "Кубок"
        assert conn.scalar(select(KifuAlbum.event).where(KifuAlbum.id == 11)) == "GNUGo3.8"


def test_apply_is_atomic_audited_idempotent_and_preserves_sgf(engine):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    with engine.connect() as conn:
        original = conn.execute(select(KifuAlbum.sgf_content, KifuAlbum.player_black, KifuAlbum.event)
                                .where(KifuAlbum.id == 11)).one()
    first = apply_bundle(engine, bundle, registry(), inv, [])
    assert first["status"] == "applied" and first["change_count"] >= 2
    second = apply_bundle(engine, bundle, registry(), inv, [])
    assert second["status"] == "already_applied" and second["batch_id"] == first["batch_id"]
    with engine.connect() as conn:
        assert conn.execute(select(KifuAlbum.sgf_content, KifuAlbum.player_black, KifuAlbum.event)
                            .where(KifuAlbum.id == 11)).one() == original
        name = conn.execute(select(KifuRawEventName).where(KifuRawEventName.raw_event_id == 7)).mappings().one()
        evidence = conn.execute(select(KifuNameResearchEvidence)
                                .where(KifuNameResearchEvidence.id == name["evidence_id"])).mappings().one()
        assert name["display_name"] == "" and name["status"] == "verified"
        assert evidence["review_status"] == "approved" and evidence["raw_event_id"] == 7
        assert evidence["lang"] == name["lang"] and evidence["candidate_name"] == name["display_name"]
        changes = conn.execute(select(KifuNameChange).where(KifuNameChange.batch_id == first["batch_id"])) \
            .mappings().all()
        assert any(change["target_table"] == "kifu_raw_event_names" and change["before_image"] is None
                   and change["after_image"]["evidence_id"] == evidence["id"] for change in changes)


def test_stale_snapshot_and_wrong_raw_id_abort_without_writes(engine):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    wrong = deepcopy(bundle)
    wrong["members"][0]["owner"]["id"] = 8
    wrong["candidates"][0]["owner"]["id"] = 8
    wrong["member_set_sha256"] = canonical_sha256(wrong["members"])
    with pytest.raises(BatchError, match="raw ID"):
        apply_bundle(engine, wrong, registry(), inv, [])
    assert counts(engine) == (0, 0, 0, 0, 0)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(event="changed"))
    with pytest.raises(BatchError, match="snapshot"):
        apply_bundle(engine, bundle, registry(), inv, [])
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_name_preimage_is_required_for_database_inspection(engine):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    del bundle["candidates"][0]["name_preimage_sha256"]
    report = validate_bundle(bundle, registry(), inv, [])
    assert report["ready"] and not report["write_ready"]
    assert "name preimage missing" in report["write_errors"][0]
    with pytest.raises(BatchError, match="name preimage"):
        dry_run_bundle(engine, bundle, registry(), inv, [])
    with pytest.raises(BatchError, match="name preimage"):
        apply_bundle(engine, bundle, registry(), inv, [])
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_name_preimage_rejects_malformed_digest(engine):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    bundle["candidates"][0]["name_preimage_sha256"] = "A" * 64
    report = validate_bundle(bundle, registry(), inv, [])
    assert report["ready"] and not report["write_ready"]
    with pytest.raises(BatchError, match="name preimage"):
        dry_run_bundle(engine, bundle, registry(), inv, [])
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_name_absent_at_review_then_inserted_aborts_without_writes(engine):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    assert dry_run_bundle(engine, bundle, registry(), inv, [])["ready"]
    with engine.begin() as conn:
        conn.execute(KifuRawEventName.__table__.insert().values(
            raw_event_id=7, lang="ru", display_name="Later edit", status="review"))
    with pytest.raises(BatchError, match="name preimage"):
        apply_bundle(engine, bundle, registry(), inv, [])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventName.display_name)) == "Later edit"
    assert counts(engine) == (0, 0, 1, 0, 0)


def test_existing_name_modified_after_review_aborts_without_writes(engine):
    with engine.begin() as conn:
        conn.execute(KifuRawEventName.__table__.insert().values(
            raw_event_id=7, lang="ru", display_name="Old", status="review"))
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    set_fixture_preimage(bundle["candidates"][0], name_preimage_sha256(
        engine, {"kind": "raw_event", "id": 7}, "ru"))
    assert dry_run_bundle(engine, bundle, registry(), inv, [])["ready"]
    with engine.begin() as conn:
        conn.execute(KifuRawEventName.__table__.update().where(KifuRawEventName.raw_event_id == 7)
                     .values(display_name="Curator's edit"))
    with pytest.raises(BatchError, match="name preimage"):
        apply_bundle(engine, bundle, registry(), inv, [])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventName.display_name)) == "Curator's edit"
    assert counts(engine) == (0, 0, 1, 0, 0)


def test_existing_name_hash_covers_reference_and_row_identity(engine):
    with engine.begin() as conn:
        conn.execute(KifuPlayerName.__table__.insert().values(
            id=22, player_id=17, lang="ru", display_name="Old", status="review",
            reference_url="https://example.org/old"))
    inv = build_inventory(engine)
    bundle, research = player_bundle(inv)
    set_fixture_preimage(bundle["candidates"][0], name_preimage_sha256(
        engine, {"kind": "player", "id": 17}, "ru"))
    assert dry_run_bundle(engine, bundle, registry(), inv, research)["ready"]
    with engine.begin() as conn:
        conn.execute(KifuPlayerName.__table__.update().where(KifuPlayerName.id == 22)
                     .values(reference_url="https://example.org/new"))
    with pytest.raises(BatchError, match="name preimage"):
        apply_bundle(engine, bundle, registry(), inv, research)
    with engine.begin() as conn:
        conn.execute(KifuPlayerName.__table__.delete().where(KifuPlayerName.id == 22))
        conn.execute(KifuPlayerName.__table__.insert().values(
            id=23, player_id=17, lang="ru", display_name="Old", status="review",
            reference_url="https://example.org/old"))
    with pytest.raises(BatchError, match="name preimage"):
        apply_bundle(engine, bundle, registry(), inv, research)
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuNameBatch)) == 0


def test_matching_existing_name_preimage_allows_audited_update_and_undo(engine):
    with engine.begin() as conn:
        conn.execute(KifuRawEventName.__table__.insert().values(
            raw_event_id=7, lang="ru", display_name="Prior review", status="review"))
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    set_fixture_preimage(bundle["candidates"][0], name_preimage_sha256(
        engine, {"kind": "raw_event", "id": 7}, "ru"))
    applied = apply_bundle(engine, bundle, registry(), inv, [])
    assert applied["status"] == "applied"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventName.display_name)) == ""
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventName.display_name)) == "Prior review"


def test_unrelated_name_change_does_not_stale_reviewed_name(engine):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    with engine.begin() as conn:
        conn.execute(KifuRawEventName.__table__.insert().values(
            raw_event_id=8, lang="ru", display_name="Other", status="review"))
    result = apply_bundle(engine, bundle, registry(), inv, [])
    assert result["status"] == "applied"


def test_failed_mid_batch_rolls_back_every_table(engine, monkeypatch):
    from katrain.web.kifu import name_batch

    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    original = name_batch._apply_candidate

    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected failure")

    monkeypatch.setattr(name_batch, "_apply_candidate", fail_after_write)
    with pytest.raises(RuntimeError, match="injected"):
        apply_bundle(engine, bundle, registry(), inv, [])
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_undo_uses_after_image_compare_and_swap(engine):
    inv = build_inventory(engine)
    applied = apply_bundle(engine, approved_bundle(inv), registry(), inv, [])
    undone = undo_batch(engine, applied["batch_id"])
    assert undone["status"] == "undone" and undone["reverted"] == applied["change_count"]
    assert counts(engine) == (1, 0, 0, 1, applied["change_count"])
    assert batch_status(engine, applied["batch_id"])["status"] == "undone"


def test_undo_preserves_later_user_edit_and_reports_partial(engine):
    inv = build_inventory(engine)
    applied = apply_bundle(engine, approved_bundle(inv), registry(), inv, [])
    with engine.begin() as conn:
        conn.execute(KifuRawEventName.__table__.update().where(KifuRawEventName.raw_event_id == 7)
                     .values(display_name="Later user edit"))
    undone = undo_batch(engine, applied["batch_id"])
    assert undone["status"] == "partial_undo" and undone["skipped"] >= 1
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventName.display_name).where(KifuRawEventName.raw_event_id == 7)) == "Later user edit"
        assert conn.scalar(select(func.count()).select_from(KifuNameResearchEvidence)) == 1


def test_undo_preserves_evidence_on_default_sqlite_cli_engine(engine):
    # The CLI constructs a plain engine, unlike this test module's FK-enabled fixture.
    plain_engine = create_engine(engine.url)
    try:
        inventory = build_inventory(plain_engine)
        bundle, evidence = player_bundle(inventory)
        applied = apply_bundle(plain_engine, bundle, registry(), inventory, evidence)
        with plain_engine.begin() as conn:
            conn.execute(KifuPlayerName.__table__.update().where(
                KifuPlayerName.player_id == 17, KifuPlayerName.lang == "ru"
            ).values(display_name="later editor change"))
        undone = undo_batch(plain_engine, applied["batch_id"])
        assert undone["status"] == "partial_undo"
        with plain_engine.connect() as conn:
            name = conn.execute(select(KifuPlayerName).where(
                KifuPlayerName.player_id == 17, KifuPlayerName.lang == "ru"
            )).mappings().one()
            assert name["evidence_id"] is not None
            assert conn.scalar(select(func.count()).select_from(KifuNameResearchEvidence)) == 1
            assert conn.execute(text("PRAGMA foreign_key_check")).all() == []
    finally:
        plain_engine.dispose()


def test_conventional_name_evidence_matches_verified_row_and_collision_is_blocked(engine):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=18, canonical_name="Other player"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, black_player_id=18, player_black="Other player", player_white="Unknown",
            event=None, sgf_content="(;PB[Other player]PW[Unknown])", source_path="two.sgf"))
    inv = build_inventory(engine)
    first, first_research = player_bundle(inv)
    second, second_research = player_bundle(inv, owner_id=18, display="Го Сэйгэн")
    applied = apply_bundle(engine, first, registry(), inv, first_research)
    with engine.connect() as conn:
        name = conn.execute(select(KifuPlayerName).where(KifuPlayerName.player_id == 17)).mappings().one()
        evidence = conn.execute(select(KifuNameResearchEvidence).where(
            KifuNameResearchEvidence.id == name["evidence_id"])).mappings().one()
        assert name["verified_at"] == evidence["reviewed_at"]
        assert (
            name["player_id"], name["lang"], name["display_name"], name["decision_kind"], name["revision"]
        ) == (
            evidence["player_id"], evidence["lang"], evidence["candidate_name"],
            evidence["decision_kind"], evidence["revision"]
        )
    with pytest.raises(BatchError, match="collision"):
        apply_bundle(engine, second, registry(), inv, second_research)
    assert batch_status(engine, applied["batch_id"])["status"] == "applied"
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuPlayerName)) == 1


def test_cli_validate_and_dry_run_leave_database_untouched(engine, tmp_path, capsys):
    inv = build_inventory(engine)
    bundle = approved_bundle(inv)
    paths = {kind: tmp_path / f"{kind}.json" for kind in ("bundle", "registry", "inventory", "evidence")}
    for kind, value in (("bundle", bundle), ("registry", registry()), ("inventory", inv)):
        paths[kind].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    paths["evidence"].write_text("", encoding="utf-8")
    inputs = ["--bundle", str(paths["bundle"]), "--registry", str(paths["registry"]),
              "--inventory", str(paths["inventory"]), "--evidence", str(paths["evidence"])]
    assert main(["validate", *inputs]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["ready"] and validated["write_ready"]
    assert main(["dry-run", *inputs, "--database-url", str(engine.url)]) == 0
    assert json.loads(capsys.readouterr().out)["affected_albums"] == [11]
    assert counts(engine) == (0, 0, 0, 0, 0)
    del bundle["candidates"][0]["name_preimage_sha256"]
    paths["bundle"].write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    assert main(["validate", *inputs]) == 1
    legacy = json.loads(capsys.readouterr().out)
    assert legacy["ready"] and not legacy["write_ready"]


def _v2_wrap(engine, inventory, bundle, owners, links):
    result = deepcopy(bundle)
    result.update(bundle_format=2, catalog_sha256=catalog_snapshot_sha(engine), owners=owners,
                  owner_set_sha256=canonical_sha256(owners), album_links=links,
                  link_set_sha256=canonical_sha256(links))
    groups = {}
    for link in links:
        field = {"black": "player_black", "white": "player_white", "event": "event"}[link["slot"]]
        key = (canonical_sha256(link["target"]), link["expected"][field])
        groups.setdefault(key, []).append(link)
    for group in groups.values():
        declaration = next(item for item in owners if item["owner"] == group[0]["target"])
        for link in group:
            link["identity_review"]["scope_frozen_at"] = "2026-10-02T10:30:00Z"
        scope_hash = identity_scope_sha256(result, group, declaration)
        for link in group:
            link["identity_review"]["scope_sha256"] = scope_hash
    result["link_set_sha256"] = canonical_sha256(links)
    return result


def _identity_link(engine, inventory, album_id, slot, target):
    columns = inventory["association_columns"]
    album = next(dict(zip(columns, row)) for row in inventory["album_associations"] if row[0] == album_id)
    context = {key: album[key] for key in (
        "player_black", "player_white", "event", "date_played", "round_name", "black_rank", "white_rank")}
    context["old_id"] = album[{"black": "black_player_id", "white": "white_player_id", "event": "event_id"}[slot]]
    raw = album[{"black": "player_black", "white": "player_white", "event": "event"}[slot]]
    compared = ("event",) if slot == "event" else ("black", "white")
    scope = sorted([other["id"], other_slot] for row in inventory["album_associations"]
                   for other in [dict(zip(columns, row))] for other_slot in compared
                   if other[{"black": "player_black", "white": "player_white", "event": "event"}[other_slot]] == raw)
    review = {
        "status": "approved", "producer_id": "mapper-1", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-02T10:00:00Z", "reviewer_id": "mapper-2",
        "reviewer_model": "gpt-6-luna", "reviewed_at": "2026-10-02T11:00:00Z",
        "identity_basis": "Original names and source record identify the exact person or event",
        "review_conclusion": "Checked source record and exact original name",
        "source_checks": [{"url": "https://example.org/record", "body_sha256": "a" * 64,
                           "body_excerpt": "Original match record", "identity_match": "Same source record"}],
    }
    if slot == "event":
        review["event_period_basis"] = "This event name was used in the recorded year"
    with engine.connect() as conn:
        sgf_content = conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == album_id))
    return {"album_id": album_id, "slot": slot, "association_sha256": canonical_sha256(album),
            "production_sgf_sha256": hashlib.sha256(sgf_content.encode("utf-8")).hexdigest(),
            "expected": context, "raw_scope_sha256": canonical_sha256(scope),
            "target": target, "identity_review": review}


def test_v2_new_raw_owner_fixture_dry_run_apply_and_undo(engine):
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Alpha", player_white="Beta", event="GNUGo4.0",
            sgf_content="(;PB[Alpha]PW[Beta]EV[GNUGo4.0])", source_path="two.sgf"))
    inv = build_inventory(engine)
    owner = {"kind": "raw_event", "ref": "program-four"}
    ids = [12]
    declaration = {
        "owner": owner, "create": {"raw_value": "GNUGo4.0", "category": "program_source_label"},
        "occurrence_album_ids": ids, "occurrence_sha256": canonical_sha256(ids),
        "category_review": {"status": "approved", "producer_id": "researcher-1",
                            "producer_model": "gpt-6-luna", "produced_at": "2026-10-02T10:00:00Z",
                            "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
                            "reviewed_at": "2026-10-02T10:30:00Z",
                            "category_basis": "Parser and SGF context identify a program label"},
    }
    bundle = approved_bundle(inv)
    bundle["members"][0].update(owner=owner, raw_value="GNUGo4.0")
    bundle["candidates"][0].update(owner=owner, raw_value="GNUGo4.0")
    bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
    bundle = _v2_wrap(engine, inv, bundle, [declaration], [])
    before = counts(engine)
    assert dry_run_bundle(engine, bundle, registry(), inv, [])["ready"]
    assert counts(engine) == before
    applied = apply_bundle(engine, bundle, registry(), inv, [])
    owner_id = applied["resolved_refs"]["raw_event:@program-four"]
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.raw_value).where(KifuRawEventValue.id == owner_id)) == "GNUGo4.0"
        assert conn.scalar(select(KifuRawEventName.display_name).where(KifuRawEventName.raw_event_id == owner_id)) == ""
        assert conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == 12)) == "(;PB[Alpha]PW[Beta]EV[GNUGo4.0])"
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.id).where(KifuRawEventValue.id == owner_id)) is None


def test_v2_new_raw_category_must_match_parser_and_approved_decision(engine):
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Alpha", player_white="Beta", event="GNUGo4.0",
            sgf_content="(;PB[Alpha]PW[Beta]EV[GNUGo4.0])", source_path="two.sgf"))
    inv = build_inventory(engine)
    owner = {"kind": "raw_event", "ref": "program-four"}
    declaration = {
        "owner": owner, "create": {"raw_value": "GNUGo4.0", "category": "formal_event_candidate"},
        "occurrence_album_ids": [12], "occurrence_sha256": canonical_sha256([12]),
        "category_review": {"status": "approved", "producer_id": "researcher-1",
                            "producer_model": "gpt-6-luna", "produced_at": "2026-10-02T10:00:00Z",
                            "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
                            "reviewed_at": "2026-10-02T10:30:00Z",
                            "category_basis": "Mistakenly calls engine label a tournament"},
    }
    base = approved_bundle(inv)
    base["members"][0].update(owner=owner, raw_value="GNUGo4.0")
    base["candidates"][0].update(owner=owner, raw_value="GNUGo4.0")
    base["member_set_sha256"] = canonical_sha256(base["members"])
    bundle = _v2_wrap(engine, inv, base, [declaration], [])
    with pytest.raises(BatchError, match="category"):
        dry_run_bundle(engine, bundle, registry(), inv, [])
    assert counts(engine) == (0, 0, 0, 0, 0)


def _eleven_language_identity_fixture(engine, inv, owners):
    source_registry = registry()
    source_registry["sources"] = [
        {"id": f"go-{lang}", "tier": "official", "home_url": "https://example.org/",
         "language": source_registry["language_tags"][lang]} for lang in LANGS
    ]
    source_registry["language_scopes"] = {
        lang: {"required_source_ids": [f"go-{lang}"], "complete_for_negative_claims": False}
        for lang in LANGS
    }
    members, candidates, research = [], [], []
    for owner in owners:
        for lang in LANGS:
            display = f"Example {owner['kind']} {lang.upper()}"
            member = {"owner": owner, "lang": lang}
            check = {"owner": owner, "source_id": f"go-{lang}", "query": "Example Person",
                     "status": "found", "url": f"https://example.org/{lang}",
                     "fetched_at": "2026-10-02T10:00:00Z", "http_status": 200,
                     "body_sha256": hashlib.sha256(display.encode()).hexdigest(),
                     "body_excerpt": f"Official identity profile: {display}",
                     "observed_lang": source_registry["language_tags"][lang],
                     "language_basis": "reviewed_text", "candidate_name": display,
                     "identity_basis": "Source identifies this synthetic fixture identity"}
            evidence = {"owner": owner, "lang": lang, "registry_version": "test-1",
                        "registry_sha256": registry_sha256(source_registry), "scope_status": "found",
                        "candidate_name": display, "source_checks": [check],
                        "original_name": "Example Person", "original_language": "en",
                        "original_language_basis_url": "https://example.org/original",
                        "reading": "Example Person", "reading_basis_url": "https://example.org/original",
                        "producer_id": "researcher-1", "producer_model": "gpt-6-luna", "review_status": "pending"}
            decision = bind_fixture_candidate({**member, "display_name": display, "decision_kind": "conventional",
                        "name_preimage_sha256": name_preimage_sha256(engine, owner, lang) if "id" in owner else None,
                        "research_sha256": canonical_sha256(evidence), "generation_rule_version": "none",
                        "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
                        "produced_at": "2026-10-02T10:01:00Z", "review_status": "approved",
                        "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
                        "reviewed_at": "2026-10-02T11:00:00Z",
                        "review_conclusion": "Checked synthetic language-specific profile"})
            members.append(member)
            candidates.append(decision)
            research.append(evidence)
    base = {"bundle_format": 2, "inventory_format": 2, "inventory_sha256": inv["sha256"],
            "registry_version": "test-1", "registry_sha256": registry_sha256(source_registry),
            "rule_version": "candidate-v2", "members": members,
            "member_set_sha256": canonical_sha256(members), "candidates": candidates}
    return base, research, source_registry


def test_v2_existing_player_link_rejects_one_language_without_writes(engine):
    inv = build_inventory(engine)
    owner = {"kind": "player", "id": 17}
    base, research = player_bundle(inv)
    bundle = _v2_wrap(engine, inv, base,
                      [{"owner": owner, "preimage": {"canonical_name": "吴清源"}}],
                      [_identity_link(engine, inv, 11, "white", owner)])
    result = validate_bundle(bundle, registry(), inv, research)
    assert not result["ready"]
    assert any("all eleven approved language names" in error for error in result["errors"])
    with pytest.raises(BatchError, match="all eleven approved language names"):
        dry_run_bundle(engine, bundle, registry(), inv, research)
    with pytest.raises(BatchError):
        apply_bundle(engine, bundle, registry(), inv, research)
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_v2_owner_preimage_accepts_pinned_iso_timestamp(engine):
    inv = build_inventory(engine)
    owner = {"kind": "player", "id": 17}
    with engine.connect() as conn:
        created_at = conn.scalar(select(KifuPlayer.created_at).where(KifuPlayer.id == 17))
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    bundle = _v2_wrap(
        engine, inv, base,
        [{"owner": owner, "preimage": {"canonical_name": "吴清源", "created_at": created_at.isoformat()}}],
        [_identity_link(engine, inv, 11, "white", owner)],
    )
    assert dry_run_bundle(engine, bundle, source_registry, inv, research)["ready"]


def test_v2_repeated_links_hash_common_raw_scope_once(engine, monkeypatch):
    from katrain.web.kifu import name_candidates

    with engine.begin() as conn:
        for album_id in (12, 13):
            conn.execute(KifuAlbum.__table__.insert().values(
                id=album_id, player_black="吴清源九段", player_white="Opponent", event="Cup",
                sgf_content="(;PB[吴清源九段]PW[Opponent]EV[Cup])",
                source_path=f"{album_id}.sgf"))
    inv = build_inventory(engine)
    owner = {"kind": "player", "id": 17}
    declaration = {"owner": owner, "preimage": {"canonical_name": "吴清源"}}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    links = [_identity_link(engine, inv, album_id, "black", owner) for album_id in (12, 13)]
    bundle = _v2_wrap(engine, inv, base, [declaration], links)
    actual_hash = name_candidates.canonical_sha256
    scope_hash_calls = 0

    def counting_hash(value):
        nonlocal scope_hash_calls
        if isinstance(value, list) and value and all(
            isinstance(item, list) and len(item) == 2 and item[1] in {"black", "white"}
            for item in value
        ):
            scope_hash_calls += 1
        return actual_hash(value)

    monkeypatch.setattr(name_candidates, "canonical_sha256", counting_hash)
    assert dry_run_bundle(engine, bundle, source_registry, inv, research)["ready"]
    assert scope_hash_calls == 1


def test_v2_two_slot_links_one_album_have_one_change_and_reverse_undo(engine):
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=19, canonical_name="Test Tournament"))
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            player_white="吴清源九段", event="Test Tournament"))
    inv = build_inventory(engine)
    player = {"kind": "player", "id": 17}
    event_owner = {"kind": "event", "id": 19}
    owners = [{"owner": player, "preimage": {"canonical_name": "吴清源"}},
              {"owner": event_owner, "preimage": {"canonical_name": "Test Tournament"}}]
    links = [_identity_link(engine, inv, 11, "white", player), _identity_link(engine, inv, 11, "event", event_owner)]
    player_decisions, research, source_registry = _eleven_language_identity_fixture(
        engine, inv, [player, event_owner])
    bundle = _v2_wrap(engine, inv, player_decisions, owners, links)
    assert dry_run_bundle(engine, bundle, source_registry, inv, research)["ready"]
    applied = apply_bundle(engine, bundle, source_registry, inv, research)
    with engine.connect() as conn:
        assert conn.execute(select(KifuAlbum.white_player_id, KifuAlbum.event_id)
                            .where(KifuAlbum.id == 11)).one() == (17, 19)
        changes = conn.execute(select(KifuNameChange).where(
            KifuNameChange.batch_id == applied["batch_id"], KifuNameChange.target_table == "kifu_albums")) \
            .mappings().all()
        assert len(changes) == 1
        assert changes[0]["before_image"]["white_player_id"] is None
        assert changes[0]["after_image"]["event_id"] == 19
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert conn.execute(select(KifuAlbum.white_player_id, KifuAlbum.event_id)
                            .where(KifuAlbum.id == 11)).one() == (None, None)


def test_v2_stale_catalog_rejects_bundle_without_writes(engine):
    inv = build_inventory(engine)
    bundle = _v2_wrap(engine, inv, approved_bundle(inv),
                      [{"owner": {"kind": "raw_event", "id": 7},
                        "preimage": {"raw_value": "GNUGo3.8"},
                        "occurrence_album_ids": [11], "occurrence_sha256": canonical_sha256([11])}], [])
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(canonical_name="Concurrent new event"))
    with pytest.raises(BatchError, match="catalog supplement"):
        apply_bundle(engine, bundle, registry(), inv, [])
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_v2_new_player_link_requires_and_writes_all_eleven_reviewed_names(engine):
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(player_white="Example Person"))
    inv = build_inventory(engine)
    owner = {"kind": "player", "ref": "example-person"}
    declaration = {"owner": owner, "create": {"canonical_name": "Example Person"}}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    link = _identity_link(engine, inv, 11, "white", owner)
    bundle = _v2_wrap(engine, inv, base, [declaration], [link])
    assert dry_run_bundle(engine, bundle, source_registry, inv, research)["ready"]
    applied = apply_bundle(engine, bundle, source_registry, inv, research)
    player_id = applied["resolved_refs"]["player:@example-person"]
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.white_player_id).where(KifuAlbum.id == 11)) == player_id
        names = conn.execute(select(KifuPlayerName).where(KifuPlayerName.player_id == player_id)).mappings().all()
        assert {name["lang"] for name in names} == set(LANGS)
        assert all(name["status"] == "verified" and name["evidence_id"] for name in names)
        assert conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == 11)).startswith("(;FF[4]")
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.white_player_id).where(KifuAlbum.id == 11)) is None
        assert conn.scalar(select(KifuPlayer.id).where(KifuPlayer.id == player_id)) is None


@pytest.mark.parametrize("change", ["expand", "remove", "target", "context", "evidence", "freeze"])
def test_v2_identity_scope_rejects_reusing_review_after_payload_changes(engine, change):
    with engine.begin() as conn:
        for album_id in (12, 13):
            conn.execute(KifuAlbum.__table__.insert().values(
                id=album_id, player_black="吴清源九段", player_white="Opponent", event="Cup",
                sgf_content="(;PB[吴清源九段]PW[Opponent]EV[Cup])", source_path=f"{album_id}.sgf"))
    inv = build_inventory(engine)
    owner = {"kind": "player", "id": 17}
    declaration = {"owner": owner, "preimage": {"canonical_name": "吴清源"}}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    links = [_identity_link(engine, inv, album_id, "black", owner) for album_id in (12, 13)]
    bundle = _v2_wrap(engine, inv, base, [declaration], links[:1] if change == "expand" else links)
    assert validate_bundle(bundle, source_registry, inv, research)["ready"]
    if change == "expand":
        extra = links[1]
        extra["identity_review"] = deepcopy(bundle["album_links"][0]["identity_review"])
        bundle["album_links"].append(extra)
    elif change == "remove":
        bundle["album_links"].pop()
    elif change == "target":
        other = {"kind": "player", "ref": "other"}
        bundle["owners"].append({"owner": other, "create": {"canonical_name": "Other"}})
        bundle["owner_set_sha256"] = canonical_sha256(bundle["owners"])
        for link in bundle["album_links"]:
            link["target"] = other
    elif change == "context":
        columns = inv["association_columns"]
        for row in inv["album_associations"]:
            if row[0] == 12:
                row[columns.index("round_name")] = "Changed round"
                album = dict(zip(columns, row))
        inv["sha256"] = canonical_sha256(inv["album_associations"])
        bundle["inventory_sha256"] = inv["sha256"]
        bundle["album_links"][0]["expected"]["round_name"] = "Changed round"
        bundle["album_links"][0]["association_sha256"] = canonical_sha256(album)
    elif change == "evidence":
        for link in bundle["album_links"]:
            link["identity_review"]["source_checks"][0]["body_sha256"] = "b" * 64
    else:
        for link in bundle["album_links"]:
            link["identity_review"]["scope_frozen_at"] = link["identity_review"]["reviewed_at"]
    bundle["link_set_sha256"] = canonical_sha256(bundle["album_links"])
    result = validate_bundle(bundle, source_registry, inv, research)
    assert not result["ready"]
    assert any("scope hash mismatch" in error or "scope freeze" in error for error in result["errors"])


@pytest.mark.parametrize("change", ["missing", "malformed", "integer", "changed"])
def test_v2_link_requires_signed_production_sgf_preimage(engine, change):
    inv = build_inventory(engine)
    owner = {"kind": "player", "id": 17}
    declaration = {"owner": owner, "preimage": {"canonical_name": "吴清源"}}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    bundle = _v2_wrap(engine, inv, base, [declaration], [_identity_link(engine, inv, 11, "black", owner)])
    assert validate_bundle(bundle, source_registry, inv, research)["ready"]

    link = bundle["album_links"][0]
    if change == "missing":
        del link["production_sgf_sha256"]
    elif change == "malformed":
        link["production_sgf_sha256"] = "invalid"
    elif change == "integer":
        link["production_sgf_sha256"] = int("1" * 64)
    else:
        link["production_sgf_sha256"] = "b" * 64
    if change != "changed":
        link["identity_review"]["scope_sha256"] = identity_scope_sha256(bundle, [link], declaration)
    bundle["link_set_sha256"] = canonical_sha256(bundle["album_links"])

    result = validate_bundle(bundle, source_registry, inv, research)
    assert not result["ready"]
    assert not result["write_ready"]
    expected = "production SGF SHA-256" if change != "changed" else "scope hash mismatch"
    assert any(expected in error for error in result["errors"])


def test_v2_live_sgf_drift_rejects_dry_run_and_apply_before_writes(engine):
    inv = build_inventory(engine)
    owner = {"kind": "player", "id": 17}
    declaration = {"owner": owner, "preimage": {"canonical_name": "吴清源"}}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    bundle = _v2_wrap(engine, inv, base, [declaration], [_identity_link(engine, inv, 11, "black", owner)])
    assert dry_run_bundle(engine, bundle, source_registry, inv, research)["ready"]
    before = counts(engine)

    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            sgf_content="(;FF[4]PB[吴清源九段]PW[Unknown]EV[GNUGo3.8];B[aa])"))
    assert build_inventory(engine)["sha256"] == inv["sha256"]
    with pytest.raises(BatchError, match="SGF content"):
        dry_run_bundle(engine, bundle, source_registry, inv, research)
    with pytest.raises(BatchError, match="SGF content"):
        apply_bundle(engine, bundle, source_registry, inv, research)
    assert counts(engine) == before


def selected_event_bundle(engine, *, new=False):
    from tests.web_ui.test_kifu_name_candidates import _selected_v4_case
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            source='https://19x19.com', source_path='data/kifu-album/19x19/one.sgf', date_played='1934-10-01', board_size=19,
            sgf_content='(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Selected Cup]GC[Selected Cup | 1手])'))
        if not new:
            conn.execute(KifuEvent.__table__.insert().values(id=19, canonical_name='Selected Cup'))
    apply_reviewed_selection(engine, 11)
    inv = build_inventory(engine, inventory_format=4)
    owner = {'kind': 'event', 'ref': 'selected-cup'} if new else {'kind': 'event', 'id': 19}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    _, template = _selected_v4_case()
    declaration = deepcopy(template['owners'][0])
    declaration['owner'] = owner
    if new:
        declaration['create'] = declaration.pop('preimage')
    album = dict(zip(inv['association_columns'], inv['album_associations'][0]))
    selection = dict(zip(inv['event_selection']['columns'], inv['event_selection']['rows'][0]))
    link = deepcopy(template['album_links'][0])
    link.update(album_id=11, target=owner, association_sha256=canonical_sha256(album),
                production_sgf_sha256=selection['sgf_sha256'], raw_scope_sha256=canonical_sha256([[11, 'selected_event']]),
                selection_batch_id=selection['batch_id'], selection_bundle_sha256=selection['bundle_sha256'],
                selection_before_image=selection['source_after_image'],
                selection_before_sha256=selection['source_after_sha256'],
                expected={key: album[key] for key in ('player_black', 'player_white', 'event', 'date_played',
                                                     'round_name', 'black_rank', 'white_rank')} | {'old_id': None})
    base.update(bundle_format=4, inventory_format=4, inventory_sha256=inv['sha256'],
                catalog_sha256=catalog_snapshot_sha(engine), owners=[declaration],
                owner_set_sha256=canonical_sha256([declaration]), album_links=[link])
    link['identity_review']['scope_sha256'] = identity_scope_sha256(base, [link], declaration)
    base['link_set_sha256'] = canonical_sha256([link])
    return base, source_registry, inv, research


def test_general_player_name_batch_remains_writable_after_selected_event_link(engine):
    selected, sources, selected_inventory, selected_research = selected_event_bundle(engine)
    apply_bundle(engine, selected, sources, selected_inventory, selected_research,
                 expected_bundle_sha256=canonical_sha256(selected))
    inventory = build_inventory(engine)
    assert inventory['inventory_format'] == 4
    ordinary, research = player_bundle(inventory)
    ordinary['inventory_format'] = 4
    assert dry_run_bundle(engine, ordinary, registry(), inventory, research)['affected_albums'] == [11]
    applied = apply_bundle(engine, ordinary, registry(), inventory, research)
    assert applied['status'] == 'applied'
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayerName.display_name).where(
            KifuPlayerName.player_id == 17, KifuPlayerName.lang == 'ru')) == 'Го Сэйгэн'
        assert conn.scalar(select(KifuAlbumEventSelection.event_id).where(
            KifuAlbumEventSelection.album_id == 11)) == 19


def test_selected_only_event_name_can_be_revised_with_general_bundle(engine):
    selected, sources, selected_inventory, selected_research = selected_event_bundle(engine)
    apply_bundle(engine, selected, sources, selected_inventory, selected_research,
                 expected_bundle_sha256=canonical_sha256(selected))
    inventory = build_inventory(engine)
    ordinary, research = player_bundle(inventory, owner_id=19, display='Новый Кубок')
    owner = {'kind': 'event', 'id': 19}
    ordinary['inventory_format'] = 4
    ordinary['members'][0]['owner'] = owner
    ordinary['member_set_sha256'] = canonical_sha256(ordinary['members'])
    candidate = ordinary['candidates'][0]
    candidate['owner'] = owner
    with engine.connect() as conn:
        current = conn.execute(select(KifuEventName.__table__).where(
            KifuEventName.event_id == 19, KifuEventName.lang == 'ru')).mappings().one()
    set_fixture_preimage(candidate, canonical_sha256({
        key: value.isoformat() if hasattr(value, 'isoformat') else value
        for key, value in current.items()}))
    research[0]['owner'] = owner
    research[0]['source_checks'][0]['owner'] = owner
    candidate['research_sha256'] = canonical_sha256(research[0])
    assert dry_run_bundle(engine, ordinary, registry(), inventory, research)['affected_albums'] == [11]
    applied = apply_bundle(engine, ordinary, registry(), inventory, research)
    assert applied['affected_albums'] == [11]
    with engine.connect() as conn:
        assert conn.scalar(select(KifuEventName.display_name).where(
            KifuEventName.event_id == 19, KifuEventName.lang == 'ru')) == 'Новый Кубок'


def test_general_player_link_remains_writable_after_selected_event_link(engine):
    selected, sources, selected_inventory, selected_research = selected_event_bundle(engine)
    apply_bundle(engine, selected, sources, selected_inventory, selected_research,
                 expected_bundle_sha256=canonical_sha256(selected))
    inventory = build_inventory(engine)
    owner = {'kind': 'player', 'id': 17}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inventory, [owner])
    base['inventory_format'] = 4
    ordinary = _v2_wrap(engine, inventory, base,
                        [{'owner': owner, 'preimage': {'canonical_name': '吴清源'}}],
                        [_identity_link(engine, inventory, 11, 'white', owner)])
    assert dry_run_bundle(engine, ordinary, source_registry, inventory, research)['affected_albums'] == [11]
    applied = apply_bundle(engine, ordinary, source_registry, inventory, research)
    assert applied['status'] == 'applied'
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.white_player_id).where(KifuAlbum.id == 11)) == 17
        assert conn.scalar(select(KifuAlbumEventSelection.event_id).where(
            KifuAlbumEventSelection.album_id == 11)) == 19
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ('Selected Cup', 19)}


@pytest.mark.parametrize('new', [False, True])
def test_v4_selected_event_apply_has_exact_selection_ledger(engine, new):
    bundle, sources, inv, research = selected_event_bundle(engine, new=new)
    expected = canonical_sha256(bundle)
    before = counts(engine)
    assert dry_run_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)['ready']
    assert counts(engine) == before
    with engine.connect() as conn:
        album_before = dict(conn.execute(select(KifuAlbum.__table__)).mappings().one())
        source_before = dict(conn.execute(select(KifuEventSelectionBatch.__table__)).mappings().one())
    applied = apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    target = applied['resolved_refs']['event:@selected-cup' if new else 'event:19']
    with engine.connect() as conn:
        assert dict(conn.execute(select(KifuAlbum.__table__)).mappings().one()) == album_before
        assert dict(conn.execute(select(KifuEventSelectionBatch.__table__)).mappings().one()) == source_before
        changes = conn.execute(select(KifuNameChange.__table__).where(
            KifuNameChange.batch_id == applied['batch_id'],
            KifuNameChange.target_table == 'kifu_album_event_selections')).mappings().all()
        assert len(changes) == 1
        assert changes[0]['target_row_id'] == 11
        assert changes[0]['before_image'] == bundle['album_links'][0]['selection_before_image']
        assert changes[0]['after_image'] == changes[0]['before_image'] | {'event_id': target}
    assert build_inventory(engine, inventory_format=4)['event_selection']['rows'][0][7] == target
    assert apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)['status'] == 'already_applied'


@pytest.mark.parametrize('expected', [None, 'f' * 64])
def test_v4_requires_external_trusted_bundle_hash(engine, expected):
    bundle, sources, inv, research = selected_event_bundle(engine)
    for action in (dry_run_bundle, apply_bundle):
        with pytest.raises(BatchError, match='bundle SHA'):
            action(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    assert counts(engine) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize('drift', ['selection', 'sgf', 'catalog', 'name'])
def test_v4_live_drift_rejects_without_writes(engine, drift):
    bundle, sources, inv, research = selected_event_bundle(engine)
    with engine.begin() as conn:
        if drift == 'selection':
            conn.execute(KifuAlbumEventSelection.__table__.update().values(reviewer_id='later'))
        elif drift == 'sgf':
            conn.execute(KifuAlbum.__table__.update().values(sgf_content='(;GN[changed])'))
        elif drift == 'catalog':
            conn.execute(KifuEvent.__table__.update().values(canonical_name='Changed'))
        else:
            from katrain.web.core.models_db import KifuEventName
            conn.execute(KifuEventName.__table__.insert().values(event_id=19, lang='en', display_name='Later', status='review'))
    before = counts(engine)
    for action in (dry_run_bundle, apply_bundle):
        with pytest.raises(BatchError):
            action(engine, bundle, sources, inv, research, expected_bundle_sha256=canonical_sha256(bundle))
    assert counts(engine) == before


def test_v4_retry_rejects_changed_ledger_after_image(engine):
    bundle, sources, inv, research = selected_event_bundle(engine)
    expected = canonical_sha256(bundle)
    applied = apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    with engine.begin() as conn:
        conn.execute(KifuAlbumEventSelection.__table__.update().values(reviewer_id='later'))
    with pytest.raises(BatchError, match='after-image'):
        apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)


@pytest.mark.parametrize("command", ["dry-run", "apply"])
def test_v4_cli_requires_external_hash(engine, tmp_path, capsys, command):
    bundle, sources, inv, research = selected_event_bundle(engine)
    inputs = []
    for kind, value in (("bundle", bundle), ("registry", sources), ("inventory", inv)):
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        inputs.extend([f"--{kind}", str(path)])
    path = tmp_path / "evidence.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in research), encoding="utf-8")
    inputs.extend(["--evidence", str(path), "--database-url", str(engine.url)])
    assert main([command, *inputs]) == 1
    assert "bundle SHA" in json.loads(capsys.readouterr().out)["error"]
    assert main([command, *inputs, "--expected-bundle-sha256", "f" * 64]) == 1
    assert "mismatch" in json.loads(capsys.readouterr().out)["error"]
    assert counts(engine) == (0, 0, 0, 0, 0)
    assert main([command, *inputs, "--expected-bundle-sha256", canonical_sha256(bundle)]) == 0
    assert "error" not in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("drift", ["name", "target", "ledger", "sgf", "undone"])
def test_v4_retry_rechecks_target_and_full_ledger(engine, drift):
    from katrain.web.core.models_db import KifuEventName
    bundle, sources, inv, research = selected_event_bundle(engine)
    expected = canonical_sha256(bundle)
    applied = apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    with engine.begin() as conn:
        if drift == "name":
            conn.execute(KifuEventName.__table__.update().values(display_name="Later"))
        elif drift == "target":
            conn.execute(KifuEvent.__table__.update().values(canonical_name="Later"))
        elif drift == "ledger":
            change = conn.scalar(select(KifuNameChange.id).where(
                KifuNameChange.target_table == "kifu_name_research_evidence").limit(1))
            conn.execute(KifuNameChange.__table__.delete().where(KifuNameChange.id == change))
        elif drift == "sgf":
            conn.execute(KifuAlbum.__table__.update().values(sgf_content="(;GN[changed])"))
        else:
            conn.execute(KifuNameBatch.__table__.update().values(status="undone"))
    before = counts(engine)
    with pytest.raises(BatchError):
        apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    assert counts(engine) == before


def test_v4_rejects_forged_base_inventory_hash(engine):
    bundle, sources, inv, research = selected_event_bundle(engine)
    inv['base_sha256'] = 'f' * 64
    for action in (dry_run_bundle, apply_bundle):
        with pytest.raises(BatchError, match='base'):
            action(engine, bundle, sources, inv, research, expected_bundle_sha256=canonical_sha256(bundle))
    assert counts(engine) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("drift", ["display", "raw_owner", "target_resolution", "evidence_before"])
def test_v4_retry_rejects_raw_event_name_and_ledger_rewritten_together(engine, drift):
    from katrain.web.kifu.name_batch import _image

    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=9, raw_value="Selected Cup", category="unclassified_pending", review_status="pending"))
    bundle, sources, inv, research = selected_event_bundle(engine)
    raw_owner = {"kind": "raw_event", "id": 9}
    raw_display = "Selected Cup raw EN"
    raw_research = deepcopy(research[0])
    raw_research["owner"] = raw_owner
    raw_research["candidate_name"] = raw_display
    raw_research["source_checks"][0].update(owner=raw_owner, candidate_name=raw_display,
                                               body_excerpt=f"Official identity profile: {raw_display}")
    raw_candidate = deepcopy(bundle["candidates"][0])
    raw_candidate.pop("preimage_binding")
    raw_candidate.update(owner=raw_owner, raw_value="Selected Cup", display_name=raw_display,
                         research_sha256=canonical_sha256(raw_research))
    bind_fixture_candidate(raw_candidate)
    bundle["members"].append({"owner": raw_owner, "lang": "en", "raw_value": "Selected Cup"})
    bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
    bundle["candidates"].append(raw_candidate)
    research.append(raw_research)
    bundle["owners"].append({"owner": raw_owner,
                             "preimage": {"raw_value": "Selected Cup"},
                             "occurrence_album_ids": [11], "occurrence_sha256": canonical_sha256([11])})
    bundle["owner_set_sha256"] = canonical_sha256(bundle["owners"])
    link = bundle["album_links"][0]
    link["identity_review"]["scope_sha256"] = identity_scope_sha256(bundle, [link], bundle["owners"][0])
    expected = canonical_sha256(bundle)
    applied = apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    with engine.begin() as conn:
        if drift == "raw_owner":
            conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 9)
                         .values(raw_value="Different raw event"))
        elif drift == "evidence_before":
            row = conn.execute(select(KifuNameResearchEvidence.__table__).where(
                KifuNameResearchEvidence.raw_event_id == 9)).mappings().one()
            forged = _image(conn, KifuNameResearchEvidence.__table__, row["id"]) | {"raw_event_id": 8}
            conn.execute(KifuNameChange.__table__.update().where(
                KifuNameChange.batch_id == applied["batch_id"],
                KifuNameChange.target_table == KifuNameResearchEvidence.__tablename__,
                KifuNameChange.target_row_id == row["id"]
            ).values(before_image=forged))
        else:
            if drift == "target_resolution":
                row = conn.execute(select(KifuNameBatch.__table__).where(
                    KifuNameBatch.id == applied["batch_id"])).mappings().one()
                artifact = deepcopy(row["reviewed_artifact"])
                artifact["resolved_refs"]["raw_event:9"] = 8
                conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == applied["batch_id"])
                             .values(reviewed_artifact=artifact))
            for model in ((KifuRawEventName, KifuNameResearchEvidence)
                          if drift == "target_resolution" else (KifuRawEventName,)):
                table = model.__table__
                row = conn.execute(select(table).where(table.c.raw_event_id == 9)).mappings().one()
                values = ({"raw_event_id": 8} if drift == "target_resolution"
                          else {"display_name": "UNREVIEWED replacement"})
                conn.execute(table.update().where(table.c.id == row["id"]).values(**values))
                after = _image(conn, table, row["id"])
                conn.execute(KifuNameChange.__table__.update().where(
                    KifuNameChange.batch_id == applied["batch_id"],
                    KifuNameChange.target_table == table.name,
                    KifuNameChange.target_row_id == row["id"]
                ).values(after_image=after))
    with pytest.raises(BatchError):
        apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)


def test_v4_rejects_unreferenced_research_before_writes(engine):
    bundle, sources, inv, research = selected_event_bundle(engine)
    extra = deepcopy(research[0])
    extra["owner"] = {"kind": "raw_event", "id": 7}
    extra["source_checks"][0]["owner"] = extra["owner"]
    evidence = [*research, extra]
    before = counts(engine)
    with pytest.raises(BatchError, match="unreferenced research"):
        apply_bundle(engine, bundle, sources, inv, evidence,
                     expected_bundle_sha256=canonical_sha256(bundle))
    assert counts(engine) == before


def test_v4_rejects_raw_scope_hidden_invalid_selection_before_writes(engine):
    bundle, sources, _inv, research = selected_event_bundle(engine)
    with engine.begin() as conn:
        other = dict(conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 11)).mappings().one())
        other.update(id=12, source_path="data/kifu-album/19x19/two.sgf")
        conn.execute(KifuAlbum.__table__.insert().values(**other))
    apply_reviewed_selection(engine, 12)
    with engine.begin() as conn:
        conn.execute(KifuAlbumEventSelection.__table__.update().where(
            KifuAlbumEventSelection.album_id == 12).values(event_id=19))
    inv = build_inventory(engine, inventory_format=4)
    assert len(inv["event_selection"]["rows"]) == 1
    bundle["inventory_sha256"] = inv["sha256"]
    link = bundle["album_links"][0]
    link["identity_review"]["scope_sha256"] = identity_scope_sha256(bundle, [link], bundle["owners"][0])
    bundle["link_set_sha256"] = canonical_sha256([link])
    expected = canonical_sha256(bundle)
    before = counts(engine)
    with pytest.raises(BatchError, match="raw scope"):
        dry_run_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    with pytest.raises(BatchError, match="raw scope"):
        apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    assert counts(engine) == before


@pytest.mark.parametrize("new", [False, True])
def test_v4_undo_reverts_selection_before_names_and_keeps_source_batch(engine, new):
    bundle, sources, inv, research = selected_event_bundle(engine, new=new)
    applied = apply_bundle(engine, bundle, sources, inv, research,
                           expected_bundle_sha256=canonical_sha256(bundle))
    with engine.connect() as conn:
        source_id = conn.scalar(select(KifuAlbumEventSelection.batch_id))
    result = undo_batch(engine, applied["batch_id"])
    assert result["status"] == "undone" and result["skipped"] == 0
    with engine.connect() as conn:
        selection = conn.execute(select(KifuAlbumEventSelection.__table__)).mappings().one()
        assert selection["event_id"] is None and selection["batch_id"] == source_id
        assert conn.scalar(select(KifuEventSelectionBatch.status).where(
            KifuEventSelectionBatch.id == source_id)) == "applied"
        if new:
            assert conn.scalar(select(func.count()).select_from(KifuEvent).where(
                KifuEvent.canonical_name == "Selected Cup")) == 0


@pytest.mark.parametrize("drift", ["selection", "name", "sgf", "dependent_event"])
def test_v4_undo_rejects_any_drift_atomically(engine, drift):
    from katrain.web.core.models_db import KifuEventName

    bundle, sources, inv, research = selected_event_bundle(engine, new=drift == "dependent_event")
    applied = apply_bundle(engine, bundle, sources, inv, research,
                           expected_bundle_sha256=canonical_sha256(bundle))
    with engine.begin() as conn:
        if drift == "selection":
            conn.execute(KifuAlbumEventSelection.__table__.update().values(reviewer_id="later"))
        elif drift == "name":
            conn.execute(KifuEventName.__table__.update().where(KifuEventName.lang == "en")
                         .values(display_name="Later"))
        elif drift == "sgf":
            conn.execute(KifuAlbum.__table__.update().values(sgf_content="(;GN[changed])"))
        else:
            event_id = applied["resolved_refs"]["event:@selected-cup"]
            conn.execute(KifuAlbum.__table__.insert().values(
                id=12, player_black="Other", player_white="Other", event="Other",
                event_id=event_id, source_path="other.sgf",
                sgf_content="(;PB[Other]PW[Other]EV[Other])"))
        before_selection = dict(conn.execute(select(KifuAlbumEventSelection.__table__)).mappings().one())
        before_names = list(conn.execute(select(KifuEventName.__table__).order_by(KifuEventName.id)).mappings())
    with pytest.raises(BatchError):
        undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert batch_status(engine, applied["batch_id"])["status"] == "applied"
        assert dict(conn.execute(select(KifuAlbumEventSelection.__table__)).mappings().one()) == before_selection
        assert list(conn.execute(select(KifuEventName.__table__).order_by(KifuEventName.id)).mappings()) == before_names


def test_v4_undo_rejects_artifact_format_tamper_before_legacy_path(engine):
    from katrain.web.core.models_db import KifuEventName

    bundle, sources, inv, research = selected_event_bundle(engine)
    applied = apply_bundle(engine, bundle, sources, inv, research,
                           expected_bundle_sha256=canonical_sha256(bundle))
    with engine.begin() as conn:
        batch = conn.execute(select(KifuNameBatch.__table__).where(
            KifuNameBatch.id == applied["batch_id"])).mappings().one()
        artifact = deepcopy(batch["reviewed_artifact"])
        artifact["bundle"]["bundle_format"] = 3
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == applied["batch_id"])
                     .values(reviewed_artifact=artifact))
        conn.execute(KifuEventName.__table__.update().where(KifuEventName.lang == "en")
                     .values(display_name="Later"))
        before_selection = dict(conn.execute(select(KifuAlbumEventSelection.__table__)).mappings().one())
    with pytest.raises(BatchError, match="artifact"):
        undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameBatch.status).where(KifuNameBatch.id == applied["batch_id"])) == "applied"
        assert dict(conn.execute(select(KifuAlbumEventSelection.__table__)).mappings().one()) == before_selection
