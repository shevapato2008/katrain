# 41 档 AI 阶梯接入升降级对弈 — 设计

**日期：** 2026-08-04
**状态：** 待用户批准
**范围：** 用 41 档阶梯替换升降级对弈中的拟人 AI，并把升降级账本真正接通
**上游：** `2026-08-03-41-tier-ai-ladder-finalization-design.md`（标定设计，本文不重复其 §1–§5）

---

## 1. 现状（已核对代码，非转述）

### 1.1 今天的「升降级对弈」不升降级

- 升降级规则 `katrain/web/core/ranking.py:39 calculate_rank_update` 唯一调用者是
  `katrain/web/core/game_repo.py:77 record_multiplayer_game`，而后者只在人人对弈路径被调用
  （`server.py:1247/1301/1446/1487`、`api/v1/endpoints/auth.py:446`）。
- 人机对局走 `server.py:1125-1210 _record_ai_game`，**没有任何段位调用**。
- galaxy 的升降级页从不调 `POST /api/game/setup`，`session.game_type` 停在
  `interface.py:160` 的初值 `"free"`，对局因此以 `game_type="free"` 落库
  （`server.py:1178`）。
- `?mode=rated` 是纯客户端 URL 参数，唯一实际作用是在对局页隐藏分析工具
  （`GamePage.tsx:331/340/355`）。服务端的反作弊 chokepoint（`interface.py:234-235, 817-833`）
  因为 `game_type` 从没被置为 rated 而**并未真正生效**。

### 1.2 由此产生的活死循环

`HvHLobbyPage.tsx:126-128`：`gameType === 'rated' && user?.rank === '20k'` 时弹窗
「must complete your AI Rating series (3 games)」并跳转 `/galaxy/play/ai?mode=rated`。
但人机局不改 `users.rank`，用户永远是 `20k`，永远被跳回来。**升降级人人对弈对新用户不可达。**

### 1.3 41 档阶梯已建好但全档失败关闭

- `katrain/core/ladder.py:481-485` 把 41 档**全部硬编码**为
  `certification_status="provisional"` + `availability="unavailable"`，没有任何按档分支。
- `resolve_available_rung`（`ladder.py:504-510`）因此对每一档抛 `LadderUnavailable`，
  任何带 `ladder_rung` 的 `POST /api/new-game` 直接 422（`server.py:752-758`）。
- 31 档有冻结配方，10 档（准1段–准8段、准9段、职业顶尖）连合格候选都没筛出来。
- C31–C36 全部记为 `exploratory_only`，按 §C19 precedent 不得用于拟合或发布。

### 1.4 拟人的两个诚实性缺陷（本次一并解决）

- `ai.py:1647-1653`：引擎没加载 humanSL 网时，拟人**静默降级**为 `PolicyStrategy`——
  用户以为在跟 10k 下，实际在跟裸 policy 下，界面无任何提示。
- `ai.py:1656-1664` + `AiSetupPage.tsx:197`：页面只发 `human_kyu_rank`，`modern_style`
  取自本地持久化 config。同一个「10k」在不同机器上解析成 `rank_10k` 或 `preaz_10k`，
  是两个不同强度的档。

---

## 2. 产品决定（用户已确认）

| 问题 | 决定 |
|---|---|
| 范围 | 引擎替换 **+** 升降级账本一起做 |
| 标定阻塞 | 管道先行，认证位最后翻 |
| 拟人去留 | 只在升降级里换掉；自由对弈（`mode=free`）保留拟人 |
| 段位滑块 | **移除**，对手档位由账本决定 |
| 段位体系 | **只有一个段位**，只由人机升降级对局驱动；人人对弈不影响它；不另设一套 |
| 旧 game_type 乱帐 | 一并理清 |

### 2.1 「只有一个段位」的推论（本次的行为变更，须显式确认）

- `record_multiplayer_game` 中对 `calculate_rank_update` 的调用**断开**。
  人人对弈从此不改变段位。
- `users.rank` / `users.net_wins` / `users.elo_points` / `rating_history` 停止写入，
  所有读点改读阶梯段位。旧数据保留不迁移、不删除。
