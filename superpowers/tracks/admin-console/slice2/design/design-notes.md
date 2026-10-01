# 性能监控：首个用户旅程设计记录

日期：2026-09-26。目标视口：1440×900。当前阶段：**新版内嵌 Grafana HTML 与隔离 React Fixture 四图已由独立 GPT-6 Astra max 代理代审通过**；Fan 明早仍可要求返工。未接入真实监控服务，也未实现正式后台页面。

## 2026-09-26 新版 Fixture 与四图

Fan 睡前明确委托独立 GPT-6 Astra max 代理替他处理视觉决策。本地 Fixture 已由旧 Netdata 外跳提案改为后台内嵌 Grafana 设计示意，入口仍独立于正式 `admin.html`；未接入态无 iframe、无假指标，嵌入示意态四个卡片均标注“暂无实时数据”，不向 Grafana 传令牌。

| 状态 | HTML 参考 | React Fixture | 并排 | 叠加 | 增强差异 |
|---|---|---|---|---|---|
| 夜间未接入 | [参考](./performance-grafana-design-unconnected-dark-1440x900.png) | [运行](./performance-grafana-fixture-unconnected-dark-1440x900.png) | [并排](./performance-grafana-side-unconnected-dark.png) | [叠加](./performance-grafana-overlay-unconnected-dark.png) | [差异](./performance-grafana-diff-unconnected-dark.png) |
| 夜间嵌入示意 | [参考](./performance-grafana-design-embedded-dark-1440x900.png) | [运行](./performance-grafana-fixture-embedded-dark-1440x900.png) | [并排](./performance-grafana-side-embedded-dark.png) | [叠加](./performance-grafana-overlay-embedded-dark.png) | [差异](./performance-grafana-diff-embedded-dark.png) |
| 白天嵌入示意 | [参考](./performance-grafana-design-embedded-light-1440x900.png) | [运行](./performance-grafana-fixture-embedded-light-1440x900.png) | [并排](./performance-grafana-side-embedded-light.png) | — | — |

[可交互四图查看器](./performance-grafana-fourup.html) 支持 `pair=unconnected-dark|embedded-dark|embedded-light` 与 `mode=side|overlay|diff`。独立代理裁定 **APPROVE（仅本地 Fixture 视觉）**：构图、紧凑字号、深浅主题与状态语义均通过；共享导航的轻微偏移及提示文案差异不阻断。聚焦前端 3/3 通过、`build:admin` 通过，浏览器只有 React DevTools INFO。真实 Grafana 接入尚须 Fan 当场授权只读 SSH 核实服务/鉴权/嵌入策略；本次未远程连接、写库、push 或部署。

## 2026-09-25 方向修正：回到内嵌 Grafana

Fan 指出原 spec §10 写“嵌入 Grafana / Netdata”，并记得此前承诺内嵌 Grafana。独立入口只是未经 Fan 确认的安全性提案，不能取代原需求。当前 [HTML](./admin-performance-access.html) 已改为后台内嵌 Grafana 设计：未接入态不显示 iframe/数据；内嵌示意态展示看板位置、四个无数据占位与明确的“非实际 Grafana 页面”标识。真实页面须等服务、Grafana 鉴权和浏览器嵌入策略核实后才接入。

- [夜间未接入设计图](./performance-grafana-design-unconnected-dark-1440x900.png)
- [夜间内嵌设计图](./performance-grafana-design-embedded-dark-1440x900.png)
- [白天内嵌设计图](./performance-grafana-design-embedded-light-1440x900.png)

三张均为真实 Chromium 1440×900 截图；控制台 0 error、0 warning。旧四图不可用于新版视觉确认。
独立 GPT-6 Astra 查看这三张新图，裁定 **APPROVE（仅设计方向）**：页面明确将 Grafana 放在后台内容区，未接入与示意状态清楚，无虚构指标；B/C 配色、楷体和后台壳层几何一致。无必改项。它明确指出 HTML 只是标注的布局占位，不是真实 iframe，也不代替 Fan 确认。
Fan 随后要求字号向已实现的教程和 cron 靠拢。本稿已按当前 `AdminApp.css`、`CronPage.css` 缩小监控内容字号（保留共用页眉/侧栏大小），三张图已重拍；这是同一布局的排版修订，不是新功能或真实 Grafana 截图。

