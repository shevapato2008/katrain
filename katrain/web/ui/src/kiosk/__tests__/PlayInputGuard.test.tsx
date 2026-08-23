import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlayInputGuard from '../components/vision/PlayInputGuard';
import { GeometryProvider } from '../context/GeometryContext';
import { GeometryAPI } from '../../api/geometryApi';
import { PLAY_ON_BOARD_KEY, readPlayOnBoard, writePlayOnBoard } from '../utils/playInput';

/**
 * 对局那四条路由外面那一层。
 *
 * **这条闸守的是那颗开关的后半截。** 开局设置屏上选了「屏幕」,进对局还是被推去
 * 标定工作台的话,那颗开关就只做了半截 —— 屏上答应的事和实际发生的事不一样。
 *
 * 前置状态一律造成「几何没就绪」:那正是裸 `PhysicalBoardGuard` 会挡人的那一态。
 * 造不出这个前置,下面两条就都是空的(「屏幕」那条会因为守卫本来就放行而假绿),
 * 所以第一条先把**挡得住**这件事本身钉住。
 */

vi.mock('../../api/geometryApi', () => ({
  GeometryAPI: {
    status: vi.fn(), calibrate: vi.fn(), cancel: vi.fn(),
    confirmExisting: vi.fn(), lock: vi.fn(), layout: vi.fn(),
  },
}));

const NOT_CALIBRATED = {
  phase: 'required' as const, session_calibrated: false, last_valid: false,
  capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
};

const renderGuard = () => render(
  <ThemeProvider theme={kioskTheme}>
    <GeometryProvider>
      <PlayInputGuard><div>对局内容</div></PlayInputGuard>
    </GeometryProvider>
  </ThemeProvider>,
);

beforeEach(() => {
  localStorage.removeItem(PLAY_ON_BOARD_KEY);
  vi.mocked(GeometryAPI.status).mockResolvedValue(NOT_CALIBRATED);
});

describe('PlayInputGuard', () => {
  // 默认(没动过偏好)= 走实体盘 = 和这次改动之前**一模一样**:没标定就挡。
  it('默认仍然挡:没标定过的盒子进不了对局,先去标定', async () => {
    expect(readPlayOnBoard()).toBe(true);
    renderGuard();
    expect(await screen.findByText('请清空棋盘')).toBeInTheDocument();
    expect(screen.queryByText('对局内容')).not.toBeInTheDocument();
  });

  // 选了屏幕就不该被标定挡住 —— 这一局根本不用摄像头。
  it('选了「屏幕」就直接进对局,不再被标定挡住', async () => {
    writePlayOnBoard(false);
    renderGuard();
    expect(await screen.findByText('对局内容')).toBeInTheDocument();
    expect(screen.queryByText('请清空棋盘')).not.toBeInTheDocument();
  });
});
