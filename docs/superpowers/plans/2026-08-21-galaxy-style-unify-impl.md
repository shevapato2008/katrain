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
**（2026-08-22 更新：Fan 裁定方案 A 后 `ItemToggle` 已折叠掉，见 §4.11。剩 `ResearchToolbar.ToolButton` 一处。）**

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
**（2026-08-22 更新：前者已在 S5 折叠掉（Fan 裁定方案 A，§4.11），`BoardEditToolbar.ToolButton` 在 S6 折叠掉（§4.12）。S9 只剩 `ResearchToolbar.ToolButton`。）**

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

## 4.11 S5 对局室 + 升降级对弈页（方案 A：改共享件，两页一起变）

**Fan 2026-08-22 裁定：方案 A。** 提问背景：对局室整条右栏是 `RightSidebarPanel`，与升降级
对弈页共用，而 scope 写着那页「已迁移、别改」。三个选项（A 改共享件两页一起变 / B 另起一份
只改对局室 / C 只换外壳）做成了对照页 artifact `33d10b06-5f30-4921-b7bf-a38472be73fc`，
Fan 选 A。**因此本节包含对 `GamePage.tsx` 的改动 —— 那条「照抄对象不许改」的约束被这次裁定取代。**

### 动了哪四个文件

| 文件 | 改动 |
|---|---|
| `galaxy/components/game/RightSidebarPanel.tsx` | 拆出具名导出 `RightSidebarActions`；`ItemToggle` → 共享 `ToolGridButton`；两列 → 四列；加整行「离开对局」；`isRated` 拆成 `isRated` + `analysisLocked`；加 `isSpectator` / `spectatorCount` / `resultAlert` / `onLeave`；显示开关改整行 |
| `components/PlayerCard.tsx` | 容器查询收窄档（只在 `board-rail` 里）；关注键从名字旁下沉到底行；加呼吸点 + 非轮次方压暗 |
| `galaxy/pages/GameRoomPage.tsx` | 迁 `BoardPageShell` + `ModulePlate`；删棋盘上方那条横栏；坐标/手数/落子特效接上真状态 |
| `galaxy/pages/GamePage.tsx` | `actions={<RightSidebarActions/>}`（外裹 fieldset）、`onLeave`、模块牌补副标题与状态徽章 |

### 顺手修掉的四条既有缺陷（都不是版式问题）

1. **自由的人人对弈被当成升降级对局。** `GameRoomPage` 无条件传 `isRated={true}`，于是一局
   `game_type='free'` 的对弈也挂着绿色「升降级模式：进行中 / 净胜局数将用于段位更新」横幅，
   并读到「升降级对局中道具已禁用」。根因是 `isRated` 一个 prop 兼管两件事：**算不算段位** 和
   **能不能分析**。已拆成两个正交的 prop —— 人人对弈没有引擎，`analysisLocked` 恒真；
   `isRated` 按 `isRankedGameType(gameState.game_type)` 如实传。
2. **升降级对弈页的「离开对局」弹窗没有任何键能打开。** `handleLeaveRequest` 只挂在非升降级
   那条旧顶栏上；升降级分支走 `BoardPageShell`，顶栏没了，弹窗还接着。现在按冻结稿放在工具格
   正下方。
3. **对局室的坐标 / 手数 / 落子特效三个开关是死的。** 面板照一个写死的字面量渲染、
   `onToggleChange` 对它们是空操作，而棋盘拿到的又是**另一个**写死的
   `{coords:true, numbers:false}`。已改成同一份真状态同时喂给面板和棋盘。
4. **升降级对弈页的「落子特效」也是死的**（2026-08-22 Fan 追问「为什么实现页面没有落子特效」
   时顺出来的）。那个开关的**显示条件**是 3D 打开——截图里 3D 是关的，所以不上屏，这一半是
   迁移前就有的设计，照搬没动。但底下压着一个真缺陷：`GamePage` 给棋盘的是
   `isRated ? { coords, numbers } : analysisToggles`，**升降级模式下 `stoneDropEffect`
   被过滤掉了**，于是 3D 打开后那个开关拨得动、自己也变 checked，值却到不了 `Board3D`。
   真运行时顺着 React fiber 量到：开关 `checked=true`，两块棋盘收到的都是
   `{coords:true, numbers:false}` —— 连这个 key 都不存在。
   **修法**：过滤器的用意是「分析类不上盘」，而坐标 / 手数 / 落子特效都是纯外观，
   `stoneDropEffect` 是漏的。四处重复的三元式收成一个 `boardToggles`。
   新增一条双向守卫（`GamePage.aiLadder.test.tsx`）：外观类必须**能**到 3D 棋盘、
   分析类（建议 / 领地）必须**到不了**；两个方向都变异证过。

   **一条取证教训**：React fiber 是**双缓冲**的，从 DOM 拿到的那棵可能是上一次提交的那半，
   读出来会落后一个 commit —— 中间一度据此误判「修完仍然不通」。判据是**两半都读**
   （`f.memoizedProps` 与 `f.alternate.memoizedProps`），对得上开关的那半才是当前树。
   另外 `board-stage` 里同时挂着 2D 和 3D 两块画布，从 `querySelector('canvas')` 向上爬
   只会撞到第一块；要从 stage 的 fiber **向下**遍历，把两个消费方都列出来。

   **不用重取四图**：3D 关闭时 `Board3D` 根本没挂载，这处改动在已取的那一帧上是 0 像素差异。

