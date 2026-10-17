import { useCallback, useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import { Vector3 } from 'three';
import type { RootState } from '@react-three/fiber';
import type { GameState, PlayerInfo } from '../api';
import Board3D from '../components/Board3D';
import { gridToSurface, gridToWorld, STONE_RADIUS } from '../components/Board3D/constants';
import { frameAtTime, knownRegion, subtitleAtTime, type Point, type RecordingData, type ReplayFrame, type Region } from './tutorialMediaTimeline';

declare global {
  interface Window {
    __TUTORIAL_MEDIA_DATA?: RecordingData;
    __TUTORIAL_MEDIA_READY?: boolean;
    /** Returns a visual-state key after React, fonts and WebGL have painted. */
    __tutorialSetFrame?: (timeMs: number) => Promise<string>;
  }
}

const PLAYER: PlayerInfo = { player_type: 'human', player_subtype: '', name: '', calculated_rank: null, periods_used: 0, main_time_used: 0 };
const noop = () => {};
const TOGGLES = { coords: false, numbers: false, stoneDropEffect: false };

/** The sole top-left → game/3D coordinate conversion. Never derives move history. */
function asGameState(frame: ReplayFrame): GameState {
  const { size, stones } = frame.payload;
  const flip = ([col, row]: Point): Point => [col, size - 1 - row];
  return {
    game_id: 'tutorial-media', board_size: [size, size], komi: 0, handicap: 0, ruleset: 'japanese',
    current_node_id: frame.step, current_node_index: frame.step, history: [],
    player_to_move: frame.nextColor ?? 'B',
    stones: (['B', 'W'] as const).flatMap(color => stones[color].map(point => [color, flip(point), null, null] as GameState['stones'][number])),
    last_move: frame.last ? flip(frame.last) : null, prisoner_count: { B: 0, W: 0 }, analysis: null,
    commentary: '', is_root: frame.step === 0, is_pass: frame.currentMove?.kind === 'pass', end_result: null,
    children: [], ghost_stones: [], players_info: { B: PLAYER, W: PLAYER }, note: '', language: 'zh',
    ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false, show_move_numbers: false, show_coordinates: false, zen_mode: true },
  };
}

function ProjectionOverlay({ frame, region, state, overhead = false }: { frame: ReplayFrame; region: Region | null; state: RootState; overhead?: boolean }) {
  const { size, stones, labels = {}, letters = {}, shapes = {}, unknown_stones = [] } = frame.payload;
  const width = state.gl.domElement.clientWidth;
  const height = state.gl.domElement.clientHeight;
  const project = (col: number, row: number, onStone = false) => {
    const position = (onStone ? gridToWorld : gridToSurface)(col, size - 1 - row, size);
    if (onStone) position[1] += .22;
    const vector = new Vector3(...position).project(state.camera);
    return { x: (vector.x + 1) * width / 2, y: (1 - vector.y) * height / 2 };
  };
  const radius = (col: number, row: number) => Math.abs(project(col + STONE_RADIUS, row, true).x - project(col, row, true).x);
  const polygon = (left: number, top: number, right: number, bottom: number) =>
    [[left, top], [right, top], [right, bottom], [left, bottom]].map(([col, row], index) => {
      const point = project(col, row);
      return `${index ? 'L' : 'M'}${point.x},${point.y}`;
    }).join(' ') + 'Z';
  const black = new Set(stones.B.map(point => point.join(',')));
  const occupied = new Set([...stones.B, ...stones.W].map(point => point.join(',')));
  const unknown = new Set(unknown_stones.map(stone => stone.point.join(',')));
  const markerColor = (key: string) => black.has(key) ? '#fff' : '#171717';
  const outline = region ? polygon(Math.max(-.8, region.col - .5), Math.max(-.8, region.row - .5), Math.min(size - .2, region.col + region.cols - .5), Math.min(size - .2, region.row + region.rows - .5)) : '';
  return <svg className="tm-overlay" viewBox={`0 0 ${width} ${height}`} aria-label="棋图标记与未知范围">
    <path d={outline} fill="none" stroke="#746443" strokeWidth="1" strokeDasharray="4 3" data-testid="tutorial-known-region" data-known-region={region ? `${region.col},${region.row},${region.cols},${region.rows}` : 'unknown'} />
    {unknown_stones.map(stone => {
      const [col, row] = stone.point;
      const { x, y } = project(col, row, true);
      const r = radius(col, row);
      const key = stone.point.join(',');
      return <g key={`unknown-${key}`} data-testid="tutorial-unknown-stone"><circle cx={x} cy={y} r={r} fill="#999c9e" stroke="#4f5357" strokeWidth="1.5" strokeDasharray="3 2" />
        {!labels[key] && !letters[key] && !shapes[key] && <text x={x} y={y} dominantBaseline="central" textAnchor="middle" fontSize={r * 1.3} fill="#222">?</text>}</g>;
    })}
    {Object.entries({ ...labels, ...letters }).map(([key, text]) => {
      const [col, row] = key.split(',').map(Number);
      const onStone = occupied.has(key) || unknown.has(key);
      const { x, y } = project(col, row, onStone);
      const r = radius(col, row);
      return <g key={`text-${key}`} data-annotation-point={key}>
        {!onStone && <rect x={x - r * .75} y={y - r * .75} width={r * 1.5} height={r * 1.5} rx="2" fill="#c9a061" />}
        <text x={x} y={y} textAnchor="middle" dominantBaseline="central" fill={markerColor(key)} fontWeight="600" fontSize={r * (text.length > 1 ? .95 : 1.3)}
          fontFamily={overhead ? 'Arial, sans-serif' : undefined}
          stroke={overhead && onStone ? black.has(key) ? '#15181c' : '#fffdf6' : undefined}
          strokeWidth={overhead && onStone ? .8 : undefined} paintOrder="stroke fill">{text}</text>
      </g>;
    })}
    {Object.entries(shapes).map(([key, shape]) => {
      const [col, row] = key.split(',').map(Number);
      const { x, y } = project(col, row, occupied.has(key) || unknown.has(key));
      const r = radius(col, row) * .6;
      return <g key={`shape-${key}`} data-annotation-point={key} fill="none" stroke={markerColor(key)} strokeWidth="2">
        {shape === 'triangle' && <polygon points={`${x},${y-r} ${x-r*.866},${y+r*.5} ${x+r*.866},${y+r*.5}`} />}
        {shape === 'circle' && <circle cx={x} cy={y} r={r} />}
        {shape === 'square' && <rect x={x-r} y={y-r} width={r*2} height={r*2} />}
        {shape === 'cross' && <path d={`M${x-r},${y-r}L${x+r},${y+r}M${x-r},${y+r}L${x+r},${y-r}`} />}
      </g>;
    })}
    {overhead && frame.last && occupied.has(frame.last.join(',')) && (() => {
      const [col, row] = frame.last;
      const { x, y } = project(col, row, true);
      return <circle data-testid="tutorial-last-move" cx={x} cy={y} r={radius(col, row) * .82}
        fill="none" stroke={markerColor(frame.last.join(','))} strokeWidth="1.5" />;
    })()}
  </svg>;
}

