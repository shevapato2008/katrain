import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../api';
import GamePage from './GamePage';

const mocks = vi.hoisted(() => ({
  getStatus: vi.fn(), getGameStatus: vi.fn(), onMove: vi.fn(), handleAction: vi.fn(), railToggle: vi.fn(), gameState: null as GameState | null,
}));
vi.mock('../../features/aiLadder/api', () => ({
  getAiLadderStatus: mocks.getStatus,
  getAiLadderGameStatus: mocks.getGameStatus,
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: undefined, user: { username: 'fan' } }) }));
vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_en: string, zh: string) => zh }) }));
vi.mock('../context/GameNavigationContext', () => ({ useGameNavigation: () => ({ registerActiveGame: vi.fn(), unregisterActiveGame: vi.fn() }) }));
vi.mock('../../components/Board', () => ({ default: ({ onMove, gameState }: { onMove: (x: number, y: number) => void; gameState: GameState }) => (
  <button disabled={Boolean(gameState.end_result)} onClick={() => onMove(3, 3)}>board</button>
) }));
vi.mock('../components/game/RightSidebarPanel', () => ({
  default: ({ embedded, gameState, onAction, onToggleChange }: { embedded?: boolean; gameState: GameState; onAction: (action: string) => void; onToggleChange: (setting: string) => void }) => (
    <div data-testid="game-controls" data-embedded={String(Boolean(embedded))} data-end-result={String(gameState.end_result)}>
      <button disabled={Boolean(gameState.end_result)} onClick={() => onAction('pass')}>pass</button>
      <button onClick={() => onAction('resign')}>resign action</button>
      <button onClick={() => { mocks.railToggle(); onToggleChange('coords'); }}>toggle coords</button>
      <button onClick={() => onToggleChange('view3d')}>toggle 3d</button>
      <button onClick={() => onToggleChange('stoneDropEffect')}>toggle drop</button>
      <button onClick={() => onToggleChange('hints')}>toggle hints</button>
    </div>
  ),
  /* 翻手那六个键搬到了动作区（`board-rail-actions`，不跟着滚），
     所以这个桩件也要给出具名导出 —— 少了它页面直接渲染不出来。 */
  RightSidebarActions: ({ onAction, isGameOver }: { onAction: (action: string) => void; isGameOver: boolean }) => (
    <div data-testid="game-rail-actions" data-game-over={String(isGameOver)}>
      <button onClick={() => onAction('back')}>nav back</button>
    </div>
  ),
}));

/* 3D 棋盘是动态 import 进来的；桩件把**它实际收到的**开关回读出来。
   判据不能落在右栏那个开关自己身上 —— 它 checked 会变，下游收不收得到是另一回事
   （这正是修之前的真实状态，真运行时顺着 React fiber 量到过）。 */
vi.mock('../../components/Board3D', () => ({
  default: ({ analysisToggles }: { analysisToggles: Record<string, boolean> }) => (
    <div
      data-testid="board3d"
      data-drop={String(!!analysisToggles.stoneDropEffect)}
      data-hints={String(!!analysisToggles.hints)}
      data-ownership={String(!!analysisToggles.ownership)}
    />
  ),
}));

const rung = (value: number) => ({ rung: value, rank_name: `${value}级`, certification_status: 'certified' as const, availability: 'available' as const, route: 'server' as const });
const status = (value: number) => ({ view_state: 'ready' as const, placement_state: { phase: 'placed' as const, rung: rung(value) }, current_opponent: rung(value), recent_ranked_results: [], net_score: 0 as const, pending_settlement: false });
const gameState = {
  game_id: 'g1', board_size: [19, 19], komi: 6.5, handicap: 0, ruleset: 'japanese', current_node_id: 1,
  current_node_index: 1, history: [], player_to_move: 'B', stones: [], last_move: null,
  prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '', is_root: false, is_pass: false,
  end_result: 'B+R', children: [], ghost_stones: [], note: '', language: 'zh', game_type: 'ai_ladder_ranked',
  players_info: {
    B: { player_type: 'player:human', player_subtype: '', name: 'fan', calculated_rank: null, periods_used: 0, main_time_used: 0 },
    W: { player_type: 'player:ai', player_subtype: '', name: 'AI', calculated_rank: null, periods_used: 0, main_time_used: 0 },
  },
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
} satisfies GameState;

