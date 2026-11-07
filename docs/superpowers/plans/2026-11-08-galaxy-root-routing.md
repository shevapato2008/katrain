# Galaxy Root Routing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 正式域名 `https://modelstella.com/` 和测试域名 `https://go.sailorvoyage.top/` 原址显示 Galaxy；全部 Galaxy 导航和深链接移到根命名空间，取消旧 `/galaxy` 和 `/galaxy/*` 入口，并按用户指定顺序发布到云端与 RK3562。

**Architecture:** 将现有 Galaxy 应用挂到根路径，保留其相对声明的子路由，定点迁移绝对页面 URL。FastAPI 仅为已知 Galaxy 页面命名空间提供 SPA HTML，其余请求继续使用现有 API、WebSocket、资源和静态文件处理，旧 Galaxy 前缀返回 404。Kiosk 仍挂载在 `/kiosk`，设备构建不包含 Galaxy 或 three.js；不增加代理重写、路由抽象框架或业务数据迁移。

**Tech Stack:** React 19, React Router DOM 6.30.3, Vite 8, Vitest, Playwright, FastAPI/Starlette, pytest, existing Docker/native systemd deployment tooling.

---

## Chunk 1: Contract, implementation, verification and release

### Confirmed requirements and evidence

- 用户明确选择“保持根地址，旧 `/galaxy/` 链接直接取消”，不保留旧链接 alias、301/302/307/308 或客户端兼容跳转。
- 用户明确要求：先写计划，由 Astra Max 独立代理审核、修改最多两轮；计划通过后用 `subagent-driven-development` 并行开发；最后用独立 Astra Max 审核代码，修复直至通过。
- 用户已授权发布顺序：当前分支追最新 develop、解决冲突并 push；merge/push develop；更新并 push `smartbox-software` main 的 `vendor/katrain` gitlink；部署 TEST、PROD、RK3562。
- 起点：干净的专用 worktree `/Users/fan/Repositories/katrain-kiosk-debug`，当前分支 `fix/kiosk-ui-debug`，`origin/develop` / HEAD 在编写计划时为 `09c2a167151e1e363e520785adfa3e885ac71420`。当前 worktree 已提供隔离，无需再复制开发环境。
- `AppRouter.tsx` 目前将 `/galaxy/*` 交给 Galaxy，根 `/*` 交给废弃的 `ZenModeApp`。`GalaxyApp.tsx` 内的路由已是相对路径；真正迁移对象主要是 URL 字符串，而非模块目录。
- `server.py:4587` 仅为旧 `/galaxy` 前缀提供深链接 HTML；根 `StaticFiles(html=True)` 不会为 `/play`、`/kifu/7/replay` 等页面提供 SPA fallback。仅改前端会造成刷新 404。
- 还有 3 处多人离开/判负 API 返回 `/galaxy/play/human`；`index.html` 和 `vite.config.ts` 的棋谱提前请求/模块预加载也依赖旧前缀。
- 只读 HTTP 检查：两域名 `/` 和 `/galaxy/` 目前均返回 200；根 HTML 缺少现有 Galaxy 路径的 `Cache-Control: no-cache`。
- 只读 Nginx 检查：PROD `modelstella.com` / `www.modelstella.com` 的通用 `/` 已代理 `127.0.0.1:8001`；TEST gateway 的通用 `/` 已代理 `katrain_go`，均无 `/galaxy` 重写。`/media/`、TEST `/docs/`、`/chess-kifu` 和其他棋类 API 的现有专属 location 必须保持；本次无需更改 Nginx。
- `ssh -G ucloud-v100` 已核实为当前 PROD `ubuntu@117.50.177.254`，不连接废弃 183 主机；TEST `home-ubuntu`；RK `rk3562-local` 为 `root@192.168.0.104`，实测 hostname `gzpeite`、RK3562 P04。
- 补充只读快照：两云现役 Web revision 都是 `f51fdec3ba476946d451f27cadb982d9343e1cb8`。RK stamp 的 KaTrain 是 `09c2a167151e1e363e520785adfa3e885ac71420`，main `be70d25c5334530fdd0f0cac540e0e865d2bee72`；原模式 Hermes，但唯一 page 实际在 `http://127.0.0.1:8080/launcher`，KaTrain WorkingDirectory `/root/smartbox-software/vendor/katrain`、端口8081、Go target inactive，eMMC空闲1,665,290,240 bytes。部署时全部重新读取，不能使用快照作为CAS输入。
- 已查询 Context7 的 React Router 6.30.3 文档：根 `/*` 支持后代 `Routes` 的相对匹配；index route 在父路径显示，不需要重写全部路由声明。

