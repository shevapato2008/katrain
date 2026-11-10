# Kiosk 01–21 实现截图索引

设计源：[2026-10-14 设计文档](../../design/kiosk-current-based-redesign-2026-10-14.html)。当前截图是 React 页面在 1024×600 的浏览器预览；需要登录、设备或业务数据的状态使用测试 fixture。表中的「本轮」指 2026-10-19 重新生成或复核的截图；「旧」指 2026-10-13 留档，**不能代表最新视觉验收**。页面存在和视觉符合设计是两项不同的判断。

设计文档的页码跳过 18。表中保留它实际使用的编号。

| 页码 | 页面 | 实现截图 | 证据状态 |
| --- | --- | --- | --- |
| 01 | 对弈首页 | [打开](../../../superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600/01-play--implementation.png) | 本轮重拍 |
| 02 | 自由对弈设置 | [打开](../../../superpowers/tracks/kiosk-go-play-ai/visual/02-setup-free/1024x600/02-setup-free--implementation.png) | 本轮重拍 |
| 03 | 升降级设置 | [打开](../../../superpowers/tracks/kiosk-go-play-ai/visual/03-setup-ranked/1024x600/03-setup-ranked--implementation.png) | 本轮重拍 |
| 04 | 本地对局设置 | [打开](../../../superpowers/tracks/kiosk-go-play-ai/visual/04-setup-local/1024x600/04-setup-local--implementation.png) | 本轮重拍 |
| 05 | 人机对局 | [打开](05-game-current.png) | 本轮重拍；四图脚本的旧参考指纹仍需更新 |
| 05a | 本地对局 | [打开](05a-local-game-current.png) | 本轮重拍；对局状态使用 fixture |
| 06 | 在线大厅 | [打开](06-lobby-current.png) | 本轮重拍；四图脚本仍使用旧选择器 |
| 07 | 平台选择 | 无独立运行页 | 现行路由重定向至 01，对弈首页承接平台入口；设计文档此页已过时 |
| 07a | 星阵扫码登录 | [打开](07a-golaxy-scan-current.png) | 本轮重拍；扫码状态使用 fixture |
| 07b | 星阵密码登录 | [打开](../reviewed-frontend-2026-10-19/golaxy-login-depth.png) | 本轮已有复核截图 |
| 08 | OGS 登录 | [打开](../reviewed-platform/ogs-login--implementation.png) | 本轮已有复核截图 |
| 08a | OGS 大厅 | [打开](08a-ogs-lobby-current.png) | 本轮重拍；连接和挑战列表使用 fixture |
| 09 | 星阵人机设置 | [打开](../../../superpowers/tracks/kiosk-go-shell-align/visual/07-09-platform/1024x600/09-platform-engine--implementation.png) | 本轮重拍 |
| 10 | 星阵人机对局 | [打开](../../../superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game/1024x600/10-platform-game--implementation.png) | 本轮重拍 |
| 11 | 训练营首页 | [打开](../reviewed-frontend-2026-10-19/training-reviewed-carousel.png) | 本轮已有复核截图 |
| 11a | 题型 | [打开](11a-categories-current.png) | 本轮重拍 |
| 12 | 单元 | [单元 Tab](12-units-current.png) · [错题簿入口](12-wrong-book-entry.png) | 本轮已有复核截图；旧四图参考指纹失效 |
| 13 | 题目列表 | [题目列表](../../../superpowers/tracks/kiosk-ui-redesign/visual/13-problems/1024x600/13-problems--implementation.png) · [错题 Tab](13-wrong-current.png) | 本轮重拍 |
| 14 | 错题簿 · 做题 | [打开](../reviewed-frontend-2026-10-19/training-reviewed-puzzle.png) | 本轮已有复核截图；旧四图参考指纹失效 |
| 15 | 棋谱库 | [打开](15-archive-current.png) | 本轮重拍 |
| 16 | 棋谱详情 | [打开](16-replay-current.png) | 本轮重拍，未分析回放态 |
| 17 | 摆谱 | [打开](../../../superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/1024x600/17-baipu--implementation.png) | 本轮重拍 |
| 19 | 我的对局 | [主页面](19-personal-games-current.png) · [报告菜单](19-report-menu-current.png) · [导入弹窗](19-import-current.png) | 本轮重拍 |
| 20 | 复盘报告 | [主页面](20-report-current.png) · [最后一个 Tab](20-last-tab-current.png) · [对局详情弹窗](20-report-details.png) | 本轮重拍；弹窗图为另一个状态 |
| 21 | 研究 | [主页面](21-research.png) · [设计并排对比](21-research-rail-side-by-side.png) | 本轮已有复核截图；旧四图参考指纹失效 |

## 补充页面和状态核对

设计文档在 22 成长之前共有 45 个条目，其中不少是同一运行页的状态，不应误算成漏开的路由：05+ 共用 `GamePage`；05b–05d 共用 `LocalConfirmGame`；07a+ 与 07b 共用 `PlatformLoginPage`；07c/07f 和星阵首页共用 `GolaxyHomePage`、`GolaxyPregameSetupPage`；08b 是 `PlatformLobbyPage` 的挑战状态；10a 共用对局页；17a–17d 共用 `BaipuSessionRoute`；职业棋局报告使用 `KifuReportDetailPage`；报告失败态和六个分析 Tab 使用 `ReportDetailPage` 的共享报告组件。本地观战有独立的 `PvpSpectatorPage` 和[本轮截图](pvp-spectator.png)。

07「平台选择」是唯一已取消独立路由的旧设计条目。星阵快速匹配、建房及邀请中尚未接通的外部能力，在现行页面明确显示不可用；它们不是已接通的后端流程。实机实体盘识别和 KataGo 执行仍需设备验收。本索引记录前端画面证据，不代表全部状态的视觉验收、生产部署或完整前后端联调。
