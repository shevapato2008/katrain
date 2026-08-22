# galaxy 全站风格统一 · 实施计划（2026-08-21）

分支 `feature/galaxy-style-unify`，基线 commit **fd3de2b6**。

**权威文档**（冲突时按此顺序）
1. 设计：`docs/superpowers/specs/2026-08-06-galaxy-board-template-ladder-design.md`
2. 范围：`superpowers/tracks/galaxy-ui-redesign/style-unify-scope.md`
3. 验收：`superpowers/tracks/galaxy-ui-redesign/visual/live-template/visual-review.md`
4. 可点原型（本轮定稿）：Artifact `a26b02fd-e89f-47f0-a5f8-0cf0aa35289e`

同目录的 `design.md` / `plan.md` **作废**，只当背景读。

## 0. 本轮的性质

**纯表现层搬运。** 不改后端契约、不改业务逻辑、不动 `src/kiosk/**` 的页面。
任何需要改 API 的发现 → 记进「待议」，不顺手改。

## 1. 原型 ≠ 现状：四处「我画错了，不是产品要改」

做之前先钉死，否则会照着原型的错去改真代码，那才是真的丢按钮。

| 原型里的样子 | 真实代码 | 结论 |
|---|---|---|
| 研究室「停一手」出现两次 | `ResearchToolbar.tsx:180` 只有一个 | **不动**，不存在的重复不许「修」 |
| 摆黑/摆白 是同一个灰点，交替是循环箭头 | `ResearchToolbar.tsx:51/66/81` 本来就是黑子/白子/黑白相叠 | **不动** |
| 变化图 编号/大写/小写/图形/橡皮 是 MUI 图标 | `BoardEditToolbar.tsx` 本来就是 `123 / A / a / △ / ✕` 字形 | **不动** |
| 每页都有「自动跟进」，还是带文字的第二行 | `PlaybackBar.tsx:195` 只在 `isLive` 渲染；复盘两页根本没传 | 只改**一行装完**，跟进逻辑不动 |
| 右栏「统一 320，取消 320/340/380 三档」 | spec §2.3 明写三档，§3.3 明写「1440×900 右栏 340px」 | **按 spec，三档保留**。原型那条是我自己简化的，与设计权威冲突，作废；`BoardPageShell` 不动。1440×900 下棋盘由高度定死在 828，右栏 320 还是 340 都不影响棋盘 |

## 2. 闸：控件账本

`superpowers/tracks/galaxy-ui-redesign/audit_controls.mjs`
用 TypeScript 编译器 API 静态扫 TSX，逐个记下可点控件的**可及名 + 类型 + 有没有 handler**。
可及名取值顺序：`aria-label` → `title` → `label` → `placeholder` → 子文本 → 外层 `<Tooltip title>` → 子图标名。
已扣掉三类误报：选项类控件的 handler 挂在父 `Select/Tabs/ToggleButtonGroup` 上、整行可点时里面的图标键、
`disabled` 的骨架占位。

```bash
# 基线（fd3de2b6 上跑出来：59 文件 / 275 控件 / 0 可疑）
superpowers/tracks/galaxy-ui-redesign/controls-baseline.json

# 每页改完必跑，判据：丢失 0，空按钮 0
node superpowers/tracks/galaxy-ui-redesign/audit_controls.mjs --diff fd3de2b6 <改过的文件...>
```

**判据**：`丢失 0 类 / 空按钮 0 个`。控件「新增」允许，但每一条都要在提交信息里说清是设计要求的哪一条。
名字取不出来的动态文案控件（64 个）靠**出现次数**守：数量掉了同样报丢失。

这条闸只管「有没有」，**不管「能不能用」**——那归每页的真浏览器验收。

## 3. 步骤

### S1 共享件（三处真改动，先做，因为六个页面都要用）
- `components/live/PlaybackBar.tsx`：控件收窄到 320 右栏内宽（~288）一行装得下 —— 小键 30 / 播放 42 /
  跟进 30 / 间距 2 / 手数 .74rem。现有的 `@container board-rail (max-width:340px)` 换行断点要跟着降，
  否则新右栏必然命中。**kiosk 五个页面共用这个文件**，`touchSized`（48px 触摸档）分支单独量一次。
- `components/tsumego/TsumegoBoard.tsx`：加 `showCoordinates?: boolean`，**默认 `true`** ——
  kiosk 死活题页一行都不用改。（现状 `:197` 无条件画坐标。）
