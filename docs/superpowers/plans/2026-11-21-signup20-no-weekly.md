# Signup 20 and Retire Weekly Free Reports Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 首次手机号验证只赠20积分，取消每周免费复盘及两端展示，保留历史权益与幂等。

**Architecture:** 沿用原有PhoneSignupClaim/账本事务和会员→钱包授权，不迁移余额。新发放2000 credits，响应兼容0/2000/5000；新免费周资格统一停发，历史任务/结果结算不动。沿用现有页面及11语，只删减无用内容并显示权威到账金额。

**Tech Stack:** Python/FastAPI/SQLAlchemy/PostgreSQL、React/TypeScript、Gettext、SmartBox FastAPI/Jinja/JS。

**Spec:** `docs/superpowers/specs/2026-11-21-signup20-no-weekly-design.md`。
**Repositories:** KaTrain worktree `/Users/fan/Repositories/katrain/.worktrees/signup20-no-weekly-20261121` (base26e827f19); parent worktree `/Users/fan/Repositories/smartbox-software/.worktrees/signup20-no-weekly-20261121` (basefb5b32ba)。原有开发目录不得改动。

## Chunk 1: 已确定契约与实现任务

### Task 1: 后端赠额与免费资格停止（一个implementer独占Python文件）

**Files:** `katrain/web/core/phone_otp.py`, `core/remote_client.py`, `api/v1/endpoints/phone_auth.py`, `core/config.py`, `core/membership.py`, `core/billing_operations.py`, `api/v1/endpoints/reports.py`, `api/v1/endpoints/billing.py`；对应 `tests/web_ui/test_phone_{signup,continue,bind,otp_api,continue_api}_pg.py`, `test_phone_otp_api.py`, `test_phone_auth_remote.py`, `test_free_weekly.py`, `test_report_charging.py`, `test_membership_{operations,reports}_pg.py`, `test_membership_journeys.py`，仅更新确实受本策略影响的断言。

- [ ] 先添加/调整行为用例并观察红：新注册/continue/旧号绑定均新赠2000；同账号或手机号重试/并发只一次；历史5000领取者不补赠，不降低其余额；非法bool/字符串赠额继续拒绝。
- [ ] 最小实现 `_SIGNUP_CREDITS = 2000`；所有跨进程响应validator/types明确接受0/2000/5000，保持strict int；不能将领取去重条件改成“delta==2000”。
- [ ] 停止现代 `can_claim_free_report` 新资格，usage兼容free字段但返回eligible=false/remaining=0/limit=0；报价新来源只有member/wallet/owned。已签free报价在未产生操作时拒绝并要求重报价，不静默钱包扣费；相同幂等操作及旧任务授权保留。
- [ ] 取消资格后，非会员/可信验证为false/积分不足的新报告报价应返回既有`402 insufficient_credits`，不得继续返回`403 verification_required`诱导核验；真实身份/登录错误照旧。用既有`test_membership_journeys.py`余额不足场景覆盖。
- [ ] 默认FREE_WEEKLY_REPORTS=0；legacy reports新建路径删除免费周授权，legacy billing/quota返回allowance0。保留旧free任务settlement/refund及通用quota工具，不清理历史数据库。
- [ ] 运行局部Python/API测试；真实PG验证赠额锁、收据与并发：专用loopback `membership_validation*` 随机schema，安全读取既有测试凭据、不打印URL；不得连接生产DB。测试发送器为fake，不发真实短信。若本机缺专用PG，优先使用已有本地测试实例或隔离临时实例，不能以SQLite声称并发验收完成。

### Task 2: Galaxy/Kiosk简洁展示和11语（一个implementer独占UI及i18n文件）

**Files:** `katrain/web/ui/src/api.ts`, `context/AuthContext.tsx`, `features/auth/PhoneOtpForm.tsx`, `features/auth/PhoneBindDialog.tsx`, `galaxy/pages/membership/MembershipPage.tsx`, `kiosk/pages/membership/MembershipPage.tsx`, `kiosk/components/report/ReportAccessDialog.tsx`, `features/membership/ConsumptionQuoteDialog.tsx`, 必要的对应测试与样式（含`ReportsPage`既有测试）；`scripts/phone_otp_translations.json`, `scripts/membership_translations.json`或既有批量翻译源；`katrain/i18n/locales/{en,cn,tw,jp,ko,de,es,fr,ru,tr,ua}/LC_MESSAGES/katrain.po`。

