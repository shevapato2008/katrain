"""Authenticated status and server-authoritative start API for ranked AI play."""

from __future__ import annotations

import uuid
import logging
import math
import secrets
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core import models_db
from katrain.web.core.config import settings
from katrain.web.core.ai_ladder_catalog import (
    AiLadderSessionSnapshot,
    build_opponent_snapshot,
    catalog_entry,
    catalog_projection,
    frozen_recipe_from_snapshot,
    result_for_user,
    session_snapshot_from_pending,
)
from katrain.web.core.ai_ladder_ranked import (
    AI_LADDER_GAME_TYPE,
    PLACEMENT_GAMES,
    AiLadderBlockingGame,
    AiLadderLifecycleConflict,
    AiLadderLifecycleNotFound,
    AiLadderLifecycleReceipt,
    AiLadderOpponentSnapshot,
    expected_opponent_rung,
    InvalidReservationKey,
    initial_placement_window,
)
from katrain.web.models import User

router = APIRouter()


def _settlement_outbox_key(game_id: str) -> str:
    """The one idempotency key a settlement is ever queued under, on any path."""
    return f"ladder-settlement:{game_id}"


class _IndeterminateRemoteTransition(RuntimeError):
    pass


def _is_board(request: Request) -> bool:
    return bool(
        getattr(request.app.state, "remote_client", None) and getattr(request.app.state, "repository_dispatcher", None)
    )


