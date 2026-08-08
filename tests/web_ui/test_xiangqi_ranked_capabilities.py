from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.xiangqi_ranked_capabilities import (
    TERMINAL_ACTIONS,
    TerminalCapabilityCodec,
    TerminalCapabilityError,
    TerminalCapabilityStore,
)


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
USER_UUID = "0123456789abcdef0123456789abcdef"
RESERVATION_ID = "660e8400-e29b-41d4-a716-446655440000"
GAME_ID = "550e8400-e29b-41d4-a716-446655440000"
SECRET = "ranked-capability-test-secret"


@pytest.fixture
def capability_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'capabilities.sqlite'}")
    models_db.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.add(models_db.User(uuid=USER_UUID, username="ranked-owner", hashed_password="x"))
        session.add(
            models_db.XiangqiRatingProfile(
                user_uuid=USER_UUID,
                rating=1000.0,
                rated_games=0,
                profile_version=0,
                active_algo_version=4,
                settlement_seq=0,
                updated_at=NOW,
            )
        )
        session.add(
            models_db.XiangqiRankedReservation(
                reservation_id=RESERVATION_ID,
                game_id=GAME_ID,
                user_uuid=USER_UUID,
                device_id="box-01",
                status="reserved",
                expected_profile_version=0,
                projection_fingerprint="1" * 64,
                frozen_snapshot={"schema": "xiangqi-ranked-reservation-v1"},
                last_heartbeat_at=NOW,
                created_at=NOW,
            )
        )
    clock = {"now": NOW}
    codec = TerminalCapabilityCodec(
        secret=SECRET,
        algorithm="HS256",
        ttl=timedelta(minutes=10),
        now=lambda: clock["now"],
        jti_factory=lambda: "jti-initial",
    )
    return TerminalCapabilityStore(sessions, codec), sessions, clock


def test_codec_requires_structured_terminal_claims_and_exact_binding():
    codec = TerminalCapabilityCodec(
        secret=SECRET,
        algorithm="HS256",
        ttl=timedelta(minutes=10),
        now=lambda: NOW,
        jti_factory=lambda: "jti-1",
    )
    token = codec.issue(
        user_uuid=USER_UUID,
        device_id="box-01",
        game_id=GAME_ID,
        reservation_id=RESERVATION_ID,
    )
    raw = jwt.get_unverified_claims(token)
    assert raw == {
        "aud": "xiangqi-ranked-terminal",
        "type": "terminal",
        "user_uuid": USER_UUID,
        "device_id": "box-01",
        "game_id": GAME_ID,
        "reservation_id": RESERVATION_ID,
        "jti": "jti-1",
        "actions": sorted(TERMINAL_ACTIONS),
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(minutes=10)).timestamp()),
    }
    claims = codec.verify(
        token,
        expected_user_uuid=USER_UUID,
        expected_device_id="box-01",
        expected_game_id=GAME_ID,
        expected_reservation_id=RESERVATION_ID,
        required_action="heartbeat",
    )
    assert claims.user_uuid == USER_UUID
    assert claims.jti == "jti-1"
    assert claims.actions == frozenset(TERMINAL_ACTIONS)


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("aud", "ordinary-api"),
        ("type", "access"),
        ("user_uuid", "fedcba9876543210fedcba9876543210"),
        ("device_id", "box-02"),
        ("game_id", "990e8400-e29b-41d4-a716-446655440000"),
        ("reservation_id", "880e8400-e29b-41d4-a716-446655440000"),
    ],
)
def test_codec_rejects_wrong_audience_type_or_binding(claim, value):
    payload = {
        "aud": "xiangqi-ranked-terminal",
        "type": "terminal",
        "user_uuid": USER_UUID,
        "device_id": "box-01",
        "game_id": GAME_ID,
        "reservation_id": RESERVATION_ID,
        "jti": "jti-tampered",
        "actions": sorted(TERMINAL_ACTIONS),
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(minutes=10)).timestamp()),
    }
    payload[claim] = value
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    codec = TerminalCapabilityCodec(secret=SECRET, algorithm="HS256", now=lambda: NOW)
    with pytest.raises(TerminalCapabilityError, match="invalid terminal capability"):
        codec.verify(
            token,
            expected_user_uuid=USER_UUID,
            expected_device_id="box-01",
            expected_game_id=GAME_ID,
            expected_reservation_id=RESERVATION_ID,
            required_action="settle",
        )


def test_codec_rejects_expired_or_excess_action_tokens_without_echoing_token():
    payload = {
        "aud": "xiangqi-ranked-terminal",
        "type": "terminal",
        "user_uuid": USER_UUID,
        "device_id": "box-01",
        "game_id": GAME_ID,
        "reservation_id": RESERVATION_ID,
        "jti": "secret-jti",
        "actions": sorted((*TERMINAL_ACTIONS, "profile:read")),
        "iat": int((NOW - timedelta(hours=2)).timestamp()),
        "exp": int((NOW - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    codec = TerminalCapabilityCodec(secret=SECRET, algorithm="HS256", now=lambda: NOW)
    with pytest.raises(TerminalCapabilityError) as exc_info:
        codec.verify(token, required_action="profile:read")
    assert token not in str(exc_info.value)
    assert "secret-jti" not in str(exc_info.value)


def test_store_rejects_revoked_jti_and_rotate_is_atomic_and_reserved_only(capability_store):
    store, sessions, clock = capability_store
    old_token = store.issue(
        user_uuid=USER_UUID,
        device_id="box-01",
        game_id=GAME_ID,
        reservation_id=RESERVATION_ID,
        now=NOW,
    )
    old_claims = store.verify(
        old_token,
        expected_user_uuid=USER_UUID,
        expected_device_id="box-01",
        expected_game_id=GAME_ID,
        expected_reservation_id=RESERVATION_ID,
        required_action="receipt",
    )
    assert old_claims.jti == "jti-initial"

    store.codec.jti_factory = lambda: "jti-rotated"
    clock["now"] = NOW + timedelta(minutes=1)
    new_token = store.rotate(
        user_uuid=USER_UUID,
        reservation_id=RESERVATION_ID,
        game_id=GAME_ID,
        now=NOW + timedelta(minutes=1),
    )
    with pytest.raises(TerminalCapabilityError, match="invalid terminal capability"):
        store.verify(old_token, required_action="receipt")
    assert store.verify(new_token, required_action="heartbeat").jti == "jti-rotated"
    with sessions() as session:
        old_row = session.get(models_db.XiangqiRankedCapabilityJti, "jti-initial")
        assert old_row.revoked_at is not None
        assert session.get(models_db.XiangqiRankedCapabilityJti, "jti-rotated").revoked_at is None
        reservation = session.get(models_db.XiangqiRankedReservation, RESERVATION_ID)
        reservation.status = "resigned"
        reservation.terminal_at = NOW + timedelta(minutes=2)
        session.commit()
    with pytest.raises(TerminalCapabilityError, match="invalid terminal capability"):
        store.rotate(
            user_uuid=USER_UUID,
            reservation_id=RESERVATION_ID,
            game_id=GAME_ID,
            now=NOW + timedelta(minutes=3),
        )
