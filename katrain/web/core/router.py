from typing import Optional
from katrain.web.core.engine_client import KataGoClient

class RequestRouter:
    def __init__(self, local_client: KataGoClient, cloud_client: Optional[KataGoClient] = None):
        self.local_client = local_client
        self.cloud_client = cloud_client

    async def route(self, payload: dict, timeout: float | None = None) -> dict:
        is_analysis = payload.get("is_analysis", False)

        if is_analysis and self.cloud_client:
            result = await self.cloud_client.analyze(payload, timeout=timeout)
            result["engine"] = "cloud"
            return result

        result = await self.local_client.analyze(payload, timeout=timeout)
        result["engine"] = "local"
        return result
