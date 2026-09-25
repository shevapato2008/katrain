# 管理后台 Codex 跨 session 交接（2026-09-24）

## 2026-09-25 性能监控方向修正（新版 HTML 设计，🛑 待 Fan 确认）

- Fan 指出性能监控原 spec §10 与此前沟通是**内嵌 Grafana**。上一版“独立面板入口”没有得到 Fan 确认，不能当作选定方案；其本地 Fixture 和四图已废弃，仅作历史。现已把 [HTML 设计稿](./slice2/design/admin-performance-access.html) 改为后台内嵌 Grafana 布局，保留夜间/白天 B/C 楷体、未接入诚实空态；内嵌示意仅有无数据占位，不冒充实际 Grafana 或服务在线。新版 1440×900 三张设计图见 [设计记录](./slice2/design/design-notes.md)，Chromium 控制台 0 error、0 warning；独立 GPT-6 Astra 裁定设计方向 **APPROVE**，无必改项，但不替代 Fan 确认。
- 🛑 先请 Fan 确认新版 HTML 设计，再按 [修订计划](./plan-2026-09-25-admin-performance-access.md) 修改隔离 React Fixture、制作新版四图；四图再由 Fan 确认，之后才核实测试环境 Grafana、冻结契约或写后端。真实嵌入必须核实 Grafana 自身鉴权、iframe 策略与后台 CSP，不传后台 Bearer，不开放无保护端口。没有进行远程连接、真实写入或部署。

## 2026-09-25 旧性能监控入口提案（历史；已废弃）

- 按 spec §10 的建议顺序，在 cron 后开始性能监控模块。已完成 `slice2/design/admin-performance-access.html` 单文件设计稿，沿用已批准的 B 石墨铜夜间、C 雾白蓝白天与楷体，经 `ui-ux-pro-max` 核对；独立 GPT-6 Astra 先要求修正后台壳层尺寸，修后批准进入本地 Fixture。设计/架构取舍见 [记录](./slice2/design/design-notes.md) 与 [计划](./plan-2026-09-25-admin-performance-access.md)。
- React Fixture 使用独立 `admin-performance-fixture.html` 入口，只展示“尚未接入”与明确标记的“已配置示意”；无假指标、可点击监控链接或令牌，正式 `admin.html` 未改。两态各自的参考/真实运行/并排/叠加四图已入 `slice2/design/`；独立 Astra 查看八图，裁定本地视觉 **APPROVE**，轻微壳层字位差异不阻断。Chromium 1440×900 控制台 0 error、0 warning。
- 聚焦前端 **15 passed**（性能 3 项＋既有后台 12 项），`build:admin`（含 `tsc -b`）、性能文件 ESLint、`git diff --check` 通过；确认 Fixture 入口与示意文案均未进入正式后台构建。
- 🛑 Fan 尚未确认四图或访问旅程。当前首选是后台提供独立监控面板入口，经已有 SSH 隧道访问，**不是**旧 spec 中的同页 iframe；这只是设计提案，未冻结契约。真实目标环境是否已有 Netdata/Grafana 尚未核实，未连接远端、未写库、未部署。Fan 若要求同页嵌入，先调整设计与鉴权方案。后续每次 SSH、push、部署分别重新授权。

## 2026-09-25 教程页字号跟进（已推送 develop，未部署）

- Fan 对照测试后台截图要求教程管理页与定时任务页字号一致。本地仅调整已登录教程页的顶部/侧栏和三栏文字层级，保留楷体、主题、登录页字号、cron 页与业务行为；右侧讲解从 26px 收至 18px，原书说明从 24px 收至 17px。`ui-ux-pro-max` 的后台排版一致性建议用于核对现有层级，未另起主题。`AdminApp.test.tsx` **12 passed**、`build:admin`、单文件 ESLint、`git diff --check` 通过；本机 1440×900 查看/编辑真实浏览器预览在忽略目录 `output/playwright/admin-runtime-dark-*-kaiti-1440x900.png`，无明显遮挡。
- Fan 授权一次推送后，先无冲突合并 `origin/develop=c6d8408c`（kiosk 更新），合并结果为 `e9dc7a85`；聚焦 **12 passed**、`build:admin`、`git diff --check` 通过，已执行一次 `git push origin HEAD:develop`，远端回执 `c6d8408c..e9dc7a85 HEAD -> develop`。`origin/feature/admin-console` 未同步，测试/生产均未部署；测试机 `127.0.0.1:8013` 仍显示旧字号。性能监控新模块工作在这次推送之后，不包含于 `e9dc7a85`。