### 控件账本（真浏览器 census，1440×900）

|  | 对局室 | 升降级对弈页 |
|---|---|---|
| 迁移前 | 10 个，其中 **6 个无名** | 10 个，其中 **6 个无名** |
| 迁移后 | 19 个，**0 无名** | 19 个，**0 无名** |

**丢失 0 / 空按钮 0。** 增加的九个不是新功能：
- 六个翻手键从**无名**变成有名（`跳到开局 / 后退 10 手 / 后退一手 / 前进一手 / 前进 10 手 / 跳到最后`，
  11 种语言已补）—— 它们本来就在，只是账本和读屏都看不见；
- 八个工具键（领地/建议/图表/悔棋/停一手/认输/数子/3D）迁移前是**挂了 onClick 的 `<div>`**，
  既不进账本也**不能用键盘到达**，现在是真的 `<button>`（`ToolGridButton`）；
- 一个模块牌返回键（`返回大厅` / `返回升降级`）是模板自带的。
- 「离开对局」在对局室是从棋盘上方那条横栏**搬**进右栏（不是新增）；在升降级对弈页是**新增**，
  见上面第 2 条。

### 承重实测（真浏览器，`scratchpad/lb-room.js`，两页 × 三档视口全过）

关系式先写死再读数。这一页自己的盒子链是
`board-page-shell → board-stage | board-right-rail{module | scroll | actions}`，关系式与前几页
**不照抄**：多了「两张棋手卡并排横向不许溢出」和「六个翻手键必须整个落在动作区矩形内」两条。

- **造溢出**：对局室右栏的真实内容在 768 高下装得下，装得下时量出来的「会不会滚」不算。
  往滚动段注入 1200px 填充物 —— 假的是**输入**，结论仍由浏览器算。
  **第一版量出「不会滚」是假绿**：滚动段是 column flex 容器，填充物 `flex-shrink:1` 被压回去了，
  必须写 `flex:0 0 1200px` + `min-height`。
- R1 只有中段会滚（module / actions / shell 三者 `scrollHeight == clientHeight`，中段 `scrollTop` 真能 >0）
- R2 撑高后三段守位（module.top 不变、actions.bottom 不变且 ≤ rail.bottom、棋盘边长不变）
- R3 `<900` 时 stage 为方（`aspectRatio:1/1`）；≥900 时 stage 是网格单元、方的是里面那张 canvas。
  **第一版把这条写反了**（对 ≥900 断言 stage 为方，读到 884×848 报红）—— 是期望写错，不是产品错。
- R4 右栏与棋手卡行都不横向溢出、两张卡都不退化、工具格 8 个键都在格内
- R5 整页不横向滚 R6 六个翻手键整个可见

**实测数字（只记录，不作判据）**：棋盘边长 **828 / 684 / 410**，右栏 **340 / 320 / 满宽 430** ——
与直播样板、死活题、复盘、棋谱库四页完全一致。

**87px 那条的前后配对**（升降级对弈页，同一对用户名 `sufx_s5_black` / `sufx_s5_white`）：

| | 棋手卡行 scrollWidth / clientWidth | 横向被裁 | 动作区高 |
|---|---|---|---|
| 迁移前 | 400 / 297 | **103px** | **0** |
| 迁移后 | 297 / 297 · 277 / 277 · 398 / 398 | **0**（三档） | 58 |

（此前在对照页里报的是 87px，那是另一对较短的用户名量出来的；**溢出量随名字长度变**，
缺陷是同一个：卡片按 500 宽的旧右栏做，塞进 340 的新右栏。）

### 与冻结稿的实差（四图对比里看得见，有意保留）

1. **棋手卡比稿子高。** 冻结稿的卡是三行（名字 / 时钟 / `5k · 提子 3`），把**读秒次数**
   （`0s ×0`）整条去掉了。读秒是记时对局里的真信息，去掉是信息损失，所以保留了原来的计时块，
   只做收窄（内边距、字号、关注键下沉）。
