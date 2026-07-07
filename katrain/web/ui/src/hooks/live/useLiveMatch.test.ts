import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { MatchDetail, MoveAnalysis } from '../../types/live';

// Mock the API layer; the hook is the unit under test. With LiveAPI mocked, the
// real api/live module (and its __KIOSK_2D_ONLY__ base-URL logic) never executes.
vi.mock('../../api/live', () => ({
  LiveAPI: {
    getMatch: vi.fn(),
    getMatchAnalysis: vi.fn(),
    preloadAnalysis: vi.fn(),
  },
}));

import { LiveAPI } from '../../api/live';
import { useLiveMatch } from './useLiveMatch';

const getMatch = LiveAPI.getMatch as ReturnType<typeof vi.fn>;
const getMatchAnalysis = LiveAPI.getMatchAnalysis as ReturnType<typeof vi.fn>;
const preloadAnalysis = LiveAPI.preloadAnalysis as ReturnType<typeof vi.fn>;

const POLL = 5000;

// ── Fixtures ──────────────────────────────────────────────────────────────

function makeMatch(overrides: Partial<MatchDetail> = {}): MatchDetail {
  return {
    id: 'm1',
    source: 'xingzhen',
    tournament: 'T',
    round_name: null,
    date: '2025-01-01',
    player_black: 'B',
    player_white: 'W',
    black_rank: null,
    white_rank: null,
    status: 'live',
    result: null,
    move_count: 0,
    current_winrate: 0.5,
    current_score: 0,
    last_updated: '2025-01-01T00:00:00Z',
    board_size: 19,
    komi: 7.5,
    rules: 'chinese',
    sgf: '(;)',
    moves: [],
    ...overrides,
  };
}

function moveAnalysis(n: number): MoveAnalysis {
  return {
    match_id: 'm1',
    move_number: n,
    move: null,
    player: null,
    winrate: 0.5,
    score_lead: 0,
    top_moves: [],
    ownership: null,
    is_brilliant: false,
    is_mistake: false,
    is_questionable: false,
    delta_score: 0,
    delta_winrate: 0,
  };
}

// Build an analysis record covering EXACTLY the given (sparse-allowed) move numbers.
// Mirrors the server contract: analysis is keyed by board position 0..move_count,
// SUCCESS rows only (FAILED positions are holes).
function analysisFor(moves: number[]): Record<number, MoveAnalysis> {
  const rec: Record<number, MoveAnalysis> = {};
  for (const m of moves) rec[m] = moveAnalysis(m);
  return rec;
}

function setMatchData(match: MatchDetail) {
  getMatch.mockResolvedValue(match);
}
function setPreload(analysis: Record<number, MoveAnalysis>) {
  const moves = Object.keys(analysis).map(Number);
  preloadAnalysis.mockResolvedValue({
    match_id: 'm1',
    analyzed_moves: moves,
    total_moves: moves.length,
    analysis,
  });
}
function setAnalysis(analysis: Record<number, MoveAnalysis>) {
  getMatchAnalysis.mockResolvedValue({
    match_id: 'm1',
    analyzed_moves: Object.keys(analysis).map(Number),
    analysis,
  });
}

// Flush the initial mount fetches (getMatch + preload) and their re-renders.
async function settle() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

// Fire the polling interval `times` times, one interval per step so the
// ref-sync effect commits between ticks (matches real render cadence).
//
// NOTE on the one-tick lag: the polling callback snapshots `liveRef` at the
// START of the tick, then calls fetchMatch() whose result only reaches the gate
// on the NEXT tick. So a freshly-changed move_count / currentMove takes one
// extra tick to influence the analysis gate — tests advance 2 ticks accordingly.
async function tick(times = 1) {
  for (let i = 0; i < times; i++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL);
    });
  }
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  // Sensible defaults; every test overrides what it cares about.
  setMatchData(makeMatch());
  setPreload({});
  setAnalysis({});
});

