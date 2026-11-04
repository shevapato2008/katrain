"""One finite canonical correction retains original b009/name evidence."""

from copy import deepcopy
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, event, func, select, update

from katrain.web.core import models_db as m
from katrain.web.kifu import historical_rank_repair as repair, historical_ranks as ranks, name_batch
from katrain.web.kifu.name_candidates import canonical_sha256 as digest
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_inventory import build_inventory
from tests.web_ui.test_kifu_name_batch import registry, bind_fixture_candidate, player_bundle
from tests.web_ui.test_kifu_name_first_pass import first_pass_pair

OLD, NEW = "沼官沙辉哉", "沼馆沙辉哉"
WHEN = "2026-11-04T01:00:00+00:00"
SCOPE = (
    (124026, "black", "41442702", "2014-03-06", "二段", OLD, 2189, 186520),
    (178495, "white", "91342440", "2026-10-15", "七段", NEW, 2518, 233062),
)
DISPLAYS = {"cn": NEW, "tw": "沼館沙輝哉", "jp": "沼舘沙輝哉", "en": "Sakiya Numadate", "ko": "누마다테 사키야"}


def names_package(engine, owner, *, corrected=False, locale_displays=None):
    player_id = owner["id"]
    inventory = build_inventory(engine)
    source_registry = registry()
    source_registry["sources"][0].update(home_url="https://www.nihonkiin.or.jp/", language="ja")
    bundle, _ = player_bundle(inventory, owner_id=player_id)
    bundle.update(registry_sha256=registry_sha256(source_registry))
    members, candidates, research_records = [], [], []
    with engine.connect() as conn:
        preimages = {
            r["lang"]: name_batch._image(conn, m.KifuPlayerName.__table__, r["id"])
            for r in conn.execute(
                select(m.KifuPlayerName.__table__).where(m.KifuPlayerName.player_id == player_id)
            ).mappings()
        }
    for lang in ("cn", "tw", "jp", "en", "ko"):
        display = (
            locale_displays[lang] if locale_displays else DISPLAYS[lang] if corrected or lang in {"en", "ko"} else OLD
        )
        candidate, research = first_pass_pair()
        ref = {"kind": "player", "id": player_id}
        research.update(
            owner=ref,
            lang=lang,
            original_name=owner["canonical_name"],
            candidate_name=display,
            registry_sha256=registry_sha256(source_registry),
        )
        research["source_input"].update(owner=ref, text=owner["canonical_name"], owner_preimage_sha256=digest(owner))
        research["generation"]["method"] = (
            "orthographic_conversion" if lang in {"cn", "tw", "jp"} else "transliteration"
        )
        candidate.update(
            owner=ref,
            lang=lang,
            display_name=display,
            research_sha256=digest(research),
            name_preimage_sha256=digest(preimages[lang]) if lang in preimages else None,
        )
        candidate["generated_review"].update(
            owner=ref, lang=lang, display_name=display, research_sha256=digest(research)
        )
        if corrected and lang == "jp":
            _, records = player_bundle(inventory, owner_id=5364, display=display)
            research = records[0]
            research.update(
                lang="jp",
                registry_sha256=registry_sha256(source_registry),
                original_name="沼舘沙輝哉",
                reading="ぬまだて さきや",
            )
            check = research["source_checks"][0]
            check.update(
                url="https://www.nihonkiin.or.jp/player/htm/ki000430.html",
                query="沼舘沙輝哉 NUMADATE Sakiya",
                observed_lang="ja",
                body_excerpt="沼舘沙輝哉 NUMADATE, Sakiya 2010年入段 2013年二段 2021年七段",
            )
            research["original_language_basis_url"] = research["reading_basis_url"] = check["url"]
            candidate.update(
                producer_id=research["producer_id"],
                producer_model=research["producer_model"],
                decision_kind="conventional",
                generation_rule_version="none",
                research_sha256=digest(research),
                review_conclusion="Confirmed official Japanese name",
            )
            candidate.pop("generated_review")
        bind_fixture_candidate(candidate)
        candidate["preimage_binding"].update(captured_at="2026-10-11T01:00:15Z", bound_at="2026-10-11T01:00:30Z")
        members.append({"owner": ref, "lang": lang})
        candidates.append(candidate)
        research_records.append(research)
    declaration = {"owner": {"kind": "player", "id": player_id}, "preimage": owner}
    bundle.update(
        bundle_format=2,
        members=members,
        member_set_sha256=digest(members),
        candidates=candidates,
        owners=[declaration],
        owner_set_sha256=digest([declaration]),
        album_links=[],
        link_set_sha256=digest([]),
        catalog_sha256=name_batch.catalog_snapshot_sha(engine),
    )
    return dict(bundle=bundle, registry=source_registry, inventory=inventory, evidence_records=research_records)


