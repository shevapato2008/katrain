# 阿里云手机号 OTP 注册登录与一次赠额 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development；无可用子代理时用 superpowers:executing-plans。按 checkbox 逐项闭环。独立 Astra Max 计划审核最多两轮；最终独立 Astra Max 代码及代表性真实页面审核修至通过。沿用用户已授权的开发、集成和两云发布，不再询问是否执行。

**Goal:** 以手机号短信 OTP 完成首次注册及以后登录，新手机号建号一次到账 50 显示积分（5000 credits），旧账号可绑定手机号且余额不变。

**Architecture:** 保留 canonical public username 的 JWT、用户和 Box SSO 契约；手机号只存在私有认证表。PostgreSQL 原子预占发送预算，再在无锁网络阶段调用阿里云；OTP 消费、建号、手机号占用、永久 claim 和账本一次提交。先逐个完成 Fixture 真实预览，再实施该旅程的后端和集成。

**Tech Stack:** 现有 FastAPI、SQLAlchemy、PostgreSQL、httpx、React/Vite、Vitest/Playwright、11 语 gettext；不引入 Redis、支付系统或新部署平台。

**执行状态（2026-11-11）：** B1–B4 首次注册/再次登录已实现并通过独立视觉、规格和代码复审；B1 Fixture 已退出产品源码。真实隔离 PG 接口已验证首次 5000 credits 与回登零重复赠额。B5 旧账号绑定、B6 launcher、两云发布及本人短信送达验收继续执行；目前运行服务器仍为此前发布版本。

---

## 权威范围与已有成果

- 本计划替代旧 `2026-11-11-phone-signup-and-freeplay-analysis.md` Chunk 2 的 phone+password 设计；沿用旧 R2 身份、单事务和风控要求。自由对弈 A 已发布至 `97f4b49e1ff31c66a2b4c6c1c7de1d569e7f4cb2`，不重做 A 或 A 审核。
- 主工作树 `/Users/fan/Repositories/katrain-membership-recharge`；父仓干净集成树 `/Users/fan/Repositories/smartbox-software/.worktrees/freeplay-analysis-20261111` 基线 `f1d3a241`，vendor 为上述主仓 SHA。保留原父仓全部无关修改。
- 已批准：中国大陆 SendSms、签名 `北京万智星科技`、模板 `SMS_512325758`、唯一变量 `code` 为 4–6 位数字、模板文案有效期 5 分钟、modelstella.com 注册登录场景、1000 条余额。实现冻结为 **6 位 ASCII 数字 / 300 秒**。
- root 已只读执行 STS GetCallerIdentity 且 Arn 匹配目标 `katrain-sms`，没有发短信；私有 `credentials.env` 已权限 600。任何 worker 均不得读取、打印、复制进输出或改写真实凭据；秘密不进入 Git、截图、前端、日志或镜像。
- **今天不连接、部署、重启或验收任何 RK3562。** 父仓协议可本机测试、发布源码；明日 fresh capture 后另做设备交接。
- 新账号默认 OTP，两字段为手机号及验证码；不要求用户名/密码。公开 handle 由服务端生成 `u_` + 20 个随机十六进制字符，冲突只重试生成，不包含手机号。
- 手机号首次验证将创建账号；UI 持续说明“已有账号请用账号密码登录后绑定手机号”。不猜测旧数字 username，不自动合并账号。
- 推荐且 root 已接受最小绑定：合格旧账号以当前认证、`purpose=bind` OTP及最终提交的 `current_password` 再认证绑定当前云user_id；零赠额。bind挑战/提交均拒绝guest、仅本地shadow、is_admin与保留管理员账号；无解绑、换绑、改密、国际短信、评论改造或身份大迁移。
- 旧 username/password 登录、现有 JWT `sub=canonical username` 与 `type=access`、刷新/guest/shadow/SSO 继续兼容；不搬旧 phone 分支 UUID+epoch 迁移。
- 不新增真实支付/会员规则，不修改旧余额、会员期、订单或历史赠额；旧 `/auth/register` 无验证码新注册路径必须返回明确 `phone_verification_required` 并引导OTP，不再创建账号；旧账号密码登录保持。不得只维持零赠额而留下无验证注册旁路，也不把 `BILLING_SIGNUP_GRANT` 全局改为 5000。

