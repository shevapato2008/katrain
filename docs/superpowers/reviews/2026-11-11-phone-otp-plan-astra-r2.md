# 手机号 OTP 与一次赠额：Astra Max 独立计划审核 R2

**结论：Approved。R1-01 与 R1-02 均已关闭，可立即进入 B1 UI Fixture / SDD。第二轮计划审核结束，不需要第三轮。**

审核对象：`docs/superpowers/plans/2026-11-11-aliyun-phone-otp-and-signup-grant.md`（修订后 148 行）。本轮仅定向复核首轮两项 Important，不重审已发布 A，不扩大范围。

| 首轮问题 | 修订核对 | 结论 |
|---|---|---|
| R1-01：绑定新登录因子缺少再认证和资格边界 | 第 22、39、42、44–46、108–112 行已选择最终 bind 的 `current_password` 再认证；按云 user_id 在独立事务原子预占固定 15 分钟桶，至多 5 次，缺失/错误及后续回滚均不退回额度，不能靠换号/flow/worker 重置。challenge 与 bind 均排除 guest、仅本地 shadow、is_admin 与保留管理员身份。密码仅短期内存及云端验证，OTP 登录仍是两字段。相关失败与合法零赠额用例齐备。 | 已关闭 |
| R1-02：迟到请求可改变服务端身份或使用新用户凭据 | 第 94–97、116、119–121 行已规定 board 私有 OTP 路径复用 `_identity_bound_request(expected_user_id=current_user.id)` 与捕获 Bearer/generation；launcher 按请求 sb_session/generation 取得受控快照。候选 OTP/password 不提前安装 token，远端 `/me` 后在既有受控接缝 CAS，退出/guest/较新登录淘汰旧操作，持久 refresh/shadow/session 不留旧请求副作用。两类定向迟到回归已经列入。 | 已关闭 |

绑定限额选择“全部验证尝试预占”而非成功后退额度，属于简单保守实现，满足首轮独立持久防刷要求，无须新增限流体系。

本次两云 `trustedProxy=[]`、仅真实 peer 保守共享桶的冻结与第 72–73、142 行一致；未知 ASGI 代理改写仍按计划保持 fail closed。旧无验证码 `/auth/register` 拒绝要求仍保留。

本结论批准计划进入实现，不表示产品、并发测试、真实短信送达或发布已经验收。本人一条短信证据缺口沿用计划记录；不阻塞已授权的 UI/MockTransport/隔离 PG 开发。后续仅按既定最终代码及代表页面审核闭环，今天不连接任何 RK3562。

本轮只读计划并写此审核记录；未修改产品或计划，未访问秘密、SSH、数据库、SMS 或设备，未提交 commit。
