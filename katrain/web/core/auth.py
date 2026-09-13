import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from jose import JWTError, jwt
from passlib.context import CryptContext
from katrain.web.core.config import settings

logger = logging.getLogger("katrain_web")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验口令。**无法识别的 hash 返回 False，不抛。**

    passlib 对空串/哨兵值/任何非 bcrypt 串抛 `UnknownHashError`。让它抛出去的后果是
    这类账号被打 /auth/login 时 **500 而不是 401** —— 而 500 与 401 可区分,
    于是任何人都能免费枚举出"哪些账号存在但没有可用口令"。

    仓里已经有这样的哨兵：`SHADOW_USER_NO_LOCAL_AUTH`
    （`katrain/web/api/v1/endpoints/auth.py:77`，`:187` 的 `_get_or_create_shadow_user`
    拿它建盒子影子用户）。今天够不着,因为 board 模式先把 /auth/login 转发给云端了 ——
    那是**调用顺序**保住的,不是结构。这里收口之后就与调用顺序无关。

    **只吞 `ValueError`，不写 `except Exception`，也故意不收 `TypeError`**：
    `UnknownHashError` 是 `ValueError` 的子类（实跑确认过 MRO），密码超长这类也是
    `ValueError`，它们都该当"口令不匹配"。而 bcrypt 后端缺失抛的是
    `passlib.exc.MissingBackendError`（`RuntimeError` 的子类）—— 那种故障必须原样炸成
    500 让人看见，吞掉它的表现是"全站所有人的密码都突然不对了"，一声不吭。

    `TypeError`（调用方传了非 str，比如仓储层哪天回来的是 `int`、ORM 的 `Column`、
    BYTEA 的 `memoryview`，或者拿错成 `User.hashed_password` 而不是
    `user.hashed_password`）是同一个形状的故障，不是"口令不匹配"，必须一样原样炸出来
    ——吞掉它的表现是"全站每次登录静默变 401"，`or` 短路会让它跟"密码错了"长得一模
    一样，日志里什么都不会响。需求要收口的 5 个哨兵值全部落在 `ValueError` 一侧，
    没有任何调用方需要 `TypeError` 被吞掉。
    """
    try:
        return bool(pwd_context.verify(plain_password, hashed_password))
    except ValueError:
        return False


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
    def create_user(
        self, username: str, hashed_password: str, signup_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_user_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def bind_phone(self, user_id: int, phone_e164: str) -> str:
        """返回 "ok" | "phone_taken" | "already_bound"。三个字符串是契约，不许换。"""

    @abstractmethod
    def get_phone_e164(self, user_id: int) -> Optional[str]:
        ...

    @abstractmethod
    def set_password_hash(self, user_id: int, hashed: str) -> None:
        ...

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
    def count_completed_rated_games(self, user_id: int) -> int:
        pass


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _bind(self):
        """建表/迁移要用的 engine —— 取自本对象自己的 `session_factory`。

        原来这里是 `from katrain.web.core.db import engine`，抓的是模块级全局 engine，
        于是**调用方注入了自己的 session_factory 也没用**：建表、迁移、账本触发器
        统统落到全局那个库上。2026-08-23 实测，测试就是这样把 34 张表建进开发机
        真实 dev 库的（`tests/conftest.py` 里记了完整链路）。

        生产没有变化：`_lifespan_server` 不注入时传进来的就是全局 `SessionLocal`，
        它的 bind 正是原来那个全局 engine。
        """
        bind = getattr(self.session_factory, "kw", {}).get("bind")
        if bind is not None:
            return bind
        session = self.session_factory()
        try:
            return session.get_bind()
        finally:
            session.close()

    def init_db(self):
        # With SQLAlchemy, we typically use Alembic for migrations.
        # But for simplicity/dev, we can use Base.metadata.create_all
        from sqlalchemy import inspect, text
        from katrain.web.core import ledger_immutability, migrations

        engine = self._bind()

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
        migrations.migrate_ai_ladder_decision_schema(engine)
        migrations.add_missing_columns(engine)
        migrations.backfill_ai_ladder_decisions(engine)
        migrations.create_missing_indexes(engine)
        # PostgreSQL-only: the kifu list's DESC NULLS LAST ordering cannot be
        # declared in __table_args__ without breaking SQLite. See the docstring.
        migrations.create_kifu_album_sort_index(engine)

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
            # Only rebuild non-authoritative tables; refuse to drop asset/rank ledgers.
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

        # 账本只追加 —— 由触发器执行,不靠调用方自觉。三家(象棋/国象/五子棋)
        # 2026-08-13 已在共享 `ranked.ledgers` 上装了同源的一对,围棋是最后一个。
        #
        # **必须是 init_db 的最后一步**,两个理由:
        #   1. `backfill_ai_ladder_decisions`(:122)要对存量行发 UPDATE,得先跑完;
        #   2. 上面的漂移重建走 drop+create,会把触发器一并带走 —— 虽然账本在
        #      PROTECTED_TABLES 里不会被重建,但顺序放在后面就不必依赖那个事实。
        ledger_immutability.install(engine)

    def create_user(
        self, username: str, hashed_password: str, signup_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            # Defaults are handled by SQLAlchemy model
            db_user = models_db.User(
                username=username, hashed_password=hashed_password, signup_ip=signup_ip
            )
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

    def get_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            user = (
                session.query(models_db.User)
                .filter(models_db.User.phone_e164 == phone_e164)
                .first()
            )
            return self._to_dict(user) if user else None
        finally:
            session.close()

    def bind_phone(self, user_id: int, phone_e164: str) -> str:
        """绑号。

        三个返回值：
          "ok"            —— 绑上了（含「本来就绑着同一个号」这种幂等重试）
          "already_bound" —— 这个账号已经绑着**另一个**号。**不覆盖** ——
                             覆盖就是一条自助换绑路径，而换绑同时是旧号的解绑，
                             「一号一账号」的经济论证与 Task 11 那条短路都建在
                             「不存在解绑路径」上。
          "phone_taken"   —— 这个号被别人占了。靠唯一索引兜底，不靠「先查后写」
                             那条竞态（两个请求同时到达时先查后写都会判成没占）。
        """
        from sqlalchemy.exc import IntegrityError

        session = self.session_factory()
        try:
            u = session.query(models_db.User).filter_by(id=user_id).one()
            if u.phone_e164 is not None:
                return "ok" if u.phone_e164 == phone_e164 else "already_bound"
            u.phone_e164 = phone_e164
            u.phone_verified_at = datetime.now(timezone.utc)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return "phone_taken"
            return "ok"
        finally:
            session.close()

    def get_phone_e164(self, user_id: int) -> Optional[str]:
        """原始号的**唯一**取用点。

        它不进 `_to_dict`、不进 pydantic `User` —— 灌进去会随 `User` 泄进
        每一个回 `User` 的响应（`models.py` 的 `OnlineUser` 收窄注释
        正是为防这类外溢）。闸一律读 `phone_bound` 那个布尔。
        """
        session = self.session_factory()
        try:
            u = session.query(models_db.User).filter_by(id=user_id).one_or_none()
            return u.phone_e164 if u is not None else None
        finally:
            session.close()

    def set_password_hash(self, user_id: int, hashed: str) -> None:
        """`create_user` 之外的**第二个** `hashed_password` 写入点。"""
        session = self.session_factory()
        try:
            session.query(models_db.User).filter_by(id=user_id).update({"hashed_password": hashed})
            session.commit()
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

    def get_user_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        """按 account_subject 查行。**用 `.one_or_none()` 不用 `.first()`。**

        `users.uuid` 有唯一索引（models_db.py:70-71），所以结果集基数 ≤ 1。
        用 `.one_or_none()` 的理由是：万一哪天那条唯一索引没了（迁移漏删、
        有人改了模型），它会**抛** MultipleResultsFound 而不是静默取一行 ——
        而静默取一行在鉴权路径上就是跨账号串号。
        同文件的 `get_user_by_username`(:258) 用的是 `.first()`，那是既有行为，
        本轮不动它（P3 去掉用户名唯一性时必须一起重裁）。
        """
        session = self.session_factory()
        try:
            user = session.query(models_db.User).filter(models_db.User.uuid == user_uuid).one_or_none()
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

    def count_completed_rated_games(self, user_id: int) -> int:
        session = self.session_factory()
        try:
            count = (
                session.query(models_db.UserGame)
                .filter(
                    models_db.UserGame.user_id == user_id,
                    models_db.UserGame.game_type == "rated",
                    models_db.UserGame.result.isnot(None),
                )
                .count()
            )
            return count
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
            # 解析侧要拿它和 token 里的 epoch 比。pydantic `User`(models.py:181) 没有
            # 这个字段，v2 默认 extra='ignore' 会静默丢掉它 —— 那是对的，前端不需要。
            "token_epoch": user_obj.token_epoch,
            # 发言闸/免费额度闸只需要"绑没绑"这一个布尔。原始号不进这里：
            # 它会随 pydantic `User` 泄进每一个回 User 的响应（models.py 的
            # `OnlineUser` 收窄注释正是为防这类外溢）。要原始号走 get_phone_e164()。
            "phone_bound": user_obj.phone_e164 is not None,
        }
