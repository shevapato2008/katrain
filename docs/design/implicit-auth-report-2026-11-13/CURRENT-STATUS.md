# 账号入口与报告进度：设计预览及只读核查

2026-11-13；核查基线 `ec6ca09d18069403235247866b6744843c9c4c12`，分支 `feature/membership-recharge`。本轮只读核查源代码、已有文档与本地 Git 历史，新增独立设计文件和设计合集链接。独立设计 agent 未运行生产测试、真实分析、短信、支付、数据库查询/写入、SSH、提交、合并或部署；v3 的实机参考由主 agent 另行只读取图提供。**源码支持不等于现场设备或服务验收通过。**

## 设计入口

- [推荐方案：紧凑外置报告进度](index.html)，Kiosk 目标 1024×600。
- [Galaxy 对应布局](index.html?surface=galaxy)，目标 1440×900。
- [Kiosk 统一手机号入口 v2](auth.html)；[Galaxy 模态入口 v2](auth.html?surface=galaxy)。
- [已验证手机号后补用户名](auth.html?step=name)；[Galaxy 同一弹窗补用户名](auth.html?surface=galaxy&step=name)。
- 右上角“演示”可模拟排队、分析中、盒端关闭/重开、服务端中断待继续、继续中、完成和失败重试。左侧“分析报告”菜单可触发两档内存示例；卡片右侧仅展示状态。所有状态均为**设计演示，刷新清空**，CSP 禁止 connect/form 网络提交；无生产 Fixture 路由。
- 登录左下“预览情景”可切新手机号、已绑定、旧用户名、不同手机号绑定冲突、旧 u_ 账号。验证码示例 `123456`；新名可用时不出现密码；输入示例旧名“青山”才显示原密码；“已绑定账号”在验证原密码后给出绑定冲突。均无真实账号操作。

## 最新视觉迭代：Kiosk 紧凑矩形进度（v5）

按用户最新反馈，仅修改 Kiosk：去掉圆环，复用此前 Galaxy 矩形报告块的绿色材质与横向填充方式。普通/高级报告完整名称为14px，右侧12px百分比，两者在同一行；每块34px高，两档合计74px。对局卡片仍624×74，行间距仍8px，报告块仍在卡片边框外。进行中保留轻微充电光效，填充与文字、aria值使用同一手数比例；低动态偏好关闭光效。菜单操作与现有 Galaxy 稿均不变。

代表预览：[Kiosk](index.html)；[截图](screenshots/kiosk-compact-bar-v5-1024x600.png)。本机 Chrome 1024×600 核对：三卡 y160/242/324、均624×74；圆环节点0，报告不在卡片内部；普通100%、高级44%的填充与aria同值，无脚本错误、无横向溢出。未运行生产测试或操作设备。v4 已独立保存为 [index-v4.html](index-v4.html) + `preview-v4.css/js`。

## 历史迭代：原行距＋完整名称与环形百分比（v4，Kiosk 已被 v5 替代）

本轮继续使用 claude-design 与 ui-ux-pro-max，保留既有配色、字体与固定1024×600实机画布。v3 完整隔离保存为 [index-v3.html](index-v3.html) + `preview-v3.css` / `preview-v3.js`。以下为 v4 历史记录；登录设计不变，没有生产代码、实机操作、部署或真实网络业务请求。

