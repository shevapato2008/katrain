# 开局设置 r2 · 验收记录(2026-09-21)

三屏:02 自由对弈 / 03 升降级对弈 / 04 本地对局。设计稿 2026-09-21 由 Fan 通过
(artifact `e4d3c7ef-82dd-4a5e-a7b0-42db6b4ad731` v23)。

---

## 1. 这一版改了什么

八组设置收成**两行六格 + 一条推导**:

| 组 | 内容 |
|---|---|
| 这局棋 | 路数 · 规则 · 让子 → **贴目推导条** |
| 对手 | 棋力档位轨(29 档) |
| 怎么坐 | 落子 · 我执 · 用时 |

控件选型只有一条规则:**枚举用下拉,连续量用轨**。路数 3 / 规则 4 / 让子 11 /
落子 2 / 我执 3 / 用时 7 都是小枚举;只有棋力 29 档是连续量。

**贴目不再是设置项。** 它是 (规则 × 让子) 的结果,算在
`kiosk/utils/setupOptions.ts` 的 `resolveGameTerms()` —— 整条链上唯一算它的地方。

---

## 2. 修掉的线上缺陷

### 2.1 让子局双重补偿(真缺陷,改版前一直在线上)

改版前前端在 `handicap > 0` 时只把贴目那一组**从屏上换掉**,`komi` state 不动
(缺省 6.5)且照样发给后端(`AiSetupPage.tsx:150`、`PvpLocalSetupPage.tsx:132`),
后端原样写进 `KM`(`interface.py:806-808`)。

中国规则让 2 子于是变成「白 +2(KataGo 的 `WHB_N` 自动加)+ 6.5 目贴目」——
**正是屏上那段说明警告的「两样一起用会补两遍」**。

守它的旧测试叫「让了子之后贴目那一组换成说明,**而且送出去的还是那一档的值**」,
而它的断言里**一个载荷字段都没有**。现在断言落在 `handicap` / `komi` 两个字段上。

### 2.2 `get_rules('aga-button')` 静默回退成 `japanese`

`BaseEngine.get_rules()` 查不到就回退到 japanese(`core/engine.py` 最后一行)。
在围棋里这不是降级,是**换了一种记分法**:面积计分的局按数目法算,胜负不一样,
而屏上没有任何异常——没有报错、没有降级提示,一局棋照常下完、照常判出结果。

已登记 `("button", "aga-button")`,并建 `tests/test_rules_wire.py` 逐个核前端
能送出来的每一个规则值。

### 2.3 ± 两颗键不居中(Fan 2026-09-20 指出)

真浏览器量出来的两层原因:
1. 字形是 `−`(U+2212)和 `＋`(U+FF0B),一个半角一个全角,宽 11.31 vs 20;
2. `src/index.css:41` 的 `button{padding:.6em 1.2em}`(Vite 模板自带)命中了
   `.catstep` —— 20px 字号下左右各 24px,挤进 44px 的 border-box,内容盒被压到 2px,
   字形整个溢出后居中,按钮也被撑成 50px。

改成 SVG + `padding: 0` 写死。实测 dx=dy=0、宽 46。

### 2.4 棋力读数缺等级

`AiSetupPage.tsx:491` 那句 msgid 的缺省值结尾就是「第 {n} 档 · 」,后半截
**从来没接上过**,屏上是个吊着的点号。现在是「第 15 档 · 6 级」。

---

## 3. 承重结构实测(`tests/kiosk-setup-r2-geometry.spec.ts`)

目标 viewport 1024×600,真浏览器。**先写关系式再读数,具体像素只记录。**

内容最满那一态是造出来的:让 9 子 + 最长的规则名 + 没标定摄像头。
**装得下的数据量下量到的数字一概不算。**

