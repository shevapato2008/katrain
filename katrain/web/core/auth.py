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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
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

class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def init_db(self):
        # With SQLAlchemy, we typically use Alembic for migrations.
        # But for simplicity/dev, we can use Base.metadata.create_all
        from katrain.web.core.db import engine
        models_db.Base.metadata.create_all(bind=engine)

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
            existing = session.query(models_db.Relationship).filter_by(
                follower_id=follower_id, following_id=following_id
            ).first()
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
            rel = session.query(models_db.Relationship).filter_by(
                follower_id=follower_id, following_id=following_id
            ).first()
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
            followers = session.query(models_db.User).join(
                models_db.Relationship, models_db.User.id == models_db.Relationship.follower_id
            ).filter(models_db.Relationship.following_id == user_id).all()
            return [self._to_dict(user) for user in followers]
        finally:
            session.close()

    def get_following(self, user_id: int) -> List[Dict[str, Any]]:
        session = self.session_factory()
        try:
            # Users whom this user follows
            following = session.query(models_db.User).join(
                models_db.Relationship, models_db.User.id == models_db.Relationship.following_id
            ).filter(models_db.Relationship.follower_id == user_id).all()
            return [self._to_dict(user) for user in following]
        finally:
            session.close()

    def _to_dict(self, user_obj: models_db.User) -> Dict[str, Any]:
        return {
            "id": user_obj.id,
            "username": user_obj.username,
            "hashed_password": user_obj.hashed_password,
            "rank": user_obj.rank,
            "credits": user_obj.credits,
            "avatar_url": user_obj.avatar_url,
            "created_at": user_obj.created_at
        }
