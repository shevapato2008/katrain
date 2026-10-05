import copy
import csv
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from scripts import kifu_batch_transfer as batch
from katrain.cron.db import Base
from katrain.cron.models import KifuAlbumDB as Album, KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move, ReportTaskDB
from katrain.cron.report_position import position_snapshot


def game(number, moves=1):
    sgf = f"(;GM[1]SZ[9]KM[7.5]C[game {number}]" + ";" + ";".join(["B[aa]", "W[bb]", "B[cc]"][:moves]) + ")"
    return {
        "album_id": number,
        "date_sort": "2026-10-05",
        "date_played": "2026-10-05",
        "sgf_content": sgf,
        "sgf_sha256": batch.sgf_hash(sgf),
        "total_moves": moves,
    }


@pytest.fixture
def manifest():
    body = {
        "format": "kifu-batch-manifest-v1",
        "created_at": "2026-10-06T00:00:00+00:00",
        "model_sha256": batch.MODEL_SHA256,
        "requested_visits": 2000,
        "games": [game(i) for i in range(100, 150)],
    }
    return {**body, "manifest_sha256": batch.digest(body)}


@pytest.fixture
def database(tmp_path):
    engine = batch.sqlite_engine(tmp_path / "production.sqlite3")
    Base.metadata.create_all(engine, tables=batch.worker_tables())
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE kifu_albums ADD COLUMN date_sort TEXT"))
        conn.execute(text("ALTER TABLE kifu_albums ADD COLUMN date_played TEXT"))
    yield engine
    engine.dispose()


def put_catalog(engine, games):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO kifu_albums (id, sgf_content, date_sort, date_played) "
                "VALUES (:album_id, :sgf_content, :date_sort, :date_played)"
            ),
            games,
        )


def response(request_id, turn):
    return {
        "id": request_id,
        "turnNumber": turn,
        "isDuringSearch": False,
        "_wrapper": {
            "model_sha256": batch.MODEL_SHA256,
            "model_sha256_verified": True,
            "selected_model": "tf3-b11c768",
        },
        "rootInfo": {"visits": 2003, "winrate": 0.5, "scoreLead": turn * 0.25},
        "moveInfos": [
            {"move": "A9", "visits": 1500, "winrate": 0.5, "scoreLead": turn * 0.25, "prior": 0.2, "pv": ["A9"]}
        ],
        "ownership": [0.0] * 81,
    }


def result_for(game):
    parsed, moves, previous = batch.parsed_game(game["sgf_content"]), [], None
    for number in range(game["total_moves"] + 1):
        snapshot = position_snapshot(response("fixture", number), parsed, number, previous)
        snapshot.pop("status")
        moves.append({"move_number": number, **snapshot})
        previous = SimpleNamespace(**snapshot)
    start = datetime(2026, 10, 6, tzinfo=timezone.utc)
    return {
        "album_id": game["album_id"],
        "sgf_sha256": game["sgf_sha256"],
        "total_moves": game["total_moves"],
        "started_at": start.isoformat(),
        "completed_at": (start + timedelta(seconds=len(moves) * 3)).isoformat(),
        "moves": moves,
    }


def bundles_for(manifest):
    bundles = []
    for worker, games in enumerate(batch.partitions(manifest)):
        body = {
            "format": "kifu-batch-results-v1",
            "manifest_sha256": manifest["manifest_sha256"],
            "worker_id": f"gpu{worker}",
            "model_sha256": batch.MODEL_SHA256,
            "requested_visits": 2000,
            "games": [result_for(g) for g in games],
        }
        bundles.append({**body, "results_sha256": batch.digest(body)})
    return bundles


def test_snapshot_selects_latest_exactly_50_excluding_completed_bytes_and_aliases(database):
    games = [game(i) for i in range(1, 71)]
    games += [
        {**game(71), "sgf_content": games[69]["sgf_content"]},
        game(72),
        game(73),
        {**game(74), "sgf_content": games[66]["sgf_content"]},
        {**game(999), "date_sort": "2020-01-01"},
    ]
    put_catalog(database, games)
    with Session(database) as db, db.begin():
        db.get(Album, 72).duplicate_of_id = 68
        db.get(Album, 73).sgf_content = "(;SZ[9])"
        for number, model, sha in [
            (70, batch.MODEL_SHA256, batch.sgf_hash(games[69]["sgf_content"])),
            (69, "0" * 64, batch.sgf_hash(games[68]["sgf_content"])),
            (68, batch.MODEL_SHA256, "0" * 64),
        ]:
            db.add(
                Job(
                    album_id=number,
                    sgf_sha256=sha,
                    model_sha256=model,
                    requested_visits=2000,
                    total_moves=1,
                    analyzed_moves=1,
                    status="completed",
                )
            )
    manifest = batch.export_manifest(database)
    assert [g["album_id"] for g in manifest["games"]] == [74, 69, 68, *range(66, 19, -1)]
    batch.validate_manifest(manifest)
    with pytest.raises(OperationalError), batch.read_snapshot(database) as conn:
        conn.execute(text("DELETE FROM kifu_analysis_jobs"))
    with Session(database) as db:
        assert db.query(Job).count() == 3