def _seed_fixture_event(engine):
    from katrain.web.kifu.name_first_pass import raw_scope_rows

    inv = build_inventory(engine)
    reg = registry()
    with engine.connect() as conn:
        owner_image = name_batch._image(conn, m.KifuRawEventValue.__table__, 7)
        scope = raw_scope_rows(conn, "Summer Cup")
    candidates, records, members = [], [], []
    owner = {"kind": "raw_event", "id": 7}
    for lang, display in {"cn": "夏季杯", "tw": "夏季盃", "jp": "夏季杯", "en": "Summer Cup", "ko": "여름배"}.items():
        candidate, research = first_pass_pair()
        research.update(
            owner=owner,
            lang=lang,
            original_name="Summer Cup",
            candidate_name=display,
            original_language="en",
            registry_sha256=registry_sha256(reg),
            raw_scope={"raw_value": "Summer Cup", "slots": scope},
        )
        research["source_input"] = {
            "kind": "raw_event_literal",
            "owner": owner,
            "text": "Summer Cup",
            "owner_preimage_sha256": digest(owner_image),
        }
        research["generation"] = {"method": "translation"}
        member = {"owner": owner, "lang": lang, "raw_value": "Summer Cup"}
        candidate.update(**member, display_name=display, research_sha256=digest(research), name_preimage_sha256=None)
        candidate["generated_review"].update(
            owner=owner, lang=lang, display_name=display, research_sha256=digest(research)
        )
        bind_fixture_candidate(candidate)
        candidate["preimage_binding"].update(captured_at="2026-10-11T01:00:15Z", bound_at="2026-10-11T01:00:30Z")
        members.append(member)
        candidates.append(candidate)
        records.append(research)
    declaration = {
        "owner": owner,
        "preimage": owner_image,
        "occurrence_album_ids": [124026, 178495],
        "occurrence_sha256": digest([124026, 178495]),
    }
    bundle = {
        "bundle_format": 2,
        "inventory_format": inv["inventory_format"],
        "inventory_sha256": inv["sha256"],
        "registry_version": reg["version"],
        "registry_sha256": registry_sha256(reg),
        "rule_version": "candidate-v1",
        "members": members,
        "member_set_sha256": digest(members),
        "candidates": candidates,
        "owners": [declaration],
        "owner_set_sha256": digest([declaration]),
        "album_links": [],
        "link_set_sha256": digest([]),
        "catalog_sha256": name_batch.catalog_snapshot_sha(engine),
    }
    name_batch.apply_bundle(engine, bundle, reg, inv, records)


@pytest.fixture
def correction_engine(tmp_path, request):
    other_rank = getattr(request, "param", "1p")
    engine = create_engine(f"sqlite:///{tmp_path / 'correction.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    m.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(), [dict(id=5364, canonical_name=OLD), dict(id=42, canonical_name="Other")]
        )
        conn.execute(
            m.KifuPlayerAlias.__table__.insert().values(id=58, player_id=5364, alias=NEW, normalized_alias=NEW)
        )
        conn.execute(m.KifuSource.__table__.insert().values(id=19, source_key="19x19"))
        for ident, side, item, day, rank, raw, _, _ in SCOPE:
            black, white = (raw, "Other") if side == "black" else ("Other", raw)
            path = f"data/kifu-album/19x19/{item}.sgf"
            conn.execute(
                m.KifuAlbum.__table__.insert().values(
                    id=ident,
                    source_path=path,
                    sgf_content=f"(;SZ[19]PB[{black}]PW[{white}]BR[{rank if side == 'black' else other_rank}]WR[{rank if side == 'white' else other_rank}]EV[Summer Cup]DT[{day}];B[aa])",
                    player_black=black,
                    player_white=white,
                    black_player_id=5364 if side == "black" else 42,
                    white_player_id=5364 if side == "white" else 42,
                    black_rank=rank if side == "black" else other_rank,
                    white_rank=rank if side == "white" else other_rank,
                    date_played=day,
                    date_sort=day,
                    event="Summer Cup",
                )
            )
            conn.execute(
                m.KifuAlbumSource.__table__.insert().values(
                    album_id=ident, source_id=19, origin_path=path, match_method="source_path"
                )
            )
        conn.execute(
            m.KifuRawEventValue.__table__.insert().values(
                id=7, raw_value="Summer Cup", category="formal_event_candidate", review_status="approved"
            )
        )
        from katrain.kifu_ingest.catalog import _REGISTRY

        conn.execute(
            m.KifuNameSourceRegistry.__table__.insert().values(
                id=385, version=_REGISTRY["version"], sha256=digest(_REGISTRY), registry=_REGISTRY
            )
        )
    package = names_package(engine, _owner(engine))
    name_batch.apply_bundle(
        engine, package["bundle"], package["registry"], package["inventory"], package["evidence_records"]
    )
    with engine.connect() as conn:
        other = name_batch._image(conn, m.KifuPlayer.__table__, 42)
    package = names_package(
        engine, other, locale_displays={"cn": "其他", "tw": "其他", "jp": "他", "en": "Other", "ko": "다른 기사"}
    )
    name_batch.apply_bundle(
        engine, package["bundle"], package["registry"], package["inventory"], package["evidence_records"]
    )
    _seed_fixture_event(engine)
    with engine.begin() as conn:
        conn.execute(
            m.KifuNameBatch.__table__.insert().values(
                id=875,
                bundle_sha256=digest(875),
                inventory_sha256="b" * 64,
                source_registry_id=385,
                reviewed_artifact={},
                status="applied",
            )
        )
        album = dict(conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id == 178495)).mappings().one())
    body = album["sgf_content"]
    manifest = {
        "format": "kifu-incremental-manifest-v1",
        "publication_key": "19x19-event-recovery-synthetic",
        "decisions": [],
        "games": [
            {
                "source_key": "19x19",
                "source_item_id": "91342440",
                "origin_path": album["source_path"],
                "sgf_content": body,
                "raw_sha256": sha256(body.encode()).hexdigest(),
                "sgf_sha256": sha256(body.encode()).hexdigest(),
                "metadata": {
                    key: album[key]
                    for key in ("player_black", "player_white", "black_rank", "white_rank", "date_played", "event")
                },
                "identities": {"black": {"canonical_name": "Other"}, "white": {"canonical_name": OLD}},
            }
        ],
    }
    from tests.web_ui.test_kifu_incremental_catalog import publish

    receipt = publish(engine, manifest)
    assert receipt["batch_id"] == 876
    with engine.begin() as conn:
        for ident, side, _, _, _, _, batch_id, snapshot_id in SCOPE:
            # Use real b009 preparation/application; only allocate the fixed production-shaped IDs.
            manifest = repair.prepare_manifest(conn, matched_at="2026-11-03T00:00:00+00:00", album_ids=[ident])
            part = manifest["parts"][0]
            part["changes"] = [c for c in part["changes"] if c["side"] == side]
            part["basis_bindings"] = [c["basis_binding"] for c in part["changes"]]
            conn.execute(
                m.KifuNameBatch.__table__.insert().values(
                    id=batch_id - 1,
                    bundle_sha256=digest(batch_id),
                    inventory_sha256="b" * 64,
                    source_registry_id=385,
                    reviewed_artifact={},
                    status="applied",
                )
            )
            result = repair.apply_in_transaction(conn, part, expected_sha256=digest(part))
            assert result["batch_id"] == batch_id
            current = (
                conn.execute(select(m.KifuAlbumRankSnapshot.__table__).where(m.KifuAlbumRankSnapshot.album_id == ident))
                .mappings()
                .one()
            )
            conn.execute(
                update(m.KifuAlbumRankSnapshot)
                .where(m.KifuAlbumRankSnapshot.id == current["id"])
                .values(id=snapshot_id)
            )
            journal = (
                conn.execute(select(m.KifuNameChange.__table__).where(m.KifuNameChange.batch_id == batch_id))
                .mappings()
                .one()
            )
            after = dict(journal["after_image"], id=snapshot_id)
            conn.execute(
                update(m.KifuNameChange)
                .where(m.KifuNameChange.id == journal["id"])
                .values(target_row_id=snapshot_id, after_image=after)
            )
    yield engine
    engine.dispose()


