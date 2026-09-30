from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuDedupBatch,
    KifuDedupChange,
    KifuPlayer,
    KifuPlayerAlias,
    KifuSource,
)
from katrain.web.kifu.provenance import classify_source_path, ensure_album_source
from scripts.backfill_kifu_catalog import backfill_catalog, undo_dedup_batch
from scripts.seed_kifu_translations import load_seed
from scripts import import_kifu
from katrain.web.kifu import catalog_backfill


SEED = load_seed(Path(__file__).resolve().parents[2] / "docs/resource/kifu-name-seed.json")


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _album(path, sgf="(;SZ[19]PB[Go Seigen]PW[Kitani Minoru];B[dd];W[pp])"):
    return KifuAlbum(player_black="Go Seigen", player_white="Kitani Minoru", sgf_content=sgf, source_path=path)


def test_source_classifier_requires_a_known_dataset_path():
    for folder in ("CWI_History_Full", "CWI_1950_1978", "CWI_Dosaku", "CWI_Jowa", "CWI_Shusaku", "Go_Seigen"):
        assert classify_source_path(f"data/kifu-album/{folder}/game.sgf") == "CWI"
    assert classify_source_path("data/kifu-album/19x19/game.sgf") == "19x19"
    assert classify_source_path("data/kifu-album/other/game.sgf") == "unknown"
    assert classify_source_path("data/kifu-album/fake-CWI_Dosaku/game.sgf") == "unknown"


def test_sgf_source_property_is_not_treated_as_dataset_provenance():
    engine = _db()
    with Session(engine) as db:
        album = _album("data/kifu-album/other/game.sgf")
        album.source = "星阵"
        db.add(album)
        db.commit()
        backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        db.refresh(album)
        assert album.source == "星阵"
        source = db.query(KifuSource).join(KifuAlbumSource).filter(KifuAlbumSource.album_id == album.id).one()
        assert source.source_key == "unknown"


def test_exact_content_dedup_logs_sources_and_can_undo_only_its_changes():
    engine = _db()
    with Session(engine) as db:
        master = _album("data/kifu-album/CWI_History_Full/a.sgf")
        duplicate = _album("data/kifu-album/19x19/b.sgf")
        db.add_all([master, duplicate])
        db.commit()
        report = backfill_catalog(db, SEED, dry_run=False, batch_key="batch-1", batch_size=1)
        db.refresh(duplicate)
        assert report["exact_duplicates"] == 1
        assert duplicate.duplicate_of_id == master.id
        assert db.query(KifuDedupChange).count() >= 2
        sources = {
            source.source_key
            for source in db.query(KifuSource).join(KifuAlbumSource).filter(KifuAlbumSource.album_id == master.id)
        }
        assert sources == {"CWI", "19x19"}

        repeated = backfill_catalog(db, SEED, dry_run=False, batch_key="batch-repeat", batch_size=1)
        assert repeated["exact_duplicates"] == 0
        assert repeated["source_links_added"] == 0
        assert (
            db.query(KifuDedupChange)
            .filter_by(batch_id=db.query(KifuDedupBatch).filter_by(batch_key="batch-repeat").one().id)
            .count()
            == 0
        )

        ensure_album_source(db, master.id, "data/kifu-album/extra/unrelated.sgf", "manual")
        db.commit()
        undo_dedup_batch(db, "batch-1")
        db.refresh(duplicate)
        assert duplicate.duplicate_of_id is None
        paths = {row.origin_path for row in db.query(KifuAlbumSource).filter_by(album_id=master.id)}
        assert "data/kifu-album/19x19/b.sgf" not in paths
        assert "data/kifu-album/extra/unrelated.sgf" in paths
        assert db.query(KifuDedupBatch).filter_by(batch_key="batch-1").one().status == "undone"


