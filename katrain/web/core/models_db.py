from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    ForeignKey,
    Text,
    Enum,
    CheckConstraint,
    Boolean,
    UniqueConstraint,
    Index,
    JSON,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from katrain.web.core.db import Base
import enum
import uuid as uuid_module


# ⚠️ **`none_as_null=True` 不是风格问题,是承重的。**
#
#     JSON()                     Python None -> JSON 字面量 'null'   ← 列上的 NOT NULL
#                                                                     和 `IS NOT NULL`
#                                                                     全都判它**有值**
#     JSON(none_as_null=True)    Python None -> SQL NULL
#
# 关系到 `ck_ai_ladder_ledger_decision` 里那句 `opponent_config_snapshot IS NOT NULL`:
# 没有这个参数,一个 Python `None` 会以 `'null'` 落库,那句 CHECK 照样为真 —— 闸开着却
# 看不出来。今天围棋走不到那一格(真正的判据是 `counted = reason is None` 加
# `AiLadderOpponentSnapshot.__post_init__`,库层那几句伴随子句在这个形状下从不被求值),
# 所以这条是**潜伏的、不是活的**;但三家的共享账本 2026-08-13 已经统一带上它
# (`ranked_api/envelope/models_db.py:66`),围棋是最后一个没带的。
#
# 只作用于绑定参数,**不改 DDL** —— 不需要迁移。
LadderJSON = JSON(none_as_null=True)


class MatchSourceEnum(str, enum.Enum):
    """Data source for live matches."""

    XINGZHEN = "xingzhen"
    YIKE = "yike"
    PANDANET = "pandanet"


class MatchStatusEnum(str, enum.Enum):
    """Status of a live match."""

    LIVE = "live"
    FINISHED = "finished"


