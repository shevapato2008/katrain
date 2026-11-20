"""Publication follows the live cursor, including legal backwards navigation."""

import asyncio
import importlib.util
import inspect
from pathlib import Path
import threading
from types import SimpleNamespace

import httpx
import pytest

from katrain.core.sgf_parser import Move
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.core.config import settings
from katrain.web.session import SessionManager


@pytest.fixture
def runtime_session(monkeypatch):
    import katrain.web.session as session_module

    spec = importlib.util.spec_from_file_location(
        "_publication_real_interface", Path(session_module.__file__).with_name("interface.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(session_module, "WebKaTrain", module.WebKaTrain)
    manager = SessionManager(enable_engine=False)
    session = manager.create_session(user_id=10, skip_initial_analysis=True)
    for index in range(15):
        session.katrain.game.play(Move((index, 0), player="B" if index % 2 == 0 else "W"), analyze=False)
    session.last_state = session.katrain.get_state()
    return manager, session


class _ContendedCommitLock:
    """Use the real RLock and expose whether the newer committer must wait."""

    def __init__(self, lock):
        self.lock = lock
        self.newer_thread_id = None
        self.contended_or_published = threading.Event()

    def __enter__(self):
        if threading.get_ident() == self.newer_thread_id:
            if not self.lock.acquire(blocking=False):
                self.contended_or_published.set()
                self.lock.acquire()
        else:
            self.lock.acquire()
        return self

    def __exit__(self, *_args):
        self.lock.release()

    def _is_owned(self):
        return self.lock._is_owned()


def test_snapshot_and_sync_publication_serialize_against_newer_commit(runtime_session, monkeypatch):
    manager, session = runtime_session
    runtime = session.katrain
    lock = _ContendedCommitLock(runtime.ai_ladder_commit_lock)
    runtime.ai_ladder_commit_lock = lock
    snapshot_taken = threading.Event()
    release_snapshot = threading.Event()
    old_thread_id = None
    errors = []
    published = []
    scheduled = []
    monkeypatch.setattr(manager, "_schedule_broadcast", lambda _session, payload: scheduled.append(payload))
    real_get_state = runtime.get_state

    def paused_old_snapshot():
        state = real_get_state()
        if threading.get_ident() == old_thread_id:
            snapshot_taken.set()
            assert release_snapshot.wait(2), "old snapshot was never released"
        return state

    def publish(state):
        manager._on_state(session.session_id, state)
        published.append(state["current_node_index"])

    def old_publication():
        nonlocal old_thread_id
        old_thread_id = threading.get_ident()
        try:
            runtime._broadcast_current_state([])
        except BaseException as exc:
            errors.append(exc)

    def newer_commit():
        lock.newer_thread_id = threading.get_ident()
        try:
            with lock:
                runtime.game.play(Move((15, 0), player="W"), analyze=False)
                runtime._broadcast_current_state([])
            lock.contended_or_published.set()
        except BaseException as exc:
            errors.append(exc)
            lock.contended_or_published.set()

    monkeypatch.setattr(runtime, "get_state", paused_old_snapshot)
    runtime.update_state_callback = publish
    old_worker = threading.Thread(target=old_publication)
    newer_worker = threading.Thread(target=newer_commit)
    old_worker.start()
    try:
        assert snapshot_taken.wait(2), "old publication never took its snapshot"
        newer_worker.start()
        assert lock.contended_or_published.wait(2), "newer commit never reached the commit lock"
    finally:
        release_snapshot.set()
        old_worker.join(2)
        if newer_worker.ident is not None:
            newer_worker.join(2)
    assert not old_worker.is_alive() and not newer_worker.is_alive()
    assert errors == []
    assert published == [15, 16]
    assert [payload["state"]["current_node_index"] for payload in scheduled] == [15, 16]
    assert session.last_state["current_node_index"] == 16

    # Cursor identity is authoritative; a legitimate undo must still publish 15.
    with lock:
        runtime.game.undo(1)
    runtime._broadcast_current_state([])
    assert published == [15, 16, 15]
    assert session.last_state["current_node_index"] == 15


def test_post_broadcast_runs_after_commit_and_throttle_locks_are_released(runtime_session):
    _, session = runtime_session
    runtime = session.katrain
    observed = []

    def after_state(state):
        assert runtime._broadcast_lock.acquire(blocking=False), "throttle lock must be released before hooks"
        runtime._broadcast_lock.release()
        observed.append((runtime.ai_ladder_commit_lock._is_owned(), state["current_node_index"]))

    runtime.update_state(_force=True, _post_broadcast=after_state)
    assert observed == [(False, 15)]
    assert runtime._broadcast_lock.acquire(blocking=False)
    runtime._broadcast_lock.release()


@pytest.mark.asyncio
@pytest.mark.parametrize("yield_first_socket", [False, True])
async def test_thread_and_loop_publications_reach_both_sockets_in_order(runtime_session, yield_first_socket):
    manager, session = runtime_session
    manager.attach_loop(asyncio.get_running_loop())
    first_state_started = asyncio.Event()
    release_old_send = asyncio.Event()

    class Socket:
        def __init__(self):
            self.received = []
            self.complete = asyncio.Event()

        async def send_json(self, payload):
            if self is first_socket and payload["type"] == "game_update":
                first_state_started.set()
                if yield_first_socket and payload["state"]["current_node_index"] == 15:
                    await release_old_send.wait()
            self.received.append(payload)
            if len(self.received) == 4:
                self.complete.set()

    session.sockets = {Socket(), Socket()}
    first_socket = next(iter(session.sockets))

    def publish_move(index):
        manager._schedule_broadcast(
            session, {"type": "game_update", "state": {"current_node_index": index, "current_node_id": index}}
        )
        manager._schedule_broadcast(session, {"type": "sound", "data": {"after_node_id": index}})

    worker = threading.Thread(target=publish_move, args=(15,))
    worker.start()
    worker.join(2)
    assert not worker.is_alive()
    # No event-loop yield between the completed background enqueue and this call.
    publish_move(16)
    await asyncio.wait_for(first_state_started.wait(), 2)
    release_old_send.set()
    await asyncio.wait_for(asyncio.gather(*(ws.complete.wait() for ws in session.sockets)), 2)
    for socket in session.sockets:
        received = [
            (
                payload["type"],
                payload.get("state", {}).get("current_node_index", payload.get("data", {}).get("after_node_id")),
            )
            for payload in socket.received
        ]
        assert received == [("game_update", 15), ("sound", 15), ("game_update", 16), ("sound", 16)]


def _app_with_session(monkeypatch, session):
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    app = create_app(enable_engine=False)
    app.state.session_manager._sessions[session.session_id] = session
    owner = SimpleNamespace(id=10, username="owner")
    app.dependency_overrides[get_current_user_optional] = lambda: owner
    return app


def test_private_get_cannot_replace_newer_canonical_publication(runtime_session, monkeypatch):
    from katrain.web.core import paid_analysis

    manager, session = runtime_session
    runtime = session.katrain
    app = _app_with_session(monkeypatch, session)
    # Publish into the manager used by the mounted route, just like a live session.
    manager = app.state.session_manager
    runtime.update_state_callback = lambda state: manager._on_state(session.session_id, state)
    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    stripping_old_response = threading.Event()
    release_response = threading.Event()
    responses = []
    errors = []
    real_strip = paid_analysis.strip_private_analysis

    def pause_response_projection(state):
        clean = real_strip(state)
        # get_state also strips under its commit lock. Pause only the route's
        # independent projection, after that snapshot lock has been released.
        if not runtime.ai_ladder_commit_lock._is_owned() and state["current_node_index"] == 15:
            stripping_old_response.set()
            assert release_response.wait(2), "GET response projection was never released"
        return clean

    monkeypatch.setattr(paid_analysis, "strip_private_analysis", pause_response_projection)

    async def fetch():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get("/api/state", params={"session_id": session.session_id})

    def get_old_response():
        try:
            responses.append(asyncio.run(fetch()))
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=get_old_response)
    worker.start()
    try:
        assert stripping_old_response.wait(2), "GET never reached its old response projection"
        with runtime.ai_ladder_commit_lock:
            runtime.game.play(Move((15, 0), player="W"), analyze=False)
        runtime._broadcast_current_state([])
        canonical = session.last_state
        assert canonical["current_node_index"] == 16
    finally:
        release_response.set()
        worker.join(2)
    assert not worker.is_alive() and errors == []
    assert responses[0].status_code == 200, responses[0].text
    assert responses[0].json()["state"]["current_node_index"] == 15
    assert session.last_state is canonical
    response = asyncio.run(fetch())
    assert response.status_code == 200, response.text
    assert response.json()["state"]["current_node_index"] == 16
    assert response.json()["state"]["analysis"] is None


@pytest.mark.asyncio
async def test_local_get_reads_live_cursor_without_changing_canonical_cache(runtime_session, monkeypatch):
    _, session = runtime_session
    app = _app_with_session(monkeypatch, session)
    cached = session.last_state
    cached.pop("sockets_count", None)
    cached.pop("spectator_count", None)
    with session.katrain.ai_ladder_commit_lock:
        session.katrain.game.play(Move((15, 0), player="W"), analyze=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/state", params={"session_id": session.session_id})
    assert response.status_code == 200, response.text
    assert response.json()["state"]["current_node_index"] == 16
    assert session.last_state is cached and cached["current_node_index"] == 15
    assert "sockets_count" not in cached and "spectator_count" not in cached


def test_central_read_projects_mirror_without_mutating_it(runtime_session, monkeypatch):
    _, session = runtime_session
    app = _app_with_session(monkeypatch, session)
    session.game_type = "pvp_lobby"
    session.last_state = {"current_node_index": 43, "timer": {"paused": False}}
    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "legacy")
    session.katrain.membership_guard_active = False
    app.state.membership_guard_active = False
    endpoint = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/api/state")
    state_for_read = inspect.getclosurevars(endpoint).nonlocals["session_state_for_read"]
    state = state_for_read(session)
    assert state["current_node_index"] == 43
    assert "sockets_count" not in session.last_state and "spectator_count" not in session.last_state
    state["timer"]["paused"] = True
    assert session.last_state["timer"]["paused"] is False
