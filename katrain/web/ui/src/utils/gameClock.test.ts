import { describe, expect, it } from 'vitest';
import { computeClock, type ClockInput } from './gameClock';

const S = (main_time: number, byo_length = 30, byo_periods = 3) => ({ main_time, byo_length, byo_periods });
const input = (over: Partial<ClockInput>): ClockInput => ({
  settings: S(10), mainTimeUsed: 0, periodsUsed: 0, nodeTimeUsed: 0, active: true, clientElapsed: 0, ...over,
});

/**
 * `components/PlayerCard.tsx`(HEAD 1b6c67b5,L109-166)抽函数**之前**的算法,逐行照抄,
 * 只删了提示音那段副作用。它在这里只做一件事:证明抽出来的 `computeClock` 在 galaxy
 * 能开出来的用时范围内**一个数都没变**。
 *
 * 删除条件:galaxy 玩家卡的钟**有意**改行为的那一次提交,连同下面那条「逐格对照」一起删。
 */
function legacyPlayerCard(i: ClockInput) {
  let mainTimeLeft = 0;
  let byoyomiLeft = 0;
  let periodsLeft = 0;
  let showTimer = false;
  const settings = i.settings;
  if (settings && (settings.main_time > 0 || settings.byo_length > 0)) {
    showTimer = true;
    const byoNum = settings.byo_periods;
    const byoLen = settings.byo_length;
    const mainTimeTotal = settings.main_time * 60;
    const currentMainUsed = i.mainTimeUsed + (i.active && mainTimeTotal > i.mainTimeUsed ? i.clientElapsed : 0);
    mainTimeLeft = Math.max(0, mainTimeTotal - currentMainUsed);
    if (mainTimeLeft > 0) {
      byoyomiLeft = byoLen;
      periodsLeft = byoNum - i.periodsUsed;
    } else {
      const mainTimeAvailableAtNodeStart = Math.max(0, mainTimeTotal - i.mainTimeUsed);
      const totalNodeTime = i.nodeTimeUsed + (i.active ? i.clientElapsed : 0);
      let effectiveNodeTimeUsed = Math.max(0, totalNodeTime - mainTimeAvailableAtNodeStart);
      let currentPeriodsUsed = i.periodsUsed;
      while (effectiveNodeTimeUsed > byoLen && currentPeriodsUsed < byoNum) {
        effectiveNodeTimeUsed -= byoLen;
        currentPeriodsUsed += 1;
      }
      if (currentPeriodsUsed >= byoNum) {
        byoyomiLeft = 0;
        periodsLeft = 0;
      } else {
        byoyomiLeft = Math.max(0, byoLen - effectiveNodeTimeUsed);
        periodsLeft = byoNum - currentPeriodsUsed;
      }
    }
  }
  const hasTimedOut = showTimer && mainTimeLeft <= 0 && periodsLeft <= 0 && byoyomiLeft <= 0;
  return { showTimer, mainTimeLeft, byoyomiLeft, periodsLeft, hasTimedOut };
}

describe('computeClock —— PlayerCard 抽函数前后逐格一致(galaxy 行为不变)', () => {
  it('galaxy 开得出的用时范围内,每一格的四个数和「超时」都和旧算法相同', () => {
    // galaxy 开局设置的滑块:主时间 0-60 分、读秒 5-60 秒、次数 1-10(galaxy/pages/AiSetupPage.tsx:771-786);
    // 不计时那一档写 main_time=0 / byo_length=0。
    const settingsGrid = [null, S(0, 0, 3), S(0, 30, 3), S(1, 5, 1), S(10, 30, 3), S(60, 60, 10)];
    let checked = 0;
    for (const settings of settingsGrid) {
      for (const mainTimeUsed of [0, 30, 59.5, 60, 600, 3600]) {
        for (const periodsUsed of [0, 1, 3]) {
          for (const nodeTimeUsed of [0, 4, 29.9]) {
            for (const active of [true, false]) {
              for (const clientElapsed of [0, 0.4, 25, 31, 95]) {
                const i = { settings, mainTimeUsed, periodsUsed, nodeTimeUsed, active, clientElapsed };
                const legacy = legacyPlayerCard(i);
                const v = computeClock(i);
                expect({ ...v, phase: undefined, hasTimedOut: v.phase === 'expired' && v.showTimer },
                  JSON.stringify(i)).toEqual({ ...legacy, phase: undefined });
                checked += 1;
              }
            }
          }
        }
      }
    }
    expect(checked).toBe(6 * 6 * 3 * 3 * 2 * 5);
  });
});

