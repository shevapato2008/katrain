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
    WEIQI_ORG = "weiqi_org"


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
