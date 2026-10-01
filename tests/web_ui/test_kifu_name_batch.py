"""Reviewed name bundles apply atomically and undo only their own unchanged writes."""

from copy import deepcopy
import hashlib
import json

import pytest
from sqlalchemy import create_engine, event, func, select

from katrain.web.core.models_db import (
    Base, KifuAlbum, KifuEvent, KifuNameBatch, KifuNameChange, KifuNameResearchEvidence,
    KifuNameSourceRegistry, KifuPlayer, KifuPlayerName, KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.name_batch import (
    BatchError, apply_bundle, batch_status, catalog_snapshot_sha, dry_run_bundle, undo_batch,
)
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


def _v2_wrap(engine, inventory, bundle, owners, links):
    result = deepcopy(bundle)
    result.update(bundle_format=2, catalog_sha256=catalog_snapshot_sha(engine), owners=owners,
                  owner_set_sha256=canonical_sha256(owners), album_links=links,
                  link_set_sha256=canonical_sha256(links))
    return result


def _identity_link(inventory, album_id, slot, target):
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
    return {"album_id": album_id, "slot": slot, "association_sha256": canonical_sha256(album),
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
    base, research = player_bundle(inv)
    links = [_identity_link(inv, album_id, "black", owner) for album_id in (12, 13)]
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
    assert dry_run_bundle(engine, bundle, registry(), inv, research)["ready"]
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
    links = [_identity_link(inv, 11, "white", player), _identity_link(inv, 11, "event", event_owner)]
    player_decisions, research = player_bundle(inv)
    event_display = "Тестовый турнир"
    event_check = {
        "owner": event_owner, "source_id": "go", "query": "Test Tournament", "status": "found",
        "url": "https://example.org/event", "fetched_at": "2026-10-02T10:00:00Z", "http_status": 200,
        "body_sha256": hashlib.sha256(event_display.encode()).hexdigest(),
        "body_excerpt": f"Official event record {event_display}", "observed_lang": "ru",
        "language_basis": "reviewed_text", "candidate_name": event_display,
        "identity_basis": "The named event matches this fixture's tournament"}
    event_research = {
        "owner": event_owner, "lang": "ru", "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()), "scope_status": "found",
        "candidate_name": event_display, "source_checks": [event_check],
        "original_name": "Test Tournament", "original_language": "en",
        "original_language_basis_url": "https://example.org/event",
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna", "review_status": "pending"}
    event_member = {"owner": event_owner, "lang": "ru"}
    event_candidate = {
        **event_member, "display_name": event_display, "decision_kind": "conventional",
        "research_sha256": canonical_sha256(event_research), "generation_rule_version": "none",
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-02T10:01:00Z", "review_status": "approved",
        "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
        "reviewed_at": "2026-10-02T11:00:00Z", "review_conclusion": "Checked exact event"}
    player_decisions["members"].append(event_member)
    player_decisions["member_set_sha256"] = canonical_sha256(player_decisions["members"])
    player_decisions["candidates"].append(event_candidate)
    research.append(event_research)
    bundle = _v2_wrap(engine, inv, player_decisions, owners, links)
    assert dry_run_bundle(engine, bundle, registry(), inv, research)["ready"]
    applied = apply_bundle(engine, bundle, registry(), inv, research)
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
    source_registry = registry()
    source_registry["sources"] = [
        {"id": f"go-{lang}", "tier": "official", "home_url": "https://example.org/",
         "language": source_registry["language_tags"][lang]} for lang in LANGS
    ]
    source_registry["language_scopes"] = {
        lang: {"required_source_ids": [f"go-{lang}"], "complete_for_negative_claims": False}
        for lang in LANGS
    }
    owner = {"kind": "player", "ref": "example-person"}
    declaration = {"owner": owner, "create": {"canonical_name": "Example Person"}}
    members, candidates, research = [], [], []
    for lang in LANGS:
        display = f"Example Person {lang.upper()}"
        member = {"owner": owner, "lang": lang}
        check = {"owner": owner, "source_id": f"go-{lang}", "query": "Example Person",
                 "status": "found", "url": f"https://example.org/{lang}",
                 "fetched_at": "2026-10-02T10:00:00Z", "http_status": 200,
                 "body_sha256": hashlib.sha256(display.encode()).hexdigest(),
                 "body_excerpt": f"Official player profile: {display}",
                 "observed_lang": source_registry["language_tags"][lang],
                 "language_basis": "reviewed_text", "candidate_name": display,
                 "identity_basis": "Source identifies this synthetic fixture person"}
        evidence = {"owner": owner, "lang": lang, "registry_version": "test-1",
                    "registry_sha256": registry_sha256(source_registry), "scope_status": "found",
                    "candidate_name": display, "source_checks": [check],
                    "original_name": "Example Person", "original_language": "en",
                    "original_language_basis_url": "https://example.org/original",
                    "reading": "Example Person", "reading_basis_url": "https://example.org/original",
                    "producer_id": "researcher-1", "producer_model": "gpt-6-luna", "review_status": "pending"}
        decision = {**member, "display_name": display, "decision_kind": "conventional",
                    "research_sha256": canonical_sha256(evidence), "generation_rule_version": "none",
                    "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
                    "produced_at": "2026-10-02T10:01:00Z", "review_status": "approved",
                    "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
                    "reviewed_at": "2026-10-02T11:00:00Z",
                    "review_conclusion": "Checked synthetic language-specific profile"}
        members.append(member)
        candidates.append(decision)
        research.append(evidence)
    base = {"bundle_format": 2, "inventory_format": 2, "inventory_sha256": inv["sha256"],
            "registry_version": "test-1", "registry_sha256": registry_sha256(source_registry),
            "rule_version": "candidate-v2", "members": members,
            "member_set_sha256": canonical_sha256(members), "candidates": candidates}
    link = _identity_link(inv, 11, "white", owner)
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