## Chunk 1：共享契约与第一个用户旅程

### Task B0：冻结文件边界、数据和 API

**Create:** `katrain/web/core/phone.py`（仅大陆规范化）、`sms.py`（唯一 Aliyun sender）、`phone_otp.py`（事务/风控）。
**Modify:** `katrain/web/core/models_db.py`、`migrations.py`、`auth.py:init_db`、`config.py`；`katrain/web/api/v1/endpoints/auth.py`；`katrain/web/core/remote_client.py`。公共 `web/models.py:User/OnlineUser` 不加手机号。
**Create UI:** `katrain/web/ui/src/features/auth/PhoneOtpForm.tsx`、`PhoneBindDialog.tsx`、各自测试；临时 `PhoneOtpFixture.tsx` 与仅本机 dev 入口（最终删除）。
**Modify UI:** `context/AuthContext.tsx`、`api.ts`、`galaxy/components/auth/LoginModal.tsx`、`galaxy/components/layout/GalaxySidebar.tsx`、`kiosk/pages/LoginPage.tsx`、`kiosk/components/settings/AccountSection.tsx`、旧 `components/LoginDialog.tsx` / `RegisterDialog.tsx` 统一导向相同流程。

- [ ] 将以下 DTO/错误码写进实现类型与测试；输入严格长度限制，手机号只接受大陆 11 位 `1[0-9]{10}` 与明确 +86/0086 前缀的等价写法，拒绝其他地区、全角数字及模糊格式。

| API（均在 `/api/v1/auth` 下） | 请求/响应与权威 |
|---|---|
| `POST /phone/challenges` | `{phone,purpose:'login'|'bind',flow_id}`；flow_id 为每次表单打开生成的至少128bit随机值。返回 `{challenge_id,retry_after:60,expires_in:300,delivery:'sent'|'unknown'}`，不返回 code 或手机号。bind必须是合格旧账号当前认证并固定云user_id，不在challenge接收/保存密码。 |
| `POST /phone/login` | `{challenge_id,code,flow_id}`；已绑定则登录，未知手机号则建号并赠额。返回既有 Token 形状；是否新建/余额以随后 `/me` 为准，不在提交手机号上推导身份。 |
| `GET /phone/status` | 仅当前认证用户：`{bound,masked_phone?}`；专用私有端点，不并入公开 User/大厅/棋谱 DTO。 |
| `POST /phone/bind` | `{challenge_id,code,flow_id,current_password}` + 合格旧账号当前认证；最终提交时向云端当前账号做密码再认证，密码不存入challenge/URL/日志。返回 `{bound:true,masked_phone}`。已绑定同号幂等，号或用户已占用则 `409 phone_in_use`；零账本赠额。 |

