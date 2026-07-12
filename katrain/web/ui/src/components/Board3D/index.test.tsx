// index.test.tsx — the left/right (azimuth/yaw) slider only renders when enableAzimuth.
// The full R3F Canvas (WebGL) is not available under jsdom, so Canvas and every
// three.js-backed child are stubbed out; only the plain-HTML overlay is exercised.
import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

interface MockCanvasState {
  gl: { setSize: () => void; domElement: { clientWidth: number; clientHeight: number } };
  invalidate: () => void;
}

vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children, onCreated }: { children?: ReactNode; onCreated?: (state: MockCanvasState) => void }) => {
    onCreated?.({
      gl: { setSize: () => {}, domElement: { clientWidth: 100, clientHeight: 100 } },
      invalidate: () => {},
    });
    return <div data-testid="canvas">{children}</div>;
  },
  useFrame: () => {},
  useThree: () => ({ camera: {} }),
}));
vi.mock('./Lights', () => ({ default: () => null }));
vi.mock('./BoardMesh', () => ({ default: () => null }));
vi.mock('./CameraController', () => ({ default: () => null }));
vi.mock('./StoneGroup', () => ({ default: () => null }));
vi.mock('./RaycastClick', () => ({ default: () => null }));
vi.mock('./GhostStone', () => ({ default: () => null }));
vi.mock('./Overlays/Territory', () => ({ default: () => null }));
vi.mock('./Overlays/LastMove', () => ({ default: () => null }));
vi.mock('./Overlays/EvalDots', () => ({ default: () => null }));
vi.mock('./Overlays/BestMoves', () => ({ default: () => null }));
vi.mock('./Overlays/PolicyMap', () => ({ default: () => null }));
vi.mock('./Overlays/MoveNumbers', () => ({ default: () => null }));

import Board3D from './index';
import type { GameState } from '../../api';

const gameState = { board_size: [19, 19], board: {}, end_result: null } as unknown as GameState;

test('yaw slider absent by default (galaxy behavior)', () => {
  render(<Board3D gameState={gameState} onMove={() => {}} analysisToggles={{}} />);
  expect(screen.queryByLabelText('左右')).toBeNull();
});

test('yaw slider present when enableAzimuth is set (kiosk)', () => {
  render(<Board3D gameState={gameState} onMove={() => {}} analysisToggles={{}} enableAzimuth />);
  expect(screen.getByLabelText('左右')).toBeInTheDocument();
});
