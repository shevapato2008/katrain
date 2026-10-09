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


def composition_bundle(engine, *, symbolic=False):
    from tests.web_ui.test_kifu_name_composition import fixture
    from katrain.web.kifu.name_composition import HONINBO_RAWS

    series = {"kind": "event", "ref": "honinbo"} if symbolic else {"kind": "event", "id": 7}
    bundle, sources, _, research = fixture(series)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.delete())
        conn.execute(KifuRawEventValue.__table__.delete())
        if not symbolic:
            conn.execute(KifuEvent.__table__.insert().values(id=7, canonical_name="本因坊戦"))
        for edition, raw in enumerate(HONINBO_RAWS, 1):
            conn.execute(KifuRawEventValue.__table__.insert().values(
                id=edition, raw_value=raw, category="unclassified_pending", review_status="approved"))
            conn.execute(KifuAlbum.__table__.insert().values(
                id=edition, event=raw, event_id=None if symbolic else 7, black_player_id=17,
                player_black="Black", player_white="White",
                sgf_content=f"(;PB[Black]PW[White]EV[{raw}])", source_path=f"honinbo-{edition}.sgf"))
    inventory = build_inventory(engine)
    links = [_identity_link(engine, inventory, n, "event", series) for n in range(1, 35)] if symbolic else []
    bundle["inventory_sha256"] = inventory["sha256"]
    bundle = _v2_wrap(engine, inventory, bundle, bundle["owners"], links)
    scope = bundle["composition"]["scope"]
    scope["content"].update(inventory_sha256=inventory["sha256"], catalog_sha256=bundle["catalog_sha256"])
    scope["approval"]["content_sha256"] = canonical_sha256(scope["content"])
    for row in bundle["candidates"]:
        row["name_preimage_sha256"] = None
        bind_fixture_candidate(row)
        row["preimage_binding"].update(captured_at=row["produced_at"], bound_at=row["reviewed_at"])
    # Input ordering must never dictate whether a dependency has been written yet.
    bundle["candidates"].reverse()
    return bundle, sources, inventory, research


@pytest.mark.parametrize("symbolic", [False, True])
def test_composed_import_preserves_signed_candidates_and_resolved_dependencies(engine, symbolic):
    bundle, sources, inv, research = composition_bundle(engine, symbolic=symbolic)
    reviewed = deepcopy(bundle)
    assert dry_run_bundle(engine, bundle, sources, inv, research)["approved"] == 385
    applied = apply_bundle(engine, bundle, sources, inv, research)
    assert bundle == reviewed
    before_retry = counts(engine)
    assert apply_bundle(engine, bundle, sources, inv, research)["change_count"] == 0
    assert counts(engine) == before_retry
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuRawEventName)) == 374
        assert conn.scalar(select(func.count()).select_from(KifuEventName)) == 11
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__).where(
            KifuNameResearchEvidence.decision_kind == "composed")).mappings().all()
        for stored in evidence:
            payload = stored["research_payload"]
            candidate = payload["candidate"]
            assert candidate in reviewed["candidates"] and payload["research"] is None
            composition = payload["composition"]
            rule = next(rule for rule in reviewed["composition"]["rules"]
                        if rule["content"]["lang"] == stored["lang"])
            assert composition["version"] == "honinbo-composition-v1"
            assert composition["rule"] == rule
            assert composition["scope"] == reviewed["composition"]["scope"]
            dependencies = composition["dependencies"]
            series_id = applied["resolved_refs"]["event:@honinbo" if symbolic else "event:7"]
            base = conn.execute(select(KifuEventName.__table__).where(
                KifuEventName.event_id == series_id, KifuEventName.lang == stored["lang"])).mappings().one()
            assert dependencies == {
                "series_event_id": series_id, "base_name_id": base["id"],
                "base_evidence_id": base["evidence_id"], "base_revision": base["revision"],
                "base_candidate_sha256": candidate["base_candidate_sha256"],
                "composition_rule_sha256": canonical_sha256(rule),
                "raw_scope_sha256": candidate["raw_scope_sha256"],
                "scope_sha256": canonical_sha256(reviewed["composition"]["scope"]),
            }
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuRawEventName)) == 0
        assert conn.scalar(select(func.count()).select_from(KifuEventName)) == 0


@pytest.mark.parametrize("fault", ["missing", "no_capture", "new_row", "changed_row", "missing_language"])
def test_composed_import_rejects_unproven_or_stale_preimages_and_missing_language(engine, fault):
    bundle, sources, inv, research = composition_bundle(engine)
    row = bundle["candidates"][0]
    if fault == "missing":
        del row["name_preimage_sha256"]
    elif fault == "no_capture":
        del row["preimage_binding"]["capture_sha256"]
    elif fault in {"new_row", "changed_row"}:
        with engine.begin() as conn:
            conn.execute(KifuRawEventName.__table__.insert().values(
                raw_event_id=row["owner"]["id"], lang=row["lang"], display_name="Prior", status="review"))
        if fault == "changed_row":
            set_fixture_preimage(row, name_preimage_sha256(engine, row["owner"], row["lang"]))
            with engine.begin() as conn:
                conn.execute(KifuRawEventName.__table__.update().values(display_name="Later"))
    else:
        bundle["candidates"].pop(0)
    before = counts(engine)
    with pytest.raises(BatchError, match="preimage|capture|candidate set|decisions"):
        apply_bundle(engine, bundle, sources, inv, research)
    assert counts(engine) == before


def test_composed_import_rejects_cross_bundle_same_language_collision(engine):
    bundle, sources, inv, research = composition_bundle(engine)
    row = next(row for row in bundle["candidates"] if row["decision_kind"] == "composed" and row["lang"] == "ru")
    # A separately reviewed conventional name occupies this same-language spelling.
    other, records = player_bundle(inv, display=row["display_name"])
    apply_bundle(engine, other, registry(), inv, records)
    before = counts(engine)
    with pytest.raises(BatchError, match="cross-bundle"):
        apply_bundle(engine, bundle, sources, inv, research)
    assert counts(engine) == before


def test_composed_undo_retains_dependencies_of_later_manual_edit(engine):
    bundle, sources, inv, research = composition_bundle(engine)
    applied = apply_bundle(engine, bundle, sources, inv, research)
    with engine.begin() as conn:
        conn.execute(KifuRawEventName.__table__.update().where(
            KifuRawEventName.raw_event_id == 1, KifuRawEventName.lang == "ru").values(display_name="Manual edit"))
    undone = undo_batch(engine, applied["batch_id"])
    assert undone["status"] == "partial_undo"
    with engine.connect() as conn:
        retained = conn.execute(select(KifuRawEventName.__table__)).mappings().one()
        assert retained["display_name"] == "Manual edit"
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__).where(
            KifuNameResearchEvidence.id == retained["evidence_id"])).mappings().one()
        dependency = evidence["research_payload"]["composition"]["dependencies"]
        assert conn.scalar(select(KifuEventName.id).where(KifuEventName.id == dependency["base_name_id"])) is not None
        assert conn.scalar(select(KifuNameResearchEvidence.id).where(
            KifuNameResearchEvidence.id == dependency["base_evidence_id"])) is not None


def test_composed_mid_import_failure_rolls_back_dependencies_and_all_names(engine, monkeypatch):
    from katrain.web.kifu import name_batch
    bundle, sources, inv, research = composition_bundle(engine, symbolic=True)
    before = counts(engine)
    original = name_batch._apply_candidate

    def fail_on_composed(conn, row, *args, **kwargs):
        result = original(conn, row, *args, **kwargs)
        if row["decision_kind"] == "composed":
            raise RuntimeError("injected composed failure")
        return result

    monkeypatch.setattr(name_batch, "_apply_candidate", fail_on_composed)
    with pytest.raises(RuntimeError, match="injected composed"):
        apply_bundle(engine, bundle, sources, inv, research)
    assert counts(engine) == before
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuEventName)) == 0
        assert conn.scalar(select(func.count()).select_from(KifuEvent)) == 0
        assert set(conn.scalars(select(KifuAlbum.event_id))) == {None}


