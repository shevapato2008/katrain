# 本地对弈 (kiosk-local-play) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让两个人面对面在同一台 kiosk 智能棋盘（或触屏兜底）上完成一整局围棋，终局自动存谱并同步远程，可在「对局历史」里回看并一键 AI 复盘。

**Architecture:** 复用既有对局主页面 `GamePage`（已支持人人对弈 `aiColor===null` 分支）与视觉落子注入主干（`_vision_move_poller` 按 `player_to_move` 通用归属）。新增量集中在：①后端 `pvp_local` 建局分支（双方 human）②存谱统一走 `RepositoryDispatcher`（在线→远程/离线→本地+补传，顺带修复 HvAI 存谱 local-only 的 bug）③自然终局（双 pass）也存谱 ④前端建局页 / 对局历史页 / 一键复盘。

**Tech Stack:** FastAPI + SQLAlchemy（后端）、React + TypeScript + Vite + MUI（kiosk 前端）、pytest（后端测试）、vitest + Testing Library（前端测试）。

## Global Constraints

- **SBC 构建边界契约**：本轨道只碰**共享区**（`src/api/`、`src/components/`、`src/hooks/`、`src/context/`、`src/utils/`、`src/types/`）+ `src/kiosk/**`。`src/kiosk/**` 文件**禁止** import `src/galaxy/**`、`src/components/Board3D/**`、`src/pages/VideoRecorderPage*`（`eslint.config.js` 强制）。**禁止** 引入 `three` / `@react-three/*`。
- **改动共享文件（`src/api/`、`src/hooks/`、`src/components/Board.tsx` 等）须两套构建都过**：`npm run build` **且** `npm run build:kiosk-2d`（后者自动链 `verify:kiosk-2d`，任何 `three`/`@react-three` 泄漏即 exit≠0）。
- **i18n**：所有静态串用 `t('English key', '中文默认')`（kiosk 默认语言 cn，见既有 kiosk 页）。非中文设备翻译需 `katrain-i18n-expert` 技能把 msgid 写进 `katrain/i18n/locales/*/LC_MESSAGES/katrain.po`（见 Task 9）。**禁止日文**，默认中文。
- **语言**：面向中文用户；文案默认中文。
- **`source` 词表**：`UserGameCreate.source` 是自由 `str`（`user_games.py:19` 注释 `play_ai / play_human / import / research`）。本轨道本地对弈用 **`play_local`**（区别于在线 HvH 的 `play_human`）。
- **远程 `data` 严格性**：走 dispatcher 在线创建时，body 会按 `UserGameCreate` 校验，**多余字段 422**。`data` 只能含 `UserGameCreate` 字段；`board_size` 必须 int；**`user_id` 不进 `data`**（远程从 token 推导、本地/离线路径单独传 `user_id`）。
- **测试命令**：后端 `CI=true uv run pytest tests/<file> -v`；前端 `cd katrain/web/ui && npx vitest run <path>`。
- **提交**：每个 Task 结束一次 commit，message 用 `feat(local-play): ...` / `fix(local-play): ...`。

---

## File Structure

**后端（`katrain/web/`）**
- `server.py` — `game_setup` 新增 `pvp_local` 分支；`_record_ai_game` 改 async + 走 dispatcher + 动态 source；`request_count`/`_complete_count`/`timeout`/`resign` 改造为「锁内计分、锁外 await 存谱」；`play_move` 增自然终局存谱钩子。
- `models.py` — **无改动**（`GameSettingsRequest.settings` 是自由 dict）。
- `tests/test_local_play_setup.py`（新）— `pvp_local` 建局双 human。
- `tests/test_local_play_recording.py`（新）— 存谱走 dispatcher（在线/离线两路）+ `play_local` source + 自然终局存谱 + 不重复存谱。

**前端（`katrain/web/ui/src/`）**
- `api/userGamesApi.ts`（新，**共享区**）— `UserGamesAPI.list/get` + 类型，token 参数化。
- `kiosk/pages/PvpLocalSetupPage.tsx`（新）— 本地对弈建局页。
- `kiosk/pages/GameHistoryPage.tsx`（新）— 对局历史列表+预览+一键复盘。
- `kiosk/pages/GamePage.tsx`（改）— HvH `playerColor=null` 门控；`EndgameCard` 加「复盘本局」。
- `kiosk/pages/ResearchPage.tsx`（改）— 新增 sessionStorage 生谱入口（复盘本局）+ `?user_game_id=` 入口（对局历史）。
- `kiosk/pages/PlayPage.tsx`（改）— 「人人对弈」区加「对局历史」入口。
- `kiosk/KioskApp.tsx`（改）— `play/pvp/setup` 换成 `PvpLocalSetupPage`；注册 `play/pvp/history`。
- `hooks/useGameSession.ts`（改，**共享区**）— `playSound` 尊重落子音开关。
- 对应 `*.test.tsx`（新）。

---

## Task 1: 后端 `pvp_local` 建局分支（双方 human）

**Files:**
- Modify: `katrain/web/server.py:743-792`（`game_setup` free/ranked 分支之后新增 `elif mode == "pvp_local"`）
- Test: `tests/test_local_play_setup.py`（新）

**Interfaces:**
- Consumes: `session.katrain("update_player", bw, player_type, player_subtype, name)`、`session.katrain("new_game", size, handicap, komi, rules, game_type)`（server.py:753-788 既有用法）。
- Produces: `POST /api/game/setup` 支持 `mode="pvp_local"`，`settings` 含 `board_size / rules / handicap / komi / black_name / white_name / time_enabled / main_time / byo_length / byo_periods`。建局后 `session.game_type == "pvp_local"`，B/W 双方 `player_type == "player:human"`，且引擎 `game_type == "pvp_local"`（`analysis_allowed` 为真）。

**关键正确性点（workflow 验证）：** `reset_players`（`base_katrain.py:182-186`）**保留**上一局的 `player_type`。若会话被上一局人机对弈复用，B/W 里可能残留 `player:ai`，会在人类视觉落子后误触发 `genmove`。因此本分支**必须显式**把 B、W 两座都置回 `player:human`。

- [ ] **Step 1: 写失败测试**

`tests/test_local_play_setup.py`：
```python
import os
import pytest
from fastapi.testclient import TestClient
from katrain.web.server import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _new_session(client):
    r = client.post("/api/session/create", json={})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def test_pvp_local_sets_both_players_human(client):
    sid = _new_session(client)
    r = client.post("/api/game/setup", json={
        "session_id": sid,
        "mode": "pvp_local",
        "settings": {
            "board_size": 19, "rules": "chinese", "handicap": 0, "komi": 7.5,
            "black_name": "小明", "white_name": "小红",
            "time_enabled": False,
        },
    })
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["players_info"]["B"]["player_type"] == "player:human"
    assert state["players_info"]["W"]["player_type"] == "player:human"
    assert state["players_info"]["B"]["name"] == "小明"
    assert state["players_info"]["W"]["name"] == "小红"
    # pvp_local behaves like free for analysis, but is distinguishable
    assert state["game_type"] == "pvp_local"
    assert state.get("analysis_allowed") is not False
```

