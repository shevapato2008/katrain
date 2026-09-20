import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import TsumegoInputGuard from '../components/vision/TsumegoInputGuard';
import { GeometryProvider } from '../context/GeometryContext';
import { GeometryAPI } from '../../api/geometryApi';
import { PHYSICAL_MODE_KEY, readPhysicalMode, writePhysicalMode } from '../pages/tsumegoUnits';

/**
 * 做题路由外面那一层(T9)。前置状态一律造成「几何没就绪、本次开机没确认过」——
 * 那正是盒子重启后的样子,也正是裸 `PhysicalBoardGuard` 会挡人的那一态。
 * 第一条先钉住「开着实体开关时挡得住」:造不出这个前置,第二条会因为守卫本来就放行而假绿。
 */

vi.mock('../../api/geometryApi', () => ({
  GeometryAPI: {
    status: vi.fn(), calibrate: vi.fn(), cancel: vi.fn(),
    confirmExisting: vi.fn(), lock: vi.fn(), layout: vi.fn(),
  },
}));

const NOT_CALIBRATED = {
  phase: 'required' as const, session_calibrated: false, last_valid: true,
  capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
};

const renderGuard = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter>
      <GeometryProvider>
        <TsumegoInputGuard><div>做题内容</div></TsumegoInputGuard>
      </GeometryProvider>
    </MemoryRouter>
  </ThemeProvider>,
);

beforeEach(() => {
  localStorage.removeItem(PHYSICAL_MODE_KEY);
  vi.mocked(GeometryAPI.status).mockResolvedValue(NOT_CALIBRATED);
  // `last_valid: true` (持久化的锁还在) 让 `GeometryCalibrationScreen` 去取上一次的
  // layout 渲染俯视图(照抄 `PhysicalBoardGuard.test.tsx` 同一态的写法)—— 不 mock
  // 这一个会在 GeometryAPI.layout() 上炸,和这条用例本身要钉住的行为无关。
  vi.mocked(GeometryAPI.layout).mockResolvedValue({
    revision: 0, phase: 'required', stale: true,
    frame: { width: 1920, height: 1080 }, out_size: 950, corners: [], points: [],
  });
});

describe('TsumegoInputGuard', () => {
  it('打开过实体开关的人:没确认标定就先去标定台', async () => {
    writePhysicalMode(true);
    renderGuard();
    expect(await screen.findByTestId('calib-screen')).toBeInTheDocument();
    expect(screen.queryByText('做题内容')).not.toBeInTheDocument();
  });

  it('默认(实体开关关着)在屏幕上做题:不被标定挡住', async () => {
    expect(readPhysicalMode()).toBe(false);
    renderGuard();
    expect(await screen.findByText('做题内容')).toBeInTheDocument();
    expect(screen.queryByTestId('calib-screen')).not.toBeInTheDocument();
  });
});
