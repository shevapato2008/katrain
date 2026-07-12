// CameraController.test.tsx — assert azimuth props reach OrbitControls
import { render } from '@testing-library/react';
import { vi } from 'vitest';
const orbitProps: any = {};
vi.mock('@react-three/drei', () => ({
  OrbitControls: (p: any) => { Object.assign(orbitProps, p); return null; },
}));
vi.mock('three', () => ({ MOUSE: { ROTATE: 0, DOLLY: 1 } }));
import CameraController from './CameraController';

test('azimuth locked by default (0..0)', () => {
  render(<CameraController />);
  expect(orbitProps.minAzimuthAngle).toBe(0);
  expect(orbitProps.maxAzimuthAngle).toBe(0);
});

test('azimuth range passes through when provided', () => {
  render(<CameraController minAzimuthAngle={-1} maxAzimuthAngle={1} />);
  expect(orbitProps.minAzimuthAngle).toBe(-1);
  expect(orbitProps.maxAzimuthAngle).toBe(1);
});
