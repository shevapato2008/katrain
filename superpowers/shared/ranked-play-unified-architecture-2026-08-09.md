<!-- 本文件是副本,由 superpowers/shared/sync-shared-doc.sh 生成,请勿直接编辑。
     正本: smartbox-software  分支 main  commit 7d01a2b3ceb8eae30e72cdd624d962a690038276 
     正本 sha256: 64cd60c861f52d8383e005d847688366cf204311d544ea7fef908f0f27ac928a
     改动请改正本,再重新同步。 -->

# 智星盒升降级对弈 · 统一前后端架构（落地层）

> 状态：**v3.1** · 2026-08-09 起草 / 2026-08-10 定稿 · 适用 **围棋 / 国际象棋 / 中国象棋 / 五子棋** 四条 track
> ⚠️ **v3.1 收回了 §15 五子棋第 3 行的一条改法**（详见 **§13-bis**）。它暴露的通则对另外三家同样有效：**本文 §15 给某棋类开药方之前，先查那棋类有没有自己的已批准设计稿**——横向"取交集"会把只有一家有的设计当噪声抹掉。
> 归属：横向规范，不属于任何单一棋类。正本在 smartbox 仓 `superpowers/shared/`，katrain 仓的副本由脚本生成。
> 与前作的关系：`rated-play-common-solution-2026-08-06.md` 是**原则层**（该怎么做），本文是**落地层**（实际做成了什么、差多少、怎么收口）。原则层里被现实推翻的两条，本文 §12 逐条修订。
> ⚠️ **不要在这里写相对链接**：前作在 `main`、国象分支、象棋分支上有，**五子棋分支（本文正本所在处）和 katrain 仓都没有**——本分支落后 main 170 个提交。相对链接在正本和副本上都是死链。这正是 §16 要用生成式分发的原因。
> 评审：已过**三轮** codex 对抗性评审。第一轮（27 条）推翻初稿 7 条事实断言与 6 条设计决定；第二轮对这 27 条判 **14 已改 / 7 改错 / 6 未改**，另提 15 条新问题——事实错误已逐条核实后改正，结构性缺口在 **§17** 明列而不假装已解决。第三轮判第二轮 15 条为 **3 已改 / 4 未改 / 8 改错**，另提 14 条——**其中 5 条是本文自己内部打架**（改了一处忘了另一处），已全部修平。
> §13 是勘误表，**那批错误说法不得再出现在任何衍生文档里**。

> **关于行号**：四棋类分属两个仓，smartbox 三棋还是同一个仓的三条分支——**同一个文件在不同分支上行号不同**（例：`setup-wizard/app/config.py` 的 `LOBBY_URL` 在五子棋分支是第 80 行，在国象分支是第 92 行）。本文的行号以**五子棋分支 `feat/gomoku-features-2026-07-16`** 与**象棋分支的 `vendor/katrain` pin（`73ba868f`）**为准；跨分支引用时以符号名为准，不要死抠行号。

**这份规范解决的问题**：四棋类的升降级对弈各写各的——两个仓、两个服务、四套后端、四种评级数学、四套表名、四种未登录处理。用户在四个棋类里看到的是同一个功能，代码里却没有任何一条线是共享的。

**约定的边界**：统一 **wire contract、身份、幂等、时间、生命周期语义、未登录处理**。**不统一**各棋类的评级算法（四家四种，是有意的）、前端物理目录名、盒端本地物理表名——理由见 §8.4。

---

## §1 真实拓扑（先纠正一个普遍误解）

不是「两套实现并存在一个 lobby-platform 里」。是**两个仓、两个服务、四套后端**：

| 棋类 | 云端服务 | 仓 | 模块 | 云端表 |
|---|---|---|---|---|
| 五子棋 | lobby-platform | smartbox | `lobby_api/ranked/`（17 模块） | `ranked_profiles` `ranked_reservations` `ranked_ledger` `ranked_devices` |
| 国际象棋 | lobby-platform | smartbox | `lobby_api/rated_*.py`（6 模块） | `rating_profiles` `rated_catalogs` `rated_reservations` `rated_ledgers` |
| **中国象棋** | **katrain web** | **katrain** | `katrain/web/api/v1/endpoints/xiangqi_ranked.py` | `xiangqi_rating_profiles` `xiangqi_ranked_reservations` `xiangqi_ranked_ledger` `xiangqi_ranked_capability_jtis` |
| 围棋 | katrain web | katrain | `.../endpoints/ai_ladder.py` | `ai_ladder_profiles` `ai_ladder_pending_games` `ai_ladder_game_ledger` |

**象棋的升降级后端跑在围棋的服务里。** 所以 `XIANGQI_RANKED_CLOUD_BASE_URL` 默认取 `BOX_IDENTITY_REMOTE_URL`（不是 `LOBBY_URL`）是合理的，不是配错。共享算分包在 `packages/smartbox-xiangqi-ranked/`，也在 katrain 仓里。

> ⚠️ **各分支的 `vendor/katrain` 子模块 pin 在不同 commit**：象棋分支是 `73ba868f`（有 `xiangqi_ranked.py`），五子棋分支是 `1becaa89`（只有 `ai_ladder.py`）。「云端跑的是什么」取决于你看的是哪个分支的 pin——查证时必须说明用的哪个。

**Fan 的拍板（2026-08-09）**：升降级与「人人对战大厅」是**平级**功能，不放在 `lobby_api` 下面；四棋类收敛到**一套实现**，象棋与围棋的升降级跨仓搬进 smartbox 平台。

---

## §2 目标结构

依赖方向**部分**支持这次拆分，但「零直接 import 那三个文件」不等于已解耦——这点初稿说过头了：

- 成立的部分：两套后端对 `lobby.py` / `ws.py` / `bot.py` **零引用**（grep 零命中，正对照是它们各自 12 条以上的其他 import）。它们要的从来不是「大厅」，是账号身份 + 持久层。
- 不成立的部分：国象还直接依赖 `config` / `user_repo` / `rated_catalog` / `rated_glicko2`；更关键的是**运行时与 reaper / LobbyManager / ChessAdapter / BotRunner 共用同一个 lifespan**（`main.py:25` 起）。启动/停止的所有权没有拆开。

**所以顺序是：先在原 distribution 内把 account / DB 事务 / catalog / clock / lifecycle 做成 port 并给 startup-shutdown 所有权写测试，边界稳定之后再搬包。** 不要把「零引用」当成已解耦的证据就直接搬。

```
smartbox-platform/api/
  platform_core/    account · auth · db · config · migrations     ← 唯一共享地基
  lobby_api/        人人对战大厅（将来）                            ← 平级
  ranked_api/                                                      ← 平级
    envelope/       预约 · 账本 · outbox · 幂等 · 对账（棋类无关）
    adapters/
      GameRulesAdapter        冻结规则 · 规范着法 · 局面 hash · 合法性重放 · 终局判定 · 时钟证据
      RatingAlgorithmAdapter  Glicko-2 / Elo / 离散阶梯
      CatalogAdapter          候选 · 冻结 · 认证 · 分批激活 · 退役
```

`ranked_api` **不得** import `lobby_api`，反之亦然；共享只能走 `platform_core`。需要一条依赖测试把这条钉住，否则半年后又会长回去。

### `ranked` 是命名空间，不是「让五子棋实现做幸存者」

初稿写的是「`ranked_*` 做幸存者，其余迁过来」，**这条被评审推翻，理由成立**：

- 五子棋的 wire contract 把颜色锁成 `black|white`、结果锁成 `black_win|white_win`（`api_models.py:31`）、棋盘锁成 15 路（`:119`），规则重放直接判五连（`rule_replay.py`）。
- `ranked_profiles` 要求 Glicko 三元组与黑白定级计数**非空**（迁移 `20260806_01:184`）——**围棋根本无法诚实落表**，它只有 `rung / placement_lo / placement_hi / net_score`。
- 象棋是红黑方 + 四种时控。

所以：**通用的是信封，不是某一家的实现**。档案按算法族分表，禁止给围棋填假的 Glicko 值：

```
ranked_glicko_profiles   五子棋 · 国象
ranked_elo_profiles      象棋
ranked_ladder_profiles   围棋
```

共有的只有信封列：`profile_version` · `settlement_seq` · `rated_games` · `updated_at`。

---

## §3 四家四种评级数学（这是有意保留的例外）

| 棋类 | 模型 | 初始分 | 不确定度 | 产品档位 |
|---|---|---|---|---|
| 五子棋 | Glicko-2 | 1500 | RD + volatility | `confidence_state` |
| 国际象棋 | Glicko-2 | 1500 | RD + volatility | 8 档中文等级 |
| **中国象棋** | **经典 Elo** K=40→20（20 局转稳） | **1000** | **无** | CXA 九档称号纯阈值 |
| **围棋** | **离散 41 档 + 净胜分 ±3** | 无分数 | 无 | rung 即段位 |

象棋证据 `smartbox_xiangqi_ranked/scoring.py`：`SCORING_CONTRACT_VERSION=4`、`INITIAL_RATING=1000`、`K_PROVISIONAL=40`/`K_STABLE=20`、`PROVISIONAL_GAMES=20`、`RATING_FLOOR=100`、九档 `ANCHORS` 1010–2900、`FARM_CEIL = anchor + 130`（防刷上限，合原则层 §5.4）、`TIERS` 九档纯阈值映射。表 `xiangqi_rating_profiles` **没有 rd / volatility 列**。

**Fan 拍板：算法各自例外，文档只统一契约不统一算法。** 前作 §5.1「采用 Glicko-2」四家里只有两家照做，本文按现实修订（§12）。

三条随之而来的硬规则：

1. 每棋类必须冻结自己的 `rating_contract_version`，并在账本里逐行记录。
2. **四种分数互不可比**，任何页面不得并列展示或换算；跨棋类总榜不成立。
3. 算法是 `RatingAlgorithmAdapter` 的实现，不是 `ranked_api` 的核心——加第五种棋不应改动 envelope。

---

## §4 云端表：先分清主键与业务幂等键

初稿把唯一键误写成主键，据此写迁移会产出错误 DDL。正确的是：

| 表 | PRIMARY KEY | 业务幂等 / 唯一键 |
|---|---|---|
| `ranked_reservations` | `reservation_id` | 账号活动局**条件唯一索引**（按 `account_ref`） |
| `ranked_ledger` | 自增 `id` | `(account_ref, game_type, rating_pool, rated_game_id)` |
| `ranked_catalogs` | 自增 `id` | **`(game_type, rating_pool, catalog_version)`** |
| `ranked_devices` | `device_id` | — |