- [ ] 错误为结构化 `{detail:{code,retry_after?}}`：`400 invalid_phone/invalid_code/challenge_invalid/challenge_expired/challenge_used`、`401 authentication_required/bind_reauth_failed`、`403 bind_not_allowed`、`409 phone_in_use/identity_changed`、`429 sms_limited/otp_locked/bind_reauth_locked`、`503 sms_unavailable/sms_rejected`。错误不得暴露手机号是否已有账户；旧密码错误保持原契约。
- [ ] flow_id 仅持有在当前表单内存/sessionStorage；关闭、换账号或切认证方式即清除 challenge/code。current_password仅绑定表单短期内存，完成/关闭/换人即清；密码、验证码和手机号不持久进localStorage，不进URL；API/代理不记录请求体。
- [ ] 新表均加到 `PHONE_AUTH_TABLES <= PROTECTED_TABLES`：`phone_identities`（phone_e164 unique、user_id unique、verified_at）、`phone_signup_claims`（phone_e164 PK、首次建立时间、领取/绑定类型、可空审计 user_id、grant_ref nullable unique）、`sms_phone_state`（phone_e164 PK、last_send_at、active_challenge_id、error_count、blocked_until）、`sms_challenges`（随机ID、私有phone、purpose、flow摘要、bind_user_id、code摘要、expires_at、状态、consumed_at）、`sms_send_buckets`（kind/key/window_start 唯一、count非负；复用kind=bind_reauth、key=云user_id、固定15分钟桶计绑定验证尝试）。
- [ ] phone_identity 私有原号用于认证；永久 claim 不级联删除，删账号仅解除 identity，不删除 claim/领取事实。claim 审计 user_id 不得用 RESTRICT 阻止未来删号或用 CASCADE 丢失事实。旧余额迁移零写入。
- [ ] code 用 `secrets` 生成，保存 `HMAC-SHA256(现有 SECRET_KEY, 'phone-otp-v1' + challenge_id + purpose + phone + flow_digest + code)`，常量时间比较；密钥轮换只使短期挑战失效，不影响永久手机号归属/claim。
- [ ] 每闭环一个切片，以实际修改路径 `git add`、聚焦检查后 `git commit -m "add phone otp ..."`；契约稳定后仅让无共享状态的sender/测试等任务并行，避免同时铺开未完成UI旅程。

### Task B1：手机号首次注册/再次登录 Fixture → 真实预览

**Tests:** 新 `features/auth/PhoneOtpForm.test.tsx`、`galaxy/components/auth/LoginModal.test.tsx`；扩展 `context/AuthContext.test.tsx`、`kiosk/pages/LoginPage.test.tsx`。

- [ ] 先用 @ui-ux-pro-max 读取现有 Galaxy/Kiosk 设计系统，复用当前登录容器、间距和按钮；默认“短信验证码”，另 tab“账号密码”。不增加新的账户页面或引导步骤。
- [ ] 写有意义的失败用例并运行：发送冷却禁重发、错误保留输入、unknown 提示收到码仍可验证、unavailable 不显示成功、切方式/关闭清挑战、手机/验证码键盘和自动填充语义正确。
- [ ] Fixture 只用本机隔离数据注入状态，不调用发送服务、不写 DB，不设置固定“生产验证码”。展示“未注册手机号首次验证将创建账号；新手机号首次注册赠50积分，已领取或绑定过不重复赠送；已有账号先用账号密码登录后绑定”。
- [ ] 以 Galaxy 1440×900、云 Kiosk 1024×600 在真实浏览器预览：参考 Artifact、实现截图、并排及叠加/差异图同尺寸；记录布局、间距、层级、字体/颜色、图标、文案和状态差异，仅一套代表页及必要错误状态。
- [ ] 用户已授权直接开发并以独立 Astra 代表视觉审核确认当前阶段；记录该授权与确认结论，不再制造人工确认停顿。该旅程视觉通过后才进入 B2/B3 后端。

### Task B2：阿里 sender 与持久限额（可在 B1 通过后独立 SDD）

**Tests:** 新 `tests/web_ui/test_phone_normalization.py`、`test_sms_aliyun.py`、`test_phone_otp_limits_pg.py`。

