# 手机号绑定 B5 后端代码审核

- 日期：2026-11-11。
- 基线：`37c2867b9` 上的 B5 未提交改动。
- 范围：`core/phone_otp.py` 绑定事务与再认证预算、`phone_auth.py` DTO/路由、`remote_client.py` 身份快照转发及对应 API/PG 测试。
- 权威：[实施计划 B5](../plans/2026-11-11-aliyun-phone-otp-and-signup-grant.md)。先规格符合性，再代码质量；审核未修改产品代码。
- 前端已由[独立视觉/前端审核](2026-11-11-phone-bind-visual-code.md)覆盖，本轮没有重复 UI 或截图矩阵；B6 父仓、发布和真实短信不在本报告内。

## 最终结论：Approved（B5 后端）

初审的 **1 个 Important 已修复并通过独立差异复审**，没有剩余 Critical/Important/Minor。冻结后的 B5 核心/API/remote 代码符合当前绑定旅程边界；B6、发布与真实送达验收仍独立执行。

## 初审记录：Changes requested

初审确认 **1 个 Important**，无 Critical；保留如下定位与复现依据。

### I1 — Important：board 将密码再认证失败误认为访问令牌过期，重发绑定提交

- 位置：`katrain/web/core/remote_client.py:309`–`315`、`:435`（初审版本）。
- 触发：已绑定本地身份且持有有效 cloud refresh token；一次 `phone_bind` 提交的 `current_password` 缺失或错误，云端按契约返回 `401 bind_reauth_failed`。
- 实际行为：通用 `_identity_bound_request` 对所有 401 自动刷新并重发同一 POST。一次用户操作在云端执行两次最终再认证，消耗两个独立提交的 `bind_reauth` 预算；三次界面输错就可能耗尽每 15 分钟 5 次的额度。
- 独立复现：纯 `httpx.MockTransport` 返回上述业务 401；观测到 `/phone/bind → /auth/refresh → /phone/bind`。命令 `python3 output/wechat-native/run-tests.py /tmp/test_phone_bind_review_probe.py -q --tb=line` → **1 passed in 0.08s**，表示缺陷复现成功，不表示修复通过。
- 最小修复：`bind_reauth_failed` 属于业务拒绝，直接透传并保留当前 cloud session；不刷新、不重发。真正的认证 401 仍按原身份快照刷新并重试。补 missing/wrong password 单次 POST，以及真实认证过期仍可刷新两类定向回归。

## 规格与质量核对

冻结后已确认：

- HTTP 的 `user_id` 只取当前认证身份；请求禁止额外字段。`current_password` 允许缺失/null/空串进入核心再认证预算，其他类型与超长输入在私有验证边界拒绝。密码只在最终 POST body，未进入 challenge、URL 或持久记录。
- 核心使用独立短事务，以 cloud user id 为键原子预占固定 15 分钟桶；随后才检查当前密码。错误密码、无密码、后续 OTP/数据库失败保留该计次，换手机号/flow/challenge/worker 不产生新用户桶。
- 绑定 mutation 按 phone → challenge → user 锁序执行，重验当前用户资格和密码哈希未变化；检查 active/TTL/purpose/actor/flow/HMAC，错误码计数提交后返回。只有正确 OTP 后查询目标占用，保留 B0–B4 的防枚举修复。
- 正确绑定同一事务消费 OTP、写 private identity 和永久 `bound_existing` claim；不调用赠额或修改余额/UUID/密码/会员。重放仍需当前密码、正确 OTP、active challenge 和未到期；相同归属幂等，不新建 claim/账本。
- `phone_bind` 复用已审核的 `_identity_bound_request`，快照包含 Bearer、generation 和本地绑定用户。跨账户切换后不改用新用户 Bearer，也不返回迟到私有 mask。
- 先前的 `PrivatePhoneRoute` SQL 错误常量 503/no-store 和两个非负计数 CHECK 验证保持；没有扩展迁移框架或共享身份抽象。
- 新 claim 仅在缺失时创建；历史 `signup_grant` claim 的类型、审计 user id 和 grant ref 原样保留。已绑定后删除 identity 的重建登录仍受永久 claim 约束，零赠额。
- 真实 PG 测试对单个用户最后一个再认证额度做并发竞争，只有一个请求能占用；同账号抢两个号码、同号两个 actor 的并发均最多一归属/一 claim，零账本新增。锁与唯一约束共同保护账户和手机号两侧。

## 最终差异复审与验证

I1 已解决：`remote_client.py:310` 仅在绑定路径的结构化 `bind_reauth_failed` 401 上跳过刷新/重发，直接返回原业务拒绝，并保持 active cloud session。缺失和错误密码分别断言仅一个 bind 请求、零 refresh；真正的 `authentication_required` 401 仍使用原 A 身份快照刷新一次并最多重试一次。原有跨 B 身份切换检查不变，未扩大成全局 HTTP 重试改造。

本审核独立执行：

```text
python3 output/wechat-native/run-tests.py tests/web_ui/test_phone_auth_remote.py tests/web_ui/test_phone_bind_pg.py tests/web_ui/test_phone_otp_api_pg.py -q --tb=line -k 'bind_password_refusal or bind_expired_bearer or reauth_limit_is_per_user or bind_failure_rolls_back or one_user_two_phones or one_phone_two_users or existing_user_binds_then'
```

结果：**8 passed, 32 deselected, 3 warnings in 9.55s；PG 未 skip**。覆盖业务 401 修复、真实凭据刷新、跨 phone/flow/worker 的 5 次用户桶、claim 故障整笔回滚但预算保留、两类并发和真实 ASGI→Service→PG 绑定后 OTP 登录旧账号的闭环。warning 是既有 JWT `datetime.utcnow()` 弃用提示。

实现方经 root 交接的冻结结果（已阅读对应测试，不重复全量执行）：

- B5 API/remote/真实 PG HTTP 集成：**44 passed**。
- `test_phone_bind_pg.py + test_phone_signup_pg.py + test_phone_otp_limits_pg.py` 共享 helper 回归：**55 passed in 62.06s，PG 未 skip**；其中 B5 最终 26 例，包括最后再认证额度竞争与历史 claim 保留。
- 本审核对冻结后的相关产品/测试路径执行 `git diff --check`，通过。上述各次测试有重叠，不将计数相加。

所有审核操作仅使用本机隔离 PG 或 MockTransport，没有读取真实秘密、访问现场/业务库、发送短信或连接 RK。审核仅改本文档；首旅程与绑定旅程的后端可以进入后续已授权集成。
