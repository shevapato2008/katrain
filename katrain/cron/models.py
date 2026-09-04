"""Independent DB model definitions for katrain-cron.

These map to the SAME PostgreSQL tables as katrain-web's models but are
maintained independently — zero imports from katrain.web.
"""

import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from katrain.cron.db import Base


# ──────────────────────────── Enums ────────────────────────────


class MatchSourceEnum(str, enum.Enum):
    XINGZHEN = "xingzhen"
    YIKE = "yike"
    PANDANET = "pandanet"


class MatchStatusEnum(str, enum.Enum):
    LIVE = "live"
    FINISHED = "finished"


class AnalysisStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TranslationSourceEnum(str, enum.Enum):
    STATIC = "static"
    MANUAL = "manual"
    LLM = "llm"
    SEARCH_LLM = "search+llm"
    WIKIPEDIA = "wikipedia"
    FUZZY_MATCH = "fuzzy_match"


# ──────────────────────────── Priority constants ────────────────────────────

PRIORITY_LIVE_NEW = 1000
PRIORITY_USER_VIEW = 500
PRIORITY_LIVE_BACKFILL = 100
PRIORITY_FINISHED = 10
PRIORITY_HISTORICAL = 1


# ──────────────────────────── Models ────────────────────────────


class LiveMatchDB(Base):
    """Live/historical matches from external sources."""

    __tablename__ = "live_matches"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(64), unique=True, nullable=False, index=True)
    source = Column(String(20), nullable=False)
    source_id = Column(String(64), nullable=False)
    tournament = Column(String(256), nullable=False)
    round_name = Column(String(128), nullable=True)
    match_date = Column(DateTime(timezone=True), nullable=True)
    player_black = Column(String(128), nullable=False)
    player_white = Column(String(128), nullable=False)
    black_rank = Column(String(16), nullable=True)
    white_rank = Column(String(16), nullable=True)
    status = Column(String(16), nullable=False, default="live")
    result = Column(String(64), nullable=True)
    move_count = Column(Integer, default=0)
    sgf_content = Column(Text, nullable=True)
    moves = Column(JSON, nullable=True)
    current_winrate = Column(Float, default=0.5)
    current_score = Column(Float, default=0.0)
    katago_winrate = Column(Float, nullable=True)
    katago_score = Column(Float, nullable=True)
    board_size = Column(Integer, default=19)
    komi = Column(Float, default=7.5)
    rules = Column(String(32), default="chinese")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiveAnalysisDB(Base):
    """Move-by-move analysis data."""

    __tablename__ = "live_analysis"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(64), ForeignKey("live_matches.match_id"), nullable=False, index=True)
    move_number = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    priority = Column(Integer, default=10)

    # Analysis results (populated when status=success)
    winrate = Column(Float, nullable=True)
    score_lead = Column(Float, nullable=True)
    top_moves = Column(JSON, nullable=True)
    ownership = Column(JSON, nullable=True)

    # Move classification
    actual_move = Column(String(8), nullable=True)
    actual_player = Column(String(1), nullable=True)
    delta_score = Column(Float, nullable=True)
    delta_winrate = Column(Float, nullable=True)
    is_brilliant = Column(Boolean, default=False)
    is_mistake = Column(Boolean, default=False)
    is_questionable = Column(Boolean, default=False)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    analyzed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("match_id", "move_number", name="uq_match_move"),
        Index("idx_analysis_pending_priority", "priority", "created_at", postgresql_where=text("status = 'pending'")),
    )


class PlayerTranslationDB(Base):
    """Player name translations."""

    __tablename__ = "player_translations"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(128), unique=True, nullable=False, index=True)
    country = Column(String(4), nullable=True)
    en = Column(String(128), nullable=True)
    cn = Column(String(128), nullable=True)
    tw = Column(String(128), nullable=True)
    jp = Column(String(128), nullable=True)
    ko = Column(String(128), nullable=True)
    aliases = Column(JSON, nullable=True)
    source = Column(String(16), nullable=False, default="manual")
    llm_model = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TournamentTranslationDB(Base):
    """Tournament name translations."""

    __tablename__ = "tournament_translations"

    id = Column(Integer, primary_key=True, index=True)
    original = Column(String(256), unique=True, nullable=False, index=True)
    en = Column(String(256), nullable=True)
    cn = Column(String(256), nullable=True)
    tw = Column(String(256), nullable=True)
    jp = Column(String(256), nullable=True)
    ko = Column(String(256), nullable=True)
    source = Column(String(16), nullable=False, default="manual")
    llm_model = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ──────────────────────────── Report models ────────────────────────────


