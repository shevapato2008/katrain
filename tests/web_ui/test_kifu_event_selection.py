"""Reviewed duplicate-GN selection changes only the derived event table."""

from copy import deepcopy
import json

import pytest
from sqlalchemy import create_engine, event, func, select

from katrain.core.sgf_parser import SGF
from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuAlbumEventSelection, KifuEventSelectionBatch, KifuEvent
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.provenance import sgf_sha256


SGF_TEXT = (
    "(;FF[4]SZ[19]PB[Black]PW[White]SO[https://19x19.com]"
    "GN[GNUGo3.8]GN[第5届韩国最强棋士战预选]"
    "GC[第5届韩国最强棋士战预选 | 194手];B[aa])"
)
RULE = "19x19-gnugo-second-gn-v1"


@pytest.fixture
def engine():
    db = create_engine("sqlite:///:memory:")

    @event.listens_for(db, "connect")
    def fk_on(conn, _record):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db)
    with db.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=2, canonical_name="Other event"))
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=1,
                player_black="Black",
                player_white="White",
                event="GNUGo3.8",
                event_id=None,
                source="https://19x19.com",
                source_path="data/kifu-album/19x19/a.sgf",
                date_played="1934-10-10",
                round_name="Round 1",
                board_size=19,
                sgf_content=SGF_TEXT,
            )
        )
    yield db
    db.dispose()


def member():
    return {
        "album_id": 1,
        "old_event": "GNUGo3.8",
        "old_event_id": None,
        "old_source": "https://19x19.com",
        "old_source_path": "data/kifu-album/19x19/a.sgf",
        "old_date_played": "1934-10-10",
        "old_round_name": "Round 1",
        "old_board_size": 19,
        "sgf_sha256": sgf_sha256(SGF_TEXT),
        "property_name": "GN",
        "property_index": 1,
        "selected_raw": "第5届韩国最强棋士战预选",
        "rule_version": RULE,
    }


def bundle(*, members=None):
    members = members if members is not None else [member()]
    scope_hash = canonical_sha256(members)
    review = {
        "reviewer_id": "independent-reviewer",
        "reviewed_at": "2026-10-02T05:00:00Z",
        "status": "approved",
        "member_set_sha256": scope_hash,
        "basis": "Checked the frozen SGF and second GN against its GC value",
    }
    review["review_signature"] = canonical_sha256(review)
    return {
        "selection_format": 1,
        "rule_version": RULE,
        "members": members,
        "member_set_sha256": scope_hash,
        "producer_id": "producer",
        "review": review,
    }


def counts(engine):
    with engine.connect() as conn:
        return (
            conn.scalar(select(func.count()).select_from(KifuEventSelectionBatch)),
            conn.scalar(select(func.count()).select_from(KifuAlbumEventSelection)),
        )


def test_exact_shared_predicate_rejects_lookalikes():
    from katrain.web.kifu.event_selection import selected_second_gn

    assert selected_second_gn(SGF.parse_sgf(SGF_TEXT), "19x19") == member()["selected_raw"]
    mutations = [
        SGF_TEXT.replace("GN[GNUGo3.8]", "EV[Official]GN[GNUGo3.8]"),
        SGF_TEXT.replace("GN[GNUGo3.8]", "GN[Extra]GN[GNUGo3.8]"),
        SGF_TEXT.replace("https://19x19.com", "https://other.example"),
        SGF_TEXT.replace("GN[第5届韩国最强棋士战预选]", "GN[GNUGo4.0]"),
        SGF_TEXT.replace("GN[第5届韩国最强棋士战预选]", "GN[第5届]"),
        SGF_TEXT.replace("GC[第5届韩国最强棋士战预选 | 194手]", "GC[Other event]"),
        SGF_TEXT.replace("GC[第5届韩国最强棋士战预选 | 194手]", "GC[第5届韩国最强棋士战预选 | 194手]GC[Other event]"),
    ]
    for value in mutations:
        assert selected_second_gn(SGF.parse_sgf(value), "19x19") is None
    assert selected_second_gn(SGF.parse_sgf(SGF_TEXT), "CWI_History_Full") is None


