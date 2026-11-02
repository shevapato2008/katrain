"""HTTP client for board mode → remote KaTrain server communication.

See design.md Section 4.7 for the full API surface.
"""

import logging
import time
from typing import Any, Dict, List, NamedTuple, Optional

import httpx

logger = logging.getLogger("katrain_web")


def user_game_write_refusal_code(response: httpx.Response) -> Optional[str]:
    """Distinguish explicit game write refusals from legacy duplicate 409s."""
    if response.status_code != 409:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    detail = body.get("detail") if isinstance(body, dict) else None
    code = detail.get("code") if isinstance(detail, dict) else None
    if isinstance(code, str) and code in {"report_bound_game_immutable", "user_game_identity_conflict"}:
        return code
    return None


class _CloudIdentity(NamedTuple):
    user_id: str
    generation: int
    access_token: str
    refresh_token: Optional[str]


class CloudIdentityChangedError(httpx.HTTPStatusError):
    """A private cloud request no longer belongs to the active local user."""

    def __init__(self):
        request = httpx.Request("GET", "http://cloud-session.invalid/")
        response = httpx.Response(
            401,
            request=request,
            json={"detail": {"code": "cloud_identity_changed", "message": "Cloud session changed; sign in again"}},
        )
        super().__init__("Cloud session changed; sign in again", request=request, response=response)