- `galaxy/components/layout/ContentPageHeader.tsx`：`parentLabel` / `parentTo` 改可选，
  根级页面（Dashboard）只留标题（spec §2.4）。加可选属性不影响 `AiSetupPage`。

出口：`tsc -b` + `npm run build` + `npm run build:kiosk-2d` + `vitest run` 四绿。

### S2–S7 六个棋盘页（一页一闭环，顺序按 scope 决策一）
`ResearchPage` → `TsumegoProblemPage` → `report/ReportDetailPage` → `KifuLibraryPage` →
`GameRoomPage` → `tutorials/TutorialFigurePage`

每页固定五步，**不做完不进下一页**：
1. 迁 `BoardPageShell` + `ModulePlate`（图标左置那种），右栏三段：模块牌 / 中段（唯一可滚）/ 动作区；
   棋盘上方不留任何东西；右栏定宽 320。
2. 控件账本 diff：`丢失 0 / 空按钮 0`。
3. **承重实测**（真浏览器 1440×900 / 1024×768 / 430×880）：先把数据造到会溢出，
   先写死关系式再读数，具体像素只记录。每页按自己那条盒子链重写关系式，
   **不照抄** `s0-loadbearing-checklist.md` 的条目。「能不能滚」归这一关。
4. 四图对比（参考图 / 实现截图 / 并排 / 叠加+差异），三档视口齐全。
5. 你确认。

### S8 十二个内容页（只换页头，不动承重链）
`Dashboard`、`PlayMenu`、`HvHLobbyPage`、`live/LivePage`、`report/ReportsPage`、
`TsumegoCategoriesPage`、`TsumegoLevelsPage`、`TsumegoListPage`、`TsumegoUnitsPage`、
`tutorials/TutorialLandingPage`、`tutorials/TutorialBooksPage`、`tutorials/TutorialBookDetailPage`

单行布局：**左上角返回箭头图标键 + 标题**（2026-08-22 裁定，上一级简称只进无障碍名）。英文 eyebrow / 面包屑 / 长副标题 / 状态说明 / chip
一律不进页头，要留的下沉到正文第一个业务区。合成**一张对比板**一次确认，不逐页取图。

### S9 收口
`tsc -b`、`npm run build`、`npm run build:kiosk-2d`、`vitest run`、eslint 边界规则；
kiosk dist 体积对照**同一 commit 上现跑的一次构建**（不拿磁盘上现成的 dist 当基线）。
全量控件账本 diff：`--diff fd3de2b6` 覆盖 59 个文件。

## 4. 本轮的默认裁定（没单独问，按这个做；要改说一声）

1. **教程变化图的「原书页对照层」**（棋盘左侧 34%，可收起；竖屏降级到右栏第一节）是原型里新加的，
   spec 没写。按原型做 —— 原书页必须和棋盘并排才能核对，塞进右栏等于没用。
2. **`live/LivePage` 归内容页**：它左边有棋盘预览和播放条，但主体是列表。按 scope 只换页头，
   不上 `BoardPageShell`。
3. **死活题不接进度 API**：你已明确本轮不改后端，取「不接进度」那一支。

## 4.5 2026-08-21 插队修的可用性缺陷（研究页 L2/L3 打不开）

现象：测试服 `go.sailorvoyage.top/galaxy/research` 点「开始研究」永远停在
「正在分析棋局 / 正在连接研究会话…」。本机 127.0.0.1 却是好的。

**三个叠在一起的原因，缺一个都到不了 L3：**

1. **鉴权头没带。** 后端 72 个端点挂 `Depends(get_current_user)`；
   `box_sso.resolve_http_token` 非严格档是 `cookie or header`，而那块 `sb_token`
   cookie 只在 `hostname == 127.0.0.1` 时才发（`auth.py:_issue_loopback_sso_cookie`）。
   于是本机靠 cookie 一路绿灯，换域名就整片 401。
   修法**不是逐个调用点补 token**，是 `api.ts` 加 `authHeaders()`：没显式传 token
   就从 localStorage 兜底；严格盒端 SSO 例外（那档故意不持有 token，只走 HttpOnly cookie）。
   非严格档 cookie 优先于 header ⇒ 盒端/本机行为不变。
