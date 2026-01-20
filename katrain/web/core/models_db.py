from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, Enum, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from katrain.web.core.db import Base
import enum

class GameType(str, enum.Enum):
    FREE = "free"
    RATED = "rated"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    rank = Column(String, default="20k")
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
    game_id = Column(Integer, ForeignKey("games.id"))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    game = relationship("Game", back_populates="rating_history")
    user = relationship("User")