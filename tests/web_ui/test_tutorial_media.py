"""Media authoring tests use isolated SQLite and local storage only."""

import copy

from katrain.web.tutorials.replay import validate_replay


def board():
    return {
        "schema_version": 2,
        "size": 9,
        "stones": {"B": [[0, 1], [1, 0], [2, 1], [1, 2], [1, 1]], "W": []},
        "unknown_stones": [],
        "labels": {"1,2": "41", "1,1": "43"},
        "source_region": {"col": 0, "row": 0, "cols": 9, "rows": 9, "confirmed": True},
        "viewport": {"col": 0, "row": 0, "cols": 9, "rows": 9},
        "replay": {
            "status": "complete",
            "initial": {
                "stones": {"B": [[0, 1], [1, 0], [2, 1]], "W": [[1, 1]]},
                "unknown_stones": [],
                "labels": {},
                "known_region": {"col": 0, "row": 0, "cols": 9, "rows": 9},
                "to_play": "B",
            },
            "moves": [
                {"kind": "move", "color": "B", "point": [1, 2], "printed_number": "41"},
                {"kind": "pass", "color": "W", "point": None, "printed_number": "42"},
                {"kind": "move", "color": "B", "point": [1, 1], "printed_number": "43"},
            ],
            "evidence": {"kind": "source", "source_pointer": "/p/1", "description": "checked"},
        },
    }


def test_replay_frames_capture_rewind_and_reuse_with_alive_annotations():
    from katrain.web.tutorials.replay import replay_frames

    value = board()
    value["replay"]["initial"]["labels"] = {"1,1": "old"}
    assert validate_replay(value)["status"] == "complete"
    frames = replay_frames(value)
    assert len(frames) == 4
    assert frames[1]["captured"] == [[1, 1]]
    assert frames[1]["payload"]["labels"] == {"1,2": "41"}
    assert frames[3]["payload"]["labels"] == {"1,2": "41", "1,1": "43"}
    assert frames[0]["payload"]["labels"] == {"1,1": "old"}
    assert frames[3]["last"] == [1, 1]
    assert replay_frames(value) == frames


def test_replay_draft_uses_only_contiguous_unique_alternating_numeric_labels():
    from katrain.web.tutorials.replay import replay_draft

    value = {
        "size": 9,
        "stones": {"B": [[8, 8], [1, 1], [3, 1]], "W": [[0, 1], [2, 1]]},
        "labels": {"0,1": "1", "1,1": "2", "2,1": "3", "3,1": "4"},
    }
    original = copy.deepcopy(value)
    draft = replay_draft(value)
    assert value == original
    assert draft["replay"]["status"] == "needs_calibration"
    assert draft["replay"]["initial"]["stones"] == {"B": [[8, 8]], "W": []}
    assert [item["color"] for item in draft["replay"]["moves"]] == ["W", "B", "W", "B"]
    assert draft["source_region"]["confirmed"] is False
    assert draft["replay"]["evidence"] is None
    value["labels"]["1,1"] = "1"
    assert replay_draft(value)["replay"]["moves"] == []


def test_timing_cues_resolve_color_printed_numbers_and_grouped_refs():
    from katrain.web.tutorials.media_timing import build_step_cues, digest

    value = board()
    text = "黑41，白42，再看黑43。"
    timing = {
        "audio_sha256": "a",
        "narration_sha256": __import__("hashlib").sha256(text.encode()).hexdigest(),
        "duration_ms": 4000,
        "boundaries": [
            {"text": part, "start_ms": i * 300, "duration_ms": 200}
            for i, part in enumerate(["黑", "41", "，", "白", "42", "，", "再看", "黑", "43", "。"])
        ],
    }
    cues = build_step_cues(value, text, timing)
    assert cues["status"] == "complete"
    assert [(x["step"], x["at_ms"]) for x in cues["cues"]] == [(0, 0), (1, 500), (2, 1400), (3, 2600)]
    assert cues["replay_sha256"] == digest(value["replay"])
    value["replay"]["moves"][0]["printed_number"] = "2"
    value["replay"]["moves"][2]["printed_number"] = "4"
    timing["boundaries"] = [{"text": "黑2、4", "start_ms": 500, "duration_ms": 600}]
    cues = build_step_cues(value, "黑2、4", timing)
    assert cues["status"] == "pending"  # white pass has no time strictly between grouped references
    assert cues["reason"]


def test_audio_stream_preserves_exact_text_and_uses_single_word_boundary_stream(tmp_path, monkeypatch):
    import asyncio
    import sys
    from types import SimpleNamespace
    from katrain.web.tutorials.media_timing import synthesize_audio

    calls = []

    class Communicate:
        def __init__(self, text, voice, **kwargs):
            calls.append((text, voice, kwargs))

        async def stream(self):
            yield {"type": "audio", "data": b"testmp3"}
            yield {"type": "WordBoundary", "text": "黑2", "offset": 10000000, "duration": 5000000}

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=Communicate))
    timing = asyncio.run(synthesize_audio("  原文黑2\n", "voice", tmp_path / "a.mp3"))
    assert calls == [("  原文黑2\n", "voice", {"boundary": "WordBoundary"})]
    assert timing == [{"text": "黑2", "start_ms": 1000, "duration_ms": 500}]
    assert (tmp_path / "a.mp3").read_bytes() == b"testmp3"


import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from katrain.web.core import models_db