def _owner(engine):
    with engine.connect() as conn:
        return name_batch._image(conn, m.KifuPlayer.__table__, 5364)


def inputs(engine):
    owner = dict(_owner(engine), canonical_name=NEW)
    review = {
        "producer_id": "identity-producer",
        "producer_model": "gpt-6.1-sol",
        "reviewer_id": "identity-reviewer",
        "reviewer_model": "gpt-6-astra",
        "reviewed_at": WHEN,
        "conclusion": "same_existing_player_canonical_typo",
        "official_profile": "ki000430",
        "official_name": "沼舘沙輝哉",
        "latin_name": "NUMADATE, Sakiya",
        "career": {"professional_since": 2010, "second_dan": 2013, "seventh_dan": 2021},
        "source_items": ["41442702", "91342440"],
        "same_player_id": 5364,
        "capture": {
            "url": "https://www.nihonkiin.or.jp/player/htm/ki000430.html",
            "body_excerpt": "沼舘沙輝哉 NUMADATE, Sakiya 2010年入段 2013年二段 2021年七段",
            "body_sha256": sha256(b"synthetic official capture").hexdigest(),
        },
        "corroboration": "Both existing FKs resolve same row; correct spelling in 2026 source, exact dates/ranks fit official career; typo 官 differs from 館/舘.",
    }
    return dict(
        matched_at=WHEN,
        identity_review=review,
        name_package=names_package(engine, owner, corrected=True),
        original_package={
            "publication_key": "19x19-batch-0ef14d803cd49221b37f4648",
            "manifest_sha256": "c" * 64,
            "home_batch_id": 1438,
            "home_receipt_sha256": "d" * 64,
            "home_report_sha256": "e" * 64,
            "queue_phase": "prod_publish",
        },
    )


def prepared(engine):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = correction.prepare_correction(engine, **inputs(engine))
    plan["final_approval"] = {
        "producer_id": "operator-producer",
        "producer_model": "gpt-6.1-sol",
        "reviewer_id": "independent-final-reviewer",
        "reviewer_model": "gpt-6-astra",
        "reviewed_at": WHEN,
        "decision": "approve_exact_canonical_correction",
        "content_sha256": plan["content_sha256"],
    }
    return plan


def state(engine):
    with engine.connect() as conn:
        return {
            model.__tablename__: [
                repair._json_image(dict(r))
                for r in conn.execute(select(model.__table__).order_by(model.__table__.c.id)).mappings()
            ]
            for model in (
                m.KifuPlayer,
                m.KifuPlayerAlias,
                m.KifuPlayerName,
                m.KifuNameResearchEvidence,
                m.KifuNameBatch,
                m.KifuNameChange,
                m.KifuAlbum,
                m.KifuAlbumSource,
                m.KifuAlbumRankSnapshot,
                m.KifuPlayerRankHistory,
            )
        }


def test_readonly_prepare_and_atomic_same_id_correction(correction_engine):
    from katrain.web.kifu import numadate_canonical_correction as correction

    before = state(correction_engine)
    plan = prepared(correction_engine)
    assert state(correction_engine) == before
    assert len(plan["targets"]) == 2
    for target in plan["targets"]:
        old = target["snapshot_before"]["snapshot"]
        new = target["expected_snapshot"]
        assert correction._identity_neutral(old) == correction._identity_neutral(new)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    assert receipt["status"] == "applied"
    assert _owner(correction_engine)["canonical_name"] == NEW
    after = state(correction_engine)
    assert after["kifu_albums"] == before["kifu_albums"]
    assert after["kifu_album_sources"] == before["kifu_album_sources"]
    assert not after["kifu_player_rank_history"]
    assert len(after["kifu_name_research_evidence"]) == len(before["kifu_name_research_evidence"]) + 5
    assert (
        before["kifu_name_research_evidence"]
        == after["kifu_name_research_evidence"][: len(before["kifu_name_research_evidence"])]
    )
    assert {r["lang"]: r["display_name"] for r in after["kifu_player_names"] if r["player_id"] == 5364} == DISPLAYS
    assert all(r["revision"] == 2 for r in after["kifu_player_names"] if r["player_id"] == 5364)
    with correction_engine.connect() as conn:
        proof = correction.verify_correction(conn, receipt["batch_id"])
        assert set(proof["rows"]) == {186520, 233062}
    assert correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan)) == receipt
    assert state(correction_engine) == after


