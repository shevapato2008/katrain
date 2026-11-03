"""The one-person canonical correction cannot authorize generic apply or undo."""

from copy import deepcopy

import pytest
from sqlalchemy import event, select

from katrain.web.core.models_db import KifuNameBatch, KifuNameChange, KifuNameResearchEvidence, KifuNameSourceRegistry
from katrain.web.kifu import name_batch
from katrain.web.kifu.name_candidates import canonical_sha256
from tests.web_ui.test_kifu_name_batch import engine
from tests.web_ui.test_kifu_numadate_canonical_correction import correction_engine


MARKER_VERSION = "numadate-canonical-first-pass-correction-v1"
PARENT_FORMAT = "kifu-numadate-canonical-correction-v1"


def _undo_fixture(engine, kind, status):
    marker_candidate = {
        "owner": {"kind": "player", "id": 5364},
        "lang": "cn",
        "first_pass_correction": {"version": MARKER_VERSION},
    }
    bundle = {"bundle_format": 1, "candidates": []}
    artifact = {"bundle": bundle}
    if kind == "parent":
        artifact = {"format": PARENT_FORMAT, "plan": {}, "receipt": {}}
    elif kind == "child":
        artifact["canonical_correction_parent"] = {
            "version": "numadate-canonical-correction-parent-v1",
            "parent_id": 42,
            "plan_sha256": "a" * 64,
            "identity_transition_sha256": "b" * 64,
            "player_id": 5364,
            "affected_album_ids": [124026, 178495],
        }
    elif kind == "corrupt_binding":
        artifact["canonical_correction_parent"] = None
    elif kind == "missing_binding":
        bundle["candidates"] = [marker_candidate]
    elif kind == "v4_missing_binding":
        bundle.update(bundle_format=4, candidates=[marker_candidate])
    with engine.begin() as conn:
        registry_id = conn.execute(
            KifuNameSourceRegistry.__table__.insert().values(version="numadate-test", sha256="c" * 64, registry={})
        ).inserted_primary_key[0]
        batch_id = conn.execute(
            KifuNameBatch.__table__.insert().values(
                bundle_sha256=canonical_sha256(bundle),
                inventory_sha256="d" * 64,
                source_registry_id=registry_id,
                reviewed_artifact=artifact,
                status=status,
            )
        ).inserted_primary_key[0]
        if kind == "journal_marker":
            conn.execute(
                KifuNameChange.__table__.insert().values(
                    batch_id=batch_id,
                    sequence=1,
                    target_table=KifuNameResearchEvidence.__tablename__,
                    target_row_id=123,
                    before_image=None,
                    after_image={"research_payload": {"candidate": marker_candidate}},
                )
            )
    return batch_id