**`rating_pool` 必须进目录唯一键、当前激活索引、`GET /catalog` 参数和冻结快照。** 初稿把它定义成规则分池却从目录键里漏掉，会串用不同规则的 AI 目录——五子棋的 `free/standard/renju` 强度不可公度，围棋代码也明写 19×19 / 中国规则 / 7.5 贴目 / 无让子不可混用（`ai_ladder.py:35`）。池名由**规则、棋盘、贴目/让子、时控可公度性**推导，**不许统一填 `"default"`**。

> ⚠️ **这里写 `account_ref` 不写 `user_uuid`**：初版两处打架——本节用 `user_uuid` 当业务键，§5 又规定 FK 只能用整数 `users.id`。统一为 **`account_ref` = 内部整数 `users.id`**（库内 FK），业务唯一性由它承担；对外暴露和跨系统对账用 §5 定义的 `account_subject`。**`user_uuid` 这个名字在新表里一律不再出现**——它在现网已经有两种互相冲突的含义（§5），继续用必然接错账号。

其余两条：

- 所有时间列 `DateTime(timezone=True)`。国象现在用 String ISO 字面量（`models_db.py:47,:49` 的 `created_at`/`updated_at`；同文件 `:24`/`:72`/`:116`/`:149` 也是），要改。
- **所有表都必须有 Alembic 迁移。** 见 §11 阻塞项 1。

---

## §5 身份词汇必须先冻结（迁移的前置条件）

这是最容易出事的一处，因为**两边的「user_uuid」不是同一个东西**：

- `users.user_uuid` 是**平台内部随机生成值**（`models_db.py:15`，`default=lambda: str(uuid4())`）
- `users.username` 里存的才是**上游账号 UUID**
- 国象结算用 `filter_by(username=<uuid>)` 反查（`rated_settlement.py:184`，另一处 `:283`），再按 `users.id` 关联
- 五子棋外键直接打在内部 `users.user_uuid` 上

先定义三个词，再谈迁移：

| 词 | 含义 | 用途 |
|---|---|---|
| `account_subject` | 上游不可变账号标识 | 唯一、跨盒、对外；评级归属的唯一依据 |
| 内部行主键 | 整数 `users.id` | 只在库内做 FK |
| 显示名 | `display_name` | 只用于显示，不参与任何判定 |

⚠️ **katrain 那边是三重身份，比 smartbox 还乱**：用户同时有整数 `id`、注册时随机生成的 `uuid` 和唯一 `username`，而 **JWT 的 `sub` 装的是 `username`**；围棋档案按整数 `user_id` 挂，象棋档案却按随机 `users.uuid` 挂。**跨仓合并时这四种键必须先落成一张映射表**，不能假设同名即同物。

**推荐做法：冻结 `(account_issuer, account_subject) → platform_user_id` 映射；库内继续用内部整数 FK，另建不可变唯一的 `account_subject` 列**，并在目标档案表上保留 legacy ID 列供对账，而不是把 `user_id → user_uuid` 硬迁。迁移前必须输出 `rated.user_id → users.id → user_uuid/username` 的完整映射，并检查 orphan、重复、账号合并与重新注册。

---

## §6 接口与鉴权

### §6.1 现状矩阵（由脚本生成，不是手抄）

用 [`ranked-route-matrix.py`](./ranked-route-matrix.py) 重新生成：

```bash
python3 superpowers/shared/ranked-route-matrix.py \
  --chess           /path/to/smartbox-software-chess-features \
  --xiangqi-katrain /path/to/smartbox-software-xiangqi-features/vendor/katrain \
  --go              /path/to/katrain-golaxy-ai-ladder-parity \
  --markdown
```

> 为什么必须生成：初稿手抄成「国象 5 条桥键 + 3 条 Admin」，实际是 **4 + 3**；同一轮还把象棋 phase 数抄成 20（实为 23）。路由和鉴权是本文**唯一会被人照着改代码**的表。

> ⚠️ **鉴权那一列是启发式的，必须人工复核。** 脚本靠形参名/依赖名/字段名的关键词匹配，而语义不在名字里——五子棋 `settle` 的形参叫 `request`、字段叫 `game_credential`，脚本是从函数体猜对的，**答案对但过程不对**。**方法、路径、计数可以照抄；鉴权列当线索用。** 要权威得改成 AST/OpenAPI 解析或显式 auth manifest。
>
> ⚠️ **`--chess` / `--xiangqi-katrain` / `--go` 三个源必填，没有默认值。** 第二轮评审抓到脚本原先把两家绑在同一个 `--katrain` 上——等于用象棋分支的子模块 pin 去论证围棋的路由。实测两边的 `ai_ladder.py` 连行号都不同（围棋仓 156/161/167/341，象棋 pin 155/160/166/340）。

2026-08-09 的结果：**五子棋 5 条 · 国象 7 条 · 象棋 11 条 · 围棋 4 条，合计 27 条。**
源：`gomoku feat/gomoku-features-2026-07-16@b9ca4d27` · `chess feat/chess-features-2026-07-16@c36e19ac`（⚠️ 已过期：2026-08-10 的 banner 提交把它推到了 `490701ba`——**这正说明内嵌 commit 号必然腐烂，以脚本当场打印的为准**） · `xiangqi vendor/katrain develop@73ba868f` · `go feature/golaxy-ai-ladder-parity@ae56472b`（脚本末尾会自动打印这一行，换机器复核时对得上才算数）

| 棋类 | 方法 | 路径 | 鉴权 |
|---|---|---|---|
| 五子棋 | GET | `/api/v1/ranked/profile` | `get_current_user` + `require_ranked_device` |
| 五子棋 | POST | `/api/v1/ranked/reservations` | `get_current_user` + `require_ranked_device` |
| 五子棋 | POST | `/api/v1/ranked/games/{id}/settle` | `require_ranked_device` + body 局级凭据 |
| 五子棋 | POST | `/api/v1/ranked/games/{id}/heartbeat` | 局级凭据 + `require_ranked_device` |
| 五子棋 | POST | `/api/v1/ranked/games/{id}/cancel-no-start` | 局级凭据 + `require_ranked_device` |
| 国象 | POST | `/api/v1/rated/catalogs/candidates` | `X-SmartBox-Catalog-Admin-Key` |
| 国象 | POST | `/api/v1/rated/catalogs/{gt}/{ver}/freeze-calibration` | `X-SmartBox-Catalog-Admin-Key` |
| 国象 | POST | `/api/v1/rated/catalogs/{gt}/{ver}/certify` | `X-SmartBox-Catalog-Admin-Key` |
| 国象 | GET | `/api/v1/rated/catalogs/{gt}/active` | `X-SmartBox-Bridge-Key` |
| 国象 | POST | `/api/v1/rated/profile/bootstrap` | `X-SmartBox-Bridge-Key` |
| 国象 | POST | `/api/v1/rated/reservations` | `X-SmartBox-Bridge-Key` |
| 国象 | POST | `/api/v1/rated/games/{id}/settle` | `X-SmartBox-Bridge-Key` + body 局级凭据 |
| 象棋 | POST | `/api/v1/xiangqi-ranked/previews` | `get_current_user` |
| 象棋 | POST | `/api/v1/xiangqi-ranked/reservations` | `get_current_user` |
| 象棋 | GET | `/api/v1/xiangqi-ranked/reservations/current` | `get_current_user` |
| 象棋 | POST | `/api/v1/xiangqi-ranked/reservations/{id}/capabilities/rotate` | `get_current_user` |
| 象棋 | POST | `/api/v1/xiangqi-ranked/reservations/{id}/heartbeat` | `Authorization` bearer = terminal capability |
| 象棋 | POST | `/api/v1/xiangqi-ranked/reservations/{id}/force-resign` | `get_current_user` |
| 象棋 | POST | `/api/v1/xiangqi-ranked/settlements` | **body `terminal_capability`** |
| 象棋 | GET | `/api/v1/xiangqi-ranked/settlements/{game_id}` | `get_current_user_optional` + `Authorization` |
| 象棋 | POST | `/api/v1/xiangqi-ranked/reconcile` | `get_current_user` |
| 象棋 | GET | `/api/v1/xiangqi-ranked/settlements` | `get_current_user` |
| 象棋 | POST | `/api/v1/xiangqi-ranked/reservations/{id}/void-unmaterialized` | Bridge Key |
| 围棋 | GET | `/api/v1/ai-ladder/catalog` | `get_current_user` |
| 围棋 | GET | `/api/v1/ai-ladder/status` | `get_current_user` |
| 围棋 | POST | `/api/v1/ai-ladder/start` | `get_current_user` |
| 围棋 | POST | `/api/v1/ai-ladder/settlements` | `get_current_user` |

### §6.2 统一鉴权：**必须保留账号主体**

初稿的三层鉴权（网关桥键 + 设备 HMAC + 局级凭据）**删掉了五子棋已有的账号认证层**，那是典型的 confused deputy：持全局 Bridge Key 的调用方在 body 里自报 `user_uuid`，云端照单全收——**国象现在就是这样**（`rated_profile.py:142`）。

三层各管各的，缺一不可：

| 层 | 证明什么 | **不能**证明什么 |
|---|---|---|
| Bridge Key / 网关白名单 | 调用方是可信服务 | body 里的账号属于当前盒端会话 |
| 设备登记 + 设备密钥 HMAC + `generation` | 请求来自这台已登记的盒子 | 当前用户是谁 |
| 账号主体（bearer/JWT，或桥签发的短期签名断言，含 `sub / aud / exp / identity_generation / device_id`） | 账号归属 | — |
| 局级结算凭据 | 有权补交**这一局** | 有权开新局或读档案 |

**`settle` 不挂账号主体是对的，别「修」**：退出登录后后台仍要补交，账号身份由局级凭据 + 设备 HMAC 承担。象棋把凭据放在 body（`terminal_capability`）、五子棋放在 body、国象靠桥键——三种写法，语义一致，统一到**局级凭据 + 设备**这一组。

### §6.3 统一路由集合

**共 14 条**（下面代码块逐条数得出来；不要再写「5 + 6 + 2」那种加法——象棋 11 条与五子棋 5 条只在预约 / 心跳 / 结算三类上重合，说「独有 6」是错的）。象棋的协议面是四家里最全的，**以它为蓝本**：

