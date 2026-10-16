"""Persistent single-worker media jobs with short atomic publication transactions."""

import asyncio
import copy
import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import time
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select, text, update

from katrain.web.core.models_db import TutorialFigure, TutorialMediaTask
from katrain.web.core.storage import get_storage_backend
from katrain.web.tutorials.media_timing import (
    VOICE,
    align_boundaries,
    build_step_cues,
    digest,
    narration_hash,
    probe_duration,
    synthesize_audio,
)
from katrain.web.tutorials.replay import replay_frames, validate_replay
from katrain.web.tutorials.services import _get_book_slug

logger = logging.getLogger(__name__)
_QUEUE_LOCK = threading.Lock()
_RUN_LOCK = threading.Lock()


def media_metadata(figure):
    return copy.deepcopy((figure.recognition_debug or {}).get("workbench_media") or {})


def invalidate_media(debug, *, narration=False):
    result = copy.deepcopy(debug or {})
    if "workbench_media" in result:
        if narration:
            result["workbench_media"] = {}
        else:
            result["workbench_media"].pop("videos", None)
            result["workbench_media"].pop("step_cues", None)
    return result


def content_inputs(figure, kind, voice=VOICE):
    result = {"narration": figure.narration, "voice": voice}
    if kind == "video":
        media = media_metadata(figure)
        result.update(
            board_payload=figure.board_payload,
            audio_asset=figure.audio_asset,
            audio=media.get("audio"),
            speech_timing=media.get("speech_timing"),
        )
    return result


def task_output(task):
    return {
        key: getattr(task, key)
        for key in (
            "id",
            "figure_id",
            "kind",
            "render_mode",
            "status",
            "stage",
            "error",
            "result",
            "created_at",
            "started_at",
            "finished_at",
        )
    }


