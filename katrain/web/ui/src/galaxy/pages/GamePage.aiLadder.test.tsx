import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../api';
import GamePage from './GamePage';

const { getStatus } = vi.hoisted(() => ({ getStatus: vi.fn() }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus: getStatus }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: undefined, user: { username: 'fan' } }) }));
vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_en: string, zh: string) => zh }) }));
vi.mock('../context/GameNavigationContext', () => ({ useGameNavigation: () => ({ registerActiveGame: vi.fn(), unregisterActiveGame: vi.fn() }) }));
vi.mock('../../components/Board', () => ({ default: () => <div>board</div> }));
vi.mock('../components/game/RightSidebarPanel', () => ({
  default: ({ embedded }: { embedded?: boolean }) => <div data-testid="game-controls" data-embedded={String(Boolean(embedded))}>controls</div>,
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
  sessionId: 's1', setSessionId: vi.fn(), gameState, setGameState: vi.fn(), error: null, onMove: vi.fn(),
  onNavigate: vi.fn(), handleAction: vi.fn(), initNewSession: vi.fn(), lastLog: null, chatMessages: [], sendChat: vi.fn(),
}) }));

describe('Galaxy GamePage ranked settlement', () => {
  beforeEach(() => { sessionStorage.clear(); getStatus.mockReset(); });

  it('renders the authoritative feedback and supports cookie-only status refresh', async () => {
    sessionStorage.setItem('ai-ladder-before:s1', JSON.stringify({ identity: 'fan', status: status(18) }));
    getStatus.mockResolvedValue(status(17));
    render(<MemoryRouter initialEntries={['/galaxy/play/ai/game/s1?mode=rated']}><Routes><Route path="/galaxy/play/ai/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);
    expect(await screen.findByText('降级：17级')).toBeInTheDocument();
    const rail = screen.getByTestId('board-rail-scroll');
    expect(rail).toHaveTextContent('本局已结算');
    expect(rail).toContainElement(screen.getByRole('button', { name: '再来一局' }));
    expect(rail).toContainElement(screen.getByRole('button', { name: '返回对局' }));
    expect(getStatus).toHaveBeenCalledWith(undefined, expect.any(AbortSignal));
  });

  it('keeps the rated board clear and puts the named parent action in the right rail', () => {
    getStatus.mockResolvedValue(status(18));
    render(<MemoryRouter initialEntries={['/galaxy/play/game/s1?mode=rated']}><Routes><Route path="/galaxy/play/game/:sessionId" element={<GamePage />} /></Routes></MemoryRouter>);

    const stage = screen.getByTestId('board-stage');
    const module = screen.getByTestId('board-rail-module');
    expect(stage).toHaveTextContent('board');
    expect(stage).not.toHaveTextContent('升降级对弈');
    expect(module).toHaveTextContent('升降级对弈');
    expect(module).toContainElement(screen.getByRole('button', { name: '返回升降级' }));
    expect(screen.getByTestId('game-controls')).toHaveAttribute('data-embedded', 'true');
  });
});
