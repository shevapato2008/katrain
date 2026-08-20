"""围棋账本与三家共享 `ranked.ledgers` 的契约级对齐(2026-08-14)。

象棋 / 国象 / 五子棋在 2026-08-13 收敛到共用的 `ranked.ledgers` 信封,围棋的账本住在
自己的库里(`KATRAIN_DATABASE_URL`),表名也不同,所以搬不过去 —— 但**属性必须一致**。
本文件钉的是三条此前只写在散文里、没有任何执行机构的属性:

1. **只追加**(`ledger_immutability`)—— 此前 `AiLadderGameLedger` 的 docstring 写着
   "Append-only",而库里没有任何东西在执行它。
2. **`none_as_null`** —— 没有它,Python `None` 以 JSON 字面量 `'null'` 落库,
   `IS NOT NULL` 判它有值。
3. **`account_subject` 长度** —— 三家有 `ck_ranked_ledgers_account_subject_len`,围棋没有。

⚠️ **这三条的 PostgreSQL 一侧在这里证不了。** 触发器与 CHECK 在两个方言下是两套语句,
漏改哪一套另一套照样绿(`reference_sqlite_weaker_than_production`)。本文件用 SQLite,
只能证 SQLite 那一套 + 语句生成函数的形状;PG 的验收另算,见每条测试的注释。
"""

import json

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import ledger_immutability, migrations, models_db


LEDGER = "ai_ladder_game_ledger"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    migrations.enforce_ai_ladder_account_subject_schema(engine)
    ledger_immutability.install(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine, sessions


def _user(session, username="u1"):
    user = models_db.User(username=username, hashed_password="x")
    session.add(user)
    session.commit()
    return user


def _ledger_row(user_id, **overrides):
    row = dict(
        game_id="g-1",
        user_id=user_id,
        user_color="B",
        result="win",
        game_type="ai_ladder_ranked",
        counted=False,
        reason="unreserved",
    )
    row.update(overrides)
    return models_db.AiLadderGameLedger(**row)


# ── 1. 只追加 ───────────────────────────────────────────────────────────────────


def test_a_settled_row_cannot_be_updated(db):
    """改一行已落库的账 —— 库必须拒绝。

    这条是三家 `envelope/immutability.py` 的围棋对应物。象棋 2026-08-10 在 SQLite 上
    实测过:`UPDATE ... SET rating_after=9999.0` 通过全部 CHECK、成功落库、读回来就是
    9999.0 —— **CHECK 守的是取值合法性,不是不可变性**,顶不上这一条。
    """
    engine, sessions = db
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id))
        session.commit()
    finally:
        session.close()

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE {LEDGER} SET counted = TRUE, reason = NULL WHERE game_id = 'g-1'"))
    assert ledger_immutability.IMMUTABLE_MESSAGE in str(excinfo.value)

    with engine.connect() as conn:
        counted = conn.execute(text(f"SELECT counted FROM {LEDGER} WHERE game_id = 'g-1'")).scalar()
    assert not counted, "改动被拒之后,那一行必须还是原样"


def test_a_settled_row_cannot_be_deleted(db):
    """删一行已落库的账 —— 库必须拒绝。删比改更彻底,单独钉。"""
    engine, sessions = db
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id))
        session.commit()
    finally:
        session.close()

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {LEDGER} WHERE game_id = 'g-1'"))
    assert ledger_immutability.IMMUTABLE_MESSAGE in str(excinfo.value)

    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {LEDGER}")).scalar_one() == 1


def test_appending_a_new_row_still_works(db):
    """只追加 = 追加还得能用。反向守卫:别把触发器写成「谁都不许动这张表」。"""
    engine, sessions = db
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id, game_id="g-1"))
        session.commit()
        session.add(_ledger_row(user.id, game_id="g-2"))
        session.commit()
    finally:
        session.close()
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {LEDGER}")).scalar_one() == 2


def test_install_is_idempotent_and_replaces_rather_than_skips(db):
    """重复安装不炸,而且走的是 DROP-then-CREATE 而非 `IF NOT EXISTS`。

    后半句是判据所在:`CREATE TRIGGER IF NOT EXISTS` **按名字跳过、不看内容** ——
    名字没变而内容变了就一行都不执行,长命的库留着旧规则、新建的库拿新规则,
    两边分叉且两边都绿。这里直接对语句串断言,因为那个缺陷的现象恰恰是「什么都没发生」,
    行为测试看不见它。
    """
    engine, _ = db
    ledger_immutability.install(engine)  # 第二次
    statements = ledger_immutability.install_statements("sqlite")
    assert not any("IF NOT EXISTS" in s and s.startswith("CREATE") for s in statements)
    assert sum(1 for s in statements if s.startswith("DROP TRIGGER")) == 2
    # PG 一侧在 SQLite 上跑不了,但语句形状可以在这里钉住。
    pg = ledger_immutability.install_statements("postgresql")
    assert sum(1 for s in pg if s.startswith("DROP TRIGGER")) == 2
    assert any("CREATE OR REPLACE FUNCTION" in s for s in pg)


def test_an_unknown_dialect_raises_instead_of_skipping(db):
    """方言不认识就抛。静默跳过 = 账本没人守,而且没有任何东西会红。"""
    with pytest.raises(RuntimeError):
        ledger_immutability.install_statements("mysql")