def test_composed_undo_restores_other_batch_bases_and_preserves_existing_links(engine):
    bundle, sources, inv, research = composition_bundle(engine)
    base_bundle = deepcopy(bundle)
    base_bundle.pop("composition")
    base_bundle["candidates"] = [row for row in base_bundle["candidates"] if row["owner"]["kind"] == "event"]
    base_bundle["members"] = [row for row in base_bundle["members"] if row["owner"]["kind"] == "event"]
    base_bundle["member_set_sha256"] = canonical_sha256(base_bundle["members"])
    base_bundle["owners"] = base_bundle["owners"][:1]
    base_bundle["owner_set_sha256"] = canonical_sha256(base_bundle["owners"])
    first = apply_bundle(engine, base_bundle, sources, inv, research)
    with engine.connect() as conn:
        before = conn.execute(select(KifuEventName.__table__).order_by(KifuEventName.id)).mappings().all()
    for row in bundle["candidates"]:
        if row["owner"]["kind"] == "event":
            set_fixture_preimage(row, name_preimage_sha256(engine, row["owner"], row["lang"]))
    second = apply_bundle(engine, bundle, sources, inv, research)
    assert undo_batch(engine, second["batch_id"])["status"] == "undone"
    assert batch_status(engine, first["batch_id"])["status"] == "applied"
    with engine.connect() as conn:
        assert conn.execute(select(KifuEventName.__table__).order_by(KifuEventName.id)).mappings().all() == before
        assert set(conn.scalars(select(KifuAlbum.event_id))) == {7}
        assert conn.scalar(select(func.count()).select_from(KifuNameResearchEvidence)) == 11


@pytest.mark.parametrize("manual_edit", [False, True])
def test_composed_undo_restores_complete_previous_composition_batch(engine, manual_edit):
    bundle, sources, inv, research = composition_bundle(engine)
    first = apply_bundle(engine, bundle, sources, inv, research)
    models = (KifuEventName, KifuRawEventName, KifuNameResearchEvidence)
    with engine.connect() as conn:
        before = {model: conn.execute(select(model.__table__).order_by(model.id)).mappings().all()
                  for model in models}
    revised = deepcopy(bundle)
    for candidate in revised["candidates"]:
        set_fixture_preimage(candidate, name_preimage_sha256(engine, candidate["owner"], candidate["lang"]))
    second = apply_bundle(engine, revised, sources, inv, research)
    if manual_edit:
        with engine.begin() as conn:
            conn.execute(KifuRawEventName.__table__.update().where(
                KifuRawEventName.raw_event_id == 1, KifuRawEventName.lang == "ru").values(display_name="Manual B"))
    undone = undo_batch(engine, second["batch_id"])
    assert batch_status(engine, first["batch_id"])["status"] == "applied"
    if manual_edit:
        assert undone["status"] == "partial_undo"
        with engine.connect() as conn:
            name = conn.execute(select(KifuRawEventName.__table__).where(
                KifuRawEventName.raw_event_id == 1, KifuRawEventName.lang == "ru")).mappings().one()
            assert name["display_name"] == "Manual B" and name["revision"] == 2
            evidence = conn.execute(select(KifuNameResearchEvidence.__table__).where(
                KifuNameResearchEvidence.id == name["evidence_id"])).mappings().one()
            dependency = evidence["research_payload"]["composition"]["dependencies"]
            base = conn.execute(select(KifuEventName.__table__).where(
                KifuEventName.id == dependency["base_name_id"])).mappings().one()
            assert base["revision"] == dependency["base_revision"] == 2
            assert base["evidence_id"] == dependency["base_evidence_id"]
            assert conn.scalar(select(KifuNameResearchEvidence.id).where(
                KifuNameResearchEvidence.id == dependency["base_evidence_id"])) is not None
        return
    assert undone["status"] == "undone" and undone["skipped"] == 0
    assert undone["reverted"] == second["change_count"]
    with engine.connect() as conn:
        for model in models:
            assert conn.execute(select(model.__table__).order_by(model.id)).mappings().all() == before[model]
        assert set(conn.scalars(select(KifuAlbum.event_id))) == {7}


def test_composed_undo_three_batches_restores_active_dependencies_and_keeps_history(engine):
    bundle, sources, inv, research = composition_bundle(engine)
    first = apply_bundle(engine, bundle, sources, inv, research)
    revised = deepcopy(bundle)
    for candidate in revised["candidates"]:
        set_fixture_preimage(candidate, name_preimage_sha256(engine, candidate["owner"], candidate["lang"]))
    second = apply_bundle(engine, revised, sources, inv, research)
    models = (KifuEventName, KifuRawEventName, KifuNameResearchEvidence)
    with engine.connect() as conn:
        before = {model: conn.execute(select(model.__table__).order_by(model.id)).mappings().all()
                  for model in models}
    latest = deepcopy(revised)
    for candidate in latest["candidates"]:
        set_fixture_preimage(candidate, name_preimage_sha256(engine, candidate["owner"], candidate["lang"]))
    third = apply_bundle(engine, latest, sources, inv, research)
    undone = undo_batch(engine, third["batch_id"])
    assert undone["status"] == "undone" and undone["skipped"] == 0
    assert undone["reverted"] == third["change_count"]
    assert batch_status(engine, first["batch_id"])["status"] == "applied"
    assert batch_status(engine, second["batch_id"])["status"] == "applied"
    with engine.connect() as conn:
        for model in models:
            assert conn.execute(select(model.__table__).order_by(model.id)).mappings().all() == before[model]


def test_composed_undo_preserves_historical_base_evidence_without_active_names(engine):
    bundle, sources, inv, research = composition_bundle(engine)
    applied = apply_bundle(engine, bundle, sources, inv, research)
    with engine.begin() as conn:
        # A later editor keeps the old evidence as audit history while withdrawing its name.
        evidence_id = conn.scalar(select(KifuRawEventName.evidence_id).where(
            KifuRawEventName.raw_event_id == 1, KifuRawEventName.lang == "ru"))
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__).where(
            KifuNameResearchEvidence.id == evidence_id)).mappings().one()
        dependencies = evidence["research_payload"]["composition"]["dependencies"]
        conn.execute(KifuRawEventName.__table__.update().where(
            KifuRawEventName.evidence_id == evidence_id).values(status="review"))
        conn.execute(KifuNameResearchEvidence.__table__.update().where(
            KifuNameResearchEvidence.id == evidence_id).values(producer_model="retained audit edit"))
    assert undo_batch(engine, applied["batch_id"])["status"] == "partial_undo"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuEventName.id).where(
            KifuEventName.id == dependencies["base_name_id"])) is None
        assert conn.scalar(select(KifuNameResearchEvidence.id).where(
            KifuNameResearchEvidence.id == dependencies["base_evidence_id"])) is not None


def selected_composition_bundle(engine):
    from tests.web_ui.test_kifu_name_candidates import _selected_v4_case

    bundle, sources, _, research = composition_bundle(engine, symbolic=True)
    raws = bundle["composition"]["scope"]["content"]["raws"]
    with engine.begin() as conn:
        for raw in raws:
            album_id = raw["edition"]
            value = raw["raw_value"]
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == album_id).values(
                event="GNUGo3.8", date_played="1934-10-01", board_size=19, source="https://19x19.com",
                source_path=f"data/kifu-album/19x19/{album_id}.sgf",
                sgf_content=f"(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[{value}]GC[{value} | 1手])"))
    for raw in raws:
        apply_reviewed_selection(engine, raw["edition"])
    inventory = build_inventory(engine, inventory_format=4)
    _, template = _selected_v4_case()
    declaration = bundle["owners"][0]
    declaration["identity_context"] = template["owners"][0]["identity_context"]
    links = []
    for values, selected in zip(inventory["album_associations"], inventory["event_selection"]["rows"]):
        album = dict(zip(inventory["association_columns"], values))
        selection = dict(zip(inventory["event_selection"]["columns"], selected))
        raw = raws[album["id"] - 1]
        raw["raw_scope_sha256"] = canonical_sha256([[album["id"], "selected_event"]])
        link = deepcopy(template["album_links"][0])
        link.update(
            album_id=album["id"], target=declaration["owner"], association_sha256=canonical_sha256(album),
            production_sgf_sha256=selection["sgf_sha256"], raw_scope_sha256=raw["raw_scope_sha256"],
            selection_batch_id=selection["batch_id"], selection_bundle_sha256=selection["bundle_sha256"],
            selection_before_image=selection["source_after_image"],
            selection_before_sha256=selection["source_after_sha256"],
            expected={key: album[key] for key in ("player_black", "player_white", "event", "date_played",
                                                 "round_name", "black_rank", "white_rank")} | {"old_id": None})
        links.append(link)
    bundle.update(bundle_format=4, inventory_format=4, inventory_sha256=inventory["sha256"],
                  album_links=links, catalog_sha256=catalog_snapshot_sha(engine),
                  owner_set_sha256=canonical_sha256(bundle["owners"]))
    for link in links:
        link["identity_review"]["scope_sha256"] = identity_scope_sha256(bundle, [link], declaration)
    bundle["link_set_sha256"] = canonical_sha256(links)
    scope = bundle["composition"]["scope"]
    scope["content"].update(inventory_sha256=inventory["sha256"], catalog_sha256=bundle["catalog_sha256"])
    scope["approval"]["content_sha256"] = canonical_sha256(scope["content"])
    for row in bundle["candidates"]:
        if row["decision_kind"] == "composed":
            row["raw_scope_sha256"] = raws[row["edition"] - 1]["raw_scope_sha256"]
            row["composition_review_sha256"] = canonical_sha256({
                key: value for key, value in row.items() if key not in {
                    "reviewer_id", "reviewer_model", "reviewed_at", "review_conclusion",
                    "composition_review_sha256", "name_preimage_sha256", "preimage_binding"}})
    return bundle, sources, inventory, research


