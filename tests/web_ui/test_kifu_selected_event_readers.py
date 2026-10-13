"""API, coverage and matching share the reviewed selected-event identity."""

import asyncio
from copy import deepcopy

from sqlalchemy import select
from katrain.web.core.models_db import KifuAlbum, KifuEvent, KifuEventName, KifuNameBatch
from katrain.web.kifu.name_candidates import identity_scope_sha256
from katrain.web.kifu.name_batch import catalog_snapshot_sha
from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
from tests.web_ui.test_kifu_name_batch import _eleven_language_identity_fixture, _identity_link, _v2_wrap
from tests.web_ui.test_kifu_name_api import _evidence

import pytest
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints import kifu
from katrain.web.kifu.identity import live_event_selections
from katrain.web.kifu.name_batch import apply_bundle
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_coverage import coverage_report
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.name_match import propose_album_matches
from tests.web_ui.test_kifu_name_api import _request
from tests.web_ui.test_kifu_name_batch import engine, selected_event_bundle


def _applied(engine):
    bundle, sources, inventory, research = selected_event_bundle(engine)
    applied = apply_bundle(
        engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle)
    )
    return applied


def _later_player_link(engine, album_ids=(11,), *, new=False, new_name="Unknown", new_suffix=" New"):
    inventory = build_inventory(engine, inventory_format=4)
    owner = {"kind": "player", "ref": "later-person"} if new else {"kind": "player", "id": 17}
    declaration = {"owner": owner, "create" if new else "preimage": {"canonical_name": new_name if new else "吴清源"}}
    bundle, research, sources = _eleven_language_identity_fixture(engine, inventory, [owner])
    if new:
        for candidate, record in zip(bundle["candidates"], research):
            display = candidate["display_name"] + new_suffix
            candidate["display_name"] = record["candidate_name"] = display
            for check in record["source_checks"]:
                check.update(candidate_name=display, body_excerpt=f"Official identity profile: {display}")
            candidate["research_sha256"] = canonical_sha256(record)
    bundle["inventory_format"] = 4
    links = [_identity_link(engine, inventory, album_id, "white", owner) for album_id in album_ids]
    for link in links:
        if link["expected"]["old_id"] is not None and owner.get("id") != link["expected"]["old_id"]:
            link["corrects_existing"] = True
    bundle = _v2_wrap(engine, inventory, bundle, [declaration], links)
    return apply_bundle(engine, bundle, sources, inventory, research), bundle


def _later_album_links(engine, declarations, slots, *, suffix=" Other"):
    inventory = build_inventory(engine, inventory_format=4)
    bundle, research, sources = _eleven_language_identity_fixture(
        engine, inventory, [declaration["owner"] for declaration in declarations]
    )
    for candidate, record in zip(bundle["candidates"], research):
        candidate["display_name"] += suffix
        record["candidate_name"] = candidate["display_name"]
        for check in record["source_checks"]:
            check.update(candidate_name=candidate["display_name"], body_excerpt=f"Identity: {candidate['display_name']}")
        candidate["research_sha256"] = canonical_sha256(record)
    links = [_identity_link(engine, inventory, album_id, slot, owner) for album_id, slot, owner in slots]
    for link in links:
        if link["expected"]["old_id"] is not None and link["target"].get("id") != link["expected"]["old_id"]:
            link["corrects_existing"] = True
    bundle["inventory_format"] = 4
    bundle = _v2_wrap(engine, inventory, bundle, declarations, links)
    return apply_bundle(engine, bundle, sources, inventory, research), bundle


def _off_page_album(engine, *, player_id=None, event_id=None):
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=20, canonical_name="Other Cup"))
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=12, player_black="Other", player_white="Unknown", event="Other Cup",
                sgf_content="(;PB[Other]PW[Unknown]EV[Other Cup])", source_path="other.sgf",
                white_player_id=player_id, event_id=event_id,
            )
        )


