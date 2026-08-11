"""Transactional domain rules for the independent 41-rung ranked-AI ladder."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from types import SimpleNamespace
from threading import Barrier, BrokenBarrierError

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from katrain.core.ladder import LADDER_LEVELS
from katrain.web.core import migrations, models_db
from katrain.web.core.ai_ladder_ranked import (
    AI_LADDER_GAME_TYPE,
    AiLadderLifecycleConflict,
    AiLadderLifecycleNotFound,
    AiLadderOpponentSnapshot,
    AiLadderRankedRepository,
    InvalidReservationKey,
    initial_placement_window,
)


EXPECTED_RANK_NAMES = [
    *(f"{rank}级" for rank in range(20, 0, -1)),
    *(label for rank in range(1, 10) for label in (f"准{rank}段", f"{rank}段")),
    "职业水平",
    "职业顶尖",
    "超越人类",
]


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def user(session_factory):
    with session_factory() as db:
        user = models_db.User(username="fan", hashed_password="x", rank="5d", net_wins=2)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


@pytest.fixture
def opponent():
    return AiLadderOpponentSnapshot(
        rung=16,
        rank_name="5级",
        config_snapshot={"config_digest": "fixture-certified-rung-16", "config_version": "fixture-v1"},
        certification_status="certified",
        availability="available",
        route="server",
    )


def settle(repo, user_id, game_id, result, opponent, *, game_type=AI_LADDER_GAME_TYPE, engine_stalled=False):
    return repo.settle_game(
        user_id=user_id,
        game_id=game_id,
        user_color="B",
        result=result,
        game_type=game_type,
        opponent=opponent,
        engine_stalled=engine_stalled,
    )


def placed_profile(session_factory, user_id, rung, *, net_score=0):
    with session_factory() as db:
        profile = models_db.AiLadderProfile(
            user_id=user_id,
            ai_ladder_rung=rung,
            placement_lo=rung,
            placement_hi=rung,
            placement_completed=5,
            net_score=net_score,
        )
        db.add(profile)
        db.commit()


def file_session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ai-ladder-ranked.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 3},
    )
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def concurrent_repo(session_factory):
    repo = AiLadderRankedRepository(session_factory)
    apply_barrier = Barrier(2)
    original_apply = repo._apply_result

    def synchronized_apply(profile, result):
        try:
            apply_barrier.wait(timeout=0.5)
        except BrokenBarrierError:
            pass
        original_apply(profile, result)

    repo._apply_result = synchronized_apply
    return repo


def reserve(
    repo, user_id, opponent, *, game_id="b" * 32, user_color="B", device_id="device-a", reservation_key="f" * 43
):
    return repo.reserve_game(
        user_id=user_id,
        game_id=game_id,
        user_color=user_color,
        opponent=opponent,
        origin_device_id=device_id,
        ai_subtype="ai:ladder",
        execution_identity="fixture-identity",
        rules_snapshot={"board_size": 19, "rules": "chinese", "komi": 7.5},
        time_control_snapshot={"main_time_seconds": 600, "byo_yomi_periods": 3, "byo_yomi_seconds": 30},
        reservation_key=reservation_key,
    )


def complete_game_record(*, user_color="B", result="win"):
    winner = user_color if result == "win" else ("W" if user_color == "B" else "B")
    return {
        "sgf_content": f"(;GM[1]FF[4]SZ[19]RU[Chinese]KM[7.5]PB[User]PW[AI]RE[{winner}+R])",
        "result": f"{winner}+R",
        "board_size": 19,
        "rules": "chinese",
        "komi": 7.5,
        "move_count": 0,
        "player_black": "User" if user_color == "B" else "AI",
        "player_white": "AI" if user_color == "B" else "User",
        "source": "play_ai",
        "category": "game",
        "game_type": AI_LADDER_GAME_TYPE,
    }


def test_account_reservation_freezes_contract_and_same_key_replay_is_idempotent(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)

    created = reserve(repo, user.id, opponent)
    replay = reserve(repo, user.id, opponent)

    assert created.created and created.reservation_key
    assert len(created.reservation_key) >= 43
    assert not replay.created and replay.reservation_key == created.reservation_key
    assert replay.game == created.game
    with pytest.raises(AiLadderLifecycleConflict):
        reserve(repo, user.id, opponent, reservation_key="different-key")
    assert repo.get_blocking_game(user.id) == created.game
    with session_factory() as db:
        row = db.get(models_db.AiLadderActiveGame, created.game.game_id)
        assert row.reservation_key_hash != created.reservation_key
        assert len(row.reservation_key_hash) == 64
        assert row.origin_device_id == "device-a"
        assert row.rules_snapshot == {"board_size": 19, "rules": "chinese", "komi": 7.5}
        assert row.time_control_snapshot["byo_yomi_periods"] == 3
        assert row.opponent_config_snapshot == opponent.config_snapshot


def test_one_reservation_per_account_but_different_accounts_are_independent(session_factory, user, opponent):
    with session_factory() as db:
        other = models_db.User(username="other", hashed_password="x")
        db.add(other)
        db.commit()
        other_id = other.id
    repo = AiLadderRankedRepository(session_factory)
    reserve(repo, user.id, opponent, game_id="1" * 32)

    with pytest.raises(AiLadderLifecycleConflict):
        reserve(repo, user.id, opponent, game_id="2" * 32)
    second = reserve(repo, other_id, opponent, game_id="3" * 32, device_id="device-b")

    assert second.game.user_id == other_id


def test_stale_unactivated_reservation_is_lazily_released(session_factory, user, opponent):
    from datetime import datetime, timedelta

    repo = AiLadderRankedRepository(session_factory)
    first = reserve(repo, user.id, opponent, game_id="1" * 32)
    with session_factory() as db:
        row = db.get(models_db.AiLadderActiveGame, first.game.game_id)
        row.created_at = datetime.utcnow() - timedelta(minutes=6)
        db.commit()

    assert repo.get_blocking_game(user.id) is None
    second = reserve(repo, user.id, opponent, game_id="2" * 32, reservation_key="s" * 43)
    assert second.created is True


def test_origin_transitions_require_constant_time_secret_and_cancel_only_reserved(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, opponent)

    with pytest.raises(InvalidReservationKey):
        repo.activate_reservation(
            user_id=user.id,
            game_id=reservation.game.game_id,
            reservation_key="wrong",
            origin_device_id="device-a",
            origin_session_id="session-a",
        )
    assert repo.get_blocking_game(user.id).state == "reserved"

    active = repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    assert (active.state, active.origin_session_id) == ("active", "session-a")
    with pytest.raises(AiLadderLifecycleConflict):
        repo.cancel_reservation(
            user_id=user.id,
            game_id=reservation.game.game_id,
            reservation_key=reservation.reservation_key,
            origin_device_id="device-a",
        )
    pending = repo.mark_pending_settlement(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
    )
    assert pending.state == "pending_settlement"


def test_cross_account_lifecycle_lookups_are_not_found(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, opponent)

    assert repo.get_game_lifecycle(user_id=user.id + 999, game_id=reservation.game.game_id) is None
    with pytest.raises(AiLadderLifecycleNotFound):
        repo.activate_reservation(
            user_id=user.id + 999,
            game_id=reservation.game.game_id,
            reservation_key=reservation.reservation_key,
            origin_device_id="device-a",
            origin_session_id="x",
        )


def test_played_result_finalizes_user_game_ledger_profile_and_provenance_once(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )

    first = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="played_result",
        result="win",
        deciding_device_id="device-a",
        reservation_key=reservation.reservation_key,
        game_record=complete_game_record(),
    )
    replay = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-b",
    )

    assert (first.state, first.result, first.replayed) == ("settled", "win", False)
    assert (replay.state, replay.result, replay.replayed) == ("settled", "win", True)
    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).count() == 0
        assert db.query(models_db.UserGame).count() == 1
        game = db.get(models_db.UserGame, reservation.game.game_id)
        assert (game.source, game.game_type, game.origin_device_id) == (
            "play_ai",
            AI_LADDER_GAME_TYPE,
            "device-a",
        )
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert (ledger.origin_device_id, ledger.deciding_device_id, ledger.terminal_source) == (
            "device-a",
            "device-a",
            "played_result",
        )
        profile = db.get(models_db.AiLadderProfile, user.id)
        assert (profile.placement_completed, profile.version) == (1, 1)


def test_remote_resign_cannot_overwrite_a_result_awaiting_delivery(session_factory, user, opponent):
    """A game the user already finished must not be resignable from a second device.

    `pending_settlement` means "played out locally, the box is delivering the result" -- the
    outcome exists, it just has not arrived. `remote_resign` skips the origin check by design
    (that is what makes the cross-device escape hatch work at all), and it used to skip the
    state check with it: a second device could resign a *finished* game, and because the ledger
    is written first-wins, the real result was then permanently replayed as that loss. The user
    lost a won game, their rating moved the wrong way, and `user_games` kept a fabricated
    0-move SGF in place of the real one.

    Resigning an `active` game stays allowed -- that is the user abandoning a game in progress,
    which is theirs to do. The line is drawn at "a result already exists".
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    repo.mark_pending_settlement(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
    )

    with pytest.raises(AiLadderLifecycleConflict):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source="remote_resign",
            result="loss",
            deciding_device_id="device-b",
        )

    # The reservation is still standing and still says a result is on its way, so the origin
    # box can still deliver the game the user actually played.
    with session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id).state == "pending_settlement"

    delivered = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="played_result",
        result="win",
        deciding_device_id="device-a",
        reservation_key=reservation.reservation_key,
        game_record=complete_game_record(),
    )
    assert (delivered.result, delivered.replayed) == ("win", False)