### URL and ownership contract

| 页面 | 新公开路径 | 旧路径处理 |
| --- | --- | --- |
| 首页 | `/` | `/galaxy`、`/galaxy/` 返回 404 |
| 对局 | `/play`、`/play/ai`、`/play/game/:sessionId`、`/play/human`、`/play/human/room/:sessionId` | 对应 `/galaxy/*` 取消 |
| 研究、会员 | `/research`、`/membership` | 同上 |
| 报告 | `/report`、`/report/:taskId` | 同上 |
| 棋谱 | `/kifu`、`/kifu/:albumId/replay`、`/kifu/:albumId/report` | 同上 |
| 直播 | `/live`、`/live/:matchId` | 同上 |
| 死活题 | `/tsumego` 及现有层级/题目路径 | 同上 |
| 教程 | `/tutorials` 及现有分类、book、section 路径 | 同上 |
| Kiosk | 原 `/kiosk` 和 `/kiosk/*` | 保持原路径 |
| 独立资源/协议 | `/record`、API、WebSocket、静态资源、代理专属路径 | 保持现有权威边界 |

直接打开、刷新、站内导航、返回、query/hash 都必须保持新 URL，不能重新产生 `/galaxy`。目录名 `src/galaxy`、模块 import、CSS 类、API 中的业务名 galaxy、历史设计/审核证据不重命名、不机械替换。生产 HTTP 的旧路径必须真实 404；Vite 开发模式收到 HTML 的旧路径也必须停留在原 URL 显示简洁 404，不经 Galaxy wildcard 导回首页。未知非页面命名空间及缺失 API/资源不可返回 SPA HTML。

### Parallel ownership and review gates

四个实现任务共享上述稳定 URL 契约，互不编辑对方文件。用户明确要求并行，覆盖技能中默认串行建议；任务完成前不集成未稳定业务状态。所有 worker 使用提供的任务全文，先写并运行有意义的失败测试再修改实现；只提交自己拥有的文件。控制器串行处理 Git 提交和集成，worker 不同时操作 index/commit。一个独立规格代理核对四个任务的契约，再由一个新的 Astra Max 代理独立审核完整 diff；不为机械 URL 迁移逐文件重复建立审计层。

### Task 0: Plan gate — controller and independent Astra Max

**Files:**
- Create/maintain: `docs/superpowers/plans/2026-11-08-galaxy-root-routing.md`
- Create review record: `docs/superpowers/reviews/2026-11-08-galaxy-root-plan-astra-max.md`

- [ ] 将本计划交给 `gpt-6-astra` / `max`、`fork_turns=none` 的独立代理，提供用户需求与本文件、仓库路径，不继承会话推理。要求验证路由完整性、静态/API 边界、Kiosk、预加载、并行文件归属及发布可执行性。
- [ ] 控制器修正审核发现，最多两轮审核/修改；若两轮后仍有阻塞，记录具体问题并停止代码阶段，向用户报告，不自行增加审核轮数。
- [ ] 审核通过后保存精简结论并提交计划文档。用户已授权按计划继续执行，不再重复请求“是否开始开发”。

### Task 1: Root app shell and navigation — worker A

**Files owned:**
- Modify: `katrain/web/ui/src/AppRouter.tsx`, `katrain/web/ui/src/GalaxyApp.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/{galaxyNavigation.tsx,GalaxyTopBar.tsx,GalaxySidebar.tsx,PlayPageLayout.tsx}`
- Modify corresponding existing tests: `GalaxyTopBar.test.tsx`, `GalaxySidebar.test.tsx`, `GalaxyBottomNav.test.tsx`, `useGalaxySidebar.test.tsx`, `ContentPageHeader.test.tsx`, `ModulePlate.test.tsx` under that layout directory
- Modify: `katrain/web/ui/src/galaxy/components/guards/{AuthGuard.tsx,AuthGuard.test.tsx}`
- Create: `katrain/web/ui/src/AppRouter.test.tsx`, `katrain/web/ui/src/galaxy/components/layout/galaxyNavigation.test.tsx`