def legacy_manifest(engine):
    with engine.connect() as conn:
        artifact = conn.scalar(select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == 876))
        manifest = deepcopy(artifact["logical_manifest"])
        manifest["games"][0]["sgf_content"] = conn.scalar(
            select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == 178495)
        )
        return manifest


@pytest.mark.parametrize(
    "drift",
    [
        "player",
        "alias",
        "collision",
        "source",
        "body",
        "old_repair",
        "old_journal",
        "old_evidence",
        "native_rank",
        "new_slot",
        "new_fact",
    ],
)
def test_apply_refuses_frozen_dependency_drift_without_writes(correction_engine, drift):
    from katrain.web.kifu import numadate_canonical_correction as correction

    engine = correction_engine
    plan = prepared(engine)
    with engine.begin() as conn:
        if drift == "player":
            conn.execute(update(m.KifuPlayer).where(m.KifuPlayer.id == 5364).values(canonical_name="Different"))
        elif drift == "alias":
            conn.execute(update(m.KifuPlayerAlias).where(m.KifuPlayerAlias.id == 58).values(alias="Different"))
        elif drift == "collision":
            conn.execute(m.KifuPlayerAlias.__table__.insert().values(player_id=42, alias=OLD, normalized_alias=OLD))
        elif drift == "source":
            conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 124026).values(black_rank="三段"))
        elif drift == "body":
            conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 124026).values(sgf_content="(;PB[Different])"))
        elif drift == "old_repair":
            artifact = deepcopy(plan["targets"][0]["old_authority"]["batch"]["reviewed_artifact"])
            artifact["part"]["code_sha256"] = "f" * 64
            conn.execute(update(m.KifuNameBatch).where(m.KifuNameBatch.id == 2189).values(reviewed_artifact=artifact))
        elif drift == "old_journal":
            conn.execute(
                update(m.KifuNameChange).where(m.KifuNameChange.batch_id == 2189).values(before_image={"id": 1})
            )
        elif drift == "old_evidence":
            conn.execute(
                update(m.KifuNameResearchEvidence)
                .where(m.KifuNameResearchEvidence.id == plan["old_names"][0]["evidence"]["id"])
                .values(review_status="rejected")
            )
        elif drift == "native_rank":
            artifact = conn.scalar(select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == 876))
            artifact["rank_bindings"] = []
            conn.execute(update(m.KifuNameBatch).where(m.KifuNameBatch.id == 876).values(reviewed_artifact=artifact))
        elif drift == "new_slot":
            conn.execute(
                m.KifuAlbum.__table__.insert().values(
                    id=999999,
                    player_black=NEW,
                    player_white="Other",
                    black_player_id=5364,
                    sgf_content="(;PB[沼馆沙辉哉])",
                    source_path="synthetic-extra.sgf",
                )
            )
        else:
            from datetime import datetime, timezone

            conn.execute(
                m.KifuPlayerRankHistory.__table__.insert().values(
                    player_id=5364,
                    rank_value=7,
                    rank_system="professional_dan",
                    observed_at=datetime.now(timezone.utc),
                    source_kind="synthetic",
                    source_ref={},
                    evidence={},
                    content_sha256="f" * 64,
                    status="qualified",
                    is_current=False,
                )
            )
    before = state(engine)
    with pytest.raises(ValueError):
        correction.apply_correction(engine, plan, expected_sha256=digest(plan))
    assert state(engine) == before


@pytest.mark.parametrize(
    "field",
    [
        "rank_value",
        "rank_system",
        "qualification",
        "basis",
        "identity_review",
        "final_review",
        "database",
        "source_owner",
    ],
)
def test_self_consistent_hash_does_not_authorize_changed_plan(correction_engine, field):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    if field in {"rank_value", "rank_system"}:
        plan["targets"][0]["expected_snapshot"][field] = 9 if field == "rank_value" else "professional_dan"
        plan["targets"][0]["expected_snapshot"]["content_sha256"] = ranks.snapshot_digest(
            plan["targets"][0]["expected_snapshot"]
        )
    elif field == "qualification":
        plan["targets"][0]["expected_snapshot"]["qualification"]["grade_decrease"] = True
        plan["targets"][0]["expected_snapshot"]["content_sha256"] = ranks.snapshot_digest(
            plan["targets"][0]["expected_snapshot"]
        )
    elif field == "basis":
        plan["targets"][0]["expected_snapshot"]["basis"] = [{}]
    elif field == "identity_review":
        plan["identity_review"]["source_items"] = ["91342440"]
    elif field == "final_review":
        plan["final_approval"]["reviewer_id"] = plan["final_approval"]["producer_id"]
    elif field == "database":
        plan["database_identity"]["database_sha256"] = "f" * 64
    else:
        plan["owner_before"]["id"] = 11140
    plan["identity_transition_sha256"] = correction._transition(plan)
    plan["content_sha256"] = correction._content_sha(plan)
    plan["final_approval"]["content_sha256"] = plan["content_sha256"]
    before = state(correction_engine)
    with pytest.raises(ValueError):
        correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    assert state(correction_engine) == before


