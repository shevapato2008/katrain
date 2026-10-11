import hashlib
import json

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import Base, KifuAlbum, KifuEvent, KifuEventAlias, KifuEventEdition
from scripts.import_kifu_event_types import run


def seal_plan(plan):
    plan["sha256"] = hashlib.sha256(json.dumps({key: value for key, value in plan.items() if key != "sha256"},
                                             ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return plan


@pytest.fixture
def engine():
    value = create_engine("sqlite:///:memory:")

    @event.listens_for(value, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(value)
    with Session(value) as db, db.begin():
        db.add(KifuEvent(id=44, canonical_name="大手合"))
        db.add(KifuEventAlias(event_id=44, alias="Oteai", normalized_alias="oteai"))
        db.add_all([
            KifuAlbum(id=1, event="Oteai 1927", date_played="1927-06-01", player_black="甲", player_white="乙",
                      sgf_content="(;)", source_path="one.sgf"),
            KifuAlbum(id=2, event="1st Honinbo", date_played="1941-06-01", player_black="丙", player_white="丁",
                      sgf_content="(;)", source_path="two.sgf"),
        ])
    yield value
    value.dispose()


def test_dry_run_and_apply_resolve_existing_alias_and_create_editions(engine):
    plan = {"sha256": "approved", "selected_series": ["Honinbo", "Oteai"],
            "total_albums": 2, "raw_counts": {"Oteai 1927": 1, "1st Honinbo": 1},
            "series_aliases": {"Honinbo": ["日本本因坊戦"]},
            "albums": [[1, "Oteai 1927", "Oteai", ["year", 1927], "1927-06-01"],
                       [2, "1st Honinbo", "Honinbo", ["edition_number", 1], "1941-06-01"]]}
    seal_plan(plan)
    preview = run(engine, plan, apply=False)
    assert preview["album_count"] == 2
    assert preview["new_type_count"] == 1
    assert preview["new_alias_count"] == 1
    with Session(engine) as db:
        assert db.query(KifuEventEdition).count() == 0
    result = run(engine, plan, apply=True, approved_sha256=plan["sha256"])
    assert result["updated_albums"] == 2
    assert result["event_ids"]["Oteai"] == 44
    with Session(engine) as db:
        albums = db.execute(select(KifuAlbum).order_by(KifuAlbum.id)).scalars().all()
        assert albums[0].event_id == 44
        assert albums[0].event_edition_id is not None
        assert albums[1].event_id == result["event_ids"]["Honinbo"]
        assert albums[1].event_edition_id is not None
        assert [row.event for row in albums] == ["Oteai 1927", "1st Honinbo"]
        assert db.execute(select(KifuEventAlias.alias).where(
            KifuEventAlias.event_id == result["event_ids"]["Honinbo"])).scalar_one() == "日本本因坊戦"


def test_conflicting_existing_event_link_is_rejected(engine):
    with Session(engine) as db, db.begin():
        db.add(KifuEvent(id=55, canonical_name="Other"))
        db.get(KifuAlbum, 1).event_id = 55
    plan = {"sha256": "approved", "selected_series": ["Oteai"],
            "total_albums": 2, "raw_counts": {"Oteai 1927": 1},
            "albums": [[1, "Oteai 1927", "Oteai", ["year", 1927], "1927-06-01"]]}
    seal_plan(plan)
    with pytest.raises(ValueError, match="different event type"):
        run(engine, plan, apply=False)


def test_snapshot_drift_is_rejected_before_any_write(engine):
    plan = {"sha256": "approved", "selected_series": ["Oteai"],
            "total_albums": 2, "raw_counts": {"Oteai 1927": 1},
            "albums": [[1, "Oteai 1927", "Oteai", ["year", 1927], "1927-06-01"]]}
    seal_plan(plan)
    with Session(engine) as db, db.begin():
        db.get(KifuAlbum, 2).event = "Oteai 1927"
    with pytest.raises(ValueError, match="raw EV counts"):
        run(engine, plan, apply=False)


def test_date_drift_aborts_apply_before_any_write(engine):
    plan = {"sha256": "approved", "selected_series": ["Oteai"],
            "total_albums": 2, "raw_counts": {"Oteai 1927": 1},
            "albums": [[1, "Oteai 1927", "Oteai", ["year", 1927], "1927-06-01"]]}
    seal_plan(plan)
    with Session(engine) as db, db.begin():
        db.get(KifuAlbum, 1).date_played = "1927-06-02"
    with pytest.raises(ValueError, match="date_played changed for album 1"):
        run(engine, plan, apply=True, approved_sha256=plan["sha256"])
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).event_id is None
        assert db.query(KifuEventEdition).count() == 0


def test_two_raw_series_cores_share_one_canonical_event_and_edition(engine):
    with Session(engine) as db, db.begin():
        db.add_all([
            KifuAlbum(id=3, event="1st Pro Best Ten", date_played="1975-06-01", player_black="甲", player_white="乙",
                      sgf_content="(;)", source_path="three.sgf"),
            KifuAlbum(id=4, event="1st ProBestTen", date_played="1975-07-01", player_black="丙", player_white="丁",
                      sgf_content="(;)", source_path="four.sgf"),
        ])
    plan = {
        "sha256": "approved",
        "selected_series": ["Pro Best Ten", "ProBestTen"],
        "total_albums": 4,
        "raw_counts": {"1st Pro Best Ten": 1, "1st ProBestTen": 1},
        "albums": [
            [3, "1st Pro Best Ten", "Pro Best Ten", ["edition_number", 1], "1975-06-01"],
            [4, "1st ProBestTen", "ProBestTen", ["edition_number", 1], "1975-07-01"],
        ],
    }
    seal_plan(plan)
    preview = run(engine, plan, apply=False)
    assert preview["new_type_count"] == 1
    assert preview["distinct_edition_keys"] == 1
    result = run(engine, plan, apply=True, approved_sha256=plan["sha256"])
    assert result["event_ids"]["Pro Best Ten"] == result["event_ids"]["ProBestTen"]
    with Session(engine) as db:
        albums = [db.get(KifuAlbum, album_id) for album_id in (3, 4)]
        assert albums[0].event_id == albums[1].event_id
        assert albums[0].event_edition_id == albums[1].event_edition_id
        assert db.query(KifuEvent).filter(KifuEvent.canonical_name == "日本职业十杰战").count() == 1
        assert db.query(KifuEventEdition).filter(KifuEventEdition.event_id == albums[0].event_id).count() == 1
    replay = run(engine, plan, apply=True, approved_sha256=plan["sha256"])
    assert replay["updated_albums"] == 0
    assert replay["new_type_count"] == 0


@pytest.mark.parametrize("album_id,raw,core,edition,date", [
    (33426, "第2期日本关西棋院第一位获得纪念对局", "Kansai", ["edition_number", 2], "1958-12-29"),
    (31009, "第31期日本天元战预选赛", "Tengen", ["edition_number", 31], "2006-09-21"),
    (63983, "Meijin,14th", "Meijin", None, "1974-01-16"),
])
def test_reviewed_wrong_link_cannot_be_recreated(engine, album_id, raw, core, edition, date):
    with Session(engine) as db, db.begin():
        db.add(KifuAlbum(id=album_id, event=raw, date_played=date,
                         player_black="甲", player_white="乙", sgf_content="(;)",
                         source_path=f"{album_id}.sgf"))
    plan = {"sha256": "approved", "selected_series": [core],
            "series_names": {core: f"{core} type"}, "total_albums": 3,
            "raw_counts": {raw: 1}, "albums": [[album_id, raw, core, edition, date]]}
    seal_plan(plan)
    with pytest.raises(ValueError, match="reviewed .* hold"):
        run(engine, plan, apply=True, approved_sha256=plan["sha256"])
    with Session(engine) as db:
        assert db.get(KifuAlbum, album_id).event_id is None


def test_approved_sha_cannot_authorize_mutated_plan(engine):
    plan = seal_plan({"selected_series": ["Oteai"], "total_albums": 2,
                      "raw_counts": {"Oteai 1927": 1},
                      "albums": [[1, "Oteai 1927", "Oteai", ["year", 1927], "1927-06-01"]]})
    approved = plan["sha256"]
    plan["albums"][0][3] = ["year", 1928]
    with pytest.raises(ValueError, match="plan SHA-256 does not match content"):
        run(engine, plan, apply=True, approved_sha256=approved)
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).event_id is None
