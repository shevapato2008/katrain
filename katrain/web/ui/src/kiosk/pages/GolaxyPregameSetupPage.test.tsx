import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import GolaxyPregameSetupPage from './GolaxyPregameSetupPage';

const vision = vi.hoisted(() => ({ enabled: true }));
vi.mock('../context/VisionContext', () => ({ useVision: () => ({ isVisionEnabled: vision.enabled }) }));
const renderPage = (mode = 'quick') => render(<MemoryRouter initialEntries={[`/kiosk/play/cross-platform/golaxy/setup/${mode}`]}><Routes>
  <Route path="/kiosk/play/cross-platform/golaxy/setup/:mode" element={<GolaxyPregameSetupPage />} />
  <Route path="/kiosk/play/cross-platform/golaxy" element={<div>星阵首页</div>} />
</Routes></MemoryRouter>);

beforeEach(() => { localStorage.clear(); vision.enabled = true; });
describe('Golaxy pregame setup', () => {
  it.each(['quick', 'room'])('opens %s directly with a fixed 19 line preview and unavailable submit', (mode) => {
    renderPage(mode);
    expect(screen.getByTestId('golaxy-pregame-page')).toHaveAttribute('data-mode', mode);
    expect(screen.getByTestId('kiosk-setup-board')).toBeInTheDocument();
    expect(screen.getByText('19 路 · 空盘预览')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /暂不可用/ })).toBeDisabled();
    expect(screen.getByText('星阵开局功能暂不可用，请稍后再试。')).toBeInTheDocument();
  });
  it('persists screen and physical input choices', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: '屏幕' }));
    expect(localStorage.getItem('kiosk_play_on_board')).toBe('false');
    await userEvent.click(screen.getByRole('button', { name: '实体盘' }));
    expect(localStorage.getItem('kiosk_play_on_board')).toBe('true');
  });
  it('disables physical input without camera calibration', async () => {
    vision.enabled = false;
    renderPage();
    expect(screen.getByRole('button', { name: '屏幕' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '实体盘' })).toBeDisabled();
  });
  it('offers three independent time choices while keeping at least one selected', async () => {
    renderPage();
    const fast = screen.getByRole('button', { name: /快棋.*1 分.*15 秒/ });
    const normal = screen.getByRole('button', { name: /普通.*10 分.*30 秒/ });
    const slow = screen.getByRole('button', { name: /慢棋.*30 分.*40 秒/ });
    for (const choice of [fast, normal, slow]) expect(choice).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(fast);
    await userEvent.click(normal);
    expect(fast).toHaveAttribute('aria-pressed', 'false');
    expect(normal).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(slow);
    expect(slow).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(normal);
    expect(normal).toHaveAttribute('aria-pressed', 'true');
  });
  it('keeps unverified AI fallback off and cannot issue a match request', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderPage();
    const ai = screen.getByRole('switch', { name: '允许匹配 AI 对手' });
    expect(ai).toHaveAttribute('aria-checked', 'false');
    expect(ai).toBeDisabled();
    await userEvent.click(ai);
    await userEvent.click(screen.getByRole('button', { name: '开始匹配 · 暂不可用' }));
    expect(ai).toHaveAttribute('aria-checked', 'false');
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
  it('switches create and join room settings without issuing requests', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderPage('room');
    await userEvent.click(screen.getByRole('tab', { name: '加入房间' }));
    await userEvent.type(screen.getByRole('textbox', { name: '房间号' }), '1234');
    expect(screen.getByRole('button', { name: '加入房间 · 暂不可用' })).toBeDisabled();
    await userEvent.click(screen.getByRole('tab', { name: '创建房间' }));
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: '我的房间' }));
    expect(screen.getByText('尚未接通我的房间')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开我的房间 · 暂不可用' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '打开我的房间 · 暂不可用' }));
    await userEvent.click(screen.getByRole('tab', { name: '加入房间' }));
    expect(screen.getByRole('textbox', { name: '房间号' })).toHaveValue('1234');
    expect(screen.getByText('按房号进入可能是观战身份，仍需确认可对弈席位。')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
  it('returns to Golaxy home and rejects unknown modes', async () => {
    const page = renderPage();
    await userEvent.click(screen.getByRole('button', { name: '星阵围棋' }));
    expect(await screen.findByText('星阵首页')).toBeInTheDocument();
    page.unmount();
    renderPage('unknown');
    expect(await screen.findByText('星阵首页')).toBeInTheDocument();
  });
});