def test_name_failure_rolls_back_player_alias_both_snapshots_and_both_batches(correction_engine, monkeypatch):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    before = state(correction_engine)
    original = name_batch._apply_candidate

    def fail(conn, row, *args, **kwargs):
        if row["lang"] == "en":
            raise ValueError("synthetic name failure")
        return original(conn, row, *args, **kwargs)

    monkeypatch.setattr(name_batch, "_apply_candidate", fail)
    with pytest.raises(ValueError, match="synthetic name failure"):
        correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    assert state(correction_engine) == before


@pytest.mark.parametrize(
    "tamper",
    [
        "owner_journal",
        "snapshot_journal",
        "old_authority",
        "child_binding",
        "child_status",
        "native_receipt",
        "basis_binding",
        "malformed_plan",
    ],
)
def test_read_verifier_refuses_corrupt_authority_with_selects_only(correction_engine, tamper):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    with correction_engine.begin() as conn:
        if tamper in {"owner_journal", "snapshot_journal"}:
            seq = 1 if tamper == "owner_journal" else 3
            conn.execute(
                update(m.KifuNameChange)
                .where(m.KifuNameChange.batch_id == receipt["batch_id"], m.KifuNameChange.sequence == seq)
                .values(before_image=None)
            )
        elif tamper == "old_authority":
            conn.execute(update(m.KifuNameChange).where(m.KifuNameChange.batch_id == 2189).values(before_image={}))
        elif tamper in {"child_binding", "child_status"}:
            artifact = conn.scalar(
                select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == receipt["child_batch_id"])
            )
            artifact.pop("canonical_correction_parent")
            conn.execute(
                update(m.KifuNameBatch)
                .where(m.KifuNameBatch.id == receipt["child_batch_id"])
                .values(reviewed_artifact=artifact, **({"status": "undone"} if tamper == "child_status" else {}))
            )
        else:
            target_id = 876 if tamper == "native_receipt" else receipt["batch_id"]
            artifact = conn.scalar(select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == target_id))
            if tamper == "native_receipt":
                artifact["receipt"]["status"] = "changed"
            elif tamper == "basis_binding":
                artifact["basis_bindings"][0]["target"]["player_id"] = 42
            else:
                artifact["plan"]["targets"] = None
            conn.execute(
                update(m.KifuNameBatch).where(m.KifuNameBatch.id == target_id).values(reviewed_artifact=artifact)
            )
    before = state(correction_engine)
    statements = []

    def observe(conn, cursor, statement, *args):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(correction_engine, "before_cursor_execute", observe)
    try:
        with correction_engine.connect() as conn, pytest.raises(ValueError):
            correction.verify_correction(conn, receipt["batch_id"])
    finally:
        event.remove(correction_engine, "before_cursor_execute", observe)
    assert statements and set(statements) == {"SELECT"}
    assert state(correction_engine) == before


def test_apply_and_both_generic_undo_paths_preserve_original_native876(correction_engine):
    from katrain.web.kifu import numadate_canonical_correction as correction
    from tests.web_ui.test_kifu_incremental_catalog import publish

    legacy = legacy_manifest(correction_engine)
    before = state(correction_engine)
    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    applied = state(correction_engine)
    original = next(b["reviewed_artifact"]["receipt"] for b in before["kifu_name_batches"] if b["id"] == 876)
    assert publish(correction_engine, legacy) == original
    assert state(correction_engine) == applied
    for batch_id in (receipt["batch_id"], receipt["child_batch_id"]):
        for emergency in (False, True):
            with pytest.raises(ValueError, match="undo|correction"):
                name_batch.undo_batch(correction_engine, batch_id, emergency_invalidate_search=emergency)
            assert state(correction_engine) == applied


def test_read_verifier_uses_callers_shared_source_budget_and_cache(correction_engine):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    with correction_engine.connect() as conn:
        with pytest.raises(ValueError, match="resource|budget"):
            correction.verify_correction(conn, receipt["batch_id"], resource=ranks.EvidenceBudget(max_bytes=0))
        resource = ranks.EvidenceBudget(max_bytes=512 * 1024)
        correction.verify_correction(conn, receipt["batch_id"], resource=resource)
        used = resource.used_bytes
        assert used == sum(
            len(conn.scalar(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == ident)).encode())
            for ident in (124026, 178495)
        )
        correction.verify_correction(conn, receipt["batch_id"], resource=resource)
        assert resource.used_bytes == used


