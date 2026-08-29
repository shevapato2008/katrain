import type { BaipuGeometryCorrection } from '../../api/baipuApi';

/**
 * 「刚存下那一帧的几何」这一行怎么说 —— 屏 17 摆谱用。
 *
 * **返回的是事件不是译文**:`useTranslation()` 的 `t` 每次渲染都是新函数,
 * 译文存进 state 会在切语言之后留着上一种语言(这条 track 上栽过两次)。
 *
 * 三种要说话、两种不说:`corrected` 且**没**超阈值(那就是正常,不必报)和
 * `off`(压根没开基准点模式)都返回 `null`。
 *
 * ⚠️ 上一版这是一整条通栏横幅(`DriftBanner`)。固定 1024×600 里没有它的位置 ——
 * 右栏两个折叠块一共只剩 252px,再插一块就把着法表压到 3 行以下、逼右栏整栏滚,
 * 而整栏一滚「确认落子」就不再贴底。而且它说的本来就是**采集账里的一行**:
 * 漂移描述的是刚写下那一帧的性质。
 */
export type DriftLine = { key: 'corrected' | 'stale' | 'frozen'; bad: boolean };

export function driftLine(correction: BaipuGeometryCorrection | null): DriftLine | null {
  if (!correction) return null;
  const { status, drift } = correction;
  if (status === 'corrected') return drift?.over_threshold ? { key: 'corrected', bad: false } : null;
  if (status === 'stale') return { key: 'stale', bad: true };
  if (status === 'frozen') return { key: 'frozen', bad: true };
  return null;   // 'off'
}
