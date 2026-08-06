from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db
from katrain.web.core.xiangqi_ranked_repo import ReservationConflict, TerminalConflict, XiangqiRankedRepository


POSTGRES_URL = os.environ.get("XIANGQI_RANKED_TEST_DATABASE_URL")
if not POSTGRES_URL:
    raise RuntimeError("XIANGQI_RANKED_TEST_DATABASE_URL is required; use scripts/test-xiangqi-ranked-postgres.sh")

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
USER_UUID = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def pg_repo():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    models_db.Base.metadata.create_all(engine)
    migrations.install_xiangqi_ranked_immutability(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.add(models_db.User(uuid=USER_UUID, username="pg-owner", hashed_password="x"))
    yield XiangqiRankedRepository(sessions), sessions
    engine.dispose()


def _snapshot():
    return {
        "schema": "xiangqi-ranked-reservation-v1",
        "rating_hex": (1000.0).hex(),
        "profile_version": 0,
        "outcome_win_hex": (1038.0).hex(),
        "outcome_loss_hex": (998.0).hex(),
    }


def _reserve(repo, suffix, barrier=None, expected_profile_version=0):
    if barrier:
        barrier.wait(timeout=10)
    try:
        row = repo.create_reservation_cas(
            user_uuid=USER_UUID,
            reservation_id=f"660e8400-e29b-41d4-a716-44665544{suffix:04d}",
            game_id=f"550e8400-e29b-41d4-a716-44665544{suffix:04d}",
            device_id=f"box-{suffix}",
            expected_profile_version=expected_profile_version,
            projection_fingerprint="1" * 64,
            frozen_snapshot=_snapshot(),
            now=NOW,
        )
        return row
    except ReservationConflict:
        return "conflict"


def _terminal(repo, row, status, barrier):
    barrier.wait(timeout=10)
    counted = status != "system_aborted"
    try:
        return repo.settle_terminal(
            user_uuid=USER_UUID,
            reservation_id=row.reservation_id,
            game_id=row.game_id,
            device_id=row.device_id,
            terminal_status=status,
            local_seq=1,
            payload_hash={"settled": "3", "resigned": "4", "system_aborted": "5"}[status] * 64,
            canonical_payload={"event_kind": status},
            result="loss" if status == "resigned" else ("win" if counted else None),
            counted=counted,
            reason=None if counted else "system_fault",
            rating_after=998.0 if status == "resigned" else (1038.0 if counted else None),
            rating_delta=-2 if status == "resigned" else (38 if counted else None),
            tier_before="十二级棋士",
            tier_after="十二级棋士" if counted else None,
            receipt_id=f"770e8400-e29b-41d4-a716-44665544{status.__len__():04d}",
            now=NOW + timedelta(minutes=1),
        )
    except TerminalConflict:
        return "conflict"


def test_postgres_for_update_partial_unique_terminal_race_takeover_and_release(pg_repo):
    repo, sessions = pg_repo

    reserve_gate = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reservations = list(pool.map(lambda suffix: _reserve(repo, suffix, reserve_gate), (1, 2)))
    assert reservations.count("conflict") == 1
    row = next(item for item in reservations if item != "conflict")

    terminal_gate = Barrier(3)
    with ThreadPoolExecutor(max_workers=3) as pool:
        terminals = list(
            pool.map(
                lambda status: _terminal(repo, row, status, terminal_gate), ("settled", "resigned", "system_aborted")
            )
        )
    assert terminals.count("conflict") == 2
    winner = next(item for item in terminals if item != "conflict")
    assert winner["status"] in {"settled", "resigned", "system_aborted"}

    with sessions() as session:
        assert session.query(models_db.XiangqiRankedLedger).count() == 1
        assert session.query(models_db.XiangqiRankedReservation).filter_by(status="reserved").count() == 0

    with sessions() as session:
        current_version = session.get(models_db.XiangqiRatingProfile, USER_UUID).profile_version
    next_row = _reserve(repo, 3, expected_profile_version=current_version)
    assert next_row != "conflict"
    repo.heartbeat(
        user_uuid=USER_UUID,
        reservation_id=next_row.reservation_id,
        device_id=next_row.device_id,
        now=NOW + timedelta(minutes=2),
    )
    with pytest.raises(ReservationConflict, match="heartbeat"):
        repo.force_resign_after_threshold(
            user_uuid=USER_UUID,
            reservation_id=next_row.reservation_id,
            game_id=next_row.game_id,
            now=NOW + timedelta(minutes=2, seconds=29),
            stale_after=timedelta(seconds=30),
            local_seq=2,
            payload_hash="6" * 64,
            canonical_payload={"event_kind": "resign"},
            rating_after=996.0,
            rating_delta=-2,
            tier_before="十二级棋士",
            tier_after="十二级棋士",
            receipt_id="990e8400-e29b-41d4-a716-446655440000",
        )
    takeover = repo.force_resign_after_threshold(
        user_uuid=USER_UUID,
        reservation_id=next_row.reservation_id,
        game_id=next_row.game_id,
        now=NOW + timedelta(minutes=2, seconds=30),
        stale_after=timedelta(seconds=30),
        local_seq=2,
        payload_hash="6" * 64,
        canonical_payload={"event_kind": "resign"},
        rating_after=996.0,
        rating_delta=-2,
        tier_before="十二级棋士",
        tier_after="十二级棋士",
        receipt_id="990e8400-e29b-41d4-a716-446655440000",
    )
    assert takeover["status"] == "resigned"
    assert _reserve(repo, 4, expected_profile_version=current_version + 1) != "conflict"

    with sessions() as session:
        profile = session.execute(
            select(models_db.XiangqiRatingProfile).where(models_db.XiangqiRatingProfile.user_uuid == USER_UUID)
        ).scalar_one()
        assert profile.settlement_seq == 2

    engine = sessions.kw["bind"]
    for statement in (
        "UPDATE xiangqi_ranked_ledger SET reason='rewritten' WHERE game_id=:game_id",
        "DELETE FROM xiangqi_ranked_ledger WHERE game_id=:game_id",
    ):
        with pytest.raises(Exception, match="immutable"):
            with engine.begin() as connection:
                connection.execute(text(statement), {"game_id": row.game_id})
