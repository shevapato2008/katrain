import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ReportsAPI } from '../../api/reportApi';
import { useReportTasks } from './useReportTasks';

vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_k: string, fallback: string) => fallback }),
}));

/* 402 有两种，用户该做的事完全不同：没绑手机 → 去绑（一步就有免费额度）；
   真没钱 → 去充值。合成一句「余额不足」是把前者的出路藏起来。

   判据落在**这一层**（hook 读 detail 并翻译），配合 api/reportApi.errorShape.test.ts
   那一层（真 fetch 把 detail 挂上去）。两层都有，链路才算被守住 —— 只写这一层的话，
   reportApi 忘了挂 detail 时这里照样绿。 */
describe('useReportTasks 的 402 分支', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(ReportsAPI, 'list').mockResolvedValue([] as never);
    vi.spyOn(ReportsAPI, 'summary').mockResolvedValue({ queued: 0, running: 0 } as never);
  });

  const mount = async () => {
    const hook = renderHook(() => useReportTasks('tok'));
    await waitFor(() => expect(ReportsAPI.list).toHaveBeenCalled());
    return hook;
  };

  const reject = (detail: unknown) =>
    vi.spyOn(ReportsAPI, 'create').mockRejectedValue(
      Object.assign(new Error('Request failed 402: {}'), { status: 402, detail }));

  it('402 且 free_weekly_blocked=phone_unbound：给的是绑定引导，不是只弹充值', async () => {
    reject({ code: 'insufficient_credits', free_weekly_blocked: 'phone_unbound' });
    const { result } = await mount();
    await act(async () => {
      await result.current.createReport({ userGameId: 'g1', reportType: 'normal', totalMoves: 100 })
        .catch(() => {});
    });
    await waitFor(() => expect(result.current.error).toMatch(/绑定手机号/));
    expect(result.current.error).toMatch(/免费/);
    expect(result.current.error).not.toMatch(/Request failed/);
  });

  it('402 但已绑手机：只是真的没钱，不出现绑定引导', async () => {
    reject({ code: 'insufficient_credits', free_weekly_blocked: null });
    const { result } = await mount();
    await act(async () => {
      await result.current.createReport({ userGameId: 'g1', reportType: 'normal', totalMoves: 100 })
        .catch(() => {});
    });
    await waitFor(() => expect(result.current.error).toMatch(/余额不足/));
    expect(result.current.error).not.toMatch(/绑定手机号/);
  });

  it('别的失败不被误伤，仍然原样报出来', async () => {
    vi.spyOn(ReportsAPI, 'create').mockRejectedValue(
      Object.assign(new Error('Request failed 500: boom'), { status: 500 }));
    const { result } = await mount();
    await act(async () => {
      await result.current.createReport({ userGameId: 'g1', reportType: 'normal', totalMoves: 100 })
        .catch(() => {});
    });
    await waitFor(() => expect(result.current.error).toMatch(/Request failed 500/));
  });
});
