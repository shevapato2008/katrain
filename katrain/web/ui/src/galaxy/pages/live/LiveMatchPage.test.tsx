import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { MatchDetail, MoveAnalysis } from '../../../types/live';
import { GameNavigationProvider } from '../../context/GameNavigationContext';
import LiveMatchPage from './LiveMatchPage';

const mockSetCurrentMove = vi.fn();
const mockRefresh = vi.fn();
let liveFixture: {
  match: MatchDetail | null;
  loading: boolean;
  error: Error | null;
  currentMove: number;
  setCurrentMove: (move: number) => void;
  analysis: Record<number, MoveAnalysis>;
  refresh: () => Promise<void>;
};
let boardProps: Record<string, unknown> = {};

vi.mock('../../../hooks/live/useLiveMatch', () => ({
  useLiveMatch: () => liveFixture,
}));

vi.mock('../../../hooks/useSound', () => ({
  useSound: () => ({ play: vi.fn() }),
}));

vi.mock('../../../components/live/LiveBoard', () => ({
  default: (props: Record<string, unknown>) => {
    boardProps = props;
    return <div data-testid="mock-live-board">Live Board</div>;
  },
}));

type ResizeCallback = ConstructorParameters<typeof ResizeObserver>[0];
class ResizeObserverMock {
  static callback: ResizeCallback | undefined;
  static observed: Element | undefined;
  constructor(callback: ResizeCallback) { ResizeObserverMock.callback = callback; }
  observe(target: Element) { ResizeObserverMock.observed = target; }
  unobserve() {}
  disconnect() {}
}

const match: MatchDetail = {
  id: 'live-9', source: 'yike', tournament: 'Galaxy Cup', round_name: 'Final',
  date: '2026-08-06T12:00:00Z', player_black: 'Alpha', player_white: 'Beta',
  black_rank: '九段', white_rank: '八段', status: 'live', result: null, move_count: 3,
  current_winrate: 0.56, current_score: 2.4, last_updated: '2026-08-06T12:01:00Z',
  board_size: 19, komi: 7.5, rules: 'chinese', sgf: null, moves: ['D4', 'Q16', 'C3'],
};

const moveAnalysis = (moveNumber: number, move: string, pv: string[]): MoveAnalysis => ({
  match_id: match.id, move_number: moveNumber, move, player: moveNumber % 2 ? 'B' : 'W',
  winrate: 0.56, score_lead: 2.4,
  top_moves: [{ move: 'D16', visits: 1200, winrate: 0.58, score_lead: 3.1, prior: 0.2, pv, psv: 1 }],
  ownership: Array.from({ length: 19 }, () => Array(19).fill(0.1)),
  is_brilliant: false, is_mistake: false, is_questionable: false, delta_score: 0, delta_winrate: 0,
});
const analysis = { 2: moveAnalysis(2, 'Q16', ['D16', 'Q4']), 3: moveAnalysis(3, 'C3', ['C4']) };

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/galaxy/live/live-9']}>
      <GameNavigationProvider>
        <Routes>
          <Route path="/galaxy/live/:matchId" element={<LiveMatchPage />} />
          <Route path="/galaxy/live" element={<div>Live list destination</div>} />
        </Routes>
      </GameNavigationProvider>
    </MemoryRouter>,
  );
}