def test_v4_composed_retry_checks_metadata_and_undo_is_atomic(engine):
    bundle, sources, inv, research = selected_composition_bundle(engine)
    expected = canonical_sha256(bundle)
    applied = apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected)
    assert apply_bundle(engine, bundle, sources, inv, research,
                        expected_bundle_sha256=expected)["change_count"] == 0
    with engine.begin() as conn:
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__).where(
            KifuNameResearchEvidence.decision_kind == "composed").limit(1)).mappings().one()
        payload = deepcopy(evidence["research_payload"])
        forged = deepcopy(payload)
        forged["composition"]["dependencies"]["base_revision"] += 1
        conn.execute(KifuNameResearchEvidence.__table__.update().where(
            KifuNameResearchEvidence.id == evidence["id"]).values(research_payload=forged))
    before = counts(engine)
    for action in (lambda: apply_bundle(engine, bundle, sources, inv, research, expected_bundle_sha256=expected),
                   lambda: undo_batch(engine, applied["batch_id"])):
        with pytest.raises(BatchError, match="evidence|after-image"):
            action()
        assert counts(engine) == before
    with engine.begin() as conn:
        conn.execute(KifuNameResearchEvidence.__table__.update().where(
            KifuNameResearchEvidence.id == evidence["id"]).values(research_payload=payload))
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert set(conn.scalars(select(KifuAlbumEventSelection.event_id))) == {None}
        assert conn.scalar(select(func.count()).select_from(KifuEventName)) == 0
        assert conn.scalar(select(func.count()).select_from(KifuRawEventName)) == 0
        assert conn.scalar(select(func.count()).select_from(KifuEventSelectionBatch)) == 34


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


def test_classification_v2_raw_bundle_apply_display_search_coverage_and_undo(engine, monkeypatch):
    from katrain.web.api.v1.endpoints import kifu
    monkeypatch.setattr(kifu, "name_display_language", lambda lang: lang)
    from tests.web_ui.test_kifu_name_candidates import v2_classification_candidate, V2_GENERIC_DISPLAYS
    from tests.web_ui.test_kifu_name_api import _list
    from katrain.web.core.models_db import KifuEventAlias
    from katrain.web.kifu.name_coverage import coverage_report

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    raw = "段位赛"
    sgf = f"(;PB[Alpha]PW[Beta]EV[{raw}])"
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Alpha", player_white="Beta", event=raw,
            sgf_content=sgf, source_path="generic.sgf"))
    inv = build_inventory(engine, inventory_format=4)
    owner = {"kind": "raw_event", "ref": "rank-event"}
    declaration = {
        "owner": owner, "create": {"raw_value": raw, "category": "generic_event_description"},
        "occurrence_album_ids": [12], "occurrence_sha256": canonical_sha256([12]),
        "category_review": {"status": "approved", "producer_id": "researcher-1",
                            "producer_model": "gpt-6-luna", "produced_at": "2026-10-02T10:00:00Z",
                            "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
                            "reviewed_at": "2026-10-02T10:30:00Z",
                            "category_basis": "Exact parser category: generic description without event identity"},
    }
    proposed = approved_bundle(inv)
    proposed["inventory_format"] = 4
    proposed["candidates"] = []
    for lang in LANGS:
        row = v2_classification_candidate(raw, lang, owner)
        row["name_preimage_sha256"] = None
        proposed["candidates"].append(bind_fixture_candidate(row))
    proposed["members"] = [{"owner": owner, "lang": lang, "raw_value": raw} for lang in LANGS]
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    proposed = _v2_wrap(engine, inv, proposed, [declaration], [])
    before = counts(engine)
    assert dry_run_bundle(engine, proposed, registry(), inv, [])["ready"]
    assert counts(engine) == before
    missing_preimage = deepcopy(proposed)
    del missing_preimage["candidates"][0]["name_preimage_sha256"]
    with pytest.raises(BatchError, match="preimage"):
        dry_run_bundle(engine, missing_preimage, registry(), inv, [])
    applied = apply_bundle(engine, proposed, registry(), inv, [])
    owner_id = applied["resolved_refs"]["raw_event:@rank-event"]
    report = coverage_report(engine, inv, languages=LANGS)
    with Session(engine) as db:
        names = db.query(KifuRawEventName).filter_by(raw_event_id=owner_id).all()
        assert {name.lang: name.display_name for name in names} == V2_GENERIC_DISPLAYS[raw]
        assert {name.generation_rule_version for name in names} == {"classification-v2"}
        assert db.query(KifuEvent).count() == db.query(KifuEventAlias).count() == 0
        assert db.query(KifuAlbum).filter_by(id=12).one().event_id is None
        assert db.query(KifuAlbum).filter_by(id=12).one().sgf_content == sgf
        for lang, display in V2_GENERIC_DISPLAYS[raw].items():
            assert {item.id: item.display_event for item in _list(db, lang=lang).items}[12] == display
            assert [item.id for item in _list(db, q=display, lang=lang).items] == [12]
            assert report["languages"][lang]["by_decision"] == {"generic": 1}
        # Revocation uses the same persisted approval for display, search and coverage.
        evidence = db.query(KifuNameResearchEvidence).filter_by(raw_event_id=owner_id, lang="en").one()
        evidence.review_status = "pending"
        db.commit()
        assert {item.id: item.display_event for item in _list(db, lang="en").items}[12] == "Event name unverified"
        assert _list(db, q="Dan-rank tournament", lang="en").items == []
        assert coverage_report(engine, inv, languages=("en",))["languages"]["en"]["by_decision"] == {}
        evidence.review_status = "approved"
        db.commit()
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert db.query(KifuRawEventValue).filter_by(id=owner_id).first() is None
        assert db.query(KifuRawEventName).filter_by(raw_event_id=owner_id).count() == 0
        assert db.query(KifuAlbum).filter_by(id=12).one().sgf_content == sgf
        assert db.query(KifuAlbum).filter_by(id=12).one().event_id is None


def _eleven_language_identity_fixture(engine, inv, owners, *, languages=LANGS):
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
        for lang in languages:
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
    assert any("all five approved language names" in error for error in result["errors"])
    with pytest.raises(BatchError, match="all five approved language names"):
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


def test_v2_new_player_link_accepts_five_reviewed_names(engine):
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(player_white="Example Person"))
    inv = build_inventory(engine)
    owner = {"kind": "player", "ref": "example-person"}
    declaration = {"owner": owner, "create": {"canonical_name": "Example Person"}}
    base, research, source_registry = _eleven_language_identity_fixture(
        engine, inv, [owner], languages=("en", "cn", "tw", "jp", "ko")
    )
    bundle = _v2_wrap(engine, inv, base, [declaration], [_identity_link(engine, inv, 11, "white", owner)])
    assert dry_run_bundle(engine, bundle, source_registry, inv, research)["ready"]
    applied = apply_bundle(engine, bundle, source_registry, inv, research)
    with engine.connect() as conn:
        player_id = applied["resolved_refs"]["player:@example-person"]
        names = conn.execute(select(KifuPlayerName).where(KifuPlayerName.player_id == player_id)).mappings().all()
        assert {name["lang"] for name in names} == {"en", "cn", "tw", "jp", "ko"}


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


