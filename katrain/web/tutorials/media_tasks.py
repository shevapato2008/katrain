"""Persistent bounded media pool with short atomic publication transactions."""

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
from katrain.web.tutorials.media_profiles import GALAXY, render_profile, with_profile
from katrain.web.tutorials.media_pronunciation import prepare_speech, pronunciation_is_current
from katrain.web.tutorials.media_timing import (
    VOICE,
    align_boundaries,
    build_step_cues,
    digest,
    narration_hash,
    probe_duration,
    synthesize_audio,
)
from katrain.web.tutorials.manual_review import board_authority, media_dependencies
from katrain.web.tutorials.generation_authorization import generation_eligibility
from katrain.web.tutorials.services import _get_book_slug

logger = logging.getLogger(__name__)
_QUEUE_LOCK = threading.Lock()
_RUN_LOCK = threading.Lock()


class _LeadershipLost(RuntimeError):
    pass


def _positive_setting(name, value, default, maximum):
    value = os.environ.get(name, str(default)) if value is None else value
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer between 1 and {maximum}") from None
    if not 1 <= parsed <= maximum:
        raise ValueError(f"{name} must be an integer between 1 and {maximum}")
    return parsed


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


def _source_identity(db, figure, plan):
    from katrain.web.tutorials.manual_review import presentation_source_identity

    return presentation_source_identity(figure, plan, db=db, for_generation=True)


def content_inputs(
    figure,
    kind,
    voice=VOICE,
    output_profile=None,
    *,
    presentation_plan=None,
    source_identity=None,
    generation_authorization=None,
):
    _, pronunciation = prepare_speech(figure.narration or "", voice)
    pronunciation_input = {"pronunciation_sha256": pronunciation} if pronunciation else {}
    if kind == "video":
        inputs = media_dependencies(figure, voice=voice)
        if generation_authorization is not None:
            inputs["generation_authorization_sha256"] = digest(generation_authorization)
        inputs.update(pronunciation_input)
        proof = build_step_cues(
            figure.board_payload or {},
            figure.narration,
            inputs.get("speech_timing") or {},
            presentation_plan=presentation_plan,
            source_identity=source_identity,
        )
        inputs["presentation"] = {
            key: proof[key] for key in ("presentation_plan", "source_identity", "presentation_sha256")
        }
        if output_profile is not None:
            inputs.update(output_profile=output_profile, renderer_recipe=render_profile(output_profile).renderer_recipe)
        return inputs
    inputs = {"narration": figure.narration, "voice": voice, **board_authority(figure), **pronunciation_input}
    if generation_authorization is not None:
        inputs["generation_authorization_sha256"] = digest(generation_authorization)
    if presentation_plan is not None:
        inputs["presentation_plan"] = presentation_plan
        inputs["source_identity"] = source_identity
    return inputs


def _snapshot_plan(snapshot):
    return (snapshot.get("presentation") or snapshot).get("presentation_plan")


def _current_inputs(db, figure, task):
    plan = _snapshot_plan(task.snapshot)
    try:
        source = _source_identity(db, figure, plan)
    except ValueError:
        return {"stale_presentation_source": True}
    return content_inputs(
        figure,
        task.kind,
        task.snapshot["voice"],
        task.snapshot.get("output_profile"),
        presentation_plan=plan,
        source_identity=source,
        generation_authorization=generation_eligibility(figure, db=db)["record"],
    )


def task_output(task):
    return {
        "output_profile": (task.snapshot or {}).get("output_profile") if task.kind == "video" else None,
        **{
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
        },
    }


