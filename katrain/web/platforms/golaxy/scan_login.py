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
#
# ⚠️ **这个数比星阵自己的码活得长(实测 ~182 秒,见下面 `_STATE_BY_ERROR_CODE` 前的
# 记录),它不是「屏上说实话」的机制。** 正常情况下过期由 `poll` 读 `code=6016` 当场
# 报出来,这条 TTL 只在**星阵连不上**时兜底 —— 那种情况下屏上会有一段时间仍写着
# 「等待扫描」(最长 300-182≈118 秒)。要消掉那一段得让前端把「连续 poll 失败」
# 显示出来,不是把这个数字往下调;调小只会在星阵哪天把码的寿命放长时误杀有效的码。
DEFAULT_SCAN_TTL_SECONDS = 300.0

# F5 (task-6a review): 同一用户同时允许多少条「还没过期」的扫码会话。没有这条上限,
# 一个连发 scan/start 的客户端(重试循环/前端 bug)会让 store 单调增长,而且每条都
# 各打过一次星阵 —— 长开机的盒子(2G 内存的 RK3562)上不是零成本。5 已经比任何正常
# 使用模式(一次一张码,偶尔点一次「换一张」)宽裕。
MAX_SESSIONS_PER_USER = 5


class ScanState(str, Enum):
    WAITING = "waiting"  # 0
    SCANNED = "scanned"  # 1 手机扫到了,还没点确认
    CONFIRMED = "confirmed"  # 2 可以换 token 了
    EXPIRED = "expired"  # 6016
    CANCELLED = "cancelled"  # 6019
    UNKNOWN = "unknown"  # 星阵加了新码,我们没见过


# ⚠️ **状态分两个字段来,不是一个。** 2026-09-23 对 `api.19x19.com` 实测,响应逐字:
#
#     取码        {"code":"0","msg":"","data":"8c285fe3-b420-4946-8e78-1a3279a360d3"}
#     还没扫      {"code":"0","msg":"","data":"0"}
#     码已失效    {"code":"6016","msg":"invalid UUID","data":""}
#
# 也就是说 **6016 只会出现在 `code` 里,永远不会出现在 `data` 里**。计划表把两档
# 写进了同一列(「data 取值 0/1/2/6016/6019」),照着建的 `_STATES = {6016: EXPIRED}`
# 因此是一条**永远命不中**的映射:请求会先撞上 `_get` 那句通用的 `code != "0" ⇒ 抛`,
# 于是「二维码过期」在链路上表现成 502「连不上星阵」,前端 poll 的 catch 静默吞掉、
# 下一秒接着问,屏上那颗绿点一直写着「等待扫描」—— 正是本模块 docstring 里点名要挡的
# R-32 形状(坏了和好着在用户那里长得一模一样),只是当时防在了错的那个字段上。
# 教训与本仓判例「闸量错了对象」同族:判据写对了,操作数取错了。
#
# 星阵的码实测寿命 **约 182 秒**(同一次探测:167s 仍 `data:"0"`,182s 已翻 6016),
# 比我们自己的 `DEFAULT_SCAN_TTL_SECONDS` 短 —— 服务端 TTL 因此只是兜底,不是
# 「屏上说实话」的主路径;主路径必须是下面这张按 `code` 查的表。
_STATE_BY_DATA = {
    0: ScanState.WAITING,
    1: ScanState.SCANNED,
    2: ScanState.CONFIRMED,
}

# 业务错误码 → 状态。**只有 6016 是实测到的**(上面那三行响应)。
# 6019(手机上取消)一个人验不了 —— 得真拿手机扫一次再点取消,留到上板那天走一遍;
# 这里按同族推断也放进本表,**万一它实际走的是 `data` 字段**,会落到 `UNKNOWN`:
# 继续轮询、不谎报成「已取消」,方向是安全的那一侧,并由 TTL 兜底收口。
_STATE_BY_ERROR_CODE = {
    "6016": ScanState.EXPIRED,  # 实测
    "6019": ScanState.CANCELLED,  # 推断,待上板实扫验证
}

