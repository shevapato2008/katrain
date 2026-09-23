import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GolaxyScanPanel } from './GolaxyScanPanel';

/**
 * 星阵扫码登录面板的行为测试。版式归四图,这里只测状态机与「取不到 scan_id
 * 不许摆假码」那条硬要求(计划 Review Focus #2)。
 *
 * 用假计时器 + `advanceTimersByTimeAsync`(判例见 `EngineReadinessContext.test.tsx`):
 * `screen.findBy*` 内部用真 `setTimeout` 轮询,和假计时器混用会挂起,所以这里全程
 * 用 `flush()`/`advanceTimersByTimeAsync` 手动推进,断言用同步的 `getBy*`/`queryBy*`。
 */

const { platformScanStart, platformScanState, platformScanConfirm } = vi.hoisted(() => ({
  platformScanStart: vi.fn(),
  platformScanState: vi.fn(),
  platformScanConfirm: vi.fn(),
}));
vi.mock('../../../api', () => ({
  API: { platformScanStart, platformScanState, platformScanConfirm },
}));
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok', isAuthenticated: true }),
}));

const flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

describe('GolaxyScanPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    platformScanStart.mockReset();
    platformScanState.mockReset();
    platformScanConfirm.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('取不到 scan_id 时不画二维码,画虚线框 + 重试;轮询不启动', async () => {
    platformScanStart.mockRejectedValue(new Error('连不上'));
    render(<GolaxyScanPanel platform="golaxy" onDone={() => {}} />);
    await flush();

    expect(screen.getByTestId('scan-unavailable')).toBeInTheDocument();
    expect(screen.queryByTestId('scan-qr')).toBeNull();

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(platformScanState).not.toHaveBeenCalled();
  });

  it('拿到 scan_id 就画码、开始每秒轮询,状态跟着 waiting→scanned→confirmed 走,confirmed 后调 confirm 并 onDone', async () => {
    platformScanStart.mockResolvedValue({ scan_id: 'sid-1', payload: 'golaxy_url&&&uuid-x', expires_at: 0 });
    platformScanState
      .mockResolvedValueOnce({ state: 'waiting' })
      .mockResolvedValueOnce({ state: 'scanned' })
      .mockResolvedValueOnce({ state: 'confirmed' });
    platformScanConfirm.mockResolvedValue({ connected: true, display_name: '棋手甲' });
    const onDone = vi.fn();

    render(<GolaxyScanPanel platform="golaxy" onDone={onDone} />);
    await flush();

    expect(screen.getByTestId('scan-qr')).toBeInTheDocument();
    expect(screen.queryByTestId('scan-unavailable')).toBeNull();
    expect(screen.getByTestId('scan-status')).toHaveTextContent('等待扫描');

    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByTestId('scan-status')).toHaveTextContent('等待扫描');

    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByTestId('scan-status')).toHaveTextContent('已扫描，请在手机上确认');

    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(platformScanConfirm).toHaveBeenCalledWith('golaxy', 'sid-1', 'tok');
    expect(onDone).toHaveBeenCalled();

    // 终态之后不再打 scan/state(后端短路,前端也不该再白打)。
    const callsAtConfirm = platformScanState.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(platformScanState.mock.calls.length).toBe(callsAtConfirm);
  });

  it.each([
    ['expired', '二维码已失效'],
    ['cancelled', '手机上取消了登录'],
  ])('%s:码变成按钮,压暗+中间刷新图标,点码就重新取一张', async (state, statusText) => {
    // 这两态在真实运行里要等到星阵那边把码作废才出现(实测约 182 秒),
    // 不显式造状态就没有任何东西证明这条交互是对的。
    platformScanStart
      .mockResolvedValueOnce({ scan_id: 'sid-a', payload: 'golaxy_url&&&uuid-a', expires_at: 0 })
      .mockResolvedValueOnce({ scan_id: 'sid-b', payload: 'golaxy_url&&&uuid-b', expires_at: 0 });
    platformScanState.mockResolvedValue({ state });

    render(<GolaxyScanPanel platform="golaxy" onDone={() => {}} />);
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });

    const qrButton = screen.getByTestId('scan-qr-refresh');
    expect(qrButton.tagName).toBe('BUTTON');
    // 可及名把**当前状态**念进去 —— 取消那一支的原因和失效不一样,
    // 读屏的人听到的必须和屏上那行字是同一件事。
    expect(qrButton).toHaveAccessibleName(`${statusText}，点此换一张`);
    // 码还画着(压暗是 CSS 的事,不是把它删掉)—— 删掉的话屏上剩一个空白方块。
    expect(screen.getByTestId('scan-qr')).toBeInTheDocument();

    expect(platformScanStart).toHaveBeenCalledTimes(1);
    await act(async () => { qrButton.click(); });
    await flush();
    expect(platformScanStart).toHaveBeenCalledTimes(2);
  });

  it('还没作废时二维码不是按钮 —— 点它不该有任何反应', async () => {
    // 「点码即换」只在码已经没用的时候出现。等待扫描时把它也做成按钮,
    // 手指扶一下屏幕就把正在等确认的码换掉了。
    platformScanStart.mockResolvedValue({ scan_id: 'sid-c', payload: 'golaxy_url&&&uuid-c', expires_at: 0 });
    platformScanState.mockResolvedValue({ state: 'waiting' });

    render(<GolaxyScanPanel platform="golaxy" onDone={() => {}} />);
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });

    expect(screen.getByTestId('scan-qr')).toBeInTheDocument();
    expect(screen.queryByTestId('scan-qr-refresh')).toBeNull();
  });

  it('expired:停轮询,画「换一张」,不进 confirm', async () => {
    platformScanStart.mockResolvedValue({ scan_id: 'sid-2', payload: 'golaxy_url&&&uuid-y', expires_at: 0 });
    platformScanState.mockResolvedValue({ state: 'expired' });

    render(<GolaxyScanPanel platform="golaxy" onDone={() => {}} />);
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });

    expect(screen.getByTestId('scan-status')).toHaveTextContent('二维码已失效');
    expect(platformScanConfirm).not.toHaveBeenCalled();
    expect(screen.getByTestId('scan-refresh')).toBeInTheDocument();

    const callsAtExpiry = platformScanState.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(platformScanState.mock.calls.length).toBe(callsAtExpiry);
  });

  it('unknown 不是终态,继续轮询', async () => {
    platformScanStart.mockResolvedValue({ scan_id: 'sid-3', payload: 'golaxy_url&&&uuid-z', expires_at: 0 });
    platformScanState.mockResolvedValue({ state: 'unknown' });

    render(<GolaxyScanPanel platform="golaxy" onDone={() => {}} />);
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    const callsAfterOne = platformScanState.mock.calls.length;
    expect(callsAfterOne).toBeGreaterThan(0);

    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(platformScanState.mock.calls.length).toBeGreaterThan(callsAfterOne);
  });

  it('组件卸载后不再轮询', async () => {
    platformScanStart.mockResolvedValue({ scan_id: 'sid-4', payload: 'golaxy_url&&&uuid-w', expires_at: 0 });
    platformScanState.mockResolvedValue({ state: 'waiting' });

    const { unmount } = render(<GolaxyScanPanel platform="golaxy" onDone={() => {}} />);
    await flush();
    unmount();

    const callsAtUnmount = platformScanState.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(platformScanState.mock.calls.length).toBe(callsAtUnmount);
  });
});
