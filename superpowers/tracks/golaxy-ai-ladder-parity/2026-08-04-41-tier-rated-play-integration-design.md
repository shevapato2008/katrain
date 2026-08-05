# 41 档 AI 阶梯接入升降级对弈 — 设计

> **⚠️ 2026-08-05 结局：本文描述的 S1–S4 实现已从分支上撤下，不再是代码现状。**
>
> `origin/develop` 上同期有一套独立完成的同功能实现（`codex/ai-ladder-ranked-module`，
> 37 个提交里占 19 个），两者共用同一个 `game_type='ai_ladder_ranked'`，并存会让
> 同一局棋被两条结算路径各记一次账。逐条对照见
> `artifacts/ladder-implementations-compare.html`；用户拍板**以 develop 那套为准**
> （它在结算正确性上更深：待结算对局落库、冻结对手配置快照、行锁+乐观锁、
> 数据库层约束、旧账本迁移）。合并提交 `ce941d28`。
>
> 本文以下内容仍然有效的部分：**产品决策**（六条锁定项）、**标定条件为什么必须固定**、
> **各状态的文案与语义**、以及 S1–S4 各次验收里记录的事实（尤其 RK3562 设备走查）。
> 失效的部分：`ladder_repo` / `ladder_progress` / `ladder_catalog`、`/api/ladder/*`、
> `users.ai_ladder_*` 列与 `ai_ladder_ledger` 表、以及 kiosk/galaxy 那几个自建组件——
> 这些文件都已删除，对应能力现由 `katrain/web/core/ai_ladder_ranked.py`、
> `/api/v1/ai-ladder/*`、`src/features/aiLadder/` 承担。
>
> 撤下时移植到 develop 那套上的三项（提交 `8bafb160`）：引擎失联不入账
> （`settle_game(engine_stalled=...)` → `reason=engine_unavailable`）、盘面条件收归服务端
> （`AiLadderStartRequest` 不再收 board_size/rules/komi/handicap；此前 kiosk 实发 komi 6.5、
> galaxy 实发 6.5+日本规则）、大厅闸改读段位而非数 rated 局数。

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

## 6. 升降级与定级算法

> **实现时的修正（2026-08-04）：算法在「可打档位」上运行，不在 1–41 的原始档号上。**
>
> 41 档里有 **10 档根本没有配方**（准1段–准8段、准9段、职业顶尖），不是「未认证」而是
> 连强度配置都没拟合出来——`resolve_available_rung` 对它们照样抛错，开发开关也无效。
> 实测：在 1–41 原始档号上做二分，无旧段位时 32 档窗口里有 6 个无配方档会被**座为对手**，
> 且 32 个**落点**里同样有 6 个无配方；旧段位 5d 以上时各为 10 个。也就是说用户可能打完
> 5 局定级赛落在一个永远打不了的档位上，已定级用户净胜 +3 也可能升进一个打不了的档。
>
> 因此定级与升降级都在**有配方的档位**上运行，按强度编号 `1..N`（今天 N=31）。
> `katrain/web/core/ladder_catalog.py` 独占这层映射，`ladder_progress.py` 保持纯算术。
> 标定补齐后 N 自行长回 41，缺失的准N段会插回已有段位之间。两条测试钉死这件事：
> **对手和落点永远不会是无配方档**。

### 6.1 定级（未定级用户）

- 窗口：`lo = clamp(seed - 16, 1, N - 32 + 1)`，`hi = lo + 31`，**恒为 32 宽**。
  `seed` 由旧 `users.rank` 经档号映射到位置（`20k…1k` → rung 1…20；`1d…9d` → rung 22,24,…,38；
  更高夹到 38）。**旧段位只用于开窗，用完即弃**。无旧值用固定窗口 1…32。
- N 小于 32 时窗口仍是 32 宽，超出阶梯顶端的搜索槽**钳到最高位置**。
  若改成 31 宽，部分分支第 4 局就塌成单点、第 5 局会把 `lo` 推过 `hi`（实测踩过）。
  代价只是可打档位不足 32 时最高档由 2 条路径抵达。
- 每轮对手 `mid = min(floor((lo + hi) / 2), N)`；用户胜 `lo = mid + 1`，负 `hi = mid`。
  窗口收窄用**未钳的搜索槽**，保证每轮严格折半。
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