def _archive_fixture_bundle(engine, tmp_path):
    from tests.web_ui.test_kifu_name_candidates import archive_registry, archive_declaration, archive_candidate
    from katrain.web.core.models_db import KifuSource, KifuAlbumSource

    raw = "Hoensha game"
    with engine.begin() as conn:
        conn.execute(KifuSource.__table__.insert().values(id=2, source_key="CWI"))
        for album_id in (12, 13):
            path = f"data/kifu-album/CWI_History_Full/Hoensha/{album_id}.sgf"
            conn.execute(KifuAlbum.__table__.insert().values(id=album_id, player_black="Alpha", player_white="Beta",
                event=raw, date_played="1880-01-01", sgf_content=f"(;PB[Alpha]PW[Beta]EV[{raw}])", source_path=path))
            conn.execute(KifuAlbumSource.__table__.insert().values(album_id=album_id, source_id=2,
                origin_path=path, match_method="source_path"))
    inv = build_inventory(engine, inventory_format=4)
    owner = {"kind": "raw_event", "ref": "hoensha-archive"}
    declaration = archive_declaration(inv, owner, tmp_path, ids=[12, 13])
    proposed = approved_bundle(inv)
    proposed.update(inventory_format=4, registry_sha256=registry_sha256(archive_registry()))
    proposed["candidates"] = []
    for lang in LANGS:
        row = archive_candidate(inv, declaration, lang)
        row["name_preimage_sha256"] = None
        proposed["candidates"].append(bind_fixture_candidate(row))
    proposed["members"] = [{"owner": owner, "lang": lang, "raw_value": raw} for lang in LANGS]
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    proposed = _v2_wrap(engine, inv, proposed, [declaration], [])
    return inv, proposed, declaration


def test_archive_description_finite_scope_display_search_coverage_evidence_and_undo(engine, tmp_path, monkeypatch):
    from katrain.web.api.v1.endpoints import kifu
    monkeypatch.setattr(kifu, "name_display_language", lambda lang: lang)
    from tests.web_ui.test_kifu_name_candidates import archive_registry, ARCHIVE_DISPLAYS
    from tests.web_ui.test_kifu_name_api import _list
    from katrain.web.core.models_db import KifuEventAlias
    from katrain.web.kifu.name_coverage import coverage_report
    from katrain.web.kifu.identity import strict_display_maps, strict_slot_approvals, resolve_strict_display

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    raw = "Hoensha game"
    inv, proposed, declaration = _archive_fixture_bundle(engine, tmp_path)
    before = counts(engine)
    assert dry_run_bundle(engine, proposed, archive_registry(), inv, [])["ready"]
    assert counts(engine) == before
    applied = apply_bundle(engine, proposed, archive_registry(), inv, [])
    owner_id = applied["resolved_refs"]["raw_event:@hoensha-archive"]
    report = coverage_report(engine, inv, languages=LANGS)
    with Session(engine) as db:
        assert {name.lang: name.display_name for name in db.query(KifuRawEventName).filter_by(raw_event_id=owner_id)} == ARCHIVE_DISPLAYS
        assert db.query(KifuEvent).count() == db.query(KifuEventAlias).count() == 0
        assert db.query(KifuAlbum).filter(KifuAlbum.id.in_([12, 13]), KifuAlbum.event_id.isnot(None)).count() == 0
        evidence = db.query(KifuNameResearchEvidence).filter_by(raw_event_id=owner_id, lang="en").one()
        proof = evidence.research_payload["archive_description"]
        assert proof == {"inventory_sha256": inv["sha256"], "declaration": declaration}
        for lang, display in ARCHIVE_DISPLAYS.items():
            assert {item.id: item.display_event for item in _list(db, lang=lang).items}[12] == display
            assert [item.id for item in _list(db, q=display, lang=lang).items] == [13, 12]
            assert report["languages"][lang]["by_decision"] == {"archive_description": 2}
        # Runtime is portable: retained capture paths are never opened for display.
        for check in declaration["category_review"]["archive_basis"]["source_checks"]:
            from pathlib import Path
            Path(check["body_path"]).unlink()
        assert [item.id for item in _list(db, q=ARCHIVE_DISPLAYS["en"], lang="en").items] == [13, 12]
        # New same-spelling rows, changed raw, linked events and selected events are outside approval.
        db.add(KifuAlbum(id=14, player_black="Alpha", player_white="Beta", event=raw,
                         sgf_content=f"(;EV[{raw}])", source_path="later.sgf"))
        db.commit()
        assert {item.id: item.display_event for item in _list(db, lang="en").items}[14] == "Event name unverified"
        assert [item.id for item in _list(db, q=ARCHIVE_DISPLAYS["en"], lang="en").items] == [13, 12]
        later_inv = build_inventory(engine, inventory_format=4)
        assert coverage_report(engine, later_inv, languages=("en",))["languages"]["en"]["by_decision"] == {"archive_description": 2}
        album = db.query(KifuAlbum).filter_by(id=13).one()
        album.event = "Hoensha Game"
        db.commit()
        assert [item.id for item in _list(db, q=ARCHIVE_DISPLAYS["en"], lang="en").items] == [12]
        changed_inv = build_inventory(engine, inventory_format=4)
        assert coverage_report(engine, changed_inv, languages=("en",))["languages"]["en"]["by_decision"] == {"archive_description": 1}
        album.event = raw
        db.add(KifuEvent(id=91, canonical_name="Other"))
        db.commit()
        album.event_id = 91
        db.commit()
        assert {item.id: item.display_event for item in _list(db, lang="en").items}[13] == "Event name unverified"
        assert [item.id for item in _list(db, q=ARCHIVE_DISPLAYS["en"], lang="en").items] == [12]
        linked_inv = build_inventory(engine, inventory_format=4)
        assert coverage_report(engine, linked_inv, languages=("en",))["languages"]["en"]["by_decision"] == {"archive_description": 1}
        album.event_id = None
        db.commit()
        selected = {13: ("Other selected event", None)}
        maps = strict_display_maps(db, [album], "en", selected_events=selected)
        assert resolve_strict_display(album, "en", maps[0], maps[1], maps[2], maps[4], maps[5], selected_events=selected)[2] == "Event name unverified"
        assert strict_slot_approvals(db, [album], "en", selected_events=selected)[13][2] is None
        # Revoked or damaged archive evidence loses display, search and coverage together.
        original = deepcopy(evidence.research_payload)
        for damaged in (None, "review", "body_hash", "scope_member"):
            if damaged is None:
                evidence.review_status = "pending"
            else:
                payload = deepcopy(original)
                if damaged == "review":
                    payload["archive_description"]["declaration"]["category_review"]["status"] = "pending"
                elif damaged == "body_hash":
                    payload["archive_description"]["declaration"]["category_review"]["archive_basis"]["source_checks"][0]["body_sha256"] = "c" * 64
                else:
                    payload["archive_description"]["declaration"]["occurrence_album_ids"].append(14)
                evidence.research_payload = payload
            db.commit()
            assert {item.id: item.display_event for item in _list(db, lang="en").items}[12] == "Event name unverified"
            assert _list(db, q=ARCHIVE_DISPLAYS["en"], lang="en").items == []
            assert coverage_report(engine, later_inv, languages=("en",))["languages"]["en"]["by_decision"] == {}
            evidence.review_status = "approved"
            evidence.research_payload = deepcopy(original)
            db.commit()
        db.delete(db.query(KifuAlbum).filter_by(id=14).one())
        db.delete(db.query(KifuEvent).filter_by(id=91).one())
        db.commit()
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert db.query(KifuRawEventValue).filter_by(id=owner_id).first() is None
        assert db.query(KifuRawEventName).filter_by(raw_event_id=owner_id).count() == 0
        assert db.query(KifuNameResearchEvidence).filter_by(raw_event_id=owner_id).count() == 0
        assert db.query(KifuEvent).count() == db.query(KifuEventAlias).count() == 0
        assert db.query(KifuAlbum).filter(KifuAlbum.id.in_([12, 13]), KifuAlbum.event_id.isnot(None)).count() == 0


