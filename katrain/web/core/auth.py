import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from jose import JWTError, jwt
from passlib.context import CryptContext
from katrain.web.core.config import settings

logger = logging.getLogger("katrain_web")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    *,
    box_generation: int | None = None,
):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    if box_generation is not None:
        to_encode["box_generation"] = box_generation
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


from sqlalchemy.orm import Session
from katrain.web.core import models_db


class UserRepository(ABC):
    @abstractmethod
    def create_user(self, username: str, hashed_password: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_users(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def follow_user(self, follower_id: int, following_id: int) -> bool:
        pass

    @abstractmethod
    def unfollow_user(self, follower_id: int, following_id: int) -> bool:
        pass

    @abstractmethod
    def get_followers(self, user_id: int) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_following(self, user_id: int) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def has_completed_placement(self, user_id: int) -> bool:
        pass


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def init_db(self):
        # With SQLAlchemy, we typically use Alembic for migrations.
        # But for simplicity/dev, we can use Base.metadata.create_all
        from katrain.web.core.db import engine
        from sqlalchemy import inspect, text
        from katrain.web.core import migrations

        models_db.Base.metadata.create_all(bind=engine)

        # Dev migration: drop old 'games' table and recreate 'rating_history'
        # to update game_id FK from games.id (Integer) to user_games.id (String)
        inspector = inspect(engine)
        if "games" in inspector.get_table_names():
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS rating_history"))
                conn.execute(text("DROP TABLE IF EXISTS games"))
            # Recreate rating_history with the new schema
            models_db.Base.metadata.create_all(bind=engine)

        # Lightweight, non-destructive migration (all dialects): ADD COLUMN / CREATE
        # INDEX for anything missing (e.g. users.is_admin, billing indexes). Runs
        # BEFORE the SQLite drift-rebuild so a simple new column never drops data.
        migrations.add_missing_columns(engine)
        migrations.create_missing_indexes(engine)

        # Schema drift guard (SQLite only): if ORM model columns STILL don't match
        # (e.g. a column type change that ADD COLUMN can't fix), drop and recreate
        # local tables — but NEVER the billing/ledger tables, which hold real assets.
        if engine.dialect.name == "sqlite":
            inspector = inspect(engine)
            drift_tables = []
            for table in models_db.Base.metadata.sorted_tables:
                if table.name not in inspector.get_table_names():
                    continue
                existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
                expected_cols = {c.name for c in table.columns}
                if not expected_cols.issubset(existing_cols):
                    drift_tables.append(table.name)
            # Only rebuild unprotected tables; refuse to drop asset tables
            # (credits, and the ladder ledger that every 段位 is derived from).
            rebuildable = [t for t in drift_tables if t not in migrations.PROTECTED_TABLES]
            if any(t in migrations.PROTECTED_TABLES for t in drift_tables):
                import logging

                logging.getLogger("katrain_web").error(
                    f"Schema drift in protected table(s) {set(drift_tables) & migrations.PROTECTED_TABLES}; "
                    "refusing to drop. Resolve manually."
                )
            if rebuildable:
                import logging

                logging.getLogger("katrain_web").warning(
                    f"Schema drift in {rebuildable}; rebuilding those local tables."
                )
                tables = [models_db.Base.metadata.tables[t] for t in rebuildable]
                models_db.Base.metadata.drop_all(bind=engine, tables=tables)
                models_db.Base.metadata.create_all(bind=engine, tables=tables)

    def create_user(self, username: str, hashed_password: str) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            # Defaults are handled by SQLAlchemy model
            db_user = models_db.User(username=username, hashed_password=hashed_password)
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            return self._to_dict(db_user)
        except Exception as e:
            session.rollback()
            from sqlalchemy.exc import IntegrityError

            if isinstance(e, IntegrityError):
                raise ValueError("User already exists")
            raise e
        finally:
            session.close()

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            user = session.query(models_db.User).filter(models_db.User.username == username).first()
            if user:
                return self._to_dict(user)
            return None
        finally:
            session.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            user = session.query(models_db.User).filter(models_db.User.id == user_id).first()
            if user:
                return self._to_dict(user)
            return None
        finally:
            session.close()

    def list_users(self) -> List[Dict[str, Any]]:
        session = self.session_factory()
        try:
            users = session.query(models_db.User).all()
            return [self._to_dict(user) for user in users]
        finally:
            session.close()

    def follow_user(self, follower_id: int, following_id: int) -> bool:
        if follower_id == following_id:
            return False
        session = self.session_factory()
        try:
            # Check if already following
            existing = (
                session.query(models_db.Relationship)
                .filter_by(follower_id=follower_id, following_id=following_id)
                .first()
            )
            if existing:
                return True

            rel = models_db.Relationship(follower_id=follower_id, following_id=following_id)
            session.add(rel)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def unfollow_user(self, follower_id: int, following_id: int) -> bool:
        session = self.session_factory()
        try:
            rel = (
                session.query(models_db.Relationship)
                .filter_by(follower_id=follower_id, following_id=following_id)
                .first()
            )
            if rel:
                session.delete(rel)
                session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def get_followers(self, user_id: int) -> List[Dict[str, Any]]:
        session = self.session_factory()
        try:
            # Users who follow this user
            followers = (
                session.query(models_db.User)
                .join(models_db.Relationship, models_db.User.id == models_db.Relationship.follower_id)
                .filter(models_db.Relationship.following_id == user_id)
                .all()
            )
            return [self._to_dict(user) for user in followers]
        finally:
            session.close()

    def get_following(self, user_id: int) -> List[Dict[str, Any]]:
        session = self.session_factory()
        try:
            # Users whom this user follows
            following = (
                session.query(models_db.User)
                .join(models_db.Relationship, models_db.User.id == models_db.Relationship.following_id)
                .filter(models_db.Relationship.follower_id == user_id)
                .all()
            )
            return [self._to_dict(user) for user in following]
        finally:
            session.close()

    def has_completed_placement(self, user_id: int) -> bool:
        """Whether the user has a ladder rank yet -- the prerequisite for rated PvP.

        This replaces a count of completed `game_type == "rated"` games, which was
        unreachable: nothing ever wrote that value for an AI game, so the counter sat
        at 0 forever while the lobby told players to go earn it.
        """
        session = self.session_factory()
        try:
            rung = (
                session.query(models_db.User.ai_ladder_rung)
                .filter(models_db.User.id == user_id)
                .scalar()
            )
            return rung is not None
        finally:
            session.close()

    def _to_dict(self, user_obj: models_db.User) -> Dict[str, Any]:
        return {
            "id": user_obj.id,
            "uuid": user_obj.uuid,
            "username": user_obj.username,
            "hashed_password": user_obj.hashed_password,
            "rank": user_obj.rank,
            "credits": user_obj.credits,
            "is_admin": bool(user_obj.is_admin),
            "avatar_url": user_obj.avatar_url,
            "created_at": user_obj.created_at,
        }
