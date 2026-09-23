"""`user_games.user_color` —— 这个用户坐哪一方(G2)。

**算得出就写,算不出就 NULL。** 拿玩家名去猜(`player_black == username`?)就是在编:
名字可能重、可能空、面对面那一局根本没有「你」这一方。

这一列要走完**整条路**才算数,所以这里按路段各钉一条:
  · 落账:人机局 = 唯一的人类座位;面对面 = NULL;平台引擎局 = 引擎的另一边(`human_color`)。
  · 盒子 → 云端:盒子上的局是 POST 云端 `/api/v1/user-games/` 写进去的。那个端点的请求模型
    若没有这一列,pydantic 会**静默丢掉**它 —— 不报错,云端那行永远是 NULL。
  · 云端建升降级对局行:执色取自预约记录(`row.user_color`,权威),不依赖盒子传不传。
  · 胜率:历史升降级局在这一列诞生之前写下,是 NULL;但账本(`ai_ladder_game_ledger`)里
    **早就记着**执色 —— 读它不是追认,是读一个已经记下的事实。其余历史行不回填。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db
from katrain.web.core.user_game_repo import UserGameRepository


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    models_db.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def repo(factory):
    return UserGameRepository(factory)


# ── 列 ──


def test_new_database_has_the_column(factory):
    cols = {c["name"]: c for c in inspect(factory.kw["bind"]).get_columns("user_games")}
    assert "user_color" in cols
    # 必须可空:非空列会让 `add_missing_columns` 补一个 `''` 默认值,而 `''` 会被读成「记过执色」。
    assert cols["user_color"]["nullable"] is True


def test_add_missing_columns_adds_it_to_an_older_database(tmp_path):
    """老库(建表时还没有这一列)跑一次迁移就该有。仓里没有 alembic,加列只走这条幂等链路。"""
    engine = create_engine(f"sqlite:///{tmp_path/'old.db'}")
    models_db.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_games DROP COLUMN user_color"))
    assert "user_color" not in {c["name"] for c in inspect(engine).get_columns("user_games")}

    migrations.add_missing_columns(engine)

    cols = {c["name"]: c for c in inspect(engine).get_columns("user_games")}
    assert "user_color" in cols
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO user_games (id, user_id, source) VALUES ('old', 1, 'import')"))
        # 没有默认值:老行不会被补成 `''` 冒充「记过」。
        assert conn.execute(text("SELECT user_color FROM user_games WHERE id='old'")).scalar() is None


# ── 仓储 ──


def test_create_round_trips_user_color(repo):
    row = repo.create(user_id=1, sgf_content="(;GM[1])", source="play_ai", user_color="W")
    assert row["user_color"] == "W"


def test_create_without_user_color_is_null_not_guessed(repo):
    row = repo.create(user_id=1, sgf_content="(;GM[1]B[aa])", source="import", player_black="me")
    assert row["user_color"] is None


def test_ranked_retry_is_not_judged_tampering_because_of_the_new_column(repo, factory):
    """这一列诞生之前写下的权威局是 NULL,重试时传进来的却是 'B' ——
    `user_color` 若进了 `immutable_fields`,一次正常重试会被判成「权威局被篡改」。"""
    game = dict(sgf_content="(;GM[1])", result="B+R", player_black="me", player_white="AI")
    repo.create_ai_ladder_ranked(user_id=1, game_id="ranked-1", game_type="ai_ladder_ranked", **game)
    s = factory()
    s.execute(text("UPDATE user_games SET user_color = NULL WHERE id = 'ranked-1'"))
    s.commit()
    s.close()

    again = repo.create_ai_ladder_ranked(
        user_id=1, game_id="ranked-1", game_type="ai_ladder_ranked", user_color="B", **game
    )
    assert again["id"] == "ranked-1"


# ── 落账:这一局里「这个用户」坐哪一方 ──


class _Info:
    def __init__(self, human):
        self.human = human
        self.ai = not human
        self.name = ""
        self.calculated_rank = None
        self.sgf_rank = None


@pytest.mark.parametrize(
    "seats,game_type,expected",
    [
        ({"B": True, "W": False}, "free", "B"),  # 人执黑跟 AI 下
        ({"B": False, "W": True}, "free", "W"),
        ({"B": True, "W": True}, "pvp_local", None),  # 面对面:没有「你」这一方
        ({"B": True, "W": True}, "free", None),  # 两边都是人却不是 pvp_local:照样不挑
        ({"B": False, "W": False}, "free", None),  # 两边都不是人(平台引擎局在这里是这样):不猜
    ],
)
def test_user_seat(seats, game_type, expected):
    from katrain.web.server import _user_seat

    assert _user_seat({bw: _Info(h) for bw, h in seats.items()}, game_type) == expected


def _session(seats, game_type):
    session = SimpleNamespace(
        _recorded=False,
        game_type=game_type,
        katrain=SimpleNamespace(
            get_sgf=lambda: "(;GM[1])",
            get_state=lambda: {"board_size": [19, 19], "history": [1, 2], "komi": 7.5, "ruleset": "chinese"},
            players_info={bw: _Info(h) for bw, h in seats.items()},
        ),
    )
    return session


@pytest.mark.parametrize(
    "seats,game_type,expected",
    [({"B": False, "W": True}, "free", "W"), ({"B": True, "W": True}, "pvp_local", None)],
    ids=["人机局写人坐的那一方", "面对面写 NULL"],
)
async def test_the_real_record_fn_writes_the_seat_into_the_row(seats, game_type, expected):
    import katrain.web.server as server

    server.create_app(enable_engine=False)  # `_RECORD_FN` 是 create_app 里挂出来的
    created = []

    async def user_games_create(*, user_id, data):
        created.append(data)
        return {"id": "g1"}

    app = SimpleNamespace(
        state=SimpleNamespace(repository_dispatcher=SimpleNamespace(user_games_create=user_games_create))
    )
    await server._RECORD_FN(_session(seats, game_type), app, SimpleNamespace(id=7, username="me"), "W+R")

    assert created and created[0]["user_color"] == expected


# ── 盒子 → 云端:接收端点不许把这一列丢掉 ──


def _user_games_client(repo):
    from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
    from katrain.web.api.v1.endpoints.user_games import router
    from katrain.web.models import User

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/user-games")
    user = User(id=1, username="me")
    app.dependency_overrides[require_writable_user] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user
    app.state.user_game_repo = repo
    return TestClient(app)


def test_cloud_endpoint_keeps_the_seat_the_box_sent(repo):
    resp = _user_games_client(repo).post(
        "/api/v1/user-games/", json={"sgf_content": "(;GM[1])", "source": "play_ai", "user_color": "W"}
    )
    assert resp.status_code == 200, resp.text
    assert repo.get(resp.json()["id"], 1)["user_color"] == "W"


def test_cloud_endpoint_rejects_a_seat_that_is_not_b_or_w(repo):
    resp = _user_games_client(repo).post(
        "/api/v1/user-games/", json={"sgf_content": "(;GM[1])", "source": "play_ai", "user_color": "black"}
    )
    assert resp.status_code == 422


# ── 云端建升降级对局行:执色取自预约记录 ──


def test_cloud_ranked_row_takes_the_seat_from_the_reservation(factory):
    from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository

    row = SimpleNamespace(game_id="rk-1", user_id=1, origin_device_id="box-1", user_color="W")
    record = {
        "sgf_content": "(;GM[1])",
        "result": "B+R",
        "board_size": 19,
        "rules": "chinese",
        "komi": 7.5,
        "move_count": 0,
        "player_black": "AI",
        "player_white": "me",
    }
    s = factory()
    AiLadderRankedRepository._create_or_validate_user_game(s, row=row, record=record)
    s.commit()
    assert s.get(models_db.UserGame, "rk-1").user_color == "W"
    s.close()


# ── summary 用的「算得出胜负的局」 ──

SINCE = datetime.now(timezone.utc) - timedelta(days=30)


def test_decided_since_counts_only_rows_with_a_seat_and_a_winner(repo):
    repo.create(user_id=1, sgf_content="a", source="play_ai", user_color="B", result="B+R")  # 赢
    repo.create(user_id=1, sgf_content="b", source="play_ai", user_color="W", result="B+3.5")  # 输
    repo.create(user_id=1, sgf_content="c", source="play_local", result="W+R")  # 没执色:不算
    repo.create(user_id=1, sgf_content="d", source="play_ai", user_color="B", result="Void")  # 判不出胜负:不算
    repo.create(user_id=1, sgf_content="e", source="play_ai", user_color="W", result="0")  # 和棋:不算
    repo.create(user_id=2, sgf_content="f", source="play_ai", user_color="B", result="B+R")  # 别人的
    assert repo.decided_since(1, since=SINCE) == {"decided": 2, "wins": 1, "losses": 1}


def test_decided_and_total_have_different_denominators(repo):
    """`games_in_window` 数的是**下了多少局**,`decided` 数的是**算得出胜负的局**。
    两个口径不同,屏上那句「有 N 局没算进胜率」就是它们的差。"""
    repo.create(user_id=1, sgf_content="a", source="play_ai", user_color="B", result="B+R")
    repo.create(user_id=1, sgf_content="b", source="play_local", result="W+R")
    assert repo.count_since(1, since=SINCE) == 2
    assert repo.decided_since(1, since=SINCE)["decided"] == 1


def test_historic_ranked_games_read_the_seat_the_ledger_already_recorded(repo, factory):
    """这一列上线之前的升降级局在 `user_games` 里是 NULL,但账本早就记着执色。
    不读账本的话,部署当天只下升降级的人,胜率会从有数变成「—」,最长持续 30 天。"""
    repo.create_ai_ladder_ranked(
        user_id=1, game_id="old-ranked", game_type="ai_ladder_ranked", sgf_content="(;GM[1])", result="W+R"
    )
    s = factory()
    s.execute(text("UPDATE user_games SET user_color = NULL WHERE id = 'old-ranked'"))
    s.add(
        models_db.AiLadderGameLedger(
            game_id="old-ranked",
            user_id=1,
            user_color="W",
            result="win",
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

    assert repo.decided_since(1, since=SINCE) == {"decided": 1, "wins": 1, "losses": 0}
