from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import create_engine, event, inspect as sa_inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db
from katrain.web.core.xiangqi_ranked_repo import (
    ReservationConflict,
    StaleProfile,
    TerminalConflict,
    XiangqiRankedRepository,
)


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
USER_UUID = "0123456789abcdef0123456789abcdef"
RESERVATION_ID = "660e8400-e29b-41d4-a716-446655440000"
GAME_ID = "550e8400-e29b-41d4-a716-446655440000"


def snapshot(*, rating=1000.0, profile_version=0):
    return {
        "schema": "xiangqi-ranked-reservation-v1",
        "user_uuid": USER_UUID,
        "profile_version": profile_version,
        "rating_hex": rating.hex(),
        "rated_games": 0,
        "scoring_contract_version": 4,
        "catalog_version": "pikafish-r1",
        "opponent_level": 3,
        "opponent_profile_hash": "2" * 64,
        "time_control": "standard10",
        "player_color": "red",
        "outcome_win_hex": (1038.0).hex(),
        "outcome_draw_hex": (1018.0).hex(),
        "outcome_loss_hex": (998.0).hex(),
        "delta_win": 38,
        "delta_draw": 18,
        "delta_loss": -2,
        "tier_win": "十二级棋士",
        "tier_draw": "十二级棋士",
        "tier_loss": "十二级棋士",
    }