def test_frozen_manifest_rejects_changed_content_or_expanded_scope(manifest):
    changed = copy.deepcopy(manifest)
    changed["games"][0]["sgf_content"] += " "
    with pytest.raises(batch.BatchError, match="checksum"):
        batch.validate_manifest(changed)
    changed["games"].append(game(999))
    changed["manifest_sha256"] = batch.digest({k: v for k, v in changed.items() if k != "manifest_sha256"})
    with pytest.raises(batch.BatchError, match="exactly 50"):
        batch.validate_manifest(changed)


def test_initialization_reuses_bounded_admission_and_isolates_databases(manifest, tmp_path, monkeypatch):
    calls = []
    original = batch.subprocess.run

    def admission(command, **kwargs):
        calls.append(command[4:])
        assert kwargs["env"]["KATRAIN_DATABASE_URL"].startswith("sqlite:///")
        return original(command, **kwargs)

    monkeypatch.setattr(batch.subprocess, "run", admission)
    directory = tmp_path / "workers"
    assignment = batch.init_workers(manifest, directory)
    assert sorted(len(ids) for ids in calls) == [5, 5, 20, 20]
    assert set(assignment["gpu0"]["album_ids"]).isdisjoint(assignment["gpu1"]["album_ids"])
    assert assignment["gpu0"]["positions"] == assignment["gpu1"]["positions"] == 50
    assert batch.init_workers(manifest, directory) == assignment
    engines = [batch.sqlite_engine(directory / f"gpu{i}.sqlite3") for i in range(2)]
    try:
        for index, engine in enumerate(engines):
            with Session(engine) as db:
                assert db.query(Job).count() == 25
                batch.check_worker_db(db, batch.partitions(manifest)[index])
        with Session(engines[0]) as first, Session(engines[1]) as second:
            first.query(Job).first().status = "failed"
            first.flush()
            assert all(job.status == "pending" for job in second.query(Job))
            first.rollback()
        with batch.worker_lock(directory, 0), pytest.raises(batch.BatchError, match="already in use"):
            with batch.worker_lock(directory, 0):
                pass
    finally:
        for engine in engines:
            engine.dispose()