```
GET  /profile?game_type=&rating_pool=          账号主体 + 设备
GET  /catalog?game_type=&rating_pool=          账号主体
POST /previews                                 账号主体（开局前展示胜负后果，象棋独有，值得推广）
POST /reservations                             账号主体 + 设备
GET  /reservations/current                     账号主体
POST /reservations/{id}/heartbeat              局级凭据 + 设备（须周期更新，见 §11-2/3）
POST /reservations/{id}/capabilities/rotate    账号主体
POST /reservations/{id}/force-resign           账号主体（失联接管，用户确认后）
POST /reservations/{id}/void-unmaterialized    设备
POST /games/{id}/cancel-no-start               局级凭据 + 设备（五子棋已有且盒端在用，初稿漏掉）
POST /settlements                              局级凭据 + 设备
GET  /settlements/{game_id}                    账号主体或局级凭据（取回原回执）
GET  /settlements?after_seq=                   账号主体（账本增量读）
POST /reconcile                                账号主体
```

每条必须写明：允许的前置状态 · 幂等键 · 账号/设备权限 · 竞态结果 · 错误码。

### §6.4 错误信封：四家四种形状，这条必须统一

和物理表名不同，**错误信封是 wire contract 的一部分**——客户端要照着它解析，形状不同就没法写一份通用的错误处理。四家现状：

| 端 | 形状 | 备注 |
|---|---|---|
| 五子棋云端 | `{"detail": {"code": "<snake_case>"}}` | FastAPI 默认包装，**四家里最规整** |
| 五子棋盒端 | `{"error": "<code>"}` | 自定义信封，且把云端 code 原样透传 |
| 国象盒端 | `{"detail": {"error_code": "<code>"}}` | 17 个字面量 + 1 个从云端转发（`rated_game_active`），**共 18 个能到 UI** |
| 国象云端 | `{"detail": "<英文散文>"}` | 如 `"bad bridge key"` / `"catalog version is immutable"`，**只有预约冲突那一处是 dict**——机器不可判别 |
| 象棋云端 | **顶层** `{"code", "message", ...}` | 由 `RankedAPIRoute` 统一改写（"Keep ranked errors top-level without echoing request values or credentials"）——**四家里唯一显式设计过信封的**，且刻意不回显请求值与凭据 |
| 象棋盒端 | `error_code` 族，约 42 个 code | 数量最多，另有云端 code 词汇表 `accepted/confirmed/idempotent_replay/...` |

**统一为 `{"error": {"code": "<snake_case>", "message": "<给人看>", "details": {...}}}`**，全链路（云端 → 盒端 → 前端）同一形状，`code` 是唯一判据、`message` 不参与判定。

两个具体的现存坑，迁移时必须一起清掉：

1. **五子棋 `POST /api/newgame` 对游客返回 `422 {"detail": "定级需要登录"}`**——自定义 handler `_flatten_dict_detail_error` 只展平 **dict** detail，**字符串 detail 原样落回 FastAPI 默认行为**，于是这条绕过了 `{"error": ...}` 信封。前端 `api.ts` 的 `readJson` 拿不出 `ApiError.code`，走不进正常错误分支。
2. **国象云端的散文 detail 无法被客户端判别**——`"catalog_not_certified"` 和 `"catalog version is immutable"` 一个是 code 一个是句子，却在同一个字段里。

### §6.5 「和云端交互方式一致」到底能做到什么程度

Fan 的原始要求是「后端和服务器交互的方式要保持一致」。分三层回答，**两层能完全一致，一层不可能**：

| 层 | 能不能一致 | 内容 |
|---|---|---|
| **拓扑与信任边界** | **能，且必须** | 走谁、几跳、谁持凭据、鉴权层次、错误信封、幂等键、时间表示、退避与唤醒、生命周期语义 |
| **路由集合** | **能，但分两层** | ⚠️ 初版说「完全一致」过头了。改为 **mandatory core + capability-negotiated optional**：先冻结公共状态机与错误语义，可选操作按能力协商。理由：象棋 `void-unmaterialized` 只接受**尚未 materialize** 的预约，五子棋 `cancel-no-start` 要求状态仍是 `authorized`——**前置状态不同，现在合并会丢语义**；象棋 `/previews` 是评级后果预览，接管就绪信息其实在 `reservations/current` 的 `can_force_resign` 上，也不是同一件事 |
| **报文信封** | **能** | `{envelope, game_payload, rating_block}` 三段式：信封列四家完全相同 |
| **报文体本身** | **不可能，也不该** | 五子棋是 15×15 落子 + 五连；象棋是 FEN + 红黑 + 双钟；国象是 UCI 序列；围棋是 rung + 净胜分。评级结果同理：Glicko 三元组 / Elo 标量 / rung。这正是 `GameRulesAdapter` 与 `RatingAlgorithmAdapter` 存在的理由——**硬压成一种就得给围棋填假 Glicko 值**（§2） |

**现状是四种拓扑，这是本次最该收口的一处：**

| 棋类 | 盒子跟谁说话 | 谁持真凭据 | 开局要云端授权吗 |
|---|---|---|---|
| 国象 | 全部经 setup-wizard | wizard vault | 要 |
| 象棋 | 全部经 setup-wizard | wizard `EncryptedCapabilityStore` | 要 |
| 五子棋 | **分裂**：`profile`/`reservations` 经 wizard；`settle`/`heartbeat`/`cancel-no-start` **直连云端** | **盒子自己**（AES-GCM 落盘） | 要 |
| 围棋 | **不问云端**：`AiLadderRankedRepository` 先写本地，`sync_worker` 事后推 | — | **不要** |

**统一到一种：棋类进程 → 盒内常驻 `ranked-coordinator` → 云端。**

第三轮评审指出，初版把 setup-wizard 直接选成长期运行时的凭据所有者，与 §17-1「owning surface 尚未决定」自相矛盾，并给了一个更好的第四种拓扑，**采纳**：

```
棋类进程（gomoku / chess / xiangqi / katrain）
    ↓  本地 IPC / loopback
ranked-coordinator（盒内常驻）
    持有：设备证明 · 账号断言 · capability vault · outbox transport · 盒级 lease（§10.1）
    ↓  唯一出网口
云端 ranked_api
```

`setup-wizard` 退回**只做 UI 与控制面**。**V1 允许把 coordinator 实现嵌在 wizard 进程里**（不必立刻拆 systemd unit），但**契约与存储所有权必须独立**，保留以后抽成独立 daemon 的边界。这样 §10.1 的盒级 lease 也有了名正言顺的归宿——它本来就该和 outbox、凭据在同一个进程里，而不是散在四个棋类各自的库里。

两条理由成立、一条要收窄：

1. **围棋的 local-first 破坏核心不变量。** 「同一账号全球同时只能有一局升降级对弈」是四家共有的设计前提；不问云端就开局，两台盒子可以各自离线各记一局，事后两笔都推上去。这不是风格问题。
   **但要如实计入代价**（第三轮指出初版漏了）：失去离线即时开局 · 开局链路多一个云端 SLO 依赖 · 请求超时后会留下状态不明的预约需要恢复 · 死预约要能接管 · 现存 pending/outbox 要 grandfather 或隔离。如果产品上仍要保留有限离线开局，替代方案是**预签一张「设备绑定 · 独占 · 短期 · 单次消费」的 cloud start grant**，提前发给盒子。
2. **五子棋的分裂拓扑没有收益，只有两套故障模式。** 同一个功能一半经 wizard 一半直连，出问题要查两条链路、两套超时、两套 TLS 配置。
3. ⚠️ **「凭据交给 coordinator 就不影响退出登录后补交」——这条初版说过头了，已收窄。**
   准确说法：**在 capability 未过期、且不需要轮换的前提下**，sessionless 补交成立（象棋 wizard 的 settle 只要 bridge key，不查登录 cookie）。**但三个边界是真的**：capability 默认 **24 小时 TTL**，云端对 `expires_at <= now` 直接判无效；盒端 `_rotate` 在拿不到 owner session 时抛 `401 reauth_required`；logout 本身还会先跑 `_retire_identity` 再清 cookie。
   → 所以迁移五子棋之前，**必须先冻结 `expires_at` / 轮换权限 / logout 后保留期 / GC / 超期死信 / 人工恢复**，并为这些情形写故障测试。这不是「顾虑不成立」，是「顾虑成立但可解，代价是先把凭据生命周期定死」。

> 唯一保留的例外：`settle` 不挂账号主体（§6.2），因为补交要能在退出登录后发生。**这是有意的，别当漏洞去「修」。**

---

## §7 每棋类适配器的强制接口

原则层 §9.2 就要求棋类后端持有时钟、逐步保存可信时间、重启后核对。象棋实际已经存了双边时钟 + 可信 UTC anchor + revision（`db.py:28`）。但初稿只有一个笼统的 `settle`，唯一明确的服务端重放是五子棋的 15×15 五连——那样撑不起另外三家。

`GameRulesAdapter` 必须实现：

```
freeze_rules()        冻结规则快照（规则档/棋盘/贴目/让子/时控），进预约与账本
canonicalize(moves)   规范化着法序列
position_hash()       局面哈希
replay(moves)         合法性重放
board_terminal(frozen_rules, moves)
                      **只判棋盘上的终局**（五连 / 将死 / 困毙 / 和棋）
verify_terminal_event(frozen_rules, terminal_event, clock_evidence, replay_result)
                      判**不产生着法**的终局:认输 · 超时 · 系统故障——各自要有自己的可信证据
verify_clock(evidence) 时钟证据校验
on_restart(state)     重启恢复
```

**前端状态机不能替代这些权威契约。** 客户端自报的 `engine_stalled`（围棋现状 `ai_ladder.py:337`）不可采信——原则层 §13 已写明，围棋没照做。

---

## §8 前端：分层状态模型

四家现在的状态粒度是 **4 / 8 / 23 / 3**：

| | 数量 | 枚举 |
|---|---|---|
| 五子棋 `LadderState` | 4 | `loading` `ready` `guest` `error` |
| 国象 `RatedView.kind` | 8 | `loading` `login_required` `catalog_not_certified` `ready` `pending_sync` `interrupted` `active_here` `unavailable` |
| 象棋 `RankedPhase` | **23** | `idle` `loading` `identity-unavailable` `online-ready` `online-required` `other-device-active` `starting` `stale-preview` `active` `waiting-for-time` `resumed` `saving` `save-failed` `local-saved` `accepted-cloud` `reconciling` `cloud-confirmed` `blocked` `remote-resigned` `system-aborted` `engine-unavailable` `reauth-required` `load-failed` |
| 围棋 `view_state` | **3** | `loading` `error` `ready`。另有 `startBlock`（`not_ready`/`pending_settlement`/`no_opponent`/`rung_not_certified`）——它是 `aiLadderStartBlock(status)` **从 status 算出来的派生 guard，不是第二层状态**，别当状态数加进去 |

