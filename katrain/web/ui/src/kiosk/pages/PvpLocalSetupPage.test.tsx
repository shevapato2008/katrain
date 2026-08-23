import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PvpLocalSetupPage from './PvpLocalSetupPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock('../../api', () => ({
  API: {
    createSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    gameSetup: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  },
}));
const { writeActiveSession } = vi.hoisted(() => ({ writeActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({ writeActiveSession }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok', user: { username: 'u' } }) }));

// 「怎么落子」读的是设备能力,不是设置项 —— 这一屏因此要 VisionProvider 的桩。
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({ visionStatus: { enabled: false }, isVisionEnabled: false, refreshStatus: vi.fn() }),
}));

import { API } from '../../api';

/** 最近一次 `gameSetup(sessionId, mode, settings)` 的三个入参。 */
type SetupCall = [string, string, Record<string, unknown>];
const lastSetup = (): SetupCall =>
  (API.gameSetup as unknown as { mock: { calls: SetupCall[] } }).mock.calls[0];

const renderPage = () =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter><PvpLocalSetupPage /></MemoryRouter></ThemeProvider>);

/** 档位轨的两头键。轨本身不可点(29 个点摊在 330px 上手指点不准)。 */
const step = (testId: string, dir: '＋' | '−') =>
  within(screen.getByTestId(testId)).getByRole('button', { name: dir === '＋' ? /多|提高|增加/ : /少|降低|减少/ });

beforeEach(() => vi.clearAllMocks());

describe('PvpLocalSetupPage', () => {
  it('starts a pvp_local game with both player names and navigates to the local game route', async () => {
    renderPage();
    await userEvent.type(screen.getByTestId('black-name-input'), '小明');
    await userEvent.type(screen.getByTestId('white-name-input'), '小红');
    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    const [, mode, settings] = lastSetup();
    expect(mode).toBe('pvp_local');
    expect(settings.black_name).toBe('小明');
    expect(settings.white_name).toBe('小红');
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/pvp/local/game/s1');
  });

  // **不替用户编名字。** 两个框留空时送出去的是空串,后端 `server.py:1093` 因此不写
  // SGF 的 PB/PW,对局屏回落到「黑方 / 白方」(`GameControlPanel.tsx:66`)——
  // 前端在这儿塞一个默认名,那个名字会**被写进棋谱**,而它是谁都不知道。
  it('两个名字留空时送出去的是空串,不是前端编的「黑方 / 白方」', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    const [, , settings] = lastSetup();
    expect(settings.black_name).toBe('');
    expect(settings.white_name).toBe('');
    // 屏上那句话说的正是这件事,和送出去的载荷得对得上。
    expect(screen.getByText('留空就记成「黑方 / 白方」,不编名字')).toBeInTheDocument();
  });

  // 规范 §11:左边那块盘画的是**按下按钮后真会出现的那个局面**。
  // 屏 02 那一轮补的 `handicapStones()`,这一屏是它的第二个消费者 —— 点名是哪两个点,
  // 不是数个数:数个数的话摆错位置照样绿。
  it('让子调上去,左边那块盘跟着摆出让子', async () => {
    renderPage();
    const board = screen.getByTestId('kiosk-setup-board');
    expect(board).toHaveAttribute('data-handicap', '0');
    // 这一屏没有「我执」那一次选择 ⇒ `data-color` 整个不该出现。
    expect(board).not.toHaveAttribute('data-color');

    await userEvent.click(step('setup-handicap', '＋'));
    await userEvent.click(step('setup-handicap', '＋'));
    expect(board).toHaveAttribute('data-handicap', '2');
    expect([...board.querySelectorAll('[data-stone]')].map((g) => g.getAttribute('data-at')))
      .toEqual(['Q16', 'D4']);
  });

  // 让子局没有贴目这回事 —— **不是把控件灰掉**,是换成一段说明(同屏 02)。
  it('让了子之后贴目那一组换成说明,而且送出去的还是那一档的值', async () => {
    renderPage();
    expect(screen.getByTestId('setup-komi')).toBeInTheDocument();
    await userEvent.click(step('setup-handicap', '＋'));
    expect(screen.queryByTestId('setup-komi')).not.toBeInTheDocument();
    expect(screen.getByTestId('setup-komi-explain')).toHaveTextContent('已经让了 1 子');
  });

  // 七档在轨上按时长从短到长排,默认停在最右端(不限时)⇒ 往回按一格是 60 分。
  // 按下去要改的是**送给后端的那四个字段**,不是只改一句读数。
  it('用时那条轨改的是 time_enabled / main_time 那一组载荷', async () => {
    renderPage();
    expect(screen.getByText('不限时')).toBeInTheDocument();
    await userEvent.click(step('setup-clock', '−'));
    expect(screen.getByTestId('setup-clock').parentElement).toHaveTextContent('60分+3×30秒');

    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    const [, , settings] = lastSetup();
    expect(settings).toMatchObject({ time_enabled: true, main_time: 60, byo_length: 30, byo_periods: 3 });
  });

  // 「落子」是读数不是控件:桩里 `isVisionEnabled` 为 false ⇒ 这一格写「屏幕」,
  // 而且**这一组里除了路数没有第二个能点的东西**(屏幕/实体盘不是两颗键)。
  it('「落子」那一格是读数,不是能点的分段控件', () => {
    renderPage();
    const readout = screen.getByTestId('setup-input-readout');
    expect(readout).toHaveTextContent('屏幕');
    expect(readout.querySelectorAll('button')).toHaveLength(0);
    expect(within(screen.getByTestId('setup-input-group')).getAllByRole('button'))
      .toHaveLength(3);   // 19 / 13 / 9 路,仅此三颗
  });

  // 这一屏没有引擎,所以稿子上属于人机那三组(棋力 / AI 策略 / 我执)一个都不该在。
  it('没有棋力、AI 策略和「我执」三组', () => {
    renderPage();
    expect(screen.queryByTestId('setup-strength')).not.toBeInTheDocument();
    expect(screen.queryByTestId('setup-strategy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('setup-color')).not.toBeInTheDocument();
  });

  // 屏上那两句话是**产品文案里最容易编的一类** —— 它们说的是别的屏上的事(对局屏封了什么、
  // 段位在哪儿改)。两句都有出处:`interface.py:253/258`。改了就得先去核那两行。
  it('底下那段说明指的是「升降级对弈」,不是在线大厅', () => {
    renderPage();
    const note = screen.getByTestId('setup-note');
    expect(note).toHaveTextContent('只留档,不动段位');
    expect(note).toHaveTextContent('升降级对弈');
    expect(note).not.toHaveTextContent('在线大厅');
    // 「没有形势判断」是稿子的原话,而 `pvp_local` 不在 SCORING_GAME_TYPES 里 ⇒
    // 对局屏那颗「领地」照样能按。屏上不许说这句。
    expect(note).not.toHaveTextContent('形势判断');
  });
});
