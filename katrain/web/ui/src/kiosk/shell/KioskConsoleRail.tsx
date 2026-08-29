import type { ReactNode } from 'react';
import { KioskStatusCells, type StatusCell } from './KioskStatusCells';

/**
 * §5 L1 左栏。**四个模块几何完全一样,装的东西不同** —— 所以互切不跳:
 *   对弈 / 训练营 / 课程 / 棋谱 → 实体盘镜像(盘上正在发生什么)
 *   复盘                        → 上一局的终局盘(刚下完的那局是什么样)
 * 差别只在标题和同步行那句话。
 *
 * **左栏永不滚动**,恒为 434 固定高;滚动只属于右栏(规范 §5.2 第 7 条)。
 * **它是状态显示,不是入口** —— 落子方式(屏幕/实体盘)是每种对弈方式内部的二选一,不在这里。
 *
 * 纵向那串账一分不多一分不少(`tokens.css:435-474`):
 *   20(标题) + 10 + 272(镜像框) + 10 + 32(同步行) + 10 + 56(状态格) = 410
 *   = 434 − 2×1(描边) − 2×11(内边距)
 * 这串**曾经算错过 2px**(横向算了描边、纵向漏了),而标题行和状态格当时都没写 `flex:none`,
 * 被 flex 各压了 1px —— 肉眼看不出来。现在每块都 `flex:none`,再算错会顶破外框、当场看得见。
 */
export function KioskConsoleRail({ title, sub, board, syncLeft, syncRight, statuses }: {
  title: string;
  sub: string;
  board: ReactNode;
  syncLeft: string;
  syncRight: string;
  statuses: readonly StatusCell[];
}) {
  return (
    <aside className="kiosk-console">
      <div className="kiosk-console__title"><b>{title}</b><em>{sub}</em></div>
      <div className="kiosk-console__frame">
        <div className="kiosk-mini-board">{board}</div>
      </div>
      <div className="kiosk-console__sync"><span>{syncLeft}</span><b>{syncRight}</b></div>
      <KioskStatusCells cells={statuses} />
    </aside>
  );
}