def _later_event_link(engine):
    owner = {"kind": "event", "ref": "later-event"}
    return _later_album_links(
        engine, [{"owner": owner, "create": {"canonical_name": "Later Cup"}}], [(12, "event", owner)],
        suffix=" Later",
    )


def test_reviewed_mixed_off_page_member_replays_one_complete_batch(engine):
    from katrain.web.kifu.name_batch import undo_batch

    _applied(engine)
    _off_page_album(engine)
    player, event = {"kind": "player", "id": 17}, {"kind": "event", "id": 20}
    applied, _ = _later_album_links(
        engine,
        [{"owner": player, "preimage": {"canonical_name": "吴清源"}},
         {"owner": event, "preimage": {"canonical_name": "Other Cup"}}],
        [(11, "white", player), (12, "white", player), (12, "event", event)],
    )
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    correction, _ = _later_event_link(engine)
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    assert undo_batch(engine, correction["batch_id"])["status"] == "undone"
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}


@pytest.mark.parametrize("order", [("event", "player"), ("player", "event")])
def test_reviewed_event_and_player_corrections_replay_in_order_and_undo(engine, order):
    from katrain.web.kifu.name_batch import undo_batch

    _applied(engine)
    _off_page_album(engine, player_id=17, event_id=20)
    _later_player_link(engine, (11, 12))
    corrections = []
    for kind in order:
        applied, _ = _later_event_link(engine) if kind == "event" else _later_player_link(engine, (12,), new=True)
        corrections.append(applied)
        with Session(engine) as db:
            assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    for applied in reversed(corrections):
        assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
        with Session(engine) as db:
            assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}


def test_event_noop_member_closes_later_history_and_rejects_direct_revert(engine):
    from katrain.web.kifu.name_batch import undo_batch

    _applied(engine)
    _off_page_album(engine, event_id=20)
    player, event = {"kind": "player", "id": 17}, {"kind": "event", "id": 20}
    _later_album_links(
        engine,
        [{"owner": player, "preimage": {"canonical_name": "吴清源"}},
         {"owner": event, "preimage": {"canonical_name": "Other Cup"}}],
        [(11, "white", player), (12, "event", event)],
    )
    correction, _ = _later_event_link(engine)
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    with engine.begin() as conn:
        original = conn.scalar(select(KifuAlbum.event_id).where(KifuAlbum.id == 12))
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(event_id=20))
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(event_id=original))
    assert undo_batch(engine, correction["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}


def test_unrelated_separate_event_batch_drift_keeps_selected_event_proof(engine):
    _applied(engine)
    _off_page_album(engine, event_id=20)
    _later_player_link(engine)
    _later_event_link(engine)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(event_id=20))
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}


@pytest.mark.parametrize("drift", ["direct_revert", "ledger_before", "ledger_after", "bundle", "sgf"])
def test_event_history_drift_invalidates_connected_atomic_batch(engine, drift):
    from katrain.web.core.models_db import KifuNameChange

    _applied(engine)
    _off_page_album(engine, player_id=17, event_id=20)
    _later_player_link(engine, (11, 12))
    applied, _ = _later_event_link(engine)
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    with engine.begin() as conn:
        if drift == "direct_revert":
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(event_id=20))
        elif drift == "sgf":
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(sgf_content="Changed"))
        elif drift == "bundle":
            artifact = deepcopy(conn.scalar(
                select(KifuNameBatch.reviewed_artifact).where(KifuNameBatch.id == applied["batch_id"])
            ))
            artifact["bundle"]["album_links"][0]["identity_review"]["event_period_basis"] = "Changed"
            conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == applied["batch_id"])
                         .values(reviewed_artifact=artifact))
        else:
            change = conn.execute(select(KifuNameChange.__table__).where(
                KifuNameChange.batch_id == applied["batch_id"], KifuNameChange.target_table == KifuAlbum.__tablename__,
            )).mappings().one()
            field = "before_image" if drift == "ledger_before" else "after_image"
            image = deepcopy(change[field])
            image["event_id"] = None
            conn.execute(KifuNameChange.__table__.update().where(KifuNameChange.id == change["id"])
                         .values(**{field: image}))
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}


