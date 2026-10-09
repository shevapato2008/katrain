"""Literal raw event titles have exact owner and source scope."""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuEvent, KifuEventAlias, KifuEventSelectionBatch,
    KifuNameBatch, KifuNameChange, KifuNameResearchEvidence, KifuPlayer, KifuPlayerName,
    KifuRawEventName, KifuRawEventValue, KifuRawPlayerName, KifuRawPlayerValue,
)
from katrain.web.kifu.identity import (
    _approved_raw_event_names, strict_display_maps, strict_matching_names, strict_raw_event_search_clause,
)
from katrain.web.kifu.legacy_raw_events import reviewed_raw_event_hints, reviewed_raw_event_search_clause
from katrain.web.kifu import legacy_raw_events
from katrain.web.kifu.name_batch import _image, apply_bundle, dry_run_bundle, undo_batch
from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_candidate
from katrain.web.kifu.name_evidence import EvidenceError, registry_sha256, validate_research_record
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.raw_event_translation import GEOGRAPHIC39_RAW_VALUES, validate_raw_title_research
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


def tokyo_research(ordinal="10th", core="Tokyo Shinbun Cup", kind="edition"):
    raw = f"{ordinal} {core}"
    _, research = literal(raw=raw, display=raw)
    research.update(original_name=core, original_language="en", raw_parts=[
        {"kind": kind, "text": ordinal + " "}, {"kind": "core", "text": core},
    ])
    research["source_checks"][0].update(
        query=core, observed_lang="en", candidate_name=core, body_excerpt=core + " (東京新聞盃)")
    return research


@pytest.mark.parametrize("ordinal", ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th"])
def test_tokyo_titles_accept_exact_lossless_english_editions(ordinal):
    assert validate_raw_title_research(tokyo_research(ordinal))


@pytest.mark.parametrize("ordinal,core,kind", [
    ("12th", "Tokyo Shinbun Cup", "edition"),
    ("1th", "Tokyo Shinbun Cup", "edition"),
    ("10th", "Tokyo Shimbun Cup", "edition"),
    ("10th", "Another Cup", "edition"),
    ("10th", "Tokyo Shinbun Cup", "round"),
])
def test_tokyo_titles_reject_other_editions_spelling_or_round(ordinal, core, kind):
    with pytest.raises(ValueError, match="unsupported year or ordinal"):
        validate_raw_title_research(tokyo_research(ordinal, core, kind))


def test_raw_title_candidate_binds_research_hash_and_raw_spelling():
    row, research = literal()
    inv = inventory()
    inv["album_associations"].append([3, "Black", "White", row["raw_value"], None, None, None])
    for change in ({"research_sha256": "0" * 64}, {"raw_value": "友情杯"},
                   {"generation_rule_version": "event-title-translation-v1"}):
        with pytest.raises(CandidateError):
            validate_candidate({**row, **change}, research, registry(), inv)


def geographic_research(raw="2007年中国围棋段位赛第一轮"):
    _, research = literal(raw=raw, display="China Go Rank Tournament, Round 1")
    year, _, round_text = raw.partition("中国围棋段位赛")
    research["raw_parts"] = ([{"kind": "year", "text": year}] if year else []) + [
        {"kind": "geographic_qualifier", "text": "中国"}, {"kind": "core", "text": "围棋段位赛"},
    ] + ([{"kind": "round", "text": round_text}] if round_text else [])
    research["original_name"] = "围棋段位赛"
    research["original_language_basis_url"] = "https://www.sport.gov.cn/n14471/n14482/n14519/c737737/content.html"
    research["source_checks"][0].update(
        source_id="sport-go-rank-promotion-2016", query="围棋段位赛",
        url=research["original_language_basis_url"], candidate_name="围棋段位赛",
        body_sha256="d64bd42d177f1c81ca3b467a1eac5da36154923223fbd2863b96e8f216cd16ca",
        body_excerpt="全国围棋段位赛诞生于1982年",
        identity_basis="The captured article contains the exact core 围棋段位赛; year and round come from EV")
    return research


def test_geographic_qualifier_accepts_exact_source_core_and_lossless_parts():
    assert len(GEOGRAPHIC39_RAW_VALUES) == 39
    assert canonical_sha256(sorted(GEOGRAPHIC39_RAW_VALUES)) == (
        "996b55aae2bacf4b5b1273d14fb75e5f4c95d1d5bc0451f3759606a1fd4da315")
    assert all(validate_raw_title_research(geographic_research(raw)) for raw in GEOGRAPHIC39_RAW_VALUES)
    sources = registry()
    sources["sources"].append({"id": "sport-go-rank-promotion-2016", "tier": "official",
                               "home_url": "https://www.sport.gov.cn/", "language": "zh-Hans"})
    research = geographic_research()
    research["registry_sha256"] = registry_sha256(sources)
    assert validate_research_record(research, sources)["owner"] == research["owner"]
    row, _ = literal(raw=research["raw_value"], display=research["candidate_name"])
    row["research_sha256"] = canonical_sha256(research)
    inv = inventory()
    inv["album_associations"].append([3, "Black", "White", research["raw_value"], None, None, None])
    assert validate_candidate(row, research, sources, inv) == row


@pytest.mark.parametrize("raw,parts", [
    ("2006年中国围棋段位赛第一轮", None),
    ("2007年中华围棋段位赛第一轮", ["year", "geographic_qualifier", "core", "round"]),
    ("2007年围棋段位赛中国第一轮", ["year", "core", "geographic_qualifier", "round"]),
])
def test_geographic_qualifier_rejects_outside_scope_or_wrong_text_or_position(raw, parts):
    research = geographic_research(raw)
    if parts:
        texts = ["2007年", "中华" if "中华" in raw else "中国", "围棋段位赛", "第一轮"]
        if parts[1] == "core":
            texts = ["2007年", "围棋段位赛", "中国", "第一轮"]
        research["raw_parts"] = [{"kind": kind, "text": text} for kind, text in zip(parts, texts)]
    with pytest.raises(ValueError):
        validate_raw_title_research(research)


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
        assert set(db.scalars(select(KifuAlbum.id).where(
            legacy_raw_events.reviewed_literal_raw_event_search_clause(db, "Friendship Cup, Round 1")))) == {11, 12}


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
            assert list(db.scalars(select(KifuAlbum.id).where(
                legacy_raw_events.reviewed_literal_raw_event_search_clause(db, display)))) == [11]
        for lang in ("de", "es", "fr", "ru", "tr", "ua"):
            assert reviewed_raw_event_hints(db, [album], lang) == {11: "Friendship Cup, Round 1"}


def test_legacy_bridge_works_with_old_album_orm_without_hidden_attribute(engine, monkeypatch):
    proposed, inv, research = reviewed_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, research)
    old_model = SimpleNamespace(id=KifuAlbum.id, event=KifuAlbum.event,
                                event_id=KifuAlbum.event_id, duplicate_of_id=KifuAlbum.duplicate_of_id)
    monkeypatch.setattr(legacy_raw_events, "KifuAlbum", old_model)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        old_album = SimpleNamespace(id=album.id, event=album.event,
                                    event_id=album.event_id, duplicate_of_id=album.duplicate_of_id)
        assert reviewed_raw_event_hints(db, [old_album], "en") == {11: "Friendship Cup, Round 1"}
        clause = reviewed_raw_event_search_clause(db, "Friendship Cup, Round 1")
        assert list(db.scalars(select(KifuAlbum.id).where(clause))) == [11]