class MediaWorker:
    def __init__(self, session_factory, *, storage=None, queue_limit=8):
        self.factory = session_factory
        self.storage = storage or get_storage_backend()
        self.queue_limit = queue_limit
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.thread = None
        self.active_loop = None
        self.active_tts = None
        self.active_render = None
        self.render_lock = threading.Lock()

    def enqueue(self, db, figure, body, admin):
        from katrain.web.admin.routers.tutorials import _audit, _commit, _version_filter

        with _QUEUE_LOCK:
            if not figure.narration or not figure.narration.strip():
                raise HTTPException(status_code=422, detail="Save narration before creating a media task")
            # Serialize admission across PostgreSQL admin processes; no lock survives this transaction.
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(1853101)"))
                db.refresh(figure, with_for_update=True)
            _version_filter(db, figure, body.expected_updated_at)
            inputs = content_inputs(figure, body.kind)
            input_digest = digest(inputs)
            existing = db.scalar(
                select(TutorialMediaTask)
                .where(
                    TutorialMediaTask.figure_id == figure.id,
                    TutorialMediaTask.kind == body.kind,
                    TutorialMediaTask.render_mode == body.render_mode,
                    TutorialMediaTask.input_digest == input_digest,
                    TutorialMediaTask.status.in_(["queued", "running"]),
                )
                .limit(1)
            )
            if existing is not None:
                return existing
            count = db.scalar(
                select(func.count())
                .select_from(TutorialMediaTask)
                .where(TutorialMediaTask.status.in_(["queued", "running"]))
            )
            if count >= self.queue_limit:
                raise HTTPException(status_code=429, detail="Media queue is full; retry after a task finishes")
            task = TutorialMediaTask(
                figure_id=figure.id,
                kind=body.kind,
                render_mode=body.render_mode,
                input_digest=input_digest,
                snapshot={
                    **copy.deepcopy(inputs),
                    "board_payload": copy.deepcopy(figure.board_payload),
                    "book_slug": _get_book_slug(db, figure),
                },
                requested_by=admin["username"],
                status="queued",
                stage="queued",
            )
            db.add(task)
            _audit(db, admin, "tutorial.media_task.enqueue", figure.id)
            _commit(db)
        self.wake.set()
        return task

    @contextmanager
    def _leadership(self):
        # Session advisory lock owns one active generator across admin processes.
        # It holds no row lock or open transaction while synthesis/render runs.
        with self.factory() as db:
            engine = db.get_bind()
        if engine.dialect.name != "postgresql":
            yield True
            return
        with engine.connect() as connection:
            owned = connection.execute(text("SELECT pg_try_advisory_lock(1853102)")).scalar_one()
            connection.commit()
            try:
                yield owned
            finally:
                if owned:
                    connection.execute(text("SELECT pg_advisory_unlock(1853102)"))
                    connection.commit()

    def _recover_db(self):
        with self.factory() as db:
            db.execute(
                update(TutorialMediaTask)
                .where(TutorialMediaTask.status == "running")
                .values(
                    status="failed",
                    error="Admin process restarted during media generation; retry explicitly",
                    finished_at=datetime.now(timezone.utc),
                )
            )
            db.commit()

    def recover(self):
        with _RUN_LOCK, self._leadership() as owned:
            if owned:
                self._recover_db()

    def start(self):
        self.recover()
        self.thread = threading.Thread(target=self._loop, name="tutorial-media", daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.stop_event.set()
        self.wake.set()
        active_loop, active_tts = self.active_loop, self.active_tts
        if active_loop and active_tts:
            try:
                active_loop.call_soon_threadsafe(active_tts.cancel)
            except RuntimeError:
                pass
        with self.render_lock:
            process = self.active_render
        if process is not None:
            self._terminate_render(process)
        if self.thread:
            self.thread.join(timeout=5)

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                worked = self.run_next()
            except Exception:
                logger.exception("Tutorial media worker failed")
                worked = False
            if not worked:
                self.wake.wait(2)
                self.wake.clear()

    def _stage(self, task_id, stage):
        with self.factory() as db:
            db.execute(update(TutorialMediaTask).where(TutorialMediaTask.id == task_id).values(stage=stage))
            db.commit()

    def run_next(self):
        if not _RUN_LOCK.acquire(blocking=False):
            return False
        try:
            with self._leadership() as owned:
                if not owned:
                    return False
                self._recover_db()
                return self._run_claimed()
        finally:
            _RUN_LOCK.release()

    def _run_claimed(self):
        with self.factory() as db:
            task = db.scalar(
                select(TutorialMediaTask)
                .where(TutorialMediaTask.status == "queued")
                .order_by(TutorialMediaTask.created_at, TutorialMediaTask.id)
                .limit(1)
            )
            if task is None:
                return False
            claimed = db.execute(
                update(TutorialMediaTask)
                .where(TutorialMediaTask.id == task.id, TutorialMediaTask.status == "queued")
                .values(status="running", stage="preparing", started_at=datetime.now(timezone.utc))
            )
            if claimed.rowcount != 1:
                db.rollback()
                return False
            db.commit()
            task_id, snapshot, kind, mode = task.id, copy.deepcopy(task.snapshot), task.kind, task.render_mode
        try:
            with tempfile.TemporaryDirectory(prefix="katrain-media-") as directory:
                result = self._generate(task_id, snapshot, kind, mode, Path(directory))
                if self.stop_event.is_set():
                    raise RuntimeError("Admin process is shutting down; retry explicitly")
                self._stage(task_id, "publishing")
                self._publish(task_id, result)
        except (Exception, asyncio.CancelledError) as exc:
            logger.warning("Tutorial media task %s failed: %s", task_id, exc)
            with self.factory() as db:
                db.execute(
                    update(TutorialMediaTask)
                    .where(TutorialMediaTask.id == task_id)
                    .values(
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}"[:2000],
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                db.commit()
        return True

    async def _speech(self, narration, voice, audio_path):
        self.active_loop = asyncio.get_running_loop()
        self.active_tts = asyncio.current_task()
        try:
            return await asyncio.wait_for(synthesize_audio(narration, voice, audio_path), timeout=180)
        finally:
            self.active_loop = None
            self.active_tts = None

    @staticmethod
    def _terminate_render(process):
        """Terminate the runner and all browser/ffmpeg descendants in its group."""
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)

    def _render_video(self, **spec):
        directory = spec["output_path"].parent
        spec_path = directory / "render-spec.json"
        spec_path.write_text(
            json.dumps(
                {key: str(value) if isinstance(value, Path) else value for key, value in spec.items()},
                ensure_ascii=False,
            )
        )
        # The renderer needs local binaries/fonts/Chromium only. Do not pass DB,
        # provider, storage, or admin credentials into this child environment.
        allowed = {
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "TMPDIR",
            "PLAYWRIGHT_BROWSERS_PATH",
            "TUTORIAL_MEDIA_CHROMIUM_EXECUTABLE",
        }
        environment = {key: value for key, value in os.environ.items() if key in allowed}
        with (directory / "render.log").open("w+b") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "katrain.web.tutorials.media_render_runner", str(spec_path)],
                cwd=Path(__file__).resolve().parents[3],
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            with self.render_lock:
                self.active_render = process
            deadline = time.monotonic() + 620
            try:
                while process.poll() is None:
                    if self.stop_event.wait(0.05):
                        raise RuntimeError("Admin process shut down during rendering; retry explicitly")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Tutorial render process exceeded 620 seconds")
                if self.stop_event.is_set():
                    raise RuntimeError("Admin process shut down during rendering; retry explicitly")
                if process.returncode:
                    log.seek(0, 2)
                    log.seek(max(0, log.tell() - 2000))
                    raise RuntimeError("Tutorial renderer failed: " + log.read().decode("utf-8", errors="replace"))
            finally:
                self._terminate_render(process)
                with self.render_lock:
                    if self.active_render is process:
                        self.active_render = None

    def _upload(self, key, path, content_type):
        with path.open("rb") as source:
            self.storage.put(key, source, content_type=content_type)

    def _generate(self, task_id, snapshot, kind, mode, directory):
        prefix = f"tutorial_assets/{snapshot['book_slug']}/media/{task_id}"
        audio_path = directory / "audio.mp3"
        timing, audio = snapshot.get("speech_timing"), snapshot.get("audio")
        narration = snapshot["narration"]
        valid_audio = (
            kind == "video"
            and audio
            and timing
            and snapshot.get("audio_asset") == audio.get("asset")
            and timing.get("narration_sha256") == narration_hash(narration)
            and timing.get("voice") == snapshot["voice"]
            and timing.get("audio_sha256") == audio.get("sha256")
        )
        generated_audio = not valid_audio
        if valid_audio:
            self._stage(task_id, "loading_audio")
            audio_path.write_bytes(self.storage.read(audio["asset"]))
            if hashlib.sha256(audio_path.read_bytes()).hexdigest() != audio["sha256"]:
                raise RuntimeError("Saved audio bytes do not match their immutable digest")
        else:
            self._stage(task_id, "generating_audio")
            boundaries = asyncio.run(self._speech(narration, snapshot["voice"], audio_path))
            align_boundaries(narration, boundaries)
            duration = probe_duration(audio_path)
            audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
            timing = {
                "schema_version": 1,
                "narration_sha256": narration_hash(narration),
                "voice": snapshot["voice"],
                "audio_sha256": audio_hash,
                "duration_ms": duration,
                "boundaries": boundaries,
                "asset": prefix + "/speech_timing.json",
            }
            audio = {
                "asset": prefix + "/audio.mp3",
                "sha256": audio_hash,
                "narration_sha256": timing["narration_sha256"],
                "voice": snapshot["voice"],
                "duration_ms": duration,
            }
        align_boundaries(narration, timing["boundaries"])
        payload = snapshot.get("board_payload") or {}
        cues = build_step_cues(payload, narration, timing)
        result = {
            "audio": audio,
            "speech_timing": timing,
            "generated_audio": generated_audio,
            "step_cues": {**cues, "asset": prefix + "/step_cues.json"},
        }
        if kind == "video":
            self._stage(task_id, "aligning_replay")
            frames = replay_frames(payload) if validate_replay(payload)["status"] == "complete" else []
            self._stage(task_id, "rendering_video")
            video_path = directory / "video.mp4"
            self._render_video(
                board_payload=payload,
                frames=frames,
                speech_timing=timing,
                step_cues=cues,
                audio_path=audio_path,
                output_path=video_path,
                render_mode=mode,
            )
            if not video_path.is_file() or not video_path.stat().st_size:
                raise RuntimeError("Renderer returned empty video")
            result.update(
                step_cues={**cues, "asset": prefix + "/step_cues.json"},
                video={
                    "asset": prefix + f"/video-{mode}.mp4",
                    "duration_ms": probe_duration(video_path),
                    "size_bytes": video_path.stat().st_size,
                    "audio_sha256": timing["audio_sha256"],
                    "replay_sha256": cues["replay_sha256"],
                    "playback_mode": "replay" if cues["status"] == "complete" else "static",
                    "timing_status": cues["status"],
                    "timing_reason": cues["reason"],
                },
            )
        self._stage(task_id, "uploading")
        if generated_audio:
            self._upload(audio["asset"], audio_path, "audio/mpeg")
            self.storage.put(
                timing["asset"], json.dumps(timing, ensure_ascii=False).encode(), content_type="application/json"
            )
        if kind == "video":
            self._upload(result["video"]["asset"], video_path, "video/mp4")
        self.storage.put(
            result["step_cues"]["asset"],
            json.dumps(result["step_cues"], ensure_ascii=False).encode(),
            content_type="application/json",
        )
        return result

    def _publish(self, task_id, result):
        from katrain.web.admin.routers.tutorials import _audit, _cas_update, _commit, _utc

        with self.factory() as db:
            task = db.get(TutorialMediaTask, task_id)
            if task is None or task.status != "running":
                return
            figure = db.get(TutorialFigure, task.figure_id, with_for_update=True)
            if figure is None or digest(content_inputs(figure, task.kind, task.snapshot["voice"])) != task.input_digest:
                task.status, task.stage, task.error = "stale", "stale", "Saved media inputs changed during generation"
                task.result = result
            else:
                debug = copy.deepcopy(figure.recognition_debug or {})
                media = media_metadata(figure)
                if result["generated_audio"]:
                    media.pop("videos", None)
                    media.pop("step_cues", None)
                media.update(audio=result["audio"], speech_timing=result["speech_timing"])
                values = {"audio_asset": result["audio"]["asset"]}
                if result["generated_audio"]:
                    values.update(video_asset=None, video_duration_ms=None, video_size_bytes=None)
                if digest(figure.board_payload) == digest(task.snapshot.get("board_payload")):
                    media["step_cues"] = result["step_cues"]
                if task.kind == "video":
                    media["step_cues"] = result["step_cues"]
                    media.setdefault("videos", {})[task.render_mode] = result["video"]
                    if task.render_mode == "2d":
                        values.update(
                            video_asset=result["video"]["asset"],
                            video_duration_ms=result["video"]["duration_ms"],
                            video_size_bytes=result["video"]["size_bytes"],
                        )
                debug["workbench_media"] = media
                values["recognition_debug"] = debug
                expected = _utc(figure.updated_at).isoformat() if figure.updated_at else None
                _cas_update(db, figure, expected, values)
                _audit(db, {"username": task.requested_by}, "tutorial.media_task.publish", figure.id)
                task = db.get(TutorialMediaTask, task_id)
                task.status, task.stage, task.result = "succeeded", "succeeded", result
            task.finished_at = datetime.now(timezone.utc)
            _commit(db)
