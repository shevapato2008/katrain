"""Real observers are authenticated people, independently of transport or bot seats."""

import asyncio
from unittest.mock import MagicMock

import pytest

from katrain.web.session import SessionManager, WebSession


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def presence(clock=None):
    from katrain.web.core.pvp_spectator_presence import PvpSpectatorPresence

    return PvpSpectatorPresence(clock=clock or Clock())


def test_bot_seats_and_players_do_not_create_observers():
    watchers = presence()
    assert watchers.count((-1, -2), set()) == 0
    owner, viewer = object(), object()
    watchers.join_socket(owner, 1)
    watchers.join_socket(viewer, 3)
    watchers.touch_http(1)
    watchers.touch_http(2)
    assert watchers.count((1, 2), {owner, viewer}) == 1


def test_duplicate_tabs_and_http_share_one_identity_until_last_transport_leaves():
    clock = Clock()
    watchers = presence(clock)
    first, second = object(), object()
    live = {first, second}
    watchers.join_socket(first, 7)
    watchers.join_socket(second, 7)
    watchers.touch_http(7)
    assert watchers.count((-1, -2), live) == 1
    watchers.leave_socket(first)
    live.remove(first)
    assert watchers.count((-1, -2), live) == 1
    watchers.leave_socket(second)
    live.remove(second)
    assert watchers.count((-1, -2), live) == 1
    clock.now += 10
    assert watchers.count((-1, -2), live) == 0


def test_http_ttl_uses_each_users_latest_monotonic_heartbeat():
    clock = Clock()
    watchers = presence(clock)
    watchers.touch_http(7)
    clock.now += 6
    watchers.touch_http(8)
    clock.now += 4
    assert watchers.count((-1, -2), set()) == 1
    assert watchers.next_deadline() == 116
    watchers.touch_http(7)
    clock.now += 6
    assert watchers.count((-1, -2), set()) == 1
    assert watchers.next_deadline() == 120
    clock.now += 4
    assert watchers.count((-1, -2), set()) == 0
    assert watchers.next_deadline() is None


@pytest.mark.parametrize("user_id", [None, -2, 0, True, "7"])
def test_unauthenticated_or_invalid_identities_do_not_count(user_id):
    watchers = presence()
    ws = object()
    watchers.join_socket(ws, user_id)
    watchers.touch_http(user_id)
    assert watchers.count((-1, -2), {ws}) == 0


def test_stale_socket_membership_and_current_player_seats_are_respected():
    watchers = presence()
    stale, live = object(), object()
    watchers.join_socket(stale, 7)
    watchers.join_socket(live, 8)
    assert watchers.count((-1, -2), {live}) == 1
    assert watchers.count((8, -2), {live}) == 0
    assert watchers.count((-1, -2), {live, stale}) == 1


class Handle:
    def __init__(self, deadline, callback, args):
        self.deadline, self.callback, self.args = deadline, callback, args
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class Scheduler:
    def __init__(self, clock):
        self.clock, self.handles = clock, []

    def is_running(self):
        return True

    def call_later(self, delay, callback, *args):
        handle = Handle(self.clock.now + delay, callback, args)
        self.handles.append(handle)
        return handle

    def fire_due(self):
        for handle in list(self.handles):
            if not handle.cancelled and handle.deadline <= self.clock.now:
                handle.cancelled = True
                handle.callback(*handle.args)


def managed_room():
    clock = Clock()
    manager = SessionManager(enable_engine=False)
    manager.attach_loop(Scheduler(clock))
    manager._schedule_broadcast = MagicMock()
    session = WebSession("room", MagicMock(), player_b_id=-1, player_w_id=-2)
    session.spectator_presence = presence(clock)
    manager._sessions[session.session_id] = session
    return manager, session, clock