afterEach(() => {
  vi.useRealTimers();
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe('useLiveMatch — freshness gate', () => {
  it('initial load: fetches match once and preloads analysis once', async () => {
    setMatchData(makeMatch({ move_count: 3 }));
    setPreload(analysisFor([0, 1, 2, 3]));

    const { result } = renderHook(() => useLiveMatch('m1', { pollInterval: 0 }));
    await settle();

    expect(getMatch).toHaveBeenCalledTimes(1);
    expect(preloadAnalysis).toHaveBeenCalledTimes(1);
    expect(getMatchAnalysis).not.toHaveBeenCalled();
    expect(result.current.match?.move_count).toBe(3);
    // currentMove auto-follows the tip after first load (null sentinel resolved).
    expect(result.current.currentMove).toBe(3);
  });

  it('tip pending: polls analysis every tick while the tip move is unanalyzed', async () => {
    setMatchData(makeMatch({ move_count: 2 }));
    setPreload(analysisFor([0, 1])); // tip (2) missing
    setAnalysis(analysisFor([0, 1])); // still pending on each poll
    renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    expect(getMatchAnalysis).not.toHaveBeenCalled(); // gate only runs inside the interval
    await tick(3);
    expect(getMatchAnalysis).toHaveBeenCalledTimes(3); // one per tick (below NO_PROGRESS_LIMIT)
  });

  it('caught up: steady state issues zero analysis requests but keeps match fresh', async () => {
    setMatchData(makeMatch({ move_count: 2 }));
    setPreload(analysisFor([0, 1, 2])); // covers 0..move_count
    renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    await tick(4);
    expect(getMatchAnalysis).not.toHaveBeenCalled(); // no heavy refetch once caught up
    expect(getMatch).toHaveBeenCalledTimes(1 + 4); // detail/winrate still polled every tick
  });

  it('new move: resumes analysis polling when move_count advances past coverage', async () => {
    setMatchData(makeMatch({ move_count: 2 }));
    setPreload(analysisFor([0, 1, 2])); // caught up at move 2
    renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    await tick(2);
    expect(getMatchAnalysis).not.toHaveBeenCalled(); // steady state

    // Server plays move 3; analysis for 3 not yet computed.
    setMatchData(makeMatch({ move_count: 3 }));
    setAnalysis(analysisFor([0, 1, 2])); // tip 3 still pending
    await tick(2); // tick 1: fetchMatch sees move_count=3; tick 2: gate acts on it
    expect(getMatchAnalysis).toHaveBeenCalled();
  });

  it('FAILED tip: caps retries at NO_PROGRESS_LIMIT, then resumes on a new move', async () => {
    setMatchData(makeMatch({ move_count: 2 }));
    setPreload(analysisFor([0, 1])); // tip 2 FAILED — never appears
    setAnalysis(analysisFor([0, 1])); // poll keeps returning the same hole
    renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    await tick(10);
    // streak caps at NO_PROGRESS_LIMIT (6) — no infinite hammering of a stuck position.
    expect(getMatchAnalysis).toHaveBeenCalledTimes(6);

    // A new move bumps move_count -> resets the no-progress streak -> resumes.
    setMatchData(makeMatch({ move_count: 3 }));
    setAnalysis(analysisFor([0, 1])); // 2 and 3 both still pending
    const before = getMatchAnalysis.mock.calls.length;
    await tick(3);
    expect(getMatchAnalysis.mock.calls.length).toBeGreaterThan(before);
  });

  it('view history: backfills analysis for a viewed move that has a hole', async () => {
    setMatchData(makeMatch({ move_count: 5 }));
    setPreload(analysisFor([1, 2, 3, 4, 5])); // move 0 is a hole; tip 5 covered
    setAnalysis(analysisFor([1, 2, 3, 4, 5]));
    const { result } = renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    await tick(2);
    expect(getMatchAnalysis).not.toHaveBeenCalled(); // viewing the (covered) tip

    // User scrubs back to move 0, whose analysis is missing.
    act(() => {
      result.current.setCurrentMove(0);
    });
    await tick(1);
    expect(getMatchAnalysis).toHaveBeenCalled(); // viewed-move hole triggers a fetch
  });

  it('nullable currentMove: follows the tip on load, preserves user navigation across polls', async () => {
    setMatchData(makeMatch({ move_count: 10 }));
    setPreload(analysisFor([8, 9, 10]));
    const { result } = renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    expect(result.current.currentMove).toBe(10); // not stuck at 0; null sentinel -> tip

    act(() => {
      result.current.setCurrentMove(4);
    });
    setMatchData(makeMatch({ move_count: 11 })); // server advances
    await tick(2);
    expect(result.current.currentMove).toBe(4); // user's position is NOT yanked to the new tip
  });

  it("status !== 'live': does not poll at all", async () => {
    setMatchData(makeMatch({ move_count: 50, status: 'finished' }));
    setPreload(analysisFor([0, 1, 2]));
    renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    expect(getMatch).toHaveBeenCalledTimes(1);
    expect(preloadAnalysis).toHaveBeenCalledTimes(1);

    await tick(5);
    expect(getMatch).toHaveBeenCalledTimes(1); // polling tick returns early on non-live status
    expect(getMatchAnalysis).not.toHaveBeenCalled();
  });

  it('Galaxy parity: default options preload then gate analysis while keeping match fresh', async () => {
    setMatchData(makeMatch({ move_count: 2 }));
    setPreload(analysisFor([0, 1, 2]));
    renderHook(() => useLiveMatch('m1')); // all defaults: pollInterval 5000, analysisMode 'poll'
    await settle();

    expect(preloadAnalysis).toHaveBeenCalledTimes(1);
    await tick(3);
    expect(getMatch).toHaveBeenCalledTimes(1 + 3); // match polled every tick
    expect(getMatchAnalysis).not.toHaveBeenCalled(); // gated: caught up
  });

  it('live -> finished: does one final analysis catch-up when a live match finishes', async () => {
    setMatchData(makeMatch({ move_count: 3, status: 'live' }));
    setPreload(analysisFor([0, 1, 2, 3])); // caught up while live
    setAnalysis(analysisFor([0, 1, 2, 3]));
    renderHook(() => useLiveMatch('m1', { pollInterval: POLL }));
    await settle();

    await tick(1);
    expect(getMatchAnalysis).not.toHaveBeenCalled();

    setMatchData(makeMatch({ move_count: 3, status: 'finished' }));
    await tick(1); // fetchMatch picks up 'finished' -> transition effect fires the catch-up
    expect(getMatchAnalysis).toHaveBeenCalled();
  });
});

describe('useLiveMatch — analysisMode none (board preview)', () => {
  it('never preloads or polls analysis but keeps moves fresh', async () => {
    setMatchData(makeMatch({ move_count: 5 }));
    setPreload(analysisFor([0, 1, 2, 3, 4, 5]));
    renderHook(() => useLiveMatch('m1', { pollInterval: POLL, analysisMode: 'none' }));
    await settle();

    expect(preloadAnalysis).not.toHaveBeenCalled();

    await tick(3);
    expect(getMatchAnalysis).not.toHaveBeenCalled();
    expect(getMatch).toHaveBeenCalledTimes(1 + 3); // moves/playback still refreshed for the preview
  });
});
