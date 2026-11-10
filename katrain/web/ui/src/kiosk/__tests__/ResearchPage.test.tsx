import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { writeAudioPref } from '../../utils/audioPrefs';
import type { GameState } from '../../api';

/**
 * 屏 21 研究。**2026-08-24 整份重写口径。**
 *
 * 上一版 11 条里 9 条断言的是这一轮删掉的东西:`对局信息` 两个输入框、`编辑工具` 那 12 颗
 * 药丸键、底部钉住的「开始研究」大 CTA、以及**四路 return 换整屏**这个结构本身。
 * 那 9 条不是「过期了要删」,是**换口径**:同一件事在新结构里换了个说法 ——
 * 「进没进分析中那个视图」变成「右栏这一条的第 5 颗键变成了什么、分段还在不在」。
 *
 * 布局事实一律不在这儿断言(jsdom 没有布局引擎):
 * 「表能不能滚」「右栏 516 摆不摆得下」归 `tests/kiosk-shell-geometry.spec.ts`。
 */

const { authState } = vi.hoisted(() => ({ authState: { current: { token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() } as any } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => authState.current }));

vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { get: vi.fn(), list: vi.fn(), create: (...args: unknown[]) => reportAction.save(...args) } }));

vi.mock('../../api', () => ({
  API: {
    quickAnalyze: vi.fn(),
    analysisScan: vi.fn().mockResolvedValue({}),
    analysisProgress: vi.fn(),
  },
}));

/**
 * 盘换成一个能把 `ownership` 读出来的桩 —— 真 `LiveBoard` 是 canvas,
 * 在 jsdom 里画不出东西,而这几条要问的正是「这一帧到底给不给它那张地图」。
 */
vi.mock('../../components/live/LiveBoard', () => ({
  default: (props: Record<string, unknown>) => {
    const click = props.onIntersectionClick as ((x: number, y: number) => void) | undefined;
    return (
      <div data-testid="research-board-svg" data-ownership={props.ownership ? 'grid' : 'none'}>
        <button onClick={() => click?.(3, 3)}>点 D4</button>
      </div>
    );
  },
}));

vi.mock('../../api/kifuApi', () => ({
  KifuAPI: { getAlbum: vi.fn(), getAlbums: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 }) },
}));

const mockCreateSession = vi.fn().mockResolvedValue('session-123');
const mockDestroySession = vi.fn();
const mockOnNavigate = vi.fn();
let mockGameState: GameState | null = null;

vi.mock('../../hooks/useResearchSession', () => ({
  useResearchSession: () => ({
    sessionId: 'session-123',
    gameState: mockGameState,
    error: null,
    isConnected: true,
    createSession: mockCreateSession,
    destroySession: mockDestroySession,
    onMove: vi.fn(),
    onPass: vi.fn(),
    onNavigate: mockOnNavigate,
    handleNavAction: vi.fn(),
    toggleHints: vi.fn(),
    toggleOwnership: vi.fn(),
    toggleMoveNumbers: vi.fn(),
    toggleCoordinates: vi.fn(),
    analyzeGame: vi.fn(),
    analysisScan: vi.fn(),
  }),
}));


const paidApi = vi.hoisted(() => ({ getCatalog: vi.fn(), createQuote: vi.fn(), createPosition: vi.fn() }));
const reportAction = vi.hoisted(() => ({ create: vi.fn(), save: vi.fn() }));
vi.mock('../../api/membershipApi', () => ({ membershipApi: paidApi }));
vi.mock('../../features/report/useReportTasks', () => ({ useReportTasks: () => ({ createReport: reportAction.create, pendingQuote: null, quoteBusy: false, error: null }) }));

import ResearchPage from '../pages/ResearchPage';
import { API } from '../../api';
import { KifuAPI } from '../../api/kifuApi';

/** KataGo 的 `winrate`/`scoreLead` 是**黑方视角**。空盘轮黑走 ⇒ 上屏不翻转。 */
const MOVE_INFOS = [
  { move: 'R11', visits: 61, winrate: 0.542, scoreLead: 1.8 },
  { move: 'C7', visits: 18, winrate: 0.516, scoreLead: 0.4 },
  { move: 'Q6', visits: 11, winrate: 0.491, scoreLead: -0.9 },
];

const quick = (moveInfos: unknown[] = MOVE_INFOS) => ({ turnInfos: [{ moveInfos, ownership: null }] });

