"""Professional parameters must be explicit, evidenced and bound to engine input."""

import copy
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session, sessionmaker

from katrain.cron import sgf as sgf_module
from katrain.cron.jobs import kifu_analyze
from katrain.cron.models import KifuAlbumDB as Album, KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move
from katrain.web.api.v1.endpoints.kifu import KIFU_MODEL_SHA256, get_kifu_analysis
from katrain.web.core.models_db import KifuAlbum, KifuAnalysisJob, KifuAnalysisMove
from katrain.web.kifu.library import report_availability
from tests.web_ui.test_kifu_analysis import _db
from tests.test_kifu_batch_transfer import database


def resolve(sgf, evidence=None):
    from katrain.cron.kifu_parameters import resolve_parameters

    return resolve_parameters(sgf, evidence)


def evidence(sgf, rules="japanese", komi=6.5):
    # Synthetic test evidence, never a production assertion.
    return {
        "sgf_sha256": hashlib.sha256(sgf.encode()).hexdigest(),
        "rules": rules,
        "komi": komi,
        "verified": True,
        "scope": "exact_game",
        "reference_urls": ["https://example.test/fixture-game-rules"],
        "scope_description": "Synthetic fixture game only",
        "verified_by": "test-fixture",
        "verified_at": "2026-10-07T00:00:00+00:00",
    }


@pytest.mark.parametrize(
    "props,code",
    [
        ("KM[6.5]", "missing_rules"),
        ("RU[Japanese]", "missing_komi"),
        ("RU[unknown]KM[6.5]", "unsupported_rules"),
        ("RU[Japanese]KM[NaN]", "invalid_komi"),
        ("RU[Japanese]KM[Infinity]", "invalid_komi"),
        ("RU[Japanese]KM[]", "invalid_komi"),
        ("RU[Japanese]KM[6.5]KM[7.5]", "conflicting_metadata"),
        ("RU[Japanese][Chinese]KM[6.5]", "conflicting_metadata"),
        ("RU[Japanese]KM[6.5];B[aa]RU[Chinese]", "conflicting_metadata"),
    ],
)
def test_unresolved_metadata_never_uses_personal_defaults(props, code):
    from katrain.cron.kifu_parameters import ParameterError

    with pytest.raises(ParameterError) as error:
        resolve(f"(;SZ[19]{props};B[pd])")
    assert error.value.code == code


def test_supported_explicit_pair_and_zero_komi_preserve_raw_metadata():
    sgf = "(;SZ[19]RU[ Japanese ]KM[0];B[pd])"
    params = resolve(sgf)
    assert (params["rules"], params["komi"], params["verified"]) == ("japanese", 0.0, True)
    assert params["provenance"] == {"source": "sgf", "raw_rules": " Japanese ", "raw_komi": "0"}
    assert params["sgf_sha256"] == hashlib.sha256(sgf.encode()).hexdigest()
    # Existing personal/live policies still have their explicit default path.
    assert sgf_module.parse_game("(;SZ[19];B[pd])").rules == "chinese"


def test_exact_evidence_can_fill_missing_rules_but_cannot_hide_conflict():
    from katrain.cron.kifu_parameters import ParameterError, validate_parameters

    sgf = "(;SZ[19]KM[6.5];B[pd])"
    params = resolve(sgf, evidence(sgf))
    assert params["rules"] == "japanese" and validate_parameters(sgf, params) == params
    for override in (evidence(sgf, komi=7.5), evidence(sgf + " "), {**evidence(sgf), "verified": False}):
        with pytest.raises(ParameterError):
            resolve(sgf, override)
    explicit = sgf.replace("KM", "RU[Chinese]KM")
    with pytest.raises(ParameterError, match="conflict"):
        resolve(explicit, evidence(explicit))
    changed = copy.deepcopy(params)
    changed["komi"] = 0
    with pytest.raises(ParameterError):
        validate_parameters(sgf, changed)


