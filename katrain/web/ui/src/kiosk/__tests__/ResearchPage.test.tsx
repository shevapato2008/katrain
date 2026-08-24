import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
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

vi.mock('../context/ImmersiveContext', () => ({
  useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }),
}));

const { authState } = vi.hoisted(() => ({ authState: { current: { token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() } as any } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => authState.current }));

vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { get: vi.fn(), list: vi.fn() } }));

vi.mock('../../api', () => ({
  API: {
    quickAnalyze: vi.fn(),
    analysisScan: vi.fn().mockResolvedValue({}),
    analysisProgress: vi.fn(),
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

function buildGameState(overrides: Partial<GameState> = {}): GameState {
  return {
    game_id: 'test-game', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
    current_node_id: 0, current_node_index: 0,
    history: [{ node_id: 0, score: 0, winrate: 0.5 }],
    player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 },
    analysis: { winrate: 0.632, score: 3.5, moves: [] },
    commentary: '', is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [],
    players_info: {
      B: { player_type: 'human', player_subtype: '', name: 'fan', calculated_rank: null, periods_used: 0, main_time_used: 0 },
      W: { player_type: 'ai', player_subtype: 'katago', name: 'KataGo', calculated_rank: null, periods_used: 0, main_time_used: 0 },
    },
    note: '',
    ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
    language: 'zh',
    ...overrides,
  };
}

const renderPage = (entry = '/kiosk/research') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/kiosk/research" element={<ResearchPage />} />
          <Route path="/kiosk/play" element={<div>对弈屏</div>} />
          <Route path="/kiosk/play/pvp/history" element={<div>对局历史屏</div>} />
          <Route path="/kiosk/report/:taskId" element={<div>报告屏</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

/** 表是**防抖 400ms** 之后才有的 —— 每条要看表的用例都得等它。 */
const table = () => screen.findByTestId('research-ai', {}, { timeout: 2000 });
const rows = async () => within(await table()).findAllByTestId('research-ai-row');
const actions = () => screen.getByTestId('research-actions');

describe('屏 21 研究', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateSession.mockResolvedValue('session-123');
    mockGameState = null;
    vi.mocked(API.quickAnalyze).mockResolvedValue(quick());
    vi.mocked(API.analysisScan).mockResolvedValue({});
    authState.current = { token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() };
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

  it('表:首行标绿、负目差标红、推荐度按 visits 占比', async () => {
    renderPage();
    const r = await rows();
    expect(r).toHaveLength(3);

    const cells = (i: number) => Array.from(r[i].querySelectorAll('span'));
    expect(cells(0)[0]).toHaveTextContent('R11');
    expect(cells(0)[0].className).toContain('best');
    // 61 / (61+18+11) = 67.7 → 68%
    expect(cells(0)[1]).toHaveTextContent('68%');
    expect(cells(0)[2]).toHaveTextContent('+1.8');
    expect(cells(0)[3]).toHaveTextContent('54.2%');

    // Q6 的目差是负的 ⇒ 那一格走 .neg
    expect(cells(2)[2]).toHaveTextContent('−0.9');
    expect(cells(2)[2].className).toContain('neg');
  });

  /**
   * 🔴 状态诚实。`current_winrate` 那一类「真的 50%」和「没有这个数」同值的坑,
   * 屏 18 已经判过一次:**算不出来写「—」,不写 50%**。
   */
  it('还没有数的时候折叠头写「—」,不写一个 50%', async () => {
    vi.mocked(API.quickAnalyze).mockImplementation(() => new Promise(() => {})); // 永不 resolve
    renderPage();
    await screen.findByTestId('research-ai-pending', {}, { timeout: 2000 });
    expect(await table()).toHaveTextContent('—');
    expect(screen.queryByText(/50\.0%/)).toBeNull();
  });

  it('算失败:说出服务端那句话,不把上一手的数留着假装是这一手的', async () => {
    vi.mocked(API.quickAnalyze).mockRejectedValue(new Error('引擎没起来'));
    renderPage();
    const err = await screen.findByTestId('research-ai-error', {}, { timeout: 2000 });
    expect(err).toHaveTextContent('引擎没起来');
    expect(within(await table()).queryAllByTestId('research-ai-row')).toHaveLength(0);
  });

  it('AI 一个候选都没给:说这句话,不画一张空表', async () => {
    vi.mocked(API.quickAnalyze).mockResolvedValue(quick([]));
    renderPage();
    expect(await screen.findByTestId('research-ai-none', {}, { timeout: 2000 }))
      .toHaveTextContent('没有给出候选');
  });

  // ── 全局分析 ───────────────────────────────────────────────────────────────

  /**
   * 🔴 弹层里**只许写算得出来的数**。「大概几分钟」需要一个开跑前没人校准过的每手速率
   * —— 那个数只能编。真正的「预计剩余」在扫描中由两次采样实测得出。
   */
  it('全局分析先弹确认,里面只有手数和 500,没有「大概几分钟」', async () => {
    renderPage();
    await userEvent.click(within(actions()).getByRole('button', { name: '全局分析' }));
    const dlg = screen.getByTestId('research-scan-confirm');
    expect(dlg).toHaveTextContent('每手算 500 次');
    expect(dlg).toHaveTextContent('可以随时取消');
    expect(dlg.textContent).not.toMatch(/分钟|大约|大概/);
    // 弹确认 ≠ 已经开跑
    expect(mockCreateSession).not.toHaveBeenCalled();
  });

  it('确认之后才建会话并以 500 visits 起扫', async () => {
    renderPage();
    await userEvent.click(within(actions()).getByRole('button', { name: '全局分析' }));
    await userEvent.click(screen.getByRole('button', { name: '开始算' }));
    await waitFor(() => expect(mockCreateSession).toHaveBeenCalled());
    await waitFor(() => expect(API.analysisScan).toHaveBeenCalledWith('session-123', 500));
  });

  /**
   * 🔴 扫描中分段和提示行**不渲染**,不是「渲染出来全部灰掉」——
   * `KioskOptSeg` 的契约写死「永远至少留一段能选」,全灰是违约。
   * 而「保存」**不跟着灰**:它只读,存下当前这份谱没有任何危险。
   */
  it('扫描中:编辑工具整组撤走,第 5 颗变取消,但「保存」不灰', async () => {
    vi.mocked(API.analysisProgress).mockResolvedValue({ analyzed: 3, total: 9 });
    renderPage();
    await userEvent.click(within(actions()).getByRole('button', { name: '全局分析' }));
    await userEvent.click(screen.getByRole('button', { name: '开始算' }));

    await waitFor(() => expect(screen.queryByTestId('research-tools')).toBeNull());
    expect(screen.queryByTestId('research-hint')).toBeNull();
    expect(within(actions()).getByRole('button', { name: '取消分析' })).toBeInTheDocument();
    expect(within(actions()).getByRole('button', { name: '清空' })).toBeDisabled();
    expect(within(actions()).getByRole('button', { name: '保存' })).toBeEnabled();
    expect(await screen.findByTestId('research-scan')).toHaveTextContent('已分析手数');
  });

  it('连续 5 次读不到进度才判失败,并给得出「重试分析」', async () => {
    vi.mocked(API.analysisProgress).mockRejectedValue(new Error('断了'));
    renderPage();
    await userEvent.click(within(actions()).getByRole('button', { name: '全局分析' }));
    await userEvent.click(screen.getByRole('button', { name: '开始算' }));

    await waitFor(
      () => expect(within(actions()).getByRole('button', { name: '重试分析' })).toBeInTheDocument(),
      { timeout: 8000 },
    );
    expect(await screen.findByTestId('research-ai-error')).toHaveTextContent('连续 5 次');
  }, 12000);

  it('扫完:第 5 颗变「重新分析」,表改读会话里那份 500/手', async () => {
    vi.mocked(API.analysisProgress).mockResolvedValue({ analyzed: 9, total: 9 });
    mockGameState = buildGameState({
      analysis: { winrate: 0.7, score: 5, moves: [{ move: 'D4', coords: null, winrate: 0.7, scoreLead: 5, scoreLoss: 0, visits: 500, psv: 500 }] } as any,
    });
    renderPage();
    await userEvent.click(within(actions()).getByRole('button', { name: '全局分析' }));
    await userEvent.click(screen.getByRole('button', { name: '开始算' }));

    // 进度是 1s 一轮的,`waitFor` 默认 1000ms 正好卡在边界上 —— 给够。
    await waitFor(
      () => expect(within(actions()).getByRole('button', { name: '重新分析' })).toBeInTheDocument(),
      { timeout: 4000 },
    );
    const r = await rows();
    expect(r).toHaveLength(1);
    expect(r[0]).toHaveTextContent('D4');
  });

  // ── 轻重:清空要确认,停一手不要 ────────────────────────────────────────────

  /**
   * 🔴 上一版轻重是**倒置**的:`onClear` 一点就把整盘擦掉、没有任何确认,
   * 而「停一手」这个上一手就能撤销的动作反倒弹确认框。这一版扳回来。
   */
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

  it('领地是页控条右端那颗页级图标键,有按下态', async () => {
    renderPage();
    const bar = screen.getByTestId('research-pagebar');
    const btn = within(bar).getByRole('button', { name: '领地' });
    expect(btn).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(btn);
    expect(within(bar).getByRole('button', { name: '领地' })).toHaveAttribute('aria-pressed', 'true');
  });

  // ── 返回:跟着入口走 ───────────────────────────────────────────────────────

  /**
   * 🔴 稿子把返回键写死成「← 棋谱」,可这一屏有四个入口、回去的地方各不相同,
   * 而屏 20 和对局历史两条的 URL 形状完全一样(都是 `?user_game_id=`)、反推不出来。
   * ⇒ 由 `?from=` 说了算,目标路径查前端常量表(**不收路径参数**,那是个能注入的洞)。
   */
  it('?from=history 回对局历史', async () => {
    renderPage('/kiosk/research?from=history');
    await userEvent.click(within(screen.getByTestId('research-pagebar')).getByRole('button', { name: /对局历史/ }));
    expect(screen.getByText('对局历史屏')).toBeInTheDocument();
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
  it('?kifu_id&analyze=1:把刚取到的 SGF 直接串进 createSession,并写出出处', async () => {
    vi.mocked(KifuAPI.getAlbum).mockResolvedValue({
      id: 7, player_black: '柯洁', player_white: '申真谞', black_rank: null, white_rank: null,
      event: 'LG杯', result: null, rules: 'chinese', date_played: '2026-06-15', komi: 7.5,
      handicap: 0, board_size: 19, round_name: '决赛', move_count: 2,
      place: null, source: null, sgf_content: '(;GM[1]FF[4]SZ[19];B[pd];W[dp])',
    } as any);

    renderPage('/kiosk/research?kifu_id=7&analyze=1&from=kifu');

    await waitFor(() => expect(mockCreateSession).toHaveBeenCalled());
    const [sgfArg] = mockCreateSession.mock.calls[0];
    expect(sgfArg).toContain('B[pd]');

    const bar = screen.getByTestId('research-pagebar');
    expect(bar).toHaveTextContent('棋谱库');
    expect(bar).toHaveTextContent('LG杯 · 决赛');
    expect(bar).not.toHaveTextContent('undefined');
  });

  it('token 是 null 时照样发 quickAnalyze(严格 kiosk 走的是 cookie)', async () => {
    authState.current = { token: null, isAuthenticated: false, user: null, login: vi.fn(), logout: vi.fn() };
    renderPage();
    await waitFor(() => expect(API.quickAnalyze).toHaveBeenCalled(), { timeout: 2000 });
    expect(vi.mocked(API.quickAnalyze).mock.calls[0][1]).toBeUndefined();
  });
});
