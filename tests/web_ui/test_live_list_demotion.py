"""直播列表：已经不在上游「正在直播」名单里的对局，必须被降级。

2026-08-24 的现场：上游 `api.19x19.com/api/engine/golives/all` 回
`{"code":"0","msg":"","data":[]}`（**HTTP 200，0 场直播**），而生产页面同时显示
**49 场「正在直播」**，其中好几条已经 300+ 手。原因有两层，本文件两层都守：

1. `FetchListJob` 在 `if not all_rows: return` 处提前退出 —— 上游返回空是一个
   **真答复**，却被当成「没拿到数据」，整轮更新（包括降级）被跳过。
2. 更根本的是 `SourceRegistry.fetch_all_matches()` 只返回一个扁平列表：
   **抓取失败**和**上游确实没有直播**在返回值里长得一模一样。任何降级逻辑建在
   这个返回值上，要么不敢降（就是线上这个样子），要么一遇到上游抖动就把整张
   直播列表清空。所以先让 registry 把「这家答没答」这一位显式带出来，
   再谈降级。

对应的判据：**判别位必须是抓取流程写进去的状态位（`live_ids_by_source` 里有没有
这个 key），不能是「这家没有行」这条消息的缺席。**
"""

import asyncio
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.cron.clients.registry import SourceRegistry
from katrain.cron.db import Base
from katrain.cron.jobs.fetch_list import FetchListJob
from katrain.cron.models import LiveMatchDB


def _row(match_id: str, source: str, status: str = "live", move_count: int = 0) -> dict:
    return {
        "match_id": match_id,
        "source": source,
        "match_date": None,
        "source_id": match_id,
        "tournament": f"测试杯 {match_id}",
        "player_black": f"黑{match_id}",
        "player_white": f"白{match_id}",
        "status": status,
        "result": None,
        "move_count": move_count,
        "moves": None,
        "current_winrate": 0.5,
        "current_score": 0.0,
    }