初稿想收成一个扁平十态枚举，**被评审推翻**：它把「入口 gate」和「完整对局/结算生命周期」混在一起，无法无损映射象棋那 23 个 phase。改成三层：

```
L1 入口 gate（四棋类完全一致，必须逐字一致）
   signed_out · identity_unavailable · online_required · catalog_unavailable · ready

L2 生命周期（四棋类一致的语义，物理枚举可各自更细）
   reserving · active · settling · pending_sync · sync_conflict · reauth_required

L3 棋类专属
   时钟 / 规则 / 结算子状态（象棋那 23 态里的大部分落在这层）
```

### §8.1 未登录：三条硬规则

这是四家分歧最大、也是最该统一的一处。

1. **`signed_out` 与 `identity_unavailable` 不得合并。** 前者用户能自己解决（去登录），后者不能（身份服务挂了）。文案、图标、CTA 全都不同。
2. **优先用 shell 级 auth guard，而不是每个 feature 各写一个未登录页。** 围棋 Kiosk 已经这么做，是四家里最对的：全部路由套在 `KioskAuthGuard` 下，未认证跳 `/kiosk/login`。已被 guard 保护的路由不必重复实现 `signed_out`。
3. **登录跳转目标由外壳提供，不许各棋类硬编码。** 国象现在硬编码 `http://127.0.0.1:8080/launcher?authmode=login`（`RatingPlayPage.tsx:64`）。

### §8.2 四棋类现状与改法

| 棋类 | 现状 | 改法 |
|---|---|---|
| 国际象棋 | **四家里做得最好**：`login_required` 是一等状态，整页 `rated-gate`，有图标、标题「登录后查看你的棋力」、说明、事实卡、`前往登录` 主键 | 只改一处：登录跳转改由外壳提供，不硬编码 loopback URL |
| 五子棋 | `guest` 是一等状态，但渲染成 `<LoadingView message="登录后才能参加升降级对弈" />`（`LadderScreen.tsx:161`）——**复用了命名错误的静态壳，且没有登录 CTA**。（`LoadingView` 本身只有静态 `<p>`，没有 spinner，所以不是「转圈转不完」，是「看起来像加载中的死胡同」） | 换成 `signed_out` 专用视图，补登录 CTA。可直接照抄国象的 `rated-gate` 结构 |
| 中国象棋 | 入口态**是对的**：`HubScreen.tsx:104` 有「登录后参与」+ aria 文案 + 点击打开登录，`App.ranked.test.tsx:39` 还断言了游客零 ranked 请求。**缺陷窄得多**：`RankedPhase` 23 态里**没有 signed_out**，`identity.kind==="guest"` 落回 `EMPTY_STATE`（即 `idle`，`RankedSession.ts:163`），所以**深链 `play/ranked` 时游客被错映射成 `identity-unavailable`**（`App.tsx:1339`） | 给 `RankedPhase` 加 `signed_out`，深链走它，不要重做 Hub |
| 围棋 | Kiosk 主路径**是对的**（`KioskAuthGuard`）。**Galaxy shell 没有同样的 guard**（`GalaxyApp.tsx:26`），那才是缺口。feature 内只有 401 之后的 `loadErrorUnauthorized`「登录已失效，请重新登录后再试」 | Galaxy shell 补 guard；session-expired 与 signed_out 分成两条文案 |

### §8.3 L1 gate 文案基线（照抄这张表，别各写各的）

只说「要一致」没用——四家会写出四种一致。**国象的 `rated-gate` 文案已经过 Fan 确认并上过画廊，把它提升为四棋类基线**，各家只替换棋类名词。结构固定为：图标 · 副标题 · 徽章 · 标题 · 说明 · 事实卡 · 主按钮 · 次按钮。

| L1 状态 | 标题 | 说明 | 主按钮 / 次按钮 |
|---|---|---|---|
| `signed_out` | 登录后查看你的棋力 | 升降级对弈按账号记录。登录后，棋力分、产品等级和定级进度会在不同盒子之间保持一致。 | 前往登录 / 返回对弈 |
| `identity_unavailable` | 暂时无法确认登录账号 | 身份服务暂时不可用。这不是你的操作问题，**升降级入口已安全关闭**，恢复后自动可用。 | 重新加载 / 去普通对弈 |
| `online_required` | 升降级对弈需要联网 | 开局要向云端申请授权，避免同一账号在两台盒子上重复计分。**已经开始的对局断网也能下完。** | 重新检测 / 去普通对弈 |
| `catalog_unavailable` | AI 棋力标定中 | 你的云端棋力档案已经建立，但 AI 难度目录尚未通过目标盒子的循环赛验证。 | （禁用）升降级暂未开放 / 去普通对弈 |
| `ready` | —（进入正常内容，不是 gate） | | |

三条从这张表里读出来的通则：

1. **每个 gate 都要给出路。** 四条里每一条都有一个「去普通对弈」——没有哪个状态是让用户对着一句话干瞪眼。五子棋现在的 `guest` 连按钮都没有。
2. **说明句必须回答「我的分会怎样」。** 国象的「我们不会用设备本地数据冒充最新棋力，也不会把你的分数重置」是范本——这正是 `诚实原则`：连不上时说连不上，且明说没动你的分。
3. **`signed_out` 与 `identity_unavailable` 的文案不许互抄**（§8.1 规则 1 的落地形式）：前者的主按钮是「前往登录」，后者是「重新加载」。用户能不能自己解决，决定了主按钮是什么。

> 顺带一个国象自己也没做的：它的 `unavailable` 同时承担**网络失败**和**预约冲突**两件事（`conflict` 没有专属屏）。统一后 `sync_conflict` 属于 L2，必须有自己的屏，不能塞回 gate。

### §8.4 不统一的东西

**前端物理目录名**（五子棋 `play/` · 国象 `rated/` · 象棋 `ranked/` · 围棋 `features/aiLadder/`）和**盒端本地物理表名**——这两样属于「看起来统一」：它们不进网络协议、不进数据一致性边界，说不出挡住了哪个运行时缺陷，而改名反而有真实数据风险（象棋 schema 版本不匹配时会直接 DROP 那批表，`db.py:270`）。

> 同理，「象棋盒端 `ranked_ledger` 与五子棋云端 `ranked_ledger` 撞名」初稿列为阻塞项，**是伪缺陷**：两个数据库，SQL 上不可能冲突。统一列义与诊断术语即可。

---

## §9 盒端本地存储：只统一列义，不统一表名

| 语义 | 五子棋 | 国象 | 象棋 | 围棋 |
|---|---|---|---|---|
| 开局意图 | `ranked_start_intents` | — | `ranked_start_intents` | — |
| 活动局耐久 | `ranked_game_sync` | `rated_games` | （在 `games`） | `ai_ladder_pending_games` |
| 本地账本 | `ladder_ledger` ⚠️ | — | `ranked_ledger` | `ai_ladder_game_ledger` |
| 待同步队列 | `ranked_outbox` | `rated_outbox` | `sync_outbox` | `sync_queue` |
| 云端档案缓存 | `ladder_state` ⚠️ | — | `rating_cache` | `ai_ladder_profiles` |
| 走势点（展示用） | — | — | `rating_curve_points` | — |

两处别踩的坑：

- ⚠️ **五子棋的 `ladder_state` / `ladder_ledger` 在云端路径上已经是死代码**，别把它们当成「五子棋的本地账本」照搬。终局走 `RankedStartService.persist_online_terminal`，不再调 `db.settle_ranked_game`；认输路径在 `service.py:596` 提前 return，后面那两处本地账本写入不可达。整个 `gomoku_api/ladder.py` 离散引擎（`_WINDOW_SIZE=5` / `_PROMOTE_THRESHOLD=3` / `_DEMOTE_THRESHOLD=-3`）在云端路径下完全不执行。⚠️ **别说它「就是围棋那套数学」——两者只是共用 ±3 这个阈值思想，窗口语义不同**：五子棋是**最近 5 局滑动窗口**内净分达 ±3；围棋是**自上次升降之后累计**净分达 ±3，不设窗口。搬代码前必须先认清这个差别。`service.py:836-844` 的 docstring 仍在描述旧的「games 终局行 + ladder_ledger + ladder_state 同一事务」，**已与代码矛盾，不要引用**。
- ⚠️ **象棋没有 `rating_state` 表。** 那是被 S6 设计替代掉的旧「设备单例」方案，现在只出现在 `db.py:295` 的 **DROP 列表**里和 `tests/test_ranked_migration.py` 的遗留 fixture 里（`:70` 反而断言它不存在）。象棋现存 5 张 ranked 表，不是 6 张。这条不只是名字问题：象棋的评级权威在云端 `xiangqi_rating_profiles`，盒端 `rating_cache` **只是缓存、不做任何算分**（`RankedStakePanel.tsx:29` 明写 "performs no rating math"，`service.py:485` 是校验云端 `projection_fingerprint` 而不是自己重算）——这一点它比表名看起来更接近国象的「只读云端」。

Outbox 状态枚举四家三套：

```
五子棋 / 国象   pending · inflight · confirmed · conflict          （已经一模一样）
象棋            pending · sending · accepted_cloud · confirmed · blocked   （+ lease_owner/lease_until）
围棋            pending · in_progress · completed · failed
```

**统一的是语义分档，不是物理枚举**。象棋多出来的 `accepted_cloud`（云端已接受但本地尚未吸收回执）是真实且必要的区分，不能为了凑四态砍掉。必须保留的语义：

1. 待发 → 在途 → **云端已接受** → 最终确认
2. 冲突（同 ID 不同 payload hash）与永久拒绝（4xx）分开，都不进普通重试
3. lease（谁在发、发到什么时候）
4. 人工恢复入口

退避现状四家四套，**只有国象带抖动**：

| 棋类 | 退避序列 | 抖动 | 封顶行为 |
|---|---|---|---|
| 国象 | `5·15·30·60·120·300·600·1800` s | **`sha256(rated_game_id)` 派生的确定性 ±20%** | 停在 30 分钟 |
| 五子棋 | `5·15·30·60` s | **无**（`ranked_service.py` 里没有 `random` 导入） | 停在 60 秒，无最大次数、无死信 |
| 象棋 | `5·10·30·60·300` s | 构造参数 `jitter=0.0`，**默认关** | 停在 300 秒 |
| 围棋 | `min(2**retry_count * 10, 300)`，实际只等 **20·40·80·160 s** | 无 | 计数先自增再判 `>= max_retries`（默认 5），**第 5 次直接转 failed，300 秒上限永远够不着**；但 `revive_retryable_failures()` 会在重连时复活网络类失败 |