## 2026-09-25 测试 cron 部署验收（最新）

- Fan 针对依赖修复 `2529a153` 单独确认第二次推送和测试 cron 重建。推送前 `origin/develop=35100955` 是本地 HEAD 的祖先，聚焦 Python **28 passed**；已执行一次 `git push origin HEAD:develop`，`origin/develop=2529a153`，测试机 `develop` 只快进到同一 SHA，远端已跟踪工作树干净。`origin/feature/admin-console` 未推送；用户既有 `.playwright-cli` 工作树状态保持原样。
- 测试机仅重建 `katrain-cron`；镜像确认为 SQLAlchemy **2.0.54**、psycopg2 驱动，容器稳定运行。真实测试库已有 **9 条**任务状态与运行历史；独立后台的只读 API `/api/admin/cron/jobs` 返回 9 项且健康态全部 `ok`，心跳最大约 23 秒；`fetch_list` 历史有 2 条成功运行，`/api/admin/cron/queues` 两队列读取正常。`poll_moves` 是 3 秒高频任务，正常成功不逐条持久化历史，只记录异常，故其历史空列表属契约预期。验收使用容器内签发的临时 Bearer 做只读 GET，没有调用会写审计表的登录 API；先前已验证 Keychain 密码与容器哈希匹配。
- web/admin 保持健康；后台仅绑定测试机 `127.0.0.1:8012`，公开 web 后台路由仍为 404；`katago-calib` 的测试机 8010 端口、PostgreSQL/MinIO 和生产环境均未变。Mac 本地 8010 当前被既有 Python 预览占用，Fan 浏览测试后台可另开隧道 `ssh -N -L 8013:127.0.0.1:8012 home-ubuntu`，随后访问 `http://127.0.0.1:8013/admin.html`；用户名 `admin:fan`，随机密码在 Mac Keychain 的 `katrain-admin-test` 服务项。尚待 Fan 亲自视觉确认；外部 Edge TTS/真实教程媒体、生产部署与旧生产管理员处置都未由本次验收覆盖。
- 本段交接记录为测试验收后的**本地未推送改动**；本次已获准的第二次 push 只含 `2529a153`，不得顺手再 push 报告或其他内容。

## 2026-09-25 测试机部署中途记录（历史；第二次 push 已于上节获准并完成）

