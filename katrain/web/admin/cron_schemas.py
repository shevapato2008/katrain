"""Read-only cron API response shapes shared with the admin UI contract."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


HealthState = Literal["offline", "disabled", "pending", "stuck", "running", "failed", "errors", "overdue", "ok"]
RunStatus = Literal["running", "success", "errors", "failed"]


class CronHealthOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: HealthState
    reason: str


class CronLoopStatsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_flight: int = Field(ge=0)
    capacity: int = Field(ge=0)
    errors_total: int = Field(ge=0)
    last_error_at: AwareDatetime | None


class CronJobOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["interval", "loop"]
    interval_seconds: int | None
    enabled: bool
    health: CronHealthOut
    process_started_at: AwareDatetime | None
    heartbeat_at: AwareDatetime | None
    last_started_at: AwareDatetime | None
    last_finished_at: AwareDatetime | None
    last_success_at: AwareDatetime | None
    last_status: RunStatus | None
    last_duration_ms: int | None
    last_error: str | None
    consecutive_failures: int = Field(ge=0)
    loop_iteration_at: AwareDatetime | None
    loop_stats: CronLoopStatsOut | None


class CronJobsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: AwareDatetime
    jobs: list[CronJobOut]


class CronRunOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    status: RunStatus
    duration_ms: int | None
    error_count: int = Field(ge=0)
    error: str | None


class CronRunsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[CronRunOut]
    next_before_id: int | None


class CronQueueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by_status: dict[str, int]
    oldest_pending_at: AwareDatetime | None


class CronQueuesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: AwareDatetime
    live_analysis: CronQueueOut
    report_tasks: CronQueueOut