| 量什么 | 关系式(写死在前) | 实测 |
|---|---|---|
| 该滚的是谁 | `.kiosk-rail[data-su] .kiosk-side__scroll`,不是它的祖先 | — |
| 屏 02 该不该滚 | `scrollHeight <= clientHeight` | 内容 364.5 / 可视 370,**余量 5.5** |
| 屏 03 该不该滚 | 同上 | 内容 388.8 / 可视 400,**余量 11.2** |
| 屏 04 该不该滚 | 同上 | 内容 333.5 / 可视 352,**余量 18.5** |
| 撑破了还滚得动 | 塞 `flex: 0 0 1200px` 后 `scrollTop >= 500` | 500 |
| 弹层没被裁 | border box 完整落在 `.kiosk-rail` 盒内 | 让子 / 用时两处都过 |
| 弹层盖不盖盘 | `popLeft >= boardRight` | 758 / 749 vs 532 |
| ± 居中 | `\|dx\| < 1.5` 且两键相差 `< 1` | dx=0 dy=0,宽 46 |
| 主行动键 | 在滚动区外、贴右栏底、不跟着滚 | `kiosk-shell-scroll.spec.ts` 两屏各一条 |

**闸当场抓到两个缺陷,都是我自己写的:**

- 屏 03 溢出 41px(稿子里「这局棋」和「对手」是一段,实现拆成了两段)。
- 「撑破了还滚得动」那条探针**本身是假绿**:填充块是 flex 子项,`flex-shrink` 默认 1,
  塞 1200px 进去被压扁,`scrollTop` 只写得到 3,而断言写的是「大于 0」。
  **探针自己被它要断言的那个布局改掉了。**

### ⚠️ 屏 02 余量只有 5.5px

任何一条文案在 460px 宽、11.5px 字下折成两行(≈17px)就会溢出。改这三屏文案时
请连着几何闸一起跑。溢出的后果不是崩:右栏会开始滚(已实测滚得动),
主行动键在滚动区外所以仍然贴底可见 —— 是降级不是断链。

---

## 4. 四图对比(`tests/kiosk-screen-02-04-setup.fourup.spec.ts`)

**参考图换了源。** `sample-go/shots/0{2,3,4}` 画的是改版前那三屏。新参考是通过的
那份稿子,渲染出的三张图收在 `visual/reference/` —— 参考图和实现同仓、同一次提交。

产物:`visual/0{2,3,4}-*/1024x600/*--{reference,implementation,side-by-side,diff}.png`

边缘计数(只是「参考图真读进来了」的证据,不是相似度分):
02 both=39143 / 03 both=52756 / 04 both=36625。

**看出来并改掉的三处**(用眼睛看的,不是数出来的):
- 组标题是「对手」不是「棋力」——这一组回答的是「跟谁下」,棋力只是它唯一的旋钮。
- 主读数念中文「6 级」不是 `6k`;紧凑写法留给右边的范围行(「共 29 档 · 20k – 9d」)。
- 赌注挪到「怎么坐」后面。

**留下的已知差异**(都写进图里的说明带了):
- 屏 03 对手那一格用的是 `KioskAiLadderOpponent`(它要带加载/出错/重试三态),
  稿子画的是已定档那一态的静止帧。
- 屏 03 用时默认「仅读秒 30秒×3」,稿子画的是「10分」——默认值是既有裁定,不动。
- 屏 04 实现取默认态(分先),稿子那一帧是让 2 子。
- 左盘木色:实现走 `KioskSetupBoard`,稿子走原型自己的 `gosvg`,两个渲染器。

---

## 5. 五条决策

Fan 授权派 agent 代决策。`setup-r2-decider` 的裁定**迟到但送到了**(它说前两次
SendMessage 返回 `success` 却没送达,第三次才收到)。在那之前我已按自己的证据拍了五条;
它的裁定到后逐条复核 —— **四条一致或被它补强,一条它的结论不成立**。

下面每条写的是**最终落地的那一版**。

### D1 · 「AI 赛规则」= KataGo 的 `aga-button` 预设,**只允许分先**

判据:`KataGo/cpp/game/rules.cpp:332-341` —— AREA + 情况超级劫 + `hasButton` +
`WHB_N_MINUS_ONE`,预设 komi 7.0,和 `docs/Analysis_Engine.md:82`、星阵贴 7 目三者一致。

**阻塞性前置(我已独立踩到并修了,见 `462e48b7`)**:`aga-button` 原来**不在**
`RULESETS_ABBR` 里,而 `engine.py:135` 查不到就回退 `japanese`,那个值经 `:254`
直接进引擎查询 ⇒ 不补那一行,这一档就是个静默按日本数目算分的假选项。

