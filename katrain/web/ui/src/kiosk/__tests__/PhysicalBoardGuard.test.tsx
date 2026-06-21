import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PhysicalBoardGuard from '../components/vision/PhysicalBoardGuard';
import { GeometryProvider } from '../context/GeometryContext';
import { GeometryAPI } from '../../api/geometryApi';

vi.mock('../../api/geometryApi', () => ({
  GeometryAPI: {
    status: vi.fn(),
    calibrate: vi.fn(),
    cancel: vi.fn(),
    lock: vi.fn(),
  },
}));

const renderGuard = () => render(
  <ThemeProvider theme={kioskTheme}>
    <GeometryProvider>
      <PhysicalBoardGuard><div>实体棋盘内容</div></PhysicalBoardGuard>
    </GeometryProvider>
  </ThemeProvider>,
);

describe('PhysicalBoardGuard', () => {
  it('blocks entry until the user confirms an empty board and starts calibration', async () => {
    vi.mocked(GeometryAPI.status).mockResolvedValue({
      phase: 'required', session_calibrated: false, last_valid: false,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
    });
    vi.mocked(GeometryAPI.calibrate).mockResolvedValue({
      phase: 'flashing_corners', session_calibrated: false, last_valid: false,
      progress: { current: 1, total: 13 },
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
    });

    renderGuard();

    expect(screen.queryByText('实体棋盘内容')).not.toBeInTheDocument();
    expect(await screen.findByText('请清空棋盘')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '开始自动标定' }));
    await waitFor(() => expect(GeometryAPI.calibrate).toHaveBeenCalledWith('auto'));
  });

  it('allows the protected page after session calibration', async () => {
    vi.mocked(GeometryAPI.status).mockResolvedValue({
      phase: 'ready', session_calibrated: true, last_valid: true,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true },
    });

    renderGuard();

    expect(await screen.findByText('实体棋盘内容')).toBeInTheDocument();
  });
});
