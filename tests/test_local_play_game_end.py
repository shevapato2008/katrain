"""本地对局 v2 · 终局契约（spec §3.2 认输、§3.4 双 pass 与数子）。

全部走真 `WebKaTrain` + 真 HTTP。落账由 `app.state.user_game_repo` 的 MagicMock 观察：
server 模式的 lifespan 不设 `repository_dispatcher`，`_record_ai_game` 于是走
`app.state.user_game_repo.create(user_id=..., **data)`。

**盒上模式靠 `session.katrain.suppress_auto_eval = True` 模拟**：生产里它由
`settings.KATRAIN_MODE == "board"` 在 `WebKaTrain.__init__` 设（interface.py），
这里建完会话再直接设，免得改进程级 settings。

**`save_config` 必须打桩**：`manager.create_session` 建的 `WebKaTrain` 是
`force_package_config=False`，`/api/game/setup`、`/api/new-game` 里的 `update_config`
会把 `~/.katrain/config.json` 改掉（2026-09-14 实测：跑一次 `test_guest_free_play.py`
就把开发机的 komi/rules 改了）。
"""

# Warm up the real kivy/kivymd Window singleton on the MAIN thread before any
# TestClient request runs — same reason as tests/test_local_play_setup.py: kivymd's
# first import from Starlette's background portal thread creates a real SDL2/Cocoa
# window off the main thread and aborts the process on macOS.
import kivymd.app  # noqa: F401

import types
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.server import create_app

OWNER = types.SimpleNamespace(id=7, username="owner", uuid="u-7")
STRANGER = types.SimpleNamespace(id=999, username="stranger", uuid="u-999")
HUMAN = {"name": "", "player_type": "player:human", "player_subtype": "player:human"}


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    # 必须在进 `TestClient` **之前**设：lifespan 会用它建全部 repo 并跑 `init_db()`。
    app.state.session_factory = isolated_session_factory
    with TestClient(app) as c:
        c.app.state.user_game_repo = MagicMock()
        c.app.state.repository_dispatcher = None
        c.app.dependency_overrides[get_current_user_optional] = lambda: OWNER
        yield c
        c.app.dependency_overrides.clear()
        # 会话是进程级的，不收掉会连同引擎活到本次 pytest 结束（见 test_guest_free_play.py）。
        for session in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(session.session_id)


def _owned_game(client, monkeypatch, *, game_type, board_mode, size=19, base=100, user_id=OWNER.id):
    """建一个归 OWNER 的会话并开局。两边都坐人：有 AI 座位会起 genmove 后台线程，活得比用例长。"""
    session = client.app.state.session_manager.create_session(user_id=user_id)
    monkeypatch.setattr(session.katrain, "save_config", lambda *a, **k: None)
    session.katrain.suppress_auto_eval = board_mode
    sid = session.session_id
    if game_type == "pvp_local":
        r = client.post(
            "/api/game/setup",
            json={
                "session_id": sid,
                "mode": "pvp_local",
                "settings": {
                    "board_size": size,
                    "rules": "chinese",
                    "handicap": 0,
                    "komi": 7.5,
                    "black_name": "",
                    "white_name": "",
                    "time_enabled": False,
                },
            },
        )
    else:
        r = client.post(
            "/api/new-game",
            json={
                "session_id": sid,
                "size": size,
                "rules": "chinese",
                "komi": 7.5,
                "players": {"B": HUMAN, "W": HUMAN},
            },
        )
    assert r.status_code == 200, r.text
    # 显式钉住门槛基数：开发机 ~/.katrain/config.json 里真有 count_min_moves=10。
    session.katrain.update_config("game/count_min_moves", base)
    return session


def _move(client, sid, coords=None):
    r = client.post("/api/move", json={"session_id": sid, "coords": coords, "pass_move": coords is None})
    assert r.status_code == 200, r.text
    return r.json()["state"]


def _recorded_results(client):
    return [call.kwargs["result"] for call in client.app.state.user_game_repo.create.call_args_list]


# ------------------------------------------------------------------ 状态位与门槛下发（§3.4）


@pytest.mark.parametrize("game_type", ["pvp_local", "free"])
def test_board_mode_double_pass_sets_awaiting_count(client, monkeypatch, game_type):
    session = _owned_game(client, monkeypatch, game_type=game_type, board_mode=True)
    _move(client, session.session_id, [3, 3])
    first = _move(client, session.session_id)
    assert first["awaiting_count"] is False  # 只停了一手

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is True
    assert state["end_result"]  # 回落串「终局」照样非空 —— 前端必须以 awaiting_count 为准


def test_galaxy_double_pass_never_sets_awaiting_count(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is False


@pytest.mark.parametrize("size, expected", [(19, 100), (13, 47), (9, 22)])
def test_state_count_min_moves_scales_with_board_size(client, monkeypatch, size, expected):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True, size=size, base=100)

    state = session.katrain.get_state()

    assert state["board_size"] == [size, size]
    assert state["count_min_moves"] == expected