def test_postcommit_search_failure_recovers_original_child_without_business_repetition(correction_engine, monkeypatch):
    from katrain.web.kifu import numadate_canonical_correction as correction, search_sync
    from tests.web_ui.test_kifu_search_publication import ES

    engine = correction_engine
    with engine.begin() as conn:
        # A raw-derived search member remains unlinked throughout correction.
        conn.execute(
            m.KifuAlbum.__table__.insert().values(
                id=999998,
                player_black=OLD,
                player_white="Other",
                event="Summer Cup",
                sgf_content=f"(;PB[{OLD}]PW[Other]EV[Summer Cup])",
                source_path="synthetic-unlinked.sgf",
            )
        )
        conn.execute(
            m.KifuRawPlayerValue.__table__.insert().values(
                id=143, raw_value=OLD, category="readable_unlinked", review_status="pending"
            )
        )
    plan = prepared(engine)
    es = ES()
    es.fail_bulk = True
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    monkeypatch.setattr(search_sync, "_writer_client", lambda: es)
    child_sha = digest(plan["name_package"]["bundle"])
    with pytest.raises(search_sync.SearchIndexPending) as error:
        correction.apply_correction(engine, plan, expected_sha256=digest(plan))
    assert error.value.operation_ref == {"bundle_sha256": child_sha}
    assert es.state["status"] == "pending"
    assert es.state["operation_type"] == "name_apply"
    assert es.state["operation_ref"] == {"bundle_sha256": child_sha}
    committed = state(engine)
    assert _owner(engine)["canonical_name"] == NEW
    with engine.connect() as conn:
        parent_id = conn.scalar(select(m.KifuNameBatch.id).where(m.KifuNameBatch.bundle_sha256 == digest(plan)))
        child_id = conn.scalar(select(m.KifuNameBatch.id).where(m.KifuNameBatch.bundle_sha256 == child_sha))
        receipt = correction.verify_correction(conn, parent_id)["receipt"]
        scope = search_sync._batch_scope(conn, child_id)
        scope = search_sync._expand_scope(conn, scope)
        assert ("player", 5364) in scope.owners
        assert {124026, 178495} <= scope.album_ids
        assert ("player", 42) in scope.owners
        assert "Other".lower() in scope.terms
        assert {OLD, NEW} <= scope.terms
        assert conn.scalar(select(m.KifuAlbum.black_player_id).where(m.KifuAlbum.id == 999998)) is None
    es.fail_bulk = False
    search_sync.recover_pending(engine)
    assert es.state["status"] == "ready"
    assert {"album:124026", "album:178495"} <= {a["_id"] for a in es.actions}
    docs = {a["_id"]: a["_source"] for a in es.actions if "_source" in a}
    assert docs["album:124026"]["display"]["cn"]["player_black"] == NEW
    assert docs["album:178495"]["display"]["jp"]["player_white"] == DISPLAYS["jp"]
    assert state(engine) == committed
    assert correction.apply_correction(engine, plan, expected_sha256=digest(plan)) == receipt
    assert state(engine) == committed


def test_preparation_rejects_oversized_selected_native_game_before_fetch(correction_engine):
    from katrain.web.kifu import numadate_canonical_correction as correction

    with correction_engine.begin() as conn:
        artifact = conn.scalar(select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == 876))
        artifact["logical_manifest"]["games"][0]["oversized_capture"] = "x" * (512 * 1024)
        conn.execute(update(m.KifuNameBatch).where(m.KifuNameBatch.id == 876).values(reviewed_artifact=artifact))
    queries = []

    def observe(conn, cursor, statement, *args):
        queries.append(statement)

    event.listen(correction_engine, "before_cursor_execute", observe)
    try:
        with pytest.raises(ValueError, match="resource"):
            correction.prepare_correction(correction_engine, **inputs(correction_engine))
    finally:
        event.remove(correction_engine, "before_cursor_execute", observe)
    assert not any(q.startswith("SELECT g.value FROM") for q in queries)


def test_cli_rejects_sqlite_target_and_private_inputs_are_bounded(tmp_path, monkeypatch, capsys):
    from scripts import correct_kifu_numadate as cli
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///:memory:")
    assert cli.main(["apply", "--plan", str(tmp_path / "unused"), "--expected-sha256", "a" * 64]) == 2
    assert "sqlite" not in capsys.readouterr().err.lower()
    huge = tmp_path / "huge.json"
    with huge.open("wb") as handle:
        handle.truncate(12 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="resource"):
        cli._read(huge)
    with pytest.raises(SystemExit):
        cli.main(["undo"])


def test_disposable_postgresql_readonly_binder_restores_timeout_and_takes_no_writer_locks(
    correction_engine, monkeypatch
):
    """Reuse the project's opt-in disposable PostgreSQL boundary, never PROD."""
    import os
    from uuid import uuid4
    from sqlalchemy import text
    from katrain.web.kifu import numadate_canonical_correction as correction

    dsn = os.getenv("KIFU_STANDARDIZATION_TEST_PG_DSN") or os.getenv("KIFU_RANK_TEST_POSTGRES")
    if not dsn:
        pytest.skip("set disposable PostgreSQL test DSN for RR READ ONLY binder verification")
    admin = create_engine(dsn, echo=False, hide_parameters=True)
    assert admin.url.database != correction.PROD_DATABASE
    schema = "numadate_readonly_" + uuid4().hex
    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    with correction_engine.connect() as conn:
        artifact = conn.scalar(
            select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == receipt["batch_id"])
        )
        copies = {
            model: [dict(r) for r in conn.execute(select(model.__table__)).mappings()]
            for model in (m.KifuPlayer, m.KifuPlayerAlias, m.KifuSource, m.KifuAlbum, m.KifuAlbumSource)
        }
    try:
        with admin.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        pg = admin.execution_options(schema_translate_map={None: schema})
        m.Base.metadata.create_all(pg)
        with pg.begin() as conn:
            for model, rows in copies.items():
                conn.execute(model.__table__.insert(), rows)
        readonly = pg.execution_options(isolation_level="REPEATABLE READ")
        statements = []

        def observe(conn, cursor, statement, *args):
            statements.append(statement)

        event.listen(admin, "before_cursor_execute", observe)
        try:
            with readonly.connect() as conn:
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql("SET LOCAL statement_timeout='4321ms'")
                assert conn.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on"
                resource = ranks.EvidenceBudget(max_bytes=512 * 1024)
                live = correction._live_targets(conn, correction._Budget(), resource=resource)
                bindings = [
                    ranks.bind_rank_decision(conn, t, p["expected_snapshot"], lock=False, resource=resource)
                    for (t, _, _), p in zip(live, plan["targets"])
                ]
                assert bindings == artifact["basis_bindings"]
                assert conn.exec_driver_sql("SHOW statement_timeout").scalar_one() == "4321ms"

                def proof_queries(connection, *_args, **_kwargs):
                    assert connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on"
                    assert connection.exec_driver_sql("SHOW statement_timeout").scalar_one() == "5s"
                    assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
                    return "bounded proof"

                with monkeypatch.context() as patch:
                    patch.setattr(correction, "_verify_correction", proof_queries)
                    assert correction.verify_correction(conn, 0) == "bounded proof"
                    assert conn.exec_driver_sql("SHOW statement_timeout").scalar_one() == "4321ms"

                    def refuse(connection, *args, **kwargs):
                        proof_queries(connection, *args, **kwargs)
                        raise ValueError("synthetic bounded proof refusal")

                    patch.setattr(correction, "_verify_correction", refuse)
                    with pytest.raises(ValueError, match="synthetic bounded proof refusal"):
                        correction.verify_correction(conn, 0)
                    assert conn.exec_driver_sql("SHOW statement_timeout").scalar_one() == "4321ms"
                conn.rollback()
        finally:
            event.remove(admin, "before_cursor_execute", observe)
        assert any("SAVEPOINT" in sql for sql in statements)
        assert not any(
            sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "LOCK"}
            or "FOR UPDATE" in sql.upper()
            or "pg_advisory" in sql
            for sql in statements
        )
    finally:
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        admin.dispose()


