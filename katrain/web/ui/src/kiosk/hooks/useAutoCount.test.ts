import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError, type GameState } from '../../api';
import { autoCountEligible, useAutoCount, type UseAutoCountOptions } from './useAutoCount';

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return { ...actual, API: { ...actual.API, requestCount: vi.fn() } };
});

const onState = vi.fn();
const opts = (over: Partial<UseAutoCountOptions> = {}): UseAutoCountOptions => ({
  sessionId: 's-1', awaitingCount: false, nodeId: 7, onState, ...over,
});
const pending = () =>
  new ApiError(400, 'Request failed 400: …', { code: 'analysis_pending', message: 'Analysis not available yet' });

beforeEach(() => { vi.mocked(API.requestCount).mockReset(); onState.mockReset(); });
afterEach(() => { vi.useRealTimers(); });

describe('useAutoCount', () => {
  it('不在等数子 ⇒ 一个请求都不发', () => {
    const { result } = renderHook(() => useAutoCount(opts()));
    expect(result.current.status).toBe('idle');
    expect(API.requestCount).not.toHaveBeenCalled();
  });

  it('awaiting 为真就自动数一次,终局 state 交回去;同一节点再推一次 state 不重复数', async () => {
    const ended = { end_result: 'B+3.5' } as GameState;
    vi.mocked(API.requestCount).mockResolvedValue({ session_id: 's-1', state: ended });
    const { result, rerender } = renderHook((p: UseAutoCountOptions) => useAutoCount(p), {
      initialProps: opts({ awaitingCount: true }),
    });
    expect(result.current.status).toBe('counting');
    await waitFor(() => expect(onState).toHaveBeenCalledWith(ended));
    rerender(opts({ awaitingCount: true }));
    expect(API.requestCount).toHaveBeenCalledTimes(1);
    expect(API.requestCount).toHaveBeenCalledWith('s-1');
  });

  // 时间线:第 0 / 1 / 3 / 6 / 10 / 15 秒各发一次,第 6 次还是 analysis_pending 才说原因。
  it('analysis_pending 退避重试,约 15 秒后说出真实原因;按重试重新开始', async () => {
    vi.useFakeTimers();
    vi.mocked(API.requestCount).mockRejectedValue(pending());
    const { result } = renderHook(() => useAutoCount(opts({ awaitingCount: true })));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(API.requestCount).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(14_999); });
    expect(API.requestCount).toHaveBeenCalledTimes(5);
    expect(result.current.status).toBe('counting');
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(API.requestCount).toHaveBeenCalledTimes(6);
    expect(result.current.status).toBe('failed');
    expect(result.current.reason).toBe('还在算这一手的形势，稍等再数');
    act(() => result.current.retry());
    expect(result.current.status).toBe('counting');
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(API.requestCount).toHaveBeenCalledTimes(7);
  });

  it('网络层失败不退避,直接说「分析服务连不上」', async () => {
    vi.mocked(API.requestCount).mockRejectedValue(new TypeError('Failed to fetch'));
    const { result } = renderHook(() => useAutoCount(opts({ awaitingCount: true })));
    await waitFor(() => expect(result.current.status).toBe('failed'));
    expect(result.current.reason).toBe('分析服务连不上');
    expect(API.requestCount).toHaveBeenCalledTimes(1);
  });

  it('退避中不再 awaiting ⇒ 掐掉计时器,不再请求', async () => {
    vi.useFakeTimers();
    vi.mocked(API.requestCount).mockRejectedValue(pending());
    const { result, rerender } = renderHook((p: UseAutoCountOptions) => useAutoCount(p), {
      initialProps: opts({ awaitingCount: true }),
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    rerender(opts({ awaitingCount: false }));
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
    expect(API.requestCount).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe('idle');
  });
});

describe('autoCountEligible', () => {
  const seat = (player_type: string) => ({
    player_type, player_subtype: '', name: '', calculated_rank: null, periods_used: 0, main_time_used: 0,
  });
  const gs = (game_type: string, b: string, w: string) =>
    ({ game_type, players_info: { B: seat(b), W: seat(w) } }) as unknown as GameState;
  it.each([
    ['本地对局', gs('pvp_local', 'player:human', 'player:human'), false, true],
    ['人机自由对弈', gs('free', 'player:human', 'player:ai'), false, true],
    ['大厅对局(后端 game_type 也是 free)', gs('free', 'human', 'human'), false, false],
    ['星阵人机', gs('free', 'human', 'human'), true, false],
    ['升降级', gs('ai_ladder_ranked', 'player:human', 'player:ai'), false, true],
  ] as const)('%s', (_name, state, engineMode, expected) => {
    expect(autoCountEligible(state, engineMode)).toBe(expected);
  });
});
