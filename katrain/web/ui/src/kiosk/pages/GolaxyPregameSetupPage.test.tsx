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
    expect(screen.getByText('19 路 · 开局预览')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /暂不可用/ })).toBeDisabled();
    expect(screen.getByText('星阵匹配与房间协议尚未确认，暂不能开局。')).toBeInTheDocument();
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
  it('switches create and join room settings without issuing requests', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderPage('room');
    await userEvent.click(screen.getByRole('tab', { name: '加入房间' }));
    await userEvent.type(screen.getByRole('textbox', { name: '房间号' }), '1234');
    expect(screen.getByRole('button', { name: '加入房间 · 暂不可用' })).toBeDisabled();
    await userEvent.click(screen.getByRole('tab', { name: '创建房间' }));
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
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