2. **会话建的时候没有主人。** `useResearchSession` 用四个手写 `fetch` 建会话，
   `POST /api/session` 是 `get_current_user_optional`，没凭证就把 `session.user_id`
   建成 `None`；随后 `/api/state` 的 `guard_session_reader` 要求
   `current_user.id ∈ {user_id, player_b_id, player_w_id}` ⇒ **403**，
   `gameState` 永远拿不到，进不了 L3。全部改走 `apiPost`。
   教训：**建资源和用资源必须是同一个身份**，只补「用」那一半会从 401 变成 403。
3. **UI 把失败演成了加载中。** 轮询是 `catch {}`，401/403 全吞，只剩一条不确定进度条。
   现在连续失败 5 次就报「无法获取分析进度 · HTTP xxx」并给「重试」。

**闸**：`superpowers/tracks/galaxy-ui-redesign/audit_auth_headers.py`
（后端需鉴权端点 × 前端调用最终会不会带 Authorization；已做变异验证：
拿掉一处 `authHeaders` 会红，还原会绿）。

**顺带修掉的承重缺陷**：`BoardPageShell` 的 stage 是 `display:grid` 但没写显式行列，
只有一条 `auto` 隐式行 ⇒ 子元素 `height:100%` 没有确定基准、退化成 auto ⇒
旧版 `Board`（`components/Board.tsx:97` 取 `min(width,height)`）量到的是自己画出来的
高度，越量越大：1280×640 下算出 704 的方板，把 588 高的区域撑破、整个 shell 开始滚。
加上 `gridTemplateColumns/Rows: minmax(0, 1fr)` 后 704 → 568；
L1 与已批准的 `LiveMatchPage` 四档实测数字**一个没变**（828/684/399/568）。

## 4.6 2026-08-21 两个环境的发布记录

**落地路径**：`feature/galaxy-style-unify` 先合入 `origin/develop`（快进到 `a930c6c1`），
再由 `release/ucloud-20260805` 合入 develop（`65677ce5`）。相对上一版生产镜像，
本次改动**只有前端 + i18n + 文档**：`git diff --name-only e3f50c43..a930c6c1` 里
没有任何 `.py`、没有迁移、没有 schema。

**发布前砍掉的两处投机改动**：`TsumegoBoard.showCoordinates` 与
`ContentPageHeader` 的可选 `parentLabel/parentTo` 当时都还没有任何调用方
（前者是给 S2 死活题页备的，后者是给 S8 内容页备的）。默认值都不改行为，
但「先发到生产再等消费者」正是「最小实现」那条规则要挡的事,已 revert,
到 S2 / S8 各自那一步再随消费者一起加。

**测试服 go.sailorvoyage.top（home-ubuntu）**

- 走 `docker compose up -d --build katrain-web`。构建一度失败于
  `proxyconnect tcp: dial tcp 127.0.0.1:7890: connect: connection refused` ——
  docker 的 systemd unit 里写死了这个代理，而它没在跑；nvcr.io 直连是通的
  （`curl --noproxy '*' https://nvcr.io/v2/` → 401）。改 unit 要
  `systemctl restart docker`，会把这台机器上所有容器（katago-gpu0/1、postgres、
  smartbox-platform……）一起弹掉,代价不成比例。改用一个临时的**直连穿透代理**
  占住 7890,让 daemon 的配置成立;构建完即杀掉并删文件（已核实端口空、进程无、文件不在）。
- `.mo` 是 gitignore 的,而 develop 的 `Dockerfile.web` 不编译它（release 分支的会）,
  所以本机编译后 rsync 那 11 个 `katrain.mo` 进构建上下文再构建。
- 实测：`/api/translations` 951 条（原 950），`research:progress_failed` cn/en 各就位。

**测试服上的真浏览器走查（这条是修复的判据）**

Mac 的代理是 fakeip，`/browse` 的 SSRF 闸会把 `go.sailorvoyage.top` 判成云元数据 IP 拒绝加载，
于是改走 ssh 隧道到那台机器的 8001，用主机名 **`localhost`** 打开 —— 关键在于
`SSO_LOOPBACK_HOST = "127.0.0.1"`（`auth.py:32`），`localhost` 不等于它，
**正是出问题的那个条件**。同一隧道做过对照：

- `POST /api/v1/auth/login` 经 `localhost` → 200，**无 `set-cookie`**
- 同一请求经 `127.0.0.1` → 200，**发 `sb_token` cookie**

