"""Pure-logic reason-transition table for the engine-move recovery episode
tracker (Task 7, review B5/M1/M4/m2). No asyncio, no I/O -- see engine_recovery.py.
"""

import pytest

from katrain.web.core.engine_recovery import (
    EngineRecoveryConfig,
    EngineRecoveryTracker,
)


def _tracker(max_attempts=3, tokens=None):
    tokens = iter(tokens or [f"tok-{i}" for i in range(1, 10)])
    return EngineRecoveryTracker(
        EngineRecoveryConfig(engine_move_max_attempts=max_attempts), token_factory=lambda: next(tokens)
    )


class TestCountedReasons:
    """engine_error / position_changed: same (game_id, coords) episode +1; below
    threshold -> re-arm; at threshold -> stop re-arming + trip a token."""

    @pytest.mark.parametrize("reason", ["engine_error", "position_changed"])
    def test_below_threshold_rearms_and_counts(self, reason):
        t = _tracker(max_attempts=3)
        o1 = t.on_failure(game_id="g1", coords=(3, 3), reason=reason, detail="e1")
        assert o1.rearm is True and o1.enter_engine_error is False
        assert o1.episode.count == 1 and o1.episode.recovery_token is None
        o2 = t.on_failure(game_id="g1", coords=(3, 3), reason=reason, detail="e2")
        assert o2.rearm is True
        assert o2.episode.count == 2

    @pytest.mark.parametrize("reason", ["engine_error", "position_changed"])
    def test_threshold_stops_rearm_and_trips_token(self, reason):
        t = _tracker(max_attempts=3, tokens=["tok-x"])
        t.on_failure(game_id="g1", coords=(3, 3), reason=reason)
        t.on_failure(game_id="g1", coords=(3, 3), reason=reason)
        o3 = t.on_failure(game_id="g1", coords=(3, 3), reason=reason, detail="boom")
        assert o3.rearm is False
        assert o3.enter_engine_error is True
        assert o3.episode.count == 3
        assert o3.episode.recovery_token == "tok-x"
        assert o3.episode.detail == "boom"
        assert t.active_episode is o3.episode

    def test_mixed_engine_error_and_position_changed_share_one_episode(self):
        t = _tracker(max_attempts=3)
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        o2 = t.on_failure(game_id="g1", coords=(3, 3), reason="position_changed")
        assert o2.episode.count == 2

    def test_already_tripped_episode_does_not_re_trip(self):
        t = _tracker(max_attempts=1, tokens=["tok-a", "tok-b"])
        first = t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        assert first.enter_engine_error is True and first.episode.recovery_token == "tok-a"
        again = t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        assert again.rearm is False
        assert again.enter_engine_error is False  # not re-fired
        assert again.episode.recovery_token == "tok-a"  # token unchanged


class TestPendingReason:
    def test_pending_does_not_count_or_touch_episode_and_rearms(self):
        t = _tracker()
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")  # count=1
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="pending")
        assert o.rearm is True
        assert o.episode.count == 1  # untouched by "pending"

    def test_pending_with_no_active_episode(self):
        t = _tracker()
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="pending")
        assert o.rearm is True and o.episode is None


class TestIllegalMoveReason:
    def test_illegal_move_does_not_count_and_rearms(self):
        t = _tracker()
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")  # count=1
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="illegal_move")
        assert o.rearm is True
        assert o.episode.count == 1


class TestGameEndedReason:
    def test_game_ended_clears_episode_and_does_not_rearm(self):
        t = _tracker()
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="game_ended")
        assert o.rearm is False
        assert o.episode is None
        assert t.active_episode is None

    def test_game_ended_with_no_active_episode(self):
        t = _tracker()
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="game_ended")
        assert o.rearm is False and o.episode is None


class TestUnknownReasonPassesThrough:
    def test_move_rejected_default_passes_through_like_pending(self):
        t = _tracker()
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="move_rejected")
        assert o.rearm is True
        assert o.episode.count == 1


class TestEpisodeIdentity:
    """review m2: coords change -> new episode (old discarded); success/session
    missing/unbind all clear via tracker.clear()/on_success()."""

    def test_coords_change_starts_new_episode(self):
        t = _tracker(max_attempts=3)
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        o = t.on_failure(game_id="g1", coords=(4, 4), reason="engine_error")
        assert o.episode.count == 1  # NOT 3 -- old episode discarded
        assert o.episode.coords == (4, 4)

    def test_game_id_change_starts_new_episode(self):
        t = _tracker(max_attempts=3)
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        o = t.on_failure(game_id="g2", coords=(3, 3), reason="engine_error")
        assert o.episode.count == 1

    def test_on_success_clears_episode(self):
        t = _tracker(max_attempts=3)
        t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        t.on_success()
        assert t.active_episode is None
        # a fresh failure afterwards starts a brand-new count, not a continuation
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        assert o.episode.count == 1

    def test_clear_is_idempotent(self):
        t = _tracker()
        t.clear()
        t.clear()
        assert t.active_episode is None


class TestDefaultTokenFactory:
    def test_default_config_max_attempts_is_three(self):
        assert EngineRecoveryConfig().engine_move_max_attempts == 3

    def test_default_token_factory_produces_a_uuid_like_string(self):
        t = EngineRecoveryTracker(EngineRecoveryConfig(engine_move_max_attempts=1))
        o = t.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        assert isinstance(o.episode.recovery_token, str)
        assert len(o.episode.recovery_token) >= 32  # uuid4 hex/str length ballpark
