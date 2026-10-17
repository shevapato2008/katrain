import { act, render, screen } from '@testing-library/react';
import type { RootState } from '@react-three/fiber';
import { OrthographicCamera, Scene, Texture, Vector3 } from 'three';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Board3D from '../components/Board3D';
import { loadRecordingStoneSprites } from '../components/Board3D/tutorialStoneTextures';
import TutorialMediaRecorder from './TutorialMediaRecorder';

// WebGL is exercised by test_tutorial_media_render.py; jsdom checks the recorder boundary.
vi.mock('../components/Board3D', () => ({ default: vi.fn(() => null) }));
vi.mock('../components/Board3D/tutorialStoneTextures', () => ({ loadRecordingStoneSprites: vi.fn() }));

const sprites = { B: new Texture(), W: Array.from({ length: 32 }, () => new Texture()) };
let resolveSprites: (value: typeof sprites) => void;
beforeEach(() => {
  vi.mocked(loadRecordingStoneSprites).mockImplementation(() => new Promise(resolve => { resolveSprites = resolve; }));
});

afterEach(() => { delete window.__TUTORIAL_MEDIA_DATA; vi.clearAllMocks(); });

it('waits for approved stone textures before capturing the saved board and pending label', async () => {
  window.__TUTORIAL_MEDIA_DATA = {
    narration: '静态局面。',
    render_mode: '2d',
    visual_seed: '1031',
    board_payload: { size: 19, stones: { B: [[14, 2]], W: [[15, 14]] },
      unknown_stones: [{ point: [12, 8], color: null }],
      source_region: { col: 7, row: 0, cols: 12, rows: 19, confirmed: true } },
    // A legal prefix must never replace the saved diagram in pending mode.
    frames: [{ step: 0, payload: { size: 19, stones: { B: [], W: [] } }, last: null }],
    speech_timing: { schema_version: 1, audio_sha256: 'audio', duration_ms: 2000,
      boundaries: [{ text: '静态局面。', start_ms: 100, duration_ms: 1000 }] },
    step_cues: { schema_version: 1, audio_sha256: 'audio', status: 'pending', reason: 'Replay requires calibration', cues: [] },
  };
  render(<TutorialMediaRecorder />);
  expect(screen.getByTestId('tutorial-static-reason')).toHaveTextContent('静态讲解·手顺待校准');
  const board = vi.mocked(Board3D).mock.calls.at(-1)?.[0];
  expect(board).toMatchObject({
    cameraPosition: [0, 26, 0], cameraTarget: [0, 1.2, 0], cameraUp: [0, 0, -1],
    orthographicSpan: 19.6, recordingAppearance: 'overhead',
    readOnly: true, disableControls: true, frameloop: 'demand',
    gameState: { stones: [['B', [14, 16], null, null], ['W', [15, 4], null, null]], last_move: null },
  });
  expect(window.__TUTORIAL_MEDIA_READY).not.toBe(true);
  const camera = new OrthographicCamera(-10, 10, 10, -10, .1, 100);
  camera.position.set(0, 26, 0);
  camera.up.set(0, 0, -1);
  camera.lookAt(0, 1.2, 0);
  camera.updateMatrixWorld();
  act(() => board?.onCanvasReady?.({
    camera, scene: new Scene(),
    gl: { domElement: { clientWidth: 800, clientHeight: 800 }, render: vi.fn() },
  } as unknown as RootState));
  expect(window.__TUTORIAL_MEDIA_READY).not.toBe(true);
  await act(async () => resolveSprites(sprites));
  expect(window.__TUTORIAL_MEDIA_READY).toBe(true);
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0]).toMatchObject({
    recordingStoneSprites: sprites, recordingVisualSeed: '1031',
  });
  expect(screen.queryByTestId('tutorial-known-region')).not.toBeInTheDocument();
  expect(screen.getByTestId('tutorial-unknown-stone')).toHaveTextContent('?');
});

