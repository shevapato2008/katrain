# 围棋 kiosk 对齐共享外壳 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `katrain/web/ui/src/kiosk/` 的十屏界面，逐屏搬到四棋类共享外壳（`kiosk-shell/tokens.css` 的 112 个类）上，使围棋与已对齐的象棋 / 国象 / 五子棋在顶栏、Dock、L1 两栏、模式卡、页控条、悬浮滚动条这几层上**逐像素同构**。

**Architecture:** 这是**搬运，不是重新设计**。三层来源，优先级从高到低：① 规范 `kiosk-shell-spec.md`（四棋类共享，最高权威）；② 围棋设计稿 `sample-go/go-kiosk.tmpl.html`（围棋这十屏的正本，几何逐字节引 `tokens.css`）；③ 已对齐三家的真前端（`smartbox-software/{chess,xiangqi,gomoku}/ui/src/`，是「对齐后长什么样」的活样本）。做法是**用共享类名直接写 JSX**，不再用 MUI `sx` 复刻几何——§17.2 那条「类抄进来了、页面又自己造了一套」正是本轮要消除的病灶。象棋 `xiangqi/ui/src/shell/` 已经有全套 React 外壳组件（`KioskFrame` / `KioskTopbar` / `KioskDock` / `KioskPagebar` / `KioskBoardConsole` / `KioskScrollZone` / `KioskFold`），本轮**照抄它们的结构**，只换围棋自己的内容与配色变量。

**Tech Stack:** React 18 + TypeScript + Vite + MUI（保留，仅用于业务控件与既有页面内部，外壳层不再经过它）+ Playwright（四图闸与几何闸）+ 已 vendored 的 `src/kiosk-shell/{tokens.css,fonts.css,fonts/,go-tokens.css,seclabel.css,icons/}`。

**进度（每完成一个 Task 更新这一行；129 个步骤复选框不逐个勾，git 历史才是记录）：**

| Task | 状态 | 提交 |
|---|---|---|
| 0 基线 | ✅ | 记在 `scope.md` §8 —— 计划里写的「3 文件 / 6 测试红」是**过期的**，实测是 1 文件 / 1 测试 |
| 1 画布与 `.kiosk` 作用域 | ✅ | `KioskFrame` / `kioskScale` |
| 2 四图工具 | ✅ | `bd80bcc8` `tests/helpers/fourup.ts` |
| 3 顶栏 | ✅ | `c25bb1a3` 四件指示物全拆(D9)，`Header.tsx` 删 |
| 6 图标 / 模式卡 / 组标题 | ✅ | `227706f8` 82 个 Phosphor + 契约闸（**提前到 Task 4 之前做** —— Task 4 的 Dock 要 `<Icon>`） |
| 4 Dock 与路由重映射 | ✅ | `488ddbfe` 六项(D8)；对局屏挪进 KioskLayout |
| 5 L1 两栏与镜像栏 | ⬜ 下一个 | |
| 7–20 | ⬜ | |

⚠️ **实际执行顺序是 0→1→2→3→**6**→4→5→…**，不是文档里的编号顺序。Task 4 的 `KioskDock` 消费 Task 6 的 `<Icon>`（这条依赖计划自己在 Task 4 的 Interfaces 里点过名）。

**Spec:**
- `/Users/fan/Repositories/smartbox-software/superpowers/shared/kiosk-shell/kiosk-shell-spec.md`（1191 行，v1.27，四棋类共享，**最高权威**）
- `superpowers/tracks/kiosk-go-shell-align/scope.md`（本轮范围裁定，Fan 2026-08-20 已确认）
- `superpowers/tracks/golaxy-ai-ladder-parity/kiosk-design-alignment.md`（2026-08-11/12 实测记录，踩过的坑）
- `katrain/web/ui/src/kiosk-shell/README.md`（vendored 副本说明，含两段「留着不删」的错误记录）
- 设计稿正本：`smartbox-software/superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html`（85KB 手写模板，**读这份，不要读 1.1MB 的 `go-kiosk.html`**，后者是 build.py 内联字体与图片之后的产物）
- 参考图：同目录 `shots/01-play.png … 10-settings.png`（2048×1202 = 2× 的 1024×601）

---

## Global Constraints

每一条都对**所有** Task 成立，任务里不再重复。

### G1 `.kiosk` 作用域（硬闸）—— 精确机制

口径要说准，因为**失败长相和「样式没生效」不一样**：

- `tokens.css` 里 **163 条自定义属性全部、且只在** 一个规则块里：`.kiosk { … }`（`:14-245`。实测 `grep -nE '^\s*--[a-zA-Z0-9-]+\s*:' tokens.css | awk -F: '$1<14 || $1>245'` **返回空**）。
- 另外只有一条规则要求 `.kiosk` 祖先：`.kiosk, .kiosk *, .kiosk *::before, .kiosk *::after { box-sizing: border-box }`（`:253-256`）。
- **其余 186 个规则块全是顶层 `.kiosk-*` 选择器，不要求 `.kiosk` 祖先。**

⇒ 把 `.kiosk-card` 画在 `.kiosk` 外面，**它的 `display/flex/border` 照样生效，只有每一个 `var()` 静默求空**：`height: var(--card-mode-h)` 变成 invalid-at-computed-value-time → `auto`。屏上是「布局对了一半、尺寸全塌」，**不是白屏，也不报错**。国象实测过更狠的一次（`xiangqi/ui/src/index.css:23-34`）：在 `:root` 上写 `--serif: var(--font-serif)`，CDP 量出来四个 token 全是空串、`body` 跑的是 **Times**，而屏上「没炸，纯属侥幸」。

⇒ **用到这套 token 的子树，根节点必须挂 `.kiosk`。** Task 1 把 `.kiosk` 提到 kiosk 应用根。此后若有子树 portal 到 `.kiosk` 之外（MUI `Dialog` / `Popover` / `Menu` 默认 portal 到 `body`），**那个子树必须自己挂 `.kiosk`**，否则同一个静默失败。

MUI `CssBaseline` 本来就是 border-box，提到根节点**不改变既有 MUI 组件的盒模型**（已核）。

### G2 补的变量与两处没有兜底的 `var()`

- `--paper` / `--accent-soft` **在 `tokens.css` 里既不定义也不使用**（实测 `grep -nE 'paper|accent-soft' tokens.css` 无输出），在围棋设计稿里也 **0 次命中**。它们是给「从象棋模板抄来的代码」准备的安全别名，`go-tokens.css:25,37` 已赋值。**别把它当成围棋的活依赖**——但也不要删，删了象棋来源的那几块会静默塌。
- **真正没有兜底的是 `--at`**：`tokens.css:844` `.kiosk-evalstack__cursor` 写的是 `left: calc(var(--eval-axis-w) + (100% - var(--eval-axis-w)) * var(--at))`，**没有第二参数**。消费方忘了写 `style={{'--at': String(t)}}`，整条 `calc()` 失效、游标塌回 `left:auto`。用到着法条时必须设它。
- **`--info` 有一处不跟随**：`go-tokens.css:45` 定义了 `--info: #5B9BD5`，但 `tokens.css:920` 的 `.kiosk-wip.have` 把同一个蓝**写成了字面量**（`color:#5b9bd5; border-color:rgba(91,155,213,.5)`）。要调蓝标的颜色，改 `--info` 不生效。登记，不在本轮改（那是上游的事）。
- `go-tokens.css` 与 `tokens.css` 的 `.kiosk` **特异性相同**，所以 **`go-tokens.css` 必须在 `tokens.css` 之后 import**，顺序不可换。

### G3 四图对比（硬闸，每屏一次）

每屏在**同一目标 viewport（1024×600）**下同时产出四类图，缺一不算过：

| 图 | 内容 | 答什么 |
|---|---|---|
| 参考 | `sample-go/shots/NN-*.png` 等比缩到 1024 宽、顶端对齐裁到 600 | 目标长什么样 |
| 实现 | 真浏览器 `page.screenshot()` @1024×600 | 这一屏自己成不成立 |
| 并排 | 参考 \| 实现，各带一条 34px 标签带 | 构图 / 分块顺序 / 组件层级 |
| 叠加+差异 | **边缘图**：红 = 只有参考有边，绿 = 只有实现有，白 = 两边都有 | 几何骨架对不对 |

差异图**必须用边缘图，不能用像素比**（`kiosk-layout-a-vs-xiangqi-setup.spec.ts:92-108` 已实现）：像素比只能证明「两屏配色不同」，而各棋类保留自己基调是规范要求的。**围棋这一轮参考图与实现同为青毡深色，像素比不再整屏通红，但仍然不作数**——理由换了一个：稿子里有大量不上线的旁注（见 G5），像素比会把它们全部报成回归。

逐项对比：构图、几何间距、组件层级、字体/色彩/材质、图标素材、文案、状态语义。

**未经 Fan 明确确认，不得进入下一屏。** 自动化闸绿了 ≠ 视觉过了。

### G4 承重实测（硬闸）

判据不是属性名清单，是反查：**把这次改动撤回去，页面上有没有任何元素的高度来源或裁切边界会变？** 会变就当场在**真浏览器**里量，不许攒到最后的取图关卡，不许用 jsdom 近似或逻辑推演顶替。

本轮**整条盒子链都在改**（`.kiosk-screen` 是 `position:relative` 的固定 1024×600，`.kiosk-topbar` / `.kiosk-dock` / `.kiosk-content` 全是 `position:absolute`，`tokens.css:269-278`、`:377-388`、`:415-423`），所以 **每一个 Task 都触发这一关**。

量之前先把数据造到会溢出——装得下的数据量下量出来的数字一概不算。先写死关系式期望再读数，具体像素只记录、不作判据。**同一条链上可以有不止一处断点，量通一条不等于整条链是对的。**

新增的承重面是 §5.2 那条悬浮滚动条：`overflow-y:auto` + `scrollTop` 真能推 那条闸不能丢（Task 7）。

判据一句：**把它原样搬进真浏览器，还有可能失败吗？** 不可能就删。**假的是输入可以，假的是结论删。**

### G5 稿子里的 `.note` 分两种，只搬其中一种

设计稿有 26 处 `class="note"`（11px `--dim`，`go-kiosk.tmpl.html:175`）。它们**不是同一件东西**：

| 种类 | 例 | 怎么办 |
|---|---|---|
| **给读稿人的旁注** | 「围棋原来那张稿把它做成一张并列卡，**是错的**」「这道题是我在稿子上现摆的，不是题库里的题」「见 `interface.py` 的分析闸」 | **不上线**。已对齐三家一处都没搬（实测：`grep "不是第六张并列卡\|是错的" chess/ui/src xiangqi/ui/src` 零命中；象棋稿同样有 22 处 `.note`，真前端一处没有） |
| **真 UI 文案** | 做题屏 `.panel > h3「这一题」` 底下那段题面「黑先。白有两颗子，各剩两口气…」 | **照搬**，一个字不改 |

判据：**这段话是说给屏幕前的下棋人听的，还是说给读这份稿子的人听的？** 每屏的 Task 里逐条点名了哪几处属于哪一类，不要自己重判。

⇒ **这条会让每一张差异图在旁注那几块出现大片绿/红，这是预期的**，不是回归。并排图的标签带里必须写明这一句（照 `kiosk-layout-a-vs-xiangqi-setup.spec.ts:124-128` 的做法：说明必须写在**图里**，不是写在旁边的文档里）。

### G6 构建与类型（硬闸）

```bash
cd katrain/web/ui
npx tsc -b              # 不是 tsc --noEmit —— 根 tsconfig 是 files:[] + references,
                        # 命令行 --noEmit 不跟 references, 实测检查 0 个文件
npm run build           # 完整 web 构建 -> ../static/      基线 EXIT 0, 约 52s(tsc -b 占大头)
npm run build:kiosk-2d  # SBC kiosk 构建 -> ../static-kiosk-2d/, 链了 verify:kiosk-2d
                        # 基线 EXIT 0, 约 41s。**这是 UI 代码唯一的 CI 闸**
```

这三条**都要绿**，而且**基线本来就是绿的**，所以红了就是本轮弄的。

⚠️ **下面两条本来就是红的，不许当验收标准**（2026-08-20 实测基线）：

| 命令 | 基线 | 判据换成什么 |
|---|---|---|
| `npm run lint` | **EXIT 1**，`315 problems (258 errors, 57 warnings)`，其中 `src/kiosk` 占 **100** | 只看**本轮碰过的文件**：改前改后各跑一次 `npx eslint <改动文件>`，比**名字集合**不是条数 |
| `npm test`（= `vitest run`，**不是 Playwright**） | **EXIT 1**，`3 failed / 134 passed` — `GamePageEngine.test.tsx`、`ReportsPage.polling.test.tsx`、`ReportsPage.test.tsx` | 先存基线：`npm test 2>&1 \| grep -E '^\s*(FAIL\|×)' \| sort > /tmp/base.txt`，改完再存一份，`comm -13` 取**新增**的 |

> 「改动后红一片时按文件名判『看着不相关』」会把自己造的污染归给既有噪声。**新增的失败只能靠基线 diff 得到。**

其它两个坑：

- `tsconfig.app.json:38` 把 `src/**/*.test.ts(x)` **exclude 掉了** ⇒ **TS 穷尽性闸放在测试文件里永远不会红**（已变异实测过）。要靠类型守的东西必须写在产品代码里。
- `tsconfig.app.json` 开了 `noUncheckedSideEffectImports` ⇒ **CSS 路径写错会让 `tsc -b` 直接红**，两个构建一起挂。这条是好事：它把 Task 1 那几行 import 的路径错误变成响的失败。

`src/kiosk/` 与 `src/kiosk-shell/` 都是 kiosk 领地；`src/components/`（除 `Board3D/`）、`src/hooks/`、`src/context/`、`src/api*` 是**共享领地**——改到那儿两个构建都受影响。

⚠️ **`verify:kiosk-2d` 只 grep `assets/*.js`，从不看 CSS、也不看字体**（`scripts/verify-kiosk.sh:19,26,34`）。所以 CSS 里混进一条 `/galaxy/` 的 URL，**这道闸是绿的**。本轮往 kiosk 里加 CSS，心里要有这条边界。

### G6b Playwright 怎么跑（没有 npm script）

`package.json` **没有任何 Playwright 脚本**（`test` 是 `vitest run`，而 `vite.config.ts:50` 把 `tests/**` 从 vitest 里 exclude 了）。`.github/workflows/` 里也 **0 命中 playwright**。⇒ 这些 spec 只能手动跑：

```bash
cd katrain/web/ui                      # 必须先 cd —— spec 里的 process.cwd() + ../../.. 靠它
npx playwright test <spec> --config playwright.visual.config.ts --workers=1 --reporter=list
```

**用 `playwright.visual.config.ts`**（vite dev @5173，`reuseExistingServer`）：不需要 Python、不需要数据库、不需要先 build。默认那份 `playwright.config.ts` 会去起 `python -m katrain --ui=web`，而它有三个会造**假红**的坑（`kiosk-ai-ladder-cross-device-semantics.spec.ts:22-40` 记着）：没 `cd` 就 `EACCES`、没设 `KATRAIN_DATABASE_URL` 就 `psycopg2.OperationalError`、不加 `--workers=1` 服务器会中途掉线报 `ERR_CONNECTION_REFUSED`。而且 `--ui web` **退出时会重写 `~/.katrain/config.json`**，先备份。

**`--workers=1` 不是可选的**：四图 spec 的合成步骤要读前面刚写出的 PNG，而 config 是 `fullyParallel: true`；实测并行跑会在 `expect(...).toBeVisible()` 处 5000ms 超时假红，单跑就过。spec 里同时要写 `test.describe.configure({ mode: 'serial' })`。

### G7 文案冻结

本轮**不新写文案**。屏上出现的每一个字，要么来自设计稿、要么是页面现有的字。稿子上没有、现状也没有的空格，宁可留空也不要编——「补一行说明」等于新写文案。

i18n：kiosk 的静态中文一律 `t('key', '中文默认')`（见 `reference_kiosk_i18n_architecture`）。搬运时既有 key 原样保留；外壳新增的固定词（「智星盒」「StellaBox」「围棋」「主页」）**不进 i18n**，它们是品牌与棋类名，四棋类同一份字面量。

### G8 诚实态

生产代码中不得残留模拟业务数据。加载 / 错误 / 空态 / 重试不得伪装成成功。

- **值写「—」不写 0**：`0` = 「查过了，真没有」；还没跟数据源对过账时只能写「—」。
- **灰掉的卡写「未录制 / 即将上线」，不写「锁定」**。
- **不许挂假渐隐**：内容不溢出时不要写 `data-at`，也不要画滚动条。
- **两种标不许混色**：琥珀 `.wip` = 后端根本没有；蓝 `.wip.have` = 后端已有、界面未接。
- **做不了的不留占位框**（规范 §11）。

### G9 提交纪律

每个 Task 结束提交一次，message 用中文，形如 `feat(kiosk-shell): 顶栏改用共享外壳的 .kiosk-topbar`。分支 `feature/kiosk-go-shell-align`，基于 `develop b727e721`。**不推、不合并**，除非 Fan 明说。

### G10 共享类优先 —— 稿子里的本地类多半已经被上游收编了

katrain 这份 vendored `tokens.css` **比围棋设计稿内联的那份新**：实测 `diff` 出来 205 行，**100% 是新增，零处修改、零处删除**。稿子里当年自己写的一批本地类，上游后来收成了共享类。

⇒ **凡是共享包里已经有的，一律用共享的那个**，不要照抄稿子的本地类名。对照表（左边是稿子里的写法，右边是本轮要写的）：

| 稿子本地类 | 用这个共享类 | tokens.css |
|---|---|---|
| `.rows` | `.kiosk-rows` | `:931` |
| `.row` | `.kiosk-row`（**自带 `flex:none`**，注释记着 18 行被压成 33px 那次） | `:932-941` |
| `.row .lead` | `.kiosk-row__lead` | `:942-945` |
| `.row h4` / `.row p` | `.kiosk-row__t b` / `.kiosk-row__t em` | `:947-948` |
| `.row .end` | `.kiosk-row__end` | `:949` |
| `.tag` | `.kiosk-tag` | `:952-955` |
| `.tag.win` / `.tag.loss` / `.tag.draw` | `.kiosk-tag--win` / `.kiosk-tag--loss` / `.kiosk-tag`（裸的就是灰） | `:956-957` |
| `.wrbox` + `.wraxis` + `.wrplot` | `.kiosk-eval` + `.kiosk-eval__axis` + `.kiosk-eval__plot` | `:746-754` |
| `.kiosk-stat*`（稿子已用共享名） | 原样 | `:475-486` |
| `.kiosk-navlist` / `.kiosk-navitem`（同上） | 原样 | `:765-775` |

**`.tag.live`（直播中）在共享包里没有对等物** —— 本轮加一条本地 `.kiosk-tag--live`，并登记为「该提上游的」。

### G11 React 端要补的十二件事 —— 共享 CSS 不管这些

三家活样本的注释里逐条写了它们是被什么真事故逼出来的。**每一条都必须做，做在 Task 1–8 的相应组件里**：

| # | 要补什么 | 不补会怎样 | 活样本 |
|---|---|---|---|
| 1 | **给 `.kiosk` 下的 `h1/h2/h3/h4/p` 归零 margin** | UA 默认 margin 会撑破 `--l1-greet-h`(56) / `--l1-resume-h`(60) / `--l1-sec-label-h`(20)。稿子靠一句全局 `*{margin:0}` 兜着，真应用不能这么干 | gomoku `index.css:399-423` |
| 2 | **表单控件写 `font-family: inherit`** | UA 把 `<button>` 钉死在 `400 13.333px Arial`；板子(Debian 11)上没有 Arial 的中文面 ⇒ **豆腐块**。国象用 CDP 量出 **21 处**，其中 7 处是「即将上线」徽标（`button.kiosk-card` 整条子树继承 Arial）。**必须用 `font-family:`，不能用 `font:` 简写**（简写会把字号一起重置） | xiangqi `index.css:78-88` |
| 3 | **图标用 `?raw` + `dangerouslySetInnerHTML`，不用 `<img src>`** | `<img>` 跟不了容器的 `color`，而 `.kiosk-dock__item[aria-current] { color: var(--ink) }` 就靠 `currentColor` 翻色 | gomoku `KioskIcon.tsx:46-53` |
| 4 | **图标包裹 `<span>` 要 `display: contents`** | 默认 `inline` 的 span 会打断 `.kiosk-dock__item` 的纵向 flex，图标和标签不再作为一组居中 | gomoku `index.css:105-109`。⚠️ 国象同名类写的是 `display:flex`（`shell/shell.css:203`）——**同一个类名两家给了相反的值**，照错了 Dock 就不居中。本轮取 gomoku 那条，因为它点名了具体的失败 |
| 5 | **`<a>` 做 Dock 项要 `text-decoration: none`** | 稿子的 Dock 项是 `<button>`，所以 `tokens.css` 从没写过这条 | gomoku `index.css:110-115` |
| 6 | **时钟对齐到整分再 `setInterval(60_000)`** | 挂载即 60s 轮询会漂移最多 59 秒才翻第一次 | gomoku `hooks/useClock.ts:12-37` |
| 7 | **头像首字用 `Array.from(name)[0]`，不是 `name[0]`** | 代理对（emoji、生僻字）会被切成半个 | 三家一致 |
| 8 | **身份还在加载时不许喊名字** | 国象验收挂过一次：顶栏写 `boardstage2`，同屏正文写「你好，访客」 | xiangqi `HubScreen.tsx:39-54` |
| 9 | **长用户名要有 wrap 兜底** | ≥19 个汉字 ⇒ 问候行两行 ⇒ 56 的块变 65，整栏往下推 | gomoku `index.css:428-431` |
| 10 | **滚动区的 `ResizeObserver` 不会触发** | `tokens.css` 把 `.kiosk-side__scroll` 钉成 `height:100%`，子元素长高时盒子不动 ⇒ observer 一次都不响。**必须给一个 `deps` 信号手动重算** | gomoku `useKioskScroll.ts:52-57` |
| 11 | **滚动节点首帧可能不存在** ⇒ 用 callback ref + `useState`，不要 `useRef` + 空依赖 effect | `useRef` 那种写法读到一次 `null` 就再也不会重跑 | gomoku `useKioskScroll.ts:59-65` |
| 12 | **`.kiosk-actions button` / `.kiosk-movenav button` 没有 `:disabled` 分支** | 禁用态和可用态**像素完全相同** —— 这正是 G8「禁用伪装成可用」那条 | xiangqi `shell/shell.css:154-160` |

另外三条共享包缺、要补在本地 CSS 里的（三家都各补了一份，注释都写着「该提上游」）：
`.kiosk-resume` 的子元素（`.bar/h4/p/.pill`）、`.kiosk-pagebar` 的 flex-shrink 兜底（长标题会把 36px 返回键挤成两行、触点跑位）、`.kiosk-board__play` 的 `place-items:center`（共享只给了 `grid-area`）。

---

## 决策登记

下面每一条都是本轮**已经定了**的，执行时照做，不要重新讨论。三条要 Fan 拍板的另列在最后。

### D1 成长屏本轮跳过（Fan 2026-08-20 裁定）

稿子第 08 屏（盒内段位 / 升降的规矩 / 能力诊断 / 按对手强度）在围棋这边**整条不存在**：无路由、无页面、`katrain/web/api/` 下 grep `growth` 零命中。它是新功能不是改版，带后端。**登记成独立赛道，本轮不碰。**

### D2 稿外五屏只接壳（Fan 2026-08-20 裁定）

`baipu`（摆谱）、`live`（直播）、`research`（研究）、`play/cross-platform`（跨平台）、`vision/setup`（视觉标定）稿子没画。**只接顶栏 / Dock / L1 两栏这层共享壳，内容区维持现状。** 明确不做：不照规范 §5 自己推导这五屏的版式——没有稿子当依据，四图对比就没有参照物，那等于自己发明设计。

> **D2 的前提在 2026-08-21 变了 —— 那五屏现在都有稿子了。**
>
> D2 当时不做的理由写得很清楚：「没有稿子当依据，四图对比就没有参照物，那等于自己发明设计」。
> 这个理由已经不成立：Fan 8-21 让把围棋的设计稿按 galaxy 补齐，`sample-go` 从 13 屏做到 **27 屏**，
> D2 点名的五条全部有了正式稿 ——
> `baipu` → 摆谱屏、`live` → 直播观战屏、`research` → 研究屏、
> `play/cross-platform` → 连接 / 大厅 / 人机开局三屏、`vision/setup` → 棋盘标定屏。
>
> ⇒ **执行到这五屏时不要照 D2 「只接壳」**，按新稿做，四图对比有参照物了。
>
> **2026-08-21 追加：跨平台那一条比五屏多一屏。** Fan 指出稿子「甚至最后切换到自由对弈的对局界面了」——
> 属实。`play/cross-platform/engine/game/:sessionId` 走的是 `<GamePage engineMode />`（`KioskApp.tsx:91`），
> **`engineMode` 这一个 prop 把右栏整块换掉**：本地局那三个分析开关换成三个**会扣次数**的星阵道具键
> （领地 / 支招 / 变化图，`GameControlPanel.tsx:75-90`），右上角挂余次角标（`/platforms/golaxy/engine/items`，
> 每次分析结算后重拉），`0` 用红底**不灰掉**，`—` 是「没取到数」；另外**没有胜率图表**、
> **悔棋在星阵算招期间禁用**、多一条平台条。稿子现在有第 ⑪ 屏「星阵围棋 · 对局中」专画这一屏。
> ⇒ 对齐这条链时，**`platform-engine` 的「开始对局」接的是第 ⑪ 屏，不是第 ⑤ 屏**；
> 两屏骨架相同但右栏不同，照第 ⑤ 屏做出来会是一个看着像对的错。
> 稿子在 `smartbox-software/superpowers/shared/kiosk-shell/sample-go/`（**27 屏 / 闸 754 条全过**）。
> 画廊版（逐屏对规范）：https://claude.ai/code/artifact/f1cf8ada-61c3-4950-b785-dee11963924e
> 原型版（点着走，验跳转用）：https://claude.ai/code/artifact/e4d3c7ef-82dd-4a5e-a7b0-42db6b4ad731
>
> D1（成长本轮跳过）**不变**：那一屏稿子上一直有，是实现这边登记过的落后一项，不是设计缺口。

### D3 `.kiosk-actions` 是 n 列等宽，围棋是 4 个动作

规范 §11 那张表写「动作区 **3 列**等宽」，而围棋稿对局屏是 4 个（形势 / 悔棋 / 停一手 / 认输）、做题屏也是 4 个（提示 / 退一手 / 重摆 / 下一题）。

**这不是冲突**：`tokens.css:802` 的 `.kiosk-actions` 是 `grid-auto-flow: column; grid-auto-columns: 1fr`，几个就摆几个，规范那个「3」是当时国象的实例数。**照稿子摆 4 个。**

### D4 复盘左栏第三格：**先按规范写「漏着」，除非拿到反证**

- 规范 §5 明写：复盘那三格是 `准确率 · 失误 · 漏着`（**不是妙手** —— 妙手要 MultiPV + 更深搜索）。
- 围棋稿 07 屏和它自己的闸 `sample-go/gate.mjs:29` 写的是 `["准确率", "失误", "妙手"]`，理由是「报告任务逐手存了 delta_winrate / delta_score」。

两边不一致。**判据不是谁的辈分大，是围棋这边到底算不算得出来**：规范那条禁令是从 alpha-beta 引擎推出来的（它一次只吐一个 `bestmove`），而 KataGo 的分析接口天然返回多个 `moveInfos`——**这是 §13 那条「规范里更具体的那条本来就管这件事」的同族情形**。

⇒ Task 16（07 复盘屏）**第一步就是去 `katrain/web/api/` 与 `report_task_moves` 表核实**：逐手数据里有没有「这一手是不是唯一好手」所需的第二名着法评分。
- 有 ⇒ 写「妙手」，并在 Task 里记下这条判据（照稿子）。
- 没有 ⇒ 写「漏着」（照规范），并把这条差异登记回 `sample-go/gate.mjs` 的待提上游清单。
- **两种都不许写「—」蒙混**：这一格是能查清楚的。

### D5 稿子的 `.danger` 类**没有任何样式**

围棋稿对局屏写的是 `<button class="danger">认输</button>`（`go-kiosk.tmpl.html:305`），而 `.danger` 在 `tokens.css` 和稿子自己的 `<style>` 里**都没有定义**——实测 `grep -c` 只在那一处出现。所以稿子上的「认输」和旁边三个按钮**长得一模一样**（参考图 `02-game.png` 可证）。

这与 `kiosk-design-alignment.md` §4① 描述的两派**都不同**，是第三种。⇒ 已按 **D7** 裁定：照抄五子棋 `index.css:1619`（同一个类名、同一份配方），稿子那份「零样式」是稿子自己没写全，不是设计意图。

### D6 参考图与实现之间**预期存在**的差异，登记在此

四图对比时下面这些差异**不是回归**，不要去「修」它们：

| 差异 | 为什么 |
|---|---|
| 稿子上大段旁注（`.note`）实现里没有 | G5 |
| Dock 项数（6 vs 参考图的 7，见 D8） | D1 的后果 |
| 稿子时钟恒为 `16:40`、用户恒为「访客」 | 稿子是静态样张；实现读真时钟与真身份 |
| 稿子上的题量 / 课本数 / 胜率曲线是示意值 | 稿子自己写明「不写死任何一个题量，写了就是编」（`:349`） |
| 参考图挡局屏左栏摆了一盘开局子，实现是空盘 | D11 —— 摆一个不是这一局的局面是拿装饰冒充状态（国象 `BoardConsole.tsx` 写下的规矩） |
| 木纹贴图 | 稿子在木色渐变上叠了一层 `--oak`（`mix-blend-mode:multiply`），那张图在 `sample-go/board-assets.json` 里，**不在共享资产包、不在 `MANIFEST.sha256` 管辖内**。上一轮就没抄，本轮同样不抄——抄它等于往仓里塞一份没人核的二进制。要对齐得先把它收进资产包（记账，非本轮） |

---

## File Structure

### 新建

| 文件 | 责任 |
|---|---|
| `src/kiosk/shell/KioskFrame.tsx` | 全站唯一外壳：`.kiosk`（缩放）→ `.kiosk-screen[data-level]` → 顶栏 + `.kiosk-content` + Dock |
| `src/kiosk/shell/kioskScale.ts` | `calculateKioskScale(w, h)` 纯函数 + 单测 |
| `src/kiosk/shell/KioskTopbar.tsx` | §6 上边条 |
| `src/kiosk/shell/KioskDock.tsx` | §3 底部 Dock（词典与顺序写死） |
| `src/kiosk/shell/KioskConsoleRail.tsx` | §5 L1 左栏：标题 + 248 镜像框 + 32 同步行 + 三格状态 |
| `src/kiosk/shell/KioskStatusCells.tsx` | 三格 / 两格状态格（`.kiosk-status`） |
| `src/kiosk/shell/KioskCard.tsx` | §8 一级页模式卡 220×76（含 `is-ring` / `is-current` / `is-soon` / `is-todo`） |
| `src/kiosk/shell/KioskScrollZone.tsx` | §5.2 悬浮滚动条 + 渐隐 + `scrollTop` 归零（**承重**） |
| `src/kiosk/shell/KioskPagebar.tsx` | §11 页控条（返回 / 标题 / 副标 / 分段） |
| `src/kiosk/shell/KioskFold.tsx` | §11 可折叠面板 |
| `src/kiosk/shell/KioskSecLabel.tsx` | 组标题行（中文 + 英文斜体 + 渐隐横线 + 右端 `secval`） |
| `src/kiosk/shell/icons.tsx` | Phosphor v2 静态 SVG（从 `kiosk-shell/icons/` 取，不手写内联路径） |
| `src/kiosk-shell/go-screens.css` | **围棋屏级类**，从 `go-kiosk.tmpl.html` 的 `<style>` 抄来，**但只抄共享包里没有的那些**（G10 已把被上游收编的剔掉了）。精确清单见 Task 9 |
| `src/kiosk/shell/GoBoardSvg.tsx` | 19×19 交叉点盘（`MARGIN = 0.5`、`COLS = "ABCDEFGHJKLMNOPQRST"`、九星），大小两用 |
| `tests/helpers/fourup.ts` | 四图闸公共 helper（9 个消费者，够格抽） |
| `tests/kiosk-shell-geometry.spec.ts` | 外壳几何闸（真浏览器量 1024×600） |
| `tests/kiosk-shell-contract.spec.ts` | 契约闸：无 `vw`/`vh` 泄漏、`.kiosk` 作用域、无手写内联图标 |
| `tests/kiosk-screen-NN-*.fourup.spec.ts` ×9 | 每屏一条四图闸 |
| `superpowers/tracks/kiosk-go-shell-align/visual/NN-*/1024x600/` | 四图产物 |

### 修改

| 文件 | 改什么 |
|---|---|
| `src/kiosk/KioskApp.tsx` | 引 `tokens.css` / `go-tokens.css` / `go-screens.css`；路由重排（Dock 词典） |
| `src/kiosk/components/layout/KioskLayout.tsx` | 改成套 `KioskFrame`，不再自己拼 flex 列 |
| `src/kiosk/components/layout/Header.tsx` | **删**，由 `shell/KioskTopbar.tsx` 取代 |
| `src/kiosk/components/layout/Dock.tsx` / `navTabs.tsx` | **删**，由 `shell/KioskDock.tsx` 取代 |
| `src/kiosk/components/layout/SmartBoardConsole.tsx` | **删**，由 `shell/KioskConsoleRail.tsx` 取代 |
| `src/kiosk/components/layout/SubPageBar.tsx` | **删**，17 屏改用 `shell/KioskPagebar.tsx` |
| `src/kiosk/components/common/OptionChips.tsx` | 去掉自挂的 `.kiosk` 与三条 CSS import（已由根提供） |
| `src/kiosk/components/aiLadder/KioskAiLadderBlockingPanel.tsx` | 同上 |
| `src/kiosk/pages/*.tsx` | 逐屏改成共享类（Task 10–19） |
| `src/kiosk/theme.ts` | 保留字族导出；`fonts.css` 的 import 移到 `KioskApp.tsx` 与其余 CSS 并列 |

### 不动

`src/components/`（除 `Board3D/`）、`src/hooks/`、`src/context/`、`src/api*`、`src/utils/`、`src/types/` —— **共享领地，改它波及 galaxy**。本轮凡是想改共享组件的，一律先停下来记账（上一轮 `LiveBoard` 的 `gridMargins = 1.5 格` 就是这么记的：规范要 0.5，差整整一格 ≈24px，改它会动到 galaxy 和对局屏，所以自己画一块，不改共享件）。

---

## 四条已裁定（Fan 2026-08-20 二次授权：「你自己做决定吧。相似功能的模块尽量和其他三种棋类的 kiosk 界面保持一致」）

原来这里挂着 Q1–Q4 四条「不许自己定」。Fan 把裁量权交回来了，**并且给了判据**：不是我凭审美挑，
是**去看象棋 / 国象 / 五子棋这三家同一个模块怎么做的，照做**。下面四条都是这么定出来的，
每条都点名了取证的那一行。执行时照做，不要重新讨论。

### D7（原 Q1）破坏性按钮 —— 照抄五子棋那一条，一个字不改

三家里**只有五子棋在 `.kiosk-actions` 里真的摆了「认输」这颗键**，而且它的类名和围棋稿
一模一样：`<button type="button" className="danger">` (`gomoku/ui/src/play/GameRail.tsx:373`)。
它的样式是 `gomoku/ui/src/index.css:1619` 一行：

```css
.play-screen .kiosk-actions .danger {
  color: var(--bad);
  border-color: color-mix(in srgb, var(--bad) 35%, var(--hair));
}
```

**形状、尺寸、内边距、背景一律不动，只有字色和边框着一点红。** 这正好落在原来三派的
中间：屏上认得出，但不靠实心色块吓人。

⇒ 围棋写同一条，选择器换成 `.kiosk-screen[data-screen="game"] .kiosk-actions .danger`，
放 **`go-screens.css`**（不是 `tokens.css` —— 那份是共享正本，这条等上游收编）。
`--bad` / `--hair` 都定义在 `tokens.css` 的 `.kiosk` 里，而这颗键渲染在 `.kiosk` 内，
求值没问题（G2）。

**二次确认框本轮不新造**：稿子没画。现状 `GamePage` 有什么保持什么，只核**一件事** ——
它的确认键**不能在 `.kiosk` 外面写 `var(--bad)`**。国象在 `chess/ui/src/index.css:574-580`
把这个坑记下来了：`--bad` 只定义在 `.kiosk` 上，挂在 app 根上的弹窗写它会静默求空，
真浏览器量出来是 `rgba(0,0,0,0)` —— 红键**看起来就是没红**。Task 11 Step 5 加一条断言。

（国象另有一条自己写下的判据 `index.css:571`「不可撤销的那一下才标红，而且只标**第二下**」，
和 D7 不冲突：它说的是没有屏上认输键时红标在哪儿。围棋两处都有，屏上走五子棋那条、
弹窗那颗本轮不动。）

### D8（原 Q2）Dock **六项**

