"""The authorized first pass is generated provenance with exact inputs."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_candidate
from katrain.web.kifu.name_evidence import EvidenceError, registry_sha256, validate_research_record
from katrain.web.kifu.name_batch import BatchError, _image, apply_bundle, dry_run_bundle, catalog_snapshot_sha
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.core.models_db import (
    KifuAlbum, KifuPlayer, KifuPlayerName, KifuEvent, KifuEventName,
    KifuRawEventValue, KifuRawPlayerValue, KifuRawPlayerName, KifuNameResearchEvidence,
)
from katrain.web.kifu.identity import (
    _approved_names, _qualified_name_rows, _approved_raw_event_names, _raw_event_map,
    live_event_selections, strict_raw_event_search_clause, strict_selected_event_search_ids,
    strict_display_maps,
)
from katrain.web.kifu.name_first_pass import raw_scope_rows
from katrain.web.kifu.name_raw_player_scope import CONTEXT_FIELDS
from katrain.web.kifu.name_coverage import coverage_report
from sqlalchemy.orm import Session
from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
from tests.web_ui.test_kifu_name_candidates import inventory, registry
from tests.web_ui.test_kifu_name_batch import (
    engine, player_bundle, bind_fixture_candidate, registry as db_registry,
)
from katrain.web.kifu.name_batch import undo_batch, _check_first_pass_sources, _check_name_preimages
from tests.web_ui.test_kifu_name_api import _evidence, _list


def first_pass_pair():
    owner = {"kind": "player", "id": 17}
    research = {
        "owner": owner, "lang": "cn", "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()),
        "source_basis": "user_authorized_first_pass_v1",
        "scope_status": "generated_first_pass", "verification_level": "generated_first_pass",
        "original_name": "吴清源", "original_language": "und",
        "source_input": {"kind": "catalog_canonical", "owner": owner, "text": "吴清源",
                         "owner_preimage_sha256": "a" * 64},
        "generation": {"method": "retain_original"}, "candidate_name": "吴清源",
        "producer_id": "translator", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    candidate = {
        "owner": owner, "lang": "cn", "display_name": "吴清源", "decision_kind": "generated",
        "research_sha256": canonical_sha256(research),
        "generation_rule_version": "user_authorized_first_pass_v1",
        "producer_id": "translator", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-11T01:00:00Z", "review_status": "approved",
        "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
        "reviewed_at": "2026-10-11T01:01:00Z",
        "review_conclusion": "approved_first_pass_display_and_source",
        "generated_review": {"decision": "approve_generated_first_pass", "owner": owner,
                             "lang": "cn", "display_name": "吴清源",
                             "research_sha256": canonical_sha256(research),
                             "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
                             "reviewed_at": "2026-10-11T01:01:00Z"},
    }
    return candidate, research


def test_first_pass_uses_actual_source_without_external_claims():
    candidate, research = first_pass_pair()
    assert validate_research_record(research, registry())["candidate_name"] == "吴清源"
    assert validate_candidate(candidate, research, registry(), inventory())["display_name"] == "吴清源"


def test_first_pass_rejects_mixed_and_unsourced_markers():
    candidate, research = first_pass_pair()
    for key, value in (("negative_closure", {}), ("source_checks", []),
                       ("original_language_basis_url", "https://example.org")):
        bad = deepcopy(research)
        bad[key] = value
        with pytest.raises(EvidenceError):
            validate_research_record(bad, registry())
    bad = deepcopy(candidate)
    bad["decision_kind"] = "conventional"
    with pytest.raises(CandidateError):
        validate_candidate(bad, research, registry(), inventory())


def test_first_pass_keeps_common_player_rank_guard():
    candidate, research = first_pass_pair()
    research["candidate_name"] = "吴清源九段"
    research["generation"]["method"] = "transliteration"
    candidate["display_name"] = candidate["generated_review"]["display_name"] = "吴清源九段"
    candidate["research_sha256"] = candidate["generated_review"]["research_sha256"] = canonical_sha256(research)
    with pytest.raises(CandidateError, match="rank|result"):
        validate_candidate(candidate, research, registry(), inventory())


@pytest.mark.parametrize("raw", ["GNUGo3.8", "个人赛", "(;EV[broken]"])
def test_first_pass_raw_rejects_program_generic_and_damaged_values(raw):
    _candidate, research = first_pass_pair()
    owner = {"kind": "raw_event", "id": 7}
    research.update(owner=owner, original_name=raw, candidate_name="Translated title")
    research["source_input"] = {"kind": "raw_event_literal", "owner": owner, "text": raw,
                                "owner_preimage_sha256": "a" * 64}
    research["raw_scope"] = {"raw_value": raw, "slots": [
        {"album_id": 1, "slot": "event", "raw_value": raw, "event_id": None,
         "approved": True}]}
    with pytest.raises(EvidenceError, match="program|generic|damaged"):
        validate_research_record(research, registry())


def test_first_pass_raw_player_requires_exact_literal_and_signed_scope():
    candidate, research = first_pass_pair()
    owner = {"kind": "raw_player", "id": 20}
    research.update(owner=owner, original_name="李元赫九段", candidate_name="李元赫")
    research["source_input"] = {"kind": "raw_player_literal", "owner": owner,
                                "text": "李元赫九段", "parsed_name": "李元赫", "embedded_rank": "九段",
                                "owner_preimage_sha256": "a" * 64}
    research["generation"]["method"] = "translation"
    research["raw_display_scope_sha256"] = "b" * 64
    candidate.update(owner=owner, raw_value="李元赫九段", display_name="李元赫",
                     raw_display_scope_sha256="b" * 64)
    candidate["research_sha256"] = canonical_sha256(research)
    candidate["generated_review"].update(owner=owner, display_name="李元赫",
                                           research_sha256=candidate["research_sha256"])
    inv = inventory()
    inv["album_associations"][0][1] = "李元赫九段"
    assert validate_research_record(research, registry())["source_input"]["kind"] == "raw_player_literal"
    assert validate_candidate(candidate, research, registry(), inv)["raw_display_scope_sha256"] == "b" * 64
    bad = deepcopy(candidate)
    bad.pop("raw_display_scope_sha256")
    with pytest.raises(CandidateError):
        validate_candidate(bad, research, registry(), inv)
    bad_research = deepcopy(research)
    bad_research["source_input"]["parsed_name"] = "李元赫九段"
    with pytest.raises(EvidenceError):
        validate_research_record(bad_research, registry())
    retained = deepcopy(research)
    retained["generation"]["method"] = "retain_original"
    retained["candidate_name"] = "李元赫九段"
    with pytest.raises(EvidenceError):
        validate_research_record(retained, registry())


def bound_player_bundle(engine):
    inv = build_inventory(engine)
    bundle, _ = player_bundle(inv)
    row, research = first_pass_pair()
    with engine.connect() as conn:
        owner_image = _image(conn, KifuPlayer.__table__, 17)
    research["source_input"]["owner_preimage_sha256"] = canonical_sha256(owner_image)
    research["registry_sha256"] = registry_sha256(db_registry())
    row["research_sha256"] = canonical_sha256(research)
    row["generated_review"]["research_sha256"] = row["research_sha256"]
    row["name_preimage_sha256"] = None
    bind_fixture_candidate(row)
    row["preimage_binding"]["captured_at"] = "2026-10-11T01:00:15Z"
    row["preimage_binding"]["bound_at"] = "2026-10-11T01:00:30Z"
    bundle["members"] = [{"owner": row["owner"], "lang": "cn"}]
    bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
    bundle["candidates"] = [row]
    declaration = {"owner": row["owner"], "preimage": owner_image}
    bundle.update(bundle_format=2, catalog_sha256=catalog_snapshot_sha(engine),
                  owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                  album_links=[], link_set_sha256=canonical_sha256([]))
    return inv, bundle, [research]


def bound_raw_player_bundle(engine, *, five_languages=False, second_raw=False):
    from katrain.web.kifu.name_parse import parse_player

    raw = "李元赫九段"
    with engine.begin() as conn:
        conn.execute(KifuRawPlayerValue.__table__.insert().values(
            id=20, raw_value=raw, category=parse_player(raw, None).category, review_status="pending"))
        conn.execute(KifuAlbum.__table__.insert(), [
            {"id": 12, "player_black": raw, "player_white": "Other", "event": "Cup",
             "sgf_content": "(;PB[李元赫九段])", "source_path": "raw-12.sgf"},
            {"id": 13, "player_black": raw, "black_player_id": 17, "player_white": "Other",
             "event": "Cup", "sgf_content": "(;PB[李元赫九段])", "source_path": "raw-13.sgf"},
            {"id": 14, "duplicate_of_id": 12, "player_black": raw, "player_white": "Other",
             "event": "Cup", "sgf_content": "(;PB[李元赫九段])", "source_path": "raw-14.sgf"},
            {"id": 15, "player_black": "Other", "player_white": raw, "event": "Cup",
             "sgf_content": "(;PW[李元赫九段])", "source_path": "raw-15.sgf"},
        ])
        if second_raw:
            other = "李元赫"
            conn.execute(KifuRawPlayerValue.__table__.insert().values(
                id=21, raw_value=other, category=parse_player(other, None).category, review_status="pending"))
            conn.execute(KifuAlbum.__table__.insert().values(
                id=16, player_black=other, player_white="Other", event="Cup",
                sgf_content="(;PB[李元赫])", source_path="raw-16.sgf"))
    inv, bundle, records = bound_player_bundle(engine)
    owner = {"kind": "raw_player", "id": 20}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuRawPlayerValue.__table__, 20)
        albums = {row["id"]: row for row in conn.execute(KifuAlbum.__table__.select().where(
            KifuAlbum.id.in_([12, 15]))).mappings()}
    content = {"inventory_sha256": inv["sha256"], "raw_value": raw,
               "applicability_basis": "First pass of this exact public unlinked raw slot",
               "slots": [{"album_id": 12, "slot": "black",
                          "context": {key: albums[12][key] for key in CONTEXT_FIELDS}},
                         {"album_id": 15, "slot": "white",
                          "context": {key: albums[15][key] for key in CONTEXT_FIELDS}}]}
    scope = {"content": content, "approval": {
        "status": "approved", "content_sha256": canonical_sha256(content),
        "producer_id": "translator", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-11T01:00:00Z", "reviewer_id": "reviewer",
        "reviewer_model": "gpt-6.1-sol", "reviewed_at": "2026-10-11T01:01:00Z",
        "conclusion": "approved_raw_display_scope"}}
    scope_hash = canonical_sha256(scope)
    displays = {"en": "Lee Wonhyuk", "cn": "李元赫", "tw": "李元赫",
                "jp": "李元赫", "ko": "이원혁"}
    languages = ("en", "cn", "tw", "jp", "ko") if five_languages else ("en",)
    candidates, research_records, members = [], [], []
    for lang in languages:
        research = deepcopy(records[0])
        research.update(owner=owner, lang=lang, original_name=raw, candidate_name=displays[lang],
                        raw_display_scope_sha256=scope_hash)
        research["source_input"] = {"kind": "raw_player_literal", "owner": owner, "text": raw,
                                    "parsed_name": "李元赫", "embedded_rank": "九段",
                                    "owner_preimage_sha256": canonical_sha256(owner_image)}
        research["generation"]["method"] = "transliteration" if lang in {"en", "ko"} else "retain_original"
        candidate = deepcopy(bundle["candidates"][0])
        candidate.update(owner=owner, lang=lang, raw_value=raw, display_name=displays[lang],
                         raw_display_scope_sha256=scope_hash, research_sha256=canonical_sha256(research))
        candidate["generated_review"].update(owner=owner, lang=lang, display_name=displays[lang],
                                              research_sha256=candidate["research_sha256"])
        candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(candidate)
        candidates.append(candidate)
        research_records.append(research)
        members.append({"owner": owner, "lang": lang, "raw_value": raw})
    declaration = {"owner": owner, "preimage": owner_image,
                   "occurrence_album_ids": [12, 13, 14, 15],
                   "occurrence_sha256": canonical_sha256([12, 13, 14, 15]),
                   "raw_display_scope": scope}
    bundle.update(members=members, member_set_sha256=canonical_sha256(members), candidates=candidates,
                  owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                  catalog_sha256=catalog_snapshot_sha(engine))
    if second_raw:
        with engine.connect() as conn:
            other_image = _image(conn, KifuRawPlayerValue.__table__, 21)
            album = conn.execute(KifuAlbum.__table__.select().where(KifuAlbum.id == 16)).mappings().one()
        other_owner = {"kind": "raw_player", "id": 21}
        other_content = deepcopy(content)
        other_content.update(raw_value="李元赫", slots=[{
            "album_id": 16, "slot": "black", "context": {key: album[key] for key in CONTEXT_FIELDS},
        }])
        other_scope = deepcopy(scope)
        other_scope["content"] = other_content
        other_scope["approval"]["content_sha256"] = canonical_sha256(other_content)
        other_research = deepcopy(research_records[0])
        other_research.update(owner=other_owner, original_name="李元赫",
                              raw_display_scope_sha256=canonical_sha256(other_scope))
        other_research["source_input"].update(
            owner=other_owner, text="李元赫", parsed_name="李元赫", embedded_rank=None,
            owner_preimage_sha256=canonical_sha256(other_image))
        other_candidate = deepcopy(candidates[0])
        other_candidate.update(owner=other_owner, raw_value="李元赫",
                               raw_display_scope_sha256=canonical_sha256(other_scope),
                               research_sha256=canonical_sha256(other_research))
        other_candidate["generated_review"].update(owner=other_owner,
                                                  research_sha256=other_candidate["research_sha256"])
        other_candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(other_candidate)
        other_declaration = {"owner": other_owner, "preimage": other_image,
                             "occurrence_album_ids": [16], "occurrence_sha256": canonical_sha256([16]),
                             "raw_display_scope": other_scope}
        bundle["candidates"].append(other_candidate)
        bundle["members"].append({"owner": other_owner, "lang": "en", "raw_value": "李元赫"})
        bundle["owners"].append(other_declaration)
        research_records.append(other_research)
        bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
        bundle["owner_set_sha256"] = canonical_sha256(bundle["owners"])
    return inv, bundle, research_records


def test_first_pass_raw_player_applies_only_to_public_unlinked_signed_slot_and_undoes(engine, monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    inv, bundle, records = bound_raw_player_bundle(engine, five_languages=True)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, records)["ready"]
    result = apply_bundle(engine, bundle, db_registry(), inv, records)
    assert result["status"] == "applied"
    assert apply_bundle(engine, bundle, db_registry(), inv, records)["status"] == "already_applied"
    from katrain.web.kifu.identity import _approved_raw_player_names
    with Session(engine) as db:
        for lang, display in (("en", "Lee Wonhyuk"), ("cn", "李元赫"), ("tw", "李元赫"),
                              ("jp", "李元赫"), ("ko", "이원혁")):
            names = _approved_raw_player_names(db, values={"李元赫九段"}, lang=lang)
            assert len(names) == 1 and names[0][2] is not None
            assert {item.id for item in _list(db, display, lang).items if item.id in {12, 15}} == {12, 15}
            page = {item.id: item for item in _list(db, lang=lang).items}
            assert display in page[12].display_player_black
            assert display in page[15].display_player_white
    report = coverage_report(engine, inv, languages=("en", "cn", "tw", "jp", "ko"))
    assert not any((item["album_id"], item["slot"]) in {(12, "black"), (15, "white")}
                   for item in report["missing_examples"])
    with engine.connect() as conn:
        raw_album = conn.execute(KifuAlbum.__table__.select().where(KifuAlbum.id == 12)).mappings().one()
        assert (raw_album["player_black"], raw_album["black_player_id"], raw_album["black_rank"],
                raw_album["sgf_content"]) == ("李元赫九段", None, None, "(;PB[李元赫九段])")
    assert undo_batch(engine, result["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert all(_approved_raw_player_names(db, values={"李元赫九段"}, lang=lang) == []
                   for lang in ("en", "cn", "tw", "jp", "ko"))


@pytest.mark.parametrize("drift", ["linked", "hidden"])
def test_first_pass_raw_player_rejects_linked_or_hidden_scope_after_apply(engine, drift):
    from katrain.web.kifu.identity import _approved_raw_player_names
    from katrain.web.kifu.name_first_pass import raw_player_scope_live

    inv, bundle, records = bound_raw_player_bundle(engine)
    scope = bundle["owners"][0]["raw_display_scope"]
    with engine.connect() as conn:
        assert raw_player_scope_live(conn, scope)
    apply_bundle(engine, bundle, db_registry(), inv, records)
    with engine.begin() as conn:
        changes = {"black_player_id": 17} if drift == "linked" else {"list_hidden_reason": "manual"}
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(**changes))
    with engine.connect() as conn:
        assert not raw_player_scope_live(conn, scope)
        with pytest.raises(BatchError, match="public unlinked scope changed"):
            _check_first_pass_sources(conn, bundle["candidates"],
                                      {canonical_sha256(records[0]): records[0]}, bundle["owners"])
    with Session(engine) as db:
        assert _approved_raw_player_names(db, values={"李元赫九段"}, lang="en") == []


def test_first_pass_raw_player_public_scope_uses_physical_columns_with_thin_mapper(engine, monkeypatch):
    from katrain.web.core import models_db
    from katrain.web.kifu.name_first_pass import raw_player_scope_live

    _inv, bundle, _records = bound_raw_player_bundle(engine)
    with monkeypatch.context() as patch:
        patch.setattr(models_db, "KifuAlbum", SimpleNamespace)
        with engine.connect() as conn:
            assert raw_player_scope_live(conn, bundle["owners"][0]["raw_display_scope"])


def test_first_pass_raw_player_pending_owner_does_not_enable_old_profile(engine):
    from katrain.web.kifu.identity import _approved_raw_player_names

    _inv, bundle, _records = bound_raw_player_bundle(engine)
    with Session(engine) as db:
        evidence = _evidence(db, "raw_player", 20, "en", "Old profile")
        db.add(KifuRawPlayerName(raw_player_id=20, lang="en", display_name="Old profile",
                                 status="verified", decision_kind="conventional",
                                 generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()
        assert _approved_raw_player_names(db, values={"李元赫九段"}, lang="en") == []
    with engine.connect() as conn:
        target = conn.execute(KifuRawPlayerName.__table__.select()).mappings().one()
        candidate = deepcopy(bundle["candidates"][0])
        candidate["name_preimage_sha256"] = canonical_sha256(_image(conn, KifuRawPlayerName.__table__, target["id"]))
        with pytest.raises(BatchError, match="cannot replace verified or evidence-backed"):
            _check_name_preimages(conn, [candidate])


def test_first_pass_raw_player_rejects_existing_cross_owner_name_collision(engine):
    inv, bundle, records = bound_raw_player_bundle(engine)
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "en", "Lee Wonhyuk")
        db.add(KifuPlayerName(player_id=17, lang="en", display_name="Lee Wonhyuk",
                               status="verified", decision_kind="conventional",
                               generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()
    with pytest.raises(BatchError, match="collision"):
        dry_run_bundle(engine, bundle, db_registry(), inv, records)


def _share_raw_display(candidate):
    candidate["collision_decision"] = "shared_display"
    candidate["collision_basis"] = {
        "kind": "literal_translation", "source_text": candidate["raw_value"],
        "parsed_name": "李元赫", "provenance": "signed_raw_player_literal",
    }
    candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(candidate)


def _one_raw_bundle(bundle, records, index):
    one = deepcopy(bundle)
    one["candidates"] = [deepcopy(bundle["candidates"][index])]
    one["members"] = [deepcopy(bundle["members"][index])]
    one["owners"] = [deepcopy(bundle["owners"][index])]
    one["member_set_sha256"] = canonical_sha256(one["members"])
    one["owner_set_sha256"] = canonical_sha256(one["owners"])
    return one, [deepcopy(records[index])]


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_first_pass_two_raw_players_share_display_across_batches_and_search(engine, order):
    inv, bundle, records = bound_raw_player_bundle(engine, second_raw=True)
    for candidate in bundle["candidates"]:
        _share_raw_display(candidate)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, records)["ready"]
    for index in order:
        one, one_records = _one_raw_bundle(bundle, records, index)
        assert apply_bundle(engine, one, db_registry(), inv, one_records)["status"] == "applied"
    with Session(engine) as db:
        from katrain.web.kifu.identity import strict_matching_names
        assert strict_matching_names(db, "Lee Wonhyuk")[:3] == (set(), set(), {"李元赫九段", "李元赫"})
        assert {item.id for item in _list(db, "Lee Wonhyuk", "en").items if item.id in {12, 15, 16}} == {
            12, 15, 16,
        }


def test_first_pass_two_raw_players_share_display_in_same_bundle(engine):
    inv, bundle, records = bound_raw_player_bundle(engine, second_raw=True)
    for candidate in bundle["candidates"]:
        _share_raw_display(candidate)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, records)["ready"]
    assert apply_bundle(engine, bundle, db_registry(), inv, records)["status"] == "applied"


def test_first_pass_existing_raw_display_allows_later_canonical_player(engine):
    inv, raw_bundle, raw_records = bound_raw_player_bundle(engine)
    apply_bundle(engine, raw_bundle, db_registry(), inv, raw_records)
    player_inv, player_bundle_data, player_records = bound_player_bundle(engine)
    research = player_records[0]
    research.update(lang="en", candidate_name="Lee Wonhyuk")
    research["generation"]["method"] = "translation"
    candidate = player_bundle_data["candidates"][0]
    candidate.update(lang="en", display_name="Lee Wonhyuk", research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(
        lang="en", display_name="Lee Wonhyuk", research_sha256=candidate["research_sha256"])
    candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(candidate)
    player_bundle_data["members"] = [{"owner": candidate["owner"], "lang": "en"}]
    player_bundle_data["member_set_sha256"] = canonical_sha256(player_bundle_data["members"])
    assert dry_run_bundle(engine, player_bundle_data, db_registry(), player_inv, player_records)["ready"]


def test_first_pass_shared_display_does_not_accept_old_raw_profile(engine):
    inv, bundle, records = bound_raw_player_bundle(engine, second_raw=True)
    incoming, incoming_records = _one_raw_bundle(bundle, records, 0)
    _share_raw_display(incoming["candidates"][0])
    with Session(engine) as db:
        evidence = _evidence(db, "raw_player", 21, "en", "Lee Wonhyuk")
        db.add(KifuRawPlayerName(raw_player_id=21, lang="en", display_name="Lee Wonhyuk",
                                 status="verified", decision_kind="conventional",
                                 generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()
    with pytest.raises(BatchError, match="collision"):
        dry_run_bundle(engine, incoming, db_registry(), inv, incoming_records)


def test_first_pass_raw_player_can_share_existing_canonical_display(engine):
    inv, bundle, records = bound_raw_player_bundle(engine)
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "en", "Lee Wonhyuk")
        db.add(KifuPlayerName(player_id=17, lang="en", display_name="Lee Wonhyuk",
                              status="verified", decision_kind="conventional",
                              generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()
    _share_raw_display(bundle["candidates"][0])
    assert dry_run_bundle(engine, bundle, db_registry(), inv, records)["ready"]
    assert apply_bundle(engine, bundle, db_registry(), inv, records)["status"] == "applied"
    with Session(engine) as db:
        from katrain.web.kifu.identity import strict_matching_names
        assert strict_matching_names(db, "Lee Wonhyuk")[:3] == ({17}, set(), {"李元赫九段"})
        assert {item.id for item in _list(db, "Lee Wonhyuk", "en").items if item.id in {11, 12, 15}} == {
            11, 12, 15,
        }


def test_first_pass_shared_display_requires_exact_literal_basis(engine):
    inv, bundle, records = bound_raw_player_bundle(engine)
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "en", "Lee Wonhyuk")
        db.add(KifuPlayerName(player_id=17, lang="en", display_name="Lee Wonhyuk",
                              status="verified", decision_kind="conventional",
                              generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()
    _share_raw_display(bundle["candidates"][0])
    bundle["candidates"][0]["collision_basis"]["source_text"] = "Another raw"
    bundle["candidates"][0]["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(bundle["candidates"][0])
    with pytest.raises((BatchError, CandidateError), match="collision|shared"):
        dry_run_bundle(engine, bundle, db_registry(), inv, records)


def test_first_pass_raw_player_locks_complete_literal_occurrences(engine):
    inv, bundle, records = bound_raw_player_bundle(engine)
    apply_bundle(engine, bundle, db_registry(), inv, records)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.insert().values(
            id=16, player_black="李元赫九段", player_white="Other", event="Cup",
            sgf_content="(;PB[李元赫九段])", source_path="raw-16.sgf"))
    with engine.connect() as conn:
        with pytest.raises(BatchError, match="occurrences changed"):
            _check_first_pass_sources(conn, bundle["candidates"],
                                      {canonical_sha256(records[0]): records[0]}, bundle["owners"])


def test_first_pass_apply_read_and_retry_require_persisted_proof(engine):
    inv, bundle, research = bound_player_bundle(engine)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, research)["ready"]
    result = apply_bundle(engine, bundle, db_registry(), inv, research)
    assert result["status"] == "applied"
    with engine.connect() as conn:
        name = conn.execute(KifuPlayerName.__table__.select()).mappings().one()
        evidence = conn.execute(KifuNameResearchEvidence.__table__.select()).mappings().one()
        assert evidence["research_payload"]["first_pass"]["verification_level"] == "generated_first_pass"
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {17}, "cn")
        assert len(_qualified_name_rows(db, query, KifuPlayerName, "player_id")) == 1
    assert apply_bundle(engine, bundle, db_registry(), inv, research)["status"] == "already_applied"
    with engine.begin() as conn:
        changed = deepcopy(evidence["research_payload"])
        changed.pop("first_pass")
        conn.execute(KifuNameResearchEvidence.__table__.update().values(research_payload=changed))
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {17}, "cn")
        assert _qualified_name_rows(db, query, KifuPlayerName, "player_id") == []
    with pytest.raises(BatchError):
        apply_bundle(engine, bundle, db_registry(), inv, research)
    with engine.begin() as conn:
        changed["research"].pop("source_basis")
        changed["research"].pop("scope_status")
        changed["research"].pop("verification_level")
        changed["candidate"]["generation_rule_version"] = "other-rule"
        conn.execute(KifuNameResearchEvidence.__table__.update().values(
            generation_rule_version="other-rule", research_payload=changed))
        conn.execute(KifuPlayerName.__table__.update().values(generation_rule_version="other-rule"))
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {17}, "cn")
        assert _qualified_name_rows(db, query, KifuPlayerName, "player_id") == []


def test_first_pass_canonical_owner_cas_catches_pages_drift(engine):
    inv, bundle, research = bound_player_bundle(engine)
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 17).values(
            authoritative_pages=[{"url": "https://example.org/new"}]))
    with pytest.raises(BatchError, match="owner catalog preimage differs|source owner changed"):
        dry_run_bundle(engine, bundle, db_registry(), inv, research)


def test_first_pass_event_series_is_qualified_for_read(engine):
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=4, canonical_name="Oteai"))
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(event_id=4))
    inv, bundle, records = bound_player_bundle(engine)
    owner = {"kind": "event", "id": 4}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuEvent.__table__, 4)
    research = records[0]
    research.update(owner=owner, lang="en", original_name="Oteai", candidate_name="Oteai")
    research["source_input"] = {"kind": "catalog_canonical", "owner": owner, "text": "Oteai",
                                "owner_preimage_sha256": canonical_sha256(owner_image)}
    candidate = bundle["candidates"][0]
    candidate.update(owner=owner, lang="en", display_name="Oteai", research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(owner=owner, lang="en", display_name="Oteai",
                                          research_sha256=candidate["research_sha256"])
    candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(candidate)
    member = {"owner": owner, "lang": "en"}
    declaration = {"owner": owner, "preimage": owner_image}
    bundle.update(members=[member], member_set_sha256=canonical_sha256([member]),
                  owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                  catalog_sha256=catalog_snapshot_sha(engine))
    assert dry_run_bundle(engine, bundle, db_registry(), inv, [research])["ready"]
    apply_bundle(engine, bundle, db_registry(), inv, [research])
    with Session(engine) as db:
        query = _approved_names(db, KifuEventName, "event_id", {4}, "en")
        assert [row.display_name for row, _ in _qualified_name_rows(db, query, KifuEventName, "event_id")] == ["Oteai"]


def test_first_pass_can_fill_existing_unlinked_catalog_player(engine):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=99, canonical_name="Unused"))
    inv, bundle, records = bound_player_bundle(engine)
    owner = {"kind": "player", "id": 99}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuPlayer.__table__, 99)
    research = records[0]
    research.update(owner=owner, original_name="Unused", candidate_name="闲置")
    research["source_input"] = {"kind": "catalog_canonical", "owner": owner, "text": "Unused",
                                "owner_preimage_sha256": canonical_sha256(owner_image)}
    research["generation"]["method"] = "translation"
    candidate = bundle["candidates"][0]
    candidate.update(owner=owner, display_name="闲置", research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(owner=owner, display_name="闲置",
                                          research_sha256=candidate["research_sha256"])
    member = {"owner": owner, "lang": "cn"}
    declaration = {"owner": owner, "preimage": owner_image}
    bundle.update(members=[member], member_set_sha256=canonical_sha256([member]),
                  owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                  catalog_sha256=catalog_snapshot_sha(engine))
    assert dry_run_bundle(engine, bundle, db_registry(), inv, [research])["ready"]
    apply_bundle(engine, bundle, db_registry(), inv, [research])
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {99}, "cn")
        assert [row.display_name for row, _ in _qualified_name_rows(db, query, KifuPlayerName, "player_id")] == ["闲置"]


def test_first_pass_raw_title_stays_on_exact_public_direct_slot(engine):
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            source="https://19x19.com", source_path="data/kifu-album/19x19/one.sgf",
            date_played="1934-10-01", board_size=19,
            sgf_content="(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Other]GC[Other | 1手])"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Black", player_white="White", event="Other",
            sgf_content="(;FF[4]EV[Other])", source_path="other.sgf"))
    apply_reviewed_selection(engine, 11)
    inv = build_inventory(engine, inventory_format=4)
    owner = {"kind": "raw_event", "id": 8}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuRawEventValue.__table__, 8)
        slots = raw_scope_rows(conn, "Other")
    research = {
        "owner": owner, "lang": "en", "registry_version": "test-1",
        "registry_sha256": registry_sha256(db_registry()),
        "source_basis": "user_authorized_first_pass_v1",
        "scope_status": "generated_first_pass", "verification_level": "generated_first_pass",
        "original_name": "Other", "original_language": "und",
        "source_input": {"kind": "raw_event_literal", "owner": owner, "text": "Other",
                         "owner_preimage_sha256": canonical_sha256(owner_image)},
        "raw_scope": {"raw_value": "Other", "slots": slots},
        "generation": {"method": "translation"}, "candidate_name": "Another event",
        "producer_id": "translator", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    member = {"owner": owner, "lang": "en", "raw_value": "Other"}
    candidate = bind_fixture_candidate({
        **member, "display_name": "Another event", "decision_kind": "generated",
        "research_sha256": canonical_sha256(research),
        "generation_rule_version": "user_authorized_first_pass_v1", "name_preimage_sha256": None,
        "producer_id": "translator", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-11T01:00:00Z", "review_status": "approved",
        "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
        "reviewed_at": "2026-10-11T01:01:00Z",
        "review_conclusion": "approved_first_pass_display_and_source",
        "generated_review": {"decision": "approve_generated_first_pass", "owner": owner,
                             "lang": "en", "display_name": "Another event",
                             "research_sha256": canonical_sha256(research),
                             "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
                             "reviewed_at": "2026-10-11T01:01:00Z"},
    })
    candidate["preimage_binding"]["captured_at"] = "2026-10-11T01:00:15Z"
    candidate["preimage_binding"]["bound_at"] = "2026-10-11T01:00:30Z"
    declaration = {"owner": owner, "preimage": owner_image, "occurrence_album_ids": [11, 12],
                   "occurrence_sha256": canonical_sha256([11, 12])}
    bundle = {"bundle_format": 2, "inventory_format": inv["inventory_format"],
              "inventory_sha256": inv["sha256"], "registry_version": "test-1",
              "registry_sha256": registry_sha256(db_registry()), "rule_version": "first-pass-v1",
              "catalog_sha256": catalog_snapshot_sha(engine), "members": [member],
              "member_set_sha256": canonical_sha256([member]), "candidates": [candidate],
              "owners": [declaration], "owner_set_sha256": canonical_sha256([declaration]),
              "album_links": [], "link_set_sha256": canonical_sha256([])}
    assert dry_run_bundle(engine, bundle, db_registry(), inv, [research])["ready"]
    apply_bundle(engine, bundle, db_registry(), inv, [research])
    with Session(engine) as db:
        rows = _approved_raw_event_names(db, values={"Other"}, lang="en")
        assert len(rows) == 1
        albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_([11, 12])).all()
        selected = live_event_selections(db, albums, album_ids={11})
        assert _raw_event_map(rows, albums, selected) == {
            (11, "Other", None): "Another event", (12, "Other", None): "Another event"}
        assert _raw_event_map(rows, [SimpleNamespace(id=12, event="Other", event_id=None)], {}) == {
            (12, "Other", None): "Another event"}
        assert strict_display_maps(db, albums, "en", selected_events=selected)[-1] == {
            (11, "Other", None): "Another event", (12, "Other", None): "Another event"}
        assert {item.id for item in db.query(KifuAlbum).filter(strict_raw_event_search_clause(db, {rows[0][0].id}))} == {12}
        assert strict_selected_event_search_ids(db, "Another event", {rows[0][0].id}, set()) == {11}
    coverage = coverage_report(engine, inv, languages=("en",))
    assert not any(item["slot"] == "event" and item["album_id"] in {11, 12}
                   for item in coverage["missing_examples"])
