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


def _pool_snapshot(pool):
    """Read boundary values only, with QueuePool's raw possibly negative overflow.

    size() is base capacity, not the base-plus-max-overflow connection limit.
    Unsupported pools and observation failures remain unknown.
    """
    try:
        values = {"size": pool.size(), "checkedout": pool.checkedout(), "overflow": pool.overflow()}
        return values if all(type(value) is int for value in values.values()) else None
    except Exception:
        return None


class KifuHTTPTimingMiddleware:
    def __init__(self, app: ASGIApp, pool=None):
        self.app = app
        self.pool = pool

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _ROUTE.fullmatch(scope["path"]):
            await self.app(scope, receive, send)
            return

        started = perf_counter()
        ingress_unix_s = time()
        pool_at_scope_entry = _pool_snapshot(self.pool) if self.pool is not None else None
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
                    metric = {
                        "event": "kifu_http_timing",
                        "request_id": request_id,
                        "ingress_unix_s": ingress_unix_s,
                        "asgi_total_ms": (perf_counter() - started) * 1000,
                        "status": status,
                        "bytes": body_bytes,
                    }
                    state = scope.get("state", {})
                    if "kifu_reader_pool" in state:
                        metric["reader_pool"] = state["kifu_reader_pool"]
                    elif self.pool is not None:
                        metric["db_pool_at_scope_entry"] = pool_at_scope_entry
                        metric["db_pool_after_final_body"] = _pool_snapshot(self.pool)
                    _LOGGER.info(json.dumps(metric, separators=(",", ":")))

        await self.app(scope, receive, send_with_timing)
