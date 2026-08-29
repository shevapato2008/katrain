# 三条小裁定（2026-08-26，只读代码，未改任何源文件）

仓：`/Users/fan/Repositories/katrain-kiosk-go-align`，分支 `feature/kiosk-go-shell-align`。

---

## D4 —— 手摆的局面要不要能生成复盘报告

**先更正题面的一处事实。** 屏 17 摆谱**不是**「让用户在盘上手摆局面」。
`katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx:21-25` 写死了它的来源：棋谱库里挑一份 SGF，
或导入一份本地 `.sgf`，缓存到 localStorage；屏 17 只是**重放**那份既有棋谱，灯指下一手、人摆、相机采 YOLO 训练帧
（`BaipuSessionPage.tsx:52-57`）。整条链**零 `user_games` 写入** —— `katrain/web/api/v1/endpoints/baipu.py`、
`katrain/web/core/baipu_capture.py`、`katrain/core/baipu.py` 三个文件里 `UserGame` 0 命中；写方只有
`user_game_repo.py:79/125`、`game_repo.py:52`、`ai_ladder_ranked.py:1437`。
**真正的手搭局面在屏 21 研究**（`ResearchPage.tsx:260` 的 `board.serializeToSGF()`）。
`scope.md:1402-1406` 早把这条登记成「本轮最重的一条缺口」，且把比赛谱和手搭局面并列 —— 那才是这题的对象。

**零着法喂进去会怎样（查过，不是推演）：不会崩，但会产出一份空报告。**
`cron/sgf.py:parse_game` 返回 `moves=[]` + `initial_stones=[…]`；`cron/jobs/report_analyze.py:206`
的 `range(0, 0+1)` 走一轮，`played=[]` 连同 `initial_stones/initial_player` 送 KataGo，落一行
`ReportTaskMove(move_number=0)`，任务照常 `completed`。屏 20 上：`reportStats.ts:43` 的 `accuracy` 在
`counted=0` 时是 `null`（诚实，不是 0），失误/妙手都是 0，`winrateSeries` 只有一个点，逐手列表空 ——
一张空曲线加三个「—」。**成本不在盒子**：`endpoints/reports.py:18-21` normal=500 / deep=2000 visits **每手**，
跑在 cron 侧 KataGo（`cron/config.py:39`，默认 8002，云端 GPU），瓶颈是 `CRON_REPORT_CONCURRENCY=3` 的云端队列。

### 裁定：**有条件地做。门槛落在「手数」，不落在「是不是手搭的」。**

1. 门槛 = **主线着法 ≥ 20 手**（判据就是 `parse_game(sgf).moves` 的长度，前后端同一个函数）。
   低于它，准确率的加权平均和 `keyMoves(limit=3)` 都在报告一件没发生的事。
2. **门槛以下撤掉入口，不灰着** —— 「手数不够」不是暂时不可用；同一份局面再摆一颗子就是另一份局面。
   而且门槛以下那条路本来就通：屏 21 动作区第 5 颗「全局分析」做的就是会话内 scan。
3. 落地 plumbing 已经全在，**不用动 `ReportsAPI.create` 的签名**：`POST /api/v1/user-games/` 已经收
   `source:'research'`（`endpoints/user_games.py:22`）和 `category:'position'`（`:33`；列与索引见
   `models_db.py:722/737`）。做法是「先存成 `category='position'` 的 user_game，再用它的 id 建报告任务」。
4. **一处必配，不做就别做第 3 条**：`useReportTasks.ts` 和 `ReportsPage.tsx` 今天**一处都不传 category 过滤**
   （全 src grep 0 命中）⇒ 不加过滤，手搭局面会混进复盘列表。

---

## D5 —— 屏 21「领地」板块留不留

### 裁定：**留，一行不改。**

1. **数据不是编的。** `ResearchPage.tsx:221` 是 `const raw = turn?.ownership`，取自 `API.quickAnalyze` 的响应；
   `:222-229` 只把一维数组 `slice` 成方阵，零插值零估算。画它的是共享件
   `components/live/LiveBoard.tsx:454-462`（按 `-1..1` 上色）。⇒「前端自己估 = 在编数据」这条顾虑不成立。
2. **不多花钱。** `ResearchPage.tsx:150-153` 的注释我核过是真的：ownership 和候选着法在**同一个** `quickAnalyze`
   响应里，`showTerritory` 只 gate 渲染（`:553-554` `ownership={showTerritory ? ownership : null}`）。开关它零请求。
3. **稿子画了它，只是画在别的屏。** `go-kiosk.tmpl.html:1993`（屏 05 对局）和 `:2292`（屏 10 星阵）都有
   `<button aria-pressed="true">…领地</button>`，实现里对应 `GameControlPanel.tsx:244-245`。
   所以屏 21 这一颗不是新发明一个概念，是把同一个概念补进唯一缺它的那屏 —— `scope.md:1338` 那条登记
   （「形势图对手搭局面没有替代路径，而它连一次请求都不多发」）今天逐字仍然成立。
