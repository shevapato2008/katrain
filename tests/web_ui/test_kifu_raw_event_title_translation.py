"""Literal raw event titles have exact owner and source scope."""

from copy import deepcopy

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuEventAlias, KifuNameResearchEvidence, KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.identity import (
    _approved_raw_event_names, strict_display_maps, strict_matching_names, strict_raw_event_search_clause,
)
from katrain.web.kifu.legacy_raw_events import reviewed_raw_event_hints, reviewed_raw_event_search_clause
from katrain.web.kifu.name_batch import _image, apply_bundle, dry_run_bundle, undo_batch
from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_candidate
from katrain.web.kifu.name_evidence import EvidenceError, registry_sha256, validate_research_record
from katrain.web.kifu.name_inventory import build_inventory
from tests.web_ui.test_kifu_name_batch import _v2_wrap, bind_fixture_candidate, engine  # noqa: F401
from tests.web_ui.test_kifu_name_candidates import candidate, check, inventory, registry


def owner_review(owner_id, raw):
    return {"version": "raw-event-title-owner-review-v1", "status": "approved", "review_status": "approved",
            "raw_event_id": owner_id, "raw_value": raw,
            "scope_sha256": "1" * 64, "research_manifest_sha256": "2" * 64,
            "producer_id": "producer-1", "producer_model": "gpt-6-sol",
            "produced_at": "2026-10-02T09:00:00Z", "reviewer_id": "reviewer-2",
            "reviewer_model": "gpt-6-astra", "reviewed_at": "2026-10-02T09:30:00Z",
            "review_conclusion": "Reviewed exact raw title",
            "category_basis": "Readable literal raw event title; no event identity or link approved"}


def literal(raw="友情杯第１轮", lang="en", display="Friendship Cup, Round 1"):
    owner = {"kind": "raw_event", "id": 8}
    research = {
        "owner": owner, "lang": lang, "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()), "scope_status": "translated_from_original",
        "candidate_name": display, "translation_method": "literal_event_title",
        "raw_value": raw,
        "raw_parts": [{"kind": "core", "text": "友情杯"}, {"kind": "round", "text": "第１轮"}],
        "original_name": "友情杯", "original_language": "zh-Hans",
        "original_language_basis_url": "https://example.org/friendship",
        "source_checks": [check(owner=owner, query="友情杯", url="https://example.org/friendship",
                                observed_lang="zh-Hans", candidate_name="友情杯", body_excerpt="友情杯围棋赛",
                                identity_basis="Chinese article identifies the Friendship Cup core title")],
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    row = candidate(owner=owner, lang=lang, raw_value=raw, display_name=display,
                    decision_kind="translated", research_sha256=canonical_sha256(research),
                    generation_rule_version="raw-event-title-translation-v1",
                    translation_method="literal_event_title", review_conclusion="Literal title reviewed")
    return row, research


def test_literal_raw_title_accepts_existing_owner_and_fullwidth_round():
    row, research = literal()
    inv = inventory()
    inv["album_associations"].append([3, "Black", "White", row["raw_value"], None, None, None])
    assert validate_research_record(research, registry())["owner"] == row["owner"]
    assert validate_candidate(row, research, registry(), inv) == row


@pytest.mark.parametrize("change", [
    {"raw_value": "友情杯第２轮"},
    {"raw_parts": [{"kind": "core", "text": "友情杯"}]},
    {"raw_parts": [{"kind": "core", "text": "友情杯"}, {"kind": "round", "text": "第十轮"}]},
    {"owner": {"kind": "raw_event", "ref": "new"}},
])
def test_raw_title_research_requires_existing_exact_lossless_owner(change):
    _, research = literal()
    research.update(change)
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


def test_raw_title_candidate_binds_research_hash_and_raw_spelling():
    row, research = literal()
    inv = inventory()
    inv["album_associations"].append([3, "Black", "White", row["raw_value"], None, None, None])
    for change in ({"research_sha256": "0" * 64}, {"raw_value": "友情杯"},
                   {"generation_rule_version": "event-title-translation-v1"}):
        with pytest.raises(CandidateError):
            validate_candidate({**row, **change}, research, registry(), inv)


def reviewed_bundle(engine):
    row, research = literal()
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 8).values(
            raw_value=row["raw_value"], review_status="approved", review_metadata=owner_review(8, row["raw_value"])))
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            event=row["raw_value"], sgf_content=f"(;EV[{row['raw_value']}])"))
    inv = build_inventory(engine, inventory_format=4)
    with engine.connect() as conn:
        before = _image(conn, KifuRawEventValue.__table__, 8)
    declaration = {"owner": row["owner"], "preimage": before, "occurrence_album_ids": [11],
                   "occurrence_sha256": canonical_sha256([11])}
    row["name_preimage_sha256"] = None
    bind_fixture_candidate(row)
    member = {"owner": row["owner"], "lang": row["lang"], "raw_value": row["raw_value"]}
    proposed = {"bundle_format": 2, "inventory_format": 4, "inventory_sha256": inv["sha256"],
                "registry_version": "test-1", "registry_sha256": registry_sha256(registry()),
                "rule_version": "candidate-v1", "members": [member],
                "member_set_sha256": canonical_sha256([member]), "candidates": [row]}
    return _v2_wrap(engine, inv, proposed, [declaration], []), inv, [research]


