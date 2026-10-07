"""The cron engine must reject a successful-looking but unusable response."""

import pytest
import httpx
from unittest.mock import patch

from katrain.cron.clients.katago import KataGoClient


MODEL_SHA = "93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871"


def response():
    return {
        "id": "position-0",
        "turnNumber": 0,
        "isDuringSearch": False,
        "_wrapper": {
            "selected_model": "tf3-b11c768",
            "model_sha256": MODEL_SHA,
            "model_sha256_verified": True,
        },
        "rootInfo": {"visits": 2000, "winrate": 0.51, "scoreLead": 0.3},
        "moveInfos": [{"move": "Q16", "visits": 1200, "winrate": 0.52, "scoreLead": 0.5, "prior": 0.2, "pv": ["Q16"]}],
        "ownership": [0.0] * 361,
    }


def test_accepts_model_and_extra_fields():
    result = response()
    result["futureField"] = {"anything": True}
    KataGoClient.validate_result(result, "position-0", 0, 19, MODEL_SHA, min_visits=2000)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(error="engine rejected request"),
        lambda d: d.update(id="wrong"),
        lambda d: d.update(turnNumber=1),
        lambda d: d.update(isDuringSearch=True),
        lambda d: d["_wrapper"].update(model_sha256="wrong"),
        lambda d: d["_wrapper"].update(model_sha256_verified=False),
        lambda d: d["rootInfo"].pop("winrate"),
        lambda d: d["rootInfo"].update(visits=1999),
        lambda d: d.update(moveInfos=[]),
        lambda d: d.update(ownership=[0.0] * 360),
    ],
)
def test_rejects_unusable_results(change):
    result = response()
    change(result)
    with pytest.raises(ValueError):
        KataGoClient.validate_result(result, "position-0", 0, 19, MODEL_SHA, min_visits=2000)


@pytest.mark.asyncio
async def test_health_requires_configured_default_model_sha():
    payload = {
        "ready": True,
        "default_model": "tf3-b11c768",
        "models": {"tf3-b11c768": {"running": True, "model_sha256": MODEL_SHA, "model_sha256_verified": True}},
    }

    def handler(request):
        return httpx.Response(200, json=payload)

    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)

    with patch("katrain.cron.clients.katago.httpx.AsyncClient", Client), patch(
        "katrain.cron.clients.katago.config.KATAGO_EXPECTED_MODEL_SHA256", MODEL_SHA
    ):
        assert await KataGoClient().health_check()
        payload["models"]["tf3-b11c768"]["model_sha256"] = "old"
        assert not await KataGoClient().health_check()
