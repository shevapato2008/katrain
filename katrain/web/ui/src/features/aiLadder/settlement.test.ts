import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { createElement } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getAiLadderSettlementReceipt, getAiLadderStatus } from './api';
import { AiLadderSettlementAlert, deriveSettlementFeedback, peekAiLadderBefore, pollAiLadderSettlement, saveAiLadderBefore, useAiLadderSettlement } from './settlement';

vi.mock('./api', () => ({ getAiLadderStatus: vi.fn(), getAiLadderSettlementReceipt: vi.fn() }));

const entry = (rung: number, rank_name = `${rung}级`) => ({ rung, rank_name, certification_status: 'certified' as const, availability: 'available' as const, route: 'server' as const });
const placed = (rung: number, net_score = 0) => ({ view_state: 'ready' as const, placement_state: { phase: 'placed' as const, rung: entry(rung) }, current_opponent: entry(rung), recent_ranked_results: [], net_score: net_score as -2 | -1 | 0 | 1 | 2, pending_settlement: false });
const placement = (completed_games: number) => ({ view_state: 'ready' as const, placement_state: { phase: 'placement' as const, completed_games, total_games: 5 as const }, current_opponent: entry(10), recent_ranked_results: [], net_score: 0 as const, pending_settlement: false });
const noWait = async () => {};

describe('AI ladder settlement feedback', () => {
  beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks(); });
  it('peeks the authoritative game id without consuming the settlement snapshot', () => {
    saveAiLadderBefore('s1', placed(18), 'fan', 'game-1');
    expect(peekAiLadderBefore('s1', 'fan')?.gameId).toBe('game-1');
    expect(peekAiLadderBefore('s1', 'fan')?.gameId).toBe('game-1');
  });
  it('distinguishes placement completion, promotion, demotion and score-only change', () => {
    expect(deriveSettlementFeedback(placement(4), placed(18)).kind).toBe('placement_complete');
    expect(deriveSettlementFeedback(placed(18, 2), placed(19, 0)).kind).toBe('promotion');
    expect(deriveSettlementFeedback(placed(18, -2), placed(17, 0)).kind).toBe('demotion');
    expect(deriveSettlementFeedback(placed(18, 0), placed(18, 1)).kind).toBe('score_change');
    expect(deriveSettlementFeedback(placed(18, 1), placed(18, 1)).kind).toBe('no_change');
  });

  it('does not guess a transition without a pre-game snapshot', () => {
    expect(deriveSettlementFeedback(null, placed(18))).toEqual(expect.objectContaining({ kind: 'authoritative_complete' }));
  });

  it('uses warning/error semantics and exposes the retry action only when needed', () => {
    const retry = vi.fn();
    const { rerender } = render(createElement(AiLadderSettlementAlert, { feedback: { kind: 'pending', message: '处理中', retry } }));
    expect(screen.getByRole('alert')).toHaveClass('MuiAlert-colorWarning');
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(retry).toHaveBeenCalledOnce();
    rerender(createElement(AiLadderSettlementAlert, { feedback: { kind: 'error', message: '失败', retry } }));
    expect(screen.getByRole('alert')).toHaveClass('MuiAlert-colorError');
    rerender(createElement(AiLadderSettlementAlert, { feedback: { kind: 'promotion', message: '升级' } }));
    expect(screen.getByRole('alert')).toHaveClass('MuiAlert-colorSuccess');
  });

  it('polls pending settlement a finite number of times and returns the final authority', async () => {
    const pending = { ...placed(18), pending_settlement: true };
    const getStatus = vi.fn().mockResolvedValueOnce(pending).mockResolvedValueOnce(placed(19));
    const result = await pollAiLadderSettlement(getStatus, undefined, new AbortController().signal, 4, async () => {});
    expect(result.placement_state).toEqual(expect.objectContaining({ phase: 'placed', rung: expect.objectContaining({ rung: 19 }) }));
    expect(getStatus).toHaveBeenCalledTimes(2);
  });

  it('rejects malformed and cross-account snapshots instead of comparing them', async () => {
    sessionStorage.setItem('ai-ladder-before:s1', '{"identity":"fan","status":{"view_state":"ready"}}');
    vi.mocked(getAiLadderStatus).mockResolvedValue(placed(18));
    const malformed = renderHook(() => useAiLadderSettlement('s1', 'ai_ladder_ranked', 'W+R', undefined, 'fan'));
    await waitFor(() => expect(malformed.result.current?.kind).toBe('authoritative_complete'));
    malformed.unmount();

    saveAiLadderBefore('s2', placed(17), 'other-user');
    const crossAccount = renderHook(() => useAiLadderSettlement('s2', 'ai_ladder_ranked', 'W+R', undefined, 'fan'));
    await waitFor(() => expect(crossAccount.result.current?.kind).toBe('authoritative_complete'));
    expect(sessionStorage.getItem('ai-ladder-before:s2')).toBeNull();
  });

  it('surfaces exhausted pending and network errors with retry, then settles safely', async () => {
    const pending = { ...placed(18), pending_settlement: true };
    vi.mocked(getAiLadderStatus)
      .mockResolvedValueOnce(pending).mockResolvedValueOnce(pending).mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(pending).mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(placed(19));
    const hook = renderHook(() => useAiLadderSettlement('s3', 'ai_ladder_ranked', 'B+R', undefined, 'fan', noWait));
    await waitFor(() => expect(hook.result.current?.kind).toBe('pending'));
    expect(hook.result.current?.retry).toBeTypeOf('function');
    await act(async () => hook.result.current?.retry?.());
    await waitFor(() => expect(hook.result.current?.kind).toBe('authoritative_complete'));
    hook.unmount();

    vi.mocked(getAiLadderStatus).mockRejectedValueOnce(new Error('网络失败')).mockResolvedValueOnce(placed(18));
    const failed = renderHook(() => useAiLadderSettlement('s4', 'ai_ladder_ranked', 'W+R', undefined, 'fan', noWait));
    await waitFor(() => expect(failed.result.current?.kind).toBe('error'));
    await act(async () => failed.result.current?.retry?.());
    await waitFor(() => expect(failed.result.current?.kind).toBe('authoritative_complete'));
  });

  it('clears stale feedback when the canonical settlement condition stops matching', async () => {
    vi.mocked(getAiLadderStatus).mockResolvedValue(placed(18));
    const { result, rerender } = renderHook(
      ({ gameType }) => useAiLadderSettlement('s5', gameType, 'W+R', undefined, 'fan', noWait),
      { initialProps: { gameType: 'ai_ladder_ranked' } },
    );
    await waitFor(() => expect(result.current).not.toBeNull());
    rerender({ gameType: 'free' });
    await waitFor(() => expect(result.current).toBeNull());
  });

  it('uses the game-scoped receipt to explain a result that the server did not count', async () => {
    saveAiLadderBefore('s6', placed(18), 'fan', 'g6');
    vi.mocked(getAiLadderSettlementReceipt).mockResolvedValue({
      state: 'settled', game_id: 'g6', counted: false, reason: 'engine_unavailable',
    });
    vi.mocked(getAiLadderStatus).mockResolvedValue(placed(18));

    const hook = renderHook(() => useAiLadderSettlement('s6', 'ai_ladder_ranked', 'W+R', undefined, 'fan', noWait));

    await waitFor(() => expect(hook.result.current).toEqual(expect.objectContaining({
      kind: 'not_counted', message: '本局不计入升降级：棋力服务未能正常完成对局',
    })));
    expect(getAiLadderSettlementReceipt).toHaveBeenCalledWith('g6', undefined, expect.any(AbortSignal));
  });
});
