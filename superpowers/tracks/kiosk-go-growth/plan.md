# 围棋 kiosk · 成长(kiosk-go-growth)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让成长屏(屏 22)说三句今天说不出来的真话:① 胜率覆盖所有**算得出执色**的对局,不再只有升降级局;② 「能力诊断」按开局 / 中盘 / 官子三段算出失误率并写明样本量,不再是写死的「样本 0 局」加一个标错的蓝标;③ 左栏一条近 30 天**档位**走势(Fan 2026-09-21 裁定),没有对局的那天不补点。

**Architecture:** 后端为主 + 一屏前端。
- G2:`user_games` 加一列 `user_color`(可空),在**知道的落账路径**上写它(人机局 = 人坐的那一方;面对面 / 导入 / 研究 = NULL,不猜);`growth/summary` 多回三个字段;屏上那一格换标签并在有「算不出执色的局」时说一句。
- G1:新建纯函数 `core/growth_diagnosis.py`(分桶)+ 仓储查询 + `GET /growth/diagnosis`(照抄 `growth/summary` 的三档 `authority` 与四种退回原因);屏上那块换成真数据 + 样本量。
- G3:`ai_ladder_repo.rung_trend()` 并进 `growth/summary` 的响应(**不另开端点** —— 那条链已经有云端优先与三档 `authority`);左栏一条纯 SVG 折线,**不引图表库**。
- G1 **依赖 G2**:诊断只数「本用户执的那一方」的手,而那个事实就是 G2 加的那一列。

**Tech Stack:** FastAPI + SQLAlchemy 2.0(SQLite 开发 / PG 生产,**无 alembic**,加列走 `core/migrations.py`);React 18 + TypeScript + Vite;pytest;vitest + @testing-library/react;Playwright(四图与承重)。

**Spec:** `superpowers/tracks/kiosk-go-growth/prd.md`

## 执行中的更正(2026-09-22,核对真实代码后)

> 下面各 Task 正文保留原样作为当时的设想;**与本节冲突时以本节为准**。

**流程**:按垂直切片执行 —— 三个切片的前端先做完、四图经 Fan 确认(2026-09-22「过」,连同契约),
再按 G2 → G1 → G3 做后端。

**G2(Task 2/3)**
1. `_user_seat` 放在 `server.py` **模块顶层**(`_record_platform_engine_game` 旁边):计划写的「与
   `_record_ai_game_locked` 同一层」是 `create_app` 里的嵌套函数,测试 import 不到;也避开视觉赛道
   正在改的 `create_app` 前那一段(:761-826)。
2. **计划漏了盒子 → 云端那一跳**:盒上的局是 POST 云端 `/api/v1/user-games/` 写进去的,
   `UserGameCreate` 没有 `user_color` 时 pydantic 静默丢掉。已加 `Optional[Literal["B","W"]]`,
   本机落库那一支也透传。
3. **云端建升降级对局行**(`AiLadderRankedRepository._create_or_validate_user_game`)也要写执色,
   取自预约记录 `row.user_color`;不进 `expected` 比对(老行是 NULL)。盒子的结算载荷按白名单
   `GAME_RECORD_FIELDS` 转发(`AiLadderGameRecordPayload` 是 `extra="forbid"`),`user_color`
   不在白名单里 —— 这正是它不会把结算同步打成 422 的原因,**别把它加进白名单**。
4. `decided_since` 的执色 = `COALESCE(user_games.user_color, ai_ladder_game_ledger.user_color)`:
   这一列诞生之前的升降级局在账本里早就记着执色,读它不是追认;不读的话部署当天只下升降级的人
   胜率会从有数变成「—」最长 30 天。其余历史行仍不回填。
5. 计划说 `rankedWinrate` 有 galaxy 在用 —— 实际只有 `GrowthPage` 一个调用者。
6. `tests/platforms/test_growth_summary.py` 原先断言 `UserGame` **没有** `user_color` —— 前提变了,那句删掉。
7. `black` 只对基线上本来就 black 干净的文件整文件跑;`models_db.py` / `server.py` /
   `test_growth_authority.py` 在基线上不干净,整文件跑会带出几十行无关改动(其中一处在视觉赛道的区域),
   这三份只手写自己的那几行。
8. **部署顺序:先云端再盒子。** 老云端会静默丢掉新盒子传来的 `user_color`,那些局永远算不进胜率。

**G3(Task 8)**
9. 类名是 `AiLadderRankedRepository`,不是 `AiLadderRepository`;计划里的账本种子过不了
   `ck_ai_ladder_ledger_decision`(counted 的行要 config_snapshot / certified / available / route),
   照 `tests/platforms/test_growth_summary.py::_ledger` 造。
10. 前端纯函数改名 `trendGeometry.ts`:`rungTrend.ts` 与 `RungTrend.tsx` 在 macOS 大小写不敏感的
    文件系统上互相顶替。横轴是近 30 天窗口本身(不是首末两点拉满),窗口外的点丢掉。

**G4(Task 8b,2026-09-22 Fan 新增)**
11. G1–G3 四图确认后 Fan 加了「近一年练棋日历」,裁定与契约见 `prd.md` §3 G4。前端与重出的参考图
    已在 `0739d220`;Task 8b 只展开后端与集成。日历进右栏后第一次量最满态溢出 94px,为此诊断块三段
    行距 12→8、三句样本说明并成一段 —— **已确认过的 G1 诊断块因此微调**,四图里看得见。

## Global Constraints

> **开工前先读 `prd.md` §6.0**:四条新赛道的共享文件归属与合并顺序。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-growth`(分支 `feature/kiosk-go-growth`,基线 develop `7a152df1`)里开发;**不 push、不合并 develop**,合并与部署由 Fan 决定。
- 新 worktree 的 Python 环境:`uv sync --extra web`。**光 `uv sync` 会缺 fastapi**,而缺了它整批 web 测试会在收集阶段就错,基线静默变成空集合。
- 跑测试:`CI=true uv run pytest tests/web_ui/test_growth_diagnosis.py -q`;全量基线用
  `CI=true uv run pytest tests --continue-on-collection-errors -q`,并用 `grep '^FAILED\|^ERROR'` 取名字集合(仓里有未声明依赖会让某些文件收集失败,这是既有噪声,靠基线 diff 排除)。
- Python 格式化:`uv run black -l 120 <文件>`(120 列)。
- **不碰 `_finish_ended_game`**(上一轮定的终局收尾唯一入口)。本赛道在 `server.py` 只加两个键。
- **不回填历史行**:`user_color` 诞生之前的行没有这个事实,追认就是编。
- `user_games` / `report_tasks` **不是** `PROTECTED_TABLES` 里的账本表,但新列必须**可空**:非空列会让 `add_missing_columns` 造一个假默认值(`_default_clause` 对非空列会补 `''`),而 `''` 会被误读成「记过执色」。
- 类型检查 `npx tsc -b`;新文案 `t('ns:key','中文默认')`,**不改 `.po`**。
- 触及共享领地(`src/kiosk/api/growthApi.ts` 在 kiosk 下,但 `GrowthSummary` 类型被 galaxy 间接引用的地方要核)⇒ `npm run build` 与 `npm run build:kiosk-2d` 都要绿。
- 屏 22 有参考图 ⇒ 视觉改动走 CLAUDE.md 的四图关卡(`npm run fourup`,只看屏 22 那一组四张),**未经 Fan 确认不得当作通过**;承重实测按「最满」和「最空」两态各量一次。
- 提交信息用中文,结尾加 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`;`git add` 逐个写文件名并用 `git diff --cached --stat` 回读。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/web/core/models_db.py` | 改 `UserGame`(:705-742) | 加 `user_color`(可空) |
| `katrain/web/core/user_game_repo.py` | 改 `create`(:53-82)、`create_ai_ladder_ranked`(:85-140);新增 `decided_since` | 透传执色;按执色数胜负 |
| `katrain/web/server.py` | 改 `_record_ai_game_locked` 的 `data`(:1830-1844);`_record_platform_engine_game`(:3610-3616) | 落账时写执色 |
| `katrain/web/core/growth_diagnosis.py` | **新建** | 纯函数:逐手分桶成三段的 `graded` / `bad` |
| `katrain/web/core/report_diagnosis_repo.py` | **新建** | 取「最近 N 份已完成报告」的逐手行(带执色) |
| `katrain/web/api/v1/endpoints/growth.py` | 改 `growth_summary`;新增 `growth_diagnosis` | 三个新字段;诊断端点(三档 authority) |
| `katrain/web/core/repository.py` | 新增 `growth_diagnosis_remote`(照抄 `growth_summary_remote`) | 盒上先问云端 |
| `katrain/web/core/remote_client.py` | 新增 `get_growth_diagnosis` | 同上 |
| `tests/web_ui/test_user_game_color.py` | **新建** | G2 后端单测 |
| `tests/web_ui/test_growth_diagnosis.py` | **新建** | G1 后端单测 |
| `katrain/web/ui/src/kiosk/api/growthApi.ts` | 改 + 追加 | `GrowthSummary` 三个可选字段、`winrateCell`、`GrowthDiagnosis` 类型与校验、`getGrowthDiagnosis` |
| `katrain/web/ui/src/kiosk/api/growthApi.test.ts` | **新建**(若不存在) | 纯函数与校验单测 |
| `katrain/web/ui/src/kiosk/pages/GrowthPage.tsx` | 改 `:126-142`(胜率格)、`:196-222`(诊断块) | G2 / G1 的屏上部分 |
| `katrain/web/ui/src/kiosk/__tests__/GrowthPage.test.tsx` | 追加 | 屏级单测 |
| `katrain/web/core/ai_ladder_ranked.py` | 新增 `rung_trend()`(只读) | G3:按天取当天最后一局的档位 |
| `tests/web_ui/test_growth_trend.py` | **新建** | G3 后端三条(含前提闸) |
| `katrain/web/ui/src/kiosk/components/growth/RungTrend.tsx` + `rungTrend.ts`(+ 测试) | **新建** | G3:纯函数算折线 + 一块 SVG |
| `katrain/web/ui/tests/kiosk-screen-22-growth.spec.ts` | 追加三条 | 承重实测(最满 / 最空)+ 走势块 |
| `katrain/web/core/growth_activity.py` | **新建**(G4) | 按客户端时区逐日数对局(三种来源白名单)与首次解题 |
| `tests/web_ui/test_growth_activity.py` | **新建**(G4) | 仓储四条 + 端点五条 |
| `katrain/web/ui/src/kiosk/components/growth/ActivityCalendar.tsx` + `calendarGrid.ts`(+ 测试) | **已建**(G4,`0739d220`) | 纯函数排格子 + 一块日历 |

任务顺序:Task 1 基线 → Task 2 加列与落账(G2 后端) → Task 3 summary 三字段(G2 后端) → Task 4 胜率那一格(G2 前端) → Task 5 诊断聚合(G1 后端) → Task 6 诊断端点(G1 后端) → Task 7 诊断块(G1 前端) → **Task 8 档位走势(G3,前后端)** → **Task 8b 练棋日历(G4,前端已完成,后端 + 集成)** → Task 9 四图与承重 → Task 10 收尾。**Task 5 依赖 Task 2**(诊断要读执色);Task 8 独立于 G1 / G2,可并行,但四图要等它一起重取。

---

### Task 1: 核对 worktree、装两套依赖、记录双基线

**Files:** 不改仓内文件。基线写到 `$(git rev-parse --absolute-git-dir)/growth-baseline/`。

**Interfaces:** Produces:`$BASE/before-py.txt`、`$BASE/before-failed.txt`、`$BASE/failed-names.cjs`。

- [ ] **Step 1: 核对 worktree 并装依赖**

```bash
cd /Users/fan/Repositories/katrain
# worktree 已于 2026-09-21 建好,本步只核对,不要再 add
git -C /Users/fan/Repositories/katrain-kiosk-go-growth rev-parse --abbrev-ref HEAD            # 预期 feature/kiosk-go-growth
git -C /Users/fan/Repositories/katrain-kiosk-go-growth merge-base --is-ancestor 7a152df1 HEAD && echo base-ok
cd /Users/fan/Repositories/katrain-kiosk-go-growth
uv sync --extra web            # 光 uv sync 会缺 fastapi ⇒ 基线会静默变空
cd katrain/web/ui && npm ci
```

- [ ] **Step 2: Python 基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth
BASE="$(git rev-parse --absolute-git-dir)/growth-baseline"; mkdir -p "$BASE"
CI=true uv run pytest tests --continue-on-collection-errors -q > "$BASE/before-py.log" 2>&1; echo "pytest_exit=$?"
grep '^FAILED\|^ERROR' "$BASE/before-py.log" | sort -u > "$BASE/before-py.txt"
wc -l < "$BASE/before-py.txt"
```

