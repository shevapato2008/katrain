"""`token_epoch` 列在两条路上的形状：全新建库 与 迁移旧库。

只测 `create_all` 证明不了生产 —— 线上库早就存在，跑的是
`migrations.add_missing_columns()`（`SQLAlchemyUserRepository.init_db()` 里那一串）。
这个文件照 `tests/web_ui/test_phone_migration.py` 的夹具写法。
"""
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

from katrain.web.core import migrations, models_db


def _fresh_engine(tmp_path, name):
    """按模型新建一个库 —— 「全新部署」那条路。"""
    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    models_db.Base.metadata.create_all(eng)
    return eng


def _legacy_users_db(tmp_path, name):
    """没有 token_epoch 的 users 表 —— 线上库在这次改动之前的形状。"""
    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    md = MetaData()
    Table(
        "users",
        md,
        Column("id", Integer, primary_key=True),
        Column("username", String, unique=True, index=True),
        Column("hashed_password", String),
    )
    md.create_all(eng)
    return eng


def test_fresh_db_has_token_epoch_not_null_defaulting_to_zero(tmp_path):
    insp = inspect(_fresh_engine(tmp_path, "fresh"))
    cols = {c["name"]: c for c in insp.get_columns("users")}
    assert "token_epoch" in cols, "新建库缺 token_epoch 列"
    assert cols["token_epoch"]["nullable"] is False
    # nullable=False 只保证「不能存 NULL」，不保证「存量行能拿到 0」——
    # 迁移旧库的存量行靠的是 schema 上真有一个默认值。这里连带钉住它。
    assert cols["token_epoch"]["default"] is not None, "默认值没落到 schema 上，迁移库的存量行会拿不到 0"


def test_migration_adds_token_epoch_to_an_existing_users_table(tmp_path):
    eng = _legacy_users_db(tmp_path, "legacy")
    migrations.add_missing_columns(eng)
    cols = {c["name"] for c in inspect(eng).get_columns("users")}
    assert "token_epoch" in cols, "迁移路径没把 token_epoch 加上"


def test_migrated_column_is_nullable_and_that_is_why_readers_must_coalesce(tmp_path):
    """**这条是刻意断言一个缺陷，不是断言一个期望。**

    `migrations.add_missing_columns`（migrations.py:341）拼的 DDL 只带 DEFAULT、
    不带 NOT NULL ⇒ 迁移库上这一列可空，而新建库上不可空。两条路结构不一致。

    本轮不修那个函数（它影响所有列、不属 P1 范围），改为在**读取侧**兜住：
    所有读 token_epoch 的地方都写 `(user_dict.get("token_epoch") or 0)`。
    这条测试把这个分叉钉住，免得有人日后看到「新建库是 NOT NULL」就把 `or 0` 删掉。
    配套的行为闸在 tests/web_ui/test_identity_subject.py 的闸 3。
    """
    eng = _legacy_users_db(tmp_path, "legacy2")
    migrations.add_missing_columns(eng)
    col = {c["name"]: c for c in inspect(eng).get_columns("users")}["token_epoch"]
    assert col["nullable"] is True, (
        "迁移库上 token_epoch 竟然是 NOT NULL —— 说明 add_missing_columns 改过了，"
        "此时读取侧的 `or 0` 可以评估是否还需要，但要连同闸 3 一起重裁"
    )


def test_to_dict_exposes_token_epoch(tmp_path):
    """解析侧要从仓储返回的字典里读它 —— `_to_dict` 是显式白名单，不加就永远读不到。"""
    from sqlalchemy.orm import sessionmaker

    from katrain.web.core.auth import SQLAlchemyUserRepository

    # SQLAlchemyUserRepository.__init__ 收的是 **session_factory**，不是 URL 字符串
    # （core/auth.py:140）。仓里既有写法见 tests/web_ui/test_lobby_sso_websocket.py:29。
    eng = create_engine(f"sqlite:///{tmp_path}/d.db")
    repo = SQLAlchemyUserRepository(sessionmaker(bind=eng))
    repo.init_db()
    created = repo.create_user(username="epoch-user", hashed_password="x")
    assert "token_epoch" in created
    assert created["token_epoch"] == 0
