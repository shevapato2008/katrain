import { describe, expect, test } from 'vitest';
import { DOCK_TABS, dockActiveOf, dockLevelOf } from './dockRoutes';

describe('DOCK_TABS —— 词与顺序是四棋类共享词典,不是围棋能自选的', () => {
  test('顺序写死:对弈 训练营 棋谱 复盘 成长 课程 设置', () => {
    expect(DOCK_TABS.map((t) => t.label)).toEqual(
      ['对弈', '训练营', '棋谱', '复盘', '成长', '课程', '设置'],
    );
  });

  // 成长的位置也是稿子定死的:**复盘之后、课程之前**。
  // ⚠️ 这一项围棋独有,另外三家还是六项 —— 见 `dockRoutes.ts` 上那条注释。
  test('「成长」钉在「复盘」之后、「课程」之前', () => {
    const labels = DOCK_TABS.map((t) => t.label);
    expect(labels.indexOf('成长')).toBe(labels.indexOf('复盘') + 1);
    expect(labels.indexOf('课程')).toBe(labels.indexOf('成长') + 1);
  });

  test('专属项「棋谱」钉在「训练营」之后 —— 位置也是规范定死的', () => {
    const labels = DOCK_TABS.map((t) => t.label);
    expect(labels.indexOf('棋谱')).toBe(labels.indexOf('训练营') + 1);
  });

  test('不超过 7 项(--dock-max-items)', () => {
    expect(DOCK_TABS.length).toBeLessThanOrEqual(7);
    // §17.1:「不超过 N」那一侧要配下界,不然一项不放也算过。
    expect(DOCK_TABS.length).toBeGreaterThanOrEqual(7);
  });

  test('图标全部来自 Phosphor 词典(§10),不是随手挑的近似图标', () => {
    expect(DOCK_TABS.map((t) => t.icon)).toEqual(
      ['game-controller', 'puzzle-piece', 'books', 'grid-nine', 'trend-up', 'book-open', 'gear'],
    );
  });
});

describe('dockLevelOf —— 层级跟着**屏**走,不跟着路由前缀走', () => {
  test('六个 L1 目标是 1 级', () => {
    for (const t of DOCK_TABS) expect(dockLevelOf(t.path)).toBe(1);
  });

  test('对局屏不是一级页 —— 它挂在 play 底下,但没有 Dock', () => {
    expect(dockLevelOf('/kiosk/play/ai/game/abc')).toBe(2);   // 2 = 无 Dock 的那一档
  });

  test('单元列表是训练营的二级页', () => {
    expect(dockLevelOf('/kiosk/tsumego/15k/capturing')).toBe(2);
  });

  test('尾斜杠不改变层级', () => {
    expect(dockLevelOf('/kiosk/play/')).toBe(1);
  });
});

describe('dockActiveOf —— 二/三级页高亮它的父项', () => {
  test('做题屏高亮训练营', () => {
    expect(dockActiveOf('/kiosk/tsumego/problem/42')).toBe('/kiosk/tsumego');
  });
  test('对局屏高亮对弈', () => {
    expect(dockActiveOf('/kiosk/play/ai/game/abc')).toBe('/kiosk/play');
  });
  test('下了 Dock 的三条路由没有父项 —— 一个都不许乱高亮', () => {
    expect(dockActiveOf('/kiosk/baipu')).toBe(null);
    expect(dockActiveOf('/kiosk/live')).toBe(null);
    expect(dockActiveOf('/kiosk/research')).toBe(null);
  });
  test('最长前缀优先:report/:taskId 高亮复盘,不是别的', () => {
    expect(dockActiveOf('/kiosk/report/7')).toBe('/kiosk/report');
  });
  // 前缀匹配必须卡在**路径分隔符**上。只写 startsWith(t.path),
  // 将来加一条 /kiosk/playground 就会点亮「对弈」——用户在别的屏上,Dock 却说他在对弈里。
  test('同前缀但不同段的路由不许被认领', () => {
    expect(dockActiveOf('/kiosk/playground')).toBe(null);
    expect(dockActiveOf('/kiosk/reports')).toBe(null);
  });
});
