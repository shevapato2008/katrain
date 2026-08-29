import { describe, expect, test } from 'vitest';
import { calculateKioskScale } from './kioskScale';

// 画布是固定的 1024×600(规范开头那句「画布:固定 1024×600 …本规范全部用 px」)。
// 这个函数只回答一件事:真视口装不装得下那块固定画布,装不下缩多少。
describe('calculateKioskScale', () => {
  test('设备基准 1024×600 正好是 1:1,不缩', () => {
    expect(calculateKioskScale(1024, 600)).toBe(1);
  });

  test('视口更大也不放大 —— 放大会把 px 尺规变成谎话', () => {
    expect(calculateKioskScale(1920, 1080)).toBe(1);
  });

  test('宽度不够时按宽度缩', () => {
    expect(calculateKioskScale(800, 600)).toBe(800 / 1024);
  });

  test('高度不够时按高度缩', () => {
    expect(calculateKioskScale(1024, 300)).toBe(300 / 600);
  });

  test('两边都不够取更紧的那一边', () => {
    expect(calculateKioskScale(512, 450)).toBe(0.5); // 512/1024=0.5 < 450/600=0.75
  });
});
