import sys
import os
import asyncio
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from katrain.web.server import create_app
from katrain.core.constants import AI_CONFIG_DEFAULT

# Initialize app without engine for speed
app = create_app(enable_engine=False)

async def test_ai_constants(client):
    print("Testing /api/ai-constants...")
    response = await client.get("/api/ai-constants")
    assert response.status_code == 200
    data = response.json()
    assert "strategies" in data
    assert "options" in data
    assert "key_properties" in data
    assert "default_strategy" in data
    assert data["default_strategy"] == AI_CONFIG_DEFAULT
    assert "kyu_rank" in data["options"]
    print("✓ /api/ai-constants passed")

async def test_estimate_rank(client):
    print("Testing /api/ai/estimate-rank...")
    # Test rank estimation for default AI
    response = await client.post("/api/ai/estimate-rank", json={
        "strategy": "ai:default",
        "settings": {}
    })
    assert response.status_code == 200
    assert response.json()["rank"] == "9d"

    # Test rank estimation for scoreloss with strength adjustment
    response = await client.post("/api/ai/estimate-rank", json={
        "strategy": "ai:scoreloss",
        "settings": {"strength": 0.5}
    })
    assert response.status_code == 200
    # 0.5 strength -> 1346 elo -> ~6k (using CALIBRATED_RANK_ELO)
    # Check if it returns a string like "6k" or similar
    print(f"Rank for scoreloss(0.5): {response.json()['rank']}")
    assert "k" in response.json()["rank"] or "d" in response.json()["rank"]
    print("✓ /api/ai/estimate-rank passed")

async def test_config_endpoints(client):
    print("Testing /api/config...")
    # Create session first
    response = await client.post("/api/session")
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # Get config
    response = await client.get(f"/api/config?session_id={session_id}&setting=general/debug_level")
    assert response.status_code == 200
    assert response.json()["value"] == 0 # Default

    # Update config
    response = await client.post("/api/config", json={
        "session_id": session_id,
        "setting": "general/debug_level",
        "value": 1
    })
    assert response.status_code == 200

    # Verify update
    response = await client.get(f"/api/config?session_id={session_id}&setting=general/debug_level")
    assert response.status_code == 200
    assert response.json()["value"] == 1
    print("✓ /api/config passed")

async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await test_ai_constants(client)
        await test_estimate_rank(client)
        await test_config_endpoints(client)
    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        # Print full traceback
        import traceback
        traceback.print_exc()
        sys.exit(1)