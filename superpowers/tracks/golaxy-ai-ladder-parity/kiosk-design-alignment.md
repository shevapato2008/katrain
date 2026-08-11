# 挡局屏对齐既有设计稿

来源：Fan 的《智星盒 · 围棋 · 全模块设计稿 · 样板（十屏）》
（artifact `e4d3c7ef-82dd-4a5e-a7b0-42db6b4ad731`，本机副本见 `tool-results/artifact-e4d3c7ef-*.html`）。

**这份稿不是参考，是已生效的设计系统。** 它有命名 token、命名组件、以及写在 CSS 注释里的
取舍理由。挡局屏此前按 MUI 默认样式做，等于绕开了它。方向不需要重新生成——**照抄**。

稿里第 ⑥ 屏「成长」下面直接有一节叫**「升降的规矩」**，就是本模块。国象那套 460×516
的取图用的正是本稿的 `--rail-w`，所以不统一的是围棋这一侧。

---

## 1. Token（照抄，不要另起名字）

```css
--kiosk-w: 1024px;  --kiosk-h: 600px;        /* 目标 viewport，与承重取图一致 */
--topbar-h: 56px;   --pagebar-h: 44px;  --content-top: 70px;
--content-w: 992px; --content-x: 16px;  --content-h-l2: 516px;
--rail-w: 460px;    --rail-x: 548px;    --rail-gap: 12px;   /* 右栏就是这一列 */

--ink:  #0F1416;    /* 页底 */
--panel:#18211F;    /* 卡片底 */
--raise:#1D2725;    /* 卡片内再抬一层（.row 用） */
--hair: #2B3A35;    /* 唯一的描边色 */
--text: #EEF3F1;    /* 正文 */
--dim:  #93A49D;    /* 次要信息、区块标题 */
--accent:#58B57A;   --good:#58B57A;  --warn:#E0A24A;  --bad:#E2685C;  --info:#5B9BD5;

--fs-page-title:26px; --fs-section-title:17px; --fs-card-title:16px;
--fs-body:13px; --fs-card-sub:12px; --fs-eyebrow:11px;

--btn-primary-h:44px;   --btn-primary-radius:11px;   --btn-primary-pad-x:20px;
--btn-secondary-h:38px; --btn-secondary-radius:10px; --btn-secondary-pad-x:16px;
--primary-action-h:48px; --primary-action-radius:12px;

--font-sans:  "SmartBox Sans", …;
--font-serif: "SmartBox Serif", "SmartBox Kai", "Kaiti SC", Georgia, serif;
--font-mono:  "SmartBox Mono", ui-monospace, monospace;
```

## 2. 组件（用稿里的，不要自造同类）

```css
.panel     { border:1px solid var(--hair); border-radius:12px; background:var(--panel); padding:14px }
.panel > h3{ font-size:11.5px; font-weight:700; letter-spacing:.14em; color:var(--dim) }
.empty     { border:1px dashed var(--hair); border-radius:12px;
             background:rgba(29,39,37,.55); padding:14px }
.empty h4  { font-family:var(--font-serif); font-size:15px; font-weight:600 }
.empty p   { font-size:11.5px; color:var(--dim); line-height:1.55 }
.row       { height:52px; flex:none; border:1px solid var(--hair); border-radius:10px;
             background:var(--raise); display:flex; align-items:center; gap:12px; padding:0 12px }
.row .lead { font-family:var(--font-mono); font-size:12px; color:var(--dim); width:46px }
.row h4    { font-family:var(--font-serif); font-size:14px; font-weight:600 }
.tag       { font-size:10.5px; letter-spacing:.08em; padding:2px 8px; border-radius:999px;
             border:1px solid var(--hair); color:var(--dim) }
.tag.win{color:var(--good)}  .tag.loss{color:var(--bad)}  .tag.live{color:var(--bad)}
.note      { font-size:11px; color:var(--dim); line-height:1.5 }
.wip       { font-size:9.5px; letter-spacing:.06em; color:var(--warn);
             border:1px solid rgba(224,162,74,.45); border-radius:999px; padding:1px 7px }
.wip.have  { color:var(--info); border-color:rgba(91,155,213,.5) }
```

## 3. 现状与稿的差距（挡局屏，逐项）

| 维度 | 稿 | 现在的实现 |
|---|---|---|
| 卡片 | `.panel` hair 描边 / r12 / `#18211F` | MUI Paper 默认 |
| 区块标题 | **11.5px / 700 / ls .14em / dim** | 22px 大标题 |
| 正文 | 13px | MUI body1 / body2 |
| 空态 | `.empty` **虚线** + 衬线 h4 15px + p 11.5px | 自造的实线盒子 |
| 徽标 | `.tag` 10.5px / r999 / hair 描边 | MUI Chip（明显更大更重） |
| 按钮 | primary h44 r11；secondary h38 r10 | MUI 默认 |
| 字体 | 标题走**衬线**，正文 sans，编号走 mono | 全 sans |
| 「还不能用」 | `.wip` 琥珀／`.wip.have` 蓝，**两种原因两个色** | 无此概念 |

## 4. 一个结构判断（这不是缩小字号的问题）

稿里正文区最大的字是 `.empty h4` / `.row h4` 的 **14–15px 衬线**；26px 只属于 pagebar。
所以「把 22px 标题改小」是错的解法。**正确的解法是：挡局屏整块就是一个 `.empty`。**

`.empty` 的定义写在稿的注释里——*「后端还没有的模块，给一个说清楚**为什么现在是空的**的块，
不摆假数据」*。挡局屏要做的正是这件事：说清为什么现在开不了新局。它不需要一个大标题，
它需要 `.empty` 的 h4 + p，外加一组动作按钮。

## 5. 一条要搬进来的语义

`.wip` 那对颜色是这一轮那条判据的设计层写法：

> 琥珀 = **后端根本没有**这块东西；蓝 = **后端已经有了**，界面还没接上去。
> 不标就等于默认它已经能跑。

挡局屏的三态同族：`reserved`（从没开起来）／`active·远端`（在别的机器上）／
`pending_settlement`（下完了没送到）——**三种「拿不到盘面」的原因不同，代价也不同**。
现在三格共用一句「这台机器上没有那一局的盘面」，按 `.wip` 的口径这是欠区分的。
是否分色由取图后再定，但**不能因为长得一样就当成一回事**。

## 6. 不要做的

- 不要引入稿里没有的色（尤其不要再加一个绿以外的强调色）。
- 不要用 MUI 的默认 `Alert` / `Chip` / `Button` 外观——它们自带一套与本稿冲突的尺度。
- 不要动承重结论：`overflow-y:auto` + `scrollTop` 可推动那条闸原样保留，
  改的是外观 token，不是盒子链。改完必须重跑，**余量数会变，要重打**。