const renderPage = (entry = '/kiosk/research') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/kiosk/research" element={<ResearchPage />} />
          <Route path="/kiosk/play" element={<div>对弈屏</div>} />
          <Route path="/kiosk/report" element={<div>复盘屏</div>} />
          <Route path="/kiosk/report/:taskId" element={<div>报告屏</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

/** 表是**防抖 400ms** 之后才有的 —— 每条要看表的用例都得等它。 */
const actions = () => screen.getByTestId('research-actions');

describe('屏 21 研究', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    writeAudioPref('sfx', true);
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
    mockCreateSession.mockResolvedValue('session-123');
    mockGameState = null;
    paidApi.getCatalog.mockResolvedValue({ membership_mode: 'enabled', capabilities: { quotes: true, positions: true } });
    paidApi.createQuote.mockResolvedValue({ token: 'signed', kind: 'position', source: 'membership', profile: 'normal', wallet_max_display_points: '0.01' });
    paidApi.createPosition.mockResolvedValue({ state: 'succeeded', operation_id: 'op1', result: { ownership: Array(361).fill(0.2), moves: MOVE_INFOS.map(m => ({ ...m, score_lead: m.scoreLead })) } });
    reportAction.save.mockResolvedValue({ id: 'owned-game', move_count: 1 });
    reportAction.create.mockResolvedValue(null);
    vi.mocked(API.quickAnalyze).mockResolvedValue(quick());
    vi.mocked(API.analysisScan).mockResolvedValue({});
    authState.current = { identityKey: 'person-a', status: 'authenticated', token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() };
  });

  it('sounds once after an accepted placement and keeps delete, pass, and the opening silent', async () => {
    renderPage();
    expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '点 D4' }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: '停一手' }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
    await userEvent.click(within(screen.getByTestId('research-tools')).getByRole('button', { name: '删除' }));
    await userEvent.click(screen.getByRole('button', { name: '点 D4' }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
  });

  it('keeps imported moves silent and sounds only on explicit real-stone navigation', async () => {
    vi.mocked(KifuAPI.getAlbum).mockResolvedValue({ id: 9, sgf_content: '(;SZ[19];B[dd];W[pp];B[])' } as any);
    renderPage('/kiosk/research?kifu_id=9');
    await waitFor(() => expect(screen.getByTestId('research-pagebar')).toHaveTextContent('第 3 手'));
    expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '上一手' }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: '下一手' }));
    await userEvent.click(screen.getByRole('button', { name: '回到开局' }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
  });

  // ── 编辑工具:四段互斥,不是一排开关 ────────────────────────────────────────

  it('编辑工具是四段互斥的分段控件,进屏「交替」按下', () => {
    renderPage();
    const seg = screen.getByTestId('research-tools');
    expect(within(seg).getAllByRole('button')).toHaveLength(4);
    ['交替', '摆黑', '摆白', '删除'].forEach((label) => {
      expect(within(seg).getByRole('button', { name: label })).toBeInTheDocument();
    });
    // 分段控件按定义总有一段按下 —— 上一版那个「两组都 null」的第五态没有了。
    expect(within(seg).getByRole('button', { name: '交替' })).toHaveAttribute('aria-pressed', 'true');
  });

  /**
   * 🔴 `移动` 删掉是因为它**在触摸屏上是坏的**,不是「用得少」:选中态存在一个 `useRef` 里,
   * ref 不触发重渲染 ⇒ 点第一下屏上零反馈,点第二下那颗子瞬移。
   * `手数`/`建议` 一并撤走(前者把操作顺序画成棋谱,后者被常亮的推荐点取代)。
   */
  it('移动 / 手数 / 建议 三颗都不在了', () => {
    renderPage();
    ['移动', '手数', '建议'].forEach((gone) => {
      expect(screen.queryByRole('button', { name: gone })).toBeNull();
    });
  });

  it('提示行写的是当前工具和规则,不是稿子那句讲设计的话', async () => {
    renderPage();
    const hint = screen.getByTestId('research-hint');
    expect(hint).toHaveTextContent('交替');
    expect(hint).toHaveTextContent('中国规则');
    expect(hint).toHaveTextContent('贴目 7.5');
    // 稿子原句收进了代码注释,不上屏
    expect(hint).not.toHaveTextContent('互斥');

    // 换工具,这一行跟着换
    await userEvent.click(within(screen.getByTestId('research-tools')).getByRole('button', { name: '删除' }));
    expect(screen.getByTestId('research-hint')).toHaveTextContent('删除');
  });

  // ── AI 推荐表 ──────────────────────────────────────────────────────────────

  it('清空要确认,停一手不要', async () => {
    renderPage();
    await userEvent.click(within(actions()).getByRole('button', { name: '清空' }));
    expect(screen.getByTestId('research-clear-confirm')).toHaveTextContent('撤不回来');

    await userEvent.click(within(screen.getByTestId('research-clear-confirm')).getByRole('button', { name: '取消' }));
    expect(screen.queryByTestId('research-clear-confirm')).toBeNull();

    await userEvent.click(within(actions()).getByRole('button', { name: '停一手' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  // ── 领地在页控条那一颗键上 ──────────────────────────────────────────────────

  it('?from=report 回复盘', async () => {
    renderPage('/kiosk/research?from=report');
    await userEvent.click(within(screen.getByTestId('research-pagebar')).getByRole('button', { name: /复盘/ }));
    expect(screen.getByText('复盘屏')).toBeInTheDocument();
  });

  /**
   * 表里认不得的 `from=` 一律退回对弈 —— 包括 2026-08-25 删掉的那条 `history`
   * (对局历史是 27 屏改造之前的屏,它的活由屏 19 复盘接了,自己那条路由**没有入口**)。
   * 退回去而不是崩,是因为 `?from=` 来自 URL:**手输一个不存在的值不该把这一屏打白**。
   */
  it('认不得的 from(含已删掉的 history)退回对弈,副标题整行不渲染', async () => {
    renderPage('/kiosk/research?from=history');
    const bar = screen.getByTestId('research-pagebar');
    expect(bar.querySelector('.kiosk-pagebar__sub')).toBeNull();
    await userEvent.click(within(bar).getByRole('button', { name: /对弈/ }));
    expect(screen.getByText('对弈屏')).toBeInTheDocument();
  });

  it('没有 from(手输 URL / 刷新):回对弈,而且副标题整行不渲染 —— 不许编一个出处', async () => {
    renderPage();
    const bar = screen.getByTestId('research-pagebar');
    expect(bar.querySelector('.kiosk-pagebar__sub')).toBeNull();
    await userEvent.click(within(bar).getByRole('button', { name: /对弈/ }));
    expect(screen.getByText('对弈屏')).toBeInTheDocument();
  });

  // ── 深链 ───────────────────────────────────────────────────────────────────

  /**
   * 🔴 galaxy 那个陈旧闭包 bug(`ResearchPage.tsx:187-199`):在同一段异步续体里从 `board`
   * 反推 SGF,读到的是 `loadFromSGF` 之前的空盘。这里把**刚取到的** `sgf_content`
   * 直接串进 `createSession`,所以断言它收到的不是 undefined。
   */

  it('quotes before consumption and reuses one result for territory and hints', async () => {
    renderPage();
    expect(API.quickAnalyze).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '领地' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('最多 0.01 积分');
    expect(paidApi.createPosition).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole('button', { name: '取消' }));
    expect(paidApi.createPosition).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '支招' }));
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '确认并开始' }));
    await waitFor(() => expect(screen.getAllByTestId('ai-recommend-row')).toHaveLength(3));
    await userEvent.click(screen.getByRole('button', { name: '领地' }));
    expect(screen.getByTestId('research-board-svg')).toHaveAttribute('data-ownership', 'grid');
    expect(paidApi.createPosition).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: '点 D4' }));
    expect(screen.getByTestId('research-board-svg')).toHaveAttribute('data-ownership', 'none');
    expect(screen.queryAllByTestId('ai-recommend-row')).toHaveLength(0);
    expect(paidApi.createPosition).toHaveBeenCalledTimes(1);
  });
  it('creates an owned full SGF before entering the report quote journey', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: '点 D4' }));
    await userEvent.click(screen.getByRole('button', { name: '创建复盘报告' }));
    await waitFor(() => expect(reportAction.create).toHaveBeenCalledWith({ userGameId: 'owned-game', totalMoves: 1 }));
    expect(reportAction.save.mock.calls[0][1].sgf_content).toContain('B[dp]');
    expect(API.analysisScan).not.toHaveBeenCalled();
  });
});
