import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import type { GeometryStatus } from '../../api/geometryApi';
import { GeometryAPI } from '../../api/geometryApi';
import { kioskTheme } from '../theme';
import GeometryCalibrationWorkspace from '../components/vision/GeometryCalibrationWorkspace';

const startCalibration = vi.fn();
const cancelCalibration = vi.fn();
const confirmExisting = vi.fn();
let status: GeometryStatus;

vi.mock('../context/GeometryContext', () => ({
  useGeometry: () => ({ status, startCalibration, cancelCalibration, confirmExisting, refresh: vi.fn() }),
}));

vi.mock('../../api/geometryApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/geometryApi')>();
  return { ...actual, GeometryAPI: { ...actual.GeometryAPI, layout: vi.fn() } };
});

const renderWorkspace = () => render(
  <ThemeProvider theme={kioskTheme}>
    <GeometryCalibrationWorkspace mode="settings" />
  </ThemeProvider>,
);

describe('GeometryCalibrationWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    status = {
      phase: 'required',
      session_calibrated: false,
      last_valid: false,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
    };
    vi.mocked(GeometryAPI.layout).mockRejectedValue(new Error('geometry request failed 409'));
  });

  it('shows both camera views and starts only after empty-board confirmation', async () => {
    renderWorkspace();

    expect(screen.getByText('摄像头原始画面')).toBeInTheDocument();
    expect(screen.getByText('俯视矫正画面')).toBeInTheDocument();
    expect(screen.getByAltText('摄像头原始画面')).toHaveAttribute('src', '/api/v1/geometry/stream');
    expect(screen.getByTestId('geometry-led-advisory')).toHaveTextContent('不会自动点亮 LED');
    expect(startCalibration).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '已清空，开始自动标定' }));

    await waitFor(() => expect(startCalibration).toHaveBeenCalledWith('auto'));
  });

  it('shows active anchor progress and supports explicit cancellation', () => {
    status = {
      ...status,
      phase: 'flashing_corners',
      progress: { current: 4, total: 13 },
      detected_anchors: [{ row: 0, col: 0, x: 100, y: 200, color: 'green' }],
    };

    renderWorkspace();

    expect(screen.getByText('4/13')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '取消标定' }));
    expect(cancelCalibration).toHaveBeenCalledTimes(1);
  });

  it('renders displacement as a blocking stale-geometry warning', () => {
    status = {
      ...status,
      phase: 'degraded',
      last_valid: true,
      error: 'board_moved',
    };

    renderWorkspace();

    expect(screen.getByText('摄像头或棋盘位置已变化')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '已清空，重新标定' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: '网格无误，使用上次标定' })).not.toBeInTheDocument();
  });

  it('offers existing geometry reuse after restart without requiring an empty board', async () => {
    status = {
      ...status,
      last_valid: true,
      capabilities: { camera_ready: true, led_ready: false, geometry_ready: false },
    };

    renderWorkspace();

    expect(screen.getByText('无需清空棋盘')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '网格无误，使用上次标定' }));
    await waitFor(() => expect(confirmExisting).toHaveBeenCalledTimes(1));
  });

  it('renders user-readable diagnostic card for failed anchor calibration and allows valid-grid reuse', async () => {
    status = {
      ...status,
      phase: 'failed',
      last_valid: true,
      error: 'anchor_not_found:15,15',
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
    };

    renderWorkspace();

    expect(screen.getByTestId('geometry-diagnostic-card')).toBeInTheDocument();
    expect(screen.getByText('无法定位 Q4 的定位灯')).toBeInTheDocument();
    expect(screen.getByText(/通常是棋子遮挡/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '网格无误，使用上次标定' }));
    await waitFor(() => expect(confirmExisting).toHaveBeenCalledTimes(1));
  });

  it('disables calibration when camera or LED is unavailable', () => {
    status = {
      ...status,
      capabilities: { camera_ready: false, led_ready: true, geometry_ready: false },
    };

    renderWorkspace();

    expect(screen.getByRole('button', { name: '已清空，开始自动标定' })).toBeDisabled();
    expect(screen.getByText('摄像头未连接')).toBeInTheDocument();
  });

  it('requires a second empty-board confirmation before manual recalibration', async () => {
    status = {
      ...status,
      phase: 'ready',
      session_calibrated: true,
      last_valid: true,
      metrics: { inlier_count: 13, rms_residual: 1.385, max_residual: 2.333 },
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true },
    };

    renderWorkspace();

    expect(screen.getByText(/13\/13/)).toBeInTheDocument();
    expect(screen.getByText(/RMS 1.385 px/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));

    expect(startCalibration).not.toHaveBeenCalled();
    expect(screen.getByText('请先清空实体棋盘，再启动 LED 自动标定。')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '已清空，开始自动标定' }));
    await waitFor(() => expect(startCalibration).toHaveBeenCalledWith('manual'));
    await waitFor(() => expect(screen.getByRole('button', { name: '重新标定' })).toBeEnabled());
  });
});