- Fan 针对本次测试部署明确确认：重新合并 `develop`、**一次** `git push origin HEAD:develop`、创建测试后台专用凭据、备份测试库并允许 web 建两张 cron 表、重启测试 web/cron/admin；未授权生产操作或第二次推送。本地合并 `origin/develop=7573f0e7` 后验证：根目录聚焦 **95 passed**、web-ui 聚焦 **362 passed**、管理前端 **185 passed**，Galaxy/后台/kiosk 构建及 kiosk 边界通过。唯一初始红测是本机忽略的中文 `.mo` 缺失，编译本机 `.mo` 后通过，未修改源 `.po`。已将 `35100955` 一次推到 `origin/develop`；`origin/feature/admin-console` 未更新。
- 测试机数据库先备份为 `/home/fan/Repositories/katrain/data/admin-backups/katrain-db-pre-admin-6Sd4K5cp.dump`，约 190 MB、权限 600，`pg_restore -l` 校验通过。`develop` 快进到 `35100955`。专用随机密码仅存 Mac Keychain（service `katrain-admin-test`、account `admin:fan`），测试机 `.env` 原样备份至 `data/admin-backups/.env.pre-admin-d40f6f805999` 后添加 bcrypt cost 12 哈希、随机 session secret、`KATRAIN_ADMIN_ENV=test`、`KATRAIN_ADMIN_HOST_PORT=8012`，`.env` 与备份均为 600；没有打印密码、哈希或 secret。
- 新 `katrain-web` 与 `katrain-admin` 在测试机启动：web `/api/v1/health` 200，公开 web `/api/admin/health` 404；独立后台只绑定 `127.0.0.1:8012`，`/api/admin/health` 200 且 `env=test`。Keychain 密码与容器内哈希只做布尔核对，匹配；没有调用会写审计表的登录 API。web 已创建 `cron_job_status`、`cron_job_runs` 两表。`katago-calib` 保持在 `127.0.0.1:8010`、未停或重建；PostgreSQL/MinIO 未重建。
- 新 `katrain-cron` 镜像启动失败：`requirements-cron.txt` 的 `sqlalchemy>=2.0` 装到 2.1.0，其裸 `postgresql://` 默认驱动需 `psycopg`，镜像只装 `psycopg2-binary`，报 `ModuleNotFoundError: psycopg`。本地先加红测，再将 cron SQLAlchemy 约束改为 `>=2.0,<2.1`，聚焦 **28 passed**。因本次仅批准**一次 push**，此修复未推送/部署。测试机已将保留的 `katrain-katrain-cron:pre-7c6e5ca5`（SQLAlchemy 2.0.52）恢复为运行镜像，原新版镜像留作 `failed-35100955`；旧 cron 连续运行 5 分钟且 `poll_moves` 成功。旧 cron 不写新状态表，现 `cron_job_status` 为 0 行；因此 **cron 真实数据验收尚未完成**，不可视为整个切片部署完成。
- 下一步 🛑：只对本地依赖修复提交重新取得**第二次** `git push origin HEAD:develop` 明确许可；获准后测试机快进、重建并启动新 cron，验证九条真实任务状态/心跳/运行历史与后台读取。每条后续真实写库、生产连接/部署、父仓推送均另请批准。不要清理用户原有 `.playwright-cli` 工作树状态。

## 2026-09-25 测试机部署预检（历史）

- Fan 回复“好，部署吧”，本轮仅按测试机部署理解；未获生产部署授权。本地 `feature/admin-console` 已合并当时的 `origin/develop=81e02c7e`，无冲突，保留用户原有 `.playwright-cli` 删除与未跟踪快照。合并后根目录聚焦 Python **25 passed**、web 聚焦 Python **353 passed**、前端 **149 passed**；Galaxy、后台、kiosk 2D 三套构建及 kiosk 隔离验证、管理前端 ESLint、差异空白检查通过。预检期间 `origin/develop` 又前进到 `0a533a3e`；推送前须重新合并并复测，不能基于旧祖先强推。
- 测试机 `home-ubuntu` 只读预检：工作树在 `develop=81e02c7e`，只有原有未跟踪文件；`katrain-web`、`katrain-cron` 在运行。`127.0.0.1:8010` 被已运行的 `katago-calib` 占用，不能直接启动后台；8012 空闲。测试机 `.env` 没有 `KATRAIN_ADMIN_USERNAME`、`KATRAIN_ADMIN_PASSWORD_HASH`、`KATRAIN_ADMIN_SESSION_SECRET`、`KATRAIN_ADMIN_ENV`；未打印任何密钥。数据库已有 `admin_audit_log`，尚无 `cron_job_status` 和 `cron_job_runs`。磁盘约 64 GB 可用（占用率 93%）。没有改服务、配置、数据库或远端文件。
- 独立 GPT-6 Astra 建议保留校准服务、给后台选空闲回环端口。已在本地把 Compose 的后台宿主机端口改为可配置、默认 8010；测试机拟设 `KATRAIN_ADMIN_HOST_PORT=8012`，本机测试隧道仍用 8010→测试机 8012。`tests/test_admin_compose.py` 先红后绿 **2 passed**，本机 Compose 解析只输出 `127.0.0.1:8012:8010`。上述改动尚未推送或部署。
- 🛑 下一步必须明确核准本次 `git push origin HEAD:develop`；部署时创建后台专用凭据并使 web 初始化两张新 cron 表也需按此前“每次 push／真实库写入单独点头”的约束确认。测试机部署许可不自动扩展到生产、停止 `katago-calib` 或覆盖未跟踪文件。

## 2026-09-25 当前推进（覆盖下文旧 Git 状态）

