"""The whole-inventory staging command checks live raw values before writes."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuRawEventValue, KifuRawPlayerValue
from katrain.web.kifu.catalog_preprocess import preprocess, run_against_database
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS


def _inventory():
    values = dict.fromkeys(ASSOCIATION_COLUMNS)
    values.update(id=1, player_black="吴清源九段", player_white="木谷实", event="第1届应氏杯第1轮", sources=[])
    return {
        "inventory_format": 2,
        "counts": {"all": 1},
        "detail_ids": [1],
        "association_columns": list(ASSOCIATION_COLUMNS),
        "album_associations": [[values[key] for key in ASSOCIATION_COLUMNS]],
        "scopes": {"all": {
            "album_ids": [1],
            "values": {
                "player": [
                    {"value": "吴清源九段", "occurrences": 1, "affected_games": 1},
                    {"value": "木谷实", "occurrences": 1, "affected_games": 1},
                ],
                "event": [{"value": "第1届应氏杯第1轮", "occurrences": 1, "affected_games": 1}],
            },
        }},
        "distinct_values": {"all": {"event": 1}},
    }


def test_preprocess_stages_once_and_rejects_a_stale_inventory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'raw.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuAlbum(id=1, player_black="吴清源九段", player_white="木谷实",
                         event="第1届应氏杯第1轮", source_path="one.sgf", sgf_content="(;GM[1])"))
        db.commit()
        first = preprocess(_inventory(), db)
        assert first["player_upsert"]["inserted"] == 2
        assert first["event_upsert"]["inserted"] == 1
        db.commit()
        again = preprocess(_inventory(), db)
        assert again["player_upsert"]["inserted"] == 0
        assert again["event_upsert"]["inserted"] == 0
        db.commit()
        assert db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == "吴清源九段"))
        assert db.scalar(select(KifuRawEventValue).where(KifuRawEventValue.raw_value == "第1届应氏杯第1轮"))
        db.scalar(select(KifuAlbum)).event = "别的比赛"
        db.commit()
        with pytest.raises(ValueError, match="live album raw names differ"):
            preprocess(_inventory(), db)
        db.rollback()


def test_database_dry_run_rolls_back_every_raw_insert(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'raw.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuAlbum(id=1, player_black="吴清源九段", player_white="木谷实",
                         event="第1届应氏杯第1轮", source_path="one.sgf", sgf_content="(;GM[1])"))
        db.commit()
    report = run_against_database(_inventory(), engine, apply=False)
    assert report["player_upsert"]["inserted"] == 2
    assert report["event_upsert"]["inserted"] == 1
    with Session(engine) as db:
        assert not db.scalars(select(KifuRawPlayerValue)).first()
        assert not db.scalars(select(KifuRawEventValue)).first()


def test_null_player_slot_is_accounted_for_offline():
    inventory = _inventory()
    inventory["album_associations"][0][ASSOCIATION_COLUMNS.index("player_white")] = None
    inventory["scopes"]["all"]["values"]["player"].pop()
    inventory["scopes"]["all"]["values"]["player"].append(
        {"value": None, "occurrences": 1, "affected_games": 1}
    )
    report = preprocess(inventory)
    assert report["null_player_slots"] == 1
    assert report["player_raw_values"] == 1
