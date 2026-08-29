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
 *
 * ## `clear`(SGF 的 AE)**不清盘** —— 2026-08-24 修
 *
 * 这里原来有一段 `if (s.kind === 'clear') { stones.clear(); continue; }`,**两处都错**:
 * 既把整盘擦了,又 `continue` 跳过了 `removed` 那一圈。
 *
 * 后端给 `clear` 步的语义是**只擦 AE 点名的那几颗**:`katrain/core/baipu.py:122-137`
 * 把 `clear_placements` 命中的子放进这一步的 `removed`,幸存的子原样留在盘上;
 * 而权威重建函数 `expected_board_from_steps`(同文件 `:162-170`,L2 QA 拿它判「实体盘此刻
 * 应该长什么样」)**只应用 `removed`,一次都不清盘**。
 *
 * ⇒ 遇到一条只擦几颗子的 AE,前端会把整盘画空,而实体盘上子还都在 ——
 * 摆谱屏(屏 17)上就是「一块空盘 + 一句『把黑子放在 C7』」。
 * 修法是**取消这个特例**:`clear` 步的 `row/col` 恒为 `null`(后端 `:134-135`),
 * 放子那一支本来就不走,自然落到 `removed` 那一圈 —— 和后端逐行同构。
 *
 * 三个消费者:屏 16 棋谱详情逐手回放、屏 19 复盘左栏那块终局盘(`stepCount = steps.length`)、
 * 屏 17 摆谱进行中。
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