**统一为国象那套**：`5s→15s→30s→1m→2m→5m→10m→30m` + `sha256(rated_game_id)` 派生的确定性 ±20% 抖动。确定性抖动优于随机抖动——同一局每次算出同一个偏移，可复现、可在事故里对账；同时不同局仍然错开。

> 五子棋「无抖动」不是小事：一片盒子在同一次云端故障中掉线，会**在同一秒集体回来**，恢复瞬间的重试是同步的。

唤醒事件：联网恢复 · 服务启动 · 账号登录 · 进入升降级页 · 用户点「立即重试」 · 云端推送档案版本变化。

---

## §10 初稿漏掉、必须补进来的四块

### §10.1 盒级互斥

云端的条件唯一索引只按**账号**限制。但同一台盒子上四棋类是互斥切换的，`launcher.py:303` 那把锁只序列化 systemd stop/start，**不知道另一个棋类有没有活动局、待结算或未落盘的时钟**。需要 `platform_core`/launcher 持一份**盒级 durable ranked lease**，切应用前查询：活动局必须先恢复、认输，或明确阻止切换。同时定义相机 / LED / 引擎 / renderer / 本地端口的所有权。

### §10.2 目录生命周期与设备握手

候选 → 冻结 → 认证 → **分批激活 → 退役**。预约前必须证明目标设备已装完全匹配的引擎 / 权重 / 规则实现；旧目录要能跑完存量局。需定义 manifest 签名、密钥轮换、最低盒端版本、灰度与回滚。

国象的 `rated_catalogs`（认证状态机 + `manifest_sha256 → evidence_sha256 → catalog_sha256` 证据链）是四家里最强的，**以它为蓝本**；五子棋当前 catalog 还是写在代码里的 development contract（`ranked/catalog.py:64`）。

### §10.3 账号切换 / 退出登录 / 凭据生命周期

三家的**凭据边界画在了不同的地方**，这不是风格差异，是真正相反的设计——统一时必须先选一个：

| 棋类 | 边界在哪 | 盒子里有什么 | 完整度 |
|---|---|---|---|
| 国象 | **setup-wizard**（vault 存真凭据，回包里把 `credential` 换成 `credential_ref` = `rated_game_id`） | 只有一个 ref | 记录只有 `{rated_game_id, credential}`，**没有 owner / 过期 / 删除接口** |
| 五子棋 | **没有边界**——云端签发的 `game_credential` 原样穿过 wizard 落进盒子 | **真凭据**，AES-GCM 加密后存 `ranked_game_sync.credential_ciphertext`（AAD = `rated_game_id`，密钥盒本地） | `ranked_outbox.credential_ref` 有 `CHECK (credential_ref = rated_game_id)`，是自指，不是 vault 句柄 |
| 象棋 | **setup-wizard**（`EncryptedCapabilityStore`），`_public()` 逐字段剥掉 `terminal_capability` / token，JWT 从不过界 | 只有不透明 ref | **四家里唯一完整的**：记录带 `owner_uuid` / `device_id` / `game_id` / `reservation_id` / `allowed_actions` / `jti` / `revoked` / `consumed`；401 触发 `rotate()`（吊销整个预约、换新 ref）；`consume()` 单次使用且**对 `receipt` 豁免**（丢了响应还能取回）；写盘 O_EXCL→fsync→replace，0600 |

**以象棋为蓝本。** 它已经把要补的那几项都做了：账号主体、设备绑定、用途白名单（`allowed_actions` 必须恰好等于 `{settle,resign,system_abort,heartbeat,receipt}`，否则 `capability_binding_mismatch`）、吊销、单次消费、原子落盘。国象要补 owner / 过期 / 删除；五子棋要决定是否把真凭据从盒子里挪出去——**注意这是产品取舍不是纯技术题**：凭据留在盒子里，退出登录后后台仍能独立补交；挪进 wizard 则补交要经过 wizard。

> ⚠️ 命名陷阱：`GOMOKU_RANKED_CREDENTIAL_KEY_PATH`（盒端 AES-GCM 密钥）与 `LOBBY_RANKED_CREDENTIAL_KEY`（云端 HMAC 签名密钥）**名字像、毫无关系**，配错不会报错只会全线签名失败。统一命名时这两个必须分别改成不会混淆的名字。

并写明 logout / switch 时，活动局、outbox、档案缓存、棋谱、UI 各自的边界（原则层 §12 已给规则，落地层要给字段）。

### §10.4 监控 / 赛季 / 隐私

落地层必须给出 metric 名、标签基数、告警阈值、health/readiness 检查、日志脱敏规则，不能只引用原则层一句话。`season_id` 只能进活动账本 / 排行榜，**不得重置或覆盖 canonical profile**。

---

## §11 真实阻塞项

> 判据是「**它现在就会让某个真实用户或真实部署失败**」，不是「设计上不够好」。看起来统一但说不出挡住哪个缺陷的，都归 §8.4 的「不统一」。
> 第三轮评审按这条判据重新分了级——初版有一条不够格、有一条漏了，都已改。

| # | 棋类 | 一句话 | 谁被挡住 |
|---|---|---|---|
| 1 | 国象 | 四张 rated 表在已发布 revision 下不会被创建 | 云端 PG 部署 |
| 2 | 国象 | 没有活动局存活机制，死盒子永久占名额 | 换盒子的用户 |
| 3 | **五子棋** | **前端 `RankSyncStatus` 与盒端实际返回字段对不上** | **每一个有活动局的用户**——见下 |
| 4 | 五子棋 | 云端目录未认证生产，`LOBBY_RANKED_PRODUCTION=1` 拒绝启动 | 正式环境上线 |
| 5 | 五子棋 | 「结束上一局」按钮调一条不存在的路由 | 跨盒子被卡住的用户（**但被 #3 挡在前面，见下**） |
| 6 | 象棋 | 被确定性拒绝的结算进 `blocked` 后盒内零逃逸 | 该账号此后所有升降级对弈 |
| 7 | **围棋** | **不问云端就开局，放弃「同账号全球单局」** | 换盒子 / 双盒子的用户；且事后两笔都会推上去 |

> **降级说明**：初版把「五子棋 9 态预约状态机只实现 5 态」列为阻塞第 3 条。按上面那条判据它**不够格**——它挡住的是「计划与文档会照着不存在的能力排期」，不是真实用户。已降为 🟡，正文仍保留（原 §11-3 段落）。
>
> **#3 与 #5 的先后关系**（第三轮抓到，初版没注意）：盒端 `/api/rank` 实际只发 `{status, pending_count, current_local_game_id}`，**没有前端期望的 `active_session`**，所以真实的 `game_active` 一律先落进 `malformedActive` 分支显示「段位需要核对」——**用户根本走不到那个会 404 的「结束上一局」按钮**。所以 #3 是红、#5 是它后面的依赖项：修好 #3 才会暴露 #5。修的顺序不能反。


**1. 国象四张表在当前已发布 revision 下不会被创建。**
唯一那条 Alembic 迁移 `20260806_01_ranked_foundation.py` 只建 `users` `game_records` `onetimecode` `ranked_*`；`db.py:265` 在 PostgreSQL 上跳过 `create_all` 直接返回；`_verify_postgresql_migration_head()` 只比对 revision **不检查表是否存在**，所以启动闸拦不住。2026-08-09 实查测试环境云端 PG：8 张表，国象四张一张没有。国象唯一的「真联调」harness `run-rated-journey.mjs:85` 写死 `sqlite:///`，CI 的 PG 工作流只跑 `tests/ranked`。
`migrations/env.py:8` 已把国象模型导进 `target_metadata`（第 7 行只是 `Base`），**补一条 revision 就能建**——所以准确说法是「当前发布物不建、且健康检查发现不了」，不是「永远建不出来」。
→ **修法**：补 revision；并给启动闸加一条「必需表存在性」检查。

**2. 国象云端没有活动局存活机制。**
`rated_reservations.status` 实际只出现过 `"active"`；结算时整行 `session.delete()`（`rated_settlement.py:277`）；`heartbeat_at` 建行时写一次、**之后再没更新过**（唯一写入点 `rated_reservation.py:301`）；没有心跳 / 取消 / 接管路由。**一台死掉的盒子会永久占住这个账号全球唯一的名额**，直到那台盒子自己回来调 `forfeit-recovery`。
→ **抄象棋的云端，不是盒端。** ⚠️ 这里我自己先错过一次，记下来免得别人重蹈：象棋那个部分唯一索引 `one_unconfirmed_ranked_game_per_user`（`xiangqi/api/xiangqi_api/db.py:206`）和三个触发器**都在盒端 SQLite 上**，它们保护的是本地账本 / outbox / 缓存，**既不会刷新国象云端的 `heartbeat_at`，也不会释放过期预约**——拿它去治云端死预约是文不对题。

真正能抄的是象棋**云端**那三样（`vendor/katrain/.../core/models_db.py:229` 与 `.../endpoints/xiangqi_ranked.py:216`）：

1. `last_heartbeat_at` **周期刷新**（不是建行时写一次）
2. 预约的**条件唯一约束** + 租约过期计算
3. `force-resign` 路由：takeover preview → 用户确认 → 强制认输/接管事务 → 竞态回执

盒端的索引与触发器是**另一层**完整性保护，值得同时抄，但它解决的是另一个问题。

**3. 五子棋的 9 态预约状态机大部分只是 DB 枚举。**
`conflict_hold` / `dead_letter_hold` / `takeover_eligible_at` 只出现在 model 与迁移里；服务实际只写 `authorized` / `active` / `cancelled_no_start` / `settled` / `system_fault_void`。而所谓心跳只在首次 `authorized→active` 时写时间，**对已经 active 的请求不更新**（`reservation_service.py:152`）。
→ 文档与计划里必须把「DB 允许的状态」与「已实现且过故障测试的状态机」**分两栏列**，不许混为一谈。盒端同理：`ranked_outbox.state='inflight'` 也是声明了从不写入。

**4. 五子棋的云端目录未认证生产，正式环境根本起不来。**
`ranked/catalog.py:70` 是 `certified_for_production=False`，而 `config.py:72-75` 在 `LOBBY_RANKED_PRODUCTION=1` 时会 `raise RuntimeError("ranked catalog is not certified for production")`；同时 `reservation_service.py:72` 对预约返回 503 `ranked_catalog_uncertified`。**五子棋升降级今天不可能在生产模式下运行**——这不是配置疏忽，是那道闸在正确地拦住未标定的目录。要上正式环境，先跑完标定并认证目录（走 §10.2 国象那套证据链），不是去改这个布尔值。