def _activated(repo, user, opponent, *, device_id="device-a"):
    reservation = reserve(repo, user.id, replace(opponent, rung=25), device_id=device_id)
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id=device_id,
        origin_session_id="session-a",
    )
    return reservation


def test_the_origin_device_may_always_resign_its_own_live_game(session_factory, user, opponent):
    """The threshold gates reaching in from elsewhere, never resigning where you are playing."""

    repo = AiLadderRankedRepository(session_factory)
    reservation = _activated(repo, user, opponent)
    for _ in range(2):
        repo.record_heartbeat(
            user_id=user.id,
            game_id=reservation.game.game_id,
            reservation_key=reservation.reservation_key,
            origin_device_id="device-a",
        )

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-a",
    )
    assert (receipt.result, receipt.replayed) == ("loss", False)


def test_a_client_that_never_heartbeats_keeps_the_unconditional_escape_hatch(session_factory, user, opponent):
    """Web clients send no heartbeat, and denying them would strand the very accounts we are freeing.

    This is the one place the go ladder deliberately differs from the gomoku track: there
    takeover is a new capability and defaults closed, here it already exists and defaulting
    closed would be a regression.
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = _activated(repo, user, opponent, device_id="cloud-local")

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="some-other-browser",
    )
    assert receipt.result == "loss"


def test_heartbeat_is_origin_only_and_does_not_resurrect_a_settled_game(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = _activated(repo, user, opponent)

    with pytest.raises(InvalidReservationKey):
        repo.record_heartbeat(
            user_id=user.id,
            game_id=reservation.game.game_id,
            reservation_key="wrong",
            origin_device_id="device-a",
        )

    beat = repo.record_heartbeat(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
    )
    assert beat.state == "active"

    repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-a",
    )
    with pytest.raises(AiLadderLifecycleNotFound):
        repo.record_heartbeat(
            user_id=user.id,
            game_id=reservation.game.game_id,
            reservation_key=reservation.reservation_key,
            origin_device_id="device-a",
        )


@pytest.mark.parametrize(("user_color", "expected_re"), [("B", "RE[W+F]"), ("W", "RE[B+F]")])
def test_remote_resign_generates_minimal_legal_sgf_and_uses_origin_provenance(
    session_factory, user, opponent, user_color, expected_re
):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25), user_color=user_color)

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-b",
    )

    assert receipt.result == "loss"
    with session_factory() as db:
        game = db.get(models_db.UserGame, reservation.game.game_id)
        assert "SZ[19]" in game.sgf_content
        assert expected_re in game.sgf_content
        assert game.origin_device_id == "device-a"
        assert game.result == expected_re[3:-1]


def test_invalid_played_result_key_does_not_mutate_any_terminal_state(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))

    with pytest.raises(InvalidReservationKey):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source="played_result",
            result="win",
            deciding_device_id="device-a",
            reservation_key="wrong",
            game_record=complete_game_record(),
        )

    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).count() == 1
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0


def test_sqlite_concurrent_played_result_and_remote_resign_have_one_winner(tmp_path, opponent):
    sessions = file_session_factory(tmp_path)
    with sessions() as db:
        user = models_db.User(username="terminal-race", hashed_password="x")
        db.add(user)
        db.commit()
        user_id = user.id
    repo = AiLadderRankedRepository(sessions)
    reservation = reserve(repo, user_id, replace(opponent, rung=16))
    repo.activate_reservation(
        user_id=user_id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )

    def played():
        return repo.finalize_reserved_game(
            user_id=user_id,
            game_id=reservation.game.game_id,
            terminal_source="played_result",
            result="win",
            deciding_device_id="device-a",
            reservation_key=reservation.reservation_key,
            game_record=complete_game_record(),
        )

    def resigned():
        return repo.finalize_reserved_game(
            user_id=user_id,
            game_id=reservation.game.game_id,
            terminal_source="remote_resign",
            result="loss",
            deciding_device_id="device-b",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = [future.result() for future in (pool.submit(played), pool.submit(resigned))]

    assert receipts[0].result == receipts[1].result
    assert sorted(receipt.replayed for receipt in receipts) == [False, True]
    with sessions() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.query(models_db.UserGame).count() == 1
        profile = db.get(models_db.AiLadderProfile, user_id)
        assert (profile.placement_completed, profile.version) == (1, 1)


def test_sqlite_cancel_and_remote_end_share_one_serialized_decision(tmp_path, opponent):
    sessions = file_session_factory(tmp_path)
    with sessions() as db:
        user = models_db.User(username="cancel-end-race", hashed_password="x")
        db.add(user)
        db.commit()
        user_id = user.id
    repo = AiLadderRankedRepository(sessions)
    reservation = reserve(repo, user_id, replace(opponent, rung=16))

    def cancel():
        try:
            return repo.cancel_reservation(
                user_id=user_id,
                game_id=reservation.game.game_id,
                reservation_key=reservation.reservation_key,
                origin_device_id="device-a",
            )
        except AiLadderLifecycleNotFound:
            return "cancel-lost"

    def end():
        try:
            return repo.finalize_reserved_game(
                user_id=user_id,
                game_id=reservation.game.game_id,
                terminal_source="remote_resign",
                result="loss",
                deciding_device_id="device-b",
            )
        except AiLadderLifecycleNotFound:
            return "end-lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (pool.submit(cancel), pool.submit(end))]

    with sessions() as db:
        active_count = db.query(models_db.AiLadderActiveGame).count()
        ledger_count = db.query(models_db.AiLadderGameLedger).count()
        user_game_count = db.query(models_db.UserGame).count()
        assert active_count == 0
        assert (ledger_count, user_game_count) in {(0, 0), (1, 1)}
        if ledger_count == 0:
            assert any(outcome == "end-lost" for outcome in outcomes)
        else:
            cancel_outcome = outcomes[0]
            assert cancel_outcome == "cancel-lost" or (
                not cancel_outcome.cancelled and cancel_outcome.receipt.state == "settled"
            )


def test_mismatched_frozen_game_record_rolls_back_everything(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    bad_record = complete_game_record()
    bad_record["komi"] = 6.5

    with pytest.raises(ValueError, match="does not match reservation"):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source="played_result",
            result="win",
            deciding_device_id="device-a",
            reservation_key=reservation.reservation_key,
            game_record=bad_record,
        )

    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).count() == 1
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0


def test_legacy_settlement_cannot_bypass_an_account_reservation(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))

    with pytest.raises(AiLadderLifecycleConflict):
        settle(repo, user.id, reservation.game.game_id, "win", replace(opponent, rung=25))

    with session_factory() as db:
        active = db.get(models_db.AiLadderActiveGame, reservation.game.game_id)
        assert active is not None and active.state == "reserved"
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0


def test_remote_resign_can_only_record_a_user_loss(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))

    with pytest.raises(ValueError, match="remote_resign"):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source="remote_resign",
            result="win",
            deciding_device_id="device-b",
        )

    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).count() == 1
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0


@pytest.mark.parametrize("terminal_source", ["played_result", "recovery"])
def test_origin_terminal_paths_require_active_state_and_secret(session_factory, user, opponent, terminal_source):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))

    with pytest.raises(AiLadderLifecycleConflict, match="activated"):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source=terminal_source,
            result="win",
            deciding_device_id="device-a",
            reservation_key=reservation.reservation_key,
            game_record=complete_game_record(),
        )

    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    with pytest.raises(InvalidReservationKey):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source=terminal_source,
            result="win",
            deciding_device_id="device-a",
            reservation_key=None,
            game_record=complete_game_record(),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sgf_content", "not sgf", "SGF"),
        ("player_black", "", "player_black"),
        ("player_white", "   ", "player_white"),
        ("move_count", -1, "move_count"),
        ("move_count", 1.5, "move_count"),
        ("komi", "7.5", "komi"),
        ("source", "import", "source"),
        ("category", "position", "category"),
        ("game_type", "free", "game_type"),
        ("rules", "", "rules"),
    ],
)
def test_invalid_authoritative_game_record_rolls_back(session_factory, user, opponent, field, value, message):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    record = complete_game_record()
    record[field] = value

    with pytest.raises(ValueError, match=message):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source="played_result",
            result="win",
            deciding_device_id="device-a",
            reservation_key=reservation.reservation_key,
            game_record=record,
        )

    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).count() == 1
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0


def test_finalizer_rechecks_ledger_when_locked_active_row_disappears(session_factory, user, opponent, monkeypatch):
    repo = AiLadderRankedRepository(session_factory)
    ledger = models_db.AiLadderGameLedger(
        game_id="lock-race",
        user_id=user.id,
        user_color="B",
        result="loss",
        game_type=AI_LADDER_GAME_TYPE,
        counted=False,
        reason="inconclusive",
        origin_device_id="device-a",
        deciding_device_id="device-b",
        terminal_source="remote_resign",
        decided_at=models_db.func.now(),
    )
    lookups = iter([None, ledger])
    monkeypatch.setattr(repo, "_find_ledger", lambda *args, **kwargs: next(lookups))
    monkeypatch.setattr(repo, "_lock_lifecycle_or_none", lambda *args, **kwargs: None)

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id="lock-race",
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-b",
    )

    assert (receipt.state, receipt.result, receipt.replayed) == ("settled", "loss", True)


def test_reserve_and_legacy_settle_lock_account_before_terminal_absence_read(
    session_factory, user, opponent, monkeypatch
):
    events = []
    repo = AiLadderRankedRepository(session_factory)
    original_lock_user = repo._lock_user
    original_find_ledger = repo._find_ledger_by_game_id

    def lock_user(*args, **kwargs):
        events.append("lock_user")
        return original_lock_user(*args, **kwargs)

    def find_ledger(*args, **kwargs):
        events.append("find_ledger")
        return original_find_ledger(*args, **kwargs)

    monkeypatch.setattr(repo, "_lock_user", lock_user)
    monkeypatch.setattr(repo, "_find_ledger_by_game_id", find_ledger)

    reservation = reserve(repo, user.id, opponent)
    assert events.index("lock_user") < events.index("find_ledger")

    repo.cancel_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
    )
    events.clear()
    settle(repo, user.id, "legacy-ordered", "win", replace(opponent, rung=25))
    assert events.index("lock_user") < events.index("find_ledger")


def test_legacy_settled_game_prevents_later_reservation_for_same_game(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    settle(repo, user.id, "legacy-before-reserve", "win", replace(opponent, rung=25))

    with pytest.raises(AiLadderLifecycleConflict):
        reserve(repo, user.id, opponent, game_id="legacy-before-reserve")

    with session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.query(models_db.AiLadderActiveGame).count() == 0


def test_terminal_replay_clears_exact_stale_active_row(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, opponent)
    with session_factory() as db:
        db.add(
            models_db.AiLadderGameLedger(
                game_id=reservation.game.game_id,
                user_id=user.id,
                user_color="B",
                result="loss",
                game_type=AI_LADDER_GAME_TYPE,
                counted=False,
                reason="inconclusive",
                origin_device_id="device-a",
                deciding_device_id="device-b",
                terminal_source="remote_resign",
                decided_at=models_db.func.now(),
            )
        )
        db.commit()

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-b",
    )

    assert receipt.replayed
    with session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.query(models_db.AiLadderActiveGame).count() == 0


@pytest.mark.parametrize(
    ("sgf_content", "submitted_result", "message"),
    [
        ("(;GM[1]FF[4]SZ[19]RU[Chinese]KM[7.5]PB[User]PW[AI]RE[B+R])", "inconclusive", "inconclusive"),
        ("(;GM[1]FF[4]SZ[19]RU[Japanese]KM[7.5]PB[User]PW[AI]RE[B+R])", "win", "rules"),
        ("(;GM[1]FF[4]SZ[19]RU[Chinese]KM[6.5]PB[User]PW[AI]RE[B+R])", "win", "komi"),
    ],
)
def test_sgf_terminal_and_rules_must_match_submission_and_frozen_contract(
    session_factory, user, opponent, sgf_content, submitted_result, message
):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    record = complete_game_record()
    record["sgf_content"] = sgf_content

    with pytest.raises(ValueError, match=message):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source="played_result",
            result=submitted_result,
            deciding_device_id="device-a",
            reservation_key=reservation.reservation_key,
            game_record=record,
        )

    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).count() == 1
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0


def test_pending_reservation_key_survives_repository_restart(tmp_path, opponent):
    factory = file_session_factory(tmp_path)
    with factory() as db:
        db.add(models_db.User(id=1, username="reservation-owner", hashed_password="x"))
        db.commit()
    snapshot = SimpleNamespace(
        game_id="a" * 32,
        user_id=1,
        session_id="session-reserved",
        reservation_key="secret-reservation-key",
        user_color="B",
        game_type=AI_LADDER_GAME_TYPE,
        opponent=opponent,
        ai_subtype="ai:ladder",
        execution_identity="fixture-identity",
    )

    AiLadderRankedRepository(factory).create_pending_game(snapshot)
    recovered = AiLadderRankedRepository(factory).get_pending_game(1)

    assert recovered is not None
    assert recovered["reservation_key"] == "secret-reservation-key"


def test_catalog_consumes_the_exact_41_product_names_in_order():
    assert len(LADDER_LEVELS) == 41
    assert [level.rung for level in LADDER_LEVELS] == list(range(1, 42))
    assert [level.rank_name for level in LADDER_LEVELS] == EXPECTED_RANK_NAMES
    assert all("星阵" not in name for name in EXPECTED_RANK_NAMES)


@pytest.mark.parametrize(
    ("legacy_rank", "expected"),
    [
        ("20k", (1, 32)),
        ("10k", (1, 32)),
        ("5k", (1, 32)),
        ("1k", (4, 35)),
        ("1d", (6, 37)),
        ("5d", (10, 41)),
        ("9d", (10, 41)),
        ("12d", (10, 41)),
        (None, (1, 32)),
        ("", (1, 32)),
    ],
)
def test_initial_placement_window_uses_legacy_rank_only_to_choose_32_candidates(legacy_rank, expected):
    assert initial_placement_window(legacy_rank) == expected


@pytest.mark.parametrize(
    ("legacy_rank", "mapped_rung"),
    [
        *((f"{rank}k", 21 - rank) for rank in range(20, 0, -1)),
        *((f"{rank}d", 20 + 2 * rank) for rank in range(1, 10)),
        ("10d", 38),
        ("12d", 38),
    ],
)
def test_old_rank_mapping_is_exact(legacy_rank, mapped_rung):
    start, end = initial_placement_window(legacy_rank)
    assert start == max(1, min(mapped_rung - 16, 10))
    assert end == start + 31


@pytest.mark.parametrize(
    ("results", "expected_rung"),
    [
        (["loss"] * 5, 1),
        (["win"] * 5, 32),
        (["win", "loss", "win", "loss", "win"], 22),
    ],
)
def test_five_valid_results_deterministically_finish_binary_placement(session_factory, results, expected_rung):
    with session_factory() as db:
        user = models_db.User(username=f"u-{expected_rung}", hashed_password="x", rank=None)
        db.add(user)
        db.commit()
        user_id = user.id

    repo = AiLadderRankedRepository(session_factory)
    lo, hi = 1, 32
    for round_number, result in enumerate(results, start=1):
        mid = (lo + hi) // 2
        snapshot = AiLadderOpponentSnapshot(
            rung=mid,
            rank_name=f"fixture-{mid}",
            config_snapshot={"config_digest": f"fixture-{mid}", "config_version": "fixture-v1"},
            certification_status="certified",
            availability="available",
            route="server",
        )
        outcome = settle(repo, user_id, f"placement-{expected_rung}-{round_number}", result, snapshot)
        if result == "win":
            lo = mid + 1
        else:
            hi = mid
        assert outcome.placement_completed == round_number
        assert (outcome.placement_lo, outcome.placement_hi) == (lo, hi)

    assert lo == hi == expected_rung
    assert outcome.ai_ladder_rung == expected_rung
    assert outcome.net_score == 0


def test_existing_legacy_rank_still_requires_all_five_placement_games(session_factory, user):
    repo = AiLadderRankedRepository(session_factory)
    lo, hi = initial_placement_window("5d")
    assert (lo, hi) == (10, 41)

    for round_number in range(1, 6):
        mid = (lo + hi) // 2
        snapshot = AiLadderOpponentSnapshot(
            rung=mid,
            rank_name=f"fixture-{mid}",
            config_snapshot={"config_digest": str(mid), "recipe_identity": f"fixture-recipe-{mid}"},
            certification_status="certified",
            availability="available",
            route="server",
        )
        outcome = settle(repo, user.id, f"old-rank-{round_number}", "loss", snapshot)
        hi = mid
        assert outcome.placement_completed == round_number
        assert outcome.ai_ladder_rung is None if round_number < 5 else outcome.ai_ladder_rung == lo


def test_inconclusive_game_records_decision_but_consumes_no_placement_round(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)

    outcome = settle(repo, user.id, "inconclusive", "inconclusive", opponent)

    assert not outcome.counted
    assert outcome.reason == "inconclusive"
    with session_factory() as db:
        decision = db.query(models_db.AiLadderGameLedger).one()
        assert (decision.game_id, decision.counted, decision.reason) == ("inconclusive", False, "inconclusive")
        assert db.query(models_db.AiLadderProfile).count() == 0


@pytest.mark.parametrize("result", ["win", "loss"])
def test_a_game_the_engine_could_not_play_is_recorded_but_never_counted(session_factory, user, opponent, result):
    """Found on an RK3562 kiosk (2026-08-05): its HTTP engine does not advertise
    certified ladder capabilities, so `ai:ladder` fails closed and plays nothing
    (interface._surface_ladder_unavailable). Whatever ends the game after that is an
    artefact of our engine, not a result:

      - the player gives up on a board that will never answer -> a *loss* would count
      - the AI's own clock expires and galaxy auto-forfeits -> a *win* would count,
        handing out promotion credit for a game nobody played

    Both are silent: the rank moves and nothing says why. The decision row still gets
    written, so the receipt exists and names the reason.
    """
    repo = AiLadderRankedRepository(session_factory)

    outcome = settle(repo, user.id, f"stalled-{result}", result, opponent, engine_stalled=True)

    assert not outcome.counted
    assert outcome.reason == "engine_unavailable"
    with session_factory() as db:
        decision = db.query(models_db.AiLadderGameLedger).one()
        assert (decision.counted, decision.reason) == (False, "engine_unavailable")
        # No profile is created, so the stalled game does not even start placement.
        assert db.query(models_db.AiLadderProfile).count() == 0


def test_a_game_whose_engine_recovered_still_counts(session_factory, user, opponent):
    """The flag is per-turn, not per-game: an engine that hiccuped and then played on
    must not cost the player the whole game's result."""
    repo = AiLadderRankedRepository(session_factory)
    placed_profile(session_factory, user.id, opponent.rung)

    outcome = settle(repo, user.id, "recovered", "win", opponent, engine_stalled=False)

    assert outcome.counted
    assert outcome.reason is None