@pytest.fixture
def media(tmp_path, monkeypatch):
    from katrain.web.admin.routers import tutorial_media, tutorial_workbench, tutorials
    from katrain.web.admin.session import get_current_admin
    from katrain.web.tutorials import media_tasks
    from katrain.web.tutorials.manual_review import board_content_sha256, make_review
    from katrain.web.core.storage.local import LocalStorageBackend

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models_db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(models_db.TutorialBook(id=1, category="布局", subcategory="棋书", title="c", slug="test", asset_dir="x"))
        db.flush()
        db.add(models_db.TutorialChapter(id=1, book_id=1, chapter_number="1", title="c", order=1))
        db.flush()
        db.add(models_db.TutorialSection(id=1, chapter_id=1, section_number="1", title="s", order=1))
        db.flush()
        db.add(
            models_db.TutorialFigure(
                id=1,
                section_id=1,
                page=1,
                figure_label="图1",
                order=1,
                narration="黑41，白42，再看黑43。",
                board_payload=board(),
            )
        )
        db.commit()
        figure = db.get(models_db.TutorialFigure, 1)
        figure.board_review = make_review({"username": "isolated-fixture-reviewer"}, board_content_sha256(figure))
        db.commit()
        db.execute(update(models_db.TutorialFigure).values(updated_at=None))
        db.commit()
    storage = LocalStorageBackend(tmp_path)

    def stub_renderer(**kwargs):
        kwargs["output_path"].write_bytes(b"video")

    worker = media_tasks.MediaWorker(factory, storage=storage, queue_limit=2)
    monkeypatch.setattr(worker, "_render_video", stub_renderer)
    app = FastAPI()
    app.state.admin_config = object()
    app.state.session_factory = factory
    app.state.media_worker = worker
    for router in (tutorial_media.router, tutorial_workbench.router, tutorials.router):
        app.include_router(router, prefix="/api/admin/tutorials")
    app.dependency_overrides[get_current_admin] = lambda: {"realm": "admin", "username": "admin:test"}

    async def speech(text, voice, path):
        path.write_bytes(b"generated audio")
        return [{"text": char, "start_ms": i * 100, "duration_ms": 80} for i, char in enumerate(text)]

    monkeypatch.setattr(media_tasks, "synthesize_audio", speech)
    monkeypatch.setattr(media_tasks, "probe_duration", lambda path: 4000)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, factory, worker, storage, app
    engine.dispose()


def enqueue(client, kind="audio", version=None, mode="2d"):
    return client.post(
        "/api/admin/tutorials/figures/1/media-tasks",
        json={"kind": kind, "render_mode": mode, "expected_updated_at": version},
    )


def test_task_api_auth_cas_queue_bound_and_recovery(media):
    client, factory, worker, storage, app = media
    denied = enqueue(client, version="2000-01-01T00:00:00Z")
    assert denied.status_code == 409
    assert enqueue(client).status_code == 202
    worker.queue_limit = 1
    assert enqueue(client, kind="video").status_code == 429
    worker.queue_limit = 2
    second = enqueue(client, kind="video")
    assert second.status_code == 202
    # Current creation is 2D only, even if the queue is already full.
    rejected = enqueue(client, kind="video", mode="3d")
    assert rejected.status_code == 422
    assert "2D" in rejected.json()["detail"]
    first_id = client.get("/api/admin/tutorials/figures/1/media-tasks").json()["tasks"][0]["id"]
    with factory() as db:
        db.get(models_db.TutorialMediaTask, first_id).status = "running"
        db.commit()
    worker.recover()
    assert client.get(f"/api/admin/tutorials/media-tasks/{first_id}").json()["task"]["status"] == "failed"
    assert worker.run_next()
    assert client.get(f"/api/admin/tutorials/media-tasks/{second.json()['task']['id']}").json()["task"]["status"] in (
        "succeeded",
        "failed",
    )
    from katrain.web.admin.session import get_current_admin

    app.dependency_overrides.pop(get_current_admin)
    assert client.get("/api/admin/tutorials/figures/1/media-tasks").status_code == 401


def test_audio_task_snapshot_publication_and_review_only_change(media, monkeypatch):
    client, factory, worker, storage, app = media
    task = enqueue(client).json()["task"]
    assert task["status"] == "queued"
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.recognition_debug = {"human_verified": True}
        db.commit()
    worker.run_next()
    result = client.get(f"/api/admin/tutorials/media-tasks/{task['id']}").json()["task"]
    assert result["status"] == "succeeded", result
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        metadata = figure.recognition_debug["workbench_media"]
        assert metadata["speech_timing"]["audio_sha256"] == metadata["audio"]["sha256"]
        assert storage.exists(figure.audio_asset)
        assert storage.exists(metadata["speech_timing"]["asset"])
        assert figure.recognition_debug["human_verified"] is True
        assert db.query(models_db.AdminAuditLog).count() == 2  # enqueue + publish


def test_generation_stale_content_or_upload_failure_never_binds(media, monkeypatch):
    from katrain.web.tutorials import media_tasks

    client, factory, worker, storage, app = media
    task = enqueue(client).json()["task"]

    async def changed(text, voice, path):
        with factory() as db:
            db.get(models_db.TutorialFigure, 1).narration = "new exact narration"
            db.commit()
        path.write_bytes(b"generated audio")
        return [{"text": char, "start_ms": i * 100, "duration_ms": 80} for i, char in enumerate(text)]

    monkeypatch.setattr(media_tasks, "synthesize_audio", changed)
    worker.run_next()
    assert client.get(f"/api/admin/tutorials/media-tasks/{task['id']}").json()["task"]["status"] == "stale"
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.audio_asset is None
        version = figure.updated_at.replace(tzinfo=__import__("datetime").timezone.utc).isoformat()
    task2 = enqueue(client, version=version).json()["task"]

    def failed(*args, **kwargs):
        raise RuntimeError("upload failed")

    monkeypatch.setattr(storage, "put", failed)
    worker.run_next()
    result = client.get(f"/api/admin/tutorials/media-tasks/{task2['id']}").json()["task"]
    assert result["status"] == "failed", result
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).audio_asset is None