# ── 2. none_as_null ─────────────────────────────────────────────────────────────


def test_a_python_none_snapshot_lands_as_sql_null_not_the_string_null(db):
    """`opponent_config_snapshot = None` 必须落成 SQL NULL,不是 JSON 字面量 `'null'`。

    没有 `none_as_null=True` 时它落成 `'null'`,于是
    `ck_ai_ladder_ledger_decision` 里那句 `opponent_config_snapshot IS NOT NULL`
    **对一个空快照判真** —— 闸开着,而且看不出来。

    今天围棋走不到那一格(真正的判据是 `counted = reason is None` 加
    `AiLadderOpponentSnapshot.__post_init__`),所以这条守的是**潜伏缺陷**;
    钉住它是为了与三家共享账本 (`ranked_api/envelope/models_db.py:66`) 一致。
    """
    engine, sessions = db
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id, opponent_config_snapshot=None))
        session.commit()
    finally:
        session.close()

    with engine.connect() as conn:
        is_null = conn.execute(
            text(f"SELECT opponent_config_snapshot IS NULL FROM {LEDGER} WHERE game_id = 'g-1'")
        ).scalar()
        raw = conn.execute(text(f"SELECT opponent_config_snapshot FROM {LEDGER} WHERE game_id = 'g-1'")).scalar()
    assert is_null, "Python None 必须是 SQL NULL —— 否则 IS NOT NULL 判它有值"
    assert raw is None
    assert raw != "null", "落成 JSON 字面量 'null' 正是这条要防的"


def test_a_real_snapshot_still_round_trips(db):
    """反向守卫:别为了 none_as_null 把真快照也弄丢。"""
    engine, sessions = db
    snapshot = {"rung": 7, "net": "b18", "visits": 64}
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id, opponent_config_snapshot=snapshot))
        session.commit()
    finally:
        session.close()
    with engine.connect() as conn:
        raw = conn.execute(text(f"SELECT opponent_config_snapshot FROM {LEDGER} WHERE game_id = 'g-1'")).scalar()
    assert json.loads(raw) == snapshot


# ── 3. account_subject 长度 ─────────────────────────────────────────────────────


def test_the_schema_rejects_an_over_long_account_subject(db):
    """> 32 位的主体必须被库拒掉。

    与三家的 `ck_ranked_ledgers_account_subject_len` 同源。**这条挡的正是
    36 位带横杠的 `str(uuid4())`** —— 那个格式在冻结件 §4 里是被禁的,而铸造侧
    (`users.uuid`)至今没有任何 schema 约束,只靠一个 default lambda。
    """
    engine, sessions = db
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id, account_subject="0" * 33))
        with pytest.raises(Exception):
            session.commit()
    finally:
        session.rollback()
        session.close()

    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {LEDGER}")).scalar_one() == 0


def test_the_schema_rejects_an_empty_account_subject(db):
    """空字符串主体必须被拒 —— **这一格是这条约束在 PostgreSQL 上唯一承重的地方**。

    上界在 PG 上其实由列类型 `String(32)` → `varchar(32)` 就挡住了(2026-08-14 在真 PG
    上实测,33 位报的是 `StringDataRightTruncation`,不是 CheckViolation)。**所以只测
    超长,证不出这条 CHECK 在 PG 上有用。** 下界不一样:`varchar(32)` 对空串照单全收,
    拦住它的确实是 `ck_ai_ladder_ledger_account_subject_len`(真 PG 上按 `diag.constraint_name`
    核过)。

    SQLite 这边两个界都归它 —— SQLite 根本不执行 `VARCHAR(n)` 的长度。
    """
    engine, sessions = db
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id, account_subject=""))
        with pytest.raises(Exception):
            session.commit()
    finally:
        session.rollback()
        session.close()
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {LEDGER}")).scalar_one() == 0


def test_a_32_hex_subject_and_a_null_subject_both_pass(db):
    """32 位合规;NULL 也合规 —— 本列诞生前写下的行是 NULL,不能追认。"""
    engine, sessions = db
    session = sessions()
    try:
        user = _user(session)
        session.add(_ledger_row(user.id, game_id="g-ok", account_subject="a" * 32))
        session.add(_ledger_row(user.id, game_id="g-legacy", account_subject=None))
        session.commit()
    finally:
        session.close()
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {LEDGER}")).scalar_one() == 2


def test_a_fresh_table_declares_the_constraint_not_just_a_trigger(db):
    """全新建的表要靠模型里的 CHECK,不是靠迁移补的触发器。

    两条建表路径(`create_all` 与增量迁移)必须给出同一条属性 —— 只在一处装,
    另一条路径建出来的库就是没有守卫的,而测试用的恰恰常常是前者。
    """
    engine, _ = db
    checks = {c.get("name") for c in inspect(engine).get_check_constraints(LEDGER)}
    assert "ck_ai_ladder_ledger_account_subject_len" in checks


def test_the_migration_path_is_a_no_op_when_the_constraint_already_exists(db):
    """已经有约束时,迁移不该再发一遍 DDL。"""
    assert (
        migrations.postgres_ai_ladder_account_subject_statements(
            existing_checks={"ck_ai_ladder_ledger_account_subject_len"}
        )
        == []
    )
    statements = migrations.postgres_ai_ladder_account_subject_statements(existing_checks=set())
    assert len(statements) == 1 and "ADD CONSTRAINT" in statements[0]
