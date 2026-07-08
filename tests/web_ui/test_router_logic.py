import pytest
from katrain.web.core.router import RequestRouter, build_router


class MockClient:
    def __init__(self, name):
        self.name = name

    async def analyze(self, payload):
        return {"engine": self.name, "data": payload}


@pytest.fixture
def router():
    local_client = MockClient("local")
    cloud_client = MockClient("cloud")
    return RequestRouter(local_client=local_client, cloud_client=cloud_client)


@pytest.mark.asyncio
async def test_router_play_request(router):
    # Play requests usually have a smaller maxVisits or are specifically marked
    # For this implementation, let's assume if 'is_analysis' is False, it's a play request
    payload = {"is_analysis": False, "maxVisits": 10}
    result = await router.route(payload)
    assert result["engine"] == "local"


@pytest.mark.asyncio
async def test_router_analysis_request(router):
    # Analysis requests are marked as such
    payload = {"is_analysis": True, "maxVisits": 1000}
    result = await router.route(payload)
    assert result["engine"] == "cloud"


@pytest.mark.asyncio
async def test_router_fallback_if_cloud_unconfigured():
    local_client = MockClient("local")
    router = RequestRouter(local_client=local_client, cloud_client=None)

    payload = {"is_analysis": True}
    result = await router.route(payload)
    assert result["engine"] == "local"  # Fallback to local


# -- build_router: the single knob shared by server AND board modes (Wave B #4) --------


def test_build_router_attaches_cloud_iff_url_set():
    # CLOUD_KATAGO_URL set -> cloud client present (analysis reaches the strong GPU).
    r = build_router("http://local:8000", "http://cloud:8000")
    assert r.cloud_client is not None
    assert r.local_client is not None


def test_build_router_local_only_when_cloud_url_blank():
    # Board mode used to hard-wire cloud_client=None regardless of the URL; now an empty
    # CLOUD_KATAGO_URL (the default) yields local-only, a set URL yields cloud — same wiring
    # for both modes, so is_analysis degrades to local exactly when no cloud engine exists.
    for blank in ("", None):
        r = build_router("http://local:8000", blank)
        assert r.cloud_client is None
        assert r.local_client is not None
