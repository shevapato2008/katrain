/* spec-sync: 3.2 rev=2026-08-22 sha=f861d7e1 —— 见 check_spec_sync.py；规范 §3.2 一改这里就红。 */
import { useEffect, useRef, type ReactNode } from 'react';
import { Box } from '@mui/material';
import { RAIL_GUTTER, RAIL_TIERS, railWidth } from '../../../components/railStyles';

interface BoardPageShellProps {
  board: ReactNode;
  modulePlate: ReactNode;
  railBody: ReactNode;
  displayControls?: ReactNode;
  actions: ReactNode;
  onBoardSizeChange?: (edge: number) => void;
}

const BoardPageShell = ({
  board,
  modulePlate,
  railBody,
  displayControls,
  actions,
  onBoardSizeChange,
}: BoardPageShellProps) => {
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !onBoardSizeChange) return;

    let lastEdge: number | undefined;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const edge = Math.floor(Math.min(entry.contentRect.width, entry.contentRect.height));
      if (edge === lastEdge) return;
      lastEdge = edge;
      onBoardSizeChange(edge);
    });

    observer.observe(stage);
    return () => observer.disconnect();
  }, [onBoardSizeChange]);

  return (
    <Box
      data-testid="board-page-shell"
      sx={{
        width: '100%',
        height: '100%',
        minHeight: 0,
        overflow: 'hidden',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        boxSizing: 'border-box',
        pb: 'calc(64px + env(safe-area-inset-bottom))',
        /* 右栏宽度：**档位下限 + 实测天花板**，取两者的大者（spec §2.3）。
         *
         * 棋盘是正方形，在宽屏上由**可用高度**封顶，所以「还能给右栏多少」是
         * 「壳宽 − 棋盘需要的宽」。2026-09-01 在真浏览器里对 12 档二分搜过
         * 「棋盘开始变小的那个栏宽」，反推出的关系式对 ≥1536 逐档精确：
         *
         *     天花板 = 壳宽 − 20 − min(1200, 视高 − 72)
         *
         * （20 是棋盘台的内边距，1200 是 `components/Board.tsx:118` 的棋盘边长上限，
         *   72 是棋盘台上下的固定占用。）
         *
         * 实测对照（左=旧档位，右=本式）：
         *     1440x900   360 → 376     1920x1080  620 → 652
         *     1536x900   420 → 448     2000x1050  620 → 762   ← Fan 的屏
         *     1680x1050  420 → 442     2560x1440  620 → 900
         *     1920x1200  520 → 532     2560x1600  520 → 900
         *     1280x800   360 → 360     1920x1440  520 → 520   ← 这两档式子比档位小，由下限兜住
         *
         * **下限必须留着**：1280x800 和 1920x1440 上式子算出来比现档窄（棋盘另有
         * 一个上限，式子按 1200 估过头了），没有下限就会**变窄**。clamp 的第一参数
         * 就是原来那一档的定值，所以任何一档都只可能变宽、不可能变窄，
         * 棋盘边长在 12 档全部逐像素不变（实测）。
         *
         * 上限 900 是**可读性**上限不是几何上限：3440x1440 上式子给到 1980，
         * 那么宽的一栏没人想读。Fan 2026-09-01 拍板保留 900。
         *
         * 这一条同时取代了原来那个 `min-aspect-ratio: 16/9` 分支 —— 宽高比只是
         * 「壳宽 vs 视高」的一个粗代理，式子直接把两个量都用上了，不需要代理。 */
        '@media (min-width:900px)': {
          display: 'grid',
          gridTemplateColumns: `minmax(0, 1fr) ${railWidth(RAIL_TIERS[0][1])}`,
          gridTemplateRows: 'minmax(0, 1fr)',
          overflow: 'hidden',
          pb: 0,
        },
        /* 其余三档由 `RAIL_TIERS` 摊开 —— 档数和下限只有那一处，
           断言也就只需要盯那一处（jsdom 看不见 clamp 的值，见 BoardPageShell.test.tsx）。 */
        ...Object.fromEntries(RAIL_TIERS.slice(1).map(([bp, floor]) => [
          `@media (min-width:${bp}px)`,
          { gridTemplateColumns: `minmax(0, 1fr) ${railWidth(floor)}` },
        ])),
      }}
    >
      <Box
        ref={stageRef}
        data-testid="board-stage"
        sx={{
          width: '100%',
          maxWidth: '100%',
          aspectRatio: '1 / 1',
          flex: 'none',
          minWidth: 0,
          minHeight: 0,
          display: 'grid',
          // 显式给一行一列。不写的话这个 grid 只有一条 auto 隐式行，行高由内容决定，
          // 于是子元素的 height:100% 没有确定的百分比基准，退化成 auto —— 谁量容器
          // 谁就量到自己画出来的高度，越量越大。旧版 Board（components/Board.tsx:97
          // 用 getBoundingClientRect 取 min(width,height)）就是这么在 1280×640 下
          // 算出 704 的方板、把 588 高的区域撑破、让整个 shell 开始滚的。
          gridTemplateColumns: 'minmax(0, 1fr)',
          gridTemplateRows: 'minmax(0, 1fr)',
          placeItems: 'center',
          // LiveBoard keeps its existing 4px inner breathing room; 6px here
          // preserves the approved 10px visible board inset without double-counting it.
          p: '6px',
          boxSizing: 'border-box',
          '@media (min-width:900px)': {
            width: 'auto',
            maxWidth: 'none',
            aspectRatio: 'auto',
          },
        }}
      >
        {board}
      </Box>

      <Box
        data-testid="board-right-rail"
        sx={{
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          flex: 'none',
          containerType: 'inline-size',
          containerName: 'board-rail',
          /* 右栏自己的底色 = 左边栏同一个令牌（`background.paper` #252525）。
             2026-09-01 之前这里不设底色，直接露出页底 `background.default` #0f0f0f，
             Fan 当日提出「右边栏使用颜色接近黑色，过于深了，可以考虑上边框和左边栏相同的灰色」。
             不加新色：#0f0f0f / #252525 / #1a1a1a 三个值规范 §4.4 都已经有了。

             这不只是观感。报告页「发挥水准」分不出黑白，根因就在这里：黑方的实心标记
             画在 #0f0f0f 上等于黑物件贴黑底。换成 #252525 之后黑标记才有地方站
             （形状编码——实心=黑、空心=白——仍然保留，不靠亮度）。

             层次因此变成三级：页底 #0f0f0f（凹） < 右栏 #252525（凸） > 图表凹槽
             #0f0f0f/#1a1a1a（再凹）。栏内那些 `bgcolor: 'background.default'` 的图表框
             不用改，它们从「和底一样」自动变成「嵌在面板里的凹槽」，正是要的层次。 */
          bgcolor: 'background.paper',
          '@media (min-width:900px)': {
            minHeight: 0,
            overflow: 'hidden',
          },
        }}
      >
        {/* 三段共用同一个水槽。2026-09-01 之前模块牌和动作区**一点横向内距都没有**
            （标题左内距实测 0px，而下面的卡片在 12px），页面各自在 railBody 里
            写自己的 `p: 1.5` / `p: 2`，一栏里同时存在 0 / 12 / 16 / 25 四个值。
            水槽收到这里之后，各页只留纵向内距。 */}
        <Box data-testid="board-rail-module" sx={{ flex: 'none', px: RAIL_GUTTER }}>
          {modulePlate}
        </Box>
        <Box
          data-testid="board-rail-scroll"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            flex: 'none',
            overflow: 'visible',
            px: RAIL_GUTTER,
            '@media (min-width:900px)': {
              flex: 1,
              minHeight: 0,
              overflowX: 'hidden',
              overflowY: 'auto',
              scrollbarGutter: 'stable',
            },
          }}
        >
          {railBody}
          {displayControls}
        </Box>
        <Box data-testid="board-rail-actions" sx={{ flex: 'none', px: RAIL_GUTTER }}>
          {actions}
        </Box>
      </Box>
    </Box>
  );
};

export default BoardPageShell;