@pytest.mark.parametrize("invalid", [{"scope": []}, {"reference_urls": ["https://["]}, {"note": float("nan")}])
def test_malformed_stored_evidence_is_unresolved(invalid):
    from katrain.cron.kifu_parameters import ParameterError

    sgf = "(;SZ[19]KM[6.5];B[pd])"
    with pytest.raises(ParameterError):
        resolve(sgf, {**evidence(sgf), **invalid})


@pytest.mark.asyncio
async def test_legacy_completed_job_is_unresolved_and_not_advertised():
    sgf = "(;SZ[19]KM[6.5];B[pd])"
    with _db() as db:
        album = KifuAlbum(id=1, player_black="B", player_white="W", source_path="a.sgf", sgf_content=sgf, move_count=1)
        db.add(album)
        db.flush()
        job = KifuAnalysisJob(
            album_id=1,
            sgf_sha256=hashlib.sha256(sgf.encode()).hexdigest(),
            model_sha256=KIFU_MODEL_SHA256,
            requested_visits=2000,
            status="completed",
            total_moves=1,
            analyzed_moves=1,
        )
        db.add(job)
        db.flush()
        db.add_all(KifuAnalysisMove(job_id=job.id, move_number=n, root_visits=2000) for n in (0, 1))
        db.commit()
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        payload = await get_kifu_analysis(request, 1, db)
        assert payload["status"] == "rules_unresolved"
        assert payload["moves"] == [] and payload["parameters_verified"] is False
        assert payload["parameter_error"]["code"] == "unverified_parameters"
        assert report_availability(db, [album], KIFU_MODEL_SHA256, 2000) == {1: False}


@pytest.mark.asyncio
async def test_worker_refuses_legacy_unverified_job_before_contacting_engine(database, monkeypatch):
    sgf = "(;SZ[19]KM[6.5];B[pd])"
    with Session(database) as db, db.begin():
        db.add(Album(id=1, sgf_content=sgf))
        db.add(
            Job(
                album_id=1,
                sgf_sha256=hashlib.sha256(sgf.encode()).hexdigest(),
                model_sha256=KIFU_MODEL_SHA256,
                requested_visits=2000,
                total_moves=1,
            )
        )
    monkeypatch.setattr(kifu_analyze, "SessionLocal", sessionmaker(bind=database))
    monkeypatch.setattr(kifu_analyze.config, "KATAGO_EXPECTED_MODEL_SHA256", KIFU_MODEL_SHA256)
    worker = kifu_analyze.KifuAnalyzeJob()
    worker.client.analyze = AsyncMock()
    await worker.run()
    worker.client.analyze.assert_not_called()
    with Session(database) as db:
        assert db.query(Job).one().status == "failed"
        assert "unverified_parameters" in db.query(Job).one().error_message
        assert db.query(Move).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "defect", ["legacy_position", "stale_position", "changed_during_request", "stale_during_request", "zero_komi"]
)
async def test_worker_binds_positions_and_inflight_response_to_parameters(database, monkeypatch, defect):
    from tests.test_kifu_batch_transfer import response

    sgf = "(;SZ[9]KM[0];B[aa])"
    params = resolve(sgf, evidence(sgf, komi=0))
    with Session(database) as db, db.begin():
        db.add(Album(id=1, sgf_content=sgf))
        job = Job(
            album_id=1,
            sgf_sha256=hashlib.sha256(sgf.encode()).hexdigest(),
            model_sha256=KIFU_MODEL_SHA256,
            requested_visits=2000,
            total_moves=1,
            analysis_parameters=params,
        )
        db.add(job)
        db.flush()
        if defect.endswith("position"):
            db.add(
                Move(
                    job_id=job.id,
                    move_number=0,
                    root_visits=2000,
                    parameter_sha256=None if defect == "legacy_position" else "0" * 64,
                )
            )
    monkeypatch.setattr(kifu_analyze, "SessionLocal", sessionmaker(bind=database))
    monkeypatch.setattr(kifu_analyze.config, "KATAGO_EXPECTED_MODEL_SHA256", KIFU_MODEL_SHA256)
    worker = kifu_analyze.KifuAnalyzeJob()

    async def analyze(**kwargs):
        assert (kwargs["rules"], kwargs["komi"]) == ("japanese", 0.0)
        if defect == "changed_during_request":
            with Session(database) as db, db.begin():
                db.query(Job).one().analysis_parameters = resolve(sgf, evidence(sgf, rules="chinese", komi=0))
        if defect == "stale_during_request":
            with Session(database) as db, db.begin():
                db.add(Move(job_id=db.query(Job).one().id, move_number=0, root_visits=2000, parameter_sha256="0" * 64))
        return response(kwargs["request_id"], kwargs["analyze_turns"][0])

    worker.client.analyze = AsyncMock(side_effect=analyze)
    await worker.run()
    with Session(database) as db:
        if defect.endswith("position"):
            worker.client.analyze.assert_not_called()
            assert db.query(Job).one().status == "failed"
        elif defect == "changed_during_request":
            assert db.query(Move).count() == 0
        elif defect == "stale_during_request":
            assert db.query(Job).one().status == "failed"
        else:
            assert db.query(Move).one().parameter_sha256 == params["parameter_sha256"]