def test_transaction_helper_refuses_postgresql_without_repeatable_read_readonly(correction_engine):
    from types import SimpleNamespace
    from katrain.web.kifu import numadate_canonical_correction as correction

    fake = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), get_isolation_level=lambda: "READ COMMITTED")
    with pytest.raises(ValueError, match="REPEATABLE READ"):
        correction.prepare_in_transaction(fake, **inputs(correction_engine))


@pytest.mark.parametrize("correction_engine", ["一段"], indirect=True)
def test_opposite_side_real_b009_snapshots_do_not_expand_correction_admission(correction_engine):
    from katrain.web.kifu import numadate_canonical_correction as correction

    with correction_engine.begin() as conn:
        manifest = repair.prepare_manifest(conn, matched_at="2026-11-03T02:00:00+00:00", album_ids=[124026, 178495])
        assert len(manifest["parts"]) == 1
        part = manifest["parts"][0]
        assert {(c["album_id"], c["side"]) for c in part["changes"]} == {(124026, "white"), (178495, "black")}
        repair.apply_in_transaction(conn, part, expected_sha256=digest(part))
    original = state(correction_engine)
    opposite = [row for row in original["kifu_album_rank_snapshots"] if row["id"] not in {186520, 233062}]
    assert len(opposite) == 2
    plan = prepared(correction_engine)
    correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    current = state(correction_engine)
    assert [r for r in current["kifu_album_rank_snapshots"] if r["id"] not in {186520, 233062}] == opposite
    opposite_batch = opposite[0]["native_batch_id"]
    assert [r for r in original["kifu_name_changes"] if r["batch_id"] == opposite_batch] == [
        r for r in current["kifu_name_changes"] if r["batch_id"] == opposite_batch
    ]


@pytest.mark.parametrize("target", ["evidence", "name"])
def test_current_name_material_is_size_guarded_before_whole_row_fetch(correction_engine, target):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    with correction_engine.begin() as conn:
        name = dict(
            conn.execute(
                select(m.KifuPlayerName.__table__).where(
                    m.KifuPlayerName.player_id == 5364, m.KifuPlayerName.lang == "cn"
                )
            )
            .mappings()
            .one()
        )
        model, row_id = (
            (m.KifuNameResearchEvidence, name["evidence_id"])
            if target == "evidence"
            else (m.KifuPlayerName, name["id"])
        )
        values = (
            {"research_payload": {"oversized": "x" * (correction.MAX_NAME_BYTES + 1)}}
            if target == "evidence"
            else {"reference_url": "x" * (correction.MAX_NAME_BYTES + 1)}
        )
        conn.execute(update(model).where(model.id == row_id).values(**values))
    fetched = []
    prefix = f"SELECT {model.__tablename__}.id,"

    def observe(conn, cursor, statement, parameters, *args):
        if (
            statement.lstrip().startswith(prefix)
            and row_id in parameters
            and all(
                f"{model.__tablename__}.{column.name}" in statement.split("FROM", 1)[0] for column in model.__table__.c
            )
        ):
            fetched.append(statement)

    event.listen(correction_engine, "before_cursor_execute", observe)
    try:
        with correction_engine.connect() as conn, pytest.raises(ValueError, match="resource|budget"):
            correction.verify_correction(conn, receipt["batch_id"])
    finally:
        event.remove(correction_engine, "before_cursor_execute", observe)
    assert fetched == []


def test_public_verifier_bounds_every_proof_select_and_exits_context_on_refusal(correction_engine, monkeypatch):
    from contextlib import contextmanager
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    state = {"depth": 0}
    depths = []

    @contextmanager
    def bounded(conn):
        state["depth"] += 1
        try:
            yield
        finally:
            state["depth"] -= 1

    def observe(conn, cursor, statement, *args):
        if statement.lstrip().startswith("SELECT"):
            depths.append(state["depth"])

    monkeypatch.setattr(ranks, "_bounded_queries", bounded)
    event.listen(correction_engine, "before_cursor_execute", observe)
    try:
        with correction_engine.connect() as conn:
            correction.verify_correction(conn, receipt["batch_id"])
            assert state["depth"] == 0
            with pytest.raises(ValueError):
                correction.verify_correction(conn, -1)
            assert state["depth"] == 0
    finally:
        event.remove(correction_engine, "before_cursor_execute", observe)
    assert depths and min(depths) >= 1


