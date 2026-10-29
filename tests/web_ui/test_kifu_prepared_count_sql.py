"""Only finite prepared player membership needs a union-based count."""

import pytest
from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core.models_db import KifuAlbum
from katrain.web.kifu import prepared_models as prepared
from katrain.web.kifu.prepared_read import _member_clause


@pytest.fixture
def count_db():
    engine = create_engine("sqlite://")
    KifuAlbum.__table__.create(engine)
    prepared.members.create(engine)
    with Session(engine) as db:
        for album_id, attributes in (
            (1, {"black_player_id": 17}),
            (2, {"white_player_id": 17}),
            (3, {"black_player_id": 17, "white_player_id": 17}),
            (4, {}),
            (5, {"black_player_id": 17, "list_hidden_reason": "review"}),
            (6, {"list_hidden_reason": "review"}),
            (7, {"black_player_id": 17, "duplicate_of_id": 1}),
            (8, {"duplicate_of_id": 1}),
            (9, {}),
            (10, {}),
        ):
            db.add(
                KifuAlbum(
                    id=album_id,
                    player_black="Black",
                    player_white="White",
                    source_path=f"{album_id}.sgf",
                    sgf_content="(;)",
                    **attributes,
                )
            )
        db.execute(
            prepared.members.insert(),
            [
                {"prepared_name_id": 1, "album_id": album_id, "slot": slot, "semantic": {"search": search}}
                for album_id, slot, search in (
                    (3, "black", True),
                    (4, "black", True),
                    (4, "white", True),
                    (6, "black", True),
                    (8, "black", True),
                    (9, "black", False),
                    (10, "event", True),
                )
            ],
        )
        db.flush()
        yield db
    engine.dispose()


def _visible():
    return (KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None))


@pytest.mark.parametrize("shared", [False, True])
def test_finite_player_count_unions_ids_and_preserves_visibility_and_membership(count_db, shared):
    predicate = or_(
        KifuAlbum.black_player_id.in_([17, 18]) if shared else KifuAlbum.black_player_id == 17,
        KifuAlbum.white_player_id.in_([17, 18]) if shared else KifuAlbum.white_player_id == 17,
        _member_clause([1], ("black", "white")),
    )
    query = kifu._prepared_count_query(count_db, predicate, _visible())

    assert query.scalar() == 4
    assert query.scalar() == count_db.query(func.count(KifuAlbum.id)).filter(*_visible(), predicate).scalar()
    sql = str(query.statement)
    assert " UNION " in sql
    assert "UNION ALL" not in sql
    assert sql.count("kifu_albums.duplicate_of_id IS NULL") == 3
    assert sql.count("kifu_albums.list_hidden_reason IS NULL") == 3
    assert sql.startswith("SELECT count(*) AS count_1 \nFROM (SELECT kifu_albums.id")


@pytest.mark.parametrize("kind", ["player_id", "fuzzy", "selected_ids", "other_subquery", "negative_membership"])
def test_other_count_shapes_keep_the_existing_query(count_db, kind):
    player = or_(KifuAlbum.black_player_id == 17, KifuAlbum.white_player_id == 17)
    finite = _member_clause([1], ("black", "white"))
    predicates = {
        "player_id": player,
        "fuzzy": or_(player, finite, KifuAlbum.search_text.contains("17")),
        "selected_ids": or_(player, finite, KifuAlbum.id.in_([4])),
        "other_subquery": or_(player, KifuAlbum.id.in_(select(KifuAlbum.id).where(KifuAlbum.id == 4))),
        "negative_membership": or_(player, ~finite),
    }
    predicate = predicates[kind]
    expected = count_db.query(func.count(KifuAlbum.id)).filter(*_visible(), predicate)
    query = kifu._prepared_count_query(count_db, predicate, _visible())

    assert str(query.statement) == str(expected.statement)
    assert query.scalar() == expected.scalar()