- [ ] 测试真实 AppRouter 的根首页选择（可 mock 页面与 provider，保留真实 router 语义）、根深链接、旧 `/galaxy` 的拒绝、Kiosk、`/record`；为不同编译常量建立必要的模块隔离，不能只验证静态源码字符串。测试 navigation 首页仅 `/` 选中，不误选所有路径。
- [ ] Run from `katrain/web/ui`: `npm test -- src/AppRouter.test.tsx src/galaxy/components/layout/galaxyNavigation.test.tsx`。修改前根首页应错误进入旧应用或旧前缀仍可用。
- [ ] 全量构建将 GalaxyApp 挂在根 `/*`，移除 AppRouter 对 ZenModeApp 的默认加载及旧 Galaxy 路由。Kiosk-only 构建根 fallback 导向 `/kiosk`（严格 SSO 行为保留），不加载 Galaxy/旧版 Zen；源码文件不删除。
- [ ] GalaxyApp 未匹配路径不再 `<Navigate to="/galaxy">`，使用最小 404 展示而非兼容跳转；避免为此设计新页面。现有相对子路由保持。
- [ ] 导航项 home 改 `/`、其他项去 `/galaxy`；`isGalaxyNavigationActive` 的 home 分支改为严格等于 `/`。品牌点击、sidebar home、面包屑、AuthGuard 的 `accessMetadata[feature].backPath` 直接使用根路径，防止空字符串/双斜杠。
- [ ] 更新所有本任务拥有的运行测试 URL，运行新增测试及 layout/guard 测试。报告改动列表与 RED/GREEN 结果；交控制器提交 `serve Galaxy from root routes`。

### Task 2: All page links and return paths — worker B

**Files owned (all under `katrain/web/ui/src/`):**
- `galaxy/pages/{Dashboard,PlayMenu,AiSetupPage,GamePage,HvHLobbyPage,GameRoomPage,ResearchPage,KifuLibraryPage,KifuReportDetailPage,TsumegoLevelsPage,TsumegoCategoriesPage,TsumegoUnitsPage,TsumegoListPage,TsumegoProblemPage}.tsx`
- `galaxy/pages/live/{LivePage,LiveMatchPage}.tsx`
- `galaxy/pages/tutorials/{TutorialLandingPage,TutorialBooksPage,TutorialBookDetailPage,TutorialFigurePage}.tsx`
- `galaxy/pages/report/{ReportsPage,ReportDetailPage}.tsx`
- `components/live/MatchCard.tsx`
- Existing tests adjacent to these pages: `PlayMenu.test.tsx`, `AiSetupPage.test.tsx`, `GamePage.aiLadder.test.tsx`, `HvHLobbyPage.test.tsx`, `GameRoomPage.test.tsx`, `ResearchPage.test.tsx`, `KifuLibraryPage.localization.test.tsx`, `KifuReportDetailPage.test.tsx`, `live/LiveMatchPage.test.tsx`, `report/{ReportsPage,ReportDetailPage}.test.tsx`, `membership/{MembershipPage,MembershipNavigation}.test.tsx`
- Any new focused click-to-URL tests must remain in these owned page directories.

