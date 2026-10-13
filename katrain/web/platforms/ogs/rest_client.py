"""OGS REST API client.

Handles authentication, user info, player search, challenges, and game data
via the online-go.com HTTP API.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger("katrain_web")

BASE_URL = "https://online-go.com"


class OGSRestClient:
    """HTTP client for OGS REST API."""

    def __init__(self, base_url: str = BASE_URL):
        self._base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self._csrf_token: Optional[str] = None
        self._user_jwt: Optional[str] = None
        self._user_id: Optional[int] = None
        self._username: Optional[str] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "KaTrain-SmartBoard/0.1"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # --- Authentication ---

    async def login(self, username: str, password: str) -> dict:
        """Session login -> fetch JWT from ui/config.

        Returns dict with user_jwt, user_id, username, chat_auth, notification_auth.
        """
        client = await self._ensure_client()

        # Step 1: POST /api/v0/login to establish session
        resp = await client.post("/api/v0/login", json={"username": username, "password": password})
        resp.raise_for_status()

        # Step 2: GET /api/v1/ui/config to fetch JWT and user info
        config = await self.get_ui_config()
        self._user_jwt = config.get("user_jwt")
        self._user_id = config.get("user", {}).get("id")
        self._username = config.get("user", {}).get("username")

        logger.info(f"OGS login successful: {self._username} (id={self._user_id})")
        return config

    async def login_with_token(self, auth_data: dict) -> dict:
        """Restore session from saved auth data (JWT + cookies).

        Returns ui/config dict or raises on failure.
        """
        client = await self._ensure_client()
        # If we have cookies/session data, set them
        if "cookies" in auth_data:
            for name, value in auth_data["cookies"].items():
                client.cookies.set(name, value)

        config = await self.get_ui_config()
        self._user_jwt = config.get("user_jwt")
        self._user_id = config.get("user", {}).get("id")
        self._username = config.get("user", {}).get("username")

        if not self._user_id:
            raise ValueError("Token login failed — not authenticated")
        return config

    async def get_ui_config(self) -> dict:
        """GET /api/v1/ui/config -> user info, JWT, notification/chat auth."""
        client = await self._ensure_client()
        resp = await client.get("/api/v1/ui/config")
        resp.raise_for_status()
        return resp.json()

    def get_auth_data_for_storage(self) -> dict:
        """Export current auth state for encrypted credential storage."""
        cookies = {}
        if self._client:
            for cookie in self._client.cookies.jar:
                cookies[cookie.name] = cookie.value
        return {
            "user_jwt": self._user_jwt,
            "user_id": self._user_id,
            "username": self._username,
            "cookies": cookies,
        }

    @property
    def user_jwt(self) -> Optional[str]:
        return self._user_jwt

    @property
    def user_id(self) -> Optional[int]:
        return self._user_id

    @property
    def username(self) -> Optional[str]:
        return self._username

    @property
    def is_authenticated(self) -> bool:
        return self._user_id is not None

    # --- User info ---

    async def get_me(self) -> dict:
        """GET /api/v1/me/ -> current user profile."""
        client = await self._ensure_client()
        resp = await client.get("/api/v1/me/")
        resp.raise_for_status()
        return resp.json()

    async def get_user(self, user_id: int) -> dict:
        """GET /api/v1/players/{id}/ -> user profile."""
        client = await self._ensure_client()
        resp = await client.get(f"/api/v1/players/{user_id}/")
        resp.raise_for_status()
        return resp.json()

    async def search_players(self, query: str, page_size: int = 20) -> list[dict]:
        """GET /api/v1/players/?username__startswith=query."""
        client = await self._ensure_client()
        resp = await client.get("/api/v1/players/", params={"username__startswith": query, "page_size": page_size})
        resp.raise_for_status()
        return resp.json().get("results", [])

    # --- Games ---

    async def get_active_games(self) -> list[dict]:
        """GET /api/v1/ui/overview -> active games list."""
        client = await self._ensure_client()
        resp = await client.get("/api/v1/ui/overview")
        resp.raise_for_status()
        data = resp.json()
        return data.get("active_games", [])

    async def get_game(self, game_id: int) -> dict:
        """GET /api/v1/games/{id}/ -> game details."""
        client = await self._ensure_client()
        resp = await client.get(f"/api/v1/games/{game_id}/")
        resp.raise_for_status()
        return resp.json()

    async def get_game_sgf(self, game_id: int) -> str:
        """GET /api/v1/games/{id}/sgf -> SGF content."""
        client = await self._ensure_client()
        resp = await client.get(f"/api/v1/games/{game_id}/sgf")
        resp.raise_for_status()
        return resp.text

    # --- Challenges ---

    async def challenge_player(self, player_id: int, settings: dict) -> tuple[int, int]:
        """POST /api/v1/players/{id}/challenge/ -> (challenge_id, game_id)."""
        client = await self._ensure_client()
        csrf = client.cookies.get("csrftoken")
        if not csrf:
            raise RuntimeError("OGS session CSRF token is unavailable")
        default_time = {"system": "byoyomi", "main_time": 600, "period_time": 30, "periods": 5}
        time_control = settings.get("time_control") or default_time
        if not isinstance(time_control, dict) or not isinstance(time_control.get("system"), str):
            raise ValueError("invalid OGS time control")
        time_parameters = {**time_control, "time_control": time_control["system"]}
        time_parameters.setdefault("speed", "live")
        time_parameters.setdefault("pause_on_weekends", False)
        # Build challenge payload
        payload = {
            "initialized": False,
            "min_ranking": -1000,
            "max_ranking": 1000,
            "challenger_color": "automatic",
            "game": {
                "name": "KaTrain Game",
                "rules": settings.get("rules", "chinese"),
                "ranked": settings.get("ranked", True),
                "width": settings.get("board_size", 19),
                "height": settings.get("board_size", 19),
                "handicap": settings.get("handicap", 0),
                "komi_auto": "automatic" if settings.get("komi") is None else "custom",
                "disable_analysis": True,
                "time_control": time_control["system"],
                "time_control_parameters": time_parameters,
                "pause_on_weekends": time_parameters["pause_on_weekends"],
                "private": False,
                "rengo": False,
            },
        }
        if settings.get("komi") is not None:
            payload["game"]["komi"] = settings["komi"]
        resp = await client.post(
            f"/api/v1/players/{player_id}/challenge/", json=payload,
            headers={"X-CSRFToken": csrf, "Referer": f"{self._base_url}/"},
        )
        resp.raise_for_status()
        data = resp.json()
        game = data.get("game")
        return data.get("challenge", data.get("id")), game.get("id") if isinstance(game, dict) else game

    async def accept_challenge(self, challenge_id: int) -> dict:
        """Accept a direct invitation addressed to the logged-in player."""
        client = await self._ensure_client()
        resp = await client.post(f"/api/v1/me/challenges/{challenge_id}/accept")
        resp.raise_for_status()
        return resp.json()

    async def accept_open_challenge(self, challenge_id: int) -> None:
        """Accept a public seek, using OGS's public challenge route.

        The official web client ignores the POST response and navigates using
        the seek's game_id, so callers must retain that id before posting.
        """
        if type(challenge_id) is not int or challenge_id <= 0:
            raise ValueError("invalid OGS challenge id")
        client = await self._ensure_client()
        csrf = client.cookies.get("csrftoken")
        if not csrf:
            raise RuntimeError("OGS session CSRF token is unavailable")
        resp = await client.post(
            f"/api/v1/challenges/{challenge_id}/accept",
            json={},
            headers={"X-CSRFToken": csrf, "Referer": f"{self._base_url}/"},
        )
        resp.raise_for_status()

    async def decline_challenge(self, challenge_id: int) -> None:
        """Cancel an owned invitation through OGS's challenge route."""
        client = await self._ensure_client()
        csrf = client.cookies.get("csrftoken")
        if not csrf:
            raise RuntimeError("OGS session CSRF token is unavailable")
        resp = await client.delete(
            f"/api/v1/me/challenges/{challenge_id}",
            headers={"X-CSRFToken": csrf, "Referer": f"{self._base_url}/"},
        )
        resp.raise_for_status()

    async def get_my_challenges(self) -> list[dict]:
        """GET /api/v1/me/challenges/ -> pending challenges."""
        client = await self._ensure_client()
        resp = await client.get("/api/v1/me/challenges/")
        resp.raise_for_status()
        return resp.json().get("results", [])

    async def get_open_challenges(self, page_size: int = 50) -> list[dict]:
        """GET /api/v1/challenges/ -> open/public challenges (seek graph equivalent)."""
        client = await self._ensure_client()
        resp = await client.get("/api/v1/challenges/", params={"page_size": page_size})
        resp.raise_for_status()
        return resp.json().get("results", [])
