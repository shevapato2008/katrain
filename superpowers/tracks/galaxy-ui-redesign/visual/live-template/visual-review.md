# Galaxy 直播棋盘模板视觉证据汇总

- 审阅日期：2026-08-06
- 真实后端：`http://127.0.0.1:8901`
- 真实对局：`/galaxy/live/yike_184016`（采集时 194/194 手，直播状态）
- 用户视觉确认：**已批准。** 用户在 2026-08-06 查看修复版及本组同视口证据后明确回复“明白，没问题了”。
- 数据真实性：使用真实 backend 与数据库直播详情；未启用 fixture、mock API 或生产模拟业务数据；采集结束后服务已停止。

## 证据完整性

12 个目标视口均包含原尺寸 `reference.png`、`implementation.png`、`side-by-side.png`、`overlay.png`、`diff.png` 与逐视口 `review.md`。Pillow 合成器不缩放源图：并排图宽度为两源图之和，overlay 使用 50% blend，diff 使用逐像素 difference。899×700 和 430×880 另有 `implementation-scrolled.png`。

批准复制执行注记：计划示例中的 `visual/live-template/*x*` 还会匹配 `plan-base.txt`（`.txt` 含 `x`），因此原样循环多产生一次 “Not a directory”；随后以目录过滤重跑，12 个真实 viewport 均逐文件 `cmp` PASS，批准目录恰含 12 张 PNG。

自动几何 12/12 PASS：顶栏均 52px；canvas 全部为正方形、位于 board stage 内并在视口水平方向完整；document 水平 overflow 均为 0。此结果只证明几何契约，不等于视觉验收。

| 视口 | 左栏 | 右栏/模式 | 棋盘 | 视觉状态 |
|---|---:|---:|---:|---|
| 1535×900 | 216 | 340 | 828 | 已批准；旧三项问题已修复 |
| 1536×900 | 240 | 380 | 828 | 已批准；旧三项问题已修复 |
| 1537×900 | 240 | 380 | 828 | 已批准；旧三项问题已修复 |
| 1440×900 | 216 | 340 | 828 | 已批准；旧三项问题已修复 |
| 1201×800 | 216 | 340 | 625 | 已批准；中段可滚动且无重叠 |
| 1200×800 | 216 | 340 | 624 | 已批准；中段可滚动且无重叠 |
| 1199×800 | overlay closed | 320 | 728 | 已批准；中段可滚动、手数完整 |
| 1024×768 | overlay closed | 320 | 684 | 已批准；趋势图可读、手数完整 |
| 901×700 | overlay closed | 320 | 561 | 已批准；中段可滚动且无重叠 |
| 900×700 | overlay closed | 320 | 560 | 已批准；重点复核通过 |
| 899×700 | 无侧栏 | 纵向 | 879 | 已批准；滚动后动作区不受遮挡 |
| 430×880 | 无侧栏 | 纵向 | 410 | 已批准；滚动后动作区不受遮挡 |

## 核心视觉结论

- 构图与棋盘优先：1440 棋盘精确达到 828px；1024 从参考的 244px 提升到 684px；430 从 0px 恢复到 410px。棋盘上方旧页面标题被移除，右栏模块牌承载返回、对局名、赛事/手数和直播状态。
- 响应式导航：1536+ 为 240px docked，1200–1535 为 216px docked，900–1199 默认关闭的 overlay，低于 900 使用固定底部导航。899/430 滚到底时动作区 bottom 与底栏 top 相接且 `actionsUnobscured=true`。
- 组件层级：右栏明确分为模块牌、中段内容与固定回放区；纵向模式按 board → module → body/controls → actions 排列。横向中段现有 `724px` 内容高度，在各视口形成 49–274px 的独立滚动余量；趋势图与显示开关保持正常顺序，不再重叠。
- 字体：`.galaxy-brand-cn` 为 `Galaxy Long Cang`；中文正文族为 `LXGW WenKai`；Latin 与数字由 unicode-range 回退系统 UI。1440 中文页加载 11 个 woff2，transfer 3,605,300 bytes；生成源资产 16,787,692 bytes，Galaxy build 匹配字体 16,732,140 bytes。
- 字体边界：kiosk build 匹配 Galaxy `wenkai-*`/`longcang-brand-*` 文件数为 0；来源命令、输入 SHA-256 与两份 OFL 路径记录于 `font-budget.json`。
- 色彩/材质/资产：保留真实 `/assets/img/logo-white.png`、原棋盘木纹、黑白棋子、坐标与最后一手环；模块 icons 保留现有 MUI 资产。容器统一深黑/暗灰、细边界与绿色强调。
- 文案与语义：成功态使用真实中文直播、棋手、赛事、日期、胜率、规则/贴目、AI pending 与回放手数。桌面/移动截图中已无 `Home`、`Tutorials`、`More`、`COORDINATES`；loading/error/disabled 由组件测试覆盖，不伪造进这组真实成功态截图。

