import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useKifuAnalysis } from './useKifuAnalysis';
import { kifuAnalysisStatus } from './kifuAnalysisStatus';
import type { KifuAnalysisDetail } from '../../types/kifu';

const getAnalysis = vi.hoisted(() => vi.fn());
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAnalysis } }));
afterEach(() => { vi.useRealTimers(); getAnalysis.mockReset(); });

function completedAnalysis(): KifuAnalysisDetail {
  return {
    album_id: 7, canonical_album_id: 7, sgf_sha256: 'sgf', model_sha256: 'model', requested_visits: 2000,
    status: 'completed', parameters_valid: true, parameters_verified: false, parameter_error: null,
    analysis_parameters: { version: 3, verified: false, rules: 'japanese', komi: 6.5,
      sgf_sha256: 'sgf', parameter_sha256: 'parameters',
      provenance: { source: 'komi_default', raw_rules: null, raw_komi: '6.5', policy: 'komi-default-v1' } },
    total_moves: 1, analyzed_moves: 1, error_message: null,
    moves: [{ move_number: 1, actual_move: 'D4', actual_player: 'B', winrate: .8, score_lead: 4,
      visits: 2000, root_visits: 2000, top_moves: [], ownership: null, delta_score: -3, delta_winrate: -.1,
      grade: 'mistake', points_lost: 3, points_lost_source: 'score', is_top_move: false, top_prior: .2, brilliance: null }],
  };
}

it.each([['japanese', 6.5], ['chinese', 7.5]])('maps valid default %s analysis and reports completion without claiming verification', async (rules, komi) => {
  const detail = completedAnalysis();
  detail.analysis_parameters = { ...detail.analysis_parameters!, rules: String(rules), komi: Number(komi),
    provenance: { source: 'komi_default', raw_rules: null, raw_komi: String(komi), policy: 'komi-default-v1' } };
  getAnalysis.mockResolvedValue(detail);
  const { result } = renderHook(() => useKifuAnalysis(7));
  await act(async () => {});
  expect(result.current.analysisByMove[1]).toMatchObject({ match_id: '7', move: 'D4', winrate: .8, score_lead: 4, is_mistake: true });
  expect(kifuAnalysisStatus(result.current.detail, false, (_key, fallback) => fallback)).toBe('分析已完成');
  expect(result.current.detail?.parameters_verified).toBe(false);
});

it.each([1, 2] as const)('accepts verified version %i fixtures without parameters_valid', async (version) => {
  const detail = completedAnalysis();
  delete detail.parameters_valid;
  detail.parameters_verified = true;
  detail.analysis_parameters = { ...detail.analysis_parameters!, version, verified: true, provenance: { source: 'sgf' } };
  getAnalysis.mockResolvedValue(detail);
  const { result } = renderHook(() => useKifuAnalysis(7));
  await act(async () => {});
  expect(result.current.analysisByMove[1]?.winrate).toBe(.8);
  expect(kifuAnalysisStatus(result.current.detail, false, (_key, fallback) => fallback)).toBe('分析已完成');
});

it.each(['invalid', 'unbound', 'unresolved', 'legacy_unverified', 'empty'] as const)('withholds %s completed reports', async (state) => {
  const detail = completedAnalysis();
  if (state === 'invalid') { detail.parameters_valid = false; detail.parameters_verified = true; detail.analysis_parameters!.verified = true; }
  if (state === 'unbound') detail.analysis_parameters = null;
  if (state === 'unresolved') detail.status = 'rules_unresolved';
  if (state === 'legacy_unverified') delete detail.parameters_valid;
  if (state === 'empty') detail.moves = [];
  getAnalysis.mockResolvedValue(detail);
  const { result } = renderHook(() => useKifuAnalysis(7));
  await act(async () => {});
  expect(result.current.analysisByMove).toEqual({});
  expect(kifuAnalysisStatus(result.current.detail, false, (_key, fallback) => fallback)).not.toBe('分析已完成');
});

it('withholds unverified rows and treats unresolved rules as a terminal, honest status', async () => {
  vi.useFakeTimers();
  getAnalysis.mockResolvedValue({ status: 'rules_unresolved', parameters_verified: false, analysis_parameters: null,
    parameter_error: { code: 'rules_missing', message: 'SGF has no RU' }, moves: [{ move_number: 1, winrate: .8, score_lead: 4 }] });
  const { result } = renderHook(() => useKifuAnalysis(7));
  await act(async () => {});
  expect(result.current.analysisByMove).toEqual({});
  expect(kifuAnalysisStatus(result.current.detail, false, (_key, fallback) => fallback)).toBe('规则待核验');
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(getAnalysis).toHaveBeenCalledTimes(1);
});

it('downloads a completed report once', async () => {
  vi.useFakeTimers();
  getAnalysis.mockResolvedValue({ status: 'completed', moves: [] });
  const { result } = renderHook(() => useKifuAnalysis(7));
  await act(async () => {});
  expect(result.current.detail?.status).toBe('completed');
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(getAnalysis).toHaveBeenCalledTimes(1);
});

it('polls a running report, stops when complete, and ignores a departed game', async () => {
  vi.useFakeTimers();
  getAnalysis.mockResolvedValueOnce({ status: 'running', moves: [] })
    .mockResolvedValueOnce({ status: 'completed', moves: [] });
  const { result, rerender } = renderHook(({ id }) => useKifuAnalysis(id), { initialProps: { id: 7 as number | null } });
  await act(async () => {});
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(result.current.detail?.status).toBe('completed');
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(getAnalysis).toHaveBeenCalledTimes(2);
  rerender({ id: null });
  expect(result.current.detail).toBeNull();
});