def test_media_invalidation_preserves_speech_on_board_change(media):
    client, factory, worker, storage, app = media
    enqueue(client)
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        debug = copy.deepcopy(figure.recognition_debug)
        debug["workbench_media"].update(
            videos={"2d": {"asset": "a"}, "3d": {"asset": "b"}}, step_cues={"status": "complete"}
        )
        figure.recognition_debug = debug
        db.commit()
        version = figure.updated_at.replace(tzinfo=__import__("datetime").timezone.utc).isoformat()
    changed = board()
    changed["labels"]["1,1"] = "B43"
    response = client.put(
        "/api/admin/tutorials/figures/1/calibration", json={"board_payload": changed, "expected_updated_at": version}
    )
    assert response.status_code == 200, response.text
    metadata = response.json()["recognition_debug"]["workbench_media"]
    assert metadata["audio"] and metadata["speech_timing"]
    assert not metadata.get("videos") and not metadata.get("step_cues")
    response = client.put(
        "/api/admin/tutorials/figures/1/narration",
        json={"narration": "new", "expected_updated_at": response.json()["updated_at"]},
    )
    assert response.status_code == 200
    assert response.json()["recognition_debug"].get("workbench_media") == {}


def test_versioned_replay_draft_is_pure_and_not_saved(media):
    client, factory, worker, storage, app = media
    response = client.post("/api/admin/tutorials/figures/1/replay-draft", json={"expected_updated_at": None})
    assert response.status_code == 200, response.text
    assert response.json()["board_payload"]["replay"]["status"] == "needs_calibration"
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).board_payload == board()
    assert (
        client.post(
            "/api/admin/tutorials/figures/1/replay-draft", json={"expected_updated_at": "2000-01-01T00:00:00Z"}
        ).status_code
        == 409
    )


def test_identical_active_tasks_are_deduplicated(media):
    client, factory, worker, storage, app = media
    first = enqueue(client).json()["task"]
    second = enqueue(client).json()["task"]
    assert first["id"] == second["id"]
    with factory() as db:
        assert db.query(models_db.TutorialMediaTask).count() == 1


def test_media_boundary_mismatch_fails_before_publication(media, monkeypatch):
    from katrain.web.tutorials import media_tasks

    client, factory, worker, storage, app = media

    async def mismatch(text, voice, path):
        path.write_bytes(b"audio")
        return [{"text": "different text", "start_ms": 0, "duration_ms": 100}]

    monkeypatch.setattr(media_tasks, "synthesize_audio", mismatch)
    task = enqueue(client).json()["task"]
    worker.run_next()
    result = client.get(f"/api/admin/tutorials/media-tasks/{task['id']}").json()["task"]
    assert result["status"] == "failed"
    assert result["stage"] == "generating_audio"
    assert "boundary" in result["error"].lower()
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).audio_asset is None


def test_original_1030_source_white_first_seven_steps():
    from katrain.web.tutorials.replay import replay_frames

    initial = [[14, 2], [16, 3], [15, 16]]
    points = [[15, 14], [16, 14], [16, 13], [16, 15], [15, 12], [13, 16], [16, 8]]
    moves = [
        {"kind": "move", "color": "W" if i % 2 == 0 else "B", "point": point, "printed_number": str(i + 1)}
        for i, point in enumerate(points)
    ]
    value = {
        "schema_version": 2,
        "size": 19,
        "unknown_stones": [],
        "stones": {"B": initial + points[1::2], "W": points[::2]},
        "source_region": {"col": 7, "row": 0, "cols": 12, "rows": 19, "confirmed": True},
        "replay": {
            "status": "complete",
            "initial": {
                "stones": {"B": initial, "W": []},
                "unknown_stones": [],
                "known_region": {"col": 7, "row": 0, "cols": 12, "rows": 19},
                "to_play": "W",
            },
            "moves": moves,
            "evidence": {
                "kind": "source",
                "source_pointer": "/chapters/2/sections/0/pages/0/elements/3",
                "description": "Original p011-f01 and prose, white1 through white7",
            },
        },
    }
    frames = replay_frames(value)
    assert len(frames) == 8
    assert frames[0]["payload"]["stones"] == {"B": sorted(initial), "W": []}
    assert frames[1]["payload"]["stones"]["W"] == [[15, 14]]
    assert {tuple(p) for p in frames[-1]["payload"]["stones"]["B"]} == {tuple(p) for p in value["stones"]["B"]}
    assert len(frames[-1]["payload"]["stones"]["W"]) == 4


def test_speech_alignment_normalizes_punctuation_but_detects_changed_words():
    from katrain.web.tutorials.media_timing import align_boundaries

    boundaries = [{"text": "黑", "start_ms": 10, "duration_ms": 30}, {"text": "41", "start_ms": 40, "duration_ms": 20}]
    assert align_boundaries(" 黑 41。\n", boundaries) == [(1, 2, 10), (3, 5, 40)]
    with pytest.raises(ValueError, match="boundary"):
        align_boundaries("黑42", boundaries)


def test_draft_rejects_compound_or_orphan_numeric_labels_with_reasons(media):
    from katrain.web.tutorials.replay import replay_draft, replay_draft_warnings

    value = {
        "size": 9,
        "stones": {"B": [[1, 1], [3, 1]], "W": [[2, 1]]},
        "labels": {"1,1": "1/2", "2,1": "3", "3,1": "4"},
    }
    assert replay_draft(value)["replay"]["moves"] == []
    assert any("compound" in reason for reason in replay_draft_warnings(value))
    value["labels"] = {"0,0": "1", "2,1": "2", "3,1": "3"}
    assert replay_draft(value)["replay"]["moves"] == []
    assert any("occupied" in reason for reason in replay_draft_warnings(value))


def test_media_namespace_never_changes_recognition_uncertainty(media):
    from katrain.web.admin.routers.tutorial_workbench import _entry

    client, factory, worker, storage, app = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.recognition_debug = {
            "workbench_media": {"speech_timing": {"issues": ["old media issue"], "inference": True}}
        }
        entry = _entry(figure, [], [])
        assert entry["uncertainty"] is False and entry["inference"] is False
        assert entry["media"]["speech_timing"]["issues"] == ["old media issue"]


