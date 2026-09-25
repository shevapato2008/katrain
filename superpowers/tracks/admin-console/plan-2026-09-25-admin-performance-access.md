# 内嵌 Grafana 性能监控 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan in the current worktree. Steps use checkbox (`- [ ]`) syntax for tracking. Fan 指定逐模块推进，勿另开 worktree。

**Goal:** 在独立后台页面内嵌 Grafana 看板；先完成诚实的设计与 Fixture 视觉验证，真实监控接入前不宣称模块完成。

**Architecture:** 保留现有后台的 Bearer 登录与 B/C 楷体壳层。正式版在页面内嵌 Grafana；未核实服务时只显示“尚未接入”，不从前端构造在线状态，也不展示假指标。嵌入地址、Grafana 自身鉴权、浏览器嵌入策略及同源代理需求须在目标环境只读核实后再冻结，后台 Bearer 不传给 Grafana，不向公网开放无保护端口。

**Tech Stack:** 独立 FastAPI 后台、React/Vite、Vitest、Playwright、Grafana（目标环境服务与部署尚未核实）。

---

## 边界与授权

- 原“独立面板入口”设计与 Fixture 是未获 Fan 确认的提案。Fan 指出原 spec §10 和此前承诺为**内嵌 Grafana**后，该版本已废弃；旧四图只保留历史记录，不能作为新方案的视觉通过证据。
- 现行本地 HTML 设计稿与预览见 [slice2/design](./slice2/design/design-notes.md)。🛑 Fan 确认**新版 HTML 设计**后才能改隔离 React Fixture；🛑 新版四图确认后才能冻结真实契约或写后端。
- 每次 SSH、真实库写入、push、部署仍须 Fan 当场分别授权。测试机先于生产；本计划和设计裁定都不代表这些授权。
- 保留现有工作树 `.playwright-cli` 文件状态，不暂存、不清理。Fixture 文件必须与生产构建隔离，在真实集成后删除。

## Task 1：内嵌 Grafana HTML 设计稿与视觉基准

- [x] 从仓库主题与 spec 确定 Monitor 构图；用 `claude-design` 将本地 [HTML](./slice2/design/admin-performance-access.html) 改为后台内嵌 Grafana 的设计示意，再用 `ui-ux-pro-max` 核对主题、字号、状态与对比度。
- [x] 在 1440×900 Chromium 中查看夜间未接入、夜间内嵌示意、白天内嵌示意三态；不使用真实服务或假指标。控制台 0 error、0 warning。
- [x] 独立 GPT-6 Astra 查看新版三张 1440×900 设计图，裁定 **APPROVE（仅设计方向）**，无必改项。
- [ ] 🛑 Fan 确认新版设计稿后，再改 React Fixture。代理裁定不替代 Fan 确认。

## Task 2：本地隔离 Fixture 前端（新版设计确认后）

**Files:** `katrain/web/ui/admin-performance-fixture.html`、`src/admin/performance/PerformancePage.tsx`、`PerformancePage.css`、`PerformanceFixture.tsx`、`fixture.tsx`、`PerformancePage.test.tsx`。正式 `admin.html`、`AdminApp.tsx`、`vite.admin.config.ts` 暂不接入此模块。

- [ ] 把旧独立入口 Fixture 改为后台内嵌 Grafana 区域的纯展示预览；未接入态无 iframe/假数据，内嵌示意态标明不是实际 Grafana，不能传令牌。
- [ ] 更新聚焦组件测试与本地 Vite 1440×900 预览，核对夜间未接入、夜间/白天内嵌示意；`build:admin` 不打包 Fixture 入口。

## Task 3：同视口视觉对比与确认

- [ ] 为新版未接入与内嵌示意状态各保留参考图、真实 Fixture 截图、并排图、叠加图；旧外跳方案四图不能复用。
- [ ] 独立 GPT-6 Astra 查看新版四图并记录裁定；Fan 在本地网页亲自复核。
- [ ] 🛑 在 Fan 明确确认之前，不进入 Task 4 的契约/后端；不能把 Fixture 或独立代理裁定算作真实监控验收。

## Task 4：真实监控接入（本轮暂不执行）

- [ ] 取得 Fan 的新版四图确认与单次 SSH 授权后，只读核实测试环境是否有 Grafana、数据源/看板、绑定地址、现有鉴权及 iframe/代理策略；不得凭设计稿假定已安装服务。
- [ ] 冻结最小嵌入配置/可达性契约，先写相关鉴权边界测试，再接正式只读页面；无有效来源时保持“未接入”，不可猜测“在线”。删除 Fixture。
- [ ] 本地真实运行时验收、测试机部署和 Fan 验收；生产发布另列 🛑 并单独授权。