def test_three_exact_copies_share_one_master_log_and_undo_all_aggregated_sources():
    engine = _db()
    with Session(engine) as db:
        albums = [
            _album("data/kifu-album/CWI_History_Full/a.sgf"),
            _album("data/kifu-album/19x19/b.sgf"),
            _album("data/kifu-album/CWI_Jowa/c.sgf"),
        ]
        db.add_all(albums)
        db.commit()
        report = backfill_catalog(db, None, dry_run=False, batch_key="three", batch_size=1)
        assert report["exact_duplicates"] == 2
        batch = db.query(KifuDedupBatch).filter_by(batch_key="three").one()
        assert db.query(KifuDedupChange).filter_by(batch_id=batch.id).count() == 3
        assert db.query(KifuAlbumSource).filter_by(album_id=albums[0].id).count() == 3
        undo_dedup_batch(db, "three")
        assert db.query(KifuAlbumSource).filter_by(album_id=albums[0].id).count() == 1
        assert all(album.duplicate_of_id is None for album in albums)


def test_running_batch_resumes_with_original_before_snapshot(monkeypatch):
    engine = _db()
    with Session(engine) as db:
        first = _album("data/kifu-album/CWI_History_Full/a.sgf")
        second = _album("data/kifu-album/19x19/b.sgf")
        third = _album("data/kifu-album/CWI_Jowa/c.sgf", sgf="(;PB[Other]PW[Other]C[interrupt])")
        db.add_all([first, second, third])
        db.commit()
        original = catalog_backfill.mainline_signature

        def interrupt_on_third(content):
            if "interrupt" in content:
                raise RuntimeError("simulated interrupted scan")
            return original(content)

        monkeypatch.setattr(catalog_backfill, "mainline_signature", interrupt_on_third)
        with pytest.raises(RuntimeError, match="interrupted"):
            backfill_catalog(db, None, dry_run=False, batch_key="resume", batch_size=2)
        db.rollback()
        batch = db.query(KifuDedupBatch).filter_by(batch_key="resume").one()
        assert batch.status == "running"
        change = db.query(KifuDedupChange).filter_by(batch_id=batch.id, album_id=first.id).one()
        assert len(change.source_links_before) == 1
        assert len(change.source_links_after) == 2

        monkeypatch.setattr(catalog_backfill, "mainline_signature", original)
        report = backfill_catalog(db, None, dry_run=False, batch_key="resume", batch_size=2)
        assert report["exact_duplicates"] == 0
        assert report["resumed_running_batch"] is True
        assert report["exact_duplicates_in_batch"] == 1
        assert batch.status == "complete"
        change = db.query(KifuDedupChange).filter_by(batch_id=batch.id, album_id=first.id).one()
        assert len(change.source_links_before) == 1
        assert len(change.source_links_after) == 2
        undo_dedup_batch(db, "resume")
        db.refresh(second)
        assert second.duplicate_of_id is None
        assert db.query(KifuAlbumSource).filter_by(album_id=first.id, origin_path=second.source_path).count() == 0
        with pytest.raises(ValueError, match="already exists"):
            backfill_catalog(db, None, dry_run=False, batch_key="resume")


def test_import_commits_every_fixed_batch_and_can_resume(tmp_path, monkeypatch):
    engine = _db()
    data_dir = tmp_path / "data/kifu-album"
    folder = data_dir / "19x19"
    folder.mkdir(parents=True)
    for number in range(3):
        (folder / f"{number}.sgf").write_text(f"(;FF[4]SZ[19]PB[A]PW[B]C[{number}];B[dd])")
    monkeypatch.setattr(import_kifu, "DATA_DIR", data_dir)
    monkeypatch.setattr(import_kifu, "engine", engine)
    monkeypatch.setattr(import_kifu, "COMMIT_EVERY", 2)
    original = import_kifu.parse_sgf_file

    def interrupt_on_third(path):
        if path.name == "2.sgf":
            raise KeyboardInterrupt("simulated interruption")
        return original(path)

    monkeypatch.setattr(import_kifu, "parse_sgf_file", interrupt_on_third)
    with pytest.raises(KeyboardInterrupt):
        import_kifu.import_kifu()
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 2

    monkeypatch.setattr(import_kifu, "parse_sgf_file", original)
    import_kifu.import_kifu()
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 3
        assert db.query(KifuAlbumSource).count() == 3


