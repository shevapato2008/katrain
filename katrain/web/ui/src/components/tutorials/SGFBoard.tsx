export interface SGFPayload {
  size: number;
  stones: {
    B: [number, number][];
    W: [number, number][];
  };
  labels?: Record<string, string>;
  letters?: Record<string, string>;
  shapes?: Record<string, string>;
  highlights?: [number, number][];
  viewport?: { col: number; row: number; size?: number; cols?: number; rows?: number } | null;
}

interface SGFBoardProps {
  payload: SGFPayload;
  maxMoveStep?: number;
  /** Current explicitly numbered stone; absent for static, unnumbered diagrams. */
  last?: [number, number] | null;
  showFullBoard?: boolean;
  onClick?: (col: number, row: number) => void;
  /** Override the SVG max width (default 500). Useful for kiosk thumbnails / large dialogs. */
  maxWidth?: number | string;
  /** Extra inline styles merged onto the root <svg>. */
  style?: React.CSSProperties;
  /** Optional className on the root <svg>. */
  className?: string;
  /** Optional calibration overlays. Omitting them preserves legacy rendering. */
  unknownStones?: { point: [number, number]; color: null; evidence?: string }[];
  sourceRegion?: { col: number; row: number; cols: number; rows: number; confirmed: boolean } | null;
  /** Known occupied/empty extent; null means all empty intersections are unknown. */
  knownRegion?: { col: number; row: number; cols: number; rows: number } | null;
}

