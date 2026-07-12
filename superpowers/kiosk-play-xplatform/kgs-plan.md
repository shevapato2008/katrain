# KGS 接入（live 真人 human-relay）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 kiosk 用户在实体棋盘上，通过 KGS（gokgs.com）与在线真人对弈——浏览棋友→按 KGS 设置发起邀请→对方接受→视觉识别我方落子转发 KGS、对手落子驱动 LED 引导摆子，走完一整盘。

**Architecture:** 复用既有 `PlatformAdapter → PlatformManager → PlatformCommandGateway` 主干与物理 LED 闭环。KGS 已有脚手架（`katrain/web/platforms/kgs/`，走 KGS JSON API 长轮询，坐标 identity），本计划**补完桩 + 接通 live 路径**：后端补 proposal/浏览/邀请/开局通知，前端补设置面板/大厅 WS 导航/实时对局页。LED 引导远端真人对手的一方，采用**方案 B**：把只服务人机的 `platform_engine_color` 改名中性的 `platform_guided_color`，人机与 live 两条开局路径都设它。

**Tech Stack:** Python 3 / FastAPI / httpx（后端）；React + TypeScript + Vite + MUI（kiosk 前端）；pytest（后端测试）；vitest（前端测试）。KGS = JSON 协议（`https://www.gokgs.com/json/access`，POST 发 / GET 收，cookie 会话，60s 长轮询）。

## Global Constraints

- **坐标系**：KaTrain 内部 `(col,row)` 原点左上、row 0 在顶；KGS `{"x":col,"y":row}` 同向 → **identity，零转换**。vision/LED 的 GTP 上下翻转由既有 orchestrator 处理，KGS 不碰。
- **LED 方案 B（用户已批准）**：全仓 `platform_engine_color` → `platform_guided_color`（中性名，含义=“物理人类不执、需 LED 引导摆子的那一方”）。人机=远端引擎色；live=远端真人对手色。
- **Kiosk 构建边界**：新前端代码只放 `katrain/web/ui/src/kiosk/**`，只 import 共享地盘（`components/`(非 Board3D)、`hooks/`、`context/`、`api.ts`、`utils/`、`i18n`），**禁止** import `galaxy/**`、`components/Board3D/**`、`pages/VideoRecorder*`。改动共享文件（如 `api.ts`）后**两个构建都要过**：`npm run build` 与 `npm run build:kiosk-2d`。
- **i18n**：静态串一律 `t('English key', '中文默认')`，`const { t } = useTranslation()`；默认中文。
- **语言**：注释/文档用中文或英文，绝不用日文。
- **KGS 能力**：`supports_scoring=False`（KGS 服务端点目）、`supports_automatch=False`（无自动快配）、`supports_rooms=True`、`supports_live_play=True`。MVP 不做点目 UI / 自动匹配 / 房间浏览。
- **格式化**：Python 用 `uv run black -l 120 katrain tests`；提交前跑。
- **测试命令**：后端 `CI=true uv run pytest <path>`（`CI=true` 跳过 GPU 用例）；前端 `cd katrain/web/ui && npm test`（= `vitest run`），单文件 `npx vitest run <path>`。
- **分支**：`feature/kiosk-play-xplatform`，worktree `/Users/fan/Repositories/katrain-kiosk-play-xplatform`。频繁提交，每个 Task 一次可测交付。

---

### Task 1: 全仓重命名 `platform_engine_color` → `platform_guided_color`（方案 B，纯机械、行为不变）

把只服务人机的字段改成中性名，让 live 真人对局也能复用同一 LED 引导通道。**这是纯重命名**：不改任何行为，改完全套测试必须仍绿。

**Files:**
- Modify: `katrain/web/interface.py:151,496,516,520,586,590,591`
- Modify: `katrain/web/platforms/manager.py:181`
- Modify: `katrain/web/core/physical_play_orchestrator.py:422`(注释)`,429`
- Modify: `katrain/web/ui/src/api.ts:78`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:37,45,46,56,64`
- Modify: `katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json:88`
- Modify (tests): `tests/platforms/test_engine_manager.py`, `tests/test_physical_play_orchestrator.py`, `tests/test_engine_physical_integration.py`, `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx`

**Interfaces:**
- Produces: state field `platform_guided_color: "B"|"W"|None` on `get_state()`; `edit_game(..., platform_guided_color=...)` kwarg; frontend `GameState.platform_guided_color`. 所有后续 Task 用新名。

- [ ] **Step 1: 先看基线全绿**

Run: `CI=true uv run pytest tests/platforms/test_engine_manager.py tests/test_physical_play_orchestrator.py tests/test_engine_physical_integration.py -q`
Expected: PASS（记录通过数，作为重命名后的对照）。

- [ ] **Step 2: 后端机械重命名**

在这些**非测试**文件里把标识符 `platform_engine_color` 全部替换为 `platform_guided_color`（含 `self.platform_engine_color`、`edit_game` 形参、`get_state` 键、`state.get(...)`、注释）：
`katrain/web/interface.py`、`katrain/web/platforms/manager.py`、`katrain/web/core/physical_play_orchestrator.py`。

逐文件用精确替换（示例，interface.py）：
```python
# 151:  self.platform_guided_color = None
# 496:  "platform_guided_color": getattr(self, "platform_guided_color", None),
# 520:  self.platform_guided_color = None
# 586:  def _do_edit_game(self, size=None, handicap=None, komi=None, rules=None, platform_guided_color=None):
# 590:  if platform_guided_color is not None:
# 591:      self.platform_guided_color = platform_guided_color
```
manager.py:181 → `platform_guided_color=ai_color,`
orchestrator.py:429 → `guided_color = state.get("platform_guided_color")`（并把 429 上方注释里的字段名一并改）。

- [ ] **Step 3: 前端机械重命名**

`katrain/web/ui/src/api.ts:78` → `platform_guided_color?: 'B' | 'W' | null;`
`katrain/web/ui/src/kiosk/pages/GamePage.tsx`：45/46/64 的 `gameState.platform_engine_color` → `gameState.platform_guided_color`（37/56 注释同改）。例如：
```tsx
export function deriveHumanColor(gameState: GameState): 'B' | 'W' | null {
  if (gameState.platform_guided_color === 'B') return 'W';
  if (gameState.platform_guided_color === 'W') return 'B';
  return gameState.players_info?.B?.player_type === 'player:human' ? 'B'
    : gameState.players_info?.W?.player_type === 'player:human' ? 'W'
    : null;
}
```
`katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json:88` 键改名。

- [ ] **Step 4: 测试文件重命名**

在 `tests/platforms/test_engine_manager.py`、`tests/test_physical_play_orchestrator.py`、`tests/test_engine_physical_integration.py`、`katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx` 里把所有 `platform_engine_color` 字面（断言键、`mockGameState.platform_engine_color = ...`、`engineFixture.platform_engine_color`、测试名/注释）替换为 `platform_guided_color`。

- [ ] **Step 5: 确认无残留**

Run: `grep -rn "platform_engine_color" katrain tests | grep -v node_modules`
Expected: 无输出（空）。

- [ ] **Step 6: 后端 + 前端测试仍全绿（行为不变）**

Run: `CI=true uv run pytest tests/platforms/test_engine_manager.py tests/test_physical_play_orchestrator.py tests/test_engine_physical_integration.py -q`
Expected: PASS，通过数与 Step 1 一致。
Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx`
Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(platform): rename platform_engine_color -> platform_guided_color (approach B, no behavior change)"
```

---

### Task 2: KGS `_build_proposal` 按真实 KGS `Rules`/`Proposal` 结构重写

现有 `_build_proposal`（adapter.py:283）字段扁平、且有 `nigpiresPlayers` 拼写错误，与真实 KGS 协议不符。KGS 的 `proposal` = `{gameType, rules:{...}, nigiri, players:[...]}`，且 `size/rules/handicap/komi/timeSystem/mainTime/byoYomiTime/byoYomiPeriods/byoYomiStones` 全在 `rules` 对象内。

**Files:**
- Modify: `katrain/web/platforms/kgs/adapter.py:283-306`（`_build_proposal`）
- Test: `tests/platforms/test_kgs_adapter.py`（Create）

**Interfaces:**
- Consumes: `settings: dict`（键：`board_size,rules,komi,handicap,time_system,main_time,byo_yomi_time,byo_yomi_periods,byo_yomi_stones,ranked,nigiri,opponent_name,my_color`）。
- Produces: `_build_proposal(self, settings: dict, opponent_name: str) -> dict`，返回合法 KGS proposal。

- [ ] **Step 1: 写失败测试**

Create `tests/platforms/test_kgs_adapter.py`:
```python
"""Unit tests for the KGS adapter helpers."""