- Fan 确认 cron 的模块前缀与缩小字体后，已将 `f5a9dedc`、`e91c50e3`、`2a979d01`、`60d157c1` 快进推送至 `origin/feature/admin-console`；远端现指向 `60d157c1`。未合并或推送 `develop`，未动父仓子模块，也未连接服务器、写真实库或部署。
- 推送前重新核对远端为当前分支祖先，cron 后端聚焦 **62 passed**、管理前端 **51 passed**、`build:admin`（含 `tsc -b`）和 `git diff --check` 通过。推送后补教程工作台书／章切换草稿隔离测试，现有实现无需改动；管理前端 **53 passed**，公开教程／计费路由 **28 passed**，该测试文件 ESLint 与 `tsc -b` 通过。这些新增测试及本交接更新是后续本地工作，不包含在已推送的 `60d157c1` 中，后续再 push 仍需 Fan 当场批准。
- cron 仍只在本机隔离 SQLite 中做过合成数据真实 API 浏览器验证；教程外部 Edge TTS、目标媒体存储和测试／生产环境，cron 的真实 web＋cron＋admin 三服务与任务状态，均未验收。下一步是计划中的目标环境关卡；SSH、真实库写入、测试部署和生产部署各需 Fan 当场单独批准。

## 2026-09-25 本地开发记录（以下 Git 状态为当时状态）

