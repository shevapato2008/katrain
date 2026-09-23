import { describe, it, expect } from 'vitest';
import { winrateCell, type GrowthSummary } from './growthApi';

const base: GrowthSummary = {
  window_days: 30, games_in_window: 0, ranked_total: 0,
  ranked_wins_in_window: 0, ranked_losses_in_window: 0,
  by_opponent_rung: [], authority: 'cloud',
};

describe('winrateCell', () => {
  it('有新字段时算全部算得出执色的局', () => {
    const got = winrateCell({ ...base, games_in_window: 10, decided_games_in_window: 8, wins_in_window: 6, losses_in_window: 2 });
    expect(got).toEqual({ value: 0.75, scope: 'all', unknownGames: 2 });
  });

  it('窗口里有对局但一局都算不出执色 ⇒ 没有值,并把差额报出来', () => {
    const got = winrateCell({ ...base, games_in_window: 5, decided_games_in_window: 0, wins_in_window: 0, losses_in_window: 0 });
    expect(got.value).toBeNull();
    expect(got.unknownGames).toBe(5);
  });

  // 云端还没部署新版本时,老响应里没有这三个键 —— 退回升降级口径,**标签也要跟着退**。
  it('老云端(没有新字段)退回升降级口径', () => {
    const got = winrateCell({ ...base, games_in_window: 4, ranked_wins_in_window: 3, ranked_losses_in_window: 1 });
    expect(got).toEqual({ value: 0.75, scope: 'ranked', unknownGames: 0 });
  });

  it('一局没下时是 null,不是 0%', () => {
    expect(winrateCell({ ...base, decided_games_in_window: 0, games_in_window: 0 }).value).toBeNull();
  });
});
