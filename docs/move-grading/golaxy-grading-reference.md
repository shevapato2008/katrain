# 星阵围棋（Golaxy）着手评价体系 — 实测取证

取证日期：2026-08-28 / 29
取证人：Claude（本文每条都注明证据位置；无证据的一律标「未证」）

## 0. 取证方法与两个坑

- 文档页 https://19x19.com/engine/document/engine_detail 是 Vue SPA，
  **HTML 里没有正文**。正文由 `${assetsUrl}/${filePath}.json` 拉取，
  真实地址是 https://assets.19x19.com/web/text/help/engine_detail.json
  （路由映射见 `chunk-6ec7eabe`：`{engine_detail:"web/text/help/engine_detail", ...}`，
  其余文档在 `https://assets.19x19.com/txt/<name>.json`）。
  直接 curl 页面或用 WebFetch **拿不到任何内容**，会得出「文档没写」的错误结论。
- gstack `/browse` 和 chrome MCP **都到不了 19x19.com**：Mac 上是 fakeip 代理，
  browse 把解析出来的地址判成云元数据 IP 直接拒绝。用 curl。
- 前端 bundle：`https://assets.19x19.com/web-resource/golaxy/20260828_script/js/`
  下 353 个 chunk，全量下载到 /tmp/gx/ 后 grep。入口 `app.13c026d9.js`，
  chunk 文件名带 hash，清单在 SPA 首页 HTML 里。

## 1. 谁在评分：**服务端**（这一条推翻了第一版结论）

每手棋由服务端下发一个整数 `level`，客户端只做查表：

```js
// chunk-3bfa227a @175057
userScoreHandle:function(e){
  var t=null;
  return void 0==e.level || -100==e.level ||
    (2==e.level&&(e.level=3),                       // ← level 2 被就地改写成 3
     t=this.GLOBAL.deepCopy(this.GLOBAL.scoreListArr[e.level])),
  t
}
```

`scoreListArr[level]` 的索引映射（app.js @223882）：

| level | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 11–15 |
|---|---|---|---|---|---|---|---|---|
| 档位 | 最佳 | 很好 | 不错 | 可下 | 欠佳 | 失误 | 恶手 | 妙手 lv1–5 |

实测计数（`grep -o ... /tmp/gx/*.js | wc -l`）：
- `scoreListArr[<x>.level]` 共 **7 处**（0a027197 / 15ce8802 / 3bfa227a×2 / 6e882280 / 794b00e8 / d8446b80）
- `2==<x>.level&&(<x>.level=3)` 共 **4 处**
- `score3`（不错）全 bundle **只出现 1 次**，就是它自己的定义 ⇒ **不错是死档**，
  legend 对象 `scoreList` 里也没有它。
  对比：score7 出现 4 次、score11 出现 8 次。

⇒ **实际展示的七档 = 妙手 / 最佳 / 很好 / 可下 / 欠佳 / 失误 / 恶手**，
与用户截图里的直方图七根柱子完全对上。

## 2. `optionsScore` 那张阈值表不是评分规则

app.js @212410 里那张表（全 bundle 唯一定义）：

```js
optionsScore={
 inProp:[{value:.05,score:"很好",key:"score2"},
         {value:.01,score:"不错",key:"score3"},
         {value:0,delta:0,score:"可下",key:"score4"}],
 outProp:[{value:.3, delta:10, score:"恶手",key:"score7",pr:1},
          {value:.15,delta:6,  score:"失误",key:"score6",pr:.66},
          {value:.05,delta:2.5,score:"欠佳",key:"score5",pr:1}],
 sp1:{score:"最佳",key:"score1"},
 sp2..sp6:{score:"妙手",key:"score11",name:"玄妙指数1".."玄妙指数5"}}
```

它的实际用途是 **名字 + 颜色 + 图标的查表**。关于那些数字：

- **目数阈值（2.5 / 6 / 10）是死数据。** 353 个 chunk 里没有任何一处从
  optionsScore 派生对象上读 `.delta`
  （`grep -ohE '(inProp|outProp|scoreListArr|scoreList|userScore|badPointList)[^;]{0,40}\.delta'` 无输出）。
  被读到的属性只有 `.key`(17) / `.color`(14) / `.badPointcon`(6) / `.rgb`(5)。
  ⇒ 「胜率 or 目数」这个问题在客户端**不成立**，因为目数根本没进任何判断。
- **`inProp.value` 不是胜率增益。** 它被拿去和 `options[].proportion` 比，
  而 proportion 是该选点的**访问量占比**（`f = u/t[s].v[4]`，引擎参数
  `reply_show_proportion:true`；行布局 `v[2]=winrate, v[3]=delta, v[4]=proportion`）。
  即「很好/不错/可下」在那个面板里的意思是「实战手是 AI 候选之一，
  占了 >5% / >1% / >0 的搜索访问量」。第一版说的「涨 5% 胜率」是误读。