- **恢复原密度**：Kiosk 对局卡片仍是624×74，行本身恢复74px、间距8px；三行顶部160/242/324，与原实机一致，不再用94px容器撑大行距。
- **明确布局取舍**：仅将左棋盘预览从296px收紧至224px，棋盘200×200；右列表从680扩至752px、起点x=256。卡片624px不加宽、不挤窄；外部右列为120×74，与卡片相隔8px。固定画布与分页/底栏保留。
- **每档一行**：“普通报告/高级报告”完整16px名称，右边34px环，中心12px百分比。两行各34px、间隔6px；100%满绿、50%绿半圈、90%绿九成，余段暗灰。`pathLength=100` 和 `stroke-dasharray` 直接使用同一真实示例百分比，不使用spinner代替进度。
- **运行提示**：极轻的亮点只在已完成弧段的末端调节亮度，不旋转、不改变弧长。低动态偏好关闭亮点。普通完成和高级运行各自展示；未生成显示“—”，失败/中断保留水位且卡片文字说明状态。
- **展示和操作分开**：右列全为非交互状态节点，无button、tabindex或点击处理。真实可操作入口仍在左侧“分析报告”菜单，两档各48px高；可演示生成、查看、重试、继续，运行档禁用操作。删除入口仍在选中预览标题右侧。
- **Galaxy**：保持416×104卡片及原104px行高、8px间距，不增加高度；外部右列126×74，同样是完整名＋圆环。列表总宽552px，从左预览区让出空间，卡片不挤窄。

[推荐 Kiosk](index.html) · [Galaxy 双档运行](index.html?surface=galaxy&demo=dual) · [Kiosk 双档运行](index.html?demo=dual)。代表截图：[Kiosk](screenshots/kiosk-ring-v4-1024x600.png)、[Galaxy](screenshots/galaxy-ring-v4-1440x900.png)。

最小核对：本地真实浏览器测得Kiosk三卡624×74、y160/242/324，右列120×74且在卡片外；Galaxy三卡416×104、右列126×74，无横向溢出。圆环中心、aria-valuenow与弧段同值；运行节点DIV无tabindex。菜单项48px，已实际点击查看与生成入口并确认仅内存状态变化。`node --check preview.js`通过。未重复全状态截图或生产测试，仍待用户确认。

## 历史迭代：基于 RK3562 实图的卡片外置进度（v3，已被 v4 替代）

本轮仅更新 report 的独立设计预览。根 agent 提供本机 `output/design-reference-20261113/` 内的脱敏 RK3562 复盘截图及只读几何；不将真实棋局截图复制到本目录。设计 agent 未连接实机、未变更生产代码或设备字体设置；`auth.html` / `auth.js` 保持不变。

- **真实画布**：1024×600。大浏览器中固定居中，不随窗口放大；小窗口等比缩小，保持七英寸构图。左预览仍为 `(16,70) 296×434`，列表仍为 `(328,70) 680×434`。
- **卡片宽高保留**：实机对局卡片是 **624×74**，不是早期草稿的 676×104。新稿完整保留 624×74；外部无背景的行容器为 680×94。两个报告块作为 `article.game-card` 的兄弟节点放在右侧 x=960 的现有 48px 槽位，各44px高、间距6px。左侧卡片竖直居中，不包住报告块。
- **三局可见**：行顶部为160、262、364，第三组底458；分页和导入仍在 y=460..504，底栏从518开始，不被遮挡。行高增加20px是两个44px触控块所需，卡片本身不加高、不加宽、不挤窄。
- **紧凑内容**：右侧短标签“普通/高级”＋百分比或“生成/已完成/排队/继续/重试”；详细手数留在所属卡片的状态区。进行中不变为按钮，其他状态仍可就地查看或发起。流光只在分析中出现，填充位置只随手数更新；低动态模式关闭流光。
- **删除保留**：原右侧垃圾桶槽位让给报告，删除入口移到左侧“选中这一局”标题右侧，44×44触控区；设计演示不会删除真实棋谱。原“查看棋谱/分析报告”入口保留。
- **Galaxy**：外置96px报告列＋10px间距；卡片保持上一稿 **416×104**，列表总宽为522px，从宽裕的左预览区让出空间，不挤窄卡片。其字体和外壳沿用既有 Galaxy 视觉。
- **刻意保留的差异**：合成示例棋局和棋盘、顶栏“设计预览·本地示例”与演示入口；删除入口迁移；三组行间距。均不假装是真实运行进度或真实数据。