# 1级 is rung 20 and 准1段 is rung 21. The step counts rungs a player can actually be
# seated on (§6 of 2026-08-04-41-tier-rated-play-integration-design.md); now that all 41
# carry a recipe, that is every rung, so 1级 promotes to 准1段 (21) rather than skipping it.
@pytest.mark.parametrize(("start", "results", "expected"), [(20, ["win"] * 3, 21), (20, ["loss"] * 3, 19)])
def test_plus_or_minus_three_changes_exactly_one_playable_rung_and_resets(
    session_factory, user, opponent, start, results, expected
):
    placed_profile(session_factory, user.id, start)
    repo = AiLadderRankedRepository(session_factory)

    for index, result in enumerate(results):
        outcome = settle(repo, user.id, f"threshold-{result}-{index}", result, replace(opponent, rung=start))

    assert outcome.ai_ladder_rung == expected
    assert outcome.net_score == 0


@pytest.mark.parametrize(("rung", "result"), [(1, "loss"), (41, "win")])
def test_rung_boundaries_saturate_and_reset_score(session_factory, user, opponent, rung, result):
    placed_profile(session_factory, user.id, rung, net_score=-2 if result == "loss" else 2)
    repo = AiLadderRankedRepository(session_factory)

    outcome = settle(repo, user.id, f"boundary-{rung}", result, replace(opponent, rung=rung))

    assert outcome.ai_ladder_rung == rung
    assert outcome.net_score == 0


