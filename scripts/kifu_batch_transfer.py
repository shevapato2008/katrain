"""Frozen 50-game professional batch: production export -> two home workers -> production import.

Run as ``python -m scripts.kifu_batch_transfer --help``. Production commands read
KATRAIN_DATABASE_URL from the environment; it is never included in artifacts.
Only run-worker contacts KataGo. import-results defaults to validation/dry run.
"""

import argparse
import asyncio
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from sqlalchemy import column, create_engine, event, func, inspect, select, table
from sqlalchemy.orm import Session, sessionmaker

from katrain.cron.sgf import parse_game


MODEL_SHA256 = "93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871"
VISITS = 2000
BATCH_SIZE = 50
ROOT = Path(__file__).resolve().parents[1]
MOVE_FIELDS = (
    "move_number",
    "root_visits",
    "visits",
    "winrate",
    "score_lead",
    "top_moves",
    "ownership",
    "actual_move",
    "actual_player",
    "delta_score",
    "delta_winrate",
    "grade",
    "points_lost",
    "points_lost_source",
    "is_top_move",
    "top_prior",
    "brilliance",
)


class BatchError(ValueError):
    """A bounded batch invariant failed; messages contain no connection settings."""


def require(condition, message):
    if not condition:
        raise BatchError(message)


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite stores the worker's UTC timestamps without tzinfo.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        require(parsed.tzinfo is not None, "Timestamp must include a timezone")
        return parsed
    except (TypeError, ValueError) as exc:
        raise BatchError("Invalid UTC timestamp") from exc


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def sgf_hash(sgf):
    return hashlib.sha256(sgf.encode("utf-8")).hexdigest()


