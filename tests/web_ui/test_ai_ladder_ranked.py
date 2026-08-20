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

from katrain.core import ladder as ladder_module
from katrain.core.ladder import LADDER_LEVELS
from katrain.web.core import migrations, models_db
from katrain.web.core.ai_ladder_ranked import (
    AI_LADDER_GAME_TYPE,
    AiLadderLifecycleConflict,
    AiLadderLifecycleNotFound,
    AiLadderOpponentSnapshot,
    AiLadderRankedRepository,
    InvalidReservationKey,
    expected_opponent_rung,
    initial_placement_window,
)


#: 定级搜索给一个 rank="5d" 的用户排的对手档位。**推导出来的，不是写死的**：
#: 2026-08-20 准3段(25) 封档、`expected_opponent_rung` 开始 snap 之后，它从 25 变成了 24。
#: 这些用例把它当**输入**用（构造一局合法对局去结算），值本身在
#: `test_ladder_progress.py::test_every_reachable_placement_window_seats_a_playable_rung`
#: 和 `test_ai_ladder_api.py` 里被断言，所以这里推导不构成同义反复。
PLACEMENT_RUNG_5D = expected_opponent_rung(None, *initial_placement_window("5d"))
#: 同上，给一个没有 legacy rank 的用户（窗口 1..32）。原始中点 16 = 5级，已封档 -> snap 到 15。
PLACEMENT_RUNG_DEFAULT = expected_opponent_rung(None, *initial_placement_window(None))


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
        rung=PLACEMENT_RUNG_DEFAULT,
        rank_name=LADDER_LEVELS[PLACEMENT_RUNG_DEFAULT - 1].rank_name,
        config_snapshot={"config_digest": "fixture-certified-default-rung", "config_version": "fixture-v1"},
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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
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


def _pending_settlement_reservation(repo, user, opponent):
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
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


def test_resigning_a_game_whose_result_is_still_in_flight_records_the_loss(session_factory, user, opponent):
    """成绩还在路上的那一局,从第二台设备认输,**记那一场负** —— 这是被知情选择的代价。

    这条测试记录的是一个**决定**,不是一个我们没看见的缺陷。它一度是反过来的:
    `pending_settlement` 上的 `remote_resign` 被拒,理由是账本先到先得 ⇒ 判负会**永久替换**
    真结果,用户赢的那局变成负、段位反向移动、`user_games` 里留下一份 0 手 SGF 顶替真棋谱。
    那段描述今天**依然准确**。

    2026-08-11 产品方仍然选了判负,理由是**同一处境不能有两个价钱**:另一条出路
    (什么都不记)会让认输自然消亡 —— 劣势局面下它严格更优,不需要恶意,只需要看得见。
    于是段位分只由「用户愿意下完的局」构成,一个与作弊无关的系统性向上偏移。

    换来的代价必须**由用户知情按下**,不由系统静默记账,所以有两道守卫:
      1. 账本先查(下一条测试):结果**已经落账**的一律返回真实回执,绝不写负;
      2. 手上真有在途结算的那台盒子必须先看到「立即重试」—— 前端的事,不在这里。

    剩下的就是这一格:结果还在路上、用户在别处、他自己按下了认输。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = _pending_settlement_reservation(repo, user, opponent)

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-b",
    )

    assert (receipt.result, receipt.counted) == ("loss", True)
    with session_factory() as db:
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert (ledger.result, ledger.terminal_source) == ("loss", "remote_resign")
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id) is None, "占位必须当场放开"


def test_resigning_a_game_whose_result_already_landed_returns_the_real_receipt(session_factory, user, opponent):
    """守卫 1:认输端点必须**先查账本**。

    最该准确的那一格恰恰是屏上会说谎的那一格 —— 盒子提交成功、**回包丢了**,或者第二台
    设备看到的是陈旧视图:云端其实已经写了账本、已经算了分,而屏上还写着「还没在云端记录」。
    此时按下认输,若状态判断排在账本查询前面,用户会「认输」掉一局他已经赢了并且已经计分的棋。

    国象与五子棋各自独立撞到这一格(一个回包丢了、一个视图陈旧),已升为四家必做守卫。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = _pending_settlement_reservation(repo, user, opponent)
    # 结果照它真实的路子落账 —— 原盒子拿着自己的预约凭证提交,而不是在测试里另拼一条捷径。
    repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="played_result",
        result="win",
        deciding_device_id="device-a",
        reservation_key=reservation.reservation_key,
        game_record=complete_game_record(user_color="B", result="win"),
    )

    receipt = repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="remote_resign",
        result="loss",
        deciding_device_id="device-b",
    )

    assert (receipt.result, receipt.counted) == ("win", True), "已经落账的结果不许被认输覆盖"
    with session_factory() as db:
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert (ledger.result, ledger.terminal_source) == ("win", "played_result")