@pytest.mark.parametrize(
    "kind", ["parent", "child", "corrupt_binding", "missing_binding", "v4_missing_binding", "journal_marker"]
)
@pytest.mark.parametrize("status", ["applied", "partial_undo", "undone"])
@pytest.mark.parametrize("emergency", [False, True])
def test_canonical_correction_undo_refuses_before_any_write(engine, kind, status, emergency):
    batch_id = _undo_fixture(engine, kind, status)
    with engine.connect() as conn:
        before = name_batch._image(conn, KifuNameBatch.__table__, batch_id)
        before_changes = [dict(row) for row in conn.execute(select(KifuNameChange.__table__)).mappings()]
    writes = []

    def record_write(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    event.listen(engine, "before_cursor_execute", record_write)
    try:
        with pytest.raises(name_batch.BatchError, match="canonical correction.*does not support undo"):
            name_batch.undo_batch(engine, batch_id, emergency_invalidate_search=emergency)
    finally:
        event.remove(engine, "before_cursor_execute", record_write)
    assert writes == []
    with engine.connect() as conn:
        assert name_batch._image(conn, KifuNameBatch.__table__, batch_id) == before
        assert [dict(row) for row in conn.execute(select(KifuNameChange.__table__)).mappings()] == before_changes


def _marker_candidate():
    return {
        "owner": {"kind": "player", "id": 5364},
        "lang": "cn",
        "display_name": "沼馆沙辉哉",
        "name_preimage_sha256": "a" * 64,
        "decision_kind": "generated",
        "generation_rule_version": "user_authorized_first_pass_v1",
        "review_status": "approved",
        "first_pass_correction": {
            "version": MARKER_VERSION,
            "player_id": 5364,
            "lang": "cn",
            "identity_transition_sha256": "b" * 64,
            "name_preimage_sha256": "a" * 64,
            "prior_evidence_id": 1,
            "prior_evidence_sha256": "c" * 64,
            "prior_candidate_sha256": "d" * 64,
            "prior_batch_id": 1,
            "prior_bundle_sha256": "e" * 64,
            "prior_revision": 1,
            "owner_before_sha256": "f" * 64,
            "owner_after_sha256": "0" * 64,
            "source_input_sha256": "1" * 64,
        },
    }


@pytest.mark.parametrize(
    "prior_proofs", [None, {}, {"_numadate_canonical_correction": {}}, {"_numadate_canonical_correction": object()}]
)
def test_numadate_marker_cannot_authorize_itself(prior_proofs):
    with pytest.raises(name_batch.BatchError, match="trusted.*correction context"):
        name_batch._check_first_pass_correction(object(), _marker_candidate(), {}, prior_proofs)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row["owner"].update(id=17),
        lambda row: row["owner"].update(kind="raw_player"),
        lambda row: row.update(lang="jp"),
        lambda row: row["first_pass_correction"].update(player_id=17),
        lambda row: row["first_pass_correction"].update(lang="ko"),
        lambda row: row["first_pass_correction"].update(prior_revision=True),
        lambda row: row["first_pass_correction"].update(source_input_sha256="invalid"),
        lambda row: row["first_pass_correction"].update(bypass=True),
        lambda row: row.update(generation_rule_version="generated-raw-player-semantic-correction-v1"),
        lambda row: row.update(review_status="pending"),
    ],
)
def test_numadate_marker_is_not_a_generic_player_locale_or_raw_correction(mutation):
    candidate = _marker_candidate()
    mutation(candidate)
    with pytest.raises(name_batch.BatchError, match="reviewed player5364 generated scope"):
        name_batch._check_first_pass_correction(object(), candidate, {}, {})


def _generic_marker_bundle(engine):
    from katrain.web.core.models_db import KifuPlayer, KifuPlayerName
    from katrain.web.kifu.name_evidence import registry_sha256
    from katrain.web.kifu.name_inventory import build_inventory
    from tests.web_ui.test_kifu_name_batch import bind_fixture_candidate, player_bundle, registry
    from tests.web_ui.test_kifu_name_first_pass import first_pass_pair

    owner = {"kind": "player", "id": 5364}
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=5364, canonical_name="沼馆沙辉哉"))
        name_id = conn.execute(
            KifuPlayerName.__table__.insert().values(
                player_id=5364, lang="cn", display_name="沼官沙辉哉", status="review", revision=1
            )
        ).inserted_primary_key[0]
        owner_image = name_batch._image(conn, KifuPlayer.__table__, 5364)
        name_image = name_batch._image(conn, KifuPlayerName.__table__, name_id)
    inv = build_inventory(engine)
    bundle, _ = player_bundle(inv)
    candidate, research = first_pass_pair()
    research.update(
        owner=owner,
        original_name="沼馆沙辉哉",
        candidate_name="沼馆沙辉哉",
        registry_sha256=registry_sha256(registry()),
    )
    research["source_input"].update(owner=owner, text="沼馆沙辉哉", owner_preimage_sha256=canonical_sha256(owner_image))
    candidate.update(
        owner=owner,
        display_name="沼馆沙辉哉",
        research_sha256=canonical_sha256(research),
        name_preimage_sha256=canonical_sha256(name_image),
    )
    candidate["generated_review"].update(
        owner=owner, display_name=candidate["display_name"], research_sha256=candidate["research_sha256"]
    )
    candidate["first_pass_correction"] = _marker_candidate()["first_pass_correction"]
    candidate["first_pass_correction"].update(
        name_preimage_sha256=candidate["name_preimage_sha256"],
        owner_after_sha256=canonical_sha256(owner_image),
        source_input_sha256=canonical_sha256(research["source_input"]),
    )
    bind_fixture_candidate(candidate)
    candidate["preimage_binding"].update(captured_at="2026-10-11T01:00:15Z", bound_at="2026-10-11T01:00:30Z")
    members = [{"owner": owner, "lang": "cn"}]
    owners = [{"owner": owner, "preimage": owner_image}]
    bundle.update(
        bundle_format=2,
        members=members,
        member_set_sha256=canonical_sha256(members),
        candidates=[candidate],
        owners=owners,
        owner_set_sha256=canonical_sha256(owners),
        catalog_sha256=name_batch.catalog_snapshot_sha(engine),
        album_links=[],
        link_set_sha256=canonical_sha256([]),
    )
    return inv, bundle, registry(), [research]


