import { describe, expect, test } from 'vitest';
import { replayBaipuSteps } from './baipuReplay';
import type { BaipuStep } from '../api/baipuApi';

/**
 * `replayBaipuSteps` 是**笨播放器**:放子照 `(row,col,color)`,拿子照后端给的 `removed[]`,
 * 一条气都不算。它和后端的 `expected_board_from_steps`(`katrain/core/baipu.py:162-170`)
 * 是同一件事的两半 —— L2 QA 拿后端那份判「实体盘此刻该长什么样」,屏上画的是这一份,
 * **两份不一致就是屏和盘说两样话**。
 *
 * 坐标口径:后端 `row` 从上往下数(row 0 = 第 19 line),`canonToGtp` 负责换。
 */

const step = (o: Partial<BaipuStep>): BaipuStep => ({
  kind: 'move', move_index: 0, property: 'B', row: null, col: null, color: null,
  removed: [], board_hash: '', ...o,
} as BaipuStep);

describe('replayBaipuSteps —— 照 steps 播,不算规则', () => {
  test('放子:row 从上往下,0 是第 19 line', () => {
    const b = replayBaipuSteps([step({ row: 3, col: 15, color: 'B' })], 1, 19);
    expect(b.black).toEqual(['Q16']);
    expect(b.last).toBe('Q16');
  });

  test('stepCount 截断:只播前 k 步', () => {
    const steps = [
      step({ row: 3, col: 15, color: 'B' }),
      step({ row: 15, col: 3, color: 'W', property: 'W' }),
    ];
    expect(replayBaipuSteps(steps, 1, 19).white).toEqual([]);
    expect(replayBaipuSteps(steps, 2, 19).white).toEqual(['D4']);
  });

  test('提子:被 removed 点名的子从盘上消失', () => {
    const steps = [
      step({ row: 0, col: 1, color: 'W', property: 'W' }),
      step({ row: 0, col: 0, color: 'B', removed: [{ row: 0, col: 1 }] }),
    ];
    const b = replayBaipuSteps(steps, 2, 19);
    expect(b.white).toEqual([]);
    expect(b.black).toEqual(['A19']);
  });

  test('setup 步不改 last —— last 只跟着真落子走', () => {
    const steps = [
      step({ kind: 'setup', row: 3, col: 3, color: 'B', property: 'AB' }),
      step({ kind: 'pass', property: 'W', color: 'W' }),
    ];
    expect(replayBaipuSteps(steps, 2, 19).last).toBeUndefined();
  });

  /**
   * ⚠️ **2026-08-24 的回归闸。** 这里原来有一段 `if (kind==='clear') { stones.clear(); continue; }`
   * —— 整盘擦掉,还跳过了 `removed`。
   *
   * 后端的 `clear` 步(SGF 的 AE)语义是**只擦点名的那几颗**:`baipu.py:122-137` 把
   * `clear_placements` 命中的放进 `removed`,幸存的子原样留着;权威重建
   * `expected_board_from_steps` **只应用 `removed`**。
   *
   * 挂了的样子:摆谱屏画一块空盘,而实体盘上子全在,屏上还写着「把黑子放在 C7」。
   */
  test('clear(AE)只擦点名的那几颗,幸存的子留在盘上', () => {
    const steps = [
      step({ row: 3, col: 15, color: 'B' }),                                  // Q16 黑
      step({ row: 15, col: 3, color: 'W', property: 'W' }),                   // D4 白
      step({ row: 3, col: 3, color: 'B' }),                                   // D16 黑
      step({ kind: 'clear', property: 'AE', removed: [{ row: 3, col: 3 }] }), // 只擦 D16
    ];
    const b = replayBaipuSteps(steps, 4, 19);
    expect(b.black, 'AE 把整盘擦了 —— 幸存的 Q16 不见了').toEqual(['Q16']);
    expect(b.white, 'AE 把白子也擦了').toEqual(['D4']);
  });

  test('clear 步不改 last —— 它不是一手棋', () => {
    const steps = [
      step({ row: 3, col: 15, color: 'B' }),
      step({ kind: 'clear', property: 'AE', removed: [{ row: 0, col: 0 }] }),
    ];
    expect(replayBaipuSteps(steps, 2, 19).last).toBe('Q16');
  });
});