def test_import_deduplicates_exact_content_by_default(tmp_path, monkeypatch):
    engine = _db()
    data_dir = tmp_path / "data/kifu-album"
    first = data_dir / "19x19/a.sgf"
    second = data_dir / "CWI_History_Full/b.sgf"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    sgf = "(;FF[4]SZ[19]PB[Go Seigen]PW[Kitani Minoru];B[dd])"
    first.write_text(sgf)
    second.write_text(sgf)
    monkeypatch.setattr(import_kifu, "DATA_DIR", data_dir)
    monkeypatch.setattr(import_kifu, "engine", engine)

    import_kifu.import_kifu()
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 1
        assert db.query(KifuAlbumSource).count() == 2


def test_undo_refuses_changed_sgf_content():
    engine = _db()
    with Session(engine) as db:
        master = _album("data/kifu-album/CWI_History_Full/a.sgf")
        duplicate = _album("data/kifu-album/19x19/b.sgf")
        db.add_all([master, duplicate])
        db.commit()
        backfill_catalog(db, SEED, dry_run=False, batch_key="guarded")
        duplicate.sgf_content += "changed"
        db.commit()
        with pytest.raises(ValueError, match="content changed"):
            undo_dedup_batch(db, "guarded")
        assert db.query(KifuDedupBatch).filter_by(batch_key="guarded").one().status == "complete"


def test_undo_preserves_source_link_changed_after_the_batch():
    engine = _db()
    with Session(engine) as db:
        master = _album("data/kifu-album/CWI_History_Full/a.sgf")
        duplicate = _album("data/kifu-album/19x19/b.sgf")
        db.add_all([master, duplicate])
        db.commit()
        backfill_catalog(db, None, dry_run=False, batch_key="link-changed")
        new_link = db.query(KifuAlbumSource).filter_by(album_id=master.id, origin_path=duplicate.source_path).one()
        new_link.match_method = "manual"
        db.commit()

        undo_dedup_batch(db, "link-changed")
        assert (
            db.query(KifuAlbumSource)
            .filter_by(album_id=master.id, origin_path=duplicate.source_path)
            .one()
            .match_method
            == "manual"
        )


def test_undo_dedup_batch_keeps_identity_and_ordinary_source_backfill():
    engine = _db()
    with Session(engine) as db:
        master = _album("data/kifu-album/CWI_History_Full/a.sgf")
        duplicate = _album("data/kifu-album/19x19/b.sgf")
        db.add_all([master, duplicate])
        db.commit()
        backfill_catalog(db, SEED, dry_run=False, batch_key="dedup-only")
        assert master.black_player_id is not None
        assert duplicate.duplicate_of_id == master.id

        undo_dedup_batch(db, "dedup-only")
        db.refresh(master)
        db.refresh(duplicate)
        assert duplicate.duplicate_of_id is None
        assert master.black_player_id is not None
        assert duplicate.black_player_id is not None
        assert db.query(KifuAlbumSource).filter_by(album_id=master.id, origin_path=master.source_path).count() == 1
        assert (
            db.query(KifuAlbumSource).filter_by(album_id=duplicate.id, origin_path=duplicate.source_path).count() == 1
        )
        assert db.query(KifuAlbumSource).filter_by(album_id=master.id, origin_path=duplicate.source_path).count() == 0


def test_backfill_without_seed_only_links_sources_and_deduplicates():
    engine = _db()
    with Session(engine) as db:
        first = _album("data/kifu-album/CWI_Jowa/a.sgf")
        second = _album("data/kifu-album/19x19/b.sgf")
        db.add_all([first, second])
        db.commit()
        report = backfill_catalog(db, None, dry_run=False, batch_key="no-seed")
        db.refresh(second)
        assert report["exact_duplicates"] == 1
        assert report["identity_updates"] == 0
        assert report["name_seed_coverage"] is None
        assert second.duplicate_of_id == first.id
        assert first.black_player_id is None