推荐直接体验：[Kiosk 双档运行](index.html?demo=dual)、[Galaxy 双档运行](index.html?surface=galaxy&demo=dual)。v2 独立历史稿为 [index-v2.html](index-v2.html)。本轮只检查代表视口与关键进度语义，不重复生产测试。

代表截图：[Kiosk 默认状态](screenshots/kiosk-external-v3-1024x600.png)、[Galaxy 双档运行](screenshots/galaxy-external-v3-1440x900.png)。本地浏览器核对：Kiosk 三卡均为624×74、三个独立报告列均为48×94，最后一组底458、页脚y460；Galaxy三卡均为416×104、报告列96×94，无横向溢出。1440×900浏览器内Kiosk画布仍为1024×600，坐标(208,150)。运行节点为DIV、role=progressbar、无tabindex；aria百分比与fill百分比一致。`node --check preview.js` / `viewport.js`通过。脚本未报错；最初浏览器隐式 favicon 请求404已用本页空图标消除。用户视觉确认仍待进行。

## 历史迭代：右侧充电块（v2，已被 v3 替代）

本轮仅调整本目录 report 设计，`auth.html` / `auth.js` 保持上一轮原样；生产代码和部署未动。该历史版本现保存为 `index-v2.html` + `preview-v2.css` / `preview-v2.js`；下文尺寸是当时的设计假设，不是实机原始卡片尺寸。上一版完整隔离保存为 [index-v1.html](index-v1.html) + `preview-v1.css` / `preview-v1.js`，可独立打开，不会跟着新版样式变化。

- **密度**：Kiosk 1024×600 保留 296px 左棋盘框、680px 列表和 676px 卡片外宽；每卡 104px，右侧两块各44px高、间距6px，三卡完整可见（第三卡底454px，列表底458px），分页和底栏不遮挡。主字22px、辅助18px。Galaxy 1440×900 保持原732px左区域、420px列表、416px卡片宽度，同步104px卡高。
- **动态控件**：运行/继续中的块是非交互 `div role=progressbar`，没有 tabindex 或点击动作；显示“普通44%”或“高级68%”，下行显示分析状态及 n/N。填充、百分比文字和 aria-valuenow 使用同一整数百分比；轻微流动高光只表示正在工作，不冒充数据进度。
- **水位**：默认本地示例每次增加1手，只有 n 改变才更新水位；没有随机数或单独百分比动画。页面顶栏持续标“设计预览 · 本地示例”。推荐连续填充；分格电量仍按精确比例裁切，最后一格可以部分填充，不把44%伪装成整格50%。
- **其他状态**：排队停止流光；中断/失败保留水位并提供“继续分析”/“重试”；完成满格、停止光效、可查看。普通完成与高级进行始终共存。`prefers-reduced-motion:reduce` 禁止循环高光，数据仍可正常更新。左侧只保留总手数及“高级分析中”等简短状态，避免重复 n/N 或把进行中误写成报告完成。
- **直接体验**：[Kiosk 双档充电](index.html?demo=dual)、[Galaxy 双档充电](index.html?surface=galaxy&demo=dual)、[分格紧凑对照](index.html?demo=dual&variant=cells)。默认普通已完成＋高级运行；“演示”内可选双档运行和各中断状态。服务端中断续算仍是待确认增强项。

代表图：`screenshots/kiosk-charging-v2-1024x600.png`、`galaxy-charging-v2-1440x900.png`；两动画时刻分别为 `kiosk-charging-v2-frame-a/b-1024x600.png` 和 `galaxy-charging-v2-frame-a/b-1440x900.png`。真实本地 Chrome 检查记录：两尺寸卡片外宽与v1一致；Kiosk三卡104px且全部可见；所有报告控件44px；运行节点为DIV、没有tabindex；普通/高级文字与aria/填充一致；本地n从128→130、水位68%→69%；中断后保留69%且animation none；低动态下两运行块animation none、光效opacity0；无脚本错误。仅检查独立设计预览，未运行生产测试。

## 为什么接入这个围棋合集

