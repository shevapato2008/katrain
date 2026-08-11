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
