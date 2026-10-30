#!/usr/bin/env python3
"""Finite fixed-arrival measurements for GET /api/v1/kifu/albums only.

Casefile contract (JSON, preserved in file order, then repeated):
  {"version":1,"cases":[{"id":"opaque-1","category":"unique_name",
    "params":{"q":"public query","lang":"cn","page":1,"page_size":20},
    "expected":{"total":0,"ordered_ids":[],"first_sgf_sha256":null}}]}
Use player_id instead of q for identity cases. Optional expected.public_response
compares the entire public JSON object, including card fields and preview.
Freeze real cases outside this script; keep compatibility cases in a separate run.

Examples (these commands generate traffic only when explicitly invoked):
  python scripts/kifu_search_load.py --base-url http://127.0.0.1:8001 \
      --casefile frozen.json --profile low --output low.jsonl
  python scripts/kifu_search_load.py --base-url http://127.0.0.1:8001 \
      --casefile frozen.json --profile ramp --output ramp.jsonl
  python scripts/kifu_search_load.py --summarize high.jsonl \
      --server-metrics server.jsonl --output correlated.jsonl

Server metric contract: event="kifu_http_timing", request_id (32 lowercase hex),
ingress_unix_s (scope entry), asgi_total_ms (through final body send), status,
bytes. JSONL or logger-prefixed JSON lines are accepted. Correlation assumes the
client and server share a clock: run on the same TEST host. Ingress means ASGI
entry, not an unobserved proxy/socket accept queue. Handler Server-Timing stays
separate and never substitutes for final-body timing. No server evidence means
not_observed, never a performance pass. Percentiles use nearest rank, ceil(p*N).

Timing logs contain case IDs and numeric measurements, never query text/SGFs.
Client wall includes scheduler/worker/connection queue and JSON validation;
http_ms runs from the HTTP call through final body/context close and excludes
client JSON/semantic validation; generator_queue_ms ends at worker dispatch,
dispatch_queue_ms ends when httpcore confirms request headers have been sent.
The drain (at most 2s) never contributes to achieved QPS in the offered window.
Exit codes: 0=observed gate pass, 1=failed gate, 2=invalid input/output,
3=measurements saved but performance gate not observed (including ramp/custom).
"""

import argparse
import asyncio
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import uuid

import httpx


PATH = "/api/v1/kifu/albums"
OPAQUE_ID = re.compile(r"[A-Za-z0-9_.:-]{1,80}\Z")
REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z")


def percentiles(values):
    """Nearest-rank percentiles; retain failures rather than filtering on status."""
    values = sorted(values)
    result = {"count": len(values)}
    for key, fraction in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99), ("max", 1)):
        result[key] = values[math.ceil(len(values) * fraction) - 1] if values else None
    return result


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def validate_cases(document):
    if not isinstance(document, dict) or document.get("version") != 1 or not document.get("cases"):
        raise ValueError("casefile requires version=1 and nonempty cases")
    seen = set()
    for case in document["cases"]:
        if not isinstance(case, dict) or any(
            not isinstance(case.get(key), str) or not OPAQUE_ID.fullmatch(case[key]) for key in ("id", "category")
        ):
            raise ValueError("case id/category must be opaque ASCII identifiers")
        if case["id"] in seen:
            raise ValueError("duplicate case id")
        seen.add(case["id"])
        params = case.get("params")
        if not isinstance(params, dict) or set(params) - {"q", "player_id", "lang", "page", "page_size"}:
            raise ValueError("case params contain unsupported keys")
        if (
            ("q" in params and not isinstance(params["q"], str))
            or ("player_id" in params and not _integer(params["player_id"], 1))
            or ("q" in params and "player_id" in params)
        ):
            raise ValueError("case params require either q or positive player_id")
        if (
            params.get("lang", "cn") not in {"cn", "tw", "en", "jp", "ko"}
            or any(not _integer(params.get(key, default), 1) for key, default in (("page", 1), ("page_size", 20)))
            or params.get("page_size", 20) > 100
        ):
            raise ValueError("case params have invalid language/page/page_size")
        expected = case.get("expected")
        if not isinstance(expected, dict) or not {"total", "ordered_ids", "first_sgf_sha256"} <= expected.keys():
            raise ValueError("case expected requires total, ordered_ids, first_sgf_sha256")
        ids = expected["ordered_ids"]
        digest = expected["first_sgf_sha256"]
        if not _integer(expected["total"]) or not isinstance(ids, list) or any(not _integer(i, 1) for i in ids):
            raise ValueError("case expected total/ordered_ids are invalid")
        if len(ids) > params.get("page_size", 20) or expected["total"] < len(ids):
            raise ValueError("case expected ordered_ids exceed page/total")
        if (ids and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest))) or (
            not ids and digest is not None
        ):
            raise ValueError("case expected first_sgf_sha256 must match page presence")
        if "public_response" in expected and not isinstance(expected["public_response"], dict):
            raise ValueError("case expected public_response must be an object")
    return document["cases"]