def test_literal_raw_title_import_display_search_and_undo(engine):
    proposed, inv, research = reviewed_bundle(engine)
    assert dry_run_bundle(engine, proposed, registry(), inv, research)["approved"] == 1
    applied = apply_bundle(engine, proposed, registry(), inv, research)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert album.event_id is None and album.sgf_content == "(;EV[友情杯第１轮])"
        assert db.scalar(select(KifuEventAlias.id).limit(1)) is None
        assert strict_display_maps(db, [album], "en")[-1][(11, album.event, None)] == "Friendship Cup, Round 1"
        assert reviewed_raw_event_hints(db, [album], "en") == {11: "Friendship Cup, Round 1"}
        name = db.scalar(select(KifuRawEventName))
        assert strict_matching_names(db, name.display_name)[-1] == {name.id}
        assert list(db.scalars(select(KifuAlbum.id).where(strict_raw_event_search_clause(db, {name.id})))) == [11]
        assert list(db.scalars(select(KifuAlbum.id).where(
            reviewed_raw_event_search_clause(db, name.display_name)))) == [11]
    undo_batch(engine, applied["batch_id"])
    with Session(engine) as db:
        assert _approved_raw_event_names(db, values={"友情杯第１轮"}) == []


def test_same_literal_title_can_search_two_exact_raw_members(engine):
    proposed, _, research = reviewed_bundle(engine)
    second_raw = "友情杯第1轮"
    second_row, second_research = literal(second_raw)
    second_row["owner"] = second_research["owner"] = second_research["source_checks"][0]["owner"] = {
        "kind": "raw_event", "id": 9}
    second_research["raw_parts"][-1]["text"] = "第1轮"
    second_row["research_sha256"] = canonical_sha256(second_research)
    second_row["name_preimage_sha256"] = None
    bind_fixture_candidate(second_row)
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=9, raw_value=second_raw, category="unclassified_pending", review_status="approved",
            review_metadata=owner_review(9, second_raw)))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Alpha", player_white="Beta", event=second_raw,
            sgf_content=f"(;EV[{second_raw}])", source_path="second.sgf"))
    inv = build_inventory(engine, inventory_format=4)
    with engine.connect() as conn:
        second_before = _image(conn, KifuRawEventValue.__table__, 9)
    second_declaration = {"owner": second_row["owner"], "preimage": second_before,
                          "occurrence_album_ids": [12], "occurrence_sha256": canonical_sha256([12])}
    proposed["inventory_sha256"] = inv["sha256"]
    proposed["members"].append({"owner": second_row["owner"], "lang": "en", "raw_value": second_raw})
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    proposed["candidates"].append(second_row)
    proposed["owners"].append(second_declaration)
    proposed["owner_set_sha256"] = canonical_sha256(proposed["owners"])
    from katrain.web.kifu.name_batch import catalog_snapshot_sha
    proposed["catalog_sha256"] = catalog_snapshot_sha(engine)
    assert dry_run_bundle(engine, proposed, registry(), inv, [*research, second_research])["approved"] == 2
    apply_bundle(engine, proposed, registry(), inv, [*research, second_research])
    with Session(engine) as db:
        ids = strict_matching_names(db, "Friendship Cup, Round 1")[-1]
        assert len(ids) == 2
        assert set(db.scalars(select(KifuAlbum.id).where(strict_raw_event_search_clause(db, ids)))) == {11, 12}
        assert set(db.scalars(select(KifuAlbum.id).where(
            reviewed_raw_event_search_clause(db, "Friendship Cup, Round 1")))) == {11, 12}


