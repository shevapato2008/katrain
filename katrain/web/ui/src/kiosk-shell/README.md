# kiosk-shell —— 从 smartbox 共享外壳抄进来的那一份

katrain 是独立仓,拿不到 `@shared/kiosk-shell`(那在 smartbox 仓),所以这里是**复制品**。

上游:`smartbox-software-xiangqi-features/superpowers/shared/kiosk-shell/assets/`

## 抄了什么

| 文件 | 为什么 |
|---|---|
| `tokens.css` | 991 行结构 token。**这才是围棋缺的那一块** —— 颜色本来就对(`kiosk/theme.ts` 的 jade/slate/raise/hair 与设计稿逐字一致),缺的是几何。 |
| `icons/house.svg` | `tokens.css:338` 用 `mask: url("./icons/house.svg")` 引它。不抄的话那条 mask 静默失效(和 `var()` 求空一样不报错)。 |
| `fonts.css` + `fonts/` | 规范 §9 定死的字族。202 个 woff2(194 个霞鹜文楷分块 + 4 Geist + 2 Newsreader + 1 JetBrains + 1 龙藏)+ 4 份 OFL 许可,共 9.5MB。 |

`MANIFEST.sha256` 共 **209 行**,hash 全部取自上游 `MANIFEST.sha256`(去掉 `assets/` 前缀),
在本目录 `shasum -a 256 -c MANIFEST.sha256` **209/209 OK**(2026-08-12 实跑)。
抄 hash 不是形式:复制品会漂而没人知道。

> ⚠️ 但要说清这道闸**答得了什么**:`assets/` 和它的清单是**一起抄**的,所以在这里跑它只证明
> **「我这份副本自己没被人动过」**。上游换了图、上游清单跟着重算,我这边两个都还是旧的、
> 还互相自洽,**闸照样绿**。要答「我这份还等于上游那份吗」,得再把**上游清单文件本身的
> sha256** 钉一次。那一条还没做,记在 `kiosk-design-alignment.md` §10。

## 曾经**故意没抄**字体 —— 那条判断是错的

上一版这里写着「`fonts.css`(204KB)和 `fonts/`(9.5MB)没抄」,两条理由:

1. katrain 已经自带拍过板的字体(`@fontsource` 的 Newsreader / JetBrains Mono /
   Hanken Grotesk / Noto Sans SC),抄上游等于把已定的排版改掉;
2. `tokens.css` 不依赖它们 —— 全文 `url()` 只有两处,都指向 house.svg,一处字体都没引。

**第 2 条是真的,但它不相关**:字体从来不是靠 `tokens.css` 里的 `url()` 进来的,是靠
`--font-serif/--font-sans/--font-mono` 三个变量指向 `fonts.css` 声明的族 —— 而上一版
**把那三个变量覆盖掉了**,于是所有中文跑在 Noto Sans SC 上。**第 1 条直接违反规范**:
§9(`:609/:634/:1141`)写死「其余所有中文 = 霞鹜文楷」,`:648` 把 Noto Sans SC 列为**退役字库**,
`:628` 还专门写了为什么必须自托管(板子 RK3562/Debian 11 上 PingFang / Songti / **Kaiti SC 一个都没有**,
楷体没有任何可回退的系统字)。上游 README 第 77 行早就把这类错命名了:
**「四张棋类设计稿各自用楷体或 Georgia 重新发明了品牌字」** —— 我们做的就是这件事。

留着这段不删,是因为它和下面那条「编出来的规律」是**同一个形状的两次**:
**一句真话(「tokens.css 不引字体文件」)可以支撑一个错结论,只要它答的不是被问的那个问题。**

## ⚠️ token 只在 `.kiosk` 类上生效

`tokens.css` 整份定义在 `.kiosk { … }` 里。渲染到 `.kiosk` 外面,`var()` **静默求空**、
字体掉回 sans、`color-mix` 整条作废,**且不报错**(国象踩过)。
⇒ 用到这套 token 的子树,根节点必须挂 `.kiosk`。

## ⚠️ 有两个变量 `tokens.css` **不定义**,必须由棋类补

`--paper` 和 `--accent-soft` —— 象棋模板用了它们,但它们不在 `tokens.css` 里
(它只给 `--ink/--panel/--raise/--hair/--text/--dim/--accent/--good/--warn/--bad` 的中性占位)。
漏掉就是上面那条静默求空。`go-tokens.css` 两个都赋了值。

## 🚫 这里曾经写过一条**编出来的规律**(留着,不删)

上一版这份 README 写着:

> 深色下 `--paper` 是**凹面**,要比卡片面暗 —— 与浅色稿那边的明暗关系正好相反。

**那条规律不存在。** 围棋稿子 `sample-go/go-kiosk.tmpl.html` 里 `--paper` 出现 **0 次**,
而它的三层表面是 `--ink #0F1416` → `--panel #18211F` → `--raise #1D2725` ——
**卡片比页底亮**,方向和那句话反着。

留着这段不删,是因为下一个抄外壳的人会想抄同一个洞。判据:
**看着像规律的东西,先去稿子里搜一遍那个变量名** —— 搜不到就说明它是你自己想出来的,
不是你读出来的。(同一条在别处的样子:「注释声称的守卫 ≠ 代码里真在守的那个」。)

顺带同一批查出来的:**`--accent` 和稿子是同一个值 `#58B57A`** ——
`sample-go` 的调色板逐个取自我们自己的 `theme.ts`(那份文件第 10-14 行注释直说了)。
觉得「稿子的绿更亮」是**用法**差异,不是取值差异。
