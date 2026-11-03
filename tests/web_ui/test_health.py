import asyncio

import httpx
import pytest

from katrain.web.api.v1.endpoints import health


def model_payload(**overrides):
    return {
        "default_model": "analysis",
        "models": {
            "analysis": {
                "running": True,
                "model_sha256_verified": True,
                "model_path": "/private/weights/kata1-b28c512-s123.bin.gz",
                **overrides,
            }
        },
    }


def test_model_uses_real_filename_not_route_alias():
    assert health._analysis_model_id(model_payload()) == "kata1-b28c512-s123"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"default_model": []},
        model_payload(running=False),
        model_payload(model_sha256_verified=False),
        model_payload(model_path="/weights/bad name.bin.gz"),
        model_payload(model_path="/weights/"),
        model_payload(model_path="x" * 121),
    ],
)
def test_malformed_or_unverified_model_is_unavailable(payload):
    assert health._analysis_model_id(payload) is None


def test_health_preserves_contract_and_board_uses_normalized_remote(monkeypatch):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"katago_model": "kata1-b28c512-s456"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        health.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs)
    )
    monkeypatch.setattr(health.settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(health.settings, "REMOTE_API_URL", "https://remote.test/api/v1/")
    monkeypatch.setattr(health.settings, "LOCAL_KATAGO_URL", "http://local.test")
    monkeypatch.setattr(health.settings, "CLOUD_KATAGO_URL", "")
    result = asyncio.run(health.health(None))
    assert result == {
        "status": "ok",
        "version": health.VERSION,
        "engines": {"local": "reachable", "cloud": "unconfigured"},
        "katago_model": "kata1-b28c512-s456",
    }
    assert calls == ["http://local.test/health", "https://remote.test/api/v1/health"]


@pytest.mark.parametrize("response", [model_payload(), {"katago_model": "/private/model"}, None])
def test_server_uses_explicit_analysis_service(monkeypatch, response):
    original_client = httpx.AsyncClient
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=response)

    monkeypatch.setattr(
        health.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs)
    )
    monkeypatch.setattr(health.settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(health.settings, "REPORT_ENGINE_HEALTH_URL", "http://analysis.test/health")
    assert asyncio.run(health._current_model_id()) == ("kata1-b28c512-s123" if response == model_payload() else None)
    assert calls == ["http://analysis.test/health"]


def test_unreachable_analysis_is_unavailable(monkeypatch):
    original_client = httpx.AsyncClient

    def fail(request):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(
        health.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(fail), **kwargs)
    )
    monkeypatch.setattr(health.settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(health.settings, "REPORT_ENGINE_HEALTH_URL", "http://analysis.test/health")
    assert asyncio.run(health._current_model_id()) is None
