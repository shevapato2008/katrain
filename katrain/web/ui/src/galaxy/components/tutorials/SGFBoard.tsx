export interface SGFPayload {
  size: number;
  stones: {
    B: [number, number][];
    W: [number, number][];
  };
  labels?: Record<string, string>;
  highlights?: [number, number][];
  viewport?: { col: number; row: number; size: number };
}

interface SGFBoardProps {
  payload: SGFPayload;
}

const CELL = 32;
const MARGIN = CELL * 0.75;
const STONE_R = CELL * 0.44;
const HOSHI_R = 3;

const HOSHI_19: [number, number][] = [
  [3, 3], [9, 3], [15, 3],
  [3, 9], [9, 9], [15, 9],
  [3, 15], [9, 15], [15, 15],
];

export default function SGFBoard({ payload }: SGFBoardProps) {
  const { size, stones, labels = {}, highlights = [], viewport } = payload;

  const vp = viewport ?? { col: 0, row: 0, size };
  const displaySize = vp.size;

  const svgW = MARGIN * 2 + (displaySize - 1) * CELL;
  const svgH = MARGIN * 2 + (displaySize - 1) * CELL;

  const toSvg = (col: number, row: number) => ({
    x: MARGIN + (col - vp.col) * CELL,
    y: MARGIN + (row - vp.row) * CELL,
  });

  const inViewport = (col: number, row: number) =>
    col >= vp.col && col < vp.col + displaySize &&
    row >= vp.row && row < vp.row + displaySize;

  const gridLines: React.ReactNode[] = [];
  for (let i = 0; i < displaySize; i++) {
    const xEnd = MARGIN + (displaySize - 1) * CELL;
    const y = MARGIN + i * CELL;
    gridLines.push(<line key={`h${i}`} x1={MARGIN} y1={y} x2={xEnd} y2={y} stroke="#7a5c2e" strokeWidth={0.8} />);
    const x = MARGIN + i * CELL;
    gridLines.push(<line key={`v${i}`} x1={x} y1={MARGIN} x2={x} y2={MARGIN + (displaySize - 1) * CELL} stroke="#7a5c2e" strokeWidth={0.8} />);
  }

  const hoshiDots = HOSHI_19
    .filter(([c, r]) => inViewport(c, r))
    .map(([c, r]) => {
      const { x, y } = toSvg(c, r);
      return <circle key={`hoshi-${c}-${r}`} cx={x} cy={y} r={HOSHI_R} fill="#7a5c2e" />;
    });

  const stoneEls: React.ReactNode[] = [];
  const labelEls: React.ReactNode[] = [];

  for (const [col, row] of stones.B) {
    if (!inViewport(col, row)) continue;
    const { x, y } = toSvg(col, row);
    const key = `B-${col}-${row}`;
    stoneEls.push(
      <circle key={key} cx={x} cy={y} r={STONE_R} fill="#1a1a1a" stroke="#000" strokeWidth={0.5} />
    );
    const label = labels[`${col},${row}`];
    if (label) {
      labelEls.push(
        <text key={`lbl-${key}`} x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle"
          fontSize={STONE_R * 1.1} fill="#fff" fontWeight="bold" fontFamily="sans-serif">
          {label}
        </text>
      );
    }
  }

  for (const [col, row] of stones.W) {
    if (!inViewport(col, row)) continue;
    const { x, y } = toSvg(col, row);
    const key = `W-${col}-${row}`;
    stoneEls.push(
      <circle key={key} cx={x} cy={y} r={STONE_R} fill="#f0f0f0" stroke="#555" strokeWidth={0.8} />
    );
    const label = labels[`${col},${row}`];
    if (label) {
      labelEls.push(
        <text key={`lbl-${key}`} x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle"
          fontSize={STONE_R * 1.1} fill="#333" fontWeight="bold" fontFamily="sans-serif">
          {label}
        </text>
      );
    }
  }

  const triangleEls = highlights
    .filter(([c, r]) => inViewport(c, r))
    .map(([col, row]) => {
      const { x, y } = toSvg(col, row);
      const r = STONE_R * 0.6;
      const pts = [
        `${x},${y - r}`,
        `${x - r * 0.866},${y + r * 0.5}`,
        `${x + r * 0.866},${y + r * 0.5}`,
      ].join(' ');
      const isBlack = stones.B.some(([c2, r2]) => c2 === col && r2 === row);
      return (
        <polygon key={`tri-${col}-${row}`} points={pts}
          fill="none" stroke={isBlack ? '#fff' : '#000'} strokeWidth={1.5} />
      );
    });

  return (
    <svg
      viewBox={`0 0 ${svgW} ${svgH}`}
      width="100%"
      style={{ maxWidth: 400, display: 'block', background: '#dcb468', borderRadius: 4 }}
      aria-label="Go board diagram"
    >
      {gridLines}
      {hoshiDots}
      {stoneEls}
      {triangleEls}
      {labelEls}
    </svg>
  );
}
