"""Incremental publication preserves strict names and complete immutable SGFs."""

from copy import deepcopy
from hashlib import sha256
import importlib

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuAlbumSource,
    KifuNameBatch,
    KifuNameChange,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
)
from katrain.web.kifu import name_batch
from katrain.web.kifu.identity import strict_slot_approvals
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_first_pass import VERSION, raw_scope_rows
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.name_parse import parse_event
from tests.web_ui.test_kifu_name_batch import bind_fixture_candidate, registry


LANGUAGES = ("cn", "tw", "jp", "ko", "en")


def publisher():
    # The first RED reports the missing public interface as an assertion.
    import katrain.kifu_ingest

    assert importlib.util.find_spec("katrain.kifu_ingest.catalog") is not None, "publisher is not implemented"
    return importlib.import_module("katrain.kifu_ingest.catalog")


def _seed_names(engine, players=(17, 18), event="Summer Cup"):
    inv = build_inventory(engine)
    declarations, candidates, records, members = [], [], [], []
    with engine.connect() as conn:
        specs = [("player", player_id, KifuPlayer) for player_id in players]
        if event:
            specs.append(("raw_event", 7, KifuRawEventValue))
        for kind, owner_id, model in specs:
            owner = {"kind": kind, "id": owner_id}
            preimage = name_batch._image(conn, model.__table__, owner_id)
            raw = preimage.get("raw_value", preimage.get("canonical_name"))
            declaration = {"owner": owner, "preimage": preimage}
            if kind == "raw_event":
                declaration.update(occurrence_album_ids=[11], occurrence_sha256=canonical_sha256([11]))
            declarations.append(declaration)
            for lang in LANGUAGES:
                display = {
                    "Black": {"cn": "黑棋", "tw": "黑棋", "jp": "黒棋", "ko": "흑기사", "en": "Black"},
                    "White": {"cn": "白棋", "tw": "白棋", "jp": "白棋", "ko": "백기사", "en": "White"},
                    "Summer Cup": {"cn": "夏季杯", "tw": "夏季盃", "jp": "夏季杯", "ko": "여름배", "en": "Summer Cup"},
                }[raw][lang]
                member = {"owner": owner, "lang": lang, **({"raw_value": raw} if kind == "raw_event" else {})}
                research = {
                    "owner": owner,
                    "lang": lang,
                    "registry_version": "test-1",
                    "registry_sha256": registry_sha256(registry()),
                    "source_basis": VERSION,
                    "scope_status": "generated_first_pass",
                    "verification_level": "generated_first_pass",
                    "original_name": raw,
                    "original_language": "en",
                    "candidate_name": display,
                    "source_input": {
                        "kind": "raw_event_literal" if kind == "raw_event" else "catalog_canonical",
                        "owner": owner,
                        "text": raw,
                        "owner_preimage_sha256": canonical_sha256(preimage),
                    },
                    "generation": {"method": "translation"},
                    "producer_id": "fixture-translator",
                    "producer_model": "gpt-6-luna",
                    "review_status": "pending",
                }
                if kind == "raw_event":
                    research["raw_scope"] = {"raw_value": raw, "slots": raw_scope_rows(conn, raw)}
                candidate = {
                    **member,
                    "display_name": display,
                    "decision_kind": "generated",
                    "generation_rule_version": VERSION,
                    "research_sha256": canonical_sha256(research),
                    "name_preimage_sha256": None,
                    "producer_id": "fixture-translator",
                    "producer_model": "gpt-6-luna",
                    "produced_at": "2026-10-11T01:00:00Z",
                    "review_status": "approved",
                    "reviewer_id": "fixture-reviewer",
                    "reviewer_model": "gpt-6.1-sol",
                    "reviewed_at": "2026-10-11T01:01:00Z",
                    "review_conclusion": "approved_first_pass_display_and_source",
                }
                candidate["generated_review"] = {
                    "decision": "approve_generated_first_pass",
                    **{
                        key: candidate[key]
                        for key in (
                            "owner",
                            "lang",
                            "display_name",
                            "research_sha256",
                            "reviewer_id",
                            "reviewer_model",
                            "reviewed_at",
                        )
                    },
                }
                bind_fixture_candidate(candidate)["preimage_binding"].update(
                    captured_at="2026-10-11T01:00:10Z", bound_at="2026-10-11T01:00:20Z"
                )
                members.append(member)
                candidates.append(candidate)
                records.append(research)
    bundle = {
        "bundle_format": 2,
        "inventory_format": inv["inventory_format"],
        "inventory_sha256": inv["sha256"],
        "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()),
        "rule_version": "first-pass-v1",
        "catalog_sha256": name_batch.catalog_snapshot_sha(engine),
        "members": members,
        "member_set_sha256": canonical_sha256(members),
        "owners": declarations,
        "owner_set_sha256": canonical_sha256(declarations),
        "candidates": candidates,
        "album_links": [],
        "link_set_sha256": canonical_sha256([]),
    }
    return name_batch.apply_bundle(engine, bundle, registry(), inv, records)