登录后页面上 `document.cookie` 为空、`localStorage.token` 存在（即旧代码下必然全 401），
点「开始研究」后四个请求全部 200：`/api/session?mode=research`、`/api/analysis/scan`、
`/api/state`、`/api/analysis/progress`，页面进入 L3（AI 推荐 / 走势图 / 返回编辑）。
控制台 0 错误，网络里 0 条 401/403。截图存在会话 scratchpad 的 `deploy-verify/`。

**Fixture（创建时就写好删除条件）**：测试服上注册了账号 `styleunify_probe`（id 15）。
**删除条件**：本赛道在测试服上的验收结束即删；它只存在于测试服库，生产库没有。

**生产 modelstella.com（ucloud-v100）**

按 `docs/operations/ucloud-migration-runbook.md` 的流程发布，细节记在那份文档的
「2026-08-21（当日第二次）」一节（镜像 ID / 回滚锚点 / env 单行改动 / 备份与豁免判据 /
容量闸的明示越过 / 变异验证 / 容器不变量 / 外网实测）。这里只记一条与本赛道直接相关的：
生产入口 chunk `/assets/index-xPv7qGZG.js` 与本机已验证构建的同名文件 **SHA-256 逐字节相同**
（`ba566bd4…`）——chunk 名是内容哈希，所以这不是「大概是同一版」而是同一份字节。

**生产上没做登录态走查**：在生产建探针账号属于生产数据写入，按用户级规则要单独授权。
需要的话给一个可用账号，或者授权在生产建一个探针账号，我补这一步。

## 4.7 S2 死活题页：两处「按规范不按稿子」与一笔要还的债

**规范 §2.4 与冻结稿冲突两处，按授权顺序取规范：**

| | 冻结稿 | 当时的实现 | 结局 |
|---|---|---|---|
| 返回 | 标题左侧的 `←` 图标键 | 右侧「← 死活」带简称 | **2026-08-22 Fan 裁定按稿子做**：返回键一律在右栏左上角，规范 §2.4 已按裁定改写；`ModulePlate` 改一处全站生效 |
| 状态 | 页头右挂一枚「黑先」chip | 留在中段「本题」段 | **维持**：裁定只涉及返回按钮，§2.4「chip 一律不进页头」那半句没被推翻，继续有效 |

**要还的债：工具格按钮现在有三处实现。**
`RightSidebarPanel.tsx` 的 `ItemToggle`（对局室，Fan 指的那个参照物）、
`ResearchToolbar.tsx` 的 `ToolButton`（研究页）、以及新的共享件
`galaxy/components/board/ToolGridButton.tsx`。前两处都是**挂 onClick 的 `<div>`**：
键盘到不了，控件账本也看不见它们（账本新增的那条「未登记的疑似包装件」提示会列出来）。
本次没有顺手折叠，因为研究页已经确认过、对局室归 `GamePage`（拷贝目标，不许动）。

**关掉这笔债的步骤（放在 S9 收口）**：把两处都换成 `ToolGridButton`。那是纯 DOM 变更，
sx 不动则像素不变，但要各补一张工具格截图，且动 `RightSidebarPanel` 前要先问 —— 它是
`GamePage` 的面板。折叠之后账本能第一次看见那 20 个控件（研究 12 + 对局室 8）。

## 4.8 2026-08-21 galaxy 地板字体（commit 5ff29e43）与一笔**必须还**的取图债

Fan 在对照台上指出死活题页四个工具格键的中文不是霞鹜文楷。根因比「ButtonBase 不套
`typography.button`」更靠上一层：**galaxy 从来没铺过自己的地板字体**。`theme.typography.*`
只能到达在自身根样式里展开了某个 variant 的 MUI 组件；`ButtonBase`、裸 `span/div`、
SVG `<text>` 只能沿 DOM 继承，而继承链顶端的 `<body>` 是**外层** zenTheme 的 CssBaseline
画的（`AppRouter.tsx:30-31` → `theme.ts:43` 的 `'Manrope', sans-serif`，零 CJK；且 Manrope
全仓没有 `@font-face`）。修在 `.galaxy-root`（`GalaxyApp.tsx`）—— 它本来就是规范 §4.1 说的
locale 作用域节点，已挂 `data-language` 与 `font-synthesis:none`，唯独漏了字体栈本身。
取 `galaxyTheme` 的值不写死，locale 门（`galaxy/theme.ts:8`）原样生效。

