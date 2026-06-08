import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import pytest

import katrain.core.engine as engine_module
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoHttpEngine


class _Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 so the server keeps the connection alive — required to actually
    # exercise the keep-alive Session (HTTP/1.0, the BaseHTTPRequestHandler
    # default, would close after every response and never validate reuse).
    protocol_version = "HTTP/1.1"
    # Class-level knobs the fixture resets before each test.
    status = 200
    delay = 0.0
    big = False

    def _payload(self):
        move_infos = [{"move": "D4", "visits": 10}]
        if _Handler.big:
            move_infos = move_infos * 1000  # large-response coverage (migrated)
        return {
            "id": "x",
            "moveInfos": move_infos,
            "rootInfo": {"visits": 10, "winrate": 0.5},
            "isDuringSearch": False,
        }

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if _Handler.delay:
            time.sleep(_Handler.delay)
        body = json.dumps(self._payload()).encode("utf-8")
        try:
            self.send_response(_Handler.status)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", str(len(body)))  # required for HTTP/1.1 keep-alive
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            pass  # client timed out and went away — not a server-side failure

    def log_message(self, *args):
        pass  # silence server logs


@pytest.fixture
def server():
    _Handler.status = 200
    _Handler.delay = 0.0
    _Handler.big = False
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield port
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2.0)


def _make_engine(port, timeout=8.0):
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    config["http_url"] = f"http://127.0.0.1:{port}"
    config["http_timeout"] = timeout
    return KataGoHttpEngine(katrain, config)


def test_post_json_returns_parsed_json(server):
    engine = _make_engine(server)
    try:
        result = engine._post_json({"id": "q1", "moves": []})
        assert "moveInfos" in result
        assert result["rootInfo"]["visits"] == 10
    finally:
        engine.shutdown(finish=False)


def test_post_json_creates_no_subprocess(server):
    engine = _make_engine(server)
    try:
        with mock.patch("subprocess.Popen") as popen, mock.patch("multiprocessing.get_context") as get_context:
            result = engine._post_json({"id": "q2", "moves": []})
        assert "moveInfos" in result
        get_context.assert_not_called()
        popen.assert_not_called()
    finally:
        engine.shutdown(finish=False)


def test_engine_module_drops_spawn_symbols():
    # Static guard: the de-spawn refactor must not reintroduce the worker import
    # or the multiprocessing module reference at the engine module level.
    assert not hasattr(engine_module, "do_request")
    assert not hasattr(engine_module, "multiprocessing")


def test_post_json_raises_on_http_error(server):
    _Handler.status = 500
    engine = _make_engine(server)
    try:
        with pytest.raises(Exception) as excinfo:
            engine._post_json({"id": "q3", "moves": []})
        assert "500" in str(excinfo.value)
    finally:
        engine.shutdown(finish=False)


def test_post_json_raises_on_timeout(server):
    _Handler.delay = 1.0
    engine = _make_engine(server, timeout=0.2)
    try:
        with pytest.raises(Exception):
            engine._post_json({"id": "q4", "moves": []})
    finally:
        engine.shutdown(finish=False)


def test_post_json_large_response_not_truncated(server):
    _Handler.big = True
    engine = _make_engine(server)
    try:
        result = engine._post_json({"id": "q5", "moves": []})
        assert len(result["moveInfos"]) == 1000
    finally:
        engine.shutdown(finish=False)


def test_concurrent_post_json_share_one_session(server):
    engine = _make_engine(server)
    results = {}
    errors = {}

    def worker(i):
        try:
            results[i] = engine._post_json({"id": f"c{i}", "moves": []})
        except Exception as e:  # pragma: no cover - failure path
            errors[i] = e

    try:
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
        assert not errors
        assert len(results) == 8
        assert all("moveInfos" in r for r in results.values())
    finally:
        engine.shutdown(finish=False)


def test_handle_request_routes_http_error_to_callback(server):
    _Handler.status = 500
    engine = _make_engine(server)
    captured = {}
    done = threading.Event()

    def error_callback(payload):
        captured.update(payload)
        done.set()

    try:
        engine.send_query({"moves": []}, callback=None, error_callback=error_callback)
        assert done.wait(timeout=10.0)
        assert "error" in captured
        assert "id" in captured
        assert engine.available is False
    finally:
        engine.shutdown(finish=False)


def test_restart_during_inflight_does_not_corrupt_availability(server):
    # A slow, erroring request started before restart() must not flip _available
    # on the freshly restarted (new-generation) engine when its torn-down session
    # surfaces the 500 after restart(). The generation guard must block that write.
    _Handler.delay = 0.8
    _Handler.status = 500
    engine = _make_engine(server, timeout=8.0)
    try:
        engine.send_query({"moves": []}, callback=None, error_callback=lambda p: None)
        time.sleep(0.2)  # request is now inside the server's delay window, pre-response
        engine.restart()  # bumps generation, builds a fresh session, closes the old one
        time.sleep(1.2)  # stale request returns 500 and runs _handle_request.except
        assert engine.available is True  # generation guard blocked the stale write
    finally:
        engine.shutdown(finish=False)