| 切片 | 用户旅程 | 完成判据 | 状态 |
|---|---|---|---|
| **S1** | 新用户进升降级 → 打完 5 局定级赛 → 拿到段位 | 真机走完 5 局，`ai_ladder_rung` 写入，账本 5 行，界面全程显示第 N/5 | **已完成** 2026-08-04（`fef7d166` + `9221d69a`） |
| **S2** | 已定级用户打常规升降级 → 净胜 ±3 升降一档 | 真机连胜 3 局升一档、账本归零；连败 3 局降一档 | **已完成** 2026-08-05 |
| **S3** | 旧 game_type 乱帐理清 + PvP 段位解耦 | game_type 词表收口；PvP 不再改段位；rated PvP 门槛改为「已定级」；§1.2 死循环消失 | **已完成** 2026-08-05 |
| **S4** | kiosk 升降级对弈 | kiosk 上能定级、能升降级，与网页版同一份账本 | **已完成** 2026-08-05（`0b35b861`） |

### S4 实际验收记录（2026-08-05）

kiosk 的「升降级对弈」入口原本是假的：`/kiosk/play/ai/setup/ranked` 走的是通用
AI 设置页的 `ranked` 分支，让玩家自己在 20k→9d 下拉框里挑对手，用 `ai:human` 开局，
落库写 `game_type="ranked"`——而这个值不在 `RANK_MOVING_GAME_TYPES` 里，段位永远不动。
现在它和网页版共用 `/api/ladder/*` 与同一本 `ai_ladder_ledger`。

**版式决策**：设置页骨架（左 322px 面板 + 右表单 + 底部 CTA）是为盘面预览留的，
而升降级对局的盘面永远是同一张 19 路空盘。照搬骨架（变体 A）在 1024×600 下左右两列
各空出约 180px；改成横向三段（变体 B：段位 → 本局 → 用时 → 开始）后填满横屏，
定级赛的 5 步进度条也终于铺得开。两个变体都存档在
`artifacts/kiosk-ladder-setup.html`，A 标注为否决。

**契约收紧**（本切片新增，网页版同步生效）：

- `POST /api/ladder/start-game` 不再接受 `size` / `komi` / `rules`。每一档的棋力都是在
  19 路 · 中国规则 · 贴 7.5 下量出来的（`calibration/run_selfplay.py:119-121`），
  客户端能挑 9 路，就等于让一个档位在它的档名不再成立的局面里计分。三者由
  `ladder_repo.LADDER_BOARD_SIZE / LADDER_RULES / LADDER_KOMI` 固定，并经
  `GET /api/ladder/me` 的 `game_setup` 报给页面显示——页面只读出，不参与决定。
  顺带修掉网页版那两个禁用下拉框：它们显示 19x19 / Japanese，而服务端发的是中国规则。
- `main_time` → `main_time_minutes`、`byo_length` → `byo_length_seconds`。
  `timer/main_time` 存的是分钟（每个消费方都乘 60），而 S1 的网页版传的是 `mainTime * 60`，
  于是每一局升降级都发了 600 分钟主时间。单位进名字，这个错就再犯不了。
- `POST /api/game/setup` 删掉 `"ranked"` 分支——已无调用方，留着只是给下一个人一个
  写出假排位局的机会。
- 阶梯 AI 落座时带档名（`AI 5级`），否则对局页棋手卡写着「白棋 · 无级别」，
  而这一局的全部意义就是对手的段位。

**本机验收（20 项全过）**：19 路/中国/7.5 固定 · 请求里多塞 `size=9` 被忽略 ·
`game_type` 服务端签发 · `analysis_allowed=false` · `ai:ladder` 落座 · 主时间 10 分钟 ·
`/api/game/setup` 的 ranked 已死 · 认输后账本走到定级 1/5 · 对手档位随败绩由 16 降到 8。
浏览器实机再走一局：设置页 → 开局 → 认输 → 终局卡内出现「定级赛 第 3 局 / 本局负 /
再打 2 局定下你的段位」。计分局下悔棋与回退按钮消失（`nav-controls` 子节点 6 → 3）。

**承重结构实测 @1024×600**（关系式先写死，再读数）：

| 量 | 期望 | 实测 |
|---|---|---|
| 该滚的是谁 | 页面自己的 `ladder-setup-scroll`，不是外壳 | `main.scrollHeight === clientHeight`，外壳不溢出 ✓ |
| 能不能滚 | 最高态（已定级 + 未标定 + 最近 5 局）内容 ≤ 内容盒 | band padding 16px 时 524 > 481，**开始按钮被压到折线下**；改 12px 后 481 = 481 ✓ |
| 手指拨得动 | 真滚轮派发后 scrollTop ≠ 0 | 溢出时成立（Chromium 异步应用，须 poll；立即读会误报 0） |
| 终局卡不被裁 | 卡片 bottom ≤ 600 且确认终局按钮在视区内 | 成立；已反证（给结算条加 `pb:400px` 时该断言变红） |