it('uses the solid wood camera and contrast marker for 3d recordings', () => {
  window.__TUTORIAL_MEDIA_DATA = {
    narration: '黑1。', render_mode: '3d',
    board_payload: { size: 9, stones: { B: [[2, 0]], W: [] } },
    frames: [{ step: 1, payload: { size: 9, stones: { B: [[2, 0]], W: [] } }, last: [2, 0] }],
    speech_timing: { schema_version: 1, audio_sha256: 'audio', duration_ms: 2000,
      boundaries: [{ text: '黑1', start_ms: 100, duration_ms: 1000 }] },
    step_cues: { schema_version: 1, audio_sha256: 'audio', status: 'complete', cues: [{ step: 1, at_ms: 0 }] },
  };
  render(<TutorialMediaRecorder />);
  const board = vi.mocked(Board3D).mock.calls.at(-1)?.[0];
  expect(board).toMatchObject({
    cameraTarget: [0, 1.2, 0], cameraUp: undefined, orthographicSpan: 11.6, recordingAppearance: 'solid-wood',
    recordingStoneSprites: undefined, recordingVisualSeed: undefined,
    gameState: { stones: [['B', [2, 8], null, null]], last_move: null },
  });
  expect(board?.cameraPosition?.[2]).toBeGreaterThan(0);
  expect(screen.queryByTestId('tutorial-static-reason')).not.toBeInTheDocument();
});

it('keeps the solid wood camera centered and the 2d recording unchanged', () => {
  window.__TUTORIAL_MEDIA_DATA = {
    narration: '黑1。', render_mode: '3d',
    board_payload: { size: 19, stones: { B: [[2, 0]], W: [] } },
    frames: [{ step: 1, payload: { size: 19, stones: { B: [[2, 0]], W: [] },
      labels: { '2,0': '1' }, letters: { '4,2': 'A' }, shapes: { '6,2': 'triangle' },
      unknown_stones: [{ point: [8, 2], color: null }] }, last: [2, 0] }],
    speech_timing: { schema_version: 1, audio_sha256: 'audio', duration_ms: 2000,
      boundaries: [{ text: '黑1', start_ms: 100, duration_ms: 1000 }] },
    step_cues: { schema_version: 1, audio_sha256: 'audio', status: 'complete', cues: [{ step: 1, at_ms: 0 }] },
  };
  const { rerender } = render(<TutorialMediaRecorder />);
  const board = vi.mocked(Board3D).mock.calls.at(-1)?.[0];
  expect(board).toMatchObject({ recordingAppearance: 'solid-wood', orthographicSpan: 21.6, gameState: { last_move: null } });
  expect(board?.cameraPosition?.[0]).toBe(0);
  const camera = new OrthographicCamera(-342, 342, 342, -342, .1, 100);
  camera.position.set(...board!.cameraPosition!);
  camera.zoom = 684 / board!.orthographicSpan!;
  camera.lookAt(0, 1.2, 0);
  camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  act(() => board?.onCanvasReady?.({ camera, scene: new Scene(),
    gl: { domElement: { clientWidth: 684, clientHeight: 684 }, render: vi.fn() },
  } as unknown as RootState));
  const number = document.querySelector('[data-annotation-point="2,0"]')!;
  const matrix = number.getAttribute('transform')!.slice(7, -1).split(' ').map(Number);
  expect(matrix[0] * matrix[3] - matrix[1] * matrix[2]).toBeCloseTo(Math.cos(35 * Math.PI / 180));
  const top = new Vector3(-7, 1.64, -9).project(camera);
  expect(matrix[5]).toBeCloseTo((1 - top.y) * 342);
  expect(document.querySelector('[data-annotation-point="4,2"]')?.getAttribute('transform')).toMatch(/^matrix\(/);
  expect(document.querySelector('[data-annotation-point="6,2"]')?.getAttribute('transform')).toMatch(/^matrix\(/);
  expect(screen.getByTestId('tutorial-unknown-stone')).toHaveTextContent('?');
  expect(screen.getByTestId('tutorial-last-move').parentElement?.getAttribute('transform')).toBe(number.getAttribute('transform'));
  window.__TUTORIAL_MEDIA_DATA.render_mode = '2d';
  rerender(<TutorialMediaRecorder />);
  expect(vi.mocked(Board3D).mock.calls.at(-1)?.[0]).toMatchObject({
    recordingAppearance: 'overhead', cameraPosition: [0, 26, 0], orthographicSpan: 19.6,
    recordingVisualSeed: 'tutorial',
  });
  expect(document.querySelector('[data-annotation-point="2,0"]')).not.toHaveAttribute('transform');
});
