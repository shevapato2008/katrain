from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
USER_UUID = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ranked-models.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    models_db.Base.metadata.create_all(engine)
    migrations.install_xiangqi_ranked_immutability(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _user():
    return models_db.User(uuid=USER_UUID, username="first-name", hashed_password="x")


def _profile():
    return models_db.XiangqiRatingProfile(
        user_uuid=USER_UUID,
        rating=1000.0,
        rated_games=0,
        profile_version=0,
        active_algo_version=4,
        settlement_seq=0,
        updated_at=NOW,
    )


def _reservation(
    *, reservation_id="660e8400-e29b-41d4-a716-446655440000", game_id="550e8400-e29b-41d4-a716-446655440000"
):
    return models_db.XiangqiRankedReservation(
        reservation_id=reservation_id,
        game_id=game_id,
        user_uuid=USER_UUID,
        device_id="box-01",
        status="reserved",
        expected_profile_version=0,
        projection_fingerprint="1" * 64,
        frozen_snapshot={
            "schema": "xiangqi-ranked-reservation-v1",
            "rating_hex": (1000.0).hex(),
            "outcome_loss_hex": (998.0).hex(),
        },
        last_heartbeat_at=NOW,
        created_at=NOW,
    )


def _ledger():
    return models_db.XiangqiRankedLedger(
        receipt_id="770e8400-e29b-41d4-a716-446655440000",
        game_id="550e8400-e29b-41d4-a716-446655440000",
        reservation_id="660e8400-e29b-41d4-a716-446655440000",
        user_uuid=USER_UUID,
        device_id="box-01",
        local_seq=1,
        terminal_status="settled",
        payload_hash="2" * 64,
        canonical_payload={"rating_before_hex": (1000.0).hex(), "result": "win"},
        frozen_snapshot={"rating_hex": (1000.0).hex()},
        result="win",
        counted=True,
        reason=None,
        rating_before=1000.0,
        rating_after=1038.0,
        rating_delta=38,
        tier_before="十二级棋士",
        tier_after="十二级棋士",
        profile_version_before=0,
        profile_version_after=1,
        settlement_seq=1,
        received_at=NOW,
        settled_at=NOW,
        receipt={"game_id": "550e8400-e29b-41d4-a716-446655440000", "rating_after_hex": (1038.0).hex()},
    )


def test_ranked_models_have_explicit_keys_foreign_keys_checks_and_partial_unique_index(database):
    engine, _ = database
    inspector = inspect(engine)

    assert migrations.XIANGQI_RANKED_TABLES == {
        "xiangqi_rating_profiles",
        "xiangqi_ranked_reservations",
        "xiangqi_ranked_ledger",
        "xiangqi_ranked_capability_jtis",
    }
    assert migrations.XIANGQI_RANKED_TABLES < migrations.PROTECTED_TABLES
    assert inspector.get_pk_constraint("xiangqi_rating_profiles")["constrained_columns"] == ["user_uuid"]
    assert inspector.get_pk_constraint("xiangqi_ranked_reservations")["constrained_columns"] == ["reservation_id"]
    assert any(
        fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_uuid"]
        for fk in inspector.get_foreign_keys("xiangqi_rating_profiles")
    )
    indexes = {index["name"]: index for index in inspector.get_indexes("xiangqi_ranked_reservations")}
    assert indexes["uq_xiangqi_ranked_one_reserved_per_user"]["unique"]
    where = indexes["uq_xiangqi_ranked_one_reserved_per_user"]["dialect_options"]["sqlite_where"]
    assert str(where.compile(dialect=engine.dialect)) == "status = 'reserved'"
    assert any(
        constraint["column_names"] == ["game_id"]
        for constraint in inspector.get_unique_constraints("xiangqi_ranked_reservations")
    )


def test_database_enforces_global_game_and_one_reserved_per_account(database):
    _, sessions = database
    with sessions() as session:
        session.add(_user())
        session.add(_profile())
        session.add(_reservation())
        session.commit()

        session.add(
            _reservation(
                reservation_id="880e8400-e29b-41d4-a716-446655440000",
                game_id="990e8400-e29b-41d4-a716-446655440000",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        first = session.get(models_db.XiangqiRankedReservation, "660e8400-e29b-41d4-a716-446655440000")
        first.status = "settled"
        first.terminal_at = NOW
        session.commit()
        session.add(
            _reservation(
                reservation_id="880e8400-e29b-41d4-a716-446655440000",
                game_id="990e8400-e29b-41d4-a716-446655440000",
            )
        )
        session.commit()

        session.add(
            _reservation(
                reservation_id="aa0e8400-e29b-41d4-a716-446655440000",
                game_id="990e8400-e29b-41d4-a716-446655440000",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_capability_jti_rotation_keeps_one_current_token_and_revocation_history(database):
    _, sessions = database
    with sessions() as session:
        session.add(_user())
        session.add(_profile())
        session.add(_reservation())
        session.add(
            models_db.XiangqiRankedCapabilityJti(
                jti="jti-1",
                reservation_id="660e8400-e29b-41d4-a716-446655440000",
                issued_at=NOW,
                revoked_at=None,
            )
        )
        session.commit()
        session.add(
            models_db.XiangqiRankedCapabilityJti(
                jti="jti-2",
                reservation_id="660e8400-e29b-41d4-a716-446655440000",
                issued_at=NOW,
                revoked_at=None,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        first = session.get(models_db.XiangqiRankedCapabilityJti, "jti-1")
        first.revoked_at = NOW
        session.add(
            models_db.XiangqiRankedCapabilityJti(
                jti="jti-2",
                reservation_id="660e8400-e29b-41d4-a716-446655440000",
                issued_at=NOW,
                revoked_at=None,
            )
        )
        session.commit()
        assert session.query(models_db.XiangqiRankedCapabilityJti).count() == 2
        assert session.get(models_db.XiangqiRankedCapabilityJti, "jti-1").revoked_at is not None


def test_ledger_update_and_delete_are_rejected_by_database_triggers(database):
    engine, sessions = database
    with sessions() as session:
        session.add(_user())
        session.add(_profile())
        reservation = _reservation()
        reservation.status = "settled"
        reservation.terminal_at = NOW
        session.add(reservation)
        session.add(_ledger())
        session.commit()

    for statement in (
        "UPDATE xiangqi_ranked_ledger SET reason='rewritten' WHERE game_id=:game_id",
        "DELETE FROM xiangqi_ranked_ledger WHERE game_id=:game_id",
    ):
        with pytest.raises(Exception, match="immutable"):
            with engine.begin() as connection:
                connection.execute(text(statement), {"game_id": "550e8400-e29b-41d4-a716-446655440000"})

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM xiangqi_ranked_ledger")).scalar_one() == 1


@pytest.mark.parametrize(
    "terminal_status,result,counted,reason,rating_after",
    [
        ("resigned", "win", True, None, 1010.0),
        ("system_aborted", None, True, None, 1010.0),
        ("settled", "win", False, None, None),
        ("system_aborted", None, False, "system_fault", 1000.0),
    ],
)
def test_ledger_terminal_fact_check_constraints_fail_closed(
    database, terminal_status, result, counted, reason, rating_after
):
    _, sessions = database
    with sessions() as session:
        session.add(_user())
        session.add(_profile())
        reservation = _reservation()
        reservation.status = terminal_status
        reservation.terminal_at = NOW
        session.add(reservation)
        ledger = _ledger()
        ledger.terminal_status = terminal_status
        ledger.result = result
        ledger.counted = counted
        ledger.reason = reason
        ledger.rating_after = rating_after
        session.add(ledger)
        with pytest.raises(IntegrityError):
            session.commit()
