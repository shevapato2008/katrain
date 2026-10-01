"""Kifu entity search, localized display and multi-source list contract."""

import asyncio
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuAlbumSource,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuEvent,
    KifuEventName,
    KifuSource,
)


def _request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))


def test_exact_player_aliases_find_the_same_games_and_localize_the_card():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        player = KifuPlayer(canonical_name="Go Seigen")
        db.add(player)
        db.flush()
        db.add_all(
            [
                KifuPlayerAlias(player_id=player.id, alias="Go Seigen", normalized_alias="go seigen"),
                KifuPlayerAlias(player_id=player.id, alias="吴清源", normalized_alias="吴清源"),
                KifuPlayerName(player_id=player.id, lang="cn", display_name="吴清源", status="verified"),
                KifuPlayerName(player_id=player.id, lang="en", display_name="Go Seigen", status="verified"),
            ]
        )
        game = KifuAlbum(
            player_black="Go Seigen",
            player_white="Kitani Minoru",
            black_player_id=player.id,
            round_name="Final",
            result="B+R",
            date_sort="1939-01-01",
            sgf_content="(;PB[Go Seigen]PW[Kitani Minoru];B[pd])",
            source_path="data/kifu-album/CWI_History_Full/test.sgf",
            search_text="go seigen kitani minoru",
            move_count=1,
        )
        cup = KifuAlbum(
            player_black="Someone Else",
            player_white="Another Player",
            event="吴清源杯",
            date_sort="2026-01-01",
            sgf_content="(;EV[吴清源杯];B[dp])",
            source_path="data/kifu-album/19x19/cup.sgf",
            search_text="吴清源杯",
            move_count=1,
        )
        db.add_all([game, cup])
        db.flush()
        cwi = KifuSource(source_key="cwi", display_name="CWI")
        star = KifuSource(source_key="golaxy", display_name="星阵")
        db.add_all([cwi, star])
        db.flush()
        db.add_all(
            [
                KifuAlbumSource(
                    album_id=game.id, source_id=cwi.id, origin_path="cwi/test.sgf", match_method="original_path"
                ),
                KifuAlbumSource(
                    album_id=game.id, source_id=star.id, origin_path="golaxy/test.sgf", match_method="exact_content"
                ),
            ]
        )
        db.commit()

        cn = asyncio.run(kifu.list_kifu_albums(_request(), q="吴清源", page=1, page_size=20, lang="cn", db=db))
        en = asyncio.run(kifu.list_kifu_albums(_request(), q="Go Seigen", page=1, page_size=20, lang="en", db=db))
        assert cn.total == en.total == 1
        assert [item.id for item in cn.items] == [item.id for item in en.items] == [game.id]
        assert cn.items[0].display_player_black == "吴清源"
        assert en.items[0].display_player_black == "Go Seigen"
        assert cn.items[0].display_round_name == "决赛"
        assert en.items[0].display_round_name == "Final"
        assert cn.items[0].sources == ["cwi", "golaxy"]

        detail = asyncio.run(kifu.get_kifu_album(_request(), album_id=game.id, lang="cn", db=db))
        assert detail.display_player_black == "吴清源"
        assert detail.sgf_content == game.sgf_content

    engine.dispose()


def test_cwi_oteai_edition_is_localized_but_unknown_event_is_preserved():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        event = KifuEvent(canonical_name="Oteai")
        db.add(event)
        db.flush()
        db.add_all([
            KifuEventName(event_id=event.id, lang="cn", display_name="大手合", status="verified"),
            KifuEventName(event_id=event.id, lang="jp", display_name="大手合", status="verified"),
            KifuAlbum(
                player_black="Go Seigen", player_white="Hashimoto Utaro",
                event="JapanPromotionTournament,1934,Fall", event_id=event.id,
                sgf_content="(;EV[JapanPromotionTournament,1934,Fall];B[dd])",
                source_path="cwi/oteai.sgf",
            ),
            KifuAlbum(
                player_black="A", player_white="B", event="Unknown,1934,Fall",
                sgf_content="(;EV[Unknown,1934,Fall];B[pp])", source_path="other/unknown.sgf",
            ),
        ])
        db.commit()
        cn = asyncio.run(kifu.list_kifu_albums(_request(), q=None, page=1, page_size=20, lang="cn", db=db))
        en = asyncio.run(kifu.list_kifu_albums(_request(), q=None, page=1, page_size=20, lang="en", db=db))
        cn_by_event = {item.event: item for item in cn.items}
        en_by_event = {item.event: item for item in en.items}
        assert cn_by_event["JapanPromotionTournament,1934,Fall"].display_event == "1934年秋季大手合"
        assert en_by_event["JapanPromotionTournament,1934,Fall"].display_event == "Oteai · Autumn 1934"
        assert cn_by_event["Unknown,1934,Fall"].display_event == "Unknown,1934,Fall"
    engine.dispose()