- [ ] **Step 2: 运行确认失败**

Run: `CI=true uv run pytest tests/test_local_play_setup.py -v`
Expected: FAIL —`game_type` 为 `free`/players 未按 human 设置（`pvp_local` 分支尚不存在，走了通用 `players` 空分支 → new_game 从未被调用，`state` 结构或断言不符）。

- [ ] **Step 3: 实现 `pvp_local` 分支**

在 `katrain/web/server.py`，紧接 `elif mode in ("free", "ranked"):` 块（结束于 788 行的 `new_game(...)`）之后、`state = session.katrain.get_state()`（790 行）之前，新增：
```python
            elif mode == "pvp_local":
                # Two humans face-to-face on one kiosk. Explicitly force BOTH seats to
                # player:human — reset_players preserves prior player_type, so a session
                # recycled from a previous AI game could leave a stale player:ai seat that
                # would wrongly auto-trigger genmove after the first human (vision) move.
                black_name = settings.get("black_name") or ""
                white_name = settings.get("white_name") or ""
                session.katrain(
                    "update_player", bw="B",
                    player_type="player:human", player_subtype="player:human", name=black_name,
                )
                session.katrain(
                    "update_player", bw="W",
                    player_type="player:human", player_subtype="player:human", name=white_name,
                )
                if black_name:
                    session.katrain.game.root.set_property("PB", black_name)
                if white_name:
                    session.katrain.game.root.set_property("PW", white_name)

                session.game_type = "pvp_local"

                time_enabled = settings.get("time_enabled", False)
                if time_enabled:
                    session.katrain.update_config("timer/main_time", settings.get("main_time", 0))
                    session.katrain.update_config("timer/byo_length", settings.get("byo_length", 30))
                    session.katrain.update_config("timer/byo_periods", settings.get("byo_periods", 3))
                    session.katrain.update_config("timer/paused", False)
                else:
                    session.katrain.update_config("timer/main_time", 0)
                    session.katrain.update_config("timer/byo_length", 0)
                    session.katrain.update_config("timer/paused", True)

                session.katrain(
                    "new_game",
                    size=settings.get("board_size", 19),
                    handicap=settings.get("handicap", 0),
                    komi=settings.get("komi", 7.5),
                    rules=settings.get("rules", "chinese"),
                    game_type="pvp_local",
                )
```

- [ ] **Step 4: 运行确认通过**

Run: `CI=true uv run pytest tests/test_local_play_setup.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add katrain/web/server.py tests/test_local_play_setup.py
git commit -m "feat(local-play): add pvp_local game_setup branch (both seats human)"
```

---

## Task 2: 存谱统一走 dispatcher（async）+ 动态 source（修复 HvAI local-only bug）

**Files:**
- Modify: `katrain/web/server.py:981-1049`（`_record_ai_game` → `async def` + 走 dispatcher + 动态 source）
- Modify: `katrain/web/server.py:1054-1105`（`resign`，已是 async；1103 行改 `await`）
- Modify: `katrain/web/server.py:1107-1151`（`_complete_count` 不再直接存谱，返回 `(result, needs_record)`）
- Modify: `katrain/web/server.py:1153-1216`（`request_count` → `async def`，锁外 `await` 存谱）
- Modify: `katrain/web/server.py:1218-1257`（`respond_count`，解包 tuple；仍为多人路径不需 await 存谱）
- Modify: `katrain/web/server.py:1259-1297`（`timeout` → `async def`，1295 改 `await`）
- Test: `tests/test_local_play_recording.py`（新）

**Interfaces:**
- Consumes: `dispatcher.user_games_create(user_id: int, data: dict)`（`repository.py`，async，在线→远程/离线→本地+`sync_enqueue`）；`app.state.user_game_repo.create(user_id, sgf_content, source, game_id=None, **kwargs)`（本地回退）。`UserGameCreate` 字段（`user_games.py:16-34`）。
- Produces: `async def _record_ai_game(session, app, current_user, result) -> None` — 计算 `source`（B、W 均 human → `"play_local"`，否则 `"play_ai"`），构造严格 `data` dict，`getattr(app.state, "repository_dispatcher", None)` 有则 `await dispatcher.user_games_create(...)`，无则 `app.state.user_game_repo.create(...)`。`_complete_count(session, app, current_user) -> tuple[str, bool]`。

**关键正确性点（workflow 验证）：** `session.lock` 是 `threading.Lock`。**绝不能在持锁时 `await` 网络 I/O**（会跨 await 持锁、饿死其他协程/线程）。计分与状态改写留在锁内，`await _record_ai_game` 移到锁**外**（`resign`/`timeout` 本就在锁外记录，对齐它们）。server 模式**无** `repository_dispatcher`（仅 `_lifespan_board` 在 332 设），故 `getattr(..., None)` 回退**必需**。

- [ ] **Step 1: 写失败测试**

`tests/test_local_play_recording.py`：
```python
import types
import pytest
from unittest.mock import AsyncMock, MagicMock

import katrain.web.server as server


class _Info:
    def __init__(self, human, name):
        self.human = human
        self.ai = not human
        self.name = name
        self.calculated_rank = None
        self.sgf_rank = None


def _make_session(both_human=True):
    s = MagicMock()
    s.user_id = 42
    s.player_b_id = None
    s.player_w_id = None
    s.game_type = "pvp_local" if both_human else "free"
    s.katrain.get_sgf.return_value = "(;GM[1])"
    s.katrain.get_state.return_value = {"board_size": [19, 19], "history": [1, 2, 3], "komi": 7.5, "ruleset": "chinese"}
    s.katrain.players_info = {"B": _Info(True, "小明"), "W": _Info(both_human, "小红" if both_human else "")}
    return s


@pytest.mark.asyncio
async def test_record_routes_through_dispatcher_with_play_local_source():
    session = _make_session(both_human=True)
    app = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    current_user = types.SimpleNamespace(id=42, username="小明")

    await server._RECORD_FN(session, app, current_user, "B+3.5")

    app.state.repository_dispatcher.user_games_create.assert_awaited_once()
    kwargs = app.state.repository_dispatcher.user_games_create.await_args.kwargs
    assert kwargs["user_id"] == 42
    data = kwargs["data"]
    assert data["source"] == "play_local"
    assert "user_id" not in data
    assert isinstance(data["board_size"], int) and data["board_size"] == 19
    assert data["result"] == "B+3.5"


@pytest.mark.asyncio
async def test_record_falls_back_to_local_repo_when_no_dispatcher():
    session = _make_session(both_human=False)  # AI game → play_ai
    app = MagicMock()
    app.state = types.SimpleNamespace(user_game_repo=MagicMock())
    # no repository_dispatcher attribute at all
    current_user = types.SimpleNamespace(id=42, username="小明")

    await server._RECORD_FN(session, app, current_user, "W+R")

    app.state.user_game_repo.create.assert_called_once()
    ckwargs = app.state.user_game_repo.create.call_args.kwargs
    assert ckwargs["source"] == "play_ai"
    assert ckwargs["user_id"] == 42
```

