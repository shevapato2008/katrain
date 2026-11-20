# 手机号 OTP 首旅程后端代码审核

- 日期：2026-11-11。
- 基线：`feature/membership-recharge`，`60817167cebc` 上的未提交改动。
- 类型：独立代码审核；先规格符合性，再代码质量。本轮未修改产品代码。
- 权威：[实施计划](../plans/2026-11-11-aliyun-phone-otp-and-signup-grant.md) 的 B0–B4 与有关 B7 边界。
- 范围：`core/phone.py`、`sms.py`、`phone_otp.py`、SMS 配置、五表模型/迁移及 `init_db` 接缝；`phone_auth.py`、既有 auth 注册/登录接缝、router、`remote_client.py`；对应聚焦测试。
- 排除：B5 最终绑定 mutation/界面、B6 父仓、生产发布与真实短信。未把这些尚未开始的工作作为当前首旅程缺陷。

## 最终结论：Approved（B0–B4 后端首旅程）

初审的 **2 个 Important、1 个 Minor 已全部修复并通过差异复审**，没有剩余 Critical/Important/Minor。本结论不覆盖 B5/B6、生产发布或真实短信送达；初审记录保留于下方，便于核对修复依据。

## 初审记录：Changes requested

发现 **2 个 Important、1 个 Minor**，无 Critical。下述问题均有具体代码路径和隔离复现；修复后只复审相关差异与最可能回归。

## 规格符合性

已确认的实现边界：

- 大陆号码归一化拒绝非 ASCII 数字和其他国家前缀；公开账号使用随机 `u_` handle，手机号留在私有认证表。
- Aliyun 单请求 POST、ACS3 HMAC、六位码、3 秒 HTTP 超时、零重试；配置缺失明确 unavailable，没有生产 mock/固定码回退。发送测试包含官方固定签名向量及日志/异常脱敏断言。
- 发送事务按 phone state → phone/day → IP/hour → global/day 顺序，以唯一键 upsert 和条件 UPDATE 原子预占；网络调用在提交之后。拒收、unknown 和 pending 均不返还预算；仅 sent/unknown 可消费。
- 错误码计数在提交后才抛业务错误；phone 级锁跨重发、flow 和 worker 保留，仅锁到期重置。active challenge、purpose、flow、有效期和 HMAC 均参与验证。
- 正确 OTP 消费、建号、identity、永久 claim 和 `billing.apply_adjustment(..., 5000, 'signup_grant', ref)` 同一事务提交。没有调用自行提交的 `create_user`/`billing.grant` 拆开账户事务。已存在 identity 沿用账号；只有 claim 的重建账号零赠额。
- 五表均进入 `PHONE_AUTH_TABLES <= PROTECTED_TABLES`；命名迁移仅创建同源五表，验证唯一真实列、PG 有效性与 FK 删除规则；不写旧余额、不 drop/rebuild。计数 CHECK 定义验证的初审遗漏见 M1。
- 旧 `/auth/register` 关闭；密码和 refresh 保留 canonical username/type 契约。board 候选 token 先以自己的 Bearer 取 `/me`，再在无 await 的提交接缝进行 generation 检查、shadow/refresh 安装；敏感 status/bind challenge 复用身份快照请求。
- 两云 proxy 信任判断采用 root 已核实的实际部署证据：`FORWARDED_ALLOW_IPS` 不存在、入口 Docker peer 不命中 uvicorn 默认 loopback 信任，应用不取 forwarded header。该部署证据由 root 提供，本审核没有连接现场；未把假设其他部署的宽松代理配置扩展为本轮阻塞。

### I1 — Important：bind challenge 可在零短信、零预算下枚举号码是否已注册

- 位置：`katrain/web/core/phone_otp.py:175`–`183`（初审版本），`request_challenge` 的目标 `PhoneIdentity` 查询。
- 条件：持有合格且尚未绑定手机号的旧账号；提交 `purpose='bind'`，尚未证明目标号码控制权。已占用号码在限额检查前返回 `phone_in_use`；未占用号码继续进入预算逻辑。
- 定向复现：先耗尽全局当日额度，再分别请求一个已有 identity 的假号码和一个未占用假号码，得到 `phone_in_use` 与 `sms_limited`。两个探测都没有调用 sender，也没有追加预算。攻击者可在额度用尽后继续区分任意候选号码。
- 影响：违反 B0“错误不得暴露手机号是否已有账户”。这是当前已提供的 challenge 接口行为，与未实现的 B5 最终绑定无关。
- 最小修复：challenge 阶段不按目标 identity 是否存在返回不同结果；保持相同发送/限流行为。最终绑定须在 OTP 证明号码控制权后判占用，继续依赖唯一约束。若暂不提供绑定旅程，也可统一关闭 bind challenge，而非按目标号码是否存在区别拒绝。

### I2 — Important：OTP 数据库异常可把完整手机号带入未处理异常日志

