"""`ai_ladder_game_ledger` 的不可变性,由**数据库**强制,不靠调用方自觉。

本模块是象棋/国象/五子棋共用的 `ranked_api/envelope/immutability.py` 在围棋侧的对应物,
**连同它的两条硬教训一起搬过来**(见下面两段 🔴)。围棋的账本住在自己的库里
(`KATRAIN_DATABASE_URL`,不是 lobby 的 `ranked` schema),所以不能直接复用那个模块;
但「只追加,不修改,不删除」这条属性必须由同一种机构来执行。

在这之前,围棋的 `AiLadderGameLedger` docstring 写着 "Append-only",而**没有任何东西在
执行它** —— 一条写在散文里、没有执行机构的属性,等于没有这条属性。这正是三家在
2026-08-13 那一轮拆掉的形状,围棋是最后一个。

## 为什么是触发器,不是 CHECK

CHECK 守的是**取值合法性**,不是**不可变性**。象棋 2026-08-10 在 SQLite 上实测过
(不是推演):`UPDATE ... SET rating_after=9999.0` 通过全部 CHECK、成功落库、读回来
就是 9999.0;`DELETE` 更是一路畅通。围棋这张表的 `ck_ai_ladder_ledger_decision` 同理 ——
它拦得住一行**不自洽**的改动,拦不住一行**自洽但是伪造**的改动。

## 为什么 DDL 只有这一份

围棋有两条建表路径,两条都得装上:

- `Base.metadata.create_all`(`auth.py:105/115/155`)—— 全新库与漂移重建
- 已部署库的增量迁移(`migrations.add_missing_columns` 那一条链)

两处抄两份 DDL,迟早有一份忘了改,而那种漏改在 SQLite 上**测试全绿**(触发器只是没装,
UPDATE 直接成功)。所以 DDL 只有这一份,两条路径都调 `install`。

⚠️ **PostgreSQL 那一支的验收必须真的在 PostgreSQL 上跑。在 SQLite 上绿不作数** ——
两个方言是两套语句,漏改哪一套,另一套照样绿。这条与三家同源:
`reference_sqlite_weaker_than_production`。

## 调用顺序有一条硬约束

`migrations.backfill_ai_ladder_decisions` 会对本表发 `UPDATE`(把旧 schema 的行标回
counted)。**它必须在装触发器之前跑完。** 今天成立是因为 `auth.py` 里 backfill 在
install 之前,而且 backfill 幂等 —— 第二次启动时它匹配 0 行,`FOR EACH ROW` 触发器
一次都不会烧。**将来任何需要改动存量账本行的迁移,都必须 `drop` → 迁移 → `install`,
不能指望绕过去。** `drop_statements` 就是为这个留的,不是给测试开后门用的。
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

TABLE = "ai_ladder_game_ledger"
IMMUTABLE_MESSAGE = "ai ladder ledger is immutable"

_FN = "reject_ai_ladder_ledger_mutation"
_TRG_UPDATE = "trg_ai_ladder_ledger_no_update"
_TRG_DELETE = "trg_ai_ladder_ledger_no_delete"


# 🔴 SQLite 这一支**不能**写成 `CREATE TRIGGER IF NOT EXISTS`,那是**按名字跳过、
# 不看内容**的。名字没变而内容变了 ⇒ 这条语句一行都不执行,长命的库里留着**旧**的
# 触发器体,而全新建的库(测试用的正是全新库)拿到的是**新**的。两边从此分叉,
# 且没有任何东西会红 —— 测试全绿,生产悄悄用着旧规则。
#
# 通则:幂等 DDL 若以「这个对象已存在」为跳过条件,它对**内容**变更无效。
# 要么改内容时同时改名字,要么先删后建。这里与 PG 同形:先 DROP 再 CREATE。
#
# ⚠️ 本仓 `migrations.py:242` 的终局审计触发器至今仍是 `CREATE TRIGGER IF NOT EXISTS`,
#    是同一个坑的另一处实例。它不在本次改动范围内,但别照抄它。
def install_statements(dialect_name: str) -> tuple[str, ...]:
    """两条触发器的 DDL。方言不认识就抛 —— 静默跳过等于账本没人守。"""
    if dialect_name == "sqlite":
        return (
            f'DROP TRIGGER IF EXISTS "{_TRG_UPDATE}"',
            f'CREATE TRIGGER "{_TRG_UPDATE}" BEFORE UPDATE ON "{TABLE}" '
            f"BEGIN SELECT RAISE(ABORT, '{IMMUTABLE_MESSAGE}'); END",
            f'DROP TRIGGER IF EXISTS "{_TRG_DELETE}"',
            f'CREATE TRIGGER "{_TRG_DELETE}" BEFORE DELETE ON "{TABLE}" '
            f"BEGIN SELECT RAISE(ABORT, '{IMMUTABLE_MESSAGE}'); END",
        )
    if dialect_name == "postgresql":
        return (
            f"CREATE OR REPLACE FUNCTION {_FN}() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '{IMMUTABLE_MESSAGE}'; END; $$ LANGUAGE plpgsql",
            f'DROP TRIGGER IF EXISTS "{_TRG_UPDATE}" ON "{TABLE}"',
            f'CREATE TRIGGER "{_TRG_UPDATE}" BEFORE UPDATE ON "{TABLE}" ' f"FOR EACH ROW EXECUTE FUNCTION {_FN}()",
            f'DROP TRIGGER IF EXISTS "{_TRG_DELETE}" ON "{TABLE}"',
            f'CREATE TRIGGER "{_TRG_DELETE}" BEFORE DELETE ON "{TABLE}" ' f"FOR EACH ROW EXECUTE FUNCTION {_FN}()",
        )
    raise RuntimeError(f"unsupported ai ladder ledger dialect: {dialect_name}")


def drop_statements(dialect_name: str) -> tuple[str, ...]:
    """卸掉触发器。**只给「必须改动存量账本行」的迁移用**,用完必须重新 install。"""
    if dialect_name == "sqlite":
        return (
            f'DROP TRIGGER IF EXISTS "{_TRG_UPDATE}"',
            f'DROP TRIGGER IF EXISTS "{_TRG_DELETE}"',
        )
    if dialect_name == "postgresql":
        return (
            f'DROP TRIGGER IF EXISTS "{_TRG_UPDATE}" ON "{TABLE}"',
            f'DROP TRIGGER IF EXISTS "{_TRG_DELETE}" ON "{TABLE}"',
        )
    raise RuntimeError(f"unsupported ai ladder ledger dialect: {dialect_name}")


def install(engine) -> None:
    """在账本表上装(或重装)不可变触发器。表不存在时是 no-op。

    幂等靠的是 DROP-then-CREATE,不是 `IF NOT EXISTS` —— 见模块顶部那段 🔴。
    """
    if TABLE not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        for statement in install_statements(engine.dialect.name):
            conn.execute(text(statement))
    logger.info("migrate: installed append-only triggers on %s", TABLE)