**5. 五子棋「结束上一局」按钮调的路由不存在。**
`LadderScreen` 在 `game_active + another_box` 分支给出「结束上一局」，点下去走 `api.forfeitRankedSession` → `POST /api/rank/sessions/{id}/forfeit`（`api.ts:483-484`）。盒端 `main.py` 的 `/api` router 下只有三条 rank 路由——`GET /rank`、`GET /rank/settlement/{game_id}`、`POST /rank/sync/{local_game_id}`；`"sessions"` 这个词在整个 `main.py` 里出现 **0 次**，云端 `ranked/router.py` 五条里也没有。**这条路径只能 404。** 于是「在另一台盒子上有一局未结束」的用户在这台盒子上没有任何出路。
> 同一屏还有一处更隐蔽的错配：前端 `RankSyncStatus` 的 7 个值里有 4 个（`checking_cloud` / `syncing` / `synced` / `needs_review`）**没有任何后端会产生**，而后端确实会发的 `service_unavailable` 前端类型里又没有；前端还期望 `active_session` / `last_attempt_at` / `next_retry_at`，盒端实际只发 `{status, pending_count, current_local_game_id}`。结果是**真实的 `game_active` 一律落进 `malformedActive` 分支，显示「段位需要核对」**。这类「算好了没人读 / 读的人拿不到」的字段成片出现，是本轮四家共有的病。
>
> ⚠️ **上面是事实，但本文据此给出的改法是错的** —— 那四个值里有三个来自五子棋自己的已批准设计稿，该补的是产生方不是删声明。见 **§13-bis**。修这条时还要一并注意：盒端另有一个 `RankedSettlementView.sync_status`（`Literal["synced","offline_pending"]`）**与 UI 态词表重名而含义不同**，是两条契约，不要合并。

**6. 象棋被确定性拒绝的结算在盒内是死局。**
一旦某次结算被云端确定性拒绝（如 `device_id` 漂移导致绑定不匹配），outbox 进 `blocked`，此后 `/api/ranked/next` 永久 409 `ranked_sync_blocked`，**盒内没有任何逃逸路径**：「立即重试同步」返回 200 但什么都没改变——reconcile 拿到 `missing` → 重置为 pending → 再次被拒 → 回到 blocked。2026-08-09 RK3562 板上验收用变异注入复现过，是**实测不是推理**。补救会碰到算分完整性（等于允许用户自己抹掉一次被拒绝的结算），所以修法要 Fan 拍板，不能由实现者顺手定。

> 另一条不是阻塞但必须写清的现状：**象棋的升降级从未在生产上运行过**。生产 `go.sailorvoyage.top` 自己的 openapi.json 里 193 条路径**没有一条**含 `xiangqi-ranked`（正对照 `/api/v1/auth/login` 在）。板上验收用的是临时起的 KaTrain + PG，事后已完全回退。

---

## §12 对原则层的 supersession 表

⚠️ **这一节先前只改了两条，是不够的。** 第二轮评审指出：前作与本文**同时生效且互相矛盾**——谁拿前作去 review 围棋和象棋，都能「合规地」判它们不合格。逐行查过之后，涉及评级数学的一共是**十处**（第三轮又查出前作 §15 / §18 / §21 三处，初版漏了），全部列在下面。（**只引节号**：2026-08-10 给前作加了 banner，全文行号已整体下移 18 行，写死行号必错。）

**取代范围只限「评级数学」这一个主题。** 前作在身份、幂等、时钟、离线、终局、outbox、防刷、赛季上的条款**一条都不取代**——那些恰恰是本文照单继承并用来判缺陷的依据（见本节末）。

| 前作条款 | 原文要点 | 影响谁 | 本文如何取代 |
|---|---|---|---|
| §1 一句话结论 | 每棋种一份**连续**棋力状态 | 围棋 | 改为「一份**评级状态**」——连续与否由适配器定 |
| §3.1 本方案负责 | 单棋种**连续**棋力 | 围棋 | 同上 |
| §4.3 双层展示 · 第一句 | 棋力分：**连续数值**，唯一真源 | 围棋 | 唯一真源成立，**「连续数值」不成立**：围棋的真源是 rung |
| §4.3 双层展示 · 第三句 | **不使用**独立晋级赛数学、**净胜计数器**或只升不降的成长等级 | 围棋 | **撤销对围棋的适用**。围棋的净胜 ±3 是已批准的评级机制，不是「替代品」。（「只升不降」仍然禁止——围棋是**可降**的，不违反这半条） |
| §5.1 采用 Glicko-2 · 字段清单 | 每个账号**至少**保存 `rating` / `rating_deviation` / `volatility` | 围棋 **+ 象棋** | 改为：**这三个字段属于 Glicko 族适配器**。象棋经典 Elo 无 RD/volatility，围棋无分数——按 §2 分表落库，**禁止填假值凑字段** |
| §17.2 中国象棋 | 复用「连续分唯一真源」 | — | **不取代**。象棋 Elo 本身就是连续分（1000 起，按 `K·(S−E)` 移动），这条它是合规的 |
| §17.3 五子棋 | 可复用 Glicko-2 | — | **不取代**。五子棋照做了 |
| §17.4 围棋 | **不复用**净胜达阈值的离散数学；改用连续 Glicko-2 后再投影段位 | 围棋 | **整条撤销**。围棋段位文化本就离散，且整套 golaxy 对齐标定是按 rung 做的，换算法等于标定重来 |
| §15 通用数据模型 · `rating_profiles` | 字段清单固定 `rating, rd, volatility, rated_games` | 围棋 **+ 象棋** | **限定为 Glicko adapter 的档案形状**。按 §2 分表：`ranked_glicko_profiles` 用这套；`ranked_elo_profiles` 无 rd/volatility；`ranked_ladder_profiles` 是 rung/净胜分。信封列（`profile_version` / `settlement_seq` / `rated_games` / `updated_at`）四家共用 |
| §18.1 验收与故障注入 | 验收项含「**Glicko-2 官方测试向量**」「产品等级对整个**有效分域**单调无缝唯一」 | 围棋 **+ 象棋** | **限定为 Glicko adapter 的验收项**。象棋要的是 Elo 契约 v4 的向量，围棋**根本没有「分域」**，其等价验收是「rung 阶梯保序 + 净胜阈值触发正确」。**其余验收项（目录保序、相邻档门槛、CI、指纹可复查）四家通用，不取代** |
| §21 待冻结参数 | 「Glicko-2 初始 RD、volatility、τ、RD floor/cap 和 rating period」列为**必须冻结**的参数 | 围棋 **+ 象棋** | **限定为 Glicko adapter 的参数**。象棋对应要冻结的是 `K_PROVISIONAL` / `K_STABLE` / `PROVISIONAL_GAMES` / `RATING_FLOOR` / `FARM_CEIL`；围棋是 rung 数、净胜阈值、定级区间。**同节其余参数（产品等级阈值、AI anchor、认证上限、先后手偏置）四家通用，不取代** |
| §22 决策摘要 · 评级算法行 | 评级算法 \| **Glicko-2**，AI 为固定锚 | 围棋 + 象棋 | 改为「评级算法 \| **各棋类适配器自定，逐类冻结并版本化**；AI 为固定锚这半条保留」 |
| §22 决策摘要 · 用户展示行 | 用户展示 \| **连续棋力分** + 由分数纯计算的产品等级 | 围棋 | 改为「用户展示 \| **该棋类的评级状态** + 由它纯计算的产品称号」。「纯函数、不单独存成可漂移资产」这半条保留 |

**一句话概括取代逻辑**：前作把「Glicko-2」当成了通用决定，实际它只是**四家里两家**的选择。本文把它降级为 `RatingAlgorithmAdapter` 的一个实现，**契约统一、算法各自例外**（Fan 2026-08-09 拍板）。

### 前作里**不取代**、且现在仍未被满足的条款

这些是本文用来判缺陷的依据，照单继承：

- **不能离线开新计分局** —— 围棋违反（§15 围棋行）
- **客户端自报引擎故障不可信** —— 围棋违反（`ai_ladder.py:337` 的 `engine_stalled` 是请求体字段）
- **同 ID 不同 payload 必须隔离** —— 围棋在 `sync_worker.py:156-159` 对 409 只打一行日志就 `return`，**与 2xx 分支不同，它连 `_absorb_response(item, resp)` 都不调**：不是「没校验 hash」，是**权威回执整个没读**。于是「云端算出的分」和「盒子以为的分」可以从此长期不一致，而本地看起来一切正常。
- **同账号全球单局** —— 围棋不问云端就开局，等于放弃这条（§6.5）
- **赛季不得覆盖 canonical profile** —— 四家都还没做赛季，先记在这

> 📌 前作**正本身上也要能看见这张表**：它同时存在于 `main`、国象分支、象棋分支，有人会单独打开它。2026-08-10 已在那三处文件顶部加了指向本节的 banner（Fan 拍板）。特别是这几条现在**仍未被满足**，落地层照单继承：不能离线开新计分局（围棋违反）· 客户端自报引擎故障不可信（围棋违反）· 同 ID 不同 payload 必须隔离——围棋在 `sync_worker.py:156-159` 对 409 只打一行日志就 `return`，**与 2xx 分支不同，它连 `_absorb_response(item, resp)` 都不调**：不是「没校验 hash」，是**权威回执整个没读**。于是「云端算出的分」和「盒子以为的分」可以从此长期不一致，而本地看起来一切正常。

---

## §13 勘误表：初稿被推翻的 7 条断言

**这些说法不得再出现在任何衍生文档、计划或提交信息里。**

| 初稿写的 | 实际 |
|---|---|
| 象棋游客态落回 `idle`、零文案 | 入口态是对的（`HubScreen.tsx:104` 有「登录后参与」+ aria + 打开登录）。真实缺陷是**深链 `play/ranked` 时游客被错映射成 `identity-unavailable`** |
| 围棋没有未登录态 | Kiosk 全部路由套在 `KioskAuthGuard` 下。缺口在 **Galaxy shell 没有 guard** |
| 五子棋「永远转不完的样子」 | `LoadingView` 只有静态 `<p>`，没有 spinner / aria-busy。准确说法是**复用了命名错误的静态壳且缺登录 CTA** |
| 国象 5 条桥键 + 3 条 Admin | **4 + 3** |
| 象棋 20 个 phase | **23 个**（`guest`/`unavailable` 属于 identity 联合类型，不属于 `RankedPhase`） |
| 围棋 `max_retries=5` 后永久丢弃 | `revive_retryable_failures()` 会在重连时复活网络类失败。**漏掉的真缺陷是 409 无条件当幂等成功** |
| 两套表都带 `game_type`，所以早已支持多棋类 | 列确实有，但 wire contract 把 `game_type` 写死成 `Literal["chess"]`（`rated_profile.py:20`）/ gomoku+standard（`api_models.py:268`）。准确说法：**键预留了分区列，服务/目录/规则重放/wire contract 全是单棋专用** |

