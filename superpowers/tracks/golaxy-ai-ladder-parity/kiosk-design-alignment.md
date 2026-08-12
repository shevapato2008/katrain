# 挡局屏对齐共享外壳 —— 实测版

Fan 拍板两条（2026-08-11）：
1. **引 `tokens.css`，先只用于升降级这几屏**，其余 kiosk 屏不动；
2. **骨架照象棋 24 屏，配色用围棋青毡。**

---

## 0. 先说清楚问题不在这块面板

围棋 kiosk 的**颜色是对的**（`theme.ts` 里 `#58b57a` jade / `#0f1416` slate / `#18211f` raise /
`#2b3a35` hair / `#eef3f1` ice / `#93a49d` sub / `#e0a24a` amber / `#e2685c`，与设计稿逐字一致，
字族 Newsreader / JetBrains Mono 也是拍过板的）。

**错的是几何从来没接进来。** 另外三家 `main.tsx` 里都有：

```ts
import '@shared/kiosk-shell/assets/fonts.css'
import '@shared/kiosk-shell/assets/tokens.css'   // 991 行结构 token
```

围棋 grep **零命中**，`src/kiosk/` 下**一个 CSS 文件都没有**，154 个 kiosk 文件里 127 个走
MUI 默认尺度。共享外壳在 **smartbox 仓**，katrain 是另一个仓——**这条跨仓依赖从来没建立过**，
不是忘了 import。

## 1. 怎么引（katrain 是独立仓）

复制 `superpowers/shared/kiosk-shell/assets/{fonts.css,tokens.css,fonts/}` 进
`katrain/web/ui/src/kiosk-shell/`，**并把上游 `MANIFEST.sha256` 一起抄进来**。

抄 manifest 不是形式：复制品会漂，而漂了没人知道。有 hash 才能回答
**「我这份和上游还是同一份吗」**——和这一轮在部署域反复撞的是同一条判据。

⚠️ **token 只在 `.kiosk` 类上生效。** 渲染到 `.kiosk` 外面 `var()` 静默求空，
字体掉回 sans、`color-mix` 整条作废，**且不报错**（国象踩过）。升降级这几屏的根节点必须挂 `.kiosk`。

## 2. 骨架：照抄 `.ranked-state__*`

源：`superpowers/shared/kiosk-shell/sample-xiangqi/xiangqi-kiosk.tmpl.html:258-296`
参考图：`sample-xiangqi/shots/21-ranked-other-device-active.png`（**就是同一屏**）

```css
.ranked-state          { flex:1; min-height:0; display:flex; flex-direction:column; gap:12px;
                         border:1px solid var(--hair); border-radius:14px;
                         background:var(--panel); padding:16px }
.ranked-state__head    { display:flex; align-items:center; gap:12px }
.ranked-state__seal    { width:44px; height:44px; border-radius:12px; display:grid; place-items:center;
                         color:var(--accent); background:var(--accent-soft); border:1px solid var(--hair) }
.ranked-state__head h2 { font-family:var(--font-serif); font-size:22px; color:var(--text) }
.ranked-state__head p  { font-size:11.5px; color:var(--dim); margin-top:2px }
.ranked-state__status  { min-height:44px; display:flex; align-items:center; gap:10px; padding:9px 12px;
                         border:1px solid var(--hair); border-radius:10px; background:var(--paper);
                         font-size:12px; line-height:1.45; color:var(--text) }
.ranked-state__facts   { display:grid; grid-template-columns:repeat(2,1fr); gap:8px }
.ranked-state__fact    { min-height:48px; padding:8px 10px; border:1px solid var(--hair);
                         border-radius:9px; background:var(--paper) }
.ranked-state__fact span { display:block; font-size:10px; color:var(--dim) }      /* 标签 */
.ranked-state__fact b    { display:block; margin-top:2px; font-size:13px; color:var(--text) }  /* 值 */
.ranked-state__fact b.mono { font-family:var(--font-mono) }
.ranked-state__note    { font-size:11px; line-height:1.55; color:var(--dim) }
.ranked-state__actions { margin-top:auto; display:flex; gap:8px }                 /* 并排，贴底 */
.ranked-state__actions button          { min-width:44px; min-height:44px; flex:1;
                                         border:1px solid var(--hair); border-radius:11px;
                                         background:var(--paper); color:var(--text);
                                         font-size:13px; font-weight:600 }
.ranked-state__actions button.primary  { background:var(--accent); border-color:var(--accent);
                                         color:var(--paper) }
```