@pytest.mark.parametrize("missing", ["original_language", "identity_basis", "source_id", "http_status", "display"])
def test_persisted_literal_title_requires_complete_source_and_display(engine, missing):
    proposed, inv, research = reviewed_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, research)
    with engine.begin() as conn:
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__)).mappings().one()
        payload = deepcopy(evidence["research_payload"])
        record = payload["research"]
        if missing == "display":
            payload["candidate"]["display_name"] = record["candidate_name"] = ""
            conn.execute(KifuRawEventName.__table__.update().values(display_name=""))
            conn.execute(KifuNameResearchEvidence.__table__.update().values(candidate_name=""))
        elif missing in {"identity_basis", "source_id", "http_status"}:
            record["source_checks"][0].pop(missing)
        else:
            record.pop(missing)
        payload["candidate"]["research_sha256"] = canonical_sha256(record)
        conn.execute(KifuNameResearchEvidence.__table__.update().values(research_payload=payload))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert _approved_raw_event_names(db, values={album.event}, lang="en") == []
        assert reviewed_raw_event_hints(db, [album], "en") == {}


@pytest.mark.parametrize("collision", ["two_players", "raw_player"])
def test_legacy_exact_raw_search_refuses_ambiguous_other_name_owners(engine, collision):
    proposed, inv, research = reviewed_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, research)
    display = "Friendship Cup, Round 1"
    with engine.begin() as conn:
        registry_id = conn.scalar(select(KifuNameResearchEvidence.source_registry_id).limit(1))
        if collision == "two_players":
            conn.execute(KifuPlayer.__table__.insert().values(id=18, canonical_name="Other player"))
            owners = [(17, KifuPlayerName, "player_id"), (18, KifuPlayerName, "player_id")]
        else:
            conn.execute(KifuRawPlayerValue.__table__.insert().values(
                id=99, raw_value="Other raw player", category="readable_unlinked", review_status="approved"))
            owners = [(99, KifuRawPlayerName, "raw_player_id")]
        for owner_id, model, owner_column in owners:
            evidence_id = conn.execute(KifuNameResearchEvidence.__table__.insert().values(
                **{owner_column: owner_id}, lang="en", revision=1, source_registry_id=registry_id,
                candidate_name=display, decision_kind="conventional", generation_rule_version="test-rule",
                research_payload={"candidate": {}}, producer_id="producer-1", producer_model="gpt-6-sol",
                reviewed_at=datetime.now(timezone.utc), reviewer_id="reviewer-2", reviewer_model="gpt-6-astra",
                review_status="approved")).inserted_primary_key[0]
            conn.execute(model.__table__.insert().values(
                **{owner_column: owner_id}, lang="en", revision=1, display_name=display,
                status="verified", evidence_id=evidence_id, decision_kind="conventional",
                generation_rule_version="test-rule"))
    with Session(engine) as db:
        assert reviewed_raw_event_search_clause(db, display) is None
        assert legacy_raw_events.reviewed_literal_raw_event_search_clause(db, display) is None
    with engine.begin() as conn:
        owner_field = (KifuNameResearchEvidence.player_id if collision == "two_players"
                       else KifuNameResearchEvidence.raw_player_id)
        conn.execute(KifuNameResearchEvidence.__table__.update().where(owner_field.is_not(None)).values(
            review_status="pending"))
    with Session(engine) as db:
        assert reviewed_raw_event_search_clause(db, display) is not None