def test_three_wins_two_losses_do_not_upgrade_from_recent_form(session_factory, user, opponent):
    placed_profile(session_factory, user.id, 20)
    repo = AiLadderRankedRepository(session_factory)

    for index, result in enumerate(["win", "win", "loss", "win", "loss"]):
        outcome = settle(repo, user.id, f"recent-{index}", result, replace(opponent, rung=20))

    assert outcome.ai_ladder_rung == 20
    assert outcome.net_score == 1


def test_recent_five_returns_only_counted_win_loss_decisions(session_factory, user, opponent):
    placed_profile(session_factory, user.id, 20)
    repo = AiLadderRankedRepository(session_factory)
    expected_valid_results = ["win", "loss", "win", "loss", "win", "loss"]

    settle(repo, user.id, "recent-excluded-free", "win", None, game_type="free")
    for index, result in enumerate(expected_valid_results):
        settle(repo, user.id, f"recent-counted-{index}", result, replace(opponent, rung=20))
        if index == 2:
            settle(
                repo,
                user.id,
                "recent-excluded-inconclusive",
                "inconclusive",
                replace(opponent, rung=20),
            )

    assert repo.recent_counted_results(user.id) == list(reversed(expected_valid_results[-5:]))


@pytest.mark.parametrize(
    ("game_type", "result", "snapshot", "reason"),
    [
        ("rated", "win", None, "invalid_game_type"),
        ("free", "win", None, "invalid_game_type"),
        ("pvp_local", "win", None, "invalid_game_type"),
        (AI_LADDER_GAME_TYPE, "inconclusive", None, "inconclusive"),
        (AI_LADDER_GAME_TYPE, "win", {"certification_status": "provisional"}, "opponent_not_eligible"),
        (AI_LADDER_GAME_TYPE, "win", {"availability": "unavailable"}, "opponent_not_eligible"),
    ],
)
def test_only_certified_available_ranked_ai_results_count(
    session_factory, user, opponent, game_type, result, snapshot, reason
):
    repo = AiLadderRankedRepository(session_factory)
    attempted_opponent = None if game_type == "pvp_local" else replace(opponent, **(snapshot or {}))

    outcome = settle(repo, user.id, f"ignored-{reason}-{game_type}", result, attempted_opponent, game_type=game_type)

    assert not outcome.counted
    assert outcome.reason == reason
    with session_factory() as db:
        decision = db.query(models_db.AiLadderGameLedger).one()
        assert not decision.counted
        assert decision.reason == reason
        if game_type == "pvp_local":
            assert decision.opponent_rung is None
            assert decision.opponent_config_snapshot is None
        assert db.query(models_db.AiLadderProfile).count() == 0