**状态前缀不靠颜色**（原注释：*状态同时用图形、标题与文字表达，不靠颜色*）：

```css
.ranked-state__status::before                      { content:"◆"; color:var(--accent) }
.ranked-state__status[data-tone="error"]::before    { content:"!"; color:var(--bad); font-weight:700 }
.ranked-state__status[data-tone="progress"]::before { content:"◌"; color:var(--accent); font-size:18px }
```

这条和本轮那条判据同族：**一个信息不许只走一个通道**。

## 3. 现在这屏和参考差在哪（不只是 token）

看真图 `21-ranked-other-device-active.png`：右栏从上到下是
**seal + 大衬线标题 + 小副题 → 状态条（带 `!` 前缀）→ 两列事实格 → note → 贴底并排双按钮**。

| | 参考 | 现在 |
|---|---|---|
| 中段 | **两列事实格，摆具体数字**（失联阈值 30 秒 / 当前阶段 已超过阈值） | **空的** |
| 动作 | 并排、贴底、等宽 | 竖排堆叠 |
| 标题 | 衬线 22px + seal 图标 | 无衬线、无图标 |
| 状态 | 独立状态条 + `!` 字符前缀 | MUI Alert |
| 徽标 | 事实格（有标签有值） | MUI Chip |

**中间空得像没加载完，根因在这里**：参考用事实格把中段填满，我这屏没有这一层。
而围棋这屏本来就有可摆的事实——**档位 / 执色 / 开局时间 / 心跳距今 / 已重试次数**。
补上它同时解决「空」和「信息不足」两件事。

## 4. 两处要标成开放问题，不许我们自己定

**① 破坏性按钮的长相，三家现在是两派。**
- 象棋模板：屏上 `.primary` = 实心 accent（**即使它是「按认输结束」**）；
  真正变红是在**二次确认框**里（`.ranked-confirm__actions button.primary { background: var(--bad) }`）。
- 国象 `.rated-primary.is-destructive` 与围棋现版：**屏上就描边**。

两派都自洽，但不能同时成立。模型差异是：*吓人吓在屏上，还是吓在不可回头那一步*。
**这条归 Fan，不由我们三家私下约。**

**② 挡局时左边画不画盘。** 参考图画了完整棋盘（起始局面）；围棋现版换成了虚线空态
（「这台机器上没有那一局的盘面 / 不是加载失败」）。参考那样画等于摆一个**不是这一局**的局面，
围棋这版更诚实但更空。**要 Fan 看图定。**

## 5. 不要动的

承重结论原样保留：`overflow-y:auto` + `scrollTop` 真能推 那条闸不改。
**改的是外观 token，不是盒子链**——但改完余量数一定会变，四图和余量表都要重打。

---

## 6. galaxy 那一侧的欠账(2026-08-11 记,**这一轮不做**)

kiosk 改版是关键路径,galaxy 不回头开工。以下三条只登记,等 Fan 把 kiosk 定了再一并处理。

### ① galaxy 的**四图闸没过**,而且再多拍实现图也补不上

`visual/blocking-exits/simplified-1440x900/` 里只有 `*.png` 和 `*--panel.png` ——
**没有 `--reference` / `--side-by-side` / `--diff`**。那三类只存在于已废的 `1440x900/` 里。

所以准确的说法是:**图是新的 ✔,四图闸没过 ✘**。缺的那一张是**参考图**,
而现有参考稿 `mockup.html` 描述的是**已废的两出口模型**。

> 「重跑零字节变化」证明的是**实现图与代码同步**,不是**视觉闸通过**。

⇒ galaxy 这一轮**没有参考稿**。它的参考从哪来,等 kiosk 定了一并决定。

### ② `1440x900/` 与 `galaxy-ai-ladder-blocking-exits-fourup.spec.ts`:**留着,但不能被静默读成当前**

那套图和那条 spec 的 `PAIRS` 一起停在**简化之前的两出口模型**上
(`04-active-other-takeable` / `06-pending-releasable` —— 接管窗口与放弃窗口今天都不存在)。

**比"过时"更阴的一点(已核实)**:那条 spec 全文只有两处 `page.goto`,都是
`pathToFileURL(MOCKUP)` —— 它**读的是稿子 + `1440x900/` 里的旧面板图,一次都不碰当前代码**,
却能跑绿并写出一张「四图对照」。