顺带同类五处：`ResearchPage` / `KifuLibraryPage` 的 sx 写死 `'IBM Plex Mono', monospace`，
其中四处字符串夹着中文，走的是 monospace 的 CJK 回退；改成在后面追加 galaxy 字体栈。

> ### ✅ 已还（2026-08-22）：死活题页四图已重取
>
> 原计划排到「测试服重新部署时一起做」，但 2026-08-22 因返回键裁定本来就要重取全部实现图，
> 顺势一并还清 —— 现在 `implementation` 系列已经带着字体修复。**下面是原始债务记录，留作依据。**
>
> ### ⚠️（原记录）死活题页四图取于字体修复之前
>
> `superpowers/tracks/galaxy-ui-redesign/visual/tsumego/{1440x900,1024x768,430x880}/`
> 里的 `implementation` / `side-by-side` / `overlay` / `diff` 四类图，工具格标签还是系统黑体。
> **Fan 2026-08-21 明确要求：整组重取，排在测试服重新部署时一起做，「一定要记得做」。**
>
> 触发条件：下一次部署测试服（`go.sailorvoyage.top` / home-ubuntu）时。
> 完成判据：三档视口下 `implementation.png` 里工具格标签的字形与同页「上一题」按钮一致
> （霞鹜文楷），且 `reference` 不动（稿子没变，只有实现变了）。
> 重取后同步更新对照台 Artifact `279158d5-4564-43ea-b761-bcf93d7f5522`，
> 并撤掉死活题那一节顶上的「取于修复前」黄字提示。
>
> `research/` 那组不受影响：研究页可见文字全走 Typography/Button，实测整屏逐像素 0 变化。

**波及面实测**：`/galaxy`、`/play`、`/research`、`/kifu`、`/tsumego` 五页整屏逐像素 diff
**0 变化**；只有死活题页有差，且只落在标签那条 11px 高的横带上。kiosk 侧零波及 ——
`GalaxyApp` 整个模块在 kiosk 构建里被 DCE，产物里族名 `LXGW WenKai` 命中 0。

## 4.9 S3 复盘·报告详情页（commit 00e850ea）

**返回按钮位置（已裁定）**：2026-08-22 Fan 裁定「返回按钮都放到右边栏的左上角吧。
不止限于复盘页面」，并授权改文档。规范 §2.4 已改写，`ModulePlate` 改一处、全站消费方
（升降级对局 / 死活题 / 复盘 / 直播 / 研究）一起生效。状态 chip 那半句未被推翻，仍不进页头。

**一处有意不按冻结稿：显示开关的落位。** 稿子放在中段最末（shell 的 `displayControls` 槽），
但那是按稿子里那份很短的假数据排的。真数据下掉到折线以下 208px（1440×900）/ 389px（1024×768），
迁版式前它一直可见。稿子的意图是「不用滚就能看见」（参考图里它露着），真数据下只有紧跟
对局信息才成立。

**顺带关掉了一笔债的两处**：`LiveMatchDisplayControls` 换成工具格（`ToolGridButton` 四列一行
+ 坐标单独一行开关），直播页与复盘页同时升级。S9 的折叠清单因此**只剩两处**：
`RightSidebarPanel.ItemToggle`（对局室，动之前先问 Fan）与 `ResearchToolbar.ToolButton`（研究页）。

**修掉一个既有 bug**：原来「领地」按有没有 ownership 分成两个几乎相同的 `ToggleButton` 分支，
其中 disabled 那支连 `Tooltip` 都掉了 —— 用户按不动而没有任何解释。共享件用
`disabled` + `tooltip`（`ToolGridButton` 新增的覆盖：默认 disabled 不显示提示，
但「要先有分析才能看领地」这句恰恰只在键是灰的时候才有用）一处表达。

**取图 fixture（本机 dev 库，S3 验收通过即删）**：`styleunify_probe` 名下、对局名
`STYLEUNIFY_FIXTURE`、由 `fan` 的 task 14 整套复制（250 手 / 24 失误 / task_id 25）。
报告接口按 owner 过滤，本机 probe 账号名下原本没有报告。
删除：`python3 <scratchpad>/s3-fixture.py --drop`。