class AnalysisStatusEnum(str, enum.Enum):
    """Status of analysis task."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        String, unique=True, index=True, default=lambda: uuid_module.uuid4().hex
    )  # Unique UUID assigned at registration
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    rank = Column(String, default="20k")
    net_wins = Column(Integer, default=0)
    elo_points = Column(Integer, default=0)
    credits = Column(
        Integer, default=10000, nullable=False
    )  # integer credit balance (single pool); server-authoritative
    is_admin = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    followers = relationship("Relationship", foreign_keys="[Relationship.following_id]", back_populates="following")
    following = relationship("Relationship", foreign_keys="[Relationship.follower_id]", back_populates="follower")
    tsumego_progress = relationship("UserTsumegoProgress", back_populates="user")
    ai_ladder_profile = relationship("AiLadderProfile", back_populates="user", uselist=False)


class Relationship(Base):
    __tablename__ = "relationships"

    follower_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    following_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following = relationship("User", foreign_keys=[following_id], back_populates="followers")


class RatingHistory(Base):
    __tablename__ = "rating_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    old_rank = Column(String)
    new_rank = Column(String)
    elo_change = Column(Integer, default=0)
    game_id = Column(String(32), ForeignKey("user_games.id"), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    game = relationship("UserGame")
    user = relationship("User")


class AiLadderProfile(Base):
    """Authoritative ranked-AI state, independent from the legacy human ladder."""

    __tablename__ = "ai_ladder_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    ai_ladder_rung = Column(Integer, nullable=True)
    placement_lo = Column(Integer, nullable=False)
    placement_hi = Column(Integer, nullable=False)
    placement_completed = Column(Integer, nullable=False, default=0)
    net_score = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="ai_ladder_profile")

    __table_args__ = (
        CheckConstraint("ai_ladder_rung IS NULL OR ai_ladder_rung BETWEEN 1 AND 41", name="ck_ai_ladder_rung"),
        CheckConstraint("placement_lo BETWEEN 1 AND 41", name="ck_ai_ladder_placement_lo"),
        CheckConstraint("placement_hi BETWEEN 1 AND 41", name="ck_ai_ladder_placement_hi"),
        CheckConstraint("placement_lo <= placement_hi", name="ck_ai_ladder_placement_window"),
        CheckConstraint("placement_completed BETWEEN 0 AND 5", name="ck_ai_ladder_placement_completed"),
        CheckConstraint("net_score BETWEEN -2 AND 2", name="ck_ai_ladder_net_score"),
    )


class AiLadderPendingGame(Base):
    """Durable frozen start/settlement handoff for one active ranked game per user."""

    __tablename__ = "ai_ladder_pending_games"

    game_id = Column(String(32), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, unique=True)
    # Opaque cloud reservation credential retained only for internal recovery.
    # Nullable keeps pre-reservation local rows readable after migration.
    reservation_key = Column(String(128), nullable=True)
    user_color = Column(String(1), nullable=False)
    game_type = Column(String(32), nullable=False)
    opponent_rung = Column(Integer, nullable=False)
    opponent_rank_name = Column(String(64), nullable=False)
    opponent_config_snapshot = Column(LadderJSON, nullable=False)
    opponent_certification_status = Column(String(16), nullable=False)
    opponent_availability = Column(String(16), nullable=False)
    opponent_route = Column(String(16), nullable=False)
    ai_subtype = Column(String(32), nullable=False)
    execution_identity = Column(String(64), nullable=False)
    game_saved = Column(Boolean, nullable=False, default=False)
    saved_result = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_ai_ladder_pending_user"),
        CheckConstraint("user_color IN ('B', 'W')", name="ck_ai_ladder_pending_user_color"),
        CheckConstraint("game_type = 'ai_ladder_ranked'", name="ck_ai_ladder_pending_game_type"),
        CheckConstraint("opponent_rung BETWEEN 1 AND 41", name="ck_ai_ladder_pending_rung"),
        CheckConstraint("opponent_route IN ('local', 'server')", name="ck_ai_ladder_pending_route"),
        CheckConstraint(
            "(game_saved = FALSE AND saved_result IS NULL) OR (game_saved = TRUE AND saved_result IS NOT NULL)",
            name="ck_ai_ladder_pending_saved_state",
        ),
    )


class AiLadderActiveGame(Base):
    """Cloud-owned reservation for the account's one in-flight ranked AI game."""

    __tablename__ = "ai_ladder_active_games"

    game_id = Column(String(32), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    origin_device_id = Column(String(64), nullable=False)
    origin_session_id = Column(String(64), nullable=True)
    state = Column(String(24), nullable=False, default="reserved")
    version = Column(Integer, nullable=False, default=0)
    # Liveness of the box that is playing this game, so a second device can tell "still being
    # played over there" from "that box is gone". Deliberately separate from `updated_at`:
    # nothing writes this row between activation and settlement, so `updated_at` measures how
    # long the game has been running, and a long game is not a dead one.
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    # Counts heartbeats, not devices. A client that has only ever activated sits at 0; one that
    # has proven it keeps a timer running climbs. The takeover rule reads this to tell those two
    # populations apart -- see AI_LADDER_MIN_HEARTBEAT_GENERATION_FOR_TAKEOVER.
    heartbeat_generation = Column(Integer, nullable=False, default=0)
    # When this row entered `pending_settlement`, i.e. when the origin box said "the game is
    # over, I am delivering the result". Its own column for the same reason as
    # `last_heartbeat_at`: `updated_at` is reset by any future write to this row, so a clock
    # kept there would silently restart the moment anything else touches the reservation.
    pending_settlement_since = Column(DateTime(timezone=True), nullable=True)
    reservation_key_hash = Column(String(64), nullable=False)
    user_color = Column(String(1), nullable=False)
    game_type = Column(String(32), nullable=False, default="ai_ladder_ranked")
    opponent_rung = Column(Integer, nullable=False)
    opponent_rank_name = Column(String(64), nullable=False)
    opponent_config_snapshot = Column(LadderJSON, nullable=False)
    opponent_certification_status = Column(String(16), nullable=False)
    opponent_availability = Column(String(16), nullable=False)
    opponent_route = Column(String(16), nullable=False)
    ai_subtype = Column(String(32), nullable=False)
    execution_identity = Column(String(64), nullable=False)
    rules_snapshot = Column(LadderJSON, nullable=False)
    time_control_snapshot = Column(LadderJSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_ai_ladder_active_user"),
        CheckConstraint(
            "state IN ('reserved', 'active', 'pending_settlement')",
            name="ck_ai_ladder_active_state",
        ),
        CheckConstraint("version >= 0", name="ck_ai_ladder_active_version"),
        CheckConstraint("heartbeat_generation >= 0", name="ck_ai_ladder_active_heartbeat_generation"),
        CheckConstraint("user_color IN ('B', 'W')", name="ck_ai_ladder_active_user_color"),
        CheckConstraint("game_type = 'ai_ladder_ranked'", name="ck_ai_ladder_active_game_type"),
        CheckConstraint("opponent_rung BETWEEN 1 AND 41", name="ck_ai_ladder_active_rung"),
        CheckConstraint("opponent_route IN ('local', 'server')", name="ck_ai_ladder_active_route"),
    )


class AiLadderGameLedger(Base):
    """Append-only, globally idempotent decision for every settlement attempt."""

    __tablename__ = "ai_ladder_game_ledger"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_color = Column(String(1), nullable=False)
    result = Column(String(16), nullable=False)
    game_type = Column(String(32), nullable=False)
    opponent_rung = Column(Integer, nullable=True)
    opponent_rank_name = Column(String(64), nullable=True)
    opponent_config_snapshot = Column(LadderJSON, nullable=True)
    opponent_certification_status = Column(String(16), nullable=True)
    opponent_availability = Column(String(16), nullable=True)
    opponent_route = Column(String(16), nullable=True)
    counted = Column(Boolean, nullable=False)
    reason = Column(String(32), nullable=True)
    origin_device_id = Column(String(64), nullable=True)
    deciding_device_id = Column(String(64), nullable=True)
    terminal_source = Column(String(32), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # account_subject frozen at settlement: the 32-hex users.uuid as it was WHEN THIS GAME SETTLED.
    # Deliberately NOT a ForeignKey and never joined on -- user_id above is the runtime operational
    # key; this is an immutable historical fact, written once and never updated. An audit row is
    # allowed to disagree with the present, because it records the past. Test: take the whole
    # database away and keep only this row -- can you still tell whose game it was?
    # Nullable for rows written before this column existed. See
    # superpowers/tracks/golaxy-ai-ladder-parity/identity-p3-preconditions.md §E.
    account_subject = Column(String(32), nullable=True)

    user = relationship("User", backref="ai_ladder_game_ledger")

    __table_args__ = (
        CheckConstraint("user_color IN ('B', 'W')", name="ck_ai_ladder_ledger_user_color"),
        # 与三家共享账本的 `ck_ranked_ledgers_account_subject_len` 同源
        # (`ranked_api/envelope/models_db.py:544`,那边是全局 `BETWEEN 1 AND 32`
        # 再加象棋作用域的 `= 32`)。围棋这一列可空 —— 本列诞生前写下的行是 NULL,
        # 不能追认;所以多一支 `IS NULL`,其余与三家逐字一致。
        #
        # ⚠️ 这条守的是**账本这一侧**。铸造侧 `users.uuid` 至今仍是无长度的 `String`,
        # 32 位只由一个 Python default lambda 保证 —— 那个缺口由
        # `tests/web_ui/test_account_subject_contract.py` 的 `xfail(strict=True)` 钉着,
        # 属身份服务 Phase 3,冻结件 §6-3 明令 Phase 1 不动那一列。**别顺手一起改**:
        # 那条 xfail 一旦 XPASS 会让构建红,而它红的时候应该是有人**有意**去修铸造侧。
        CheckConstraint(
            "account_subject IS NULL OR length(account_subject) BETWEEN 1 AND 32",
            name="ck_ai_ladder_ledger_account_subject_len",
        ),
        CheckConstraint(
            "opponent_rung IS NULL OR opponent_rung BETWEEN 1 AND 41",
            name="ck_ai_ladder_ledger_opponent_rung",
        ),
        CheckConstraint(
            "opponent_route IS NULL OR opponent_route IN ('local', 'server')",
            name="ck_ai_ladder_ledger_route",
        ),
        CheckConstraint(
            "(counted = FALSE AND reason IS NOT NULL) OR "
            "(counted = TRUE AND reason IS NULL AND opponent_rung IS NOT NULL "
            "AND opponent_rank_name IS NOT NULL AND opponent_config_snapshot IS NOT NULL "
            "AND opponent_certification_status = 'certified' AND opponent_availability = 'available' "
            "AND opponent_route IS NOT NULL AND result IN ('win', 'loss') "
            "AND game_type = 'ai_ladder_ranked')",
            name="ck_ai_ladder_ledger_decision",
        ),
        CheckConstraint(
            "(terminal_source IS NULL AND origin_device_id IS NULL "
            "AND deciding_device_id IS NULL AND decided_at IS NULL) OR "
            "(terminal_source IS NOT NULL "
            "AND terminal_source IN ('played_result', 'remote_resign', 'recovery') "
            "AND origin_device_id IS NOT NULL AND deciding_device_id IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_ai_ladder_ledger_terminal_audit",
        ),
    )


# 象棋升降级的四张表(xiangqi_rating_profiles / xiangqi_ranked_reservations /
# xiangqi_ranked_ledger / xiangqi_ranked_capability_jtis)已搬去
# lobby-platform `ranked_api/xiangqi/models_db.py`。已部署库里的旧表原样保留:
# 没有 ORM 模型 = 进不了 `auth.py` 的 drift 重建名单,不会被 drop。


class LiveMatchDB(Base):
    """Database model for live/historical matches from external sources."""

    __tablename__ = "live_matches"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(64), unique=True, nullable=False, index=True)  # Format: {source}_{source_id}
    source = Column(String(20), nullable=False)  # xingzhen / yike
    source_id = Column(String(64), nullable=False)
    tournament = Column(String(256), nullable=False)
    round_name = Column(String(128), nullable=True)
    match_date = Column(DateTime(timezone=True), nullable=True)
    player_black = Column(String(128), nullable=False)
    player_white = Column(String(128), nullable=False)
    black_rank = Column(String(16), nullable=True)
    white_rank = Column(String(16), nullable=True)
    status = Column(String(16), nullable=False, default="live")  # live / finished
    result = Column(String(64), nullable=True)
    move_count = Column(Integer, default=0)
    sgf_content = Column(Text, nullable=True)
    moves = Column(JSON, nullable=True)  # ["Q16", "D4", ...]
    current_winrate = Column(Float, default=0.5)  # From XingZhen API
    current_score = Column(Float, default=0.0)  # From XingZhen API
    katago_winrate = Column(Float, nullable=True)  # From local KataGo (latest move)
    katago_score = Column(Float, nullable=True)  # From local KataGo (latest move)
    # Game rules and komi
    board_size = Column(Integer, default=19)  # Board size (9, 13, 19)
    komi = Column(Float, default=7.5)  # Komi (compensation points for white)
    rules = Column(String(32), default="chinese")  # Rules: chinese, japanese, korean, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship to analysis records
    analysis_records = relationship("LiveAnalysisDB", back_populates="match", cascade="all, delete-orphan")


class LiveAnalysisDB(Base):
    """Database model for move-by-move analysis data."""

    __tablename__ = "live_analysis"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(64), ForeignKey("live_matches.match_id"), nullable=False, index=True)
    move_number = Column(Integer, nullable=False)  # 0 = empty board, 1 = after first move
    status = Column(String(16), nullable=False, default="pending")  # pending / running / success / failed
    priority = Column(Integer, default=10)  # Higher = more urgent (live matches get higher priority)

    # Analysis results (populated when status=success)
    winrate = Column(Float, nullable=True)  # Black's winrate 0-1
    score_lead = Column(Float, nullable=True)  # Black's lead in points
    top_moves = Column(JSON, nullable=True)  # [{move, visits, winrate, score_lead, prior, pv}, ...]
    ownership = Column(JSON, nullable=True)  # 2D array of ownership values (-1 to 1, positive=Black)

    # Move classification
    actual_move = Column(String(8), nullable=True)  # The move that was played
    actual_player = Column(String(1), nullable=True)  # 'B' or 'W'
    delta_score = Column(Float, nullable=True)  # Score change from previous position
    delta_winrate = Column(Float, nullable=True)  # Winrate change from previous position
    is_brilliant = Column(Boolean, default=False)
    is_mistake = Column(Boolean, default=False)
    is_questionable = Column(Boolean, default=False)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    analyzed_at = Column(DateTime(timezone=True), nullable=True)

    # Unique constraint for (match_id, move_number)
    __table_args__ = (UniqueConstraint("match_id", "move_number", name="uq_match_move"),)

    # Relationship to match
    match = relationship("LiveMatchDB", back_populates="analysis_records")