@pytest.mark.parametrize("bundle_format", [1, 2])
def test_archive_owner_rejects_conventional_replacement_without_category_manifest(engine, tmp_path, bundle_format):
    from tests.web_ui.test_kifu_name_candidates import archive_registry, ARCHIVE_DISPLAYS
    from katrain.web.kifu.name_batch import _image

    inv, original, _ = _archive_fixture_bundle(engine, tmp_path)
    applied = apply_bundle(engine, original, archive_registry(), inv, [])
    owner = {"kind": "raw_event", "id": applied["resolved_refs"]["raw_event:@hoensha-archive"]}
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.insert().values(id=14, player_black="Alpha", player_white="Beta", event="Hoensha game", source_path="unreviewed.sgf", sgf_content="(;EV[Hoensha game])"))
    inv = build_inventory(engine, inventory_format=4)
    replacement, records = player_bundle(inv, display=ARCHIVE_DISPLAYS["ru"])
    replacement["inventory_format"] = 4
    replacement["members"][0].update(owner=owner, raw_value="Hoensha game")
    record = records[0]
    record["owner"] = owner
    record["source_checks"][0]["owner"] = owner
    record["original_name"] = "Hoensha game"
    row = replacement["candidates"][0]
    row.update(owner=owner, raw_value="Hoensha game", research_sha256=canonical_sha256(record),
               name_preimage_sha256=name_preimage_sha256(engine, owner, "ru"))
    del row["preimage_binding"]
    bind_fixture_candidate(row)
    replacement["member_set_sha256"] = canonical_sha256(replacement["members"])
    if bundle_format == 2:
        # Deliberately omit category/parser_version from this existing owner's manifest.
        declaration = {"owner": owner, "preimage": {"id": owner["id"], "raw_value": "Hoensha game"},
                       "occurrence_album_ids": [12, 13, 14], "occurrence_sha256": canonical_sha256([12, 13, 14])}
        replacement = _v2_wrap(engine, inv, replacement, [declaration], [])
    before = counts(engine)
    with engine.connect() as conn:
        name = conn.scalar(select(KifuRawEventName.id).where(KifuRawEventName.raw_event_id == owner["id"], KifuRawEventName.lang == "ru"))
        before_name = _image(conn, KifuRawEventName.__table__, name)
        before_evidence = _image(conn, KifuNameResearchEvidence.__table__, before_name["evidence_id"])
    for operation in (dry_run_bundle, apply_bundle):
        with pytest.raises(BatchError, match="archive"):
            operation(engine, replacement, registry(), inv, records)
        assert counts(engine) == before
        with engine.connect() as conn:
            assert _image(conn, KifuRawEventName.__table__, name) == before_name
            assert _image(conn, KifuNameResearchEvidence.__table__, before_name["evidence_id"]) == before_evidence


@pytest.mark.parametrize("damage", ["conventional", "unknown_version"])
def test_archive_runtime_rejects_incompatible_persisted_decision_or_version(engine, tmp_path, monkeypatch, damage):
    from tests.web_ui.test_kifu_name_candidates import archive_registry, ARCHIVE_DISPLAYS
    from tests.web_ui.test_kifu_name_api import _list
    from katrain.web.kifu.identity import strict_slot_approvals
    from katrain.web.kifu.name_coverage import coverage_report

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inv, original, _ = _archive_fixture_bundle(engine, tmp_path)
    applied = apply_bundle(engine, original, archive_registry(), inv, [])
    owner_id = applied["resolved_refs"]["raw_event:@hoensha-archive"]
    with Session(engine) as db:
        db.add(KifuAlbum(id=14, player_black="Alpha", player_white="Beta", event="Hoensha game", source_path="unreviewed.sgf", sgf_content="(;EV[Hoensha game])"))
        db.commit()
        inv = build_inventory(engine, inventory_format=4)
        name = db.query(KifuRawEventName).filter_by(raw_event_id=owner_id, lang="en").one()
        evidence = db.query(KifuNameResearchEvidence).filter_by(id=name.evidence_id).one()
        assert {item.id: item.display_event for item in _list(db, lang="en").items}[12] == ARCHIVE_DISPLAYS["en"]
        assert {item.id: item.display_event for item in _list(db, lang="en").items}[14] == "Event name unverified"
        if damage == "conventional":
            name.decision_kind = evidence.decision_kind = "conventional"
            name.generation_rule_version = evidence.generation_rule_version = "none"
        else:
            name.generation_rule_version = evidence.generation_rule_version = "archive-description-v999"
        db.commit()
        displayed = {item.id: item.display_event for item in _list(db, lang="en").items}
        assert displayed[12] == displayed[14] == "Event name unverified"
        assert _list(db, q=ARCHIVE_DISPLAYS["en"], lang="en").items == []
        albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_([12, 13, 14])).all()
        assert all(slots[2] is None for slots in strict_slot_approvals(db, albums, "en").values())
        assert coverage_report(engine, inv, languages=("en",))["languages"]["en"]["by_decision"] == {}
        name.decision_kind = evidence.decision_kind = "archive_description"
        name.generation_rule_version = evidence.generation_rule_version = "archive-description-v1"
        db.commit()
        assert [item.id for item in _list(db, q=ARCHIVE_DISPLAYS["en"], lang="en").items] == [13, 12]
        assert coverage_report(engine, inv, languages=("en",))["languages"]["en"]["by_decision"] == {"archive_description": 2}


def positive_ja_ko_bundle(inv):
    from tests.web_ui.test_kifu_name_candidates import positive_ja_ko_fixture
    evidence, row = positive_ja_ko_fixture()
    evidence["registry_sha256"] = registry_sha256(registry())
    row["research_sha256"] = canonical_sha256(evidence)
    row["generated_review"]["research_sha256"] = row["research_sha256"]
    row["name_preimage_sha256"] = None
    bind_fixture_candidate(row)
    proposed, _ = player_bundle(inv)
    member = {"owner": row["owner"], "lang": row["lang"]}
    proposed.update(members=[member], member_set_sha256=canonical_sha256([member]), candidates=[row])
    return proposed, [evidence]


def positive_zh_ko_bundle(inv, owner_id=5498, *, source_anchors=(), source_registry=None):
    from tests.web_ui.test_kifu_name_candidates import positive_zh_ko_fixture

    research, row, reg = positive_zh_ko_fixture(owner_id)
    if source_registry is not None:
        reg = source_registry
        research["registry_sha256"] = registry_sha256(reg)
    research["positive_zh_ko"]["source_anchors"] = list(source_anchors)
    row["research_sha256"] = canonical_sha256(research)
    row["generated_review"]["research_sha256"] = row["research_sha256"]
    row["generated_review"]["positive_zh_ko_sha256"] = canonical_sha256(research["positive_zh_ko"])
    row["name_preimage_sha256"] = None
    row["preimage_binding"] = {
        "actor_id": "fixture-binder-3", "actor_model": "gpt-6.1-sol",
        "captured_at": "2026-10-08T21:56:00Z", "bound_at": "2026-10-08T21:57:00Z",
        "name_preimage_sha256": None, "source_candidate_sha256": canonical_sha256(row),
        "capture_sha256": hashlib.sha256(b"synthetic Chinese preimage capture").hexdigest(),
    }
    proposed, _ = player_bundle(inv)
    member = {"owner": row["owner"], "lang": "ko"}
    proposed.update(registry_sha256=registry_sha256(reg), members=[member],
                    member_set_sha256=canonical_sha256([member]), candidates=[row])
    return proposed, [research], reg


def test_positive_zh_ko_importer_reader_requires_exact_applied_ledger(engine):
    from katrain.web.kifu.identity import _approved_names, _qualified_name_rows, strict_display_maps
    from katrain.web.kifu.name_coverage import coverage_report

    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=5498, canonical_name="王宏伟"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, black_player_id=5498, player_black="王宏伟", player_white="Unknown",
            event="GNUGo3.8", sgf_content="(;FF[4]PB[王宏伟]PW[Unknown]EV[GNUGo3.8])", source_path="two.sgf"))
    inv = build_inventory(engine)
    proposed, evidence, reg = positive_zh_ko_bundle(inv)
    receipt = apply_bundle(engine, proposed, reg, inv, evidence)
    with Session(engine) as db:
        def eligible():
            return _qualified_name_rows(db, _approved_names(db, KifuPlayerName, "player_id", [5498], "ko"),
                                        KifuPlayerName, "player_id")

        def visible_ids():
            return [name.player_id for name, _ in _qualified_name_rows(
                db, _approved_names(db, KifuPlayerName, "player_id", [5498], "ko").filter(
                    KifuPlayerName.display_name == "왕훙웨이"), KifuPlayerName, "player_id")]

        album = db.get(KifuAlbum, 12)

        assert [name.player_id for name, _ in eligible()] == [5498]
        assert visible_ids() == [5498]
        assert strict_display_maps(db, [album], "ko")[0][5498] == "왕훙웨이"
        assert coverage_report(engine, inv, languages=("ko",))["languages"]["ko"]["by_decision"]["generated"] == 1
        proof = db.query(KifuNameResearchEvidence).one()
        original = deepcopy(proof.research_payload)
        assert original["normative_zh_ko"] == {
            "batch_id": receipt["batch_id"], "research_sha256": canonical_sha256(evidence[0]),
            "candidate_sha256": canonical_sha256(proposed["candidates"][0])}
        batch = db.get(KifuNameBatch, receipt["batch_id"])
        batch.status = "pending"
        db.flush()
        assert eligible() == []

        assert visible_ids() == []
        assert 5498 not in strict_display_maps(db, [album], "ko")[0]
        batch.status = "applied"
        for malformed in (True, [], receipt["batch_id"] + 1):
            changed = deepcopy(original)
            changed["normative_zh_ko"]["batch_id"] = malformed
            proof.research_payload = changed
            db.flush()
            assert eligible() == []
        changed = deepcopy(original)
        changed["candidate"]["display_name"] = "바뀐 이름"
        proof.research_payload = changed
        db.flush()
        assert eligible() == []
        proof.research_payload = original
        artifact = deepcopy(batch.reviewed_artifact)
        damaged_artifact = deepcopy(artifact)
        damaged_artifact["normative_research"][0]["reading"] = "other reading"
        batch.reviewed_artifact = damaged_artifact
        db.flush()
        assert eligible() == []
        batch.reviewed_artifact = artifact
        db.flush()
        for removed in ("normative_zh_ko", "research"):
            changed = deepcopy(original)
            changed.pop(removed)
            proof.research_payload = changed
            db.flush()
            assert eligible() == []
        proof.research_payload = {"candidate": {}, "research": {}}
        name = db.query(KifuPlayerName).one()
        name.generation_rule_version = "legacy-generated-v1"
        proof.generation_rule_version = "legacy-generated-v1"
        db.flush()
        assert eligible() == []
        legacy_like = deepcopy(original)
        legacy_like.pop("normative_zh_ko")
        legacy_like["research"].pop("source_basis")
        legacy_like["research"].pop("positive_zh_ko")
        legacy_like["research"]["scope_status"] = "not_found_in_scope"
        legacy_like["research"]["candidate_name"] = ""
        legacy_like["research"]["negative_closure"] = {"version": 1}
        legacy_like["candidate"]["generation_rule_version"] = "legacy-generated-v1"
        proof.research_payload = legacy_like
        db.flush()
        assert eligible() == []


