"""Reviewed name bundles apply atomically and undo only their own unchanged writes."""

from copy import deepcopy
import hashlib
import json

import pytest
from sqlalchemy import create_engine, event, func, select

from katrain.web.core.models_db import (
    Base, KifuAlbum, KifuNameBatch, KifuNameChange, KifuNameResearchEvidence,
    KifuNameSourceRegistry, KifuPlayer, KifuPlayerName, KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.name_batch import BatchError, apply_bundle, batch_status, dry_run_bundle, undo_batch
from katrain.web.kifu.name_candidates import canonical_sha256, classification_template_sha256
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_inventory import build_inventory
from scripts.kifu_name_batch import main


LANGS = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")


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
    candidate = {
        **member, "display_name": "", "decision_kind": "hidden", "research_sha256": "",
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
    }
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
    candidate = {
        **member, "display_name": display, "decision_kind": "conventional",
        "research_sha256": canonical_sha256(research), "generation_rule_version": "none",
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-02T10:01:00Z", "review_status": "approved",
        "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
        "reviewed_at": "2026-10-02T11:00:00Z", "review_conclusion": "Confirmed exact Russian professional profile",
    }
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
    assert json.loads(capsys.readouterr().out)["ready"]
    assert main(["dry-run", *inputs, "--database-url", str(engine.url)]) == 0
    assert json.loads(capsys.readouterr().out)["affected_albums"] == [11]
    assert counts(engine) == (0, 0, 0, 0, 0)