@pytest.mark.parametrize("damage", ["owner", "raw", "hash", "signature", "pending", "source",
                                    "owner_review", "rule", "empty_reviewer_id", "empty_reviewer_model",
                                    "blank_conclusion", "owner_blank_conclusion", "owner_blank_basis"])
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
        elif damage in {"empty_reviewer_id", "empty_reviewer_model"}:
            field = "reviewer_id" if damage == "empty_reviewer_id" else "reviewer_model"
            payload["candidate"][field] = ""
            conn.execute(KifuNameResearchEvidence.__table__.update().values(**{field: ""}))
        elif damage == "blank_conclusion":
            payload["candidate"]["review_conclusion"] = "   "
        elif damage == "pending":
            conn.execute(KifuNameResearchEvidence.__table__.update().values(review_status="pending"))
        elif damage == "owner_review":
            conn.execute(KifuRawEventValue.__table__.update().values(review_metadata=None))
        elif damage in {"owner_blank_conclusion", "owner_blank_basis"}:
            field = "review_conclusion" if damage == "owner_blank_conclusion" else "category_basis"
            review = owner_review(8, payload["candidate"]["raw_value"])
            review[field] = "   "
            conn.execute(KifuRawEventValue.__table__.update().values(review_metadata=review))
        elif damage == "rule":
            payload["candidate"]["generation_rule_version"] = "forged-rule"
            conn.execute(KifuRawEventName.__table__.update().values(generation_rule_version="forged-rule"))
            conn.execute(KifuNameResearchEvidence.__table__.update().values(generation_rule_version="forged-rule"))
        else:
            payload["research"]["source_checks"][0]["candidate_name"] = "Wrong core"
            payload["candidate"]["research_sha256"] = canonical_sha256(payload["research"])
        if damage not in {"pending", "owner_review", "owner_blank_conclusion", "owner_blank_basis"}:
            conn.execute(KifuNameResearchEvidence.__table__.update().values(research_payload=payload))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en") == {}
        assert _approved_raw_event_names(db, values={album.event}, lang="en") == []
        assert legacy_raw_events.reviewed_literal_raw_event_search_clause(db, "Friendship Cup, Round 1") is None


@pytest.mark.parametrize("damage", ["pending_batch", "bundle_hash", "candidate", "research_hash", "ledger"])
def test_literal_exact_search_requires_live_immutable_batch(engine, damage):
    proposed, inv, research = reviewed_bundle(engine)
    applied = apply_bundle(engine, proposed, registry(), inv, research)
    with engine.begin() as conn:
        batch = conn.execute(select(KifuNameBatch.__table__)).mappings().one()
        artifact = deepcopy(batch["reviewed_artifact"])
        if damage == "pending_batch":
            conn.execute(KifuNameBatch.__table__.update().values(status="pending"))
        elif damage == "bundle_hash":
            conn.execute(KifuNameBatch.__table__.update().values(bundle_sha256="0" * 64))
        elif damage == "candidate":
            artifact["bundle"]["candidates"][0]["display_name"] = "Different title"
            conn.execute(KifuNameBatch.__table__.update().values(
                reviewed_artifact=artifact, bundle_sha256=canonical_sha256(artifact["bundle"])))
        elif damage == "research_hash":
            artifact["research_hashes"] = []
            conn.execute(KifuNameBatch.__table__.update().values(reviewed_artifact=artifact))
        else:
            conn.execute(KifuNameChange.__table__.delete().where(
                KifuNameChange.batch_id == applied["batch_id"],
                KifuNameChange.target_table == "kifu_name_research_evidence"))
    with Session(engine) as db:
        assert legacy_raw_events.reviewed_literal_raw_event_search_clause(db, "Friendship Cup, Round 1") is None


@pytest.mark.parametrize("damage", ["hidden", "linked", "duplicate", "selected", "changed_raw"])
def test_literal_exact_search_keeps_only_reviewed_public_unlinked_scope(engine, monkeypatch, damage):
    proposed, inv, research = reviewed_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, research)
    old_model = SimpleNamespace(id=KifuAlbum.id, event=KifuAlbum.event,
                                event_id=KifuAlbum.event_id, duplicate_of_id=KifuAlbum.duplicate_of_id)
    monkeypatch.setattr(legacy_raw_events, "KifuAlbum", old_model)
    with Session(engine) as db:
        db.add(KifuAlbum(id=12, player_black="A", player_white="B", event="友情杯第１轮",
                         sgf_content="(;)", source_path="outside-reviewed-scope.sgf"))
        db.commit()
        clause = legacy_raw_events.reviewed_literal_raw_event_search_clause(db, "Friendship Cup, Round 1")
        assert list(db.scalars(select(KifuAlbum.id).where(clause))) == [11]
        assert legacy_raw_events.reviewed_literal_raw_event_search_clause(db, "Friendship Cup") is None
        album = db.get(KifuAlbum, 11)
        if damage == "hidden":
            album.list_hidden_reason = "fixture"
        elif damage == "linked":
            db.add(KifuEvent(id=1, canonical_name="Other event"))
            db.flush()
            album.event_id = 1
        elif damage == "duplicate":
            album.duplicate_of_id = 12
        elif damage == "changed_raw":
            album.event = "友情杯第２轮"
        else:
            now = datetime.now(timezone.utc)
            batch = KifuEventSelectionBatch(bundle_sha256="a" * 64, member_set_sha256="b" * 64,
                reviewed_artifact={}, producer_id="producer", reviewer_id="reviewer", reviewed_at=now,
                status="applied")
            db.add(batch)
            db.flush()
            db.add(KifuAlbumEventSelection(album_id=11, batch_id=batch.id, selected_raw="Other GN",
                sgf_sha256="c" * 64, property_name="GN", property_index=1, status="approved",
                rule_version="fixture", reviewer_id="reviewer", reviewed_at=now))
        db.commit()
        clause = legacy_raw_events.reviewed_literal_raw_event_search_clause(db, "Friendship Cup, Round 1")
        assert list(db.scalars(select(KifuAlbum.id).where(clause))) == []