@pytest.mark.parametrize("new", [False, True])
def test_later_reviewed_player_link_keeps_selected_event_api_proof(engine, monkeypatch, new):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _applied(engine)
    _later_player_link(engine, new=new)
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
        assert asyncio.run(kifu.get_kifu_album(_request(), 11, lang="en", db=db)).display_event == "Example event EN"
        result = asyncio.run(
            kifu.list_kifu_albums(_request(), q="Example event RU", page=1, page_size=20, lang="en", db=db)
        )
        assert result.total == 1
        assert result.items[0].display_event == "Example event EN"


@pytest.mark.parametrize(
    ("extra", "drift"),
    [(extra, drift) for extra in ("event", "noop_player", "event_noop", "event_noop_new") for drift in ("sgf", "fk")]
    + [(extra, "reverted_fk") for extra in ("noop_player", "event_noop", "event_noop_new")],
)
def test_later_player_replay_allows_unrelated_links_and_noop_members(engine, extra, drift):
    from katrain.web.kifu.name_batch import dry_run_bundle

    _applied(engine)
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=12,
                player_black="Other",
                player_white="Unknown" if extra != "event" else "Other",
                event="Other Cup",
                sgf_content="(;PB[Other]PW[Other]EV[Other Cup])",
                source_path="other.sgf",
                white_player_id=17 if extra != "event" else None,
            )
        )
        if extra in ("event", "event_noop"):
            conn.execute(KifuEvent.__table__.insert().values(id=20, canonical_name="Other Cup"))
    inventory = build_inventory(engine, inventory_format=4)
    player = {"kind": "player", "id": 17}
    owners = [{"owner": player, "preimage": {"canonical_name": "吴清源"}}]
    links = [_identity_link(engine, inventory, 11, "white", player)]
    if extra != "noop_player":
        event = {"kind": "event", "ref": "other-cup"} if extra == "event_noop_new" else {"kind": "event", "id": 20}
        owners.append(
            {"owner": event, "create" if extra == "event_noop_new" else "preimage": {"canonical_name": "Other Cup"}}
        )
        links.append(_identity_link(engine, inventory, 12, "event", event))
    if extra != "event":
        links.append(_identity_link(engine, inventory, 12, "white", player))
    bundle, research, sources = _eleven_language_identity_fixture(
        engine, inventory, [owner["owner"] for owner in owners]
    )
    if extra != "noop_player":
        for candidate, record in zip(bundle["candidates"], research):
            if candidate["owner"]["kind"] == "event":
                candidate["display_name"] += " Other"
                record["candidate_name"] = candidate["display_name"]
                for check in record["source_checks"]:
                    check["candidate_name"] = candidate["display_name"]
                    check["body_excerpt"] += " Other"
                candidate["research_sha256"] = canonical_sha256(record)
    bundle["inventory_format"] = 4
    bundle = _v2_wrap(engine, inventory, bundle, owners, links)
    assert dry_run_bundle(engine, bundle, sources, inventory, research)["ready"]
    assert apply_bundle(engine, bundle, sources, inventory, research)["status"] == "applied"
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    if extra != "event":
        _later_player_link(engine, (12,), new=True)
        with Session(engine) as db:
            assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
        if drift == "reverted_fk":
            with engine.begin() as conn:
                conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(white_player_id=17))
            with Session(engine) as db:
                assert live_event_selections(db, [], album_ids={11}) == {}
            return
    with engine.begin() as conn:
        column = "sgf_content" if drift == "sgf" else "white_player_id" if extra != "event" else "event_id"
        old = conn.scalar(select(getattr(KifuAlbum, column)).where(KifuAlbum.id == 12))
        conn.execute(
            KifuAlbum.__table__.update()
            .where(KifuAlbum.id == 12)
            .values(**{column: old + " " if drift == "sgf" else None})
        )
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}


