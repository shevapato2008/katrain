# cron 可视化：本地设计稿（2026-09-25）

状态：HTML 已按独立 GPT-6 Astra 的源码／语义反馈修订；下列 `v2` 截图是当前 1440×900 Chromium 参考图。独立 Astra 裁定设计稿 **APPROVE FOR LOCAL FIXTURE**，又对下方 Fixture 四图裁定 **APPROVE FOR LOCAL CONTRACT/BACKEND**，均无必改项。Fan 仍在 MacBook 浏览器做最终复核。旧版截图只作构图历史。此稿不是生产页面、真实 cron 数据或发布授权。

## 构图与现有后台的一致性

- 主表面是 **Monitor**，次级表面是 **Inspect**：顶部直接显示进程心跳，下面是两条真实契约中的队列摘要和九项任务状态；点击任务后右侧查看运行历史。没有营销首屏或装饰性指标。
- 延续 Fan 确认的 B「石墨铜」夜间、C「雾白蓝」白天、楷体，以及现有教程后台的 52px 顶栏、216px 侧栏、品牌、环境标签与登录口吻。`ui-ux-pro-max` 给出的通用深色/Fira 字体建议不覆盖既定主题；采纳其状态反馈、文字标签、可滚动表格、错误恢复与可见焦点规则。
- 所有状态同时用文字表达，不依赖颜色。失联时九项任务全部变成“失联”，不沿用最后一次“正常”；接口错误保留旧数据但标明上次成功读取时刻；表不存在、零任务分别使用诚实空态。
- 原 cron 计划的共享公开用户鉴权已经过时；设计沿用当前独立的 `admin:fan` 会话和 `/api/admin` 同源边界。页面只读，不提供“立即运行/暂停”。示例时间、队列数和历史记录只在本设计 HTML 中，不得进入生产数据流。

## 目标尺寸与状态入口

设计稿：[admin-cron-design.html](./admin-cron-design.html)。已在 Playwright Chromium 验证的地址是 `http://127.0.0.1:8009/superpowers/tracks/admin-console/slice1/design/admin-cron-design.html?theme=light&state=failed`；服务需在仓库根目录执行 `python3 -m http.server 8009 --bind 127.0.0.1`。普通 MacBook Chrome 也可尝试 `file:///Users/fan/Repositories/katrain-admin-console/superpowers/tracks/admin-console/slice1/design/admin-cron-design.html?theme=light&state=failed`，但 Playwright CLI 自身禁止 `file:` 导航，故自动化证据均来自 HTTP。把 `theme` 改为 `dark` 看夜间版，把 `state` 改为 `healthy`、`offline`、`api-error`、`no-table`、`empty`、`loading`、`history`、`signin` 看不同状态。历史抽屉可加 `&job=fetch_upcoming`；异常态中点击任务会保留原列表状态。

1440×900 Chromium 当前参考图（`v2`）：

| 状态 | 截图 |
|---|---|
| 白天·失败与报错优先 | [cron-light-failed-v2-1440x900.png](./cron-light-failed-v2-1440x900.png) |
| 白天·异常列表打开赛事列表历史 | [cron-light-history-failed-v2-1440x900.png](./cron-light-history-failed-v2-1440x900.png) |
| 白天·首次加载 | [cron-light-loading-v2-1440x900.png](./cron-light-loading-v2-1440x900.png) |
| 白天·接口错误保留旧采样 | [cron-light-api-error-v2-1440x900.png](./cron-light-api-error-v2-1440x900.png) |
| 夜间·进程失联 | [cron-dark-offline-v2-1440x900.png](./cron-dark-offline-v2-1440x900.png) |
| 夜间·全正常 | [cron-dark-healthy-v2-1440x900.png](./cron-dark-healthy-v2-1440x900.png) |
| 夜间·200 条运行历史 | [cron-dark-history-v2-1440x900.png](./cron-dark-history-v2-1440x900.png) |

旧版 1440×900 构图参考（**非当前 HTML 的验收图**）：

| 状态 | 截图 |
|---|---|
| 夜间·全正常 | [cron-dark-healthy-1440x900.png](./cron-dark-healthy-1440x900.png) |
| 白天·任务有报错 | [cron-light-failed-1440x900.png](./cron-light-failed-1440x900.png) |
| 夜间·进程失联 | [cron-dark-offline-1440x900.png](./cron-dark-offline-1440x900.png) |
| 白天·接口错误、旧数据 | [cron-light-api-error-1440x900.png](./cron-light-api-error-1440x900.png) |
| 白天·状态表不存在 | [cron-light-no-table-1440x900.png](./cron-light-no-table-1440x900.png) |
| 白天·零任务 | [cron-light-empty-1440x900.png](./cron-light-empty-1440x900.png) |
| 白天·加载中 | [cron-light-loading-1440x900.png](./cron-light-loading-1440x900.png) |
| 夜间·200 条运行历史 | [cron-dark-history-1440x900.png](./cron-dark-history-1440x900.png) |
| 白天·继承既有登录态外观 | [cron-light-signin-1440x900.png](./cron-light-signin-1440x900.png) |

## Fixture 四图与独立视觉裁定

