# 摆谱改摄像头自动推进 · 设计说明(2026-09-23)

## 起因(Fan 原话)

> 棋谱使用实体棋盘摆谱功能的时候不要每走一步都要按屏幕上的确认键啊。太麻烦了。应该使用摄像头确认。复用对弈模块的摄像头识别方法。

对屏 17 的六条:(1) 确认落子去掉;(2) 虚手没用去掉;(3) 完成没用去掉;(4) 右上灯泡是什么;
(5) 加 AI 支招,与对弈页的 AI 支招对齐;(6) 加试下,按下保持,选中时摄像头不识别,随便摆、推演。

Fan 拍板的三件(AskUserQuestion,均取推荐):
- 试下结束 → **灯引导复原**(蓝灯拿走、红/绿灯放上,认到复原自动接着摆)。
- AI 支招 → **和对弈页一样**:候选卡 + 白灯闪候选点;开着时暂停识别;试下中与访客不可用。
- 摄像头用不了 → **临时露出「确认落子」**并写明原因,恢复后自动收起。

设计稿:artifact `e4d3c7ef` 第 37 版,smartbox `feat/kiosk-go-kifu-list-design-2026-09-23` `df8d78b8b`,
屏 17 / 17a / 17b / 17c / 17d 五帧。

## 行为

整页只有两个识别状态,外加两个「暂停」叠加态:

| 状态 | 识别 | 灯 | 离开条件 |
|---|---|---|---|
| **AWAIT**(17)等下一手 | 期望盘面 = 谱上第 k 手之后;落子检测开 | 下一手一颗(红黑 / 绿白) | `move_confirmed` 坐标 **且颜色** 等于第 k+1 手 → 推进;不等 → SETUP(第 k 手局面) |
| **SETUP**(17a)把盘面摆对 | `setupMode(target)`;落子检测关 | 缺的点目标色常亮、多的点**蓝灯闪** | `setup_complete` → AWAIT |
| **TRY**(17b)试下 | `visionPause(true)`,落子检测关 | 全灭 | 再按「试下」→ SETUP(第 k 手局面) |
| **HINT**(17c)AI 支招 | `visionPause(true)` | 候选点白灯(`hint`) | 再按「AI 支招」或 30 s → 回到进入前的状态,重新点灯 |

进入 SETUP 的五种来源:入场(盘上有残子,**必须**先走一次 setup —— 监视模式从 UNBOUND 起,不走 setup 永远不报落子)、
提子(推进后 target = 第 k+1 手局面,被提的子在盘上 ⇒ 多)、放错(target = 第 k 手局面,错的那颗 ⇒ 多)、
撤回(屏上立刻 k-1,target = 第 k-1 手局面)、退出试下。

SETUP 卡住的出口:整盘逐子精确匹配,中后盘一颗子认不稳就可能一直对不上。**进 SETUP 10 秒还没对上**,
动作区最前面临时露出「摆好了，继续」:读 `GET /api/v1/vision/detected-board` → 以它为目标再 `setupMode`
(当帧即对上)→ 对上后按 AWAIT 推谱上局面。

摄像头可用的判据照抄死活题页(`TsumegoProblemPage` 的 `physicalAvailable`):
`visionStatus.enabled && recognitionReady && geometryConfirmed`(几何 ready + session_calibrated,或 disabled)。
不可用 ⇒ 手动兜底(17d):「确认落子」在第一格 + 原因写在待摆卡(没接摄像头 / 需确认标定 / 标定失效 / 正在连接)。

采集机(`collect=true`)**整条不变**:手动确认 + 拍照,不走识别。

## 动作区与页控条

- 上线态:`撤回上一手 · 试下 · AI 支招`;兜底态在最前多一格「确认落子」(`arrow-right`);SETUP 卡住时多一格「摆好了，继续」。
- 「完成」删:摆完自动 `clearProgress`,离开走返回。「虚手」本来就没做。
- 「重新点灯」留在页控条右上,图标 `lightbulb` → `arrows-clockwise`(灯泡让给 AI 支招)。
- 撤回:不再弹「已撤回」确认框 —— 屏上立刻退一手,灯引导把盘面摆回去。

## 识别层的约束(只读核验,2026-09-23,依据见 agent 报告)

后端**不改**。前端必须守:
1. 入场先 `visionMonitor(true)` 再 `setupMode`;`/ws/vision` 连上之前不发(否则空盘的 setup_complete 丢了)。
2. `move_confirmed` 只带 `{row,col,color}`,worker 不查合法性不查颜色 ⇒ **坐标与颜色都要页面自己比**。
3. 改期望盘面之前先 `moveDetection(false)`;提子一律走 SETUP,**不推提子后的局面给 expectedBoard**
   (那会把还在盘上的被提子当成新落子)。
4. 下一手那颗灯**不做屏蔽**(屏蔽会让落在灯上的子永远不报);收到目标点的 `move_pending` 先熄那颗灯
   (红灯压在黑子下会被读成 `led_red` ⇒ 认不出子),3 s 没确认再点回来。
5. 退出试下 / 支招的顺序:`moveDetection(false)` → `setupMode(target)` → `visionPause(false)`,**依次 await**
   (解除暂停不会重建基线,试下时摆的 1–3 颗会被当成落子)。
6. 卸载时清场:`moveDetection(false)`、`visionPause(false)`、`visionMonitor(false)`、`LedAPI.clear()`。
7. 识别状态是全局单例、无归属;`illegal_change` / `ambiguous_stone` 在监视模式下是噪声,忽略。

## AI 支招

`POST /api/v1/analysis/quick-analyze`(无会话;盒上走本机 KataGo):`moves` = 谱上前 k 手的 `[color, gtp]`
(`setup` 步走 `initial_stones`),`komi` / `rules` 取 `meta`,`max_visits` 200。回来的胜率 / 目差是**黑方视角**,
按走子方翻转(`ResearchPage.toRows` 同一口径)。取前 3 手。要登录(`get_current_user`),访客灰 + 原因。