- [ ] 先测试：两种会员页面都不再出现每周免费资格/剩余次数/免费倒计时/资格待确认；非会员仍可看到积分余额并充值/开会员；会员本期/本周用量保留。
- [ ] 赠额类型接受0/2000/5000，成功信息按真实numeric grant/100插值；0不报赠额，5000历史响应显示50，2000显示20。首验证提示20且一次，不再长段解释。
- [ ] 删除上述免费展示块、非会员侧栏免费说明和帮助中的相关句子，必要时以“未开通会员”“使用API积分分析”等短文案替代；不删未知/错误/重试和购买确认，不改价格、会员周规则、页面宽度或导航。
- [ ] 两端共用报价确认窗收到陈旧`free_report`时只提示“报价已更新，请重新发起分析”并提供关闭/重试路径，不能继续调用onConfirm，也不能伪装owned/wallet；正常member/wallet/owned确认保持。Kiosk报告错误窗的旧403改中性账户提示，删除“免费资格”引导，保留真实账户错误语义。添加这两个状态和正常付费确认的聚焦组件测试。
- [ ] 使用 `katrain-i18n-expert`，全部新/改key在现有翻译源及11语同步，保持占位符一致；不要通过全量同步工具产生大范围无关PO变更。
- [ ] 运行受影响Vitest；build和strict2d build；Galaxy代表viewport及Kiosk1024×600各一张真实预览，核对长译文不溢出、关键余额/按钮可见。纯文案/局部删除按用户比例原则，不做全状态重拍。

### Task 3: 盒端launcher契约与短文案（独占parent，不与Task2写同一文件）

**Files (parent):** `setup-wizard/app/routers/auth.py`, `app/static/js/launcher.js`, `app/locales/{zh,zh-TW,en,ja,ko}.json`, `setup-wizard/tests/test_phone_otp_auth.py`, `tests/test_i18n.py`及已有相关JS测试。

- [ ] 先测试20响应可通过register/continue/bind，0和历史5000保留，bool/字符串拒绝。
- [ ] 将原仅接受0/5000的校验扩至0/2000/5000；实际金额成功提示，提示文案20且一次；沿用5种语言现有fallback，不添加无关流程。
- [ ] 不修改identity存储、账号标识、cookie/密钥、权限或手机号验证步骤；只改赠额响应契约和对应精简文案。运行相关pytest/已有JS测试。

契约已确定、3组文件所有权互斥，可按用户明确要求并行开发。独立Astra Max计划审核最多两轮后才启动；实现完成先验spec再验代码质量，最终独立Astra Max审核整组变更，修改直至通过。

## Chunk 2: 集成、发布与验收

- [ ] root聚合局部测试结果、检查git diff范围与11语placeholder，独立审核通过后集成。已有BoxSSO的2项基线失败（WS模拟/旧guest余额检查）只记录，不借机修复。
- [ ] 传统第1步：fetch最新develop合入KaTrain特性分支，解决冲突，验证并push特性。
- [ ] 第2步：合入并push develop，核对实际远端SHA；不把仅部署特性分支说成已发布develop。
- [ ] 第3步：parent先fetch最新main并保留其他会话改动，加入launcher改动、gitlink更新为已发布KaTrain develop，提交并push main，核对两仓40位SHA。
- [ ] 第4步的兼容顺序：先RK3562-local更新代理/页面（能接旧5000与新2000），再TEST→PROD更新云端发放2000。盒端自身board不发赠额，滚动期间success始终显示实际金额。若RK断网，不能先把新2000发给旧的只接5000代理；应报告阻塞而非制造注册失败。旧浏览器页正常刷新后载入新文案。
- [ ] RK仅`rk3562-local`（正常SSH hostkey、hostname gzpeite），先核实设备身份、部署进程、launcher锁和活动棋局；其他会话在部署则等待。使用已发布parent的原生app维护/备份/五模式健康/页面恢复流程；磁盘全量预算保留1GiB，不碰真实用户状态。仅对本次不涉及视觉识别的app发布，未接摄像头可明确allow-offline-camera并记录未验摄像头。
- [ ] 可复用已独立审过的一次性rsync `--copy-dest` 独立暂存优化，保留checksum、空间预算、翻译/前端哈希与事务。只清理用户已授权可删除的旧发布回滚副本；保留本次新回滚，不临时归档或重启Chromium。
- [ ] TEST/PROD按server-deploy：fresh完整Docker Config/Env/网络/挂载私密beforeimage，候选delta独立审核后切换；仅source/image/revision/buildSHA，支付、短信、身份socket、DB/GPU/MinIO保持。核实是否需Cron升级（原则上历史settlement逻辑未变，不应为UI/phone发放重启Cron）。服务器现有FREE_WEEKLY_REPORTS已为0，保持。
- [ ] 发布验证：运行源文件与已发布SHA相符、网站Galaxy/kiosk页面200及新bundle/11语、RK真实DOM不出现免费周文案和错误50赠额提示。需本人手机号的真实短信验收仍由用户亲自收取并输入，不自动发送短信/创建付费订单。
- [ ] 最终报告三个部署目标版本、子模块对应关系、测试结果、用户需验收入口及任何真实限制；不能把HTTP或健康检查说成已做真实付款/手机号赠额全链路。