> 说明：`_record_ai_game` 是 `create_app()` 内部闭包，测试不便直接取。实现时在 `create_app` 里把该闭包挂到模块级引用 `server._RECORD_FN = _record_ai_game`（紧接定义之后一行）以便单测；生产逻辑不受影响。

- [ ] **Step 2: 运行确认失败**

Run: `CI=true uv run pytest tests/test_local_play_recording.py -v`
Expected: FAIL — `AttributeError: module 'katrain.web.server' has no attribute '_RECORD_FN'`（且 `_record_ai_game` 尚为 sync、未走 dispatcher）。

- [ ] **Step 3: 改 `_record_ai_game`（async + dispatcher + 动态 source）**

把 `_record_ai_game`（981 行）签名改为 `async def`，并把结尾的 `app.state.user_game_repo.create(...)`（1033-1049 附近）整段替换为构造 `data` + dispatcher 分支。定义之后新增一行 `server._RECORD_FN = _record_ai_game`（模块顶部已 `import ... as server` 不适用；用 `globals()` 挂载）。完整结尾：
```python
    async def _record_ai_game(session, app, current_user, result):
        """Record a completed single-player/local game to user_games (remote-first via
        dispatcher, else local). source = play_local when both seats are human, else play_ai."""
        try:
            sgf_content = session.katrain.get_sgf()
            state = session.katrain.get_state()
            players_info = session.katrain.players_info
            # ... (unchanged name/rank derivation block 988-1027) ...

            source = "play_local" if (players_info["B"].human and players_info["W"].human) else "play_ai"

            data = {
                "sgf_content": sgf_content,
                "source": source,
                "player_black": player_black,
                "player_white": player_white,
                "black_rank": black_rank,
                "white_rank": white_rank,
                "result": result,
                "board_size": int(board_size),
                "rules": rules,
                "komi": komi,
                "move_count": move_count,
                "category": "game",
                "game_type": game_type,
                "game_date": game_date,
            }

            dispatcher = getattr(app.state, "repository_dispatcher", None)
            if dispatcher is not None:
                await dispatcher.user_games_create(user_id=current_user.id, data=data)
            else:
                app.state.user_game_repo.create(user_id=current_user.id, **data)
        except Exception as e:
            logging.getLogger("katrain_web").error(f"Failed to record game: {e}")

    globals()["_RECORD_FN"] = _record_ai_game
```
（保留 988-1027 的 name/rank/board_size/move_count/komi/rules/game_type/game_date 推导原样，只替换最后的 create 调用与新增 `source`/`data`/dispatcher 分支。）

- [ ] **Step 4: 改 4 个调用点（锁外 await）**

`resign`（已 async，1101-1103）：
```python
            result = session.katrain.game.end_result
            if result:
                await _record_ai_game(session, app, current_user, result)
```

`_complete_count`（1107）：删掉其内部对 `_record_ai_game` 的直接调用（1148-1149），改为返回是否需要单人存谱：
```python
    def _complete_count(session, app, current_user):
        # ... scoring + set end_state under caller's lock (unchanged 1109-1128) ...
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if is_multiplayer:
            # ... unchanged multiplayer record_multiplayer_game + broadcast (1132-1147) ...
            return result, False
        needs_record = current_user is not None and session.user_id is not None
        return result, needs_record
```

`request_count`（1153）→ `async def request_count(...)`；两处 `_complete_count` 调用解包，单人分支锁外 await：
```python
                # (HvH other-player-accept, ~1186) multiplayer → no single-player record
                with session.lock:
                    result, _ = _complete_count(session, app, current_user)
                    session.pending_count_request = None
                    session.pending_count_timestamp = None
                    state = session.katrain.get_state()
                    session.last_state = state
                return {"session_id": session.session_id, "state": state, "result": result}
        ...
        else:
            # HvAI / pvp_local: complete immediately
            with session.lock:
                result, needs_record = _complete_count(session, app, current_user)
                state = session.katrain.get_state()
                session.last_state = state
            if needs_record:
                await _record_ai_game(session, app, current_user, result)
            return {"session_id": session.session_id, "state": state, "result": result}
```

`respond_count`（1218，多人路径）：解包 tuple（该路径 `is_multiplayer` 为真 → `needs_record` False，无需 await）：
```python
            with session.lock:
                result, _ = _complete_count(session, app, current_user)
                session.pending_count_request = None
                session.pending_count_timestamp = None
                state = session.katrain.get_state()
                session.last_state = state
            return {"session_id": session.session_id, "state": state, "result": result, "accepted": True}
```

`timeout`（1259）→ `async def timeout(...)`；1292-1295：
```python
        elif not is_multiplayer and current_user and session.user_id:
            result = session.katrain.game.end_result
            if result:
                await _record_ai_game(session, app, current_user, result)
```

- [ ] **Step 5: 运行确认通过**

Run: `CI=true uv run pytest tests/test_local_play_recording.py tests/test_ai_game_autosave.py -v`
Expected: PASS（新测试 + 既有 autosave 回归 `test_multiplayer_game_not_double_saved` 不破）。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/server.py tests/test_local_play_recording.py
git commit -m "fix(local-play): route game recording through RepositoryDispatcher (remote sync) + play_local source"
```

---

## Task 3: 自然终局（双 pass）也存谱 + 不重复存谱

**Files:**
- Modify: `katrain/web/server.py:603-643`（`play_move`：落子后若刚终局则单人存谱）
- Modify: `katrain/web/server.py`（`_record_ai_game` 内加 `session._recorded` 幂等标记）
- Test: `tests/test_local_play_recording.py`（追加）

**Interfaces:**
- Consumes: `session.katrain.game.end_result`（`game.py:306-310`：当前节点与父节点均为 pass → 自动返回 `manual_score or "board-game-end"`）。
- Produces: 双 pass 自然终局的 `pvp_local`/单人对局也会存谱一次，且与 `数子`/`认输` 路径**不重复**。

**关键正确性点（本会话直接验证）：** `end_result`（game.py:309）在**连续两个 pass** 时自动变真 → `GamePage` 显示终局卡片；但 `request_count`（1165）此时 `raise 400 "Game is already over"`，`play_move` 又从不存谱 → **双 pass 终局的对局永远存不下来**。这直接违背「记录下来方便复盘」。修复：`play_move` 落子后若 `end_result` 由无变有，为单人/本地对局补一次存谱；用 `session._recorded` 防止与后续动作重复。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_local_play_recording.py`）

```python
@pytest.mark.asyncio
async def test_record_is_idempotent_within_session():
    session = _make_session(both_human=True)
    session._recorded = False
    app = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    current_user = types.SimpleNamespace(id=42, username="小明")

    await server._RECORD_FN(session, app, current_user, "board-game-end")
    await server._RECORD_FN(session, app, current_user, "board-game-end")

    assert app.state.repository_dispatcher.user_games_create.await_count == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `CI=true uv run pytest tests/test_local_play_recording.py::test_record_is_idempotent_within_session -v`
Expected: FAIL — `await_count == 2`（尚无幂等标记）。

- [ ] **Step 3: 在 `_record_ai_game` 加幂等标记**

在 `_record_ai_game` 的 `try:` 开头、成功写入之后设标记；开头短路：
```python
    async def _record_ai_game(session, app, current_user, result):
        if getattr(session, "_recorded", False):
            return
        try:
            # ... build data + dispatcher/local write (Task 2) ...
            session._recorded = True
        except Exception as e:
            logging.getLogger("katrain_web").error(f"Failed to record game: {e}")