@pytest.mark.parametrize("value", [[], {}, True, -1, "17"])
def test_malformed_player_ledger_ids_leave_readers_unverified(engine, monkeypatch, value):
    from katrain.web.core.models_db import KifuNameChange

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _applied(engine)
    applied, _ = _later_player_link(engine)
    with engine.begin() as conn:
        change = (
            conn.execute(
                select(KifuNameChange.__table__).where(
                    KifuNameChange.batch_id == applied["batch_id"],
                    KifuNameChange.target_table == KifuAlbum.__tablename__,
                )
            )
            .mappings()
            .one()
        )
        after = deepcopy(change["after_image"])
        after["white_player_id"] = value
        conn.execute(
            KifuNameChange.__table__.update().where(KifuNameChange.id == change["id"]).values(after_image=after)
        )
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}
        assert (
            asyncio.run(kifu.get_kifu_album(_request(), 11, lang="en", db=db)).display_event == "Event name unverified"
        )
        assert (
            asyncio.run(
                kifu.list_kifu_albums(_request(), q="Example event EN", page=1, page_size=20, lang="en", db=db)
            ).total
            == 0
        )
    report = coverage_report(engine, build_inventory(engine, inventory_format=4), languages=("en",))
    assert any(row["slot"] == "event" for row in report["missing_examples"])


@pytest.mark.parametrize(
    "drift", ["direct_fk", "bundle", "missing_bundle", "raw_scope", "ledger", "partial_undo", "resolved_ref"]
)
def test_later_player_link_cannot_mask_unreviewed_association_change(engine, drift):
    from katrain.web.core.models_db import KifuNameChange

    _applied(engine)
    applied, _ = _later_player_link(engine)
    with engine.begin() as conn:
        if drift == "direct_fk":
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(black_player_id=None))
        elif drift == "ledger":
            change = (
                conn.execute(
                    select(KifuNameChange.__table__).where(
                        KifuNameChange.batch_id == applied["batch_id"],
                        KifuNameChange.target_table == KifuAlbum.__tablename__,
                    )
                )
                .mappings()
                .one()
            )
            after = deepcopy(change["after_image"])
            after["black_player_id"] = None
            conn.execute(
                KifuNameChange.__table__.update().where(KifuNameChange.id == change["id"]).values(after_image=after)
            )
        elif drift == "partial_undo":
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == applied["batch_id"])
                .values(status="partial_undo")
            )
        else:
            artifact = deepcopy(
                conn.scalar(select(KifuNameBatch.reviewed_artifact).where(KifuNameBatch.id == applied["batch_id"]))
            )
            if drift == "bundle":
                artifact["bundle"]["album_links"][0]["identity_review"]["identity_basis"] = "Changed"
            elif drift == "missing_bundle":
                artifact["bundle"] = None
            elif drift == "raw_scope":
                artifact["bundle"]["album_links"][0]["expected"]["player_white"] = []
            else:
                artifact["resolved_refs"]["player:17"] = 18
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == applied["batch_id"])
                .values(reviewed_artifact=artifact)
            )
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}


@pytest.mark.parametrize("drift", ["sgf", "fk"])
def test_later_player_batch_checks_off_page_drift_and_fully_undone_batch(engine, drift):
    from katrain.web.kifu.name_batch import undo_batch

    bundle, sources, inventory, research = _multi_selected_bundle(engine, 2)
    apply_bundle(engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle))
    applied, _ = _later_player_link(engine, (11, 12))
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup 0", 19)}
    with engine.begin() as conn:
        column = "sgf_content" if drift == "sgf" else "white_player_id"
        original = conn.scalar(select(getattr(KifuAlbum, column)).where(KifuAlbum.id == 12))
        conn.execute(
            KifuAlbum.__table__.update()
            .where(KifuAlbum.id == 12)
            .values(**{column: original + " " if drift == "sgf" else None})
        )
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(**{column: original}))
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup 0", 19)}


