# 变更请求：结掉冻结件 §8-2（JWT sub 改装 account_subject）

> 提出方：围棋 track（katrain `feature/phone-login`）· 2026-09-13
> 目标文件：`superpowers/shared/identity-vocabulary-freeze-2026-08-10.md`（正本在 smartbox-software 仓）
> **本 track 不得编辑正本，本文是变更请求，需 Fan 人工转达给身份 track。**

## 怎么核这份文件

下面每条断言都带 `文件:行号`，行号一律指 **katrain `feature/phone-login` @ `a29092b1`**，
写入前逐条 `grep -n` 核过。未加仓名前缀的路径都在 katrain 仓内。
凡是本仓答不了的，写在最后「本轮未覆盖」一节，**没有用推理补**。

---

## 一、请求内容（对冻结件正本的四处改动）

1. **§8-2 从「未决」改为「已决：改」。** 决策人 Fan，2026-09-13。
2. **§6-2 第 2 条删除**（「不改 JWT `sub` 的语义」）。它推迟这件事的唯一理由是
   「改成装 uuid 会让所有存量 token 失效」——项目处于测试阶段，无真实存量 token，
   该代价已实际为零，且随上线只会变贵。
3. **§5 改写**：katrain 的 access/refresh token，`sub` 装 `users.uuid`（= `account_subject`），
   并新增 `epoch` claim（`users.token_epoch`）。验证侧按 uuid 反查并比对 epoch。
   §5 原文点名的矛盾（「用只用于显示、不参与任何判定的那个值当唯一鉴权主体」）由此消除。

   改写时请一并更新 §5 里的行号：现行 §5 引的是 `vendor/katrain/...` 那份快照的
   `auth.py:214/:265/:279/:317`（铸造）与 `:112`/`:121`（验证），这些位置今天都已漂走。
   今天的实际位置（`katrain/web/api/v1/endpoints/auth.py`）：
   - 铸造点 **7 处**：`:115`（手机号登录）、`:315`（`/box-sso/bootstrap`）、
     `:369` 与 `:372`（board 模式登录的 access / refresh）、
     `:387` 与 `:388`（server 模式登录的 access / refresh）、`:439`（`/auth/refresh` 换发）。
   - 验证点 **2 处**：`get_user_from_token`（`:189` 起，取 `sub` 在 `:197`，
     反查 `repo.get_user_by_uuid` 在 `:212`，比对 epoch 在 `:219-223`）；
     `/auth/refresh`（`:393` 起，取 `sub` 在 `:406`，反查在 `:420`，比对 epoch 在 `:424-428`）。
   - 反查方法本身：`katrain/web/core/auth.py:104`（抽象）/ `:369`（SQLAlchemy 实现）。

4. **§2 的 `display_name` 行加一句**：katrain `users.username` 在 P1 之后**不再**是鉴权主体；
   它仍唯一（唯一索引未动 —— `katrain/web/core/models_db.py:73`
   `username = Column(String, unique=True, index=True, nullable=False)`），
   P3 会去掉唯一性并使其可改。

---

## 二、本请求提出的唯一接口改动：401 缺一个可区分位

`/auth/refresh` 的五条 401 失败分支**共用同一个异常对象**
（`katrain/web/api/v1/endpoints/auth.py:398-402` 构造 `credentials_exception`，
五处 `raise` 在 `:415`、`:417`、`:422`、`:426`、`:428`，
判定条件分别在 `:414`、`:416`、`:421`、`:425`、`:427`）。
五条分支的状态码（401）、`detail` 串（`"Invalid or expired refresh token"`）、
`WWW-Authenticate` 头**逐字相同**。

其中至少覆盖了两种语义完全不同的情况：

- `:427-428`：**epoch 对不上** —— 账号还在，票因为改密码/换轨作废了，重新登录即可恢复。
- `:421-422`：**按 uuid 反查不到行** —— 这个账号在云端已经没了，重新登录也没用。

⇒ **盒子侧永远反推不出是哪一种。** 要区分只能读云端日志或直接查库，
而盒子既够不着云端日志也够不着云端库。

**请求**：如果身份 track 希望盒子能把这件事对用户说清楚（「请用新密码重新登录」
vs「这个账号已不存在」），需要在 401 响应里加一个可区分位。

具体加什么、加在哪（`detail` 里的结构化 `code`、响应头、还是别的）**由身份 track 定，
本 track 不代拟**。但有一条约束请一并权衡：`/auth/refresh` 的调用者是未经鉴权的，
把「账号不存在」与「票过期」对外区分开，会开出一个账号存在性探测面。
这个取舍归身份 track，本 track 只负责指出两种语义今天是不可分的。

**这是本请求提出的唯一接口改动，其余一律「不请求变更」。**

---

## 三、不请求变更的部分（明确划清）

