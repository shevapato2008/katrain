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
