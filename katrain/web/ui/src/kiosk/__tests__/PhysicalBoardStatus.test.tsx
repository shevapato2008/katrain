import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import type { GeometryStatus } from '../../api/geometryApi';
import { kioskTheme } from '../theme';
import PhysicalBoardStatus from '../components/settings/PhysicalBoardStatus';

let status: GeometryStatus;

vi.mock('../context/GeometryContext', () => ({
  useGeometry: () => ({ status }),
}));

const renderStatus = () => render(
  <ThemeProvider theme={kioskTheme}>
    <PhysicalBoardStatus />
  </ThemeProvider>,
);

describe('PhysicalBoardStatus', () => {
  it('renders the three rows and shows locked when calibrated', () => {
    status = {
      phase: 'ready',
      session_calibrated: true,
      last_valid: true,
      capabilities: { camera_ready: true, led_ready: false, geometry_ready: true },
    };

    renderStatus();

    expect(screen.getByText('摄像头')).toBeInTheDocument();
    expect(screen.getByText('LED')).toBeInTheDocument();
    expect(screen.getByText('几何标定')).toBeInTheDocument();
    expect(screen.getByText('几何已锁定')).toBeInTheDocument();
  });

  it('shows not-calibrated when session is not calibrated', () => {
    status = {
      phase: 'required',
      session_calibrated: false,
      last_valid: false,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
    };

    renderStatus();

    expect(screen.getByText('待校准')).toBeInTheDocument();
  });

  it('falls through to neutral gray dots with no throw when all capabilities are false', () => {
    status = {
      phase: 'required',
      session_calibrated: false,
      last_valid: false,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false },
    };

    expect(() => renderStatus()).not.toThrow();

    expect(screen.getByText('摄像头')).toBeInTheDocument();
    expect(screen.getByText('LED')).toBeInTheDocument();
    expect(screen.getByText('几何标定')).toBeInTheDocument();
    expect(screen.getByText('待校准')).toBeInTheDocument();
  });
});