不用 JSON dict —— agent 补了三条我没查到的硬约束:
`models_db.py:355/:695`(`String(32)`)、`:720`(`String(64)`)对 **125 字符**的 JSON
⇒ PG 上截断报错、SQLite 不报错(本机全绿、生产炸);SGF 往返遇 Python repr 会
`JSONDecodeError` 而那个 `except` 是 `pass` ⇒ 又回 japanese;账本 `_normalize_rules`
(`ai_ladder_ranked.py:1413`)只 `casefold()`,键序一变就对不上。

**只允许分先(2026-09-21 改)**:`WHB_N_MINUS_ONE` 让 N 子白得 N−1 而中国规则是 N,
这 1 目在中文用户这里没有直觉支撑。原来我允许让子,按 agent 判据改掉了。

**`evenKomi: 7.0` 是我们自己的选择,不是引擎强制** —— katrain 每次显式发
`"komi"`(`engine.py:258`)覆盖预设,写 7.5 也不会报错。(agent 的补正,已采纳进注释。)

⚠️ **已知差异(非阻塞,待上板)**:button 规则下 KataGo 的第一次停一手**取走 button
并把 `consecutiveEndingPasses` 清零**(`boardhistory.cpp:947-951`),也就是终局要
三次停手;而 katrain 两处判据(`core/game.py:316`、`web/interface.py:118-126`)
都写死两次、不看 `hasButton`。后果是那半目之后少了一轮「免费」停手;盘面既然双停,
分数由 KataGo 在同一手上算出(button 已计入),**胜负不会算错**。
改它要连实体棋盘的双停流程一起想(摄像头/LED 怎么表达第三次停手),那条链的运行时
证据现在没有。两处都留了注释。

### D2 · 「猜先」在客户端掷

判据:`server.py:1230` 是 `human_bw = "B" if color == "black" else "W"` ——
**任何非 "black" 的值都会把人静默坐到白**,后端不认 `nigiri`;而升降级那条路是
`Literal["black","white"]` + `extra="forbid"`,加 `nigiri` 要改 pydantic 模型。

掷在客户端**不产生完整性差异**:执黑执白本来就是自由选择,自己掷和自己选等价。
已把用词对齐仓里既有的 `_resolve_color`(`platforms.py:50`)叫 `nigiri`。

### D3 · 前端送 0 + **kiosk 分支**兜底(agent 裁的是 `_do_new_game`,结论不成立)

agent 裁「后端兜底插进 `_do_new_game`」,理由是「兜底挡不住任何合法用法」——
那句是拿 **kiosk 的枚举**推出来的。核了 galaxy:`NewGameDialog.tsx:285` 和 `:305`
是两个**自由数字框**,让子和贴目没有任何耦合,而它走的正是 `_do_new_game`
(`server.py:1212` mode=="newgame")。在那一层归零 = 把用户亲手输的 6.5 悄悄改掉,
**方向和这次要修的毛病一模一样,只是反过来**。

⇒ 兜底放在 kiosk 那几个 mode 自己的分支(`server.py` 的 `_kiosk_game_terms`),
galaxy 一个字节都不动。条件 `>= 2` 不是 `> 0`(采纳 agent 判据:`HA[1]` 不摆子,
KataGo 的补偿判据也是 `blackTurnAdvantage <= 1 → 0`;「让先」是独立一档,
不该由这条规则管)。`_do_edit_game` 不加。

**变异实测**:把 `handicap >= 2` 改成 `if False`,`tests/web_ui/test_kiosk_game_terms.py`
当场红;还原后 7 条全绿。

**兜底的完整性有一条没人写着的前提**(agent 在认下 D3 时补的,已核):
这道兜底只长在 kiosk 那三个 mode 上,而 `POST /api/new-game`(前端出口
`src/api.ts` 的 `API.newGame`)**原样透传** handicap/komi 直达 `_do_new_game` ——
绕开它。今天 kiosk 侧零调用者(唯一调用者是 galaxy 的 `AiSetupPage.tsx:271`),
但这个前提哪儿都没写。哪天「再来一局」之类图省事用了它,让子局的 komi 兜底会在
那条路上**静默失效,而且失效的样子和正常的一模一样**。
⇒ 建 `src/kiosk/__tests__/kioskNewGameBoundary.test.ts` 把前提钉下来,
后端那段注释也点名了这个出口。**两个方向都变异过**:真调用当场红并给出可执行指引;
注释里提到 `API.newGame(` 不误报。

