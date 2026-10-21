import { act, render, screen } from '@testing-library/react';
import type { RootState } from '@react-three/fiber';
import { OrthographicCamera, Scene, Texture, Vector3 } from 'three';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Board3D from '../components/Board3D';
import { loadRecordingStoneSprites } from '../components/Board3D/tutorialStoneTextures';
import { gridToSurface } from '../components/Board3D/constants';
import TutorialMediaRecorder from './TutorialMediaRecorder';
import type { RecordingData, ReplayFrame } from './tutorialMediaTimeline';

// WebGL is exercised by test_tutorial_media_render.py; jsdom checks the recorder boundary.
vi.mock('../components/Board3D', () => ({ default: vi.fn(() => null) }));
vi.mock('../components/Board3D/tutorialStoneTextures', () => ({ loadRecordingStoneSprites: vi.fn() }));

const sprites = { B: new Texture(), W: Array.from({ length: 32 }, () => new Texture()) };
let resolveSprites: (value: typeof sprites) => void;
beforeEach(() => {
  vi.mocked(loadRecordingStoneSprites).mockImplementation(() => new Promise(resolve => { resolveSprites = resolve; }));
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 0; });
  Object.defineProperty(document, 'fonts', { configurable: true, value: { ready: Promise.resolve() } });
});
afterEach(() => {
  delete window.__TUTORIAL_MEDIA_DATA;
  delete window.__tutorialSetFrame;
  delete window.__TUTORIAL_MEDIA_READY;
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

function recordingData(overrides: Partial<RecordingData> = {}): RecordingData {
  const frames: ReplayFrame[] = [{ step: 0, payload: { size: 19, stones: { B: [[14, 2]], W: [[15, 14]] },
    unknown_stones: [{ point: [12, 8], color: null }] }, last: null, appeared_stones: [] }];
  return {
    narration: '静态局面。', render_mode: '2d', visual_seed: '1031', board_payload: frames[0].payload, frames,
    speech_timing: { schema_version: 1, audio_sha256: 'audio', duration_ms: 4000,
      boundaries: [{ text: '静态局面。', start_ms: 100, duration_ms: 3000 }] },
    step_cues: { schema_version: 1, mode: 'static', audio_sha256: 'audio', status: 'complete', frames, objects: [], events: [],
      cues: [{ step: 0, at_ms: 0, source: 'initial' }] },
    ...overrides,
  };
}

function attachCanvas(width = 800, camera?: OrthographicCamera) {
  const board = vi.mocked(Board3D).mock.calls.at(-1)![0];
  const actualCamera = camera ?? new OrthographicCamera(-10, 10, 10, -10, .1, 100);
  if (!camera) {
    actualCamera.position.set(0, 26, 0);
    actualCamera.up.set(0, 0, -1);
    actualCamera.lookAt(0, 1.2, 0);
    actualCamera.updateMatrixWorld();
  }
  const render = vi.fn();
  act(() => board.onCanvasReady?.({ camera: actualCamera, scene: new Scene(),
    gl: { domElement: { clientWidth: width, clientHeight: width }, render },
  } as unknown as RootState));
  return { camera: actualCamera, render };
}

it.each([undefined, 'galaxy-4k-v1', 'kiosk-7-v1'] as const)('waits for approved textures and preserves the static complete profile %s', async outputProfile => {
  window.__TUTORIAL_MEDIA_DATA = recordingData({ output_profile: outputProfile });
  render(<TutorialMediaRecorder />);
  const recorder = screen.getByRole('main');
  if (outputProfile) expect(recorder).toHaveAttribute('data-output-profile', outputProfile);
  else expect(recorder).not.toHaveAttribute('data-output-profile');
  expect(recorder).toHaveAttribute('data-step', '0');
  const board = vi.mocked(Board3D).mock.calls.at(-1)?.[0];
  expect(board).toMatchObject({
    cameraPosition: [0, 26, 0], cameraTarget: [0, 1.2, 0], cameraUp: [0, 0, -1],
    orthographicSpan: 19.6, recordingAppearance: 'overhead',
    readOnly: true, disableControls: true, frameloop: 'demand',
    gameState: { stones: [['B', [14, 16], null, null], ['W', [15, 4], null, null]], last_move: null },
  });
  expect(window.__TUTORIAL_MEDIA_READY).not.toBe(true);
  attachCanvas();
  expect(window.__TUTORIAL_MEDIA_READY).not.toBe(true);
  await act(async () => resolveSprites(sprites));
  expect(window.__TUTORIAL_MEDIA_READY).toBe(true);
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0]).toMatchObject({ recordingStoneSprites: sprites, recordingVisualSeed: '1031' });
  expect(screen.queryByTestId('tutorial-static-reason')).not.toBeInTheDocument();
  expect(screen.queryByTestId('tutorial-known-region')).not.toBeInTheDocument();
  expect(screen.getByTestId('tutorial-unknown-stone')).toHaveTextContent('?');
});