- 位置：`katrain/web/api/v1/endpoints/phone_auth.py:28`–`47`、`:148`–`159`、`:175`–`178`（初审版本）；`core/phone_otp.py` 的 DB 事务异常向上逃逸。
- 条件：含手机号参数的 SQL 执行出现 DBAPI/约束等数据库错误。现有 endpoint 只转换 `PhoneOtpError`；SQLAlchemy 异常的格式化 traceback 包含 statement 参数及可能含手机号的驱动 DETAIL，`echo=False` 不会消除它。
- 定向复现：仅在随机隔离 PG schema 注入可触发的预算约束失败；`request_challenge` 抛出的真实 `DBAPIError` 格式化 traceback 包含完整假手机号，sender 零调用。正常 ASGI 服务会将这类未处理错误交给服务器异常日志。
- 影响：违反 B2/B3 的异常隐私要求；且用户收到非结构化 500，无法按既定 unavailable 状态处理。
- 最小修复：在私有 OTP HTTP/服务边界捕获 SQLAlchemy 数据库异常，事务正常回滚后转为常量 `503 sms_unavailable` + `Cache-Control: no-store`；不记录原始异常或串联上下文。不要求改造全库日志系统。

### M1 — Minor：同名但错误的预算 CHECK 被 schema 验证接受

- 位置：`katrain/web/core/migrations.py:109`–`111`（初审版本）。
- 条件：保留 `ck_sms_send_bucket_count` 名字，将定义从 `count >= 0` 换成 `count <= 0`。
- 定向复现：`verify_phone_auth_schema` 正常返回，虽然第一笔合法预算 UPDATE 随后会失败。验证只检查 CHECK 名称及 PG convalidated，没有验证计数边界的真实定义。
- 影响：B3 的已有错误 schema fail-closed 目标没有完全覆盖预算/错误计数约束。应用条件 UPDATE 仍避免正常路径超发，因此不升为和身份或赠额竞态相同级别。
- 最小修复：仅对本次两个非负计数 CHECK 比对归一化后的同源表达式，新增同名反向定义的 PG 失败用例；不引入通用 SQL 解析器。

## 代码质量与证据

- 账户事务、发送预算与 sender 边界清楚；sender 的安全常量异常不关联原始 HTTP 请求，未发现凭据进入日志、DTO 或 URL 的路径。
- 聚焦 PG 测试实际使用多 Session/连接验证首发和最后额度竞争、同 challenge/不同 challenge 消费、账本故障完整回滚、旧账号余额/UUID/密码/会员 revision 保留及永久 claim 生存，不以 mock 账本替代事务证据。
- root 提供的已执行结果：sender 65 passed；冻结 core 51 passed（PG 未 skip）；API/remote 57 passed；兼容 86 passed、1 个既有 xfail；随后联合聚焦 157 passed、1 个既有 xfail。以上数字是各次运行，存在重叠，不作相加，也不冒称为本审核独立重跑。
- 本审核独立执行：`python3 output/wechat-native/run-tests.py /tmp/test_phone_otp_review_probe.py -q --tb=line` → **3 passed in 2.07s**。这是复现上述初审缺陷的探针通过，不能解读为产品修复已通过；文件位于 `/tmp`，不加入产品。
- 所有复现仅使用任务测试 runner 提供的本机隔离 PostgreSQL、随机 schema、测试假号码及 fake sender。未读取真实 `.env`/凭据/DSN，未连接生产 DB/SSH/RK，未发送短信。

## 差异复审

逐行复核修复后的实现及对应回归，结果如下：

| 发现 | 修复与证据 | 结果 |
|---|---|---|
| I1 | `phone_otp.py:175` 仅校验 bind actor，移除按目标 identity 是否存在返回 409 的分支；目标已占用/未知均走相同预算和发送路径。真实 PG 覆盖额度已满时两个目标均 `sms_limited`、无 sender 调用；额度可用时响应形状/语义相同，identity/claim/账本未变化。 | Resolved |
| I2 | `phone_auth.py:48` 的私有 route 捕获 `SQLAlchemyError`，直接返回常量 no-store 503，不重新抛出或记录异常。ASGI 默认 `raise_app_exceptions=True` 的定向测试无异常外逃；真实 PG 账本写入后注入 DB 错误，用户/identity/claim/账本/OTP 消费完整回滚，同码重试只形成一笔 5000 credits 赠额。 | Resolved |
| M1 | `migrations.py:112` 对两个非负计数 CHECK 的实际 sqltext 与同源模型定义进行括号/空白归一化比对；两个同名反向定义分别 fail closed，SQLite 原生格式和重复迁移仍通过。 | Resolved |

本审核独立运行的修复验证命令：

```text
python3 output/wechat-native/run-tests.py tests/web_ui/test_phone_otp_api.py tests/web_ui/test_phone_otp_api_pg.py tests/web_ui/test_phone_otp_limits_pg.py tests/web_ui/test_phone_otp_schema_pg.py -q --tb=line -k 'database_error_is_contained or database_failure_rolls_back or bind_challenge_does_not_disclose or reverse_nonnegative_check or sqlite_phone_nonnegative'
```

结果：**7 passed, 40 deselected, 2 warnings in 4.86s；PG 未 skip**。两个 warning 来自既有 JWT `datetime.utcnow()` 弃用提示，与本次修复无关。相关产品路径与本报告 `git diff --check` 通过。

上述最小修复没有增加通用代理策略、迁移框架或额外认证抽象。首旅程后端审核通过，可继续后续已授权的绑定/父仓工作；正式发布仍须执行计划中的后续验收。