def read_artifact(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def write_artifact(path, value, *, replace=False):
    path = Path(path)
    if path.exists() and not replace:
        require(read_artifact(path) == value, "Output already exists with different content")
        return
    data = json_bytes(value)
    if path.suffix == ".gz":
        data = gzip.compress(data, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".kifu-batch-", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def worker_lock(directory, worker):
    with (Path(directory) / f"gpu{worker}.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BatchError(f"gpu{worker} is already in use") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def read_snapshot(engine):
    """No accidental writes; catalog and completion checks share one snapshot."""
    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)
            conn.begin()
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA query_only=ON")
            conn.exec_driver_sql("BEGIN")
        else:
            raise BatchError("Only PostgreSQL and isolated SQLite are supported")
        try:
            yield conn
        finally:
            conn.rollback()
            if engine.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA query_only=OFF")
                conn.commit()


def parsed_game(sgf):
    parsed = parse_game(sgf)
    require(bool(parsed.moves) and not parsed.invalid_moves and not parsed.dropped_midgame_setup, "Unsupported SGF")
    require(math.isfinite(parsed.komi), "Nonfinite SGF komi")
    return parsed


def validate_manifest(manifest):
    require(manifest.get("format") == "kifu-batch-manifest-v1", "Unsupported manifest format")
    require(
        manifest.get("model_sha256") == MODEL_SHA256 and manifest.get("requested_visits") == VISITS,
        "Manifest model/visits mismatch",
    )
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    require(manifest.get("manifest_sha256") == digest(body), "Manifest checksum mismatch")
    games = manifest.get("games", [])
    require(len(games) == BATCH_SIZE, "Manifest must contain exactly 50 games")
    require(len({g["album_id"] for g in games}) == BATCH_SIZE, "Repeated album ID")
    require(len({g["sgf_sha256"] for g in games}) == BATCH_SIZE, "Repeated exact SGF")
    for game in games:
        require(type(game["album_id"]) is int and game["album_id"] > 0, "Invalid album ID")
        require(sgf_hash(game["sgf_content"]) == game["sgf_sha256"], "Frozen SGF checksum mismatch")
        require(len(parsed_game(game["sgf_content"]).moves) == game["total_moves"], "Frozen SGF move count mismatch")
    return games


def export_manifest(engine):
    from katrain.cron.models import KifuAnalysisJobDB as Job

    # The cron album mapper intentionally has no date_sort/date_played columns.
    albums = table(
        "kifu_albums", *(column(name) for name in ("id", "duplicate_of_id", "date_sort", "date_played", "sgf_content"))
    )
    games = []
    with read_snapshot(engine) as conn:
        completed = conn.execute(
            select(Job.sgf_sha256, albums.c.sgf_content)
            .join(albums, albums.c.id == Job.album_id)
            .where(
                Job.status == "completed",
                Job.model_sha256 == MODEL_SHA256,
                Job.requested_visits == VISITS,
            )
        )
        # Compare actual bytes too; changed source content is not a completed identity.
        seen = {sgf for sha, sgf in completed if sgf_hash(sgf) == sha}
        query = (
            select(albums)
            .where(albums.c.duplicate_of_id.is_(None))
            .order_by(albums.c.date_sort.desc().nulls_last(), albums.c.id.desc())
        )
        with conn.execute(query.execution_options(stream_results=True)).yield_per(128) as rows:
            for album in rows.mappings():
                sgf = album["sgf_content"]
                if sgf in seen:
                    continue
                try:
                    parsed = parsed_game(sgf)
                except BatchError:
                    continue
                seen.add(sgf)
                games.append(
                    {
                        "album_id": album["id"],
                        "date_sort": album["date_sort"],
                        "date_played": album["date_played"],
                        "sgf_content": sgf,
                        "sgf_sha256": sgf_hash(sgf),
                        "total_moves": len(parsed.moves),
                    }
                )
                if len(games) == BATCH_SIZE:
                    break
    require(len(games) == BATCH_SIZE, "Fewer than 50 eligible unanalysed SGFs")
    body = {
        "format": "kifu-batch-manifest-v1",
        "created_at": iso(utcnow()),
        "model_sha256": MODEL_SHA256,
        "requested_visits": VISITS,
        "games": games,
    }
    return {**body, "manifest_sha256": digest(body)}


def partitions(manifest):
    games = validate_manifest(manifest)
    groups, loads = [[], []], [0, 0]
    for game in sorted(games, key=lambda g: (-g["total_moves"], g["album_id"])):
        worker = min(range(2), key=lambda i: (loads[i], len(groups[i]), i))
        groups[worker].append(game)
        loads[worker] += game["total_moves"] + 1
    return groups


def sqlite_engine(path):
    engine = create_engine("sqlite:///" + str(Path(path).resolve()))

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def worker_tables():
    from katrain.cron.models import (
        KifuAlbumDB,
        KifuAnalysisJobDB,
        KifuAnalysisMoveDB,
        ReportTaskDB,
        LiveMatchDB,
        LiveAnalysisDB,
    )

    return [
        model.__table__
        for model in (KifuAlbumDB, KifuAnalysisJobDB, KifuAnalysisMoveDB, ReportTaskDB, LiveMatchDB, LiveAnalysisDB)
    ]


def check_worker_db(db, games, *, admitted=True):
    from katrain.cron.models import KifuAlbumDB, KifuAnalysisJobDB, ReportTaskDB, LiveMatchDB, LiveAnalysisDB

    expected = {g["album_id"]: g for g in games}
    albums = db.query(KifuAlbumDB).all()
    require({a.id for a in albums} == set(expected), "Worker album roster mismatch")
    for album in albums:
        require(
            album.duplicate_of_id is None and album.sgf_content == expected[album.id]["sgf_content"],
            "Worker SGF differs from the manifest",
        )
    for model in (ReportTaskDB, LiveMatchDB, LiveAnalysisDB):
        require(db.query(model).first() is None, "Worker database contains unrelated work")
    jobs = db.query(KifuAnalysisJobDB).all()
    require(len({j.album_id for j in jobs}) == len(jobs), "Multiple worker identities for one album")
    for job in jobs:
        require(job.album_id in expected, "Worker has an unassigned job")
        game = expected[job.album_id]
        require(
            job.sgf_sha256 == game["sgf_sha256"]
            and job.model_sha256 == MODEL_SHA256
            and job.requested_visits == VISITS
            and job.total_moves == game["total_moves"],
            "Worker job identity mismatch",
        )
    if admitted:
        require({j.album_id for j in jobs} == set(expected), "Admission skipped one or more selected games")


def init_workers(manifest, directory):
    from katrain.cron.db import Base
    from katrain.cron.models import KifuAlbumDB

    groups = partitions(manifest)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with worker_lock(directory, 0), worker_lock(directory, 1):
        frozen = directory / "manifest.json"
        if not frozen.exists():
            require(not any(directory.glob("gpu*.sqlite3")), "Unidentified worker databases already exist")
        write_artifact(frozen, manifest)
        for worker, games in enumerate(groups):
            path = directory / f"gpu{worker}.sqlite3"
            existing = path.exists()
            engine = sqlite_engine(path)
            try:
                if existing:
                    require(
                        set(inspect(engine).get_table_names()) == {t.name for t in worker_tables()},
                        "Unexpected worker database schema",
                    )
                else:
                    Base.metadata.create_all(engine, tables=worker_tables())
                    with Session(engine) as db, db.begin():
                        db.add_all(KifuAlbumDB(id=g["album_id"], sgf_content=g["sgf_content"]) for g in games)
                with Session(engine) as db:
                    check_worker_db(db, games, admitted=False)
                env = {
                    **os.environ,
                    "KATRAIN_DATABASE_URL": "sqlite:///" + str(path),
                    "KATAGO_EXPECTED_MODEL_SHA256": MODEL_SHA256,
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
                for start in range(0, len(games), 20):
                    command = [
                        sys.executable,
                        "-m",
                        "scripts.backfill_kifu_analysis",
                        "--apply",
                        *(str(g["album_id"]) for g in games[start : start + 20]),
                    ]
                    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
                    require(result.returncode == 0, f"gpu{worker} admission process failed")
                with Session(engine) as db:
                    check_worker_db(db, games)
            finally:
                engine.dispose()
    return {
        f"gpu{i}": {"album_ids": [g["album_id"] for g in group], "positions": sum(g["total_moves"] + 1 for g in group)}
        for i, group in enumerate(groups)
    }


def move_payload(row):
    return {key: getattr(row, key) for key in MOVE_FIELDS}


def validate_moves(game, moves, *, complete=True):
    from katrain.cron.clients.katago import KataGoClient

    parsed = parsed_game(game["sgf_content"])
    maximum = len(parsed.moves) + 1
    require(len(moves) == maximum if complete else len(moves) <= maximum, "Wrong position count")
    for number, row in enumerate(moves):
        require(set(row) == set(MOVE_FIELDS), "Unexpected move fields")
        require(type(row["move_number"]) is int and row["move_number"] == number, "Noncontiguous positions")
        expected_player, expected_move = parsed.moves[number - 1] if number else (None, None)
        require((row["actual_player"], row["actual_move"]) == (expected_player, expected_move), "SGF position mismatch")
        ownership = row["ownership"]
        require(
            isinstance(ownership, list)
            and len(ownership) == parsed.board_size
            and all(isinstance(r, list) and len(r) == parsed.board_size for r in ownership),
            "Ownership shape mismatch",
        )
        # Reuse the engine client's numeric/shape validation for the stored snapshot.
        # This adapter does not assert new engine provenance; identity comes from the job.
        response = {
            "id": "stored",
            "turnNumber": number,
            "isDuringSearch": False,
            "_wrapper": {"model_sha256": MODEL_SHA256, "model_sha256_verified": True, "selected_model": "tf3-b11c768"},
            "rootInfo": {"visits": row["root_visits"], "winrate": row["winrate"], "scoreLead": row["score_lead"]},
            "moveInfos": [{**m, "scoreLead": m.get("score_lead")} for m in row["top_moves"]],
            "ownership": [value for r in ownership for value in r],
        }
        try:
            KataGoClient.validate_result(response, "stored", number, parsed.board_size, MODEL_SHA256, VISITS)
        except ValueError as exc:
            raise BatchError(f"Invalid stored analysis at position {number}") from exc
    json_bytes(moves)  # Also rejects NaN/Infinity in optional snapshot fields.


def worker_state(sessions, games):
    from katrain.cron.models import KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move

    with sessions() as db:
        check_worker_db(db, games)
        totals = {
            job_id: (count, visits)
            for job_id, count, visits in db.query(
                Move.job_id, func.count(Move.id), func.sum(Move.root_visits)
            ).group_by(Move.job_id)
        }
        state = []
        for job in db.query(Job).order_by(Job.created_at, Job.id):
            count, visits = totals.get(job.id, (0, 0))
            start, end = iso(job.started_at), iso(job.completed_at)
            elapsed = (timestamp(end or iso(utcnow())) - timestamp(start)).total_seconds() if start else 0
            state.append(
                {
                    "album_id": job.album_id,
                    "status": job.status,
                    "started_at": start,
                    "completed_at": end,
                    "wall_seconds": max(0, elapsed),
                    "positions": count,
                    "root_visits": visits,
                    "root_visits_per_second": visits / elapsed if elapsed > 0 else None,
                }
            )
        return state


def timing_summary(manifest, worker, state):
    starts = [timestamp(g["started_at"]) for g in state if g["started_at"]]
    ends = [timestamp(g["completed_at"]) for g in state if g["completed_at"]]
    done = all(g["status"] == "completed" for g in state)
    elapsed = ((max(ends) if done and ends else utcnow()) - min(starts)).total_seconds() if starts else 0
    visits = sum(g["root_visits"] for g in state)
    return {
        "format": "kifu-batch-timings-v1",
        "manifest_sha256": manifest["manifest_sha256"],
        "worker_id": f"gpu{worker}",
        "wall_seconds": max(0, elapsed),
        "root_visits": visits,
        "root_visits_per_second": visits / elapsed if elapsed > 0 else None,
        "games": state,
    }


def write_progress_csv(path, manifest, worker, state):
    """Rebuild from durable rows on resume; one row per completed game, flushed."""
    fields = (
        "manifest_sha256",
        "worker_id",
        "album_id",
        "started_at",
        "completed_at",
        "wall_seconds",
        "positions",
        "root_visits",
        "root_visits_per_second",
    )
    path = Path(path)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, prefix=".kifu-progress-", delete=False
    ) as handle:
        temporary = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for game in state:
            if game["status"] == "completed":
                writer.writerow(
                    {
                        "manifest_sha256": manifest["manifest_sha256"],
                        "worker_id": f"gpu{worker}",
                        **{key: game[key] for key in fields[2:]},
                    }
                )
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def run_loop(worker, sessions, manifest, worker_index, metrics_path, *, stall_seconds=600):
    require(stall_seconds > 0, "Stall timeout must be positive")
    games = partitions(manifest)[worker_index]
    deadline = time.monotonic() + stall_seconds
    state = worker_state(sessions, games)
    completed = None
    while True:
        write_artifact(metrics_path, timing_summary(manifest, worker_index, state), replace=True)
        current = {g["album_id"] for g in state if g["status"] == "completed"}
        if current != completed:
            write_progress_csv(
                Path(metrics_path).with_name(f"gpu{worker_index}.progress.csv"), manifest, worker_index, state
            )
            completed = current
        require(not any(g["status"] == "failed" for g in state), "Worker has a failed job; inspect its local database")
        if all(g["status"] == "completed" for g in state):
            return
        before = sum(g["positions"] for g in state)
        remaining = deadline - time.monotonic()
        require(remaining > 0, "Worker stalled without committed position growth")
        try:
            await asyncio.wait_for(worker.run(), timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise BatchError("Worker stalled without committed position growth") from exc
        state = worker_state(sessions, games)
        if sum(g["positions"] for g in state) > before:
            deadline = time.monotonic() + stall_seconds
        else:
            await asyncio.sleep(min(1, max(0, deadline - time.monotonic())))


def load_worker(directory, worker):
    directory = Path(directory).resolve()
    manifest = read_artifact(directory / "manifest.json")
    games = partitions(manifest)[worker]
    path = directory / f"gpu{worker}.sqlite3"
    require(path.is_file(), "Worker database is missing; run init-workers first")
    return directory, manifest, games, path


def export_results(manifest, worker_index, engine):
    from katrain.cron.models import KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move

    games = partitions(manifest)[worker_index]
    output = []
    with read_snapshot(engine) as conn, Session(bind=conn) as db:
        check_worker_db(db, games)
        for game in games:
            job = db.query(Job).filter_by(album_id=game["album_id"]).one()
            require(job.status == "completed" and job.analyzed_moves == game["total_moves"], "Worker is incomplete")
            moves = [move_payload(row) for row in db.query(Move).filter_by(job_id=job.id).order_by(Move.move_number)]
            validate_moves(game, moves)
            start, end = iso(job.started_at), iso(job.completed_at)
            require(start is not None and end is not None and timestamp(end) >= timestamp(start), "Invalid job timing")
            output.append(
                {
                    "album_id": game["album_id"],
                    "sgf_sha256": game["sgf_sha256"],
                    "total_moves": game["total_moves"],
                    "started_at": start,
                    "completed_at": end,
                    "moves": moves,
                }
            )
    body = {
        "format": "kifu-batch-results-v1",
        "manifest_sha256": manifest["manifest_sha256"],
        "worker_id": f"gpu{worker_index}",
        "model_sha256": MODEL_SHA256,
        "requested_visits": VISITS,
        "games": output,
    }
    return {**body, "results_sha256": digest(body)}


def validate_results(manifest, bundles):
    groups = partitions(manifest)
    expected = {g["album_id"]: g for g in manifest["games"]}
    require(
        len(bundles) == 2 and {b.get("worker_id") for b in bundles} == {"gpu0", "gpu1"},
        "Both worker results are required",
    )
    results = {}
    for bundle in bundles:
        require(
            bundle.get("format") == "kifu-batch-results-v1"
            and bundle.get("manifest_sha256") == manifest["manifest_sha256"]
            and bundle.get("model_sha256") == MODEL_SHA256
            and bundle.get("requested_visits") == VISITS,
            "Result identity mismatch",
        )
        require(
            bundle.get("results_sha256") == digest({k: v for k, v in bundle.items() if k != "results_sha256"}),
            "Results checksum mismatch",
        )
        assigned = groups[int(bundle["worker_id"][-1])]
        require(
            len(bundle["games"]) == len(assigned)
            and {g["album_id"] for g in bundle["games"]} == {g["album_id"] for g in assigned},
            "Result roster mismatch",
        )
        for result in bundle["games"]:
            game = expected[result["album_id"]]
            require(
                result["sgf_sha256"] == game["sgf_sha256"] and result["total_moves"] == game["total_moves"],
                "Result SGF mismatch",
            )
            require(timestamp(result["completed_at"]) >= timestamp(result["started_at"]), "Invalid job timing")
            validate_moves(game, result["moves"])
            results[game["album_id"]] = result
    return results


def import_game(sessions, game, result, *, apply=False):
    from katrain.cron.models import KifuAlbumDB as Album, KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move

    # Each call owns its connection/transaction. Lock album before checking identity
    # so concurrent catalog edits cannot change the canonical SGF during import.
    with sessions() as db, db.begin():
        query = db.query(Album).filter_by(id=game["album_id"])
        album = (query.with_for_update() if apply else query).first()
        require(album is not None and album.duplicate_of_id is None, "Production canonical album changed")
        require(
            album.sgf_content == game["sgf_content"] and sgf_hash(album.sgf_content) == game["sgf_sha256"],
            "Production SGF changed",
        )
        identity = dict(
            album_id=game["album_id"], sgf_sha256=game["sgf_sha256"], model_sha256=MODEL_SHA256, requested_visits=VISITS
        )
        query = db.query(Job).filter_by(**identity)
        job = (query.with_for_update() if apply else query).first()
        existing = []
        if job:
            require(job.total_moves == game["total_moves"], "Existing job move count mismatch")
            existing = [move_payload(row) for row in db.query(Move).filter_by(job_id=job.id).order_by(Move.move_number)]
            require(job.analyzed_moves == max(0, len(existing) - 1), "Existing progress is inconsistent")
            if job.status == "completed":
                validate_moves(game, existing)
                return "already_completed"
            require(existing == result["moves"][: len(existing)], "Inconsistent existing partial analysis")
        action = "complete_partial" if job else "insert"
        if apply:
            if job is None:
                job = Job(**identity, total_moves=game["total_moves"], analyzed_moves=0, status="pending")
                db.add(job)
                db.flush()
            db.add_all(Move(job_id=job.id, **row) for row in result["moves"][len(existing) :])
            db.flush()
            require(
                db.query(Move).filter_by(job_id=job.id).count() == game["total_moves"] + 1,
                "Imported position count mismatch",
            )
            job.analyzed_moves = game["total_moves"]
            job.started_at = timestamp(result["started_at"])
            job.completed_at = timestamp(result["completed_at"])
            job.error_message = None
            job.retry_count = 0
            job.status = "completed"
        return action


def import_results(engine, manifest, bundles, *, apply=False):
    results = validate_results(manifest, bundles)  # Validate all 50 before any production writes.
    sessions = sessionmaker(bind=engine, autoflush=False)
    return [
        {"album_id": g["album_id"], "action": import_game(sessions, g, results[g["album_id"]], apply=apply)}
        for g in manifest["games"]
    ]


def production_engine():
    url = os.environ.get("KATRAIN_DATABASE_URL")
    require(bool(url), "Set KATRAIN_DATABASE_URL in the production process environment")
    engine = create_engine(url, echo=False, hide_parameters=True)
    require(engine.dialect.name == "postgresql", "Production commands require PostgreSQL")
    return engine


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-manifest", help="Read-only production snapshot; freeze exactly 50 games")
    export.add_argument("--output", required=True)
    initialize = commands.add_parser(
        "init-workers", help="Create/admit two isolated SQLite workers; never contact KataGo"
    )
    initialize.add_argument("--manifest", required=True)
    initialize.add_argument("--work-dir", required=True)
    for command in ("run-worker", "export-results"):
        sub = commands.add_parser(command)
        sub.add_argument("--work-dir", required=True)
        sub.add_argument("--worker", type=int, choices=(0, 1), required=True)
        if command == "run-worker":
            sub.add_argument("--stall-seconds", type=float, default=600)
        else:
            sub.add_argument("--output", required=True)
    importer = commands.add_parser("import-results", help="Validate both worker bundles; write only with --apply")
    importer.add_argument("--manifest", required=True)
    importer.add_argument("--results", nargs=2, required=True)
    importer.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command in ("export-manifest", "import-results"):
            engine = production_engine()
            try:
                if args.command == "export-manifest":
                    manifest = export_manifest(engine)
                    write_artifact(args.output, manifest)
                    print(json.dumps({"manifest_sha256": manifest["manifest_sha256"], "games": BATCH_SIZE}))
                else:
                    outcomes = import_results(
                        engine, read_artifact(args.manifest), [read_artifact(p) for p in args.results], apply=args.apply
                    )
                    print(json.dumps({"applied": args.apply, "games": outcomes}))
            finally:
                engine.dispose()
        elif args.command == "init-workers":
            print(json.dumps(init_workers(read_artifact(args.manifest), args.work_dir)))
        else:
            directory, manifest, games, path = load_worker(args.work_dir, args.worker)
            # Must precede imports of models, db, or the worker: cron binds at import.
            os.environ["KATRAIN_DATABASE_URL"] = "sqlite:///" + str(path)
            os.environ["KATAGO_EXPECTED_MODEL_SHA256"] = MODEL_SHA256
            os.environ["KATAGO_URL"] = f"http://127.0.0.1:{18002 if args.worker == 0 else 8002}"
            os.environ["CRON_HUMAN_SL_PROFILE"] = ""
            with worker_lock(directory, args.worker):
                engine = sqlite_engine(path)
                try:
                    if args.command == "export-results":
                        write_artifact(args.output, export_results(manifest, args.worker, engine))
                    else:
                        from katrain.cron.jobs.kifu_analyze import KifuAnalyzeJob
                        from katrain.cron.db import SessionLocal

                        worker = KifuAnalyzeJob()
                        require(
                            asyncio.run(worker.client.health_check()), "Home engine is not ready with the pinned model"
                        )
                        asyncio.run(
                            run_loop(
                                worker,
                                SessionLocal,
                                manifest,
                                args.worker,
                                directory / f"gpu{args.worker}.timings.json",
                                stall_seconds=args.stall_seconds,
                            )
                        )
                        # Do not report success based on the worker's status alone.
                        export_results(manifest, args.worker, engine)
                finally:
                    engine.dispose()
    except BatchError as exc:
        parser.exit(1, f"Batch stopped: {exc}\n")
    except Exception as exc:
        # Driver/HTTP exception strings can contain URLs, usernames, or parameters.
        parser.exit(1, f"Batch stopped: {type(exc).__name__}; inspect local state without printing credentials\n")


if __name__ == "__main__":
    main()
