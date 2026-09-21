# 直播列表屏(稿外屏)与棋谱屏入口行 —— 实现图存档

**没有参考图。** `/kiosk/live` 不在 27 屏设计稿里,属 Fan 2026-08-20 裁的「稿外五屏,只接壳不重排」。
四图对比的前提是有一张参考图可比 —— 这里没有,所以**只存实现图**,不做并排 / 差异图,
**也不伪造一张参考图凑四图**(PRD §7)。判据改为:

- 页面头注那三条(去 canvas 棋盘预览、去写死 0.5 的胜率条、去 `_blank` 外链);
- 行的几何与屏 15 棋谱「职业直播」那四行同一套 `.kiosk-row`(52 高、46 宽等宽行首);
- `katrain/web/ui/tests/kiosk-live-list.spec.ts` 的承重断言(下表)。

屏 15 本身有参考图:入口行在它首屏之下,静态那一帧只变了滚动条拇指(内容变长),
四图随本赛道重拍在 `superpowers/tracks/kiosk-go-shell-align/visual/15-kifu/`。

## 图

| 文件 | 内容 |
|---|---|
| `live-list-live--implementation.png` | 1024×600,「直播中」段,50 场桩数据,时钟冻在 2026-08-20 16:40 |
| `live-list-finished--implementation.png` | 「已结束」段,30 场(副行:对阵 · 来源 · 结果 · 日期) |
| `live-list-upcoming--implementation.png` | 「即将开始」段,20 场赛程(行尾是开赛时刻,来源是字不是链接) |
| `kifu-bottom--implementation.png` | 屏 15 滚到底:直播那一组 4 行 + 末行「全部直播 · 赛程」 |

## 承重实测(2026-09-22,真 Chromium 1024×600,数据先造到溢出)

关系式先写死再读数;像素只记录,不作判据。

| 量 | 判据 | 实测 |
|---|---|---|
| 该滚的元素 | `[data-testid=live-page] .kiosk-side__scroll` 自己 | scrollHeight 3018 > clientHeight 460 |
| 行没被 flex 压扁 | 行高 = `--row-h`,且 scrollHeight ≥ 50 × 行高 | 52 = 52;3018 ≥ 2600 |
| 行首格装得下三位数手数 | 每个 `.kiosk-row__lead` scrollWidth ≤ clientWidth | 0 个溢出(到「247 手」) |
| 手指拨得动 | 真滚轮一次后 scrollTop > 0 | 通过 |
| 滚到底 | 写入大 scrollTop 读回 = scrollHeight − clientHeight | 2558 = 2558 |
| 不被裁 | 末行 ⊂ 滚动框 ⊂ 视口 600 | 末行 [534, 586] ⊂ 框 [126, 586];586 ≤ 600 |
| 整页不溢出 | 文档 scrollWidth ≤ clientWidth、scrollHeight ≤ clientHeight | 通过 |
| 切分段 | 页控条 y、高不变;列表 scrollTop 归 0 | 通过 |
| 赛程行不横向溢出 | 每行 scrollWidth ≤ clientWidth | 0 行溢出 |
| 屏 15 入口行 | 滚到底后入口行 ⊂ 滚动框 | [452, 504] ⊂ [70, 504] |
| 坐标系 / 落点 | 不适用 | 两屏都没有代码读 `offsetTop` 或把某一行滚进视野 |
