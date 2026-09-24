"""The dedicated admin tutorial writer uses local, isolated SQLite only."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core import models_db


BOARD = {"size": 19, "stones": {"B": [[3, 3]], "W": []}}
URL = "/api/admin/tutorials/figures/1"


@pytest.fixture
def writer(tmp_path, monkeypatch):
    from katrain.web.admin.routers import tutorials
    from katrain.web.admin.session import get_current_admin
    from katrain.web.core.storage.local import LocalStorageBackend

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models_db.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        book = models_db.TutorialBook(
            category="布局", subcategory="棋书", title="Test", slug="test-book", asset_dir="x"
        )
        db.add(book)
        db.flush()
        chapter = models_db.TutorialChapter(book_id=book.id, chapter_number="1", title="Test", order=1)
        db.add(chapter)
        db.flush()
        section = models_db.TutorialSection(chapter_id=chapter.id, section_number="1", title="Test", order=1)
        db.add(section)
        db.flush()
        db.add(models_db.TutorialFigure(id=1, section_id=section.id, page=1, figure_label="图1", order=1))
        db.commit()
        db.execute(update(models_db.TutorialFigure).where(models_db.TutorialFigure.id == 1).values(updated_at=None))
        db.commit()

    app = FastAPI()
    app.state.session_factory = Session
    app.include_router(tutorials.router, prefix="/api/admin/tutorials")
    app.dependency_overrides[get_current_admin] = lambda: {"realm": "admin", "username": "admin:fan"}
    monkeypatch.setattr(tutorials, "get_storage_backend", lambda: LocalStorageBackend(tmp_path))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, Session, tutorials, tmp_path
    engine.dispose()


def _version(client):
    return client.put(f"{URL}/narration", json={"narration": "first", "expected_updated_at": None}).json()["updated_at"]


def test_missing_version_and_unknown_media_fields_rejected(writer):
    client, Session, _, _ = writer
    assert client.put(f"{URL}/board", json={"board_payload": BOARD}).status_code == 422
    assert client.put(f"{URL}/narration", json={"narration": "x", "expected_updated_at": "bad"}).status_code == 422
    assert (
        client.put(
            f"{URL}/narration", json={"narration": "x", "expected_updated_at": None, "audio_asset": "forged.mp3"}
        ).status_code
        == 422
    )
    assert client.put(f"{URL}/verify", json={"expected_updated_at": None, "verified_by": "forged"}).status_code == 422
    with Session() as db:
        assert db.get(models_db.TutorialFigure, 1).updated_at is None


def test_board_cas_history_audit_and_invalidates_old_board_samples(writer):
    client, Session, _, _ = writer
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.recognition_debug = {"human_verified": True, "verified_by": "old", "classification": {"label_map": {}}}
        figure.narration = "old"
        figure.audio_asset = "old.mp3"
        figure.video_asset = "old.mp4"
        figure.video_duration_ms = 12000
        figure.video_size_bytes = 3456
        db.add(
            models_db.TrainingSample(
                figure_id=1,
                patch_label="A",
                local_col=0,
                local_row=0,
                global_col=0,
                global_row=0,
                patch_image_path="old.png",
                base_type="empty",
            )
        )
        db.commit()
        db.execute(update(models_db.TutorialFigure).where(models_db.TutorialFigure.id == 1).values(updated_at=None))
        db.commit()

    response = client.put(
        f"{URL}/board", json={"board_payload": BOARD, "expected_updated_at": None, "narration": "new"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["board_payload"]["viewport"] is not None
    assert body["recognition_debug"]["human_verified"] is False
    assert body["audio_asset"] is None
    assert body["video_asset"] is None
    assert body["video_duration_ms"] is None
    assert body["video_size_bytes"] is None
    assert body["updated_at"] is not None
    with Session() as db:
        assert db.query(models_db.TrainingSample).filter_by(figure_id=1).count() == 0
        history = db.query(models_db.BoardPayloadHistory).one()
        assert history.changed_by == "admin:fan"
        audit = db.query(models_db.AdminAuditLog).one()
        assert (audit.actor_realm, audit.actor_username, audit.action, audit.target_id) == (
            "admin",
            "admin:fan",
            "tutorial.board",
            1,
        )

    stale = client.put(f"{URL}/board", json={"board_payload": BOARD, "expected_updated_at": None})
    assert stale.status_code == 409
    with Session() as db:
        assert db.query(models_db.BoardPayloadHistory).count() == 1
        assert db.query(models_db.AdminAuditLog).count() == 1


def test_narration_versions_increase_and_preserve_audio_if_text_same(writer):
    client, Session, _, _ = writer
    with Session() as db:
        db.get(models_db.TutorialFigure, 1).audio_asset = "current.mp3"
        db.get(models_db.TutorialFigure, 1).video_asset = "current.mp4"
        db.get(models_db.TutorialFigure, 1).video_duration_ms = 12000
        db.get(models_db.TutorialFigure, 1).video_size_bytes = 3456
        db.commit()
        db.execute(update(models_db.TutorialFigure).where(models_db.TutorialFigure.id == 1).values(updated_at=None))
        db.commit()
    first = client.put(f"{URL}/narration", json={"narration": "first", "expected_updated_at": None})
    assert first.status_code == 200, first.text
    assert first.json()["audio_asset"] is None
    assert first.json()["video_asset"] is None
    assert first.json()["video_duration_ms"] is None
    assert first.json()["video_size_bytes"] is None
    version = first.json()["updated_at"]
    second = client.put(f"{URL}/narration", json={"narration": "first", "expected_updated_at": version})
    assert second.status_code == 200, second.text
    assert datetime.fromisoformat(second.json()["updated_at"]) > datetime.fromisoformat(version)
    assert (
        client.put(f"{URL}/narration", json={"narration": "stale", "expected_updated_at": version}).status_code == 409
    )


def test_unknown_figure_returns_404(writer):
    client, _, _, _ = writer
    assert (
        client.put(
            "/api/admin/tutorials/figures/404/narration", json={"narration": "x", "expected_updated_at": None}
        ).status_code
        == 404
    )


def test_audit_failure_rolls_back_business_change(writer):
    client, Session, _, _ = writer
    from sqlalchemy import event

    @event.listens_for(Session, "before_flush")
    def fail_audit(session, *_):
        if any(isinstance(item, models_db.AdminAuditLog) for item in session.new):
            raise RuntimeError("audit unavailable")

    try:
        assert (
            client.put(
                f"{URL}/narration", json={"narration": "must roll back", "expected_updated_at": None}
            ).status_code
            >= 500
        )
    finally:
        event.remove(Session, "before_flush", fail_audit)
    with Session() as db:
        assert db.get(models_db.TutorialFigure, 1).narration is None


def test_tts_failure_leaves_database_untouched_and_retry_binds_versioned_asset(writer, monkeypatch):
    client, Session, tutorials, tmp_path = writer
    with Session() as db:
        db.get(models_db.TutorialFigure, 1).video_asset = "old.mp4"
        db.get(models_db.TutorialFigure, 1).video_duration_ms = 12000
        db.get(models_db.TutorialFigure, 1).video_size_bytes = 3456
        db.commit()
        db.execute(update(models_db.TutorialFigure).where(models_db.TutorialFigure.id == 1).values(updated_at=None))
        db.commit()

    async def failing(_text, _path):
        raise RuntimeError("TTS unavailable")

    monkeypatch.setattr(tutorials, "_synthesize_audio", failing)
    failed = client.post(f"{URL}/generate-audio", json={"narration": "spoken", "expected_updated_at": None})
    assert failed.status_code == 502
    with Session() as db:
        fig = db.get(models_db.TutorialFigure, 1)
        assert fig.narration is None and fig.audio_asset is None and fig.video_asset == "old.mp4"
        assert fig.video_duration_ms == 12000 and fig.video_size_bytes == 3456
        assert fig.updated_at is None

    async def succeeding(_text, path):
        path.write_bytes(b"MP3 test bytes")

    monkeypatch.setattr(tutorials, "_synthesize_audio", succeeding)
    saved = client.post(f"{URL}/generate-audio", json={"narration": "spoken", "expected_updated_at": None})
    assert saved.status_code == 200, saved.text
    key = saved.json()["audio_asset"]
    assert key.startswith("tutorial_assets/test-book/audio/fig_1_") and key.endswith(".mp3")
    assert (tmp_path / key).read_bytes() == b"MP3 test bytes"
    assert saved.json()["narration"] == "spoken"
    assert saved.json()["video_asset"] is None
    assert saved.json()["video_duration_ms"] is None
    assert saved.json()["video_size_bytes"] is None


def test_tts_upload_failure_does_not_commit_narration(writer, monkeypatch):
    client, Session, tutorials, _ = writer

    async def succeeding(_text, path):
        path.write_bytes(b"audio")

    class FailingStorage:
        def put(self, *_args, **_kwargs):
            raise RuntimeError("object storage unavailable")

    monkeypatch.setattr(tutorials, "_synthesize_audio", succeeding)
    monkeypatch.setattr(tutorials, "get_storage_backend", FailingStorage)
    response = client.post(f"{URL}/generate-audio", json={"narration": "new text", "expected_updated_at": None})
    assert response.status_code == 502
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.narration is None and figure.audio_asset is None and figure.updated_at is None


def test_tts_detects_a_conflict_after_upload(writer, monkeypatch):
    client, Session, tutorials, tmp_path = writer

    async def racing_generation(_text, path):
        path.write_bytes(b"audio")
        with Session() as db:
            db.execute(
                update(models_db.TutorialFigure)
                .where(models_db.TutorialFigure.id == 1)
                .values(narration="another editor", updated_at=datetime.now(timezone.utc))
            )
            db.commit()

    monkeypatch.setattr(tutorials, "_synthesize_audio", racing_generation)
    response = client.post(f"{URL}/generate-audio", json={"narration": "stale", "expected_updated_at": None})
    assert response.status_code == 409
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.narration == "another editor" and figure.audio_asset is None
        assert db.query(models_db.AdminAuditLog).count() == 0
    assert len(list(tmp_path.rglob("fig_1_*.mp3"))) == 1


def test_missing_audit_table_returns_unavailable_and_rolls_back(writer):
    client, Session, _, _ = writer
    models_db.AdminAuditLog.__table__.drop(Session.kw["bind"])
    response = client.put(f"{URL}/narration", json={"narration": "uncommitted", "expected_updated_at": None})
    assert response.status_code == 503
    assert response.json()["detail"] == "Admin audit table unavailable"
    with Session() as db:
        assert db.get(models_db.TutorialFigure, 1).narration is None


def test_verify_reports_skipped_export_and_preserves_version_contract(writer):
    client, Session, _, _ = writer
    response = client.put(f"{URL}/verify", json={"expected_updated_at": None})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["figure"]["recognition_debug"]["human_verified"] is True
    assert body["figure"]["recognition_debug"]["verified_by"] == "admin:fan"
    assert body["training_export"]["status"] == "skipped"
    assert body["training_export"]["count"] == 0
    assert body["training_export"]["reason"]
    with Session() as db:
        assert db.query(models_db.AdminAuditLog).count() == 1
    assert client.put(f"{URL}/verify", json={"expected_updated_at": None}).status_code == 409


def test_verify_reports_failed_export_without_losing_verified_status(writer, monkeypatch):
    client, Session, tutorials, tmp_path = writer
    import sys
    from types import SimpleNamespace

    crop = tmp_path / "tutorial_assets" / "test-book" / "debug" / "图1" / "crop.png"
    crop.parent.mkdir(parents=True)
    crop.write_bytes(b"crop")
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.board_payload = BOARD
        figure.recognition_debug = {"classification": {"label_map": {"A": [0, 0]}}}
        db.commit()
        db.execute(update(models_db.TutorialFigure).where(models_db.TutorialFigure.id == 1).values(updated_at=None))
        db.commit()

    def failed_export(db, figure, **_kwargs):
        db.add(
            models_db.TrainingSample(
                figure_id=figure.id,
                patch_label="A",
                local_col=0,
                local_row=0,
                global_col=0,
                global_row=0,
                patch_image_path="partial.png",
                base_type="empty",
            )
        )
        db.flush()
        raise RuntimeError("crop processing failed")

    monkeypatch.setitem(
        sys.modules,
        "katrain.web.tutorials.training_export",
        SimpleNamespace(export_figure_training_samples=failed_export),
    )
    response = client.put(f"{URL}/verify", json={"expected_updated_at": None})
    assert response.status_code == 200, response.text
    assert response.json()["training_export"] == {"status": "failed", "count": 0, "reason": "training_export_error"}
    with Session() as db:
        assert db.get(models_db.TutorialFigure, 1).recognition_debug["human_verified"] is True
        assert db.query(models_db.TrainingSample).count() == 0


def test_verify_exports_samples_in_the_audited_transaction(writer, monkeypatch):
    client, Session, _, tmp_path = writer
    import sys
    from types import SimpleNamespace

    crop = tmp_path / "tutorial_assets" / "test-book" / "debug" / "图1" / "crop.png"
    crop.parent.mkdir(parents=True)
    crop.write_bytes(b"crop")
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.board_payload = BOARD
        figure.recognition_debug = {"classification": {"label_map": {"A": [0, 0]}}}
        db.commit()
        db.execute(update(models_db.TutorialFigure).where(models_db.TutorialFigure.id == 1).values(updated_at=None))
        db.commit()

    def sample_export(db, figure, *, commit, asset_base, book_slug):
        assert commit is False
        assert asset_base == tmp_path
        assert book_slug == "test-book"
        db.add(
            models_db.TrainingSample(
                figure_id=figure.id,
                patch_label="A",
                local_col=0,
                local_row=0,
                global_col=0,
                global_row=0,
                patch_image_path="sample.png",
                base_type="black",
            )
        )
        return 1

    monkeypatch.setitem(
        sys.modules,
        "katrain.web.tutorials.training_export",
        SimpleNamespace(export_figure_training_samples=sample_export),
    )
    response = client.put(f"{URL}/verify", json={"expected_updated_at": None})
    assert response.status_code == 200, response.text
    assert response.json()["training_export"] == {"status": "exported", "count": 1, "reason": None}
    with Session() as db:
        assert db.query(models_db.TrainingSample).count() == 1
        assert db.query(models_db.BoardPayloadHistory).one().changed_by == "admin:fan"
        assert db.query(models_db.AdminAuditLog).one().action == "tutorial.verify"


def test_verify_audit_failure_rolls_back_exported_sample_and_verification(writer, monkeypatch):
    client, Session, _, tmp_path = writer
    import sys
    from types import SimpleNamespace
    from sqlalchemy import event

    crop = tmp_path / "tutorial_assets" / "test-book" / "debug" / "图1" / "crop.png"
    crop.parent.mkdir(parents=True)
    crop.write_bytes(b"crop")
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.board_payload = BOARD
        figure.recognition_debug = {"classification": {"label_map": {"A": [0, 0]}}}
        db.commit()
        db.execute(update(models_db.TutorialFigure).where(models_db.TutorialFigure.id == 1).values(updated_at=None))
        db.commit()

    def sample_export(db, figure, **_kwargs):
        db.add(
            models_db.TrainingSample(
                figure_id=figure.id,
                patch_label="A",
                local_col=0,
                local_row=0,
                global_col=0,
                global_row=0,
                patch_image_path="sample.png",
                base_type="black",
            )
        )
        db.flush()
        return 1

    monkeypatch.setitem(
        sys.modules,
        "katrain.web.tutorials.training_export",
        SimpleNamespace(export_figure_training_samples=sample_export),
    )

    @event.listens_for(Session, "before_flush")
    def fail_audit(session, *_):
        if any(isinstance(item, models_db.AdminAuditLog) for item in session.new):
            raise RuntimeError("audit unavailable")

    try:
        assert client.put(f"{URL}/verify", json={"expected_updated_at": None}).status_code >= 500
    finally:
        event.remove(Session, "before_flush", fail_audit)
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.recognition_debug.get("human_verified") is not True
        assert figure.updated_at is None
        assert db.query(models_db.TrainingSample).count() == 0
        assert db.query(models_db.BoardPayloadHistory).count() == 0
