# 后台专用账号与教程管理：垂直切片计划

状态：Galaxy 风格旧设计及 Fixture 四图曾获 Fan 确认，已进入本地契约与后台实现；随后 Fan 又决定后台专属 B「石墨铜」夜间、C「雾白蓝」白天及楷体。新主题已在本地 React 前端实现并做同视口核对，**Fan 已确认新版 React 外观**，详见 [新主题视觉记录](./tutorial-theme-visual-review.md)；这不等于真实后端集成验收。本文覆盖旧 spec §5.3 的共享 `users.is_admin` 身份方案，并取代旧 cron 计划中“先做 cron”的顺序；旧计划中网络隔离、同视口视觉关卡、发布审批仍有效。**本文件、教程设计稿和 Fixture 不得在切片 0 推至 develop 前提交。**

## 裁决和边界

- 第一个完整模块是教程管理；cron 在教程完成后另起完整切片。公开 Galaxy 的用户成品阅读页面由 Fan 的另一 session 负责，本切片只做后台工作台及其必要的公开 API 退役。
- 首版只有一个后台专用操作者，登录名 `admin:fan`。`KATRAIN_ADMIN_USERNAME`、`KATRAIN_ADMIN_PASSWORD_HASH`、`KATRAIN_ADMIN_SESSION_SECRET` 仅注入 admin 进程；不用 Galaxy `users` 表、不用公共 `KATRAIN_SECRET_KEY` 签后台令牌、不开放后台注册。
- 后台令牌保持 8 小时、localStorage + Bearer；必须显式校验 `sub`、`type=admin_session`、`aud=katrain-admin`、`env`、`exp`。更换口令时同时轮换后台签名密钥才能使旧令牌全部失效。审计主体为 `realm=admin` + 用户名，不伪造公开用户 ID。
- 独立进程、SSH 隧道、宿主机仅 `127.0.0.1:8010`；后台凭据隔离不等于业务库权限隔离。后台进程不自动建表；公开 web 的 schema 初始化负责必要的审计表。
- 公开教程 GET、图片/音视频资产 GET 保留；四个教程写接口最终只在后台同源 `/api/admin/tutorials/*` 提供。旧公开设备列表及两项计费管理接口最终撤挂，设备心跳和普通计费操作不动。过渡期不临时恢复公开管理员。
- 原书页、棋图、讲解音频、视频和审核状态都必须取自当前环境真实数据。TTS 失败/上传失败不可伪称成功；保存冲突保持 `expected_updated_at` 语义。后端集成后删除 Fixture。线上全表替换式教程同步可能覆盖后台编辑，教程上线前须停用/调整该路径并备份核差。

## 完成顺序与停点

### T0：切片 0 安全发布（先做，不把教程半成品推上去）

- [x] 切片 0 Task 1–5 已完成并经 Fan 确认；Task 6 Step 1 已在单独授权后只读清点，三个环境只有旧 `admin`。
- [x] 移除公开 web 空库自动创建管理员的入口，聚焦测试先红后绿，提交 `b84a015a`。
- [ ] 🛑 对每个环境的旧 `admin` 做只读目标核对后，逐条取得 Fan 对该环境写库命令的当场批准：撤 `is_admin`、密码改为不可恢复随机值。不能把异步方案选择当成实际写库许可。
  - [x] Fan 单独批准测试机写库后，`home-ubuntu` 的 `katrain_db.users.id=1` 已在同一事务撤权并换随机口令哈希；写后返回 `admin False password_hash_changed`。本机和生产仍未写入，下一条命令须重新取得批准。
- [ ] 🛑 每次 push、测试部署、生产部署分别请求当场批准。先测试后生产；撤权与安全补丁发布作为同一变更窗口，不单独宣称其中一步已关闭匿名教程漏洞。推送前核对只包含安全提交，不包含本文件、设计稿或 Fixture。
  - [x] Fan 明确要求后，`feature/admin-console` 与 `develop` 均已推送切片 0 合并提交 `f0a0b4a9`；未包含本文件、设计稿、Fixture 或未完成教程后台。测试/生产部署及服务验收仍未执行，安全发布窗口未结束。
- [ ] 验证旧公开登录失败、未登录教程写入被拒、设备心跳和只读教程仍工作，并记录设备列表/计费管理功能暂时不可用。

### T1：教程工作台设计（当前阶段）

- [x] 按 `ui-ux-pro-max` 和 Fan 的 Galaxy 截图产出 [设计说明](./tutorial-design-notes.md)、[HTML 设计稿](./tutorial-admin-design.html?state=detail)，以及 1440×900 的 [登录](./tutorial-admin-design-signin-1440x900.png)、[详情](./tutorial-admin-design-detail-1440x900.png)、[编辑](./tutorial-admin-design-editing-1440x900.png)预览。
- [x] 🛑 Fan 已确认第一版工作台设计稿，T2 第一版已完成。
- [x] 🛑 Fan 确认 Galaxy 风格与字体一致的[修订设计稿及三态截图](./tutorial-design-notes.md)。

### T2：隔离的 Fixture 前端（只做可见旅程）

目标文件：`katrain/web/ui/admin.html`、`vite.admin.config.ts`、`src/admin/**`、`package.json`、`.gitignore`、`eslint.config.js`。不改公开 `vite.config.ts` 的构建路径。