- [ ] 用 Context7 核对当前官方 [SendSms](https://help.aliyun.com/zh/sms/developer-reference/api-dysmsapi-2017-05-25-sendsms) 与[签名示例](https://help.aliyun.com/document_detail/2593177.html)；本计划已核对 endpoint `https://dysmsapi.aliyuncs.com/`、API `2017-05-25`、POST 推荐、Code=OK 为接受，不能等同手机已送达。
- [ ] 实现最小异步 httpx POST sender（标准库 ACS3-HMAC-SHA256，当前官方向量验证；不新增 SDK 依赖），只发送单个国内号码、冻结签名/模板与 `TemplateParam={"code":"六位数字"}`。3秒超时、禁自动重试；设置敏感 HTTP 日志过滤，异常仅保留安全错误分类/RequestId，不串联 URL/body/原始异常。
- [ ] 可择取 `feature/phone-login@1ae9a7b7` 的纯 phone 逻辑、SmsRejected/SmsUnreachable 分类及适用测试向量；不 cherry-pick 整分支，不搬国际/console sender、旧 GET 含敏感参数日志、count→insert 限额或 verify 内部 commit。
- [ ] 生产唯一 provider 为 Aliyun；凭据运行时只读读取挂载文件，测试只注入 MockTransport。缺失/不完整配置：OTP 明确 unavailable，但现有密码登录/支付服务可正常启动；没有 console/fixed code/mock provider 生产回退。
- [ ] 固定限额：同手机号60秒冷却、每手机号上海自然日5条、每可信IP整点小时20条、全局上海自然日 TEST10/PROD50条；失败尝试最多5次，达到后 phone 级锁15分钟。重发、换purpose/flow/challenge均不重置错误桶；解锁后才重置错误数。
- [ ] 单独 DB 事务按固定顺序锁 phone_state→phone/day→IP/hour→global/day：原子 upsert 唯一桶、条件 UPDATE 预占全部预算、废止旧challenge、插入 pending challenge 后提交。首次并发不存在行也必须用唯一约束/upsert处理，禁止先count后insert；限额失败整次回滚、零短信。
- [ ] 提交后才发短信，不持 phone/user/账务锁。回写同一 pending challenge：OK→sent；明确拒收→rejected；超时/5xx/坏响应→unknown。**三类均保留本次预占预算与冷却**，避免拒收/未知重试套利；unknown 收到正确码可验证，UI 提示状态不确定且不自动重发。进程崩溃 pending 过期不可用，预算不返还。
- [ ] 本次两云均冻结 `trustedProxy=[]`，仅按真实 `request.client.host` peer保守共享IP桶；必须确认ASGI未被宽松proxy middleware提前改写，否则先修精确信任配置或保持短信unavailable。预备的精确白名单仅在后续取得实际ASGI peer与入口覆盖证据后启用；禁任意XFF、整段Docker CIDR或通配信任，不使用XFF用户可控左侧值。
- [ ] 已读到的现场：两云SHA均97f4b49e1；TEST 8001全网且有第三主机reverse-SSH路径，故不依据本机nginx设置启用信任；PROD 8001仅127.0.0.1/10.8.0.3、nginx覆写X-Real-IP，但尚无实际ASGI peer证据，也保持空白名单。本次不连接第三主机，不扩展入口改造。
- [ ] 测试用 barrier、多 Session/连接证明仅剩1额度/冷却首发竞争只发一次、失败预算持久、unknown不退、伪造XFF不换IP、5次错误跨重发/worker仍锁；MockTransport 断言 code/号码只进预期请求且无日志泄露。

### Task B3：OTP 登录/注册与5000 credits 单事务

**Tests:** 新 `tests/web_ui/test_phone_otp_api.py`、`test_phone_signup_pg.py`、`test_phone_otp_schema_pg.py`；扩展 `test_signup_grant.py`、`test_account_subject_contract.py`。

- [ ] 先写失败测试：未验证/过期/目的或flow不符/重放不能建号；正确码首次建号显示50而内部5000，第二次登录零新增赠额；旧账号余额不变。
- [ ] 错误验证用独立短事务：锁 phone_state 再锁 challenge，校验当前active、有效期、purpose、flow与bind身份；错误码递增 phone错误数后提交，再返回错误。不得抛错导致计数回滚；账号事务失败也不能清掉错误历史。
- [ ] 正确候选进入调用方持有的同一 Session：再次按相同锁序校验当前challenge/错误锁/摘要/绑定，核销OTP；已存在identity则取其canonical用户。未知号直接 `db.add(User(...credits=0)) / flush()`，密码为未向任何人提供的高熵随机值哈希；不生成可见密码。
- [ ] 新用户同一事务插入 private identity、永久 phone claim；仅本号从未有claim时 `billing.apply_adjustment(db,user_id,5000,'signup_grant',stable_ref)`，最后唯一一次 commit。已有claim但无identity的重建账号允许登录且零赠额；不是报“用户不存在”。
- [ ] 禁调用自行commit的 `repo.create_user`、`billing.grant` 或旧verify；成功建号后才签发canonical token。唯一竞争失败完整rollback，重读获胜identity/claim；未消费的挑战可重试，但不悄悄把身份不符登录为别的人。
- [ ] 在 `migrations.py` 增加命名明确的 `migrate_phone_auth_schema(engine)` / `verify_phone_auth_schema(engine)`，由既有 `auth.py:init_db` 接缝调用；仅对PHONE_AUTH_TABLES的同源模型 `Base.metadata.create_all(tables=...)` 后校验。空库/旧库/重复执行均安全；检查唯一索引及约束真实列/有效性，已存在不符则fail closed，不drop/rebuild、不补旧余额；不另造迁移容器或CLI。
- [ ] PG并发验证：同challenge及同phone不同challenge至多1身份/1claim/1赠额；账本写入异常回滚建号/identity/claim/consume；成功响应丢失后重放不再赠，下一次新OTP仍登录同号；删号保留claim后重建零赠额。真实查账本唯一ref与余额，不以mock通过宣称事务正确。
- [ ] 聚焦隐私/兼容测试：JWT、`/me`、大厅、棋谱、WS、异常均不含完整手机号；数字旧username与phone分路；guest/admin保留名不可由新生成handle冒用；旧密码登录/刷新保持，旧无验证码注册端点明确拒绝且不建号/不赠额。

### Task B4：把首次注册/登录接入真实前端及 board remote

**Modify/Test:** `AuthContext.tsx/.test.tsx`、`PhoneOtpForm.tsx/.test.tsx`、现有 auth 页面；`remote_client.py`、`tests/web_ui/test_board_auth.py`、`test_account_subject_contract.py`；`ui/tests/auth.spec.ts` 增加OTP隔离旅程。

- [ ] 将OTP token接入现有generation/abort失效机制；拿到token后先用它请求云 `/me` 验证canonical，再装token/用户；登出/换账号后的旧OTP响应不能写回身份。
- [ ] board mode新增挑战/OTP方法。OTP及本次触及的password候选登录在云调用前捕获服务端 `_identity_generation`；远端候选调用不得直接set_tokens。以候选token调用 `/me`，在安装tokens、保存refresh、找/建canonical shadow与bind_user的同一受控提交接缝先CAS该generation；已完成logout/guest切换/新登录使旧候选失败，无持久凭据或shadow副作用。云UUID与板shadowUUID本来不同，保留已有shadowUUID，不强制相等/迁移。
- [ ] board的phone/status、purpose=bind challenge与phone/bind必须复用 `remote_client._identity_bound_request(..., expected_user_id=current_user.id)`：捕获Bearer/generation，转发前后均校验同一身份，refresh只为该快照；换人即 `identity_changed`，不读取新活动token重试或返回迟到私有结果。
- [ ] strict Kiosk继续去setup-wizard，不开放本地直登/直注册；非strict云Kiosk可OTP。对password board登录同样使用云canonical修复输入直建shadow接缝，不将phone当shadow或token sub。
- [ ] `test_board_auth.py`增加两类定向迟到用例：A候选登录挂起→B登录/退出→释放A，B/退出状态及持久refresh不变；A绑定/状态请求跨B切换，不使用B Bearer、不对B落绑定、不返回旧私有结果。不扩为全协议矩阵。
- [ ] 整合真实隔离DB端点验证新号5000、回登不赠、限流/失败可恢复，删除本旅程全部Fixture入口/模拟业务状态；真实sender仍由MockTransport代替，不发短信。
- [ ] 使用 @katrain-i18n-expert：新key先入en.po并同步结构，`scripts/batch_translate_galaxy.py` 补齐本任务全部key，更新 en/cn/tw/jp/ko/de/es/fr/ru/tr/ua PO、编译MO；动态组件使用 `useTranslation()`，金额显示用现有credits换算。只翻译本次新增文案。

## Chunk 2：旧账号绑定与父仓协议闭环

### Task B5：旧账号已登录绑定（无赠额）

**UI:** GalaxySidebar现有账户区一个入口；非strict Kiosk AccountSection一行，使用共享 `PhoneBindDialog`。strict Kiosk仍导向launcher账户入口。
**Tests:** 新 `tests/web_ui/test_phone_bind_pg.py`、`features/auth/PhoneBindDialog.test.tsx`；扩展账户组件测试。

- [ ] 先Fixture预览同尺寸“未绑定→获取验证码→输入当前账号密码→绑定成功”及占用/再认证失败/锁等待文案，复用B1已确认样式；仅绑定表单增加current_password，OTP登录仍只phone+code。独立视觉确认后才做绑定后端，不同时铺开另一个未闭环旅程。
- [ ] bind挑战与提交均要求合格旧账号当前认证并固定同一云user_id，拒绝guest、仅本地shadow、is_admin与保留管理员身份；purpose=login的码、别人的session/code一律拒绝。board只按B4身份快照转发云端再认证，不本地校验shadow sentinel，也不读取可变“当前token”。
- [ ] 最终bind提交先按已认证云user_id原子预占 `sms_send_buckets(kind='bind_reauth',key=user_id,window_start=固定15分钟窗口)`，每桶至多5次；此独立短事务提交后才检查current_password，缺失/错误均计次并返回bind_reauth_failed。更换phone/flow/challenge/worker不能重置，达到上限返回bind_reauth_locked及距窗口结束retry_after；后续OTP/账号事务失败也不回滚该计数。密码仅用于此次云端再认证，不存challenge/URL/日志，不改旧密码登录机制。
- [ ] 绑定同一DB事务核销OTP、插入identity和永久claim(type=bound_existing，未赠额)后commit；不调用任何grant。不允许覆盖已有identity，不做合并/换绑；两账号抢同号或一账号抢两号由两个唯一约束裁定。
- [ ] 测试有效旧Bearer+攻击者手机号正确OTP+缺失/错误当前密码均零identity/claim/余额变化；更换号码仍共享5次user桶、错误计数跨回滚持久，guest/admin/reserved拒绝且不发bind短信；合法绑定旧余额/UUID/JWT canonical原样、账本零新增、后续OTP登录原账号、绑定后删号再建零赠额。服务端换人测试复用B4两类即可；集成后删除本绑定Fixture。

### Task B6：父仓 launcher OTP 传输与身份落点

**Parent Modify:** `setup-wizard/app/routers/auth.py`、`app/services/identity.py`、`app/services/box_identity.py`（现有store的generation/CAS与受控凭据快照接缝）、`app/static/js/launcher.js`、`app/templates/launcher.html`、必要现有 `app/static/css/smartbox.css`、`app/locales/{zh,zh-TW,en,ja,ko}.json`；新增 `setup-wizard/tests/test_phone_otp_auth.py` 并扩展既有launcher/box_identity测试。

- [ ] 本机launcher Fixture按真实1024×600预览默认OTP/密码tab与已登录绑定；独立视觉确认后再接父仓后端。父仓只补既有5语，主仓11语全部保留；不扩父仓语言基础设施。
- [ ] 新增专用PhoneChallenge/PhoneLogin/PhoneBind DTO与路由，保留Credentials旧密码契约；逐字段转发challenge_id/code/flow/purpose，绑定最终提交透传current_password至云端但不持久化。phone/status及bind挑战/提交通过请求有效sb_session/generation取得受控云凭据快照，转发前后核验同一身份、刷新仍绑定该快照，不能从新active全局记录取token；guest/admin资格仍由云端拒绝。
- [ ] OTP及本次触及的password候选登录在远端等待前捕获store认证generation；成功后复用 `_create_remote_session`→`identity.remote_me`→canonical user，在 `replace_active` 既有受控锁/CAS接缝核验原generation再退休旧身份并保存新session。等待期间已完成logout/guest切换/较新登录即拒绝旧候选、无凭据/身份持久写入；手机号不写Box identity或sb cookie，不新增全局身份迁移。
- [ ] `test_phone_otp_auth.py`/`test_box_identity.py`覆盖同B4两类迟到：A候选挂起后B登录或退出，A返回不能改B/退出状态及加密凭据；A绑定/状态请求跨换人仍只能携A快照或失败，绝不携B Bearer或替B绑定。仅补这两类定向回归。
- [ ] 旧register兼容入口收到云 `phone_verification_required` 时引导OTP，不创建未验证账号、不回退密码登录；仅准确 `user_exists` 才允许原有duplicate→password login，不把所有400/409当重复，OTP永不走该回退。测试验证码400、phone_in_use409、上游不可达、canonical不一致及退休失败不误切账号。
- [ ] 父仓本机测试通过、删除launcher Fixture；只提交源码和vendor指针，今天不访问RK、不声称实机绑定或灯反馈通过。

## Chunk 3：最低充分验证、审核与两云发布

### Task B7：自动化和一次本人短信验收

- [ ] 每个服务任务先运行新增聚焦失败用例，再最小实现至通过；不写镜像实现的浅测试。PG复用 `tests/web_ui/membership_test_support.py`，新增测试不得读应用默认DB。
- [ ] `python output/wechat-native/run-tests.py tests/web_ui/test_phone_normalization.py tests/web_ui/test_sms_aliyun.py tests/web_ui/test_phone_otp_limits_pg.py tests/web_ui/test_phone_otp_api.py tests/web_ui/test_phone_signup_pg.py tests/web_ui/test_phone_otp_schema_pg.py tests/web_ui/test_phone_bind_pg.py tests/web_ui/test_board_auth.py tests/web_ui/test_account_subject_contract.py tests/web_ui/test_signup_grant.py` → 全部PASS且PG未skip；runner私下供给TEST_DATABASE_URL，loopback `membership_validation*` + 独立TEST marker、随机schema，`KATRAIN_DATABASE_URL=sqlite:///:memory:`。不打印私有env/URL。
- [ ] UI目录运行 `npm run test -- src/features/auth src/context/AuthContext.test.tsx src/galaxy/components/auth/LoginModal.test.tsx src/kiosk/pages/LoginPage.test.tsx src/kiosk/components/settings/AccountSection.test.tsx` → PASS；`npm run build` 与 `npm run build:smartbox-kiosk-2d` → PASS。
- [ ] 仓库根按顺序运行 `python i18n.py`（新key结构）、`python scripts/batch_translate_galaxy.py`、`python scripts/compile_gettext_catalogs.py` → Compiled 11 gettext catalogs；聚焦检查新增key全部有翻译与占位符一致，不追加全目录重译。
- [ ] 父仓运行 `python -m pytest setup-wizard/tests/test_phone_otp_auth.py setup-wizard/tests/test_box_identity.py` 及实际改动的launcher测试 → PASS；一套普通浏览器Galaxy/云Kiosk/本机launcher代表旅程即可，不做全状态截图矩阵。
- [ ] 自动化测试禁止任何真实SendSms；仅在TEST发布且用户给出本人号码后，通过正常UI发送**一条**并人工输入收到的码验收首次建号及50积分。号码目前缺口不阻塞源码/MockTransport/迁移测试；不得猜号码、批发短信或以固定码宣称真实通过。该条可复用为唯一真实供应商证据，绑定路径用隔离测试覆盖，不另发第二条。
- [ ] 按SDD做规格/质量审核；最后独立Astra Max审核最终diff、聚焦测试和同尺寸代表真实页面至通过。只重验实际修订和最可能回归，不重审A、不做无关支付回归。

### Task B8：集成、精确配置增量和TEST→PROD

- [ ] 读取 @server-deploy；fetch最新develop→合入feature→解冲突→聚焦验证→commit/push feature→合入并push develop→在上述父仓干净树更新vendor至已发布develop、提交并push main。保持用户无关工作树不动。
- [ ] 新建本次发布目录 `output/releases/phone-otp-20261111/`；fresh capture两云完整Config/HostConfig/Env/挂载及实际ingress；公开回执只输出非敏感值和哈希，秘密不落截图/聊天。确认TEST=home-ubuntu、PROD=ucloud-v100实际名称及SHA。
- [ ] 旧code-only helper只允许改变 `KATRAIN_BUILD_SHA`，不能冒充它已授权任意加env/mount。本次另编最小config-delta manifest/验证器（本任务发布目录内），让独立Astra审明确allowlist后才应用；拒绝其他差异。
- [ ] 精确新增非秘密env：`KATRAIN_SMS_ENABLED=true`、`KATRAIN_SMS_CREDENTIALS_FILE=/run/secrets/aliyun-sms.env`、`KATRAIN_SMS_SIGN_NAME=北京万智星科技`、`KATRAIN_SMS_TEMPLATE_CODE=SMS_512325758`、`KATRAIN_SMS_DAILY_LIMIT=10|50`、`KATRAIN_SMS_TRUSTED_PROXY_IPS=`（两云本次均空，仅peer桶）；手机号/验证码规则为上述代码常量，不增加随意覆盖开关。
- [ ] 精确新增单文件只读bind：各主机root确认的私有credentials.env→`/run/secrets/aliyun-sms.env:ro`，宿主600。通过安全传输装配，worker不得读/回显内容；缺配置先保持SMS disabled/unavailable。不得把AK/SK加入Docker Env、镜像或payload。
- [ ] 发布review列明本次5表/索引/约束DDL；由既有启动 `init_db` 调用同源 `migrate_phone_auth_schema`、`verify_phone_auth_schema`，校验通过才接受OTP请求，留备份及重复执行/回滚说明。回滚代码保留私有表和永久claim，不反向删表/赠额；不额外发明one-shot容器或迁移框架。
- [ ] config-delta核对保留微信8项Env与原只读秘密挂载、enabled/live、billing=true、Free0、Max sale原值、网络、卷、端口、资源限制、健康检查及其他运行资源；不关闭原支付/会员，不重启无关DB/GPU/Cron。
- [ ] TEST先发布并验证健康、SHA、真实Galaxy/Kiosk密码/OTP状态和隔离账户账本；本人单条短信若号码尚未提供，准确记录“真实送达未验收”，不能声称已正式验收。配置/迁移或实际功能失败不得推进PROD。
- [ ] PROD按同一已审代码/明确配置增量发布，验证健康及代表实际页面，避免消耗个人额度或代用户付款；保留发送预算可用与旧账户登录。回执报告feature/develop/父仓main精确commit、两云运行SHA、迁移状态、短信验收结果/缺口。
- [ ] 明日RK交接仅记录：父仓源码已准备、设备今天未更新、需重新fresh capture后验证本人OTP/旧密码/绑定、SSO canonical、500visits与灯反馈；不在本次补做设备部署。