- **`outProp.value` 唯一被求值的那处还是错的**：
  `for(var r in n.outProp) if(t.options[0].winrate - t.value < n.outProp[r].value){e=n.outProp[r];break}`
  数组顺序是 恶手(.3) → 失误(.15) → 欠佳(.05)，判断是 `<`，
  于是**任何小于 30% 的损失都会在第一轮命中「恶手」**，≥30% 反而什么都不命中。
  欠佳/失误在该面板不可达。同样的五份拷贝（15ce8802 ×2 / 3bfa227a ×2 / d8446b80），
  不是抄写错误。

**可以带走的结论**：这些数字反映了星阵**设计者心里的量级**（欠佳≈2.5目/5%、
失误≈6目/15%、恶手≈10目/30%），但**不能声称那是星阵的判定阈值**。

## 3. 服务端每手下发的字段（这才是可对标的接口）

`parseDataBadPoint`（chunk-3bfa227a @~293000）逐手读到的字段：

| 字段 | 含义 |
|---|---|
| `level` / `userScore` | 服务端评级（见 §1） |
| `evaluate` | **严重度排序键**（问题手列表按它排序） |
| `number` | 手数 |
| `color` | 落子方 |
| `actualValue` | 实战手胜率（0–1） |
| `actualScore` | 实战手目数 |
| `winrateDrop` | 胜率损失（服务端预算好，21 处引用） |
| `deltaDrop` | 目数损失（服务端预算好，12 处引用） |
| `options[0].winrate` / `options[0].delta` | AI 最佳点的胜率 / 目数<br>（旧协议回退名：`optionsFirstWinrate/optionsFirstDelta`、`ofw/ofd`） |

⇒ 星阵服务端**两个量都算**（胜率损失 + 目数损失），并且**同时下发**
「最佳点的值」和「实战手的值」。tooltip 就是拿这两组数画
「胜率 62.3% → 41.0%」这种前后对照的。

## 4. 显示上限：确证「星阵不是失误少，是只显示前几个」

```js
// chunk-3bfa227a, parseDataBadPoint
e = e.splice(this.minNumCul, e.length);                 // 掐掉开头 N 手
for (...) if (e[d].userScore && badPointList[e[d].userScore.key]   // 只留 欠佳/失误/恶手
             && Number(d)>=p && Number(d)<=h            // 阶段区间 [min,max]
             && (!f || f==i)) { ... 1==i ? o.push(S) : s.push(S) } // 按黑/白分两条队
o = sortData(o, (a,b)=>Number(a.sort)>Number(b.sort));  // sort:g，g = e[d].evaluate
s = sortData(s, ...);
var _ = 0==f ? reportFilter.badPoint.num : 2*reportFilter.badPoint.num;   // 5 或 10
o.splice(_, o.length-_);  s.splice(_, s.length-_);      // 每条队各截断
```

对抗复核修正了三处（我最初读错了）：

- **阶段区间不是 0–60 / 61–180 / 181–end。** 那三个数只存在于
  `reportFilter.levelBar`，而 `levelBar` 在 353 个 chunk 里**只出现一次**
  （就是它自己的定义），**从未被读取，是死配置**。
  真正喂给 `getMinMax()` 的是组件自己的 `subType.data`（chunk-3bfa227a @291028，
  三个 chunk 里字节相同）：**全盘 0–end / 布局 0–59 / 中盘 60–149 / 官子 150–end**。
  另有一处「棋力预测」用的是 布局 11–60 / 中盘 61–150 / 官子 151–end，是另一个功能，别混。
- **`f` 是棋手筛选（双方=0 / 黑方=1 / 白方=-1），不是阶段。**
  阶段选择器**不改上限**，它只改 `p`/`h` 区间 —— 换阶段能看到更多问题手，
  是因为**每个窗口各自重新分配一份 5 条的预算**，不是上限变了。
  选单方时上限翻到 10，但循环守卫 `(!f||f==i)` 会让另一方的队列为空 ⇒
  **屏幕上总数永远 ≤10**（5+5 或 10+0），棋手筛选是**重新分配预算而不是加倍**。
- **`evaluate` 是不是「严重度」没有证据。** 它是服务端下发的字段，
  在整个 bundle 里从不渲染、没有 i18n 标签，唯一的功能性用途就是这里当排序键。
  真正承载严重度的是 `level`（决定进不进列表）和 `winrateDrop`/`deltaDrop`（决定幅度），
  而且兄弟面板 妙手 排序用的就是 `level`。所以只能说「按服务端的 `evaluate` 降序取前 N」，
  不能说「按严重度」。
- 妙手面板**不共用** `reportFilter.badPoint.num`，它在 `extraordinaryListFilter`
  里硬写了同样的字面量：`1==e?black.splice(0,10):-1==e?white.splice(0,10):black.splice(0,5).concat(white.splice(0,5))`，
  排序用 `level`。行为一样，代码上是解耦的。
- 上限在某方不足 5 条时是 no-op（`splice(5, -2)` 删不掉东西），
  正好对应文档那句「当问题手不足5个时会显示全部问题手」。
