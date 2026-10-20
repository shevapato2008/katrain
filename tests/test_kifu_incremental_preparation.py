from hashlib import sha256

import pytest


def test_importer_metadata_and_embedded_rank_keep_original_sgf():
    from katrain.kifu_ingest.preparation import derive_metadata

    sgf = "(;FF[4]SZ[19]PB[张三九段]PW[李四]WR[8p]EV[比赛]DT[2026-03-01,02]KM[6.5]HA[2]PC[北京]RO[决赛]SO[https://19x19.com];B[aa])"
    values = derive_metadata(sgf)
    assert values["player_black"] == "张三九段"
    assert values["black_rank"] == "九段"
    assert values["player_white"] == "李四"
    assert values["date_sort"] == "2026-03-01"
    assert values["komi"] == 6.5
    assert values["handicap"] == 2
    assert values["board_size"] == 19
    assert values["move_count"] == 1
    assert "张三" in values["search_text"]
    assert "张三九段" in sgf


def test_sgf_authority_and_source_fallback_with_conflict_quarantine():
    from katrain.kifu_ingest.preparation import derive_metadata

    sgf = "(;PB[Alice]PW[Bob]EV[Match];B[aa])"
    assert derive_metadata(sgf, {"date_played": "2026-03-01"})["date_played"] == "2026-03-01"
    with pytest.raises(ValueError, match="source metadata conflicts"):
        derive_metadata(sgf, {"player_black": "Different"})


def test_source_player_without_embedded_rank_matches_sgf_identity():
    from katrain.kifu_ingest.preparation import derive_metadata

    result = derive_metadata("(;PB[张三九段]PW[李四]EV[比赛];B[aa])", {"pb": "张三", "pw": "李四"})
    assert result["player_black"] == "张三九段"
    assert result["black_rank"] == "九段"


def test_actual_scope_player_literal_is_preserved_while_rank_is_derived():
    from katrain.kifu_ingest.preparation import derive_metadata

    values = derive_metadata("(;PB[陈祈睿九段]PW[对手]EV[比赛];B[aa])", {"pb": "陈祈睿", "pw": "对手"})
    assert values["player_black"] == "陈祈睿九段"
    assert values["black_rank"] == "九段"


def test_nonfinite_komi_and_non_19_board_are_isolated():
    from katrain.kifu_ingest.preparation import derive_metadata

    with pytest.raises(ValueError, match="komi"):
        derive_metadata("(;PB[B]PW[W]EV[E];B[aa])", {"komi": "nan"})
    with pytest.raises(ValueError, match="19x19"):
        derive_metadata("(;SZ[13]PB[B]PW[W]EV[E];B[aa])")


def test_ambiguous_gn_is_quarantined_except_existing_approved_rule():
    from katrain.kifu_ingest.preparation import derive_metadata

    with pytest.raises(ValueError, match="ambiguous GN"):
        derive_metadata("(;PB[B]PW[W]GN[One][Two];B[aa])")
    sgf = "(;PB[B]PW[W]SO[https://19x19.com]GN[GNUGo3.8][Game]GC[Game];B[aa])"
    assert derive_metadata(sgf)["event"] == "Game"


def test_historical_exclusions_are_versioned_and_rejected():
    from katrain.kifu_ingest.exclusions import assert_source_allowed, historical_excluded_ids

    ids = historical_excluded_ids()
    assert len(ids) == 1752
    assert_source_allowed("19x19", "999999999")
    with pytest.raises(ValueError, match="historically excluded"):
        assert_source_allowed("19x19", next(iter(ids)))


def test_real_public_source_fields_use_play_time_not_upload_time():
    from katrain.kifu_ingest.preparation import derive_metadata

    sgf = "(;PB[金明训]PW[许家元]EV[第12届国手山脉杯世界赛8强赛];B[aa])"
    source = {
        "id": 91358273,
        "pb": "金明训",
        "pw": "许家元",
        "gamename": "第12届国手山脉杯世界赛8强赛",
        "boardSize": 19,
        "rule": "japanese",
        "komi": 6.5,
        "handicap": 0,
        "gameResult": "W+R",
        "moveNum": 1,
        "playTime": {"date": {"year": 2026, "month": 10, "day": 19}},
        "createTime": {"date": {"year": 2030, "month": 1, "day": 1}},
        "blackLevel": 3002,
        "whiteLevel": 3002,
    }
    result = derive_metadata(sgf, source)
    assert result["date_played"] == result["date_sort"] == "2026-10-19"
    assert result["board_size"] == 19
    assert result["rules"] == "japanese"
    assert result["result"] == "W+R"
    assert "black_rank" not in result
