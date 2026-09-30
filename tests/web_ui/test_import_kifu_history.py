from scripts import import_kifu


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
