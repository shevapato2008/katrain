"""Manual review authority uses isolated fixtures; never a configured database."""

import asyncio
import copy
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event, text

from katrain.web.core import models_db
from test_tutorial_media import board, enqueue, media

ROOT = "/api/admin/tutorials/figures/1"


def version(factory):
    with factory() as db:
        value = db.get(models_db.TutorialFigure, 1).updated_at
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def approve(client, factory):
    response = client.put(ROOT + "/verify-board", json={"expected_updated_at": version(factory)})
    assert response.status_code == 200, response.text
    return response.json()


def test_static_review_digest_excludes_replay_and_includes_evidence():
    from katrain.web.tutorials.manual_review import board_content_sha256

    figure = SimpleNamespace(board_payload=board(), page=1, bbox=None, page_image_path="source.png")
    original = board_content_sha256(figure)
    figure.board_payload["replay"] = {"status": "needs_calibration"}
    assert board_content_sha256(figure) == original
    figure.board_payload["source_region"]["confirmed"] = False
    assert board_content_sha256(figure) != original
    figure.board_payload = board()
    figure.page_image_path = "other-source.png"
    assert board_content_sha256(figure) != original


@pytest.mark.parametrize("kind", ["audio", "video"])
def test_unapproved_or_historical_flags_never_enqueue(media, kind):
    client, factory, worker, storage, app = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.board_review = None
        figure.recognition_debug = {"human_verified": True, "calibration_review": {"board": {"verified_by": "old"}}}
        db.commit()
    response = enqueue(client, kind=kind, version=version(factory))
    assert response.status_code == 422
    assert "approval" in response.json()["detail"].lower()
    with factory() as db:
        assert db.query(models_db.TutorialMediaTask).count() == 0


def test_review_authenticated_persisted_cas_and_independent_from_replay(media):
    client, factory, worker, storage, app = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        value = board()
        value["replay"] = {"status": "needs_calibration", "initial": None, "moves": []}
        figure.board_payload = value
        figure.board_review = None
        db.commit()
    old = version(factory)
    result = approve(client, factory)
    record = result["board_review"]
    assert record["reviewed_by"] == "admin:test" and len(record["content_sha256"]) == 64
    assert result["review_validity"]["board"] == {"approved": True, "reason": None}
    assert result["video_2d_review"] is None
    assert client.put(ROOT + "/verify-board", json={"expected_updated_at": old}).status_code == 409
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).board_review == record


def test_board_review_audit_failure_rolls_back(media):
    client, factory, worker, storage, app = media
    with factory() as db:
        db.get(models_db.TutorialFigure, 1).board_review = None
        db.commit()

    @event.listens_for(factory, "before_flush")
    def reject(session, *_):
        if any(
            isinstance(row, models_db.AdminAuditLog) and row.action == "tutorial.verify_board" for row in session.new
        ):
            raise RuntimeError("audit unavailable")

    try:
        response = client.put(ROOT + "/verify-board", json={"expected_updated_at": version(factory)})
        assert response.status_code == 500
    finally:
        event.remove(factory, "before_flush", reject)
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).board_review is None


@pytest.mark.parametrize("change", ["board", "review"])
def test_queued_task_loses_authority_before_tts(media, monkeypatch, change):
    client, factory, worker, storage, app = media
    task = enqueue(client).json()["task"]
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        if change == "board":
            payload = copy.deepcopy(figure.board_payload)
            payload["letters"] = {"8,8": "X"}
            figure.board_payload = payload
        else:
            record = copy.deepcopy(figure.board_review)
            record["reviewed_at"] = "2099-01-01T00:00:00+00:00"
            figure.board_review = record
        db.commit()

    def forbidden(*args):
        raise AssertionError("must reject before generation")

    monkeypatch.setattr(worker, "_generate", forbidden)
    worker.run_next()
    with factory() as db:
        row = db.get(models_db.TutorialMediaTask, task["id"])
        assert row.status == "stale" and "approval" in row.error.lower()
        assert db.get(models_db.TutorialFigure, 1).audio_asset is None


def test_rereview_during_audio_prevents_publication(media, monkeypatch):
    from katrain.web.tutorials import media_tasks

    client, factory, worker, storage, app = media
    task = enqueue(client).json()["task"]

    async def speech(text, voice, path):
        approve(client, factory)
        path.write_bytes(b"audio")
        return [{"text": text, "start_ms": 0, "duration_ms": 3000}]

    monkeypatch.setattr(media_tasks, "synthesize_audio", speech)
    worker.run_next()
    with factory() as db:
        assert db.get(models_db.TutorialMediaTask, task["id"]).status == "stale"
        assert db.get(models_db.TutorialFigure, 1).audio_asset is None


