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
    confirmExisting: vi.fn(),
    lock: vi.fn(),
    layout: vi.fn(),
  },
}));

const renderGuard = () => render(
  <ThemeProvider theme={kioskTheme}>
    <GeometryProvider>
      <PhysicalBoardGuard><div>实体棋盘内容</div></PhysicalBoardGuard>
    </GeometryProvider>
  </ThemeProvider>,
);

const renderGuardRequireRecognition = () => render(
  <ThemeProvider theme={kioskTheme}>
    <GeometryProvider>
      <PhysicalBoardGuard requireRecognition><div>实体棋盘内容</div></PhysicalBoardGuard>
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
    fireEvent.click(screen.getByRole('button', { name: '已清空，开始自动标定' }));
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

  it('allows the protected page after the operator confirms existing geometry', async () => {
    vi.mocked(GeometryAPI.status).mockResolvedValue({
      phase: 'required', session_calibrated: false, last_valid: true,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
    });
    vi.mocked(GeometryAPI.layout).mockResolvedValue({
      revision: 0,
      phase: 'required',
      stale: true,
      frame: { width: 1920, height: 1080 },
      out_size: 950,
      corners: [],
      points: [],
    });
    const readyStatus = {
      phase: 'ready', session_calibrated: true, last_valid: true,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true },
    } as const;
    vi.mocked(GeometryAPI.confirmExisting).mockImplementation(async () => {
      vi.mocked(GeometryAPI.status).mockResolvedValue(readyStatus);
      return readyStatus;
    });

    renderGuard();

    fireEvent.click(await screen.findByRole('button', { name: '网格无误，使用上次标定' }));
    expect(await screen.findByText('实体棋盘内容')).toBeInTheDocument();
  });

  // B2.5: screen-solve pass-through cases for the tsumego/problem route, which now mounts
  // <PhysicalBoardGuard> WITHOUT requireRecognition (physical mode owns recognition only when
  // its toggle is ON — see TsumegoProblemPage's PhysicalModeToggle).
  it('phase "disabled" short-circuits to ready even with requireRecognition (kiosk has no vision hardware)', async () => {
    vi.mocked(GeometryAPI.status).mockResolvedValue({
      phase: 'disabled', session_calibrated: false, last_valid: false,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false },
    });

    renderGuardRequireRecognition();

    expect(await screen.findByText('实体棋盘内容')).toBeInTheDocument();
  });

  it('a ready camera kiosk lacking recognition_ready still solves on screen once the route drops requireRecognition', async () => {
    vi.mocked(GeometryAPI.status).mockResolvedValue({
      phase: 'ready', session_calibrated: true, last_valid: true,
      capabilities: { camera_ready: true, led_ready: false, geometry_ready: true, recognition_ready: false },
    });

    renderGuard();

    expect(await screen.findByText('实体棋盘内容')).toBeInTheDocument();
  });
});
