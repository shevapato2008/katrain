from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, Enum, CheckConstraint, Boolean, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from katrain.web.core.db import Base
import enum
import uuid as uuid_module


class GameType(str, enum.Enum):
    FREE = "free"
    RATED = "rated"


class MatchSourceEnum(str, enum.Enum):
    """Data source for live matches."""
    XINGZHEN = "xingzhen"
    WEIQI_ORG = "weiqi_org"


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
    uuid = Column(String, unique=True, index=True, default=lambda: uuid_module.uuid4().hex)  # Unique UUID assigned at registration
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    rank = Column(String, default="20k")
    net_wins = Column(Integer, default=0)
    elo_points = Column(Integer, default=0)
    credits = Column(Float, default=10000.00)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    games_black = relationship("Game", foreign_keys="[Game.black_player_id]", back_populates="black_player")
    games_white = relationship("Game", foreign_keys="[Game.white_player_id]", back_populates="white_player")
    followers = relationship("Relationship", foreign_keys="[Relationship.following_id]", back_populates="following")
    following = relationship("Relationship", foreign_keys="[Relationship.follower_id]", back_populates="follower")

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    black_player_id = Column(Integer, ForeignKey("users.id"))
    white_player_id = Column(Integer, ForeignKey("users.id"))
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sgf_content = Column(Text, nullable=True)
    result = Column(String, nullable=True)
    game_type = Column(String, nullable=False, default="free") # 'free' or 'rated'
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    black_player = relationship("User", foreign_keys=[black_player_id], back_populates="games_black")
    white_player = relationship("User", foreign_keys=[white_player_id], back_populates="games_white")
    rating_history = relationship("RatingHistory", back_populates="game")

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
    game_id = Column(Integer, ForeignKey("games.id"))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    game = relationship("Game", back_populates="rating_history")
    user = relationship("User")


class LiveMatchDB(Base):
    """Database model for live/historical matches from external sources."""
    __tablename__ = "live_matches"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(64), unique=True, nullable=False, index=True)  # Format: {source}_{source_id}
    source = Column(String(20), nullable=False)  # xingzhen / weiqi_org
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
    current_score = Column(Float, default=0.0)    # From XingZhen API
    katago_winrate = Column(Float, nullable=True)  # From local KataGo (latest move)
    katago_score = Column(Float, nullable=True)    # From local KataGo (latest move)
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
    __table_args__ = (
        UniqueConstraint('match_id', 'move_number', name='uq_match_move'),
    )

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