@pytest.mark.parametrize("snapshot", [{"certification_status": "provisional"}, {"availability": "unavailable"}])
def test_the_provisional_switch_lets_the_game_be_played_but_never_banked(
    session_factory, user, opponent, snapshot, monkeypatch
):
    """KATRAIN_LADDER_ALLOW_PROVISIONAL decides seating, never scoring.

    A rank earned against unmeasured strength means nothing, and the schema says so:
    `ck_ai_ladder_ledger_decision` will not store a counted row whose opponent is not
    certified+available. So the game is recorded with its real reason, and the profile
    does not move -- with the switch on exactly as with it off.
    """
    from katrain.core import ladder

    monkeypatch.setenv(ladder.LADDER_ALLOW_PROVISIONAL_ENV, "1")
    repo = AiLadderRankedRepository(session_factory)
    attempted_opponent = replace(opponent, **snapshot)
    placed_profile(session_factory, user.id, attempted_opponent.rung)

    outcome = settle(repo, user.id, "provisional-not-banked", "loss", attempted_opponent)

    assert not outcome.counted
    assert outcome.reason == "opponent_not_eligible"
    with session_factory() as db:
        decision = db.query(models_db.AiLadderGameLedger).one()
        assert not decision.counted
        # The row still names what was actually played, so the record is honest about it.
        assert decision.opponent_certification_status == attempted_opponent.certification_status
        assert decision.opponent_availability == attempted_opponent.availability
        profile = db.query(models_db.AiLadderProfile).one()
        assert (profile.net_score, profile.ai_ladder_rung) == (0, attempted_opponent.rung)


