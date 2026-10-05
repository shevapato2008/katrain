import copy

import pytest
from sqlalchemy.orm import Session, sessionmaker

from scripts import kifu_batch_transfer as batch
from scripts import sync_kifu_analysis as sync
from katrain.cron.models import KifuAlbumDB as Album, KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move, ReportTaskDB
from tests.test_kifu_batch_transfer import database, game, put_catalog, result_for


def reports(games):
    body = {
        "format": "kifu-report-sync-v1",
        "model_sha256": batch.MODEL_SHA256,
        "requested_visits": batch.VISITS,
        "games": [{**g, **result_for(g)} for g in games],
    }
    return {**body, "reports_sha256": batch.digest(body)}


def test_export_requires_completed_exact_sgf_model_and_full_depth(database):
    selected = game(123)
    put_catalog(database, [selected])
    sessions = sessionmaker(bind=database)
    batch.import_game(sessions, selected, result_for(selected), apply=True)
    artifact = sync.export_reports(database, [123])
    assert [g["album_id"] for g in sync.validate_reports(artifact)] == [123]
    with sessions() as db, db.begin():
        db.get(Album, 123).sgf_content += " "
    with pytest.raises(batch.BatchError, match="completed identity"):
        sync.export_reports(database, [123])
    with sessions() as db, db.begin():
        db.get(Album, 123).sgf_content = selected["sgf_content"]
        db.query(Move).first().root_visits = 1999
    with pytest.raises(batch.BatchError, match="Invalid stored analysis"):
        sync.export_reports(database, [123])


def test_sync_preflights_every_target_before_any_writes(database):
    games = [game(123), game(124)]
    put_catalog(database, games)
    with Session(database) as db, db.begin():
        db.get(Album, 124).sgf_content += " "
    with pytest.raises(batch.BatchError, match="124.*SGF changed"):
        sync.import_reports(database, sync.validate_reports(reports(games)), apply=True)
    with Session(database) as db:
        assert db.query(Job).count() == db.query(Move).count() == 0


def test_sync_validates_artifact_is_dry_by_default_and_idempotent(database):
    games = [game(123), game(124)]
    put_catalog(database, games)
    artifact = reports(games)
    changed = copy.deepcopy(artifact)
    changed["games"][0]["moves"][0]["winrate"] = 0.6
    with pytest.raises(batch.BatchError, match="checksum"):
        sync.validate_reports(changed)
    changed = copy.deepcopy(artifact)
    changed["model_sha256"] = "0" * 64
    with pytest.raises(batch.BatchError, match="model/visits"):
        sync.validate_reports(changed)
    rows = sync.validate_reports(artifact)
    with Session(database) as db, db.begin():
        db.add(ReportTaskDB(id=9000, user_id=1, user_game_id="untouched", status="pending"))
    assert {r["action"] for r in sync.import_reports(database, rows)} == {"insert"}
    with Session(database) as db:
        assert db.query(Job).count() == 0
    assert {r["action"] for r in sync.import_reports(database, rows, apply=True)} == {"insert"}
    assert {r["action"] for r in sync.import_reports(database, rows, apply=True)} == {"already_completed"}
    with Session(database) as db:
        assert db.query(Job).count() == 2
        assert db.query(Move).count() == 4
        assert db.get(ReportTaskDB, 9000).status == "pending"
        assert [a.sgf_content for a in db.query(Album).order_by(Album.id)] == [g["sgf_content"] for g in games]
