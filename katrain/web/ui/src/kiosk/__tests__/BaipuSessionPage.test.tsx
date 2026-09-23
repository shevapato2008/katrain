import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
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

// 摆谱缓存按身份分区(kioskActivityStorage,develop 2026-09):真用户的键带 `:<uuid>` 后缀。
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { uuid: 'u1' }, isGuest: false, isLoading: false }),
}));
const key = (k: string) => `${k}:u1`;

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

// 三路判据:`vis.status` 为 null = 没有 VisionProvider = 手动兜底;给了就绪状态 = 摄像头态。
// 识别 IO 层(`usePhysicalBaipu`)的规则由它自己的单测管,这里只换成一个可控的读数,并记下页面喂给它什么。
const { vis, phys, quickAnalyze } = vi.hoisted(() => ({
  vis: { status: null as null | { enabled: boolean; recognitionReady: boolean } },
  phys: { state: {} as Record<string, unknown>, opts: null as null | Record<string, unknown> & { onMatched: () => void } },
  quickAnalyze: vi.fn(),
}));
vi.mock('../context/VisionContext', () => ({
  useOptionalVision: () => (vis.status ? { visionStatus: vis.status } : null),
}));
vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({ syncEvents: [], latestEvent: null, setupProgress: null, isSetupComplete: false, connected: true }),
}));
vi.mock('../hooks/usePhysicalBaipu', () => ({
  usePhysicalBaipu: (o: typeof phys.opts) => { phys.opts = o; return phys.state; },
}));
vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return { ...actual, API: { ...actual.API, quickAnalyze } };
});

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
  localStorage.setItem(key('baipu:sgf:g1'), JSON.stringify({ id: 'g1', name: '三星杯', sgf: '(;SZ[19];B[pd];W[dp])', savedAt: 1 }));
  baipuLoad.mockResolvedValue({ board_size: 19, steps: STEPS, meta: META });
  baipuCapture.mockResolvedValue({ kind: 'disabled' });
  ledPoint.mockResolvedValue({ ok: true, connected: true });
  vis.status = null;
  phys.opts = null;
  phys.state = {
    phase: 'await', reason: null, missing: [], extra: [], wrong: null, stuck: false, ledOk: true,
    relight: vi.fn(), adopt: vi.fn(),
  };
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

  it('采集机摆完按「完成」回 /kiosk/kifu,并清掉这份的进度', async () => {
    renderPage(true);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'done'));
    fireEvent.click(screen.getByRole('button', { name: '完成' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
    expect(localStorage.getItem(key('baipu:progress:g1'))).toBeNull();
  });
});