class RemoteHistoryIdentityChanged(RuntimeError):
    """The shared board cloud session no longer belongs to the captured owner."""


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
        self._identity_generation = 0
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            trust_env=False,
        )

    # ── Token Management ──

    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None, user_id=None):
        self._identity_generation += 1
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._auth_required = False
        # login and box-sso both install tokens first and then bind the local
        # shadow user. Never carry the previous account's binding into that gap.
        self._bound_user_id = None if user_id is None else str(user_id)

    def set_refresh_token(self, refresh_token: str):
        self._identity_generation += 1
        self._bound_user_id = None
        self._access_token = None
        self._refresh_token = refresh_token
        self._auth_required = False

    def bind_user(self, user_id) -> None:
        """Say which local user the current cloud session speaks for."""
        self._identity_generation += 1
        self._bound_user_id = None if user_id is None else str(user_id)

    @property
    def bound_user_id(self) -> Optional[str]:
        return self._bound_user_id

    def clear_tokens(self):
        """Clear all tokens and mark auth as required (used on logout)."""
        self._identity_generation += 1
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

    def cloud_session_is(self, user_id) -> bool:
        """A token without an explicit matching local binding proves no owner."""
        return (
            user_id is not None
            and self._bound_user_id is not None
            and str(user_id) == self._bound_user_id
            and self.is_authenticated
        )

    def _check_history_owner(self, user_id, generation):
        if not self.cloud_session_is(user_id) or self._identity_generation != generation:
            raise RemoteHistoryIdentityChanged("Cloud history identity changed")

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"X-StellaBox-Device-ID": self.device_id}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _refresh_access_token(self) -> bool:
        """Attempt to refresh the access token. Returns True on success."""
        refresh_token, bound_user_id, generation = (
            self._refresh_token,
            self._bound_user_id,
            self._identity_generation,
        )
        if not refresh_token:
            return False
        try:
            resp = await self._client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            if resp.status_code == 200:
                if (self._refresh_token, self._bound_user_id, self._identity_generation) != (
                    refresh_token,
                    bound_user_id,
                    generation,
                ):
                    return False
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
        history_owner=None,
        history_generation=None,
    ) -> httpx.Response:
        """Make an HTTP request with automatic token refresh on 401."""
        if history_owner is not None:
            self._check_history_owner(history_owner, history_generation)
        session = (self._refresh_token, self._bound_user_id, self._identity_generation)
        headers = self._auth_headers() if auth else {}
        resp = await self._client.request(method, path, json=json, params=params, headers=headers)

        if history_owner is not None:
            self._check_history_owner(history_owner, history_generation)

        if resp.status_code == 401 and auth and session[0]:
            if (self._refresh_token, self._bound_user_id, self._identity_generation) != session:
                return resp
            refreshed = await self._refresh_access_token()
            if history_owner is not None:
                self._check_history_owner(history_owner, history_generation)
            if (self._refresh_token, self._bound_user_id, self._identity_generation) != session:
                return resp
            if refreshed:
                headers = self._auth_headers()
                resp = await self._client.request(method, path, json=json, params=params, headers=headers)
            else:
                self._auth_required = True
                logger.warning("Auth required: both access and refresh tokens invalid")

        if history_owner is not None:
            self._check_history_owner(history_owner, history_generation)
        return resp

    async def _history_json(self, user_id, method, path, **kwargs):
        generation = self._identity_generation
        self._check_history_owner(user_id, generation)
        response = await self._request(method, path, history_owner=user_id, history_generation=generation, **kwargs)
        self._check_history_owner(user_id, generation)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as exc:
            raise httpx.DecodingError("Malformed cloud history response", request=response.request) from exc

    async def baipu_history_list(self, user_id, limit=30):
        return await self._history_json(user_id, "GET", "/api/v1/baipu/history", params={"limit": limit})

    async def baipu_history_get(self, user_id, record_id):
        return await self._history_json(user_id, "GET", f"/api/v1/baipu/history/{record_id}")

    async def baipu_history_sync(self, user_id, record_id, data):
        return await self._history_json(user_id, "PUT", f"/api/v1/baipu/history/{record_id}/sync", json=data)

    def _assert_cloud_identity(self, identity: _CloudIdentity) -> None:
        if (self._bound_user_id, self._identity_generation) != (identity.user_id, identity.generation):
            raise CloudIdentityChangedError()

    async def _identity_bound_refresh(self, identity: _CloudIdentity) -> bool:
        """Refresh only this session; outages stay retryable rather than logging it out."""
        self._assert_cloud_identity(identity)
        if not identity.refresh_token:
            return False
        try:
            response = await self._client.post("/api/v1/auth/refresh", json={"refresh_token": identity.refresh_token})
        except httpx.TransportError:
            self._assert_cloud_identity(identity)
            raise
        self._assert_cloud_identity(identity)
        if response.status_code >= 500:
            response.raise_for_status()
        if response.status_code != 200:
            return False
        access_token = response.json()["access_token"]
        self._assert_cloud_identity(identity)
        self._access_token = access_token
        self._auth_required = False
        return True

    async def _identity_bound_request(self, method: str, path: str, *, expected_user_id, json=None) -> Any:
        if not self.is_authenticated or self._bound_user_id is None or self._bound_user_id != str(expected_user_id):
            raise CloudIdentityChangedError()
        identity = _CloudIdentity(
            self._bound_user_id, self._identity_generation, self._access_token, self._refresh_token
        )

        async def send(access_token):
            # No mutable singleton token reads after the snapshot check. A request
            # already sent with A's bearer may finish for A, but can never become B's.
            self._assert_cloud_identity(identity)
            try:
                response = await self._client.request(
                    method,
                    path,
                    json=json,
                    headers={
                        "X-StellaBox-Device-ID": self.device_id,
                        "Authorization": f"Bearer {access_token}",
                    },
                )
            except httpx.TransportError:
                self._assert_cloud_identity(identity)
                raise
            self._assert_cloud_identity(identity)
            return response

        response = await send(identity.access_token)
        if response.status_code == 401 and identity.refresh_token:
            refreshed = await self._identity_bound_refresh(identity)
            self._assert_cloud_identity(identity)
            if refreshed:
                response = await send(self._access_token)
            else:
                self._auth_required = True
        self._assert_cloud_identity(identity)
        response.raise_for_status()
        result = response.json()
        self._assert_cloud_identity(identity)
        return result

    # ── Membership and paid analysis (cloud authority only) ──

    async def billing_catalog(self, *, expected_user_id) -> Dict:
        return await self._identity_bound_request("GET", "/api/v1/billing/catalog", expected_user_id=expected_user_id)

    async def billing_usage(self, *, expected_user_id) -> Dict:
        return await self._identity_bound_request("GET", "/api/v1/billing/usage", expected_user_id=expected_user_id)

    async def billing_quote(self, data: Dict, *, expected_user_id) -> Dict:
        return await self._identity_bound_request(
            "POST", "/api/v1/billing/quotes", json=data, expected_user_id=expected_user_id
        )

    async def billing_create_order(self, data: Dict, *, expected_user_id) -> Dict:
        return await self._identity_bound_request(
            "POST", "/api/v1/billing/orders", json=data, expected_user_id=expected_user_id
        )

    async def billing_list_orders(self, *, expected_user_id) -> Dict:
        return await self._identity_bound_request("GET", "/api/v1/billing/orders", expected_user_id=expected_user_id)

    async def billing_get_order(self, order_id: str, *, expected_user_id) -> Dict:
        return await self._identity_bound_request(
            "GET", f"/api/v1/billing/orders/{order_id}", expected_user_id=expected_user_id
        )

    async def paid_position(self, data: Dict, *, expected_user_id) -> Dict:
        return await self._identity_bound_request(
            "POST", "/api/v1/analysis/positions", json=data, expected_user_id=expected_user_id
        )

    async def paid_position_get(self, position_id: str, *, expected_user_id) -> Dict:
        return await self._identity_bound_request(
            "GET", f"/api/v1/analysis/positions/{position_id}", expected_user_id=expected_user_id
        )

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

    async def get_kifu(self, album_id: int, lang: str = "cn") -> Dict:
        resp = await self._request("GET", f"/api/v1/kifu/albums/{album_id}", params={"lang": lang})
        resp.raise_for_status()
        return resp.json()

    async def get_kifu_analysis(self, album_id: int) -> Dict:
        resp = await self._request("GET", f"/api/v1/kifu/albums/{album_id}/analysis")
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

    async def send_ai_ladder_heartbeat(self, game_id: str, reservation_key: str) -> Dict:
        resp = await self._request(
            "POST",
            f"/api/v1/ai-ladder/games/{game_id}/heartbeat",
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

    async def count_ai_ladder_game(self, game_id: str, reservation_key: str, sgf_content: str, trigger: str) -> Dict:
        resp = await self._request(
            "POST", f"/api/v1/ai-ladder/games/{game_id}/count",
            json={"reservation_key": reservation_key, "sgf_content": sgf_content, "trigger": trigger},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_ai_ladder_territory(self, game_id: str) -> Dict:
        resp = await self._request("GET", f"/api/v1/ai-ladder/games/{game_id}/territory")
        resp.raise_for_status()
        return resp.json()

    async def request_ai_ladder_territory(
        self, game_id: str, reservation_key: str, sgf_content: str, request_id: str
    ) -> Dict:
        resp = await self._request(
            "POST", f"/api/v1/ai-ladder/games/{game_id}/territory",
            json={"reservation_key": reservation_key, "sgf_content": sgf_content, "request_id": request_id},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Growth (box asks the cloud; falls back to its own cache) ──

    async def get_growth_summary(self, days: int) -> Dict:
        resp = await self._request("GET", "/api/v1/growth/summary", params={"days": days})
        resp.raise_for_status()
        return resp.json()

    async def get_growth_diagnosis(self, days: int, reports: int) -> Dict:
        resp = await self._request("GET", "/api/v1/growth/diagnosis", params={"days": days, "reports": reports})
        resp.raise_for_status()
        return resp.json()

    async def get_growth_activity(self, days: int, tz_offset: int) -> Dict:
        resp = await self._request("GET", "/api/v1/growth/activity", params={"days": days, "tz_offset": tz_offset})
        resp.raise_for_status()
        return resp.json()

    # ── Reports (remote-only in board mode) ──

    async def list_reports(self, *, expected_user_id=None) -> List[Dict]:
        if expected_user_id is not None:
            return await self._identity_bound_request("GET", "/api/v1/reports/", expected_user_id=expected_user_id)
        resp = await self._request("GET", "/api/v1/reports/")
        resp.raise_for_status()
        return resp.json()

    async def get_report_summary(self, *, expected_user_id=None) -> Dict:
        if expected_user_id is not None:
            return await self._identity_bound_request(
                "GET", "/api/v1/reports/summary", expected_user_id=expected_user_id
            )
        resp = await self._request("GET", "/api/v1/reports/summary")
        resp.raise_for_status()
        return resp.json()

    async def get_report(self, task_id: int, *, expected_user_id=None) -> Dict:
        if expected_user_id is not None:
            return await self._identity_bound_request(
                "GET", f"/api/v1/reports/{task_id}", expected_user_id=expected_user_id
            )
        resp = await self._request("GET", f"/api/v1/reports/{task_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_report(self, data: Dict, *, expected_user_id=None) -> Dict:
        if expected_user_id is not None:
            return await self._identity_bound_request(
                "POST", "/api/v1/reports/", json=data, expected_user_id=expected_user_id
            )
        resp = await self._request("POST", "/api/v1/reports/", json=data)
        resp.raise_for_status()
        return resp.json()

    async def retry_report(self, task_id: int, data: Optional[Dict] = None, *, expected_user_id=None) -> Dict:
        if expected_user_id is not None:
            return await self._identity_bound_request(
                "POST", f"/api/v1/reports/{task_id}/retry", json=data, expected_user_id=expected_user_id
            )
        kwargs = {} if data is None else {"json": data}
        resp = await self._request("POST", f"/api/v1/reports/{task_id}/retry", **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def get_report_moves(self, task_id: int, *, expected_user_id=None) -> List[Dict]:
        if expected_user_id is not None:
            return await self._identity_bound_request(
                "GET", f"/api/v1/reports/{task_id}/moves", expected_user_id=expected_user_id
            )
        resp = await self._request("GET", f"/api/v1/reports/{task_id}/moves")
        resp.raise_for_status()
        return resp.json()

    # ── Tutorial (read-only, public) ──

    async def get_ogs_course(self, lang: str = "zh-cn") -> Any:
        resp = await self._request("GET", "/api/v1/tutorials/ogs-course", params={"lang": lang}, auth=False)
        resp.raise_for_status()
        return resp.json()

    async def get_ogs_step(self, page: int, lang: str = "zh-cn") -> Any:
        resp = await self._request(
            "GET", f"/api/v1/tutorials/ogs-course/steps/{page}", params={"lang": lang}, auth=False
        )
        resp.raise_for_status()
        return resp.json()

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
