"""Pool checks use a private file DB so real concurrent sessions stay independent."""

import asyncio
import copy
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db as models
from katrain.web.core.storage.local import LocalStorageBackend
from katrain.web.tutorials import media_tasks
from katrain.web.tutorials.manual_review import board_content_sha256, make_review


def wait_for(predicate):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate(), "media pool did not reach the expected state"


@pytest.fixture
def pool(tmp_path, monkeypatch):
    pg_url = os.environ.get("TUTORIAL_MEDIA_TEST_PG_URL")
    schema = "media_pool_" + uuid.uuid4().hex
    admin_engine = create_engine(pg_url) if pg_url else None
    if admin_engine:
        with admin_engine.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(pg_url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'pool.sqlite'}", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(models.TutorialBook(id=1, category="布局", title="pool", slug="pool", asset_dir="x"))
        db.flush()
        db.add(models.TutorialChapter(id=1, book_id=1, chapter_number="1", title="c", order=1))
        db.flush()
        db.add(models.TutorialSection(id=1, chapter_id=1, section_number="1", title="s", order=1))
        db.flush()
        for ident in range(1, 4):
            figure = models.TutorialFigure(
                id=ident,
                section_id=1,
                page=ident,
                figure_label=f"图{ident}",
                order=ident,
                narration="观察棋盘。",
                board_payload={"size": 9, "stones": {"B": [], "W": []}},
            )
            db.add(figure)
            db.flush()
            figure.board_review = make_review({"username": "fixture"}, board_content_sha256(figure))
        db.commit()
    worker = media_tasks.MediaWorker(factory, storage=LocalStorageBackend(tmp_path / "assets"), workers=2)

    async def speech(narration, voice, path):
        path.write_bytes(b"immutable audio")
        return [{"text": narration, "start_ms": 0, "duration_ms": 500}]

    monkeypatch.setattr(media_tasks, "synthesize_audio", speech)
    monkeypatch.setattr(media_tasks, "probe_duration", lambda path: 1000)
    monkeypatch.setattr(worker, "_render_video", lambda **spec: spec["output_path"].write_bytes(b"video"))
    yield worker, factory
    worker.close()
    engine.dispose()
    if admin_engine:
        with admin_engine.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def enqueue(worker, factory, figure_id, *, kind="audio", profile=None):
    from katrain.web.admin.routers.tutorial_media import MediaTaskWrite

    with factory() as db:
        figure = db.get(models.TutorialFigure, figure_id)
        version = figure.updated_at.replace(tzinfo=timezone.utc).isoformat() if figure.updated_at else None
        task = worker.enqueue(
            db,
            figure,
            MediaTaskWrite(kind=kind, output_profile=profile, expected_updated_at=version),
            {"username": "fixture"},
        )
        return task.id


def statuses(factory):
    with factory() as db:
        return {task.id: task.status for task in db.scalars(select(models.TutorialMediaTask))}


def test_pool_bounds_parallel_claims_and_recovery_never_fails_live_tasks(pool, monkeypatch):
    worker, factory = pool
    ids = [enqueue(worker, factory, figure) for figure in (1, 2, 3)]
    release = threading.Event()
    original = worker._generate
    recoveries = []
    recover = worker._recover_db
    monkeypatch.setattr(worker, "_recover_db", lambda: (recoveries.append(1), recover())[1])

    def generate(*args):
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(worker, "_generate", generate)
    try:
        worker.start()
        wait_for(lambda: list(statuses(factory).values()).count("running") == 2)
        assert list(statuses(factory).values()).count("queued") == 1
        contender = media_tasks.MediaWorker(factory, storage=worker.storage)
        assert contender.recover() is False
        assert contender.run_next() is False
        assert worker.recover() is False
        assert list(statuses(factory).values()).count("running") == 2
    finally:
        release.set()
    wait_for(lambda: all(statuses(factory)[ident] == "succeeded" for ident in ids))
    assert recoveries == [1]


def test_same_figure_profiles_run_in_order_without_blocking_other_figures(pool, monkeypatch):
    worker, factory = pool
    for figure in (1, 2):
        enqueue(worker, factory, figure)
        assert worker.run_next()
    ids = [
        enqueue(worker, factory, 1, kind="video", profile="galaxy-4k-v1"),
        enqueue(worker, factory, 1, kind="video", profile="kiosk-7-v1"),
        enqueue(worker, factory, 2, kind="video", profile="galaxy-4k-v1"),
    ]
    release, started, lock = threading.Event(), [], threading.Lock()

    def render(**spec):
        with lock:
            started.append((spec["visual_seed"], spec["output_profile"]))
        assert release.wait(5)
        spec["output_path"].write_bytes(b"video")

    monkeypatch.setattr(worker, "_render_video", render)
    try:
        worker.start()
        wait_for(lambda: len(started) == 2)
        assert sorted(started) == [("1", "galaxy-4k-v1"), ("2", "galaxy-4k-v1")]
        assert statuses(factory)[ids[1]] == "queued"
    finally:
        release.set()
    wait_for(lambda: all(statuses(factory)[ident] == "succeeded" for ident in ids))
    assert len(started) == 3
    with factory() as db:
        media = copy.deepcopy(db.get(models.TutorialFigure, 1).recognition_debug["workbench_media"])
    assert set(media["videos"]["2d"]["profiles"]) == {"galaxy-4k-v1", "kiosk-7-v1"}
    assert {item["audio_sha256"] for item in media["videos"]["2d"]["profiles"].values()} == {media["audio"]["sha256"]}