vi.mock('../../hooks/useGameSession', () => ({ useGameSession: () => ({
  sessionId: 's1', setSessionId: vi.fn(), gameState: mocks.gameState, setGameState: vi.fn(), error: null, onMove: mocks.onMove,
  onNavigate: vi.fn(), handleAction: mocks.handleAction, initNewSession: vi.fn(), lastLog: null, chatMessages: [], sendChat: vi.fn(),
}) }));

describe('Galaxy GamePage ranked settlement', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mocks.getStatus.mockReset();
    mocks.getGameStatus.mockReset();
    mocks.onMove.mockReset();
    mocks.handleAction.mockReset();
    mocks.railToggle.mockReset();
    mocks.gameState = gameState;
  });
  afterEach(() => vi.useRealTimers());

  /* 升降级模式下棋盘只接非分析的开关。这一条同时守两个方向：
     纯外观的「落子特效」必须**能**到棋盘（修之前到不了 —— 空按钮），
     而分析类的建议 / 领地必须**到不了**（那正是这个过滤器存在的理由）。 */
  it('passes the cosmetic stone-drop toggle to the 3D board but never the analysis toggles', async () => {
    mocks.gameState = { ...gameState, end_result: null };
    render(<MemoryRouter initialEntries={['/galaxy/play/ai/game/s1?mode=rated']}><Routes><Route path="/galaxy/play/ai/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);

    fireEvent.click(screen.getByRole('button', { name: 'toggle 3d' }));
    const board3d = await screen.findByTestId('board3d');
    expect(board3d).toHaveAttribute('data-drop', 'false');

    fireEvent.click(screen.getByRole('button', { name: 'toggle drop' }));
    await waitFor(() => expect(screen.getByTestId('board3d')).toHaveAttribute('data-drop', 'true'));

    fireEvent.click(screen.getByRole('button', { name: 'toggle hints' }));
    expect(screen.getByTestId('board3d')).toHaveAttribute('data-hints', 'false');
    expect(screen.getByTestId('board3d')).toHaveAttribute('data-ownership', 'false');
  });

  it('renders the authoritative feedback and supports cookie-only status refresh', async () => {
    sessionStorage.setItem('ai-ladder-before:s1', JSON.stringify({ identity: 'fan', status: status(18) }));
    mocks.getStatus.mockResolvedValue(status(17));
    render(<MemoryRouter initialEntries={['/galaxy/play/ai/game/s1?mode=rated']}><Routes><Route path="/galaxy/play/ai/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);
    expect(await screen.findByText('降级：17级')).toBeInTheDocument();
    const rail = screen.getByTestId('board-rail-scroll');
    expect(rail).toHaveTextContent('本局已结算');
    expect(rail).toContainElement(screen.getByRole('button', { name: '再来一局' }));
    expect(rail).toContainElement(screen.getByRole('button', { name: '返回对局' }));
    expect(mocks.getStatus).toHaveBeenCalledWith(undefined, expect.any(AbortSignal));
  });

  it('keeps the rated board clear and puts the named parent action in the right rail', () => {
    mocks.getStatus.mockResolvedValue(status(18));
    render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);

    const stage = screen.getByTestId('board-stage');
    const module = screen.getByTestId('board-rail-module');
    expect(stage).toHaveTextContent('board');
    expect(stage).not.toHaveTextContent('升降级对弈');
    expect(module).toHaveTextContent('升降级对弈');
    expect(module).toContainElement(screen.getByRole('button', { name: '返回升降级' }));
    expect(screen.getByTestId('game-controls')).toHaveAttribute('data-embedded', 'true');
  });

  it('keeps polling pending settlement every five seconds until settled', async () => {
    vi.useFakeTimers();
    try {
      mocks.gameState = { ...gameState, end_result: null };
      mocks.getGameStatus
        .mockResolvedValueOnce({ state: 'active', game_id: 'g1' })
        .mockResolvedValueOnce({ state: 'pending_settlement', game_id: 'g1' })
        .mockResolvedValueOnce({ state: 'settled', game_id: 'g1', receipt: { counted: true, reason: null } });
      render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated&game_id=g1']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);

      await act(async () => { await Promise.resolve(); await Promise.resolve(); });
      expect(mocks.getGameStatus).toHaveBeenCalledTimes(1);
      await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); await Promise.resolve(); });
      expect(screen.getByText('本局已在其他设备结束，正在结算')).toBeInTheDocument();
      await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); await Promise.resolve(); });
      expect(screen.getByText('本局已在其他设备结束，结算已完成')).toBeInTheDocument();
      expect(mocks.getGameStatus).toHaveBeenCalledTimes(3);
      await act(async () => { vi.advanceTimersByTime(10000); });
      expect(mocks.getGameStatus).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it('deduplicates an action check with polling and never re-enables after deferred settlement', async () => {
    mocks.gameState = { ...gameState, end_result: null };
    let resolveLifecycle!: (value: { state: 'settled'; game_id: string; receipt: { counted: boolean; reason: null } }) => void;
    mocks.getGameStatus.mockReturnValueOnce(new Promise((resolve) => { resolveLifecycle = resolve; }));
    render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated&game_id=g1']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(mocks.getGameStatus).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'board' }));
    expect(mocks.getGameStatus).toHaveBeenCalledTimes(1);
    resolveLifecycle({ state: 'settled', game_id: 'g1', receipt: { counted: true, reason: null } });
    expect(await screen.findByText('本局已在其他设备结束，结算已完成')).toBeInTheDocument();

    mocks.getGameStatus.mockResolvedValue({ state: 'active', game_id: 'g1' });
    fireEvent.click(screen.getByRole('button', { name: 'board' }));
    expect(mocks.getGameStatus).toHaveBeenCalledTimes(1);
    expect(mocks.onMove).not.toHaveBeenCalled();
  });

  it('rechecks authority before confirming an already-open resign dialog', async () => {
    mocks.gameState = { ...gameState, end_result: null };
    mocks.getGameStatus
      .mockResolvedValueOnce({ state: 'active', game_id: 'g1' })
      .mockResolvedValueOnce({ state: 'pending_settlement', game_id: 'g1' });
    render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated&game_id=g1']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(mocks.getGameStatus).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'resign action' }));
    fireEvent.click(screen.getByRole('button', { name: 'Resign' }));

    expect(await screen.findByText('本局已在其他设备结束，正在结算')).toBeInTheDocument();
    expect(mocks.handleAction).not.toHaveBeenCalled();
  });

  it('blocks board moves and rail actions after remote settlement without inventing a board result', async () => {
    mocks.gameState = { ...gameState, end_result: null };
    mocks.getGameStatus.mockResolvedValue({
      state: 'settled', game_id: 'g1', receipt: { counted: true, reason: null },
    });
    render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated&game_id=g1']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);
    const user = userEvent.setup();

    expect(await screen.findByText('本局已在其他设备结束，结算已完成')).toBeInTheDocument();
    expect(screen.getByTestId('game-controls')).toHaveAttribute('data-end-result', 'null');
    expect(screen.getByRole('button', { name: 'pass' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'toggle coords' })).toBeDisabled();
    expect(screen.getByTestId('ranked-board-interaction')).toHaveAttribute('aria-disabled', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'board' }));
    fireEvent.click(screen.getByRole('button', { name: 'pass' }));
    await user.click(screen.getByRole('button', { name: 'toggle coords' }));
    expect(mocks.onMove).not.toHaveBeenCalled();
    expect(mocks.handleAction).not.toHaveBeenCalled();
    expect(mocks.railToggle).not.toHaveBeenCalled();
  });

  it('checks authority immediately before a human move and keeps play alive on status errors', async () => {
    mocks.gameState = { ...gameState, end_result: null };
    mocks.getGameStatus
      .mockResolvedValueOnce({ state: 'active', game_id: 'g1' })
      .mockRejectedValueOnce(new Error('offline'));
    render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated&game_id=g1']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(mocks.getGameStatus).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'board' }));
    await waitFor(() => expect(mocks.getGameStatus).toHaveBeenCalledTimes(2));
    expect(mocks.onMove).not.toHaveBeenCalled();
    expect(screen.getByText('暂时无法确认本局状态，请重试')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'board' })).not.toBeDisabled();
  });
});

