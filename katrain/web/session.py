import threading
import time
import uuid
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, List

from starlette.websockets import WebSocket

from katrain.web.interface import WebKaTrain


@dataclass
class WebSession:
    session_id: str
    katrain: WebKaTrain
    user_id: Optional[int] = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    sockets: Set[WebSocket] = field(default_factory=set)
    last_access: float = field(default_factory=time.time)
    last_state: Optional[Dict] = None

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

    def create_session(self) -> WebSession:
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                self._cleanup_locked()
                if len(self._sessions) >= self.max_sessions:
                    raise RuntimeError("Session limit reached")
            session_id = uuid.uuid4().hex
            katrain = WebKaTrain(force_package_config=False, enable_engine=self.enable_engine, user_id=session_id)
            session = WebSession(session_id=session_id, katrain=katrain)
            self._sessions[session_id] = session

        session.katrain.update_state_callback = lambda state, sid=session_id: self._on_state(sid, state)
        session.katrain.message_callback = lambda msg_type, data, sid=session_id: self._on_message(sid, msg_type, data)
        katrain.start()
        session.last_state = katrain.get_state()
        return session

    def get_session(self, session_id: str) -> WebSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(session_id)
            session.touch()
            return session

    def remove_session(self, session_id: str):
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            session.katrain.shutdown()

    def cleanup_expired(self):
        with self._lock:
            self._cleanup_locked()

    def _cleanup_locked(self):
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_access > self.session_timeout]
        for sid in expired:
            session = self._sessions.pop(sid, None)
            if session:               session.katrain.shutdown()

    def _on_state(self, session_id: str, state: Dict):
        try:
            session = self.get_session(session_id)
        except KeyError:
            return
        session.last_state = state
        self._schedule_broadcast(session, {"type": "game_update", "state": state})

    def _on_message(self, session_id: str, msg_type: str, data: Dict):
        try:            session = self.get_session(session_id)
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
            future.add_done_callback(lambda f: f.exception() and print(f"Error in broadcast task: {f.exception()}", flush=True))

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