另有一条初稿列为阻塞、实为伪缺陷的：**象棋盒端 `ranked_ledger` 与五子棋云端同名**——两个库，不冲突（见 §8.4）。

## §13-bis 本文 v3 自己开错的一副药（2026-08-10 由五子棋 track 回写）

**错的那句**：§15 五子棋第 3 行原写「以盒端实际返回为准重定契约，**删掉四个没人产生的值**」。

「没人产生」是**事实**（§11-5 注核过，成立）；「所以删掉」是**错的结论**。五子棋有一份本文写作时没读到的上位设计稿 `docs/superpowers/specs/2026-08-06-gomoku-ranked-cloud-sync-design.md`，它的 §14 明列 **13 个** UI 状态：

| 前端有的值 | 设计稿 §14 有吗 | 正确处置 |
|---|---|---|
| `checking_cloud` / `syncing` / `synced` | ✅ 三个都在 | **保留，盒端补上产生方** |
| `needs_review` | ❌ 不在 | **拆开**——它把 `conflict` / `dead_letter` / `credential_revoked` 三态压成了一个 |
| `game_active` | ❌ §14 是**三个** | **拆开**——`game_active_local` / `game_active_remote_healthy` / `game_active_remote_takeover_allowed` |

所以真相与本文的判断相反：**前端是照设计稿实现的（只是两处三压一），落后的是盒端**——盒端 `sync.status` 今天只产生 4 个值（`ready` / `game_active` / `offline_pending` / `service_unavailable`）。照原话删，等于把一份已批准设计删掉一半。

**为什么 `game_active` 尤其不能压**：§14 对两个远端态规定了相反的产品行为——remote healthy「不显示可用的结束按钮」，takeover allowed「显示明确后果的结束操作」。压成一个，前端就无从决定那个按钮该不该出现，**而那个按钮正是 §11-5 那条阻塞的主角**。

**通则（这条比个案重要）**：**横向规范给某棋类开药方之前，先查那棋类有没有自己的上位设计稿。** 本文 §15 是四家横向对比推出来的，四家里只要有一家另有已批准设计，横向"取交集/删差集"这个动作就会把那家的设计当噪声抹掉。四条 track 现存的 track 级设计稿都要先摸一遍，再谈收敛。

> 同源提醒：五子棋 track 的收口计划**初稿照着前端的形状抄，把 `game_active` 三压一又犯了一遍**，自查时才发现。两边都只对着对方看、谁都没回去读设计稿——这才是这条勘误真正的病根。

---

## §14 迁移顺序：expand-contract

测试环境云端 PG 已经在跑真数据（`ranked.sailorvoyage.top`，账本里有真实结算行），所以顺序是安全前提，不是流程洁癖。

1. 备份并记录 schema、行数、账本 hash、部署 SHA、Alembic revision
2. 新增 revision / 列 / 索引，**绝不修改已上线 revision**
3. 新旧 URL、环境变量、import 路径**同时兼容**
4. 回填身份与账本，校验 orphan / 行数 / hash / 序号
5. shadow read，再按棋类 feature flag 切写
6. 等至少一个盒端发布周期 + 旧 outbox 清空，才删旧路由 / 表 / 变量
7. **包名、容器名等纯运维改名放最后**

### ⚠️ `LOBBY_URL` 不能机械改名

它的默认值是 `https://lobby.sailorvoyage.top`（`setup-wizard/app/config.py`，五子棋分支第 80 行 / 国象分支第 92 行），而且它**同时**用于调 rated API（`lobby_bridge.py:374`）和**铸造大厅 SSO code**（`:545`）。把所有 `LOBBY_*` 一起改成 `RANKED_*` 会同时改坏真正的大厅 SSO。

> 顺带一条已知债：这个默认域名 `lobby.sailorvoyage.top` **从来不存在**（2026-08-09 查证无 A 记录），是从计划文档抄进配置的。板上靠 systemd drop-in 覆盖成真实域名才能用。

**做法**：同域部署引入 `PLATFORM_BASE_URL`，并暂时回退读 `LOBBY_URL`；真要拆域时再分 `LOBBY_BASE_URL` / `RANKED_BASE_URL`。命名扩散面实测 **88 个文件**，不要一次性动。

---

## §15 逐棋类收口清单

前面各节按**主题**组织；这一节按**棋类**重组同一批结论，供各 track 直接当 backlog 用。每条格式是「现状 → 改法」，**不重复论证，理由回看对应小节**。

标记：🔴 阻塞（现在就会失败） · 🟡 收口（不改就不算统一） · ⚪ 择机（有真实收益但可排后）

### 五子棋

| | 现状 | 改法 | 依据 |
|---|---|---|---|
| 🔴 | 云端目录 `certified_for_production=False`，生产模式拒绝启动 | 跑完标定并按国象证据链认证目录；**不要改这个布尔值** | §11-4 |
| 🔴 | 「结束上一局」调 `POST /api/rank/sessions/{id}/forfeit`，该路由不存在 | 要么实现它，要么在跨盒子分支给真实出路 | §11-5 |
| 🔴 | 前端 `RankSyncStatus` 与盒端实际字段对不上，真实 `game_active` 一律显示「段位需要核对」 | **以 sync-design §14 的 13 个状态为准重定契约，盒端补上产生方**（~~删掉四个没人产生的值~~ —— **这条改法是错的，见 §13-bis**） | §13-bis |
| 🟡 | `guest` 渲染成 `LoadingView`，没有登录 CTA | 换 `signed_out` 专用视图，照抄 §8.3 文案表 | §8.2 §8.3 |
| 🟡 | 退避 `5·15·30·60` 秒，**无抖动**，故障恢复时全网同步重试 | 换成 §9 的八级退避 + 确定性抖动 | §9 |
| 🟡 | 游客开局返回 `422 {"detail": "定级需要登录"}`——字符串 detail 绕过了自定义信封，前端解析不出 code | 换成统一错误信封 | §6.4 |
| 🟡 | 9 态预约状态机只实现 5 态；`inflight` 从不写入（**第三轮按判据从 🔴 降到这里**：它挡住的是排期，不是用户） | 文档分两栏列；未实现的要么实现要么从 DDL 删掉 | §11 降级说明 |
| ⚪ | `ladder_state` / `ladder_ledger` / `ladder.py` 在云端路径下是死代码，docstring 还在描述旧行为 | 删死代码；**至少先改掉矛盾的 docstring** | §9 |
| 🟡 | 盒子里存的是真凭据（AES-GCM），与国象/象棋方向相反 | **§6.5 已经定了**：迁到 `ranked-coordinator` 持有。前置条件是先冻结 capability 的 `expires_at` / 轮换权限 / logout 保留期 / GC / 超期死信 | §6.5 §10.3 |

### 国际象棋

| | 现状 | 改法 | 依据 |
|---|---|---|---|
| 🔴 | 四张 rated 表在已发布 revision 下不会被创建，启动闸发现不了 | 补 revision；给启动闸加「必需表存在性」检查 | §11-1 |
| 🔴 | 无活动局存活机制，死盒子永久占名额 | **抄象棋云端**：周期心跳 `last_heartbeat_at` + 租约过期 + 条件唯一活动预约 + takeover preview/confirm + `force-resign` 事务与竞态回执。⚠️ **不是抄盒端那个部分唯一索引和触发器**——那在 SQLite 上，治不了云端预约（§11-2 详述） | §11-2 |
| 🟡 | 云端错误 detail 是英文散文，机器不可判别 | 换成统一错误信封 | §6.4 |
| 🟡 | 桥键调用方在 body 里自报 `user_uuid`，云端照单全收（confused deputy） | 补账号主体层 | §6.2 |
| 🟡 | 时间列是 String ISO 字面量 | 改 `DateTime(timezone=True)` | §4 |
| 🟡 | 登录跳转硬编码 `http://127.0.0.1:8080/launcher?authmode=login` | 改由外壳提供 | §8.1-3 |
| 🟡 | vault 记录只有 `{rated_game_id, credential}`，无 owner / 过期 / 删除 | 补齐，抄象棋 | §10.3 |
| 🟡 | `unavailable` 同时承担网络失败与预约冲突 | `sync_conflict` 归 L2，给独立屏 | §8.3 注 |
| ⚪ | 唯一「真联调」harness 写死 SQLite | 补一条 PG 的 | §11-1 |
| ✅ | 目录认证状态机 + 三段证据链、确定性抖动、`login_required` 一等状态 | **这三样是四家蓝本，别动**。⚠️ **「8 档」本身不是蓝本**——档数与阈值必须按各棋类标定产出（象棋 9 档 CXA 称号、围棋 41 rung），可复用的是**认证机制**不是那张表 | §10.2 §8.3 §9 |

### 中国象棋

| | 现状 | 改法 | 依据 |
|---|---|---|---|
| 🔴 | 被确定性拒绝的结算进 `blocked` 后盒内零逃逸，此后该账号永久 409 | **需 Fan 拍板**（补救会碰算分完整性） | §11-6 |
| 🟡 | `RankedPhase` 23 态里没有 `signed_out`，深链 `play/ranked` 游客被错映射成 `identity-unavailable` | 加 `signed_out`，深链走它；**Hub 入口已经是对的，别重做** | §8.2 |
| — | ~~前端在入口处合并了 401/503~~ **不实，已删**：`HubScreen.tsx:104` 本来就区分游客与身份不可用。唯一缺陷是深链，已在上一行 | — |
| 🟡 | 抖动构造参数默认 `0.0` | 打开，并换成确定性抖动 | §9 |
| ⚪ | 从未在生产运行过（生产 openapi 193 条路径零命中） | 上线前按 §14 顺序走 | §11 注 |
| ✅ | 协议面最全（11 条，含 `/reconcile`、账本读、capability 轮换、`force-resign`）；不变量同时下沉到**云端**条件唯一 + **盒端**部分唯一索引与触发器；算分包盒云共用 | **§6.3 路由集合与 §10.3 凭据都以它为蓝本** | §6.3 §10.3 §11-2 |
| 🟡 | capability 生命周期**是四家最完整的，但不是完整的**：解码不校验 `exp` 之外的保留期，持久记录无 `expires_at` / 删除接口 / GC | 补齐后才能当作四家蓝本推广 | §17-3 |

