# 成长概览 · ui-ux-pro-max 三个候选

三版都是 **1024×600** 真实浏览器预览。原 HTML、生产代码、左侧段位卡、顶部/底部外壳、统计卡、胜率说明及三个 Tab 均未修改。独立 HTML 用同源 iframe 引用现有 Artifact，只在概览日历里插入候选；需要 HTTP 服务打开。

| 候选 | 预览 | 同尺寸截图 | 设计依据与取舍 |
| --- | --- | --- | --- |
| **UIUX 1 · 全年宽幅** | [uiux-1.html](uiux-1.html) | [uiux-1.png](uiux-1.png) | 53 周全部展示。9.4px 方格 / 11.4px 节距，矩阵宽 602px；保留方格形状，月份单排，星期一/三/五贴齐格点。最接近 GitHub 视觉语法；格点放大程度有限。 |
| **UIUX 2 · 纵向舒展（本组推荐）** | [uiux-2.html](uiux-2.html) | [uiux-2.png](uiux-2.png) | 53 周全部展示。9.4×13px 格点 / 横向11.4、纵向16.5px 节距；矩阵高112px，星期一/三/五/日四锚点有33px间隔。保持全年一屏，活跃点面积比原8px方格大约91%，纵向呼吸感最好；格点成为轻微竖矩形。 |
| **UIUX 3 · 大格横移** | [uiux-3.html](uiux-3.html) | [uiux-3.png](uiux-3.png) | 14px 方格 / 17px 节距，面积约为原格点3倍。默认显示最近约8个月，触控横移或44px前后按钮可看全年。月份与星期最易辨；一屏不能同时看完12个月，增加一次操作。 |

## 使用 skill 的依据

读取现有 `KIOSK-UNIFIED-REDESIGN-RULES-2026-10-14.md`、`kiosk-unified/growth.css`、`growth.js`、`tactile.css` 后，搜索：

- `education kiosk dashboard dark green skeuomorphic heatmap readability --design-system`：命中 Data-Dense Dashboard，建议暗底、绿色正向指示、信息可扫描；沿用已有深绿、霞鹜楷体与 IBM Plex Mono，既有设计系统优先于搜索返回的 Orbitron/蓝黑配色。
- `heatmap calendar matrix labels legend --domain chart`：命中 Heat Map / calendar；应用明确行列标签、固定数值图例与文字等价物。保留 17 天摘要，不把不可点击的小格子伪装成触控按钮。

三版共同改进：月份按其真实月份区段中心单排放置，避免原交错两行；图例统一为 **0 / 1–2 / 3–5 / 6–9 / 10+**，不依赖“少/多”猜测；文字18/22/28px，数据数字由现有 numeral helper 使用 IBM Plex Mono；信息键和翻动键均至少44px。

## 数据来源与边界

- 数据全部复用 `docs/design/kiosk-evidence-2026-10-14/current/growth-device-now.png`，不是新造年度样本。
- 原格点中心取样坐标：`x = 460 + col × 10`、`y = 214 + row × 10`，列0–52、行0–6；所得371个位置含365个有效日期、6个空白占位，**17个活跃日期**。`captured-cells.json` 保存完整位置与已有色阶；不推测每天的精确次数。
- 周一为第一行；今日白框在 `(52,2)`，对应实机采集的2026-10-14，不表示当前系统日期。
- 五档阈值与“当天下完的对局 + 当天新解出的题”语义来自 `katrain/web/ui/src/kiosk/components/growth/calendarGrid.ts`。候选只提高显示对比，不改变分档。
- 原日历说明“颜色越深越多”与实际色阶方向不符，候选说明改为“绿色越亮，完成越多”，并解释白框和五档。

## 集成交付

无需搬 iframe。可将 `integration.js` 放进现有 `docs/design/kiosk-unified/growth.js` 的 IIFE（`info()` helper 后），然后把原 `calendar(root, byId)` 的实现换成 `() => growthCalendarCandidate(2)`。将 `integration.css` 追加到 `growth.css`；其样式仅针对 `.u-growth-calendar` 与新日历内的 `.cx-*` 元素。这样只改概览日历，其他标签和所有其他页面不受影响。

UIUX 1/2 不需要新增事件处理。UIUX 3 若选用，需把 `candidate.js` 末尾的 `data-pan` 处理接到每次 render 后，并根据滚动边界禁用对应按钮。

`integration.js` 内的 `growthCapturedActiveCells` 已列出全部17个活跃格的列、行、色阶；可直接复制，无需依赖 JSON fetch。

## 核对结果

- 三张截图均来自 Chromium，viewport 1024×600；无页面滚动、文字遮挡或控件溢出。
- `node --check candidate.js` 和 `integration.js` 通过。
- 大格版前后翻动可操作；在能力诊断与概览之间切换后，候选重新显示。浏览器确认365个格点、17个活跃点及概览选中状态。
- 仅新增本目录文件，没有修改原 HTML、page17、page19 或生产 UI。