- cron 任务列现按真实职责统一显示 `模块 - 任务`（直播、复盘、教程、系统）；字体在 cron 页面约缩小 30%，顶栏/侧栏随当前 cron 页面同步，切回教程或登录不受影响。原 `admin-cron-v3.html` 也同步更新。1440×900 表格已无需横向裁切，2048×1060 的长状态标签不再与下一列碰撞；Chromium 控制台 0 errors，独立 GPT-6 Astra 最终视觉裁定通过。管理前端 **51 passed**，后台构建、ESLint、`git diff --check` 成功；截图保存在忽略的 `output/playwright/cron-compact-*.png`。相关六个文件仅本地提交 `60d157c1`，没有 push、部署或连接远程；本机状态数据仍为合成示例。
- Fan 审核 cron 页面后要求精简顶部状态并解释各任务用途。已按 `claude-design` 落地新 [HTML 设计稿](./slice1/design/admin-cron-v3.html)，再按 `ui-ux-pro-max` 的图标加文字、状态色与深浅主题原则优化；React 顶部改为按异常优先的短状态标签，任务抽屉增加九项任务的用途说明、健康原因、频率、上次运行/成功/耗时及最近错误。状态从现有只读 API 每 15 秒重新采样并派生计数；不是每秒本地计时，也不修改任务。独立 GPT-6 Astra 对设计稿及真实运行截图两次视觉裁定通过。Chromium 暗色 2048×1060、浅色 1440×900 已预览；截图保存在被忽略的 `output/playwright/admin-cron-v3-*.png`。管理前端 50 passed、后台构建、ESLint、`git diff --check` 成功，本次改动仅本地提交 `2a979d01`。九个任务 ID 来自真实 `katrain/cron/scheduler.py`，但当前本机预览的运行时间、错误、计数和部分频率均由 `output/playwright/admin-cron-local-smoke.py` 写入临时 SQLite 合成，不能当成目标环境状态。HTML 设计稿也标明示例数据；没有远程连接、真实库写入、push 或部署。
- Fan 在本机预览指出后台登录卡片及内部页面文字过小。已将登录卡宽度约翻倍至 760px，标题/说明/标签/输入字约放大一倍；管理导航、教程空态、cron 摘要/任务表/历史文字同步放大，并把任务表横向溢出限制在表内。同步更新 `slice1/design/admin-cron-design.html`。本机已重建后台，Chromium 验证浅色 1440×900 登录/教程/cron 与深色 2048×1060 登录/cron；独立 GPT-6 Astra 视觉裁定通过（1440px 任务表右列需横向滚动，非阻断）。`npm test -- src/admin` 为 48 passed，后台构建、`git diff --check` 成功；预览图暂存于被忽略的 `output/playwright/admin-large-*.png`。此调整**仅本地提交 `e91c50e3`**，未 push，未触及远程或真实数据。
- 用户最新权限下，本机 `127.0.0.1` 预览与 Playwright Chromium 均能正常启动；Google Chrome 也已安装。此前“沙箱不允许启动服务/Chromium”只描述旧会话的限制，不适用于当前权限。Playwright CLI 单独禁止 `file:` 导航；通过本地 HTTP 查看设计稿/应用正常。
- cron 已按 `claude-design` HTML → `ui-ux-pro-max` 优化 → 隔离 Fixture → 1440×900 参考/运行/并排/叠加/差异四图推进。独立 GPT-6 Astra 查看两组四图后裁定 **APPROVE FOR LOCAL CONTRACT/BACKEND**，无阻断差异；Fan 明日视觉复核和外部操作授权仍独立。详情见 [设计说明](./slice1/design/design-notes.md) 与 [重排计划](./plan-2026-09-25-admin-cron-rebase.md)。
- 本地 cron 契约、两张 web 建表/cron 同名映射、运行记录器、调度器和 loop 心跳、九态健康函数、三个只读后台 API 及 React 真接口集成均已落盘；`cron` 依赖 extra 加到 pyproject/lock。最终聚焦复核：后端 cron＋鉴权 **90 passed**、相邻教程后台接口 **14 passed**、管理前端 **48 passed**；Black、ESLint、`git diff --check` 均通过。后台、公开 Galaxy、kiosk 2D 构建成功，kiosk 隔离校验通过；后台构建 JS/CSS 不含 Fixture 入口或示例业务值。cron 切片代码／测试／设计证据已**仅本地提交 `f5a9dedc`**，未 push 或部署；本报告仍是工作树改动。
- 真浏览器本地验收使用 `output/playwright/admin-cron-local-smoke.py`：只写 `/private/tmp` 临时 SQLite，合成九项状态和一次成功/吞错/失败记录，由真实专用后台 API + 已构建 React 页面读取；`http://127.0.0.1:8010/admin.html` 登录、切换 cron、异常优先排序、历史抽屉全文、15 秒刷新后抽屉仍开，Chromium 控制台 0 errors。图见 [本地列表](./slice1/design/cron-runtime-local-1440x900.png)、[本地历史](./slice1/design/cron-runtime-local-history-1440x900.png)。它不是目标环境真实 cron 作业或正式部署验收；开发期 Fixture 已删，示例数据仅在测试文件和被 Git 忽略的 smoke 脚本。
- 独立 GPT-6 Astra 的高风险代码复核找到并复现四处边界缺陷，均已加红测后修复：未建 cron 历史表时不再回滚原有清理；60 秒登记等待可响应停止；普通数据库故障不再误报缺表；旧轮询响应不能覆盖新健康状态。没有扩大到与本模块无关的审查。
- 设计稿第一道裁定：独立 Astra 指出并推动修正异常排序、失败次数、历史时间与错误摘要、旧数据采样、加载态及浅色小字对比。设计 HTML 的七张当前 `v2` Chromium 图均为 1440×900、控制台 0 errors / 0 warnings，历史 200 行实测可滚；当时裁定 **APPROVE FOR LOCAL FIXTURE**。随后 Fixture 四图裁定已把本地开发关卡推进至后端，见上方最新记录。设计 HTML 可通过 `http://127.0.0.1:8009/superpowers/tracks/admin-console/slice1/design/admin-cron-design.html?theme=light&state=failed` 查看（需在仓库根目录运行 `python3 -m http.server 8009 --bind 127.0.0.1`）。