def test_generic_name_apply_refuses_numadate_marker_without_operator_context(engine):
    inv, bundle, registry, records = _generic_marker_bundle(engine)
    with pytest.raises(name_batch.BatchError, match="trusted.*correction context"):
        name_batch.apply_bundle(engine, bundle, registry, inv, records)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameBatch.id)) is None
        assert conn.scalar(select(KifuNameResearchEvidence.id)) is None


@pytest.mark.parametrize("field", ["owner_after_sha256", "source_input_sha256"])
def test_numadate_generated_source_pins_the_new_owner_input(engine, field):
    _inv, bundle, _registry, records = _generic_marker_bundle(engine)
    candidate = bundle["candidates"][0]
    candidate["first_pass_correction"][field] = "2" * 64
    with (
        engine.connect() as conn,
        pytest.raises(name_batch.BatchError, match="generated source differs from the new owner"),
    ):
        name_batch._check_first_pass_sources(
            conn, [candidate], {canonical_sha256(records[0]): records[0]}, bundle["owners"]
        )


def test_internal_name_writer_refuses_numadate_marker_without_operator_context(engine):
    _inv, bundle, registry, records = _generic_marker_bundle(engine)
    with engine.begin() as conn, pytest.raises(name_batch.BatchError, match="trusted.*correction context"):
        name_batch._apply_candidate(
            conn, bundle["candidates"][0], {canonical_sha256(records[0]): records[0]}, 1, 1, 1, registry=registry
        )
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameResearchEvidence.id)) is None
        assert conn.scalar(select(KifuNameChange.id)) is None


@pytest.mark.parametrize("drift", ["connection", "evidence", "creation_journal"])
def test_real_operator_context_binds_connection_and_rechecks_old_proof(correction_engine, monkeypatch, drift):
    from katrain.web.kifu import numadate_canonical_correction as correction
    from tests.web_ui.test_kifu_numadate_canonical_correction import prepared, state

    before = state(correction_engine)
    plan = prepared(correction_engine)
    original = name_batch._apply_candidate
    inspected = []

    def check_context(conn, row, *args, **kwargs):
        if row.get("lang") != "cn":
            return original(conn, row, *args, **kwargs)
        proofs, registry = kwargs["prior_proofs"], kwargs["registry"]
        # Only the real operator may create the context exercised here.
        name_batch._check_name_preimages(conn, [row], registry, proofs)
        marker = row["first_pass_correction"]
        if drift == "connection":
            with (
                correction_engine.connect() as another_conn,
                pytest.raises(name_batch.BatchError, match="trusted.*correction context"),
            ):
                name_batch._check_first_pass_correction(another_conn, row, registry, proofs)
        else:
            if drift == "evidence":
                conn.execute(
                    KifuNameResearchEvidence.__table__.update()
                    .where(KifuNameResearchEvidence.id == marker["prior_evidence_id"])
                    .values(review_status="pending")
                )
            else:
                journal = (
                    conn.execute(
                        select(KifuNameChange.__table__).where(
                            KifuNameChange.batch_id == marker["prior_batch_id"],
                            KifuNameChange.target_table == KifuNameResearchEvidence.__tablename__,
                            KifuNameChange.target_row_id == marker["prior_evidence_id"],
                        )
                    )
                    .mappings()
                    .one()
                )
                changed = deepcopy(journal["after_image"])
                changed["review_status"] = "pending"
                conn.execute(
                    KifuNameChange.__table__.update()
                    .where(KifuNameChange.id == journal["id"])
                    .values(after_image=changed)
                )
            with pytest.raises(name_batch.BatchError, match="trusted.*correction context"):
                name_batch._check_first_pass_correction(conn, row, registry, proofs)
        inspected.append(drift)
        raise RuntimeError("context boundary probe complete")

    monkeypatch.setattr(name_batch, "_apply_candidate", check_context)
    with pytest.raises(RuntimeError, match="context boundary probe complete"):
        correction.apply_correction(correction_engine, plan, expected_sha256=canonical_sha256(plan))
    assert inspected == [drift]
    assert state(correction_engine) == before