权威入口为 [围棋界面设计集合](../kiosk-current-based-redesign-2026-10-14.html)，不是 `kiosk-unified/` 目录下不存在的 index，也不是用户提供的中国象棋类比。证据：

1. [统一改版规则](../KIOSK-UNIFIED-REDESIGN-RULES-2026-10-14.md) 开头明确把该 HTML 称为“围棋界面设计集合”。
2. 该 HTML 加载 `kiosk-unified/core.css`、`personal-review.js/css`、`report.js/css`、设置、成长、训练和后续会员章节，具备完整页面索引、旧实机参考与设计叠加。`kiosk-library-report-7inch.html`、`kifu-list-report-polish.html`、`analysis-report-v2.html` 是专题页。
3. 本轮仅在合集顶部增加“新增 · 报告进度与统一登录 v4”链接；原稿及原章节未被替换。此前 `phone-named-signup-2026-11-13/index.html` 保留原状，本目录登录稿为重大交互修订的新版本。

视觉来源：`kiosk-unified/core.css:3` 的 56px 顶栏、`:17` 的 82px 底栏；`personal-review.css:14` 的 296px/680px 分栏及 18/22/28px 层级；生产 `ui/src/kiosk-shell/go-tokens.css:14` 的青毡色值、`kiosk/pages/personalGamesReviewed.css:28` 的现行卡片与软键材质；`ui/src/kiosk-shell/fonts.css` 的霞鹜文楷及品牌字体。Galaxy 依据 `galaxy/components/layout/GalaxyTopBar.tsx:22` 的 52px 顶栏、`MainLayout.tsx:18` 外壳、现有登录稿记录的 216px 侧栏，以及 `ui/src/theme.ts:5` 的 charcoal/jade token。未参考中国象棋配色或布局。

设计主要是 **Operate** 表面：在所属棋局上选择和查看报告；不新增任务中心。ui-ux-pro-max 的自动生成配方与既有产品不匹配，因此保留现有已批准视觉系统，仅采用其触控≥44px、就地反馈、焦点与渐进表单规则。claude-design 用于独立可点击 HTML、源代码视觉复用及单推荐/单备选比较。

## 报告现状：逐项结论

| 项目 | 当前 HEAD 状态 | 证据与边界 |
| --- | --- | --- |
| 任务和逐手结果持久化 | 已实现基础，**不是仅内存或仅写 SGF** | `katrain/cron/models.py:246` 映射 `report_tasks`；`:307` 映射 `report_task_moves`，包含 winrate、score、visits、候选、ownership、grade、root_visits，`(task_id,move_number)` 唯一。普通旧路径 `report_analyze.py:355` 创建/更新手数行，`:372` 更新 analyzed_moves，`:373` 同事务 commit。收费路径 `:449` 创建结果行，`:454` 更新手数，`:455` 同事务 commit。粒度为每次最终局面分析结果，不是引擎内部每个 visit。 |
| RK3562/浏览器关闭，云端仍在线 | 源码支持云任务继续及客户端重读，**未实机验收** | `web/server.py:646` 的 board 初始化在 `:756` 建立 RepositoryDispatcher。`api/v1/endpoints/reports.py:480` 创建、`:609` 列表遇 dispatcher 时转发；`core/repository.py:479`、`:503`、`:511` 全走 `_remote_only` 的 cloud reports API，无本地报告回退。关闭盒端不会主动取消独立 cron job。 |
| 重开列表关联原任务 | 源码已有，卡片显示仍有缺陷 | `features/report/useReportTasks.ts:133` GET list+summary；`:188` 的 effect 启用即 refresh；`:219` 在有活动任务时每 2 秒刷新。`reportModel.ts:104` 按 `task.user_game_id`、report_type 重建卡片状态。无需依靠上次 React 内存保存 task id，也不因重新开页面自动 POST 新任务。账号/云连通恢复是前提。 |
| 旧/非收费 worker 中断后继续 | 已有旧路径；不是收费路径的证明 | `report_analyze.py:126` 启动 running→pending，`:160` 运行时 stale 处理；`:245` 从 DB 最大 move_number+1 读恢复点，`:303` 读取并在 `:329` 仅遍历后续局面。只检查最大手数，不是完整连续有效前缀校验。模型变更会拒绝混合续跑（`:305`）。 |
| 当前收费报告 worker 重启/中断后保留断点续算 | **尚有缺口，当前行为相反** | `_paid` 在 `report_analyze.py:27` 以 billing_version/operation_id 区分。启动恢复 `:140` 将收费 running 标 failed、提示退回授权；stale 路径 `:180` 同样处理。claim `:219` 增加 generation 后删除已有 move 行并归零；`_process_paid_task :422` 从 0..N 全部处理。收费 `/retry`（`reports.py:648`）需失败/退款状态并重新授权；`:712` 也清除已保存逐手行。不能把“已写过 DB”误当“会用断点继续”。 |
| Kiosk 列表真实逐手进度 | 部分已有，需修复档位覆盖与补齐设计 | `kiosk/pages/ReportsPage.tsx:647` 已把 running 的 analyzed/total 放在卡片。`reviewPresentation.ts:207` 的 rowState 先取 completed，普通已完成会遮住高级 active；`:216` activeDeep优先，仅一档活动水位；旧注释把有进度失败描述成可续算，不能覆盖新的收费行为。 |
| Galaxy 列表进度 | 已有进度条，仍需按两档独立比较 | `galaxy/components/report/ReportGameCard.tsx:68` 取 activeDeep 或 activeNormal，`:308` 渲染真实 analyzed/total 和 LinearProgress；完成档位按钮与活动进度可共存。并非完全缺失进度，不能重建整页。 |