⇒ 这正是变异三层里的**第 2 层:打中了,但根本没到达被测物**。
下一个人(或下一个 agent)会把那张 diff 当回归信号读。

下次谁手碰 galaxy 时顺手做两件小事(现在别做):
- 那条 spec **开头 `test.skip` 并写明理由**(参考稿描述的是已废模型);
- `1440x900/` 里放一行 README,说清它对应哪个模型、被谁取代。

### ③ galaxy 最大的字是段位名、kiosk 是问题句 —— **先不拉齐**

不是「保持分歧」,是**现在没有可判据的图**:象棋骨架的 head 是 seal + 衬线 22px 标题 + 小副题,
kiosk 改完之后「最大的字」是什么本身就变了。等有图了,这问题要么自己消失,要么才第一次成立。

---

## 7. 「自动最小尺寸吃掉你为溢出准备的那条出路」——**这是一族,两根轴上各有一个**

这一轮在同一个概念上栽了两次,轴不同、症状不同、修法同一个。写在这里而不是只留在代码注释里,
因为下一个搭这类面板的人会在**另一根轴**上再踩一次。

> flex / grid 子项的**自动最小尺寸**(`min-*: auto`)会让它**拒绝收缩到内容尺寸以下**。
> 于是你为「装不下」准备的那条出路——滚动、省略号——**永远没有机会生效**,
> 而失败长相是「内容被祖先硬裁」,不是你设计的那种优雅降级。

| 轴 | 默认值 | 被吃掉的出路 | 实测长相 | 修法 |
|---|---|---|---|---|
| 纵向 | flex 子项 `min-height: auto` | `overflow-y: auto` | 面板把父容器撑破,再被父容器 `overflow: hidden` 裁掉;**按钮不见了** | 该滚的那一层加 `min-height: 0` |
| 横向 | **grid** 子项 `min-width: auto` | `text-overflow: ellipsis` | 300 字的档位名把 `<b>` 撑到 **3900px 宽**(视口才 1024),**一个省略号都没有**,纯靠祖先硬裁 | 格子加 `min-width: 0` |

两条附带的坑,也都是量出来的:

1. **`overflow` 一旦不是 `visible`,那一层的 `min-*: auto` 自己就解析成 0。**
   所以「三处 `minHeight: 0` 都不能省」是错的 —— 叙述区自带 `overflow-y: auto`,那一处是**冗余**;
   真正承重的是**面板根**(它 `overflow: visible`)。我一开始把这句写反了,是变异掉那一处、
   9 条全绿才发现的。**判断哪一处承重,先看那一层的 `overflow`。**
2. **判据要跟着轴走。** 纵向截断验 `scrollHeight > clientHeight`,横向截断验
   `scrollWidth > clientWidth`。轴换了而断言没换,会红在一个不存在的缺陷上
   (实测:改成横向省略号之后,那条纵向断言的两个数都是 20)。


---

## 8. follow-up:`SmartBoardConsole` 与样稿的三处出入(2026-08-12 定,**这一轮不动**)

那块卡是**共享的**(`/kiosk/play` 也在用),改它就把这一刀切到 Fan 没要求的屏上去。
只修了其中一条**真 bug**(盘上压字读不出来:深色字压木色 ⇒ 改浅字 + 更实的深衬),
其余三处记账:

| 出入 | 现状 | 样稿 |
|---|---|---|
| 宽度 | 322px,MUI 自绘 | 外壳 `kiosk-console` 296px(`--l1-rail-w`) |
| 标题 | 智能棋盘 / Live board | 实体棋盘 / Camera board |
| 同步行 | **没有** | 盘面与屏幕一致 · 刚刚同步 |

判据:**记下来比现在改值钱** —— 改一块共享卡要连它的另一个消费者一起验,而那不在这次范围里。

## 9. 本地补丁:上游 `tokens.css` 缺 `.kiosk-status__cell { min-width: 0 }`

grid 子项默认 `min-width: auto` ⇒ 格子拒绝收缩到内容宽度以下 ⇒ `text-overflow: ellipsis`
**永不生效**(实测把值撑到 3900px 宽,视口才 1024)。这是**外壳自己的类,四家都会踩**。
我们在 `blockingPanel.css` 里本地补了 —— **上游修了就删这条本地补丁**。

