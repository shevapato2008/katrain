"""Bounded, fixed-arrival API measurements must not hide slow/error samples."""

import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

import httpx
import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/kifu_search_load.py"


@pytest.fixture
def load():
    spec = importlib.util.spec_from_file_location("kifu_search_load", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(identifier="case-1", **params):
    return {
        "id": identifier,
        "category": "unique_name",
        "params": {"q": "public name", **params},
        "expected": {"total": 0, "ordered_ids": [], "first_sgf_sha256": None},
    }


def empty_body(**changes):
    return {"total": 0, "items": [], "preview": None, "page": 1, "page_size": 20, **changes}


async def sent(request):
    await request.extensions["trace"]("http11.send_request_headers.complete", {})


def test_nearest_rank_percentiles_include_the_slowest_observation(load):
    assert load.percentiles(range(1, 21)) == {"count": 20, "p50": 10, "p95": 19, "p99": 20, "max": 20}
    assert load.percentiles([]) == {"count": 0, "p50": None, "p95": None, "p99": None, "max": None}


def test_semantics_keep_empty_results_and_compare_exact_order_hash_and_public_fields(load):
    assert load.semantic_errors(empty_body(), case()) == []
    sgf = "(;PB[Private preview name];B[aa])"
    frozen = case(page=2)
    frozen["expected"] = {
        "total": 25,
        "ordered_ids": [7, 4],
        "first_sgf_sha256": hashlib.sha256(sgf.encode()).hexdigest(),
    }
    body = empty_body(total=25, page=2, items=[{"id": 7}, {"id": 4}], preview={"id": 7, "sgf_content": sgf})
    assert load.semantic_errors(body, frozen) == []
    assert "ordered_ids" in load.semantic_errors({**body, "items": [{"id": 4}, {"id": 7}]}, frozen)
    assert "total" in load.semantic_errors({**body, "total": 24}, frozen)
    assert "first_sgf_sha256" in load.semantic_errors({**body, "preview": {"id": 7, "sgf_content": "bad"}}, frozen)
    frozen["expected"]["public_response"] = body
    assert "public_response" in load.semantic_errors({**body, "extra": True}, frozen)
    assert load.semantic_errors({"total": 0}, case())


def test_casefile_is_frozen_order_and_rejects_unexpected_params(load):
    cases = [case(f"case-{i}") for i in range(12)]
    assert load.validate_cases({"version": 1, "cases": cases}) == cases
    with pytest.raises(ValueError, match="params"):
        load.validate_cases({"version": 1, "cases": [case(token="secret")]})
    with pytest.raises(ValueError, match="expected"):
        load.validate_cases({"version": 1, "cases": [{**case(), "expected": {"total": 0}}]})


def test_frozen_five_language_rotation_uses_the_public_korean_code(load):
    cases = [case(f"lang-{lang}", lang=lang) for lang in ("cn", "tw", "en", "jp", "ko")]
    assert load.validate_cases({"version": 1, "cases": cases}) == cases


def test_profiles_have_finite_fixed_arrival_counts_and_ramp_is_separate(load):
    high = load.make_plan("high")
    assert high["window_s"] == 30 and len(high["offsets_s"]) == 3000
    assert high["offsets_s"][-1] == pytest.approx(29.99)
    low = load.make_plan("low")
    assert low["window_s"] == 120 and len(low["offsets_s"]) == 120
    ramp = load.make_plan("ramp")
    assert ramp["window_s"] == 10 and len(ramp["offsets_s"]) == 300
    with pytest.raises(ValueError):
        load.make_plan("custom", rate=3, duration=0.5)


@pytest.mark.asyncio
async def test_every_http_json_semantic_and_timeout_error_remains_in_statistics(load):
    records = []
    bodies = [
        httpx.Response(200, json=empty_body()),
        httpx.Response(503, json={"detail": "unavailable"}),
        httpx.Response(200, content=b"not JSON"),
        httpx.Response(200, json=empty_body(total=1)),
    ]
    requests = []

    async def respond(request):
        await sent(request)
        index = len(requests)
        requests.append(request)
        if index == 4:
            raise httpx.ReadTimeout("must never log URL/name/secret")
        return bodies[index]

    summary = await load.run_load(
        "http://test",
        [case()],
        load.make_plan("custom", rate=100, count=5),
        emit=records.append,
        transport=httpx.MockTransport(respond),
    )
    samples = [row for row in records if row["type"] == "sample"]
    assert len(samples) == 5
    assert summary["scheduled"] == 5 and summary["sent"] == 5
    assert summary["errors"] == 4 and summary["error_rate"] == 0.8
    assert summary["complete_bodies"] == 4 and summary["complete_json"] == 3
    assert summary["latency_ms"]["client_wall"]["count"] == 5
    assert summary["categories"]["unique_name"]["scheduled"] == 5
    assert summary["gates"]["ingress"] == "not_observed"
    assert records[-1] == summary
    log = json.dumps(records)
    assert "public name" not in log and "must never log" not in log and "unavailable" not in log


@pytest.mark.asyncio
async def test_fixed_scheduler_queues_without_dropping_and_caps_inflight(load):
    records = []
    active = 0
    maximum = 0

    async def slow(request):
        nonlocal active, maximum
        await sent(request)
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(0.08)
            return httpx.Response(200, json=empty_body())
        finally:
            active -= 1

    summary = await load.run_load(
        "http://test",
        [case("first"), case("second")],
        load.make_plan("custom", rate=200, count=8),
        max_inflight=1,
        drain_s=0.07,
        emit=records.append,
        transport=httpx.MockTransport(slow),
    )
    samples = sorted((r for r in records if r["type"] == "sample"), key=lambda r: r["sequence"])
    assert [s["case_id"] for s in samples] == ["first", "second"] * 4
    assert maximum == 1 and summary["max_inflight_observed"] == 1
    assert summary["scheduled"] == 8 and summary["errors"] >= 6
    assert summary["sent_within_window"] == 1
    assert summary["not_sent"] >= 6
    assert all(s["client_wall_ms"] is not None for s in samples)
    assert samples[1]["generator_queue_ms"] >= 50
    assert samples[1]["dispatch_queue_ms"] >= 50
    assert any("not_sent" in s["errors"] for s in samples)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,error", [(httpx.ReadTimeout, "timeout"), (RuntimeError, "client_error")])
async def test_partial_body_failure_retains_received_headers_and_bytes(load, failure, error):
    records = []

    class BrokenBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"items":'
            raise failure("private response must not appear in logs")

    async def respond(request):
        await sent(request)
        return httpx.Response(200, stream=BrokenBody(), headers={"server-timing": "kifu_handler;dur=2.5"})

    result = await load.run_load(
        "http://test",
        [case()],
        load.make_plan("custom", rate=100, count=1),
        emit=records.append,
        transport=httpx.MockTransport(respond),
    )
    sample = next(row for row in records if row["type"] == "sample")
    assert result["errors"] == 1 and result["complete_bodies"] == 0
    assert sample["status"] == 200 and sample["response_bytes"] == 9
    assert sample["server_timing_ms"] == {"kifu_handler": 2.5}
    assert sample["errors"] == [error]


def synthetic_high():
    run = {
        "type": "run",
        "profile": "high",
        "window_s": 30,
        "started_unix_s": 1000,
        "scheduled_count": 3000,
        "max_inflight": 32,
        "max_inflight_observed": 4,
        "elapsed_s": 31,
    }
    samples = [
        {
            "type": "sample",
            "sequence": i,
            "request_id": f"{i:032x}",
            "category": "player_id",
            "sent": True,
            "sent_offset_ms": i * 10,
            "complete_body": True,
            "json_valid": True,
            "errors": [],
            "semantic_errors": [],
            "response_bytes": 12,
            "status": 200,
            "client_wall_ms": 250,
            "http_ms": 240,
            "generator_queue_ms": 1,
            "dispatch_queue_ms": 10,
        }
        for i in range(3000)
    ]
    metrics = [
        {
            "event": "kifu_http_timing",
            "request_id": s["request_id"],
            "ingress_unix_s": 1000 + i * 0.01,
            "asgi_total_ms": 190,
            "status": 200,
            "bytes": 12,
        }
        for i, s in enumerate(samples)
    ]
    return run, samples, metrics


def test_gate_requires_server_ingress_and_asgi_last_body_not_client_or_handler_time(load):
    run, samples, metrics = synthetic_high()
    summary = load.summarize(run, samples)
    assert summary["sent_qps_within_window"] == 100
    assert summary["gates"]["overall"] == "not_observed"
    assert summary["gates"]["ingress"] == "not_observed"
    assert summary["latency_ms"]["asgi_total"]["count"] == 0
    summary = load.summarize(run, samples, metrics)
    assert summary["gates"]["overall"] == "pass"
    assert summary["latency_ms"]["client_wall"]["p95"] == 250
    assert summary["latency_ms"]["asgi_total"]["p95"] == 190
    for metric in metrics[2969:]:
        metric["ingress_unix_s"] = 1030.001
    summary = load.summarize(run, samples, metrics)
    assert summary["ingress_within_window"] == 2969
    assert summary["gates"]["ingress"] == "fail"
    assert summary["gates"]["overall"] == "fail"


def test_drain_sent_requests_do_not_inflate_window_achieved_qps(load):
    run, samples, metrics = synthetic_high()
    for sample in samples[2969:]:
        sample["sent_offset_ms"] = 30001
    summary = load.summarize(run, samples, metrics)
    assert summary["sent"] == 3000 and summary["sent_within_window"] == 2969
    assert summary["gates"]["sent"] == "fail"
    samples[0]["errors"] = ["timeout"]
    summary = load.summarize(run, samples, metrics)
    assert summary["errors"] == 1 and summary["gates"]["errors"] == "fail"


def test_offline_metrics_ignore_unrelated_events_and_reject_duplicate_request_ids(load, tmp_path):
    path = tmp_path / "server.jsonl"
    metric = {
        "event": "kifu_http_timing",
        "request_id": "a" * 32,
        "ingress_unix_s": 1,
        "asgi_total_ms": 2,
        "status": 200,
        "bytes": 3,
    }
    path.write_text(json.dumps({"event": "other"}) + "\n2026-10-28 [INFO] " + json.dumps(metric) + "\n")
    assert load.read_server_metrics(path) == [metric]
    path.write_text(json.dumps(metric) + "\n" + json.dumps(metric) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load.read_server_metrics(path)


def test_missing_offline_samples_are_errors_not_discarded(load):
    run, samples, _ = synthetic_high()
    result = load.summarize(run, samples[:-1])
    assert result["scheduled"] == 3000 and result["missing_samples"] == 1
    assert result["errors"] == 1 and result["not_sent"] == 1
    assert result["gates"]["overall"] == "fail"


def test_cli_requires_observed_server_gate_and_never_overwrites_output(load, tmp_path):
    run, samples, metrics = synthetic_high()
    client = tmp_path / "client.jsonl"
    server = tmp_path / "server.jsonl"
    client.write_text("\n".join(json.dumps(row) for row in [run, *samples]))
    server.write_text("\n".join(json.dumps(row) for row in metrics))
    incomplete = tmp_path / "incomplete.jsonl"
    assert load.main(["--summarize", str(client), "--output", str(incomplete)]) == 3
    complete = tmp_path / "complete.jsonl"
    assert load.main(["--summarize", str(client), "--server-metrics", str(server), "--output", str(complete)]) == 0
    assert json.loads(complete.read_text())["gates"]["overall"] == "pass"
    previous = complete.read_bytes()
    assert load.main(["--summarize", str(client), "--output", str(complete)]) == 2
    assert complete.read_bytes() == previous