def sgf_literal(raw="2020中国国家队积分大循环第1轮"):
    row, research = literal(raw=raw, display="2020 China National Go Team Points Round-Robin Tournament, Round 1")
    core, separator, round_number = raw.partition("第")
    research.update(source_basis="sgf_literal_v1", original_language_basis="reviewed_sgf_gn",
                    original_name=core if separator else raw, source_checks=[])
    research.pop("original_language_basis_url")
    research["raw_parts"] = [{"kind": "core", "text": research["original_name"]}]
    if separator:
        research["raw_parts"].append({"kind": "round", "text": separator + round_number})
    scope = [{"id": 11, "event": raw, "event_id": None, "round_name": None,
              "date_played": "2020-01-01", "black_rank": "1p", "white_rank": "1p",
              "source_path": "national.sgf", "sgf_sha256": "3" * 64}]
    research["sgf_literal_evidence"] = {"captured_at": "2026-10-02T10:00:00Z",
                                        "scope_sha256": canonical_sha256(scope),
                                        "scope_file": "TEST/owner-plan.approved.json", "scope_rows": scope}
    research["original_sgf_refs"] = [{"album_id": 11, "source_path": "national.sgf",
                                      "sgf_sha256": "3" * 64, "ev_values": [],
                                      "gn_values": [raw, raw + " (timeout)"]}]
    row["research_sha256"] = canonical_sha256(research)
    return row, research


@pytest.mark.parametrize("raw", ["2020中国国家队积分大循环第1轮", "2013职业棋手精英赛",
                                  "2014日本国家队新浪网络训练赛"])
def test_national15_sgf_literal_accepts_three_true_title_shapes(raw):
    _, research = sgf_literal(raw)
    assert validate_raw_title_research(research)
    assert validate_research_record(research, registry())["raw_value"] == raw
    assert "".join(part["text"] for part in research["raw_parts"]) == raw


@pytest.mark.parametrize("damage", ["other_raw", "event", "player", "raw_player", "scope_hash",
                                     "raw_reference", "sgf_hash", "reference_missing", "fake_ev_basis"])
def test_sgf_literal_rejects_scope_or_reference_misuse(damage):
    _, research = sgf_literal()
    if damage == "other_raw":
        research["raw_value"] = "2021中国国家队积分大循环第1轮"
        research["raw_parts"][0]["text"] = research["original_name"] = "2021中国国家队积分大循环"
    elif damage in {"event", "player", "raw_player"}:
        research["owner"]["kind"] = damage
    elif damage == "scope_hash":
        research["sgf_literal_evidence"]["scope_sha256"] = "0" * 64
    elif damage == "raw_reference":
        research["original_sgf_refs"][0]["gn_values"][0] = "Different title"
    elif damage == "sgf_hash":
        research["original_sgf_refs"][0]["sgf_sha256"] = "4" * 64
    elif damage == "reference_missing":
        research["original_sgf_refs"] = []
    else:
        research["original_language_basis"] = "reviewed_sgf_ev"
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


def test_sgf_marker_absent_keeps_external_source_gate():
    _, research = sgf_literal()
    research.pop("source_basis")
    with pytest.raises(EvidenceError, match="source URL"):
        validate_research_record(research, registry())
    _, research = literal()
    research["source_checks"] = []
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


def sgf_reviewed_bundle(engine):
    proposed, inv, _ = reviewed_bundle(engine)
    row, research = sgf_literal()
    raw = research["raw_value"]
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            event=raw, sgf_content=f"(;GN[{raw}]GN[{raw} (timeout)])"))
        from scripts.kifu_raw_event_title_owners import _scope_rows
        scope = _scope_rows(conn, raw)
        review = owner_review(8, raw)
        review["scope_sha256"] = canonical_sha256(scope)
        conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 8).values(
            raw_value=raw, review_metadata=review))
    research["sgf_literal_evidence"]["scope_rows"] = scope
    research["sgf_literal_evidence"]["scope_sha256"] = canonical_sha256(scope)
    research["original_sgf_refs"][0].update(source_path=scope[0]["source_path"], sgf_sha256=scope[0]["sgf_sha256"])
    row["research_sha256"] = canonical_sha256(research)
    row["name_preimage_sha256"] = None
    bind_fixture_candidate(row)
    inv = build_inventory(engine, inventory_format=4)
    with engine.connect() as conn:
        before = _image(conn, KifuRawEventValue.__table__, 8)
    declaration = {"owner": row["owner"], "preimage": before, "occurrence_album_ids": [11],
                   "occurrence_sha256": canonical_sha256([11])}
    proposed["inventory_sha256"] = inv["sha256"]
    proposed["members"][0]["raw_value"] = raw
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    proposed["candidates"] = [row]
    return _v2_wrap(engine, inv, proposed, [declaration], []), inv, [research]


def test_sgf_candidate_requires_approved_owner_scope_hash(engine):
    proposed, inv, research = sgf_reviewed_bundle(engine)
    assert dry_run_bundle(engine, proposed, registry(), inv, research)["approved"] == 1
    proposed["owners"][0]["preimage"]["review_metadata"]["scope_sha256"] = "0" * 64
    proposed["owner_set_sha256"] = canonical_sha256(proposed["owners"])
    from katrain.web.kifu.name_candidates import validate_bundle
    report = validate_bundle(proposed, registry(), inv, research)
    assert any("SGF literal owner scope" in error for error in report["errors"])


@pytest.mark.parametrize("capture", ["sgf", "support"])
def test_sgf_name_approval_must_follow_used_captures(engine, capture):
    proposed, inv, research = sgf_reviewed_bundle(engine)
    r = research[0]
    if capture == "sgf":
        r["sgf_literal_evidence"]["captured_at"] = "2026-10-02T12:00:00Z"
    else:
        r["translation_support"] = [{"source_id": "article", "url": "https://example.org/concept",
                                     "body_excerpt": "国家队积分大循环", "body_sha256": "5" * 64,
                                     "fetched_at": "2026-10-02T12:00:00Z", "http_status": 200,
                                     "observed_lang": "zh-Hans", "purpose": "Tournament concept vocabulary only",
                                     "archive_file": "sources/article.html"}]
    proposed["candidates"][0]["research_sha256"] = canonical_sha256(r)
    from katrain.web.kifu.name_candidates import validate_bundle
    report = validate_bundle(proposed, registry(), inv, research)
    assert any("predates a source capture" in error for error in report["errors"])


