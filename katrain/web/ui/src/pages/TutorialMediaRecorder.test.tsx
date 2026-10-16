import { render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import TutorialMediaRecorder from './TutorialMediaRecorder';

afterEach(() => { delete window.__TUTORIAL_MEDIA_DATA; });

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
  const { container } = render(<TutorialMediaRecorder />);
  expect(screen.getByTestId('tutorial-static-reason')).toHaveTextContent('静态讲解·手顺待校准');
  expect(container.querySelectorAll('[data-stone-color="B"]')).toHaveLength(1);
  expect(container.querySelectorAll('[data-stone-color="W"]')).toHaveLength(1);
  expect(screen.getByTestId('tutorial-known-region')).toHaveAttribute('data-known-region', '7,0,12,19');
  expect(screen.getByTestId('tutorial-unknown-stone')).toHaveTextContent('?');
});