it('blocks pending recordings before rendering the fully annotated source board', () => {
  const data = recordingData();
  window.__TUTORIAL_MEDIA_DATA = { ...data, step_cues: { ...data.step_cues, status: 'pending', reason: 'Missing spoken A', frames: [], cues: [] } };
  expect(() => render(<TutorialMediaRecorder />)).toThrow(/pending.*Missing spoken A/i);
  expect(vi.mocked(Board3D)).not.toHaveBeenCalled();
  expect(window.__TUTORIAL_MEDIA_READY).not.toBe(true);
});

it('reveals grouped stones, independent co-located marks and source arrows at their actual cues, including on rewind', async () => {
  const data = recordingData({ render_mode: '3d' });
  const frames: ReplayFrame[] = [
    { step: 0, payload: { size: 19, stones: { B: [[8, 8]], W: [] } }, last: null, appeared_stones: [] },
    { step: 1, payload: { size: 19, stones: { B: [[8, 8], [2, 0]], W: [[4, 2]] }, labels: { '2,0': '1', '4,2': '2' } },
      last: null, currentMove: null, appeared_stones: [{ color: 'B', point: [2, 0] }, { color: 'W', point: [4, 2] }] },
    { step: 2, payload: { size: 19, stones: { B: [[8, 8], [2, 0]], W: [[4, 2]] }, labels: { '2,0': '1', '4,2': '2', '10,10': '9' },
      letters: { '2,0': 'A', '10,10': 'B' }, shapes: { '2,0': 'triangle' },
      presentation_arrows: [{ id: 'arrow:direction', from: [2, 0], to: [4, 2], source_pointer: '/source/page.png', image_sha256: 'a'.repeat(64) }] },
      last: null, currentMove: null, appeared_stones: [] },
  ];
  window.__TUTORIAL_MEDIA_DATA = { ...data, board_payload: frames[2].payload, frames,
    step_cues: { ...data.step_cues, mode: 'presentation', frames, cues: [
      { step: 0, at_ms: 0, source: 'initial' }, { step: 1, at_ms: 1000, source: 'speech_end' }, { step: 2, at_ms: 1400, source: 'speech_end' },
    ] } };
  render(<TutorialMediaRecorder />);
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].gameState.stones).toEqual([['B', [8, 10], null, null]]);
  const canvas = attachCanvas();
  expect(document.querySelector('[data-annotation-point]')).toBeNull();
  await act(async () => { await window.__tutorialSetFrame!(999); });
  expect(document.querySelector('[data-annotation-point]')).toBeNull();
  await act(async () => { await window.__tutorialSetFrame!(1000); });
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].recordingPlacement).toEqual([
    { point: [2, 18], lift: .25, scale: .96 }, { point: [4, 16], lift: .25, scale: .96 },
  ]);
  expect(document.querySelector('[data-annotation-kind="labels"][data-annotation-point="2,0"]')).toHaveTextContent('1');
  expect(document.querySelector('[data-annotation-kind="letters"]')).toBeNull();
  expect(document.querySelector('[data-annotation-kind="shapes"]')).toBeNull();
  expect(document.querySelector('[data-presentation-arrow]')).toBeNull();
  let before = '';
  await act(async () => { before = await window.__tutorialSetFrame!(1360); });
  canvas.render.mockClear();
  let after = '';
  await act(async () => { after = await window.__tutorialSetFrame!(1400); });
  expect(after).not.toBe(before); // A new annotation frame must paint even with the same caption and no placement.
  expect(canvas.render).toHaveBeenCalledOnce();
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].recordingPlacement).toEqual([]);
  const label = document.querySelector('[data-annotation-kind="labels"][data-annotation-point="2,0"] text')!;
  const letter = document.querySelector('[data-annotation-kind="letters"][data-annotation-point="2,0"] text')!;
  expect(label).toHaveTextContent('1');
  expect(letter).toHaveTextContent('A');
  expect(label.getAttribute('x')).not.toBe(letter.getAttribute('x'));
  expect(document.querySelector('[data-annotation-kind="shapes"][data-annotation-point="2,0"] polygon')).not.toBeNull();
  const arrow = document.querySelector('[data-presentation-arrow="arrow:direction"]')!;
  expect(arrow).toHaveAttribute('marker-end', 'url(#tm-presentation-arrowhead)');
  const projected = ([col, row]: [number, number]) => {
    const vector = new Vector3(...gridToSurface(col, 18 - row, 19)).project(canvas.camera);
    return `${(vector.x + 1) * 400} ${(1 - vector.y) * 400}`;
  };
  expect(arrow).toHaveAttribute('d', `M${projected([2, 0])}L${projected([4, 2])}`);
  expect(document.querySelectorAll('[data-annotation-point="10,10"] rect')).toHaveLength(1);
  expect(document.querySelector('[data-presentation-arrow]')?.getAttribute('data-source-pointer')).toBe('/source/page.png');
  await act(async () => { await window.__tutorialSetFrame!(1000); });
  expect(document.querySelector('[data-annotation-kind="letters"]')).toBeNull();
  expect(document.querySelector('[data-presentation-arrow]')).toBeNull();
  await act(async () => { await window.__tutorialSetFrame!(0); });
  expect(document.querySelector('[data-annotation-point]')).toBeNull();
});