## 10. 记账:副本侧那道闸围棋一层都没有

- `superpowers/shared/kiosk-shell/scripts/verify-assets.sh` **围棋根本没接**;
- 就算接了也只答「我这份副本自己没被人动过」—— 因为 `assets/` 和 `MANIFEST.sha256` 是
  **一起抄**的,上游换了图、上游 manifest 跟着重算,我这边两个都还是旧的、**还互相自洽**。
- 要答「我这份**还等不等于**上游那份」,得**把上游 `MANIFEST.sha256` 文件本身的 sha256 再钉一次**。

不做,记账。

---

## 11. 字体(A 块,2026-08-12 做完)

抄了 `fonts.css` + `fonts/`(194 霞鹜文楷分块 + 8 拉丁/品牌 woff2 + 4 份 OFL,9.5MB),
`MANIFEST.sha256` 209 行在本地 `shasum -c` **209/209 OK**。

**上一版「故意不抄字体」的判断是错的**,理由在 `kiosk-shell/README.md` 里逐条留着没删。
一句话:那条理由(「`tokens.css` 全文 `url()` 只有两处,不引字体」)**是真的,但答的不是被问的问题** ——
字体从来不是靠 `url()` 进来的,是靠 `--font-*` 三个变量指向 `fonts.css` 声明的族,而我们把那三个变量覆盖了。

### 11.1 「删掉覆盖的三行」不是生效点

MUI 组件走 `typography.fontFamily`(emotion 类),**不读 `var(--font-*)`**。只删
`go-tokens.css` 那三行,屏上一个字都不会变。真正的生效点是 `kiosk/theme.ts`。

**而它也只是生效点之一**:kiosk 里另有 **22 处 `sx={{ fontFamily: … }}`(15 个文件)**绕开主题
直接写字体栈 —— 品牌行、问候语、各页标题、棋钟、SGF 文本。字体闸第一次跑出来的就是它们:
「智星盒」「晚上好」还落在 **Songti SC(40 字)**、触屏键盘落在 **PingFang SC(35 字)**。
现在全部 import `theme.ts` 导出的 `KIOSK_SANS/SERIF/MONO`。

`public/smartkeyboard.css` 也改了(它不是 React,原来写死 `-apple-system, "PingFang SC", …`):
`"SmartBox Kai"` 放最前、系统字保留在后 —— **这个文件 galaxy 也加载,而那边没有 `fonts.css`**。

### 11.2 闸:方法照抄上游,作用域不照抄

上游 `scripts/check-fonts.mjs` 把探针页写进 `assets/` 再量 —— 它量的是**资产包自己**。
抄过来跑只能证明「这份副本内部自洽」,证明不了「我们屏上的中文由谁画」,
**和 §10 那道闸是同一个形状**。所以新写了 `tests/kiosk-font-routing.spec.ts`:
同样用 CDP `CSS.getPlatformFontsForNode`,但探的是**真页面上真正带文字的叶子元素**(逐个问再合并)。

> 写这条闸时先错了一版:在 `body` 上问一次,报「一个都没有」。
> 该命令只统计节点**自己的直接子文本节点**,不递归,而 `body` 底下全是元素。
> **那次红是闸自己写错了,不是页面坏了** —— 同一次跑里「真 Bold 面已加载」是绿的。

三条:中文命中霞鹜文楷 / 退役字库与系统 CJK 字一个都不许出现 / 龙藏覆盖字数 ≤ 3。
第二条比第一条强:「楷体在场」和「所有中文都走楷体」是两回事。

### 11.3 三条记账(都不在本轮范围)

1. **galaxy 早就自托管了霞鹜文楷**(`src/galaxy/assets/fonts/galaxy-fonts.css`,48 个分块,
   族名 `wenkai-400/500`)。同一个字体在一个仓里有两份、两套族名、两套分块粒度。
   要不要合并是**另一个决定**,合并会动 galaxy 的排版。
2. `package.json` 里 `@fontsource/{noto-sans-sc,hanken-grotesk,newsreader,jetbrains-mono}`
   现在**没有任何 import 引用**。没删:删要动 lockfile,风险大于收益。
3. 键盘上那个 `⌄`(U+2304)落在 **Menlo** 上 —— 我们的字体里没有这个字形。
   它是符号不是中文,闸放行了。真要管得给键盘换个图标。

