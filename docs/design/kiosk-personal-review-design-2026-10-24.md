# 个人复盘设计核对 · 2026-10-24

本轮只更新现有 HTML 设计集合，未修改生产 React／后端、未提交、未推送、未部署。使用 `claude-design` 和 `ui-ux-pro-max`，沿用现有 Kiosk 统一规则、圆润软键与中文字体偏好。

## 查看与操作

- [复盘主页](kiosk-current-based-redesign-2026-10-14.html#review)：左侧选中棋局与原谱入口，右侧两档报告常驻，历史对局仍点按选中。
- [导入棋谱复盘](kiosk-current-based-redesign-2026-10-14.html#review-import)：搜索、清空、选中、翻页及三种导入方式可点击。
- [个人原谱回放](kiosk-current-based-redesign-2026-10-14.html#review-replay)：开局、前后手、终局、滑块、坐标和手数开关可操作，返回保留所选棋局与任务示意。
- [已完成个人报告](kiosk-current-based-redesign-2026-10-14.html#review-report)：主页完成按钮保留普通／深度档位；走势、失误跳手、AI 推荐为简化设计示意。原有 `#report` 六标签参考页仍保留。

本地预览：`http://127.0.0.1:4188/docs/design/kiosk-current-based-redesign-2026-10-14.html?review=20261024#review`。

画布外的“设计示意 · 非实机任务状态”可切换：普通完成＋深度运行、双完成、失败续算、提交／排队、同档上次完成＋本次运行、未生成、总手数未确认。切换状态回到主页，避免将未完成任务留在正式报告工作区。

## 构图与状态

采用 Operate 表面：沿用 1024×600、顶栏 56、一级底栏 82、296／680 双栏；二级回放沿用 516 棋盘／460 右栏。普通 500／深度 2000 各占一行，状态、进度条、已分析手数／总手数与动作并列，互不遮盖。

| 状态 | 可见信息与动作 |
| --- | --- |
| 提交处理中 | 等待服务端确认；禁用重复提交，不显示已开始计算 |
| 排队中 | 尚未开始分析；续算排队明确显示“已保留 a/b 手” |
| 分析中 | 进度条＋a/b 手＋百分比；本次报告不可进入 |
| 中断 | 保留实际进度；“继续分析”仅将示意切为待续算排队 |
| 已完成 | 常驻“查看报告”，主动进入对应档位，不自动跳页 |
| 同档旧完成＋新运行 | “本次分析中”及进度始终可见，独立“上次报告”入口 |
| 总手数未确认 | 等待总手数；不计算百分比 |

新增回放、导入、个人报告均标为 `designOnly`，没有对应实机截图。即使通过设计索引进入未完成档位，也只展示“报告尚未完成”和返回入口，不绘制正式分析工作区。

## 导入弹窗

来源仍为 **KifuAPI 公共职业棋谱库**，不与个人历史混用。960×576 弹窗位于画布 x32／y12；标题 28、棋手／赛事／按钮 22、日期／手数等元数据 18 px。中间列表每页 10 条、独立滚动，一屏约四条；分页和底部操作固定，分页 y467。保留“仅导入，不生成报告”“普通 500，导入并分析”“深度 2000，导入并分析”。说明入口交代分析费用需在正式确认时说明，当前预览无实际导入或扣费。

## 数据边界与后续契约

- 新模块只含匿名 `example-*` 设计棋局；公开棋谱主线仅用作盘面几何，未新增用户私有 SGF／UUID。报告曲线、推荐和任务数字均为隔离示意，不来自后台 15 份完成报告。
- 没有 `fetch`、真实任务轮询、计时假进度或任何写请求。重试、生成、导入按钮只改变设计内存状态或显示说明。
- 正式实现复用按个人棋局＋`normal/deep` 分档的任务模型；使用服务端 `status`、`analyzed_moves`、`total_moves`、`requested_visits`。`authorizing`／提交中单独展示，完成只认 `completed`，上次报告不能覆盖本次 active／failed。
- 个人原谱使用个人棋局主线，不请求职业 album 接口；无分析时不绘制胜率／候选。公共导入保持 numeric album → 个人棋局 → 可选对应档位任务的边界。
- Fixture 隔离在 `personal-review.js`，进入生产实现时必须替换为实际数据与原谱主线，删除画布外示意控制器和静态报告数字。本轮仍需用户视觉确认后才能进入生产前后端开发。

## 验证与视觉对照

专用本地 Playwright session `personal-review-design`，浏览器 1440×920，截图 `#stage` 实测 1024×600。检查默认混合、完成档位入口、回放与返回、失败续算、提交／排队、旧报告与新任务、未知总手数、未完成详情门槛；导入检查选中、分页、搜索空结果、清空及操作禁用。主页文本仅 18／22，弹窗仅 18／22／28；按钮最小 44 px；回放与报告右栏无纵向溢出。字体偏好切换隶书后弹窗中文沿用隶书、数字保留 IBM Plex Mono，并已恢复原预览设置。

`node --check`（新增模块与 HTML inline JS）、`git diff --check` 通过；最终浏览器 console 0 errors／0 warnings。未运行生产全量测试或构建。

已亲自查看以下同尺寸参考、实现、并排与 50% 叠加图；数据内容不同用于几何、字体和层级核对，不将像素差异解读为任务数据错误：

- [主页设计](../../output/playwright/personal-review-design-2026-10-24/review-mixed.png)、[双完成](../../output/playwright/personal-review-design-2026-10-24/review-completed.png)、[失败续算](../../output/playwright/personal-review-design-2026-10-24/review-failed.png)。
- [主页实机参考](../../output/playwright/personal-review-design-2026-10-24/review-reference.png)、[并排](../../output/playwright/personal-review-design-2026-10-24/review-side-by-side.png)、[叠加](../../output/playwright/personal-review-design-2026-10-24/review-overlay.png)：2026-10-14 采集截图，保留左右构图；以双档任务区替代旧空曲线与底部生成区。
- [导入设计](../../output/playwright/personal-review-design-2026-10-24/import-dialog.png)、[调查 mock 参考](../../output/playwright/personal-review-design-2026-10-24/import-reference.png)、[并排](../../output/playwright/personal-review-design-2026-10-24/import-side-by-side.png)、[叠加](../../output/playwright/personal-review-design-2026-10-24/import-overlay.png)：参考是 2026-10-23 现有实现的本地 mock，**不是实机截图**；对比可见字号放大、分页移出滚动区、导入动作缩短且语义保留。
- [个人回放](../../output/playwright/personal-review-design-2026-10-24/personal-replay.png)、[已完成个人报告](../../output/playwright/personal-review-design-2026-10-24/personal-report.png)：新增提案，无实机对照。

## 文件与保留工作

新增 `kiosk-unified/personal-review.js`、`personal-review.css` 和本说明；主 HTML 只补这两份资源、三个 designOnly 索引、画布外示意控制器、专属说明与初始化钩子。未修改原 `report.js/css`、大厅 `game.js/css` 或 OGS 课程文件。原 HTML 的未提交工作原样保留；开始前备份位于 `/private/tmp/kiosk-personal-review-backup-20261024/`。全部改动保持未提交，便于与用户原有 HTML 改动一起审阅。