def _activated(repo, user, opponent, *, device_id="device-a"):
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D), device_id=device_id)
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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D), user_color=user_color)
    # 认输是**有棋盘**那一格的出口,所以这里先 activate:一手没走过的占位现在根本不许
    # 走到 finalize(见 `test_a_reservation_that_never_started_can_never_be_resigned`)。
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )

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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))

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
    reservation = reserve(repo, user_id, replace(opponent, rung=PLACEMENT_RUNG_DEFAULT))
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
    reservation = reserve(repo, user_id, replace(opponent, rung=PLACEMENT_RUNG_DEFAULT))

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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))

    with pytest.raises(AiLadderLifecycleConflict):
        settle(repo, user.id, reservation.game.game_id, "win", replace(opponent, rung=PLACEMENT_RUNG_5D))

    with session_factory() as db:
        active = db.get(models_db.AiLadderActiveGame, reservation.game.game_id)
        assert active is not None and active.state == "reserved"
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0


def test_remote_resign_can_only_record_a_user_loss(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))

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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))

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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
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
    settle(repo, user.id, "legacy-ordered", "win", replace(opponent, rung=PLACEMENT_RUNG_5D))
    assert events.index("lock_user") < events.index("find_ledger")


def test_legacy_settled_game_prevents_later_reservation_for_same_game(session_factory, user, opponent):
    repo = AiLadderRankedRepository(session_factory)
    settle(repo, user.id, "legacy-before-reserve", "win", replace(opponent, rung=PLACEMENT_RUNG_5D))

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
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
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
        # 镜像生产：**坐上去的**对手是 snap 过的，而二分游标仍走原始中点。两者只有在中点
        # 恰好可坐时才是同一个数（见 `expected_opponent_rung` 的 docstring）。
        mid = (lo + hi) // 2
        seated = expected_opponent_rung(None, lo, hi)
        snapshot = AiLadderOpponentSnapshot(
            rung=seated,
            rank_name=f"fixture-{seated}",
            config_snapshot={"config_digest": f"fixture-{seated}", "config_version": "fixture-v1"},
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
    # 落点也 snap；这三个 expected_rung(1/32/22) 本身就可坐，所以 snap 是恒等。
    assert expected_rung in ladder_module.PLAYABLE_RUNGS
    assert outcome.ai_ladder_rung == expected_rung
    assert outcome.net_score == 0


def test_existing_legacy_rank_still_requires_all_five_placement_games(session_factory, user):
    repo = AiLadderRankedRepository(session_factory)
    lo, hi = initial_placement_window("5d")
    assert (lo, hi) == (10, 41)

    for round_number in range(1, 6):
        mid = (lo + hi) // 2
        seated = expected_opponent_rung(None, lo, hi)
        snapshot = AiLadderOpponentSnapshot(
            rung=seated,
            rank_name=f"fixture-{seated}",
            config_snapshot={"config_digest": str(seated), "recipe_identity": f"fixture-recipe-{seated}"},
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


# 1级 is rung 20, 准1段 is rung 21 and 1段 is rung 22. The step counts rungs a player can
# actually be seated on (§6 of 2026-08-04-41-tier-rated-play-integration-design.md); 准1段 is
# retired (2026-08-13), so 1级 promotes straight to 1段(22). Downward, 2级(19) is playable,
# so a demotion is one raw rung -- the two directions are asymmetric on purpose.
@pytest.mark.parametrize(("start", "results", "expected"), [(20, ["win"] * 3, 22), (20, ["loss"] * 3, 19)])
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
        # 一个可坐但**不是**搜索排给他的档位。不写死数字：2026-08-20 之前写死的 24 正好
        # 变成了正确答案，那次这条用例是靠别处红才被发现的。
        (AI_LADDER_GAME_TYPE, "win", {"rung": "OTHER_PLAYABLE_RUNG"}, "opponent_rung_mismatch"),
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
    valid_opponent = replace(opponent, rung=PLACEMENT_RUNG_5D)
    if first_snapshot and first_snapshot.get("rung") == "OTHER_PLAYABLE_RUNG":
        other = ladder_module.step_playable_rung(PLACEMENT_RUNG_5D, 1)
        assert other != PLACEMENT_RUNG_5D
        first_snapshot = {**first_snapshot, "rung": other}
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
    valid_opponent = replace(opponent, rung=PLACEMENT_RUNG_5D)
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
                opponent_rung=PLACEMENT_RUNG_5D,
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

    # 一个**明确不对**的对手：可坐、但不是搜索排给他的那一档。写成推导式，免得阶梯一变
    # 这个"错的"悄悄变成"对的"—— 2026-08-20 就正好发生过（原来写死的 24 变成了正确答案）。
    from katrain.core import ladder

    wrong_rung = ladder.step_playable_rung(PLACEMENT_RUNG_5D, 1)
    assert wrong_rung != PLACEMENT_RUNG_5D
    placement = settle(repo, user.id, "wrong-placement-opponent", "win", replace(opponent, rung=wrong_rung))
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
    opponent = replace(opponent, rung=PLACEMENT_RUNG_5D)

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
    mutable_opponent = replace(opponent, rung=PLACEMENT_RUNG_5D, config_snapshot=mutable_config)
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

    settle(repo, user.id, "legacy-independent", "win", replace(opponent, rung=PLACEMENT_RUNG_5D))

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


# --- 让掉一个从没开起来的预约 --------------------------------------------------
#
# 这一节此前守的是另一条规则(「等够 30 分钟就放弃一笔送不到的成绩」),那条规则
# 2026-08-11 被产品方撤销:占位只有一个价钱。规则过期了,但它当初守的**陷阱**没有 ——
# 陷阱只是换了出口,从 `release_abandoned_settlement` 换到 `release_unplayed_reservation`。
# 下面四条按新出口的形状重写,守的仍然是原来那四个陷阱。


def test_releasing_an_unplayed_reservation_banks_nothing_and_moves_no_rating(session_factory, user, opponent):
    """让掉一个从没开起来的预约:占位当场放开,**不写账本、不留棋谱、不动分**。

    「云端登记过、盘面从没开起来」不是一个判决。把它当 `inconclusive` 写进账本,等于声称
    我们知道这局没下出结果,而我们真正知道的是它从来没开始;判一场负更糟 —— 那是一场
    没人下过、也没法向用户解释的负。

    这个判据能成立,靠的是 `/start` 的写序:`session_id` 是 activate 返回之后才发给客户端的,
    而 activate 正是把状态推离 `reserved` 的那次写。所以在锁下读到 `reserved`,就等于
    **任何一端都还没有人拿到这盘棋**。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))

    released = repo.release_unplayed_reservation(
        user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b"
    )

    assert (released.cancelled, released.receipt) == (True, None)
    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id) is None, "占位必须当场放开"
        assert db.query(models_db.AiLadderGameLedger).count() == 0, "让掉不是判决,不该留下账本行"
        assert db.query(models_db.UserGame).count() == 0, "没有对局记录 —— 这盘棋从没开起来过"
        assert db.query(models_db.AiLadderProfile).count() == 0, "段位一步都不许动"


def test_a_released_reservation_leaves_its_game_id_settleable(session_factory, user, opponent):
    """让掉之后,同一个 game_id 的结算仍然照真结果入账。

    这是「不写账本」那个决定的**回报**,也是它唯一说得过去的理由:换成写一条 inconclusive
    墓碑,账本先到先得,这里就会重放出「不计分」—— 一局真下过的棋被一次「从没开始」的
    登记永久抹掉。

    `settle_game` 走的是 `active is None` 那条分支(占位行已经被让掉了),所以这条同时
    钉住:让掉不能在别处留下任何挡住结算的残留。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
    repo.release_unplayed_reservation(user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b")

    late = repo.settle_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        user_color="B",
        result="win",
        game_type=AI_LADDER_GAME_TYPE,
        opponent=replace(opponent, rung=PLACEMENT_RUNG_5D),
    )

    assert (late.counted, late.reason) == (True, None)


def test_release_returns_the_real_receipt_when_the_result_already_landed(session_factory, user, opponent):
    """账本先查,状态后判 —— 陷阱换了出口,形状一模一样。

    端点是「先读 lifecycle 看见 `reserved`,再调这里释放」,两步之间有缝:原盒子恰在此时
    把真结果交上来,占位行就没了、账本行有了。这时诚实的回答是那张回执。

    把账本查询排在状态判断之后,`_lock_lifecycle` 会先抛 NotFound —— 用户按下的那一下
    得到的是「查无此局」,而他刚刚赢的那局其实已经计了分。这就是那种「正确分支永远到不了」
    的形状,原来那条测试守的正是它。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    repo.finalize_reserved_game(
        user_id=user.id,
        game_id=reservation.game.game_id,
        terminal_source="played_result",
        result="win",
        deciding_device_id="device-a",
        reservation_key=reservation.reservation_key,
        game_record=complete_game_record(user_color="B", result="win"),
    )

    outcome = repo.release_unplayed_reservation(
        user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b"
    )

    assert outcome.cancelled is False
    assert outcome.receipt is not None
    assert (outcome.receipt.result, outcome.receipt.counted) == ("win", True)


@pytest.mark.parametrize("state", ["active", "pending_settlement"])
def test_a_game_that_really_started_is_never_releasable(session_factory, user, opponent, state):
    """真开起来的局绝不可被让掉 —— 无论它开了多久、结果在不在路上。

    原来这条守的是「在下的棋不许当成待送达的结果放掉」。出口换了,陷阱一字未改:让掉
    不计分,所以任何一条能把**真下过的局**送进让掉的路,都是一次免费弃局 —— 劣势局面下
    它严格优于认输,正是段位并发规则要防的东西。

    两个状态都要挡:`active`(在下)与 `pending_settlement`(下完了、成绩在送)。后者今天
    与 `active` 同价(认输记一负),把它漏在这里,那个价钱就有了绕过去的路。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
    repo.activate_reservation(
        user_id=user.id,
        game_id=reservation.game.game_id,
        reservation_key=reservation.reservation_key,
        origin_device_id="device-a",
        origin_session_id="session-a",
    )
    if state == "pending_settlement":
        repo.mark_pending_settlement(
            user_id=user.id,
            game_id=reservation.game.game_id,
            reservation_key=reservation.reservation_key,
            origin_device_id="device-a",
        )

    with pytest.raises(AiLadderLifecycleConflict):
        repo.release_unplayed_reservation(
            user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b"
        )

    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id).state == state, "占位必须原封不动"


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
        reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D), game_id=taken.game.game_id)

    # 而且没有留下半条预约 —— 拒绝必须是彻底的,否则挡住的只是账本那一半。
    with session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).filter_by(user_id=user.id).one_or_none() is None


