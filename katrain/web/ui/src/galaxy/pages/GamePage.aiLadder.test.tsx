import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../api';
import GamePage from './GamePage';

const mocks = vi.hoisted(() => ({
  getStatus: vi.fn(), getGameStatus: vi.fn(), onMove: vi.fn(), handleAction: vi.fn(), gameState: null as GameState | null,
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
  default: ({ embedded, gameState, onAction }: { embedded?: boolean; gameState: GameState; onAction: (action: string) => void }) => (
    <div data-testid="game-controls" data-embedded={String(Boolean(embedded))}>
      <button disabled={Boolean(gameState.end_result)} onClick={() => onAction('pass')}>pass</button>
    </div>
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
    mocks.gameState = gameState;
  });
  afterEach(() => vi.useRealTimers());

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

  it('polls an active ranked game every five seconds and stops at remote pending settlement', async () => {
    vi.useFakeTimers();
    try {
      mocks.gameState = { ...gameState, end_result: null };
      mocks.getGameStatus
        .mockResolvedValueOnce({ state: 'active', game_id: 'g1' })
        .mockResolvedValueOnce({ state: 'pending_settlement', game_id: 'g1' });
      render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated&game_id=g1']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);

      await act(async () => { await Promise.resolve(); await Promise.resolve(); });
      expect(mocks.getGameStatus).toHaveBeenCalledTimes(1);
      await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); await Promise.resolve(); });
      expect(screen.getByText('本局已在其他设备结束，正在结算')).toBeInTheDocument();
      await act(async () => { vi.advanceTimersByTime(10000); });
      expect(mocks.getGameStatus).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('blocks board moves and rail actions after remote settlement without inventing a board result', async () => {
    mocks.gameState = { ...gameState, end_result: null };
    mocks.getGameStatus.mockResolvedValue({
      state: 'settled', game_id: 'g1', receipt: { counted: true, reason: null },
    });
    render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated&game_id=g1']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);

    expect(await screen.findByText('本局已在其他设备结束，结算已完成')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'pass' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'board' }));
    fireEvent.click(screen.getByRole('button', { name: 'pass' }));
    expect(mocks.onMove).not.toHaveBeenCalled();
    expect(mocks.handleAction).not.toHaveBeenCalled();
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