def test_legacy_generation_rejected_before_synthesis(media, monkeypatch):
    from katrain.web.admin.routers import tutorials

    client, factory, worker, storage, app = media

    async def forbidden(*args):
        raise AssertionError("legacy must not call TTS")

    monkeypatch.setattr(tutorials, "_synthesize_audio", forbidden)
    response = client.post(ROOT + "/generate-audio", json={"narration": "text", "expected_updated_at": None})
    assert response.status_code == 409
    assert "media-tasks" in response.json()["detail"]


def test_old_batch_entrypoints_reject_before_database_or_backfill(monkeypatch):
    from scripts import generate_video, generate_voice

    def forbidden():
        raise AssertionError("legacy must reject before opening DB")

    monkeypatch.setattr(generate_video, "SessionLocal", forbidden)
    monkeypatch.setattr(generate_voice, "SessionLocal", forbidden)
    for coroutine in (
        generate_voice.process_section(1),
        generate_video.process_figure(1),
        generate_video.process_section(1),
    ):
        with pytest.raises(RuntimeError, match="media-tasks"):
            asyncio.run(coroutine)
    with pytest.raises(RuntimeError, match="media-tasks"):
        generate_video.concat_section_video(1)


def test_explicit_additive_review_migration_preserves_historical_flags():
    from sqlalchemy import create_engine, inspect
    from scripts.migrate_tutorial_reviews import migrate

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE tutorial_figures (id INTEGER PRIMARY KEY, recognition_debug JSON)"))
        connection.execute(
            text("INSERT INTO tutorial_figures VALUES (1, :value)"), {"value": '{"human_verified":true}'}
        )
        migrate(connection)
        migrate(connection)
        row = connection.execute(
            text("SELECT board_review, video_2d_review, video_3d_review, recognition_debug FROM tutorial_figures")
        ).one()
        assert row[:3] == (None, None, None)
        assert row[3] == '{"human_verified":true}'
        assert inspect(connection).get_table_names() == ["tutorial_figures"]
    engine.dispose()


def enqueue_historical_3d(media):
    """A queued row admitted before 2D-only creation remains processable/readable."""
    from katrain.web.tutorials.media_tasks import content_inputs
    from katrain.web.tutorials.media_timing import digest

    _, factory, *_ = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        inputs = content_inputs(figure, "video")
        task = models_db.TutorialMediaTask(
            figure_id=figure.id,
            kind="video",
            render_mode="3d",
            input_digest=digest(inputs),
            snapshot={
                **copy.deepcopy(inputs),
                "board_payload": copy.deepcopy(figure.board_payload),
                "book_slug": "test",
            },
            requested_by="historical-admin",
            status="queued",
            stage="queued",
        )
        db.add(task)
        db.commit()
        return {"id": task.id}


def generate_video(media, mode="2d"):
    client, factory, worker, storage, app = media
    if mode == "3d":
        task = enqueue_historical_3d(media)
    else:
        response = enqueue(client, kind="video", mode=mode, version=version(factory))
        assert response.status_code == 202, response.text
        task = response.json()["task"]
    worker.run_next()
    if mode == "3d":
        historical = client.get(f"/api/admin/tutorials/media-tasks/{task['id']}")
        assert historical.status_code == 200
        assert historical.json()["task"]["render_mode"] == "3d"
    with factory() as db:
        assert db.get(models_db.TutorialMediaTask, task["id"]).status == "succeeded"
        return db.get(models_db.TutorialFigure, 1).recognition_debug["workbench_media"]["videos"][mode]["asset"]


def approve_video(media, mode, asset, expected=None):
    client, factory, *_ = media
    return client.put(
        ROOT + "/approve-video",
        json={
            "render_mode": mode,
            "expected_asset": asset,
            "expected_updated_at": version(factory) if expected is None else expected,
        },
    )


def test_video_approval_exact_file_cas_and_independent_modes(media):
    client, factory, worker, storage, app = media
    first = generate_video(media)
    old_version = version(factory)
    response = approve_video(media, "2d", first)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["video_2d_review"]["asset"] == first
    assert result["video_2d_review"]["file_sha256"] == hashlib.sha256(b"video").hexdigest()
    assert result["review_validity"]["video_2d"]["approved"] is True
    assert approve_video(media, "2d", first, expected=old_version).status_code == 409
    second = generate_video(media, "3d")
    response = approve_video(media, "3d", second)
    assert response.status_code == 200, response.text
    assert response.json()["review_validity"]["video_2d"]["approved"]
    assert response.json()["review_validity"]["video_3d"]["approved"]
    generate_video(media)
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.video_2d_review is None and figure.video_3d_review is not None
    assert approve_video(media, "2d", first).status_code == 409