class _FakeClient:
    """live_rows=None 表示这一家**抓取失败**（抛异常），不是「没有直播」。"""

    def __init__(self, source: str, live_rows: list[dict] | None):
        self.source = source
        self._live_rows = live_rows

    async def get_live_matches(self) -> list[dict]:
        if self._live_rows is None:
            raise RuntimeError(f"{self.source} upstream unreachable")
        return self._live_rows

    def parse_match_to_row(self, raw: dict) -> dict:
        return raw


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[LiveMatchDB.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _seed(session, *specs):
    for match_id, source, status in specs:
        session.add(LiveMatchDB(**_row(match_id, source, status=status)))
    session.commit()


def _run_job(session, clients: dict[str, list[dict] | None]):
    """跑一轮 FetchListJob，registry 用假客户端，DB 用调用方给的 session。"""
    registry = SourceRegistry()
    for source, live_rows in clients.items():
        registry.register(source, _FakeClient(source, live_rows))

    job = FetchListJob()
    with (
        patch.object(FetchListJob, "_build_registry", staticmethod(lambda: registry)),
        patch("katrain.cron.jobs.fetch_list.SessionLocal", lambda: session),
        patch.object(session, "close", lambda: None),
    ):
        asyncio.run(job.run())
    session.expire_all()


def _status(session, match_id: str) -> str:
    return session.query(LiveMatchDB).filter(LiveMatchDB.match_id == match_id).one().status


# ── registry 层：那一位在不在 ────────────────────────────────────────────


def test_registry_reports_an_empty_answer_as_an_answer():
    """上游成功返回 0 场直播 ⇒ key 在，集合为空。这是「现在没有直播」。"""
    registry = SourceRegistry()
    registry.register("xingzhen", _FakeClient("xingzhen", []))

    rows, live_by_source = asyncio.run(registry.fetch_all_matches_with_liveness())

    assert rows == []
    assert "xingzhen" in live_by_source, "空答复被当成没答复了"
    assert live_by_source["xingzhen"] == set()


def test_registry_omits_a_source_that_failed():
    """抓取失败 ⇒ key 不在。下游据此不许对这家做任何推断。"""
    registry = SourceRegistry()
    registry.register("xingzhen", _FakeClient("xingzhen", None))

    rows, live_by_source = asyncio.run(registry.fetch_all_matches_with_liveness())

    assert rows == []
    assert "xingzhen" not in live_by_source, "失败和空答复没有区分开 —— 这正是原来的 bug"


def test_registry_keeps_the_two_sources_independent():
    registry = SourceRegistry()
    registry.register("xingzhen", _FakeClient("xingzhen", None))
    registry.register("yike", _FakeClient("yike", [_row("y1", "yike")]))

    _, live_by_source = asyncio.run(registry.fetch_all_matches_with_liveness())

    assert set(live_by_source) == {"yike"}
    assert live_by_source["yike"] == {"y1"}


# ── job 层：降级 ────────────────────────────────────────────────────────


def test_a_match_the_source_no_longer_lists_is_marked_finished(db_session):
    _seed(db_session, ("x1", "xingzhen", "live"), ("x2", "xingzhen", "live"))

    _run_job(db_session, {"xingzhen": [_row("x1", "xingzhen")]})

    assert _status(db_session, "x1") == "live"
    assert _status(db_session, "x2") == "finished", "上游不再列出它，却还挂在正在直播"


def test_an_empty_but_successful_answer_still_demotes(db_session):
    """线上那一幕：上游 200 + `data: []`，页面却还是 49 场「正在直播」。

    这条用例专守被删掉的那个 `if not all_rows: return` —— 把它加回去，本例转红。
    """
    _seed(db_session, ("x1", "xingzhen", "live"), ("x2", "xingzhen", "live"))

    _run_job(db_session, {"xingzhen": []})

    assert _status(db_session, "x1") == "finished"
    assert _status(db_session, "x2") == "finished"


def test_a_failed_source_demotes_nothing(db_session):
    """抓不到 ≠ 没在下。这条要是红了，一次上游抖动就会清空整张直播列表。"""
    _seed(db_session, ("x1", "xingzhen", "live"), ("x2", "xingzhen", "live"))

    _run_job(db_session, {"xingzhen": None})

    assert _status(db_session, "x1") == "live"
    assert _status(db_session, "x2") == "live"


def test_one_source_failing_does_not_demote_the_other_source(db_session):
    _seed(db_session, ("x1", "xingzhen", "live"), ("y1", "yike", "live"))

    _run_job(db_session, {"xingzhen": None, "yike": []})

    assert _status(db_session, "x1") == "live", "星阵失败，不该影响星阵自己的对局"
    assert _status(db_session, "y1") == "finished", "弈客明确答了 0 场，该降级"


def test_a_match_that_comes_back_is_live_again(db_session):
    """上游抖一下（200 但漏了一条）之后能自愈：下一轮列出来就恢复 live。"""
    _seed(db_session, ("x1", "xingzhen", "live"))

    _run_job(db_session, {"xingzhen": []})
    assert _status(db_session, "x1") == "finished"

    _run_job(db_session, {"xingzhen": [_row("x1", "xingzhen")]})
    assert _status(db_session, "x1") == "live"


def test_already_finished_matches_are_left_alone(db_session):
    """降级只碰 status=='live' 的行，不去重复写已经结束的。"""
    _seed(db_session, ("x1", "xingzhen", "finished"))

    _run_job(db_session, {"xingzhen": []})

    assert _status(db_session, "x1") == "finished"


def test_an_undeletable_duplicate_does_not_roll_back_the_whole_round(db_session):
    """去重要删的旧行删不掉时，这一轮（含降级）必须照样落库。

    测试机实测：dedup 那句 `db.delete(dup)` 撞上
    ``live_analysis_match_id_fkey``（旧行还被分析表引用），错误在 `db.commit()`
    才炸，于是**整轮回滚** —— 降级明明算对了、日志也打了 "demoted N"，
    写进去的东西又被撤销，接口读出来还是老样子。
    这条守的就是「一条删不掉的重复行不许连累这一轮」。

    SQLite 默认不强制外键（见 reference：SQLite 比生产弱的那一族），
    所以这里不去复现 FK 本身，而是直接让 delete 抛错 —— 断言对象是
    **失败之后这一轮还算不算数**，那一点两个库上一致。
    """
    _seed(db_session, ("y_dup", "yike", "live"), ("x_other", "xingzhen", "live"))
    # 让 y_dup 和新来的 xingzhen 行是同一对棋手，才会走到 dedup 的删除分支
    dup_row = db_session.query(LiveMatchDB).filter(LiveMatchDB.match_id == "y_dup").one()
    dup_row.player_black, dup_row.player_white = "黑x_new", "白x_new"
    db_session.commit()

    original_delete = db_session.delete

    def _boom(obj):
        raise RuntimeError("FK: still referenced from live_analysis")

    db_session.delete = _boom
    try:
        _run_job(db_session, {"xingzhen": [_row("x_new", "xingzhen")]})
    finally:
        db_session.delete = original_delete

    # 这一轮没白跑：x_other 不在本轮 live 名单里，该降的降了
    assert _status(db_session, "x_other") == "finished", "一条删不掉的重复行把整轮降级连累回滚了"
    # 删不掉的那条原样留着，没有被半删成脏数据
    assert _status(db_session, "y_dup") == "live"