def test_later_player_changes_replay_exact_chain_and_reverse_undo(engine):
    from katrain.web.kifu.name_batch import undo_batch

    _applied(engine)
    first, _ = _later_player_link(engine)
    second, _ = _later_player_link(engine, new=True)
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    assert undo_batch(engine, second["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    assert undo_batch(engine, first["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}


def test_original_selected_event_batch_undo_keeps_later_player_link(engine):
    from katrain.web.core.models_db import KifuAlbumEventSelection
    from katrain.web.kifu.name_batch import undo_batch

    selected = _applied(engine)
    _later_player_link(engine)
    assert undo_batch(engine, selected["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.white_player_id).where(KifuAlbum.id == 11)) == 17
        assert (
            conn.scalar(select(KifuAlbumEventSelection.event_id).where(KifuAlbumEventSelection.album_id == 11)) is None
        )


def test_later_player_replay_prefetches_connected_off_page_histories(engine):
    bundle, sources, inventory, research = _multi_selected_bundle(engine, 3)
    apply_bundle(engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle))
    _later_player_link(engine, (11, 12))
    _later_player_link(engine, (12, 13), new=True)
    _later_player_link(engine, (13,))
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup 0", 19)}
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 13).values(white_player_id=None))
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}


def test_later_player_replay_closes_history_through_successive_noop_members(engine):
    from katrain.web.kifu.name_batch import undo_batch

    _applied(engine)
    with engine.begin() as conn:
        for album_id in (12, 13):
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=album_id, player_black="Other", player_white="Unknown", event="Other Cup",
                    sgf_content="(;PB[Other]PW[Unknown]EV[Other Cup])", source_path=f"other-{album_id}.sgf",
                    white_player_id=17,
                )
            )
    _later_player_link(engine, (11, 12))
    _later_player_link(engine, (12,), new=True)
    _later_player_link(engine, (12, 13))
    last, _ = _later_player_link(engine, (13,), new=True, new_name="Another reviewed player", new_suffix=" New Second")
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
    with engine.begin() as conn:
        original = conn.scalar(select(KifuAlbum.white_player_id).where(KifuAlbum.id == 13))
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 13).values(white_player_id=17))
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 13).values(white_player_id=original))
    assert undo_batch(engine, last["batch_id"])["status"] == "undone"
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}


