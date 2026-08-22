import { canonToGtp, type BaipuStep } from '../api/baipuApi';

export interface BoardState {
  black: string[];
  white: string[];
  last?: string;
}

/**
 * 把 `/api/v1/baipu/load` 给的前 `stepCount` 步**原样播一遍**,得到那一刻的盘面。
 *
 * 放子用 `(row, col, color)`,拿子用后端给的 `removed[]` —— **两样都是数据,不是规则**。
 * 前端不算气、不判提子:那是 `baipuApi.ts` 决定 ② 定下的分工(前端是 `steps[]` 的笨播放器)。
 * `clear` 清盘(SGF 里的 AE / 重开)。
 *
 * 两个消费者:屏 16 棋谱详情逐手回放、屏 19 复盘左栏那块终局盘(`stepCount = steps.length`)。
 */
export function replayBaipuSteps(
  steps: readonly BaipuStep[],
  stepCount: number,
  size: number,
): BoardState {
  const stones = new Map<string, 'B' | 'W'>();
  let last: string | undefined;
  for (let i = 0; i < stepCount && i < steps.length; i += 1) {
    const s = steps[i];
    if (s.kind === 'clear') {
      stones.clear();
      last = undefined;
      continue;
    }
    if (s.row != null && s.col != null && s.color) {
      const coord = canonToGtp(s.row, s.col, size);
      stones.set(coord, s.color);
      if (s.kind === 'move') last = coord;
    }
    for (const p of s.removed) stones.delete(canonToGtp(p.row, p.col, size));
  }
  const black: string[] = [];
  const white: string[] = [];
  for (const [coord, color] of stones) (color === 'B' ? black : white).push(coord);
  return { black, white, last };
}