it('keeps solid wood projection and responsive overhead marker strokes', async () => {
  const data = recordingData({ render_mode: '3d', visual_seed: undefined });
  const frames: ReplayFrame[] = [{ step: 0, payload: { size: 19, stones: { B: [[2, 0]], W: [] },
    labels: { '2,0': '1' }, letters: { '4,2': 'A' }, shapes: { '6,2': 'triangle' },
    unknown_stones: [{ point: [8, 2], color: null }] }, last: [2, 0], appeared_stones: [] }];
  window.__TUTORIAL_MEDIA_DATA = { ...data, frames, step_cues: { ...data.step_cues, frames } };
  const { rerender } = render(<TutorialMediaRecorder />);
  const board = vi.mocked(Board3D).mock.calls.at(-1)![0];
  expect(board).toMatchObject({ recordingAppearance: 'solid-wood', orthographicSpan: 21.6, gameState: { last_move: null } });
  expect(board.cameraPosition?.[0]).toBe(0);
  const camera = new OrthographicCamera(-342, 342, 342, -342, .1, 100);
  camera.position.set(...board.cameraPosition!);
  camera.zoom = 684 / board.orthographicSpan!;
  camera.lookAt(0, 1.2, 0);
  camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  attachCanvas(684, camera);
  const number = document.querySelector('[data-annotation-point="2,0"]')!;
  const matrix = number.getAttribute('transform')!.slice(7, -1).split(' ').map(Number);
  expect(matrix[0] * matrix[3] - matrix[1] * matrix[2]).toBeCloseTo(Math.cos(35 * Math.PI / 180));
  const top = new Vector3(-7, 1.64, -9).project(camera);
  expect(matrix[5]).toBeCloseTo((1 - top.y) * 342);
  expect(document.querySelector('[data-annotation-point="4,2"]')?.getAttribute('transform')).toMatch(/^matrix\(/);
  expect(document.querySelector('[data-annotation-point="6,2"]')?.getAttribute('transform')).toMatch(/^matrix\(/);
  expect(screen.getByTestId('tutorial-last-move').parentElement?.getAttribute('transform')).toBe(number.getAttribute('transform'));
  expect(number.querySelector('text')).toHaveAttribute('stroke-width', '0.8');
  window.__TUTORIAL_MEDIA_DATA.render_mode = '2d';
  rerender(<TutorialMediaRecorder />);
  await act(async () => resolveSprites(sprites));
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0]).toMatchObject({
    recordingAppearance: 'overhead', cameraPosition: [0, 26, 0], orthographicSpan: 19.6, recordingVisualSeed: 'tutorial',
  });
  expect(document.querySelector('[data-annotation-point="2,0"]')).not.toHaveAttribute('transform');
  const strokes = () => [
    number.querySelector('text'), document.querySelector('[data-annotation-point="6,2"]'),
    screen.getByTestId('tutorial-unknown-stone').querySelector('circle'), screen.getByTestId('tutorial-last-move'),
  ].map(element => Number(element?.getAttribute('stroke-width')));
  const baselineStrokes = strokes();
  attachCanvas(1880, camera);
  strokes().forEach((stroke, index) => expect(stroke / baselineStrokes[index]).toBeCloseTo(1880 / 684));
});