def test_http_join_pushes_existing_clients_and_quiet_room_expiry_pushes_without_state_reads():
    manager, session, clock = managed_room()
    session.sockets.add(object())
    manager.touch_http_spectator(session, 7)
    assert manager._schedule_broadcast.call_args.args == (
        session,
        {"type": "spectator_count", "count": 1, "spectator_count": 1},
    )
    last_access = session.last_access
    # A list/state read may prune first; the timer still needs to publish the decrement.
    clock.now += 10
    assert session.spectator_presence.count((-1, -2), session.sockets) == 0
    manager._loop.fire_due()
    assert manager._schedule_broadcast.call_args.args == (
        session,
        {"type": "spectator_count", "count": 1, "spectator_count": 0},
    )
    assert manager._schedule_broadcast.call_count == 2
    assert session.last_access == last_access
    assert all(handle.cancelled for handle in manager._loop.handles)
    session.katrain.get_state.assert_not_called()


def test_heartbeat_rearms_one_timer_and_session_removal_cancels_it():
    manager, session, clock = managed_room()
    manager.touch_http_spectator(session, 7)
    clock.now += 6
    manager.touch_http_spectator(session, 7)
    active = [handle for handle in manager._loop.handles if not handle.cancelled]
    assert len(active) == 1 and active[0].deadline == 116
    assert manager._schedule_broadcast.call_count == 1
    manager.remove_session(session.session_id)
    assert active[0].cancelled
    assert session.spectator_presence.count((-1, -2), set()) == 0
    clock.now += 10
    manager._loop.fire_due()
    assert manager._schedule_broadcast.call_count == 1


def test_replaced_session_cannot_receive_old_expiry_broadcast():
    manager, session, clock = managed_room()
    manager.touch_http_spectator(session, 7)
    replacement = WebSession("room", MagicMock(), player_b_id=-1, player_w_id=-2)
    manager._sessions["room"] = replacement
    clock.now += 10
    manager._loop.fire_due()
    assert manager._schedule_broadcast.call_count == 1
    assert replacement.spectator_presence.count((-1, -2), set()) == 0


def test_shutdown_clears_socket_and_http_memberships_and_cancels_timer():
    manager, session, _ = managed_room()
    ws = object()
    session.sockets.add(ws)
    session.spectator_presence.join_socket(ws, 8)
    manager.touch_http_spectator(session, 7)
    manager.clear_spectator_presence()
    assert session.spectator_presence.count((-1, -2), session.sockets) == 0
    assert all(handle.cancelled for handle in manager._loop.handles)
    session.spectator_presence.touch_http(7)
    session.spectator_presence.join_socket(ws, 8)
    assert session.spectator_presence.count((-1, -2), session.sockets) == 0


def test_state_callback_keeps_raw_socket_count_and_adds_unique_observers():
    manager, session, _ = managed_room()
    first, second = object(), object()
    session.sockets.update((first, second))
    session.spectator_presence.join_socket(first, 7)
    session.spectator_presence.join_socket(second, 7)
    state = {"stones": []}
    manager._on_state(session.session_id, state)
    assert state["sockets_count"] == 2
    assert state["spectator_count"] == 1


@pytest.mark.asyncio
async def test_failed_broadcast_removes_socket_identity_and_updates_remaining_client():
    manager = SessionManager(enable_engine=False)
    manager.attach_loop(asyncio.get_running_loop())
    manager._schedule_broadcast = MagicMock()
    session = WebSession("room", MagicMock(), player_b_id=1, player_w_id=2)
    manager._sessions["room"] = session
    stale, live = MagicMock(), MagicMock()

    async def fail(payload):
        raise RuntimeError("gone")

    async def send(payload):
        return None

    stale.send_json.side_effect, live.send_json.side_effect = fail, send
    session.sockets.update((stale, live))
    session.spectator_presence.join_socket(stale, 7)
    session.spectator_presence.join_socket(live, 8)
    manager.broadcast_spectator_count(session, force=True)
    await manager._broadcast_payload(session, {"type": "game_update", "state": {}})
    assert session.spectator_presence.count((1, 2), session.sockets) == 1
    assert manager._schedule_broadcast.call_args.args[1] == {
        "type": "spectator_count",
        "count": 1,
        "spectator_count": 1,
    }
