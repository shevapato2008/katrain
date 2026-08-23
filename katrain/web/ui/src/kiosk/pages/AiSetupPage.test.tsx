import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from './AiSetupPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const {
  startRanked, rankedState, retryRanked, createSession, gameSetup,
  endRanked, retrySettlement, applyBlockingSync,
} = vi.hoisted(() => ({
  startRanked: vi.fn().mockResolvedValue({ session_id: 'ranked-s1', game_id: 'g1' }),
  retryRanked: vi.fn(),
  createSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  gameSetup: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  endRanked: vi.fn(),
  retrySettlement: vi.fn(),
  applyBlockingSync: vi.fn(),
  rankedState: { current: { view_state: 'ready', placement_state: { phase: 'placement', completed_games: 2, total_games: 5 }, current_opponent: { rung: 12, rank_name: '9级', certification_status: 'certified', availability: 'available', route: 'server' }, recent_ranked_results: [], net_score: 0, pending_settlement: false } as any },
}));

const READY_STATUS = rankedState.current;

/** 挡住新局的那一局。默认是最省事的一格,每条测试只覆写它关心的字段。 */
const blockingGame = (overrides: Record<string, unknown> = {}) => ({
  game_id: 'occupied-game',
  state: 'active',
  ownership: 'other_device',
  user_color: 'B',
  opponent_rank_name: '9级',
  ...overrides,
});

const withBlocking = (game: Record<string, unknown> | null) => {
  rankedState.current = { ...READY_STATUS, blocking_game: game } as any;
};

vi.mock('../../api', () => ({
  API: {
    createSession,
    gameSetup,
  },
}));
// vi.mock 的工厂被提升到文件顶部,所以类必须也在 vi.hoisted 里造 —— 写成模块级
// `class` 时工厂会在它初始化之前跑到,报 "Cannot access before initialization"。
const { MockAiLadderApiError } = vi.hoisted(() => ({
  MockAiLadderApiError: class extends Error {
    status: number;
    constructor(status: number, message: string) { super(message); this.status = status; }
  },
}));
vi.mock('../../features/aiLadder/api', () => ({
  startAiLadderGame: startRanked,
  endAiLadderGame: endRanked,
  retryAiLadderSettlement: retrySettlement,
  AiLadderApiError: MockAiLadderApiError,
}));
vi.mock('../../features/aiLadder/useAiLadderStatus', () => ({
  useAiLadderStatus: () => ({ status: rankedState.current, retry: retryRanked, applyBlockingSync }),
}));

const { writeActiveSession } = vi.hoisted(() => ({ writeActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({ writeActiveSession }));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true }),
}));

// 「怎么落子」那一格读的是**设备能力**(摄像头标没标定),不是设置项 ——
// 所以它要有个桩,而且要能切:两态在屏上是两句不同的话。
const vision = vi.hoisted(() => ({ enabled: false }));
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: { enabled: vision.enabled },
    isVisionEnabled: vision.enabled,
    refreshStatus: vi.fn(),
  }),
}));