export default function TutorialMediaRecorder() {
  const data = window.__TUTORIAL_MEDIA_DATA;
  const overhead = data?.render_mode === '2d';
  const [timeMs, setTimeMs] = useState(0);
  const [canvasState, setCanvasState] = useState<RootState | null>(null);
  const onCanvasReady = useCallback((state: RootState) => setCanvasState(state), []);
  useEffect(() => {
    if (!data || !canvasState) return;
    let lastPaintedKey: string | null = null;
    window.__tutorialSetFrame = async (time: number) => {
      const frame = frameAtTime(data, time);
      const key = JSON.stringify([frame.step, subtitleAtTime(data.narration, data.speech_timing, time)]);
      if (key === lastPaintedKey) return key;
      flushSync(() => setTimeMs(time));
      await document.fonts.ready;
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      if (canvasState) canvasState.gl.render(canvasState.scene, canvasState.camera);
      lastPaintedKey = key;
      return key;
    };
    window.__TUTORIAL_MEDIA_READY = true;
    return () => { window.__TUTORIAL_MEDIA_READY = false; delete window.__tutorialSetFrame; };
  }, [data, canvasState]);

  if (!data) return <div>缺少录制快照</div>;
  const frame = frameAtTime(data, timeMs);
  const region = knownRegion(data);
  const distance = (frame.payload.size + .6) / (2 * Math.tan(Math.PI / 9)) * 1.12;
  const angle = .10 * Math.PI;
  const cameraPosition: [number, number, number] = [0, 1.2 + distance * Math.cos(angle), distance * Math.sin(angle)];
  const staticLabel = data.frames.length > 1 ? '静态讲解·落子时间待校准' : '静态讲解·手顺待校准';
  const gameState = asGameState(frame);
  if (overhead) gameState.last_move = null; // The SVG ring stays clear of material highlights.
  return <main className="tm-recorder" data-step={frame.step} data-render-mode={data.render_mode}>
    <div className="tm-board-area"><div className="tm-board-square">
      <Board3D gameState={gameState} onMove={noop} analysisToggles={TOGGLES} readOnly disableControls
        cameraPosition={overhead ? [0, 26, 0] : cameraPosition} cameraTarget={[0, 1.2, 0]}
        cameraUp={overhead ? [0, 0, -1] : undefined} orthographicSpan={overhead ? frame.payload.size + .6 : undefined}
        recordingAppearance={overhead ? 'overhead' : undefined} frameloop="demand" onCanvasReady={onCanvasReady} />
      {canvasState && <ProjectionOverlay frame={frame} region={region} state={canvasState} overhead={overhead} />}
    </div>{data.step_cues.status !== 'complete' && <div className="tm-static" data-testid="tutorial-static-reason">{staticLabel}</div>}</div>
    <div className="tm-caption"><span>{subtitleAtTime(data.narration, data.speech_timing, timeMs)}</span></div>
  </main>;
}