@pytest.mark.parametrize("mutation", ["missing", "bytes", "legacy", "dependencies"])
def test_video_approval_rejects_missing_changed_legacy_or_stale_artifacts(media, mutation):
    client, factory, worker, storage, app = media
    asset = generate_video(media)
    if mutation == "missing":
        storage.fspath(asset).unlink()
    elif mutation == "bytes":
        storage.put(asset, b"changed bytes")
    else:
        with factory() as db:
            figure = db.get(models_db.TutorialFigure, 1)
            debug = copy.deepcopy(figure.recognition_debug)
            if mutation == "legacy":
                debug["workbench_media"]["videos"]["2d"].pop("sha256")
            else:
                figure.narration = "changed directly"
            figure.recognition_debug = debug
            db.commit()
    response = approve_video(media, "2d", asset)
    assert response.status_code in (409, 422), response.text
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).video_2d_review is None


def test_video_review_does_not_stale_other_mode_job_and_audit_failure_rolls_back(media):
    client, factory, worker, storage, app = media
    asset = generate_video(media)
    task = enqueue_historical_3d(media)
    assert approve_video(media, "2d", asset).status_code == 200
    worker.run_next()
    with factory() as db:
        row = db.get(models_db.TutorialMediaTask, task["id"])
        assert row.status == "succeeded"
        other_asset = db.get(models_db.TutorialFigure, 1).recognition_debug["workbench_media"]["videos"]["3d"]["asset"]

    @event.listens_for(factory, "before_flush")
    def reject(session, *_):
        if any(
            isinstance(row, models_db.AdminAuditLog) and row.action == "tutorial.approve_video_3d"
            for row in session.new
        ):
            raise RuntimeError("audit unavailable")

    try:
        assert approve_video(media, "3d", other_asset).status_code == 500
    finally:
        event.remove(factory, "before_flush", reject)
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).video_3d_review is None


@pytest.mark.parametrize("edit", ["static", "replay", "narration"])
def test_edit_invalidates_only_dependent_reviews(media, edit):
    client, factory, worker, storage, app = media
    asset = generate_video(media)
    assert approve_video(media, "2d", asset).status_code == 200
    with factory() as db:
        original = copy.deepcopy(db.get(models_db.TutorialFigure, 1).board_review)
    if edit == "narration":
        response = client.put(
            ROOT + "/narration", json={"narration": "new exact text", "expected_updated_at": version(factory)}
        )
    else:
        payload = board()
        if edit == "static":
            payload["letters"] = {"8,8": "A"}
        else:
            payload["replay"]["evidence"]["description"] = "Updated replay evidence"
        response = client.put(
            ROOT + "/calibration", json={"board_payload": payload, "expected_updated_at": version(factory)}
        )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["video_2d_review"] is None and result["video_3d_review"] is None
    assert result["board_review"] == (original if edit == "narration" else None)
    assert result["review_validity"]["board"]["approved"] == (edit == "narration")


def test_startup_never_adds_review_columns_or_rebuilds_review_table():
    from sqlalchemy import create_engine, inspect
    from katrain.web.core import migrations

    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for name in ("board_review", "video_2d_review", "video_3d_review"):
            connection.execute(text(f'ALTER TABLE tutorial_figures DROP COLUMN "{name}"'))
    migrations.add_missing_columns(engine)
    names = {column["name"] for column in inspect(engine).get_columns("tutorial_figures")}
    assert not {"board_review", "video_2d_review", "video_3d_review"} & names
    assert "tutorial_figures" in migrations.PROTECTED_TABLES
    engine.dispose()


def test_public_figure_schema_does_not_expose_reviewer_identity(media):
    from katrain.web.tutorials.models import TutorialFigureOut

    client, factory, *_ = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        public = TutorialFigureOut.model_validate(figure).model_dump()
        assert "board_review" not in public and "video_2d_review" not in public


