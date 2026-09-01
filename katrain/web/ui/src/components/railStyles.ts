import type { SxProps, Theme } from '@mui/material';

/** 右栏内部版式的共用样式（spec §2.5）。
 *
 * 放在 `src/components/`（共享地界）而不是 `src/galaxy/` —— 消费方里 `PlayerCard.tsx`
 * 和 `live/PlaybackBar.tsx` 本身就是共享件，共享件反向 import `src/galaxy/` 会把 galaxy
 * 拖进 kiosk 包（见 CLAUDE.md「SBC 构建边界契约」，eslint.config.js 有闸）。
 *
 * 建这个文件是因为「标签 ↔ 开关」这一族在三个地方各写了一份：
 * `game/RightSidebarPanel.tsx`（对局 / 人人对弈）、`pages/live/LiveMatchDisplayControls.tsx`
 * （直播 / 复盘共用）、`tsumego/TsumegoProblemControls.tsx`。三份各自演化，
 * 右栏一加宽就会在同一档下长出三种样子——那正是「不同页面设计风格统一」的反面。
 */

/** 「右栏宽到放得下第二列」。
 *
 * 320/360/420 三档可用宽约 288/328/388，都在 460 以下 —— 这三档的排布与加宽之前
 * 逐像素一致。520 档可用 488，越过这条线。
 *
 * 这条在 <900 的堆叠态（右栏变成棋盘下方的满宽段）同样会命中，而且**应该**命中：
 * 那时右栏更宽、开关同样会排成多列，需要的正是同一套多列规则。
 */
export const RAIL_WIDE = '@container board-rail (min-width: 460px)';

/** 「右栏窄到放不下原尺寸」—— 需要收字号、收内边距的那条带。
 *
 * `PlayerCard.tsx`、`PlaybackBar.tsx`、`KifuLibraryPage.tsx` 共用这一个界。
 * 2026-08-30 之前这三处分别写死 899 / 340 / 340：340 是照着「1200–1535 档右栏 340」
 * 定的，那一档一改成 360，两处 340 的收窄就**悄悄不再生效**了。统一到 460，
 * 使 320/360/420 三档仍然全部收窄、只有 520 档退回原尺寸 —— 与加宽之前的行为一致。
 */
export const RAIL_TIGHT = '@container board-rail (max-width: 460px)';

/** 一组「标签 ↔ 开关」。
 *
 * 窄档一行一个、文字靠左开关靠右（冻结稿的形状，不动）。
 * 宽档 `auto-fit` 排成多列，同时**把 `space-between` 关掉**：多列下继续两端对齐，
 * 每个滑块离**下一列的标签**只有 16px、离自己的标签 158px（1920 实测），
 * 邻近性整个反过来，比不分列还糟。多列时改成标签和滑块贴着、整体靠左。
 */
export const railToggleGroupSx: SxProps<Theme> = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
  columnGap: 2,
  [RAIL_WIDE]: {
    /* `&&` 而不是 `&`：`.parent > *` 的特异性是 (0,1,0)（通配符不计），和
       `FormControlLabel` 自带的那条 `sx` 生成的类**打平**，谁后注入谁赢——实测输了，
       520 档量出来滑块离自己的标签仍是 159px。`&&` 把父选择器写两遍，(0,2,0) 稳赢。 */
    /* `justifySelf: 'start'` 是关键，不是 `justifyContent`：这些开关是
       `FormControlLabel labelPlacement="start"`，MUI 给它的是 `flex-direction: row-reverse`，
       于是 `justify-content: flex-start` 反而把整对推到格子的**右**端（实测如此）。
       让格子里的项目缩到内容宽再靠左，方向就与 `flex-direction` 无关了。 */
    '&& > *': { justifySelf: 'start', width: 'auto', maxWidth: '100%', gap: '12px' },
  },
};

/** 单独一行的「标签 ↔ 开关」（直播 / 复盘 / 死活题各只有一个开关，排不出第二列）。
 *  宽档下与上面同一套规则：贴着、靠左 —— 于是同一个「坐标」开关在四类页面上长得一样。 */
export const railToggleRowSx: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  [RAIL_WIDE]: { justifyContent: 'flex-start', gap: '12px' },
};