@pytest.fixture
def repo(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ranked-repo.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    models_db.Base.metadata.create_all(engine)
    migrations.install_xiangqi_ranked_immutability(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.add(models_db.User(uuid=USER_UUID, username="name-one", hashed_password="x"))
    return XiangqiRankedRepository(sessions), sessions


def reserve(
    repo,
    *,
    reservation_id=RESERVATION_ID,
    game_id=GAME_ID,
    device_id="box-01",
    expected_profile_version=0,
    now=NOW,
):
    return repo.create_reservation_cas(
        user_uuid=USER_UUID,
        reservation_id=reservation_id,
        game_id=game_id,
        device_id=device_id,
        expected_profile_version=expected_profile_version,
        projection_fingerprint="1" * 64,
        frozen_snapshot=snapshot(profile_version=expected_profile_version),
        now=now,
    )


def settle(repo, *, terminal_status="settled", payload_hash="3" * 64, failure_hook=None, now=NOW):
    counted = terminal_status != "system_aborted"
    result = "loss" if terminal_status == "resigned" else ("win" if counted else None)
    return repo.settle_terminal(
        user_uuid=USER_UUID,
        reservation_id=RESERVATION_ID,
        game_id=GAME_ID,
        device_id="box-01",
        terminal_status=terminal_status,
        local_seq=1,
        payload_hash=payload_hash,
        canonical_payload={"payload_schema": "xiangqi-ranked-event-v2", "result": result},
        result=result,
        counted=counted,
        reason=None if counted else "engine_unavailable",
        rating_after=998.0 if terminal_status == "resigned" else (1038.0 if counted else None),
        rating_delta=-2 if terminal_status == "resigned" else (38 if counted else None),
        tier_before="十二级棋士",
        tier_after="十二级棋士" if counted else None,
        receipt_id="770e8400-e29b-41d4-a716-446655440000",
        now=now,
        failure_hook=failure_hook,
    )


def test_first_stable_uuid_creates_one_initial_profile_and_rename_does_not_change_identity(repo):
    repository, sessions = repo
    with sessions.begin() as session:
        first = repository.get_or_create_profile_for_update(session, USER_UUID, now=NOW)
        assert (first.user_uuid, first.rating, first.rated_games, first.profile_version) == (
            USER_UUID,
            1000.0,
            0,
            0,
        )
    with sessions.begin() as session:
        user = session.execute(select(models_db.User).where(models_db.User.uuid == USER_UUID)).scalar_one()
        user.username = "renamed-display-name"
    with sessions.begin() as session:
        same = repository.get_or_create_profile_for_update(session, USER_UUID, now=NOW + timedelta(minutes=1))
        assert same.user_uuid == USER_UUID
        assert session.query(models_db.XiangqiRatingProfile).count() == 1


def test_repository_owned_sessions_return_stable_values_with_production_expiration_default(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ranked-expiring-session.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    models_db.Base.metadata.create_all(engine)
    migrations.install_xiangqi_ranked_immutability(engine)
    sessions = sessionmaker(bind=engine)  # production default: expire_on_commit=True
    with sessions.begin() as session:
        session.add(models_db.User(uuid=USER_UUID, username="expiring-owner", hashed_password="x"))
    repository = XiangqiRankedRepository(sessions)

    statements = []
    event.listen(engine, "before_cursor_execute", lambda *_args: statements.append(_args[2]))
    reservation = reserve(repository)
    count_after_reserve = len(statements)
    public_reservation_values = (
        reservation.reservation_id,
        reservation.game_id,
        reservation.user_uuid,
        reservation.device_id,
        reservation.status,
        reservation.expected_profile_version,
        reservation.projection_fingerprint,
        reservation.frozen_snapshot["rating_hex"],
        reservation.last_heartbeat_at,
        reservation.created_at,
        reservation.materialized_at,
        reservation.terminal_at,
    )
    assert sa_inspect(reservation, raiseerr=False) is None
    assert public_reservation_values[:5] == (RESERVATION_ID, GAME_ID, USER_UUID, "box-01", "reserved")
    assert len(statements) == count_after_reserve

    heartbeat = repository.heartbeat(
        user_uuid=USER_UUID,
        reservation_id=RESERVATION_ID,
        device_id="box-01",
        now=NOW + timedelta(seconds=5),
    )
    count_after_heartbeat = len(statements)
    public_heartbeat_values = (
        heartbeat.reservation_id,
        heartbeat.game_id,
        heartbeat.user_uuid,
        heartbeat.device_id,
        heartbeat.status,
        heartbeat.expected_profile_version,
        heartbeat.projection_fingerprint,
        heartbeat.frozen_snapshot["rating_hex"],
        heartbeat.last_heartbeat_at,
        heartbeat.created_at,
        heartbeat.materialized_at,
        heartbeat.terminal_at,
    )
    assert sa_inspect(heartbeat, raiseerr=False) is None
    assert public_heartbeat_values[0:5] == (RESERVATION_ID, GAME_ID, USER_UUID, "box-01", "reserved")
    assert len(statements) == count_after_heartbeat

    receipt = settle(repository, now=NOW + timedelta(seconds=10))
    persisted = repository.get_receipt(user_uuid=USER_UUID, game_id=GAME_ID)
    device_page = repository.page_device_statuses(
        user_uuid=USER_UUID,
        device_id="box-01",
        after_local_seq=0,
        through_local_seq=1,
    )
    summary_page = repository.page_settlement_summaries(
        user_uuid=USER_UUID,
        after_seq=0,
        snapshot_seq=1,
    )
    assert all(sa_inspect(value, raiseerr=False) is None for value in (receipt, persisted, device_page, summary_page))
    assert receipt == persisted == device_page["items"][0]["receipt"] == summary_page["items"][0]


def test_reservation_cas_rejects_stale_profile_and_keeps_database_empty(repo):
    repository, sessions = repo
    with pytest.raises(StaleProfile):
        repository.create_reservation_cas(
            user_uuid=USER_UUID,
            reservation_id=RESERVATION_ID,
            game_id=GAME_ID,
            device_id="box-01",
            expected_profile_version=1,
            projection_fingerprint="1" * 64,
            frozen_snapshot=snapshot(profile_version=1),
            now=NOW,
        )
    with sessions() as session:
        assert session.query(models_db.XiangqiRankedReservation).count() == 0


def test_two_independent_sessions_concurrently_reserve_only_one_barrier(repo):
    repository, sessions = repo
    gate = Barrier(2)

    def worker(suffix):
        gate.wait(timeout=5)
        try:
            repository.create_reservation_cas(
                user_uuid=USER_UUID,
                reservation_id=f"660e8400-e29b-41d4-a716-44665544{suffix:04d}",
                game_id=f"550e8400-e29b-41d4-a716-44665544{suffix:04d}",
                device_id=f"box-{suffix}",
                expected_profile_version=0,
                projection_fingerprint="1" * 64,
                frozen_snapshot=snapshot(),
                now=NOW,
            )
            return "reserved"
        except ReservationConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(worker, (1, 2)))
    assert outcomes == ["conflict", "reserved"]
    with sessions() as session:
        assert session.query(models_db.XiangqiRankedReservation).filter_by(status="reserved").count() == 1


def test_terminal_transaction_atomically_updates_profile_ledger_receipt_and_releases_barrier(repo):
    repository, sessions = repo
    reserve(repository)
    receipt = settle(repository)

    assert receipt["rating_before_hex"] == (1000.0).hex()
    assert receipt["rating_after_hex"] == (1038.0).hex()
    assert receipt["profile_version_after"] == 1
    assert receipt["settlement_seq"] == 1
    assert repository.get_receipt(user_uuid=USER_UUID, game_id=GAME_ID) == receipt

    with sessions() as session:
        profile = session.get(models_db.XiangqiRatingProfile, USER_UUID)
        reservation = session.get(models_db.XiangqiRankedReservation, RESERVATION_ID)
        ledger = session.execute(select(models_db.XiangqiRankedLedger)).scalar_one()
        assert (profile.rating, profile.rated_games, profile.profile_version, profile.settlement_seq) == (
            1038.0,
            1,
            1,
            1,
        )
        assert reservation.status == "settled"
        assert reservation.terminal_at.replace(tzinfo=timezone.utc) == NOW
        assert ledger.receipt == receipt

    reserve(
        repository,
        reservation_id="880e8400-e29b-41d4-a716-446655440000",
        game_id="990e8400-e29b-41d4-a716-446655440000",
        expected_profile_version=1,
        now=NOW + timedelta(seconds=1),
    )


def test_injected_failure_rolls_back_profile_ledger_receipt_and_reservation_status(repo):
    repository, sessions = repo
    reserve(repository)

    def fail(phase):
        if phase == "before_commit":
            raise RuntimeError("injected terminal failure")

    with pytest.raises(RuntimeError, match="injected terminal failure"):
        settle(repository, failure_hook=fail)

    with sessions() as session:
        profile = session.get(models_db.XiangqiRatingProfile, USER_UUID)
        reservation = session.get(models_db.XiangqiRankedReservation, RESERVATION_ID)
        assert (profile.rating, profile.rated_games, profile.profile_version, profile.settlement_seq) == (
            1000.0,
            0,
            0,
            0,
        )
        assert (reservation.status, reservation.terminal_at) == ("reserved", None)
        assert session.query(models_db.XiangqiRankedLedger).count() == 0


def test_two_terminal_workers_have_one_winner_and_idempotent_replay_is_exact(repo):
    repository, sessions = repo
    reserve(repository)
    gate = Barrier(2)

    def worker(status):
        gate.wait(timeout=5)
        try:
            return status, settle(
                repository, terminal_status=status, payload_hash=("3" if status == "settled" else "4") * 64
            )
        except TerminalConflict:
            return status, "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = dict(pool.map(worker, ("settled", "resigned")))
    assert list(outcomes.values()).count("conflict") == 1
    winner_receipt = next(value for value in outcomes.values() if isinstance(value, dict))
    assert repository.get_receipt(user_uuid=USER_UUID, game_id=GAME_ID) == winner_receipt
    with sessions() as session:
        assert session.query(models_db.XiangqiRankedLedger).count() == 1


def test_heartbeat_threshold_force_resign_and_void_unmaterialized(repo):
    repository, sessions = repo
    reserve(repository)
    repository.heartbeat(
        user_uuid=USER_UUID,
        reservation_id=RESERVATION_ID,
        device_id="box-01",
        now=NOW + timedelta(seconds=5),
    )
    with pytest.raises(ReservationConflict, match="heartbeat"):
        repository.force_resign_after_threshold(
            user_uuid=USER_UUID,
            reservation_id=RESERVATION_ID,
            game_id=GAME_ID,
            now=NOW + timedelta(seconds=34),
            stale_after=timedelta(seconds=30),
            local_seq=2,
            payload_hash="4" * 64,
            canonical_payload={"event_kind": "resign"},
            rating_after=998.0,
            rating_delta=-2,
            tier_before="十二级棋士",
            tier_after="十二级棋士",
            receipt_id="770e8400-e29b-41d4-a716-446655440000",
        )
    receipt = repository.force_resign_after_threshold(
        user_uuid=USER_UUID,
        reservation_id=RESERVATION_ID,
        game_id=GAME_ID,
        now=NOW + timedelta(seconds=35),
        stale_after=timedelta(seconds=30),
        local_seq=2,
        payload_hash="4" * 64,
        canonical_payload={"event_kind": "resign"},
        rating_after=998.0,
        rating_delta=-2,
        tier_before="十二级棋士",
        tier_after="十二级棋士",
        receipt_id="770e8400-e29b-41d4-a716-446655440000",
    )
    assert receipt["status"] == "resigned"

    second = reserve(
        repository,
        reservation_id="880e8400-e29b-41d4-a716-446655440000",
        game_id="990e8400-e29b-41d4-a716-446655440000",
        expected_profile_version=1,
        now=NOW + timedelta(minutes=1),
    )
    assert repository.void_unmaterialized(
        user_uuid=USER_UUID,
        reservation_id=second.reservation_id,
        game_id=second.game_id,
    )
    with sessions() as session:
        assert session.get(models_db.XiangqiRankedReservation, second.reservation_id) is None


def test_device_and_settlement_pages_have_independent_monotone_cursors(repo):
    repository, _ = repo
    reserve(repository)
    settle(repository)

    statuses = repository.page_device_statuses(
        user_uuid=USER_UUID,
        device_id="box-01",
        after_local_seq=0,
        through_local_seq=10,
        limit=1,
    )
    summaries = repository.page_settlement_summaries(
        user_uuid=USER_UUID,
        after_seq=0,
        snapshot_seq=10,
        limit=1,
    )
    assert statuses["items"][0]["local_seq"] == statuses["next_cursor"] == 1
    assert summaries["items"][0]["settlement_seq"] == summaries["next_cursor"] == 1
    assert statuses["items"][0]["payload_hash"] == "3" * 64
    assert summaries["items"][0]["rating_after_hex"] == (1038.0).hex()


def test_a_defect_shaped_integrity_error_is_not_dressed_up_as_a_conflict(repo):
    """外键、非空这类违例是自己这边的缺陷,不许穿上"别人先占了"这件外衣。

    云端在 PostgreSQL 上「每个账号第一次预约都失败、API 却回一句平静的 409 本账号已有
    进行中的预约」能藏那么久,就是因为这里把任何 IntegrityError 都翻成冲突——等于给自己的
    缺陷配了一个调用方会照单全收的解释。只有真的撞上唯一键才算冲突,其余照原样炸出来。
    """
    repository, _ = repo
    with pytest.raises(IntegrityError):
        repository.create_reservation_cas(
            user_uuid=USER_UUID,
            reservation_id=RESERVATION_ID,
            game_id=GAME_ID,
            device_id=None,          # NOT NULL:是我们自己传错了,不是别人抢先
            expected_profile_version=0,
            projection_fingerprint="1" * 64,
            frozen_snapshot=snapshot(),
            now=NOW,
        )