from katrain.web.platforms.kgs.adapter import KGSAdapter


def _adapter_with_user(name="me"):
    a = KGSAdapter()
    a._client._username = name  # set the logged-in name without a network login
    return a


def test_build_proposal_byoyomi_nests_rules_and_players():
    a = _adapter_with_user("me")
    p = a._build_proposal(
        {
            "board_size": 19,
            "rules": "chinese",
            "komi": 7.5,
            "handicap": 0,
            "time_system": "byo_yomi",
            "main_time": 1200,
            "byo_yomi_time": 30,
            "byo_yomi_periods": 5,
            "ranked": False,
            "nigiri": True,
            "my_color": "B",
        },
        opponent_name="rival",
    )
    assert p["gameType"] == "free"
    assert p["nigiri"] is True
    r = p["rules"]
    assert r["size"] == 19
    assert r["rules"] == "chinese"
    assert r["komi"] == 7.5
    assert r["timeSystem"] == "byo_yomi"
    assert r["mainTime"] == 1200
    assert r["byoYomiTime"] == 30
    assert r["byoYomiPeriods"] == 5
    assert "byoYomiStones" not in r  # only for canadian
    assert "handicap" not in r  # omitted when 0
    # first player must be the challenge owner (us)
    assert p["players"][0]["name"] == "me"
    names = {pl["name"] for pl in p["players"]}
    assert names == {"me", "rival"}


def test_build_proposal_ranked_canadian_with_handicap_and_fixed_color():
    a = _adapter_with_user("me")
    p = a._build_proposal(
        {
            "board_size": 13,
            "rules": "japanese",
            "komi": 0.5,
            "handicap": 3,
            "time_system": "canadian",
            "main_time": 600,
            "byo_yomi_time": 300,
            "byo_yomi_stones": 25,
            "ranked": True,
            "nigiri": False,
            "my_color": "W",
        },
        opponent_name="rival",
    )
    assert p["gameType"] == "ranked"
    assert p["nigiri"] is False
    r = p["rules"]
    assert r["handicap"] == 3
    assert r["timeSystem"] == "canadian"
    assert r["byoYomiStones"] == 25
    assert "byoYomiPeriods" not in r
    # fixed color honored: we are White, owner-first
    assert p["players"][0] == {"role": "white", "name": "me"}
    assert {"role": "black", "name": "rival"} in p["players"]


def test_build_proposal_no_time():
    a = _adapter_with_user("me")
    p = a._build_proposal(
        {"board_size": 9, "rules": "aga", "komi": 7.0, "handicap": 0, "time_system": "none",
         "ranked": False, "nigiri": True, "my_color": "B"},
        opponent_name="rival",
    )
    r = p["rules"]
    assert r["timeSystem"] == "none"
    assert "mainTime" not in r and "byoYomiTime" not in r
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q`
Expected: FAIL（当前 `_build_proposal` 只接受 `settings` 一个参数，签名不符 + 结构不符）。

- [ ] **Step 3: 重写 `_build_proposal`**

替换 `katrain/web/platforms/kgs/adapter.py` 的 `_build_proposal`：
```python
    def _build_proposal(self, settings: dict, opponent_name: str) -> dict:
        """Build a KGS challenge proposal from settings (real KGS Rules/Proposal shape).

        All board/time params nest inside `rules`; the challenge owner (us) must be the
        first entry in `players`. See gokgs.com/json/dataTypes.html.
        """
        rules = {
            "size": int(settings.get("board_size", 19)),
            "rules": settings.get("rules", "japanese"),
            "komi": float(settings.get("komi", 6.5)),
            "timeSystem": settings.get("time_system", "byo_yomi"),
        }
        handicap = int(settings.get("handicap", 0) or 0)
        if handicap:
            rules["handicap"] = handicap
        ts = rules["timeSystem"]
        if ts != "none":
            rules["mainTime"] = int(settings.get("main_time", 600))
        if ts in ("byo_yomi", "canadian"):
            rules["byoYomiTime"] = int(settings.get("byo_yomi_time", 30))
        if ts == "byo_yomi":
            rules["byoYomiPeriods"] = int(settings.get("byo_yomi_periods", 5))
        if ts == "canadian":
            rules["byoYomiStones"] = int(settings.get("byo_yomi_stones", 25))

        nigiri = bool(settings.get("nigiri", True))
        me = self._client.username
        if nigiri:
            # roles are placeholders; KGS decides color by nigiri. Owner (us) first.
            players = [{"role": "black", "name": me}, {"role": "white", "name": opponent_name}]
        else:
            my_role = "black" if settings.get("my_color", "B") == "B" else "white"
            opp_role = "white" if my_role == "black" else "black"
            players = [{"role": my_role, "name": me}, {"role": opp_role, "name": opponent_name}]

        return {
            "gameType": "ranked" if settings.get("ranked") else "free",
            "rules": rules,
            "nigiri": nigiri,
            "players": players,
        }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q`
Expected: PASS。

- [ ] **Step 5: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/platforms/kgs/adapter.py tests/platforms/test_kgs_adapter.py
git add katrain/web/platforms/kgs/adapter.py tests/platforms/test_kgs_adapter.py
git commit -m "feat(kgs): build valid KGS proposal (nested rules + owner-first players)"
```

---

### Task 3: KGS 连接后加入默认房间 + `get_online_users`（浏览棋友）

“浏览棋友→主动邀请”需要能列出房间在线用户。KGS 用户列表随房间来（`ROOM_JOIN`/房间用户）。MVP：`connect` 成功后从 `LOGIN_SUCCESS.rooms` 里加入第一个房间，`get_online_users` 返回该房间用户（可选按前缀过滤）。

**Files:**
- Modify: `katrain/web/platforms/kgs/adapter.py`（`connect`、`_on_room_join`、`get_online_users`、新增登录后 join 逻辑）
- Test: `tests/platforms/test_kgs_adapter.py`（追加）

**Interfaces:**
- Consumes: `KGSJsonClient.join_channel(channel_id)`（已有，json_client.py:175）、`OnlineUser`（models）。
- Produces: `get_online_users(room=None) -> list[OnlineUser]`（返回当前房间在线用户；`room` 作为用户名前缀过滤）；`self._rooms` 至少含一个已加入房间。

- [ ] **Step 1: 写失败测试**