2. **没有「该你了」飘带。** 稿子在轮次方卡片底部压一条飘带。`PlayerCard` 的 `active` 表示
   **该这一方走**，不表示**该你走** —— 直接照搬会在**对手的卡上**写「该你了」，是错的；
   要做得加一个「这张卡是不是我」的新 prop。而轮次归属已经由模块牌右侧的徽章
   （`轮到你了 / 对手回合 / 观战中 / 已结束`）如实说了，那里才是它该在的地方。
   稿子要的**冗余线索**做到了三条：描边 + 外发光 + 呼吸点，再加非轮次方压暗到 62%。
   时钟**没有**改成玉色 —— 它现在的颜色编码的是「主时间 / 读秒 / 危险」，比轮次更要紧。
3. **禁用提示文案短一句。** 稿子写「升降级对局中不开放 AI 分析、改规则、改贴目、改让子或改强度」，
   实现用的是既有 key `items_disabled_rated`（「升降级对局中道具已禁用」）。改文案要动 11 种语言，
   与版式无关，没有顺手改。
4. **呼吸点与压暗只在 `board-rail` 容器里生效**，盒端对局面板和禅模式一像素不动 ——
   `PlayerCard` 是共享件（kiosk / ZenMode 都用），共享件的改动一律走容器查询，不走断点。

### 单测

新增 `galaxy/pages/GameRoomPage.test.tsx`（6 条），**五条闸的红分支逐条变异证过**，记录写在
文件顶部的 docstring 里。`GamePage.aiLadder.test.tsx` 的 `RightSidebarPanel` 桩件补了
`RightSidebarActions` 具名导出。

### i18n

新增 13 个 key × 11 种语言（`game_room:title` / `board_size` / `ended` / `lobby_short` /
`leave_game` / `exit_spectating`、`game:nav_first` / `nav_back_10` / `nav_back` / `nav_forward` /
`nav_forward_10` / `nav_last`、`game:in_play`），走 `scripts/batch_translate_galaxy.py` 的
`update_po_file` 子集调用，与本轮前几页同一条路子。

### 四图对比

`visual/gameroom/{1440x900,1024x768,430x880}/` 与 `visual/rated/{...}/`，各 5 张
（reference / implementation / side-by-side / overlay / diff），共 30 张。
参考图取自冻结原型 `game-room · 棋手 2D` 与 `game-rated · 对局中`，取图时由页面**回读屏名 /
分支 / 视口 / `usedV2`**（见 §5 那条判据）。实现图取自本机 8001 的**真运行时** ——
两个临时账号撮合出的一局真人人对弈，同一个 session 既当对局室也当升降级页的渲染输入。

**不用原型的「现状」渲染做对照**：它把对局室的工具格画成四列（真的是两列），还画了一排
「认输 / 数子 / 离开 / 终局」底部按钮，`git log -S"终局"` 证明 `RightSidebarPanel` 里从未有过。
这是 §1「原型 ≠ 现状」的第五、第六处。

### Fixture

`scratchpad/s5-room-fixture.py` 在本机 dev 库注册 `sufx_s5_black` / `sufx_s5_white` 并撮合一局。
**删除条件写在 docstring 里：四图对比取完即删** —— `python3 s5-room-fixture.py --drop`。

## 4.12 S6 教程 · 原书页（变化图制作工具）

冻结稿把这一页标成「唯一没有硬套的一页 …… 本轮里最没把握的一处」。**重叠风险先排除**：
`git log` 显示教程目录最后一次改动是 2026-04-10，本分支基点之后没动过；唯一领先 develop 的
`feature/enhanced-editing-voice` 是四个月前的陈分支，那 3 行早已在 develop 里重新落地。

### 这一页为什么不能照搬

它是**内部制作工具**，审图的人必须让原书页扫描图和识别出的棋盘**并排**才能核对。
塞进右栏上下滚会真的弄坏这个工作流。所以按冻结稿的做法：右栏仍是统一的三段，
但原书页图**不进右栏** —— 它是 stage 里的一层，占左侧 34%，点右栏「对照原书页」一键收起，
收起后棋盘吃满整个 stage。竖屏放不下并排，那一档没有对照层，原书页降到右栏第一节。

### 迁移前后的几何（真浏览器，第 3 节「拆」，30 张图数据齐全）

| | 1440×900 | 1024×768 | 430×880 |
|---|---|---|---|
| 迁移前 三列各宽 | 387 | 320 | 堆叠 |
| 迁移前 棋盘 | 379×703 | 312×579 | 390×724 |
| 迁移后 棋盘 | **442**×820 | **370**×688 | **216**×402 |
| 迁移后 对照层 | 296 | 235 | 无（降到右栏） |