def semantic_errors(body, case):
    """Return field names only: never include an actual/expected name or SGF."""
    if not isinstance(body, dict) or not {"items", "total", "page", "page_size", "preview"} <= body.keys():
        return ["response_shape"]
    expected, params = case["expected"], case["params"]
    errors = []
    if not _integer(body["total"]) or body["total"] != expected["total"]:
        errors.append("total")
    items = body["items"]
    if not isinstance(items, list) or any(
        not isinstance(item, dict) or not _integer(item.get("id"), 1) for item in items
    ):
        errors.append("items_shape")
        ids = None
    else:
        ids = [item["id"] for item in items]
    if ids != expected["ordered_ids"]:
        errors.append("ordered_ids")
    for key, default in (("page", 1), ("page_size", 20)):
        if not _integer(body[key], 1) or body[key] != params.get(key, default):
            errors.append(key)
    preview, digest = body["preview"], None
    if preview is not None:
        if not isinstance(preview, dict) or not isinstance(preview.get("sgf_content"), str):
            errors.append("preview_shape")
        else:
            digest = hashlib.sha256(preview["sgf_content"].encode("utf-8")).hexdigest()
            if not ids or preview.get("id") != ids[0]:
                errors.append("preview_id")
    elif ids:
        errors.append("preview_shape")
    if digest != expected["first_sgf_sha256"]:
        errors.append("first_sgf_sha256")
    if "public_response" in expected and json.dumps(body, sort_keys=True) != json.dumps(
        expected["public_response"], sort_keys=True
    ):
        errors.append("public_response")
    return errors


def make_plan(profile, *, rate=None, duration=None, count=None):
    if profile in {"low", "high", "ramp"}:
        if any(value is not None for value in (rate, duration, count)):
            raise ValueError("fixed profiles do not accept rate/duration/count overrides")
        if profile == "low":
            rate, duration, count = 1, 120, 120
        elif profile == "high":
            rate, duration, count = 100, 30, 3000
        else:
            return {
                "profile": profile,
                "window_s": 10,
                "offsets_s": [i / 10 for i in range(50)] + [5 + i / 50 for i in range(250)],
            }
    elif profile != "custom":
        raise ValueError("unknown profile")
    if profile == "custom" and (
        rate is None or not math.isfinite(rate) or rate <= 0 or (duration is None) == (count is None)
    ):
        raise ValueError("custom requires a positive rate and exactly one of duration/count")
    if duration is not None:
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be positive and finite")
        offered = rate * duration
        if not math.isclose(offered, round(offered), abs_tol=1e-9):
            raise ValueError("rate * duration must be an exact finite request count")
        count = round(offered)
    if not _integer(count, 1) or count > 100000:
        raise ValueError("request count must be within 1..100000")
    return {"profile": profile, "window_s": count / rate, "offsets_s": [i / rate for i in range(count)]}