追加到 `tests/platforms/test_kgs_adapter.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_on_room_join_populates_users_and_get_online_users_filters():
    a = _adapter_with_user("me")
    await a._on_room_join(
        {
            "channelId": 42,
            "name": "English Game Room",
            "users": [
                {"name": "alice", "rank": "5k", "flags": "c"},
                {"name": "bob", "rank": "1d", "flags": "c"},
                {"name": "alan", "rank": "8k", "flags": "c"},
            ],
        }
    )
    all_users = await a.get_online_users()
    names = {u.username for u in all_users}
    assert {"alice", "bob", "alan"} <= names
    # prefix filter (used by the /users?q= search)
    filtered = await a.get_online_users(room="al")
    assert {u.username for u in filtered} == {"alice", "alan"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q -k room_join`
Expected: FAIL（`get_online_users` 现返回 `[]`）。

- [ ] **Step 3: 实现房间用户缓存 + 过滤**

`katrain/web/platforms/kgs/adapter.py`：在 `__init__` 里加 `self._room_users: dict[int, list[dict]] = {}` 和 `self._default_room: Optional[int] = None`。改 `_on_room_join`：
```python
    async def _on_room_join(self, msg: dict) -> None:
        """Joined a room."""
        channel_id = msg.get("channelId")
        users = msg.get("users", [])
        self._rooms.append({"channelId": channel_id, "name": msg.get("name", ""), "users": users})
        self._room_users[channel_id] = users
        if self._default_room is None:
            self._default_room = channel_id
```
改 `get_online_users`：
```python
    async def get_online_users(self, room: Optional[str] = None) -> list[OnlineUser]:
        """Users in the joined room(s). `room` is treated as a username prefix filter."""
        raw: list[dict] = []
        for users in self._room_users.values():
            raw.extend(users)
        prefix = (room or "").strip().lower()
        out: list[OnlineUser] = []
        seen: set[str] = set()
        for u in raw:
            name = u.get("name", "")
            if not name or name in seen:
                continue
            if prefix and not name.lower().startswith(prefix):
                continue
            seen.add(name)
            disp, num = _parse_kgs_rank(u.get("rank", ""))
            flags = u.get("flags", "") or ""
            out.append(
                OnlineUser(
                    platform="kgs",
                    user_id=name,  # KGS keys players by name
                    username=name,
                    rank=disp,
                    rank_numeric=num,
                    status="playing" if "p" in flags else "idle",
                )
            )
        return out
```

- [ ] **Step 4: 连接后加入默认房间**

在 `connect` 成功分支里，登录后请求并加入一个房间。KGS 的 `LOGIN_SUCCESS` 携带 `rooms`；json_client 的 `login` 已把 `you` 存了，但没暴露 rooms。最小改动：`connect` 里读取登录响应的 rooms 并 join 第一个。为避免深挖 json_client 内部，改 `KGSJsonClient.login` 的 `on_success` 也存 `self._login_rooms = msg.get("rooms", [])`，并加只读属性 `login_rooms`。然后 `connect`：
```python
    async def connect(self, credentials: PlatformCredentials) -> bool:
        try:
            password = credentials.auth_data.get("password", "")
            success = await self._client.login(credentials.username, password)
            if success:
                self._connected = True
                self._register_events()
                for room in (self._client.login_rooms or [])[:1]:
                    rid = room.get("channelId")
                    if rid is not None:
                        await self._client.join_channel(rid)
            return success
        except Exception as e:
            logger.error(f"KGS connection failed: {e}")
            return False
```
在 `KGSJsonClient`：`__init__` 加 `self._login_rooms: list = []`；`login` 的 `on_success` 里加 `self._login_rooms = msg.get("rooms", [])`；加属性：
```python
    @property
    def login_rooms(self) -> list:
        return self._login_rooms
```

- [ ] **Step 5: 跑测试确认通过**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q`
Expected: PASS。

- [ ] **Step 6: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/platforms/kgs/
git add katrain/web/platforms/kgs/
git commit -m "feat(kgs): join default room on connect + list room users with prefix filter"
```

---

### Task 4: KGS `send_challenge`（在房间里对指定棋友发起邀请）+ 端点透传设置

补完 `send_challenge`：用已加入房间的 channelId + 真实 proposal（含对手名）发 `CHALLENGE_CREATE`。同时让 `POST /{platform}/challenge` 端点把完整设置透传给 adapter（现有 `PlatformChallengeRequest` 只有硬编码几项）。

**Files:**
- Modify: `katrain/web/platforms/kgs/adapter.py`（`send_challenge`）
- Modify: `katrain/web/api/v1/endpoints/platforms.py`（`PlatformChallengeRequest` 增字段；`send_challenge` 端点已 `req.model_dump()` 透传，确认字段齐全）
- Test: `tests/platforms/test_kgs_adapter.py`（追加，用 fake client 断言发出的消息）

**Interfaces:**
- Consumes: `self._default_room`、`_build_proposal(settings, opponent_name)`、`KGSJsonClient.challenge_create(room_channel_id, proposal, global_challenge)`。
- Produces: `send_challenge(user_id, settings) -> str`（`user_id`=对手 KGS 名；返回 challenge 标识串）。

- [ ] **Step 1: 写失败测试（用 fake client 捕获发出的消息）**

追加到 `tests/platforms/test_kgs_adapter.py`:
```python
class _FakeClient:
    def __init__(self, username="me"):
        self._username = username
        self.sent = []

    @property
    def username(self):
        return self._username

    async def challenge_create(self, room_channel_id, proposal, global_challenge=True):
        self.sent.append(("challenge_create", room_channel_id, proposal, global_challenge))


@pytest.mark.asyncio
async def test_send_challenge_creates_in_joined_room_targeting_opponent():
    a = KGSAdapter()
    a._client = _FakeClient("me")
    a._default_room = 42
    a._room_users = {42: [{"name": "rival", "rank": "2d"}]}
    cid = await a.send_challenge(
        "rival",
        {"board_size": 19, "rules": "chinese", "komi": 7.5, "handicap": 0,
         "time_system": "byo_yomi", "main_time": 1200, "byo_yomi_time": 30,
         "byo_yomi_periods": 5, "ranked": False, "nigiri": True, "my_color": "B"},
    )
    assert isinstance(cid, str) and cid
    assert len(a._client.sent) == 1
    kind, room, proposal, _ = a._client.sent[0]
    assert kind == "challenge_create"
    assert room == 42
    assert proposal["rules"]["size"] == 19
    assert {p["name"] for p in proposal["players"]} == {"me", "rival"}


@pytest.mark.asyncio
async def test_send_challenge_without_room_raises():
    a = KGSAdapter()
    a._client = _FakeClient("me")
    a._default_room = None
    with pytest.raises(RuntimeError):
        await a.send_challenge("rival", {"board_size": 19})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q -k send_challenge`
Expected: FAIL（现 `send_challenge` 用 `self._rooms[0]`、`_build_proposal` 旧签名、缺对手名）。

- [ ] **Step 3: 重写 `send_challenge`**

```python
    async def send_challenge(self, user_id: str, settings: dict) -> str:
        """Create a KGS challenge in the joined room, targeting `user_id` (opponent name)."""
        if self._default_room is None:
            raise RuntimeError("KGS: must be in a room before creating a challenge")
        proposal = self._build_proposal(settings, opponent_name=user_id)
        await self._client.challenge_create(self._default_room, proposal, global_challenge=True)
        return f"kgs-challenge-{self._default_room}-{user_id}"
```

- [ ] **Step 4: 端点透传完整设置**