四图采集时的临时 Vite Fixture 入口现已随真实接口集成删除；`?cron-fixture=1` 不再提供示例预览。可直接查看下面保留的参考图、运行图与四图，或运行上面的 HTML 设计稿和后述本机真实 API 预览。示例业务数据只留在测试专用 `cronTestData.ts`，生产构建无 Fixture 数据或入口。

| 代表状态 | HTML 参考 | Fixture 运行图 | 并排 | 50% 叠加 | 增强差异 | 四格总览 |
|---|---|---|---|---|---|---|
| 白天·失败 | [参考](./cron-light-failed-v2-1440x900.png) | [运行](./cron-fixture-light-failed-1440x900.png) | [并排](./cron-fourup-light-failed-side-by-side.png) | [叠加](./cron-fourup-light-failed-overlay.png) | [差异](./cron-fourup-light-failed-diff.png) | [四格](./cron-fourup-light-failed-fourup.png) |
| 夜间·200 条历史 | [参考](./cron-dark-history-v2-1440x900.png) | [运行](./cron-fixture-dark-history-1440x900.png) | [并排](./cron-fourup-dark-history-side-by-side.png) | [叠加](./cron-fourup-dark-history-overlay.png) | [差异](./cron-fourup-dark-history-diff.png) | [四格](./cron-fourup-dark-history-fourup.png) |

两组均为 1440×900，同视口比较。Fixture 初版夜间预览曾被浏览器浅色偏好覆盖，修订为显式深色 token 后重拍。独立 GPT-6 Astra 实际查看四图及单图后裁定 **APPROVE**：构图、表格列、抽屉、遮罩、楷体、品牌与 B/C 主题没有阻断偏差。非阻断差异：表格正文略大，导航图标/选中项略有位移，副标题简化，历史示例耗时统一为 1.2 秒，页脚改为诚实的“仅显示最近记录”。该裁定只覆盖视觉和可见状态文案；不替代 Fan 最终复核，也不授权远程、真实库、push 或部署。

## 真接口本机预览（合成任务）

本机 `output/playwright/admin-cron-local-smoke.py` 在 `/private/tmp` 建一次性 SQLite，复用 web 侧 schema 建表、cron 记录器写入和专用 admin 进程的真实只读接口。后台已构建 React 页面在 `http://127.0.0.1:8010/admin.html` 登录后切换「定时任务」；[九项列表运行图](./cron-runtime-local-1440x900.png) 和 [失败历史运行图](./cron-runtime-local-history-1440x900.png) 都是 1440×900 Chromium，控制台 0 errors。浏览器实测失败／有报错／该跑没跑优先展示，历史显示实际记录的完整异常；两次 15 秒采样后历史抽屉仍保持打开。示例任务和临时账号只存在于本机 smoke 脚本/临时库，**不是生产 cron 进程或真实环境数据**；截图中的 1 ms 耗时和“本机合成”是刻意的隔离演示。

## 契约与 Fixture 边界

Fixture 和同视口四图已通过独立视觉关卡，可冻结与现有后台相容的 `observed_at`、`jobs`、`health`、`runs`、`queues` 契约并进入本地后端。生产构建不能包含示例业务数据；Fixture 删除条件是本地真实接口集成及验收。

## 修订与当前验证

独立 Astra 指出并经 HTML 修订：真正的失败与有报错分开、异常优先排序；抽屉开合保持原列表状态；历史时间不晚于采样，短间隔成功和常驻循环普通迭代不虚构历史；浅色小字对比度和旧数据提示不再因表格透明度变淡；首次加载不显示假健康。Astra 对源码／语义和七张当前视觉图均给出通过意见；其权限只到本地 Fixture，不代替 Fan 最终验收。

本次用现有 `jsdom` 执行设计稿内联脚本，11 项断言通过：异常首行、九项任务、异常抽屉状态、接口错误旧采样时刻、失联时间及 200 条历史等均为预期 DOM 结果。`jsdom` 不等于 Chromium 视觉检查，不能替代四图。

Chromium 最新一轮：`127.0.0.1:8009` 静态服务可访问，Playwright 独立会话成功打开；七张 `v2` 图均核对为 **1440×900**，控制台 **0 errors / 0 warnings**。历史抽屉 200 行，`clientHeight=717`、`scrollHeight=15976`，指针悬停在抽屉后真实滚轮使 `scrollTop` 由 0 到 600。注意 Playwright 的 `open` 会重置视口，本轮每个状态均在打开后重新设为 1440×900 再截图。

## 旧版截图自检（仅供构图参考）

Chromium 已在 1440×900 打开设计稿；刷新后控制台 0 error。主表格九项在普通状态一屏可见，失联/接口错误多一条提示时表格自身可滚。历史抽屉为独立滚动区，示例任务 `fetch_upcoming` 灌入 200 条；任务点击只改变设计稿 query，不调用后端。`claude-design` 的十项俗套特征诊断为 **0/10**：无科技渐变、通用紫、功能卡片、左侧装饰条、玻璃模糊、夸张数字、图标顶饰、居中堆叠、默认 Inter 或错误的营销式构图。
