"""跨局能力诊断(G1):最近几份已完成报告里,**你执的那一方**的手,按布局 / 中盘 / 官子数问题手。

**分母只算「本用户执的那一方 + 已评级」的手。** `grade` 为空或 `unrated` 的手是「不知道」,
不是「没问题」—— 算进分母,失误率会被稀释成一个看着很好的假数。

**同一局只算一次。** 一局可能跑过好几份报告(重跑、不同档位),按「份」数会把同一局的手
重复计入,样本量也跟着虚高 ⇒ 每局只取最新那份已完成的。

盒子上报告在云端、本机库里没有逐手数据 ⇒ 端点和 `growth/summary` 同形:先问云端,
拿不到退本机并如实标 `local_cache`,四种退回原因各写各的日志。
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
from katrain.web.core.growth_diagnosis import bucket
from katrain.web.core.report_diagnosis_repo import ReportDiagnosisRepository

SINCE = datetime.now(timezone.utc) - timedelta(days=90)


# ── 分桶(纯函数)──


def test_bucket_splits_by_the_same_phases_as_the_report_screen():
    # 阶段边界取 move_grade.yaml:布局 0-59 / 中盘 60-149 / 官子 150-
    got = bucket(
        [
            {"move_number": 10, "grade": "best"},
            {"move_number": 59, "grade": "mistake"},  # 布局 · 问题手
            {"move_number": 60, "grade": "inaccuracy"},  # 中盘 · 问题手(小亏也算)
            {"move_number": 150, "grade": "playable"},  # 官子
            {"move_number": 200, "grade": "blunder"},  # 官子 · 问题手
        ]
    )
    assert got["graded"] == 5
    assert got["phases"]["opening"] == {"graded": 2, "bad": 1}
    assert got["phases"]["midgame"] == {"graded": 1, "bad": 1}
    assert got["phases"]["endgame"] == {"graded": 2, "bad": 1}


def test_bucket_leaves_unrated_and_missing_grades_out_of_the_denominator():
    got = bucket(
        [
            {"move_number": 10, "grade": None},
            {"move_number": 11, "grade": "unrated"},
            {"move_number": 12, "grade": ""},
            {"move_number": 13, "grade": "blunder"},
        ]
    )
    assert got["graded"] == 1
    assert got["phases"]["opening"] == {"graded": 1, "bad": 1}


# ── 取数 ──


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'d.db'}")
    models_db.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


_seq = iter(range(1, 10_000))


def _seed(factory, *, user_id=1, user_color="B", status="completed", moves=(), game_id=None):
    """一局 + 一份报告 + 逐手评级。`moves` 是 `(手数, 落子方, 评级)`。"""
    n = next(_seq)
    s = factory()
    game_id = game_id or f"g{n}"
    if s.get(models_db.UserGame, game_id) is None:
        s.add(
            models_db.UserGame(
                id=game_id, user_id=user_id, sgf_content=f"(;GM[1]C[{n}])", source="play_ai", user_color=user_color
            )
        )
        s.flush()
    task = models_db.ReportTask(user_id=user_id, user_game_id=game_id, status=status)
    s.add(task)
    s.flush()
    for mv, player, grade in moves:
        s.add(models_db.ReportTaskMove(task_id=task.id, move_number=mv, actual_player=player, grade=grade))
    s.commit()
    task_id = task.id
    s.close()
    return game_id, task_id


def _pick(factory, user_id=1, max_reports=20):
    return ReportDiagnosisRepository(factory).recent_graded_moves(user_id, since=SINCE, max_reports=max_reports)


def test_only_the_users_own_moves_count(factory):
    _seed(factory, user_color="B", moves=[(10, "B", "mistake"), (11, "W", "blunder")])
    _seed(factory, user_id=2, user_color="B", moves=[(10, "B", "mistake")])  # 别人的报告
    got = _pick(factory)
    assert got["reports"] == 1
    assert [m["move_number"] for m in got["moves"]] == [10]  # 对手那手不算


def test_a_report_whose_game_has_no_seat_is_skipped_whole_and_reported(factory):
    """执色没记的局**整份跳过并报出来**,不拿两边的手混在一起算。"""
    _seed(factory, user_color=None, moves=[(10, "B", "mistake")])
    got = _pick(factory)
    assert (got["reports"], got["skipped_without_color"], got["moves"]) == (0, 1, [])


def test_unfinished_reports_do_not_count(factory):
    _seed(factory, status="running", moves=[(10, "B", "mistake")])
    assert _pick(factory)["reports"] == 0


def test_one_game_counts_once_even_with_two_finished_reports(factory):
    game_id, _ = _seed(factory, moves=[(10, "B", "mistake")])
    _seed(factory, game_id=game_id, moves=[(10, "B", "best"), (12, "B", "best")])  # 同一局重跑,较新
    got = _pick(factory)
    assert got["reports"] == 1
    assert [(m["move_number"], m["grade"]) for m in got["moves"]] == [(10, "best"), (12, "best")]


def test_max_reports_takes_the_newest(factory):
    for _ in range(3):
        _seed(factory, moves=[(10, "B", "best")])
    assert _pick(factory, max_reports=2)["reports"] == 2


def test_historic_ranked_game_reads_the_seat_from_the_ledger(factory):
    game_id, _ = _seed(factory, user_color=None, moves=[(10, "W", "mistake"), (11, "B", "best")])
    s = factory()
    s.add(
        models_db.AiLadderGameLedger(
            game_id=game_id,
            user_id=1,
            user_color="W",
            result="loss",
            game_type="ai_ladder_ranked",
            opponent_rung=18,
            opponent_rank_name="3级",
            opponent_config_snapshot={"recipe": "fixture"},
            opponent_certification_status="certified",
            opponent_availability="available",
            opponent_route="local",
            counted=True,
            reason=None,
        )
    )
    s.commit()
    s.close()
    got = _pick(factory)
    assert got["reports"] == 1
    assert [m["move_number"] for m in got["moves"]] == [10]


# ── 端点 ──


class _FakeConnectivity:
    def __init__(self, online):
        self.is_online = online


class _FakeRemoteClient:
    def __init__(self, *, payload=None, raises=None):
        self._payload, self._raises, self.calls = payload, raises, []

    async def get_growth_diagnosis(self, days, reports):
        self.calls.append((days, reports))
        if self._raises is not None:
            raise self._raises
        return self._payload


def _http_error(status):
    request = httpx.Request("GET", "https://cloud.example/api/v1/growth/diagnosis")
    return httpx.HTTPStatusError(str(status), request=request, response=httpx.Response(status, request=request))


def _client(factory, *, remote=None, online=True):
    from katrain.web.api.v1.endpoints.auth import get_current_user
    from katrain.web.api.v1.endpoints.growth import router
    from katrain.web.core.repository import RepositoryDispatcher
    from katrain.web.models import User

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/growth")
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="me")
    app.state.report_diagnosis_repo = ReportDiagnosisRepository(factory)
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


CLOUD = {
    "window_days": 90,
    "reports": 6,
    "skipped_without_color": 0,
    "graded_moves": 420,
    "phases": [{"phase": "midgame", "graded": 200, "bad": 60}],
    "authority": "this_node",
}


def test_this_node_answers_three_phases_with_the_sample_size(factory):
    _seed(factory, moves=[(10, "B", "mistake"), (70, "B", "best"), (71, "W", "blunder")])
    body = _client(factory).get("/api/v1/growth/diagnosis").json()
    assert body["authority"] == "this_node"
    assert (body["reports"], body["graded_moves"], body["skipped_without_color"]) == (1, 2, 0)
    # 只列有评过级的手的那几段 —— 官子一手没有就不列,不摆一个 0/0。
    assert body["phases"] == [
        {"phase": "opening", "graded": 1, "bad": 1},
        {"phase": "midgame", "graded": 1, "bad": 0},
    ]


def test_no_reports_is_zero_not_404_and_not_three_zero_phases(factory):
    resp = _client(factory).get("/api/v1/growth/diagnosis")
    assert resp.status_code == 200
    body = resp.json()
    assert (body["reports"], body["graded_moves"], body["phases"]) == (0, 0, [])


def test_bad_params_are_422(factory):
    client = _client(factory)
    assert client.get("/api/v1/growth/diagnosis?days=0").status_code == 422
    assert client.get("/api/v1/growth/diagnosis?reports=51").status_code == 422


def test_box_online_takes_the_clouds_answer_and_says_cloud(factory):
    remote = _FakeRemoteClient(payload=dict(CLOUD))
    body = _client(factory, remote=remote).get("/api/v1/growth/diagnosis?days=30&reports=5").json()
    assert remote.calls == [(30, 5)]
    assert body["reports"] == 6
    # 云端自己答的是 this_node;在盒子的回答里那句话不成立。
    assert body["authority"] == "cloud"


@pytest.mark.parametrize(
    "raises,needle",
    [
        (httpx.ConnectError("no route"), "cloud unreachable"),
        (_http_error(404), "no /growth/diagnosis"),
        (_http_error(503), "cloud failed with 503"),
        (_http_error(401), "cloud refused with 401"),
    ],
    ids=["不可达", "云端少这个端点", "云端 5xx", "云端拒绝"],
)
def test_box_falls_back_to_local_cache_and_logs_why(factory, caplog, raises, needle):
    with caplog.at_level(logging.INFO):
        body = _client(factory, remote=_FakeRemoteClient(raises=raises)).get("/api/v1/growth/diagnosis").json()
    assert body["authority"] == "local_cache"
    assert body["reports"] == 0  # 盒上本机库里没有报告 —— 屏上据此说「读不到云端的报告」
    assert needle in caplog.text


def test_box_offline_does_not_ask_the_cloud(factory):
    remote = _FakeRemoteClient(payload=dict(CLOUD))
    body = _client(factory, remote=remote, online=False).get("/api/v1/growth/diagnosis").json()
    assert remote.calls == []
    assert body["authority"] == "local_cache"


def test_cloud_answering_200_with_the_wrong_shape_falls_back(factory, caplog):
    remote = _FakeRemoteClient(payload={"reports": 3})
    with caplog.at_level(logging.INFO):
        body = _client(factory, remote=remote).get("/api/v1/growth/diagnosis").json()
    assert body["authority"] == "local_cache"
    assert "unrecognised shape" in caplog.text