- rated 人人对弈的入场门槛从「打满 3 盘升降级人机」改为「**已完成定级**」
  （`ai_ladder_rung IS NOT NULL`）。这同时修掉 §1.2 的死循环。

---

## 3. 数据模型

### 3.1 `users` 新增列（全部 nullable / 有默认值，不破坏既有行）

| 列 | 类型 | 语义 |
|---|---|---|
| `ai_ladder_rung` | `Integer` nullable | **唯一段位真源**，1–41；`NULL` = 未定级 |
| `ai_ladder_net_wins` | `Integer` default 0 | 累计净胜，`±3` 触发升降后归零 |
| `ai_ladder_placement_lo` | `Integer` nullable | 定级二分窗口下界 |
| `ai_ladder_placement_hi` | `Integer` nullable | 定级二分窗口上界 |
| `ai_ladder_placement_games` | `Integer` default 0 | 已完成的有效定级局数，0–5 |

定级完成的判据是 `ai_ladder_rung IS NOT NULL`；定级中的判据是
`ai_ladder_rung IS NULL AND ai_ladder_placement_lo IS NOT NULL`。

### 3.2 新表 `ai_ladder_ledger`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | `Integer` PK | |
| `user_id` | FK `users.id` | |
| `game_id` | `String(32)` **UNIQUE**，无 FK | 幂等约束，见下 |
| `is_placement` | `Boolean` | 定级局 / 常规升降级局 |
| `opponent_rung` | `Integer` | 本局 AI 实际档位 |
| `won` | `Boolean` | |
| `rung_before` / `rung_after` | `Integer` nullable | 定级期间 before 为 NULL |
| `net_wins_before` / `net_wins_after` | `Integer` | |
| `placement_lo_after` / `placement_hi_after` | `Integer` nullable | |
| `created_at` | `DateTime` | |

`game_id` 的唯一约束是幂等的唯一保证：重复结算同一局直接违反约束、事务回滚、段位不动。

**`game_id` 不能建 FK 到 `user_games.id`**：`_record_ai_game` 走
`repository_dispatcher.user_games_create`（`core/repository.py:273-289`），在线时对局行写到**远端**
仓库、本地根本没有那一行，FK 会直接违反。`users` 表则不在 dispatcher 覆盖范围内（它只代理
tsumego / kifu / user_games），段位与账本都是本地权威。

### 3.3 账本必须防住 SQLite 漂移重建

`core/auth.py:init_db` 有一段 SQLite drift 保护：ORM 列与实际表不符时 **drop 并重建**该表，
只有 `migrations.BILLING_TABLES`（`migrations.py:19`）里的表被豁免。
`ai_ladder_ledger` 存的是用户真实资产（段位），必须一并加进那个禁止 drop 的集合——
否则一次列变更就会静默清空所有人的段位历史。

### 3.4 不做的事

- 不迁移 `users.rank`。它保留为 legacy 列，停止写入，**所有读点一次性改完**——
  不留半读半写（那会让界面显示一个永远停在 20k 的假段位，违反状态诚实）。
- 不新建 elo 列。设计文档 §6 的账本只有净胜计数，没有 elo。

---

## 4. 认证开关（管道先行的实现）

### 4.1 按档认证表

`ladder.py` 现在的硬编码换成一个**显式的、按档列举的**真源：

```python
# 标定通过的档位在此逐档登记。空集 = 全部 provisional。
# 每次登记必须引用 EXPERIMENTS.md 中通过正式相邻验证的那一批。
_CERTIFIED_RUNGS: FrozenSet[int] = frozenset()
```

`LADDER_LEVELS` 构造时按档取值，而不是常量：

```python
certified = rung in _CERTIFIED_RUNGS and recipe is not None
certification_status = "certified" if certified else "provisional"
availability = "available" if certified else "unavailable"
```

### 4.2 开发期放行开关

环境变量 **`KATRAIN_LADDER_ALLOW_PROVISIONAL=1`**。

- 只放行 `resolve_available_rung` 的那道门，让未认证档在开发/自测环境可以真的下棋。
- **不改变 API 返回的 `certification_status` / `availability`**——API 永远如实报告
  `provisional` / `unavailable`。