@pytest.mark.parametrize(
    ("first_game_type", "first_result", "first_snapshot", "reason"),
    [
        ("free", "win", {}, "invalid_game_type"),
        ("pvp_local", "win", None, "invalid_game_type"),
        (AI_LADDER_GAME_TYPE, "inconclusive", {}, "inconclusive"),
        (AI_LADDER_GAME_TYPE, "win", {"availability": "unavailable"}, "opponent_not_eligible"),
        (AI_LADDER_GAME_TYPE, "win", {"rung": 24}, "opponent_rung_mismatch"),
    ],
)
def test_excluded_game_id_replays_its_first_decision_even_if_later_parameters_would_count(
    session_factory,
    user,
    opponent,
    first_game_type,
    first_result,
    first_snapshot,
    reason,
):
    repo = AiLadderRankedRepository(session_factory)
    valid_opponent = replace(opponent, rung=25)
    first_opponent = None if first_snapshot is None else replace(valid_opponent, **first_snapshot)

    first = settle(
        repo,
        user.id,
        f"excluded-replay-{reason}",
        first_result,
        first_opponent,
        game_type=first_game_type,
    )
    replay = settle(repo, user.id, f"excluded-replay-{reason}", "win", valid_opponent)

    assert (first.counted, first.replayed, first.reason) == (False, False, reason)
    assert (replay.counted, replay.replayed, replay.reason) == (False, True, reason)
    with session_factory() as db:
        decision = db.query(models_db.AiLadderGameLedger).one()
        assert (decision.counted, decision.reason) == (False, reason)
        assert db.query(models_db.AiLadderProfile).count() == 0