桌面两档棋盘各大 **17% / 19%**；**竖屏小 45%**（390 → 216）。原因是统一版式的 stage 在
堆叠态是**方的**（`aspectRatio:1/1`），而这一页的「棋盘」按变化图的 viewport 出图、
**不一定是方的**（这一节实测 0.54 的竖长图），于是被高度卡住。冻结稿在竖屏同样是方 stage，
所以这是**照稿实现的结果**，不是实现走样；内部工具的实际使用场景是桌面。**记录，不改。**

### 控件账本（真浏览器 census，1440×900）

| | 只读态 | 编辑态 |
|---|---|---|
| 迁移前 | 14，其中 **6 个无名** | 14，其中 6 个无名，**8 个工具键账本完全看不见** |
| 迁移后 | 16，**0 无名** | 24，**0 无名** |

**丢失 0 / 空按钮 0。** 逐条：
- **识别调试面板那五步（S0–S4）**原来是「挂 onClick 的 `<div>` 里再套一个既没有 onClick
  也没有名字的 `IconButton`」—— 它能用只是因为点击冒泡到了外层 div。键盘到不了、读屏念不出、
  账本记成五个空按钮。改成真按钮（名字取小节标题，展开态用 `aria-expanded` 报告）。
- **手数滑轨**原来没有可及名（账本记成 `«input:range»`），补 `aria-label="手数"`。
- **编辑工具条那 10 个键**（摆黑/摆白/交替/编号/大写/小写/橡皮/图形/撤销/一键清空）原来
  账本一个都数不到，现在全部是有名字的真按钮。
- `← 返回` → 模块牌的 `返回教程`。
- 新增两个：`对照原书页`（右栏的开关）与 `收起原书页`（对照层自己的收起键）——
  同一件事的两个入口，冻结稿如此。

### 承重实测（`scratchpad/lb-fig.js`，三档全过）

这一页的盒子链比别的棋盘页**多一层**：stage 里有两块。所以关系式多两条，不是照抄：
- **R3b 对照层那条滚动条不能长在右栏的滚动段里**（两条滚动条互不干扰）
- **R4 棋盘必须完整落在它那块区域内**（不被对照层盖住、不溢出 stage）

其余同前几页（三段承重、注入 1200px 撑高后守位、整页不横向滚）。

**中途抓到一条真缺陷**：竖屏下右栏横向可滚 5px。逐层反查是**手数滑轨的滑块**——
滑到最右端时它和水波纹越过轨道末端约 13px，而 <900 的滚动段不裁横向，一路顶到右栏上。
重写时把原来滑轨外面那圈 `px` padding 丢了，补回去即消。

### 与冻结稿的实差

1. **原书页图是坏图。** `data/tutorial_assets/` 在这台机器上**整个目录不存在**，
   `/api/v1/assets/...` 返回 404，浏览器里 `naturalWidth: 0`。实现截图里那一格是浏览器的
   坏图占位符 + alt 文字。版式对不对不依赖图的内容，但**这一页的四图对比只能证到版式**。
2. **竖屏没有「展开原书页」按钮。** 冻结稿在竖屏画了那个 chevron，但它自己又说竖屏没有
   对照层 —— 那个键会展开一个不存在的东西。实现里 `isWide` 为假时不渲染它。
3. **`下一手编号` / `下一个字母` 两个输入框只在对应工具生效时出现**（冻结稿画成常驻）。
   常驻会留下两个改了不起作用的输入框。

### 顺带

`BoardEditToolbar` 自己那份 `ToolButton` 是工具格按钮的**第四份实现**，已折叠到共享的
`ToolGridButton`；`保存 / 取消` 从工具条里移到右栏动作区（编辑长图时它们原来会跟着工具条
一起滚出视口）。S9 的折叠清单**只剩研究页的 `ResearchToolbar.ToolButton` 一处**。
`ToolGridButton.onClick` 加了事件透传（图形菜单要拿 `currentTarget` 当锚点），
对忽略参数的既有调用方完全兼容。

### 这一轮踩到的三个取证坑（都不是产品问题）

1. **`board_payload IS NOT NULL` 骗人**：2885 条 figure 里 **2401 条存的是 jsonb 字面量
   `null`**，SQL 判非空为真、API 取出来是 null。真有棋盘的只有 484 条。挑取图基准前
   必须按 `board_payload::text <> 'null'` 数。
2. **`&& echo built` 说了假话**：`npx tsc -b` 在子目录下报 TS5083（找不到那一层的 tsconfig），
   链子断了、构建根本没跑，但输出里照样出现了 `built`，于是白量了一轮「修完仍然不通」。
   **判据是磁盘上产物的哈希变没变**，不是任何一句成功消息。
3. **`/browse` 的截图路径沙箱跟着 cwd 走**：在 `katrain/web/ui` 下跑时拒绝写
   `superpowers/tracks/...`，必须回到仓库根。另外本机 dev server 一小时内挂死两次
   （进程在、不响应），重起即可。

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