(agent 还补了一条我没提的:`_do_new_game` 的非 kiosk 调用者**不止** `NewGameDialog`
一条,还有 `/api/new-game` 和 `setupposition` —— 也就是说在那一层归零会同时打到三个入口,
我原来的判断只是更保守地估了一条。)

顺带按 agent 建议把 `color` 改成 fail-closed:不是 `black`/`white` 就 400。
`human_bw = "B" if color == "black" else "W"` 对任何别的值都落到白 ——
送 `"nigiri"` 进来不是 50% 坐白,是 **100% 坐白**。

### D4 · 「自定贴目」沿用 0.5 – 7.5、半目一档、15 档

判据:这是改版前那条轨的原范围(`KOMI_MIN=0.5` / `KOMI_STEP=0.5`),
对旧能力是**严格超集** —— 0 目归「让先」、负贴目归「倒贴」,原来那条轨本来也够不着。
不抄星阵的 ±100 目 101 档:那是研究用的量,不是 7″ 触屏上给人点的。

### D5 · 韩国规则只撤**新建局的选项**,读取能力全留;galaxy 不动

判据:KataGo 里 `korean` 和 `japanese` 是同一个 if 分支、逐字相同
(`cpp/game/rules.cpp:276`),只有 SGF 的 `RU` 标签不同。
galaxy 那两处(`ResearchSetupPanel.tsx:149`、`NewGameDialog.tsx:99`)**没有动** ——
它们是另一个构建产物,而且存量对局的显示路径(`utils/resultTranslation.ts:100`、
`ReportMetaPanel.tsx:30`)仍然认 `korean`,旧棋谱照常显示。
agent 的补充判据(已核):`src/components/NewGameDialog.tsx` 全仓只有
`src/ZenModeApp.tsx:14` 一个 importer,不进 kiosk 包 ⇒ **是范围问题不是构建边界问题**;
「7 寸屏上四个位置要塞下 AI 赛规则」这个理由在 galaxy 上不存在。

**按 agent 建议把 `RULES_HINT` 的 korean 加回来了**(零成本;读取面板复用时未知 key
会静默变空串),`RULE_LABEL` 也补了它 —— 新建局不给选,但旧棋谱读得出名字。

### 5.6 · agent 挖出来、原议题里没有的两条(都已修)

**① wire ≠ key 会让载入旧棋谱查表查空。** `RULE_LABEL` / `RULES_HINT` 的键是
`button`,写进 SGF 的是 `aga-button`,而载入是从 wire 回填 state
(`hooks/useResearchBoard.ts:222`)。另三条规则恰好同名,所以这个写法在加 button
之前一直看不出问题。补了 `ruleKeyFromWire()` / `ruleNameOf()`,**查不到原样回显**。

**② 研究页那条规则三元链本来就错。** `ResearchPage.tsx:537-539` 非 japanese/korean
一律说「中国规则」—— 今天一局 `RU[aga]` 就已经显示错了,而那句话的全部意义就是
「AI 是按什么规则算的」。改走查表。

**③(我自己的副作用)桌面 Kivy 规则下拉**会从 `RULESETS_ABBR` 里把 `aga-button`
一起列出来(`gui/popups.py:278`),而 `.po` 里每个规则名都有自己的 msgid、这一条没有
⇒ 屏上是个裸的 `aga-button`。已在那里过滤掉,桌面 GUI 保持改动前的样子。

---

## 6. 回归核验

**2026-09-21 合入 develop(165 个提交)之后重跑,基线换成 develop 本身。**
基线在 `git worktree add` 出来的独立树上跑 —— 不是把本树切过去,那会在别人正要查树时
把代码换掉。