class MediaWorker:
    def __init__(self, session_factory, *, storage=None, queue_limit=None, workers=None, encoder_threads=None):
        self.factory = session_factory
        self.storage = storage or get_storage_backend()
        self.workers = _positive_setting("TUTORIAL_MEDIA_WORKERS", workers, 1, 32)
        self.queue_limit = _positive_setting("TUTORIAL_MEDIA_QUEUE_LIMIT", queue_limit, max(8, self.workers * 4), 1024)
        self.encoder_threads = _positive_setting("TUTORIAL_MEDIA_ENCODER_THREADS", encoder_threads, 4, 32)
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.thread = None
        self.lanes = []
        self.claim_lock = threading.Lock()
        self.activity_lock = threading.Lock()
        self.activities = {}
        self.leader_identity = None
        self.leadership_lost = False

    def enqueue(self, db, figure, body, admin):
        from katrain.web.admin.routers.tutorials import _audit, _commit, _version_filter

        if body.kind == "video" and body.render_mode != "2d":
            raise HTTPException(
                status_code=422, detail="New tutorial videos support 2D only; historical 3D media remains readable"
            )
        output_profile = (body.output_profile or GALAXY) if body.kind == "video" else None
        with _QUEUE_LOCK:
            if not figure.narration or not figure.narration.strip():
                raise HTTPException(status_code=422, detail="Save narration before creating a media task")
            # Serialize admission across PostgreSQL admin processes; no lock survives this transaction.
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(1853101)"))
                db.refresh(figure, with_for_update=True)
            _version_filter(db, figure, body.expected_updated_at)
            eligibility = generation_eligibility(figure, db=db)
            if not eligibility["authorized"]:
                raise HTTPException(status_code=422, detail=eligibility["reason"])
            plan = body.presentation_plan.model_dump(by_alias=True) if body.presentation_plan is not None else None
            if plan is None and body.kind == "video":
                plan = (media_metadata(figure).get("step_cues") or {}).get("presentation_plan")
            try:
                source = _source_identity(db, figure, plan)
                from katrain.web.tutorials.media_presentation import discover_objects

                discover_objects(figure.board_payload or {}, plan, source)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            inputs = content_inputs(
                figure,
                body.kind,
                output_profile=output_profile,
                presentation_plan=plan,
                source_identity=source,
                generation_authorization=eligibility["record"],
            )
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
                    "visual_seed": str(figure.id),
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
        # One leader owns the entire pool across admin processes. Keep this
        # connection until every lane exits, including cancellation/publication.
        # It holds no row lock or open transaction while synthesis/render runs.
        with self.factory() as db:
            engine = db.get_bind()
        if engine.dialect.name != "postgresql":
            yield True
            return
        with engine.connect() as connection:
            owned = connection.execute(text("SELECT pg_try_advisory_lock(1853102)")).scalar_one()
            if owned:
                identity = connection.execute(
                    text("SELECT pid, backend_start FROM pg_stat_activity WHERE pid = pg_backend_pid()")
                ).one()
                self.leader_identity = (identity.pid, identity.backend_start)
                self.leadership_lost = False
            connection.commit()
            try:
                yield owned
            finally:
                if owned:
                    try:
                        if not self.leadership_lost:
                            connection.execute(text("SELECT pg_advisory_unlock(1853102)"))
                            connection.commit()
                    finally:
                        self.leader_identity = None

    def _fence(self, db):
        if db.get_bind().dialect.name != "postgresql":
            return
        # Admission, recovery and all worker writes share this short transaction
        # lock. A successor cannot recover between an old owner's valid fence
        # and its commit. The original backend identity must still own the pool
        # lock; a new connection must never transparently inherit ownership.
        db.execute(text("SELECT pg_advisory_xact_lock(1853101)"))
        identity = self.leader_identity
        alive = identity is not None and db.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE l.locktype = 'advisory' AND l.classid = 0 AND l.objid = 1853102 "
                "AND l.objsubid = 1 AND l.granted AND l.mode = 'ExclusiveLock' "
                "AND a.pid = :pid AND a.backend_start = :started)"
            ),
            {"pid": identity[0], "started": identity[1]},
        )
        if not alive:
            self.leadership_lost = True
            self.stop_event.set()
            self.wake.set()
            self._cancel_active()
            raise _LeadershipLost("Media pool lost its original PostgreSQL leadership session")

    def _recover_db(self):
        # Only the newly acquired leader can recover its predecessor's rows.
        # Never run this between claims: other lanes are still generating.
        with self.factory() as db:
            self._fence(db)
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
        if not _RUN_LOCK.acquire(blocking=False):
            return False
        try:
            with self._leadership() as owned:
                if owned:
                    self._recover_db()
                return bool(owned)
        finally:
            _RUN_LOCK.release()

    def start(self):
        if self.thread is not None or self.stop_event.is_set():
            raise RuntimeError("Media pool has already been started or closed")
        self.thread = threading.Thread(target=self._loop, name="tutorial-media", daemon=True)
        self.thread.start()
        return self

    def _cancel_active(self):
        with self.activity_lock:
            active = list(self.activities.values())
        for activity in active:
            active_loop, active_tts = activity.get("loop"), activity.get("tts")
            if not active_loop or not active_tts:
                continue
            try:
                active_loop.call_soon_threadsafe(active_tts.cancel)
            except RuntimeError:
                pass

    def close(self):
        self.stop_event.set()
        self.wake.set()
        self._cancel_active()
        # Each renderer observes stop_event and terminates its own process group;
        # no shared render handle can overwrite another lane's process.
        if self.thread:
            self.thread.join(timeout=15)
            if self.thread.is_alive():
                logger.warning("Media pool is still finishing shutdown; leadership remains held")

    def _loop(self):
        while not self.stop_event.is_set():
            if _RUN_LOCK.acquire(blocking=False):
                try:
                    with self._leadership() as owned:
                        if owned and not self.stop_event.is_set():
                            self._recover_db()
                            logger.info(
                                "Tutorial media pool leader: workers=%s queue_limit=%s encoder_threads=%s",
                                self.workers,
                                self.queue_limit,
                                self.encoder_threads,
                            )
                            self.lanes = [
                                threading.Thread(
                                    target=self._lane_loop, name=f"tutorial-media-{index + 1}", daemon=True
                                )
                                for index in range(self.workers)
                            ]
                            try:
                                for lane in self.lanes:
                                    lane.start()
                                while any(lane.is_alive() for lane in self.lanes):
                                    # Also fail closed while idle or while all
                                    # lanes are inside external rendering/TTS.
                                    with self.factory() as db:
                                        self._fence(db)
                                    for lane in self.lanes:
                                        lane.join(timeout=0.1)
                            finally:
                                self.stop_event.set()
                                self.wake.set()
                                self._cancel_active()
                                for lane in self.lanes:
                                    if lane.ident is not None:
                                        lane.join()
                except Exception:
                    logger.exception("Tutorial media pool leadership failed")
                finally:
                    _RUN_LOCK.release()
            if not self.stop_event.is_set():
                self.wake.wait(2)
                self.wake.clear()

    def _lane_loop(self):
        try:
            self._consume()
        finally:
            with self.activity_lock:
                self.activities.pop(threading.get_ident(), None)

    def _consume(self):
        while not self.stop_event.is_set():
            try:
                worked = self._run_claimed()
            except Exception:
                logger.exception("Tutorial media worker failed")
                worked = False
            if not worked:
                self.wake.wait(2)
                self.wake.clear()

    def _stage(self, task_id, stage):
        with self.factory() as db:
            self._fence(db)
            db.execute(
                update(TutorialMediaTask)
                .where(TutorialMediaTask.id == task_id, TutorialMediaTask.status == "running")
                .values(stage=stage)
            )
            db.commit()

    def run_next(self):
        # Synchronous one-job entry used by maintenance/tests. Pool lanes already
        # own leadership and call _run_claimed directly.
        if self.stop_event.is_set():
            return False
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
        with self.claim_lock:
            if self.stop_event.is_set():
                return False
            claimed = self._claim_next()
        if claimed is None:
            return False
        if claimed is True:  # Consumed a stale queued task.
            return True
        task_id, snapshot, kind, mode = claimed
        try:
            with tempfile.TemporaryDirectory(prefix="katrain-media-") as directory:
                result = self._generate(task_id, snapshot, kind, mode, Path(directory))
                if self.stop_event.is_set():
                    raise RuntimeError("Admin process is shutting down; retry explicitly")
                self._stage(task_id, "publishing")
                self._publish(task_id, result)
        except (Exception, asyncio.CancelledError) as exc:
            logger.warning("Tutorial media task %s failed: %s", task_id, exc)
            try:
                with self.factory() as db:
                    self._fence(db)
                    db.execute(
                        update(TutorialMediaTask)
                        .where(TutorialMediaTask.id == task_id, TutorialMediaTask.status == "running")
                        .values(
                            status="failed",
                            error=f"{type(exc).__name__}: {exc}"[:2000],
                            finished_at=datetime.now(timezone.utc),
                        )
                    )
                    db.commit()
            except _LeadershipLost:
                # The successor owns recovery. An old lane cannot change even
                # task status after it has lost its PostgreSQL ownership fence.
                pass
        finally:
            self.wake.set()
        return True

    def _claim_next(self):
        with self.factory() as db:
            self._fence(db)
            running_figures = select(TutorialMediaTask.figure_id).where(TutorialMediaTask.status == "running")
            task = db.scalar(
                select(TutorialMediaTask)
                .where(TutorialMediaTask.status == "queued", TutorialMediaTask.figure_id.not_in(running_figures))
                .order_by(TutorialMediaTask.created_at, TutorialMediaTask.id)
                .limit(1)
            )
            if task is None:
                return None
            figure = db.get(TutorialFigure, task.figure_id)
            if (
                figure is None
                or not generation_eligibility(figure, db=db)["authorized"]
                or digest(_current_inputs(db, figure, task)) != task.input_digest
            ):
                task.status, task.stage = "stale", "stale"
                task.error = "Generation authorization or saved media inputs changed before generation"
                task.finished_at = datetime.now(timezone.utc)
                db.commit()
                return True
            claimed = db.execute(
                update(TutorialMediaTask)
                .where(TutorialMediaTask.id == task.id, TutorialMediaTask.status == "queued")
                .values(status="running", stage="preparing", started_at=datetime.now(timezone.utc))
            )
            if claimed.rowcount != 1:
                db.rollback()
                return None
            db.commit()
            return task.id, copy.deepcopy(task.snapshot), task.kind, task.render_mode

    async def _speech(self, narration, voice, audio_path):
        ident = threading.get_ident()
        with self.activity_lock:
            self.activities[ident] = {"loop": asyncio.get_running_loop(), "tts": asyncio.current_task()}
        try:
            if self.stop_event.is_set():
                raise asyncio.CancelledError("Admin process is shutting down")
            return await asyncio.wait_for(synthesize_audio(narration, voice, audio_path), timeout=180)
        finally:
            with self.activity_lock:
                self.activities.pop(ident, None)

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
        from katrain.web.tutorials.media_render import render_timeout_seconds

        timeout_seconds = render_timeout_seconds(spec.get("output_profile")) + 20
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
            ident = threading.get_ident()
            with self.activity_lock:
                self.activities[ident] = {"render": process}
            deadline = time.monotonic() + timeout_seconds
            try:
                while process.poll() is None:
                    if self.stop_event.wait(0.05):
                        raise RuntimeError("Admin process shut down during rendering; retry explicitly")
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Tutorial render process exceeded {timeout_seconds} seconds")
                if self.stop_event.is_set():
                    raise RuntimeError("Admin process shut down during rendering; retry explicitly")
                if process.returncode:
                    log.seek(0, 2)
                    log.seek(max(0, log.tell() - 2000))
                    raise RuntimeError("Tutorial renderer failed: " + log.read().decode("utf-8", errors="replace"))
            finally:
                self._terminate_render(process)
                with self.activity_lock:
                    self.activities.pop(ident, None)

    def _upload(self, key, path, content_type):
        with path.open("rb") as source:
            self.storage.put(key, source, content_type=content_type)

    def _generate(self, task_id, snapshot, kind, mode, directory):
        output_profile = snapshot.get("output_profile") if kind == "video" else None
        profile = render_profile(output_profile)
        prefix = f"tutorial_assets/{snapshot['book_slug']}/media/{task_id}"
        audio_path = directory / "audio.mp3"
        timing, audio = snapshot.get("speech_timing"), snapshot.get("audio")
        narration = snapshot["narration"]
        _, pronunciation = prepare_speech(narration, snapshot["voice"])
        valid_audio = (
            kind == "video"
            and audio
            and timing
            and snapshot.get("audio_asset") == audio.get("asset")
            and timing.get("narration_sha256") == narration_hash(narration)
            and timing.get("voice") == snapshot["voice"]
            and timing.get("audio_sha256") == audio.get("sha256")
            and audio.get("narration_sha256") == timing.get("narration_sha256")
            and audio.get("voice") == timing.get("voice")
            and audio.get("duration_ms") == timing.get("duration_ms")
            and timing.get("schema_version") == 1
            and pronunciation_is_current(narration, snapshot["voice"], audio, timing)
        )
        if kind == "video" and not valid_audio:
            raise RuntimeError(
                "Video requires valid previously completed audio with current pronunciation; generate audio first"
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
            if pronunciation:
                audio["pronunciation_sha256"] = pronunciation
                timing["pronunciation_sha256"] = pronunciation
        align_boundaries(narration, timing["boundaries"])
        payload = snapshot.get("board_payload") or {}
        presentation = snapshot.get("presentation") or snapshot
        cues = build_step_cues(
            payload,
            narration,
            timing,
            presentation_plan=presentation.get("presentation_plan"),
            source_identity=presentation.get("source_identity"),
        )
        result = {
            "audio": audio,
            "speech_timing": timing,
            "generated_audio": generated_audio,
            "step_cues": {**cues, "asset": prefix + "/step_cues.json"},
        }
        if kind == "video":
            self._stage(task_id, "aligning_replay")
            if cues["status"] != "complete":
                raise RuntimeError("Recording presentation needs calibration: " + cues["reason"])
            frames = cues["frames"]
            self._stage(task_id, "rendering_video")
            video_path = directory / "video.mp4"
            self._render_video(
                narration=narration,
                board_payload=payload,
                frames=frames,
                speech_timing=timing,
                step_cues=cues,
                audio_path=audio_path,
                output_path=video_path,
                render_mode=mode,
                visual_seed=snapshot.get("visual_seed", "tutorial"),
                output_profile=output_profile,
                encoder_threads=self.encoder_threads,
            )
            if not video_path.is_file() or not video_path.stat().st_size:
                raise RuntimeError("Renderer returned empty video")
            checksum = hashlib.sha256()
            with video_path.open("rb") as video_source:
                for chunk in iter(lambda: video_source.read(1024 * 1024), b""):
                    checksum.update(chunk)
            file_sha256 = checksum.hexdigest()
            result.update(
                step_cues={**cues, "asset": prefix + "/step_cues.json"},
                video={
                    "asset": prefix + f"/video-{mode}{'-' + output_profile if output_profile else ''}.mp4",
                    "output_profile": output_profile,
                    "renderer_recipe": profile.renderer_recipe,
                    "width": profile.width,
                    "height": profile.height,
                    "fps": profile.fps,
                    "sha256": file_sha256,
                    "dependencies_sha256": digest(
                        {
                            **{
                                key: snapshot[key]
                                for key in (
                                    "board_content_sha256",
                                    "board_review_sha256",
                                    "narration",
                                    "voice",
                                    "board_payload",
                                )
                            },
                            "audio_asset": audio["asset"],
                            "audio": audio,
                            "speech_timing": timing,
                            "presentation": {
                                key: cues[key]
                                for key in ("presentation_plan", "source_identity", "presentation_sha256")
                            },
                        }
                    ),
                    "duration_ms": probe_duration(video_path),
                    "size_bytes": video_path.stat().st_size,
                    "audio_sha256": timing["audio_sha256"],
                    "replay_sha256": cues["replay_sha256"],
                    "playback_mode": cues["mode"],
                    "presentation_sha256": cues["presentation_sha256"],
                    "presentation_plan": cues["presentation_plan"],
                    "source_identity": cues["source_identity"],
                    "presentation_objects": cues["objects"],
                    "presentation_events": cues["events"],
                    "presentation_asset": prefix + "/step_cues.json",
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
            self._fence(db)
            task = db.get(TutorialMediaTask, task_id)
            if task is None or task.status != "running":
                return
            figure = db.get(TutorialFigure, task.figure_id, with_for_update=True)
            if (
                figure is None
                or not generation_eligibility(figure, db=db)["authorized"]
                or digest(_current_inputs(db, figure, task)) != task.input_digest
            ):
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
                    values.update(video_2d_review=None, video_3d_review=None)
                    values.update(video_asset=None, video_duration_ms=None, video_size_bytes=None)
                if digest(figure.board_payload) == digest(task.snapshot.get("board_payload")):
                    media["step_cues"] = result["step_cues"]
                if task.kind == "video":
                    output_profile = task.snapshot.get("output_profile")
                    review_key = f"video_{task.render_mode}_review"
                    values[review_key] = with_profile(
                        values.get(review_key, getattr(figure, review_key)), output_profile, None
                    )
                    media["step_cues"] = result["step_cues"]
                    videos = media.setdefault("videos", {})
                    videos[task.render_mode] = with_profile(
                        videos.get(task.render_mode), output_profile, result["video"]
                    )
                    if task.render_mode == "2d" and output_profile in (None, GALAXY):
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
