import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from katrain.web.core.models_db import Base, KifuAlbum, KifuEvent, KifuEventEdition
from scripts.rollback_kifu_event_links_exact import plan_sha256, run


@pytest.fixture
def engine():
    value = create_engine("sqlite:///:memory:")

    @event.listens_for(value, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(value)
    with Session(value) as db, db.begin():
        db.add(KifuEvent(id=1, canonical_name="日本关西棋院第一位决定战"))
        db.flush()
        db.add(KifuEventEdition(id=2, event_id=1, edition_number=2))
        db.flush()
        db.add_all([
            KifuAlbum(id=3, event="第2期日本关西棋院第一位获得纪念对局",
                      event_id=1, event_edition_id=2, date_played="1958-12-29",
                      player_black="甲", player_white="乙", sgf_content="(;)", source_path="a.sgf"),
            KifuAlbum(id=4, event="unrelated", player_black="丙", player_white="丁",
                      sgf_content="(;)", source_path="b.sgf"),
        ])
    yield value
    value.dispose()


def plan():
    return {"expected_total_albums": 2, "rows": [{
        "album_id": 3, "raw_event": "第2期日本关西棋院第一位获得纪念对局",
        "date_played": "1958-12-29", "event_id": 1, "event_edition_id": 2,
        "event_name": "日本关西棋院第一位决定战",
    }]}


def test_exact_rollback_requires_approved_plan_and_preserves_raw_event(engine):
    assert run(engine, plan(), apply=False)["matched_albums"] == 1
    with pytest.raises(ValueError, match="approved plan"):
        run(engine, plan(), apply=True, approved_plan_sha256="wrong")
    result = run(engine, plan(), apply=True, approved_plan_sha256=plan_sha256(plan()))
    assert result["updated_albums"] == 1
    with Session(engine) as db:
        row = db.get(KifuAlbum, 3)
        assert row.event == "第2期日本关西棋院第一位获得纪念对局"
        assert row.date_played == "1958-12-29"
        assert row.event_id is None and row.event_edition_id is None
        assert db.get(KifuAlbum, 4).event == "unrelated"


def test_exact_rollback_rejects_preimage_drift_without_writing(engine):
    target = plan()
    target["rows"][0]["event_edition_id"] = 999
    with pytest.raises(ValueError, match="preimage"):
        run(engine, target, apply=True, approved_plan_sha256=plan_sha256(target))
    with Session(engine) as db:
        assert db.get(KifuAlbum, 3).event_id == 1


def test_exact_rollback_can_hold_only_wrong_edition(engine):
    target = plan()
    target["rows"][0]["retain_event_type"] = True
    result = run(engine, target, apply=True, approved_plan_sha256=plan_sha256(target))
    assert result["updated_albums"] == 1
    with Session(engine) as db:
        row = db.get(KifuAlbum, 3)
        assert row.event_id == 1
        assert row.event_edition_id is None
        assert row.event == target["rows"][0]["raw_event"]