def test_close_cancels_every_active_tts_and_leaves_queued_tasks_unclaimed(pool, monkeypatch):
    worker, factory = pool
    ids = [enqueue(worker, factory, figure) for figure in (1, 2, 3)]
    started, cancelled = [], []

    async def speech(narration, voice, path):
        started.append(str(path))
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(str(path))

    monkeypatch.setattr(media_tasks, "synthesize_audio", speech)
    worker.start()
    wait_for(lambda: len(started) == 2)
    worker.close()
    assert not worker.thread.is_alive()
    assert len(cancelled) == 2
    assert sorted(statuses(factory).values()) == ["failed", "failed", "queued"]
    # A successor recovers old interrupted rows once, then can claim the remaining job.
    assert statuses(factory)[ids[-1]] == "queued"


def test_config_defaults_and_bounded_queue_scale_only_when_configured(tmp_path, monkeypatch):
    for key in ("TUTORIAL_MEDIA_WORKERS", "TUTORIAL_MEDIA_QUEUE_LIMIT", "TUTORIAL_MEDIA_ENCODER_THREADS"):
        monkeypatch.delenv(key, raising=False)
    kwargs = {"storage": LocalStorageBackend(tmp_path)}
    worker = media_tasks.MediaWorker(None, **kwargs)
    assert (worker.workers, worker.queue_limit, worker.encoder_threads) == (1, 8, 4)
    monkeypatch.setenv("TUTORIAL_MEDIA_WORKERS", "10")
    worker = media_tasks.MediaWorker(None, **kwargs)
    assert (worker.workers, worker.queue_limit) == (10, 40)
    monkeypatch.setenv("TUTORIAL_MEDIA_QUEUE_LIMIT", "60")
    monkeypatch.setenv("TUTORIAL_MEDIA_ENCODER_THREADS", "3")
    worker = media_tasks.MediaWorker(None, **kwargs)
    assert (worker.workers, worker.queue_limit, worker.encoder_threads) == (10, 60, 3)
    monkeypatch.setenv("TUTORIAL_MEDIA_WORKERS", "0")
    with pytest.raises(ValueError, match="TUTORIAL_MEDIA_WORKERS"):
        media_tasks.MediaWorker(None, **kwargs)


@pytest.mark.skipif(not os.environ.get("TUTORIAL_MEDIA_TEST_PG_URL"), reason="requires isolated temporary PostgreSQL")
def test_pg_lost_leader_cannot_write_or_claim_after_cross_process_takeover(pool, monkeypatch, tmp_path):
    worker, factory = pool
    ids = [enqueue(worker, factory, figure) for figure in (1, 2, 3)]
    original, release = worker._generate, threading.Event()

    def generate(*args):
        assert release.wait(8)
        return original(*args)

    monkeypatch.setattr(worker, "_generate", generate)
    worker.start()
    try:
        wait_for(lambda: list(statuses(factory).values()).count("running") == 2)
        with factory() as db:
            schema = db.scalar(text("SELECT current_schema()"))
        environment = dict(os.environ, MEDIA_TEST_SCHEMA=schema, MEDIA_TEST_ASSETS=str(tmp_path / "follower"))
        contender = """
import json, os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from katrain.web.tutorials.media_tasks import MediaWorker
from katrain.web.core.storage.local import LocalStorageBackend
engine=create_engine(os.environ["TUTORIAL_MEDIA_TEST_PG_URL"],connect_args={"options":"-csearch_path="+os.environ["MEDIA_TEST_SCHEMA"]})
worker=MediaWorker(sessionmaker(bind=engine),storage=LocalStorageBackend(os.environ["MEDIA_TEST_ASSETS"]))
print(json.dumps({"recovered":worker.recover()}))
engine.dispose()
"""

        def recover_in_other_process():
            result = subprocess.run(
                [sys.executable, "-c", contender], env=environment, capture_output=True, text=True, timeout=10
            )
            assert result.returncode == 0, "isolated PostgreSQL contender failed"
            return json.loads(result.stdout.splitlines()[-1])["recovered"]

        assert recover_in_other_process() is False
        assert list(statuses(factory).values()).count("running") == 2
        with factory() as db:
            assert db.scalar(text("SELECT pg_terminate_backend(:pid)"), {"pid": worker.leader_identity[0]})
            db.commit()
        # A new PROCESS can acquire the released session lock even though the
        # old process is still blocked in generation and holds its local mutex.
        assert recover_in_other_process() is True
        wait_for(worker.stop_event.is_set)
        assert sorted(statuses(factory).values()) == ["failed", "failed", "queued"]
        with pytest.raises(media_tasks._LeadershipLost):
            worker._stage(ids[-1], "preparing")
        with pytest.raises(media_tasks._LeadershipLost):
            worker._claim_next()
        with pytest.raises(media_tasks._LeadershipLost):
            worker._publish(ids[0], {})
    finally:
        release.set()
        worker.close()
    assert not worker.thread.is_alive()
    with factory() as db:
        assert all(figure.audio_asset is None for figure in db.scalars(select(models.TutorialFigure)))
    assert sorted(statuses(factory).values()) == ["failed", "failed", "queued"]