- 教程后台在 `feature/admin-console` 的单独提交 `252bffaa` 已快进到本地及远端 `develop`；`smartbox-software/vendor/katrain` 指向该提交，父仓仅本地提交 `41ebfec6`，**未推送**。切片 0 与教程代码都未部署，生产旧 `admin` 仍未处理。
- 本机曾用 `output/playwright/admin-local-smoke.py` 在 `127.0.0.1:8010` 启动独立后台、临时 SQLite 和临时本地媒体存储；用户要求安全暂停时该本地服务已关闭。Chromium 中已有音频及 MP4 均解码并播放至结尾（各 2 秒）；切到无媒体的图显示正确空态；离线合成器经真实后台写接口生成新 MP3，页面随响应显示新音频。1440×900 截图：`output/playwright/admin-local-media-1440x900.png`。这些合成媒体与临时账号仅用于本机预览，**没有测试外部 Edge TTS、真实对象存储或目标环境数据**。
- 新跑后台 Python **36 passed**、公开边界重点 **25 passed**、后台前端 **19 passed**。教程本地集成已有证据，但书/章切换、外部媒体服务、公开成品页另一个 session 的改动与 Fan 最终验收仍待复核；不可标成完成。用户最新指令允许在本地继续 cron 设计与隔离 Fixture，独立 GPT-6 Astra 裁定此仅调整本地开发顺序；SSH、真实库写入、push、部署仍逐项等 Fan 批准。
- 本次另补教程本地交互验收：未保存讲解草稿切换棋图不会串图，写接口返回 401 后退回登录并丢弃本地令牌；`AdminApp.test.tsx` **10 passed**，`tsc -b` 与该文件 ESLint 退出码 0。此检查不代替本机真实浏览器的书/章切换或 Fan 验收。
- 本工作树另有 6 个早期已跟踪 `.playwright-cli` 快照被外部清理为删除状态；本轮未恢复、未暂存、未提交它们。新浏览器快照也不入库。

## 2026-09-25 Git 集成更新（覆盖下文的旧 Git 状态描述）

Fan 已明确要求将当前教程后台工作树改动作为**单独一次提交**合入并推送 `develop`。该提交包含教程后台代码、设计与验收资料、计划/交接更新及 `/output/` 忽略规则；`.playwright-cli` 临时快照不入库。下文“教程草稿未提交/未推送”的句子是这次集成前的历史状态，不再作为后续操作指令。**合入代码不等于教程模块验收或部署**：测试/生产运行服务仍未部署，生产旧 `admin` 尚未处置，cron 尚未开始。`smartbox-software` 父仓的 push 不在本次授权范围。

## 旧停点（历史，不作为当前行动指令）

Fan 已恢复按计划开发。现在停在**切片 0 的下一条逐项写库／部署授权关卡**：测试机旧 `admin` 已获单独批准并撤权、随机化口令，本机和生产仍未处理。切片 0 已按 Fan 的新指令合入并推送 `develop`，但**代码推送不是部署**，测试/生产的运行服务仍待单独批准。教程管理 T4/T5 已有本机隔离数据库的真实 HTTP 浏览器检查，但尚未做测试／生产验收，不继续开发 cron。教程草稿的 Git 状态以本报告顶部更新为准。

后续新增了非绿色主题设计稿 `tutorial-admin-design-v2.html`。Fan 已选 **B「石墨铜」作夜间版、C「雾白蓝」作白天版、楷体作后台界面字体**。这套主题已在本地 `AdminApp.css` 实现，依系统深浅模式自动切换；Mac 优先 `Kaiti SC`，Windows 用 `KaiTi`，其他环境回退仓内 `LXGW WenKai`。本地 React 登录、详情、编辑态的 1440×900 预览及同视口并排/叠加/差异记录见 `tutorial-theme-visual-review.md`；详情/编辑预览用 `output/playwright/admin-theme-preview.mjs` 的临时模拟响应，未写入生产代码或真实数据库。聚焦前端测试 13 passed、`build:admin` 和 ESLint 均通过。**Fan 已确认新版 React 外观，但教程模块尚未验收**；此次确认不授权远程连接、写库、push 或部署。
设计自检：工作台采用 Operate／Inspect 构图，没有营销 hero、假指标、功能卡片网格、玻璃模糊或装饰性渐变；`claude-design` 的十项俗套特征评分 0/10。当前 B/C＋楷体的设计参考及本地 React 登录、详情、编辑三态均在 Chromium 1440×900 检查；详情/编辑使用测试响应，不是实际后端集成验收。

工作树：`/Users/fan/Repositories/katrain-admin-console`；分支：`feature/admin-console`。保留工作树中未跟踪的 `.playwright-cli` 临时快照；不能用 `stash`、`reset --hard` 或 `checkout --` 清掉。

## 计划覆盖与顺序

