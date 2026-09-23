import { describe, expect, test } from 'vitest';
import { readGoClock, type GoClockInput } from './goClock';

const input = (over: Partial<GoClockInput> = {}): GoClockInput => ({
  mainTimeMin: 5, byoLength: 30, byoPeriods: 3, mainUsed: 0, periodsUsed: 0, nodeTimeUsed: 0, active: true, elapsed: 0, ...over,
});

describe('readGoClock —— 与 interface.py update_timer 同一套算法', () => {
  test('主时间里:只扣主时间,读秒还没开始', () => {
    expect(readGoClock(input({ mainUsed: 100, elapsed: 20 }))).toEqual({ mainLeft: 180, byoLeft: null, periodsLeft: 3, expired: false });
  });

  test('不轮到的一方不外推本地流逝', () => {
    expect(readGoClock(input({ mainUsed: 100, elapsed: 20, active: false })).mainLeft).toBe(200);
  });

  test('主时间在这一手里用完:超出的部分才进读秒', () => {
    // 这一手开始时还剩 10 秒主时间,已经想了 25 秒 ⇒ 读秒用掉 15 秒
    expect(readGoClock(input({ mainUsed: 290, elapsed: 25 }))).toEqual({ mainLeft: 0, byoLeft: 15, periodsLeft: 3, expired: false });
  });

  test('每满一次读秒长度记一次,次数用完即超时', () => {
    expect(readGoClock(input({ mainTimeMin: 0, elapsed: 65 }))).toEqual({ mainLeft: 0, byoLeft: 25, periodsLeft: 1, expired: false });
    expect(readGoClock(input({ mainTimeMin: 0, elapsed: 91 })).expired).toBe(true);
  });

  test('只有主时间、没有读秒:主时间用完即超时', () => {
    expect(readGoClock(input({ byoLength: 0, byoPeriods: 0, mainUsed: 300 })).expired).toBe(true);
  });
});