def test_static_video_allowed_without_sequence_review(media, monkeypatch):
    client, factory, worker, storage, app = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        payload = copy.deepcopy(figure.board_payload)
        payload["replay"] = {"status": "needs_calibration", "initial": None, "moves": []}
        figure.board_payload = payload
        db.commit()
    calls = []

    def render(**kwargs):
        calls.append(kwargs)
        kwargs["output_path"].write_bytes(b"static video")

    monkeypatch.setattr(worker, "_render_video", render)
    generate_video(media)
    assert calls[0]["frames"] == []
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.recognition_debug["workbench_media"]["videos"]["2d"]["playback_mode"] == "static"
        assert not (figure.recognition_debug or {}).get("calibration_review", {}).get("sequence")


def test_admin_figure_refresh_returns_review_fields_and_requires_auth(media):
    from katrain.web.admin.session import get_current_admin

    client, factory, worker, storage, app = media
    response = client.get(ROOT)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["board_review"]["reviewed_by"] == "isolated-fixture-reviewer"
    assert result["review_validity"]["board"] == {"approved": True, "reason": None}
    assert result["video_2d_review"] is None and result["video_3d_review"] is None
    app.dependency_overrides.pop(get_current_admin)
    assert client.get(ROOT).status_code == 401


def test_video_file_hash_does_not_require_python_311_file_digest(media, monkeypatch):
    monkeypatch.delattr(hashlib, "file_digest", raising=False)
    generate_video(media)
    with media[1]() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        video = figure.recognition_debug["workbench_media"]["videos"]["2d"]
        assert video["sha256"] == hashlib.sha256(b"video").hexdigest()


def test_board_review_persists_explicit_user_confirmation_provenance_with_cas(media):
    client, factory, worker, storage, app = media
    expected = version(factory)
    note = "- 确认通过，授权代为登记并生成"
    body = {"expected_updated_at": expected, "confirmation_source": "user_confirmation", "confirmation_note": note}
    response = client.put(ROOT + "/verify-board", json=body)
    assert response.status_code == 200, response.text
    record = response.json()["board_review"]
    assert record["confirmation_source"] == "user_confirmation"
    assert record["confirmation_note"] == note
    assert record["reviewed_by"] == "admin:test"
    assert record["reviewed_at"] and len(record["content_sha256"]) == 64
    assert client.put(ROOT + "/verify-board", json=body).status_code == 409
    refreshed = client.get(ROOT).json()
    assert refreshed["board_review"] == record
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).board_review == record
        audits = db.query(models_db.AdminAuditLog).filter_by(action="tutorial.verify_board").all()
        assert len(audits) == 1 and audits[0].actor_username == "admin:test"


def test_board_review_default_confirmation_source_is_admin_ui(media):
    client, factory, *_ = media
    record = approve(client, factory)["board_review"]
    assert record["confirmation_source"] == "admin_ui"
    assert record["confirmation_note"] is None


def test_board_review_confirmation_note_is_bounded(media):
    client, factory, *_ = media
    response = client.put(
        ROOT + "/verify-board",
        json={
            "expected_updated_at": version(factory),
            "confirmation_source": "user_confirmation",
            "confirmation_note": "x" * 1001,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("source_region", [None, {"col": 0, "row": 0, "cols": 9, "rows": 9, "confirmed": False}])
def test_explicit_review_accepts_unconfirmed_source_and_retains_unknown_stones(media, source_region):
    client, factory, *_ = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        value = board()
        value["source_region"] = source_region
        value["unknown_stones"] = [{"point": [8, 8], "color": None, "evidence": "visible unresolved color"}]
        value.pop("replay", None)
        figure.board_payload = value
        figure.board_review = None
        db.commit()
    result = approve(client, factory)
    assert result["review_validity"]["board"]["approved"] is True
    assert result["board_payload"]["unknown_stones"] == value["unknown_stones"]


def test_replay_edit_invalidates_manual_approval_but_narration_only_preserves_it(media):
    client, factory, *_ = media
    approved = approve(client, factory)
    payload = copy.deepcopy(approved["board_payload"])
    narration = client.put(
        ROOT + "/calibration",
        json={
            "expected_updated_at": approved["updated_at"],
            "board_payload": payload,
            "narration": "Only narration changes",
        },
    )
    assert narration.status_code == 200, narration.text
    assert narration.json()["board_review"] == approved["board_review"]
    payload["replay"] = {"status": "needs_calibration", "initial": None, "moves": []}
    response = client.put(
        ROOT + "/calibration", json={"expected_updated_at": narration.json()["updated_at"], "board_payload": payload}
    )
    assert response.status_code == 200, response.text
    assert response.json()["board_review"] is None
    assert response.json()["review_validity"]["board"]["approved"] is False