def test_legacy_zh_negative_creation_reader_restores_only_unchanged_applied_name(engine):
    from datetime import datetime
    from katrain.web.kifu.identity import _approved_names, _qualified_name_rows, strict_display_maps, strict_slot_approvals
    from katrain.web.kifu.name_coverage import coverage_report
    from katrain.web.kifu.name_evidence import (
        negative_closure_evidence_sha256, negative_closure_scope_sha256,
        negative_closure_template_sha256, validate_research_record,
    )
    from tests.web_ui.test_kifu_name_candidates import approved_generated, candidate, check, research
    from tests.web_ui.test_kifu_name_api import _list
    from katrain.web.kifu.name_batch import _image

    source_registry = registry()
    source_registry["sources"][0]["language"] = "ko"
    owner = {"kind": "player", "id": 17}
    source_check = check(
        owner=owner, status="not_found", candidate_name="", identity_basis="", observed_lang="ko",
        body_excerpt="No player matched this query", check_id="ko-search", method="site_search",
        response_sha256="a" * 64, completeness="complete", searched_forms=["선이언"],
        entity_field_scope=None, scan_id="ko-profiles", page_index=1, page_count=1,
        next_page_url="", pagination_exhausted=True, pagination_basis="No next-page link",
        search_scope="Indexed profiles", scope_complete=True, negative_outcome="no_target_string",
    )
    researched = research(
        owner=owner, lang="ko", registry_sha256=registry_sha256(source_registry),
        original_name="沈逸恩", original_language="zh", source_lang="zh", reading="Shen Yi'en",
        scope_status="not_found_in_scope", candidate_name="", source_checks=[source_check],
        produced_at="2026-10-02T10:05:00Z",
    )
    researched["negative_closure"] = {
        "version": 1, "owner": owner, "lang": "ko", "source_lang": "zh", "scope_id": "player-17-ko",
        "scope_version": "1", "registry_sha256": researched["registry_sha256"],
        "required_check_ids": ["ko-search"], "scope_boundary": "Indexed profiles only",
        "required_checks": [{key: source_check[key] for key in (
            "check_id", "source_id", "method", "query", "url", "searched_forms",
            "entity_field_scope", "scan_id", "page_index", "page_count", "next_page_url",
            "pagination_exhausted", "pagination_basis") }],
        "known_leads": [], "retained_limitations": ["Printed sources"],
        "reviewer_id": "scope-reviewer", "reviewer_model": "gpt-6-astra",
        "reviewed_at": "2026-10-02T10:30:00Z", "conclusion": "approved_not_found_in_scope",
        "reason": "No admissible Korean name in the searched scope",
    }
    closure = researched["negative_closure"]
    closure["scope_template_sha256"] = negative_closure_template_sha256(researched)
    closure["scope_sha256"] = negative_closure_scope_sha256(researched)
    closure["evidence_sha256"] = negative_closure_evidence_sha256(researched)
    validate_research_record(researched, source_registry)
    row = approved_generated(candidate(
        owner=owner, lang="ko", display_name="선이언", decision_kind="generated",
        generation_rule_version="nikl-zh-ko-personal-name-v1",
        research_sha256=canonical_sha256(researched), produced_at="2026-10-02T10:40:00Z",
    ), researched)
    payload = {"candidate": row, "research": researched}
    timestamp = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
    with engine.begin() as conn:
        conn.execute(KifuNameSourceRegistry.__table__.insert().values(
            id=41, version=source_registry["version"], sha256=registry_sha256(source_registry),
            registry=source_registry))
        conn.execute(KifuNameBatch.__table__.insert().values(
            id=332, bundle_sha256="b" * 64, inventory_sha256="c" * 64,
            source_registry_id=41, reviewed_artifact={}, status="applied"))
        conn.execute(KifuNameResearchEvidence.__table__.insert().values(
            id=42, player_id=17, lang="ko", revision=1, source_registry_id=41,
            candidate_name=row["display_name"], decision_kind="generated",
            generation_rule_version=row["generation_rule_version"], research_payload=payload,
            producer_id=row["producer_id"], producer_model=row["producer_model"],
            produced_at=timestamp(row["produced_at"]), reviewer_id=row["reviewer_id"],
            reviewer_model=row["reviewer_model"], reviewed_at=timestamp(row["reviewed_at"]),
            review_status="approved"))
        conn.execute(KifuPlayerName.__table__.insert().values(
            id=43, player_id=17, lang="ko", display_name=row["display_name"], status="verified",
            decision_kind="generated", generation_rule_version=row["generation_rule_version"],
            revision=1, evidence_id=42))
        conn.execute(KifuNameChange.__table__.insert().values(
            id=44, batch_id=332, sequence=1, target_table="kifu_name_research_evidence",
            target_row_id=42, before_image=None,
            after_image=_image(conn, KifuNameResearchEvidence.__table__, 42)))
    inv = build_inventory(engine)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        batch = db.get(KifuNameBatch, 332)
        evidence = db.get(KifuNameResearchEvidence, 42)

        def eligible():
            return _qualified_name_rows(db, _approved_names(db, KifuPlayerName, "player_id", {17}, "ko"),
                                        KifuPlayerName, "player_id")

        assert [name.display_name for name, _ in eligible()] == ["선이언"]
        assert strict_display_maps(db, [album], "ko")[0][17] == "선이언"
        assert [item.id for item in _list(db, q="선이언", lang="ko").items] == [11]
        assert strict_slot_approvals(db, [album], "ko")[11][0] == ("generated", 42)
        assert coverage_report(engine, inv, languages=("ko",))["languages"]["ko"]["by_decision"]["generated"] == 1
        batch.status = "pending"
        db.flush()
        assert eligible() == []
        assert _list(db, q="선이언", lang="ko").items == []
        assert strict_slot_approvals(db, [album], "ko")[11][0] is None
        batch.status = "applied"
        evidence.candidate_name = "선이언 "
        db.flush()
        assert eligible() == []
        evidence.candidate_name = "선이언"
        db.query(KifuNameChange).filter_by(id=44).delete()
        db.flush()
        assert eligible() == []


@pytest.mark.parametrize("owner_id", [5498, 9999])
def test_positive_zh_ko_rejects_published_target_and_cross_owner_collision(engine, owner_id):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=5498, canonical_name="王宏伟"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, black_player_id=5498, player_black="王宏伟", player_white="Unknown",
            event="GNUGo3.8", sgf_content="(;FF[4]PB[王宏伟]PW[Unknown]EV[GNUGo3.8])", source_path="two.sgf"))
        if owner_id != 5498:
            conn.execute(KifuPlayer.__table__.insert().values(id=owner_id, canonical_name="Other"))
        conn.execute(KifuPlayerName.__table__.insert().values(
            player_id=owner_id, lang="ko", display_name="왕훙웨이", status="verified",
            decision_kind="conventional", generation_rule_version="none", revision=1))
    inv = build_inventory(engine)
    proposed, evidence, reg = positive_zh_ko_bundle(inv)
    with pytest.raises(BatchError):
        apply_bundle(engine, proposed, reg, inv, evidence)