1. `plan-2026-09-24-tutorial-admin-guard.md`：切片 0，公开入口安全修复与旧 `admin` 撤权/发布。顶部 2026-09-24 修订优先于旧 Task 6–7 的“提升公开用户”文字。
2. `plan-2026-09-24-admin-tutorial-first.md`：后台专用账号与**首个完整模块：教程管理**，T0→T6。它覆盖旧 spec 的共享 `users.is_admin` 鉴权及旧 cron 计划的先后顺序。
3. `plan-2026-09-24-admin-console-cron.md`：旧的后台骨架 + cron 计划；顶部修订注明不得照原 Task 顺序和鉴权部分直接执行。教程完成后只复用 cron 记录器、健康判定、只读接口及仍有效的视觉/发布关卡，按当前基础重排。

三份计划**不覆盖全部未来后台模块**。spec §10 的性能监控、金镜像制品、用户/计费及审计查看、YOLO 数据集、设备页、配置体检、报错/告警仍需各自单独设计和计划；教程已从旧的“后续模块”提前。

依赖链：切片 0 安全发布及旧管理员处置 → 教程专用身份/共享后台骨架/真实集成与验收 → cron 完整垂直切片。三个窗口若共用一个 worktree/分支，会同时改后台 app、模型、前端、compose 和 Git 暂存区/HEAD，也可能把未完成教程代码随切片 0 推上去；**不要并行实施**。可以分三个顺序交接的 CLI session。若只读研究/设计要并行，使用独立 worktree，不越过每个模块的设计稿与四图确认 🛑，也不提前改共享基础。

## 已有成果

- 切片 0 安全提交已通过合并提交 `f0a0b4a9` 追上 `develop`，`origin/feature/admin-console` 与 `origin/develop` 均指向它；合并无文本冲突，相对原 `develop` 仅 20 个切片 0 文件，没有教程后台 Fixture、设计稿或代码。合并结果的聚焦 Python 31 项、前端 5 项、Galaxy 与 kiosk 2D 构建及 kiosk 边界检查通过；预期的 `tests/deploy` 在此仓版本中不存在，未宣称通过。Task 1–5b 已完成；Task 6 中测试机旧 `admin` 已撤权并随机化口令，本机和生产未执行；Task 7 仅代码 push 完成，测试/生产部署和验收均未执行。
- `smartbox-software/vendor/katrain` 已在父仓本地 `main` 上更新到 `f0a0b4a9`，提交 `e9d93193`；没有推送 `smartbox-software`，其原有的 `vendor/hermes-agent` 工作树改动未进提交。教程草稿另有仅本地恢复锚点 `wip/admin-tutorial-handoff-20260924` 的 `4fa7aeb3`，未推送；草稿已重新应用回原工作目录的 `feature/admin-console`，保持未提交。根目录 `/output/` 已加入 `.gitignore`，只影响本地验收产物，不影响服务启动；`.playwright-cli` 的已有临时快照仍未跟踪。
- 教程 Galaxy 风格设计稿、Fixture 的 1440×900 四图已获 Fan 确认；`tutorial-admin-contract.md` 已冻结本地契约。它们和教程计划、代码/截图仅在本地 WIP 恢复锚点中保存，**尚未提交到 feature/admin-console 或推送**。
- 本地教程后台实现了独立管理进程/专用 `admin:fan` 身份、登录与写入审计、真实教程读写、并发版本检查、音频/训练样本状态、前端真实 API 集成、Fixture 删除及公开管理员写路由退役。Docker/compose 的本地配置也已调整；没有运行真实数据库迁移或任何远程操作。
- 先前聚焦验证记录为后台及相关公开路由 Python **158 passed**。本次新跑：后台 Python **40 passed**，公开鉴权／教程／计费回归 **122 passed**；并发修正后管理前端 **19 passed**、教程写接口 **13 passed**、`build:admin`、管理前端 ESLint、改动 Python 文件 Black 检查和 `git diff --check` 通过。原 Galaxy 构建、kiosk 构建及隔离校验曾在本次前半程通过，最新修正后未重跑这些非直接相关项。全量 web suite 未宣称通过；本地环境缺 `cv2`，训练导出的正向 OpenCV 路径未实跑。
- 接入新版 `develop` 后，教程工作区的后台 Python **36 passed**、公开鉴权／教程／设备／计费重点回归 **23 passed**、后台前端 **19 passed**，后台、Galaxy、kiosk 2D 三套构建和 kiosk 边界检查通过；这些检查只证明本机组合结果，不构成教程模块验收。
- 本次用 `output/playwright/admin-local-smoke.py` 在临时 SQLite 中建立独立教材，`127.0.0.1:8010` 独立进程提供已构建后台，并在 Chromium 1440×900 真实 HTTP 中验证专用账号登录、读教材和讲解保存；双标签实测 409 后草稿保留、读取服务器版本、核对后重试成功；无效令牌的写请求返回 401 并回到登录。冲突态截图在 `output/playwright/admin-runtime-local-conflict-1440x900.png`。这是隔离测试数据，不是真实环境验收；浏览器尚未做实际 TTS 和音视频播放。
- 由这些检查发现并修复：409 后原无读取服务器版本入口；`board_payload=NULL` 时工作台不显示；空小节无提示；旧视频在棋图／讲解／语音更新后仍被当作成品显示；原“预检查”并未实际检查。后续聚焦复核又发现三项数据风险，均经测试先红后绿：409 刷新后整份旧草稿可能覆盖另一会话独立修改的字段，现按字段重基，双方改同一字段时保存被阻止直到显式确认；仅编辑空棋盘图的讲解可能误创建空盘，现仅显式“编辑棋图”可初始化；失效视频引用时旧时长和大小仍残留，现同事务清空。
- Fan 先明确授权**一次测试机只读 SSH 复核**；`home-ubuntu` 的 `katrain_db` 当时返回 `1|admin|t`。随后 Fan 单独确认了测试机这一条写库命令：在 `katrain-web` 容器内先核对 `current_database()='katrain_db'`、`users.id=1`、用户名 `admin` 与 `is_admin=True`，再在同一事务中将 `is_admin=False`、密码哈希换为不可恢复随机口令。命令退出码 0，写后打印 `katrain_db 1 admin False password_hash_changed`；没有打印口令或哈希。没有连接生产机，下一条远程／写库命令仍须单独批准。
- 发现 `.agents`、`.claude`、`.gemini` 的 `tutorial-data-sync` 旧流程会 `TRUNCATE` 教程表和棋图历史，覆盖后台编辑，而原备份不含历史、计数核对不检测内容差异。三份技能已一致标注停用并移除可直接执行的全表导入命令；未来新增教材须另定按范围核差、冲突拒绝及完整备份恢复演练。不曾执行旧同步。