- 文档原文两处印证（engine_detail.json）：
  > 妙手中会默认给出每方全盘各5个妙手（当妙手不足5个时会显示全部妙手）。还可以分阶段、分棋手查看，如此可以查看出更多的妙手。
  > 问题手中会默认给出每方全盘各5个问题手（当问题手不足5个时会显示全部问题手）。

### 4.1 结论要收窄

**已证**：星阵**分类的比它展示的多**（`level` 由服务端给，进列表只看 level ∈ {4,5,6}，
然后被截断到每方 5 条）。

**未证**：星阵分类出来的问题手数量和我们一样多。它的**入选门槛本身**也是个闸 ——
前端那张表把 欠佳 标为「5% 胜率 / 2.5 目」，比我们现在的「1.5 目」严。
一手亏 2 目、掉 3% 胜率的棋，在星阵那里**根本不进问题手**。
要做数量对比，得先统一门槛口径，光看这份 bundle 判不了。

## 5. 妙手（只有厂商文案，没有可见规则）

engine_detail.json 原文：
> 妙手是指实战下出了 AI 第一选点并且该选点较难被下出。星阵还根据玄妙程度将妙手分为 5 个级别，蓝色柱子越高则代表该妙手越难被发现。

博客也有一句独立表述（blog.19x19.com/archives/2024_04_26_21_37_08_1028）：
> 通过一系列的规则，星阵在"最佳"中挑选出"妙手"独立展示，在"妙手"标签和"发挥水准"标签内都有所体现。星阵还将"妙手"分成5种不同的玄妙程度，蓝色柱子越高则表示越玄妙

客户端侧只看到 `level` 11–15 → `"sp".concat(level-9)` 的映射（柱高 = level-9，y 轴固定 0–6），
**判定规则在服务端，不可见**。

**证据强度必须写清楚**（三份复核一致指出）：
- 「妙手 = AI 第一选点 ∩ 较难被下出」**只有厂商文案**，且 engine_detail /
  report_detail / live_detail 三处是**同一句话的三次粘贴**，不是三份独立证据。
- 17 MB JS 里「玄妙」只出现 **5 次**，全是 `name:"玄妙指数N"` 这五个标签字符串；
  妙手图的 tooltip 只打印「玄妙指数3」，**不带任何判据说明**。
- 结构上有一条弱佐证：`level` 是**单值**字段，妙手（11–15）与最佳（0）互斥，
  妙手占的正是最佳本该占的那个槽 ⇒ 与「最佳的子分级」自洽，
  也**排除了**「妙手 = 惩罚了对手恶手」这种正交读法。
- 但「不看胜率增益」这句**不能断言**：客户端里唯一一处 妙手 判定
  （`parseScore` / `culUserScore`，三个 chunk 各有一份）是**纯胜率判据**且方向相反 ——
  走了 AI 首选给的是 `sp1` 最佳，`sp2` 妙手 只在「实战手不在候选列表里、
  且其胜率高过第一选点」时给出。已核实这条路径是**死代码**
  （`userScore` 从不被读，实际渲染的徽章走服务端 `level`），但它是厂商自己的代码。
- 「玄妙指数」按什么算，policy 先验 / 与第二选点的胜率差 / 访问量占比 三种读法
  都同样满足那句文案，bundle 里区分不出来。要定案得抓一次真实 report 响应。

⇒ 写进设计文档时的口径：**这是星阵声明的意图，不是已证的机制**。
我们要不要照做，取决于这个思路本身站不站得住（§7 有实测），不取决于星阵。

但对我们的设计而言这一条已经够用：它给出的是**另一根轴**（难度），
而不是在同一根「目数损失」轴上放宽阈值。

## 6. 发挥水准

> 发挥水准是这盘棋每手棋评价的数据统计，可以查看全盘，也可以查看不同阶段。

即七档的黑白双色直方图，每档两行「手数 / 占比」，作用域是 全盘/布局/中盘/官子。
代码实测（`parseDataLevel`，chunk-3bfa227a @305296）：

- **分母是该方自己在所选阶段内被评级的手数**（黑 `b` / 白 `g`），不是总手数，不是两方合并。
- 七根柱子的顺序：妙手 / 最佳 / 很好 / 可下 / 欠佳 / 失误 / 恶手（妙手 tab 隐藏时第一根被 shift 掉）。
- **发挥水准没有棋手筛选** —— 双方/黑方/白方 那条控件只对 问题手 和 妙手 显示。
- 不错**不是并进很好**：`score3` 根本不在 `scoreList` 里，服务端的 level 2 被改写成 3，
  所以一手「不错」在直方图里显示成**可下**。
用户截图实测一局：最佳 33(44%) / 43(57%)，很好 26(35%) / 20(27%)，
可下 8(11%) / 6(8%)，欠佳 5(7%) / 4(5%)，失误 2(3%) / 0(0%)，恶手 0 / 0，
妙手 1(1%) / 2(3%)。占比分母是该方自己的手数（两方各自归一）。
