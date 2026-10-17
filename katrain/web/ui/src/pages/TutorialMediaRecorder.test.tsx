import { act, render, screen } from '@testing-library/react';
import type { RootState } from '@react-three/fiber';
import { OrthographicCamera, Scene } from 'three';
import { afterEach, expect, it, vi } from 'vitest';
import Board3D from '../components/Board3D';
import TutorialMediaRecorder from './TutorialMediaRecorder';

// WebGL is exercised by test_tutorial_media_render.py; jsdom checks the recorder boundary.
vi.mock('../components/Board3D', () => ({ default: vi.fn(() => null) }));

afterEach(() => { delete window.__TUTORIAL_MEDIA_DATA; vi.clearAllMocks(); });

it('renders the saved final board and permanent pending label with unknown extent and occupied points', () => {
  window.__TUTORIAL_MEDIA_DATA = {
    narration: '静态局面。',
    render_mode: '2d',
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
  expect(window.__TUTORIAL_MEDIA_READY).toBe(true);
  expect(screen.getByTestId('tutorial-known-region')).toHaveAttribute('data-known-region', '7,0,12,19');
  expect(screen.getByTestId('tutorial-known-region')).toHaveAttribute('fill', 'none');
  expect(screen.getByTestId('tutorial-known-region')).toHaveAttribute('stroke-dasharray', '4 3');
  expect(screen.getByTestId('tutorial-unknown-stone')).toHaveTextContent('?');
});

it('keeps the perspective camera and native last-move marker for 3d recordings', () => {
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
    cameraTarget: [0, 1.2, 0], cameraUp: undefined, orthographicSpan: undefined, recordingAppearance: undefined,
    gameState: { stones: [['B', [2, 8], null, null]], last_move: [2, 8] },
  });
  expect(board?.cameraPosition?.[2]).toBeGreaterThan(0);
  expect(screen.queryByTestId('tutorial-static-reason')).not.toBeInTheDocument();
});