def make_engine(path, players=(17, 18)):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for owner_id, canonical in zip(players, ("Black", "White")):
            conn.execute(KifuPlayer.__table__.insert().values(id=owner_id, canonical_name=canonical))
            conn.execute(
                KifuPlayerAlias.__table__.insert().values(
                    player_id=owner_id, alias=canonical + " Alias", normalized_alias=(canonical + " Alias").lower()
                )
            )
        conn.execute(
            KifuRawEventValue.__table__.insert().values(
                id=7, raw_value="Summer Cup", category=parse_event("Summer Cup", None).category, review_status="pending"
            )
        )
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=11,
                black_player_id=players[0],
                white_player_id=players[1],
                player_black="Black",
                player_white="White",
                event="Summer Cup",
                date_played="2026-01-30",
                sgf_content="(;PB[Black]PW[White]EV[Summer Cup];B[aa])",
                source_path="legacy-11.sgf",
            )
        )
    _seed_names(engine, players)
    return engine


@pytest.fixture
def engine(tmp_path):
    result = make_engine(tmp_path / "incremental.db")
    yield result
    result.dispose()


def manifest(source_id="123", black="Black Alias", event="Summer Cup"):
    sgf = f"(;FF[4]GM[1]SZ[19]PB[{black}]PW[White]EV[{event}]DT[2026-02-01]C[whole original];B[bb];W[cc])"
    return {
        "format": "kifu-incremental-manifest-v1",
        "publication_key": f"fixture-{source_id}",
        "decisions": [],
        "games": [
            {
                "source_key": "19x19",
                "source_item_id": source_id,
                "origin_path": f"fixture/{source_id}.sgf",
                "raw_sha256": sha256(sgf.encode()).hexdigest(),
                "sgf_sha256": sha256(sgf.encode()).hexdigest(),
                "sgf_content": sgf,
                "metadata": {
                    "player_black": black,
                    "player_white": "White",
                    "event": event,
                    "date_played": "2026-02-01",
                },
            }
        ],
    }


def publish(engine, value):
    return publisher().publish_manifest(engine, value, expected_manifest_sha256=canonical_sha256(value))


def assert_qualified(engine, ids):
    with Session(engine) as db:
        albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_(ids)).all()
        for lang in LANGUAGES:
            approvals = strict_slot_approvals(db, albums, lang)
            assert set(approvals) == set(ids)
            assert all(all(slots) for slots in approvals.values()), (lang, approvals)


def state(engine):
    with engine.connect() as conn:
        return {
            table: [tuple(row) for row in conn.execute(select(table).order_by(table.c.id))]
            for table in (
                KifuAlbum.__table__,
                KifuAlbumSource.__table__,
                KifuPlayerName.__table__,
                KifuRawEventName.__table__,
                KifuNameResearchEvidence.__table__,
                KifuNameBatch.__table__,
                KifuNameChange.__table__,
                KifuSource.__table__,
                KifuNameSourceRegistry.__table__,
                KifuRawPlayerValue.__table__,
                KifuRawPlayerName.__table__,
                KifuRawEventValue.__table__,
            )
        }


def test_incremental_publication_renews_existing_raw_event_and_keeps_history(engine):
    assert_qualified(engine, [11])
    before = state(engine)
    value = manifest()
    result = publish(engine, value)
    album_id = result["games"][0]["album_id"]
    assert result["games"][0]["action"] == "inserted"
    assert_qualified(engine, [11, album_id])
    with engine.connect() as conn:
        album = conn.execute(select(KifuAlbum).where(KifuAlbum.id == album_id)).mappings().one()
        assert (album["black_player_id"], album["white_player_id"]) == (17, 18)
        assert album["sgf_content"] == value["games"][0]["sgf_content"]
        assert conn.scalar(select(func.count()).select_from(KifuPlayer)) == 2
        assert set(conn.scalars(select(KifuRawEventName.revision))) == {2}
        assert conn.scalar(select(func.count()).select_from(KifuNameResearchEvidence)) == 20
    assert state(engine)[KifuAlbum.__table__][0] == before[KifuAlbum.__table__][0]
    assert state(engine)[KifuNameResearchEvidence.__table__][:15] == before[KifuNameResearchEvidence.__table__]


def test_atomic_scope_renewal_preserves_two_qualified_raw_events_sharing_display(engine):
    first = manifest("124", event="Summer Tournament")
    approved = decision(first, "raw_event", "Summer Tournament")
    approved["displays"] = publisher().qualified_raw_event_templates(engine)["templates"]["Summer Cup"]["displays"]
    approved["review"]["content_sha256"] = publisher().review_content_sha256(approved)
    first["decisions"] = [approved]
    prior = publish(engine, first)
    old_ids = [11, prior["games"][0]["album_id"]]
    assert_qualified(engine, old_ids)
    before = state(engine)

    value = manifest("125")
    second = manifest("126", event="Summer Tournament")["games"][0]
    second["sgf_content"] = second["sgf_content"].replace("B[bb]", "B[dd]")
    second["sgf_sha256"] = second["raw_sha256"] = sha256(second["sgf_content"].encode()).hexdigest()
    value["games"].append(second)
    receipt = publish(engine, value)

    assert_qualified(engine, old_ids + [row["album_id"] for row in receipt["games"]])
    with engine.connect() as conn:
        assert set(conn.scalars(select(KifuRawEventName.revision))) == {2}
    assert state(engine)[KifuNameResearchEvidence.__table__][:20] == before[KifuNameResearchEvidence.__table__]