def test_second_bundle_accepts_same_title_only_from_approved_raw_translation(engine):
    first, inv, research = reviewed_bundle(engine)
    apply_bundle(engine, first, registry(), inv, research)
    raw = "友情杯第1轮"
    row, evidence = literal(raw)
    owner = {"kind": "raw_event", "id": 9}
    row["owner"] = evidence["owner"] = evidence["source_checks"][0]["owner"] = owner
    evidence["raw_parts"][-1]["text"] = "第1轮"
    row["research_sha256"] = canonical_sha256(evidence)
    row["name_preimage_sha256"] = None
    bind_fixture_candidate(row)
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=9, raw_value=raw, category="unclassified_pending", review_status="approved",
            review_metadata=owner_review(9, raw)))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="A", player_white="B", event=raw,
            sgf_content=f"(;EV[{raw}])", source_path="second.sgf"))
    inv = build_inventory(engine, inventory_format=4)
    with engine.connect() as conn:
        before = _image(conn, KifuRawEventValue.__table__, 9)
    declaration = {"owner": owner, "preimage": before, "occurrence_album_ids": [12],
                   "occurrence_sha256": canonical_sha256([12])}
    second = deepcopy(first)
    second["inventory_sha256"] = inv["sha256"]
    second["members"] = [{"owner": owner, "lang": "en", "raw_value": raw}]
    second["member_set_sha256"] = canonical_sha256(second["members"])
    second["candidates"] = [row]
    second["owners"] = [declaration]
    second["owner_set_sha256"] = canonical_sha256(second["owners"])
    from katrain.web.kifu.name_batch import catalog_snapshot_sha
    second["catalog_sha256"] = catalog_snapshot_sha(engine)
    assert dry_run_bundle(engine, second, registry(), inv, [evidence])["approved"] == 1


def test_five_primary_titles_and_secondary_english_fallback(engine):
    proposed, inv, research = reviewed_bundle(engine)
    displays = {"cn": "友情杯第１轮", "tw": "友情盃第１輪", "jp": "友情杯第１回戦",
                "ko": "우정배 제1라운드"}
    for lang, display in displays.items():
        row, evidence = literal(lang=lang, display=display)
        row["name_preimage_sha256"] = None
        bind_fixture_candidate(row)
        proposed["members"].append({"owner": row["owner"], "lang": lang, "raw_value": row["raw_value"]})
        proposed["candidates"].append(row)
        research.append(evidence)
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    apply_bundle(engine, proposed, registry(), inv, research)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        for lang, display in {**displays, "en": "Friendship Cup, Round 1"}.items():
            assert strict_display_maps(db, [album], lang)[-1][(11, album.event, None)] == display
            assert reviewed_raw_event_hints(db, [album], lang) == {11: display}
        for lang in ("de", "es", "fr", "ru", "tr", "ua"):
            assert reviewed_raw_event_hints(db, [album], lang) == {11: "Friendship Cup, Round 1"}


@pytest.mark.parametrize("damage", ["owner", "raw", "hash", "signature", "pending", "source",
                                    "owner_review", "rule"])
def test_persisted_literal_title_rejects_changed_approval_or_evidence(engine, damage):
    proposed, inv, research = reviewed_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, research)
    with engine.begin() as conn:
        evidence = dict(conn.execute(select(KifuNameResearchEvidence.__table__)).mappings().one())
        payload = deepcopy(evidence["research_payload"])
        if damage == "owner":
            payload["candidate"]["owner"]["id"] = 9
        elif damage == "raw":
            payload["candidate"]["raw_value"] = "Different"
        elif damage == "hash":
            payload["candidate"]["research_sha256"] = "0" * 64
        elif damage == "signature":
            payload["candidate"]["reviewer_id"] = payload["candidate"]["producer_id"]
        elif damage == "pending":
            conn.execute(KifuNameResearchEvidence.__table__.update().values(review_status="pending"))
        elif damage == "owner_review":
            conn.execute(KifuRawEventValue.__table__.update().values(review_metadata=None))
        elif damage == "rule":
            payload["candidate"]["generation_rule_version"] = "forged-rule"
            conn.execute(KifuRawEventName.__table__.update().values(generation_rule_version="forged-rule"))
            conn.execute(KifuNameResearchEvidence.__table__.update().values(generation_rule_version="forged-rule"))
        else:
            payload["research"]["source_checks"][0]["candidate_name"] = "Wrong core"
            payload["candidate"]["research_sha256"] = canonical_sha256(payload["research"])
        if damage not in {"pending", "owner_review"}:
            conn.execute(KifuNameResearchEvidence.__table__.update().values(research_payload=payload))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en") == {}
        assert _approved_raw_event_names(db, values={album.event}, lang="en") == []