# ------------------------------------------------------------------ 认输（§3.2）


@pytest.mark.parametrize(
    "stones, color, expected",
    [
        ([], "W", "B+R"),  # 开局即认输：今天会判「落最后一手的一方」胜 = W+R
        ([[3, 3]], "B", "W+R"),  # 黑下一手后黑认输：今天会判 B+R
    ],
)
def test_local_resign_scores_the_named_side(client, monkeypatch, stones, color, expected):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True)
    for coords in stones:
        _move(client, session.session_id, coords)

    r = client.post("/api/resign", json={"session_id": session.session_id, "color": color})

    assert r.status_code == 200, r.text
    assert r.json()["state"]["end_result"] == expected
    assert _recorded_results(client) == [expected]


def test_local_resign_without_color_is_rejected_before_mutation(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True)
    _move(client, session.session_id, [3, 3])

    r = client.post("/api/resign", json={"session_id": session.session_id})

    assert r.status_code == 400, r.text
    assert session.katrain.game.current_node.end_state is None
    assert _recorded_results(client) == []


def test_free_resign_with_color_is_rejected(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=True)
    _move(client, session.session_id, [3, 3])

    r = client.post("/api/resign", json={"session_id": session.session_id, "color": "B"})

    assert r.status_code == 400, r.text
    assert session.katrain.game.current_node.end_state is None


def test_free_resign_without_color_is_unchanged(client, monkeypatch):
    """正对照：其它模式不带 color，行为与今天一致（落最后一手的一方胜）。"""
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False)
    _move(client, session.session_id, [3, 3])

    r = client.post("/api/resign", json={"session_id": session.session_id})

    assert r.status_code == 200, r.text
    assert r.json()["state"]["end_result"] == "B+R"
    assert _recorded_results(client) == ["B+R"]


# ------------------------------------------------------------------ 双 pass 落账钩子（§3.4、P4、§7-3）


@pytest.mark.parametrize("game_type", ["pvp_local", "free"])
def test_board_mode_double_pass_records_nothing(client, monkeypatch, game_type):
    """P4：盒上不自动分析，end_result 此刻只是回落串「终局」；落账就是一条没有胜负的记录。"""
    session = _owned_game(client, monkeypatch, game_type=game_type, board_mode=True)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is True
    assert _recorded_results(client) == []


def test_timeout_during_awaiting_count_does_not_record_and_count_still_can(client, monkeypatch):
    """F2：等数子期间 end_result 是回落串「终局」，不是真实结果 —— /api/timeout 不能把它当成
    「已判过」而放行落账，之后数子成功也必须还能正常落账（不是已经被 `_recorded` 卡死）。
    """
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True, base=100)
    sid = session.session_id
    _move(client, sid, [3, 3])
    _move(client, sid)
    state = _move(client, sid)
    assert state["awaiting_count"] is True

    r = client.post("/api/timeout", json={"session_id": sid})

    assert r.status_code == 200, r.text
    assert r.json()["state"]["awaiting_count"] is True
    assert _recorded_results(client) == []  # 没有落账「终局」这个无胜负占位符

    session.katrain.game.current_node.analysis["root"] = {"scoreLead": 3.2, "winrate": 0.6, "visits": 10}
    count_r = client.post("/api/count/request", json={"session_id": sid})

    assert count_r.status_code == 200, count_r.text
    assert _recorded_results(client) == ["B+3.2"]  # 数子结果照样能存进去


def test_galaxy_double_pass_records_exactly_as_today(client, monkeypatch):
    """spec §7-3：galaxy（非盒上模式）双 pass 的落账与今天逐字一致 —— 仍是没有胜负的回落串。

    这条在改动前后都必须绿：它钉的是「不变」，不是新行为。
    """
    from katrain.core.lang import i18n

    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is False
    assert state["end_result"] == i18n._("board-game-end")
    assert _recorded_results(client) == [state["end_result"]]


def test_board_mode_scoring_game_type_double_pass_records_as_today(client, monkeypatch):
    """反作弊类型(rated / ranked / ai_ladder_ranked)不进 awaiting_count，盒上也照旧落账。

    这里直接改 `game_type` 模拟，不走真的 rated 开局（那条要引擎与段位配置）；
    判定本身的类型排除已由 tests/test_game_end_rules.py 逐个类型钉住。
    """
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=True)
    session.katrain.game_type = "rated"
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is False
    assert _recorded_results(client) == [state["end_result"]]


# ------------------------------------------------------------------ /api/count/request（§3.4、P6、P7、P18）