def _server_timing(header):
    # Keep numeric durations only; arbitrary descriptions can contain user data.
    return {
        name: float(duration)
        for name, duration in re.findall(
            r"(?:^|,)\s*([A-Za-z][A-Za-z0-9_-]{0,60});\s*dur=([0-9]+(?:\.[0-9]+)?)", header or ""
        )
    }


def read_server_metrics(path):
    metrics, seen = [], set()
    for line in Path(path).read_text().splitlines():
        if "kifu_http_timing" not in line:
            continue
        try:
            row = json.loads(line[line.index("{") :])
        except (ValueError, json.JSONDecodeError):
            raise ValueError("invalid kifu_http_timing JSON") from None
        if row.get("event") != "kifu_http_timing":
            continue
        if not isinstance(row.get("request_id"), str) or not REQUEST_ID.fullmatch(row["request_id"]):
            raise ValueError("invalid server request_id")
        if row["request_id"] in seen:
            raise ValueError("duplicate server request_id")
        for key in ("ingress_unix_s", "asgi_total_ms"):
            if type(row.get(key)) not in (int, float) or not math.isfinite(row[key]) or row[key] < 0:
                raise ValueError("invalid server timing number")
        if not _integer(row.get("status"), 100) or not _integer(row.get("bytes")):
            raise ValueError("invalid server status/bytes")
        seen.add(row["request_id"])
        metrics.append(row)
    return metrics


