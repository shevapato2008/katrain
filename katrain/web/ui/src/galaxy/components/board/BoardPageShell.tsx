/* spec-sync: 3.2 rev=2026-08-22 sha=f861d7e1 —— 见 check_spec_sync.py；规范 §3.2 一改这里就红。 */
import { useEffect, useRef, type ReactNode } from 'react';
import { Box } from '@mui/material';

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
        // 右栏四档宽（spec §2.3）。2026-08-30 从三档 320/340/380 加宽而来：
        // 棋盘是**正方形**，所以在宽屏上它由**高度**封顶，棋盘列多出来的横向空间
        // 全是死白边。实测（`/galaxy/live` 真浏览器，见 spec §3.3 的表）：2000×1050 上
        // 棋盘 986，棋盘列却有 1380 —— 382px 白边；2560×1440 上 552px。
        //
        // 每一档的取值判据是**加宽之后棋盘边长不变**（新栏宽仍落在那一档最矮的常见
        // 分辨率的白边之内），只有三处例外（1200×800 / 1280×800 各 −20，1536×960 −32），
        // 那三处棋盘本来就是宽度受限的、白边为零，任何加宽都要棋盘出。
        // 900–1199 因此**不动**：1024×768 上棋盘列 704 已经窄于可用高度 716。
        //
        // 顶档止于 520，卡住它的是**图表**不是棋盘。2560×1440 上棋盘另有一个上限
        // （`components/Board.tsx:118` 的 `Math.min(1200, …)`），所以那一档右栏再加宽
        // 一个像素都不花棋盘的 —— 换句话说「棋盘优先」在那一档根本不构成约束。
        // 真正的约束是三个矢量图表的 viewBox 写死 420 宽、`xMidYMid meet`：栏宽超过 420
        // 之后图不再变大，多出来的宽度全变成图表框内部的死区。520 时那块死区还能忍，
        // 620 就明显了。**要先把图表改成按容器实测宽度驱动（spec §2.5「已知未解」），
        // 再谈抬高顶档**。2560 下现在仍有约 410px 死白边，记账。
        '@media (min-width:900px)': {
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 320px',
          gridTemplateRows: 'minmax(0, 1fr)',
          overflow: 'hidden',
          pb: 0,
        },
        '@media (min-width:1200px)': {
          gridTemplateColumns: 'minmax(0, 1fr) 360px',
        },
        '@media (min-width:1536px)': {
          gridTemplateColumns: 'minmax(0, 1fr) 420px',
        },
        '@media (min-width:1920px)': {
          gridTemplateColumns: 'minmax(0, 1fr) 520px',
        },
        /* 顶档在**宽扁屏**上再加一档到 620。
         *
         * 2026-09-01 Fan 提出右栏还是太窄（他的截图约 2000px 宽）。规范 §2.3 记着
         * 2026-08-30 试过 620 但「栏内散架」——那次的三个前置现在都拆掉了
         * （开关分列规则、图表按容器宽度驱动、工具键横排），所以可以谈加宽了。
         *
         * **但按视口宽度分档在这里是错的。** 逐视口实测「棋盘开始变小的那个栏宽」：
         *
         *     1920x1080  天花板 652   （死白边 132）
         *     1920x1200  天花板 532   （死白边  12）
         *     1920x1440  天花板 520   （死白边   0）← 同样是 1920 宽，一寸都不能加
         *     2560x1440  天花板 932   （死白边 412）
         *     3440x1440  天花板 1812
         *
         * 棋盘是正方形、在宽屏上由**高度**封顶，所以死白边由**宽高比**决定而不是宽度。
         * 于是这一档挂在 `min-aspect-ratio: 16/9` 上：16:9 及更扁的屏才加宽，
         * 1920x1200 / 1920x1440 这类高屏留在 520。代数上界 `7W/16 - 188`，
         * W=1920 时是 652，与实测吻合；620 因此留了 32px 余量。
         *
         * 这条必须排在上面那条 min-width:1920 之后：两条都命中时后写的赢。 */
        '@media (min-width:1920px) and (min-aspect-ratio: 16/9)': {
          gridTemplateColumns: 'minmax(0, 1fr) 620px',
        },
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
        <Box data-testid="board-rail-module" sx={{ flex: 'none' }}>
          {modulePlate}
        </Box>
        <Box
          data-testid="board-rail-scroll"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            flex: 'none',
            overflow: 'visible',
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
        <Box data-testid="board-rail-actions" sx={{ flex: 'none' }}>
          {actions}
        </Box>
      </Box>
    </Box>
  );
};

export default BoardPageShell;