describe('屏 17 摆谱 · 上线态不拍照(K4,Fan 2026-09-14)', () => {
  it('确认落子只推进:一次 /capture 都不发(开局帧也不拍),屏上没有「帧 / 拍照」', async () => {
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
    expect(baipuCapture).not.toHaveBeenCalled();
    expect(screen.getByTestId('baipu-led-fold')).toHaveTextContent('红灯 = 放黑子');
    expect(screen.queryByTestId('baipu-cam-fold')).toBeNull();
    // 「摄像头」可以出现 —— 手动兜底要说清为什么没用它;不许出现的是拍照那一族。
    expect(screen.getByTestId('baipu-session-page').textContent).not.toMatch(/帧|拍照/);
  });

  it('提子那一手:「已移除」之后照样只推进,不拍照', async () => {
    baipuLoad.mockResolvedValue({
      board_size: 19, meta: META,
      steps: [move(0, 3, 15, 'B'), { ...move(1, 0, 0, 'W'), removed: [{ row: 3, col: 15 }] }],
    });
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
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

describe('屏 17 摆谱 · 只摆 19 路(K2)', () => {
  // 实体盘和灯阵都是 19 路。13 路的行列发给灯,会亮在实体盘左上角那一块 —— 每一颗都错位。
  it('13 路的谱:说清摆不了、一颗灯都不点,并从「最近摆过」和本地缓存里拿掉', async () => {
    localStorage.setItem(key('baipu:recent'), JSON.stringify([
      { id: 'g1', name: '三星杯', savedAt: 1 }, { id: 'other', name: '别的', savedAt: 1 },
    ]));
    localStorage.setItem(key('baipu:progress:g1'), JSON.stringify({ k: 0, frames: 0, updatedAt: 1 }));
    baipuLoad.mockResolvedValue({ board_size: 13, steps: [move(0, 3, 3, 'B')], meta: META });
    renderPage();
    expect(await screen.findByText('这是 13 路的谱，摆不了')).toBeInTheDocument();
    expect(ledPoint).not.toHaveBeenCalled();
    expect(localStorage.getItem(key('baipu:sgf:g1'))).toBeNull();
    expect(localStorage.getItem(key('baipu:progress:g1'))).toBeNull();
    expect(JSON.parse(localStorage.getItem(key('baipu:recent'))!)).toEqual([{ id: 'other', name: '别的', savedAt: 1 }]);
    fireEvent.click(screen.getByRole('button', { name: /棋谱/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });
});

describe('屏 17 摆谱 · 手动兜底(摄像头用不了,稿 17d)', () => {
  it('临时露出「确认落子」并写明原因;试下灰着说为什么;没有「完成」;摆完自动清进度', async () => {
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('没接摄像头 —— 摆好后按「确认落子」');
    expect(screen.getByTestId('baipu-led-fold')).toHaveTextContent('手动确认');
    const tryBtn = screen.getByRole('button', { name: '试下' });
    expect(tryBtn).toBeDisabled();
    expect(tryBtn).toHaveAttribute('title', '摄像头没在识别');
    expect(screen.queryByRole('button', { name: '完成' })).toBeNull();
    expect(phys.opts?.enabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'done'));
    expect(localStorage.getItem(key('baipu:progress:g1'))).toBeNull();
  });
});

describe('屏 17 摆谱 · 摄像头态(Fan 2026-09-23:不用每步按确认)', () => {
  beforeEach(() => { vis.status = { enabled: true, recognitionReady: true }; });

  it('没有确认键:动作区只有 撤回 / 试下 / AI支招;识别层拿到下一手(黑 = 1)', async () => {
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    const names = screen.getAllByRole('button').map((b) => b.textContent);
    expect(names).not.toContain('确认落子');
    expect(screen.getByTestId('baipu-actions').textContent).toBe('撤回上一手试下AI支招');
    expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('摄像头认到就自动下一手');
    expect(screen.getByTestId('baipu-led-fold')).toHaveTextContent('摄像头在看');
    expect(phys.opts).toMatchObject({ enabled: true, k: 0, paused: false, next: { row: 3, col: 15, color: 1 } });
  });

  it('摄像头认到 → 推进一手;撤回立刻生效、不弹框', async () => {
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    act(() => phys.opts!.onMatched());
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
    fireEvent.click(screen.getByRole('button', { name: '撤回上一手' }));
    expect(screen.queryByTestId('baipu-undo-confirm')).toBeNull();
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 1 / 2 手'));
  });

  it('放错:pcard 说应该在哪、蓝灯那颗是哪;盘上圈出该拿走的', async () => {
    phys.state = { ...phys.state, phase: 'setup', reason: 'wrong', wrong: [4, 15], extra: [[4, 15, 1]] };
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'setup');
    expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('放错了 · 应该在 Q16');
    expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('把蓝灯那颗(Q15)拿起来，放到 Q16');
    expect(document.querySelectorAll('.gob .remove')).toHaveLength(1);
  });

  it('setup 卡住 10 s → 露出「摆好了，继续」,按下走 adopt', async () => {
    phys.state = { ...phys.state, phase: 'setup', reason: 'entry', stuck: true };
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '摆好了，继续' }));
    expect(phys.state.adopt).toHaveBeenCalled();
  });

  it('试下是开关:按下暂停识别,撤回和 AI支招灰掉;再按一次恢复', async () => {
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    act(() => phys.opts!.onMatched());
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    expect(screen.getByRole('button', { name: '试下' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('试下中 · 摄像头暂停识别');
    expect(phys.opts?.paused).toBe(true);
    expect(screen.getByRole('button', { name: '撤回上一手' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'AI支招' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    expect(phys.opts?.paused).toBe(false);
  });

  it('AI 支招:候选三行借灯图例的位置,识别暂停,候选点交给识别层点白灯', async () => {
    quickAnalyze.mockResolvedValue({ moveInfos: [{ move: 'D4', winrate: 0.524, scoreLead: 0.9 }] });
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: 'AI支招' }));
    await waitFor(() => expect(screen.getByTestId('baipu-hint-fold')).toHaveTextContent('1 · D4胜率 52.4% · 目差 +0.9'));
    expect(screen.queryByTestId('baipu-led-fold')).toBeNull();
    expect(phys.opts).toMatchObject({ paused: true, hintLeds: [{ row: 15, col: 3, color: 'hint' }] });
    expect(document.querySelectorAll('.gob .hint')).toHaveLength(1);
  });
});