def _require_bound_board_user(request: Request, current_user: User) -> None:
    if str(getattr(request.app.state.remote_client, "bound_user_id", "")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cloud session does not match local user")


async def _remote(call, what: str):
    try:
        return await call()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except Exception as exc:
        logging.getLogger("katrain_web").warning("%s remote call failed: %s", what, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Remote server unavailable"
        ) from exc


def _is_indeterminate_remote_error(exc: Exception) -> bool:
    return isinstance(exc, httpx.RequestError) or (
        isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500
    )


async def _retry_indeterminate(call):
    try:
        return await call()
    except Exception as first:
        if not _is_indeterminate_remote_error(first):
            raise
        try:
            return await call()
        except Exception as second:
            if _is_indeterminate_remote_error(second):
                raise _IndeterminateRemoteTransition(str(second)) from second
            raise


#: The board every rung was measured on. Fixed here rather than taken from the
#: request, for the same reason the rung is: a rung's rank name describes its
#: strength in a 19x19 Chinese-rules 7.5-komi even game and nothing else (every
#: calibration campaign ran exactly that -- see
#: superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py), so a
#: client that could ask for 9x9, or for 6.5 komi, would be seating an opponent
#: whose measured strength no longer describes the game being played -- and then
#: banking the result. The player still chooses their seat and their clock.
LADDER_BOARD_SIZE = 19
LADDER_RULES = "chinese"
LADDER_KOMI = 7.5
LADDER_HANDICAP = 0


class AiLadderStartRequest(BaseModel):
    """Seat and clock only. Strength, board conditions, result and configuration
    are all server-owned; `extra="forbid"` means a client that still sends
    board_size/rules/komi/handicap is told so rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")

    color: Literal["black", "white"] = "black"
    time_enabled: bool = False
    main_time: int = Field(default=0, ge=0, le=86400)
    byo_length: int = Field(default=30, ge=0, le=3600)
    byo_periods: int = Field(default=3, ge=0, le=100)


class AiLadderReserveRequest(AiLadderStartRequest):
    game_id: str = Field(min_length=1, max_length=32)
    reservation_key: str = Field(min_length=1, max_length=128)


class AiLadderReservationKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_key: str = Field(min_length=1, max_length=128)


class AiLadderActivateRequest(AiLadderReservationKeyRequest):
    session_id: str = Field(min_length=1, max_length=128)


class AiLadderEndRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["user_resigned"]


def _require_authority(request: Request) -> None:
    if not getattr(request.app.state, "ai_ladder_authoritative", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ranked AI ladder authority is unavailable on this node",
        )


def _pending_settlement(request: Request, user_id: int) -> bool:
    lifecycle = request.app.state.ai_ladder_repo.get_blocking_game(user_id)
    if lifecycle is not None:
        return lifecycle.state == "pending_settlement"
    return request.app.state.ai_ladder_repo.get_pending_game(user_id) is not None


def _device_identity(request: Request) -> Optional[str]:
    """这次请求的设备身份 —— **取不到就是 `None`,不发明一个**。

    和 `_device_id` 只差这一处,而这一处就是那块屏的全部:`_device_id` 在没有头的时候
    发明一个 `"cloud-local"`。那个值当**出处标签**写进 `origin_device_id` 是无害的
    (审计里的一行字,谁写的就记谁),当**身份**参与 `==` 就是撒谎 —— 两个不同的浏览器
    都叫 `"cloud-local"`,比出来相等,屏上于是言之凿凿地说「这一局在本机开始」;而它
    对上一台真盒子起的局,比出来不等,屏上说「在你的另一台设备上」。两句都不是查出来的,
    是一个占位字符串碰巧比出来的。

    **多一个取值只是让谎话有地方待着。** 取不到就 `None`,让调用方说得出「不知道」。
    """

    value = request.headers.get("X-StellaBox-Device-ID")
    normalized = value.strip() if isinstance(value, str) else ""
    if len(normalized) > 64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-StellaBox-Device-ID must be a non-empty label of at most 64 characters",
        )
    return normalized or None


def _device_id(request: Request, *, required: bool = True) -> str:
    """写进账本/预约行的**出处标签**。身份判断一律走 `_device_identity`。"""

    identity = _device_identity(request)
    if required and identity is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-StellaBox-Device-ID must be a non-empty label of at most 64 characters",
        )
    return identity or "cloud-local"


def _ownership(origin_device_id: str, device_identity: Optional[str]) -> str:
    """那一局在哪台设备上 —— 三个取值,因为世界有三种。

    判据只有一条:**两个设备身份的比较**。不是「哪条路答上来的」,不是「本机有没有它的
    记录」——「本机没有记录 ⇒ 那一定在别台」等价于假设本机记录永不丢,而换过盒子、重装
    系统、清过库的那台正站在用户面前。

    `unknown` 不是第三种位置,是**没有位置**:这次请求根本没带设备身份(网页直连云端),
    拿它和任何东西比都得不出结论。布尔装不下这个格子 —— 塞回二值就一定有一格在撒谎,
    而撒的正好是「在别的机器上」那句(`None != 真身份` 恒真)。
    """

    if device_identity is None:
        return "unknown"
    return "current_device" if origin_device_id == device_identity else "other_device"


def _age_seconds(moment: Optional[datetime]) -> Optional[int]:
    """距今多少秒。没有那个时刻就是 None —— **不要拿 0 顶替**:
    「从没收到过心跳」和「刚刚收到」在屏上是相反的两件事。"""
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - moment).total_seconds()))


def _blocking_payload(
    request: Request, game: AiLadderBlockingGame, device_identity: Optional[str]
) -> dict[str, object]:
    """挡住新局的那一局,以及**只有**用户需要知道的那几件事。

    曾经这里发 10 个字段(两组 can_*/eligible_at/eligible_in_seconds/threshold_seconds/
    threshold_version),因为出口分两种、各带一条倒计时。现在出口只有一个「开新局」,
    代价由 `state` 决定,所以这里只剩事实:是哪一局、什么状态、在不在这台机器上。

    `session_id` 仍然只有盒子能回答 —— 云端知道这局属于哪个会话 id,但不知道那个会话
    此刻还在不在。在场就意味着用户该做的是**接着下**,不是开新局。
    """

    ownership = _ownership(game.origin_device_id, device_identity)
    payload: dict[str, object] = {
        "game_id": game.game_id,
        # `reserved` 不能并进 `active`。它一样占着账号,但**代价不同** —— 那一格两端都还没
        # 有人拿到这盘棋,释放它不记成绩。曾经这里把它显示成 active,屏上就会写着「会记为
        # 本局负」,而后端什么都不会记:一句关于后果的假话,而且是往贵了说,用户会因此干等
        # 那 5 分钟的自动回收。
        "state": game.state if game.state in {"reserved", "pending_settlement"} else "active",
        "ownership": ownership,
        "user_color": game.user_color,
        "opponent_rank_name": game.opponent.rank_name,
        # 两个**时长**,不是时刻 —— 常年离线、没有可靠 NTP 的一体机正是钟偏最大的那一台,
        # 拿服务端时刻去减本机的钟,差多少钟就错多少。时长是差值,对钟偏免疫。
        # 用途只有一个:让屏上说得出「那台设备多久没消息了」「成绩压了多久」。
        # **它们不是判据** —— 心跳早已不换取任何权限,别让删掉的那套从 UI 里长回来。
        "heartbeat_age_seconds": _age_seconds(game.last_heartbeat_at),
        "pending_since_seconds": _age_seconds(game.pending_settlement_since),
    }
    # `session_id` 的判据是**这个节点此刻真的握着那个会话**,不是 ownership。两件事今天
    # 恰好同值(会话活着 ⇒ 一定是本机的),但它们是两个语义:ownership 说位置,`session_id`
    # 说「在这里接得回来」。挂在同一个布尔上,第三态一出现就会两边一起错。
    # `other_device` 仍然一律不给:那台的会话不在这个节点上,给一个接不上的 id 是假出路。
    if (
        game.state == "active"
        and ownership != "other_device"
        and game.origin_session_id
        and _active_session(request, game.origin_session_id)
    ):
        payload["session_id"] = game.origin_session_id
    return payload


def _lifecycle_payload(receipt: AiLadderLifecycleReceipt) -> dict[str, object]:
    return {
        "state": "settled",
        "game_id": receipt.game_id,
        "receipt": {"counted": receipt.counted, "reason": receipt.reason},
    }


def _lifecycle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AiLadderLifecycleNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found")
    if isinstance(exc, (AiLadderLifecycleConflict, InvalidReservationKey)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _session_by_id(request: Request, session_id: Optional[str]):
    """The live session object for `session_id`, or None. Takes the manager's lock when it
    has one (the test harness swaps in a plain dict)."""
    if not session_id:
        return None
    manager = request.app.state.session_manager
    lock = getattr(manager, "_lock", None)
    if lock is None:
        return getattr(manager, "_sessions", {}).get(session_id)
    with lock:
        return manager._sessions.get(session_id)


def _active_session(request: Request, session_id: str) -> bool:
    return _session_by_id(request, session_id) is not None


def _engine_stalled_for(request: Request, lifecycle) -> bool:
    """这一局的阶梯引擎是不是拒绝过落子。

    `_ignored_reason` 早就写着「engine_stalled ⇒ 不计分」,可它只能判调用方递给它的东西,
    而这条路**什么都没递** —— 于是屏上写着「本局不计入升降级」,账本里记的却是一场
    counted 的负。生产实测:2026-08-29,user 10,game 7a6c8e42…,`counted=t`、`reason` 为空,
    定级进度被这一局从 0 推到 1。

    这个状态位活在下棋的那个进程里、不在行上,所以只能顺着 `origin_session_id`
    (`activate_reservation` 写下的那个指针)回去读。**那个会话若已经没了**(服务重启、
    会话超时),这里就问不出来,于是照旧计分 —— 这是把洞收窄,不是补上。要真补上,
    得让停摆这件事写进 lifecycle 行里。
    """
    session = _session_by_id(request, getattr(lifecycle, "origin_session_id", None))
    return bool(getattr(getattr(session, "katrain", None), "last_ladder_error", False))


def _preflight_ladder_engine(session, frozen_recipe) -> None:
    """开局之前先问引擎:这一档你到底能不能下。

    从前是**先把一切写下来**(预约、pending 账本行、坐好玩家、开钟),第一手棋才发现引擎
    服务不了这一档。玩家于是拿到一局已经押上定级名额的死棋 —— 用户看到的
    「对局开出来了、对手标 6级、钟在跑、一手不落」正是这套顺序的必然输出。

    这里问的就是 `LadderStrategy.generate_move` 开头那一句(`core/ai.py`),所以引擎服务不了
    的部署会在 `/start` 拿到 503,而不是在第 2 手拿到一条横幅。
    """
    from katrain.core.ladder import rung_strength_spec

    engine = getattr(getattr(session, "katrain", None), "engine", None)
    if engine is None:
        return
    spec = rung_strength_spec(frozen_recipe)
    engine.require_ladder_capability(spec.main_model, human_required=spec.human_model is not None)


def _local_ranked_session_matches(request: Request, current_user: User, pending: dict, game_id: str) -> bool:
    session_id = pending.get("session_id")
    session = _session_by_id(request, session_id)
    if session is None:
        return False
    snapshot = getattr(session, "ai_ladder_snapshot", None)
    return bool(
        getattr(session, "user_id", None) == current_user.id
        and getattr(session, "game_type", None) == AI_LADDER_GAME_TYPE
        and isinstance(snapshot, AiLadderSessionSnapshot)
        and snapshot.game_id == game_id
        and snapshot.user_id == current_user.id
        and snapshot.session_id == session_id
    )


def mark_ai_ladder_remote_terminal(session, lifecycle) -> None:
    runtime = getattr(session, "katrain", None)
    commit_lock = getattr(runtime, "ai_ladder_commit_lock", None)

    def commit_marker() -> None:
        session.ai_ladder_remote_ended = True
        session.ai_ladder_remote_lifecycle = lifecycle
        if runtime is not None:
            runtime.ai_ladder_remote_ended = True

    if commit_lock is None:
        commit_marker()
    else:
        with commit_lock:
            commit_marker()

    engine = getattr(runtime, "engine", None)
    terminate = getattr(engine, "terminate_queries", None)
    if callable(terminate):
        terminate(only_for_node=getattr(getattr(runtime, "game", None), "current_node", None))
    engine_stop = getattr(engine, "stop_pondering", None)
    fallback_stop = getattr(runtime, "stop_pondering", None)
    stop = engine_stop if callable(engine_stop) else fallback_stop
    if callable(stop):
        stop()
    if runtime is not None:
        runtime.pondering = False


def _mark_local_remote_terminal(request: Request, current_user: User, game_id: str, lifecycle: dict) -> None:
    pending = request.app.state.ai_ladder_repo.get_pending_game(current_user.id)
    if pending is None or pending.get("game_id") != game_id:
        return
    if not _local_ranked_session_matches(request, current_user, pending, game_id):
        return
    session = request.app.state.session_manager._sessions.get(pending["session_id"])
    if session is None:
        return
    mark_ai_ladder_remote_terminal(session, lifecycle)


def _recover_pending(request: Request, user_id: int) -> None:
    if _is_board(request):
        repo = request.app.state.ai_ladder_repo
        pending = repo.get_pending_game(user_id)
        if pending is None or not pending.get("reservation_key"):
            return
        try:
            game = request.app.state.user_game_repo.get_authoritative_ai_ladder_ranked(pending["game_id"], user_id)
            enqueue = getattr(request.app.state, "sync_enqueue_fn", None)
            if game is None or enqueue is None:
                return
            from katrain.web.core.ai_ladder_sync import build_settlement_payload

            snapshot = session_snapshot_from_pending(pending)
            lifecycle = repo.get_game_lifecycle(user_id=user_id, game_id=snapshot.game_id)
            durable = (
                enqueue(
                    operation="settle_ai_ladder_ranked",
                    endpoint="/api/v1/ai-ladder/settlements",
                    method="POST",
                    payload=build_settlement_payload(
                        snapshot,
                        game["result"],
                        reservation_key=pending["reservation_key"],
                        game_record=game,
                        device_id=settings.DEVICE_ID,
                        engine_stalled=getattr(lifecycle, "reason", None) == "engine_unavailable",
                    ),
                    user_id=str(user_id),
                    idempotency_key=_settlement_outbox_key(snapshot.game_id),
                )
                is True
            )
            if durable:
                repo.clear_pending_game(user_id=user_id, game_id=snapshot.game_id)
        except Exception as exc:
            logging.getLogger("katrain_web").warning("Could not recover ranked settlement outbox: %s", exc)
        return
    repo = request.app.state.ai_ladder_repo
    pending = repo.get_pending_game(user_id)
    if pending is None:
        return
    lifecycle = repo.get_blocking_game(user_id)
    try:
        game = request.app.state.user_game_repo.get_authoritative_ai_ladder_ranked(pending["game_id"], user_id)
        if lifecycle is not None:
            # Account occupancy is cloud-authoritative. Never abandon it merely
            # because this process lost its session. A fully saved origin result may
            # still complete the same credentialed terminal transaction after restart.
            if game is None or not pending.get("reservation_key"):
                return
            snapshot = session_snapshot_from_pending(pending)
            repo.mark_pending_game_saved(user_id=user_id, game_id=snapshot.game_id, result=game["result"])
            repo.finalize_reserved_game(
                user_id=user_id,
                game_id=snapshot.game_id,
                terminal_source="recovery",
                result=result_for_user(game["result"], snapshot.user_color),
                deciding_device_id=lifecycle.origin_device_id,
                reservation_key=pending["reservation_key"],
                game_record=game,
            )
            repo.clear_pending_game(user_id=user_id, game_id=snapshot.game_id)
            return
        if game is None:
            if not _active_session(request, pending["session_id"]):
                repo.clear_pending_game(user_id=user_id, game_id=pending["game_id"])
            return
        snapshot = session_snapshot_from_pending(pending)
        repo.mark_pending_game_saved(user_id=user_id, game_id=snapshot.game_id, result=game["result"])
        repo.settle_game(
            user_id=user_id,
            game_id=snapshot.game_id,
            user_color=snapshot.user_color,
            result=result_for_user(game["result"], snapshot.user_color),
            game_type=snapshot.game_type,
            opponent=snapshot.opponent,
        )
        repo.clear_pending_game(user_id=user_id, game_id=snapshot.game_id)
    except Exception as exc:
        logging.getLogger("katrain_web").error("Failed to recover ranked AI settlement: %s", exc)


def _status_payload(
    request: Request, current_user: User, *, device_identity: Optional[str] = None
) -> dict[str, object]:
    _recover_pending(request, current_user.id)
    repo = request.app.state.ai_ladder_repo
    db = repo.session_factory()
    try:
        profile = db.get(models_db.AiLadderProfile, current_user.id)
        if profile is None:
            lo, hi = initial_placement_window(current_user.rank)
            completed = 0
            rung = None
            net_score = 0
        else:
            lo, hi = profile.placement_lo, profile.placement_hi
            completed = profile.placement_completed
            rung = profile.ai_ladder_rung
            net_score = profile.net_score
    finally:
        db.close()

    opponent_rung = expected_opponent_rung(rung, lo, hi)
    opponent = catalog_entry(opponent_rung)
    current_opponent = dict(opponent)
    if opponent["certification_status"] == "certified" and opponent["availability"] == "available":
        current_opponent["counting_eligibility"] = "eligible"
    else:
        current_opponent["counting_eligibility"] = "ineligible"
        current_opponent["counting_reason"] = "opponent_not_eligible"
    placement_state: dict[str, object]
    if rung is None:
        placement_state = {"phase": "placement", "completed_games": completed, "total_games": PLACEMENT_GAMES}
    else:
        placement_state = {"phase": "placed", "rung": opponent}

    from katrain.core import ladder

    blocking = repo.get_blocking_game(current_user.id)
    return {
        "view_state": "ready",
        "placement_state": placement_state,
        "current_opponent": current_opponent,
        "recent_ranked_results": repo.recent_counted_results(current_user.id, limit=5),
        "net_score": net_score,
        "pending_settlement": _pending_settlement(request, current_user.id),
        "blocking_game": _blocking_payload(request, blocking, device_identity) if blocking else None,
        # Whether THIS node will seat an uncertified rung. The rung's own
        # certification_status/availability keep telling the truth about the rung; this
        # says what the server will do about it, so the client can stop guessing why a
        # start request would be refused (or, here, accepted).
        "provisional_play_allowed": ladder.provisional_play_allowed(),
    }


@router.get("/catalog")
def get_catalog(current_user: User = Depends(get_current_user)):
    return catalog_projection()


@router.get("/status")
async def get_status(request: Request, current_user: User = Depends(get_current_user)):
    if _is_board(request):
        _require_bound_board_user(request, current_user)
        _recover_pending(request, current_user.id)
        payload = await _remote(lambda: request.app.state.remote_client.get_ai_ladder_status(), "AI ladder status")
        blocking = payload.get("blocking_game") if isinstance(payload, dict) else None
        if isinstance(blocking, dict):
            payload = dict(payload)
            blocking = dict(blocking)
            blocking.pop("session_id", None)
            blocking.pop("reservation_key", None)
            payload["blocking_game"] = blocking
        if isinstance(blocking, dict) and blocking.get("state") == "pending_settlement":
            # 云端只知道「这局的成绩还没到」,它无从知道**为什么** —— 排队、退避、
            # 重试用尽还是被拒收,全在盒子这边的 outbox 里。不接上去,屏上就只能写
            # 一个不含信息的「同步中」,而用户想知道的正是这个。
            worker = getattr(request.app.state, "sync_worker", None)
            describe = getattr(worker, "describe", None)
            if describe is not None:
                sync = describe(_settlement_outbox_key(blocking["game_id"]), user_id=current_user.id)
                if sync is not None:
                    payload["blocking_game"]["sync"] = sync
        if isinstance(blocking, dict) and blocking.get("state") == "active":
            pending = request.app.state.ai_ladder_repo.get_pending_game(current_user.id)
            # 这台设备是不是那一局的 origin —— **不看云端那个标签,看凭证在不在手上**。
            #
            # ⚠️ **这段扛着 100% 的负载,不是在救一个罕见情况。谁觉得它冗余把它删掉,假话立刻上屏。**
            # 云端的 `ownership` 比的是 `origin_device_id` 这个标签,而这个标签**每次重启就换一个**:
            # `config.py:132-134` 在 `KATRAIN_DEVICE_ID` 没配时现生成 `uuid4().hex`(README 原文:
            # *If omitted, a random UUID is generated on each startup*),而**全仓没有任何一份
            # 部署产物写过这个环境变量**(2026-08-16 扫过 .env/.service/.sh/.yml/.conf:0 命中;
            # 只有 README 和几份计划文档提到过它)。⇒ 盒子重启一次,它自己那一局在云端就变成
            # 「另一台设备」—— 而人正站在这台前面,会去找一台不存在的机器。
            #
            # 真正的根治是把 DEVICE_ID 持久化,但那个值同时是 refresh-token 的存储键和 outbox 的
            # device 字段,不在升降级模块的范围里。在那之前,这段是屏上那句话为真的唯一原因。
            #
            # 这台设备手上有那一局的 `reservation_key`,而 `_verify_origin`
            # (`ai_ladder_ranked.py`)写得很明白:设备 id 是可变的出处标签、从来不是凭证,
            # **那把猜不到的钥匙是 origin 唯一的凭据**。钥匙只在 `/start` 时发给创建方一次,
            # 所以「本机 pending 表里存着这一局的 key」就等于「这一局是这台设备起的」。
            # 我想问的那句话是「那一局是不是这台起的」,这一步问的正是它 —— 没有换成更宽的
            # 「本机有没有它的记录」(那句在库被清过之后会答错,而且答的是相反的方向)。
            owned_here = (
                pending is not None
                and pending.get("game_id") == blocking.get("game_id")
                and bool(pending.get("reservation_key"))
            )
            if owned_here and blocking.get("ownership") != "current_device":
                payload["blocking_game"]["ownership"] = "current_device"
            if owned_here and _local_ranked_session_matches(request, current_user, pending, blocking["game_id"]):
                await _remote(
                    lambda: _retry_indeterminate(
                        lambda: request.app.state.remote_client.activate_ai_ladder_game(
                            blocking["game_id"], pending["reservation_key"], pending["session_id"]
                        )
                    ),
                    "AI ladder activation reconciliation",
                )
                # Work on a copy: never pass through any cloud-side session/key.
                payload["blocking_game"]["session_id"] = pending["session_id"]
                # 会话住在盒子上,云端分不清「能接回来」和「已经孤儿」,所以对每一局盒子上的棋
                # 它都答「接不回来」—— `session_id` 就是为此在这里补上的。
                # (曾经还要在这里抹掉一组云端发来的接管字段;那组字段已经不存在了。)
            elif owned_here:
                try:
                    cancelled = await request.app.state.remote_client.cancel_ai_ladder_reservation(
                        blocking["game_id"], pending["reservation_key"]
                    )
                    if cancelled.get("state") == "cancelled":
                        request.app.state.ai_ladder_repo.clear_pending_game(
                            user_id=current_user.id, game_id=blocking["game_id"]
                        )
                except Exception:
                    # An active cloud game cannot be cancelled; a transient failure is
                    # retried on the next status refresh without dropping the key.
                    pass
        elif blocking is None:
            pending = request.app.state.ai_ladder_repo.get_pending_game(current_user.id)
            game = (
                request.app.state.user_game_repo.get_authoritative_ai_ladder_ranked(pending["game_id"], current_user.id)
                if pending is not None
                else None
            )
            if pending is not None and game is None:
                request.app.state.ai_ladder_repo.clear_pending_game(user_id=current_user.id, game_id=pending["game_id"])
        return payload
    _require_authority(request)
    return _status_payload(request, current_user, device_identity=_device_identity(request))


def _reserve(*, body: AiLadderReserveRequest, request: Request, current_user: User, device_id: str):
    status_payload = _status_payload(request, current_user, device_identity=_device_identity(request))
    opponent_entry = status_payload["current_opponent"]
    assert isinstance(opponent_entry, dict)
    try:
        opponent, execution_identity = build_opponent_snapshot(int(opponent_entry["rung"]))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    try:
        return request.app.state.ai_ladder_repo.reserve_game(
            user_id=current_user.id,
            game_id=body.game_id,
            user_color="B" if body.color == "black" else "W",
            opponent=opponent,
            origin_device_id=device_id,
            ai_subtype="ai:ladder",
            execution_identity=execution_identity,
            rules_snapshot={
                "board_size": LADDER_BOARD_SIZE,
                "rules": LADDER_RULES,
                "komi": LADDER_KOMI,
                "handicap": LADDER_HANDICAP,
            },
            time_control_snapshot={
                "time_enabled": body.time_enabled,
                "main_time": body.main_time,
                "byo_length": body.byo_length,
                "byo_periods": body.byo_periods,
            },
            reservation_key=body.reservation_key,
        )
    except (ValueError, AiLadderLifecycleConflict) as exc:
        raise _lifecycle_error(exc) from exc


@router.post("/games/reserve", status_code=status.HTTP_201_CREATED)
def reserve_ranked_game(
    body: AiLadderReserveRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    # 两个用途,两个值,别合并:`device_id` 是记进预约行的**出处标签**(不能为空),
    # `identity` 是这次请求**能不能证明自己是谁**(没有就是 None)。
    device_id = _device_id(request, required=False)
    identity = _device_identity(request)
    try:
        reserved = _reserve(body=body, request=request, current_user=current_user, device_id=device_id)
    except HTTPException as exc:
        blocking = request.app.state.ai_ladder_repo.get_blocking_game(current_user.id)
        if exc.status_code == status.HTTP_409_CONFLICT and blocking is not None:
            exc.detail = {"message": str(exc.detail), "blocking_game": _blocking_payload(request, blocking, identity)}
        raise
    if reserved.reservation_key is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Reservation already exists; its credential cannot be replayed",
                "blocking_game": _blocking_payload(request, reserved.game, identity),
            },
        )
    return {
        "game_id": reserved.game.game_id,
        "reservation_key": reserved.reservation_key,
        "blocking_game": _blocking_payload(request, reserved.game, identity),
        "opponent": {
            "rung": reserved.game.opponent.rung,
            "rank_name": reserved.game.opponent.rank_name,
            "config_snapshot": dict(reserved.game.opponent.config_snapshot),
            "certification_status": reserved.game.opponent.certification_status,
            "availability": reserved.game.opponent.availability,
            "route": reserved.game.opponent.route,
        },
        "execution_identity": reserved.game.execution_identity,
    }


@router.post("/games/{game_id}/activate")
def activate_ranked_game(
    game_id: str,
    body: AiLadderActivateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        game = request.app.state.ai_ladder_repo.activate_reservation(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=body.reservation_key,
            origin_device_id=_device_id(request, required=False),
            origin_session_id=body.session_id,
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    return {"state": "active", "game_id": game.game_id}


@router.post("/games/{game_id}/pending-settlement")
def mark_ranked_game_pending(
    game_id: str,
    body: AiLadderReservationKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        game = request.app.state.ai_ladder_repo.mark_pending_settlement(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=body.reservation_key,
            origin_device_id=_device_id(request, required=False),
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    return {"state": "pending_settlement", "game_id": game.game_id}


@router.post("/games/{game_id}/heartbeat")
async def heartbeat_ranked_game(
    game_id: str,
    body: AiLadderReservationKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Report that the client running this ranked game is still alive.

    Called on a fixed timer, never off the back of a move: a player thinking for three minutes
    is normal, so move-driven liveness would read deep thought as a dead box. The cloud uses
    nothing but this to decide whether another device may end the game, which is why it is
    origin-only -- the reservation key proves the caller is the client actually playing.
    """

    if _is_board(request):
        _require_bound_board_user(request, current_user)
        return await _remote(
            lambda: request.app.state.remote_client.send_ai_ladder_heartbeat(game_id, body.reservation_key),
            "AI ladder heartbeat",
        )
    _require_authority(request)
    try:
        game = request.app.state.ai_ladder_repo.record_heartbeat(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=body.reservation_key,
            origin_device_id=_device_id(request, required=False),
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    return {"state": game.state, "game_id": game.game_id}


@router.delete("/games/{game_id}/reservation")
def cancel_ranked_game_reservation(
    game_id: str,
    body: AiLadderReservationKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        result = request.app.state.ai_ladder_repo.cancel_reservation(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=body.reservation_key,
            origin_device_id=_device_id(request, required=False),
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    if result.receipt is not None:
        return _lifecycle_payload(result.receipt)
    return {"state": "cancelled", "game_id": game_id}


@router.get("/games/{game_id}/status")
async def get_ranked_game_status(
    game_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    if _is_board(request):
        _require_bound_board_user(request, current_user)
        lifecycle = await _remote(
            lambda: request.app.state.remote_client.get_ai_ladder_game_status(game_id),
            "AI ladder game status",
        )
        if not isinstance(lifecycle, dict) or lifecycle.get("game_id") != game_id:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid ranked lifecycle response")
        if isinstance(lifecycle, dict) and lifecycle.get("state") in {"pending_settlement", "settled"}:
            _mark_local_remote_terminal(request, current_user, game_id, lifecycle)
        return lifecycle
    _require_authority(request)
    try:
        lifecycle = request.app.state.ai_ladder_repo.get_game_lifecycle(user_id=current_user.id, game_id=game_id)
    except AiLadderLifecycleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found") from exc
    if lifecycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found")
    if isinstance(lifecycle, AiLadderLifecycleReceipt):
        return _lifecycle_payload(lifecycle)
    return {
        "state": "pending_settlement" if lifecycle.state == "pending_settlement" else "active",
        "game_id": lifecycle.game_id,
    }


@router.post("/games/{game_id}/end")
async def end_ranked_game(
    game_id: str,
    body: AiLadderEndRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    if _is_board(request):
        _require_bound_board_user(request, current_user)
        return await _remote(lambda: request.app.state.remote_client.end_ai_ladder_game(game_id), "AI ladder game end")
    _require_authority(request)
    repo = request.app.state.ai_ladder_repo
    deciding_device_id = _device_id(request, required=False)

    # 有棋盘的那一格只有一个出口:认输,一个价钱 —— 不再按云端知道什么分流。
    #
    # 曾经这里按「结果已宣告」分过一次叉:那条走释放、什么都不记,其余判负。同一处境两个
    # 价钱会让贵的那条自然消亡 —— 劣势局面下认输记一场负、放弃什么都不记,后者严格更优,
    # 不需要恶意、只需要看得见。合成一条之后,「不得靠断线躲掉一场负」才重新成立。
    #
    # 认输写下的那行账本同时是**墓碑**:原盒子的在途结算重投时命中它,拿到重放回执干净
    # 收尾,而不是撞上「查无此局」把自己锁死。
    #
    # `reserved` 是另一回事,不是第二个价钱:那一格**两端都还没有人拿到这盘棋**。
    # 判据能成立是因为 `/start` 的顺序 —— session_id 是 activate 返回之后才发出去的,
    # 而 activate 正是把状态推离 `reserved` 的那一次写;activate 失败会 `remove_session`
    # 并抛错。所以在锁下读到 `reserved`,就等于「没有任何一端持有这盘棋」。
    # 这不是推的:失败路径见本文件 `/start` 的 except 块。
    #
    # 注意这个判据的形状 ——「云端没收到过盒子的消息」**不是**同一件事,那种缺席有两个
    # 解释(没起过 / 起了但断网),两个解释在这里价钱正好相反。别的棋种若拿「没心跳」
    # 当判据,会把一盘离线下完的棋静悄悄丢掉。
    lifecycle = repo.get_game_lifecycle(user_id=current_user.id, game_id=game_id)
    if isinstance(lifecycle, AiLadderBlockingGame) and lifecycle.state == "reserved":
        try:
            # 读到之后、写进去之前那一格可能已经被 activate 推走了。不用在这里防:
            # `release_unplayed_reservation` 在锁下重新验状态,那时已经开起来的局会拿到
            # 409 而不是被悄悄释放 —— 用户再按一次就走认输那条。宁可多一次 409。
            released = repo.release_unplayed_reservation(
                user_id=current_user.id,
                game_id=game_id,
                deciding_device_id=deciding_device_id,
            )
        except ValueError as exc:
            raise _lifecycle_error(exc) from exc
        if released.receipt is not None:
            return _lifecycle_payload(released.receipt)
        return {"state": "released", "game_id": game_id, "counted": False}

    try:
        receipt = repo.finalize_reserved_game(
            user_id=current_user.id,
            game_id=game_id,
            terminal_source="remote_resign",
            result="loss",
            deciding_device_id=deciding_device_id,
            # 认输记一场负是有意的(「不得靠断线躲掉一场负」),但**引擎自己没落过子的那一局
            # 不是一场负**。这一格从前不传,于是横幅上的「本局不计入升降级」是句空话。
            engine_stalled=_engine_stalled_for(request, lifecycle),
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    return _lifecycle_payload(receipt)


@router.post("/games/{game_id}/settlement/retry")
async def retry_ranked_settlement(
    game_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Send the queued settlement now instead of waiting out the backoff.

    Only a board has this route, because only a board has an outbox: on the cloud a
    settlement is either recorded or was never submitted, and there is nothing in
    between to retry. The reply is the same descriptor `/status` carries, taken after
    the attempt — so the button's own result is what refreshes the panel.
    """
    if not _is_board(request):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The settlement outbox only exists on a board device"
        )
    _require_bound_board_user(request, current_user)
    worker = getattr(request.app.state, "sync_worker", None)
    if worker is None or not hasattr(worker, "describe"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No settlement outbox on this device")
    key = _settlement_outbox_key(game_id)
    if worker.describe(key, user_id=current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No queued settlement for this game")
    if getattr(request.app.state.remote_client, "auth_required", False):
        # 队列在这种状态下会整个暂停(`_process_queue` 一进循环就 break),所以这里
        # 按下去一步都不会走。不说破的话屏上会显示「正在送」—— 一句不会成真的话。
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cloud session needs to be renewed")
    if worker.retry_now(key, user_id=current_user.id):
        try:
            await worker.run_sync()
        except Exception as exc:
            # 一次没送成不是错误,是这块屏本来就在显示的那件事;失败会落进 outbox 的
            # 计数和退避里,下一行 describe 就把它读出来。
            logging.getLogger("katrain_web").info("Manual ranked settlement retry did not land: %s", exc)
    return {"game_id": game_id, "sync": worker.describe(key, user_id=current_user.id)}


@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_ranked_game(
    body: AiLadderStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    board = _is_board(request)
    if not board:
        _require_authority(request)
    else:
        _require_bound_board_user(request, current_user)
    device_id = _device_id(request, required=False)
    game_id = uuid.uuid4().hex
    reservation_key = secrets.token_urlsafe(32)
    if board:
        reserve_payload = {"game_id": game_id, "reservation_key": reservation_key, **body.model_dump()}
        try:
            reservation_payload = await _retry_indeterminate(
                lambda: request.app.state.remote_client.reserve_ai_ladder_game(reserve_payload)
            )
        except _IndeterminateRemoteTransition as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ranked game reservation is awaiting cloud expiry",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
        try:
            if reservation_payload["game_id"] != game_id:
                raise ValueError("cloud reservation game_id mismatch")
            opponent = AiLadderOpponentSnapshot(**reservation_payload["opponent"])
            execution_identity = reservation_payload["execution_identity"]
        except (KeyError, TypeError, ValueError) as exc:
            try:
                await request.app.state.remote_client.cancel_ai_ladder_reservation(game_id, reservation_key)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail="Cloud returned an invalid ranked reservation") from exc
    else:
        status_payload = _status_payload(request, current_user, device_identity=_device_identity(request))
        if status_payload["pending_settlement"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Previous ranked game settlement is pending"
            )
        reservation = _reserve(
            body=AiLadderReserveRequest(game_id=game_id, reservation_key=reservation_key, **body.model_dump()),
            request=request,
            current_user=current_user,
            device_id=device_id,
        )
        assert reservation.reservation_key is not None
        reservation_key = reservation.reservation_key
        opponent = reservation.game.opponent
        execution_identity = reservation.game.execution_identity

    manager = request.app.state.session_manager
    activity = getattr(request.app.state, "ranked_analysis_activity", None)
    user_color = "B" if body.color == "black" else "W"
    ai_color = "W" if user_color == "B" else "B"

    def snapshot_for(session_id: str) -> AiLadderSessionSnapshot:
        return AiLadderSessionSnapshot(
            game_id=game_id,
            session_id=session_id,
            user_id=current_user.id,
            user_color=user_color,
            game_type=AI_LADDER_GAME_TYPE,
            opponent=opponent,
            ai_subtype="ai:ladder",
            execution_identity=execution_identity,
        )

    def analysis_is_active(session_id: str, kinds: dict[str, int]) -> bool:
        if any(kind.startswith(("quick-analysis", "platform:")) for kind in kinds):
            return True
        try:
            analysis_session = manager.get_session(session_id)
        except KeyError:
            return False
        if set(kinds) == {"continuous"}:
            return bool(getattr(analysis_session.katrain, "pondering", False))
        # One-shot and tree-wide analysis can outlive the initiating HTTP call and
        # may touch nodes other than current_node. Conservatively keep the lease
        # until the session is reset/deleted; this is safer than guessing completion.
        return True

    if activity is not None and not activity.reserve_ranked_start(current_user.id, analysis_is_active):
        if board:
            await _remote(
                lambda: request.app.state.remote_client.cancel_ai_ladder_reservation(game_id, reservation_key),
                "AI ladder reservation cancellation",
            )
        else:
            request.app.state.ai_ladder_repo.cancel_reservation(
                user_id=current_user.id,
                game_id=game_id,
                reservation_key=reservation_key,
                origin_device_id=device_id,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop active analysis before starting a ranked AI game",
        )

    try:
        session = manager.create_session(
            katago_uuid=current_user.uuid,
            user_id=current_user.id,
            initial_game_type=AI_LADDER_GAME_TYPE,
            skip_initial_analysis=True,
        )
    except Exception as exc:
        if activity is not None:
            activity.release_ranked_start(current_user.id)
        if board:
            cancelled = False
            try:
                await request.app.state.remote_client.cancel_ai_ladder_reservation(game_id, reservation_key)
                cancelled = True
            except Exception:
                pass
            if not cancelled:
                try:
                    request.app.state.ai_ladder_repo.create_pending_game(
                        snapshot_for(f"unconfigured-{game_id}"), reservation_key=reservation_key
                    )
                except Exception:
                    pass
        else:
            request.app.state.ai_ladder_repo.cancel_reservation(
                user_id=current_user.id,
                game_id=game_id,
                reservation_key=reservation_key,
                origin_device_id=device_id,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not create game session"
        ) from exc

    snapshot = snapshot_for(session.session_id)
    frozen_recipe = frozen_recipe_from_snapshot(opponent)

    # 账本还一个字都没写的最后一刻 —— `create_pending_game` 是第一次落账。
    try:
        _preflight_ladder_engine(session, frozen_recipe)
    except Exception as exc:
        logging.getLogger("katrain_web").error(
            "[ladder] refusing to seat rung %s (%s): %s", opponent.rung, opponent.rank_name, exc
        )
        if activity is not None:
            activity.release_ranked_start(current_user.id)
        try:
            manager.remove_session(session.session_id)
        except Exception:
            pass
        if board:
            try:
                await request.app.state.remote_client.cancel_ai_ladder_reservation(game_id, reservation_key)
            except Exception:
                pass
        else:
            request.app.state.ai_ladder_repo.cancel_reservation(
                user_id=current_user.id,
                game_id=game_id,
                reservation_key=reservation_key,
                origin_device_id=device_id,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ranked engine cannot serve the seated rung",
        ) from exc

    try:
        request.app.state.ai_ladder_repo.create_pending_game(snapshot, reservation_key=reservation_key)
        if activity is not None:
            activity.release_ranked_start(current_user.id)
        with session.lock:
            session.user_id = current_user.id
            session.game_type = AI_LADDER_GAME_TYPE
            session.ai_ladder_snapshot = snapshot
            session.ai_ladder_runtime_identity = execution_identity
            session.ai_ladder_ai_subtype = "ai:ladder"
            session.ai_ladder_settlement_pending = False
            session.ai_ladder_reservation_key = reservation_key
            # Kept so the heartbeat loop reports under the device that actually reserved this
            # game. Provenance, not a credential -- `_verify_origin` authenticates on the
            # reservation key alone, and a device label is mutable by whoever sends it.
            session.ai_ladder_origin_device_id = device_id
            session._recorded = False
            session.katrain(
                "update_player",
                bw=user_color,
                player_type="player:human",
                player_subtype="player:human",
                name=current_user.username,
            )
            session.katrain(
                "update_player",
                bw=ai_color,
                player_type="player:ai",
                player_subtype="ai:ladder",
                name=opponent.rank_name,
            )
            if body.time_enabled:
                session.katrain.update_config("timer/main_time", body.main_time)
                session.katrain.update_config("timer/byo_length", body.byo_length)
                session.katrain.update_config("timer/byo_periods", body.byo_periods)
                session.katrain.update_config("timer/paused", False)
            else:
                session.katrain.update_config("timer/main_time", 0)
                session.katrain.update_config("timer/byo_length", 0)
                session.katrain.update_config("timer/paused", True)
            session.katrain(
                "new_game",
                size=LADDER_BOARD_SIZE,
                handicap=LADDER_HANDICAP,
                komi=LADDER_KOMI,
                rules=LADDER_RULES,
                game_type=AI_LADDER_GAME_TYPE,
                ladder_rung=opponent.rung,
                frozen_ladder_recipe=frozen_recipe,
                skip_initial_analysis=True,
            )
            session.katrain.game_type = AI_LADDER_GAME_TYPE
            session.last_state = session.katrain.get_state()
        if board:
            await _retry_indeterminate(
                lambda: request.app.state.remote_client.activate_ai_ladder_game(
                    game_id, reservation_key, session.session_id
                )
            )
        else:
            request.app.state.ai_ladder_repo.activate_reservation(
                user_id=current_user.id,
                game_id=game_id,
                reservation_key=reservation_key,
                origin_device_id=device_id,
                origin_session_id=session.session_id,
            )
    except Exception as exc:
        if activity is not None:
            activity.release_ranked_start(current_user.id)
        ambiguous_activation = board and (
            isinstance(exc, _IndeterminateRemoteTransition) or _is_indeterminate_remote_error(exc)
        )
        if ambiguous_activation:
            try:
                lifecycle = await request.app.state.remote_client.get_ai_ladder_game_status(game_id)
                if lifecycle.get("state") in {"active", "pending_settlement"}:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Ranked game activation is awaiting cloud reconciliation",
                    ) from exc
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Ranked game activation is awaiting cloud reconciliation",
                ) from exc
        cancelled = not board
        try:
            if board:
                await request.app.state.remote_client.cancel_ai_ladder_reservation(game_id, reservation_key)
                cancelled = True
            else:
                request.app.state.ai_ladder_repo.cancel_reservation(
                    user_id=current_user.id,
                    game_id=game_id,
                    reservation_key=reservation_key,
                    origin_device_id=device_id,
                )
        except Exception:
            pass
        if cancelled:
            try:
                request.app.state.ai_ladder_repo.clear_pending_game(user_id=current_user.id, game_id=game_id)
            except Exception:
                pass
        try:
            manager.remove_session(session.session_id)
        except Exception:
            pass
        if isinstance(exc, httpx.HTTPStatusError):
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
        code = status.HTTP_409_CONFLICT if isinstance(exc, ValueError) else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail="Could not configure ranked game") from exc

    return {
        "session_id": session.session_id,
        "game_id": game_id,
        "opponent": catalog_entry(opponent.rung),
        "status": (
            await _remote(lambda: request.app.state.remote_client.get_ai_ladder_status(), "AI ladder status")
            if board
            else _status_payload(request, current_user, device_identity=_device_identity(request))
        ),
    }


class AiLadderOpponentPayload(BaseModel):
    """The opponent exactly as the board froze it when the game started."""

    model_config = ConfigDict(extra="forbid")

    rung: int = Field(ge=1, le=41)
    rank_name: str = Field(min_length=1)
    config_snapshot: dict
    certification_status: str = Field(min_length=1)
    availability: str = Field(min_length=1)
    route: Literal["local", "server"]


class AiLadderGameRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sgf_content: str = Field(min_length=1)
    result: str = Field(min_length=1)
    board_size: int
    rules: str = Field(min_length=1)
    komi: float
    move_count: int = Field(ge=0)
    player_black: str = Field(min_length=1)
    player_white: str = Field(min_length=1)
    source: Literal["play_ai"]
    category: Literal["game"]
    game_type: Literal["ai_ladder_ranked"]
    black_rank: Optional[str] = None
    white_rank: Optional[str] = None
    title: Optional[str] = None
    event: Optional[str] = None
    round_name: Optional[str] = None
    game_date: Optional[str] = None


class AiLadderSettlementSubmission(BaseModel):
    """One settled game, forwarded by the board that played it.

    The board is the authority for what happened at its own table (which game, which
    seat, which result, against which frozen rung). It is NOT the authority for the
    account's rank: this endpoint re-runs the same settlement against the cloud's own
    profile, so the cloud stays the single place ranks are decided across devices.
    """

    model_config = ConfigDict(extra="forbid")

    game_id: str = Field(min_length=1, max_length=64)
    user_color: Literal["B", "W"]
    result: Literal["win", "loss", "inconclusive"]
    game_type: str = Field(min_length=1)
    opponent: Optional[AiLadderOpponentPayload] = None
    engine_stalled: bool = False
    device_id: Optional[str] = Field(default=None, max_length=64)
    reservation_key: Optional[str] = Field(default=None, min_length=1, max_length=128)
    game_record: Optional[AiLadderGameRecordPayload] = None


@router.post("/settlements")
def submit_settlement(
    body: AiLadderSettlementSubmission,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Accept a settled ranked game from a board and apply it to the cloud profile.

    Idempotent by `game_id`: `settle_game` replays the first decision it recorded for a
    game rather than settling it twice, so a board that retries after a timeout (or
    after being unsure whether its POST landed) cannot move the rank twice.
    """
    _require_authority(request)
    opponent = None
    if body.opponent is not None:
        try:
            opponent = AiLadderOpponentSnapshot(**body.opponent.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        lifecycle = request.app.state.ai_ladder_repo.get_game_lifecycle(user_id=current_user.id, game_id=body.game_id)
        if isinstance(lifecycle, AiLadderBlockingGame):
            receipt = request.app.state.ai_ladder_repo.finalize_reserved_game(
                user_id=current_user.id,
                game_id=body.game_id,
                terminal_source="played_result",
                result=body.result,
                deciding_device_id=_device_id(request, required=False),
                reservation_key=body.reservation_key,
                game_record=body.game_record.model_dump() if body.game_record is not None else None,
                engine_stalled=body.engine_stalled,
            )
            outcome = receipt
        elif isinstance(lifecycle, AiLadderLifecycleReceipt):
            outcome = lifecycle
            receipt = lifecycle
        else:
            # No reservation and no ledger row: the cloud has never heard of this game.
            # A board cannot get here for a game it really played -- `/start` reserves
            # against the cloud first and raises 503 when that does not land, so a rated
            # game cannot begin without a reservation row. What is left is a request whose
            # every scoring input (result, rung, "certified", "available") was written by
            # the account that stands to gain from it. Record it, never count it.
            receipt = None
            outcome = request.app.state.ai_ladder_repo.settle_game(
                user_id=current_user.id,
                game_id=body.game_id,
                user_color=body.user_color,
                result=body.result,
                game_type=body.game_type,
                opponent=opponent,
                engine_stalled=body.engine_stalled,
                unreserved_origin=True,
            )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc

    logging.getLogger("katrain_web").info(
        "ai-ladder settlement from device %s: game=%s counted=%s reason=%s",
        body.device_id or "unknown",
        body.game_id,
        outcome.counted,
        outcome.reason,
    )
    response = {
        "game_id": body.game_id,
        "counted": outcome.counted,
        "replayed": outcome.replayed,
        "reason": outcome.reason,
        # The cloud's answer for this account, which is the one that counts across
        # devices. A board that disagrees is looking at a stale local profile.
        "profile": {
            "ai_ladder_rung": outcome.ai_ladder_rung,
            "placement_lo": outcome.placement_lo,
            "placement_hi": outcome.placement_hi,
            "placement_completed": outcome.placement_completed,
            "net_score": outcome.net_score,
        },
    }
    if receipt is not None:
        response["lifecycle"] = _lifecycle_payload(receipt)
    return response


@router.get("/settlements/{game_id}")
def get_settlement_receipt(
    game_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        lifecycle = request.app.state.ai_ladder_repo.get_game_lifecycle(user_id=current_user.id, game_id=game_id)
    except AiLadderLifecycleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found") from exc
    if isinstance(lifecycle, AiLadderBlockingGame):
        return {"state": "pending"}
    receipt = request.app.state.ai_ladder_repo.get_settlement_receipt(
        user_id=current_user.id,
        game_id=game_id,
    )
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found")
    return receipt