def test_existing_duplicate_pointer_is_preserved_when_master_has_higher_id():
    engine = _db()
    with Session(engine) as db:
        hidden = _album("data/kifu-album/CWI_Jowa/hidden.sgf")
        master = _album("data/kifu-album/19x19/master.sgf")
        db.add_all([hidden, master])
        db.flush()
        hidden.duplicate_of_id = master.id
        db.commit()
        report = backfill_catalog(db, None, dry_run=False, batch_key="old-pointer", batch_size=1)
        db.refresh(hidden)
        db.refresh(master)
        assert report["exact_duplicates"] == 0
        assert hidden.duplicate_of_id == master.id
        assert master.duplicate_of_id is None


def test_backfill_fetches_existing_sources_once_per_batch():
    engine = _db()
    with Session(engine) as db:
        db.add_all(_album(f"data/kifu-album/CWI_Dosaku/{i}.sgf", sgf=f"(;PB[A]PW[B]C[{i}])") for i in range(30))
        db.commit()
        source_selects = []

        def count_source_select(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT") and (
                "kifu_sources" in statement or "kifu_album_sources" in statement
            ):
                source_selects.append(statement)

        event.listen(engine, "before_cursor_execute", count_source_select)
        try:
            backfill_catalog(db, None, dry_run=False, dedupe=False, batch_size=10)
        finally:
            event.remove(engine, "before_cursor_execute", count_source_select)
        assert len(source_selects) <= 10


def test_same_mainline_with_different_sgf_is_only_a_candidate():
    moves = ";".join(f"{'B' if i % 2 == 0 else 'W'}[{chr(97 + i % 19)}{chr(97 + i // 19)}]" for i in range(30))
    engine = _db()
    with Session(engine) as db:
        first = _album("data/kifu-album/CWI_Dosaku/a.sgf", f"(;SZ[19]PB[A]PW[B];{moves})")
        second = _album("data/kifu-album/19x19/b.sgf", f"(;SZ[19]PB[C]PW[D]DT[1965];{moves})")
        db.add_all([first, second])
        db.commit()
        report = backfill_catalog(db, SEED, dry_run=False, batch_key="batch-2", batch_size=1)
        db.refresh(second)
        assert report["mainline_candidates"] == 1
        assert second.duplicate_of_id is None
        assert db.query(KifuDedupChange).count() == 0
        fast = backfill_catalog(db, None, dry_run=True, scan_mainlines=False)
        assert fast["mainline_candidates"] is None


def test_import_exact_duplicate_adds_all_source_paths_to_the_master(tmp_path, monkeypatch):
    engine = _db()
    data_dir = tmp_path / "data/kifu-album"
    first = data_dir / "19x19/a.sgf"
    second = data_dir / "CWI_History_Full/b.sgf"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    sgf = "(;FF[4]SZ[19]PB[Go Seigen]PW[Kitani Minoru];B[dd];W[pp])"
    first.write_text(sgf)
    second.write_text(sgf)
    monkeypatch.setattr(import_kifu, "DATA_DIR", data_dir)
    monkeypatch.setattr(import_kifu, "engine", engine)

    import_kifu.import_kifu(dedupe_content=True)
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 1
        album = db.query(KifuAlbum).one()
        assert {row.origin_path for row in db.query(KifuAlbumSource).filter_by(album_id=album.id)} == {
            "data/kifu-album/19x19/a.sgf",
            "data/kifu-album/CWI_History_Full/b.sgf",
        }

    third = data_dir / "CWI_Jowa/c.sgf"
    third.parent.mkdir(parents=True)
    third.write_text(sgf)
    import_kifu.import_kifu(dedupe_content=True)
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 1
        assert db.query(KifuAlbumSource).count() == 3


def test_import_keeps_mainline_only_candidate(tmp_path, monkeypatch, capsys):
    engine = _db()
    data_dir = tmp_path / "data/kifu-album"
    first = data_dir / "CWI_1950_1978/a.sgf"
    second = data_dir / "19x19/b.sgf"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    moves = ";".join(f"{'B' if i % 2 == 0 else 'W'}[{chr(97 + i % 19)}{chr(97 + i // 19)}]" for i in range(30))
    first.write_text(f"(;FF[4]SZ[19]PB[A]PW[B]DT[1965-01-01];{moves})")
    monkeypatch.setattr(import_kifu, "DATA_DIR", data_dir)
    monkeypatch.setattr(import_kifu, "engine", engine)
    import_kifu.import_kifu(dedupe_content=True, dedupe_mainline_years=(1950, 1978))
    second.write_text(f"(;FF[4]SZ[19]PB[C]PW[D]DT[1965-01-01];{moves})")

    import_kifu.import_kifu(dedupe_content=True, dedupe_mainline_years=(1950, 1978))
    assert "Same-mainline candidates (imported): 1" in capsys.readouterr().out
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 2
        assert all(row.duplicate_of_id is None for row in db.query(KifuAlbum))