class ReportTaskDB(Base):
    """Persistent report-generation task for a user-owned game.

    Maps to the same table as katrain.web.core.models_db.ReportTask.
    """

    __tablename__ = "report_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_game_id = Column(String(32), nullable=False, index=True)
    report_type = Column(String(20), default="normal")
    requested_visits = Column(Integer, default=500)
    status = Column(String(20), default="pending")  # pending / running / completed / failed
    total_moves = Column(Integer, default=0)
    analyzed_moves = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    # 授权那一刻棋谱内容的指纹，认领时比对(见 report_analyze.py)。cron 侧要写
    # 这一列 —— 只加在 web 模型会让这里永远读到 None、校验形同虚设(见
    # katrain/web/core/models_db.py:ReportTask 同名列的注释)。
    sgf_hash = Column(String(64), nullable=True)
    # 非 NULL = 这个任务不该被 web 侧结算器收费(如本文件 requeue_reports.py 重排)。
    # cron 侧要写这一列 —— 只加在 web 模型会让 requeue_reports.py 的赋值在 cron
    # 容器里抛 AttributeError(见 katrain/web/core/models_db.py:ReportTask 同名列的注释)。
    billing_exempt_reason = Column(String(32), nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_report_tasks_status_created", "status", "created_at"),
        {"extend_existing": True},
    )


class ReportTaskMoveDB(Base):
    """Stored move-by-move analysis snapshot for a report task.

    Maps to the same table as katrain.web.core.models_db.ReportTaskMove.
    """

    __tablename__ = "report_task_moves"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    move_number = Column(Integer, nullable=False)
    status = Column(String(16), default="success")
    winrate = Column(Float, nullable=True)
    score_lead = Column(Float, nullable=True)
    visits = Column(Integer, nullable=True)
    top_moves = Column(JSON, nullable=True)
    ownership = Column(JSON, nullable=True)
    actual_move = Column(String(8), nullable=True)
    actual_player = Column(String(1), nullable=True)
    delta_score = Column(Float, nullable=True)
    delta_winrate = Column(Float, nullable=True)
    # 着手评价（阈值真源：katrain/core/move_grade.yaml）。
    # grade 为 NULL 或 'unrated' 表示这手没有被评级（上一手没分析 / visits 不够），
    # 前端必须把它当作「不知道」，不能当作「没问题」。
    grade = Column(String(16), nullable=True)
    points_lost = Column(Float, nullable=True)          # 对落子方而言亏的目数，>=0
    points_lost_source = Column(String(12), nullable=True)  # in_search | two_search | none
    is_top_move = Column(Boolean, nullable=True)
    top_prior = Column(Float, nullable=True)            # 引擎首选的 policy 先验
    brilliance = Column(Integer, nullable=True)         # 妙度 1-5，仅 grade='brilliant' 时有值
    # 注意：上面的 `visits` 列存的是**首选的 childVisits**，不是根搜索量
    # （report_analyze 取的是 move_infos[:1] 的 visits）。评级的「搜够了没有」闸
    # 必须看根搜索量，否则会静默压制妙手，所以单独存一列。
    root_visits = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("task_id", "move_number", name="uq_report_task_move"),
        {"extend_existing": True},
    )


class UserGameDB(Base):
    """Minimal read-only view of user_games for report analyzer.

    Only the fields needed to retrieve SGF content for analysis.
    """

    __tablename__ = "user_games"

    id = Column(String(32), primary_key=True)
    sgf_content = Column(Text, nullable=True)

    __table_args__ = ({"extend_existing": True},)


class UpcomingMatchDB(Base):
    """Upcoming/scheduled matches from various sources."""

    __tablename__ = "live_upcoming"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(128), unique=True, nullable=False, index=True)
    tournament = Column(String(256), nullable=False)
    round_name = Column(String(128), nullable=True)
    scheduled_time = Column(DateTime(timezone=True), nullable=False, index=True)
    player_black = Column(String(128), nullable=True)
    player_white = Column(String(128), nullable=True)
    source = Column(String(32), nullable=False)  # foxwq, nihonkiin, etc.
    source_url = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