- [ ] 先将现有页面行为测试的期望位置改为新路径，选择 PlayMenu、入房和棋谱/报告返回的测试运行，确认实现仍产生旧前缀而失败。
- [ ] 定点更新 navigate、backTo、parentTo、Dashboard 卡片以及动态模板 URL，保留 session/album/task IDs、query、hash 和现有导航离局守卫。共享 MatchCard 仍只在无 onSelect 时进入 Galaxy 直播，不能给 Kiosk 引入 Galaxy 模块或直播 API。
- [ ] 相应更新本任务测试的 initialEntries、Route path、期望地址，不能把 `../galaxy/` 模块 import 或模型/业务标识替换为根路径。不改变权限、支付或对局逻辑。
- [ ] Run: `npm test -- src/galaxy/pages`；共享 MatchCard 由现有 LivePage/列表行为测试验证，确有缺口才新增小型点击测试。所有这次 URL 相关测试应通过；确认为既有的失败需用基线复现而非重写无关业务。
- [ ] 交控制器文件清单及测试结果，提交 `move Galaxy navigation to domain root`。

### Task 3: HTML/bootstrap/build and browser journeys — worker C

**Files owned:**
- Modify: `katrain/web/ui/index.html`, `katrain/web/ui/vite.config.ts`, `katrain/web/ui/playwright.visual.config.ts`, `katrain/web/ui/scripts/verify-kiosk.sh`
- Modify active E2E URLs: `katrain/web/ui/tests/{galaxy-live-template,galaxy-play-record-entry-visual,membership-i18n,galaxy-ai-ladder-active-game-visual,tutorial,galaxy-ai-ladder-game-visual,galaxy-report-tabs-visual,ladder-geometry,report-v2,membership-recharge,galaxy-ai-ladder-setup-visual,galaxy-ai-ladder-blocking-exits-visual,kiosk-ai-ladder-cross-device-semantics}.spec.ts`
- Create focused tests: `katrain/web/ui/src/galaxy-root-bootstrap.test.ts`, `katrain/web/ui/tests/galaxy-root-routing.spec.ts`

- [ ] 为 HTML bounded kifu request 的实际内联脚本编写小型运行测试：`/kifu`（含 query/尾斜杠）和 `/kiosk/kifu` 提前请求一次并保留参数；`/galaxy/kifu`、详情页、`/api/...`、首页不请求。修改前 `/kifu` 应失败。
- [ ] 将 `index.html` matcher 改为 `/^\/(?:kiosk\/)?kifu\/?$/`。模块预加载保留 surfaces 的 galaxy/kiosk 构建名字，以 pathname 的精确 `/kifu[/]` 映射 galaxy，`/kiosk/kifu[/]` 映射 kiosk；不按旧前缀识别。验证生成 HTML 的脚本实际执行，不只改正则文本。
- [ ] Visual webServer readiness 改 `/play`；更新上列浏览器用例和转义 URL 正则。保持 HTTP API、mock payload、测试标题和视觉基准不变，不重拍全部截图。
- [ ] 修正 Kiosk build guard：旧 `/galaxy/` 文字已不再能证明 Galaxy 被 DCE；保留 three/live 检查，补充检查输出中不存在 GalaxyApp/Galaxy 页 chunk（或稳定的构建 manifest/模块特征），以及严格 SSO token guard。不要粗暴拒绝合法 `/kiosk/play`、API URL 或共享组件名。
- [ ] 浏览器回归覆盖：根首页且地址栏不跳转、点击主导航到 `/play` 或 `/kifu`、深链接刷新、带 query 的会员或棋谱页面、返回首页、旧 URL 不进入首页；Kiosk 在 `/kiosk`。真实 HTTP 404 由 Task 4 及最终真实服务器验证，Vite SPA fallback 的 200 不冒充生产 404。
- [ ] Run `npm test -- src/galaxy-root-bootstrap.test.ts`；完成联调后控制器运行该 E2E。移交控制器提交 `update Galaxy bootstrap and route checks`。worker 不与控制器并行执行会覆盖 static 的生产 build。

### Task 4: Server SPA route ownership and API-generated URLs — worker D

**Files owned:**
- Modify: `katrain/web/server.py`
- Create: `tests/web_ui/test_spa_routes.py`
- Extend existing test: `tests/web_ui/test_game_termination_and_chat_identity.py` (only redirect expectations)

