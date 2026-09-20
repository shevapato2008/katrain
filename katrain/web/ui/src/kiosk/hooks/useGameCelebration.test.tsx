import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../api';
import { useGameCelebration } from './useGameCelebration';

const { play } = vi.hoisted(() => ({ play: vi.fn() }));
vi.mock('../../hooks/useSound', () => ({ useSound: () => ({ play }) }));

const state = (overrides: Partial<GameState> = {}) => ({
  game_id: 'game-1', game_type: 'free', end_result: null, current_node_id: 10,
  ...overrides,
}) as GameState;

interface Props {
  sessionId: string;
  gameState: GameState | undefined;
  humanColor: 'B' | 'W' | null;
}
const props = (gameState: GameState | undefined, overrides: Partial<Props> = {}): Props => ({
  sessionId: 'session-1', gameState, humanColor: 'B', ...overrides,
});
const mount = (initialProps: Props) => renderHook(
  (p: Props) => useGameCelebration(p.sessionId, p.gameState, p.humanColor), { initialProps },
);
const startFrame = () => act(() => vi.advanceTimersToNextFrame());

describe('useGameCelebration', () => {
  beforeEach(() => { vi.useFakeTimers(); play.mockClear(); });
  afterEach(() => vi.useRealTimers());

  it('celebrates the live counted win once, for 1.6 seconds, after the result renders', () => {
    const hook = mount(props(undefined));
    hook.rerender(props(state({ awaiting_count: true })));
    hook.rerender(props(state({ awaiting_count: true, end_result: 'B+3.5' })));
    startFrame();
    expect(play).not.toHaveBeenCalled();

    hook.rerender(props(state({ end_result: 'B+3.5' })));
    expect(hook.result.current).toBe(false);
    startFrame();
    expect(play).toHaveBeenCalledExactlyOnceWith('solved');
    expect(hook.result.current).toBe(true);

    hook.rerender(props(state({ end_result: 'B+3.5', current_node_id: 11 })));
    act(() => vi.advanceTimersByTime(1600));
    expect(hook.result.current).toBe(false);

    // Reviewing an earlier node then returning to the final position is not a new win.
    hook.rerender(props(state()));
    hook.rerender(props(state({ end_result: 'B+3.5' })));
    startFrame();
    expect(play).toHaveBeenCalledTimes(1);
    expect(hook.result.current).toBe(false);
  });

  it.each([
    ['white human', 'free', 'W', 'W+0.5', true],
    ['resignation', 'free', 'B', 'B+R', true],
    ['black local winner', 'pvp_local', null, 'B+3.5', true],
    ['white local winner', 'pvp_local', null, 'W+2.5', true],
    ['loss', 'free', 'B', 'W+3.5', false],
    ['unknown online seat', 'pvp_online', null, 'B+3.5', false],
    ['unknown free-game seat', 'free', null, 'B+3.5', false],
    ['draw', 'free', 'B', 'Draw', false],
    ['void', 'free', 'B', 'Void', false],
    ['zero margin', 'free', 'B', 'B+0', false],
    ['unknown result', 'free', 'B', 'B+?', false],
  ] as const)('%s: celebrates only a known human winner', (_label, game_type, humanColor, end_result, expected) => {
    const hook = mount(props(state({ game_type }), { humanColor }));
    hook.rerender(props(state({ game_type, end_result }), { humanColor }));
    startFrame();
    expect(hook.result.current).toBe(expected);
    expect(play).toHaveBeenCalledTimes(expected ? 1 : 0);
  });

  it('does not celebrate loading an ended game or reconnecting to its final state', () => {
    const hook = mount(props(undefined));
    hook.rerender(props(state({ end_result: 'B+3.5' })));
    startFrame();
    hook.rerender(props(undefined));
    hook.rerender(props(state({ end_result: 'B+3.5' })));
    startFrame();
    hook.rerender(props(state()));
    hook.rerender(props(state({ end_result: 'B+3.5' })));
    startFrame();
    expect(play).not.toHaveBeenCalled();
    expect(hook.result.current).toBe(false);
  });

  it('recognizes game-level terminal_result and never replays it during review', () => {
    const hook = mount(props(state()));
    hook.rerender(props(state({ terminal_result: 'B+1.5' })));
    startFrame();
    expect(play).toHaveBeenCalledExactlyOnceWith('solved');
    hook.rerender(props(state({ terminal_result: 'B+1.5', current_node_id: 1 })));
    startFrame();
    expect(play).toHaveBeenCalledTimes(1);
  });

  it('clears celebration on game change and allows a new live win in the same session', () => {
    const hook = mount(props(state()));
    hook.rerender(props(state({ end_result: 'B+3.5' })));
    startFrame();
    expect(hook.result.current).toBe(true);

    hook.rerender(props(state({ game_id: 'game-2' })));
    expect(hook.result.current).toBe(false);
    hook.rerender(props(state({ game_id: 'game-2', end_result: 'B+R' })));
    startFrame();
    expect(hook.result.current).toBe(true);
    expect(play).toHaveBeenCalledTimes(2);
  });

  it('does not treat a new session ending state as a live transition from the old session', () => {
    const hook = mount(props(state()));
    hook.rerender(props(state({ end_result: 'B+3.5' }), { sessionId: 'session-2' }));
    startFrame();
    expect(play).not.toHaveBeenCalled();
    expect(hook.result.current).toBe(false);
  });

  it('cancels pending sound and animation when unmounted before the result frame', () => {
    const hook = mount(props(state()));
    hook.rerender(props(state({ end_result: 'B+3.5' })));
    hook.unmount();
    startFrame();
    expect(play).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
});