原来担心的是「参考图七格、实现六格，九张差异图底部会有一条固定红带」。**取证之后这个顾虑降级了**：

- 五子棋自己就是 **6 项**（`gomoku/ui/src/shell/dockRoutes.ts`）—— 它没有「棋谱」那一格，因为五子棋没有棋谱库。
- 象棋 7 项（`xiangqi/ui/src/shell/KioskDock.tsx`）、国象 7 项（`chess/ui/src/shell/routes.ts`）。

⇒ **「四家 Dock 项数必须相等」从来不是规矩。** 规矩是「词与顺序来自共享词典、
专属项最多一个且钉在训练营之后」。围棋 `对弈 训练营 棋谱 复盘 课程 设置` 满足这条，
和五子棋同为 6 项。成长按 D1 跳过，不摆假入口（G8）。

⇒ **方案 (a)，6 项。** 每张四图的标签带里写死这句：**「参考图的 Dock 是 7 格，实现是 6 格，
差的是成长（D1 跳过）——底部这条红带是预期差异，不是回归。」**

### D9（原 Q3）顶栏那四样 **全部拆掉**

- 三家顶栏都是**同一份**：logo / 智星盒·StellaBox / 分隔线 / 棋种名 / 主页 / 头像 / 名字 / 时钟。
  **零指示器、零齿轮**（`xiangqi/ui/src/shell/KioskTopbar.tsx` 整份可证）。
- 器件状态在四家共同的另一个位置：**L1 左栏 `.kiosk-console` 底部的 `.kiosk-status` 三格**。
  国象 `chess/ui/src/shell/boardStatus.ts` 把它写死成「三格的**格数、顺序、灯色语义**四棋类相同，
  只有第一格跟着硬件走」—— 国象第一格是「传感盘」，围棋第一格就是「摄像头」。
  围棋稿 L1 屏上那个 `<div class="kiosk-status" data-status></div>` 就是这三格。
- **围棋现状已经有这三格了**：`SmartBoardConsole.tsx:171-188`（摄像头 / 标定 / LED）。
  所以顶栏那两个是**同一份信息的第二个出口**，拆掉不丢信息。
- 原来写的「拆了 L3 就盲了」**是错的，取证推翻**：`GamePage.tsx:14,18` 已经挂了
  `VisionSyncOverlay` + `PhysicalPlayStatusChip`，外加 `RecalibrationModal`；做题屏走
  `usePhysicalTsumego`。**L3 上摄像头掉线是「打断」不是「读数」** —— 它本来就该弹东西，
  不该常驻一个小点。国象那句「盘上没有的器件不摆在界面上」是同一个态度。
- 引擎状态点：四家顶栏都没有。拆。
- 齿轮：规范 §1 点名拆（Dock 里已经有设置）。

⇒ **方案 ①。** Task 3 删 `Header.tsx` 时这四样一并删。`VisionIndicators` / `GeometryIndicator`
是 `Header.tsx` 里的局部组件，跟着没了；**动手前先 grep 确认 `Header.tsx` 之外没有第二个使用者**。

### D10（原 Q4）设置页 **只做有内容的组**

- 国象 `chess/ui/src/pages/SettingsPage.tsx` 的 `<aside aria-label="设置分类">` 只有**两项**
  （棋盘与棋子 / 声音与语音），右边三张卡。稿子画多少组，它没跟。
- 象棋 `xiangqi/ui/src/screens/SettingsScreen.tsx` 是**一条八行的平表**，连导航都没有。
- 五子棋根本没有设置屏。
- **三家没有一家摆过空组，也没有一家挂过「未接后端」的空壳。**

⇒ **方案 (a)。导航项数 = 真有内容的组数，词一一对应。** 和参考图差的那几组写进标签带，
和 D8 那条红带一样属于登记过的预期差异。

**语言那一格：留着。** 登记成规范 §12 的一处已知偏差 —— 设置中心不在本仓，搬走等于
这台盒子上再没有语言开关。（国象把「语音语言」做成 disabled + 「跟随界面语言」，
那是**语音**语言；围棋这一格是**界面**语言本身，不是同一件事，不照抄。）

### D11（scope.md §7 第二条）挡局屏左栏 **画盘，但画空盘**

参考图画的是**完整开局局面**，围棋现版是空态。国象把这条规矩写在
`chess/ui/src/shell/BoardConsole.tsx` 的注释里，一字不改地适用：

> **不画局面**：盒子上还没有传感盘，盘面数据一个字节都拿不到，摆一个开局局面上去
> 就是拿装饰冒充状态。空盘 + 一行说明，才是今天的真相。

它渲染的是 `EMPTY_FEN`（不是初始局面），底下压一句 `mirrorNote()`。

**围棋现状已经就是这个形态**：`SmartBoardConsole.tsx` 把 `moves ?? []` 传给
`LiveBoard`（真盘面网格 + 星位、零颗子），叠一条 `实时预览暂不可用 · no live feed`。

⇒ **不改行为，只改外观**：Task 5 把这块卡搬进 `.kiosk-console` 时，
盘面数据照旧空、说明句照旧在（那句已经修过对比度，别退回去）。
参考图那盘开局子是**样张**，登记进 D6 的预期差异表。

### G12（新增，本轮起长期有效）相似模块先看那三家

Fan 2026-08-20 的原话：「相似功能的模块尽量和其他三种棋类的 kiosk 界面保持一致」。
⇒ **每屏动手前，先找出那三家里做同一件事的那一屏 / 那一个组件，读它，照它。**
稿子和三家实现打架时，**先查是不是自己看漏了**（D7 就是这么翻案的：稿子上 `.danger`
零样式看着像「不区分」，其实五子棋早就给同一个类名写好了一行）。
真打架且三家一致时，**以三家为准**并在这里补一条 D。

---

## Task 0: 存基线

**红了才知道是不是自己弄的 —— 而 `lint` 和 `npm test` 本来就是红的。** 一条改动都还没做的时候先把基线存下来，后面每次比的都是它。

**Files:** 无（只产出 `/tmp` 里的基线文件与一条提交注记）

- [ ] **Step 1: 确认工作树干净、分支对**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-align
git status --porcelain            # 期望空
git rev-parse --abbrev-ref HEAD   # 期望 feature/kiosk-go-shell-align
git log --oneline -1              # 期望 0f821149
```

- [ ] **Step 2: 存单测基线（本来就有 3 个文件红）**

```bash
cd katrain/web/ui && npm install --no-audit --no-fund   # node_modules 可能不在
npm test 2>&1 | tee /tmp/kiosk-base-test.log | tail -5
grep -E '^\s*(FAIL|×)' /tmp/kiosk-base-test.log | sort > /tmp/base.txt
wc -l /tmp/base.txt
```

Expected: `Test Files 3 failed | 134 passed`，`Tests 6 failed | 1228 passed | 5 skipped`。三个红的是 `GamePageEngine.test.tsx`、`ReportsPage.polling.test.tsx`、`ReportsPage.test.tsx`（4 条全是 `Test timed out in 5000ms`）。

**这三条本轮不修**，它们和外壳无关。但 **Task 16 会重写 `ReportsPage`** —— 到那时如果它们变绿了，很好；如果换了个红法，**要能说清是哪一条**，这份基线就是为那一刻存的。

- [ ] **Step 3: 存 lint 基线（本来就 315 条）**

```bash
cd katrain/web/ui && npx eslint . 2>&1 | tee /tmp/kiosk-base-lint.log | tail -3
grep -oE '^/[^ ]+' /tmp/kiosk-base-lint.log | sort -u > /tmp/base-lint-files.txt
wc -l /tmp/base-lint-files.txt
```

Expected: `✖ 315 problems (258 errors, 57 warnings)`。

- [ ] **Step 4: 确认三条构建基线是绿的**

```bash
cd katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d
```

Expected: 三条全 EXIT 0。`build:kiosk-2d` 末尾要看到 `✅ kiosk boundary clean`。**这三条本来就绿，所以本轮任何一条红了都是自己弄的。**

- [ ] **Step 5: 存 vendored 资产基线**

```bash
cd katrain/web/ui/src/kiosk-shell && shasum -a 256 -c MANIFEST.sha256 2>&1 | grep -c ': OK$'
```

Expected: **209**。（Task 6 之后会变成 290。）

- [ ] **Step 6: 备份会被 Playwright 默认 config 改掉的东西**

```bash
cp ~/.katrain/config.json ~/.katrain/config.json.bak-$(date +%Y%m%d) 2>/dev/null || true
```

`python -m katrain --ui web` **退出时会重写 `~/.katrain/config.json`**。本计划推荐用 `playwright.visual.config.ts`（不起 Python），但万一有人用了默认那份，这份备份是唯一的退路。

- [ ] **Step 7: 把基线数字记进 track**

在 `superpowers/tracks/kiosk-go-shell-align/scope.md` 末尾追加一节「基线（2026-08-20，动手前实测）」，把上面五组数字写进去。**写进仓库，不要只留在 `/tmp`** —— `/tmp` 会被清，而下一个人需要它才能判断「这条红是不是我弄的」。

```bash
git add superpowers/tracks/kiosk-go-shell-align/scope.md
git commit -m "docs(kiosk): 记下动手前的基线 —— lint 与单测本来就是红的

315 条 lint、3 个测试文件红(GamePageEngine / ReportsPage ×2),三条构建绿、
MANIFEST 209/209。判据从此是**基线 diff**,不是「全绿」——
按文件名判「看着不相关」会把自己造的污染归给既有噪声。"
```

---

## Task 1: 画布与作用域 —— `.kiosk` / `.kiosk-screen` / 缩放

把 kiosk 从「100vw×100vh 流式 + 三处各自挂 `.kiosk`」改成「固定 1024×600 逻辑画布 + 根节点一处 `.kiosk`」。**这是整条盒子链的根，它不对后面每一屏都白量。**

**Files:**
- Create: `katrain/web/ui/src/kiosk/shell/kioskScale.ts`
- Create: `katrain/web/ui/src/kiosk/shell/kioskScale.test.ts`
- Create: `katrain/web/ui/src/kiosk/shell/KioskFrame.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`（加 CSS import）
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx:18-33`
- Modify: `katrain/web/ui/src/kiosk/components/common/OptionChips.tsx:1-3,40`
- Modify: `katrain/web/ui/src/kiosk/components/aiLadder/KioskAiLadderBlockingPanel.tsx:16-17,93`
- Test: `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts`

**Interfaces:**
- Produces: `calculateKioskScale(viewportW: number, viewportH: number): number`
- Produces: `<KioskFrame level={1|2} dock={ReactNode} extras={ReactNode}>{children}</KioskFrame>`，渲染 `div.kiosk > div.kiosk-screen[data-level] > (topbar 插槽 + div.kiosk-content + dock)`
- Consumes: 无

- [ ] **Step 1: 写失败的单测——缩放是纯函数**

`katrain/web/ui/src/kiosk/shell/kioskScale.test.ts`：

```ts
import { describe, expect, test } from 'vitest';
import { calculateKioskScale } from './kioskScale';

// 画布是固定的 1024×600(规范开头那句「画布:固定 1024×600 …本规范全部用 px」)。
// 这个函数只回答一件事:真视口装不装得下那块固定画布,装不下缩多少。
describe('calculateKioskScale', () => {
  test('设备基准 1024×600 正好是 1:1,不缩', () => {
    expect(calculateKioskScale(1024, 600)).toBe(1);
  });

  test('视口更大也不放大 —— 放大会把 px 尺规变成谎话', () => {
    expect(calculateKioskScale(1920, 1080)).toBe(1);
  });

  test('宽度不够时按宽度缩', () => {
    expect(calculateKioskScale(800, 600)).toBe(800 / 1024);
  });

  test('高度不够时按高度缩', () => {
    expect(calculateKioskScale(1024, 300)).toBe(300 / 600);
  });

  test('两边都不够取更紧的那一边', () => {
    expect(calculateKioskScale(512, 450)).toBe(0.5); // 512/1024=0.5 < 450/600=0.75
  });
});
```

- [ ] **Step 2: 跑它，确认红**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/kioskScale.test.ts
```

Expected: FAIL — `Cannot find module './kioskScale'`

- [ ] **Step 3: 写实现**

`katrain/web/ui/src/kiosk/shell/kioskScale.ts`：

```ts
/**
 * 画布是**固定的** 1024×600 —— 规范开头那句话:「四张设计稿都是这个值,所以本规范
 * 全部用 px。任何人不要把这些值改成 cqw / vw / %:一旦相对化,『切模块不跳』就没法用
 * 截图证明。」所以这里做的是**整块画布等比缩放**,不是让布局自己流。
 *
 * 不放大(`Math.min(…, 1)`):放大之后屏上量到的 px 就不再是 tokens.css 里那个 px,
 * 几何闸和四图闸量的都会是被放大过的数,尺规就成了谎话。板子本来就是 1024×600。
 */
export const KIOSK_CANVAS_W = 1024;
export const KIOSK_CANVAS_H = 600;

export function calculateKioskScale(viewportW: number, viewportH: number): number {
  return Math.min(viewportW / KIOSK_CANVAS_W, viewportH / KIOSK_CANVAS_H, 1);
}
```

- [ ] **Step 4: 跑它，确认绿**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/kioskScale.test.ts
```

Expected: PASS，5 条全绿

- [ ] **Step 5: 写 `KioskFrame`**

`katrain/web/ui/src/kiosk/shell/KioskFrame.tsx`。结构照象棋 `xiangqi/ui/src/shell/KioskFrame.tsx` —— 那是活样本，别自己发明：

```tsx
import { useEffect, useState, type ReactNode } from 'react';
import { calculateKioskScale } from './kioskScale';

function useKioskScale(): number {
  const measure = () => calculateKioskScale(window.innerWidth, window.innerHeight);
  const [scale, setScale] = useState(measure);
  useEffect(() => {
    const onResize = () => setScale(measure());
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return scale;
}

/**
 * 全站唯一的外壳。规范 §5:顶栏和 Dock 都是通栏贴边,中间区外框 x16–1008、y70 起,
 * L1 时下缘 504(Dock 在场)、L2/L3 时 586。
 *
 * `.kiosk` 挂在**这一层**(不是各屏各挂)—— tokens.css 整份定义在 `.kiosk {}` 里,
 * 在它外面 var() 静默求空、字体掉回 sans、color-mix 整条作废,而且不报错。
 *
 * @param level 1 = 一级页(有 Dock,中间区 434 高);2 = 二/三级页(无 Dock,516 高)
 * @param dock  一级页传 <KioskDock/>;二/三级页不传
 * @param topbar 顶栏节点(Task 3 之前先传 null,Task 3 起恒传 <KioskTopbar/>)
 * @param extras 盖在整屏之上、但仍跟着画布缩放的东西(弹窗、全局提示)
 */
export function KioskFrame({ level, topbar, dock, extras, children }: {
  level: 1 | 2;
  topbar?: ReactNode;
  dock?: ReactNode;
  extras?: ReactNode;
  children: ReactNode;
}) {
  const scale = useKioskScale();
  return (
    <div
      className="kiosk"
      style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: `translate(-50%, -50%) scale(${scale})`,
      }}
    >
      {/* data-level 写成字符串:tokens.css:423 那条选择器是 [data-level="1"],
          它决定 L1 的中间区下缘停在 504 还是 586 —— 写错整屏内容会被 Dock 压住。 */}
      <div className="kiosk-screen" data-level={String(level)}>
        {topbar}
        <div className="kiosk-content">{children}</div>
        {dock}
      </div>
      {extras}
    </div>
  );
}
```

- [ ] **Step 6: 把 CSS 引到 kiosk 应用根**

`katrain/web/ui/src/kiosk/KioskApp.tsx`，在既有 import 之后加：

```ts
// 顺序不可换:fonts.css 先声明字族,tokens.css 的 --font-* 才指得到它;
// go-tokens.css 补 tokens.css 不定义的 --paper / --accent-soft(漏掉就是静默求空);
// go-screens.css 是围棋屏级类,Task 9 才建 —— 那之前先不要加这一行。
import '../kiosk-shell/fonts.css';
import '../kiosk-shell/tokens.css';
import '../kiosk-shell/go-tokens.css';
import '../kiosk-shell/seclabel.css';
```

同时把 `src/kiosk/theme.ts:6` 那行 `import '../kiosk-shell/fonts.css'` 删掉（现在由 `KioskApp.tsx` 统一引，两处引同一份 CSS 会让「谁先谁后」变成打包器的实现细节）。

**这一步在 `KioskApp.tsx` 而不是 `main.tsx`**：`AppRouter.tsx:17` 是 `lazy(() => import('./kiosk/KioskApp'))`，引在这里，CSS 就落进 kiosk 分块，galaxy 不受影响；kiosk-2d 构建里 galaxy 整条被 DCE，也不受影响。

- [ ] **Step 7: 让 `KioskLayout` 套上 `KioskFrame`**

`katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`，把 `KioskShell` 的返回值换成：

```tsx
  return (
    <KioskFrame
      level={isL1 ? 1 : 2}
      topbar={immersive ? undefined : <Header username={username} showHome={isL1} onHome={...} />}
      dock={showDock ? <Dock /> : undefined}
    >
      {/* 内容区暂时保持现状:左栏与 <Outlet/> 的两栏化留给 Task 5,
          本 Task 只把画布和作用域立起来 —— 一次只改一层,断点才定位得到。 */}
      <Box sx={{ display: 'flex', height: '100%', minHeight: 0 }}>
        {showConsole && <SmartBoardConsole />}
        <Box component="main" sx={{ flex: 1, minWidth: 0, minHeight: 0, overflow: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
    </KioskFrame>
  );
```

`Header` 与 `Dock` 暂时留用旧的（Task 3 / Task 4 才换）；`immersive` 语义保持不变。

- [ ] **Step 8: 去掉三处自挂的 `.kiosk` 与重复 CSS import**

全仓今天挂 `.kiosk` 的**恰好三处**（`grep -rn 'className="kiosk"\|className="kiosk '` 实测）：

- `OptionChips.tsx:1-3` 删掉三行 CSS import；`:40` 的 `<div className="kiosk">` 改成 `<div>`。
- `KioskAiLadderBlockingPanel.tsx:16-17` 删掉两行 CSS import；`:93` 的 `className="kiosk kiosk-side"` 改成 `className="kiosk-side"`。
- `AiSetupPage.tsx:217` 的 `<Box className="kiosk" sx={{ height:'100%', boxSizing:'border-box', px:'var(--content-x)', py:'var(--content-pad-y)' }}>` —— 去掉 `className="kiosk"`，**并且把 `px`/`py` 一起去掉**：`.kiosk-content`（`tokens.css:415-422`）现在自己就给 `left/right: var(--content-x)` 和 `padding: var(--content-pad-y) 0`，留着就是**两层内边距叠加**，中间区从 992 缩成 960、纵向各多 14。
- `blockingPanel.css:1` 那条 `@import '../../../kiosk-shell/seclabel.css'` 删掉（根已引）。

⚠️ 删之前先确认：这三个组件的**每一个**渲染位置都在 `KioskFrame` 里面。`AiSetupPage` / `PvpLocalSetupPage` 在 `KioskLayout` 的 `<Outlet/>` 下 —— 在。若发现有 MUI `Dialog` / `Popover` / `Menu` portal 出去的用法（它们默认 portal 到 `body`），**那个用法要自己挂回 `.kiosk`**（G1）。`PlatformConnectPage` 的登录 `Dialog`、`PlatformLobbyPage` 的挑战 `Dialog`、`ReportsPage` 的删除 `Dialog`、`SettingsPage` 的语言 `Select`（`Menu`）都是这一类——**逐个查**。

> 这一步是**替换不是叠加**：`AiSetupPage` 那处 `px/py` 曾经是对的（那时没有 `.kiosk-content`），现在它变成重复。留着不报错，只是尺寸悄悄小一圈——又是一次静默失败。

- [ ] **Step 9: 写外壳几何闸（真浏览器，承重）**

`katrain/web/ui/tests/kiosk-shell-geometry.spec.ts`：

```ts
import { expect, test } from '@playwright/test';

/**
 * 承重闸:量的是**真浏览器算出来的布局结论**,不是 CSS 里写了什么。
 * jsdom 没有布局引擎,对这些数字无权作证。
 *
 * 期望先写成**关系式**,具体像素只 console.log 记录、不作判据 ——
 * 「盘吃满纵向」是判据,「516」只是它今天的值。
 */
const CANVAS = { w: 1024, h: 600 };

async function boot(page, path: string) {
  await page.setViewportSize(CANVAS);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-shell-geometry');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.goto(path);
  await page.waitForSelector('.kiosk-screen');
}

const box = (page, sel: string) => page.locator(sel).evaluate((el: Element) => {
  const r = el.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});

test('L1:画布 1024×600、顶栏通栏贴顶、Dock 通栏贴底、中间区 x16–1008 y70–504', async ({ page }) => {
  await boot(page, '/kiosk/play');

  const screen = await box(page, '.kiosk-screen');
  expect(screen.w).toBe(CANVAS.w);
  expect(screen.h).toBe(CANVAS.h);

  const topbar = await box(page, '.kiosk-topbar');
  expect(topbar.x).toBe(screen.x);                 // 通栏贴边,不留左右外边距
  expect(topbar.y).toBe(screen.y);
  expect(topbar.w).toBe(screen.w);
  expect(topbar.h).toBe(56);

  const dock = await box(page, '.kiosk-dock');
  expect(dock.x).toBe(screen.x);
  expect(dock.w).toBe(screen.w);
  expect(dock.h).toBe(82);
  expect(dock.y + dock.h).toBe(screen.y + screen.h);   // 贴底

  const content = await box(page, '.kiosk-content');
  expect(content.x - screen.x).toBe(16);
  expect(content.w).toBe(screen.w - 2 * 16);           // 992
  expect(content.y - screen.y).toBe(topbar.h);         // 内容盒从顶栏下缘起
  expect(content.y + content.h).toBe(dock.y);          // 下缘停在 Dock 上沿
});

test('L2/L3:没有 Dock,中间区一路到底(y70–586)', async ({ page }) => {
  await boot(page, '/kiosk/settings');   // Task 4 之前 settings 仍是 L2
  await expect(page.locator('.kiosk-dock')).toHaveCount(0);

  const screen = await box(page, '.kiosk-screen');
  const content = await box(page, '.kiosk-content');
  expect(content.y + content.h).toBe(screen.y + screen.h);
});

test('token 求得到值 —— .kiosk 作用域真的生效了', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const vars = await page.locator('.kiosk-screen').evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      railW: cs.getPropertyValue('--l1-rail-w').trim(),
      paper: cs.getPropertyValue('--paper').trim(),        // 只 go-tokens.css 有 —— 用它单独证明第二份 CSS 也进来了
      accent: cs.getPropertyValue('--accent').trim(),      // go-tokens 覆盖 tokens 的中性占位 -> 必须是青玉
      font: cs.fontFamily,
    };
  });
  // 空字符串 = var() 静默求空 = .kiosk 没生效。这一条就是为了把那种静默失败推红。
  // 三个值分别证明三件事:tokens.css 进来了 / go-tokens.css 也进来了且在它之后 / fonts.css 的族名指得到。
  expect(vars.railW).toBe('296px');
  expect(vars.paper).not.toBe('');
  expect(vars.accent.toUpperCase()).toBe('#58B57A');   // 不是 tokens.css 的中性占位 #… ⇒ 顺序也对
  expect(vars.font).toContain('SmartBox');
});
```

- [ ] **Step 10: 跑几何闸**

```bash
cd katrain/web/ui && npx playwright test tests/kiosk-shell-geometry.spec.ts --reporter=list
```

Expected: 前两条 PASS；第三条也 PASS。若 `--paper` 为空 → `go-tokens.css` 没进作用域，回 Step 6。

- [ ] **Step 11: 演示这道闸有牙（变异）**

把 `KioskFrame.tsx` 里 `className="kiosk"` 临时改成 `className="kiosk-off"`，重跑第三条。

Expected: **红**，报文含 `--l1-rail-w` 求得空串。改回来，重跑，绿。

> 这一步不是形式：`var()` 求空**不报错**，它是本轮最容易静默失败的一处。没演示过的闸和没有闸长得一样。

- [ ] **Step 12: 双构建 + 类型**

```bash
cd katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d
```

Expected: 三条全绿。`build:kiosk-2d` 末尾的 `verify:kiosk-2d` 必须 exit 0。

- [ ] **Step 13: 提交**

```bash
git add katrain/web/ui/src/kiosk/shell katrain/web/ui/src/kiosk/KioskApp.tsx \
        katrain/web/ui/src/kiosk/theme.ts \
        katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx \
        katrain/web/ui/src/kiosk/components/common/OptionChips.tsx \
        katrain/web/ui/src/kiosk/components/aiLadder/ \
        katrain/web/ui/tests/kiosk-shell-geometry.spec.ts
git commit -m "feat(kiosk-shell): 立起固定 1024×600 画布,把 .kiosk 提到 kiosk 应用根

tokens.css 整份定义在 .kiosk 里,此前只有 3 个消费点各自挂;提到根之后
全部 kiosk 屏才拿得到那 991 行几何 token。几何闸在真浏览器量,并变异演示过
(className 改掉 -> --l1-rail-w 求空 -> 红)。"
```

---

## Task 2: 四图闸 helper —— 九屏共用一份

上一轮那条四图 spec（`kiosk-layout-a-vs-xiangqi-setup.spec.ts`）里的合成代码是**对的**，但它写在唯一那个调用点里。本轮有 **9 个消费者**，够格抽了。

> ⚠️ 抽的判据是**消费者数**，不是「看起来通用」。上一轮那条「非黑采样点」判据只有一个调用点，就**没有**做成 helper——那是同一条规则的另一半。

**Files:**
- Create: `katrain/web/ui/tests/helpers/fourup.ts`
- Test: 本 Task 用 Task 1 已有的 `/kiosk/play` 当被测物做一次自测（产物是临时的，Task 10 会覆盖）

**Interfaces:**
- Produces:
  ```ts
  export interface FourUpOptions {
    page: Page;
    /** 参考图绝对路径,sample-go/shots/NN-*.png */
    referencePng: string;
    /** 产物目录,superpowers/tracks/kiosk-go-shell-align/visual/NN-*/1024x600/ */
    outDir: string;
    /** 文件名前缀,如 '01-play' */
    slug: string;
    /** 画在并排图左半标签带上的一句话 */
    referenceCaption: string;
    /** 画在并排图右半标签带上的一句话 —— 预期差异必须写在图里 */
    implementationCaption: string;
  }
  export async function captureFourUp(o: FourUpOptions): Promise<{ both: number; refOnly: number; implOnly: number }>;
  export async function waitForRealPixels(page: Page, selector: string): Promise<void>;
  ```
- Consumes: Task 1 的 `.kiosk-screen`

- [ ] **Step 1: 写 helper**

`katrain/web/ui/tests/helpers/fourup.ts`。合成部分**逐字节搬** `kiosk-layout-a-vs-xiangqi-setup.spec.ts:66-160`，只把两个写死的路径和两句标签带提成参数：

```ts
import type { Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export const KIOSK_VIEWPORT = { width: 1024, height: 600 } as const;

export interface FourUpOptions {
  page: Page;
  referencePng: string;
  outDir: string;
  slug: string;
  referenceCaption: string;
  implementationCaption: string;
}

/**
 * 四图对比:参考 / 实现 / 并排 / 叠加+差异,同一 viewport 1024×600。
 *
 * ## 差异图为什么是**边缘图**不是像素比
 *
 * 稿子里有 26 处 `.note` 旁注(「围棋原来那张稿把它做成一张并列卡,是错的」这一类),
 * 它们是写给读稿人的,不上线 —— 已对齐三家一处都没搬。像素比会把这些整块报成回归。
 * 边缘图去掉颜色只留结构:**红 = 只有参考有边,绿 = 只有实现有,白 = 两边都有**。
 *
 * ⚠️ **像素差异一个都不作数。** 几何的判据在 kiosk-shell-geometry.spec.ts(真浏览器
 * 量出来的数),不在这几张图上。这几张图答的是「构图 / 分块顺序 / 组件层级对不对」。
 */
export async function captureFourUp(o: FourUpOptions) {
  mkdirSync(o.outDir, { recursive: true });
  const implementationPath = resolve(o.outDir, `${o.slug}--implementation.png`);
  await o.page.screenshot({ path: implementationPath });

  const asDataUrl = (file: string) => `data:image/png;base64,${readFileSync(file).toString('base64')}`;

  const result = await o.page.evaluate(async ({ refSrc, implSrc, refCap, implCap }) => {
    const load = (src: string) => new Promise<HTMLImageElement>((done, fail) => {
      const image = new Image();
      image.onload = () => done(image);
      image.onerror = () => fail(new Error('图片读不出来'));
      image.src = src;
    });
    const [reference, implementation] = await Promise.all([load(refSrc), load(implSrc)]);

    const W = 1024;
    const H = 600;
    const draw = (image: HTMLImageElement) => {
      const canvas = document.createElement('canvas');
      canvas.width = W; canvas.height = H;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, W, H);
      // 等比缩到 1024 宽再顶端对齐裁到 600 —— 样张是 2048×1202(2× 的 1024×601)。
      const scale = W / image.width;
      ctx.drawImage(image, 0, 0, W, Math.round(image.height * scale));
      return ctx;
    };
    const refCtx = draw(reference);
    const implCtx = draw(implementation);

    const edges = (ctx: CanvasRenderingContext2D) => {
      const d = ctx.getImageData(0, 0, W, H).data;
      const lum = new Float32Array(W * H);
      for (let i = 0; i < W * H; i += 1) {
        lum[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
      }
      const out = new Uint8Array(W * H);
      for (let y = 0; y < H - 1; y += 1) {
        for (let x = 0; x < W - 1; x += 1) {
          const i = y * W + x;
          const g = Math.abs(lum[i] - lum[i + 1]) + Math.abs(lum[i] - lum[i + W]);
          out[i] = g > 28 ? 1 : 0;
        }
      }
      return out;
    };
    const refEdges = edges(refCtx);
    const implEdges = edges(implCtx);

    const band = 34;
    const gap = 20;
    const side = document.createElement('canvas');
    side.width = W * 2 + gap;
    side.height = H + band;
    const sideCtx = side.getContext('2d')!;
    sideCtx.fillStyle = '#0f1416';
    sideCtx.fillRect(0, 0, side.width, side.height);
    sideCtx.drawImage(refCtx.canvas, 0, band);
    sideCtx.drawImage(implCtx.canvas, W + gap, band);
    sideCtx.fillStyle = '#93a49d';
    sideCtx.font = '600 14px system-ui, sans-serif';
    // ⚠️ 说明必须写在**图里**,不是写在旁边的文档里:图一旦离开它的说明,
    // 「界面对不对」和「稿子上那段旁注为什么没有」就混成一件事了。
    sideCtx.fillText(refCap, 4, 21);
    sideCtx.fillText(implCap, W + gap + 4, 21);

    const diff = document.createElement('canvas');
    diff.width = W; diff.height = H;
    const diffCtx = diff.getContext('2d')!;
    const out = diffCtx.createImageData(W, H);
    let both = 0, refOnly = 0, implOnly = 0;
    for (let i = 0; i < W * H; i += 1) {
      const a = refEdges[i]; const b = implEdges[i]; const p = i * 4;
      out.data[p + 3] = 255;
      if (a && b) { out.data[p] = 235; out.data[p + 1] = 235; out.data[p + 2] = 235; both += 1; }
      else if (a) { out.data[p] = 226; out.data[p + 1] = 104; out.data[p + 2] = 92; refOnly += 1; }
      else if (b) { out.data[p] = 88; out.data[p + 1] = 181; out.data[p + 2] = 122; implOnly += 1; }
    }
    diffCtx.putImageData(out, 0, 0);

    document.body.innerHTML = '';
    document.body.style.margin = '0';
    side.id = 'fourup-side';
    diff.id = 'fourup-diff';
    refCtx.canvas.id = 'fourup-ref';
    document.body.append(side, diff, refCtx.canvas);
    return { both, refOnly, implOnly };
  }, {
    refSrc: asDataUrl(o.referencePng),
    implSrc: asDataUrl(implementationPath),
    refCap: o.referenceCaption,
    implCap: o.implementationCaption,
  });

  await o.page.locator('#fourup-ref').screenshot({ path: resolve(o.outDir, `${o.slug}--reference.png`) });
  await o.page.locator('#fourup-side').screenshot({ path: resolve(o.outDir, `${o.slug}--side-by-side.png`) });
  await o.page.locator('#fourup-diff').screenshot({ path: resolve(o.outDir, `${o.slug}--diff.png`) });
  return result;
}
```

- [ ] **Step 2: 写「按快门前等真像素」**

同一个文件，接在后面。

**这段代码仓库里现在没有 —— 它被删过一次，删得对。** 三次提交的完整来龙去脉：`a000f794` 建了 `tests/helpers/canvasPainted.ts` → `77626007` 因为只有一个调用点、把它内联回去并删掉 helper → `600b31f0` 连内联的那段也删了，commit 标题写着「**演示的结果是「它在那屏装不上」**」：给那屏 6 个图片资产的 route handler 各塞 12 秒延迟、六个 handler 全部命中，spec 仍然 **5.2 秒通过**——因为那屏用的是 `components/Board.tsx`，它**在图到齐之前就先画了底和格线**，压根没有全黑那一帧。**挂一段结构上不可能生效的闸，比不挂更坏**：下一个人会把它读成「这屏有保护」。

**但竞态在别处是真的**：`components/live/LiveBoard.tsx:339-358` 先 `Promise.all` 预加载 5 张 PNG，全部 `onload` 才 `setImagesLoaded(true)`，绘制 effect 挂在这个标志上——图没到齐之前**一笔都不画**。实测 `/kiosk/play` 连开 6 次：元素出现那一刻 **4 次空、2 次已画**；1200ms 后 6 次全部已画。

⇒ **本轮重新加回来，但只在真会全黑的地方用**：全仓今天渲染 `LiveBoard` 的路由**只有 `/kiosk/play`**，而它正是屏 01 的路由（Task 10）。其余各屏若不含 `LiveBoard`，**不要挂这段**。

```ts
/**
 * `waitForSelector` / `toBeVisible()` 只证明**元素在**,证明不了**画完了**。
 * 判据是**非黑采样点**:在元素中心取 9 个点,全黑就是还没画。
 *
 * ⚠️ 这条判据的**边界**:它分的是「一笔没画」和「画了」,分不出「画了一半」。
 * 用在 LiveBoard 那种**整段绘制被 imagesLoaded 挡住**的失败上是够的;
 * 别拿它当通用的「画对了」。Board.tsx 那种「先画底和格线、图到齐再覆盖」的
 * 组件上它**永远不会红** —— 上一轮给 6 个资产各塞 12 秒延迟实测过,spec 仍 5.2 秒通过。
 */
export async function waitForRealPixels(page: Page, selector: string) {
  await page.waitForSelector(selector);
  await page.waitForFunction((sel) => {
    const el = document.querySelector(sel);
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return false;
    const canvas = document.createElement('canvas');
    canvas.width = 3; canvas.height = 3;
    // canvas 元素直接采样;非 canvas 的(内联 SVG)只要有子节点即可 —— 它们不走图片预加载。
    if (!(el instanceof HTMLCanvasElement)) return el.childElementCount > 0;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(el, 0, 0, 3, 3);
    const d = ctx.getImageData(0, 0, 3, 3).data;
    for (let i = 0; i < 9; i += 1) {
      if (d[i * 4] > 12 || d[i * 4 + 1] > 12 || d[i * 4 + 2] > 12) return true;
    }
    return false;
  }, selector, { timeout: 10_000 });
}
```

- [ ] **Step 2b: 把时钟冻在 16:40，一举两得**

同一个文件再加一个导出。实测发现（survey，2026-08-20）：顶栏渲染的是**真时钟**，所以**每一次重跑都会把已提交的 PNG 弄脏，哪怕代码一个字没改**。而参考图上恒为 `16:40`。

```ts
/**
 * 把页面时间冻在参考图那一刻(16:40)。两件事一起解决:
 *   ① 四图产物变成**字节稳定**的 —— 否则每次重跑都 dirty 一批 PNG,
 *      「重跑零字节变化」这条本来能用的信号就没了;
 *   ② 顶栏时钟和参考图对得上,差异图里少一处注定的红。
 * 必须在 page.goto 之前调 —— addInitScript 只对之后加载的文档生效。
 */
export async function freezeClock(page: Page, iso = '2026-08-20T16:40:00') {
  await page.addInitScript((frozen) => {
    const fixed = new Date(frozen).getTime();
    const RealDate = Date;
    // 只钉「现在」:带参数的 new Date(x) 仍按原样走,否则日期格式化会一起坏掉。
    class FrozenDate extends RealDate {
      constructor(...args: unknown[]) {
        if (args.length === 0) super(fixed);
        else super(...(args as ConstructorParameters<typeof RealDate>));
      }
      static now() { return fixed; }
    }
    (globalThis as { Date: DateConstructor }).Date = FrozenDate as unknown as DateConstructor;
  }, iso);
}
```

- [ ] **Step 3: 自测一次 —— 拿 `/kiosk/play` 当被测物**

临时 spec `tests/tmp-fourup-selftest.spec.ts`：