def test_count_threshold_scales_on_9x9_and_reports_codes(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=False, size=9, base=100)
    sid = session.session_id
    for i in range(10):  # 黑落子、白停一手，交替 10 轮：20 手 + 根节点 = 21；从不连续两手 pass
        _move(client, sid, [i % 9, i // 9])
        _move(client, sid)
    assert len(session.katrain.get_state()["history"]) == 21

    below = client.post("/api/count/request", json={"session_id": sid})
    assert below.status_code == 400, below.text
    assert below.json()["detail"] == {"code": "below_min_moves", "message": "Cannot count before 22 moves"}

    _move(client, sid, [1, 1])  # 第 22 个节点，过门槛；没有分析
    pending = client.post("/api/count/request", json={"session_id": sid})
    assert pending.status_code == 400, pending.text
    assert pending.json()["detail"]["code"] == "analysis_pending"


def test_count_on_a_finished_galaxy_game_reports_game_over(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False, base=1)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)
    _move(client, session.session_id)

    r = client.post("/api/count/request", json={"session_id": session.session_id})

    assert r.status_code == 400, r.text
    assert r.json()["detail"] == {"code": "game_over", "message": "Game is already over"}


def test_board_mode_double_pass_counts_without_threshold_once_analysis_arrives(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True, base=100)
    sid = session.session_id
    _move(client, sid, [3, 3])
    _move(client, sid)
    _move(client, sid)  # history = 4，远低于 100

    pending = client.post("/api/count/request", json={"session_id": sid})
    assert pending.status_code == 400, pending.text
    assert pending.json()["detail"]["code"] == "analysis_pending"  # 绕过了门槛，卡在分析上

    # 分析回来（生产里是前端 analyzeCurrent 触发的那一份）。此刻 game.manual_score 已非空，
    # end_result 变成 "黑+3.0?" 这种估计串 —— awaiting_count 必须仍为真，否则下面会被判「已终局」。
    session.katrain.game.current_node.analysis["root"] = {"scoreLead": 3.2, "winrate": 0.6, "visits": 10}
    assert session.katrain.game.manual_score is not None
    assert session.katrain.get_state()["awaiting_count"] is True

    r = client.post("/api/count/request", json={"session_id": sid})

    assert r.status_code == 200, r.text
    assert r.json()["result"] == "B+3.2"
    assert r.json()["state"]["end_result"] == "B+3.2"
    assert r.json()["state"]["awaiting_count"] is False
    assert _recorded_results(client) == ["B+3.2"]


def test_free_game_ended_by_a_pass_outside_api_move_is_recordable(client, monkeypatch):
    """spec §3.4 待核实那一条。

    AI 的着手不经 `/api/move`：`WebKaTrain._do_ai_move`（后台线程）→ `katrain/core/ai.py`
    `generate_ai_move` → `game.play(move)`，之后 `_do_ai_move_and_broadcast` 的 finally 只调
    `update_state()`。所以「人先停、AI 再停」收尾的局，`/api/move` 的钩子从来走不到，也没有别的
    落账路径。这里不真起 AI（NullEngine 下 genmove 线程会挂住并活过用例），而是照那条线程的
    做法直接 `game.play` + `update_state()`。
    """
    from katrain.core.game import Move

    session = _owned_game(client, monkeypatch, game_type="free", board_mode=True, base=100)
    sid = session.session_id
    _move(client, sid, [3, 3])
    _move(client, sid)  # 人（白）停一手
    with session.lock:  # 「AI」（黑）停一手，走的是 genmove 线程那条路
        session.katrain.game.play(Move(None, player=session.katrain.game.current_node.next_player))
    session.katrain.update_state()
    assert _recorded_results(client) == []  # 今天到这里为止就是没落账
    assert session.katrain.get_state()["awaiting_count"] is True

    session.katrain.game.current_node.analysis["root"] = {"scoreLead": -4.5, "winrate": 0.3, "visits": 10}
    r = client.post("/api/count/request", json={"session_id": sid})

    assert r.status_code == 200, r.text
    assert _recorded_results(client) == ["W+4.5"]


def test_count_is_restricted_to_the_owner(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=False)
    sid = session.session_id

    client.app.dependency_overrides[get_current_user_optional] = lambda: STRANGER
    assert client.post("/api/count/request", json={"session_id": sid}).status_code == 403
    client.app.dependency_overrides[get_current_user_optional] = lambda: None
    assert client.post("/api/count/request", json={"session_id": sid}).status_code == 401
    assert session.katrain.game.current_node.end_state is None

    # 正对照：主人本人打得到端点本身（被门槛挡，不是被归属闸挡）。
    client.app.dependency_overrides[get_current_user_optional] = lambda: OWNER
    owner = client.post("/api/count/request", json={"session_id": sid})
    assert owner.status_code == 400, owner.text
    assert owner.json()["detail"]["code"] == "below_min_moves"


def test_count_on_an_unclaimed_session_needs_no_login(client, monkeypatch):
    """无人认领（游客开的）会话不设闸 —— 与认输、超时同一口径。"""
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False, user_id=None)
    client.app.dependency_overrides[get_current_user_optional] = lambda: None

    r = client.post("/api/count/request", json={"session_id": session.session_id})

    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "below_min_moves"