@pytest.mark.parametrize("new_title", [False, True])
def test_scope_or_new_title_cannot_launder_an_unqualified_existing_display_collision(engine, new_title):
    raw = "Spring Cup" if new_title else "Summer Cup"
    display = "春季杯" if new_title else "夏季杯"
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=8, raw_value="Unreviewed Other Cup", category="readable_unlinked", review_status="pending"
        ))
        conn.execute(KifuRawEventName.__table__.insert().values(
            raw_event_id=8, lang="jp", display_name=display, status="verified",
            decision_kind="generated", generation_rule_version=VERSION,
            evidence_id=conn.scalar(select(KifuRawEventName.evidence_id).where(KifuRawEventName.lang == "jp"))
        ))
    value = manifest("127", event=raw)
    if new_title:
        value["decisions"] = [decision(value, "raw_event", raw)]
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="normalized name collision"):
        publish(engine, value)
    assert state(engine) == before
    assert_qualified(engine, [11])


def test_two_new_candidates_need_explicit_shared_display_before_any_proof_is_written(engine):
    records = [{"owner": {"kind": "raw_event", "id": owner_id}} for owner_id in (8, 9)]
    candidates = [
        {"owner": {"kind": "raw_event", "id": owner_id}, "lang": "jp", "display_name": "同名大会",
         "decision_kind": "generated", "generation_rule_version": VERSION, "research_sha256": canonical_sha256(record)}
        for owner_id, record in zip((8, 9), records)
    ]
    before = state(engine)
    with name_batch._locked_write(engine) as conn:
        with pytest.raises(publisher().PublicationError, match="incoming name decisions have conflicting displays"):
            publisher()._write_name_batch(conn, candidates, records, [], "a" * 64, "b" * 64)
    assert state(engine) == before


def test_incremental_failure_rolls_back_sgf_sources_names_and_receipt(engine, monkeypatch):
    api = publisher()
    before = state(engine)
    real = api.strict_slot_approvals

    def fail_new(db, albums, lang, **kwargs):
        actual = real(db, albums, lang, **kwargs)
        return {key: ((None, *slots[1:]) if key != 11 else slots) for key, slots in actual.items()}

    monkeypatch.setattr(api, "strict_slot_approvals", fail_new)
    with pytest.raises(api.PublicationError, match="five-language|coverage"):
        publish(engine, manifest())
    assert state(engine) == before
    assert_qualified(engine, [11])


def test_same_logical_manifest_resolves_each_databases_own_player_ids(engine, tmp_path):
    target = make_engine(tmp_path / "target.db", players=(101, 202))
    value = manifest()
    first, second = publish(engine, value), publish(target, value)
    for db_engine, result, expected in ((engine, first, (17, 18)), (target, second, (101, 202))):
        with db_engine.connect() as conn:
            album = (
                conn.execute(select(KifuAlbum).where(KifuAlbum.id == result["games"][0]["album_id"])).mappings().one()
            )
            assert (album["black_player_id"], album["white_player_id"]) == expected
        assert_qualified(db_engine, [11, result["games"][0]["album_id"]])


@pytest.mark.parametrize("fault", ["missing_language", "ambiguous_alias", "raw_source_change", "missing_journal"])
def test_incremental_rejects_incomplete_conflicting_or_changed_source_without_writes(engine, fault):
    api = publisher()
    value = manifest()
    if fault == "missing_language":
        with engine.begin() as conn:
            conn.execute(
                KifuPlayerName.__table__.delete().where(KifuPlayerName.player_id == 17, KifuPlayerName.lang == "ko")
            )
    elif fault == "ambiguous_alias":
        with engine.begin() as conn:
            conn.execute(
                KifuPlayerAlias.__table__.insert().values(
                    player_id=18, alias="Black Alias", normalized_alias="black alias"
                )
            )
    elif fault == "missing_journal":
        with engine.begin() as conn:
            evidence_id = conn.scalar(
                select(KifuPlayerName.evidence_id).where(KifuPlayerName.player_id == 17, KifuPlayerName.lang == "ko")
            )
            conn.execute(
                KifuNameChange.__table__.delete().where(
                    KifuNameChange.target_table == "kifu_name_research_evidence",
                    KifuNameChange.target_row_id == evidence_id,
                )
            )
    else:
        publish(engine, value)
        value["publication_key"] += "-changed"
        value["games"][0]["sgf_content"] += "\n"
        value["games"][0]["sgf_sha256"] = sha256(value["games"][0]["sgf_content"].encode()).hexdigest()
        value["games"][0]["raw_sha256"] = value["games"][0]["sgf_sha256"]
    before = state(engine)
    with pytest.raises(api.PublicationError):
        publish(engine, value)
    assert state(engine) == before