| 套件 | 结果 |
|---|---|
| 前端单测 | **2193 passed / 0 failed**(合并前那 11 条红继承自旧基点 `66c6825d`,develop 上已修) |
| `tsc -b --force` | ✓ 干净 |
| Python | 4052 passed / 101 failed + 41 errors —— **142 条与 develop 基线名字集合完全一致**,新增 0、消失 0 |
| Playwright · 开局设置几何闸 | 6/6 过,数字见 §3 |
| Playwright · 屏 02/03/04 四图 | 3/3 过 |
| Playwright · `kiosk-shell-scroll` | 25 条里 3 条红(全是**摆谱**),**develop 上同样红、同一个选择器超时**;两条「开局设置」绿 |
| Playwright · 升降级阻挡/版式 A 四个 spec | 18 条里 2 条红,**develop 上同样红**(详见下面「两条容易误判的红」) |
| `npm run build` | ✓ |
| `npm run build:kiosk-2d` | ✓ `verify:kiosk-2d` 边界干净 |
| `kiosk-shell/MANIFEST.sha256` | 293/294 —— `tokens.css` 对不上,**是 develop 带进来的**(`3f3798c6` 改了它没更清单,清单最后一次更新在 `156e38c7`)。没动,记在 §7。 |
| eslint(本轮碰过的文件) | **0 条**。全树 91 条都在没碰过的文件里(develop 侧升级了插件)。 |
| 六条跨层闸 | `test_rules_wire.py`(含 config 自洽那条)· `test_kiosk_game_terms.py` · `kioskNewGameBoundary.test.ts` · `test_kiosk_i18n.py`(全树)· `test_kiosk_shell_manifest.py` · `emphasized.test.tsx`,**每条都做过变异实测** |

> **2026-09-21 第三轮之后复跑**:pytest 142 条与 develop 基线逐条同名,新增 0;
> Playwright 全量 **82 → 49**(名字集合零新增,17 条真修好);
> 前端单测 2198 passed;`tsc -b --force` 干净;两个构建绿;
> `kiosk-shell/MANIFEST.sha256` **294/294 OK**(那条 `tokens.css` 的漂已补)。

### 两条容易误判的红

`kiosk-ai-ladder-layout-a-geometry` 停在
`getByRole('button', { name: '○ 白' }).click()` —— 「○ 白」正是本轮换掉的那种分段控件,
**看起来百分之百是本轮造成的**。专门去 develop 独立树上量了一遍:同样红、同一行。
结论相反。

判据留在这里:**「这条红看起来和我的改动有关」不是证据,把基线跑出来才是。**
反过来同样成立 —— §6 那 142 条 Python 红全在我没碰过的文件里,
但那也不能当作「与我无关」的依据,一样是靠名字集合比对得出的。

> 基线跑法的坑:新 worktree 里 `uv sync` 缺 `--extra web`,不加的话 pytest 在
> collection 就全挂,`FAILED` 列表**静默为空**,一比就成了「全是新增」。
> Playwright 的基线要先 `kill` 掉 5173 —— `reuseExistingServer: true` 会让基线
> 读到当前树的代码。

---

## 7. 没做 / 留给 Fan

> **2026-09-21 第二轮**:Fan 点了四件(i18n / 合 kiosk-local-play v2 / config.json 贴目 /
> 板上实测)。前三件已办完,下面把**办完的**和**仍然没办的**分开写。

### 7.A 已办掉的(原来这一节记的)

1. ~~**i18n**~~ → **三屏已补齐**。96 个 key × 11 语种 = 1056 条,闸在
   `tests/web_ui/test_kiosk_setup_i18n.py`,变异实测三条分支各一次。
   **但见 7.B-1:kiosk 全树还欠 863 个。**
2. ~~**屏 04「终局死活两人自己确认」是过期文案**~~ → **合并带进来了**。
   `e92f15a1`(F7 五处文案)已在 develop 上,现在这条分支里是
   「自动数子,死活按引擎判断」。那条「动它会和 kiosk-local-play 撞车」的顾虑
   **前提已经不成立**:v2 的 `8107b138` 早就合进 develop 并 push 了,
   是我那条记录过期了。
3. ~~**`katrain/config.json` 自相矛盾**~~ → **已改回 `komi: 6.5`**(`b0acc6bc`)。
   查史:6.5 从 2024 年一直到 2026-02,`f06440c4`(2026-07-08 的一次 merge)
   把它变成 7.5 而没动 rules。
   **这个 bug 不在开局设置三屏上** —— 那三屏的贴目全由前端 `resolveGameTerms` 算完
   再送,日本规则恒 6.5,config 根本不参与。它伤的是**任何不显式送 komi/rules 的
   建局**:实测会话初始局改前是 `KM=7.5 RU=japanese`,`get_state()` 报
   `komi 7.5 / ruleset japanese`。更要紧的是这份包内 config 首次运行时会被**整份
   复制**成 `~/.katrain/config.json` —— 盒子上那份就是它。
   闸:`test_packaged_config_default_rules_and_komi_agree`,只认「这一对自洽」,
   不钉死具体数值(想改成中国规则 7.5 是正当的,连着改两个值就行)。