# States Golaxy will never walk back from. `UNKNOWN` is deliberately NOT here —
# an unrecognized code might still resolve to something real on a later poll,
# so it stays live. The other three are terminal for a DIFFERENT reason than
# "no point asking again": once CONFIRMED, Golaxy very likely invalidates the
# uuid server-side, so a poll AFTER confirmation can flip a legitimately-
# confirmed session to EXPIRED — the user tapped "confirm" on their phone and
# the kiosk screen would flash "二维码已失效" right back at them. Once a
# session reaches one of these, the endpoint must cache it and stop asking.
TERMINAL_STATES = frozenset({ScanState.CONFIRMED, ScanState.EXPIRED, ScanState.CANCELLED})


@dataclass(frozen=True)
class ScanStart:
    uuid: str
    payload: str


class ScanRateLimited(Exception):
    """Raised by `ScanSessionStore.create` when `initiating_user_id` already
    has `MAX_SESSIONS_PER_USER` live (non-expired) sessions (F5, task-6a
    review). The endpoint layer maps this to HTTP 429."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"too many in-flight scan sessions for user {user_id}")


class GolaxyScanLogin:
    """薄客户端,只管 uuid / 状态 / 昵称三步只读查询(①③⑤)。

    第 ④ 步(拿确认后的 uuid 换 access/refresh token)**不在这里**——它复用
    `adapter.py` 里既有的 token 存储/刷新路径(`GolaxyRestClient.login_scan_code`),
    不另写一份。这个类因此没有 token 状态,每次调用都可以是无状态的一次性对象。
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client

    async def _fetch(self, path: str, **params) -> dict:
        """发请求、拿 JSON,**不判 `code`** —— 判 `code` 的是 `_get`。

        分成两层是因为 `poll` 必须自己看 `code`:对它来说 `code=6016` 不是失败,
        是「二维码失效」这个正常状态(见上面 `_STATE_BY_ERROR_CODE` 的实测记录)。
        """
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
        return body

    async def _get(self, path: str, **params) -> dict:
        body = await self._fetch(path, **params)
        # 200 不等于成功:星阵用字符串 code 报错,存在性不是可用性。
        if str(body.get("code")) != "0":
            raise RuntimeError(body.get("msg") or f"星阵返回 code={body.get('code')}")
        return body

    async def start(self) -> ScanStart:
        body = await self._get("/api/auth/scan/code")
        uuid = str(body["data"])
        return ScanStart(uuid=uuid, payload=f"{QR_PREFIX}{uuid}")

    async def poll(self, uuid: str) -> ScanState:
        """③ 查一次状态。**先看 `code` 再看 `data`** —— 两个字段各管一半状态空间,
        见上面 `_STATE_BY_DATA` / `_STATE_BY_ERROR_CODE` 前的实测记录。

        这里刻意不复用 `_get`:`_get` 会把任何非 "0" 的 `code` 一律当失败抛掉,
        而对 `poll` 来说 `6016` 恰恰是要显示给用户看的那个正常终态。
        """
        body = await self._fetch("/api/auth/scan/state", uuid=uuid)
        code = str(body.get("code"))
        if code != "0":
            state = _STATE_BY_ERROR_CODE.get(code)
            if state is not None:
                return state
            # 真·失败(服务忙、限流、没见过的错误码):照旧抛,由端点转 502。
            raise RuntimeError(body.get("msg") or f"星阵返回 code={code}")
        try:
            raw = int(body["data"])
        except (KeyError, TypeError, ValueError):
            # `code=0` 却给不出能当整数读的 `data` —— 星阵改了形状。不猜,报未知:
            # 猜成 WAITING 就又变回「对着一张死码等下去」了(R-32)。
            return ScanState.UNKNOWN
        return _STATE_BY_DATA.get(raw, ScanState.UNKNOWN)

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
    # F4 (task-6a review): which platform this session belongs to. Today only
    # "golaxy" ever creates one, but the session itself didn't record it —
    # `scan_state`/`scan_confirm` trusted the URL's `platform` path param
    # unconditionally, so a golaxy `scan_id` posted to an unrelated/unknown
    # platform path reached `connect_platform` and blew up as a bare
    # `ValueError` -> unhandled 500. Recording it here lets the endpoints
    # check "is this session even for the platform in this URL" themselves.
    platform: str = "golaxy"
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

    def __init__(
        self, ttl_seconds: float = DEFAULT_SCAN_TTL_SECONDS, max_per_user: int = MAX_SESSIONS_PER_USER
    ) -> None:
        self._ttl = ttl_seconds
        self._max_per_user = max_per_user
        self._sessions: dict[str, ScanSession] = {}
        self.lock = asyncio.Lock()

    def _sweep_expired(self) -> None:
        """Drop every session whose TTL has lapsed. `state`/`confirm` already
        discard a session THEY happen to touch after it expires, but a
        session nobody ever polls again (an abandoned tab, a client that
        gave up) would otherwise sit in `_sessions` forever (F5, task-6a
        review). Runs on every `create()`, so the table self-bounds even
        under a caller that only ever calls `scan/start`."""
        expired_ids = [sid for sid, s in self._sessions.items() if s.expired]
        for sid in expired_ids:
            del self._sessions[sid]

    def check_capacity(self, initiating_user_id: int) -> None:
        """Sweep expired sessions and raise `ScanRateLimited` if the caller
        already has `MAX_SESSIONS_PER_USER` live ones — WITHOUT creating
        anything. Callers should call this BEFORE making the (real, costs a
        Golaxy request) `scan/code` call, so a rate-limited caller never pays
        for an outbound request that's going to be discarded anyway.

        This is a BACKSTOP, not the primary defense — see `_supersede_unconsumed`
        on `create()` below (team-lead ruling ①, this round). Under normal use
        (repeatedly hitting "换一张") a caller should never actually reach this
        cap: each new `create()` retires the same user's previous unconsumed
        session first, so at most one unconsumed session per user ever
        accumulates. This only fires for genuinely abnormal cases — e.g. a
        user who has completed several successful (consumed) logins in quick
        succession, since consumed sessions are deliberately NOT superseded
        (their cached result may still be legitimately replayed by a
        network-retried confirm)."""
        self._sweep_expired()
        live_for_user = sum(1 for s in self._sessions.values() if s.initiating_user_id == initiating_user_id)
        if live_for_user >= self._max_per_user:
            raise ScanRateLimited(initiating_user_id)

    def _supersede_unconsumed(self, user_id: int) -> None:
        """F5 (team-lead ruling ①): a new scan_start from the SAME user makes
        any of their own not-yet-consumed sessions obsolete immediately — the
        old QR code is orphaned the moment a new one is drawn, and nothing on
        the kiosk screen lets the user act on a stale one anyway.

        This is the PRIMARY defense against the session table growing under
        normal use, deliberately NOT the `MAX_SESSIONS_PER_USER` cap: a hard
        cap with no supersede would eventually trap a user who just keeps
        clicking "换一张" behind a 429 with nothing on screen they could do
        about it — the same dead-end shape as the D2 finding (a message
        telling someone to disconnect when the disconnect button only
        renders once connected). Consumed sessions are left alone so a
        network-retried confirm can still replay its cached result."""
        stale_ids = [sid for sid, s in self._sessions.items() if s.initiating_user_id == user_id and not s.consumed]
        for sid in stale_ids:
            del self._sessions[sid]

    def create(self, *, golaxy_uuid: str, initiating_user_id: int, platform: str = "golaxy") -> ScanSession:
        self._sweep_expired()
        self._supersede_unconsumed(initiating_user_id)
        live_for_user = sum(1 for s in self._sessions.values() if s.initiating_user_id == initiating_user_id)
        if live_for_user >= self._max_per_user:
            raise ScanRateLimited(initiating_user_id)
        scan_id = _uuid.uuid4().hex
        session = ScanSession(
            scan_id=scan_id,
            golaxy_uuid=golaxy_uuid,
            initiating_user_id=initiating_user_id,
            expires_at=time.time() + self._ttl,
            platform=platform,
        )
        self._sessions[scan_id] = session
        return session

    def get(self, scan_id: str) -> Optional[ScanSession]:
        return self._sessions.get(scan_id)

    def discard(self, scan_id: str) -> None:
        self._sessions.pop(scan_id, None)