def test_idempotent_replay_returns_identical_receipt_without_any_write(engine):
    value = manifest()
    first = publish(engine, value)
    before = state(engine)
    assert publish(engine, value) == first
    assert state(engine) == before


def test_replay_rejects_a_changed_published_sgf(engine):
    value = manifest()
    result = publish(engine, value)
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.update()
            .where(KifuAlbum.id == result["games"][0]["album_id"])
            .values(sgf_content="(;PB[Black]PW[White];B[zz])")
        )
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="source|SGF|receipt"):
        publish(engine, value)
    assert state(engine) == before


def test_equal_mainline_with_different_full_sgf_is_not_automatically_merged(engine):
    first = publish(engine, manifest())
    value = manifest("124")
    game = value["games"][0]
    game["sgf_content"] = game["sgf_content"].replace("whole original", "different annotation")
    game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
    second = publish(engine, value)
    assert second["games"][0]["action"] == "inserted"
    assert second["games"][0]["album_id"] != first["games"][0]["album_id"]
    assert_qualified(engine, [11, first["games"][0]["album_id"], second["games"][0]["album_id"]])


def test_canonical_identical_sgf_adds_source_but_does_not_replace_stored_original(engine):
    first_value = manifest()
    first = publish(engine, first_value)
    value = manifest("124")
    value["games"][0]["sgf_content"] = SGF.parse_sgf(first_value["games"][0]["sgf_content"]).sgf()
    value["games"][0]["sgf_sha256"] = sha256(value["games"][0]["sgf_content"].encode()).hexdigest()
    value["games"][0]["raw_sha256"] = value["games"][0]["sgf_sha256"]
    second = publish(engine, value)
    assert second["games"][0]["action"] == "reused"
    assert second["games"][0]["album_id"] == first["games"][0]["album_id"]
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuAlbum)) == 2
        assert conn.scalar(select(func.count()).select_from(KifuAlbumSource)) == 2


def decision(value, kind, key, slot="event"):
    api = publisher()
    displays = (
        {"cn": "春季杯", "tw": "春季盃", "jp": "春季杯", "ko": "봄 대회", "en": "Spring Cup"}
        if kind == "raw_event"
        else {"cn": "新棋手", "tw": "新棋手", "jp": "新棋士", "ko": "신기사", "en": "New Player"}
    )
    result = {
        "kind": kind,
        "key": key,
        "displays": displays,
        "original_language": "en",
        "methods": {lang: "translation" for lang in LANGUAGES},
        "sources": [],
        "source_items": [
            {
                "source_key": game["source_key"],
                "source_item_id": game["source_item_id"],
                "sgf_sha256": game["sgf_sha256"],
                "slot": slot,
            }
            for game in value["games"]
        ],
        "producer": {
            "id": "actual-producer",
            "model": "actual-model",
            "request_id": "request-producer-1",
            "at": "2026-10-18T01:00:00Z",
        },
    }
    result["review"] = {
        "id": "actual-reviewer",
        "model": "actual-review-model",
        "request_id": "request-reviewer-1",
        "at": "2026-10-18T01:01:00Z",
        "decision": "approve",
        "content_sha256": api.review_content_sha256(result),
    }
    return result


def test_reviewed_new_five_language_title_preserves_actual_requests_and_sources(engine):
    value = manifest(event="Spring Cup")
    approved = decision(value, "raw_event", "Spring Cup")
    excerpt = "Official Spring Cup event page"
    approved["sources"] = [
        {
            "url": "https://example.org/spring",
            "lang": "en",
            "title": "Spring Cup",
            "retrieved_at": "2026-10-18T00:00:00Z",
            "excerpt": excerpt,
            "content_sha256": sha256(excerpt.encode()).hexdigest(),
        }
    ]
    approved["review"]["content_sha256"] = publisher().review_content_sha256(approved)
    value["decisions"] = [approved]
    result = publish(engine, value)
    assert_qualified(engine, [11, result["games"][0]["album_id"]])
    with engine.connect() as conn:
        owner_id = conn.scalar(select(KifuRawEventValue.id).where(KifuRawEventValue.raw_value == "Spring Cup"))
        rows = (
            conn.execute(
                select(KifuNameResearchEvidence.__table__).where(KifuNameResearchEvidence.raw_event_id == owner_id)
            )
            .mappings()
            .all()
        )
        assert len(rows) == 5
        for row in rows:
            binding = row["research_payload"]["research"]["incremental_binding"]
            assert binding["decision"] == approved
            assert row["producer_id"] == "actual-producer"
            assert row["reviewer_id"] == "actual-reviewer"


def test_raw_player_review_extends_only_explicit_new_source_slots(engine):
    value = manifest(black="New Player")
    value["decisions"] = [decision(value, "raw_player", "New Player", slot="black")]
    first = publish(engine, value)
    assert_qualified(engine, [11, first["games"][0]["album_id"]])
    next_value = manifest("125", black="New Player")
    # Make the next game different, so exact-SGF reuse cannot skip scope binding.
    game = next_value["games"][0]
    game["sgf_content"] = game["sgf_content"].replace("B[bb]", "B[dd]")
    game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="scope|coverage|decision"):
        publish(engine, next_value)
    assert state(engine) == before
    next_value["decisions"] = [decision(next_value, "raw_player", "New Player", slot="black")]
    second = publish(engine, next_value)
    assert_qualified(engine, [first["games"][0]["album_id"], second["games"][0]["album_id"]])
    with engine.connect() as conn:
        assert set(conn.scalars(select(KifuRawPlayerName.revision))) == {2}


