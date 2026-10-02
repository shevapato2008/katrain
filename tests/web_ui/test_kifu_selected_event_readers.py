"""API, coverage and matching share the reviewed selected-event identity."""

import asyncio
from copy import deepcopy

from sqlalchemy import select
from katrain.web.core.models_db import KifuAlbum, KifuEvent, KifuEventName, KifuNameBatch
from katrain.web.kifu.name_candidates import identity_scope_sha256
from katrain.web.kifu.name_batch import catalog_snapshot_sha
from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
from tests.web_ui.test_kifu_name_batch import _eleven_language_identity_fixture
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