```ts
import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, KIOSK_VIEWPORT } from './helpers/fourup';

test('helper 自测:能产出四张图', async ({ page }) => {
  await page.setViewportSize(KIOSK_VIEWPORT);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup-selftest');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: { id: 1, username: 'tester', rank: '5段', credits: 0 } }));
  await page.goto('/kiosk/play');
  await page.waitForSelector('.kiosk-screen');
  const r = await captureFourUp({
    page,
    referencePng: resolve(process.cwd(), '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots/01-play.png'),
    outDir: resolve(process.cwd(), '../../../superpowers/tracks/kiosk-go-shell-align/visual/_selftest/1024x600'),
    slug: '01-play',
    referenceCaption: '参考:sample-go/shots/01-play.png（像素与旁注不作数）',
    implementationCaption: '实现:helper 自测,内容尚未搬运',
  });
  console.log(`[fourup-selftest] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
```

- [ ] **Step 4: 跑它，确认四张图真的落盘**

```bash
cd katrain/web/ui && npx playwright test tests/tmp-fourup-selftest.spec.ts --reporter=list
ls -la ../../../superpowers/tracks/kiosk-go-shell-align/visual/_selftest/1024x600/
```

Expected: 四个文件 `01-play--{reference,implementation,side-by-side,diff}.png`，且 `both > 0`（两边都有边 = 参考图确实读进来了）。

若 `both === 0` **且** `refOnly === 0` → 参考图路径错了（读成了空图），不是「实现全对」。**这是「0 是不是最优解」那条通则的一个实例：`refOnly` 小看着像好事，`refOnly === 0` 却是参考图没加载。**

- [ ] **Step 5: 删掉临时 spec 与自测产物**

```bash
rm katrain/web/ui/tests/tmp-fourup-selftest.spec.ts
rm -rf superpowers/tracks/kiosk-go-shell-align/visual/_selftest
```

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/tests/helpers/fourup.ts
git commit -m "test(kiosk-shell): 抽出四图闸 helper(9 个消费者)与等真像素的判据

合成代码逐字节取自 kiosk-layout-a-vs-xiangqi-setup.spec.ts。差异图用边缘图不用
像素比 —— 稿子里 26 处旁注不上线,像素比会把它们整块报成回归。
等真像素那条写明了边界:分得出「一笔没画」,分不出「画了一半」。"
```

---

## Task 3: 顶栏

**Files:**
- Create: `katrain/web/ui/src/kiosk/shell/KioskTopbar.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/identityPresentation.ts`
- Create: `katrain/web/ui/src/kiosk/shell/identityPresentation.test.ts`
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`
- Delete: `katrain/web/ui/src/kiosk/components/layout/Header.tsx`
- Test: `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts`（加一组顶栏断言）

**Interfaces:**
- Consumes: Task 1 的 `KioskFrame`（`topbar` 插槽）
- Produces: `<KioskTopbar identity={{username?: string}} onHome?={() => void} homeBusy?={boolean} />`
- Produces: `identityPresentation(identity): { avatar: string; label: string }`

**规范 §6 逐像素**（`tokens.css:269-370` 全部给好了，React 侧只负责结构与内容）：

```
左簇 x=24 起:  logo 32×32 → 10px → 智星盒 20px 龙藏 → 6px → StellaBox 12px Serif 斜体 --dim
              → 12px → 竖线 1×20 --hair → 12px → 围棋 16px Serif 600 --accent .12em
右簇 贴 x=1000: [主页 88×48(仅 L1)] 头像 26 圆 accent 实底 + --ink 首字 → 8px → 名字 13px Sans
              → 14px → 时钟 14px Mono tabular-nums
```

- [ ] **Step 1: 写失败的单测——身份呈现**

`katrain/web/ui/src/kiosk/shell/identityPresentation.test.ts`：

```ts
import { describe, expect, test } from 'vitest';
import { identityPresentation } from './identityPresentation';

describe('identityPresentation', () => {
  test('没登录显示「访客」,头像首字是「访」', () => {
    expect(identityPresentation({})).toEqual({ avatar: '访', label: '访客' });
  });

  test('登录了取用户名首字', () => {
    expect(identityPresentation({ username: '张三' })).toEqual({ avatar: '张', label: '张三' });
  });

  test('拉丁名首字母大写 —— 头像格是 12px,小写字母在圆里偏下', () => {
    expect(identityPresentation({ username: 'frank' })).toEqual({ avatar: 'F', label: 'frank' });
  });

  test('空串按没登录处理 —— 空头像圈比「访」更没信息', () => {
    expect(identityPresentation({ username: '' })).toEqual({ avatar: '访', label: '访客' });
  });
});
```

- [ ] **Step 2: 跑它，确认红**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/identityPresentation.test.ts
```

Expected: FAIL — 模块不存在

- [ ] **Step 3: 写实现**

```ts
// katrain/web/ui/src/kiosk/shell/identityPresentation.ts
export interface ShellIdentity {
  username?: string;
}

/**
 * 顶栏右簇的身份呈现。规范 §6:头像是**强调色实底 + 深色首字**(访客显示「访」),
 * 不是空心描边圈。
 *
 * 首字母大写只对拉丁生效 —— 中文 toUpperCase() 是恒等,写一次两边都对。
 */
export function identityPresentation(identity: ShellIdentity): { avatar: string; label: string } {
  const name = identity.username?.trim();
  if (!name) return { avatar: '访', label: '访客' };
  return { avatar: [...name][0].toUpperCase(), label: name };
}
```

- [ ] **Step 4: 跑它，确认绿**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/identityPresentation.test.ts
```

Expected: PASS，4 条全绿

- [ ] **Step 5: 写 `KioskTopbar`**

```tsx
// katrain/web/ui/src/kiosk/shell/KioskTopbar.tsx
import { useEffect, useState } from 'react';
import { identityPresentation, type ShellIdentity } from './identityPresentation';

function clockText(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

/**
 * 先对齐到**下一个整分**,之后才每 60 秒一跳(gomoku hooks/useClock.ts:12-37 的做法)。
 * 挂载即 setInterval(60_000) 会漂:最坏要等 59 秒才翻第一次,屏上的分钟数一直是慢的。
 * 国象那份 1 秒一跳也能对,但为同一个 HH:MM 多渲染 60 倍。
 */
function useMinuteClock(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let interval: number | undefined;
    const timeout = window.setTimeout(() => {
      setNow(new Date());
      interval = window.setInterval(() => setNow(new Date()), 60_000);
    }, 60_000 - (Date.now() % 60_000));
    return () => {
      window.clearTimeout(timeout);
      if (interval !== undefined) window.clearInterval(interval);
    };
  }, []);
  return now;
}

/**
 * §6 上边条。**任何层级、任何模块都不变高、不隐藏**(防跳铁律 1),
 * 右簇内容与位置在所有页面完全恒定(防跳铁律 2)。
 *
 * 「智星盒」三个字走**龙藏行楷**,只此一处(规范 §2/§9)。字族与
 * `font-synthesis:none` 都由 tokens.css 的 `.kiosk-topbar__brand-zh` 给,
 * 这里**不要**再写 sx/style 覆盖 —— 上一轮那个 bug 正是 React 侧覆盖掉了字族。
 *
 * 返回、2D/3D、页面标题一律**不在这里**,下放到 §11 的页控条。
 */
export function KioskTopbar({ identity, onHome, homeBusy = false }: {
  identity: ShellIdentity;
  onHome?: () => void;
  homeBusy?: boolean;
}) {
  const clock = clockText(useMinuteClock());
  const presented = identityPresentation(identity);

  return (
    <header className="kiosk-topbar">
      {/* 规范 §10 钉死的那一份 logo。围棋是青毡深底,不加象棋那条 invert 滤镜。 */}
      <img className="kiosk-topbar__logo" src="/assets/img/logo-white.png" alt="" />
      <span className="kiosk-topbar__brand">
        <span className="kiosk-topbar__brand-zh" data-testid="kiosk-brand-zh">智星盒</span>
        <span className="kiosk-topbar__brand-en">StellaBox</span>
      </span>
      <span className="kiosk-topbar__rule" aria-hidden="true" />
      <span className="kiosk-topbar__game">围棋</span>
      <div className="kiosk-topbar__right">
        {onHome && (
          <button
            type="button"
            className="kiosk-topbar__home"
            aria-label="返回智星盒主页"
            data-testid="kiosk-home-action"
            disabled={homeBusy}
            onClick={onHome}
          >
            <span className="kiosk-topbar__home-icon" aria-hidden="true" />
            <span>主页</span>
          </button>
        )}
        <span className="kiosk-topbar__avatar" aria-hidden="true">{presented.avatar}</span>
        <span className="kiosk-topbar__user" data-testid="header-username">{presented.label}</span>
        {/* dateTime 和正文复用同一份格式化结果 —— 各写一套会独立漂移。 */}
        <time className="kiosk-topbar__clock" data-testid="clock" dateTime={clock}>{clock}</time>
      </div>
    </header>
  );
}
```

- [ ] **Step 6: 接进 `KioskLayout`，删掉 `Header.tsx`**

`KioskLayout.tsx` 的 `topbar` 插槽换成 `<KioskTopbar identity={{ username }} onHome={isL1 ? onHome : undefined} />`，删掉 `import Header`，`git rm` 掉 `Header.tsx`。

✅ **已按 D9 裁定**：`engine-status` 点、`VisionIndicators`、`GeometryIndicator`、设置齿轮**四样全拆**，不进 `KioskTopbar`。摄像头 / 标定这两条信息的去处是 **L1 左栏 `.kiosk-status` 三格**，而 `SmartBoardConsole.tsx:171-188` 早就有这三格了 —— 拆掉不丢信息。L3 已有 `VisionSyncOverlay` + `PhysicalPlayStatusChip` + `RecalibrationModal`（`GamePage.tsx:14,18`），不会盲。

⚠️ **删之前先 grep**：确认 `VisionIndicators` / `GeometryIndicator` 除 `Header.tsx` 外没有第二个使用者；有的话只删顶栏这一处引用。

⚠️ 同时要删掉 `src/kiosk/__tests__/Header.test.tsx`（它 `:65-68` 断言 `toHaveStyle({height:'56px'})`，被测组件没了）。**不要只是删**：把「顶栏恒 56 高」这条断言搬进 Task 1 那条真浏览器几何闸里——jsdom 对布局无权作证，那条 jsdom 断言本来就该被替换掉（**替换不是叠加**）。

- [ ] **Step 7: 给几何闸加顶栏一组**

在 `tests/kiosk-shell-geometry.spec.ts` 追加：

```ts
test('§6 顶栏:左簇顺序与间距、右簇贴右缘、品牌字是龙藏', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const screen = await box(page, '.kiosk-screen');
  const logo = await box(page, '.kiosk-topbar__logo');
  const zh = await box(page, '.kiosk-topbar__brand-zh');
  const en = await box(page, '.kiosk-topbar__brand-en');
  const rule = await box(page, '.kiosk-topbar__rule');
  const game = await box(page, '.kiosk-topbar__game');
  const clock = await box(page, '.kiosk-topbar__clock');
  const avatar = await box(page, '.kiosk-topbar__avatar');

  expect(logo.x - screen.x).toBe(24);          // --topbar-pad-x
  expect(logo.w).toBe(32);
  expect(logo.h).toBe(32);
  expect(Math.round(zh.x - (logo.x + logo.w))).toBe(10);
  expect(Math.round(en.x - (zh.x + zh.w))).toBe(6);
  expect(rule.w).toBe(1);
  expect(rule.h).toBe(20);
  expect(avatar.w).toBe(26);
  expect(avatar.h).toBe(26);
  // 左簇顺序不可调,右簇贴右缘
  expect(logo.x).toBeLessThan(zh.x);
  expect(zh.x).toBeLessThan(en.x);
  expect(en.x).toBeLessThan(rule.x);
  expect(rule.x).toBeLessThan(game.x);
  expect(Math.round(screen.x + screen.w - (clock.x + clock.w))).toBe(24);
});

test('§2 品牌字「智星盒」跑的是龙藏行楷,而且三个字都是', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const client = await page.context().newCDPSession(page);
  await client.send('DOM.enable');
  await client.send('CSS.enable');
  const { root } = await client.send('DOM.getDocument');
  const { nodeId } = await client.send('DOM.querySelector', {
    nodeId: root.nodeId, selector: '[data-testid="kiosk-brand-zh"]',
  });
  const { fonts } = await client.send('CSS.getPlatformFontsForNode', { nodeId });
  // 上界不是判据:「一个字都没盖」会让 <=3 满分。下界才是真正要的那件事。
  expect(fonts[0].familyName).toContain('Long Cang');
  expect(fonts[0].glyphCount).toBe(3);
});
```

> §17.1 那条通则：**任何「不许超过 N」的断言，都要问一句「0 是不是最优解」。** 是的话它就没有下界，而下界通常才是你真正要的那件事。这里的下界钉在「首位是龙藏 **且** 覆盖 3 个字」上——只钉首位的话，掉出去两个字它还是首位。

- [ ] **Step 8: 跑几何闸**

```bash
cd katrain/web/ui && npx playwright test tests/kiosk-shell-geometry.spec.ts --reporter=list
```

Expected: 全绿。

- [ ] **Step 9: 演示品牌字那条闸有牙**

把 `KioskTopbar.tsx` 的 `className="kiosk-topbar__brand-zh"` 临时改成 `className="kiosk-topbar__brand"`（丢掉龙藏那条规则），重跑。

Expected: **红**，报 `LXGW WenKai` 而不是 `Long Cang`。

⚠️ 变异要**真的到达产物**：只改 className 会留下未使用的东西时 `tsc -b` 会报 TS6133、vite 不跑、产物名不变，那时跑测试会得到「全绿」并被读成「闸没牙」——**和真的没牙逐字相同**。跑之前先确认 `npx tsc -b` 是绿的、`dist/assets/KioskApp-*.js` 的哈希变了。

改回来，重跑，绿。

- [ ] **Step 10: 双构建 + 提交**

```bash
cd katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d
cd ../../.. && git add -A katrain/web/ui/src/kiosk/shell katrain/web/ui/src/kiosk/components/layout katrain/web/ui/tests
git commit -m "feat(kiosk-shell): 顶栏改用共享外壳的 .kiosk-topbar

补上此前没有的｜围棋、26px 头像;齿轮按规范 §1 拆掉(Dock 里已有设置)。
品牌字闸补了下界(首位是龙藏 且 覆盖 3 字),并变异演示过。
围棋专属的摄像头/标定/引擎点/齿轮四样按 D9 全拆:三家顶栏都零指示器,
那三格信息在 L1 左栏 SmartBoardConsole 里已有,L3 走 VisionSyncOverlay。"
```

---

## Task 4: Dock 与路由重映射

✅ **Q2 已裁定 —— 见 D8：6 项。** 五子棋自己就是 6 项，「四家 Dock 项数相等」不是规矩。照下面写，不要再回头讨论。

**Files:**
- Create: `katrain/web/ui/src/kiosk/shell/KioskDock.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/dockRoutes.ts`
- Create: `katrain/web/ui/src/kiosk/shell/dockRoutes.test.ts`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx:78-99`（路由重排）
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/Dock.test.tsx`
- Delete: `katrain/web/ui/src/kiosk/components/layout/Dock.tsx`、`navTabs.tsx`
- Test: `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts`

**Interfaces:**
- Consumes: Task 3 的 `KioskFrame`（`dock` 插槽）、Task 6 的 `<Icon name/>`（本 Task 与 Task 6 有依赖，**先做 Task 6 再做本 Task**，或本 Task 临时用内联 SVG 再由 Task 6 换掉——**不要**用 `@mui/icons-material`，规范 §10 要求四棋类同一份 Phosphor 字节）
- Produces: `<KioskDock activePath={string} onTab={(path: string) => void} />`
- Produces: `dockLevelOf(pathname: string): 1 | 2`、`dockActiveOf(pathname: string): string | null`

**现状**（`navTabs.tsx:20-32`，8 项）→ **目标**（规范 §3 词典）：

| 现在 | 图标 | 去处 | 规范依据 |
|---|---|---|---|
| 对弈 `/kiosk/play` | `SportsEsports` | **对弈**，图标换 `game-controller` | §3 核心六项 |
| 死活 `/kiosk/tsumego` | `Extension` | **训练营**，图标 `puzzle-piece` | §3「死活 → 训练营，词典里本来就有这一格」 |
| 研究 `/kiosk/research` | `Science` | **下 Dock**，并进复盘 | §3「研究盘本来就能读用户自己的对局，它和复盘是同一件事的两个入口」 |
| 棋谱 `/kiosk/kifu` | `LibraryBooks` | **棋谱**（留作那一个专属项），图标 `books` | §3 专属项，**位置钉在训练营之后** |
| 摆谱 `/kiosk/baipu` | `GridOn` | **下 Dock**，降为「选中一份棋谱之后的落子方式」 | §3 + §4 同源 |
| 直播 `/kiosk/live` | `LiveTv` | **下 Dock**，并进棋谱 | §3「正在下的谱和下完的谱是同一件事的两个时态」 |
| 教程 `/kiosk/tutorial` | `MenuBook` | **课程**，图标 `book-open` | §3 |
| 复盘 `/kiosk/report` | `Assessment` | **复盘**，图标 `grid-nine` | §3 |
| （无） | — | **设置** `/kiosk/settings`，图标 `gear` | §1「Dock 里已经有设置」，顶栏齿轮拆掉 |

✅ **Task 3 欠下的那笔账已在本 Task 销(2026-08-20)。** D9 拆掉顶栏齿轮那一刻，「设置」在壳上一个入口都没有了，`src/kiosk/__tests__/navigation.integration.test.tsx` 里那条用例因此被 `it.skip` 挂起。本 Task 把 `设置` 加进 Dock 之后已经解开：选择器改成**点 Dock 上的设置项**，用例改名为 `opens Settings from the Dock and its back action lands on the safe fallback`。⚠️ 没有改成 `renderApp('/kiosk/settings')` 直接跳 —— 那是「到达性测试给断路发通行证」。返回落到 `/kiosk/play`(Dock 不带 `location.state.from`，`SettingsPage.tsx:73` 走安全兜底)；旧齿轮那条路会带上原路由，**Dock 要不要带留给 Task 18 重做设置屏时定**。

⚠️ **下 Dock ≠ 删路由。** `research` / `baipu` / `live` 三条路由**照旧存在**（D2 只接壳），只是不再是 Dock 项。它们的入口在 Task 15（棋谱屏出 `摆谱` / `直播`）和 Task 16（复盘屏出 `研究`）里补上。**Task 4 做完到 Task 15/16 做完之间，这三屏只能靠直接输 URL 到达**——这是可接受的中间态，但**每个 Task 的验收里要点名它还没接**，不要让它悄悄变成永久状态。

- [ ] **Step 1: 写失败的单测——Dock 词典与层级**

`katrain/web/ui/src/kiosk/shell/dockRoutes.test.ts`：

```ts
import { describe, expect, test } from 'vitest';
import { DOCK_TABS, dockActiveOf, dockLevelOf } from './dockRoutes';

describe('DOCK_TABS —— 词与顺序是四棋类共享词典,不是围棋能自选的', () => {
  test('顺序写死:对弈 训练营 棋谱 复盘 课程 设置', () => {
    expect(DOCK_TABS.map((t) => t.label)).toEqual(
      ['对弈', '训练营', '棋谱', '复盘', '课程', '设置'],
    );
  });

  test('专属项「棋谱」钉在「训练营」之后 —— 位置也是规范定死的', () => {
    const labels = DOCK_TABS.map((t) => t.label);
    expect(labels.indexOf('棋谱')).toBe(labels.indexOf('训练营') + 1);
  });

  test('不超过 7 项(--dock-max-items)', () => {
    expect(DOCK_TABS.length).toBeLessThanOrEqual(7);
  });

  test('图标全部来自 Phosphor 词典(§10),不是随手挑的近似图标', () => {
    expect(DOCK_TABS.map((t) => t.icon)).toEqual(
      ['game-controller', 'puzzle-piece', 'books', 'grid-nine', 'book-open', 'gear'],
    );
  });
});

describe('dockLevelOf —— 层级跟着**屏**走,不跟着路由前缀走', () => {
  test('六个 L1 目标是 1 级', () => {
    for (const t of DOCK_TABS) expect(dockLevelOf(t.path)).toBe(1);
  });

  test('对局屏是 3 级 —— 它挂在 play 底下,但不是一级页', () => {
    expect(dockLevelOf('/kiosk/play/ai/game/abc')).toBe(2);   // 2 = 无 Dock 的那一档
  });

  test('单元列表是训练营的二级页', () => {
    expect(dockLevelOf('/kiosk/tsumego/15k/capturing')).toBe(2);
  });

  test('尾斜杠不改变层级', () => {
    expect(dockLevelOf('/kiosk/play/')).toBe(1);
  });
});

describe('dockActiveOf —— 二/三级页高亮它的父项', () => {
  test('做题屏高亮训练营', () => {
    expect(dockActiveOf('/kiosk/tsumego/problem/42')).toBe('/kiosk/tsumego');
  });
  test('对局屏高亮对弈', () => {
    expect(dockActiveOf('/kiosk/play/ai/game/abc')).toBe('/kiosk/play');
  });
  test('下了 Dock 的三条路由没有父项 —— 一个都不许乱高亮', () => {
    expect(dockActiveOf('/kiosk/baipu')).toBe(null);
    expect(dockActiveOf('/kiosk/live')).toBe(null);
    expect(dockActiveOf('/kiosk/research')).toBe(null);
  });
  test('最长前缀优先:report/:taskId 高亮复盘,不是别的', () => {
    expect(dockActiveOf('/kiosk/report/7')).toBe('/kiosk/report');
  });
});
```

- [ ] **Step 2: 跑它，确认红**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/dockRoutes.test.ts
```

Expected: FAIL — 模块不存在

- [ ] **Step 3: 写实现**

```ts
// katrain/web/ui/src/kiosk/shell/dockRoutes.ts
import type { IconName } from './icons';

/**
 * §3 底部 Dock。**词与顺序来自四棋类共享词典,不是围棋能自选的**:
 *   对弈 · 训练营 · 复盘 · 成长 · 课程 · 设置
 * 棋种专属项最多再加 1 个,**插在「训练营」之后**;围棋用掉的那一个是「棋谱」。
 *
 * 「成长」本轮不在这里:围棋没有 growth 路由/页面/后端(scope.md 决策一,Fan 2026-08-20)。
 * 摆假入口比缺一格更坏 —— 见 G8。这条差异登记在 D6,四图的标签带里要写出来。
 */
export interface DockTab { path: string; label: string; icon: IconName }

export const DOCK_TABS: readonly DockTab[] = [
  { path: '/kiosk/play',     label: '对弈',   icon: 'game-controller' },
  { path: '/kiosk/tsumego',  label: '训练营', icon: 'puzzle-piece' },
  { path: '/kiosk/kifu',     label: '棋谱',   icon: 'books' },
  { path: '/kiosk/report',   label: '复盘',   icon: 'grid-nine' },
  { path: '/kiosk/tutorial', label: '课程',   icon: 'book-open' },
  { path: '/kiosk/settings', label: '设置',   icon: 'gear' },
];

const norm = (p: string) => (p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p);

/**
 * 高亮哪一项。二/三级页高亮它的**父项**(做题屏 → 训练营,对局屏 → 对弈)。
 * 下了 Dock 的三条(baipu/live/research)**返回 null** —— 它们没有父项,
 * 乱认一个父项等于告诉用户「你在棋谱里」,而 Dock 上那一格并没有把他带到这儿来。
 */
export function dockActiveOf(pathname: string): string | null {
  const p = norm(pathname);
  // 最长前缀优先:/kiosk/play 和 /kiosk/play/... 都要落到 play,而 /kiosk/playground 不许。
  const hit = [...DOCK_TABS]
    .sort((a, b) => b.path.length - a.path.length)
    .find((t) => p === t.path || p.startsWith(`${t.path}/`));
  return hit ? hit.path : null;
}

/**
 * 1 = 一级页(有 Dock,中间区 434 高);2 = 二/三级页(无 Dock,516 高)。
 * **层级跟着屏走,不跟着路由前缀走** —— 国象踩过:复盘分析屏挂在 review 这条 L1 路由下
 * 但其实是 L2,判错就从 516 的盘上裁掉 82px。
 */
export function dockLevelOf(pathname: string): 1 | 2 {
  const p = norm(pathname);
  return DOCK_TABS.some((t) => t.path === p) ? 1 : 2;
}
```

- [ ] **Step 4: 跑它，确认绿**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/dockRoutes.test.ts
```

Expected: PASS，12 条全绿

- [ ] **Step 5: 写 `KioskDock`**

```tsx
// katrain/web/ui/src/kiosk/shell/KioskDock.tsx
import { Icon } from './icons';
import { DOCK_TABS, dockActiveOf } from './dockRoutes';

/**
 * §7 Dock:通栏贴底、高 82、≤7 项等宽、图标 24、标签 12.5px Sans 600、
 * 选中 = 强调色实底 + translateY(-2px)。全部由 tokens.css:377-412 给,
 * 这里只负责结构、词、图标和高亮。
 *
 * 用 <button> 不用 <a>:稿子就是 button,tokens.css 因此从没写 text-decoration。
 */