@pytest.mark.parametrize("change", ["album_id", "rank_fact_id", "side", "snapshot", "publication_key", "missing_field"])
def test_supplied_rows_require_every_real_snapshot_column(correction_engine, change):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    with correction_engine.connect() as conn:
        row = dict(
            conn.execute(select(m.KifuAlbumRankSnapshot.__table__).where(m.KifuAlbumRankSnapshot.id == 186520))
            .mappings()
            .one()
        )
        # Readers add joined metadata; it does not substitute for real base fields.
        row["_joined_metadata"] = {"album_id": "untrusted extra"}
        assert (
            correction.verify_correction(conn, receipt["batch_id"], expected_rows=[row])["batch_id"]
            == receipt["batch_id"]
        )
        altered = deepcopy(row)
        if change == "missing_field":
            altered.pop("rank_fact_id")
        elif change == "snapshot":
            altered["snapshot"]["raw_name"] = "Different"
        else:
            altered[change] = {"album_id": 999, "rank_fact_id": 123, "side": "white", "publication_key": "changed"}[
                change
            ]
        with pytest.raises(ValueError, match="supplied current rows"):
            correction.verify_correction(conn, receipt["batch_id"], expected_rows=[altered])


def test_applied_read_proof_retains_historical_operator_pin_while_apply_requires_running_code(
    correction_engine, monkeypatch
):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    original = state(correction_engine)
    monkeypatch.setattr(correction, "operator_code_sha256", lambda: "f" * 64)
    with correction_engine.connect() as conn:
        assert correction.verify_correction(conn, receipt["batch_id"])["receipt"] == receipt
    with pytest.raises(ValueError, match="operator code changed"):
        correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    assert state(correction_engine) == original


def test_live_name_budget_uses_same_player_language_predicate_as_normal_qualifier(correction_engine):
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    with correction_engine.begin() as conn:
        original = dict(
            conn.execute(
                select(m.KifuPlayerName.__table__).where(
                    m.KifuPlayerName.player_id == 5364, m.KifuPlayerName.lang == "cn"
                )
            )
            .mappings()
            .one()
        )
        conn.execute(m.KifuPlayer.__table__.insert().values(id=7777, canonical_name="Different"))
        conn.execute(update(m.KifuPlayerName).where(m.KifuPlayerName.id == original["id"]).values(player_id=7777))
        replacement = {key: value for key, value in original.items() if key != "id"}
        replacement["reference_url"] = "x" * (correction.MAX_NAME_BYTES + 1)
        replacement_id = conn.execute(m.KifuPlayerName.__table__.insert().values(**replacement)).inserted_primary_key[0]
    fetched = []

    def observe(conn, cursor, statement, parameters, *args):
        if (
            statement.lstrip().startswith("SELECT kifu_player_names.id,")
            and replacement_id in parameters
            and "kifu_player_names.reference_url" in statement.split("FROM", 1)[0]
        ):
            fetched.append(statement)

    event.listen(correction_engine, "before_cursor_execute", observe)
    try:
        with correction_engine.connect() as conn, pytest.raises(ValueError, match="resource|budget"):
            correction.verify_correction(conn, receipt["batch_id"])
    finally:
        event.remove(correction_engine, "before_cursor_execute", observe)
    assert fetched == []


@pytest.mark.parametrize("action,expected_status", [("verify", 0), ("apply", 2)])
def test_cli_historical_read_pin_does_not_relax_apply(
    correction_engine, monkeypatch, tmp_path, capsys, action, expected_status
):
    """Exercise CLI dispatch against real applied evidence through a test transport."""
    import json
    from types import SimpleNamespace
    from scripts import correct_kifu_numadate as cli
    from katrain.web.kifu import numadate_canonical_correction as correction

    plan = prepared(correction_engine)
    receipt = correction.apply_correction(correction_engine, plan, expected_sha256=digest(plan))
    before = state(correction_engine)
    path = tmp_path / "approved-private-plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False))
    path.chmod(0o600)
    # The CLI's production dialect gate is separately tested; this adapter keeps
    # its branch/readonly transaction and full proof on the disposable fixture DB.
    transport = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        url=SimpleNamespace(database=correction.PROD_DATABASE),
        connect=correction_engine.connect,
        dispose=lambda: None,
    )
    monkeypatch.setattr(cli, "create_engine", lambda *args, **kwargs: transport)
    monkeypatch.setattr(correction, "operator_code_sha256", lambda: "f" * 64)
    assert cli.main([action, "--plan", str(path), "--expected-sha256", digest(plan)]) == expected_status
    output = capsys.readouterr()
    if action == "verify":
        assert json.loads(output.out) == receipt
        assert output.err == ""
    else:
        assert output.out == ""
        assert "refused" in output.err
    assert state(correction_engine) == before


@pytest.mark.parametrize(
    "publication_key,accepted",
    [
        ("19x19-batch-0ef14d803cd49221b37f4648", True),
        ("19x19-0ef14d803cd49221b37f4648", False),
    ],
)
def test_original_package_requires_exact_published_batch_key(correction_engine, publication_key, accepted):
    from katrain.web.kifu import numadate_canonical_correction as correction

    arguments = inputs(correction_engine)
    arguments["original_package"]["publication_key"] = publication_key
    frozen_package = deepcopy(arguments["original_package"])
    before = state(correction_engine)
    if accepted:
        plan = correction.prepare_correction(correction_engine, **arguments)
        assert plan["original_package"] == frozen_package
    else:
        with pytest.raises(ValueError, match="original frozen publication pins"):
            correction.prepare_correction(correction_engine, **arguments)
    assert state(correction_engine) == before