it('keeps the last move ring clear of multiple co-located marks', () => {
  const data = recordingData({ render_mode: '3d' });
  const frames: ReplayFrame[] = [{ step: 0, payload: { size: 19, stones: { B: [[2, 0]], W: [] },
    labels: { '2,0': '1' }, letters: { '2,0': 'A' }, shapes: { '2,0': 'triangle' } },
    last: [2, 0], appeared_stones: [] }];
  window.__TUTORIAL_MEDIA_DATA = { ...data, frames, step_cues: { ...data.step_cues, frames } };
  render(<TutorialMediaRecorder />);
  attachCanvas();
  expect(document.querySelectorAll('[data-annotation-point="2,0"]')).toHaveLength(3);
  expect(screen.queryByTestId('tutorial-last-move')).not.toBeInTheDocument();
});

it.each([{ profile: 'galaxy-4k-v1', width: 1880 }, { profile: 'kiosk-7-v1', width: 576 }] as const)(
  'reserves fixed edge margins and reveals sixteen source callouts at group cues in $profile', async ({ profile, width }) => {
    const data = recordingData({ output_profile: profile });
    const source = { source_pointer: '/routes/0', image_sha256: 'a'.repeat(64) };
    const callouts = ['top-left', 'top-right', 'right-top', 'right-bottom'].flatMap((group, index) =>
      Array.from({ length: 4 }, (_, route) => ({ id: `callout:${group}-${route + 1}`, text: `${'一二三四'[route]}路线`,
        side: index < 2 ? 'top' as const : 'right' as const,
        anchor: (index < 2 ? [index === 0 ? route : 18 - route, 0] : [18, index === 2 ? route : 18 - route]) as [number, number], ...source })));
    const frames: ReplayFrame[] = Array.from({ length: 5 }, (_, step) => ({ step,
      payload: { size: 19, stones: { B: [], W: [] }, presentation_callouts: callouts.slice(0, step * 4) },
      last: null, currentMove: null, appeared_stones: [] }));
    window.__TUTORIAL_MEDIA_DATA = { ...data, frames, board_payload: frames[0].payload,
      step_cues: { ...data.step_cues, frames, mode: 'presentation', presentation_plan: { callouts },
        cues: frames.map(frame => ({ step: frame.step, at_ms: frame.step * 500, source: frame.step ? 'speech_end' as const : 'initial' as const })) } };
    render(<TutorialMediaRecorder />);
    expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].orthographicSpan).toBe(28);
    const camera = new OrthographicCamera(-14, 14, 14, -14, .1, 100);
    camera.position.set(0, 26, 0); camera.up.set(0, 0, -1); camera.lookAt(0, 1.2, 0); camera.updateMatrixWorld();
    attachCanvas(width, camera);
    await act(async () => resolveSprites(sprites));
    expect(document.querySelector('[data-presentation-callout]')).toBeNull();
    for (let step = 1; step <= 4; step++) {
      await act(async () => { await window.__tutorialSetFrame!(step * 500 - 1); });
      expect(document.querySelectorAll('[data-presentation-callout]')).toHaveLength((step - 1) * 4);
      await act(async () => { await window.__tutorialSetFrame!(step * 500); });
      expect(document.querySelectorAll('[data-presentation-callout]')).toHaveLength(step * 4);
      expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].orthographicSpan).toBe(28);
      expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].recordingPlacement).toEqual([]);
    }
    const top = document.querySelector('[data-presentation-callout="callout:top-left-1"]')!;
    expect(top.querySelectorAll('tspan')).toHaveLength(3);
    expect(top.querySelector('text')).toHaveTextContent('一路线');
    const right = document.querySelector('[data-presentation-callout="callout:right-top-1"]')!;
    expect(right.querySelector('text')).toHaveTextContent('一路线');
    expect(right.querySelectorAll('tspan')).toHaveLength(0);
    for (const group of document.querySelectorAll('[data-presentation-callout]')) {
      const path = group.querySelector('path')!;
      const [x1,y1,x2,y2] = path.getAttribute('d')!.match(/-?[0-9.]+/g)!.map(Number);
      expect([x1,y1,x2,y2].every(value => value > 0 && value < width)).toBe(true);
      if (group.getAttribute('data-callout-side') === 'top') expect(y2).toBeLessThan(y1);
      else expect(x2).toBeGreaterThan(x1);
      expect(path).toHaveAttribute('marker-end', 'url(#tm-callout-arrowhead)');
    }
    await act(async () => { await window.__tutorialSetFrame!(0); });
    expect(document.querySelector('[data-presentation-callout]')).toBeNull();
    expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].orthographicSpan).toBe(28);
  });