def test_admission_rejects_unresolved_and_reset_cannot_reuse_old_positions(database):
    from scripts.backfill_kifu_analysis import admit_album

    sgf = "(;SZ[19]KM[6.5];B[pd])"
    with Session(database) as db:
        album = Album(id=1, sgf_content=sgf)
        db.add(album)
        db.commit()
        from katrain.cron.kifu_parameters import ParameterError

        with pytest.raises(ParameterError, match="missing_rules"):
            admit_album(db, album, KIFU_MODEL_SHA256, apply=True)
        assert db.query(Job).count() == 0
        proof = evidence(sgf)
        admit_album(db, album, KIFU_MODEL_SHA256, evidence=proof, apply=True)
        job = db.query(Job).one()
        db.add(
            Move(
                job_id=job.id,
                move_number=0,
                root_visits=2000,
                parameter_sha256=job.analysis_parameters["parameter_sha256"],
            )
        )
        db.commit()
        changed = evidence(sgf, rules="korean")
        with pytest.raises(ParameterError, match="parameter_mismatch"):
            admit_album(db, album, KIFU_MODEL_SHA256, evidence=changed, apply=True)
        admit_album(db, album, KIFU_MODEL_SHA256, evidence=changed, reanalyze=True)
        assert db.query(Move).count() == 1  # dry run
        admit_album(db, album, KIFU_MODEL_SHA256, evidence=changed, reanalyze=True, apply=True)
        assert db.query(Move).count() == 0
        assert db.query(Job).one().analysis_parameters["rules"] == "korean"
        assert db.get(Album, 1).sgf_content == sgf


def test_transfer_rejects_parameter_mismatch_even_with_recomputed_outer_checksum(database):
    from scripts import kifu_batch_transfer as batch, sync_kifu_analysis as sync
    from tests.test_kifu_batch_transfer import game, put_catalog, result_for
    from tests.test_sync_kifu_analysis import reports

    selected = game(1)
    put_catalog(database, [selected])
    result = result_for(selected)
    sessions = sessionmaker(bind=database)
    changed = copy.deepcopy(result)
    changed["analysis_parameters"]["komi"] = 6.5
    with pytest.raises(batch.BatchError, match="parameter"):
        batch.import_game(sessions, selected, changed, apply=True)
    artifact = reports([selected])
    artifact["games"][0]["analysis_parameters"] = {**selected["analysis_parameters"], "komi": 6.5}
    artifact["reports_sha256"] = batch.digest({k: v for k, v in artifact.items() if k != "reports_sha256"})
    with pytest.raises(batch.BatchError, match="parameter"):
        sync.validate_reports(artifact)
    changed = copy.deepcopy(result)
    changed["moves"][0]["parameter_sha256"] = "0" * 64
    with pytest.raises(batch.BatchError, match="parameter"):
        batch.import_game(sessions, selected, changed, apply=True)
    batch.import_game(sessions, selected, result, apply=True)
    with Session(database) as db, db.begin():
        db.query(Job).one().analysis_parameters = None
    with pytest.raises(batch.BatchError, match="parameter"):
        batch.import_game(sessions, selected, result, apply=True)
    with pytest.raises(batch.BatchError, match="parameter"):
        sync.export_reports(database, [1])