---

## 12. 布局 A(C 块,2026-08-12)

开局设置屏从「通栏返回条 + 296 镜像栏」改成规范 §11 **布局 A**。
依据 `:399`(L2/L3 可用高 516、盘 516×516 贴 x16、右栏 x548–1008 宽 460)与
`:510-512`(「开局设置是对局的前一步,走布局 A,和对局屏同一个骨架」)。

**上一版错在把 §5 的 L1 构件搭在了一屏 L2 上** —— `SmartBoardConsole` 是 296 的**摄像头镜像栏**
(`:139`),它属于 `/kiosk/play`;而通栏页控条是**布局 B**(无棋盘)的做法(`:742-743` 两行搞反)。

实测(真浏览器 1024×600,`tests/kiosk-ai-ladder-layout-a-geometry.spec.ts`):
盘 `516×516 @(16,70)`、落子区 `460×460 @(44,98)`、右栏 `460 @x548`、
页控条 `460×44 @y70`、返回按钮高 `36` —— 规范给的数**一次全中**。

### 12.1 左栏画的是「开局局面」,不是镜像

`:512`:「左边那块盘画的是**按下按钮后真会出现的那个局面**,视角跟着执棋方翻」。
围棋的起始局面就是**空盘**,所以一颗子都不摆 —— 空不是占位,是答案。
黑白两种执子**各取一张**(`visual/kiosk-layout-a/1024x600/01-…-black.png` / `02-…-white.png`),
不靠「另一种应该也对」。

### 12.2 没复用 `LiveBoard`,理由是数

`LiveBoard` 的 `calculateBoardLayout` 写死 `gridMargins = 1.5 格`
(`components/board/boardUtils.ts:34`),规范 `:432` 要 **0.5 格** —— 差的是**整整一格(≈24px)**,
不是几个像素。改共享组件的边距会动到 galaxy 和对局屏,blast radius 远大于自己画一块空盘。

### 12.3 本地补丁 ②:刻度轨道等分 —— **常驻,不是等上游**

`tokens.css:607-616` 只写了 `display:grid` + `grid-auto-flow:column`,轨道按**字宽**取尺寸。
围棋 `M` 比 `J` 宽 ⇒ 字心不落在 `(i+0.5)/19` 上,**实测最大错开 2.8px**,补成 `1fr` 之后 **0**。
它是被闸抓出来的 —— 外框那 8 个数一次全中,唯独这条差 2.8px。

🔴 **上一版把它判成「上游缺口,上游修了就删」,那是错的。** 象棋在真浏览器上量了两个数推翻它:

| | 实测 | 说明 |
|---|---|---|
| 象棋现状 | 字心 vs 竖线错开 **0.02px** | 轨道确实是 `auto`,但装的是 `1`–`9` / `九`–`一`,**同族等宽**,`auto` 被拉伸成等分 ⇒ 那个缺陷在它身上**不产生后果** |
| 象棋若收 `1fr` | **第一条字偏出 26px** | 象棋盘**不占满落子区**(8:9 比例 `xMidYMid meet` 居中,盘宽 356.2),轨道 9×44.53 = 400.8 与盘**节距同为 44.53、逐条重合**;`1fr` 后轨道撑满 460、节距 51.11,盘仍 44.53 |

⇒ **这不是上游缺口,是共享类覆盖不到的一格。** `.kiosk-board__ruler` 只能定「四条带都在」,
定不了轨道尺寸 —— 轨道尺寸取决于**盘占不占满落子区**:占满(围棋/五子棋)⇒ 等分;
按真实比例居中、盘比落子区窄(象棋)⇒ 跟着盘的节距。**两边正确的值不是同一个数,上游收敛不了。**

**该往上游提的是那条不变式,不是 `1fr`**:

> **刻度带的节距必须等于盘的线节距。** 判据是**屏上那条线的横坐标**,
> 不是「字心应该落在 `(i+0.5)/N`」那个版式规则。

最后半句是象棋踩出来的:它第一版探针拿版式规则当判据,套到自己身上量出「最大错开 26px」——
**数字漂亮、结论全假**。而那个 26 恰好就是「把 `1fr` 收进上游之后会真实出现的错位」。
**同一个数,一次是模型错、一次会是真缺陷**,分开它们的唯一办法是去量屏上那条线。