export function KioskDock({ pathname, onTab }: {
  pathname: string;
  onTab: (path: string) => void;
}) {
  const active = dockActiveOf(pathname);
  return (
    <nav className="kiosk-dock" aria-label="主导航">
      {DOCK_TABS.map((tab) => {
        const on = active === tab.path;
        return (
          <button
            key={tab.path}
            type="button"
            className="kiosk-dock__item"
            aria-current={on ? 'page' : undefined}
            onClick={() => onTab(tab.path)}
          >
            <Icon name={tab.icon} filled={on} />
            <span className="kiosk-dock__label">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 6: 路由重排**

`katrain/web/ui/src/kiosk/KioskApp.tsx`：

1. `settings` 路由不动（`:99`），它现在是 Dock 的目标。
2. **`GamePage` 那四条（`:58-61`）挪进 `KioskLayout`**。现在它们在 `KioskAuthGuard` 下、`KioskLayout` 外，所以对局屏**连顶栏都没有**——而规范 §5 防跳铁律 1 写死「顶栏永远占 y 0–56，**任何层级、任何模块都不变高、不隐藏**」。挪进去之后 `dockLevelOf` 会判成 2 级、不出 Dock，正确。
   ⚠️ 挪的时候保留 `PhysicalBoardGuard requireRecognition` 包裹，不要顺手改掉。
3. `immersive` 语义：`ImmersiveContext` 现在会把顶栏和 Dock 一起抽掉。规范不允许抽顶栏。**本 Task 只把 Dock 归 `dockLevelOf` 管，`immersive` 对顶栏的作用先原样留着**，并在提交信息里登记「immersive 抽顶栏与规范 §5 防跳铁律 1 冲突，待定」。**不要顺手删** —— 它有别的消费者，删它超出本 Task。

`KioskLayout.tsx` 改成：

```tsx
  const location = useLocation();
  const level = dockLevelOf(location.pathname);
  return (
    <KioskFrame
      level={level}
      topbar={<KioskTopbar identity={{ username }} onHome={level === 1 ? onHome : undefined} />}
      dock={level === 1 ? <KioskDock pathname={location.pathname} onTab={(p) => navigate(p)} /> : undefined}
    >
      …
    </KioskFrame>
  );
```

- [ ] **Step 7: 改既有的 Dock 单测**

`src/kiosk/__tests__/Dock.test.tsx:22-28` 现在断言 8 项、并断言「设置**不**在 Dock 里」。两条都反了。改成断言新词典，并把「设置在 Dock 里」写成正向断言，注释写清依据是规范 §1（顶栏齿轮拆掉，因为 Dock 里已经有设置）。

- [ ] **Step 8: 给几何闸加 Dock 一组**

```ts
test('§7 Dock:项数、等宽、项高 65、选中态位移 -2px', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const dock = await box(page, '.kiosk-dock');
  const items = await page.locator('.kiosk-dock__item').all();
  expect(items.length).toBe(6);           // D8:六项。五子棋也是 6 项,项数相等不是规矩

  const boxes = await Promise.all(items.map((i) => i.evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { x: r.x, w: r.width, h: r.height, y: r.y };
  })));
  // 等宽:最宽和最窄差不到 1px(亚像素)
  expect(Math.max(...boxes.map((b) => b.w)) - Math.min(...boxes.map((b) => b.w))).toBeLessThan(1);
  // 项高 65 = 82 − 1(顶部描边) − 2×8(内边距)。关系式写出来,不写字面量。
  expect(Math.round(boxes[0].h)).toBe(dock.h - 1 - 2 * 8);
  // 选中项上移 2 —— 它是**唯一**上移的那一个
  const raised = boxes.filter((b) => b.y < Math.max(...boxes.map((x) => x.y)) - 1);
  expect(raised.length).toBe(1);
});
```

- [ ] **Step 9: 跑全部闸 + 双构建**

```bash
cd katrain/web/ui
npx vitest run src/kiosk
npx playwright test tests/kiosk-shell-geometry.spec.ts --config playwright.visual.config.ts --workers=1
npx tsc -b && npm run build && npm run build:kiosk-2d
```

Expected: vitest 与基线相比**没有新增**失败（`comm -13` 比名字集合）；playwright 全绿；三条构建绿。

- [ ] **Step 10: 提交**

```bash
git add -A katrain/web/ui/src/kiosk katrain/web/ui/tests
git commit -m "feat(kiosk-shell): Dock 收成共享词典的六项,路由跟着重排

死活->训练营、教程->课程、研究/摆谱/直播 下 Dock(路由保留,入口在棋谱与复盘屏补),
设置进 Dock、顶栏齿轮拆掉。对局屏四条路由挪进 KioskLayout —— 规范 §5 防跳铁律 1
要求顶栏任何层级都不隐藏,而它们此前连顶栏都没有。
成长本轮不进 Dock(scope.md 决策一),差异已登记。"
```

---

## Task 5: L1 两栏与镜像栏

**Files:**
- Create: `katrain/web/ui/src/kiosk/shell/KioskConsoleRail.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/KioskStatusCells.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/KioskStatusCells.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`
- Delete: `katrain/web/ui/src/kiosk/components/layout/SmartBoardConsole.tsx`
- Test: `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts`

**Interfaces:**
- Consumes: Task 9 的 `<GoBoardSvg/>`（**先做 Task 9 的盘那一半**，或本 Task 先放一个空 `<div className="kiosk-mini-board"/>` 占位、Task 9 填进去）
- Produces: `<KioskConsoleRail title sub board syncLeft syncRight statuses />`
- Produces: `<KioskStatusCells cells={StatusCell[]} />`，`StatusCell = { label: string; value: string; tone?: 'good'|'warn'|'bad' }`

**规范 §5 的纵向账，一分不多一分不少**：

```
20（标题）+ 10 + 272（镜像框）+ 10 + 32（同步行）+ 10 + 56（状态格）= 410 = 434 − 2×1（描边）− 2×11（内边距）
```

> 这串等号**曾经算错过 2px**（横向算了 1px 描边、纵向漏了，写成 434 − 2×11 = 412，标题按 22 排）。多出来的 2px 没有报错——标题行和状态格都没写 `flex:none`，被 flex 各压了 1px，**肉眼看不出来**。现在栏里每块都写死 `flex:none`（`tokens.css:440` 起），再有人算错会顶破外框、当场看得见。

> 镜像框**不许 `flex:1` 吃剩余空间**：早先那样写出来是框 272×**312**、盘 248 居中——上下各空 32、左右只有 12，一条不对称的空带。剩余空间要给同步行。

**现状差距**（`SmartBoardConsole.tsx:96-98`）：宽 322 + 左右各 20 外边距 = **362 占位**，右边 `<main>` 只剩 662。目标是 296 + 16 + 680。

- [ ] **Step 1: 写失败的单测——状态三格跟着真实硬件走**

`katrain/web/ui/src/kiosk/shell/KioskStatusCells.test.tsx`：

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { GO_HARDWARE_CELLS, KioskStatusCells } from './KioskStatusCells';

describe('围棋的硬件三格', () => {
  // 规范 §5:统一的是**格数、几何和灯色语义,不是器件名**。
  // 国象/象棋盘上根本没有摄像头,五子棋盘上没有 LED —— 说明书上没有的东西,界面上不能有。
  test('围棋是 摄像头 · 标定 · LED —— 摄像头识子,盘上另有一层 LED 指下一手', () => {
    expect(GO_HARDWARE_CELLS.map((c) => c.label)).toEqual(['摄像头', '标定', 'LED']);
  });

  test('渲染出三格,每格上行是名称+灯、下行是状态值', () => {
    render(<KioskStatusCells cells={[
      { label: '摄像头', value: '已连接', tone: 'good' },
      { label: '标定', value: '需重标', tone: 'warn' },
      { label: 'LED', value: '就绪', tone: 'good' },
    ]} />);
    expect(document.querySelectorAll('.kiosk-status__cell')).toHaveLength(3);
    expect(screen.getByText('需重标')).toBeInTheDocument();
  });

  test('两格变体只给成长用 —— 三格是硬件状态的形状,不许拿来装两个数', () => {
    const { container } = render(<KioskStatusCells cells={[
      { label: '本月', value: '—' }, { label: '最高', value: '—' },
    ]} />);
    expect(container.querySelector('.kiosk-status--2')).not.toBeNull();
  });

  test('没有 tone 就不画灯 —— 灯是状态,不是装饰', () => {
    const { container } = render(<KioskStatusCells cells={[
      { label: '准确率', value: '78%' }, { label: '失误', value: '4 手' }, { label: '漏着', value: '1 手' },
    ]} />);
    expect(container.querySelectorAll('.kiosk-status__k i')).toHaveLength(0);
  });
});
```

- [ ] **Step 2: 跑它，确认红**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/KioskStatusCells.test.tsx
```

Expected: FAIL — 模块不存在

- [ ] **Step 3: 写实现**

```tsx
// katrain/web/ui/src/kiosk/shell/KioskStatusCells.tsx
export interface StatusCell { label: string; value: string; tone?: 'good' | 'warn' | 'bad' }

/**
 * §5 状态格。几何写死(三格 84×56、格内文字垂直居中,tokens.css:461-474),
 * **填什么由模块决定**:硬件状态(对弈/训练营/课程/棋谱)、本局指标(复盘)、分数摘要(成长)。
 *
 * 灯色语义四棋类统一:绿=正常、琥珀=需处理、红=故障。器件名各家跟着**自己盘上真有的东西**走。
 */
export const GO_HARDWARE_CELLS: readonly StatusCell[] = [
  { label: '摄像头', value: '—' },
  { label: '标定', value: '—' },
  { label: 'LED', value: '—' },
];

export function KioskStatusCells({ cells }: { cells: readonly StatusCell[] }) {
  return (
    <div className={`kiosk-status${cells.length === 2 ? ' kiosk-status--2' : ''}`}>
      {cells.map((c) => (
        <div className="kiosk-status__cell" key={c.label}>
          <span className="kiosk-status__k">
            {c.tone && <i style={{ color: `var(--${c.tone})` }} />}{c.label}
          </span>
          <b className="kiosk-status__v">{c.value}</b>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: 跑它，确认绿**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/KioskStatusCells.test.tsx
```

Expected: PASS，4 条全绿

- [ ] **Step 5: 写 `KioskConsoleRail`**

```tsx
// katrain/web/ui/src/kiosk/shell/KioskConsoleRail.tsx
import type { ReactNode } from 'react';
import { KioskStatusCells, type StatusCell } from './KioskStatusCells';

/**
 * §5 L1 左栏。**四个模块几何完全一样,装的东西不同** —— 所以互切不跳:
 *   对弈 / 训练营 / 课程 / 棋谱 → 实体盘镜像(盘上正在发生什么)
 *   复盘                        → 上一局的终局盘(刚下完的那局是什么样)
 * 差别只在标题和同步行那句话。
 *
 * **左栏永不滚动**,恒为 434 固定高;滚动只属于右栏(规范 §5.2 第 7 条)。
 * **它是状态显示,不是入口** —— 落子方式(屏幕/实体盘)是每种对弈方式内部的二选一,不在这里。
 */
export function KioskConsoleRail({ title, sub, board, syncLeft, syncRight, statuses }: {
  title: string;
  sub: string;
  board: ReactNode;
  syncLeft: string;
  syncRight: string;
  statuses: readonly StatusCell[];
}) {
  return (
    <aside className="kiosk-console">
      <div className="kiosk-console__title"><b>{title}</b><em>{sub}</em></div>
      <div className="kiosk-console__frame">
        <div className="kiosk-mini-board">{board}</div>
      </div>
      <div className="kiosk-console__sync"><span>{syncLeft}</span><b>{syncRight}</b></div>
      <KioskStatusCells cells={statuses} />
    </aside>
  );
}
```

- [ ] **Step 6: 让 `KioskLayout` 出两栏骨架**

`KioskLayout.tsx` 的 children 换成：

```tsx
      {level === 1 && railFor(location.pathname)
        ? <div className="kiosk-layout-l1">{railFor(location.pathname)}<Outlet /></div>
        : <Outlet />}
```

`railFor` 先只覆盖 `/kiosk/play`（等价于今天的 `CONSOLE_ROUTES`），**其余 L1 屏在各自的 Task 里接**。删掉 `SmartBoardConsole` 的 import 与文件。

⚠️ `.kiosk-layout-l1` 是 `grid-template-columns: 296px 680px`（`tokens.css:430-433`），**右栏由页面自己提供根节点**。所以 `<Outlet/>` 渲染出来的那一层就是右栏——各屏的根必须是 `.kiosk-side` 或 `.kiosk-side kiosk-scrollzone`（Task 7）。在各屏改造完之前，它们的老 `<Box>` 会直接落进网格第二列，**尺寸会当场变成 680**，这是预期的中间态。

- [ ] **Step 7: 给几何闸加左栏纵向账（承重，最关键的一条）**

```ts
test('§5 L1 两栏:296 + 16 + 680,左栏纵向 20+10+272+10+32+10+56=410 严丝合缝', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const content = await box(page, '.kiosk-content');
  const rail = await box(page, '.kiosk-console');
  const side = await box(page, '.kiosk-side, .kiosk-layout-l1 > *:nth-child(2)');

  expect(rail.w).toBe(296);
  expect(side.w).toBe(680);
  expect(Math.round(side.x - (rail.x + rail.w))).toBe(16);
  expect(rail.x).toBe(content.x);
  expect(Math.round(side.x + side.w)).toBe(Math.round(content.x + content.w));

  const title  = await box(page, '.kiosk-console__title');
  const frame  = await box(page, '.kiosk-console__frame');
  const mini   = await box(page, '.kiosk-mini-board');
  const sync   = await box(page, '.kiosk-console__sync');
  const status = await box(page, '.kiosk-status');

  // 关系式先行:每一块都不许被 flex 压扁(全部 flex:none),四段间距都是 10
  expect(title.h).toBe(20);
  expect(sync.h).toBe(32);
  expect(status.h).toBe(56);
  expect(Math.round(frame.y - (title.y + title.h))).toBe(10);
  expect(Math.round(sync.y - (frame.y + frame.h))).toBe(10);
  expect(Math.round(status.y - (sync.y + sync.h))).toBe(10);
  // 纵向恰好用完,不多不少:最后一块的下缘 = 栏的内容盒下缘
  expect(Math.round(status.y + status.h)).toBe(Math.round(rail.y + rail.h - 1 - 11));

  // 镜像框是**正方形**,不许吃剩余空间(早先写 flex:1 → 272×312,上下各空 32)
  expect(frame.w).toBe(frame.h);
  expect(mini.w).toBe(mini.h);
  expect(mini.w).toBe(frame.w - 2 * 12);   // 248 = 272 − 2×12
});

test('§5 左栏永不滚动 —— 滚动只属于右栏', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const scrollable = await page.locator('.kiosk-console').evaluate((el) => {
    const walk = (n: Element): boolean => {
      const cs = getComputedStyle(n);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && n.scrollHeight > n.clientHeight) return true;
      return Array.from(n.children).some(walk);
    };
    return walk(el);
  });
  expect(scrollable, '左栏里有东西在滚 —— 它必须恒为 434 固定高').toBe(false);
});
```

- [ ] **Step 8: 把数据造到会溢出再量一次**

承重实测的铁律：**装得下的数据量下量出来的数字一概不算。** 用 `page.evaluate` 把三格的值撑长（例如把「已连接」换成 300 字），重跑上面两条。

```bash
cd katrain/web/ui && npx playwright test tests/kiosk-shell-geometry.spec.ts --config playwright.visual.config.ts --workers=1
```

Expected: 长值下 `.kiosk-status__cell` 出省略号、**外框 296×434 一动不动**。若格子被撑宽 → `tokens.css` 少了 `.kiosk-status__cell { min-width: 0 }`（grid 子项默认 `min-width:auto` 会拒绝收缩到内容宽度以下，实测把值撑到 **3900px 宽**、视口才 1024、**一个省略号都没有**）。`blockingPanel.css` 里有本地补丁，确认它还在作用域内；不在就把那条补丁搬进 `go-screens.css`。

> ⚠️ 这条本地补丁的口径要说准：它现在按「上游缺口」记，**但那是未验证的判断**，不像刻度轨道那条被两个数确认过。别把它写成结论。

- [ ] **Step 9: 双构建 + 提交**

```bash
cd katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d
cd ../../.. && git add -A katrain/web/ui/src/kiosk katrain/web/ui/tests
git commit -m "feat(kiosk-shell): L1 两栏改成 296+16+680,镜像栏用共享 .kiosk-console

此前是 322+2×20 外边距 = 362 占位、右边只剩 662。左栏纵向那串
20+10+272+10+32+10+56=410 在真浏览器量过,并把三格的值撑到会溢出再量了一遍。"
```

---

## Task 6: 图标、模式卡、组标题

**Files:**
- Create: `katrain/web/ui/src/kiosk/shell/icons.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/icons.test.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/KioskCard.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/KioskSecLabel.tsx`
- Copy: `smartbox-software/.../assets/icons/*.svg` → `katrain/web/ui/src/kiosk-shell/icons/`（82 个文件）
- Modify: `katrain/web/ui/src/kiosk-shell/MANIFEST.sha256`
- Test: `katrain/web/ui/tests/kiosk-shell-contract.spec.ts`

**Interfaces:**
- Produces: `<Icon name={IconName} filled?={boolean} />`，`IconName` 是从 `icons/` 目录名派生的联合类型
- Produces: `<KioskCard title sub icon|ring current?|soon?|todo?|dot? onClick? />`
- Produces: `<KioskSecLabel zh en value?/>`

**为什么要抄图标**：`src/kiosk-shell/icons/` 现在**只有 `house.svg` 一个**（当初只抄了 `tokens.css:338` 那条 mask 引到的那一个）。上游 `assets/icons/` 有 **82 个**（41 对 `<name>.svg` + `<name>-fill.svg`，Phosphor v2，`viewBox="0 0 256 256"`，`fill="currentColor"`，不带死色）。围棋十屏用到 **36 个不同名字**。规范 §10：**图标只能从 Phosphor v2 出，成对导出，重算 `MANIFEST.sha256`**，四个前端用**同一份字节**——所以整目录抄，不挑。

- [ ] **Step 1: 抄图标并扩 manifest**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-align/katrain/web/ui/src/kiosk-shell
cp /Users/fan/Repositories/smartbox-software/superpowers/shared/kiosk-shell/assets/icons/*.svg icons/
ls icons/*.svg | wc -l          # 期望 82
# manifest 里已有 icons/house.svg 那一行,其余 81 个补进去(路径去掉 assets/ 前缀,和既有 209 行同格式)
shasum -c MANIFEST.sha256 2>&1 | grep -c OK    # 补之前:209
```

补 manifest：把上游 `MANIFEST.sha256` 里 `assets/icons/` 那些行取出来、去掉 `assets/` 前缀、合进本地那份并按原顺序排好，然后：

```bash
shasum -a 256 -c MANIFEST.sha256 2>&1 | grep -v ': OK$'   # 期望没有输出
shasum -a 256 -c MANIFEST.sha256 2>&1 | grep -c ': OK$'   # 期望 290
```

> ⚠️ 这道闸答得了什么，要说准：`icons/` 和清单是**一起抄**的，所以在这里跑它只证明「**我这份副本自己没被人动过**」。上游换了图、上游清单跟着重算，我这边两个都还是旧的、还互相自洽，**闸照样绿**。要答「我这份还等于上游那份吗」，得再把**上游清单文件本身的 sha256** 钉一次——那条还没做，继续记在 `kiosk-design-alignment.md` §10。

- [ ] **Step 2: 写失败的单测——图标必须能跟随 `currentColor`**

`katrain/web/ui/src/kiosk/shell/icons.test.tsx`：

```tsx
import { render } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { Icon } from './icons';

describe('Icon', () => {
  // 用 <img src> 就跟不了容器的 color,而 .kiosk-dock__item[aria-current]{color:var(--ink)}
  // 全靠 currentColor 翻色 —— 选中那一格的图标会一直是灰的。
  test('内联 <svg>,不是 <img>', () => {
    const { container } = render(<Icon name="game-controller" />);
    expect(container.querySelector('svg')).not.toBeNull();
    expect(container.querySelector('img')).toBeNull();
  });

  test('svg 用 currentColor,没有写死的颜色', () => {
    const { container } = render(<Icon name="game-controller" />);
    const html = container.innerHTML;
    expect(html).toContain('currentColor');
    expect(html).not.toMatch(/fill="#[0-9a-fA-F]/);
  });

  test('filled 取 -fill 那一份,不是给同一份加个 CSS', () => {
    const off = render(<Icon name="gear" />).container.innerHTML;
    const on = render(<Icon name="gear" filled />).container.innerHTML;
    expect(on).not.toBe(off);
  });

  test('包裹层是 display:contents —— 默认的 inline span 会打断 Dock 项的纵向 flex', () => {
    const { container } = render(<Icon name="gear" />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain('kiosk-icon');
  });
});
```

- [ ] **Step 3: 跑它，确认红**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/icons.test.tsx
```

Expected: FAIL — 模块不存在

- [ ] **Step 4: 写实现**

```tsx
// katrain/web/ui/src/kiosk/shell/icons.tsx
// Phosphor v2(MIT),规范 §10:四个前端用同一份字节。`?raw` 拿到源码内联,
// 不能用 <img src> —— <img> 跟不了容器的 color。
const modules = import.meta.glob('../../kiosk-shell/icons/*.svg', {
  eager: true, query: '?raw', import: 'default',
}) as Record<string, string>;

const table: Record<string, string> = {};
for (const [path, source] of Object.entries(modules)) {
  table[path.split('/').pop()!.replace(/\.svg$/, '')] = source;
}

export type IconName =
  | 'arrow-clockwise' | 'arrow-counter-clockwise' | 'arrow-left' | 'arrow-right'
  | 'arrows-clockwise' | 'book-open' | 'books' | 'camera' | 'caret-down'
  | 'circuitry' | 'crown-simple' | 'flag' | 'game-controller' | 'gear'
  | 'globe-hemisphere-west' | 'grid-nine' | 'hand-pointing' | 'house' | 'info'
  | 'lightbulb' | 'magnifying-glass' | 'puzzle-piece' | 'robot' | 'skip-forward'
  | 'sliders-horizontal' | 'speaker-high' | 'squares-four' | 'trend-up'
  | 'trophy' | 'upload-simple' | 'user-circle' | 'users';

export function Icon({ name, filled = false }: { name: IconName; filled?: boolean }) {
  const source = table[filled ? `${name}-fill` : name] ?? table[name];
  if (!source) {
    // 缺图标要**响**,不要静默画个空盒子 —— 静默的话屏上少一个图标没人发现。
    throw new Error(`图标不在 kiosk-shell/icons/ 里:${name}${filled ? '-fill' : ''}`);
  }
  return <span className="kiosk-icon" aria-hidden="true" dangerouslySetInnerHTML={{ __html: source }} />;
}
```

- [ ] **Step 5: 跑它，确认绿**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/icons.test.tsx
```

Expected: PASS，4 条全绿

- [ ] **Step 6: 写 `KioskCard` 与 `KioskSecLabel`**

```tsx
// katrain/web/ui/src/kiosk/shell/KioskCard.tsx
import { Icon, type IconName } from './icons';

/**
 * §8 一级页模式卡。**所有一级页的卡片按钮都是这一种规格:220×76,40 方衬在左,
 * 标题+副标在右,间距 12。** 不许某个模块自己另做一套尺寸或把图标挪到上面 ——
 * 那是「切模块不跳」的另一种破法:框没跳,**手要去够的目标跳了**。
 *
 * 进度环卡不是新构造,是同一张卡换个衬(.kiosk-card__tile.is-ring):
 * 几何一个字不改,只把方衬里的图标换成环。
 *   · 环描边 4 ⇒ 半径 (40−4)/2 = 18,中间写百分比(9.5px)
 *   · **100% 的环走 --good,不走强调色** —— 棋种把强调色换成青毡绿时,
 *     「进行中」和「学完了」必须还分得开
 *   · 在学的那张 .is-current(强调色描边),一屏只有一张
 * 值读不到时环里写「—」不写 0(G8)。
 */
export function KioskCard({ title, sub, icon, ring, current, soon, todo, dot, onClick, ariaLabel }: {
  title: string;
  sub: string;
  icon?: IconName;
  ring?: number | null;      // null = 读不到 ⇒ 环里写「—」
  current?: boolean;
  soon?: string;             // 文案由调用方给(「即将上线」/「未录制」),不许写「锁定」
  todo?: boolean;
  dot?: boolean;
  onClick?: () => void;
  ariaLabel?: string;
}) {
  const cls = ['kiosk-card', current && 'is-current', soon && 'is-soon', todo && 'is-todo']
    .filter(Boolean).join(' ');
  const pct = ring == null ? null : Math.round(ring);
  return (
    <button
      type="button"
      className={cls}
      aria-label={ariaLabel ?? title}
      disabled={Boolean(soon || todo)}
      onClick={onClick}
    >
      <span className={`kiosk-card__tile${ring !== undefined ? ' is-ring' : ''}`}>
        {ring !== undefined
          ? <b>{pct == null ? '—' : `${pct}%`}</b>
          : icon && <Icon name={icon} />}
      </span>
      <span className="kiosk-card__t"><b>{title}</b><em>{sub}</em></span>
      {dot && <span className="dot" aria-hidden="true" />}
      {soon && <span className="soon">{soon}</span>}
    </button>
  );
}
```

```tsx
// katrain/web/ui/src/kiosk/shell/KioskSecLabel.tsx
/**
 * 组标题行:中文 12.5px Sans 700 .12em + 英文 11px Serif 斜体 --dim + 渐隐横线
 * + 右端可选的值(.secval)。容器几何在 tokens.css:563-566,四个子元素在 seclabel.css。
 *
 * 右端那个值是**数据**(「本机 5 局」「两档:500 / 2000 次计算」),不是旁注。
 * 稿子里的解释性段落(.note)是给读稿人的,不进这里,也不上线 —— 见 G5。
 */
export function KioskSecLabel({ zh, en, value }: { zh: string; en: string; value?: string }) {
  return (
    <div className="kiosk-seclabel">
      <h2>{zh}</h2>
      <em>{en}</em>
      <span className="rule" />
      {value && <b className="secval">{value}</b>}
    </div>
  );
}
```

- [ ] **Step 7: 写契约闸（不是几何闸）**

`katrain/web/ui/tests/kiosk-shell-contract.spec.ts`：

```ts
import { expect, test } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

const SRC = resolve(process.cwd(), 'src');

/**
 * 契约闸:扫源码,不开浏览器。它守的是三条「本地看着对、上板才塌」的规矩。
 */
test('固定画布上不许出现 vw / vh / cqw —— 一相对化,「切模块不跳」就没法用截图证明', () => {
  const bad: string[] = [];
  const walk = (dir: string) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = resolve(dir, e.name);
      if (e.isDirectory()) { if (e.name !== 'kiosk-shell') walk(p); continue; }
      if (!/\.(tsx?|css)$/.test(e.name)) continue;
      if (!p.includes('/kiosk/')) continue;
      readFileSync(p, 'utf8').split('\n').forEach((line, i) => {
        if (/\b\d+(\.\d+)?(vw|vh|cqw|cqh)\b/.test(line) && !line.trimStart().startsWith('*')
            && !line.trimStart().startsWith('//')) {
          bad.push(`${p}:${i + 1}  ${line.trim()}`);
        }
      });
    }
  };
  walk(SRC);
  expect(bad, `固定 1024×600 画布上不许用视口单位:\n${bad.join('\n')}`).toEqual([]);
});

test('图标不许手写内联路径 —— 只能从 kiosk-shell/icons/ 出(规范 §10)', () => {
  const bad: string[] = [];
  const walk = (dir: string) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = resolve(dir, e.name);
      if (e.isDirectory()) { walk(p); continue; }
      if (!/\.tsx$/.test(e.name) || !p.includes('/kiosk/')) continue;
      if (p.endsWith('shell/icons.tsx')) continue;              // 它就是那个出口
      const src = readFileSync(p, 'utf8');
      if (/<path\s+d="/.test(src)) bad.push(`${p}  手写了 <path d=…>`);
      if (/@mui\/icons-material/.test(src)) bad.push(`${p}  用了 MUI 图标`);
    }
  };
  walk(resolve(SRC, 'kiosk'));
  expect(bad, `图标要走 shell/icons.tsx:\n${bad.join('\n')}`).toEqual([]);
});
```

⚠️ **这条闸会一次报出一大堆现存违规**（`src/kiosk` 现在到处是 `@mui/icons-material`）。**不要为了让它变绿去大改**。做法：本 Task 先把它写成 `test.fail()` 之外的形式——用一个**白名单基线**（把今天所有违规文件列进 `KNOWN_MUI_ICON_FILES`，断言「没有新增」），每个屏 Task 做完就从白名单里划掉那一屏的文件。**基线 diff，不是一刀切。**

- [ ] **Step 8: 跑两条闸 + 双构建 + 提交**

```bash
cd katrain/web/ui
npx vitest run src/kiosk/shell
npx playwright test tests/kiosk-shell-contract.spec.ts --config playwright.visual.config.ts --workers=1
npx tsc -b && npm run build && npm run build:kiosk-2d
cd ../../.. && git add -A katrain/web/ui/src/kiosk katrain/web/ui/src/kiosk-shell katrain/web/ui/tests
git commit -m "feat(kiosk-shell): 抄进 82 个 Phosphor 图标,补模式卡与组标题两个共享构件

图标走 ?raw 内联而不是 <img src> —— <img> 跟不了 currentColor,
而 Dock 选中态的翻色全靠它。MANIFEST 由 209 行扩到 290 行,shasum -c 全绿。
契约闸先按白名单基线记既有违规,每屏做完划掉一批。"
```

---

## Task 7: 悬浮滚动区（**承重**，本轮唯一的新承重面）

规范 §5.2 要求右栏可滚，且**必须自己画一条悬浮滚动条**：原生滚动条一旦占宽度，680 就不是 680，三列 220 的算术当场崩；但零宽度的代价是完全没有位置指示。两个都要，就只能自己画。

共享包给的是**几何、渐隐和条子的画法**（`tokens.css:505-557`）；**状态机和条子的位置全是消费方的活**。

**Files:**
- Create: `katrain/web/ui/src/kiosk/shell/KioskScrollZone.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/KioskScrollZone.test.tsx`
- Test: `katrain/web/ui/tests/kiosk-shell-scroll.spec.ts`（**真浏览器、真滚轮**）

**Interfaces:**
- Produces: `<KioskScrollZone grow? head? resetKey?>{children}</KioskScrollZone>`
  - 不传 `grow` = **形态 1 整栏滚**（对弈首页、训练营首页、棋谱、课程、设置）
  - 传 `grow` = **形态 2 头尾固定、中列滚**（复盘的「待复盘对局」）

- [ ] **Step 1: 写失败的真浏览器闸（这条先写，因为它才是判据）**

`katrain/web/ui/tests/kiosk-shell-scroll.spec.ts`：

```ts
import { expect, test } from '@playwright/test';

test.use({ viewport: { width: 1024, height: 600 } });

/**
 * 承重闸。四条硬性,一条都不能靠 jsdom:
 *   ① 不溢出就**没有** data-at、**不画**滚动条(挂一条永远亮着的渐隐 = 谎报下面还有东西)
 *   ② 溢出了就**必须有** data-at,且拇指最短 24
 *   ③ 真的能滚 —— 用**真滚轮**,不是 scrollTop = n
 *      (Chromium 不认未受信任的合成 WheelEvent,`scrollTop = n` 证明不了「用户能滚」)
 *   ④ 换一批内容 scrollTop 归零
 */
async function boot(page, path: string) { /* 同 kiosk-shell-geometry.spec.ts 的 boot */ }

test('内容不溢出时:没有 data-at,也不画滚动条', async ({ page }) => {
  await boot(page, '/kiosk/settings');           // 用一个内容少的屏,或用 route 把列表 stub 空
  const zone = page.locator('.kiosk-scrollzone').first();
  await expect(zone).not.toHaveAttribute('data-at', /.*/);
  const barVisible = await zone.locator('.kiosk-scrollbar').evaluate(
    (el) => getComputedStyle(el).display !== 'none');
  expect(barVisible, '不溢出却画了滚动条 —— 谎报下面还有东西').toBe(false);
});

test('溢出时:data-at 从 top 走到 end,拇指 >=24 且不占布局宽度', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const zone = page.locator('.kiosk-scrollzone').first();
  const scroll = zone.locator('.kiosk-side__scroll');

  const overflow = await scroll.evaluate((el) => el.scrollHeight - el.clientHeight);
  expect(overflow, '这一屏没溢出,这条闸没有被测对象').toBeGreaterThan(0);

  await expect(zone).toHaveAttribute('data-at', 'top');

  // 拇指:>=24,且**不参与布局** —— 右栏仍然是 680
  const thumb = await zone.locator('.kiosk-scrollbar').evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { h: r.height, w: r.width, pos: getComputedStyle(el).position };
  });
  expect(thumb.h).toBeGreaterThanOrEqual(24);
  expect(thumb.pos).toBe('absolute');
  const sideW = await zone.evaluate((el) => el.getBoundingClientRect().width);
  expect(sideW, '滚动条占了布局宽度 —— 三列 220 的算术会当场崩').toBe(680);

  // **真滚轮**。Chromium 不认合成的 WheelEvent,scrollTop = n 证明不了用户能滚。
  await scroll.hover();
  await page.mouse.wheel(0, 200);
  await expect.poll(() => scroll.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  await expect(zone).toHaveAttribute('data-at', 'mid');

  await page.mouse.wheel(0, 5000);
  await expect.poll(() => zone.getAttribute('data-at')).toBe('end');
});

test('§5「露一半」:视口底边切在一张卡的中间,不许切在缝上', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const r = await page.locator('.kiosk-scrollzone').first().evaluate((zone) => {
    const scroll = zone.querySelector('.kiosk-side__scroll') as HTMLElement;
    const bottom = scroll.getBoundingClientRect().bottom;
    const cards = Array.from(scroll.querySelectorAll('.kiosk-card')) as HTMLElement[];
    // 找那张被视口底边穿过的卡
    const cut = cards.map((c) => c.getBoundingClientRect())
      .find((b) => b.top < bottom && b.bottom > bottom);
    return cut ? { peek: bottom - cut.top, h: cut.height } : null;
  });
  expect(r, '视口底边没有穿过任何一张卡 —— 要么没溢出,要么正好切在缝上(最坏的一种)').not.toBeNull();
  // 上下界按卡高比例算,再加绝对下限:max(16, .25h) <= 露出 <= h − max(12, .25h)
  const lo = Math.max(16, 0.25 * r!.h);
  const hi = r!.h - Math.max(12, 0.25 * r!.h);
  expect(r!.peek, `露出 ${r!.peek} 不在 [${lo}, ${hi}]`).toBeGreaterThanOrEqual(lo);
  expect(r!.peek).toBeLessThanOrEqual(hi);
});
```

- [ ] **Step 2: 跑它，确认红**

```bash
cd katrain/web/ui && npx playwright test tests/kiosk-shell-scroll.spec.ts --config playwright.visual.config.ts --workers=1
```

Expected: FAIL — 页面上根本没有 `.kiosk-scrollzone`

- [ ] **Step 3: 写实现**

结构照象棋 `xiangqi/ui/src/shell/KioskScrollZone.tsx`（活样本），但**要吸收五子棋那份 hook 里记下的两条**（G11 的第 10、11 条）：

```tsx
// katrain/web/ui/src/kiosk/shell/KioskScrollZone.tsx
import { type ReactNode, useCallback, useEffect, useState } from 'react';

function sync(rail: HTMLElement | null, scroll: HTMLElement | null, bar: HTMLElement | null) {
  if (!rail || !scroll) return;
  const overflow = scroll.scrollHeight - scroll.clientHeight;
  if (overflow < 1) {
    // 不溢出:两条都撤掉。挂一条永远亮着的渐隐,等于谎报下面还有东西。
    rail.removeAttribute('data-at');
    if (bar) bar.style.display = 'none';
    return;
  }
  const atTop = scroll.scrollTop < 1;
  const atEnd = scroll.scrollTop >= overflow - 1;
  rail.dataset.at = atTop ? 'top' : atEnd ? 'end' : 'mid';
  if (bar) {
    // 拇指最短 24 —— 再短就成了一个点,读不出比例。
    const height = Math.max(24, (scroll.clientHeight / scroll.scrollHeight) * scroll.clientHeight);
    bar.style.display = '';
    // 形态 2 下 offsetTop 量的正是组标题占掉的那一截 = 滚动视口的起点。
    bar.style.top = `${scroll.offsetTop}px`;
    bar.style.height = `${height}px`;
    bar.style.transform = `translateY(${(scroll.scrollTop / overflow) * (scroll.clientHeight - height)}px)`;
  }
}

export function KioskScrollZone({ children, grow, head, resetKey }: {
  children: ReactNode;
  grow?: boolean;
  head?: ReactNode;
  /**
   * 换了一批内容就回到顶部。**不是锦上添花**:滚动容器是同一个 DOM 节点,
   * React 只换里面的行,scrollTop 会原样留着 —— 翻到第 2 页时列表还停在第 1 页
   * 滚到的位置。国象在真浏览器里量到过 **558px**(棋谱库翻页),静态截图看不出来。
   * 规范 §5 防跳铁律 4 也要求切 L1 模块时归零。
   */
  resetKey?: string | number;
}) {
  // callback ref + useState,**不能用 useRef + 空依赖 effect** ——
  // 滚动节点首帧可能还不存在,useRef 那种写法读到一次 null 就再也不会重跑。
  const [rail, setRail] = useState<HTMLElement | null>(null);
  const [scroll, setScroll] = useState<HTMLDivElement | null>(null);
  const [bar, setBar] = useState<HTMLElement | null>(null);
  const resync = useCallback(() => sync(rail, scroll, bar), [rail, scroll, bar]);

  // ResizeObserver 在这儿**不会触发**:tokens.css 把 .kiosk-side__scroll 钉成 height:100%,
  // 子元素长高时盒子一动不动。所以只能靠 children 变化这个信号手动重算。
  useEffect(() => { resync(); }, [children, resync]);

  useEffect(() => {
    if (resetKey === undefined || !scroll) return;
    scroll.scrollTop = 0;
    resync();                        // 回到顶部之后渐隐和条子也要跟着回 top 态
  }, [resetKey, scroll, resync]);

  const inner = (
    <>
      {head}
      <div className="kiosk-side__scroll" ref={setScroll} onScroll={resync}>{children}</div>
      <i className="kiosk-scrollbar" ref={setBar} />
    </>
  );

  return grow
    ? <section className="kiosk-section kiosk-section--grow kiosk-scrollzone" ref={setRail}>{inner}</section>
    : <div className="kiosk-side kiosk-scrollzone" ref={setRail}>{inner}</div>;
}
```

- [ ] **Step 4: 在一屏上真接起来再跑**

本 Task 只需要**一个**被测物：把 `/kiosk/play` 的右栏根节点换成 `<KioskScrollZone>`（内容先不动，Task 10 才搬）。**内容必须真的溢出**——`PlayPage` 现在的内容在 680×434 里可能装得下，装得下就没有被测对象。造数据：`page.route` 把「继续上一局」和跨平台那一组撑到 5 张卡。

```bash
cd katrain/web/ui && npx playwright test tests/kiosk-shell-scroll.spec.ts --config playwright.visual.config.ts --workers=1
```

Expected: 四条全绿。

- [ ] **Step 5: 演示这道闸有牙（三处变异，一处一跑）**

| 变异 | 应该红在哪条 |
|---|---|
| 把 `if (overflow < 1)` 那个早退删掉（永远写 `data-at`） | 「不溢出时没有 data-at」 |
| 把 `Math.max(24, …)` 改成不带下限 | 「拇指 >= 24」 |
| 把 `resetKey` 那个 effect 删掉 | 需要额外一条：切模块后 `scrollTop` 应为 0（在 Step 1 里补上） |

每次变异后 **先确认 `npx tsc -b` 是绿的、产物哈希变了**，再跑测试。⚠️ 上一轮踩过：只改一处会留下未使用的符号，`tsc -b` 报 TS6133 → vite 没跑 → 产物没变 → **测试全绿，被读成「闸没牙」，和真的没牙逐字相同**。

- [ ] **Step 6: 双构建 + 提交**

```bash
cd katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d
cd ../../.. && git add -A katrain/web/ui/src/kiosk katrain/web/ui/tests
git commit -m "feat(kiosk-shell): 补上规范 §5.2 那条悬浮滚动条(此前完全没做)

宽 3、拇指最短 24、绝对定位不占布局宽度;不溢出就不画,也不写 data-at。
闸用真滚轮不用 scrollTop=n(Chromium 不认合成 WheelEvent),
并变异演示过三处。ResizeObserver 在这儿不触发的原因写进注释了。"
```

---

### Task 7 修订（2026-08-22，做完之后回填）

计划写的四条闸落地成**三条真浏览器闸 + 两条 jsdom 单测**，四处与原文不同，都是动手时才拿到的事实：

1. **§5「露一半」那条挪到 Task 10。** 它量的是**内容落点**，而 `/kiosk/play` 的内容
   Task 10 才定稿 —— 现在测它，红了只能靠调即将作废的内容变绿，那是假绿。
   （顺带：接上滚动区之后它**天然**就成立了，见 `play-top.png`，底边正切在「对局历史」那条上。）

2. **拇指下限 24 那条闸在 `stuff(300)` 这批输入下是睡着的。** 434/777×434 = **242**，
   把 `Math.max(24, …)` 整个拿掉照样过关。下限要到内容极长才承重 ⇒ 单开一条
   `STUFF_HUGE`（20000px，算出来 **9.19**），并且**在闸里断言「不带下限算出来的数 < 24」**——
   这一条是判据本身：它一旦不成立，下条断言就又睡着了，而睡着和有牙**逐字相同**。

3. **造输入必须在挂载之前。** 事后 `page.addStyleTag` 改内容高度，组件**收不到任何信号**
   （`ResizeObserver` 盯的是滚动容器自己的盒子，而它恒是 `height:100%`）—— 量到的是上一帧
   的结论，闸会红在一个不存在的产品缺陷上。改成 `addInitScript` 注入 `<style>`。
   这不是脚手架的将就，**它就是 G11 第 10 条描述的那个机制**。

4. **`flexShrink: 0` 不能省。** `.kiosk-side__scroll` 是 flex column，默认 `shrink:1` 会把
   页面内容那一整块压回 434 —— 内容再多也永远「不溢出」，滚动条不画、渐隐不亮，
   **和裁掉一模一样**，而且是静默的。

**实测到的病灶**：`/kiosk/play` 右栏视口 680×434、内容 **477** ⇒ 底下 43px
（「对局历史」那一条）在 `overflow:hidden` 下**一直看不见**。Task 7 顺带修掉的就是这个。

三处变异各红在对应那条：早退删掉 → 「装得下却写了 data-at（Received: "top"）」；
下限拿掉 → 「拇指 9.1875 < 24」；`resetKey` effect 删掉 → 「expected 120 to be +0」。
第三处删 effect 会留下未使用的 `resetKey` 触发 TS6133，**顺手把解构里那个名字也去掉**——
否则编译不过、测试根本没跑，全绿会被读成「闸没牙」。

---

## Task 8: 页控条、动作区、主行动 —— 替掉 `SubPageBar`

规范 §11：**顶栏在所有层级恒为品牌态**，返回 / 视图切换 / 上下文标题全部下放到页控条。页控条位置写死，两种布局下**纵向位置完全相同**（y 70–114，高 44），所以有盘页和无盘页来回切时这条控件带不会上下跳。

| 布局 | 何时用 | 页控条位置 |
|---|---|---|
| **A · 有棋盘** | 对局屏、做题屏 | 右栏顶部，x **548–1008** |
| **B · 无棋盘** | 单元列表、课程列表、设置子页 | 中间区顶部通栏，x **16–1008** |

**页控条只许放三类东西**：① 返回 ② 视图 / 落子方式切换（最多 3 段）③ 最多一个页级图标按钮。**悔棋、认输、求和、提示一律不许上页控条**——它们属于右栏下面的动作区。

**现状**：`AiSetupPage.tsx:227-237` 是**全仓唯一**已经用 `.kiosk-pagebar` 的（上一轮做的）。另外 **15 个页面**用 `SubPageBar`（52px 通栏返回条），**2 个**手写了同构造（`SettingsPage.tsx:97-108`、`VisionSetupPage.tsx:10-12`），**3 个**手写 52px 面包屑条（`ResearchPage.tsx:532,589,680`），还有 `PvpLocalSetupPage.tsx:102` 把返回键塞进表单头。`GameHistoryPage`（`play/pvp/history`）**一个返回入口都没有**，Dock 也不出——是个死胡同屏（唯一出路是「复盘」跳去 `/kiosk/research`）。

**Files:**
- Create: `katrain/web/ui/src/kiosk/shell/KioskPagebar.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/KioskPagebar.test.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/KioskActions.tsx`
- Modify: 上述 15 + 2 个页面（**只换这条控件带，不动页面内容**）
- Delete: `katrain/web/ui/src/kiosk/components/layout/SubPageBar.tsx`、`SubPageBar.test.tsx`
- Test: `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts`

**Interfaces:**
- Produces: `<KioskPagebar backLabel? onBack? backBusy? title sub? segment? action? />`
- Produces: `<KioskActions items={{ icon, label, onClick, disabled?, danger? }[]} />`

- [ ] **Step 1: 写失败的单测——页控条只许放三类东西**

`katrain/web/ui/src/kiosk/shell/KioskPagebar.test.tsx`：

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { KioskPagebar } from './KioskPagebar';

describe('KioskPagebar', () => {
  test('没有返回回调时不渲染返回键,但标题位置不变', () => {
    const { container } = render(<KioskPagebar title="设置" />);
    expect(container.querySelector('.kiosk-pagebar__back')).toBeNull();
    expect(screen.getByText('设置')).toBeInTheDocument();
  });

  test('没有 sub 就整块不渲染 —— 不占位、不写占位字', () => {
    const { container } = render(<KioskPagebar title="设置" />);
    expect(container.querySelector('.kiosk-pagebar__sub')).toBeNull();
  });

  test('没有 segment 时右端就空着,返回键位置不变', () => {
    const { container } = render(<KioskPagebar title="x" onBack={() => {}} backLabel="返回" />);
    expect(container.querySelector('.kiosk-seg')).toBeNull();
  });

  test('分段最多 3 段 —— 再多就该换别的控件', () => {
    expect(() => render(<KioskPagebar title="x" segment={{
      value: 'a', options: [['a','A'],['b','B'],['c','C'],['d','D']], onChange: () => {},
    }} />)).toThrow(/最多 3 段/);
  });

  test('忙碌时返回键保留位置与去向,但如实标成忙碌且不可点', () => {
    render(<KioskPagebar title="x" backLabel="返回" onBack={() => {}} backBusy />);
    const back = screen.getByRole('button', { name: /返回/ });
    expect(back).toBeDisabled();
    expect(back).toHaveAttribute('aria-busy', 'true');
  });
});
```

- [ ] **Step 2: 跑它，确认红**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/KioskPagebar.test.tsx
```

Expected: FAIL — 模块不存在

- [ ] **Step 3: 写 `KioskPagebar`**

```tsx
// katrain/web/ui/src/kiosk/shell/KioskPagebar.tsx
import type { KeyboardEvent, ReactNode } from 'react';
import { Icon, type IconName } from './icons';

export interface PagebarSegment {
  value: string;
  options: readonly (readonly [string, string])[];   // [value, label]
  onChange: (next: string) => void;
  ariaLabel?: string;
}

/**
 * §11 页控条:`[← 返回 36h] 12px [标题 15px Serif] [英文副标 12px 斜体] …auto… [分段 32h]`。
 *
 * **悔棋、认输、求和、提示一律不许放这里** —— 它们属于右栏下面的动作区。
 * 页面没有 2D/3D 时右端就空着,**返回按钮的位置不变**(位置恒定是肌肉记忆)。
 */