预期:名字集合写出(行数照实记)。**不提交**。

- [ ] **Step 3: 前端基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-growth rev-parse --absolute-git-dir)/growth-baseline"
cat > "$BASE/failed-names.cjs" <<'EOF'
const report = require(process.argv[2]);
const out = [];
for (const file of report.testResults) {
  const rel = file.name.replace(/^.*\/katrain\/web\/ui\//, '');
  if (file.status === 'failed' && file.assertionResults.length === 0) out.push(`${rel} :: <文件级失败>`);
  for (const a of file.assertionResults) if (a.status === 'failed') out.push(`${rel} :: ${a.fullName}`);
}
console.log(out.sort().join('\n'));
EOF
npx vitest run --reporter=json --outputFile="$BASE/before.json" > "$BASE/before.log" 2>&1; echo "vitest_exit=$?"
node "$BASE/failed-names.cjs" "$BASE/before.json" > "$BASE/before-failed.txt"
npx tsc -b; echo "tsc_exit=$?"
```

---

### Task 2: G2-a · `user_games` 记下「用户坐哪一方」

**Files:**
- Modify: `katrain/web/core/models_db.py`(`UserGame`)
- Modify: `katrain/web/core/user_game_repo.py`(`create`、`create_ai_ladder_ranked`)
- Modify: `katrain/web/server.py`(`_record_ai_game_locked` 的 `data`;`_record_platform_engine_game`)
- Test: `tests/web_ui/test_user_game_color.py`(新建)

**Interfaces:**
- Produces:`UserGame.user_color: str | None`(`'B'` / `'W'` / NULL);`server._user_seat(players_info, game_type) -> str | None`;`user_game_repo.create(..., user_color=...)`。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_user_game_color.py
"""`user_games.user_color` —— 这个用户坐哪一方。

**算得出就写,算不出就 NULL。** 拿玩家名去猜(`player_black == username`?)就是在编:
名字可能重、可能空、面对面那一局根本没有「你」这一方。
"""
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db, migrations
from katrain.web.core.user_game_repo import UserGameRepository


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    models_db.Base.metadata.create_all(engine)
    return UserGameRepository(sessionmaker(bind=engine)), engine


def test_column_exists(repo):
    _, engine = repo
    cols = {c["name"] for c in inspect(engine).get_columns("user_games")}
    assert "user_color" in cols


def test_create_round_trips_user_color(repo):
    r, _ = repo
    row = r.create(user_id=1, sgf_content="(;GM[1])", source="play_ai", user_color="W")
    assert row["user_color"] == "W"


def test_create_without_user_color_is_null_not_guessed(repo):
    r, _ = repo
    row = r.create(user_id=1, sgf_content="(;GM[1]B[aa])", source="import", player_black="me")
    assert row["user_color"] is None


def test_add_missing_columns_adds_it_to_an_older_database(tmp_path):
    """老库(建表时还没有这一列)跑一次迁移就该有。**仓里没有 alembic**,
    加列只走 `migrations.add_missing_columns` 那条幂等链路。"""
    engine = create_engine(f"sqlite:///{tmp_path/'old.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE user_games (id VARCHAR(32) PRIMARY KEY, user_id INTEGER NOT NULL, "
            "sgf_content TEXT, source VARCHAR(50) NOT NULL)"
        )
    migrations.add_missing_columns(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("user_games")}
    assert "user_color" in cols


@pytest.mark.parametrize(
    "seats,game_type,expected",
    [
        ({"B": True, "W": False}, "free", "B"),      # 人执黑跟 AI 下
        ({"B": False, "W": True}, "free", "W"),
        ({"B": True, "W": True}, "pvp_local", None),  # 面对面:没有「你」这一方
        ({"B": False, "W": False}, "free", None),     # AI 对 AI:同样不猜
    ],
)
def test_user_seat(seats, game_type, expected):
    from katrain.web.server import _user_seat

    class Info:
        def __init__(self, human):
            self.human = human

    assert _user_seat({bw: Info(h) for bw, h in seats.items()}, game_type) == expected
```

- [ ] **Step 2: 跑,确认它失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth
CI=true uv run pytest tests/web_ui/test_user_game_color.py -q
```

预期:FAIL(没有 `user_color` 列;`_user_seat` 不存在)。

- [ ] **Step 3: 加列**

`katrain/web/core/models_db.py`,`UserGame` 里 `game_type` 那一行之后加:

```python
    # 这个用户坐哪一方('B' / 'W')。**算不出来就是 NULL,不猜** —— 面对面(两边都是人)、
    # 导入的谱、研究局都没有「你」这一方;拿玩家名去比就是在编(重名、没填名字)。
    # 升降级那条链另有权威记录(`ai_ladder_game_ledger.user_color`,非空),这一列是
    # **给其余局型用的**,所以可空。这一列诞生之前的行一律 NULL 且**不回填**:
    # 那个事实当时没记下来,追认就是编。成长屏那句「有 N 局没记执色」是它的出口。
    user_color = Column(String(1), nullable=True)
```

- [ ] **Step 4: 仓储透传**

`user_game_repo.create` 的 `game_kwargs` 里加一行:

```python
                user_color=kwargs.get("user_color"),
```

`create_ai_ladder_ranked` 的 `db_game = models_db.UserGame(` 里同样加一行 `user_color=kwargs.get("user_color"),`。

⚠️ **不要把 `user_color` 加进 `immutable_fields`**(`:104-118`):那份比对是给重试用的,而这一列诞生之前写下的权威局是 NULL,重试时传进来的却是 `'B'`/`'W'` ⇒ 会把一次正常的重试判成「authoritative ranked AI game is immutable」。在那段代码旁边写下这句理由。

- [ ] **Step 5: 落账时写它**

`katrain/web/server.py`,在 `_record_ai_game_locked` 定义之前(与它同一层)加:

```python
    def _user_seat(players_info, game_type):
        """这一局里「这个用户」坐哪一方。

        **两边都是人(面对面)或都不是人 ⇒ None。** 面对面那一局没有「你」这一方,
        硬挑一方出来记,成长屏的胜率就会开始编。
        """
        if game_type == "pvp_local":
            return None
        seats = [bw for bw, info in players_info.items() if getattr(info, "human", False)]
        return seats[0] if len(seats) == 1 else None
```

`data = {` 字典里(`"game_date": game_date,` 之后)加:

```python
                # 见 models_db.UserGame.user_color:算得出就写,算不出就 None。
                "user_color": _user_seat(players_info, game_type),
```

`_record_platform_engine_game`(:3610-3616)的 `data_overrides` 里加一键(它本来就算出了 `human_color`):

```python
        data_overrides={
            "source": "play_ai",
            "player_black": names["B"],
            "player_white": names["W"],
            # 平台引擎局:人坐的是引擎的另一边。这里是全仓唯一知道这件事的地方。
            "user_color": human_color,
        },
```

- [ ] **Step 6: 跑,确认它通过**

```bash
CI=true uv run pytest tests/web_ui/test_user_game_color.py -q
CI=true uv run pytest tests/web_ui -q -k "user_game or ladder or record" 
uv run black -l 120 katrain/web/core/models_db.py katrain/web/core/user_game_repo.py katrain/web/server.py
```

预期:新文件全绿;既有相关测试不新增失败(有疑问就跟 Task 1 的基线名字集合比)。

- [ ] **Step 7: 提交**

```bash
git add katrain/web/core/models_db.py katrain/web/core/user_game_repo.py katrain/web/server.py tests/web_ui/test_user_game_color.py
git diff --cached --stat
git commit -m "$(cat <<'EOF'
feat(growth): user_games 记下用户坐哪一方

算得出就写(人机局 = 唯一的人类座位、平台引擎局 = 引擎的另一边),
算不出就 NULL(面对面、导入、研究)——不拿玩家名去猜。
不回填历史行:那个事实当时没记下来。
不进 immutable_fields:老的权威局是 NULL,否则一次正常重试会被判成篡改。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: G2-b · `growth/summary` 回「算得出胜负的局」

**Files:**
- Modify: `katrain/web/core/user_game_repo.py`(新增 `decided_since`)
- Modify: `katrain/web/api/v1/endpoints/growth.py`(本机那一支多三个字段)
- Test: `tests/web_ui/test_user_game_color.py`(追加)

**Interfaces:**
- Produces:`UserGameRepository.decided_since(user_id, *, since) -> dict` 返回 `{"decided": int, "wins": int, "losses": int}`;`/growth/summary` 响应多三个键 `decided_games_in_window` / `wins_in_window` / `losses_in_window`。

- [ ] **Step 1: 写失败的测试(追加)**

```python
def test_decided_since_counts_only_rows_with_a_seat(repo):
    r, _ = repo
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=30)
    r.create(user_id=1, sgf_content="a", source="play_ai", user_color="B", result="B+R")   # 赢
    r.create(user_id=1, sgf_content="b", source="play_ai", user_color="W", result="B+3.5") # 输
    r.create(user_id=1, sgf_content="c", source="play_local", result="W+R")                # 没执色:不算
    r.create(user_id=1, sgf_content="d", source="play_ai", user_color="B", result="Void")  # 判不出胜负:不算
    got = r.decided_since(1, since=since)
    assert got == {"decided": 2, "wins": 1, "losses": 1}


def test_decided_and_total_have_different_denominators(repo):
    """`games_in_window` 数的是**下了多少局**,`decided` 数的是**算得出胜负的局**。
    两个口径不同,屏上那句「有 N 局没记执色」就是它们的差。"""
    r, _ = repo
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=30)
    r.create(user_id=1, sgf_content="a", source="play_ai", user_color="B", result="B+R")
    r.create(user_id=1, sgf_content="b", source="play_local", result="W+R")
    assert r.count_since(1, since=since) == 2
    assert r.decided_since(1, since=since)["decided"] == 1
```

- [ ] **Step 2: 跑,确认它失败**

```bash
CI=true uv run pytest tests/web_ui/test_user_game_color.py -q
```

预期:FAIL(`decided_since` 不存在)。

- [ ] **Step 3: 写 `decided_since`**

放在 `user_game_repo.py` 的 `count_since` 之后:

```python
    def decided_since(self, user_id: int, *, since) -> dict:
        """近 N 天里**算得出胜负**的局:`user_color` 有值、且 `result` 判得出赢家。

        胜负在 Python 里判,不在 SQL 里:`result` 是 `"B+R"` / `"W+3.5"` / `"Draw"` /
        `"Void"` 这种自由文本,SQLite 与 PG 的字符串函数不一样,而这点数据量不值得
        为它写两套 SQL。

        ⚠️ 和 `count_since` **口径不同**:那个数的是下了多少局,这个数的是算得出胜负的局。
        屏上那句「有 N 局没记执色」就是两者的差 —— 不许拿一个冒充另一个。
        """
        session = self.session_factory()
        try:
            rows = (
                session.query(models_db.UserGame.user_color, models_db.UserGame.result)
                .filter(
                    models_db.UserGame.user_id == user_id,
                    models_db.UserGame.created_at >= since,
                    models_db.UserGame.user_color.isnot(None),
                    models_db.UserGame.result.isnot(None),
                )
                .all()
            )
            wins = losses = 0
            for color, result in rows:
                winner = (result or "").strip()[:1].upper()
                if winner not in ("B", "W") or color not in ("B", "W"):
                    continue
                if winner == color:
                    wins += 1
                else:
                    losses += 1
            return {"decided": wins + losses, "wins": wins, "losses": losses}
        finally:
            session.close()
```

- [ ] **Step 4: 端点多回三个字段**

`endpoints/growth.py` 本机那一支(`return {` 那段)加三行:

```python
    decided = game_repo.decided_since(current_user.id, since=since)
    ...
        # 「算得出胜负的局」——`user_color` 有值的那些。与 `games_in_window` **口径不同**:
        # 后者数的是下了多少局。老云端不回这三个字段,前端把它们当**可选**处理
        # (`_looks_like_summary` 只查必需键,所以老云端的响应仍然算「长得对」)。
        "decided_games_in_window": decided["decided"],
        "wins_in_window": decided["wins"],
        "losses_in_window": decided["losses"],
```

⚠️ **不要把这三个键加进 `_REQUIRED_KEYS`**:那份清单判的是「云端那份敢不敢原样转出去」,把新键加进去等于**老云端一律被判成坏 payload**,盒子会在云端还没部署的那几天里全部退回本机缓存。

- [ ] **Step 5: 跑,确认它通过**

```bash
CI=true uv run pytest tests/web_ui/test_user_game_color.py tests/web_ui/test_growth_authority.py -q
uv run black -l 120 katrain/web/core/user_game_repo.py katrain/web/api/v1/endpoints/growth.py
```

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/user_game_repo.py katrain/web/api/v1/endpoints/growth.py tests/web_ui/test_user_game_color.py
git commit -m "$(cat <<'EOF'
feat(growth): summary 回「算得出胜负的局」

decided/wins/losses 只数 user_color 有值且 result 判得出赢家的局,
与 games_in_window 口径不同。三个新键**不**进 _REQUIRED_KEYS ——
否则云端没部署的那几天里,盒子会把老云端的正常响应判成坏 payload。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: G2-c · 屏上那一格改成「胜率 · 近 30 天」

**Files:**
- Modify: `katrain/web/ui/src/kiosk/api/growthApi.ts`
- Create: `katrain/web/ui/src/kiosk/api/growthApi.test.ts`
- Modify: `katrain/web/ui/src/kiosk/pages/GrowthPage.tsx`(`:126-142` 与 `:196-210` 的 setnote 区)
- Test: `katrain/web/ui/src/kiosk/__tests__/GrowthPage.test.tsx`(追加)

**Interfaces:**
- Produces:`winrateCell(s: GrowthSummary): { value: number | null; scope: 'all' | 'ranked'; unknownGames: number }`。
  - `scope: 'all'` ⇒ 标签写「胜率 · 近 30 天」;`'ranked'` ⇒ 老云端没回新字段,退回「升降级胜率 · 近 30 天」。**标签跟着数走**,不能显示一个口径、算另一个。

- [ ] **Step 1: 写失败的单测**

```ts
// katrain/web/ui/src/kiosk/api/growthApi.test.ts
import { describe, it, expect } from 'vitest';
import { winrateCell, type GrowthSummary } from './growthApi';

const base: GrowthSummary = {
  window_days: 30, games_in_window: 0, ranked_total: 0,
  ranked_wins_in_window: 0, ranked_losses_in_window: 0,
  by_opponent_rung: [], authority: 'cloud',
};

describe('winrateCell', () => {
  it('有新字段时算全部算得出执色的局', () => {
    const got = winrateCell({ ...base, games_in_window: 10, decided_games_in_window: 8, wins_in_window: 6, losses_in_window: 2 });
    expect(got).toEqual({ value: 0.75, scope: 'all', unknownGames: 2 });
  });

  it('窗口里有对局但一局都算不出执色 ⇒ 没有值,并把差额报出来', () => {
    const got = winrateCell({ ...base, games_in_window: 5, decided_games_in_window: 0, wins_in_window: 0, losses_in_window: 0 });
    expect(got.value).toBeNull();
    expect(got.unknownGames).toBe(5);
  });

  // 云端还没部署新版本时,老响应里没有这三个键 —— 退回升降级口径,**标签也要跟着退**。
  it('老云端(没有新字段)退回升降级口径', () => {
    const got = winrateCell({ ...base, games_in_window: 4, ranked_wins_in_window: 3, ranked_losses_in_window: 1 });
    expect(got).toEqual({ value: 0.75, scope: 'ranked', unknownGames: 0 });
  });

  it('一局没下时是 null,不是 0%', () => {
    expect(winrateCell({ ...base, decided_games_in_window: 0, games_in_window: 0 }).value).toBeNull();
  });
});
```

- [ ] **Step 2: 跑,确认它失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth/katrain/web/ui
npx vitest run src/kiosk/api/growthApi.test.ts
```

- [ ] **Step 3: 改 `growthApi.ts`**

在 `GrowthSummary` 接口里加三个**可选**字段:

```ts
  /**
   * 「算得出胜负的局」——`user_games.user_color` 有值的那些。
   * **可选**:云端可能还没部署到这一版,那时整块退回升降级口径(见 `winrateCell`)。
   */
  decided_games_in_window?: number;
  wins_in_window?: number;
  losses_in_window?: number;
```

末尾追加(`rankedWinrate` 保留,galaxy 与既有测试在用):

```ts
/**
 * 屏上那一格该显示什么。**标签跟着数走** —— 显示一个口径、算另一个,是这一屏最容易犯的错。
 *
 * · 云端给了新字段 ⇒ `scope: 'all'`,分母是所有算得出执色的局。
 * · 没给(老云端)⇒ 退回升降级口径,`scope: 'ranked'`,屏上的标签也退回「升降级胜率」。
 * · 分母是 0 ⇒ `value: null`,屏上写 `—`。**不返回 0%**:「一局没下」和「全输了」是两句话。
 *
 * `unknownGames` 是「下了但算不出执色」的局数(新字段存在时才有意义),
 * 屏上那句「有 N 局没记执色」就是它。
 */
export const winrateCell = (s: GrowthSummary): {
  value: number | null; scope: 'all' | 'ranked'; unknownGames: number;
} => {
  if (typeof s.decided_games_in_window === 'number') {
    const decided = s.decided_games_in_window;
    const unknown = Math.max(0, s.games_in_window - decided);
    if (decided === 0) return { value: null, scope: 'all', unknownGames: unknown };
    return { value: (s.wins_in_window ?? 0) / decided, scope: 'all', unknownGames: unknown };
  }
  return { value: rankedWinrate(s), scope: 'ranked', unknownGames: 0 };
};
```

- [ ] **Step 4: 改屏**

`GrowthPage.tsx`:把 `const wr = summary ? rankedWinrate(summary) : null;` 换成

```tsx
  const cell = summary ? winrateCell(summary) : null;
```

四格里那一格改成:

```tsx
    {
      v: cell?.value == null ? dash : pct(cell.value),
      // 口径必须写在标签里(共享外壳 §5:「一个光秃秃的 58% 谁也不知道是哪来的」)。
      // 老云端只给得出升降级那一半,标签跟着退 —— 显示一个口径、算另一个是这屏最容易犯的错。
      k: cell?.scope === 'ranked'
        ? t('growth:stat_winrate_ranked', '升降级胜率 · 近 30 天')
        : t('growth:stat_winrate_all', '胜率 · 近 30 天'),
      good: cell?.value != null && cell.value >= 0.5,
    },
```

在两条既有 setnote 之后加第三条:

```tsx
        {cell && cell.scope === 'all' && cell.unknownGames > 0 && (
          <p className="setnote" data-testid="growth-unknown-seat">
            {t('growth:unknown_seat_a', '有 ')}
            <b>{cell.unknownGames}</b>
            {t('growth:unknown_seat_b', ' 局没记执黑还是执白（面对面、导入的谱，以及这一列上线之前下的），算不进胜率。')}
          </p>
        )}
```

同时把文件头注「## 胜率为什么只算升降级局」那一段改写成现在的事实:

```
 * ## 胜率算哪些局
 *
 * 2026-09-20 之前 `user_games` **没有一列记这个用户坐哪一方**,所以只有升降级局
 * (`ai_ladder_game_ledger` 有 `user_color`)算得出胜负。现在 `user_games.user_color`
 * 补上了,人机局与平台引擎局也算得出;面对面、导入的谱、以及这一列上线之前的行
 * 仍然是 NULL —— 它们**不进分母**,差额由屏上那句「有 N 局没记执色」说出来。
```

- [ ] **Step 5: 屏级单测(追加)**

```tsx
  it('有算得出胜负的局时,那一格是百分比、标签是「胜率 · 近 30 天」', async () => {
    mockSummary({ games_in_window: 10, decided_games_in_window: 8, wins_in_window: 6, losses_in_window: 2 });
    renderGrowth();
    expect(await screen.findByText('75%')).toBeInTheDocument();
    expect(screen.getByText('胜率 · 近 30 天')).toBeInTheDocument();
  });

  it('一局都算不出执色时写 —,并说清有几局没记', async () => {
    mockSummary({ games_in_window: 5, decided_games_in_window: 0, wins_in_window: 0, losses_in_window: 0 });
    renderGrowth();
    expect(await screen.findByTestId('growth-unknown-seat')).toHaveTextContent('5');
  });

  it('老云端没给新字段时,标签退回「升降级胜率」', async () => {
    mockSummary({ games_in_window: 4, ranked_wins_in_window: 3, ranked_losses_in_window: 1 });
    renderGrowth();
    expect(await screen.findByText('升降级胜率 · 近 30 天')).toBeInTheDocument();
  });
```

(`mockSummary` / `renderGrowth` 沿用该文件既有助手;没有就照既有 mock 写法补。)

- [ ] **Step 6: 跑,确认通过**

```bash
npx vitest run src/kiosk/api/growthApi.test.ts src/kiosk/__tests__/GrowthPage.test.tsx
npx tsc -b
```

- [ ] **Step 7: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth
git add katrain/web/ui/src/kiosk/api/growthApi.ts katrain/web/ui/src/kiosk/api/growthApi.test.ts \
  katrain/web/ui/src/kiosk/pages/GrowthPage.tsx katrain/web/ui/src/kiosk/__tests__/GrowthPage.test.tsx
git commit -m "$(cat <<'EOF'
feat(growth): 胜率那一格覆盖所有算得出执色的局

标签跟着数走:老云端没给新字段就退回「升降级胜率」。
分母为 0 写 —,不写 0%;差额由「有 N 局没记执色」说出来。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: G1-a · 诊断聚合(纯函数 + 仓储查询)

**Files:**
- Create: `katrain/web/core/growth_diagnosis.py`
- Create: `katrain/web/core/report_diagnosis_repo.py`
- Test: `tests/web_ui/test_growth_diagnosis.py`(新建)

**Interfaces:**
- Produces:
  - `growth_diagnosis.bucket(moves: Iterable[Mapping]) -> dict` —— `moves` 的每一项要有 `move_number` 与 `grade`;返回 `{"graded": int, "phases": {phase: {"graded": int, "bad": int}}}`。
  - `ReportDiagnosisRepository.recent_graded_moves(user_id, *, since, max_reports) -> dict` —— 返回 `{"reports": int, "skipped_without_color": int, "moves": [ {"move_number", "grade"} ]}`。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_growth_diagnosis.py
"""跨局能力诊断:按开局 / 中盘 / 官子三段算失误率。

**分母只算「本用户执的那一方 + 已评级」的手。** `grade` 为空或 `unrated` 的手是
「不知道」,不是「没问题」—— 把它们算进分母,失误率会被稀释成一个看着很好的假数。
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.growth_diagnosis import bucket
from katrain.web.core.report_diagnosis_repo import ReportDiagnosisRepository


def test_bucket_splits_by_phase():
    moves = [
        {"move_number": 10, "grade": "best"},        # 开局
        {"move_number": 20, "grade": "mistake"},     # 开局 · 坏
        {"move_number": 80, "grade": "inaccuracy"},  # 中盘 · 坏
        {"move_number": 200, "grade": "playable"},   # 官子
    ]
    got = bucket(moves)
    assert got["graded"] == 4
    assert got["phases"]["opening"] == {"graded": 2, "bad": 1}
    assert got["phases"]["midgame"] == {"graded": 1, "bad": 1}
    assert got["phases"]["endgame"] == {"graded": 1, "bad": 0}


def test_bucket_ignores_unrated_and_missing_grades():
    got = bucket([
        {"move_number": 10, "grade": None},
        {"move_number": 11, "grade": "unrated"},
        {"move_number": 12, "grade": ""},
        {"move_number": 13, "grade": "blunder"},
    ])
    assert got["graded"] == 1
    assert got["phases"]["opening"] == {"graded": 1, "bad": 1}


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'d.db'}")
    models_db.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed(Session, *, user_id=1, user_color="B", status="completed", moves=()):
    s = Session()
    game = models_db.UserGame(
        id=f"g{user_id}{user_color}{status}{len(moves)}", user_id=user_id,
        sgf_content="(;GM[1])", source="play_ai", user_color=user_color,
    )
    s.add(game); s.flush()
    task = models_db.ReportTask(user_id=user_id, user_game_id=game.id, status=status)
    s.add(task); s.flush()
    for n, player, grade in moves:
        s.add(models_db.ReportTaskMove(task_id=task.id, move_number=n, actual_player=player, grade=grade))
    s.commit(); s.close()
    return task


def test_only_counts_the_user_side(db):
    _seed(db, user_color="B", moves=[(10, "B", "mistake"), (11, "W", "blunder")])
    repo = ReportDiagnosisRepository(db)
    got = repo.recent_graded_moves(1, since=datetime.now(timezone.utc) - timedelta(days=90), max_reports=20)
    assert got["reports"] == 1
    assert [m["move_number"] for m in got["moves"]] == [10]   # 对手那手不算


def test_skips_reports_whose_game_has_no_seat(db):
    """执色没记的局**整份跳过并报出来**,不拿两边的手混在一起算。"""
    _seed(db, user_color=None, moves=[(10, "B", "mistake")])
    repo = ReportDiagnosisRepository(db)
    got = repo.recent_graded_moves(1, since=datetime.now(timezone.utc) - timedelta(days=90), max_reports=20)
    assert got["reports"] == 0
    assert got["skipped_without_color"] == 1


def test_ignores_unfinished_reports(db):
    _seed(db, status="running", moves=[(10, "B", "mistake")])
    repo = ReportDiagnosisRepository(db)
    got = repo.recent_graded_moves(1, since=datetime.now(timezone.utc) - timedelta(days=90), max_reports=20)
    assert got["reports"] == 0
```

- [ ] **Step 2: 跑,确认它失败**

```bash
CI=true uv run pytest tests/web_ui/test_growth_diagnosis.py -q
```

- [ ] **Step 3: 写纯函数**

```python
# katrain/web/core/growth_diagnosis.py
"""跨局能力诊断的分桶:按开局 / 中盘 / 官子三段数「评过级的手」和「其中坏的手」。

**没有新阈值。** 档位与阶段边界的唯一真源都是 `katrain/core/move_grade.yaml`
(`tiers[].bad`、`display.phases`)—— 仓里为「妙手 / 失误」散过五份阈值,那条路不能再走。

**`grade` 为空 / `unrated` 的手不进分母。** 它们是「不知道」(上一手没分析、搜索量不够),
不是「没问题」;算进分母只会把失误率稀释成一个看着很好的假数。
"""

from typing import Any, Iterable, Mapping

from katrain.core import move_grade

PHASES = ("opening", "midgame", "endgame")


def _bad_ids(cfg) -> set:
    return {t["id"] for t in cfg["tiers"] if t.get("bad")}


def bucket(moves: Iterable[Mapping[str, Any]], cfg=None) -> dict:
    cfg = cfg or move_grade.load_config()
    bad_ids = _bad_ids(cfg)
    out = {"graded": 0, "phases": {p: {"graded": 0, "bad": 0} for p in PHASES}}
    for move in moves:
        grade = move.get("grade")
        if not grade or grade == move_grade.UNRATED:
            continue
        phase = move_grade.phase_of(int(move["move_number"]), cfg)
        slot = out["phases"].setdefault(phase, {"graded": 0, "bad": 0})
        slot["graded"] += 1
        if grade in bad_ids:
            slot["bad"] += 1
        out["graded"] += 1
    return out
```

⚠️ 若 `move_grade` 没有导出 `UNRATED`,从 `katrain.core.move_grade_core import UNRATED` 取(那份是 stdlib-only 的判级逻辑,`move_grade.py` 从它生成 cron 副本)。写之前 `grep -n "UNRATED" katrain/core/move_grade*.py` 确认一次。

- [ ] **Step 4: 写仓储查询**

```python
# katrain/web/core/report_diagnosis_repo.py
"""取「最近 N 份已完成报告」里本用户执的那一方的逐手评级。

为什么不复用 `endpoints/reports.py` 的 `_moves_with_grades`:那份会**按需补算**
老报告缺的 `grade`(要读 `top_moves` 重新判级),逐份补算跨 20 份报告在 RK3562 上
太贵。这里只读已经落库的 `grade`,补算不了的手按「不知道」处理(不进分母)。
"""

from typing import Any, Dict

from katrain.web.core import models_db


class ReportDiagnosisRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def recent_graded_moves(self, user_id: int, *, since, max_reports: int = 20) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            T, G, M = models_db.ReportTask, models_db.UserGame, models_db.ReportTaskMove
            tasks = (
                session.query(T.id, G.user_color)
                .join(G, G.id == T.user_game_id)
                .filter(T.user_id == user_id, T.status == "completed", G.created_at >= since)
                .order_by(T.id.desc())
                .limit(max_reports)
                .all()
            )
            usable = [(task_id, color) for task_id, color in tasks if color in ("B", "W")]
            skipped = len(tasks) - len(usable)
            moves: list[dict] = []
            for task_id, color in usable:
                rows = (
                    session.query(M.move_number, M.grade)
                    .filter(M.task_id == task_id, M.actual_player == color)
                    .all()
                )
                moves.extend({"move_number": n, "grade": g} for n, g in rows)
            return {"reports": len(usable), "skipped_without_color": skipped, "moves": moves}
        finally:
            session.close()
```

- [ ] **Step 5: 跑,确认通过**

```bash
CI=true uv run pytest tests/web_ui/test_growth_diagnosis.py -q
uv run black -l 120 katrain/web/core/growth_diagnosis.py katrain/web/core/report_diagnosis_repo.py
```

预期:6 passed。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/growth_diagnosis.py katrain/web/core/report_diagnosis_repo.py tests/web_ui/test_growth_diagnosis.py
git commit -m "$(cat <<'EOF'
feat(growth): 诊断分桶与取数

按 move_grade.yaml 的阶段与 bad 档分桶,不新造阈值。
未评级的手不进分母(「不知道」不是「没问题」);
执色没记的局整份跳过并报出来,不把两边的手混在一起算。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: G1-b · `GET /growth/diagnosis`(三档 authority)

**Files:**
- Modify: `katrain/web/api/v1/endpoints/growth.py`
- Modify: `katrain/web/core/repository.py`、`katrain/web/core/remote_client.py`
- Modify: `katrain/web/server.py`(把 `ReportDiagnosisRepository` 挂到 `app.state`,照 `user_game_repo` 的挂法)
- Test: `tests/web_ui/test_growth_diagnosis.py`(追加端点层)

**Interfaces:**
- Produces:`GET /api/v1/growth/diagnosis?days=90&reports=20` →
  `{"window_days", "reports", "skipped_without_color", "graded_moves", "phases": [{"phase","graded","bad"}], "authority"}`。

- [ ] **Step 1: 写失败的测试(追加)**

```python
def test_endpoint_shape(client_with_user):     # 沿用该目录既有的 TestClient 夹具写法
    resp = client_with_user.get("/api/v1/growth/diagnosis?days=90")
    assert resp.status_code == 200
    body = resp.json()
    assert body["phases"] == [] or {p["phase"] for p in body["phases"]} <= {"opening", "midgame", "endgame"}
    assert body["authority"] in ("this_node", "cloud", "local_cache")


def test_no_reports_is_zero_not_404(client_with_user):
    body = client_with_user.get("/api/v1/growth/diagnosis").json()
    assert body["reports"] == 0 and body["graded_moves"] == 0 and body["phases"] == []


def test_box_asks_the_cloud_first(client_on_box_with_cloud):
    """盒上报告在云端,本机库里没有 ⇒ 这个端点必须先问云端,退回时如实标 local_cache。"""
    body = client_on_box_with_cloud.get("/api/v1/growth/diagnosis").json()
    assert body["authority"] == "cloud"
```

> ⚠️ **夹具注入的顺序**:`app.dependency_overrides` / `app.state` 的替换必须在 `TestClient(app)` **之后**再被 lifespan 覆盖一次的话就白写了(本仓栽过:646 行写进真 PG 而夹具全无效)。照 `tests/web_ui/test_growth_authority.py` 既有的夹具顺序写,别自创。

- [ ] **Step 2: 跑,确认它失败**

```bash
CI=true uv run pytest tests/web_ui/test_growth_diagnosis.py -q
```

- [ ] **Step 3: 远端客户端 + dispatcher**

`remote_client.py`,在 `get_growth_summary` 旁边:

```python
    async def get_growth_diagnosis(self, days: int, reports: int) -> Dict:
        resp = await self._request("GET", "/api/v1/growth/diagnosis", params={"days": days, "reports": reports})
        resp.raise_for_status()
        return resp.json()
```

`repository.py`,在 `growth_summary_remote` 之后加一个同形的 `growth_diagnosis_remote(days, reports)` ——
**四种退回原因照抄**(`no_remote_client` / `offline` / `remote_unreachable` / `remote_missing_endpoint` /
`remote_error` / `remote_refused` / `remote_bad_payload`),它们在用户屏上长得一样、在运维那儿是不同的事。

- [ ] **Step 4: 端点**

```python
_DIAGNOSIS_REQUIRED_KEYS = ("reports", "graded_moves", "phases")


def _looks_like_diagnosis(payload: Any) -> bool:
    if not isinstance(payload, dict) or any(k not in payload for k in _DIAGNOSIS_REQUIRED_KEYS):
        return False
    return isinstance(payload["phases"], list) and isinstance(payload["reports"], int)


@router.get("/diagnosis")
async def growth_diagnosis(
    request: Request,
    days: int = 90,
    reports: int = 20,
    current_user: User = Depends(get_current_user),
):
    """能力诊断:最近 N 份已完成报告里,本用户执的那一方按三段的失误率。

    **样本量一起回。** 三个比率脱离样本量就是骗人 —— 20 手算出来的「官子最弱」
    和 2000 手算出来的是两回事,屏上必须写得出「来自几份报告的几手」。
    """
    if not 1 <= days <= 365:
        raise HTTPException(status_code=422, detail="days must be 1..365")
    if not 1 <= reports <= 50:
        raise HTTPException(status_code=422, detail="reports must be 1..50")

    repo = getattr(request.app.state, "report_diagnosis_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="growth diagnosis unavailable on this node")

    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        remote, reason = await dispatcher.growth_diagnosis_remote(days, reports)
        if remote is not None and _looks_like_diagnosis(remote):
            return {**remote, "authority": "cloud"}
        if remote is not None:
            logger.warning("growth diagnosis: cloud answered 200 with an unrecognised shape, using local cache")
            reason = "remote_bad_payload"
        logger.info("growth diagnosis: serving local cache (%s)", reason)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    picked = repo.recent_graded_moves(current_user.id, since=since, max_reports=reports)
    counts = growth_diagnosis.bucket(picked["moves"])
    return {
        "window_days": days,
        "reports": picked["reports"],
        "skipped_without_color": picked["skipped_without_color"],
        "graded_moves": counts["graded"],
        # 只列**有评过级的手**的那几段 —— 没打过的档不列,和「按对手强度」同一条口径。
        "phases": [
            {"phase": p, "graded": v["graded"], "bad": v["bad"]}
            for p, v in counts["phases"].items() if v["graded"] > 0
        ],
        "authority": "local_cache" if dispatcher is not None else "this_node",
    }
```

`server.py` 里挂仓储(挨着 `app.state.user_game_repo` 那一行):

```python
    app.state.report_diagnosis_repo = ReportDiagnosisRepository(session_factory)
```

- [ ] **Step 5: 跑,确认通过**

```bash
CI=true uv run pytest tests/web_ui/test_growth_diagnosis.py tests/web_ui/test_growth_authority.py -q
uv run black -l 120 katrain/web/api/v1/endpoints/growth.py katrain/web/core/repository.py katrain/web/core/remote_client.py katrain/web/server.py
```

- [ ] **Step 6: 提交**

```bash
git add katrain/web/api/v1/endpoints/growth.py katrain/web/core/repository.py katrain/web/core/remote_client.py katrain/web/server.py tests/web_ui/test_growth_diagnosis.py
git commit -m "$(cat <<'EOF'
feat(growth): GET /growth/diagnosis

盒上先问云端(报告在云端),退回本机时如实标 local_cache,四种退回原因各写各的日志。
样本量与比率一起回 —— 三个比率脱离样本量就是骗人。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: G1-c · 屏上那块换成真数据

**Files:**
- Modify: `katrain/web/ui/src/kiosk/api/growthApi.ts`(追加类型、校验、取数)
- Modify: `katrain/web/ui/src/kiosk/pages/GrowthPage.tsx`(`:212-222` 那一块)
- Test: `katrain/web/ui/src/kiosk/__tests__/GrowthPage.test.tsx`(追加)

**Interfaces:**
- Produces:`GrowthDiagnosis`、`isGrowthDiagnosis`、`getGrowthDiagnosis(token?, signal?)`;
  `diagnosisLines(d, t) -> { phase: string; label: string; rate: number; graded: number; weakest: boolean }[]`。

- [ ] **Step 1: 写失败的单测**

```tsx
  it('三段各一行,最弱那段有标记,样本量写出来', async () => {
    mockDiagnosis({ reports: 6, skipped_without_color: 0, graded_moves: 420, phases: [
      { phase: 'opening', graded: 150, bad: 15 },
      { phase: 'midgame', graded: 200, bad: 60 },
      { phase: 'endgame', graded: 70, bad: 7 },
    ] });
    renderGrowth();
    const rows = await screen.findAllByTestId('diag-row');
    expect(rows).toHaveLength(3);
    expect(screen.getByTestId('diag-weakest')).toHaveTextContent('中盘');
    expect(screen.getByTestId('diag-sample')).toHaveTextContent('6');
    expect(screen.getByTestId('diag-sample')).toHaveTextContent('420');
  });

  it('样本不够时照显示,但多一句「样本还不够」', async () => {
    mockDiagnosis({ reports: 1, skipped_without_color: 0, graded_moves: 40, phases: [{ phase: 'opening', graded: 40, bad: 4 }] });
    renderGrowth();
    expect(await screen.findByTestId('diag-thin')).toBeInTheDocument();
    expect(screen.getAllByTestId('diag-row')).toHaveLength(1);
  });

  it('一份报告都没有时说「还没有复盘报告」并给出口,不说「样本 0 局」', async () => {
    mockDiagnosis({ reports: 0, skipped_without_color: 0, graded_moves: 0, phases: [] });
    renderGrowth();
    expect(await screen.findByTestId('diag-empty')).toBeInTheDocument();
    expect(screen.queryByText('样本 0 局')).toBeNull();
    await userEvent.click(screen.getByTestId('diag-go-report'));
    expect(screen.getByTestId('report-page-stub')).toBeInTheDocument();
  });

  it('诊断请求失败时说「诊断没读到」,不退回空态', async () => {
    mockDiagnosisFailure();
    renderGrowth();
    expect(await screen.findByTestId('diag-error')).toBeInTheDocument();
    expect(screen.queryByTestId('diag-empty')).toBeNull();
  });
```

- [ ] **Step 2: 跑,确认它失败**

```bash
npx vitest run src/kiosk/__tests__/GrowthPage.test.tsx
```

- [ ] **Step 3: `growthApi.ts` 追加**

```ts
export interface GrowthDiagnosisPhase { phase: 'opening' | 'midgame' | 'endgame'; graded: number; bad: number; }

export interface GrowthDiagnosis {
  window_days: number;
  reports: number;
  /** 执色没记下来、整份跳过的报告数。屏上不单独显示,但它解释了 `reports` 为什么偏小。 */
  skipped_without_color: number;
  graded_moves: number;
  phases: GrowthDiagnosisPhase[];
  authority: DataAuthority;
}

/** 样本门槛。低于它照样显示,但要**明说样本还不够** —— 藏起来等于不承认自己在猜。 */
export const DIAGNOSIS_THIN_MOVES = 200;
export const DIAGNOSIS_THIN_REPORTS = 3;

export const isGrowthDiagnosis = (value: unknown): value is GrowthDiagnosis => {
  if (!value || typeof value !== 'object') return false;
  const v = value as Partial<GrowthDiagnosis>;
  return typeof v.reports === 'number' && typeof v.graded_moves === 'number'
    && Array.isArray(v.phases)
    && v.phases.every((p) => p && typeof p.graded === 'number' && typeof p.bad === 'number'
      && ['opening', 'midgame', 'endgame'].includes(p.phase as string))
    && AUTHORITIES.includes(v.authority as DataAuthority);
};

export const getGrowthDiagnosis = async (token?: string, signal?: AbortSignal): Promise<GrowthDiagnosis> => {
  const response = await fetch('/api/v1/growth/diagnosis', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!response.ok) throw new GrowthApiError(response.status, `growth diagnosis failed: ${response.status}`);
  const body: unknown = await response.json();
  if (!isGrowthDiagnosis(body)) throw new GrowthApiError(response.status, 'growth diagnosis payload not recognised');
  return body;
};

const PHASE_ZH: Record<GrowthDiagnosisPhase['phase'], string> = {
  opening: '开局', midgame: '中盘', endgame: '官子',
};

/**
 * 三段各一行。**最弱只在段与段真的分得开时才标** —— 两段失误率差一个百分点就说
 * 「你中盘最弱」,是拿噪声给人下结论。差距 < 3 个百分点时不标任何一段。
 */
export const diagnosisLines = (d: GrowthDiagnosis) => {
  const rows = d.phases.map((p) => ({
    phase: p.phase, label: PHASE_ZH[p.phase], graded: p.graded, bad: p.bad,
    rate: p.graded === 0 ? 0 : p.bad / p.graded,
  }));
  const sorted = [...rows].sort((a, b) => b.rate - a.rate);
  const separated = sorted.length >= 2 && sorted[0].rate - sorted[1].rate >= 0.03;
  return rows.map((r) => ({ ...r, weakest: separated && r.phase === sorted[0].phase }));
};
```

- [ ] **Step 4: 改屏**

把 `GrowthPage.tsx` 里那块写死的诊断换成(`useEffect` 取数与 `summary` 同形,失败不退回空态):

```tsx
          <div className="panel gsec" data-testid="growth-diagnosis">
            <h3>{t('growth:diag_title', '能力诊断')}</h3>
            {diagFailed ? (
              <div className="empty" data-testid="diag-error">
                <h4>{t('growth:diag_failed', '诊断没读到')}</h4>
                <p>{t('growth:diag_failed_p', '不是「还没下过棋」。稍后再看一次。')}</p>
              </div>
            ) : diag === null ? (
              <div className="empty"><h4>{t('growth:diag_loading', '正在算')}</h4></div>
            ) : diag.reports === 0 ? (
              <div className="empty" data-testid="diag-empty">
                <h4>{t('growth:diag_no_report', '还没有复盘报告')}</h4>
                <p>{t('growth:diag_no_report_p', '诊断拿已经跑过报告的对局算。下完一局去复盘里生成一份报告，这里就有数了。')}</p>
                <button
                  type="button" className="kiosk-btn kiosk-btn--secondary"
                  data-testid="diag-go-report" onClick={() => navigate('/kiosk/report')}
                >
                  {t('growth:diag_go_report', '去复盘')}
                </button>
              </div>
            ) : (
              <>
                <div className="grules" data-testid="diag-rows">
                  {diagnosisLines(diag).map((row) => (
                    <div className="grule" key={row.phase} data-testid="diag-row">
                      <span className="lead">{row.label}</span>
                      <b {...(row.weakest ? { 'data-testid': 'diag-weakest' } : {})}>
                        {row.label}
                        {' · '}
                        {t('growth:diag_rate', '每 {n} 手有 {m} 手失误')
                          .replace('{n}', String(row.graded))
                          .replace('{m}', String(row.bad))}
                      </b>
                    </div>
                  ))}
                </div>
                <p className="setnote" data-testid="diag-sample">
                  {t('growth:diag_sample', '来自最近 {r} 份报告的 {m} 手（只算你执的那一方）')
                    .replace('{r}', String(diag.reports))
                    .replace('{m}', String(diag.graded_moves))}
                </p>
                {(diag.graded_moves < DIAGNOSIS_THIN_MOVES || diag.reports < DIAGNOSIS_THIN_REPORTS) && (
                  <p className="setnote" data-testid="diag-thin">
                    {t('growth:diag_thin', '样本还不够，这几个数会抖。再下几局、多跑几份报告。')}
                  </p>
                )}
              </>
            )}
          </div>
```

并把文件头注里「留下的只有「能力诊断」那一块…」那段改写成现在的事实(2026-09-20 接上了,口径是三段失误率,样本量写在旁边)。

- [ ] **Step 5: 跑,确认通过**

```bash
npx vitest run src/kiosk/api/growthApi.test.ts src/kiosk/__tests__/GrowthPage.test.tsx
npx tsc -b
cd /Users/fan/Repositories/katrain-kiosk-go-growth && rg 'diag_wip|后端已有 · 界面未接' katrain/web/ui/src; echo "exit=$?"
```

预期:单测全绿;最后一条 `rg` 零命中(`exit=1`)。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/src/kiosk/api/growthApi.ts katrain/web/ui/src/kiosk/pages/GrowthPage.tsx katrain/web/ui/src/kiosk/__tests__/GrowthPage.test.tsx
git commit -m "$(cat <<'EOF'
feat(growth): 能力诊断说真话

三段失误率 + 样本量;样本不够照显示但明说;一份报告都没有时给出口,
不再写「样本 0 局」,也去掉标错的「后端已有 · 界面未接」蓝标。
最弱只在段与段差 ≥3 个百分点时才标 —— 否则是拿噪声下结论。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: G3 · 近 30 天档位走势(Fan 2026-09-21 裁定:画档位)

**Files:**
- Modify: `katrain/web/core/ai_ladder_ranked.py`(新增 `rung_trend`,**只读**)
- Modify: `katrain/web/api/v1/endpoints/growth.py`(本机那一支多一个 `rung_trend` 键)
- Create: `tests/web_ui/test_growth_trend.py`
- Create: `katrain/web/ui/src/kiosk/components/growth/rungTrend.ts`(+ `.test.ts`)、`RungTrend.tsx`
- Modify: `katrain/web/ui/src/kiosk/api/growthApi.ts`(加一个**可选**字段与类型)、`pages/GrowthPage.tsx`(左栏)
- Test: `src/kiosk/__tests__/GrowthPage.test.tsx`(追加两条)

**Interfaces:**
- Produces:
  - `AiLadderRepository.rung_trend(user_id, *, since) -> list[dict]`,每项 `{"date": "YYYY-MM-DD", "rung": int, "rank_name": str | None}`,按日期升序,**没有对局的那天不出现**。
  - `/growth/summary` 响应多一个**可选**键 `rung_trend`。
  - 前端 `trendPath(points, width, height) -> { d: string; peak: { x: number; y: number; point: GrowthTrendPoint } } | null`。

- [ ] **Step 1: 写失败的后端测试**

```python
# tests/web_ui/test_growth_trend.py
"""近 30 天档位走势。

**数据源的前提**:`expected_opponent_rung` 的 docstring 写着「定级之后玩家面对的就是自己那一档」——
所以定级**之后**那些局的 `opponent_rung` 就是本人当时的档位。这份前提由本文件最后一条测试钉住:
前提变了,它先红,而不是走势图开始画错。

**定级期那 5 局必须排除**:那时的 `opponent_rung` 是二分搜索的中点,不是实力。
账本里没有一列写着「这局是不是定级局」,唯一摘得出来的办法是按时间取前 PLACEMENT_GAMES 局。
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import PLACEMENT_GAMES, AiLadderRepository


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    models_db.Base.metadata.create_all(engine)
    return AiLadderRepository(sessionmaker(bind=engine))


def _settle(repo, *, day, rung, user_id=1, n=1):
    session = repo.session_factory()
    for i in range(n):
        session.add(models_db.AiLadderGameLedger(
            game_id=f"g{user_id}-{day.isoformat()}-{rung}-{i}", user_id=user_id, user_color="B",
            result="win", game_type="ai_ladder_ranked", opponent_rung=rung,
            opponent_rank_name=f"{rung}档", counted=True, settled_at=day,
        ))
    session.commit()
    session.close()


def test_one_point_per_day_taking_the_last_game_of_that_day(repo):
    base = datetime.now(timezone.utc) - timedelta(days=10)
    for i in range(PLACEMENT_GAMES):                      # 定级那 5 局:排除
        _settle(repo, day=base + timedelta(minutes=i), rung=5)
    _settle(repo, day=base + timedelta(days=1, hours=1), rung=10)
    _settle(repo, day=base + timedelta(days=1, hours=5), rung=11)   # 同一天的后一局
    _settle(repo, day=base + timedelta(days=2), rung=12)

    got = repo.rung_trend(1, since=datetime.now(timezone.utc) - timedelta(days=30))

    assert [p["rung"] for p in got] == [11, 12]           # 当天最后一局 + 不补点
    assert got[0]["date"] < got[1]["date"]


def test_still_in_placement_means_no_trend_at_all(repo):
    """**不许**把定级局的中点画出来充当实力曲线。"""
    base = datetime.now(timezone.utc) - timedelta(days=3)
    for i in range(PLACEMENT_GAMES - 1):
        _settle(repo, day=base + timedelta(minutes=i), rung=7)
    assert repo.rung_trend(1, since=base - timedelta(days=1)) == []


def test_the_premise_behind_the_data_source(repo):
    """**前提闸。** 定级之后「对手档 = 自己那一档」——走势图整条建立在这句话上。
    这条一旦红,说明前提变了,`rung_trend` 的数据源随之作废(不是改这条测试)。"""
    from katrain.web.core.ai_ladder_ranked import expected_opponent_rung

    assert expected_opponent_rung(12, 1, 41) == 12
```

- [ ] **Step 2: 跑,确认失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth
CI=true uv run pytest tests/web_ui/test_growth_trend.py -q
```

预期:FAIL(`rung_trend` 不存在)。

- [ ] **Step 3: 写 `rung_trend`**

放在 `ai_ladder_ranked.py` 的 `growth_summary` 之后:

```python
    def rung_trend(self, user_id: int, *, since) -> list[dict]:
        """近 N 天的档位走势,**一天一个点**(取当天最后一局),没有对局的那天不出现。

        为什么可以拿 `opponent_rung` 当「本人当时的档位」:`expected_opponent_rung` 的
        docstring 写着「定级之后玩家面对的就是自己那一档」。这条前提由
        `tests/web_ui/test_growth_trend.py::test_the_premise_behind_the_data_source` 钉着。

        **定级期那 5 局排除**:那时的 `opponent_rung` 是二分搜索的中点,不是实力。账本里
        没有一列写着「这局是不是定级局」,唯一摘得出来的办法就是按时间取前 PLACEMENT_GAMES 局 ——
        所以这里先查出第 5 局的 `settled_at`,再按它切。**两次比较都留在 SQL 里**:
        SQLite 取回来的 datetime 不带时区,在 Python 里和带时区的 `since` 比会直接抛。

        日期按数据库里的 `settled_at` 算(PG 是 UTC)。东八区凌晨那几局会落到前一天 ——
        走势看的是 30 天的形状,这点偏移不影响判读;要改就得先定「哪个时区算一天」,
        那是产品口径不是实现细节。
        """
        session = self.session_factory()
        try:
            L = models_db.AiLadderGameLedger
            counted = (L.user_id == user_id, L.counted.is_(True), L.result.in_(("win", "loss")))

            placement_end = (
                session.query(L.settled_at)
                .filter(*counted)
                .order_by(L.settled_at.asc(), L.id.asc())
                .offset(PLACEMENT_GAMES - 1)
                .limit(1)
                .scalar()
            )
            if placement_end is None:
                return []          # 还在定级期(counted 的局不足 5)⇒ 没有可画的实力

            rows = (
                session.query(L.settled_at, L.opponent_rung, L.opponent_rank_name)
                .filter(
                    *counted,
                    L.opponent_rung.isnot(None),
                    L.settled_at > placement_end,
                    L.settled_at >= since,
                )
                .order_by(L.settled_at.asc(), L.id.asc())
                .all()
            )
            by_day: dict = {}
            for settled_at, rung, rank_name in rows:
                # 查询已按时间升序 ⇒ 同一天后写覆盖前写 = 当天最后一局。
                key = settled_at.date().isoformat()
                by_day[key] = {"date": key, "rung": int(rung), "rank_name": rank_name}
            return [by_day[k] for k in sorted(by_day)]
        finally:
            session.close()
```

- [ ] **Step 4: 端点带上它**

`endpoints/growth.py` 本机那一支的 `return {` 里加一行(紧挨着 `by_opponent_rung`):

```python
        # 走势是**可选**键:老云端不回它时前端不画走势块(不画,不是画一条空轴)。
        # 同样不进 `_REQUIRED_KEYS` —— 理由见那份清单旁边的注释。
        "rung_trend": ladder_repo.rung_trend(current_user.id, since=since),
```

- [ ] **Step 5: 跑,确认通过**

```bash
CI=true uv run pytest tests/web_ui/test_growth_trend.py tests/web_ui/test_growth_authority.py -q
uv run black -l 120 katrain/web/core/ai_ladder_ranked.py katrain/web/api/v1/endpoints/growth.py
```

- [ ] **Step 6: 写失败的前端单测(纯函数)**

```ts
// katrain/web/ui/src/kiosk/components/growth/rungTrend.test.ts
import { describe, it, expect } from 'vitest';
import { trendPath } from './rungTrend';

const pt = (date: string, rung: number) => ({ date, rung, rank_name: `${rung}档` });

describe('trendPath', () => {
  it('两个点以上才画;一个点不画(**一个点不是趋势**)', () => {
    expect(trendPath([pt('2026-09-01', 10)], 240, 56)).toBeNull();
    expect(trendPath([], 240, 56)).toBeNull();
    expect(trendPath([pt('2026-09-01', 10), pt('2026-09-02', 11)], 240, 56)).not.toBeNull();
  });

  it('最高点标在最强那一档上(档位越大越强)', () => {
    const out = trendPath([pt('2026-09-01', 10), pt('2026-09-02', 14), pt('2026-09-03', 12)], 240, 56)!;
    expect(out.peak.point.rung).toBe(14);
  });

  it('全程同一档时也画得出来(不除以 0)', () => {
    const out = trendPath([pt('2026-09-01', 10), pt('2026-09-02', 10)], 240, 56)!;
    expect(out.d).toMatch(/^M/);
    expect(Number.isFinite(out.peak.y)).toBe(true);
  });

  // 折线按**日期**分布横坐标,不是按点的序号:中间隔了 10 天没下棋时,
  // 两点之间应当是一段长横距,而不是等距——否则屏上会把「十天没下」画成「天天在下」。
  it('横坐标按日期分布,不按序号', () => {
    const out = trendPath([pt('2026-09-01', 10), pt('2026-09-11', 11), pt('2026-09-12', 12)], 300, 56)!;
    const xs = out.d.match(/-?\d+(\.\d+)?/g)!.filter((_, i) => i % 2 === 0).map(Number);
    expect(xs[1] - xs[0]).toBeGreaterThan(xs[2] - xs[1]);
  });
});
```

- [ ] **Step 7: 写纯函数与组件**

```ts
// katrain/web/ui/src/kiosk/components/growth/rungTrend.ts
import type { GrowthTrendPoint } from '../../api/growthApi';

export interface TrendGeometry {
  d: string;
  peak: { x: number; y: number; point: GrowthTrendPoint };
}

/**
 * 近 30 天档位折线。**横坐标按日期,不按序号** —— 中间十天没下棋,屏上就该是一段长横距;
 * 按序号画会把「十天没下」画成「天天在下」。
 *
 * 少于两个点返回 `null`:**一个点不是趋势**,画出来是一条没有斜率的线,读者会以为是「持平」。
 */
export function trendPath(points: GrowthTrendPoint[], width: number, height: number): TrendGeometry | null {
  if (points.length < 2) return null;
  const ts = points.map((p) => new Date(`${p.date}T00:00:00Z`).getTime());
  const t0 = ts[0];
  const span = Math.max(1, ts[ts.length - 1] - t0);
  const rungs = points.map((p) => p.rung);
  const lo = Math.min(...rungs);
  const hi = Math.max(...rungs);
  const range = hi - lo || 1;           // 全程同一档也要画得出来,不除以 0
  const pad = 3;                        // 线宽的一半,免得最高/最低点被裁掉
  const xy = points.map((p, i) => ({
    x: ((ts[i] - t0) / span) * (width - 2 * pad) + pad,
    y: height - pad - ((p.rung - lo) / range) * (height - 2 * pad),
    point: p,
  }));
  const peakIndex = rungs.indexOf(hi);
  return {
    d: xy.map((q, i) => `${i === 0 ? 'M' : 'L'}${q.x.toFixed(1)} ${q.y.toFixed(1)}`).join(' '),
    peak: xy[peakIndex],
  };
}
```

```tsx
// katrain/web/ui/src/kiosk/components/growth/RungTrend.tsx
import type { GrowthTrendPoint } from '../../api/growthApi';
import { trendPath } from './rungTrend';

const W = 248;
const H = 56;

/**
 * 左栏那条近 30 天档位走势(共享规范 §5;Fan 2026-09-21 裁定画**档位**不画净胜分 ——
 * 净胜分是 −2…+2 的锯齿,到 ±3 就清零,画成 30 天曲线读不出趋势)。
 *
 * **纯 SVG,不引图表库**:RK3562 上多一个包就多一份内存,而这里要画的只是一条折线。
 * 画法与屏 20 的 `.wrplot` 同族。
 *
 * **没有对局的那天不补点**(后端就不给点),折线因此会有长横段 —— 那是事实:那几天没下棋。
 */
const RungTrend = ({ points }: { points: GrowthTrendPoint[] }) => {
  const geo = trendPath(points, W, H);
  if (!geo) {
    // 一个点或没有点:**说一句话,不画一条没有斜率的线**(那会被读成「持平」)。
    return (
      <p className="setnote" data-testid="growth-trend-empty">
        还没有足够的升降级对局，下几局就能看出走势。
      </p>
    );
  }
  return (
    <div className="gtrend" data-testid="growth-trend">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label="近 30 天档位走势">
        <path className="line" d={geo.d} fill="none" />
        <circle className="peak" cx={geo.peak.x} cy={geo.peak.y} r={3} />
      </svg>
      <span>
        最高 <b data-testid="growth-trend-peak">{geo.peak.point.rank_name ?? `#${geo.peak.point.rung}`}</b>
      </span>
    </div>
  );
};

export default RungTrend;
```

`growthApi.ts` 加类型与可选字段:

```ts
export interface GrowthTrendPoint { date: string; rung: number; rank_name: string | null; }
```

```ts
  /** 近 N 天档位走势,一天一个点。**可选**:老云端不回它,那时屏上不画走势块。 */
  rung_trend?: GrowthTrendPoint[];
```

`GrowthPage.tsx` 左栏(`.gmetric` 那一块之后、「升降的规矩」之前)插:

```tsx
        {summary?.rung_trend && <RungTrend points={summary.rung_trend} />}
```

样式(`kiosk-shell/go-screens.css`,挨着成长屏那一段):

```css
/* 成长左栏的档位走势。纯 SVG 一条线 + 一个最高点,不引图表库。
   高度写死 56:左栏是固定高度的一栏,走势块长出去会把「升降的规矩」三行挤下去。 */
.gtrend { display: flex; flex-direction: column; gap: 4px; margin-top: 10px; }
.gtrend svg { display: block; }
.gtrend .line { stroke: var(--accent); stroke-width: 1.8; stroke-linejoin: round; stroke-linecap: round; }
.gtrend .peak { fill: var(--accent); }
.gtrend span { font-size: 11.5px; color: var(--dim); }
```

- [ ] **Step 8: 屏级单测(追加两条)**

```tsx
  it('有走势数据时左栏画出折线,并标出最高档', async () => {
    mockSummary({ rung_trend: [
      { date: '2026-09-01', rung: 10, rank_name: '3级' },
      { date: '2026-09-05', rung: 12, rank_name: '1级' },
    ] });
    renderGrowth();
    expect(await screen.findByTestId('growth-trend')).toBeInTheDocument();
    expect(screen.getByTestId('growth-trend-peak')).toHaveTextContent('1级');
  });

  it('老云端没给 rung_trend 时,左栏不出现走势块(也不出现空轴)', async () => {
    mockSummary({});
    renderGrowth();
    await screen.findByTestId('growth-rank');
    expect(screen.queryByTestId('growth-trend')).toBeNull();
    expect(screen.queryByTestId('growth-trend-empty')).toBeNull();
  });
```

- [ ] **Step 9: 跑,确认通过**

```bash
cd katrain/web/ui
npx vitest run src/kiosk/components/growth src/kiosk/__tests__/GrowthPage.test.tsx && npx tsc -b
```

- [ ] **Step 10: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth
git add katrain/web/core/ai_ladder_ranked.py katrain/web/api/v1/endpoints/growth.py tests/web_ui/test_growth_trend.py \
  katrain/web/ui/src/kiosk/components/growth/ katrain/web/ui/src/kiosk/api/growthApi.ts \
  katrain/web/ui/src/kiosk/pages/GrowthPage.tsx katrain/web/ui/src/kiosk/__tests__/GrowthPage.test.tsx \
  katrain/web/ui/src/kiosk-shell/go-screens.css
git diff --cached --stat
git commit -m "$(cat <<'EOF'
feat(growth): 左栏近 30 天档位走势

Fan 2026-09-21 裁定画档位不画净胜分。定级那 5 局排除(它们的对手档是二分中点不是实力),
没有对局的那天不补点,横坐标按日期不按序号——否则「十天没下」会被画成「天天在下」。
数据源的前提(定级后对手档=自己档)有一条测试钉着。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8b: G4 · 近一年练棋日历(Fan 2026-09-22 新增;前端已完成,本 Task 展开后端与集成)

> 裁定与契约见 `prd.md` §3 G4。前端、重出的参考图、承重两态与四图都在 `0739d220`,Fan 09-22「两项都过了」。

**Files:**
- Create: `katrain/web/core/growth_activity.py`
- Create: `tests/web_ui/test_growth_activity.py`
- Modify: `katrain/web/api/v1/endpoints/growth.py`(新增 `GET /activity`)
- Modify: `katrain/web/core/repository.py`(新增 `growth_activity_remote`)、`katrain/web/core/remote_client.py`(新增 `get_growth_activity`)
- Modify: `katrain/web/server.py`(两个 lifespan 各挂一行 `growth_activity_repo`,挨着 `report_diagnosis_repo`)

**Interfaces:**
- Consumes(前端已写死):`getGrowthActivity` 请求 `/api/v1/growth/activity?days=365&tz_offset=${-new Date().getTimezoneOffset()}`,
  `isGrowthActivity` 校验 `window_days: number`、`days[].date` 形如 `YYYY-MM-DD`、`games` / `solved` 为 number、`authority` 三档之一。
- Produces:`{"window_days": 365, "days": [{"date", "games", "solved"}], "authority": "this_node" | "cloud" | "local_cache"}`,
  `days` 只列有活动的日子、升序。

- [x] **Step 0(已完成,`0739d220`):前端 + 参考图**

`ActivityCalendar.tsx` + `calendarGrid.ts`(+ 单测)、`growthApi.ts` 的 `GrowthActivity` / `isGrowthActivity` / `getGrowthActivity`、
`GrowthPage` 接入与四态单测、`go-screens.css` 屏 22 那一段、承重两态(在线 / 离线最满)、四图(参考图 pin `1a454cfc…`)。
fixture 只在 `tests/` 下(`FULL_ACTIVITY` / `EMPTY_ACTIVITY` / fourup 的 `ACTIVITY`),生产代码里没有。

- [x] **Step 1: 写仓储的失败测试**

`tests/web_ui/test_growth_activity.py`:

```python
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
        models_db.UserGame(
            id=f"g{next(_seq)}", user_id=user_id, sgf_content="(;GM[1])", source=source, created_at=at
        )
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
```

- [x] **Step 2: 跑,确认失败**

```bash
CI=true uv run pytest tests/web_ui/test_growth_activity.py -q
```

预期:收集阶段 `ModuleNotFoundError: katrain.web.core.growth_activity`。

- [x] **Step 3: 仓储**

`katrain/web/core/growth_activity.py`:

```python
"""近一年练棋日历(G4)的数据源:每天下完几局、首次解出几道题。

**一格 = 当天下完的对局 + 当天新解出的题**(Fan 2026-09-22 定)。两项分开回,由前端相加上色 ——
以后要分开画也不用改契约。

**按客户端的时区切天。** 按 UTC 切,北京早上 8 点前下的棋会落到前一天,「今天」那格明明下过却是空的。
`tz_offset` 是东几区的分钟数(北京 = 480)。

**哪些算「下完的对局」**:只认自己下的那三种来源,口径同前端
`kiosk/components/report/reviewPresentation.ts` 的 `isPlaySource`。用**白名单**不用黑名单 ——
导入的谱、棋谱库、研究局都不是你下的,之后再加一种新来源也不会悄悄混进来。

⚠️ 解题时间是 `first_completed_at`,由 `merge_tsumego_progress` 盖戳。盒子离线时解的题,
同步到云端那一刻才在云端盖戳 ⇒ 云端那份可能把它算到同步那天。盒子通常在线,不为此改同步协议。
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List

from katrain.web.core import models_db

PLAYED_SOURCES = ("play_ai", "play_local", "play_human")


def _local_date(ts: datetime, tz: timezone) -> date:
    # SQLite 读回来是 naive(不存时区);写进去的一律是 UTC(`func.now()` / `utcnow()`)。
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(tz).date()


class GrowthActivityRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def daily(self, user_id: int, *, days: int, tz_offset: int, now: datetime = None) -> List[Dict]:
        """→ `[{"date": "YYYY-MM-DD", "games": n, "solved": m}, ...]`,按日期升序,**只列有活动的日子**。

        窗口是客户端时区里的「今天」往前数 `days` 天(含今天)。
        """
        tz = timezone(timedelta(minutes=tz_offset))
        today = (now or datetime.now(timezone.utc)).astimezone(tz).date()
        first = today - timedelta(days=days - 1)
        # 换成 UTC 再进 SQL:SQLite 比的是字面时间,带 +08:00 的参数会被当成 UTC 读,错开 8 小时。
        since = datetime.combine(first, time.min, tzinfo=tz).astimezone(timezone.utc)

        G, P = models_db.UserGame, models_db.UserTsumegoProgress
        session = self.session_factory()
        try:
            games = (
                session.query(G.created_at)
                .filter(G.user_id == user_id, G.source.in_(PLAYED_SOURCES), G.created_at >= since)
                .all()
            )
            solved = (
                session.query(P.first_completed_at)
                .filter(P.user_id == user_id, P.completed.is_(True), P.first_completed_at >= since)
                .all()
            )
        finally:
            session.close()

        buckets: Dict[date, List[int]] = defaultdict(lambda: [0, 0])
        for column, rows in ((0, games), (1, solved)):
            for (ts,) in rows:
                if ts is None:
                    continue
                day = _local_date(ts, tz)
                if first <= day <= today:
                    buckets[day][column] += 1
        return [{"date": d.isoformat(), "games": g, "solved": s} for d, (g, s) in sorted(buckets.items())]
```

- [x] **Step 4: 跑,确认仓储四条通过**

```bash
CI=true uv run pytest tests/web_ui/test_growth_activity.py -q
```

预期:`4 passed`。**变异自查一次**:把 `.astimezone(timezone.utc)` 那一段删掉再跑,
`test_window_edges_…` 必须变红(证明那条测试真的守着那一行),然后改回。

- [x] **Step 5: 写端点的失败测试(追加到同一文件)**

```python
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
```

- [x] **Step 6: 跑,确认端点五条失败**

```bash
CI=true uv run pytest tests/web_ui/test_growth_activity.py -q
```

预期:仓储 4 passed,端点 5 failed(404 —— 路由还不存在)。

- [x] **Step 7: 远端客户端 + dispatcher + 端点 + 挂仓储**

`remote_client.py`,在 `get_growth_diagnosis` 之后(**手写,不整文件跑 black** —— 它在基线上就不干净):

```python
    async def get_growth_activity(self, days: int, tz_offset: int) -> Dict:
        resp = await self._request("GET", "/api/v1/growth/activity", params={"days": days, "tz_offset": tz_offset})
        resp.raise_for_status()
        return resp.json()
```

`repository.py`,在 `growth_diagnosis_remote` 之后:

```python
    async def growth_activity_remote(self, days: int, tz_offset: int) -> tuple[dict | None, str]:
        """练棋日历,口径同 `growth_summary_remote`。`tz_offset` 原样带给云端 —— 按盒子这边的「今天」切天。"""
        return await self._cloud_first(
            "growth activity",
            "/growth/activity",
            lambda: self._remote_client.get_growth_activity(days, tz_offset),
        )
```

`growth.py`,文件末尾(不用新增 import:仓储从 `app.state` 取):

```python
# ── 近一年练棋日历(G4)──────────────────────────────────────────────────────

DEFAULT_ACTIVITY_DAYS = 365
#: 东几区的分钟数(北京 = 480)。世界上的时区落在 UTC−12 … UTC+14。
MIN_TZ_OFFSET, MAX_TZ_OFFSET = -12 * 60, 14 * 60


def _looks_like_activity(payload: Any) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get("window_days"), int):
        return False
    days = payload.get("days")
    return isinstance(days, list) and all(
        isinstance(d, dict)
        and isinstance(d.get("date"), str)
        and isinstance(d.get("games"), int)
        and isinstance(d.get("solved"), int)
        for d in days
    )


@router.get("/activity")
async def growth_activity(
    request: Request,
    days: int = DEFAULT_ACTIVITY_DAYS,
    tz_offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """近一年练棋日历:每天下完几局、首次解出几道题,**只列有活动的日子**。

    按客户端时区切天(`tz_offset`)—— 按 UTC 切,北京早上 8 点前下的棋会落到前一天。
    盒子上先问云端(跨设备完整);退回本机时如实标 `local_cache`,屏上写「本机记录」。
    """
    if not 1 <= days <= MAX_WINDOW_DAYS:
        raise HTTPException(status_code=422, detail=f"days must be 1..{MAX_WINDOW_DAYS}")
    if not MIN_TZ_OFFSET <= tz_offset <= MAX_TZ_OFFSET:
        raise HTTPException(status_code=422, detail=f"tz_offset must be {MIN_TZ_OFFSET}..{MAX_TZ_OFFSET}")

    repo = getattr(request.app.state, "growth_activity_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="growth activity unavailable on this node")

    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        remote, reason = await dispatcher.growth_activity_remote(days, tz_offset)
        if remote is not None and _looks_like_activity(remote):
            return {**remote, "authority": "cloud"}
        if remote is not None:
            logger.warning("growth activity: cloud answered 200 with an unrecognised shape, using local cache")
            reason = "remote_bad_payload"
        logger.info("growth activity: serving local cache (%s)", reason)

    return {
        "window_days": days,
        "days": repo.daily(current_user.id, days=days, tz_offset=tz_offset),
        "authority": "local_cache" if dispatcher is not None else "this_node",
    }
```

`server.py`,**两处** lifespan 各在 `app.state.report_diagnosis_repo = …` 那一行之后加(手写,不整文件跑 black):

```python
    # 成长屏「近一年练棋日历」:逐日数对局与首次解题(盒上只在连不上云端时兜底)。
    from katrain.web.core.growth_activity import GrowthActivityRepository

    app.state.growth_activity_repo = GrowthActivityRepository(session_factory)
```

- [x] **Step 8: 跑,确认通过;格式化只动基线干净的文件**

```bash
CI=true uv run pytest tests/web_ui/test_growth_activity.py tests/web_ui/test_growth_authority.py tests/web_ui/test_growth_diagnosis.py tests/web_ui/test_growth_trend.py -q
uv run black -l 120 katrain/web/core/growth_activity.py katrain/web/api/v1/endpoints/growth.py katrain/web/core/repository.py tests/web_ui/test_growth_activity.py
git diff --stat
git status --short katrain/config.json katrain/web/ui/src/kiosk/__tests__/fixtures/   # pytest 改写过的话 git checkout 还原
```

预期:全部通过;`git diff --stat` 只列本 Task 的六个文件。

- [x] **Step 9: 提交**

```bash
git add katrain/web/core/growth_activity.py tests/web_ui/test_growth_activity.py katrain/web/api/v1/endpoints/growth.py katrain/web/core/repository.py katrain/web/core/remote_client.py katrain/web/server.py
git diff --cached --stat
git commit -m "$(cat <<'EOF'
feat(growth): GET /growth/activity —— 近一年练棋日历的后端(G4)

一格 = 当天下完的对局(play_ai/play_local/play_human 白名单)+ 当天首次解出的题,
按客户端时区切天。盒上先问云端,退回本机如实标 local_cache。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

- [x] **Step 10: 集成 —— 真服务端 + 真浏览器**

沿用 G1–G3 的集成脚手架(scratchpad `int/serve.py`:`create_app(enable_engine=False)` 起在 :8123,独立 SQLite;
**不走 `python -m katrain`**,它退出时会改写 `~/.katrain/config.json`)。先 `npm run build`(服务端发的是构建产物)。

1. 快照 `~/.katrain/config.json`;起服务:
   `KATRAIN_DATABASE_URL="sqlite:///$SP/int/int.db" KATRAIN_SECRET_KEY=<≥32 位> CI=true uv run python $SP/int/serve.py`。
2. 造数据:
   - **经真接口**建一局 `POST /api/v1/user-games/`(`source: "play_ai"`)—— 证明真的落账路径写出的来源在白名单里,落在今天。
   - 用 `sqlite3` 直接插历史:几天前的对局若干、一局 `source='import'`(不该算)、北京凌晨 2 点那种跨 UTC 日界的一局、
     `user_tsumego_progress` 两道解出一道没解出。
3. `curl` 接口(`tz_offset=480`),记下 `days` 条数与今天那条的 `games + solved`。
4. 真浏览器 1024×600 打开 `/kiosk/growth`,读 `growth-cal-days` 的文本、今天那格(`.gcal__c.is-today`)的 `data-level`、
   跨日界那局所在格子的 `data-date`,**与第 3 步的数对上**(天数 = `days` 条数;档位按 0/1–2/3–5/6–9/10+ 由今天的合计推出)。截一张图存档。
5. 停服务;`diff` 快照与 `~/.katrain/config.json`,必须一致;`git status` 干净。

> **验收记录(2026-09-22,`78a94bab`)**
> - 单测:仓储 4 + 端点 5 全过;变异 —— 删掉 `since` 换 UTC 那一段,`test_window_edges_…` 变红,改回变绿。
>   成长四个测试文件合计 45 passed。
> - 集成(真服务端 :8123 + 独立 SQLite + Chromium 1024×600,`timezoneId=Asia/Shanghai`):
>   造数前写死的期望 —— 09-10 解 10 题(档 4)、09-16 一局(UTC 09-15 20:00,跨日界,档 1)、
>   09-19 三局(另有一局 `import` 不算,档 2)、今天经真接口建一局 + 解 2 题(档 3 合计,档 2),共 4 天。
>   接口(`tz_offset=480`)逐条相符;`tz_offset=0` 时跨日界那局回到 09-15。
>   浏览器自己发出 `tz_offset=480`;屏上「4 天」、今天那格 `data-level=2`、亮着的格子恰是那四天且档位相符、
>   带日期的格子 365 个。`~/.katrain/config.json` 前后一致,`git status` 干净。
> - 顺带看见(**不在本 Task 改**):同一屏「近 30 天对局」是 6,日历同期对局合计 5 ——
>   G2 那一格的 `count_since` 连导入的谱也数,日历按 PRD 只数自己下的。已记入交付说明待 Fan 定。

- [x] **Step 11: Fixture 删除条件核对**

```bash
git grep -n "FULL_ACTIVITY\|EMPTY_ACTIVITY\|mulberry32" -- katrain/web/ui/src
```

预期:无输出(日历的假数据只在 `katrain/web/ui/tests/` 与 `__tests__/` 下,生产代码里没有)。

---

### Task 9: 四图对比与承重实测(屏 22)

**Files:**
- Modify: `katrain/web/ui/tests/kiosk-screen-22-growth.spec.ts`(追加两条)
- Modify: `superpowers/tracks/kiosk-go-shell-align/visual/22-*/`(四图重取产物)

- [ ] **Step 1: 承重实测 —— 先造到最满**

```ts
// 追加到 tests/kiosk-screen-22-growth.spec.ts
test('诊断三段 + 样本量 + 样本不足那句都在时,右栏不溢出', async ({ page }) => {
  await page.route('**/api/v1/growth/diagnosis**', (r) => r.fulfill({ json: {
    window_days: 90, reports: 2, skipped_without_color: 3, graded_moves: 120,
    phases: [
      { phase: 'opening', graded: 40, bad: 12 },
      { phase: 'midgame', graded: 50, bad: 9 },
      { phase: 'endgame', graded: 30, bad: 11 },
    ], authority: 'cloud',
  } }));
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.goto('/kiosk/growth');
  await expect(page.getByTestId('diag-thin')).toBeVisible();
  const overflow = await page.evaluate(() => {
    const el = document.querySelector('.gcol') as HTMLElement;
    return { scroll: el.scrollHeight, client: el.clientHeight };
  });
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.client + 1);  // 右栏不许被撑破
});
```

- [ ] **Step 1b: 左栏(走势块)承重**

> 左栏是**固定高度**的一栏:走势块长出去会把「升降的规矩」三行挤下去。造一条 30 天的走势再量。

```ts
test('左栏加了走势块之后,「升降的规矩」三行仍在视口里', async ({ page }) => {
  await page.route('**/api/v1/growth/summary**', (r) => r.fulfill({ json: {
    window_days: 30, games_in_window: 40, ranked_total: 40,
    ranked_wins_in_window: 20, ranked_losses_in_window: 20, by_opponent_rung: [],
    authority: 'cloud',
    rung_trend: [...Array(30)].map((_, i) => ({
      date: `2026-09-${String(i + 1).padStart(2, '0')}`, rung: 10 + (i % 5), rank_name: `${10 + (i % 5)}档`,
    })),
  } }));
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.goto('/kiosk/growth');
  await expect(page.getByTestId('growth-trend')).toBeVisible();
  const rules = await page.locator('.grules').boundingBox();
  expect((rules?.y ?? 0) + (rules?.height ?? 0)).toBeLessThanOrEqual(600);   // 没被挤出屏
});
```

- [ ] **Step 2: 再量最空那一态**

> 「先造到会溢出」只对**溢出类**成立;**塌陷类相反** —— 内容一多自己就被撑住了。诊断块用 `flex` 传高度,空态那一版内容最少,必须单量一次。

```ts
test('一份报告都没有(最空)时,诊断块不塌,两块诊断仍然等高', async ({ page }) => {
  await page.route('**/api/v1/growth/diagnosis**', (r) => r.fulfill({ json: {
    window_days: 90, reports: 0, skipped_without_color: 0, graded_moves: 0, phases: [], authority: 'cloud',
  } }));
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.goto('/kiosk/growth');
  await expect(page.getByTestId('diag-empty')).toBeVisible();
  const [a, b] = await page.locator('.gdiag > .panel').evaluateAll(
    (els) => els.map((el) => Math.round(el.getBoundingClientRect().height)),
  );
  expect(Math.abs(a - b)).toBeLessThanOrEqual(1);   // 关系式期望,不钉具体像素
});
```

- [ ] **Step 3: 跑**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-22-growth.spec.ts
```

- [ ] **Step 4: 四图重取(屏 22)**

```bash
npm run fourup            # 会重跑 27 屏;只看 22 那一组
cd /Users/fan/Repositories/katrain-kiosk-go-growth
git status --short superpowers/tracks/kiosk-go-shell-align/visual/ | head -20
```

**跑两次**,把两次的 22 那组实现图互相 diff,得到这一屏自己的抖动底(屏 22 是 DOM 屏,底约 200 像素)。
只提交**真的变了**的那几张;其余 `git checkout HEAD -- <屏目录>` 还原。

- [ ] **Step 5: 人眼看四图,交 Fan 确认**

四张一起看(参考 / 实现 / 并排 / 差异),逐项比:构图、几何间距、组件层级、字体色彩、文案、状态语义。
**这一步的结论要 Fan 明确确认**(CLAUDE.md 硬性关卡);没确认之前不要把这条赛道报成完成。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/tests/kiosk-screen-22-growth.spec.ts superpowers/tracks/kiosk-go-shell-align/visual/
git commit -m "$(cat <<'EOF'
test(growth): 屏 22 承重实测(最满/最空)与四图重取

最空那一态单量:塌陷类的缺陷在内容一多时会被自己撑住,量不出来。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: 收尾验证与交付说明

- [ ] **Step 1: 双基线 diff**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-growth
BASE="$(git rev-parse --absolute-git-dir)/growth-baseline"
CI=true uv run pytest tests --continue-on-collection-errors -q > "$BASE/after-py.log" 2>&1
grep '^FAILED\|^ERROR' "$BASE/after-py.log" | sort -u > "$BASE/after-py.txt"
comm -13 "$BASE/before-py.txt" "$BASE/after-py.txt"
cd katrain/web/ui
npx vitest run --reporter=json --outputFile="$BASE/after.json" > "$BASE/after.log" 2>&1
node "$BASE/failed-names.cjs" "$BASE/after.json" > "$BASE/after-failed.txt"
comm -13 "$BASE/before-failed.txt" "$BASE/after-failed.txt"
```

预期:两个 `comm` 都为空。

- [ ] **Step 2: 类型、构建、格式**

```bash
npx tsc -b && npm run build && npm run build:kiosk-2d; echo "exit=$?"
cd /Users/fan/Repositories/katrain-kiosk-go-growth && uv run black -l 120 --check katrain/web tests; echo "black=$?"
```

- [ ] **Step 3: 新增文案 key 清单 + 交付说明**

```bash
git diff 7a152df1..HEAD -- katrain/web/ui/src | grep -o "t('[a-z]*:[a-z_0-9]*'" | sort -u
```

交付说明里写清:① 做了 G1 G2 G3 G4(G3 是 Fan 2026-09-21 裁定的「画档位」;G4 是 09-22 新增的练棋日历,smartbox 设计分支 `9d359bac9` 未 push);② 新增 key 清单;③ 四图与承重结论(附 Fan 确认);
④ **部署顺序**:先 home-ubuntu 再 ucloud;⑤ 云端未部署期间盒上的表现(胜率标签退回升降级口径、诊断走本机缓存或 503 ⇒ 屏上「诊断没读到」)。

- [ ] **Step 4: 部署前自检(交给部署会话)**

- 新列是可空的 ⇒ 老库启动时 `add_missing_columns` 会补上,不触发 SQLite 的 drift 重建;
- `user_games` 不在 `PROTECTED_TABLES` 里,但**也不要**把它加进去(那是账本表的名单);
- 云端与盒端版本不一致时的两条路径都验过(Task 3 的 `_REQUIRED_KEYS` 那条注释 + Task 4 的 `scope: 'ranked'` 用例)。

---