/** Resolve an exact book move number only when a real stone occupies that point. */
export function findNumberedStone(payload: SGFPayload | null | undefined, step: number | null): [number, number] | null {
  if (!payload || step == null || step <= 0) return null;
  for (const [col, row] of [...payload.stones.B, ...payload.stones.W]) {
    const label = payload.labels?.[`${col},${row}`];
    if (col >= 0 && row >= 0 && col < payload.size && row < payload.size
      && label && /^\d+$/.test(label) && Number(label) === step) return [col, row];
  }
  return null;
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

export default function SGFBoard({ payload, maxMoveStep, last, showFullBoard, onClick, maxWidth, style, className, unknownStones = [], sourceRegion, knownRegion }: SGFBoardProps) {
  const { size, stones, labels = {}, letters = {}, shapes = {}, highlights = [], viewport } = payload;

  // Viewport: support rectangular {col, row, cols, rows} and square {col, row, size}
  const vp = showFullBoard
    ? { col: 0, row: 0, cols: size, rows: size }
    : viewport
      ? { col: viewport.col, row: viewport.row, cols: viewport.cols ?? viewport.size ?? size, rows: viewport.rows ?? viewport.size ?? size }
      : { col: 0, row: 0, cols: size, rows: size };

  const vpCols = vp.cols;
  const vpRows = vp.rows;

  const svgW = MARGIN * 2 + (vpCols - 1) * CELL;
  const svgH = MARGIN * 2 + (vpRows - 1) * CELL;

  const toSvg = (col: number, row: number) => ({
    x: MARGIN + (col - vp.col) * CELL,
    y: MARGIN + (row - vp.row) * CELL,
  });

  const inViewport = (col: number, row: number) =>
    col >= vp.col && col < vp.col + vpCols &&
    row >= vp.row && row < vp.row + vpRows;

  // Check if a stone should be shown based on maxMoveStep
  const shouldShowStone = (col: number, row: number): boolean => {
    if (maxMoveStep === undefined) return true;
    const label = labels[`${col},${row}`];
    if (!label) return true; // unlabeled stones always shown
    const num = parseInt(label, 10);
    if (isNaN(num)) return true; // non-numeric labels always shown
    return num <= maxMoveStep;
  };

  // Grid lines
  const gridLines: React.ReactNode[] = [];
  for (let i = 0; i < vpRows; i++) {
    const y = MARGIN + i * CELL;
    gridLines.push(
      <line key={`h${i}`} x1={MARGIN} y1={y} x2={MARGIN + (vpCols - 1) * CELL} y2={y} stroke="#7a5c2e" strokeWidth={0.8} />
    );
  }
  for (let i = 0; i < vpCols; i++) {
    const x = MARGIN + i * CELL;
    gridLines.push(
      <line key={`v${i}`} x1={x} y1={MARGIN} x2={x} y2={MARGIN + (vpRows - 1) * CELL} stroke="#7a5c2e" strokeWidth={0.8} />
    );
  }

  // Hoshi dots
  const hoshiDots = HOSHI_19
    .filter(([c, r]) => inViewport(c, r))
    .map(([c, r]) => {
      const { x, y } = toSvg(c, r);
      return <circle key={`hoshi-${c}-${r}`} cx={x} cy={y} r={HOSHI_R} fill="#7a5c2e" />;
    });

  // Stones and labels
  const stoneEls: React.ReactNode[] = [];
  const labelEls: React.ReactNode[] = [];

  for (const [col, row] of stones.B) {
    if (!inViewport(col, row) || !shouldShowStone(col, row)) continue;
    const { x, y } = toSvg(col, row);
    const key = `B-${col}-${row}`;
    stoneEls.push(
      <circle key={key} data-stone-color="B" data-point={`${col},${row}`} cx={x} cy={y} r={STONE_R} fill="#1a1a1a" stroke="#000" strokeWidth={0.5} />
    );
    const label = labels[`${col},${row}`];
    if (label && (maxMoveStep === undefined || parseInt(label, 10) <= (maxMoveStep ?? Infinity))) {
      labelEls.push(
        <text key={`lbl-${key}`} x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle"
          fontSize={STONE_R * 1.1} fill="#fff" fontWeight="bold" fontFamily="sans-serif">
          {label}
        </text>
      );
    }
  }

  for (const [col, row] of stones.W) {
    if (!inViewport(col, row) || !shouldShowStone(col, row)) continue;
    const { x, y } = toSvg(col, row);
    const key = `W-${col}-${row}`;
    stoneEls.push(
      <circle key={key} data-stone-color="W" data-point={`${col},${row}`} cx={x} cy={y} r={STONE_R} fill="#f0f0f0" stroke="#555" strokeWidth={0.8} />
    );
    const label = labels[`${col},${row}`];
    if (label && (maxMoveStep === undefined || parseInt(label, 10) <= (maxMoveStep ?? Infinity))) {
      labelEls.push(
        <text key={`lbl-${key}`} x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle"
          fontSize={STONE_R * 1.1} fill="#333" fontWeight="bold" fontFamily="sans-serif">
          {label}
        </text>
      );
    }
  }

  // Book annotations can occupy stones or empty intersections.
  const blackPoints = new Set(stones.B.map(point => point.join(',')));
  const whitePoints = new Set(stones.W.map(point => point.join(',')));
  const calibrationOverlays = knownRegion !== undefined || sourceRegion !== undefined || unknownStones.length > 0;
  const markerColor = (coordinate: string, legacyColor: string) => calibrationOverlays
    ? blackPoints.has(coordinate) ? '#fff' : '#222' : legacyColor;
  const letterEls: React.ReactNode[] = [];
  for (const [coordStr, letter] of Object.entries(letters)) {
    const [col, row] = coordStr.split(',').map(Number);
    if (!inViewport(col, row)) continue;
    const { x, y } = toSvg(col, row);
    const empty = !blackPoints.has(coordStr) && !whitePoints.has(coordStr) && !unknownStones.some(stone => stone.point.join(',') === coordStr);
    const outsideKnown = knownRegion !== undefined && (!knownRegion || col < knownRegion.col || row < knownRegion.row || col >= knownRegion.col + knownRegion.cols || row >= knownRegion.row + knownRegion.rows);
    if (empty && calibrationOverlays) letterEls.push(<g key={`letter-mask-${coordStr}`} data-letter-mask={coordStr}>
      <rect x={x - STONE_R * .68} y={y - STONE_R * .68} width={STONE_R * 1.36} height={STONE_R * 1.36} fill={String(style?.background ?? '#dcb468')} />
      {outsideKnown && <rect x={x - STONE_R * .68} y={y - STONE_R * .68} width={STONE_R * 1.36} height={STONE_R * 1.36} fill="#777d81" fillOpacity=".43" />}
    </g>);
    letterEls.push(
      <text key={`letter-${coordStr}`} data-annotation-point={coordStr} x={x} y={y + 1} textAnchor="middle"
        dominantBaseline="middle" fontSize={STONE_R * 1.2} fill={markerColor(coordStr, '#d32f2f')}
        fontWeight="bold" fontFamily="sans-serif">
        {letter}
      </text>
    );
  }

  const shapeEls: React.ReactNode[] = [];
  for (const [coordStr, shape] of Object.entries(shapes)) {
    const [col, row] = coordStr.split(',').map(Number);
    if (!inViewport(col, row)) continue;
    const { x, y } = toSvg(col, row);
    const r = STONE_R * 0.5;
    const color = markerColor(coordStr, '#1565c0');
    if (shape === 'triangle') {
      const pts = `${x},${y - r} ${x - r * 0.866},${y + r * 0.5} ${x + r * 0.866},${y + r * 0.5}`;
      shapeEls.push(<polygon key={`shape-${coordStr}`} data-annotation-point={coordStr} points={pts} fill="none" stroke={color} strokeWidth={2} />);
    } else if (shape === 'square') {
      shapeEls.push(<rect key={`shape-${coordStr}`} data-annotation-point={coordStr} x={x - r} y={y - r} width={r * 2} height={r * 2}
        fill="none" stroke={color} strokeWidth={2} />);
    } else if (shape === 'circle') {
      shapeEls.push(<circle key={`shape-${coordStr}`} data-annotation-point={coordStr} cx={x} cy={y} r={r}
        fill="none" stroke={color} strokeWidth={2} />);
    } else if (shape === 'cross') {
      const d = r * 0.7;
      shapeEls.push(
        <g key={`shape-${coordStr}`} data-annotation-point={coordStr} stroke={color} strokeWidth={2}>
          <line x1={x - d} y1={y - d} x2={x + d} y2={y + d} />
          <line x1={x - d} y1={y + d} x2={x + d} y2={y - d} />
        </g>
      );
    }
  }

  // Highlight triangles (on stones)
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

  const lastColor = last && inViewport(...last) && shouldShowStone(...last)
    ? stones.B.some(([c, r]) => c === last[0] && r === last[1]) ? '#fff'
      : stones.W.some(([c, r]) => c === last[0] && r === last[1]) ? '#000' : null
    : null;
  const lastPoint = lastColor && last ? toSvg(...last) : null;

  // Click grid (when onClick is provided)
  const clickGrid: React.ReactNode[] = [];
  if (onClick) {
    for (let r = vp.row; r < vp.row + vpRows; r++) {
      for (let c = vp.col; c < vp.col + vpCols; c++) {
        const { x, y } = toSvg(c, r);
        clickGrid.push(
          <rect
            key={`click-${c}-${r}`}
            x={x - CELL / 2}
            y={y - CELL / 2}
            width={CELL}
            height={CELL}
            fill="transparent"
            style={{ cursor: 'crosshair' }}
            onClick={() => onClick(c, r)}
          />
        );
      }
    }
  }

  return (
    <svg
      viewBox={`0 0 ${svgW} ${svgH}`}
      width="100%"
      className={className}
      style={{ maxWidth: maxWidth ?? 500, display: 'block', background: '#dcb468', borderRadius: 4, ...style }}
      aria-label="Go board diagram"
    >
      {gridLines}
      {hoshiDots}
      {knownRegion !== undefined && (() => {
        const region = knownRegion;
        const start = region ? toSvg(region.col, region.row) : null;
        const x = start ? Math.max(0, Math.min(svgW, start.x - CELL / 2)) : 0;
        const y = start ? Math.max(0, Math.min(svgH, start.y - CELL / 2)) : 0;
        const w = region ? Math.max(0, Math.min(svgW - x, region.cols * CELL)) : 0;
        const h = region ? Math.max(0, Math.min(svgH - y, region.rows * CELL)) : 0;
        return <path pointerEvents="none" data-testid="tutorial-known-region" data-known-region={region ? `${region.col},${region.row},${region.cols},${region.rows}` : 'unknown'}
          d={`M0 0H${svgW}V${svgH}H0Z M${x} ${y}h${w}v${h}h${-w}Z`} fill="#777d81" fillOpacity=".43" fillRule="evenodd" />;
      })()}
      {sourceRegion !== undefined && (() => {
        const region = sourceRegion;
        const start = region ? toSvg(region.col, region.row) : null;
        const x = start ? Math.max(0, Math.min(svgW, start.x - CELL / 2)) : 0;
        const y = start ? Math.max(0, Math.min(svgH, start.y - CELL / 2)) : 0;
        const w = region ? Math.max(0, Math.min(svgW - x, region.cols * CELL)) : 0;
        const h = region ? Math.max(0, Math.min(svgH - y, region.rows * CELL)) : 0;
        return <g pointerEvents="none" data-testid="tutorial-source-region">
          {region && <rect x={x} y={y} width={w} height={h} fill="none" stroke="#9a552e" strokeWidth="2.2" strokeDasharray={region.confirmed ? undefined : '7 5'} />}
        </g>;
      })()}
      {stoneEls}
      {unknownStones.filter(stone => inViewport(...stone.point)).map(stone => {
        const { x, y } = toSvg(...stone.point);
        const coordinate = stone.point.join(',');
        const annotation = labels[coordinate] || (letters[coordinate] || shapes[coordinate] ? null : '?');
        return <g key={`unknown-${stone.point}`} data-testid="tutorial-unknown-stone">
          <title>{stone.evidence || '棋子颜色待确认'}</title>
          <circle cx={x} cy={y} r={STONE_R} fill="#999c9e" stroke="#4f5357" strokeDasharray="3 2" />
          {annotation && <text x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle" fontSize={STONE_R * 1.1} fill="#222" fontFamily="inherit">{annotation}</text>}
        </g>;
      })}
      {triangleEls}
      {letterEls}
      {shapeEls}
      {labelEls}
      {lastPoint && <circle data-testid="tutorial-last-move" cx={lastPoint.x} cy={lastPoint.y}
        r={STONE_R * 0.82} fill="none" stroke={lastColor!} strokeWidth={1.5} pointerEvents="none" />}
      {clickGrid}
    </svg>
  );
}