手数口径：N 手棋需分析初始 position 0 和之后 1..N 共 N+1 个局面；UI 采用 `已完成 k/N 手`，仅提交初始局面仍为 0/N。普通与高级仅两档，各自独立。running 即使水位为 N/N，也仍须等待最终 completed 再开放报告；不能把初始局面额外算进 UI 百分比。设计未改变 visits、计价、权限、扣费或报告读权限。

用户关心的 RK 关闭/重开场景，现有云任务继续与列表重绑定源码已有支持，不能因云端 worker 故障策略不同就判定该场景缺失。确定缺口为 Kiosk 普通完成遮挡高级进度，以及跨平台来源字段/标签链路。云端 worker 中断后的收费断点续算是**单独待用户确认的增强项，不是本轮默认批准范围**。

“中断待继续”是该增强项的拟议状态，不宣称当前收费任务已支持；“继续分析”也没有承诺免费或免扣费。盒端关闭示例与执行分析的服务端中断示例在演示控件中分开。

## 来源现状：标签错误来自字段链路缺失

- 真实平台 ID：`golaxy = 星阵`、`fox = 野狐`、`ogs = OGS`，来自 `ui/src/kiosk/constants/platforms.ts:22`；对应 adapter 的 `platform_name` 分别在 `platforms/golaxy/adapter.py:894`、`fox/adapter.py:128`、`ogs/adapter.py:115`。语音“星阵/新阵镜”不推测为其他平台。
- `platforms/manager.py:450` 的星阵引擎开局已知 platform，`server.py:5422` 保存平台引擎局时 `:5444` 只覆盖 `source=play_ai`、玩家和执色，未写入平台字段。
- `core/models_db.py:1464` 的 UserGame 有 `source`、`game_type`（`:1482`），没有独立持久化 platform；`ui/src/api/userGamesApi.ts:8` 的 UserGameSummary 同样没有 platform。不是把现有 `game_type=free` 文案改一下就能可靠补齐平台来源。
- `kiosk/components/report/reviewPresentation.ts:131` 的 historyCardTitle 对 play_ai/free 返回“自由对弈”；Galaxy `ReportGameCard.tsx:40` 也把非 ranked play_ai 当自由对弈。跨平台引擎局由此落入自由对弈分类。
- 设计中有明确来源的示例分别为“跨平台 · 星阵”“跨平台 · OGS”“自由对弈”。不按对手名字/标题推断历史平台。未知旧行不能假装来源已找回；需要可信数据后再改标签。
- `platforms.ts:38` 注明野狐为当前不可用入口，故本稿不添加可开始野狐对弈的交互，也不把 adapter 存在当作设备已验证。

