import { useCallback, useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import { Vector3 } from 'three';
import type { RootState } from '@react-three/fiber';
import type { GameState, PlayerInfo } from '../api';
import Board3D from '../components/Board3D';
import { loadRecordingStoneSprites, type RecordingStoneSprites } from '../components/Board3D/tutorialStoneTextures';
import { gridToSurface, gridToWorld, STONE_HEIGHT, STONE_RADIUS } from '../components/Board3D/constants';
import { TUTORIAL_STONE_DIAMETER_RATIO } from '../components/tutorials/tutorialStoneSprites';
import { frameAtTime, placementsAtTime, subtitleAtTime, type Point, type RecordingData, type RecordingPlacement, type ReplayFrame } from './tutorialMediaTimeline';

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

function ProjectionOverlay({ frame, state, surfaceMarkers = false, spriteStones = false, placements }: { frame: ReplayFrame; state: RootState; surfaceMarkers?: boolean; spriteStones?: boolean; placements: RecordingPlacement[] }) {
  const { size, stones, labels = {}, letters = {}, shapes = {}, unknown_stones = [], presentation_arrows = [], presentation_callouts = [] } = frame.payload;
  const width = state.gl.domElement.clientWidth;
  const height = state.gl.domElement.clientHeight;
  const project = (col: number, row: number, onStone = false, extraHeight = 0) => {
    const position = (onStone ? gridToWorld : gridToSurface)(col, size - 1 - row, size);
    if (onStone) position[1] += STONE_HEIGHT + extraHeight;
    const vector = new Vector3(...position).project(state.camera);
    return { x: (vector.x + 1) * width / 2, y: (1 - vector.y) * height / 2 };
  };
  const placementAt = (col: number, row: number) => placements.find(pose => pose.point[0] === col && pose.point[1] === row);
  const black = new Set(stones.B.map(point => point.join(',')));
  const radius = (col: number, row: number) => Math.abs(project(col + STONE_RADIUS, row, true).x - project(col, row, true).x)
    * (placementAt(col, row)?.scale ?? 1)
    * (spriteStones && black.has(`${col},${row}`) ? TUTORIAL_STONE_DIAMETER_RATIO.B : 1);
  // Project the local X/Z tangent basis, so glyphs and rings follow the board/stone
  // top instead of facing the screen. Orthographic recording makes this affine exact.
  const marker = (col: number, row: number, onStone: boolean) => {
    const placement = onStone ? placementAt(col, row) : undefined;
    const extraHeight = placement ? placement.lift + STONE_HEIGHT * (placement.scale - 1) : 0;
    const center = project(col, row, onStone, extraHeight);
    if (!surfaceMarkers) return { ...center, transform: undefined };
    const along = project(col + 1, row, onStone, extraHeight);
    const down = project(col, row + 1, onStone, extraHeight);
    const unit = Math.hypot(along.x - center.x, along.y - center.y);
    return { x: 0, y: 0, transform: `matrix(${(along.x - center.x) / unit} ${(along.y - center.y) / unit} ${(down.x - center.x) / unit} ${(down.y - center.y) / unit} ${center.x} ${center.y})` };
  };
  const occupied = new Set([...stones.B, ...stones.W].map(point => point.join(',')));
  const unknown = new Set(unknown_stones.map(stone => stone.point.join(',')));
  const lastKey = frame.last?.join(',');
  const crowdedLast = lastKey && ((labels[lastKey] && letters[lastKey]) || (shapes[lastKey] && (labels[lastKey] || letters[lastKey])));
  const markerColor = (key: string) => black.has(key) ? '#fff' : '#171717';
  return <svg className="tm-overlay" viewBox={`0 0 ${width} ${height}`} aria-label="棋图标记">
    {presentation_arrows.length > 0 && <defs><marker id="tm-presentation-arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
      <path d="M0,0L6,3L0,6Z" fill="#9a3127" />
    </marker></defs>}
    {presentation_arrows.map(arrow => {
      const from = project(...arrow.from);
      const to = project(...arrow.to);
      return <path key={arrow.id} data-presentation-arrow={arrow.id} data-source-pointer={arrow.source_pointer}
        d={`M${from.x} ${from.y}L${to.x} ${to.y}`} fill="none" stroke="#9a3127"
        strokeWidth={radius(...arrow.from) * .12} strokeLinecap="round" markerEnd="url(#tm-presentation-arrowhead)" />;
    })}
    {presentation_callouts.some(callout => callout.side !== 'board') && <defs><marker id="tm-callout-arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
      <path d="M0,0L6,3L0,6Z" fill="#f4f1e9" />
    </marker></defs>}
    {presentation_callouts.map(callout => {
      const anchor = project(...callout.anchor);
      const next = project(callout.anchor[0] + 1, callout.anchor[1]);
      const unit = Math.hypot(next.x - anchor.x, next.y - anchor.y);
      if (callout.side === 'board') return <g key={callout.id} data-presentation-callout={callout.id} data-callout-side={callout.side} data-source-pointer={callout.source_pointer}>
        <text x={anchor.x} y={anchor.y} textAnchor="middle" dominantBaseline="central" fill="#171717" fontSize={.9 * unit} fontWeight="600">{callout.text}</text>
      </g>;
      const top = callout.side === 'top';
      const from = { x: anchor.x + (top ? 0 : .35 * unit), y: anchor.y - (top ? .35 * unit : 0) };
      const to = { x: anchor.x + (top ? 0 : 1.15 * unit), y: anchor.y - (top ? 1.15 * unit : 0) };
      const fontSize = .8 * unit;
      const x = top ? to.x : to.x + .5 * unit;
      const y = top ? to.y - .5 * unit - (callout.text.length - 1) * fontSize : to.y;
      return <g key={callout.id} data-presentation-callout={callout.id} data-callout-side={callout.side} data-source-pointer={callout.source_pointer}>
        <path d={`M${from.x} ${from.y}L${to.x} ${to.y}`} stroke="#f4f1e9" strokeWidth={.06 * unit} fill="none" markerEnd="url(#tm-callout-arrowhead)" />
        <text x={x} y={y} textAnchor={top ? 'middle' : 'start'} dominantBaseline="central" fill="#f4f1e9" fontSize={fontSize} fontWeight="600">
          {top ? [...callout.text].map((character, index) => <tspan key={index} x={x} dy={index ? fontSize : 0}>{character}</tspan>) : callout.text}
        </text>
      </g>;
    })}
    {unknown_stones.map(stone => {
      const [col, row] = stone.point;
      const { x, y, transform } = marker(col, row, true);
      const r = radius(col, row);
      const strokeScale = spriteStones ? r / 16 : 1;
      const key = stone.point.join(',');
      return <g key={`unknown-${key}`} transform={transform} data-testid="tutorial-unknown-stone"><circle cx={x} cy={y} r={r} fill="#999c9e" stroke="#4f5357" strokeWidth={1.5 * strokeScale} strokeDasharray={`${3 * strokeScale} ${2 * strokeScale}`} />
        {!labels[key] && !letters[key] && !shapes[key] && <text x={x} y={y} dominantBaseline="central" textAnchor="middle" fontSize={r * 1.3} fill="#222">?</text>}</g>;
    })}
    {(['labels', 'letters'] as const).flatMap(kind => Object.entries(kind === 'labels' ? labels : letters).map(([key, text]) => {
      const [col, row] = key.split(',').map(Number);
      const onStone = occupied.has(key) || unknown.has(key);
      const { x: centerX, y: centerY, transform } = marker(col, row, onStone);
      const r = radius(col, row);
      const paired = Boolean(labels[key] && letters[key]);
      const x = centerX + (paired ? (kind === 'labels' ? -.38 : .38) * r : 0);
      const y = centerY + (shapes[key] ? .16 * r : 0);
      return <g key={`${kind}-${key}`} transform={transform} data-annotation-kind={kind} data-annotation-point={key}>
        {!onStone && (kind === 'labels' || !labels[key]) && <rect x={centerX - r * (paired ? 1 : .75)} y={y - r * .75} width={r * (paired ? 2 : 1.5)} height={r * 1.5} rx="2" fill="#c9a061" />}
        <text x={x} y={y} textAnchor="middle" dominantBaseline="central" fill={markerColor(key)} fontWeight="600" fontSize={r * (paired ? .85 : text.length > 1 ? .95 : 1.3)}
          fontFamily="Arial, sans-serif"
          stroke={onStone ? black.has(key) ? '#15181c' : '#fffdf6' : undefined}
          strokeWidth={onStone ? .8 * (spriteStones ? r / 16 : 1) : undefined} paintOrder="stroke fill">{text}</text>
      </g>;
    }))}
    {Object.entries(shapes).map(([key, shape]) => {
      const [col, row] = key.split(',').map(Number);
      const { x, y: centerY, transform } = marker(col, row, occupied.has(key) || unknown.has(key));
      const stoneRadius = radius(col, row);
      const besideText = Boolean(labels[key] || letters[key]);
      const y = centerY - (besideText ? .67 * stoneRadius : 0);
      const r = stoneRadius * (besideText ? .25 : .6);
      return <g key={`shape-${key}`} transform={transform} data-annotation-kind="shapes" data-annotation-point={key} fill="none" stroke={markerColor(key)} strokeWidth={(besideText ? 1.3 : 2) * (spriteStones ? stoneRadius / 16 : 1)}>
        {shape === 'triangle' && <polygon points={`${x},${y-r} ${x-r*.866},${y+r*.5} ${x+r*.866},${y+r*.5}`} />}
        {shape === 'circle' && <circle cx={x} cy={y} r={r} />}
        {shape === 'square' && <rect x={x-r} y={y-r} width={r*2} height={r*2} />}
        {shape === 'cross' && <path d={`M${x-r},${y-r}L${x+r},${y+r}M${x-r},${y+r}L${x+r},${y-r}`} />}
      </g>;
    })}
    {frame.last && !crowdedLast && occupied.has(frame.last.join(',')) && (() => {
      const [col, row] = frame.last;
      const { x, y, transform } = marker(col, row, true);
      const r = radius(col, row);
      return <g transform={transform}><circle data-testid="tutorial-last-move" cx={x} cy={y} r={r * .82}
        fill="none" stroke={markerColor(frame.last.join(','))} strokeWidth={1.5 * (spriteStones ? r / 16 : 1)} /></g>;
    })()}
  </svg>;
}

export default function TutorialMediaRecorder() {
  const data = window.__TUTORIAL_MEDIA_DATA;
  const overhead = data?.render_mode === '2d';
  const solidWood = data?.render_mode === '3d';
  const [timeMs, setTimeMs] = useState(0);
  const [canvasState, setCanvasState] = useState<RootState | null>(null);
  const [stoneSprites, setStoneSprites] = useState<RecordingStoneSprites | null>(null);
  const [spriteError, setSpriteError] = useState<unknown>(null);
  const onCanvasReady = useCallback((state: RootState) => setCanvasState(state), []);
  useEffect(() => {
    if (!overhead) return;
    let active = true;
    loadRecordingStoneSprites().then(
      textures => { if (active) setStoneSprites(textures); },
      error => { if (active) setSpriteError(error); },
    );
    return () => { active = false; };
  }, [overhead]);
  useEffect(() => {
    if (!data || !canvasState || (overhead && !stoneSprites)) return;
    let lastPaintedKey: string | null = null;
    window.__tutorialSetFrame = async (time: number) => {
      const frame = frameAtTime(data, time);
      const key = JSON.stringify([frame.step, subtitleAtTime(data.narration, data.speech_timing, time), placementsAtTime(data, time)]);
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
  }, [data, canvasState, overhead, stoneSprites]);

  if (spriteError) throw spriteError;
  if (!data) return <div>缺少录制快照</div>;
  const frame = frameAtTime(data, timeMs);
  const placements = placementsAtTime(data, timeMs);
  const recordingPlacement = placements.map(pose => ({ ...pose, point: [pose.point[0], frame.payload.size - 1 - pose.point[1]] as Point }));
  const distance = (frame.payload.size + .6) / (2 * Math.tan(Math.PI / 9)) * 1.12;
  const angle = 35 * Math.PI / 180;
  const cameraPosition: [number, number, number] = [0, 1.2 + distance * Math.cos(angle), distance * Math.sin(angle)];
  const outputProfile = data.output_profile === 'galaxy-4k-v1' || data.output_profile === 'kiosk-7-v1' ? data.output_profile : undefined;
  const hasMarginCallouts = data.step_cues.presentation_plan?.callouts?.some(callout => callout.side !== 'board');
  const orthographicSpan = frame.payload.size + (hasMarginCallouts ? 9 : overhead ? .6 : 2.6);
  const gameState = asGameState(frame);
  gameState.last_move = null; // The SVG ring stays clear of material highlights.
  return <main className="tm-recorder" data-output-profile={outputProfile} data-step={frame.step} data-render-mode={data.render_mode} data-board-appearance={solidWood ? 'solid-wood' : 'overhead'}>
    <div className="tm-board-area"><div className="tm-board-square">
      <Board3D gameState={gameState} onMove={noop} analysisToggles={TOGGLES} readOnly disableControls
        cameraPosition={overhead ? [0, 26, 0] : cameraPosition} cameraTarget={[0, 1.2, 0]}
        cameraUp={overhead ? [0, 0, -1] : undefined} orthographicSpan={orthographicSpan}
        recordingAppearance={overhead ? 'overhead' : 'solid-wood'} recordingPlacement={recordingPlacement}
        recordingStoneSprites={overhead ? stoneSprites ?? undefined : undefined} recordingVisualSeed={overhead ? data.visual_seed ?? 'tutorial' : undefined}
        frameloop="demand" onCanvasReady={onCanvasReady} />
      {canvasState && <ProjectionOverlay frame={frame} state={canvasState} surfaceMarkers={solidWood} spriteStones={overhead} placements={placements} />}
    </div></div>
    <div className="tm-caption"><span>{subtitleAtTime(data.narration, data.speech_timing, timeMs)}</span></div>
  </main>;
}