```

- [ ] **Step 4: `play_move` 加自然终局存谱钩子**

`play_move`（603，已 async）的本地分支（639-643）改为：
```python
        with session.lock:
            session.katrain("play", None if coords is None else tuple(coords))
            state = session.katrain.get_state()
            session.last_state = state
        # Natural (two-pass) game end never hits resign/count/timeout — record here so
        # local face-to-face games ending by both passing are still saved (end_result
        # auto-becomes truthy on two consecutive passes; requestCount then refuses).
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if state.get("end_result") and not is_multiplayer and current_user and session.user_id:
            await _record_ai_game(session, app, current_user, state["end_result"])
        return {"session_id": session.session_id, "state": state}
```

- [ ] **Step 5: 运行确认通过**

Run: `CI=true uv run pytest tests/test_local_play_recording.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add katrain/web/server.py tests/test_local_play_recording.py
git commit -m "fix(local-play): record on natural two-pass game end + idempotent guard"
```

---

## Task 4: 共享 `userGamesApi.ts`（list + get + 类型）

**Files:**
- Create: `katrain/web/ui/src/api/userGamesApi.ts`（**共享区**）
- Test: `katrain/web/ui/src/api/userGamesApi.test.ts`（新）

**Interfaces:**
- Consumes: `GET /api/v1/user-games/`（list，`?page&page_size&source&sort&q`，需 Bearer token）、`GET /api/v1/user-games/{id}`（get，需 token）。
- Produces：
```ts
export interface UserGameSummary {
  id: string; source: string; player_black: string | null; player_white: string | null;
  result: string | null; move_count: number; board_size: number;
  game_type: string | null; game_date: string | null; created_at: string;
}
export interface UserGameListResponse { items: UserGameSummary[]; total: number; page: number; page_size: number; }
export interface UserGameDetail extends UserGameSummary { sgf_content: string; komi: number; rules: string; }
export const UserGamesAPI: {
  list(token: string, params?: { page?: number; page_size?: number; source?: string; q?: string }): Promise<UserGameListResponse>;
  get(token: string, gameId: string): Promise<UserGameDetail>;
};
```

**决定（避免触碰 galaxy）：** 不移动 `src/galaxy/api/userGamesApi.ts`（会波及 ~5 个 galaxy import + 全量构建）。新建一个**最小 load-only** 共享封装（仅 list/get），与 `src/api/kifuApi.ts` 同位、同风格，但因端点需鉴权而带 `token` 参数。galaxy 版保持原样（load-only 与 galaxy 的 create/update 无重叠）。

- [ ] **Step 1: 写失败测试**

`katrain/web/ui/src/api/userGamesApi.test.ts`：
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UserGamesAPI } from './userGamesApi';

beforeEach(() => { vi.restoreAllMocks(); });

describe('UserGamesAPI', () => {
  it('list sends bearer token + source filter', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }) });
    vi.stubGlobal('fetch', fetchMock);
    await UserGamesAPI.list('tok123', { source: 'play_local', page: 2 });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/user-games/');
    expect(url).toContain('source=play_local');
    expect(url).toContain('page=2');
    expect(opts.headers.Authorization).toBe('Bearer tok123');
  });

  it('get fetches detail by id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'g1', sgf_content: '(;GM[1])' }) });
    vi.stubGlobal('fetch', fetchMock);
    const g = await UserGamesAPI.get('tok', 'g1');
    expect(g.sgf_content).toBe('(;GM[1])');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/user-games/g1');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd katrain/web/ui && npx vitest run src/api/userGamesApi.test.ts`
Expected: FAIL — 模块不存在。

- [ ] **Step 3: 实现**

`katrain/web/ui/src/api/userGamesApi.ts`：
```ts
// Shared (both builds) minimal load-only client for the personal game library
// (user_games). Auth-required, so every call takes a token. Kiosk must NOT import
// galaxy/api/userGamesApi.ts (SBC boundary); this lives in shared src/api/ like kifuApi.ts.

export interface UserGameSummary {
  id: string;
  source: string;
  player_black: string | null;
  player_white: string | null;
  result: string | null;
  move_count: number;
  board_size: number;
  game_type: string | null;
  game_date: string | null;
  created_at: string;
}

export interface UserGameListResponse {
  items: UserGameSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserGameDetail extends UserGameSummary {
  sgf_content: string;
  komi: number;
  rules: string;
}

async function authGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`user-games ${res.status}`);
  return res.json() as Promise<T>;
}

export const UserGamesAPI = {
  list: (token: string, params: { page?: number; page_size?: number; source?: string; q?: string } = {}): Promise<UserGameListResponse> => {
    const qs = new URLSearchParams();
    qs.set('page', String(params.page ?? 1));
    qs.set('page_size', String(params.page_size ?? 20));
    if (params.source) qs.set('source', params.source);
    if (params.q) qs.set('q', params.q);
    return authGet<UserGameListResponse>(`/api/v1/user-games/?${qs.toString()}`, token);
  },
  get: (token: string, gameId: string): Promise<UserGameDetail> =>
    authGet<UserGameDetail>(`/api/v1/user-games/${gameId}`, token),
};
```

- [ ] **Step 4: 运行确认通过**

Run: `cd katrain/web/ui && npx vitest run src/api/userGamesApi.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add katrain/web/ui/src/api/userGamesApi.ts katrain/web/ui/src/api/userGamesApi.test.ts
git commit -m "feat(local-play): add shared load-only UserGamesAPI (list/get) client"
```

---

## Task 5: `PvpLocalSetupPage`（本地对弈建局页）+ 路由接线 + 落子音开关

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx:64`（`play/pvp/setup` 换 `PvpLocalSetupPage`）
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts:42-55`（**共享区**，`playSound` 尊重开关）
- Test: `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.test.tsx`（新）

**Interfaces:**
- Consumes: `API.createSession(token)`、`API.gameSetup(sessionId, 'pvp_local', settings)`、`writeActiveSession(...)`（AiSetupPage.tsx:49-68 既有用法）。
- Produces: 路由 `play/pvp/setup` 渲染 `PvpLocalSetupPage`；「开始对弈」发 `gameSetup(id, 'pvp_local', {board_size, rules, handicap, komi, black_name, white_name, time_enabled, main_time, byo_length, byo_periods})` 并跳 `/kiosk/play/pvp/local/game/${id}`。落子音开关写 `localStorage['kioskPlaySound']`（`'1'`/`'0'`）。

**落子音开关机制（本会话验证）：** 后端 `play_stone_sound`（interface.py:879）无配置门；前端 `useGameSession.playSound`（hooks/useGameSession.ts:42）恒播。因此以**客户端偏好**实现：设置页写 `localStorage['kioskPlaySound']`，`playSound` 开头 `if (localStorage.getItem('kioskPlaySound') === '0') return;`（默认 null → 播，向后兼容）。改的是共享 hook → 两套构建都要过（Task 9）。