**国象和五子棋未量**(不要替它们写「大概率占满」)。

> 顺带对 §9 那条(`.kiosk-status__cell { min-width: 0 }`)的口径也收一下:
> 它**没有被同样验过**。它现在仍按「上游缺口」记,但那是**未验证的判断**,
> 不是像这一条一样被两个数确认过的结论。

### 12.4 与稿子的唯一出入:没抄木纹贴图

稿子在木色渐变之上叠了一层 `--oak`(`mix-blend-mode:multiply`),那张图在
`sample-go/board-assets.json` 里、**不在共享资产包、不在 MANIFEST 管辖内**。没抄 ——
抄它等于往仓里塞一份没人核的二进制。要对齐得先把它收进资产包。

### 12.5 跟进项

- **另外 17 屏还在用 `SubPageBar`**(通栏返回条)。这一轮只换了 `AiSetupPage`——
  换共享组件等于 18 屏返工,远超本次交付价值。**它们也该走 `.kiosk-pagebar`**,登记在此。
- 「盘面预览」那行眉标随旧预览盒一起没了。布局 A 的左栏只有盘(`:512`),**这是布局裁定的
  后果,不是改文案** —— 但它确实是一处可见文字的消失,记在这里备查。
- 实测发现 `用时` 那格屏上显示「仅读秒」而代码里的中文默认是「仅读秒 30秒×3」:
  差别来自**服务端翻译表**,不是截断(`scrollWidth == clientWidth == 225`),也不是本轮改动。

---

## 13. 刻度不跟着执棋方翻(2026-08-12 裁定)

`:514`「视角跟着执棋方翻」在围棋上会把**绝对坐标**改错。**这不是给规范开例外,是规范里
更具体的那条本来就管这件事** —— 写理由要按这个顺序,不要写成「我认为规范错了」:

1. **§8 `:414` 已经立过刻度方向的法,依据就是记法**:「象棋两条刻度数值不同向…
   **看到某个实现把上面那行也写成 9…1,那是错的**」⇒ **刻度是记法的函数,不是执棋方的函数**;
2. 围棋记法**绝对**(A1 永远是那一个角,SGF、棋谱库、对局屏都按它)⇒ **不倒**;
3. `:514` 那句是从**国象**推出来的(v1.21 改动记录自陈),而 `sample-go` 里**根本没有开局设置屏** ——
   这条规则从来没有被它的作者在围棋上应用过。

⇒ 本仓按 §8 `:414` 执行;**`:514` 的措辞由协调方提请上游澄清**(那份文档四家共读,住在象棋
worktree,不是这里能改的)。措辞方向:「视角跟着执棋方翻;**刻度方向仍按 §8 由该棋种记法定**,
记法绝对的棋种(围棋)不倒」。

> ⚠️ 一句**不要复用**的错话:我先前写过「围棋空盘 180° 完全对称,所以翻不翻都一样」。
> **空盘对,让子局不对** —— 3 子让子是右上/左下/左上,转 180° 变成左下/右上/右下,
> 不是同一个局面。结论不变(反而更硬),但理由是**记法绝对**,不是图形对称。

## 14. `.kiosk-optseg` 接上了;`.kiosk-opthint` 没用,理由在下面

「我执」原来走本地 `OptionChips` 自绘的两颗独立圆角按钮 + 一道缝,而外壳里**本来就有**
`.kiosk-optseg`(`tokens.css:691`,象棋稿 `:602-607` 就是这么用的)。
**这和 §7 那次是同一个形状:类抄进来了,页面又自己造了一个。**

改的是**共享组件本身**而不是只改这一屏:它的另一个消费者 `PvpLocalSetupPage` 自陈
「mirrors AiSetupPage's canonical kiosk setup skeleton」,只改一屏等于把不统一固化下来。
组件根节点自己挂 `.kiosk` —— `tokens.css` 整份定义在 `.kiosk {}` 里,不在它下面 `var()`
**静默求空**;挂在自己身上就不依赖调用方的祖先链。

**没用 `.kiosk-opthint`**:它是给「分段格塞不下副标题、但说明不能丢」的组用的,
而这里两个选项(「● 黑」/「○ 白」)本来就没有副标题,补一行等于**新写文案**,本轮文案冻结。

