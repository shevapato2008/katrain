/**
 * 围棋盘的坐标与几何 —— **一份,四屏共用**。
 *
 * 这些常量原来锁在 `components/board/KioskSetupBoard.tsx` 私有作用域里。抽出来不是为了
 * 「以后可能有用」:对局屏(Task 11)和做题屏(Task 14)都要按坐标摆子,拿不到就会各抄一份 ——
 * 而这套东西**每一条都容易抄错**(跳 I、行号 1 在最下、九星在 4/10/16 线、留白 0.5 格),
 * 抄错了屏上看着还挺像。本轮的教训之一就是「两份并行实现」。
 *
 * ⚠️ 这里只放**算式**,不放长相。线宽、颜色、木框归 CSS 和各自的组件。
 */

/** 跳 I:A–S 跳掉 I 只有 18 个,19 路要写到 T。 */
export const GO_COLS = 'ABCDEFGHJKLMNOPQRST';

/**
 * 留白 0.5 格。**这个数是被闸算出来的,不是取的**:
 * 刻度带把 N 个字均分在落子区上,第 i 个字心在 `(i+0.5)/N`;盘上第 i 条线在 `(margin+i)/(N-1+2·margin)`。
 * 两式相等当且仅当 `margin = 0.5`。拿 1.5 的盘(galaxy `LiveBoard` 就是)配 0.5 的刻度带,
 * 字和线整整错开一格(≈24px),不是「差几个像素」。
 */
export const GO_MARGIN = 0.5;

/** 星位按路数换,不是同一组坐标缩放:9 路的星在 3-3,19 路在 4-4(这里是 0 起索引)。 */
const STARS_BY_SIZE: Record<number, readonly (readonly [number, number])[]> = {
  9: [[2, 2], [2, 6], [6, 2], [6, 6], [4, 4]],
  13: [[3, 3], [3, 9], [9, 3], [9, 9], [6, 6]],
  19: [[3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15]],
};

export const STARS_19 = STARS_BY_SIZE[19];

export function starsFor(size: number): readonly (readonly [number, number])[] {
  return STARS_BY_SIZE[size] ?? [];
}

/** 这一路数用到的列名。9 路取前 9 个,跳 I 这条一样成立。 */
export function colsFor(size: number): string[] {
  return [...GO_COLS].slice(0, size);
}

/** 从上往下读的行号:19…1。行号 1 在**最下**。 */
export function rowsFor(size: number): number[] {
  return Array.from({ length: size }, (_, i) => size - i);
}

/**
 * `"Q16"` → `{ x: 15, y: 3 }`(0 起索引,y 从**上**往下数)。
 *
 * 记法是**绝对**的:A1 永远是左下那个角,不跟着执棋方翻。SGF 记谱、棋谱库、对局屏都按它。
 * (别把理由写成「空盘 180° 对称所以翻不翻都一样」—— 那句是错的:让子局不对。)
 */
export function coordToXY(coord: string, size = 19): { x: number; y: number } {
  return { x: GO_COLS.indexOf(coord[0]), y: size - parseInt(coord.slice(1), 10) };
}

/** 四条刻度带上第 i 格写什么:上下 A–T,左右 19–1。 */
export function labelFor(band: 'top' | 'bottom' | 'left' | 'right', i: number, size = 19): string {
  return band === 'top' || band === 'bottom' ? GO_COLS[i] : String(size - i);
}

/** 第 i 条线在 SVG 内部坐标里的位置(单位 `unit`,默认 100)。 */
export function lineAt(i: number, unit = 100): number {
  return (GO_MARGIN + i) * unit;
}

/** 这一路数的 viewBox 边长。 */
export function boardExtent(size: number, unit = 100): number {
  return (size - 1 + 2 * GO_MARGIN) * unit;
}

/**
 * 让 `n` 子时盘上那几颗黑子，写成 `["Q16","D4"]` 这样的坐标。
 *
 * **算式照后端那一份搬**：`katrain/core/sgf_parser.py:374 place_handicap_stones`
 * 的 `n <= 9` 那一支。开局设置屏左边那块盘按规范 §11 画的是「按下按钮后**真会出现**
 * 的那个局面」——让子局的起始局面就是带着这几颗子的，画成空盘等于画错了局面。
 *
 * 顺序不是随便排的：先两个对角、再另两个角、奇数补天元、最后四个边星。
 * 取前 `n` 个。**下标的 y 方向在这里不用纠结** —— `n ≤ 9` 那一支取出来的集合
 * 在上下翻转下不变（角是四个全取或不取、天元在中心、四个边星成对），
 * 所以前端 y 朝下、后端 y 朝上这件事不改变结果。实测 2 子 = `Q16` + `D4`，和稿子一致。
 *
 * `n > 9` 后端另有一支（按 `ceil(sqrt(n))` 铺格），这里不抄：让子上限就是 9
 * （`pages/AiSetupPage.tsx` 的档位轨 0–9），抄一段没人走的分支只是多一处要维护的算式。
 */
export function handicapStones(size: number, n: number): string[] {
  if (n < 2 || size < 3) return [];
  const near = size >= 13 ? 3 : Math.min(2, size - 1);
  const far = size - 1 - near;
  const mid = Math.floor(size / 2);
  const pts: [number, number][] = [[far, far], [near, near], [far, near], [near, far]];
  if (n % 2 === 1) pts.push([mid, mid]);
  pts.push([near, mid], [far, mid], [mid, near], [mid, far]);
  return pts.slice(0, Math.min(n, 9)).map(([x, y]) => `${GO_COLS[x]}${y + 1}`);
}