def test_single_decision_table_rejects_a_second_valid_row_after_exclusion(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    valid_opponent = replace(opponent, rung=25)
    first = settle(repo, user.id, "single-table-unique", "win", None, game_type="pvp_local")
    assert (first.counted, first.reason) == (False, "invalid_game_type")

    with session_factory() as db:
        db.add(
            models_db.AiLadderGameLedger(
                game_id="single-table-unique",
                user_id=user.id,
                user_color="B",
                result="win",
                game_type=AI_LADDER_GAME_TYPE,
                opponent_rung=25,
                opponent_rank_name=valid_opponent.rank_name,
                opponent_config_snapshot=dict(valid_opponent.config_snapshot),
                opponent_certification_status="certified",
                opponent_availability="available",
                opponent_route="server",
                counted=True,
                reason=None,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    replay = settle(repo, user.id, "single-table-unique", "win", valid_opponent)
    assert (replay.counted, replay.replayed, replay.reason) == (False, True, "invalid_game_type")
    with session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.query(models_db.AiLadderProfile).count() == 0


def test_settlement_requires_the_current_placement_or_ranked_opponent(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)

    placement = settle(repo, user.id, "wrong-placement-opponent", "win", replace(opponent, rung=24))
    assert not placement.counted
    assert placement.reason == "opponent_rung_mismatch"

    placed_profile(session_factory, user.id, 20)
    ranked = settle(repo, user.id, "wrong-ranked-opponent", "win", replace(opponent, rung=19))
    assert not ranked.counted
    assert ranked.reason == "opponent_rung_mismatch"

    with session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 2
        profile = db.get(models_db.AiLadderProfile, user.id)
        assert (profile.ai_ladder_rung, profile.net_score) == (20, 0)


def test_ledger_snapshots_opponent_contract_and_replay_is_idempotent(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    opponent = replace(opponent, rung=25)

    first = settle(repo, user.id, "same-game", "win", opponent)
    replay = settle(repo, user.id, "same-game", "win", opponent)

    assert first.counted and not first.replayed
    assert replay.counted and replay.replayed
    assert replay.placement_completed == first.placement_completed == 1
    with session_factory() as db:
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert (ledger.game_id, ledger.counted, ledger.reason) == ("same-game", True, None)
        assert ledger.game_id == "same-game"
        assert ledger.user_id == user.id
        assert ledger.user_color == "B"
        assert ledger.result == "win"
        assert ledger.game_type == AI_LADDER_GAME_TYPE
        assert ledger.opponent_rung == opponent.rung
        assert ledger.opponent_rank_name == opponent.rank_name
        assert ledger.opponent_config_snapshot == opponent.config_snapshot
        assert ledger.opponent_certification_status == "certified"
        assert ledger.opponent_availability == "available"
        assert ledger.opponent_route == "server"
        assert ledger.settled_at is not None


@pytest.mark.parametrize(
    "config_snapshot",
    [
        {},
        {"config_digest": "digest-only"},
        {"config_version": "version-only"},
        {"config_digest": "", "config_version": "v1"},
        {"config_digest": "digest", "config_version": ""},
    ],
)
def test_opponent_snapshot_requires_a_stable_nonempty_config_identity(config_snapshot):
    with pytest.raises(ValueError, match="config_snapshot"):
        AiLadderOpponentSnapshot(
            rung=1,
            rank_name="20级",
            config_snapshot=config_snapshot,
            certification_status="certified",
            availability="available",
            route="server",
        )


def test_callers_cannot_mutate_persisted_config_snapshot_after_settlement(session_factory, user, opponent):
    mutable_config = {
        "config_digest": "original-digest",
        "config_version": "catalog-v1",
        "recipe": {"identity": "fixture-recipe"},
    }
    mutable_opponent = replace(opponent, rung=25, config_snapshot=mutable_config)
    repo = AiLadderRankedRepository(session_factory)

    settle(repo, user.id, "immutable-config", "win", mutable_opponent)
    mutable_config["config_digest"] = "mutated-digest"
    mutable_config["config_version"] = "mutated-version"
    mutable_config["recipe"]["identity"] = "mutated-recipe"

    with session_factory() as db:
        ledger = db.query(models_db.AiLadderGameLedger).one()
        expected = {
            "config_digest": "original-digest",
            "config_version": "catalog-v1",
            "recipe": {"identity": "fixture-recipe"},
        }
        assert ledger.opponent_config_snapshot == expected


def test_ai_ladder_never_changes_legacy_user_rank_or_net_wins(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)

    settle(repo, user.id, "legacy-independent", "win", replace(opponent, rung=25))

    with session_factory() as db:
        unchanged = db.get(models_db.User, user.id)
        assert unchanged.rank == "5d"
        assert unchanged.net_wins == 2


def test_new_tables_are_created_with_unique_game_id_and_one_to_one_profile(session_factory, user):
    engine = session_factory.kw["bind"]
    inspector = inspect(engine)
    assert {"ai_ladder_profiles", "ai_ladder_game_ledger"}.issubset(inspector.get_table_names())
    assert "ai_ladder_settlement_receipts" not in inspector.get_table_names()
    ledger_columns = {column["name"]: column for column in inspector.get_columns("ai_ladder_game_ledger")}
    assert ledger_columns["opponent_rung"]["nullable"]
    assert ledger_columns["opponent_config_snapshot"]["nullable"]
    assert {"counted", "reason"}.issubset(ledger_columns)
    assert inspector.get_pk_constraint("ai_ladder_profiles")["constrained_columns"] == ["user_id"]
    assert any(
        foreign_key["constrained_columns"] == ["user_id"]
        and foreign_key["referred_table"] == "users"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in inspector.get_foreign_keys("ai_ladder_profiles")
    )
    unique_columns = [
        constraint["column_names"] for constraint in inspector.get_unique_constraints("ai_ladder_game_ledger")
    ]
    unique_columns.extend(
        index["column_names"] for index in inspector.get_indexes("ai_ladder_game_ledger") if index["unique"]
    )
    assert ["game_id"] in unique_columns

    placed_profile(session_factory, user.id, 20)
    with session_factory() as db:
        loaded_user = db.get(models_db.User, user.id)
        assert isinstance(loaded_user.ai_ladder_profile, models_db.AiLadderProfile)


def test_rank_state_and_ledger_are_protected_from_schema_drift_rebuilds():
    assert migrations.AI_LADDER_TABLES == {
        "ai_ladder_profiles",
        "ai_ladder_game_ledger",
        "ai_ladder_pending_games",
        "ai_ladder_active_games",
    }
    assert migrations.AI_LADDER_TABLES < migrations.PROTECTED_TABLES
    assert migrations.BILLING_TABLES < migrations.PROTECTED_TABLES


def test_transaction_failure_rolls_back_both_profile_and_ledger(session_factory, user, opponent):
    rollback_calls = []

    class FailingCommitSession(Session):
        def commit(self):
            self.flush()
            raise RuntimeError("forced commit failure")

        def rollback(self):
            rollback_calls.append(True)
            super().rollback()

    placed_profile(session_factory, user.id, 20, net_score=1)
    failing_factory = sessionmaker(bind=session_factory.kw["bind"], class_=FailingCommitSession)
    repo = AiLadderRankedRepository(failing_factory)

    with pytest.raises(RuntimeError, match="forced commit failure"):
        settle(repo, user.id, "rollback", "win", replace(opponent, rung=20))

    assert rollback_calls == [True]
    with session_factory() as db:
        profile = db.get(models_db.AiLadderProfile, user.id)
        assert (profile.ai_ladder_rung, profile.net_score, profile.version) == (20, 1, 0)
        assert db.query(models_db.AiLadderGameLedger).count() == 0


def test_sqlite_serializes_concurrent_different_games_for_one_user(tmp_path, opponent):
    sessions = file_session_factory(tmp_path)
    with sessions() as db:
        user = models_db.User(username="concurrent-different", hashed_password="x")
        db.add(user)
        db.commit()
        user_id = user.id
    placed_profile(sessions, user_id, 20)
    repo = concurrent_repo(sessions)

    def run(game_id):
        return settle(repo, user_id, game_id, "win", replace(opponent, rung=20))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, ["concurrent-a", "concurrent-b"]))

    assert all(outcome.counted and not outcome.replayed for outcome in outcomes)
    with sessions() as db:
        profile = db.get(models_db.AiLadderProfile, user_id)
        assert (profile.ai_ladder_rung, profile.net_score, profile.version) == (20, 2, 2)
        assert db.query(models_db.AiLadderGameLedger).count() == 2


def test_sqlite_serializes_concurrent_replay_of_the_same_game(tmp_path, opponent):
    sessions = file_session_factory(tmp_path)
    with sessions() as db:
        user = models_db.User(username="concurrent-replay", hashed_password="x")
        db.add(user)
        db.commit()
        user_id = user.id
    placed_profile(sessions, user_id, 20)
    repo = concurrent_repo(sessions)

    def run(_):
        return settle(repo, user_id, "concurrent-same", "win", replace(opponent, rung=20))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, range(2)))

    assert sorted(outcome.replayed for outcome in outcomes) == [False, True]
    with sessions() as db:
        profile = db.get(models_db.AiLadderProfile, user_id)
        assert (profile.ai_ladder_rung, profile.net_score, profile.version) == (20, 1, 1)
        assert db.query(models_db.AiLadderGameLedger).count() == 1


# --- pending_settlement 的诚实释放路径 -----------------------------------------


def _pending(repo, user, opponent, *, rung=25):
    reservation = reserve(repo, user.id, replace(opponent, rung=rung))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    repo.mark_pending_settlement(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
    )
    return reservation


def _age_pending(session_factory, game_id, minutes):
    with session_factory() as db:
        row = db.get(models_db.AiLadderActiveGame, game_id)
        row.pending_settlement_since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        db.commit()


def test_releasing_an_undelivered_result_banks_nothing_and_moves_no_rating(session_factory, user, opponent):
    """等够了之后放行,而且**不写账本、不动分**。

    这是这条路径与接管判负的分界:接管记一负、动段位;释放什么都不记。
    「那台盒子再没回来」不是一个判决 —— 把它当 inconclusive 写进账本,等于声称我们知道
    这局没下出结果,而我们真正知道的只是「我们不知道」。而且账本先到先得,那一写会把
    一周后才同步上来的真结果永久重放掉。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = _pending(repo, user, opponent)
    _age_pending(session_factory, reservation.game.game_id, 31)

    released = repo.release_abandoned_settlement(
        user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b"
    )

    assert (released.cancelled, released.receipt) == (True, None)
    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id) is None
        assert db.query(models_db.AiLadderGameLedger).count() == 0, "释放不是判决,不该留下账本行"
        assert db.query(models_db.UserGame).count() == 0, "没有对局记录 —— 那局的棋谱从没送到过"


def test_a_released_game_still_counts_for_what_it_really_was_if_it_ever_arrives(session_factory, user, opponent):
    """释放之后真结果又送到了,照旧按真结果算。

    这条是「不写账本」那个决定的**回报**,也是它唯一说得过去的理由:换成写一条 inconclusive
    墓碑,这里就会重放出「不计分」,用户真下赢的那局被永久抹掉。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = _pending(repo, user, opponent)
    _age_pending(session_factory, reservation.game.game_id, 31)
    repo.release_abandoned_settlement(user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b")

    late = repo.settle_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        user_color="B",
        result="win",
        game_type=AI_LADDER_GAME_TYPE,
        opponent=replace(opponent, rung=25),
    )

    assert late.counted is True
    assert late.reason is None