/** 工具格一行四个键的栅格。
 *
 * 2026-09-01 之前这条规则在四个文件里各写了一份 `repeat(4, 1fr)`
 * （`RightSidebarPanel` / `TsumegoProblemControls` / `BoardEditToolbar` /
 * `ResearchToolbar` 两处 / `LiveMatchDisplayControls`）—— 和「标签↔开关」当初散三份
 * 是同一个形状：右栏一加宽就会在同一档下长出几种样子。
 *
 * **为什么不用 `auto-fit`。** `repeat(auto-fit, minmax(N, 1fr))` 在中间宽度上会算出
 * **3 列**，而这些工具条都是 4 个键 —— 3 列排 4 个键就是 3+1，最后一格孤零零占满一行。
 * 用与 `RAIL_WIDE` 同一条界显式切两档，只有两种版式要看，不会漏掉中间那种难看的。
 *
 * 窄档（容器 <460px，对应右栏 320/360/420 三档）2×2；宽档 1×4。
 * 窄档两列每格约 141px、宽档四列每格约 112px，都装得下「图标 + 两字标签」的横排。
 */
export const toolGridSx: SxProps<Theme> = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: '6px',
  [RAIL_WIDE]: { gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' },
};

/** 栏内左右内边距 —— **全档、全页面只有这一个值**（Fan 2026-09-01 拍板）。
 *
 * 改之前一栏里同时有四个：模块牌 0（标题贴着左框，就是他报的那一条）、
 * 搜索框 16、卡片 12、卡内文字 25。收到 `BoardPageShell` 的三段上之后，
 * 各页的 railBody 只留纵向内距。
 *
 * 窄档（320）曾经想留 16 的例外，Fan 问「什么是水槽」之后一并取消：
 * 376 的栏上 20 比 16 只多吃 8px，换「以后没人再问这一档该用哪个」值。
 */
export const RAIL_GUTTER = '20px';

/** 「右栏宽到可以把字放大一档」。
 *
 * 与 `RAIL_WIDE`（460，管**分不分列**）是两件事，所以是第二条界：
 * 分列看的是「放不放得下第二列」，字号看的是「一行还剩多少字的余量」。
 * 560 之上对应 620/652/762/900 这几档，实测一行仍装得下最长的赛事名。
 */
export const RAIL_ROOMY = '@container board-rail (min-width: 560px)';

/** 栏内字号两档（spec §2.5）。改之前实测最小到 10.4px（结果徽章）、11.2px（日期），
 *  Fan 2026-09-01：「卡片里的字体太小了」。窄档也抬了一档 —— 那些档位加宽帮不上忙。 */
export const railTitleSx: SxProps<Theme> = { fontSize: '1.43rem', [RAIL_ROOMY]: { fontSize: '1.625rem' } };
export const railPlayerSx: SxProps<Theme> = { fontSize: '0.9375rem', [RAIL_ROOMY]: { fontSize: '1.0625rem' } };
export const railBodySx: SxProps<Theme> = { fontSize: '0.875rem', [RAIL_ROOMY]: { fontSize: '1rem' } };
export const railControlSx: SxProps<Theme> = { fontSize: '0.875rem', [RAIL_ROOMY]: { fontSize: '0.9375rem' } };
export const railMetaSx: SxProps<Theme> = { fontSize: '0.75rem', [RAIL_ROOMY]: { fontSize: '0.8125rem' } };
export const railBadgeSx: SxProps<Theme> = { fontSize: '0.6875rem', [RAIL_ROOMY]: { fontSize: '0.75rem' } };

/** 一档右栏宽 = `clamp(该档下限, 实测天花板, 可读性上限)`。
 *
 * 天花板那一项写成 CSS 而不是 JS，是因为它要跟着**壳的实际宽度**走：
 * 侧边栏可以折叠，折叠后壳变宽、右栏就该跟着变宽。用 `100%` 让浏览器算，
 * 不用 `100vw` 减一个写死的侧边栏宽度 —— 那个减数会在折叠时立刻过期。 */
export const RAIL_MAX = 900;

/** 四档的**下限**：`[断点, 下限px]`。下限只兜底、不封顶（见下面的注释）。 */
export const RAIL_TIERS = [[900, 320], [1200, 360], [1536, 420], [1920, 520]] as const;

/** 天花板那一项：壳自己还剩多少横向空间是棋盘吃不下的。
 *  `100%` 是**壳的宽**不是视口宽 —— 侧边栏折叠后壳变宽，这一项自动跟上。 */
export const RAIL_CEILING = 'calc(100% - 20px - min(1200px, 100vh - 72px))';

export const railWidth = (floorPx: number) => `clamp(${floorPx}px, ${RAIL_CEILING}, ${RAIL_MAX}px)`;