`katrain/web/api/v1/endpoints/platforms.py`：给 `PlatformChallengeRequest`（Pydantic 模型，文件顶部附近）补字段（保留既有 `user_id`）：
```python
class PlatformChallengeRequest(BaseModel):
    user_id: str
    board_size: int = 19
    rules: str = "chinese"
    ranked: bool = False
    handicap: int = 0
    komi: float = 7.5
    nigiri: bool = True
    my_color: str = "B"
    time_system: str = "byo_yomi"
    main_time: int = 1200
    byo_yomi_time: int = 30
    byo_yomi_periods: int = 5
    byo_yomi_stones: int = 25
```
`send_challenge` 端点（platforms.py:434-444）已 `await adapter.send_challenge(req.user_id, req.model_dump())`，无需改逻辑——`req.model_dump()` 现在带全部字段。

- [ ] **Step 5: 跑测试确认通过**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q`
Expected: PASS。

- [ ] **Step 6: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/platforms/kgs/adapter.py katrain/web/api/v1/endpoints/platforms.py
git add katrain/web/platforms/kgs/adapter.py katrain/web/api/v1/endpoints/platforms.py tests/platforms/test_kgs_adapter.py
git commit -m "feat(kgs): send_challenge in joined room + pass full settings through the challenge endpoint"
```

---

### Task 5: 对手 PASS 处理 + 手数取自游戏状态（`_on_game_update`）

现有 `_on_game_update`：PASS 是 `# TODO`，手数是每 channel 朴素计数（易与真实手数错位）。修正：解析 PASS 并 `_emit("opponent_move", ...)` 用 pass 语义；手数从当前局面真实节点推导（用 sgfEvent 的 `nodeId` 或递增维护但以我方/对手都计入的方式）。MVP：把 PASS 表示为 `col=row=-1` 的 `PlatformMove`（下游 manager 需识别为 pass）。

**Files:**
- Modify: `katrain/web/platforms/kgs/adapter.py`（`_on_game_update`）
- Modify: `katrain/web/platforms/manager.py`（`_on_opponent_move`：识别 pass）
- Test: `tests/platforms/test_kgs_adapter.py`（追加）

**Interfaces:**
- Produces: 对手 PASS → `PlatformMove(col=-1, row=-1, color=..., move_number=..., game_id=...)`；`manager._on_opponent_move` 见到 `col<0` 调 `session.katrain("play", coords=None)`（KaTrain 的 pass）。

- [ ] **Step 1: 写失败测试**

追加到 `tests/platforms/test_kgs_adapter.py`:
```python
@pytest.mark.asyncio
async def test_on_game_update_emits_opponent_pass():
    a = _adapter_with_user("me")
    emitted = []

    async def cap(move):
        emitted.append(move)

    a.on_opponent_move(cap)
    a._game_channels[7] = {}
    await a._on_game_update(
        {
            "channelId": 7,
            "sgfEvents": [
                {"type": "MOVE", "loc": "PASS", "color": "white", "player": {"name": "rival"}}
            ],
        }
    )
    assert len(emitted) == 1
    assert emitted[0].col == -1 and emitted[0].row == -1
    assert emitted[0].color == "W"
    assert emitted[0].game_id == "7"


@pytest.mark.asyncio
async def test_on_game_update_skips_our_own_move():
    a = _adapter_with_user("me")
    emitted = []

    async def cap(move):
        emitted.append(move)

    a.on_opponent_move(cap)
    a._game_channels[7] = {}
    await a._on_game_update(
        {"channelId": 7, "sgfEvents": [
            {"type": "MOVE", "loc": {"x": 3, "y": 3}, "color": "black", "player": {"name": "me"}}]}
    )
    assert emitted == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q -k "pass or own_move"`
Expected: FAIL（PASS 目前被丢弃）。

- [ ] **Step 3: 修 `_on_game_update`（统一 MOVE/PASS，先判我方回显）**

替换 `_on_game_update` 的 sgfEvents 循环体：
```python
        for event in sgf_events:
            if event.get("type") != "MOVE":
                continue
            player_name = event.get("player", {}).get("name", "")
            if player_name == self._client.username:
                continue  # our own move echoed back
            color = (event.get("color", "") or "").upper()
            color = color[0] if color else "B"
            game_info = self._game_channels.get(channel_id, {})
            move_count = game_info.get("_move_count", 0) + 1
            game_info["_move_count"] = move_count
            loc = event.get("loc")
            if loc == "PASS":
                move = PlatformMove(col=-1, row=-1, color=color, move_number=move_count, game_id=str(channel_id))
            elif isinstance(loc, dict):
                move = PlatformMove(col=loc["x"], row=loc["y"], color=color, move_number=move_count, game_id=str(channel_id))
            else:
                continue
            await self._emit("opponent_move", move)
```

- [ ] **Step 4: manager 识别 pass**

`katrain/web/platforms/manager.py` `_on_opponent_move`：把落子调用改为区分 pass：
```python
            session = self._session_manager.get_session(ctx.session_id)
            if move.col < 0 or move.row < 0:
                session.katrain("play", coords=None)  # opponent pass
            else:
                session.katrain("play", coords=(move.col, move.row))
```

- [ ] **Step 5: 跑测试确认通过**

Run: `CI=true uv run pytest tests/platforms/test_kgs_adapter.py -q`
Expected: PASS。

- [ ] **Step 6: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/platforms/kgs/adapter.py katrain/web/platforms/manager.py
git add katrain/web/platforms/kgs/adapter.py katrain/web/platforms/manager.py tests/platforms/test_kgs_adapter.py
git commit -m "feat(kgs): handle opponent pass + skip own-move echo in game updates"
```

---

### Task 6: 注册 KGS adapter + 纳入契约/能力测试

把 KGS 注册进 server，纳入 `test_adapter_contract` 的 `ALL_ADAPTERS`，并加 KGS 能力断言。

**Files:**
- Modify: `katrain/web/server.py:252-256`（注册循环加 KGS）
- Modify: `tests/platforms/test_adapter_contract.py:8-13`（import + `ALL_ADAPTERS`）+ 追加 `TestKGSSpecific`

**Interfaces:**
- Produces: 运行期 `platform_manager` 含 `kgs` adapter；`GET /api/v1/platforms/status` 列出 kgs（`supports_live_play=True, rooms=True, scoring=False, automatch=False`）。

- [ ] **Step 1: 契约/能力测试（先失败）**

`tests/platforms/test_adapter_contract.py` 顶部加 import + 列表：
```python
from katrain.web.platforms.kgs.adapter import KGSAdapter
...
ALL_ADAPTERS = [OGSAdapter, FoxAdapter, GolaxyAdapter, KGSAdapter]
```
文件末尾追加：
```python
class TestKGSSpecific:
    def test_kgs_capabilities(self):
        a = KGSAdapter()
        assert a.platform_name == "kgs"
        assert a.supports_live_play is True
        assert a.supports_rooms is True
        assert a.supports_scoring is False
        assert a.supports_automatch is False

    def test_kgs_rank_parsing(self):
        from katrain.web.platforms.kgs.adapter import _parse_kgs_rank
        assert _parse_kgs_rank("5k")[0] == "5k"
        assert _parse_kgs_rank("3d")[0] == "3d"
        assert _parse_kgs_rank("")[0] == "?"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/platforms/test_adapter_contract.py -q`
Expected: FAIL（import 前 KGS 未在列表；或 KGS 未满足某契约——若失败，据报错修 adapter）。

- [ ] **Step 3: 注册 adapter**

`katrain/web/server.py` 注册循环加一行：
```python
    for adapter_path, name in [
        ("katrain.web.platforms.ogs.adapter", "OGS"),
        ("katrain.web.platforms.fox.adapter", "Fox"),
        ("katrain.web.platforms.golaxy.adapter", "Golaxy"),
        ("katrain.web.platforms.kgs.adapter", "KGS"),
    ]:
