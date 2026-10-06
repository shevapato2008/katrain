"""One position per run for explicitly admitted professional kifu jobs."""

import hashlib
import logging
from datetime import datetime, timezone

from katrain.cron import config
from katrain.cron.clients.katago import KataGoClient
from katrain.cron.db import SessionLocal
from katrain.cron.jobs.base import BaseJob
from katrain.cron.models import (
    KifuAlbumDB, KifuAnalysisJobDB, KifuAnalysisMoveDB, ReportTaskDB, LiveAnalysisDB,
    PRIORITY_LIVE_BACKFILL,
)
from katrain.cron.report_position import position_snapshot
from katrain.cron.sgf import parse_game
from katrain.cron.kifu_parameters import ParameterError, validate_parameters

logger = logging.getLogger("katrain_cron.kifu_analyze")


class KifuAnalyzeJob(BaseJob):
    name = "kifu_analyze"
    interval_seconds = 10

    def __init__(self):
        super().__init__()
        self.client = KataGoClient(timeout=config.KIFU_ANALYSIS_TIMEOUT)

    async def run(self) -> None:
        # Admission is explicit. Yield before every position to interactive work.
        if not config.KATAGO_EXPECTED_MODEL_SHA256:
            raise RuntimeError("Kifu analysis requires a pinned KataGo model SHA")
        with SessionLocal() as db:
            if db.query(ReportTaskDB.id).filter(ReportTaskDB.status.in_(("pending", "running"))).first():
                return
            if db.query(LiveAnalysisDB.id).filter(
                LiveAnalysisDB.status.in_(("pending", "running")),
                LiveAnalysisDB.priority >= PRIORITY_LIVE_BACKFILL,
            ).first():
                return
            job = (
                db.query(KifuAnalysisJobDB)
                .filter(KifuAnalysisJobDB.status.in_(("running", "pending")))
                .order_by(KifuAnalysisJobDB.created_at, KifuAnalysisJobDB.id)
                .first()
            )
            if job is None:
                return
            job_id = job.id
            album_id = job.album_id
            model_sha256 = job.model_sha256
            album = db.query(KifuAlbumDB).filter(KifuAlbumDB.id == job.album_id).first()
            if album is None or album.duplicate_of_id is not None:
                self._fail(job, "Canonical professional SGF not found")
                db.commit()
                return
            sgf = album.sgf_content
            if hashlib.sha256(sgf.encode("utf-8")).hexdigest() != job.sgf_sha256:
                self._fail(job, "Professional SGF changed after admission")
                db.commit()
                return
            if job.model_sha256 != config.KATAGO_EXPECTED_MODEL_SHA256 or job.requested_visits != 2000:
                self._fail(job, "Pinned model or visits changed")
                db.commit()
                return
            parsed = parse_game(sgf)
            try:
                parameters = validate_parameters(sgf, job.analysis_parameters)
            except ParameterError as exc:
                self._fail(job, str(exc))
                db.commit()
                return
            parameter_sha256 = parameters["parameter_sha256"]
            parsed.rules, parsed.komi = parameters["rules"], parameters["komi"]
            if parsed.dropped_midgame_setup or parsed.invalid_moves or len(parsed.moves) != job.total_moves:
                self._fail(job, "SGF cannot be replayed faithfully")
                db.commit()
                return
            rows = (
                db.query(KifuAnalysisMoveDB)
                .filter(KifuAnalysisMoveDB.job_id == job_id)
                .order_by(KifuAnalysisMoveDB.move_number)
                .all()
            )
            if any(row.parameter_sha256 != parameter_sha256 for row in rows):
                self._fail(job, "parameter_mismatch: Stored positions require reanalysis with verified parameters")
                db.commit()
                return
            if len(rows) > job.total_moves + 1 or any(
                row.move_number != position or row.root_visits < 2000 for position, row in enumerate(rows)
            ):
                self._fail(job, "Stored analysis positions are not contiguous or deep enough")
                db.commit()
                return
            move_number = len(rows)
            if move_number > job.total_moves:
                job.status = "completed"
                job.analyzed_moves = job.total_moves
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
            job.status = "running"
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.error_message = None
            db.commit()

        request_id = f"kifu_{job_id}_{move_number}"
        try:
            response = await self.client.analyze(
                request_id=request_id,
                moves=[[color, coord] for color, coord in parsed.moves[:move_number]],
                rules=parsed.rules, komi=parsed.komi, board_size=parsed.board_size,
                max_visits=2000, analyze_turns=[move_number], include_ownership=True,
                include_policy=False, initial_stones=parsed.initial_stones,
                initial_player=parsed.initial_player, priority=1,
            )
            KataGoClient.validate_result(response, request_id, move_number, parsed.board_size, model_sha256, 2000)
        except Exception as exc:
            logger.warning("Professional job %s position %s failed: %s", job_id, move_number, exc)
            with SessionLocal() as db:
                job = db.query(KifuAnalysisJobDB).filter(KifuAnalysisJobDB.id == job_id).first()
                if job and job.analysis_parameters == parameters and job.status == "running":
                    job.retry_count = (job.retry_count or 0) + 1
                    job.status = "failed" if job.retry_count >= 3 else "pending"
                    job.error_message = f"Position {move_number}: {type(exc).__name__}: {exc}"
                    db.commit()
            return

        with SessionLocal() as db:
            # Same lock order as admission/import; keep the album stable through
            # the position commit without holding locks during engine search.
            album = db.query(KifuAlbumDB).filter_by(id=album_id).with_for_update().first()
            job = db.query(KifuAnalysisJobDB).filter(KifuAnalysisJobDB.id == job_id).with_for_update().first()
            if job is None or album is None or hashlib.sha256(album.sgf_content.encode("utf-8")).hexdigest() != job.sgf_sha256:
                if job:
                    self._fail(job, "Professional SGF changed during analysis")
                    db.commit()
                return
            # A result belongs to the exact admitted engine request, including
            # parameters. Discard in-flight work after reset/import/metadata edits.
            if (
                job.status != "running"
                or job.analysis_parameters != parameters
                or job.model_sha256 != model_sha256
                or job.requested_visits != 2000
                or job.album_id != album_id
                or job.total_moves != len(parsed.moves)
                or album.duplicate_of_id is not None
            ):
                return
            try:
                validate_parameters(album.sgf_content, job.analysis_parameters)
            except ParameterError as exc:
                self._fail(job, str(exc))
                db.commit()
                return
            stored = (
                db.query(
                    KifuAnalysisMoveDB.move_number, KifuAnalysisMoveDB.root_visits, KifuAnalysisMoveDB.parameter_sha256
                )
                .filter_by(job_id=job_id)
                .order_by(KifuAnalysisMoveDB.move_number)
                .all()
            )
            if any(row.parameter_sha256 != parameter_sha256 for row in stored):
                self._fail(job, "parameter_mismatch: Stored positions changed during analysis")
                db.commit()
                return
            if any(row.move_number != number or row.root_visits < 2000 for number, row in enumerate(stored)):
                self._fail(job, "Stored analysis positions changed during analysis")
                db.commit()
                return
            if len(stored) != move_number:
                return  # Another worker committed or a reset removed the prefix.
            previous = db.query(KifuAnalysisMoveDB).filter(
                KifuAnalysisMoveDB.job_id == job_id, KifuAnalysisMoveDB.move_number == move_number - 1,
            ).first() if move_number else None
            snapshot = position_snapshot(response, parsed, move_number, previous, config.HUMAN_SL_PROFILE or None)
            snapshot.pop("status")
            db.add(
                KifuAnalysisMoveDB(
                    job_id=job_id, move_number=move_number, parameter_sha256=parameter_sha256, **snapshot
                )
            )
            job.analyzed_moves = move_number
            job.retry_count = 0
            job.error_message = None
            if move_number == job.total_moves:
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def _fail(job: KifuAnalysisJobDB, reason: str) -> None:
        job.status = "failed"
        job.error_message = reason
