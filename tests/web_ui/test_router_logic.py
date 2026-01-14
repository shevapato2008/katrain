import pytest
from katrain.web.core.router import RequestRouter

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
    assert result["engine"] == "local" # Fallback to local