```

- [ ] **Step 4: 跑契约测试确认通过**

Run: `CI=true uv run pytest tests/platforms/test_adapter_contract.py -q`
Expected: PASS（KGS 走完整参数化契约 + KGS 能力断言）。

- [ ] **Step 5: Commit**

```bash
git add katrain/web/server.py tests/platforms/test_adapter_contract.py
git commit -m "feat(kgs): register adapter + add to contract/capability tests"
```

---

### Task 7: `start_platform_game` 配置本地局 + 设 `platform_guided_color`（live LED，方案 B）

live 开局要像人机一样：把本地 KaTrain 局的棋盘参数对齐远端，并标记“远端真人对手色”为 `platform_guided_color`，LED orchestrator 就会为对手落子点亮引导灯。

**Files:**
- Modify: `katrain/web/platforms/manager.py:121-144`（`start_platform_game`）
- Test: `tests/platforms/test_kgs_live_manager.py`（Create）

**Interfaces:**
- Consumes: `PlatformGameSession`（含 `my_color, board_size, handicap, komi, rules`）、`session.katrain("edit_game", ..., platform_guided_color=...)`（Task 1 改名后）。
- Produces: 本地 session 的 `get_state()["platform_guided_color"]` == 远端对手色。

- [ ] **Step 1: 写失败测试（真实 session 栈）**

Create `tests/platforms/test_kgs_live_manager.py`（参照 `tests/platforms/test_engine_manager.py` 的 session/manager 搭法）:
```python
import pytest

from katrain.web.session import SessionManager
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformGameSession, OnlineUser, TimeControl


def _gs(my_color="B"):
    return PlatformGameSession(
        platform="kgs", game_id="7", board_size=19, my_color=my_color,
        opponent=OnlineUser(platform="kgs", user_id="rival", username="rival", rank="2d", rank_numeric=31),
        time_control=TimeControl(system="byo_yomi", main_time=1200, period_time=30, periods=5),
        rules="chinese", ranked=False, handicap=0, komi=7.5,
    )


@pytest.mark.asyncio
async def test_start_platform_game_sets_guided_color_to_opponent():
    sm = SessionManager()
    pm = PlatformManager(sm, credential_store=None)
    # human plays Black -> opponent (guided) is White
    sid = await pm.start_platform_game("kgs", _gs("B"), user_id=1)
    state = sm.get_session(sid).katrain.get_state()
    assert state["platform_guided_color"] == "W"
    assert state["board_size"] == [19, 19]
    assert state["komi"] == 7.5


@pytest.mark.asyncio
async def test_start_platform_game_human_white_guides_black():
    sm = SessionManager()
    pm = PlatformManager(sm, credential_store=None)
    sid = await pm.start_platform_game("kgs", _gs("W"), user_id=1)
    assert sm.get_session(sid).katrain.get_state()["platform_guided_color"] == "B"
```
（若 `PlatformManager(sm, credential_store=None)` 构造签名不符，照 `test_engine_manager.py` 里的实际构造方式对齐。）

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/platforms/test_kgs_live_manager.py -q`
Expected: FAIL（现 `start_platform_game` 不调 edit_game，`platform_guided_color` 为 None）。

- [ ] **Step 3: 在 `start_platform_game` 里配置本地局 + 设引导色**

`start_platform_game`（manager.py:121）在建好 session 后、返回前，插入 edit_game（镜像 `start_engine_game` 的做法）：
```python
        guided_color = "W" if game_session.my_color == "B" else "B"
        session.katrain(
            "edit_game",
            size=game_session.board_size,
            handicap=game_session.handicap,
            komi=game_session.komi,
            rules=game_session.rules,
            platform_guided_color=guided_color,
        )
```
放在 `ctx = PlatformGameContext(...)` 之前。

- [ ] **Step 4: 跑测试确认通过**

Run: `CI=true uv run pytest tests/platforms/test_kgs_live_manager.py -q`
Expected: PASS。

- [ ] **Step 5: 物理编排回归（LED 会为 live 对手亮灯）**

Run: `CI=true uv run pytest tests/test_physical_play_orchestrator.py -q`
Expected: PASS（引导逻辑现认 `platform_guided_color`，人机用例仍绿）。

- [ ] **Step 6: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/platforms/manager.py tests/platforms/test_kgs_live_manager.py
git add katrain/web/platforms/manager.py tests/platforms/test_kgs_live_manager.py
git commit -m "feat(platform): live game configures local board + sets platform_guided_color (LED for remote human)"
```

---

### Task 8: `_on_game_started` 接通开局 + 用 LobbyManager 通知发起方导航

现 `_on_game_started`（manager.py:337）是空 log，live 开局在此断链。要：对手接受→adapter join→`GAME_JOIN`→adapter emit `game_started` → manager `_on_game_started` **创建本地 session（`start_platform_game`）+ 通过 lobby WS 通知发起用户带上 session_id**（前端此刻还在大厅页、没进对局 session，只能靠 user 级通道）。为此给 `LobbyManager` 加 `send_to_user`。

**Files:**
- Modify: `katrain/web/session.py`（`LobbyManager.send_to_user`）
- Modify: `katrain/web/platforms/manager.py:337-338`（`_on_game_started`）+ 确认能拿到 `lobby_manager` 与 `user_id`
- Modify: `katrain/web/server.py`（把 `app.state.lobby_manager` 传给 `PlatformManager`，或让 manager 可访问）
- Test: `tests/platforms/test_kgs_live_manager.py`（追加）

**Interfaces:**
- Consumes: `self._platform_user_ids[platform]`（owning user_id）、`start_platform_game(...)`。
- Produces: `LobbyManager.send_to_user(user_id, payload)`；`_on_game_started` 触发后，owning user 的 lobby WS 收到 `{"type":"platform_game_started","platform":"kgs","session_id":...,"game":{...}}`。

- [ ] **Step 1: LobbyManager.send_to_user 测试（先失败）**

追加到 `tests/platforms/test_kgs_live_manager.py`:
```python
class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_lobby_send_to_user_targets_only_that_user():
    from katrain.web.session import LobbyManager
    lm = LobbyManager()
    ws1, ws2 = _FakeWS(), _FakeWS()
    lm.add_user(1, ws1)
    lm.add_user(2, ws2)
    await lm.send_to_user(1, {"type": "platform_game_started", "session_id": "abc"})
    assert ws1.sent == [{"type": "platform_game_started", "session_id": "abc"}]
    assert ws2.sent == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/platforms/test_kgs_live_manager.py -q -k send_to_user`
Expected: FAIL（无 `send_to_user`）。

- [ ] **Step 3: 加 `LobbyManager.send_to_user`**

`katrain/web/session.py` `LobbyManager` 内：
```python
    async def send_to_user(self, user_id: int, payload: Dict):
        with self._lock:
            sockets = list(self._online_users.get(user_id, ()))
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                pass
```

- [ ] **Step 4: 让 PlatformManager 能拿到 lobby_manager**

`katrain/web/server.py` `_init_platform_manager`：构造后注入
```python
    platform_manager.lobby_manager = app.state.lobby_manager