闸门留在 `tests/ladder-kiosk-setup.spec.ts`，四条关系式各一条断言。

**S4 期间发现并修复的真缺陷**：`useGameSession` 的 resign/timeout 只等 WebSocket 广播，
不应用 HTTP 已经返回的终局 state。认输之后当前这台机器还停在一局服务端已经结束的棋里——
对升降级来说就是结算永远不出现。改成与 undo/redo 一致后，WebSocket 断着也能立刻出终局卡。

**i18n**：`ladder:*` 54 键 + `lobby:placement_required` 补齐 10 个启用语种
（`es` 在 `i18n.py` 的 `INACTIVE_LANGS` 里，.po 已写入但不编译 .mo）。
顺带补了三处 kiosk 设置页一直在漏中文的共享键（`My Color` / `Black Stone` /
`White Stone` / 四个用时预设 / `Ranked Game` / `Free Game` / `retry`）。
占位符 `{n}` `{rank}` 前端用 `String.replace` 只替换第一处，故每条译文里各只出现一次；
唯一的例外 `ladder:setup_size`（英文 `{n}×{n}`）改用 `replaceAll` 渲染。

档名 `5级` / `5段` 在任何语种下都保持中文，这是 41 档目录自己的命名，不是漏翻。

### S4 设备走查（RK3562，2026-08-05）

网线直连、`ssh rk3562-direct`。**不动生产部署**：本分支比 `origin/develop` 落后 37 个
提交、14 个文件重叠，覆盖 `vendor/katrain` 会把设备回退到分叉点，所以整棵树 rsync 到
`/mnt/data/ladder-walkthrough/` 独立跑（独立端口 8091 / 独立 SQLite / `HOME` 隔离，
免得 `--ui web` 退出时改到设备的 `config.json`），走完全部删除。生产树 mtime、
`/mnt/data/weiqi/weiqi-web.db`、launcher 的 `mode: idle` 走查前后一致。

驱动的是**设备自己的 Chromium**（kiosk unit 已开 `--remote-debugging-port=9222`，
经 ssh 隧道打 CDP），不是 Mac 上的 headless——面板实测 `1024×600 / dpr 1 /
maxTouchPoints 16`，就是目标 viewport 本身。Chromium 120 会以 Origin 头拒绝 CDP
握手，客户端需 `suppress_origin`。

- **20 项 API 验收**：设备上全过（与本机同一份脚本）。定级对手 = 位置 16 = `5级`，
  落在 Band A（humanSL 原生、humanv0 单 visit），正是设备 realtime_api 已有的配置。
- **承重实测（真机）**：最高状态（已定级 + 上下档 + 净胜条 + 最近 5 局）下
  `ladder-setup-scroll` 的 `scrollHeight 481 = clientHeight 481`，不溢出；开始按钮
  `top 532 / bottom 588`，完整落在其最近裁切祖先（`DIV.ladder-setup-scroll`，
  `top 119 / bottom 600`）内。与 Mac 上量的一字不差。定级中/已定级/未标定三态各量一次。
- **横划不再退出 app**：kiosk unit 里 2026-08-04 记的那条连环故障（横向拖动被当成
  overscroll → history back → 掉出整个 app）入口是难度滑条，本切片已删。真机上左右
  各拖一次，`location.pathname` 不变。
- **board 模式无分析泄漏**：server 模式下这局的 state 里带着 `analysis`
  （winrate/score），kiosk 图表面板会显示——但那是 `KATRAIN_MODE=board` 才关掉的
  每手自动评估（`interface.py:156`）。设备按生产配置跑 board 模式，实测显示
  `黑棋胜率: --%`，`analysis present: False`。`AI支招` 在升降级局里是灰的。
- **时钟单位**：真机上人类 `10:00` 起跳、正常倒数——S1 那个 600 分钟的 bug 在设备上
  也确认修掉了。

**走查抓到的真缺陷**（已修，见下一节）：设备的 HTTP 引擎不宣告 certified ladder
能力，`ai:ladder` 按设计一手不下，而画面停在「AI 思考中…」不动。

**仍未做**：RK3576 未走查（手上只有 RK3562）。board 模式下账号仍走云端
（`register`/`login` 无条件转发 remote），本轮是本地建号 + 本地签 JWT 注入
`localStorage` 绕过的；SSO 桥那条路没走。

### 引擎开不了局时的两个缺陷（设备走查发现，2026-08-05 修复）

`_CERTIFIED_RUNGS` 是空集、设备的 realtime_api 又不宣告 certified ladder 能力，
所以 `ai:ladder` 走 fail-closed 分支：**一手不下**。这条分支本身是对的（宁可不下，
也不能用没标定的强度落子还把结果记进账本），错的是它之后发生的事。

