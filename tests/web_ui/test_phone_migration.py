"""手机号两列 + sms_challenges 表，以及**迁移那条路**真的会把它们加上。

只测 `create_all` 证明不了生产：线上库早就存在，跑的是
`migrations.add_missing_columns()` / `create_missing_indexes()`
（`SQLAlchemyUserRepository.init_db()` 里那一串）。
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db


def _fresh_engine(tmp_path, name):
    """按模型新建一个库 —— "全新部署"那条路。"""
    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    models_db.Base.metadata.create_all(eng)
    return eng


def _legacy_users_db(tmp_path, name):
    """只有老三列的 users 表 —— 线上库在这次改动之前的形状。"""
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


def _unique_column_sets(insp, table_name):
    """这张表上「哪几组列被强制唯一」，不管它落成索引还是表约束。

    **不能只看 `get_indexes()`**：列上写 `unique=True` 时，唯一性会落成
    CREATE TABLE 里的表约束，`get_indexes()` 根本看不见它 —— 于是"只看索引"的
    断言对「有人把 unique 从 __table_args__ 挪到列上」这个错误完全免疫。
    """
    out = set()
    for ix in insp.get_indexes(table_name):
        if ix["unique"]:
            out.add(tuple(ix["column_names"]))
    for uc in insp.get_unique_constraints(table_name):
        out.add(tuple(uc["column_names"]))
    return out


def test_user_phone_columns_and_unique_index_exist(tmp_path):
    insp = inspect(_fresh_engine(tmp_path, "t1"))
    cols = {c["name"] for c in insp.get_columns("users")}
    assert {"phone_e164", "phone_verified_at"} <= cols
    idx = {i["name"]: i for i in insp.get_indexes("users")}
    assert "ix_users_phone_e164" in idx
    # **不许写 `is True`**：SQLite 的 inspector 把 unique 反射成 int 1，
    # 而 `1 is True` 为假 ⇒ 那样写的断言恒红，最省事的"修法"就是把它删掉。
    # 2026-09-07 实测：`[(i["name"], i["unique"]) for i in insp.get_indexes("users")]`
    # → `[('ix_users_id', 0), ('ix_users_username', 1), ('ix_users_uuid', 1)]`。
    assert bool(idx["ix_users_phone_e164"]["unique"]) is True


def test_phone_column_itself_is_not_unique():
    """列上不许写 `unique=True`（F2）。

    `add_missing_columns()` 拼的 ADD COLUMN 不带 UNIQUE，写在列上会让
    "新建库"与"迁移旧库"得到不同的表结构 —— 后者根本没有唯一性。
    """
    col = models_db.User.__table__.columns["phone_e164"]
    assert col.unique is not True
    assert col.nullable is True  # 存量账号留 NULL，不造占位号


def test_null_phones_do_not_collide(tmp_path):
    """F1：SQLite 与 PostgreSQL 的唯一索引都不管 NULL ⇒ 几百个老账号不需要占位号。"""
    session = sessionmaker(bind=_fresh_engine(tmp_path, "t3"))()
    session.add(models_db.User(username="a", hashed_password="h"))
    session.add(models_db.User(username="b", hashed_password="h"))
    session.commit()
    assert session.query(models_db.User).count() == 2
    session.close()


def test_two_users_cannot_share_a_phone_number(tmp_path):
    """唯一索引必须**真的拦得住**。

    只断言"索引存在且 unique=1"是在断言元数据；一个号绑到两个账号上会让
    `get_by_phone()` 的 `one_or_none()` 直接抛，而受害者是先绑的那个人。
    """
    Session = sessionmaker(bind=_fresh_engine(tmp_path, "t4"))
    session = Session()
    session.add(models_db.User(username="a", hashed_password="h", phone_e164="+8613800138000"))
    session.commit()
    session.add(models_db.User(username="b", hashed_password="h", phone_e164="+8613800138000"))
    # match= 把判据钉在被测对象上：SQLite/PostgreSQL 的完整性冲突报错文本不同，
    # 但两边都会在错误里带上冲突的列名，"phone_e164" 是两边共有的最小子串
    # （2026-09-08 SQLite 实测：`UNIQUE constraint failed: users.phone_e164`）。
    with pytest.raises(IntegrityError, match="phone_e164"):
        session.commit()
    session.rollback()
    session.close()


def test_sms_challenges_table_shape(tmp_path):
    """`sms_challenges` 是本 Task 独有的新表 —— 列集合用 `==`，多一列也要红。

    （`users` 那张表不这么断言：它还有一堆既有列，`==` 会立刻错。）
    """
    insp = inspect(_fresh_engine(tmp_path, "t5"))
    cols = {c["name"] for c in insp.get_columns("sms_challenges")}
    assert cols == {
        "id", "challenge_id", "phone_e164", "purpose", "code_hash", "attempts",
        "consumed_at", "provider_charged", "delivered_ok", "is_intl", "client_ip",
        "created_at", "expires_at",
    }
    idx = {i["name"]: i for i in insp.get_indexes("sms_challenges")}
    assert bool(idx["ix_sms_challenge_cid"]["unique"]) is True
    # 四条索引里之前只断言了一条：删掉另外三条中的任意一条（同号冷却查询、
    # 全站日额度查询、按 IP 查询各自要用的那条），8 条用例照样全绿——
    # 丢了不报错，只会让 Task 6 的查询退化成全表扫描。
    assert set(idx) >= {
        "ix_sms_challenge_cid",
        "ix_sms_challenge_phone_purpose",
        "ix_sms_challenge_cap",
        "ix_sms_challenge_ip",
    }


def test_delivered_ok_is_a_mapped_column_not_a_stray_attribute(tmp_path):
    """`delivered_ok` 必须是**映射过的列**，断言要落在**另一个 session** 上。

    列没映射时 `row.delivered_ok = False` 只是给实例挂了个游离属性：
    同一个 session 因 identity map 返回同一个对象，读回来还是 False（**测试绿**）；
    生产的下一个请求是新 session，那个属性根本不存在，调用方的
    `getattr(row, "delivered_ok", True)` 会兜成 True（**行为相反**）。
    2026-09-07 用仓里的 SQLAlchemy 实跑复现过：同 session 读到 False，
    异 session 读到 AttributeError/兜底值。
    """
    Session = sessionmaker(bind=_fresh_engine(tmp_path, "t6"))
    now = datetime.now(timezone.utc)
    s1 = Session()
    s1.add(
        models_db.SmsChallenge(
            challenge_id="cid-1",
            phone_e164="+8613800138000",
            purpose="login",
            code_hash="h" * 64,
            attempts=0,
            provider_charged=True,
            is_intl=False,
            client_ip="203.0.113.9",
            expires_at=now + timedelta(seconds=300),
        )
    )
    s1.commit()
    row = s1.query(models_db.SmsChallenge).filter_by(challenge_id="cid-1").one()
    assert row.delivered_ok is True       # 默认：交出去了就当送达
    assert row.provider_charged is True
    row.delivered_ok = False
    s1.commit()
    s1.close()

    s2 = Session()
    reread = s2.query(models_db.SmsChallenge).filter_by(challenge_id="cid-1").one()
    assert reread.delivered_ok is False
    s2.close()


def test_add_missing_columns_migrates_an_existing_users_table(tmp_path):
    """生产上跑的是这条路：表早就在，靠 ADD COLUMN / CREATE INDEX 补。"""
    eng = _legacy_users_db(tmp_path, "old1")
    migrations.add_missing_columns(eng)
    migrations.create_missing_indexes(eng)
    insp = inspect(eng)
    assert {"phone_e164", "phone_verified_at"} <= {c["name"] for c in insp.get_columns("users")}
    assert ("phone_e164",) in _unique_column_sets(insp, "users")


def test_migrated_users_table_also_rejects_duplicate_phone(tmp_path):
    """迁移路径的唯一性不能只靠 inspector 反射证明。

    `test_two_users_cannot_share_a_phone_number` 验的是 create_all 那条路；
    `test_add_missing_columns_migrates_an_existing_users_table` 只断言
    `_unique_column_sets()` 反射出来"看着是 unique"——反射读的是真库 schema，
    覆盖不是零，但缺"索引存在且反射为 unique、但库不真拦"这一格。这条测
    在迁移出来的库上真插两行同号，拿 `IntegrityError`。
    """
    eng = _legacy_users_db(tmp_path, "old3")
    migrations.add_missing_columns(eng)
    migrations.create_missing_indexes(eng)
    Session = sessionmaker(bind=eng)
    session = Session()
    session.add(models_db.User(username="a", hashed_password="h", phone_e164="+8613800138000"))
    session.commit()
    session.add(models_db.User(username="b", hashed_password="h", phone_e164="+8613800138000"))
    with pytest.raises(IntegrityError, match="phone_e164"):
        session.commit()
    session.rollback()
    session.close()


def test_migrated_old_db_and_fresh_db_agree_on_users(tmp_path):
    """F2 的真判据：**新建库与迁移旧库必须得到同一个结构**。

    2026-09-07 先在今天的 `models_db`（还没有 phone 列）上验过这条前提成立：
    两条路的列集合与唯一列集合都相等（`{('username',), ('uuid',)}`），
    所以这条测试红起来只可能是 phone 那两列/那条索引的问题。
    """
    fresh = inspect(_fresh_engine(tmp_path, "fresh"))
    old = _legacy_users_db(tmp_path, "old2")
    migrations.add_missing_columns(old)
    migrations.create_missing_indexes(old)
    migrated = inspect(old)

    assert {c["name"] for c in migrated.get_columns("users")} == {
        c["name"] for c in fresh.get_columns("users")
    }
    assert _unique_column_sets(migrated, "users") == _unique_column_sets(fresh, "users")
