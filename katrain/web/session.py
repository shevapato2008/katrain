import logging
import threading
import time
import uuid
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, List

from starlette.websockets import WebSocket

from katrain.web.core.ai_ladder_ranked import AI_LADDER_GAME_TYPE
from katrain.web.interface import WebKaTrain


@dataclass
class WebSession:
    session_id: str
    katrain: WebKaTrain
    user_id: Optional[int] = None  # Primary user (usually for AI play)
    player_b_id: Optional[int] = None  # For HvH
    player_w_id: Optional[int] = None  # For HvH
    mode: str = "play"  # "play" or "research"
    lock: threading.Lock = field(default_factory=threading.Lock)
    record_game_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    sockets: Set[WebSocket] = field(default_factory=set)
    last_access: float = field(default_factory=time.time)
    last_state: Optional[Dict] = None
    pending_count_request: Optional[int] = None  # User ID that initiated count request
    pending_count_timestamp: Optional[float] = None  # Timestamp of count request
    game_ended: bool = False

    def touch(self):
        self.last_access = time.time()


class SessionManager:
    def __init__(self, session_timeout=3600, max_sessions=100, enable_engine=True):
        self.session_timeout = session_timeout
        self.max_sessions = max_sessions
        self.enable_engine = enable_engine
        self._sessions: Dict[str, WebSession] = {}
        self._lock = threading.Lock()
        self._loop = None
        self._loop_thread_id = None

    def attach_loop(self, loop):
        self._loop = loop
        self._loop_thread_id = threading.get_ident()

    def create_session(
        self,
        katago_uuid: Optional[str] = None,
        user_id: Optional[int] = None,
        initial_game_type: str = "free",
        skip_initial_analysis: bool = False,
    ) -> WebSession:
        evicted: List[WebSession] = []
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                # 摘出来的会话在锁外关（见 `_cleanup_locked`）。名额检查仍然成立 ——
                # `_cleanup_locked` 已经把它们从 `_sessions` 里 pop 掉了，
                # 关引擎快不快不影响这个计数。
                evicted = self._cleanup_locked()
                if len(self._sessions) >= self.max_sessions:
                    self._shutdown_all(evicted)
                    raise RuntimeError("Session limit reached")
            session_id = uuid.uuid4().hex
            # Use provided UUID for KataGo requests if available, otherwise session_id
            engine_user_id = katago_uuid or session_id
            katrain = WebKaTrain(force_package_config=False, enable_engine=self.enable_engine, user_id=engine_user_id)
            session = WebSession(session_id=session_id, katrain=katrain, user_id=user_id)
            self._sessions[session_id] = session

        self._shutdown_all(evicted)

        session.katrain.update_state_callback = lambda state, sid=session_id: self._on_state(sid, state)
        session.katrain.message_callback = lambda msg_type, data, sid=session_id: self._on_message(sid, msg_type, data)
        katrain.start(game_type=initial_game_type, skip_initial_analysis=skip_initial_analysis)
        session.last_state = katrain.get_state()
        return session

    def create_research_session(self, user_id: int, katago_uuid: Optional[str] = None) -> WebSession:
        session = self.create_session(katago_uuid=katago_uuid, user_id=user_id)
        session.mode = "research"
        session.user_id = user_id
        return session

    def create_multiplayer_session(
        self,
        player_b_id: int,
        player_w_id: int,
        b_name: str = None,
        w_name: str = None,
        skip_initial_analysis: bool = False,
    ) -> WebSession:
        primary_user_id = player_b_id if player_b_id >= 0 else player_w_id if player_w_id >= 0 else None
        session = self.create_session(user_id=primary_user_id, skip_initial_analysis=skip_initial_analysis)
        session.player_b_id = player_b_id
        session.player_w_id = player_w_id

        # Set player names in KaTrain
        if b_name:
            session.katrain("update_player", bw="B", player_type="human", name=b_name)
        if w_name:
            session.katrain("update_player", bw="W", player_type="human", name=w_name)

        return session

    def get_session(self, session_id: str) -> WebSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(session_id)
            session.touch()
            return session

    def list_active_multiplayer_sessions(self) -> List[WebSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.player_b_id is not None]

    def ai_ladder_liveness_targets(self) -> List[tuple]:
        """`(user_id, game_id, reservation_key, origin_device_id)` per ranked game running here.

        The heartbeat has to be sent by whoever holds the reservation key, and the key never
        leaves this process -- `/start` mints it, hands it to the cloud, and keeps it on the
        session. So liveness is reported by the server that owns the session, not by the browser:
        a closed tab does not mean the game is gone, and the device the cloud is judging is the
        box, not the page.

        What is reported is "this game is still being played here", and the binding is
        `game_ended` -- the marker the engine sets the moment a result exists (`_on_state`).
        It is deliberately NOT the settlement state. The cloud rejects a settlement
        asynchronously, inside the sync worker, which marks its queue row `failed` and never
        touches this session: a box whose settlement was refused an hour ago would go on
        reporting a game nobody is playing, the reservation would stay `active` forever, and
        the takeover rule -- which only ever asks "has this box gone quiet" -- would never
        come true. The account is then locked out of ranked play on every device it owns.

        So the rule is the honest reading of the signal rather than a proxy for it: a heartbeat
        claims someone is at the board. Once the game is over, that claim is false, whatever
        the settlement is doing.
        """

        with self._lock:
            sessions = list(self._sessions.values())
        targets: Dict[tuple, tuple] = {}
        for session in sessions:
            if getattr(session, "game_type", None) != AI_LADDER_GAME_TYPE:
                continue
            if getattr(session, "game_ended", False):
                continue
            snapshot = getattr(session, "ai_ladder_snapshot", None)
            reservation_key = getattr(session, "ai_ladder_reservation_key", None)
            game_id = getattr(snapshot, "game_id", None)
            if session.user_id is None or not game_id or not reservation_key:
                continue
            # Keyed so two sessions on one game report once. The cloud counts heartbeats to tell
            # "this client keeps a timer alive" from "this client never will", and double-counting
            # would let one box cross that threshold at twice the rate it earned.
            targets[(session.user_id, game_id)] = (
                session.user_id,
                game_id,
                reservation_key,
                getattr(session, "ai_ladder_origin_device_id", None) or "cloud-local",
            )
        return list(targets.values())

    def remove_session(self, session_id: str):
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            session.katrain.shutdown()

    def broadcast_to_session(self, session_id: str, payload: Dict):
        try:
            session = self.get_session(session_id)
            self._schedule_broadcast(session, payload)
        except KeyError:
            pass

    def cleanup_expired(self):
        """回收过期会话。**同步方法，不要直接在事件循环上调用** —— 见 `_cleanup_locked`。"""
        with self._lock:
            evicted = self._cleanup_locked()
        # 关引擎在**锁外**做。理由见 `_cleanup_locked` 的注释。
        self._shutdown_all(evicted)

    @staticmethod
    def _shutdown_all(sessions: List[WebSession]):
        """逐个关停，一个失败不影响其余 —— 关停路径上再抛异常只会漏掉后面那些。"""
        for session in sessions:
            try:
                session.katrain.shutdown()
            except Exception:
                logging.getLogger("katrain_web").warning(
                    "shutting down session %s failed", session.session_id, exc_info=True
                )

    def _cleanup_locked(self) -> List[WebSession]:
        """在锁内把过期会话**摘出去**并返回，**不在这里关引擎**。

        2026-08-22 之前这里是就地 `session.katrain.shutdown()`，而那个 shutdown 会
        `t.join()` 三个线程、当时还没有超时。合起来的后果是：清理线程持着 `_lock`
        阻塞在 join 上，于是**每一个要取会话的请求都排在它后面**（`get_session`、
        `create_session`、`remove_session` 全都要这把锁）。本机抓到过现行：
        `sample` 采下来 25 个线程里 18 个的栈上都有 `lock_PyThread_acquire_lock`，
        主线程（uvloop 事件循环）也在其中 —— 服务进程还在、端口还听着、
        对所有请求不回话。那不是「慢」，是一条锁队列。

        锁内只做字典操作（O(n) 纯内存），关引擎放到锁外 ——
        `remove_session` 从一开始就是这么写的，这里只是补上同样的写法。
        """
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_access > self.session_timeout]
        evicted: List[WebSession] = []
        for sid in expired:
            session = self._sessions.pop(sid, None)
            if session:
                evicted.append(session)

        # Clean up expired count requests (60 second timeout)
        for session in self._sessions.values():
            if session.pending_count_request is not None and session.pending_count_timestamp is not None:
                if now - session.pending_count_timestamp > 60:
                    session.pending_count_request = None
                    session.pending_count_timestamp = None
                    # Broadcast timeout notification
                    self._schedule_broadcast(session, {"type": "count_timeout", "data": {}})

        return evicted

    def _on_state(self, session_id: str, state: Dict):
        try:
            session = self.get_session(session_id)
        except KeyError:
            return
        if state.get("end_result"):
            session.game_ended = True
        session.last_state = state
        state["sockets_count"] = len(session.sockets)
        self._schedule_broadcast(session, {"type": "game_update", "state": state})

    def _on_message(self, session_id: str, msg_type: str, data: Dict):
        try:
            session = self.get_session(session_id)
        except KeyError:
            return
        self._schedule_broadcast(session, {"type": msg_type, "data": data})

    def _schedule_broadcast(self, session: WebSession, payload: Dict):
        if not self._loop or not self._loop.is_running():
            return

        if threading.get_ident() == self._loop_thread_id:
            self._loop.create_task(self._broadcast_payload(session, payload))
        else:
            future = asyncio.run_coroutine_threadsafe(self._broadcast_payload(session, payload), self._loop)
            future.add_done_callback(
                lambda f: f.exception() and print(f"Error in broadcast task: {f.exception()}", flush=True)
            )

    async def _broadcast_payload(self, session: WebSession, payload: Dict):
        if not session.sockets:
            return
        stale = []
        for ws in list(session.sockets):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            session.sockets.discard(ws)