- [x] 聚焦测试先红后绿：入口/隔离和演示登录、书章图切换、棋图编辑/撤销、讲解草稿、保存/生成语音/审核反馈。
- [x] 独立入口与最小 shell；Fixture 位于 `src/admin/fixtures/`，所有操作标为开发预览，生产构建仅显示“管理后台尚未接入”。真实 API client 与 token key 留到 T5 集成时加入，避免为 Fixture 伪造鉴权。
- [x] 工作台复用纯 `SGFBoard`；公开包不导入 `src/admin/**`。Fixture 不含后台密钥或生产数据，原书页明确为示意图。视频仍是“未接入”状态，不伪造可播放内容。
- [x] 1440×900 真实 Chromium 中走通演示登录、编辑落子/撤销、保存讲解、切换下一图；相关测试、lint、后台及原 Galaxy/kiosk 构建通过。
- [x] 按 Galaxy 主题换肤：复用本地文楷字体及品牌图，页眉、侧栏、面板、按钮与公开 Galaxy 风格一致；不导入其业务路由或认证状态。相关测试先红后绿，13/13 通过，后台构建、lint 通过。

### T3：同尺寸四图视觉关卡

- [x] 1440×900 的“图详情”和“编辑中”均保存设计参考图、真实 Chromium Fixture 图、并排图、叠加图、差异图；几何及语义差异见 [视觉对比记录](./tutorial-visual-review.md)。设计稿是参考，没有冒充运行时实现。
- [x] 🛑 Fan 曾确认第一版四图，随后追加视觉变更；此前确认只适用于第一版。
- [x] 1440×900 的新版详情和编辑态已保存参考图、真实 Chromium Fixture 图、并排图、叠加图、差异图；见 [Galaxy 风格四图记录](./tutorial-visual-review-galaxy.md)。
- [x] 🛑 新版 Galaxy 风格 Fixture 四图获 Fan 确认；可冻结数据契约并进入本地 T4 后端，不含远程、写库、push 或部署授权。
- [x] 🛑 Fan 确认 B 夜间／C 白天＋楷体的本地 React 外观；只解除新版视觉停点，不包含教程模块验收或发布授权。

### T4：后台身份与教程 API

目标文件：`katrain/web/admin/{app,settings,session,audit}.py`、`routers/{auth,tutorials}.py`、必要的 `katrain/web/core/models_db.py` 审计表，以及 `tests/web_ui/test_admin_*.py`。不调用公开 `create_app()`。

- [ ] 先写失败测试：缺/弱凭据拒启；公共 access/refresh 不能进后台，后台令牌不能进公开 API；缺 `aud/type/env/exp` 拒绝；后台用户名与 Galaxy 用户隔离；失败登录不泄露具体原因。
- [ ] 实现单管理员 env password hash 校验、后台独立 JWT 密钥、登录/登出/`me`、CSP/无跨站 CORS、同源静态资源。审计记登录和写操作，`actor_realm=admin`，无虚构 `users.id`。
- [ ] 先写失败测试，再迁移四个教程写操作；请求先鉴权，保存遵守并发版本，服务端确定作者/审核者；公开只读资产可从后台工作台读取。必要共享业务函数只在服务层复用，不让后台 token 被公开 API 接收。
- [ ] 错误路径只测本次真实边界：TTS 部分成功/重试，审计与业务提交一致性，媒体共享存储和训练样本路径；不搭通用任务平台。

### T5：真实集成与公开路由退役

- [x] 本机隔离 SQLite＋独立后台进程＋1440×900 真浏览器已验证登录、读取、讲解保存、双标签 409 保留草稿并重试、失效令牌 401 返回登录；见 [交接报告](./codex-report.md)。这不是测试/生产环境验收。
- [x] 补齐无棋盘图和空小节的诚实状态；旧视频在棋图、讲解或语音变更后失效；“预检查”改为明确的人工核对确认。相关测试先红后绿。
- [ ] admin 前端换真实 API、删除 Fixture；确认书/章/图切换不串草稿，401 退出/重登，冲突提示与重试，音频视频更新后可重新读取。
- [ ] 公开 `/api/v1/tutorials` 四写路由、`GET /board/devices`、两项计费管理员路由撤挂；公开 Galaxy/kiosk 不含后台写 client/编辑控件。另一 session 的成品页合入时先核对其工作树，避免覆盖。
- [ ] 真实本地端到端与必要回归、后台构建及原 Galaxy/kiosk 两套构建；检查生产构建无 Fixture。切片只有真实可部署、状态诚实、后端已集成且 Fan 验收通过才算完成。

### T6：发布与下一模块

- [ ] 🛑 push、测试部署/验收、生产部署/验收及每次涉及真实数据的命令均逐项取得 Fan 当场批准；不主动 SSH。环境凭据只检查存在/长度，不打印值。
- [ ] 教程模块完成后，按相同顺序为 cron 先做 `ui-ux-pro-max` 设计与视觉确认，再用旧 cron 计划中仍适用的记录器/健康判定部分实现；旧计划的共享用户鉴权段一律不用。

## 当前可交付与未满足的关卡

当前有切片 0 本地安全补丁，以及后台专用身份、真实教程 API 和前端的未提交本地实现；B 夜间／C 白天＋楷体外观已获 Fan 确认，本机临时库真实 HTTP 浏览器流程已跑通。教程模块尚未获 Fan 端到端验收，真实媒体生成／播放、测试和生产环境仍待验证。旧全表教程同步已在三份技能说明中标为停用，替代导入流程尚未制定。没有具体授权不能写任一真实库、连接远程、push 或部署。
