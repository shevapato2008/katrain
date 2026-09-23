"""近一年练棋日历(G4):每天下完几局、首次解出几道题。

**一格 = 当天下完的对局 + 当天新解出的题**(Fan 2026-09-22)。按**客户端时区**切天 ——
按 UTC 切,北京早上 8 点前下的棋会落到前一天,「今天」那格明明下过却是空的。

「下完的对局」只认自己下的三种来源(白名单):导入的谱、棋谱库、研究局都不是你下的。

端点和 `growth/summary` 同形:盒上先问云端,拿不到退本机并如实标 `local_cache`。
四种退回原因在共用的 `_cloud_first` 里,`test_growth_authority.py` 已逐条断言;这里只验本端点的
标签与路径接对了(404 那条日志里要出现 `/growth/activity`)。
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.growth_activity import GrowthActivityRepository

NOW = datetime(2026, 9, 22, 4, 0, tzinfo=timezone.utc)  # 北京 9-22 中午
BEIJING = 480


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'a.db'}")
    models_db.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


_seq = iter(range(1, 10_000))


def _game(factory, at, *, source="play_ai", user_id=1):
    s = factory()
    s.add(
        models_db.UserGame(id=f"g{next(_seq)}", user_id=user_id, sgf_content="(;GM[1])", source=source, created_at=at)
    )
    s.commit()
    s.close()


def _solve(factory, at, *, completed=True, user_id=1):
    s = factory()
    s.add(
        models_db.UserTsumegoProgress(
            user_id=user_id,
            problem_id=f"p{next(_seq)}",
            completed=completed,
            attempts=1,
            first_completed_at=at if completed else None,
        )
    )
    s.commit()
    s.close()


def _daily(factory, *, days=365, tz_offset=BEIJING):
    return GrowthActivityRepository(factory).daily(1, days=days, tz_offset=tz_offset, now=NOW)


def test_days_are_cut_in_the_clients_timezone(factory):
    _game(factory, datetime(2026, 9, 21, 23, 0, tzinfo=timezone.utc))  # 北京 9-22 早上 7 点
    assert _daily(factory) == [{"date": "2026-09-22", "games": 1, "solved": 0}]
    assert _daily(factory, tz_offset=0) == [{"date": "2026-09-21", "games": 1, "solved": 0}]


def test_only_games_you_played_count(factory):
    for source in ("play_ai", "play_local", "play_human", "import", "kifu_library", "research"):
        _game(factory, NOW - timedelta(hours=1), source=source)
    assert _daily(factory) == [{"date": "2026-09-22", "games": 3, "solved": 0}]


def test_solved_counts_first_solves_and_shares_the_day_with_games(factory):
    at = NOW - timedelta(hours=1)
    _game(factory, at)
    _solve(factory, at)
    _solve(factory, at, completed=False)  # 做过没解出
    _solve(factory, at, user_id=2)  # 别人的
    assert _daily(factory) == [{"date": "2026-09-22", "games": 1, "solved": 1}]


def test_window_edges_in_the_clients_timezone_and_only_active_days(factory):
    """窗口 = 北京的今天往前数 365 天(含今天)⇒ 首日是北京 2025-09-23。
    首日凌晨 2 点那局(= UTC 前一天 18:00)必须在内 —— `since` 进 SQL 前没换成 UTC 的话,
    SQLite 按字面时间比,这一局会被比掉。"""
    _game(factory, datetime(2025, 9, 22, 15, 0, tzinfo=timezone.utc))  # 北京 2025-09-22 23:00,窗口外
    _game(factory, datetime(2025, 9, 22, 18, 0, tzinfo=timezone.utc))  # 北京 2025-09-23 02:00,首日
    _game(factory, NOW - timedelta(days=3))
    assert _daily(factory) == [
        {"date": "2025-09-23", "games": 1, "solved": 0},
        {"date": "2026-09-19", "games": 1, "solved": 0},
    ]


# ── 端点 ──


class _FakeConnectivity:
    def __init__(self, online):
        self.is_online = online


class _FakeRemoteClient:
    def __init__(self, *, payload=None, raises=None):
        self._payload, self._raises, self.calls = payload, raises, []

    async def get_growth_activity(self, days, tz_offset):
        self.calls.append((days, tz_offset))
        if self._raises is not None:
            raise self._raises
        return self._payload


def _client(factory, *, remote=None, online=True):
    from katrain.web.api.v1.endpoints.auth import get_current_user
    from katrain.web.api.v1.endpoints.growth import router
    from katrain.web.core.repository import RepositoryDispatcher
    from katrain.web.models import User

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/growth")
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="me")
    app.state.growth_activity_repo = GrowthActivityRepository(factory)
    if remote is not None:
        app.state.repository_dispatcher = RepositoryDispatcher(
            connectivity_manager=_FakeConnectivity(online),
            remote_tsumego=None,
            remote_kifu=None,
            remote_user_games=None,
            local_user_game_repo=None,
            remote_client=remote,
        )
    return TestClient(app)


CLOUD = {"window_days": 365, "days": [{"date": "2026-09-20", "games": 4, "solved": 2}], "authority": "this_node"}
URL = "/api/v1/growth/activity?days=365&tz_offset=480"


def test_this_node_answers_the_contract(factory):
    _game(factory, datetime.now(timezone.utc) - timedelta(minutes=5))
    body = _client(factory).get(URL).json()
    assert (body["window_days"], body["authority"]) == (365, "this_node")
    assert [(d["games"], d["solved"]) for d in body["days"]] == [(1, 0)]


def test_bad_params_are_422(factory):
    client = _client(factory)
    for query in ("days=0", "days=366", "tz_offset=-721", "tz_offset=841"):
        assert client.get(f"/api/v1/growth/activity?{query}").status_code == 422, query


def test_box_online_takes_the_clouds_answer_and_says_cloud(factory):
    remote = _FakeRemoteClient(payload=dict(CLOUD))
    body = _client(factory, remote=remote).get(URL).json()
    assert remote.calls == [(365, 480)]  # 时区原样带给云端:云端按盒子的「今天」切天
    assert body["days"] == CLOUD["days"]
    assert body["authority"] == "cloud"


def test_box_falls_back_to_local_cache_when_the_cloud_lacks_the_endpoint(factory, caplog):
    request = httpx.Request("GET", "https://cloud.example/api/v1/growth/activity")
    missing = httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))
    _game(factory, datetime.now(timezone.utc) - timedelta(minutes=5))
    with caplog.at_level(logging.INFO):
        body = _client(factory, remote=_FakeRemoteClient(raises=missing)).get(URL).json()
    assert body["authority"] == "local_cache"
    assert [d["games"] for d in body["days"]] == [1]
    assert "no /growth/activity" in caplog.text


def test_box_offline_does_not_ask_and_bad_cloud_shape_falls_back(factory, caplog):
    remote = _FakeRemoteClient(payload=dict(CLOUD))
    assert _client(factory, remote=remote, online=False).get(URL).json()["authority"] == "local_cache"
    assert remote.calls == []

    bad = _FakeRemoteClient(payload={"window_days": 365, "days": "nope"})
    with caplog.at_level(logging.INFO):
        assert _client(factory, remote=bad).get(URL).json()["authority"] == "local_cache"
    assert "unrecognised shape" in caplog.text