@dataclass
class Match:
    match_id: str
    player1_id: int
    player2_id: int
    game_type: str
    player1_socket: WebSocket
    player2_socket: WebSocket


class Matchmaker:
    def __init__(self):
        self._queues: Dict[str, List[Dict]] = {"rated": [], "free": []}
        self._lock = threading.Lock()

    def add_to_queue(self, user_id: int, game_type: str, websocket: WebSocket) -> Optional[Match]:
        import logging

        logger = logging.getLogger("katrain_web")
        with self._lock:
            queue = self._queues.get(game_type)
            if queue is None:
                logger.warning(f"Invalid game_type requested: {game_type}")
                return None

            # Check if user already in queue
            for entry in queue:
                if entry["user_id"] == user_id:
                    logger.info(f"User {user_id} already in {game_type} queue, updating socket.")
                    entry["websocket"] = websocket  # Update socket
                    return None

            # Check for existing match
            if queue:
                opponent = queue.pop(0)
                match_id = uuid.uuid4().hex
                logger.info(f"Match found in {game_type} queue! User {user_id} matched with User {opponent['user_id']}")
                return Match(
                    match_id=match_id,
                    player1_id=opponent["user_id"],
                    player2_id=user_id,
                    game_type=game_type,
                    player1_socket=opponent["websocket"],
                    player2_socket=websocket,
                )
            else:
                logger.info(f"Adding User {user_id} to {game_type} queue. Queue size now: {len(queue) + 1}")
                queue.append({"user_id": user_id, "websocket": websocket})
                return None

    def remove_from_queue(self, user_id: int):
        with self._lock:
            for queue in self._queues.values():
                for i, entry in enumerate(queue):
                    if entry["user_id"] == user_id:
                        queue.pop(i)
                        return


class LobbyManager:
    def __init__(self):
        self._online_users: Dict[int, Set[WebSocket]] = {}
        self._lock = threading.Lock()

    def add_user(self, user_id: int, websocket: WebSocket):
        with self._lock:
            if user_id not in self._online_users:
                self._online_users[user_id] = set()
            self._online_users[user_id].add(websocket)

    def remove_user(self, user_id: int, websocket: WebSocket):
        with self._lock:
            if user_id in self._online_users:
                self._online_users[user_id].discard(websocket)
                if not self._online_users[user_id]:
                    del self._online_users[user_id]

    def get_online_user_ids(self) -> List[int]:
        with self._lock:
            return list(self._online_users.keys())

    async def broadcast(self, payload: Dict):
        with self._lock:
            all_sockets = [ws for sockets in self._online_users.values() for ws in sockets]

        for ws in all_sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                pass