- 用环境变量而非配置项，因为 `--ui web` 退出时会写回 `~/.katrain/config.json`
  （见 memory `reference_katrain_web_writes_config.md`），配置项会污染用户配置。

### 4.3 前端如实呈现

- 开关关闭（生产默认）：对局按钮 **disabled**，卡片显示「该档位尚未完成标定，暂不可对局」。
  不伪装成可用，不静默降级到拟人或任何其他 AI。
- 开关开启：按钮可用，但档位名旁挂**「未标定」角标**。用户看到的状态与服务端返回的
  `certification_status` 严格一致。

---

## 5. API 契约

### 5.1 `GET /api/ladder/me` — 升降级页面的唯一数据源

```jsonc
{
  "rung": 26,                       // null = 未定级
  "rank_name": "3段",               // null = 未定级
  "net_wins": 1,                    // -2..2
  "threshold": 3,                   // ±3 升降
  "placement": null,                // 或 {"games_done": 2, "games_total": 5, "lo": 17, "hi": 32}
  "recent": [                       // 最近 5 局，只从账本生成
    {"won": true,  "opponent_rung": 26, "opponent_rank_name": "3段"},
    {"won": false, "opponent_rung": 26, "opponent_rank_name": "3段"}
  ],
  "next_opponent": {
    "rung": 26,
    "rank_name": "3段",
    "certification_status": "provisional",   // 如实
    "availability": "unavailable",           // 如实
    "route": "server"
  },
  "playable": false,                // 综合判断：档位可用 或 开发开关已开
  "blocked_reason": "not_certified" // null | "not_certified" | "engine_unavailable"
}
```

**权威边界：对手档位由服务端计算，绝不接受客户端传入。** 这是整个升降级可信度的根。

### 5.2 `POST /api/ladder/start-game`

请求体只有对局设置（棋盘、规则、计时），**没有档位字段**：

```jsonc
{ "session_id": "...", "size": 19, "komi": 7.5, "rules": "japanese",
  "main_time": 600, "byo_length": 30, "byo_periods": 3 }
```

服务端：
1. 读当前用户的 `ai_ladder_rung` / placement 状态，算出本局对手档位。
2. `resolve_available_rung(opponent_rung)`——不通过则 **409 + 明确的
   `blocked_reason`**，不是 422「invalid ladder_rung」那种误导信息。
3. 置 `session.game_type = "ai_ladder_ranked"`（服务端签发，客户端无法伪造）。
4. `new_game(..., ladder_rung=opponent_rung)`，AI 方 `player_subtype = "ai:ladder"`。

### 5.3 结算

沿用现有 `_record_ai_game` 落库路径（`server.py:1125-1210`），在其中加分支：
`session.game_type == "ai_ladder_ranked"` 时，用对局行返回的 id 作为 `game_id`，
**在一个本地事务内**写 ledger 行 + 更新 `users` 的段位与净胜。不可判定局（无胜负）不进账本。

对局行本身可能落在远端（§3.2），所以「同一事务」只覆盖**本地的账本 + 用户段位**这两处——
它们必须原子，否则会出现账本记了而段位没动、或反之。对局行与账本之间的一致性由
`game_id` 唯一约束兜底：对局行写失败则不调用结算；结算重放则唯一约束拒绝。

---

## 6. 升降级与定级算法（照搬上游设计文档 §6，此处只记落地细节）

### 6.1 定级（未定级用户）

- 窗口：`lo = clamp(mapped - 16, 1, 10)`，`hi = lo + 31`。
  `mapped` 由旧 `users.rank` 映射（`20k…1k` → 1…20；`1d…9d` → 22,24,…,38；更高夹到 38）。
  **旧段位只用于开窗，用完即弃**，不再有其他用途。无旧值用固定窗口 1…32。
- 每轮对手 `mid = floor((lo + hi) / 2)`；用户胜 `lo = mid + 1`，负 `hi = mid`。
- 不可判定局重赛且不占 5 盘之一（不写账本）。
- 5 个有效胜负后必有 `lo == hi`，写入 `ai_ladder_rung`，清空 placement 三列。

