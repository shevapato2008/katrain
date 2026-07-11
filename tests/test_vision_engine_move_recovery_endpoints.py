"""Endpoint tests for POST /vision/engine-move/retry and /vision/engine-move/cancel
(Task 8, review B4/M5, decision D8).

Uses httpx.AsyncClient + ASGITransport (per tests/platforms/test_engine_move_guards.py's
pattern) rather than the sync TestClient used by tests/test_vision_bind_state.py /
test_vision_api.py, because the concurrent-double-retry scenario needs two requests
genuinely in flight at once on the same event loop -- TestClient's sync wrapper
processes one request at a time and can't exercise that race.
"""

import asyncio

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints import vision
from katrain.web.core.engine_recovery import EngineRecoveryConfig, EngineRecoveryTracker
from katrain.web.platforms.gateway import PlatformMoveRejectedError


class FakeVision:
    def __init__(self, bound_session_id="s1"):
        self._bound = bound_session_id

    @property
    def bound_session_id(self):
        return self._bound


class FakeGateway:
    """`outcomes` is a FIFO queue of either a plain value (success) or an Exception
    to raise, consumed one per `play_move` call. `gate` (an asyncio.Event), if
    given, is awaited INSIDE play_move before consuming an outcome -- used to force
    two concurrent calls to actually overlap for the double-retry race test."""

    def __init__(self, outcomes=None, gate=None, release_after=0):
        self._outcomes = list(outcomes or ["ok"])
        self._gate = gate
        self._release_after = release_after
        self.calls = []

    async def play_move(self, session_id, col, row, user_id=0):
        self.calls.append((session_id, col, row))
        if self._gate is not None:
            if len(self.calls) >= self._release_after:
                self._gate.set()
            await asyncio.sleep(0)  # yield control at least once
        outcome = self._outcomes.pop(0) if self._outcomes else "ok"
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeOrchestrator:
    def __init__(self):
        self.entered_error = []
        self.cleared_error = 0
        self.entered_awaiting_removal = []

    def enter_engine_error(self, coords, token):
        self.entered_error.append((coords, token))

    def clear_engine_error(self):
        self.cleared_error += 1

    def enter_awaiting_removal(self, coords):
        self.entered_awaiting_removal.append(coords)


def _tracker(max_attempts=3, tokens=None):
    tokens = iter(tokens or [f"tok-{i}" for i in range(1, 20)])
    return EngineRecoveryTracker(
        EngineRecoveryConfig(engine_move_max_attempts=max_attempts), token_factory=lambda: next(tokens)
    )


def _tripped_tracker(coords=(3, 15), token="tok-1", game_id="g1"):
    """A tracker with one already-tripped active episode, as if the poller's
    threshold fired (Task 7). Extra fallback tokens are queued behind `token` so a
    subsequent trip_now() (e.g. retry-fails-again) has one to hand out."""
    t = _tracker(max_attempts=1, tokens=[token, "tok-fallback-1", "tok-fallback-2"])
    t.on_failure(game_id=game_id, coords=coords, reason="engine_error", detail="boom")
    return t