describe('computeClock —— 三个阶段', () => {
  it('没有设置 / 不限时那一档(main 0 · byo 0):不显示钟,四个数全 0', () => {
    expect(computeClock(input({ settings: null }))).toEqual(
      { showTimer: false, phase: 'main', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 });
    expect(computeClock(input({ settings: S(0, 0, 3), clientElapsed: 500 })).showTimer).toBe(false);
  });

  it('主时间阶段:剩余主时间随客户端流逝减少;没轮到的一方不减', () => {
    expect(computeClock(input({ mainTimeUsed: 18 }))).toMatchObject({ phase: 'main', mainTimeLeft: 582, byoyomiLeft: 30, periodsLeft: 3 });
    expect(computeClock(input({ mainTimeUsed: 18, clientElapsed: 12 })).mainTimeLeft).toBe(570);
    expect(computeClock(input({ mainTimeUsed: 18, clientElapsed: 12, active: false })).mainTimeLeft).toBe(582);
  });

  it('客户端流逝跨过主时间:只有超出主时间的那部分进读秒', () => {
    // 快照时主时间还剩 10 秒,又过了 20 秒 ⇒ 读秒用了 10 秒
    expect(computeClock(input({ mainTimeUsed: 590, clientElapsed: 20 })))
      .toMatchObject({ phase: 'byoyomi', mainTimeLeft: 0, byoyomiLeft: 20, periodsLeft: 3 });
  });

  it('读秒阶段:服务端残量 + 客户端流逝;用满一段才扣一次', () => {
    expect(computeClock(input({ mainTimeUsed: 600, periodsUsed: 1, nodeTimeUsed: 6 })))
      .toMatchObject({ phase: 'byoyomi', byoyomiLeft: 24, periodsLeft: 2 });
    expect(computeClock(input({ mainTimeUsed: 600, periodsUsed: 1, nodeTimeUsed: 6, clientElapsed: 30 })))
      .toMatchObject({ phase: 'byoyomi', byoyomiLeft: 24, periodsLeft: 1 });
  });

  it('次数用满 ⇒ expired,三个数全 0', () => {
    expect(computeClock(input({ mainTimeUsed: 600, periodsUsed: 3 })))
      .toEqual({ showTimer: true, phase: 'expired', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 });
  });
});

describe('computeClock —— 与后端 update_timer / is_time_exhausted 的边界一致', () => {
  // 同一组数在 tests/test_time_exhausted.py 里喂给真的 `WebKaTrain.update_timer`。
  // 「仅读秒 30秒×3」(setupOptions.ts 的 byoOnly):主时间 0。
  const byoOnly = (clientElapsed: number) =>
    computeClock(input({ settings: S(0, 30, 3), clientElapsed }));

  it('正好 90.0 秒:后端循环是 `>`,第三段还没用满 ⇒ 不是 expired', () => {
    expect(byoOnly(90)).toMatchObject({ phase: 'byoyomi', byoyomiLeft: 0, periodsLeft: 1 });
  });

  it('89.5 秒:还剩半秒、一次', () => {
    expect(byoOnly(89.5)).toMatchObject({ phase: 'byoyomi', byoyomiLeft: 0.5, periodsLeft: 1 });
  });

  it('90.5 秒:三段用满 ⇒ expired', () => {
    expect(byoOnly(90.5).phase).toBe('expired');
  });

  it('byo_periods 为 0 时按 max(1, …) 算一次(后端同一套);原 PlayerCard 会在主时间一到就判超时', () => {
    const v = computeClock(input({ settings: S(10, 30, 0), mainTimeUsed: 600 }));
    expect(v).toMatchObject({ phase: 'byoyomi', byoyomiLeft: 30, periodsLeft: 1 });
    expect(legacyPlayerCard(input({ settings: S(10, 30, 0), mainTimeUsed: 600 })).hasTimedOut).toBe(true);
  });
});
