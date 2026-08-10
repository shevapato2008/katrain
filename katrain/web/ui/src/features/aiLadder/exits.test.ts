import { describe, expect, it, vi, afterEach } from 'vitest';
import { aiLadderExits, formatCountdown } from './exits';
import type { AiLadderBlockingGame } from './types';

const base: AiLadderBlockingGame = {
  game_id: 'game-1',
  state: 'active',
  ownership: 'other_device',
  user_color: 'B',
  opponent_rank_name: '业余 3 段',
};

afterEach(() => vi.useRealTimers());

describe('aiLadderExits', () => {
  it('一扇能按的门:此刻可用,没有倒计时可走', () => {
    // 原盒结束自己那局就是认输,不进接管窗口 —— 服务端给的正是 true + null。
    // 把这一格误读成「等不来」会把唯一的出路藏掉,而店里往往只有这一台机器。
    expect(aiLadderExits({ ...base, ownership: 'current_device', can_force_resign: true, takeover_eligible_in_seconds: null }))
      .toEqual([{ kind: 'resign', ready: true, readyInSeconds: null }]);
  });

  it('一扇等得到的门:给出真**时长**,好让屏上走秒', () => {
    // 时长而不是时刻:本机拿服务端的时刻去减自己的钟,差多少钟倒计时就错多少,
    // 而常年离线、没有可靠 NTP 的一体机正是钟偏最大的那一台(国象量出来的)。
    expect(aiLadderExits({ ...base, can_force_resign: false, takeover_eligible_in_seconds: 252 }))
      .toEqual([{ kind: 'resign', ready: false, readyInSeconds: 252 }]);
  });

  it('时刻在场也不作数 —— 只发时刻的旧服务端,这扇门就不出现', () => {
    // 断言的是「走秒**只**从时长算起」。若哪天有人把它改回读时刻,这条当场红。
    expect(aiLadderExits({ ...base, can_force_resign: false, takeover_eligible_at: '2026-08-11T04:05:06.000Z' }))
      .toEqual([]);
  });

  it('等不来的门根本不出现 —— 不是画一个永远按不动的按钮', () => {
    // `false + null` 的含义是「这扇门对这一格不适用」,不是「再等等」。
    // 摆一个既按不动、又没有期限的按钮,用户只会一直戳它。
    expect(aiLadderExits({ ...base, can_force_resign: false, takeover_eligible_in_seconds: null })).toEqual([]);
  });

  it('服务端没发这组字段时,这扇门不存在', () => {
    // 键不在 = 这一格没有这扇门(服务端只在能承载答案时才发)。
    expect(aiLadderExits(base)).toEqual([]);
  });

  it('两扇门同时在的时候,认输排在放弃前面', () => {
    const exits = aiLadderExits({
      ...base,
      state: 'pending_settlement',
      can_force_resign: false,
      takeover_eligible_in_seconds: null,
      can_release_abandoned_settlement: true,
      abandoned_settlement_eligible_in_seconds: null,
    });
    expect(exits).toEqual([{ kind: 'release', ready: true, readyInSeconds: null }]);
  });

  it('坏时长当作没有,而不是当作 0(那会让门立刻开)', () => {
    const broken = { ...base, can_force_resign: false, takeover_eligible_in_seconds: Number.NaN };
    expect(aiLadderExits(broken)).toEqual([]);
  });

  it('负时长夹到 0,而不是显示「还需 -137 秒」', () => {
    expect(aiLadderExits({ ...base, can_force_resign: false, takeover_eligible_in_seconds: -137 }))
      .toEqual([{ kind: 'resign', ready: false, readyInSeconds: 0 }]);
  });
});

describe('formatCountdown', () => {
  it.each([
    [252_000, '4:12'],
    [59_000, '0:59'],
    [9_000, '0:09'],
    [0, '0:00'],
    [-5_000, '0:00'],
    [3_800_000, '1:03:20'],
  ])('%i 毫秒 → %s', (ms, text) => {
    expect(formatCountdown(ms)).toBe(text);
  });

  it('向上取整,好让最后一秒显示 0:01 而不是 0:00', () => {
    // 显示 0:00 却还按不动,是这块屏最不该出现的那一句。
    expect(formatCountdown(1)).toBe('0:01');
  });
});