```
（`app.state.lobby_manager` 已在启动时建；若构造顺序上 lobby_manager 尚未存在，把该注入移到 lobby_manager 建好之后。）
`PlatformManager.__init__` 里加默认 `self.lobby_manager = None`。

- [ ] **Step 5: 实现 `_on_game_started`（创建 session + 通知发起方）**

`katrain/web/platforms/manager.py`：
```python
    async def _on_game_started(self, game_session: PlatformGameSession) -> None:
        logger.info(f"Game started event from {game_session.platform}: {game_session.game_id}")
        if game_session.game_id in self._active_games:
            return  # already bridged (e.g. via accept_challenge endpoint)
        user_id = self._platform_user_ids.get(game_session.platform)
        if user_id is None:
            logger.warning(f"game_started for {game_session.platform} but no owning user; cannot bridge")
            return
        session_id = await self.start_platform_game(game_session.platform, game_session, user_id)
        if self.lobby_manager is not None:
            await self.lobby_manager.send_to_user(
                user_id,
                {
                    "type": "platform_game_started",
                    "platform": game_session.platform,
                    "session_id": session_id,
                    "game": {
                        "game_id": game_session.game_id,
                        "my_color": game_session.my_color,
                        "opponent": game_session.opponent.username,
                        "board_size": game_session.board_size,
                    },
                },
            )
```

- [ ] **Step 6: 集成测试（fake adapter emit game_started → 通知发起方）**

追加到 `tests/platforms/test_kgs_live_manager.py`:
```python
@pytest.mark.asyncio
async def test_game_started_bridges_session_and_notifies_owner():
    from katrain.web.session import LobbyManager
    sm = SessionManager()
    pm = PlatformManager(sm, credential_store=None)
    lm = LobbyManager()
    ws = _FakeWS()
    lm.add_user(1, ws)
    pm.lobby_manager = lm
    pm._platform_user_ids["kgs"] = 1
    await pm._on_game_started(_gs("B"))
    started = [m for m in ws.sent if m.get("type") == "platform_game_started"]
    assert len(started) == 1
    sid = started[0]["session_id"]
    assert sm.get_session(sid).katrain.get_state()["platform_guided_color"] == "W"
```

- [ ] **Step 7: 跑测试确认通过**

Run: `CI=true uv run pytest tests/platforms/test_kgs_live_manager.py -q`
Expected: PASS。

- [ ] **Step 8: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/session.py katrain/web/platforms/manager.py katrain/web/server.py
git add katrain/web/session.py katrain/web/platforms/manager.py katrain/web/server.py tests/platforms/test_kgs_live_manager.py
git commit -m "feat(platform): bridge live game_started -> session + notify owner via lobby (send_to_user)"
```

---

### Task 9: 前端 A — `PLATFORM_META` 加 kgs + KGS 发起对局设置面板（对齐 KGS 字段）

加 kgs 平台卡元数据；新建一个“发起对局”设置面板组件，字段对齐 KGS `Rules`/`Proposal`（对局类型/棋盘/规则/让子/贴目/时间制式联动/猜先）。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx:18-32`（PLATFORM_META 加 kgs）
- Create: `katrain/web/ui/src/kiosk/components/platform/KgsChallengeSettings.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/KgsChallengeSettings.test.tsx`

**Interfaces:**
- Produces: `type KgsChallengeValues = { board_size:number; rules:string; komi:number; handicap:number; ranked:boolean; nigiri:boolean; my_color:'B'|'W'; time_system:'none'|'absolute'|'byo_yomi'|'canadian'; main_time:number; byo_yomi_time:number; byo_yomi_periods:number; byo_yomi_stones:number }`；
  组件 `KgsChallengeSettings({ value, onChange }: { value: KgsChallengeValues; onChange:(v:KgsChallengeValues)=>void })`；导出 `DEFAULT_KGS_CHALLENGE: KgsChallengeValues`（慢棋友好默认：19 路 / chinese / komi 7.5 / byo_yomi / main 1200s / 30s×5 / nigiri）。

- [ ] **Step 1: 写失败测试**

Create `katrain/web/ui/src/kiosk/__tests__/KgsChallengeSettings.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import KgsChallengeSettings, { DEFAULT_KGS_CHALLENGE } from '../components/platform/KgsChallengeSettings';