def test_validate_and_dry_run_do_not_write(engine):
    from katrain.web.kifu.event_selection import dry_run_bundle, validate_bundle

    reviewed = bundle()
    before = counts(engine)
    assert validate_bundle(reviewed)["member_count"] == 1
    assert dry_run_bundle(engine, reviewed)["status"] == "ready"
    assert counts(engine) == before == (0, 0)


@pytest.mark.parametrize(
    "field,changed",
    [
        ("event", "Other"),
        ("event_id", 2),
        ("source", "Other"),
        ("source_path", "data/kifu-album/19x19/other.sgf"),
        ("date_played", "1934-10-11"),
        ("round_name", "Round 2"),
        ("board_size", 13),
        ("sgf_content", SGF_TEXT + " "),
    ],
)
def test_live_preimage_drift_blocks_apply(engine, field, changed):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle

    reviewed = bundle()
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1).values(**{field: changed}))
    with pytest.raises(EventSelectionError, match="preimage|SGF"):
        apply_bundle(engine, reviewed)
    assert counts(engine) == (0, 0)


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b["members"].append(deepcopy(b["members"][0])),
        lambda b: b["members"][0].update(selected_raw="Wrong"),
        lambda b: b["review"].update(reviewer_id="producer"),
        lambda b: b["review"].update(review_signature="0" * 64),
    ],
)
def test_invalid_member_or_review_blocks_apply(engine, change):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle

    reviewed = bundle()
    change(reviewed)
    with pytest.raises(EventSelectionError):
        apply_bundle(engine, reviewed)
    assert counts(engine) == (0, 0)


def test_atomic_apply_retry_and_undo_preserve_original_album(engine):
    from katrain.web.kifu.event_selection import apply_bundle, batch_status, undo_batch

    reviewed = bundle()
    with engine.connect() as conn:
        album_before = conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 1)).mappings().one()
    applied = apply_bundle(engine, reviewed)
    assert applied["status"] == "applied"
    assert counts(engine) == (1, 1)
    assert apply_bundle(engine, reviewed)["status"] == "already_applied"
    assert counts(engine) == (1, 1)
    with engine.connect() as conn:
        selection = conn.execute(select(KifuAlbumEventSelection.__table__)).mappings().one()
        assert selection["selected_raw"] == member()["selected_raw"]
        assert selection["sgf_sha256"] == member()["sgf_sha256"]
        assert conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 1)).mappings().one() == album_before
    assert batch_status(engine, applied["batch_id"])["status"] == "applied"
    assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
    assert counts(engine) == (1, 0)
    with engine.connect() as conn:
        assert conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 1)).mappings().one() == album_before


def test_undo_refuses_later_selection_edit(engine):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle, undo_batch

    applied = apply_bundle(engine, bundle())
    with engine.begin() as conn:
        conn.execute(
            KifuAlbumEventSelection.__table__.update()
            .where(KifuAlbumEventSelection.album_id == 1)
            .values(selected_raw="Later edit")
        )
    with pytest.raises(EventSelectionError, match="changed"):
        undo_batch(engine, applied["batch_id"])
    assert counts(engine) == (1, 1)


def test_undo_refuses_corrupt_batch_audit(engine):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle, undo_batch

    applied = apply_bundle(engine, bundle())
    with engine.begin() as conn:
        conn.execute(
            KifuEventSelectionBatch.__table__.update()
            .where(KifuEventSelectionBatch.id == applied["batch_id"])
            .values(reviewed_artifact={"bundle": bundle(), "before_images": [], "after_images": []})
        )
    with pytest.raises(EventSelectionError, match="audit"):
        undo_batch(engine, applied["batch_id"])
    assert counts(engine) == (1, 1)


def test_existing_selection_blocks_new_bundle(engine):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle

    apply_bundle(engine, bundle())
    another = bundle()
    another["review"]["basis"] = "Separate review of same member"
    another["review"]["review_signature"] = canonical_sha256(
        {key: value for key, value in another["review"].items() if key != "review_signature"}
    )
    with pytest.raises(EventSelectionError, match="already selected"):
        apply_bundle(engine, another)
    assert counts(engine) == (1, 1)


