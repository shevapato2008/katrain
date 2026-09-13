# P1：身份主体换轨（JWT sub → users.uuid + token_epoch）

> 2026-09-13 · 状态：待评审 · 分支基线 `feature/phone-login` @ `04a80f4b`
> 这是身份改造四片里的第一片。P2 公开号 / P3 手机号注册与昵称去唯一 / P4 盒端，各自另立 spec。

## 1. 要解决的两件事

**(a) 鉴权主体是个显示名。** access/refresh token 的 `sub` 装的是 `users.username` ——
用户自选、可为中文、P3 之后还会变成可改且不唯一。跨四条 track 的身份冻结件
`superpowers/shared/identity-vocabulary-freeze-2026-08-10.md` §5 早已点名这条：

> **现状用「只用于显示、不参与任何判定」的那个值，当唯一鉴权主体。**

**(b) 改密码踢不掉任何已签发的凭据，最长 90 天。** `/auth/refresh`
（`katrain/web/api/v1/endpoints/auth.py:381-403`）只验签名 + 「这个 username 还存在」，
不看密码改没改；`REFRESH_TOKEN_EXPIRE_DAYS = 90`（`katrain/web/core/config.py:114`）。
Task 17 已经把这件事**诚实地写在了改密码成功页上**（「最长 90 天内仍可继续使用」）——
它诚实地描述着一个洞。这正是 Sudhodanan & Paverd（USENIX Security '22，arXiv:2205.10174）
五类账号预劫持里的 **Unexpired Session**，也是我们唯一命中的那一类。

### 还有一条今天就悬着

`/auth/phone/login`（`auth.py:97-117`）按**手机号**查行（`get_by_phone`，拿到的整行里就有 `uuid`），
却用该行的 **username** 去签 token。身份以用户名字符串传递 ⇒ 签发时选中的行与
`get_user_from_token` 用 `.first()` 解析时选中的行**可以是不同的两行**。
它今天不触发**只因为 `username` 还唯一** —— 也就是说这条本轨道自己新写的端点，
其安全性正依赖着 P3 计划要删掉的那个约束。P1 必须把它一起改掉。

## 2. 为什么是现在

冻结件 §6-2 推迟这件事的**唯一**理由是「改成装 uuid 会让所有存量 token 失效」。
项目仍在测试阶段，没有真实用户、没有需要保全的存量 token ⇒ **那个代价现在≈0，且只会越来越贵。**

## 3. 契约状态：可以先写代码，合并前要有转达记录

- 冻结件 §6-2 **明令**「不改 JWT `sub` 的语义」；§8-2 把「sub 是否最终改为装 `account_subject`」
  列为**未决、须决策人拍板**。Fan 已于 2026-09-13 拍板改。
- 但**正本在 `smartbox-software` 仓，四条 track 一律不得编辑**，只能提变更请求；
  而维护它的象棋 track 对其余三家是**只出不进**的
  （见 `superpowers/tracks/golaxy-ai-ladder-parity/identity-p3-handoff-for-fan.md`，
  那里已经积压了 4 条同样悬空的请求）。
- ⇒ **交付物包含一份变更请求草稿，由 Fan 人工转达。合并前置：转达记录存在。**

## 4. 明确不在 P1 范围内

| 不做 | 归属 |
|---|---|
| 删 `users.username` 的唯一索引 | P3 |
| 新增数字公开号 | P2 |
| 改任何 wire 字段（`/box-sso/bootstrap` 仍收 `username`） | P4 |
| 改登录标识（仍是 username + password） | P3 |
| 盒端 UI、kiosk 登录页 | P4 |
| `_get_or_create_shadow_user` 的去重键（P1 里 username 仍唯一，照旧安全） | P3/P4 |

**这条边界让 P1 成为零跨仓改动**：JWT 由 katrain 自己铸造、自己消费
（全仓 `jwt.decode` 只有 2 处，均在 `endpoints/auth.py`），wire 契约一个字节不动。

## 5. 数据模型

`katrain/web/core/models_db.py` 的 `User` 新增一列：

```python
token_epoch = Column(Integer, nullable=False, default=0, server_default="0")
```

**迁移安全性已核**：`migrations._default_clause`（`migrations.py:351-372`）对「整数 + 标量默认」
返回 `"0"` ⇒ 拼出 `ALTER TABLE "users" ADD COLUMN "token_epoch" INTEGER DEFAULT 0`，
SQLite 与 PostgreSQL 都过。

⚠️ **一处已知分叉，必须在读取侧兜住**：`add_missing_columns`（`migrations.py:341`）拼的 DDL
**不带 NOT NULL** ⇒ **新建库是 NOT NULL、迁移旧库是 nullable**。所以所有读取一律写成
`(user_dict.get("token_epoch") or 0)`，**不许假设非空**。这一条配一条专门的测试（见 §9 闸 3）。

## 6. Token 形状

