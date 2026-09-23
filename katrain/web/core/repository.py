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


# 盒上题库读取在云端不可用时的说明。前端只认 503 这个状态码,这句只进日志与响应 detail。
TSUMEGO_UNAVAILABLE = "Remote tsumego service unavailable"


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

        # 任一分类取失败就整体失败(N9)。吞掉它会返回一份缺块的列表,而 `total` 仍是全量 ——
        # 「全部题目」页照样画、照样翻页,缺的那一类没人看得出来。
        results = await asyncio.gather(*(fetch_category(cat, cnt) for cat, cnt in categories.items()))

        all_problems: List[Dict] = []
        for result in results:
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

    # ── Tsumego (online-only) ──
    #
    # 盒上题库是**在线直读**的:盒子上不存题,也没有任何同步。所以连不上云端时**不许**回空列表 ——
    # 前端会把空列表说成「这台盒子上还没有题」、把 None → 404 说成「这道题不存在」(N9)。
    # 走 `_remote_only`:离线 / 传输失败 / 云端 5xx ⇒ RemoteServiceUnavailableError(端点翻成 503);
    # 云端 4xx 原样抛(端点转回同一个状态码)。

    async def tsumego_get_levels(self):
        return await self._remote_only(lambda: self.remote_tsumego.get_levels(), TSUMEGO_UNAVAILABLE)

    async def tsumego_get_all_problems(self, level, page=1, page_size=50):
        return await self._remote_only(
            lambda: self.remote_tsumego.get_all_problems(level, page, page_size), TSUMEGO_UNAVAILABLE
        )

    async def tsumego_get_problems(self, level, category, offset=0, limit=20):
        return await self._remote_only(
            lambda: self.remote_tsumego.get_problems(level, category, offset, limit), TSUMEGO_UNAVAILABLE
        )

    async def tsumego_get_problem(self, problem_id):
        return await self._remote_only(lambda: self.remote_tsumego.get_problem(problem_id), TSUMEGO_UNAVAILABLE)

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

    # ── Kifu (online-only: offline / cloud failure = 503, never an empty library) ──
    #
    # 棋谱库只在云端,盒上没有本地副本。以前这两条离线回空列表 / None,端点就把「连不上」
    # 说成了「没搜到 / 没有这一局」,屏 15 写「没有对得上的谱 · 换棋手名再试」。
    # 远端 404 照旧是 404:`_remote_only` 只把离线、传输错误和 5xx 收成不可用。

    async def kifu_list_albums(self, q=None, page=1, page_size=20):
        return await self._remote_only(
            lambda: self.remote_kifu.list_albums(q, page, page_size), "Remote kifu service unavailable"
        )

    async def kifu_get_album(self, album_id):
        return await self._remote_only(lambda: self.remote_kifu.get_album(album_id), "Remote kifu service unavailable")

    # ── User Games (online→remote, offline→local+sync) ──

    async def user_games_create(self, user_id: int, data: Dict) -> Dict:
        # The cloud attributes this POST to its bearer. If the shared box is
        # currently signed in as somebody else, keep the owner's game local and
        # queue it until their cloud session is active.
        bound = getattr(self._remote_client, "bound_user_id", None)
        if self.is_online and (bound is None or str(bound) == str(user_id)):
            try:
                return await self.remote_user_games.create_game(data)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_create remote failed, falling back to local: %s", e)
        elif self.is_online:
            logger.info("user_games_create: cloud session is user %s, keeping user %s's game local", bound, user_id)
        # Offline, remote failed, or another user's cloud session is active.
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
        """列表带上 `authority` —— **这个数是谁数的**。

        在线时这一份来自云端,`total` 是**跨设备**的总数;离线时才是本机那一份。
        两者在屏上长得一模一样,而复盘屏那句标签写死着「本机 N 局」
        —— 联网时它说的是假话(数其实来自云端),断网时才碰巧是真的。
        口径和 `growth/summary` 的 `authority` 一致,三档同名。
        """
        if self.is_online:
            try:
                remote = await self.remote_user_games.list_games(**params)
                if isinstance(remote, dict):
                    return {**remote, "authority": "cloud"}
                return remote
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_list remote failed, falling back to local: %s", e)
        local = self._local_user_game_repo.list(user_id=user_id, **params)
        return {**local, "authority": "local_cache"} if isinstance(local, dict) else local

    async def user_games_get(self, game_id: str, user_id: int):
        if self.is_online:
            try:
                return await self.remote_user_games.get_game(game_id)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning("user_games_get remote failed, falling back to local: %s", e)
        return self._local_user_game_repo.get(game_id, user_id)

    # ── Growth (跨设备的总数在云端;拿不到就退回本机缓存,**并说清是缓存**) ──

    async def growth_summary_remote(self, days: int, user_id) -> tuple[dict | None, str]:
        """→ `(云端那份汇总, "cloud")`,或 `(None, 退回本机的原因)`。

        **不抛。** 这个端点的降级是「换一个数据源」,不是「这次请求失败了」——
        调用方拿到 `None` 之后会自己数本机的,并把 `authority` 标成 `local_cache`。
        ⚠️ 退回**不是静默的**:屏上那句「本机记录」就是它的出口。
        这里只负责把**为什么退**记进日志,四种原因各写各的 ——
        「盒子没联网」和「云端少了这个端点」在运维那儿是两件完全不同的事,
        而它们在用户屏上长得一模一样(都是「本机记录」)。
        """
        return await self._cloud_first(
            "growth summary", "/growth/summary", lambda: self._remote_client.get_growth_summary(days), user_id=user_id
        )

    async def growth_diagnosis_remote(self, days: int, reports: int, user_id) -> tuple[dict | None, str]:
        """能力诊断,口径同 `growth_summary_remote`。盒子上报告在云端、本机库里没有逐手数据,
        所以退回本机时的「0 份报告」说的是「没连上云端」—— 屏上据 `local_cache` 这样说。"""
        return await self._cloud_first(
            "growth diagnosis",
            "/growth/diagnosis",
            lambda: self._remote_client.get_growth_diagnosis(days, reports),
            user_id=user_id,
        )

    async def growth_activity_remote(self, days: int, tz_offset: int, user_id) -> tuple[dict | None, str]:
        """练棋日历,口径同 `growth_summary_remote`。`tz_offset` 原样带给云端 —— 按盒子这边的「今天」切天。"""
        return await self._cloud_first(
            "growth activity",
            "/growth/activity",
            lambda: self._remote_client.get_growth_activity(days, tz_offset),
            user_id=user_id,
        )

    def cloud_session_is(self, user_id) -> bool:
        """云端会话此刻说的是不是**这个**本机用户?

        盒子是共用设备:`RemoteAPIClient` 是进程级单例,只揣着**最后一次登录**那个人的 token
        (`auth.py` 的 box-sso bootstrap 里 `bind_user(shadow_user["id"])` 绑的就是本机影子用户 id)。
        所以「问云端」这件事必须先问一句「云端认的是谁」—— 否则甲的页面会显示乙的账。
        同一判断在 `user_games_create`、`sync_worker`、`ai-ladder/status` 都有,这里是第四处。

        **绑不上就当不是**(没 bind 过 = 证明不了这份 token 属于谁)。非严格盒端会从磁盘恢复
        refresh token 而不 bind,那份 token 的主人未必是屏前这个人。
        """
        bound = getattr(self._remote_client, "bound_user_id", None)
        return bound is not None and str(bound) == str(user_id)

    async def _cloud_first(self, label: str, path: str, call, *, user_id) -> tuple[dict | None, str]:
        """成长屏那几块的「先问云端」:`(payload, "cloud")` 或 `(None, 原因)`,**不抛**。"""
        if self._remote_client is None:
            return None, "no_remote_client"
        if not self.is_online:
            return None, "offline"
        if not self.cloud_session_is(user_id):
            # 退回本机是**正确的降级**,不是错误:屏上那句「本机记录」就是它的出口。
            # 报 401 会让屏上写「读不到」,而本机明明有这个人自己的数。
            logger.warning(
                "%s: cloud session belongs to user %s, not %s — using local cache",
                label,
                getattr(self._remote_client, "bound_user_id", None),
                user_id,
            )
            return None, "remote_other_user"
        try:
            payload = await call()
        except httpx.TransportError as exc:
            logger.warning("%s: cloud unreachable, using local cache (%s)", label, exc)
            return None, "remote_unreachable"
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                # 云端是**旧版本**,没有这个端点 —— 部署歪了,不是坏了。
                logger.warning("%s: cloud has no %s (404) — deploy skew?", label, path)
                return None, "remote_missing_endpoint"
            if status >= 500:
                logger.warning("%s: cloud failed with %s, using local cache", label, status)
                return None, "remote_error"
            logger.warning("%s: cloud refused with %s (credentials?), using local cache", label, status)
            return None, "remote_refused"
        if not isinstance(payload, dict):
            logger.warning("%s: cloud answered 200 with a non-object body", label)
            return None, "remote_bad_payload"
        return payload, "cloud"

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
