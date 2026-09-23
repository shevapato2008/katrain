"""星阵扫码登录 —— 五步链。

## 为什么二维码在本地画

星阵**没有**「给我一张二维码图片」的接口。`GET /api/auth/scan/code` 只给一个 uuid,
真正要编进码里的是字符串 `golaxy_url&&&<uuid>`。所以后端只负责 uuid 和状态,
画码是前端的事(Task 6b/前端半边)。

## 为什么状态要有 UNKNOWN 这一档

把没见过的码映射成「还在等」,会让用户对着一个永远不动的二维码等下去 ——
坏了和好着在用户那里长得一模一样(R-32)。不认识就说不认识。

## 为什么服务端要有一张 `ScanSession` 表,而不是把星阵的 uuid 直接转发给前端

这条链上唯一的串联物(uuid)不带身份。盒子中途换人时,`poll`/`confirm` 各自
只判「这次请求的调用者是谁」——如果不额外钉住「谁发起的」,用户 2 就能拿着
用户 1 扫出来的码去 confirm,凭据会落到用户 2 头上(R-28,task-6a-brief.md)。
"""

from __future__ import annotations

import asyncio
import time
import uuid as _uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx

from katrain.web.platforms.golaxy.adapter import GOLAXY_API_BASE  # adapter.py:69 = "https://api.19x19.com"

QR_PREFIX = "golaxy_url&&&"

# 会话在服务端存活多久(秒)。扫码登录整条链按秒计,不需要更长;盒子重启即丢
# (内存表,不持久化——一次没扫完的登录不值得跨重启保留)。
DEFAULT_SCAN_TTL_SECONDS = 300.0


class ScanState(str, Enum):
    WAITING = "waiting"  # 0
    SCANNED = "scanned"  # 1 手机扫到了,还没点确认
    CONFIRMED = "confirmed"  # 2 可以换 token 了
    EXPIRED = "expired"  # 6016
    CANCELLED = "cancelled"  # 6019
    UNKNOWN = "unknown"  # 星阵加了新码,我们没见过


_STATES = {
    0: ScanState.WAITING,
    1: ScanState.SCANNED,
    2: ScanState.CONFIRMED,
    6016: ScanState.EXPIRED,
    6019: ScanState.CANCELLED,
}


@dataclass(frozen=True)
class ScanStart:
    uuid: str
    payload: str


class GolaxyScanLogin:
    """薄客户端,只管 uuid / 状态 / 昵称三步只读查询(①③⑤)。

    第 ④ 步(拿确认后的 uuid 换 access/refresh token)**不在这里**——它复用
    `adapter.py` 里既有的 token 存储/刷新路径(`GolaxyRestClient.login_scan_code`),
    不另写一份。这个类因此没有 token 状态,每次调用都可以是无状态的一次性对象。
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client

    async def _get(self, path: str, **params) -> dict:
        # ⚠️ **注入进来的 client 不归我们关。** `async with` 一个共享的 AsyncClient
        # 会在第一次调用后把它关掉,后面每一次都 RuntimeError —— 而单测里每个用例
        # 各注一个新的,恰好看不出来。只有自己 new 的那个才由自己关(R-31)。
        owned = self._client is None
        c = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            r = await c.get(f"{GOLAXY_API_BASE}{path}", params=params or None)
            r.raise_for_status()
            body = r.json()
        finally:
            if owned:
                await c.aclose()
        # 200 不等于成功:星阵用字符串 code 报错,存在性不是可用性。
        if str(body.get("code")) != "0":
            raise RuntimeError(body.get("msg") or f"星阵返回 code={body.get('code')}")
        return body

    async def start(self) -> ScanStart:
        body = await self._get("/api/auth/scan/code")
        uuid = str(body["data"])
        return ScanStart(uuid=uuid, payload=f"{QR_PREFIX}{uuid}")

    async def poll(self, uuid: str) -> ScanState:
        body = await self._get("/api/auth/scan/state", uuid=uuid)
        return _STATES.get(int(body["data"]), ScanState.UNKNOWN)

    async def username(self, uuid: str) -> str:
        """星阵账号的**昵称**——不是登录 principal,不能拿它去拼 `0086-{昵称}`
        (见 adapter.py 里 scan_login 相关注释 / R-29)。仅用于屏上展示。"""
        body = await self._get("/api/auth/scan/username", uuid=uuid)
        return str(body["data"])


@dataclass
class ScanSession:
    """服务端持有的扫码登录会话——发起时钉死 `initiating_user_id`,`poll`/`confirm`
    都据此校验,不看「这次请求的调用者是谁」(那个会随盒子换人而变,uuid 本身不带身份)。
    """

    scan_id: str
    golaxy_uuid: str
    initiating_user_id: int
    expires_at: float
    state: ScanState = ScanState.WAITING
    consumed: bool = False
    result: Optional[dict] = None

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at


class ScanSessionStore:
    """进程内内存表,单盒单进程,不需要持久化。

    `lock` 是整表共用的一把锁,只在 `confirm` 的「查 consumed → 换 token → 置位」
    这段临界区里持——量级是「同一时刻最多几个人在扫同一台盒子的码」,不值得做
    按 scan_id 的细粒度锁。
    """

    def __init__(self, ttl_seconds: float = DEFAULT_SCAN_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._sessions: dict[str, ScanSession] = {}
        self.lock = asyncio.Lock()

    def create(self, *, golaxy_uuid: str, initiating_user_id: int) -> ScanSession:
        scan_id = _uuid.uuid4().hex
        session = ScanSession(
            scan_id=scan_id,
            golaxy_uuid=golaxy_uuid,
            initiating_user_id=initiating_user_id,
            expires_at=time.time() + self._ttl,
        )
        self._sessions[scan_id] = session
        return session

    def get(self, scan_id: str) -> Optional[ScanSession]:
        return self._sessions.get(scan_id)

    def discard(self, scan_id: str) -> None:
        self._sessions.pop(scan_id, None)