```
{"sub": "<users.uuid，32 位小写十六进制>", "epoch": <int>, "exp": ...,
 ["type": "refresh"], ["box_generation": <int>]}
```

`sub` 装 `users.uuid` 而不是 `users.id`：`uuid` 就是冻结件 §2 定义的 `account_subject`
（「上游不可变账号标识，评级归属的唯一依据」），升降级账本 `account_subject` 列
（`models_db.py:281`）已经在用它。用整数行主键会让 token 携带一个冻结件明写
「跨服务不可比」的值。

**7 个铸造点全部改**（2026-09-13 逐行回读确认）：`endpoints/auth.py:115`（phone/login）、
`:299`（box-sso bootstrap）、`:350`/`:351`（board login 的 access/refresh）、
`:364`/`:365`（server login 的 access/refresh）、`:402`（refresh 换发）。

## 7. 解析

`get_user_from_token`（`endpoints/auth.py:189-208`）改成：

1. `jwt.decode(...)`
2. `subject = payload.get("sub")`；为空 → 401
3. `user_dict = repo.get_user_by_uuid(subject)`；None → 401
4. `if int(payload.get("epoch", 0)) != (user_dict.get("token_epoch") or 0)` → 401
5. strict box 的 `box_generation` 校验位置与语义不变

`/auth/refresh`（`:381-403`）走同样四步，然后用**当前** epoch 重新签发。

### 仓储

新增 `get_user_by_uuid(uuid: str) -> Optional[Dict]`，两处：
`UserRepository` 抽象基类（`core/auth.py:83` 起）与 `SQLAlchemyUserRepository`（`:139` 起），
照 `get_user_by_id`（`:333`）的形状写。**用 `.one_or_none()` 不用 `.first()`** ——
`uuid` 有唯一索引，`.one_or_none()` 在约束万一失效时会抛而不是静默取一行。

`get_user_by_username` **保留不动**（P1 里它仍被 `_get_or_create_shadow_user`、
`/login`、`/users/follow` 使用，且 username 仍唯一）。

## 8. epoch 在哪 bump

**P1 只有一个 bump 点**：`SQLAlchemyUserRepository.set_password_hash`（`core/auth.py:324-331`），
它是 `create_user` 之外**第二个也是唯一另一个** `hashed_password` 写入点。

必须与密码写入落在**同一条 UPDATE** 里：

```python
session.query(models_db.User).filter_by(id=user_id).update(
    {"hashed_password": hashed, "token_epoch": models_db.User.token_epoch + 1}
)
```

分成两条 UPDATE 在并发下会丢 bump（读-改-写竞争）。用 SQL 表达式 `token_epoch + 1`
而不是先读出来再加，理由同上。

P3 增加手机号换绑时再加第二个 bump 点，不在本片。

## 9. 错误处理

- **所有失败路径返 401，不返 403/500**，与现有 `credentials_exception` 同形。
- **「epoch 不匹配」与「uuid 查不到」必须不可区分**：同一个状态码、同一句 detail。
  判据与 `verify_password` 的 docstring（`core/auth.py:16-21`）同源 ——
  那里明写「500 与 401 可区分，于是任何人都能免费枚举出『哪些账号存在但没有可用口令』」。
- `int(payload.get("epoch", 0))` 要能吃下非整数（伪造的 token 里 epoch 可以是任意 JSON 值）：
  `TypeError`/`ValueError` 一律当 401，不许炸成 500。

## 10. 盒端影响

- `_get_or_create_shadow_user` 的去重键不变（仍是 username），但签 token 时用
  `shadow_user["uuid"]`。影子用户由 `create_user` 建，`uuid` 有 `default=lambda: uuid4().hex`
  ⇒ 每行都有，无需额外处理。
- `/box-sso/bootstrap` 收到的 `body.username` 语义与校验不变 ⇒ **setup-wizard 侧零改动**。
- ⚠️ 盒子用 `credentials.save_refresh_token`（`core/credentials.py:66-78`）持久化的是
  **云端**的 refresh token，文件里只有 `{"refresh_token": ...}` 一个键。云端换轨之后，
  盒子重启时拿旧票去打云端 `/auth/refresh` 会 401 ⇒ **需要重新登录一次**。
  测试阶段可接受，但**必须确认失败路径是「提示重新登录」而不是静默卡死** —— 这一条要实测，
  不能只读代码（`remote_client._refresh_access_token` 的调用方吞异常的方式见
  `endpoints/auth.py:397-400`，那里是 best-effort `except Exception` + 只打 debug 日志）。

## 11. 测试

### 三条新闸（今天一条都没有）

1. **改密码即刻失效**：改密码后，改前签发的 access token 与 refresh token **双双 401**。
   这是 P1 的核心价值，`tests/web_ui/` 里今天没有任何用例守它。
2. **主体形状**：登录后 decode 自己签的 token，`sub` 必须匹配 `^[0-9a-f]{32}$`
   且**不等于**该用户的 username。防止有人日后改回去。