def _build_app(*, vision_obj=None, tracker=None, gateway=None, orchestrator="default"):
    app = FastAPI()
    app.include_router(vision.router, prefix="/api/v1/vision")
    app.state.vision = vision_obj if vision_obj is not None else FakeVision()
    if tracker is not None:
        app.state.engine_recovery = tracker
    if gateway is not None:
        app.state.platform_gateway = gateway
    if orchestrator == "default":
        app.state.physical_play = FakeOrchestrator()
    elif orchestrator is not None:
        app.state.physical_play = orchestrator
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestRetryHappyPath:
    @pytest.mark.asyncio
    async def test_retry_success_clears_reason_and_resumes_detection(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        gateway = FakeGateway(outcomes=["ok"])
        app = _build_app(tracker=tracker, gateway=gateway)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 200
        assert r.json() == {"ok": True}
        assert gateway.calls == [("s1", 3, 15)]
        assert tracker.active_episode is None
        assert app.state.physical_play.cleared_error == 1


class TestRetryFailsAgain:
    @pytest.mark.asyncio
    async def test_retry_fails_again_returns_new_token_stays_paused(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("still stuck", reason="engine_error")])
        app = _build_app(tracker=tracker, gateway=gateway)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 200  # per brief: failure-again is still HTTP 200
        body = r.json()
        assert body["ok"] is False
        assert body["detail"] == "still stuck"
        assert body["recovery_token"] and body["recovery_token"] != "tok-1"
        assert tracker.active_episode is not None
        assert tracker.active_episode.recovery_token == body["recovery_token"]
        # dialog stays up: orchestrator's error context re-armed with the new token
        assert app.state.physical_play.entered_error[-1] == ((3, 15), body["recovery_token"])
        assert app.state.physical_play.cleared_error == 0

    @pytest.mark.asyncio
    async def test_retry_fails_with_plain_exception_still_reports_ok_false(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        gateway = FakeGateway(outcomes=[RuntimeError("tunnel down")])
        app = _build_app(tracker=tracker, gateway=gateway)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert "tunnel down" in body["detail"]
        assert body["recovery_token"]


class TestRetryGuards409:
    @pytest.mark.asyncio
    async def test_stale_token_returns_409(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        gateway = FakeGateway()
        app = _build_app(tracker=tracker, gateway=gateway)

        async with _client(app) as ac:
            r = await ac.post(
                "/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-WRONG"}
            )

        assert r.status_code == 409
        assert gateway.calls == []
        assert tracker.active_episode is not None  # untouched

    @pytest.mark.asyncio
    async def test_no_active_episode_returns_409(self):
        tracker = _tracker()  # nothing tripped
        gateway = FakeGateway()
        app = _build_app(tracker=tracker, gateway=gateway)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 409
        assert gateway.calls == []

    @pytest.mark.asyncio
    async def test_unbound_session_mismatch_returns_409(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        gateway = FakeGateway()
        # vision bound to a DIFFERENT session than the one requesting retry.
        app = _build_app(vision_obj=FakeVision(bound_session_id="other-session"), tracker=tracker, gateway=gateway)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 409
        assert gateway.calls == []
        assert tracker.active_episode is not None  # untouched -- belongs to the bound session

    @pytest.mark.asyncio
    async def test_no_engine_recovery_tracker_returns_409(self):
        gateway = FakeGateway()
        app = _build_app(tracker=None, gateway=gateway)  # tracker never wired up

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 409
        assert gateway.calls == []


class TestRetryConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_double_retry_exactly_one_gateway_call(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        gate = asyncio.Event()
        gateway = FakeGateway(outcomes=["ok", "ok"], gate=gate, release_after=1)
        app = _build_app(tracker=tracker, gateway=gateway)

        async with _client(app) as ac1, _client(app) as ac2:
            r1, r2 = await asyncio.gather(
                ac1.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"}),
                ac2.post("/api/v1/vision/engine-move/retry", json={"session_id": "s1", "recovery_token": "tok-1"}),
            )

        statuses = sorted([r1.status_code, r2.status_code])
        assert statuses == [200, 409]  # exactly one winner, one loser
        assert len(gateway.calls) == 1  # exactly one submission reached the gateway


class TestCancelAwaitingRemoval:
    @pytest.mark.asyncio
    async def test_cancel_enters_awaiting_removal_and_returns_immediately(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        app = _build_app(tracker=tracker)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/cancel", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 200
        assert r.json() == {"ok": True, "awaiting_removal": True}
        assert tracker.active_episode is None  # consumed
        assert app.state.physical_play.entered_awaiting_removal == [(3, 15)]

    @pytest.mark.asyncio
    async def test_cancel_stale_token_returns_409(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        app = _build_app(tracker=tracker)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/cancel", json={"session_id": "s1", "recovery_token": "nope"})

        assert r.status_code == 409
        assert app.state.physical_play.entered_awaiting_removal == []
        assert tracker.active_episode is not None

    @pytest.mark.asyncio
    async def test_cancel_unbound_session_returns_409(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        app = _build_app(vision_obj=FakeVision(bound_session_id="other-session"), tracker=tracker)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/cancel", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_without_orchestrator_does_not_raise(self):
        tracker = _tripped_tracker(coords=(3, 15), token="tok-1")
        app = _build_app(tracker=tracker, orchestrator=None)

        async with _client(app) as ac:
            r = await ac.post("/api/v1/vision/engine-move/cancel", json={"session_id": "s1", "recovery_token": "tok-1"})

        assert r.status_code == 200
        assert r.json() == {"ok": True, "awaiting_removal": True}