def test_release_returns_the_real_receipt_when_the_result_actually_landed(session_factory, user, opponent):
    """账本先查,状态后判。

    如果结果其实已经落地了,诚实的回答是那张回执,不是一次释放。把账本查询排在状态判断
    之后,就是那种「正确分支永远到不了」的形状。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = _pending(repo, user, opponent)
    repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="played_result",
        result="win",
        deciding_device_id="device-a",
        reservation_key=reservation.reservation_key,
        game_record=complete_game_record(user_color="B", result="win"),
    )

    outcome = repo.release_abandoned_settlement(
        user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b"
    )

    assert outcome.cancelled is False
    assert outcome.receipt is not None
    assert (outcome.receipt.result, outcome.receipt.counted) == ("win", True)


def test_an_active_game_is_never_releasable_however_long_it_runs(session_factory, user, opponent):
    """在下的棋不是「没送达的结果」—— 它走接管那条路,而接管要记一负。

    没有这条,一局长考就能被当成待送达的结果放掉,而放掉是不计分的:那就成了免费弃局,
    正是段位并发规则要防的东西。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )

    with pytest.raises(AiLadderLifecycleConflict) as excinfo:
        repo.release_abandoned_settlement(
            user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b"
        )


def test_a_game_id_already_in_the_ledger_cannot_be_reserved_again(session_factory, user, opponent):
    """已经进过账本的 game_id 不许再被预约 —— 无论是不是同一个账号。

    审计对抗性反驳挖出来的:`game_id` 由盒端 `uuid4().hex` 铸造、云端照单全收,而
    `ai_ladder_game_ledger.game_id` 是全局唯一的。一个复用了别人 game_id 的盒子,
    能给自己的账号造出一条**每一条出路都关着**的预约 —— `_find_ledger` 在账本行属于
    他人时直接抛 NotFound,而它是接管路径和释放路径的**第一句**。等多久都没用,
    因为那一行永远不会变。

    所以拦在门口而不是事后拆解:那个状态按构造就无解,唯一的治法是不要造出它。
    """

    repo = AiLadderRankedRepository(session_factory)
    with session_factory() as db:
        other = models_db.User(username="ledger-squatter", hashed_password="x", rank="20k")
        db.add(other)
        db.commit()
        other_id = other.id

    taken = reserve(repo, other_id, replace(opponent, rung=20))
    repo.activate_reservation(
        user_id=other_id,
        game_id=taken.game.game_id,
        reservation_key=taken.reservation_key,
        origin_device_id="device-x",
        origin_session_id="session-x",
    )
    repo.finalize_reserved_game(
        user_id=other_id,
        game_id=taken.game.game_id,
        terminal_source="played_result",
        result="win",
        deciding_device_id="device-x",
        reservation_key=taken.reservation_key,
        game_record=complete_game_record(user_color="B", result="win"),
    )

    with pytest.raises(AiLadderLifecycleConflict):
        reserve(repo, user.id, replace(opponent, rung=25), game_id=taken.game.game_id)

    # 而且没有留下半条预约 —— 拒绝必须是彻底的,否则挡住的只是账本那一半。
    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).filter_by(user_id=user.id).one_or_none() is None


def test_ending_an_unplayed_reservation_banks_a_loss_on_purpose(session_factory, user, opponent):
    """未激活的预约被任意设备 `/end` 掉,**照样记一笔计分的负**。这是设计,不是漏网。

    对抗性审计把它报成缺陷(「一手没下就记负」),我照着改了,然后 5 条既有测试当场红 ——
    其中 `test_any_account_device_can_end_immediately_and_replay_same_receipt` 逐字断言了
    这个行为。**这条钉在这里,是为了让下一次审计(或下一个我)在改之前先撞到理由。**

    理由是契约 ④「判负后放行」用在预约上:预约本身已经占住了这个账号的段位位子,
    而释放占位不能是免费的 —— 否则「开一局、看一眼对手、不想下就免费退掉」就成了
    可以反复刷的动作,段位并发规则要防的正是这个。

    代价也说清楚:`user_games` 里会存一份 `RE[W+F] move_count=0` 的合成棋谱。
    那份棋谱不诚实(它长得像一局下过的棋),但那是 `remote_resign` 在 `active` 上
    也有的既有表示法,不是这条路径独有的问题。要改就四条路径一起改,不在这里顺手动。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=25))
    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id).state == "reserved"

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-b",
    )

    assert (receipt.state, receipt.counted) == ("settled", True)
    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id) is None


def test_a_pre_existing_user_game_row_must_not_be_able_to_lock_the_account(session_factory, user, opponent):
    """先建 `user_games` 行、再用同一个 id 预约 —— 不许因此把账号锁死。

    已有的闸只挡一个方向:`user_game_repo.create` 会拒绝一个已被段位预约占用的 game_id
    (`ReservedAiLadderGameIdError`)。**反方向没人查** —— `reserve_game` 只查账本,不查
    `user_games`。

    而 `_create_or_validate_user_game` 会把已存在的那行逐字段与本次结算比对,任一不同就抛
    Conflict,且它挡在 finalize 的**每一条** terminal_source 前面。于是:预约在、
    接管走 finalize 被拒、释放要求 `pending_settlement` 也够不着 ⇒ 账号在所有设备上锁死。

    game_id 由客户端给,所以这条路是**两次公开请求**就能走到的。
    """

    repo = AiLadderRankedRepository(session_factory)
    game_id = "c" * 32
    from katrain.web.core.user_game_repo import UserGameRepository

    UserGameRepository(session_factory).create(
        user_id=user.id,
        sgf_content="(;GM[1]FF[4]SZ[19]RU[chinese]KM[7.5]RE[B+1.5])",
        source="upload",
        game_id=game_id,
        result="B+1.5",
        board_size=19,
        rules="chinese",
        komi=7.5,
        move_count=1,
        player_black="someone",
        player_white="else",
    )

    with pytest.raises(AiLadderLifecycleConflict):
        reserve(repo, user.id, replace(opponent, rung=25), game_id=game_id)

    with session_factory() as db:
        assert (
            db.query(models_db.AiLadderActiveGame).filter_by(user_id=user.id).one_or_none() is None
        ), "预约建成了,而它的每一条出路都被那行 user_games 挡着 —— 账号从此锁死"