- [ ] 使用临时静态 fixture / 无生命周期 ASGI 客户端测试页面路由，禁止启动引擎、写真实数据库或依赖某次本机构建；优先沿用现有 create_app 测试接缝，不为本次加通用路由框架。
- [ ] 新测试：`/`、上述各页面根和代表性动态深链接（`/play/human/room/session`、`/kifu/7/replay`、`/report/7`、`/tutorials/book/7`）返回同一 index HTML + `Cache-Control: no-cache`，query 不丢失；非根页面同时覆盖无尾斜杠和有尾斜杠，禁用自动跟随重定向，不能依靠 Starlette 自动补斜杠；`/kiosk`、`/record` 仍可用。
- [ ] 阴性/正性对照：`/galaxy`、`/galaxy/`、`/galaxy/kifu`、未知顶级路径、已知模块内无效深路径（如 `/play/not-a-page`、`/kifu/7/not-a-page`）、缺失 JS 404；存在的 JS/CSS、资源原样返回；缺失 `/api/v1/...` 保持 JSON 404，不变成 HTML，现有健康和 OpenAPI 端点仍由其原 handler 处理。页面 GET 与 HEAD 均 200、同样 no-cache/content-type，HEAD body 为空；旧路径 GET/HEAD 均 404 且无 Location，不引入路径穿越或任意文件 fallback。
- [ ] Run `.venv/bin/python -m pytest tests/web_ui/test_spa_routes.py -q`，确认新根深链接先失败。
- [ ] 以现有 FileResponse/no-cache 方式为上表及 GalaxyApp 当前声明的**精确页面模式**注册 SPA handlers：`/`、`/play`、`/play/ai`、`/play/game/{session_id}`、`/play/human`、`/play/human/room/{session_id}`、`/research`、`/membership`、`/report`、`/report/{task_id}`、`/kifu`、`/kifu/{album_id}/replay`、`/kifu/{album_id}/report`、`/live`、`/live/{match_id}`、`/tsumego`、`/tsumego/problem/{problem_id}`、`/tsumego/{level}`、`/tsumego/{level}/{category}`、`/tsumego/{level}/{category}/{unit}`、`/tutorials`、`/tutorials/book/{book_id}`、`/tutorials/section/{section_id}`、`/tutorials/{category}`。静态更具体模式在宽泛参数模式之前；参数不引入比前端更宽的跨段匹配。使用局部 tuple 加 `app.add_api_route` 或简洁现有 decorators 即可，不建通用注册框架。
- [ ] 每个精确页面模式显式 `methods=["GET", "HEAD"]`、`include_in_schema=False`；除 `/` 本身外同时注册 `pattern` 与 `pattern + "/"`，返回同一个 FileResponse，保持地址不重定向。移除旧 `/galaxy` handlers，页面模式仍在最终 StaticFiles mount 前注册；不得添加 `/{full_path:path}` 或 `/play/{full_path:path}` 等 HTML fallback。保留 board 模式 static-kiosk-2d 选择、原 Kiosk handler 与 strict root 导向 Kiosk 的语义；不向 board bundle 引入 Galaxy。保留 `tests/test_ws_route_order.py`，新增 HTTP 测试可参考 `tests/web_ui/test_guest_bootstrap_route.py` 的轻量装配。
- [ ] 3 处多人退出返回地址统一 `/play/human`；为 left、已终局与首次 forfeit 三支断言相同新 URL，保留身份与终局权限检查。
- [ ] Run focused Python routing and termination tests；交控制器提交 `serve root Galaxy deep links and retire old prefix`。

### Task 5: Integrated verification and independent review — controller

**Files:** four workers' changes; review record `docs/superpowers/reviews/2026-11-08-galaxy-root-code-astra-max.md`.