def test_unverified_ordinary_event_name_falls_back_to_original_sgf_text():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        event = KifuEvent(canonical_name="Oteai")
        db.add(event)
        db.flush()
        db.add(KifuAlbum(
            player_black="A", player_white="B", event="大手合", event_id=event.id,
            sgf_content="(;EV[大手合];B[dd])", source_path="cwi/ordinary.sgf",
        ))
        db.commit()
        result = asyncio.run(kifu.list_kifu_albums(_request(), q=None, page=1, page_size=20, lang="ru", db=db))
        assert result.items[0].display_event == "大手合"
    engine.dispose()


def test_embedded_player_dan_has_separate_display_fields_and_preserves_raw_sgf():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        album = KifuAlbum(
            player_black="吴清源六段", player_white="木谷实",
            black_rank=None, white_rank="七段",
            sgf_content="(;PB[吴清源六段]PW[木谷实]WR[七段];B[dd])",
            source_path="19x19/embedded.sgf",
        )
        db.add(album)
        db.commit()
        response = asyncio.run(kifu.list_kifu_albums(_request(), q=None, page=1, page_size=20, lang="cn", db=db))
        item = response.items[0]
        assert item.player_black == "吴清源六段"
        assert item.black_rank is None
        assert item.display_player_black == "吴清源"
        assert item.display_black_rank == "六段"
        assert item.display_player_white == "木谷实"
        assert item.display_white_rank == "七段"
    engine.dispose()


def test_duplicate_copy_is_hidden_from_list_but_detail_remains_available():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        original = KifuAlbum(
            player_black="A", player_white="B", sgf_content="(;B[pd])", source_path="a.sgf", search_text="a b"
        )
        db.add(original)
        db.flush()
        copy = KifuAlbum(
            player_black="A",
            player_white="B",
            sgf_content="(;B[pd])",
            source_path="b.sgf",
            search_text="a b",
            duplicate_of_id=original.id,
        )
        db.add(copy)
        db.commit()

        listing = asyncio.run(kifu.list_kifu_albums(_request(), q=None, page=1, page_size=20, lang="cn", db=db))
        assert listing.total == 1
        assert [item.id for item in listing.items] == [original.id]
        assert asyncio.run(kifu.get_kifu_album(_request(), album_id=copy.id, lang="cn", db=db)).id == copy.id

    engine.dispose()


def test_fuzzy_search_treats_sql_wildcards_as_literal_characters():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        player = KifuPlayer(canonical_name="Alias_Player")
        db.add(player)
        db.flush()
        db.add(KifuPlayerAlias(player_id=player.id, alias="Alias_Player", normalized_alias="alias_player"))
        literal = KifuAlbum(
            player_black="Alias_Player",
            player_white="White",
            black_player_id=player.id,
            sgf_content="(;B[pd])",
            source_path="literal.sgf",
            search_text="alias_player white",
        )
        unrelated = KifuAlbum(
            player_black="Alice Stone",
            player_white="Bob",
            sgf_content="(;B[dp])",
            source_path="unrelated.sgf",
            search_text="alice stone bob",
        )
        db.add_all([literal, unrelated])
        db.commit()

        percent = asyncio.run(kifu.list_kifu_albums(_request(), q="%", page=1, page_size=20, lang="cn", db=db))
        underscore = asyncio.run(kifu.list_kifu_albums(_request(), q="_", page=1, page_size=20, lang="cn", db=db))
        assert percent.total == 0
        assert [item.id for item in underscore.items] == [literal.id]

    engine.dispose()