def _qualified_source_anchor(engine, inv, reg, lang, display, *, owner_id=5498,
                             original_name="王宏伟", reading="Wang Hongwei"):
    from katrain.web.kifu.name_batch import _image
    from tests.web_ui.test_kifu_name_candidates import candidate, check, research

    owner = {"kind": "player", "id": owner_id}
    source_id, url, observed = (("cwa", "https://wqapi.cwql.org.cn/playerInfo/professional/list", "zh-Hans")
                                if lang == "cn" else ("ugo", "https://db.u-go.net/1923/", "en"))
    source_check = check(owner=owner, source_id=source_id, url=url, observed_lang=observed,
                         query=display, candidate_name=display, body_excerpt=f"Go player {display}",
                         body_sha256=hashlib.sha256(display.encode()).hexdigest())
    found = research(owner=owner, lang=lang, registry_sha256=registry_sha256(reg),
                     candidate_name=display, source_checks=[source_check], original_name=original_name,
                     original_language="zh-Hans", original_language_basis_url=url,
                     reading=reading, reading_basis_url="https://db.u-go.net/1923/")
    row = candidate(owner=owner, lang=lang, display_name=display,
                    research_sha256=canonical_sha256(found), name_preimage_sha256=None)
    bind_fixture_candidate(row)
    proposed, _ = player_bundle(inv)
    member = {"owner": owner, "lang": lang}
    proposed.update(registry_sha256=registry_sha256(reg), members=[member],
                    member_set_sha256=canonical_sha256([member]), candidates=[row])
    receipt = apply_bundle(engine, proposed, reg, inv, [found])
    with engine.connect() as conn:
        name_id = conn.scalar(select(KifuPlayerName.id).where(KifuPlayerName.player_id == owner_id,
                                                               KifuPlayerName.lang == lang))
        name = _image(conn, KifuPlayerName.__table__, name_id)
        evidence = _image(conn, KifuNameResearchEvidence.__table__, name["evidence_id"])
        batch = _image(conn, KifuNameBatch.__table__, receipt["batch_id"])
    kind = "verified_chinese_display" if lang == "cn" else "verified_english_display"
    content = {"reference_kind": kind, "owner": owner, "original_name": display,
               "source_lang": "zh-Hans" if lang == "cn" else "en",
               "source_script": "Hans" if lang == "cn" else "Latin",
               "binding": {"kind": kind, "owner": owner, "source_name": name, "source_evidence": evidence,
                           "source_batch": {"id": batch["id"], "bundle_sha256": batch["bundle_sha256"],
                                            "evidence_creation_sha256": canonical_sha256(evidence)}}}
    return {"evidence_kind": "primary_orthographic", "version": 1, "content": content,
            "approval": {"status": "approved", "content_sha256": canonical_sha256(content),
                         "producer_id": "source-binder", "producer_model": "gpt-6.1-sol",
                         "produced_at": "2026-10-08T21:53:00Z", "reviewer_id": "source-reviewer",
                         "reviewer_model": "gpt-6-astra", "reviewed_at": "2026-10-08T21:54:00Z",
                         "conclusion": "approved_orthographic_original"}}


@pytest.mark.parametrize("revoked_lang", ["cn", "en"])
@pytest.mark.parametrize("tamper", ["batch", "name", "evidence", "creation_ledger"])
def test_positive_zh_ko_source_revocation_hides_display_search_and_coverage(engine, revoked_lang, tamper):
    from katrain.web.kifu.identity import _approved_names, _qualified_name_rows, strict_display_maps
    from katrain.web.kifu.name_coverage import coverage_report

    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=5498, canonical_name="王宏伟"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, black_player_id=5498, player_black="王宏伟", player_white="Unknown",
            event="GNUGo3.8", sgf_content="(;FF[4]PB[王宏伟]PW[Unknown]EV[GNUGo3.8])", source_path="two.sgf"))
    inv = build_inventory(engine)
    from tests.web_ui.test_kifu_name_candidates import positive_zh_ko_fixture
    _, _, reg = positive_zh_ko_fixture()
    reg["sources"].append({"id": "ugo", "tier": "language_go", "home_url": "https://db.u-go.net/",
                           "language": "en"})
    anchors = [_qualified_source_anchor(engine, inv, reg, "cn", "王宏伟"),
               _qualified_source_anchor(engine, inv, reg, "en", "Wang Hongwei")]
    proposed, evidence, reg = positive_zh_ko_bundle(inv, source_anchors=anchors, source_registry=reg)
    source_batch_id = next(anchor["content"]["binding"]["source_batch"]["id"] for anchor in anchors
                           if anchor["content"]["binding"]["source_name"]["lang"] == revoked_lang)
    with engine.begin() as conn:
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == source_batch_id).values(status="pending"))
    with pytest.raises(BatchError):
        apply_bundle(engine, proposed, reg, inv, evidence)
    with engine.begin() as conn:
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == source_batch_id).values(status="applied"))
    apply_bundle(engine, proposed, reg, inv, evidence)
    from katrain.web.kifu.name_batch import _image
    from katrain.web.kifu.name_evidence import persisted_positive_zh_ko_eligible
    with engine.connect() as conn:
        ko_id = conn.scalar(select(KifuPlayerName.id).where(KifuPlayerName.player_id == 5498,
                                                             KifuPlayerName.lang == "ko"))
        ko_name = _image(conn, KifuPlayerName.__table__, ko_id)
        ko_evidence = _image(conn, KifuNameResearchEvidence.__table__, ko_name["evidence_id"])
        ko_batch_id = ko_evidence["research_payload"]["normative_zh_ko"]["batch_id"]
        ko_batch = _image(conn, KifuNameBatch.__table__, ko_batch_id)
        ko_changes = [_image(conn, KifuNameChange.__table__, change_id)
                      for change_id in conn.scalars(select(KifuNameChange.id).where(KifuNameChange.batch_id == ko_batch_id))]
    assert not persisted_positive_zh_ko_eligible(ko_name, ko_evidence, ko_batch, reg, ko_changes)
    from katrain.web.kifu.name_orthographic import verified_source_live
    with engine.connect() as conn:
        assert persisted_positive_zh_ko_eligible(
            ko_name, ko_evidence, ko_batch, reg, ko_changes,
            source_live=lambda anchor: verified_source_live(conn, anchor))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 12)
        query = _approved_names(db, KifuPlayerName, "player_id", [5498], "ko").filter(
            KifuPlayerName.display_name == "왕훙웨이")
        assert [name.player_id for name, _ in _qualified_name_rows(db, query, KifuPlayerName, "player_id")] == [5498]
        assert strict_display_maps(db, [album], "ko")[0][5498] == "왕훙웨이"
    assert coverage_report(engine, inv, languages=("ko",))["languages"]["ko"]["by_decision"]["generated"] == 1
    with engine.begin() as conn:
        source = next(anchor["content"]["binding"] for anchor in anchors
                      if anchor["content"]["binding"]["source_name"]["lang"] == revoked_lang)
        if tamper == "batch":
            conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == source_batch_id).values(status="pending"))
        elif tamper == "name":
            conn.execute(KifuPlayerName.__table__.update().where(
                KifuPlayerName.id == source["source_name"]["id"]).values(display_name="Changed"))
        elif tamper == "evidence":
            conn.execute(KifuNameResearchEvidence.__table__.update().where(
                KifuNameResearchEvidence.id == source["source_evidence"]["id"]).values(producer_model="Changed"))
        else:
            change_id = conn.scalar(select(KifuNameChange.id).where(
                KifuNameChange.batch_id == source_batch_id,
                KifuNameChange.target_table == "kifu_name_research_evidence",
                KifuNameChange.target_row_id == source["source_evidence"]["id"]))
            conn.execute(KifuNameChange.__table__.update().where(KifuNameChange.id == change_id).values(
                after_image={**source["source_evidence"], "producer_model": "Changed"}))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 12)
        query = _approved_names(db, KifuPlayerName, "player_id", [5498], "ko").filter(
            KifuPlayerName.display_name == "왕훙웨이")
        assert _qualified_name_rows(db, query, KifuPlayerName, "player_id") == []
        assert 5498 not in strict_display_maps(db, [album], "ko")[0]
        if revoked_lang == "cn":
            assert strict_display_maps(db, [album], "en")[0][5498] == "Wang Hongwei"
    assert coverage_report(engine, inv, languages=("ko",))["languages"]["ko"]["by_decision"].get("generated", 0) == 0


