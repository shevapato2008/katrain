"""Request-local proof reuse still observes refreshed mutable dependencies."""

from copy import deepcopy

import pytest
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuNameBatch, KifuPlayer, KifuPlayerName, KifuNameResearchEvidence
from katrain.web.kifu import name_candidates, name_orthographic, name_transliteration
from katrain.web.kifu.identity import _approved_names, _qualified_name_rows, strict_matching_names, strict_display_maps
from katrain.web.kifu.name_batch import apply_bundle
from tests.web_ui.test_kifu_name_batch import engine, registry
from tests.web_ui.test_kifu_name_first_pass import bound_player_bundle, bound_shared_raw_event_bundle


@pytest.fixture(autouse=True)
def clear_compiled_first_pass_cache():
    from katrain.web.kifu.compiled_first_pass import _CACHE

    _CACHE.clear()
    yield
    _CACHE.clear()


def read_player(db, contexts):
    return _qualified_name_rows(
        db,
        _approved_names(db, KifuPlayerName, "player_id", {17}, "cn"),
        KifuPlayerName,
        "player_id",
        orthographic_batch_contexts=contexts,
    )


def test_uncached_proof_groups_do_not_load_two_orthographic_artifacts_together(monkeypatch):
    from katrain.web.kifu import identity
    from tests.web_ui.test_kifu_name_orthographic import fixture
    from tests.web_ui.test_kifu_name_transliteration import registry as orthographic_registry

    engine, bundle, anchors, inventory = fixture()
    try:
        applied = apply_bundle(engine, bundle, orthographic_registry(), inventory, anchors)
        with Session(engine) as db:
            first = db.query(KifuPlayerName).one()
            evidence = db.get(KifuNameResearchEvidence, first.evidence_id)
            original = db.get(KifuNameBatch, applied["batch_id"])
            artifact = deepcopy(original.reviewed_artifact)
            artifact["bundle"]["independent_packet_probe"] = True
            second = KifuNameBatch(
                bundle_sha256=name_candidates.canonical_sha256(artifact["bundle"]),
                inventory_sha256=original.inventory_sha256,
                source_registry_id=original.source_registry_id,
                reviewed_artifact=artifact,
                status="applied",
            )
            db.add_all([KifuPlayer(id=18, canonical_name="Different owner"), second])
            db.flush()
            values = {
                column.name: getattr(evidence, column.name)
                for column in evidence.__table__.columns
                if column.name != "id"
            }
            values["player_id"] = 18
            values["candidate_name"] = "Different packet name"
            values["research_payload"] = deepcopy(values["research_payload"])
            values["research_payload"]["primary_orthographic"]["batch_id"] = second.id
            copied = KifuNameResearchEvidence(**values)
            db.add(copied)
            db.flush()
            db.add(
                KifuPlayerName(
                    player_id=18,
                    lang=first.lang,
                    display_name="Different packet name",
                    status="verified",
                    evidence_id=copied.id,
                    decision_kind=first.decision_kind,
                    generation_rule_version=first.generation_rule_version,
                    revision=first.revision,
                )
            )
            db.commit()
        original_build = name_orthographic.persisted_batch_bindings
        checked = []
        with Session(engine) as db:

            def build(batch):
                checked.append(batch.id)
                resident = [
                    row
                    for row in db.identity_map.values()
                    if isinstance(row, KifuNameBatch) and "reviewed_artifact" in row.__dict__
                ]
                assert len(resident) == 1
                return original_build(batch)

            monkeypatch.setattr(name_orthographic, "persisted_batch_bindings", build)
            monkeypatch.setattr(identity, "deepcopy", lambda value: pytest.fail("offline snapshot deepcopy"))
            names = {name_id for name_id, in db.query(KifuPlayerName.id)}
            qualified = []
            for group in identity.iter_name_proof_groups(db, KifuPlayerName, names):
                qualified.extend(
                    _qualified_name_rows(
                        db,
                        _approved_names(db, KifuPlayerName, "player_id").filter(KifuPlayerName.id.in_(group)),
                        KifuPlayerName,
                        "player_id",
                    )
                )
            assert len(checked) == 2 and len(set(checked)) == 2
            # The second packet is fully checked, then rejected for its different owner.
            assert [name.player_id for name, _evidence in qualified] == [17]
    finally:
        engine.dispose()


def test_first_pass_only_does_not_build_other_proof_families(engine, monkeypatch):
    inventory, bundle, research = bound_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    calls = []
    for module in (name_transliteration, name_orthographic):
        original = module.persisted_batch_bindings

        def observe(batch, *, original=original, family=module.__name__):
            calls.append(family)
            return original(batch)

        monkeypatch.setattr(module, "persisted_batch_bindings", observe)
    with Session(engine) as db:
        assert len(read_player(db, {})) == 1
    assert calls == []