- [ ] 只在计划审核通过后并行派发 A/B/C/D；记录文件 ownership，禁止 worker 运行 release、push、全局 clean 或回退别人的文件。控制器逐个检查 diff、提交，仅将测试/代码实际达到的步骤标完成。
- [ ] 用 `rg -n '/galaxy|galaxy\|kiosk'` 重新检查活跃源码、入口、构建配置及 E2E；逐项区分 HTTP URL 与模块 import、业务类名、历史注释。不要求全仓历史文档清零；所有运行时导航旧 URL 必须清零，拒绝旧路径的测试可保留。
- [ ] Run UI root/navigation/bootstrap/全部 Galaxy page 用例，加共享 MatchCard 的相关现有用例及受影响 shared hook suites。Run Python `tests/web_ui/test_spa_routes.py` 和 termination focused tests；失败仅追查当前改动及直接回归。
- [ ] Run full `npm run build`，再 `npm run build:smartbox-kiosk-2d`（顺序执行），确认 TypeScript、生产打包、no-three/Galaxy/live 和严格 SSO guard 通过。不重复做无关全量后端测试。
- [ ] 在专用端口运行本 worktree frontend 的 `tests/galaxy-root-routing.spec.ts`，并用实际 FastAPI 静态服务核对 HTTP 深链接和旧 URL 404。采用一个桌面真实预览和 RK3562 已授权验收，不开展全状态视觉重拍；本次不改变视觉布局，无 fixture 后端集成门槛。
- [ ] 独立规格代理先审阅完整需求/Task 1–4 的 diff 与测试证据，修复缺漏后再进入质量审核。
- [ ] 新建 Astra Max (`gpt-6-astra`, `max`, `fork_turns=none`) 独立代理审阅全部实现及发布计划，提供 base/head SHA、计划、验证结果及边界要求，不继承控制器推理。发现缺陷交原 owner 修复、补必要测试，再送审直到 APPROVED；最终必须明确无未解决的 blocking/important findings。
- [ ] 审核通过后的代码变更需要重新验证并重新审核相关 diff。`git diff --check` 通过，记录精简审核/验证事实，不把未执行设备/线上步骤写成通过。

### Task 6: Publish in the required order — controller only

**Files/repos:** current feature branch; `develop`; `/Users/fan/Repositories/smartbox-software` main gitlink; release receipt `docs/operations/galaxy-root-routing-release-2026-11-08.md`.