### 7.B 仍然没办的

> **2026-09-21 第三轮**:Fan 说「除了板上验收项,其他的缺陷继续修」。
> 原来这一节六条,现在只剩两条(板上 + push),其余四条办完,记在 7.C。

1. **板上没走**:RK3562 实机没验过。Fan 说稍后接入再测。
   板上要注意一件事:`.mo` 是 `.gitignore` 掉的,只有 `Dockerfile.web` 里那行
   `python3 i18n.py` 会生成。**盒子若不是从容器起的,就没有任何语种的译文** ——
   不只这两轮补的,是全部。`lang.py` 会往 stderr 打一行说明,屏上静默退回 msgid。
   **这条是本轮 i18n 能不能在板上生效的前置**,比译文本身更要紧。
2. **没 push、没合、没部署** —— Fan 说等前面几件办完再议。

### 7.C 第三轮办掉的四件

1. ~~**kiosk 全树还有 863 个界面字符串没进 .po**~~ → **全补完了**。
   872 个(重新数过,比上一轮估的 863 多 9 个)+ 5 条既有欠账 = 877 × 11 = 9647 条。
   闸 `tests/web_ui/test_kiosk_i18n.py` 随之从「三屏」放宽到 **`src/kiosk` 全树**,
   变异实测用的是**非设置屏**的 key,证明扩得真。
   顺带逮到全树唯一一处「一个 msgid 兼管两件事」(`grade:tabs`),另铸新键。
2. ~~**拆成五段/十段的拼句**~~ → 改成**一句一个 key**,强调写成 `<b>` 标记,
   由新的 `emphasized()` 渲染(不走 `dangerouslySetInnerHTML`:译文是运行时下发的,
   那等于把整条译文变成注入面)。五条单测含「粗体放句首」和「`<script>` 当字面文本」。
3. ~~**MANIFEST 与 tokens.css 对不上**~~ → **补上那一行,并把校验接进 pytest**。
   查清了:`472436f5` 改 `tokens.css` 时**连着重算了清单**(对的做法),
   下一次 `3f3798c6` 又改了却**没重算** —— 所以这不是误报,是补一个漏掉的动作。
   真正的病根是**那份清单从来没人在跑**(只写在 README 和计划文档里),
   新增 `tests/test_kiosk_shell_manifest.py`(295 条),三支变异各实测一次。
4. ~~**摆谱三条红**~~ → **不是「摆谱死页」,是夹具过期**,而且是一整族 17 条。
   `1d5f67a0`(盒子 SSO 第 4 层)把摆谱/死活/错题的存储改成按 `user.uuid` 分命名空间,
   **没同步改 e2e 夹具**:种子写裸键 + `/me` 不给 uuid ⇒ 两头都断,页面渲染它
   **正确的**空态,断言停在永远不出现的选择器上超时。
   **我上一轮把它错认成缺口账本里那条 P0** —— 页面好好的。
   新增 `tests/helpers/kioskIdentity.ts`,并顺带修掉三处与身份无关的过期锚/文案。
   Playwright 全量 82(develop 基线)→ 49,名字集合零新增。

### 7.D 第三轮顺带修掉、原来没记在账上的

* **图标契约**:本轮开局设置件里两处手写内联 `<path d=>`,被 `kiosk-shell-contract`
  抓了。下拉箭头换成共享的 `caret-down`;± 换回**配对的字形** `−`(U+2212)/ `+`(U+002B)
  —— Fan 最初报的「+/-号不居中」根因**不是「文本不行」**,是原来配了**全角** `＋`(U+FF0B)。
  真浏览器实测 dx=0 dy=0、宽 46,和画 SVG 那一版一模一样。
* **「默认值不许和 PO 说两回事」那条闸的 baseline 本来是空的,冒出来三条**(develop
  基线上同样红)。按该闸记着的 Fan 2026-08-26 裁定「PO 是正本」处理,
  其中两条是「一个 msgid 兼管两件事」⇒ 铸新键(`review:void_result` /
  `game:count_failed_retry`)。
* **两份 baseline 名单各划掉一行**:`TsumegoCategoriesPage.tsx` 两条闸都干净了,
  而那两份名单是**双向棘轮**,清干净却留在名单里一样要红。
