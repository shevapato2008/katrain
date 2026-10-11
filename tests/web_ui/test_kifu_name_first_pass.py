"""The authorized first pass is generated provenance with exact inputs."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_candidate
from katrain.web.kifu.name_evidence import EvidenceError, registry_sha256, validate_research_record
from katrain.web.kifu.name_batch import BatchError, _image, apply_bundle, dry_run_bundle, catalog_snapshot_sha
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.core.models_db import (
    KifuAlbum, KifuPlayer, KifuPlayerName, KifuEvent, KifuEventName,
    KifuRawEventValue, KifuRawEventName, KifuRawPlayerValue, KifuRawPlayerName, KifuNameResearchEvidence,
    KifuNameChange,
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


def test_formal_event_own_year_and_finite_raw_collision(engine):
    from katrain.web.kifu.name_batch import _canonical_shared_permissions
    from katrain.web.kifu.name_first_pass import (
        canonical_shared_display_candidate, own_source_event_numbers_preserved,
    )

    original = "2026野狐围棋研究会春季循环赛"
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=15, canonical_name=original))
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=63269, raw_value=original, category="formal_event_candidate", review_status="approved"))
    with Session(engine) as db:
        evidence = _evidence(db, "raw_event", 63269, "cn", original)
        db.add(KifuRawEventName(raw_event_id=63269, lang="cn", display_name=original, status="verified",
                                decision_kind="conventional", generation_rule_version="test-v1",
                                revision=1, evidence_id=evidence.id))
        db.commit()
    with engine.connect() as conn:
        event_image = _image(conn, KifuEvent.__table__, 15)
        raw_image = _image(conn, KifuRawEventValue.__table__, 63269)
    owner = {"kind": "event", "id": 15}
    candidate, research = first_pass_pair()
    candidate.update(owner=owner, display_name=original)
    research.update(owner=owner, original_name=original, candidate_name=original)
    research["source_input"].update(owner=owner, text=original,
                                    owner_preimage_sha256=canonical_sha256(event_image))
    assert own_source_event_numbers_preserved(candidate, research)
    bad = dict(candidate, display_name="2027野狐围棋研究会春季循环赛")
    assert not own_source_event_numbers_preserved(bad, research)
    url = engine.url
    permission = {
        "version": "canonical-shared-display-v1", "owner_kind": "event", "environment": "TEST",
        "database_binding": f"{url.drivername}://{url.host or ''}:{url.port or ''}/{url.database or ''}",
        "normalizer": "normalize_alias-v1", "lang": "cn", "display_name": original,
        "normalized_key": original, "identity_relation": "unknown",
        "members": [{"id": 15, "source_preimage_sha256": canonical_sha256(event_image)}],
        "raw_members": [{"id": 63269, "source_preimage_sha256": canonical_sha256(raw_image)}],
    }
    candidate["collision_decision"] = "shared_display"
    candidate["collision_basis"] = {"permission_sha256": canonical_sha256(permission)}
    candidate["research_sha256"] = canonical_sha256(research)
    assert canonical_shared_display_candidate(candidate, research, permission)
    with engine.connect() as conn:
        assert _canonical_shared_permissions(conn, [candidate], [permission],
                                             {candidate["research_sha256"]: research}) == {
            ("event", "cn", original): ({15}, {63269})
        }
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=63270, raw_value="Another", category="formal_event_candidate", review_status="approved"))
    with Session(engine) as db:
        evidence = _evidence(db, "raw_event", 63270, "cn", original)
        db.add(KifuRawEventName(raw_event_id=63270, lang="cn", display_name=original, status="verified",
                                decision_kind="conventional", generation_rule_version="test-v1",
                                revision=1, evidence_id=evidence.id))
        db.commit()
    with engine.connect() as conn, pytest.raises(BatchError, match="raw-event members changed"):
        _canonical_shared_permissions(conn, [candidate], [permission],
                                      {candidate["research_sha256"]: research})


def test_first_pass_event_year_gate_requires_own_source_numbers():
    from katrain.web.kifu.name_first_pass import validate_candidate as validate_first_pass_candidate

    candidate, research = first_pass_pair()
    owner = {"kind": "event", "id": 3}
    original = "2026世界围棋团体赛热身赛1/3轮"
    display = "2026 세계 바둑 단체전 연습 경기 1/3라운드"
    research.update(owner=owner, lang="ko", original_name=original, candidate_name=display)
    research["source_input"].update(owner=owner, text=original)
    research["generation"]["method"] = "translation"
    candidate.update(owner=owner, lang="ko", display_name=display,
                     research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(owner=owner, lang="ko", display_name=display,
                                          research_sha256=candidate["research_sha256"])
    assert validate_candidate(candidate, research, registry(), inventory()) == candidate
    assert validate_first_pass_candidate(candidate, research) == candidate
    changed = deepcopy(candidate)
    changed_research = deepcopy(research)
    changed["display_name"] = changed_research["candidate_name"] = display.replace("2026", "2027")
    changed["research_sha256"] = canonical_sha256(changed_research)
    changed["generated_review"].update(display_name=changed["display_name"],
                                       research_sha256=changed["research_sha256"])
    with pytest.raises(CandidateError, match="event first-pass source numbers changed"):
        validate_candidate(changed, changed_research, registry(), inventory())
    with pytest.raises(ValueError, match="event first-pass source numbers changed"):
        validate_first_pass_candidate(changed, changed_research)
    dropped = deepcopy(candidate)
    dropped_research = deepcopy(research)
    dropped["display_name"] = dropped_research["candidate_name"] = display.replace("2026 ", "")
    dropped["research_sha256"] = canonical_sha256(dropped_research)
    dropped["generated_review"].update(display_name=dropped["display_name"],
                                       research_sha256=dropped["research_sha256"])
    with pytest.raises(CandidateError, match="event first-pass source numbers changed"):
        validate_candidate(dropped, dropped_research, registry(), inventory())
    with pytest.raises(ValueError, match="event first-pass source numbers changed"):
        validate_first_pass_candidate(dropped, dropped_research)


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


def test_first_pass_record_label_requires_exact_token_template_and_submode():
    from katrain.web.kifu.name_first_pass import record_label_display

    _candidate, research = first_pass_pair()
    owner = {"kind": "raw_event", "id": 7}
    raw = "GNUGo3.8"
    research.update(owner=owner, lang="cn", original_name=raw,
                    candidate_name=record_label_display("cn", raw))
    research["source_input"] = {"kind": "raw_event_literal", "owner": owner, "text": raw,
                                "owner_preimage_sha256": "a" * 64,
                                "record_label_basis": "program_token"}
    research["generation"] = {"method": "translation", "submode": "literal_record_label"}
    research["raw_scope"] = {"raw_value": raw, "slots": [
        {"album_id": 1, "slot": "event", "raw_value": raw, "event_id": None, "approved": True}]}
    assert validate_research_record(research, registry())["candidate_name"] == "棋谱标记：GNUGo3.8"
    sgf = deepcopy(research)
    sgf["original_name"] = sgf["source_input"]["text"] = "004sgf"
    sgf["source_input"]["record_label_basis"] = "sgf_token"
    sgf["raw_scope"]["raw_value"] = sgf["raw_scope"]["slots"][0]["raw_value"] = "004sgf"
    sgf["candidate_name"] = record_label_display("cn", "004sgf")
    assert validate_research_record(sgf, registry())["candidate_name"] == "棋谱标记：004sgf"
    for change in (lambda r: r["generation"].pop("submode"),
                   lambda r: r["source_input"].update(record_label_basis="sgf_token"),
                   lambda r: r.update(candidate_name="围棋比赛")):
        bad = deepcopy(research)
        change(bad)
        with pytest.raises(EvidenceError):
            validate_research_record(bad, registry())
    for unreadable in ("2010??????", "(;EV[broken]", ""):
        bad = deepcopy(research)
        bad["original_name"] = bad["source_input"]["text"] = unreadable
        bad["raw_scope"]["raw_value"] = bad["raw_scope"]["slots"][0]["raw_value"] = unreadable
        bad["candidate_name"] = record_label_display("cn", unreadable)
        with pytest.raises(EvidenceError):
            validate_research_record(bad, registry())


def test_first_pass_shared_raw_title_requires_literal_basis_and_number():
    from katrain.web.kifu.name_first_pass import shared_event_display_candidate

    row, research = first_pass_pair()
    owner = {"kind": "raw_event", "id": 8}
    raw = "28th Honinbo"
    research.update(owner=owner, lang="en", original_name=raw, candidate_name="28th Honinbo Tournament")
    research["source_input"] = {"kind": "raw_event_literal", "owner": owner, "text": raw,
                                "owner_preimage_sha256": "a" * 64}
    research["generation"]["method"] = "translation"
    research["raw_scope"] = {"raw_value": raw, "slots": [
        {"album_id": 1, "slot": "event", "raw_value": raw, "event_id": None, "approved": True}]}
    row.update(owner=owner, lang="en", raw_value=raw, display_name="28th Honinbo Tournament",
               research_sha256=canonical_sha256(research), collision_decision="shared_display",
               collision_basis={"kind": "literal_title_translation", "source_text": raw,
                                "provenance": "signed_raw_event_literal"})
    row["generated_review"].update(owner=owner, lang="en", display_name=row["display_name"],
                                   research_sha256=row["research_sha256"])
    assert shared_event_display_candidate(row, research)
    bad = deepcopy(row)
    bad["display_name"] = "Honinbo Tournament"
    assert not shared_event_display_candidate(bad, research)
    bad["display_name"] = research["candidate_name"] = "128th Honinbo Tournament"
    assert not shared_event_display_candidate(bad, research)
    research["candidate_name"] = row["display_name"]
    research["source_input"]["text"] = research["original_name"] = "28th Honinbo Round 28"
    research["raw_scope"]["raw_value"] = "28th Honinbo Round 28"
    row["raw_value"] = "28th Honinbo Round 28"
    row["collision_basis"]["source_text"] = "28th Honinbo Round 28"
    assert not shared_event_display_candidate(row, research)
    bad = deepcopy(row)
    bad["collision_basis"]["source_text"] = "Other"
    assert not shared_event_display_candidate(bad, research)


def test_first_pass_record_label_rejects_mismatched_live_category(engine):
    raw = "004sgf"
    owner = {"kind": "raw_event", "id": 20}
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=20, raw_value=raw, category="formal_event_candidate", review_status="pending"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Black", player_white="White", event=raw,
            sgf_content=f"(;EV[{raw}])", source_path="record-label.sgf"))
    with engine.connect() as conn:
        image = _image(conn, KifuRawEventValue.__table__, 20)
        scope = raw_scope_rows(conn, raw)
    research = {
        "owner": owner, "lang": "en", "source_basis": "user_authorized_first_pass_v1",
        "scope_status": "generated_first_pass", "verification_level": "generated_first_pass",
        "original_name": raw, "original_language": "und", "source_input": {
            "kind": "raw_event_literal", "owner": owner, "text": raw,
            "owner_preimage_sha256": canonical_sha256(image), "record_label_basis": "sgf_token"},
        "raw_scope": {"raw_value": raw, "slots": scope},
        "generation": {"method": "translation", "submode": "literal_record_label"},
        "candidate_name": "Record label: 004sgf",
    }
    candidate = {"owner": owner, "lang": "en", "decision_kind": "generated",
                 "generation_rule_version": "user_authorized_first_pass_v1",
                 "research_sha256": canonical_sha256(research)}
    with engine.connect() as conn, pytest.raises(BatchError, match="classified|record label"):
        _check_first_pass_sources(conn, [candidate], {candidate["research_sha256"]: research}, [])


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


def test_existing_qualified_literal_raw_event_can_share_generated_display(engine):
    from katrain.web.kifu.name_batch import _check_cross_bundle_collisions
    from tests.web_ui.test_kifu_raw_event_title_translation import registry as raw_title_registry, sgf_reviewed_bundle

    bundle, inv, records = sgf_reviewed_bundle(engine)
    apply_bundle(engine, bundle, raw_title_registry(), inv, records)
    display = bundle["candidates"][0]["display_name"]
    with Session(engine) as db:
        existing = db.query(KifuRawEventName).filter_by(raw_event_id=8, lang="en").one()
        rows = _approved_raw_event_names(db, name_ids={existing.id})
        assert len(rows) == 1 and rows[0][0].id == existing.id and rows[0][2] is None
        assert existing.decision_kind == "translated"
        assert existing.generation_rule_version == "raw-event-title-translation-v1"
        evidence_id = existing.evidence_id

    raw = "2020另一赛事第1轮"
    incoming = {"owner": {"kind": "raw_event", "id": 99}, "lang": "en",
                "display_name": display, "decision_kind": "generated",
                "generation_rule_version": "user_authorized_first_pass_v1",
                "review_status": "approved", "raw_value": raw,
                "collision_decision": "shared_display",
                "collision_basis": {"kind": "literal_title_translation", "source_text": raw,
                                    "provenance": "signed_raw_event_literal"},
                "research_sha256": "a" * 64}
    research = {"source_input": {"kind": "raw_event_literal", "text": raw},
                "raw_scope": {"raw_value": raw, "slots": [{"album_id": 99}]},
                "candidate_name": display, "generation": {"method": "translation"}}
    research_by_hash = {incoming["research_sha256"]: research}
    with engine.connect() as conn:
        _check_cross_bundle_collisions(conn, [incoming], research_by_hash=research_by_hash)
        with pytest.raises(BatchError, match="first-pass normalized name collision"):
            _check_cross_bundle_collisions(conn, [{**incoming, "collision_decision": "reject"}],
                                           research_by_hash=research_by_hash)

    with Session(engine) as db:
        db.get(KifuNameResearchEvidence, evidence_id).review_status = "rejected"
        db.commit()
    with engine.connect() as conn, pytest.raises(BatchError, match="first-pass normalized name collision"):
        _check_cross_bundle_collisions(conn, [incoming], research_by_hash=research_by_hash)


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


def test_bounded_first_pass_correction_requires_exact_generated_journal(engine, monkeypatch):
    from katrain.web.kifu import name_batch

    inv, bundle, records = bound_raw_player_bundle(engine)
    applied = apply_bundle(engine, bundle, db_registry(), inv, records)
    old = bundle["candidates"][0]
    owner = old["owner"]
    with engine.connect() as conn:
        name = conn.execute(KifuRawPlayerName.__table__.select().where(
            KifuRawPlayerName.raw_player_id == owner["id"], KifuRawPlayerName.lang == "en"
        )).mappings().one()
        name_image = _image(conn, KifuRawPlayerName.__table__, name["id"])
        evidence_image = _image(conn, KifuNameResearchEvidence.__table__, name["evidence_id"])
    source_url = "https://example.org/player/20"
    monkeypatch.setitem(name_batch._FIRST_PASS_CORRECTION_CELLS, (20, "en"),
                        ("李元赫九段", "Lee Wonhyuk", "Lee Won-hyuk", source_url))
    candidate = deepcopy(old)
    candidate["display_name"] = "Lee Won-hyuk"
    candidate["produced_at"] = "2026-10-11T01:00:40Z"
    candidate["name_preimage_sha256"] = canonical_sha256(name_image)
    candidate["first_pass_correction"] = {
        "version": "bounded-first-pass-correction-712-v1",
        "prior_batch_id": applied["batch_id"], "prior_name_revision": name["revision"],
        "prior_candidate_sha256": canonical_sha256(old),
        "prior_evidence_sha256": canonical_sha256(evidence_image),
        "source_check": {
            "owner": owner, "source_id": "go", "query": "Lee Won-hyuk", "status": "found",
            "url": source_url, "fetched_at": "2026-10-11T01:00:30Z", "http_status": 200,
            "body_sha256": "a" * 64, "body_excerpt": "Lee Won-hyuk",
            "language_basis": "html_lang", "observed_lang": "en",
            "candidate_name": "Lee Won-hyuk",
            "identity_basis": "Exact fixture raw owner: https://example.org/official/20",
        },
    }
    monkeypatch.setitem(name_batch._FIRST_PASS_CORRECTION_IDENTITY_URLS, 20,
                        "https://example.org/official/20")
    with engine.connect() as conn:
        _check_name_preimages(conn, [candidate], db_registry())
        stale = deepcopy(candidate)
        stale["name_preimage_sha256"] = "b" * 64
        with pytest.raises(BatchError, match="name preimage changed"):
            _check_name_preimages(conn, [stale], db_registry())
        outside = deepcopy(candidate)
        outside["owner"] = {"kind": "raw_player", "id": 21}
        with pytest.raises(BatchError, match="outside the reviewed 712 scope"):
            name_batch._check_first_pass_correction(conn, outside, db_registry())
        unknown = deepcopy(candidate)
        unknown["first_pass_correction"]["prior_evidence_sha256"] = "b" * 64
        with pytest.raises(BatchError, match="old evidence or provenance differs"):
            _check_name_preimages(conn, [unknown], db_registry())
    with engine.begin() as conn:
        payload = deepcopy(evidence_image["research_payload"])
        payload.pop("first_pass")
        conn.execute(KifuNameResearchEvidence.__table__.update().where(
            KifuNameResearchEvidence.id == name["evidence_id"]
        ).values(research_payload=payload))
    with engine.connect() as conn:
        authority = deepcopy(candidate)
        authority["first_pass_correction"]["prior_evidence_sha256"] = canonical_sha256(
            _image(conn, KifuNameResearchEvidence.__table__, name["evidence_id"]))
        with pytest.raises(BatchError, match="old evidence or provenance differs"):
            _check_name_preimages(conn, [authority], db_registry())
    with engine.begin() as conn:
        conn.execute(KifuNameResearchEvidence.__table__.update().where(
            KifuNameResearchEvidence.id == name["evidence_id"]
        ).values(research_payload=evidence_image["research_payload"]))

    research = deepcopy(records[0])
    research["candidate_name"] = candidate["display_name"]
    research["produced_at"] = "2026-10-11T01:00:40Z"
    candidate["research_sha256"] = canonical_sha256(research)
    candidate["produced_at"] = research["produced_at"]
    candidate["generated_review"].update(display_name=candidate["display_name"],
                                         research_sha256=candidate["research_sha256"])
    candidate["preimage_binding"].update(name_preimage_sha256=candidate["name_preimage_sha256"],
                                         captured_at="2026-10-11T01:00:41Z",
                                         bound_at="2026-10-11T01:00:45Z")
    corrected = deepcopy(bundle)
    corrected["candidates"] = [candidate]
    assert dry_run_bundle(engine, corrected, db_registry(), inv, [research])["ready"]
    assert apply_bundle(engine, corrected, db_registry(), inv, [research])["status"] == "applied"
    with Session(engine) as db:
        from katrain.web.kifu.identity import _approved_raw_player_names
        rows = _approved_raw_player_names(db, values={"李元赫九段"}, lang="en")
        assert len(rows) == 1 and rows[0][0].display_name == "Lee Won-hyuk"


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


def test_first_pass_reader_loads_only_relevant_batch_journal_rows(engine):
    inv, bundle, research = bound_player_bundle(engine)
    result = apply_bundle(engine, bundle, db_registry(), inv, research)
    with engine.begin() as conn:
        name = conn.execute(KifuPlayerName.__table__.select()).mappings().one()
        evidence = conn.execute(KifuNameResearchEvidence.__table__.select()).mappings().one()
        conn.execute(KifuNameChange.__table__.insert().values(
            batch_id=result["batch_id"], sequence=999999, target_table="kifu_raw_event_names",
            target_row_id=999999, before_image=None, after_image={"unrelated": True},
        ))

    loaded = set()

    def observe_change(change, _context):
        loaded.add((change.target_table, change.target_row_id))

    event.listen(KifuNameChange, "load", observe_change)
    try:
        with Session(engine) as db:
            query = _approved_names(db, KifuPlayerName, "player_id", {17}, "cn")
            assert len(_qualified_name_rows(db, query, KifuPlayerName, "player_id")) == 1
    finally:
        event.remove(KifuNameChange, "load", observe_change)
    assert ("kifu_name_research_evidence", evidence["id"]) in loaded
    assert ("kifu_player_names", name["id"]) in loaded
    assert ("kifu_raw_event_names", 999999) not in loaded

    with engine.begin() as conn:
        conn.execute(KifuNameChange.__table__.update().where(
            KifuNameChange.batch_id == result["batch_id"],
            KifuNameChange.target_table == "kifu_player_names",
            KifuNameChange.target_row_id == name["id"],
        ).values(after_image={"corrupt": True}))
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


def test_canonical_shared_display_is_finite_and_searches_each_id_once(engine, monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert(), [
            {"id": 18, "canonical_name": "吴清源"},
            {"id": 19, "canonical_name": "Other"},
        ])
        conn.execute(KifuAlbum.__table__.insert(), [
            {"id": 12, "black_player_id": 18, "player_black": "Other", "player_white": "Other",
             "event": "Cup", "sgf_content": "(;B[aa])", "source_path": "two.sgf"},
            {"id": 13, "black_player_id": 17, "white_player_id": 18, "player_black": "Other",
             "player_white": "Other", "event": "Cup", "sgf_content": "(;B[bb])", "source_path": "both.sgf"},
            {"id": 14, "black_player_id": 19, "player_black": "Other", "player_white": "Other",
             "event": "Cup", "sgf_content": "(;B[cc])", "source_path": "outside.sgf"},
        ])
    inv, bundle, records = bound_player_bundle(engine)
    with engine.connect() as conn:
        second_image = _image(conn, KifuPlayer.__table__, 18)
    first_image = bundle["owners"][0]["preimage"]
    url = engine.url
    permission = {
        "version": "canonical-shared-display-v1", "environment": "TEST",
        "database_binding": f"{url.drivername}://{url.host or ''}:{url.port or ''}/{url.database or ''}",
        "normalizer": "normalize_alias-v1", "lang": "cn", "display_name": "吴清源",
        "normalized_key": "吴清源", "identity_relation": "unknown",
        "members": [
            {"id": 17, "source_preimage_sha256": canonical_sha256(first_image)},
            {"id": 18, "source_preimage_sha256": canonical_sha256(second_image)},
        ],
    }
    second_research = deepcopy(records[0])
    second_research["owner"] = {"kind": "player", "id": 18}
    second_research["source_input"].update(
        owner=second_research["owner"], owner_preimage_sha256=canonical_sha256(second_image))
    second_candidate = deepcopy(bundle["candidates"][0])
    second_candidate["owner"] = second_research["owner"]
    second_candidate["research_sha256"] = canonical_sha256(second_research)
    second_candidate["generated_review"].update(
        owner=second_research["owner"], research_sha256=second_candidate["research_sha256"])
    for candidate in (bundle["candidates"][0], second_candidate):
        candidate["collision_decision"] = "shared_display"
        candidate["collision_basis"] = {"permission_sha256": canonical_sha256(permission)}
        candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(candidate)
    members = [{"owner": candidate["owner"], "lang": "cn"}
               for candidate in (bundle["candidates"][0], second_candidate)]
    owners = [bundle["owners"][0], {"owner": second_candidate["owner"], "preimage": second_image}]
    bundle.update(members=members, member_set_sha256=canonical_sha256(members),
                  candidates=[bundle["candidates"][0], second_candidate],
                  owners=owners, owner_set_sha256=canonical_sha256(owners),
                  shared_displays=[permission])
    records.append(second_research)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, records)["ready"]
    assert apply_bundle(engine, bundle, db_registry(), inv, records)["status"] == "applied"
    with Session(engine) as db:
        other_locale = _evidence(db, "player", 17, "jp", "吴清源")
        db.add(KifuPlayerName(player_id=17, lang="jp", display_name="吴清源", status="verified",
                               decision_kind="conventional", generation_rule_version="test-v1",
                               revision=1, evidence_id=other_locale.id))
        db.commit()
    with Session(engine) as db:
        from katrain.web.kifu.identity import strict_matching_names
        assert strict_matching_names(db, "吴清源")[0] == {17, 18}
        response = _list(db, "吴清源")
        assert {item.id for item in response.items} == {11, 12, 13}
        assert response.total == 3
        monkeypatch.setenv("KIFU_STRICT_NAMES", "0")
        assert {item.id for item in _list(db, "吴清源").items} == {11, 12, 13}
        monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        db.add(KifuEvent(id=31, canonical_name="吴清源"))
        event_evidence = _evidence(db, "event", 31, "cn", "吴清源")
        db.add(KifuEventName(event_id=31, lang="cn", display_name="吴清源", status="verified",
                             decision_kind="conventional", generation_rule_version="test-v1",
                             revision=1, evidence_id=event_evidence.id))
        db.flush()
        from katrain.web.kifu.identity import strict_matching_names
        assert strict_matching_names(db, "吴清源") == (set(), set(), set(), set())
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 18).values(canonical_name="Changed"))
    with Session(engine) as db:
        from katrain.web.kifu.identity import strict_matching_names
        assert strict_matching_names(db, "吴清源")[0] == {17}
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 18).values(canonical_name="吴清源"))
    with Session(engine) as db:
        evidence = _evidence(db, "player", 19, "cn", "吴清源")
        db.add(KifuPlayerName(player_id=19, lang="cn", display_name="吴清源", status="verified",
                               decision_kind="conventional", generation_rule_version="test-v1",
                               revision=1, evidence_id=evidence.id))
        db.commit()
        from katrain.web.kifu.identity import strict_matching_names
        assert strict_matching_names(db, "吴清源")[0] == set()


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


def bound_shared_raw_event_bundle(engine):
    from katrain.web.kifu.name_parse import parse_event

    raws = ("28th Honinbo", "第28期本因坊战")
    with engine.begin() as conn:
        for index, raw in enumerate(raws):
            conn.execute(KifuRawEventValue.__table__.insert().values(
                id=20 + index, raw_value=raw, category=parse_event(raw, None).category,
                review_status="pending"))
            conn.execute(KifuAlbum.__table__.insert().values(
                id=12 + index, player_black="Black", player_white="White", event=raw,
                sgf_content=f"(;EV[{raw}])", source_path=f"raw-event-{index}.sgf"))
    inv = build_inventory(engine)
    candidates, records, members, declarations = [], [], [], []
    for index, raw in enumerate(raws):
        owner = {"kind": "raw_event", "id": 20 + index}
        with engine.connect() as conn:
            owner_image = _image(conn, KifuRawEventValue.__table__, owner["id"])
            slots = raw_scope_rows(conn, raw)
        research = {
            "owner": owner, "lang": "en", "registry_version": "test-1",
            "registry_sha256": registry_sha256(db_registry()),
            "source_basis": "user_authorized_first_pass_v1", "scope_status": "generated_first_pass",
            "verification_level": "generated_first_pass", "original_name": raw,
            "original_language": "und", "source_input": {
                "kind": "raw_event_literal", "owner": owner, "text": raw,
                "owner_preimage_sha256": canonical_sha256(owner_image)},
            "raw_scope": {"raw_value": raw, "slots": slots},
            "generation": {"method": "translation"}, "candidate_name": "28th Honinbo Tournament",
            "producer_id": "translator", "producer_model": "gpt-6-luna", "review_status": "pending",
        }
        member = {"owner": owner, "lang": "en", "raw_value": raw}
        candidate = bind_fixture_candidate({
            **member, "display_name": research["candidate_name"], "decision_kind": "generated",
            "research_sha256": canonical_sha256(research),
            "generation_rule_version": "user_authorized_first_pass_v1", "name_preimage_sha256": None,
            "collision_decision": "shared_display",
            "collision_basis": {"kind": "literal_title_translation", "source_text": raw,
                                "provenance": "signed_raw_event_literal"},
            "producer_id": "translator", "producer_model": "gpt-6-luna",
            "produced_at": "2026-10-11T01:00:00Z", "review_status": "approved",
            "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
            "reviewed_at": "2026-10-11T01:01:00Z",
            "review_conclusion": "approved_first_pass_display_and_source",
            "generated_review": {"decision": "approve_generated_first_pass", "owner": owner,
                                 "lang": "en", "display_name": research["candidate_name"],
                                 "research_sha256": canonical_sha256(research),
                                 "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
                                 "reviewed_at": "2026-10-11T01:01:00Z"},
        })
        candidate["preimage_binding"].update(captured_at="2026-10-11T01:00:15Z",
                                               bound_at="2026-10-11T01:00:30Z")
        candidates.append(candidate)
        records.append(research)
        members.append(member)
        declarations.append({"owner": owner, "preimage": owner_image,
                             "occurrence_album_ids": [12 + index],
                             "occurrence_sha256": canonical_sha256([12 + index])})
    bundle = {"bundle_format": 2, "inventory_format": inv["inventory_format"],
              "inventory_sha256": inv["sha256"], "registry_version": "test-1",
              "registry_sha256": registry_sha256(db_registry()), "rule_version": "first-pass-v1",
              "catalog_sha256": catalog_snapshot_sha(engine), "members": members,
              "member_set_sha256": canonical_sha256(members), "candidates": candidates,
              "owners": declarations, "owner_set_sha256": canonical_sha256(declarations),
              "album_links": [], "link_set_sha256": canonical_sha256([])}
    return inv, bundle, records


def _one_shared_raw_event_bundle(bundle, records, index):
    one = deepcopy(bundle)
    one["members"] = [bundle["members"][index]]
    one["member_set_sha256"] = canonical_sha256(one["members"])
    one["candidates"] = [bundle["candidates"][index]]
    one["owners"] = [bundle["owners"][index]]
    one["owner_set_sha256"] = canonical_sha256(one["owners"])
    return one, [records[index]]


def _corrected_raw_event_bundle(engine, prior_bundle, prior_research, prior_batch_id, display):
    from katrain.web.core.models_db import KifuNameBatch

    old = prior_bundle["candidates"][0]
    owner = old["owner"]
    with engine.connect() as conn:
        name_row = conn.execute(KifuRawEventName.__table__.select().where(
            KifuRawEventName.raw_event_id == owner["id"], KifuRawEventName.lang == old["lang"]
        )).mappings().one()
        name = _image(conn, KifuRawEventName.__table__, name_row["id"])
        evidence = _image(conn, KifuNameResearchEvidence.__table__, name["evidence_id"])
        batch = _image(conn, KifuNameBatch.__table__, prior_batch_id)
    marker = {
        "version": "generated-raw-event-semantic-correction-v1",
        "owner": owner, "lang": old["lang"], "raw_value": old["raw_value"],
        "name_preimage_sha256": canonical_sha256(name),
        "prior_name_revision": name["revision"],
        "prior_candidate_sha256": canonical_sha256(old),
        "prior_evidence_sha256": canonical_sha256(evidence),
        "prior_batch_id": prior_batch_id, "prior_bundle_sha256": batch["bundle_sha256"],
    }
    research = deepcopy(prior_research)
    research["candidate_name"] = display
    candidate = deepcopy(old)
    candidate.update(display_name=display, name_preimage_sha256=marker["name_preimage_sha256"],
                     research_sha256=canonical_sha256(research), first_pass_correction=marker)
    candidate["generated_review"].update(display_name=display,
                                         research_sha256=candidate["research_sha256"])
    candidate["preimage_binding"].update(name_preimage_sha256=marker["name_preimage_sha256"])
    corrected = deepcopy(prior_bundle)
    corrected["candidates"] = [candidate]
    return corrected, research


def test_generated_raw_event_prior_proof_reused_per_transaction_with_live_cas(engine, monkeypatch):
    from katrain.web.core.models_db import KifuNameBatch
    from katrain.web.kifu import name_batch

    inv, prior, records = bound_shared_raw_event_bundle(engine)
    records[1]["candidate_name"] = "28th Honinbo Tournament Chinese record"
    prior["candidates"][1]["display_name"] = records[1]["candidate_name"]
    prior["candidates"][1]["research_sha256"] = canonical_sha256(records[1])
    prior["candidates"][1]["generated_review"].update(
        display_name=records[1]["candidate_name"],
        research_sha256=prior["candidates"][1]["research_sha256"],
    )
    applied = apply_bundle(engine, prior, db_registry(), inv, records)
    corrections, corrected_records = [], []
    for index, display in enumerate(("28th Honinbo Championship", "28th Honinbo Championship Chinese record")):
        one, one_records = _one_shared_raw_event_bundle(prior, records, index)
        corrected, research = _corrected_raw_event_bundle(
            engine, one, one_records[0], applied["batch_id"], display)
        corrections.append(corrected["candidates"][0])
        corrected_records.append(research)
    corrected_bundle = deepcopy(prior)
    corrected_bundle["candidates"] = corrections

    original_image = name_batch._image
    original_sha = name_batch.canonical_sha256
    batch_reads = 0
    prior_bundle_hashes = 0

    def counted_image(conn, table, row_id):
        nonlocal batch_reads
        if table.name == KifuNameBatch.__tablename__ and row_id == applied["batch_id"]:
            batch_reads += 1
        return original_image(conn, table, row_id)

    def counted_sha(value):
        nonlocal prior_bundle_hashes
        if value == prior:
            prior_bundle_hashes += 1
        return original_sha(value)

    monkeypatch.setattr(name_batch, "_image", counted_image)
    monkeypatch.setattr(name_batch, "canonical_sha256", counted_sha)
    assert dry_run_bundle(engine, corrected_bundle, db_registry(), inv, corrected_records)["ready"]
    assert (batch_reads, prior_bundle_hashes) == (1, 1)
    assert dry_run_bundle(engine, corrected_bundle, db_registry(), inv, corrected_records)["ready"]
    assert (batch_reads, prior_bundle_hashes) == (2, 2)  # A new transaction reloads the prior proof.

    with engine.connect() as conn:
        name_row = conn.execute(KifuRawEventName.__table__.select().where(
            KifuRawEventName.raw_event_id == corrections[0]["owner"]["id"],
            KifuRawEventName.lang == corrections[0]["lang"],
        )).mappings().one()
        forged = deepcopy(corrections[0])
        forged["name_preimage_sha256"] = "b" * 64
        with pytest.raises(BatchError, match="name preimage changed"):
            _check_name_preimages(conn, [forged], db_registry())
        conn.execute(KifuNameResearchEvidence.__table__.update().where(
            KifuNameResearchEvidence.id == name_row["evidence_id"]).values(review_status="pending"))
        with pytest.raises(BatchError, match="old evidence or status differs"):
            _check_name_preimages(conn, [corrections[0]], db_registry())
        conn.execute(KifuRawEventName.__table__.update().where(
            KifuRawEventName.id == name_row["id"]).values(display_name="tampered title"))
        with pytest.raises(BatchError, match="name preimage changed"):
            _check_name_preimages(conn, [corrections[0]], db_registry())

    result = apply_bundle(engine, corrected_bundle, db_registry(), inv, corrected_records)
    assert result["status"] == "applied"
    assert (batch_reads, prior_bundle_hashes) == (3, 3)  # Apply reuses proof in its write loop.


def test_generated_raw_event_semantic_correction_twice_keeps_reader_and_journal(engine):
    from katrain.web.kifu import name_batch

    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    first, first_records = _one_shared_raw_event_bundle(bundle, records, 0)
    first_result = apply_bundle(engine, first, db_registry(), inv, first_records)
    prior_bundle, prior_research, prior_batch_id = first, first_records[0], first_result["batch_id"]
    old_corrections = []
    for display in ("28th Honinbo Championship", "28th Honinbo Championship Finals"):
        corrected, research = _corrected_raw_event_bundle(
            engine, prior_bundle, prior_research, prior_batch_id, display)
        assert dry_run_bundle(engine, corrected, db_registry(), inv, [research])["ready"]
        result = apply_bundle(engine, corrected, db_registry(), inv, [research])
        with engine.connect() as conn:
            changes = conn.execute(KifuNameChange.__table__.select().where(
                KifuNameChange.batch_id == result["batch_id"])).mappings().all()
            name_change = next(change for change in changes if change["target_table"] == "kifu_raw_event_names")
            evidence_change = next(change for change in changes
                                   if change["target_table"] == "kifu_name_research_evidence")
            assert name_change["before_image"]["display_name"] == prior_bundle["candidates"][0]["display_name"]
            assert name_change["after_image"]["display_name"] == display
            assert evidence_change["before_image"] is None
            assert evidence_change["after_image"]["candidate_name"] == display
        with Session(engine) as db:
            names = _approved_raw_event_names(db, values={"28th Honinbo"}, lang="en")
            assert len(names) == 1 and names[0][0].display_name == display
        old_corrections.append(deepcopy(corrected["candidates"][0]))
        prior_bundle, prior_research, prior_batch_id = corrected, research, result["batch_id"]
    with engine.connect() as conn:
        latest = conn.execute(KifuRawEventName.__table__.select().where(
            KifuRawEventName.raw_event_id == 20, KifuRawEventName.lang == "en"
        )).mappings().one()
        latest_sha = canonical_sha256(_image(conn, KifuRawEventName.__table__, latest["id"]))
        for stale in old_corrections:
            with pytest.raises(BatchError, match="name preimage changed"):
                _check_name_preimages(conn, [stale], db_registry())
            forged_cas = deepcopy(stale)
            forged_cas["name_preimage_sha256"] = latest_sha
            with pytest.raises(BatchError, match="marker or target differs"):
                name_batch._check_first_pass_correction(conn, forged_cas, db_registry())


@pytest.mark.parametrize("drift", [
    "prior_name_revision", "prior_candidate_sha256", "prior_evidence_sha256",
    "prior_batch_id", "prior_bundle_sha256", "name_preimage_sha256", "owner_kind",
    "non_generated_name", "non_generated_evidence", "unapproved_evidence", "other_generation_rule",
])
def test_generated_raw_event_correction_rejects_stale_or_authoritative_preimage(engine, drift):
    from katrain.web.kifu import name_batch

    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    first, first_records = _one_shared_raw_event_bundle(bundle, records, 0)
    result = apply_bundle(engine, first, db_registry(), inv, first_records)
    corrected, _research = _corrected_raw_event_bundle(
        engine, first, first_records[0], result["batch_id"], "28th Honinbo Championship")
    candidate = corrected["candidates"][0]
    marker = candidate["first_pass_correction"]
    if drift in {"prior_name_revision", "prior_batch_id"}:
        marker[drift] += 1
    elif drift in {"prior_candidate_sha256", "prior_evidence_sha256", "prior_bundle_sha256"}:
        marker[drift] = "b" * 64
    elif drift == "name_preimage_sha256":
        marker[drift] = "b" * 64
    elif drift == "owner_kind":
        candidate["owner"] = {"kind": "raw_player", "id": candidate["owner"]["id"]}
    else:
        with engine.begin() as conn:
            name = conn.execute(KifuRawEventName.__table__.select()).mappings().one()
            if drift == "non_generated_name":
                conn.execute(KifuRawEventName.__table__.update().where(
                    KifuRawEventName.id == name["id"]).values(decision_kind="conventional"))
            else:
                change = ({"non_generated_evidence": {"decision_kind": "conventional"},
                           "unapproved_evidence": {"review_status": "pending"},
                           "other_generation_rule": {"generation_rule_version": "other-v1"}}[drift])
                conn.execute(KifuNameResearchEvidence.__table__.update().where(
                    KifuNameResearchEvidence.id == name["evidence_id"]).values(**change))
        with engine.connect() as conn:
            name = conn.execute(KifuRawEventName.__table__.select()).mappings().one()
            image = _image(conn, KifuRawEventName.__table__, name["id"])
            evidence = _image(conn, KifuNameResearchEvidence.__table__, name["evidence_id"])
            candidate["name_preimage_sha256"] = marker["name_preimage_sha256"] = canonical_sha256(image)
            marker["prior_evidence_sha256"] = canonical_sha256(evidence)
    with engine.connect() as conn, pytest.raises(BatchError):
        name_batch._check_first_pass_correction(conn, candidate, db_registry())


@pytest.mark.parametrize("drift", ["method", "scope", "owner_source"])
def test_generated_raw_event_correction_requires_new_literal_translation_scope(engine, drift):
    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    first, first_records = _one_shared_raw_event_bundle(bundle, records, 0)
    result = apply_bundle(engine, first, db_registry(), inv, first_records)
    corrected, research = _corrected_raw_event_bundle(
        engine, first, first_records[0], result["batch_id"], "28th Honinbo Championship")
    if drift == "method":
        research["generation"]["method"] = "transliteration"
    elif drift == "scope":
        research["raw_scope"]["slots"] = [{**research["raw_scope"]["slots"][0], "album_id": 999}]
    else:
        research["source_input"]["owner_preimage_sha256"] = "b" * 64
    candidate = corrected["candidates"][0]
    candidate["research_sha256"] = canonical_sha256(research)
    candidate["generated_review"]["research_sha256"] = candidate["research_sha256"]
    with engine.connect() as conn, pytest.raises(BatchError):
        _check_first_pass_sources(conn, [candidate], {candidate["research_sha256"]: research},
                                  corrected["owners"])


def test_generated_raw_event_correction_rejects_changed_live_scope(engine):
    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    first, first_records = _one_shared_raw_event_bundle(bundle, records, 0)
    result = apply_bundle(engine, first, db_registry(), inv, first_records)
    corrected, research = _corrected_raw_event_bundle(
        engine, first, first_records[0], result["batch_id"], "28th Honinbo Championship")
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.insert().values(
            id=88, player_black="Black", player_white="White", event="28th Honinbo",
            sgf_content="(;EV[28th Honinbo])", source_path="late-raw-event.sgf"))
    candidate = corrected["candidates"][0]
    with engine.connect() as conn, pytest.raises(BatchError, match="occurrence scope changed"):
        _check_first_pass_sources(conn, [candidate], {candidate["research_sha256"]: research},
                                  corrected["owners"])


def test_generated_raw_event_correction_rejects_existing_locale_source(engine):
    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    first, first_records = _one_shared_raw_event_bundle(bundle, records, 0)
    result = apply_bundle(engine, first, db_registry(), inv, first_records)
    corrected, research = _corrected_raw_event_bundle(
        engine, first, first_records[0], result["batch_id"], "28th Honinbo Championship")
    with Session(engine) as db:
        source_evidence = _evidence(db, "raw_event", 20, "cn", "28th Honinbo")
        db.add(KifuRawEventName(raw_event_id=20, lang="cn", display_name="28th Honinbo",
                                status="verified", decision_kind="conventional",
                                generation_rule_version="test-v1", revision=1,
                                evidence_id=source_evidence.id))
        db.commit()
    with engine.connect() as conn:
        source_name = conn.execute(KifuRawEventName.__table__.select().where(
            KifuRawEventName.raw_event_id == 20, KifuRawEventName.lang == "cn"
        )).mappings().one()
        source_name_image = _image(conn, KifuRawEventName.__table__, source_name["id"])
        source_evidence_image = _image(conn, KifuNameResearchEvidence.__table__, source_name["evidence_id"])
    research["source_input"] = {
        "kind": "existing_locale", "owner": research["owner"], "text": "28th Honinbo",
        "owner_preimage_sha256": research["source_input"]["owner_preimage_sha256"],
        "lang": "cn", "name_id": source_name["id"],
        "name_preimage_sha256": canonical_sha256(source_name_image),
        "evidence_preimage_sha256": canonical_sha256(source_evidence_image),
    }
    candidate = corrected["candidates"][0]
    candidate.pop("collision_decision")
    candidate.pop("collision_basis")
    candidate["research_sha256"] = canonical_sha256(research)
    candidate["generated_review"]["research_sha256"] = candidate["research_sha256"]
    assert validate_research_record(research, db_registry())
    assert validate_candidate(candidate, research, db_registry(), inv)
    with engine.connect() as conn, pytest.raises(BatchError, match="literal translation research"):
        _check_first_pass_sources(conn, [candidate], {candidate["research_sha256"]: research},
                                  corrected["owners"])


def test_first_pass_shared_raw_event_same_bundle_and_finite_search(engine):
    from katrain.web.kifu.identity import strict_matching_names

    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, records)["ready"]
    apply_bundle(engine, bundle, db_registry(), inv, records)
    with Session(engine) as db:
        assert len(strict_matching_names(db, "28th Honinbo Tournament")[3]) == 2
        assert {item.id for item in _list(db, "28th Honinbo Tournament", "en").items if item.id in {12, 13}} == {
            12, 13,
        }


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_first_pass_shared_raw_event_cross_bundle_order(engine, order):
    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    for index in order:
        one, one_records = _one_shared_raw_event_bundle(bundle, records, index)
        assert dry_run_bundle(engine, one, db_registry(), inv, one_records)["ready"]
        assert apply_bundle(engine, one, db_registry(), inv, one_records)["status"] == "applied"


def test_first_pass_shared_raw_event_can_match_existing_canonical_event(engine):
    from katrain.web.kifu.identity import strict_matching_names

    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=4, canonical_name="Honinbo"))
    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    one, one_records = _one_shared_raw_event_bundle(bundle, records, 0)
    with Session(engine) as db:
        evidence = _evidence(db, "event", 4, "en", "28th Honinbo Tournament")
        db.add(KifuEventName(event_id=4, lang="en", display_name="28th Honinbo Tournament",
                             status="verified", decision_kind="conventional",
                             generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()
    assert dry_run_bundle(engine, one, db_registry(), inv, one_records)["ready"]
    apply_bundle(engine, one, db_registry(), inv, one_records)
    with Session(engine) as db:
        player_ids, event_ids, _players, raw_names = strict_matching_names(db, "28th Honinbo Tournament")
        assert player_ids == set() and event_ids == {4} and len(raw_names) == 1


def test_first_pass_existing_shared_raw_event_allows_later_canonical_event(engine):
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=4, canonical_name="Honinbo"))
    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    one, one_records = _one_shared_raw_event_bundle(bundle, records, 0)
    apply_bundle(engine, one, db_registry(), inv, one_records)
    event_inv, event_bundle, event_records = bound_player_bundle(engine)
    owner = {"kind": "event", "id": 4}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuEvent.__table__, 4)
    research = event_records[0]
    research.update(owner=owner, lang="en", original_name="Honinbo",
                    candidate_name="28th Honinbo Tournament")
    research["source_input"] = {"kind": "catalog_canonical", "owner": owner, "text": "Honinbo",
                                "owner_preimage_sha256": canonical_sha256(owner_image)}
    research["generation"]["method"] = "translation"
    candidate = event_bundle["candidates"][0]
    candidate.update(owner=owner, lang="en", display_name="28th Honinbo Tournament",
                     research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(owner=owner, lang="en", display_name=candidate["display_name"],
                                          research_sha256=candidate["research_sha256"])
    candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(candidate)
    event_bundle["members"] = [{"owner": owner, "lang": "en"}]
    event_bundle["member_set_sha256"] = canonical_sha256(event_bundle["members"])
    event_bundle["owners"] = [{"owner": owner, "preimage": owner_image}]
    event_bundle["owner_set_sha256"] = canonical_sha256(event_bundle["owners"])
    event_bundle["catalog_sha256"] = catalog_snapshot_sha(engine)
    assert dry_run_bundle(engine, event_bundle, db_registry(), event_inv, event_records)["ready"]


@pytest.mark.parametrize("other_kind", ["player", "old_raw_event"])
def test_first_pass_shared_raw_event_does_not_mix_player_or_old_raw(engine, other_kind):
    inv, bundle, records = bound_shared_raw_event_bundle(engine)
    one, one_records = _one_shared_raw_event_bundle(bundle, records, 0)
    with Session(engine) as db:
        if other_kind == "player":
            evidence = _evidence(db, "player", 17, "en", "28th Honinbo Tournament")
            db.add(KifuPlayerName(player_id=17, lang="en", display_name="28th Honinbo Tournament",
                                   status="verified", decision_kind="conventional",
                                   generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        else:
            evidence = _evidence(db, "raw_event", 21, "en", "28th Honinbo Tournament")
            from katrain.web.core.models_db import KifuRawEventName
            db.add(KifuRawEventName(raw_event_id=21, lang="en", display_name="28th Honinbo Tournament",
                                    status="verified", decision_kind="conventional",
                                    generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()
    with pytest.raises(BatchError, match="collision"):
        dry_run_bundle(engine, one, db_registry(), inv, one_records)


def test_first_pass_record_label_only_on_direct_scope_not_selected_title(engine):
    from katrain.web.kifu.name_first_pass import record_label_display

    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            source="https://19x19.com", source_path="data/kifu-album/19x19/one.sgf",
            date_played="1934-10-01", board_size=19,
            sgf_content="(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Other]GC[Other | 1手])"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Black", player_white="White", event="GNUGo3.8",
            sgf_content="(;EV[GNUGo3.8])", source_path="gnugo-direct.sgf"))
    apply_reviewed_selection(engine, 11)
    inv = build_inventory(engine, inventory_format=4)
    owner = {"kind": "raw_event", "id": 7}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuRawEventValue.__table__, 7)
        slots = raw_scope_rows(conn, "GNUGo3.8")
    assert owner_image["category"] == "program_source_label"
    declaration = {"owner": owner, "preimage": owner_image, "occurrence_album_ids": [11, 12],
                   "occurrence_sha256": canonical_sha256([11, 12])}
    members, candidates, records = [], [], []
    for lang in ("en", "cn", "tw", "jp", "ko"):
        display = record_label_display(lang, "GNUGo3.8")
        research = {
            "owner": owner, "lang": lang, "registry_version": "test-1",
            "registry_sha256": registry_sha256(db_registry()),
            "source_basis": "user_authorized_first_pass_v1", "scope_status": "generated_first_pass",
            "verification_level": "generated_first_pass", "original_name": "GNUGo3.8",
            "original_language": "und", "source_input": {
                "kind": "raw_event_literal", "owner": owner, "text": "GNUGo3.8",
                "owner_preimage_sha256": canonical_sha256(owner_image),
                "record_label_basis": "program_token"},
            "raw_scope": {"raw_value": "GNUGo3.8", "slots": slots},
            "generation": {"method": "translation", "submode": "literal_record_label"},
            "candidate_name": display, "producer_id": "translator", "producer_model": "gpt-6-luna",
            "review_status": "pending",
        }
        member = {"owner": owner, "lang": lang, "raw_value": "GNUGo3.8"}
        candidate = bind_fixture_candidate({
            **member, "display_name": display, "decision_kind": "generated",
            "research_sha256": canonical_sha256(research),
            "generation_rule_version": "user_authorized_first_pass_v1", "name_preimage_sha256": None,
            "record_label_mode": "literal_record_label",
            "producer_id": "translator", "producer_model": "gpt-6-luna",
            "produced_at": "2026-10-11T01:00:00Z", "review_status": "approved",
            "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
            "reviewed_at": "2026-10-11T01:01:00Z",
            "review_conclusion": "approved_first_pass_display_and_source",
            "generated_review": {"decision": "approve_generated_first_pass", "owner": owner,
                                 "lang": lang, "display_name": display,
                                 "research_sha256": canonical_sha256(research),
                                 "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
                                 "reviewed_at": "2026-10-11T01:01:00Z"},
        })
        candidate["preimage_binding"].update(captured_at="2026-10-11T01:00:15Z",
                                               bound_at="2026-10-11T01:00:30Z")
        members.append(member)
        candidates.append(candidate)
        records.append(research)
    bundle = {"bundle_format": 2, "inventory_format": inv["inventory_format"],
              "inventory_sha256": inv["sha256"], "registry_version": "test-1",
              "registry_sha256": registry_sha256(db_registry()), "rule_version": "first-pass-v1",
              "catalog_sha256": catalog_snapshot_sha(engine), "members": members,
              "member_set_sha256": canonical_sha256(members), "candidates": candidates,
              "owners": [declaration], "owner_set_sha256": canonical_sha256([declaration]),
              "album_links": [], "link_set_sha256": canonical_sha256([])}
    unmarked = deepcopy(candidates[0])
    unmarked.pop("record_label_mode")
    with pytest.raises(CandidateError, match="record label"):
        validate_candidate(unmarked, records[0], db_registry(), inv)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, records)["ready"]
    result = apply_bundle(engine, bundle, db_registry(), inv, records)
    with Session(engine) as db:
        albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_([11, 12])).all()
        selected = live_event_selections(db, albums, album_ids={11})
        for lang in ("en", "cn", "tw", "jp", "ko"):
            rows = _approved_raw_event_names(db, values={"GNUGo3.8"}, lang=lang)
            assert len(rows) == 1
            assert _raw_event_map(rows, albums, selected) == {
                (12, "GNUGo3.8", None): record_label_display(lang, "GNUGo3.8")}
            assert {item.id for item in _list(db, record_label_display(lang, "GNUGo3.8"), lang).items
                    if item.id in {11, 12}} == {12}
    coverage = coverage_report(engine, inv, languages=("en", "cn", "tw", "jp", "ko"))
    assert all(coverage["languages"][lang]["by_decision"].get("record_label", 0) == 1
               for lang in ("en", "cn", "tw", "jp", "ko"))
    from katrain.web.kifu.name_batch import _check_cross_bundle_collisions
    with engine.connect() as conn:
        with pytest.raises(BatchError, match="collision"):
            _check_cross_bundle_collisions(conn, [{
                "owner": {"kind": "event", "id": 4}, "lang": "en",
                "display_name": "Record label: GNUGo3.8", "decision_kind": "generated",
                "generation_rule_version": "user_authorized_first_pass_v1", "review_status": "approved",
            }])
    assert undo_batch(engine, result["batch_id"])["status"] == "undone"