- [ ] 先 `git fetch origin`，把最新 `origin/develop` merge 到当前 `fix/kiosk-ui-debug`；有冲突按新根 URL 契约逐项解决。若集成引入新相关改动，运行受影响测试并送 Astra 复核；提交并 push 当前分支，不 force push。
- [ ] 在干净的集成 worktree 合并当前功能分支到最新 develop，完成必要验证后 push develop；确认远端确切 SHA。保留现有 develop worktree 的无关工作。
- [ ] 读父仓 AGENTS，检查 main 的远端与工作区。使用干净父 main 发布 worktree 将 `vendor/katrain` gitlink 更新到已发布 develop，单独提交并 push main；不夹带父仓其他改动，不 reset 开发者工作区。确认 published parent/main 与 gitlink。
- [ ] 从**已发布 commit 的 git archive / 干净发布 checkout**重新构建 full static 与 strict Kiosk，不从本开发 worktree 复制 ignored static。Cloud candidate 用每端现役 immutable image 为基底，仅覆盖本次已审核 runtime 差量（包括新 `server.py`，不能仅替换 frontend）和完整新 static；比较现役 build SHA 到发布 SHA 的 runtime 差量、依赖及挂载覆盖，不能丢掉现役修复或伪称整个 overlay 基底都等于新源码。记录 source manifest、OCI revision、asset hash 和 immutable candidate image。
- [ ] 按 `.agents/skills/server-deploy/SKILL.md` 捕获 TEST/PROD 实际 Web 的私有 beforeimage、镜像、挂载、网络、资源与角色配置。固定复用已验证的 native helper：TEST `/tmp/membership-i18n-release-959800a467/native-release.py`，PROD `/var/tmp/membership-i18n-release-959800a467/native-release.py`；每次执行前 SHA256 必须为 `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`。不使用硬编码旧容器数量/ID的 October kifu operator。helper 不负责非 Web 容器核验，由控制器捕获所有非 Web 的完整 ID、image、StartedAt、restart count、state 并发布后逐项比较；Cron/GPU/DB/MinIO 不重启。
- [ ] 在每端新建 mode0700 release 私有目录，私下从新鲜 live Env 提取 helper 要求的六个 allowlisted 配置到 mode0600 `env.json`：`KATRAIN_ENVIRONMENT`、`MEMBERSHIP_MODE`、`BILLING_ENFORCED`、`PAYMENTS_MODE`、`FREE_WEEKLY_REPORTS`、`MEMBERSHIP_MAX_SALE_ENABLED`，逐项验证与原值一致及角色正确。不能用空 JSON 或只含 build SHA；helper 自行设置新 `KATRAIN_BUILD_SHA`。不打印环境或 DSN。
- [ ] 运行 `python3 HELPER prepare --container NAME --image CANDIDATE_IMAGE_ID --sha RELEASE_SHA --env-json PRIVATE/env.json --manifest PRIVATE/manifest.json --rollback-compatible`，PROD 前置 `sudo -n`。这里 HELPER/NAME 分别固定为上述路径、TEST `katrain-web` / PROD `katrain-ucloud-katrain-web-1`，SHA/镜像/manifest 摘要由实际已发布产物填充，不能传分支名或 mutable image tag。检查 metadata receipt 和允许的配置差量。
- [ ] 切换前刷新 live full ID/image，确认与 prepare 捕获值及活动会话闸一致；然后 `python3 HELPER apply --manifest PRIVATE/manifest.json --manifest-sha256 MANIFEST_SHA256 --expected-old-id LIVE_FULL_ID --expected-old-image LIVE_IMAGE_ID --receipt PRIVATE/apply.jsonl --rollback-compatible --stop-timeout 180 --health-timeout 180`（PROD `sudo -n`）。helper 保留 stopped old backup 并在 apply 失败时做兼容自动恢复；失败后先看 receipt/实际 ID，不能盲目重试。
- [ ] 上线后控制器发现不合格时，先重新核对 operation label 和实际 old/new full IDs、无在用真人棋局；正常停止候选 full ID、改名为独立 failed backup、把原 stopped backup full ID 改回服务名并启动；复核原 config/health/assets 和全部非 Web 不变。helper 无 rollback 子命令，不编造调用，也不删除候选或原备份。先 TEST 完成根首页/深链接/旧路径404/Kiosk 验收再 PROD；根地址无 Location、HTML no-cache，实际 JS/CSS hash 与包一致。
- [ ] 无需新增或修改 Nginx；发布前后核对现有专属 location 仍优先，若实际配置已变化，先停止应用该主机并查明，不用猜测性 rewrite 覆盖。
- [ ] RK3562 固定使用下面的 **KaTrain-only 有界替换配方**，不是 parent app/full push。存储依据是**父仓** `docs/rk3562-deployment-storage.md`；历史增量参考是**KaTrain 仓库** `docs/design/local-confirm-2026-10-11/RELEASE-DECISION.md`，其旧路径/旧 hash 不直接使用。发布包来自已 push 父 main/gitlink 的 immutable archive，包含审核过的 KaTrain runtime 差量、完整普通 static、完整 strict static-kiosk-2d 和仅包含这次 KaTrain 事实的独立 release manifest；不伪造四棋全量 `.smartbox-release.json`。
- [ ] RK preflight：验证 SSH 地址/hostname；从 `systemctl show` 的实际 WorkingDirectory/ExecStart 确认 KaTrain 根和 Python，不打印 Env；读取原 target/members、原 setup 活动状态、唯一现有 CDP page id/精确 URL、Go session/vision 绑定事实。未结束真人局/页面游戏状态不明时只准备 staging，不停服、不结束棋局。核对当前模式，不能因 KaTrain inactive 就认定全设备 idle。
- [ ] 在 eMMC `/var/lib/smartbox/deployments/galaxy-root-RELEASE_SHA/` 建0700目录，先预算 incoming + 原文件/两静态备份 + 原子替换临时空间 + 1GiB余量，确认不落TF。复制候选到 incoming 并验证所有 manifest hash；以 fresh inode 的备份保存将变更的原文件、文件不存在标志、属主/权限、旧两静态目录和原版本事实；不碰数据库、身份、标定、引擎/venv/unit配置。
- [ ] 有界维护实现复用父仓 `scripts/rk3562_deploy.py` 的 `Runtime`（仅 Runtime，不调用 broad `Files`/`Transaction`/`board_deploy`）：使用其从真实 setup service config 解析的 mode registry/CDP/`LAUNCHER_LOCK_PATH`；按既有 `O_CREAT|O_EXCL` JSON lock 协议取得锁，15秒刷新timestamp；`Runtime.capture` 再核对模式/page 与 preflight 一致，既有 page 导到 about:blank。仅在安全空闲的维护窗口按真实 target/member 互斥停止原模式并确认 cgroup释放；不会直接启动API绕过target，不停常驻gateway/setup。
- [ ] 每个 runtime 文件先复制到目标同目录临时文件、校验/设置原属主权限后 `os.replace`，禁止原位覆写共享 inode；源码根不 `--delete`。两静态目录按“原目录原地 rename 到 eMMC 备份 → incoming 普通目录 rename 到原路径”的顺序发布，静态才允许精确替换；提交 manifest 最后。每一步写私有进度receipt，保留失败文件，确保中断后可辨认 old/new。
- [ ] 通过 `Runtime.start('go')` 启动Go target并核对成员、KataGo ready、KaTrain8081 health与双静态hash；用原 page 验证strict `/` 到 `/kiosk`及代表性页。成功后停止验收Go target并等cgroup释放，再恢复原模式target（原idle则不启动模式）与同一page的精确原URL；最后复查模式/URL一致再删除自己创建的lock。原模式为Go时保持已升级Go并恢复其精确原URL。
- [ ] 设备任一写入/验收失败：停止验收Go并确认释放；按receipt倒序还原原文件/权限/不存在标志及两静态目录/旧manifest，校验旧hash；再通过target恢复原模式与同一page精确URL。恢复失败则保持相应模式停止、保留lock/现场并明确报错，不能报告成功或自动结束已有局。
- [ ] 控制器在实施阶段将上述有界操作准备为一次性 `output/releases/galaxy-root-20261108/rk-katrain-only.py`，复用已找到的 `/Users/fan/Repositories/katrain-kiosk-local-play/output/rk-local-prestart/release/rk/rk_release.py`（现有源SHA256 `6457c91375de4bec7dc8a97e7e40e99eb7e448edeb1d84cb1bd85d322cf1e135`）的hash校验、原文件备份/absence恢复和同目录原子替换机制，加上前述当前Runtime锁/target/page流程；不能原样执行其直接启动KaTrain且不恢复模式的旧分支。该一次性脚本在最终Astra审核中一并提供源码/hash；先在临时目录验证before-hash不符拒绝、原子替换、失败恢复hash/absence，再执行 `python3 -m py_compile`，不以编译通过代替恢复测试。不新增通用发布平台，不修改父仓部署工具。
- [ ] 设备验收通过实际 Go target：KataGo ready、KaTrain health、`/` 在 strict build 导向 `/kiosk`，现有 `/kiosk` 和代表性棋谱页可用；API 地址不变。只在必要窗口切换模式并恢复原模式和精确 URL。记录实际部署的父/main、KaTrain SHA 与 build manifest，不把云端 Galaxy 首页替换为盒子默认界面。
- [ ] 发布回执列出 feature/develop/parent-main 的 published SHA、TEST/PROD 镜像与健康、两个根域名及旧链接的真实 HTTP/浏览器结果、RK3562 版本/服务/页面验收和回退位置。任一步失败如实记录，不能把部分发布称为全部完成。

### Acceptance checklist

- [ ] TEST、PROD `/` 原址显示 Galaxy；所有当前导航/生成 URL 无 `/galaxy` 前缀。
- [ ] 新页面可直接打开和刷新，query/hash 正常，旧 `/galaxy` 及子路径真实 404 且无兼容跳转。
- [ ] 原首页不再加载 ZenModeApp/创建旧首页会话；Kiosk、API、WebSocket、媒体/静态及其他代理入口保持各自行为。
- [ ] 棋谱提前请求和模块预加载支持新 `/kifu`；严格 Kiosk 仍无 Galaxy/three/live/token 泄漏路径。
- [ ] 计划审阅不超过两轮；独立规格检查与最终独立 Astra Max 代码审核通过。
- [ ] 按四步发布顺序完成三处 Git 发布和 TEST、PROD、RK3562 的真实验收。
