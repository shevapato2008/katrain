import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

/**
 * ⚠️ 2026-08-22(屏 14):`PhysicalModeToggle` 这个组件连同它那一组断言一起删了 ——
 * 做题屏按稿子重画之后,「实体棋盘」是共享外壳那排 `role="switch"` 里的一个
 * (Fan 2026-08-22:「galaxy 界面里都是开关这种形式,kiosk 也改成一样的」),
 * 没有第二个消费方。留下来的是**这两个读写函数**:开关换了长相,存在哪儿没变。
 */
import { readPhysicalMode, writePhysicalMode } from '../pages/tsumegoUnits';

describe('Physical mode persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('readPhysicalMode and writePhysicalMode', () => {
    it('should default to false with empty localStorage', () => {
      expect(readPhysicalMode()).toBe(false);
    });

    it('should persist and read true value', () => {
      writePhysicalMode(true);
      expect(readPhysicalMode()).toBe(true);
    });

    it('should persist and read false value', () => {
      writePhysicalMode(true);
      writePhysicalMode(false);
      expect(readPhysicalMode()).toBe(false);
    });

    it('should handle localStorage unavailability gracefully', () => {
      const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new Error('Storage unavailable');
      });
      const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('Storage unavailable');
      });

      expect(readPhysicalMode()).toBe(false);
      writePhysicalMode(true); // should not throw
      writePhysicalMode(false); // should not throw

      getItem.mockRestore();
      setItem.mockRestore();
    });
  });
});
