import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BaipuSessionRoute from '../pages/BaipuSessionRoute';
import { GeometryProvider } from '../context/GeometryContext';
import { GeometryAPI, type GeometryPhase, type GeometryStatus } from '../../api/geometryApi';

const { modeMock, sessionRendered } = vi.hoisted(() => ({ modeMock: vi.fn(), sessionRendered: vi.fn() }));
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, mode: modeMock } };
});
// 摆谱屏一挂就点灯(`BaipuSessionPage` 效应里的 `LedAPI.point`),所以「它渲染过没有」= 「摆谱碰没碰过灯」。
vi.mock('../pages/BaipuSessionPage', () => ({
  default: ({ collect }: { collect: boolean }) => {
    sessionRendered(collect);
    return <div data-testid="session" data-collect={String(collect)} />;
  },
}));
vi.mock('../components/vision/PhysicalBoardGuard', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="guard">{children}</div>,
}));
// 棋盘状态走**真的** `GeometryProvider`(初值 phase=required、loaded=false —— 和盒上刷新那一刻一样),
// 只桩它背后的接口。直接给 `useGeometry` 一个值的话,「还没读到」这一态根本造不出来。
vi.mock('../../api/geometryApi', () => ({
  GeometryAPI: {
    status: vi.fn(), calibrate: vi.fn(), cancel: vi.fn(), confirmExisting: vi.fn(), lock: vi.fn(), layout: vi.fn(),
  },
}));
vi.mock('../components/vision/GeometryCalibrationScreen', () => ({
  default: ({ title }: { title: string }) => <div data-testid="calib-running">{title}</div>,
}));

const geo = (phase: GeometryPhase): GeometryStatus => ({
  phase, session_calibrated: false, last_valid: false,
  capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
});
const deferred = <T,>() => {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
};

const renderRoute = () => render(
  <MemoryRouter><GeometryProvider><BaipuSessionRoute /></GeometryProvider></MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(GeometryAPI.status).mockReset();
  vi.mocked(GeometryAPI.status).mockResolvedValue(geo('required'));   // 服务重启后没标定:上线态照样直接进
});

describe('摆谱入口:拍不拍照决定要不要先标定(K4)', () => {
  it('上线态不套标定守卫(即使 geometry 是 required)—— 只用灯,灯的行列换算不需要摄像头', async () => {
    modeMock.mockResolvedValue({ collect: false });
    renderRoute();
    expect(await screen.findByTestId('session')).toHaveAttribute('data-collect', 'false');
    expect(screen.queryByTestId('guard')).toBeNull();
    expect(screen.queryByTestId('calib-running')).toBeNull();
  });

  // 设置里开始标定 → 按返回(返回不取消,服务端标定线程接着跑)→ 进摆谱。摆谱屏一挂就点灯,
  // 而标定每个锚点都是 clear → 拍熄灯帧 → 点亮 → 拍亮灯帧;`/led/point` 先 CLEAR 再点、没有忙检查
  // ⇒ 两边互相冲掉对方的灯:摆谱指错、标定失败。采集态没这个问题 —— 守卫在标定进行中本来就不放行。
  it('上线态但标定线程还在跑:先不挂摆谱屏,给标定进度;标定结束(这里是取消)才进摆谱', async () => {
    modeMock.mockResolvedValue({ collect: false });
    const next = deferred<GeometryStatus>();
    // 第一次问到「在跑」;之后 Provider 每 300ms 再问,那一次先挂着,由用例决定何时回「已取消」。
    vi.mocked(GeometryAPI.status).mockResolvedValueOnce(geo('flashing_corners')).mockReturnValue(next.promise);
    renderRoute();
    expect(await screen.findByTestId('calib-running')).toHaveTextContent('棋盘标定还在进行');
    expect(sessionRendered).not.toHaveBeenCalled();
    await act(async () => { next.resolve(geo('cancelled')); });
    expect(await screen.findByTestId('session')).toHaveAttribute('data-collect', 'false');
    expect(screen.queryByTestId('calib-running')).toBeNull();
  });

  // 刷新直接进这条 URL(或服务刚起)时 Provider 还没读到状态:phase 是**初值** required、loaded=false。
  // /mode 先回 false 的话,只看 phase 就会先挂摆谱屏点灯,等迟到的 flashing_corners 再卸掉 —— 灯已经被冲过一次。
  it('上线态 /mode 先回、棋盘状态迟到而标定在跑:摆谱屏一次都不许挂', async () => {
    modeMock.mockResolvedValue({ collect: false });
    const first = deferred<GeometryStatus>();
    vi.mocked(GeometryAPI.status).mockReturnValue(first.promise);
    renderRoute();
    await waitFor(() => expect(screen.getByTestId('baipu-loading')).toHaveTextContent('正在检查棋盘状态'));
    expect(screen.getByTestId('baipu-pagebar')).toBeInTheDocument();   // 读不到时也有出口
    await act(async () => { first.resolve(geo('flashing_corners')); });
    expect(await screen.findByTestId('calib-running')).toBeInTheDocument();
    expect(sessionRendered).not.toHaveBeenCalled();
  });

  it('采集态照旧先过标定守卫 —— 拍照要几何锁', async () => {
    modeMock.mockResolvedValue({ collect: true });
    renderRoute();
    expect(await screen.findByTestId('session')).toHaveAttribute('data-collect', 'true');
    expect(screen.getByTestId('guard')).toBeInTheDocument();
  });

  // 只守「问的那几百毫秒里有出口」。问不回来会不会一直停在这儿,由 baipuApi.test.ts 的两条超时用例守
  // (`mode()` 到点必回 `{collect:false}`),不靠这一条。
  it('还没问到时屏上有页控条 —— 不许再造一块没有出口的屏', () => {
    modeMock.mockReturnValue(new Promise(() => {}));
    renderRoute();
    expect(screen.getByTestId('baipu-pagebar')).toBeInTheDocument();
  });
});