def test_selected_event_link_readers_share_valid_proof(engine, monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _applied(engine)
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup", 19)}
        detail = asyncio.run(kifu.get_kifu_album(_request(), 11, lang="en", db=db))
        assert detail.display_event == "Example event EN"
        assert detail.event == "GNUGo3.8"
        assert "GN[Selected Cup]" in detail.sgf_content
        result = asyncio.run(
            kifu.list_kifu_albums(_request(), q="Example event RU", page=1, page_size=20, lang="en", db=db)
        )
        assert result.total == 1
        assert result.items[0].display_event == "Example event EN"
    inventory = build_inventory(engine, inventory_format=4)
    report = coverage_report(engine, inventory, languages=("en",))
    assert not [row for row in report["missing_examples"] if row["slot"] == "event"]
    proposals = list(propose_album_matches(inventory, player_aliases={}, event_aliases={"Selected Cup": {19}}))
    event = next(row for row in proposals if row["side"] == "event")
    assert event["raw_value"] == "Selected Cup"
    assert event["existing_id"] == 19


def test_selected_event_link_coverage_v4_unlinked_and_linked(engine):
    bundle, sources, before, research = selected_event_bundle(engine)
    before_report = coverage_report(engine, before, languages=("en",))
    apply_bundle(engine, bundle, sources, before, research, expected_bundle_sha256=canonical_sha256(bundle))
    after = build_inventory(engine, inventory_format=4)
    assert before["sha256"] != after["sha256"]
    report = coverage_report(engine, before, languages=("en",))
    assert report["event_selection_drift"] == 1
    assert report["event_selection_sha256"] != before_report["event_selection_sha256"]


def _selected_bundle(engine, raw):
    new = False
    from tests.web_ui.test_kifu_name_candidates import _selected_v4_case

    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.update()
            .where(KifuAlbum.id == 11)
            .values(
                source="https://19x19.com",
                source_path="data/kifu-album/19x19/one.sgf",
                date_played="1934-10-01",
                board_size=19,
                sgf_content=f"(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[{raw}]GC[{raw} | 1手])",
            )
        )
        if not new:
            conn.execute(KifuEvent.__table__.insert().values(id=19, canonical_name="Selected Cup"))
    apply_reviewed_selection(engine, 11)
    inv = build_inventory(engine, inventory_format=4)
    owner = {"kind": "event", "ref": "selected-cup"} if new else {"kind": "event", "id": 19}
    base, research, source_registry = _eleven_language_identity_fixture(engine, inv, [owner])
    _, template = _selected_v4_case()
    declaration = deepcopy(template["owners"][0])
    declaration["owner"] = owner
    if new:
        declaration["create"] = declaration.pop("preimage")
    album = dict(zip(inv["association_columns"], inv["album_associations"][0]))
    selection = dict(zip(inv["event_selection"]["columns"], inv["event_selection"]["rows"][0]))
    link = deepcopy(template["album_links"][0])
    link.update(
        album_id=11,
        target=owner,
        association_sha256=canonical_sha256(album),
        production_sgf_sha256=selection["sgf_sha256"],
        raw_scope_sha256=canonical_sha256([[11, "selected_event"]]),
        selection_batch_id=selection["batch_id"],
        selection_bundle_sha256=selection["bundle_sha256"],
        selection_before_image=selection["source_after_image"],
        selection_before_sha256=selection["source_after_sha256"],
        expected={
            key: album[key]
            for key in (
                "player_black",
                "player_white",
                "event",
                "date_played",
                "round_name",
                "black_rank",
                "white_rank",
            )
        }
        | {"old_id": None},
    )
    base.update(
        bundle_format=4,
        inventory_format=4,
        inventory_sha256=inv["sha256"],
        catalog_sha256=catalog_snapshot_sha(engine),
        owners=[declaration],
        owner_set_sha256=canonical_sha256([declaration]),
        album_links=[link],
    )
    link["identity_review"]["scope_sha256"] = identity_scope_sha256(base, [link], declaration)
    base["link_set_sha256"] = canonical_sha256([link])
    return base, source_registry, inv, research


