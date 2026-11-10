# 成长概览活跃矩阵 · Claude Design 三版

设计表面：**Monitor / 状态概览**。沿用既有深绿 Kiosk、霞鹜楷体、IBM Plex Mono 数字、立体按钮、左侧段位卡、右侧三 Tab；改动仅为「概览」中的练棋矩阵。

## 候选

| 方案 | HTML / 1024×600 浏览器截图 | 差异与理由 |
| --- | --- | --- |
| A 全年舒展 | [HTML](a-annual-open.html) · [截图](a-annual-open.png) | 全年单排 624×110px，月份单排、星期一三五日、底部图例。最接近现有结构，矩阵面积约为原 540×73px 的 1.74 倍。 |
| **B 完整星期坐标（推荐）** | [HTML](b-weekday-axis.html) · [截图](b-weekday-axis.png) | 全年单排 624×126px，星期一至日逐行标明；图例移入标题行，释放矩阵高度。矩阵面积约 2 倍，年内趋势可一眼扫读。 |
| C 半年折行 | [HTML](c-half-year-fold.html) · [截图](c-half-year-fold.png) | 53 周分为连续的 27 周与 26 周，前后两段各占 518×75px；标题和图例置左。单格宽度明显增加，适合近距离辨认单日；查看全年时需上下阅读。 |

三份 HTML 为完整独立的原页面副本，使用仓库现有字体与样式资源，通过 `<base href="../../">` 保持相对引用。原 HTML 与 `kiosk-unified/` 文件均未修改。可通过仓库静态 HTTP 服务打开。

## 数据与验证

- 数据来源为 `docs/design/kiosk-evidence-2026-10-14/current/growth-device-now.png` 中每日格子的像素中心：`x = 461 + column × 10`，`y = 215 + row × 10`。
- 53×7 个位置；保留同样的 **17 个活跃格**、首尾范围外位置以及最后一列第三行的当前日期轮廓。活动等级由原图采样归并，未新增对局或练棋记录。
- [captured-calendar-data.json](captured-calendar-data.json) 记录精确 17 个活跃位置、等级、空位和采样坐标；索引从 0 开始，行顺序为周一至周日。
- 三版已在真实 Chromium 浏览器 **1024×600** 预览并截图。B、C 最终页面控制台无错误；B/C 均确认 371 格、17 活跃格、12 个月标签；C 页面范围为 1024×600，无页面滚动。
- claude-design 自查 **0/10**：沿用产品明确的色彩和字体；采用状态图表构图，无新增展示性统计或装饰区块。

## 选中后局部集成

实际成长页由 `docs/design/kiosk-unified/growth.js` 中的 `KioskDesignFamilies.growth` 渲染，原 HTML 第 684 行 `heat()` 是旧 fallback，当前不会用于这页。

1. 在 `growth.js` 之前引入 [calendar-integration.js](calendar-integration.js)，或将其纯渲染函数内联到 `growth.js`。
2. 仅替换 `growth.js` 的 `calendar()`：

```js
const calendar = () => window.renderGrowthCalendarCandidate('b',
  info('绿色方格代表那天下过棋或解过题。颜色越深，练习越多。日历显示近一年的记录。', '近一年练棋说明')
);
```

3. 在 `growth.css` 之后引入所选方案的局部 CSS：[A](a-annual-open.css)、[B](b-weekday-axis.css)、[C](c-half-year-fold.css)。所有规则只匹配成长日历或 `candidate-*` 节点。选 A/C 时将上例 `'b'` 改为 `'a'` / `'c'`。
4. 「能力诊断」「对手」、左卡、四个统计卡、胜率说明保持原实现。上述 helper 只返回日历 HTML。
