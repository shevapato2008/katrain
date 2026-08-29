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