def test_finite_raw_literal_can_share_canonical_text_without_linking_person_identity(engine):
    value = manifest(black="Unknown Black")
    approved = decision(value, "raw_player", "Unknown Black", slot="black")
    with engine.connect() as conn:
        approved["displays"] = dict(
            conn.execute(
                select(KifuPlayerName.lang, KifuPlayerName.display_name).where(KifuPlayerName.player_id == 17)
            ).all()
        )
    approved["review"]["content_sha256"] = publisher().review_content_sha256(approved)
    value["decisions"] = [approved]
    value["games"][0]["identities"] = {"black": None}
    result = publish(engine, value)
    with engine.connect() as conn:
        assert (
            conn.scalar(select(KifuAlbum.black_player_id).where(KifuAlbum.id == result["games"][0]["album_id"])) is None
        )
        assert conn.scalar(select(func.count()).select_from(KifuPlayer)) == 2
    assert_qualified(engine, [11, result["games"][0]["album_id"]])


def test_canonical_cache_rechecks_changed_stored_bytes_under_the_lock(engine):
    api = publisher()
    cache = api.warm_sgf_cache(engine)
    value = manifest()
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(sgf_content=value["games"][0]["sgf_content"])
        )
    result = api.publish_manifest(engine, value, expected_manifest_sha256=canonical_sha256(value), sgf_cache=cache)
    assert result["games"][0]["action"] == "reused"
    assert result["games"][0]["album_id"] == 11


def test_read_only_helpers_offer_qualified_target_provenance_without_fabricating_new_review(engine):
    value = manifest(black="New Player")
    value["decisions"] = [decision(value, "raw_player", "New Player", slot="black")]
    publish(engine, value)
    api = publisher()
    before = state(engine)
    assert hasattr(api, "qualified_raw_player_templates"), "qualified raw-player templates are not implemented"
    report = api.qualified_raw_player_templates(engine, raw_values={"New Player", "Unknown"})
    template = report["templates"]["New Player"]
    assert template["original_language"] == value["decisions"][0]["original_language"]
    assert template["methods"] == value["decisions"][0]["methods"]
    assert template["displays"] == value["decisions"][0]["displays"]
    assert not {"producer", "review", "source_items"} & set(template)
    assert set(report["target_bindings"]["New Player"]) == set(LANGUAGES)
    assert report["unavailable"]["Unknown"] == "missing_qualified_five_languages"
    lookup = api.lookup_qualified_identities(engine, player_values=["Black Alias", "Unknown"])
    assert lookup["player"]["Black Alias"]["status"] == "qualified"
    assert lookup["player"]["Black Alias"]["id"] == 17
    assert lookup["player"]["Unknown"]["status"] == "unresolved"
    assert state(engine) == before


def test_target_identity_check_uses_native_aliases_conflicts_and_qualification_read_only(engine):
    api = publisher()
    with engine.begin() as conn:
        conn.execute(
            KifuPlayerAlias.__table__.insert().values(
                player_id=17, alias="Portable Black", normalized_alias="portable black"
            )
        )
        for owner_id in (17, 18):
            conn.execute(
                KifuPlayerAlias.__table__.insert().values(
                    player_id=owner_id, alias="Ambiguous", normalized_alias="ambiguous"
                )
            )
    request = {
        "operation": "check-identities",
        "game_count": 2,
        "instructions": [
            {"kind": "player", "raw": "Black Alias", "canonical_name": "Portable Black", "name_decision": False},
            {"kind": "player", "raw": "White", "canonical_name": "Portable Black", "name_decision": False},
            {"kind": "player", "raw": "Black Alias", "canonical_name": "黑棋", "name_decision": False},
            {"kind": "player", "raw": "Ambiguous", "canonical_name": "Portable Black", "name_decision": False},
            {"kind": "player", "raw": "Black", "canonical_name": "Portable Black", "name_decision": True},
            {"kind": "player", "raw": "Black", "canonical_name": "Black", "name_decision": True},
        ],
    }
    before = state(engine)
    assert api.check_identity_instructions(engine, request) == {
        "status": "checked",
        "request_sha256": canonical_sha256(request),
        "results": ["qualified", "conflict", "unresolved", "ambiguous", "canonical_decision_key_mismatch", "qualified"],
    }
    assert state(engine) == before
    with engine.begin() as conn:
        conn.execute(
            KifuPlayerName.__table__.delete().where(KifuPlayerName.player_id == 17, KifuPlayerName.lang == "ko")
        )
    request["instructions"] = [request["instructions"][index] for index in (0, 4, 5)]
    before = state(engine)
    assert api.check_identity_instructions(engine, request)["results"] == [
        "missing_qualified_five_languages",
        "canonical_decision_key_mismatch",
        "missing_qualified_five_languages",
    ]
    assert state(engine) == before