/* ── 自由对弈那半 ────────────────────────────────────────────────
 * 2026-08-23：`free` 分支从「顶栏（标题 + 退出键）+ 棋盘 / 右边 500px 面板」的老版式
 * 迁到与 `rated` **同一个** `BoardPageShell`。版式结论（右栏三档宽、三段和、棋盘方不方）
 * 由真浏览器量（`loadbearing_board_page.js`，六个棋盘页共用的那份探针，三档全过）；
 * 这里只守渲染结构 —— 判据「把它原样搬进真浏览器，还有可能失败吗」：会。
 *
 * 变异实跑：
 *   1. 模块牌标题写死成 `t('rated_play', …)`  → 「标题/返回」那条红
 *   2. `railBody` 里去掉 `isRated &&` 这个条件 → 「不渲染结算面板」那条红
 *   3. `controls(true)` 改回 `controls()`      → 「右栏是 embedded」那条红
 */
describe('Galaxy GamePage 自由对弈', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mocks.getStatus.mockReset();
    mocks.getGameStatus.mockReset();
    mocks.gameState = { ...gameState, end_result: null, game_type: 'ai' };
  });

  const renderFree = () => render(
    <MemoryRouter initialEntries={['/galaxy/play/game/s1']}>
      <Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes>
    </MemoryRouter>,
  );

  it('走的是与升降级同一个棋盘页外壳，模块牌是「自由对弈」、返回「对局」', () => {
    renderFree();
    expect(screen.getByTestId('board-page-shell')).toBeInTheDocument();
    const plate = screen.getByTestId('module-plate');
    expect(plate.querySelector('h1')).toHaveTextContent('自由对弈');
    /* 返回键去哪儿不能靠点（`useGameNavigation` 在这份桩件里没有 requestNavigation），
       改判无障碍名 —— 它由 backLabel 拼出来，同样能区分升降级和自由。 */
    expect(plate.querySelector('button[aria-label="返回对局"]')).not.toBeNull();
  });

  it('不渲染升降级的结算面板', () => {
    mocks.gameState = { ...gameState, end_result: 'B+R', game_type: 'ai' };
    renderFree();
    expect(screen.queryByText(/晋级|降级|正在读取服务器结算结果/)).toBeNull();
  });

  it('右栏面板走 embedded，且顶栏那个「退出」键不再存在', () => {
    renderFree();
    // 迁移前 free 分支传的是非 embedded 的 `controls()`（自带 500px 宽和自己的滚动）。
    expect(screen.getByTestId('game-controls')).toHaveAttribute('data-embedded', 'true');
    // 「退出」搬进右栏成了「离开对局」，顶栏那份是重复，已删。
    expect(screen.queryByRole('button', { name: '退出' })).toBeNull();
    // 翻手六键在动作区，不跟着中段滚。
    expect(screen.getByTestId('board-rail-actions')).toContainElement(screen.getByTestId('game-rail-actions'));
  });
});

