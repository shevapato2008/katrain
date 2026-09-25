# 性能监控入口 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan in the current worktree. Steps use checkbox (`- [ ]`) syntax for tracking. Fan 指定逐模块推进，勿另开 worktree。

**Goal:** 为后台性能监控模块先完成诚实的访问入口和设计/Fixture 验证；真实监控接入前不宣称模块完成。

**Architecture:** 保留现有后台的 Bearer 登录与 B/C 楷体壳层。设计稿与 Fixture 只用明确标记的未接入、已配置示意状态；正式版必须由服务器可信配置和实际可达性决定，不从前端构造“在线”状态。首个真实旅程是管理员经既有 SSH 隧道打开后台，再进入独立转发的监控面板；不在 URL 中携带后台令牌，不向公网开放监控端口。

**Tech Stack:** 独立 FastAPI 后台、React/Vite、Vitest、Playwright；如目标环境确认可用，第一版监控面板优先 Netdata，本计划不安装或部署监控服务。

---

## 边界与授权

- 本地 HTML 设计稿与视觉记录：[slice2/design](./slice2/design/design-notes.md)。设计稿里的 `127.0.0.1:19999` **只是示意**，不是已核实的测试机端口。
- 计划目前只执行到本地 Fixture 视觉关卡。🛑 Fan 明确确认四图与“独立面板入口”旅程后，才能冻结真实数据/配置契约或写后端。旧 spec 写“嵌入 Grafana / Netdata”；若 Fan 要求同页 iframe，须先重做该部分设计与鉴权方案。
- 每次 SSH、真实库写入、push、部署仍须 Fan 当场分别授权。测试机先于生产；本计划和设计裁定都不代表这些授权。
- 保留现有工作树 `.playwright-cli` 文件状态，不暂存、不清理。Fixture 文件必须与生产构建隔离，在真实集成后删除。

## Task 1：HTML 设计稿与视觉基准

- [x] 从仓库主题与 spec 确定 Monitor 构图；用 `claude-design` 完成本地 [HTML](./slice2/design/admin-performance-access.html)，再用 `ui-ux-pro-max` 核对主题、字号、状态与对比度。
- [x] 在 1440×900 Chromium 中查看夜间未接入、夜间已配置示意、白天已配置示意三态；不使用真实服务或假指标。控制台 0 error、0 warning。
- [x] 独立 GPT-6 Astra 指出壳层宽度/导航高度/图标尺寸和左下孤行一项必改；已修正并重新截图，裁定 **APPROVE FOR LOCAL FIXTURE**。此裁定不替代 Fan 最终视觉确认。

## Task 2：本地隔离 Fixture 前端

**Files:** `katrain/web/ui/admin-performance-fixture.html`、`src/admin/performance/PerformancePage.tsx`、`PerformancePage.css`、`PerformanceFixture.tsx`、`fixture.tsx`、`PerformancePage.test.tsx`。正式 `admin.html`、`AdminApp.tsx`、`vite.admin.config.ts` 暂不接入此模块。

- [x] 写聚焦组件测试：未接入态没有指标、连接按钮禁用；示意态明确标“示意”、不含真实链接或令牌；状态/主题预览可切换。
- [x] 实现最小纯展示页面，复用现有后台图标、品牌、B/C 色板和楷体；Fixture 仅从单独的 `admin-performance-fixture.html` 入口加载，生产 `build:admin` 不打包此入口。
- [x] 在本地 Vite 预览 1440×900 两个代表状态，查看控制台，核对视觉差异；聚焦 Vitest **15 passed**（含既有后台 12 项）、`build:admin`（含 `tsc -b`）、ESLint、`git diff --check` 通过。构建产物未包含 Fixture 入口或示意文案。

## Task 3：同视口视觉对比与确认

- [x] 为未接入与已配置示意状态各保留参考图、真实 Fixture 截图、并排图、叠加图；只修正影响本模块阅读、几何或状态语义的差异。见 [设计记录](./slice2/design/design-notes.md)。
- [x] 独立 GPT-6 Astra 已看两态八张图，裁定 **APPROVE（仅本地视觉）**；Fan 的本地网页复核仍待进行。
- [ ] 🛑 在 Fan 明确确认之前，不进入 Task 4 的契约/后端；不能把 Fixture 或独立代理裁定算作真实监控验收。

## Task 4：真实监控接入（本轮暂不执行）

- [ ] 取得 Fan 对接入路径的明确确认后，只读核实测试环境监控服务、绑定地址、现有鉴权、端口与 SSH 转发可行性；不得凭设计稿假定已安装 Netdata。
- [ ] 冻结最小服务器配置/可达性契约，先写安全边界测试，再在后台接只读入口；无有效来源时保持“未接入”，不可猜测“在线”。删除 Fixture。
- [ ] 本地真实运行时验收、测试机部署和 Fan 验收；生产发布另列 🛑 并单独授权。