it.each(['galaxy-4k-v1', 'kiosk-7-v1'] as const)('reveals board region words without arrows, drops or extra margins in %s', async profile => {
  const data = recordingData({ output_profile: profile });
  const source = { source_pointer: '/regions/0', image_sha256: 'a'.repeat(64) };
  const positions: [number, number][] = [[2,2],[16,2],[2,16],[16,16],[9,2],[2,9],[16,9],[9,16],[9,9]];
  const callouts = positions.map((anchor, index) => ({ id: `callout:region-${index}`, anchor, side: 'board' as const,
    text: index < 4 ? '隅' : index < 8 ? '边' : '中央', ...source }));
  const frames: ReplayFrame[] = [0,4,8,9].map((count, step) => ({ step,
    payload: { size: 19, stones: { B: [], W: [] }, presentation_callouts: callouts.slice(0,count) },
    last: null, currentMove: null, appeared_stones: [] }));
  window.__TUTORIAL_MEDIA_DATA = { ...data, frames, board_payload: frames[0].payload,
    step_cues: { ...data.step_cues, frames, mode: 'presentation', presentation_plan: { callouts },
      cues: frames.map(frame => ({ step: frame.step, at_ms: frame.step * 500, source: frame.step ? 'speech_end' as const : 'initial' as const })) } };
  render(<TutorialMediaRecorder />);
  attachCanvas();
  await act(async () => resolveSprites(sprites));
  expect(document.querySelectorAll('[data-presentation-callout]')).toHaveLength(0);
  for (let step=1; step<=3; step++) {
    await act(async () => { await window.__tutorialSetFrame!(step * 500); });
    expect(document.querySelectorAll('[data-presentation-callout]')).toHaveLength([0,4,8,9][step]);
    expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].orthographicSpan).toBe(19.6);
    expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].recordingPlacement).toEqual([]);
    expect(document.querySelector('[data-presentation-callout] path')).toBeNull();
    expect(document.querySelector('#tm-callout-arrowhead')).toBeNull();
    expect(screen.queryByTestId('tutorial-last-move')).not.toBeInTheDocument();
  }
  const center = document.querySelector('[data-presentation-callout="callout:region-8"] text')!;
  expect(center).toHaveTextContent('中央');
  expect(center).toHaveAttribute('fill','#171717');
  expect(center).toHaveAttribute('text-anchor','middle');
  await act(async () => { await window.__tutorialSetFrame!(0); });
  expect(document.querySelectorAll('[data-presentation-callout]')).toHaveLength(0);
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0].orthographicSpan).toBe(19.6);
});