@pytest.mark.parametrize(
    "fault",
    [
        "bool_count",
        "too_many_games",
        "too_many_instructions",
        "duplicate",
        "unknown_field",
        "id_field",
        "bad_kind",
        "nonstring_kind",
        "nonstring",
        "nonboolean_decision",
        "long_text",
    ],
)
def test_target_identity_check_rejects_unbounded_or_nonlogical_schema_before_database(fault):
    api = publisher()
    request = {
        "operation": "check-identities",
        "game_count": 1,
        "instructions": [{"kind": "player", "raw": "Black", "canonical_name": "Black", "name_decision": False}],
    }
    if fault == "bool_count":
        request["game_count"] = True
    elif fault == "too_many_games":
        request["game_count"] = 101
    elif fault == "too_many_instructions":
        request["game_count"] = 100
        request["instructions"] = [
            {"kind": "player", "raw": str(i), "canonical_name": "Black", "name_decision": False} for i in range(301)
        ]
    elif fault == "duplicate":
        request["instructions"] *= 2
    elif fault == "unknown_field":
        request["sql"] = "SELECT secret"
    elif fault == "id_field":
        request["instructions"][0]["id"] = 17
    elif fault == "bad_kind":
        request["instructions"][0]["kind"] = "raw_player"
    elif fault == "nonstring_kind":
        request["instructions"][0]["kind"] = ["player"]
    elif fault == "nonstring":
        request["instructions"][0]["raw"] = 17
    elif fault == "nonboolean_decision":
        request["instructions"][0]["name_decision"] = 1
    else:
        request["instructions"][0]["canonical_name"] = "x" * 513
    with pytest.raises(ValueError, match="identity check"):
        api.check_identity_instructions(object(), request)


def test_identity_check_accepts_exact_finite_schema_bounds():
    request = {
        "operation": "check-identities",
        "game_count": 100,
        "instructions": [
            {"kind": "event", "raw": str(i) + "x" * 509, "canonical_name": "y" * 512, "name_decision": False}
            for i in range(300)
        ],
    }
    assert publisher().validate_identity_check_request(request) == request


def test_scope_renewal_preserves_complete_existing_generation_meaning(engine):
    api = publisher()
    value = manifest(black="New Player")
    value["decisions"] = [decision(value, "raw_player", "New Player", slot="black")]
    first = publish(engine, value)
    # An actual native revision whose recorded method has an additional reading
    # basis must survive the portable template (which exposes the method only).
    with name_batch._locked_write(engine) as conn:
        prior = api._existing_player_proofs(conn, {"New Player"})
        candidates, records = [], []
        for lang in LANGUAGES:
            previous = prior[("New Player", lang)]
            payload = previous["evidence"]["research_payload"]
            candidate, research = deepcopy(payload["candidate"]), deepcopy(payload["research"])
            research["generation"]["reading_basis"] = "model_inferred"
            marker = api._scope_refresh_marker(conn, "raw_player", previous)
            marker["version"] = "generated-raw-player-semantic-correction-v1"
            marker.pop("source_meaning_sha256")
            candidate.update(
                first_pass_correction=marker,
                name_preimage_sha256=canonical_sha256(previous["name"]),
                research_sha256=canonical_sha256(research),
            )
            candidate["generated_review"]["research_sha256"] = candidate["research_sha256"]
            candidates.append(candidate)
            records.append(research)
        old_batch = name_batch._image(conn, KifuNameBatch.__table__, payload["first_pass"]["batch_id"])
        declarations = old_batch["reviewed_artifact"]["bundle"]["owners"]
        api._write_name_batch(
            conn, candidates, records, declarations, old_batch["inventory_sha256"], canonical_sha256(value)
        )
    template = api.qualified_raw_player_templates(engine, raw_values={"New Player"})["templates"]["New Player"]
    next_value = manifest("126", black="New Player")
    game = next_value["games"][0]
    game["sgf_content"] = game["sgf_content"].replace("B[bb]", "B[ee]")
    game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
    reviewed = decision(next_value, "raw_player", "New Player", slot="black")
    reviewed.update(template)
    reviewed["review"]["content_sha256"] = api.review_content_sha256(reviewed)
    next_value["decisions"] = [reviewed]
    second = publish(engine, next_value)
    assert_qualified(engine, [first["games"][0]["album_id"], second["games"][0]["album_id"]])
    report = api.qualified_raw_player_templates(engine, raw_values={"New Player"})
    assert all(
        binding["source_meaning"]["generation"]["reading_basis"] == "model_inferred"
        for binding in report["target_bindings"]["New Player"].values()
    )


