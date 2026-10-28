"""Measure kifu HTTP responses through the awaited final ASGI body send.

Ingress is entry into this middleware, not proxy or socket acceptance. Handler
Server-Timing remains separate because it ends before validation/serialization.
"""

import json
import logging
import re
from time import perf_counter, time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


_LOGGER = logging.getLogger("katrain_web.kifu_http_timing")
_ROUTE = re.compile(r"/api/v1/kifu/albums(?:/[^/]+(?:/analysis)?)?/?")
_REQUEST_ID = re.compile(r"[0-9a-f]{32}")


class KifuHTTPTimingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _ROUTE.fullmatch(scope["path"]):
            await self.app(scope, receive, send)
            return

        started = perf_counter()
        ingress_unix_s = time()
        incoming_id = Headers(scope=scope).get("x-kifu-request-id", "")
        request_id = incoming_id if _REQUEST_ID.fullmatch(incoming_id) else uuid4().hex
        status = None
        body_bytes = 0
        completed = False

        async def send_with_timing(message: Message) -> None:
            nonlocal status, body_bytes, completed
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["x-kifu-request-id"] = request_id

            await send(message)

            if message["type"] == "http.response.body":
                body_bytes += len(message.get("body", b""))
                if not message.get("more_body", False) and not completed:
                    completed = True
                    _LOGGER.info(
                        json.dumps(
                            {
                                "event": "kifu_http_timing",
                                "request_id": request_id,
                                "ingress_unix_s": ingress_unix_s,
                                "asgi_total_ms": (perf_counter() - started) * 1000,
                                "status": status,
                                "bytes": body_bytes,
                            },
                            separators=(",", ":"),
                        )
                    )

        await self.app(scope, receive, send_with_timing)