def test_first_pass_reuses_bundle_and_member_digests_for_current_snapshot(engine, monkeypatch):
    inventory, bundle, research = bound_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    digests = {"bundle": 0, "member": 0}
    original = name_candidates.canonical_sha256

    def observe(value):
        if value == bundle:
            digests["bundle"] += 1
        elif value == bundle["candidates"][0]:
            digests["member"] += 1
        return original(value)

    monkeypatch.setattr(name_candidates, "canonical_sha256", observe)
    with Session(engine) as db:
        contexts = {}
        first = read_player(db, contexts)
        second = read_player(db, contexts)
        assert len(first) == len(second) == 1
    # Compile signed membership once, then hash each live candidate on every read.
    assert digests == {"bundle": 1, "member": 3}


@pytest.mark.parametrize(
    "drift, changed",
    [
        ("status", "undone"),
        ("bundle_sha256", "f" * 64),
        ("reviewed_artifact", {"changed": True}),
    ],
)
def test_first_pass_context_refreshes_held_batch(engine, drift, changed):
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        held = db.get(KifuNameBatch, applied["batch_id"])
        contexts = {}
        assert len(read_player(db, contexts)) == 1
        with engine.begin() as conn:
            conn.execute(
                KifuNameBatch.__table__.update().where(KifuNameBatch.id == held.id).values({drift: deepcopy(changed)})
            )
        assert read_player(db, contexts) == []
        assert getattr(held, drift) == changed


@pytest.mark.parametrize("target", ["owner", "evidence", "candidate", "candidate_json_number"])
def test_first_pass_context_rechecks_live_source_and_payload(engine, target):
    inventory, bundle, research = bound_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        held_owner = db.get(KifuPlayer, 17)
        contexts = {}
        first = read_player(db, contexts)
        evidence = first[0][1]
        with engine.begin() as conn:
            if target == "owner":
                conn.execute(
                    KifuPlayer.__table__.update().where(KifuPlayer.id == 17).values(canonical_name="Changed source")
                )
            else:
                payload = deepcopy(evidence.research_payload)
                if target == "evidence":
                    payload["first_pass"]["candidate_sha256"] = []
                elif target == "candidate_json_number":
                    payload["candidate"]["owner"]["id"] = 17.0
                else:
                    payload["candidate"]["unsigned_extra"] = True
                conn.execute(
                    KifuNameResearchEvidence.__table__.update()
                    .where(KifuNameResearchEvidence.id == evidence.id)
                    .values(research_payload=payload)
                )
        assert read_player(db, contexts) == []
        if target == "owner":
            assert held_owner.canonical_name == "Changed source"


@pytest.mark.parametrize("original, changed", [(17, 17.0), (True, 1), (0.0, -0.0)])
def test_first_pass_context_requires_canonical_batch_snapshot(engine, original, changed):
    inventory, bundle, research = bound_player_bundle(engine)
    bundle["json_number_probe"] = original
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        contexts = {}
        assert len(read_player(db, contexts)) == 1
        batch = db.get(KifuNameBatch, applied["batch_id"])
        artifact = deepcopy(batch.reviewed_artifact)
        artifact["bundle"]["json_number_probe"] = changed
        assert artifact == batch.reviewed_artifact
        assert name_candidates.canonical_sha256(artifact["bundle"]) != batch.bundle_sha256
        with engine.begin() as conn:
            conn.execute(
                KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch.id).values(reviewed_artifact=artifact)
            )
        assert read_player(db, contexts) == []


def test_dirty_session_does_not_reuse_first_pass_context(engine):
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine, autoflush=False) as db:
        contexts = {}
        assert len(read_player(db, contexts)) == 1
        held = db.get(KifuNameBatch, applied["batch_id"])
        held.reviewed_artifact = {"changed": True}
        assert read_player(db, contexts) == []
        assert held in db.dirty


def test_raw_event_search_and_display_share_members_but_recheck_scope(engine, monkeypatch):
    inventory, bundle, research = bound_shared_raw_event_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    digests = 0
    original = name_candidates.canonical_sha256

    def observe(value):
        nonlocal digests
        if value == bundle:
            digests += 1
        return original(value)

    monkeypatch.setattr(name_candidates, "canonical_sha256", observe)
    with Session(engine) as db:
        contexts = {}
        matches = strict_matching_names(db, "28th Honinbo Tournament", orthographic_batch_contexts=contexts)
        assert len(matches[3]) == 2
        albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_({12, 13})).all()
        maps = strict_display_maps(db, albums, "en", orthographic_batch_contexts=contexts)
        assert maps[5] == {
            (12, "28th Honinbo", None): "28th Honinbo Tournament",
            (13, "第28期本因坊战", None): "28th Honinbo Tournament",
        }
        with engine.begin() as conn:
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(list_hidden_reason="withdrawn"))
        assert (
            len(
                strict_matching_names(
                    db,
                    "28th Honinbo Tournament",
                    orthographic_batch_contexts=contexts,
                )[3]
            )
            == 1
        )
    assert digests == 1