def summarize(run, samples, server_metrics=None):
    count = run.get("scheduled_count")
    if not _integer(count, 1):
        raise ValueError("invalid client sample count")
    sequences, request_ids = set(), set()
    for row in samples:
        if not isinstance(row, dict):
            raise ValueError("invalid client sample")
        sequence, request_id = row.get("sequence"), row.get("request_id")
        if not _integer(sequence) or sequence >= count or sequence in sequences:
            raise ValueError("invalid or duplicate client sample sequence")
        if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id) or request_id in request_ids:
            raise ValueError("invalid or duplicate client sample request_id")
        sequences.add(sequence)
        request_ids.add(request_id)
    metrics = {row["request_id"]: row for row in (server_metrics or [])}
    window_ms, start = run["window_s"] * 1000, run["started_unix_s"]

    def aggregate(rows):
        correlated = [metrics[row["request_id"]] for row in rows if row["request_id"] in metrics]
        errors = sum(bool(row["errors"]) for row in rows)
        sent_window = sum(
            row.get("sent_offset_ms") is not None and 0 <= row["sent_offset_ms"] < window_ms for row in rows
        )
        ingress_window = sum(start <= metric["ingress_unix_s"] < start + run["window_s"] for metric in correlated)
        latency = {
            name: percentiles(row[field] for row in rows if row.get(field) is not None)
            for name, field in (
                ("client_wall", "client_wall_ms"),
                ("http", "http_ms"),
                ("generator_queue", "generator_queue_ms"),
                ("dispatch_queue", "dispatch_queue_ms"),
            )
        }
        latency["asgi_total"] = percentiles(metric["asgi_total_ms"] for metric in correlated)
        return {
            "scheduled": len(rows),
            "sent": sum(row["sent"] for row in rows),
            "sent_within_window": sent_window,
            "sent_qps_within_window": sent_window / run["window_s"],
            "ingress_within_window": ingress_window if correlated else None,
            "ingress_qps_within_window": ingress_window / run["window_s"] if correlated else None,
            "not_sent": sum(not row["sent"] for row in rows),
            "errors": errors,
            "error_rate": errors / len(rows) if rows else None,
            "error_reasons": dict(Counter(error for row in rows for error in row["errors"])),
            "semantic_differences": sum(bool(row.get("semantic_errors")) for row in rows),
            "complete_bodies": sum(row["complete_body"] for row in rows),
            "complete_json": sum(row["json_valid"] for row in rows),
            "response_bytes_decoded": sum(row.get("response_bytes", 0) for row in rows),
            "statuses": dict(Counter(str(row["status"]) for row in rows)),
            "latency_ms": latency,
            "server_correlated": len(correlated),
            "http_over_200ms": sum(row.get("http_ms") is not None and row["http_ms"] > 200 for row in rows),
        }

    result = {"type": "summary", **aggregate(samples)}
    missing = max(0, run["scheduled_count"] - len(samples))
    result.update(
        {
            "scheduled": run["scheduled_count"],
            "missing_samples": missing,
            "offered_qps": run["scheduled_count"] / run["window_s"],
            "max_inflight_observed": run.get("max_inflight_observed"),
            "elapsed_s": run.get("elapsed_s"),
            "percentile_method": "nearest_rank",
            "categories": {
                category: aggregate([row for row in samples if row["category"] == category])
                for category in sorted({row["category"] for row in samples})
            },
            "run": run,
        }
    )
    result["errors"] += missing
    result["not_sent"] += missing
    result["error_rate"] = result["errors"] / result["scheduled"]
    target_ms = {"low": 20, "high": 200}.get(run["profile"])
    minimum_sent = 2970 if run["profile"] == "high" else run["scheduled_count"]
    complete_server = result["server_correlated"] == run["scheduled_count"]
    gates = {
        "errors": "pass" if result["errors"] == 0 else "fail",
        "sent": "pass" if result["sent_within_window"] >= minimum_sent else "fail",
        "ingress": (
            ("pass" if result["ingress_within_window"] >= minimum_sent else "fail")
            if result["ingress_within_window"] is not None
            else "not_observed"
        ),
        "asgi_p95": (
            ("pass" if result["latency_ms"]["asgi_total"]["p95"] <= target_ms else "fail")
            if complete_server and target_ms is not None
            else "not_observed"
        ),
    }
    high = run["profile"] == "high"
    http = result["latency_ms"]["http"]
    gates["complete_http"] = "pass" if (
        result["complete_bodies"] == count and result["complete_json"] == count
        and http["count"] == count and result["semantic_differences"] == 0
        and result["statuses"] == {"200": count}
    ) else "fail"
    gates["http_max"] = (
        ("pass" if http["max"] is not None and http["max"] <= 200 else "fail")
        if high else "not_observed"
    )
    gates["fixed_arrival"] = (
        ("pass" if count == 3000 and run["window_s"] == 30
         and 0 < (run.get("max_inflight_observed") or 0) <= 32
         and run.get("max_inflight", 32) <= 32
         and run.get("elapsed_s") is not None and run["elapsed_s"] <= 32 else "fail")
        if high else "not_observed"
    )
    # ASGI p95 and low-profile 20ms are diagnostics. Acceptance uses every
    # complete HTTP response and requires the actual 100QPS arrival window.
    required = [gates[key] for key in ("errors", "sent", "ingress", "complete_http")]
    if high:
        required += [gates["http_max"], gates["fixed_arrival"]]
    gates["overall"] = (
        "fail" if "fail" in required
        else "pass" if high and "not_observed" not in required
        else "not_observed"
    )
    result["gates"] = gates
    return result