顺带:`.kiosk-seclabel` 的四条子元素样式从 `blockingPanel.css` 搬到了
`kiosk-shell/seclabel.css` —— 现在有两个消费者,留在其中一边就会变成「另一边导入了类却没样式」。

## 15. 布局 A 的四图:参考物换了,理由在这

协调方点的参考是 `sample-xiangqi/shots/21-ranked-other-device-active.png`(象棋**挡局屏**)。
换成了 **`02-setup.png`(象棋自己的 L2 布局 A **开局设置**屏)**,因为
`01-setup-my-black` 是**常态开局设置屏**:参考物要和被参考的东西**是同一类屏**,
挡局屏那一类的参考已经在 `kiosk-ai-ladder-vs-xiangqi-reference.spec.ts` 里对着围棋挡局屏。
上一轮四图被打回的原因正是**参考物不对**。

差异图用的是**边缘图**不是像素比:两屏一个米黄浅色一个青毡深色,**基调不同是规范要求的**,
直接比亮度会整屏通红,只能证明「两种棋类配色不同」。边缘图去掉颜色只留结构:
**红 = 只有参考有边,绿 = 只有实现有,白 = 两边都有**。

> ⚠️ **「已认证」是 fixture 造的态**:`katrain/core/ladder.py:541` `_CERTIFIED_RUNGS` 是**空集**,
> `:553` 的 `certified` 恒 False,真机上这个徽章**永远不会出现**。
> 这句话写进了**图里的标签带**,不是写在文档旁边 —— 合成态一旦离开它的说明,
> 「界面对不对」和「后端有没有」就混成一件事,以后会有人指着这张图说「认证链是通的」。

---

## 16. 取图侧:按快门之前等**真像素**(2026-08-12)

`waitForSelector('canvas')` / `toBeVisible()` 只证明**元素在**。`LiveBoard`
(`components/live/LiveBoard.tsx:339-358`)先 `Promise.all` 预加载 **5 张 PNG**,
全部 `onload` 才 `setImagesLoaded(true)`,而绘制 effect 挂在这个标志上 ——
**图没到齐之前一笔都不画**。

实测(`/kiosk/play`,同一份代码连开 6 次):元素出现那一刻 **4 次空、2 次已画**;
1200ms 后 **6 次全部已画**;canvas 尺寸每次都对(400×400 / CSS 274)。
⇒ 约六七成的截图会是**空盘**,而空盘和「盘真的坏了」在图上分不开。

新助手 `tests/helpers/canvasPainted.ts`,判据是**非黑采样点**。
**当前唯一消费者是 galaxy 那条结算图**(`galaxy-ai-ladder-game-visual.spec.ts`)——
kiosk 开局设置屏改布局 A 之后左栏是**内联 SVG**,没有图片加载、没有这个竞态。
B 块给 `/kiosk/play` 取图时会是第二个。

### 16.1 这条竞态**曾经被误判成回归**

`92cfaae9` 的图有盘、`1a211a25` 的没有,一度被归因给字体那批改动。
**一张空白截图不携带「谁让它空的」** —— 两种解释(真回归 / 撞上竞态)长得完全一样,
一边一个样本的对照**没有分辨力**。连开 6 次才是能分辨的对照。
字体那批**不在这条链上**(挡着绘制的是 5 张 PNG 的 `onload`);
它有没有把概率推高一点 —— **未量,按未确定记**。

### 16.2 产品侧的兜底:记账,挂到**设备走查**

`boardUtils.ts:90-96` 的 `drawBoardBackground` 有 `#dcb35c` 木色兜底,但**永远轮不到** ——
整个绘制被 `imagesLoaded` 挡在外面。**那个兜底答的是「图加载失败了」,答不了「图还没到」。**
和「空集 / 合成 seed / False / 没部署 是同一件事四张脸」同族:**两种「没有图」被当成了一种。**

修法(把兜底提到闸前面:图没到时先画木色 + 格线,到了再覆盖)**这轮不做**,两个理由:
1. `LiveBoard` 是**共享组件**(galaxy + 对局屏都在用),改绘制时序的 blast radius 超出本切片;
2. 「板子上冷启动也会空一下」这句是**推的,不是量的** —— 5 张本地 PNG 从本机服务端拉,
   RK3562 慢不慢**没人量过**。

⇒ **挂到设备走查**:上板时专门看一眼 `/kiosk/play` 冷启动那块卡。
**量到了就是真 bug,量不到就是取图机器特有的。**