4. **「照抄另外三家」这条判据在这里不适用。** `smartbox-software/{chess,xiangqi,gomoku}/ui/src/` 里根本没有
   research/分析屏（只有 `review/`），没有对应模块可抄；而且领地是围棋独有概念。
5. **撤掉的代价是 `scope.md:1407-1408` 自己写的**：手搭局面再也没有形势判断的路径。
   这条和 D4 咬合 —— D4 门槛以下（<20 手）的局面，形势判断**只剩这一条路**。

可选的一处小改（不做也成立）：把这颗键的 label 与屏 05 那颗对死成一个常量，别让同一功能在两屏各写一份字面量 ——
同一形状 `scope.md:1166` 附近已经登记过一次（野狐卡那句「即将上线」）。

---

## D7 —— 棋盘木纹贴图这一轮引不引（= `scope.md` 里的 D6）

### 裁定：**引进。D6 那条登记的两个前提，今天只剩一个成立。**

D6 原话（`scope.md:226` / `:976-977`，代码里在 `kiosk-shell/go-screens.css:121-124`）：
「那张图不在共享资产包、不在 MANIFEST 管辖内，抄它等于往仓里塞一份**没人核的二进制**」。

- **前半句仍然对。** `shared/kiosk-shell/assets/` 只有 `brand/ fonts/ icons/ tokens.css`；
  `shared/kiosk-shell/MANIFEST.sha256` 里 `wood|oak|board` 零命中。贴图只活在四份
  `sample-*/board-assets.json`（data URI：oak 15120 / darkwood 14820 字符 base64）。
- **后半句是错的。** 同一份字节早就是三家的**生产资产**：
  `smartbox-software/{chess,xiangqi,gomoku}/ui/src/assets/board/darkwood_512.jpg` 三份**同为 51733 字节**、
  `oak_512.jpg` 三份**同为 55247 字节**。来源写在 `xiangqi/ui/src/skins.tsx:11`：**Poly Haven CC0**。
  `xiangqi/ui/src/shell/KioskBoardFrame.tsx:2` 的注释直说「**已经上板的**木纹贴图（darkwood_512.jpg）」。
  ⇒ 它不是没人核的二进制，是四家里三家在用、许可清楚、已上板的那一份。
  Fan 2026-08-20 的授权判据（`scope.md` §7）恰恰是「去看那三家同一个模块怎么做的，照做」。

**成本：闸不会红。** `katrain/web/ui/scripts/verify-kiosk.sh` 全文**没有体积闸**（末尾只 `du -sh` 打印一行），
三条闸查的是 three.js / `/galaxy/` / 非 board 的 live API。两张图共 107KB，对 RK3562 2G 不是问题（三家已在同一块板上跑）。
**落点不是 `kiosk-shell/MANIFEST.sha256`** —— 那份 hash 全部抄自上游（`kiosk-shell/README.md`），
这两张图不在上游清单里，塞进去等于伪造「和上游一致」。正确落点是 `src/kiosk/assets/board/`，走 Vite import，与三家同构。

**不引进的代价（真代价，写明是哪几屏）：**
稿子 `.kiosk-board` 用 `--darkwood`（`go-kiosk.tmpl.html:69`）、`.kiosk-mini-board` 同（`:70`）、
落子区由 `paintGo` 从 `--oak` 取纹理贴进 SVG（`:2392-2393`）。数出来是 **17 屏**：
整盘 12 屏 **02/03/04/05/09/14/16/17/18/20/21/25** + 迷你盘 5 屏 **01/11/15/19/23**。
这 17 屏的四图在盘面区域**永远对不齐**，而盘是布局 A 上最大的那一块。
`visual/05-game/1024x600/05-game--side-by-side.png` 上肉眼直接可见：稿子那盘有木纹、实现是一层平渐变，
且实现明显浅一档（`scope.md:969` 实测同一像素 (192,154,101) vs (206,174,121)，屏 04 / 屏 09 两处一模一样）。

---

## 需要 Fan 本人回答的

1. **贴图要不要顺手推给上游共享资产包 + 上游 MANIFEST。**（`scope.md:977` 那句「请 Fan 定」问的就是这个。）
   我上面的裁定是「本仓照三家的做法自己收一份」，这一步不用等他；但四家共用一处、由上游清单管辖，是他的事。
2. **D4 门槛数 20 是我定的**，判据可判定（`parse_game(sgf).moves.length`），但不是从别处抄来的 ——
   它答的是「三个统计量到几手才有意义」。若他有别的数，改一个常量即可。
