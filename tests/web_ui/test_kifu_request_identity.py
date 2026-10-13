"""Late engine responses must not acquire a retry/reset's parameter identity."""

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from katrain.cron.jobs import kifu_analyze
from katrain.cron.models import KifuAlbumDB as Album, KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move
from scripts.backfill_kifu_analysis import admit_album
from tests.test_kifu_batch_transfer import database, response
from tests.web_ui.test_kifu_parameters import evidence
from tests.web_ui.test_cron_katago_contract import MODEL_SHA


SGF = "(;SZ[9]KM[6.5];B[aa])"


def prepare(database, monkeypatch):
    with Session(database) as db:
        album = Album(id=1, sgf_content=SGF)
        db.add(album)
        db.commit()
        admit_album(db, album, MODEL_SHA, evidence=evidence(SGF), apply=True)
    monkeypatch.setattr(kifu_analyze, "SessionLocal", sessionmaker(bind=database))
    monkeypatch.setattr(kifu_analyze.config, "KATAGO_EXPECTED_MODEL_SHA256", MODEL_SHA)


def reset(database):
    with Session(database) as db:
        admit_album(
            db, db.get(Album, 1), MODEL_SHA, evidence=evidence(SGF, rules="chinese"), reanalyze=True, apply=True
        )


def use_transport(monkeypatch, handler):
    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("katrain.cron.clients.katago.httpx.AsyncClient", Client)


@pytest.mark.asyncio
@pytest.mark.parametrize("transition", ["retry", "reset"])
async def test_real_wrapper_ignores_timed_out_response_after_retry_or_reset(database, monkeypatch, transition):
    prepare(database, monkeypatch)
    path = Path(__file__).resolve().parents[2] / "deploy/katago-cron/realtime_api/katago_wrapper.py"
    spec = importlib.util.spec_from_file_location("kifu_identity_wrapper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    wrapper = module.KataGoWrapper("unused", "unused", "unused")
    stdout = asyncio.StreamReader()
    requests = []

    class EngineInput:
        def write(self, data):
            requests.append(json.loads(data))
            if len(requests) == 2:
                # The first request has timed out but the engine finishes it
                # before the new search. Use the actual wrapper's ID routing.
                old = response(requests[0]["id"], 0)
                old["rootInfo"]["scoreLead"] = -12.5
                current = response(requests[1]["id"], 0)
                current["rootInfo"]["scoreLead"] = 2.5
                stdout.feed_data((json.dumps(old) + "\n" + json.dumps(current) + "\n").encode())

        async def drain(self):
            pass

    wrapper.process = SimpleNamespace(returncode=None, stdin=EngineInput(), stdout=stdout)
    wrapper.running = True
    reader = asyncio.create_task(wrapper._read_loop())

    async def handler(request):
        payload = json.loads(request.content)
        result = await wrapper.query(payload, timeout=0.01 if not requests else 1)
        return httpx.Response(200, json=result)

    use_transport(monkeypatch, handler)
    try:
        await kifu_analyze.KifuAnalyzeJob().run()
        with Session(database) as db:
            assert db.query(Move).count() == 0
            assert db.query(Job).one().status == "pending"
        assert not wrapper.pending_requests
        if transition == "reset":
            reset(database)
        # A new worker instance also exercises process-restart independence.
        await kifu_analyze.KifuAnalyzeJob().run()
        with Session(database) as db:
            row, job = db.query(Move).one(), db.query(Job).one()
            assert row.score_lead == 2.5, "A late response was relabelled as the new request"
            assert row.parameter_sha256 == job.analysis_parameters["parameter_sha256"]
            assert job.id == 1 and row.move_number == 0
        assert len(requests) == 2 and requests[0]["id"] != requests[1]["id"]
        assert [r["rules"] for r in requests] == ["japanese", "chinese" if transition == "reset" else "japanese"]
        assert not wrapper.pending_requests
    finally:
        wrapper.running = False
        stdout.feed_eof()
        await reader


@pytest.mark.asyncio
async def test_worker_rejects_old_id_returned_by_http_and_retries_with_fresh_id(database, monkeypatch):
    prepare(database, monkeypatch)
    requests = []

    async def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            raise httpx.ReadTimeout("synthetic timed-out request", request=request)
        echoed_id = requests[0]["id"] if len(requests) == 2 else requests[-1]["id"]
        return httpx.Response(200, json=response(echoed_id, 0))

    use_transport(monkeypatch, handler)
    await kifu_analyze.KifuAnalyzeJob().run()
    reset(database)
    await kifu_analyze.KifuAnalyzeJob().run()
    with Session(database) as db:
        assert db.query(Move).count() == 0
        assert "different request" in db.query(Job).one().error_message
    await kifu_analyze.KifuAnalyzeJob().run()
    with Session(database) as db:
        assert db.query(Move).one().parameter_sha256 == db.query(Job).one().analysis_parameters["parameter_sha256"]
    assert len({r["id"] for r in requests}) == 3
