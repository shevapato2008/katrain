import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlatformEngineSetupPage from './PlatformEngineSetupPage';
import { openPick, pick } from '../__tests__/helpers/setupPick';
import { clearActiveSession } from '../utils/activeSession';
import { readSessionPlayOnBoard, writePlayOnBoard } from '../utils/playInput';

/**
 * 屏 09 跨平台 · 人机开局的**行为**那一半。版式归
 * `tests/kiosk-screen-07-09-platform.fourup.spec.ts`(眼睛)和
 * `tests/kiosk-shell-scroll.spec.ts`(机器量),这里一条几何都不断言。
 *
 * ⚠️ 上一版这里有一条 `expect(getComputedStyle(panel).overflowY).not.toBe('auto')` ——
 * **删了**:它断的是布局结论,而 jsdom 没有布局引擎;而且这一屏改完之后右栏**本来就要滚**,
 * 那条断言连意图都反了。它换成的是真浏览器里那条
 * 「装不下时右栏自己滚,而『开始对局』怎么滚都还在」。
 *
 * 这里检查平台下发的棋力档、让子与贴目的对应关系、落子方式和开局请求。
 * 对手菜单沿用已有组件；没有第二套加减档控件。
 */

const { platformEngineLevels, platformEngineStart } = vi.hoisted(() => ({
  platformEngineLevels: vi.fn(),
  platformEngineStart: vi.fn(),
}));
vi.mock('../../api', () => ({ API: { platformEngineLevels, platformEngineStart } }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok', user: { id: 1, username: 'u' }, isAuthenticated: true }),
}));
// 默认没标定摄像头 —— 和这个 mock 之前的静态值一致。R-08 的两次渲染对比测试
// 把它改成 `true` 来看差异,别的用例都吃这个默认值。
let mockIsVisionEnabled = false;
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({ visionStatus: { enabled: mockIsVisionEnabled }, isVisionEnabled: mockIsVisionEnabled, refreshStatus: vi.fn() }),
}));
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const LEVELS = Array.from({ length: 39 }, (_, i) => ({
  elo_score: 100 + i * 10,
  level_name: `第 ${i + 1} 档`,
  name: `星阵 ${i + 1}`,
  goal_difference: 0,
  timing: '',
  display_elo: 400 + i * 50,
  ref_rank: `业余 ${i + 1}`,
}));

const renderPage = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/cross-platform/engine/golaxy']}>
      <Routes>
        <Route path="/kiosk/play/cross-platform/engine/:platform" element={<PlatformEngineSetupPage />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>,
);

/** 对手名牌 —— 读数搬到这里之后,「星阵 1 · 第 1 档」「第 1 / 39 档 · 展示 Elo … · 对标…」都在它身上。 */
const plate = () => screen.getByTestId('setup-opponent-plate');
/** 对手组标题右端(「星阵下发 39 档」)。 */
const opponentSecval = () => screen.getByTestId('setup-opponent').querySelector('.secval')!;
const komiValue = () => screen.getByTestId('setup-komi-value');
/** 棋力档拉回来了 = 这一屏的控件全部就绪。 */
const ready = () => waitFor(() => expect(plate()).toHaveTextContent('第 1 档'));

beforeEach(() => {
  vi.clearAllMocks();
  clearActiveSession('game');
  writePlayOnBoard(true);
  mockIsVisionEnabled = false;
  platformEngineLevels.mockResolvedValue({ levels: LEVELS });
  platformEngineStart.mockResolvedValue({ session_id: 's1' });
});

