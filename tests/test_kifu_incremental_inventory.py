"""A local source inventory must not depend on an album database."""

from hashlib import sha256

import pytest

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.inventory import scan_inventory


def _write(source_dir, name, content):
    path = source_dir / name
    path.write_bytes(content.encode("utf-8"))
    return path


def test_streams_new_source_metadata_and_canonical_sgf_hash(tmp_path):
    raw = " (;FF[4]SZ[19]DT[2026-01-31]PB[Black]PW[White]BR[9p]WR[8p]EV[Match]GN[Round]GC[Note];B[aa];W[]) "
    _write(tmp_path, "42.sgf", raw)
    _write(tmp_path, "43.sgf", "(;DT[2026-02-01];B[bb])")
    seen = []

    summary = scan_inventory(
        tmp_path,
        known_source_paths={"data/kifu-album/19x19/43.sgf"},
        on_entry=seen.append,
    )

    assert len(seen) == 1
    item = seen[0]
    assert item.source_id == "42"
    assert item.origin_path == "data/kifu-album/19x19/42.sgf"
    assert item.raw_sha256 == sha256(raw.encode("utf-8")).hexdigest()
    assert item.sgf_sha256 == sha256(SGF.parse_sgf(raw).sgf().encode("utf-8")).hexdigest()
    assert item.sgf_content == SGF.parse_sgf(raw).sgf()
    assert (item.date_raw, item.date_status, item.date_played) == ("2026-01-31", "in_range", "2026-01-31")
    assert (item.player_black, item.player_white, item.black_rank, item.white_rank) == ("Black", "White", "9p", "8p")
    assert (item.ev_values, item.gn_values, item.gc_values, item.source_raw, item.event_raw) == (
        ("Match",),
        ("Round",),
        ("Note",),
        None,
        "Match",
    )
    assert item.move_count == 2
    assert summary.total_sgf_files == 2
    assert summary.known_source_paths == 1
    assert summary.in_range == 1
    assert summary.date_min == summary.date_max == "2026-01-31"
    assert summary.errors == []


def test_partial_or_invalid_dt_stays_pending_and_old_date_is_separate(tmp_path):
    _write(tmp_path, "1.sgf", "(;DT[2026-01-30]GN[Old];B[aa])")
    _write(tmp_path, "2.sgf", "(;DT[2026-02]GN[Month];B[aa])")
    _write(tmp_path, "3.sgf", "(;DT[2026-02-30]GN[Invalid];B[aa])")
    _write(tmp_path, "4.sgf", "(;GN[Missing];B[aa])")
    seen = []

    summary = scan_inventory(tmp_path, on_entry=seen.append)

    assert [(x.source_id, x.date_status, x.date_played) for x in seen] == [
        ("1", "out_of_range", "2026-01-30"),
        ("2", "date_pending", None),
        ("3", "date_pending", None),
        ("4", "date_pending", None),
    ]
    assert (summary.in_range, summary.out_of_range, summary.date_pending) == (0, 1, 3)
    assert (summary.date_min, summary.date_max) == ("2026-01-30", "2026-01-30")


def test_excludes_ids_and_records_invalid_ids_and_parse_errors_without_source_text(tmp_path):
    _write(tmp_path, "1.sgf", "(;DT[2026-02-01])")
    _write(tmp_path, "2.sgf", "(;DT[2026-02-02])")
    _write(tmp_path, "bad-name.sgf", "(;DT[2026-02-03])")
    _write(tmp_path, "3.sgf", "not an sgf: secret source text")
    seen = []

    summary = scan_inventory(tmp_path, excluded_source_ids={"2"}, on_entry=seen.append)

    assert [item.source_id for item in seen] == ["1"]
    assert (summary.total_sgf_files, summary.excluded_source_ids, summary.invalid_source_id, summary.errors_count) == (
        4,
        1,
        1,
        1,
    )
    assert len(summary.errors) == 1
    assert summary.errors[0].source_id == "3"
    assert summary.errors[0].reason == "sgf_parse_error"
    assert "secret source text" not in repr(summary)


@pytest.mark.parametrize("bad_id", ["../1", "1.sgf", "-1", "１", "", "01/2"])
def test_rejects_untrusted_excluded_ids_before_scanning(tmp_path, bad_id):
    with pytest.raises(ValueError, match="source ID"):
        scan_inventory(tmp_path, excluded_source_ids={bad_id}, on_entry=lambda _: None)
