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
        '@media (min-width:900px)': {
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 320px',
          gridTemplateRows: 'minmax(0, 1fr)',
          overflow: 'hidden',
          pb: 0,
        },
        '@media (min-width:1200px)': {
          gridTemplateColumns: 'minmax(0, 1fr) 340px',
        },
        '@media (min-width:1536px)': {
          gridTemplateColumns: 'minmax(0, 1fr) 380px',
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
