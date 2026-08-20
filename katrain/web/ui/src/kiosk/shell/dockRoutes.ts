import type { IconName } from './icons';

/**
 * §3 底部 Dock。**词与顺序来自四棋类共享词典,不是围棋能自选的**:
 *   对弈 · 训练营 · 复盘 · 成长 · 课程 · 设置
 * 棋种专属项最多再加 1 个,**插在「训练营」之后**;围棋用掉的那一个是「棋谱」。
 *
 * 「成长」本轮不在这里:围棋没有 growth 路由/页面/后端(scope.md 决策一,Fan 2026-08-20)。
 * 摆假入口比缺一格更坏 —— 见 G8。这条差异登记在 D6,四图的标签带里要写出来。
 *
 * 「设置」在这里,所以顶栏没有齿轮(规范 §1,D9)。这两件事是同一个决定的两半,
 * 改任何一半之前先看另一半。
 */
export interface DockTab { path: string; label: string; icon: IconName }

export const DOCK_TABS: readonly DockTab[] = [
  { path: '/kiosk/play',     label: '对弈',   icon: 'game-controller' },
  { path: '/kiosk/tsumego',  label: '训练营', icon: 'puzzle-piece' },
  { path: '/kiosk/kifu',     label: '棋谱',   icon: 'books' },
  { path: '/kiosk/report',   label: '复盘',   icon: 'grid-nine' },
  { path: '/kiosk/tutorial', label: '课程',   icon: 'book-open' },
  { path: '/kiosk/settings', label: '设置',   icon: 'gear' },
];

const norm = (p: string) => (p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p);

/**
 * 高亮哪一项。二/三级页高亮它的**父项**(做题屏 → 训练营,对局屏 → 对弈)。
 *
 * 下了 Dock 的三条(baipu / live / research)**返回 null** —— 它们没有父项,
 * 乱认一个父项等于告诉用户「你在棋谱里」,而 Dock 上那一格并没有把他带到这儿来。
 *
 * 前缀匹配卡在 `/` 上,不是裸 startsWith:`/kiosk/playground` 不许点亮「对弈」。
 * 排序取最长前缀,免得将来加了嵌套路由时短的先命中。
 */
export function dockActiveOf(pathname: string): string | null {
  const p = norm(pathname);
  const hit = [...DOCK_TABS]
    .sort((a, b) => b.path.length - a.path.length)
    .find((t) => p === t.path || p.startsWith(`${t.path}/`));
  return hit ? hit.path : null;
}

/**
 * 1 = 一级页(有 Dock,中间区 434 高);2 = 二/三级页(无 Dock,516 高)。
 *
 * **层级跟着屏走,不跟着路由前缀走** —— 国象踩过:复盘分析屏挂在 review 这条 L1 路由下
 * 但其实是 L2,判错就从 516 的盘上裁掉 82px。所以这里是**全等**比较,不是前缀。
 */
export function dockLevelOf(pathname: string): 1 | 2 {
  const p = norm(pathname);
  return DOCK_TABS.some((t) => t.path === p) ? 1 : 2;
}
