import type { StatusCell } from './KioskStatusCells';

/**
 * 围棋盘上**真有的**三样东西。规范 §5:统一的是格数、几何和灯色语义,**不是器件名** ——
 * 国象/象棋盘上根本没有摄像头,五子棋盘上没有 LED。说明书上没有的东西,界面上不能有。
 *
 * 值是「—」而不是「未连接」:还没读到状态 ≠ 读到了「没连上」。也不给 tone ——
 * 没有灯,比亮一颗颜色不对的灯诚实(G8)。
 *
 * 单独一个文件、不跟组件同住:`KioskStatusCells.tsx` 里一起导出会撞
 * `react-refresh/only-export-components`(那条规则要求一个文件只导出组件)。
 */
export const GO_HARDWARE_CELLS: readonly StatusCell[] = [
  { label: '摄像头', value: '—' },
  { label: '标定', value: '—' },
  { label: 'LED', value: '—' },
];