@pytest.mark.parametrize(
    "fault", ["same_reviewer", "same_request", "wrong_scope", "missing_language", "changed_source"]
)
def test_new_decisions_reject_incomplete_or_unreviewed_text_and_members(engine, fault):
    value = manifest(black="New Player")
    approved = decision(value, "raw_player", "New Player", slot="black")
    if fault == "same_reviewer":
        approved["review"]["id"] = approved["producer"]["id"]
    elif fault == "same_request":
        approved["review"]["request_id"] = approved["producer"]["request_id"]
    elif fault == "wrong_scope":
        approved["source_items"][0]["source_item_id"] = "999"
        approved["review"]["content_sha256"] = publisher().review_content_sha256(approved)
    elif fault == "missing_language":
        approved["displays"].pop("ko")
        approved["review"]["content_sha256"] = publisher().review_content_sha256(approved)
    else:
        approved["sources"].append({"url": "https://example.org/forged"})
    value["decisions"] = [approved]
    before = state(engine)
    with pytest.raises(publisher().PublicationError):
        publish(engine, value)
    assert state(engine) == before


@pytest.mark.parametrize("visibility", [{"list_hidden_reason": "historical quarantine"}, {"duplicate_of_id": 11}])
def test_exact_sgf_cannot_reuse_an_excluded_album(engine, visibility):
    value = manifest()
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.update()
            .where(KifuAlbum.id == 11)
            .values(sgf_content=value["games"][0]["sgf_content"], **visibility)
        )
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="public|hidden|duplicate"):
        publish(engine, value)
    assert state(engine) == before


@pytest.mark.parametrize("visibility", [{"list_hidden_reason": "later quarantine"}, {"duplicate_of_id": 11}])
def test_receipt_replay_requires_every_requested_album_to_remain_public(engine, visibility):
    value = manifest()
    receipt = publish(engine, value)
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.update().where(KifuAlbum.id == receipt["games"][0]["album_id"]).values(**visibility)
        )
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="public|hidden|duplicate"):
        publish(engine, value)
    assert state(engine) == before


@pytest.mark.parametrize("conflict", ["different_alias_owner", "ambiguous_alias", "different_canonical_owner"])
def test_explicit_canonical_instruction_cannot_override_conflicting_raw_identity(engine, conflict):
    value = manifest(black="White" if conflict == "different_canonical_owner" else "Black Alias")
    value["games"][0]["identities"] = {"black": {"canonical_name": "Black"}}
    with engine.begin() as conn:
        if conflict == "different_alias_owner":
            conn.execute(
                KifuPlayerAlias.__table__.update()
                .where(KifuPlayerAlias.normalized_alias == "black alias")
                .values(player_id=18)
            )
        elif conflict == "ambiguous_alias":
            conn.execute(
                KifuPlayerAlias.__table__.insert().values(
                    player_id=18, alias="Black Alias", normalized_alias="black alias"
                )
            )
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="identity|ambiguous"):
        publish(engine, value)
    assert state(engine) == before


@pytest.mark.parametrize("instruction", [{"canonical_name": "White"}, None])
def test_exact_reuse_cannot_silently_ignore_explicit_identity_instruction(engine, instruction):
    publish(engine, manifest())
    value = manifest("129")
    value["games"][0]["identities"] = {"black": instruction}
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="identity"):
        publish(engine, value)
    assert state(engine) == before


def test_explicit_identity_is_checked_again_on_receipt_replay(engine):
    value = manifest()
    value["games"][0]["identities"] = {"black": {"canonical_name": "Black"}}
    publish(engine, value)
    with engine.begin() as conn:
        conn.execute(
            KifuPlayerAlias.__table__.update()
            .where(KifuPlayerAlias.normalized_alias == "black alias")
            .values(player_id=18)
        )
    before = state(engine)
    with pytest.raises(publisher().PublicationError, match="identity"):
        publish(engine, value)
    assert state(engine) == before


def test_qualified_raw_event_helper_offers_native_renewal_without_new_text_review(engine):
    api = publisher()
    before = state(engine)
    assert hasattr(api, "qualified_raw_event_templates"), "qualified raw-event helper is not implemented"
    report = api.qualified_raw_event_templates(engine, raw_values={"Summer Cup", "Unknown"})
    template = report["templates"]["Summer Cup"]
    assert template["kind"] == "raw_event"
    assert template["displays"]["en"] == "Summer Cup"
    assert template["original_language"] == "en"
    assert set(template["methods"].values()) == {"translation"}
    assert not {"producer", "review", "source_items"} & set(template)
    assert report["unavailable"]["Unknown"] == "missing_qualified_five_languages"
    assert state(engine) == before
    result = publish(engine, manifest())
    assert result["reviewed_name_batch_id"] is None
    assert result["name_batch_id"] is not None
    renewed = api.qualified_raw_event_templates(engine, raw_values={"Summer Cup"})
    for lang in LANGUAGES:
        assert (
            renewed["target_bindings"]["Summer Cup"][lang]["source_meaning"]
            == report["target_bindings"]["Summer Cup"][lang]["source_meaning"]
        )
    assert_qualified(engine, [11, result["games"][0]["album_id"]])


