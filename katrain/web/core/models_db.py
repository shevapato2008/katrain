from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, Enum, CheckConstraint, Boolean, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from katrain.web.core.db import Base
import enum
import uuid as uuid_module

class GameType(str, enum.Enum):
    FREE = "free"
    RATED = "rated"

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
    tsumego_progress = relationship("UserTsumegoProgress", back_populates="user")

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

    __table_args__ = (
        Index("ix_tsumego_level_category", "level", "category"),
    )


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