describe('KgsChallengeSettings', () => {
  it('defaults are slow-play friendly and KGS-valid', () => {
    expect(DEFAULT_KGS_CHALLENGE.time_system).toBe('byo_yomi');
    expect(DEFAULT_KGS_CHALLENGE.board_size).toBe(19);
    expect(DEFAULT_KGS_CHALLENGE.main_time).toBeGreaterThanOrEqual(600);
    expect(['japanese', 'chinese', 'aga', 'new_zealand']).toContain(DEFAULT_KGS_CHALLENGE.rules);
  });

  it('shows byo-yomi period field only for byo_yomi time system', () => {
    const onChange = vi.fn();
    const { rerender } = render(<KgsChallengeSettings value={DEFAULT_KGS_CHALLENGE} onChange={onChange} />);
    expect(screen.getByTestId('kgs-byo-periods')).toBeTruthy();
    rerender(<KgsChallengeSettings value={{ ...DEFAULT_KGS_CHALLENGE, time_system: 'canadian' }} onChange={onChange} />);
    expect(screen.queryByTestId('kgs-byo-periods')).toBeNull();
    expect(screen.getByTestId('kgs-byo-stones')).toBeTruthy();
  });

  it('emits changes through onChange', () => {
    const onChange = vi.fn();
    render(<KgsChallengeSettings value={DEFAULT_KGS_CHALLENGE} onChange={onChange} />);
    fireEvent.click(screen.getByTestId('kgs-ranked-toggle'));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ ranked: true }));
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KgsChallengeSettings.test.tsx`
Expected: FAIL（组件不存在）。

- [ ] **Step 3: 实现设置面板组件**

Create `katrain/web/ui/src/kiosk/components/platform/KgsChallengeSettings.tsx`（MUI，`t()` 中文默认，字段对齐 KGS；数值型子字段随 `time_system` 联动显隐；给关键控件 `data-testid`）：
```tsx
import { Box, MenuItem, TextField, FormControlLabel, Switch } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';

export type KgsChallengeValues = {
  board_size: number; rules: string; komi: number; handicap: number;
  ranked: boolean; nigiri: boolean; my_color: 'B' | 'W';
  time_system: 'none' | 'absolute' | 'byo_yomi' | 'canadian';
  main_time: number; byo_yomi_time: number; byo_yomi_periods: number; byo_yomi_stones: number;
};

export const DEFAULT_KGS_CHALLENGE: KgsChallengeValues = {
  board_size: 19, rules: 'chinese', komi: 7.5, handicap: 0,
  ranked: false, nigiri: true, my_color: 'B',
  time_system: 'byo_yomi', main_time: 1200, byo_yomi_time: 30, byo_yomi_periods: 5, byo_yomi_stones: 25,
};

const RULES = [
  ['japanese', '日式'], ['chinese', '中式'], ['aga', 'AGA'], ['new_zealand', '新西兰'],
] as const;
const TIME_SYSTEMS = [
  ['none', '不计时'], ['absolute', '包干'], ['byo_yomi', '读秒'], ['canadian', '加拿大'],
] as const;

export default function KgsChallengeSettings(
  { value, onChange }: { value: KgsChallengeValues; onChange: (v: KgsChallengeValues) => void }
) {
  const { t } = useTranslation();
  const set = <K extends keyof KgsChallengeValues>(k: K, v: KgsChallengeValues[K]) =>
    onChange({ ...value, [k]: v });
  const ts = value.time_system;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <TextField select size="small" label={t('Game type', '对局类型')}
        value={value.ranked ? 'ranked' : 'free'}
        onChange={(e) => set('ranked', e.target.value === 'ranked')}
        inputProps={{ 'data-testid': 'kgs-ranked-select' }}>
        <MenuItem value="free">{t('Free', '免费')}</MenuItem>
        <MenuItem value="ranked">{t('Ranked', '排位')}</MenuItem>
      </TextField>
      <FormControlLabel
        control={<Switch checked={value.ranked} onChange={(e) => set('ranked', e.target.checked)}
          inputProps={{ 'data-testid': 'kgs-ranked-toggle' } as any} />}
        label={t('Ranked', '排位')} />
      <TextField select size="small" label={t('Board size', '棋盘')} value={value.board_size}
        onChange={(e) => set('board_size', Number(e.target.value))}>
        {[19, 13, 9].map((s) => <MenuItem key={s} value={s}>{s}×{s}</MenuItem>)}
      </TextField>
      <TextField select size="small" label={t('Rules', '规则')} value={value.rules}
        onChange={(e) => set('rules', e.target.value)}>
        {RULES.map(([v, cn]) => <MenuItem key={v} value={v}>{t(v, cn)}</MenuItem>)}
      </TextField>
      <TextField type="number" size="small" label={t('Handicap', '让子')} value={value.handicap}
        onChange={(e) => set('handicap', Math.max(0, Math.min(9, Number(e.target.value))))} />
      <TextField type="number" size="small" label={t('Komi', '贴目')} value={value.komi}
        onChange={(e) => set('komi', Number(e.target.value))} inputProps={{ step: 0.5 }} />
      <FormControlLabel
        control={<Switch checked={value.nigiri} onChange={(e) => set('nigiri', e.target.checked)} />}
        label={t('Nigiri (random color)', '猜先（随机执子）')} />
      {!value.nigiri && (
        <TextField select size="small" label={t('My color', '我方执子')} value={value.my_color}
          onChange={(e) => set('my_color', e.target.value as 'B' | 'W')}>
          <MenuItem value="B">{t('Black', '黑')}</MenuItem>
          <MenuItem value="W">{t('White', '白')}</MenuItem>
        </TextField>
      )}
      <TextField select size="small" label={t('Time system', '时间制式')} value={ts}
        onChange={(e) => set('time_system', e.target.value as KgsChallengeValues['time_system'])}>
        {TIME_SYSTEMS.map(([v, cn]) => <MenuItem key={v} value={v}>{t(v, cn)}</MenuItem>)}
      </TextField>
      {ts !== 'none' && (
        <TextField type="number" size="small" label={t('Main time (s)', '主时间（秒）')} value={value.main_time}
          onChange={(e) => set('main_time', Number(e.target.value))} />
      )}
      {(ts === 'byo_yomi' || ts === 'canadian') && (
        <TextField type="number" size="small" label={t('Byo-yomi time (s)', '读秒时长（秒）')} value={value.byo_yomi_time}
          onChange={(e) => set('byo_yomi_time', Number(e.target.value))} />
      )}
      {ts === 'byo_yomi' && (
        <TextField type="number" size="small" label={t('Byo-yomi periods', '读秒次数')} value={value.byo_yomi_periods}
          onChange={(e) => set('byo_yomi_periods', Number(e.target.value))}
          inputProps={{ 'data-testid': 'kgs-byo-periods' }} />
      )}
      {ts === 'canadian' && (
        <TextField type="number" size="small" label={t('Stones per period', '每段子数')} value={value.byo_yomi_stones}
          onChange={(e) => set('byo_yomi_stones', Number(e.target.value))}
          inputProps={{ 'data-testid': 'kgs-byo-stones' }} />
      )}
    </Box>
  );
}
```

- [ ] **Step 4: PLATFORM_META 加 kgs**

`katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx` 的 `PLATFORM_META` 加：
```tsx
  kgs: {
    label: 'KGS', labelCn: 'KGS', color: '#7e57c2',
    login: { userLabel: 'Username', userLabelCn: '用户名', passLabel: 'Password', passLabelCn: '密码' },
  },
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KgsChallengeSettings.test.tsx`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx katrain/web/ui/src/kiosk/components/platform/KgsChallengeSettings.tsx katrain/web/ui/src/kiosk/__tests__/KgsChallengeSettings.test.tsx
git commit -m "feat(kiosk): KGS platform meta + KGS-aligned challenge settings panel"
```

---

### Task 10: 前端 B — 大厅 WS 接通 `onGameStarted` 导航 + 实时对局路由 + GamePage live 支持

把 live 开局的“最后一公里”接起来：`PlatformLobbyPage` 用设置面板发起邀请、开 lobby WS、收到 `platform_game_started` 就 `navigate` 到新的实时对局路由；`KioskApp` 加该路由；`GamePage` 在 live 模式下不显示“AI 已落子”横幅、挂上已存在但未接的 `PlatformTimer`/`PlatformBadge`。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`（加 `play/cross-platform/live/game/:sessionId`）
- Modify: `katrain/web/ui/src/api.ts`（`platformSendChallenge` 传完整设置；返回类型）
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（live：`aiColor` 为 null 时不显示 AI 横幅；挂 PlatformTimer/Badge）
- Create/Modify test: `katrain/web/ui/src/kiosk/__tests__/PlatformLobbyPage.test.tsx`

**Interfaces:**
- Consumes: `usePlatformEvents(wsRef, { onGameStarted })`（已有）、`DEFAULT_KGS_CHALLENGE`/`KgsChallengeSettings`（Task 9）、`deriveHumanColor`（Task 1 改名后对 live 已正确：live 有 `platform_guided_color`）。
- Produces: 实时对局路由 `#/kiosk/play/cross-platform/live/game/:sessionId`；`onGameStarted` → `navigate('/kiosk/play/cross-platform/live/game/'+sessionId)`。

- [ ] **Step 1: 写失败测试（大厅收到 game_started 就导航）**

Create/patch `katrain/web/ui/src/kiosk/__tests__/PlatformLobbyPage.test.tsx`（用 mock 的 WS + mocked `useNavigate`，参照 `PlatformConnectPage.test.tsx` 的 mock 方式）:
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

const navigate = vi.fn();
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<any>()),
  useNavigate: () => navigate,
  useSearchParams: () => [new URLSearchParams('platform=kgs')],
}));

// TODO(impl): mock useAuth -> token, API.platformStatus/platformUsers, and the
// lobby WebSocket so a 'platform_game_started' message drives navigation.

import PlatformLobbyPage from '../pages/PlatformLobbyPage';

describe('PlatformLobbyPage live start', () => {
  it('navigates to the live game route when platform_game_started arrives', async () => {
    render(<PlatformLobbyPage />);
    // simulate the lobby WS delivering a game_started event (helper set up in impl)
    (globalThis as any).__emitLobby?.({
      type: 'platform_game_started', platform: 'kgs', session_id: 'sess-1', game: {},
    });
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/live/game/sess-1')
    );
  });
});
```
（实现时把 WS 抽象成可注入/可 mock 的小 hook，使 `__emitLobby` 能驱动事件；测试细节随实现的 mock 方式微调，但断言“收到 game_started → navigate 到 live 路由”不变。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PlatformLobbyPage.test.tsx`
Expected: FAIL（大厅当前不开 WS、`handleChallenge` 只弹 toast、无 navigate）。

- [ ] **Step 3: 加实时对局路由**

`katrain/web/ui/src/kiosk/KioskApp.tsx`：在顶部无导航栏区块（与 engine game 同款）加一行，紧邻第 57 行：
```tsx
        <Route path="play/cross-platform/live/game/:sessionId" element={<PhysicalBoardGuard requireRecognition><GamePage /></PhysicalBoardGuard>} />
```
（注意：不传 `engineMode`——live 不是引擎局；`GamePage` 靠 `platform_guided_color` 识别引导方。）

- [ ] **Step 4: `PlatformLobbyPage` 接 WS + 设置面板 + 导航**

