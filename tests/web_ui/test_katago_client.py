import pytest
import respx
from httpx import Response
from katrain.web.core.engine_client import KataGoClient

@pytest.mark.asyncio
@respx.mock
async def test_katago_client_analyze_success():
    client = KataGoClient(url="http://katago:8000")
    payload = {"id": "test", "moves": []}
    
    # Mock the KataGo Analysis API
    respx.post("http://katago:8000/analyze").mock(return_value=Response(200, json={"id": "test", "analysis": []}))
    
    result = await client.analyze(payload)
    assert result["id"] == "test"
    assert "analysis" in result

@pytest.mark.asyncio
@respx.mock
async def test_katago_client_error_handling():
    client = KataGoClient(url="http://katago:8000")
    
    # Mock a 500 error
    respx.post("http://katago:8000/analyze").mock(return_value=Response(500))
    
    with pytest.raises(Exception) as excinfo:
        await client.analyze({"id": "err"})
    assert "500" in str(excinfo.value)

@pytest.mark.asyncio
@respx.mock
async def test_katago_client_timeout():
    client = KataGoClient(url="http://katago:8000", timeout=0.1)
    
    # Mock a timeout
    respx.post("http://katago:8000/analyze").mock(side_effect=pytest.importorskip("httpx").TimeoutException("Timeout"))
    
    with pytest.raises(Exception) as excinfo:
        await client.analyze({"id": "timeout"})
    assert "timeout" in str(excinfo.value).lower()