## 与参考图的意图性差异

品牌由“弈航”同步改为“智星盒 / StellaBox”；左栏尺寸/模式和右栏宽度按新断点统一；控制由参考单行改为两列；中文导航替代多数英文文案。这些是已确认设计方向，不应按像素 diff 视为回归。参考与实现保留相同棋盘/棋子资产，但真实直播在两次采集时的棋盘局面绘制存在轻微时间差，diff 中相应棋子区域不应解释为材质替换。

## 修复复核与批准项

1. 趋势图/controls 重叠已修复：全部横向中段 `scrollHeight > clientHeight`，截图中趋势图完整；900×700 为 `724/450px`，有 274px 可滚动余量。
2. 回放手数裁切已修复：320/340/380px 三档均完整显示 `194 / 194 手`。
3. 中文混用已修复：cn desktop/mobile 无 `Home`、`Tutorials`、`More`、`COORDINATES`；对应文案为首页、教程、更多、坐标。
4. 中文字体切片总构建体积约 16.7MB，1440 首屏实际请求与精确值记录于 `font-budget.json`；kiosk 隔离正确。用户在批准修复版时接受该项为非阻塞差异。

本轮未发现新的视觉阻塞；12 个目标视口于 2026-08-06 获得用户批准。唯一记录的已接受非阻塞差异是上述约 16.7MB Galaxy 中文字体构建体积与 1440 首屏请求预算；不扩展为其他未获用户陈述支持的差异。

批准证据：用户在查看修复版后明确回复“明白，没问题了”。对应 12 张 `implementation.png` 已按 Task 12 复制到 `visual/approved/live-template/`，并以逐文件 `cmp` 验证字节一致。

## 最终验证与例外

- 构建与证据：`npm run build`、`npm run build:kiosk-2d` PASS；focused Python 为 30/30 与 3/3 PASS；approved 截图逐文件 `cmp` 12/12 PASS。相关 review tests 27/27 PASS，目标 lint 0；此前同像素 Playwright 验证为 17/17 PASS，最终 spec review 与 quality review 均为 Approved。
- Fresh browser 限制：Task 12 的 fresh Playwright 原命令因该 worktree Python 缺少 `fastapi`，webServer 未能启动，因此本轮不虚报 fresh Playwright PASS；保留上述此前 17/17 同像素证据。
- 全量 unit：在 Node 26 正确提供 localStorage 文件后为 1043 pass、2 fail、5 skip；两项失败涉及的生产与测试文件相对 immutable plan-base 均无 diff，记录为 plan-base 既有失败。
- Lint：repository-wide lint 仍有基线失败；最终 review 后，分支新增/修改目标的 lint 为 0。该事实不改写全库 lint 的失败状态。
- 字体接受例外：1440 中文页 `encoded_bytes=3,602,000`（约 3.602MB）高于计划中的 511KiB 断言，属于用户已明确接受的唯一非阻塞差异；Galaxy build 字体总量为 16,732,140 bytes，低于 49MiB，kiosk Galaxy 字体匹配为 0。实际许可文件为 `OFL-LXGW-WenKai.txt` 与 `OFL-Long-Cang.txt` 两份，而非计划中的旧单一 `OFL-1.1.txt` 路径；`sources.json` 的 generator、版本、SHA-256 与 OFL 字段完整。
- 资产与隔离：protected board/stone/logo 与 drawing utility 相对 immutable plan-base 无变化；kiosk build 无 Galaxy 字体或 `/galaxy/` route match。未启动 ladder backend 或 kiosk 设计/实现。