## 其他本地 worktree 与提交核查

相关工作树：`/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/review-platform-progress-20261112`，分支 `fix/review-platform-progress-20261112`，HEAD `8c02b98d7`（标题为 `initialize local reference lighting on bootstrap enable`，该提交本身与报告无关，并已为当前 HEAD 祖先）。其 `git status --short` 只有两份未跟踪计划：

- `docs/superpowers/plans/2026-11-12-review-platform-origin.md`
- `docs/superpowers/plans/2026-11-12-review-report-progress.md`

两份均明确待用户确认，实施任务未勾选；它们是已调查/待确认计划，**不是已实现待集成代码**。本轮检索相关 Git 历史未发现这两项的后续实现提交。当前收费 worker 的引入提交为 `160606c66`（2026-11-02，`authorize and fence complete paid reports`）；Kiosk 卡片标题映射最后相关提交 `467b4ce9c`（2026-10-19，`align history game cards`）。不把旧计划中的审核记录当作本轮开发授权或运行时验收。

## 已有测试的含义（本轮仅阅读，未运行）

- `tests/web_ui/test_report_analyzer.py:242` 的 `test_report_analyzer_resumes_from_existing_moves` 预置 position0，断言只调用 `[1,2]`，覆盖旧路径续跑；使用假的 KataGo 返回，不是断电设备验收。
- `test_report_analyzer.py:114` 覆盖旧模型 partial 拒绝混合续跑。
- `tests/web_ui/test_membership_reports_pg.py:414` 的 `test_automatic_worker_retry_restarts_the_entire_generation` 明确断言 `seen == [0,1,0,1,2]`、claim 后旧行清空，证明当前收费路径按整次重跑设计，不能作为收费续算通过证据。
- 同文件 `:133` 覆盖失败 prefix 全退后重试，`:195` 覆盖 claim generation 与旧 worker 晚到写入围栏。后续应复用这些高风险边界，不另造报告数据库、队列或计费系统。

## 历史本地设计核对（v1–v3）

以下为早期稿核对记录，最终布局与交互以本文顶部 v4 段落为准。

设计文件为纯 HTML/CSS/JS，`node --check` 通过；真实本地 Chrome 预览检查 1024×600 和 1440×900，无横向溢出；截图与交互只针对本目录独立预览。核对了普通已完成+高级分析中共存、模拟中断后继续保持同一棋局、盒端重开读取示例新水位、手机号验证后只补用户名、名称已存在才出现旧密码、更改用户名可回到无密码分支、Galaxy 无访客入口。没有运行生产测试。

主方案遵守既有 296px 预览与 680px 列表、软键、中文字体、品牌字、18/22/28px 层级；双档各自展示进度；Kiosk 的手数在所属棋局卡片内，百分比及操作位于卡片外侧对应档位。推荐连续填充，分格电量在“演示→卡片比较”切换；两种方案均在卡片外部右侧竖排普通/高级两个44px控件，不再用全宽逐档横条。无营销说明、计费单位或后台实现术语占用产品表单。

代表截图见 [screenshots/](screenshots/)：Kiosk 复盘/登录/补用户名与 Galaxy 复盘/同弹窗补用户名。剩余待确认是用户对设计和需求整体的确认；开发、运行时验收和发布均未开始。

设计自检：未采用 hero/营销卡片、默认科技渐变、装饰指标、装饰图标或独立任务中心；既有软键的微渐变只用于表现触控层级。推荐/备选改变信息占用和展开成本，未做仅换色的伪方案。已保留正常焦点与低动态偏好。所绘棋盘和棋局为明确标注的设计例子，不作真实数据证据。
