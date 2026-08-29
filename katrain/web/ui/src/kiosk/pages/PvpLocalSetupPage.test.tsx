import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PvpLocalSetupPage from './PvpLocalSetupPage';
import { PLAY_ON_BOARD_KEY, readPlayOnBoard } from '../utils/playInput';

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

// 「怎么落子」的**设备那一段**由它给(用户那一段在 `utils/playInput`)。
const vision = { enabled: false };
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: { enabled: vision.enabled }, isVisionEnabled: vision.enabled, refreshStatus: vi.fn(),
  }),
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

beforeEach(() => {
  vi.clearAllMocks();
  // 偏好活在 localStorage 里,**跨用例会串**。清掉 = 回到默认(开)。
  localStorage.removeItem(PLAY_ON_BOARD_KEY);
  vision.enabled = false;
});

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

  // 「怎么落子」是**两段之和**:设备能不能 + 这一局想不想。2026-08-23 之前这里是
  // 一格读数,理由写着「全仓没有任何地方能让用户切」—— 那句话是错的(做题屏早有这颗开关)。
  const seg = () => within(screen.getByTestId('setup-input'));

  it('没标定摄像头时「实体盘」灰掉,「屏幕」照样能按,而且说得出为什么', () => {
    renderPage();
    expect(seg().getByRole('button', { name: '屏幕' })).toHaveAttribute('aria-pressed', 'true');
    expect(seg().getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(seg().getByRole('button', { name: '屏幕' })).toBeEnabled();
    expect(screen.getByTestId('setup-input-group'))
      .toHaveTextContent('这台机器没有标定过摄像头,只能下在屏幕上');
  });

  // 两人面对面、盘就在中间 ⇒ **默认走实体盘**(偏好默认开,也正是这次改动之前的行为)。
  it('标定过的机器上默认走实体盘,选了屏幕就写进偏好', async () => {
    vision.enabled = true;
    renderPage();
    expect(seg().getByRole('button', { name: '实体盘' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('setup-input-group')).toHaveTextContent('两人面对面下在这块盘上');

    await userEvent.click(seg().getByRole('button', { name: '屏幕' }));
    expect(readPlayOnBoard()).toBe(false);
    expect(screen.getByTestId('setup-input-group')).toHaveTextContent('两人轮流点屏幕落子');
  });

  // 盒子上那块盘是 19 路的 —— 选 9 路,实体盘这条路自己塌掉,偏好不动。
  it('切到 9 路,实体盘这条路自己塌掉', async () => {
    vision.enabled = true;
    renderPage();
    await userEvent.click(within(screen.getByTestId('setup-size')).getByRole('button', { name: '9 路' }));
    expect(seg().getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(seg().getByRole('button', { name: '屏幕' })).toHaveAttribute('aria-pressed', 'true');
    expect(readPlayOnBoard()).toBe(true);   // 偏好没被改,调回 19 路它自己就回来
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
