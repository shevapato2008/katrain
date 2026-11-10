"""Root SPA routes must not swallow retired URLs, API misses, or missing assets."""

import pytest
from fastapi.testclient import TestClient

from katrain.web.core.config import settings
from katrain.web import server


SPA_PATHS = (
    "/play",
    "/play/ai",
    "/play/game/session",
    "/play/human",
    "/play/human/room/session",
    "/research",
    "/membership",
    "/report",
    "/report/7",
    "/kifu",
    "/kifu/7/replay",
    "/kifu/7/report",
    "/live",
    "/live/7",
    "/tsumego",
    "/tsumego/problem/7",
    "/tsumego/elementary",
    "/tsumego/elementary/life",
    "/tsumego/elementary/life/1",
    "/tutorials",
    "/tutorials/book/7",
    "/tutorials/section/7",
    "/tutorials/elementary",
)
SERVER_INDEX = b"<!doctype html><title>isolated Galaxy index</title>"
BOARD_INDEX = b"<!doctype html><title>isolated strict kiosk index</title>"
ASSETS = {
    "app.js": (b"console.log('isolated asset');", {"application/javascript", "text/javascript"}),
    "app.css": (b"body { color: black; }", {"text/css"}),
}


@pytest.fixture
def static_tree(tmp_path, monkeypatch):
    """Use no built output and never enter the application's lifespan."""
    package_root = tmp_path / "katrain"
    web_root = package_root / "web"
    for directory, index in (("static", SERVER_INDEX), ("static-kiosk-2d", BOARD_INDEX)):
        static_root = web_root / directory
        (static_root / "assets").mkdir(parents=True)
        (static_root / "index.html").write_bytes(index)
        for filename, (content, _) in ASSETS.items():
            (static_root / "assets" / filename).write_bytes(content)
    for directory in ("img", "fonts", "sounds"):
        (package_root / directory).mkdir()
    monkeypatch.setattr(server, "__file__", str(web_root / "server.py"))
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    return web_root


@pytest.fixture
def spa_client(static_tree):
    # TestClient's context manager starts lifespan; plain construction does not.
    client = TestClient(server.create_app(enable_engine=False), follow_redirects=False)
    try:
        yield client
    finally:
        client.close()


def assert_index(response, index=SERVER_INDEX):
    assert response.status_code == 200
    assert "location" not in response.headers
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"
    assert response.content == index


@pytest.mark.parametrize("path", ["/"] + [variant for path in SPA_PATHS for variant in (path, path + "/")])
def test_root_spa_routes_support_get_and_head_without_redirects(spa_client, path):
    response = spa_client.get(path)
    assert_index(response)

    head = spa_client.head(path)
    assert head.status_code == 200
    assert "location" not in head.headers
    assert head.content == b""
    for header in ("content-type", "content-length", "cache-control", "etag", "last-modified"):
        assert head.headers[header] == response.headers[header]


def test_root_query_does_not_redirect(spa_client):
    assert_index(spa_client.get("/?code=login-code&next=%2Fplay%2Fhuman"))


@pytest.mark.parametrize(
    "path",
    (
        "/galaxy",
        "/galaxy/",
        "/galaxy/kifu",
        "/unknown-page",
        "/play/not-a-page",
        "/kifu/7/not-a-page",
        "/assets/missing.js",
    ),
)
def test_retired_unknown_and_missing_asset_urls_are_real_404s(spa_client, path):
    for method in ("GET", "HEAD"):
        response = spa_client.request(method, path)
        assert response.status_code == 404
        assert "location" not in response.headers
        assert response.content != SERVER_INDEX
        if method == "HEAD":
            assert response.content == b""


@pytest.mark.parametrize("filename", ASSETS)
def test_existing_assets_keep_their_bytes_and_content_type(spa_client, filename):
    content, media_types = ASSETS[filename]
    response = spa_client.get(f"/assets/{filename}")
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].split(";", 1)[0] in media_types
    assert "location" not in response.headers


def test_missing_api_route_remains_json_404(spa_client):
    response = spa_client.get("/api/v1/not-a-route")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}
    assert "location" not in response.headers


def test_health_and_openapi_keep_their_original_handlers(spa_client, monkeypatch):
    # Empty upstream URLs fail locally, so health checks make no network calls.
    monkeypatch.setattr(settings, "LOCAL_KATAGO_URL", "")
    monkeypatch.setattr(settings, "CLOUD_KATAGO_URL", "")
    monkeypatch.setattr(settings, "REPORT_ENGINE_HEALTH_URL", "")
    for path in ("/health", "/api/v1/health"):
        response = spa_client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.json()["status"] == "ok"
        assert response.json()["engines"] == {"local": "unreachable", "cloud": "unconfigured"}

    response = spa_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    schema = response.json()
    assert "/api/session" in schema["paths"]
    assert "/play" not in schema["paths"]


@pytest.mark.parametrize("path", ("/kiosk", "/kiosk/settings", "/record"))
def test_kiosk_and_record_keep_serving_the_index(spa_client, path):
    response = spa_client.get(path)
    assert response.status_code == 200
    assert response.content == SERVER_INDEX
    assert response.headers["content-type"].startswith("text/html")
    assert "location" not in response.headers


def test_board_root_uses_the_strict_kiosk_bundle(static_tree, monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    client = TestClient(server.create_app(enable_engine=False), follow_redirects=False)
    try:
        assert_index(client.get("/"), BOARD_INDEX)
        assert_index(client.get("/kiosk"), BOARD_INDEX)
    finally:
        client.close()