## 4.10 S4 棋谱库页

**这一页是六个里唯一整体翻转构图的**：迁前是「左 520 写死宽度的列表 / 右 棋盘」，
冻结稿 V2 要求「左 棋盘 / 右 320 信息栏」，搜索 + 卡片列表 + 分页整块搬进右栏。
`style-unify-scope.md` 的注解也点名它是**唯一有信息损失风险**的一页。

**照稿子做的**：模块牌（标题 + 副标题 + 胜负 chip）、搜索段、记录数/页码行、卡片列表、
分页、动作区的「在研究中打开」（未选中时禁用）。

**四处按规范/实测不按稿子，各有理由：**

1. **赛事名改成最多两行，不是一行截断。** 实测（1024×768，右栏 320）20 张卡里 **11 张**的
   赛事名超出：最长一条要 298px 只显示得下 165px，被吃掉的正好是
   「苏泊尔杭州-山西元工弘弈」这半截队名 —— 围甲局的辨识信息。两行 = 2 × 165 = 330 > 298，
   最长那条也装得下。改完复量：三档 **被截断的赛事名 0、棋手名 0**（棋手名本来就没截过）。
   这就是 scope 注解要我查的那一处。
2. **播放条用共享的 `PlaybackBar`，不是稿子那排光秃秃的走子键。** 稿子画的是同一件东西的
   低保真版（它标注的图标 SkipPrevious / NavigateBefore 连实际用的都不是）。直播页和复盘页
   动作区都是这一件，本轮题目就是统一；顺带收掉本页第五份手写播放控件。
   代价是多了滑轨和播放键 —— 账本上是**加**不是减。
3. **分页保持 MUI 默认密度，不收 `siblingCount`。** 收了每档都是一行，但第 1 页会从
   `1 2 3 4 5 … 1254` 掉成 `1 2 3 … 1254`，账本上就是丢两个直达页码。实测默认密度在 320 栏
   放得下（第 1 页 270/309）；翻到第 600 页那种四位数居中的情况会**折成两行**（28 → 56），
   但它在中段里、滚到底完整可见（R6 量过）。两行不好看，比够不着页码轻。
4. **坐标改走 `useBoardCoordinates` 自动档，稿子画的是常开。** spec §3.2「棋盘边长低于 500px
   时坐标默认关闭」。430 档棋盘 410 < 500，所以竖屏实现图没有坐标而稿子有 —— 这是规范压稿子。
   本页没有坐标开关（右栏塞的是列表，没有显示开关那一段），所以只取 `visible`。

**承重实测（真浏览器，按本页自己的盒子链重写关系式，见 `scratchpad/lb-kifu.js`）：**
本页独有的一条是 **R6「中段滚到底之后分页控件必须完整可见」** —— 够不着分页 = 翻不了页，
这是别的棋盘页没有的失效模式。另有 R8「列表必须真的溢出，否则这一轮数字全部不算」。
1440×900 / 1024×768 / 430×880 **各 0 失败**，外加 1024×768 第 600 页（分页两行）也 0 失败。
棋盘 **828 / 684 / 410**，与已迁三页逐格相同；右栏 340 / 320 / 满宽；中段溢出 1122 / 1362 / 1923。

**控件账本（1440×900，选中一局）：迁前 34 → 迁后 36，空按钮 0。**
差集是 4 失 6 得，**4 个失全部是同一批能力换了实现**，逐个真点过验证：
`⏮`→`第一手`(→0)、`◀`→`上一手`(211→210)、`▶`→`下一手`(0→1)、`⏭`→`最新`(→211)。
原来那四个是**没有可及名的字形按钮**（账本里名字就是 `⏮`），现在都有名字了。
净增 2：`播放`（自动播放）与 `手数进度`（滑轨）。竖屏 430 账本与横屏**逐条相同**。

**顺手补的一处共享缺陷**：`PlaybackBar` 的滑轨一直没有可及名，账本把它记成空按钮。
补 `aria-label`（新 key `live:move_slider` × 11 语言），直播 / 复盘 / 棋谱库 / kiosk 一起受益；
守卫写在 `LiveMatchPage.test.tsx`，去掉 label 即红（变异验过）。

## 5. 待议（发现即记，不顺手改）