describe('屏 09 跨平台 · 人机开局', () => {
  it('对手只用名牌打开档位菜单,不再显示加减档控件', async () => {
    renderPage();
    await ready();
    expect(screen.queryAllByTestId('level-row')).toHaveLength(0);
    expect(screen.queryByTestId('setup-level-sheet')).not.toBeInTheDocument();
    expect(screen.queryByTestId('setup-level')).not.toBeInTheDocument();
    expect(plate()).toHaveTextContent('星阵 1 · 第 1 档');
  });

  it('打开对手菜单选档后,名牌上的读数跟着更新', async () => {
    renderPage();
    await ready();
    await userEvent.click(plate());
    const sheet = screen.getByTestId('setup-level-sheet');
    await userEvent.click(within(sheet).getAllByTestId('level-row')[1].querySelector('button')!);
    expect(plate()).toHaveTextContent('星阵 2 · 第 2 档');
    expect(screen.queryByTestId('setup-level-sheet')).not.toBeInTheDocument();
  });

  /**
   * **反写死变异**:名单只有 5 条时屏上必须写「5 档」「第 n / 5 档」。
   * 「39」这个数由组标题和名牌共同展示,写死其中一处会露馅。
   */
  it('档数来自下发那份名单,不是写死的 39', async () => {
    platformEngineLevels.mockResolvedValue({ levels: LEVELS.slice(0, 5) });
    renderPage();
    await ready();
    expect(opponentSecval()).toHaveTextContent('星阵围棋下发 5 档');
    expect(plate()).toHaveTextContent('第 1 / 5 档');
  });

  // `ref_rank` 是那份名单里唯一不在轨上的一列(顶上六档是「野狐 9D」「职业 / 野狐 9D+」)。
  // 名牌保留这两项平台下发的事实。
  it('名牌带上展示 Elo 和「对标棋力」—— 名单撤了,那一列得有落点', async () => {
    renderPage();
    await ready();
    expect(plate()).toHaveTextContent('展示 Elo 400');
    expect(plate()).toHaveTextContent('对标业余 1');
  });

  it('让子使用下拉,保留星阵的分先/让先/让 2–9 子和贴目对应关系', async () => {
    renderPage();
    await ready();
    expect(screen.getByTestId('setup-handicap-value')).toHaveTextContent('分先');
    expect(komiValue()).toHaveTextContent('黑贴 7.5 目');
    const user = userEvent.setup();
    const pop = await openPick(user, 'setup-handicap');
    expect([...pop.querySelectorAll('[data-k]')].map((e) => e.getAttribute('data-k')))
      .toEqual(['0', '-1', '2', '3', '4', '5', '6', '7', '8', '9']);
    await user.click(within(pop).getByRole('option', { name: '让先' }));
    expect(komiValue()).toHaveTextContent('不贴目');
    await pick(user, 'setup-handicap', '2');
    expect(komiValue()).toHaveTextContent('黑贴 2 子');
  });

  it('「开始对局」发的是当下这三项', async () => {
    renderPage();
    await ready();
    await userEvent.click(plate());
    await userEvent.click(within(screen.getByTestId('setup-level-sheet')).getAllByTestId('level-row')[1].querySelector('button')!);
    await pick(userEvent.setup(), 'setup-handicap', '-1');
    await userEvent.click(screen.getByTestId('platform-engine-start'));
    await waitFor(() => expect(platformEngineStart).toHaveBeenCalledWith(
      'golaxy', { level: 110, human_color: 'nigiri', handicap: -1 }, 'tok',
    ));
    await waitFor(() => expect(mockNavigate)
      .toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/game/s1', { state: { backTo: '/kiosk/play/cross-platform/engine/golaxy' } }));
  });

  it('实体盘开局后固定本局落子方式,不受下一局的偏好变化影响', async () => {
    mockIsVisionEnabled = true;
    renderPage();
    await ready();
    expect(screen.getByTestId('setup-input-value')).toHaveTextContent('实体盘');
    await userEvent.click(screen.getByTestId('platform-engine-start'));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
    const route = '/kiosk/play/cross-platform/engine/game/s1';
    expect(readSessionPlayOnBoard(route)).toEqual({ onBoard: true, fromSession: true });
    writePlayOnBoard(false);
    expect(readSessionPlayOnBoard(route)).toEqual({ onBoard: true, fromSession: true });
  });

  it('我执下拉保留猜先 / 执黑 / 执白,选了执白就写进 payload', async () => {
    renderPage();
    await ready();
    expect(screen.getByTestId('setup-side-value')).toHaveTextContent('猜先');
    const pop = await openPick(userEvent.setup(), 'setup-side');
    ['猜先', '执黑', '执白'].forEach((label) => {
      expect(within(pop).getByRole('option', { name: label })).toBeInTheDocument();
    });
    await userEvent.click(within(pop).getByRole('option', { name: '执白' }));
    await userEvent.click(screen.getByTestId('platform-engine-start'));
    await waitFor(() => expect(platformEngineStart).toHaveBeenCalledWith(
      'golaxy', { level: 100, human_color: 'W', handicap: 0 }, 'tok',
    ));
  });

  it('返回键回跨平台连接页', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: /跨平台/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform');
  });

  it('拉不到棋力档:说出来,**不给兜底表**,也开不了局', async () => {
    platformEngineLevels.mockRejectedValue(new Error('golaxy 没回话'));
    renderPage();
    await screen.findByText('golaxy 没回话');
    expect(screen.queryByTestId('setup-opponent-plate')).not.toBeInTheDocument();
    expect(screen.getByTestId('platform-engine-start')).toBeDisabled();
  });

  it('路数不是控件 —— 星阵只开 19 路,屏上没有任何棋盘尺寸按钮', async () => {
    renderPage();
    await ready();
    expect(screen.queryByRole('button', { name: /路/ })).not.toBeInTheDocument();
  });

  // 这一屏之前**没有**这颗开关(屏 02/03/04 早就接了)——
  // 于是同一台盒子上自由对弈选得了屏幕、跨平台却选不了。
  it('落子下拉在;没标定摄像头时「实体盘」灰掉并说明原因', async () => {
    renderPage();
    await ready();
    expect(screen.getByTestId('setup-input-value')).toHaveTextContent('屏幕');
    const pop = await openPick(userEvent.setup(), 'setup-input');
    expect(within(pop).getByRole('option', { name: '屏幕' })).toBeEnabled();
    expect(within(pop).getByRole('option', { name: /实体盘/ })).toBeDisabled();
    expect(screen.getByText(/还没标定摄像头/)).toBeInTheDocument();
  });

  // Review Focus #1:平台一档都没下发。
  it('平台一档都没下发时,开始键按不下去,也不画名牌', async () => {
    platformEngineLevels.mockResolvedValue({ levels: [] });
    renderPage();
    await screen.findByTestId('platform-engine-start');
    expect(screen.getByTestId('platform-engine-start')).toBeDisabled();
    expect(screen.queryByTestId('setup-opponent-plate')).toBeNull();
  });

  /**
   * R-08:brief 原 Step 11 要求「面板开着时派一个视觉事件,断言轨够不着」——
   * 不写。理由两条:① 这份 mock 把 `useVision` 做成静态返回值,没有事件总线可派事件;
   * ② 就算写了也不可能失败 —— 面板是同一棵 React 树里的子节点,「开着的面板吞掉一次
   * state 更新」在 React 里没有对应机制。面板盖没盖住轨是**布局**问题,归 Task 4 的
   * 真浏览器几何闸,不归这里。
   *
   * 这里改测**真实为真的行为**:摄像头能不能用,决定「实体盘」这一档选不选得了、
   * 提示行说的是哪一句 —— 这是屏 09 曾经真出过的缺陷(上线时压根没有「怎么落子」
   * 这颗开关),提示行是它唯一诚实的降级路径。
   */
  it('摄像头能不能用,决定「实体盘」选不选得了、提示行说哪一句', async () => {
    mockIsVisionEnabled = true;
    const available = renderPage();
    await waitFor(() => expect(within(available.getByTestId('setup-opponent-plate')).getByText(/第 1 档/)).toBeInTheDocument());
    const availablePop = await openPick(userEvent.setup(), 'setup-input');
    expect(within(availablePop).getByRole('option', { name: '实体盘' })).toBeEnabled();
    expect(available.getByTestId('setup-input-hint')).toHaveTextContent('屏幕和实体盘走同一条隧道');
    available.unmount();

    mockIsVisionEnabled = false;
    const unavailable = renderPage();
    await waitFor(() => expect(within(unavailable.getByTestId('setup-opponent-plate')).getByText(/第 1 档/)).toBeInTheDocument());
    const unavailablePop = await openPick(userEvent.setup(), 'setup-input');
    expect(within(unavailablePop).getByRole('option', { name: /实体盘/ })).toBeDisabled();
    expect(unavailable.getByTestId('setup-input-hint')).toHaveTextContent('还没标定摄像头');
  });
});