- [ ] **Step 1: 写失败测试**

`PvpLocalSetupPage.test.tsx`（镜像 `AiSetupPage.test.tsx` 的 mock 结构）：
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PvpLocalSetupPage from './PvpLocalSetupPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock('../../api', () => ({
  API: {
    createSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    gameSetup: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  },
}));
const { writeActiveSession } = vi.hoisted(() => ({ writeActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({ writeActiveSession }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok', user: { username: 'u' } }) }));

import { API } from '../../api';

const renderPage = () =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter><PvpLocalSetupPage /></MemoryRouter></ThemeProvider>);

beforeEach(() => vi.clearAllMocks());

describe('PvpLocalSetupPage', () => {
  it('starts a pvp_local game with both player names and navigates to the local game route', async () => {
    renderPage();
    await userEvent.type(screen.getByTestId('black-name-input').querySelector('input')!, '小明');
    await userEvent.type(screen.getByTestId('white-name-input').querySelector('input')!, '小红');
    await userEvent.click(screen.getByRole('button', { name: /开始对弈|Start Game/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    const [, mode, settings] = (API.gameSetup as any).mock.calls[0];
    expect(mode).toBe('pvp_local');
    expect(settings.black_name).toBe('小明');
    expect(settings.white_name).toBe('小红');
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/pvp/local/game/s1');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/PvpLocalSetupPage.test.tsx`
Expected: FAIL — 模块不存在。

- [ ] **Step 3: 实现 `PvpLocalSetupPage.tsx`**

以 `AiSetupPage.tsx` 为骨架，**保留** boardSize / rules / handicap / komi / 计时；**删** aiStrategy、rank、「我执」；**加** blackName / whiteName（`TextField`）与落子音开关（`Switch`）。关键片段（其余表单项照抄 AiSetupPage 对应块）：
```tsx
import { useState } from 'react';
import { Box, Typography, Button, Slider, Switch, FormControlLabel, Alert, TextField } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PlayArrow, ArrowBack } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';
import { API } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import LiveBoard from '../../components/live/LiveBoard';
import { writeActiveSession } from '../utils/activeSession';

const PvpLocalSetupPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();

  const [boardSize, setBoardSize] = useState(19);
  const [rules, setRules] = useState<'chinese' | 'japanese' | 'korean' | 'aga'>('chinese');
  const [blackName, setBlackName] = useState('');
  const [whiteName, setWhiteName] = useState('');
  const [handicap, setHandicap] = useState(0);
  const [komi, setKomi] = useState(6.5);
  const [timeEnabled, setTimeEnabled] = useState(false);
  const [mainTime, setMainTime] = useState(0);
  const [byoyomiTime, setByoyomiTime] = useState(30);
  const [byoyomiPeriods, setByoyomiPeriods] = useState(3);
  const [confirmSound, setConfirmSound] = useState(localStorage.getItem('kioskPlaySound') !== '0');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleStart = async () => {
    setError(''); setLoading(true);
    try {
      localStorage.setItem('kioskPlaySound', confirmSound ? '1' : '0');
      const { session_id } = await API.createSession(token ?? undefined);
      await API.gameSetup(session_id, 'pvp_local', {
        board_size: boardSize, rules, handicap, komi,
        black_name: blackName, white_name: whiteName,
        time_enabled: timeEnabled, main_time: mainTime,
        byo_length: byoyomiTime, byo_periods: byoyomiPeriods,
      });
      writeActiveSession({
        kind: 'game',
        label: `${blackName || t('Black', '黑方')} vs ${whiteName || t('White', '白方')}`,
        route: `/kiosk/play/pvp/local/game/${session_id}`,
        ts: Date.now(),
      });
      navigate(`/kiosk/play/pvp/local/game/${session_id}`);
    } catch (e: any) {
      setError(e.message || t('Failed to create game', '创建对局失败'));
    } finally {
      setLoading(false);
    }
  };
  // ... JSX: left LiveBoard preview + right form.
  // Reuse AiSetupPage board/rules/handicap/komi/time blocks verbatim (minus AI strategy/rank/color).
  // Player name fields:
  //   <TextField data-testid="black-name-input" label={t('Black player','黑方姓名')} value={blackName} onChange={e=>setBlackName(e.target.value)} .../>
  //   <TextField data-testid="white-name-input" label={t('White player','白方姓名')} value={whiteName} onChange={e=>setWhiteName(e.target.value)} .../>
  // Sound toggle:
  //   <FormControlLabel control={<Switch checked={confirmSound} onChange={(_,c)=>setConfirmSound(c)} />} label={t('Move sound','落子提示音')} />
  // Start button label t('Start Game','开始对弈'); back button navigate('/kiosk/play').
};

export default PvpLocalSetupPage;
```
（JSX 完整表单从 `AiSetupPage.tsx:77-305` 复制，删除 AI 策略 OptionChips(144-157)、rank Slider(160-175)、「我执」OptionChips(136-141)，把标题改 `t('Local Game','本地对局')`，插入上面两个 `TextField` 与 Sound `Switch`。）

- [ ] **Step 4: 接线路由**

`katrain/web/ui/src/kiosk/KioskApp.tsx`：顶部加 `import PvpLocalSetupPage from './pages/PvpLocalSetupPage';`（27 行附近）；把 64 行
```tsx
<Route path="play/pvp/setup" element={<PlaceholderPage />} />
```
改为
```tsx
<Route path="play/pvp/setup" element={<PvpLocalSetupPage />} />
```

- [ ] **Step 5: 落子音开关接线（共享 hook）**

`katrain/web/ui/src/hooks/useGameSession.ts` 的 `playSound`（42 行）函数体最前加：
```ts
  const playSound = useCallback((sound: string) => {
    if (typeof localStorage !== 'undefined' && localStorage.getItem('kioskPlaySound') === '0') return;
    const now = Date.now();
    // ... existing body ...
  }, []);
```

- [ ] **Step 6: 运行确认通过**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/PvpLocalSetupPage.test.tsx`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.test.tsx katrain/web/ui/src/kiosk/KioskApp.tsx katrain/web/ui/src/hooks/useGameSession.ts
git commit -m "feat(local-play): PvpLocalSetupPage + route + client move-sound toggle"
```

---

## Task 6: GamePage HvH 门控（`playerColor=null`）+ 终局「复盘本局」

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:288-291`（`humanColor` 双人判定）
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:70-90`（`EndgameCard` 加「复盘本局」，接收 `sessionId`）
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`（追加用例）

**Interfaces:**
- Consumes: `Board` 的 `playerColor: 'B'|'W'|null`（`Board.tsx:472,627`：`null` = 允许当前手方任意落子）。`API.saveSGF(sessionId): Promise<{sgf: string}>`（api.ts:228）。
- Produces: HvH（B、W 均 `player:human`）时 `playerColor={null}` → 触屏可双方轮流落子；`EndgameCard` 新增「复盘本局」→ 取 live SGF 存 `sessionStorage['kioskReviewSgf']` → `navigate('/kiosk/research')`。

**关键正确性点（workflow 验证）：** 现 `humanColor`（288-291）对 HvH 塌成 `'B'`，`Board.tsx:627` 于是**挡掉白方触屏落子**（摄像头掉线兜底下白方无法走）。修复：两方皆 human 时传 `null`。用「both-human」判定而非 `game_type==='pvp_local'`（不依赖 game_type 串是否透传到 get_state，更稳）。前端**拿不到**刚存的 `user_games.id`（`_record_ai_game` 丢弃返回；单人终局只广播无 id 的 state），故复盘用 **live SGF**（`API.saveSGF`），不用 `user_game_id` 深链。

- [ ] **Step 1: 写失败测试**（追加到 `GamePage.test.tsx`）

```tsx
// Assumes existing GamePage.test.tsx harness (mocked useGameSession / Board / API).
it('passes playerColor=null to Board when both players are human (HvH)', () => {
  // Arrange a gameState with B and W both player:human, then render GamePage.
  // Assert the Board mock received playerColor === null (not 'B').
  // (Mirror the existing Board mock capture pattern in this file.)
});
```
> 依 `GamePage.test.tsx` 现有对 `Board` 的 mock 方式捕获 props；断言 `playerColor` 为 `null`。若该文件用 `vi.mock('../../components/Board', ...)` 捕获最近一次 props，取其 `playerColor`。

- [ ] **Step 2: 运行确认失败**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.test.tsx`
Expected: FAIL — `playerColor` 为 `'B'`。

- [ ] **Step 3: 改 `humanColor`（both-human → null）**

`GamePage.tsx` 288-291：
```tsx
  // Both-human (local PvP): pass null so Board lets whichever side is to move play
  // (touchscreen fallback works for BOTH colors). Board.tsx:472/627 treat null as "anyone".
  const bothHuman =
    gameState.players_info?.B?.player_type === 'player:human' &&
    gameState.players_info?.W?.player_type === 'player:human';
  const humanColor: 'B' | 'W' | null =
    bothHuman ? null
    : gameState.players_info?.B?.player_type === 'player:human' ? 'B'
    : gameState.players_info?.W?.player_type === 'player:human' ? 'W'
    : null;
```

- [ ] **Step 4: `EndgameCard` 加「复盘本局」**

给 `EndgameCard` 增 `sessionId` 与 `onReview` prop（GamePage 有 `sessionId = useParams()`）。按钮行（84 行附近）加：
```tsx
        <Button variant="outlined" onClick={onReview}>{t('Review this game', '复盘本局')}</Button>
```
`EndgameCard` 渲染处（548 行）传：
```tsx
      {isGameOver && (
        <EndgameCard
          key={sessionId}
          gameState={gameState}
          t={t}
          onExit={handleExit}
          onReview={async () => {
            if (!sessionId) return;
            try {
              const { sgf } = await API.saveSGF(sessionId);
              sessionStorage.setItem('kioskReviewSgf', sgf);
              navigate('/kiosk/research');
            } catch (e) { console.error(e); }
          }}
        />
      )}
```
（`EndgameCardProps` 加 `onReview: () => void`。）

- [ ] **Step 5: 运行确认通过**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.test.tsx`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.test.tsx
git commit -m "feat(local-play): HvH playerColor=null gating + EndgameCard 复盘本局"
```

---

## Task 7: ResearchPage 复盘入口（sessionStorage 生谱 + `?user_game_id=`）

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx`（新增两个 mount 加载分支）
- Test: `katrain/web/ui/src/kiosk/pages/ResearchPage.userGame.test.tsx`（新）

**Interfaces:**
- Consumes: `board.loadFromSGF(sgf)`、`session.createSession(sgf, {skipAnalysis})`（ResearchPage 既有 `?kifu_id=` 分支 378-420 用法）、`UserGamesAPI.get(token, id)`（Task 4）、`useAuth().token`。
- Produces: ①mount 时若 `sessionStorage['kioskReviewSgf']` 有值 → `board.loadFromSGF(sgf)` 后清除（复盘本局落地）；②`?user_game_id=X` → `UserGamesAPI.get(token, X)` → `board.loadFromSGF(detail.sgf_content)`，`?analyze=1` 则接 `createSession(detail.sgf_content, {skipAnalysis:true})`。

**关键正确性点（workflow 验证）：** 必须把 fetch 得到的 `sgf_content` **直接**喂进 `createSession`，不要从 `board` 重新取（`board` 的 `loadFromSGF` 状态在同一异步续体内**未刷新**，会读到空值——即 galaxy `ResearchPage.tsx:187-199` 的 stale-closure bug，该文件 370-376 注释已说明）。用各自的 `ref` 守卫防重入。`GET /{id}` 需 token；token 为 null 时守卫等待。

- [ ] **Step 1: 写失败测试**

`ResearchPage.userGame.test.tsx`（聚焦加载分支；按该文件既有 mock 方式 mock `useResearchBoard`/`useResearchSession`/`UserGamesAPI`）：
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const loadFromSGF = vi.fn();
vi.mock('../hooks/useResearchBoard', () => ({ useResearchBoard: () => ({ loadFromSGF, moves: [], currentMove: 0, serializeToSGF: () => ({ sgf: '' }) }) }));
vi.mock('../../hooks/useResearchSession', () => ({ useResearchSession: () => ({ createSession: vi.fn().mockResolvedValue('s2') }) }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok' }) }));
const get = vi.fn().mockResolvedValue({ id: 'g1', sgf_content: '(;GM[1]FF[4])' });
vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { get, list: vi.fn() } }));

import ResearchPage from './ResearchPage';

beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });

const renderAt = (path: string) =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={[path]}><ResearchPage /></MemoryRouter></ThemeProvider>);

describe('ResearchPage local-play review entry', () => {
  it('loads SGF handed off via sessionStorage (复盘本局)', async () => {
    sessionStorage.setItem('kioskReviewSgf', '(;GM[1]FF[4])');
    renderAt('/kiosk/research');
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
    expect(sessionStorage.getItem('kioskReviewSgf')).toBeNull();
  });

  it('loads a recorded game by ?user_game_id', async () => {
    renderAt('/kiosk/research?user_game_id=g1');
    await waitFor(() => expect(get).toHaveBeenCalledWith('tok', 'g1'));
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/ResearchPage.userGame.test.tsx`
Expected: FAIL — 未加载。

- [ ] **Step 3: 实现两个 mount 分支**

在 `ResearchPage.tsx` 顶部加 `import { useAuth } from '../../context/AuthContext';`、`import { UserGamesAPI } from '../../api/userGamesApi';`，组件内 `const { token } = useAuth();`。在既有 `?kifu_id=` effect 附近新增（各带 ref 守卫）：
```tsx
  // (a) 复盘本局: raw SGF handed off via sessionStorage by GamePage EndgameCard.
  const reviewSgfLoadedRef = useRef(false);
  useEffect(() => {
    if (reviewSgfLoadedRef.current) return;
    const sgf = sessionStorage.getItem('kioskReviewSgf');
    if (!sgf) return;
    reviewSgfLoadedRef.current = true;
    sessionStorage.removeItem('kioskReviewSgf');
    board.loadFromSGF(sgf);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // (b) 对局历史一键复盘: ?user_game_id=X (&analyze=1). Thread the fetched sgf_content
  // straight into createSession — never re-derive from board (stale-closure, see kifu_id).
  const userGameLoadedRef = useRef(false);
  useEffect(() => {
    const id = searchParams.get('user_game_id');
    if (!id || userGameLoadedRef.current || !token) return;
    userGameLoadedRef.current = true;
    (async () => {
      try {
        const detail = await UserGamesAPI.get(token, id);
        if (!detail.sgf_content) return;
        board.loadFromSGF(detail.sgf_content);
        if (searchParams.get('analyze') === '1') {
          await session.createSession(detail.sgf_content, { skipAnalysis: true });
        }
      } catch (e) { console.error(e); }
    })();
  }, [searchParams, token]); // eslint-disable-line react-hooks/exhaustive-deps
```
> 若该文件已有 `board`/`session` 变量名不同，按实际名对齐（分别来自 `useResearchBoard`/`useResearchSession`）。

- [ ] **Step 4: 运行确认通过**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/ResearchPage.userGame.test.tsx`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add katrain/web/ui/src/kiosk/pages/ResearchPage.tsx katrain/web/ui/src/kiosk/pages/ResearchPage.userGame.test.tsx
git commit -m "feat(local-play): ResearchPage review entries (sessionStorage SGF + ?user_game_id)"
```

---

## Task 8: `GameHistoryPage`（对局历史）+ PlayPage 入口 + 路由

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/GameHistoryPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`（注册 `play/pvp/history`）
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx:104-124`（「人人对弈」区加入口）
- Test: `katrain/web/ui/src/kiosk/pages/GameHistoryPage.test.tsx`（新）

**Interfaces:**
- Consumes: `UserGamesAPI.list(token, {source, page})` / `UserGamesAPI.get(token, id)`（Task 4）、`useAuth().token`、`LiveBoard`、`KioskResultBadge`。
- Produces: 路由 `play/pvp/history`（`/kiosk/play/pvp/history`）渲染列表+预览；行点击 → `UserGamesAPI.get` 预览；「复盘」→ `navigate('/kiosk/research?user_game_id=' + id + '&analyze=1')`。默认 `source='play_local'`，含「本地/全部」切换。

**关键点（workflow 验证）：** 列表项**不含 SGF**（`user_game_repo.py:128 include_sgf=False`）→ 预览/复盘需 `get` 二次拉取（镜像 `KifuPage` 的 selectedId→getAlbum）。item `id` 是 string UUID、日期字段是 `game_date`/`created_at`（≠ KifuPage 的 `date_played`）。列表 URL-regex mock 里 **detail 路由要在 list 路由之前匹配**（KifuPage.test.tsx:60 的坑）。页面在 `KioskAuthGuard` 之内 → token 必有；nav 用 nav-rail 组（要 dock），无需 `PhysicalBoardGuard`。

- [ ] **Step 1: 写失败测试**

`GameHistoryPage.test.tsx`：
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok' }) }));
const list = vi.fn().mockResolvedValue({ items: [
  { id: 'g1', source: 'play_local', player_black: '小明', player_white: '小红', result: 'B+3.5', move_count: 180, board_size: 19, game_type: 'pvp_local', game_date: '2026-07-12', created_at: '2026-07-12T10:00:00Z' },
], total: 1, page: 1, page_size: 20 });
const get = vi.fn().mockResolvedValue({ id: 'g1', sgf_content: '(;GM[1])', player_black: '小明', player_white: '小红', result: 'B+3.5', move_count: 180, board_size: 19, komi: 7.5, rules: 'chinese', source: 'play_local', game_type: 'pvp_local', game_date: '2026-07-12', created_at: '2026-07-12T10:00:00Z' });
vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { list, get } }));

import GameHistoryPage from './GameHistoryPage';

beforeEach(() => vi.clearAllMocks());
const renderPage = () =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter><GameHistoryPage /></MemoryRouter></ThemeProvider>);

describe('GameHistoryPage', () => {
  it('lists local games and 复盘 navigates to research with user_game_id', async () => {
    renderPage();
    await waitFor(() => expect(list).toHaveBeenCalledWith('tok', expect.objectContaining({ source: 'play_local' })));
    await screen.findByText('小明');
    await userEvent.click(screen.getByText('小明'));
    await waitFor(() => expect(get).toHaveBeenCalledWith('tok', 'g1'));
    await userEvent.click(screen.getByRole('button', { name: /复盘|Review/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/research?user_game_id=g1&analyze=1');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GameHistoryPage.test.tsx`
Expected: FAIL — 模块不存在。

- [ ] **Step 3: 实现 `GameHistoryPage.tsx`**（镜像 `KifuPage.tsx` 的列表+预览结构，换 `UserGamesAPI` + token + 字段名）

```tsx
import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, List, ListItemButton, CircularProgress, Chip, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import LiveBoard from '../../components/live/LiveBoard';
import { sgfToMoves } from '../../utils/sgfSerializer';
import { UserGamesAPI, type UserGameSummary, type UserGameDetail } from '../../api/userGamesApi';

const GameHistoryPage = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [source, setSource] = useState<'play_local' | 'all'>('play_local');
  const [items, setItems] = useState<UserGameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<UserGameDetail | null>(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    UserGamesAPI.list(token, { page: 1, page_size: 30, ...(source === 'play_local' ? { source: 'play_local' } : {}) })
      .then(r => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [token, source]);

  const select = useCallback(async (id: string) => {
    if (!token) return;
    setDetail(null);
    try { setDetail(await UserGamesAPI.get(token, id)); } catch { /* keep null */ }
  }, [token]);

  // Left: list; Right: preview (LiveBoard from detail.sgf_content) + 复盘 button.
  // 复盘: navigate(`/kiosk/research?user_game_id=${detail.id}&analyze=1`).
  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Box sx={{ width: 360, borderRight: '1px solid', borderColor: 'divider', overflow: 'auto' }}>
        <Box sx={{ display: 'flex', gap: 1, p: 1.5 }}>
          <Chip label={t('Local games', '本地对局')} color={source === 'play_local' ? 'primary' : 'default'} onClick={() => setSource('play_local')} />
          <Chip label={t('All', '全部')} color={source === 'all' ? 'primary' : 'default'} onClick={() => setSource('all')} />
        </Box>
        {loading ? <CircularProgress sx={{ m: 2 }} /> : (
          <List>
            {items.map(g => (
              <ListItemButton key={g.id} onClick={() => select(g.id)}>
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>{g.player_black || t('Black', '黑方')}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {g.result || '—'} · {g.move_count}{t('moves', '手')} · {g.game_date || g.created_at?.slice(0, 10)}
                  </Typography>
                </Box>
              </ListItemButton>
            ))}
          </List>
        )}
      </Box>
      <Box sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column' }}>
        {detail ? (
          <>
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <LiveBoard moves={sgfToMoves(detail.sgf_content).moves} currentMove={sgfToMoves(detail.sgf_content).moves.length} boardSize={detail.board_size} showCoordinates />
            </Box>
            <Button variant="contained" sx={{ mt: 2 }} onClick={() => navigate(`/kiosk/research?user_game_id=${detail.id}&analyze=1`)}>
              {t('Review', '复盘')}
            </Button>
          </>
        ) : <Typography color="text.secondary" sx={{ m: 'auto' }}>{t('Select a game', '选择一局查看')}</Typography>}
      </Box>
    </Box>
  );
};

export default GameHistoryPage;
```
> `sgfToMoves` 的返回结构以 `KifuPage.tsx` 现有用法为准（它已 `import { sgfToMoves } from '../../utils/sgfSerializer'`）；若签名不同按 KifuPage 对齐。

- [ ] **Step 4: 注册路由 + PlayPage 入口**

`KioskApp.tsx`：加 `import GameHistoryPage from './pages/GameHistoryPage';`；在 nav-rail 组内（`play/pvp/lobby` 那行之后，65 行附近）加：
```tsx
          <Route path="play/pvp/history" element={<GameHistoryPage />} />
```
`PlayPage.tsx`：在「人人对弈」grid（105-124）之后，加一个次级入口（复用 55-77 的 `ButtonBase` 风格，避免破坏 `repeat(3,1fr)`）：
```tsx
      <ButtonBase
        onClick={() => navigate('/kiosk/play/pvp/history')}
        data-testid="game-history-entry"
        sx={{ mt: 0.5, alignSelf: 'flex-start', px: 1.5, py: 0.75, borderRadius: '10px', border: '1px solid', borderColor: 'divider', color: 'text.secondary', fontSize: 13 }}
      >
        {t('Game history', '对局历史')} ›
      </ButtonBase>
```

- [ ] **Step 5: 运行确认通过**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GameHistoryPage.test.tsx`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/src/kiosk/pages/GameHistoryPage.tsx katrain/web/ui/src/kiosk/pages/GameHistoryPage.test.tsx katrain/web/ui/src/kiosk/KioskApp.tsx katrain/web/ui/src/kiosk/pages/PlayPage.tsx
git commit -m "feat(local-play): GameHistoryPage (对局历史) + PlayPage entry + route"
```

---

## Task 9: i18n 登记 + 两套构建验证 + 端到端冒烟

**Files:**
- Modify: `katrain/i18n/locales/*/LC_MESSAGES/katrain.po`（新 msgid，经 `katrain-i18n-expert` 技能）
- 验证：整仓构建 + 后端测试

**Interfaces:**
- Consumes: 前面 Tasks 引入的所有 `t('English key','中文默认')` 串。
- Produces: 非中文设备也有翻译；两套前端构建绿；后端全测通过。

- [ ] **Step 1: 收集新增 i18n key**

列出本轨道所有新 `t()` key（如 `Local Game`/`本地对局`、`Black player`/`黑方姓名`、`White player`/`白方姓名`、`Move sound`/`落子提示音`、`Review this game`/`复盘本局`、`Game history`/`对局历史`、`Local games`/`本地对局`、`All`/`全部`、`Review`/`复盘`、`Select a game`/`选择一局查看`、`moves`/`手`、`Black`/`黑方`、`White`/`白方`、`Failed to create game`/`创建对局失败`）。

- [ ] **Step 2: 用 i18n 技能补全 11 语**

调用 `katrain-i18n-expert` 技能把上述 msgid 写进各语 `katrain.po`（cn≠zh、jp≠ja；**禁日文**留空或英文回退按技能规则）。

- [ ] **Step 3: 前端两套构建 + lint**

Run:
```bash
cd katrain/web/ui && npm run lint && npm run build && npm run build:kiosk-2d
```
Expected: 三条全 exit 0；`verify:kiosk-2d` 无 `three`/`@react-three` 泄漏；eslint 无 kiosk→galaxy 越界。

- [ ] **Step 4: 后端全量测试**

Run: `CI=true uv run pytest tests -q`
Expected: PASS（含 `test_local_play_setup.py`、`test_local_play_recording.py`、既有 `test_ai_game_autosave.py`）。

- [ ] **Step 5: 端到端手动冒烟**（board 模式，见记忆 mac_kiosk_launch）

启动 kiosk（board 模式，匹配分辨率），走一遍：`对弈 → 人人对弈 · 本地对局 → 填黑白名 → 开始 → 触屏轮流落子（确认白方也能落）→ 双 pass 终局 → 复盘本局进研究页 → 返回 → 人人对弈 · 对局历史 → 该局在列 → 复盘`。在线时确认远程列表/galaxy 端也能看到该局；断网时确认本地存 + 联网后补传。

- [ ] **Step 6: 提交**

```bash
git add katrain/i18n
git commit -m "chore(local-play): register i18n strings for local play across locales"
```

---

## Self-Review（针对 prd.md 逐条核对）

**Spec coverage：**
- PRD R1（建局页）→ Task 5 ✅；R2（后端 pvp_local）→ Task 1 ✅；R3（HvH 门控/触屏/视觉/数子）→ Task 6（门控）+ Task 1（视觉天然通用，workflow 已确认无需改 poller）✅；R4（存谱同步）→ Task 2 ✅；R5（历史+复盘）→ Task 4/7/8 ✅。
- PRD 风险表：自动 genmove（Task 1 显式重置双 human 座）、LED no-op（无 AI 座 → guided_colors 空 → 无落子灯；无 LED 硬件时全 no-op，见 vision-led 验证，无需新代码，Task 9 冒烟核对）、sync→async 接线（Task 2）、拿不到 user_game_id（Task 6 用 live SGF）、Board 门控（Task 6）✅。
- **新增覆盖（PRD 未显式但为核心正确性）**：自然双 pass 终局存谱 → Task 3 ✅（否则「记录下来」在最自然的终局方式下失效）。

**Placeholder scan：** 无 TBD/TODO；每个改动步给了真实代码/命令与期望输出。JSX 表单大段以「从 AiSetupPage 对应块复制、删 X 加 Y」明确指代（非 "similar to"），因为要复制的正是同仓已存在的成熟文件。

**Type consistency：** `UserGamesAPI.list/get`、`UserGameSummary/Detail`（Task 4）在 Task 7/8 一致引用；`_record_ai_game` async 签名（Task 2）在 Task 3 复用；`EndgameCardProps.onReview`（Task 6）自洽；`source='play_local'` 在后端写入（Task 2）与前端列表 filter（Task 8）用同一字面量。

**遗留/未决（实现时确认，非阻断）：**
- 支招/hint 对 `pvp_local` 关闭（`game_type==='free'` 门控）——符合「双人无 AI」，PRD 已列 descope，无需改。
- LED「捕子蓝灯/让子红灯」在有 LED 硬件时仍会亮（非落子引导）——PRD 决定「本地对弈无 LED」，若要严格 no-op 需给这几处加 `pvp_local` 门（Task 9 冒烟时判断是否必要；默认无 LED 硬件即自动 no-op，暂不加代码）。
- 幂等 `id`（客户端 UUID）未做——依赖 `sgf_hash` 去重（`user_game_repo.py:28-38`）已足够，YAGNI。