class LiveCommentDB(Base):
    """Database model for comments on live matches."""

    __tablename__ = "live_comments"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(64), ForeignKey("live_matches.match_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    match = relationship("LiveMatchDB", backref="comments")
    user = relationship("User", backref="live_comments")


class TranslationSourceEnum(str, enum.Enum):
    """Source of translation data."""

    STATIC = "static"  # From JSON files
    MANUAL = "manual"  # Manually entered by user
    LLM = "llm"  # Generated by LLM
    WIKIPEDIA = "wikipedia"  # From Wikipedia lookup


class PlayerTranslationDB(Base):
    """Database model for player name translations."""

    __tablename__ = "player_translations"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(128), unique=True, nullable=False, index=True)  # Original name (e.g., "王立诚")
    country = Column(String(4), nullable=True)  # CN, JP, KR, TW
    en = Column(String(128), nullable=True)  # English translation
    cn = Column(String(128), nullable=True)  # Simplified Chinese
    tw = Column(String(128), nullable=True)  # Traditional Chinese
    jp = Column(String(128), nullable=True)  # Japanese (kanji/katakana)
    ko = Column(String(128), nullable=True)  # Korean (hangul)
    aliases = Column(JSON, nullable=True)  # List of alternative names
    source = Column(String(16), nullable=False, default="manual")  # static/manual/llm/wikipedia
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TournamentTranslationDB(Base):
    """Database model for tournament name translations."""

    __tablename__ = "tournament_translations"

    id = Column(Integer, primary_key=True, index=True)
    original = Column(String(256), unique=True, nullable=False, index=True)  # Original tournament name
    en = Column(String(256), nullable=True)  # English translation
    cn = Column(String(256), nullable=True)  # Simplified Chinese
    tw = Column(String(256), nullable=True)  # Traditional Chinese
    jp = Column(String(256), nullable=True)  # Japanese
    ko = Column(String(256), nullable=True)  # Korean
    source = Column(String(16), nullable=False, default="manual")  # static/manual/llm/wikipedia
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SystemConfigDB(Base):
    """Database model for system configuration.

    Stores runtime-configurable settings. Sensitive values like API keys
    should still be stored in environment variables for security.
    """

    __tablename__ = "system_config"

    key = Column(String(64), primary_key=True, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============ Tsumego Models ============


class TsumegoProblem(Base):
    """Individual tsumego problem."""

    __tablename__ = "tsumego_problems"

    id = Column(String(32), primary_key=True)  # Problem number, e.g. "1014"
    level = Column(String(8), nullable=False, index=True)  # "3d", "4d"
    category = Column(String(32), nullable=False, index=True)  # "life-death", "tesuji"
    hint = Column(String(16), nullable=False)  # "黑先", "白先"
    board_size = Column(Integer, default=19)
    initial_black = Column(JSON)  # ["pa", "rd", ...]
    initial_white = Column(JSON)  # ["nc", "qf", ...]
    sgf_content = Column(Text)  # Full SGF for solving
    source = Column(String(256))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_tsumego_level_category", "level", "category"),)


class UserTsumegoProgress(Base):
    """User's progress on a specific problem."""

    __tablename__ = "user_tsumego_progress"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    problem_id = Column(String(32), ForeignKey("tsumego_problems.id"), primary_key=True)
    completed = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    first_completed_at = Column(DateTime(timezone=True))
    last_attempt_at = Column(DateTime(timezone=True))
    last_duration = Column(Integer)  # Seconds to complete last time

    user = relationship("User", back_populates="tsumego_progress")
    problem = relationship("TsumegoProblem")


# ============ Tutorial Models ============


class UserTutorialProgress(Base):
    # DEPRECATED in V2 — kept for data preservation. Will be replaced in Phase 3.
    """User's progress on a specific tutorial example."""
    __tablename__ = "user_tutorial_progress"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    example_id = Column(String(64), primary_key=True)
    topic_id = Column(String(64), nullable=False, index=True)
    last_step_id = Column(String(64), nullable=True)
    completed = Column(Boolean, default=False)
    last_played_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="tutorial_progress")


