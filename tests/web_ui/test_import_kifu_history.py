from scripts import import_kifu
import pytest


def test_normalize_historical_date_with_text_prefix():
    assert import_kifu.normalize_date("ca. 1665") == "1665-00-00"
    assert import_kifu.normalize_date("1928-09-04,05") == "1928-09-04"


def test_import_uses_extended_date_for_sort_only(tmp_path, monkeypatch):
    sgf = tmp_path / "data" / "kifu-album" / "CWI_History_Full" / "old.sgf"
    sgf.parent.mkdir(parents=True)
    sgf.write_text("(;FF[4]SZ[19]PB[A]PW[B]DTX[Published 1842-05-06];B[dd];W[pp])")
    monkeypatch.setattr(import_kifu, "DATA_DIR", sgf.parent.parent)

    record = import_kifu.parse_sgf_file(sgf)

    assert record["date_played"] is None
    assert record["date_sort"] == "1842-05-06"


def test_mainline_signature_ignores_metadata_but_keeps_moves():
    moves = ";".join(f"{'B' if i % 2 == 0 else 'W'}[{chr(97 + i % 19)}{chr(97 + i // 19)}]" for i in range(30))
    first = f"(;SZ[19]PB[A]PW[B];{moves})"
    second = f"(;SZ[19]PB[C]PW[D]DT[1965];{moves})"
    changed = second.replace("B[aa]", "B[ba]")

    assert import_kifu.mainline_signature(first) == import_kifu.mainline_signature(second)
    assert import_kifu.mainline_signature(first) != import_kifu.mainline_signature(changed)
    assert import_kifu.mainline_signature("(;SZ[19];B[dd];W[pp])") is None


@pytest.mark.parametrize(
    ("properties", "source", "expected"),
    [
        (
            "GN[GNUGo3.8]GN[第5届韩国最强棋士战预选]GC[第5届韩国最强棋士战预选 | 194手]",
            "https://19x19.com",
            "第5届韩国最强棋士战预选",
        ),
        (
            "GN[GNUGo3.8]GN[第5届韩国最强棋士战预选]GC[其他对局]",
            "https://19x19.com",
            "GNUGo3.8",
        ),
        (
            "GN[GNUGo3.8]GN[GNUGo4.0]GC[GNUGo4.0 | 194手]",
            "https://19x19.com",
            "GNUGo3.8",
        ),
        (
            "GN[GNUGo3.8]GN[第5届]GC[第5届韩国最强棋士战预选 | 194手]",
            "https://19x19.com",
            "GNUGo3.8",
        ),
        (
            "GN[GNUGo3.8]GN[第5届韩国最强棋士战预选]"
            "GC[第5届韩国最强棋士战预选 | 194手]GC[其他赛事]",
            "https://19x19.com",
            "GNUGo3.8",
        ),
        (
            "EV[正式赛事]GN[GNUGo3.8]GN[第5届韩国最强棋士战预选]"
            "GC[第5届韩国最强棋士战预选 | 194手]",
            "https://19x19.com",
            "正式赛事",
        ),
        (
            "GN[段位赛]GN[第4届中国棋王战]GC[第4届中国棋王战 | 200手]",
            "https://19x19.com",
            "段位赛",
        ),
        (
            "GN[GNUGo3.8]GN[第5届韩国最强棋士战预选]GC[第5届韩国最强棋士战预选 | 194手]",
            "https://other.example",
            "GNUGo3.8",
        ),
    ],
)
def test_import_selects_second_game_name_only_for_verified_program_label(
    tmp_path, monkeypatch, properties, source, expected
):
    sgf = tmp_path / "data" / "kifu-album" / "19x19" / "game.sgf"
    sgf.parent.mkdir(parents=True)
    sgf.write_text(f"(;FF[4]SZ[19]PB[Black]PW[White]{properties}SO[{source}];B[aa])", encoding="utf-8")
    monkeypatch.setattr(import_kifu, "DATA_DIR", sgf.parent.parent)

    record = import_kifu.parse_sgf_file(sgf)

    assert record["event"] == expected
    if "GNUGo" in properties:
        assert "GN[GNUGo3.8][" in record["sgf_content"]
