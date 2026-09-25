# 性能监控：首个用户旅程设计记录

日期：2026-09-25。目标视口：1440×900。当前阶段：HTML 设计稿与隔离 React Fixture；**未接入真实监控服务，未实现正式后台页面**。

## 范围与判断

- 本切片从 spec §10 建议顺序中的“性能监控”开始。主界面是 **Monitor**，管理员主要识别当前环境、监控来源与可访问性，然后进入实时面板。沿用已批准的后台 B 石墨铜（夜间）、C 雾白蓝（白天）、楷体和教程/cron 的紧凑字号，不使用绿色主题。
- 仓库目前未发现 Grafana/Netdata 的部署配置或监控 API；不以此推断目标机器必然没有监控进程。默认状态诚实显示“尚未接入／状态未知”，不显示虚构 CPU、内存、磁盘数值。
- 三种可行路径比较：① 监控端口独立经 SSH 隧道访问，由后台提供入口（本轮选用，认证边界最小）；② iframe 嵌入 Grafana/Netdata（需解决监控产品自己的鉴权、浏览器嵌入策略与后台 CSP）；③ 后台代理 Netdata API 并原生绘图（需新增受保护的数据契约与采集/缓存）。独立 GPT-6 Astra 决策代理建议先选 ①，待真实端点核实后再判断是否升级为 ②/③。**入口设计不等于性能监控模块已完成。**
- [Netdata 官方安全说明](https://learn.netdata.cloud/docs/netdata-agent/configuration/securing-agents)明确本地面板默认在 19999 端口，需限制访问；[Grafana 官方嵌入说明](https://grafana.com/docs/grafana/latest/visualizations/dashboards/share-dashboards-panels/)说明嵌入查看仍需 Grafana 自身的授权。因此设计不传递后台 Bearer、不开放无保护的监控端口，也不把“已配置”冒充“已在线”。

## 可视稿

- [可交互 HTML](./admin-performance-access.html)：右下角可切换未接入/已配置示意、夜间/白天；截图模式加 `?capture=true` 隐藏设计控件。
- 初版设计截图在 Git 忽略的 `output/playwright/`。修复首轮品牌图 404 后，夜间未接入和白天已配置示意两态均在真实 Chromium 中按 1440×900 截取，控制台 0 error、0 warning；这两态的最终证据已复制到本目录。
- 隔离 React Fixture：本机 Vite 的 `admin-performance-fixture.html`，不在正式 `admin.html` 中引入，也不包含真实监控链接、指标或令牌。浏览器控制台 0 error、0 warning。
- 夜间未接入：[参考图](./performance-reference-unconnected-dark-1440x900.png) · [真实运行图](./performance-fixture-unconnected-dark-1440x900.png) · [并排](./performance-side-unconnected-dark.png) · [叠加](./performance-overlay-unconnected-dark.png)。
- 白天已配置示意：[参考图](./performance-reference-connected-light-1440x900.png) · [真实运行图](./performance-fixture-connected-light-1440x900.png) · [并排](./performance-side-connected-light.png) · [叠加](./performance-overlay-connected-light.png)。也可用 [四图查看器](./performance-fourup.html) 切换。
- 独立 GPT-6 Astra 实际查看两态八图，裁定 **APPROVE（仅本地视觉）**。主面板尺寸、栅格、间距与状态语义已对齐；遗留差异是正式后台壳层导航/页脚的轻微字位偏移，以及设计稿和 Fixture 的预览标识不同，不影响阅读。此裁定不能替代 Fan 的视觉确认。
- `ui-ux-pro-max` 建议的状态可见、图标加文字、浅深主题对照、焦点态与无数据说明已纳入；自动推荐的绿色/Dark-OLED 方案未采用，因为 Fan 已指定独立于 Galaxy 的现有 B/C 主题。这里只选用了与监控任务相关的原则，没有另起视觉系统。
- `claude-design` 自查：Monitor 构图、左侧主监控区与右侧访问事实区有清晰主次；无营销 hero、三等分功能卡、假统计数字、渐变/玻璃效果。十项 anti-slop 指标为 0/10；网格只是无数据画布，不假扮趋势图。

## 下一关

1. 🛑 Fan 在本地复核上面的四图，并确认是否接受“后台提供独立监控面板入口，经既有 SSH 隧道访问”，而非旧 spec 中的同页嵌入。
2. **在 Fan 明确确认四图与访问旅程前，不冻结契约、不写监控后端。** 后续接真实服务还需核实目标环境的监控端点，并分别取得 SSH、部署、每次 push 的授权；测试机先于生产。