def test_positive_zh_ko_paired_profile_importer_reader_and_live_source(engine):
    from katrain.web.kifu.identity import _approved_names, _qualified_name_rows, strict_display_maps
    from katrain.web.kifu.name_coverage import coverage_report
    from tests.web_ui.test_kifu_name_candidates import positive_zh_ko_modern_fixture

    owner_id = 5214
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=owner_id, canonical_name="柯沛辰"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, black_player_id=owner_id, player_black="柯沛辰", player_white="Unknown",
            event="GNUGo3.8", sgf_content="(;FF[4]PB[柯沛辰]PW[Unknown]EV[GNUGo3.8])", source_path="two.sgf"))
    inv = build_inventory(engine)
    research, row, reg = positive_zh_ko_modern_fixture(owner_id)
    reg["sources"].append({"id": "ugo", "tier": "language_go", "home_url": "https://db.u-go.net/",
                           "language": "en"})
    research["registry_sha256"] = registry_sha256(reg)
    anchors = [_qualified_source_anchor(engine, inv, reg, "cn", "柯沛辰", owner_id=owner_id,
                                        original_name="柯沛辰", reading="Ke Peichen"),
               _qualified_source_anchor(engine, inv, reg, "en", "Ke Peichen", owner_id=owner_id,
                                        original_name="柯沛辰", reading="Ke Peichen")]
    research["positive_zh_ko"]["source_anchors"] = anchors
    row["research_sha256"] = canonical_sha256(research)
    row["generated_review"]["research_sha256"] = row["research_sha256"]
    row["generated_review"]["positive_zh_ko_sha256"] = canonical_sha256(research["positive_zh_ko"])
    row["name_preimage_sha256"] = None
    row["preimage_binding"] = {
        "actor_id": "fixture-binder-3", "actor_model": "gpt-6.1-sol",
        "captured_at": "2026-10-08T21:56:00Z", "bound_at": "2026-10-08T21:57:00Z",
        "name_preimage_sha256": None, "source_candidate_sha256": canonical_sha256(row),
        "capture_sha256": hashlib.sha256(b"synthetic paired capture").hexdigest(),
    }
    proposed, _ = player_bundle(inv)
    member = {"owner": row["owner"], "lang": "ko"}
    proposed.update(registry_sha256=registry_sha256(reg), members=[member],
                    member_set_sha256=canonical_sha256([member]), candidates=[row])
    receipt = apply_bundle(engine, proposed, reg, inv, [research])

    def qualified(db):
        query = _approved_names(db, KifuPlayerName, "player_id", [owner_id], "ko").filter(
            KifuPlayerName.display_name == "커페이천")
        return [name.player_id for name, _ in _qualified_name_rows(db, query, KifuPlayerName, "player_id")]

    with Session(engine) as db:
        album = db.get(KifuAlbum, 12)
        assert qualified(db) == [owner_id]
        assert strict_display_maps(db, [album], "ko")[0][owner_id] == "커페이천"
    assert coverage_report(engine, inv, languages=("ko",))["languages"]["ko"]["by_decision"]["generated"] == 1
    source_batch_id = anchors[0]["content"]["binding"]["source_batch"]["id"]
    with engine.begin() as conn:
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == source_batch_id).values(status="pending"))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 12)
        assert qualified(db) == []
        assert owner_id not in strict_display_maps(db, [album], "ko")[0]
    assert coverage_report(engine, inv, languages=("ko",))["languages"]["ko"]["by_decision"].get("generated", 0) == 0
    assert batch_status(engine, receipt["batch_id"])["status"] == "applied"


def test_positive_zh_ko_persisted_gate_has_no_importer_dependency(engine, monkeypatch):
    import sys
    from katrain.web.kifu.name_batch import _image
    from katrain.web.kifu.name_evidence import persisted_positive_zh_ko_eligible

    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=5498, canonical_name="王宏伟"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, black_player_id=5498, player_black="王宏伟", player_white="Unknown",
            event="GNUGo3.8", sgf_content="(;FF[4]PB[王宏伟]PW[Unknown]EV[GNUGo3.8])", source_path="two.sgf"))
    inv = build_inventory(engine)
    proposed, evidence, reg = positive_zh_ko_bundle(inv)
    receipt = apply_bundle(engine, proposed, reg, inv, evidence)
    with engine.connect() as conn:
        name_id = conn.scalar(select(KifuPlayerName.id).where(KifuPlayerName.lang == "ko"))
        name = _image(conn, KifuPlayerName.__table__, name_id)
        stored = _image(conn, KifuNameResearchEvidence.__table__, name["evidence_id"])
        batch = _image(conn, KifuNameBatch.__table__, receipt["batch_id"])
        changes = [_image(conn, KifuNameChange.__table__, change_id)
                   for change_id in conn.scalars(select(KifuNameChange.id))]
    monkeypatch.setitem(sys.modules, "katrain.web.kifu.name_candidates", None)
    assert persisted_positive_zh_ko_eligible(name, stored, batch, reg, changes)
    for malformed_id in (True, 1.0):
        changed = deepcopy(stored)
        changed["research_payload"]["normative_zh_ko"]["batch_id"] = malformed_id
        assert not persisted_positive_zh_ko_eligible(name, changed, batch, reg, changes)


def test_positive_ja_ko_importer_reader_requires_exact_applied_ledger(engine):
    from katrain.web.kifu.identity import _approved_names, _qualified_name_rows
    inv = build_inventory(engine)
    proposed, evidence = positive_ja_ko_bundle(inv)
    receipt = apply_bundle(engine, proposed, registry(), inv, evidence)
    with Session(engine) as db:
        def eligible():
            return _qualified_name_rows(db, _approved_names(db, KifuPlayerName, "player_id", [17], "ko"),
                                        KifuPlayerName, "player_id")
        assert len(eligible()) == 1
        name = db.query(KifuPlayerName).one()
        proof = db.query(KifuNameResearchEvidence).one()
        assert proof.research_payload.get("normative_ja_ko", {}).get("batch_id") == receipt["batch_id"]
        batch = db.get(KifuNameBatch, receipt["batch_id"])
        batch.status = "pending"
        db.flush()
        assert eligible() == []
        batch.status = "applied"
        original_payload = deepcopy(proof.research_payload)
        proof.research_payload = {**original_payload, "normative_ja_ko": {"batch_id": receipt["batch_id"] + 1}}
        db.flush()
        assert eligible() == []
        for malformed_id in ([], True):
            altered = deepcopy(original_payload)
            altered['normative_ja_ko']['batch_id'] = malformed_id
            proof.research_payload = altered
            db.flush()
            assert eligible() == []
        for key in ("normative_ja_ko", "research"):
            altered = deepcopy(original_payload)
            altered.pop(key)
            proof.research_payload = altered
            db.flush()
            assert eligible() == []
        altered = deepcopy(original_payload)
        altered["research"]["reading"] = "ご べつじん"
        proof.research_payload = altered
        db.flush()
        assert eligible() == []
        proof.research_payload = {"candidate": {}, "research": {}}
        name.generation_rule_version = "legacy-generated-v1"
        proof.generation_rule_version = "legacy-generated-v1"
        db.flush()
        assert eligible() == []
        name.generation_rule_version = "nikl-ja-ko-personal-name-v1"
        proof.generation_rule_version = "nikl-ja-ko-personal-name-v1"
        proof.research_payload = original_payload
        name.revision += 1
        proof.revision += 1
        db.flush()
        assert eligible() == []
        db.rollback()
    assert apply_bundle(engine, proposed, registry(), inv, evidence)["status"] == "already_applied"
    with engine.begin() as conn:
        conn.execute(KifuPlayerName.__table__.update().values(display_name="바뀐 이름"))
    with pytest.raises(BatchError): apply_bundle(engine, proposed, registry(), inv, evidence)


def test_positive_ja_ko_persisted_gate_has_no_importer_dependency(engine, monkeypatch):
    import sys
    from katrain.web.kifu.name_evidence import persisted_positive_ja_ko_eligible
    from katrain.web.kifu.name_batch import _image
    inv = build_inventory(engine)
    proposed, evidence = positive_ja_ko_bundle(inv)
    receipt = apply_bundle(engine, proposed, registry(), inv, evidence)
    with engine.connect() as conn:
        name_id = conn.scalar(select(KifuPlayerName.id))
        evidence_id = conn.scalar(select(KifuNameResearchEvidence.id))
        name = _image(conn, KifuPlayerName.__table__, name_id)
        stored = _image(conn, KifuNameResearchEvidence.__table__, evidence_id)
        batch = _image(conn, KifuNameBatch.__table__, receipt['batch_id'])
        changes = [_image(conn, KifuNameChange.__table__, change_id)
                   for change_id in conn.scalars(select(KifuNameChange.id))]
    monkeypatch.setitem(sys.modules, 'katrain.web.kifu.name_candidates', None)
    assert persisted_positive_ja_ko_eligible(name, stored, batch, registry(), changes)