def test_selected_event_core_does_not_cover_full_current_field(engine, monkeypatch):
    from katrain.web.core.models_db import KifuRawEventValue, KifuRawEventName

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    bundle, sources, inventory, research = _selected_bundle(engine, "28th Honinbo Final")
    apply_bundle(engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle))
    inventory = build_inventory(engine, inventory_format=4)
    with Session(engine) as db:
        detail = asyncio.run(kifu.get_kifu_album(_request(), 11, lang="en", db=db))
        assert detail.display_event == "Event name unverified"
        result = asyncio.run(
            kifu.list_kifu_albums(_request(), q="Example event EN", page=1, page_size=20, lang="en", db=db)
        )
        assert result.total == 0
        report = coverage_report(engine, inventory, languages=("en",))
        assert any(row["slot"] == "event" for row in report["missing_examples"])
        raw = KifuRawEventValue(raw_value="28th Honinbo Final", category="event_candidate", review_status="approved")
        db.add(raw)
        db.flush()
        evidence = _evidence(db, "raw_event", raw.id, "en", "28th Honinbo Final")
        db.add(
            KifuRawEventName(
                raw_event_id=raw.id,
                lang="en",
                display_name="28th Honinbo Final",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()
        assert asyncio.run(kifu.get_kifu_album(_request(), 11, lang="en", db=db)).display_event == "28th Honinbo Final"
        result = asyncio.run(
            kifu.list_kifu_albums(_request(), q="Example event EN", page=1, page_size=20, lang="en", db=db)
        )
        assert result.total == 1
    report = coverage_report(engine, inventory, languages=("en",))
    assert not [row for row in report["missing_examples"] if row["slot"] == "event"]


@pytest.mark.parametrize("drift", ["sgf", "revoked", "pending_name"])
def test_selected_event_invalid_proof_and_current_name_keep_gap(engine, monkeypatch, drift):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    applied = _applied(engine)
    inventory = build_inventory(engine, inventory_format=4)
    with engine.begin() as conn:
        if drift == "sgf":
            content = conn.scalar(select(KifuAlbum.sgf_content))
            conn.execute(KifuAlbum.__table__.update().values(sgf_content=content + " "))
        elif drift == "revoked":
            conn.execute(
                KifuNameBatch.__table__.update().where(KifuNameBatch.id == applied["batch_id"]).values(status="undone")
            )
        else:
            conn.execute(KifuEventName.__table__.update().where(KifuEventName.lang == "en").values(status="review"))
    with Session(engine) as db:
        assert (
            asyncio.run(kifu.get_kifu_album(_request(), 11, lang="en", db=db)).display_event == "Event name unverified"
        )
        result = asyncio.run(
            kifu.list_kifu_albums(_request(), q="Example event EN", page=1, page_size=20, lang="en", db=db)
        )
        assert result.total == 0
        assert result.items == []
    report = coverage_report(engine, inventory, languages=("en",))
    assert any(row["slot"] == "event" for row in report["missing_examples"])


def test_invalid_selection_cannot_fall_back_to_hidden_program_label(engine, monkeypatch):
    from katrain.web.core.models_db import KifuRawEventName

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    _applied(engine)
    inventory = build_inventory(engine, inventory_format=4)
    with Session(engine) as db:
        evidence = _evidence(db, "raw_event", 7, "en", "", decision="hidden")
        db.add(
            KifuRawEventName(
                raw_event_id=7,
                lang="en",
                display_name="",
                status="verified",
                decision_kind="hidden",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        album = db.get(KifuAlbum, 11)
        album.sgf_content = "(;FF[4]SZ[19]GN[GNUGo3.8])"
        db.commit()
        assert (
            asyncio.run(kifu.get_kifu_album(_request(), 11, lang="en", db=db)).display_event == "Event name unverified"
        )
    report = coverage_report(engine, inventory, languages=("en",))
    assert any(row["slot"] == "event" for row in report["missing_examples"])


def _multi_selected_bundle(engine, count):
    bundle, sources, _, research = _selected_bundle(engine, "Selected Cup 0")
    for offset in range(1, count):
        raw = f"Selected Cup {offset}"
        with engine.begin() as conn:
            original = dict(conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 11)).mappings().one())
            original.update(
                id=11 + offset,
                source_path=f"data/kifu-album/19x19/{offset}.sgf",
                sgf_content=f"(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[{raw}]GC[{raw} | 1手])",
            )
            conn.execute(KifuAlbum.__table__.insert().values(**original))
        apply_reviewed_selection(engine, 11 + offset)
    inventory = build_inventory(engine, inventory_format=4)
    template = deepcopy(bundle["album_links"][0])
    links = []
    for album_values, selection_values in zip(inventory["album_associations"], inventory["event_selection"]["rows"]):
        album = dict(zip(inventory["association_columns"], album_values))
        selection = dict(zip(inventory["event_selection"]["columns"], selection_values))
        link = deepcopy(template)
        link.update(
            album_id=album["id"],
            association_sha256=canonical_sha256(album),
            production_sgf_sha256=selection["sgf_sha256"],
            raw_scope_sha256=canonical_sha256([[album["id"], "selected_event"]]),
            selection_batch_id=selection["batch_id"],
            selection_bundle_sha256=selection["bundle_sha256"],
            selection_before_image=selection["source_after_image"],
            selection_before_sha256=selection["source_after_sha256"],
        )
        links.append(link)
    bundle.update(inventory_sha256=inventory["sha256"], album_links=links)
    for link in links:
        link["identity_review"]["scope_sha256"] = identity_scope_sha256(bundle, [link], bundle["owners"][0])
    bundle["link_set_sha256"] = canonical_sha256(links)
    return bundle, sources, inventory, research


@pytest.mark.parametrize("count", [1, 5, 20])
def test_one_page_selection_proof_queries_bounded_across_raw_groups(engine, count):
    from sqlalchemy import event

    bundle, sources, inventory, research = _multi_selected_bundle(engine, count)
    apply_bundle(engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle))
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with Session(engine) as db:
            assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup 0", 19)}
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(statements) <= 20


def _apply_independent_selected_batches(engine, count):
    template, _, _, _ = _multi_selected_bundle(engine, count)
    applied = []
    for original_link in template["album_links"]:
        inventory = build_inventory(engine, inventory_format=4)
        bundle, research, sources = _eleven_language_identity_fixture(
            engine, inventory, [template["owners"][0]["owner"]]
        )
        link = deepcopy(original_link)
        bundle.update(
            bundle_format=4,
            inventory_format=4,
            catalog_sha256=catalog_snapshot_sha(engine),
            owners=deepcopy(template["owners"]),
            owner_set_sha256=template["owner_set_sha256"],
            album_links=[link],
        )
        link["identity_review"]["scope_sha256"] = identity_scope_sha256(bundle, [link], bundle["owners"][0])
        bundle["link_set_sha256"] = canonical_sha256([link])
        applied.append(
            apply_bundle(engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle))
        )
    return applied