export function KioskPagebar({ backLabel, onBack, backBusy = false, title, sub, segment, action }: {
  backLabel?: string;
  onBack?: () => void;
  backBusy?: boolean;
  title: ReactNode;
  sub?: ReactNode;
  segment?: PagebarSegment;
  action?: { icon: IconName; label: string; onClick: () => void };
}) {
  if (segment && segment.options.length > 3) {
    throw new Error('§11:页控条的分段控件最多 3 段,再多就该换别的控件');
  }
  const switchByKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (!segment || !['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    e.preventDefault();
    const i = segment.options.findIndex(([v]) => v === segment.value);
    const next = e.key === 'ArrowLeft' ? Math.max(0, i - 1) : Math.min(segment.options.length - 1, i + 1);
    segment.onChange(segment.options[next][0]);
  };
  return (
    <div className="kiosk-pagebar">
      {onBack && (
        <button type="button" className="kiosk-pagebar__back"
                disabled={backBusy} aria-busy={backBusy || undefined} onClick={onBack}>
          <Icon name="arrow-left" />{backLabel}
        </button>
      )}
      <span className="kiosk-pagebar__title">
        {title}
        {sub ? <span className="kiosk-pagebar__sub">{sub}</span> : null}
      </span>
      {action && (
        <button type="button" className="kiosk-btn kiosk-btn--icon kiosk-pagebar__spacer"
                aria-label={action.label} onClick={action.onClick}>
          <Icon name={action.icon} />
        </button>
      )}
      {segment && (
        <span className={`kiosk-seg${action ? '' : ' kiosk-pagebar__spacer'}`}
              role="radiogroup" aria-label={segment.ariaLabel ?? '视图'}>
          {segment.options.map(([value, label]) => (
            <button key={value} type="button" className="kiosk-seg__btn" role="radio"
                    aria-checked={segment.value === value}
                    aria-pressed={segment.value === value}
                    tabIndex={segment.value === value ? 0 : -1}
                    onKeyDown={switchByKey}
                    onClick={() => segment.onChange(value)}>{label}</button>
          ))}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 跑它，确认绿**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/KioskPagebar.test.tsx
```

Expected: PASS，5 条全绿

- [ ] **Step 5: 写 `KioskActions`**

```tsx
// katrain/web/ui/src/kiosk/shell/KioskActions.tsx
import { Icon, type IconName } from './icons';

/**
 * §11 动作区:等宽,每格高 52,圆角 10,列间距 7,图标在上、文字在下。
 * tokens.css:802 是 `grid-auto-flow: column; grid-auto-columns: 1fr`,**几个就摆几个** ——
 * 规范表里那个「3 列」是当时国象的实例数,围棋是 4 个(见 D3)。
 *
 * **动作区永远贴右栏底**(tokens.css:758 `.kiosk-rail .kiosk-actions{margin-top:auto}`):
 * 上面的折叠面板收起时,空白落在它**上面**,按钮不许跟着上移 —— 悔棋/认输的位置是肌肉记忆。
 *
 * `danger` 走**类名 `danger`**,不是 `data-danger` —— 五子棋 `play/GameRail.tsx:373` 和
 * 围棋设计稿 `go-kiosk.tmpl.html:305` 用的都是这个类名,三处对齐才不用各写一套选择器。
 * 长相见 **D7**:只换字色和边框(`gomoku/ui/src/index.css:1619`),形状尺寸背景一律不动;
 * 规则写在 `go-screens.css`,不写进共享的 tokens.css。
 */
export function KioskActions({ items }: {
  items: readonly { icon: IconName; label: string; onClick: () => void; disabled?: boolean; danger?: boolean }[];
}) {
  return (
    <div className="kiosk-actions">
      {items.map((a) => (
        <button key={a.label} type="button" disabled={a.disabled}
                className={a.danger ? 'danger' : undefined} onClick={a.onClick}>
          <Icon name={a.icon} /><span>{a.label}</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: 逐屏换掉 `SubPageBar`（17 处）**

**只换控件带，不动页面内容。** 逐个文件把 `<SubPageBar title=… right=…/>` 换成 `<KioskPagebar …/>`，并按下表选布局：

| 布局 | 页面 |
|---|---|
| **A**（页控条在右栏顶，x548） | `TsumegoProblemPage`（做题屏，右栏顶）、`ReportDetailPage`（有盘） |
| **B**（通栏，x16） | `LobbyPage`、`LiveMatchPage`、`PlatformConnectPage`、`PlatformLobbyPage`、`PlaceholderPage`、`PlatformEngineSetupPage`、`TsumegoCategoriesPage`、`TsumegoUnitListPage`、`TsumegoLevelPage`、`TsumegoUnitsPage`、`TutorialBooksPage`、`TutorialBookDetailPage`、`TutorialSectionPage`、`SettingsPage`（→ 但它 Task 18 会重排成 L1-B，本 Task 先接壳）、`VisionSetupPage` |

`right` 插槽里原来放的东西**分两类处理**：
- 是**视图/落子方式切换**（最多 3 段）→ 放 `segment`。
- 是**业务动作**（`LobbyPage` 的「排位赛 / 自由对局」、`ReportDetailPage` 的「在研究中打开」、`LiveMatchPage` 的「直播中」Chip、`TutorialBooksPage` 的分类文字、`TutorialBookDetailPage` 的作者）→ **不许上页控条**。降到内容区第一行，或并进 `sub`（作者、分类这种是**副标性质**，并进 `sub` 是对的；「排位赛/自由对局」是**动作**，降到内容区）。

~~⚠️ **`GameHistoryPage` 顺手补一个返回**~~ —— **2026-08-21 作废**：Fan 裁定对局历史直接进
`/kiosk/report`，这一页没有入口了，该并进 `ReportsPage` 而不是给它补返回。见 Task 10 那条再修订。

⚠️ `ResearchPage` 那三条手写 52px 面包屑条**本轮不动**（D2：research 只接壳，内容区维持现状）。它有 864 行、三处结构不同，动它超出「接壳」。**登记。**

- [ ] **Step 7: 给几何闸加页控条两组**

```ts
test('§11 布局 B:页控条通栏 x16–1008、y70–114、高 44,返回键高 36', async ({ page }) => {
  await boot(page, '/kiosk/tsumego/15k/capturing');
  const screen = await box(page, '.kiosk-screen');
  const bar = await box(page, '.kiosk-pagebar');
  const back = await box(page, '.kiosk-pagebar__back');
  expect(bar.x - screen.x).toBe(16);
  expect(bar.w).toBe(992);
  expect(bar.y - screen.y).toBe(70);
  expect(bar.h).toBe(44);
  expect(back.h).toBe(36);
});

test('§11 有盘页与无盘页来回切,页控条的纵向位置一模一样', async ({ page }) => {
  await boot(page, '/kiosk/tsumego/15k/capturing');
  const b = await box(page, '.kiosk-pagebar');
  await boot(page, '/kiosk/tsumego/problem/1');       // 布局 A
  const a = await box(page, '.kiosk-pagebar');
  expect(a.y).toBe(b.y);          // 这条就是「切模块不跳」本身
  expect(a.h).toBe(b.h);
  expect(a.x).toBe(548);          // 布局 A 在右栏顶
  expect(a.w).toBe(460);
});

test('§11 长标题不许把返回键挤成两行 —— 触点位置在每一屏都一样', async ({ page }) => {
  await boot(page, '/kiosk/tsumego/15k/capturing');
  const shortBack = await box(page, '.kiosk-pagebar__back');
  await page.locator('.kiosk-pagebar__title').evaluate((el) => {
    el.textContent = '很长的标题'.repeat(40);          // 把数据造到会溢出
  });
  const longBack = await box(page, '.kiosk-pagebar__back');
  expect(longBack.h, '返回键被长标题挤高了').toBe(shortBack.h);
  expect(longBack.x).toBe(shortBack.x);
  const overflow = await page.locator('.kiosk-pagebar__title')
    .evaluate((el) => el.scrollWidth > el.clientWidth);
  expect(overflow, '长标题没有被截断,它把整条撑开了').toBe(true);
});
```

第三条会红——共享包**没给** `.kiosk-pagebar` 的 flex-shrink 兜底（G11 末尾那三条之一）。补进 `go-screens.css`（Task 9）：`.kiosk-pagebar__back { flex: none }` + `.kiosk-pagebar__title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }`。

> ⚠️ **判据要跟着轴走**：横向截断验 `scrollWidth > clientWidth`，纵向验 `scrollHeight > clientHeight`。轴换了而断言没换，会红在一个不存在的缺陷上（上一轮实测过：改成横向省略号之后，那条纵向断言的两个数都是 20）。

- [ ] **Step 8: 全量跑 + 双构建 + 提交**

```bash
cd katrain/web/ui
npx vitest run src/kiosk                    # 与基线比,不许新增失败
npx playwright test tests/kiosk-shell-geometry.spec.ts --config playwright.visual.config.ts --workers=1
npx tsc -b && npm run build && npm run build:kiosk-2d
cd ../../.. && git add -A katrain/web/ui/src/kiosk katrain/web/ui/tests
git commit -m "feat(kiosk-shell): 17 屏的通栏返回条换成规范 §11 的页控条

SubPageBar(52 通栏)删掉。原来 right 插槽里的业务动作降到内容区 —— §11 只许放
返回 / 视图切换 / 一个页级图标按钮。顺手给 GameHistoryPage 补了返回(它此前
没有任何返回入口、Dock 也不出,是个死胡同)。ResearchPage 那三条手写条登记未动。"
```

---

### Task 8 修订（2026-08-22，做完之后回填）

**做到了**：15 个用 `SubPageBar` 的页面 + `SettingsPage` + `VisionSetupPage` 共 **17 处**全换成
`KioskPagebar`，`SubPageBar.tsx` / `.test.tsx` 删除。布局 B 实测 **x16 / y70 / w992 / h44、返回键 h36**，
布局 A（`AiSetupPage`）实测 **x548 / y70 / w460 / h44** —— 与 §11 逐个吻合。

**七处与原文不同，都是动手时才拿到的事实：**

1. **`KioskActions` 推迟到 Task 11。** Task 8 没有任何一屏渲染动作区（对局屏 / 做题屏归 Task 11、14），
   而它的全部内容——等宽、格高 52、图标在上文字在下、**永远贴右栏底**——都是**布局结论**。
   现在建，只能靠 jsdom 断言类名，等于发一个没被任何真运行时验证过的构件。

2. **标题渲染成 `<h2>`，不是稿子里的 `<span>`。** 静态稿无所谓，真应用丢了标题语义读屏就没法跳转
   （`SettingsPage` / `navigation.integration` 两个既有测试就是查 `role="heading"` 红的）。
   UA 给 h2 的上下 margin 只在 `.kiosk-pagebar__title` 这一个类上归零 ——
   **不做 `.kiosk h1,h2,h3,h4{margin:0}` 那种全局归零**：它的特异性 (0,1,1) 压得过 MUI emotion 类 (0,1,0)，
   会把全站 `<Typography gutterBottom>` 的下边距一起吃掉。（G11 第 1 条到 Task 9 再按屏补。）

3. **`go-screens.css` 提前到 Task 8 建。** §11「长标题不许挤到返回键」那条闸现在就要有被测对象，
   而它靠的正是这个文件里的两条兜底。Task 9 的屏级类往下加，不要另起文件。

4. **闸原来量错了对象。** 计划写的三条断言是 `back.h` / `back.x` / 标题溢出 —— 这条带子**没有
   `flex-wrap`，「挤成两行」在这儿根本发生不了**；真实的失效是返回键被**压窄**（实测 82 → 68）。
   拿掉 `flex: none` 之后原断言**全绿**。补了 `back.w` 才有牙。

5. **`min-width: 0` 与 `overflow: hidden` 互为冗余，两条并存等于给闸发免疫。**
   CSS Sizing §4.1：`overflow` 不是 `visible` 时 flex 项的自动最小尺寸就是 0。删掉任一条行为都不变
   ⇒ 针对任一条的变异都杀不死闸。删掉 `min-width: 0` 之后，把 `overflow` 改成 `visible` 当场红在
   **布局断言**上（client 3000 = scroll 3000，不再收缩）。

6. **`SettingsPage` 根节点的 `px/pt` 撤了。** 它把页控条推到 **x28 / y78** —— 正是 §11 要防的
   「有盘页无盘页来回切上下跳 8px」。内边距挪到下面的内容网格，视觉一个字没变。

7. **`TsumegoProblemPage` 的布局 A 不达标，归 Task 14。** 实测 **x548 / y86 / w444**（该 548 / 70 / 460）：
   它的右栏还带 `p: 2`，整屏也还没换成 `.kiosk-layout-a`。本 Task 只换控件带，不动骨架 ⇒
   闸的布局 A 用 `AiSetupPage`（它上一轮就是真布局 A，实测正好命中三个数）。

**两笔净损失，都不拿别的东西顶上：**

- `TsumegoUnitListPage` 的进度 Chip **做完时变绿**那个信号没了（数字并进 `sub`，颜色语义丢失）。归 **Task 13**。
- `ReportDetailPage` 标题的 `title=` 原生提示没了。**这是台触摸屏，手指没有悬停态**，那个提示本来就点不出来；
  标题截断该看见的是省略号，已由真浏览器闸守着。

**未动的**：`ResearchPage` 那三条手写 52px 面包屑条（D2：research 本轮只接壳）。

---

## Task 9: `go-screens.css` 与围棋棋盘

**Files:**
- Create: `katrain/web/ui/src/kiosk-shell/go-screens.css`
- Create: `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx`
- Create: `katrain/web/ui/src/kiosk/shell/goBoard.ts`
- Create: `katrain/web/ui/src/kiosk/shell/goBoard.test.ts`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`（加第 5 行 CSS import）

**`go-screens.css` 的精确内容**（G10 已经把被上游收编的剔掉了；下面就是全部，不多不少）：

```
A. UA 兜底(G11 第 1、2 条 —— 稿子靠一句全局 *{margin:0} 兜着,真应用不能这么干)
   .kiosk h1,.kiosk h2,.kiosk h3,.kiosk h4,.kiosk p { margin: 0 }
   .kiosk button,.kiosk input,.kiosk select,.kiosk textarea { font-family: inherit }
       ⚠️ 用 font-family: 不用 font: 简写(简写会把字号一起重置)
B. 共享包缺的三条(三家都各补了一份,注释都写着「该提上游」)
   .kiosk-resume 的 .bar / h4 / p / .pill
   .kiosk-pagebar__back{flex:none} + .kiosk-pagebar__title{min-width:0;overflow:hidden;
       text-overflow:ellipsis;white-space:nowrap}
   .kiosk-board__play{display:grid;place-items:center}
   .kiosk-actions button:disabled / .kiosk-movenav button:disabled(G8 禁用不许伪装成可用)
   .kiosk-icon{display:contents}      ⚠️ 国象同名类写的是 display:flex,照错 Dock 就不居中
   .kiosk-greet 的 b / b i / span,外加长名字的 wrap 兜底(G11 第 9 条)
   .kiosk-tag--live(共享包没有直播态)
C. 模式卡的三个附加态(共享包只有 .is-todo)
   .kiosk-card{position:relative} / .kiosk-card.is-soon / .kiosk-card .soon / .kiosk-card .dot
D. 围棋专属,从 go-kiosk.tmpl.html 逐字节抄(行号在括号里)
   .disc / .disc.b / .disc.w                      (:126-128)  黑白圆珠
   .pcard 及其 .disc/h4/p/.clock/.clock b/span    (:120-135)  对局屏玩家卡
   .railsec / .rst / .rst b                       (:137-138)  右栏可长块
   .mvrows 及其 span/.n/.mv/.mv.now/::-webkit-scrollbar (:139-143) 棋谱等宽两列
   .ledger / .lrow / .lrow .disc/b/i              (:146-150)  本局记账
   .panel / .panel > h3                           (:153-154)  通用面板
   .dots / .dots i / i.ok / i.now                 (:178-181)  做题进度点阵
   .empty / h4 / p / p b                          (:184-187)  空态块
   .gob / .ln / .star / .mark / .ghost / .atari   (:74-80)    棋盘 SVG 的线与标记
   .note / .note b / .note code / code.k          (:175-177)  **只给真 UI 文案用**(G5)
   .wrplot 的 .mid/.curve/.drop/.now              (:194-198)  复盘曲线的线型
       ⚠️ 外框用共享的 .kiosk-eval/__axis/__plot,不要抄 .wrbox/.wraxis/.wrplot
E. **不抄**
   .row/.rows/.tag*  → 用 .kiosk-row*/.kiosk-tag*(G10)
   .big/.metric/.bar → 成长屏专用,本轮跳过(D1)
   .gal/.galintro/.galcap/.device → 画廊装订,不是设备上的东西
   .kiosk-screen 那条 → 共享包 :258 已经有,稿子那条只是画廊的圆角和阴影
   木纹贴图 --oak/--darkwood → D6,资产不在 MANIFEST 管辖内
```

- [ ] **Step 1: 写失败的单测——棋盘几何**

`katrain/web/ui/src/kiosk/shell/goBoard.test.ts`：

```ts
import { describe, expect, test } from 'vitest';
import { GO_COLS, STARS_19, coordToXY, labelFor } from './goBoard';

describe('围棋坐标 —— 记法是绝对的,四棋类里只有围棋这套', () => {
  // A–S 跳掉 I 只有 18 个,19 路要写到 T。这条上过 sample-go/gate.mjs。
  test('列名跳 I,A–T 正好 19 个', () => {
    expect(GO_COLS).toBe('ABCDEFGHJKLMNOPQRST');
    expect(GO_COLS.length).toBe(19);
    expect(GO_COLS).not.toContain('I');
  });

  test('行号 1 在最下、19 在最上', () => {
    expect(coordToXY('A1').y).toBe(18);
    expect(coordToXY('A19').y).toBe(0);
  });

  test('九星在第 4 / 10 / 16 条线上(0 起算 3 / 9 / 15)', () => {
    expect(STARS_19).toEqual([
      [3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15],
    ]);
  });

  test('Q16 是右上星位那一带 —— 拿一个真坐标钉住方向', () => {
    expect(coordToXY('Q16')).toEqual({ x: 15, y: 3 });
  });

  test('刻度四条带都写字,上下 A–T、左右 19–1', () => {
    expect(labelFor('top', 0)).toBe('A');
    expect(labelFor('top', 18)).toBe('T');
    expect(labelFor('left', 0)).toBe('19');
    expect(labelFor('left', 18)).toBe('1');
  });
});
```

- [ ] **Step 2: 跑它，确认红**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/goBoard.test.ts
```

Expected: FAIL — 模块不存在

- [ ] **Step 3: 写 `goBoard.ts` 与 `GoBoardSvg.tsx`**

留白取 **0.5 格**，这条不是随手取的：刻度带把 19 个字均分在 460 上，第 i 个字的中心在 `(i+0.5)/19`；盘上第 i 条线在 `(0.5+i)/19` —— 两式相等，**字和线逐条对齐**。

```ts
// katrain/web/ui/src/kiosk/shell/goBoard.ts
export const GO_SIZE = 19;
/** 跳 I:A–S 跳掉 I 只有 18 个,19 路要写到 T。 */
export const GO_COLS = 'ABCDEFGHJKLMNOPQRST';
/** 留白 0.5 格 —— 取 0.66/0.7 两端各差六七个像素,一眼能看出字没对准线。 */
export const GO_MARGIN = 0.5;
export const STARS_19: readonly (readonly [number, number])[] = [
  [3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15],
];

export function coordToXY(coord: string): { x: number; y: number } {
  return { x: GO_COLS.indexOf(coord[0]), y: GO_SIZE - parseInt(coord.slice(1), 10) };
}

export function labelFor(band: 'top' | 'bottom' | 'left' | 'right', i: number): string {
  return band === 'top' || band === 'bottom' ? GO_COLS[i] : String(GO_SIZE - i);
}
```

`GoBoardSvg.tsx` 照 `go-kiosk.tmpl.html:849-920` 的 `gosvg()` 搬。**两条必须带上**：

1. **paint server 的 id 必须带自增后缀**（`id="gr-3"`）。`url(#gr)` **永远解析到文档里第一个同名的**；一页上有好几块盘时，一旦第一个落进 `display:none` 的那一台，**所有盘的浅色底一起失效**——象棋整块盘变黑褐就是这么来的（规范 §13②）。
2. **木纹那层 `mix-blend-mode:multiply` 必须有显式 `isolation: isolate` 祖先**（`.gob { isolation: isolate }`）。不隔离的话它不只跟盘面浅底相乘，而是**一路穿透**跟底下那圈深色木框一起相乘（规范 §13③）。

- [ ] **Step 4: 跑它，确认绿；再写 `go-screens.css` 并引入**

```bash
cd katrain/web/ui && npx vitest run src/kiosk/shell/goBoard.test.ts
```

Expected: PASS，5 条全绿

`KioskApp.tsx` 的 CSS import 补第 5 行（顺序：fonts → tokens → go-tokens → seclabel → **go-screens**）。

- [ ] **Step 5: 给几何闸加刻度那一条（这条上一轮抓出过 2.8px）**

```ts
test('§8 刻度带 19 列、没有 I 列,且字心与盘上的线逐条对齐', async ({ page }) => {
  await boot(page, '/kiosk/tsumego/problem/1');
  const r = await page.evaluate(() => {
    const top = document.querySelector('.kiosk-board__ruler--top')!;
    const labels = Array.from(top.querySelectorAll('span'));
    const svg = document.querySelector('.kiosk-board__play .gob') as SVGSVGElement;
    // 两组数都从**渲染结果**里取,不从公式里取 —— 判据是屏上那条线的横坐标。
    const lineCenters = Array.from(svg.querySelectorAll('line'))
      .filter((l) => Math.abs(+l.getAttribute('x1')! - +l.getAttribute('x2')!) < 0.01)
      .map((l) => { const b = l.getBoundingClientRect(); return b.x + b.width / 2; })
      .sort((a, b) => a - b);
    const rulerCenters = labels
      .map((s) => { const b = s.getBoundingClientRect(); return b.x + b.width / 2; })
      .sort((a, b) => a - b);
    return {
      cols: labels.length,
      hasI: labels.some((s) => s.textContent!.trim() === 'I'),
      first: labels[0].textContent!.trim(),
      last: labels[labels.length - 1].textContent!.trim(),
      maxDrift: lineCenters.length === rulerCenters.length
        ? Math.max(...lineCenters.map((c, i) => Math.abs(c - rulerCenters[i]))) : null,
    };
  });
  console.log('[go-ruler]', JSON.stringify(r));    // 数先打出来:断言一红后面的 log 就不执行了
  expect(r.cols).toBe(19);
  expect(r.hasI, '刻度里出现了 I 列 —— 会让人在真盘上数错一路').toBe(false);
  expect(r.first).toBe('A');
  expect(r.last).toBe('T');
  expect(r.maxDrift, '字心没落在线上').toBeLessThan(1);
});
```

⚠️ **刻度轨道要写 `1fr`，这是常驻本地补丁，不是等上游**：`tokens.css:607-616` 只写了 `display:grid` + `grid-auto-flow:column`，轨道按**字宽**取尺寸；围棋 `M` 比 `J` 宽 ⇒ 字心不落在 `(i+0.5)/19` 上，**实测最大错开 2.8px**，补成 `1fr` 之后 **0**。

**但这条不能提上游**：象棋在真浏览器上量了两个数——它的轨道是 `auto` 却错开只有 **0.02px**（装的是 `1`–`9`/`九`–`一`，同族等宽，`auto` 被拉伸成等分），而若给它收 `1fr`，**第一条字会偏出 26px**（象棋盘不占满落子区，`xMidYMid meet` 居中，盘宽 356.2，轨道节距要跟着盘走）。⇒ **两边正确的值不是同一个数，上游收敛不了。** 该往上游提的是那条**不变式**：「刻度带的节距必须等于盘的线节距」，判据是**屏上那条线的横坐标**，不是「字心应该落在 `(i+0.5)/N`」那个版式规则。

- [ ] **Step 6: 双构建 + 提交**

```bash
cd katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d
cd ../../.. && git add -A katrain/web/ui/src/kiosk katrain/web/ui/src/kiosk-shell
git commit -m "feat(kiosk-shell): 补齐围棋屏级 CSS 与 19 路棋盘构件

go-screens.css 只装共享包没有的那些 —— vendored tokens.css 比设计稿新,
.row/.tag/.wrbox 早被上游收成 .kiosk-row/.kiosk-tag/.kiosk-eval 了。
棋盘:留白 0.5 格、列名跳 I 写到 T、九星在 4/10/16 线;paint server id 带自增后缀
(url(#x) 只认第一个,象棋整块盘变黑褐就是这么来的),.gob 显式 isolation:isolate。
刻度轨道 1fr 是常驻本地补丁,不提上游 —— 象棋收 1fr 反而偏 26px,理由写在注释里。"
```

---

### Task 9 修订（2026-08-22，做完之后回填）

**计划里这个 Task 的清单大半已经在树上了** —— 2026-08-11/12 那轮做挡局屏时顺手做掉的，
计划书当时没回填。动手前逐条核过：

| 计划说要做 | 实际状态 |
|---|---|
| `go-screens.css` 建文件 | Task 8 已建（§11 那条闸要有被测对象） |
| 棋盘留白 0.5 格、列名跳 I 写到 T、九星 4/10/16 | `KioskSetupBoard.tsx` 早就是对的，且注释比计划详尽 |
| 刻度轨道 `1fr` 常驻本地补丁 + 「不提上游」的两个数 | `kioskSetupBoard.css` 已有，象棋 0.02px / 收 1fr 偏 26px 都记在里面 |
| 刻度对齐的几何闸 | `kiosk-ai-ladder-layout-a-geometry.spec.ts:135` 已有，实测 drift **0** |
| paint server id 带自增后缀 | 只有一块盘、id 已是 `kiosk-setup-board-wood`（唯一名），Task 11 出现第二块盘时再说 |

**所以本 Task 真正做的是三件：**

1. **把坐标算式从 `KioskSetupBoard` 私有作用域抽成 `shell/goBoard.ts`。** 这不是整理癖：
   对局屏（Task 11）和做题屏（Task 14）都要按坐标摆子，拿不到就会**各抄一份**——
   而跳 I / 行号 1 在最下 / 星位按路数换 / 留白 0.5，每一条都容易抄错且抄错了屏上还挺像。
   11 条单测钉住这些事实，其中一条正面证「`margin=0.5` 是字线对齐的充要条件，换 1.5 就不成立」。
   变异验过：`GO_MARGIN` 改 1.5 → 既有刻度闸当场红。

2. **字族闸扩到 Task 8 那三屏**（跨平台 / 设置 / 单元列表）——它们各引进了一批裸 `<button>`。

3. **`GoBoardSvg.tsx` 推迟到 Task 11**，理由同 `KioskActions`：本 Task 没有一屏要摆子，
   而「摆得对不对」是渲染结论。抽出来的 `goBoard.ts` 已经把会抄错的部分锁住了。

**一处实测推翻了 G11：**

> **G11 第 2 条（表单控件写 `font-family: inherit`，否则板子上出豆腐块）在本仓是多余的。**
> 往跨平台屏塞一个裸 `<button>中文</button>` 当变异探针，字族闸**没红**。查计算值：
> `"SmartBox Sans", "SmartBox Kai", …`，匹配到 **两条 `button → inherit`**，发规则的是
> **MUI `CssBaseline`**。三家活样本要补这条，是因为**它们不是 MUI 栈**（纯 React + 手写 CSS）。
> ⇒ 这不是「我们还没踩到」，是这条坑在这个技术栈上不存在。照抄会多一条永远不承重的规则，
> 而不承重的规则会让针对它的变异永远杀不死闸（本轮已在 `min-width:0` 上栽过一次）。
> **G11 第 1 条（heading margin 归零）同理不做全局版**，理由见 Task 8 修订第 2 点。
> 两条都写进了 `go-screens.css` 的注释，连同量到的数。

**`go-screens.css` 的 D 段（`.pcard` / `.railsec` / `.mvrows` / `.ledger` / `.panel` / `.dots` /
`.empty` / `.note` / `.wrplot`）本轮不搬**：它们各自只有一屏消费，跟着那一屏进来，
落地当场就能被那一屏的四图和承重闸看住。现在整批倒进去，只能得到一堆没有任何真运行时验证过的规则。

---

## 第一块到此为止 —— **停下来给 Fan 看四图**

Task 1–9 做完，共享壳就稳定了：顶栏 / Dock / L1 两栏 / 模式卡 / 主行动 / 悬浮滚动条六件都接上了，每一屏的内容还是旧的。

**这时先拍一次 `/kiosk/play` 的四图**，作为「壳对了、内容还没搬」的存档，交 Fan 过目。它同时是 Task 10 的前后对照物。**Fan 确认之前不要开始 Task 10。**

---

# 第二块：逐屏搬运

**每一屏一个 Task，形状完全一致，所以只在 Task 10 把公共步骤写全，后面的屏只写自己不同的那部分。**

## 每屏的固定七步

1. **读三样东西**：设计稿里这一屏的 markup（`go-kiosk.tmpl.html` 的行号在各 Task 里给了）、参考图 `sample-go/shots/NN-*.png`、现状页面文件。
2. **列出这一屏的 `.note`**，逐条判定是「给读稿人的旁注」还是「真 UI 文案」（G5），把判定写进 Task 的提交信息。**旁注一条都不搬。**
3. **改页面**：根节点换成 `<KioskScrollZone>`（形态 1）或 `.kiosk-side` + `<KioskScrollZone grow>`（形态 2），内部用共享类重写；**数据来源、hooks、API 调用、路由跳转一律不动**。
4. **删掉这一屏用的 `@mui/icons-material`**，换 `shell/icons.tsx`，并从 Task 6 那个白名单里划掉这一屏的文件。
5. **跑既有单测**：这一屏的 `*.test.tsx` 大多断言的是**文案与行为**（不是像素），所以**应该继续绿**。红了先看是不是自己把文案改了——G7 文案冻结，改文案就是错的。
6. **四图 + 承重**：写这一屏的 `tests/kiosk-screen-NN-*.fourup.spec.ts`，跑出四张图；若这一屏有滚动区，跑 `kiosk-shell-scroll.spec.ts` 的那三条对着它再跑一遍（把数据造到会溢出）。
7. **停下来给 Fan 看四图。确认之前不进入下一屏。**

## 四图 spec 的模板（每屏照抄，只换五个值）

```ts
import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, waitForRealPixels } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });        // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600');

test('四图:对弈首页 ←→ sample-go/shots/01-play.png', async ({ page }) => {
  await freezeClock(page);                          // 冻在 16:40 —— 和参考图对得上,产物也字节稳定
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/**', (route) => {     // 一条兜底 + 按 pathname 分派,别漏接口
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    if (path === '/api/v1/vision/status') return route.fulfill({ json: { enabled: true, camera_connected: true, pose_locked: true, sync_state: 'synced', recognition_ready: true, led_connected: true, bound_session_id: null } });
    if (path === '/api/v1/geometry/status') return route.fulfill({ json: { phase: 'ready', session_calibrated: true, last_valid: true, capabilities: { camera_ready: true, led_ready: true, geometry_ready: true } } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play');
  await page.waitForSelector('.kiosk-screen');
  await waitForRealPixels(page, '.kiosk-mini-board canvas, .kiosk-mini-board svg');
  const r = await captureFourUp({
    page, referencePng: resolve(SHOTS, '01-play.png'), outDir: OUT, slug: '01-play',
    referenceCaption: '参考：sample-go/shots/01-play.png · 稿子上的 .note 旁注不上线（三家都没搬）',
    implementationCaption: '实现：/kiosk/play @1024×600 · 时钟冻在 16:40 · Dock 六项（成长本轮跳过）',
  });
  console.log(`[fourup 01-play] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
```

⚠️ **硬件三格必须 stub 成 ready。** 取图机器上没有摄像头和 LED，不 stub 的话三格全是红/琥珀，**交到人手上会被读成设计**（国象记过这条）。同时——**stub 出来的态要写进图里的标签带**，别让下一个人指着这张图说「硬件链是通的」。

---

## Task 10: 屏 01 · 对弈首页 `/kiosk/play`

> **从 Task 7 挪过来的一条（2026-08-22）**：§5「露一半」的闸在这里写 ——
> 视口底边必须切在一张卡的**中间**，不许切在缝上。判据：`max(16, .25h) <= 露出 <= h − max(12, .25h)`。
> 闸本身在 `tests/kiosk-shell-scroll.spec.ts` 里写现成的注释指路，别另起一个文件。


**设计稿**：`go-kiosk.tmpl.html` 第 ① 屏（L1-A，形态 1 整栏滚；行号在 2026-08-21 那一轮之后变了，按 `data-screen="play"` 找）。**现状**：`pages/PlayPage.tsx`（203 行）。

> ### ⚠️ 2026-08-21 修订：这一屏少了一组、也不再摆散文
>
> Fan 看完二十七屏之后当面否掉了两件事，稿子已经改，**下面那张表里的「落子方式」一行和「四处 `.note`」那一段都作废**：
>
> 1. **「落子方式」整组从首页拿掉**，搬进每一张开局设置屏的最上面（②③④⑩ 四屏，`.setgrp.inputgrp`）。
>    原话：「画框的设置(是否使用物理棋盘，使用几路棋盘)应该放到每个对弈页面子模块的对局设置页中……放在其最上方，醒目一些。不要放在对弈首页」。
>    ⇒ 本 Task **不再新加**那一组;改由 Task 11(自由对弈设置) / Task 12(升降级) / Task 13(本地对局) 和跨平台人机那一屏各自加一次。
>    下面那段「这一屏最重要的一处结构改动」连同它引的那句稿内散文一并作废 ——
>    **那句解释「实体盘不是第六张并列卡」的话，本身就是这个位置放错了的证据**。
> 2. **首页四段 `.note` 已经从稿子上删掉**（收进 HTML 注释）。原话：「不要写那么多解释文字，还都是小字，7 英寸屏看起来非常费劲」。
>    原来那条「四处 `.note` 全是旁注，一条都不搬」的结论**方向没变**，但依据变了：稿子上现在根本没有这四段。
>    ⚠️ `platforms.ts` 的 `comingSoon` 那条**事实**照旧要落实（Step 5 不变）。
>
> ⇒ 右栏由六块收成**五块**：问候行 / 继续上一局 / 人机对弈 / 人人对弈 / 跨平台对弈（+ 底部「对局历史」那个小方块）。

**左栏**（`KioskConsoleRail`）：标题 `实体棋盘` / `Camera board`；盘画 `data-b="Q16,Q4" data-w="D4,D16" data-last="D16"`（**实现里换成真镜像数据**，不是这四颗）；同步行 `盘面与屏幕一致` / `刚刚同步`；三格 `摄像头 · 标定 · LED`。

**右栏五块，自上而下**：

| 块 | 类 | 内容 |
|---|---|---|
| 问候行 56 | `.kiosk-greet` | `下午好，<i>访客</i>` + `选择一种方式开始对弈`。**身份还在加载时不许喊名字**（G11 第 8 条） |
| 继续上一局 60 | `.kiosk-resume` | 竖条 + `继续上一局` + `自由对弈 · KataGo 5 级 · 第 10 手 · 你执黑` + 药丸 `恢复`。**无未完成对局时整块不渲染**，不许留占位 |
| 落子方式 | `.kiosk-section` + 两条 `.kiosk-row` | 组标题 `落子方式` / `Input` / secval `下面每一种玩法都能用`；行一 `屏幕 / 实体盘` + 分段；行二 `棋盘路数` + 分段 `19 路 / 13 路 / 9 路` |
| 人机对弈 | `.kiosk-cards` 2 张 | `自由对弈`(`robot`)、`升降级对弈`(`trophy`)；组标题 secval `强度档说的是对手，不是你的段位` |
| 人人对弈 | `.kiosk-cards` 2 张 | `本地对局`(`users`)、`在线大厅`(`globe-hemisphere-west`, 带 `.dot`) |
| 跨平台对弈 | `.kiosk-cards` 3 张 | `OGS`、`星阵围棋`、`野狐围棋`(`.is-soon` + `即将上线`)；组标题 secval `平台由 /platforms 返回` |

**这一屏最重要的一处结构改动（规范 §4）**：**「智能棋盘」不是第六张并列卡**，它是**每种对弈方式内部的落子方式二选一**。稿子把它提到最上面那一组，理由写在稿里：*「这两条摆在最上面，是因为它们横跨下面每一种玩法：选好了再挑玩法，而不是每张卡里各问一遍。」* 现状 `PlayPage` 没有这一组，**要新加**——但那两个分段**接的是现有的设置状态**，不是新功能。

**四处 `.note` 全是旁注，一条都不搬**（`:238`「围棋原来那张稿把它做成一张并列卡，是错的」、`:245`「见 `interface.py` 的分析闸」、`:252`「段位只有在线大厅的定级队列会改」、`:261`「三家的名字…在 `kiosk/constants/platforms.ts` 里」）。⚠️ 但 `:261` 里有一条**事实**要落到实现上：`野狐` 那张灰是因为 `platforms.ts:26` 的 `comingSoon` —— 而 `PlayPage` **今天根本没读这个字段**（survey 实测）。本轮要读它，让灰是真的。

**要保住的现状**（`PlayPage.test.tsx` 13 条断言的都是这些，改坏会红）：
- 三家平台 DOM 顺序恒为 **OGS → 野狐 → 星阵**，空响应和请求失败时也一样；
- 连接态路由：`engine/golaxy` / `lobby?platform=ogs` / `/cross-platform`；
- token 变化时**同步**重置成断开态；**旧请求不许覆盖新请求**；登出后到的响应要丢掉；
- `对局历史 ›` → `/kiosk/play/pvp/history`。

> ### ⚠️ 2026-08-21 再修订：`对局历史` 现在稿子上有了，但它**不通向 `GameHistoryPage`**
>
> 上面那段（「稿子上没有、不要删、摆法有疑问就问」）**整段作废**。问过了，Fan 当场裁了两条：
>
> 1. **「对局历史按钮太大了，可以参考国际象棋的对局历史按钮，和其他按钮保持大小一致」**
>    ⇒ 就是一张普通的 `.kiosk-card`（220×76），进「对局历史」组，和同屏其他 7 张卡一模一样。
>    **同一屏上的卡不许有第二种尺寸** —— 这条国象 2026-07-28 就裁过，注释还留在 `sample-chess` 里。
>    不要用通栏 `.rows > .row` + 「打开」药丸键，那是围棋自己发明的第二种尺寸。
> 2. **「需要能够跳转到复盘模块的首页，不是现在的单独创建一个复盘页，搞得过于复杂了」**
>    ⇒ 落点是 **`/kiosk/report`（复盘模块首页）**，不是 `/kiosk/play/pvp/history`。
>    设计稿里那一屏 `history` **已经删掉**（28 屏 → 27 屏）：它和复盘屏的列表画的是同一批局，
>    而它自己的职责只是「从一张表里挑一局送到另一屏的同一张表去」。国象从来没有这一屏。
>
> ⇒ **`GameHistoryPage` 因此没有任何入口了。** 这不是「顺手补个返回」能解决的（下面 Task 里
>    那条「⚠️ GameHistoryPage 顺手补一个返回」也一并作废）。建议：把它的列表并进
>    `ReportsPage`（那边本来就渲染同一张表，且已有「未分析 / 分析中 / 已分析」三态），
>    然后删掉 `play/pvp/history` 路由。**这一步动的是实现不是稿子，落地前跟 Fan 确认一次。**

- [ ] **Step 1** 读 `go-kiosk.tmpl.html:214-268` + `shots/01-play.png` + `pages/PlayPage.tsx` 全文。
- [ ] **Step 2** 列出这一屏四处 `.note` 的判定（都是旁注），写进提交信息。
- [ ] **Step 3** 改 `PlayPage.tsx`：根节点换 `<KioskScrollZone>`，六块按上表用共享类重写；`ModeCard` 换 `KioskCard`（`ModeCard.tsx` 若无其它消费者就删，有就留着）。
- [ ] **Step 4** 让 `KioskLayout.railFor` 给 `/kiosk/play` 返回 `<KioskConsoleRail …/>`，数据接现有的 `VisionContext` / `GeometryContext`（**不新造数据源**）。
- [ ] **Step 5** 读 `platforms.ts` 的 `comingSoon`，让野狐那张真的走 `.is-soon`。
- [ ] **Step 6** 跑单测：`npx vitest run src/kiosk/pages/PlayPage.test.tsx src/kiosk/__tests__/PlayPage.test.tsx`。Expected: 15 条全绿（**文案冻结，红了先怀疑自己改了文案**）。
- [ ] **Step 7** 写 `tests/kiosk-screen-01-play.fourup.spec.ts`（照上面的模板），跑出四张图。
- [ ] **Step 8** 承重：把跨平台那一组 stub 成 6 张卡（造到会溢出），跑 `kiosk-shell-scroll.spec.ts` 的三条对着 `/kiosk/play`。Expected：`data-at` 走 top→mid→end、拇指 ≥24、右栏恒 680、底边切在卡的 [19, 57] 之间。
- [ ] **Step 9** 双构建 + `tsc -b` + 提交。
- [ ] **Step 10** **把四张图交给 Fan，等确认。**

---

### Task 10 修订（2026-08-22，做完之后回填）

**Fan 看第一版四图后指出两条**，都不是「细节没抠」，是整块东西不见了：

1. **镜像栏里的棋盘整块没画。** 上一版 `GoConsoleRail` 传 `board={null}`，理由写的是「不画假子」。
   那个理由只推翻了三个选项里的一个 —— **不画盘**（画面少一块、也没说清为什么）、
   **画一盘子**（假数据）、**画空盘 + 压暗 + 同步行写「识别的盘面还没接进来」**（盘在、但我看不到它）。
   第三条才对。`GoBoardSvg`（Task 9 推迟的那个，现在有真消费者）落地，`.gob.is-muted` 就是
   「看不到盘」和「盘上没子」的区分。压暗档位试过 `.32`，盘几乎看不见，收到 `.5`。
2. **组标题的渐隐横线不见了。** 上一版那三行是 MUI `Typography`，**根本没走 `.kiosk-seclabel`** ——
   中文标题 / 英文副标 / 横线 / 右端值四样只剩一样。`KioskSecLabel` 是 Task 6 就建好的，
   这一屏一直没接。

**顺手收掉的三处**（都是「实现在说一句不真的话」，不是审美）：

- 「自由对弈」不再是 jade 渐变的 primary 卡。稿子四张一模一样 —— 差别由**内容**表达，
  把一张做成主推等于替用户决定他该下哪一种。
- **野狐不再请人「点击登录连接」一个连不上的平台。** 它在 `PLATFORM_META` 里本来就带
  `comingSoon`，`PlatformConnectPage` 早把按钮禁掉写「即将支持」，而首页却在邀请你去登录。
  现在首页禁用 + 「即将上线」，并把连接页那句一起改成「即将上线」——
  **同一个事实两处口径必须一致**。顺序也照稿子改成「能用的在前、即将上线的最后」。
- 「对局历史」从一条通向死胡同（`play/pvp/history` 没有任何返回入口、Dock 也不出）的小入口，
  改成一张普通卡，落点 `/kiosk/report`（Fan 2026-08-21 的裁定）。

**`KioskCard` 的可及名改了**：默认从 `title` 改成 `title，sub，soon`。
`.dot`（已连接那颗绿点）和 `.soon` 徽标都是**纯视觉**，只报标题的话读屏的人拿到的三张平台卡
一模一样，分不出哪张连上了。它当时只有 PlayPage 一个消费者，改动面为零。

**没搬的两条 `.secval`**（「强度档说的是对手，不是你的段位」「平台由 `/platforms` 返回」）：
`.secval` 的位置按规范放的是**数据**，这两句是写给读稿人的解释（G5）。

**「全部对局」的副标没有数字。** 稿子写「6 局 · 1 局已有报告」是示例数据；本页拿不到真数
（要另开一次 `user-games` 计数请求），**不许把示例数字当成真的印上去**。要数字先去取，登记。

**四图的三处 fixture**（硬件三格 ready / 继续上一局 / OGS 已连接）全部写进了图上的标签带 ——
造的是**输入**，画出来的还是页面自己的逻辑；不写明的话下一个人会指着这张图说「板上真有一局在下」。
`refOnly` 从 38986 降到 21094，`both` 从 11387 升到 29279。

**交付形式改了（Fan 2026-08-22）**：从此不再贴 PNG，做成 Artifact 给链接。
第一份对照台 https://claude.ai/code/artifact/edf481c3-fed0-425d-9088-0d4ce6a0c440
（叠加擦除 / 参考 / 实现 / 并排 / 差异五视图 + 差异清单）。**后面每一屏照此办理。**

---

## Task 11: 屏 02 · 对局中 `/kiosk/play/ai/game/:sessionId`

**设计稿**：`go-kiosk.tmpl.html:270-311`（**L3 布局 A**）。**现状**：`pages/GamePage.tsx`（825 行）+ `components/game/GameControlPanel.tsx`。

> ### ⚠️ 2026-08-22 修订：这一屏整块重画了，**下面那张表和「不许有 `.kiosk-eval`」那一段全部作废**
>
> Fan 把 galaxy 的自由对弈页和这一屏并排看，给了三条，都成立（原话：「kiosk 界面需要涵盖 galaxy 界面
> 有边框所有元素：按钮、胜率/目差图 等」「3D 效果按钮可以不做」「新增的按钮没有图标，字体也不是
> 霞骛楷体，大小也不一致」）。稿子已改，按**新稿**做，行号按 `data-screen="game"` 找：
>
> 1. **胜率/目差图回来了。** 旧禁令的依据是**能力判断**（KataGo 要真跑 playout），而
>    `interface.py:_do_analyze_current` 是**领地和图表共用的一次按需分析**（点一次算一次，优先走
>    `analysis_engine()` 即云端），胜率是那一次调用的**副产品**。规范 §8 已改（v1.32），
>    `sample-go/gate.mjs` 那条断言**反了过来**：对局屏**必须**有 `data-fold="eval"`。
>    图是**双轴**：左胜率、右目差，**上黑下白**（`models_db.py:373` 的 winrate 是黑方的，
>    共享 `ScoreGraph` 把 1.0 画在顶上）。
> 2. **七个键排成 4×2 的等大格阵**（galaxy 八个减掉 3D）：`领地` `AI 支招` `图表` `数子` /
>    `悔棋` `停一手` `认输`。实现里它们**本来就是同一个 `ItemToggle`**，不需要改组件，改的是稿子。
>    `数子` 灰着是真的（`/api/count/request` 在 `count_min_moves`=100 之前一律拒），
>    灰的旁边要写明还差什么。
> 3. **`本局记账` 那一块和 `棋谱` 那一块都撤了。** 提子挪进玩家卡副行、规则与贴目挪进页控条副标；
>    棋谱在这一屏是**稿子自己发明的**（galaxy 右栏没有、`GameControlPanel` 也没有），
>    而右栏 516 装不下「胜率块 + 记账块 + 棋谱」三样。
> 4. **页控条右端没有 `2D | 3D`**（围棋不做 3D，这条 2026-08-21 已经在别处作废过一次）。
>
> **本屏两条要动实现的（不是稿子的事，做这个 Task 时一起做）：**
>
> - **升降级局里这一块必须整块不渲染。** 现在前端只是**不去请求**（`GamePage.tsx` 的
>   `isRankedGameType` 早退），面板照样渲染，画出来是一条全 `--` 的空图 —— 规范 §8 明写
>   「禁的时候整块不渲染，不要渲成灰的或显示『—』，那是在提示『这里本来有个东西，你没资格看』」。
>   改法：`GameControlPanel` 的 `showScore` 再与 `!isRanked` 相与，`图表` 那个键在升降级局里
>   一并不出现（同一条 `interface.py` 分析闸已经在后端拦住了，界面只是没跟上）。
> - **`analysisToggles.score` 默认 `true` ⇒ 默认状态下每手都会触发一次 `analyze_current`。**
>   配了云端分析引擎就走云端；没配就和对弈引擎抢同一个本地 KataGo —— 这正是 2026-07-27 那条
>   禁令当初担心的事，实现用「默认开」把它变成了常态。规范 §8 那句「默认关」**四家一家都没实现**。
>   **要不要把默认改成关，是产品决定，等 Fan 定**，先别自己改。


✅ **Q1 已裁定 —— 见 D7：照抄五子棋 `gomoku/ui/src/index.css:1619` 那一行**（`color: var(--bad)` + `border-color: color-mix(in srgb, var(--bad) 35%, var(--hair))`，形状尺寸背景一律不动）。写进 `go-screens.css`，选择器 `.kiosk-screen[data-screen="game"] .kiosk-actions .danger`。

**骨架**：`.kiosk-layout-a` = 盘 516 贴 x16 + 16 + 右栏 460。右栏自上而下：

| 块 | 类 | 内容 |
|---|---|---|
| 页控条 44 | `.kiosk-pagebar` | `← 退出对局` / 标题 `自由对弈` / 副标 `19 路 · 贴 6.5 目 · 不让子` / 右端 `2D \| 3D` |
| 玩家卡 ×2，每张 60 | `.pcard` / `.pcard.turn` | 白：圆珠 + `KataGo · 5 级` + `已落子 · 执白` + 右端 `08:12` / `本局已下`；黑：`访客（你）` + `轮到你 · 执黑` + `第 11 手` / `不限时` |
| 本局记账（可折叠） | `.kiosk-fold[data-fold="ledger"]` | 标题行 30 `本局记账 · 按规则数出来的`，右端 `白贴 6.5 目`；体内两条 `.lrow`：`提子 0` / `还没有子被吃`、`提子 0` / `贴目 6.5 · 不让子` |
| 棋谱（可折叠，会长） | `.kiosk-fold.kiosk-fold--grow[data-fold="moves"]` | 标题行 `棋谱 · 交叉点坐标`，右端 `第 10 手`；体是 `.mvrows` 三列网格（手数 / 黑 / 白），**默认滚到最后一手** |
| 动作区 4 格 | `.kiosk-actions` | `形势`(`lightbulb`) `悔棋`(`arrow-counter-clockwise`) `停一手`(`hand-pointing`) `认输`(`flag`, `danger`) |

**规范 §11 明写围棋对局屏「不画胜率曲线，也不留占位框」**（KataGo 要真跑 playout，还和对手引擎抢同一块 Mali）。`sample-go/gate.mjs:47-48` 有一条断言专门核这个：**对局屏不许有 `data-fold="eval"`**。⇒ **本屏一个 `.kiosk-eval` 都不许出现。**

**折叠面板四条硬性**（规范 §11）：默认展开；**收起的是明细不是结论**（标题行右端那个当前值收起后照旧显示）；腾出的空间归还给同栏里仍展开的那一块，**优先给棋谱**；**动作区永远贴右栏底**，两块都收起时空白落在它**上面**。

**棋谱默认停在当前这一手**，不是第 1 手；用户手动往回翻之后不再自动跟随，直到他翻回底部。

**两处 `.note`**：`:287`「这里不画胜率曲线：盒上的 KataGo 要真跑 playout…」是**旁注**（它在解释设计决定），不搬。

- [ ] **Step 1** 读 `go-kiosk.tmpl.html:270-311` + `shots/02-game.png` + `GamePage.tsx` + `GameControlPanel.tsx`。
- [ ] **Step 2** 确认这屏已经在 `KioskLayout` 里了（Task 4 Step 6 挪过来的），`dockLevelOf` 判成 2、不出 Dock、顶栏在。
- [ ] **Step 3** 右栏按上表重写；棋盘换成 `.kiosk-board` + 四条刻度带 + `.kiosk-board__play` 里的 `GoBoardSvg`。
- [ ] **Step 4** 写 `KioskFold`（`shell/KioskFold.tsx`，照象棋 `shell/KioskFold.tsx`），带上那四条硬性。
- [ ] **Step 5** 单测：加两条 —— ① 收起「本局记账」后，标题行右端 `白贴 6.5 目` **仍在**；② 两块都收起时，动作区的 `bottom` 不变（这条要在真浏览器里量，写进 spec 不是 jsdom）。**再加一条真浏览器断言（D7）**：认输键 `color` 求得出值且 ≠ 兄弟键的 `color`；若现状的认输确认框渲染在 `.kiosk` 外，它那颗确认键的 `color`/`border-color` 也要求得出值（国象 `index.css:574-580` 记过这个坑）。
- [ ] **Step 6** 真浏览器几何：盘 516×516@(16,70)、落子区 460×460@(44,98)、右栏 460@x548、页控条 460×44@y70、返回键高 36。**上一轮量过，规范给的数一次全中**（`kiosk-ai-ladder-layout-a-geometry.spec.ts`），照抄那条 spec 的量法。
- [ ] **Step 7** 承重：把棋谱造到 300 手，量 ① 棋谱那块自己滚（`.kiosk-fold--grow` 内 `scrollHeight > clientHeight`）② **外层不滚**（L3 布局 A 整体不滚是首选形态）③ 动作区仍贴底。
- [ ] **Step 8** 四图（slug `02-game`）；标签带里写明「稿子上那段解释为什么不画胜率曲线的话是旁注，不上线」。
- [ ] **Step 9** 双构建 + 提交 + **等 Fan 确认四图**。

---

### Task 11 修订（2026-08-22，做完之后回填）

**做到了**：`/kiosk/play/ai/game` 整屏按新稿重画成 §11 布局 A。真浏览器实测:
盘 **516×516@(16,70)**、落子区 **460×460@(44,98)**、右栏 **460@x548**、页控条 **460×44@y70**、
返回键 **36** —— 规范给的数一次全中。右栏那本账也对上了:
44 + 60 + 60 + **128**(胜率块,30 + 96 **+ 2 描边**)+ 40 + 111 + 5×12 = **503**,余 13。
(计划里写的 126 少算了折叠块上下各 1px 的描边;稿子那本账写的 128 是对的。)

**屏号**:计划里叫「屏 02」,那是十屏稿的编号。稿子 8-21 扩到 27 屏后这一屏是 **05**
(`sample-go/shots/05-game.png`)。文件名跟参考图走:`kiosk-screen-05-game*.spec.ts`、四图 slug `05-game`。

**九处与原文不同,都是动手时才拿到的事实:**

1. **盘没有换成 `GoBoardSvg`,而是给共享 `Board` 加了一个默认 `false` 的 `externalRulers`。**
   计划 Step 3 写的是「`.kiosk-board__play` 里放 `GoBoardSvg`」—— 那会把**触屏落子、领地热力图、
   AI 候选点、变化图、手数、最后一手、ghost stone** 一起丢掉(约 500 行共享逻辑),
   为了一块画得更像的盘。⇒ 反过来:让共享 `Board` 能长在 460 的落子区里。
   打开这个开关**三件事一起变,少一件就白改**:留白 1.5 → **0.5 格**、容器 `padding:4px` + `min−8` → **0**、
   格距 `Math.floor` → **不取整**;外加盘内不再画坐标(那是外面四条带的活)。
   三条**逐条变异验过**,刻度对齐闸分别红在 **21.4px / 数不出 19 条线 / 2.4px**。
   默认 `false` ⇒ galaxy / ZenMode / 复盘一个字节不变。

2. **刻度对齐的判据是「从 canvas 像素里读出来的竖线横坐标」**,不是「字心应该落在 (i+0.5)/19」。
   后者是版式规则,拿它当判据会「数字漂亮、结论全假」(象棋踩过)。实测最大错开 **0.98px**。

3. **`.kiosk-board` 的木框、四条刻度带轨道等分、`.gob` 那一组,从 `kioskSetupBoard.css` 搬进了
   `go-screens.css`**,`kioskSetupBoard.css` 整个删掉。理由:这几条对**每一块围棋盘**都成立,
   留在开局屏那个类下面,第二块盘进来就得抄第二份 —— 两处载荷、改一处不报错。
   选择器带一层 `.kiosk-board`(0,2,0 > tokens 的 0,1,0):组件级 CSS 与 `go-screens.css` 的
   相对顺序 Vite 不保证,**同特异性时靠顺序赢是赌**。

4. **`KioskSetupBoard` 顺手改成用 `GoBoardSvg`**,少了 40 行重复的画线代码,也拆掉了它那颗
   写死的 `id="kiosk-setup-board-wood"` —— 规范 §13① 那颗雷(计划里记的是「Task 11 出现第二块盘时再说」,
   就是现在)。

5. **`tokens.css` 从上游同步了一版**(`.kiosk-actions button.danger` + `:disabled`,上游 8-22 补的),
   `MANIFEST.sha256` 跟着更新,**290/290 校验通过**。⇒ D7 说的「写进 `go-screens.css`
   并按屏限定作用域」不做了:共享包里已经有了,再写一份就是第 3 条那个毛病。

6. **`GameControlPanel` 返回的是 Fragment,不是一个包住一切的 `<div>`。**
   这些块必须是 `.kiosk-rail` 的**直接子元素**,否则 `.kiosk-rail .kiosk-actions { margin-top:auto }`
   选不中,「动作区永远贴右栏底」当场失效。变异验过:去掉那条规则,动作区底 586 → **573**。

7. **着法导航六个键 → 终局后才渲染的四个键(`.kiosk-movenav`)。**
   它们原来 `disabled={!isGameOver}`,对局中全程是灰的 —— 稿子的判词是「不是在这一屏塞一排点不动的键」。
   终局时反过来:悔棋/停一手/认输/数子那四个全变死键,整组撤掉,位置让给真能用的导航。
   **`±10 手` 那两个键没了**(`.kiosk-movenav` 是 4 列,Phosphor 里也没有对应图标),登记为欠账。

8. **顶条那三颗常亮状态灯(摄像头/标定/LED)撤了,但信号没撤。**
   §5 说状态显示归 L1 镜像栏,L3 上没它们的位置;可 **LED 掉线在这一屏原来只有那颗灯说得出来**。
   ⇒ 改成「只在真出故障时说一句」,落在显示开关排右端那格 `.ghint`(它本来就是解释「为什么那个键是灰的」的位置),
   平时不占地方,故障优先于「数子还差几手」。`GamePageLedBadge.test.tsx` 跟着改判据。
   顺带:**「重置识别」不再需要先卡住 10 秒才出现** —— 它现在是页控条上那个唯一的页级图标键(§11),
   实体模式下常驻;`stuckEligible` + `syncStuck` 那套计时器整个删了。

9. **`.items` 角标的 `—` 曾经渲成空。** 原写法 `engineItemCounts ? engineItemCounts.area : null`,
   而接口回 `{}` 时对象**是真值**、`.area` 是 `undefined`,`undefined === null` 为假 ⇒ React 渲成空。
   「没取到数」和「这一格不存在」在屏上长得一样。改成 `?? null`,浏览器闸里钉死三个 `—`。

**同一个组件顺带覆盖了屏 10(星阵人机)。** `GamePage engineMode` 和自由对弈是**同一个 `GamePage`**,
右栏内容不同、骨架相同 ⇒ 改一屏必然动另一屏,**只量一屏等于只证了一半**。所以浏览器闸里两屏各量一遍
(道具键在 / 胜率块不在 / 动作区贴底 / 不滚)。

**没做、已登记:**

- **`.plat` 平台条(稿子屏 10 顶上那一条)**:`PlatformBadge.tsx` 现在**零消费者**,
  而它要的 `connected` / `latency` 没有任何地方喂 —— 造一条出来就是假数据。
- **`棋谱` 折叠块(稿子屏 10 那块 `.mvrows`)**:`GameState.history` 里**只有 `node_id/score/winrate`,
  没有坐标**;`stones` 有 `moveNumber` 但**被提掉的子就不在里面了**,拿它拼出来的棋谱会缺手。
  ⇒ 要么后端加一个着法序列,要么不画。CSS 先写着(`.mvrows` / `.plat` / `.items` 都在 `go-screens.css`),
  接口一到就能接。
- **`analysisToggles.score` 默认 `true`** —— 默认状态下每手触发一次 `analyze_current`。
  规范 §8 那句「默认关」四家一家都没实现。**是产品决定,等 Fan 定**,本轮没动。
- **`AI 支招` 在纯触屏模式下永远是灰的**(`hintVisible` 与 `isVisionEnabled` 相与)。
  实体盘白闪引导确实要摄像头,但 `HintPanel` 在屏上也能显示 —— 这条限制是既有的,不在本 Task 改。
- **`internalToRank` 那句「Fallback if it's already a rank string like "20k"」从来没生效过**:
  `parseInt('5k', 10)` = 5 不是 NaN,于是 `'5k'` 被画成「**5 段**」。后端给的一直是数值
  (`base_katrain.py:178`),所以那个坑**休眠**;但拿字符串造 fixture 会把它叫醒 —— 本轮四图第一版
  就画错了。fixture 已改成内部数值(−4 = 5 级)。共享 `rankUtils` 没动。
- **`kiosk-shell-contract.spec.ts` 的 MUI 图标名单一次摘掉四条**,其中 `SubPageBar` / `PlayPage` /
  `VisionSetupPage` 三条**在本 Task 之前就已经清干净了** —— 也就是**这条闸从 Task 8 之后就一直是红的**
  (它是 `toEqual` 双向棘轮,名单只许缩、缩了不改名单一样红)。「上一轮全绿」那句话在这一条上不成立。

**基线 diff(新增失败只能这么得到)**:整套 Playwright 在 HEAD 上跑一遍,**失败集合与改动后逐条相同,21 条**
(auth / console / diagnose / integration / interaction / smoke / tutorial×3 / tutorial-kiosk×3 /
report-kiosk×2 / galaxy-active-game×3 / ladder-geometry / kiosk-shell-contract)。
⇒ 本 Task **零新增失败**,并且修好了其中一条(图标名单)。
单测 `1 failed | 1304 passed`,那一条红是既有基线(`GamePageEngine` 认输那条,断言写在 await 之前)。

---

### Task 11 追补（2026-08-22 下午，Fan 看完对照台之后）

**三条,都做完了。**

1. **对照台的滑块和视图切换全是死的。** 根因不是 CSS:那份内联脚本里写了
   `const top = document.getElementById('topLayer')` —— `window.top` 是
   `[[Configurable]]: false` 的**受限全局属性**,经典脚本的全局作用域里同名词法声明
   直接抛 `SyntaxError: Identifier 'top' has already been declared`,**整份 script 一行都不执行**。
   表现是「拉了没反应」,而其实上面那排「参考 / 实现 / 并排 / 差异」也一起是死的。
   真浏览器验过两遍:改之前 `pageerrors` 里就是那句、clip-path 卡在 50%;改之后 50% → 80%。
   ⚠️ **Task 10 那份对照台是同一份模板,同一个 bug** —— 一起修了。

2. **坐标 / 手数改成开关**(Fan:「galaxy 界面里都是开关这种形式」)。稿子和实现一起改。
   语义 `aria-pressed` → `role="switch"` + `aria-checked` —— 前者说的是「按钮此刻被按住」,
   而这两个是**状态**:开着就一直开着,没有「发生」。
   **做成修饰类 `.gtoggles--switch`,没有直接改 `.gtoggles`。** 第一版直接改了,
   当场把稿子的直播屏和复盘屏画坏:那两排里的「试下」「AI 推荐」「跟到最新」不是开关,
   是动作和模式 —— 是重新取图时那两张参考图跟着变了才发现的(收成修饰类后逐像素回到原样)。
   闸落在**屏上那颗珠子挪没挪**,不落在类名或 `aria-checked` 上;变异过。
   点击那条要等 .12s 过渡落定再读 —— 不等会在**没有缺陷**时红(实测读到半路的 `matrix(…,9.6,-7)`)。

3. **可点击原型每屏标出实现进度**,并把标题从「二十八屏」补回二十七
   (2026-08-21 删掉对局历史那一屏时,gate 数的是 27、画廊标题写的是 28,**两边各说各的**)。
   三态:已按稿重画 3 / 外壳已接 23 / 还没有那一屏 1。几屏是**数出来的**,数不对当场看得见。

**顺带修了一条既有的偶发红**:`kiosk-shell-geometry` 的 `box()` 只等到 `.kiosk-screen`(外壳),
路由里的元素在并发跑满时可能还没挂上 —— 41 条里偶发红 1 条(「没有这个元素: .kiosk-pagebar」),
单独重跑就绿。补 `waitForSelector(state: 'attached')`,**仍然不用默认的 `'visible'`**:
画布塌成 0×0 时元素照旧在 DOM 里,默认值会把「量出来是 0」糊成一条 30 秒超时 ——
那正是这个文件要防的头号故障。补完连跑三遍 16/16。

提交:katrain `cfacdb2b`;smartbox-software `4b7fcb887`(开关)+ `15dcbb23f`(原型进度带)。

---

## Task 12: 屏 03 · 训练营 `/kiosk/tsumego`

**设计稿**：`go-kiosk.tmpl.html:313-359`（L1-A，形态 1）。**现状**：`pages/TsumegoPage.tsx`（213 行）。

**左栏**：标题同 01；盘画一道题的题面（`data-b="C5,B4,E5,F4" data-w="C4,E4" data-ghost="D4"`，实现里换成**真的当前题**）；同步行 `题目已摆上实体盘` / `等你落子`；三格同 01。

**右栏**：

| 块 | 内容 |
|---|---|
| 问候行 | `今天练点<i>什么</i>` + `题在实体盘上摆好，落子即判` |
| 接着上次 60 | `接着上次` + `15 级 · 吃子 · 第 1 单元` + 药丸 `继续`。无进度时整块不渲染 |
| 按分类 | 组标题 `按分类` / `By category` / secval `六类，是题库自己的分法`；**6 张卡** `死活`(`puzzle-piece`)`做活 / 杀棋`、`手筋`(`hand-pointing`)`局部那一手妙手`、`对杀`(`users`)`两块棋比气`、`吃子`(`grid-nine`)`怎么把子吃下来`、`官子`(`squares-four`)`收官那几目`、`布局`(`crown-simple`)`开局怎么占` |
| 按级别 | 组标题 `按级别` / `By level` / secval `15 级 → 7 段`；**6 张进度环卡** `15 级`/`最容易的一档`、`10 级`/`会吃子之后`、`5 级`/`要算清几步`、`1 级`/`业余中段前的坎`、`3 段`/`长手数死活`、`7 段`/`最难的一档` |

⚠️ **环里写「—」不写数字**，这是 G8 那条：题库（`data/life-n-death` 那批 SGF）**不在仓库里**，级别有哪几档、每档几道题都要问 `/api/v1/tsumego/levels`。**稿子上不写死任何一个题量，写了就是编。** 排序口径倒是代码里写死的：**级越大越弱、段越大越强**（15 级 → 1 级 → 1 段 → 7 段），所以那一排是从易到难。

**训练营的「每日一题」**：规范 §5 要求写 `今日 0 / 2`（本地题库 + Lichess 各一道）。**围棋稿这一屏没画每日一题**，围棋也没有 Lichess 等价物。规范同一条写着：**只有一个来源时不写分母**。⇒ **本轮不加这一块**（稿子没画 = 没有参照物 = 不发明）。登记。

**两处 `.note` 都是旁注**（`:339` 六个分类是题库自带标签、`:349` 环里写「—」的理由），不搬。

- [ ] Step 1–10 同 Task 10 的七步；四图 slug `03-training`；单测跑 `src/kiosk/__tests__/TsumegoPage.test.tsx`（10 条）。
- [ ] 承重：级别那一排造成 12 档，量整栏滚 + 露一半。

---

### Task 12 修订（2026-08-22，做完之后回填）

⚠️ **屏号是 11 不是 03。** 计划书这一屏写作「屏 03」，那是 2026-08-20 那份**十屏**稿的编号；
稿子 2026-08-21 扩到 27 屏之后，训练营成了第 11 屏（`shots/11-training.png`）。
**参考图的文件名是唯一不会漂的锚**，四图 slug 和 spec 文件名一律跟它走。
往下的对照（计划号 → 稿子号）：Task 13 屏 04 → **12**，Task 14 屏 05 → **14**（稿子在 13 补了一层
「题目列表」，计划里没有这个 Task），Task 15 屏 06 → **15**，Task 16 屏 07 → **19 / 20**，
Task 17 屏 09 → **23**，Task 18 屏 10 → **27**。

**九处偏离稿子，全部有依据：**

1. **镜像栏画的还是压暗空盘 + 「识别的盘面还没接进来 / 暂不可用」**，不是稿子那道摆好的题。
   `GoConsoleRail` 四个 L1 屏共用一份，识别结果一天没接进来，四屏就一天都该这么说。
   稿子给每屏写了不同的同步行（这屏是「题目已摆上实体盘 / 等你落子」），那是**接通之后**的话。
2. **「按分类」画哪几类由 `/levels` 说了算**，不是写死六张。后端 `TsumegoProblem.category` 是
   自由字符串（`sync_tsumego_db.py` 从 SGF 注释里解析），六个 slug 只是**今天**的取值。
   `CATEGORY_META` 只负责给已知 key 配中文名/图标/说明；表外的 key 照画，标题退回原始 key、
   副标写题量。次序按稿子那六张排，表外的排最后。
3. **「按分类」是有级别作用域的**，因为路由是级别在前（`tsumego/:level/:category`）。
   取 `readLastLevel()`，没有就取最弱那档。组标题右端写明是哪一档（`15 级 · 6 类`）——
   稿子那句 `六类，是题库自己的分法` 是解释不是数据，`.secval` 的位置按规范放数据（G5）。
4. **`is-current` 需要一个「上次那一类」，仓库里原来没有** ⇒ 加 `LAST_CATEGORY_KEY`，
   由 `TsumegoProblemPage` 在写 `writeLastLevel` 的同一个 effect 里一起写。
   和级别那个一样是**指针不是进度**——它说「你上次做的是这一类」，不说「你做完了多少」。
5. **「按级别」画的是后端返回的每一档，不是稿子挑的六个代表**；副标写 `{total} 题`（真数据），
   不是稿子逐档手写的「最容易的一档 / 会吃子之后 / …」——档数是变的，写不出来也不该现编。
6. **环恒为 `null`（屏上写「—」）**。每档做完没做完要按级取回该级全部题号才算得出，
   那是 R2/§3.5 当年明确不做的事。**这和单元列表屏的 `0%` 不是一回事**（那边进度真存在
   `/api/v1/tsumego/progress` 里），两屏的差别不许抹平。
   读屏的可及名补了「进度未知」——「—」是纯视觉，只报「15 级，1164 题」等于漏掉了结论。
7. **加载 / 读不到 / 真的没有三态各说各的话**，用稿子自己的 `.empty` 构造（`go-kiosk.tmpl.html:424-427`，
   已搬进 `go-screens.css`）：加载只有标题没有结论；读不到写出原因**并且给一个真能再试的键**
   （单测点它、断言第二次请求发出且卡出来了，否则「重试」只是装饰）；真的没有说清楚东西从哪来。
8. **不加「每日一题」**（规范 §5 对训练营的要求）：稿子没画，围棋也没有第二个题源，
   后端更没有这个接口。登记，见下面第 ⑨ 条——它和「露一半」那条撞在一起了。
9. **稿子上两段 `.note` 是旁注，不搬**（分类标签的来源、环里为什么写「—」）。

**承重（真浏览器 1024×600 量的，`.kiosk-side__scroll` 底边 y=504）：**

- 右栏恒 680、滚动条绝对定位不占宽、拇指 ≥24、真滚轮 `data-at` 走 top→mid→end —— 12 档时全绿。
- 空态那一块装得下 ⇒ **不写 `data-at`、不画滚动条**（挂一条永远亮着的渐隐 = 谎报下面还有东西）。
- ⚠️ **§5「露一半」两个数据态都不合规，根因在设计稿：**
    · 有「接着上次」→ 卡行 424..500，底边落在 500..510 那条 10px 的缝里（**离上一张 4**）——
      规范点名「切在缝上」是**最坏的一种**；
    · 没有「接着上次」→ 卡行 442..518，**露 62** / 卡高 76（上界 57）。
  **根因是量出来的**：把稿子 `data-screen="training"` 那两段 `.note`（共 **41px**）`hidden` 掉重跑
  稿子自己的闸，它当场报 `FAIL [training] §5 露一半 ← 正好切在缝上,底下那条完全没露(离上一张 4)`。
  ⇒ **这一屏的合规是靠一段按 G5 永远不会上线的散文撑着的。**
  ⇒ **2026-08-22 Fan 裁：改规范，不加内容**（见下面「Task 12 追补」）。这条从硬性降成建议，
  两边的闸都拆了；当时那条 `test.fail()` 只活了半天。
  ⚠️ 留一条它教的：`test.fail()` **写在文件作用域会套住后面每一条** —— 实测把五条真闸一起
  标成「预期失败」，整份文件只剩这一条「过」。要标必须写在用例体里。

**契约棘轮往下走两格**：`TsumegoPage.tsx` 从视口单位名单（`height:'50vh'` 的加载转圈）和
MUI 图标名单（`ArrowForward`）里一起划掉。**名单只许缩，缩了不改名单一样红。**

**单测整份换过**（13 → 14 条）：上一版断的是 `死活题 / 选择难度级别 / 15K / 手筋: 139`，
那是 MUI 卡片时代的标题栏和分类计数条，稿子上没有这两样。上一版 fixture 的分类键写的是**中文**
（`{ '手筋': 139 }`）—— 后端存的是英文 slug，**那份 fixture 描述的是一个不存在的后端**，一并改掉
（`navigation.integration.test.tsx` 里那两处同病）。两条主判据变异过：
把作用域改成恒取第一档 ⇒ 红 3 条；把 `ring={null}` 改成 `ring={0}` ⇒ 红 1 条。

**基线 diff**：改动后全量 Playwright 20 红 / 123 绿；退回 HEAD 重新构建、跑同一批 spec 文件，
红的**名字集合完全相同**（`comm` 逐条比过）⇒ **零新增失败**。跑全量会重写已提交的视觉存档
（galaxy 的 `reference.png` 也在内），已全部还原。

四图：`superpowers/tracks/kiosk-go-shell-align/visual/11-training/1024x600/`，
`both=25893 refOnly=24975 implOnly=11416`。

---

### Task 12 追补（2026-08-22 晚，Fan 裁完两条之后）

**Fan 裁了两条，都执行完了。**

**① 「露一半」从硬性降成建议**（规范 v1.33，`kiosk-shell-spec.md` §5.3）。
我给的三条里他选了「改规范」，理由写全在规范里：

1. **切口位置不是设计能选的。** 它 =（问候行 56 + 继续条 60 + 组标题 20 + 间距 8/6 + 卡 76 或行 52 …）
   对卡距取模，而这些高度全是共享外壳钉死的节奏 —— 想挪进窗口只能改壳的行高，**波及四家**。
2. **实现侧挑哪个 fixture 就等于挑结论**（训练营两态：缝上 / 露 62），那不是闸。
3. **它原来的「全过」是散文撑的** —— 见 ②。

共享闸 `scripts/screen-gate.mjs` 里那条 `add()` 换成 `note()`：**只打 `INFO` 行、不计红绿**。
没有做成「宽容的断言」—— 一条永远绿的 `add()` 是睡着的闸，会让人以为有东西在守；
`INFO` 明说自己不判断，数还在，判断交给看稿的人。katrain 这边那条 `test.fail()` 直接删掉，
理由写进 `kiosk-shell-scroll.spec.ts` 的文件头，**并写明「不要把它加回来」**。

**② 稿子上剩下的 26 段旁注全部收进 HTML 注释**（Fan：「要」）。分布在 13 屏，
按 v1.30 那次的成例搬进每屏的头注释里，一个字没丢。**这一步当场证实了上面第 3 条**：
重跑稿子自己那道闸，**六屏一起变红** —— 在线大厅 / 跨平台连接 / 训练营 / 棋谱 / 复盘 / 课程。

**顺带修的一处，是删字才暴露出来的**：屏 12 单元列表底下空出 **100px**
（`无空带` 那条闸抓的，不是「露一半」）。原因是稿子只画了 3 个单元当形状示意，
而 15 级·吃子 630 题 ⇒ **32 个单元**。改成画 9 个（三行）——
**不是为了填满，是原来那 3 个不像真的**：真数据下这一屏本来就该溢出、该出滚动条。

结果：围棋 **742 条断言全过 · 14 条观测**（8 ✓ / 6 ✗，✗ 的六屏就是上面那六屏）。
另外三家不受影响（象棋 996 全过、五子棋 338 全过、国象只剩 v1.30 就记过的那条
`§9 首选族 ← -apple-system`，根在 `setup-wizard/` 不在稿子）。

四图重取（参考图变了）：`both 25893→28111 · refOnly 24975→20004 · implOnly 11416→9198`。

---

## Task 13: 屏 04 · 单元列表 `/kiosk/tsumego/:level/:category`

**设计稿**：`go-kiosk.tmpl.html:360-399`（**L2 布局 B**，无棋盘 ⇒ 页控条通栏 x16，无 Dock）。**现状**：`pages/TsumegoUnitsPage.tsx`（172 行）+ `TsumegoUnitListPage.tsx`（145 行）。

| 块 | 类 | 内容 |
|---|---|---|
| 页控条 44 通栏 | `.kiosk-pagebar` | `← 训练营` / `15 级 · 吃子` / 副标 `落子即判 · 走错当场退回` |
| 数据条 72 | `.kiosk-stats` 3 格 | `20` / `每单元题数 · 当前`；`0` + 小字 `/ 20` / `本单元已做对`；`开` / `做对后自动下一题 · 当前` |
| 继续 60 | `.kiosk-resume` | `开始 · 第 1 单元` + `15 级 · 吃子 · 第 1 题` + 药丸 `开始` |
| 单元 | 组标题 `单元` / `Units` / secval `每 20 题一单元`；进度环卡，`第 1 单元` `第 1 – 20 题`… | **一排几张是变的**（要看这一级这一类到底有多少题），稿子画三个只是给出形状 |
| 整级一起做 | 组标题 `整级一起做` / `Whole level`；2 张卡 `15 级全部`(`squares-four`)`六类混在一起，不分单元`、`只做错过的`(`arrow-clockwise`)`把做错的重来一遍` |

**数据条的口径规则**：值自带分母时（`0 / 20`）**就不必再在标签里写时间窗**——分母本身就是口径。

⚠️ 环里写 `0%` **是对的**（和屏 03 的「—」不同）：做题进度**真存下来**在 `/api/v1/tsumego/progress`，换台盒子登录也还在。所以 `0%` = 「真的一道没做」，不是「读不到」。**这两屏的差别不许抹平。**

**规范 §12 那条「已掌握必须写明判据」**：稿子这一屏没写。**不加**（G7 文案冻结 + 稿子没画）。登记为「规范要求但稿子没画」的一条，交 Fan。

**两处 `.note` 都是旁注**（`:387` UNIT_SIZE 与进度的来源、`:396` 整级混做和按单元做是两条并列的路子）。

- [ ] Step 1–10 同上；四图 slug `04-units`；承重：单元造成 11 个，量通栏滚 + 露一半（列表行高 40 的上下界是 [16, 29]，**不是模式卡那个 [19,57]**——不能拿一个 16px 常数套两种高度）。

---

### Task 13 修订（2026-08-22，做完之后回填）

⚠️ **屏号是 12 不是 04。** 四图 slug 跟参考图文件名走（`shots/12-units.png`）。
**只做了屏 12。** 稿子 2026-08-21 在中间补了一屏「题目列表」（屏 13 = `TsumegoUnitListPage`），
计划书里没有对应的 Task —— 那一屏单独排，不并进这一轮。

**这一屏是本仓第一个真的走 L2 布局 B 的屏**（跨平台那几屏还是手搓的 `<Box>`）：
`.kiosk-layout-b` 补在 `go-screens.css`（**该提上游** —— 四家的无盘页都是这个形状），
**里面不写死任何高度**，滚动区吃剩余空间。承重闸写成关系式：
`70 + 44(页控条) + 12 + 460 = 586`，且滚动区通栏 992。
⚠️ 闸的第一版拿 `.kiosk-content` 的 **border box** 去比，红在 `600 ≠ 586` ——
那是**闸量错了对象**（border box 一路到画布下缘，上下各 14 的内边距才是能用的 70..586），
改成量 padding box。把 gap 12 改成 16 变异过，当场红。

**几处口径：**

1. **环里写真 `0%`**，不是屏 11 的「—」。这一层为了 prev/next 契约本来就把整类题号取回来了，
   所以每个单元做完几道**算得出来** ⇒ `0%` = 真的一道没做。**两屏的差别不许抹平。**
2. **「当前单元」= 第一个没做完的**，不是恒定的第 1 单元；全做完了指最后一个
   （**不许指向一个不存在的单元**）。数据条第二格、开始条、`is-current` 三处同一个来源。
3. **「只做错过的」标成「还没接」，但副标写真数。** 这个集合算得出来
   （本地进度里 `attempts > 0 && !completed`），**但没有地方去**：后端没有按错题筛的接口，
   前端也没有一条只播这批题的路由 —— 做题屏的上/下一题读的是 `sessionStorage` 里那条
   **整类**的顺序表，塞一份筛过的进去会把正常的上下一题弄坏。§14：后端没有的块要标出来，不是藏起来。
4. **`第 1-20 题` 用的是 galaxy 也在用的 `tsumego:problemRange`**，所以是 PO 里那个写法，
   不是稿子上的 `第 1 – 20 题`（多两个空格、破折号不同）。**两处口径统一比对上稿子的破折号要紧。**

---

### ⚠️ Task 13 抓到的那个 bug：`t()` 的占位符约定

**四图对比抓到的，单测全绿。** 卡片写成 `t('tsumego:unit', '第 {n} 单元').replace('{n}', …)`，
而 `tsumego:unit` 在 cn PO 里是 **`单元`**（galaxy 三处在用）。`t()` 是
`translations[key] || defaultText` —— **翻译表赢**，于是 `.replace` 找不到东西可换，
**数字连同占位符一起没了**，屏上只剩「单元」。同一次的另一半：
`t('tsumego:problemRange', '第 {a} – {b} 题')` —— PO 里那条的占位符叫 `{start}/{end}`，
于是 `第 {start}-{end} 题` **原样上了屏**。

**单测为什么抓不到**：jsdom 里翻译表没加载，`t()` 恒返回默认值，
而默认值里的占位符名当然和我自己写的 `.replace` 对得上 ——
**断言断的是「我自己和我自己一致」**。

**两半表现相反，所以补两条闸：**

| 表现 | 闸 | 判据 |
|---|---|---|
| 花括号原样上屏 | `tests/kiosk-copy-placeholders.spec.ts` | 真浏览器 + 真翻译表扫 `innerText`，不许有 `{word}` |
| 数字连同占位符消失 | `kiosk-shell-contract.spec.ts` 闸三 | 源码里 `t(key, 默认值)` 的占位符集合 == cn PO 里那条的 |

**只有前一条时杀不死变异**（实测）：把 `unit_n` 改回 `unit`，屏上是「单元」，一个花括号都没有。
闸三扫源码前**先剥注释** —— 第一版指着这条闸自己的说明里举的反例说「你这儿写错了」，
**闸把文档当成了代码**。

**闸三一上来就抓到另外两处既有的同类 bug**（都不在本轮改的屏上，都是用户看得见的乱码文字）：

- `ReportsPage` `t('report:no_match', '没有匹配的棋谱')` ←→ PO `没有找到与 "{query}" 匹配的棋局。`
  ⇒ 搜不到结果时屏上印着一个字面的 `{query}`。已修（`query` 就在作用域里）。
- `ResearchPage` `t('research:progress', '进度')` ←→ PO `已完成 {analyzed} / {total} 步`
  ⇒ 那是**一整句**，被当成一个 StatBlock 的标签用了。已改成自己的 key。

`interpolate` 因此从 `pages/tsumegoUnits.ts` 挪到 `utils/interpolate.ts`（两个模块都要用），
**没匹配上的占位符原样留在屏上** —— 静默吞掉会让「拿错 msgid」变成一句读起来通顺的假话。

**登记（i18n 债）**：新加的 kiosk key `tsumego:unit_n` / `tsumego:unit_size` / `tsumego:problem_no`
/ `tsumego:wrong_now` / `tsumego:category_unit` / `research:progress_label` 只有中文兜底，
**还没进 PO**（要走 katrain-i18n-expert，11 种语言一起）。

**基线 diff**：全量 Playwright 20 红 / 128 绿，与 Task 12 前那次退回 HEAD 跑出来的红**名字集合完全相同**
⇒ 零新增失败。四图 `both=17777 refOnly=16923 implOnly=15767`。

---

## Task 13b（计划外补的一屏）: 屏 13 · 题目列表 `/kiosk/tsumego/:level/:category/:unit`

**计划书原来没有这个 Task** —— 稿子 2026-08-21 在单元列表和做题屏之间补了一层
（`data-screen="problems"`，参考图 `shots/13-problems.png`），Task 13 做完时明确排除了它。
这里补记。**现状**：`pages/TsumegoUnitListPage.tsx`（原 140 行 MUI + `ProblemCard` 缩略棋盘）。

| 块 | 类 | 内容 |
|---|---|---|
| 页控条 | `.kiosk-pagebar` | `← 单元` / `15 级 · 吃子 · 第 1 单元` / 副标 `第 1-20 题 · 落子即判` |
| 数据条 | `.kiosk-stats` | `3 / 20 本单元已做对` · `1.7 平均尝试次数` · `22 秒 平均用时` |
| 这 20 道题 | `.qgrid`（新） | 10 列 × 76 高，一格一题：题号 + 试了几次；`ok` / `now` / 无类 |
| 换一批 | `.kiosk-rows` | `整级 → /kiosk/tsumego/:level/all`；`错题` 挂 `.kiosk-wip`，没有键 |

### 三条口径

1. **`attempts` 数的是失败的那几次，不是总次数。** `useTsumegoProblem` 里只在**走错**
   （`:418` / `:440`）和**重摆**（`:618`）时 `+1`，做对那一手不加 ⇒ 一道第一次就做对的题存下来是
   `attempts: 0`。屏上写的是 **`attempts + (做对了 ? 1 : 0)`**，稿子那三格 `1 次 / 1 次 / 3 次`
   正是按这个意思画的。**不换算的话，标签会把「试了几次」讲成「错了几次」——数没错，话变了。**
   「平均尝试次数」走同一个口径。没做过的写「—」，**不写「0 次」**（0 次是一个次数，「没做过」不是）；
   一道没试过时平均值也写「—」，不写 `0.0`。
2. **常路一次接口都不取。** 屏 12 已经把整类题号按顺序写进 `sessionStorage`（prev/next 契约），
   这一层要的东西全在里面 ⇒ 直接读。只有**深链**才自己取一次 `?limit=1000` 并回填。
   旧实现取的是 `?offset&limit=20` 的**整题**（带 `initialBlack/initialWhite` 画缩略棋盘）——
   630 题的类目上这是实打实的省。⇒ `components/tsumego/ProblemCard.tsx` 没有消费方了，
   **连同它在 `tsumego-components.test.tsx` 里那一组断言一起删掉**（galaxy 那份不动）。
3. **「只做错过的」连一个按不动的键都不给。** 屏 12 那张卡是「灰掉 + 标注」，这一行连 `开始`
   都不摆 —— **摆一个灰键等于说「这儿有路，只是暂时走不通」**。挂 §14 的琥珀 `.kiosk-wip`。

### 和稿子的出入（都往「少写小字」那边，Fan 2026-08-22「不要写那么多解释文字」）

| 处 | 稿子 | 实现 | 为什么 |
|---|---|---|---|
| 两条组标题右端 | `点一格直接进那一道` / `同一副骨架，只换题从哪儿来` | 去掉 | `KioskSecLabel` 自己写着那格**是数据不是旁注**；一句是操作说明、一句在讲界面构造 |
| 数据条标签 | `平均尝试次数 · 当前单元` | `平均尝试次数` | **这一屏只有一个单元**，页控条已经写着是第几个；屏 12 留「· 当前」是因为那屏摆着十几个 |
| 错题那行 | `把做错的重来一遍` | `把**这一类**做错的重来一遍` | 上一行是**整级**，scope 在两行之间跳过一次，不点名会被读成整级的数 |
| 平均尝试次数 | `1.6` | `1.7` | `(1+1+3)/3 = 1.667`，四舍五入是 1.7。**数是算出来的，不跟着稿子改** |
| 题号范围 | `第 1 – 20 题` | `第 1-20 题` | 同屏 12：用的是 galaxy 也在用的 `tsumego:problemRange` |

### 两条新承重闸（`kiosk-shell-scroll.spec.ts`）

- **满编 20 格 + 换一批两行必须一屏装得下**。这条断言的是「**不**需要滚」：格高 76 是稿子
  2026-08-21 从 58 调上来的，**那次是拿底下的空带换的**；再有人往上加，20 格就会把「换一批」
  那两行顶到视野之外，而那两行是这一屏**唯一**的两个出口。那时滚动条会照常出现、`data-at`
  照常诚实，三条通用闸**全绿**，人却看不见出口 —— 所以这件事只有在这里说得出来。
  实测底下还空 **48px**（只记录，不作判据）。变异：格高 76 → 110，当场红。
  ⚠️ 第一版拿 `clientHeight - scrollHeight` 当空带 —— `scrollHeight` 有 `clientHeight` 这个下界，
  **那个差永远是 0 或负**，是一条恒等于 0 的假读数。空带只能从最后一行的下缘量。
- **`.qgrid` 10 列铺满通栏 992，页面本体不横向溢出**。横向溢出**在截图上看不出来**
  （格子被裁掉一点点，或者整页能左右拖）。判据写成关系式：第一行正好 10 格、首末两格贴通栏两缘，
  不写死 92。变异：`repeat(10, 1fr)` → `repeat(8, 1fr)`，当场红。

**基线划账**：`TsumegoUnitListPage.tsx` 从 `VIEWPORT_UNIT_BASELINE` 里划掉（`height:'50vh'`
的转圈换成了 `.empty` 三态）。`tests/kiosk-copy-placeholders.spec.ts` 加了这条路由。

**i18n 债**（接着 Task 13 那笔记）：又添 `tsumego:tries_n` / `tsumego:these_n_problems`
/ `tsumego:unit_range`，仍只有中文兜底。⚠️ **另有一笔早就在的**：`tsumego:problem_n` 在 PO 里是
`第{n}题`（无空格），而 Task 13 新造了一个 `tsumego:problem_no`（`第 {n} 题`）—— 两条同义。
合并要连 galaxy 两处一起改，**不在本轮做**。

**登记（不在本轮改）**：稿子那段注释说这副骨架还兼着 `tsumego/:level/all`（整级混做），
但真前端那条路由今天走的是另一个组件 `TsumegoLevelPage`。合不合并是内容不是版式，登记。

---

## Task 14: 屏 05 · 做题屏 `/kiosk/tsumego/problem/:problemId`

**设计稿**：`go-kiosk.tmpl.html:400-438`（**L2 布局 A**）。**现状**：`pages/TsumegoProblemPage.tsx`（588 行）。

| 块 | 类 | 内容 |
|---|---|---|
| 页控条 | `.kiosk-pagebar` | `← 吃子` / `一手叫吃两边` / 副标 `15 级 · 第 1 / 20 题` / 右端 `2D \| 3D` |
| 这一题 | `.panel` + `h3` | **题面正文是真 UI 文案，照搬**（G5）：`<b>黑先。</b>白有两颗子，各剩两口气，而且两颗<b>不连在一起</b>。找出那一个点：…`；下面三个 `.kiosk-tag`：`吃子` `15 级` `示意题面` |
| 你的走法 | `.railsec` + `.rst` | 标题行 `你的走法`，右端 `落子即判`；体是 `.mvrows`，空态一行 `—` / `还没落子` |
| 第 N 单元 | `.panel` | `第 1 单元 · 20 题` + `.dots` 20 个点阵（一个点一道题，颜色就是状态，不需要图例） |
| 动作区 4 格 | `.kiosk-actions` | `提示`(`lightbulb`) `退一手`(`arrow-counter-clockwise`) `重摆`(`arrows-clockwise`) `下一题`(`skip-forward`) |

⚠️ **`示意题面` 那个 tag 不要照搬** —— 它标的是「这道题是稿子上现摆的，不是题库里的」。真实现里题目**来自题库**，挂这个标就是撒谎。**去掉它**，只留 `吃子` `15 级` 两个。这一条要写进提交信息。

**最后那块 `.panel` 里的 `.note` 是旁注**（`:428`「这道题是我在稿子上现摆的…解完之后才提一次它的名字：双打吃」），不搬。⚠️ 但它里面有一条**产品规则**要保住：**入口那一层不出现术语**（「双打吃」这种名字只在解完之后出现一次）。现状是不是这样，要核；不是的话**不在本轮改**（那是内容不是版式），登记。

- [ ] Step 1–10 同上；四图 slug `05-puzzle`；几何同 Task 11 的布局 A 那一组。

---

### Task 14 修订（2026-08-22，做完之后回填）

⚠️ **屏号是 14 不是 05**，四图 slug `14-puzzle`。

### ⚠️ 计划里那张块表有一条是错的：**题库里没有「题面」**

计划写着「题面正文是真 UI 文案，照搬（G5）」。**实测不成立。**
`TsumegoProblem` 的列只有 `id / level / category / hint(String(16)) / board_size /
initial_black / initial_white / sgf_content / source` —— `hint` 那一列的注释逐字写着
`# "黑先", "白先"`。**没有标题，也没有一段讲人话的题面。**
稿子上那段「黑先。白有两颗子……」和页控条上的「一手叫吃两边」都是**画稿时手写的**
（稿子自己的注释就写着这句）。⇒ **两样都不搬，也不编** —— 搬过来就是生产代码里的假业务数据。

屏上因此只写得出 `hint` 那一句 + 这一屏自己的规则（落子即判、走错当场退回）。
稿子第三个标签 `示意题面` 照计划去掉（它标的是「这题是稿子上现摆的」，真题来自题库）。

**G5 那条判据本身没错，错的是我把它套在了一段「查过就知道后端没有」的文字上。**
判据要补一句：**先问这段话在数据里有没有对应的列，再问它是说给谁听的。**

### 稿子没画、而真前端一直有的四样，各自找了位置

| 功能 | 位置 | 为什么 |
|---|---|---|
| 上一题 | 动作区第 4 格（**五个键一排**，格子一样大） | 稿子四个键里没有它，而它和「下一题」是一对 |
| 试下 | 开关排 `role="switch"` | 原来是「试下 / 退出试下」两个轮流出现的按钮 —— **那本来就是一个开关的两半** |
| 实体棋盘 | 同一排开关 | Fan 2026-08-22：「galaxy 界面里都是开关这种形式，kiosk 也改成一样的」。`PhysicalModeToggle.tsx` 整个删掉 |
| 实体模式的阶段引导 | **换掉**「你的走法」那一块的内容 | 见下 |

**实体引导是「换」不是「加」。** 右栏 516 是死的；加一块就会把动作区顶出右栏，
而它贴底靠 `margin-top: auto` —— 顶出去之后键还在 DOM 里、手指够不到。
而且两者本来就是同一个问题的两种答案（「现在轮到我做什么」），换内容是对的。

### 四图对比抓到两个 bug，两条都不是这一屏独有的

1. **`t('Undo', '退一手')` 屏上写的是「悔棋」。** cn PO 里 `Undo` 就是「悔棋」，
   而 `t()` 是 `translations[key] || defaultText` —— **翻译表赢**。同一次还有两处：
   `tsumego:practiceProblems` 在 PO 里是一整句「练习死活题以提高计算能力」，被当页控条标题用；
   `tsumego:loadError` 是一句话，被当 `<h4>` 标题用。三处都换了自己的 key。
   ⇒ 补 **`kiosk-shell-contract.spec.ts` 闸四**：`t(key, 中文默认值)` 里默认值和 PO 里那条
   **都是中文且不相等**就红。和闸三是同一个病的两种症状（闸三管占位符，这条管词本身）。
   名单 77 条是实测存量，一条都不是本轮引入的。变异：把 `undoMove` 改回 `Undo`，当场红。
2. **盘上的线和外壳刻度带的字对不上（错开 11.9px）。** `TsumegoBoard` 按 **1.5 格边距**画
   （那是给盘面里**自己那圈坐标**留的位置），而 kiosk 布局 A 的坐标交给外壳画 ⇒
   线的节距 `W/(N−1+3)`、刻度带 `W/N`，**两者不等**；再加上 `Math.floor(gridSize)`
   和 4px 内边距，头尾各偏 ~6px。
   ⇒ 给组件加一个 `showCoordinates`（默认 `true`，galaxy 行为一字节不变）；为 `false` 时
   边距收到 0.5、不 floor、不留内边距。**这三处是同一条不变式的三个破口**。

### 两条新承重闸（`kiosk-shell-geometry.spec.ts`）

- **盘上第一条 / 最后一条竖线，正对刻度带头尾两个字。** `go-screens.css` 早就把这条写成了
  不变式，还写明**判据是屏上那条线的横坐标**——但一直没有闸。线画在 canvas 上、DOM 问不出来，
  所以**直接读像素**：横切一条，找最暗的那些列 = 竖线。⚠️ 第一版多数出两条 ——
  木底没铺满整个 canvas（盘宽按格数取整，两侧各余 2px 暗边），那两条暗边被当成了棋盘线。
  变异记录：修之前它就是红的（11.9px），修完 ≤0.5px。
- **着法再多，动作区也贴着右栏底。** ⚠️ 前四条断言（右栏 516、五个键、不溢出、贴底）
  **对 `overflow-y: visible` 免疫** —— 那种写法下每个盒子的矩形一模一样，只是内容糊出去了。
  分得出来的只有「它自己能不能滚」，所以补了一条**真滚轮**。变异实测：改成 `visible`，
  前四条全绿、只有滚轮那条红。

### 登记（不在本轮改）

- **棋盘木色比稿子亮一大截**：`board.png` 是全仓共用的资源（对局屏那块盘同一张），
  换它要连 galaxy 一起换。屏 14 和屏 05 长得一样，这一条**本仓内部是自洽的**。
- `.rst` 右端写的是「用时 0:00」而不是稿子的「落子即判」——「落子即判」挪进了题面那句话里
  （规则只说一遍），右端那格让给**实时数据**（`KioskSecLabel` 的同一条口径：那格是数据）。
- **页控条**：`← 第 1 单元 / 第 1 题 / 15 级 · 吃子`，稿子是 `← 吃子 / 一手叫吃两边 / 15 级 · 第 1 / 20 题`。
  返回落在**屏 13**（这道题所在的那一单元）而不是屏 12 —— 稿子那个画法早于 2026-08-21 补出屏 13。

**i18n 债**（接前两笔）：`tsumego:undoMove` / `loadingTitle` / `problemLoadError` /
`thisProblem` / `yourMoves` / `physicalBoard` / `noMoveYet` / `tries_n` 等仍只有中文兜底。

**基线 diff**：退回 HEAD 跑过一次全量（20 红 / 129 绿），改动后跑了**两次**：
两次都是 **20 条既有红 + 1 条轮换的偶发红**，而且**两次那一条不是同一个**
（第一次 `smoke.test.ts › can play a move`，第二次 `tutorial.spec.ts › Books page…`），
单独重跑都绿。⇒ 零新增失败；那一条是这套 galaxy 用例在满并发下的**既有偶发**，
和本轮改动无关（两条都走 `Board.tsx` / 教程线，本轮一个字节没碰）。已登记。

⚠️ **全量跑会重新生成已提交的视觉档案**（01-play / 05-game / 11-training 的实现图各变
26–141 个像素，纯抗锯齿噪声）。跑完一律 `git checkout --` 还原，不要提交进去。

---

## Task 15: 屏 06 · 棋谱 `/kiosk/kifu`

**设计稿**：`go-kiosk.tmpl.html:439-494`（L1-A，形态 1）。**现状**：`pages/KifuPage.tsx`（413 行）。

**这一屏是三条路由的汇合点**（规范 §3）：原来的 `棋谱 / 摆谱 / 直播` 三个 Dock 项收成一项。Task 4 已经把后两个下了 Dock，**它们的入口就在这一屏**——不接上，那两屏就只能靠输 URL 到达。

**左栏**：标题同 01，但盘画的是**正在摆的那一谱**（`data-ghost="C7"` = 灯指的下一手）；同步行 `正在摆谱 · 下一手 C7` / `灯已点亮`；三格同 01。

**右栏五块**：

| 块 | 内容 | 对应现状 |
|---|---|---|
| 问候行 | `看别人的<i>棋</i>` + `名局、职业直播，以及把谱摆到实体盘上` | `KifuPage` 现在是 `variant="h4"` 标题 |
| 继续摆谱 60 | `继续摆谱` + `上次摆到第 47 手 · 灯会指下一手落在哪` + 药丸 `继续` | **接 `BaipuListPage` 的进度数据** |
| 名局棋谱 | 组标题 secval `按棋手 / 赛事 / 日期搜`；3 张卡 `搜棋谱`(`magnifying-glass`)`一个搜索框，模糊匹配`、`摆到实体盘`(`grid-nine`)`灯一手一手指着摆`、`导入 SGF`(`upload-simple`)`本地文件，离线也能摆` | 「摆到实体盘」→ `/kiosk/baipu` |
| 最近摆过 | 组标题 secval `存在这台盒子上`；`.kiosk-row` 列表，`.kiosk-row__lead` 放 `47 手` / `全谱` / `12 手` | 接 `BaipuListPage` 的最近列表 |
| 棋谱详情 | 组标题 + **琥珀 `.wip 未接后端`** + `.empty` 块：`点进一局是「敬请期待」` | 现状 `kifu/:kifuId` 挂的正是 `PlaceholderPage` —— **稿子说的是实话，照搬** |
| 职业直播 | 组标题 secval `来源：星阵 · 弈客`；`.kiosk-row` 列表 + `.kiosk-tag--live 直播中` | → `/kiosk/live`。**断网时整块不渲染**，不摆一排「加载中」骗人在等 |

**三处 `.note` 全是旁注**（`:462` 搜索是一个框糊搜、`:478` SGF 整份缓存、`:492` 直播和棋谱为什么收在一项里），不搬。

⚠️ **`搜棋谱` 那张卡的行为要照实现，不要照稿子的措辞**：稿子说「接口只收一个 `q`，做成两级筛选后端支持不了」。现状 `KifuPage` 就有搜索。**不要为了对齐稿子的三张卡把现有的搜索框删掉再做成一张卡** —— 那是把能用的功能换成一个入口。做法：三张卡是**入口**，现有搜索框保留在它下面或并入「名局棋谱」组。**摆法有疑问就停下来问。**

- [ ] Step 1–10 同 Task 10 的七步；四图 slug `06-kifu`。
- [ ] 额外一步：**验收「摆谱和直播现在到得了」** —— 从 `/kiosk/kifu` 点得到 `/kiosk/baipu` 和 `/kiosk/live`，写成两条断言。Task 4 埋下的那个中间态到这里销账。

### Task 15 修订（2026-08-22，做完之后回填）

⚠️ **屏号是 15 不是 06**，四图 slug `15-kifu`。稿子行号也变了（`go-kiosk.tmpl.html:1463`）。

### 计划里那张块表的第五块（棋谱详情）**没搬**，而且这是照 G5 判的

那一整块（`.wip have 后端已有 · 界面未接` + `.empty` 里印着 `PlaceholderPage` 和
`galaxy/pages/KifuLibraryPage.tsx` 两个文件名）是**说给读稿人听的进度说明**，
和那三处 `.note` 同类。计划写着「稿子说的是实话，照搬」—— 是实话不等于是 UI。
何况本轮把详情屏接上了（Task 15b），它说的事当场不成立。

### 「搜棋谱」做成开关，不是把能用的搜索换成一个入口

计划已经点过这个雷（「不要为了对齐稿子的三张卡把现有的搜索框删掉再做成一张卡」）。
最后的摆法：**三张卡照稿子画，`搜棋谱` 是个开关** —— 收起时这一组和稿子一样，
按下去搜索框 + 六行结果 + 翻页在这一组里展开，行点进屏 16。
`摆到实体盘` → `/kiosk/baipu`；`导入 SGF` **在本屏直接开文件选择框**
（卡的 `onClick` 就是用户手势，导航之后再 `input.click()` 会被浏览器拦掉），
读到 SGF 就缓存 + 直接进摆谱会话。

⇒ **Task 4 埋的那个中间态在这里销账**：摆谱和直播从这一屏点得到，两条都写成了断言。

### 组标题右端那两个值换成了真数据

稿子写的是「按棋手 / 赛事 / 日期搜」和「来源：星阵 · 弈客」——前者是一句解释，
后者是写死的。规范说 `.secval` 放的是**数据**（G5），所以：
- 名局棋谱 → `共 N 局`。收起时也有 —— 挂载时探一发 `page_size: 1` **只为拿 `total`**，
  不取列表、不渲染行。闸落在**请求的形状**上（`toHaveBeenCalledWith({page:1,page_size:1})`），
  不是「屏上有没有搜索框」：后者在「整页拉回来先不渲染」的写法下一样绿。
- 职业直播 → 按**这一批真的来自哪几家**算。

### 「已摆完」这三个字要两个数才敢说

`BaipuProgress` 原来只存 `k`（摆到第几步），**没有总步数** ⇒ 拿 `k` 判不了摆完没有。
给它加了可选的 `total`，`BaipuSessionPage` 两处 `saveProgress` 一起写上。
**必须留成可选**：2026-08-22 之前写下的进度里没有这个字段，读到 `undefined` 的正确反应是
**不下结论** —— 不出「已摆完」的标。三条用例守三个方向（有 total 且摆完 / 有 total 没摆完 /
根本没有 total）。这是「否定的答复不携带原因」那条的同族。

### 直播那块断网时整块不渲染 —— 照稿子，但代价要写明

稿子原话：「断网时这一块**整块不渲染**，不摆一排『加载中』骗人在等」。照办了。
⚠️ 代价：**「没有直播」和「拉不到」在屏上长得一样**。这是稿子选的口径（7″ 屏上一块
常驻的报错块不值那个位置），**已登记**，不是漏。

### `KioskLayout.RAIL_ROUTES` 少了 `/kiosk/kifu`

稿子的屏 15 是 **L1 布局 A**（左边有镜像栏），而 `RAIL_ROUTES` 只有 play / tsumego ⇒
这一屏原来是通栏 992 的。**是承重闸抓到的**（右栏量出来 992 而不是 680），不是看出来的。
判据（§5：「这个模块的活动会不会发生在实体盘上」）棋谱过得去 —— 靠的就是摆谱。

### 闸四又抓到四条 PO 覆盖（这是它第二次真的挡住东西）

`kifu:library`＝「棋谱库」、`kifu:loading`＝「加载中...」、`kifu:handicap`＝「让子」、
`kifu:records`＝**「条记录」**（galaxy 拿它当量词）。四个 key 我都是当另一个意思用的
（返回键要「棋谱」、标题要「正在读这一局」、要拼「让 2 子」、组标题要「名局棋谱」）——
**PO 赢默认值**，复用就是屏上四处换了词。各自另起了 key。
另外 `KifuPage` 从 `MUI_ICON_BASELINE` 里去掉了（这一屏不再用 MUI 图标）。

### 四图对比抓到的一处几何

`.khero p` 只写了 `margin-top` —— 稿子那份 CSS 自己带全局 reset，**本仓没有**，
于是 UA 的 `margin-bottom: 1em` 在题头底下留了 11.5px，整块 87 高（该 71），
右栏底下每一块跟着往下挪 16px。改成 `margin: 4px 0 0`。

### 新闸

- （scroll）**棋谱：展开搜索之后右栏自己滚，最后一块（职业直播）滚得到。**
  判据不是「有没有滚动条」，是**最后一块滚得到** —— 直播那几行如果永远在视野外，
  Task 4 把它下 Dock 之后就再也到不了了。用真滚轮，不是 `scrollTop = n`。

### 登记（不在本轮改）

- `SOURCE_LABEL`（星阵 / 弈客）在 `components/live/MatchCard.tsx` 和 `MatchInfo.tsx` 里
  已经各有一份，这是**第三处**。没合并是有意的：那两份带着颜色、是 galaxy 卡片的样子，
  合并要动 galaxy 两屏。
- 最近摆过只显示前 6 条，没有「更多」。
- 计划里那句「接 `BaipuListPage` 的进度数据」实际接的是 `baipuApi` 的 localStorage
  （`listRecent` / `getProgress`），`BaipuListPage` 本身没动。

---

## Task 15b: 屏 16 · 棋谱详情 `/kiosk/kifu/:kifuId`（计划外补的一屏）

**计划里没有这个 Task**（Task 15 只到屏 15），和屏 13 一样是稿子后来长出来的一屏。
**做它的直接理由**：屏 15 那张列表点下去总得有个落点；而且不做它，`KifuPage` 原来那半边
（预览 + 逐手 + 「在研究中打开」）就是净损失。**顺序是先 15b 后 15**，这样任何一个提交上
都没有功能回退。做完 `PlaceholderPage.tsx` 成了死代码，删掉。

**设计稿**：`go-kiosk.tmpl.html:1537`（L2 布局 A）。**现状**：路由挂 `PlaceholderPage`。

### 盘不复用 `LiveBoard`，提子不在前端算

`LiveBoard` 会算提子，但它的 `calculateBoardLayout` 写死 **1.5 格**边距，而刻度带要 **0.5**。
对局屏是给共享 `Board` 加 `externalRulers` 解决的 —— 那条路对 `LiveBoard` 也走得通，
但要连 `boardUtils` 一起改，**而这一屏的盘根本不需要能点**。
⇒ 用 `GoBoardSvg`（0.5 由构造保证）+ **`/api/v1/baipu/load` 给的 `removed[]`**。
`baipuApi.ts` 开头那段决策 ② 逐字写着「前端是 `steps[]` 的笨播放器，永远不自己重算提子」——
照办：本页只做「放一颗 → 按给定名单删几颗」，一条围棋规则都不实现。
单测里造了一步带 `removed` 的谱，断言那颗子从盘上没了、退一手又回来。

### 稿子三个动作键，实现两个 —— 「送去复盘」那条路不存在

`POST /api/v1/reports/` 收的是 `user_game_id`，服务端 `endpoints/reports.py:133` 拿它去
`UserGame` 表里查这一局是不是**你下的**；名局棋谱没有这一行。
galaxy 那边的棋谱库（`KifuLibraryPage.tsx`）也**只有**「在研究中打开」一个出口 ——
稿子那句「三个出口对应真前端的三条路」有一条是错的。
**画一个按下去必然报错的键，比少一个键坏。** 用例把这条钉住：多出第三个键就红。

同理稿子右上那枚 `界面未接` 蓝标不搬（接上了就不成立）；题头补了段位（库里真有的列）。

### 新闸（`kiosk-shell-geometry.spec.ts`）

- **SVG 盘的头尾两条竖线正对刻度带头尾两个字。** 和屏 14 那条是**同一条不变式的另一条
  实现路径**（那边是 canvas 读像素，这边 SVG 问 DOM），判据一个字不改。它守的不是
  `GoBoardSvg` 自己算错（0.5 是构造保证的），而是**外面那层**：`__play` 的内边距、
  `preserveAspectRatio` 的居中留白、将来有人给盘加一圈边框。
- **谱再长，动作区也贴右栏底，谱自己滚。** 造 240 手把 `.kiosk-fold__body` 撑破。
  ⚠️ 共享 `.kiosk-fold__body` 是 `overflow: hidden`（它管的是收起时裁掉），
  所以加了 `.kiosk-fold__body.mvrows { overflow-y: auto }` —— **这一行是承重的**。
  变异实测（2026-08-22）：去掉它，前六条盒子断言**全绿**，只有真滚轮那条红。

### 登记

- 总手数写的是这份 fixture 真有的手数，不是稿子那个 241 —— 造一份 241 手的假谱只为让
  角标好看，就是拿假数据充门面。
- 盘的木色比稿子亮（`GoBoardSvg` 走 `go-tokens.css` 的 `--gb-light/--gb-dark`，
  开局设置屏同一份，Fan 已确认过那几屏）—— **本仓内部自洽**，同屏 14 那条债。
- 稿子的木纹贴图仍未抄（D6）。

---

## Task 16: 屏 07 · 复盘 `/kiosk/report`

**设计稿**：`go-kiosk.tmpl.html:495-553`（L1-A，**形态 2：头尾固定 + 中列滚**）。**现状**：`pages/ReportsPage.tsx`（348 行）。

⚠️ **这屏的现状和稿子是左右对调的**：现在是**左盘 54% + 右列表 46%**，稿子是 **296 镜像栏 + 680 内容**。这是本轮改动最大的一屏。

**左栏**（`KioskConsoleRail`，但装的不是实体盘镜像）：标题 `选中这一局` / `Selected`；盘画**选中那一局的终局盘**；同步行 `自由对弈 · KataGo 5 级` / `今天 15:12`；三格是**本局指标**不是硬件状态 —— 见 **D4**，第三格写「妙手」还是「漏着」要先去核后端。

**右栏形态 2**：

| 块 | 类 | 内容 |
|---|---|---|
| 这一局的胜率（**固定**） | `.kiosk-section` + `.kiosk-eval` | 组标题 `这一局的胜率` / `Win rate` + **蓝 `.wip.have 后端已有 · 界面未接`**；纵坐标三档 `白 100 / 50 / 黑 100`，画布 96、刻度带 38 |
| 待复盘对局（**会长，只有它滚**） | `<KioskScrollZone grow head={<KioskSecLabel …/>}>` | 组标题 secval `本机 5 局`；`.kiosk-row` 每行：圆珠 + `vs KataGo · 5 级` + `你(黑)中盘胜 · 187 手 · 今天 15:12` + `.kiosk-tag--win 已分析` / `.kiosk-tag 未分析` |
| 生成报告（**固定**） | `.kiosk-cards` 3 张 | `标准`(`lightbulb`)`每手算 500 次`、`精读`(`magnifying-glass`)`每手算 2000 次 · 慢四倍`、`导入 SGF 复盘`(`upload-simple`, `.is-soon` + `即将上线`)`接口还没有`；组标题 secval `两档：500 / 2000 次计算` |

> **形态 2 是有理由的**：把「生成报告」那三张卡也一起滚走是错的，那是常驻入口。渐隐必须钉在**真正滚的那一块**上，从组标题下缘开始，别盖住标题（`tokens.css:555` 已经处理）。

**规范 §11 四种状态各有各的样子**，现状 `ReportGameCard` 已经有 排队中/生成中/已完成/失败，**对得上**：
| 状态 | 行尾 | 点了会怎样 |
|---|---|---|
| 已分析 | `准确率 NN%` + 「查看报告」 | 进报告屏 |
| 正在分析 | `正在分析 n/N` + **行内进度条** | 无按钮，算完自己变 |
| 只算到 n/N | `只算到 n/N` + 「继续分析」 | **就地续算**，不跳页 |
| 未分析 | `未分析` + 「开始分析」 | **就地开算**，不跳页 |

**打开某一局是点整行**，不是点行尾的按钮（Fan 2026-07-28 拍板）：跳转和干活分在两个手势上。**现状是点按钮**，要改。

**未分析屏那块走势位不许画一条贴中线的平线冒充均势** —— 那是把「没算过」伪装成「算过了，结果是均势」。`tokens.css:924` 的 `.kiosk-eval__plot.is-empty` 就是给这一格用的。

**两处 `.note`**：`:524`（上白下黑、红段是第 43 手、蓝标不是琥珀标的理由）和 `:551`（两档是后端写死的、升降级局整局封分析）都是**旁注**，不搬。⚠️ 但 `:551` 里那条**产品规则要保住**：**升降级局整局封分析，下完也不给复盘**（后端 `interface.py` 有闸）。现状列表里如果出现了 ranked 局，要确认它不给「开始分析」。

**这一屏的胜率曲线怎么办 —— 三条路，按顺序试**：
1. 后端 `report_task_moves` 里逐手 `winrate` **已经落库**（稿子的蓝标就是这个意思）。**先去核 kiosk 侧的 API 有没有把它吐出来**（`ReportDetailPage` 用的是 `TrendChart`，说明数据链已经通到了详情页）。通 ⇒ **接真数据，把蓝标去掉**。
2. 通不到 kiosk 列表页 ⇒ **整块不渲染**（规范 §11「做不了的不留占位框」）。
3. **一律不许画示意曲线**（G8）。稿子上那条是示意的，稿子自己写明了；上线就是假数据。

- [ ] **Step 0** 先做 **D4** 那次核实：读 `katrain/web/api/` 与 `report_task_moves` 的字段，判定第三格写「妙手」还是「漏着」，把依据写进提交信息。
- [ ] Step 1–10 同 Task 10 的七步；四图 slug `07-review`。
- [ ] 承重：待复盘对局造成 30 局，量 ① **只有中间那块滚**（头尾两块的 `y` 不随滚动变）② 渐隐从组标题下缘开始、没盖住标题 ③ 露一半按**行高 40** 的上下界 [16, 29] 算，不是卡高那套。
- [ ] 额外一步：**验收「研究现在到得了」** —— Task 4 把 `研究` 下了 Dock，规范 §3 说它并进复盘。从 `/kiosk/report` 点得到 `/kiosk/research`（现状 `GameHistoryPage` 的「复盘」按钮就跳那儿，可以复用同一个入口）。写成断言，销掉 Task 4 埋的账。

---

### Task 16 修订（2026-08-23，做完之后回填）

⚠️ **屏号是 19 不是 07**，四图 slug `19-review`。稿子行号 `go-kiosk.tmpl.html:1664-1734`。

### D4 那次核实的结论：**写「妙手」**，判据 `delta_score >= 2`

计划问的是「逐手数据里有没有『这一手是不是唯一好手』所需的第二名着法评分」。**有** ——
`report_task_moves.top_moves` 是十个候选，每个带 `winrate` / `score_lead` / `prior`，
`GET /api/v1/reports/{task_id}/moves` 原样吐出来（`endpoints/reports.py:85`）；
第 N 手的候选在第 N−1 行里（分析送进去的是 `moves[:move_number]`，`report_analyze.py:304`）。

但**更要紧的是另一件事**：这个仓里早就有一份妙手口径，而且它**不用 top_moves** ——
`features/report/reportModel.ts:192` 把同一批 `ReportTaskMove` 映射成
`is_brilliant: delta_score >= 2` / `is_mistake: delta_score <= -3`，
后端 `cron/analysis_repo.py:185` 和 `live/models.py:67` 也是这两个数。⇒ 复用，不另立。

**国象 2026-07-28 把妙手撤成「漏着」的那个理由不能转过来**：它的分析跑在盒子自己身上
（单线程 12 万节点、13–16 层、同一局面能摆 45cp），噪声吃掉了判据；围棋的报告是 **cron 离线**
跑的，每手 500 或 2000 次计算，跟盒子算力无关。**转判据不转结论。**

⚠️ 附带查出来一条既有的不一致（本轮不动）：`web/interface.py:1337` 用的是丢分
`-0.5 / 1.0` 那一套，和 cron / live 那套 `2.0 / -3.0` 对不上。两套各自服务不同的数据源
（对局中实时 vs 离线报告），这一屏读的是 `report_task_moves`，所以取 cron 那套。

### 准确率照搬 `core/ai.py` 的公式，不自己发明

`100 × 0.75^加权丢分`，权重是「这一手有多难」（候选着法按 policy 先验加权的平均丢分）。
搬进 `features/report/reportStats.ts`，期望值**手算**写在 `reportStats.test.ts` 里。
理由：桌面版和 web 版的对局报告显示的就是这个数，同一局在两处必须一样。

### 稿子这一屏的三处漏画 / 一处写错（都已登记，该提上游）

| 稿子 | 实际 | 怎么办 |
|---|---|---|
| 行尾只有一个状态标 | 规范 §11 要四态各有各的样子 + 「就地干活不跳页」（Fan 2026-07-28）；国象稿子同处画的就是「状态标 + 药丸键」 | 照规范做，四图上多出的键是预期 |
| 这一屏没画搜索 | **稿子自己的 `.sbox` 注释把复盘列进了「有搜索的四屏」**（`:326`），而现状搜索是通的 | 做成开关：收起态和稿子逐像素一样 |
| 第三张卡 `is-soon`「接口还没有 · 即将上线」 | 两条导入路都在跑（`ReportLocalImportDialog` / `ReportLibraryImportDialog` → `POST /user-games`） | 做成能用的，一张卡两条路 |
| 旁注说「升降级局下完也不给复盘」 | **没有任何实现**：`POST /reports/` 不看 game_type；带 ranked 闸的是 `hint_gate.py`，它挡的是**对局进行中**的选点白灯。国象稿子明写「两者进的是同一条复盘线、同一份报告」 | 按国象和后端来；那句旁注是把「对局中封分析」错误延伸到了下完之后 |

### 「算了一半」那一档是从 `failed + analyzed_moves > 0` 认出来的

后端没有「暂停」状态：跑了一半断掉的任务落在 `failed` 上、`analyzed_moves` 还留着，
而重试会从断点续算（`_get_resume_move_number`）。所以 `failed` 按有没有进度分两档，
有进度的那档说「继续分析」——说「重试」反而像要从头再来。

### 「研究到得了」那笔账（Task 4 埋的）**落在屏 20 不在屏 19**

稿子自己写着研究的入口有三个：「棋谱详情的『去研究』、**复盘报告**的『去研究』、棋谱库的
`open_in_research`」（`:1800`）——不含复盘列表屏。而 `ReportDetailPage.tsx:324` 早就有
「在研究中打开」。⇒ 从 `/kiosk/report` 点整行的「查看报告」进屏 20，再点「去研究」，路是通的。

### 顺手修的两件与本屏无关但会咬人的事

1. **`ReportsPage.layout.test.tsx` 删掉了。** 它在 jsdom 里断言 `flex:1` / `minHeight:0` ——
   断的是**声明**不是**结论**（原样搬进真浏览器不可能失败），而且它的断言对象
   （`report-preview-region` / `PlaybackBar`）本轮整块没了。承重判据搬进了几何闸。
2. **两条做题屏的几何闸原来依赖「另一个进程在不在」。** `tsumego/problem/:id` 外面套着
   `PhysicalBoardGuard`，它读 `GeometryContext`，而后者**只在接口 404 时**才落到 `disabled`；
   接口连不上（502）时 phase 停在 `required` ⇒ 整屏被换成标定台 ⇒ 30 秒超时。
   后端起着就绿、一停就红的东西不叫闸。已在 `boot()` 里把 geometry status 钉成
   「这台盒子没有摄像头」。同理给四图加了 `stubShellAssets`（logo 502 会让实现图左上角变成碎图标，
   而 Task 20 Step 3 要靠「重跑零字节变化」验证确定性）。

---

## Task 16b: 屏 20 · 复盘 · 报告 `/kiosk/report/:taskId`（计划外补的一屏）

计划的任务表按十屏稿编的，屏 20 不在里面；稿子 8-21 扩到 27 屏时补进来的。
**现状 `ReportDetailPage.tsx`（397 行）本来就在**，本轮是把它从「左盘 aspect-1 + 右列」
改成 L2 布局 A（盘 516 + 16 + 右栏 460），并把稿子那两块（逐手胜率 / 重点手）接上真数据。

### 这一屏逼出了 `LiveBoard` 的 0.5 格边距 —— 同一条不变式的第三次

做题屏（Task 14）在 `TsumegoBoard` 上修过一次：坐标交给外壳画时，
盘的边距要从 1.5 收回 0.5，**而且不许取整**。这一屏的盘是 `LiveBoard`，同一个坑：

| 症状 | 来源 | 修法 |
|---|---|---|
| 头尾两条线偏 11.9px | 三处叠加 | 见下 |
| ① 容器 `padding: 4px` | 落子区 460 → canvas 452 | `showCoordinates` 为假时去掉 |
| ② `size = floor(min(w,h) − 8)` | 又减一次 | 同上，减 0 |
| ③ `floor(gridSize)` + `round(offset)` | 24.2→24，18 格累出 4px，再重新居中 | 外壳画坐标时**不取整** |

`calculateBoardLayout` 的第四个参数因此从「一个 margin 数字」改成
`{ margin, exact }` —— **两个必须一起用**，只改一个照样对不上。galaxy 那边三个参数调用不受影响。

⚠️ 这条**只有真浏览器量得出来**：闸写在 `kiosk-shell-geometry.spec.ts`（读 canvas 像素找竖线，
比对刻度带头尾两个字心）。变异实测：把 `exact` 去掉，同文件另外 25 条一条都不红。

### 四图当场看见的一个 bug：沉浸模式在屏顶留了一条 56 高的空带

这一屏原来 `setImmersive(true)`，而 `immersive` 在 `KioskLayout` 里只干一件事 ——
**把顶栏整块不渲染**；可 `.kiosk-content` 的 `top` 仍然是 `var(--topbar-h)`。
规范 §5 防跳铁律 1 写死「顶栏永远占 y 0–56，任何层级都不隐藏」，稿子这一屏画的也是有顶栏的。
⇒ **这一屏不再进沉浸。** `immersive` 本身留着（研究 / 摆谱 / 做题 / 直播还在用），
那笔账仍在 Task 4 名下。

### 稿子写了而后端给不出的一处：「用了 6 分 12 秒」

`ReportTaskStatus` **不吐时间戳** —— `started_at` / `completed_at` 在表里有、在响应里没有
（`endpoints/reports.py:64` 的 `_task_to_dict`）。编一个耗时上去就是假数据。
⇒ 这一行改写真能拿到的：还在跑时写「已分析 a / b 手」，跑完写「每手算 N 次 · M 手」。
**登记：该给 `_task_to_dict` 补两个时间戳字段**，补了这一行就能照稿子写。

### 稿子没有滑块，但「点曲线跳手」不能跟着 `PlaybackBar` 一起丢

187 手的谱靠四个翻手键一手一手挪走不到第 120 手。`TrendChart` 本来就支持点击跳手 ——
换控件不能把功能换没。曲线因此可点，并多画一条竖游标标出「现在在第几手」。

### 候选着法表在研究屏，不在这儿 —— 但「看一条推荐的后续」留住了

稿子这一屏没有 `.aitab`（那张表在屏 21 研究），所以原来的 `AiAnalysis` 整块不搬。
可「点一条推荐看它的后续」是真功能：改成**打开「AI 推荐」之后点盘上那个标记就是选它**，
点别处收起。比原来那张表少占一整块高度，手势还更直接。

### 顺带删掉一个变成死码的组件

`ReportMetaPanel`（kiosk 那份，250 行）没有消费者了 —— 它的三件事（状态/档位、这一局的元数据、
当前手的读数）分别落到了页控条副标、`.rhead` 和重点手行上。连同它的测试一起删。

### 「重点手」怎么排:**按走子方自己视角的胜率跌幅**

白走坏的时候黑方胜率是**涨**的。按黑方胜率的绝对变化排，会把白的失误排成「黑的好手」，
而且方向反了屏上照样是一行通顺的中文。门槛借的是仓里已有的失误线（`delta_score <= -3`）——
屏上列的这几手，和左栏三格里数进「失误」的那些手必须是同一批。
「该走 X」取的是**上一行**的 `top_moves[0]`：本行已经是走完之后的局面，它的首选说的是「下一手」。

---

## Task 17: 屏 09 · 课程 `/kiosk/tutorial`

**设计稿**：`go-kiosk.tmpl.html:611-654`（L1-A，形态 1）。**现状**：`pages/TutorialCategoriesPage.tsx`（141 行）。

**左栏**：标题同 01；盘画课上的图；同步行 `课上的图会摆到盘上` / `等选课`（规范 §5：课程页左栏和对弈**逐像素相同**，差别只在同步行那句话）。

**右栏三块**：

| 块 | 内容 |
|---|---|
| 问候行 | `课程<i>随云端同步</i>` + `后端是五层结构，内容不在这台盒子上生成` |
| 分类 | 组标题 secval `每类几本，由接口返回`；进度环卡 `入门`/`规则与吃子`、`基本功`/`死活 · 手筋`、`布局与定式`/`开局怎么走` |
| 一课长什么样 | 组标题 `一课长什么样` / `Anatomy`；3 条 `.kiosk-row`：`书`→`一本书`/`分若干章`/`.kiosk-tag Book`；`章 / 节`→`章下面是节`/`节是真正「一课」的粒度`/`.kiosk-tag Section`；`图`→`节里是一张张棋图`/`每张图带一段人声旁白，还能一键摆到实体盘上`/`.kiosk-tag--win 带音频` |
| 现在能练的 | 组标题 `现在能练的` / `Instead`；2 张卡 `去训练营`(`puzzle-piece`)`六类题 · 现在就能做`、`去摆谱`(`grid-nine`)`跟着名局摆一遍` |

⚠️ **环里写「—」不写 0**，理由稿子写死了：`0` 意味着「查过了，一本都没有」，而这台盒子**还没跟云端对过账**——**这两件事在界面上必须分得开**。而且「同步不到」和「一本都没有」是两种状态，**得分开报**。**接口返回空就是空态一句「暂无教程」**，不摆一排点不开的卡让人以为快了。

⚠️ **分类名与每类几本都从 `/api/v1/tutorials/categories` 拿，界面不写死。** 稿子上那三个分类名是**形状不是清单**。现状 `TutorialCategoriesPage` 就是读接口的——**保住这个行为**，不要把稿子上那三个名字硬编进去。

**「现在能练的」这一组是稿子特有的空态兜底**：云端还没同步下来课的时候，这一屏的正事就是**把人送到有内容的地方去**。**只在分类为空时渲染这一组**；有课时不渲染（否则它就成了一排永远在的杂物）。

**两处 `.note` 都是旁注**（`:630` 分类来源与「—」的理由、`:648` 五层结构是后端已建好的）。

- [ ] Step 1–10 同 Task 10 的七步；四图 slug `09-courses`。

---

### Task 17 修订（2026-08-23，做完之后回填）

⚠️ **屏号是 23 不是 09**，四图 slug `23-courses`。稿子行号 `go-kiosk.tmpl.html:1922-1970`。
「一课长什么样」是 **4 条**不是计划表里写的 3 条（书 / 章 / 节 / 图）。

### 左栏走 `RAIL_ROUTES`，只把同步行那句话换掉

规范 §5 说课程屏的左栏和对弈屏**逐像素相同**，差别只在同步行。所以
`/kiosk/tutorial` 进 `RAIL_ROUTES`，`GoConsoleRail` 加两个可选 prop
（`syncLeft` / `syncRight`），标题、盘、三格状态一律不给改 —— 开的口子只有这一处。

**课程过 §5 那条判据靠的是「课上的图会摆到盘上」**，同步行那句话说的就是它。

### 稿子这一屏**自己是不自洽的**，所以没有哪一份数据能和它逐像素对上

它同时画着「三张分类卡」和「现在能练的」，而**那两块按定义不共存**：
环里写「—」说明这台盒子还没跟云端对过账，可三张卡又说分类拿到了。
稿子自己的注释解释了这一点 —— 那三张卡是**形状不是清单**。

⇒ 四图取的是**有课的那一面**（常态），「现在能练的」因此不渲染（计划的裁定：
有课的时候它就是一排永远在的杂物）。另一面由单测两个方向各钉一条。
**实测下来这条差异在四图上看不见** —— 稿子那张截图里「现在能练的」也在折线以下。

### 环里的「—」不是「还没查」，是「这个数接口不给」

计划写的判据（`0` = 查过了一本都没有；`—` = 还没对过账）**只说对了一半**：
`KioskCard` 的 `ring` 渲染成 **`NN%`**，是**进度**不是本数。而
`/api/v1/tutorials/categories` 只给 `book_count`，**每一类看到哪儿了它不给**。
⇒ 环恒为 `null`（屏上「—」），**本数落在卡的副标和组标题右端**，那两处是真数。
拿本数去画进度环会画出一条谁也读不懂的弧。

### 三种「没有」在屏上是三句话

| 状态 | 屏上 | 判据 |
|---|---|---|
| 还没查到 | 正在跟云端对课 | `categories === null` 且没有错 |
| 查了拿不到 | 加载失败 + 那条错 + 重试 | catch |
| 查到了是空 | 暂无教程 | `categories.length === 0` |

**「暂无教程」是结论不是「还没查」** —— 混了就是把没查过伪装成查过了。

### 组标题右端换成真数

稿子写「每类几本，由接口返回」——那是**说给读稿人听的**，而那一格按规范放的是**数据**。
改成「N 类 · 共 M 本」。

---

## Task 18: 屏 10 · 设置 `/kiosk/settings`

**设计稿**：`go-kiosk.tmpl.html:655-762`（**L1-B**，但左栏仍是 `.kiosk-console` 装 `.kiosk-navlist`，宽照样 296 —— 规范 §12「左栏宽度和 L1-A 的镜像栏一样，从对弈切到设置那条纵向接缝不动」）。**现状**：`pages/SettingsPage.tsx`（197 行）。

✅ **Q4 已裁定 —— 见 D10：方案 (a)，只做有内容的组，导航项数 = 真组数。** 语言那一格留着，登记成规范 §12 的已知偏差。下面「Q4」那一小节保留作取证记录，**不再是待办**。

**骨架**（D10 只决定摆几组，骨架本身不受影响）：
- 左栏 296：`.kiosk-console` > `.kiosk-console__title`（`设置` / `Settings`）+ `.kiosk-navlist`（`.kiosk-navitem` 高 44、间距 6、18px 图标 + 13px 文字、整项可点）+ 底部一句 `系统设置（网络、语言、输入法）在**设置中心**，不在这里。`（`margin-top:auto`）
- 右栏 680：`<KioskScrollZone>` 形态 1，一条完整的纵向流，每组一个 `.kiosk-section[data-group]`。
- **导航只跳不换页**：点导航**滚过去**，不是把右边整块换掉。换页式在这块屏上更差——用户看不到自己一共有多少可调的。
- **高亮跟着真正在看的那一组走**（滚动联动）。写死在某一项上而右边滚到了别处，**是在谎报你在哪儿**。
- **导航项数 = 分组数，且词一一对应。** 导航里写「声音」，右边那组的标题就得是「声音」——两套词等于两套心智模型。

**这屏还要接三个共享构件**（`tokens.css` 都给好了，现状一个都没用）：
- `.kiosk-slider`：**连续量不许用分段控件硬掰成三档**（识别帧率、音量、落子确认速度）。**刻度必须带单位或档名**：`2 帧 / 5 帧 / 10 帧`，光写「适中」没有信息。
- `.kiosk-swatch`：**看样子选**的项给色块，不给文字列表——「胡桃·枫木」四个字说不清它长什么样。40×40，选中态用**强调色描边**（不靠色块本身的深浅暗示，色板本身就是各种颜色，深浅是内容不是状态）。
- `.kiosk-seg`：一屏之内所有选择组必须用**同一种控件**。

**四处 `.note`**：`:667`（系统设置在设置中心）是**真 UI 文案**，照搬；`:674`（不登录也能用）是**真 UI 文案**，照搬；`:682`（三家平台登录字段各不相同）和 `:697`（围棋走摄像头识子不是传感盘）是**旁注**，不搬。

- [ ] Step 1–10 同 Task 10 的七步；四图 slug `10-settings`。
- [ ] 承重：右栏造到 7 组全满，量整栏滚 + 渐隐 + 高亮跟着滚动走（**滚到第 3 组时导航第 3 项 `aria-current="true"`，其余都不是**）。

### 取证记录（原 Q4）· 设置页七组里有五组现在没有内容

survey 逐项核过，稿子的 7 组对上现状的 5 张卡：

| 稿子分组 | 现状 |
|---|---|
| 账号与平台 | 只有「盒内账号」（`AccountSection`）。四个平台是一块 `pointer-events:none` 的**死装饰**，而且列的是 `99围棋/野狐/腾讯/新浪`，和真正能连的 `ogs/fox/golaxy` **对不上** |
| 实体棋盘 | 只有「重新标定」+ 状态读数。**LED 提示开关、识别帧率滑条都没有** |
| 棋盘外观 | **整组不存在** |
| 落子与提示 | 只有「做对后自动进入下一题」 |
| 声音与报着 | **整组不存在**（走子音效在 `PvpLocalSetupPage` 里） |
| 对局默认值 | **整组不存在**（都在 `AiSetupPage` / `PvpLocalSetupPage` 里按局设） |
| 关于 | **整组不存在** |
| （稿子没有）语言 | **现状有** —— 而规范 §12 明写「系统设置（网络、账号、**语言**、输入法）不在这里，在设置中心」 |

三条路，**已按 D10 选了 (a)**：

- ✅ **(a) 只做有内容的组**（**已选**）：导航 3–4 项，词与右边一一对应。**符合「导航项数 = 分组数」和 G8**，但和参考图差 3–4 组，差异图上是一片红。
- **(b) 七组全摆，空的挂琥珀「未接后端」**：图上最像，但那五组里**大部分不是「后端没有」而是「这个设置项还没做」**——挂「未接后端」是**用错标**（G8 那条两色规则）。而且它把一条表现层赛道拖出五个新功能。
- **(c) 七组全摆，空的组做成真功能**：那是五个新 feature，远超本轮。

**语言那一格：留着**（D10）。按规范该搬去设置中心，但**设置中心不在本仓**，搬走等于这台盒子上再没有语言开关 ⇒ 登记为「规范 §12 的一处已知偏差，等设置中心接手」。

---

### Task 18 修订（2026-08-23，做完之后回填）

⚠️ **屏号是 27 不是 10**，四图 slug `27-settings`。稿子行号 `go-kiosk.tmpl.html:2110-2220`。

### 计划表里那三个共享构件，实际用上的只有 `.kiosk-seg`

`.kiosk-slider`（识别帧率 / 音量 / 落子确认速度）和 `.kiosk-swatch`（棋盘皮肤）
**它们要调的那几个设置项本身不存在** —— D10 选的是「只做有内容的组」，
所以这两个构件这一屏用不上。**它们仍然没有第一个消费者**，登记。

### 左栏那句「系统设置在设置中心」**没搬** —— 稿子 8-22 自己把它收进注释了

计划把 `:667` 判成「真 UI 文案，照搬」。可 Fan 8-22 那次「不要写那么多解释文字」的清理
把这一屏的旁注**全收进了 HTML 注释**，包括这一句。稿子里现在的左栏只有标题 + 导航。
⇒ 按稿子来，不搬。计划那条判定被稿子的新版本取代了。

### 页控条撤了：设置是 Dock 项 ⇒ L1 ⇒ 没有返回键

上一版有一条带返回的页控条，还从 `location.state.from` 算「退回哪儿」。
**那是死码**：全仓只有 Dock 会跳到这一屏，而 Dock 不带 `state`。
六条测它的用例一并删掉，`navigation.integration` 那条改成「L1 没有返回键，出口是 Dock」。

### 滚动联动有个真问题：**最后两组太矮，滚到底也到不了视口顶**

四组的高度是 417 / 258 / 78 / 78，视口 434 —— 内容总高 855，最大 scrollTop 421，
而第三组的上缘在 691。「滚过视口顶的那一组就是正在看的」这条规则**永远轮不到它**：
点导航第 3 项之后，scroll 事件会把高亮弹回第 2 项 —— **那正是「谎报你在哪儿」**。

⇒ 补一段量出来的尾部留白（`视口高 − 最后一组高`），每一组就都能滚到顶上，
**点和滚从此说的是同一件事**。量在最后一组的 callback ref 里，不在 effect 里
（effect 里同步 setState 会被 `react-hooks/set-state-in-effect` 拦下）。

### 账号那一块从 MUI 卡片重排成了 `.kiosk-row`

上一版是一张 `background.paper` 的卡 + 一条满宽的红色退出按钮，夹在两组行中间
**像是从别的应用里剪进来的**（四图第一版当场看见）。现在是两行：一行账号、一行 AI 段位。
**段位详情那张卡（`AiLadderStatusCard`）还没重画** —— 它只在点开对话框之后才出现，登记。

### 平台那四张死卡换成一行真入口

上一版摆着四张 `pointer-events:none` 的卡，列的是 `99围棋 / 野狐 / 腾讯 / 新浪` ——
**和真正能连的三家（ogs / fox / golaxy）对不上**。改成一行：念真能连的三家，
按钮去跨平台对弈那条路（三家的登录字段各不相同，不该在这儿复制一套表单）。

---

## Task 19: 稿外五屏只接壳（D2）

`baipu` / `live` / `research` / `play/cross-platform` / `vision/setup` 稿子没画。**只接顶栏 / Dock / L1 两栏这层共享壳，让它们不再是视觉孤岛；内容区维持现状。**

**明确不做**：不照规范 §5 自己推导这五屏的版式。**没有稿子当依据，四图对比就没有参照物，那等于自己发明设计。**

⇒ **这个 Task 没有四图闸**（没有参照物）。它的验收是**几何闸 + 眼睛看不跳**：

- [ ] **Step 1** 这五屏（含它们的子路由）全部走 `KioskFrame`，顶栏在、`dockLevelOf` 判层级、页控条已经在 Task 8 换过了。
- [ ] **Step 2** `LivePage`（L1）接 `KioskConsoleRail`？—— **不接**。规范 §5 的判据是「这个模块的活动会不会发生在实体盘上」；看直播不会。它走 **L1-B 通栏**。`BaipuListPage`（L1）**接**（摆谱就是在盘上摆）。
  ⚠️ 但 Task 4 已经把 `baipu` / `live` 下了 Dock，它们**不再是 L1**。所以 `dockLevelOf` 会判成 2、不出 Dock、内容区 516 高。**这是对的**，别去纠正。
- [ ] **Step 3** `ResearchPage` 那三条手写 52px 面包屑条：**本轮不动**（Task 8 已登记）。它有 864 行、四个渲染分支、三处结构各不相同，动它超出「接壳」。**在提交信息里再登记一次**，别让它悄悄消失。
- [ ] **Step 4** 几何闸：五屏各量一次「顶栏 1024×56@(0,0)、内容区 x16 宽 992、无 Dock 时下缘贴 600」。**这三条就是「切模块不跳」在这五屏上的全部要求。**
- [ ] **Step 5** 眼睛看：从 `/kiosk/play` 逐个切过去，**顶栏和中间区外框不许动一个像素**。用 Playwright 连续 `goto` 并各截一张，肉眼对齐。
- [ ] **Step 6** 双构建 + 提交。

---

## Task 20: 收尾

- [ ] **Step 1** 把 Task 6 那个 `@mui/icons-material` 白名单清空——如果还有剩，逐个看是不是稿外五屏的内容区（那些**允许**留着，D2 只接壳）。剩下的写进白名单并注明理由。
- [ ] **Step 2** 全量跑，和基线比：

```bash
cd katrain/web/ui
npm test 2>&1 | grep -E '^\s*(FAIL|×)' | sort > /tmp/after.txt
comm -13 /tmp/base.txt /tmp/after.txt          # 期望为空 —— 一条新增失败都没有
npx eslint src/kiosk src/kiosk-shell 2>&1 | tail -5   # 和 Task 0 存的基线比名字集合
npx playwright test tests/kiosk-shell-*.spec.ts tests/kiosk-screen-*.spec.ts \
    --config playwright.visual.config.ts --workers=1 --reporter=list
npx tsc -b && npm run build && npm run build:kiosk-2d
```

- [ ] **Step 3** 重跑一遍全部九屏四图，确认**零字节变化**（时钟已冻，所以这一条现在有意义了）。有变化说明有非确定性，先查出来。
  > ⚠️ 「重跑零字节变化」证明的是**实现图与代码同步**，**不是视觉闸通过**。视觉闸是 Fan 的眼睛，已经在每屏那一步过了。
- [ ] **Step 4** 更新三份文档：
  - `superpowers/tracks/kiosk-go-shell-align/scope.md` —— 把 Q1–Q4 的答复和 D1–D6 的执行结果落下去；
  - `katrain/web/ui/src/kiosk-shell/README.md` —— 记 icons 由 1 个扩到 82 个、MANIFEST 209→290、新增 `go-screens.css` 及它**为什么这么小**（vendored tokens.css 比设计稿新）；
  - `superpowers/tracks/golaxy-ai-ladder-parity/kiosk-design-alignment.md` §17.2 —— A 组六条逐条标上「本轮接了」，§12.5 那条「另外 17 屏还在用 `SubPageBar`」销账。
- [ ] **Step 5** 登记本轮**没做**的（每条都写清判据，**不写「暂无」**——否定的答复不携带原因，下一个人会读成「没人查过」）：
  - 成长屏（D1，独立赛道）
  - `ResearchPage` 三条手写面包屑条（Task 8/19）
  - 木纹贴图 `--oak`（D6：资产不在 MANIFEST 管辖内）
  - `.kiosk-wip.have` 的蓝不跟 `--info`（G2，上游的事）
  - `.kiosk-tag--live` 该提上游
  - 刻度轨道那条**不变式**该提上游（Task 9，不是提 `1fr`）
  - `immersive` 抽顶栏与规范 §5 防跳铁律 1 冲突（Task 4）
  - 训练营「每日一题」（Task 12：稿子没画）
  - 单元列表「已掌握判据」那句话（Task 13：规范要求但稿子没画）
  - 上游 `MANIFEST.sha256` 本身的 sha256 还没钉（Task 6）
- [ ] **Step 6** 上板走查（RK3562）。**判据可执行，不是「看一眼觉得还行」**：
  - `/kiosk/play` **冷启动**（清缓存、首次进页）看左栏那块盘，**秒表计从页面出现到盘画出来的时长，跑两次**。看得见空白 = 真 bug；两次都看不见 = 把这条销掉，并写明「**RK3562 上量过，没复现**」。**「看不见」也要写来源。**
  - 中文是不是霞鹜文楷、「智星盒」是不是龙藏（板子上 PingFang / Songti / Kaiti **一个都没有**，回退长相和开发机完全不同）。
  - 2G 内存：**一次只跑一家**（服务自己就占 750M）。
- [ ] **Step 7** 提交，**不推**。等 Fan 说。

---

## Self-Review（写完这份计划后自查的结果）

**1. 规范覆盖** —— 规范 §1–§14 逐节对到 Task：§1/§2/§6 → Task 3；§3/§7 → Task 4；§4 → Task 10；§5 → Task 5、7；§8 → Task 6、9、11；§9 → Task 1（字体已在上一轮做完，本轮只保住）；§10 → Task 6；§11 → Task 8、11、16；§12 → Task 18；§13 → Task 9（id 重名 + isolation）；§14 → G8 + 各屏。**§5 的成长屏那一节没有对应 Task**——这是 D1 有意跳过的，不是漏。

**2. 占位扫描** —— 全文无 TBD / TODO / 「类似 Task N」。每个 Task 的每个代码步都带可运行的代码块与期望输出。**Task 12/13/14/15/17 的 Step 1–10 写成了「同 Task 10 的七步」**——这是**有意的**：七步在「每屏的固定七步」那一节写全了，那不是引用一个别处的 Task，是引用同一份清单。

**3. 类型一致性** —— `IconName`（Task 6）被 Task 4 的 `DockTab.icon`、Task 8 的 `KioskPagebar.action`、Task 6 的 `KioskCard.icon` 共用；`StatusCell`（Task 5）被 `KioskConsoleRail.statuses` 共用；`calculateKioskScale`（Task 1）只有 `KioskFrame` 一个消费者。**Task 4 依赖 Task 6 的 `Icon`** —— 已在 Task 4 的 Interfaces 里点名「先做 Task 6」。

**4. 一处已知的顺序张力** —— Task 5（镜像栏）要用 Task 9 的 `GoBoardSvg`，Task 7（滚动区）要 Task 10 的内容才有被测物。已分别在两个 Task 里写了过渡办法（占位 / 造数据），不改顺序：**共享壳必须整块先稳定**，这是 Fan 定的。

**5. 两处自查后补上的** —— ① Task 20 要比的那份基线原来没有任何 Task 产出，补了 **Task 0**（`lint` 和 `npm test` 本来就是红的，不存基线就没法判「这条红是不是我弄的」）；② 设置页那个七组对五卡的缺口原来只写在 Task 18 里，提到了顶上的 **Q4**——它和 Q1/Q2 一样会挡住一整屏。**（2026-08-20 二次授权后 Q1–Q4 已全部裁定为 D7–D10，见上。）**

---

## 执行前的四条：**已全部裁定**（Fan 2026-08-20 二次授权自决）

| # | 问题 | 裁定 | 依据（三家取证） |
|---|---|---|---|
| **Q1 → D7** | 破坏性按钮的长相 | 照抄五子棋：只换字色和边框，形状不动 | `gomoku/.../GameRail.tsx:373` 用的就是 `className="danger"`；`gomoku/ui/src/index.css:1619` 给了它样式 |
| **Q2 → D8** | Dock 六项还是七项 | **六项** | 五子棋自己就是 6 项（`gomoku/.../dockRoutes.ts`）—— 项数相等从来不是规矩 |
| **Q3 → D9** | 顶栏那几个围棋专属指示器 | **四样全拆** | 三家顶栏都零指示器零齿轮；三格状态在 L1 左栏（`chess/.../boardStatus.ts`）；L3 已有 `VisionSyncOverlay` + `PhysicalPlayStatusChip`，原来那条「会盲」是错的 |
| **Q4 → D10** | 设置页七组里五组没内容 | **只做有内容的组**；语言留着 | 国象设置屏只有 2 项导航、象棋是平表、五子棋没有设置屏 —— 三家没有一家摆过空组 |

**没有任何一条还挡着执行。** 从 Task 0 开始按序做，每屏四图仍然要 Fan 点头才进下一屏（G4，这条没变）。
