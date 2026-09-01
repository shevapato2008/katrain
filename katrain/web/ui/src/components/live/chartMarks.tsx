import { Box } from '@mui/material';

/**
 * 五个分析 tab 共用的编码零件。
 *
 * **一条贯穿全部图表的规则：颜色给黑白，档位给位置。**
 *
 * 2026-09-01 之前反过来 —— 颜色编码档位（绿/橙/红），黑白靠形状（实心 vs 空心+斜纹）。
 * Fan 看完直接问「我如何一眼就看出哪个是黑棋，哪个是白棋呢？用户不见得有耐心去研究图的
 * 意思」。问得对：形状差在 5.5px 的圆点和 14px 的柱子上太弱，等于要求用户先学一套约定。
 *
 * 现在把最强的通道给最需要一眼认出的东西：**用围棋自己的黑白两色**，零学习成本；
 * 档位交给横轴位置（轴上本来就写着「妙手/最佳/…/恶手」）加标签下一条细色线，
 * 绿→红的好坏梯度还在，但不再和黑白抢通道。
 *
 * 黑子画成近黑 + 一圈亮边：这不是装饰，是**必需**的 —— 右栏底色 2026-09-01 才从
 * #0f0f0f 改成 #252525，在那之前黑标记等于黑物件贴黑底。亮边让它在任何一种底色上都立得住，
 * 并且黑白之差是**亮度**差（最大对比），色觉障碍下同样分得开。
 */
export const STONE_BLACK = '#0d0d0d';
export const STONE_BLACK_RIM = 'rgba(255,255,255,0.80)';
export const STONE_WHITE = '#f2efea';
export const STONE_WHITE_RIM = 'rgba(0,0,0,0.35)';

export const stoneFill = (isBlack: boolean) => (isBlack ? STONE_BLACK : STONE_WHITE);
export const stoneRim = (isBlack: boolean) => (isBlack ? STONE_BLACK_RIM : STONE_WHITE_RIM);

/** SVG 里的一颗棋子。 */
export function StoneCircle({ cx, cy, r, black }: { cx: number; cy: number; r: number; black: boolean }) {
  return <circle cx={cx} cy={cy} r={r} fill={stoneFill(black)} stroke={stoneRim(black)} strokeWidth={1.5} />;
}

/** 正文里的一颗棋子（图例、统计行）。用 SVG 而不是带边框的 div：
 *  边框盒在不同字号下会被四舍五入成椭圆，SVG 不会。 */
export function StoneDot({ black, size = 13 }: { black: boolean; size?: number }) {
  return (
    <Box
      component="svg"
      viewBox="0 0 16 16"
      sx={{ width: size, height: size, flexShrink: 0, verticalAlign: 'text-bottom' }}
      aria-hidden
    >
      <StoneCircle cx={8} cy={8} r={6.4} black={black} />
    </Box>
  );
}