def test_parameter_migration_is_dry_idempotent_and_keeps_legacy_rows_unverified(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from scripts.migrate_kifu_parameters import migrate

    engine = create_engine("sqlite:///" + str(tmp_path / "old.sqlite3"))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE kifu_analysis_jobs (id INTEGER PRIMARY KEY, status TEXT)"))
        conn.execute(text("CREATE TABLE kifu_analysis_moves (id INTEGER PRIMARY KEY, job_id INTEGER)"))
        conn.execute(text("INSERT INTO kifu_analysis_jobs VALUES (1, 'completed')"))
        conn.execute(text("INSERT INTO kifu_analysis_moves VALUES (1, 1)"))
    assert len(migrate(engine)) == 2
    assert "analysis_parameters" not in {c["name"] for c in inspect(engine).get_columns("kifu_analysis_jobs")}
    assert len(migrate(engine, apply=True)) == 2
    assert migrate(engine, apply=True) == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status, analysis_parameters FROM kifu_analysis_jobs")).one() == (
            "completed",
            None,
        )
        assert conn.execute(text("SELECT job_id, parameter_sha256 FROM kifu_analysis_moves")).one() == (1, None)
    engine.dispose()


@pytest.mark.asyncio
async def test_api_withholds_all_moves_if_even_a_shallow_extra_row_has_stale_parameters():
    from tests.web_ui.test_kifu_analysis import SGF

    params = resolve(SGF)
    with _db() as db:
        db.add(KifuAlbum(id=1, player_black="B", player_white="W", source_path="a.sgf", sgf_content=SGF, move_count=1))
        db.flush()
        job = KifuAnalysisJob(
            album_id=1,
            sgf_sha256=params["sgf_sha256"],
            model_sha256=KIFU_MODEL_SHA256,
            requested_visits=2000,
            status="completed",
            total_moves=1,
            analyzed_moves=1,
            analysis_parameters=params,
        )
        db.add(job)
        db.flush()
        db.add_all(
            KifuAnalysisMove(
                job_id=job.id, move_number=n, root_visits=2000, parameter_sha256=params["parameter_sha256"]
            )
            for n in (0, 1)
        )
        db.add(KifuAnalysisMove(job_id=job.id, move_number=2, root_visits=1, parameter_sha256="0" * 64))
        db.commit()
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        payload = await get_kifu_analysis(request, 1, db)
        assert payload["status"] == "rules_unresolved" and payload["moves"] == []
        assert payload["parameter_error"]["code"] == "parameter_mismatch"


def test_explicit_reanalysis_manifest_preserves_evidence_and_requires_resolved_selection(database, tmp_path):
    from scripts import kifu_batch_transfer as batch
    from tests.test_kifu_batch_transfer import game, put_catalog

    selected = game(1)
    selected["sgf_content"] = selected["sgf_content"].replace("RU[Chinese]", "")
    selected["sgf_sha256"] = batch.sgf_hash(selected["sgf_content"])
    put_catalog(database, [selected])
    with pytest.raises(batch.BatchError, match="missing_rules"):
        batch.export_manifest(database, [1])
    proof = evidence(selected["sgf_content"], komi=7.5)
    manifest = batch.export_manifest(database, [1], {selected["sgf_sha256"]: proof})
    assert len(batch.validate_manifest(manifest)) == 1
    batch.init_workers(manifest, tmp_path / "workers")
    engine = batch.sqlite_engine(tmp_path / "workers" / "gpu0.sqlite3")
    with Session(engine) as db:
        job = db.query(Job).one()
        assert job.analysis_parameters == manifest["games"][0]["analysis_parameters"]
        assert job.analysis_parameters["provenance"]["evidence"] == proof
        assert db.query(Album).one().sgf_content == selected["sgf_content"]
    engine.dispose()
