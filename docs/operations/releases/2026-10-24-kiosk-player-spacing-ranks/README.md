# Kiosk 棋手卡片间距与真实等级

本次只修改 Kiosk 双人棋手卡片及其展示所需的最小数据契约。保留落子、摆谱识别、纠错、时钟、提子、棋盘及操作按钮行为；Galaxy 未改动。

## 页面盘点与间距

自由对弈、升降级、邀请大厅对局、OGS、星阵引擎、本地普通回退、摆谱及大厅/星阵观战复用同一个 SVG 卡片表面与间距公式。专用本地面对面操作席仍保留原有整高矩形；棋谱列表、报告等小型姓名条不改成对局卡片。

原大厅观战可见斜缝约 30.671px，AI/邀请大厅参考约 6.864px。统一后，1024×600 的真实 React 页面在卡高25%、50%、75%处测得约6.78–6.87px，最大模块差异小于0.1px。测量对象是 SVG 可见路径/描边，不是 CSS box gap；装饰阴影不计入。保留 AI/大厅104px、摆谱76px、大厅观战136px高度；星阵观战使用104px同类卡片。星阵观战姓名22px、等级18px，并保留原时钟及操作区域。

## 等级来源与缺失例外

| 场景 | 权威来源 | 无数据时 |
| --- | --- | --- |
| 大厅对局/观战 | 当前场次、黑白席位的中央 `rank_label`，按 session 精确匹配 | 等级未知；不从 rung、姓名或旧缓存推算 |
| 自由/升降级真人 | 后端明确确认当前账号拥有该真人席位后，读取该账号天梯定级状态 | 等级未知；只有明确 placement 状态显示尚未定级 |
| 本地 AI | 对局固化的真实 AI 目录难度；缺失时才用该 AI 的估计难度 | 等级未知；绝不把 AI 难度赋给真人 |
| OGS | 当前平台 game_data 中已核实席位的等级 | 临时/缺失/无法确认的数值等级显示未知 |
| 星阵引擎 | 当前引擎等级目录的真实 level_name，仅 AI 席 | 平台未提供真人等级，真人显示未知 |
| 星阵观战 | 当前观战快照人物 rank | 等级未知，不阻断整盘快照 |
| 摆谱 | 原 SGF BR/WR；职业9p等原标签保留 | SGF 未写等级时未知 |
| 临时本地双人 | 没有账号或平台级别来源 | 两席均明确未知 |

后端区分真实账号 user_id 与引擎 UUID，排除 SGF 导入、研究、多人与平台局的账号席位归属。切换账号/场次立即丢弃旧等级；请求有8秒总截止、单请求、仅前台30秒轮询，走子不触发重复请求。缺等级、请求失败不影响棋局。独立等级标签不随长姓名被裁切；姓名保留可见开头及完整辅助名称。

## 审核与验证

实施前 Writing Plans 两轮独立 Astra Max 计划审核通过。最终代码与实际视觉审核 Approved、无剩余必须修复项，见[审核记录](../../../superpowers/reviews/2026-10-24-kiosk-player-card-spacing-ranks-code-astra-final.md)。真实 React 使用现有保存字体偏好，等待字体加载并稳定后核对1024×600截图、并排/叠加/差异、姓名、等级、内部滚动边界和主要操作区。

后端聚焦89项通过；平台 OGS 聚焦99项通过、1项既有不相关断言排除；前端13文件327项通过。最终 Astra 另独立运行89项后端与123项前端检查。仓库既有测试全局 mock 污染及一个旧 requestCount 参数断言未扩张修复，不宣称全量仓库套件通过。

发布采用已发布 develop 的完整受控 Python、十九路 policy 和同源 full/strict 静态，保护设备配置、身份、模型、标定、字体偏好和其他棋类。实际发布版本及设备回执如下；本地截图是隔离 fixture 驱动的真实 React 预览，生产代码不含业务模拟数据。

截图：[模块总览](screenshots/modules-contact-sheet.png)、[大厅观战前后](screenshots/pvp-spectator-side-by-side.png)、[邀请对局前后](screenshots/lobby-side-by-side.png)、[未知等级姓名](screenshots/after-lobby-unknown.png)、[长姓名](screenshots/after-lobby-long.png)。

## 发布结果

| 项目 | 已核实版本 |
| --- | --- |
| 功能分支与 published develop | `597f3a9b96cdafe92df5115d4d82b228b755d2c2` |
| Smartbox origin/main | `77e7f02fbb9202220389da295bca18599d1988d5` |
| vendor/katrain gitlink | 同上述 published develop |
| RK 实际进程 KATRAIN_BUILD_SHA | 同上述 published develop，PID `337544` |
| RK 实际严格入口 | `index-zRXho9zL.js` |

已先 fetch 最新 develop 并确认无冲突，推 feature 后将 develop 正常快进；Smartbox 从最新 main 的隔离 worktree 仅更新 gitlink 并推送。没有 force 或覆盖其他任务工作树。

从该已发布提交导出391个受控 Python、十九路 policy 与同源 full/strict 静态，共1189文件逐项哈希通过。发布前备份旧源码/静态/标记及 SQLite；当前462个配置、身份、模型、标定等文件哈希不变。只有围棋服务停起，Kiosk服务及围棋target状态保持；教程字体偏好和既有十九路派生/保留接口均验证保持。

旧应用 cookie 在服务重启后返回401，已通过设备真实“主页→围棋”恢复现有fan身份200，并回到原 `/kiosk/play`；没有读取或注入 cookie。真实当前中央 active-games 返回200，3局均具黑白rank_label，样本17级、10级、9级，故本次无需额外云端等级发布。

[设备回执](verification.json)、[原账号/页面恢复](browser-verification.json)、[实际原页截图](screenshots/rk-original-page-restored.png)和[文件清单](manifest.json)。设备 screenshot 是原对弈首页恢复证据；卡片效果来自上面的真实 React 预览与独立视觉审核。为保留用户状态，没有新建或进入对局、没有摆盘/标定/采集，也没有宣称完成邀请对局或硬件摆谱端到端验收。用户可直接在RK继续实机验收。

设备回滚目录保留在 `/mnt/data/smartbox-deployments/20261024-kiosk-player-spacing-ranks-597f3a9b9/`，包含 [rollback.sh](rollback.sh)、旧受控源码/静态、在线数据库快照与保护哈希。回滚未执行；只恢复本次代码/静态及标记，不覆盖当前数据库或标定。已清理本次上传包及解包候选，保留回滚；根分区约2.1GiB可用、数据盘约15GiB。

此回执提交只增加文档证据，单独保存于 evidence 分支；设备与Smartbox仍指向上述已经审核发布的 develop，不把回执提交误报为新的设备源码版本。