# ============ Tutorial V2 Models ============


class TutorialBook(Base):
    """A Go tutorial book imported from book.json."""

    __tablename__ = "tutorial_books"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(32), nullable=False, index=True)  # 入门/布局/中盘/官子
    subcategory = Column(String(64), nullable=False, default="棋书")
    title = Column(String(256), nullable=False)
    author = Column(String(128), nullable=True)
    translator = Column(String(128), nullable=True)
    slug = Column(String(128), nullable=False, unique=True, index=True)
    asset_dir = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    chapters = relationship(
        "TutorialChapter", back_populates="book", cascade="all, delete-orphan", order_by="TutorialChapter.order"
    )

    __table_args__ = (CheckConstraint("category IN ('入门', '布局', '中盘', '官子')", name="ck_book_category"),)


class TutorialChapter(Base):
    """A chapter within a tutorial book."""

    __tablename__ = "tutorial_chapters"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("tutorial_books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    order = Column(Integer, nullable=False)

    book = relationship("TutorialBook", back_populates="chapters")
    sections = relationship(
        "TutorialSection", back_populates="chapter", cascade="all, delete-orphan", order_by="TutorialSection.order"
    )

    __table_args__ = (UniqueConstraint("book_id", "order", name="uq_chapter_book_order"),)


class TutorialSection(Base):
    """A section within a chapter (= one Example in the UI)."""

    __tablename__ = "tutorial_sections"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("tutorial_chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    section_number = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    order = Column(Integer, nullable=False)

    chapter = relationship("TutorialChapter", back_populates="sections")
    figures = relationship(
        "TutorialFigure", back_populates="section", cascade="all, delete-orphan", order_by="TutorialFigure.order"
    )

    __table_args__ = (UniqueConstraint("chapter_id", "order", name="uq_section_chapter_order"),)


class TutorialFigure(Base):
    """A single board diagram (= one Variation in the UI). Core content unit."""

    __tablename__ = "tutorial_figures"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("tutorial_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    page = Column(Integer, nullable=False)
    figure_label = Column(String(32), nullable=False)
    book_text = Column(Text, nullable=True)
    page_context_text = Column(Text, nullable=True)
    bbox = Column(JSON, nullable=True)
    page_image_path = Column(String(512), nullable=True)
    board_payload = Column(JSON, nullable=True)
    recognition_debug = Column(JSON, nullable=True)
    narration = Column(Text, nullable=True)
    audio_asset = Column(String(512), nullable=True)
    video_asset = Column(String(512), nullable=True)
    video_duration_ms = Column(Integer, nullable=True)
    video_size_bytes = Column(Integer, nullable=True)
    order = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    section = relationship("TutorialSection", back_populates="figures")

    __table_args__ = (UniqueConstraint("section_id", "order", name="uq_figure_section_order"),)


class BoardPayloadHistory(Base):
    """Audit trail for board_payload changes (edits and verifications)."""

    __tablename__ = "board_payload_history"

    id = Column(Integer, primary_key=True, index=True)
    figure_id = Column(Integer, ForeignKey("tutorial_figures.id", ondelete="CASCADE"), nullable=False, index=True)
    board_payload = Column(JSON, nullable=False)
    changed_by = Column(String(128), default="anonymous")
    change_type = Column(String(16), nullable=False, default="edit")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    figure = relationship("TutorialFigure")


class TrainingSample(Base):
    """Individual patch sample for EfficientNet-B0 stone classifier training.

    Populated from human-verified figures via scripts/export_training_data.py.
    Each row = one CV-cropped intersection patch with ground-truth label.
    """

    __tablename__ = "training_samples"

    id = Column(Integer, primary_key=True, index=True)
    figure_id = Column(Integer, ForeignKey("tutorial_figures.id", ondelete="CASCADE"), nullable=False, index=True)
    patch_label = Column(String(4), nullable=False)  # "A", "B", "AA"
    local_col = Column(Integer, nullable=False)
    local_row = Column(Integer, nullable=False)
    global_col = Column(Integer, nullable=False)
    global_row = Column(Integer, nullable=False)
    patch_image_path = Column(String(512), nullable=False)  # relative to data/
    base_type = Column(String(16), nullable=False)  # black/white/empty
    move_number = Column(Integer, nullable=True)  # 1-99 or null
    shape = Column(String(16), nullable=True)  # triangle/square/circle or null
    letter = Column(String(4), nullable=True)  # A/B/C or null
    source = Column(String(16), nullable=False, server_default="human")
    book_slug = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    figure = relationship("TutorialFigure")


class KifuAlbum(Base):
    """Database model for tournament game records (大赛棋谱)."""

    __tablename__ = "kifu_albums"

    id = Column(Integer, primary_key=True, index=True)
    player_black = Column(String(512), nullable=False, index=True)
    player_white = Column(String(512), nullable=False, index=True)
    black_rank = Column(String(64), nullable=True)
    white_rank = Column(String(64), nullable=True)
    event = Column(String(256), nullable=True, index=True)
    result = Column(String(64), nullable=True)
    date_played = Column(String(32), nullable=True)  # Raw SGF date string for display ("1926", "1928-09-04,05")
    date_sort = Column(
        String(10), nullable=True, index=True
    )  # Normalized ISO prefix for sorting ("1926-00-00", "1928-09-04")
    place = Column(String(256), nullable=True)
    komi = Column(Float, nullable=True)
    handicap = Column(Integer, default=0)
    board_size = Column(Integer, default=19)
    rules = Column(String(32), nullable=True)
    round_name = Column(String(128), nullable=True)
    source = Column(String(256), nullable=True)
    move_count = Column(Integer, default=0)
    sgf_content = Column(Text, nullable=False)
    source_path = Column(String(512), unique=True, nullable=False, index=True)  # Prevents duplicate imports
    search_text = Column(Text, nullable=True)  # Lowercased concatenated searchable fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserGame(Base):
    """Personal game library: play records, imported SGFs, research positions."""

    __tablename__ = "user_games"

    id = Column(String(32), primary_key=True, default=lambda: uuid_module.uuid4().hex)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    sgf_content = Column(Text, nullable=True)
    player_black = Column(String(100), nullable=True)
    player_white = Column(String(100), nullable=True)
    black_rank = Column(String(16), nullable=True)
    white_rank = Column(String(16), nullable=True)
    result = Column(String(50), nullable=True)
    board_size = Column(Integer, default=19)
    rules = Column(String(64), default="chinese")
    komi = Column(Float, default=7.5)
    move_count = Column(Integer, default=0)
    source = Column(String(50), nullable=False)  # play_ai / play_human / import / research
    category = Column(String(50), default="game")  # game / position
    game_type = Column(String(50), nullable=True)  # free / rated / null
    origin_device_id = Column(String(64), nullable=True)
    sgf_hash = Column(String(64), nullable=True, index=True)
    event = Column(String(255), nullable=True)
    round_name = Column(String(100), nullable=True)
    game_date = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="user_games")
    analysis_records = relationship("UserGameAnalysis", back_populates="game", cascade="all, delete-orphan")
    report_tasks = relationship("ReportTask", back_populates="user_game", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_user_games_user_category", "user_id", "category"),
        Index("ix_user_games_user_source", "user_id", "source"),
        Index("ix_user_games_created", "created_at"),
    )


class UserGameAnalysis(Base):
    """Move-by-move analysis data for user games (research module)."""

    __tablename__ = "user_game_analysis"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String(32), ForeignKey("user_games.id"), nullable=False, index=True)
    move_number = Column(Integer, nullable=False)
    status = Column(String(16), default="pending")  # pending / running / success / failed
    priority = Column(Integer, default=10)
    winrate = Column(Float, nullable=True)
    score_lead = Column(Float, nullable=True)
    visits = Column(Integer, nullable=True)
    top_moves = Column(JSON, nullable=True)
    ownership = Column(JSON, nullable=True)
    move = Column(String(8), nullable=True)  # actual move played (e.g. "Q16")
    actual_player = Column(String(1), nullable=True)  # B / W
    delta_score = Column(Float, nullable=True)
    delta_winrate = Column(Float, nullable=True)
    is_brilliant = Column(Boolean, default=False)
    is_mistake = Column(Boolean, default=False)
    is_questionable = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    game = relationship("UserGame", back_populates="analysis_records")

    __table_args__ = (
        UniqueConstraint("game_id", "move_number", name="uq_user_game_analysis_move"),
        Index("ix_user_game_analysis_status", "status", "priority"),
    )


class ReportTask(Base):
    """Persistent report-generation task for a user-owned game."""

    __tablename__ = "report_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_game_id = Column(String(32), ForeignKey("user_games.id"), nullable=False, index=True)
    report_type = Column(String(20), default="normal")
    requested_visits = Column(Integer, default=500)
    status = Column(String(20), default="pending")  # authorizing / pending / running / completed / failed
    total_moves = Column(Integer, default=0)
    analyzed_moves = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    # 账本幂等键。None = 没走积分扣费(用了免费周额度,或 BILLING_ENFORCED 关着,或历史数据)。
    charge_ref = Column(String(160), nullable=True, index=True)
    # 用掉的免费周额度的周期键(如 "W:2026-W36")。与 charge_ref 互斥。
    free_grant_period = Column(String(32), nullable=True)
    # 非 NULL = 这个任务不该被结算器收费(如运维 requeue_reports.py 重排)。
    # 结算器看见它一律跳过，无论 charge_ref 是否还挂着。留痕用途：区分
    # "从没计费过"(charge_ref 也是 None 且这一列也是 None)与
    # "计费了但被运维豁免"。
    billing_exempt_reason = Column(String(32), nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user_game = relationship("UserGame", back_populates="report_tasks")
    moves = relationship("ReportTaskMove", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_report_tasks_user_created", "user_id", "created_at"),
        Index("ix_report_tasks_game_type_created", "user_game_id", "report_type", "created_at"),
        Index("ix_report_tasks_status_created", "status", "created_at"),
    )


class ReportTaskMove(Base):
    """Stored move-by-move analysis snapshot for a report task."""

    __tablename__ = "report_task_moves"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("report_tasks.id"), nullable=False, index=True)
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

    task = relationship("ReportTask", back_populates="moves")

    __table_args__ = (UniqueConstraint("task_id", "move_number", name="uq_report_task_move"),)


class SyncQueueEntry(Base):
    """Offline sync queue for board mode. See design.md Section 4.5.1."""

    __tablename__ = "sync_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    idempotency_key = Column(String(64), unique=True, nullable=False, index=True)
    operation = Column(String(64), nullable=False)  # create_user_game / update_tsumego_progress
    endpoint = Column(String(256), nullable=False)  # Remote API path
    method = Column(String(8), nullable=False)  # POST / PUT
    payload = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False, default="pending", index=True)  # pending/in_progress/completed/failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    locked_at = Column(DateTime(timezone=True), nullable=True)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=5)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    last_http_status = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    user_id = Column(String(64), nullable=True)
    device_id = Column(String(64), nullable=True)

    __table_args__ = (Index("ix_sync_queue_status_retry", "status", "next_retry_at"),)


