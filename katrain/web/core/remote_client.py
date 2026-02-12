"""HTTP client for board mode → remote KaTrain server communication.

See design.md Section 4.7 for the full API surface.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("katrain_web")


class RemoteAPIClient:
    """Async HTTP client wrapping calls to the remote KaTrain server.

    Features:
    - Automatic access_token refresh on 401 via refresh_token
    - Connection pooling via httpx.AsyncClient
    - Health check with RTT measurement
    """

    def __init__(
        self,
        base_url: str,
        device_id: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._auth_required: bool = False  # True when refresh also fails
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            trust_env=False,
        )

    # ── Token Management ──

    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None):
        self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token
        self._auth_required = False

    def set_refresh_token(self, refresh_token: str):
        self._refresh_token = refresh_token
        self._auth_required = False

    def clear_tokens(self):
        """Clear all tokens and mark auth as required (used on logout)."""
        self._access_token = None
        self._refresh_token = None
        self._auth_required = True

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None and not self._auth_required

    @property
    def auth_required(self) -> bool:
        return self._auth_required

    def _auth_headers(self) -> Dict[str, str]:
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    async def _refresh_access_token(self) -> bool:
        """Attempt to refresh the access token. Returns True on success."""
        if not self._refresh_token:
            return False
        try:
            resp = await self._client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": self._refresh_token},
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data["access_token"]
                self._auth_required = False
                logger.info("Access token refreshed successfully")
                return True
            else:
                logger.warning(f"Refresh token rejected: {resp.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
            return False

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Optional[Dict] = None,
        auth: bool = True,
    ) -> httpx.Response:
        """Make an HTTP request with automatic token refresh on 401."""
        headers = self._auth_headers() if auth else {}
        resp = await self._client.request(method, path, json=json, params=params, headers=headers)

        if resp.status_code == 401 and auth and self._refresh_token:
            refreshed = await self._refresh_access_token()
            if refreshed:
                headers = self._auth_headers()
                resp = await self._client.request(method, path, json=json, params=params, headers=headers)
            else:
                self._auth_required = True
                logger.warning("Auth required: both access and refresh tokens invalid")

        return resp

    # ── Auth ──

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        resp = await self._request(
            "POST",
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            auth=False,
        )
        resp.raise_for_status()
        data = resp.json()
        self.set_tokens(data["access_token"], data.get("refresh_token"))
        return data

    async def register(self, username: str, password: str) -> Dict[str, Any]:
        resp = await self._request(
            "POST",
            "/api/v1/auth/register",
            json={"username": username, "password": password},
            auth=False,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Tsumego (read-only) ──

    async def get_levels(self) -> List[Dict]:
        resp = await self._request("GET", "/api/v1/tsumego/levels")
        resp.raise_for_status()
        return resp.json()

    async def get_problems(self, level: str, category: str, offset: int = 0, limit: int = 20) -> List[Dict]:
        resp = await self._request(
            "GET",
            f"/api/v1/tsumego/levels/{level}/categories/{category}",
            params={"offset": offset, "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_problem(self, problem_id: str) -> Dict:
        resp = await self._request("GET", f"/api/v1/tsumego/problems/{problem_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_progress(self) -> Dict:
        resp = await self._request("GET", "/api/v1/tsumego/progress")
        resp.raise_for_status()
        return resp.json()

    async def update_progress(self, problem_id: str, data: Dict) -> Dict:
        resp = await self._request("POST", f"/api/v1/tsumego/progress/{problem_id}", json=data)
        resp.raise_for_status()
        return resp.json()

    # ── Kifu (read-only) ──

    async def search_kifu(self, **params) -> Dict:
        resp = await self._request("GET", "/api/v1/kifu/albums", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_kifu(self, album_id: int) -> Dict:
        resp = await self._request("GET", f"/api/v1/kifu/albums/{album_id}")
        resp.raise_for_status()
        return resp.json()

    # ── User Games (CRUD) ──

    async def list_user_games(self, **params) -> Dict:
        resp = await self._request("GET", "/api/v1/user-games/", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_user_game(self, data: Dict) -> Dict:
        resp = await self._request("POST", "/api/v1/user-games/", json=data)
        resp.raise_for_status()
        return resp.json()

    async def get_user_game(self, game_id: str) -> Dict:
        resp = await self._request("GET", f"/api/v1/user-games/{game_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Live (read-only) ──

    async def get_live_matches(self, **params) -> Any:
        # Filter out None values from params
        params = {k: v for k, v in params.items() if v is not None}
        resp = await self._request("GET", "/api/v1/live/matches", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_live_match(self, match_id: str) -> Dict:
        resp = await self._request("GET", f"/api/v1/live/matches/{match_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Board (device management) ──

    async def heartbeat(
        self,
        queue_depth: int = 0,
        failed_count: int = 0,
        oldest_unsynced_age_sec: int = 0,
        last_sync_at: Optional[str] = None,
    ) -> Dict:
        resp = await self._request(
            "POST",
            "/api/v1/board/heartbeat",
            json={
                "device_id": self.device_id,
                "queue_depth": queue_depth,
                "failed_count": failed_count,
                "oldest_unsynced_age_sec": oldest_unsynced_age_sec,
                "last_sync_at": last_sync_at,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ── Health ──

    async def check_health(self) -> Dict[str, Any]:
        """Check remote server health. Returns {ok: bool, rtt_ms: int}."""
        start = time.monotonic()
        try:
            resp = await self._client.get("/health", timeout=5.0)
            rtt_ms = int((time.monotonic() - start) * 1000)
            return {"ok": resp.status_code == 200, "rtt_ms": rtt_ms}
        except Exception:
            rtt_ms = int((time.monotonic() - start) * 1000)
            return {"ok": False, "rtt_ms": rtt_ms}

    # ── Lifecycle ──

    async def close(self):
        await self._client.aclose()