def test_multi_member_stale_preimage_rolls_back_whole_batch(engine):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle

    second = {**member(), "album_id": 2, "old_source_path": "data/kifu-album/19x19/b.sgf"}
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=2,
                player_black="Black",
                player_white="White",
                event="Changed",
                source="https://19x19.com",
                source_path=second["old_source_path"],
                date_played=second["old_date_played"],
                round_name=second["old_round_name"],
                board_size=19,
                sgf_content=SGF_TEXT,
            )
        )
    with pytest.raises(EventSelectionError, match="preimage"):
        apply_bundle(engine, bundle(members=[member(), second]))
    assert counts(engine) == (0, 0)


def test_retry_refuses_changed_selection_without_writing(engine):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle

    reviewed = bundle()
    apply_bundle(engine, reviewed)
    with engine.begin() as conn:
        conn.execute(
            KifuAlbumEventSelection.__table__.update()
            .where(KifuAlbumEventSelection.album_id == 1)
            .values(selected_raw="Later edit")
        )
    with pytest.raises(EventSelectionError, match="changed"):
        apply_bundle(engine, reviewed)
    assert counts(engine) == (1, 1)


def test_retry_refuses_changed_source_album_without_writing(engine):
    from katrain.web.kifu.event_selection import EventSelectionError, apply_bundle

    reviewed = bundle()
    apply_bundle(engine, reviewed)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1).values(round_name="Later edit"))
    with pytest.raises(EventSelectionError, match="changed"):
        apply_bundle(engine, reviewed)
    assert counts(engine) == (1, 1)


def test_malformed_pinned_sgf_fails_as_review_error(engine):
    from katrain.web.kifu.event_selection import EventSelectionError, dry_run_bundle

    malformed = "(;BROKEN"
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1).values(sgf_content=malformed))
    revised = member()
    revised["sgf_sha256"] = sgf_sha256(malformed)
    with pytest.raises(EventSelectionError, match="SGF cannot be checked"):
        dry_run_bundle(engine, bundle(members=[revised]))


def test_cli_validate_and_status_are_structured(tmp_path, capsys):
    from scripts.kifu_event_selection import main

    reviewed = bundle()
    artifact = tmp_path / "bundle.json"
    artifact.write_text(json.dumps(reviewed, ensure_ascii=False), encoding="utf-8")
    assert main(["validate", "--bundle", str(artifact)]) == 0
    assert json.loads(capsys.readouterr().out)["member_count"] == 1


def test_cli_dry_run_apply_status_and_undo(tmp_path, capsys):
    from scripts.kifu_event_selection import main

    database_url = f"sqlite:///{tmp_path / 'catalog.sqlite'}"
    db = create_engine(database_url)
    Base.metadata.create_all(db)
    with db.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=1,
                player_black="Black",
                player_white="White",
                event="GNUGo3.8",
                source="https://19x19.com",
                source_path=member()["old_source_path"],
                date_played=member()["old_date_played"],
                round_name=member()["old_round_name"],
                board_size=19,
                sgf_content=SGF_TEXT,
            )
        )
    db.dispose()
    artifact = tmp_path / "bundle.json"
    artifact.write_text(json.dumps(bundle(), ensure_ascii=False), encoding="utf-8")

    def run(*args):
        assert main(list(args)) == 0
        return json.loads(capsys.readouterr().out)

    preview = run("dry-run", "--bundle", str(artifact), "--database-url", database_url)
    assert preview["status"] == "ready"
    applied = run("apply", "--bundle", str(artifact), "--database-url", database_url)
    assert applied["change_count"] == 1
    batch_id = applied["batch_id"]
    assert run("status", "--batch-id", str(batch_id), "--database-url", database_url)["status"] == "applied"
    assert run("undo", "--batch-id", str(batch_id), "--database-url", database_url)["status"] == "undone"