describe('LiveMatchPage', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    ResizeObserverMock.callback = undefined;
    ResizeObserverMock.observed = undefined;
    boardProps = {};
    mockSetCurrentMove.mockReset();
    mockRefresh.mockReset();
    mockRefresh.mockResolvedValue(undefined);
    liveFixture = {
      match, loading: false, error: null, currentMove: 2,
      setCurrentMove: mockSetCurrentMove, analysis, refresh: mockRefresh,
    };
  });

  it('composes real match data and panels into the shared shell without an old board header', () => {
    renderPage();

    const shell = screen.getByTestId('board-page-shell');
    const stage = screen.getByTestId('board-stage');
    const module = screen.getByTestId('board-rail-module');
    const rail = screen.getByTestId('board-rail-scroll');
    const actions = screen.getByTestId('board-rail-actions');

    expect(within(stage).getByTestId('mock-live-board')).toBeInTheDocument();
    expect(within(stage).queryByText('Alpha vs Beta')).not.toBeInTheDocument();
    expect(within(module).getByText('Alpha vs Beta')).toBeInTheDocument();
    expect(within(module).getByText('Galaxy Cup · Final · 2 / 3 live:moves')).toBeInTheDocument();
    expect(within(module).getByText('live:status_live')).toBeInTheDocument();
    expect(within(rail).getByText('Alpha')).toBeInTheDocument();
    expect(within(rail).getByText('AI Recommendations')).toBeInTheDocument();
    const controls = within(rail).getByTestId('live-match-display-controls-grid');
    const trend = within(rail).getByTestId('live-match-trend-region');
    expect(controls).toBeInTheDocument();
    // 工具格是四列一行的四个键；坐标不在格子里，是格子下面单独一行的开关。
    expect(within(controls).getAllByRole('button')).toHaveLength(4);
    expect(within(rail).getByRole('checkbox', { name: 'Coordinates' })).toBeInTheDocument();
    expect(trend).toHaveStyle({ flex: 'none' });
    expect(within(actions).getByText('2 / 3 live:moves')).toBeInTheDocument();
    expect(shell).toBeInTheDocument();
  });

  it('preserves board props, PV hover, playback callbacks, try moves, and responsive coordinates', async () => {
    renderPage();

    expect(boardProps).toMatchObject({
      moves: match.moves, currentMove: 2, showAiMarkers: true, showMoveNumbers: false,
      showTerritory: false, showCoordinates: false, minimumCanvasSize: 0, minContainerHeight: 0,
    });
    expect(boardProps.aiMarkers).toEqual([{ move: 'D16', rank: 1, visits: 1200, winrate: 0.58, score_lead: 3.1 }]);
    expect(boardProps.ownership).toEqual(analysis[2].ownership);

    fireEvent.mouseEnter(screen.getByText('D16'));
    expect(boardProps.pvMoves).toEqual(['D16', 'Q4']);
    fireEvent.mouseLeave(screen.getByText('D16'));
    expect(boardProps.pvMoves).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'live:previous' }));
    expect(mockSetCurrentMove).toHaveBeenCalledWith(1);

    fireEvent.click(screen.getByRole('button', { name: 'Try Move' }));
    act(() => (boardProps.onTryMove as (move: string) => void)('K10'));
    expect(boardProps.tryMoves).toEqual(['K10']);
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(boardProps.tryMoves).toEqual([]);

    act(() => ResizeObserverMock.callback?.(
      [{ target: ResizeObserverMock.observed, contentRect: { width: 620, height: 600 } } as ResizeObserverEntry],
      {} as ResizeObserver,
    ));
    expect(boardProps.showCoordinates).toBe(true);
    // 坐标已从工具格挪成单独一行的开关（与死活题页对齐），role 从 button 变成 checkbox。
    expect(screen.getByRole('checkbox', { name: 'Coordinates' })).toBeChecked();
  });

  it('keeps the playback move counter as one measurable action-region item', () => {
    renderPage();
    const counter = within(screen.getByTestId('board-rail-actions')).getByTestId('playback-move-counter');
    expect(counter).toHaveTextContent('2 / 3 live:moves');
    expect(counter).toHaveStyle({ minWidth: '87px', whiteSpace: 'nowrap' });
  });

  it('uses requestNavigation for the module back action', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(await screen.findByText('Live list destination')).toBeInTheDocument();
  });

  it('keeps shell geometry with progress and disabled controls while loading', () => {
    liveFixture = { ...liveFixture, match: null, loading: true };
    renderPage();

    expect(screen.getByTestId('board-page-shell')).toBeInTheDocument();
    expect(screen.getByTestId('board-loading-skeleton')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByTestId('board-rail-scroll')).toBeInTheDocument();
    expect(screen.getByTestId('board-rail-actions')).toBeInTheDocument();
    screen.getAllByRole('button').filter((button) => button.getAttribute('aria-label') !== 'Back')
      .forEach((button) => expect(button).toBeDisabled());
  });

  it('keeps the shell and hides stale match data in a retryable error state', () => {
    liveFixture = { ...liveFixture, error: new Error('Broadcast unavailable') };
    renderPage();

    expect(screen.getByTestId('board-page-shell')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Broadcast unavailable');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled();
    expect(screen.queryByTestId('mock-live-board')).not.toBeInTheDocument();
    expect(screen.queryByText('Alpha vs Beta')).not.toBeInTheDocument();
  });

  it('awaits refresh and keeps the fixed-size retry action disabled with progress', async () => {
    let resolveRefresh!: () => void;
    mockRefresh.mockReturnValue(new Promise<void>((resolve) => { resolveRefresh = resolve; }));
    liveFixture = { ...liveFixture, error: new Error('Broadcast unavailable') };
    renderPage();

    const retry = screen.getByRole('button', { name: 'Retry' });
    fireEvent.click(retry);
    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(retry).toBeDisabled();
    expect(retry).toHaveStyle({ minWidth: '96px' });
    expect(within(retry).getByRole('progressbar')).toBeInTheDocument();

    resolveRefresh();
    await waitFor(() => expect(retry).toBeEnabled());
  });
});