async def run_load(
    base_url,
    cases,
    plan,
    *,
    max_inflight=32,
    timeout_s=5,
    drain_s=2,
    emit=lambda row: None,
    transport=None,
    casefile_sha256=None,
):
    origin = urlsplit(base_url)
    if (
        origin.scheme not in {"http", "https"}
        or not origin.hostname
        or origin.username
        or origin.password
        or (origin.path not in {"", "/"} or origin.query or origin.fragment)
    ):
        raise ValueError("base URL must be an HTTP(S) origin without credentials/path/query")
    if not _integer(max_inflight, 1) or max_inflight > 32 or not 0 <= drain_s <= 2 or not 0 < timeout_s < math.inf:
        raise ValueError("max_inflight must be 1..32; drain 0..2s; timeout positive and finite")
    validate_cases({"version": 1, "cases": cases})
    loop = asyncio.get_running_loop()
    start = loop.time()
    run = {
        "type": "run",
        "version": 1,
        "profile": plan["profile"],
        "run_id": uuid.uuid4().hex,
        "started_unix_s": time.time(),
        "window_s": plan["window_s"],
        "scheduled_count": len(plan["offsets_s"]),
        "max_inflight": max_inflight,
        "max_connections": max_inflight,
        "timeout_s": timeout_s,
        "drain_s": drain_s,
        "casefile_sha256": casefile_sha256,
        "connections_opened": 0,
        "max_inflight_observed": 0,
        "ingress_clock_requirement": "same host clock",
        "response_bytes_basis": "decoded body",
    }
    samples = [
        {
            "type": "sample",
            "sequence": i,
            "case_id": cases[i % len(cases)]["id"],
            "category": cases[i % len(cases)]["category"],
            "request_id": uuid.uuid4().hex,
            "scheduled_offset_ms": offset * 1000,
            "sent_offset_ms": None,
            "sent": False,
            "complete_body": False,
            "json_valid": False,
            "status": None,
            "response_bytes": 0,
            "server_timing_ms": {},
            "errors": [],
            "semantic_errors": [],
            "client_wall_ms": None,
            "http_ms": None,
            "generator_queue_ms": None,
            "dispatch_queue_ms": None,
        }
        for i, offset in enumerate(plan["offsets_s"])
    ]
    queue = asyncio.Queue(maxsize=len(samples))
    active = 0

    def finish(sample):
        if not sample["sent"]:
            sample["errors"].append("not_sent")
        sample["client_wall_ms"] = max(0, (loop.time() - start) * 1000 - sample["scheduled_offset_ms"])
        emit(sample.copy())

    async def worker(client):
        nonlocal active
        while True:
            index = await queue.get()
            sample = samples[index]
            sample["generator_queue_ms"] = (loop.time() - start) * 1000 - sample["scheduled_offset_ms"]
            http_start = loop.time()
            active += 1
            run["max_inflight_observed"] = max(active, run["max_inflight_observed"])

            async def trace(event, info):
                if event == "connection.connect_tcp.complete":
                    run["connections_opened"] += 1
                elif event in {"http11.send_request_headers.complete", "http2.send_request_headers.complete"}:
                    sample["sent"] = True
                    sample["sent_offset_ms"] = (loop.time() - start) * 1000
                    sample["dispatch_queue_ms"] = sample["sent_offset_ms"] - sample["scheduled_offset_ms"]

            try:
                async with asyncio.timeout(timeout_s):
                    async with client.stream(
                        "GET",
                        PATH,
                        params=cases[index % len(cases)]["params"],
                        headers={"x-kifu-request-id": sample["request_id"]},
                        extensions={"trace": trace},
                    ) as response:
                        sample["sent"] = True  # A response proves send, but not its unobserved timestamp.
                        sample.update(
                            {
                                "status": response.status_code,
                                "server_timing_ms": _server_timing(response.headers.get("server-timing")),
                            }
                        )
                        response_id = response.headers.get("x-kifu-request-id")
                        if response_id is not None and response_id != sample["request_id"]:
                            sample["errors"].append("request_id_mismatch")
                        if response.status_code != 200:
                            sample["errors"].append("http_status")
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            sample["response_bytes"] += len(chunk)
                        sample["complete_body"] = True
                    sample["http_ms"] = (loop.time() - http_start) * 1000
                    try:
                        body = json.loads(content)
                    except (ValueError, UnicodeError):
                        sample["errors"].append("invalid_json")
                    else:
                        sample["json_valid"] = True
                        sample["semantic_errors"] = semantic_errors(body, cases[index % len(cases)])
                        if sample["semantic_errors"]:
                            sample["errors"].append("semantic_difference")
            except (TimeoutError, httpx.TimeoutException):
                sample["errors"].append("timeout")
            except httpx.HTTPError:
                sample["errors"].append("http_error")
            except asyncio.CancelledError:
                sample["errors"].append("drain_expired")
                raise
            except Exception:
                # Transport/decoder failures must never become successful missing responses.
                # Keep exception text out of logs because it can embed URLs or body content.
                sample["errors"].append("client_error")
            finally:
                if sample["http_ms"] is None:
                    sample["http_ms"] = (loop.time() - http_start) * 1000
                active -= 1
                finish(sample)
                queue.task_done()

    emit(run.copy())
    limits = httpx.Limits(max_connections=max_inflight, max_keepalive_connections=max_inflight)
    async with httpx.AsyncClient(
        base_url=base_url,
        limits=limits,
        timeout=timeout_s,
        follow_redirects=False,
        trust_env=False,
        transport=transport,
    ) as client:
        workers = [asyncio.create_task(worker(client)) for _ in range(min(max_inflight, len(samples)))]
        try:
            for index, offset in enumerate(plan["offsets_s"]):
                await asyncio.sleep(max(0, start + offset - loop.time()))
                queue.put_nowait(index)
            await asyncio.sleep(max(0, start + plan["window_s"] - loop.time()))
            await asyncio.wait_for(queue.join(), timeout=max(0, start + plan["window_s"] + drain_s - loop.time()))
        except TimeoutError:
            pass
        except asyncio.CancelledError:
            run["interrupted"] = True
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            for sample in samples:
                if sample["client_wall_ms"] is None:
                    sample["errors"].append("drain_expired")
                    finish(sample)
    run["elapsed_s"] = loop.time() - start
    summary = summarize(run, samples)
    emit(summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url")
    parser.add_argument("--casefile", type=Path)
    parser.add_argument("--profile", choices=("low", "high", "ramp", "custom"), default="low")
    parser.add_argument("--rate", type=float)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--count", type=int)
    parser.add_argument("--max-inflight", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--drain", type=float, default=2)
    parser.add_argument("--summarize", type=Path, help="offline client JSONL; generates no traffic")
    parser.add_argument("--server-metrics", type=Path, help="correlate actual ASGI JSONL using the same host clock")
    parser.add_argument("--output", type=Path, help="JSONL destination; default stdout")
    args = parser.parse_args(argv)
    destination = sys.stdout

    def emit(row):
        destination.write(json.dumps(row, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n")
        destination.flush()

    try:
        if args.output:
            destination = args.output.open("x")
        if args.summarize:
            rows = [json.loads(line) for line in args.summarize.read_text().splitlines() if line.strip()]
            runs = [row for row in rows if row.get("type") == "run"]
            if len(runs) != 1:
                raise ValueError("client JSONL must contain exactly one run")
            prior = [row for row in rows if row.get("type") == "summary"]
            run = prior[-1].get("run", runs[0]) if prior else runs[0]
            metrics = read_server_metrics(args.server_metrics) if args.server_metrics else None
            summary = summarize(run, [row for row in rows if row.get("type") == "sample"], metrics)
            emit(summary)
        else:
            if not args.base_url or not args.casefile or args.server_metrics:
                raise ValueError("run requires --base-url and --casefile; server metrics use offline --summarize")
            raw = args.casefile.read_bytes()
            cases = validate_cases(json.loads(raw))
            plan = make_plan(args.profile, rate=args.rate, duration=args.duration, count=args.count)
            summary = asyncio.run(
                run_load(
                    args.base_url,
                    cases,
                    plan,
                    max_inflight=args.max_inflight,
                    timeout_s=args.timeout,
                    drain_s=args.drain,
                    emit=emit,
                    casefile_sha256=hashlib.sha256(raw).hexdigest(),
                )
            )
        return {"pass": 0, "fail": 1, "not_observed": 3}[summary["gates"]["overall"]]
    except (ValueError, OSError):
        # Do not echo JSON decoding context, URLs, query terms, or exception bodies.
        print("Invalid input/output; check the documented casefile and metric contracts.", file=sys.stderr)
        return 2
    finally:
        if destination is not sys.stdout:
            destination.close()


if __name__ == "__main__":
    raise SystemExit(main())
