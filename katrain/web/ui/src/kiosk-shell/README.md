# kiosk-shell —— 从 smartbox 共享外壳抄进来的那一份

katrain 是独立仓,拿不到 `@shared/kiosk-shell`(那在 smartbox 仓),所以这里是**复制品**。

上游:`smartbox-software-xiangqi-features/superpowers/shared/kiosk-shell/assets/`

## 抄了什么

| 文件 | 为什么 |
|---|---|
| `tokens.css` | 991 行结构 token。**这才是围棋缺的那一块** —— 颜色本来就对(`kiosk/theme.ts` 的 jade/slate/raise/hair 与设计稿逐字一致),缺的是几何。 |
| `icons/house.svg` | `tokens.css:338` 用 `mask: url("./icons/house.svg")` 引它。不抄的话那条 mask 静默失效(和 `var()` 求空一样不报错)。 |

`MANIFEST.sha256` 里两行的 hash 与上游 `MANIFEST.sha256` 对应两行**逐字节相同**(2026-08-11 核过)。
抄 hash 不是形式:复制品会漂而没人知道,有 hash 才答得出**「我这份和上游还是同一份吗」**。

## 故意**没**抄什么 —— 这条是判断,不是遗漏

**`fonts.css`(204KB)和 `fonts/`(9.5MB)没抄。** 两个理由:

1. **katrain 已经自带拍过板的字体**,而且是自托管的:`kiosk/theme.ts` 顶部 `@fontsource` 引入
   Newsreader / JetBrains Mono / Hanken Grotesk / Noto Sans SC,无 CDN 依赖。
   抄上游字体等于把 `--font-serif` 换成 SmartBox Kai —— **那是把已经拍过板的排版改掉**,
   不是对齐。
2. **`tokens.css` 不依赖它们**:全文 `url()` 只有两处,都指向上面那个 house.svg,
   一处字体文件都没引。字体只通过 `--font-serif/--font-sans/--font-mono` 三个**变量**进来,
   而变量由各棋类自己赋值(见 `go-tokens.css`)。

⇒ 抄了字体也用不上,不抄也不缺。哪天要对齐排版,那是另一个决定,得先拍板。

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