### 6.2 常规升降级（已定级用户）

- 对手档位 = 用户当前档位（同档）。
- 胜 `net_wins += 1`，负 `-= 1`；达 `+3` 升一档并归零，达 `-3` 降一档并归零。
- 1 / 41 边界饱和。
- 最近 5 局展示条**只从账本生成**——3 胜 2 负不会升级，展示条不做任何自己的推断。

---

## 7. 页面形态

升降级设置页（`galaxy/pages/AiSetupPage.tsx`，`mode=rated` 分支）：

- **移除**「AI选点方式」下拉（本来就 `disabled`）和「段位 20k→9d」滑块。
- 新增「你的阶梯段位」卡片：档位中文名、净胜计数、最近 5 局圆点、本局对手档位。
- 未定级用户该卡片显示「定级赛 第 N/5 局 · 本局对手 X」。
- 保留棋盘与规则卡片、时间卡片。

自由对弈（`mode=free`）**完全不动**——拟人、滑块、其余 16 种选点方式原样保留。

具体视觉走 `frontend-design` → `ui-ux-pro-max`，四图对比后由用户确认，本文不预设样式。

---

## 8. 垂直切片划分

共享基础（最小，只建当前旅程要用的）：`ladder.py` 按档认证表 + 开发开关、
`users` 五列 + `ai_ladder_ledger` 表、`GET /api/ladder/me`。

| 切片 | 用户旅程 | 完成判据 |
|---|---|---|
| **S1** | 新用户进升降级 → 打完 5 局定级赛 → 拿到段位 | 真机走完 5 局，`ai_ladder_rung` 写入，账本 5 行，界面全程显示第 N/5 |
| **S2** | 已定级用户打常规升降级 → 净胜 ±3 升降一档 | 真机连胜 3 局升一档、账本归零；连败 3 局降一档 |
| **S3** | 旧 game_type 乱帐理清 + PvP 段位解耦 | galaxy 调 `/api/game/setup`；kiosk/galaxy 字符串统一；PvP 不再改段位；rated PvP 门槛改为「已定级」；§1.2 死循环消失 |

S1 先于 S2，因为「新用户第一次打开升降级对弈」是真实的第一个旅程，且 S1 跑通后 S2 天然有数据可测，
不需要造段位 fixture。

S3 排最后：它改的是既有人人对弈行为，风险边界与 S1/S2 不重叠，且不阻塞前两片。

---

## 9. 已知风险（带着做，不假装不存在）

1. **生产环境本功能在标定完成前是暗的。** `_CERTIFIED_RUNGS` 为空集时任何档位都不可对局，
   页面如实显示不可用。这是「管道先行」的直接代价，也是设计文档 §6「未认证档失败关闭、
   不降级到另一档AI」的要求。
2. **正式验证门槛在 5d–8d 区间欠功率。** §C36 证明 `rank_6d@1` 与 `rank_5d@1` 的差距
   小于 80 盘可分辨的尺度；5d/4d、8d/7d 亦为 10–10。40 组相邻边里至少 3 条预期卡住。
   这不阻塞本次工程，但决定了 `_CERTIFIED_RUNGS` 何时能非空。
3. **10 档待拟合档位无合格候选。** 准1段–准8段、准9段、职业顶尖至今没有任何候选同时满足
   「弱于上档且强于下档」。即使标定推进，这 10 档也可能长期缺席。
4. **`users.rank` 读点改不干净会显示假段位。** 必须一次性改完所有读点，靠 grep 清单验收。

---

## 10. 本次不做

- 不动自由对弈的任何行为。
- 不动 kiosk 的 AI 设置页（它没有阶梯 UI，且强度配置不分叉是上游设计文档 §6 的约束，
  kiosk 接入排在标定之后）。
- 不做 RK3562 本地/服务端路由决策（上游 §6 明确要等基准表）。
- 不修 `ladder.py` 里遗留的 37 档 `LADDER_RUNGS` 表和「1..37」文案，除非它们挡路。
- 不动 `tests/core/test_ladder_strategy.py` 那 21 条红测试，除非本次改动使它们可修复。
