import type { OgsStep, OgsPoint } from '../../types/ogsCourse';
import type { OgsExerciseState } from './ogsExercise';
import { GO_COLS, starsFor } from '../shell/goBoard';

interface Props {
  step: OgsStep;
  state: OgsExerciseState;
  onPoint: (point: OgsPoint) => void;
  disabled?: boolean;
  extra?: OgsPoint[];
}

const key = (x: number, y: number) => `${x},${y}`;

export function OgsCourseBoard({ step, state, onPoint, disabled = false, extra = [] }: Props) {
  const { size } = step;
  const vp = step.viewport ?? { col: 0, row: 0, cols: size, rows: size };
  const cell = 100;
  const startX = vp.col * cell;
  const startY = vp.row * cell;
  const showPoint = (x: number, y: number) => x >= vp.col && x < vp.col + vp.cols && y >= vp.row && y < vp.row + vp.rows;
  const position = (n: number) => (n + .5) * cell;
  const selected = new Set(state.selectedRemoval.map(([x, y]) => key(x, y)));
  const extras = new Set(extra.map(([x, y]) => key(x, y)));
  const clickable = !disabled && state.status === 'active' && (step.exercise.kind === 'puzzle' || step.exercise.kind === 'remove');
  return <div className="ogs-board-wrap" data-testid="ogs-board" data-window={`${vp.cols}x${vp.rows}`} style={{ ['--ogs-axis' as string]: `${size === 19 ? 50 : size === 13 ? 43 : 37}px` }}>
    <div className="ogs-board-axis ogs-board-axis--top">{Array.from({ length: vp.cols }, (_, i) => <span key={i}>{GO_COLS[vp.col + i]}</span>)}</div>
    <div className="ogs-board-axis ogs-board-axis--left">{Array.from({ length: vp.rows }, (_, i) => <span key={i}>{size - vp.row - i}</span>)}</div>
    <svg className="ogs-board-svg" viewBox={`${startX} ${startY} ${vp.cols * cell} ${vp.rows * cell}`} role="img" aria-label={`${size} 路互动棋盘`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="ogs-wood" x2=".9" y2="1"><stop stopColor="#e8bd77"/><stop offset=".48" stopColor="#e6b66d"/><stop offset="1" stopColor="#c98f4b"/></linearGradient>
        <radialGradient id="ogs-black"><stop stopColor="#555a58"/><stop offset=".64" stopColor="#202524"/><stop offset="1" stopColor="#060808"/></radialGradient>
        <radialGradient id="ogs-white"><stop stopColor="#fff"/><stop offset=".7" stopColor="#eff2eb"/><stop offset="1" stopColor="#bdc3b9"/></radialGradient>
      </defs>
      <rect x="0" y="0" width={size * cell} height={size * cell} fill="url(#ogs-wood)" />
      <g stroke="#674825" strokeWidth="3">
        {Array.from({ length: size }, (_, i) => <g key={i}>
          <line x1={position(0)} x2={position(size - 1)} y1={position(i)} y2={position(i)} />
          <line x1={position(i)} x2={position(i)} y1={position(0)} y2={position(size - 1)} />
        </g>)}
      </g>
      {starsFor(size).map(([x, y]) => <circle key={key(x, y)} cx={position(x)} cy={position(y)} r="7" fill="#50371c" />)}
      {state.board.flatMap((row, y) => row.map((stone, x) => stone && showPoint(x, y) ? <g key={key(x, y)}>
        <circle cx={position(x)} cy={position(y)} r="39" fill={`url(#ogs-${stone === 'B' ? 'black' : 'white'})`} stroke={stone === 'B' ? '#111718' : '#d5d8d0'} strokeWidth="3" />
        {selected.has(key(x, y)) && <circle cx={position(x)} cy={position(y)} r="33" fill="none" stroke="#75e9a0" strokeWidth="7" />}
        {extras.has(key(x, y)) && <text x={position(x)} y={position(y) + 20} textAnchor="middle" fontSize="64" fill="#ec635a">×</text>}
      </g> : null))}
      {Object.entries(step.letters).map(([point, label]) => {
        const [x, y] = point.split(',').map(Number);
        return showPoint(x, y) ? <text key={`l${point}`} x={position(x)} y={position(y) - 31} textAnchor="middle" fontSize="39" fontWeight="bold" fill="#183c28" paintOrder="stroke" stroke="#f3d496" strokeWidth="8">{label}</text> : null;
      })}
      {Object.entries(step.shapes).map(([point, shape]) => {
        const [x, y] = point.split(',').map(Number);
        return showPoint(x, y) ? <text key={`s${point}`} x={position(x)} y={position(y) + 13} textAnchor="middle" fontSize="38" fill="#ee914b">{shape === 'triangle' ? '△' : shape === 'square' ? '□' : shape === 'circle' ? '○' : shape}</text> : null;
      })}
      {clickable && Array.from({ length: vp.rows * vp.cols }, (_, i) => {
        const x = vp.col + i % vp.cols;
        const y = vp.row + Math.floor(i / vp.cols);
        if (step.exercise.kind === 'puzzle' && state.board[y][x]) return null;
        if (step.exercise.kind === 'remove' && !state.board[y][x]) return null;
        return <circle key={`h${i}`} cx={position(x)} cy={position(y)} r="47" fill="transparent" className="ogs-hit" role="button" tabIndex={0} aria-label={`${GO_COLS[x]}${size - y}`} data-testid={`ogs-point-${x}-${y}`} onClick={() => onPoint([x, y])} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onPoint([x, y]); } }} />;
      })}
    </svg>
    <div className="ogs-board-axis ogs-board-axis--right">{Array.from({ length: vp.rows }, (_, i) => <span key={i}>{size - vp.row - i}</span>)}</div>
    <div className="ogs-board-axis ogs-board-axis--bottom">{Array.from({ length: vp.cols }, (_, i) => <span key={i}>{GO_COLS[vp.col + i]}</span>)}</div>
  </div>;
}