@pytest.mark.parametrize("damage", ["owner_scope", "research_signature", "late_sgf", "late_support"])
def test_sgf_persisted_readers_recheck_scope_signature_and_capture_times(engine, damage):
    proposed, inv, research = sgf_reviewed_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, research)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en") == {11: proposed["candidates"][0]["display_name"]}
        assert _approved_raw_event_names(db, values={album.event}, lang="en")
    with engine.begin() as conn:
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__)).mappings().one()
        payload = deepcopy(evidence["research_payload"])
        if damage == "owner_scope":
            review = deepcopy(proposed["owners"][0]["preimage"]["review_metadata"])
            review["scope_sha256"] = "0" * 64
            conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 8).values(review_metadata=review))
        elif damage == "research_signature":
            payload["research"]["producer_id"] = "forged-producer"
        elif damage == "late_sgf":
            payload["research"]["sgf_literal_evidence"]["captured_at"] = "2026-10-02T12:00:00Z"
        else:
            payload["research"]["translation_support"] = [{"source_id": "article", "url": "https://example.org/concept",
                "body_excerpt": "国家队积分大循环", "body_sha256": "5" * 64, "fetched_at": "2026-10-02T12:00:00Z",
                "http_status": 200, "observed_lang": "zh-Hans", "purpose": "Concept only", "archive_file": "article.html"}]
        if damage != "owner_scope":
            payload["candidate"]["research_sha256"] = canonical_sha256(payload["research"])
            conn.execute(KifuNameResearchEvidence.__table__.update().values(research_payload=payload))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en") == {}
        assert _approved_raw_event_names(db, values={album.event}, lang="en") == []


def test_sgf_national_title_preserves_existing_core_and_round_parts():
    _, research = sgf_literal()
    research["raw_parts"] = [{"kind": "core", "text": research["raw_value"]}]
    research["original_name"] = research["raw_value"]
    with pytest.raises(EvidenceError, match="fixed title parts"):
        validate_research_record(research, registry())


BULK_PARTS = (
    ("2013职业精英网络赛", [{"kind": "core", "text": "2013职业精英网络赛"}]),
    ("第1届洛阳龙门杯中国棋圣战预选第2轮", [{"kind": "edition", "text": "第1届"},
        {"kind": "core", "text": "洛阳龙门杯中国棋圣战预选"}, {"kind": "round", "text": "第2轮"}]),
    ("第4届台湾碁圣战分组循环赛", [{"kind": "edition", "text": "第4届"},
        {"kind": "core", "text": "台湾碁圣战分组循环赛"}]),
    ("2012韩国网站联赛第3轮", [{"kind": "core", "text": "2012韩国网站联赛"},
        {"kind": "round", "text": "第3轮"}]),
)


def bulk_sgf_literal(raw=BULK_PARTS[0][0], parts=None):
    row, research = sgf_literal(raw)
    parts = deepcopy(parts or BULK_PARTS[0][1])
    research["raw_parts"] = parts
    research["original_name"] = next(part["text"] for part in parts if part["kind"] == "core")
    research["sgf_literal_evidence"].update(owner_profile="sgf_chinese", raw_parts_sha256=canonical_sha256(parts))
    row["research_sha256"] = canonical_sha256(research)
    return row, research


MIXED_PARTS = (
    ("KB国民银行杯2012韩国围乙联赛", [{"kind": "core", "text": "KB国民银行杯2012韩国围乙联赛"}]),
    ("第2期日本幽玄杯精锐循环赛", [{"kind": "edition", "text": "第2期"},
        {"kind": "core", "text": "日本幽玄杯精锐循环赛"}]),
    ("3届韩国最强棋手战循环圈", [{"kind": "edition", "text": "3届"},
        {"kind": "core", "text": "韩国最强棋手战循环圈"}]),
)

# Actual pending raw titles; the third is PROD discovery owner 62450.
MIXED_GAME_ROUND_RAWS = (
    "2016惠山古镇杯中国围乙1轮",
    "18届韩国GG拍卖杯绅士淑女擂台赛2局",
    "2022年弈城中韩冠军争霸赛32强战2番棋第2局",
)


@pytest.mark.parametrize("raw", MIXED_GAME_ROUND_RAWS)
def test_sgf_chinese_mixed_game_round_research_uses_actual_parser(raw):
    from katrain.web.kifu.name_structure import structure_event
    parts = [{"kind": p["kind"], "text": p["text"]} for p in structure_event(raw)["parts"]]
    _, research = bulk_sgf_literal(raw, parts)
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese_mixed"
    assert validate_research_record(research, registry())["raw_parts"] == parts
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese"
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


@pytest.mark.parametrize("kind,text", [("round", "0轮"), ("game", "0局"), ("game", "第0局"),
                                      ("game", "００局"), ("round", "2局"), ("game", "第2轮"),
                                      ("game", "一一局"), ("round", "百百轮"),
                                      ("game", "1000局"), ("game", "１０００局"),
                                      ("match", "第2局")])
def test_sgf_chinese_mixed_game_round_rejects_zero_or_mismatched_kind(kind, text):
    raw = "友情杯" + text
    parts = [{"kind": "core", "text": "友情杯"}, {"kind": kind, "text": text}]
    _, research = bulk_sgf_literal(raw, parts)
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese_mixed"
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


