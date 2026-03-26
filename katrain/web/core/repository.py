"""Repository Protocol + Dispatcher for board/server mode abstraction.

See design.md Section 4.8 for the architecture.

Server mode: endpoints use LocalRepository (direct SQLAlchemy) — unchanged.
Board mode:  endpoints use RepositoryDispatcher which routes to Remote (online)
             or Local (offline) + sync_queue.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from katrain.web.core.remote_client import RemoteAPIClient

logger = logging.getLogger("katrain_web")


# ── Protocol Definitions ──


@runtime_checkable
class TsumegoRepositoryProtocol(Protocol):
    """Interface for tsumego data access."""

    def get_levels(self, db: Any) -> List[Any]: ...
    def get_categories(self, db: Any, level: str) -> List[Any]: ...
    def get_problems(self, db: Any, level: str, category: str, offset: int, limit: int) -> List[Any]: ...
    def get_problem(self, db: Any, problem_id: str) -> Any: ...
    def get_progress(self, db: Any, user_id: int) -> Dict: ...
    def update_progress(self, db: Any, user_id: int, problem_id: str, data: Dict) -> Dict: ...


@runtime_checkable
class KifuRepositoryProtocol(Protocol):
    """Interface for kifu album data access."""

    def list_albums(self, db: Any, q: Optional[str], page: int, page_size: int) -> Dict: ...
    def get_album(self, db: Any, album_id: int) -> Any: ...


@runtime_checkable
class UserGameRepositoryProtocol(Protocol):
    """Interface for user game data access."""

    def list_games(self, user_id: int, **params) -> Dict: ...
    def create_game(self, user_id: int, data: Dict) -> Dict: ...
    def get_game(self, game_id: str, user_id: int) -> Optional[Dict]: ...


# ── Remote Implementations (board mode, online) ──


class RemoteTsumegoRepository:
    """Tsumego data access via remote API."""

    def __init__(self, client: RemoteAPIClient):
        self._client = client

    async def get_levels(self) -> List[Dict]:
        return await self._client.get_levels()

    async def get_problems(self, level: str, category: str, offset: int = 0, limit: int = 20) -> List[Dict]:
        return await self._client.get_problems(level, category, offset, limit)

    async def get_problem(self, problem_id: str) -> Dict:
        return await self._client.get_problem(problem_id)

    async def get_progress(self) -> Dict:
        return await self._client.get_progress()

    async def update_progress(self, problem_id: str, data: Dict) -> Dict:
        return await self._client.update_progress(problem_id, data)


class RemoteKifuRepository:
    """Kifu data access via remote API."""

    def __init__(self, client: RemoteAPIClient):
        self._client = client

    async def list_albums(self, q: Optional[str] = None, page: int = 1, page_size: int = 20) -> Dict:
        params = {"page": page, "page_size": page_size}
        if q:
            params["q"] = q
        return await self._client.search_kifu(**params)

    async def get_album(self, album_id: int) -> Dict:
        return await self._client.get_kifu(album_id)


class RemoteUserGameRepository:
    """User game data access via remote API."""

    def __init__(self, client: RemoteAPIClient):
        self._client = client

    async def list_games(self, **params) -> Dict:
        return await self._client.list_user_games(**params)

    async def create_game(self, data: Dict) -> Dict:
        return await self._client.create_user_game(data)

    async def get_game(self, game_id: str) -> Dict:
        return await self._client.get_user_game(game_id)


# ── Dispatcher (board mode, routes online/offline) ──


class RepositoryDispatcher:
    """Routes data access to remote (online) or local (offline) repositories.

    See design.md Section 4.8 for the routing logic.
    """

    def __init__(
        self,
        connectivity_manager,
        remote_tsumego: RemoteTsumegoRepository,
        remote_kifu: RemoteKifuRepository,
        remote_user_games: RemoteUserGameRepository,
        local_user_game_repo,
        sync_enqueue_fn=None,
    ):
        self._connectivity = connectivity_manager
        self.remote_tsumego = remote_tsumego
        self.remote_kifu = remote_kifu
        self.remote_user_games = remote_user_games
        self._local_user_game_repo = local_user_game_repo
        self._sync_enqueue = sync_enqueue_fn

    @property
    def is_online(self) -> bool:
        return self._connectivity.is_online

    # ── Tsumego (online-only, offline = unavailable) ──

    async def tsumego_get_levels(self):
        if not self.is_online:
            return []
        return await self.remote_tsumego.get_levels()

    async def tsumego_get_problems(self, level, category, offset=0, limit=20):
        if not self.is_online:
            return []
        return await self.remote_tsumego.get_problems(level, category, offset, limit)

    async def tsumego_get_problem(self, problem_id):
        if not self.is_online:
            return None
        return await self.remote_tsumego.get_problem(problem_id)

    # ── Kifu (online-only, offline = unavailable) ──

    async def kifu_list_albums(self, q=None, page=1, page_size=20):
        if not self.is_online:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        return await self.remote_kifu.list_albums(q, page, page_size)

    async def kifu_get_album(self, album_id):
        if not self.is_online:
            return None
        return await self.remote_kifu.get_album(album_id)

    # ── User Games (online→remote, offline→local+sync) ──

    async def user_games_create(self, user_id: int, data: Dict) -> Dict:
        if self.is_online:
            return await self.remote_user_games.create_game(data)
        else:
            # Write to local SQLite
            result = self._local_user_game_repo.create(
                user_id=user_id,
                sgf_content=data.get("sgf_content", ""),
                source=data.get("source", "play_ai"),
                game_id=data.get("id"),
                **{k: v for k, v in data.items() if k not in ("sgf_content", "source", "id")},
            )
            # Enqueue for later sync
            if self._sync_enqueue:
                self._sync_enqueue(
                    operation="create_user_game",
                    endpoint="/api/v1/user-games/",
                    method="POST",
                    payload=data,
                    user_id=str(user_id),
                )
            return result

    async def user_games_list(self, user_id: int, **params) -> Dict:
        if self.is_online:
            return await self.remote_user_games.list_games(**params)
        else:
            return self._local_user_game_repo.list(user_id=user_id, **params)

    async def user_games_get(self, game_id: str, user_id: int):
        if self.is_online:
            return await self.remote_user_games.get_game(game_id)
        else:
            return self._local_user_game_repo.get(game_id, user_id)


def enqueue_sync_item(session_factory, operation: str, endpoint: str, method: str, payload: Dict, user_id: str = None, device_id: str = None):
    """Helper to insert a sync queue entry."""
    from katrain.web.core.models_db import SyncQueueEntry

    db = session_factory()
    try:
        entry = SyncQueueEntry(
            idempotency_key=uuid.uuid4().hex,
            operation=operation,
            endpoint=endpoint,
            method=method,
            payload=payload,
            status="pending",
            user_id=user_id,
            device_id=device_id,
        )
        db.add(entry)
        db.commit()
        logger.debug(f"Enqueued sync: {operation} → {endpoint}")
    finally:
        db.close()