改造 `PlatformLobbyPage.tsx`：
1) 打开 lobby WS：`const wsRef = useRef<WebSocket|null>(null)`，`useEffect` 里 `new WebSocket(\`\${wsBase}/ws/lobby?token=\${token}\`)`（base 用与 GamePage/useGameSession 相同的推导；可复用现有工具）。
2) `usePlatformEvents(wsRef, { onGameStarted: (_p, sid) => navigate(\`/kiosk/play/cross-platform/live/game/\${sid}\`) })`。
3) “挑战”对话框内嵌 `KgsChallengeSettings`（当 `activePlatform==='kgs'`；其他平台保留原简单确认）：
```tsx
const [challengeSettings, setChallengeSettings] = useState(DEFAULT_KGS_CHALLENGE);
...
const handleChallenge = async (user: PlatformUser) => {
  if (!token) return;
  try {
    await API.platformSendChallenge(activePlatform, {
      user_id: user.user_id,
      ...(activePlatform === 'kgs' ? challengeSettings : { board_size: 19, rules: 'chinese', ranked: true }),
    }, token);
    setToast({ message: t('Challenge sent, waiting for opponent…', '已发起邀请，等待对手接受…'), severity: 'success' });
    setChallengeTarget(null);
  } catch (e: any) {
    setToast({ message: e.message || t('Challenge failed', '发起失败'), severity: 'error' });
  }
};
```
在挑战对话框 `<DialogContent>` 里，当 `activePlatform==='kgs'` 渲染 `<KgsChallengeSettings value={challengeSettings} onChange={setChallengeSettings} />`。

- [ ] **Step 5: `api.ts` 透传完整设置**

`platformSendChallenge` 已是 `(platform, data: object, token)`，无需签名改动；确认调用方传完整对象即可。若要类型收紧，可加：
```ts
export interface KgsChallengePayload {
  user_id: string; board_size: number; rules: string; komi: number; handicap: number;
  ranked: boolean; nigiri: boolean; my_color: 'B' | 'W'; time_system: string;
  main_time: number; byo_yomi_time: number; byo_yomi_periods: number; byo_yomi_stones: number;
}
```
（可选；不改运行行为。）

- [ ] **Step 6: `GamePage` live 分支（不误报 AI 横幅 + 挂时钟/徽标）**

`GamePage.tsx`：AI 已落子横幅只应在 `aiColor !== null` 时显示。`deriveHumanColor` 对 live 返回本地人色、`aiColor` 由既有 `deriveAiTurnState` 依据 `platform_guided_color`/`player:ai` 计算——live 局 `platform_guided_color` 非空，故引导方即“对手方”。确认 AI 横幅文案在 live 时改为中性“对手已落子，请在实体棋盘对应点摆放对方棋子”，或复用现有横幅但依据 `engineMode===false && platform_guided_color` 显示“对手已落子”。最小实现：横幅文案根据 `engineMode` 选词：
```tsx
{engineMode ? t('AI played', 'AI 已落子') : t('Opponent played', '对手已落子')} <b>{aiMoveBanner}</b> · ...
```
并在右栏挂上已存在的 `PlatformTimer`（`clock` 来自 `usePlatformEvents`）与 `PlatformBadge`（当 `platform_guided_color` 存在）。import 两个组件并按 `!engineMode && gameState.platform_guided_color` 渲染。

- [ ] **Step 7: 跑前端测试确认通过**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PlatformLobbyPage.test.tsx src/kiosk/__tests__/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx`
Expected: PASS（新导航测试过；GamePage 引擎/非引擎既有用例不回归）。

- [ ] **Step 8: 两个构建都过（共享文件 api.ts 被动）**

Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d`
Expected: 两个构建都成功（kiosk-2d 的 `verify:kiosk-2d` 无 three.js 泄漏）。

- [ ] **Step 9: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx katrain/web/ui/src/kiosk/KioskApp.tsx katrain/web/ui/src/api.ts katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/__tests__/PlatformLobbyPage.test.tsx
git commit -m "feat(kiosk): live KGS game — lobby WS navigation, live route, GamePage live mode (timer/badge, no AI banner)"
```

---

## 端到端手测（MVP 验收，非自动化）

在能联网的机器/kiosk 上，用两个 KGS 账号（或找一位真人）验收整条链路：
1. kiosk 登录 KGS → 平台卡显示 KGS「实时对弈/房间」能力 → 进大厅，看到房间在线棋友列表。
2. 选一名棋友 → 弹出对齐 KGS 的设置面板（慢棋默认）→ 发起邀请 → toast「等待对手接受」。
3. 对手在 KGS 客户端接受 → kiosk 自动跳转到实时对局页（`.../live/game/:sessionId`）。
4. 我方在实体棋盘落子 → vision 识别 → KGS 收到我方着手；对手在 KGS 落子 → kiosk LED 点亮对应交叉点，提示摆放对手棋子。
5. 走到终局（含 PASS/认输）→ 结果正确显示。
> 复用 mac kiosk 启动流程见 memory `reference_mac_kiosk_launch`；`/ws/vision` 路由顺序坑见 `reference_ws_vision_route_order`。

---

## 后续路线图（本计划不实现，仅登记）

- **接受对方邀请**（`accept_challenge` + 前端收到 `platform_challenge` 的来邀 UI）——反向匹配。
- **房间/公开对局列表浏览** + 房间选择 UI（当前 MVP 固定加入登录默认房间）。
- **点目 UI**：KGS 服务端点目，`supports_scoring=False`；MVP 依赖 KGS 自身流程，后续可加 dead-stone 标记/确认。
- **断线重连硬化**：长轮询断连恢复、`needs_resync` 快照重放（`fetch_game_snapshot`）。
- **排位账号政策确认**：`ranked` 局与 KGS `authLevel`/`=`(can-play-ranked) 标志的关系；上线前核对。
- **像素级 UI 视觉对齐**：在能联网机器/kiosk 上跑 `/browse` 对照 KGS 真实 New Game 对话框做视觉细化（本计划字段语义已对齐，视觉未对齐——本机 fake-IP 代理触发 browse SSRF 拦截，见 research 记录）。
- **时钟精细化**：`PlatformTimer` 与 KGS `GAME_STATE.clocks` 的字段映射打磨（MVP 先挂上，展示可能粗糙）。

---

## 计划自检（写完对照 spec）

- **Spec 覆盖**：匹配=浏览棋友+邀请(Task 3/4/10)✓；时限/排位每局自选+对齐 KGS 设置页(Task 9)✓；LED 方案 B(Task 1/7)✓；live 开局接通(Task 8/10)✓；坐标 identity（无需任务，Global Constraints 记录）✓；MVP+路线图✓。
- **类型一致**：后端 `platform_guided_color`（Task 1 起全仓统一）；`_build_proposal(settings, opponent_name)` 签名在 Task 2 定义、Task 4 调用一致；`send_to_user` 在 Task 8 定义并自用；前端 `KgsChallengeValues`/`DEFAULT_KGS_CHALLENGE`(Task 9) 被 Task 10 消费；`onGameStarted(platform, sessionId, game)` 签名沿用既有 `usePlatformEvents`。
- **无占位符**：各 Task 均含真实代码/命令/预期。
- **已知留白（有意，非占位）**：Task 7/8 的 `PlatformManager(sm, credential_store=None)` 构造与 `_platform_user_ids` 赋值，需对齐 `tests/platforms/test_engine_manager.py` 里既有的真实构造/连接方式；Task 10 的 lobby WS mock 细节随实现的注入方式微调。这些是“照现有测试搭法对齐”，不是待补逻辑。
