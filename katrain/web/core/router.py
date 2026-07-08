from typing import Optional
from katrain.web.core.engine_client import KataGoClient


class RequestRouter:
    def __init__(self, local_client: KataGoClient, cloud_client: Optional[KataGoClient] = None):
        self.local_client = local_client
        self.cloud_client = cloud_client

    async def route(self, payload: dict) -> dict:
        is_analysis = payload.get("is_analysis", False)

        if is_analysis and self.cloud_client:
            result = await self.cloud_client.analyze(payload)
            result["engine"] = "cloud"
            return result

        result = await self.local_client.analyze(payload)
        result["engine"] = "local"
        return result


def build_router(local_url: str, cloud_url: Optional[str]) -> RequestRouter:
    """Construct the dual-engine router shared by BOTH server and board (kiosk) modes.

    A cloud client is attached IFF *cloud_url* (CLOUD_KATAGO_URL) is set — so a single
    knob turns cloud analysis on: an ``is_analysis`` query (e.g. AI 支招) reaches the
    strong cloud GPU whenever the URL is configured, and degrades to the local engine
    otherwise. Board mode previously hard-wired ``cloud_client=None`` regardless of the
    URL, stranding all kiosk analysis on the weak local SBC engine (Wave B #4)."""
    local_client = KataGoClient(url=local_url)
    cloud_client = KataGoClient(url=cloud_url) if cloud_url else None
    return RequestRouter(local_client=local_client, cloud_client=cloud_client)