class DeviceHeartbeatDB(Base):
    """Server-side device tracking. See design.md Section 4.15.2."""

    __tablename__ = "device_heartbeats"

    device_id = Column(String(64), primary_key=True)
    last_seen = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    queue_depth = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    oldest_unsynced_age_sec = Column(Integer, default=0)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(64), nullable=True)
    app_version = Column(String(32), nullable=True)


class UpcomingMatchDB(Base):
    """Upcoming/scheduled matches from various sources (populated by katrain-cron)."""

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


# ============ Cross-Platform Play Models ============


class PlatformGameDB(Base):
    """Cross-platform game records — games played on external platforms (OGS, Fox, etc.) via KaTrain."""

    __tablename__ = "platform_games"

    id = Column(String(64), primary_key=True)  # KaTrain game UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String(20), nullable=False, index=True)  # "ogs", "fox", "golaxy", "kgs"
    platform_game_id = Column(String(128), nullable=False)  # ID on the remote platform
    opponent_name = Column(String(128), nullable=True)
    opponent_rank = Column(String(16), nullable=True)
    my_color = Column(String(1), nullable=True)  # "B" or "W"
    result = Column(String(64), nullable=True)  # "B+5.5", "W+R", etc.
    board_size = Column(Integer, default=19)
    sgf_content = Column(Text, nullable=True)
    played_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="platform_games")

    __table_args__ = (UniqueConstraint("platform", "platform_game_id", name="uq_platform_game"),)