1. **假的加载态。** `interface._surface_ladder_unavailable` 早就置了
   `last_ladder_error`，注释里明写「User surface is the generic last_ladder_error
   flag」——但前端从来没有人读它（`grep last_ladder_error src/` 零命中）。屏幕停在
   绿色的「AI 思考中…」，而没有任何东西在思考，也永远不会有落子。
2. **凭空发出去的升段额度。** 对手的钟照走。galaxy 的 `PlayerCard` 到点自动
   `onTimeout` → 这局以「人类获胜」结算 → 写进升降级账本。kiosk 没接 `onTimeout`，
   所以那边只是永远卡住。

修法（服务端是权威，客户端只负责说实话）：

- `server.py _settle_ladder_game`：会话带着 `last_ladder_error` 时拒绝结算，
  `reason=engine_unavailable`。无论这局怎么结束（认输、超时、退出）都不进账本。
  标志由下一手成功的 AI 落子清除，所以中途卡一下又恢复的对局照常结算。
- kiosk / galaxy 同一句琥珀色横幅：「阶梯引擎不可用，AI 无法落子 · 本局不计入升降级，
  请退出本局」。`deriveAiTurnState` 新增 `ladderStalled`，与 `showThinking` 互斥。
- 终局卡/对话框新增 `engine_unavailable` 文案：「段位没有变动，也不占定级赛的局数」。
- galaxy `handleTimeout` 在该标志下直接返回——服务端已经不记分了，但那句「你赢了」
  也不该出现在屏幕上。

设备上按同一条链复验：横幅正确、thinking 横幅关闭、认输后终局卡显示未计入、
账本 6 行仍是 5 条种子 + 另一用户的 1 条，`laddertest` 一行未加。
`tests/web_ui/test_ladder_stalled_not_scored.py` 复现整条链，去掉服务端守卫即失败
（`assert True is False`）。

### S1 实际验收记录（2026-08-04）

真机（本地 PostgreSQL + 一次性账号，验完连同数据删除）：

- 未定级用户 → `placement {games_done: 0, games_total: 5, lo: 1, hi: 32}`，对手位置 16 = `5级`
- `next_opponent.certification_status = "provisional"` / `availability = "unavailable"`
  **即使开发开关已开**——开关只放行 `resolve_available_rung`，不改 API 说的话
- 黑认输 → `W+R` → 定级第 1 局判负 → 窗口 `1..32` 收到 `1..16` → 下一对手 `13级`，账本 1 行
- 对局以 `game_type = "ai_ladder_ranked"` 落库；`analysis_allowed = False`；`POST /api/undo` → 403
- 往 start-game 请求体注入 `ladder_rung: 41 / rung: 41 / game_type: "free"` → **全部无效**

S1 期间发现并修复的两个缺陷：

1. `ai_ladder_ranked` 不在反作弊集合里，计分局曾允许分析与悔棋。两处闸口现在都读
   `WebKaTrain.SCORING_GAME_TYPES`。
2. 先座 ai:ladder 玩家、后 `new_game`，中间窗口里该玩家没有注入档位。它按设计失败关闭
   （不落子），但会报错并白跑一次引擎查询。改为 `new_game` 先行。

S1 先于 S2，因为「新用户第一次打开升降级对弈」是真实的第一个旅程，且 S1 跑通后 S2 天然有数据可测，
不需要造段位 fixture。

### S2 实际验收记录（2026-08-05）

S2 补上了一件设计里没写、但旅程必需的东西：**对局结束后的段位结算反馈**。
升降级的全部意义就是档位会动，而在 S1 结束时，用户升了档在当场是看不见的——
只有回到设置页才会发现。新增 `GET /api/ladder/session-result/{session_id}` +
`LadderSettlementDialog`，六种状态：升段 / 降段 / 未升降（净胜条）/ 定级赛第 N 局 /
定级完成 / **本局未计入**（带原因）。

结算结论由服务端给，前端**不做两次 `/api/ladder/me` 相减**：差值为 0 分不出
「打平」和「这局没算」，而不可判定局必须能说出自己没算。

真机（本地 PostgreSQL + 一次性账号，11 局全部在**同一个 session** 上打完，验完连数据删除）：

- 定级 5 局 → `2段`(rung 24)，账本 5 行 `is_placement`
- 连胜 3 局：净胜 `0→1→2→0`，第 3 局 `moved=1`，`2段 → 3段`（**跳过 rung 25 准3段这个洞**）
- 连败 3 局：净胜 `0→-1→-2→0`，第 3 局 `moved=-1`，退回 `2段`
- 账本 11 行、`game_id` 全唯一；11 局全部以 `ai_ladder_ranked` 落库

