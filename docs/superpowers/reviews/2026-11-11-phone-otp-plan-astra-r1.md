# 手机号 OTP 与一次赠额：Astra Max 独立计划审核 R1

**结论：Need fixes。** 仅有下列两项 Important；无 Critical。按最小修正补齐后做一次定向 R2，不扩展为身份迁移或新的安全基础设施。

审核对象：`docs/superpowers/plans/2026-11-11-aliyun-phone-otp-and-signup-grant.md`（144 行），主仓基线 `97f4b49e1ff31c66a2b4c6c1c7de1d569e7f4cb2`，并只读核对父仓既有认证接缝。范围仅为新 B 切片；不重审已发布 A。未修改产品或计划，未运行数据库、SMS、支付或 GPU 操作，未连接任何主机或 RK3562，未读取真实凭据。

## R1-01 · Important：绑定新登录因子缺少当前账号再认证和账号资格边界

**位置：** 计划第 22、39、42、107–109 行。

`purpose=bind` 目前只要求现有 Bearer/session 与新手机号 OTP。OTP 证明的是新号码由谁控制，不能证明操作者仍掌握旧账号密码。取得未过期 Bearer 的人可把自己的号码永久绑定到旧账号，随后反复短信登录；原 Bearer 过期也不能结束这种接管。绑定又不提供解绑/换绑，正常用户无法自行纠正。

计划排除了 guest/local shadow，但没有明确排除 `is_admin` 或保留管理员身份。给管理员增加短信登录因子超出了本次普通账号功能。

**最小修正：**

- 仅为旧账号绑定增加 `current_password` 再认证。可在创建 bind challenge 时验证并把成功证明固定于该短期 challenge，或在最终 bind 提交前验证；必须明确选择一种，不能只依赖此前登录状态。密码不存入 challenge、不转入日志或 URL。
- 对绑定密码失败按当前云端 `user_id` 持久限制为 5 次及明确冷却；更换手机号、flow、challenge 或 worker 不可重置。复用现有持久桶即可，不改旧密码登录和全局 JWT 体系；错误计数必须独立提交。
- bind challenge 与 bind 提交均拒绝 guest、仅本地 shadow、`is_admin` 和保留管理员账号。board/launcher 只向云端合格旧账号转发，不在本地验证 shadow 的 sentinel hash。
- 增加聚焦用例：有效旧 Bearer + 攻击者手机号正确 OTP + 缺失/错误当前密码，不能建立 identity/claim 或改变余额；改号码后失败额度仍受限；guest/admin 拒绝；合法旧账号绑定仍零赠额。

## R1-02 · Important：前端丢弃迟到响应不能替代服务端会话身份约束

**位置：** 计划第 93–95、107、109、116–118 行。

现计划规定前端 generation/abort，并规定取得候选 token 后 `/me` 校验再安装；这仍未规定异步等待期间服务端身份变化时必须拒绝安装。主仓当前 `RemoteAPIClient.login()` 会直接 `set_tokens()`，board 登录路由随后保存 refresh 并绑定 shadow；父仓 `_create_remote_session()` 在远端 `/me` 完成后才调用 `replace_active()`，后者选择调用当时的活动账号。若 A 的登录响应迟到于 B 登录或退出，A 仍可在服务器上覆盖已切换身份，即使浏览器丢弃了 A 的响应。

新绑定/状态转发同样不能使用“云当前 token”的可变全局值：持有 A 的有效本地 token 的请求，不能在换成 B 后替 B 创建绑定挑战、绑定号码或读取私有状态。

**最小修正：**

- board 的 `phone/status`、`purpose=bind` challenge、`phone/bind` 使用已有 `_identity_bound_request(..., expected_user_id=current_user.id)` 或等价的既有身份快照校验。请求使用捕获的 Bearer；身份变化后不改用新用户 token 重试，不暴露迟到的私有结果。
- launcher 从请求的有效 `sb_session` / generation 获取云凭据，使用既有 store 的受控凭据接口；不按“当前活动用户”替换请求身份。转发前后检查同一身份，禁止 guest，刷新也保持同一身份。
- board 和 launcher 的 OTP/本次触及的密码候选登录，在远端等待前捕获服务端认证世代；安装 token、保存 refresh、绑定 shadow 或 `replace_active` 时校验仍允许该次操作。已完成退出、guest 切换或较新的账号安装应使旧操作失败。利用现有 generation/CAS 接缝完成，不引入全局 UUID/JWT 迁移。
- 两类定向并发用例足够：A 候选登录挂起，B 登录/退出后释放 A，B/退出状态及持久凭据不变；A 的绑定/状态请求跨 B 切换，不能使用 B Bearer 或对 B 落绑定。无须扩大为全协议测试矩阵。

## 已有要求足以进入实现的部分

- 6 位/300 秒规范、单事务 OTP 核销/建号/identity/永久 claim/5000 credits、零额度旧账号绑定、删除后重建零赠额和旧无验证码注册拒绝已经明确。账本唯一 ref、永久 claim 与私有手机号边界仍须按计划在实现审核中验证。
- phone → phone/day → IP/hour → global/day 的顺序、唯一桶原子预占、失败/unknown 不返还预算、错误计数跨重发独立持久，以及发送不持账务锁，计划层面完整。
- schema 同源增量、保护表、约束验证与代码回滚保留 claim 足够；无须引入新迁移平台。
- 精确 env/只读单文件挂载需单独审配置增量，不能借旧 code-only helper 放宽；原支付/会员资源保全要求充分。
- root 新补充的 TEST reverse-SSH 绕过 nginx 线索进一步支持 TEST 使用 `trustedProxy=[]`；尚未取得实际 ASGI peer 证据时，两端都用 peer 保守共享桶可接受。PROD 仅有网关推断不足以声称已实测可信入口；遵循现有 fresh-capture 门槛即可，不另扩审。
- 本人号码和真实一条短信证据尚缺，不阻塞源码、MockTransport 和隔离 PG 开发；不得把 STS 成功、供应商接受或 MockTransport 通过表述为真实送达验收。

R2 只复核 R1-01 / R1-02 的明确契约、最小用例和对应文件边界。其余执行、视觉、集成与两云发布继续沿用已授权范围；今天不连接 RK3562。