def test_2d_video_reuses_same_audio_and_keeps_historical_3d(media, monkeypatch):
    from katrain.web.tutorials import media_tasks

    client, factory, worker, storage, app = media
    narration = "黑41，白42，再看黑43。"
    with factory() as db:
        db.get(models_db.TutorialFigure, 1).narration = narration
        db.commit()
        db.execute(update(models_db.TutorialFigure).values(updated_at=None))
        db.commit()
    enqueue(client)
    worker.run_next()
    captured = []

    def render(**kwargs):
        captured.append(kwargs)
        kwargs["output_path"].write_bytes(b"video")

    monkeypatch.setattr(worker, "_render_video", render)

    async def forbidden(*args):
        raise AssertionError("valid saved audio must be reused")

    monkeypatch.setattr(media_tasks, "synthesize_audio", forbidden)

    def version():
        with factory() as db:
            return (
                db.get(models_db.TutorialFigure, 1)
                .updated_at.replace(tzinfo=__import__("datetime").timezone.utc)
                .isoformat()
            )

    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        debug = copy.deepcopy(figure.recognition_debug)
        debug["workbench_media"]["videos"] = {"3d": {"asset": "historical-3d.mp4", "audio_sha256": "historical"}}
        figure.recognition_debug = debug
        db.commit()
    first = enqueue(client, kind="video", version=version()).json()["task"]
    with factory() as db:
        assert db.get(models_db.TutorialMediaTask, first["id"]).snapshot["visual_seed"] == "1"
    worker.run_next()
    rejected = enqueue(client, kind="video", mode="3d", version=version())
    assert rejected.status_code == 422
    assert "2D" in rejected.json()["detail"]
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        metadata = figure.recognition_debug["workbench_media"]
        assert set(metadata["videos"]) == {"2d", "3d"}
        assert metadata["videos"]["3d"] == {"asset": "historical-3d.mp4", "audio_sha256": "historical"}
        assert figure.video_asset == metadata["videos"]["2d"]["profiles"][GALAXY]["asset"]
    assert len(captured) == 1
    assert captured[0]["visual_seed"] == "1"
    assert captured[0]["narration"] == narration


def test_explicit_media_migration_only_creates_media_table():
    from scripts.migrate_tutorial_media import migrate
    from sqlalchemy import inspect

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        migrate(connection)
        migrate(connection)
        assert inspect(connection).get_table_names() == ["tutorial_media_tasks"]
    engine.dispose()


def test_audio_immediately_publishes_authoritative_cues(media, monkeypatch):
    from katrain.web.tutorials import media_tasks

    client, factory, worker, storage, app = media

    async def speech(text, voice, path):
        path.write_bytes(b"audio")
        return [
            {"text": word, "start_ms": time, "duration_ms": 200}
            for word, time in [("黑41", 100), ("白42", 1000), ("再看黑43", 2000)]
        ]

    monkeypatch.setattr(media_tasks, "synthesize_audio", speech)
    enqueue(client)
    worker.run_next()
    with factory() as db:
        metadata = db.get(models_db.TutorialFigure, 1).recognition_debug["workbench_media"]
        assert metadata["step_cues"]["status"] == "complete"
        assert metadata["step_cues"]["audio_sha256"] == metadata["audio"]["sha256"]
        assert storage.exists(metadata["step_cues"]["asset"])


def test_board_edit_during_audio_prevents_publication(media, monkeypatch):
    from katrain.web.tutorials import media_tasks

    client, factory, worker, storage, app = media

    async def speech(text, voice, path):
        with factory() as db:
            figure = db.get(models_db.TutorialFigure, 1)
            value = copy.deepcopy(figure.board_payload)
            value["labels"]["1,1"] = "changed"
            figure.board_payload = value
            db.commit()
        path.write_bytes(b"audio")
        return [{"text": char, "start_ms": i * 100, "duration_ms": 80} for i, char in enumerate(text)]

    monkeypatch.setattr(media_tasks, "synthesize_audio", speech)
    task = enqueue(client).json()["task"]
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.audio_asset is None
        assert not (figure.recognition_debug or {}).get("workbench_media")
        assert db.get(models_db.TutorialMediaTask, task["id"]).status == "stale"


def test_publication_audit_failure_rolls_back_media_binding(media):
    from sqlalchemy import event

    client, factory, worker, storage, app = media
    task = enqueue(client).json()["task"]

    @event.listens_for(factory, "before_flush")
    def reject_publish(session, *_):
        if any(
            isinstance(row, models_db.AdminAuditLog) and row.action == "tutorial.media_task.publish"
            for row in session.new
        ):
            raise RuntimeError("audit unavailable")

    try:
        worker.run_next()
    finally:
        event.remove(factory, "before_flush", reject_publish)
    with factory() as db:
        assert db.get(models_db.TutorialFigure, 1).audio_asset is None
        assert db.get(models_db.TutorialMediaTask, task["id"]).status == "failed"
        assert db.query(models_db.AdminAuditLog).count() == 1


def test_unchanged_calibration_keeps_current_video_variant(media):
    client, factory, worker, storage, app = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.video_asset = "current.mp4"
        figure.video_duration_ms = 4000
        figure.video_size_bytes = 12
        figure.recognition_debug = {"workbench_media": {"videos": {"2d": {"asset": "current.mp4"}}}}
        db.commit()
        db.execute(update(models_db.TutorialFigure).values(updated_at=None))
        db.commit()
    response = client.put(
        "/api/admin/tutorials/figures/1/calibration", json={"board_payload": board(), "expected_updated_at": None}
    )
    assert response.status_code == 200
    assert response.json()["video_asset"] == "current.mp4"
    assert response.json()["recognition_debug"]["workbench_media"]["videos"]["2d"]["asset"] == "current.mp4"