S2 期间发现并修复的缺陷：

1. **`POST /api/ladder/start-game` 没有重置 `session._recorded`。** 一个 session 上的
   第二局永远不会落库，因此永远不会结算——而「连胜 3 局」这条旅程天生就是同一个
   session 上的连续三局，也就是说 S1 之后升降级实际上**一局都升不了**。
   `/api/new-game` 和 `/api/game/setup` 都有这个重置，start-game 漏了。
   验收脚本因此刻意把 11 局全打在一个 session 上。

一次读错：中途把 `.MuiDialog-container` 的 `overflow-y: visible` 读成「弹窗不能滚」，
实际 `.MuiDialog-paper` 自带 `overflow-y: auto`（scroll="paper" 默认），量到的
`-101px` 只是 `scrollTop=0` 时按钮在折叠线以下而已。没有这个缺陷，多加的 override 已撤回。
真浏览器几何闸仍然保留（`tests/ladder-settlement-geometry.spec.ts`）：它断言的是
Chromium 算出的 `scrollHeight/clientHeight`、**真实滚轮**之后读回的 `scrollTop`、
以及滚到底后按钮盒相对裁切框的位置；把 paper 改成 `overflow: hidden` 它会变红（已验）。

S3 排最后：它改的是既有人人对弈行为，风险边界与 S1/S2 不重叠，且不阻塞前两片。

### S3 实际验收记录（2026-08-05）

四件事：

1. **game_type 词表收口。** `WebKaTrain.GAME_TYPES` 列全 5 个取值并各写一行含义，
   `SCORING_GAME_TYPES`（禁分析禁悔棋）与 `RANK_MOVING_GAME_TYPES`（会动段位）
   从它派生。`RANK_MOVING_GAME_TYPES` **只有 `ai_ladder_ranked` 一项**——多一项就是
   又造了第二套段位，测试钉死这一条。**没有重命名任何已入库的取值**：kiosk 的
   `ranked` 与 PvP 的 `rated` 保持原样（既有行、报告卡文案、kiosk 判断都读它），
   它们本来就不动段位，收口后这件事在代码里说得出口了。
2. **人人对弈不再动段位。** `record_multiplayer_game` 里的 Elo/净胜更新整段删除，
   `katrain/web/core/ranking.py` 随之删掉（无其他引用）。`rating_history` 表与
   `users.rank/net_wins/elo_points` 三列保留但不再写入；`users.rank` 仅剩一个用途——
   给定级赛开窗做种子。
3. **rated PvP 门槛：`count_completed_rated_games` → `has_completed_placement`。**
   旧门槛数的是 `game_type == "rated"` 的对局，而 AI 对局从来不写这个值，计数永远是 0，
   大厅却把人送去一个改不动它的页面（§1.2 的活死循环）。两个大厅前端同步改掉。
   kiosk 目前还没有升降级 UI，所以它如实说明并**留在原地**，不再把人传送到死路。
4. **`/api/new-game` 不再继承上一局的 game_type。** 之前在打完一局升降级的 session 上
   开一局自由对弈，会继承 `ai_ladder_ranked`——挑一个弱 AI 赢一盘就能推段位。
   `_do_new_game` 和 `/api/new-game` 各自复位，与 `ladder_rung` 的失败关闭规则一致。

真机（本地 PostgreSQL，一次性账号，验完连数据删除）：未定级 → 拒绝且理由是
`PLACEMENT_REQUIRED`；打完 5 局定级赛 → 不再拒绝（**死循环有出口了**）；
一局 rated PvP 胜局后 `rank/net_wins/elo_points/ai_ladder_rung/ai_ladder_net_wins`
五个值全部不变、账本不增行、对局照常入库；同一 session 上 `new-game` → `free` +
恢复可分析，之后那局不进账本、段位不动、以 `free` 入库，`session-result` 回
`{"settled": false, "reason": "not_a_ladder_game"}`。

两点限制，如实记下：

- **`/ws/lobby` 这一段没跑通传输层**：本机 uvicorn 没装 WebSocket 库
  （`Unsupported upgrade request`），大厅 socket 在这里根本连不上。验的是
  handler 调用的同一个 `has_completed_placement`，数据来自真 API 打出来的真行。
- 全量测试相对 S1 基线**零新增失败**（前后各跑一次全量对比，唯一差异是一条引擎超时日志）。
  仓库既有的 29 个采集错误（缺 cv2）与 74 条红测试均为存量。

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