@pytest.mark.parametrize("count", [1, 5, 20])
def test_one_page_selection_proof_queries_bounded_across_name_batches(engine, count):
    from sqlalchemy import event

    _apply_independent_selected_batches(engine, count)
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with Session(engine) as db:
            assert live_event_selections(db, [], album_ids=set(range(11, 11 + count))) == {
                11 + offset: (f"Selected Cup {offset}", 19) for offset in range(count)
            }
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(statements) <= 20


@pytest.mark.parametrize("count", [1, 5, 20])
def test_one_page_later_player_proof_queries_stay_bounded(engine, count):
    from sqlalchemy import event

    bundle, sources, inventory, research = _multi_selected_bundle(engine, count)
    apply_bundle(engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle))
    _later_player_link(engine, tuple(range(11, 11 + count)))
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with Session(engine) as db:
            assert live_event_selections(db, [], album_ids=set(range(11, 11 + count))) == {
                11 + offset: (f"Selected Cup {offset}", 19) for offset in range(count)
            }
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(statements) <= 20


def test_selected_event_proof_checks_off_page_batch_member_and_undo_stays_atomic(engine):
    from katrain.web.core.models_db import KifuAlbumEventSelection
    from katrain.web.kifu.name_batch import BatchError, undo_batch

    bundle, sources, inventory, research = _multi_selected_bundle(engine, 2)
    applied = apply_bundle(
        engine, bundle, sources, inventory, research, expected_bundle_sha256=canonical_sha256(bundle)
    )
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {11: ("Selected Cup 0", 19)}
    with engine.begin() as conn:
        content = conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == 12))
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 12).values(sgf_content=content + " "))
        before_selections = list(conn.execute(select(KifuAlbumEventSelection.__table__)).mappings())
        before_names = list(conn.execute(select(KifuEventName.__table__)).mappings())
    with Session(engine) as db:
        assert live_event_selections(db, [], album_ids={11}) == {}
    with pytest.raises(BatchError):
        undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameBatch.status).where(KifuNameBatch.id == applied["batch_id"])) == "applied"
        assert list(conn.execute(select(KifuAlbumEventSelection.__table__)).mappings()) == before_selections
        assert list(conn.execute(select(KifuEventName.__table__)).mappings()) == before_names