## 范围与判断

- 本切片从 spec §10 建议顺序中的“性能监控”开始。主界面是 **Monitor**，管理员主要识别当前环境、监控来源与可访问性，然后进入实时面板。沿用已批准的后台 B 石墨铜（夜间）、C 雾白蓝（白天）、楷体和教程/cron 的紧凑字号，不使用绿色主题。
- 仓库目前未发现 Grafana/Netdata 的部署配置或监控 API；不以此推断目标机器必然没有监控进程。默认状态诚实显示“尚未接入／状态未知”，不显示虚构 CPU、内存、磁盘数值。
- 三种路径曾被比较：① 独立监控入口；② iframe 嵌入 Grafana/Netdata；③ 后台代理指标 API 并原生绘图。曾有独立代理建议先选 ①，但 Fan 指出需求是内嵌 Grafana，故现按 ② 设计。仍需解决 Grafana 自身鉴权、浏览器嵌入策略与后台 CSP。**设计示意不等于性能监控模块已完成。**
- [Netdata 官方安全说明](https://learn.netdata.cloud/docs/netdata-agent/configuration/securing-agents)明确本地面板默认在 19999 端口，需限制访问；[Grafana 官方嵌入说明](https://grafana.com/docs/grafana/latest/visualizations/dashboards/share-dashboards-panels/)说明嵌入查看仍需 Grafana 自身的授权。因此设计不传递后台 Bearer、不开放无保护的监控端口，也不把“已配置”冒充“已在线”。

## 旧独立入口可视稿（已废弃，仅作历史）

- [可交互 HTML](./admin-performance-access.html) 现已改为内嵌 Grafana 示意；右下角可切换未接入/内嵌示意、夜间/白天；截图模式加 `?capture=true` 隐藏设计控件。
- 初版设计截图在 Git 忽略的 `output/playwright/`。修复首轮品牌图 404 后，夜间未接入和白天已配置示意两态均在真实 Chromium 中按 1440×900 截取，控制台 0 error、0 warning；这两态的最终证据已复制到本目录。
- 隔离 React Fixture：本机 Vite 的 `admin-performance-fixture.html`，不在正式 `admin.html` 中引入，也不包含真实监控链接、指标或令牌。浏览器控制台 0 error、0 warning。
- 夜间未接入：[参考图](./performance-reference-unconnected-dark-1440x900.png) · [真实运行图](./performance-fixture-unconnected-dark-1440x900.png) · [并排](./performance-side-unconnected-dark.png) · [叠加](./performance-overlay-unconnected-dark.png)。
- 白天已配置示意：[参考图](./performance-reference-connected-light-1440x900.png) · [真实运行图](./performance-fixture-connected-light-1440x900.png) · [并排](./performance-side-connected-light.png) · [叠加](./performance-overlay-connected-light.png)。也可用 [四图查看器](./performance-fourup.html) 切换。
- 独立 GPT-6 Astra 曾查看旧外跳方案两态八图，裁定旧版 **APPROVE（仅本地视觉）**；该裁定不适用于现在的内嵌设计。旧 Fixture 页面与图片只作历史，勿展示为当前方案。
- `ui-ux-pro-max` 建议的状态可见、图标加文字、浅深主题对照、焦点态与无数据说明已纳入；自动推荐的绿色/Dark-OLED 方案未采用，因为 Fan 已指定独立于 Galaxy 的现有 B/C 主题。这里只选用了与监控任务相关的原则，没有另起视觉系统。
- `claude-design` 自查：Monitor 构图、左侧主监控区与右侧访问事实区有清晰主次；无营销 hero、三等分功能卡、假统计数字、渐变/玻璃效果。十项 anti-slop 指标为 0/10；网格只是无数据画布，不假扮趋势图。

## 下一关

1. 设计与四图视觉停点按 Fan 睡前明确授权交给独立 GPT-6 Astra max 代理，均已通过；Fan 明早可以在本地网页复核并要求返工。
2. 🛑 真实 Grafana 接入前仍需 Fan 当场授权测试机只读 SSH，核实端点、服务与鉴权；每次 push、部署和真实库写入也分别授权。没有目标环境事实前不冻结嵌入契约、不写监控后端，不把 Fixture 当成真实监控验收。
