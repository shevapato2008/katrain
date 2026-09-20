import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PvpLocalSetupPage from './PvpLocalSetupPage';
import { PLAY_ON_BOARD_KEY, readPlayOnBoard } from '../utils/playInput';
import { openPick, pick } from '../__tests__/helpers/setupPick';

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
    await pick(userEvent.setup(), 'setup-handicap', '3');
    expect(board).toHaveAttribute('data-handicap', '3');
    expect([...board.querySelectorAll('[data-stone]')].map((g) => g.getAttribute('data-at')))
      .toEqual(['Q16', 'D4', 'Q4']);
  });

  /* **这一条是冲着一个真事故来的。**

     改版前这条测试叫「让了子之后贴目那一组换成说明,**而且送出去的还是那一档的值**」——
     标题说要验载荷,而它的断言里**一个载荷字段都没有**。于是那个 bug 一直没人挡:
     前端在 `handicap > 0` 时只把贴目那一组从屏上换掉,`komi` state 不动(缺省 6.5)
     且照样发出去。中国规则让 3 子实际是「白 +3(KataGo 按 `WHB_N` 自动加)+ 6.5 目」,
     正好是屏上那段说明警告的「两样一起用会补两遍」。

     所以现在断言**落在送出去的那两个字段上**,不落在屏上有没有那一组控件。 */
  it('让子局送出去的 komi 是 0 —— 补偿是 KataGo 按规则自动加的', async () => {
    renderPage();
    const user = userEvent.setup();
    await pick(user, 'setup-handicap', '3');
    expect(screen.getByTestId('setup-komi-value')).toHaveTextContent('不贴目 · 黑先摆 3 子');

    await user.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    expect(lastSetup()[2]).toMatchObject({ handicap: 3, komi: 0 });
  });

  it('分先送出去的是规则的默认贴目,换规则就跟着换', async () => {
    renderPage();
    const user = userEvent.setup();
    await pick(user, 'setup-rules', 'japanese');
    expect(screen.getByTestId('setup-komi-value')).toHaveTextContent('黑贴 6.5 目');
    await user.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    expect(lastSetup()[2]).toMatchObject({ rules: 'japanese', handicap: 0, komi: 6.5 });
  });

  it('用时那条下拉改的是 time_enabled / main_time 那一组载荷', async () => {
    renderPage();
    const user = userEvent.setup();
    expect(screen.getByTestId('setup-clock-value')).toHaveTextContent('不限时');
    await pick(user, 'setup-clock', '60');
    expect(screen.getByTestId('setup-clock-value')).toHaveTextContent('60分+3×30秒');

    await user.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    expect(lastSetup()[2]).toMatchObject({ time_enabled: true, main_time: 60, byo_length: 30, byo_periods: 3 });
  });

  // 「怎么落子」是**两段之和**:设备能不能 + 这一局想不想。
  it('没标定摄像头时「实体盘」灰掉,说得出为什么,屏幕照样选得了', async () => {
    renderPage();
    expect(screen.getByTestId('setup-input-value')).toHaveTextContent('屏幕');
    const pop = await openPick(userEvent.setup(), 'setup-input');
    expect(pop.querySelector('[data-k="board"]')).toBeDisabled();
    expect(pop.querySelector('[data-k="board"]')).toHaveTextContent('没标定过摄像头');
    expect(pop.querySelector('[data-k="screen"]')).toBeEnabled();
  });

  it('标定过的机器上默认走实体盘,选了屏幕就写进偏好', async () => {
    vision.enabled = true;
    renderPage();
    expect(screen.getByTestId('setup-input-value')).toHaveTextContent('实体盘');
    await pick(userEvent.setup(), 'setup-input', 'screen');
    expect(readPlayOnBoard()).toBe(false);
    expect(screen.getByTestId('setup-input-value')).toHaveTextContent('屏幕');
  });

  it('切到 9 路,实体盘这条路自己塌掉', async () => {
    vision.enabled = true;
    renderPage();
    const user = userEvent.setup();
    expect(screen.getByTestId('setup-input-value')).toHaveTextContent('实体盘');
    await pick(user, 'setup-size', '9');
    expect(screen.getByTestId('setup-input-value')).toHaveTextContent('屏幕');
    // 9 路的让子上限是 4 子,而且没有倒贴 —— 星位就那么多。
    const pop = await openPick(user, 'setup-handicap');
    expect([...pop.querySelectorAll('[data-k]')].map((e) => e.getAttribute('data-k')))
      .toEqual(['even', 'sen', '2', '3', '4', 'free']);
  });

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
