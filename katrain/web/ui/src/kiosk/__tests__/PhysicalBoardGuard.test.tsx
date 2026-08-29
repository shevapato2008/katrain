import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
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

/**
 * ⚠️ 2026-08-24 起要 `MemoryRouter`:守卫挡人时渲染的标定台**有返回键**了
 * (它用 `useNavigate`)。加它之前那一屏一个出口都没有 —— L2 无 Dock、顶栏不带返回,
 * 从做题/摆谱撞上「未标定」的人只能重启盒子。
 *
 * `sub` 是必填:说明**这一屏为什么需要摄像头**,做题和摆谱要说的不是同一句话。
 */
const wrap = (node: React.ReactNode) => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter>
      <GeometryProvider>{node}</GeometryProvider>
    </MemoryRouter>
  </ThemeProvider>,
);

const renderGuard = () => wrap(
  <PhysicalBoardGuard sub="实体做题要先让摄像头看清盘面"><div>实体棋盘内容</div></PhysicalBoardGuard>,
);

const renderGuardRequireRecognition = () => wrap(
  <PhysicalBoardGuard requireRecognition sub="实体做题要先让摄像头看清盘面"><div>实体棋盘内容</div></PhysicalBoardGuard>,
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
    // 口径换了、意图一字未改:「挡住了没有」原来看那句 `phaseHint`(已随四步清单一起撤掉),
    // 现在看四步清单的第 1 步 —— 它说的是同一件事,而且多说了前后文。
    expect(await screen.findByTestId('calib-screen')).toBeInTheDocument();
    expect(screen.getAllByTestId('calib-step')[0]).toHaveTextContent('准备空盘标定');
    fireEvent.click(screen.getByRole('button', { name: '重新开始标定' }));
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

    fireEvent.click(await screen.findByRole('button', { name: '沿用上次标定' }));
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