def test_admission_skipping_with_success_exit_is_rejected(manifest, tmp_path, monkeypatch):
    monkeypatch.setattr(batch.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    with pytest.raises(batch.BatchError, match="Admission skipped"):
        batch.init_workers(manifest, tmp_path / "workers")


@pytest.mark.parametrize("defect", ["missing", "extra", "gap", "shallow"])
def test_result_validation_rejects_incomplete_or_shallow_positions(defect):
    selected = game(123)
    moves = result_for(selected)["moves"]
    if defect == "missing":
        moves.pop()
    elif defect == "extra":
        moves.append(copy.deepcopy(moves[-1]))
    elif defect == "gap":
        moves[1]["move_number"] = 2
    else:
        moves[1]["root_visits"] = 1999
    with pytest.raises(batch.BatchError):
        batch.validate_moves(selected, moves)


def test_import_is_dry_by_default_remaps_rows_and_is_idempotent_by_completed_identity(database, manifest):
    put_catalog(database, manifest["games"])
    bundles = bundles_for(manifest)
    with Session(database) as db, db.begin():
        db.add(ReportTaskDB(id=9000, user_id=1, user_game_id="unrelated", status="pending"))
    assert len(batch.import_results(database, manifest, bundles)) == 50
    with Session(database) as db:
        assert db.query(Job).count() == 0
    assert {r["action"] for r in batch.import_results(database, manifest, bundles, apply=True)} == {"insert"}
    with Session(database) as db:
        assert db.query(Job).count() == 50
        assert db.query(Move).count() == 100
        for job in db.query(Job):
            assert job.status == "completed" and job.analyzed_moves == 1
            assert db.query(Move).filter_by(job_id=job.id).count() == 2
        assert db.get(ReportTaskDB, 9000).status == "pending"
        # A valid existing result under the same identity is authoritative even
        # when a repeated search had a slightly different visit overshoot.
        row = db.query(Move).first()
        row.root_visits = 2004
        db.commit()
    assert {r["action"] for r in batch.import_results(database, manifest, bundles, apply=True)} == {"already_completed"}
    with Session(database) as db:
        assert db.query(Move).count() == 100
        assert db.query(Move).first().root_visits == 2004


def test_import_rechecks_canonical_sgf_and_rejects_inconsistent_partial(database):
    selected = game(123)
    put_catalog(database, [selected])
    result = result_for(selected)
    sessions = sessionmaker(bind=database)
    with sessions() as db, db.begin():
        db.get(Album, 123).sgf_content += " "
    with pytest.raises(batch.BatchError, match="Production SGF changed"):
        batch.import_game(sessions, selected, result, apply=True)
    with sessions() as db, db.begin():
        album = db.get(Album, 123)
        album.sgf_content = selected["sgf_content"]
        album.duplicate_of_id = 99
    with pytest.raises(batch.BatchError, match="canonical album changed"):
        batch.import_game(sessions, selected, result, apply=True)
    with sessions() as db, db.begin():
        db.get(Album, 123).duplicate_of_id = None
        job = Job(
            album_id=123,
            sgf_sha256=selected["sgf_sha256"],
            model_sha256=batch.MODEL_SHA256,
            requested_visits=2000,
            total_moves=1,
            analyzed_moves=0,
            status="running",
        )
        db.add(job)
        db.flush()
        db.add(Move(job_id=job.id, **{**result["moves"][0], "root_visits": 2004}))
    with pytest.raises(batch.BatchError, match="Inconsistent existing partial"):
        batch.import_game(sessions, selected, result, apply=True)
    with sessions() as db:
        assert db.query(Job).one().status == "running"
        assert db.query(Move).count() == 1


def test_per_game_publish_failure_rolls_back_rows_and_preserves_prior_game(database):
    first, second = game(123), game(124)
    put_catalog(database, [first, second])
    sessions = sessionmaker(bind=database)
    batch.import_game(sessions, first, result_for(first), apply=True)

    def fail_publish(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE kifu_analysis_jobs"):
            raise RuntimeError("simulate failure after move flush")

    event.listen(database, "before_cursor_execute", fail_publish)
    try:
        with pytest.raises(RuntimeError, match="after move flush"):
            batch.import_game(sessions, second, result_for(second), apply=True)
    finally:
        event.remove(database, "before_cursor_execute", fail_publish)
    with sessions() as db:
        assert [job.album_id for job in db.query(Job)] == [123]
        assert db.query(Move).count() == 2
    assert batch.import_game(sessions, second, result_for(second), apply=True) == "insert"


@pytest.mark.asyncio
async def test_runner_stops_stalls_resumes_existing_worker_and_flushes_completed_csv(manifest, tmp_path, monkeypatch):
    from katrain.cron.jobs import kifu_analyze

    directory = tmp_path / "workers"
    batch.init_workers(manifest, directory)
    engine = batch.sqlite_engine(directory / "gpu0.sqlite3")
    sessions = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(kifu_analyze, "SessionLocal", sessions)
    monkeypatch.setattr(kifu_analyze.config, "KATAGO_EXPECTED_MODEL_SHA256", batch.MODEL_SHA256)
    monkeypatch.setattr(kifu_analyze.config, "HUMAN_SL_PROFILE", "")
    metrics = directory / "gpu0.timings.json"

    async def no_progress():
        return None

    with pytest.raises(batch.BatchError, match="stalled"):
        await batch.run_loop(SimpleNamespace(run=no_progress), sessions, manifest, 0, metrics, stall_seconds=0.01)
    worker = kifu_analyze.KifuAnalyzeJob()
    requests = []

    async def analyze(**kwargs):
        requests.append(kwargs["request_id"])
        return response(kwargs["request_id"], kwargs["analyze_turns"][0])

    worker.client.analyze = analyze
    real_run = worker.run
    calls = 0

    async def interrupted():
        nonlocal calls
        calls += 1
        if calls == 4:  # One completed game and the root of the next are durable.
            raise RuntimeError("simulated interruption")
        await real_run()

    worker.run = interrupted
    try:
        with pytest.raises(RuntimeError, match="interruption"):
            await batch.run_loop(worker, sessions, manifest, 0, metrics)
        with (directory / "gpu0.progress.csv").open() as handle:
            initial = list(csv.DictReader(handle))
        assert len(initial) == 1 and int(initial[0]["root_visits"]) == 4006
        worker.run = real_run
        await batch.run_loop(worker, sessions, manifest, 0, metrics)
        with (directory / "gpu0.progress.csv").open() as handle:
            completed = list(csv.DictReader(handle))
        assert len(completed) == 25
        assert completed[0] == initial[0]
        assert len(requests) == len(set(requests)) == 50
        assert batch.read_artifact(metrics)["root_visits"] == 25 * 4006
        bundle = batch.export_results(manifest, 0, engine)
        assert len(bundle["games"]) == 25
        with sessions() as db, db.begin():
            db.query(Job).first().status = "failed"
        with pytest.raises(batch.BatchError, match="failed job"):
            await batch.run_loop(worker, sessions, manifest, 0, metrics)
    finally:
        engine.dispose()
