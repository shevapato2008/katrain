import { describe, it, expect } from 'vitest';
import { driftLine } from './baipuDrift';

/**
 * 从 `__tests__/DriftBanner.test.tsx` 搬过来的六条 —— **意图一个字没改**:
 * 五种几何状态里哪三种要说话、哪两种一声不吭。
 *
 * 变的只是落点:上一版那是一整条通栏横幅,2026-08-24 屏 17 重画时收进了摄像头折叠块的
 * 一行 + 折叠头右端的结论词(固定 516 里没有横幅的位置,见 `baipuDrift.ts` 头注)。
 * 断言从「渲染出了哪个 `data-drift-status`」换成「这个纯函数说什么」——
 * 屏上那一行由 `tests/kiosk-screen-17-baipu.fourup.spec.ts` 和真浏览器闸盯。
 */
describe('driftLine —— 几何漂移哪几种要说话', () => {
  it('没有 correction:不说话', () => {
    expect(driftLine(null)).toBeNull();
  });

  it('校正过、又没超阈值:不说话 —— 那就是正常', () => {
    expect(driftLine({ status: 'corrected', drift: { median_cells: 0.02, over_threshold: false } })).toBeNull();
  });

  it('校正过、但漂移超了阈值:说一声,不算警告', () => {
    expect(driftLine({ status: 'corrected', drift: { median_cells: 0.6, over_threshold: true } }))
      .toEqual({ key: 'corrected', bad: false });
  });

  it('这一帧没校正成、沿用了上次的:警告', () => {
    expect(driftLine({ status: 'stale', drift: { median_cells: 0.6, over_threshold: true } }))
      .toEqual({ key: 'stale', bad: true });
  });

  it('从来没校正过:警告', () => {
    expect(driftLine({ status: 'frozen', drift: { median_cells: 0, over_threshold: false } }))
      .toEqual({ key: 'frozen', bad: true });
  });

  it('压根没开基准点模式:不说话', () => {
    expect(driftLine({ status: 'off' })).toBeNull();
  });
});
