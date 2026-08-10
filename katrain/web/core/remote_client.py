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
        health_timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        # Health probes get their own (shorter) timeout. Defaults to 10s — long
        # enough to absorb a slow TLS handshake or a momentarily starved event
        # loop at startup, but bounded so the 10s health loop stays responsive.
        # Override via KATRAIN_HEALTH_CHECK_TIMEOUT (wired in server.py).
        self._health_timeout = health_timeout
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._auth_required: bool = False  # True when refresh also fails
        # Which LOCAL user this cloud session belongs to. A board is shared, so queued
        # per-user work (a rank event) has to be able to tell "my session is up" from
        # "somebody's session is up" before it posts anything.
        self._bound_user_id: Optional[str] = None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            trust_env=False,
        )

    # ── Token Management ──

    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None, user_id=None):
        self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token
        self._auth_required = False
        if user_id is not None:
            self._bound_user_id = str(user_id)

    def set_refresh_token(self, refresh_token: str):
        self._refresh_token = refresh_token
        self._auth_required = False

    def bind_user(self, user_id) -> None:
        """Say which local user the current cloud session speaks for."""
        self._bound_user_id = None if user_id is None else str(user_id)

    @property
    def bound_user_id(self) -> Optional[str]:
        return self._bound_user_id

    def clear_tokens(self):
        """Clear all tokens and mark auth as required (used on logout)."""
        self._access_token = None
        self._refresh_token = None
        self._auth_required = True
        # Drop the binding too: a restored refresh token proves a session exists, not
        # whose it is, and a stale binding is exactly how one player's game would be
        # credited to the next player who walks up to the board.
        self._bound_user_id = None

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None and not self._auth_required

    @property
    def auth_required(self) -> bool:
        return self._auth_required

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"X-StellaBox-Device-ID": self.device_id}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

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

    async def get_all_problems(self, level: str, page: int = 1, page_size: int = 50) -> Dict:
        resp = await self._request(
            "GET",
            f"/api/v1/tsumego/levels/{level}/problems",
            params={"page": page, "page_size": page_size},
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

    async def delete_user_game(self, game_id: str) -> Dict:
        resp = await self._request("DELETE", f"/api/v1/user-games/{game_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Ranked AI ladder (cloud-authoritative lifecycle) ──

    async def get_ai_ladder_status(self) -> Dict:
        resp = await self._request("GET", "/api/v1/ai-ladder/status")
        resp.raise_for_status()
        return resp.json()

    async def reserve_ai_ladder_game(self, data: Dict) -> Dict:
        resp = await self._request("POST", "/api/v1/ai-ladder/games/reserve", json=data)
        resp.raise_for_status()
        return resp.json()

    async def activate_ai_ladder_game(self, game_id: str, reservation_key: str, session_id: str) -> Dict:
        resp = await self._request(
            "POST",
            f"/api/v1/ai-ladder/games/{game_id}/activate",
            json={"reservation_key": reservation_key, "session_id": session_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def mark_ai_ladder_game_pending(self, game_id: str, reservation_key: str) -> Dict:
        resp = await self._request(
            "POST",
            f"/api/v1/ai-ladder/games/{game_id}/pending-settlement",
            json={"reservation_key": reservation_key},
        )
        resp.raise_for_status()
        return resp.json()

    async def cancel_ai_ladder_reservation(self, game_id: str, reservation_key: str) -> Dict:
        resp = await self._request(
            "DELETE",
            f"/api/v1/ai-ladder/games/{game_id}/reservation",
            json={"reservation_key": reservation_key},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_ai_ladder_game_status(self, game_id: str) -> Dict:
        resp = await self._request("GET", f"/api/v1/ai-ladder/games/{game_id}/status")
        resp.raise_for_status()
        return resp.json()

    async def end_ai_ladder_game(self, game_id: str) -> Dict:
        resp = await self._request(
            "POST", f"/api/v1/ai-ladder/games/{game_id}/end", json={"reason": "user_resigned"}
        )
        resp.raise_for_status()
        return resp.json()

    # ── Reports (remote-only in board mode) ──

    async def list_reports(self) -> List[Dict]:
        resp = await self._request("GET", "/api/v1/reports/")
        resp.raise_for_status()
        return resp.json()

    async def get_report_summary(self) -> Dict:
        resp = await self._request("GET", "/api/v1/reports/summary")
        resp.raise_for_status()
        return resp.json()

    async def get_report(self, task_id: int) -> Dict:
        resp = await self._request("GET", f"/api/v1/reports/{task_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_report(self, data: Dict) -> Dict:
        resp = await self._request("POST", "/api/v1/reports/", json=data)
        resp.raise_for_status()
        return resp.json()

    async def retry_report(self, task_id: int) -> Dict:
        resp = await self._request("POST", f"/api/v1/reports/{task_id}/retry")
        resp.raise_for_status()
        return resp.json()

    async def get_report_moves(self, task_id: int) -> List[Dict]:
        resp = await self._request("GET", f"/api/v1/reports/{task_id}/moves")
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

    async def get_live_featured(self, lang: Optional[str] = None) -> Dict:
        params = {k: v for k, v in {"lang": lang}.items() if v is not None}
        resp = await self._request("GET", "/api/v1/live/matches/featured", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_live_match_analysis(self, match_id: str, move_number: Optional[int] = None) -> Dict:
        params = {k: v for k, v in {"move_number": move_number}.items() if v is not None}
        resp = await self._request("GET", f"/api/v1/live/matches/{match_id}/analysis", params=params)
        resp.raise_for_status()
        return resp.json()

    async def preload_live_analysis(self, match_id: str) -> Dict:
        resp = await self._request("GET", f"/api/v1/live/matches/{match_id}/analysis/preload")
        resp.raise_for_status()
        return resp.json()

    async def get_live_upcoming(self, limit: int = 20, lang: Optional[str] = None) -> Dict:
        params = {k: v for k, v in {"limit": limit, "lang": lang}.items() if v is not None}
        resp = await self._request("GET", "/api/v1/live/upcoming", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_live_stats(self) -> Dict:
        resp = await self._request("GET", "/api/v1/live/stats")
        resp.raise_for_status()
        return resp.json()

    async def get_live_translations(self, lang: str) -> Dict:
        resp = await self._request("GET", "/api/v1/live/translations", params={"lang": lang})
        resp.raise_for_status()
        return resp.json()

    # ── Tutorial (read-only, public) ──

    async def get_tutorial_categories(self) -> Any:
        resp = await self._request("GET", "/api/v1/tutorials/categories", auth=False)
        resp.raise_for_status()
        return resp.json()

    async def get_tutorial_books(self, category: str) -> Any:
        from urllib.parse import quote

        resp = await self._request("GET", f"/api/v1/tutorials/categories/{quote(category)}/books", auth=False)
        resp.raise_for_status()
        return resp.json()

    async def get_tutorial_book(self, book_id: int) -> Any:
        resp = await self._request("GET", f"/api/v1/tutorials/books/{book_id}", auth=False)
        resp.raise_for_status()
        return resp.json()

    async def get_tutorial_chapters(self, book_id: int) -> Any:
        resp = await self._request("GET", f"/api/v1/tutorials/books/{book_id}/chapters", auth=False)
        resp.raise_for_status()
        return resp.json()

    async def get_tutorial_sections(self, chapter_id: int) -> Any:
        resp = await self._request("GET", f"/api/v1/tutorials/chapters/{chapter_id}/sections", auth=False)
        resp.raise_for_status()
        return resp.json()

    async def get_tutorial_section(self, section_id: int) -> Any:
        resp = await self._request("GET", f"/api/v1/tutorials/sections/{section_id}", auth=False)
        resp.raise_for_status()
        return resp.json()

    async def get_tutorial_figure(self, figure_id: int) -> Any:
        resp = await self._request("GET", f"/api/v1/tutorials/figures/{figure_id}", auth=False)
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
            resp = await self._client.get("/health", timeout=self._health_timeout)
            rtt_ms = int((time.monotonic() - start) * 1000)
            return {"ok": resp.status_code == 200, "rtt_ms": rtt_ms}
        except Exception:
            rtt_ms = int((time.monotonic() - start) * 1000)
            return {"ok": False, "rtt_ms": rtt_ms}

    # ── Lifecycle ──

    async def close(self):
        await self._client.aclose()