# ============ Billing / Credits Models (single-pool integer ledger) ============
#
# Asset accounting uses INTEGER amounts only (credits as whole units; CNY as 分/fen).
# Server is authoritative — board (kiosk) terminals proxy to the cloud and never
# spend against local SQLite. See katrain/web/core/billing.py for the service layer.


class CreditTransaction(Base):
    """Append-only credit ledger. One row per balance-affecting event.

    status lifecycle for spends: reserved -> committed | refunded.
    Grants (recharge/redeem/admin) are written directly as committed.
    `ref_id` is the idempotency key — a unique, server-derived string. Replaying
    the same ref_id is a no-op that returns the existing row's balance_after.
    """

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    delta = Column(Integer, nullable=False)  # signed: negative=spend(reserve), positive=grant/refund
    reason = Column(String(64), nullable=False)  # e.g. analysis_territory, redeem, order, admin_grant, refund_*
    ref_id = Column(String(160), nullable=False, unique=True)  # idempotency key
    status = Column(String(16), nullable=False, default="committed")  # committed | reserved | refunded
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_credit_tx_user_status", "user_id", "status"),)


class RedeemCode(Base):
    """High-entropy redeemable codes that grant credits. Single-use, optional expiry."""

    __tablename__ = "redeem_codes"

    code = Column(String(64), primary_key=True)  # >=128-bit random hex; not enumerable
    credits = Column(Integer, nullable=False)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RechargeOrder(Base):
    """A recharge order through a PaymentProvider. ManualConfirm + redeem this round.

    status: pending -> proof_submitted -> paid | cancelled. No auto-expiry this round.
    Package amount/credits come from server config — never trusted from the client.
    """

    __tablename__ = "recharge_orders"

    id = Column(Integer, primary_key=True, index=True)
    out_trade_no = Column(String(64), nullable=False, unique=True, index=True)  # provider order id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    package_id = Column(String(64), nullable=False)
    amount_fen = Column(Integer, nullable=False)  # CNY in 分 (cents)
    credits = Column(Integer, nullable=False)
    provider = Column(String(32), nullable=False)  # manual | wechat | alipay
    status = Column(String(24), nullable=False, default="pending")
    proof_url = Column(Text, nullable=True)
    proof_hash = Column(String(64), nullable=True)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    confirm_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    settled_at = Column(DateTime(timezone=True), nullable=True)


class QuotaBucket(Base):
    """会员额度桶：计数器，不是货币。

    周期键惰性生成（`D:2026-09-05` / `W:2026-W36` / `M:2026-09`，Asia/Shanghai），
    到点自然换一个新键 ⇒ **不需要任何重置任务**。
    `allowance` 是开桶那一刻的套餐快照，中途改套餐不影响已开的桶。
    """

    __tablename__ = "quota_buckets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(32), nullable=False)
    period_key = Column(String(32), nullable=False)
    allowance = Column(Integer, nullable=False)
    used = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "kind", "period_key", name="uq_quota_bucket"),
        Index("ix_quota_bucket_lookup", "user_id", "kind", "period_key"),
    )