@pytest.mark.parametrize("profile", ["sgf_chinese", "sgf_chinese_mixed"])
def test_sgf_chinese_existing_zero_ordinal_remains_accepted(profile):
    from katrain.web.kifu.name_structure import structure_event
    raw = "友情杯第0轮"
    parts = [{"kind": p["kind"], "text": p["text"]} for p in structure_event(raw)["parts"]]
    _, research = bulk_sgf_literal(raw, parts)
    research["sgf_literal_evidence"]["owner_profile"] = profile
    assert validate_research_record(research, registry())["raw_parts"] == parts


@pytest.mark.parametrize("raw", ["友情杯001局", "友情杯999轮", "友情杯九十九局"])
def test_sgf_chinese_mixed_new_numbers_match_parser_boundaries(raw):
    from katrain.web.kifu.name_structure import structure_event
    parts = [{"kind": p["kind"], "text": p["text"]} for p in structure_event(raw)["parts"]]
    _, research = bulk_sgf_literal(raw, parts)
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese_mixed"
    assert validate_research_record(research, registry())["raw_parts"] == parts


@pytest.mark.parametrize("raw,parts", MIXED_PARTS)
def test_sgf_chinese_mixed_research_accepts_exact_existing_parts(raw, parts):
    _, research = bulk_sgf_literal(raw, parts)
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese_mixed"
    assert validate_research_record(research, registry())["raw_parts"] == parts
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese"
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


@pytest.mark.parametrize("damage", ["pure_latin", "duplicate_core", "duplicate_kind", "non_lossless", "parts_hash"])
def test_sgf_chinese_mixed_research_rejects_invalid_parts(damage):
    _, research = bulk_sgf_literal(*MIXED_PARTS[1])
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese_mixed"
    if damage == "pure_latin":
        research["raw_value"] = research["original_name"] = "KB Cup"
        research["raw_parts"] = [{"kind": "core", "text": "KB Cup"}]
    elif damage == "duplicate_core":
        research["raw_parts"] = [{"kind": "core", "text": "第2期"},
                                 {"kind": "core", "text": "日本幽玄杯精锐循环赛"}]
    elif damage == "duplicate_kind":
        research["raw_parts"] = [{"kind": "edition", "text": "第"}, {"kind": "edition", "text": "2期"},
                                 {"kind": "core", "text": "日本幽玄杯精锐循环赛"}]
    elif damage == "non_lossless":
        research["raw_parts"][0]["text"] = "2期"
    else:
        research["sgf_literal_evidence"]["raw_parts_sha256"] = "0" * 64
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


ENGLISH_RAWS = ("Hoensha game", "1st Tokyo Shinbun Cup", "26thP'aewang", "Kiseong,10th")
HOENSHA_DISPLAYS = {"cn": "Hoensha棋局", "tw": "Hoensha棋局", "jp": "Hoenshaの対局",
                    "ko": "Hoensha 대국", "en": "Hoensha game"}


def english_sgf_literal(raw):
    from katrain.web.kifu.name_structure import structure_event
    structure = structure_event(raw)
    parts = [{"kind": part["kind"], "text": part["text"]} for part in structure["parts"]]
    row, research = bulk_sgf_literal(raw, parts)
    research["original_language"] = "en"
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_english"
    row["research_sha256"] = canonical_sha256(research)
    return row, research, structure


@pytest.mark.parametrize("raw", ENGLISH_RAWS)
def test_sgf_english_research_accepts_actual_parser_shapes(raw):
    _, research, structure = english_sgf_literal(raw)
    assert validate_research_record(research, registry())["raw_parts"] == [
        {"kind": part["kind"], "text": part["text"]} for part in structure["parts"]]


def test_sgf_english_event_research_accepts_ev_and_mixed_gn_scope():
    _, research, _ = english_sgf_literal("1st Tokyo Shinbun Cup")
    research["original_language_basis"] = "reviewed_sgf_event_title"
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_english_event"
    research["original_sgf_refs"][0].update(gn_values=["Game 1"], ev_values=[research["raw_value"]])
    second = {**research["sgf_literal_evidence"]["scope_rows"][0], "id": 12,
              "source_path": "second.sgf", "sgf_sha256": "4" * 64}
    research["sgf_literal_evidence"]["scope_rows"].append(second)
    research["sgf_literal_evidence"]["scope_sha256"] = canonical_sha256(
        research["sgf_literal_evidence"]["scope_rows"])
    research["original_sgf_refs"].append({"album_id": 12, "source_path": "second.sgf",
                                          "sgf_sha256": "4" * 64,
                                          "gn_values": [research["raw_value"]], "ev_values": []})
    assert validate_research_record(research, registry())["raw_value"] == research["raw_value"]


@pytest.mark.parametrize("damage", ("wrong_ev", "later_ev", "wrong_gn", "wrong_basis", "old_profile"))
def test_sgf_english_event_rejects_wrong_source_field(damage):
    _, research, _ = english_sgf_literal("1st Tokyo Shinbun Cup")
    raw = research["raw_value"]
    research["original_language_basis"] = "reviewed_sgf_event_title"
    research["sgf_literal_evidence"]["owner_profile"] = "sgf_english_event"
    ref = research["original_sgf_refs"][0]
    ref.update(gn_values=[raw], ev_values=[raw])
    if damage == "wrong_ev":
        ref["ev_values"] = ["Other Cup"]
    elif damage == "later_ev":
        ref["ev_values"] = ["Other Cup", raw]
    elif damage == "wrong_gn":
        ref.update(gn_values=["Other game"], ev_values=[])
    elif damage == "wrong_basis":
        research["original_language_basis"] = "reviewed_sgf_gn"
    else:
        research["sgf_literal_evidence"]["owner_profile"] = "sgf_english"
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


