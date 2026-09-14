import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import BaipuSessionPage from '../pages/BaipuSessionPage';
import type { BaipuStep } from '../../api/baipuApi';

/**
 * 屏 17 · 摆谱进行中 —— **行为 / 调用级**的单测(谁被导航到哪、发没发哪个请求、屏上说了哪句)。
 * ⚠️ jsdom 没有布局引擎:右栏装不装得下、动作区贴不贴底,判据在 `tests/kiosk-shell-scroll.spec.ts`。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { baipuLoad, baipuCapture } = vi.hoisted(() => ({ baipuLoad: vi.fn(), baipuCapture: vi.fn() }));
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load: baipuLoad, capture: baipuCapture } };
});

const { ledPoint } = vi.hoisted(() => ({ ledPoint: vi.fn() }));
vi.mock('../../api/ledApi', () => ({
  LedAPI: {
    point: ledPoint,
    points: vi.fn(() => Promise.resolve({ ok: true, connected: true })),
    clear: vi.fn(() => Promise.resolve({ ok: true, connected: true })),
  },
}));

const move = (i: number, row: number, col: number, color: 'B' | 'W'): BaipuStep => ({
  kind: 'move', move_index: i, property: color, row, col, color, removed: [], board_hash: `h${i}`,
});
const STEPS: BaipuStep[] = [move(0, 3, 15, 'B'), move(1, 15, 3, 'W')];
const META = { player_black: '申真谞', player_white: '柯洁', handicap: 0, komi: 7.5, ruleset: 'chinese' };

const renderPage = (collect = false) =>
  render(
    <MemoryRouter initialEntries={['/kiosk/baipu/session/g1']}>
      <Routes>
        <Route path="/kiosk/baipu/session/:source" element={<BaipuSessionPage collect={collect} />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  Element.prototype.scrollIntoView = vi.fn();   // jsdom 缺口,不是产品要绕的东西
  localStorage.setItem('baipu:sgf:g1', JSON.stringify({ id: 'g1', name: '三星杯', sgf: '(;SZ[19];B[pd];W[dp])', savedAt: 1 }));
  baipuLoad.mockResolvedValue({ board_size: 19, steps: STEPS, meta: META });
  baipuCapture.mockResolvedValue({ kind: 'disabled' });
  ledPoint.mockResolvedValue({ ok: true, connected: true });
});

describe('屏 17 摆谱 · 出口都回棋谱屏(K1)', () => {
  // `/kiosk/baipu` 那一页没有页控条、不在 Dock 词典里 ⇒ 盒上进去就出不来。
  it('退出确认里按「退出」回 /kiosk/kifu', async () => {
    renderPage();
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: /棋谱/ }));
    fireEvent.click(screen.getByTestId('baipu-exit-confirm-action'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });

  it('读谱失败时页控条返回回 /kiosk/kifu', async () => {
    baipuLoad.mockRejectedValue(new Error('baipu/load failed 422: bad'));
    renderPage();
    await screen.findByTestId('baipu-load-error');
    fireEvent.click(screen.getByRole('button', { name: /棋谱/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });

  it('摆完按「完成」回 /kiosk/kifu,并清掉这份的进度', async () => {
    renderPage();
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('把白子放'));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'done'));
    fireEvent.click(screen.getByRole('button', { name: '完成' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
    expect(localStorage.getItem('baipu:progress:g1')).toBeNull();
  });
});

describe('屏 17 摆谱 · 上线态不拍照(K4,Fan 2026-09-14)', () => {
  it('确认落子只推进:一次 /capture 都不发(开局帧也不拍),屏上没有「帧 / 拍照 / 摄像头」', async () => {
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
    expect(baipuCapture).not.toHaveBeenCalled();
    expect(screen.getByTestId('baipu-led-fold')).toHaveTextContent('红灯 = 放黑子');
    expect(screen.queryByTestId('baipu-cam-fold')).toBeNull();
    expect(screen.getByTestId('baipu-session-page').textContent).not.toMatch(/帧|拍照|摄像头/);
  });

  it('提子那一手:「已移除」之后照样只推进,不拍照', async () => {
    baipuLoad.mockResolvedValue({
      board_size: 19, meta: META,
      steps: [move(0, 3, 15, 'B'), { ...move(1, 0, 0, 'W'), removed: [{ row: 3, col: 15 }] }],
    });
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('把白子放'));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'removal'));
    fireEvent.click(screen.getByRole('button', { name: '已移除 1 子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'done'));
    expect(baipuCapture).not.toHaveBeenCalled();
  });

  it('采集态一个字没变:开局帧照拍,确认落子发 /capture', async () => {
    baipuCapture.mockResolvedValue({ kind: 'ok', result: { ok: true, path: '/c/g1/frame_001.jpg' } });
    renderPage(true);
    await screen.findByTestId('baipu-pcard');
    await waitFor(() => expect(baipuCapture).toHaveBeenCalledWith(expect.objectContaining({ move_index: -1 })));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(baipuCapture).toHaveBeenCalledWith(expect.objectContaining({ move_index: 0 })));
    expect(screen.getByTestId('baipu-cam-fold')).toBeInTheDocument();
  });
});
