<!-- 本文件是副本,由 superpowers/shared/sync-shared-doc.sh 生成,请勿直接编辑。
     正本: smartbox-software  分支 main  commit 994c0e6d15eb71131ea4c1c0a5e04bf36dcc2319 
     正本 sha256: 08b30a62e13b11caa1e4a4de852a86c5e87a72a89cebcdb1c88fc7ffebab3caf
     改动请改正本,再重新同步。 -->

# 身份词汇冻结（Phase 1 契约）

> 状态：**v1** · 2026-08-10 · 适用 **围棋 / 国际象棋 / 中国象棋 / 五子棋** 四条 track
> 归属：横向契约。正本在 smartbox 仓 `superpowers/shared/`，与
> `ranked-play-unified-architecture-2026-08-09.md` 同级、被其 §5 / §6.1 / §13-ter 引用。
> 生成物：`identity-contract-matrix.py`（路由表），本文（词汇与流向）。

> ⚠️ **本文所有引用都写全路径，不写裸文件名。** 这个仓里 `config.py` 有 **11** 个、
> `auth.py` / `models_db.py` 各 **4** 个、`identity.py` / `schema.py` 各 3–4 个。
> 写 `auth.py:214` 的人知道自己指哪个，读的人不知道——四条 track 会各自解析到不同的文件。
> `vendor/katrain/…` 前缀表示在 katrain 子模块里（pin `73ba868f`）。

## 为什么要有这份东西

统一架构文档 §5 说「身份词汇必须先冻结」，但它冻结的是**一张三行表**
（`account_subject` / 内部行主键 / 显示名），而现实里同一个用户有**四个**标识符、
两个服务各有一套 `/api/v1/auth/*`、同一个叫 `username` 的 wire 字段在两条链路上装的是
**不同的值**。照那张三行表写代码，写不出来。

更要命的是：`ranked-route-matrix.py` 生成的 27 条路由里**零条** auth 路由，
它的 `SOURCES` 也不扫任何 `auth.py`。**要冻结的契约从来没被写下来过。**

本文是那份缺失的契约。**Phase 1 只冻结与记录，不改任何运行时行为。**

---

## §1 现状矩阵（由脚本生成，不是手抄）

```bash
python3 superpowers/shared/identity-contract-matrix.py \
  --katrain <象棋 worktree>/vendor/katrain \
  --lobby   <任一带 lobby-platform 的 worktree> [--markdown]
```

2026-08-10 的结果：**katrain 7 条 · lobby-platform 4 条，合计 11 条。**
源：`katrain develop@73ba868f` · `lobby feat/xiangqi-features-2026-07-16@c9c95e72`

| 服务 | 方法 | 路径 | 鉴权 | 返回凭据 |
|---|---|---|---|---|
| katrain | POST | `/api/v1/auth/box-sso/bootstrap` | 桥键 | `access_token` |
| katrain | POST | `/api/v1/auth/box-sso/clear` | 桥键 | — |
| katrain | POST | `/api/v1/auth/login` | 密码 | `access_token` + `refresh_token` |
| katrain | POST | `/api/v1/auth/refresh` | `refresh_token` | `access_token` |
| katrain | POST | `/api/v1/auth/register` | — | — |
| katrain | GET | `/api/v1/auth/me` | `get_current_user` | — |
| katrain | POST | `/api/v1/auth/logout` | `get_current_user` | `code` |
| lobby-platform | POST | `/api/v1/auth/box-sso/bootstrap` | `X-SmartBox-Bridge-Key` | **`code`** |
| lobby-platform | POST | `/api/v1/auth/box-sso/backend-token` | `X-SmartBox-Bridge-Key` | `access_token` |
| lobby-platform | POST | `/api/v1/auth/dev-login` | —（仅开发） | `access_token` |
| lobby-platform | GET | `/api/v1/auth/me` | `get_current_user` | — |

⚠️ **同名不同物，2 条**：

- `POST /api/v1/auth/box-sso/bootstrap` —— katrain 回 **`access_token`**，lobby 回 **`code`**
- `GET /api/v1/auth/me` —— 两个服务各一份，返回的 User 模型不同

**任何「调 `/api/v1/auth/...`」的说法，不写明是哪个服务，都是不完整的。**

---

## §2 冻结的词汇：**按服务分栏，不存在全局一张表**

| 词 | katrain（身份权威） | lobby-platform（下游消费者） |
|---|---|---|
| `users.id` | 整数行主键。围棋三张升降级表的 FK | 整数行主键。国象四张 rated 表的 FK |
| `users.uuid` | **32 位小写十六进制**，`uuid4().hex`。象棋档案的 FK | 与上游无关的本地随机 `str(uuid4())`（36 位带横杠）。**五子棋云端表的 FK** |
| `users.username` | **用户自选登录名，可为中文**。JWT `sub` 装的就是它 | **装的是 katrain 的 `users.uuid`**（不是用户名） |
| `display_name` | 无此列 | 装的是 katrain 的 `users.username` |