3. **迁移分叉**：构造一行 `token_epoch IS NULL` 的用户（模拟迁移旧库），
   该用户仍能正常鉴权。守 §5 那条 nullable 分叉。

### 批量改造

**实数 15 处 / 5 个文件**（`grep -rn 'create_access_token(\|create_refresh_token(' tests/`，
2026-09-13 实跑）：`test_ai_ladder_api.py` 8 处、`test_board_auth.py` 4 处、
`test_lobby_sso_websocket.py` / `test_tutorial_db_api.py` / `test_box_sso.py` 各 1 处。
**抽一个 `token_for(user_dict)` 助手放进 `tests/web_ui/conftest.py`，集中改一处。**

走 `/auth/login` 拿 token 的夹具（`conftest.py` 的 `phone_auth_client` 等）**不用改** ——
P1 不动登录契约，它们拿到的自然是新形状的 token。

⚠️ **其中 7 处是「攻击者」token**（`{'sub': 'receipt-attacker'}`、`'state-other'` 等），
用来验越权返 403/404。换轨后它们会变成 **401**（token 解不出用户）——
测试照样红，但**红因变了**：断言的东西从「越权被拒」退化成「身份无效」。
修的时候必须用对应 User 行的 uuid 去签，**不许改断言迁就 401** ——
那等于把一批越权闸悄悄退役。

### 变异矩阵（每条必须让指定的闸变红，不多不少）

| 变异 | 期待变红 |
|---|---|
| M1 `get_user_from_token` 去掉 epoch 比较 | 闸 1 的 access 那半 |
| M2 `/auth/refresh` 去掉 epoch 比较 | 闸 1 的 refresh 那半 |
| M3 `set_password_hash` 不 bump epoch | 闸 1 两半同红 |
| M4 铸造点改回 `sub = username` | 闸 2 |
| M5 读取侧去掉 `or 0` | 闸 3 |
| M6 `get_user_by_uuid` 改回 `.first()` 并去掉唯一性依赖 | —— 预期**不红**，如实记录（见下） |

M6 的预期是「不红」：`uuid` 的唯一索引今天真实存在，构造不出重复行，
所以这一格**没有可执行的变异**。按「闸的每条分支都要被执行过一次」的口径，
这属于**休眠闸**，要在 spec 与代码注释里写明「它守的是约束失效那天」，不许硬凑一个假的 M6。

### 基线比对

换轨会让一大片测试同时变红，**真回归极易被淹没**。对策分两步：

1. 只改铸造与解析（不改测试），跑一次全量 pytest，把红的**名字集合**存成一份
   `/tmp/p1-expected-red.txt`，逐条确认每一条的红因都是「token 形状变了」；
2. 改完测试助手之后再跑一次，新的失败集合必须与 `superpowers/tracks/phone-login/test-baseline.txt`
   的既有噪声**完全相等** —— 即第 1 步那份预期红全部归零，且没有多出任何新名字。

两边都 `LC_ALL=C sort` 后再 `comm`（基线文件当初按 `en_US` collation 排的，直接比会吐假新增）。

## 12. 交付顺序

1. `token_epoch` 列 + 迁移 + 闸 3
2. `get_user_by_uuid`（抽象 + 实现）
3. 6 个铸造点 + 2 个解析点换轨 → **此时全量测试大片红，符合预期**，产出预期红清单
4. `token_for()` 助手 + 批量改造 → 预期红归零
5. `set_password_hash` bump + 闸 1 + 闸 2
6. 变异矩阵 M1–M5（M6 如实记录为休眠）
7. 基线比对 + 三个前端构建 + 全量 vitest
8. 变更请求草稿（交 Fan 转达身份 track）

## 13. 风险与对策

| 风险 | 对策 |
|---|---|
| 15 处测试同时红，淹没真回归 | §11 的两步基线法，先存预期红清单 |
| 7 处越权闸的红因从 403/404 变成 401，被「改绿」时静默退役 | §11 点名：必须用对应用户的 uuid 重签，不许改断言 |
| 盒子重启后拿旧票 401、静默卡死 | §10 实测该路径，不只读代码 |
| 合并时冻结件仍未更新 | 合并前置：Fan 的转达记录 |
| `epoch` 被伪造成非整数导致 500 | §9 显式吃 `TypeError`/`ValueError` |
| 有人日后把 `sub` 改回 username | 闸 2 就是为这个建的 |

## 14. 本片不解决、但要记在案的

- `username` 仍是 `/login`、`/users/follow/{username}`、`billing.py:208` 的查找键 ——
  P3 去唯一之前它们都是安全的，去唯一那天必须一起改（P2 的公开号是它们的替代键）。
- `_to_dict`（`core/auth.py:437-452`）与 pydantic `User`（`models.py:181-203`）是两道串联白名单，
  P1 **不**把 `uuid` / `token_epoch` 暴露给前端（前端不需要）。P2 加公开号时要两头一起加，
  只加一头的表现是「前端永远拿不到，且没有任何报错」。