def test_a_reservation_that_never_started_can_never_be_resigned(session_factory, user, opponent):
    """没开过局的占位**不许记负** —— 而且这条规则钉在写账本的这个函数上,不在路由里。

    ⚠️ **这条测试是一次反转,前一版逐字断言了相反的行为**
    (`test_ending_an_unplayed_reservation_banks_a_loss_on_purpose`,「释放占位不能是免费的,
    否则『开一局、看一眼对手、不想下就免费退掉』可以反复刷」)。反转的理由,按当时那条给的
    理由逐条对:

    1. **经 `/start` 选不进这个状态。** 顺序是 reserve → 建 session → activate → 才把
       `session_id` 发出去,activate 失败就 `remove_session` 并抛错。所以**经 `/start` 拿到过
       棋盘的人手上一定是 `active`**,`reserved` 只在「棋盘压根没开起来」时留存 —— 免费释放的
       不是一局棋,是一次失败的开局。跑出来的:`test_a_failed_activation_hands_the_player_
       no_board_so_reserved_means_no_game`(test_ai_ladder_api.py)。

       ⚠️ **这条只覆盖 `/start` 那条路,别写成无条件的。** `POST /games/reserve`
       (endpoints/ai_ladder.py)是**独立端点、不接 activate**,一个拿着有效凭据的客户端
       确实可以自己停在 `reserved` 里。所以「用户选不进这个状态」是句假话;真话是
       「**经 `/start` 时**选不进」。(2026-08-16 team lead 驳中,原论证在这里过宽。)
    1b. **而且无论走哪条路,预约都不揭示任何新信息** —— 这一条不依赖 `/start` 的顺序,
       所以上面那个洞补得掉。原裁定要防的是「开一局**看一眼对手**就退掉」,而围棋这一眼
       看不到任何东西:对手档位是 `expected_opponent_rung(rung, lo, hi)`,一个**自己档案的
       纯函数**,而档案在 `/status` 里就发给客户端了。⇒「看一眼」这个动作没有内容。
       跑出来的:`test_reserving_reveals_nothing_that_status_did_not_already_hand_over`。
    2. **生产早就这么做了。** `/end` 读到 `reserved` 时走 `release_unplayed_reservation`,
       不写账本行、不动段位。这条 guard 不是新政策,是把那条政策搬到唯一写账本的地方 ——
       原来它只活在端点里的一个 `if`,一次重构就没了,而账本不可变:写错一行负改不回来。
    3. 四家统一口径的判据是**「服务端从没收到过这一局的心跳」**这一类的**代理量**
       (2026-08-16 定;更早那版「有没有走过一手」已作废 —— 云端手上根本没有着法,着法只在
       结算那一刻上云,而免费释放走的恰恰是没有结算载荷的那条路)。围棋用的代理量是
       `state == "reserved"`,它比心跳**更靠前也更准**:activate 挂在棋盘建起来那一刻,
       心跳是之后的定时器,一局 `active` 的棋可以一次心跳都还没发。象棋那条代理量误盖的
       「盒子离线把一整局下完了」,在围棋这里盖不到 —— 理由与「围棋为什么可以删行」是同一条,
       写在 `ai_ladder_ranked.py` 的 `release_unplayed_reservation` 里。

    合成棋谱那条代价也随之消失:这一格不再写 `user_games`,因为它根本不落账。
    """

    repo = AiLadderRankedRepository(session_factory)
    reservation = reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D))
    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id).state == "reserved"

    with pytest.raises(AiLadderLifecycleConflict):
        repo.finalize_reserved_game(
            user_id=user.id,
            game_id=reservation.game.game_id,
            terminal_source="remote_resign",
            result="loss",
            deciding_device_id="device-b",
        )

    # 被拒了就**什么都不许留下**:没有账本行、没有合成棋谱、没有段位。占位原样还在,
    # 用户走 `release_unplayed_reservation` 免费拿回它。
    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id).state == "reserved"
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0

    released = repo.release_unplayed_reservation(
        user_id=user.id, game_id=reservation.game.game_id, deciding_device_id="device-b"
    )
    assert (released.cancelled, released.receipt) == (True, None)
    with session_factory() as db:
        assert db.get(models_db.AiLadderActiveGame, reservation.game.game_id) is None
        assert db.query(models_db.AiLadderGameLedger).count() == 0


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
        reserve(repo, user.id, replace(opponent, rung=PLACEMENT_RUNG_5D), game_id=game_id)

    with session_factory() as db:
        assert (
            db.query(models_db.AiLadderActiveGame).filter_by(user_id=user.id).one_or_none() is None
        ), "预约建成了,而它的每一条出路都被那行 user_games 挡着 —— 账号从此锁死"
