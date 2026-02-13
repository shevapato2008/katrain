import httpx
import logging

logger = logging.getLogger("katrain_web")

class KataGoClient:
    def __init__(self, url: str, timeout: float = 120.0):
        self.url = url.rstrip('/')
        self.timeout = timeout

    async def analyze(self, payload: dict, timeout: float | None = None) -> dict:
        effective_timeout = timeout or self.timeout
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            try:
                response = await client.post(f"{self.url}/analyze", json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"KataGo API error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"KataGo API returned status {e.response.status_code}")
            except httpx.TimeoutException:
                logger.error(f"[KataGo API timeout] {self.url} (timeout={effective_timeout}s)")
                raise Exception("KataGo API timeout")
            except Exception as e:
                logger.error(f"KataGo API connection failed: {e}")
                raise Exception(f"Failed to connect to KataGo API: {e}")