### 围棋

| | 现状 | 改法 | 依据 |
|---|---|---|---|
| 🟡 | Galaxy shell 没有 auth guard | 补 guard（**Kiosk 那条已经是四家最对的，别动**） | §8.2 |
| 🔴 | HTTP 409 直接 `return`，**连 `_absorb_response` 都不调**——权威回执被整个丢掉，云端算的分与盒子显示的分从此长期不一致 | 409 也要读回执、比对 payload hash；同 ID 不同 hash 必须隔离 | §12 |
| 🟡 | 客户端自报 `engine_stalled` 被采信 | 服务端判定，见 `GameRulesAdapter` | §7 |
| 🔴 | **本地先落库、事后同步**（**第三轮升红**：只要「同账号全球单局」还是硬不变量，这就是现在就会出错的功能，不是收口项）：`AiLadderRankedRepository` 直接写盒内 `ai_ladder_pending_games` / `game_ledger` / `profiles`，开局链路上没有云端授权步骤，云端只在 `sync_worker` 事后推送时才介入 | 开新计分局必须先拿云端授权（其余三家都是这样），否则同一账号两台盒子各自离线各记一局 | §12 |
| 🟡 | session-expired 与 signed_out 共用一条文案 | 拆成两条 | §8.2 |
| ✅ | `KioskAuthGuard` 全路由保护 | **§8.1 规则 2 就是从这儿提炼的** | §8.1 |
| — | 离散 41 档数学 | **已批准的例外，不改** | §3 §12 |

---

## §16 本文的分发

**正本**：smartbox 仓 `superpowers/shared/ranked-play-unified-architecture-2026-08-09.md`（本文件）。
**副本**：katrain 仓 `superpowers/shared/`，**由脚本生成**，头部记录 source repo / commit / hash。

不用手工 `diff` 当长期同步机制——前作已经证伪：同名的 `rated-play-common-solution-2026-08-06.md` 在国象和象棋分支上有，**五子棋分支和 katrain 仓都没有**。各仓 CI 应校验副本与正本一致。

---

## §17 本文尚未闭合的部分（不要当成已经定了）

第二轮评审最一针见血的一条：**「落地层」里有几节其实还停在「需定义 / 必须给出」，那是原则层的写法，不是落地层。** 与其混在正文里读着像已经定了，不如在这里列清楚。

**但第三轮又指出：初版把两类东西混成了一类，还一律禁止实现——把现在其实就能定的也推走了。** 所以分两栏：

| | 判据 | 处置 |
|---|---|---|
| **A 类·现在就能冻结** | 材料已经齐了（源码 + 本文已有的目标设计），缺的只是把它写下来 | **不许再拖**。写不出来是文档欠债，不是外部依赖 |
| **B 类·需要决策或实测** | 缺的是**具体数值或人的拍板**（TTL、保留期、SLO 阈值、信任根、灰度比例） | 拿到之前不得作为实现依据 |

**A 类（现在就能定，材料都在手上）**：canonical writer 迁移算法（本文 §14 补充里其实已经写到了水位线与退役条件）· 完整 supersession（**已闭合**，见下表第 6 项）· 现状/目标两张鉴权矩阵（源码齐全）· L1/L2/L3 逐态映射与禁止组合（象棋 23 态、围棋 3+4 都已枚举）· 各表的**结构性字段**（哪些列存在、什么语义）。

**B 类（下表其余各项）**：capability `expires_at` 与保留期 · 监控阈值 · manifest 签名的信任根 · 灰度比例 · 盒级 lease 的过期时长。

| # | 缺什么 | 现在写到哪一步 | 谁该定 |
|---|---|---|---|
| 1 | **盒级互斥的 owning surface 与表结构** | §10.1 只说「需要一份 durable ranked lease」。而且目标树把 `platform_core` 画在**云端** `smartbox-platform/api` 下，盒级租约却挂在它名下——**位置本身就是错的**，应归盒内的 `ranked-coordinator` / setup-wizard | 需给出：本地持久表、owner、generation、expiry、切应用事务 |
| 2 | **目录 manifest / attestation 的 schema** | §10.2 列了「候选→冻结→认证→激活→退役」和「需定义签名、轮换、灰度、回滚」，但没有字段 | 抄国象证据链后补齐 |
| 3 | **凭据生命周期的具体字段** | §10.3 给了三家对比和「抄象棋」，但没写 `issued_at` / `expires_at` / `retention_until` 与 GC 触发条件。⚠️ 并且**象棋那套也不是完美的**：解码时**不校验 `exp`**，持久记录没有过期与删除——「四家里唯一完整」这个说法要收窄成「四家里最完整」 | 需给出字段表 + logout/switch 逐类处置表 |
| 4 | **监控的 metric 名 / 标签 / 阈值** | §10.4 只写「必须给出」，正文一个也没给 | 需给出清单 |
| 5 | **expand-contract 的数据库细节** | §14 的第 2 步只写「加索引」，没有 `CREATE INDEX CONCURRENTLY`、nullable-expand、回填后 validate；第 4 步是一次性回填，没有 watermark / 变更日志追尾；第 5 步切写没有写入栅栏或单写权威。**旧固件 + 旧 outbox 在切换后仍能打旧服务，会形成双账本** | 见下方补充 |
| 6 | ~~原则层的完整 supersession~~ **已闭合** | 2026-08-10 §12 已扩成完整 supersession 表（十处），前作三份正本也已加 banner 并提交（国象 `490701ba` · 象棋 `c5b7259d` · main 走分支 `a68556ab`）。**此条不再是缺口** | — |
| 7 | **鉴权矩阵要拆「现状 / 目标」两张** | §6.1 是现状，§6.2/§6.3 是目标，混在一节里读者会当成同一件事。且现状描述里「三种写法语义一致」说过头了——国象 settle 没有已登记设备 generation，五子棋 heartbeat 凭据在 header 而 settle 在 body | 拆表 |
| 8 | **L1/L2/L3 的逐态映射** | §8 给了三层，但没给象棋 23 态、围棋 3 view_state + 4 startBlock 的**逐行映射与禁止组合**。评审建议改成正交状态向量 `gate × reservation × sync × gameplay` + 纯派生的展示态 | 需附映射表 |

### 关于第 5 条，先记下已知的三个危险动作

线上测试环境 PG 里有真实结算行，所以这三条不是洁癖：

1. **加索引必须 `CREATE INDEX CONCURRENTLY`**，加列先 nullable、回填后再 validate 约束；直接加会锁表。
2. **回填要有水位线 / 变更日志追尾**，一次性快照回填期间新写入会漏。
3. **切写要么有写入栅栏、要么旧 URL 代理到同一个 canonical writer——不要新旧双写。** 双写在两边都活着的窗口里必然分叉。退役旧路由的条件应是「最低固件覆盖率 + 零旧流量窗口 + outbox 不再新增」，不是「等一个发布周期」。
4. 建全局条件唯一索引**之前**，先枚举并处置跨棋类同时活动的存量局，否则建索引本身就会失败。

### 关于「实查」类事实的取证等级

本文有几条是**外部观察**，仓库里没有随文归档的证据包：云端 PG 实查 8 张表 · RK3562 变异注入复现 `blocked` 死局 · 生产 openapi 193 条路径零命中 · `lobby.sailorvoyage.top` 无 A 记录。它们来自当时的真实操作，但**读者无法从本仓复现**。引用时请注明「外部观察」，不要写成可由代码推出的结论；后续应补一个只读 evidence appendix，逐项记 `checked_at` / 环境标识 / 部署 SHA / Alembic revision / 命令 / 脱敏输出 / 文件哈希。

---

## 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v3.1 | 2026-08-10 | **由下游 track 回写的第一条勘误。** 新增 §13-bis：收回 §15 五子棋第 3 行「删掉四个没人产生的值」——那四个里有三个出自五子棋自己的已批准设计稿 `2026-08-06-gomoku-ranked-cloud-sync-design.md` §14（13 个 UI 态），该补产生方而不是删声明；同时查出前端把 `game_active` 三压一，而 §14 的 remote-healthy 与 remote-takeover-allowed 产品行为相反，压掉就无从决定「结束上一局」按钮该不该出现——**正是 §11-5 那条阻塞的主角**。§11-5 注与 §15 表格各加一条指回 §13-bis。**通则**：§15 给某棋类开药方前先查那棋类有没有上位设计稿。另记一处易混：盒端 `RankedSettlementView.sync_status` 与 UI 态词表重名而含义不同，是两条契约 |
| v3 | 2026-08-10 | 过第三轮评审。修 5 处**内部自相矛盾**（§15 仍让国象抄盒端索引而 §11 已否定它；§15 把游客响应写回裸字符串；§4 用 `user_uuid` 而 §5 要整数 FK；§17-6 声称 §12 只改两条；头部 v1 / 变更记录 v2）；**§6.5 采纳第四种拓扑**（棋类进程 → 盒内 `ranked-coordinator` → 云端，wizard 退回只做 UI）；**收窄「象棋已证明退出登录后照样补交」**（24h TTL、轮换要 owner session、logout 先退休身份）；§11 重新分级（前端契约错配升红、9 态降黄、围棋 local-first 升红）；§12 补前作 §15/§18/§21；§17 拆成「现在能冻结 / 需决策实测」两类；脚本三源必填 + provenance 带完整 commit 与 dirty + 明示鉴权列是启发式 |
| v2 | 2026-08-10 | 过第二轮评审。修 12 处事实错误（围棋状态数 3 非 1+4、围棋退避公式、五子棋滑窗≠围棋累计、象棋顶层错误信封、五子棋游客响应形状、§6.3 计数、四处行号）；**推翻我自己前一版加的「国象抄象棋盒端索引」——那是盒端 SQLite，治不了云端死预约**；新增 §6.5（拓扑一致性，回答 Fan 的原问题）、§17（未闭合项）；修脚本三个缺陷（象棋/围棋源混用、header 凭据误报成 body、缺文件仍退 0）；`--check` 增加头部 sha256 校验 |
| v1 | 2026-08-09 | 首版。过 codex 对抗性评审一轮（27 条），推翻初稿 7 条事实断言与 6 条设计决定：`ranked_*` 不再做「幸存者实现」而是命名空间 + 适配器；档案按算法族分表；`rating_pool` 进目录键；保留账号主体层；前端改分层状态模型；不统一物理目录名与本地表名；补盒级互斥、目录生命周期、凭据生命周期、监控四块 |