**读法**：`users.uuid` 与 `users.username` 这两个列名在两个服务里**含义互换**。
这不是笔误，是既成事实（见 §3 的流向）。

依据：

- katrain `users.uuid` 铸造 —— `vendor/katrain/katrain/web/core/models_db.py:52-53`
  `uuid = Column(String, unique=True, index=True, default=lambda: uuid_module.uuid4().hex)`
- lobby `users.user_uuid` 本地铸造 —— `lobby-platform/api/lobby_api/models_db.py:15-21`
  `default=lambda: str(uuid4())`
- lobby `users.username` 写入上游 uuid —— `lobby-platform/api/lobby_api/user_repo.py:28`
- katrain 用户名可为中文 —— `setup-wizard/app/routers/auth.py:19` 注释

### 冻结的三个词（对外语汇，取代按列名称呼）

| 词 | 定义 | 现阶段取值 |
|---|---|---|
| `account_subject` | 上游不可变账号标识。评级归属的**唯一**依据 | katrain `users.uuid`，32 位小写十六进制 |
| `account_row_ref` | 某一个服务**库内**的整数行主键 | 各服务各自的 `users.id`，**跨服务不可比** |
| `display_name` | 只用于显示，**不参与任何判定** | katrain `users.username` |

> 原 §5 用「内部行主键」指代 `users.id`，但没说明**每个服务各有一个、互不相等**：
> katrain 读 `KATRAIN_DATABASE_URL`（`vendor/katrain/katrain/web/core/config.py:74`），
> lobby 读 `LOBBY_DATABASE_URL`（`lobby-platform/api/lobby_api/config.py:12`）——两个库。
> 改名为 `account_row_ref` 就是为了让「跨服务不可比」写在名字里。

---

## §3 主体流向：`username` 这个字段名在哪里发生了调包

盒端两条 bootstrap 链路，字段名相同，装的东西不同：

```
setup-wizard ──► katrain  /api/v1/auth/box-sso/bootstrap
  setup-wizard/app/services/box_identity.py:467
      {"username": record["user"].get("username")}
                    └─ 真的是用户名（可为中文）

setup-wizard ──► lobby    /api/v1/auth/box-sso/backend-token
  setup-wizard/app/services/lobby_bridge.py:584
      {"username": user_uuid, "display_name": display_name}
  setup-wizard/app/routers/ranked.py:31-32
      user_uuid    = user.get("uuid")       ── 32 位 hex
      display_name = user.get("username")   ── 用户名
                    └─ 调包发生在这里
```

lobby 收到后写库（`lobby-platform/api/lobby_api/user_repo.py:28`）：
`User(username=<katrain uuid>, display_name=<katrain username>)`。

**结论**：`username` 是一个已经被两种含义占用的 wire 字段名。
Phase 1 **不改**它（见 §6），但任何新代码不得再以「字段叫 username 所以装用户名」为前提。

### 一个用户的四个标识符

| # | 值 | 存放处 | 谁以它为键 |
|---|---|---|---|
| 1 | 整数 `id` | katrain `users.id` | 围棋三张表；**五子棋盒端**（转成字符串） |
| 2 | 32-hex `uuid` | katrain `users.uuid` | 象棋档案；lobby `users.username`；**account_subject** |
| 3 | 用户名 | katrain `users.username` | katrain JWT `sub`；lobby `display_name` |
| 4 | 本地 uuid4 | lobby `users.user_uuid` | 五子棋四张云端表 |

⚠️ **五子棋盒端把 #1（整数）存进了名为 `user_uuid` 的 TEXT 列**：
`gomoku/api/gomoku_api/identity.py:118-120` 取 `user.get("id")`、断言是 `int`、转 `str`，
落进 `gomoku/api/gomoku_api/schema.py:412` 的 `user_uuid TEXT NOT NULL`。
列名与内容不符是既成事实，**Phase 1 不改列名**（该列上有 `RAISE(ABORT)` 不可变触发器，见 §7）。

---

## §4 格式约束：32 位是承重的，不是巧合

- katrain 铸造 —— `vendor/katrain/katrain/web/core/models_db.py:52-53`，`uuid4().hex`
  → **32 位、小写、无横杠**
- lobby 校验 —— `lobby-platform/api/lobby_api/auth.py:57`
  `_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")`，在 `:76`、`:92` 两处强制