def test_old_sgf_english_profile_still_requires_empty_ev():
    _, research, _ = english_sgf_literal("1st Tokyo Shinbun Cup")
    research["original_sgf_refs"][0]["ev_values"] = [research["raw_value"]]
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


@pytest.mark.parametrize("ordinal", ("2nd", "3rd", "11th", "12th", "13th", "21st", "112th", "999th"))
def test_sgf_english_accepts_correct_ordinal_boundaries(ordinal):
    _, research, _ = english_sgf_literal(f"{ordinal} Cup")
    assert validate_research_record(research, registry())["raw_value"] == f"{ordinal} Cup"


@pytest.mark.parametrize("raw", ("0th Cup", "1th Cup", "11st Cup", "12nd Cup", "13rd Cup",
                                  "21th Cup", "1000th Cup", "Cup, 10th"))
def test_sgf_english_rejects_invalid_ordinal_even_if_parser_keeps_core(raw):
    _, research, _ = english_sgf_literal(raw)
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


@pytest.mark.parametrize("damage", ("wrong_language", "chinese_profile", "bad_hash", "wrong_parts",
                                          "extra_part", "bad_ordinal", "non_ascii", "no_letter"))
def test_sgf_english_research_rejects_cross_profile_or_invalid_parts(damage):
    _, research, _ = english_sgf_literal("1st Tokyo Shinbun Cup")
    if damage == "wrong_language":
        research["original_language"] = "zh-Hans"
    elif damage == "chinese_profile":
        research["sgf_literal_evidence"]["owner_profile"] = "sgf_chinese_mixed"
    elif damage == "bad_hash":
        research["sgf_literal_evidence"]["raw_parts_sha256"] = "0" * 64
    elif damage == "wrong_parts":
        research["raw_parts"][0]["text"] = "2nd "
    elif damage == "extra_part":
        research["raw_parts"] = [{"kind": "edition", "text": "1st "},
                                 {"kind": "core", "text": "Tokyo Shinbun "},
                                 {"kind": "core", "text": "Cup"}]
    else:
        raw = {"bad_ordinal": "1th Cup", "non_ascii": "Café Cup", "no_letter": "123"}[damage]
        research["raw_value"] = research["original_name"] = raw
        research["raw_parts"] = [{"kind": "core", "text": raw}]
        research["original_sgf_refs"][0]["gn_values"][0] = raw
        research["sgf_literal_evidence"]["scope_rows"][0]["event"] = raw
        research["sgf_literal_evidence"]["scope_sha256"] = canonical_sha256(
            research["sgf_literal_evidence"]["scope_rows"])
        research["sgf_literal_evidence"]["raw_parts_sha256"] = canonical_sha256(research["raw_parts"])
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


@pytest.mark.parametrize("raw", ENGLISH_RAWS)
def test_sgf_english_name_apply_and_strict_read(engine, raw):
    _, evidence, structure = english_sgf_literal(raw)
    parts = evidence["raw_parts"]
    proposed, inv, research = bulk_reviewed_bundle(engine, raw, parts, profile="sgf_english", structure=structure)
    research[0]["original_language"] = "en"
    candidate = proposed["candidates"][0]
    candidate["research_sha256"] = canonical_sha256(research[0])
    candidate.pop("preimage_binding")
    bind_fixture_candidate(candidate)
    assert dry_run_bundle(engine, proposed, registry(), inv, research)["approved"] == 1
    apply_bundle(engine, proposed, registry(), inv, research)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert strict_display_maps(db, [album], "en")[-1][(11, raw, None)] == candidate["display_name"]


@pytest.mark.parametrize("lang,display", HOENSHA_DISPLAYS.items())
def test_sgf_english_hoensha_five_language_apply_and_strict_read(engine, lang, display):
    from katrain.web.kifu.name_structure import structure_event
    raw = "Hoensha game"
    structure = structure_event(raw)
    parts = [{"kind": part["kind"], "text": part["text"]} for part in structure["parts"]]
    proposed, inv, research = bulk_reviewed_bundle(engine, raw, parts, profile="sgf_english", structure=structure)
    research[0].update(original_language="en", lang=lang, candidate_name=display)
    candidate = proposed["candidates"][0]
    candidate.update(lang=lang, display_name=display, research_sha256=canonical_sha256(research[0]))
    candidate.pop("preimage_binding")
    bind_fixture_candidate(candidate)
    proposed["members"][0]["lang"] = lang
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    assert dry_run_bundle(engine, proposed, registry(), inv, research)["approved"] == 1
    apply_bundle(engine, proposed, registry(), inv, research)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert strict_display_maps(db, [album], lang)[-1][(11, raw, None)] == display


@pytest.mark.parametrize("raw,parts", BULK_PARTS)
def test_sgf_chinese_research_accepts_four_actual_parser_shapes(raw, parts):
    _, research = bulk_sgf_literal(raw, parts)
    assert validate_research_record(research, registry())["raw_parts"] == parts


@pytest.mark.parametrize("raw", ["Tokyo Cup", "中国ABC赛", "日本カップ", "中国대회", "比赛\n名称", "2026"])
def test_sgf_chinese_rejects_non_chinese_or_control_text(raw):
    _, research = bulk_sgf_literal(raw, [{"kind": "core", "text": raw}])
    with pytest.raises(EvidenceError):
        validate_research_record(research, registry())


