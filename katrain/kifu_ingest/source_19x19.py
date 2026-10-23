"""Bounded, injectable client for the public 19x19 game API."""

import asyncio
import random
import re
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import httpx


class SourceError(Exception):
    def __init__(self, message, *, retryable=True, code=None, source_message=None):
        super().__init__(message)
        self.retryable = retryable
        self.code = code
        self.source_message = source_message


class SourceBudgetExceeded(SourceError):
    """The run stopped before another network request could be made."""


class SourceRateLimited(SourceError):
    """Retry-After exceeds this run's permitted wait; defer the next request."""

    def __init__(self, retry_after):
        super().__init__("HTTP 429")
        self.retry_after = retry_after


class Source19x19:
    source_key = "19x19"
    base_url = "https://api.19x19.com/api/engine"
    username = "0086-golaxy_public"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        sleep=asyncio.sleep,
        clock=time.monotonic,
        list_interval=(5, 10),
        sgf_interval=(2, 5),
        max_retries=3,
        max_requests=500,
        deadline=None,
        retry_after_cap=60,
    ):
        """Create a client; max_retries=3 permits one request and three retries."""
        self.client = client
        self.sleep = sleep
        self.clock = clock
        self.list_interval = list_interval
        self.sgf_interval = sgf_interval
        self.max_retries = max_retries
        self.max_requests = max_requests
        self.deadline = deadline
        self.retry_after_cap = retry_after_cap
        self.requests = 0
        self._last_request = None

    def _remaining(self):
        return float("inf") if self.deadline is None else self.deadline - self.clock()

    async def _pause(self, seconds):
        if seconds > self._remaining():
            raise SourceBudgetExceeded("source time budget exhausted")
        if seconds > 0:
            await self.sleep(seconds)

    @staticmethod
    def _retry_after(response):
        value = response.headers.get("Retry-After", "")
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return 1.0

    async def _request(self, method, path, *, interval, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Referer": "https://www.19x19.com/",
            "Accept": "application/json, text/plain, */*",
        }
        for attempt in range(self.max_retries + 1):
            if self.requests >= self.max_requests or self._remaining() <= 0:
                raise SourceBudgetExceeded("source request budget exhausted")
            if self._last_request is not None:
                await self._pause(max(0.0, random.uniform(*interval) - (self.clock() - self._last_request)))
            self.requests += 1
            self._last_request = self.clock()
            try:
                remaining = self._remaining()
                response = await asyncio.wait_for(
                    self.client.request(
                        method, self.base_url + path, headers=headers, timeout=min(30, remaining), **kwargs
                    ),
                    timeout=remaining,
                )
            except asyncio.TimeoutError as exc:
                raise SourceBudgetExceeded("source time budget exhausted during request") from exc
            except httpx.RequestError as exc:
                error = SourceError(f"network error: {exc}")
                if attempt == self.max_retries:
                    raise error from exc
                await self._pause(min(2**attempt, self.retry_after_cap))
                continue
            if response.status_code == 429:
                delay = self._retry_after(response)
                # Retry-After applies to the whole source, including other IDs.
                raise SourceRateLimited(delay)
            if response.status_code >= 500:
                error = SourceError(f"HTTP {response.status_code}")
                if attempt == self.max_retries:
                    raise error
                await self._pause(min(2**attempt, self.retry_after_cap))
                continue
            if response.status_code != 200:
                raise SourceError(f"HTTP {response.status_code}", retryable=False)
            try:
                body = response.json()
            except ValueError as exc:
                raise SourceError("invalid JSON response") from exc
            if not isinstance(body, dict) or body.get("code") not in ("0", 0):
                code = body.get("code") if isinstance(body, dict) else "invalid body"
                message = str(body.get("msg") or body.get("message") or "")[:512] if isinstance(body, dict) else ""
                raise SourceError(
                    f"source business error: {code}",
                    retryable=not (path.startswith("/games/shared/") and str(code) == "7004"),
                    code=code,
                    source_message=message,
                )
            return body.get("data")
        raise SourceError("source retries exhausted")

    async def fetch_page(self, page: int):
        if not isinstance(page, int) or page < 0:
            raise ValueError("page must be a nonnegative integer")
        data = await self._request(
            "GET",
            f"/games/{self.username}",
            interval=self.list_interval,
            params={"page": page, "size": 20, "game_type": 2, "username": self.username},
        )
        if not isinstance(data, dict) or not isinstance(data.get("gameMetaList"), list):
            raise SourceError("missing gameMetaList")
        games = data["gameMetaList"]
        if any(not isinstance(item, dict) or not re.fullmatch(r"[0-9]+", str(item.get("id", ""))) for item in games):
            raise SourceError("invalid game metadata")
        return games

    async def fetch_sgf(self, external_id: str):
        if not isinstance(external_id, str) or not re.fullmatch(r"[0-9]+", external_id):
            raise ValueError("external_id must contain only digits")
        data = await self._request(
            "POST",
            f"/games/shared/{external_id}",
            interval=self.sgf_interval,
            json={"id": int(external_id)},
        )
        if not isinstance(data, dict) or not isinstance(data.get("sgf"), str) or not data["sgf"]:
            raise SourceError("missing SGF")
        # Match the existing finite publication artifact limit (16 MiB).
        if len(data["sgf"].encode("utf-8")) > 16 * 1024 * 1024:
            raise SourceError("SGF exceeds 16 MiB limit", retryable=False)
        return data["sgf"]
