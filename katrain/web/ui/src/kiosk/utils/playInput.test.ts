import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';
import { PLAY_ON_BOARD_KEY, playInputState, readPlayOnBoard, writePlayOnBoard } from './playInput';

/**
 * 这里只钉**两个方向**,不重复页面已经测过的组合:
 *
 *  ① **默认是「开」。** 这是整次改动为什么是纯增量的全部依据 —— 默认取 `false` 的话,
 *     现有用户升级之后会莫名其妙地从实体盘上被踢下来,而且没有任何报错。
 *  ② **读不出来也回「开」。** 隐私模式 / localStorage 被禁时,回落方向必须是
 *     「和以前一样」,不是「把人从盘上赶下来」。这条只能靠让 getItem 抛来证。
 */
describe('playInput', () => {
  beforeEach(() => localStorage.removeItem(PLAY_ON_BOARD_KEY));
  afterEach(() => vi.restoreAllMocks());

  it('没写过偏好时默认用实体盘 —— 那正是这次改动之前的行为', () => {
    expect(readPlayOnBoard()).toBe(true);
  });

  it('localStorage 读不了时同样回落到实体盘,不是回落到屏幕', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
    expect(readPlayOnBoard()).toBe(true);
  });

  it('两段都成立才落在盘上,而灰掉的理由分得清是哪一段不成立', () => {
    writePlayOnBoard(true);
    expect(playInputState(true, 19)).toMatchObject({ onBoard: true, available: true, reason: null });
    expect(playInputState(false, 19)).toMatchObject({ onBoard: false, reason: 'noCamera' });
    expect(playInputState(true, 9)).toMatchObject({ onBoard: false, reason: 'notNineteen' });

    // 想不想那一段关掉时:**不是「不可用」** —— 实体盘还选得回来,所以没有理由可说。
    writePlayOnBoard(false);
    expect(playInputState(true, 19)).toMatchObject({ onBoard: false, available: true, reason: null });
  });
});