def test_import_duplicate_uses_visible_master_even_if_legacy_duplicate_has_lower_id(tmp_path, monkeypatch):
    engine = _db()
    data_dir = tmp_path / "data/kifu-album"
    source_file = data_dir / "CWI_Jowa/new.sgf"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("(;FF[4]SZ[19]PB[Go Seigen]PW[Kitani Minoru];B[dd];W[pp])")
    monkeypatch.setattr(import_kifu, "DATA_DIR", data_dir)
    monkeypatch.setattr(import_kifu, "engine", engine)
    normalized = import_kifu.parse_sgf_file(source_file)["sgf_content"]
    with Session(engine) as db:
        hidden = _album("data/kifu-album/other/hidden.sgf", normalized)
        visible = _album("data/kifu-album/19x19/visible.sgf", normalized)
        db.add_all([hidden, visible])
        db.flush()
        hidden.duplicate_of_id = visible.id
        db.commit()
        visible_id = visible.id

    import_kifu.import_kifu(dedupe_content=True)
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 2
        assert (
            db.query(KifuAlbumSource)
            .filter_by(album_id=visible_id, origin_path="data/kifu-album/CWI_Jowa/new.sgf")
            .count()
            == 1
        )


def test_import_links_only_unambiguous_audited_aliases(tmp_path, monkeypatch):
    engine = _db()
    with Session(engine) as db:
        backfill_catalog(db, SEED, dry_run=False, dedupe=False)
    data_dir = tmp_path / "data/kifu-album"
    sgf_path = data_dir / "CWI_History_Full/new.sgf"
    sgf_path.parent.mkdir(parents=True)
    sgf_path.write_text("(;FF[4]SZ[19]PB[Go Seigen]PW[Unknown]EV[吴清源杯];B[dd])")
    monkeypatch.setattr(import_kifu, "DATA_DIR", data_dir)
    monkeypatch.setattr(import_kifu, "engine", engine)

    import_kifu.import_kifu()
    with Session(engine) as db:
        album = db.query(KifuAlbum).one()
        assert album.black_player_id is not None
        assert album.white_player_id is None
        assert album.event_id is not None


def test_import_leaves_conflicting_audited_alias_unlinked(tmp_path, monkeypatch):
    engine = _db()
    with Session(engine) as db:
        backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        other = KifuPlayer(canonical_name="Different Person")
        db.add(other)
        db.flush()
        db.add(KifuPlayerAlias(player_id=other.id, alias="Go Seigen", normalized_alias="go seigen"))
        db.commit()
    data_dir = tmp_path / "data/kifu-album"
    sgf_path = data_dir / "19x19/new.sgf"
    sgf_path.parent.mkdir(parents=True)
    sgf_path.write_text("(;FF[4]SZ[19]PB[Go Seigen]PW[Kitani Minoru];B[dd])")
    monkeypatch.setattr(import_kifu, "DATA_DIR", data_dir)
    monkeypatch.setattr(import_kifu, "engine", engine)

    import_kifu.import_kifu()
    with Session(engine) as db:
        album = db.query(KifuAlbum).one()
        assert album.black_player_id is None
        assert album.white_player_id is not None


def test_cli_uses_environment_database_url_without_echoing_it(tmp_path, monkeypatch, capsys):
    database_url = f"sqlite:///{tmp_path / 'catalog.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("KATRAIN_DATABASE_URL", database_url)
    monkeypatch.setattr("sys.argv", ["catalog_backfill", "--skip-mainline-candidates"])

    assert catalog_backfill.main() == 0
    output = capsys.readouterr().out
    assert '"albums_scanned": 0' in output
    assert database_url not in output
