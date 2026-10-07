"""The first Chinese pass is a guarded display fallback, not an identity approval."""

import asyncio
import hashlib
import importlib
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core import models_db
from katrain.web.core.models_db import Base, KifuAlbum, KifuEvent, KifuEventName, KifuPlayer, KifuPlayerAlias
from katrain.web.kifu import first_pass_cn
from scripts.build_kifu_cn_first_pass_asset import translated_event_core


def _request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))


@pytest.mark.parametrize("endpoint", ["current", "legacy"])
def test_exact_player_search_does_not_include_games_named_for_player_in_event(endpoint, monkeypatch):
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    if endpoint == "legacy":
        # The deployment overlay imports analysis models absent from the current schema.
        monkeypatch.setattr(models_db, "KifuAnalysisJob", object, raising=False)
        monkeypatch.setattr(models_db, "KifuAnalysisMove", object, raising=False)
        legacy = importlib.import_module("deploy.ucloud.kifu_cn_first_pass_legacy.kifu")
        legacy_identity = importlib.import_module("deploy.ucloud.kifu_cn_first_pass_legacy.identity")
        monkeypatch.setattr(legacy, "matching_entity_ids", legacy_identity.matching_entity_ids)
        monkeypatch.setattr(legacy, "display_maps", legacy_identity.display_maps)
        api = legacy
    else:
        api = kifu

    raw_event = "Yomiuri 7-8 Dans Tournament to find challenger to Go Seigen"
    chinese_event = "读卖新闻七八段挑战吴清源选拔赛"
    assert (raw_event, None) in first_pass_cn.search_raw_names("吴清源")[1]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        player = KifuPlayer(canonical_name="Go Seigen")
        db.add(player)
        db.flush()
        db.add_all([
            KifuPlayerAlias(player_id=player.id, alias=name, normalized_alias=name.casefold())
            for name in ("吴清源", "Go Seigen")
        ])
        game = KifuAlbum(
            player_black="Go Seigen", player_white="Kitani Minoru", black_player_id=player.id,
            sgf_content="(;PB[Go Seigen]PW[Kitani Minoru])", source_path="player.sgf",
        )
        event_game = KifuAlbum(
            player_black="Fujisawa Shuko", player_white="Kitani Minoru", event=raw_event,
            sgf_content="(;PB[Fujisawa Shuko]PW[Kitani Minoru])", source_path="event.sgf",
        )
        db.add_all([game, event_game])
        db.commit()

        for query, lang in (("吴清源", "cn"), ("吴清源", "en"),
                            ("Go Seigen", "cn"), ("Go Seigen", "en")):
            result = asyncio.run(api.list_kifu_albums(_request(), q=query, page=1, page_size=20, lang=lang, db=db))
            assert (result.total, [item.id for item in result.items]) == (1, [game.id])
        event_result = asyncio.run(api.list_kifu_albums(
            _request(), q=chinese_event, page=1, page_size=20, lang="cn", db=db
        ))
        assert (event_result.total, [item.id for item in event_result.items]) == (1, [event_game.id])
    engine.dispose()


def test_event_core_translation_keeps_edition_and_year():
    glossary = {"Nihon Saikyo": {"zh": "日本最强战", "unit": "期"},
                "TaiwanPromotionTournament,2000": {"zh": "台湾升段赛"}}
    assert translated_event_core("4th Nihon Saikyo", "Nihon Saikyo", glossary) == "第4期日本最强战"
    assert translated_event_core("TaiwanPromotionTournament,2000", "TaiwanPromotionTournament,2000", glossary) == "2000年台湾升段赛"
    assert translated_event_core("4th Nihon Saikyo Final", "Nihon Saikyo", glossary) is None
    assert translated_event_core("GNUGo3.8", None, glossary) is None
    assert ("4th Nihon Saikyo", None) in first_pass_cn.search_raw_names("日本最强战")[1]


def test_cn_fallback_uses_linked_canonical_and_exact_raw_without_changing_source(monkeypatch):
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        player = KifuPlayer(canonical_name="岩本薰")
        event = KifuEvent(canonical_name="大手合")
        db.add_all([player, event])
        db.flush()
        album = KifuAlbum(
            player_black="Iwamoto Kaoru", player_white="Cho Chikun",
            black_player_id=player.id, event="JapanPromotionTournament,1934,Fall", event_id=event.id,
            sgf_content="(;B[aa])", source_path="first-pass.sgf",
        )
        db.add(album)
        db.commit()
        result = asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="cn", db=db))
        assert result.display_player_black == "岩本薰"
        assert result.display_player_white == "赵治勋"
        assert result.display_event == "1934年秋季大手合"
        assert (result.player_black, result.event) == (
            "Iwamoto Kaoru", "JapanPromotionTournament,1934,Fall"
        )
        searched = asyncio.run(kifu.list_kifu_albums(
            _request(), q="赵治勋", page=1, page_size=20, lang="cn", db=db
        ))
        assert [item.id for item in searched.items] == [album.id]
        searched_event = asyncio.run(kifu.list_kifu_albums(
            _request(), q="1934年秋季大手合", page=1, page_size=20, lang="cn", db=db
        ))
        assert [item.id for item in searched_event.items] == [album.id]
        assert asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="en", db=db)).display_event == album.event
    finally:
        db.close()
        engine.dispose()


def test_sgf_override_requires_exact_source_and_skips_selected_event(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        album = KifuAlbum(
            player_black="Black", player_white="White", event="11", sgf_content="(;GN[11]GN[中国棋圣战])",
            source_path="override.sgf",
        )
        db.add(album)
        db.commit()
        digest = hashlib.sha256(album.sgf_content.encode()).hexdigest()
        monkeypatch.setattr(first_pass_cn, "_hints", lambda: ({}, {}, {album.id: ("11", digest, "中国棋圣战")}))
        assert first_pass_cn.event_hints(db, [album], {}) == {album.id: "中国棋圣战"}
        assert first_pass_cn.search_raw_names("中国棋圣战")[2] == {album.id}
        assert first_pass_cn.valid_override_search_ids(db, {album.id}) == {album.id}
        assert first_pass_cn.event_hints(db, [album], {}, selected_events={album.id: ("已选赛事", None)}) == {}
        album.sgf_content = "(;GN[11]GN[另一赛事])"
        db.flush()
        assert first_pass_cn.event_hints(db, [album], {}) == {}
        assert first_pass_cn.valid_override_search_ids(db, {album.id}) == set()
    finally:
        db.close()
        engine.dispose()


def test_legacy_verified_event_name_outranks_first_pass_hint(monkeypatch):
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        event = KifuEvent(canonical_name="大手合")
        db.add(event)
        db.flush()
        db.add(KifuEventName(event_id=event.id, lang="cn", display_name="已核实的大手合", status="verified"))
        album = KifuAlbum(
            player_black="黑方", player_white="白方", event="Oteai", event_id=event.id,
            sgf_content="(;B[aa])", source_path="verified-event.sgf",
        )
        db.add(album)
        db.commit()
        result = asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="cn", db=db))
        assert result.display_event == "已核实的大手合"
    finally:
        db.close()
        engine.dispose()
