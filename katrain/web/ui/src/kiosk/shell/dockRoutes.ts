import type { IconName } from './icons';

/**
 * §3 底部 Dock。**词与顺序来自四棋类共享词典,不是围棋能自选的**:
 *   对弈 · 训练营 · 复盘 · 成长 · 课程 · 设置
 * 棋种专属项最多再加 1 个,**插在「训练营」之后**;围棋用掉的那一个是「棋谱」。
 *
 * ⚠️ **2026-08-26 更正上面第二段。** 那里原来写着「『成长』本轮不在这里:围棋没有
 * growth 路由/页面/后端」—— 而 2026-08-25 的 `67821cba` 已经把屏 22 做出来并把这一项
 * 加进了下面的数组。**注释和它下面五行的代码互相矛盾了一整天**,而且那句话被抄进了
 * 九个四图 spec 的标签带,其中四个(屏 02/03/04/06)是 L2、**根本没有 Dock**,
 * 那句话在那儿从来就不适用。
 * ⇒ 判据:注释里断言「现在有几项 / 现在没有什么」的句子,**和它下面那个数组是同一份事实的两份拷贝**。
 *   改数组的那次提交必须一起改它,否则下一个人读到的是去年的盒子。
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
  // 成长钉在**复盘之后、课程之前**(稿子 27 屏版的 Dock 表)。
  // ⚠️ 这一项**围棋独有** —— 另外三家(象棋 / 国象 / 五子棋)的 Dock 还是六项。
  //    它靠的是 `ai_ladder_game_ledger`(每局带 `user_color` 和 `opponent_rung`),
  //    那三家有没有同形的账本要各自查,**不能拿这里的结论去推它们**。已登记在
  //    `superpowers/tracks/kiosk-go-shell-align/scope.md` §29。
  { path: '/kiosk/growth',   label: '成长',   icon: 'trend-up' },
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