## 下一 session 的安全起点（2026-09-25 更新）

1. 读 `CLAUDE.md`、`codex-handoff.md` 顶部修订、三份旧计划的最新修订、[cron 重排计划](./plan-2026-09-25-admin-cron-rebase.md)、[cron 契约](./slice1/cron-contract.md) 和本报告；先看 `git status`，保留已有 `.playwright-cli` 删除及未跟踪状态，**不要清理/恢复/一并暂存**。cron 四个提交已推送到 `origin/feature/admin-console` 的 `60d157c1`；本报告、教程聚焦测试及此前教程相关文档更新属于后续本地更改，尚未 push。
2. cron 本地代码与合成数据浏览器验收已做；Fan 明日可看 [设计说明及四图](./slice1/design/design-notes.md)，并启动 `output/playwright/admin-cron-local-smoke.py` 于 `127.0.0.1:8010` 看真实 API 后台（本机临时库）。独立 Astra 的视觉通过不替代 Fan 意见；若 Fan 指出差异先改。
3. 后续仍需明确标注：未用实际目标环境的 web/cron/admin 三服务和真实任务验收，未运行外部 API/TTS，未验证测试/生产部署。不要把本机临时 SQLite 的通过写成生产可用。教程模块仍有真实媒体服务和 Fan 最终验收待办，切片 0 安全补丁仍未部署。
4. 🛑 后续再次 push，以及进入远程、目标库写入、测试/生产部署前，每项当场请 Fan 批准；此前可做本地代码检查和只读计划核对。`smartbox-software` 父仓子模块指针仅本地提交，未获得父仓 push 授权。