def test_shutdown_terminates_owned_render_process_and_cleans_job_temp(media, tmp_path, monkeypatch):
    import json
    import sys
    import threading
    import time
    from katrain.web.tutorials import media_tasks

    client, factory, worker, storage, app = media
    enqueue(client)
    worker.run_next()
    with factory() as db:
        version = (
            db.get(models_db.TutorialFigure, 1)
            .updated_at.replace(tzinfo=__import__("datetime").timezone.utc)
            .isoformat()
        )
    task = enqueue(client, kind="video", version=version).json()["task"]
    marker = tmp_path / "render-started.json"
    real_popen = __import__("subprocess").Popen
    processes = []
    child = """import json, pathlib, sys, time, os
spec = json.loads(pathlib.Path(sys.argv[1]).read_text())
pathlib.Path(sys.argv[2]).write_text(json.dumps({'pid': os.getpid(), 'directory': str(pathlib.Path(spec['output_path']).parent)}))
time.sleep(60)
"""

    def launch(command, **kwargs):
        process = real_popen([sys.executable, "-c", child, command[-1], str(marker)], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(media_tasks.subprocess, "Popen", launch)
    worker._render_video = media_tasks.MediaWorker._render_video.__get__(worker)
    worker.thread = threading.Thread(target=worker.run_next)
    worker.thread.start()
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert marker.exists(), "owned render child did not start"
    details = json.loads(marker.read_text())
    worker.close()
    assert not worker.thread.is_alive()
    assert processes[0].poll() is not None
    assert not __import__("pathlib").Path(details["directory"]).exists()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.video_asset is None
        assert not figure.recognition_debug["workbench_media"].get("videos")
        result = db.get(models_db.TutorialMediaTask, task["id"])
        assert result.status == "failed" and result.stage == "rendering_video"


GALAXY = "galaxy-4k-v1"
KIOSK = "kiosk-7-v1"


def current_version(factory):
    from datetime import timezone

    with factory() as db:
        value = db.get(models_db.TutorialFigure, 1).updated_at
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def enqueue_profile(media, profile, *, kind="video", mode="2d"):
    client, factory, *_ = media
    body = {"kind": kind, "render_mode": mode, "expected_updated_at": current_version(factory)}
    if profile is not None:
        body["output_profile"] = profile
    return client.post("/api/admin/tutorials/figures/1/media-tasks", json=body)


def prepare_audio(media):
    response = enqueue_profile(media, None, kind="audio")
    assert response.status_code == 202, response.text
    media[2].run_next()


def test_profile_defaults_validation_and_independent_queue_identity(media):
    client, factory, worker, *_ = media
    audio = enqueue_profile(media, None, kind="audio").json()["task"]
    assert audio["output_profile"] is None
    with factory() as db:
        assert "output_profile" not in db.get(models_db.TutorialMediaTask, audio["id"]).snapshot
    worker.run_next()
    first = enqueue_profile(media, None).json()["task"]
    assert first["output_profile"] == GALAXY
    assert enqueue_profile(media, GALAXY).json()["task"]["id"] == first["id"]
    second = enqueue_profile(media, KIOSK).json()["task"]
    assert second["id"] != first["id"] and second["output_profile"] == KIOSK
    for profile, kind, mode in [("unknown", "video", "2d"), (KIOSK, "video", "3d"), (GALAXY, "audio", "2d")]:
        assert enqueue_profile(media, profile, kind=kind, mode=mode).status_code == 422
    with factory() as db:
        first_row = db.get(models_db.TutorialMediaTask, first["id"])
        second_row = db.get(models_db.TutorialMediaTask, second["id"])
        assert first_row.input_digest != second_row.input_digest
        assert first_row.snapshot["renderer_recipe"]


def test_both_profiles_publish_independently_and_preserve_legacy(media):
    from katrain.web.tutorials.manual_review import video_artifact

    client, factory, worker, *_ = media
    prepare_audio(media)
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        debug = copy.deepcopy(figure.recognition_debug)
        debug["workbench_media"]["videos"] = {"2d": {"asset": "legacy.mp4", "sha256": "old"}, "3d": {"asset": "3d.mp4"}}
        figure.recognition_debug = debug
        figure.video_asset = "legacy.mp4"
        figure.video_2d_review = {"reviewed_by": "legacy", "profiles": {KIOSK: {"asset": "old-kiosk"}}}
        db.commit()
    galaxy = enqueue_profile(media, GALAXY).json()["task"]
    kiosk = enqueue_profile(media, KIOSK).json()["task"]
    assert worker.run_next() and worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        videos = figure.recognition_debug["workbench_media"]["videos"]
        assert videos["2d"]["asset"] == "legacy.mp4" and videos["3d"] == {"asset": "3d.mp4"}
        assert video_artifact(figure, "2d") == {"asset": "legacy.mp4", "sha256": "old"}
        assert figure.video_2d_review["reviewed_by"] == "legacy"
        assert figure.video_2d_review["profiles"] == {GALAXY: None, KIOSK: None}
        assert figure.video_asset == videos["2d"]["profiles"][GALAXY]["asset"]
        for task_id, profile, dimensions in [(galaxy["id"], GALAXY, (3840, 2160)), (kiosk["id"], KIOSK, (1024, 600))]:
            task = db.get(models_db.TutorialMediaTask, task_id)
            artifact = video_artifact(figure, "2d", profile)
            assert task.status == "succeeded"
            assert artifact["output_profile"] == profile and profile in artifact["asset"]
            assert (artifact["width"], artifact["height"], artifact["fps"]) == (*dimensions, 30)
            assert task.result["video"] == artifact
            assert artifact["renderer_recipe"]
            assert artifact["presentation_objects"] == task.result["step_cues"]["objects"]
            assert artifact["presentation_events"] == task.result["step_cues"]["events"]
            assert artifact["presentation_asset"] == task.result["step_cues"]["asset"]


def test_old_snapshot_remains_legacy_and_renders_original_dimensions(media, monkeypatch):
    from katrain.web.tutorials.media_tasks import content_inputs
    from katrain.web.tutorials.media_timing import digest

    client, factory, worker, *_ = media
    captured = []

    def render(**kwargs):
        captured.append(kwargs)
        kwargs["output_path"].write_bytes(b"legacy video")

    monkeypatch.setattr(worker, "_render_video", render)
    prepare_audio(media)
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        inputs = content_inputs(figure, "video")
        task = models_db.TutorialMediaTask(
            figure_id=1,
            kind="video",
            render_mode="2d",
            input_digest=digest(inputs),
            snapshot={**inputs, "book_slug": "test"},
            requested_by="old",
            status="queued",
            stage="queued",
        )
        db.add(task)
        db.commit()
        task_id = task.id
    assert worker.run_next()
    with factory() as db:
        task = db.get(models_db.TutorialMediaTask, task_id)
        assert task.status == "succeeded"
        artifact = task.result["video"]
        assert artifact["output_profile"] is None
        assert (artifact["width"], artifact["height"], artifact["fps"]) == (1280, 800, 15)
    assert captured[0].get("output_profile") is None


@pytest.mark.parametrize("profile", [GALAXY, KIOSK])
def test_public_and_admin_figures_expose_only_exact_profile_summaries(media, profile):
    from katrain.web.api.v1.endpoints import tutorials as public
    from katrain.web.core.db import get_db

    client, factory, worker, storage, app = media
    app.include_router(public.router, prefix="/api/v1/tutorials")

    def isolated_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    prepare_audio(media)
    task = enqueue_profile(media, profile).json()["task"]
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        before = copy.deepcopy(figure.recognition_debug)
        updated = figure.updated_at
    figure = client.get("/api/v1/tutorials/figures/1").json()
    section = client.get("/api/v1/tutorials/sections/1").json()["figures"][0]
    admin = client.get("/api/admin/tutorials/figures/1").json()
    for result in [figure, section, admin]:
        assert set(result["video_profiles"]) == {GALAXY, KIOSK}
        summary = result["video_profiles"][profile]
        assert summary["output_profile"] == profile
        assert result["video_profiles"][KIOSK if profile == GALAXY else GALAXY] is None
        assert "reviewed_by" not in summary and "profiles" not in summary
        assert result["video_output_profile"] == (GALAXY if profile == GALAXY else None)
    assert "board_review" not in figure and "video_2d_review" not in section
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.recognition_debug == before and figure.updated_at == updated


def test_public_legacy_video_does_not_fill_missing_profile(media):
    from katrain.web.tutorials.models import TutorialFigureOut

    with media[1]() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.video_asset = "old-low-resolution.mp4"
        figure.recognition_debug = {"workbench_media": {"videos": {"2d": {"asset": figure.video_asset}}}}
        output = TutorialFigureOut.model_validate(figure)
        assert output.video_profiles == {GALAXY: None, KIOSK: None}
        assert output.video_output_profile == "legacy"


def test_publish_merges_sibling_change_made_during_render(media, monkeypatch):
    from katrain.web.tutorials.media_profiles import with_profile

    client, factory, worker, *_ = media
    prepare_audio(media)
    sibling = {"asset": "new-kiosk.mp4", "output_profile": KIOSK}
    review = {"asset": "new-kiosk.mp4", "reviewed_by": "concurrent reviewer"}

    def render(**kwargs):
        with factory() as db:
            figure = db.get(models_db.TutorialFigure, 1)
            debug = copy.deepcopy(figure.recognition_debug)
            debug["workbench_media"]["videos"] = {"2d": with_profile(None, KIOSK, sibling)}
            figure.recognition_debug = debug
            figure.video_2d_review = with_profile(None, KIOSK, review)
            db.commit()
        kwargs["output_path"].write_bytes(b"video")

    monkeypatch.setattr(worker, "_render_video", render)
    task = enqueue_profile(media, GALAXY).json()["task"]
    worker.run_next()
    with factory() as db:
        assert db.get(models_db.TutorialMediaTask, task["id"]).status == "succeeded"
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.recognition_debug["workbench_media"]["videos"]["2d"]["profiles"][KIOSK] == sibling
        assert figure.video_2d_review["profiles"] == {KIOSK: review, GALAXY: None}


def test_presentation_plan_is_typed_snapshotted_and_video_proof_is_profile_local(media):
    from katrain.web.tutorials.manual_review import video_problem, video_artifact

    client, factory, worker, *_ = media
    prepare_audio(media)
    plan = {
        "schema_version": 1,
        "bindings": [
            {"span": [0, 3], "object_ids": ["labels:1,2"]},
            {"span": [4, 7], "object_ids": ["replay:2"]},
            {"span": [10, 13], "object_ids": ["labels:1,1"]},
        ],
    }
    response = client.post(
        "/api/admin/tutorials/figures/1/media-tasks",
        json={
            "kind": "video",
            "output_profile": GALAXY,
            "expected_updated_at": current_version(factory),
            "presentation_plan": plan,
        },
    )
    assert response.status_code == 202, response.text
    task_id = response.json()["task"]["id"]
    with factory() as db:
        task = db.get(models_db.TutorialMediaTask, task_id)
        assert task.snapshot["presentation"]["presentation_plan"]["bindings"] == plan["bindings"]
    worker.run_next()
    assert enqueue_profile(media, KIOSK).status_code == 202
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert video_problem(figure, "2d", GALAXY) is None
        assert video_problem(figure, "2d", KIOSK) is None
        debug = copy.deepcopy(figure.recognition_debug)
        debug["workbench_media"]["videos"]["2d"]["profiles"][GALAXY]["presentation_sha256"] = "0" * 64
        figure.recognition_debug = debug
        db.commit()
        assert "presentation" in video_problem(figure, "2d", GALAXY)
        assert video_problem(figure, "2d", KIOSK) is None
    bad = {**plan, "bindings": [{"span": [0, 3], "object_ids": ["labels:1,2"], "at_ms": 20}]}
    response = client.post(
        "/api/admin/tutorials/figures/1/media-tasks",
        json={
            "kind": "audio",
            "expected_updated_at": current_version(factory),
            "presentation_plan": bad,
        },
    )
    assert response.status_code == 422


def test_source_arrows_require_registered_current_figure_identity(media):
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage

    client, factory, worker, *_ = media
    source = {"source_pointer": "/chapters/0/figures/0", "image_sha256": "a" * 64}
    plan = {
        "schema_version": 1,
        "arrows": [{"id": "arrow:direction", "from": [0, 0], "to": [2, 2], **source}],
        "bindings": [],
    }
    body = {"kind": "audio", "expected_updated_at": current_version(factory), "presentation_plan": plan}
    assert client.post("/api/admin/tutorials/figures/1/media-tasks", json=body).status_code == 422
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.page_image_path = "tutorial_assets/test/page1.png"
        from katrain.web.tutorials.manual_review import make_review, board_content_sha256

        figure.board_review = make_review({"username": "reviewer"}, board_content_sha256(figure))
        db.add(
            TutorialSourceBook(
                id=1,
                source_namespace="test",
                catalog_id="test",
                book_id=1,
                source_json_sha256="b" * 64,
                assets_manifest_sha256="c" * 64,
                source_metadata={},
                matching_evidence={},
            )
        )
        db.flush()
        db.add(
            TutorialSourceFigure(
                source_book_id=1,
                source_figure_id="test-1",
                source_pointer=source["source_pointer"],
                page=1,
                figure_id=1,
                source_metadata={},
            )
        )
        db.add(
            TutorialSourcePage(
                source_book_id=1,
                page=1,
                page_image_path=figure.page_image_path,
                image_sha256=source["image_sha256"],
                text_fragments=[],
                page_context_text="",
            )
        )
        db.commit()
    body["expected_updated_at"] = current_version(factory)
    accepted = client.post("/api/admin/tutorials/figures/1/media-tasks", json=body)
    assert accepted.status_code == 202, accepted.text
    task_id = accepted.json()["task"]["id"]
    with factory() as db:
        assert db.get(models_db.TutorialMediaTask, task_id).snapshot["source_identity"] == source
        page = db.query(TutorialSourcePage).one()
        page.image_sha256 = "d" * 64
        db.commit()
    worker.run_next()
    with factory() as db:
        assert db.get(models_db.TutorialMediaTask, task_id).status == "stale"
    plan["arrows"][0]["image_sha256"] = "e" * 64
    body["expected_updated_at"] = current_version(factory)
    assert client.post("/api/admin/tutorials/figures/1/media-tasks", json=body).status_code == 422


def test_changing_presentation_plan_invalidates_sibling_and_same_plan_preserves_it(media):
    from katrain.web.tutorials.manual_review import video_problem, video_artifact

    client, factory, worker, storage, *_ = media
    prepare_audio(media)
    assert enqueue_profile(media, GALAXY).status_code == 202
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        original = copy.deepcopy(video_artifact(figure, "2d", GALAXY))
        assert video_problem(figure, "2d", GALAXY) is None
    # Same narration/audio/order but explicit color spans include the following punctuation.
    plan = {
        "schema_version": 1,
        "bindings": [
            {"span": [0, 4], "object_ids": ["labels:1,2"]},
            {"span": [4, 8], "object_ids": ["replay:2"]},
            {"span": [10, 14], "object_ids": ["labels:1,1"]},
        ],
    }
    response = client.post(
        "/api/admin/tutorials/figures/1/media-tasks",
        json={
            "kind": "video",
            "output_profile": KIOSK,
            "expected_updated_at": current_version(factory),
            "presentation_plan": plan,
        },
    )
    assert response.status_code == 202, response.text
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert video_problem(figure, "2d", GALAXY) is not None
        assert video_problem(figure, "2d", KIOSK) is None
        assert video_artifact(figure, "2d", GALAXY) == original
        assert storage.exists(original["asset"])
    assert enqueue_profile(media, GALAXY).status_code == 202
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert video_problem(figure, "2d", GALAXY) is None
        assert video_problem(figure, "2d", KIOSK) is None


def test_approval_revalidates_registered_source_after_video_publication(media):
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage
    from katrain.web.tutorials.manual_review import make_review, board_content_sha256, video_problem, video_artifact

    client, factory, worker, *_ = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.page_image_path = "tutorial_assets/test/page1.png"
        figure.narration += "箭头。"
        figure.board_review = make_review({"username": "reviewer"}, board_content_sha256(figure))
        db.add(
            TutorialSourceBook(
                id=1,
                source_namespace="test",
                catalog_id="test",
                book_id=1,
                source_json_sha256="b" * 64,
                assets_manifest_sha256="c" * 64,
                source_metadata={},
                matching_evidence={},
            )
        )
        db.flush()
        db.add(
            TutorialSourceFigure(
                source_book_id=1, source_figure_id="one", source_pointer="/one", page=1, figure_id=1, source_metadata={}
            )
        )
        db.add(
            TutorialSourcePage(
                source_book_id=1,
                page=1,
                page_image_path=figure.page_image_path,
                image_sha256="a" * 64,
                text_fragments=[],
                page_context_text="",
            )
        )
        db.commit()
    prepare_audio(media)
    plan = {
        "schema_version": 1,
        "arrows": [
            {"id": "arrow:one", "from": [3, 3], "to": [4, 4], "source_pointer": "/one", "image_sha256": "a" * 64}
        ],
        "bindings": [
            {"span": [0, 3], "object_ids": ["labels:1,2"]},
            {"span": [4, 7], "object_ids": ["replay:2"]},
            {"span": [10, 13], "object_ids": ["labels:1,1"]},
            {"span": [14, 16], "object_ids": ["arrow:one"]},
        ],
    }
    response = client.post(
        "/api/admin/tutorials/figures/1/media-tasks",
        json={
            "kind": "video",
            "output_profile": GALAXY,
            "expected_updated_at": current_version(factory),
            "presentation_plan": plan,
        },
    )
    assert response.status_code == 202, response.text
    worker.run_next()
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert video_problem(figure, "2d", GALAXY) is None
        asset = video_artifact(figure, "2d", GALAXY)["asset"]
        db.query(TutorialSourcePage).one().image_sha256 = "d" * 64
        db.query(TutorialSourceFigure).one().source_pointer = "/new-source"
        db.commit()
        assert video_problem(figure, "2d", GALAXY) is not None
    response = client.put(
        "/api/admin/tutorials/figures/1/approve-video",
        json={
            "render_mode": "2d",
            "output_profile": GALAXY,
            "expected_asset": asset,
            "expected_updated_at": current_version(factory),
        },
    )
    assert response.status_code == 422, response.text
    assert "source" in response.json()["detail"].lower()


def test_source_recording_api_reuses_audio_and_publishes_distinct_rule_mode_with_saved_board_intact(media):
    from test_tutorial_media_presentation import historical_capture_source
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage
    from katrain.web.tutorials.manual_review import make_review, board_content_sha256, video_problem

    value, plan, source = historical_capture_source()
    client, factory, worker, *_ = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.board_payload = value
        figure.narration = "白1，黑2。"
        figure.page_image_path = "tutorial_assets/test/source.png"
        figure.board_review = make_review({"username": "reviewer"}, board_content_sha256(figure))
        approval = copy.deepcopy(figure.board_review)
        db.add(
            TutorialSourceBook(
                id=1,
                source_namespace="test",
                catalog_id="test",
                book_id=1,
                source_json_sha256="b" * 64,
                assets_manifest_sha256="c" * 64,
                source_metadata={},
                matching_evidence={},
            )
        )
        db.flush()
        db.add(
            TutorialSourceFigure(
                source_book_id=1,
                source_figure_id="one",
                source_pointer=source["source_pointer"],
                page=1,
                figure_id=1,
                source_metadata={},
            )
        )
        db.add(
            TutorialSourcePage(
                source_book_id=1,
                page=1,
                page_image_path=figure.page_image_path,
                image_sha256=source["image_sha256"],
                text_fragments=[],
                page_context_text="",
            )
        )
        db.commit()
    for kind in ("audio", "video"):
        response = client.post(
            "/api/admin/tutorials/figures/1/media-tasks",
            json={"kind": kind, "expected_updated_at": current_version(factory), "presentation_plan": plan},
        )
        assert response.status_code == 202, response.text
        task_id = response.json()["task"]["id"]
        worker.run_next()
        with factory() as db:
            task = db.get(models_db.TutorialMediaTask, task_id)
            assert task.status == "succeeded", task.error
            figure = db.get(models_db.TutorialFigure, 1)
            assert figure.board_payload == value and figure.board_review == approval
            assert task.result["step_cues"]["mode"] == "source_replay"
            if kind == "video":
                assert task.result["generated_audio"] is False
                assert task.result["video"]["playback_mode"] == "source_replay"
                assert task.result["step_cues"]["frames"][-1]["captured"] == [[0, 0]]
                assert video_problem(figure, "2d", GALAXY) is None


@pytest.mark.parametrize("invalid", [None, "no_applied", "pointer", "page", "foreign_book"])
def test_source_identity_accepts_only_current_applied_candidate_graph_for_extra_figures(media, invalid):
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage
    from katrain.web.tutorials.recognition_models import TutorialRecognitionCandidate
    from katrain.web.tutorials.manual_review import presentation_source_identity

    client, factory, *_ = media
    with factory() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.page_image_path = "tutorial_assets/test/source.png"
        if invalid == "foreign_book":
            db.add(
                models_db.TutorialBook(
                    id=2, category="布局", subcategory="test", title="foreign", slug="foreign", asset_dir="other"
                )
            )
            db.flush()
        db.add(
            TutorialSourceBook(
                id=1,
                source_namespace="test",
                catalog_id="test",
                book_id=2 if invalid == "foreign_book" else 1,
                source_json_sha256="b" * 64,
                assets_manifest_sha256="c" * 64,
                source_metadata={},
                matching_evidence={},
            )
        )
        db.flush()
        db.add(
            TutorialSourceFigure(
                id=1,
                source_book_id=1,
                source_figure_id="primary",
                source_pointer="/primary",
                page=1,
                figure_id=None,
                source_metadata={},
            )
        )
        db.add(
            TutorialSourcePage(
                source_book_id=1,
                page=1,
                page_image_path=figure.page_image_path,
                image_sha256="a" * 64,
                text_fragments=[],
                page_context_text="",
            )
        )
        db.flush()
        db.add(
            TutorialRecognitionCandidate(
                id=1,
                source_book_id=1,
                dataset="test",
                recognition_id="extra-1",
                figure_id=1,
                source_figure_id=1,
                source_pointer="/foreign" if invalid == "pointer" else "/primary",
                page=2 if invalid == "page" else 1,
                source_content_sha256="e" * 64,
                raw_result={},
                board_payload=figure.board_payload,
            )
        )
        if invalid != "no_applied":
            figure.recognition_debug = {**(figure.recognition_debug or {}), "applied_candidate_id": 1}
        db.commit()
        plan = {"source_replay": {"source_pointer": "/primary", "image_sha256": "a" * 64}}
        if invalid:
            with pytest.raises(ValueError):
                presentation_source_identity(figure, plan, db=db)
        else:
            assert presentation_source_identity(figure, plan, db=db) == {
                "source_pointer": "/primary",
                "image_sha256": "a" * 64,
            }
