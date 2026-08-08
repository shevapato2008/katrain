"""Repository Protocol + Dispatcher for board/server mode abstraction.

See design.md Section 4.8 for the architecture.

Server mode: endpoints use LocalRepository (direct SQLAlchemy) — unchanged.
Board mode:  endpoints use RepositoryDispatcher which routes to Remote (online)
             or Local (offline) + sync_queue.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import httpx

from katrain.web.core.remote_client import RemoteAPIClient

logger = logging.getLogger("katrain_web")


class RemoteServiceUnavailableError(RuntimeError):
    """A board-mode remote-only operation can be retried when online."""


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

    async def get_all_problems(self, level: str, page: int = 1, page_size: int = 50) -> Dict:
        """Aggregate problems across categories using existing remote endpoints.

        The remote server may not have the /levels/{level}/problems endpoint,
        so we build the paginated response from get_levels + get_problems.
        """
        # Step 1: get categories for this level from the levels list
        levels = await self._client.get_levels()
        categories: Dict[str, int] = {}
        for lvl in levels:
            if lvl.get("level", "").lower() == level.lower():
                categories = lvl.get("categories", {})
                break

        if not categories:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

        total = sum(categories.values())

        # Step 2: fetch problems from each category in parallel (slim fields only)
        async def fetch_category(cat: str, count: int) -> List[Dict]:
            raw = await self._client.get_problems(level, cat, offset=0, limit=count)
            return [{"id": p["id"], "category": p.get("category", cat), "hint": p.get("hint", "")} for p in raw]

        results = await asyncio.gather(
            *(fetch_category(cat, cnt) for cat, cnt in categories.items()),
            return_exceptions=True,
        )

        all_problems: List[Dict] = []
        for result in results:
            if isinstance(result, list):
                all_problems.extend(result)

        # Step 3: paginate
        start = (page - 1) * page_size
        page_items = all_problems[start : start + page_size]

        return {"items": page_items, "total": total, "page": page, "page_size": page_size}

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
        local_tsumego_progress_repo=None,
        remote_client: Optional[RemoteAPIClient] = None,
    ):
        self._connectivity = connectivity_manager
        self.remote_tsumego = remote_tsumego
        self.remote_kifu = remote_kifu
        self.remote_user_games = remote_user_games
        self._local_user_game_repo = local_user_game_repo
        self._sync_enqueue = sync_enqueue_fn
        self._local_tsumego_progress_repo = local_tsumego_progress_repo
        self._remote_client = remote_client

    @property
    def is_online(self) -> bool:
        return self._connectivity.is_online

    # ── Tsumego (online-only, offline = unavailable) ──

    async def tsumego_get_levels(self):
        if not self.is_online:
            return []
        try:
            return await self.remote_tsumego.get_levels()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("tsumego_get_levels remote failed: %s", e)
            return []

    async def tsumego_get_all_problems(self, level, page=1, page_size=50):
        if not self.is_online:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        try:
            return await self.remote_tsumego.get_all_problems(level, page, page_size)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("tsumego_get_all_problems remote failed: %s", e)
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    async def tsumego_get_problems(self, level, category, offset=0, limit=20):
        if not self.is_online:
            return []
        try:
            return await self.remote_tsumego.get_problems(level, category, offset, limit)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("tsumego_get_problems remote failed: %s", e)
            return []

    async def tsumego_get_problem(self, problem_id):
        if not self.is_online:
            return None
        try:
            return await self.remote_tsumego.get_problem(problem_id)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("tsumego_get_problem remote failed: %s", e)
            return None

    # ── Tsumego progress (online→remote, offline→local+sync) ──

    async def tsumego_update_progress(self, user_id: int, problem_id: str, data: Dict) -> Dict:
        if self.is_online:
            try:
                return await self.remote_tsumego.update_progress(problem_id, data)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("tsumego_update_progress remote failed, falling back to local: %s", e)
        # Offline or remote failed — write locally + enqueue for later sync
        result = self._local_tsumego_progress_repo.upsert(user_id, problem_id, data)
        if self._sync_enqueue:
            self._sync_enqueue(
                operation="update_tsumego_progress",
                endpoint=f"/api/v1/tsumego/progress/{problem_id}",
                method="POST",
                payload=data,
                user_id=str(user_id),
                coalesce_on_endpoint=True,  # per-problem dedup (endpoint contains problem_id)
            )
        return result

    async def tsumego_get_progress_local(self, user_id: int) -> Dict:
        return self._local_tsumego_progress_repo.list(user_id)

    # ── Kifu (online-only, offline = unavailable) ──

    async def kifu_list_albums(self, q=None, page=1, page_size=20):
        if not self.is_online:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        try:
            return await self.remote_kifu.list_albums(q, page, page_size)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("kifu_list_albums remote failed: %s", e)
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    async def kifu_get_album(self, album_id):
        if not self.is_online:
            return None
        try:
            return await self.remote_kifu.get_album(album_id)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("kifu_get_album remote failed: %s", e)
            return None

    # ── User Games (online→remote, offline→local+sync) ──

    async def user_games_create(self, user_id: int, data: Dict) -> Dict:
        if self.is_online:
            try:
                return await self.remote_user_games.create_game(data)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_create remote failed, falling back to local: %s", e)
        # Offline or remote failed — write locally
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
            try:
                return await self.remote_user_games.list_games(**params)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_list remote failed, falling back to local: %s", e)
        return self._local_user_game_repo.list(user_id=user_id, **params)

    async def user_games_get(self, game_id: str, user_id: int):
        if self.is_online:
            try:
                return await self.remote_user_games.get_game(game_id)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_get remote failed, falling back to local: %s", e)
        return self._local_user_game_repo.get(game_id, user_id)

    # ── Remote-only operations ──

    async def _remote_only(self, call, unavailable_detail: str = "Remote server unavailable"):
        if not self.is_online or self._remote_client is None:
            raise RemoteServiceUnavailableError(unavailable_detail)
        try:
            return await call()
        except httpx.TransportError as exc:
            logger.warning("Remote-only operation unavailable: %s", exc)
            raise RemoteServiceUnavailableError(unavailable_detail) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                logger.warning("Remote-only operation failed upstream: %s", exc)
                raise RemoteServiceUnavailableError(unavailable_detail) from exc
            raise

    async def user_games_delete(self, game_id: str):
        return await self._remote_only(lambda: self._remote_client.delete_user_game(game_id))

    async def reports_list(self):
        return await self._remote_only(lambda: self._remote_client.list_reports(), "Remote report service unavailable")

    async def reports_summary(self):
        return await self._remote_only(
            lambda: self._remote_client.get_report_summary(), "Remote report service unavailable"
        )

    async def reports_get(self, task_id: int):
        return await self._remote_only(
            lambda: self._remote_client.get_report(task_id), "Remote report service unavailable"
        )

    async def reports_create(self, data: Dict):
        return await self._remote_only(
            lambda: self._remote_client.create_report(data), "Remote report service unavailable"
        )

    async def reports_retry(self, task_id: int):
        return await self._remote_only(
            lambda: self._remote_client.retry_report(task_id), "Remote report service unavailable"
        )

    async def reports_moves(self, task_id: int):
        return await self._remote_only(
            lambda: self._remote_client.get_report_moves(task_id), "Remote report service unavailable"
        )


def enqueue_sync_item(
    session_factory,
    operation: str,
    endpoint: str,
    method: str,
    payload: Dict,
    user_id: str = None,
    device_id: str = None,
    coalesce_on_endpoint: bool = False,
    idempotency_key: str = None,
):
    """Helper to insert a sync queue entry.

    If ``coalesce_on_endpoint`` is True, any existing *pending* rows for the
    same endpoint are deleted before inserting the new one. The endpoint embeds
    a unique key (e.g. problem_id), so this collapses repeated updates of the
    same resource to a single latest-wins entry. Latest-wins is safe because
    progress fields are monotonic (completed via OR at both local upsert and
    remote merge; attempts via max).

    ``idempotency_key`` defaults to a random uuid, which identifies the ATTEMPT and
    nothing else. Pass a key derived from the thing being synced when re-enqueueing the
    same fact must not create a second one (the column is unique, so the duplicate
    insert is rejected here rather than discovered on the server).
    """
    from katrain.web.core.models_db import SyncQueueEntry
    from sqlalchemy.exc import IntegrityError

    db = session_factory()
    try:
        if coalesce_on_endpoint:
            dedup_q = db.query(SyncQueueEntry).filter(
                SyncQueueEntry.endpoint == endpoint,
                SyncQueueEntry.status == "pending",
            )
            # Scope dedup to the same user so a board with sequential multi-user
            # sessions never drops another user's pending progress for the same problem.
            if user_id is not None:
                dedup_q = dedup_q.filter(SyncQueueEntry.user_id == user_id)
            dedup_q.delete(synchronize_session=False)
        entry = SyncQueueEntry(
            idempotency_key=idempotency_key or uuid.uuid4().hex,
            operation=operation,
            endpoint=endpoint,
            method=method,
            payload=payload,
            status="pending",
            user_id=user_id,
            device_id=device_id,
        )
        db.add(entry)
        try:
            db.commit()
        except IntegrityError:
            # Same fact already queued (or already synced). Enqueueing it twice would
            # hand the server the same event under two names.
            db.rollback()
            logger.info(f"Sync item already queued, not duplicating: {operation} [{idempotency_key}]")
            return True
        logger.debug(f"Enqueued sync: {operation} → {endpoint}")
        return True
    finally:
        db.close()