- 已有可执行守卫 —— `lobby-platform/api/tests/test_auth.py:198-216`：
  32-hex 通过、36 位带横杠的 `str(uuid4())` 返回 400，注释写明
  「If a future upstream change emits dashed uuids, EVERY bootstrap 400s (feature dead)」

**冻结**：`account_subject` 的格式是 **32 位小写十六进制、无横杠**。
改成规范带横杠 UUID（36 位）会让**所有** bootstrap 400 —— 国象与五子棋一起断。
任何改动 katrain uuid 生成方式的提案，必须同时改 lobby 的正则与上述测试。

⚠️ 另有长度漂移，**Phase 1 只记录不修**：
`lobby-platform/api/lobby_api/rated_profile.py:23` 收 `{1,32}`，而
`lobby-platform/api/lobby_api/rated_reservation.py:30` 与
`lobby-platform/api/lobby_api/rated_settlement.py:32` 收 `{1,64}`。
今天唯一的主体产生器恰好是 32 位，所以三处都过；但 33–64 位的主体会**半通**。

---

## §5 JWT 主体：现状与「显示名不参与判定」相抵触

katrain 的 access token，`sub` 装的是 `username`，四处铸造点：
`vendor/katrain/katrain/web/api/v1/endpoints/auth.py:214`、`:265`、`:279`、`:317`。
验证侧按名反查：同文件 `:112` 取 `payload.get("sub")`，`:121` 调 `repo.get_user_by_username(username)`。

而 `username` 是**用户自选、可为中文**的登录名。也就是说：
**现状用「只用于显示、不参与任何判定」的那个值，当唯一鉴权主体。**

**Phase 1 不改它**（见 §6-2）。它是 §8 的未决项之一。

---

## §6 Phase 1 的边界：expand-contract 的 expand 段

**本阶段改这些**：本文与 `identity-contract-matrix.py`；
统一架构文档 §1 / §4 / §5 / §6.1 / §15 的表述，以及新增的 §13-ter。

**本阶段不改这些**（都属于 contract 段，须整体灰度）：

1. **不重命名任何 wire 字段。** `username` 一旦改名为 `account_subject`，
   已出厂的盒子发旧字段就会被 lobby 的 `extra=forbid` 打成 422 —— 那是双进程同步发布。
2. **不改 JWT `sub` 的语义。** 改成装 uuid 会让所有存量 token 失效。
3. **不改任何列名或 FK。**

---

## §7 交给各 track 的 P3 前置（不是本阶段做，但现在就要认领）

| # | 归属 | 内容 |
|---|---|---|
| 1 | 五子棋 | 三张 ranked 表的 `user_uuid` 上有 `RAISE(ABORT)` 不可变触发器（`gomoku/api/gomoku_api/schema.py:479`、`:491`、`:502`），身份换键须先发触发器 drop/recreate 迁移 |
| 2 | 五子棋 | `get_or_create_user`（`lobby-platform/api/lobby_api/user_repo.py:16`）与 `get_or_create_profile`（`lobby-platform/api/lobby_api/ranked/profile_service.py:35`）在主体不匹配时**静默新建**，结果是评级重置为 placement 且无任何报错。迁移期须加显式主体白名单 |
| 3 | 围棋 | 三张表 FK `users.id`（`vendor/katrain/katrain/web/core/models_db.py:105`、`:133`、`:170`），身份服务的副本必须**保 id 值**，否则三张表全成孤儿 |
| 4 | 围棋 | `users` 行上有围棋域字段 `rank`（`vendor/katrain/katrain/web/core/models_db.py:57`），`vendor/katrain/katrain/web/api/v1/endpoints/ai_ladder.py:118` 读它定 placement 区间。**须裁定 rank 归账号还是归围棋** |
| 5 | 国象 | `rated-chess-bridge.key`（`chess/api/chess_api/config.py:167`）与 `lobby-sso-bridge.key`（`setup-wizard/app/config.py:122`）从未被 provisioning 铸造 —— `provisioning/provision.sh` 只铸 `box-sso-bridge.key` |
| 6 | 国象 | 共享架构文档副本落后一版（blob `b40ea880`，其余三处已是 `1cf147da`），须从 main 拉齐 |

---

## §8 本文没有决定的事（须决策人拍板）

1. **`users.rank` 的归属**（§7-4）——账号属性还是围棋产品状态。
2. **JWT `sub` 是否最终改为装 `account_subject`**（§5）。影响所有存量 token，属产品决策。
3. **是否统一四处主体长度上限**（§4 的 32/32/64/64 漂移）。

---

## 变更记录

- v1 · 2026-08-10 · 首版。由象棋 track 在 Phase 1 产出。