def test_conditional_publication_undo_restores_prior_scope_and_is_replay_safe(engine):
    api = publisher()
    assert hasattr(api, "undo_publication"), "atomic publication compensation is not implemented"
    value = manifest(black="New Player")
    value["decisions"] = [decision(value, "raw_player", "New Player", slot="black")]
    before = state(engine)
    receipt = publish(engine, value)
    outcome = api.undo_publication(engine, receipt["batch_id"])
    assert outcome["status"] == "undone"
    after = state(engine)
    for table in before:
        if table not in {KifuNameBatch.__table__, KifuNameChange.__table__, KifuNameSourceRegistry.__table__}:
            assert after[table] == before[table], table.name
    assert_qualified(engine, [11])
    assert api.undo_publication(engine, receipt["batch_id"]) == outcome
    assert state(engine) == after


@pytest.mark.parametrize("changed", ["album", "source_link", "name", "child_artifact", "journal"])
def test_conditional_publication_undo_refuses_any_changed_postimage_atomically(engine, changed):
    api = publisher()
    assert hasattr(api, "undo_publication"), "atomic publication compensation is not implemented"
    receipt = publish(engine, manifest())
    with engine.begin() as conn:
        if changed == "album":
            conn.execute(
                KifuAlbum.__table__.update()
                .where(KifuAlbum.id == receipt["games"][0]["album_id"])
                .values(place="a later edit")
            )
        elif changed == "source_link":
            conn.execute(KifuAlbumSource.__table__.update().values(match_method="later-source-review"))
        elif changed == "name":
            conn.execute(
                KifuRawEventName.__table__.update()
                .where(KifuRawEventName.lang == "en")
                .values(display_name="a later reviewed title")
            )
        elif changed == "child_artifact":
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == receipt["name_batch_id"])
                .values(reviewed_artifact={})
            )
        else:
            change_id = conn.scalar(select(KifuNameChange.id).where(KifuNameChange.batch_id == receipt["batch_id"]))
            conn.execute(KifuNameChange.__table__.delete().where(KifuNameChange.id == change_id))
    before = state(engine)
    with pytest.raises(api.PublicationError, match="changed|journal|artifact"):
        api.undo_publication(engine, receipt["batch_id"])
    assert state(engine) == before


def test_publication_undo_refuses_later_source_dependency_without_partial_reversal(engine):
    api = publisher()
    first = publish(engine, manifest())
    publish(engine, manifest("127"))  # A later receipt retains this exact album/source.
    before = state(engine)
    with pytest.raises(api.PublicationError, match="dependent|changed"):
        api.undo_publication(engine, first["batch_id"])
    assert state(engine) == before


def test_publication_undo_honors_later_receipt_even_when_it_created_no_rows(engine):
    api = publisher()
    value = manifest()
    first = publish(engine, value)
    value["publication_key"] += "-confirmed-again"
    second = publish(engine, value)
    before = state(engine)
    with pytest.raises(api.PublicationError, match="dependent|receipt"):
        api.undo_publication(engine, first["batch_id"])
    assert state(engine) == before
    api.undo_publication(engine, second["batch_id"])
    api.undo_publication(engine, first["batch_id"])
    assert_qualified(engine, [11])


def test_publication_undo_restores_existing_finite_raw_player_scope(engine):
    api = publisher()
    first_value = manifest(black="New Player")
    first_value["decisions"] = [decision(first_value, "raw_player", "New Player", slot="black")]
    first = publish(engine, first_value)
    prior = api.qualified_raw_player_templates(engine, raw_values={"New Player"})
    value = manifest("128", black="New Player")
    game = value["games"][0]
    game["sgf_content"] = game["sgf_content"].replace("B[bb]", "B[ee]")
    game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
    value["decisions"] = [decision(value, "raw_player", "New Player", slot="black")]
    second = publish(engine, value)
    api.undo_publication(engine, second["batch_id"])
    assert api.qualified_raw_player_templates(engine, raw_values={"New Player"}) == prior
    assert_qualified(engine, [11, first["games"][0]["album_id"]])


def test_publisher_derives_search_date_and_numeric_metadata_from_complete_sgf(engine):
    value = manifest()
    game = value["games"][0]
    game["sgf_content"] = game["sgf_content"].replace("SZ[19]", "SZ[19]KM[6.5]HA[0]")
    game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
    receipt = publish(engine, value)
    with engine.connect() as conn:
        album = conn.execute(select(KifuAlbum).where(KifuAlbum.id == receipt["games"][0]["album_id"])).mappings().one()
    assert album["date_sort"] == "2026-02-01"
    assert album["search_text"] == "black alias white summer cup 2026-02-01"
    assert album["komi"] == 6.5
    assert album["board_size"] == 19
    assert album["move_count"] == 2
    assert album["sgf_content"] == game["sgf_content"]


def test_publisher_rejects_derived_metadata_override_and_historical_source_ids(engine):
    from katrain.kifu_ingest.exclusions import historical_excluded_ids

    before = state(engine)
    value = manifest()
    value["games"][0]["metadata"]["date_sort"] = "2030-01-01"
    with pytest.raises(publisher().PublicationError, match="metadata"):
        publish(engine, value)
    with pytest.raises(publisher().PublicationError, match="excluded"):
        publish(engine, manifest(source_id=next(iter(historical_excluded_ids()))))
    assert state(engine) == before