def bulk_reviewed_bundle(engine, raw=BULK_PARTS[0][0], parts=None, profile="sgf_chinese", structure=None):
    proposed, _, _ = sgf_reviewed_bundle(engine)
    row, research = bulk_sgf_literal(raw, parts)
    research["sgf_literal_evidence"]["owner_profile"] = profile
    raw, parts = research["raw_value"], research["raw_parts"]
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            event=raw, sgf_content=f"(;GN[{raw}]GN[{raw} (timeout)])"))
        from scripts.kifu_raw_event_title_owners import _scope_rows
        scope = _scope_rows(conn, raw)
        review = owner_review(8, raw)
        review["scope_sha256"] = canonical_sha256(scope)
        review["sgf_literal"] = {"source_basis": "sgf_literal_v1", "profile": profile,
                                 "raw_parts_sha256": canonical_sha256(parts)}
        conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 8).values(
            raw_value=raw, parsed_data={"structure": structure or {"parts": [{**p, "value": p["text"]} for p in parts]}},
            review_metadata=review))
        before = _image(conn, KifuRawEventValue.__table__, 8)
    research["sgf_literal_evidence"].update(scope_rows=scope, scope_sha256=canonical_sha256(scope))
    research["original_sgf_refs"][0].update(source_path=scope[0]["source_path"], sgf_sha256=scope[0]["sgf_sha256"])
    row["research_sha256"] = canonical_sha256(research)
    row["name_preimage_sha256"] = None
    bind_fixture_candidate(row)
    inv = build_inventory(engine, inventory_format=4)
    proposed["inventory_sha256"] = inv["sha256"]
    proposed["members"][0]["raw_value"] = raw
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    proposed["candidates"] = [row]
    declaration = {"owner": row["owner"], "preimage": before, "occurrence_album_ids": [11],
                   "occurrence_sha256": canonical_sha256([11])}
    return _v2_wrap(engine, inv, proposed, [declaration], []), inv, [research]


@pytest.mark.parametrize("raw", MIXED_GAME_ROUND_RAWS)
def test_sgf_chinese_mixed_game_round_apply_and_strict_read(engine, raw):
    from katrain.web.kifu.name_structure import structure_event
    from katrain.web.kifu.name_candidates import validate_bundle
    structure = structure_event(raw)
    parts = [{"kind": p["kind"], "text": p["text"]} for p in structure["parts"]]
    proposed, inv, research = bulk_reviewed_bundle(
        engine, raw, parts, profile="sgf_chinese_mixed", structure=structure)
    assert validate_bundle(proposed, registry(), inv, research)["ready"]
    assert dry_run_bundle(engine, proposed, registry(), inv, research)["approved"] == 1
    apply_bundle(engine, proposed, registry(), inv, research)
    display = proposed["candidates"][0]["display_name"]
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert db.get(KifuRawEventValue, 8).parsed_data == {"structure": structure}
        assert album.event == raw and album.sgf_content == f"(;GN[{raw}]GN[{raw} (timeout)])"
        assert reviewed_raw_event_hints(db, [album], "en") == {11: display}
        assert _approved_raw_event_names(db, values={raw}, lang="en")
        assert strict_display_maps(db, [album], "en")[-1][(11, raw, None)] == display


@pytest.mark.parametrize("damage", ["missing_marker", "parts_hash", "actual_parser"])
def test_sgf_chinese_candidate_binds_approved_parser_parts(engine, damage):
    from katrain.web.kifu.name_candidates import validate_bundle
    proposed, inv, research = bulk_reviewed_bundle(engine)
    assert validate_bundle(proposed, registry(), inv, research)["ready"]
    before = proposed["owners"][0]["preimage"]
    if damage == "missing_marker":
        before["review_metadata"].pop("sgf_literal")
    elif damage == "parts_hash":
        before["review_metadata"]["sgf_literal"]["raw_parts_sha256"] = "0" * 64
    else:
        before["parsed_data"]["structure"]["parts"][0]["text"] = "Different parser core"
    proposed["owner_set_sha256"] = canonical_sha256(proposed["owners"])
    report = validate_bundle(proposed, registry(), inv, research)
    assert any("SGF literal owner scope" in error for error in report["errors"])


@pytest.mark.parametrize("damage", ["missing_marker", "parts_hash"])
def test_sgf_chinese_persisted_readers_require_new_parts_marker(engine, damage):
    proposed, inv, research = bulk_reviewed_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, research)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en")
        assert _approved_raw_event_names(db, values={album.event}, lang="en")
    with engine.begin() as conn:
        review = deepcopy(proposed["owners"][0]["preimage"]["review_metadata"])
        if damage == "missing_marker":
            review.pop("sgf_literal")
        else:
            review["sgf_literal"]["raw_parts_sha256"] = "0" * 64
        conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 8).values(review_metadata=review))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en") == {}
        assert _approved_raw_event_names(db, values={album.event}, lang="en") == []


@pytest.mark.parametrize("damage", ("missing_marker", "wrong_profile", "unknown_profile"))
def test_sgf_chinese_mixed_candidate_and_reader_require_matching_profile(engine, damage):
    from katrain.web.kifu.name_candidates import validate_bundle
    raw, parts = MIXED_PARTS[0]
    proposed, inv, research = bulk_reviewed_bundle(engine, raw, parts, profile="sgf_chinese_mixed")
    assert validate_bundle(proposed, registry(), inv, research)["ready"]
    apply_bundle(engine, proposed, registry(), inv, research)
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en")
    with engine.begin() as conn:
        review = deepcopy(proposed["owners"][0]["preimage"]["review_metadata"])
        if damage == "missing_marker":
            review.pop("sgf_literal")
        else:
            review["sgf_literal"]["profile"] = "sgf_chinese" if damage == "wrong_profile" else "unlisted"
        conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 8).values(review_metadata=review))
    with Session(engine) as db:
        album = db.get(KifuAlbum, 11)
        assert reviewed_raw_event_hints(db, [album], "en") == {}
        assert _approved_raw_event_names(db, values={album.event}, lang="en") == []