- **基线上就红的一条单测**：`src/kiosk/__tests__/GamePageEngine.test.tsx`
  「confirming resign from the error dialog fires the resign action AND closes the error dialog」，
  `mockClearPhysicalEngineError` 期望调用 1 次实得 0 次。已在 **fd3de2b6 干净树**上单独跑过复现 ——
  与本轮无关，属 kiosk 对局页赛道。本轮的判据是「不新增失败」，不是「全绿」。

- **直播页的显示开关可能也在折线以下**：复盘页实测工具格掉到折线下 208–389px，原因是真数据把
  中段撑长。`LiveMatchPage` 用的是同一个共享件、同样挂在 `displayControls` 槽，但本机没有直播
  数据，量不到。**下一次有直播数据时量一次**；若同样在折线以下，改法与复盘页相同（挪到
  `MatchInfo` 之后）。
- ~~**「进入研究室」是个空跳转**~~ **已补（Fan 2026-08-22 点头「补」）**：
  `ReportDetailPage` 现在跳 `/galaxy/research?user_game_id=<uuid>`，研究页新增对应的深链
  effect（`ResearchPage.tsx`，紧挨原有的 `?kifu_id=` 那条）。三处裁定写在代码注释里：
  1. **用 `user_game_id` 不用 `kifu_id`** —— 后者走棋谱库 `KifuAPI.getAlbum`，是另一个
     id 空间；把报告的 game id 塞进去会加载到一局无关的棋，**比不跳转更坏**。
  2. **不带 `&analyze=1`** —— 全盘扫描是计费动作，不该由一次导航悄悄触发；这一局报告页
     也早已分析过。要分析在研究页按「开始研究」。单测里有一条绊线守着这个决定。
  3. **SGF 用刚取回的 `detail.sgf_content`，不从 `board` 反推** —— `loadFromSGF` 的
     setState 在同一段 async 续体里还没冲刷。这正是 kiosk 同名页注释里记的那个坑，
     而 galaxy 原有的 `?kifu_id=` 那条**仍然踩着**（`setTimeout(handleStartAnalysis, 100)`
     闭包在空棋盘那一帧）——**属另一条入口的既有缺陷，本轮不动，记在这里**。

  真浏览器实测（本机 8001 + S3 fixture，1280×720）：点「进入研究室」→
  `/galaxy/research?user_game_id=sufx_s3_report_250`，棋盘 **250 / 250 手**、
  对局信息回填 武宫正树 / 铃木伊佐男 / 19×19 / 中国规则 / 贴目 6.5，页面停在 L1 摆盘态
  （「开始研究」还在，无进度条），网络里只有 1 次 `GET /api/v1/user-games/sufx_s3_report_250`、
  **0 次 session/scan**。截图 `scratchpad/research-deeplink-1440.png`。
  四条新断言全部做过变异（改坏 → 变红）。

- **规范 §3.2 的坐标默认档，研究页与死活题页没做到**：spec §3.2 写「棋盘边长低于 500px 时
  坐标默认关闭，但开关仍保留」。实测现状：已批准的直播样板、复盘页（S3）、棋谱库页（S4）
  都走 `useBoardCoordinates` 的自动档；而 **`ResearchPage.tsx:591,687` 写死 `true`**，
  **`TsumegoProblemPage.tsx:56` 是 `useState(true)`**（开关有，但默认不随边长走）。
  两页在 430 档都会在 410px 的棋盘上画坐标。属**既有缺陷、迁版式时没顺手关**，
  而 S1/S2 已经确认过、不在 S4 里回头改。**改法**：两页各改一行，换成
  `useBoardCoordinates(boardEdge).visible` 作为初值来源；死活题那个开关继续保留。
  建议排 S9 收口一起做 —— 等 Fan 点头。

- **取参考图必须回读屏名**：2026-08-22 发现研究页（S1）的三张 `reference.png` 画的其实是
  **直播观战页** —— 取图脚本切了屏但没有核对切到没切到，四图对比因此拿研究页的实现去比直播页的
  稿子，而 S1 的确认是在这份错证据上做出的。已重取并修好。**判据从此是：取每一张参考图时，
  由页面自己回读它当前渲染的屏名并打印出来**（`SCREENS.find(s => s.id === S.screen).label`），
  不能只看脚本里写了哪个 id。这是「否定的答复不携带原因」的同族 —— 切屏没成功和切屏成功后
  画面长得像，在截图里是同一个结果。
