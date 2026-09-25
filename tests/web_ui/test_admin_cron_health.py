from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from katrain.web.admin.cron_health import as_utc, derive_health


NOW = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)


def ago(seconds):
    return NOW - timedelta(seconds=seconds)


def row(**overrides):
    fields = dict(
        kind="interval",
        interval_seconds=60,
        enabled=True,
        heartbeat_at=ago(10),
        last_started_at=ago(20),
        last_status="success",
        consecutive_failures=0,
        loop_iteration_at=None,
        loop_stats=None,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def loop(**overrides):
    return row(**dict(kind="loop", interval_seconds=None, last_status="running", loop_iteration_at=ago(5)) | overrides)


@pytest.mark.parametrize(
    ("expected", "job"),
    [
        ("offline", row(heartbeat_at=ago(121))),
        ("offline", row(heartbeat_at=None)),
        ("disabled", row(enabled=False)),
        ("pending", row(last_started_at=None, last_status=None)),
        ("stuck", row(last_status="running", last_started_at=ago(601))),
        ("running", row(last_status="running", last_started_at=ago(30))),
        ("failed", row(last_status="failed", consecutive_failures=2)),
        ("errors", row(last_status="errors")),
        ("overdue", row(last_started_at=ago(181))),
        ("ok", row(last_started_at=ago(179))),
        ("pending", loop(loop_iteration_at=None)),
        ("stuck", loop(loop_iteration_at=ago(301))),
        ("failed", loop(last_status="failed")),
        ("errors", loop(loop_stats={"last_error_at": ago(300).isoformat()})),
        ("ok", loop(loop_stats={"last_error_at": ago(601).isoformat()})),
    ],
)
def test_nine_health_states(expected, job):
    result = derive_health(job, NOW)
    assert result.state == expected
    assert result.reason


@pytest.mark.parametrize(
    ("job", "expected"),
    [
        (row(heartbeat_at=ago(121), enabled=False, last_status="failed"), "offline"),
        (row(enabled=False, last_started_at=None), "disabled"),
        (row(last_started_at=None, last_status="failed"), "pending"),
        (row(last_status="running", last_started_at=ago(601)), "stuck"),
        (row(last_status="failed", last_started_at=ago(181)), "failed"),
        (row(last_status="errors", last_started_at=ago(181)), "errors"),
        (loop(last_status="failed", loop_iteration_at=ago(301)), "stuck"),
        (loop(last_status="failed", loop_stats={"last_error_at": ago(1).isoformat()}), "failed"),
    ],
)
def test_precedence(job, expected):
    assert derive_health(job, NOW).state == expected


@pytest.mark.parametrize(
    ("job", "expected"),
    [
        (row(heartbeat_at=ago(120)), "ok"),
        (row(heartbeat_at=ago(121)), "offline"),
        (row(last_status="running", last_started_at=ago(600)), "running"),
        (row(last_status="running", last_started_at=ago(601)), "stuck"),
        (row(interval_seconds=300, last_status="running", last_started_at=ago(900)), "running"),
        (row(interval_seconds=300, last_status="running", last_started_at=ago(901)), "stuck"),
        (row(last_started_at=ago(180)), "ok"),
        (row(last_started_at=ago(181)), "overdue"),
        (loop(loop_iteration_at=ago(300)), "ok"),
        (loop(loop_iteration_at=ago(301)), "stuck"),
        (loop(loop_stats={"last_error_at": ago(600).isoformat()}), "errors"),
        (loop(loop_stats={"last_error_at": ago(601).isoformat()}), "ok"),
    ],
)
def test_strict_time_boundaries(job, expected):
    assert derive_health(job, NOW).state == expected


def test_sqlite_naive_timestamps_and_offset_are_utc_normalized():
    assert as_utc(None) is None
    assert as_utc(ago(10).replace(tzinfo=None)) == ago(10)
    assert as_utc(ago(10).astimezone(timezone(timedelta(hours=8)))) == ago(10)
    job = row(heartbeat_at=ago(10).replace(tzinfo=None), last_started_at=ago(20).replace(tzinfo=None))
    assert derive_health(job, NOW).state == "ok"


def test_loop_recent_error_accepts_naive_iso_and_invalid_value():
    assert (
        derive_health(loop(loop_stats={"last_error_at": ago(30).replace(tzinfo=None).isoformat()}), NOW).state
        == "errors"
    )
    assert derive_health(loop(loop_stats={"last_error_at": "invalid"}), NOW).state == "ok"
