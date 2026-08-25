"""棋谱库列表的两条性能修复的闸。

生产 151,197 行、堆 247MB。2026-08-24 用 EXPLAIN ANALYZE 量到两处，各修一处：

1. **COUNT 里带着 ORDER BY**。`Query.count()` 把**带排序的**查询整个套进子查询，
   ORDER BY 活了下来 ⇒ COUNT 也要外部归并排序落盘 3712kB。557ms → 27ms。
   守它的是 `test_count_statement_carries_no_order_by`（变异：把 `total`
   改回 `query.count()`，该用例转红——已实跑验证）。

2. **排序没有能用的索引**（`create_kifu_album_sort_index`）。这一条的**效果**
   只能在 PostgreSQL 上证，见本文件末尾的 skip 说明；这里守的是它的**副作用边界**：
   它不能把 SQLite 启动搞挂。

判据都选在「能被这个测试自己造出来的状态」上，不是 EXPLAIN 里的毫秒数——
毫秒数在别的机器上不可复现，只记录在 docstring 与 runbook 里。
"""

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core import migrations, models_db


def _sqlite_engine():
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})


@pytest.fixture
def db_with_albums():
    """三条棋谱：两条有 date_sort、一条为 NULL（NULLS LAST 那一支要被走到）。"""
    engine = _sqlite_engine()
    models_db.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add_all(
        [
            models_db.KifuAlbum(
                player_black="丁浩",
                player_white="杨楷文",
                date_sort="2026-01-29",
                sgf_content="(;B[pd])",
                source_path="/fixtures/a.sgf",
                search_text="丁浩 杨楷文 2026",
                move_count=252,
            ),
            models_db.KifuAlbum(
                player_black="李钦诚",
                player_white="丁浩",
                date_sort="2026-01-30",
                sgf_content="(;B[dp])",
                source_path="/fixtures/b.sgf",
                search_text="李钦诚 丁浩 2026",
                move_count=166,
            ),
            models_db.KifuAlbum(
                player_black="范胤",
                player_white="王星昊",
                date_sort=None,
                sgf_content="(;B[qq])",
                source_path="/fixtures/c.sgf",
                search_text="范胤 王星昊",
                move_count=132,
            ),
        ]
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _request_without_dispatcher():
    """没有 repository_dispatcher 的最小 Request 替身（走本机 DB 分支）。"""
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))


def _list_albums(session, **kwargs):
    params = {"q": None, "page": 1, "page_size": 20}
    params.update(kwargs)
    return asyncio.run(kifu.list_kifu_albums(request=_request_without_dispatcher(), db=session, **params))


def _capture_sql(session):
    seen = []
    event.listen(session.bind, "before_cursor_execute", lambda *a: seen.append(a[2]))
    return seen


def test_count_statement_carries_no_order_by(db_with_albums):
    """COUNT 那条语句里不许出现 ORDER BY —— 它是这次修复的全部内容。

    断言对象选的是**发出去的 SQL**，不是耗时：耗时在 SQLite 上根本量不出差别
    （三行数据），而 ORDER BY 在不在是同一个代码路径的直接结果，两个库上一致。
    """
    seen = _capture_sql(db_with_albums)
    _list_albums(db_with_albums)

    counts = [s for s in seen if "count(" in s.lower()]
    assert counts, f"没发出 COUNT 语句，实际发出：{seen}"
    for statement in counts:
        assert "order by" not in statement.lower(), f"COUNT 又带上排序了：{statement}"


def test_count_and_page_stay_consistent_without_query(db_with_albums):
    result = _list_albums(db_with_albums)
    assert result.total == 3
    assert len(result.items) == 3


def test_count_respects_the_same_filter_as_the_page(db_with_albums):
    """拆成两条查询之后最容易坏的地方：过滤条件只加在其中一条上。"""
    result = _list_albums(db_with_albums, q="丁浩")
    assert result.total == 2, "COUNT 没跟着过滤 —— 分页会多出空白页"
    assert len(result.items) == 2
    assert {item.player_black for item in result.items} == {"丁浩", "李钦诚"}


def test_count_is_zero_when_nothing_matches(db_with_albums):
    result = _list_albums(db_with_albums, q="不存在的棋手")
    assert result.total == 0
    assert result.items == []


def test_ordering_puts_null_date_last(db_with_albums):
    """NULLS LAST 那一支：date_sort 为空的那条排最后，不是最前。"""
    result = _list_albums(db_with_albums)
    assert [item.player_black for item in result.items] == ["李钦诚", "丁浩", "范胤"]


def test_page_two_does_not_repeat_page_one(db_with_albums):
    first = _list_albums(db_with_albums, page=1, page_size=2)
    second = _list_albums(db_with_albums, page=2, page_size=2)
    assert first.total == second.total == 3
    assert {item.id for item in first.items}.isdisjoint({item.id for item in second.items})


def test_sort_index_is_a_no_op_on_sqlite():
    """`DESC NULLS LAST` 在 SQLite 的 CREATE INDEX 里是语法错误。

    实测（sqlite 3.51）：``CREATE INDEX a ON kifu_albums (date_sort DESC NULLS LAST, id DESC)``
    → ``OperationalError: unsupported use of NULLS LAST``。所以这条索引只能是
    PostgreSQL 专属；本用例守的是「它在 SQLite 上安静地什么都不做」。
    """
    engine = _sqlite_engine()
    models_db.Base.metadata.create_all(bind=engine)

    migrations.create_kifu_album_sort_index(engine)  # 不许抛

    names = {ix["name"] for ix in inspect(engine).get_indexes("kifu_albums")}
    assert migrations.KIFU_SORT_INDEX not in names
    engine.dispose()


def test_create_missing_indexes_survives_sqlite():
    """真正的护栏：谁把这条索引挪进 ``__table_args__``，这里就会红。

    `create_missing_indexes` 对所有方言照单建模型声明的索引，而 SQLAlchemy 对
    SQLite 也会渲染出 ``NULLS LAST``。变异验证：把
    ``Index(KIFU_SORT_INDEX, KifuAlbum.date_sort.desc().nullslast(), KifuAlbum.id.desc())``
    加进 `KifuAlbum.__table_args__`，本用例转红（OperationalError）——已实跑验证。
    """
    engine = _sqlite_engine()
    models_db.Base.metadata.create_all(bind=engine)

    migrations.create_missing_indexes(engine)  # 不许抛

    engine.dispose()


@pytest.mark.skip(
    reason="索引的**效果**只能在 PostgreSQL 上证：SQLite 既不接受 DESC NULLS LAST 的 "
    "CREATE INDEX，也没有 EXPLAIN (ANALYZE, BUFFERS)。2026-08-24 在与生产同数据的 "
    "PG 测试库上实测：取页 364ms→0.13ms（9 buffers vs 31,707）、COUNT 557ms→25ms、"
    "端到端接口 1.30s→0.18s。不许在 SQLite 上改成绿的。"
)
def test_planner_uses_the_sort_index_on_postgres():
    raise AssertionError("PostgreSQL only")
