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

class SQLiteUserRepository(UserRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def create_user(self, username: str, hashed_password: str) -> Dict[str, Any]:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
                    (username, hashed_password),
                )
                conn.commit()
                return self.get_user_by_username(username)
        except sqlite3.IntegrityError:
            raise ValueError("User already exists")

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row:
                return dict(row)
        return None

    def list_users(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(row) for row in rows]