- **§4 的 32-hex 冻结不动。** 本轮不改 `users.uuid` 的生成方式。
  但要提醒：sub 改装 uuid 把这个值从「只在 bootstrap 出网」提升到**每一次鉴权的热路径**，
  而 `tests/web_ui/test_account_subject_contract.py` 那条 `xfail(strict=True)`
  （marker 在 `:88-98`，用例 `test_schema_rejects_a_dashed_subject` 在 `:99`）正记着
  「铸造侧 `users.uuid` 仍是无长度的 `String`，32 位只由一个 Python default lambda 保证」——
  今天的列定义在 `katrain/web/core/models_db.py:70-71`
  （`uuid = Column(String, unique=True, index=True, default=lambda: uuid_module.uuid4().hex)`），
  既没有长度约束也没有 `nullable=False`。
  该缺口的优先级因此上升，但仍属身份服务 Phase 3，本轮不动。
  （注：冻结件 §2 与 §4 引的 `vendor/katrain/.../models_db.py:52-53` 也已漂到 `:70-71`。）
- **§3 的四标识符表不动。** 数字公开号是第 5 个标识符，属 P2，届时另提。
- **所有 wire 字段不动。** `/box-sso/bootstrap` 仍收 `username`
  （`BoxBootstrapRequest.username`，`katrain/web/api/v1/endpoints/auth.py:178-182`；
  消费点 `:310`）⇒ setup-wizard 侧零改动。

---

## 四、只是告知，不请求变更：盒端实测的两件事

以下由 Task 7 Step 4 用三路只读 fan-out（服务端端点 / `remote_client` 异常处理 /
前端 401 处理）读出、第四路专门找分歧复核。全程只读，未跑测试。
写在这里是**防止身份 track 按错的模型排期**，不构成变更请求。

### 4.1 盒子本地会话不受影响 —— 不要以为盒子会掉登录

这一条推翻了一个常见的想当然。

盒子签给浏览器的 access/refresh 认的是**本地影子用户**的 uuid/epoch，不是云端账号的：
- 签发在 `katrain/web/api/v1/endpoints/auth.py:363-376`
  （`:369-373` 两处 `data={"sub": shadow_user["uuid"], "epoch": shadow_user.get("token_epoch") or 0}`）；
  strict 盒子那一支在 `:315-318`，同样用 `shadow_user["uuid"]`。
- 影子用户由 `_get_or_create_shadow_user`（`:281-286`，其中 `:286` 调 `repo.create_user`）
  建在**本机 SQLite** —— board 模式的 `user_repo` 就是本机那个
  （`katrain/web/server.py:434-436`）。

而 `token_epoch` 全仓唯一写入点是 `katrain/web/core/auth.py:351`
（`SQLAlchemyUserRepository.set_password_hash`，`:329` 起；`:116` 只是抽象声明），
它唯一的非测试调用者是 `/auth/set-password`
（`katrain/web/api/v1/endpoints/auth.py:609`）——
**而该端点在盒子上被 `_guard_phone_endpoint` 挡住**
（`:588` 调 `:44-59`：strict 盒子 403 `phone_disabled_on_device`，
board 非 strict 503 `need_online_phone`）。

⇒ 云端改密码只让**云端**那一行的 epoch +1。
**死的只有盒端 Python 进程手里存着的那张「云端」refresh token**
（登录时写进加密凭据文件 —— `:358-361`；开机读回 —— `katrain/web/server.py:463-472`）。
**屏上不掉登录，顶栏仍是用户名。**

### 4.2 一处静默的数据丢失（非阻塞，本轮不修，已交 P4）

换轨瞬间在飞的同步队列项会被打成 `failed` 终态且**重新登录救不回来**
（401 算 `PermanentError` 不算 transient；重连不复活、手动重试也拒绝），
叠加 `_auth_required` 只活在内存里 ⇒ 盒子每重启一次就再打死一条。

**整段事实与逐条行号已记在 `superpowers/tracks/phone-login/plan.md:9466-9472`**
（收尾清单「换轨瞬间在飞的同步队列项会被永久丢掉（P1 发现，非 P1 引入）」那一条；
注意该节编号 `18` 出现过两次，按行号找不会认错），交 P4，此处不重复。
同节 `:9474-9479` 还记着相邻的一条：盒子的「在线」指示灯走**不带鉴权**的 `/health`，
对鉴权失效是瞎的。

---

## 五、本轮未覆盖（如实写，未用推理补）

- **strict SSO 盒子那一档，本轮没人读到。** 那条路上 `/auth/refresh` 在
  `katrain/web/api/v1/endpoints/auth.py:396-397` 直接 403（`"Direct refresh disabled"`），
  云端票由 launcher 经 `/box-sso/bootstrap` 代持。
  票死了之后 launcher 显示什么、会不会拉起重新登录 —— **launcher 那一层在 smartbox-software 仓，
  本仓答不了**（本仓 `grep` 只命中 `auth.py:33` 一条注释提到 launcher）。
  身份 track 若要完整的盒端影响面，这一格需要由能读那个仓的人补。
- **出厂盒子此刻的运行档**（`KATRAIN_MODE` / strict box SSO 开没开 / 装的是哪个构建包）
  本仓证不了。

---

## 六、实施状态

katrain `feature/phone-login` 上已实现（Task 1–6、6b、7），代码是终态，零新增失败，
**尚未合并、尚未 push**。
合并前置就是本请求被转达并有记录。**没有转达记录不合。**
