"""Wire contract for the dedicated admin cron read API."""

from datetime import datetime, timezone

from katrain.web.admin.cron_schemas import CronJobsResponse, CronQueuesResponse, CronRunsResponse


def test_cron_response_shapes_emit_timezone_aware_iso_times():
    now = datetime(2026, 9, 24, 8, 32, 8, tzinfo=timezone.utc)
    jobs = CronJobsResponse.model_validate(
        {
            "observed_at": now,
            "jobs": [
                {
                    "name": "poll_moves",
                    "kind": "interval",
                    "interval_seconds": 3,
                    "enabled": True,
                    "health": {"state": "ok", "reason": "recent heartbeat"},
                    "process_started_at": now,
                    "heartbeat_at": now,
                    "last_started_at": now,
                    "last_finished_at": now,
                    "last_success_at": now,
                    "last_status": "success",
                    "last_duration_ms": 480,
                    "last_error": None,
                    "consecutive_failures": 0,
                    "loop_iteration_at": None,
                    "loop_stats": None,
                }
            ],
        }
    ).model_dump(mode="json")
    assert jobs["observed_at"].endswith("Z")
    assert jobs["jobs"][0]["heartbeat_at"].endswith("Z")
    assert jobs["jobs"][0]["health"] == {"state": "ok", "reason": "recent heartbeat"}

    runs = CronRunsResponse.model_validate(
        {
            "runs": [
                {
                    "id": 5,
                    "started_at": now,
                    "finished_at": now,
                    "status": "errors",
                    "duration_ms": 900,
                    "error_count": 2,
                    "error": "first ERROR",
                }
            ],
            "next_before_id": 5,
        }
    ).model_dump(mode="json")
    assert runs["runs"][0]["error_count"] == 2
    assert runs["next_before_id"] == 5

    queues = CronQueuesResponse.model_validate(
        {
            "observed_at": now,
            "live_analysis": {"by_status": {"pending": 3}, "oldest_pending_at": now},
            "report_tasks": {"by_status": {"pending": 0}, "oldest_pending_at": None},
        }
    ).model_dump(mode="json")
    assert queues["live_analysis"]["by_status"]["pending"] == 3
    assert queues["report_tasks"]["oldest_pending_at"] is None