const renderPage = (mode = 'free') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/play/ai/setup/${mode}`]}>
        <Routes>
          <Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('AiSetupPage', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mockNavigate.mockReset();
    writeActiveSession.mockReset();
    startRanked.mockClear();
    createSession.mockClear();
    gameSetup.mockClear();
    endRanked.mockReset();
    retrySettlement.mockReset();
    applyBlockingSync.mockReset();
    retryRanked.mockReset();
    withBlocking(null);
    vision.enabled = false;
    startRanked.mockResolvedValue({ session_id: 'ranked-s1', game_id: 'g1', status: rankedState.current });
  });

  // 原来钉的是「盘面预览」那行眉标。布局 A 的左栏**只有盘**(规范 `:512`:它画的是按下
  // 按钮后真会出现的局面),那行眉标随旧的预览盒一起没了 —— 这是布局裁定的后果,不是改文案。
  // 陷阱照旧:左边必须有一块真盘,而且它得跟着「我执」翻(`:512` 后半句)。
  it('renders the opening-position board, oriented by my colour', () => {
    renderPage();
    const board = screen.getByTestId('kiosk-setup-board');
    expect(board).toBeInTheDocument();
    expect(board).toHaveAttribute('data-color', 'black');
  });

  it('writes the active session and navigates to the game route on Start (free mode)', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对局|开始计分局/i }));

    await waitFor(() => {
      expect(writeActiveSession).toHaveBeenCalledWith({
        kind: 'game',
        label: '自由对弈',
        route: '/kiosk/play/ai/game/s1',
        ts: expect.any(Number),
      });
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/game/s1');
    });
  });

  it('writes the ranked label on Start (ranked mode)', async () => {
    renderPage('ranked');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对局|开始计分局/i }));

    await waitFor(() => {
      expect(writeActiveSession).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'game', label: '升降级对弈', route: '/kiosk/play/ai/game/ranked-s1' })
      );
      expect(startRanked).toHaveBeenCalledWith(expect.objectContaining({ color: 'black' }), 'test-token');
      expect(startRanked.mock.calls[0][0]).not.toHaveProperty('board_size');
      expect(createSession).not.toHaveBeenCalled();
      expect(gameSetup).not.toHaveBeenCalled();
      expect(JSON.parse(sessionStorage.getItem('ai-ladder-before:ranked-s1')!)).toEqual(expect.objectContaining({
        game_id: 'g1',
      }));
    });
  });

  it('shows the server-selected ranked opponent instead of HumanSL strength', () => {
    renderPage('ranked');
    expect(screen.getByText('定级对手：9级')).toBeInTheDocument();
    // 棋力那条轨在升降级屏**整组不渲染** —— 对手由盒子配档。
    // (原来这里钉的是「没有 `combobox[name=AI 棋力]`」,而控件已经不是 combobox 了,
    //  那条断言从此永远为真、什么都不再守。)
    expect(screen.queryByTestId('setup-strength')).not.toBeInTheDocument();
  });

  // 升降级那一屏上,规则 / 让子 / 贴目 / 路数**都是服务端定的**:给个能点的控件
  // 只会是个改不动的旋钮。屏上因此是一格读数,不是一排灰掉的选择器。
  it('升降级屏:服务端定的那几项是读数,不是控件', () => {
    renderPage('ranked');
    expect(screen.getByTestId('setup-ranked-fixed')).toHaveTextContent('19 路');
    expect(screen.getByTestId('setup-ranked-fixed')).toHaveTextContent('中国规则 · 贴 7.5 目 · 不让子');
    // 路数、让子、贴目、规则、棋力五组在这一屏一组都不该出现。
    expect(screen.queryByTestId('setup-size')).not.toBeInTheDocument();
    expect(screen.queryByTestId('setup-handicap')).not.toBeInTheDocument();
    expect(screen.queryByTestId('setup-komi')).not.toBeInTheDocument();
    expect(screen.queryByTestId('setup-rules')).not.toBeInTheDocument();
    expect(screen.queryByTestId('setup-strength')).not.toBeInTheDocument();
    // 用时和执子照旧是能选的。
    expect(screen.getByTestId('setup-clock')).toBeInTheDocument();
    expect(screen.getByTestId('setup-color')).toBeInTheDocument();
    expect(screen.getByTestId('ranked-start-action')).toBeInTheDocument();
  });

  // 稿子那两格写的是「胜 · 升到 4 级」「负 · 退到 6 级」—— **那是净胜分正好 ±2 的特例**。
  // 真规则在 `core/ai_ladder_ranked.py:1503-1506`:每局 ±1,到 ±3 才动档。
  // 这三条守的就是「不把特例说成常态」。
  it.each([
    [0, '胜 · 净胜分 +1', '负 · 净胜分 -1'],
    [2, '胜 · 升一档', '负 · 净胜分 +1'],
    [-2, '胜 · 净胜分 -1', '负 · 退一档'],
  ])('赌注按净胜分 %i 说话', (net, win, loss) => {
    rankedState.current = { ...rankedState.current, net_score: net };
    renderPage('ranked');
    const stakes = screen.getByTestId('setup-stakes');
    expect(stakes).toHaveTextContent(win);
    expect(stakes).toHaveTextContent(loss);
  });

  it('自由对弈:路数三档照旧都在,而且是分段控件不是下拉', () => {
    renderPage('free');
    const size = screen.getByTestId('setup-size');
    expect(size).toHaveTextContent('19 路');
    expect(size).toHaveTextContent('13 路');
    expect(size).toHaveTextContent('9 路');
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  // 规范 §11(v1.21):一屏之内所有选择组必须用同一种控件,项数上限 6。
  // 这一条**倒过来了**:原来钉的是「规则要是下拉、AGA 不许可见」,
  // 而稿子 02 屏画的正是四段并排。项数 4 ≤ 6,分段就是对的那一种。
  it('规则四段并排 —— 不再是下拉', () => {
    renderPage('free');
    const rules = screen.getByTestId('setup-rules');
    for (const label of ['中国', '日本', '韩国', 'AGA']) {
      expect(rules).toHaveTextContent(label);
    }
  });

  // 「怎么落子」不是设置项,是这台盒子此刻的能力(`VisionContext`,后端给的)。
  // 两态在屏上是两句不同的话,而且**两态都不给按** —— 它是 `.igfix` 读数。
  it.each([
    [true, '实体盘'],
    [false, '屏幕'],
  ])('落子那一格照实说设备能力:isVisionEnabled=%s', (enabled, expected) => {
    vision.enabled = enabled;
    renderPage('free');
    const readout = screen.getByTestId('setup-input-readout');
    expect(readout).toHaveTextContent(expected);
    expect(readout.querySelector('button')).toBeNull();
  });

  // 让子 > 0 时贴目那一组**整个换成一段话**,不是把控件灰掉:
  // 灰掉说的是「你现在不能改」,而这一局是根本没有贴目这回事。
  it('让子调上去,贴目那一组换成说明;调回 0 再变回档位轨', async () => {
    renderPage('free');
    const user = userEvent.setup();
    expect(screen.getByTestId('setup-komi')).toBeInTheDocument();
    expect(screen.queryByTestId('setup-komi-explain')).not.toBeInTheDocument();

    await user.click(within(screen.getByTestId('setup-handicap')).getByRole('button', { name: '多让一子' }));
    expect(screen.getByTestId('setup-komi-explain')).toHaveTextContent('已经让了 1 子');
    expect(screen.queryByTestId('setup-komi')).not.toBeInTheDocument();

    await user.click(within(screen.getByTestId('setup-handicap')).getByRole('button', { name: '少让一子' }));
    expect(screen.getByTestId('setup-komi')).toBeInTheDocument();
  });

  // 两头的键要禁用,**不是回绕**:让子从 0 按 `−` 绕到 9 子,是把一次误触变成
  // 一局完全不同的棋 —— 而这一组标着「开局后不可改」。
  it('档位轨两头到底就禁用', () => {
    renderPage('free');
    const handicap = within(screen.getByTestId('setup-handicap'));
    expect(handicap.getByRole('button', { name: '少让一子' })).toBeDisabled();   // 默认 0 子
    expect(handicap.getByRole('button', { name: '多让一子' })).toBeEnabled();
  });

  it('Start button is present without scrolling (rendered, not gated behind overflow)', () => {
    renderPage('free');
    expect(screen.getByRole('button', { name: /开始对局|start game/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /返回对弈|back/i })).toBeInTheDocument();
  });
});

describe('AiSetupPage — 升降级挡局面板', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mockNavigate.mockReset();
    endRanked.mockReset();
    retrySettlement.mockReset();
    applyBlockingSync.mockReset();
    retryRanked.mockReset();
    withBlocking(null);
  });

  it('另一台设备在下的时候，右栏整个换成挡局面板，开始按钮不在了', () => {
    // 从前这块屏根本没有这一格:那些设置照常摆着、开始按钮照常可点,点下去才被服务端
    // 一个 409 顶回来。设置一个都用不上却摆在那里,是在暗示「改一改就能开局」。
    withBlocking(blockingGame());
    renderPage('ranked');

    expect(screen.getByTestId('kiosk-ladder-blocking-panel')).toBeInTheDocument();
    // 「正在进行」是云端猜不出来的:那台机器可能已经下完、结果卡在它自己的发送队列里,
    // 而云端只知道预约还在。换成两种情形下都真的说法。
    expect(screen.getByText('这一局在你的另一台设备上，还没了结。')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/正在进行|还没下完/);
    expect(screen.queryByRole('button', { name: /开始计分局/ })).not.toBeInTheDocument();
    // 「设置表单整个不在」用**下拉控件**当判据,不用「我执」那个标签 ——
    // 重设计之后挡局面板自己有一格事实也叫「我执」(对手档位/我执/状态/同步),
    // 拿标签文本判断会撞上它,红在一个不存在的缺陷上。下拉是设置表单独有的。
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    // 这一格两端都不在本机,没有可继续的棋盘。
    expect(screen.queryByRole('button', { name: '继续对局' })).not.toBeInTheDocument();
  });

  it.each([
    ['other_device', undefined, true],
    ['unknown', undefined, true],
    ['current_device', undefined, true],
    ['current_device', 'live-session', false],
    ['unknown', 'live-session', false],
  ] as const)(
    '那一局可能其实已经下完 —— ownership=%s session=%s 披不披露这条代价',
    async (ownership, session_id, discloses) => {
      // **这条代价消不掉,只能说出来。** 那一局可能已经下完、结果还卡在某台自己的发送队列里,
      // 而云端**看不见任何一台设备的队列**,所以照样报 `active`。用户在这里按认输,那边补交时
      // 命中墓碑 —— 一局可能是胜的棋被判负永久顶掉。守卫 2 挡不住这一格:它只看本机 outbox。
      //
      // ⚠️ **这条测试反转过一次。** 前一版的分叉轴是 `ownership`,`current_device` 那格不披露,
      // 理由是「本机若真下完了,状态会是 `pending_settlement`、根本到不了这一格」。那个推理
      // 成立,但它悄悄多用了一个前提:**本机那个进程还在**。前提不成立的那一格恰好存在 ——
      // 就是屏上那句「这一局就在这台设备上，只是本机没有它的记录」说的那一格(库被清过、
      // 盒子重启过)。那时本机既看不见进度,也可能有一份成绩压在自己队列里没送出去。
      //
      // 所以分叉轴换成 `session_id`:**这个节点此刻握不握着那个会话**。握着 ⇒ 进度看得见 ⇒
      // 「还没下完」是查出来的;握不着 ⇒ 一律披露。位置不再参与这个判断,它只回答「在哪」。
      const user = userEvent.setup();
      withBlocking(blockingGame({ state: 'active', ownership, session_id }));
      renderPage('ranked');

      await user.click(screen.getByRole('button', { name: '认输那一局，在这里开新局' }));
      const disclosure = /真实结果会被顶掉|结果会被这一场负顶掉/;
      if (discloses) {
        expect(document.body.textContent).toMatch(disclosure);
        // 而且不许再说「正在进行 / 还没下完」—— 没握着会话就不知道棋下没下完。
        expect(document.body.textContent).not.toMatch(/正在进行|还没下完/);
      } else {
        expect(document.body.textContent).not.toMatch(disclosure);
        // 握着会话那一格反过来:说得出「没下完」,因为它确实知道。
        expect(document.body.textContent).toMatch(/没有下完|尚未结束/);
      }
    },
  );

  it('从没开起来的那一格：说的是让掉，整块屏一个「记为本局负」都没有', async () => {
    // 与 galaxy 那块屏同一条硬要求(CLAUDE.md「状态必须诚实」):`reserved` 让掉**什么都不记**,
    // 后端一行账本都不会写。往贵了说会让用户以为自己必须先输一场,或者干等 5 分钟自动回收。
    const user = userEvent.setup();
    withBlocking(blockingGame({ state: 'reserved' }));
    renderPage('ranked');

    // 徽标那一格在重设计后没有了 —— 它的那句话已经由标题说出来,再摆一格就是标题的回声。
    // 所以这里改成断言标题本身。
    expect(screen.getByText('这一局登记了，但棋盘没能开起来 —— 两边都没有人在下。')).toBeInTheDocument();
    expect(screen.getByText('那一局没能开起来，让掉它不记成绩')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '让掉它，在这里开新局' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('让掉那一局？');
    // 面板 + 弹窗一起查。挨个查元素会漏掉下一个人新加的那一处。
    expect(document.body.textContent).not.toMatch(/记为本局负|计为本局负|计入升降级/);

    await user.click(screen.getByRole('button', { name: '确认让掉' }));
    await waitFor(() => expect(endRanked).toHaveBeenCalledWith('occupied-game', 'test-token'));
  });

  it('守卫 2：站在有在途结算的这台盒子前，先给的是「立即重试」，不是认输', async () => {
    // 四家共同约定的守卫 2。云端只知道「成绩还没到」,它无从知道是在排队、在退避、
    // 试完了还是被拒收 —— 而那恰好是用户唯一想问的事,答案只在这台机器的 outbox 里。
    // 少了这一格,用户能做的就只剩认输,而认输是**放弃**那一局真实的成绩。
    const user = userEvent.setup();
    withBlocking(blockingGame({
      state: 'pending_settlement', ownership: 'current_device',
      sync: {
        state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 18,
        last_http_status: null, last_error: null,
      },
    }));
    retrySettlement.mockResolvedValue({ game_id: 'occupied-game', sync: { state: 'sending', attempt: 3, max_attempts: 5, next_attempt_in_seconds: null, last_http_status: null, last_error: null } });
    renderPage('ranked');

    // 那一行说的是 outbox 的实况,不是一句没有信息的「同步中」。
    expect(screen.getByTestId('kiosk-ladder-sync-line')).toHaveTextContent('重试 2/5');

    const retryButton = screen.getByRole('button', { name: '立即重试' });
    const resignButton = screen.getByRole('button', { name: '认输那一局，在这里开新局' });
    // 「先给出」不是修辞:DOM 顺序决定了触屏上先看到哪一个。
    expect(retryButton.compareDocumentPosition(resignButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    await user.click(retryButton);
    await waitFor(() => expect(retrySettlement).toHaveBeenCalledWith('occupied-game', 'test-token'));
    // 没送成:就地贴上 outbox 刚给的状态,**不去打云端**。`/status` 在盒子上是转发到云端的,
    // 断网即 503,而一失败整块面板就换成「加载失败」—— 那正是这个按钮存在的场景。
    await waitFor(() => expect(applyBlockingSync).toHaveBeenCalledWith('occupied-game', expect.objectContaining({ state: 'sending' })));
    expect(retryRanked).not.toHaveBeenCalled();
  });

  it('云端在事实上拒收的那一份，不给重试按钮 —— 按不出结果的按钮比不给更坏', () => {
    withBlocking(blockingGame({
      state: 'pending_settlement', ownership: 'current_device',
      sync: {
        state: 'refused', attempt: 1, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 422, last_error: 'HTTP 422: rung mismatch',
      },
    }));
    renderPage('ranked');

    expect(screen.queryByRole('button', { name: '立即重试' })).not.toBeInTheDocument();
    expect(screen.getByTestId('kiosk-ladder-sync-line'))
      .toHaveTextContent('云端拒收了这一局的成绩，再试也是同一个答复。');
    expect(document.body.textContent).not.toMatch(/HTTP\s*4\d\d/);
    // 而价钱仍然是同一个:这一格有棋盘,认输就是记一负。
    expect(screen.getByText('那一局会记为本局负，并计入升降级')).toBeInTheDocument();
  });

  it('本机还接得回来的那一局，给的是「继续对局」并走升降级的对局路由', async () => {
    const user = userEvent.setup();
    withBlocking(blockingGame({
      state: 'active', ownership: 'current_device', session_id: 'occupied-session',
    }));
    renderPage('ranked');

    await user.click(screen.getByRole('button', { name: '继续对局' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/game/occupied-session');
  });

  it.each([
    ['reserved', '让掉它，在这里开新局'],
    ['active', '认输那一局，在这里开新局'],
    ['pending_settlement', '认输那一局，在这里开新局'],
  ] as const)('屏的那一半：%s 这一格按钮按得下，而且真的发出去', async (state, label) => {
    // 这条和后端那条 `test_the_end_gate_is_open_in_every_state_a_blocking_game_can_be_in`
    // 合起来才是一条断言:**屏和闸必须给同一个答案。** 分开写是因为它们住在两个语言里,
    // 而分开的正是会漂的地方 —— 另一条赛道拿掉一道闸时只拿掉了端点那一半,读路径还在按
    // 旧判据回答「现在不能」,屏上写着「还要等 5 分钟」而端点当场就受理。
    //
    // 注意这里**不断言任何秒数、任何倒计时**:那正是拿掉闸时唯一会漏掉的东西。
    const user = userEvent.setup();
    withBlocking(blockingGame({
      state,
      ownership: 'current_device',
      ...(state === 'pending_settlement'
        ? { sync: { state: 'waiting', attempt: 1, max_attempts: 5, next_attempt_in_seconds: 30, last_http_status: null, last_error: null } }
        : {}),
    }));
    endRanked.mockResolvedValue({ state: 'settled', game_id: 'occupied-game', receipt: { counted: true, reason: null } });
    renderPage('ranked');

    const button = screen.getByRole('button', { name: label });
    expect(button).toBeEnabled();
    await user.click(button);
    await user.click(screen.getByRole('button', { name: state === 'reserved' ? '确认让掉' : '确认认输' }));
    await waitFor(() => expect(endRanked).toHaveBeenCalledWith('occupied-game', 'test-token'));
  });

  it('守卫 2 的边界：重试用尽那一格，认输**不许**因此被关掉', async () => {
    // 守卫 2 是「优先摆出立即重试」,**不是「关掉认输」**。原始产品要求是每个死锁都必须
    // 有诚实出口:`exhausted` 意味着网络还坏着、成绩还救得回来,所以重试仍然给;但用户
    // 要是在这台机器前决定不等了,他必须走得掉 —— 否则这台盒子上他什么都做不了。
    //
    // 四条赛道里有三条各自独立地写出过「有在途结算就拦掉认输」这同一个死锁。它不是疏忽,
    // 是那个正当理由自带的陷阱:**拒绝要看有没有出口,不看理由多正当。**
    const user = userEvent.setup();
    withBlocking(blockingGame({
      state: 'pending_settlement', ownership: 'current_device',
      sync: {
        state: 'exhausted', attempt: 5, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: null, last_error: 'connection refused',
      },
    }));
    endRanked.mockResolvedValue({ state: 'settled', game_id: 'occupied-game', receipt: { counted: true, reason: null } });
    renderPage('ranked');

    // 两条出路同时在,而且重试排在前面。
    expect(screen.getByRole('button', { name: '立即重试' })).toBeEnabled();
    const resign = screen.getByRole('button', { name: '认输那一局，在这里开新局' });
    expect(resign).toBeEnabled();

    await user.click(resign);
    await user.click(screen.getByRole('button', { name: '确认认输' }));
    await waitFor(() => expect(endRanked).toHaveBeenCalledWith('occupied-game', 'test-token'));
  });

  it('连按两次「让掉」：第二次的 404 不许在屏上变成失败', async () => {
    // 让掉**不留墓碑**(它按定义什么都不记),所以「再按一次」只能靠把 404 认成成功来收尾。
    // 这条依赖是承重的 —— 后端那条 `test_pressing_end_twice_...` 钉住 404 真的会发生,
    // 这条钉住屏上不把它说成失败。
    const user = userEvent.setup();
    withBlocking(blockingGame({ state: 'reserved' }));
    endRanked
      .mockResolvedValueOnce({ state: 'released', game_id: 'occupied-game', counted: false })
      .mockRejectedValueOnce(new MockAiLadderApiError(404, 'not found'));
    renderPage('ranked');

    for (const _pass of [0, 1]) {
      await user.click(screen.getByRole('button', { name: '让掉它，在这里开新局' }));
      await user.click(screen.getByRole('button', { name: '确认让掉' }));
      // 弹窗关闭期间 MUI 会给 app root 挂 aria-hidden,面板此刻对查询是不可见的 ——
      // 不等它退场,第二次就会在一屋子 presentation 节点里找按钮。
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    }

    await waitFor(() => expect(endRanked).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('结束对局失败，请重试')).not.toBeInTheDocument();
  });

  it('结束请求打回 404 时说的是「已经没了」，不是「失败了」', async () => {
    // 那一局多半是原盒子刚把结果送到,或者用户重复按了一次。说成失败会让他在一个
    // 已经放开的账号上继续按 —— 而让掉那条路**没有账本当墓碑**,靠的就是这一条。
    const user = userEvent.setup();
    withBlocking(blockingGame({ state: 'reserved' }));
    endRanked.mockRejectedValue(new MockAiLadderApiError(404, 'not found'));
    renderPage('ranked');

    await user.click(screen.getByRole('button', { name: '让掉它，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认让掉' }));

    await waitFor(() => expect(retryRanked).toHaveBeenCalled());
    expect(screen.queryByText('结束对局失败，请重试')).not.toBeInTheDocument();
  });
});
